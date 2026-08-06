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
    mqtt_availability_topic: str = "home/face_recognition/status"
    mqtt_ha_discovery_prefix: str = "homeassistant"

    # Frigate
    frigate_api_url: str = "http://192.168.1.100:5000"
    frigate_snapshot_retention_hours: int = 24
    # How long RecognitionEvent rows stay in the database before being
    # purged — without this, the events table grows unbounded since
    # confirmed events already have their training data copied elsewhere
    # (see routes/recognition.py confirm_event).
    event_retention_days: int = 7
    # Throttle for checking Frigate's train-face-crop bucket during an active
    # track (via "update" MQTT events) — avoids hitting the Frigate API on
    # every one of the frequent update ticks.
    frigate_update_check_interval_seconds: int = 1

    # Face Recognition
    insightface_model: str = "buffalo_sc"
    insightface_providers: list = ["CPUExecutionProvider"]
    similarity_threshold_known: float = 0.50
    similarity_threshold_unknown: float = 0.35
    # Below these, a training image is flagged as low-quality (still saved,
    # just surfaced as a warning) — blurry/low-contrast source images are a
    # common, otherwise silent cause of bad embeddings and wrong matches.
    quality_blur_threshold: float = 80.0
    quality_contrast_threshold: float = 20.0
    # Similarity above which two Frigate person-event snapshots are grouped
    # into the same on-the-fly cluster in the Frigate-import UI (no
    # persistence — purely a request-time convenience for bulk selection).
    cluster_similarity_threshold: float = 0.45
    # Minimum gap between the winning candidate's similarity and the best
    # similarity among a *different* person before a match counts as "known"
    # — guards against two similar-looking people separated by a hair.
    similarity_margin_min: float = 0.05
    # Number of nearest per-image embeddings considered in the k-NN majority
    # vote in find_best_match.
    knn_k: int = 5
    # Minimum number of Frigate face crops that must agree on the same person
    # before a "update"/"end" recognition is trusted.
    consensus_min_crops: int = 2
    # Stricter margin required to publish from a single crop when fewer than
    # consensus_min_crops crops are available yet (e.g. a very brief
    # appearance) — avoids regressing responsiveness while still guarding
    # against a lone bad crop.
    consensus_fallback_margin_min: float = 0.15
    # Below this leave-one-out similarity to a person's own other training
    # images, a training image is flagged "outlier" in quality_warning.
    outlier_similarity_threshold: float = 0.30
    # Minimum number of training images a person needs before outlier
    # detection runs (too few images make the leave-one-out comparison
    # meaningless).
    outlier_min_images: int = 3

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
