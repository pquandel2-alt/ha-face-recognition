from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import relationship

from database import Base


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    training_images = relationship("TrainingImage", back_populates="person", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="person", cascade="all, delete-orphan")
    events = relationship("RecognitionEvent", back_populates="person")


class TrainingImage(Base):
    __tablename__ = "training_images"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    filename = Column(String(255), nullable=False)  # relative path in data/images/
    face_detected = Column(Boolean, default=False)
    has_embedding = Column(Boolean, default=False)
    source = Column(String(50), default="upload")  # "upload" or "frigate_import"
    frigate_event_id = Column(String(255), nullable=True)
    # "<frigate_name>/<filename>" of the source image in Frigate's /api/faces
    # bucket, when imported via the "Trainierte Gesichter" flow. Used to skip
    # re-importing the same image on a later Frigate-import run.
    frigate_source_filename = Column(String(500), nullable=True)
    # Comma-separated list of quality issues found at upload/import time
    # (e.g. "blurry,low_contrast"), or NULL if the image passed both checks.
    # Informational only — the image is still saved and usable for training.
    quality_warning = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="training_images")
    embeddings = relationship(
        "Embedding", back_populates="training_image", cascade="all, delete-orphan"
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    # One row per training image (per-image embeddings, not an averaged
    # centroid) — enables k-NN matching in FaceEngine.find_best_match instead
    # of comparing against a single mean vector per person. NULL only for
    # legacy rows from before this column existed.
    training_image_id = Column(Integer, ForeignKey("training_images.id"), nullable=True)
    vector_json = Column(Text, nullable=False)  # JSON serialized 512-dim vector
    # Legacy field from the averaged-embedding model; always 1 for per-image
    # rows. Kept to avoid a SQLite DROP COLUMN migration for a harmless field.
    image_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="embeddings")
    training_image = relationship("TrainingImage", back_populates="embeddings")
