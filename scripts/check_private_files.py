"""Rechaza archivos ignorados que se hayan añadido con git add --force."""

import subprocess


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--ignored", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    paths = result.stdout.decode("utf-8").rstrip("\0").split("\0") if result.stdout else []
    if paths:
        print("No se pueden versionar archivos privados o generados:")
        for path in paths:
            print(f"- {path}")
        return 1
    print("Sin archivos privados o generados en el índice de Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
