# Revision de facturas Carnival

Procesa los correos no leidos de `facturacion@carnival-tours.com` con asunto
`Factura Arancia Services SRL`, compara sus tickets con **Facturacion > FAC
Prove AR** y genera `reporte_revision.csv`.

## Primera instalacion

Desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\bot_revision_facturas\requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Crear primero `.venv` siguiendo el [README principal](../README.md).
Obtener el archivo OAuth de la aplicación de Google y guardarlo localmente como
`bot_revision_facturas/client_secret.json`. No se incluye en Git. En la primera
ejecución se abre Google para autorizar Gmail; el acceso queda guardado en
`token_automation.json`. La cuenta autorizada debe ser la cuenta operativa
configurada en `workflow.py`. Los tokens deben permanecer en el equipo local.

Para autorizar sin procesar correos ni abrir Arancia:

```powershell
.\.venv\Scripts\python.exe .\bot_revision_facturas\main.py --authorize-gmail
```

## Prueba sin cambios

```powershell
.\.venv\Scripts\python.exe .\bot_revision_facturas\main.py --dry-run --show-browser
```

`--dry-run` usa `token.json` con permisos de solo lectura (pedirá autorización si falta): no marca correos,
no crea borradores y no actualiza Arancia.

## Ejecucion real

```powershell
.\.venv\Scripts\python.exe .\bot_revision_facturas\main.py
```

Reglas aplicadas:

- diferencia exacta `0,00`, o entre `4,99` y `5,01`: valida;
- los tickets que coinciden se actualizan aunque otros tickets de la factura fallen;
- factura sin tickets: se marca leida y se archiva;
- nota de credito: queda sin leer en Recibidos;
- factura con tickets inexistentes o ya asignados, sin diferencias de importes:
  queda incompleta y el correo permanece sin leer en Recibidos, sin borrador;
- diferencia rechazada: se crea un borrador para Enzo como respuesta en el hilo
  original, con solo las diferencias, y el correo queda leido en Recibidos.

La programacion en el Programador de tareas de Windows se configurara despues
de validar una ejecucion real.
