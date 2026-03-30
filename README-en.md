# AFIP Nuevo

Python automation for:

- downloading invoices from AFIP,
- downloading HTML reports from Arancia/Bookit,
- transforming and comparing both datasets,
- uploading pending invoices into Arancia.

Browser automation is implemented with Playwright.

## Requirements

- Python 3.11 or compatible
- Dependencies from `requirements.txt`
- Playwright Chromium browser installed
- A `.env` file with the required credentials

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Environment Variables

The project expects these variables in `.env`:

```env
AFIP_URL=
AFIP_USERNAME=
AFIP_PASSWORD=
ARANCIA_URL=
ARANCIA_USERNAME=
ARANCIA_PASSWORD=
```

## Usage

Main entrypoint:

```bash
python src/main.py
```

Available options:

```bash
python src/main.py --help
```

Examples:

```bash
python src/main.py --mode todo
python src/main.py --mode compras
python src/main.py --mode ventas
python src/main.py --mode todo --skip-downloads
python src/main.py --mode compras --show-browser
```

## Workflow

`src/main.py` runs:

1. Cleanup of the `downloads/` folder
2. AFIP invoice download
3. Arancia/Bookit report download
4. Data transformation
5. Invoice comparison
6. Upload of pending invoices to Arancia

## Structure

- `src/main.py`: main entrypoint
- `src/download_afip_reports.py`: AFIP download
- `src/download_bookit_reports.py`: Arancia/Bookit download
- `src/afip_data_transformation.py`: AFIP file transformation
- `src/bookit_data_transformation.py`: Arancia/Bookit HTML transformation
- `src/data_comparison.py`: AFIP vs system comparison
- `src/workflows.py`: pending dataset builders
- `src/data_upload.py`: invoice upload to Arancia

## Notes

- If you use `--skip-downloads`, the workflow reuses existing files in `downloads/`.
- If there are no pending invoices, the upload stage exits without submitting anything.
- Console logs show the workflow progress step by step.
