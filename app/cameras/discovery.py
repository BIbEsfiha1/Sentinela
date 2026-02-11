"""Camera auto-discovery: WS-Discovery + port scanning."""

import asyncio
import socket
import logging
from typing import Optional
from ..models import DiscoveredCamera

logger = logging.getLogger(__name__)


def get_local_subnet() -> Optional[str]:
    """Get local IP and derive /24 subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception:
        return None


async def scan_port(ip: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open on the given IP."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False


async def scan_subnet(subnet: str, ports: list[int] = None) -> list[DiscoveredCamera]:
    """Scan /24 subnet for cameras on RTSP ports."""
    if ports is None:
        ports = [554, 8899]
    found = []
    tasks = []

    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        for port in ports:
            tasks.append((ip, port, scan_port(ip, port)))

    # Run scans in batches to avoid overwhelming the network
    batch_size = 50
    for batch_start in range(0, len(tasks), batch_size):
        batch = tasks[batch_start:batch_start + batch_size]
        results = await asyncio.gather(
            *[t[2] for t in batch],
            return_exceptions=True,
        )
        for (ip, port, _), result in zip(batch, results):
            if result is True:
                # Check if already found this IP
                if not any(c.ip == ip for c in found):
                    found.append(DiscoveredCamera(
                        ip=ip, port=port, source="scan",
                        name=f"Camera {ip.split('.')[-1]}",
                    ))
                    logger.info(f"Found camera at {ip}:{port}")

    return found


async def discover_onvif() -> list[DiscoveredCamera]:
    """Discover cameras via WS-Discovery (ONVIF)."""
    found = []
    try:
        from WSDiscovery import WSDiscovery

        def _discover():
            wsd = WSDiscovery()
            wsd.start()
            services = wsd.searchServices(
                types=["dn:NetworkVideoTransmitter"],
                timeout=5,
            )
            result = []
            for svc in services:
                for xaddr in svc.getXAddrs():
                    # Extract IP from URL like http://192.168.1.100:80/onvif/device_service
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(xaddr)
                        ip = parsed.hostname
                        if ip:
                            result.append(DiscoveredCamera(
                                ip=ip, port=554, source="onvif",
                                name=f"ONVIF {ip}",
                            ))
                    except Exception:
                        pass
            wsd.stop()
            return result

        # Run in executor to avoid blocking
        found = await asyncio.to_thread(_discover)
        # Deduplicate
        seen = set()
        unique = []
        for cam in found:
            if cam.ip not in seen:
                seen.add(cam.ip)
                unique.append(cam)
        found = unique

    except ImportError:
        logger.warning("WSDiscovery not installed. Skipping ONVIF discovery.")
    except Exception as e:
        logger.warning(f"ONVIF discovery error: {e}")

    return found


async def discover() -> list[DiscoveredCamera]:
    """Run all discovery methods and merge results."""
    all_cameras = []
    seen_ips = set()

    # Try ONVIF first
    try:
        onvif_cameras = await discover_onvif()
        for cam in onvif_cameras:
            if cam.ip not in seen_ips:
                seen_ips.add(cam.ip)
                all_cameras.append(cam)
    except Exception as e:
        logger.warning(f"ONVIF discovery failed: {e}")

    # Fallback: port scan
    subnet = get_local_subnet()
    if subnet:
        try:
            scan_cameras = await scan_subnet(subnet)
            for cam in scan_cameras:
                if cam.ip not in seen_ips:
                    seen_ips.add(cam.ip)
                    all_cameras.append(cam)
        except Exception as e:
            logger.warning(f"Port scan failed: {e}")

    logger.info(f"Discovery complete: {len(all_cameras)} cameras found")
    return all_cameras
