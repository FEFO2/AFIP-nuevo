from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from bot_revision_facturas.arancia_client import AranciaClient, AranciaSettings
from bot_revision_facturas.models import AranciaRow, Invoice, TicketLine
from bot_revision_facturas.rules import accepted_difference, compare_invoice, parse_money


class MoneyRulesTests(unittest.TestCase):
    def test_only_equal_or_five_plus_minus_one_cent_is_accepted(self) -> None:
        billed = Decimal("100.00")
        for system in (Decimal("100.00"), Decimal("95.01"), Decimal("95.00"), Decimal("94.99")):
            self.assertTrue(accepted_difference(billed, system)[0])
        for system in (Decimal("99.99"), Decimal("95.02"), Decimal("94.98")):
            self.assertFalse(accepted_difference(billed, system)[0])

    def test_money_parser_accepts_argentine_and_us_formats(self) -> None:
        self.assertEqual(parse_money("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_money("1,234.56"), Decimal("1234.56"))

    def test_comparison_keeps_matching_tickets_when_another_fails(self) -> None:
        invoice = Invoice(
            Path("invoice.pdf"),
            "invoice",
            "0008-00000123",
            None,
            "USD",
            (TicketLine("111111", Decimal("100.00")), TicketLine("222222", Decimal("200.00"))),
            True,
        )
        rows = {
            "111111": AranciaRow("111111", Decimal("95.00"), "", "one"),
            "222222": AranciaRow("222222", Decimal("180.00"), "", "two"),
        }
        checks = compare_invoice(invoice, rows)
        self.assertEqual([check.status for check in checks], ["accepted", "difference"])

    def test_partial_invoice_updates_only_the_matching_ticket(self) -> None:
        checked: list[str] = []
        filled: list[str] = []

        class FakeLocator:
            def __init__(self, selector: str) -> None:
                self.selector = selector

            def check(self) -> None:
                checked.append(self.selector)

            def fill(self, value: str) -> None:
                filled.append(value)

            def click(self) -> None:
                pass

        class FakeFrame:
            def locator(self, selector: str) -> FakeLocator:
                return FakeLocator(selector)

        class FakePage:
            def wait_for_load_state(self, _: str) -> None:
                pass

            def wait_for_timeout(self, _: int) -> None:
                pass

        invoice = Invoice(
            Path("invoice.pdf"),
            "invoice",
            "0008-00000123",
            None,
            "USD",
            (TicketLine("111111", Decimal("100.00")), TicketLine("222222", Decimal("200.00"))),
            True,
        )
        rows = {
            "111111": AranciaRow("111111", Decimal("95.00"), "", "one"),
            "222222": AranciaRow("222222", Decimal("180.00"), "", "two"),
        }
        frame = FakeFrame()
        client = AranciaClient(FakePage(), AranciaSettings("", "", ""))  # type: ignore[arg-type]
        client.table_frame = frame  # type: ignore[assignment]
        client.facturacion_frame = frame  # type: ignore[assignment]
        client.list_rows = lambda: rows  # type: ignore[method-assign]
        client._wait_for_child_frame = lambda *_: frame  # type: ignore[method-assign]

        result = client.process_invoice(invoice, dry_run=False)

        self.assertEqual(result.status, "partially_updated")
        self.assertEqual(checked, ['[id="one"]'])
        self.assertIn("0008-00000123", filled)


if __name__ == "__main__":
    unittest.main()
