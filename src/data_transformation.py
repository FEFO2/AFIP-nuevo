import pandas as pd
import string
import numpy as np
import re


# ------ FUNCTION 1 --------
# --- This function will use the document called "comprobantes recibidos" and will transform into the private database.


def transform_inbound_invoices(data):
    #TIPO DE FACTURA
    data['Tipo'] = data['Tipo'].astype('string').str[-9:]
    data['Tipo2'] = data['Tipo'].str[:7]
    data['Tipo3'] = data['Tipo'].str[-1:]

    # FACTURA
    data['Punto de Venta'] = data['Punto de Venta'].astype(str).str.zfill(5)
    data['Número Desde'] = data['Número Desde'].astype(str).str.zfill(8)
    data['Factura'] = data['Punto de Venta'] + '-' + data['Número Desde']

    # PROVEEDOR
    data['Denominación Emisor'] = data['Denominación Emisor'].str.translate(
        str.maketrans('', '', string.punctuation))
    data['Proveedor'] = data['Denominación Emisor'].str[:35]

    # CUIT
    data['CUIT'] = data['Nro. Doc. Emisor'].astype(str)


    # IMPORTES
    data['NETO 10.5'] = data['Neto Grav. IVA 10,5%'] 
    data['IVA 10.5'] = data['IVA 10,5%'] 
    data['NETO 21'] = data['Neto Grav. IVA 21%'] 
    data['IVA 21'] = data['IVA 21%'] 
    data['NO GRAVADO'] = data['Neto No Gravado'] 
    data['EXENTO'] = data['Op. Exentas'] 
    data['IMPUESTOS'] = data['Otros Tributos']
    data['NETO 0'] = data['Neto Grav. IVA 0%']
    data['TOTAL_NO_GRAVADO'] = (data['NO GRAVADO'] + data['EXENTO'] + data['IMPUESTOS'] + data['NETO 0'])

    # PONER 0 A TODAS LAS COLUMNAS
    columnas = ['NETO 0', 'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO', 'EXENTO', 'IMPUESTOS',
                'IVA 2,5%', 'IVA 5%', 'IVA 27%', 'TOTAL_NO_GRAVADO'] 
    for col in columnas: 
        data[col] = data[col].fillna(0)

    # TIPO DE CAMBIO ESTE CAMBIAR PORQUE CAMBIA A FUTURO
    columnas_tc = ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO', 'EXENTO', 'IMPUESTOS'] 
    for col in columnas_tc: 
        data[col] = data[col] * data['Tipo Cambio']

    # SUMAR LO QUE NO LLEVA IVA
    data['TOTAL_NO_GRAVADO'] = (data['NO GRAVADO'] + data['EXENTO'] + data['IMPUESTOS'] + data['NETO 0'])

    # Convertimos las columnas a str
    data['NETO 10.5'] = data['NETO 10.5'].astype(str)
    data['IVA 10.5'] = data['IVA 10.5'].astype(str)
    data['NETO 21'] = data['NETO 21'].astype(str)
    data['IVA 21'] = data['IVA 21'].astype(str)

    # PONER EN NEGATICO LAS COLUMNAS QUE SON CREDITO
    for col in columnas:
        data.loc[data['Tipo2'] == 'Crédito', col] = -data[col].astype(float)
        data[col] = data[col].astype(str)

    # CREAR Y APLICAR MÁSCARA
    clean = ['Fecha','Tipo2','Tipo3', 'Factura',
            'Proveedor','CUIT', 'NETO 10.5', 
            'NETO 21', 'IVA 10.5', 'IVA 21', 
            'TOTAL_NO_GRAVADO']

    clean_data = data[clean]
    return clean_data


# ------ FUNCTION 2 --------
# --- This function will use the document called "comprobantes emitidos" and will transform into the private database.

def transform_outbound_invoices(data):
    #TIPO DE FACTURA
#TIPO DE FACTURA
    data['codigo_fc'] = [int(re.match(r'(\d+)', x).group(1)) for x in data['Tipo']]
    data['Tipo'] = data['Tipo'].astype('string').str[-9:]
    data['Tipo2'] = data['Tipo'].str[:7]
    data['Tipo3'] = data['Tipo'].str[-1:]

    data['tipo2_new'] = np.where(data['codigo_fc'].isin([1,6,11]), "Factura", "Credito")
    data['tipo2_new'] = np.where(data['codigo_fc'] == 201, "Pyme_fc", data['tipo2_new'])
    data['tipo2_new'] = np.where(data['codigo_fc'] == 203, "Pyme_nc", data['tipo2_new'])

    data['tipo3_new'] = np.where(data['codigo_fc'].isin([1,3,201,203]), "A", "C")
    data['tipo3_new'] = np.where(data['codigo_fc'].isin([6,8]), "B", data['tipo3_new'])

    data['tipo3_new']

    # FACTURA
    data['Punto de Venta'] = data['Punto de Venta'].astype(str).str.zfill(5)
    data['Número Desde'] = data['Número Desde'].astype(str).str.zfill(8)
    data['Factura'] = data['Número Desde'].astype(int)

    # Cliente
    data['Denominación Receptor'] = data['Denominación Receptor'].str.translate(
        str.maketrans('', '', string.punctuation))
    data['Cliente'] = data['Denominación Receptor'].str[:35]

    # CUIT
    data['CUIT'] = data['Nro. Doc. Receptor'].astype(str)


    # IMPORTES
    data['NETO 10.5'] = data['Neto Grav. IVA 10,5%'] 
    data['IVA 10.5'] = data['IVA 10,5%'] 
    data['NETO 21'] = data['Neto Grav. IVA 21%'] 
    data['IVA 21'] = data['IVA 21%'] 
    data['NO GRAVADO'] = data['Neto No Gravado'] 
    data['EXENTO'] = data['Op. Exentas'] 
    data['IMPUESTOS'] = data['Otros Tributos']
    data['NETO 0'] = data['Neto Grav. IVA 0%']
    data['TOTAL_NO_GRAVADO'] = (data['NO GRAVADO'] + data['EXENTO'] + data['IMPUESTOS'] + data['NETO 0'])
    data['TOTAL_10.5'] = round(data['NETO 10.5'] + data['IVA 10.5'],2)
    data['TOTAL_21'] = round(data['NETO 21'] + data['IVA 21'],2)


    # PONER 0 A TODAS LAS COLUMNAS QUE NO TIENEN ALGO
    columnas = ['NETO 0', 'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO', 'EXENTO', 'IMPUESTOS',
                'IVA 2,5%', 'IVA 5%', 'IVA 27%', 'TOTAL_NO_GRAVADO', 'TOTAL_10.5', 'TOTAL_21'] 
    for col in columnas: 
        data[col] = data[col].fillna(0)

    # TIPO DE CAMBIO ESTE CAMBIAR PORQUE CAMBIA A FUTURO
    columnas_tc = ['NETO 0','NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO', 'EXENTO', 'IMPUESTOS', 'TOTAL_10.5', 'TOTAL_21'] 
    for col in columnas_tc: 
        data[col] = data[col] * data['Tipo Cambio']

    # SUMAR LO QUE NO LLEVA IVA
    data['TOTAL_NO_GRAVADO'] = (data['NO GRAVADO'] + data['EXENTO'] + data['IMPUESTOS'] + data['NETO 0'])

    # Convertimos las columnas a str
    data['NETO 10.5'] = data['NETO 10.5'].astype(str)
    data['IVA 10.5'] = data['IVA 10.5'].astype(str)
    data['NETO 21'] = data['NETO 21'].astype(str)
    data['IVA 21'] = data['IVA 21'].astype(str)
    data['TOTAL_21'] = data['TOTAL_21'].astype(str)
    data['TOTAL_10.5'] = data['TOTAL_10.5'].astype(str)

    # PONER EN NEGATIVO LAS COLUMNAS QUE SON CREDITO
    for col in columnas:
        mask = (data['tipo2_new'] == 'Credito') | (data['tipo2_new'] == 'Pyme_nc')
        data.loc[mask, col] = -data.loc[mask, col].astype(float)
        data[col] = data[col].astype(str)

    # CREAR Y APLICAR MÁSCARA
    clean = ['Fecha','tipo2_new','tipo3_new', 'Factura',
            'Cliente','CUIT', 'TOTAL_10.5', 'TOTAL_21',
            'TOTAL_NO_GRAVADO']

    clean_data = data[clean]
    return clean_data
