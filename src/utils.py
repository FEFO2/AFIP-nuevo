from __future__ import annotations

from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


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
