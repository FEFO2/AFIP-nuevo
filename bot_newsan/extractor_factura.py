from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF_DIR = BASE_DIR / "facturas_para_carga"
DEFAULT_OUTPUT_PATH = BASE_DIR / "salida_csv" / "facturas_extraidas.csv"
COPY_LABELS = {"original", "duplicado", "triplicado"}
DATE_PATTERN = re.compile(r"\d{2}/\d{2}/\d{4}")
AMOUNT_PATTERN = r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d+"
ITEM_DETAIL_PATTERN = re.compile(
    rf"""
    ^
    (?P<cantidad>{AMOUNT_PATTERN})\s+
    (?P<unidad_medida>[A-Za-zA-Za-z.]+)\s+
    (?P<precio_unitario>{AMOUNT_PATTERN})\s+
    (?P<bonificacion>{AMOUNT_PATTERN})\s+
    (?P<subtotal>{AMOUNT_PATTERN})\s+
    (?P<alicuota_iva>(?:\d{{1,2}}(?:[.,]\d+)?%|No\s+gravado))\s+
    (?P<subtotal_con_iva>{AMOUNT_PATTERN})
    $
    """,
    re.VERBOSE,
)
ITEM_START_PATTERN = re.compile(rf"(?P<numeric>{AMOUNT_PATTERN}\s+[A-Za-z.]+.*)")
TOTAL_PATTERNS = {
    "importe_otros_tributos": re.compile(rf"Importe Otros Tributos:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "importe_neto_no_gravado": re.compile(rf"Importe Neto No Gravado:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "importe_neto_gravado": re.compile(rf"Importe Neto Gravado:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_27": re.compile(rf"IVA 27%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_21": re.compile(rf"IVA 21%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_10_5": re.compile(rf"IVA 10(?:[.,]5)?%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_5": re.compile(rf"IVA 5%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_2_5": re.compile(rf"IVA 2(?:[.,]5)?%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "iva_0": re.compile(rf"IVA 0%:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
    "importe_total": re.compile(rf"Importe Total:\s*\$\s*(?P<value>{AMOUNT_PATTERN})"),
}


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def normalize_block(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_match(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return normalize_block(text).lower()


def parse_amount(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    normalized = raw_value.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def sanitize_csv_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_block(value)
    return value


def extract_page_texts(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def extract_copy_label(page_text: str) -> str | None:
    for raw_line in page_text.splitlines()[:5]:
        line = normalize_match(raw_line)
        if line in COPY_LABELS:
            return clean_line(raw_line)
    return None


def canonicalize_page(page_text: str) -> str:
    filtered_lines: list[str] = []
    for raw_line in page_text.splitlines():
        cleaned = clean_line(raw_line)
        if not cleaned or normalize_match(cleaned) in COPY_LABELS:
            continue
        filtered_lines.append(cleaned)
    return "\n".join(filtered_lines)


def unique_page_texts(page_texts: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_pages: list[str] = []
    for page_text in page_texts:
        canonical = canonicalize_page(page_text)
        if canonical in seen:
            continue
        seen.add(canonical)
        unique_pages.append(canonical)
    return unique_pages


def find_index(lines: list[str], expected: str) -> int | None:
    expected_normalized = normalize_match(expected)
    for index, line in enumerate(lines):
        if normalize_match(line) == expected_normalized:
            return index
    return None


def next_matching_line(lines: list[str], start_index: int, pattern: re.Pattern[str]) -> str | None:
    for line in lines[start_index + 1 :]:
        if pattern.fullmatch(line):
            return line
    return None


def parse_customer_line(line: str) -> dict[str, str | None]:
    match = re.match(r"^(?P<cuit>\d{11})\s+(?P<razon_social>.+)$", line)
    if not match:
        return {"cuit": None, "razon_social": line or None}
    return match.groupdict()


def parse_invoice_header(lines: list[str], unique_text: str) -> dict[str, Any]:
    period_line = next((line for line in lines if len(DATE_PATTERN.findall(line)) == 3), "")
    period_dates = DATE_PATTERN.findall(period_line)
    standalone_dates = [line for line in lines if DATE_PATTERN.fullmatch(line)]

    emission_index = find_index(lines, "Fecha de Emision:")
    emitter_name = None
    emitter_address = None
    if emission_index is not None and emission_index + 3 < len(lines):
        emitter_name = lines[emission_index + 1]
        emitter_address = " ".join(lines[emission_index + 2 : emission_index + 4])

    customer_line = next((line for line in lines if re.match(r"^\d{11}\s+.+$", line)), "")
    customer = parse_customer_line(customer_line)
    customer_address = None
    if customer_line and customer_line in lines:
        customer_index = lines.index(customer_line)
        if customer_index + 1 < len(lines):
            customer_address = lines[customer_index + 1]

    point_of_sale = None
    invoice_number = None
    point_line = next((line for line in lines if normalize_match(line).startswith("punto de venta:")), "")
    point_match = re.search(r"Punto de Venta:\s*Comp\.\s*Nro:(?P<pv>\d+)\s+(?P<number>\d+)", point_line)
    if point_match:
        point_of_sale = point_match.group("pv")
        invoice_number = point_match.group("number")

    invoice_type = None
    invoice_code = None
    invoice_type_line = next((line for line in lines if normalize_match(line).startswith("factura")), "")
    type_match = re.search(r"FACTURA\s*(?P<type>[A-Z])\s*COD\.\s*(?P<code>\d+)", invoice_type_line)
    if type_match:
        invoice_type = type_match.group("type")
        invoice_code = type_match.group("code")

    iva_lines = [line for line in lines if normalize_match(line).startswith("iva ")]
    activity_label_index = find_index(lines, "Fecha de Inicio de Actividades:")
    start_activities = None
    if activity_label_index is not None:
        start_activities = next_matching_line(lines, activity_label_index, DATE_PATTERN)

    cae_match = re.search(
        r"Comprobante Autorizado.*?(?P<fecha_vto>\d{2}/\d{2}/\d{4})\s+(?P<cae>\d{14})",
        unique_text,
        re.DOTALL,
    )

    legend = next((line for line in lines if "LEGAJO" in normalize_match(line).upper()), None)
    page_reference = next((line for line in lines if normalize_match(line).startswith("pag.")), None)
    emitter_cuits = [line for line in lines if re.fullmatch(r"\d{11}", line)]
    company_name_index = find_index(lines, "Razon Social:")
    commercial_name = None
    if company_name_index is not None and company_name_index + 1 < len(lines):
        commercial_name = lines[company_name_index + 1]

    return {
        "fecha_emision": standalone_dates[0] if standalone_dates else None,
        "periodo_facturado": {
            "desde": period_dates[0] if len(period_dates) > 0 else None,
            "hasta": period_dates[1] if len(period_dates) > 1 else None,
            "vencimiento_pago": period_dates[2] if len(period_dates) > 2 else None,
        },
        "emisor": {
            "razon_social": emitter_name,
            "nombre_comercial": commercial_name,
            "cuit": emitter_cuits[0] if emitter_cuits else None,
            "domicilio": emitter_address,
            "condicion_iva": iva_lines[0] if iva_lines else None,
            "fecha_inicio_actividades": start_activities,
        },
        "receptor": {
            "cuit": customer["cuit"],
            "razon_social": customer["razon_social"],
            "domicilio": customer_address,
            "condicion_iva": iva_lines[1] if len(iva_lines) > 1 else iva_lines[0] if iva_lines else None,
            "condicion_venta": next(
                (line for line in lines if "tarjeta de credito" in normalize_match(line)),
                None,
            ),
        },
        "comprobante": {
            "tipo": invoice_type,
            "codigo": invoice_code,
            "punto_venta": point_of_sale,
            "numero": invoice_number,
            "cae": cae_match.group("cae") if cae_match else None,
            "vencimiento_cae": cae_match.group("fecha_vto") if cae_match else None,
            "pagina_referencia": page_reference,
        },
        "leyenda": legend,
    }


def extract_items(lines: list[str]) -> list[dict[str, Any]]:
    start_index = find_index(lines, "IVA Subtotal c/IVA")
    if start_index is None:
        return []

    end_index = None
    for index in range(start_index + 1, len(lines)):
        if normalize_match(lines[index]).startswith("cae"):
            end_index = index
            break

    if end_index is None:
        return []

    section_lines = [line for line in lines[start_index + 1 : end_index] if line]
    items: list[dict[str, Any]] = []
    description_parts: list[str] = []
    index = 0

    while index < len(section_lines):
        line = section_lines[index]
        numeric_start = ITEM_START_PATTERN.search(line)
        if not numeric_start:
            description_parts.append(line)
            index += 1
            continue

        prefix = clean_line(line[: numeric_start.start("numeric")])
        numeric_parts = [clean_line(numeric_start.group("numeric"))]
        if prefix:
            description_parts.append(prefix)

        while index + 1 < len(section_lines):
            current_numeric = normalize_block(" ".join(numeric_parts))
            if ITEM_DETAIL_PATTERN.fullmatch(current_numeric):
                break
            index += 1
            numeric_parts.append(section_lines[index])

        current_numeric = normalize_block(" ".join(numeric_parts))
        match = ITEM_DETAIL_PATTERN.fullmatch(current_numeric)
        if not match:
            description_parts = []
            index += 1
            continue

        data = match.groupdict()
        items.append(
            {
                "descripcion": normalize_block(" ".join(description_parts)),
                "cantidad": parse_amount(data["cantidad"]),
                "unidad_medida": data["unidad_medida"],
                "precio_unitario": parse_amount(data["precio_unitario"]),
                "bonificacion": parse_amount(data["bonificacion"]),
                "subtotal": parse_amount(data["subtotal"]),
                "alicuota_iva": normalize_block(data["alicuota_iva"]),
                "subtotal_con_iva": parse_amount(data["subtotal_con_iva"]),
            }
        )
        description_parts = []
        index += 1

    return items


def extract_totals(unique_text: str) -> dict[str, float | None]:
    totals: dict[str, float | None] = {}
    for key, pattern in TOTAL_PATTERNS.items():
        matches = pattern.findall(unique_text)
        totals[key] = parse_amount(matches[-1] if matches else None)
    return totals


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    page_texts = extract_page_texts(pdf_path)
    unique_pages = unique_page_texts(page_texts)
    unique_text = "\n\n".join(unique_pages)
    lines = [clean_line(line) for line in unique_text.splitlines() if clean_line(line)]

    return {
        "archivo": pdf_path.name,
        "ruta": str(pdf_path.resolve()),
        "paginas_totales": len(page_texts),
        "copias_detectadas": [label for label in (extract_copy_label(page) for page in page_texts) if label],
        "texto_unico": unique_text,
        "datos_generales": parse_invoice_header(lines, unique_text),
        "items": extract_items(lines),
        "totales": extract_totals(unique_text),
    }


def flatten_invoice_data(data: dict[str, Any]) -> dict[str, Any]:
    general = data["datos_generales"]
    periodo = general["periodo_facturado"]
    emisor = general["emisor"]
    receptor = general["receptor"]
    comprobante = general["comprobante"]
    items = data["items"]
    totals = data["totales"]

    return {
        "archivo": data["archivo"],
        "ruta": data["ruta"],
        "paginas_totales": data["paginas_totales"],
        "copias_detectadas": " | ".join(data["copias_detectadas"]),
        "fecha_emision": general["fecha_emision"],
        "periodo_desde": periodo["desde"],
        "periodo_hasta": periodo["hasta"],
        "vencimiento_pago": periodo["vencimiento_pago"],
        "emisor_razon_social": emisor["razon_social"],
        "emisor_nombre_comercial": emisor["nombre_comercial"],
        "emisor_cuit": emisor["cuit"],
        "emisor_domicilio": emisor["domicilio"],
        "emisor_condicion_iva": emisor["condicion_iva"],
        "emisor_fecha_inicio_actividades": emisor["fecha_inicio_actividades"],
        "receptor_cuit": receptor["cuit"],
        "receptor_razon_social": receptor["razon_social"],
        "receptor_domicilio": receptor["domicilio"],
        "receptor_condicion_iva": receptor["condicion_iva"],
        "condicion_venta": receptor["condicion_venta"],
        "comprobante_tipo": comprobante["tipo"],
        "comprobante_codigo": comprobante["codigo"],
        "punto_venta": comprobante["punto_venta"],
        "numero_comprobante": comprobante["numero"],
        "cae": comprobante["cae"],
        "vencimiento_cae": comprobante["vencimiento_cae"],
        "pagina_referencia": comprobante["pagina_referencia"],
        "leyenda": general["leyenda"],
        "cantidad_items": len(items),
        "items_descripcion": " | ".join(item["descripcion"] for item in items),
        "items_alicuota_iva": " | ".join(str(item["alicuota_iva"]) for item in items),
        "items_subtotal": " | ".join("" if item["subtotal"] is None else str(item["subtotal"]) for item in items),
        "items_subtotal_con_iva": " | ".join(
            "" if item["subtotal_con_iva"] is None else str(item["subtotal_con_iva"]) for item in items
        ),
        "items_json": json.dumps(items, ensure_ascii=False),
        "importe_otros_tributos": totals["importe_otros_tributos"],
        "importe_neto_no_gravado": totals["importe_neto_no_gravado"],
        "importe_neto_gravado": totals["importe_neto_gravado"],
        "iva_27": totals["iva_27"],
        "iva_21": totals["iva_21"],
        "iva_10_5": totals["iva_10_5"],
        "iva_5": totals["iva_5"],
        "iva_2_5": totals["iva_2_5"],
        "iva_0": totals["iva_0"],
        "importe_total": totals["importe_total"],
        "texto_unico": data["texto_unico"],
    }


def resolve_pdf_paths(pdf_dir: Path, pdf_arg: Path | None) -> list[Path]:
    if pdf_arg:
        pdf_path = pdf_arg if pdf_arg.is_absolute() else BASE_DIR / pdf_arg
        return [pdf_path]
    return sorted(pdf_dir.glob("*.pdf"))


def write_csv_output(rows: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No hay filas para escribir en el CSV.")

    sanitized_rows = [
        {key: sanitize_csv_value(value) for key, value in row.items()}
        for row in rows
    ]

    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(sanitized_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sanitized_rows)
    return output_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extrae informacion de facturas PDF y la consolida en un CSV.")
    parser.add_argument("--pdf", type=Path, help="Ruta a un PDF especifico. Si no se informa, procesa toda la carpeta.")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Carpeta que contiene los PDFs a procesar.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Ruta del CSV consolidado de salida.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Imprime por pantalla las filas generadas.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    pdf_dir = args.pdf_dir if args.pdf_dir.is_absolute() else BASE_DIR / args.pdf_dir
    output_path = args.output if args.output.is_absolute() else BASE_DIR / args.output
    pdf_paths = resolve_pdf_paths(pdf_dir, args.pdf)

    if not pdf_paths:
        raise FileNotFoundError(f"No se encontraron PDFs en {pdf_dir}")

    rows: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            raise FileNotFoundError(f"No existe el PDF: {pdf_path}")
        rows.append(flatten_invoice_data(parse_pdf(pdf_path)))

    csv_path = write_csv_output(rows, output_path)
    print(f"CSV generado: {csv_path}")
    print(f"Facturas procesadas: {len(rows)}")

    if args.stdout:
        print(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
