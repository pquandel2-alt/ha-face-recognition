import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models.event import RecognitionEvent
from routes.training import get_face_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    camera: str = "manual",
    db: Session = Depends(get_db),
):
    """
    Upload an image and recognize faces.
    Returns list of detected faces with names and confidence scores.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        engine = get_face_engine()
        content = await file.read()

        # Analyze image
        result = engine.analyze_image(content, db)

        # Save event(s) to database
        timestamp = datetime.utcnow()
        for recognition in result["results"]:
            event = RecognitionEvent(
                camera=camera,
                person_name=recognition["name"],
                confidence=recognition["confidence"],
                timestamp=timestamp,
            )
            db.add(event)

        db.commit()

        logger.info(f"Analyzed image from {camera}: {result['faces_detected']} faces")
        return {
            "faces_detected": result["faces_detected"],
            "results": result["results"],
            "timestamp": timestamp.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error analyzing image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
def get_recent_events(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent recognition events."""
    events = (
        db.query(RecognitionEvent)
        .order_by(RecognitionEvent.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": e.id,
            "camera": e.camera,
            "person_name": e.person_name,
            "confidence": e.confidence,
            "frigate_sub_label": e.frigate_sub_label,
            "frigate_sub_label_score": e.frigate_sub_label_score,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]
