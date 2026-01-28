from playwright.sync_api import Playwright, sync_playwright, expect

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://auth.afip.gob.ar/contribuyente_/login.xhtml")

    # Login
    page.get_by_role("spinbutton").wait_for(state="visible")
    page.get_by_role("spinbutton").fill("20244138897")
    page.get_by_role("button", name="Siguiente").click()

    page.get_by_role("textbox", name="TU CLAVE").wait_for(state="visible")
    page.get_by_role("textbox", name="TU CLAVE").fill("Arancia.2025")
    page.get_by_role("button", name="Ingresar").click()

    # Abrir Comprobantes en línea en popup
    with page.expect_popup() as popup_info:
        page.locator("a").filter(has_text="Comprobantes en línea").click()
    page1 = popup_info.value

    # Esperar botones y seleccionar empresa
    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").wait_for(state="visible")
    page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()
    page1.get_by_role("button", name="Generar Comprobantes").click()

    # -------------------------------
    # Detectar el iframe donde están los formularios
    frame = page1.frame_locator("iframe").first  # Usar 'name' si lo conoces: page1.frame(name="nombre")

    # Puntodeventa
    frame.locator("#puntodeventa").wait_for(state="visible", timeout=60000)
    frame.locator("#puntodeventa").select_option("2")
    page1.get_by_role("button", name="Continuar >").click()

    # Concepto
    frame.locator("#idconcepto").wait_for(state="visible", timeout=60000)
    frame.locator("#idconcepto").select_option("2")

    # Moneda extranjera
    frame.get_by_role("checkbox", name="Moneda Extranjera").wait_for(state="visible")
    frame.get_by_role("checkbox", name="Moneda Extranjera").check()
    page1.get_by_role("button", name="Continuar >").click()

    # Receptor
    frame.locator("#idivareceptor").wait_for(state="visible")
    frame.locator("#idivareceptor").select_option("1")
    frame.locator("#nrodocreceptor").fill("20244138897")
    frame.get_by_role("checkbox", name="Contado").check()
    page1.get_by_role("button", name="Continuar >").click()

    # Detalle de comprobantes
    frame.locator("#detalle_descripcion1").wait_for(state="visible")
    frame.locator("#detalle_descripcion1").fill("EMISIÓN DE PASAJES A PRUEBA DE FACTURA")
    frame.locator("#detalle_precio1").fill("0.01")
    frame.locator("#detalle_tipo_iva1").select_option("2")
    frame.get_by_role("button", name="Agregar línea descripción").click()

    frame.locator("#detalle_descripcion2").wait_for(state="visible")
    frame.locator("#detalle_descripcion2").fill("CONCEPTO DOS")
    frame.locator("#detalle_precio2").fill("0.01")
    frame.locator("#detalle_tipo_iva2").select_option("4")
    frame.get_by_role("button", name="Agregar línea descripción").click()

    frame.locator("#detalle_descripcion3").wait_for(state="visible")
    frame.locator("#detalle_descripcion3").fill("CONCEPTO TRES0")
    frame.locator("#detalle_precio3").fill("0.01")

    page1.get_by_role("button", name="Continuar >").click()
    page1.once("dialog", lambda dialog: dialog.dismiss())
    page1.get_by_role("button", name="Confirmar Datos...").click()

    # Cerrar contexto y navegador
    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
