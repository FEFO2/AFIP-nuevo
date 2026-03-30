from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara y carga comprobantes de venta en Arancia usando Playwright."
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Muestra el navegador durante la carga.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Tolerancia máxima permitida al comparar importes.",
    )
    args = parser.parse_args()

    from data_upload import cargar_facturas_ventas
    from workflows import build_sales_upload_data

    clean_data = build_sales_upload_data(tolerance=args.tolerance)
    cargar_facturas_ventas(clean_data, headless=not args.show_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
