from __future__ import annotations

import base64
import tempfile
import unittest
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot_revision_facturas import workflow
from bot_revision_facturas.gmail_client import GmailClient
from bot_revision_facturas.models import Invoice, InvoiceResult, TicketCheck, TicketLine


class EmailActionTests(unittest.TestCase):
    def test_only_differences_create_drafts(self) -> None:
        invoice = Invoice(Path("invoice.pdf"), "invoice", "0008-123", None, "USD", (), True)
        for statuses in (
            ("missing",),
            ("assigned_to_other_invoice",),
            ("difference",),
            ("missing", "difference"),
        ):
            with self.subTest(statuses=statuses), tempfile.TemporaryDirectory() as directory:
                checks = tuple(
                    TicketCheck(
                        TicketLine(str(index), Decimal("100")),
                        status,
                        system_amount=Decimal("90"),
                        difference=Decimal("10"),
                    )
                    for index, status in enumerate(statuses)
                )
                result = InvoiceResult(invoice, checks, "incomplete")
                source = {"id": "original", "threadId": "thread"}
                prepared = workflow.PreparedMessage(source, [], [invoice])
                # Give the workflow a ticket-bearing invoice so it consults Arancia.
                invoice = Invoice(
                    invoice.path,
                    invoice.kind,
                    invoice.number,
                    None,
                    "USD",
                    (checks[0].ticket,),
                    True,
                )
                prepared.invoices = [invoice]
                with (
                    patch.object(workflow, "BASE_DIR", Path(directory)),
                    patch.object(workflow, "GmailClient") as gmail_class,
                    patch.object(workflow, "_prepare_messages", return_value=[prepared]),
                    patch.object(workflow, "sync_playwright"),
                    patch.object(workflow, "load_settings"),
                    patch.object(workflow, "AranciaClient") as arancia_class,
                ):
                    gmail = gmail_class.return_value
                    gmail.profile_email.return_value = "francesc@aranciatravel.com"
                    gmail.create_difference_draft.return_value = "draft"
                    arancia_class.return_value.process_invoice.return_value = result
                    self.assertEqual(workflow.run(), 0)
                    gmail.archive_read.assert_not_called()
                    if "difference" in statuses:
                        gmail.create_difference_draft.assert_called_once()
                        kwargs = gmail.create_difference_draft.call_args.kwargs
                        self.assertEqual(kwargs["source_message"], source)
                        self.assertNotIn("no aparece", kwargs["body"])
                        gmail.mark_read.assert_called_once_with("original")
                    else:
                        gmail.create_difference_draft.assert_not_called()
                        gmail.mark_read.assert_not_called()

    def test_draft_is_reply_in_original_thread(self) -> None:
        client = GmailClient(Path("secret"), Path("token"))
        client._service = MagicMock()
        create = client._service.users.return_value.drafts.return_value.create
        create.return_value.execute.return_value = {"id": "draft"}
        source = {
            "threadId": "original-thread",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Factura Arancia Services SRL"},
                    {"name": "Message-ID", "value": "<original@example.com>"},
                    {"name": "References", "value": "<previous@example.com>"},
                ]
            },
        }
        self.assertEqual(
            client.create_difference_draft(
                recipient="Enzo@aranciatravel.com",
                source_message=source,
                body="Diferencia",
                attachments=[],
            ),
            "draft",
        )
        payload = create.call_args.kwargs["body"]["message"]
        self.assertEqual(payload["threadId"], "original-thread")
        message = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(payload["raw"])
        )
        self.assertEqual(message["Subject"], "Re: Factura Arancia Services SRL")
        self.assertEqual(message["In-Reply-To"], "<original@example.com>")
        self.assertEqual(message["References"], "<previous@example.com> <original@example.com>")
        self.assertEqual(message["To"], "Enzo@aranciatravel.com")


if __name__ == "__main__":
    unittest.main()
