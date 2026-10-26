from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from bot_revision_facturas.models import Invoice, TicketLine
from bot_revision_facturas.rules import normalize_ticket, parse_money

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"Fecha de Emisi.n:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
INVOICE_NUMBER_RE = re.compile(r"\bNro:\s*(\d+)\s*-\s*(\d+)", re.IGNORECASE)
CURRENCY_RE = re.compile(r"Moneda:\s*([A-Za-z]{3})", re.IGNORECASE)
TICKET_ROW_RE = re.compile(
    r"(?P<tkt>\d{6,})\s+"
    r"(?P<fare>-?[\d.,]+)\s+"
    r"(?P<tax>-?[\d.,]+)\s+"
    r"(?P<oc>-?[\d.,]+)\s+"
    r"(?P<subtotal>-?[\d.,]+)\s*$"
)


class InvoiceParseError(ValueError):
    pass


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", value).upper()


def parse_invoice_text(text: str, path: Path) -> Invoice:
    normalized = _normalized(text)
    if "NOTA DE CR" in normalized:
        kind = "credit_note"
    elif "FACTURA" in normalized:
        kind = "invoice"
    else:
        kind = "unknown"

    number_match = INVOICE_NUMBER_RE.search(text)
    number = ""
    if number_match:
        number = f"{number_match.group(1).zfill(4)}-{number_match.group(2).zfill(8)}"

    date_match = DATE_RE.search(text)
    issue_date = datetime.strptime(date_match.group(1), "%d/%m/%Y").date() if date_match else None
    currency_match = CURRENCY_RE.search(text)
    currency = currency_match.group(1).upper() if currency_match else ""

    tickets_by_number: dict[str, TicketLine] = {}
    for line in text.splitlines():
        match = TICKET_ROW_RE.search(line)
        if not match:
            continue
        ticket = normalize_ticket(match.group("tkt"))
        parsed = TicketLine(ticket, parse_money(match.group("subtotal")))
        previous = tickets_by_number.get(ticket)
        if previous and previous.billed_amount != parsed.billed_amount:
            raise InvoiceParseError(
                f"El TKT {ticket} aparece con dos importes distintos en {path.name}."
            )
        tickets_by_number[ticket] = parsed

    has_ticket_table = "NRO TKT" in normalized
    if kind == "unknown":
        raise InvoiceParseError(f"No se reconoce el tipo de comprobante de {path.name}.")
    if kind == "invoice" and not number:
        raise InvoiceParseError(f"No se encontro el numero de factura en {path.name}.")
    if kind == "invoice" and has_ticket_table and not tickets_by_number:
        raise InvoiceParseError(
            f"Se encontro la tabla de TKT pero no se pudieron leer sus filas en {path.name}."
        )

    return Invoice(
        path=path,
        kind=kind,
        number=number,
        issue_date=issue_date,
        currency=currency,
        tickets=tuple(tickets_by_number.values()),
        has_ticket_table=has_ticket_table,
    )


def parse_pdf(path: Path) -> Invoice:
    try:
        import pdfplumber
    except ImportError as error:
        raise RuntimeError(
            "Falta pdfplumber. Ejecuta: pip install -r bot_revision_facturas/requirements.txt"
        ) from error

    page_texts: list[str] = []
    seen: set[str] = set()
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            canonical = re.sub(r"\s+", " ", text).strip()
            if canonical and canonical not in seen:
                seen.add(canonical)
                page_texts.append(text)

    if not page_texts:
        raise InvoiceParseError(f"El PDF {path.name} no contiene texto legible.")
    return parse_invoice_text("\n".join(page_texts), path)
