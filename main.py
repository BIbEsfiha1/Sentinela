"""Sentinela - Sistema de Gravacao de Cameras IP"""

import sys
import os
import logging
import webbrowser
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def setup_logging():
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    handler = RotatingFileHandler(
        logs_dir / "sentinela.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(console)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def open_browser(port: int):
    """Open browser after a short delay."""
    import time
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


def main():
    setup_logging()
    logger = logging.getLogger("sentinela")

    # Ensure we're in the right directory
    os.chdir(BASE_DIR)

    from app.config import load_config
    config = load_config()
    port = config.system.web_port

    logger.info(f"Sentinela v1.0 - Starting on port {port}")

    # Open browser in background
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    import uvicorn
    from app.server import create_app

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
