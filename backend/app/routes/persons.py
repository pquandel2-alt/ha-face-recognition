import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.person import Person, TrainingImage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/")
def list_persons(db: Session = Depends(get_db)):
    """List all persons."""
    persons = db.query(Person).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "active": p.active,
            "image_count": len(p.training_images),
            "has_embedding": bool(p.embeddings),
            "created_at": p.created_at.isoformat(),
        }
        for p in persons
    ]


@router.post("/")
def create_person(name: str, db: Session = Depends(get_db)):
    """Create new person."""
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")

    existing = db.query(Person).filter_by(name=name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Person already exists")

    person = Person(name=name)
    db.add(person)
    db.commit()
    db.refresh(person)

    logger.info(f"Created person: {name}")
    return {
        "id": person.id,
        "name": person.name,
        "active": person.active,
        "created_at": person.created_at.isoformat(),
    }


@router.get("/{person_id}")
def get_person(person_id: int, db: Session = Depends(get_db)):
    """Get person details."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return {
        "id": person.id,
        "name": person.name,
        "active": person.active,
        "image_count": len(person.training_images),
        "has_embedding": bool(person.embeddings),
        "created_at": person.created_at.isoformat(),
    }


@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete person and all training images."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Delete images from filesystem
    for training_image in person.training_images:
        image_path = settings.data_dir / "images" / training_image.filename
        if image_path.exists():
            image_path.unlink()

    db.delete(person)
    db.commit()

    logger.info(f"Deleted person: {person.name}")
    return {"status": "deleted", "name": person.name}


@router.post("/{person_id}/images")
async def upload_training_image(
    person_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload training image for a person."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Generate unique filename
        filename = f"{person_id}_{uuid.uuid4().hex}_{file.filename}"
        filepath = settings.data_dir / "images" / filename

        # Save file
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        # Create training image record
        training_image = TrainingImage(
            person_id=person_id,
            filename=filename,
            source="upload",
        )
        db.add(training_image)
        db.commit()
        db.refresh(training_image)

        logger.info(f"Uploaded training image for {person.name}: {filename}")
        return {
            "id": training_image.id,
            "person_id": person_id,
            "filename": filename,
            "source": "upload",
            "created_at": training_image.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error uploading training image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{person_id}/images")
def list_training_images(person_id: int, db: Session = Depends(get_db)):
    """List all training images for a person."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    images = db.query(TrainingImage).filter_by(person_id=person_id).all()
    return [
        {
            "id": img.id,
            "filename": img.filename,
            "face_detected": img.face_detected,
            "has_embedding": img.has_embedding,
            "source": img.source,
            "created_at": img.created_at.isoformat(),
        }
        for img in images
    ]


@router.delete("/{person_id}/images/{image_id}")
def delete_training_image(person_id: int, image_id: int, db: Session = Depends(get_db)):
    """Delete a training image."""
    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    training_image = db.query(TrainingImage).filter_by(id=image_id, person_id=person_id).first()
    if not training_image:
        raise HTTPException(status_code=404, detail="Training image not found")

    # Delete from filesystem
    image_path = settings.data_dir / "images" / training_image.filename
    if image_path.exists():
        image_path.unlink()

    db.delete(training_image)
    db.commit()

    logger.info(f"Deleted training image: {training_image.filename}")
    return {"status": "deleted"}
