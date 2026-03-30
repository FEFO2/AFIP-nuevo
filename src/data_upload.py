from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import Frame, Page, sync_playwright


DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_WAIT_MS = 1_000


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


def _print_row_loaded(kind: str, index: int, total: int) -> None:
    print(f"[OK] {kind} {index}/{total} cargada.")


class AranciaPlaywrightClient:
    def __init__(self, page: Page, settings: AranciaSettings) -> None:
        self.page = page
        self.settings = settings

    def login(self) -> None:
        self.page.goto(self.settings.url, wait_until="domcontentloaded")

        if not self.page.locator("#TextBox1").is_visible():
            enter_button = self.page.locator("#Button1")
            if enter_button.count():
                enter_button.first.click()

        self.page.locator("#TextBox1").wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        self.page.locator("#TextBox1").fill(self.settings.username)
        self.page.locator("#TextBox2").fill(self.settings.password)
        self.page.locator("#Button1").click()
        self.page.wait_for_load_state("networkidle")
        self.page.locator("#Button10").click()
        self.page.wait_for_timeout(DEFAULT_WAIT_MS)

    def upload_purchase_invoices(self, data: pd.DataFrame) -> None:
        facturacion_frame = self._open_facturacion_module()
        facturacion_frame.locator("#Button3").click()
        self.page.wait_for_timeout(DEFAULT_WAIT_MS)

        marco_frame = self._wait_for_frame("marco")
        total_rows = len(data)

        for index, (_, row) in enumerate(data.iterrows(), start=1):
            marco_frame.locator("#DetailsView1_TextBox1").fill(_to_text(row["Fecha"]))
            marco_frame.locator("#DetailsView1_TextBox2").fill(_to_text(row["Fecha"]))
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
            self.page.wait_for_timeout(DEFAULT_WAIT_MS)
            _print_row_loaded("Compra", index, total_rows)

    def upload_sales_invoices(self, data: pd.DataFrame) -> None:
        facturacion_frame = self._open_facturacion_module()
        facturacion_frame.locator("#Button5").click()
        self.page.wait_for_timeout(DEFAULT_WAIT_MS)

        marco_frame = self._wait_for_frame("marco")

        self._set_checkbox(marco_frame, "#CheckBoxList1_0", checked=False)
        self._set_checkbox(marco_frame, "#CheckBoxList1_3", checked=True)
        self._fill_and_commit(marco_frame, "#contar", "3")

        for field_id, value in {"ivasa1": "0", "ivasa2": "10.5"}.items():
            self._fill_and_commit(marco_frame, f"#{field_id}", value)

        total_rows = len(data)
        for index, (_, row) in enumerate(data.iterrows(), start=1):
            self._fill_and_commit(marco_frame, "#total1", row["TOTAL_NO_GRAVADO"])
            self._fill_and_commit(marco_frame, "#total2", row["TOTAL_10.5"])
            self._fill_and_commit(marco_frame, '[name="total3"]', row["TOTAL_21"])

            marco_frame.locator("#Button2").click()
            self.page.wait_for_timeout(DEFAULT_WAIT_MS)

            self._fill_and_commit(marco_frame, '[name="TextBox3"]', row["Cliente"])
            self._fill_and_commit(marco_frame, '[name="TextBox4"]', row["CUIT"])
            self._fill_and_commit(marco_frame, '[name="TextBox6"]', row["Factura"])
            self._fill_and_commit(marco_frame, '[name="TextBox7"]', row["tipo3_new"])

            fecha_input = marco_frame.locator('[name="TextBox8"]')
            fecha_input.fill(_to_text(row["Fecha"]))
            self.page.wait_for_timeout(DEFAULT_WAIT_MS)

            marco_frame.locator("#Button5").click()
            self.page.wait_for_timeout(DEFAULT_WAIT_MS)
            _print_row_loaded("Venta", index, total_rows)

    def _open_facturacion_module(self) -> Frame:
        self.page.wait_for_selector("iframe[name='facturacion']", timeout=DEFAULT_TIMEOUT_MS)
        return self._wait_for_frame("facturacion")

    def _wait_for_frame(self, name: str) -> Frame:
        deadline = time.monotonic() + (DEFAULT_TIMEOUT_MS / 1000)

        while time.monotonic() < deadline:
            frame = self.page.frame(name=name)
            if frame is not None:
                return frame
            self.page.wait_for_timeout(200)

        raise TimeoutError(f"No se pudo obtener el iframe '{name}'.")

    def _set_checkbox(self, frame: Frame, selector: str, *, checked: bool) -> None:
        checkbox = frame.locator(selector)
        checkbox.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)

        if checkbox.is_checked() != checked:
            checkbox.click()
            self.page.wait_for_timeout(DEFAULT_WAIT_MS)

    def _fill_and_commit(self, frame: Frame, selector: str, value: object) -> None:
        field = frame.locator(selector)
        field.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        field.click()
        field.fill(_to_text(value))
        field.press("Tab")
        self.page.wait_for_timeout(DEFAULT_WAIT_MS)


def cargar_facturas_compra(data: pd.DataFrame, *, headless: bool = True) -> None:
    if data.empty:
        print("[OK] No hay facturas de compra pendientes para cargar.")
        return

    settings = load_arancia_settings()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        client = AranciaPlaywrightClient(page, settings)
        client.login()
        client.upload_purchase_invoices(data)

        context.close()
        browser.close()

    print("[OK] Carga de compras finalizada.")


def cargar_facturas_ventas(data: pd.DataFrame, *, headless: bool = True) -> None:
    if data.empty:
        print("[OK] No hay facturas de venta pendientes para cargar.")
        return

    settings = load_arancia_settings()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        client = AranciaPlaywrightClient(page, settings)
        client.login()
        client.upload_sales_invoices(data)

        context.close()
        browser.close()

    print("[OK] Carga de ventas finalizada.")
