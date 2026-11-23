from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .bookit_data_transformation import procesar_outbound_html
from .data_comparison import comparar_facturas_venta
from .data_upload import cargar_facturas_ventas
from .download_bookit_reports import run_download_arancia_reports
from .utils import PROJECT_ROOT, configure_logging, get_playwright_timeout_config

SALES_COLUMNS = [
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
AMOUNT_COLUMNS = ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]


def _valid_cuit(value: str) -> bool:
    if not re.fullmatch(r"\d{11}", value):
        return False
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    remainder = 11 - sum(int(digit) * weight for digit, weight in zip(value, weights)) % 11
    check_digit = 0 if remainder == 11 else 9 if remainder == 10 else remainder
    return check_digit == int(value[-1])


def read_sales_csv(csv_path: Path) -> pd.DataFrame:
    data = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        dtype={
            "Fecha": "string",
            "tipo2_new": "string",
            "tipo3_new": "string",
            "FacturaReporte": "string",
            "Cliente": "string",
            "CUIT": "string",
        },
    )
    missing = [column for column in SALES_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en el CSV de ventas: {missing}")

    data = data[SALES_COLUMNS].copy()
    if data.empty:
        raise ValueError("El CSV de ventas no contiene facturas.")

    text_columns = ["Fecha", "tipo2_new", "tipo3_new", "FacturaReporte", "Cliente", "CUIT"]
    for column in text_columns:
        data[column] = data[column].str.strip()
    if data[text_columns].isna().any().any() or data[text_columns].eq("").any().any():
        raise ValueError("El CSV de ventas contiene campos obligatorios vacios.")

    parsed_dates = pd.to_datetime(data["Fecha"], dayfirst=True, errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError("El CSV de ventas contiene fechas invalidas.")
    data["Fecha"] = parsed_dates.dt.strftime("%d/%m/%Y")

    data["Factura"] = pd.to_numeric(data["Factura"], errors="raise")
    if (data["Factura"] % 1 != 0).any() or (data["Factura"] <= 0).any():
        raise ValueError("La columna Factura debe contener numeros enteros positivos.")
    data["Factura"] = data["Factura"].astype("int64")

    for column in AMOUNT_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")
    if data[AMOUNT_COLUMNS].isna().any().any():
        raise ValueError("El CSV de ventas contiene importes vacios.")

    if not data["tipo3_new"].isin(["A", "B", "C"]).all():
        raise ValueError("La columna tipo3_new solo admite A, B o C.")
    if (data["Cliente"].str.len() > 35).any():
        raise ValueError("La columna Cliente supera el limite de 35 caracteres.")
    if not data["CUIT"].map(_valid_cuit).all():
        raise ValueError("El CSV de ventas contiene CUIT invalidos.")
    if not data["FacturaReporte"].str.fullmatch(r"\d{5}-\d{8}").all():
        raise ValueError("FacturaReporte debe usar el formato 00000-00000000.")
    if data["FacturaReporte"].duplicated().any():
        raise ValueError("El CSV de ventas contiene facturas duplicadas.")

    report_numbers = data["FacturaReporte"].str[-8:].astype("int64")
    if not report_numbers.equals(data["Factura"]):
        raise ValueError("Factura y FacturaReporte no coinciden.")

    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara y carga en Arancia un CSV de ventas ya transformado."
    )
    parser.add_argument("--csv", type=Path, required=True, help="CSV con el formato de bot_carga.")
    parser.add_argument(
        "--period",
        choices=["current", "previous"],
        default="current",
        help="Periodo del reporte de Arancia usado para evitar duplicados.",
    )
    parser.add_argument(
        "--skip-arancia-download",
        action="store_true",
        help="Reutiliza downloads/outbound.html en vez de descargarlo otra vez.",
    )
    parser.add_argument("--show-browser", action="store_true", help="Muestra el navegador.")
    parser.add_argument(
        "--manual-on-error",
        action="store_true",
        help="Permite continuar manualmente si Playwright falla.",
    )
    parser.add_argument(
        "--slow-network",
        action="store_true",
        help="Usa timeouts y pausas mas altas.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Tolerancia maxima al comparar importes.",
    )
    args = parser.parse_args()

    configure_logging()
    headless = not (args.show_browser or args.manual_on_error)
    timeout_config = get_playwright_timeout_config(slow_network=args.slow_network)
    data = read_sales_csv(args.csv)
    print(f"[OK] CSV de ventas validado: {len(data)} facturas.")

    if not args.skip_arancia_download:
        run_download_arancia_reports(
            period=args.period,
            headless=headless,
            manual_on_error=args.manual_on_error,
            timeout_config=timeout_config,
        )

    outbound_path = PROJECT_ROOT / "downloads" / "outbound.html"
    if not outbound_path.is_file():
        raise FileNotFoundError(
            "No existe downloads/outbound.html. Ejecuta sin --skip-arancia-download."
        )
    arancia_data = procesar_outbound_html(str(outbound_path))
    pending = comparar_facturas_venta(data, arancia_data, args.tolerance)
    cargar_facturas_ventas(
        pending,
        headless=headless,
        manual_on_error=args.manual_on_error,
        timeout_config=timeout_config,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
