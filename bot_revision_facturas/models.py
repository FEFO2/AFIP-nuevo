from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class TicketLine:
    number: str
    billed_amount: Decimal


@dataclass(frozen=True)
class Invoice:
    path: Path
    kind: str
    number: str
    issue_date: date | None
    currency: str
    tickets: tuple[TicketLine, ...]
    has_ticket_table: bool


@dataclass(frozen=True)
class AranciaRow:
    ticket: str
    amount: Decimal
    supplier_invoice: str
    checkbox_id: str


@dataclass(frozen=True)
class TicketCheck:
    ticket: TicketLine
    status: str
    system_amount: Decimal | None = None
    difference: Decimal | None = None
    checkbox_id: str = ""
    system_invoice: str = ""


@dataclass(frozen=True)
class InvoiceResult:
    invoice: Invoice
    tickets: tuple[TicketCheck, ...]
    status: str

    @property
    def successful(self) -> bool:
        return self.status in {"updated", "already_updated", "would_update"}
