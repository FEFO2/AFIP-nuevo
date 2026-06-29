README - bot_facturador

Este directorio tiene dos scripts de automatizacion con Playwright para emitir comprobantes en AFIP/ARCA:

- `invoice_process_a.py`: genera Facturas A.
- `invoice_process_b.py`: genera Facturas B.

Los dos scripts hacen casi el mismo recorrido en la web de AFIP. La diferencia principal es el tipo de comprobante que eligen y algunos datos del receptor.


1. Flujo general de ambos scripts

Cuando se ejecuta cualquiera de los dos archivos:

1. Lee un CSV con las facturas a emitir.
2. Normaliza los nombres de columnas y algunos textos para evitar problemas con mayusculas, tildes o espacios.
3. Crea la carpeta de descargas `~/Downloads/AFIP_Facturas` si no existe.
4. Abre Chromium con Playwright en modo visible (`headless=False`).
5. Entra a `https://auth.afip.gob.ar/contribuyente_/login.xhtml`.
6. Hace login con credenciales que hoy estan escritas directamente en el codigo.
7. Abre "Comprobantes en linea".
8. Selecciona la empresa `ARANCIA SERVICES S.R.L.`.
9. Recorre cada fila del CSV y genera una factura por fila.
10. Descarga el PDF al final de cada comprobante.
11. Vuelve al menu principal para seguir con la siguiente factura.


2. Que pasa dentro del loop de facturacion

Por cada factura del CSV, el script:

1. Hace click en `Generar Comprobantes`.
2. Selecciona el punto de venta `10`.
3. Elige el tipo de comprobante:
   - En `invoice_process_a.py` usa `10` (Factura A).
   - En `invoice_process_b.py` usa `19` (Factura B).
4. Completa la fecha con `FECHA_FACTURACION`.
5. Marca el concepto `2`, que corresponde a servicios.
6. Hace click en `Moneda Extranjera`.
   Nota: el comentario en el codigo dice que esto deberia hacerse solo si la factura es en USD.
7. Completa el periodo `Desde` y `Hasta` con la misma fecha.
8. Convierte valores del CSV a los codigos que espera AFIP:
   - `condicion_iva`
   - `tipo_doc`
   - `iva`
9. En la pantalla del receptor:
   - selecciona la condicion frente al IVA,
   - completa CUIT o DNI,
   - dispara la busqueda con `Tab`,
   - si el documento es DNI y AFIP no completa domicilio, usa la direccion del CSV,
   - marca `Contado`.
10. En la pantalla de detalle:
   - carga la descripcion en `concepto`,
   - carga el importe en `precio`,
   - selecciona el tipo de IVA.
11. Confirma los datos.
12. Hace click en `Imprimir...` y guarda el archivo descargado.
13. Hace click en `Menu Principal` para continuar con la siguiente fila.


3. Diferencias entre invoice_process_a y invoice_process_b

`invoice_process_a.py`

- Lee el archivo `lista_fac_a.csv`.
- Permite estas condiciones de IVA del receptor:
  - `responsable inscripto` -> `1`
  - `consumidor final` -> `5`
  - `sujeto exento` -> `4`
- En la pantalla del receptor no selecciona explicitamente `#idtipodocreceptor`.
- Usa `#universocomprobante = 10`, o sea Factura A.

`invoice_process_b.py`

- Lee el archivo `lista_fac.csv`.
- Permite estas condiciones de IVA del receptor:
  - `consumidor final` -> `5`
  - `sujeto exento` -> `4`
- Si el CSV trae otra condicion de IVA, el script falla con `ValueError`.
- Si selecciona explicitamente `#idtipodocreceptor` antes de cargar el numero de documento.
- Usa `#universocomprobante = 19`, o sea Factura B.


4. Estructura esperada del CSV

Los scripts esperan columnas como estas:

- `condicion_iva`
- `tipo_doc`
- `num_doc`
- `concepto`
- `precio`
- `iva`
- `direccion` (tambien funciona si el encabezado original viene con tilde)

Detalles importantes:

- Los encabezados se normalizan, asi que un nombre como `direccion` con tilde termina interpretandose como `direccion`.
- `tipo_doc` soporta:
  - `CUIT` -> `80`
  - `DNI` -> `96`
- `iva` soporta:
  - `no gravado`
  - `no grav`
  - `exento`
  - `10,5%`
  - `10.5%`
  - `21%`


5. Funciones importantes

`normalizar_texto(texto)`

- Pasa el texto a minusculas.
- Quita espacios al inicio y al final.
- Elimina tildes y variaciones Unicode.
- Se usa para comparar valores del CSV sin depender de como fueron escritos.

`cargar_facturas()`

- Intenta leer el CSV con `utf-8-sig`.
- Si falla, intenta con `latin-1`.
- Devuelve una lista de diccionarios, una por cada fila.

`obtener_codigo(valor, opciones, campo)`

- Traduce el texto del CSV al codigo que necesita AFIP.
- Si aparece un valor no contemplado, corta la ejecucion con un error claro.

`run(playwright)`

- Contiene toda la automatizacion del navegador y el loop principal de facturacion.


6. Observaciones importantes del estado actual

- Las credenciales de acceso estan hardcodeadas en el codigo. Eso es practico para pruebas, pero inseguro para produccion.
- `FECHA_FACTURACION` esta fija en ambos scripts. Si cambia la fecha, hay que editar el archivo.
- En ambos scripts se hace click en `Moneda Extranjera`, aunque el comentario dice que solo deberia hacerse si la operacion es en USD.
- `invoice_process_a.py` espera `lista_fac_a.csv`. Si ese archivo no existe en esta carpeta, el script va a fallar al iniciar.
- Los mensajes de error de `cargar_facturas()` mencionan `lista_fac.csv`, incluso en el script A. El comportamiento real depende de `CSV_PATH`, no del texto del mensaje.
- La vuelta al `Menu Principal` parece ser la forma actual de reiniciar el flujo para la siguiente factura.


7. Resumen corto

- `invoice_process_a.py` automatiza Factura A.
- `invoice_process_b.py` automatiza Factura B.
- Ambos leen un CSV, entran a AFIP, cargan datos del receptor, completan el detalle, confirman y descargan el comprobante.
- La mayor diferencia esta en el tipo de comprobante y en como manejan los datos del receptor.
