"""Ejecuta Gitleaks sobre los cambios preparados sin imprimir los secretos."""

import os
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    executable = shutil.which("gitleaks")
    if executable is None:
        filename = "gitleaks.exe" if os.name == "nt" else "gitleaks"
        local = Path(__file__).resolve().parents[1] / ".tools" / "gitleaks" / filename
        if local.is_file():
            executable = str(local)
    if executable is None:
        print("Falta Gitleaks. Instalarlo según README.md antes de hacer commit.")
        return 1
    return subprocess.run(
        [executable, "git", "--pre-commit", "--redact", "--staged", "--no-banner"],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
