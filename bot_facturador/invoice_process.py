import argparse
import csv
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Playwright, sync_playwright

from afip_common.config import get_required_env as _get_required_env
from afip_common.config import load_environment

DOWNLOADS_DIR = Path.home() / "Downloads" / "AFIP_Facturas"

CONDICION_IVA_MAP = {
    "responsable inscripto": "1",
    "consumidor final": "5",
    "sujeto exento": "4",
}

TIPO_DOC_MAP = {
    "cuit": "80",
    "dni": "96",
}

TIPO_IVA_MAP = {
    "no gravado": "1",
    "no grav": "1",
    "exento": "2",
    "10,5%": "4",
    "10.5%": "4",
    "21%": "5",
}

REQUIRED_COLUMNS = {
    "condicion_iva",
    "tipo_doc",
    "num_doc",
    "concepto",
    "precio",
    "iva",
}


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def cargar_facturas(csv_path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with csv_path.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                columnas = {normalizar_texto(name) for name in (reader.fieldnames or [])}
                faltantes = sorted(REQUIRED_COLUMNS - columnas)
                if faltantes:
                    raise ValueError(
                        f"Faltan columnas requeridas en {csv_path.name}: {', '.join(faltantes)}"
                    )
                facturas = []
                for fila in reader:
                    if None in fila:
                        raise ValueError(f"Fila con columnas de más en {csv_path.name}.")
                    facturas.append(
                        {normalizar_texto(k): (v or "").strip() for k, v in fila.items() if k}
                    )
                return facturas
        except UnicodeDecodeError:
            continue

    raise ValueError(f"No se pudo leer {csv_path.name} con las codificaciones esperadas.")


def obtener_codigo(valor: str, opciones: dict[str, str], campo: str) -> str:
    codigo = opciones.get(normalizar_texto(valor))
    if codigo is None:
        raise ValueError(f"Valor no soportado para {campo}: {valor}")
    return codigo


def run(
    playwright: Playwright,
    *,
    invoice_type: str,
    csv_path: Path,
    invoice_date: str,
    point_of_sale: str = "10",
    currency: str | None = None,
    downloads_dir: Path = DOWNLOADS_DIR,
) -> None:
    if invoice_type not in {"A", "B"}:
        raise ValueError("El tipo de factura debe ser A o B.")
    invoice_date = datetime.strptime(invoice_date, "%d/%m/%Y").strftime("%d/%m/%Y")
    currency = currency or ("ARS" if invoice_type == "A" else "USD")
    if currency not in {"ARS", "USD"}:
        raise ValueError("La moneda debe ser ARS o USD.")
    facturas = cargar_facturas(csv_path)
    if not facturas:
        raise ValueError(f"{csv_path.name} no tiene filas para facturar.")

    condiciones = dict(CONDICION_IVA_MAP)
    if invoice_type == "B":
        condiciones.pop("responsable inscripto")
    # Validar todo el lote antes de emitir el primer comprobante.
    for factura in facturas:
        for campo, opciones in (
            ("condicion_iva", condiciones),
            ("tipo_doc", TIPO_DOC_MAP),
            ("iva", TIPO_IVA_MAP),
        ):
            obtener_codigo(factura[campo], opciones, campo)
        if not all(factura[campo] for campo in REQUIRED_COLUMNS):
            raise ValueError("Hay campos obligatorios vacíos en el CSV.")

    load_environment()
    afip_url = _get_required_env("AFIP_URL")
    afip_username = _get_required_env("AFIP_USERNAME")
    afip_password = _get_required_env("AFIP_PASSWORD")

    downloads_dir.mkdir(parents=True, exist_ok=True)

    browser = playwright.chromium.launch(headless=False, slow_mo=800)
    context = None
    try:
        context = browser.new_context()
        page = context.new_page()

        # Logearse en ARCA
        page.goto(afip_url)
        page.get_by_role("spinbutton").fill(afip_username)
        page.get_by_role("button", name="Siguiente").click()
        page.get_by_role("textbox", name="TU CLAVE").fill(afip_password)
        page.get_by_role("button", name="Ingresar").click()

        # El loop comienza aqui
        with page.expect_popup() as page1_info:
            page.locator("a").filter(has_text="Comprobantes en línea").click()
        page1 = page1_info.value

        page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()

        for factura in facturas:
            page1.get_by_role("button", name="Generar Comprobantes").click()
            page1.locator("#puntodeventa").select_option(point_of_sale)
            page1.locator("#universocomprobante").select_option(
                "10" if invoice_type == "A" else "19"
            )
            page1.wait_for_load_state("networkidle")
            page1.get_by_role("button", name="Continuar >").click()

            page1.get_by_role("textbox", name="Fecha del Comprobante").fill(invoice_date)
            page1.locator("#idconcepto").select_option("2")
            if currency == "USD":
                page1.get_by_text("Moneda Extranjera").click()
            page1.get_by_role("textbox", name="Desde").fill(invoice_date)
            page1.get_by_role("textbox", name="Hasta").fill(invoice_date)
            page1.wait_for_load_state("networkidle")

            condicion_iva = obtener_codigo(factura["condicion_iva"], condiciones, "condicion_iva")
            tipo_doc = obtener_codigo(factura["tipo_doc"], TIPO_DOC_MAP, "tipo_doc")
            tipo_iva = obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
            direccion = factura.get("direccion", "")

            page1.get_by_role("button", name="Continuar >").click()
            page1.locator("#idivareceptor").select_option(condicion_iva)
            if invoice_type == "B":
                page1.locator("#idtipodocreceptor").select_option(tipo_doc)
            page1.locator("#nrodocreceptor").fill(factura["num_doc"])
            page1.locator("#nrodocreceptor").press("Tab")
            page1.wait_for_load_state("networkidle")
            if tipo_doc == "96":
                domicilio_receptor = page1.locator("#domicilioreceptor")
                if direccion and not domicilio_receptor.input_value().strip():
                    domicilio_receptor.fill(direccion)
            page1.get_by_role("checkbox", name="Contado").check()
            page1.get_by_role("button", name="Continuar >").click()
            page1.wait_for_load_state("networkidle")

            page1.locator("#detalle_descripcion1").fill(factura["concepto"])
            page1.locator("#detalle_precio1").fill(factura["precio"])
            page1.locator("#detalle_tipo_iva1").select_option(tipo_iva)

            page1.get_by_role("button", name="Continuar >").click()
            page1.get_by_role("button", name="Confirmar Datos...").click()
            page1.get_by_role("button", name="Confirmar", exact=True).click()
            with page1.expect_download() as download_info:
                page1.get_by_role("button", name="Imprimir...").click()
            download = download_info.value
            download.save_as(downloads_dir / Path(download.suggested_filename).name)

            page1.get_by_role("button", name="Menú Principal").click()

    finally:
        try:
            if context is not None:
                context.close()
        finally:
            browser.close()


def main(invoice_type: str) -> int:
    parser = argparse.ArgumentParser(description=f"Emitir facturas {invoice_type} en AFIP/ARCA.")
    default_csv = "lista_fac_a.csv" if invoice_type == "A" else "lista_fac.csv"
    parser.add_argument("--csv", type=Path, default=Path(__file__).with_name(default_csv))
    parser.add_argument("--fecha", required=True, help="Fecha de emisión: DD/MM/AAAA.")
    parser.add_argument("--punto-venta", default="10")
    parser.add_argument(
        "--moneda", choices=["ARS", "USD"], default="ARS" if invoice_type == "A" else "USD"
    )
    args = parser.parse_args()
    with sync_playwright() as playwright:
        run(
            playwright,
            invoice_type=invoice_type,
            csv_path=args.csv,
            invoice_date=args.fecha,
            point_of_sale=args.punto_venta,
            currency=args.moneda,
        )
    return 0
