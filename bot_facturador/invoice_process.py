import argparse
import csv
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    Locator,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from pypdf import PdfReader

from afip_common.config import get_required_env as _get_required_env
from afip_common.config import load_environment

DOWNLOADS_DIR = Path.home() / "Downloads" / "AFIP_Facturas"
DEFAULT_POINT_OF_SALE = "2"
MIN_INVOICE_DATE = {
    "A": datetime(2026, 10, 31),
    "B": datetime(2026, 10, 30),
}

CONDICION_IVA_MAP = {
    "responsable inscripto": "1",
    "responsable monotributo": "6",
    "monotributista": "6",
    "consumidor final": "5",
    "sujeto exento": "4",
}

CONDICIONES_POR_TIPO = {
    "A": {"responsable inscripto", "responsable monotributo", "monotributista"},
    "B": {"consumidor final", "sujeto exento"},
}

TIPO_DOC_MAP = {
    "cuit": "80",
    "dni": "96",
}

TIPO_IVA_MAP = {
    "no gravado": "1",
    "no grav": "1",
    "exento": "2",
    "10,5%": "4",
    "10.5%": "4",
    "21%": "5",
}

REQUIRED_COLUMNS = {
    "condicion_iva",
    "tipo_doc",
    "num_doc",
    "concepto",
    "precio",
    "iva",
}

CONSUMIDOR_FINAL_COLUMNS = {
    "monto (ars)",
    "razon social",
    "categoria",
    "column 10",
    "doc",
}
CONSUMIDOR_FINAL_CONCEPTO = "INTERMEDIACIÓN DE SERVICIOS TURÍSTICOS"
CONSUMIDOR_FINAL_CONFIG = {
    "_lote_protegido": "consumidor-final-octubre-2026",
    "_tipo_factura": "B",
    "_punto_venta": "2",
    "_moneda": "ARS",
    "_fecha_emision": "30/10/2026",
}
ESTADOS_TERMINALES = {"emitida", "omitida"}


class ReceptorNoVerificado(RuntimeError):
    pass


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def cargar_facturas(csv_path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with csv_path.open("r", encoding=encoding, newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                columnas = {normalizar_texto(name) for name in (reader.fieldnames or [])}
                formato_normal = REQUIRED_COLUMNS <= columnas
                formato_consumidor_final = CONSUMIDOR_FINAL_COLUMNS <= columnas
                if not formato_normal and not formato_consumidor_final:
                    faltantes = sorted(REQUIRED_COLUMNS - columnas)
                    raise ValueError(
                        f"Faltan columnas requeridas en {csv_path.name}: {', '.join(faltantes)}"
                    )
                facturas = []
                for fila in reader:
                    if None in fila:
                        raise ValueError(f"Fila con columnas de más en {csv_path.name}.")
                    datos = {normalizar_texto(k): (v or "").strip() for k, v in fila.items() if k}
                    if formato_consumidor_final:
                        factura = {
                            "condicion_iva": datos["categoria"],
                            "tipo_doc": datos["column 10"],
                            "num_doc": datos["doc"],
                            "receptor": datos["razon social"],
                            "concepto": CONSUMIDOR_FINAL_CONCEPTO,
                            "precio": datos["monto (ars)"],
                            "iva": "exento",
                            "direccion": "",
                            **CONSUMIDOR_FINAL_CONFIG,
                        }
                    else:
                        factura = datos
                    facturas.append(factura)
                return facturas
        except UnicodeDecodeError:
            continue

    raise ValueError(f"No se pudo leer {csv_path.name} con las codificaciones esperadas.")


def obtener_codigo(valor: str, opciones: dict[str, str], campo: str) -> str:
    codigo = opciones.get(normalizar_texto(valor))
    if codigo is None:
        raise ValueError(f"Valor no soportado para {campo}: {valor}")
    return codigo


def normalizar_fecha(valor: str, campo: str) -> tuple[datetime, str]:
    try:
        fecha = datetime.strptime(valor, "%d/%m/%Y")
    except ValueError as exception:
        raise ValueError(
            f"{campo} debe ser una fecha válida con formato DD/MM/AAAA."
        ) from exception
    return fecha, fecha.strftime("%d/%m/%Y")


def normalizar_importe(valor: str) -> Decimal:
    texto = valor.strip()
    if not re.fullmatch(r"\d[\d.,]*", texto):
        raise ValueError(f"Importe no válido: {valor}")
    if "," in texto and "." in texto:
        decimal = "," if texto.rfind(",") > texto.rfind(".") else "."
        miles = "." if decimal == "," else ","
        texto = texto.replace(miles, "").replace(decimal, ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        importe = Decimal(texto)
    except InvalidOperation as exception:
        raise ValueError(f"Importe no válido: {valor}") from exception
    if importe <= 0 or max(0, -importe.as_tuple().exponent) > 2:
        raise ValueError(f"El importe debe ser positivo y tener como máximo dos decimales: {valor}")
    return importe


def normalizar_documento(valor: str, tipo: str) -> str:
    documento = re.sub(r"[.\s-]", "", valor)
    if not documento.isdigit():
        raise ValueError(f"El {tipo.upper()} debe contener únicamente números.")
    if tipo == "cuit" and len(documento) != 11:
        raise ValueError("El CUIT debe tener 11 dígitos.")
    if tipo == "dni" and len(documento) not in {7, 8}:
        raise ValueError("El DNI debe tener 7 u 8 dígitos.")
    return documento


def _configuracion_protegida(facturas: list[dict[str, str]]) -> dict[str, str] | None:
    configuradas = [factura for factura in facturas if factura.get("_lote_protegido")]
    if not configuradas:
        return None
    if len(configuradas) != len(facturas):
        raise ValueError("El CSV mezcla filas protegidas con filas de otro formato.")
    for campo, esperado in CONSUMIDOR_FINAL_CONFIG.items():
        if any(factura.get(campo) != esperado for factura in facturas):
            raise ValueError(f"La configuración protegida del lote no coincide en {campo}.")
    return CONSUMIDOR_FINAL_CONFIG


def _verificar_bloqueo_lote(
    facturas: list[dict[str, str]],
    *,
    invoice_type: str,
    point_of_sale: str,
    currency: str,
    invoice_date: str,
) -> None:
    configuracion = _configuracion_protegida(facturas)
    if configuracion is None:
        return
    recibida = {
        "_tipo_factura": invoice_type,
        "_punto_venta": point_of_sale,
        "_moneda": currency,
        "_fecha_emision": invoice_date,
    }
    errores = [
        f"{campo[1:]}={valor} (debe ser {configuracion[campo]})"
        for campo, valor in recibida.items()
        if valor != configuracion[campo]
    ]
    if errores:
        raise ValueError(
            "LOTE BLOQUEADO: estas facturas solo pueden emitirse como Factura B, "
            "punto de venta 2, ARS y fecha 30/10/2026. " + "; ".join(errores)
        )


def _documento_oculto(documento: str) -> str:
    limpio = re.sub(r"\D", "", documento)
    return f"****{limpio[-4:]}" if limpio else "(vacío)"


def _registrar_omision(
    *,
    indice: int,
    factura: dict[str, str],
    fila_estado: dict[str, Any],
    motivo: str,
    estado_path: Path,
    estado: dict[str, Any],
    review_only: bool,
) -> None:
    print(f"Fila {indice + 1} omitida ({_documento_oculto(factura.get('num_doc', ''))}): {motivo}.")
    if not review_only:
        fila_estado.clear()
        fila_estado.update({"estado": "omitida", "motivo": motivo})
        _guardar_estado(estado_path, estado)


def _motivo_rechazo_documento(page: Page) -> str | None:
    texto = _texto_resumen(page.locator("body").inner_text())
    indicadores = (
        "documento ingresado no es valido",
        "documento no valido",
        "dni no valido",
        "cuit no valida",
        "cuit invalida",
        "no se encontro la persona",
        "persona no encontrada",
        "documento inexistente",
        "no existe el documento",
    )
    referencia_documento = any(
        termino in texto for termino in ("documento", "dni", "cuit", "persona", "padron")
    )
    rechazo = any(
        termino in texto
        for termino in (
            "no valido",
            "invalido",
            "invalida",
            "incorrecto",
            "no encontrado",
            "no encontrada",
            "no existe",
            "inexistente",
            "rechazado",
            "no pudo verificar",
        )
    )
    if any(indicador in texto for indicador in indicadores) or (referencia_documento and rechazo):
        return "ARCA rechazó o no pudo verificar el documento"
    return None


def _volver_menu_principal(page: Page) -> None:
    boton = page.get_by_role("button", name="Menú Principal")
    boton.wait_for(state="visible", timeout=5_000)
    boton.click()
    page.get_by_role("button", name="Generar Comprobantes").wait_for(state="visible")


def confirmar_lote(
    *,
    invoice_type: str,
    invoice_date: str,
    service_from: str,
    service_to: str,
    payment_due: str,
    point_of_sale: str,
    currency: str,
    csv_path: Path,
    total: int,
    review_only: bool,
    batch_id: str,
) -> None:
    accion = "REVISAR" if review_only else "EMITIR"
    token = f"{accion} {invoice_type}-{point_of_sale} {currency} {invoice_date} {total} {batch_id}"
    print(
        f"\n=== CONFIRMAR {accion} ===\n"
        f"Tipo: Factura {invoice_type}\n"
        f"Punto de venta: {point_of_sale}\n"
        f"Moneda: {currency}\n"
        f"Fecha de emisión: {invoice_date}\n"
        f"Período del servicio: {service_from} - {service_to}\n"
        f"Vencimiento del pago: {payment_due}\n"
        f"CSV: {csv_path.resolve()}\n"
        f"Comprobantes: {total}\n"
        f"Lote: {batch_id}"
    )
    if input(f"Escribe '{token}' para continuar: ").strip() != token:
        raise RuntimeError(f"{accion.capitalize()} cancelada: el lote no fue confirmado.")


def rellenar_fecha(locator: Locator, fecha: str, campo: str) -> None:
    locator.fill(fecha)
    locator.press("Tab")
    valor_actual = locator.input_value().strip()
    if valor_actual != fecha:
        raise RuntimeError(
            f"ARCA dejó {campo} como {valor_actual or 'vacío'}; se esperaba {fecha}."
        )


def esperar_nombre_receptor(page: Page, nombre: str) -> None:
    try:
        page.wait_for_function(
            """
            esperado => {
                const normalizar = texto => (texto || "").normalize("NFD")
                    .replace(/[\u0300-\u036f]/g, "").toLowerCase();
                const tokens = normalizar(esperado).match(/[a-z0-9]+/g) || [];
                const valores = [...document.querySelectorAll("input, textarea")]
                    .map(elemento => elemento.value).join(" ");
                const texto = normalizar(`${document.body.innerText} ${valores}`);
                return tokens.length > 0 && tokens.every(token => texto.includes(token));
            }
            """,
            arg=nombre,
            timeout=15_000,
        )
    except PlaywrightTimeoutError as exception:
        raise ReceptorNoVerificado(
            "ARCA no devolvió el nombre esperado para el documento"
        ) from exception


def _texto_resumen(texto: str) -> str:
    return " ".join(normalizar_texto(texto).split())


def _exigir_campo(
    texto: str, etiquetas: tuple[str, ...], valores: tuple[str, ...], campo: str
) -> None:
    for etiqueta in etiquetas:
        etiqueta = _texto_resumen(etiqueta)
        for valor in valores:
            patron = rf"{re.escape(etiqueta)}.{{0,160}}{re.escape(_texto_resumen(valor))}"
            if re.search(patron, texto):
                return
    raise RuntimeError(f"El resumen de ARCA no confirma correctamente {campo}.")


def _exigir_nombre_receptor(texto: str, nombre: str) -> None:
    esperado = set(re.findall(r"[a-z0-9]+", _texto_resumen(nombre)))
    for etiqueta in ("razon social", "apellido y nombre", "nombre y apellido", "receptor"):
        coincidencia = re.search(rf"{re.escape(etiqueta)}(.{{0,200}})", texto)
        if coincidencia:
            encontrado = set(re.findall(r"[a-z0-9]+", coincidencia.group(1)))
            if esperado <= encontrado:
                return
    raise RuntimeError("El resumen de ARCA no confirma correctamente el nombre del receptor.")


def _variantes_importe(importe: Decimal) -> tuple[str, ...]:
    normal = f"{importe:.2f}"
    miles_us = f"{importe:,.2f}"
    miles_ar = miles_us.replace(",", "_").replace(".", ",").replace("_", ".")
    return normal, normal.replace(".", ","), miles_us, miles_ar


def _variantes_documento(documento: str) -> tuple[str, ...]:
    if len(documento) == 11:
        return documento, f"{documento[:2]}-{documento[2:10]}-{documento[10]}"
    if len(documento) in {7, 8}:
        return documento, f"{int(documento):,}".replace(",", ".")
    return (documento,)


def _variantes_iva(iva: str) -> tuple[str, ...]:
    if not iva.endswith("%"):
        return (iva,)
    try:
        valor = Decimal(iva[:-1].replace(",", "."))
    except InvalidOperation:
        return (iva,)
    return iva, f"{valor:.2f}%", f"{valor:.2f}%".replace(".", ",")


def verificar_resumen(
    page: Page,
    *,
    invoice_type: str,
    point_of_sale: str,
    currency: str,
    invoice_date: str,
    service_from: str,
    service_to: str,
    payment_due: str,
    factura: dict[str, str],
) -> None:
    texto = _texto_resumen(page.locator("body").inner_text())
    _exigir_campo(
        texto, ("tipo de comprobante", "comprobante"), (f"factura {invoice_type}",), "el tipo"
    )
    _exigir_campo(texto, ("punto de venta",), (point_of_sale,), "el punto de venta")
    if currency == "USD":
        _exigir_campo(texto, ("moneda",), ("usd", "dolar", "dolares"), "la moneda")
    elif re.search(r"\b(?:usd|dolar|dolares)\b", texto):
        raise RuntimeError("El resumen de ARCA muestra moneda extranjera en un lote ARS.")
    etiquetas_fecha = ("fecha del comprobante", "fecha de emision")
    if any(etiqueta in texto for etiqueta in etiquetas_fecha):
        _exigir_campo(texto, etiquetas_fecha, (invoice_date,), "la fecha de emisión")
    _exigir_campo(texto, ("desde",), (service_from,), "la fecha desde")
    _exigir_campo(texto, ("hasta",), (service_to,), "la fecha hasta")
    _exigir_campo(texto, ("vto", "vencimiento"), (payment_due,), "el vencimiento")
    try:
        _exigir_campo(
            texto,
            ("cuit", "dni", "documento"),
            _variantes_documento(factura["num_doc"]),
            "el receptor",
        )
        if factura.get("receptor"):
            _exigir_nombre_receptor(texto, factura["receptor"])
    except RuntimeError as exception:
        raise ReceptorNoVerificado(str(exception)) from exception
    _exigir_campo(
        texto,
        ("descripcion", "concepto", "producto/servicio"),
        (factura["concepto"],),
        "el concepto",
    )
    _exigir_campo(
        texto,
        ("precio", "importe"),
        _variantes_importe(normalizar_importe(factura["precio"])),
        "el importe",
    )
    variantes_iva = _variantes_iva(factura["iva"])
    if "alicuota iva" in texto:
        if not any(_texto_resumen(valor) in texto for valor in variantes_iva):
            raise RuntimeError("El resumen de ARCA no confirma correctamente el IVA.")
    else:
        _exigir_campo(texto, ("iva", "alicuota"), variantes_iva, "el IVA")


def _guardar_estado(path: Path, estado: dict[str, Any]) -> None:
    temporal = path.with_suffix(path.suffix + ".tmp")
    contenido = json.dumps(estado, indent=2, ensure_ascii=False)
    temporal.write_text(contenido, encoding="utf-8")
    try:
        temporal.replace(path)
    except PermissionError:
        # shortcut: Windows puede bloquear renombres atómicos en carpetas protegidas.
        path.write_text(contenido, encoding="utf-8")
        temporal.unlink()


def _cargar_estado(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"runs": {}}
    try:
        estado = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exception:
        raise RuntimeError(f"No se puede leer el diario de facturación {path}.") from exception
    if not isinstance(estado, dict) or not isinstance(estado.get("runs"), dict):
        raise RuntimeError(f"El diario de facturación {path} no tiene un formato válido.")
    return estado


def _id_ejecucion(csv_path: Path, parametros: dict[str, str]) -> str:
    huella = hashlib.sha256(csv_path.read_bytes())
    huella.update(json.dumps(parametros, sort_keys=True).encode())
    return huella.hexdigest()


def _resolver_confirmaciones_inciertas(path: Path, estado: dict[str, Any]) -> None:
    for execution_id, ejecucion in estado["runs"].items():
        for indice, fila in enumerate(ejecucion.get("filas", [])):
            if fila.get("estado") != "confirmando":
                continue
            parametros = ejecucion.get("parametros", {})
            pdf = path.parent / f"{parametros.get('tipo')}_{execution_id}_{indice + 1}.pdf"
            if pdf.is_file() and not fila.get("pdf"):
                fila["pdf"] = str(pdf.resolve())
                _guardar_estado(path, estado)
            print(
                "\n=== CONFIRMACIÓN INCIERTA ===\n"
                f"Tipo: {parametros.get('tipo')} | Punto: {parametros.get('punto_venta')} | "
                f"Fecha: {parametros.get('fecha')} | Fila: {indice + 1}\n"
                "Comprueba en ARCA si se emitió antes de responder."
            )
            respuesta = input(
                "Escribe NO_EMITIDA o EMITIDA <00002-00000001> <CAE de 14 dígitos>: "
            ).strip()
            if respuesta == "NO_EMITIDA":
                if fila.get("pdf"):
                    raise RuntimeError(
                        "Hay un PDF guardado para esta fila; revísalo antes de resolverla."
                    )
                fila["estado"] = "pendiente"
            else:
                emitida = re.fullmatch(r"EMITIDA\s+(\d{4,5}-\d{8})\s+(\d{14})", respuesta)
                if not emitida:
                    raise RuntimeError(
                        "La confirmación incierta sigue bloqueada; no se modificó el diario."
                    )
                fila.update(
                    {
                        "estado": "emitida",
                        "numero": emitida.group(1),
                        "cae": emitida.group(2),
                    }
                )
            _guardar_estado(path, estado)


def _datos_confirmacion(texto: str) -> tuple[str, str]:
    cae = re.search(r"\bCAE\b\D{0,40}(\d{14})", texto, re.IGNORECASE)
    numero = re.search(
        r"(?:comprobante|factura|comp\.?\s*nro\.?)\D{0,50}"
        r"(\d{4,5})\s*[-–]\s*(\d{8})",
        texto,
        re.IGNORECASE,
    )
    if numero:
        numero_texto = f"{numero.group(1)}-{numero.group(2)}"
    else:
        punto = re.search(r"punto\s+de\s+venta\D{0,20}(\d{1,5})", texto, re.IGNORECASE)
        comprobante = re.search(
            r"(?:comprobante|comp\.?)\s*(?:nro\.?)?\D{0,20}(\d{1,8})",
            texto,
            re.IGNORECASE,
        )
        numero_texto = (
            f"{int(punto.group(1)):05d}-{int(comprobante.group(1)):08d}"
            if punto and comprobante
            else None
        )
    if not cae or not numero_texto:
        raise RuntimeError(
            "No se pudieron leer el número y el CAE. "
            "Revisa el comprobante manualmente antes de volver a ejecutar el bot."
        )
    return numero_texto, cae.group(1)


def run(
    playwright: Playwright,
    *,
    invoice_type: str,
    csv_path: Path,
    invoice_date: str,
    service_from: str,
    service_to: str,
    payment_due: str | None = None,
    point_of_sale: str = DEFAULT_POINT_OF_SALE,
    currency: str | None = None,
    downloads_dir: Path = DOWNLOADS_DIR,
    review_only: bool = False,
) -> None:
    if invoice_type not in {"A", "B"}:
        raise ValueError("El tipo de factura debe ser A o B.")
    invoice_day, invoice_date = normalizar_fecha(invoice_date, "fecha de emisión")
    service_from_day, service_from = normalizar_fecha(service_from, "fecha desde")
    service_to_day, service_to = normalizar_fecha(service_to, "fecha hasta")
    payment_due_day, payment_due = normalizar_fecha(
        payment_due or invoice_date, "fecha de vencimiento"
    )
    if point_of_sale == DEFAULT_POINT_OF_SALE and invoice_day < MIN_INVOICE_DATE[invoice_type]:
        minimum = MIN_INVOICE_DATE[invoice_type].strftime("%d/%m/%Y")
        raise ValueError(
            f"La Factura {invoice_type} del punto de venta {point_of_sale} no puede tener "
            f"una fecha anterior a {minimum}."
        )
    if service_from_day > service_to_day:
        raise ValueError("Las fechas deben cumplir: desde <= hasta.")
    if payment_due_day < invoice_day:
        raise ValueError("El vencimiento no puede ser anterior a la fecha de emisión.")
    facturas = cargar_facturas(csv_path)
    if not facturas:
        raise ValueError(f"{csv_path.name} no tiene filas para facturar.")
    configuracion = _configuracion_protegida(facturas)
    currency = currency or (
        configuracion["_moneda"]
        if configuracion is not None
        else ("ARS" if invoice_type == "A" else "USD")
    )
    if currency not in {"ARS", "USD"}:
        raise ValueError("La moneda debe ser ARS o USD.")
    _verificar_bloqueo_lote(
        facturas,
        invoice_type=invoice_type,
        point_of_sale=point_of_sale,
        currency=currency,
        invoice_date=invoice_date,
    )

    condiciones = {
        nombre: codigo
        for nombre, codigo in CONDICION_IVA_MAP.items()
        if nombre in CONDICIONES_POR_TIPO[invoice_type]
    }
    errores_fila: dict[int, str] = {}
    for indice, factura in enumerate(facturas):
        try:
            if not all(factura[campo] for campo in REQUIRED_COLUMNS):
                raise ValueError("hay campos obligatorios vacíos")
            obtener_codigo(factura["condicion_iva"], condiciones, "condicion_iva")
            tipo_doc = normalizar_texto(factura["tipo_doc"])
            obtener_codigo(tipo_doc, TIPO_DOC_MAP, "tipo_doc")
            if invoice_type == "A" and tipo_doc != "cuit":
                raise ValueError("la Factura A requiere un receptor identificado con CUIT")
            factura["num_doc"] = normalizar_documento(factura["num_doc"], tipo_doc)
            obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
            normalizar_importe(factura["precio"])
        except (KeyError, ValueError) as exception:
            errores_fila[indice] = str(exception)
    if errores_fila and configuracion is None:
        primera_fila = min(errores_fila)
        raise ValueError(f"Fila {primera_fila + 1}: {errores_fila[primera_fila]}")

    parametros = {
        "tipo": invoice_type,
        "punto_venta": point_of_sale,
        "moneda": currency,
        "fecha": invoice_date,
        "desde": service_from,
        "hasta": service_to,
        "vencimiento": payment_due,
    }
    estado_path = downloads_dir / "facturador_estado.json"
    estado = _cargar_estado(estado_path)
    _resolver_confirmaciones_inciertas(estado_path, estado)
    for ejecucion in estado["runs"].values():
        anteriores = ejecucion.get("parametros", {})
        if (
            anteriores.get("tipo") == invoice_type
            and anteriores.get("punto_venta") == point_of_sale
            and any(fila.get("estado") == "emitida" for fila in ejecucion.get("filas", []))
        ):
            fecha_anterior, _ = normalizar_fecha(anteriores["fecha"], "fecha registrada")
            if invoice_day < fecha_anterior:
                raise ValueError(
                    f"El diario ya registra una Factura {invoice_type} del {anteriores['fecha']} "
                    f"para el punto de venta {point_of_sale}."
                )

    execution_id = _id_ejecucion(csv_path, parametros)
    ejecucion = estado["runs"].setdefault(
        execution_id,
        {
            "parametros": parametros,
            "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "filas": [
                {
                    "estado": "pendiente",
                    "documento": factura.get("num_doc"),
                    "receptor": factura.get("receptor"),
                    "concepto": factura.get("concepto"),
                    "importe": factura.get("precio"),
                    "iva": factura.get("iva"),
                }
                for factura in facturas
            ],
        },
    )
    for indice, motivo in errores_fila.items():
        fila_estado = ejecucion["filas"][indice]
        if fila_estado.get("estado") == "pendiente":
            fila_estado.update({"estado": "omitida", "motivo": motivo})
        print(
            f"Fila {indice + 1} omitida "
            f"({_documento_oculto(facturas[indice].get('num_doc', ''))}): {motivo}."
        )
    if errores_fila and not review_only:
        downloads_dir.mkdir(parents=True, exist_ok=True)
        _guardar_estado(estado_path, estado)
    if not review_only and all(
        fila.get("estado") in ESTADOS_TERMINALES for fila in ejecucion["filas"]
    ):
        print("Este lote ya está resuelto completamente; no se hará nada.")
        return

    facturas_pendientes = sum(fila.get("estado") == "pendiente" for fila in ejecucion["filas"])
    if facturas_pendientes == 0:
        print("No quedan filas válidas para revisar o emitir.")
        return

    confirmar_lote(
        invoice_type=invoice_type,
        invoice_date=invoice_date,
        service_from=service_from,
        service_to=service_to,
        payment_due=payment_due,
        point_of_sale=point_of_sale,
        currency=currency,
        csv_path=csv_path,
        total=facturas_pendientes,
        review_only=review_only,
        batch_id=execution_id[:8],
    )

    load_environment()
    afip_url = _get_required_env("AFIP_URL")
    afip_username = _get_required_env("AFIP_USERNAME")
    afip_password = _get_required_env("AFIP_PASSWORD")

    downloads_dir.mkdir(parents=True, exist_ok=True)
    if not review_only:
        _guardar_estado(estado_path, estado)

    browser = playwright.chromium.launch(headless=False, slow_mo=800)
    context = None
    try:
        context = browser.new_context()
        page = context.new_page()

        page.goto(afip_url)
        page.get_by_role("spinbutton").fill(afip_username)
        page.get_by_role("button", name="Siguiente").click()
        page.get_by_role("textbox", name="TU CLAVE").fill(afip_password)
        page.get_by_role("button", name="Ingresar").click()

        with page.expect_popup() as page1_info:
            page.locator("a").filter(has_text="Comprobantes en línea").click()
        page1 = page1_info.value

        page1.get_by_role("button", name="ARANCIA SERVICES S.R.L.").click()

        for indice, factura in enumerate(facturas):
            fila_estado = ejecucion["filas"][indice]
            if fila_estado.get("estado") in ESTADOS_TERMINALES:
                if fila_estado["estado"] == "emitida":
                    print(f"Fila {indice + 1} ya emitida; se omite.")
                continue
            page1.get_by_role("button", name="Generar Comprobantes").click()
            page1.locator("#puntodeventa").select_option(point_of_sale)
            page1.locator("#universocomprobante").select_option(
                "10" if invoice_type == "A" else "19"
            )
            page1.get_by_role("button", name="Continuar >").click()
            page1.get_by_role("textbox", name="Fecha del Comprobante").wait_for(state="visible")

            rellenar_fecha(
                page1.get_by_role("textbox", name="Fecha del Comprobante"),
                invoice_date,
                "Fecha del Comprobante",
            )
            page1.locator("#idconcepto").select_option("2")
            if currency == "USD":
                page1.get_by_text("Moneda Extranjera").click()
            rellenar_fecha(page1.get_by_role("textbox", name="Desde"), service_from, "Desde")
            rellenar_fecha(page1.get_by_role("textbox", name="Hasta"), service_to, "Hasta")
            rellenar_fecha(
                page1.get_by_role(
                    "textbox", name=re.compile(r"Vto.*pago|vencimiento.*pago", re.IGNORECASE)
                ),
                payment_due,
                "Vencimiento del pago",
            )

            condicion_iva = obtener_codigo(factura["condicion_iva"], condiciones, "condicion_iva")
            tipo_doc = obtener_codigo(factura["tipo_doc"], TIPO_DOC_MAP, "tipo_doc")
            tipo_iva = obtener_codigo(factura["iva"], TIPO_IVA_MAP, "iva")
            direccion = factura.get("direccion", "")

            page1.get_by_role("button", name="Continuar >").click()
            page1.locator("#idivareceptor").wait_for(state="visible")
            page1.locator("#idivareceptor").select_option(condicion_iva)
            if invoice_type == "B":
                page1.locator("#idtipodocreceptor").select_option(tipo_doc)
            try:
                page1.locator("#nrodocreceptor").fill(factura["num_doc"])
                page1.locator("#nrodocreceptor").press("Tab")
                if factura.get("receptor"):
                    esperar_nombre_receptor(page1, factura["receptor"])
                page1.get_by_role("checkbox", name="Contado").wait_for(state="visible")
                if tipo_doc == "96":
                    domicilio_receptor = page1.locator("#domicilioreceptor")
                    if not domicilio_receptor.input_value().strip():
                        domicilio_receptor.fill(direccion or "-")
                page1.get_by_role("checkbox", name="Contado").check()
                page1.get_by_role("button", name="Continuar >").click()
                page1.locator("#detalle_descripcion1").wait_for(state="visible")
            except ReceptorNoVerificado as exception:
                _registrar_omision(
                    indice=indice,
                    factura=factura,
                    fila_estado=fila_estado,
                    motivo=str(exception),
                    estado_path=estado_path,
                    estado=estado,
                    review_only=review_only,
                )
                _volver_menu_principal(page1)
                continue
            except PlaywrightTimeoutError:
                motivo = _motivo_rechazo_documento(page1)
                if motivo is None:
                    raise
                _registrar_omision(
                    indice=indice,
                    factura=factura,
                    fila_estado=fila_estado,
                    motivo=motivo,
                    estado_path=estado_path,
                    estado=estado,
                    review_only=review_only,
                )
                _volver_menu_principal(page1)
                continue

            page1.locator("#detalle_descripcion1").fill(factura["concepto"])
            page1.locator("#detalle_precio1").fill(f"{normalizar_importe(factura['precio']):.2f}")
            page1.locator("#detalle_tipo_iva1").select_option(tipo_iva)

            page1.get_by_role("button", name="Continuar >").click()
            boton_confirmar_datos = page1.get_by_role(
                "button", name=re.compile(r"Confirmar\s+Datos", re.IGNORECASE)
            )
            boton_confirmar_datos.wait_for(state="visible")
            try:
                verificar_resumen(
                    page1,
                    invoice_type=invoice_type,
                    point_of_sale=point_of_sale,
                    currency=currency,
                    invoice_date=invoice_date,
                    service_from=service_from,
                    service_to=service_to,
                    payment_due=payment_due,
                    factura=factura,
                )
            except ReceptorNoVerificado:
                _registrar_omision(
                    indice=indice,
                    factura=factura,
                    fila_estado=fila_estado,
                    motivo="ARCA no confirmó la identidad del receptor en el resumen",
                    estado_path=estado_path,
                    estado=estado,
                    review_only=review_only,
                )
                _volver_menu_principal(page1)
                continue
            if review_only:
                print("Revisión completada: no se confirmó ningún comprobante.")
                return

            boton_confirmar_datos.click()
            page1.get_by_role("button", name="Confirmar", exact=True).wait_for(state="visible")
            _verificar_bloqueo_lote(
                facturas,
                invoice_type=invoice_type,
                point_of_sale=point_of_sale,
                currency=currency,
                invoice_date=invoice_date,
            )
            destino = downloads_dir / f"{invoice_type}_{execution_id}_{indice + 1}.pdf"
            if destino.exists():
                raise RuntimeError(f"No se sobrescribirá el PDF existente: {destino}")
            fila_estado["estado"] = "confirmando"
            _guardar_estado(estado_path, estado)
            page1.get_by_role("button", name="Confirmar", exact=True).click()
            page1.get_by_role("button", name="Imprimir...").wait_for(state="visible")
            with page1.expect_download() as download_info:
                page1.get_by_role("button", name="Imprimir...").click()
            download = download_info.value
            download.save_as(destino)
            fila_estado["pdf"] = str(destino.resolve())
            _guardar_estado(estado_path, estado)
            with destino.open("rb") as pdf:
                if pdf.read(5) != b"%PDF-":
                    raise RuntimeError(f"La descarga no es un PDF válido: {destino}")
            texto_pdf = PdfReader(destino).pages[0].extract_text(extraction_mode="layout")
            numero, cae = _datos_confirmacion(texto_pdf)
            if int(numero.split("-")[0]) != int(point_of_sale):
                raise RuntimeError(f"El punto de venta del PDF no coincide: {destino}")
            fila_estado.update({"estado": "emitida", "numero": numero, "cae": cae})
            _guardar_estado(estado_path, estado)
            print(f"Factura {numero}, CAE {cae}. PDF: {destino.resolve()}")

            page1.get_by_role("button", name="Menú Principal").click()
            page1.get_by_role("button", name="Generar Comprobantes").wait_for(state="visible")

    finally:
        try:
            if context is not None:
                context.close()
        finally:
            browser.close()


def main(invoice_type: str) -> int:
    parser = argparse.ArgumentParser(description=f"Emitir facturas {invoice_type} en AFIP/ARCA.")
    default_csv = "lista_fac_a.csv" if invoice_type == "A" else "lista_fac.csv"
    parser.add_argument("--csv", type=Path, default=Path(__file__).with_name(default_csv))
    parser.add_argument("--fecha", required=True, help="Fecha de emisión: DD/MM/AAAA.")
    parser.add_argument("--desde", required=True, help="Inicio del período del servicio.")
    parser.add_argument("--hasta", required=True, help="Fin del período del servicio.")
    parser.add_argument(
        "--vencimiento", help="Vencimiento del pago; por defecto usa la fecha de emisión."
    )
    parser.add_argument("--punto-venta", default=DEFAULT_POINT_OF_SALE)
    parser.add_argument(
        "--moneda",
        choices=["ARS", "USD"],
        default=None,
        help="Moneda; el lote de consumidor final de octubre usa ARS automáticamente.",
    )
    parser.add_argument(
        "--solo-revisar",
        action="store_true",
        help="Completa y valida la primera factura sin confirmarla.",
    )
    args = parser.parse_args()
    with sync_playwright() as playwright:
        run(
            playwright,
            invoice_type=invoice_type,
            csv_path=args.csv,
            invoice_date=args.fecha,
            service_from=args.desde,
            service_to=args.hasta,
            payment_due=args.vencimiento,
            point_of_sale=args.punto_venta,
            currency=args.moneda,
            review_only=args.solo_revisar,
        )
    return 0
