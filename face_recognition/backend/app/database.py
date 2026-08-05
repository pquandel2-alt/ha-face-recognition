import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

logger = logging.getLogger(__name__)

# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)

# For SQLite, convert to file:// URL if needed
if settings.database_url.startswith("sqlite"):
    # SQLite requires 4 slashes for absolute paths: sqlite:////path/to/file
    db_url = settings.database_url
else:
    db_url = settings.database_url

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_add_missing_columns():
    """
    Base.metadata.create_all() only creates missing tables, it never adds
    columns to a table that already exists. Patch new columns onto an
    existing recognition_events table here so upgrades don't silently
    lose new fields on users' already-populated databases.
    """
    with engine.connect() as conn:
        existing = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(recognition_events)")
        }
        for column, ddl_type in (
            ("frigate_sub_label", "VARCHAR(255)"),
            ("frigate_sub_label_score", "FLOAT"),
        ):
            if column not in existing:
                logger.info(f"Migrating: adding column {column} to recognition_events")
                conn.exec_driver_sql(
                    f"ALTER TABLE recognition_events ADD COLUMN {column} {ddl_type}"
                )

        existing_training_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(training_images)")
        }
        for column, ddl_type in (("frigate_source_filename", "VARCHAR(500)"),):
            if column not in existing_training_columns:
                logger.info(f"Migrating: adding column {column} to training_images")
                conn.exec_driver_sql(
                    f"ALTER TABLE training_images ADD COLUMN {column} {ddl_type}"
                )

        conn.commit()


def init_db():
    """Create all tables."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()
    logger.info("Database initialized successfully")
