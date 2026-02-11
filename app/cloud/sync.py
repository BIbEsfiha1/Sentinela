"""Cloud sync management with rclone (Google Drive primary)."""

import subprocess
import sys
import os
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from ..models import CloudSettings, CloudProvider
from ..config import load_config, BASE_DIR

logger = logging.getLogger(__name__)

RCLONE_EXE = BASE_DIR / "tools" / "rclone" / "rclone.exe"


class CloudSyncManager:
    """Manages periodic cloud sync via rclone."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._syncing = False
        self._last_sync: str | None = None
        self._last_error: str | None = None
        self._next_sync: float = 0

    def start(self):
        """Start periodic sync thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info("Cloud sync started")

    def stop(self):
        """Stop sync thread."""
        self._running = False
        logger.info("Cloud sync stopped")

    def sync_now(self):
        """Trigger immediate sync."""
        self._next_sync = 0

    def _sync_loop(self):
        """Background loop that syncs periodically."""
        while self._running:
            config = load_config()
            if not config.cloud.enabled:
                time.sleep(30)
                continue

            interval = config.cloud.sync_interval_minutes * 60

            if time.time() >= self._next_sync:
                self._do_sync(config.cloud)
                self._next_sync = time.time() + interval

            time.sleep(10)

    def _do_sync(self, cloud: CloudSettings):
        """Execute rclone copy."""
        if not RCLONE_EXE.exists():
            self._last_error = "rclone nao encontrado. Execute setup.bat."
            logger.error(self._last_error)
            return

        config = load_config()
        rec_path = BASE_DIR / config.recording.recordings_path

        if not rec_path.exists():
            return

        self._syncing = True
        self._last_error = None

        remote = f"{cloud.remote_name}:{cloud.remote_path}"

        cmd = [
            str(RCLONE_EXE),
            "copy",
            str(rec_path),
            remote,
            "--min-age", "2m",
            "--bwlimit", cloud.bandwidth_limit,
            "--log-level", "INFO",
            "--stats", "0",
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            logger.info(f"Cloud sync starting: {rec_path} -> {remote}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                self._last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Cloud sync complete at {self._last_sync}")
            else:
                self._last_error = result.stderr[:200] if result.stderr else "Unknown error"
                logger.error(f"Cloud sync failed: {self._last_error}")
        except subprocess.TimeoutExpired:
            self._last_error = "Sync timeout (1h)"
            logger.error(self._last_error)
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Cloud sync error: {e}")
        finally:
            self._syncing = False

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "syncing": self._syncing,
            "last_sync": self._last_sync,
            "error": self._last_error,
        }

    def is_configured(self) -> bool:
        """Check if rclone remote is configured."""
        if not RCLONE_EXE.exists():
            return False
        config = load_config()
        try:
            result = subprocess.run(
                [str(RCLONE_EXE), "listremotes"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return config.cloud.remote_name + ":" in result.stdout
        except Exception:
            return False


async def setup_rclone_remote(cloud: CloudSettings) -> dict:
    """Launch rclone config for the provider."""
    import asyncio

    if not RCLONE_EXE.exists():
        return {"ok": False, "error": "rclone nao encontrado. Execute setup.bat."}

    provider_map = {
        CloudProvider.GDRIVE: "drive",
        CloudProvider.ONEDRIVE: "onedrive",
        CloudProvider.DROPBOX: "dropbox",
        CloudProvider.S3: "s3",
    }

    provider_type = provider_map.get(cloud.provider)
    if not provider_type:
        return {"ok": False, "error": "Provedor nao suportado"}

    # Use rclone authorize flow - opens browser automatically
    try:
        cmd = [
            str(RCLONE_EXE), "config", "create",
            cloud.remote_name, provider_type,
        ]

        def _run():
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )

        result = await asyncio.to_thread(_run)
        if result.returncode == 0:
            return {"ok": True, "message": "Remoto configurado com sucesso!"}
        else:
            return {"ok": False, "error": result.stderr[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
