"""Consulta de clientes frecuentes por alias, nombre o documento."""

import argparse
import json
import unicodedata
from pathlib import Path


BASE = Path(__file__).resolve().parents[1] / ".local" / "clientes_recurrentes.json"


def normalizar(valor):
    texto = unicodedata.normalize("NFKD", valor.casefold())
    return "".join(caracter for caracter in texto if caracter.isalnum())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("consulta")
    args = parser.parse_args()
    clave = normalizar(args.consulta)
    if not clave:
        parser.error("Ingresá un nombre, alias o documento.")
    if not BASE.is_file():
        parser.error(f"No se encontró la base local de clientes: {BASE}")
    base = json.loads(BASE.read_text(encoding="utf-8"))
    resultados = []
    for cliente in base["clientes"]:
        nombres = [cliente["razon_social"], *cliente["alias"]]
        if clave.isdigit():
            coincide = clave == cliente["numero_documento"]
        else:
            coincide = any(clave in normalizar(nombre) for nombre in nombres)
        if coincide:
            resultados.append(cliente)
    print(json.dumps(resultados, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
