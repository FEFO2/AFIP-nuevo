from __future__ import annotations

from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup


def _read_html_table(path_html: str) -> pd.DataFrame:
    with open(path_html, encoding="utf-8") as file:
        html = file.read()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        wrapped = f"<table>{soup}</table>"
        table = BeautifulSoup(wrapped, "html.parser").find("table")

    if table is None:
        raise ValueError(f"No se encontro ninguna tabla util en {path_html}")

    dataframe = pd.read_html(StringIO(str(table)))[0]
    dataframe.columns = dataframe.columns.str.strip().str.upper()
    return dataframe


def procesar_outbound_html(path_html: str) -> pd.DataFrame:
    df = _read_html_table(path_html)

    required_cols = ["FACTURA", "NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "NO GRAVADO"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el HTML de ventas: {missing}")

    df["TOTAL_10.5"] = df["NETO 10.5"] + df["IVA 10.5"]
    df["TOTAL_21"] = df["NETO 21"] + df["IVA 21"]
    df["TOTAL_NO_GRAVADO"] = df["NO GRAVADO"]

    result = df[["FACTURA", "TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]].copy()

    for col in ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)

    print(f"[OK] HTML de ventas procesado: {path_html} ({len(result)} filas).")
    return result


def procesar_inbound_html(path_html: str) -> pd.DataFrame:
    df = _read_html_table(path_html)
    df["TOTAL_NO_GRAVADO"] = df["NO GRAVADO"]

    required_cols = ["FACTURA", "NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el HTML de compras: {missing}")

    result = df[required_cols].copy()

    for col in ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"]:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)

    print(f"[OK] HTML de compras procesado: {path_html} ({len(result)} filas).")
    return result
