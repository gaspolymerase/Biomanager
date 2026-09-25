/* Rack grid: housing units shown where they physically sit.
 *
 * One component for mouse cages, fly vials, worm plates and fish tanks. The
 * page renders the shell with the `rack_grid` macro (templates/_rack_grid.html)
 * and a JSON payload:
 *
 *   { "racks": [{ "id": 3, "name": "B", "rows": 8, "cols": 10, "edit": {...} }],
 *     "items": [{ "id": 12, "label": "C-104", "sub": "DBH-Cre", "badge": "4",
 *                 "tone": "breeder", "flag": false, "rack": 3, "row": 2, "col": 7,
 *                 "search": "…", "edit": { "data-org-edit": "…", … } }],
 *     "create": { "attrs": {…}, "payload": {…}, "rack_field": "location_id_fk",
 *                 "row_field": "row", "col_field": "col", "text_field": null } }
 *
 * Rows and columns are 1-based in the payload. A page whose storage is
 * 0-based (fish tanks) sets data-index-base="0" and this script converts on
 * the way out.
 *
 * Editing on the grid:
 *   · drag a tile to a cell to move it (an occupied cell swaps), or onto the
 *     tray to unplace it — saved immediately through data-move-url;
 *   · click a tile to open that record's own edit dialog (its `edit`
 *     attributes are the same data-*-edit hooks the table rows use);
 *   · click an empty cell to create a record already placed there.
 */
(function () {
  'use strict';

  /* Position names — mirrors app/positions.py, so the grid, the sheet and
     the dialogs all call a cell the same thing under each rack's scheme. */
  const DEFAULT_NAMING = { mode: 'grid', rows: 'letters', cols: 'numbers', order: 'row_col', separator: '', start: 1 };
  function naming(raw) {
    const s = Object.assign({}, DEFAULT_NAMING, raw || {});
    s.start = parseInt(s.start, 10) === 0 ? 0 : 1;
    if (s.mode === 'grid' && s.rows === s.cols && !s.separator) s.separator = '-';
    return s;
  }
  function letters(n) {
    let out = '';
    while (n > 0) { const rem = (n - 1) % 26; out = String.fromCharCode(65 + rem) + out; n = Math.floor((n - 1) / 26); }
    return out;
  }
  const axisLabel = (n, style, start) => (style === 'letters' ? letters(n) : String(n - 1 + start));
  function cellLabel(row, col, raw, cols) {
    const s = naming(raw);
    if (s.mode === 'sequential') return String((row - 1) * cols + col - 1 + s.start);
    const r = axisLabel(row, s.rows, s.start);
    const c = axisLabel(col, s.cols, s.start);
    return s.order === 'row_col' ? `${r}${s.separator}${c}` : `${c}${s.separator}${r}`;
  }
  const escapeHtml = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* Click an invisible button carrying data-* hooks, so the page's existing
     delegated listeners (record-dialog.js, orgEdit, the mouse dialog) open
     their own dialog exactly as a table row would. */
  function trigger(attrs) {
    const button = document.createElement('button');
    button.type = 'button';
    button.hidden = true;
    Object.entries(attrs || {}).forEach(([name, value]) => {
      button.setAttribute(name, typeof value === 'string' ? value : JSON.stringify(value));
    });
    document.body.appendChild(button);
    button.click();
    button.remove();
  }

  function setup(root) {
    const dataNode = root.querySelector('script[data-rack-data]');
    if (!dataNode) return;
    let data;
    try { data = JSON.parse(dataNode.textContent); } catch (e) { console.error(e); return; }
    const racks = data.racks || [];
    const items = data.items || [];
    const create = data.create || null;
    const base = parseInt(root.dataset.indexBase || '1', 10);
    const moveUrl = root.dataset.moveUrl || '';
    const fields = {
      rack: root.dataset.rackField || 'rack_id',
      row: root.dataset.rowField || 'row',
      col: root.dataset.colField || 'col',
    };
    const key = `rack:${root.dataset.rackView}:active`;

    const select = root.querySelector('[data-rack-select]');
    const meta = root.querySelector('[data-rack-meta]');
    const grid = root.querySelector('[data-rack-grid]');
    const tray = root.querySelector('[data-rack-tray-items]');
    const trayBox = root.querySelector('[data-rack-tray]');
    const search = root.querySelector('[data-rack-search]');
    const editRack = root.querySelector('[data-rack-edit]');
    const status = root.querySelector('[data-rack-status]');

    let active = null;
    try { active = parseInt(localStorage.getItem(key) || '', 10) || null; } catch (_) {}
    if (!racks.some((r) => r.id === active)) active = racks[0] ? racks[0].id : null;

    racks.forEach((rack) => {
      const option = document.createElement('option');
      option.value = rack.id;
      option.textContent = rack.name;
      select.appendChild(option);
    });
    if (!racks.length) {
      select.disabled = true;
      const option = document.createElement('option');
      option.textContent = 'No racks yet';
      select.appendChild(option);
    }
    if (active) select.value = String(active);

    const say = (state, text) => {
      if (!status) return;
      status.dataset.state = state;
      status.textContent = text;
      if (state === 'saved') setTimeout(() => { if (status.textContent === text) status.textContent = ''; }, 2000);
    };

    const rackById = (id) => racks.find((r) => r.id === id);
    const placedIn = (rack, item) => item.rack === rack.id && item.row >= 1 && item.col >= 1
      && item.row <= rack.rows && item.col <= rack.cols;
    const isPlacedAnywhere = (item) => racks.some((rack) => placedIn(rack, item));

    function tile(item) {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'rack-tile';
      el.draggable = true;
      el.dataset.id = item.id;
      if (item.tone) el.dataset.tone = String(item.tone).toLowerCase();
      el.title = item.title || [item.label, item.sub].filter(Boolean).join(' · ');
      el.innerHTML = `
        <span class="rack-tile-top">
          <span class="rack-tile-id">${escapeHtml(item.label)}</span>
          ${item.flag ? '<span class="rack-tile-flag" aria-label="Needs attention"></span>' : ''}
          ${item.badge ? `<span class="rack-tile-badge">${escapeHtml(item.badge)}</span>` : ''}
        </span>
        ${item.sub ? `<span class="rack-tile-sub">${escapeHtml(item.sub)}</span>` : ''}`;
      el.addEventListener('dragstart', (event) => {
        event.dataTransfer.setData('text/plain', String(item.id));
        event.dataTransfer.effectAllowed = 'move';
        el.classList.add('is-dragging');
      });
      el.addEventListener('dragend', () => el.classList.remove('is-dragging'));
      el.addEventListener('click', () => { if (item.edit) trigger(item.edit); });
      return el;
    }

    // The position alone ("D7"); the rack is a separate field.
    const positionText = (rack, row, col) => cellLabel(row, col, rack.naming, rack.cols);
    const whereText = (rack, row, col) => `${rack.name} · ${positionText(rack, row, col)}`;

    function render() {
      const rack = rackById(active);
      grid.innerHTML = '';
      tray.innerHTML = '';
      if (editRack) {
        editRack.hidden = !rack;
        if (rack && rack.edit) Object.entries(rack.edit).forEach(([n, v]) => editRack.setAttribute(n, typeof v === 'string' ? v : JSON.stringify(v)));
      }
      if (!rack) {
        grid.innerHTML = `<div class="rack-empty">${escapeHtml(root.dataset.emptyText || 'Add a rack to start placing.')}</div>`;
      } else {
        const occupied = items.filter((item) => placedIn(rack, item)).length;
        if (meta) meta.textContent = `${rack.rows} × ${rack.cols} · ${occupied} of ${rack.rows * rack.cols} filled`;
        const scheme = naming(rack.naming);
        const sequential = scheme.mode === 'sequential';
        grid.style.gridTemplateColumns = `28px repeat(${rack.cols}, minmax(84px, 1fr))`;
        grid.appendChild(Object.assign(document.createElement('div'), { className: 'rack-corner' }));
        for (let c = 1; c <= rack.cols; c += 1) {
          grid.appendChild(Object.assign(document.createElement('div'), {
            className: 'rack-col-label', textContent: sequential ? '' : axisLabel(c, scheme.cols, scheme.start) }));
        }
        for (let r = 1; r <= rack.rows; r += 1) {
          grid.appendChild(Object.assign(document.createElement('div'), {
            className: 'rack-row-label', textContent: sequential ? '' : axisLabel(r, scheme.rows, scheme.start) }));
          for (let c = 1; c <= rack.cols; c += 1) {
            const cell = document.createElement('div');
            cell.className = 'rack-cell';
            cell.dataset.row = r;
            cell.dataset.col = c;
            cell.title = whereText(rack, r, c);
            const here = items.find((item) => item.rack === rack.id && item.row === r && item.col === c);
            if (here) {
              cell.appendChild(tile(here));
            } else {
              // An empty cell shows its own name, so what the sheet calls D7
              // is visibly the D7 here.
              const name = `<span class="rack-cell-name">${escapeHtml(positionText(rack, r, c))}</span>`;
              if (create) {
                const add = document.createElement('button');
                add.type = 'button';
                add.className = 'rack-cell-add';
                add.setAttribute('aria-label', `New at ${whereText(rack, r, c)}`);
                add.innerHTML = name + '<svg class="icon" aria-hidden="true"><use href="/static/icons.svg#plus"></use></svg>';
                add.addEventListener('click', () => createAt(rack, r, c));
                cell.appendChild(add);
              } else {
                cell.insertAdjacentHTML('beforeend', name);
              }
            }
            wireDrop(cell, () => moveTo(cell._dragId, rack, r, c));
            grid.appendChild(cell);
          }
        }
      }
      // Unplaced: no valid position in any rack.
      items.filter((item) => !isPlacedAnywhere(item)).forEach((item) => tray.appendChild(tile(item)));
      if (!tray.children.length) tray.innerHTML = '<div class="rack-tray-empty">Everything is placed.</div>';
      applySearch();
    }

    function wireDrop(target, onDrop) {
      target.addEventListener('dragover', (event) => { event.preventDefault(); target.classList.add('is-drop-target'); });
      target.addEventListener('dragleave', () => target.classList.remove('is-drop-target'));
      target.addEventListener('drop', (event) => {
        event.preventDefault();
        target.classList.remove('is-drop-target');
        target._dragId = parseInt(event.dataTransfer.getData('text/plain'), 10);
        if (target._dragId) onDrop();
      });
    }
    wireDrop(trayBox, () => moveTo(trayBox._dragId, null, null, null));

    function createAt(rack, r, c) {
      const payload = Object.assign({}, create.payload || {});
      if (create.rack_field) payload[create.rack_field] = rack.id;
      if (create.row_field) payload[create.row_field] = r - 1 + base;
      if (create.col_field) payload[create.col_field] = c - 1 + base;
      if (create.text_field) payload[create.text_field] = positionText(rack, r, c);
      // The payload attribute pairs with the dialog hook:
      // data-org-edit → data-org-payload, data-record-edit → data-record-payload.
      const attrs = Object.assign({}, create.attrs || {});
      const hook = Object.keys(attrs).find((name) => name.endsWith('-edit'));
      attrs[hook ? hook.replace(/-edit$/, '-payload') : 'data-record-payload'] = JSON.stringify(payload);
      trigger(attrs);
    }

    async function moveTo(itemId, rack, r, c) {
      const item = items.find((i) => i.id === itemId);
      if (!item) return;
      if (rack && item.rack === rack.id && item.row === r && item.col === c) return;
      const previous = { rack: item.rack, row: item.row, col: item.col };
      const occupant = rack ? items.find((i) => i !== item && i.rack === rack.id && i.row === r && i.col === c) : null;
      const body = new FormData();
      body.append(fields.rack, rack ? rack.id : '');
      body.append(fields.row, rack ? r - 1 + base : '');
      body.append(fields.col, rack ? c - 1 + base : '');
      say('saving', 'Saving…');
      try {
        const response = await fetch(moveUrl.replace('{id}', itemId), {
          method: 'POST', body, headers: { 'X-Autosave': '1' },
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || result.ok === false) throw new Error(result.error || `The server answered ${response.status}.`);
        // Mirror the server: the moved item takes the cell, an occupant swaps.
        Object.assign(item, rack ? { rack: rack.id, row: r, col: c } : { rack: null, row: null, col: null });
        if (occupant) Object.assign(occupant, previous);
        syncEditPayload(item);
        if (occupant) syncEditPayload(occupant);
        // Let the page update anything else showing these records.
        [item, occupant].filter(Boolean).forEach((moved) => {
          const where = moved.rack ? rackById(moved.rack) : null;
          document.dispatchEvent(new CustomEvent('rack-grid:moved', { detail: {
            view: root.dataset.rackView, id: moved.id, rackId: moved.rack,
            position: where && moved.row ? positionText(where, moved.row, moved.col) : '',
          } }));
        });
        say('saved', rack ? `Moved ${item.label} to ${whereText(rack, r, c)}` : `Unplaced ${item.label}`);
        render();
      } catch (error) {
        say('error', `Couldn’t move ${item.label}: ${error.message}`);
      }
    }

    /* A tile's edit dialog was filled from the page as it loaded; after a
       move, write the new position into it so the dialog shows where the
       record is now, not where it was. */
    function syncEditPayload(item) {
      if (!item.edit || !create) return;
      const name = Object.keys(item.edit).find((n) => n.endsWith('-payload'));
      if (!name) return;
      let payload;
      try { payload = JSON.parse(item.edit[name]); } catch (_) { return; }
      const rack = item.rack ? rackById(item.rack) : null;
      const placed = rack && item.row && item.col;
      if (create.text_field) payload[create.text_field] = placed ? positionText(rack, item.row, item.col) : '';
      if (create.rack_field && rack) payload[create.rack_field] = rack.id;
      if (create.row_field) payload[create.row_field] = placed ? item.row - 1 + base : '';
      if (create.col_field) payload[create.col_field] = placed ? item.col - 1 + base : '';
      item.edit[name] = JSON.stringify(payload);
    }

    function applySearch() {
      const q = search ? search.value.trim().toLowerCase() : '';
      root.querySelectorAll('.rack-tile').forEach((el) => {
        const item = items.find((i) => String(i.id) === el.dataset.id);
        const hay = item ? (item.search || `${item.label} ${item.sub || ''}`).toLowerCase() : '';
        el.classList.toggle('is-dimmed', Boolean(q) && !hay.includes(q));
        el.classList.toggle('is-match', Boolean(q) && hay.includes(q));
      });
    }

    select.addEventListener('change', () => {
      active = parseInt(select.value, 10) || null;
      try { localStorage.setItem(key, String(active)); } catch (_) {}
      render();
    });
    if (search) search.addEventListener('input', applySearch);
    render();
  }

  /* Table / grid switch, remembered per page:
       <div class="view-switch" data-view-switch="mouse-cages">
         <button data-layout="table" class="dt-chip">…</button>
         <button data-layout="grid" class="dt-chip">…</button>
       </div>
       <div data-layout-panel="table">…</div> <div data-layout-panel="grid" hidden>…</div> */
  function setupSwitch(switcher) {
    const key = `layout:${switcher.dataset.viewSwitch}`;
    const buttons = Array.from(switcher.querySelectorAll('[data-layout]'));
    const scope = switcher.closest('[data-layout-scope]') || document;
    const panels = Array.from(scope.querySelectorAll('[data-layout-panel]'));
    const apply = (name, save) => {
      if (!buttons.some((b) => b.dataset.layout === name)) name = buttons[0].dataset.layout;
      buttons.forEach((b) => b.setAttribute('aria-pressed', b.dataset.layout === name ? 'true' : 'false'));
      panels.forEach((p) => { p.hidden = p.dataset.layoutPanel !== name; });
      if (save) { try { localStorage.setItem(key, name); } catch (_) {} }
    };
    buttons.forEach((b) => b.addEventListener('click', () => apply(b.dataset.layout, true)));
    let saved = null;
    try { saved = localStorage.getItem(key); } catch (_) {}
    apply(saved || buttons[0].dataset.layout, false);
  }

  /* A rack dialog opened for an existing rack shows its Delete button,
     pointed at that rack. */
  document.addEventListener('record-dialog:open', (event) => {
    const dialog = event.target;
    const form = dialog.querySelector('form[data-rack-delete]');
    if (!form) return;
    const { data, isNew } = event.detail;
    form.hidden = isNew;
    if (!isNew) form.action = form.dataset.rackDelete.replace('/0/', `/${data.id}/`);
  }, true);

  /* Rack dialog: show what the chosen scheme names the first, a middle and
     the last position, and hide the row/column options in sequential mode. */
  function setupNamingPreview(fieldset) {
    const form = fieldset.closest('form');
    const read = (name) => (form.elements[name] ? form.elements[name].value : undefined);
    const update = () => {
      const rows = Math.max(1, parseInt(read('rows'), 10) || 8);
      const cols = Math.max(1, parseInt(read('cols'), 10) || 10);
      const s = { mode: read('naming_mode'), rows: read('naming_rows'), cols: read('naming_cols'),
                  order: read('naming_order'), separator: read('naming_separator'), start: read('naming_start') };
      const mid = [Math.min(4, rows), Math.min(7, cols)];
      fieldset.querySelector('[data-naming-example]').textContent =
        [cellLabel(1, 1, s, cols), cellLabel(mid[0], mid[1], s, cols), cellLabel(rows, cols, s, cols)].join(' · ');
      fieldset.querySelectorAll('[data-naming-grid]').forEach((el) => { el.hidden = s.mode === 'sequential'; });
    };
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    form.closest('dialog').addEventListener('record-dialog:open', () => setTimeout(update, 0));
    update();
  }

  function init() {
    document.querySelectorAll('[data-rack-naming]').forEach(setupNamingPreview);
    document.querySelectorAll('[data-view-switch]').forEach(setupSwitch);
    document.querySelectorAll('[data-rack-view]').forEach(setup);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
