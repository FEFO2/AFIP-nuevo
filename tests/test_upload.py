import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from bot_carga import data_upload as upload


class UploadTests(unittest.TestCase):
    def test_empty_data_does_not_read_credentials_or_start_browser(self):
        for function in (upload.cargar_facturas_compra, upload.cargar_facturas_ventas):
            with (
                self.subTest(function=function.__name__),
                patch.object(upload, "load_arancia_settings") as settings,
                patch.object(upload, "sync_playwright") as playwright,
            ):
                data = pd.DataFrame(columns=["Factura"])
                pd.testing.assert_frame_equal(function(data), data)
                settings.assert_not_called()
                playwright.assert_not_called()

    def test_dispatch_and_cleanup_on_success_or_failure(self):
        data = pd.DataFrame({"Factura": ["0001-00000001"]})
        for function, method in (
            (upload.cargar_facturas_compra, "upload_purchase_invoices"),
            (upload.cargar_facturas_ventas, "upload_sales_invoices"),
        ):
            for fails in (False, True):
                with (
                    self.subTest(method=method, fails=fails),
                    patch.object(upload, "load_arancia_settings", return_value=MagicMock()),
                    patch.object(upload, "sync_playwright") as playwright,
                    patch.object(upload, "AranciaPlaywrightClient") as client,
                ):
                    browser = (
                        playwright.return_value.__enter__.return_value.chromium.launch.return_value
                    )
                    action = getattr(client.return_value, method)
                    action.return_value = data
                    if fails:
                        action.side_effect = RuntimeError("test failure")
                        with self.assertRaises(RuntimeError):
                            function(data)
                    else:
                        self.assertIs(function(data), data)
                    action.assert_called_once_with(data)
                    browser.new_context.return_value.close.assert_called_once()
                    browser.close.assert_called_once()
