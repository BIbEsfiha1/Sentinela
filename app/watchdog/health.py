"""Watchdog - health checks, auto-recovery, and day rollover."""

import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class WatchdogManager:
    """Monitors all subsystems and auto-recovers on failure."""

    def __init__(self, app_state: dict):
        self._state = app_state
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_day: str = datetime.now().strftime("%Y-%m-%d")
        self._check_interval = 30  # seconds

    def start(self):
        """Start watchdog thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Watchdog started (checking every 30s)")

    def stop(self):
        """Stop watchdog."""
        self._running = False
        logger.info("Watchdog stopped")

    def _watch_loop(self):
        """Main watchdog loop."""
        while self._running:
            try:
                self._check_day_rollover()
                self._check_recorder()
                self._check_mediamtx()
                self._check_tunnel()
                self._check_disk()
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

            time.sleep(self._check_interval)

    def _check_day_rollover(self):
        """Restart recordings at midnight for new day folder."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_day:
            logger.info(f"Day rollover: {self._last_day} -> {today}")
            self._last_day = today
            recorder = self._state.get("recorder")
            if recorder:
                recorder.day_rollover()

    def _check_recorder(self):
        """Check FFmpeg processes and restart dead ones."""
        recorder = self._state.get("recorder")
        if recorder:
            recorder.check_and_restart()

    def _check_mediamtx(self):
        """Check MediaMTX is running."""
        mediamtx = self._state.get("mediamtx")
        if mediamtx and not mediamtx.is_running():
            logger.warning("MediaMTX is down. Restarting...")
            mediamtx.start()

    def _check_tunnel(self):
        """Check tunnel is running if configured."""
        from ..config import load_config
        config = load_config()
        tunnel = self._state.get("tunnel")
        if tunnel and config.tunnel.mode != "disabled":
            if not tunnel.is_running():
                logger.warning("Tunnel is down. Restarting...")
                tunnel.restart()

    def _check_disk(self):
        """Check disk space and cleanup if needed."""
        from ..recording.storage import cleanup_old_recordings, cleanup_if_disk_low
        cleanup_old_recordings()
        cleanup_if_disk_low()
