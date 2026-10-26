"""Configuración local: nunca incluir valores de credenciales en los errores."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment() -> None:
    # Una ruta fija evita cargar accidentalmente el .env de otro proyecto.
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def get_required_env(name: str, legacy_name: str | None = None) -> str:
    value = os.getenv(name) or (os.getenv(legacy_name) if legacy_name else None)
    if value is None or not value.strip():
        raise ValueError(f"Falta la variable de entorno {name}.")
    return value


@dataclass(frozen=True)
class AranciaSettings:
    url: str
    username: str = field(repr=False)
    password: str = field(repr=False)


def load_arancia_settings() -> AranciaSettings:
    load_environment()
    return AranciaSettings(
        *(
            get_required_env(name)
            for name in ("ARANCIA_URL", "ARANCIA_USERNAME", "ARANCIA_PASSWORD")
        )
    )
