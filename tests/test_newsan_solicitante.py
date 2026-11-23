import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot_newsan import cargador_facturas as loader
from bot_newsan.cargador_facturas import SOLICITANTE, load_invoices


class SolicitanteTests(unittest.TestCase):
    def test_empty_csv_does_not_open_browser(self):
        with (
            patch("sys.argv", ["cargador_facturas"]),
            patch.object(loader, "load_invoices", return_value=[]),
            patch.object(loader, "sync_playwright") as browser,
        ):
            loader.main()
            browser.assert_not_called()

    def test_review_displays_solicitante(self):
        with (
            patch.object(loader, "show_manual_review_alert") as alert,
            patch("builtins.input", return_value=""),
            patch("builtins.print") as output,
        ):
            loader.wait_for_manual_review(
                {"numero_comprobante": "123", "solicitante": "PEREZ, ANA"}, 1, 1
            )
            self.assertEqual(alert.call_args.kwargs["solicitante"], "PEREZ, ANA")
            output.assert_any_call("Solicitante: PEREZ, ANA")

    def test_csv_solicitante_and_default(self):
        for value in (None, "", "   ", "PEREZ, ANA"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "facturas.csv"
                fields = ["items_json"] + (["solicitante"] if value is not None else [])
                with path.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    row = {"items_json": "[]"}
                    if value is not None:
                        row["solicitante"] = value
                    writer.writerow(row)
                self.assertEqual(
                    load_invoices(path)[0]["solicitante"], (value or "").strip() or SOLICITANTE
                )
