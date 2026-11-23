import os
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from bot_newsan import cargador_facturas as loader
from bot_newsan.extractor_factura import FILENAME_CODE_PATTERN, extract_items


class PgaSessionTests(unittest.TestCase):
    def browser(self, *, login_visible: bool):
        playwright = MagicMock()
        context = playwright.chromium.launch_persistent_context.return_value
        page = MagicMock()
        context.pages = [page]

        username_input = MagicMock()
        if not login_visible:
            username_input.wait_for.side_effect = PlaywrightTimeoutError("sesion existente")
        password_input = MagicMock()
        next_button = MagicMock()
        home_link = MagicMock()
        home_link.is_visible.return_value = False
        create_invoice_link = MagicMock()

        def get_by_role(role, **kwargs):
            name = kwargs.get("name")
            if role == "textbox" and name == "Username":
                return username_input
            if role == "textbox" and name == "Password":
                return password_input
            if role == "button" and name == "Next":
                return next_button
            if role == "link" and name == "Página Inicial":
                return home_link
            if role == "link":
                return create_invoice_link
            raise AssertionError((role, kwargs))

        page.get_by_role.side_effect = get_by_role
        return (
            playwright,
            context,
            page,
            username_input,
            password_input,
            next_button,
            create_invoice_link,
        )

    def test_reuses_persistent_session_without_reading_credentials(self):
        playwright, context, page, username, password, next_button, create_link = self.browser(
            login_visible=False
        )
        with patch.dict(os.environ, {"PGA_URL": "https://pga.example"}, clear=True):
            returned_context, returned_page = loader.open_oracle(playwright)

        self.assertIs(returned_context, context)
        self.assertIs(returned_page, page)
        playwright.chromium.launch_persistent_context.assert_called_once_with(
            str(loader.PGA_PROFILE_DIR), headless=False, slow_mo=1200
        )
        username.fill.assert_not_called()
        password.fill.assert_not_called()
        next_button.click.assert_not_called()
        create_link.click.assert_called_once_with(timeout=60000)

    def test_logs_in_and_leaves_time_for_email_verification(self):
        playwright, _context, _page, username, password, next_button, _create_link = self.browser(
            login_visible=True
        )
        environment = {
            "PGA_URL": "https://pga.example",
            "PGA_USERNAME": "usuario",  # gitleaks:allow - usuario ficticio para el navegador simulado.
            "PGA_PASSWORD": "clave",  # gitleaks:allow - clave ficticia para el navegador simulado.
        }
        with patch.dict(os.environ, environment, clear=True):
            loader.open_oracle(playwright)

        username.fill.assert_called_once_with("usuario")
        password.fill.assert_called_once_with("clave")
        next_button.click.assert_called_once_with()


class ExemptAndUntaxedInvoiceTests(unittest.TestCase):
    def test_uses_pga_grouped_tax_rounding_for_header_total(self):
        invoice = {
            "importe_total": "308052.83",
            "items": [
                {
                    "subtotal": 235893.39,
                    "subtotal_con_iva": 285431.00,
                    "alicuota_iva": "21%",
                },
                {
                    "subtotal": 18695.73,
                    "subtotal_con_iva": 22621.83,
                    "alicuota_iva": "21%",
                },
            ],
        }

        self.assertEqual(loader.get_pga_total(invoice), Decimal("308052.84"))

    def test_rejects_pga_total_difference_greater_than_one_cent(self):
        invoice = {
            "importe_total": "100.03",
            "items": [
                {
                    "subtotal": 100,
                    "subtotal_con_iva": 100,
                    "alicuota_iva": "Exento",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "mas de un centavo"):
            loader.get_pga_total(invoice)

    def test_selects_exact_fiscal_classification_when_results_share_a_prefix(self):
        page = MagicMock()
        classification_input = page.get_by_role.return_value
        option = page.locator.return_value.filter.return_value.first

        loader.select_fiscal_classification(page, "001_FACTURA_A")

        classification_input.fill.assert_called_once_with("001_FACTURA_A")
        classification_input.press.assert_called_once_with("Tab")
        page.locator.assert_called_once_with("td.xen:visible")
        pattern = page.locator.return_value.filter.call_args.kwargs["has_text"]
        self.assertIsNotNone(pattern.search("001_FACTURA_A"))
        self.assertIsNone(pattern.search("001_FACTURA_A_EXTRA"))
        option.click.assert_called_once_with()
        page.get_by_role.assert_any_call("button", name="Aceptar", exact=True)

    def test_fiscal_classification_without_results_requires_manual_confirmation(self):
        page = MagicMock()
        field = page.get_by_role.return_value
        option = page.locator.return_value.filter.return_value.first
        option.wait_for.side_effect = PlaywrightTimeoutError("sin lista")
        field.first.input_value.return_value = "201_FACTURA_CREDITO_A_MiPyMEs"

        with patch("builtins.input", return_value="SI"):
            loader.select_fiscal_classification(page, "201_FACTURA_CREDITO_A_MiPyMEs")
        option.click.assert_not_called()
        page.get_by_role.assert_called_once()

        with patch("builtins.input", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "no confirmada"):
                loader.select_fiscal_classification(page, "201_FACTURA_CREDITO_A_MiPyMEs")

        field.first.input_value.return_value = "OTRO"
        with patch("builtins.input", return_value="SI"):
            with self.assertRaisesRegex(RuntimeError, "no coincide"):
                loader.select_fiscal_classification(page, "201_FACTURA_CREDITO_A_MiPyMEs")

    def test_selects_exact_tax_result_when_oracle_opens_search_dialog(self):
        page = MagicMock()
        tax_input = page.get_by_role.return_value
        overlay = page.locator.return_value
        modal = overlay.locator.return_value
        option = modal.get_by_text.return_value.first
        accept = modal.get_by_role.return_value

        loader.select_tax_code(page, "ar_iva_general")

        tax_input.fill.assert_called_once_with("ar_iva_general")
        page.keyboard.press.assert_called_once_with("Tab")
        modal.get_by_text.assert_called_once_with("AR_IVA_GENERAL", exact=True)
        option.click.assert_called_once_with()
        modal.get_by_role.assert_called_once_with("button", name="Aceptar", exact=True)
        accept.click.assert_called_once_with()
        overlay.wait_for.assert_any_call(state="hidden", timeout=10000)

    def test_extracts_exempt_and_untaxed_lines(self):
        lines = [
            "Código Producto / Servicio Cantidad U. medida Precio Unit. % Bonif "
            "Subtotal AlicuotaIVA Subtotal c/IVA",
            "Servicio exento 1,00 un. 100,00 0,00 100,00 Exento 100,00",
            "Servicio no gravado 1,00 un. 50,00 0,00 50,00 No gravado 50,00",
            "CAE",
        ]

        items = extract_items(lines)

        self.assertEqual([item["alicuota_iva"] for item in items], ["Exento", "No gravado"])
        self.assertEqual(
            [loader.get_tax_code(item) for item in items], ["ar_iva_exento", "ar_iva_no"]
        )
        self.assertEqual([loader.get_line_amount(item) for item in items], [100.0, 50.0])

    def test_reads_document_code_from_downloaded_copy_filename(self):
        match = FILENAME_CODE_PATTERN.match("30714894346_203_00010_00000001 (1)")

        self.assertIsNotNone(match)
        self.assertEqual(match.group("code"), "203")

    def test_extracts_item_with_multiline_unit(self):
        lines = [
            "Código Producto / Servicio Cantidad U. medida Precio Unit. % Bonif "
            "Subtotal AlicuotaIVA Subtotal c/IVA",
            "Servicio 1,00 otras",
            "unidades",
            "100,00 0,00 100,00 10,5% 110,50",
            "CAE",
        ]

        items = extract_items(lines)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["unidad_medida"], "otras unidades")
        self.assertEqual(items[0]["alicuota_iva"], "10,5%")


if __name__ == "__main__":
    unittest.main()
