# --- Libraries ---
import re
import os
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright, expect

# --- variables ---
load_dotenv()
required_vars = ['AFIP_URL', 'AFIP_USERNAME', 'AFIP_PASSWORD']
for var in required_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"❌ Missing environment variable: {var}")

# --- main function ---
def download_reports(playwright: Playwright) -> None:
    
    # --- Variables ---
    url = os.getenv("AFIP_URL")
    cuit = os.getenv("AFIP_USERNAME")
    password = os.getenv("AFIP_PASSWORD")

    # --- Aux variables ---
    comprobantes =[
        ("#btnRecibidos","comprobantes_recibidos.xlsx"),
        ("#btnEmitidos","comprobantes_emitidos.xlsx")
    ]
    
    # --- Browser settings ----
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:

        # --- Login ---
        page.goto(url)
        page.get_by_role("spinbutton").click()
        page.get_by_role("spinbutton").fill(cuit)
        page.get_by_role("button", name="Siguiente").click()
        page.get_by_role("textbox", name="TU CLAVE").fill(password)
        page.get_by_role("button", name="Ingresar").click()

        # --- Find section ----
        page.get_by_role("link", name="Ver todos").wait_for(state="visible", timeout=30000)
        page.get_by_role("link", name="Ver todos").click(timeout=30000)
        
        # --- Get buy invoices menu ---
        with page.expect_popup() as page1_info:
            page.get_by_role("button", name="MIS COMPROBANTES Consulta de").click()
        page1 = page1_info.value
        page1.get_by_role("link", name=re.compile("ARANCIA SERVICES")).click()
        # --- loop to get inbound and outbound invoices ---
        for index, (btn_id, file_name) in enumerate(comprobantes):
            page1.wait_for_load_state("networkidle")
            btn = page1.locator(btn_id)
            btn.wait_for(state="visible", timeout=30000)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)

            # --- filter by month ---
            page1.wait_for_load_state("networkidle")            
            page1.get_by_role("textbox", name="Fecha del Comprobante *").click()
            page1.get_by_text("Este mes").click()
            page1.get_by_role("button", name="Buscar").click()

            # --- download file ---
            with page1.expect_download() as download_info:
                page1.get_by_role("button", name="Excel").click()
            download = download_info.value
            download_path = os.path.join(os.getcwd(), "downloads")
            os.makedirs(download_path, exist_ok=True)
            file_path = os.path.join(download_path, file_name)
            download.save_as(file_path)
            print(f"✅ Archivo {file_name} descargado en: {download.path()}")

            # --- return to main menu once ---
            if index == 0:
                menu_principal = page1.locator("a[href='menuPrincipal.do']")
                menu_principal.wait_for(state="visible", timeout=30000)
                menu_principal.click(force=True)
                page1.wait_for_load_state("networkidle")

        
    except Exception as e:
         print(f"⚠️ Error en la descarga: {e}")       
    # ---------------------
    finally: 
        context.close()
        browser.close()

with sync_playwright() as playwright:
    download_reports(playwright)