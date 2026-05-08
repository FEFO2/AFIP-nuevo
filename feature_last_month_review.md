Objetivo:
realizar una revisión en el sistema de las facturas cargadas el mes pasado

Pasos para obtener facturas del mes pasado:
1- Modificar archivo download_afip_reports.py en la linea 69:
    popup.get_by_text("Este mes").click()
    por
    popup.get_by_text("Mes pasado").click()    
Esta modificación permite obtener las facturas del mes pasado.

2- Modificar archivo download_bookit_reports.py a partir de la linea 100:
    Tomar el segundo elemento de la lista desplegable #DropDownList1
Esta modificacion permite obtener las facturas del mes pasado.
Ya obtenidos ambos reportes, el proceso sigue igual.

Forma de implementación:
Un argumento dentro de main.py que permita distinguir si la función toma las facturas del mes actual o pasado.

IMPORTANTE:
- No está claro el paso 2 para que logre el objetivo. Verificar ese paso exaustivamente.

