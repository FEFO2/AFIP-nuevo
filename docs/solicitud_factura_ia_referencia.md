# Solicitud de factura por texto: referencia para el extractor

Estado: propuesta de prueba. Ninguna salida del modelo crea una orden ni emite una factura.

## Objetivo

Convertir un pedido escrito por Fran en un **borrador de extracción**. El modelo identifica lo que dice el texto. La aplicación completa datos conocidos del cliente, calcula importes y valida la orden antes de ofrecerla para revisión humana.

## Datos que puede extraer el modelo

| Campo | Criterio |
| --- | --- |
| `cliente` | Nombre mencionado literalmente. Si no hay cliente o hay varios posibles, `null`. |
| `tipo_factura` | `A` o `B` solo si el texto lo pide expresamente. En otro caso, `null`. |
| `moneda` | `ARS` para pesos argentinos, `USD` para dólares; `null` si no se indica. |
| `tipo_cambio` | Pesos por 1 USD solo si se especifica. Se representa con punto decimal. |
| `correo_entrega` | Dirección de correo explícita, sin inventar una habitual. |
| `conceptos` | Una entrada por concepto, con descripción, monto neto sin IVA y alícuota. |

El formato de extracción es:

```json
{
  "cliente": "Cliente de prueba",
  "tipo_factura": null,
  "moneda": "ARS",
  "tipo_cambio": null,
  "correo_entrega": "fran@example.com",
  "conceptos": [
    {"concepto": "intermediación de pasajes aéreos", "precio_neto": "453.15", "iva": "10,5%"},
    {"concepto": "gestión administrativa", "precio_neto": "100.00", "iva": "21%"}
  ]
}
```

`precio_neto` es un string decimal con punto y dos decimales. `iva` admite `no gravado`, `exento`, `10,5%` y `21%`. El modelo no calcula IVA, subtotal, total ni equivalente en pesos. Si el texto da un importe **con IVA incluido**, no debe copiarlo como neto: deja `precio_neto: null` y señala que hace falta aclararlo o convertirlo con una regla verificada.

Una alícuota expresada como «todo al 10,5 %» se aplica a todos los conceptos del pedido, salvo que alguno tenga una alícuota propia. Un monto sin indicación de neto o total requiere revisión antes de emitir.

## Contexto que aporta la aplicación

La única ficha existente para la prueba es **Cliente de prueba**, con documento ficticio `11111111`. Su recomendación actual es Factura A, responsable inscripto, CUIT y punto de venta 2 (`clientes.js`). Esta recomendación no equivale a una mención de Factura A en el texto; debe aparecer como valor sugerido y modificable después de la extracción.

Cuando exista una base real, la aplicación resolverá el cliente y traerá CUIT, condición frente al IVA, tipo y número de documento, dirección y preferencias de facturación desde esa base. El modelo no debe fabricar ninguno de esos datos. Si el cliente no coincide de forma inequívoca con una ficha, se pide selección manual.

La aplicación completa la fecha de emisión, el período de servicio y el vencimiento con el día actual, como hace el formulario vigente. El correo de entrega se pide si falta. Para USD, el tipo de cambio positivo es obligatorio. Las preferencias precargadas son editables antes de crear la orden.

## De borrador a orden del bot

El borrador del modelo **no es** el JSON final que acepta `/api/ordenes`. Tras la revisión, la aplicación transforma `precio_neto` en `precio` y agrega `id`, `cuit`, `condicion_iva`, `tipo_doc`, `num_doc`, `direccion`, `punto_venta` y las cuatro fechas. Conserva `moneda`, `correo_entrega`, `tipo_factura`, `conceptos` y, si corresponde, `tipo_cambio`. El servidor calcula IVA, desglose, neto, total y equivalente ARS (`bot_facturador/panel.py`).

La orden se crea solo tras una acción explícita de Fran. Antes, el borrador debe mostrar de dónde salió cada dato, qué viene de la ficha del cliente y qué falta o genera dudas. El servidor sigue validando la combinación de tipo de factura y condición fiscal, documentos, fechas, montos, IVA, correo y tipo de cambio.

## Uso de esta referencia con Qwen

El archivo no entra en el contexto de Ollama por sí solo. La futura prueba debe leer esta referencia y enviarla como mensaje de sistema o contexto junto con un esquema JSON. Los casos de `solicitud_factura_ia_casos.md` se ejecutan por separado para medir la calidad; no se deben incluir sus respuestas esperadas en el pedido que se está evaluando.
