import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from bot_facturador import invoice_process as invoices

HEADER = "condicion_iva,tipo_doc,num_doc,concepto,precio,iva,dirección\n"
A_ROW = "Responsable inscripto,CUIT,20000000000,Prueba,10,21%,Calle ficticia\n"
B_ROW = "Consumidor final,DNI,12345678,Prueba,10,21%,Calle ficticia\n"
CF_HEADER = "Monto (USD),Monto (ARS),Razon Social,categoria,Column 10,DOC\n"
CF_ROW = '1,"10,00",PERSONA PRUEBA,consumidor final,DNI,12345678\n'


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.csv = self.root / "input.csv"
        self.csv.write_text(HEADER + B_ROW, encoding="utf-8-sig")

    def run_arguments(self, kind="B", **overrides):
        arguments = {
            "invoice_type": kind,
            "csv_path": self.csv,
            "invoice_date": "31/10/2026" if kind == "A" else "30/10/2026",
            "service_from": "01/10/2026",
            "service_to": "31/10/2026" if kind == "A" else "30/10/2026",
            "downloads_dir": self.root / f"downloads-{kind}",
        }
        arguments.update(overrides)
        return arguments

    def summary(
        self,
        kind,
        document,
        invoice_date,
        service_to,
        *,
        currency=None,
        concept="Prueba",
        iva="21%",
        receptor=None,
    ):
        currency = currency or ("ARS" if kind == "A" else "USD")
        document_label = "CUIT" if kind == "A" else "DNI"
        receptor_text = f"Razón Social: {receptor}" if receptor else ""
        return f"""
        Tipo de comprobante: Factura {kind}
        Punto de venta: 2
        Moneda: {currency}
        Fecha del Comprobante: {invoice_date}
        Desde: 01/10/2026
        Hasta: {service_to}
        Vto. para el pago: {invoice_date}
        {document_label}: {document}
        {receptor_text}
        Descripción: {concept}
        Precio: 10,00
        IVA: {iva}
        """

    def browser(self, summary, confirmation=None):
        playwright = MagicMock()
        browser = playwright.chromium.launch.return_value
        context = browser.new_context.return_value
        login_page = context.new_page.return_value
        invoice_page = login_page.expect_popup.return_value.__enter__.return_value.value

        date_controls = {
            "Fecha del Comprobante": MagicMock(),
            "Desde": MagicMock(),
            "Hasta": MagicMock(),
            "Vencimiento": MagicMock(),
        }
        values = re.findall(r"\d{2}/\d{2}/\d{4}", summary)
        date_controls["Fecha del Comprobante"].input_value.return_value = values[0]
        date_controls["Desde"].input_value.return_value = values[1]
        date_controls["Hasta"].input_value.return_value = values[2]
        date_controls["Vencimiento"].input_value.return_value = values[3]
        default_control = MagicMock()
        checkbox_control = MagicMock()
        confirm_control = MagicMock()

        def get_by_role(role, name=None, **_kwargs):
            if role == "textbox" and name in date_controls:
                return date_controls[name]
            if role == "textbox" and isinstance(name, re.Pattern):
                return date_controls["Vencimiento"]
            if role == "checkbox" and name == "Contado":
                return checkbox_control
            if role == "button" and name == "Confirmar" and _kwargs.get("exact"):
                return confirm_control
            return default_control

        controls = {}
        body = MagicMock()
        body.inner_text.side_effect = [summary] + ([confirmation] if confirmation else [])
        controls["__body"] = body
        controls["__checkbox"] = checkbox_control
        controls["__confirm"] = confirm_control

        def locator(selector):
            if selector == "body":
                return body
            control = controls.setdefault(selector, MagicMock())
            if selector == "#domicilioreceptor":
                control.input_value.return_value = ""
            return control

        invoice_page.get_by_role.side_effect = get_by_role
        invoice_page.locator.side_effect = locator
        download = invoice_page.expect_download.return_value.__enter__.return_value.value
        download.save_as.side_effect = lambda path: Path(path).write_bytes(b"%PDF-test")
        reader = self.enterContext(patch.object(invoices, "PdfReader"))
        reader.return_value.pages = [MagicMock()]
        reader.return_value.pages[0].extract_text.return_value = confirmation or ""
        return playwright, invoice_page, controls, default_control

    def test_csv_encodings_and_required_columns(self):
        for encoding in ("utf-8-sig", "latin-1"):
            with self.subTest(encoding=encoding):
                self.csv.write_text(HEADER + B_ROW, encoding=encoding)
                self.assertEqual(
                    invoices.cargar_facturas(self.csv)[0]["direccion"], "Calle ficticia"
                )
        self.csv.write_text("concepto\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Faltan columnas"):
            invoices.cargar_facturas(self.csv)

    def test_consumer_final_export_is_mapped_to_fixed_invoice_data(self):
        self.csv.write_text(CF_HEADER + CF_ROW, encoding="utf-8-sig")
        factura = invoices.cargar_facturas(self.csv)[0]
        self.assertEqual(factura["condicion_iva"], "consumidor final")
        self.assertEqual(factura["tipo_doc"], "DNI")
        self.assertEqual(factura["num_doc"], "12345678")
        self.assertEqual(factura["concepto"], "INTERMEDIACIÓN DE SERVICIOS TURÍSTICOS")
        self.assertEqual(factura["iva"], "exento")
        self.assertEqual(factura["precio"], "10,00")
        self.assertEqual(factura["_fecha_emision"], "30/10/2026")

    def test_consumer_final_batch_rejects_november_and_wrong_fiscal_settings(self):
        self.csv.write_text(CF_HEADER + CF_ROW, encoding="utf-8-sig")
        cases = (
            {"invoice_date": "01/11/2026", "service_to": "01/11/2026"},
            {"currency": "USD"},
            {"point_of_sale": "3"},
            {"invoice_type": "A", "invoice_date": "31/10/2026"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                arguments = self.run_arguments(currency="ARS")
                arguments.update(overrides)
                playwright = MagicMock()
                with self.assertRaisesRegex(ValueError, "LOTE BLOQUEADO"):
                    invoices.run(playwright, **arguments)
                playwright.chromium.launch.assert_not_called()

    def test_invalid_later_row_stops_before_browser_opens(self):
        self.csv.write_text(HEADER + B_ROW + B_ROW.replace("21%", "no soportado"))
        playwright = MagicMock()
        with self.assertRaises(ValueError):
            invoices.run(playwright, **self.run_arguments())
        playwright.chromium.launch.assert_not_called()

    def test_date_rules_and_minimums_stop_before_browser(self):
        for kind, invalid_date, minimum in (
            ("A", "30/10/2026", "31/10/2026"),
            ("B", "29/10/2026", "30/10/2026"),
        ):
            self.csv.write_text(HEADER + (A_ROW if kind == "A" else B_ROW))
            with self.subTest(kind=kind):
                playwright = MagicMock()
                with self.assertRaisesRegex(ValueError, minimum):
                    invoices.run(
                        playwright,
                        **self.run_arguments(
                            kind,
                            invoice_date=invalid_date,
                            service_to=invalid_date,
                        ),
                    )
                playwright.chromium.launch.assert_not_called()

        self.csv.write_text(HEADER + B_ROW)
        invalid_cases = (
            ({"service_from": "31/10/2026", "service_to": "01/10/2026"}, "desde"),
            ({"payment_due": "29/10/2026"}, "vencimiento"),
        )
        for arguments, message in invalid_cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                invoices.run(MagicMock(), **self.run_arguments(**arguments))

    def test_future_service_end_is_allowed(self):
        with (
            patch("builtins.input", return_value="NO"),
            self.assertRaisesRegex(RuntimeError, "cancelada"),
        ):
            invoices.run(
                MagicMock(),
                **self.run_arguments(service_to="10/11/2026", payment_due="30/10/2026"),
            )

    def test_invoice_matrix_documents_and_amounts_are_validated(self):
        cases = (
            ("A", B_ROW, "condicion_iva"),
            ("A", A_ROW.replace("CUIT,20000000000", "DNI,12345678"), "CUIT"),
            ("B", B_ROW.replace("12345678", "12O45678"), "números"),
            ("B", B_ROW.replace(",10,21%", ",-10,21%"), "Importe"),
            ("B", B_ROW.replace(",10,21%", ",10.123,21%"), "dos decimales"),
        )
        for kind, row, message in cases:
            with self.subTest(kind=kind, message=message):
                self.csv.write_text(HEADER + row)
                with self.assertRaisesRegex(ValueError, message):
                    invoices.run(MagicMock(), **self.run_arguments(kind))

        self.csv.write_text(
            HEADER + A_ROW.replace("Responsable inscripto", "Responsable monotributo")
        )
        with patch("builtins.input", return_value="NO"), self.assertRaises(RuntimeError):
            invoices.run(MagicMock(), **self.run_arguments("A"))

    def test_confirmation_requires_complete_fingerprint(self):
        arguments = dict(
            invoice_type="B",
            invoice_date="30/10/2026",
            service_from="01/10/2026",
            service_to="30/10/2026",
            payment_due="30/10/2026",
            point_of_sale="2",
            currency="USD",
            csv_path=self.csv,
            total=1,
            review_only=False,
            batch_id="deadbeef",
        )
        with (
            patch("builtins.input", return_value="30/10/2026"),
            self.assertRaisesRegex(RuntimeError, "cancelada"),
        ):
            invoices.confirmar_lote(**arguments)
        with patch("builtins.input", return_value="EMITIR B-2 USD 30/10/2026 1 deadbeef"):
            invoices.confirmar_lote(**arguments)

    def test_summary_checks_labeled_values(self):
        page = MagicMock()
        page.locator.return_value.inner_text.return_value = self.summary(
            "B", "12345678", "30/10/2026", "30/10/2026"
        )
        factura = invoices.cargar_facturas(self.csv)[0]
        invoices.verificar_resumen(
            page,
            invoice_type="B",
            point_of_sale="2",
            currency="USD",
            invoice_date="30/10/2026",
            service_from="01/10/2026",
            service_to="30/10/2026",
            payment_due="30/10/2026",
            factura=factura,
        )
        page.locator.return_value.inner_text.return_value = (
            self.summary("B", "12345678", "30/10/2026", "30/10/2026")
            .replace("Fecha del Comprobante: 30/10/2026", "")
            .replace("Descripción:", "Producto/Servicio:")
            .replace("IVA: 21%", f"Alícuota IVA {'cabecera ' * 30}21%")
        )
        invoices.verificar_resumen(
            page,
            invoice_type="B",
            point_of_sale="2",
            currency="USD",
            invoice_date="30/10/2026",
            service_from="01/10/2026",
            service_to="30/10/2026",
            payment_due="30/10/2026",
            factura=factura,
        )
        page.locator.return_value.inner_text.return_value = self.summary(
            "B", "12345678", "30/10/2026", "30/10/2026"
        ).replace("Moneda: USD", "")
        invoices.verificar_resumen(
            page,
            invoice_type="B",
            point_of_sale="2",
            currency="ARS",
            invoice_date="30/10/2026",
            service_from="01/10/2026",
            service_to="30/10/2026",
            payment_due="30/10/2026",
            factura=factura,
        )
        page.locator.return_value.inner_text.return_value = self.summary(
            "B", "12345678", "30/10/2026", "30/10/2026"
        )
        with self.assertRaisesRegex(RuntimeError, "moneda extranjera"):
            invoices.verificar_resumen(
                page,
                invoice_type="B",
                point_of_sale="2",
                currency="ARS",
                invoice_date="30/10/2026",
                service_from="01/10/2026",
                service_to="30/10/2026",
                payment_due="30/10/2026",
                factura=factura,
            )
        page.locator.return_value.inner_text.return_value = self.summary(
            "B", "12.345.678", "30/10/2026", "30/10/2026"
        ).replace("IVA: 21%", "IVA: 21,00%")
        invoices.verificar_resumen(
            page,
            invoice_type="B",
            point_of_sale="2",
            currency="USD",
            invoice_date="30/10/2026",
            service_from="01/10/2026",
            service_to="30/10/2026",
            payment_due="30/10/2026",
            factura=factura,
        )
        page.locator.return_value.inner_text.return_value = self.summary(
            "B", "87654321", "30/10/2026", "30/10/2026"
        )
        with self.assertRaisesRegex(RuntimeError, "receptor"):
            invoices.verificar_resumen(
                page,
                invoice_type="B",
                point_of_sale="2",
                currency="USD",
                invoice_date="30/10/2026",
                service_from="01/10/2026",
                service_to="30/10/2026",
                payment_due="30/10/2026",
                factura=factura,
            )

        self.csv.write_text(CF_HEADER + CF_ROW, encoding="utf-8-sig")
        factura = invoices.cargar_facturas(self.csv)[0]
        summary = self.summary(
            "B",
            "12345678",
            "30/10/2026",
            "30/10/2026",
            currency="ARS",
            concept=invoices.CONSUMIDOR_FINAL_CONCEPTO,
            iva="Exento",
            receptor="OTRA PERSONA",
        )
        page.locator.return_value.inner_text.return_value = summary
        with self.assertRaisesRegex(invoices.ReceptorNoVerificado, "nombre del receptor"):
            invoices.verificar_resumen(
                page,
                invoice_type="B",
                point_of_sale="2",
                currency="ARS",
                invoice_date="30/10/2026",
                service_from="01/10/2026",
                service_to="30/10/2026",
                payment_due="30/10/2026",
                factura=factura,
            )

    def test_full_run_saves_unique_pdf_and_idempotency_journal(self):
        for kind, row, document, invoice_date in (
            ("A", A_ROW, "20000000000", "31/10/2026"),
            ("B", B_ROW, "12345678", "30/10/2026"),
        ):
            with self.subTest(kind=kind):
                self.csv.write_text(HEADER + row)
                service_to = invoice_date
                summary = self.summary(kind, document, invoice_date, service_to)
                confirmation = "Comprobante Nro: 00002-00000001 CAE: 12345678901234"
                playwright, invoice_page, controls, _ = self.browser(summary, confirmation)
                with (
                    patch.object(invoices, "load_environment"),
                    patch.object(invoices, "_get_required_env", return_value="test-value"),
                    patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
                ):
                    invoices.run(
                        playwright,
                        **self.run_arguments(
                            kind,
                            invoice_date=invoice_date,
                            service_to=service_to,
                        ),
                    )
                self.assertEqual(controls["#puntodeventa"].select_option.call_args, call("2"))
                self.assertEqual(
                    controls["#universocomprobante"].select_option.call_args,
                    call("10" if kind == "A" else "19"),
                )
                controls["#detalle_precio1"].fill.assert_called_once_with("10.00")
                state = json.loads(
                    (self.root / f"downloads-{kind}" / "facturador_estado.json").read_text(
                        encoding="utf-8"
                    )
                )
                row_state = next(iter(state["runs"].values()))["filas"][0]
                self.assertTrue(Path(row_state["pdf"]).exists())
                self.assertEqual(row_state["estado"], "emitida")
                self.assertEqual(row_state["cae"], "12345678901234")
                self.assertEqual(row_state["documento"], document)
                self.assertEqual(row_state["importe"], "10")

                second_playwright = MagicMock()
                invoices.run(second_playwright, **self.run_arguments(kind))
                second_playwright.chromium.launch.assert_not_called()
                self.assertIn(
                    call.get_by_role("button", name="Confirmar", exact=True),
                    invoice_page.mock_calls,
                )

    def test_protected_batch_omits_invalid_document_and_continues(self):
        invalid = CF_ROW.replace("12345678", "12X45678")
        self.csv.write_text(CF_HEADER + invalid + CF_ROW, encoding="utf-8-sig")
        summary = self.summary(
            "B",
            "12345678",
            "30/10/2026",
            "30/10/2026",
            currency="ARS",
            concept=invoices.CONSUMIDOR_FINAL_CONCEPTO,
            iva="Exento",
            receptor="PERSONA PRUEBA",
        )
        confirmation = "Comprobante Nro: 00002-00000001 CAE: 12345678901234"
        playwright, invoice_page, _controls, _ = self.browser(summary, confirmation)
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
        ):
            invoices.run(playwright, **self.run_arguments(currency=None))

        state = json.loads(
            (self.root / "downloads-B" / "facturador_estado.json").read_text(encoding="utf-8")
        )
        rows = next(iter(state["runs"].values()))["filas"]
        self.assertEqual([row["estado"] for row in rows], ["omitida", "emitida"])
        self.assertEqual(invoice_page.wait_for_function.call_args.kwargs["arg"], "PERSONA PRUEBA")
        _controls["#domicilioreceptor"].fill.assert_called_once_with("-")
        self.assertEqual(_controls["__confirm"].click.call_count, 1)

    def test_arca_document_rejection_is_recorded_and_next_row_is_emitted(self):
        first = CF_ROW.replace("12345678", "87654321")
        self.csv.write_text(CF_HEADER + first + CF_ROW, encoding="utf-8-sig")
        summary = self.summary(
            "B",
            "12345678",
            "30/10/2026",
            "30/10/2026",
            currency="ARS",
            concept=invoices.CONSUMIDOR_FINAL_CONCEPTO,
            iva="Exento",
            receptor="PERSONA PRUEBA",
        )
        confirmation = "Comprobante Nro: 00002-00000001 CAE: 12345678901234"
        playwright, invoice_page, controls, _ = self.browser(summary, confirmation)
        invoice_page.wait_for_function.side_effect = [
            invoices.PlaywrightTimeoutError("rechazo"),
            None,
        ]
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
        ):
            invoices.run(playwright, **self.run_arguments(currency=None))

        state = json.loads(
            (self.root / "downloads-B" / "facturador_estado.json").read_text(encoding="utf-8")
        )
        rows = next(iter(state["runs"].values()))["filas"]
        self.assertEqual([row["estado"] for row in rows], ["omitida", "emitida"])
        self.assertIn("nombre esperado", rows[0]["motivo"])
        self.assertEqual(controls["__confirm"].click.call_count, 1)

    def test_protected_batch_rechecks_date_before_final_confirmation(self):
        self.csv.write_text(CF_HEADER + CF_ROW, encoding="utf-8-sig")
        summary = self.summary(
            "B",
            "12345678",
            "30/10/2026",
            "30/10/2026",
            currency="ARS",
            concept=invoices.CONSUMIDOR_FINAL_CONCEPTO,
            iva="Exento",
            receptor="PERSONA PRUEBA",
        )
        playwright, _invoice_page, controls, _ = self.browser(summary)
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
            patch.object(
                invoices,
                "_verificar_bloqueo_lote",
                side_effect=[None, ValueError("LOTE BLOQUEADO: fecha alterada")],
            ),
            self.assertRaisesRegex(ValueError, "fecha alterada"),
        ):
            invoices.run(playwright, **self.run_arguments(currency=None))
        controls["__confirm"].click.assert_not_called()

    def test_review_only_never_confirms_or_writes_state(self):
        summary = self.summary("B", "12345678", "30/10/2026", "30/10/2026")
        playwright, invoice_page, _controls, _default_control = self.browser(summary)
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
        ):
            invoices.run(playwright, **self.run_arguments(review_only=True))
        self.assertNotIn(
            call.get_by_role("button", name="Confirmar", exact=True), invoice_page.mock_calls
        )
        self.assertFalse((self.root / "downloads-B" / "facturador_estado.json").exists())

    def test_uncertain_confirmation_blocks_every_new_run(self):
        downloads = self.root / "downloads-B"
        downloads.mkdir()
        (downloads / "facturador_estado.json").write_text(
            json.dumps(
                {
                    "runs": {
                        "old": {
                            "parametros": {"tipo": "B", "punto_venta": "2"},
                            "filas": [{"estado": "confirmando"}],
                        }
                    }
                }
            )
        )
        playwright = MagicMock()
        with (
            patch("builtins.input", return_value=""),
            self.assertRaisesRegex(RuntimeError, "sigue bloqueada"),
        ):
            invoices.run(playwright, **self.run_arguments())
        playwright.chromium.launch.assert_not_called()

        state_path = downloads / "facturador_estado.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        with patch("builtins.input", return_value="EMITIDA 00002-00000001 12345678901234"):
            invoices._resolver_confirmaciones_inciertas(state_path, state)
        row = state["runs"]["old"]["filas"][0]
        self.assertEqual(row["estado"], "emitida")
        self.assertEqual(row["cae"], "12345678901234")

    def test_confirmation_data_must_include_number_and_cae(self):
        self.assertEqual(
            invoices._datos_confirmacion("Comprobante Nro: 00002-00000001 CAE: 12345678901234"),
            ("00002-00000001", "12345678901234"),
        )
        self.assertEqual(
            invoices._datos_confirmacion("Punto de Venta: 2 Comp. Nro.: 1 CAE: 12345678901234"),
            ("00002-00000001", "12345678901234"),
        )
        with self.assertRaisesRegex(RuntimeError, "manualmente"):
            invoices._datos_confirmacion("Operación aprobada")

    def test_pdf_is_preserved_when_confirmation_details_cannot_be_read(self):
        summary = self.summary("B", "12345678", "30/10/2026", "30/10/2026")
        playwright, _, _, _ = self.browser(summary, "sin datos")
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
            self.assertRaisesRegex(RuntimeError, "manualmente"),
        ):
            invoices.run(playwright, **self.run_arguments())
        path = self.root / "downloads-B" / "facturador_estado.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        row = next(iter(state["runs"].values()))["filas"][0]
        self.assertEqual(row["estado"], "confirmando")
        self.assertTrue(Path(row["pdf"]).is_file())
        with (
            patch("builtins.input", return_value="NO_EMITIDA"),
            self.assertRaisesRegex(RuntimeError, "PDF guardado"),
        ):
            invoices._resolver_confirmaciones_inciertas(path, state)

    def test_recovery_finds_pdf_saved_before_journal_update(self):
        path = self.root / "facturador_estado.json"
        pdf = self.root / "B_run123_1.pdf"
        pdf.write_bytes(b"%PDF-test")
        state = {
            "runs": {"run123": {"parametros": {"tipo": "B"}, "filas": [{"estado": "confirmando"}]}}
        }
        with (
            patch("builtins.input", return_value="NO_EMITIDA"),
            self.assertRaisesRegex(RuntimeError, "PDF guardado"),
        ):
            invoices._resolver_confirmaciones_inciertas(path, state)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["runs"]["run123"]["filas"][0]["pdf"], str(pdf.resolve()))

    def test_browser_closes_if_login_fails(self):
        playwright = MagicMock()
        browser = playwright.chromium.launch.return_value
        context = browser.new_context.return_value
        context.new_page.return_value.goto.side_effect = RuntimeError("test failure")
        with (
            patch.object(invoices, "load_environment"),
            patch.object(invoices, "_get_required_env", return_value="test-value"),
            patch("builtins.input", side_effect=lambda prompt: prompt.split("'")[1]),
            self.assertRaises(RuntimeError),
        ):
            invoices.run(playwright, **self.run_arguments())
        context.close.assert_called_once()
        browser.close.assert_called_once()
