from afip_data_transformation import transform_afip_inbound_invoices # -> Transforma los comprobantes en formato que necesitamos
from bookit_data_transformation import procesar_inbound_html # -> Transforma el registro de afip
from data_comparison import comparar_facturas_compra # -> Compara ambos registros y devuelve una lista de los que no están actualizados

#LIBRERIAS DEL PROYECTO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import lxml
import pandas as pd
import string
import numpy as np
import html5lib

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # raíz del proyecto
afip_data = pd.read_excel(BASE_DIR / 'downloads' / 'comprobantes_recibidos.xlsx', header=0, skiprows=1)
bookit_data_inbound = procesar_inbound_html(str(BASE_DIR / 'downloads' / 'inbound.html'))


afip_data_inbound = transform_afip_inbound_invoices(afip_data)
clean_data = comparar_facturas_compra(afip_data_inbound,bookit_data_inbound,1)

#LIBRERIAS DEL PROYECTO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

# clean_data es la varaible que va a cargar en sistema. 

# A partir de aquí todo esto se transforma en función

#Este es driver que va a navegar.
driver = webdriver.Chrome()

# Función para iniciar sesión
arancia_url = 'https://arancia-bookit.com/'

driver.get(arancia_url)
time.sleep(3)

# Entrar a la web
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
    driver.find_element(By.NAME, 'DetailsView1$TextBox7').send_keys(row['TOTAL_NO_GRAVADO'])
    # Haz clic en el botón "Agregar"
    driver.find_element(By.LINK_TEXT, 'Agregar').click()
    # Espera un poco para que la página se actualice
    time.sleep(3)

driver.quit()