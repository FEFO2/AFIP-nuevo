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
python -m bot_carga
```

Backward-compatible entrypoint:

```bash
python src/main.py
```

Available options:

```bash
python -m bot_carga --help
```

Examples:

```bash
python -m bot_carga --mode todo
python -m bot_carga --mode compras
python -m bot_carga --mode ventas
python -m bot_carga --mode todo --skip-downloads
python -m bot_carga --mode todo --skip-afip-downloads
python -m bot_carga --mode todo --skip-arancia-downloads
python -m bot_carga --mode compras --show-browser
```

## Workflow

`bot_carga/main.py` runs:

1. Cleanup of the `downloads/` folder
2. AFIP invoice download
3. Arancia/Bookit report download
4. Data transformation
5. Invoice comparison
6. Upload of pending invoices to Arancia

## Structure

- `bot_carga/main.py`: main invoice-loading bot entrypoint
- `bot_carga/download_afip_reports.py`: AFIP download
- `bot_carga/download_bookit_reports.py`: Arancia/Bookit download
- `bot_carga/afip_data_transformation.py`: AFIP file transformation
- `bot_carga/bookit_data_transformation.py`: Arancia/Bookit HTML transformation
- `bot_carga/data_comparison.py`: AFIP vs system comparison
- `bot_carga/workflows.py`: pending dataset builders
- `bot_carga/data_upload.py`: purchase and sales upload to Arancia
- `bot_carga/report_generator.py`: HTML report generation
- `bot_carga/utils.py`: shared workflow utilities
- `src/*.py`: compatibility wrappers that forward to `bot_carga`

## Notes

- If you use `--skip-downloads`, the workflow reuses all existing files in `downloads/`.
- If you use `--skip-afip-downloads`, it reuses only the AFIP files and downloads Arancia/Bookit again.
- If you use `--skip-arancia-downloads`, it reuses only the Arancia/Bookit files and downloads AFIP again.
- If there are no pending invoices, the upload stage exits without submitting anything.
- Console logs show the workflow progress step by step.
