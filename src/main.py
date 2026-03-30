from __future__ import annotations

import argparse
import warnings


def _print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def _print_step(number: int, message: str) -> None:
    print(f"Paso {number}. {message}")


def _print_result(label: str, count: int) -> None:
    print(f"[OK] {label}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga, compara y carga comprobantes usando Playwright de punta a punta."
    )
    parser.add_argument(
        "--mode",
        choices=["todo", "compras", "ventas"],
        default="todo",
        help="Define si se procesa todo el flujo, solo compras o solo ventas.",
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
        help="Tolerancia maxima permitida al comparar importes.",
    )
    args = parser.parse_args()

    warnings.filterwarnings("ignore", category=FutureWarning)

    from data_upload import cargar_facturas_compra, cargar_facturas_ventas
    from download_afip_reports import run_download_afip_reports
    from download_bookit_reports import run_download_arancia_reports
    from utils import clear_downloads_dir
    from workflows import build_purchase_upload_data, build_sales_upload_data

    _print_section("Descarga de Archivos")
    if not args.skip_downloads:
        _print_step(1, "Limpiando la carpeta downloads...")
        clear_downloads_dir()
        _print_step(2, "Descargando comprobantes desde AFIP...")
        run_download_afip_reports()
        _print_step(3, "Descargando reportes desde Arancia/Bookit...")
        run_download_arancia_reports()
    else:
        _print_step(1, "Reutilizando archivos existentes en downloads (--skip-downloads).")

    _print_section("Comparacion de Facturas")
    purchase_data = None
    sales_data = None
    next_step = 4

    if args.mode in {"todo", "compras"}:
        _print_step(next_step, "Comparando facturas de compra...")
        purchase_data = build_purchase_upload_data(tolerance=args.tolerance)
        _print_result("Facturas de compra pendientes", len(purchase_data))
        next_step += 1

    if args.mode in {"todo", "ventas"}:
        _print_step(next_step, "Comparando facturas de venta...")
        sales_data = build_sales_upload_data(tolerance=args.tolerance)
        _print_result("Facturas de venta pendientes", len(sales_data))
        next_step += 1

    _print_section("Carga de Facturas")
    if purchase_data is not None:
        _print_step(next_step, "Cargando facturas de compra pendientes...")
        cargar_facturas_compra(purchase_data, headless=not args.show_browser)
        next_step += 1

    if sales_data is not None:
        _print_step(next_step, "Cargando facturas de venta pendientes...")
        cargar_facturas_ventas(sales_data, headless=not args.show_browser)

    _print_section("Proceso Finalizado")
    print("[OK] Flujo completado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
