"""REST API routes."""

import os
import time
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response, Request
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

    # Check for duplicate IP
    existing = [c for c in config.cameras if c.ip == data.ip]
    if existing:
        names = ", ".join(f'"{c.name}" ({c.id})' for c in existing)
        raise HTTPException(
            status_code=409,
            detail=f"Ja existe camera com IP {data.ip}: {names}. "
                   f"Remova a existente ou use um IP diferente.",
        )

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
    from ..cameras.rtsp import build_rtsp_url, test_rtsp, auto_detect_brand
    
    brand = getattr(data, "brand", "auto") or "auto"
    
    if brand == "auto":
        # Try all known formats
        result = await auto_detect_brand(
            data.ip, data.port, data.username, data.password,
            data.channel, data.stream,
        )
        if result:
            return {"ok": True, "brand": result["brand"], "url": result["url"]}
        else:
            return {"ok": False, "brand": None, "error": "Nenhum formato RTSP funcionou. Verifique usuario/senha da camera."}
    else:
        url = build_rtsp_url(data.ip, data.port, data.username, data.password, data.channel, data.stream, brand=brand)
        ok = await test_rtsp(url)
        return {"ok": ok, "brand": brand, "url": url}


@router.get("/tools/qr")
async def generate_qr(text: str):
    """Generate generic QR Code."""
    import qrcode
    from io import BytesIO
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return Response(content=buf.getvalue(), media_type="image/png")


# ─── Recordings ───────────────────────────────────────────────────────
    return Response(content=buf.getvalue(), media_type="image/png")


# ─── Bluetooth Tools ──────────────────────────────────────────────────

@router.get("/tools/ble/scan")
async def scan_ble_devices():
    """Scan for BLE devices (specifically cameras)."""
    try:
        from bleak import BleakScanner
        print("Starting BLE scan...")
        devices = await BleakScanner.discover(timeout=4.0, return_adv=True)
        
        results = []
        # Support Bleak < 0.19 and >= 0.19
        iter_devices = devices.values() if isinstance(devices, dict) else devices
        
        for d, adv in iter_devices:
            # Filter weak signals
            if adv.rssi < -85: continue
            
            name = d.name or "Unknown"
            is_camera = "XM" in name or "IPC" in name or "Robot" in name
            
            results.append({
                "address": d.address,
                "name": name,
                "rssi": adv.rssi,
                "is_likely_camera": is_camera
            })
            
        # Sort by signal strength
        results.sort(key=lambda x: x["rssi"], reverse=True)
        return results
    except ImportError:
        return {"error": "Biblioteca 'bleak' nao instalada. Bluetooth nao disponivel."}
    except Exception as e:
        logger.error(f"BLE Scan error: {e}")
        return {"error": str(e)}

@router.post("/tools/ble/configure")
async def configure_ble_device(address: str, ssid: str, password: str):
    """Connect to BLE device and send Wi-Fi credentials."""
    try:
        from bleak import BleakClient
        import json
        import random
        
        print(f"Connecting to BLE {address}...")
        async with BleakClient(address, timeout=15.0) as client:
            # Find writable characteristic
            write_char = None
            
            for service in client.services:
                for char in service.characteristics:
                    props = ",".join(char.properties).lower()
                    if "write" in props:
                        uuid_s = str(char.uuid).lower()
                        # Prioritize XM/iCSee service (FFE1 or 2B11)
                        if "ffe1" in uuid_s or "2b11" in uuid_s:
                            write_char = char
                            break
                        # Fallback: any writable char if no specific one found yet
                        if not write_char:
                            write_char = char
                if write_char and ("ffe1" in str(write_char.uuid).lower() or "2b11" in str(write_char.uuid).lower()):
                    break
            
            if not write_char:
                return {"ok": False, "error": "Nenhuma caracteristica de escrita encontrada no dispositivo."}
                
            # Prepare payload
            payload = json.dumps({
                "s": ssid,
                "p": password,
                "k": str(random.randint(100000, 999999)),
                "t": "WPA"
            })
            
            print(f"Sending BLE payload to {write_char.uuid}: {payload}")
            await client.write_gatt_char(write_char, payload.encode('utf-8'), response=True)
            
            return {"ok": True, "message": "Configuracao enviada! Aguarde a camera conectar."}
            
    except Exception as e:
        logger.error(f"BLE Config error: {e}")
        return {"ok": False, "error": str(e)}
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
    from ..server import get_app_state
    state = get_app_state()
    config = load_config()
    
    if state and state.get("cloud_sync"):
        state["cloud_sync"].start_setup(config.cloud)
        return {"ok": True, "message": "Iniciando configuracao..."}
    
    raise HTTPException(400, "Cloud sync manager not available")


@router.get("/cloud/setup/status")
async def cloud_setup_status():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("cloud_sync"):
        return state["cloud_sync"].get_setup_status()
    return {"status": "error", "error": "Manager not available"}


@router.post("/cloud/setup/cancel")
async def cloud_setup_cancel():
    from ..server import get_app_state
    state = get_app_state()
    if state and state.get("cloud_sync"):
        state["cloud_sync"].cancel_setup()
        return {"ok": True}
    return {"ok": False}


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


# ─── WHEP Proxy (for tunnel/HTTPS access) ─────────────────────────────

@router.post("/whep/{camera_id}")
async def whep_proxy(camera_id: str, request: Request):
    """Proxy WHEP requests to local MediaMTX for tunnel/HTTPS compatibility."""
    import httpx

    config = load_config()
    whep_url = f"http://127.0.0.1:{config.system.mediamtx_webrtc_port}/{camera_id}/whep"

    body = await request.body()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                whep_url,
                content=body,
                headers={"Content-Type": "application/sdp"},
                timeout=10.0,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={
                    "Content-Type": resp.headers.get("Content-Type", "application/sdp"),
                    "Location": resp.headers.get("Location", ""),
                },
            )
    except httpx.ConnectError:
        raise HTTPException(502, "MediaMTX not reachable")
    except httpx.TimeoutException:
        raise HTTPException(504, "MediaMTX timeout")
