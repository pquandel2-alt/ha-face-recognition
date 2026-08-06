import asyncio
import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import init_db, get_db, SessionLocal
from models.cpu_sample import CpuSample
from models.event import RecognitionEvent
from models.person import Person
from routes import persons, training, recognition, frigate, stats, settings as settings_routes
from services.mqtt_service import MQTTService
from services.frigate_service import FrigateService
from services.ha_discovery import get_discovery_configs

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Face Recognition Service",
    description="Local face recognition for Home Assistant",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routes
app.include_router(persons.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(recognition.router, prefix="/api")
app.include_router(frigate.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(settings_routes.router, prefix="/api")


# Global MQTT service
mqtt_service: MQTTService | None = None
active_websockets: list[WebSocket] = []
main_loop: asyncio.AbstractEventLoop | None = None

# Throttle state for on_frigate_event_update: last time we hit the Frigate
# API for each in-progress event_id. Only ever touched from the MQTT
# client's single background thread (paho-mqtt's loop_forever), so no lock
# is needed — consistent with the rest of this module.
_last_update_check: dict[str, datetime] = {}

SNAPSHOT_DIR = settings.data_dir / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def schedule_broadcast(data: dict) -> None:
    """
    Schedule a WebSocket broadcast from any thread.

    on_frigate_event/on_frigate_event_end run synchronously on the MQTT
    client's background thread (paho-mqtt's loop_forever), which has no
    asyncio event loop of its own — asyncio.create_task() would raise
    "no running event loop" there. run_coroutine_threadsafe schedules the
    coroutine onto the loop captured at startup instead, which works from
    any thread.
    """
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(broadcast_event(data), main_loop)


def _resolve_person_id(person_name: str | None, db: Session) -> int | None:
    """Look up the Person row behind a recognition's name, for the Events
    review workflow. None for "unknown"/"uncertain"/no match."""
    if not person_name or person_name in ("unknown", "uncertain"):
        return None
    person = db.query(Person).filter_by(name=person_name).first()
    return person.id if person else None


def _save_event_snapshot(event_id: str, image_bytes: bytes | None) -> str | None:
    """
    Persist the image actually used for a recognition attempt so the Events
    page can show it for review (confirm/reject). Returns the filename
    (relative to SNAPSHOT_DIR) to store on RecognitionEvent.snapshot_path, or
    None on failure. Safe to call repeatedly for the same event_id — later
    calls (update/end) overwrite the file with a better crop.
    """
    if not event_id or not image_bytes:
        return None
    try:
        filename = f"{event_id}.jpg"
        with open(SNAPSHOT_DIR / filename, "wb") as f:
            f.write(image_bytes)
        return filename
    except Exception as e:
        logger.warning(f"Could not save snapshot for event {event_id}: {e}")
        return None


def _analyze_crops_for_consensus(
    crops: list[bytes],
) -> tuple[str | None, float, float, bytes | None, float]:
    """
    Analyze all of Frigate's face-detector crops for an in-progress or
    finished event and require multiple crops to agree on the same person
    before trusting the result — a single outlier crop should not be enough
    to publish a recognition.

    Returns (person_name, confidence, margin, representative_crop_bytes,
    duration_ms) — duration_ms is the total wall-clock time to analyze all
    crops and reach a verdict (crops run in parallel, so this is the actual
    end-to-end recognition latency for update/end events, not a per-crop sum).
    person_name is None if no trustworthy consensus was reached yet.
    """
    start = time.monotonic()
    if not crops:
        return None, 0.0, 0.0, None, 0.0

    from routes.training import get_face_engine

    engine = get_face_engine()

    def analyze_one(crop_bytes: bytes) -> list[tuple[str, float, float, bytes]]:
        # Each worker gets its own short-lived session — SQLAlchemy
        # sessions aren't safe to share across concurrently running threads.
        crop_db = SessionLocal()
        try:
            result = engine.analyze_image(crop_bytes, crop_db)
        finally:
            crop_db.close()
        return [
            (
                face_result["name"],
                face_result["confidence"],
                face_result.get("margin", 0.0),
                crop_bytes,
            )
            for face_result in result["results"]
        ]

    # Analyze crops concurrently — this runs on every throttled "update"
    # poll while a person is still in frame, so keeping it fast matters for
    # real-time recognition. InsightFace inference is CPU-bound but releases
    # the GIL during the heavy numpy/onnxruntime work, so this can run truly
    # in parallel on multi-core hosts (harmless, just less of a win on
    # single-core hardware).
    with ThreadPoolExecutor(max_workers=min(len(crops), 4)) as executor:
        per_crop_lists = list(executor.map(analyze_one, crops))
    per_crop = [item for sublist in per_crop_lists for item in sublist]

    duration_ms = (time.monotonic() - start) * 1000

    if not per_crop:
        return None, 0.0, 0.0, None, duration_ms

    confident = [p for p in per_crop if p[0] not in ("unknown", "uncertain")]
    if len(confident) >= settings.consensus_min_crops:
        votes = Counter(p[0] for p in confident)
        winner, _ = votes.most_common(1)[0]
        agreeing = [p for p in confident if p[0] == winner]
        best = max(agreeing, key=lambda p: p[1])
        return (*best, duration_ms)

    # Not enough crops agree yet (e.g. only one crop available so far, or a
    # very brief appearance that will never produce more). Only trust a
    # single crop if it clears a stricter margin than the normal threshold.
    best_single = max(per_crop, key=lambda p: p[1])
    if best_single[0] not in ("unknown", "uncertain") and best_single[2] >= settings.consensus_fallback_margin_min:
        return (*best_single, duration_ms)

    return None, best_single[1], 0.0, best_single[3], duration_ms


def publish_ha_discovery_configs():
    """Publish all HA Discovery configs. Called on every successful MQTT (re-)connect."""
    for entity_id, config in get_discovery_configs().items():
        mqtt_service.publish_ha_discovery(entity_id, entity_id, config)
    logger.info("Published Home Assistant MQTT Discovery configs")


def _init_mqtt_service() -> MQTTService:
    """Build and connect a fresh MQTTService with the standard callbacks
    registered — shared by startup() and reinitialize_mqtt() (Settings page
    broker changes) so both stay in sync."""
    service = MQTTService()
    service.set_frigate_callback(on_frigate_event)
    # Publishes HA Discovery configs on every successful (re-)connect, not
    # just the first — connect() is async/non-blocking with automatic
    # reconnect, so we can't assume the connection is up right away.
    service.set_on_connect_callback(publish_ha_discovery_configs)
    try:
        service.connect()
    except Exception as e:
        logger.error(f"Failed to initialize MQTT: {e}")
    return service


def reinitialize_mqtt():
    """
    Rebuild the MQTT connection after the Settings page changes broker
    host/port/credentials — cleanly disconnects the old client (so the
    Last-Will "offline" doesn't fire) and reconnects with the new settings,
    without needing a process restart.
    """
    global mqtt_service
    if mqtt_service:
        try:
            mqtt_service.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting previous MQTT client: {e}")
    mqtt_service = _init_mqtt_service()
    logger.info("MQTT service reinitialized with updated settings")


@app.on_event("startup")
async def startup():
    """Initialize database, start MQTT service, and setup HA Discovery."""
    global mqtt_service, main_loop

    logger.info("Starting Face Recognition Service...")
    main_loop = asyncio.get_running_loop()

    # Initialize database
    init_db()

    mqtt_service = _init_mqtt_service()

    asyncio.create_task(_snapshot_retention_loop())


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global mqtt_service

    if mqtt_service:
        mqtt_service.disconnect()
    logger.info("Face Recognition Service stopped")


def on_frigate_event(payload: dict):
    """Callback for Frigate MQTT events."""
    try:
        event_type = payload.get("type")
        after = payload.get("after", {})
        label = after.get("label")
        camera = after.get("camera", "unknown")
        event_id = after.get("id")

        if label != "person":
            return

        # Frigate's own recognition verdict (sub_label) isn't ready at "new" —
        # it only finalizes once the tracked object's lifecycle ends.
        if event_type == "end":
            on_frigate_event_end(event_id)
            return

        # "update" events fire frequently while a track is still active —
        # used to catch a confident result as soon as Frigate's face-detector
        # crops become available, without waiting for the track to end.
        if event_type == "update":
            on_frigate_event_update(event_id, camera)
            return

        if event_type != "new":
            return

        if not event_id or not camera:
            logger.warning(f"Incomplete Frigate event: {payload}")
            return

        logger.debug(f"Processing Frigate event: {camera}/{event_id}")

        # Get snapshot and analyze
        frigate = FrigateService()
        snapshot_bytes = frigate.get_snapshot(event_id, crop=True)
        if not snapshot_bytes:
            logger.warning(f"Could not get snapshot for event {event_id}")
            return

        # Analyze with face engine
        db = SessionLocal()
        try:
            from routes.training import get_face_engine

            engine = get_face_engine()
            result = engine.analyze_image(snapshot_bytes, db)

            if not result["results"]:
                logger.warning(f"No faces detected in event {event_id}")
                return

            # Take best match
            best_result = max(result["results"], key=lambda x: x["confidence"])
            person_name = best_result["name"]
            confidence = best_result["confidence"]

            # Only publish when the whole-person crop already gives a
            # confident match — an "unknown"/"uncertain" guess here would be
            # a premature, unreliable notification. If it isn't confident
            # yet, on_frigate_event_update / on_frigate_event_end still get
            # a chance to notify once a better result is available.
            is_confident = person_name not in ("unknown", "uncertain")

            # Save event
            timestamp = datetime.utcnow()
            event = RecognitionEvent(
                camera=camera,
                person_name=person_name,
                person_id=_resolve_person_id(person_name, db),
                confidence=confidence,
                frigate_event_id=event_id,
                snapshot_path=_save_event_snapshot(event_id, snapshot_bytes),
                notified=is_confident,
                timestamp=timestamp,
                recognition_duration_ms=result.get("duration_ms"),
                frigate_recognition_duration_ms=frigate.get_face_recognition_speed_ms(),
            )
            db.add(event)
            db.commit()
            logger.debug(f"Saved recognition event: {person_name} on {camera}")

            # Publish via MQTT — at most once per Frigate event, so a later
            # phase (update/end) never double-fires a downstream automation.
            if is_confident:
                if mqtt_service and mqtt_service.connected:
                    mqtt_service.publish_recognition(person_name, confidence, camera, timestamp.isoformat())
                    logger.debug(f"Published MQTT event: {person_name}")
                else:
                    logger.warning("MQTT not connected, event not published")

            # Notify WebSocket clients
            schedule_broadcast(
                {
                    "type": "recognition",
                    "person_name": person_name,
                    "confidence": confidence,
                    "camera": camera,
                    "timestamp": timestamp.isoformat(),
                }
            )

            logger.info(f"Frigate recognition: {person_name} ({confidence:.2f}) on {camera}")
        except Exception as e:
            logger.error(f"Error analyzing Frigate event {event_id}: {e}", exc_info=True)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in on_frigate_event: {e}", exc_info=True)


def on_frigate_event_update(event_id: str | None, camera: str):
    """
    Frigate emits frequent "update" events while a track is still active,
    and progressively populates the /api/faces "train" bucket with
    dedicated face-detector crops during that same window — not only once
    the track ends. Poll for those crops here (throttled per event_id),
    requiring multiple crops to agree (see _analyze_crops_for_consensus)
    before trusting the result, so a confident, reliable result can be
    published within a second or two of the person appearing, instead of
    only at "end" when they leave the frame. No-ops once the event has
    already been notified.
    """
    if not event_id:
        return

    now = datetime.utcnow()
    last_check = _last_update_check.get(event_id)
    if last_check and (now - last_check).total_seconds() < settings.frigate_update_check_interval_seconds:
        return
    _last_update_check[event_id] = now

    db = SessionLocal()
    try:
        event = (
            db.query(RecognitionEvent)
            .filter(RecognitionEvent.frigate_event_id == event_id)
            .first()
        )
        if event is not None and event.notified:
            return  # Already published for this event — nothing left to do faster.

        frigate = FrigateService()
        crops = frigate.get_train_face_crops(event_id)
        if not crops:
            return  # Frigate hasn't produced a face crop for this event yet.

        winner_name, winner_confidence, _margin, rep_crop, duration_ms = _analyze_crops_for_consensus(crops)

        if winner_name is None:
            return  # Not confident/agreed yet — try again on the next throttled update.

        snapshot_path = _save_event_snapshot(event_id, rep_crop)
        person_id = _resolve_person_id(winner_name, db)

        if event is None:
            event = RecognitionEvent(
                camera=camera,
                person_name=winner_name,
                person_id=person_id,
                confidence=winner_confidence,
                frigate_event_id=event_id,
                snapshot_path=snapshot_path,
                timestamp=now,
                recognition_duration_ms=duration_ms,
                frigate_recognition_duration_ms=frigate.get_face_recognition_speed_ms(),
            )
            db.add(event)
        else:
            event.person_name = winner_name
            event.person_id = person_id
            event.confidence = winner_confidence
            event.recognition_duration_ms = duration_ms
            if snapshot_path:
                event.snapshot_path = snapshot_path

        event.notified = True
        db.commit()

        logger.info(
            f"Real-time recognition via Frigate face crop consensus (update event) for "
            f"{event_id}: {event.person_name} ({event.confidence:.2f})"
        )

        if mqtt_service and mqtt_service.connected:
            mqtt_service.publish_recognition(
                event.person_name, event.confidence, event.camera, event.timestamp.isoformat()
            )

        schedule_broadcast(
            {
                "type": "recognition",
                "person_name": event.person_name,
                "confidence": event.confidence,
                "camera": event.camera,
                "timestamp": event.timestamp.isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error processing Frigate event update for {event_id}: {e}", exc_info=True)
    finally:
        db.close()


def on_frigate_event_end(event_id: str | None):
    """
    Fetch Frigate's own finalized recognition verdict (sub_label) for an
    event, and re-run our own consensus matching against Frigate's dedicated
    face-detector crops (the /api/faces "train" bucket) instead of the
    coarse whole-person snapshot used at "new" time. Those crops are
    tightly framed on the actual face the way our training images are,
    while the "new"-time snapshot is a whole-body crop where the face is
    small and often produces near-random similarity scores. Whichever
    result is saved here is what gets published to MQTT/HA, since it's
    the best information we'll ever have for this event.
    """
    if not event_id:
        return

    db = SessionLocal()
    try:
        frigate = FrigateService()
        frigate_event = frigate.get_event(event_id) or {}
        sub_label = frigate_event.get("sub_label")
        sub_label_score = (frigate_event.get("data") or {}).get("sub_label_score")

        event = (
            db.query(RecognitionEvent)
            .filter(RecognitionEvent.frigate_event_id == event_id)
            .first()
        )
        already_notified = bool(event and event.notified)

        crops = frigate.get_train_face_crops(event_id)
        best_name, best_confidence, snapshot_path, duration_ms = None, -1.0, None, None
        if crops:
            best_name, best_confidence, _margin, rep_crop, duration_ms = _analyze_crops_for_consensus(crops)
            if best_name is not None:
                snapshot_path = _save_event_snapshot(event_id, rep_crop)
            else:
                best_confidence = -1.0

        refined = False
        if event is None:
            if best_name is None:
                # Nothing was ever saved for this event (e.g. no snapshot at
                # "new") and Frigate has no face crops for it either.
                return
            event = RecognitionEvent(
                camera=frigate_event.get("camera", "unknown"),
                person_name=best_name,
                person_id=_resolve_person_id(best_name, db),
                confidence=best_confidence,
                frigate_event_id=event_id,
                snapshot_path=snapshot_path,
                timestamp=datetime.utcnow(),
                recognition_duration_ms=duration_ms,
            )
            db.add(event)
            refined = True
        elif best_name is not None and best_confidence > event.confidence:
            event.person_name = best_name
            event.person_id = _resolve_person_id(best_name, db)
            event.confidence = best_confidence
            event.recognition_duration_ms = duration_ms
            if snapshot_path:
                event.snapshot_path = snapshot_path
            refined = True

        if sub_label is not None:
            event.frigate_sub_label = sub_label
            event.frigate_sub_label_score = sub_label_score

        # Frigate's own face recognizer's current average speed, refreshed
        # here since "end" is when its verdict has actually finalized.
        event.frigate_recognition_duration_ms = frigate.get_face_recognition_speed_ms()

        # At most one MQTT publish per Frigate event: if "new" or "update"
        # already notified, only the DB record (history/accuracy) is
        # updated here — never a second, correcting notification.
        should_publish = refined and not already_notified
        if should_publish:
            event.notified = True

        db.commit()
        logger.debug(f"Processed Frigate event end for {event_id}")

        if refined:
            logger.info(
                f"Refined recognition for event {event_id} using Frigate face crop consensus: "
                f"{event.person_name} ({event.confidence:.2f})"
            )
            if should_publish:
                if mqtt_service and mqtt_service.connected:
                    mqtt_service.publish_recognition(
                        event.person_name, event.confidence, event.camera, event.timestamp.isoformat()
                    )
            else:
                logger.debug(
                    f"Suppressed republish for event {event_id} — already notified earlier."
                )

        _last_update_check.pop(event_id, None)

        schedule_broadcast(
            {
                "type": "frigate_comparison",
                "frigate_event_id": event_id,
                "person_name": event.person_name,
                "confidence": event.confidence,
                "frigate_sub_label": event.frigate_sub_label,
                "frigate_sub_label_score": event.frigate_sub_label_score,
            }
        )
    except Exception as e:
        logger.error(f"Error processing Frigate event end for {event_id}: {e}", exc_info=True)
    finally:
        db.close()


def _cleanup_old_snapshots():
    """Delete persisted event snapshots older than frigate_snapshot_retention_hours,
    bounding disk growth from the Events-page review workflow."""
    cutoff = datetime.utcnow().timestamp() - settings.frigate_snapshot_retention_hours * 3600
    removed = 0
    for path in SNAPSHOT_DIR.glob("*.jpg"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as e:
            logger.warning(f"Could not remove old snapshot {path}: {e}")
    if removed:
        logger.info(f"Snapshot retention sweep: removed {removed} snapshot(s)")


def _cleanup_old_events():
    """Delete RecognitionEvent rows older than event_retention_days, bounding
    database growth — confirmed events already have their training data
    copied into a separate TrainingImage row (see confirm_event), so
    deleting the event row itself loses nothing needed for training."""
    cutoff = datetime.utcnow() - timedelta(days=settings.event_retention_days)
    db = SessionLocal()
    try:
        old_events = db.query(RecognitionEvent).filter(RecognitionEvent.timestamp < cutoff).all()
        if not old_events:
            return
        for event in old_events:
            if event.snapshot_path:
                try:
                    (SNAPSHOT_DIR / event.snapshot_path).unlink(missing_ok=True)
                except OSError as e:
                    logger.warning(f"Could not remove snapshot for expired event {event.id}: {e}")
            db.delete(event)
        db.commit()
        logger.info(f"Event retention sweep: removed {len(old_events)} event(s)")
    finally:
        db.close()


CPU_SAMPLE_RETENTION_DAYS = 7


def _cleanup_old_cpu_samples():
    """Delete CpuSample rows older than CPU_SAMPLE_RETENTION_DAYS, bounding
    database growth from the per-recognition CPU sampling used by the Stats
    page chart."""
    cutoff = datetime.utcnow() - timedelta(days=CPU_SAMPLE_RETENTION_DAYS)
    db = SessionLocal()
    try:
        removed = db.query(CpuSample).filter(CpuSample.timestamp < cutoff).delete()
        db.commit()
        if removed:
            logger.info(f"CPU sample retention sweep: removed {removed} sample(s)")
    finally:
        db.close()


async def _snapshot_retention_loop():
    """Background task: periodically sweep old event snapshots, expired
    RecognitionEvent rows, and expired CpuSample rows."""
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(None, _cleanup_old_snapshots)
            await asyncio.get_running_loop().run_in_executor(None, _cleanup_old_events)
            await asyncio.get_running_loop().run_in_executor(None, _cleanup_old_cpu_samples)
        except Exception as e:
            logger.error(f"Retention sweep failed: {e}", exc_info=True)
        await asyncio.sleep(3600)


async def broadcast_event(data: dict):
    """Broadcast event to all connected WebSocket clients."""
    disconnected = []
    for websocket in active_websockets:
        try:
            await websocket.send_json(data)
        except Exception:
            disconnected.append(websocket)

    # Remove disconnected clients
    for ws in disconnected:
        active_websockets.remove(ws)


@app.websocket("/api/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket endpoint for live events."""
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info("WebSocket client connected")

    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info("WebSocket client disconnected")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "mqtt_connected": mqtt_service.connected if mqtt_service else False,
    }


FRONTEND_DIR = Path(__file__).parent / "static"

if FRONTEND_DIR.is_dir():

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the bundled React SPA, with client-side routing fallback."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = FRONTEND_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")

else:
    logger.warning(
        "No built frontend found at %s — running API-only.", FRONTEND_DIR
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )
