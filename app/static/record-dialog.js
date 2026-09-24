/* Record dialog: one <dialog> serves both New and Edit for a database page.
 *
 *   <button data-record-edit="sample-dialog"
 *           data-record-payload='{"id": 4, "sample_id": "S-12", ...}'>
 *
 *   <dialog id="sample-dialog" class="record-dialog">
 *     <form method="post" data-record-form
 *           data-create-action="/samples"
 *           data-update-action="/samples/0/update"      ← /0/ becomes the id
 *           data-new-title="New sample" data-edit-title="Sample {label}"
 *           data-new-submit="Create sample" data-edit-submit="Save">
 *       <h3 data-record-title></h3> … <button data-record-submit>
 *
 * Fields are filled by name from the payload; a field the payload does not
 * mention keeps its default, which is how New gets sensible defaults.
 * Payload keys starting with "_" are metadata: _label names the record in
 * the title, _locked opens it read-only.
 *
 * The row travels as a data attribute, never inside an onclick: Jinja's
 * tojson leaves double quotes unescaped, which silently broke every Add
 * button on the organism pages.
 */
(function () {
  'use strict';

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-record-edit]');
    if (!button) return;
    const dialog = document.getElementById(button.dataset.recordEdit);
    const form = dialog && dialog.querySelector('form[data-record-form]');
    if (!form) return;

    let data = {};
    try { data = JSON.parse(button.dataset.recordPayload || '{}'); } catch (e) { console.error(e); }
    const isNew = !data.id;
    const locked = Boolean(data._locked);

    form.reset();
    Array.from(form.elements).forEach((el) => {
      if (!el.name) return;
      if (Object.prototype.hasOwnProperty.call(data, el.name)) {
        const value = data[el.name];
        if (el.type === 'checkbox') el.checked = Boolean(value);
        else el.value = value === null || value === undefined ? '' : value;
      }
      if (el.type !== 'hidden' && el.tagName !== 'BUTTON') el.disabled = locked;
    });

    form.action = isNew
      ? form.dataset.createAction
      : form.dataset.updateAction.replace('/0/', `/${data.id}/`);

    const title = dialog.querySelector('[data-record-title]');
    if (title) {
      title.textContent = isNew
        ? form.dataset.newTitle
        : (form.dataset.editTitle || 'Edit').replace('{label}', data._label || '');
    }
    const submit = dialog.querySelector('[data-record-submit]');
    if (submit) {
      submit.textContent = isNew ? (form.dataset.newSubmit || 'Create') : (form.dataset.editSubmit || 'Save');
      submit.hidden = locked;
    }

    dialog.dispatchEvent(new CustomEvent('record-dialog:open', { detail: { data, isNew } }));
    dialog.showModal();
    const first = form.querySelector('input:not([type=hidden]):not(:disabled), select:not(:disabled), textarea:not(:disabled)');
    if (first) first.focus();
  });
})();
