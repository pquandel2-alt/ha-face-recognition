import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.person import Person, Embedding
from services.face_engine import FaceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

# Global face engine instance
face_engine: FaceEngine | None = None


def get_face_engine() -> FaceEngine:
    global face_engine
    if face_engine is None:
        face_engine = FaceEngine()
    return face_engine


@router.post("/batch")
def train_batch(
    person_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Train/retrain multiple persons in one call. Without person_ids, trains
    every person that has at least one training image.

    Registered before /{person_id} so "batch" isn't swallowed as a
    person_id path segment (FastAPI matches routes in registration order).
    """
    query = db.query(Person)
    if person_ids:
        query = query.filter(Person.id.in_(person_ids))
    persons = [p for p in query.all() if p.training_images]

    if not persons:
        raise HTTPException(status_code=400, detail="No persons with training images to train")

    engine = get_face_engine()
    results = []
    for person in persons:
        try:
            success = engine.compute_person_embedding(person.id, db)
        except Exception as e:
            logger.error(f"Batch training error for {person.name}: {e}")
            success = False
        results.append(
            {
                "person_id": person.id,
                "person_name": person.name,
                "status": "trained" if success else "failed",
            }
        )

    trained_count = sum(1 for r in results if r["status"] == "trained")
    logger.info(f"Batch training: {trained_count}/{len(results)} persons trained")
    return {
        "trained": trained_count,
        "failed": len(results) - trained_count,
        "results": results,
    }


@router.post("/{person_id}")
def train_person(person_id: int, db: Session = Depends(get_db)):
    """
    Train/retrain a person: compute embedding from all training images.
    """
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if not person.training_images:
        raise HTTPException(status_code=400, detail="Person has no training images")

    try:
        engine = get_face_engine()
        success = engine.compute_person_embedding(person_id, db)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to compute embedding (no faces detected)",
            )

        logger.info(f"Trained person: {person.name}")
        return {
            "status": "trained",
            "person_id": person_id,
            "person_name": person.name,
            "message": f"Embedding computed from {len(person.training_images)} images",
        }
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def training_status(db: Session = Depends(get_db)):
    """Get training status for all persons."""
    persons = db.query(Person).all()
    status = []

    for person in persons:
        embedding = db.query(Embedding).filter_by(person_id=person.id).first()
        status.append(
            {
                "id": person.id,
                "name": person.name,
                "image_count": len(person.training_images),
                "has_embedding": bool(embedding),
                "faces_in_images": embedding.image_count if embedding else 0,
                "trained_at": embedding.created_at.isoformat() if embedding else None,
            }
        )

    return status


@router.get("/{person_id}/status")
def person_training_status(person_id: int, db: Session = Depends(get_db)):
    """Get training status for a specific person."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    embedding = db.query(Embedding).filter_by(person_id=person_id).first()

    return {
        "id": person.id,
        "name": person.name,
        "image_count": len(person.training_images),
        "has_embedding": bool(embedding),
        "faces_in_images": embedding.image_count if embedding else 0,
        "trained_at": embedding.created_at.isoformat() if embedding else None,
    }
