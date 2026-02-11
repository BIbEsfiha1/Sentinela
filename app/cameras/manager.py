"""Camera lifecycle management."""

import logging
from ..models import CameraModel, CameraStatus
from ..config import load_config, update_camera

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages camera status updates."""

    def set_status(self, camera_id: str, status: CameraStatus):
        """Update camera status in config."""
        config = load_config()
        update_camera(config, camera_id, {"status": status.value})

    def get_all_enabled(self) -> list[CameraModel]:
        """Get all enabled cameras."""
        config = load_config()
        return [c for c in config.cameras if c.enabled]

    def get_all(self) -> list[CameraModel]:
        """Get all cameras."""
        config = load_config()
        return config.cameras
