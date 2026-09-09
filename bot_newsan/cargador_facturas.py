from __future__ import annotations

import argparse
import code
import csv
import json
import os
import re
import traceback
import unicodedata
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from playwright.sync_api import Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "salida_csv" / "facturas_extraidas.csv"
UNIDAD_NEGOCIO = "pga"
PROVEEDOR = "arancia"
SOLICITANTE = "JORBA, AGUSTINA"
CLASIFICACION_FISCAL = "001_FACTURA_A"
FINAL_ACTIONS = {"manual", "cancelar"}
POST_SAVE_CONTINUE_SELECTOR = (
    '[id="pt1:_FOr1:1:_FONSr2:0:_FOTsr1:0:pm1:r1:0:r1:0:ITPdtl:0:AT1:_ATp:ct2"]'
)
IMPUESTO_MAP = {
    "21": "ar_iva_general",
    "21%": "ar_iva_general",
    "10,5": "ar_iva_reducido",
    "10.5": "ar_iva_reducido",
    "10,5%": "ar_iva_reducido",
    "10.5%": "ar_iva_reducido",
    "no gravado": "ar_iva_no",
    "exento": "ar_iva_exento",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized)


def format_decimal(value: Any) -> str:
    return f"{float(value):.2f}".replace(".", ",")


def format_invoice_number(row: dict[str, str]) -> str:
    return f"{row['punto_venta']}-{row['numero_comprobante']}"


def get_tax_code(item: dict[str, Any]) -> str:
    tax_key = normalize_text(str(item.get("alicuota_iva", "")))
    if tax_key not in IMPUESTO_MAP:
        raise ValueError(f"Alicuota no soportada: {item.get('alicuota_iva')}")
    return IMPUESTO_MAP[tax_key]


def get_line_amount(item: dict[str, Any]) -> float:
    tax_key = normalize_text(str(item.get("alicuota_iva", "")))
    if tax_key in {"no gravado", "exento"}:
        return float(item["subtotal_con_iva"])
    return float(item["subtotal"])


def load_invoices(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        invoices: list[dict[str, Any]] = []
        for row in reader:
            row["items"] = json.loads(row["items_json"])
            invoices.append(row)
        return invoices


def _get_required_env(name: str, legacy_name: str | None = None) -> str:
    value = os.getenv(name)
    if value:
        return value

    if legacy_name:
        legacy_value = os.getenv(legacy_name)
        if legacy_value:
            return legacy_value

    legacy_hint = f" o {legacy_name}" if legacy_name else ""
    raise ValueError(f"Falta la variable de entorno {name}{legacy_hint}.")


def open_oracle(playwright: Playwright) -> tuple[Any, Any, Page]:
    url = _get_required_env("PGA_URL", "PAG_URL")
    username = _get_required_env("PGA_USERNAME")
    password = _get_required_env("PGA_PASSWORD")

    browser = playwright.chromium.launch(headless=False, slow_mo=1200)
    context = browser.new_context()
    page = context.new_page()

    page.goto(url)
    page.get_by_role("textbox", name="Username").fill(username)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Next").click()
    page.wait_for_load_state("networkidle")

    try:
        page.get_by_role("link", name="Página Inicial", exact=True).click(timeout=10000)
    except PlaywrightTimeoutError:
        pass

    page.get_by_role("link", name=re.compile(r"Crear factura", re.IGNORECASE)).click(timeout=60000)

    return browser, context, page


def fill_header(page: Page, invoice: dict[str, Any]) -> None:
    page.get_by_role("combobox", name=re.compile(r"Unidad de negocio", re.IGNORECASE)).fill(UNIDAD_NEGOCIO)
    page.get_by_role("combobox", name=re.compile(r"Unidad de negocio", re.IGNORECASE)).press("Tab")

    page.get_by_role("combobox", name="Proveedor", exact=True).fill(PROVEEDOR)
    page.get_by_role("combobox", name="Proveedor", exact=True).press("Tab")

    page.get_by_role("button", name="Aceptar").click()

    page.get_by_role("textbox", name=re.compile(r"N.mero$", re.IGNORECASE)).fill(format_invoice_number(invoice))
    page.get_by_role("textbox", name="Importe", exact=True).fill(format_decimal(invoice["importe_total"]))
    page.get_by_role("textbox", name="Fecha", exact=True).fill(invoice["fecha_emision"])

    page.get_by_role("combobox", name=re.compile(r"Solicitante", re.IGNORECASE)).fill(SOLICITANTE)
    page.get_by_role("combobox", name=re.compile(r"Solicitante", re.IGNORECASE)).press("Tab")

    page.get_by_role("link", name=re.compile(r"Gestionar Anexos", re.IGNORECASE)).click()
    page.set_input_files("input[type='file']", invoice["ruta"])
    page.get_by_role("button", name="Aceptar").click()

    page.get_by_role("link", name="*Tipo de Comprobante").click()
    page.get_by_role("combobox", name=re.compile(r"Clasificaci.n fiscal de", re.IGNORECASE)).fill(
        CLASIFICACION_FISCAL
    )
    page.get_by_role("combobox", name=re.compile(r"Clasificaci.n fiscal de", re.IGNORECASE)).press("Tab")
    page.locator('tr[_afrrk="0"]').locator('td.xen >> text=001_FACTURA_A').click()         
    page.get_by_role("button", name="Aceptar").click()

    page.get_by_role("button", name=re.compile(r"Ampliar L.neas", re.IGNORECASE)).click()


def fill_line_items(page: Page, items: list[dict[str, Any]]) -> None:
    if len(items) > 4:
        raise ValueError(f"Se esperaban hasta 4 conceptos y llegaron {len(items)}.")

    for index, item in enumerate(items, start=1):
        if index > 1:
            page.locator(f'tr[_afrrk="{index - 1}"]').locator(".xen.x1i5").click()

        row = page.locator(f'tr[_afrrk="{index - 1}"]')
        row.get_by_label("Importe").fill(format_decimal(get_line_amount(item)))
        page.keyboard.press("Tab")
        page.get_by_role("combobox", name=re.compile(r"Clasificaci.n de impuestos", re.IGNORECASE)).fill(
            get_tax_code(item)
        )
        page.keyboard.press("Tab")


def fill_cae_data(page: Page, invoice: dict[str, Any]) -> None:
    page.get_by_role("button", name=re.compile(r"Ampliar Impuestos", re.IGNORECASE)).click()
    page.get_by_role("link", name="*CAE/CAEA").click()
    page.locator('[id="pt1:_FOr1:1:_FONSr2:0:MAnt2:0:pm1:r1:0:ap1:df1_headerDFF1Iterator__FLEX_Context__FLEX_EMPTY::content"]').click()
    page.locator('[id="pt1:_FOr1:1:_FONSr2:0:MAnt2:0:pm1:r1:0:ap1:df1_headerDFF1Iterator__FLEX_Context__FLEX_EMPTY::content"]').select_option(label="CAE")
    page.get_by_role("textbox", name=re.compile(r"N.mero CAE", re.IGNORECASE)).fill(invoice["cae"])
    page.get_by_role("textbox", name=re.compile(r"Fecha CAE", re.IGNORECASE)).fill(invoice["vencimiento_cae"])
    page.get_by_role("link", name="*Tipo de Comprobante").click()


def finalize_invoice(page: Page, final_action: str) -> None:
    if final_action == "manual":
        print("Factura cargada en pantalla. Revision/finalizacion manual pendiente.")
        return

    if final_action == "cancelar":
        page.get_by_role("button", name="Cancelar", exact=True).click()
        return

    raise ValueError(f"Accion final no soportada: {final_action}")


def load_invoice(page: Page, invoice: dict[str, Any], final_action: str) -> None:
    fill_header(page, invoice)
    fill_line_items(page, invoice["items"])
    fill_cae_data(page, invoice)
    finalize_invoice(page, final_action)


def pause_with_browser_open(browser: Any, context: Any, page: Page, error: Exception | None = None) -> None:
    if error is not None:
        print("\nSe produjo un error y el navegador va a quedar abierto para revisar.")
        print(f"Error: {error}")
        traceback.print_exc()
    else:
        print("\nProceso finalizado y el navegador va a quedar abierto para revisar.")

    print("\nVariables disponibles: page, context, browser")
    print("Escribi exit() para salir y cerrar todo manualmente.")
    local_vars = {"page": page, "context": context, "browser": browser}
    if error is not None:
        local_vars["error"] = error
    code.interact(local=local_vars)


def prepare_next_invoice_after_manual_save(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    next_invoice_button = page.locator(POST_SAVE_CONTINUE_SELECTOR)
    next_invoice_button.wait_for(state="visible", timeout=60000)
    next_invoice_button.click()


def show_manual_review_alert(invoice_number: str, current_index: int, total_invoices: int) -> None:
    """Muestra un aviso visible cuando una factura queda lista para revisar."""
    message = (
        f"La factura {invoice_number} esta lista para revisar en PGA "
        f"({current_index}/{total_invoices}).\n\n"
        "Cierra este aviso, revisala y aceptala manualmente en el navegador."
    )

    if os.name == "nt":
        # Aviso nativo, en primer plano, sin dependencias adicionales.
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            message,
            "Revision de factura pendiente",
            0x40 | 0x10000 | 0x40000,  # Informacion + primer plano + topmost.
        )
    else:
        print("\a", end="", flush=True)


def wait_for_manual_review(invoice: dict[str, Any], current_index: int, total_invoices: int) -> bool:
    show_manual_review_alert(
        invoice["numero_comprobante"],
        current_index=current_index,
        total_invoices=total_invoices,
    )
    print(
        f"\nFactura {invoice['numero_comprobante']} lista para revisar en PGA "
        f"({current_index}/{total_invoices})."
    )
    print("Revisala y aceptala manualmente en la web.")
    while True:
        user_input = input(
            "Cuando termines, presionÃ¡ Enter para seguir con la siguiente, o escribÃ­ 'salir' para cortar: "
        ).strip().lower()
        if user_input == "":
            return True
        if user_input == "salir":
            return False
        print("Entrada no vÃ¡lida. UsÃ¡ Enter para continuar o 'salir' para detener el proceso.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Carga facturas en PGA a partir del CSV extraido.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=CSV_PATH,
        help="Ruta al CSV de facturas generado por extractor_factura.py",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Cantidad maxima de facturas a procesar.",
    )
    parser.add_argument(
        "--invoice-number",
        help="Procesa solo el numero de comprobante indicado, por ejemplo 00003564.",
    )
    parser.add_argument(
        "--final-action",
        choices=sorted(FINAL_ACTIONS),
        default="manual",
        help="manual deja la factura lista para revisar; cancelar descarta la carga al final.",
    )
    return parser


def select_invoices(
    invoices: list[dict[str, Any]],
    invoice_number: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = invoices
    if invoice_number:
        selected = [invoice for invoice in invoices if invoice["numero_comprobante"] == invoice_number]
        if not selected:
            raise ValueError(f"No se encontro la factura {invoice_number} en el CSV.")
    if limit is not None:
        selected = selected[:limit]
    return selected


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    csv_path = args.csv if args.csv.is_absolute() else BASE_DIR / args.csv
    invoices = load_invoices(csv_path)
    selected_invoices = select_invoices(invoices, args.invoice_number, args.limit)

    if not selected_invoices:
        raise ValueError("No hay facturas para procesar.")

    with sync_playwright() as playwright:
        browser, context, page = open_oracle(playwright)
        should_close = args.final_action != "manual"
        try:
            for index, invoice in enumerate(selected_invoices):
                print(f"Cargando factura {invoice['numero_comprobante']}...")
                load_invoice(
                    page,
                    invoice,
                    final_action=args.final_action,
                )
                if args.final_action == "manual":
                    should_continue = wait_for_manual_review(
                        invoice,
                        current_index=index + 1,
                        total_invoices=len(selected_invoices),
                    )
                    if not should_continue:
                        should_close = False
                        print("Proceso detenido por el usuario. El navegador queda abierto.")
                        pause_with_browser_open(browser, context, page)
                        return
                    if index < len(selected_invoices) - 1:
                        prepare_next_invoice_after_manual_save(page)
        except Exception as error:
            should_close = False
            pause_with_browser_open(browser, context, page, error)
        finally:
            if should_close:
                context.close()
                browser.close()


if __name__ == "__main__":
    main()

