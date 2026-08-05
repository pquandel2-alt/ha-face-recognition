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
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="training_images")


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    vector_json = Column(Text, nullable=False)  # JSON serialized 512-dim vector
    image_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="embeddings")
