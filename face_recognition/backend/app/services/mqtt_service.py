import json
import logging
import threading
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from config import settings

logger = logging.getLogger(__name__)


class MQTTService:
    """MQTT client for Frigate integration and Home Assistant."""

    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.connected = False
        self.frigate_callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None

    def set_frigate_callback(self, callback: Callable):
        """Set callback for Frigate events."""
        self.frigate_callback = callback

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """Called when connected to broker."""
        if reason_code == 0:
            logger.info(f"Connected to MQTT broker {settings.mqtt_host}:{settings.mqtt_port}")
            self.connected = True
            client.subscribe(settings.mqtt_frigate_topic)
            # Mark ourselves available now that we're actually connected —
            # the Last Will (set in connect()) takes over and flips this to
            # "offline" automatically if the connection drops uncleanly.
            client.publish(settings.mqtt_availability_topic, "online", qos=1, retain=True)
        else:
            logger.error(f"MQTT connection failed: {reason_code}")
            self.connected = False

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Called when disconnected from broker."""
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")
        self.connected = False

    def _on_message(self, client, userdata, msg):
        """Called when message received."""
        try:
            if msg.topic == settings.mqtt_frigate_topic:
                payload = json.loads(msg.payload.decode())
                if self.frigate_callback:
                    self.frigate_callback(payload)
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def connect(self):
        """Connect to MQTT broker."""
        try:
            if settings.mqtt_username:
                self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
            # Last Will: if the container crashes or the connection drops
            # without a clean disconnect, the broker publishes this on our
            # behalf so HA's sensors show "unavailable" instead of silently
            # keeping the last-known person/confidence forever.
            self.client.will_set(settings.mqtt_availability_topic, "offline", qos=1, retain=True)
            self.client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            # Start background loop
            self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
            self._thread.start()
            logger.info("MQTT service started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            raise

    def disconnect(self):
        """Disconnect from MQTT broker."""
        # A clean disconnect doesn't trigger the Last Will, so mark
        # unavailable explicitly before closing the connection.
        try:
            self.client.publish(settings.mqtt_availability_topic, "offline", qos=1, retain=True)
        except Exception as e:
            logger.warning(f"Failed to publish offline availability: {e}")
        self.client.disconnect()

    def publish_recognition(self, person_name: str, confidence: float, camera: str, timestamp: str):
        """Publish recognition result."""
        payload = {
            "name": person_name,
            "confidence": confidence,
            "camera": camera,
            "time": timestamp,
        }
        try:
            self.client.publish(
                settings.mqtt_result_topic,
                json.dumps(payload),
                qos=1,
                retain=False,
            )
            logger.debug(f"Published: {person_name} ({confidence:.2f}) on {camera}")
        except Exception as e:
            logger.error(f"Failed to publish recognition result: {e}")

    def publish_ha_discovery(self, sensor_name: str, entity_id: str, config: dict):
        """Publish Home Assistant MQTT Discovery config."""
        topic = f"{settings.mqtt_ha_discovery_prefix}/sensor/face_recognition/{entity_id}/config"
        try:
            self.client.publish(
                topic,
                json.dumps(config),
                qos=1,
                retain=True,
            )
            logger.debug(f"Published HA discovery for {sensor_name}")
        except Exception as e:
            logger.error(f"Failed to publish HA discovery: {e}")
