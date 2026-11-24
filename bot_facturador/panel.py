"""Panel local y bandeja de órdenes del facturador. Iniciar con python -m bot_facturador.panel."""
import csv
import io
import json
import mimetypes
import re
import sqlite3
import unicodedata
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo
from datetime import datetime
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / ".local" / "facturacion.sqlite"
ASSETS = {"index.html", "panel.css", "panel.js", "solicitud.js", "clientes.js", "iva.js", "arancia-logo.png"}
IVA_SYNC_LOCK = Lock()
RATES = {"no gravado": 0, "exento": 0, "10,5%": 105, "21%": 210}


def connect():
    DATABASE.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS clientes (cuit TEXT PRIMARY KEY, razon_social TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ordenes (
            id TEXT PRIMARY KEY, creada TEXT DEFAULT CURRENT_TIMESTAMP,
            estado TEXT DEFAULT 'pendiente', contenido TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resumen_iva (
            periodo TEXT PRIMARY KEY, contenido TEXT NOT NULL,
            actualizado TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    with db:
        db.execute("INSERT OR IGNORE INTO clientes(cuit,razon_social) VALUES (?,?)", ("11111111", "Cliente de prueba"))
    return db


def import_clients(db, raw):
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";" if ";" in text.splitlines()[0] else ",")
    def normalize(name):
        return unicodedata.normalize("NFKD", name.strip().lower()).encode("ascii", "ignore").decode().replace(" ", "_")
    reader.fieldnames = [normalize(name) for name in reader.fieldnames or []]
    if not {"razon_social", "cuit"}.issubset(reader.fieldnames):
        raise ValueError("El CSV debe incluir razon_social y cuit.")
    clients = {}
    for number, row in enumerate(reader, 2):
        cuit = re.sub(r"[- ]", "", row["cuit"] or "")
        name = (row["razon_social"] or "").strip()
        if not re.fullmatch(r"[0-9]{11}", cuit) or not name or (cuit in clients and clients[cuit] != name):
            raise ValueError(f"Revisá el CUIT y la razón social en la fila {number}.")
        clients[cuit] = name
    if not clients:
        raise ValueError("El archivo está vacío.")
    with db:
        db.executemany("INSERT INTO clientes VALUES (?,?) ON CONFLICT(cuit) DO UPDATE SET razon_social=excluded.razon_social", clients.items())
    return {"cantidad": len(clients)}


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def queue_order(db, data):
    order_id = str(UUID(data["id"]))
    customer = db.execute("SELECT razon_social FROM clientes WHERE cuit=?", (data["cuit"],)).fetchone()
    if not customer or data["moneda"] not in ("ARS", "USD") or not isinstance(data["conceptos"], list) or not data["conceptos"]:
        raise ValueError("Revisá el cliente, la moneda y los conceptos.")
    from datetime import date
    invoice_type = data.get("tipo_factura")
    condition = data.get("condicion_iva")
    document_type = data.get("tipo_doc")
    document_number = data.get("num_doc")
    allowed = {
        "A": {"responsable inscripto", "responsable monotributo"},
        "B": {"consumidor final", "sujeto exento"},
    }
    if invoice_type not in allowed or condition not in allowed[invoice_type]:
        raise ValueError("La condición fiscal no corresponde al tipo de factura.")
    if document_type not in ("cuit", "dni") or (
        invoice_type == "A" and document_type != "cuit"
    ):
        raise ValueError("Revisá el tipo de documento.")
    if not isinstance(document_number, str) or not re.fullmatch(
        r"[0-9]{11}" if document_type == "cuit" else r"[0-9]{7,8}",
        document_number,
    ):
        if document_number != "11111111" or data["cuit"] != "11111111":
            raise ValueError("Revisá el número de documento.")
    point = data.get("punto_venta")
    if not isinstance(point, str) or not re.fullmatch(r"[0-9]+", point) or int(point) == 0:
        raise ValueError("Revisá el punto de venta.")
    dates = {}
    date_fields = {
        "fecha_emision": "fecha_emision",
        "servicio_desde": "servicio_desde",
        "servicio_hasta": "servicio_hasta",
        "vencimiento_pago": "vencimiento_pago",
    }
    for name in date_fields:
        value = data.get(name)
        if value:
            try:
                dates[name] = date.fromisoformat(value)
            except (TypeError, ValueError) as error:
                raise ValueError("Revisá las fechas de la factura.") from error
    if not dates:
        today = datetime.now(ZoneInfo("Europe/Madrid")).date()
        dates = {name: today for name in date_fields}
    if len(dates) != len(date_fields):
        raise ValueError("Completá todas las fechas de la factura.")
    if dates:
        if dates["servicio_desde"] > dates["servicio_hasta"] or dates["vencimiento_pago"] < dates["fecha_emision"]:
            raise ValueError("Revisá el período del servicio y el vencimiento.")
        minimum = date(2026, 10, 31) if invoice_type == "A" else date(2026, 10, 30)
        if point == "2" and dates["fecha_emision"] < minimum:
            raise ValueError("La fecha de emisión es anterior a la admitida.")
    address = data.get("direccion", "")
    if not isinstance(address, str):
        raise ValueError("Revisá la dirección.")
    email = data.get("correo_entrega")
    if (
        not isinstance(email, str)
        or len(email) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        raise ValueError("Revisá el correo donde recibir la factura.")
    items = []
    groups = {}
    subtotal = taxes = 0
    for line in data["conceptos"]:
        description = line["concepto"].strip()
        amount = line["precio"]
        rate = line["iva"]
        if not description or rate not in RATES or not re.fullmatch(r"[0-9]{1,14}\.[0-9]{2}", amount):
            raise ValueError("Revisá el concepto, su importe y su IVA.")
        cents = int(amount.replace(".", ""))
        if cents < 1:
            raise ValueError("El monto debe ser positivo.")
        tax = (cents * RATES[rate] + 500) // 1000
        items.append({"concepto": description, "precio": money(cents), "iva": rate, "importe_iva": money(tax)})
        group = groups.setdefault(rate, [0, 0])
        group[0] += cents
        group[1] += tax
        subtotal += cents
        taxes += tax
    order = {"id": order_id, "cliente": {"razon_social": customer[0], "condicion_iva": condition, "tipo_doc": document_type, "num_doc": document_number, "direccion": address.strip()},
                          "tipo_factura": invoice_type, "punto_venta": point,
                          "fecha_emision": dates["fecha_emision"].strftime("%d/%m/%Y") if dates else None,
                          "servicio_desde": dates["servicio_desde"].strftime("%d/%m/%Y") if dates else None,
                          "servicio_hasta": dates["servicio_hasta"].strftime("%d/%m/%Y") if dates else None,
                          "vencimiento_pago": dates["vencimiento_pago"].strftime("%d/%m/%Y") if dates else None,
                          "moneda": data["moneda"], "correo_entrega": email, "conceptos": items, "neto": money(subtotal),
                          "iva_total": money(taxes), "total": money(subtotal + taxes)}
    order["desglose_iva"] = [{"iva": rate, "base": money(base), "importe_iva": money(tax)}
                             for rate, (base, tax) in groups.items()]
    if data["moneda"] == "USD":
        fx = data.get("tipo_cambio", "")
        if not isinstance(fx, str) or not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,6})?", fx):
            raise ValueError("Tipo de cambio inválido.")
        whole, _, fraction = fx.partition(".")
        millionths = int(whole + fraction.ljust(6, "0"))
        if millionths == 0:
            raise ValueError("El tipo de cambio debe ser positivo.")
        order["tipo_cambio"] = fx
        order["total_ars"] = money(((subtotal + taxes) * millionths + 500000) // 1000000)
    payload = json.dumps(order, ensure_ascii=False)
    with db:
        db.execute(
            "INSERT OR IGNORE INTO ordenes(id,estado,contenido) VALUES (?,?,?)",
            (order_id, "pendiente" if dates else "incompleta", payload),
        )
        if db.execute("SELECT contenido FROM ordenes WHERE id=?", (order_id,)).fetchone()[0] != payload:
            raise ValueError("El identificador ya corresponde a otra orden.")
    return {"id": order_id, "estado": "pendiente" if dates else "incompleta"}


class Panel(BaseHTTPRequestHandler):
    def answer(self, body, mime="application/json", status=200):
        if mime == "application/json":
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            return self.send_error(403)
        if self.path == "/api/iva":
            with closing(connect()) as db:
                rows = db.execute("SELECT contenido, actualizado FROM resumen_iva ORDER BY periodo DESC")
                return self.answer([
                    {**json.loads(content), "actualizado": updated}
                    for content, updated in rows
                ])
        if self.path == "/api/clientes":
            with closing(connect()) as db:
                rows = db.execute("SELECT cuit,razon_social FROM clientes ORDER BY razon_social COLLATE NOCASE")
                return self.answer([{"cuit": c, "nombre": n} for c, n in rows])
        name = "index.html" if self.path == "/" else self.path[1:]
        if name in ASSETS:
            return self.answer((ROOT / name).read_bytes(), mimetypes.guess_type(name)[0] or "application/octet-stream")
        self.send_error(404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get("Origin") != "http://" + self.headers["Host"]:
            return self.send_error(403)
        if self.path == "/api/iva/actualizar":
            if not IVA_SYNC_LOCK.acquire(blocking=False):
                return self.answer({"error": "Ya hay una actualización en curso."}, status=409)
            try:
                from bot_carga.calculo_iva import fetch_monthly_records
                records = fetch_monthly_records()
                with closing(connect()) as db, db:
                    db.executemany(
                        """INSERT INTO resumen_iva(periodo,contenido,actualizado)
                           VALUES (?,?,CURRENT_TIMESTAMP)
                           ON CONFLICT(periodo) DO UPDATE SET
                           contenido=excluded.contenido,
                           actualizado=CURRENT_TIMESTAMP""",
                        [(row["periodo"], json.dumps(row, ensure_ascii=False)) for row in records],
                    )
                return self.answer({"periodos_actualizados": len(records)})
            except Exception:
                return self.answer(
                    {"error": "No se pudo leer Cálculo de IVA. Revisá el acceso y la estructura de la página."},
                    status=502,
                )
            finally:
                IVA_SYNC_LOCK.release()
        if self.path not in ("/api/clientes", "/api/ordenes"):
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 5_000_000:
                raise ValueError("El archivo debe tener contenido y pesar menos de 5 MB.")
            raw = self.rfile.read(length)
            with closing(connect()) as db:
                result = import_clients(db, raw) if self.path == "/api/clientes" else queue_order(db, json.loads(raw))
            self.answer(result)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, csv.Error):
            self.answer({"error": "Revisá el CSV (UTF-8, razón social y CUIT de 11 dígitos) o los datos de la orden."}, status=400)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pendientes", action="store_true", help="Leer órdenes pendientes como JSON.")
    if parser.parse_args().pendientes:
        with closing(connect()) as db:
            rows = db.execute("SELECT contenido FROM ordenes WHERE estado='pendiente' ORDER BY creada,id")
            print(json.dumps([json.loads(row[0]) for row in rows], ensure_ascii=False, indent=2))
    else:
        ThreadingHTTPServer(("127.0.0.1", 8765), Panel).serve_forever()
