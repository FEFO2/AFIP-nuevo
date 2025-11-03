from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO

# --- FUNCION 1: PROCESADO DE HTML DE VENTAS ----


def procesar_outbound_html(path_html: str) -> pd.DataFrame:
    """
    Procesa un archivo HTML exportado de Arancia y devuelve un DataFrame
    con las columnas necesarias para comparar con AFIP.

    Parámetros:
        path_html (str): ruta al archivo HTML (por ejemplo, "../outbound.html")

    Devuelve:
        pd.DataFrame con columnas ['FACTURA', 'TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']
    """

    # Leer archivo HTML
    with open(path_html, encoding="utf-8") as f:
        html = f.read()

    # Parsear HTML con BeautifulSoup (auto repara etiquetas mal cerradas)
    soup = BeautifulSoup(html, "html.parser")

    # Intentar encontrar tabla
    table = soup.find("table")
    if not table:
        wrapped = f"<table>{soup}</table>"
        table = BeautifulSoup(wrapped, "html.parser").find("table")

    # Convertir tabla a DataFrame
    df = pd.read_html(StringIO(str(table)))[0]

    # Si hay columnas con nombres similares pero no exactos,
    # normalizamos para evitar errores por espacios o mayúsculas
    df.columns = df.columns.str.strip().str.upper()

    # Verificar columnas necesarias antes de continuar
    required_cols = ['FACTURA', 'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'NO GRAVADO']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"⚠️ Faltan columnas requeridas en el HTML: {missing}")

    # Calcular totales
    df['TOTAL_10.5'] = df['NETO 10.5'] + df['IVA 10.5']
    df['TOTAL_21'] = df['NETO 21'] + df['IVA 21']
    df['TOTAL_NO_GRAVADO'] = df['NO GRAVADO']

    # Seleccionar columnas finales
    cols = ['FACTURA', 'TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']
    df = df[cols]

    # Asegurar tipos numéricos
    for col in ['TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    print(f"✅ Archivo {path_html} procesado correctamente ({len(df)} filas).")

    return df

# --- FUNCION 2: PROCESADO DE HTML DE COMPRAS ----

from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO

def procesar_inbound_html(path_html: str) -> pd.DataFrame:
    """
    Procesa un archivo HTML de COMPRAS exportado de Arancia y devuelve
    un DataFrame con las columnas necesarias para comparar con AFIP.

    Parámetros:
        path_html (str): ruta al archivo HTML (por ejemplo, "../inbound.html")

    Devuelve:
        pd.DataFrame con columnas ['FACTURA','NETO 10.5','IVA 10.5','NETO 21','IVA 21','NO GRAVADO']
    """

    # Leer archivo HTML
    with open(path_html, encoding="utf-8") as f:
        html = f.read()

    # Parsear con BeautifulSoup (repara etiquetas mal cerradas)
    soup = BeautifulSoup(html, "html.parser")

    # Intentar encontrar tabla
    table = soup.find("table")
    if not table:
        wrapped = f"<table>{soup}</table>"
        table = BeautifulSoup(wrapped, "html.parser").find("table")

    # Convertir tabla a DataFrame
    df = pd.read_html(StringIO(str(table)))[0]

    # Normalizar nombres de columnas
    df.columns = df.columns.str.strip().str.upper()

    df['TOTAL_NO_GRAVADO'] = df['NO GRAVADO']

    # Verificar que estén las columnas esperadas
    required_cols = ['FACTURA','NETO 10.5','IVA 10.5','NETO 21','IVA 21','TOTAL_NO_GRAVADO']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"⚠️ Faltan columnas requeridas en el HTML: {missing}")

    # Filtrar solo las columnas relevantes
    df = df[required_cols]

    # Convertir columnas numéricas
    for col in ['NETO 10.5','IVA 10.5','NETO 21','IVA 21','NO GRAVADO']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    print(f"✅ Archivo {path_html} procesado correctamente ({len(df)} filas).")

    return df
