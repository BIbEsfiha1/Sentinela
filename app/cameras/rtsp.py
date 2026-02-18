"""RTSP URL builder and tester for multiple camera brands."""

import asyncio
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


# ─── URL templates per brand ────────────────────────────────────────────

RTSP_TEMPLATES = {
    "intelbras": "rtsp://{user}:{password}@{ip}:{port}/cam/realmonitor?channel={channel}&subtype={stream}",
    "dahua":     "rtsp://{user}:{password}@{ip}:{port}/cam/realmonitor?channel={channel}&subtype={stream}",
    "hikvision": "rtsp://{user}:{password}@{ip}:{port}/Streaming/Channels/{channel}0{substream}",
    "icsee":     "rtsp://{ip}:{port}/user={user}&password={password}&channel={channel}&stream={stream}.sdp?real_stream",
    "generic":   "rtsp://{user}:{password}@{ip}:{port}/",
    "onvif":     "rtsp://{user}:{password}@{ip}:{port}/onvif1",
}

# All templates to try in order of popularity
AUTO_DETECT_ORDER = ["intelbras", "hikvision", "icsee", "generic", "onvif"]


def build_rtsp_url(ip: str, port: int = 554, username: str = "admin",
                   password: str = "", channel: int = 1,
                   stream: int = 0, brand: str = "auto") -> str:
    """Build RTSP URL for the specified brand.

    stream: 0 = main (high quality), 1 = sub (low quality)
    brand: 'auto', 'intelbras', 'hikvision', 'icsee', 'generic', 'onvif'
    """
    if brand == "auto":
        brand = "intelbras"  # Most common in Brazil

    template = RTSP_TEMPLATES.get(brand, RTSP_TEMPLATES["generic"])

    # Hikvision uses a different channel format
    substream = "1" if stream == 0 else "2"

    return template.format(
        user=username,
        password=password,
        ip=ip,
        port=port,
        channel=channel,
        stream=stream,
        substream=substream,
    )


def build_rtsp_url_from_camera(camera) -> str:
    """Build RTSP URL from a CameraModel."""
    brand = getattr(camera, "brand", "auto") or "auto"
    return build_rtsp_url(
        camera.ip, camera.port, camera.username,
        camera.password, camera.channel, camera.stream,
        brand=brand,
    )


async def test_rtsp(url: str, timeout: int = 5) -> bool:
    """Test if RTSP URL is reachable using FFprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-rtsp_transport", "tcp",
            "-timeout", str(timeout * 1000000),
            "-i", url,
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=creationflags,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout + 2)
            return proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            return False
    except FileNotFoundError:
        logger.error("FFprobe not found. Install FFmpeg.")
        return False
    except Exception as e:
        logger.error(f"RTSP test error: {e}")
        return False


async def auto_detect_brand(ip: str, port: int, username: str, password: str,
                            channel: int = 1, stream: int = 0) -> dict:
    """Try multiple RTSP URL formats to find the one that works.
    
    Returns dict with 'brand' and 'url' if found, or None.
    """
    for brand in AUTO_DETECT_ORDER:
        url = build_rtsp_url(ip, port, username, password, channel, stream, brand=brand)
        logger.debug(f"Testing brand '{brand}': {url}")
        ok = await test_rtsp(url, timeout=3)
        if ok:
            logger.info(f"Auto-detect: Camera {ip} matches brand '{brand}'")
            return {"brand": brand, "url": url}
    
    return None
