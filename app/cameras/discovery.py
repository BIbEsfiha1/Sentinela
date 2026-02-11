"""Camera auto-discovery: WS-Discovery + port scanning."""

import asyncio
import socket
import logging
from typing import Optional
from ..models import DiscoveredCamera

logger = logging.getLogger(__name__)

# Common camera ports
CAMERA_PORTS = [554, 8554, 8899, 37777, 34567, 80, 8080]


def get_local_subnet() -> Optional[str]:
    """Get local IP and derive /24 subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split(".")
        logger.info(f"Local IP: {ip}, scanning subnet {parts[0]}.{parts[1]}.{parts[2]}.0/24")
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception as e:
        logger.error(f"Failed to detect local subnet: {e}")
        return None


def get_local_ip() -> Optional[str]:
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


async def scan_port(ip: str, port: int, timeout: float = 0.5) -> bool:
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


def guess_brand(open_ports: list[int]) -> str:
    """Guess camera brand based on open ports."""
    port_set = set(open_ports)
    if 37777 in port_set or 34567 in port_set:
        return "Intelbras/Dahua"
    if 8899 in port_set:
        return "Intelbras/HiSilicon"
    if 554 in port_set and 80 in port_set:
        return "ONVIF/Generica"
    if 8554 in port_set:
        return "MediaMTX/Generica"
    return "Desconhecida"


async def scan_subnet(subnet: str, ports: list[int] = None) -> list[DiscoveredCamera]:
    """Scan /24 subnet for cameras on common ports."""
    if ports is None:
        ports = CAMERA_PORTS
    
    local_ip = get_local_ip()
    found = []
    ip_ports: dict[str, list[int]] = {}  # Track all open ports per IP

    # Build all tasks
    async def check(ip: str, port: int):
        ok = await scan_port(ip, port)
        return ip, port, ok

    tasks = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        if ip == local_ip:
            continue  # Skip self
        for port in ports:
            tasks.append(check(ip, port))

    logger.info(f"Starting subnet scan: {len(tasks)} checks on {subnet}.0/24")

    # Run ALL tasks concurrently (faster)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            continue
        ip, port, ok = result
        if ok:
            if ip not in ip_ports:
                ip_ports[ip] = []
            ip_ports[ip].append(port)

    # Build camera list from found IPs
    for ip, open_ports in ip_ports.items():
        # Skip routers/gateways that only have port 80 open
        if open_ports == [80] or open_ports == [8080]:
            # Check if this is likely a router (x.x.x.1)
            if ip.endswith(".1"):
                continue
        
        # Pick the best RTSP port  
        rtsp_port = 554
        if 554 in open_ports:
            rtsp_port = 554
        elif 8554 in open_ports:
            rtsp_port = 8554
        elif 8899 in open_ports:
            rtsp_port = 8899
        elif open_ports:
            rtsp_port = open_ports[0]

        brand = guess_brand(open_ports)
        name = f"{brand} ({ip.split('.')[-1]})"

        found.append(DiscoveredCamera(
            ip=ip, port=rtsp_port, source="scan",
            name=name,
        ))
        logger.info(f"Found device at {ip} - ports: {open_ports} - brand: {brand}")

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
                logger.info(f"ONVIF camera found: {cam.ip}")
    except Exception as e:
        logger.warning(f"ONVIF discovery failed: {e}")

    # Port scan
    subnet = get_local_subnet()
    if subnet:
        try:
            scan_cameras = await scan_subnet(subnet)
            for cam in scan_cameras:
                if cam.ip not in seen_ips:
                    seen_ips.add(cam.ip)
                    all_cameras.append(cam)
                else:
                    # Update existing with scan info if ONVIF found it first
                    for existing in all_cameras:
                        if existing.ip == cam.ip and existing.source == "onvif":
                            existing.name = cam.name  # Use the brand-detected name
        except Exception as e:
            logger.warning(f"Port scan failed: {e}")
    else:
        logger.error("Could not determine local subnet. No cameras can be discovered.")

    logger.info(f"Discovery complete: {len(all_cameras)} cameras found")
    return all_cameras
