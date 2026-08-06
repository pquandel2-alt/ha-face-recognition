from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Float
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
    frigate_sub_label = Column(String(255), nullable=True)
    frigate_sub_label_score = Column(Float, nullable=True)
    # True once an MQTT message has been published for this Frigate event —
    # ensures at most one notification per person-appearance regardless of
    # how many recognition phases (new/update/end) run after it.
    notified = Column(Boolean, default=False)
    # Set by the Events-page review workflow: "confirmed" (snapshot accepted
    # as a new training image) or "rejected" (marked as a known false
    # positive, never used as training data). NULL until reviewed.
    verdict = Column(String(20), nullable=True)
    # How long our own recognition took to produce this event's result, and
    # (for comparison) Frigate's own face recognizer's current average
    # inference speed at that time — both in milliseconds. NULL if unknown
    # (e.g. Frigate's face recognition feature isn't enabled).
    recognition_duration_ms = Column(Float, nullable=True)
    frigate_recognition_duration_ms = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    person = relationship("Person", back_populates="events")
