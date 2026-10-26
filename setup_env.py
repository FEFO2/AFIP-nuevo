"""Preparar el entorno del proyecto: py -3.11 setup_env.py."""

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_VERSION = (3, 11)


def setup_environment(project_root: Path = PROJECT_ROOT) -> Path:
    if sys.version_info[:2] != PYTHON_VERSION:
        raise RuntimeError("Se necesita Python 3.11. Ejecuta: py -3.11 setup_env.py")

    lock_file = project_root / "requirements-lock.txt"
    if not lock_file.is_file():
        raise RuntimeError("Falta requirements-lock.txt. Descarga el proyecto completo.")

    environment = project_root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if environment.exists():
        if not (environment / "pyvenv.cfg").is_file() or not python.is_file():
            raise RuntimeError(
                ".venv ya existe pero no es un entorno válido. Revísalo antes de continuar."
            )
    else:
        print("Creando .venv con Python 3.11...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)

    result = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import json, sys; print(json.dumps({'version': list(sys.version_info[:2]), 'prefix': sys.prefix}))",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    details = json.loads(result.stdout)
    if (
        tuple(details["version"]) != PYTHON_VERSION
        or Path(details["prefix"]).resolve() != environment.resolve()
    ):
        raise RuntimeError("El entorno .venv debe usar Python 3.11 y pertenecer a este proyecto.")

    for description, arguments in (
        ("Instalando las versiones fijadas...", ["pip", "install", "-r", str(lock_file)]),
        ("Comprobando dependencias...", ["pip", "check"]),
        ("Instalando Chromium para Playwright...", ["playwright", "install", "chromium"]),
    ):
        print(description, flush=True)
        subprocess.run([str(python), "-I", "-m", *arguments], check=True, cwd=project_root)

    env_file = project_root / ".env"
    if not env_file.exists():
        with env_file.open("xb") as destination:
            destination.write((project_root / ".env.example").read_bytes())
        print("Creado .env vacío: completa tus accesos antes de ejecutar los bots.")

    return python


def main() -> int:
    try:
        python = setup_environment()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"No se completó la instalación: {error}", file=sys.stderr)
        return 1
    print(f"Entorno preparado. Ejecuta los bots con: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
