import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context()
    page = context.new_page()

    # Logearse en ARCA
    page.goto("https://auth.afip.gob.ar/contribuyente_/login.xhtml")
    page.get_by_role("spinbutton").fill("20244138897")
    page.get_by_role("button", name="Siguiente").click()
    page.get_by_role("textbox", name="TU CLAVE").fill("Arancia.2025")
    page.get_by_role("button", name="Ingresar").click()

    # Acceder a comprobantes en línea
    with page.expect_popup() as page1_info:
        page.locator("a").filter(has_text="Comprobantes en línea").click()
    page1 = page1_info.value

    # Seleccionar opción de facturación 
    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click() # Cuit a usar
    page1.get_by_role("button", name="Generar Comprobantes").click() # Opción a usar (facturar)
    page1.locator("#puntodeventa").select_option("2") # Punto de venta -> 2 / 3 / 10 según tenemos nosotros.
    page1.locator("#universocomprobante").select_option("19") # tipo de factura (10 es FC A, 19 es B)
    page1.wait_for_load_state("networkidle") # -> ESPERA A QUE CARGUE 
    page1.get_by_role("button", name="Continuar >").click()
    
    # Fecha, tipo de factura y moneda
    page1.get_by_role("textbox", name="Fecha del Comprobante").fill("29/05/2026") # FECHA DE FACTURACIÓN
    page1.locator("#idconcepto").select_option("2") # SERVCIOS
    page1.get_by_text("Moneda Extranjera").click() # HACER SOLO SI ES USD
    page1.get_by_role("textbox", name="Desde").fill("29/05/2026") # FECHA DE FACTURACIÓN
    page1.get_by_role("textbox", name="Hasta").fill("29/05/2026") # FECHA DE FACTURACIÓN
    page1.wait_for_load_state("networkidle") # -> ESPERA A QUE CARGUE 

    # Info del cliente 
    page1.get_by_role("button", name="Continuar >").click()
    page1.locator("#idivareceptor").select_option("5") # -> 5 es Consumidor final, 4 es sujeto exento
    page1.locator("#idtipodocreceptor").select_option("96") # -> CUIT ES 80, DNI ES 96
    page1.locator("#nrodocreceptor").fill("20179746744") # AQUI SE PONE EL CUIT
    page1.locator("#domicilioreceptor").fill("belgrano 5") #DIRECCIÓN (SOLO USAR SI VIENE VACÍO)
    page1.get_by_role("checkbox", name="Contado").check()
    page1.get_by_role("button", name="Continuar >").click()
    page1.wait_for_load_state("networkidle") # -> ESPERA A QUE CARGUE 

    # Detalles de la factura -> OJO EL LOOP PARA AQUELLAS FACTURAS QUE TENGAN MAS DE UN CONCEPTO
    page1.locator("#detalle_descripcion1").fill("Intermediación por viaje de intercambio a Alemania") # -> EL CONCEPTO
    page1.locator("#detalle_precio1").fill("2190") # PRECIO
    page1.locator("#detalle_tipo_iva1").select_option("2") #1 no grav, 2 exento, 4 10,5% y 5 21%
    # page1.get_by_role("button", name="Agregar línea descripción").click() AGREGAR LINEAS DE DESCRIPCIÓN SI ES NECESARIO

    # Hacer la factura e imprimirla 
    page1.get_by_role("button", name="Continuar >").click()
    page1.get_by_role("button", name="Confirmar Datos...").click()
    page1.get_by_role("button", name="Confirmar", exact=True).click()
    with page1.expect_download() as download_info:
        page1.get_by_role("button", name="Imprimir...").click()
    download = download_info.value

    # SI HAY MAS DE UNA FACTURA, SE VUELVE DOS PASOS ATRÁS
    page1.goto("https://fe.afip.gob.ar/rcel/jsp/genComDatosOperacion.do")
    page1.goto("https://fe.afip.gob.ar/rcel/jsp/genComDatosReceptor.do")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
