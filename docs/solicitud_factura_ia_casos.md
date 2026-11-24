# Casos de prueba para solicitudes de factura

Los ejemplos son ficticios. Se evalúa la **extracción**, antes de consultar la base de clientes o crear una orden. En todos los casos, el resultado debe ser un objeto con la lista `facturas`.

## 1. Dos conceptos, una factura

**Entrada:** «Factura a Cliente de prueba: intermediación de pasajes aéreos por 453,15 sin IVA al 10,5 % y gestión administrativa por 100 sin IVA al 21 %. En pesos.»

**Esperado:** Una factura con `cliente="Cliente de prueba"`, `cuit=null`, `tipo_factura=null`, `condicion_iva=null`, `moneda="ARS"`. Dos conceptos: `importe_informado` y `precio_neto` de `453.15` con `10,5%`, y `100.00` con `21%`. La preferencia A y los datos fiscales se aplican después desde la ficha.

## 2. Nombre de código y alícuota común

**Entrada:** «Para el cliente código SOL, asesoría 200 netos y gestión 50 netos. Todo al 10,5 %.»

**Esperado:** Una factura con `cliente="SOL"`, `moneda="ARS"`, `tipo_factura=null` y dos conceptos `200.00` y `50.00`, ambos con `iva="10,5%"`. La aplicación debe resolver SOL en la base; el modelo no inventa CUIT ni razón social.

## 3. Tipo y condición explícitos

**Entrada:** «Factura B para Ana, consumidora final: asesoría 250,50 netos al 21 % en USD.»

**Esperado:** Una factura con `cliente="Ana"`, `tipo_factura="B"`, `condicion_iva="consumidor final"`, `moneda="USD"` y un concepto de `250.50` con `21%`. La aplicación obtiene el tipo de cambio del sistema. Ana no existe en la base de prueba, por lo que requiere identificación antes de crear la orden.

## 4. Condición monotributista y CUIT

**Entrada:** «Facturá a Pérez, monotributista, CUIT 20-12345678-3, un servicio por 90 netos exento.»

**Esperado:** Una factura con `cliente="Pérez"`, `cuit="20123456783"`, `condicion_iva="responsable monotributo"`, `tipo_factura=null`, `moneda="ARS"` y un concepto `90.00` con `iva="exento"`. El CUIT es dato de prueba; la aplicación lo comprueba contra la ficha antes de usarlo.

## 5. Dos facturas en un correo

**Entrada:** «Hacé dos facturas: para Cliente de prueba, pasajes 300 netos al 10,5 %; para Ana, asesoría 100 netos al 21 %, Factura B. Todo en pesos.»

**Esperado:** Dos elementos en `facturas`, en el orden del correo. El primero tiene cliente `Cliente de prueba`, un concepto `300.00` al `10,5%` y `tipo_factura=null`. El segundo tiene cliente `Ana`, un concepto `100.00` al `21%` y `tipo_factura="B"`. Ambos tienen `moneda="ARS"`. No se mezclan los conceptos.

## 6. Importe final con IVA

**Entrada:** «Cliente de prueba, hotel por 121 pesos finales con IVA 21 %.»

**Esperado:** Una factura con concepto «hotel», `iva="21%"`, `importe_informado="121.00"`, `precio_neto=null` y `moneda="ARS"`. El monto requiere conversión verificada o revisión.

## 7. Datos insuficientes

**Entrada:** «Facturá los pasajes de ayer.»

**Esperado:** Una factura con `cliente=null`, `cuit=null`, `tipo_factura=null`, `condicion_iva=null`, `moneda="ARS"`. Puede aparecer el concepto «pasajes», con `precio_neto=null` e `iva=null`. No se crea orden.

## 8. Venta sin desglose fiscal

**Entrada:** «Hola. Te pido fc para CLIENTE-DEMO. Detalle: Emisión de pasajes para Pasajero Uno y Pasajera Dos. Venta $ 123.456. Gracias.»

**Esperado:** Una factura con `cliente="CLIENTE-DEMO"`, `cuit=null`, `tipo_factura=null`, `condicion_iva=null`, `moneda="ARS"`. El concepto conserva las dos referencias ficticias. `importe_informado="123456.00"`, `precio_neto=null` e `iva=null`. «Venta» no indica monto neto ni categoría de IVA. La ficha del cliente se consulta después de extraer el correo.

## Criterio de evaluación

Comparar cantidad de facturas, asignación de conceptos, cliente o código, CUIT, tipo de factura, condición, moneda, importe informado, neto e IVA. Registrar datos inventados, omisiones, nombres truncados y mezclas entre facturas. Un JSON válido con datos incorrectos no aprueba. El tipo de cambio y el correo de entrega no forman parte de la respuesta del modelo.
