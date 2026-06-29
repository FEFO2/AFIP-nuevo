### OJO REVISAR QUE LAS FACTURAS
#   -> FECHA EN LINEA 14
#   -> PUNTO DE VENTA EN LA 100
#   -> USD O ARS EN LA 109 (COMENTAR SI ES ARS)

import csv
import os
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright


load_dotenv()


CSV_PATH = Path(__file__).with_name("lista_fac_a.csv")
DOWNLOADS_DIR = Path.home() / "Downloads" / "AFIP_Facturas"
FECHA_FACTURACION = "30/05/2026"

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


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Falta la variable de entorno {name}.")
    return value


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def cargar_facturas() -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with CSV_PATH.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                facturas = [
                    {
                        normalizar_texto(clave): (valor or "").strip()
                        for clave, valor in fila.items()
                        if clave
                    }
                    for fila in reader
                ]
                if facturas:
                    columnas = set(facturas[0].keys())
                    faltantes = sorted(REQUIRED_COLUMNS - columnas)
                    if faltantes:
                        disponibles = ", ".join(sorted(columna for columna in columnas if columna))
                        raise ValueError(
                            f"Faltan columnas requeridas en {CSV_PATH.name}: {', '.join(faltantes)}. "
                            f"Columnas detectadas: {disponibles}"
                        )
                return facturas
        except UnicodeDecodeError:
            continue

    raise ValueError(f"No se pudo leer {CSV_PATH.name} con las codificaciones esperadas.")


def obtener_codigo(valor: str, opciones: dict[str, str], campo: str) -> str:
    codigo = opciones.get(normalizar_texto(valor))
    if codigo is None:
        raise ValueError(f"Valor no soportado para {campo}: {valor}")
    return codigo


def run(playwright: Playwright) -> None:
    facturas = cargar_facturas()
    if not facturas:
        raise ValueError(f"{CSV_PATH.name} no tiene filas para facturar.")

    afip_url = _get_required_env("AFIP_URL")
    afip_username = _get_required_env("AFIP_USERNAME")
    afip_password = _get_required_env("AFIP_PASSWORD")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    browser = playwright.chromium.launch(headless=False, slow_mo=800)
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
        page.locator("a").filter(has_text="Comprobantes en lÃ­nea").click()
    page1 = page1_info.value

    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()

    for factura in facturas:
        page1.get_by_role("button", name="Generar Comprobantes").click()
        page1.locator("#puntodeventa").select_option("10")
        page1.locator("#universocomprobante").select_option("10")
        page1.wait_for_load_state("networkidle")
        page1.get_by_role("button", name="Continuar >").click()

        page1.get_by_role("textbox", name="Fecha del Comprobante").fill(FECHA_FACTURACION)
        page1.locator("#idconcepto").select_option("2")
        page1.get_by_role("textbox", name="Desde").fill(FECHA_FACTURACION)
        page1.get_by_role("textbox", name="Hasta").fill(FECHA_FACTURACION)
        page1.wait_for_load_state("networkidle")

        condicion_iva = obtener_codigo(factura["condicion_iva"], CONDICION_IVA_MAP, "condicion_iva")
        tipo_doc = obtener_codigo(factura["tipo_doc"], TIPO_DOC_MAP, "tipo_doc")
        tipo_iva = obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
        direccion = factura.get("direccion", "")

        page1.get_by_role("button", name="Continuar >").click()
        page1.locator("#idivareceptor").select_option(condicion_iva)
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
        download.save_as(DOWNLOADS_DIR / download.suggested_filename)

        page1.get_by_role("button", name="MenÃº Principal").click()

    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
