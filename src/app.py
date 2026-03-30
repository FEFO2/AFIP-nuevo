from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga compras o ventas en Arancia usando una sola capa Playwright."
    )
    parser.add_argument(
        "mode",
        choices=["compras", "ventas"],
        nargs="?",
        default="compras",
        help="Flujo a ejecutar.",
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

    from data_upload import cargar_facturas_compra, cargar_facturas_ventas
    from workflows import build_purchase_upload_data, build_sales_upload_data

    if args.mode == "compras":
        clean_data = build_purchase_upload_data(tolerance=args.tolerance)
        cargar_facturas_compra(clean_data, headless=not args.show_browser)
        return 0

    clean_data = build_sales_upload_data(tolerance=args.tolerance)
    cargar_facturas_ventas(clean_data, headless=not args.show_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
