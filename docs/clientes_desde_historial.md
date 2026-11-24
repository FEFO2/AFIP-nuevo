# Base de clientes a partir del historial de facturación

## Material local ya disponible

En `feature_interfaz` están `QWEN.md`, `src/consultar_cliente.py` y la base local `.local/clientes_recurrentes.json`. El JSON reúne **56 fichas** con razón social, documento, alias, cantidad de facturas y tipos de comprobante e IVA observados. Una ficha tiene `tipo_factura_para_emitir` explícito y dos tienen `condicion_iva_para_emitir`. `QWEN.md` indica que esas instrucciones actuales prevalecen sobre los antecedentes y que una coincidencia ambigua se resuelve antes de facturar.

El JSON real permanece **fuera de Git** porque el repositorio remoto es público. El buscador y la guía pueden versionarse sin datos fiscales. Ollama no lee estos archivos automáticamente: la aplicación debe consultar la ficha y pasarle solo el contexto necesario para cada solicitud.

## Ficha propuesta

| Dato | Uso |
| --- | --- |
| Razón social | Identificación para facturar. |
| CUIT o documento | Identificación fiscal; único cuando exista. |
| Nombres y códigos internos | Alias para resolver los nombres empleados en correos. Un alias ambiguo requiere elección manual. |
| Condición frente al IVA | `responsable inscripto`, `responsable monotributo`, `sujeto exento` o `consumidor final`. |
| Tipo de factura preferido | A o B como propuesta editable. |
| Tipo y número de documento, dirección, punto de venta | Datos que requiere el flujo vigente según el caso. |
| Fuente y última confirmación | Referencia al comprobante o correo que respalda la ficha y cuándo se verificó. |

La tabla SQLite `clientes` del centro de control solo guarda CUIT y razón social. La ficha propuesta puede partir del JSON local existente y ampliar lo necesario; los alias necesitan una estructura que detecte duplicados y coincidencias ambiguas.

## Construcción a partir del correo

1. Localizar correos y comprobantes de facturación del historial, sin modificar mensajes.
2. Extraer candidatos de cliente, CUIT, condición fiscal, tipo de factura y alias. Conservar la referencia al origen y la fecha del comprobante.
3. Agrupar por CUIT o documento. Un nombre parecido no basta para unir fichas.
4. Estimar la preferencia de factura a partir de las operaciones observadas, mostrando cuántas respaldan cada tipo y cuándo fue la última. No tratar la frecuencia como una regla fiscal.
5. Revisar manualmente conflictos, datos desactualizados y alias compartidos antes de activar una ficha para generar órdenes.

Las 56 fichas ya son un punto de partida parcial. Para ampliar o confirmar datos desde el correo habrá que identificar los mensajes pertinentes y revisar los resultados. No se incluyen correos reales ni datos fiscales reales en estos documentos o en los casos de Qwen.

## Aplicación de la ficha a una solicitud

La aplicación busca el cliente por nombre, código interno o CUIT. Si el correo no trae CUIT, usa el de la ficha identificada. La condición frente al IVA y el tipo de factura preferido completan campos ausentes. Los valores explícitos del correo conservan su origen; un conflicto con la ficha requiere revisión. Ninguna coincidencia ambigua pasa automáticamente a una orden.

La ficha ficticia actual recomienda Factura A, responsable inscripto, CUIT y punto de venta 2. Esta recomendación se aplica después de la extracción y no debe aparecer como si el correo la hubiera pedido.

Para USD, la aplicación obtiene el tipo de cambio del sistema y muestra la cotización utilizada. El valor del correo no se usa. Si no existe cotización del sistema, la orden queda pendiente. La aplicación completa fechas y demás campos requeridos, calcula importes y muestra el borrador a Fran antes de crear una orden.

El JSON extraído por Qwen no es el de `/api/ordenes`. El servidor actual (`bot_facturador/panel.py`) todavía exige `correo_entrega` y recibe `tipo_cambio` en una orden USD; la interfaz actual también los solicita manualmente. Para aplicar la nueva política hay que resolver la entrega sin correo, definir la fuente de cambio y adaptar la integración. La validación actual admite A con `responsable inscripto` o `responsable monotributo`, y B con `consumidor final` o `sujeto exento`. Los conflictos se revisan antes de enviar la orden.
