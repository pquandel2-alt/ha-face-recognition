import logging
from datetime import datetime, timedelta
from typing import Optional, List

import requests

from config import settings

logger = logging.getLogger(__name__)


class FrigateService:
    """Client for Frigate NVR REST API."""

    def __init__(self):
        self.base_url = settings.frigate_api_url.rstrip("/")
        self.timeout = 10

    def get_recent_events(
        self, label: str = "person", limit: int = 50, after_hours: int = 24
    ) -> List[dict]:
        """
        Get recent Frigate events.
        Returns list of event dicts with id, camera, timestamp, etc.
        """
        try:
            after_timestamp = int(
                (datetime.utcnow() - timedelta(hours=after_hours)).timestamp()
            )
            url = f"{self.base_url}/api/events?label={label}&limit={limit}&after={after_timestamp}"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching Frigate events: {e}")
            return []

    def get_event(self, event_id: str) -> Optional[dict]:
        """Get a single Frigate event by id (includes sub_label once finalized)."""
        try:
            url = f"{self.base_url}/api/events/{event_id}"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching Frigate event {event_id}: {e}")
            return None

    def get_snapshot(self, event_id: str, crop: bool = False) -> Optional[bytes]:
        """
        Get snapshot for a Frigate event.

        crop=True requests Frigate's variant cropped tightly to the tracked
        object's bounding box instead of the full camera frame — the "new"
        event snapshot is often still far/small in the full frame, which
        hurts our own face detector's hit rate.
        """
        try:
            url = f"{self.base_url}/api/events/{event_id}/snapshot.jpg"
            params = {"crop": 1} if crop else None
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error fetching snapshot for event {event_id}: {e}")
            return None

    def get_thumbnail(self, event_id: str) -> Optional[bytes]:
        """Get thumbnail for a Frigate event."""
        try:
            url = f"{self.base_url}/api/events/{event_id}/thumbnail.jpg"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error fetching thumbnail for event {event_id}: {e}")
            return None

    def get_trained_faces(self) -> dict:
        """
        Get Frigate's own trained face images (Frigate's built-in Face Recognition
        feature), grouped by person name. Excludes the 'train' bucket, which holds
        Frigate's auto-collected recognition attempts rather than manually trained faces.
        """
        try:
            url = f"{self.base_url}/api/faces"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            data.pop("train", None)
            return data
        except Exception as e:
            logger.error(f"Error fetching Frigate trained faces: {e}")
            return {}

    def get_train_face_crops(self, event_id: str) -> List[bytes]:
        """
        Fetch Frigate's own auto-collected face-detector crops for one event
        from the /api/faces 'train' bucket (filenames are prefixed with the
        Frigate event id). Frigate runs a dedicated face detector to produce
        these — tightly cropped to the actual face — unlike our crop=1
        snapshot which is the whole person bounding box, so these are a much
        better match for the framing our stored embeddings were trained on.
        """
        try:
            url = f"{self.base_url}/api/faces"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            filenames = response.json().get("train", [])
            crops = []
            for filename in filenames:
                if not filename.startswith(f"{event_id}-"):
                    continue
                image_response = requests.get(
                    f"{self.base_url}/clips/faces/train/{filename}", timeout=self.timeout
                )
                if image_response.ok:
                    crops.append(image_response.content)
            return crops
        except Exception as e:
            logger.error(f"Error fetching train face crops for event {event_id}: {e}")
            return []

    def get_face_image(self, name: str, filename: str) -> Optional[bytes]:
        """Get one of Frigate's trained face images by person name + filename."""
        try:
            url = f"{self.base_url}/clips/faces/{name}/{filename}"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error fetching Frigate face image {name}/{filename}: {e}")
            return None

    def health_check(self) -> bool:
        """Check if Frigate API is reachable."""
        try:
            url = f"{self.base_url}/api/stats"
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Frigate health check failed: {e}")
            return False
