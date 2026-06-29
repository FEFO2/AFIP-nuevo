import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright


CSV_PATH = Path(__file__).with_name("lista_fac.csv")
RCEL_URL = "https://fe.afip.gob.ar/rcel"
FECHA_FACTURACION_PRUEBA = "29/05/2026"
SLOW_MO_MS = 300
WAIT_UI_MS = 1200

CONDICION_IVA_MAP = {
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


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def cargar_facturas() -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with CSV_PATH.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                return [
                    {
                        normalizar_texto(clave): (valor or "").strip()
                        for clave, valor in fila.items()
                        if clave
                    }
                    for fila in reader
                ]
        except UnicodeDecodeError:
            continue

    raise ValueError("No se pudo leer lista_fac.csv con las codificaciones esperadas.")


def obtener_codigo(valor: str, opciones: dict[str, str], campo: str) -> str:
    codigo = opciones.get(normalizar_texto(valor))
    if codigo is None:
        raise ValueError(f"Valor no soportado para {campo}: {valor}")
    return codigo


def obtener_fecha_facturacion() -> str:
    fecha_ingresada = input(
        "Ingresa la fecha de facturacion en formato dd-mm-yyyy "
        "(Enter para usar hoy): "
    ).strip()

    if not fecha_ingresada:
        return datetime.now().strftime("%d/%m/%Y")

    try:
        fecha = datetime.strptime(fecha_ingresada, "%d-%m-%Y")
    except ValueError as error:
        raise ValueError(
            "La fecha debe ingresarse en formato dd-mm-yyyy."
        ) from error

    return fecha.strftime("%d/%m/%Y")


def esperar_estabilidad(page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(WAIT_UI_MS)


def abrir_comprobantes(page):
    enlace_comprobantes = page.get_by_role(
        "link",
        name=re.compile(r"Comprobantes (electr[oó]nicos|en l[ií]nea)", re.IGNORECASE),
    ).first

    enlace_comprobantes.wait_for(state="visible", timeout=30000)
    page.wait_for_timeout(WAIT_UI_MS)

    try:
        with page.expect_popup(timeout=10000) as page1_info:
            enlace_comprobantes.click()
        page1 = page1_info.value
    except PlaywrightTimeoutError:
        enlace_comprobantes.click()
        page1 = page

    if RCEL_URL not in page1.url:
        page1.wait_for_load_state("networkidle")

    return page1


def run(playwright: Playwright) -> None:
    facturas = cargar_facturas()
    if not facturas:
        raise ValueError("lista_fac.csv no tiene filas para facturar.")
    fecha_facturacion = FECHA_FACTURACION_PRUEBA

    browser = playwright.chromium.launch(headless=False, slow_mo=SLOW_MO_MS)
    context = browser.new_context()
    page = context.new_page()

    # Logearse en ARCA
    page.goto("https://auth.afip.gob.ar/contribuyente_/login.xhtml")
    page.get_by_role("spinbutton").fill("20244138897")
    page.get_by_role("button", name="Siguiente").click()
    page.get_by_role("textbox", name="TU CLAVE").fill("Arancia.2025")
    page.get_by_role("button", name="Ingresar").click()

    # Acceder a comprobantes en linea
    with page.expect_popup() as page1_info:
        page.locator("a").filter(has_text="Comprobantes en línea").click()
    page1 = page1_info.value

    # Seleccionar opcion de facturacion
    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()  # Cuit a usar
    page1.get_by_role("button", name="Generar Comprobantes").click()  # Opcion a usar
    page1.locator("#puntodeventa").select_option("2")  # Punto de venta
    page1.locator("#universocomprobante").select_option("19")  # 10 es FC A, 19 es B
    page1.wait_for_load_state("networkidle")
    page1.get_by_role("button", name="Continuar >").click()

    # Fecha, tipo de factura y moneda
    page1.get_by_role("textbox", name="Fecha del Comprobante").fill(fecha_facturacion)
    page1.locator("#idconcepto").select_option("2")  # Servicios
    page1.get_by_text("Moneda Extranjera").click()  # Solo si es USD
    page1.get_by_role("textbox", name="Desde").fill(fecha_facturacion)
    page1.get_by_role("textbox", name="Hasta").fill(fecha_facturacion)
    page1.wait_for_load_state("networkidle")

    for factura in facturas:
        condicion_iva = obtener_codigo(
            factura["condicion_iva"], CONDICION_IVA_MAP, "condicion_iva"
        )
        tipo_doc = obtener_codigo(factura["tipo_doc"], TIPO_DOC_MAP, "tipo_doc")
        tipo_iva = obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
        direccion = factura.get("direccion", "")

        # Info del cliente
        if "genComDatosOperacion.do" in page1.url:
            page1.get_by_role("button", name="Continuar >").click()
        elif "genComDatosReceptor.do" not in page1.url:
            page1.goto("https://fe.afip.gob.ar/rcel/jsp/genComDatosReceptor.do")

        esperar_estabilidad(page1)
        page1.locator("#idivareceptor").select_option(condicion_iva)
        page1.locator("#idtipodocreceptor").select_option(tipo_doc)
        page1.locator("#nrodocreceptor").fill(factura["num_doc"])
        esperar_estabilidad(page1)

        domicilio_receptor = page1.locator("#domicilioreceptor")
        if not domicilio_receptor.input_value().strip() and direccion and direccion != "-":
            domicilio_receptor.fill(direccion)

        contado = page1.get_by_role("checkbox", name="Contado")
        if not contado.is_checked():
            contado.check()

        page1.get_by_role("button", name="Continuar >").click()
        esperar_estabilidad(page1)

        # Detalles de la factura
        page1.locator("#detalle_descripcion1").fill(factura["concepto"])
        page1.locator("#detalle_precio1").fill(factura["precio"])
        page1.locator("#detalle_tipo_iva1").select_option(tipo_iva)
        esperar_estabilidad(page1)

        # Hacer la factura e imprimirla
        page1.get_by_role("button", name="Continuar >").click()
        esperar_estabilidad(page1)
        page1.get_by_role("button", name="Confirmar Datos...").click()
        esperar_estabilidad(page1)
        page1.get_by_role("button", name="Confirmar", exact=True).click()
        esperar_estabilidad(page1)
        with page1.expect_download() as download_info:
            page1.get_by_role("button", name="Imprimir...").click()
        _ = download_info.value

        # Vuelve a la carga de datos para la siguiente factura
        page1.goto("https://fe.afip.gob.ar/rcel/jsp/genComDatosOperacion.do")
        esperar_estabilidad(page1)
        page1.goto("https://fe.afip.gob.ar/rcel/jsp/genComDatosReceptor.do")
        esperar_estabilidad(page1)

    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
