# Referencia breve para interpretar solicitudes de factura

Estado: contrato propuesto para la prueba con Qwen. La salida es un borrador; no crea órdenes ni emite facturas.

## Tarea del modelo

Leer el texto de un correo y devolver una lista `facturas`. Normalmente habrá una, pero un correo puede solicitar varias. Cada factura debe conservar sus propios cliente, datos fiscales, moneda y conceptos. No mezclar conceptos de clientes o facturas distintas.

Extraer únicamente lo indicado por el texto:

| Campo | Regla |
| --- | --- |
| `cliente` | Nombre o código interno claramente indicado. No sustituirlo por una razón social supuesta. |
| `cuit` | CUIT expresado en el correo, normalizado a dígitos. Si falta, `null`. |
| `tipo_factura` | `A` o `B` solo si se pide expresamente; si no, `null`. |
| `condicion_iva` | Condición del cliente si se expresa: `responsable inscripto`, `responsable monotributo`, `sujeto exento` o `consumidor final`. Si falta, `null`. «Monotributista» se normaliza a `responsable monotributo`. |
| `moneda` | `USD` para dólares. `ARS` para pesos o si no se menciona moneda. |
| `conceptos` | Una entrada por concepto con descripción completa, importe informado, precio neto si está indicado y alícuota si está indicada. |

Formato de respuesta:

```json
{
  "facturas": [
    {
      "cliente": "Cliente de prueba",
      "cuit": null,
      "tipo_factura": null,
      "condicion_iva": null,
      "moneda": "ARS",
      "conceptos": [
        {"concepto": "intermediación de pasajes aéreos", "importe_informado": "453.15", "precio_neto": "453.15", "iva": "10,5%"},
        {"concepto": "gestión administrativa", "importe_informado": "100.00", "precio_neto": "100.00", "iva": "21%"}
      ]
    }
  ]
}
```

`importe_informado` conserva cualquier monto citado, normalizado con punto decimal y dos decimales. `precio_neto` solo tiene valor cuando el correo dice expresamente «neto», «sin IVA» o equivalente para ese concepto; «venta» no demuestra que el monto sea neto. Si se da un precio final, `precio_neto` queda en `null`. `iva` admite `no gravado`, `exento`, `10,5%` y `21%`, pero solo si la alícuota o categoría aparece en el correo. No inferir «no gravado» por tratarse de pasajes. Cuando la tasa se indica para toda la factura, se aplica a todos los conceptos sin tasa propia. Los campos faltantes o ambiguos quedan en `null`, salvo la moneda, cuyo valor por defecto es `ARS`.

Conservar en `concepto` el detalle completo útil para facturar, incluidos nombres de pasajeros si figuran. Se pueden corregir tildes y mayúsculas, pero no truncar nombres ni agregar datos. El destinatario del saludo no es necesariamente el cliente: en «Hola. Te pido fc para CLIENTE-DEMO», el cliente mencionado es `CLIENTE-DEMO`.

El modelo no extrae correo de entrega ni tipo de cambio. Tampoco calcula IVA, totales, fechas o equivalentes en pesos. Esos datos quedan fuera de su tarea. La prueba envía **solo esta referencia** y un esquema JSON a Ollama. Los resultados esperados de `solicitud_factura_ia_casos.md` se usan para evaluar la respuesta y no se incluyen en el mismo pedido al modelo.
