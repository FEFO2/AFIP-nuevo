import os
import re

from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright


load_dotenv()


def _get_required_env(name: str, legacy_name: str | None = None) -> str:
    value = os.getenv(name)
    if value:
        return value

    if legacy_name:
        legacy_value = os.getenv(legacy_name)
        if legacy_value:
            return legacy_value

    legacy_hint = f" o {legacy_name}" if legacy_name else ""
    raise ValueError(f"Falta la variable de entorno {name}{legacy_hint}.")


def abrir_oracle(playwright: Playwright):
    url = _get_required_env("PGA_URL", "PAG_URL")
    username = _get_required_env("PGA_USERNAME")
    password = _get_required_env("PGA_PASSWORD")

    browser = playwright.chromium.launch(
        headless=False,
        slow_mo=2000,
    )
    context = browser.new_context()
    page = context.new_page()

    page.goto(url)
    page.get_by_role("textbox", name="Username").fill(username)
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Next").click()
    page.get_by_role("link", name="PÃ¡gina Inicial", exact=True).click()
    page.get_by_role("link", name="Crear factura").click()

    return browser, context, page


def prueba(page):
    page.locator("tr").filter(has_text=re.compile(r"^Crear factura: Ayuda$")).get_by_role("link")


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser, context, page = abrir_oracle(playwright)

        print("Oracle quedo abierto.")
        print("Puedes probar comandos usando la variable page.")
        print("Ejemplo: prueba(page)")

        import code
        code.interact(local=globals() | locals())

        context.close()
        browser.close()


# ejemplo:
# page.get_by_role("button", name="Algun boton").click()
# page.get_by_label("Proveedor").fill("Mi proveedor")
