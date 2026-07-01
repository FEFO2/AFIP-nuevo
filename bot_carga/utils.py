from __future__ import annotations

import logging
import shutil
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"


@dataclass(frozen=True)
class PlaywrightTimeoutConfig:
    action_timeout_ms: int
    navigation_timeout_ms: int
    wait_ms: int


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


def get_playwright_timeout_config(*, slow_network: bool = False) -> PlaywrightTimeoutConfig:
    if slow_network:
        return PlaywrightTimeoutConfig(
            action_timeout_ms=60_000,
            navigation_timeout_ms=180_000,
            wait_ms=2_000,
        )

    return PlaywrightTimeoutConfig(
        action_timeout_ms=30_000,
        navigation_timeout_ms=90_000,
        wait_ms=1_000,
    )


def pause_for_manual_mode(
    *,
    enabled: bool,
    headless: bool,
    system_name: str,
    error: Exception,
) -> None:
    if not enabled:
        return

    if headless:
        logging.getLogger(__name__).warning(
            "%s: no se puede entrar en modo manual porque el navegador estaba oculto.",
            system_name,
        )
        return

    print(f"\n[MANUAL] {system_name}: la automatizacion se detuvo por este error:")
    print(f"[MANUAL] {error}")
    print("[MANUAL] El navegador queda abierto para que puedas continuar manualmente.")
    print("[MANUAL] Cuando termines, vuelve a esta consola y presiona Enter para cerrar el navegador.")

    try:
        input()
    except EOFError:
        logging.getLogger(__name__).warning(
            "%s: no se pudo esperar confirmacion de consola en modo manual.",
            system_name,
        )


def ensure_downloads_dir() -> Path:
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    return DOWNLOADS_DIR


def clear_downloads_dir(*, names: Collection[str] | None = None) -> Path:
    downloads_dir = ensure_downloads_dir()
    target_names = set(names) if names is not None else None

    for child in downloads_dir.iterdir():
        if child.name.startswith("."):
            continue

        if target_names is not None and child.name not in target_names:
            continue

        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    return downloads_dir

