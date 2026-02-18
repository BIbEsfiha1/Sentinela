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
FFMPEG_EXE = BASE_DIR / "tools" / "ffmpeg" / "ffmpeg.exe"


class MediaMTXManager:
    """Manages the MediaMTX process and ffmpeg transcoders for live streaming."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._cameras: dict[str, CameraModel] = {}
        self._transcoders: dict[str, subprocess.Popen] = {}

    def _needs_transcode(self, camera: CameraModel) -> bool:
        """Check if camera needs H.265 -> H.264 transcoding."""
        codec = getattr(camera, "codec", "auto")
        brand = getattr(camera, "brand", "auto")
        return codec == "h265" or (codec == "auto" and brand in ("icsee",))

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
            if self._needs_transcode(camera):
                mtx_config["paths"][cam_id] = {
                    "source": "publisher",
                }
                logger.info(f"Camera {cam_id}: H.265 transcoding enabled")
            else:
                rtsp_url = build_rtsp_url_from_camera(camera)
                mtx_config["paths"][cam_id] = {
                    "source": rtsp_url,
                    "sourceOnDemand": True,
                    "sourceOnDemandStartTimeout": "10s",
                    "sourceOnDemandCloseAfter": "30s",
                }

        # Catch-all for any path
        mtx_config["paths"]["all_others"] = {
            "source": "publisher",
        }

        MEDIAMTX_DIR.mkdir(parents=True, exist_ok=True)
        with open(MEDIAMTX_CONFIG, "w") as f:
            yaml.dump(mtx_config, f, default_flow_style=False)

        logger.info(f"MediaMTX config generated with {len(self._cameras)} cameras")

    def _start_transcoder(self, cam_id: str, camera: CameraModel):
        """Start an ffmpeg transcoder process for an H.265 camera."""
        if not FFMPEG_EXE.exists():
            logger.error(f"ffmpeg not found at {FFMPEG_EXE}")
            return

        # Stop existing transcoder if any
        self._stop_transcoder(cam_id)

        rtsp_url = build_rtsp_url_from_camera(camera)
        output_url = f"rtsp://127.0.0.1:8554/{cam_id}"

        cmd = [
            str(FFMPEG_EXE),
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-vf", "scale=1280:-2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "1500k",
            "-maxrate", "2000k",
            "-bufsize", "3000k",
            "-g", "50",
            "-an",
            "-f", "rtsp",
            output_url,
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            self._transcoders[cam_id] = proc
            logger.info(
                f"Transcoder started for {cam_id} (PID: {proc.pid}) "
                f"H.265 -> H.264"
            )
        except Exception as e:
            logger.error(f"Failed to start transcoder for {cam_id}: {e}")

    def _stop_transcoder(self, cam_id: str):
        """Stop an ffmpeg transcoder process."""
        proc = self._transcoders.pop(cam_id, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info(f"Transcoder stopped for {cam_id}")

    def _stop_all_transcoders(self):
        """Stop all ffmpeg transcoder processes."""
        for cam_id in list(self._transcoders.keys()):
            self._stop_transcoder(cam_id)

    def _start_all_transcoders(self):
        """Start transcoders for all H.265 cameras."""
        for cam_id, camera in self._cameras.items():
            if self._needs_transcode(camera):
                self._start_transcoder(cam_id, camera)

    def start(self):
        """Start MediaMTX process and all transcoders."""
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

            # Wait for MediaMTX to be ready
            time.sleep(2)

            # Start all transcoders
            self._start_all_transcoders()

        except Exception as e:
            logger.error(f"Failed to start MediaMTX: {e}")

    def stop(self):
        """Stop MediaMTX process and all transcoders."""
        self._stop_all_transcoders()

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

    def set_cameras(self, cameras: list[CameraModel]):
        """Set all cameras at once (for startup). Does NOT restart."""
        self._cameras = {cam.id: cam for cam in cameras if cam.enabled}
        logger.info(f"MediaMTX: {len(self._cameras)} cameras configured")

    def add_camera(self, camera: CameraModel):
        """Add a single camera and restart if running."""
        self._cameras[camera.id] = camera
        if self.is_running():
            self.restart()

    def remove_camera(self, camera_id: str):
        """Remove a camera and restart if running."""
        self._cameras.pop(camera_id, None)
        self._stop_transcoder(camera_id)
        if self.is_running():
            self.restart()

    def check_transcoders(self):
        """Check if any transcoder died and restart it."""
        for cam_id, camera in self._cameras.items():
            if not self._needs_transcode(camera):
                continue
            proc = self._transcoders.get(cam_id)
            if proc is None or proc.poll() is not None:
                logger.warning(f"Transcoder for {cam_id} died, restarting...")
                self._start_transcoder(cam_id, camera)

    def get_webrtc_url(self, camera_id: str, request_host: str = "localhost") -> str:
        """Get WebRTC URL for a camera, adjusted for the requesting host."""
        config = load_config()
        port = config.system.mediamtx_webrtc_port
        host = request_host.split(":")[0]
        return f"http://{host}:{port}/{camera_id}/whep"

    def get_hls_url(self, camera_id: str, request_host: str = "localhost") -> str:
        """Get HLS URL for a camera."""
        host = request_host.split(":")[0]
        return f"http://{host}:8888/{camera_id}/index.m3u8"
