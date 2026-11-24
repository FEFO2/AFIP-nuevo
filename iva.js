const tabs = document.querySelectorAll('.app-tab');
const views = {tasks:document.querySelector('#tasks-view'), numbers:document.querySelector('#numbers-view')};
const yearPicker = document.querySelector('#iva-year');
const ivaContent = document.querySelector('#iva-content');
const ivaStatus = document.querySelector('#iva-status');
let ivaRecords = [];
const fields = [
  ['neto_105','Neto 10,5 %'],['neto_21','Neto 21 %'],
  ['iva_105','IVA 10,5 %'],['iva_21','IVA 21 %'],
  ['no_gravado','No gravado'],['total','Total']
];
const numberFormat = new Intl.NumberFormat('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2});
const monthFormat = new Intl.DateTimeFormat('es-AR',{month:'long',timeZone:'UTC'});

function cents(value) {
  return Math.round(Number(value) * 100);
}
function display(value) {
  return numberFormat.format(value / 100);
}
function sumGroup(records, group) {
  return Object.fromEntries(fields.map(([key]) => [
    key, records.reduce((sum, record) => sum + cents(record[group][key]), 0)
  ]));
}
function metric(label, amount) {
  const element = document.createElement('div');
  element.className = 'iva-metric';
  const title = document.createElement('span');
  title.textContent = label;
  const value = document.createElement('strong');
  value.textContent = display(amount);
  element.append(title,value);
  return element;
}
function renderNumbers() {
  const year = yearPicker.value;
  const records = ivaRecords.filter(record => record.periodo.startsWith(year)).sort((a,b)=>a.periodo.localeCompare(b.periodo));
  ivaContent.replaceChildren();
  document.querySelector('#iva-coverage').textContent = records.length + ' de 12 meses disponibles';
  if (!records.length) {
    ivaContent.textContent = 'No hay datos guardados para este año. Usá «Actualizar desde Arancia» cuando el acceso esté configurado.';
    return;
  }
  const sales = sumGroup(records,'ventas');
  const purchases = sumGroup(records,'compras');
  const overview = document.createElement('div');
  overview.className = 'iva-overview';
  overview.append(
    metric('Total ventas · año',sales.total),
    metric('Total compras · año',purchases.total),
    metric('Diferencia IVA 21 %',sales.iva_21-purchases.iva_21),
    metric('Diferencia IVA 10,5 %',sales.iva_105-purchases.iva_105)
  );
  ivaContent.append(overview);
  const annualTitle = document.createElement('h2');
  annualTitle.textContent = 'Resumen anual';
  const annualScroll = document.createElement('div');
  annualScroll.className = 'iva-table-scroll annual-scroll';
  const annualTable = document.createElement('table');
  annualTable.className = 'iva-table annual-table';
  const annualHead = annualTable.createTHead().insertRow();
  for (const label of ['Origen', ...fields.map(([,name]) => name)]) {
    const th = document.createElement('th');
    th.textContent = label;
    annualHead.append(th);
  }
  const annualBody = annualTable.createTBody();
  for (const [label, values] of [
    ['Ventas', sales],
    ['Compras', purchases],
    ['Diferencia', Object.fromEntries(fields.map(([key]) => [key, sales[key] - purchases[key]]))]
  ]) {
    const row = annualBody.insertRow();
    row.insertCell().textContent = label;
    for (const [key] of fields) row.insertCell().textContent = display(values[key]);
  }
  annualScroll.append(annualTable);
  ivaContent.append(annualTitle, annualScroll);
  const title = document.createElement('h2');
  title.textContent = 'Detalle mensual';
  ivaContent.append(title);
  const scroll = document.createElement('div');
  scroll.className = 'iva-table-scroll';
  const table = document.createElement('table');
  table.className = 'iva-table';
  const head = table.createTHead();
  const groups = head.insertRow();
  for (const [label,span] of [['Mes',1],['Ventas',6],['Compras',6]]) {
    const th = document.createElement('th');
    th.textContent = label;
    th.colSpan = span;
    groups.append(th);
  }
  const columns = head.insertRow();
  const month = document.createElement('th');
  month.textContent = 'Período';
  columns.append(month);
  for (const group of ['ventas','compras']) {
    for (const [,label] of fields) {
      const th = document.createElement('th');
      th.textContent = label;
      columns.append(th);
    }
  }
  for (const record of records) {
    const row = table.createTBody().insertRow();
    const [,monthNumber] = record.periodo.split('-');
    const label = monthFormat.format(new Date(Date.UTC(2026,Number(monthNumber)-1,1)));
    row.insertCell().textContent = label.charAt(0).toUpperCase()+label.slice(1);
    for (const group of ['ventas','compras']) {
      for (const [key] of fields) row.insertCell().textContent = display(cents(record[group][key]));
    }
  }
  const totals = table.createTFoot().insertRow();
  totals.insertCell().textContent = 'Acumulado ' + year;
  for (const group of [sales,purchases]) {
    for (const [key] of fields) totals.insertCell().textContent = display(group[key]);
  }
  scroll.append(table);
  ivaContent.append(scroll);
}
async function loadNumbers() {
  const response = await fetch('/api/iva');
  if (!response.ok) throw new Error('No se pudieron leer los datos locales.');
  ivaRecords = await response.json();
  const years = [...new Set(ivaRecords.map(row=>row.periodo.slice(0,4)))].sort().reverse();
  const previous = yearPicker.value;
  yearPicker.replaceChildren(...years.map(year=>new Option(year,year)));
  if (years.includes(previous)) yearPicker.value = previous;
  if (!years.length) {
    yearPicker.add(new Option(String(new Date().getFullYear())));
  }
  renderNumbers();
}
yearPicker.onchange = renderNumbers;
document.querySelector('#refresh-iva').onclick = async event => {
  const button = event.currentTarget;
  button.disabled = true;
  ivaStatus.textContent = 'Leyendo Cálculo de IVA…';
  try {
    const response = await fetch('/api/iva/actualizar',{method:'POST'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    await loadNumbers();
    ivaStatus.textContent = result.periodos_actualizados + ' período(s) actualizados.';
  } catch(error) {
    ivaStatus.textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
for (const tab of tabs) {
  tab.onclick = () => {
    for (const item of tabs) {
      const active = item === tab;
      item.classList.toggle('active',active);
      if (active) item.setAttribute('aria-current','page');
      else item.removeAttribute('aria-current');
      views[item.dataset.view].hidden = !active;
    }
    if (tab.dataset.view === 'numbers') loadNumbers().catch(error => ivaStatus.textContent = error.message);
  };
}
