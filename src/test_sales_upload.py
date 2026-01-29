# This document is tended to run all the scripts 

from transform.afip import transform_afip_outbound_invoices
from transform.bookit import procesar_outbound_html
from compare.afip_vs_bookit import comparar_facturas_venta
#from load.sales_upload import all

import os
import lxml
import pandas as pd
import string
import numpy as np

afip_data = pd.read_excel('../downloads/comprobantes_emitidos.xlsx', header=0, skiprows=1)

afip_data_outbound = transform_afip_outbound_invoices(afip_data)
bookit_data_outbound = procesar_outbound_html('../downloads/outbound.html')
clean_data = comparar_facturas_venta(afip_data_outbound,bookit_data_outbound,1)

# -----------------------------------

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
    time.sleep(3)
    return browser, page

def go_to_invoicing_sales(page):
    # Click "facturación" (según tu Selenium: Button10)
    page.get_by_role("button", name="Facturacion").click()

    # Esperar a que aparezca el iframe "facturacion"
    page.wait_for_selector("iframe[name='facturacion']")
    frame_facturacion = page.frame(name="facturacion")
    frame_facturacion.get_by_role("button", name="facturacion").click()

    # Esperás a que cargue el iframe interno
    frame_marco = None
    for f in frame_facturacion.child_frames:
        if f.name == "marco":
            frame_marco = f
            break

    return frame_marco  # devolvemos el frame donde se interactúa

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

def run_sales_upload(clean_data, headless: bool = False):
    with sync_playwright() as playwright:
        browser, page = bot_init(playwright, headless=headless)
        try:
            marco = go_to_invoicing_sales(page)
            configure_invoice_form(marco)
            upload_rows(marco, clean_data)
        finally:
            browser.close()



run_sales_upload(clean_data)