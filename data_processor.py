"""
Módulo para procesar los datos del Excel
"""

import pandas as pd
import numpy as np
import string
import logging
import os
from config import PATHS, DATA_CONFIG

class DataProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        self.data = None
        
    def setup_logging(self):
        """Configura el logging para la clase"""
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('data_processor.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def cargar_datos(self):
        """Carga los datos del archivo Excel"""
        try:
            file_path = os.path.join(PATHS['downloads'], PATHS['excel_file'])
            self.data = pd.read_excel(file_path, header=0, skiprows=1)
            self.logger.info("Datos cargados correctamente")
        except Exception as e:
            self.logger.error(f"Error al cargar datos: {str(e)}")
            raise

    def procesar_datos(self):
        """Procesa los datos según las reglas de negocio"""
        try:
            self._procesar_fecha()
            self._procesar_tipo_factura()
            self._procesar_factura()
            self._procesar_proveedor()
            self._procesar_cuit()
            self._procesar_tipo_cambio()
            self._procesar_iva()
            self._crear_columnas_valores()
            self._procesar_creditos()
            self._limpiar_datos()
            self.logger.info("Datos procesados correctamente")
        except Exception as e:
            self.logger.error(f"Error al procesar datos: {str(e)}")
            raise

    def _procesar_fecha(self):
        """Procesa el campo de fecha"""
        self.data['Fecha'] = pd.to_datetime(self.data['Fecha'], format='%d/%m/%Y')
        self.data['Fecha'] = self.data['Fecha'].dt.strftime('%m/%d/%Y')

    def _procesar_tipo_factura(self):
        """Procesa el tipo de factura"""
        self.data['Tipo'] = self.data['Tipo'].astype('string').str[-9:]
        self.data['Tipo2'] = self.data['Tipo'].str[:7]
        self.data['Tipo3'] = self.data['Tipo'].str[-1:]

    def _procesar_factura(self):
        """Procesa el número de factura"""
        self.data['Punto de Venta'] = self.data['Punto de Venta'].astype(str).str.zfill(DATA_CONFIG['punto_venta_length'])
        self.data['Número Desde'] = self.data['Número Desde'].astype(str).str.zfill(DATA_CONFIG['numero_desde_length'])
        self.data['Factura'] = self.data['Punto de Venta'] + '-' + self.data['Número Desde']

    def _procesar_proveedor(self):
        """Procesa el nombre del proveedor"""
        self.data['Denominación Emisor'] = self.data['Denominación Emisor'].str.translate(
            str.maketrans('', '', string.punctuation))
        self.data['Proveedor'] = self.data['Denominación Emisor'].str[:DATA_CONFIG['proveedor_length']]

    def _procesar_cuit(self):
        """Procesa el CUIT"""
        self.data['CUIT'] = self.data['Nro. Doc. Emisor'].astype(str)

    def _procesar_tipo_cambio(self):
        """Procesa los valores según el tipo de cambio"""
        columnas = ['Imp. Neto Gravado', 'Imp. Neto No Gravado', 
                   'Imp. Op. Exentas', 'Otros Tributos', 'IVA']
        for col in columnas:
            self.data[col] = self.data[col] * self.data['Tipo Cambio']

    def _procesar_iva(self):
        """Procesa los porcentajes de IVA"""
        self.data['% IVA'] = (self.data['IVA'] / self.data['Imp. Neto Gravado']) * 100
        self.data['% IVA'] = np.where(abs(self.data['% IVA'] - 21) < 0.01, 21, self.data['% IVA'])
        self.data['% IVA'] = np.where(abs(self.data['% IVA'] - 10.5) < 0.01, 10.5, self.data['% IVA'])

    def _crear_columnas_valores(self):
        """Crea y procesa las columnas de valores"""
        # Crear columnas
        columnas = ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
        for col in columnas:
            self.data[col] = 0

        # Asignar valores
        self.data.loc[self.data['% IVA'] == 10.5, 'NETO 10.5'] = self.data['Imp. Neto Gravado']
        self.data.loc[self.data['% IVA'] == 10.5, 'IVA 10.5'] = self.data['IVA']
        self.data.loc[self.data['% IVA'] == 21, 'NETO 21'] = self.data['Imp. Neto Gravado']
        self.data.loc[self.data['% IVA'] == 21, 'IVA 21'] = self.data['IVA']
        
        # Procesar NO GRAVADO
        self.data['NO GRAVADO'] = (self.data['Imp. Neto No Gravado'] + 
                                 self.data['Imp. Op. Exentas'] + 
                                 self.data['Otros Tributos'])

    def _procesar_creditos(self):
        """Procesa los valores negativos para créditos"""
        columnas = ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
        for col in columnas:
            self.data.loc[self.data['Tipo2'] == 'Crédito', col] = -self.data[col].astype(float)
            self.data[col] = self.data[col].astype(str)

    def _limpiar_datos(self):
        """Selecciona solo las columnas necesarias"""
        columnas_limpias = ['Fecha', 'Tipo3', 'Factura', 'Proveedor', 'CUIT',
                          'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
        self.data = self.data[columnas_limpias]

    def limpiar_archivo(self):
        """Elimina el archivo Excel después de procesarlo"""
        try:
            file_path = os.path.join(PATHS['downloads'], PATHS['excel_file'])
            os.remove(file_path)
            self.logger.info("Archivo Excel eliminado correctamente")
        except Exception as e:
            self.logger.error(f"Error al eliminar archivo: {str(e)}")
            raise

    def obtener_datos_procesados(self):
        """Retorna los datos procesados"""
        return self.data 