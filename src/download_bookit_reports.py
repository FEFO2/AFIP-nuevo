import time
import re
import os
from playwright.sync_api import Playwright, sync_playwright, expect
from dotenv import load_dotenv

# --- variables ---
load_dotenv()
required_vars = ['ARANCIA_URL', 'ARANCIA_USERNAME', 'ARANCIA_PASSWORD']
for var in required_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"❌ Missing environment variable: {var}")

# --- main function ---
def download_arancia_reports(playwright: Playwright) -> None:
    # --- Variables de entorno ---
    url = os.getenv("ARANCIA_URL")
    user = os.getenv("ARANCIA_USERNAME")
    password = os.getenv("ARANCIA_PASSWORD")

    # --- Inicialización del navegador ---
    browser = playwright.chromium.launch(headless=True)  # headless=False para ver lo que pasa
    context = browser.new_context()
    page = context.new_page()

    # --- Login ---
    page.goto(url)
    page.get_by_role("button", name="Entrar").click()
    page.locator('input[name="TextBox1"]').fill(user)
    page.locator('input[name="TextBox2"]').fill(password)
    page.get_by_role("button", name="Ingresar").click()
    time.sleep(3)

    # --- Navegación hasta AFIP ---
    page.get_by_role("button", name="Facturacion").click()
    time.sleep(3)

    # Esperar a que aparezca el iframe "facturacion"
    page.wait_for_selector("iframe[name='facturacion']")
    frame_facturacion = page.frame(name="facturacion")
    frame_facturacion.get_by_role("button", name="Afip").click()
    
    # Esperás a que cargue el iframe interno
    frame_marco = None
    for f in frame_facturacion.child_frames:
        if f.name == "marco":
            frame_marco = f
            break

    # --- Seleccionar período (ejemplo: octubre 2025) ---
    frame_marco.wait_for_selector("#DropDownList1")
    frame_marco.locator("#DropDownList1").select_option("102025")

    # Guardar HTML de la pestaña de ventas ("VENTAS DEL MES")
    frame_marco.wait_for_timeout(1000)
    html_outbound = frame_marco.content()

    # --- Cambiar a pestaña de compras ---
    frame_marco.get_by_role("radio", name="COMPRAS DEL MES").check()
    frame_marco.wait_for_timeout(2000)
    html_inbound = frame_marco.content()

    # --- Guardar los HTML localmente ---
    with open("outbound.html", "w", encoding="utf-8") as f:
        f.write(html_outbound)

    with open("inbound.html", "w", encoding="utf-8") as f:
        f.write(html_inbound)

    print("✅ Archivos guardados: outbound.html e inbound.html")

    # --- Cerrar navegador ---
    context.close()
    browser.close()

    return html_outbound, html_inbound


with sync_playwright() as playwright:
    download_arancia_reports(playwright)