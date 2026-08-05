import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from database import init_db, get_db, SessionLocal
from models.event import RecognitionEvent
from routes import persons, training, recognition, frigate, stats
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


# Global MQTT service
mqtt_service: MQTTService | None = None
active_websockets: list[WebSocket] = []
main_loop: asyncio.AbstractEventLoop | None = None

# Throttle state for on_frigate_event_update: last time we hit the Frigate
# API for each in-progress event_id. Only ever touched from the MQTT
# client's single background thread (paho-mqtt's loop_forever), so no lock
# is needed — consistent with the rest of this module.
_last_update_check: dict[str, datetime] = {}


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


@app.on_event("startup")
async def startup():
    """Initialize database, start MQTT service, and setup HA Discovery."""
    global mqtt_service, main_loop

    logger.info("Starting Face Recognition Service...")
    main_loop = asyncio.get_running_loop()

    # Initialize database
    init_db()

    # Initialize MQTT service
    mqtt_service = MQTTService()
    mqtt_service.set_frigate_callback(on_frigate_event)

    try:
        mqtt_service.connect()
        await asyncio.sleep(1)  # Give MQTT time to connect

        # Publish HA Discovery configs
        if mqtt_service.connected:
            for entity_id, config in get_discovery_configs().items():
                mqtt_service.publish_ha_discovery(entity_id, entity_id, config)
            logger.info("Published Home Assistant MQTT Discovery configs")
        else:
            logger.warning("MQTT not connected, HA Discovery skipped")
    except Exception as e:
        logger.error(f"Failed to initialize MQTT: {e}")


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
                confidence=confidence,
                frigate_event_id=event_id,
                notified=is_confident,
                timestamp=timestamp,
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
    the track ends. Poll for those crops here (throttled per event_id) so a
    confident, reliable result can be published within a second or two of
    the person appearing, instead of only at "end" when they leave the
    frame. No-ops once the event has already been notified.
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

        from routes.training import get_face_engine

        engine = get_face_engine()
        best_name, best_confidence = None, -1.0
        for crop_bytes in crops:
            result = engine.analyze_image(crop_bytes, db)
            for face_result in result["results"]:
                if face_result["confidence"] > best_confidence:
                    best_confidence = face_result["confidence"]
                    best_name = face_result["name"]

        if best_name in (None, "unknown", "uncertain"):
            return  # Not confident yet — try again on the next throttled update.

        if event is None:
            event = RecognitionEvent(
                camera=camera,
                person_name=best_name,
                confidence=best_confidence,
                frigate_event_id=event_id,
                timestamp=now,
            )
            db.add(event)
        else:
            event.person_name = best_name
            event.confidence = best_confidence

        event.notified = True
        db.commit()

        logger.info(
            f"Real-time recognition via Frigate face crop (update event) for "
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
    event, and re-run our own matching against Frigate's dedicated
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
        best_name, best_confidence = None, -1.0
        if crops:
            from routes.training import get_face_engine

            engine = get_face_engine()
            for crop_bytes in crops:
                result = engine.analyze_image(crop_bytes, db)
                for face_result in result["results"]:
                    if face_result["confidence"] > best_confidence:
                        best_confidence = face_result["confidence"]
                        best_name = face_result["name"]

        refined = False
        if event is None:
            if best_name is None:
                # Nothing was ever saved for this event (e.g. no snapshot at
                # "new") and Frigate has no face crops for it either.
                return
            event = RecognitionEvent(
                camera=frigate_event.get("camera", "unknown"),
                person_name=best_name,
                confidence=best_confidence,
                frigate_event_id=event_id,
                timestamp=datetime.utcnow(),
            )
            db.add(event)
            refined = True
        elif best_name is not None and best_confidence > event.confidence:
            event.person_name = best_name
            event.confidence = best_confidence
            refined = True

        if sub_label is not None:
            event.frigate_sub_label = sub_label
            event.frigate_sub_label_score = sub_label_score

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
                f"Refined recognition for event {event_id} using Frigate face crops: "
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
