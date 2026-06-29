import code
import os
import re
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright

load_dotenv()


def abrir_oracle(playwright: Playwright):
    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=1000
    )

    context = browser.new_context()
    page = context.new_page()

    page.goto("https://hdqc.fa.us2.oraclecloud.com/")
    page.get_by_role("textbox", name="Username").fill("pga@aranciatravel.com")

    password = os.getenv('PGA_PASSWORD')

    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Next").click()

    page.get_by_role("link", name="Página Inicial", exact=True).click()
    page.get_by_role("link", name="Crear factura").click()

    return browser, context, page


def prueba(page):
    page.locator("tr").filter(
        has_text=re.compile(r"^Crear factura: Ayuda$")
    ).get_by_role("link").click()


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser, context, page = abrir_oracle(playwright)

        print("Navegador abierto.")
        print("Puedes ejecutar comandos como:")
        print("  prueba(page)")
        print("  page.url")
        print("  page.get_by_role('button', name='Guardar').click()")
        print("Escribe exit() para salir.")

        code.interact(local=locals())

        context.close()
        browser.close()