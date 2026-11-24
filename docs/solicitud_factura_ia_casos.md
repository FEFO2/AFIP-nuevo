# Casos de prueba para solicitud de factura por texto

Estos ejemplos son ficticios. El resultado esperado describe solo la **extracción** del modelo. La ficha del cliente, los cálculos y la validación se aplican después, como indica `solicitud_factura_ia_referencia.md`.

## 1. Dos conceptos y dos alícuotas

**Entrada:** «Factura a Cliente de prueba: intermediación de pasajes aéreos por 453,15 sin IVA al 10,5 % y gestión administrativa por 100 sin IVA al 21 %. En pesos. Enviarla a fran@example.com.»

**Esperado:** `cliente="Cliente de prueba"`, `tipo_factura=null`, `moneda="ARS"`, `correo_entrega="fran@example.com"`. Dos conceptos: `453.15` con `10,5%` y `100.00` con `21%`. El tipo A recomendado para el cliente se agrega después, identificado como sugerencia.

## 2. Alícuota común a todos los conceptos

**Entrada:** «Para Cliente de prueba, facturar asesoría 200 netos y gestión 50 netos. Todo al 10,5 %. Enviar a fran@example.com.»

**Esperado:** Dos conceptos, ambos con `iva="10,5%"` y netos `200.00` y `50.00`. `tipo_factura=null`. `moneda=null`, porque el texto no la indica; la aplicación deberá pedirla o sugerirla para revisión.

## 3. Factura B en dólares

**Entrada:** «Factura B a Ana: asesoría 250,50 netos al 21 % en USD. Tipo de cambio 1200,50 pesos por dólar. Enviar a ana@example.com.»

**Esperado:** `cliente="Ana"`, `tipo_factura="B"`, `moneda="USD"`, `tipo_cambio="1200.50"`, `correo_entrega="ana@example.com"`, un concepto de `250.50` con `21%`. Ana no existe en la base de prueba: la aplicación no puede crear la orden hasta identificarla.

## 4. USD sin tipo de cambio

**Entrada:** «Facturar a Cliente de prueba un servicio de coordinación por 90 netos, exento, en dólares. Enviar a fran@example.com.»

**Esperado:** `moneda="USD"`, `tipo_cambio=null`, un concepto `90.00` con `iva="exento"`. Se debe solicitar el tipo de cambio antes de crear la orden.

## 5. Importe con IVA incluido

**Entrada:** «Cliente de prueba, hotel por 121 pesos finales con IVA 21 %. Enviar a fran@example.com.»

**Esperado:** Concepto «hotel», `iva="21%"`, `precio_neto=null`. Se debe aclarar o convertir el importe con una regla verificada antes de crear la orden. El valor `121.00` no se puede presentar como neto.

## 6. Datos insuficientes

**Entrada:** «Facturá los pasajes de ayer.»

**Esperado:** `cliente=null`, `tipo_factura=null`, `moneda=null`, `correo_entrega=null`. Puede identificarse el concepto «pasajes», pero su `precio_neto` y `iva` quedan en `null`. No se crea orden.

## Criterio de evaluación

Para cada caso, comparar cliente, tipo, moneda, cambio, correo, número de conceptos, descripción, neto e IVA con el esperado. Registrar campos inventados, campos omitidos y conversiones incorrectas. Una respuesta JSON válida con datos erróneos **no aprueba** el caso. Probar también que la ausencia de Ollama o un tiempo de espera no cree ninguna orden.
