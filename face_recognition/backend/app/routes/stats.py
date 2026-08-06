import logging
from datetime import datetime, timedelta

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.cpu_sample import CpuSample
from models.event import RecognitionEvent
from models.person import Person

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])

STATS_DAYS = 14
CPU_SAMPLES_MAX = 200


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    """Aggregate recognition stats for the dashboard."""
    total_events = db.query(func.count(RecognitionEvent.id)).scalar() or 0
    avg_confidence = db.query(func.avg(RecognitionEvent.confidence)).scalar() or 0.0

    by_person = (
        db.query(RecognitionEvent.person_name, func.count(RecognitionEvent.id))
        .group_by(RecognitionEvent.person_name)
        .order_by(func.count(RecognitionEvent.id).desc())
        .all()
    )

    by_camera = (
        db.query(RecognitionEvent.camera, func.count(RecognitionEvent.id))
        .group_by(RecognitionEvent.camera)
        .order_by(func.count(RecognitionEvent.id).desc())
        .all()
    )

    since = datetime.utcnow() - timedelta(days=STATS_DAYS - 1)
    by_day_rows = (
        db.query(func.date(RecognitionEvent.timestamp), func.count(RecognitionEvent.id))
        .filter(RecognitionEvent.timestamp >= since)
        .group_by(func.date(RecognitionEvent.timestamp))
        .all()
    )
    counts_by_day = {day: count for day, count in by_day_rows}
    # Fill in zero-count gaps so the frontend renders a continuous bar chart.
    by_day = [
        {
            "date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"),
            "count": counts_by_day.get(
                (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"), 0
            ),
        }
        for i in range(STATS_DAYS - 1, -1, -1)
    ]

    persons_total = db.query(func.count(Person.id)).scalar() or 0
    persons_trained = db.query(func.count(func.distinct(Person.id))).join(Person.embeddings).scalar() or 0

    cpu_rows = (
        db.query(CpuSample)
        .order_by(CpuSample.timestamp.desc())
        .limit(CPU_SAMPLES_MAX)
        .all()
    )
    cpu_usage = [
        {"timestamp": sample.timestamp.isoformat(), "cpu_percent": sample.cpu_percent}
        for sample in reversed(cpu_rows)
    ]

    return {
        "total_events": total_events,
        "avg_confidence": float(avg_confidence),
        "persons_total": persons_total,
        "persons_trained": persons_trained,
        "by_person": [{"person_name": name or "unknown", "count": count} for name, count in by_person],
        "by_camera": [{"camera": camera, "count": count} for camera, count in by_camera],
        "by_day": by_day,
        "cpu_usage": cpu_usage,
        "cpu_count": psutil.cpu_count() or 1,
    }
