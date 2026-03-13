from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_ORDER = [
    "download_afip_reports.py",
    "download_bookit_reports.py",
    "buy_upload.py",
    "sales_upload.py",
]


def run_script(script_path: Path, project_root: Path) -> int:
    print(f"\n=== Running {script_path.name} ===")
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        check=False,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the AFIP/Bookit download and upload scripts in sequence."
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep running the remaining scripts even if one fails.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    src_dir = project_root / "src"

    missing_scripts = [
        script_name for script_name in SCRIPT_ORDER if not (src_dir / script_name).exists()
    ]
    if missing_scripts:
        print("The following scripts were not found:")
        for script_name in missing_scripts:
            print(f" - {src_dir / script_name}")
        return 1

    failures: list[tuple[str, int]] = []

    for script_name in SCRIPT_ORDER:
        script_path = src_dir / script_name
        return_code = run_script(script_path, project_root)

        if return_code == 0:
            print(f"Completed {script_name}")
            continue

        print(f"Failed {script_name} with exit code {return_code}")
        failures.append((script_name, return_code))

        if not args.continue_on_error:
            break

    if failures:
        print("\nRun finished with errors:")
        for script_name, return_code in failures:
            print(f" - {script_name}: exit code {return_code}")
        return 1

    print("\nAll scripts completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
