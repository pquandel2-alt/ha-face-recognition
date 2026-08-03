import logging

from config import settings

logger = logging.getLogger(__name__)


def get_discovery_configs() -> dict:
    """
    Generate Home Assistant MQTT Discovery configs for all sensors.
    Returns dict of entity_id -> config.
    """
    base_topic = settings.mqtt_result_topic

    configs = {
        "face_last_person": {
            "name": "Face Last Person",
            "unique_id": "face_recognition_last_person",
            "state_topic": f"{base_topic}",
            "value_template": "{{ value_json.name }}",
            "json_attributes_topic": f"{base_topic}",
            "json_attributes_template": "{{ value_json | tojson }}",
            "icon": "mdi:face-recognition",
            "device": {
                "name": "Face Recognition",
                "identifiers": ["face_recognition"],
                "manufacturer": "Home Assistant",
            },
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
            "device": {
                "name": "Face Recognition",
                "identifiers": ["face_recognition"],
                "manufacturer": "Home Assistant",
            },
        },
        "face_camera": {
            "name": "Face Camera",
            "unique_id": "face_recognition_camera",
            "state_topic": f"{base_topic}",
            "value_template": "{{ value_json.camera }}",
            "icon": "mdi:camera",
            "device": {
                "name": "Face Recognition",
                "identifiers": ["face_recognition"],
                "manufacturer": "Home Assistant",
            },
        },
    }

    return configs
