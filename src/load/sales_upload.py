# --- import libraries ---
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
from dotenv import load_dotenv

# --- variables de entorno ---
load_dotenv()
required_vars = ['ARANCIA_URL', 'ARANCIA_USERNAME', 'ARANCIA_PASSWORD']
for var in required_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"❌ Missing environment variable: {var}")


import os
from playwright.sync_api import Playwright, sync_playwright

def bot_init(playwright: Playwright, headless: bool = False):
    url = os.environ["ARANCIA_URL"]
    user = os.environ["ARANCIA_USERNAME"]
    password = os.environ["ARANCIA_PASSWORD"]

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()

    # Login
    page.goto(url, wait_until="domcontentloaded")
    page.fill('input[name="TextBox1"]', user)   # o '#TextBox1' si es ID
    page.fill('input[name="TextBox2"]', password)
    page.get_by_role("button", name="Ingresar").click()

    # En vez de sleep: esperar algo del "menú principal"
    # Ajustá este selector a algo que siempre exista post-login:
    page.wait_for_selector("#Button10", timeout=30_000)
    return browser, page

def go_to_invoicing_sales(page):
    # Click "facturación" (según tu Selenium: Button10)
    page.locator("#Button10").click()

    # Esperar a que el frame aparezca
    page.wait_for_selector('iframe[name="facturacion"], frame[name="facturacion"]', timeout=30_000)

    # Entrar al frame "facturacion" y click en Button5
    facturacion = page.frame(name="facturacion")
    if facturacion is None:
        raise RuntimeError("No encontré el frame 'facturacion'")

    facturacion.locator("#Button5").click()

    # Ahora dentro de "marco"
    page.wait_for_selector('iframe[name="marco"], frame[name="marco"]', timeout=30_000)
    marco = page.frame(name="marco")
    if marco is None:
        raise RuntimeError("No encontré el frame 'marco'")

    return marco  # devolvemos el frame donde se interactúa

def configure_invoice_form(marco):
    # Quitar check "aéreo" y poner "manual"
    marco.locator("#CheckBoxList1_0").click()
    marco.locator("#CheckBoxList1_3").click()

    # Set IVAS count = 3
    contar = marco.locator("#contar")
    contar.fill("3")
    contar.press("Tab")

    # Set IVA fields
    ivasa1 = marco.locator("#ivasa1")
    ivasa1.fill("0")
    ivasa1.press("Tab")

    ivasa2 = marco.locator("#ivasa2")
    ivasa2.fill("10.5")  # con punto como dijiste
    ivasa2.press("Tab")

def upload_rows(marco, clean_data):
    for _, row in clean_data.iterrows():
        # Totales
        marco.locator("#total1").fill(str(row["TOTAL_NO_GRAVADO"]))
        marco.locator("#total1").press("Tab")

        marco.locator("#total2").fill(str(row["TOTAL_10.5"]))
        marco.locator("#total2").press("Tab")

        # En tu Selenium era By.NAME total3
        marco.locator('[name="total3"]').fill(str(row["TOTAL_21"]))
        marco.locator('[name="total3"]').press("Tab")

        # Click para avanzar (Button2)
        marco.locator("#Button2").click()

        # Esperar a que aparezcan los campos del formulario (ajustar selector si hace falta)
        marco.wait_for_selector('[name="TextBox3"]', timeout=30_000)

        # Datos cliente
        marco.locator('[name="TextBox3"]').fill(str(row["Cliente"]))  # Razón social
        marco.locator('[name="TextBox3"]').press("Tab")

        marco.locator('[name="TextBox4"]').fill(str(row["CUIT"]))     # CUIT
        marco.locator('[name="TextBox4"]').press("Tab")

        marco.locator('[name="TextBox6"]').fill(str(row["Factura"]))  # Número factura
        marco.locator('[name="TextBox6"]').press("Tab")

        marco.locator('[name="TextBox7"]').fill(str(row["tipo3_new"]))  # Clase
        marco.locator('[name="TextBox7"]').press("Tab")

        marco.locator('[name="TextBox8"]').fill(str(row["Fecha"]))      # Fecha
        # si requiere tab:
        # marco.locator('[name="TextBox8"]').press("Tab")

        # Grabar
        marco.locator("#Button5").click()

        # Esperar confirmación / que vuelva a estado listo para la siguiente carga
        # Ajustá a un selector real (mensaje OK, o que reaparezca Button2, etc.)
        marco.wait_for_timeout(1000)  # último recurso; ideal: wait_for_selector de un "OK"

def run_sales_upload(clean_data, headless: bool = True):
    with sync_playwright() as playwright:
        browser, page = bot_init(playwright, headless=headless)
        try:
            marco = go_to_invoicing_sales(page)
            configure_invoice_form(marco)
            upload_rows(marco, clean_data)
        finally:
            browser.close()



# -----------------------------------------------------------



# # --- FUNCION 3: CARGAR VENTAS
# def upload_sales(page):





# # --- FUNCION 1: CARGA DE COMPRAS ---

# def cargar_facturas_compra(data: pd.DataFrame):
#     """
#     Carga los datos de un DataFrame en el sistema Arancia utilizando Playwright.
#     Las credenciales y la URL se toman desde el archivo .env.
#     """

#     # --- Cargar variables de entorno ---
#     load_dotenv()
#     ARANCIA_URL = os.getenv("ARANCIA_URL")
#     ARANCIA_USERNAME = os.getenv("ARANCIA_USERNAME")
#     ARANCIA_PASSWORD = os.getenv("ARANCIA_PASSWORD")

#     # Validación básica
#     if not ARANCIA_URL or not ARANCIA_USERNAME or not ARANCIA_PASSWORD:
#         raise ValueError("Faltan variables ARANCIA_URL, ARANCIA_USERNAME o ARANCIA_PASSWORD en el archivo .env")

#     # --- Iniciar Playwright ---
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)  # headless=True si no querés ver la ventana
#         context = browser.new_context()
#         page = context.new_page()

#         # --- 1. Ingresar a la página ---
#         page.goto(ARANCIA_URL)
#         page.wait_for_load_state("networkidle")

#         # --- 2. Entrar a la web ---
#         page.click("#Button1")
#         page.wait_for_timeout(2000)

#         # --- 3. Iniciar sesión ---
#         page.fill("#TextBox1", ARANCIA_USERNAME)
#         page.fill("#TextBox2", ARANCIA_PASSWORD)
#         page.click("#Button1")
#         page.wait_for_load_state("networkidle")

#         # --- 4. Ir al módulo de facturación ---
#         page.click("#Button10")
#         page.wait_for_timeout(2000)

#         # --- 5. Cambiar al frame "facturacion" ---
#         facturacion_frame = page.frame(name="facturacion")
#         facturacion_frame.click("#Button3")
#         page.wait_for_timeout(2000)

#         # --- 6. Cambiar al frame "marco" para cargar datos ---
#         marco_frame = page.frame(name="marco")

#         # --- 7. Iterar sobre el DataFrame y cargar los datos ---
#         for index, row in data.iterrows():
#             marco_frame.fill('#DetailsView1_TextBox1', str(row['Fecha']))
#             marco_frame.fill('#DetailsView1_TextBox2', str(row['Fecha']))
#             marco_frame.fill('input[name="DetailsView1$ctl02"]', str(row['Tipo3']))
#             marco_frame.fill('input[name="DetailsView1$ctl03"]', str(row['Factura']))
#             marco_frame.fill('input[name="DetailsView1$ctl04"]', str(row['Proveedor']))
#             marco_frame.fill('input[name="DetailsView1$ctl05"]', str(row['CUIT']))
#             marco_frame.fill('input[name="DetailsView1$TextBox3"]', str(row['NETO 10.5']))
#             marco_frame.fill('input[name="DetailsView1$TextBox4"]', str(row['NETO 21']))
#             marco_frame.fill('input[name="DetailsView1$TextBox5"]', str(row['IVA 10.5']))
#             marco_frame.fill('input[name="DetailsView1$TextBox6"]', str(row['IVA 21']))
#             marco_frame.fill('input[name="DetailsView1$TextBox7"]', str(row['TOTAL_NO_GRAVADO']))

#             # Hacer clic en "Agregar"
#             marco_frame.click('text=Agregar')
#             page.wait_for_timeout(2000)  # Espera ligera para evitar duplicados

#             print(f"✅ Fila {index+1} cargada correctamente")

#         # --- 8. Cierre del navegador ---
#         print("🎉 Carga finalizada correctamente.")
#         browser.close()

# # --- FUNCION 2: CARGA DE VENTAS ---

# def cargar_facturas_ventas(data: pd.DataFrame):
#     """
#     Carga facturas de ventas en el sistema Arancia utilizando Playwright.
#     Usa credenciales y URL desde el archivo .env
#     """

#     # --- Cargar variables de entorno ---
#     load_dotenv()
#     ARANCIA_URL = os.getenv("ARANCIA_URL")
#     ARANCIA_USERNAME = os.getenv("ARANCIA_USERNAME")
#     ARANCIA_PASSWORD = os.getenv("ARANCIA_PASSWORD")

#     if not all([ARANCIA_URL, ARANCIA_USERNAME, ARANCIA_PASSWORD]):
#         raise ValueError("Faltan variables ARANCIA_URL, ARANCIA_USERNAME o ARANCIA_PASSWORD en el archivo .env")

#     # --- Iniciar Playwright ---
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=False)
#         context = browser.new_context()
#         page = context.new_page()

#         # --- 1. Ingresar a la página ---
#         page.goto(ARANCIA_URL)
#         page.wait_for_load_state("networkidle")

#         # --- 2. Entrar a la web ---
#         page.click("#Button1")
#         page.wait_for_timeout(2000)

#         # --- 3. Iniciar sesión ---
#         page.fill("#TextBox1", ARANCIA_USERNAME)
#         page.fill("#TextBox2", ARANCIA_PASSWORD)
#         page.click("#Button1")
#         page.wait_for_load_state("networkidle")

#         # --- 4. Ir al módulo de facturación ---
#         page.click("#Button10")
#         page.wait_for_timeout(1500)

#         # --- 5. Cambiar al frame 'facturacion' y abrir la subpestaña de facturas de venta ---
#         facturacion_frame = page.frame(name="facturacion")
#         facturacion_frame.click("#Button5")
#         page.wait_for_timeout(1000)

#         # --- 6. Cambiar al frame 'marco' para cargar facturas ---
#         marco_frame = page.frame(name="marco")

#         # --- 7. Configurar checkboxes ---
#         marco_frame.click("#CheckBoxList1_0")  # Quitar “aéreo”
#         marco_frame.wait_for_timeout(1000)
#         marco_frame.click("#CheckBoxList1_3")  # Activar “manual”
#         marco_frame.wait_for_timeout(1000)

#         # --- 8. Campo de IVAS ---
#         marco_frame.fill("#contar", "3")
#         marco_frame.keyboard.press("Tab")
#         marco_frame.wait_for_timeout(1000)

#         # --- 9. Configurar IVAS específicos ---
#         valores = {
#             "ivasa1": "0",
#             "ivasa2": "10.5"
#         }

#         for field_id, valor in valores.items():
#             marco_frame.fill(f"#{field_id}", valor)
#             marco_frame.keyboard.press("Tab")
#             marco_frame.wait_for_timeout(1000)

#         # --- 10. Iterar sobre cada fila del DataFrame ---
#         for index, row in clean_data.iterrows():
#             print(f"➡️ Cargando fila {index + 1}...")

#             # TOTAL_NO_GRAVADO
#             marco_frame.fill("#total1", str(row["TOTAL_NO_GRAVADO"]))
#             marco_frame.keyboard.press("Tab")

#             # TOTAL_10.5
#             marco_frame.fill("#total2", str(row["TOTAL_10.5"]))
#             marco_frame.keyboard.press("Tab")

#             # TOTAL_21
#             marco_frame.fill('[name="total3"]', str(row["TOTAL_21"]))
#             marco_frame.keyboard.press("Tab")

#             # Click en botón para agregar factura
#             marco_frame.click("#Button2")
#             marco_frame.wait_for_timeout(2000)

#             # RAZON SOCIAL
#             marco_frame.fill('[name="TextBox3"]', str(row["Cliente"]))
#             marco_frame.keyboard.press("Tab")

#             # CUIT
#             marco_frame.fill('[name="TextBox4"]', str(row["CUIT"]))
#             marco_frame.keyboard.press("Tab")

#             # FACTURA NÚMERO
#             marco_frame.fill('[name="TextBox6"]', str(row["Factura"]))
#             marco_frame.keyboard.press("Tab")

#             # CLASE
#             marco_frame.fill('[name="TextBox7"]', str(row["tipo3_new"]))
#             marco_frame.keyboard.press("Tab")

#             # FECHA
#             marco_frame.fill('[name="TextBox8"]', str(row["Fecha"]))
#             marco_frame.wait_for_timeout(1000)

#             # GRABAR
#             marco_frame.click("#Button5")
#             marco_frame.wait_for_timeout(1500)

#             print(f"✅ Fila {index + 1} cargada correctamente.")

#         print("🎉 Carga de facturas finalizada con éxito.")
#         browser.close()


# # --------------------------------------------------