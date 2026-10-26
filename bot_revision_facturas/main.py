from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_revision_facturas.workflow import authorize_gmail, run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revisa facturas de Carnival en Gmail y las compara con FAC Prove AR."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compara y genera el reporte sin modificar Gmail ni Arancia.",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Muestra Chromium durante la consulta de Arancia.",
    )
    parser.add_argument(
        "--authorize-gmail",
        action="store_true",
        help="Autoriza Gmail y termina sin procesar correos ni abrir Arancia.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    if args.authorize_gmail:
        return authorize_gmail()
    return run(dry_run=args.dry_run, show_browser=args.show_browser)


if __name__ == "__main__":
    raise SystemExit(main())
