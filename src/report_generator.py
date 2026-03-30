from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from utils import ensure_downloads_dir


INVOICE_TYPES = {"Factura", "Pyme_fc"}
CREDIT_TYPES = {"Credito", "Pyme_nc"}


def _safe_sum(data: pd.DataFrame, column: str) -> float:
    if data.empty:
        return 0.0
    return float(pd.to_numeric(data[column], errors="coerce").fillna(0).sum())


def _count_types(data: pd.DataFrame, allowed_types: set[str]) -> int:
    if data.empty:
        return 0
    return int(data["tipo2_new"].isin(allowed_types).sum())


def _format_amount(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get_report_key_series(data: pd.DataFrame) -> pd.Series:
    if "FacturaReporte" in data.columns:
        return data["FacturaReporte"].astype(str)
    return data["Factura"].astype(str)


def _build_summary(data: pd.DataFrame) -> dict[str, str]:
    return {
        "Facturas agregadas": str(_count_types(data, INVOICE_TYPES)),
        "Notas de credito agregadas": str(_count_types(data, CREDIT_TYPES)),
        "Gravado 10,5": _format_amount(_safe_sum(data, "NETO 10.5")),
        "Gravado 21": _format_amount(_safe_sum(data, "NETO 21")),
        "No gravado": _format_amount(_safe_sum(data, "TOTAL_NO_GRAVADO")),
        "Total facturado": _format_amount(_safe_sum(data, "TOTAL_FACTURADO")),
    }


def _build_month_difference_summary(
    monthly_sales_data: pd.DataFrame,
    monthly_purchase_data: pd.DataFrame,
) -> dict[str, str]:
    difference_iva_21 = _safe_sum(monthly_sales_data, "IVA 21") - _safe_sum(monthly_purchase_data, "IVA 21")
    difference_iva_10_5 = _safe_sum(monthly_sales_data, "IVA 10.5") - _safe_sum(
        monthly_purchase_data, "IVA 10.5"
    )
    difference_no_gravado = _safe_sum(monthly_sales_data, "TOTAL_NO_GRAVADO") - _safe_sum(
        monthly_purchase_data, "TOTAL_NO_GRAVADO"
    )
    difference_facturacion = _safe_sum(monthly_sales_data, "TOTAL_FACTURADO") - _safe_sum(
        monthly_purchase_data, "TOTAL_FACTURADO"
    )

    taxable_base_21 = difference_iva_21 / 0.21 if difference_iva_21 else 0.0
    taxable_base_10_5 = difference_iva_10_5 / 0.105 if difference_iva_10_5 else 0.0

    # Assumption based on the example shared by the user:
    # the missing non-taxed amount is the billing difference minus the positive taxable bases.
    missing_non_taxed_amount = difference_facturacion - max(taxable_base_21, 0) - max(taxable_base_10_5, 0)

    return {
        "Diferencia IVA 21": _format_amount(difference_iva_21),
        "Diferencia IVA 10,5": _format_amount(difference_iva_10_5),
        "Diferencia No gravado": _format_amount(difference_no_gravado),
        "Diferencia facturacion": _format_amount(difference_facturacion),
        "Importe gravado del 21": _format_amount(taxable_base_21),
        "Importe gravado del 10,5": _format_amount(taxable_base_10_5),
        "Importe No gravado faltante": _format_amount(missing_non_taxed_amount),
    }


def _render_summary_rows(summary: dict[str, str]) -> str:
    rows = []
    for label, value in summary.items():
        rows.append(
            f"""
            <div class="metric-row">
              <div class="metric-label">{label}</div>
              <div class="metric-value">{value}</div>
            </div>
            """
        )
    return "\n".join(rows)


def _detect_period_label(month_data: pd.DataFrame) -> str:
    if month_data.empty or "Fecha" not in month_data.columns:
        return "Periodo actual"

    dates = pd.to_datetime(month_data["Fecha"], errors="coerce")
    if dates.dropna().empty:
        return "Periodo actual"

    return dates.dropna().max().strftime("%m/%Y")


def generate_sales_report(
    *,
    loaded_sales_data: pd.DataFrame,
    monthly_sales_data: pd.DataFrame,
    monthly_purchase_data: pd.DataFrame,
    output_path: Path | None = None,
) -> Path:
    output_file = output_path or ensure_downloads_dir() / "informe_facturacion.html"

    loaded_keys = set(_get_report_key_series(loaded_sales_data)) if not loaded_sales_data.empty else set()
    monthly_report_keys = _get_report_key_series(monthly_sales_data)
    loaded_detail = monthly_sales_data[monthly_report_keys.isin(loaded_keys)].copy()

    loaded_summary = _build_summary(loaded_detail)
    monthly_summary = _build_month_difference_summary(monthly_sales_data, monthly_purchase_data)
    period_label = _detect_period_label(monthly_sales_data)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Informe de facturacion</title>
  <style>
    :root {{
      --primary-strong: #F05A28;
      --primary-medium: #FF7A3C;
      --primary-soft: #FFB199;
      --orange-bg: #FFE5DC;
      --text-main: #2B2B2B;
      --text-secondary: #6F6F6F;
      --border: #E0E0E0;
      --bg-base: #FFFFFF;
      --bg-alt: #F7F7F7;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg-base);
      color: var(--text-main);
    }}
    .wrap {{
      max-width: 980px;
      margin: 0 auto;
      padding: 36px 24px 56px;
    }}
    .topbar {{
      height: 6px;
      width: 100%;
      background: linear-gradient(90deg, var(--primary-strong), var(--primary-medium), var(--primary-soft));
      border-radius: 999px;
      margin-bottom: 28px;
    }}
    h1, h2 {{
      margin: 0;
      font-weight: 700;
    }}
    h1 {{
      font-size: 30px;
      letter-spacing: -0.02em;
      margin-bottom: 10px;
    }}
    h2 {{
      font-size: 20px;
      margin-bottom: 16px;
    }}
    .hero {{
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }}
    .subtitle {{
      color: var(--text-secondary);
      font-size: 15px;
      line-height: 1.5;
    }}
    .section {{
      margin-top: 26px;
      padding-top: 8px;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 12px;
      border-bottom: 2px solid var(--orange-bg);
      margin-bottom: 8px;
    }}
    .section-kicker {{
      font-size: 12px;
      font-weight: 700;
      color: var(--primary-strong);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .summary {{
      background: var(--bg-alt);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow: hidden;
    }}
    .metric-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
    }}
    .metric-row:last-child {{
      border-bottom: 0;
    }}
    .metric-label {{
      color: var(--text-secondary);
      font-size: 14px;
    }}
    .metric-value {{
      font-size: 18px;
      font-weight: 600;
      color: var(--text-main);
      text-align: right;
    }}
    .metric-row:last-child .metric-value {{
      color: var(--primary-strong);
    }}
    .footnote {{
      margin-top: 12px;
      color: var(--text-secondary);
      font-size: 14px;
      line-height: 1.5;
    }}
    .accent-note {{
      color: var(--primary-medium);
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar"></div>
    <section class="hero">
      <h1>Informe de facturacion</h1>
      <p class="subtitle">
        Periodo analizado: {period_label}<br />
        Generado: {generated_at}
      </p>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-kicker">1. Carga realizada</div>
          <h2>Resumen de la facturacion cargada</h2>
        </div>
      </div>
      <div class="summary">
        {_render_summary_rows(loaded_summary)}
      </div>
      <p class="footnote">
        <span class="accent-note">Criterio:</span> los importes monetarios se calculan sumando facturas y restando notas de credito.
      </p>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <div class="section-kicker">2. Panorama mensual</div>
          <h2>Resumen total del mes</h2>
        </div>
      </div>
      <div class="summary">
        {_render_summary_rows(monthly_summary)}
      </div>
      <p class="footnote">
        Este bloque resume ventas menos compras del mes. El importe no gravado faltante se estima restando de la diferencia de facturacion solo los importes gravados positivos detectados.
      </p>
    </section>
  </div>
</body>
</html>
"""

    output_file.write_text(html, encoding="utf-8")
    return output_file


def build_dummy_sales_report_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_sales_data = pd.DataFrame(
        [
            {
                "Fecha": "2026-03-03",
                "Factura": "1001",
                "FacturaReporte": "00001-00001001",
                "tipo2_new": "Factura",
                "NETO 10.5": 1250.00,
                "NETO 21": 4800.00,
                "IVA 10.5": 131.25,
                "IVA 21": 1008.00,
                "TOTAL_NO_GRAVADO": 300.00,
                "TOTAL_FACTURADO": 7489.25,
            },
            {
                "Fecha": "2026-03-05",
                "Factura": "1002",
                "FacturaReporte": "00001-00001002",
                "tipo2_new": "Factura",
                "NETO 10.5": 850.00,
                "NETO 21": 3200.00,
                "IVA 10.5": 89.25,
                "IVA 21": 672.00,
                "TOTAL_NO_GRAVADO": 120.00,
                "TOTAL_FACTURADO": 4931.25,
            },
            {
                "Fecha": "2026-03-09",
                "Factura": "1003",
                "FacturaReporte": "00001-00001003",
                "tipo2_new": "Credito",
                "NETO 10.5": -200.00,
                "NETO 21": -900.00,
                "IVA 10.5": -21.00,
                "IVA 21": -189.00,
                "TOTAL_NO_GRAVADO": -50.00,
                "TOTAL_FACTURADO": -1360.00,
            },
            {
                "Fecha": "2026-03-17",
                "Factura": "1004",
                "FacturaReporte": "00001-00001004",
                "tipo2_new": "Factura",
                "NETO 10.5": 1400.00,
                "NETO 21": 6100.00,
                "IVA 10.5": 147.00,
                "IVA 21": 1281.00,
                "TOTAL_NO_GRAVADO": 500.00,
                "TOTAL_FACTURADO": 9428.00,
            },
            {
                "Fecha": "2026-03-22",
                "Factura": "1005",
                "FacturaReporte": "00001-00001005",
                "tipo2_new": "Pyme_fc",
                "NETO 10.5": 300.00,
                "NETO 21": 1600.00,
                "IVA 10.5": 31.50,
                "IVA 21": 336.00,
                "TOTAL_NO_GRAVADO": 80.00,
                "TOTAL_FACTURADO": 2347.50,
            },
            {
                "Fecha": "2026-03-28",
                "Factura": "1006",
                "FacturaReporte": "00001-00001006",
                "tipo2_new": "Pyme_nc",
                "NETO 10.5": -100.00,
                "NETO 21": -450.00,
                "IVA 10.5": -10.50,
                "IVA 21": -94.50,
                "TOTAL_NO_GRAVADO": -30.00,
                "TOTAL_FACTURADO": -685.00,
            },
        ]
    )

    monthly_purchase_data = pd.DataFrame(
        [
            {
                "Fecha": "2026-03-02",
                "Factura": "5001",
                "Tipo2": "Factura",
                "NETO 10.5": 980.00,
                "NETO 21": 2100.00,
                "IVA 10.5": 102.90,
                "IVA 21": 441.00,
                "TOTAL_NO_GRAVADO": 140.00,
                "TOTAL_FACTURADO": 3623.90,
            },
            {
                "Fecha": "2026-03-10",
                "Factura": "5002",
                "Tipo2": "Factura",
                "NETO 10.5": 420.00,
                "NETO 21": 1400.00,
                "IVA 10.5": 44.10,
                "IVA 21": 294.00,
                "TOTAL_NO_GRAVADO": 90.00,
                "TOTAL_FACTURADO": 2248.10,
            },
            {
                "Fecha": "2026-03-19",
                "Factura": "5003",
                "Tipo2": "Crédito",
                "NETO 10.5": -50.00,
                "NETO 21": -600.00,
                "IVA 10.5": -5.25,
                "IVA 21": -126.00,
                "TOTAL_NO_GRAVADO": -40.00,
                "TOTAL_FACTURADO": -821.25,
            },
            {
                "Fecha": "2026-03-25",
                "Factura": "5004",
                "Tipo2": "Factura",
                "NETO 10.5": 730.00,
                "NETO 21": 3500.00,
                "IVA 10.5": 76.65,
                "IVA 21": 735.00,
                "TOTAL_NO_GRAVADO": 180.00,
                "TOTAL_FACTURADO": 5221.65,
            },
        ]
    )

    loaded_sales_data = pd.DataFrame(
        [
            {"Factura": "1002", "FacturaReporte": "00001-00001002"},
            {"Factura": "1003", "FacturaReporte": "00001-00001003"},
            {"Factura": "1004", "FacturaReporte": "00001-00001004"},
            {"Factura": "1006", "FacturaReporte": "00001-00001006"},
        ]
    )

    return loaded_sales_data, monthly_sales_data, monthly_purchase_data


def generate_dummy_sales_report(output_path: Path | None = None) -> Path:
    loaded_sales_data, monthly_sales_data, monthly_purchase_data = build_dummy_sales_report_data()
    return generate_sales_report(
        loaded_sales_data=loaded_sales_data,
        monthly_sales_data=monthly_sales_data,
        monthly_purchase_data=monthly_purchase_data,
        output_path=output_path or ensure_downloads_dir() / "informe_facturacion_dummy.html",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera el informe HTML de facturacion.")
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="Genera un informe dummy para trabajar el estilo sin depender de datos reales.",
    )
    args = parser.parse_args()

    if args.dummy:
        output_path = generate_dummy_sales_report()
        print(f"[OK] Informe dummy generado en {output_path}")
        return 0

    print("Usa --dummy para generar un informe de ejemplo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
