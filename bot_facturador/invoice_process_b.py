import csv
import unicodedata
from pathlib import Path

from playwright.sync_api import Playwright, sync_playwright


CSV_PATH = Path(__file__).with_name("lista_fac.csv")
DOWNLOADS_DIR = Path.home() / "Downloads" / "AFIP_Facturas"
FECHA_FACTURACION = "29/05/2026"

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


def run(playwright: Playwright) -> None:
    facturas = cargar_facturas()
    if not facturas:
        raise ValueError("lista_fac.csv no tiene filas para facturar.")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    browser = playwright.chromium.launch(headless=False, slow_mo=800)
    context = browser.new_context()
    page = context.new_page()

    # Logearse en ARCA
    page.goto("https://auth.afip.gob.ar/contribuyente_/login.xhtml")
    page.get_by_role("spinbutton").fill("20244138897")
    page.get_by_role("button", name="Siguiente").click()
    page.get_by_role("textbox", name="TU CLAVE").fill("Arancia.2025")
    page.get_by_role("button", name="Ingresar").click()

    # EL LOOP COMIENZA AQUÍ
    # Acceder a comprobantes en linea
    with page.expect_popup() as page1_info:
        page.locator("a").filter(has_text="Comprobantes en línea").click()
    page1 = page1_info.value

    # Seleccionar opcion de facturacion
    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()  # Cuit a usar

    for factura in facturas:
        page1.get_by_role("button", name="Generar Comprobantes").click()  # Opcion a usar (facturar)
        page1.locator("#puntodeventa").select_option("10")  # Punto de venta -> 2 / 3 / 10 segun tenemos nosotros.
        page1.locator("#universocomprobante").select_option("19")  # tipo de factura (10 es FC A, 19 es B)
        page1.wait_for_load_state("networkidle")  # -> ESPERA A QUE CARGUE
        page1.get_by_role("button", name="Continuar >").click()

        # Fecha, tipo de factura y moneda
        page1.get_by_role("textbox", name="Fecha del Comprobante").fill(FECHA_FACTURACION)
        page1.locator("#idconcepto").select_option("2")  # SERVICIOS
        page1.get_by_text("Moneda Extranjera").click()  # HACER SOLO SI ES USD
        page1.get_by_role("textbox", name="Desde").fill(FECHA_FACTURACION)
        page1.get_by_role("textbox", name="Hasta").fill(FECHA_FACTURACION)
        page1.wait_for_load_state("networkidle")  # -> ESPERA A QUE CARGUE

        condicion_iva = obtener_codigo(
            factura["condicion_iva"], CONDICION_IVA_MAP, "condicion_iva"
        )
        tipo_doc = obtener_codigo(factura["tipo_doc"], TIPO_DOC_MAP, "tipo_doc")
        tipo_iva = obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
        direccion = factura.get("direccion", "")

        # Info del cliente
        page1.get_by_role("button", name="Continuar >").click()
        page1.locator("#idivareceptor").select_option(condicion_iva)  # 5 es Consumidor final, 4 es sujeto exento
        page1.locator("#idtipodocreceptor").select_option(tipo_doc)  # CUIT es 80, DNI es 96
        page1.locator("#nrodocreceptor").fill(factura["num_doc"])  # AQUI SE PONE EL CUIT/DNI
        page1.locator("#nrodocreceptor").press("Tab")  # Dispara la busqueda del receptor
        page1.wait_for_load_state("networkidle")  # Espera a que AFIP termine de buscar los datos del receptor
        if tipo_doc == "96":
            domicilio_receptor = page1.locator("#domicilioreceptor")
            if direccion and not domicilio_receptor.input_value().strip():
                domicilio_receptor.fill(direccion)
        page1.get_by_role("checkbox", name="Contado").check()
        page1.get_by_role("button", name="Continuar >").click()
        page1.wait_for_load_state("networkidle")  # -> ESPERA A QUE CARGUE

        # Detalles de la factura
        page1.locator("#detalle_descripcion1").fill(factura["concepto"])  # -> EL CONCEPTO
        page1.locator("#detalle_precio1").fill(factura["precio"])  # PRECIO
        page1.locator("#detalle_tipo_iva1").select_option(tipo_iva)  # 1 no grav, 2 exento, 4 10,5% y 5 21%

        # Hacer la factura e imprimirla
        page1.get_by_role("button", name="Continuar >").click()
        page1.get_by_role("button", name="Confirmar Datos...").click()
        page1.get_by_role("button", name="Confirmar", exact=True).click()
        with page1.expect_download() as download_info:
            page1.get_by_role("button", name="Imprimir...").click()
        download = download_info.value
        download.save_as(DOWNLOADS_DIR / download.suggested_filename)


        # Si hay mas de una factura, se vuelve dos pasos atras
        page1.get_by_role("button", name="Menú Principal").click()

    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
