"""REST API routes."""

import os
import time
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..models import (
    CameraAdd, CameraUpdate, CameraModel, CameraStatus,
    RecordingSettings, CloudSettings, TunnelSettings, SystemSettings,
    SystemStatus, DiscoveredCamera,
)
from ..config import (
    load_config, save_config, get_camera, add_camera,
    remove_camera, update_camera, next_camera_id, BASE_DIR,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

START_TIME = time.time()


# ─── System ───────────────────────────────────────────────────────────

@router.get("/status")
async def system_status():
    import psutil
    config = load_config()
    rec_path = BASE_DIR / config.recording.recordings_path

    rec_size = 0
    if rec_path.exists():
        for f in rec_path.rglob("*"):
            if f.is_file():
                rec_size += f.stat().st_size

    disk = psutil.disk_usage(str(BASE_DIR))
    tunnel_url = None
    tunnel_active = False
    if hasattr(router, "app") and hasattr(router.app, "state"):
        tunnel_mgr = getattr(router.app.state, "tunnel_manager", None)
        if tunnel_mgr:
            tunnel_active = tunnel_mgr.is_running()
            tunnel_url = tunnel_mgr.public_url

    recording_count = 0
    online_count = 0
    for cam in config.cameras:
        if cam.status == CameraStatus.RECORDING:
            recording_count += 1
        if cam.status in (CameraStatus.ONLINE, CameraStatus.RECORDING):
            online_count += 1

    return SystemStatus(
        cameras_total=len(config.cameras),
        cameras_recording=recording_count,
        cameras_online=online_count,
        disk_total_gb=round(disk.total / (1024**3), 1),
        disk_used_gb=round(disk.used / (1024**3), 1),
        disk_free_gb=round(disk.free / (1024**3), 1),
        recordings_size_gb=round(rec_size / (1024**3), 2),
        cpu_percent=psutil.cpu_percent(interval=0.1),
        ram_percent=psutil.virtual_memory().percent,
        cloud_connected=config.cloud.enabled,
        tunnel_active=tunnel_active,
        tunnel_url=tunnel_url,
        uptime_seconds=int(time.time() - START_TIME),
    )


# ─── Cameras ──────────────────────────────────────────────────────────

@router.get("/cameras")
async def list_cameras():
    config = load_config()
    return config.cameras


@router.post("/cameras")
async def create_camera(data: CameraAdd):
    config = load_config()
    cam_id = next_camera_id(config)
    camera = CameraModel(id=cam_id, **data.model_dump())
    add_camera(config, camera)

    # Start recording if recorder is available
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("recorder"):
        state["recorder"].start_camera(camera)
    if state and state.get("mediamtx"):
        state["mediamtx"].add_camera(camera)

    return camera


@router.put("/cameras/{camera_id}")
async def edit_camera(camera_id: str, data: CameraUpdate):
    config = load_config()
    cam = get_camera(config, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    update_camera(config, camera_id, data.model_dump(exclude_unset=True))
    return get_camera(load_config(), camera_id)


@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    config = load_config()
    cam = get_camera(config, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")

    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("recorder"):
        state["recorder"].stop_camera(camera_id)
    if state and state.get("mediamtx"):
        state["mediamtx"].remove_camera(camera_id)

    remove_camera(config, camera_id)
    return {"ok": True}


@router.post("/cameras/{camera_id}/toggle")
async def toggle_camera(camera_id: str):
    config = load_config()
    cam = get_camera(config, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    update_camera(config, camera_id, {"enabled": not cam.enabled})

    from ..server import get_app_state
    state = get_app_state()
    updated = get_camera(load_config(), camera_id)
    if updated.enabled:
        if state and state.get("recorder"):
            state["recorder"].start_camera(updated)
    else:
        if state and state.get("recorder"):
            state["recorder"].stop_camera(camera_id)

    return updated


# ─── Discovery ────────────────────────────────────────────────────────

@router.post("/discover")
async def discover_cameras():
    from ..cameras.discovery import discover
    config = load_config()
    existing_ips = {c.ip for c in config.cameras}
    found = await discover()
    for cam in found:
        cam.already_added = cam.ip in existing_ips
    return found


@router.post("/test-camera")
async def test_camera(data: CameraAdd):
    from ..cameras.rtsp import build_rtsp_url, test_rtsp
    url = build_rtsp_url(data.ip, data.port, data.username, data.password, data.channel, data.stream)
    ok = await test_rtsp(url)
    return {"ok": ok, "url": url}


# ─── Recordings ───────────────────────────────────────────────────────

@router.get("/recordings/dates")
async def recording_dates():
    config = load_config()
    rec_path = BASE_DIR / config.recording.recordings_path
    dates = []
    if rec_path.exists():
        for d in sorted(rec_path.iterdir(), reverse=True):
            if d.is_dir() and len(d.name) == 10:
                dates.append(d.name)
    return dates


@router.get("/recordings/{date}")
async def recording_cameras(date: str):
    config = load_config()
    rec_path = BASE_DIR / config.recording.recordings_path / date
    if not rec_path.exists():
        return []
    cameras = []
    for d in sorted(rec_path.iterdir()):
        if d.is_dir():
            files = []
            for f in sorted(d.iterdir()):
                if f.suffix == ".mp4":
                    files.append({
                        "name": f.name,
                        "size_mb": round(f.stat().st_size / (1024**2), 1),
                        "path": f"recordings/{date}/{d.name}/{f.name}",
                    })
            cam_config = get_camera(config, d.name)
            cameras.append({
                "id": d.name,
                "name": cam_config.name if cam_config else d.name,
                "files": files,
            })
    return cameras


@router.get("/recordings/play/{date}/{camera_id}/{filename}")
async def play_recording(date: str, camera_id: str, filename: str):
    # Sanitize path components
    for part in (date, camera_id, filename):
        if ".." in part or "/" in part or "\\" in part:
            raise HTTPException(400, "Invalid path")
    config = load_config()
    rec_dir = (BASE_DIR / config.recording.recordings_path).resolve()
    file_path = (rec_dir / date / camera_id / filename).resolve()
    # Ensure resolved path is inside recordings directory
    if not str(file_path).startswith(str(rec_dir)):
        raise HTTPException(400, "Invalid path")
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path), media_type="video/mp4")


# ─── Settings ─────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    config = load_config()
    return {
        "system": config.system.model_dump(),
        "recording": config.recording.model_dump(),
        "cloud": config.cloud.model_dump(),
        "tunnel": config.tunnel.model_dump(),
    }


@router.put("/settings/system")
async def update_system_settings(data: SystemSettings):
    config = load_config()
    config.system = data
    save_config(config)
    return config.system


@router.put("/settings/recording")
async def update_recording_settings(data: RecordingSettings):
    config = load_config()
    config.recording = data
    save_config(config)
    return config.recording


@router.put("/settings/cloud")
async def update_cloud_settings(data: CloudSettings):
    config = load_config()
    config.cloud = data
    save_config(config)
    return config.cloud


@router.put("/settings/tunnel")
async def update_tunnel_settings(data: TunnelSettings):
    config = load_config()
    config.tunnel = data
    save_config(config)

    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("tunnel"):
        tunnel = state["tunnel"]
        if data.mode == "disabled":
            tunnel.stop()
        else:
            tunnel.stop()
            tunnel.start(data.mode, data.hostname)

    return config.tunnel


@router.post("/wizard/complete")
async def wizard_complete():
    config = load_config()
    config.system.first_run = False
    save_config(config)
    return {"ok": True}


# ─── Cloud ────────────────────────────────────────────────────────────

@router.post("/cloud/sync")
async def trigger_cloud_sync():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("cloud_sync"):
        state["cloud_sync"].sync_now()
        return {"ok": True}
    raise HTTPException(400, "Cloud sync not configured")


@router.get("/cloud/status")
async def cloud_sync_status():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("cloud_sync"):
        return state["cloud_sync"].get_status()
    return {"running": False, "last_sync": None, "error": None}


@router.post("/cloud/setup")
async def cloud_setup():
    from ..cloud.sync import setup_rclone_remote
    config = load_config()
    result = await setup_rclone_remote(config.cloud)
    return result


# ─── Tunnel ───────────────────────────────────────────────────────────

@router.get("/tunnel/status")
async def tunnel_status():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("tunnel"):
        t = state["tunnel"]
        return {
            "active": t.is_running(),
            "url": t.public_url,
            "mode": t.mode,
        }
    return {"active": False, "url": None, "mode": "disabled"}


@router.post("/tunnel/start")
async def tunnel_start():
    config = load_config()
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("tunnel"):
        t = state["tunnel"]
        t.start(config.tunnel.mode or "quick", config.tunnel.hostname)
        return {"ok": True, "url": t.public_url}
    raise HTTPException(400, "Tunnel manager not available")


@router.post("/tunnel/stop")
async def tunnel_stop():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("tunnel"):
        state["tunnel"].stop()
        return {"ok": True}
    raise HTTPException(400, "Tunnel manager not available")
