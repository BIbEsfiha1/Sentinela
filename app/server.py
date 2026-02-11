"""FastAPI application and lifecycle management."""

import logging
import asyncio
import signal
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .config import load_config, save_config, BASE_DIR

logger = logging.getLogger(__name__)

_app_state: dict = {}


def get_app_state() -> dict:
    return _app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of all subsystems."""
    config = load_config()
    logger.info("Sentinela starting...")

    # Ensure directories exist
    (BASE_DIR / config.recording.recordings_path).mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    # Start MediaMTX
    try:
        from .streaming.mediamtx import MediaMTXManager
        mediamtx = MediaMTXManager()
        mediamtx.start()
        _app_state["mediamtx"] = mediamtx
        logger.info("MediaMTX started.")
    except Exception as e:
        logger.warning(f"MediaMTX not available: {e}")

    # Start recorder for enabled cameras
    try:
        from .recording.recorder import RecorderManager
        recorder = RecorderManager()
        _app_state["recorder"] = recorder
        for cam in config.cameras:
            if cam.enabled:
                recorder.start_camera(cam)
                # Register with MediaMTX
                if "mediamtx" in _app_state:
                    _app_state["mediamtx"].add_camera(cam)
        logger.info(f"Recorder started for {len([c for c in config.cameras if c.enabled])} cameras.")
    except Exception as e:
        logger.warning(f"Recorder not available: {e}")

    # Start cloud sync
    try:
        from .cloud.sync import CloudSyncManager
        cloud_sync = CloudSyncManager()
        if config.cloud.enabled:
            cloud_sync.start()
        _app_state["cloud_sync"] = cloud_sync
        logger.info("Cloud sync ready.")
    except Exception as e:
        logger.warning(f"Cloud sync not available: {e}")

    # Start tunnel
    try:
        from .tunnel.cloudflare import TunnelManager
        tunnel = TunnelManager()
        _app_state["tunnel"] = tunnel
        if config.tunnel.mode != "disabled":
            tunnel.start(config.tunnel.mode, config.tunnel.hostname)
        logger.info("Tunnel manager ready.")
    except Exception as e:
        logger.warning(f"Tunnel not available: {e}")

    # Start watchdog
    try:
        from .watchdog.health import WatchdogManager
        watchdog = WatchdogManager(_app_state)
        watchdog.start()
        _app_state["watchdog"] = watchdog
        logger.info("Watchdog started.")
    except Exception as e:
        logger.warning(f"Watchdog not available: {e}")

    logger.info(f"Sentinela running on http://0.0.0.0:{config.system.web_port}")
    yield

    # Shutdown
    logger.info("Sentinela shutting down...")
    if "watchdog" in _app_state:
        _app_state["watchdog"].stop()
    if "tunnel" in _app_state:
        _app_state["tunnel"].stop()
    if "cloud_sync" in _app_state:
        _app_state["cloud_sync"].stop()
    if "recorder" in _app_state:
        _app_state["recorder"].stop_all()
    if "mediamtx" in _app_state:
        _app_state["mediamtx"].stop()
    logger.info("Sentinela stopped.")


def create_app() -> FastAPI:
    app = FastAPI(title="Sentinela", version="1.0.0", lifespan=lifespan)

    # Templates
    templates_dir = BASE_DIR / "templates"
    app.state.templates = Jinja2Templates(directory=str(templates_dir))

    # Static files
    static_dir = BASE_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Serve recordings for playback
    rec_dir = BASE_DIR / "recordings"
    rec_dir.mkdir(exist_ok=True)

    # Routes
    from .web.routes import router as web_router
    from .web.api_routes import router as api_router
    app.include_router(api_router)
    app.include_router(web_router)

    return app
