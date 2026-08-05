import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.event import RecognitionEvent
from models.person import Person, TrainingImage
from routes.training import get_face_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recognition", tags=["recognition"])

SNAPSHOT_DIR = settings.data_dir / "snapshots"


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
            "person_id": e.person_id,
            "person_name": e.person_name,
            "confidence": e.confidence,
            "frigate_sub_label": e.frigate_sub_label,
            "frigate_sub_label_score": e.frigate_sub_label_score,
            "has_image": e.snapshot_path is not None,
            "verdict": e.verdict,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@router.get("/events/{event_id}/image")
def get_event_image(event_id: int, db: Session = Depends(get_db)):
    """
    Serve the actual image that was analyzed for a recognition event — lets
    the Events page show the user what the AI saw, for the confirm/reject
    review workflow.
    """
    event = db.query(RecognitionEvent).filter_by(id=event_id).first()
    if not event or not event.snapshot_path:
        raise HTTPException(status_code=404, detail="No image saved for this event")

    path = SNAPSHOT_DIR / event.snapshot_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot file no longer available")

    return FileResponse(path, media_type="image/jpeg")


class ConfirmEventRequest(BaseModel):
    person_id: Optional[int] = None


@router.post("/events/{event_id}/confirm")
def confirm_event(
    event_id: int,
    body: ConfirmEventRequest = ConfirmEventRequest(),
    db: Session = Depends(get_db),
):
    """
    "Train on this": the recognition (or the user's correction) was right —
    copy the event's snapshot into the person's training images. Does not
    auto-retrain, consistent with the existing manual "Train" button flow;
    the response flags needs_retrain so the UI can prompt for it.
    """
    event = db.query(RecognitionEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.snapshot_path:
        raise HTTPException(status_code=400, detail="No snapshot saved for this event")

    target_person_id = body.person_id or event.person_id
    if not target_person_id:
        raise HTTPException(
            status_code=400,
            detail="No person to confirm for — specify person_id",
        )

    person = db.query(Person).filter_by(id=target_person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    snapshot_file = SNAPSHOT_DIR / event.snapshot_path
    if not snapshot_file.is_file():
        raise HTTPException(status_code=404, detail="Snapshot file no longer available")

    content = snapshot_file.read_bytes()
    filename = f"{target_person_id}_{uuid.uuid4().hex}_event_confirm.jpg"
    filepath = settings.data_dir / "images" / filename
    with open(filepath, "wb") as f:
        f.write(content)

    engine = get_face_engine()
    quality_warning = engine.assess_quality(content)

    training_image = TrainingImage(
        person_id=target_person_id,
        filename=filename,
        face_detected=True,
        source="event_confirm",
        quality_warning=quality_warning,
    )
    db.add(training_image)

    event.verdict = "confirmed"
    event.person_id = target_person_id
    db.commit()
    db.refresh(training_image)

    logger.info(
        f"Confirmed event {event_id} for {person.name}, added training image {training_image.id}"
    )
    return {
        "event_id": event_id,
        "person_id": target_person_id,
        "training_image_id": training_image.id,
        "needs_retrain": True,
    }


@router.post("/events/{event_id}/reject")
def reject_event(event_id: int, db: Session = Depends(get_db)):
    """
    "Anti-train": the recognition was wrong. Marks the event as a known
    false positive so it's never mistaken for confirmed training data —
    deliberately does not create a training image, since there is nothing
    correct here to learn from.
    """
    event = db.query(RecognitionEvent).filter_by(id=event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.verdict = "rejected"
    db.commit()

    logger.info(f"Rejected event {event_id} ({event.person_name}) as a false positive")
    return {"event_id": event_id, "verdict": "rejected"}
