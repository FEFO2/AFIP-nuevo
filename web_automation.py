"""
Módulo para manejar la automatización web con Selenium
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from config import WEB_CONFIG

class WebAutomation:
    def __init__(self):
        self.driver = None
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
    def setup_logging(self):
        """Configura el logging para la clase"""
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('web_automation.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def iniciar_navegador(self):
        """Inicia el navegador Chrome"""
        try:
            self.driver = webdriver.Chrome()
            self.logger.info("Navegador iniciado correctamente")
        except WebDriverException as e:
            self.logger.error(f"Error al iniciar el navegador: {str(e)}")
            raise

    def login(self):
        """Realiza el proceso de login en la aplicación"""
        try:
            self.driver.get(WEB_CONFIG['url'])
            time.sleep(WEB_CONFIG['timeout'])

            # Click en el botón inicial
            self._esperar_y_click(By.ID, "Button1")
            
            # Ingresar credenciales
            self._esperar_y_escribir(By.ID, 'TextBox1', WEB_CONFIG['username'])
            self._esperar_y_escribir(By.ID, 'TextBox2', WEB_CONFIG['password'])
            
            # Click en login
            self._esperar_y_click(By.ID, "Button1")
            
            # Click en facturación
            self._esperar_y_click(By.ID, "Button10")
            
            # Cambiar al frame de facturación
            self.driver.switch_to.frame('facturacion')
            self._esperar_y_click(By.ID, "Button3")
            
            self.logger.info("Login realizado correctamente")
        except Exception as e:
            self.logger.error(f"Error durante el login: {str(e)}")
            raise

    def _esperar_y_click(self, by, value, timeout=10):
        """Espera a que un elemento sea clickeable y hace click"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            element.click()
        except TimeoutException:
            self.logger.error(f"Timeout esperando elemento clickeable: {value}")
            raise

    def _esperar_y_escribir(self, by, value, text, timeout=10):
        """Espera a que un elemento sea visible y escribe texto"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            element.send_keys(text)
        except TimeoutException:
            self.logger.error(f"Timeout esperando elemento visible: {value}")
            raise

    def subir_datos(self, datos):
        """Sube los datos al sistema"""
        try:
            self.driver.switch_to.frame('marco')
            for index, row in datos.iterrows():
                self._subir_fila(row)
                time.sleep(WEB_CONFIG['timeout'])
            self.logger.info("Datos subidos correctamente")
        except Exception as e:
            self.logger.error(f"Error al subir datos: {str(e)}")
            raise

    def _subir_fila(self, row):
        """Sube una fila individual de datos"""
        try:
            self._esperar_y_escribir(By.ID, 'DetailsView1_TextBox1', row['Fecha'])
            self._esperar_y_escribir(By.ID, 'DetailsView1_TextBox2', row['Fecha'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$ctl02', row['Tipo3'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$ctl03', row['Factura'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$ctl04', row['Proveedor'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$ctl05', row['CUIT'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$TextBox3', row['NETO 10.5'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$TextBox4', row['NETO 21'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$TextBox5', row['IVA 10.5'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$TextBox6', row['IVA 21'])
            self._esperar_y_escribir(By.NAME, 'DetailsView1$TextBox7', row['NO GRAVADO'])
            self._esperar_y_click(By.LINK_TEXT, 'Agregar')
        except Exception as e:
            self.logger.error(f"Error al subir fila: {str(e)}")
            raise

    def cerrar(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
            self.logger.info("Navegador cerrado correctamente") 