"""MediaMTX management for RTSP -> WebRTC/HLS conversion."""

import subprocess
import sys
import os
import logging
import time
import yaml
from pathlib import Path
from ..models import CameraModel
from ..cameras.rtsp import build_rtsp_url_from_camera
from ..config import load_config, BASE_DIR

logger = logging.getLogger(__name__)

MEDIAMTX_DIR = BASE_DIR / "tools" / "mediamtx"
MEDIAMTX_EXE = MEDIAMTX_DIR / "mediamtx.exe"
MEDIAMTX_CONFIG = MEDIAMTX_DIR / "mediamtx.yml"


class MediaMTXManager:
    """Manages the MediaMTX process for live streaming."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._cameras: dict[str, CameraModel] = {}

    def _generate_config(self):
        """Generate mediamtx.yml with camera paths."""
        config = load_config()

        mtx_config = {
            "logLevel": "warn",
            "logDestinations": ["stdout"],
            "api": True,
            "apiAddress": f":{config.system.mediamtx_api_port}",
            "rtsp": True,
            "rtspAddress": ":8554",
            "webrtc": True,
            "webrtcAddress": f":{config.system.mediamtx_webrtc_port}",
            "hls": True,
            "hlsAddress": ":8888",
            "paths": {},
        }

        for cam_id, camera in self._cameras.items():
            rtsp_url = build_rtsp_url_from_camera(camera)
            mtx_config["paths"][cam_id] = {
                "source": rtsp_url,
                "sourceOnDemand": True,
                "sourceOnDemandStartTimeout": "10s",
                "sourceOnDemandCloseAfter": "30s",
            }

        # Add a catch-all for any path
        mtx_config["paths"]["all_others"] = {
            "source": "publisher",
        }

        MEDIAMTX_DIR.mkdir(parents=True, exist_ok=True)
        with open(MEDIAMTX_CONFIG, "w") as f:
            yaml.dump(mtx_config, f, default_flow_style=False)

        logger.info(f"MediaMTX config generated with {len(self._cameras)} cameras")

    def start(self):
        """Start MediaMTX process."""
        if not MEDIAMTX_EXE.exists():
            logger.warning(f"MediaMTX not found at {MEDIAMTX_EXE}. Run setup.bat to download.")
            return

        self._generate_config()

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self._process = subprocess.Popen(
                [str(MEDIAMTX_EXE), str(MEDIAMTX_CONFIG)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=str(MEDIAMTX_DIR),
                creationflags=creationflags,
            )
            logger.info(f"MediaMTX started (PID: {self._process.pid})")
        except Exception as e:
            logger.error(f"Failed to start MediaMTX: {e}")

    def stop(self):
        """Stop MediaMTX process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("MediaMTX stopped.")
        self._process = None

    def restart(self):
        """Restart MediaMTX with updated config."""
        self.stop()
        time.sleep(1)
        self.start()

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def add_camera(self, camera: CameraModel):
        """Add a camera and reload config."""
        self._cameras[camera.id] = camera
        if self.is_running():
            self._generate_config()
            # MediaMTX supports hot reload via API, but restart is simpler
            self.restart()

    def remove_camera(self, camera_id: str):
        """Remove a camera and reload config."""
        self._cameras.pop(camera_id, None)
        if self.is_running():
            self._generate_config()
            self.restart()

    def get_webrtc_url(self, camera_id: str, request_host: str = "localhost") -> str:
        """Get WebRTC URL for a camera, adjusted for the requesting host."""
        config = load_config()
        port = config.system.mediamtx_webrtc_port
        # Use the same host as the request (works for LAN and tunnel)
        host = request_host.split(":")[0]
        return f"http://{host}:{port}/{camera_id}/whep"

    def get_hls_url(self, camera_id: str, request_host: str = "localhost") -> str:
        """Get HLS URL for a camera."""
        host = request_host.split(":")[0]
        return f"http://{host}:8888/{camera_id}/index.m3u8"
