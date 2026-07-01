from __future__ import annotations

from pathlib import Path

import pandas as pd

from .afip_data_transformation import (
    build_afip_inbound_report_data,
    build_afip_outbound_report_data,
    transform_afip_inbound_invoices,
    transform_afip_outbound_invoices,
)
from .bookit_data_transformation import procesar_inbound_html, procesar_outbound_html
from .data_comparison import comparar_facturas_compra, comparar_facturas_venta
from .utils import PROJECT_ROOT


def build_purchase_upload_data(
    *, project_root: Path = PROJECT_ROOT, tolerance: float = 1.0
) -> pd.DataFrame:
    downloads_dir = project_root / "downloads"
    afip_data = pd.read_excel(
        downloads_dir / "comprobantes_recibidos.xlsx",
        header=0,
        skiprows=1,
    )
    bookit_data = procesar_inbound_html(str(downloads_dir / "inbound.html"))
    afip_data_inbound = transform_afip_inbound_invoices(afip_data)
    return comparar_facturas_compra(afip_data_inbound, bookit_data, tolerance)


def build_sales_upload_data(
    *, project_root: Path = PROJECT_ROOT, tolerance: float = 1.0
) -> pd.DataFrame:
    downloads_dir = project_root / "downloads"
    afip_data = pd.read_excel(
        downloads_dir / "comprobantes_emitidos.xlsx",
        header=0,
        skiprows=1,
    )
    bookit_data = procesar_outbound_html(str(downloads_dir / "outbound.html"))
    afip_data_outbound = transform_afip_outbound_invoices(afip_data)
    return comparar_facturas_venta(afip_data_outbound, bookit_data, tolerance)


def build_sales_month_report_data(*, project_root: Path = PROJECT_ROOT) -> pd.DataFrame:
    downloads_dir = project_root / "downloads"
    afip_data = pd.read_excel(
        downloads_dir / "comprobantes_emitidos.xlsx",
        header=0,
        skiprows=1,
    )
    return build_afip_outbound_report_data(afip_data)


def build_purchase_month_report_data(*, project_root: Path = PROJECT_ROOT) -> pd.DataFrame:
    downloads_dir = project_root / "downloads"
    afip_data = pd.read_excel(
        downloads_dir / "comprobantes_recibidos.xlsx",
        header=0,
        skiprows=1,
    )
    return build_afip_inbound_report_data(afip_data)

