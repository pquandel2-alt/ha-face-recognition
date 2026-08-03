import asyncio
import logging
from base64 import b64decode
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import init_db, get_db, SessionLocal
from models.event import RecognitionEvent
from routes import persons, training, recognition, frigate
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


# Auth middleware
class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not settings.auth_enabled:
            return await call_next(request)

        # Skip auth for health check and root
        if request.url.path in ["/health", "/"] or request.url.path.startswith("/docs"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header",
                headers={"WWW-Authenticate": "Basic"},
            )

        try:
            scheme, credentials = auth_header.split(" ", 1)
            if scheme.lower() != "basic":
                raise ValueError
            decoded = b64decode(credentials).decode("utf-8")
            username, password = decoded.split(":", 1)

            if username == settings.auth_username and password == settings.auth_password:
                return await call_next(request)
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.warning(f"Auth error: {e}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


if settings.auth_enabled:
    app.add_middleware(BasicAuthMiddleware)

# Include routes
app.include_router(persons.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(recognition.router, prefix="/api")
app.include_router(frigate.router, prefix="/api")


# Global MQTT service
mqtt_service: MQTTService | None = None
active_websockets: list[WebSocket] = []


@app.on_event("startup")
async def startup():
    """Initialize database, start MQTT service, and setup HA Discovery."""
    global mqtt_service

    logger.info("Starting Face Recognition Service...")

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
        camera = after.get("camera")
        event_id = after.get("id")

        # Only process new person detections
        if event_type not in ["new", "update"] or label != "person":
            return

        logger.debug(f"Processing Frigate event: {camera}/{event_id}")

        # Get snapshot and analyze
        frigate = FrigateService()
        snapshot_bytes = frigate.get_snapshot(event_id)
        if not snapshot_bytes:
            logger.warning(f"Could not get snapshot for event {event_id}")
            return

        # Analyze with face engine
        db = SessionLocal()
        try:
            from routes.training import get_face_engine

            engine = get_face_engine()
            result = engine.analyze_image(snapshot_bytes, db)

            # Take best match
            best_result = max(result["results"], key=lambda x: x["confidence"])
            person_name = best_result["name"]
            confidence = best_result["confidence"]

            # Save event
            timestamp = datetime.utcnow()
            event = RecognitionEvent(
                camera=camera,
                person_name=person_name,
                confidence=confidence,
                frigate_event_id=event_id,
                timestamp=timestamp,
            )
            db.add(event)
            db.commit()

            # Publish via MQTT
            if mqtt_service and mqtt_service.connected:
                mqtt_service.publish_recognition(person_name, confidence, camera, timestamp.isoformat())

            # Notify WebSocket clients
            asyncio.create_task(
                broadcast_event(
                    {
                        "type": "recognition",
                        "person": person_name,
                        "confidence": confidence,
                        "camera": camera,
                        "timestamp": timestamp.isoformat(),
                    }
                )
            )

            logger.info(f"Frigate event: {person_name} ({confidence:.2f}) on {camera}")
        except Exception as e:
            logger.error(f"Error processing Frigate event: {e}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in on_frigate_event: {e}")


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


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "Face Recognition API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )
