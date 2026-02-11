"""Storage management - file organization and cleanup."""

import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from ..config import load_config, BASE_DIR

logger = logging.getLogger(__name__)


def get_recordings_path() -> Path:
    config = load_config()
    return BASE_DIR / config.recording.recordings_path


def get_recordings_size_bytes() -> int:
    """Get total size of recordings directory."""
    rec_path = get_recordings_path()
    total = 0
    if rec_path.exists():
        for f in rec_path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def cleanup_old_recordings():
    """Delete recordings older than retention_days."""
    config = load_config()
    rec_path = get_recordings_path()
    if not rec_path.exists():
        return

    cutoff = datetime.now() - timedelta(days=config.recording.retention_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    deleted = 0

    for day_dir in sorted(rec_path.iterdir()):
        if day_dir.is_dir() and day_dir.name < cutoff_str:
            try:
                shutil.rmtree(day_dir)
                deleted += 1
                logger.info(f"Deleted old recordings: {day_dir.name}")
            except Exception as e:
                logger.error(f"Failed to delete {day_dir}: {e}")

    if deleted:
        logger.info(f"Cleanup: deleted {deleted} old day folders")


def cleanup_if_disk_low(min_free_gb: float = 5.0):
    """Delete oldest recordings if disk space is low."""
    import psutil
    rec_path = get_recordings_path()
    if not rec_path.exists():
        return

    disk = psutil.disk_usage(str(BASE_DIR))
    free_gb = disk.free / (1024**3)

    if free_gb >= min_free_gb:
        return

    logger.warning(f"Disk space low: {free_gb:.1f} GB free. Cleaning up...")

    # Delete oldest day folders first
    day_dirs = sorted(d for d in rec_path.iterdir() if d.is_dir())
    for day_dir in day_dirs:
        if free_gb >= min_free_gb:
            break
        try:
            size = sum(f.stat().st_size for f in day_dir.rglob("*") if f.is_file())
            shutil.rmtree(day_dir)
            free_gb += size / (1024**3)
            logger.info(f"Emergency cleanup: deleted {day_dir.name} (freed {size/(1024**3):.1f} GB)")
        except Exception as e:
            logger.error(f"Failed to delete {day_dir}: {e}")


def list_dates() -> list[str]:
    """List available recording dates."""
    rec_path = get_recordings_path()
    if not rec_path.exists():
        return []
    return sorted(
        [d.name for d in rec_path.iterdir() if d.is_dir() and len(d.name) == 10],
        reverse=True,
    )


def list_cameras_for_date(date: str) -> list[dict]:
    """List cameras with recordings for a given date."""
    rec_path = get_recordings_path() / date
    if not rec_path.exists():
        return []

    config = load_config()
    result = []
    for cam_dir in sorted(rec_path.iterdir()):
        if not cam_dir.is_dir():
            continue
        files = []
        for f in sorted(cam_dir.iterdir()):
            if f.suffix == ".mp4":
                files.append({
                    "name": f.name,
                    "size_mb": round(f.stat().st_size / (1024**2), 1),
                })
        cam = next((c for c in config.cameras if c.id == cam_dir.name), None)
        result.append({
            "id": cam_dir.name,
            "name": cam.name if cam else cam_dir.name,
            "files": files,
        })
    return result
