import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.person import Person, TrainingImage
from services.frigate_service import FrigateService
from routes.training import get_face_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/frigate", tags=["frigate"])

# Global Frigate service instance
frigate_service: FrigateService | None = None


def get_frigate_service() -> FrigateService:
    global frigate_service
    if frigate_service is None:
        frigate_service = FrigateService()
    return frigate_service


@router.get("/health")
def frigate_health(frigate: FrigateService = Depends(get_frigate_service)):
    """Check if Frigate API is reachable."""
    healthy = frigate.health_check()
    return {
        "healthy": healthy,
        "url": settings.frigate_api_url,
    }


@router.get("/snapshots")
def list_snapshots(
    limit: int = 50,
    db: Session = Depends(get_db),
    frigate: FrigateService = Depends(get_frigate_service),
):
    """
    Get list of recent person detection events from Frigate.

    Excludes events already imported as a training image in a previous run
    (tracked via TrainingImage.frigate_event_id), so a repeat import only
    ever offers genuinely new events.
    """
    events = frigate.get_recent_events(label="person", limit=limit)

    if not events:
        return {"events": [], "count": 0}

    already_imported = {
        row[0]
        for row in db.query(TrainingImage.frigate_event_id).filter(
            TrainingImage.frigate_event_id.isnot(None)
        )
    }
    events = [e for e in events if e.get("id") not in already_imported]

    return {
        "events": [
            {
                "id": e.get("id"),
                "camera": e.get("camera"),
                "start": e.get("start_time"),
                "end": e.get("end_time"),
                "label": e.get("label"),
            }
            for e in events
        ],
        "count": len(events),
    }


@router.get("/snapshots/clusters")
def cluster_snapshots(
    limit: int = 50,
    db: Session = Depends(get_db),
    frigate: FrigateService = Depends(get_frigate_service),
):
    """
    Group recent person-event snapshots by face similarity, computed
    on the fly (nothing is persisted) so the import UI can offer bulk
    selection of visually similar events instead of a flat picklist.
    Frigate already retains these snapshots regardless of this add-on, so
    this doesn't introduce any new storage of biometric data.
    """
    events = frigate.get_recent_events(label="person", limit=limit)
    if not events:
        return {"clusters": [], "unclustered": []}

    already_imported = {
        row[0]
        for row in db.query(TrainingImage.frigate_event_id).filter(
            TrainingImage.frigate_event_id.isnot(None)
        )
    }
    events = [e for e in events if e.get("id") not in already_imported]

    engine = get_face_engine()
    centroids: list = []
    groups: list = []
    unclustered = []

    for e in events:
        event_id = e.get("id")
        summary = {
            "id": event_id,
            "camera": e.get("camera"),
            "start": e.get("start_time"),
            "end": e.get("end_time"),
            "label": e.get("label"),
        }

        snapshot_bytes = frigate.get_snapshot(event_id, crop=True)
        embeddings = engine.detect_and_embed_bytes(snapshot_bytes) if snapshot_bytes else []
        if not embeddings:
            unclustered.append(summary)
            continue

        embedding = embeddings[0]
        best_idx, best_sim = None, 0.0
        for idx, centroid in enumerate(centroids):
            sim = engine.similarity(embedding, centroid)
            if sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx is not None and best_sim >= settings.cluster_similarity_threshold:
            groups[best_idx].append(summary)
            n = len(groups[best_idx])
            centroids[best_idx] = (centroids[best_idx] * (n - 1) + embedding) / n
        else:
            centroids.append(embedding)
            groups.append([summary])

    clusters = []
    for group in groups:
        if len(group) > 1:
            clusters.append({"cluster_id": len(clusters), "count": len(group), "events": group})
        else:
            unclustered.extend(group)

    clusters.sort(key=lambda c: c["count"], reverse=True)

    return {"clusters": clusters, "unclustered": unclustered}


@router.get("/thumbnail/{event_id}")
def get_thumbnail(
    event_id: str,
    frigate: FrigateService = Depends(get_frigate_service),
):
    """Proxy a Frigate event thumbnail (Frigate's REST port isn't reachable from the browser)."""
    image_bytes = frigate.get_thumbnail(event_id)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return Response(content=image_bytes, media_type="image/jpeg")


@router.get("/snapshot/{event_id}")
def get_snapshot(
    event_id: str,
    frigate: FrigateService = Depends(get_frigate_service),
):
    """Proxy a Frigate event snapshot (Frigate's REST port isn't reachable from the browser)."""
    image_bytes = frigate.get_snapshot(event_id)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return Response(content=image_bytes, media_type="image/jpeg")


@router.get("/faces")
def list_trained_faces(
    db: Session = Depends(get_db),
    frigate: FrigateService = Depends(get_frigate_service),
):
    """
    List Frigate's own trained face images (from Frigate's built-in Face
    Recognition feature), grouped by person name.

    Excludes filenames already imported as training images in a previous
    run (tracked via TrainingImage.frigate_source_filename), so a repeat
    import only ever offers genuinely new images.
    """
    faces = frigate.get_trained_faces()
    already_imported = {
        row[0]
        for row in db.query(TrainingImage.frigate_source_filename).filter(
            TrainingImage.frigate_source_filename.isnot(None)
        )
    }

    new_faces = {}
    for name, files in faces.items():
        remaining = [f for f in files if f"{name}/{f}" not in already_imported]
        if remaining:
            new_faces[name] = remaining

    return {
        "faces": new_faces,
        "names": list(new_faces.keys()),
    }


def _safe_face_path_part(value: str) -> str:
    if not value or "/" in value or ".." in value:
        raise HTTPException(status_code=400, detail="Invalid path segment")
    return value


@router.get("/faces/{name}/{filename}")
def get_face_image(
    name: str,
    filename: str,
    frigate: FrigateService = Depends(get_frigate_service),
):
    """Proxy one of Frigate's trained face images."""
    name = _safe_face_path_part(name)
    filename = _safe_face_path_part(filename)
    image_bytes = frigate.get_face_image(name, filename)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="Face image not found")
    return Response(content=image_bytes, media_type="image/webp")


class FaceImportRequest(BaseModel):
    name: str
    filenames: list[str]
    person_id: int


@router.post("/faces/import")
def import_trained_faces(
    body: FaceImportRequest,
    db: Session = Depends(get_db),
    frigate: FrigateService = Depends(get_frigate_service),
):
    """
    Import a batch of Frigate's own trained face images (already classified by
    Frigate's Face Recognition feature) as training images for a person.
    """
    person = db.query(Person).filter_by(id=body.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    name = _safe_face_path_part(body.name)

    engine = get_face_engine()
    imported = []
    skipped = []

    for filename in body.filenames:
        filename = _safe_face_path_part(filename)
        source_key = f"{name}/{filename}"
        try:
            if db.query(TrainingImage).filter_by(frigate_source_filename=source_key).first():
                # Already imported in a previous run — the gallery should have
                # excluded it already, but guard against stale frontend state.
                skipped.append(filename)
                continue

            image_bytes = frigate.get_face_image(name, filename)
            if not image_bytes:
                skipped.append(filename)
                continue

            local_filename = f"{body.person_id}_{uuid.uuid4().hex}_frigate_face_{filename}"
            filepath = settings.data_dir / "images" / local_filename

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            embeddings = engine.detect_and_embed_bytes(image_bytes)
            quality_warning = engine.assess_quality(image_bytes)

            training_image = TrainingImage(
                person_id=body.person_id,
                filename=local_filename,
                face_detected=bool(embeddings),
                source="frigate_import",
                frigate_source_filename=source_key,
                quality_warning=quality_warning,
            )
            db.add(training_image)
            db.commit()
            db.refresh(training_image)
            imported.append(training_image.id)
        except Exception as e:
            logger.error(f"Error importing Frigate face image {name}/{filename}: {e}")
            skipped.append(filename)

    logger.info(
        f"Imported {len(imported)} Frigate face images for {person.name} "
        f"({len(skipped)} skipped)"
    )

    return {
        "person_id": body.person_id,
        "imported": len(imported),
        "skipped": skipped,
        "training_image_ids": imported,
    }


@router.post("/import/{event_id}")
def import_snapshot_as_training_image(
    event_id: str,
    person_id: int = None,
    db: Session = Depends(get_db),
    frigate: FrigateService = Depends(get_frigate_service),
):
    """
    Import a Frigate snapshot as a training image for a person.
    Automatically detects face and crops it.

    Body: {"person_id": 1} or query param ?person_id=1
    """
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id required")

    person = db.query(Person).filter_by(id=person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing = db.query(TrainingImage).filter_by(frigate_event_id=event_id).first()
    if existing:
        # Already imported in a previous run — the gallery should have
        # excluded it already, but guard against stale frontend state.
        raise HTTPException(status_code=409, detail="Event already imported")

    try:
        # Get snapshot from Frigate
        snapshot_bytes = frigate.get_snapshot(event_id)
        if not snapshot_bytes:
            raise HTTPException(status_code=404, detail="Snapshot not found in Frigate")

        # Save snapshot to filesystem
        filename = f"{person_id}_{uuid.uuid4().hex}_frigate_{event_id}.jpg"
        filepath = settings.data_dir / "images" / filename

        with open(filepath, "wb") as f:
            f.write(snapshot_bytes)

        # Detect face and verify it exists
        engine = get_face_engine()
        embeddings = engine.detect_and_embed_bytes(snapshot_bytes)
        quality_warning = engine.assess_quality(snapshot_bytes)

        # Create training image record
        training_image = TrainingImage(
            person_id=person_id,
            filename=filename,
            face_detected=bool(embeddings),
            source="frigate_import",
            frigate_event_id=event_id,
            quality_warning=quality_warning,
        )
        db.add(training_image)
        db.commit()
        db.refresh(training_image)

        logger.info(
            f"Imported Frigate snapshot for {person.name}: {filename} "
            f"({len(embeddings)} faces)"
        )

        return {
            "id": training_image.id,
            "person_id": person_id,
            "filename": filename,
            "source": "frigate_import",
            "face_detected": bool(embeddings),
            "faces_count": len(embeddings),
            "quality_warning": quality_warning,
            "created_at": training_image.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing Frigate snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))
