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
            ("notified", "BOOLEAN DEFAULT 0"),
            ("verdict", "VARCHAR(20)"),
        ):
            if column not in existing:
                logger.info(f"Migrating: adding column {column} to recognition_events")
                conn.exec_driver_sql(
                    f"ALTER TABLE recognition_events ADD COLUMN {column} {ddl_type}"
                )

        existing_training_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(training_images)")
        }
        for column, ddl_type in (
            ("frigate_source_filename", "VARCHAR(500)"),
            ("quality_warning", "VARCHAR(255)"),
        ):
            if column not in existing_training_columns:
                logger.info(f"Migrating: adding column {column} to training_images")
                conn.exec_driver_sql(
                    f"ALTER TABLE training_images ADD COLUMN {column} {ddl_type}"
                )

        existing_embedding_columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(embeddings)")
        }
        for column, ddl_type in (
            ("training_image_id", "INTEGER REFERENCES training_images(id)"),
        ):
            if column not in existing_embedding_columns:
                logger.info(f"Migrating: adding column {column} to embeddings")
                conn.exec_driver_sql(
                    f"ALTER TABLE embeddings ADD COLUMN {column} {ddl_type}"
                )

        conn.commit()


def _load_settings_overrides():
    """
    Ensure the single-row AppSettings override table exists, then apply any
    non-NULL column onto the shared config.settings singleton — since every
    module does `from config import settings` and shares that same object,
    this attribute assignment takes effect everywhere immediately, no
    further plumbing needed. Imported locally to avoid a database.py <->
    models.settings import cycle (models.settings imports Base from here).
    """
    from config import settings
    from models.settings import AppSettings

    db = SessionLocal()
    try:
        row = db.query(AppSettings).filter_by(id=1).first()
        if row is None:
            row = AppSettings(id=1)
            db.add(row)
            db.commit()
            db.refresh(row)

        for column in AppSettings.__table__.columns:
            if column.name == "id":
                continue
            value = getattr(row, column.name)
            if value is not None:
                setattr(settings, column.name, value)
    finally:
        db.close()


def init_db():
    """Create all tables."""
    logger.info("Initializing database...")
    from models.settings import AppSettings  # noqa: F401 — register table with Base

    Base.metadata.create_all(bind=engine)
    _migrate_add_missing_columns()
    _load_settings_overrides()
    logger.info("Database initialized successfully")
