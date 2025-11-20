# import libraries
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
from dotenv import load_dotenv


# --- FUNCION 1: CARGA DE COMPRAS ---

def cargar_facturas_compra(data: pd.DataFrame):
    """
    Carga los datos de un DataFrame en el sistema Arancia utilizando Playwright.
    Las credenciales y la URL se toman desde el archivo .env.
    """

    # --- Cargar variables de entorno ---
    load_dotenv()
    ARANCIA_URL = os.getenv("ARANCIA_URL")
    ARANCIA_USERNAME = os.getenv("ARANCIA_USERNAME")
    ARANCIA_PASSWORD = os.getenv("ARANCIA_PASSWORD")

    # Validación básica
    if not ARANCIA_URL or not ARANCIA_USERNAME or not ARANCIA_PASSWORD:
        raise ValueError("Faltan variables ARANCIA_URL, ARANCIA_USERNAME o ARANCIA_PASSWORD en el archivo .env")

    # --- Iniciar Playwright ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=True si no querés ver la ventana
        context = browser.new_context()
        page = context.new_page()

        # --- 1. Ingresar a la página ---
        page.goto(ARANCIA_URL)
        page.wait_for_load_state("networkidle")

        # --- 2. Entrar a la web ---
        page.click("#Button1")
        page.wait_for_timeout(2000)

        # --- 3. Iniciar sesión ---
        page.fill("#TextBox1", ARANCIA_USERNAME)
        page.fill("#TextBox2", ARANCIA_PASSWORD)
        page.click("#Button1")
        page.wait_for_load_state("networkidle")

        # --- 4. Ir al módulo de facturación ---
        page.click("#Button10")
        page.wait_for_timeout(2000)

        # --- 5. Cambiar al frame "facturacion" ---
        facturacion_frame = page.frame(name="facturacion")
        facturacion_frame.click("#Button3")
        page.wait_for_timeout(2000)

        # --- 6. Cambiar al frame "marco" para cargar datos ---
        marco_frame = page.frame(name="marco")

        # --- 7. Iterar sobre el DataFrame y cargar los datos ---
        for index, row in data.iterrows():
            marco_frame.fill('#DetailsView1_TextBox1', str(row['Fecha']))
            marco_frame.fill('#DetailsView1_TextBox2', str(row['Fecha']))
            marco_frame.fill('input[name="DetailsView1$ctl02"]', str(row['Tipo3']))
            marco_frame.fill('input[name="DetailsView1$ctl03"]', str(row['Factura']))
            marco_frame.fill('input[name="DetailsView1$ctl04"]', str(row['Proveedor']))
            marco_frame.fill('input[name="DetailsView1$ctl05"]', str(row['CUIT']))
            marco_frame.fill('input[name="DetailsView1$TextBox3"]', str(row['NETO 10.5']))
            marco_frame.fill('input[name="DetailsView1$TextBox4"]', str(row['NETO 21']))
            marco_frame.fill('input[name="DetailsView1$TextBox5"]', str(row['IVA 10.5']))
            marco_frame.fill('input[name="DetailsView1$TextBox6"]', str(row['IVA 21']))
            marco_frame.fill('input[name="DetailsView1$TextBox7"]', str(row['TOTAL_NO_GRAVADO']))

            # Hacer clic en "Agregar"
            marco_frame.click('text=Agregar')
            page.wait_for_timeout(2000)  # Espera ligera para evitar duplicados

            print(f"✅ Fila {index+1} cargada correctamente")

        # --- 8. Cierre del navegador ---
        print("🎉 Carga finalizada correctamente.")
        browser.close()

# --- FUNCION 2: CARGA DE VENTAS ---

def cargar_facturas_ventas(data: pd.DataFrame):
    """
    Carga facturas de ventas en el sistema Arancia utilizando Playwright.
    Usa credenciales y URL desde el archivo .env
    """

    # --- Cargar variables de entorno ---
    load_dotenv()
    ARANCIA_URL = os.getenv("ARANCIA_URL")
    ARANCIA_USERNAME = os.getenv("ARANCIA_USERNAME")
    ARANCIA_PASSWORD = os.getenv("ARANCIA_PASSWORD")

    if not all([ARANCIA_URL, ARANCIA_USERNAME, ARANCIA_PASSWORD]):
        raise ValueError("Faltan variables ARANCIA_URL, ARANCIA_USERNAME o ARANCIA_PASSWORD en el archivo .env")

    # --- Iniciar Playwright ---
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # --- 1. Ingresar a la página ---
        page.goto(ARANCIA_URL)
        page.wait_for_load_state("networkidle")

        # --- 2. Entrar a la web ---
        page.click("#Button1")
        page.wait_for_timeout(2000)

        # --- 3. Iniciar sesión ---
        page.fill("#TextBox1", ARANCIA_USERNAME)
        page.fill("#TextBox2", ARANCIA_PASSWORD)
        page.click("#Button1")
        page.wait_for_load_state("networkidle")

        # --- 4. Ir al módulo de facturación ---
        page.click("#Button10")
        page.wait_for_timeout(1500)

        # --- 5. Cambiar al frame 'facturacion' y abrir la subpestaña de facturas de venta ---
        facturacion_frame = page.frame(name="facturacion")
        facturacion_frame.click("#Button5")
        page.wait_for_timeout(1000)

        # --- 6. Cambiar al frame 'marco' para cargar facturas ---
        marco_frame = page.frame(name="marco")

        # --- 7. Configurar checkboxes ---
        marco_frame.click("#CheckBoxList1_0")  # Quitar “aéreo”
        marco_frame.wait_for_timeout(1000)
        marco_frame.click("#CheckBoxList1_3")  # Activar “manual”
        marco_frame.wait_for_timeout(1000)

        # --- 8. Campo de IVAS ---
        marco_frame.fill("#contar", "3")
        marco_frame.keyboard.press("Tab")
        marco_frame.wait_for_timeout(1000)

        # --- 9. Configurar IVAS específicos ---
        valores = {
            "ivasa1": "0",
            "ivasa2": "10.5"
        }

        for field_id, valor in valores.items():
            marco_frame.fill(f"#{field_id}", valor)
            marco_frame.keyboard.press("Tab")
            marco_frame.wait_for_timeout(1000)

        # --- 10. Iterar sobre cada fila del DataFrame ---
        for index, row in clean_data.iterrows():
            print(f"➡️ Cargando fila {index + 1}...")

            # TOTAL_NO_GRAVADO
            marco_frame.fill("#total1", str(row["TOTAL_NO_GRAVADO"]))
            marco_frame.keyboard.press("Tab")

            # TOTAL_10.5
            marco_frame.fill("#total2", str(row["TOTAL_10.5"]))
            marco_frame.keyboard.press("Tab")

            # TOTAL_21
            marco_frame.fill('[name="total3"]', str(row["TOTAL_21"]))
            marco_frame.keyboard.press("Tab")

            # Click en botón para agregar factura
            marco_frame.click("#Button2")
            marco_frame.wait_for_timeout(2000)

            # RAZON SOCIAL
            marco_frame.fill('[name="TextBox3"]', str(row["Cliente"]))
            marco_frame.keyboard.press("Tab")

            # CUIT
            marco_frame.fill('[name="TextBox4"]', str(row["CUIT"]))
            marco_frame.keyboard.press("Tab")

            # FACTURA NÚMERO
            marco_frame.fill('[name="TextBox6"]', str(row["Factura"]))
            marco_frame.keyboard.press("Tab")

            # CLASE
            marco_frame.fill('[name="TextBox7"]', str(row["tipo3_new"]))
            marco_frame.keyboard.press("Tab")

            # FECHA
            marco_frame.fill('[name="TextBox8"]', str(row["Fecha"]))
            marco_frame.wait_for_timeout(1000)

            # GRABAR
            marco_frame.click("#Button5")
            marco_frame.wait_for_timeout(1500)

            print(f"✅ Fila {index + 1} cargada correctamente.")

        print("🎉 Carga de facturas finalizada con éxito.")
        browser.close()


# --------------------------------------------------