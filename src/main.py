from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga, compara y carga comprobantes usando Playwright de punta a punta."
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Usa los archivos existentes en downloads/ y omite la descarga.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Muestra el navegador durante las cargas a Arancia.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Tolerancia máxima permitida al comparar importes.",
    )
    args = parser.parse_args()

    from data_upload import cargar_facturas_compra, cargar_facturas_ventas
    from download_afip_reports import run_download_afip_reports
    from download_bookit_reports import run_download_arancia_reports
    from utils import clear_downloads_dir
    from workflows import build_purchase_upload_data, build_sales_upload_data

    if not args.skip_downloads:
        clear_downloads_dir()
        run_download_afip_reports()
        run_download_arancia_reports()

    purchase_data = build_purchase_upload_data(tolerance=args.tolerance)
    sales_data = build_sales_upload_data(tolerance=args.tolerance)

    cargar_facturas_compra(purchase_data, headless=not args.show_browser)
    cargar_facturas_ventas(sales_data, headless=not args.show_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
