from __future__ import annotations

import argparse
import logging
import warnings

from .data_upload import cargar_facturas_compra, cargar_facturas_ventas
from .download_afip_reports import run_download_afip_reports
from .download_bookit_reports import run_download_arancia_reports
from .report_generator import generate_sales_report
from .utils import (
    browser_mode_label,
    clear_downloads_dir,
    configure_logging,
    get_playwright_timeout_config,
)
from .workflows import (
    build_purchase_month_report_data,
    build_purchase_upload_data,
    build_sales_month_report_data,
    build_sales_upload_data,
)


AFIP_DOWNLOAD_FILES = {
    "comprobantes_recibidos.xlsx",
    "comprobantes_emitidos.xlsx",
}
ARANCIA_DOWNLOAD_FILES = {
    "inbound.html",
    "outbound.html",
}


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
        "--skip-afip-downloads",
        action="store_true",
        help="Reutiliza los archivos de AFIP ya existentes en downloads/.",
    )
    parser.add_argument(
        "--skip-arancia-downloads",
        action="store_true",
        help="Reutiliza los archivos de Arancia/Bookit ya existentes en downloads/.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Muestra el navegador durante las descargas y las cargas de Playwright.",
    )
    parser.add_argument(
        "--manual-on-error",
        action="store_true",
        help="Si Playwright falla, deja el navegador abierto para continuar manualmente antes de cerrarlo.",
    )
    parser.add_argument(
        "--slow-network",
        action="store_true",
        help="Usa timeouts y pausas mas altas para conexiones lentas o sitios inestables.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Tolerancia maxima permitida al comparar importes.",
    )
    args = parser.parse_args()

    warnings.filterwarnings("ignore", category=FutureWarning)

    configure_logging()
    logger = logging.getLogger(__name__)

    playwright_headless = not (args.show_browser or args.manual_on_error)
    skip_afip_downloads = args.skip_downloads or args.skip_afip_downloads
    skip_arancia_downloads = args.skip_downloads or args.skip_arancia_downloads
    timeout_config = get_playwright_timeout_config(slow_network=args.slow_network)
    files_to_refresh = set()

    if not skip_afip_downloads:
        files_to_refresh.update(AFIP_DOWNLOAD_FILES)
    if not skip_arancia_downloads:
        files_to_refresh.update(ARANCIA_DOWNLOAD_FILES)

    logger.info(
        "Inicio del flujo | period=%s | mode=%s | skip_downloads=%s | skip_afip_downloads=%s | skip_arancia_downloads=%s | manual_on_error=%s | slow_network=%s | navegador Playwright=%s | tolerance=%s",
        args.period,
        args.mode,
        args.skip_downloads,
        skip_afip_downloads,
        skip_arancia_downloads,
        args.manual_on_error,
        args.slow_network,
        browser_mode_label(playwright_headless),
        args.tolerance,
    )

    _print_section("Descarga de Archivos")
    next_step = 1

    if files_to_refresh:
        files_label = ", ".join(sorted(files_to_refresh))
        _print_step(next_step, f"Limpiando archivos previos en downloads/: {files_label}")
        logger.info("Limpiando archivos previos en downloads/: %s", files_label)
        clear_downloads_dir(names=files_to_refresh)
        next_step += 1

    if skip_afip_downloads:
        _print_step(next_step, "Reutilizando archivos existentes de AFIP en downloads/.")
        logger.info("Se reutilizan los archivos existentes de AFIP en downloads.")
    else:
        _print_step(next_step, "Descargando comprobantes desde AFIP...")
        logger.info("Iniciando descarga de comprobantes desde AFIP.")
        run_download_afip_reports(
            period=args.period,
            headless=playwright_headless,
            manual_on_error=args.manual_on_error,
            timeout_config=timeout_config,
        )
    next_step += 1

    if skip_arancia_downloads:
        _print_step(next_step, "Reutilizando archivos existentes de Arancia/Bookit en downloads/.")
        logger.info("Se reutilizan los archivos existentes de Arancia/Bookit en downloads.")
    else:
        _print_step(next_step, "Descargando reportes desde Arancia/Bookit...")
        logger.info("Iniciando descarga de reportes desde Arancia/Bookit.")
        run_download_arancia_reports(
            period=args.period,
            headless=playwright_headless,
            manual_on_error=args.manual_on_error,
            timeout_config=timeout_config,
        )
    next_step += 1

    _print_section("Comparacion de Facturas")
    purchase_data = None
    sales_data = None
    uploaded_sales_data = None
    purchase_month_report_data = None
    sales_month_report_data = None

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
            browser_mode_label(playwright_headless),
        )
        cargar_facturas_compra(
            purchase_data,
            headless=playwright_headless,
            manual_on_error=args.manual_on_error,
            timeout_config=timeout_config,
        )
        next_step += 1

    if sales_data is not None:
        _print_step(next_step, "Cargando facturas de venta pendientes...")
        logger.info(
            "Iniciando carga de ventas en Arancia con navegador %s.",
            browser_mode_label(playwright_headless),
        )
        uploaded_sales_data = cargar_facturas_ventas(
            sales_data,
            headless=playwright_headless,
            manual_on_error=args.manual_on_error,
            timeout_config=timeout_config,
        )
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

