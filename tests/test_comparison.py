import unittest

import pandas as pd

from bot_carga.data_comparison import comparar_facturas_compra, comparar_facturas_venta


class ComparisonTests(unittest.TestCase):
    def test_only_missing_invoices_are_returned_without_mutating_inputs(self):
        for function, columns in (
            (
                comparar_facturas_compra,
                ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"],
            ),
            (comparar_facturas_venta, ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]),
        ):
            with self.subTest(function=function.__name__):
                afip = pd.DataFrame(
                    {"Factura": [" 001 ", "002", "003"], **{c: [10, 20, 30] for c in columns}}
                )
                system = pd.DataFrame(
                    {"FACTURA": ["001", "002"], **{c: [10, 999] for c in columns}}
                )
                original = afip.copy(deep=True)
                result = function(afip, system)
                self.assertEqual(result["Factura"].tolist(), ["003"])
                pd.testing.assert_frame_equal(afip, original)
                pd.testing.assert_frame_equal(
                    function(afip, system.iloc[:0]), original.assign(Factura=["001", "002", "003"])
                )

    def test_empty_inputs_keep_schema(self):
        columns = ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]
        afip = pd.DataFrame(columns=["Factura", *columns])
        system = pd.DataFrame(columns=["FACTURA", *columns])
        result = comparar_facturas_venta(afip, system)
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), list(afip.columns))
