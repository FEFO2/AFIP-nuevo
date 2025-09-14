#LIBRERIAS DEL PROYECTO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

import pandas as pd
import string
import numpy as np

#--------------------------------------------------------------------------------------
# PARTE 1: PROCESA LAS FACTURAS

import pandas as pd
import string
import numpy as np

data = pd.read_excel(r'C:\Users\ThinkPad-PC\Downloads\Mis Comprobantes Recibidos - CUIT 30714894346.xlsx', header=0, skiprows=1)

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


# PONER 0 A TODAS LAS COLUMNAS
columnas = ['NETO 0', 'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO', 'EXENTO', 'IMPUESTOS',
            'IVA 2,5%', 'IVA 5%', 'IVA 27%'] 
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
clean = ['Fecha','Factura',
        'Proveedor','CUIT',
        'NETO 10.5', 'IVA 10.5',
        'NETO 21', 'IVA 21', 'TOTAL_NO_GRAVADO']

clean_data = data[clean]
clean_data

#--------------------------------------------------------------------------------------
# PARTE 2: SUBIR LAS FACTURAS AL SERVIDOR DE ARANCIA

#Este es driver que va a navegar.
driver = webdriver.Chrome()

# Función para iniciar sesión
arancia_url = 'http://arancia-001-site1.btempurl.com/'

driver.get(arancia_url)
time.sleep(3)

# Entrar a la web
element = driver.find_element(By.ID,"Button1")
element.click()
time.sleep(3)

element = driver.find_element(By.ID, 'TextBox1')
element.send_keys('FRANCESC')
element = driver.find_element(By.ID, 'TextBox2')
element.send_keys('n4r4nj4720')

element = driver.find_element(By.ID,"Button1")
element.click()
time.sleep(3)

element = driver.find_element(By.ID,"Button10")
element.click()
time.sleep(3)

driver.switch_to.frame('facturacion')
element = driver.find_element(By.ID,"Button3")
element.click()

driver.switch_to.frame('marco')

for index, row in clean_data.iterrows():
    # Encuentra cada campo por su id y llena el valor
    driver.find_element(By.ID, 'DetailsView1_TextBox1').send_keys(row['Fecha'])
    driver.find_element(By.ID, 'DetailsView1_TextBox2').send_keys(row['Fecha'])
    driver.find_element(By.NAME, 'DetailsView1$ctl02').send_keys(row['Tipo3'])
    driver.find_element(By.NAME, 'DetailsView1$ctl03').send_keys(row['Factura'])
    driver.find_element(By.NAME, 'DetailsView1$ctl04').send_keys(row['Proveedor'])
    driver.find_element(By.NAME, 'DetailsView1$ctl05').send_keys(row['CUIT'])
    driver.find_element(By.NAME, 'DetailsView1$TextBox3').send_keys(row['NETO 10.5'])
    driver.find_element(By.NAME, 'DetailsView1$TextBox4').send_keys(row['NETO 21'])
    driver.find_element(By.NAME, 'DetailsView1$TextBox5').send_keys(row['IVA 10.5'])
    driver.find_element(By.NAME, 'DetailsView1$TextBox6').send_keys(row['IVA 21'])
    driver.find_element(By.NAME, 'DetailsView1$TextBox7').send_keys(row['NO GRAVADO'])
    # Haz clic en el botón "Agregar"
    driver.find_element(By.LINK_TEXT, 'Agregar').click()
    # Espera un poco para que la página se actualice
    time.sleep(3)

    os.remove(r'C:\Users\ThinkPad-PC\Downloads\Mis Comprobantes Recibidos - CUIT 30714894346.xlsx')
