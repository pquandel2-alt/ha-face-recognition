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


def init_db():
    """Create all tables."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")
