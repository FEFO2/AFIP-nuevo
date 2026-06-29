from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from playwright.sync_api import Frame, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

from utils import (
    browser_mode_label,
    configure_logging,
    ensure_downloads_dir,
    pause_for_manual_mode,
    PlaywrightTimeoutConfig,
    get_playwright_timeout_config,
)


logger = logging.getLogger(__name__)
PERIOD_OPTION_INDEX = {
    "current": 0,
    "previous": 1,
}


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing environment variable: {name}")
    return value


def _open_arancia_login(page, url: str, *, timeout_config: PlaywrightTimeoutConfig) -> None:
    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout_config.navigation_timeout_ms,
        )
    except PlaywrightTimeoutError:
        logger.warning(
            "Bookit: la navegacion al portal no completo a tiempo, pero se verificara si el formulario quedo disponible."
        )

    page.locator("#TextBox1").wait_for(state="visible", timeout=timeout_config.action_timeout_ms)


def _select_period_option(
    frame: Frame,
    *,
    period: str,
    timeout_config: PlaywrightTimeoutConfig,
) -> None:
    if period not in PERIOD_OPTION_INDEX:
        raise ValueError(f"Periodo Bookit no soportado: {period}")

    dropdown = frame.locator("#DropDownList1")
    dropdown.wait_for(state="visible", timeout=timeout_config.action_timeout_ms)
    options = dropdown.locator("option")
    option_count = options.count()
    target_index = PERIOD_OPTION_INDEX[period]

    if option_count <= target_index:
        raise ValueError(
            f"Bookit: la lista #DropDownList1 tiene {option_count} opcion(es); "
            f"no alcanza para seleccionar el periodo '{period}'."
        )

    target_option = options.nth(target_index)
    target_value = target_option.get_attribute("value")
    target_label = (target_option.text_content() or "").strip()

    if target_value is None:
        raise ValueError(
            f"Bookit: la opcion en posicion {target_index + 1} no tiene atributo value."
        )

    logger.info(
        "Bookit: seleccionando periodo '%s' con la opcion %s de #DropDownList1 (%s).",
        period,
        target_index + 1,
        target_label or target_value,
    )
    dropdown.select_option(value=target_value)
    frame.page.wait_for_timeout(timeout_config.wait_ms)


def _wait_for_frame(page, name: str, timeout_ms: int) -> Frame:
    deadline = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < deadline:
        frame = page.frame(name=name)
        if frame is not None:
            return frame
        page.wait_for_timeout(200)

    raise TimeoutError(f"No se pudo obtener el iframe '{name}'.")


def _wait_for_child_frame(
    parent_frame: Frame,
    name: str,
    *,
    required_selector: str | None = None,
    timeout_ms: int = 30_000,
) -> Frame:
    deadline = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < deadline:
        for child_frame in parent_frame.child_frames:
            if child_frame.name != name:
                continue

            if required_selector is None:
                return child_frame

            try:
                child_frame.locator(required_selector).wait_for(state="visible", timeout=500)
                return child_frame
            except PlaywrightTimeoutError:
                continue

        parent_frame.page.wait_for_timeout(200)

    raise TimeoutError(f"No se pudo obtener el iframe hijo '{name}'.")


def download_arancia_reports(
    playwright: Playwright,
    *,
    headless: bool = True,
    period: str = "current",
    manual_on_error: bool = False,
    timeout_config: PlaywrightTimeoutConfig | None = None,
) -> tuple[str, str]:
    load_dotenv()
    timeout_config = timeout_config or get_playwright_timeout_config()

    url = _get_required_env("ARANCIA_URL")
    user = _get_required_env("ARANCIA_USERNAME")
    password = _get_required_env("ARANCIA_PASSWORD")
    downloads_dir = ensure_downloads_dir()

    logger.info(
        "Bookit: iniciando automatizacion con navegador %s para el periodo '%s'.",
        browser_mode_label(headless),
        period,
    )
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    context.set_default_timeout(timeout_config.action_timeout_ms)
    context.set_default_navigation_timeout(timeout_config.navigation_timeout_ms)
    page = context.new_page()

    try:
        logger.info("Bookit: abriendo portal e iniciando sesion.")
        _open_arancia_login(page, url, timeout_config=timeout_config)

        if not page.locator("#TextBox1").is_visible():
            enter_button = page.locator("#Button1")
            if enter_button.count():
                enter_button.first.click()

        page.locator("#TextBox1").fill(user)
        page.locator("#TextBox2").fill(password)
        page.locator("#Button1").click()
        page.wait_for_load_state("networkidle")

        if page.locator("#Button10").count():
            page.locator("#Button10").click()
        else:
            page.get_by_role("button", name="Facturacion").click()
        page.wait_for_timeout(timeout_config.wait_ms)
        logger.info("Bookit: modulo de facturacion abierto.")

        frame_facturacion = _wait_for_frame(page, "facturacion", timeout_ms=timeout_config.action_timeout_ms)
        if frame_facturacion.get_by_role("button", name="Afip").count():
            frame_facturacion.get_by_role("button", name="Afip").click()
        else:
            frame_facturacion.locator("#Button7").click()
        page.wait_for_timeout(timeout_config.wait_ms)

        frame_marco = _wait_for_child_frame(
            frame_facturacion,
            "marco",
            required_selector="#DropDownList1",
            timeout_ms=timeout_config.action_timeout_ms,
        )

        _select_period_option(frame_marco, period=period, timeout_config=timeout_config)
        html_outbound = frame_marco.evaluate("() => document.documentElement.outerHTML")

        frame_marco.get_by_role("radio", name="COMPRAS DEL MES").check()
        page.wait_for_timeout(timeout_config.wait_ms * 2)
        html_inbound = frame_marco.evaluate("() => document.documentElement.outerHTML")

        outbound_path = downloads_dir / "outbound.html"
        inbound_path = downloads_dir / "inbound.html"
        outbound_path.write_text(html_outbound, encoding="utf-8")
        inbound_path.write_text(html_inbound, encoding="utf-8")

        print(f"[OK] Bookit: archivos guardados en {outbound_path} y {inbound_path}")
        logger.info("Bookit: archivos guardados en %s y %s", outbound_path, inbound_path)
        return html_outbound, html_inbound
    except Exception as error:
        pause_for_manual_mode(
            enabled=manual_on_error,
            headless=headless,
            system_name="Arancia/Bookit",
            error=error,
        )
        raise
    finally:
        context.close()
        browser.close()
        logger.info("Bookit: navegador cerrado.")


def run_download_arancia_reports(
    *,
    headless: bool = True,
    period: str = "current",
    manual_on_error: bool = False,
    timeout_config: PlaywrightTimeoutConfig | None = None,
) -> tuple[str, str]:
    with sync_playwright() as playwright:
        return download_arancia_reports(
            playwright,
            headless=headless,
            period=period,
            manual_on_error=manual_on_error,
            timeout_config=timeout_config,
        )


def main() -> int:
    configure_logging()
    run_download_arancia_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
