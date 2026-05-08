from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright

from utils import browser_mode_label, configure_logging, ensure_downloads_dir


logger = logging.getLogger(__name__)
PERIOD_LABELS = {
    "current": "Este mes",
    "previous": "Mes pasado",
}


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing environment variable: {name}")
    return value


def download_reports(
    playwright: Playwright,
    *,
    headless: bool = True,
    period: str = "current",
) -> None:
    load_dotenv()

    if period not in PERIOD_LABELS:
        raise ValueError(f"Periodo AFIP no soportado: {period}")

    url = _get_required_env("AFIP_URL")
    cuit = _get_required_env("AFIP_USERNAME")
    password = _get_required_env("AFIP_PASSWORD")
    downloads_dir = ensure_downloads_dir()
    period_label = PERIOD_LABELS[period]

    comprobantes = [
        ("#btnRecibidos", "comprobantes_recibidos.xlsx"),
        ("#btnEmitidos", "comprobantes_emitidos.xlsx"),
    ]

    logger.info(
        "AFIP: iniciando automatizacion con navegador %s para el periodo '%s'.",
        browser_mode_label(headless),
        period,
    )
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()

    try:
        logger.info("AFIP: abriendo portal e iniciando sesion.")
        page.goto(url)
        page.get_by_role("spinbutton").click()
        page.get_by_role("spinbutton").fill(cuit)
        page.get_by_role("button", name="Siguiente").click()
        page.get_by_role("textbox", name="TU CLAVE").fill(password)
        page.get_by_role("button", name="Ingresar").click()

        page.get_by_role("link", name="Ver todos").wait_for(state="visible", timeout=30_000)
        page.get_by_role("link", name="Ver todos").click(timeout=30_000)

        with page.expect_popup() as popup_info:
            page.get_by_role("button", name="MIS COMPROBANTES Consulta de").click()
        popup = popup_info.value
        popup.get_by_role("link", name=re.compile("ARANCIA SERVICES")).click()
        logger.info("AFIP: acceso a MIS COMPROBANTES confirmado.")

        for index, (button_id, file_name) in enumerate(comprobantes):
            logger.info("AFIP: preparando descarga de %s.", file_name)
            popup.wait_for_load_state("networkidle")
            button = popup.locator(button_id)
            button.wait_for(state="visible", timeout=30_000)
            button.scroll_into_view_if_needed()
            button.click(force=True)

            popup.wait_for_load_state("networkidle")
            popup.get_by_role("textbox", name="Fecha del Comprobante *").click()
            popup.get_by_text(period_label).click()
            popup.get_by_role("button", name="Buscar").click()

            with popup.expect_download() as download_info:
                popup.get_by_role("button", name="Excel").click()

            download = download_info.value
            target_path = downloads_dir / file_name
            download.save_as(str(target_path))
            print(f"[OK] AFIP: archivo descargado en {target_path}")
            logger.info("AFIP: archivo guardado en %s", target_path)

            if index == 0:
                menu_principal = popup.locator("a[href='menuPrincipal.do']")
                menu_principal.wait_for(state="visible", timeout=30_000)
                menu_principal.click(force=True)
                popup.wait_for_load_state("networkidle")
    finally:
        context.close()
        browser.close()
        logger.info("AFIP: navegador cerrado.")


def run_download_afip_reports(*, headless: bool = True, period: str = "current") -> None:
    with sync_playwright() as playwright:
        download_reports(playwright, headless=headless, period=period)


def main() -> int:
    configure_logging()
    run_download_afip_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
