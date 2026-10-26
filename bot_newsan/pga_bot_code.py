import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_newsan.cargador_facturas import open_oracle as abrir_oracle


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
