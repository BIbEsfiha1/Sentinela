"""Configuration management using config.yaml."""

import yaml
import os
import logging
from pathlib import Path
from .models import AppConfig, CameraModel

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> AppConfig:
    """Load configuration from config.yaml, creating defaults if missing."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return AppConfig(**data)
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            return AppConfig()
    else:
        config = AppConfig()
        save_config(config)
        return config


def save_config(config: AppConfig) -> None:
    """Save configuration to config.yaml."""
    try:
        data = config.model_dump(mode="json")
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Config saved.")
    except Exception as e:
        logger.error(f"Error saving config: {e}")


def get_camera(config: AppConfig, camera_id: str) -> CameraModel | None:
    """Get a camera by ID."""
    for cam in config.cameras:
        if cam.id == camera_id:
            return cam
    return None


def add_camera(config: AppConfig, camera: CameraModel) -> AppConfig:
    """Add a camera to config."""
    config.cameras.append(camera)
    save_config(config)
    return config


def remove_camera(config: AppConfig, camera_id: str) -> AppConfig:
    """Remove a camera from config."""
    config.cameras = [c for c in config.cameras if c.id != camera_id]
    save_config(config)
    return config


def update_camera(config: AppConfig, camera_id: str, updates: dict) -> AppConfig:
    """Update a camera's settings."""
    for i, cam in enumerate(config.cameras):
        if cam.id == camera_id:
            cam_data = cam.model_dump()
            cam_data.update({k: v for k, v in updates.items() if v is not None})
            config.cameras[i] = CameraModel(**cam_data)
            break
    save_config(config)
    return config


def next_camera_id(config: AppConfig) -> str:
    """Generate next camera ID."""
    if not config.cameras:
        return "camera-1"
    nums = []
    for c in config.cameras:
        try:
            nums.append(int(c.id.split("-")[-1]))
        except ValueError:
            pass
    next_num = max(nums, default=0) + 1
    return f"camera-{next_num}"
