# Consulta de clientes de facturación

Para identificar a un cliente, consultá la base local `.local/clientes_recurrentes.json` o ejecutá desde la raíz `python src/consultar_cliente.py "nombre o código"`. La consulta admite alias, parte de la razón social o documento completo con o sin guiones. La base real permanece fuera de Git.

Cada ficha resume los comprobantes encontrados para un cliente. Los campos `tipo_factura_para_emitir` y `condicion_iva_para_emitir`, cuando existen, son las instrucciones actuales del usuario y prevalecen sobre los antecedentes históricos. Si hay varias coincidencias sin instrucción actual, mostrá las opciones antes de preparar la factura. Una lista de IVA vacía significa que queda por confirmar. La condición de venta para nuevas facturas es **Contado**.

Algunos documentos de personas del exterior pueden aparecer con distintos nombres. Al consultar uno de esos documentos, usá también la razón social para identificar la ficha.
