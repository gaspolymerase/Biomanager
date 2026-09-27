/* Keep what was typed when a save is refused.
 *
 * Forms here post and the server answers with a redirect back to the page
 * and a flash message. When the message is an error ("Tank T-3 already
 * exists", "Pick a female tank"), the page used to come back with the
 * dialog closed and the fields empty, so everything had to be typed again.
 *
 * Now each posted form's fields are kept for this tab (sessionStorage),
 * and if the next page, a moment later on the same path, shows an error,
 * the form gets them back and its dialog (or folded card) opens again.
 * Any other outcome forgets them. A record dialog is reopened through its
 * own button path (record-dialog.js), so its title, action and Delete
 * button are those of the record being edited.
 *
 * Not kept: passwords, files, forms that save themselves (the sheets'
 * autosave, which never reloads the page), GET forms, and any form marked
 * data-no-remember.
 */
(function () {
  'use strict';

  const KEY = 'biomanager:retry';
  const FRESH_MS = 2 * 60 * 1000;

  function remember(form) {
    const values = [];
    Array.from(form.elements).forEach((el) => {
      if (!el.name || el.disabled || /csrf/i.test(el.name)) return;
      if (el.type === 'password' || el.type === 'file' || el.tagName === 'BUTTON') return;
      if (el.type === 'submit' || el.type === 'reset' || el.type === 'image') return;
      if ((el.type === 'checkbox' || el.type === 'radio') && !el.checked) {
        values.push([el.name, null, el.type]);
        return;
      }
      if (el.tagName === 'SELECT' && el.multiple) {
        Array.from(el.selectedOptions).forEach((o) => values.push([el.name, o.value, 'multi']));
        return;
      }
      values.push([el.name, el.value, el.type]);
    });
    const dialog = form.closest('dialog');
    const scope = dialog || document;
    const state = {
      path: location.pathname,
      at: Date.now(),
      action: form.getAttribute('action') ? form.action : '',
      dialog: dialog && dialog.id ? dialog.id : '',
      index: Array.from(scope.querySelectorAll('form')).indexOf(form),
      record: form.hasAttribute('data-record-form'),
      title: dialog && dialog.querySelector('[data-record-title]') ? dialog.querySelector('[data-record-title]').textContent : '',
      values,
    };
    try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (_) { /* storage off */ }
  }

  // Last in line (window, bubbling), so a handler that sends the form
  // itself (fetch) or asks first (data-confirm) has had its say.
  window.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
    if ((form.method || 'get').toLowerCase() !== 'post' || form.hasAttribute('data-no-remember')) return;
    if (form.querySelector('[data-autosave]')) return;
    // Sent to another address by its button (the Wean dialog's two):
    // the page coming back could not send it there again.
    if (event.submitter && event.submitter.hasAttribute('formaction')) return;
    remember(form);
  });

  // Refused outright: an error and nothing done. A save that partly
  // worked ("Moved 2 mice" and "Not moved: 46") is not typed again.
  function refused() {
    return Boolean(document.querySelector('.flash-message.flash-error'))
      && !document.querySelector('.flash-message.flash-success');
  }

  function fill(form, values) {
    const seen = {};
    values.forEach(([name, value, type]) => {
      const fields = Array.from(form.elements).filter((el) => el.name === name);
      if (!fields.length) return;
      if (type === 'checkbox' || type === 'radio') {
        fields.forEach((el) => {
          if (value === null) { if (el.type === 'checkbox' && fields.length === 1) el.checked = false; }
          else if (el.value === value) el.checked = true;
        });
        return;
      }
      if (type === 'multi') {
        fields.forEach((el) => Array.from(el.options || []).forEach((o) => { if (o.value === value) o.selected = true; }));
        return;
      }
      // Repeated names (rows of a table, name[]) are filled in order.
      const i = seen[name] || 0;
      seen[name] = i + 1;
      const el = fields[Math.min(i, fields.length - 1)];
      if (el.type === 'hidden' && el.name !== 'id' && !el.value && !value) return;
      el.value = value;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  function restore() {
    let state = null;
    try {
      state = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      sessionStorage.removeItem(KEY);
    } catch (_) { return; }
    if (!state || state.path !== location.pathname || Date.now() - state.at > FRESH_MS || !refused()) return;

    const dialog = state.dialog ? document.getElementById(state.dialog) : null;
    const scope = dialog || document;
    let form = scope.querySelectorAll('form')[state.index];
    if (!form && state.action) {
      form = Array.from(document.querySelectorAll('form')).find((f) => f.getAttribute('action') && f.action === state.action);
    }
    if (!form) return;

    if (dialog && state.record && form.hasAttribute('data-record-form')) {
      // Reopen the way its button does, with what was typed as the record.
      const payload = {};
      state.values.forEach(([name, value, type]) => {
        if (type === 'checkbox') { if (!(name in payload)) payload[name] = value !== null; }
        else if (type === 'radio') { if (value !== null) payload[name] = value; }
        else if (!(name in payload)) payload[name] = value;
      });
      const opener = document.createElement('button');
      opener.type = 'button';
      opener.hidden = true;
      opener.dataset.recordEdit = dialog.id;
      opener.dataset.recordPayload = JSON.stringify(payload);
      document.body.appendChild(opener);
      opener.click();
      opener.remove();
      fill(form, state.values.filter(([, , type]) => type === 'multi' || type === 'radio'));
      if (state.action) form.action = state.action;
      // "Tank T-3", as it read when it was sent (the payload has no label).
      const title = dialog.querySelector('[data-record-title]');
      if (title && state.title) title.textContent = state.title;
      return;
    }

    fill(form, state.values);
    if (state.action) form.action = state.action;
    const details = form.closest('details');
    if (details) details.open = true;
    if (dialog && !dialog.open && typeof dialog.showModal === 'function') dialog.showModal();
    else form.scrollIntoView({ block: 'center' });
    const first = form.querySelector('input:not([type=hidden]):not(:disabled), select:not(:disabled), textarea:not(:disabled)');
    if (first) { try { first.focus({ preventScroll: true }); } catch (_) {} }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(restore, 0));
  else setTimeout(restore, 0);
})();
