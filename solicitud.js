const requestDialog = document.querySelector('#request');
const requestForm = requestDialog.querySelector('form');
const draft = document.querySelector('#draft');
const lines = document.querySelector('#lines');
const template = document.querySelector('#line-template');
const rates = { 'no-gravado': 0n, exento: 0n, '105': 105n, '210': 210n };

requestDialog.querySelector('.close').onclick = () => requestDialog.close();
requestForm.oninput = event => {
  event.target.setCustomValidity('');
  draft.replaceChildren();
};

function refreshLines() {
  Array.from(lines.children).forEach((row, index) => {
    row.querySelector('legend').textContent = 'Concepto ' + (index + 1);
    row.querySelector('.remove').hidden = lines.childElementCount === 1;
  });
  draft.replaceChildren();
}

function addLine() {
  const row = template.content.firstElementChild.cloneNode(true);
  lines.append(row);
  row.querySelector('.remove').onclick = () => {
    const neighbor = row.nextElementSibling || row.previousElementSibling;
    row.remove();
    refreshLines();
    neighbor.querySelector('input').focus();
  };
  refreshLines();
  return row;
}

document.querySelector('#add-line').onclick = () => addLine().querySelector('input').focus();
addLine();

function formatCents(cents) {
  const whole = (cents / 100n).toLocaleString('es-AR');
  return whole + ',' + String(cents % 100n).padStart(2, '0');
}

function appendAmount(summary, label, cents) {
  const term = document.createElement('dt');
  const data = document.createElement('dd');
  term.textContent = label;
  data.textContent = formatCents(cents);
  summary.append(term, data);
}

requestForm.onsubmit = event => {
  event.preventDefault();
  validateInvoiceFields();
  if (!requestForm.reportValidity()) return;
  const result = document.createDocumentFragment();
  const title = document.createElement('h3');
  title.textContent = 'Borrador de solicitud';
  const todayParts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {timeZone:'Europe/Madrid', year:'numeric', month:'2-digit', day:'2-digit'})
      .formatToParts(new Date()).map(part => [part.type, part.value])
  );
  const today = todayParts.year + '-' + todayParts.month + '-' + todayParts.day;
  const order = {id:crypto.randomUUID(), cuit:clientPicker.value, moneda:usd.checked ? 'USD' : 'ARS', correo_entrega:document.querySelector('#delivery-email').value.trim(),
    tipo_factura:invoiceType.value, condicion_iva:customerTax.value,
    tipo_doc:documentType.value, num_doc:documentNumber.value,
    direccion:customerAddress.value.trim(), punto_venta:pointOfSale.value,
    fecha_emision:today, servicio_desde:today, servicio_hasta:today,
    vencimiento_pago:today, conceptos:[]};
  let fxMillionths;
  if (usd.checked) {
    order.tipo_cambio = fx.value.replace(',', '.');
    const [whole, fraction = ''] = order.tipo_cambio.split('.');
    fxMillionths = BigInt(whole + fraction.padEnd(6, '0'));
    if (!fxMillionths) {
      fx.setCustomValidity('Ingresá un tipo de cambio mayor que cero.');
      fx.reportValidity();
      return;
    }
  }
  const groups = new Map();
  const header = document.createElement('p');
  header.textContent = clientPicker.selectedOptions[0].textContent + ' · CUIT ' + order.cuit + ' · ' + order.moneda;
  const delivery = document.createElement('p');
  delivery.textContent = 'Enviar factura a ' + order.correo_entrega;
  const terms = document.createElement('p');
  terms.textContent = 'Factura ' + order.tipo_factura + ' · ' + order.condicion_iva
    + ' · ' + order.tipo_doc.toUpperCase() + ' ' + order.num_doc
    + ' · Punto de venta ' + order.punto_venta;
  const dates = document.createElement('p');
  dates.textContent = 'Emisión, servicio y vencimiento · ' + todayParts.day + '/' + todayParts.month + '/' + todayParts.year;
  result.append(title, header, terms, dates, delivery);
  let netTotal = 0n;
  let vatTotal = 0n;
  for (const row of lines.children) {
    const { concept, tax, amount } = row.elements;
    const [whole, fraction = ''] = amount.value.split(/[.,]/);
    const net = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
    if (net === 0n) {
      amount.setCustomValidity('Ingresá un monto mayor que cero.');
      amount.reportValidity();
      return;
    }
    const vat = (net * rates[tax.value] + 500n) / 1000n;
    const description = document.createElement('h4');
    description.textContent = concept.value.trim();
    const detail = document.createElement('dl');
    appendAmount(detail, 'Monto sin IVA', net);
    appendAmount(detail, 'IVA · ' + tax.selectedOptions[0].textContent, vat);
    appendAmount(detail, 'Subtotal con IVA', net + vat);
    result.append(description, detail);
    order.conceptos.push({concepto:concept.value.trim(), iva:ivaBot[tax.value], precio:String(net / 100n) + '.' + String(net % 100n).padStart(2, '0')});
    const label = tax.selectedOptions[0].textContent;
    const group = groups.get(label) || {net:0n, vat:0n};
    group.net += net;
    group.vat += vat;
    groups.set(label, group);
    netTotal += net;
    vatTotal += vat;
  }
  const breakdown = document.createElement('table');
  breakdown.className = 'vat-summary';
  breakdown.createCaption().textContent = 'Desglose de IVA (' + order.moneda + ')';
  const columns = breakdown.createTHead().insertRow();
  for (const label of ['Tipo de IVA', 'Base', 'IVA']) {
    const cell = document.createElement('th');
    cell.scope = 'col';
    cell.textContent = label;
    columns.append(cell);
  }
  const body = breakdown.createTBody();
  for (const [label, group] of groups) {
    const row = body.insertRow();
    const name = document.createElement('th');
    name.scope = 'row';
    name.textContent = label;
    row.append(name);
    row.insertCell().textContent = formatCents(group.net);
    row.insertCell().textContent = formatCents(group.vat);
  }
  const subtotalHeading = document.createElement('h3');
  subtotalHeading.textContent = 'Subtotal';
  subtotalHeading.className = 'summary-heading';
  result.append(subtotalHeading, breakdown);
  const totals = document.createElement('dl');
  totals.className = 'invoice-totals';
  appendAmount(totals, 'Total sin IVA', netTotal);
  appendAmount(totals, 'IVA total', vatTotal);
  appendAmount(totals, 'Total de la factura (' + order.moneda + ')', netTotal + vatTotal);
  if (usd.checked) {
    const rate = document.createElement('p');
    rate.textContent = '1 USD = ' + order.tipo_cambio.replace('.', ',') + ' ARS';
    result.append(totals, rate);
    const converted = document.createElement('dl');
    appendAmount(converted, 'Equivalente en pesos (ARS)', ((netTotal + vatTotal) * fxMillionths + 500000n) / 1000000n);
    result.append(converted);
  } else {
    result.append(totals);
  }
  result.append(orderButton(order));
  draft.replaceChildren(result);
  title.scrollIntoView({block:'nearest'});
};
