import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pandas as pd

from bot_carga import data_upload as upload
from bot_carga.cargar_ventas_csv import read_sales_csv


class UploadTests(unittest.TestCase):
    def test_read_sales_csv_validates_and_normalizes_bot_format(self):
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "ventas.csv"
            csv_path.write_text(
                "Fecha,tipo2_new,tipo3_new,Factura,FacturaReporte,Cliente,CUIT,"
                "TOTAL_10.5,TOTAL_21,TOTAL_NO_GRAVADO\n"
                "31/10/2026,Factura,A,467,00010-00000467,D ONOFRIO DARIO OSCAR,"
                "20265624430,0,0,3897600\n",
                encoding="utf-8-sig",
            )

            data = read_sales_csv(csv_path)

        self.assertEqual(
            list(data.columns),
            [
                "Fecha",
                "tipo2_new",
                "tipo3_new",
                "Factura",
                "FacturaReporte",
                "Cliente",
                "CUIT",
                "TOTAL_10.5",
                "TOTAL_21",
                "TOTAL_NO_GRAVADO",
            ],
        )
        self.assertEqual(data.loc[0, "Fecha"], "31/10/2026")
        self.assertEqual(data.loc[0, "Factura"], 467)
        self.assertEqual(data.loc[0, "CUIT"], "20265624430")

    def test_read_sales_csv_rejects_missing_columns(self):
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "ventas.csv"
            csv_path.write_text("Fecha,Factura\n31/10/2026,467\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Faltan columnas"):
                read_sales_csv(csv_path)

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
