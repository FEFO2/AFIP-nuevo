# AFIP Nuevo

Automatizaciones de AFIP/ARCA, Arancia/Bookit, Newsan y revisión de facturas recibidas por Gmail.

## Instalación en otro portátil

Requiere Git, Python 3.11 de 64 bits e Internet para la primera instalación.
Desde PowerShell:

```powershell
git clone --branch codex/limpieza-seguridad https://github.com/FEFO2/AFIP-nuevo.git
cd AFIP-nuevo
py -3.11 setup_env.py
.\.venv\Scripts\python.exe -m pre_commit install --install-hooks
```

El script crea `.venv`, instala las versiones exactas de `requirements-lock.txt`
(incluidas las dependencias indirectas y las herramientas de desarrollo), comprueba
su compatibilidad e instala Chromium para la versión fijada de Playwright.
Si falta `.env`, crea una copia de `.env.example`. Conserva un `.env` existente.
Se puede volver a ejecutar para completar una instalación interrumpida o aplicar
las versiones fijadas a un `.venv` válido de Python 3.11. No modifica el antiguo `env/`.

En macOS/Linux, ejecutar `python3.11 setup_env.py` y usar `.venv/bin/python` en lugar
de `.\.venv\Scripts\python.exe`. El entorno de referencia se ha probado en Windows
x64 con Python 3.11.9; el script admite las versiones 3.11.x.

`requirements.txt` y `requirements-dev.txt` describen las dependencias del proyecto;
`requirements-lock.txt` fija 77 versiones basadas en el entorno probado, con la
corrección de seguridad de `certifi` y una versión fija de `pip`. Las instalaciones
nuevas y GitHub Actions usan este archivo. La versión de mantenimiento de Python
procede de la instalación local de Python 3.11.

Para que el control de secretos funcione antes de cada commit, instalar también
[Gitleaks 8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)
y añadirlo al `PATH`. Alternativamente, guardar el ejecutable oficial en
`.tools/gitleaks/gitleaks.exe` (Windows) o `.tools/gitleaks/gitleaks` (macOS/Linux).
Comprobar su SHA-256 contra el archivo de sumas publicado en esa misma versión.
El portátil original ya tiene el ejecutable verificado en esa carpeta local.
Antes de hacer commits desde una terminal, activar el entorno con
`.\.venv\Scripts\Activate.ps1` (Windows) o `source .venv/bin/activate`
(macOS/Linux), para que los controles encuentren Ruff.

Completar `.env` con los accesos correspondientes. Las variables disponibles están
en `.env.example`; cada bot solo exige las que utiliza. `PAG_URL` sigue aceptándose
como nombre antiguo de `PGA_URL`. Las variables del sistema tienen prioridad.

Las claves, tokens, documentos de entrada y resultados **no viajan con Git**.
Transferir los documentos necesarios por un medio privado y configurar los accesos
localmente. El entorno `env/` del portátil original se conserva, pero cada equipo
debe crear su propio entorno. Antes de volver a utilizar los accesos antiguos,
seguir [SECURITY.md](SECURITY.md): había credenciales en el historial del repositorio.

## Bots

Todos los ejemplos se ejecutan desde la raíz con el Python del entorno virtual.

| Carpeta | Función | Inicio |
| --- | --- | --- |
| `bot_carga/` | Descargar, comparar y cargar comprobantes | `python bot_carga/main.py --help` |
| `bot_facturador/` | Emitir facturas A/B | `python bot_facturador/invoice_process_a.py --help` |
| `bot_newsan/` | Extraer PDF y cargar en Oracle | `python bot_newsan/extractor_factura.py --help` |
| `bot_revision_facturas/` | Revisar facturas recibidas por Gmail | `python bot_revision_facturas/main.py --help` |
| `afip_common/` | Configuración compartida | No se ejecuta directamente |
| `legacy/` | Archivo de los accesos antiguos de `src/` | No se usa para iniciar los bots actuales |

Cada bot se inicia con un script dentro de su propia carpeta. En el caso de carga,
también se puede entrar en `bot_carga/` y ejecutar `python main.py`.
`python -m bot_carga` sigue disponible. Los diez archivos de la antigua carpeta
`src/` se han movido a `legacy/src/`; actualizar cualquier tarea programada que
todavía use una ruta `src/...`. Más detalles en [legacy/README.md](legacy/README.md).

### Carga en Arancia

```powershell
python bot_carga/main.py --mode todo
python bot_carga/main.py --mode compras --show-browser
python bot_carga/main.py --mode ventas --period previous
python bot_carga/main.py --mode todo --skip-downloads
```

El flujo descarga, compara y **carga las facturas pendientes**. Los archivos de trabajo
se guardan en `downloads/`. También admite `--skip-afip-downloads`,
`--skip-arancia-downloads`, `--slow-network` y `--manual-on-error`.

### Emisión de facturas

Preparar `bot_facturador/lista_fac_a.csv` (A) o `bot_facturador/lista_fac.csv` (B),
con las columnas de `bot_facturador/lista_fac.example.csv`.

```powershell
python -m bot_facturador.invoice_process_a --fecha 26/10/2026 --moneda ARS
python -m bot_facturador.invoice_process_b --fecha 26/10/2026 --moneda USD
```

Estos comandos **emiten comprobantes reales**. Elegir la fecha correcta en cada
ejecución; ya no hay una fecha fija dentro del código. Se conservan los valores
predeterminados del flujo anterior: punto de venta `10`, A en ARS y B en USD.
Se pueden cambiar con `--punto-venta`, `--moneda` y `--csv`.
Los PDF se guardan en `~/Downloads/AFIP_Facturas`.
También funcionan las rutas `python bot_facturador/invoice_process_a.py` y `_b.py`
con los mismos argumentos. Las copias obsoletas de `bot_facturador/legacy/`
fueron retiradas durante la limpieza de seguridad.

### Newsan

Colocar los PDF en `bot_newsan/facturas_para_carga/` (crear la carpeta si falta).

```powershell
python -m bot_newsan.extractor_factura
python -m bot_newsan.cargador_facturas --help
```

La extracción genera el CSV local en `bot_newsan/salida_csv/`. La carga conserva
la revisión manual y la compatibilidad con las facturas de crédito MiPyME.
`pga_bot_code.py` reutiliza el mismo acceso a Oracle para la consola de pruebas.

### Revisión por Gmail

Consultar [las instrucciones del bot](bot_revision_facturas/README.md).
Es necesario aportar `client_secret.json` localmente y autorizar Gmail en el equipo
nuevo. No copiar tokens al repositorio. Las dependencias opcionales de este bot
están incluidas en `requirements-dev.txt`; para instalar solo el bot principal
se puede usar `requirements.txt`.

## Comprobaciones

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bot_revision_facturas/tests -v
python -m ruff check .
python -m ruff format --check .
python scripts/check_private_files.py
python -m pre_commit run --all-files
python -m pip_audit -r requirements-lock.txt
```

Las pruebas usan datos ficticios y navegadores simulados. No emiten facturas ni
modifican Gmail o Arancia. El control previo al commit detecta archivos privados,
revisa Python y busca secretos con Gitleaks. GitHub ejecuta controles equivalentes
en cada push/PR, sin necesitar claves de los portales.
