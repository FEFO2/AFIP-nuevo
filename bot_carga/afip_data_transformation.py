from __future__ import annotations

import re
import string

import numpy as np
import pandas as pd


PURCHASE_AMOUNT_COLUMNS = [
    "NETO 0",
    "NETO 10.5",
    "IVA 10.5",
    "NETO 21",
    "IVA 21",
    "NO GRAVADO",
    "EXENTO",
    "IMPUESTOS",
    "IVA 2,5%",
    "IVA 5%",
    "IVA 27%",
    "TOTAL_NO_GRAVADO",
]

PURCHASE_EXCHANGE_RATE_COLUMNS = [
    "NETO 10.5",
    "IVA 10.5",
    "NETO 21",
    "IVA 21",
    "NO GRAVADO",
    "EXENTO",
    "IMPUESTOS",
]

SALES_AMOUNT_COLUMNS = [
    "NETO 0",
    "NETO 10.5",
    "IVA 10.5",
    "NETO 21",
    "IVA 21",
    "NO GRAVADO",
    "EXENTO",
    "IMPUESTOS",
    "IVA 2,5%",
    "IVA 5%",
    "IVA 27%",
    "TOTAL_NO_GRAVADO",
    "TOTAL_10.5",
    "TOTAL_21",
]

SALES_EXCHANGE_RATE_COLUMNS = [
    "NETO 0",
    "NETO 10.5",
    "IVA 10.5",
    "NETO 21",
    "IVA 21",
    "NO GRAVADO",
    "EXENTO",
    "IMPUESTOS",
    "TOTAL_10.5",
    "TOTAL_21",
]


def _sanitize_text_column(series: pd.Series) -> pd.Series:
    return series.str.translate(str.maketrans("", "", string.punctuation))


def _fill_amount_columns(data: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        data[column] = data[column].fillna(0)


def _apply_exchange_rate(data: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        data[column] = data[column] * data["Tipo Cambio"]


def transform_afip_inbound_invoices(data: pd.DataFrame) -> pd.DataFrame:
    transformed = data.copy()

    transformed["Tipo"] = transformed["Tipo"].astype("string").str[-9:]
    transformed["Tipo2"] = transformed["Tipo"].str[:7]
    transformed["Tipo3"] = transformed["Tipo"].str[-1:]

    transformed["Punto de Venta"] = transformed["Punto de Venta"].astype(str).str.zfill(5)
    transformed["NÃºmero Desde"] = transformed["NÃºmero Desde"].astype(str).str.zfill(8)
    transformed["Factura"] = transformed["Punto de Venta"] + "-" + transformed["NÃºmero Desde"]

    transformed["DenominaciÃ³n Emisor"] = _sanitize_text_column(transformed["DenominaciÃ³n Emisor"])
    transformed["Proveedor"] = transformed["DenominaciÃ³n Emisor"].str[:35]
    transformed["CUIT"] = transformed["Nro. Doc. Emisor"].astype(str)

    transformed["NETO 10.5"] = transformed["Neto Grav. IVA 10,5%"]
    transformed["IVA 10.5"] = transformed["IVA 10,5%"]
    transformed["NETO 21"] = transformed["Neto Grav. IVA 21%"]
    transformed["IVA 21"] = transformed["IVA 21%"]
    transformed["NO GRAVADO"] = transformed["Neto No Gravado"]
    transformed["EXENTO"] = transformed["Op. Exentas"]
    transformed["IMPUESTOS"] = transformed["Otros Tributos"]
    transformed["NETO 0"] = transformed["Neto Grav. IVA 0%"]

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )

    _fill_amount_columns(transformed, PURCHASE_AMOUNT_COLUMNS)
    _apply_exchange_rate(transformed, PURCHASE_EXCHANGE_RATE_COLUMNS)

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )

    for column in ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21"]:
        transformed[column] = transformed[column].astype(str)

    credit_mask = transformed["Tipo2"] == "CrÃ©dito"
    for column in PURCHASE_AMOUNT_COLUMNS:
        transformed.loc[credit_mask, column] = -transformed.loc[credit_mask, column].astype(float)
        transformed[column] = transformed[column].astype(str)

    return transformed[
        [
            "Fecha",
            "Tipo2",
            "Tipo3",
            "Factura",
            "Proveedor",
            "CUIT",
            "NETO 10.5",
            "NETO 21",
            "IVA 10.5",
            "IVA 21",
            "TOTAL_NO_GRAVADO",
        ]
    ].copy()


def build_afip_inbound_report_data(data: pd.DataFrame) -> pd.DataFrame:
    transformed = transform_afip_inbound_invoices(data).copy()

    for column in ["NETO 10.5", "NETO 21", "IVA 10.5", "IVA 21", "TOTAL_NO_GRAVADO"]:
        transformed[column] = pd.to_numeric(transformed[column], errors="coerce").fillna(0)

    transformed["TOTAL_FACTURADO"] = (
        transformed["NETO 10.5"]
        + transformed["NETO 21"]
        + transformed["IVA 10.5"]
        + transformed["IVA 21"]
        + transformed["TOTAL_NO_GRAVADO"]
    )

    return transformed[
        [
            "Fecha",
            "Factura",
            "Tipo2",
            "NETO 10.5",
            "NETO 21",
            "IVA 10.5",
            "IVA 21",
            "TOTAL_NO_GRAVADO",
            "TOTAL_FACTURADO",
        ]
    ].copy()


def transform_afip_outbound_invoices(data: pd.DataFrame) -> pd.DataFrame:
    transformed = data.copy()

    transformed["codigo_fc"] = [int(re.match(r"(\d+)", value).group(1)) for value in transformed["Tipo"]]
    transformed["Tipo"] = transformed["Tipo"].astype("string").str[-9:]
    transformed["Tipo2"] = transformed["Tipo"].str[:7]
    transformed["Tipo3"] = transformed["Tipo"].str[-1:]

    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"].isin([1, 6, 11]),
        "Factura",
        "Credito",
    )
    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"] == 201,
        "Pyme_fc",
        transformed["tipo2_new"],
    )
    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"] == 203,
        "Pyme_nc",
        transformed["tipo2_new"],
    )

    transformed["tipo3_new"] = np.where(transformed["codigo_fc"].isin([1, 3, 201, 203]), "A", "C")
    transformed["tipo3_new"] = np.where(transformed["codigo_fc"].isin([6, 8]), "B", transformed["tipo3_new"])

    transformed["Punto de Venta"] = transformed["Punto de Venta"].astype(str).str.zfill(5)
    transformed["NÃºmero Desde"] = transformed["NÃºmero Desde"].astype(str).str.zfill(8)
    transformed["FacturaReporte"] = transformed["Punto de Venta"] + "-" + transformed["NÃºmero Desde"]
    transformed["Factura"] = transformed["NÃºmero Desde"].astype(int)

    transformed["DenominaciÃ³n Receptor"] = _sanitize_text_column(transformed["DenominaciÃ³n Receptor"])
    transformed["Cliente"] = transformed["DenominaciÃ³n Receptor"].str[:35]
    transformed["CUIT"] = transformed["Nro. Doc. Receptor"].astype(str)

    transformed["NETO 10.5"] = transformed["Neto Grav. IVA 10,5%"]
    transformed["IVA 10.5"] = transformed["IVA 10,5%"]
    transformed["NETO 21"] = transformed["Neto Grav. IVA 21%"]
    transformed["IVA 21"] = transformed["IVA 21%"]
    transformed["NO GRAVADO"] = transformed["Neto No Gravado"]
    transformed["EXENTO"] = transformed["Op. Exentas"]
    transformed["IMPUESTOS"] = transformed["Otros Tributos"]
    transformed["NETO 0"] = transformed["Neto Grav. IVA 0%"]

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )
    transformed["TOTAL_10.5"] = round(transformed["NETO 10.5"] + transformed["IVA 10.5"], 2)
    transformed["TOTAL_21"] = round(transformed["NETO 21"] + transformed["IVA 21"], 2)

    _fill_amount_columns(transformed, SALES_AMOUNT_COLUMNS)
    _apply_exchange_rate(transformed, SALES_EXCHANGE_RATE_COLUMNS)

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )

    for column in ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_21", "TOTAL_10.5"]:
        transformed[column] = transformed[column].astype(str)

    credit_mask = (transformed["tipo2_new"] == "Credito") | (transformed["tipo2_new"] == "Pyme_nc")
    for column in SALES_AMOUNT_COLUMNS:
        transformed.loc[credit_mask, column] = -transformed.loc[credit_mask, column].astype(float)
        transformed[column] = transformed[column].astype(str)

    return transformed[
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
        ]
    ].copy()


def build_afip_outbound_report_data(data: pd.DataFrame) -> pd.DataFrame:
    transformed = data.copy()

    transformed["codigo_fc"] = [int(re.match(r"(\d+)", value).group(1)) for value in transformed["Tipo"]]
    transformed["Tipo"] = transformed["Tipo"].astype("string").str[-9:]

    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"].isin([1, 6, 11]),
        "Factura",
        "Credito",
    )
    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"] == 201,
        "Pyme_fc",
        transformed["tipo2_new"],
    )
    transformed["tipo2_new"] = np.where(
        transformed["codigo_fc"] == 203,
        "Pyme_nc",
        transformed["tipo2_new"],
    )

    transformed["Punto de Venta"] = transformed["Punto de Venta"].astype(str).str.zfill(5)
    transformed["NÃºmero Desde"] = transformed["NÃºmero Desde"].astype(str).str.zfill(8)
    transformed["FacturaReporte"] = transformed["Punto de Venta"] + "-" + transformed["NÃºmero Desde"]
    transformed["Factura"] = transformed["NÃºmero Desde"].astype(int).astype(str)

    transformed["NETO 10.5"] = transformed["Neto Grav. IVA 10,5%"]
    transformed["IVA 10.5"] = transformed["IVA 10,5%"]
    transformed["NETO 21"] = transformed["Neto Grav. IVA 21%"]
    transformed["IVA 21"] = transformed["IVA 21%"]
    transformed["NO GRAVADO"] = transformed["Neto No Gravado"]
    transformed["EXENTO"] = transformed["Op. Exentas"]
    transformed["IMPUESTOS"] = transformed["Otros Tributos"]
    transformed["NETO 0"] = transformed["Neto Grav. IVA 0%"]

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )
    transformed["TOTAL_10.5"] = round(transformed["NETO 10.5"] + transformed["IVA 10.5"], 2)
    transformed["TOTAL_21"] = round(transformed["NETO 21"] + transformed["IVA 21"], 2)

    _fill_amount_columns(transformed, SALES_AMOUNT_COLUMNS)
    _apply_exchange_rate(transformed, SALES_EXCHANGE_RATE_COLUMNS)

    transformed["TOTAL_NO_GRAVADO"] = (
        transformed["NO GRAVADO"]
        + transformed["EXENTO"]
        + transformed["IMPUESTOS"]
        + transformed["NETO 0"]
    )
    transformed["TOTAL_FACTURADO"] = (
        transformed["TOTAL_10.5"] + transformed["TOTAL_21"] + transformed["TOTAL_NO_GRAVADO"]
    )

    credit_mask = (transformed["tipo2_new"] == "Credito") | (transformed["tipo2_new"] == "Pyme_nc")
    for column in SALES_AMOUNT_COLUMNS:
        transformed.loc[credit_mask, column] = -transformed.loc[credit_mask, column].astype(float)

    transformed.loc[credit_mask, "TOTAL_FACTURADO"] = -transformed.loc[credit_mask, "TOTAL_FACTURADO"].astype(
        float
    )

    return transformed[
        [
            "Fecha",
            "Factura",
            "FacturaReporte",
            "tipo2_new",
            "NETO 10.5",
            "NETO 21",
            "IVA 10.5",
            "IVA 21",
            "TOTAL_NO_GRAVADO",
            "TOTAL_FACTURADO",
        ]
    ].copy()

