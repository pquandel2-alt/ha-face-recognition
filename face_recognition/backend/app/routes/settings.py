import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings, Settings
from database import get_db
from models.settings import AppSettings
from routes.training import reset_face_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Bounds mirror config.yaml's schema: section — kept in sync manually since
# the HA add-on schema and this API validate the same values through two
# different mechanisms (Supervisor UI vs. this app's own Settings page).
FIELD_SPECS = {
    "similarity_threshold_known": {"type": "float", "min": 0, "max": 1},
    "similarity_threshold_unknown": {"type": "float", "min": 0, "max": 1},
    "similarity_margin_min": {"type": "float", "min": 0, "max": 1},
    "knn_k": {"type": "int", "min": 1, "max": 20},
    "quality_blur_threshold": {"type": "float", "min": 0, "max": 1000},
    "quality_contrast_threshold": {"type": "float", "min": 0, "max": 255},
    "outlier_similarity_threshold": {"type": "float", "min": 0, "max": 1},
    "outlier_min_images": {"type": "int", "min": 2, "max": 20},
    "cluster_similarity_threshold": {"type": "float", "min": 0, "max": 1},
    "consensus_min_crops": {"type": "int", "min": 1, "max": 10},
    "consensus_fallback_margin_min": {"type": "float", "min": 0, "max": 1},
    "frigate_update_check_interval_seconds": {"type": "int", "min": 1, "max": 10},
    "frigate_snapshot_retention_hours": {"type": "int", "min": 1, "max": 720},
    "event_retention_days": {"type": "int", "min": 1, "max": 365},
    "insightface_model": {
        "type": "enum",
        "options": ["buffalo_sc", "buffalo_s", "buffalo_m", "buffalo_l"],
    },
    "frigate_api_url": {"type": "str"},
    "mqtt_host": {"type": "str"},
    "mqtt_port": {"type": "int", "min": 1, "max": 65535},
    "mqtt_username": {"type": "str", "secret": False},
    "mqtt_password": {"type": "str", "secret": True},
}

# Changing these requires rebuilding the FaceEngine/MQTTService singletons —
# handled below instead of just mutating settings in place.
_MODEL_FIELDS = {"insightface_model"}
_MQTT_FIELDS = {"mqtt_host", "mqtt_port", "mqtt_username", "mqtt_password"}


class SettingsUpdate(BaseModel):
    similarity_threshold_known: Optional[float] = None
    similarity_threshold_unknown: Optional[float] = None
    similarity_margin_min: Optional[float] = None
    knn_k: Optional[int] = None
    quality_blur_threshold: Optional[float] = None
    quality_contrast_threshold: Optional[float] = None
    outlier_similarity_threshold: Optional[float] = None
    outlier_min_images: Optional[int] = None
    cluster_similarity_threshold: Optional[float] = None
    consensus_min_crops: Optional[int] = None
    consensus_fallback_margin_min: Optional[float] = None
    frigate_update_check_interval_seconds: Optional[int] = None
    frigate_snapshot_retention_hours: Optional[int] = None
    event_retention_days: Optional[int] = None
    insightface_model: Optional[str] = None
    frigate_api_url: Optional[str] = None
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None


def _get_or_create_row(db: Session) -> AppSettings:
    row = db.query(AppSettings).filter_by(id=1).first()
    if row is None:
        row = AppSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("")
def get_settings():
    """
    Current effective value + default + validation bounds per field, so the
    Settings page can render inputs and validate client-side without
    duplicating the bounds definition.
    """
    fields = {}
    for name, spec in FIELD_SPECS.items():
        entry = {
            "value": getattr(settings, name),
            "default": Settings.model_fields[name].default,
            **spec,
        }
        if spec.get("secret"):
            entry["value"] = "•" * 8 if entry["value"] else ""
            entry["default"] = None
        fields[name] = entry
    return fields


@router.put("")
def update_settings(update: SettingsUpdate, db: Session = Depends(get_db)):
    """
    Partial update: validates bounds, persists to the AppSettings override
    row, mutates the shared settings singleton (effective everywhere
    immediately), and reloads the FaceEngine/MQTT singletons if a field that
    needs it changed.
    """
    changes = update.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        return {"updated": {}}

    for name, value in changes.items():
        spec = FIELD_SPECS[name]
        if spec["type"] in ("int", "float"):
            if not (spec["min"] <= value <= spec["max"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} must be between {spec['min']} and {spec['max']}",
                )
        elif spec["type"] == "enum":
            if value not in spec["options"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"{name} must be one of {spec['options']}",
                )

    row = _get_or_create_row(db)
    for name, value in changes.items():
        setattr(row, name, value)
        setattr(settings, name, value)
    db.commit()

    changed_fields = set(changes.keys())
    result = {name: "applied" for name in changed_fields}

    if changed_fields & _MODEL_FIELDS:
        reset_face_engine()
        for name in changed_fields & _MODEL_FIELDS:
            result[name] = "reloading"
        logger.info("insightface_model changed via Settings page, engine will reload on next use")

    if changed_fields & _MQTT_FIELDS:
        from main import reinitialize_mqtt

        reinitialize_mqtt()
        for name in changed_fields & _MQTT_FIELDS:
            result[name] = "reconnecting"
        logger.info("MQTT settings changed via Settings page, reconnecting")

    return {"updated": result}
