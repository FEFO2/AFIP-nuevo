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
python -m bot_carga
```

Compatibilidad con el entrypoint anterior:

```bash
python src/main.py
```

Opciones disponibles:

```bash
python -m bot_carga --help
```

Ejemplos:

```bash
python -m bot_carga --mode todo
python -m bot_carga --mode compras
python -m bot_carga --mode ventas
python -m bot_carga --mode todo --skip-downloads
python -m bot_carga --mode todo --skip-afip-downloads
python -m bot_carga --mode todo --skip-arancia-downloads
python -m bot_carga --mode compras --show-browser
```

## Flujo

`bot_carga/main.py` ejecuta:

1. Limpieza de la carpeta `downloads/`
2. Descarga de comprobantes desde AFIP
3. Descarga de reportes desde Arancia/Bookit
4. Transformacion de datos
5. Comparacion de facturas
6. Carga de pendientes en Arancia

## Estructura

- `bot_carga/main.py`: entrypoint principal del bot de carga
- `bot_carga/download_afip_reports.py`: descarga de AFIP
- `bot_carga/download_bookit_reports.py`: descarga de Arancia/Bookit
- `bot_carga/afip_data_transformation.py`: transformacion de archivos AFIP
- `bot_carga/bookit_data_transformation.py`: transformacion de HTML de Arancia/Bookit
- `bot_carga/data_comparison.py`: comparacion entre AFIP y sistema
- `bot_carga/workflows.py`: construccion de datasets pendientes
- `bot_carga/data_upload.py`: carga de compras y ventas en Arancia
- `bot_carga/report_generator.py`: generacion del informe HTML
- `bot_carga/utils.py`: utilidades compartidas del flujo
- `src/*.py`: wrappers de compatibilidad hacia `bot_carga`

## Notas

- Si usas `--skip-downloads`, el sistema reutiliza todos los archivos ya existentes en `downloads/`.
- Si usas `--skip-afip-downloads`, reutiliza solo los archivos de AFIP y vuelve a descargar Arancia/Bookit.
- Si usas `--skip-arancia-downloads`, reutiliza solo los archivos de Arancia/Bookit y vuelve a descargar AFIP.
- Si no hay facturas pendientes, el flujo termina sin cargar nada.
- Los logs de consola muestran el avance por pasos.
