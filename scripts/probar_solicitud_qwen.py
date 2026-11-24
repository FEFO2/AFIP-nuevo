"""Convierte un correo simulado en JSON con Ollama; no crea órdenes."""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "solicitud_factura_ia_referencia.md"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

CONCEPT = {
    "type": "object",
    "properties": {
        "concepto": {"type": "string"},
        "importe_informado": {"type": ["string", "null"]},
        "precio_neto": {"type": ["string", "null"]},
        "iva": {
            "type": ["string", "null"],
            "enum": ["no gravado", "exento", "10,5%", "21%", None],
        },
    },
    "required": ["concepto", "importe_informado", "precio_neto", "iva"],
    "additionalProperties": False,
}

INVOICE = {
    "type": "object",
    "properties": {
        "cliente": {"type": ["string", "null"]},
        "cuit": {"type": ["string", "null"]},
        "tipo_factura": {"type": ["string", "null"], "enum": ["A", "B", None]},
        "condicion_iva": {
            "type": ["string", "null"],
            "enum": [
                "responsable inscripto", "responsable monotributo",
                "sujeto exento", "consumidor final", None,
            ],
        },
        "moneda": {"type": "string", "enum": ["ARS", "USD"]},
        "conceptos": {"type": "array", "items": CONCEPT},
    },
    "required": ["cliente", "cuit", "tipo_factura", "condicion_iva", "moneda", "conceptos"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {"facturas": {"type": "array", "items": INVOICE}},
    "required": ["facturas"],
    "additionalProperties": False,
}


def normalizar_importe(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", value):
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", value):
        value = value.replace(",", "")
    elif re.fullmatch(r"\d+(?:,\d{1,2})?", value):
        value = value.replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        return None
    whole, _, fraction = value.partition(".")
    return f"{int(whole)}.{fraction.ljust(2, '0')}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("texto", nargs="?", help="Correo simulado; si falta, se lee de stdin.")
    parser.add_argument("--modelo", default="qwen3:4b")
    args = parser.parse_args()

    texto = args.texto if args.texto is not None else sys.stdin.read()
    if not texto.strip():
        parser.error("Pasá el texto del correo como argumento o por stdin.")

    payload = {
        "model": args.modelo,
        "messages": [
            {
                "role": "system",
                "content": REFERENCE.read_text(encoding="utf-8")
                + "\nRespondé únicamente con JSON que cumpla el esquema proporcionado.",
            },
            {"role": "user", "content": texto},
        ],
        "format": SCHEMA,
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
        facturas = json.loads(result["message"]["content"])
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"No se pudo obtener un JSON de Ollama: {error}\n")

    if not isinstance(facturas, dict) or not isinstance(facturas.get("facturas"), list):
        parser.exit(1, "Ollama devolvió un JSON sin la lista facturas.\n")
    for invoice in facturas["facturas"]:
        for concept in invoice["conceptos"]:
            for key in ("importe_informado", "precio_neto"):
                concept[key] = normalizar_importe(concept[key])
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(facturas, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
