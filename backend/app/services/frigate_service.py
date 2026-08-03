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

    def get_snapshot(self, event_id: str) -> Optional[bytes]:
        """Get snapshot for a Frigate event."""
        try:
            url = f"{self.base_url}/api/events/{event_id}/snapshot.jpg"
            response = requests.get(url, timeout=self.timeout)
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

    def health_check(self) -> bool:
        """Check if Frigate API is reachable."""
        try:
            url = f"{self.base_url}/api/stats"
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Frigate health check failed: {e}")
            return False
