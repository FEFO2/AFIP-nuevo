import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from bot_facturador import invoice_process as invoices

HEADER = "condicion_iva,tipo_doc,num_doc,concepto,precio,iva,dirección\n"
ROW = "Consumidor final,DNI,00000000,Prueba,10,21%,Calle ficticia\n"


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.csv = self.root / "input.csv"
        self.csv.write_text(HEADER + ROW, encoding="utf-8-sig")

    def test_csv_encodings_and_required_columns(self):
        for encoding in ("utf-8-sig", "latin-1"):
            with self.subTest(encoding=encoding):
                self.csv.write_text(HEADER + ROW, encoding=encoding)
                self.assertEqual(
                    invoices.cargar_facturas(self.csv)[0]["direccion"], "Calle ficticia"
                )
        self.csv.write_text("concepto\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Faltan columnas"):
            invoices.cargar_facturas(self.csv)

    def test_invalid_later_row_stops_before_browser_opens(self):
        self.csv.write_text(HEADER + ROW + ROW.replace("21%", "no soportado"), encoding="utf-8")
        playwright = MagicMock()
        with self.assertRaises(ValueError):
            invoices.run(playwright, invoice_type="A", csv_path=self.csv, invoice_date="01/01/2026")
        playwright.chromium.launch.assert_not_called()

    def test_invalid_date_stops_before_browser_opens(self):
        playwright = MagicMock()
        with self.assertRaises(ValueError):
            invoices.run(playwright, invoice_type="A", csv_path=self.csv, invoice_date="31/02/2026")
        playwright.chromium.launch.assert_not_called()

    def test_a_and_b_preserve_type_currency_and_document_selection(self):
        for kind, code, foreign_currency in (("A", "10", False), ("B", "19", True)):
            with self.subTest(kind=kind):
                playwright = MagicMock()
                browser = playwright.chromium.launch.return_value
                context = browser.new_context.return_value
                page = context.new_page.return_value
                invoice_page = page.expect_popup.return_value.__enter__.return_value.value
                download = invoice_page.expect_download.return_value.__enter__.return_value.value
                download.suggested_filename = "invoice.pdf"
                with (
                    patch.object(invoices, "load_environment"),
                    patch.object(invoices, "_get_required_env", return_value="test-value"),
                ):
                    invoices.run(
                        playwright,
                        invoice_type=kind,
                        csv_path=self.csv,
                        invoice_date="01/01/2026",
                        downloads_dir=self.root,
                    )
                self.assertIn(call.locator("#universocomprobante"), invoice_page.mock_calls)
                self.assertIn(call.locator().select_option(code), invoice_page.mock_calls)
                self.assertEqual(
                    call.get_by_text("Moneda Extranjera") in invoice_page.mock_calls,
                    foreign_currency,
                )
                self.assertEqual(
                    call.locator("#idtipodocreceptor") in invoice_page.mock_calls, kind == "B"
                )
                download.save_as.assert_called_once_with(self.root / "invoice.pdf")
                context.close.assert_called_once()
                browser.close.assert_called_once()

    def test_browser_closes_if_login_fails(self):
        playwright = MagicMock()
        browser = playwright.chromium.launch.return_value
        context = browser.new_context.return_value
        context.new_page.return_value.goto.side_effect = RuntimeError("test failure")
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            self.assertRaises(RuntimeError),
        ):
            invoices.run(
                playwright,
                invoice_type="A",
                csv_path=self.csv,
                invoice_date="01/01/2026",
                downloads_dir=self.root,
            )
        context.close.assert_called_once()
        browser.close.assert_called_once()
