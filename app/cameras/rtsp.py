"""RTSP URL builder and tester for iCSee cameras."""

import asyncio
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)


def build_rtsp_url(ip: str, port: int = 554, username: str = "admin",
                   password: str = "12345678", channel: int = 1,
                   stream: int = 0) -> str:
    """Build iCSee RTSP URL.

    stream: 0 = main (high quality), 1 = sub (low quality)
    """
    return (
        f"rtsp://{ip}:{port}/user={username}&password={password}"
        f"&channel={channel}&stream={stream}.sdp?real_stream"
    )


def build_rtsp_url_from_camera(camera) -> str:
    """Build RTSP URL from a CameraModel."""
    return build_rtsp_url(
        camera.ip, camera.port, camera.username,
        camera.password, camera.channel, camera.stream,
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
