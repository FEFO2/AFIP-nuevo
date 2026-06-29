import re
import os
from playwright.sync_api import Playwright, sync_playwright, expect

def abrir_oracle(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=2000
    )
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://hdqc.fa.us2.oraclecloud.com/")
    page.get_by_role("textbox", name="Username").fill("pga@aranciatravel.com")
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(os.getenv("PGA_PASSWORD"))
    page.get_by_role("button", name="Next").click()
    page.get_by_role("link", name="Página Inicial", exact=True).click()
    page.get_by_role("link", name="Crear factura").click()

    return browser, context, page

def prueba(page):
    page.locator("tr").filter(has_text=re.compile(r"^Crear factura: Ayuda$")).get_by_role("link")

if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser, context, page = abrir_oracle(playwright)

        print("Oracle quedó abierto.")
        print("Puedes probar comandos usando la variable page.")
        print("Ejemplo: prueba(page)")

        import code
        code.interact(local=globals() | locals())

        context.close()
        browser.close()


            # ejemplo:
    # page.get_by_role("button", name="Algún botón").click()
    # page.get_by_label("Proveedor").fill("Mi proveedor")

# def carga
# Unidad de negocio
#     page.get_by_role("combobox", name="Unidad de negocio").fill("pga")
#     page.get_by_role("combobox", name="Unidad de negocio").press("Tab")

# Proveedor
#     page.get_by_role("combobox", name="Proveedor", exact=True).fill("arancia")
#     page.get_by_role("combobox", name="Proveedor", exact=True).press("Tab")

# Click boton
#     page.get_by_role("button", name="Aceptar").click()

# Numero de factura
#     page.get_by_role("textbox", name="Número").fill("00002-00001234")

# Importe
#     page.get_by_role("textbox", name="Importe").fill("12345,12")

# Fecha
#     page.get_by_role("textbox", name="Fecha").fill("02/01/2026")

# Solicitante
#     page.get_by_role("combobox", name="Solicitante").fill("jorba")
#     page.get_by_role("combobox", name="Solicitante").press("Tab")

# Anexo Factura
#     page.get_by_role("link", name="Gestionar Anexos").click()
#     page.set_input_files("input[type='file']", r"C:\Users\ThinkPad-PC\Desktop\FACTURAS NEWSAN\30714894346_001_00002_00003564.pdf")
#     page.get_by_role("button", name="Aceptar").click()

# Clasificación fiscal del documento
    # page.get_by_role("link", name="*Tipo de Comprobante").click()
    # page.get_by_role("combobox", name="Clasificación fiscal de").fill("001_FACTURA_A")
    # page.get_by_role("combobox", name="Clasificación fiscal de").press("Tab")
    # page.locator('tr[_afrrk="0"]').locator('td.xen >> text=001_FACTURA_A').click()         
    # page.get_by_role("button", name="Aceptar").click()   

# Desbloquear lineas
#     page.get_by_role("button", name="Ampliar Líneas").click()

# Cargar lineas -> ASI CON TODAS LAS LINEAS

# Linea 1
    #     page.get_by_role("row", name="1 Ítem Tipo Importe Descripci").get_by_label("Importe").fill("1234,12")
    #     page.keyboard.press("Tab")
    #     page.get_by_role("combobox", name="Clasificación de impuestos").fill("ar_iva_general")
    #     page.keyboard.press("Tab")

# Linea 2
    #     page.locator('tr[_afrrk="1"]').locator(".xen.x1i5").click()
    #     page.get_by_role("row", name="1 Ítem Tipo Importe Descripci").get_by_label("Importe").fill("1234,12")
    #     page.keyboard.press("Tab")
    #     page.get_by_role("combobox", name="Clasificación de impuestos").fill("ar_iva_general")
    #     page.keyboard.press("Tab")

# Autodetectar impuestos -> Al expandir el menú, el sistema de PGA lo hace solo.
    #     page.get_by_role("button", name="Ampliar Impuestos").click()

# Completar datos CAE
#     page.get_by_role("link", name="*CAE/CAEA").click()
#     page.locator('[id="pt1:_FOr1:1:_FONSr2:0:MAnt2:0:pm1:r1:0:ap1:df1_headerDFF1Iterator__FLEX_Context__FLEX_EMPTY::content"]').select_option(label="CAE")
#     page.get_by_role("textbox", name="Número CAE").fill("123456789")
#     page.get_by_role("textbox", name="Fecha CAE").fill("01/01/2026")

# ACEPTAR LA CARGA
#     page.get_by_role("button", name="Cancelar", exact=True).click()

#     # ---------------------
#     context.close()
#     browser.close()
