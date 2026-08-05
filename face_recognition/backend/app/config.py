import json
import logging
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

HA_OPTIONS_PATH = Path("/data/options.json")


def _load_ha_addon_options() -> dict:
    """Read Supervisor-managed Options if present (HA Add-on mode)."""
    if not HA_OPTIONS_PATH.is_file():
        return {}
    try:
        with open(HA_OPTIONS_PATH) as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if v is not None}
    except Exception:
        return {}


class Settings(BaseSettings):
    # MQTT
    mqtt_host: str = "192.168.1.100"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_frigate_topic: str = "frigate/events"
    mqtt_result_topic: str = "home/face_recognition/person"
    mqtt_ha_discovery_prefix: str = "homeassistant"

    # Frigate
    frigate_api_url: str = "http://192.168.1.100:5000"
    frigate_snapshot_retention_hours: int = 24
    # Throttle for checking Frigate's train-face-crop bucket during an active
    # track (via "update" MQTT events) — avoids hitting the Frigate API on
    # every one of the frequent update ticks.
    frigate_update_check_interval_seconds: int = 2

    # Face Recognition
    insightface_model: str = "buffalo_sc"
    insightface_providers: list = ["CPUExecutionProvider"]
    similarity_threshold_known: float = 0.50
    similarity_threshold_unknown: float = 0.35

    # Database
    data_dir: Path = Path("/data")
    database_url: str = "sqlite:////data/face_db.db"

    # Logging
    log_level: str = "INFO"

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**{**_load_ha_addon_options(), **kwargs})
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "images").mkdir(exist_ok=True)
        (self.data_dir / "models").mkdir(exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


settings = Settings()
