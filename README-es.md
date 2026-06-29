# AFIP Nuevo

Automatizacion en Python para:

- descargar comprobantes desde AFIP,
- descargar reportes HTML desde Arancia/Bookit,
- transformar y comparar ambos conjuntos de datos,
- cargar en Arancia las facturas pendientes.

La automatizacion web usa Playwright.

## Requisitos

- Python 3.11 o compatible
- Dependencias de `requirements.txt`
- Navegador Chromium instalado para Playwright
- Archivo `.env` con las credenciales necesarias

## Instalacion

```bash
pip install -r requirements.txt
playwright install chromium
```

## Variables de entorno

El proyecto espera estas variables en `.env`:

```env
AFIP_URL=
AFIP_USERNAME=
AFIP_PASSWORD=
ARANCIA_URL=
ARANCIA_USERNAME=
ARANCIA_PASSWORD=
```

## Uso

Punto de entrada principal:

```bash
python src/main.py
```

Opciones disponibles:

```bash
python src/main.py --help
```

Ejemplos:

```bash
python src/main.py --mode todo
python src/main.py --mode compras
python src/main.py --mode ventas
python src/main.py --mode todo --skip-downloads
python src/main.py --mode todo --skip-afip-downloads
python src/main.py --mode todo --skip-arancia-downloads
python src/main.py --mode compras --show-browser
```

## Flujo

`src/main.py` ejecuta:

1. Limpieza de la carpeta `downloads/`
2. Descarga de comprobantes desde AFIP
3. Descarga de reportes desde Arancia/Bookit
4. Transformacion de datos
5. Comparacion de facturas
6. Carga de pendientes en Arancia

## Estructura

- `src/main.py`: entrypoint principal
- `src/download_afip_reports.py`: descarga de AFIP
- `src/download_bookit_reports.py`: descarga de Arancia/Bookit
- `src/afip_data_transformation.py`: transformacion de archivos AFIP
- `src/bookit_data_transformation.py`: transformacion de HTML de Arancia/Bookit
- `src/data_comparison.py`: comparacion entre AFIP y sistema
- `src/workflows.py`: construccion de datasets pendientes
- `src/data_upload.py`: carga de compras y ventas en Arancia

## Notas

- Si usas `--skip-downloads`, el sistema reutiliza todos los archivos ya existentes en `downloads/`.
- Si usas `--skip-afip-downloads`, reutiliza solo los archivos de AFIP y vuelve a descargar Arancia/Bookit.
- Si usas `--skip-arancia-downloads`, reutiliza solo los archivos de Arancia/Bookit y vuelve a descargar AFIP.
- Si no hay facturas pendientes, el flujo termina sin cargar nada.
- Los logs de consola muestran el avance por pasos.
