const clientPicker = document.querySelector('#client');
const clientStatus = document.querySelector('#client-status');
const usd = document.querySelector('#usd');
const fx = document.querySelector('#fx');
function updateCurrency() {
  fx.disabled = !usd.checked;
  document.querySelector('#fx-field').hidden = !usd.checked;
}
usd.onchange = updateCurrency;

const clientProfiles = {
  '11111111': {
    documentType: 'cuit',
    invoiceType: 'A',
    customerTax: 'responsable inscripto',
    pointOfSale: '2'
  }
};
const documentType = document.querySelector('#document-type');
const documentNumber = document.querySelector('#document-number');
const invoiceType = document.querySelector('#invoice-type');
const customerTax = document.querySelector('#customer-tax');
const pointOfSale = document.querySelector('#point-of-sale');
const customerAddress = document.querySelector('#customer-address');
const addressField = document.querySelector('#address-field');

function updateDocument() {
  const isDni = documentType.value === 'dni';
  addressField.hidden = !isDni;
  customerAddress.required = isDni;
  documentNumber.pattern = isDni ? '[0-9]{7,8}' : '[0-9]{11}|11111111';
  documentNumber.title = isDni ? 'Ingresá un DNI de 7 u 8 dígitos.' : 'Ingresá un CUIT de 11 dígitos.';
}
function applyClientProfile() {
  const profile = clientProfiles[clientPicker.value];
  if (!profile) return;
  documentType.value = profile.documentType;
  documentNumber.value = clientPicker.value;
  invoiceType.value = profile.invoiceType;
  customerTax.value = profile.customerTax;
  pointOfSale.value = profile.pointOfSale;
  updateDocument();
}
function validateInvoiceFields() {
  for (const field of [customerTax, documentType]) {
    field.setCustomValidity('');
  }
  if (invoiceType.value === 'A' && !['responsable inscripto', 'responsable monotributo'].includes(customerTax.value)) {
    customerTax.setCustomValidity('Para Factura A, seleccioná responsable inscripto o monotributo.');
  } else if (invoiceType.value === 'B' && !['consumidor final', 'sujeto exento'].includes(customerTax.value)) {
    customerTax.setCustomValidity('Para Factura B, seleccioná consumidor final o sujeto exento.');
  }
  if (invoiceType.value === 'A' && documentType.value !== 'cuit') {
    documentType.setCustomValidity('La Factura A requiere CUIT.');
  }

}
clientPicker.onchange = applyClientProfile;
documentType.onchange = updateDocument;
applyClientProfile();

const ivaBot = {'no-gravado':'no gravado', exento:'exento', '105':'10,5%', '210':'21%'};

async function api(path, options) {
  const response = await fetch('/api/' + path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'No se pudo completar la operación.');
  return body;
}

if (location.protocol === 'file:') {
  clientStatus.innerHTML = '<a href="http://127.0.0.1:8765/">Abrir el panel local para crear órdenes</a>';
}

function orderButton(order) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'back';
  button.textContent = 'Crear orden para el bot';
  const status = document.createElement('p');
  button.onclick = async () => {
    button.disabled = true;
    try {
      const saved = await api('ordenes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(order)});
      button.remove();
      status.textContent = 'Orden ' + saved.id + ' guardada · Pendiente de facturación';
      requestForm.reset();
      updateCurrency();
      applyClientProfile();
      while (lines.childElementCount > 1) lines.lastElementChild.remove();
      lines.firstElementChild.querySelector('.remove').hidden = true;
    } catch (error) {
      status.textContent = 'No se pudo confirmar la orden. Podés reintentar.';
      button.disabled = false;
    }
  };
  const group = document.createElement('div');
  group.append(button, status);
  return group;
}
