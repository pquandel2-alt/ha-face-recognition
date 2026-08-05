import logging

from config import settings

logger = logging.getLogger(__name__)


def get_discovery_configs() -> dict:
    """
    Generate Home Assistant MQTT Discovery configs for all sensors.
    Returns dict of entity_id -> config.
    """
    base_topic = settings.mqtt_result_topic
    device = {
        "name": "Face Recognition",
        "identifiers": ["face_recognition"],
        "manufacturer": "Home Assistant",
    }
    # Shared availability so all three sensors show "unavailable" in HA
    # instead of a stale last-known value if the add-on crashes or loses
    # its MQTT connection (see MQTTService.will_set in mqtt_service.py).
    availability = {
        "availability_topic": settings.mqtt_availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
    }

    configs = {
        "face_last_person": {
            "name": "Face Last Person",
            "unique_id": "face_recognition_last_person",
            "state_topic": f"{base_topic}",
            "value_template": "{{ value_json.name }}",
            "json_attributes_topic": f"{base_topic}",
            "json_attributes_template": "{{ value_json | tojson }}",
            "icon": "mdi:face-recognition",
            "device": device,
            **availability,
        },
        "face_confidence": {
            "name": "Face Confidence",
            "unique_id": "face_recognition_confidence",
            "state_topic": f"{base_topic}",
            "value_template": "{{ value_json.confidence | round(2) }}",
            "unit_of_measurement": "%",
            "json_attributes_topic": f"{base_topic}",
            "device_class": "severity",
            "icon": "mdi:percent",
            "device": device,
            **availability,
        },
        "face_camera": {
            "name": "Face Camera",
            "unique_id": "face_recognition_camera",
            "state_topic": f"{base_topic}",
            "value_template": "{{ value_json.camera }}",
            "icon": "mdi:camera",
            "device": device,
            **availability,
        },
    }

    return configs
