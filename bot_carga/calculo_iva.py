"""Extrae el resumen mensual de Cálculo de IVA en Arancia."""
import argparse
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

from afip_common.config import load_arancia_settings

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
FIELDS = ("neto_105", "neto_21", "iva_105", "iva_21", "no_gravado", "total")
CALCULATIONS = {
    "diferencia iva 21": "diferencia_iva_21",
    "diferencia iva 10.5": "diferencia_iva_105",
    "diferencia no gravado": "diferencia_no_gravado",
    "diferencia facturacion": "diferencia_facturacion",
    "importe gravado del 21": "importe_gravado_21",
    "importe gravado del 10.5": "importe_gravado_105",
    "importe gravado faltante": "importe_gravado_faltante",
}


def normalized(value):
    return "".join(
        character for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


def parse_amount(value):
    value = value.strip().replace("\u00a0", "").replace(" ", "")
    if "," in value and "." in value:
        decimal = "," if value.rfind(",") > value.rfind(".") else "."
        value = value.replace("." if decimal == "," else ",", "")
        value = value.replace(decimal, ".")
    else:
        value = value.replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", value):
        raise ValueError(f"Importe inválido en Cálculo de IVA: {value!r}")
    return str(Decimal(value).quantize(Decimal("0.01")))


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"tag": tag, "text": ""}

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = self.cell["text"].strip()
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_monthly_html(html):
    reader = TableReader()
    reader.feed(html)
    records = []
    for table in reader.tables:
        headers = " ".join(normalized(cell["text"]) for row in table for cell in row if cell["tag"] == "th")
        if not all(label in headers for label in ("fecha", "neto", "iva", "total")):
            continue
        record = None
        calculations = {}
        for row in table:
            cells = [cell["text"] for cell in row if cell["tag"] == "td"]
            if len(cells) == 13:
                period = normalized(cells[0])
                match = re.fullmatch(r"([a-z]+)\s+(20\d{2})", period)
                if not match or match.group(1) not in MONTHS:
                    continue
                amounts = [parse_amount(value) for value in cells[1:]]
                record = {
                    "periodo": f"{match.group(2)}-{MONTHS[match.group(1)]:02d}",
                    "ventas": dict(zip(FIELDS, amounts[:6])),
                    "compras": dict(zip(FIELDS, amounts[6:])),
                }
            elif len(cells) == 2:
                label = normalized(cells[0]).strip()
                if label in CALCULATIONS:
                    calculations[CALCULATIONS[label]] = parse_amount(cells[1])
        if record:
            if set(calculations) != set(CALCULATIONS.values()):
                raise ValueError(f"Faltan importes calculados para {record['periodo']}.")
            record["calculos"] = calculations
            records.append(record)
    if not records:
        raise ValueError("No se encontró una tabla mensual con las doce columnas esperadas.")
    periods = [item["periodo"] for item in records]
    if len(periods) != len(set(periods)):
        raise ValueError("Cálculo de IVA contiene períodos duplicados.")
    return records


def fetch_monthly_records():
    settings = load_arancia_settings()
    if not settings.url:
        raise ValueError("Configurá ARANCIA_URL en .env.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(settings.url, wait_until="domcontentloaded")
            page.locator("#TextBox1").fill(settings.username)
            page.locator("#TextBox2").fill(settings.password)
            page.locator("#Button1").click()
            page.wait_for_load_state("networkidle")
            page.locator("#Button10").click()
            frame = page.frame(name="facturacion")
            if frame is None:
                raise ValueError("No se encontró el módulo Facturación.")
            frame.get_by_text(re.compile("c[aá]lculo de iva", re.I), exact=True).first.click()
            frame.page.wait_for_timeout(1_000)
            marco = next((child for child in frame.child_frames if child.name == "marco"), None)
            if marco is None:
                raise ValueError("No se encontró el marco de Cálculo de IVA.")
            marco.locator("table th").first.wait_for(state="attached")
            return parse_monthly_html(marco.content())
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Leer una captura HTML para verificar el extractor.")
    args = parser.parse_args()
    records = parse_monthly_html(args.html.read_text(encoding="utf-8")) if args.html else fetch_monthly_records()
    import json
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
