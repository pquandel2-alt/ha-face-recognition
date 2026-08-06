from sqlalchemy import Column, Integer, String, Float

from database import Base


class AppSettings(Base):
    """
    Single-row table (id=1) of runtime overrides for the Settings page.
    Every column is nullable — NULL means "use the config.yaml/HA add-on
    option default from config.Settings", a non-NULL value overrides it.
    Loaded once at startup (see database.load_settings_overrides) and
    applied directly onto the shared config.settings singleton; further
    updates go through routes/settings.py's PUT endpoint.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)

    # Recognition thresholds
    similarity_threshold_known = Column(Float, nullable=True)
    similarity_threshold_unknown = Column(Float, nullable=True)
    similarity_margin_min = Column(Float, nullable=True)
    knn_k = Column(Integer, nullable=True)

    # Quality checks
    quality_blur_threshold = Column(Float, nullable=True)
    quality_contrast_threshold = Column(Float, nullable=True)

    # Outlier detection
    outlier_similarity_threshold = Column(Float, nullable=True)
    outlier_min_images = Column(Integer, nullable=True)

    # Frigate import clustering
    cluster_similarity_threshold = Column(Float, nullable=True)

    # Consensus (multi-crop agreement)
    consensus_min_crops = Column(Integer, nullable=True)
    consensus_fallback_margin_min = Column(Float, nullable=True)

    # Frigate polling / retention
    frigate_update_check_interval_seconds = Column(Integer, nullable=True)
    frigate_snapshot_retention_hours = Column(Integer, nullable=True)
    event_retention_days = Column(Integer, nullable=True)

    # Requires reload/reconnect when changed, handled in routes/settings.py
    insightface_model = Column(String(50), nullable=True)
    frigate_api_url = Column(String(512), nullable=True)
    mqtt_host = Column(String(255), nullable=True)
    mqtt_port = Column(Integer, nullable=True)
    mqtt_username = Column(String(255), nullable=True)
    mqtt_password = Column(String(255), nullable=True)
