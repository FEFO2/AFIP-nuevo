const tabs = document.querySelectorAll('.app-tab');
const views = {
  tasks: document.querySelector('#tasks-view'),
  numbers: document.querySelector('#numbers-view')
};
const yearPicker = document.querySelector('#iva-year');
const content = document.querySelector('#iva-content');
const status = document.querySelector('#iva-status');
const coverage = document.querySelector('#iva-coverage');
const fields = [
  ['neto_105', 'Neto 10,5 %'], ['neto_21', 'Neto 21 %'],
  ['iva_105', 'IVA 10,5 %'], ['iva_21', 'IVA 21 %'],
  ['no_gravado', 'No gravado'], ['total', 'Total']
];
const calculations = [
  ['diferencia_iva_21', 'Diferencia IVA 21 %'],
  ['diferencia_iva_105', 'Diferencia IVA 10,5 %'],
  ['diferencia_no_gravado', 'Diferencia no gravado'],
  ['diferencia_facturacion', 'Diferencia facturación'],
  ['importe_gravado_21', 'Importe gravado del 21 %'],
  ['importe_gravado_105', 'Importe gravado del 10,5 %'],
  ['importe_gravado_faltante', 'Importe gravado faltante']
];
const formatter = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2, maximumFractionDigits: 2
});
const monthFormatter = new Intl.DateTimeFormat('es-AR', {
  month: 'long', timeZone: 'UTC'
});
let records = [];

function cents(value) {
  return Math.round(Number(value) * 100);
}

function display(value) {
  return formatter.format(value / 100);
}

function sumValues(rows, source, keys) {
  return Object.fromEntries(keys.map(([key]) => [
    key, rows.reduce((total, row) => total + cents(row[source][key]), 0)
  ]));
}

function monthName(period) {
  const month = Number(period.slice(5, 7));
  const name = monthFormatter.format(new Date(Date.UTC(2026, month - 1, 1)));
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function sectionTitle(title) {
  const heading = document.createElement('h2');
  heading.textContent = title;
  return heading;
}

function verticalBlock(title, values, entries) {
  const block = document.createElement('section');
  block.className = 'iva-vertical-block';
  const heading = document.createElement('h3');
  heading.textContent = title;
  const list = document.createElement('dl');
  for (const [key, label] of entries) {
    const term = document.createElement('dt');
    const amount = document.createElement('dd');
    term.textContent = label;
    amount.textContent = display(values[key]);
    list.append(term, amount);
  }
  block.append(heading, list);
  return block;
}

function renderVertical(title, differences) {
  const section = document.createElement('section');
  section.className = 'iva-vertical-section';
  section.append(sectionTitle(title));
  section.append(verticalBlock('Diferencias y bases calculadas', differences, calculations));
  return section;
}

function renderPreviousMonths(rows) {
  const section = document.createElement('section');
  section.className = 'iva-previous';
  section.append(sectionTitle('Meses anteriores'));
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No hay meses anteriores para este año.';
    section.append(empty);
    return section;
  }
  const scroll = document.createElement('div');
  scroll.className = 'iva-table-scroll';
  const table = document.createElement('table');
  table.className = 'iva-table';
  const groupRow = table.createTHead().insertRow();
  for (const [label, span] of [['Mes', 1], ['Ventas', 6], ['Compras', 6], ['Diferencias y bases calculadas', 7]]) {
    const cell = document.createElement('th');
    cell.textContent = label;
    cell.colSpan = span;
    groupRow.append(cell);
  }
  const headerRow = table.tHead.insertRow();
  for (const label of ['Período', ...fields.map(([, name]) => name), ...fields.map(([, name]) => name), ...calculations.map(([, name]) => name)]) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headerRow.append(cell);
  }
  const body = table.createTBody();
  for (const record of rows) {
    const row = body.insertRow();
    row.insertCell().textContent = monthName(record.periodo);
    for (const source of ['ventas', 'compras']) {
      for (const [key] of fields) row.insertCell().textContent = display(cents(record[source][key]));
    }
    for (const [key] of calculations) row.insertCell().textContent = display(cents(record.calculos[key]));
  }
  scroll.append(table);
  section.append(scroll);
  return section;
}

function renderNumbers() {
  const year = yearPicker.value;
  const yearly = records
    .filter(record => record.periodo.startsWith(year))
    .sort((first, second) => second.periodo.localeCompare(first.periodo));
  content.replaceChildren();
  coverage.textContent = yearly.length + ' de 12 meses disponibles';
  if (!yearly.length) {
    content.textContent = 'No hay datos guardados para este año.';
    return;
  }
  content.append(renderVertical(
    'Acumulado ' + year, sumValues(yearly, 'calculos', calculations)
  ));
  const today = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit'
    }).formatToParts(new Date()).map(part => [part.type, part.value])
  );
  const currentPeriod = today.year + '-' + today.month;
  const current = yearly.find(record => record.periodo === currentPeriod);
  if (year === today.year) {
    if (current) {
      content.append(renderVertical(
        monthName(current.periodo) + ' ' + year,
        Object.fromEntries(calculations.map(([key]) => [key, cents(current.calculos[key])]))
      ));
    } else {
      const message = document.createElement('p');
      message.textContent = 'El mes en curso todavía no figura en Cálculo de IVA.';
      content.append(message);
    }
  }
  content.append(renderPreviousMonths(
    yearly.filter(record => record.periodo !== currentPeriod)
  ));
}

async function loadNumbers() {
  const response = await fetch('/api/iva');
  if (!response.ok) throw new Error('No se pudieron leer los datos locales.');
  records = await response.json();
  const years = [...new Set(records.map(record => record.periodo.slice(0, 4)))].sort().reverse();
  const selected = yearPicker.value;
  yearPicker.replaceChildren(...years.map(year => new Option(year, year)));
  if (years.includes(selected)) yearPicker.value = selected;
  if (!years.length) yearPicker.add(new Option(String(new Date().getFullYear())));
  renderNumbers();
}

yearPicker.onchange = renderNumbers;
document.querySelector('#refresh-iva').onclick = async event => {
  const button = event.currentTarget;
  button.disabled = true;
  status.textContent = 'Leyendo Cálculo de IVA…';
  try {
    const response = await fetch('/api/iva/actualizar', {method: 'POST'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    await loadNumbers();
    status.textContent = result.periodos_actualizados + ' período(s) actualizados.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
for (const tab of tabs) {
  tab.onclick = () => {
    for (const item of tabs) {
      const active = item === tab;
      item.classList.toggle('active', active);
      if (active) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
      views[item.dataset.view].hidden = !active;
    }
    if (tab.dataset.view === 'numbers') {
      loadNumbers().catch(error => status.textContent = error.message);
    }
  };
}
