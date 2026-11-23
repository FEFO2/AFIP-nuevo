# Facturador AFIP/ARCA

`invoice_process.py` contiene el único flujo de emisión. Los puntos de entrada
`invoice_process_a.py` e `invoice_process_b.py` eligen el tipo de comprobante.
Importar estos módulos no abre el navegador ni emite facturas.

Consultar [instalación y uso](../README.md#emisión-de-facturas).
La emisión requiere `--fecha`, `--desde` y `--hasta`, todas con formato
`DD/MM/AAAA`; `--vencimiento` es opcional y usa la fecha de emisión por defecto.
Antes de abrir ARCA hay que confirmar la identidad completa del lote. El bot valida
documentos, importes, combinaciones A/B y todos los datos críticos del resumen.
`--solo-revisar` permite comprobar la primera fila sin emitirla. El punto de venta
predeterminado es `2`; allí la fecha mínima es `31/10/2026` para A y `30/10/2026`
para B. Las monedas predeterminadas son A/ARS y B/USD, salvo el lote protegido de
consumidor final descrito debajo, que usa ARS.

`~/Downloads/AFIP_Facturas/facturador_estado.json` registra número, CAE y PDF de
cada fila emitida. No borrar este archivo: evita duplicados y guía la reconciliación
si una ejecución se interrumpe durante la confirmación.
El bot descarga el PDF antes de extraer de él el número y el CAE; el diario también
registra los datos de la fila y la ruta del archivo. Si no puede leer los datos,
conserva el PDF y deja la fila en confirmación pendiente para revisión manual.
Esto no recupera automáticamente comprobantes de ejecuciones anteriores.

Los CSV de entrada son privados y no se versionan. `lista_fac.example.csv`
proporciona los encabezados. La columna `direccion` es opcional; los demás campos
son obligatorios. Se admiten UTF-8 con/sin BOM y Latin-1.

También se admite directamente la exportación de consumidor final con las columnas
`Monto (ARS)`, `Razon Social`, `categoria`, `Column 10` y `DOC`. Para ese formato el
bot fija el concepto `INTERMEDIACIÓN DE SERVICIOS TURÍSTICOS`, IVA `exento`, Factura
B, punto de venta 2, moneda ARS y fecha de emisión `30/10/2026`. Una fecha de
noviembre o cualquier cambio de esas cuatro condiciones bloquea el lote antes de
abrir ARCA y vuelve a comprobarse antes de la confirmación final.

Si un DNI de ese lote es inválido localmente o ARCA lo rechaza de forma explícita,
la fila queda como `omitida` en el diario y el bot continúa con la siguiente. Un fallo
de fecha, moneda, tipo, punto de venta, importe o resumen fiscal sigue deteniendo la
ejecución.
