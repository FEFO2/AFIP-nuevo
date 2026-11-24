const tasks = [
  {group:'facturacion', name:'Solicitar factura', summary:'Prepará una solicitud de factura.', date:'20 nov 2026', iso:'2026-11-20', color:['#e9edf9','#4f65a5'], path:'M3 5h18v14H3z M3 6l9 7 9-7', request:true},
  {group:'facturacion', name:'Cargar factura', summary:'Registrá una factura existente de compra o venta.', date:'20 nov 2026', iso:'2026-11-20', color:['#fff0e5','#a54c19'], path:'M6 3h8l4 4v5 M14 3v5h5 M6 3v18h6 M14 17h8 M18 13v8', note:'Probá cómo elegirías el tipo de operación y el PDF. El archivo queda en tu equipo.', options:['Compra','Venta'], label:'Operación', file:true},
  {group:'facturacion', name:'Cargar factura IATA', summary:'Seleccioná un comprobante de IATA para su carga.', date:'17 nov 2026', iso:'2026-11-17', color:['#e4f2ee','#24755f'], path:'M2 14l8-3 7-8 3-1-1 4-6 7-1 8-2 1-1-8-6 2z', note:'Elegí el PDF de la factura IATA para probar la carga local.', file:true},
  {group:'gestion', name:'Conciliar facturación', summary:'Compará los comprobantes de ARCA y Arancia.', date:'19 nov 2026', iso:'2026-11-19', color:['#e4f2ee','#24755f'], path:'M3 7h17l-4-4 M21 17H4l4 4 M20 7l-4 4 M4 17l4-4', note:'Elegí qué comprobantes incluirías en la comparación.', options:['Compras y ventas','Compras','Ventas'], label:'Comprobantes'},
  {group:'gestion', name:'Realizar facturación grupal', summary:'Prepará un lote de facturas A o B para emitir en ARCA.', date:'16 nov 2026', iso:'2026-11-16', color:['#eeeafa','#7356a0'], path:'M5 3l2 1 2-1 3 1 3-1 2 1 2-1v18l-3-2-4 2-4-2-3 2z M8 8h8 M8 12h6', note:'Seleccioná el tipo de factura que tendría el lote.', options:['Factura A','Factura B'], label:'Tipo de factura'},
  {group:'gestion', name:'Revisar facturas de Gmail', summary:'Revisá las facturas recibidas por correo.', date:'18 nov 2026', iso:'2026-11-18', color:['#e9edf9','#4f65a5'], path:'M3 5h18v14H3z M3 6l9 7 9-7', note:'Esta tarea reúne las facturas recibidas por correo para su revisión.'},
  {group:'facturacion', name:'Cargar factura Newsan', summary:'Prepará los PDF de Newsan para su carga en Oracle.', date:'13 nov 2026', iso:'2026-11-13', color:['#f7eddc','#95692f'], path:'M3 7V5h7l2 2h9v12H3z M3 10h18', note:'Probá la selección de un PDF de Newsan. El archivo queda en tu equipo.', file:true}
];
const detail = document.querySelector('#detail');
for (const task of tasks) {
  const button = document.createElement('button');
  button.className = 'card';
  button.innerHTML = `<span class="icon" style="--bg:${task.color[0]};--ink:${task.color[1]}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="${task.path}"/></svg></span><strong>${task.name}</strong><span class="desc">${task.summary}</span><span class="stamp">Última ejecución <time datetime="${task.iso}">${task.date}</time></span>`;
  button.onclick = () => {
    if (task.request) {
      requestDialog.showModal();
      return;
    }
    document.querySelector('#task-name').textContent = task.name;
    document.querySelector('#description').textContent = task.note;
    const options = document.querySelector('#options');
    options.replaceChildren();
    if (task.options) {
      const label = document.createElement('label');
      label.textContent = task.label;
      const select = document.createElement('select');
      for (const value of task.options) select.add(new Option(value, value));
      label.append(select);
      options.append(label);
    }
    if (task.file) options.insertAdjacentHTML('beforeend','<label>Factura en PDF<input type="file" accept=".pdf,application/pdf"></label>');
    detail.showModal();
  };
  document.getElementById(task.group).append(button);
}
for (const button of detail.querySelectorAll('button')) button.onclick = () => detail.close();
