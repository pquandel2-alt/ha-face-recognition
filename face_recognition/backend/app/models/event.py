from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float
from sqlalchemy.orm import relationship

from database import Base


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id = Column(Integer, primary_key=True)
    camera = Column(String(255), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    person_name = Column(String(255), nullable=False)  # Copy of name for history
    confidence = Column(Float, nullable=False)
    snapshot_path = Column(String(512), nullable=True)
    frigate_event_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="events")
