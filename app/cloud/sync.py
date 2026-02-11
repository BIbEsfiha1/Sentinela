"""Cloud sync management with rclone (Google Drive primary)."""

import subprocess
import sys
import os
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from ..models import CloudSettings, CloudProvider
from ..config import load_config, BASE_DIR

logger = logging.getLogger(__name__)

RCLONE_EXE = BASE_DIR / "tools" / "rclone" / "rclone.exe"


class CloudSyncManager:
    """Manages periodic cloud sync via rclone."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._running = False
        self._syncing = False
        self._last_sync: str | None = None
        self._last_error: str | None = None
        self._next_sync: float = 0
        
        # Setup state
        self._setup_thread: threading.Thread | None = None
        self._setup_status = "idle"  # idle, waiting_auth, success, error
        self._setup_auth_url: str | None = None
        self._setup_error: str | None = None
        self._setup_process: subprocess.Popen | None = None

    def start(self):
        """Start periodic sync thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info("Cloud sync started")

    def stop(self):
        """Stop sync thread."""
        self._running = False
        logger.info("Cloud sync stopped")

    def sync_now(self):
        """Trigger immediate sync."""
        self._next_sync = 0

    def _sync_loop(self):
        """Background loop that syncs periodically."""
        while self._running:
            config = load_config()
            if not config.cloud.enabled:
                time.sleep(30)
                continue

            interval = config.cloud.sync_interval_minutes * 60

            if time.time() >= self._next_sync:
                self._do_sync(config.cloud)
                self._next_sync = time.time() + interval

            time.sleep(10)

    def _do_sync(self, cloud: CloudSettings):
        """Execute rclone copy."""
        if not RCLONE_EXE.exists():
            self._last_error = "rclone nao encontrado. Execute setup.bat."
            logger.error(self._last_error)
            return

        config = load_config()
        rec_path = BASE_DIR / config.recording.recordings_path

        if not rec_path.exists():
            return

        self._syncing = True
        self._last_error = None

        remote = f"{cloud.remote_name}:{cloud.remote_path}"

        cmd = [
            str(RCLONE_EXE),
            "copy",
            str(rec_path),
            remote,
            "--min-age", "2m",
            "--bwlimit", cloud.bandwidth_limit,
            "--log-level", "INFO",
            "--stats", "0",
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            logger.info(f"Cloud sync starting: {rec_path} -> {remote}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                self._last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"Cloud sync complete at {self._last_sync}")
            else:
                self._last_error = result.stderr[:200] if result.stderr else "Unknown error"
                logger.error(f"Cloud sync failed: {self._last_error}")
        except subprocess.TimeoutExpired:
            self._last_error = "Sync timeout (1h)"
            logger.error(self._last_error)
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Cloud sync error: {e}")
        finally:
            self._syncing = False

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "syncing": self._syncing,
            "last_sync": self._last_sync,
            "error": self._last_error,
        }

    def is_configured(self) -> bool:
        """Check if rclone remote is configured."""
        if not RCLONE_EXE.exists():
            return False
        config = load_config()
        try:
            result = subprocess.run(
                [str(RCLONE_EXE), "listremotes"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception:
            return False

    def start_setup(self, cloud: CloudSettings):
        """Start the async setup process."""
        if self._setup_thread and self._setup_thread.is_alive():
            return
        
        self._setup_status = "starting"
        self._setup_auth_url = None
        self._setup_error = None
        self._setup_thread = threading.Thread(target=self._run_setup, args=(cloud,), daemon=True)
        self._setup_thread.start()

    def get_setup_status(self) -> dict:
        """Get current status of the setup process."""
        return {
            "status": self._setup_status,
            "auth_url": self._setup_auth_url,
            "error": self._setup_error
        }
    
    def cancel_setup(self):
        """Cancel any running setup."""
        if self._setup_process:
            self._setup_process.terminate()
            self._setup_process = None
        self._setup_status = "cancelled"


    def _run_setup(self, cloud: CloudSettings):
        """Background thread for rclone config."""
        import asyncio
        import re

        if not RCLONE_EXE.exists():
            self._setup_status = "error"
            self._setup_error = "rclone nao encontrado"
            return

        provider_map = {
            CloudProvider.GDRIVE: "drive",
            CloudProvider.ONEDRIVE: "onedrive",
            CloudProvider.DROPBOX: "dropbox",
            CloudProvider.S3: "s3",
        }

        provider_type = provider_map.get(cloud.provider)
        if not provider_type:
             self._setup_status = "error"
             self._setup_error = "Provedor nao suportado"
             return

        cmd = [
            str(RCLONE_EXE), "config", "create",
            cloud.remote_name, provider_type,
        ]

        try:
            self._setup_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            timeout = 300 # 5 min
            start_time = time.time()
            
            self._setup_status = "waiting_auth"

            while True:
                if time.time() - start_time > timeout:
                    self._setup_process.terminate()
                    self._setup_status = "error"
                    self._setup_error = "Tempo limite excedido"
                    return

                retcode = self._setup_process.poll()
                line = self._setup_process.stdout.readline()
                
                if line:
                    logger.debug(f"Setup Rclone: {line.strip()}")
                    # Detect Auth URL
                    if "http://127.0.0.1" in line and "/auth" in line and not self._setup_auth_url:
                        match = re.search(r'(http://127\.0\.0\.1:\d+/auth\?state=\S+)', line)
                        if match:
                            self._setup_auth_url = match.group(1)
                            logger.info(f"Auth URL detected: {self._setup_auth_url}")

                if retcode is not None and not line:
                    break
            
            if retcode == 0:
                self._setup_status = "success"
            else:
                self._setup_status = "error"
                self._setup_error = "Falha no processo rclone"

        except Exception as e:
            self._setup_status = "error"
            self._setup_error = str(e)
        finally:
            self._setup_process = None


async def setup_rclone_remote(cloud: CloudSettings) -> dict:
    """Launch rclone config for the provider."""
    import asyncio
    import webbrowser
    import re

    if not RCLONE_EXE.exists():
        return {"ok": False, "error": "rclone nao encontrado. Execute setup.bat."}

    provider_map = {
        CloudProvider.GDRIVE: "drive",
        CloudProvider.ONEDRIVE: "onedrive",
        CloudProvider.DROPBOX: "dropbox",
        CloudProvider.S3: "s3",
    }

    provider_type = provider_map.get(cloud.provider)
    if not provider_type:
        return {"ok": False, "error": "Provedor nao suportado"}

    # Use rclone authorize flow - opens browser automatically
    try:
        cmd = [
            str(RCLONE_EXE), "config", "create",
            cloud.remote_name, provider_type,
        ]

        def _interactive_run():
            # Use Popen to read stdout/stderr in real-time
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,
                universal_newlines=True,
                # On Windows, we refrain from creating a new window but we need IO
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            auth_url_found = False
            output_lines = []
            
            # 3-minute timeout for user to authorize
            timeout = 180
            start_time = time.time()
            final_retcode = None

            while True:
                # Check for timeout
                if time.time() - start_time > timeout:
                    process.terminate()
                    return {"ok": False, "error": "Timeout aguardando autorizacao (3min)."}

                # Check if process ended
                retcode = process.poll()
                if retcode is not None:
                    final_retcode = retcode
                    # Read any remaining output
                    rest = process.stdout.read()
                    if rest:
                        output_lines.append(rest)
                    break
                
                # Consume available output without blocking too much
                line = process.stdout.readline()
                if line:
                    stripped = line.strip()
                    output_lines.append(stripped)
                    # logger.info(f"rclone: {stripped}")
                    
                    # Detect Auth URL
                    if "http://127.0.0.1" in line and "/auth" in line and not auth_url_found:
                        # Use \S+ to match any non-whitespace character for the state param
                        match = re.search(r'(http://127\.0\.0\.1:\d+/auth\?state=\S+)', line)
                        if match:
                            url = match.group(1)
                            logger.info(f"ACTION REQUIRED: Please visit this URL to authorize: {url}")
                            try:
                                webbrowser.open(url)
                            except Exception as e:
                                logger.error(f"Failed to open browser: {e}")
                            auth_url_found = True

            if final_retcode == 0:
                return {"ok": True, "message": "Remoto configurado com sucesso!"}
            else:
                return {"ok": False, "error": "\n".join(output_lines[-10:])}

        return await asyncio.to_thread(_interactive_run)

    except Exception as e:
        logger.error(f"Rclone setup error: {e}")
        return {"ok": False, "error": str(e)}
