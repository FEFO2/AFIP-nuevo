"""
Archivo de configuración para el proyecto AFIP
"""

# Configuración de la aplicación web
WEB_CONFIG = {
    'url': 'http://arancia-001-site1.btempurl.com/',
    'username': 'FRANCESC',
    'password': 'n4r4nj4720',
    'timeout': 3
}

# Configuración de rutas
PATHS = {
    'downloads': 'C:\\Users\\Francesc\\Downloads',
    'excel_file': 'Mis Comprobantes Recibidos - CUIT 30714894346.xlsx'
}

# Configuración de procesamiento de datos
DATA_CONFIG = {
    'proveedor_length': 35,
    'punto_venta_length': 5,
    'numero_desde_length': 8
}

# Configuración de logging
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'afip.log'
} 