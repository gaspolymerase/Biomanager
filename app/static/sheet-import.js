/* Import from Excel (templates/sheet_import.html): the chosen file's name,
   one spreadsheet column per BioManager column, and the must-have columns
   the sheet still lacks. The server checks all of it again. */
(function () {
  'use strict';
  const file = document.querySelector('[data-si-file]');
  if (file) {
    const drop = file.closest('.si-drop');
    const chosen = document.querySelector('[data-si-chosen]');
    file.addEventListener('change', () => {
      const f = file.files[0];
      chosen.hidden = !f;
      if (f) chosen.textContent = `${f.name} (${Math.max(1, Math.round(f.size / 1024))} KB)`;
    });
    ['dragenter', 'dragover'].forEach((e) => file.addEventListener(e, () => drop.classList.add('is-over')));
    ['dragleave', 'drop'].forEach((e) => file.addEventListener(e, () => drop.classList.remove('is-over')));
  }

  const form = document.querySelector('[data-si-match]');
  if (!form) return;
  const rows = Array.from(form.querySelectorAll('[data-si-row]'));
  const fills = Array.from(form.querySelectorAll('[data-si-fill]'));
  const allThere = form.querySelector('[data-si-all-there]');

  function refresh() {
    const used = {};
    rows.forEach((row) => {
      const value = row.querySelector('[data-si-map]').value;
      used[value] = (used[value] || 0) + 1;
      row.dataset.state = ['_new', '_notes', '_skip'].includes(value) ? value.slice(1) : 'field';
      const kind = row.querySelector('[data-si-kind]');
      if (kind) kind.hidden = value !== '_new';
    });
    rows.forEach((row) => {
      const value = row.querySelector('[data-si-map]').value;
      const clash = !value.startsWith('_') && used[value] > 1;
      row.classList.toggle('is-clash', clash);
      row.querySelector('[data-si-clash]').hidden = !clash;
    });
    let missing = 0;
    fills.forEach((fill) => {
      const has = Boolean(used[fill.dataset.siFill]);
      fill.hidden = has;
      fill.querySelectorAll('input, select').forEach((el) => { el.disabled = has; });
      if (!has) missing += 1;
    });
    if (allThere) allThere.hidden = missing > 0;
  }

  form.addEventListener('change', refresh);
  form.addEventListener('submit', (event) => {
    if (form.querySelector('tr.is-clash')) {
      event.preventDefault();
      form.querySelector('tr.is-clash [data-si-map]').focus();
    }
  });
  refresh();
})();
