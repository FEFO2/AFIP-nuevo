"""
Script principal para la automatización de carga de datos AFIP
"""

import logging
from web_automation import WebAutomation
from data_processor import DataProcessor
from config import LOGGING_CONFIG
import os
import pandas as pd
import string
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

def setup_logging():
    """Configura el logging global de la aplicación"""
    logging.basicConfig(
        level=LOGGING_CONFIG['level'],
        format=LOGGING_CONFIG['format'],
        filename=LOGGING_CONFIG['file']
    )

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def mostrar_menu():
    print("\n=== MENÚ PRINCIPAL ===")
    print("1. Iniciar sesión en Arancia")
    print("2. Procesar archivo Excel")
    print("3. Subir datos a Arancia")
    print("4. Salir")
    return input("\nSeleccione una opción (1-4): ")

def iniciar_sesion():
    print("\nIniciando sesión en Arancia...")
    driver = webdriver.Chrome()
    arancia_url = 'http://arancia-001-site1.btempurl.com/'
    
    try:
        driver.get(arancia_url)
        time.sleep(3)
        
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
        
        print("¡Sesión iniciada exitosamente!")
        return driver
    except Exception as e:
        print(f"Error al iniciar sesión: {str(e)}")
        return None

def procesar_excel():
    print("\nProcesando archivo Excel...")
    try:
        ruta_archivo = input("Ingrese la ruta completa del archivo Excel: ")
        data = pd.read_excel(ruta_archivo, header=0, skiprows=1)
        
        # Procesamiento de datos (mismo código que en el notebook)
        data['Fecha'] = pd.to_datetime(data['Fecha'], format='%d/%m/%Y')
        data['Fecha'] = data['Fecha'].dt.strftime('%m/%d/%Y')
        
        data['Tipo'] = data['Tipo'].astype('string').str[-9:]
        data['Tipo2'] = data['Tipo'].str[:7]
        data['Tipo3'] = data['Tipo'].str[-1:]
        
        data['Punto de Venta'] = data['Punto de Venta'].astype(str).str.zfill(5)
        data['Número Desde'] = data['Número Desde'].astype(str).str.zfill(8)
        data['Factura'] = data['Punto de Venta'] + '-' + data['Número Desde']
        
        data['Denominación Emisor'] = data['Denominación Emisor'].str.translate(
            str.maketrans('', '', string.punctuation))
        data['Proveedor'] = data['Denominación Emisor'].str[:35]
        
        data['CUIT'] = data['Nro. Doc. Emisor'].astype(str)
        
        columnas = ['Imp. Neto Gravado', 'Imp. Neto No Gravado', 
                    'Imp. Op. Exentas', 'Otros Tributos', 'IVA']
        for col in columnas:
            data[col] = data[col] * data['Tipo Cambio']
        
        data['% IVA'] = (data['IVA'] / data['Imp. Neto Gravado']) * 100
        data['% IVA'] = np.where(abs(data['% IVA'] - 21) < 0.01, 21, data['% IVA'])
        data['% IVA'] = np.where(abs(data['% IVA'] - 10.5) < 0.01, 10.5, data['% IVA'])
        
        data['NETO 10.5'] = np.nan
        data['IVA 10.5'] = np.nan
        data['NETO 21'] = np.nan
        data['IVA 21'] = np.nan
        data['NO GRAVADO'] = np.nan
        
        columnas = ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
        for col in columnas:
            data[col] = data[col].fillna(0)
        
        for col in columnas:
            data[col] = data[col].astype(str)
        
        data.loc[data['% IVA'] == 10.5, 'NETO 10.5'] = data['Imp. Neto Gravado'].astype(str)
        data.loc[data['% IVA'] == 10.5, 'IVA 10.5'] = data['IVA'].astype(str)
        data.loc[data['% IVA'] == 21, 'NETO 21'] = data['Imp. Neto Gravado'].astype(str)
        data.loc[data['% IVA'] == 21, 'IVA 21'] = data['IVA'].astype(str)
        
        data['NO GRAVADO'] = (data['Imp. Neto No Gravado'] + data['Imp. Op. Exentas'] + data['Otros Tributos'])
        
        for col in columnas:
            data.loc[data['Tipo2'] == 'Crédito', col] = -data[col].astype(float)
            data[col] = data[col].astype(str)
        
        clean = ['Fecha','Tipo3','Factura',
                'Proveedor','CUIT',
                'NETO 10.5', 'IVA 10.5',
                'NETO 21', 'IVA 21', 'NO GRAVADO']
        
        clean_data = data[clean]
        print("¡Archivo procesado exitosamente!")
        return clean_data
    except Exception as e:
        print(f"Error al procesar el archivo: {str(e)}")
        return None

def subir_datos(driver, clean_data):
    if driver is None:
        print("Error: No hay una sesión activa")
        return
    
    print("\nSubiendo datos a Arancia...")
    try:
        driver.switch_to.frame('marco')
        
        for index, row in clean_data.iterrows():
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
            driver.find_element(By.LINK_TEXT, 'Agregar').click()
            time.sleep(3)
            print(f"Registro {index + 1} subido exitosamente")
        
        print("¡Todos los datos han sido subidos exitosamente!")
    except Exception as e:
        print(f"Error al subir los datos: {str(e)}")

def main():
    driver = None
    clean_data = None
    
    while True:
        limpiar_pantalla()
        opcion = mostrar_menu()
        
        if opcion == '1':
            driver = iniciar_sesion()
        elif opcion == '2':
            clean_data = procesar_excel()
        elif opcion == '3':
            subir_datos(driver, clean_data)
        elif opcion == '4':
            if driver:
                driver.quit()
            print("\n¡Gracias por usar el programa!")
            sys.exit()
        else:
            print("\nOpción no válida. Por favor, intente nuevamente.")
        
        input("\nPresione Enter para continuar...")

if __name__ == "__main__":
    main() 