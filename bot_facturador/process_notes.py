from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from playwright.sync_api import Locator, Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright


DEFAULT_TIMEOUT_MS = 30_000
DEFAULT_WAIT_MS = 800
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "downloads" / "afip_facturas"

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_output_dir(path: Path | None = None) -> Path:
    output_dir = path or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def browser_mode_label(headless: bool) -> str:
    return "oculto" if headless else "visible"


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Falta la variable de entorno requerida: {name}")
    return value


def _clean_text(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def _optional_text(value: object) -> str | None:
    text = _clean_text(value)
    return text or None


def _normalize_date(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None

    for input_format in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, input_format)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text)
        return parsed.strftime("%d/%m/%Y")
    except ValueError:
        return text


def _sanitize_filename(value: str) -> str:
    clean_value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return clean_value.strip("._") or "factura"


@dataclass(frozen=True)
class AfipSettings:
    login_url: str
    portal_url: str
    cuit: str
    password: str
    company_name: str
    point_of_sale: str
    voucher_type: str
    concept: str
    recipient_vat_condition: str
    sale_condition: str
    item_vat_type: str
    quantity: str
    currency_label: str | None = None
    unit_measure: str | None = None


def load_afip_settings() -> AfipSettings:
    load_dotenv()

    return AfipSettings(
        login_url=os.getenv("AFIP_URL", "https://auth.afip.gob.ar/contribuyente_/login.xhtml"),
        portal_url=os.getenv("AFIP_PORTAL_URL", "https://portalcf.cloud.afip.gob.ar/portal/app/"),
        cuit=_get_required_env("AFIP_USERNAME"),
        password=_get_required_env("AFIP_PASSWORD"),
        company_name=os.getenv("AFIP_COMPANY_NAME", "ARANCIA SERVICES S.R.L."),
        point_of_sale=os.getenv("AFIP_INVOICE_POINT_OF_SALE", "2"),
        voucher_type=os.getenv("AFIP_INVOICE_VOUCHER_TYPE", "19"),
        concept=os.getenv("AFIP_INVOICE_CONCEPT", "2"),
        recipient_vat_condition=os.getenv("AFIP_RECIPIENT_VAT_CONDITION", "5"),
        sale_condition=os.getenv("AFIP_SALE_CONDITION", "contado"),
        item_vat_type=os.getenv("AFIP_ITEM_VAT_TYPE", "2"),
        quantity=os.getenv("AFIP_ITEM_QUANTITY", "1"),
        currency_label=_optional_text(os.getenv("AFIP_CURRENCY_LABEL", "Moneda Extranjera")),
        unit_measure=_optional_text(os.getenv("AFIP_ITEM_UNIT_MEASURE")),
    )


@dataclass(frozen=True)
class InvoiceInput:
    recipient_doc: str
    description: str
    amount: str
    issue_date: str | None = None
    company_name: str | None = None
    point_of_sale: str | None = None
    voucher_type: str | None = None
    concept: str | None = None
    recipient_vat_condition: str | None = None
    sale_condition: str | None = None
    item_vat_type: str | None = None
    quantity: str | None = None
    unit_measure: str | None = None
    currency_label: str | None = None
    service_start: str | None = None
    service_end: str | None = None
    payment_due: str | None = None


@dataclass(frozen=True)
class InvoiceResult:
    index: int
    status: str
    recipient_doc: str
    description: str
    amount: str
    pdf_path: str | None = None
    cae: str | None = None
    voucher_number: str | None = None
    error: str | None = None


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "recipient_doc": ("recipient_doc", "document_number", "cuit", "nrodocreceptor", "doc"),
    "description": ("description", "detalle", "detail", "concept_description"),
    "amount": ("amount", "importe", "price", "unit_price", "detalle_precio1"),
    "issue_date": ("issue_date", "fecha", "date", "invoice_date"),
    "company_name": ("company_name", "empresa", "company"),
    "point_of_sale": ("point_of_sale", "punto_de_venta", "puntodeventa"),
    "voucher_type": ("voucher_type", "tipo_comprobante", "universocomprobante"),
    "concept": ("concept", "idconcepto"),
    "recipient_vat_condition": ("recipient_vat_condition", "vat_condition", "idivareceptor"),
    "sale_condition": ("sale_condition", "forma_pago", "payment_condition"),
    "item_vat_type": ("item_vat_type", "vat_type", "detalle_tipo_iva1"),
    "quantity": ("quantity", "cantidad", "detalle_cantidad1"),
    "unit_measure": ("unit_measure", "medida", "detalle_medida1"),
    "currency_label": ("currency_label", "currency", "moneda"),
    "service_start": ("service_start", "fecha_desde", "service_from"),
    "service_end": ("service_end", "fecha_hasta", "service_to"),
    "payment_due": ("payment_due", "fecha_vencimiento", "due_date"),
}


def _pick_value(record: dict[str, Any], field_name: str) -> Any:
    aliases = FIELD_ALIASES[field_name]

    for alias in aliases:
        if alias in record:
            return record[alias]

    lowered_record = {key.lower(): value for key, value in record.items()}
    for alias in aliases:
        if alias.lower() in lowered_record:
            return lowered_record[alias.lower()]

    return None


def _invoice_from_record(record: dict[str, Any]) -> InvoiceInput:
    recipient_doc = _clean_text(_pick_value(record, "recipient_doc"))
    description = _clean_text(_pick_value(record, "description"))
    amount = _clean_text(_pick_value(record, "amount"))

    missing_fields = [
        field_name
        for field_name, value in (
            ("recipient_doc", recipient_doc),
            ("description", description),
            ("amount", amount),
        )
        if not value
    ]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Faltan campos obligatorios en la factura: {missing}")

    kwargs: dict[str, Any] = {
        "recipient_doc": recipient_doc,
        "description": description,
        "amount": amount,
    }

    for optional_field in (
        "issue_date",
        "company_name",
        "point_of_sale",
        "voucher_type",
        "concept",
        "recipient_vat_condition",
        "sale_condition",
        "item_vat_type",
        "quantity",
        "unit_measure",
        "currency_label",
        "service_start",
        "service_end",
        "payment_due",
    ):
        kwargs[optional_field] = _optional_text(_pick_value(record, optional_field))

    return InvoiceInput(**kwargs)


def load_invoices(input_path: Path) -> list[InvoiceInput]:
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo de entrada: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".json":
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(raw_data, dict):
            records = raw_data.get("invoices", [])
        elif isinstance(raw_data, list):
            records = raw_data
        else:
            raise ValueError("El JSON debe ser una lista o un objeto con la clave 'invoices'.")
    elif suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            records = list(csv.DictReader(csv_file))
    else:
        raise ValueError("Formato no soportado. Usa .json o .csv.")

    invoices = [_invoice_from_record(record) for record in records]
    if not invoices:
        raise ValueError("El archivo no contiene facturas para procesar.")

    return invoices


class AfipInvoiceClient:
    def __init__(self, page: Page, settings: AfipSettings, *, pause_ms: int = DEFAULT_WAIT_MS) -> None:
        self.page = page
        self.settings = settings
        self.pause_ms = pause_ms
        self.page.set_default_timeout(DEFAULT_TIMEOUT_MS)

    def login(self) -> None:
        logger.info("AFIP: abriendo login.")
        self.page.goto(self.settings.login_url, wait_until="domcontentloaded")
        self.page.get_by_role("spinbutton").fill(self.settings.cuit)
        self.page.get_by_role("button", name=re.compile(r"Siguiente", re.IGNORECASE)).click()
        password_input = self.page.get_by_role("textbox", name=re.compile(r"TU CLAVE", re.IGNORECASE))
        if password_input.count():
            password_input.fill(self.settings.password)
        else:
            self.page.locator("input[type='password']").first.fill(self.settings.password)
        self.page.get_by_role("button", name=re.compile(r"Ingresar", re.IGNORECASE)).click()
        self.page.wait_for_load_state("networkidle")
        logger.info("AFIP: sesion iniciada.")

    def create_invoice(
        self,
        invoice: InvoiceInput,
        *,
        output_dir: Path,
        preview_only: bool = False,
    ) -> InvoiceResult:
        popup = self._open_invoice_popup(invoice.company_name or self.settings.company_name)
        try:
            self._start_new_invoice(popup, invoice)
            self._fill_invoice_header(popup, invoice)
            self._fill_recipient_data(popup, invoice)
            self._fill_item_data(popup, invoice)

            if preview_only:
                self._open_confirmation_preview(popup)
                return InvoiceResult(
                    index=0,
                    status="preview",
                    recipient_doc=invoice.recipient_doc,
                    description=invoice.description,
                    amount=invoice.amount,
                )

            cae, voucher_number = self._confirm_invoice(popup)
            pdf_path = self._download_invoice_pdf(popup, invoice, output_dir)

            return InvoiceResult(
                index=0,
                status="ok",
                recipient_doc=invoice.recipient_doc,
                description=invoice.description,
                amount=invoice.amount,
                pdf_path=str(pdf_path),
                cae=cae,
                voucher_number=voucher_number,
            )
        finally:
            popup.close()

    def _open_invoice_popup(self, company_name: str) -> Page:
        logger.info("AFIP: abriendo portal de Comprobantes en linea.")
        self.page.goto(self.settings.portal_url, wait_until="networkidle")

        with self.page.expect_popup() as popup_info:
            self.page.locator("a").filter(
                has_text=re.compile(r"Comprobantes en l[i\u00ed]nea", re.IGNORECASE)
            ).first.click()

        popup = popup_info.value
        popup.set_default_timeout(DEFAULT_TIMEOUT_MS)
        popup.wait_for_load_state("networkidle")
        popup.get_by_role("button", name=re.compile(re.escape(company_name), re.IGNORECASE)).click()
        popup.get_by_role("button", name=re.compile(r"Generar Comprobantes", re.IGNORECASE)).click()
        popup.wait_for_load_state("networkidle")
        return popup

    def _start_new_invoice(self, popup: Page, invoice: InvoiceInput) -> None:
        self._select_option(popup.locator("#puntodeventa"), invoice.point_of_sale or self.settings.point_of_sale)
        self._select_option(
            popup.locator("#universocomprobante"),
            invoice.voucher_type or self.settings.voucher_type,
        )
        self._click_continue(popup)

    def _fill_invoice_header(self, popup: Page, invoice: InvoiceInput) -> None:
        self._try_fill_date(
            popup,
            invoice.issue_date,
            selectors=(
                "#fcmp",
                "#fechaComprobante",
                "input[name='fechaComprobante']",
                "input[placeholder*='dd/mm']",
            ),
            label_pattern=r"Fecha del Comprobante",
        )

        self._select_option(popup.locator("#idconcepto"), invoice.concept or self.settings.concept)

        self._try_fill_date(
            popup,
            invoice.service_start,
            selectors=("#fsd", "#fechaServicioDesde", "input[name='fechaServicioDesde']"),
            label_pattern=r"Desde",
        )
        self._try_fill_date(
            popup,
            invoice.service_end,
            selectors=("#fsh", "#fechaServicioHasta", "input[name='fechaServicioHasta']"),
            label_pattern=r"Hasta",
        )
        self._try_fill_date(
            popup,
            invoice.payment_due,
            selectors=("#fvencpago", "#fechaVtoPago", "input[name='fechaVtoPago']"),
            label_pattern=r"Vencimiento",
        )

        currency_label = invoice.currency_label or self.settings.currency_label
        if currency_label:
            self._click_text_if_visible(popup, currency_label)

        self._click_continue(popup)

    def _fill_recipient_data(self, popup: Page, invoice: InvoiceInput) -> None:
        self._select_option(
            popup.locator("#idivareceptor"),
            invoice.recipient_vat_condition or self.settings.recipient_vat_condition,
        )
        popup.locator("#nrodocreceptor").fill(invoice.recipient_doc)

        sale_condition = (invoice.sale_condition or self.settings.sale_condition).strip().lower()
        if sale_condition == "contado":
            popup.get_by_role("checkbox", name=re.compile(r"Contado", re.IGNORECASE)).check()

        self._click_continue(popup)

    def _fill_item_data(self, popup: Page, invoice: InvoiceInput) -> None:
        popup.locator("#detalle_descripcion1").fill(invoice.description)

        quantity = invoice.quantity or self.settings.quantity
        if quantity:
            popup.locator("#detalle_cantidad1").fill(quantity)

        unit_measure = invoice.unit_measure or self.settings.unit_measure
        if unit_measure and popup.locator("#detalle_medida1").count():
            self._select_option(popup.locator("#detalle_medida1"), unit_measure)

        popup.locator("#detalle_precio1").fill(invoice.amount)
        self._select_option(
            popup.locator("#detalle_tipo_iva1"),
            invoice.item_vat_type or self.settings.item_vat_type,
        )
        self._click_continue(popup)

    def _open_confirmation_preview(self, popup: Page) -> None:
        popup.get_by_role("button", name=re.compile(r"Confirmar Datos", re.IGNORECASE)).click()
        popup.wait_for_load_state("networkidle")
        popup.get_by_role("button", name=re.compile(r"Confirmar$", re.IGNORECASE)).wait_for(
            state="visible",
            timeout=DEFAULT_TIMEOUT_MS,
        )

    def _confirm_invoice(self, popup: Page) -> tuple[str | None, str | None]:
        self._open_confirmation_preview(popup)
        popup.get_by_role("button", name=re.compile(r"Confirmar$", re.IGNORECASE)).click()
        popup.wait_for_load_state("networkidle")
        page_text = popup.locator("body").inner_text()
        return self._extract_pattern(page_text, r"CAE\s*:?\s*([0-9]+)"), self._extract_pattern(
            page_text,
            r"([0-9]{1,5}-[0-9]{1,8})",
        )

    def _download_invoice_pdf(self, popup: Page, invoice: InvoiceInput, output_dir: Path) -> Path:
        safe_doc = _sanitize_filename(invoice.recipient_doc)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = output_dir / f"{timestamp}_{safe_doc}.pdf"

        with popup.expect_download() as download_info:
            popup.get_by_role("button", name=re.compile(r"Imprimir", re.IGNORECASE)).click()

        download = download_info.value
        if target_path.suffix != Path(download.suggested_filename).suffix:
            target_path = target_path.with_suffix(Path(download.suggested_filename).suffix or ".pdf")

        download.save_as(str(target_path))
        logger.info("AFIP: PDF guardado en %s", target_path)
        return target_path

    def _select_option(self, locator: Locator, value: str) -> None:
        locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        try:
            locator.select_option(value=value)
        except PlaywrightTimeoutError:
            raise
        except Exception:
            locator.select_option(label=value)
        self.page.wait_for_timeout(self.pause_ms)

    def _click_continue(self, popup: Page) -> None:
        popup.get_by_role("button", name=re.compile(r"Continuar", re.IGNORECASE)).click()
        popup.wait_for_timeout(self.pause_ms)

    def _click_text_if_visible(self, popup: Page, text: str) -> bool:
        locator = popup.get_by_text(re.compile(re.escape(text), re.IGNORECASE))
        if not locator.count():
            return False

        try:
            locator.first.wait_for(state="visible", timeout=1_000)
        except PlaywrightTimeoutError:
            return False

        locator.first.click()
        popup.wait_for_timeout(self.pause_ms)
        return True

    def _try_fill_date(
        self,
        popup: Page,
        value: str | None,
        *,
        selectors: Iterable[str],
        label_pattern: str,
    ) -> bool:
        normalized_date = _normalize_date(value)
        if not normalized_date:
            return False

        for selector in selectors:
            field = popup.locator(selector)
            if not field.count():
                continue

            try:
                field.first.wait_for(state="visible", timeout=1_000)
            except PlaywrightTimeoutError:
                continue

            field.first.click()
            field.first.fill(normalized_date)
            field.first.press("Tab")
            popup.wait_for_timeout(self.pause_ms)
            return True

        fallback_locator = popup.get_by_role("textbox", name=re.compile(label_pattern, re.IGNORECASE))
        if fallback_locator.count():
            fallback_locator.first.click()
            fallback_locator.first.fill(normalized_date)
            fallback_locator.first.press("Tab")
            popup.wait_for_timeout(self.pause_ms)
            return True

        logger.warning("AFIP: no encontre un campo visible para la fecha '%s'.", label_pattern)
        return False

    @staticmethod
    def _extract_pattern(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1) if match else None


def run_batch_invoicing(
    playwright: Playwright,
    invoices: list[InvoiceInput],
    *,
    settings: AfipSettings,
    output_dir: Path,
    headless: bool,
    stop_on_error: bool,
    preview_only: bool,
    pause_ms: int = DEFAULT_WAIT_MS,
) -> list[InvoiceResult]:
    logger.info(
        "AFIP: iniciando %s de %s facturas con navegador %s.",
        "prueba sin confirmacion" if preview_only else "emision masiva",
        len(invoices),
        browser_mode_label(headless),
    )

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    client = AfipInvoiceClient(page, settings, pause_ms=pause_ms)
    results: list[InvoiceResult] = []

    try:
        client.login()

        for index, invoice in enumerate(invoices, start=1):
            logger.info(
                "AFIP: procesando factura %s/%s para documento %s.",
                index,
                len(invoices),
                invoice.recipient_doc,
            )
            try:
                created = client.create_invoice(
                    invoice,
                    output_dir=output_dir,
                    preview_only=preview_only,
                )
                results.append(
                    InvoiceResult(
                        index=index,
                        status=created.status,
                        recipient_doc=created.recipient_doc,
                        description=created.description,
                        amount=created.amount,
                        pdf_path=created.pdf_path,
                        cae=created.cae,
                        voucher_number=created.voucher_number,
                    )
                )
                if preview_only:
                    print(
                        f"[OK] Factura {index}/{len(invoices)} validada en modo prueba para "
                        f"{invoice.recipient_doc}."
                    )
                else:
                    print(f"[OK] Factura {index}/{len(invoices)} emitida para {invoice.recipient_doc}.")
            except Exception as exc:
                logger.exception("AFIP: error al procesar la factura %s.", index)
                error_result = InvoiceResult(
                    index=index,
                    status="error",
                    recipient_doc=invoice.recipient_doc,
                    description=invoice.description,
                    amount=invoice.amount,
                    error=str(exc),
                )
                results.append(error_result)
                print(f"[ERROR] Factura {index}/{len(invoices)} fallo: {exc}")

                if stop_on_error:
                    logger.warning("AFIP: se detiene el proceso por --stop-on-error.")
                    break
    finally:
        context.close()
        browser.close()
        logger.info("AFIP: navegador cerrado.")

    return results


def write_results(results: list[InvoiceResult], output_path: Path) -> None:
    serializable = [asdict(result) for result in results]
    output_path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emision masiva de facturas en AFIP a partir de un JSON o CSV."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Ruta al archivo .json o .csv con las facturas a emitir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Carpeta donde se guardaran los PDFs y el resumen de resultados.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecuta Playwright en modo oculto. Por defecto abre el navegador visible.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Detiene el proceso ante el primer error.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=DEFAULT_WAIT_MS,
        help="Pausa entre acciones de Playwright en milisegundos.",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Completa el flujo hasta la pantalla final de revision pero no confirma la factura.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    settings = load_afip_settings()
    output_dir = ensure_output_dir(args.output_dir)
    invoices = load_invoices(args.input)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = output_dir / f"results_{timestamp}.json"

    with sync_playwright() as playwright:
        results = run_batch_invoicing(
            playwright,
            invoices,
            settings=settings,
            output_dir=output_dir,
            headless=args.headless,
            stop_on_error=args.stop_on_error,
            preview_only=args.preview_only,
            pause_ms=args.pause_ms,
        )

    write_results(results, results_path)

    success_count = sum(result.status in {"ok", "preview"} for result in results)
    preview_count = sum(result.status == "preview" for result in results)
    error_count = len(results) - success_count
    mode_label = "prueba sin confirmacion" if args.preview_only else "emision"
    print(
        f"[OK] Proceso finalizado en modo {mode_label}. "
        f"Exitosas={success_count}, previews={preview_count}, con error={error_count}. "
        f"Resumen: {results_path}"
    )
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
