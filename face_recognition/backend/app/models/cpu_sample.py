from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer

from database import Base


class CpuSample(Base):
    __tablename__ = "cpu_samples"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_percent = Column(Float, nullable=False)
