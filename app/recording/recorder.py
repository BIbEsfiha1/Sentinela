"""FFmpeg recording manager - zero transcoding with segment muxer."""

import subprocess
import sys
import os
import logging
import time
from pathlib import Path
from datetime import datetime
from ..models import CameraModel, CameraStatus
from ..cameras.rtsp import build_rtsp_url_from_camera
from ..config import load_config, update_camera, BASE_DIR

logger = logging.getLogger(__name__)


class RecorderManager:
    """Manages one FFmpeg process per camera."""

    def __init__(self):
        self._processes: dict[str, subprocess.Popen] = {}
        self._start_times: dict[str, float] = {}
        self._fail_counts: dict[str, int] = {}

    def _get_output_path(self, camera_id: str) -> Path:
        config = load_config()
        today = datetime.now().strftime("%Y-%m-%d")
        path = BASE_DIR / config.recording.recordings_path / today / camera_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def start_camera(self, camera: CameraModel):
        """Start recording for a camera."""
        if camera.id in self._processes:
            proc = self._processes[camera.id]
            if proc.poll() is None:
                logger.info(f"Camera {camera.id} already recording.")
                return

        rtsp_url = build_rtsp_url_from_camera(camera)
        output_dir = self._get_output_path(camera.id)
        config = load_config()
        segment_time = config.recording.segment_duration

        output_pattern = str(output_dir / "rec_%H-%M-%S.mp4")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-timeout", "5000000",
            "-i", rtsp_url,
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-segment_format", "mp4",
            "-strftime", "1",
            "-reset_timestamps", "1",
            "-movflags", "+faststart",
            output_pattern,
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
            self._processes[camera.id] = proc
            self._start_times[camera.id] = time.time()
            self._fail_counts[camera.id] = 0

            # Update status
            config = load_config()
            update_camera(config, camera.id, {"status": CameraStatus.RECORDING.value})

            logger.info(f"Recording started: {camera.name} ({camera.id}) -> {output_dir}")
        except FileNotFoundError:
            logger.error("FFmpeg not found. Install FFmpeg and add to PATH.")
            config = load_config()
            update_camera(config, camera.id, {"status": CameraStatus.ERROR.value})
        except Exception as e:
            logger.error(f"Failed to start recording for {camera.id}: {e}")
            config = load_config()
            update_camera(config, camera.id, {"status": CameraStatus.ERROR.value})

    def stop_camera(self, camera_id: str):
        """Stop recording for a camera."""
        proc = self._processes.pop(camera_id, None)
        self._start_times.pop(camera_id, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info(f"Recording stopped: {camera_id}")

        config = load_config()
        update_camera(config, camera_id, {"status": CameraStatus.OFFLINE.value})

    def stop_all(self):
        """Stop all recordings."""
        for cam_id in list(self._processes.keys()):
            self.stop_camera(cam_id)

    def is_recording(self, camera_id: str) -> bool:
        """Check if a camera is recording."""
        proc = self._processes.get(camera_id)
        return proc is not None and proc.poll() is None

    def get_status(self) -> dict:
        """Get status of all recording processes."""
        status = {}
        for cam_id, proc in self._processes.items():
            alive = proc.poll() is None
            status[cam_id] = {
                "recording": alive,
                "pid": proc.pid if alive else None,
                "uptime": time.time() - self._start_times.get(cam_id, time.time()),
            }
        return status

    def check_and_restart(self):
        """Check for dead processes and restart them. Called by watchdog."""
        config = load_config()
        for camera in config.cameras:
            if not camera.enabled:
                continue

            proc = self._processes.get(camera.id)
            if proc is None or proc.poll() is not None:
                # Process died or never started
                fail_count = self._fail_counts.get(camera.id, 0)
                # Exponential backoff: 5, 10, 30, 60, 300 seconds
                backoffs = [5, 10, 30, 60, 300]
                backoff = backoffs[min(fail_count, len(backoffs) - 1)]
                last_start = self._start_times.get(camera.id, 0)

                if time.time() - last_start >= backoff:
                    self._fail_counts[camera.id] = fail_count + 1
                    logger.warning(f"Restarting recording for {camera.id} (attempt {fail_count + 1})")
                    self.start_camera(camera)

    def day_rollover(self):
        """Restart all recordings for new day folder. Called at midnight."""
        logger.info("Day rollover: restarting all recordings")
        config = load_config()
        for camera in config.cameras:
            if camera.enabled and self.is_recording(camera.id):
                self.stop_camera(camera.id)
                self.start_camera(camera)
