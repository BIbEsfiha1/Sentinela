"""Cloudflare Tunnel management for remote access."""

import subprocess
import sys
import os
import re
import logging
import threading
import time
from pathlib import Path
from ..config import load_config, save_config, BASE_DIR

logger = logging.getLogger(__name__)

CLOUDFLARED_EXE = BASE_DIR / "tools" / "cloudflared" / "cloudflared.exe"


class TunnelManager:
    """Manages cloudflared process for remote access."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self.public_url: str | None = None
        self.mode: str = "disabled"
        self._running = False

    def start(self, mode: str = "quick", hostname: str | None = None):
        """Start cloudflared tunnel.

        Args:
            mode: "quick" for temporary URL, "named" for permanent hostname
            hostname: Required for named mode (e.g., sentinela.example.com)
        """
        if not CLOUDFLARED_EXE.exists():
            logger.warning(f"cloudflared not found at {CLOUDFLARED_EXE}. Run setup.bat.")
            return

        if self._running:
            self.stop()

        self.mode = mode
        config = load_config()
        port = config.system.web_port

        if mode == "quick":
            cmd = [
                str(CLOUDFLARED_EXE),
                "tunnel", "--url", f"http://localhost:{port}",
            ]
        elif mode == "named" and hostname:
            cmd = [
                str(CLOUDFLARED_EXE),
                "tunnel", "run",
                "--url", f"http://localhost:{port}",
            ]
        else:
            logger.error(f"Invalid tunnel mode: {mode}")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_tunnel, args=(cmd,), daemon=True,
        )
        self._thread.start()
        logger.info(f"Tunnel starting in {mode} mode...")

    def _run_tunnel(self, cmd: list[str]):
        """Run cloudflared process and capture public URL."""
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )

            # Read output to find the public URL
            for line in iter(self._process.stdout.readline, ''):
                if not self._running:
                    break

                # Quick tunnel outputs URL like: https://xxx-xxx-xxx.trycloudflare.com
                url_match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', line)
                if url_match:
                    self.public_url = url_match.group(1)
                    logger.info(f"Tunnel active: {self.public_url}")

                    # Save URL to config
                    config = load_config()
                    config.tunnel.public_url = self.public_url
                    save_config(config)

                # Also check for generic https URLs (named tunnels)
                if not self.public_url:
                    url_match = re.search(r'(https://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', line)
                    if url_match and 'trycloudflare' not in line:
                        self.public_url = url_match.group(1)
                        logger.info(f"Tunnel active: {self.public_url}")

            self._process.wait()
        except Exception as e:
            logger.error(f"Tunnel error: {e}")
        finally:
            self._running = False
            self.public_url = None

    def stop(self):
        """Stop cloudflared process."""
        self._running = False
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self.public_url = None
        self.mode = "disabled"
        logger.info("Tunnel stopped.")

    def is_running(self) -> bool:
        return self._running and self._process is not None and self._process.poll() is None

    def restart(self):
        """Restart the tunnel."""
        mode = self.mode
        config = load_config()
        hostname = config.tunnel.hostname
        self.stop()
        time.sleep(2)
        self.start(mode, hostname)
