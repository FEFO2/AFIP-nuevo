import pandas as pd
import numpy as np

# --- FUNCION 1: COMPARACIÓN DE FACTURAS DE VENTA ----

def comparar_facturas_venta(afip_df, sistem_df,tolerancia = 1.0):
    """
    Compara las facturas de AFIP con las cargadas en el sistema.
    
    Parámetros:
        afip_df (pd.DataFrame): dataset con facturas AFIP (columna NUMERO)
        sistem_df (pd.DataFrame): dataset con facturas del sistema (columna FACTURA)
        tolerancia (float): diferencia máxima aceptable en totales (default = 1.0)
    
    Devuelve:
        pd.DataFrame: copia de afip_df con columnas extra:
                      - 'loaded' (bool)
                      - 'totales_ok' (bool o NaN si no está cargada)
    """  
       # Copias para no modificar los originales
    a = afip_df.copy()
    b = sistem_df.copy()

    # --- Normalizar claves ---
    a['Factura'] = a['Factura'].astype(str).str.strip()
    b['FACTURA'] = b['FACTURA'].astype(str).str.strip()

    # --- Merge por clave ---
    merged = a.merge(
        b[['FACTURA', 'TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']],
        left_on='Factura',
        right_on='FACTURA',
        how='left',
        suffixes=('', '_sistema')
    )

    # --- Columna de existencia ---
    merged['loaded'] = ~merged['FACTURA'].isna()

    # --- Forzar tipos numéricos y calcular diferencias ---
    for col in ['TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']:
        merged[col] = pd.to_numeric(merged[col], errors='coerce')
        merged[f'{col}_sistema'] = pd.to_numeric(merged[f'{col}_sistema'], errors='coerce')
        merged[f'diff_{col}'] = abs(merged[col] - merged[f'{col}_sistema'])

    # --- Evaluar si las diferencias son menores o iguales a la tolerancia ---
    merged['totales_ok'] = (
        merged[[f'diff_{c}' for c in ['TOTAL_10.5', 'TOTAL_21', 'TOTAL_NO_GRAVADO']]]
        .max(axis=1) <= tolerancia
    )

    # --- Si no está cargada, totales_ok = NaN ---
    merged.loc[~merged['loaded'], 'totales_ok'] = np.nan

    # --- Logs ---
    no_cargadas = merged[~merged['loaded']]
    mal_cargadas = merged[(merged['loaded']) & (~merged['totales_ok'].fillna(False))]

    # Facturas no cargadas
    if len(no_cargadas) > 0:
        print(f"⚠️  {len(no_cargadas)} facturas no están cargadas en el sistema.")
    else:
        print("✅ Todas las facturas AFIP están cargadas en el sistema.")

    # Facturas cargadas pero con error en totales
    for factura in mal_cargadas['Factura']:
        print(f"❌ La factura {factura} no está cargada correctamente (diferencia en totales).")

    # --- Filtrar solo las facturas correctamente cargadas ---
    resultado = merged.loc[~merged['loaded'], a.columns[:9]].copy()


    print(f"✅ {len(resultado)} facturas correctamente cargadas y listas para procesar.")

    return resultado

# --- FUNCION 2 : COMPARAR COMPRAS ---

def comparar_facturas_compra(afip_df, sistem_df,tolerancia = 1.0):
    """
    Compara las facturas de AFIP con las cargadas en el sistema.
    
    Parámetros:
        afip_df (pd.DataFrame): dataset con facturas AFIP (columna NUMERO)
        sistem_df (pd.DataFrame): dataset con facturas del sistema (columna FACTURA)
        tolerancia (float): diferencia máxima aceptable en totales (default = 1.0)
    
    Devuelve:
        pd.DataFrame: copia de afip_df con columnas extra:
                      - 'loaded' (bool)
                      - 'totales_ok' (bool o NaN si no está cargada)
    """  
       # Copias para no modificar los originales
    a = afip_df.copy()
    b = sistem_df.copy()

    # --- Normalizar claves ---
    a['Factura'] = a['Factura'].astype(str).str.strip()
    b['FACTURA'] = b['FACTURA'].astype(str).str.strip()

    # --- Merge por clave ---
    merged = a.merge(
        b[['FACTURA', 'NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'TOTAL_NO_GRAVADO']],
        left_on='Factura',
        right_on='FACTURA',
        how='left',
        suffixes=('', '_sistema')
    )

    # --- Columna de existencia ---
    merged['loaded'] = ~merged['FACTURA'].isna()

    # --- Forzar tipos numéricos y calcular diferencias ---
    for col in ['NETO 10.5', 'IVA 10.5', 'NETO 21', 'IVA 21', 'TOTAL_NO_GRAVADO']:
        merged[col] = pd.to_numeric(merged[col], errors='coerce')
        merged[f'{col}_sistema'] = pd.to_numeric(merged[f'{col}_sistema'], errors='coerce')
        merged[f'diff_{col}'] = abs(merged[col] - merged[f'{col}_sistema'])

    # --- Evaluar si las diferencias son menores o iguales a la tolerancia ---
    merged['totales_ok'] = merged[[f'diff_{c}' for c in ['NETO 10.5','IVA 10.5','NETO 21','IVA 21','TOTAL_NO_GRAVADO']]].max(axis=1) <= tolerancia

    # --- Si no está cargada, totales_ok = NaN ---
    merged.loc[~merged['loaded'], 'totales_ok'] = np.nan

    # --- Logs ---
    no_cargadas = merged[~merged['loaded']]
    mal_cargadas = merged[(merged['loaded']) & (~merged['totales_ok'].fillna(False))]

    # Facturas no cargadas
    if len(no_cargadas) > 0:
        print(f"⚠️  {len(no_cargadas)} facturas no están cargadas en el sistema.")
    else:
        print("✅ Todas las facturas AFIP están cargadas en el sistema.")

    # Facturas cargadas pero con error en totales
    for factura in mal_cargadas['Factura']:
        print(f"❌ La factura {factura} no está cargada correctamente (diferencia en totales).")

    # --- Filtrar solo las facturas correctamente cargadas ---
    resultado = merged.loc[~merged['loaded'], a.columns[:9]].copy()


    print(f"✅ {len(resultado)} facturas correctamente cargadas y listas para procesar.")

    return resultado
