from __future__ import annotations

import argparse
import logging
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
        "--period",
        choices=["current", "previous"],
        default="current",
        help="Indica si las descargas deben tomar comprobantes del mes actual o del mes pasado.",
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

    from utils import browser_mode_label, clear_downloads_dir, configure_logging

    configure_logging()
    logger = logging.getLogger(__name__)

    from data_upload import cargar_facturas_compra, cargar_facturas_ventas
    from download_afip_reports import run_download_afip_reports
    from download_bookit_reports import run_download_arancia_reports
    from report_generator import generate_sales_report
    from workflows import (
        build_purchase_month_report_data,
        build_purchase_upload_data,
        build_sales_month_report_data,
        build_sales_upload_data,
    )

    upload_headless = not args.show_browser
    logger.info(
        "Inicio del flujo | period=%s | mode=%s | skip_downloads=%s | navegador en cargas=%s | tolerance=%s",
        args.period,
        args.mode,
        args.skip_downloads,
        browser_mode_label(upload_headless),
        args.tolerance,
    )

    _print_section("Descarga de Archivos")
    if not args.skip_downloads:
        _print_step(1, "Limpiando la carpeta downloads...")
        logger.info("Limpiando carpeta downloads...")
        clear_downloads_dir()
        _print_step(2, "Descargando comprobantes desde AFIP...")
        logger.info("Iniciando descarga de comprobantes desde AFIP.")
        run_download_afip_reports(period=args.period)
        _print_step(3, "Descargando reportes desde Arancia/Bookit...")
        logger.info("Iniciando descarga de reportes desde Arancia/Bookit.")
        run_download_arancia_reports(period=args.period)
    else:
        _print_step(1, "Reutilizando archivos existentes en downloads (--skip-downloads).")
        logger.info("Se reutilizan archivos existentes en downloads.")

    _print_section("Comparacion de Facturas")
    purchase_data = None
    sales_data = None
    uploaded_sales_data = None
    purchase_month_report_data = None
    sales_month_report_data = None
    next_step = 4

    if args.mode in {"todo", "compras"}:
        _print_step(next_step, "Comparando facturas de compra...")
        logger.info("Preparando comparacion de facturas de compra.")
        purchase_data = build_purchase_upload_data(tolerance=args.tolerance)
        purchase_month_report_data = build_purchase_month_report_data()
        _print_result("Facturas de compra pendientes", len(purchase_data))
        logger.info("Comparacion de compras finalizada. Pendientes=%s", len(purchase_data))
        next_step += 1

    if args.mode in {"todo", "ventas"}:
        _print_step(next_step, "Comparando facturas de venta...")
        logger.info("Preparando comparacion de facturas de venta.")
        sales_data = build_sales_upload_data(tolerance=args.tolerance)
        sales_month_report_data = build_sales_month_report_data()
        if purchase_month_report_data is None:
            purchase_month_report_data = build_purchase_month_report_data()
        _print_result("Facturas de venta pendientes", len(sales_data))
        logger.info("Comparacion de ventas finalizada. Pendientes=%s", len(sales_data))
        next_step += 1

    _print_section("Carga de Facturas")
    if purchase_data is not None:
        _print_step(next_step, "Cargando facturas de compra pendientes...")
        logger.info(
            "Iniciando carga de compras en Arancia con navegador %s.",
            browser_mode_label(upload_headless),
        )
        cargar_facturas_compra(purchase_data, headless=upload_headless)
        next_step += 1

    if sales_data is not None:
        _print_step(next_step, "Cargando facturas de venta pendientes...")
        logger.info(
            "Iniciando carga de ventas en Arancia con navegador %s.",
            browser_mode_label(upload_headless),
        )
        uploaded_sales_data = cargar_facturas_ventas(sales_data, headless=upload_headless)
        next_step += 1

    if (
        uploaded_sales_data is not None
        and sales_month_report_data is not None
        and purchase_month_report_data is not None
    ):
        _print_section("Informe HTML")
        _print_step(next_step, "Generando informe de facturacion...")
        report_path = generate_sales_report(
            loaded_sales_data=uploaded_sales_data,
            monthly_sales_data=sales_month_report_data,
            monthly_purchase_data=purchase_month_report_data,
        )
        print(f"[OK] Informe generado en {report_path}")
        logger.info("Informe HTML generado en %s", report_path)

    _print_section("Proceso Finalizado")
    print("[OK] Flujo completado.")
    logger.info("Proceso completo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
