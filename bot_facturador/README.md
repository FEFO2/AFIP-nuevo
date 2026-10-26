# Facturador AFIP/ARCA

`invoice_process.py` contiene el único flujo de emisión. Los puntos de entrada
`invoice_process_a.py` e `invoice_process_b.py` eligen el tipo de comprobante.
Importar estos módulos no abre el navegador ni emite facturas.

Consultar [instalación y uso](../README.md#emisión-de-facturas).
La fecha se indica con `--fecha DD/MM/AAAA`. Se conservan el punto de venta 10
y las monedas predeterminadas A/ARS y B/USD.

Los CSV de entrada son privados y no se versionan. `lista_fac.example.csv`
proporciona los encabezados. La columna `direccion` es opcional; los demás campos
son obligatorios. Se admiten UTF-8 con/sin BOM y Latin-1.
