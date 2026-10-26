from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from bot_revision_facturas.invoice_parser import parse_invoice_text


class InvoiceParserTests(unittest.TestCase):
    def test_extracts_invoice_ticket_and_subtotal(self) -> None:
        invoice = parse_invoice_text(
            """FACTURA A
Fecha de Emision: 18/10/2026
Nro: 8 - 148974
Moneda: USD
Nro TKT Tarifa Imp OC Sub-Total
5892884827 500,00 40,00 12,40 552,40
""",
            Path("factura.pdf"),
        )
        self.assertEqual(invoice.number, "0008-00148974")
        self.assertEqual(invoice.tickets[0].number, "5892884827")
        self.assertEqual(invoice.tickets[0].billed_amount, Decimal("552.40"))

    def test_invoice_without_ticket_table_is_concepts_only(self) -> None:
        invoice = parse_invoice_text(
            "FACTURA A\nFecha de Emision: 18/10/2026\nNro: 8 - 1\nMoneda: USD\nServicio terrestre 100,00",
            Path("conceptos.pdf"),
        )
        self.assertFalse(invoice.has_ticket_table)
        self.assertEqual(invoice.tickets, ())

    def test_detects_credit_note(self) -> None:
        invoice = parse_invoice_text("NOTA DE CREDITO A\nNro: 8 - 99", Path("nc.pdf"))
        self.assertEqual(invoice.kind, "credit_note")

    def test_extracts_realistic_carnival_rows_with_thousands(self) -> None:
        invoice = parse_invoice_text(
            """FACTURA ELECTRONICA
Fecha de Emision: 16/10/2026 Nro: 0008 - 00161239
Moneda: USD
Pax Ruta Salida Cia Cl Nro TKT Tarifa Imp. O.C. Sub-Total
20/11/26 KL J 3534591226 9461.00 2809.30 0 12,270.30
20/11/26 KL J 3534591227 0 0 0 0.00
""",
            Path("FCE_A_11738_161239.pdf"),
        )
        self.assertEqual(len(invoice.tickets), 2)
        self.assertEqual(invoice.tickets[0].billed_amount, Decimal("12270.30"))


if __name__ == "__main__":
    unittest.main()
