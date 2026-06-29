from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Frame, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from utils import (
    browser_mode_label,
    pause_for_manual_mode,
    PlaywrightTimeoutConfig,
    get_playwright_timeout_config,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AranciaSettings:
    url: str
    username: str
    password: str


def load_arancia_settings() -> AranciaSettings:
    load_dotenv()

    url = os.getenv("ARANCIA_URL")
    username = os.getenv("ARANCIA_USERNAME")
    password = os.getenv("ARANCIA_PASSWORD")

    if not all([url, username, password]):
        raise ValueError(
            "Faltan variables ARANCIA_URL, ARANCIA_USERNAME o ARANCIA_PASSWORD en el archivo .env"
        )

    return AranciaSettings(url=url, username=username, password=password)


def _to_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _to_date_input_value(value: object) -> str:
    if pd.isna(value):
        return ""

    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return str(value)

    return parsed.strftime("%Y-%m-%d")


def _print_row_loaded(kind: str, index: int, total: int) -> None:
    print(f"[OK] {kind} {index}/{total} cargada.")


class AranciaPlaywrightClient:
    def __init__(
        self,
        page: Page,
        settings: AranciaSettings,
        timeout_config: PlaywrightTimeoutConfig,
    ) -> None:
        self.page = page
        self.settings = settings
        self.timeout_config = timeout_config

    def login(self) -> None:
        logger.info("Arancia: abriendo portal.")
        self.page.goto(self.settings.url, wait_until="domcontentloaded")

        if not self.page.locator("#TextBox1").is_visible():
            enter_button = self.page.locator("#Button1")
            if enter_button.count():
                enter_button.first.click()

        self.page.locator("#TextBox1").wait_for(
            state="visible",
            timeout=self.timeout_config.action_timeout_ms,
        )
        self.page.locator("#TextBox1").fill(self.settings.username)
        self.page.locator("#TextBox2").fill(self.settings.password)
        self.page.locator("#Button1").click()
        self.page.wait_for_load_state("networkidle")
        self.page.locator("#Button10").click()
        self.page.wait_for_timeout(self.timeout_config.wait_ms)
        logger.info("Arancia: sesion iniciada y modulo de facturacion abierto.")

    def upload_purchase_invoices(self, data: pd.DataFrame) -> pd.DataFrame:
        logger.info("Compras: iniciando carga de %s facturas.", len(data))
        facturacion_frame = self._open_facturacion_module()
        facturacion_frame.locator("#Button3").click()

        marco_frame = self._wait_for_child_frame(
            facturacion_frame,
            "marco",
            required_selector="#DetailsView1_TextBox1",
        )
        total_rows = len(data)
        uploaded_rows: list[dict[str, object]] = []

        for index, (_, row) in enumerate(data.iterrows(), start=1):
            logger.info(
                "Compras: cargando factura %s/%s (%s).",
                index,
                total_rows,
                _to_text(row["Factura"]),
            )
            purchase_date = _to_date_input_value(row["Fecha"])
            marco_frame.locator("#DetailsView1_TextBox1").fill(purchase_date)
            marco_frame.locator("#DetailsView1_TextBox2").fill(purchase_date)
            marco_frame.locator('input[name="DetailsView1$ctl02"]').fill(_to_text(row["Tipo3"]))
            marco_frame.locator('input[name="DetailsView1$ctl03"]').fill(_to_text(row["Factura"]))
            marco_frame.locator('input[name="DetailsView1$ctl04"]').fill(_to_text(row["Proveedor"]))
            marco_frame.locator('input[name="DetailsView1$ctl05"]').fill(_to_text(row["CUIT"]))
            marco_frame.locator('input[name="DetailsView1$TextBox3"]').fill(_to_text(row["NETO 10.5"]))
            marco_frame.locator('input[name="DetailsView1$TextBox4"]').fill(_to_text(row["NETO 21"]))
            marco_frame.locator('input[name="DetailsView1$TextBox5"]').fill(_to_text(row["IVA 10.5"]))
            marco_frame.locator('input[name="DetailsView1$TextBox6"]').fill(_to_text(row["IVA 21"]))
            marco_frame.locator('input[name="DetailsView1$TextBox7"]').fill(
                _to_text(row["TOTAL_NO_GRAVADO"])
            )
            marco_frame.get_by_role("link", name="Agregar").click()
            self.page.wait_for_timeout(self.timeout_config.wait_ms)
            uploaded_rows.append(row.to_dict())
            _print_row_loaded("Compra", index, total_rows)

        logger.info("Compras: carga finalizada. Facturas cargadas=%s", len(uploaded_rows))
        return pd.DataFrame(uploaded_rows, columns=data.columns)

    def upload_sales_invoices(self, data: pd.DataFrame) -> pd.DataFrame:
        logger.info("Ventas: iniciando carga de %s facturas.", len(data))
        facturacion_frame = self._open_facturacion_module()
        facturacion_frame.locator("#Button5").click()

        marco_frame = self._wait_for_child_frame(
            facturacion_frame,
            "marco",
            required_selector="#CheckBoxList1_0",
        )
        uploaded_rows: list[dict[str, object]] = []

        self._set_checkbox(marco_frame, "#CheckBoxList1_0", checked=False)
        self._set_checkbox(marco_frame, "#CheckBoxList1_3", checked=True)
        self._wait_for_visible_selector(marco_frame, "#contar")
        self._fill_and_commit(marco_frame, "#contar", "3")
        self._wait_for_visible_selector(marco_frame, "#ivasa1")

        for field_id, value in {"ivasa1": "0", "ivasa2": "10.5"}.items():
            self._fill_and_commit(marco_frame, f"#{field_id}", value)

        total_rows = len(data)
        for index, (_, row) in enumerate(data.iterrows(), start=1):
            logger.info(
                "Ventas: cargando factura %s/%s (%s).",
                index,
                total_rows,
                _to_text(row["Factura"]),
            )
            self._fill_and_commit(marco_frame, "#total1", row["TOTAL_NO_GRAVADO"])
            self._fill_and_commit(marco_frame, "#total2", row["TOTAL_10.5"])
            self._fill_and_commit(marco_frame, '[name="total3"]', row["TOTAL_21"])

            marco_frame.locator("#Button2").click()
            self._wait_for_visible_selector(marco_frame, "#Button5")

            self._fill_and_commit(marco_frame, '[name="TextBox3"]', row["Cliente"])
            self._fill_and_commit(marco_frame, '[name="TextBox4"]', row["CUIT"])
            self._fill_and_commit(marco_frame, '[name="TextBox6"]', row["Factura"])
            self._fill_and_commit(marco_frame, '[name="TextBox7"]', row["tipo3_new"])

            fecha_input = marco_frame.locator('[name="TextBox8"]')
            fecha_input.fill(_to_date_input_value(row["Fecha"]))
            self.page.wait_for_timeout(self.timeout_config.wait_ms)

            marco_frame.locator("#Button5").click()
            self.page.wait_for_timeout(self.timeout_config.wait_ms)
            uploaded_rows.append(row.to_dict())
            _print_row_loaded("Venta", index, total_rows)

        logger.info("Ventas: carga finalizada. Facturas cargadas=%s", len(uploaded_rows))
        return pd.DataFrame(uploaded_rows, columns=data.columns)

    def _open_facturacion_module(self) -> Frame:
        self.page.wait_for_selector(
            "iframe[name='facturacion']",
            timeout=self.timeout_config.action_timeout_ms,
        )
        return self._wait_for_frame("facturacion")

    def _wait_for_frame(self, name: str, *, required_selector: str | None = None) -> Frame:
        deadline = time.monotonic() + (self.timeout_config.action_timeout_ms / 1000)

        while time.monotonic() < deadline:
            frame = self.page.frame(name=name)
            if frame is not None:
                if required_selector is None:
                    return frame

                try:
                    frame.locator(required_selector).wait_for(state="visible", timeout=500)
                    return frame
                except PlaywrightTimeoutError:
                    pass
            self.page.wait_for_timeout(200)

        if required_selector is None:
            raise TimeoutError(f"No se pudo obtener el iframe '{name}'.")

        raise TimeoutError(
            f"No se pudo obtener el iframe '{name}' con el selector '{required_selector}' visible."
        )

    def _wait_for_child_frame(
        self,
        parent_frame: Frame,
        name: str,
        *,
        required_selector: str | None = None,
    ) -> Frame:
        deadline = time.monotonic() + (self.timeout_config.action_timeout_ms / 1000)

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

            self.page.wait_for_timeout(200)

        if required_selector is None:
            raise TimeoutError(f"No se pudo obtener el iframe hijo '{name}'.")

        raise TimeoutError(
            f"No se pudo obtener el iframe hijo '{name}' con el selector '{required_selector}' visible."
        )

    def _set_checkbox(self, frame: Frame, selector: str, *, checked: bool) -> None:
        checkbox = frame.locator(selector)
        checkbox.wait_for(state="visible", timeout=self.timeout_config.action_timeout_ms)

        if checkbox.is_checked() != checked:
            checkbox.click()
            self.page.wait_for_timeout(self.timeout_config.wait_ms)

    def _wait_for_visible_selector(self, frame: Frame, selector: str) -> None:
        frame.locator(selector).wait_for(
            state="visible",
            timeout=self.timeout_config.action_timeout_ms,
        )

    def _fill_and_commit(self, frame: Frame, selector: str, value: object) -> None:
        field = frame.locator(selector)
        field.wait_for(state="visible", timeout=self.timeout_config.action_timeout_ms)
        field.click()
        field.fill(_to_text(value))
        field.press("Tab")
        self.page.wait_for_timeout(self.timeout_config.wait_ms)


def cargar_facturas_compra(
    data: pd.DataFrame,
    *,
    headless: bool = True,
    manual_on_error: bool = False,
    timeout_config: PlaywrightTimeoutConfig | None = None,
) -> pd.DataFrame:
    if data.empty:
        print("[OK] No hay facturas de compra pendientes para cargar.")
        logger.info("Compras: no hay facturas pendientes para cargar.")
        return data.iloc[0:0].copy()

    settings = load_arancia_settings()
    timeout_config = timeout_config or get_playwright_timeout_config()
    logger.info(
        "Compras: iniciando Playwright con navegador %s.",
        browser_mode_label(headless),
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(timeout_config.action_timeout_ms)
        context.set_default_navigation_timeout(timeout_config.navigation_timeout_ms)
        page = context.new_page()

        try:
            client = AranciaPlaywrightClient(page, settings, timeout_config)
            client.login()
            uploaded_data = client.upload_purchase_invoices(data)
        except Exception as error:
            pause_for_manual_mode(
                enabled=manual_on_error,
                headless=headless,
                system_name="Carga de compras",
                error=error,
            )
            raise
        finally:
            context.close()
            browser.close()

    print("[OK] Carga de compras finalizada.")
    logger.info("Compras: navegador cerrado y proceso finalizado.")
    return uploaded_data


def cargar_facturas_ventas(
    data: pd.DataFrame,
    *,
    headless: bool = True,
    manual_on_error: bool = False,
    timeout_config: PlaywrightTimeoutConfig | None = None,
) -> pd.DataFrame:
    if data.empty:
        print("[OK] No hay facturas de venta pendientes para cargar.")
        logger.info("Ventas: no hay facturas pendientes para cargar.")
        return data.iloc[0:0].copy()

    settings = load_arancia_settings()
    timeout_config = timeout_config or get_playwright_timeout_config()
    logger.info(
        "Ventas: iniciando Playwright con navegador %s.",
        browser_mode_label(headless),
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        context.set_default_timeout(timeout_config.action_timeout_ms)
        context.set_default_navigation_timeout(timeout_config.navigation_timeout_ms)
        page = context.new_page()

        try:
            client = AranciaPlaywrightClient(page, settings, timeout_config)
            client.login()
            uploaded_data = client.upload_sales_invoices(data)
        except Exception as error:
            pause_for_manual_mode(
                enabled=manual_on_error,
                headless=headless,
                system_name="Carga de ventas",
                error=error,
            )
            raise
        finally:
            context.close()
            browser.close()

    print("[OK] Carga de ventas finalizada.")
    logger.info("Ventas: navegador cerrado y proceso finalizado.")
    return uploaded_data
