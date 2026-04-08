from __future__ import annotations

import logging
from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def browser_mode_label(headless: bool) -> str:
    return "oculto" if headless else "visible"


def ensure_downloads_dir() -> Path:
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    return DOWNLOADS_DIR


def clear_downloads_dir() -> Path:
    downloads_dir = ensure_downloads_dir()

    for child in downloads_dir.iterdir():
        if child.name.startswith("."):
            continue

        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    return downloads_dir
