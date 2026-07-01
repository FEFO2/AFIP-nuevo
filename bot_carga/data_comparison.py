import pandas as pd


def _print_comparison_summary(*, total_afip: int, pendientes: int, con_diferencias: int) -> None:
    if pendientes > 0:
        print(f"Hay {pendientes} facturas pendientes de carga en el sistema.")
    else:
        print("No hay facturas pendientes de carga.")

    if con_diferencias > 0:
        print(f"Hay {con_diferencias} facturas cargadas con diferencias en los importes.")
    else:
        print("No se detectaron diferencias de importes en las facturas ya cargadas.")

    print(f"Resultado: {pendientes} facturas pendientes sobre {total_afip} facturas AFIP.")


def comparar_facturas_venta(afip_df, sistem_df, tolerancia=1.0):
    """
    Compara las facturas de AFIP con las cargadas en el sistema.

    Parametros:
        afip_df (pd.DataFrame): dataset con facturas AFIP
        sistem_df (pd.DataFrame): dataset con facturas del sistema
        tolerancia (float): diferencia maxima aceptable en totales
    """
    a = afip_df.copy()
    b = sistem_df.copy()

    a["Factura"] = a["Factura"].astype(str).str.strip()
    b["FACTURA"] = b["FACTURA"].astype(str).str.strip()

    merged = a.merge(
        b[["FACTURA", "TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]],
        left_on="Factura",
        right_on="FACTURA",
        how="left",
        suffixes=("", "_sistema"),
    )

    merged["loaded"] = ~merged["FACTURA"].isna()

    for col in ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
        merged[f"{col}_sistema"] = pd.to_numeric(merged[f"{col}_sistema"], errors="coerce")
        merged[f"diff_{col}"] = abs(merged[col] - merged[f"{col}_sistema"])

    merged["totales_ok"] = pd.array(
        merged[[f"diff_{c}" for c in ["TOTAL_10.5", "TOTAL_21", "TOTAL_NO_GRAVADO"]]].max(axis=1)
        <= tolerancia,
        dtype="boolean",
    )
    merged.loc[~merged["loaded"], "totales_ok"] = pd.NA

    no_cargadas = merged[~merged["loaded"]]
    mal_cargadas = merged[(merged["loaded"]) & merged["totales_ok"].eq(False)]

    for factura in mal_cargadas["Factura"]:
        print(f"La factura {factura} no esta cargada correctamente (diferencia en totales).")

    resultado = merged.loc[~merged["loaded"], a.columns].copy()

    _print_comparison_summary(
        total_afip=len(a),
        pendientes=len(no_cargadas),
        con_diferencias=len(mal_cargadas),
    )

    return resultado


def comparar_facturas_compra(afip_df, sistem_df, tolerancia=1.0):
    """
    Compara las facturas de AFIP con las cargadas en el sistema.

    Parametros:
        afip_df (pd.DataFrame): dataset con facturas AFIP
        sistem_df (pd.DataFrame): dataset con facturas del sistema
        tolerancia (float): diferencia maxima aceptable en totales
    """
    a = afip_df.copy()
    b = sistem_df.copy()

    a["Factura"] = a["Factura"].astype(str).str.strip()
    b["FACTURA"] = b["FACTURA"].astype(str).str.strip()

    merged = a.merge(
        b[["FACTURA", "NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"]],
        left_on="Factura",
        right_on="FACTURA",
        how="left",
        suffixes=("", "_sistema"),
    )

    merged["loaded"] = ~merged["FACTURA"].isna()

    for col in ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce")
        merged[f"{col}_sistema"] = pd.to_numeric(merged[f"{col}_sistema"], errors="coerce")
        merged[f"diff_{col}"] = abs(merged[col] - merged[f"{col}_sistema"])

    merged["totales_ok"] = pd.array(
        merged[
            [f"diff_{c}" for c in ["NETO 10.5", "IVA 10.5", "NETO 21", "IVA 21", "TOTAL_NO_GRAVADO"]]
        ].max(axis=1)
        <= tolerancia,
        dtype="boolean",
    )
    merged.loc[~merged["loaded"], "totales_ok"] = pd.NA

    no_cargadas = merged[~merged["loaded"]]
    mal_cargadas = merged[(merged["loaded"]) & merged["totales_ok"].eq(False)]

    for factura in mal_cargadas["Factura"]:
        print(f"La factura {factura} no esta cargada correctamente (diferencia en totales).")

    resultado = merged.loc[~merged["loaded"], a.columns].copy()

    _print_comparison_summary(
        total_afip=len(a),
        pendientes=len(no_cargadas),
        con_diferencias=len(mal_cargadas),
    )

    return resultado
