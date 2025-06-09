# AFIP Data Uploader

Este programa automatiza el proceso de carga de datos de facturas AFIP a la plataforma Arancia.

## Requisitos

- Python 3.8 o superior
- Chrome Browser instalado
- ChromeDriver compatible con tu versión de Chrome

## Instalación

1. Clona este repositorio o descarga los archivos
2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

## Uso

1. Ejecuta el programa:
```bash
python main.py
```

2. Sigue las opciones del menú:
   - Opción 1: Iniciar sesión en Arancia
   - Opción 2: Procesar archivo Excel
   - Opción 3: Subir datos a Arancia
   - Opción 4: Salir

## Notas importantes

- Asegúrate de tener el archivo Excel con el formato correcto antes de procesarlo
- El programa requiere una conexión a internet activa
- Las credenciales de Arancia están hardcodeadas en el programa

## Formato del archivo Excel

El archivo Excel debe tener las siguientes columnas:
- Fecha
- Tipo
- Punto de Venta
- Número Desde
- Denominación Emisor
- Nro. Doc. Emisor
- Tipo Cambio
- Imp. Neto Gravado
- Imp. Neto No Gravado
- Imp. Op. Exentas
- Otros Tributos
- IVA 