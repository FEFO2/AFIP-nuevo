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
from config import *

#--------------------------------------------------------------------------------------
# PARTE 1: DESCARGA DEL ARCHIVO CON LAS FACTURAS

# Este es driver que va a navegar.
driver = webdriver.Chrome()

# Esta es la web para comenzar
afip_url = 'https://auth.afip.gob.ar/contribuyente_/login.xhtml'

# Función para iniciar sesión
def download_invoices(username, password):
    driver.get(afip_url)
    
    # Esperar hasta que el campo de CUIT esté presente
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'F1:username'))
    )
    
    # Ingresar CUIT
    cuit_field = driver.find_element(By.ID, 'F1:username')
    cuit_field.send_keys(username)

    element = driver.find_element(By.ID, 'F1:btnSiguiente')
    element.click()
    
    # Ingresar Clave
    password_field = driver.find_element(By.ID, 'F1:password')
    password_field.send_keys(password)
    element = driver.find_element(By.ID, 'F1:btnIngresar')
    element.click()

    # Ingresar en los servicios de facturación
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.LINK_TEXT, 'Ver todos')))
    element = driver.find_element(By.LINK_TEXT,'Ver todos')
    element.click()

    # Abrir servicios de facturación    
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[@title='mcmp']")))
    element = driver.find_element(By.XPATH, "//a[@title='mcmp']")
    element.location_once_scrolled_into_view
    time.sleep(5)
    element.click()

    # Encuentra el elemento y haz clic en él
    time.sleep(5)
    driver.switch_to.window(driver.window_handles[-1])
    element = driver.find_element(By.XPATH,"//a[@onclick=\"document.getElementById('idcontribuyente').value='0';document.seleccionaEmpresaForm.submit();return false;\"]")
    element.click()

    # Comprobantes recibidos
    element = driver.find_element(By.ID,"btnRecibidos")
    element.location_once_scrolled_into_view
    element.click()
    time.sleep(2)

    # Fecha de emisión
    element = driver.find_element(By.ID,"btnCalendarioFechaEmision")
    element.click()
    time.sleep(3)

    # Fecha de emisión
    element = driver.find_element(By.XPATH,"//li[@data-range-key='Ayer']")
    element.click()
    time.sleep(3)

    element = driver.find_element(By.ID,"buscarComprobantes")
    element.click()
    time.sleep(3)

    # Descargar el excel
    element = driver.find_element(By.CSS_SELECTOR, ".btn.btn-default.buttons-excel.buttons-html5.btn-defaut.btn-sm.sinborde")
    element.click()
    time.sleep(5)

    driver.quit()

download_invoices(20244138897,'Arancia.2023')

#--------------------------------------------------------------------------------------
# PARTE 2: PROCESAR LAS FACTURAS PARA ADECUARSE A LA PÁGINA WEB DE ARANCIA

data = pd.read_excel(r'C:\Users\Francesc\Downloads\Mis Comprobantes Recibidos - CUIT 30714894346.xlsx', header=0, skiprows=1)

#FECHA
data['Fecha'] = pd.to_datetime(data['Fecha'], format='%d/%m/%Y')
data['Fecha'] = data['Fecha'].dt.strftime('%m/%d/%Y')

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

# TIPO DE CAMBIO
columnas = ['Imp. Neto Gravado', 'Imp. Neto No Gravado', 
            'Imp. Op. Exentas', 'Otros Tributos', 'IVA']
for col in columnas:
    data[col] = data[col] * data['Tipo Cambio']

# IVA (10.5 O 21)
data['% IVA'] = (data['IVA'] / data['Imp. Neto Gravado']) * 100
data['% IVA'] = np.where(abs(data['% IVA'] - 21) < 0.01, 21, data['% IVA'])
data['% IVA'] = np.where(abs(data['% IVA'] - 10.5) < 0.01, 10.5, data['% IVA'])

# CREAR COLUMNAS DE VALORES
data['NETO 10.5'] = np.nan
data['IVA 10.5'] = np.nan
data['NETO 21'] = np.nan
data['IVA 21'] = np.nan
data['NO GRAVADO'] = np.nan

# PONER 0 A TODAS LAS COLUMNAS
columnas = ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
for col in columnas:
    data[col] = data[col].fillna(0)

# Convertimos las columnas a str
data['NETO 10.5'] = data['NETO 10.5'].astype(str)
data['IVA 10.5'] = data['IVA 10.5'].astype(str)
data['NETO 21'] = data['NETO 21'].astype(str)
data['IVA 21'] = data['IVA 21'].astype(str)


# Asignamos los valores correspondientes a las nuevas columnas
data.loc[data['% IVA'] == 10.5, 'NETO 10.5'] = data['Imp. Neto Gravado'].astype(str)
data.loc[data['% IVA'] == 10.5, 'IVA 10.5'] = data['IVA'].astype(str)
data.loc[data['% IVA'] == 21, 'NETO 21'] = data['Imp. Neto Gravado'].astype(str)
data.loc[data['% IVA'] == 21, 'IVA 21'] = data['IVA'].astype(str)
data[col] = data[col].fillna(0)
# NO GRAVADO
data['NO GRAVADO'] = (data['Imp. Neto No Gravado'] + data['Imp. Op. Exentas'] + data['Otros Tributos'])

# PONER EN NEGATICO LAS COLUMNAS QUE SON CREDITO
for col in columnas:
    data.loc[data['Tipo2'] == 'Crédito', col] = -data[col].astype(float)
    data[col] = data[col].astype(str)

# CREAR Y APLICAR MÁSCARA
clean = ['Fecha','Tipo3','Factura',
        'Proveedor','CUIT',
        'NETO 10.5', 'IVA 10.5',
        'NETO 21', 'IVA 21', 'NO GRAVADO']

clean_data = data[clean]

#--------------------------------------------------------------------------------------
# PARTE 3: SUBIR LAS FACTURAS AL SERVIDOR DE ARANCIA

# Web driver
driver = webdriver.Chrome()

# Pagina web
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

# Cerrar driver
driver.quit()

# Eliminar el archivo
os.remove(r'C:\Users\Francesc\Downloads\Mis Comprobantes Recibidos - CUIT 30714894346.xlsx')
