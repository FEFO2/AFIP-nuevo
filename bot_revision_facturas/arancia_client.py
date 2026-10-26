from __future__ import annotations

from afip_common.config import AranciaSettings
from afip_common.config import load_arancia_settings as load_settings

__all__ = ["AranciaClient", "AranciaSettings", "load_settings"]

import time

from playwright.sync_api import Frame, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bot_revision_facturas.models import AranciaRow, Invoice, InvoiceResult
from bot_revision_facturas.rules import compare_invoice, normalize_ticket, parse_money


class AranciaClient:
    def __init__(self, page: Page, settings: AranciaSettings, timeout_ms: int = 30_000) -> None:
        self.page = page
        self.settings = settings
        self.timeout_ms = timeout_ms
        self.facturacion_frame: Frame | None = None
        self.table_frame: Frame | None = None

    def login(self) -> None:
        self.page.goto(self.settings.url, wait_until="domcontentloaded")
        if not self.page.locator("#TextBox1").is_visible():
            enter = self.page.locator("#Button1")
            if enter.count():
                enter.first.click()
        self.page.locator("#TextBox1").wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator("#TextBox1").fill(self.settings.username)
        self.page.locator("#TextBox2").fill(self.settings.password)
        self.page.locator("#Button1").click()
        self.page.wait_for_load_state("networkidle")
        self.page.locator("#Button10").click()
        self.page.wait_for_timeout(1_000)

    def open_fac_prove_ar(self) -> None:
        frame = self._wait_for_frame("facturacion")
        frame.locator("#Button9").click()
        self.page.wait_for_timeout(1_000)
        self.facturacion_frame = frame
        self.table_frame = self._wait_for_child_frame(frame, "marco", "#TextBox1")

    def set_start_date(self, value: str) -> None:
        frame = self._table()
        frame.locator("#TextBox1").fill(value)
        frame.locator("#TextBox1").press("Tab")
        self.page.wait_for_timeout(1_000)

    def list_rows(self) -> dict[str, AranciaRow]:
        raw_rows = self._table().evaluate(
            """() => Array.from(document.querySelectorAll('table tr')).map(tr => {
                const cells = Array.from(tr.querySelectorAll('td'));
                const checkbox = tr.querySelector('input[type=checkbox]');
                if (cells.length < 7 || !checkbox) return null;
                return {
                    ticket: cells[2].innerText.trim(),
                    amount: cells[5].innerText.trim(),
                    supplier_invoice: cells[6].innerText.trim(),
                    checkbox_id: checkbox.id,
                };
            }).filter(Boolean)"""
        )
        rows: dict[str, AranciaRow] = {}
        for raw in raw_rows:
            try:
                row = AranciaRow(
                    ticket=normalize_ticket(raw["ticket"]),
                    amount=parse_money(raw["amount"]),
                    supplier_invoice=raw["supplier_invoice"],
                    checkbox_id=raw["checkbox_id"],
                )
            except ValueError:
                continue
            if row.ticket:
                rows[row.ticket] = row
        return rows

    def process_invoice(self, invoice: Invoice, *, dry_run: bool) -> InvoiceResult:
        checks = compare_invoice(invoice, self.list_rows())
        complete = all(check.status in {"accepted", "already_updated"} for check in checks)
        pending = [check for check in checks if check.status == "accepted"]
        if not pending:
            return InvoiceResult(invoice, checks, "already_updated" if complete else "incomplete")
        if dry_run:
            return InvoiceResult(
                invoice, checks, "would_update" if complete else "would_update_partial"
            )

        for check in pending:
            self._table().locator(f'[id="{check.checkbox_id}"]').check()
        frame = self._table()
        frame.locator("#TextBox3").fill(invoice.number)
        frame.locator("#Button3").click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(1_000)
        if self.facturacion_frame is None:
            raise RuntimeError("No esta abierto el modulo de facturacion.")
        self.table_frame = self._wait_for_child_frame(self.facturacion_frame, "marco", "#TextBox1")
        return InvoiceResult(invoice, checks, "updated" if complete else "partially_updated")

    def _table(self) -> Frame:
        if self.table_frame is None:
            raise RuntimeError("Primero hay que abrir FAC Prove AR.")
        return self.table_frame

    def _wait_for_frame(self, name: str) -> Frame:
        deadline = time.monotonic() + self.timeout_ms / 1_000
        while time.monotonic() < deadline:
            frame = self.page.frame(name=name)
            if frame is not None:
                return frame
            self.page.wait_for_timeout(200)
        raise TimeoutError(f"No se encontro el iframe {name!r}.")

    def _wait_for_child_frame(self, parent: Frame, name: str, selector: str) -> Frame:
        deadline = time.monotonic() + self.timeout_ms / 1_000
        while time.monotonic() < deadline:
            for child in parent.child_frames:
                if child.name != name:
                    continue
                try:
                    child.locator(selector).wait_for(state="visible", timeout=500)
                    return child
                except PlaywrightTimeoutError:
                    pass
            self.page.wait_for_timeout(200)
        raise TimeoutError(f"No se encontro el iframe hijo {name!r}.")
