from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from playwright.sync_api import Frame, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

from utils import ensure_downloads_dir


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing environment variable: {name}")
    return value


def _wait_for_frame(page, name: str, timeout_ms: int = 30_000) -> Frame:
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


def download_arancia_reports(playwright: Playwright, *, headless: bool = True) -> tuple[str, str]:
    load_dotenv()

    url = _get_required_env("ARANCIA_URL")
    user = _get_required_env("ARANCIA_USERNAME")
    password = _get_required_env("ARANCIA_PASSWORD")
    downloads_dir = ensure_downloads_dir()

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto(url)

        if not page.locator("#TextBox1").is_visible():
            enter_button = page.locator("#Button1")
            if enter_button.count():
                enter_button.first.click()

        page.locator("#TextBox1").wait_for(state="visible", timeout=30_000)
        page.locator("#TextBox1").fill(user)
        page.locator("#TextBox2").fill(password)
        page.locator("#Button1").click()
        page.wait_for_load_state("networkidle")

        if page.locator("#Button10").count():
            page.locator("#Button10").click()
        else:
            page.get_by_role("button", name="Facturacion").click()
        page.wait_for_timeout(1_000)

        frame_facturacion = _wait_for_frame(page, "facturacion")
        if frame_facturacion.get_by_role("button", name="Afip").count():
            frame_facturacion.get_by_role("button", name="Afip").click()
        else:
            frame_facturacion.locator("#Button7").click()
        page.wait_for_timeout(1_000)

        frame_marco = _wait_for_child_frame(
            frame_facturacion,
            "marco",
            required_selector="#DropDownList1",
        )

        selected_option = frame_marco.locator("#DropDownList1").locator("option[selected]").get_attribute(
            "value"
        )
        if selected_option:
            frame_marco.locator("#DropDownList1").select_option(selected_option)

        page.wait_for_timeout(1_000)
        html_outbound = frame_marco.evaluate("() => document.documentElement.outerHTML")

        frame_marco.get_by_role("radio", name="COMPRAS DEL MES").check()
        page.wait_for_timeout(2_000)
        html_inbound = frame_marco.evaluate("() => document.documentElement.outerHTML")

        outbound_path = downloads_dir / "outbound.html"
        inbound_path = downloads_dir / "inbound.html"
        outbound_path.write_text(html_outbound, encoding="utf-8")
        inbound_path.write_text(html_inbound, encoding="utf-8")

        print(f"Archivos guardados: {outbound_path.name} e {inbound_path.name}")
        return html_outbound, html_inbound
    finally:
        context.close()
        browser.close()


def run_download_arancia_reports(*, headless: bool = True) -> tuple[str, str]:
    with sync_playwright() as playwright:
        return download_arancia_reports(playwright, headless=headless)


def main() -> int:
    run_download_arancia_reports()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
