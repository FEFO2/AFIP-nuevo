from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from bot_revision_facturas.arancia_client import AranciaClient, load_settings
from bot_revision_facturas.gmail_client import GmailClient
from bot_revision_facturas.invoice_parser import InvoiceParseError, parse_pdf
from bot_revision_facturas.models import Invoice, InvoiceResult

BASE_DIR = Path(__file__).resolve().parent
if (BASE_DIR / ".playwright").is_dir():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BASE_DIR / ".playwright"))

logger = logging.getLogger(__name__)

SENDER = "facturacion@carnival-tours.com"
SUBJECT = "Factura Arancia Services SRL"
REVIEW_RECIPIENT = "Enzo@aranciatravel.com"
REPORT_FIELDS = [
    "message_id",
    "attachment",
    "invoice",
    "ticket",
    "billed_amount",
    "system_amount",
    "difference",
    "system_invoice",
    "ticket_status",
    "invoice_status",
    "email_action",
]


@dataclass
class PreparedMessage:
    raw: dict[str, Any]
    attachments: list[Path]
    invoices: list[Invoice]
    error: str = ""

    @property
    def id(self) -> str:
        return self.raw["id"]


def first_day_previous_month(today: date | None = None) -> date:
    today = today or date.today()
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"drafts": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"drafts": {}}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _prepare_messages(gmail: GmailClient) -> list[PreparedMessage]:
    prepared: list[PreparedMessage] = []
    for message in gmail.find_unread_invoices(SENDER, SUBJECT):
        destination = BASE_DIR / "adjuntos" / message["id"]
        attachments = gmail.download_attachments(message, destination)
        pdfs = [path for path in attachments if path.suffix.casefold() == ".pdf"]
        invoices: list[Invoice] = []
        errors: list[str] = []
        if not pdfs:
            errors.append("El correo no contiene ningun PDF.")
        else:
            for path in pdfs:
                try:
                    invoices.append(parse_pdf(path))
                except (InvoiceParseError, OSError, RuntimeError) as exception:
                    errors.append(str(exception))
        prepared.append(PreparedMessage(message, attachments, invoices, "; ".join(errors)))
    return prepared


def _report_rows_for_result(message_id: str, result: InvoiceResult) -> list[dict[str, Any]]:
    return [
        {
            "message_id": message_id,
            "attachment": result.invoice.path.name,
            "invoice": result.invoice.number,
            "ticket": check.ticket.number,
            "billed_amount": check.ticket.billed_amount,
            "system_amount": check.system_amount,
            "difference": check.difference,
            "system_invoice": check.system_invoice,
            "ticket_status": check.status,
            "invoice_status": result.status,
            "email_action": "",
        }
        for check in result.tickets
    ]


def _draft_body(results: list[InvoiceResult]) -> str:
    lines = ["Hola Enzo,", "", "Estas facturas tienen diferencias y requieren revision:", ""]
    for result in results:
        if not any(check.status == "difference" for check in result.tickets):
            continue
        lines.append(f"Factura {result.invoice.number}:")
        for check in result.tickets:
            if check.status == "difference":
                lines.append(
                    f"- TKT {check.ticket.number} con diferencia de {check.difference} "
                    f"(factura: {check.ticket.billed_amount}; sistema: {check.system_amount})."
                )
        lines.append("")
    return "\n".join(lines)


def _write_report(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _print_report(rows: list[dict[str, Any]]) -> None:
    print("\n=== REPORTE REVISION DE FACTURAS ===")
    if not rows:
        print("No habia correos pendientes.")
        return
    labels = {
        "accepted": "OK",
        "already_updated": "YA ACTUALIZADO",
        "difference": "DIFERENCIA NO ACEPTADA",
        "missing": "NO ENCONTRADO",
        "assigned_to_other_invoice": "ASIGNADO A OTRA FACTURA",
        "sin_tickets": "SIN TICKETS",
    }
    for row in rows:
        detail = f"TKT {row['ticket']}" if row["ticket"] else row["attachment"]
        status = row["ticket_status"] or row["invoice_status"]
        status = labels.get(status, status)
        existing = (
            f" | factura en Arancia={row.get('system_invoice')}"
            if row.get("system_invoice")
            else ""
        )
        print(
            f"- {detail}: {status}"
            f" | factura={row['invoice'] or '-'}{existing} | correo={row['email_action'] or '-'}"
        )


def authorize_gmail() -> int:
    gmail = GmailClient(
        BASE_DIR / "client_secret.json",
        BASE_DIR / "token_automation.json",
    )
    account = gmail.profile_email()
    if account.casefold() != "francesc@aranciatravel.com":
        raise RuntimeError(f"La cuenta autorizada es {account}, no francesc@aranciatravel.com.")
    print(f"Gmail autorizado correctamente para {account}.")
    return 0


def run(*, dry_run: bool = False, show_browser: bool = False) -> int:
    token_path = BASE_DIR / ("token.json" if dry_run else "token_automation.json")
    gmail = GmailClient(BASE_DIR / "client_secret.json", token_path, readonly=dry_run)
    account = gmail.profile_email()
    if account.casefold() != "francesc@aranciatravel.com":
        raise RuntimeError(f"La cuenta autorizada es {account}, no francesc@aranciatravel.com.")
    messages = _prepare_messages(gmail)
    state_path = BASE_DIR / "estado.json"
    state = _read_state(state_path)
    report_rows: list[dict[str, Any]] = []
    results_by_message: dict[str, list[InvoiceResult]] = {message.id: [] for message in messages}

    pending = [
        (message, invoice)
        for message in messages
        if not message.error and not any(item.kind == "credit_note" for item in message.invoices)
        for invoice in message.invoices
        if invoice.kind == "invoice" and invoice.tickets
    ]

    if pending:
        current_message: PreparedMessage | None = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not show_browser)
                context = browser.new_context()
                context.set_default_timeout(30_000)
                context.set_default_navigation_timeout(90_000)
                page = context.new_page()
                try:
                    arancia = AranciaClient(page, load_settings())
                    arancia.login()
                    arancia.open_fac_prove_ar()
                    arancia.set_start_date(first_day_previous_month().isoformat())
                    for current_message, invoice in pending:
                        result = arancia.process_invoice(invoice, dry_run=dry_run)
                        results_by_message[current_message.id].append(result)
                        report_rows.extend(_report_rows_for_result(current_message.id, result))
                finally:
                    context.close()
                    browser.close()
        except Exception as exception:
            logger.exception("No se pudo completar la consulta de Arancia.")
            failed = False
            for message, _ in pending:
                if current_message is not None and message.id == current_message.id:
                    failed = True
                if failed or current_message is None:
                    message.error = f"Arancia: {exception}"

    technical_error = False
    for message in messages:
        action = ""
        results = results_by_message[message.id]

        if any(invoice.kind == "credit_note" for invoice in message.invoices):
            action = "nota_credito_sin_cambios_no_leida"
            for invoice in message.invoices:
                report_rows.append(
                    {
                        "message_id": message.id,
                        "attachment": invoice.path.name,
                        "invoice": invoice.number,
                        "ticket": "",
                        "billed_amount": "",
                        "system_amount": "",
                        "difference": "",
                        "ticket_status": "",
                        "invoice_status": "credit_note",
                        "email_action": action,
                    }
                )
        elif message.error:
            technical_error = True
            action = "sin_cambios_no_leido"
            report_rows.append(
                {
                    "message_id": message.id,
                    "attachment": "",
                    "invoice": "",
                    "ticket": "",
                    "billed_amount": "",
                    "system_amount": "",
                    "difference": "",
                    "ticket_status": f"error: {message.error}",
                    "invoice_status": "error",
                    "email_action": action,
                }
            )
        elif not results:
            action = "archivar_leido" if not dry_run else "archivaria_leido"
            if not dry_run:
                gmail.archive_read(message.id)
            for invoice in message.invoices:
                report_rows.append(
                    {
                        "message_id": message.id,
                        "attachment": invoice.path.name,
                        "invoice": invoice.number,
                        "ticket": "",
                        "billed_amount": "",
                        "system_amount": "",
                        "difference": "",
                        "ticket_status": "sin_tickets",
                        "invoice_status": "concepts_only",
                        "email_action": action,
                    }
                )
        elif all(result.successful for result in results):
            action = "archivar_leido" if not dry_run else "archivaria_leido"
            if not dry_run:
                gmail.archive_read(message.id)
        else:
            issues = [
                check
                for result in results
                for check in result.tickets
                if check.status == "difference"
            ]
            if issues:
                action = (
                    "borrador_y_dejar_en_recibidos_leido"
                    if not dry_run
                    else "crearia_borrador_y_leeria"
                )
                if not dry_run:
                    if message.id not in state["drafts"]:
                        draft_id = gmail.create_difference_draft(
                            recipient=REVIEW_RECIPIENT,
                            source_message=message.raw,
                            body=_draft_body(results),
                            attachments=message.attachments,
                        )
                        state["drafts"][message.id] = draft_id
                        _write_state(state_path, state)
                    gmail.mark_read(message.id)
            else:
                action = (
                    "dejar_en_recibidos_no_leido"
                    if not dry_run
                    else "dejaria_en_recibidos_no_leido"
                )

        for row in report_rows:
            if row["message_id"] == message.id and not row["email_action"]:
                row["email_action"] = action

    report_path = BASE_DIR / "reporte_revision.csv"
    _write_report(report_rows, report_path)
    _print_report(report_rows)
    print(f"\nReporte CSV: {report_path}")
    return 1 if technical_error else 0
