from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from bot_revision_facturas.models import AranciaRow, Invoice, TicketCheck

CENT = Decimal("0.01")
FIVE_MIN = Decimal("4.99")
FIVE_MAX = Decimal("5.01")


def parse_money(value: str) -> Decimal:
    cleaned = re.sub(r"[^\d,.-]", "", value or "")
    if not cleaned:
        raise ValueError(f"Importe vacio o invalido: {value!r}")

    if "," in cleaned and "." in cleaned:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        cleaned = cleaned.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in cleaned:
        parts = cleaned.split(",")
        cleaned = "".join(parts) if len(parts[-1]) == 3 else ".".join(parts)
    elif cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return Decimal(cleaned).quantize(CENT)
    except InvalidOperation as error:
        raise ValueError(f"Importe invalido: {value!r}") from error


def normalize_ticket(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def normalize_invoice_number(value: str) -> str:
    groups = re.findall(r"\d+", value or "")
    return "-".join(str(int(group)) for group in groups) if groups else ""


def accepted_difference(billed: Decimal, system: Decimal) -> tuple[bool, Decimal]:
    difference = abs(billed - system).quantize(CENT)
    return difference == Decimal("0.00") or FIVE_MIN <= difference <= FIVE_MAX, difference


def compare_invoice(invoice: Invoice, rows: dict[str, AranciaRow]) -> tuple[TicketCheck, ...]:
    checks: list[TicketCheck] = []
    expected_invoice = normalize_invoice_number(invoice.number)

    for ticket in invoice.tickets:
        row = rows.get(normalize_ticket(ticket.number))
        if row is None:
            checks.append(TicketCheck(ticket=ticket, status="missing"))
            continue

        accepted, difference = accepted_difference(ticket.billed_amount, row.amount)
        if not accepted:
            checks.append(
                TicketCheck(
                    ticket=ticket,
                    status="difference",
                    system_amount=row.amount,
                    difference=difference,
                    system_invoice=row.supplier_invoice,
                )
            )
            continue

        current_invoice = normalize_invoice_number(row.supplier_invoice)
        if current_invoice and current_invoice != expected_invoice:
            checks.append(
                TicketCheck(
                    ticket=ticket,
                    status="assigned_to_other_invoice",
                    system_amount=row.amount,
                    difference=difference,
                    system_invoice=row.supplier_invoice,
                )
            )
            continue

        status = "already_updated" if current_invoice == expected_invoice else "accepted"
        checks.append(
            TicketCheck(
                ticket=ticket,
                status=status,
                system_amount=row.amount,
                difference=difference,
                checkbox_id=row.checkbox_id,
                system_invoice=row.supplier_invoice,
            )
        )

    return tuple(checks)
