#LIBRERIAS DEL PROYECTO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from afip_data_transformation import transform_afip_outbound_invoices # -> Transforma los comprobantes en formato que necesitamos
from bookit_data_transformation import procesar_outbound_html # -> Transforma el registro de afip
from data_comparison import comparar_facturas_venta # -> Compara ambos registros y devuelve una lista de los que no están actualizados
import os
import lxml
import pandas as pd
import string
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # raíz del proyecto
afip_data = pd.read_excel(BASE_DIR / 'downloads' / 'comprobantes_emitidos.xlsx', header=0, skiprows=1)
bookit_data_outbound = procesar_outbound_html(str(BASE_DIR / 'downloads' / 'outbound.html'))
afip_data_outbound = transform_afip_outbound_invoices(afip_data)
clean_data = comparar_facturas_venta(afip_data_outbound,bookit_data_outbound,1)

#LIBRERIAS DEL PROYECTO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

#Este es driver que va a navegar.
driver = webdriver.Chrome()

# Función para iniciar sesión
arancia_url = 'https://arancia-bookit.com/'

driver.get(arancia_url)
time.sleep(3)

# Colocar las claves
element = driver.find_element(By.ID, 'TextBox1')
element.send_keys('FRANCESC')
element = driver.find_element(By.ID, 'TextBox2')
element.send_keys('n4r4nj4720')

# click en entrar
element = driver.find_element(By.ID,"Button1")
element.click()
time.sleep(3)

# clickear en la pestaña de "facturación"
element = driver.find_element(By.ID,"Button10")
element.click()
time.sleep(3)

# clickear en la sub-pestaña de "facturación" (para cargar facturas de ventas)
driver.switch_to.frame('facturacion')
element = driver.find_element(By.ID,"Button5")
element.click()
time.sleep(1)

driver.switch_to.frame('marco')

# Quitar check de "aéreo"
element = driver.find_element(By.ID,"CheckBoxList1_0")
element.click()
time.sleep(2)

# Poner check en "manual"
element = driver.find_element(By.ID,"CheckBoxList1_3")
element.click()
time.sleep(2)

# Buscar el input de IVAS
element = driver.find_element(By.ID, "contar")

# Seleccionar todo el texto actual
element.send_keys(Keys.CONTROL, "a")
time.sleep(0.2)

# Escribir el nuevo valor (3 por la información que manejamos)
element.send_keys("3")

# Disparar el evento de cambio usando TAB (como si el usuario saliera del campo)
element.send_keys(Keys.TAB)
time.sleep(3)

# Valores específicos para cada campo
valores = {
    "ivasa1": "0",
    "ivasa2": "10.5"  # con punto, ojo a la compa que rompe la página
}

for field_id, valor in valores.items():
    element = driver.find_element(By.ID, field_id)

    # Escribir directamente el nuevo valor (sin dejar el campo vacío)
    element.send_keys(Keys.CONTROL, 'a')
    element.send_keys(valor)
    element.send_keys(Keys.TAB)
    time.sleep(3)

for index, row in clean_data.iterrows():
    # TOTAL_NO_GRAVADO
    elem = driver.find_element(By.ID, 'total1')
    elem.send_keys(Keys.CONTROL, 'a')  # Selecciona todo
    elem.send_keys(row['TOTAL_NO_GRAVADO'])  # Sobreescribe
    elem.send_keys(Keys.TAB)
    time.sleep(3)

    # TOTAL_10.5
    elem = driver.find_element(By.ID, 'total2')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['TOTAL_10.5'])
    elem.send_keys(Keys.TAB)
    time.sleep(3)

    # TOTAL_21
    elem = driver.find_element(By.NAME, 'total3')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['TOTAL_21'])
    elem.send_keys(Keys.TAB)
    time.sleep(3)

    driver.find_element(By.ID, "Button2").click()
    time.sleep(3)

    # RAZON SOCIAL
    elem = driver.find_element(By.NAME, 'TextBox3')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['Cliente'])
    elem.send_keys(Keys.TAB)
    time.sleep(1)

    # CUIT
    elem = driver.find_element(By.NAME, 'TextBox4')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['CUIT'])
    elem.send_keys(Keys.TAB)
    time.sleep(1)   

    # Factura NÚMERO
    elem = driver.find_element(By.NAME, 'TextBox6')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['Factura'])
    elem.send_keys(Keys.TAB)
    time.sleep(1)  

    # Clase
    elem = driver.find_element(By.NAME, 'TextBox7')
    elem.send_keys(Keys.CONTROL, 'a')
    elem.send_keys(row['tipo3_new'])
    elem.send_keys(Keys.TAB)
    elem = driver.find_element(By.NAME, 'TextBox8')   
    elem.send_keys(row['Fecha'])
    time.sleep(1)

    # Click en Grabar
    driver.find_element(By.ID, "Button5").click()
    time.sleep(2)

#quit driver
driver.quit()

