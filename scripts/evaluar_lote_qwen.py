"""Evalúa una muestra local de correos con Qwen. No modifica órdenes."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "probar_solicitud_qwen.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origen", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--indices", default="1,2,3,4,5")
    args = parser.parse_args()
    local_dir = (ROOT / ".local").resolve()
    if not args.salida.resolve().is_relative_to(local_dir):
        parser.error("La salida debe guardarse dentro de .local para no subir datos de correos a Git.")
    mails = json.loads(args.origen.read_text(encoding="utf-8"))
    indices = [int(value) for value in args.indices.split(",")]
    if not isinstance(mails, list) or not all(isinstance(item, str) for item in mails):
        parser.error("El origen debe ser una lista JSON de correos de texto.")
    if not all(1 <= index <= len(mails) for index in indices):
        parser.error("Índice fuera de rango.")
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with args.salida.open("w", encoding="utf-8") as output:
        for index in indices:
            start = time.monotonic()
            try:
                process = subprocess.run(
                    [sys.executable, "-X", "utf8", str(SCRIPT)],
                    input=mails[index - 1],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=140,
                    check=False,
                )
                result = json.loads(process.stdout) if process.returncode == 0 else None
                error = process.stderr.strip() if process.returncode else None
            except (subprocess.TimeoutExpired, json.JSONDecodeError) as exception:
                result = None
                error = type(exception).__name__
            seconds = round(time.monotonic() - start, 1)
            output.write(json.dumps({"indice": index, "segundos": seconds,
                                     "resultado": result, "error": error}, ensure_ascii=False) + "\n")
            output.flush()
            status = "OK" if result is not None else "ERROR"
            print(f"Correo {index}: {status} ({seconds}s)", flush=True)


if __name__ == "__main__":
    main()
