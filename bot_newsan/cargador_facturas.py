from __future__ import annotations

import argparse
import code
import csv
import json
import os
import re
import sys
import traceback
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Playwright, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from afip_common.config import get_required_env as _get_required_env
from afip_common.config import load_environment

load_environment()


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "salida_csv" / "facturas_extraidas.csv"
PGA_PROFILE_DIR = BASE_DIR.parent / ".local" / "pga_browser_profile"
PGA_LOGIN_TIMEOUT_MS = 10_000
PGA_VERIFICATION_TIMEOUT_MS = 5 * 60 * 1000
UNIDAD_NEGOCIO = "pga"
PROVEEDOR = "arancia"
SOLICITANTE = "JORBA, AGUSTINA"
# Clasificacion fiscal en Oracle segun el codigo de comprobante AFIP.
CLASIFICACION_FISCAL_POR_CODIGO = {
    1: "001_FACTURA_A",
    201: "201_FACTURA_CREDITO_A_MiPyMEs",
}
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
TASA_IVA_POR_ALICUOTA = {
    "21": Decimal("0.21"),
    "21%": Decimal("0.21"),
    "10,5": Decimal("0.105"),
    "10.5": Decimal("0.105"),
    "10,5%": Decimal("0.105"),
    "10.5%": Decimal("0.105"),
}
CENTAVO = Decimal("0.01")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized)


def format_decimal(value: Any) -> str:
    amount = Decimal(str(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return f"{amount:.2f}".replace(".", ",")


def format_invoice_number(row: dict[str, str]) -> str:
    return f"{row['punto_venta']}-{row['numero_comprobante']}"


def get_fiscal_classification(invoice: dict[str, Any]) -> str:
    raw_code = str(invoice.get("comprobante_codigo") or "").strip()
    if not raw_code.isdigit():
        raise ValueError(f"La factura {invoice.get('archivo')} no tiene codigo de comprobante.")
    code = int(raw_code)
    if code not in CLASIFICACION_FISCAL_POR_CODIGO:
        raise ValueError(
            f"Codigo de comprobante {code} no soportado ({invoice.get('archivo')}). "
            f"Soportados: {sorted(CLASIFICACION_FISCAL_POR_CODIGO)}"
        )
    return CLASIFICACION_FISCAL_POR_CODIGO[code]


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


def get_pga_total(invoice: dict[str, Any]) -> Decimal:
    bases_por_tasa: dict[Decimal, Decimal] = {}
    total = Decimal("0")

    for item in invoice["items"]:
        tax_key = normalize_text(str(item.get("alicuota_iva", "")))
        if tax_key in {"no gravado", "exento"}:
            total += Decimal(str(item["subtotal_con_iva"]))
            continue
        if tax_key not in TASA_IVA_POR_ALICUOTA:
            raise ValueError(f"Alicuota no soportada: {item.get('alicuota_iva')}")

        rate = TASA_IVA_POR_ALICUOTA[tax_key]
        bases_por_tasa[rate] = bases_por_tasa.get(rate, Decimal("0")) + Decimal(
            str(item["subtotal"])
        )

    for rate, base in bases_por_tasa.items():
        total += base + (base * rate).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    pga_total = total.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    invoice_total = Decimal(str(invoice["importe_total"])).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if abs(pga_total - invoice_total) > CENTAVO:
        raise ValueError(
            f"El total calculado por PGA ({pga_total}) difiere del total de la factura "
            f"({invoice_total}) en mas de un centavo."
        )
    return pga_total


def select_tax_code(page: Page, tax_code: str) -> None:
    tax_input = page.get_by_role(
        "combobox", name=re.compile(r"Clasificaci.n de impuestos", re.IGNORECASE)
    )
    tax_input.fill(tax_code)
    page.keyboard.press("Tab")

    modal_overlay = page.locator(".AFModalGlassPane:visible")
    try:
        modal_overlay.wait_for(state="visible", timeout=1000)
    except PlaywrightTimeoutError:
        return

    modal = modal_overlay.locator("xpath=..")
    modal.get_by_text(tax_code.upper(), exact=True).first.click()
    modal.get_by_role("button", name="Aceptar", exact=True).click()
    modal_overlay.wait_for(state="hidden", timeout=10000)


def select_fiscal_classification(page: Page, classification: str) -> None:
    classification_input = page.get_by_role(
        "combobox", name=re.compile(r"Clasificaci.n fiscal de", re.IGNORECASE)
    )
    classification_input.fill(classification)
    classification_input.press("Tab")

    option = page.locator("td.xen:visible").filter(
        has_text=re.compile(rf"^\s*{re.escape(classification)}\s*$")
    )
    try:
        option.first.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        print(
            f"PGA no mostro una lista para seleccionar {classification}. "
            "Comprueba en el navegador que la clasificacion fiscal del documento es correcta "
            "y, si hace falta, seleccionala manualmente."
        )
        if input("Escribe SI para continuar o pulsa Enter para detener: ").strip().upper() != "SI":
            raise RuntimeError("Clasificacion fiscal no confirmada; carga detenida.")
        if classification_input.first.input_value().strip() != classification:
            raise RuntimeError("La clasificacion fiscal no coincide; carga detenida.")
    else:
        option.first.click()
        page.get_by_role("button", name="Aceptar", exact=True).click()


def load_invoices(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        invoices: list[dict[str, Any]] = []
        for row in reader:
            row["items"] = json.loads(row["items_json"])
            row["solicitante"] = (row.get("solicitante") or "").strip() or SOLICITANTE
            invoices.append(row)
        return invoices


def open_oracle(playwright: Playwright) -> tuple[Any, Page]:
    url = _get_required_env("PGA_URL", "PAG_URL")
    PGA_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        str(PGA_PROFILE_DIR), headless=False, slow_mo=1200
    )
    page = context.pages[0] if context.pages else context.new_page()

    try:
        page.goto(url)
        username_input = page.get_by_role("textbox", name="Username")
        try:
            username_input.wait_for(state="visible", timeout=PGA_LOGIN_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        else:
            username_input.fill(_get_required_env("PGA_USERNAME"))
            page.get_by_role("textbox", name="Password").fill(_get_required_env("PGA_PASSWORD"))
            page.get_by_role("button", name="Next").click()
            print(
                "Si PGA solicita el codigo enviado por correo, introducilo en el navegador "
                "y marca la opcion de confiar en este dispositivo durante 15 dias."
            )

        home_link = page.get_by_role("link", name="Página Inicial", exact=True)
        create_invoice_link = page.get_by_role(
            "link", name=re.compile(r"Crear factura", re.IGNORECASE)
        )
        try:
            home_link.or_(create_invoice_link).first.wait_for(
                state="visible", timeout=PGA_VERIFICATION_TIMEOUT_MS
            )
        except PlaywrightTimeoutError as exception:
            raise RuntimeError(
                "PGA no completo el inicio de sesion. Si pidio un codigo, introducilo y marca "
                "la opcion de confiar en este dispositivo durante 15 dias."
            ) from exception

        if home_link.is_visible():
            home_link.click()
        create_invoice_link.click(timeout=60000)
    except Exception:
        try:
            context.close()
        except Exception:
            pass
        raise

    return context, page


def fill_header(page: Page, invoice: dict[str, Any]) -> None:
    page.get_by_role("combobox", name=re.compile(r"Unidad de negocio", re.IGNORECASE)).fill(
        UNIDAD_NEGOCIO
    )
    page.get_by_role("combobox", name=re.compile(r"Unidad de negocio", re.IGNORECASE)).press("Tab")

    page.get_by_role("combobox", name="Proveedor", exact=True).fill(PROVEEDOR)
    page.get_by_role("combobox", name="Proveedor", exact=True).press("Tab")

    page.get_by_role("button", name="Aceptar").click()

    page.get_by_role("textbox", name=re.compile(r"N.mero$", re.IGNORECASE)).fill(
        format_invoice_number(invoice)
    )
    pga_total = get_pga_total(invoice)
    invoice_total = Decimal(str(invoice["importe_total"])).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if pga_total != invoice_total:
        print(
            f"Ajuste de redondeo PGA para {invoice['numero_comprobante']}: "
            f"{invoice_total} -> {pga_total}"
        )
    page.get_by_role("textbox", name="Importe", exact=True).fill(format_decimal(pga_total))
    page.get_by_role("textbox", name="Fecha", exact=True).fill(invoice["fecha_emision"])

    page.get_by_role("combobox", name=re.compile(r"Solicitante", re.IGNORECASE)).fill(
        invoice.get("solicitante") or SOLICITANTE
    )
    page.get_by_role("combobox", name=re.compile(r"Solicitante", re.IGNORECASE)).press("Tab")

    page.get_by_role("link", name=re.compile(r"Gestionar Anexos", re.IGNORECASE)).click()
    page.set_input_files("input[type='file']", invoice["ruta"])
    page.get_by_role("button", name="Aceptar").click()

    clasificacion_fiscal = get_fiscal_classification(invoice)
    page.get_by_role("link", name="*Tipo de Comprobante").click()
    select_fiscal_classification(page, clasificacion_fiscal)

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
        select_tax_code(page, get_tax_code(item))


def fill_cae_data(page: Page, invoice: dict[str, Any]) -> None:
    page.get_by_role("button", name=re.compile(r"Ampliar Impuestos", re.IGNORECASE)).click()
    page.get_by_role("link", name="*CAE/CAEA").click()
    page.locator(
        '[id="pt1:_FOr1:1:_FONSr2:0:MAnt2:0:pm1:r1:0:ap1:df1_headerDFF1Iterator__FLEX_Context__FLEX_EMPTY::content"]'
    ).click()
    page.locator(
        '[id="pt1:_FOr1:1:_FONSr2:0:MAnt2:0:pm1:r1:0:ap1:df1_headerDFF1Iterator__FLEX_Context__FLEX_EMPTY::content"]'
    ).select_option(label="CAE")
    page.get_by_role("textbox", name=re.compile(r"N.mero CAE", re.IGNORECASE)).fill(invoice["cae"])
    page.get_by_role("textbox", name=re.compile(r"Fecha CAE", re.IGNORECASE)).fill(
        invoice["vencimiento_cae"]
    )
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


def pause_with_browser_open(context: Any, page: Page, error: Exception | None = None) -> None:
    if error is not None:
        print("\nSe produjo un error y el navegador va a quedar abierto para revisar.")
        print(f"Error: {error}")
        traceback.print_exc()
    else:
        print("\nProceso finalizado y el navegador va a quedar abierto para revisar.")

    print("\nVariables disponibles: page, context")
    print("Escribi exit() para salir y cerrar todo manualmente.")
    local_vars = {"page": page, "context": context}
    if error is not None:
        local_vars["error"] = error
    code.interact(local=local_vars)


def prepare_next_invoice_after_manual_save(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    next_invoice_button = page.locator(POST_SAVE_CONTINUE_SELECTOR)
    next_invoice_button.wait_for(state="visible", timeout=60000)
    next_invoice_button.click()


def show_manual_review_alert(
    invoice_number: str,
    current_index: int,
    total_invoices: int,
    solicitante: str = SOLICITANTE,
) -> None:
    """Muestra un aviso visible cuando una factura queda lista para revisar."""
    message = (
        f"La factura {invoice_number} esta lista para revisar en PGA "
        f"({current_index}/{total_invoices}).\n\n"
        f"Solicitante: {solicitante}.\n\n"
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


def wait_for_manual_review(
    invoice: dict[str, Any], current_index: int, total_invoices: int
) -> bool:
    show_manual_review_alert(
        invoice["numero_comprobante"],
        current_index=current_index,
        total_invoices=total_invoices,
        solicitante=invoice.get("solicitante") or SOLICITANTE,
    )
    print(
        f"\nFactura {invoice['numero_comprobante']} lista para revisar en PGA "
        f"({current_index}/{total_invoices})."
    )
    print("Revisala y aceptala manualmente en la web.")
    print(f"Solicitante: {invoice.get('solicitante') or SOLICITANTE}")
    while True:
        user_input = (
            input(
                "Cuando termines, presionÃ¡ Enter para seguir con la siguiente, o escribÃ­ 'salir' para cortar: "
            )
            .strip()
            .lower()
        )
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
        selected = [
            invoice for invoice in invoices if invoice["numero_comprobante"] == invoice_number
        ]
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
        print("No hay facturas para procesar.")
        return

    # Validar todos los codigos de comprobante antes de abrir el navegador.
    for invoice in selected_invoices:
        get_fiscal_classification(invoice)

    with sync_playwright() as playwright:
        context, page = open_oracle(playwright)
        should_close = args.final_action != "manual"
        try:
            for index, invoice in enumerate(selected_invoices):
                print(
                    f"Cargando factura {invoice['numero_comprobante']} "
                    f"(cod. {invoice.get('comprobante_codigo')} -> {get_fiscal_classification(invoice)})..."
                )
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
                        pause_with_browser_open(context, page)
                        return
                    if index < len(selected_invoices) - 1:
                        prepare_next_invoice_after_manual_save(page)
        except Exception as error:
            should_close = False
            pause_with_browser_open(context, page, error)
        finally:
            if should_close:
                context.close()


if __name__ == "__main__":
    main()
