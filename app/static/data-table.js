/* Reusable data-table behavior.
 *
 * Activate by giving the wrapper a data-table-id attribute. The script
 * auto-attaches on DOMContentLoaded:
 *
 *   <section class="data-table-card" data-table-id="orders">
 *     <div class="dt-toolbar">
 *       <input class="dt-search" />
 *       <button class="dt-btn-sort">…</button>
 *       <button class="dt-btn-hide">…</button>
 *     </div>
 *     <div class="dt-scroll">
 *       <table class="dt" data-resizable="1">…</table>
 *     </div>
 *     <div class="dt-bottom-bar">
 *       <span class="dt-count"></span>
 *       <select class="dt-page-size"><option>50</option>…</select>
 *       <button class="dt-prev"></button><button class="dt-next"></button>
 *       <span class="dt-page-label"></span>
 *     </div>
 *   </section>
 *
 * Search filters rows by the union of all data-* attributes. Sort uses
 * th.dt-sortable[data-sort-key]. Column widths and hidden columns are
 * persisted to localStorage keyed by data-table-id. A row may carry a
 * detail row, <tr data-detail-for="<its data-id>" hidden>, which moves and
 * pages with it (the page toggles its `hidden`).
 */

(function () {
  'use strict';

  // SVG glyphs for column-type icons. Inserted into .dt-col-type spans with
  // a data-icon attribute (date/status/check/list — types where a unicode
  // letter doesn't suffice). Text/number/id are handled by ::before in CSS.
  const ICONS = {
    date: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg>',
    status: '<svg viewBox="0 0 24 24"><path d="M2 12a10 10 0 0 1 10-10"/><path d="M12 2a10 10 0 0 1 10 10"/><path d="M22 12a10 10 0 0 1-10 10"/><path d="M12 22A10 10 0 0 1 2 12"/></svg>',
    check: '<svg viewBox="0 0 24 24"><rect width="18" height="18" x="3" y="3" rx="3"/><path d="m9 12 2 2 4-4"/></svg>',
    list: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/></svg>',
    file: '<svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
  };

  function injectIconSvgs(root) {
    root.querySelectorAll('.dt-col-type[data-icon]').forEach((el) => {
      const kind = el.dataset.icon;
      if (ICONS[kind] && !el.innerHTML.trim()) el.innerHTML = ICONS[kind];
    });
    root.querySelectorAll('.dt-row-icon').forEach((el) => {
      if (!el.innerHTML.trim()) el.innerHTML = ICONS.file;
    });
  }

  // Only one toolbar menu is open at a time.
  let openMenu = null;
  function closeMenus() {
    if (!openMenu) return;
    if (openMenu._anchor) openMenu._anchor.setAttribute('aria-expanded', 'false');
    openMenu.remove();
    openMenu = null;
  }
  document.addEventListener('click', (event) => {
    if (openMenu && !openMenu.contains(event.target)) closeMenus();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeMenus(); });
  window.addEventListener('resize', closeMenus);
  document.addEventListener('scroll', (event) => {
    if (openMenu && !openMenu.contains(event.target)) closeMenus();
  }, true);

  // Per-table state keyed by table id.
  class DataTableController {
    constructor(card) {
      this.card = card;
      this.id = card.dataset.tableId || 'data-table';
      this.table = card.querySelector('table.dt');
      this.tbody = this.table && this.table.tBodies[0];
      this.rows = this.tbody ? Array.from(this.tbody.querySelectorAll('tr[data-id]')) : [];
      this.original = this.rows.slice();
      this.filtered = this.rows.slice();
      this.sortKey = null;
      this.sortDir = 1;
      this.page = 0;
      this.query = '';
      this.quick = null;   // {attr, value} from a .dt-chip
      this.hidden = this._loadHiddenCols();
      this.noun = card.dataset.noun || card.dataset.selectionNoun || 'entry';
      this.nounPlural = card.dataset.nounPlural || card.dataset.selectionNounPlural
        || (this.noun === 'entry' ? 'entries' : this.noun + 's');

      this.search = card.querySelector('.dt-search');
      this.count = card.querySelector('.dt-count');
      this.pageSize = card.querySelector('.dt-page-size');
      this.pageLabel = card.querySelector('.dt-page-label');
      this.prev = card.querySelector('.dt-prev');
      this.next = card.querySelector('.dt-next');
      this.selectAll = card.querySelector('.dt-select-all');

      injectIconSvgs(card);
      this._wireHeaderSort();
      this._wireSearch();
      this._wireSelection();
      this._wirePagination();
      this._wireHideButton();
      this._wireSortButton();
      this._wireChips();
      this._wireResize();
      this._wireExport();
      this._applyHidden();
      this._applyResizedWidths();
      this.render();
    }

    _wireHeaderSort() {
      if (!this.table) return;
      this.table.querySelectorAll('th.dt-sortable').forEach((th) => {
        th.addEventListener('click', (event) => {
          // Ignore clicks that started on the resize handle.
          if (event.target.classList && event.target.classList.contains('dt-col-resize')) return;
          const key = th.dataset.sortKey;
          if (!key) return;
          if (this.sortKey === key) this.sortDir = -this.sortDir;
          else { this.sortKey = key; this.sortDir = 1; }
          this.table.querySelectorAll('th.dt-sortable').forEach((other) => {
            other.classList.remove('dt-sort-asc', 'dt-sort-desc');
          });
          th.classList.add(this.sortDir === 1 ? 'dt-sort-asc' : 'dt-sort-desc');
          const sortBtn = this.card.querySelector('.dt-btn-sort');
          if (sortBtn) sortBtn.classList.add('is-active');
          this._applySort();
          this.render();
        });
      });
    }

    _wireSearch() {
      if (!this.search) return;
      this.search.addEventListener('input', () => {
        this.query = (this.search.value || '').trim().toLowerCase();
        this._refilter();
      });
    }

    /* A row's searchable text: what it shows, its data-* attributes, and
       the current value of any cell you can edit (an input's value is not
       part of textContent, so an editable sheet would otherwise be
       unsearchable). */
    _rowText(tr) {
      let blob = (tr.textContent || '').toLowerCase();
      for (const key in tr.dataset) blob += ' ' + (tr.dataset[key] || '').toLowerCase();
      tr.querySelectorAll('input:not([type=checkbox]):not([type=hidden]), select, textarea').forEach((el) => {
        const shown = el.tagName === 'SELECT' && el.selectedOptions[0] ? el.selectedOptions[0].textContent : '';
        blob += ' ' + String(el.value || '').toLowerCase() + ' ' + shown.toLowerCase();
      });
      return blob;
    }

    _refilter() {
      const q = this.query;
      const quick = this.quick;
      this.filtered = this.original.filter((tr) => {
        if (quick && (tr.dataset[quick.attr] || '') !== quick.value) return false;
        return !q || this._rowText(tr).includes(q);
      });
      if (this.sortKey) this._applySort();
      this.page = 0;
      this.render();
    }

    /* Quick filter chips: <button class="dt-chip" data-dt-filter="active:true">.
       An empty data-dt-filter means "everything". The choice is remembered. */
    _wireChips() {
      const chips = Array.from(this.card.querySelectorAll('.dt-chip[data-dt-filter]'));
      if (!chips.length) return;
      const apply = (chip, save) => {
        chips.forEach((c) => c.setAttribute('aria-pressed', c === chip ? 'true' : 'false'));
        const spec = chip.dataset.dtFilter || '';
        const at = spec.indexOf(':');
        this.quick = at > 0 ? { attr: spec.slice(0, at), value: spec.slice(at + 1) } : null;
        if (save) { try { localStorage.setItem(`dt:${this.id}:filter`, spec); } catch (_) {} }
        this._refilter();
      };
      chips.forEach((chip) => chip.addEventListener('click', () => apply(chip, true)));
      let saved = null;
      try { saved = localStorage.getItem(`dt:${this.id}:filter`); } catch (_) {}
      const initial = chips.find((c) => (c.dataset.dtFilter || '') === saved)
        || chips.find((c) => c.getAttribute('aria-pressed') === 'true');
      if (initial) apply(initial, false);
    }

    /* The value a row sorts by: an editable cell of that name if the row
       has one (so a sort reflects edits made since the page loaded),
       otherwise the data-* attribute. */
    _sortValue(tr, key) {
      const cell = tr.querySelector(`[name="${key}"]`);
      if (cell) return String(cell.value || '');
      return tr.dataset[key] || '';
    }

    _applySort() {
      const key = this.sortKey;
      const dir = this.sortDir;
      this.filtered.sort((a, b) => {
        const av = this._sortValue(a, key);
        const bv = this._sortValue(b, key);
        // Empty cells sink to the bottom whichever way the sort runs.
        if (!av.trim() !== !bv.trim()) return av.trim() ? -1 : 1;
        const aNum = parseFloat(av), bNum = parseFloat(bv);
        if (!isNaN(aNum) && !isNaN(bNum) && av.trim() && bv.trim()) return (aNum - bNum) * dir;
        return av.localeCompare(bv) * dir;
      });
    }

    _wireSelection() {
      if (this.selectAll) {
        this.selectAll.addEventListener('change', () => {
          this.tbody.querySelectorAll('.dt-row-check').forEach((cb) => {
            const tr = cb.closest('tr');
            if (tr && tr.style.display !== 'none') {
              cb.checked = this.selectAll.checked;
              tr.classList.toggle('is-selected', this.selectAll.checked);
            }
          });
        });
      }
      if (this.tbody) {
        this.tbody.addEventListener('change', (event) => {
          if (event.target.classList && event.target.classList.contains('dt-row-check')) {
            const tr = event.target.closest('tr');
            tr && tr.classList.toggle('is-selected', event.target.checked);
          }
        });
      }
    }

    _wirePagination() {
      if (this.pageSize) this.pageSize.addEventListener('change', () => { this.page = 0; this.render(); });
      if (this.prev) this.prev.addEventListener('click', () => { if (this.page > 0) { this.page--; this.render(); } });
      if (this.next) this.next.addEventListener('click', () => { this.page++; this.render(); });
    }

    /* A small popover menu anchored under a toolbar button. Fixed
       positioning, because the card clips overflow. */
    _openMenu(anchor, build) {
      closeMenus();
      const menu = document.createElement('div');
      menu.className = 'dt-menu';
      menu.setAttribute('role', 'menu');
      build(menu);
      document.body.appendChild(menu);
      const rect = anchor.getBoundingClientRect();
      const width = menu.offsetWidth;
      const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
      menu.style.left = `${left}px`;
      menu.style.top = `${rect.bottom + 6}px`;
      menu.style.maxHeight = `${Math.max(160, window.innerHeight - rect.bottom - 24)}px`;
      anchor.setAttribute('aria-expanded', 'true');
      menu._anchor = anchor;
      openMenu = menu;
      return menu;
    }

    _columnLabel(th) {
      const head = th.querySelector('.dt-col-head');
      return (head ? head.textContent : th.textContent || '').replace(/\s+/g, ' ').trim();
    }

    _wireHideButton() {
      const btn = this.card.querySelector('.dt-btn-hide');
      if (!btn || !this.table) return;
      btn.setAttribute('aria-haspopup', 'menu');
      // Pressed only when the columns differ from the page's defaults, so
      // a table that simply starts with empty columns tucked away is calm.
      const defaults = () => Array.from(this.table.tHead.rows[0].cells)
        .map((th, idx) => (th.dataset.defaultHidden === '1' ? idx : -1)).filter((i) => i >= 0);
      const sync = () => {
        const d = defaults();
        const same = d.length === this.hidden.size && d.every((i) => this.hidden.has(i));
        btn.classList.toggle('is-active', !same);
      };
      btn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (openMenu && openMenu._anchor === btn) { closeMenus(); return; }
        const headers = Array.from(this.table.tHead.rows[0].cells);
        this._openMenu(btn, (menu) => {
          const title = document.createElement('div');
          title.className = 'dt-menu-title';
          title.textContent = 'Columns';
          menu.appendChild(title);
          headers.forEach((th, idx) => {
            const label = this._columnLabel(th);
            if (!label) return;   // checkbox and action columns
            const row = document.createElement('label');
            row.className = 'dt-menu-item';
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.checked = !this.hidden.has(idx);
            box.addEventListener('change', () => {
              if (box.checked) this.hidden.delete(idx); else this.hidden.add(idx);
              this._saveHiddenCols();
              this._applyHidden();
              sync();
            });
            row.append(box, document.createTextNode(label));
            menu.appendChild(row);
          });
          const all = document.createElement('button');
          all.type = 'button';
          all.className = 'dt-menu-action';
          all.textContent = 'Show all columns';
          all.addEventListener('click', () => {
            this.hidden.clear();
            this._saveHiddenCols();
            this._applyHidden();
            sync();
            closeMenus();
          });
          menu.appendChild(all);
        });
      });
      sync();
    }

    _wireSortButton() {
      const btn = this.card.querySelector('.dt-btn-sort');
      if (!btn || !this.table) return;
      btn.setAttribute('aria-haspopup', 'menu');
      btn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (openMenu && openMenu._anchor === btn) { closeMenus(); return; }
        const headers = Array.from(this.table.querySelectorAll('th.dt-sortable'))
          .filter((th) => th.style.display !== 'none');
        if (!headers.length) return;
        this._openMenu(btn, (menu) => {
          const title = document.createElement('div');
          title.className = 'dt-menu-title';
          title.textContent = 'Sort by';
          menu.appendChild(title);
          headers.forEach((th) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'dt-menu-item';
            const active = this.sortKey === th.dataset.sortKey;
            item.classList.toggle('is-active', active);
            const arrow = active ? (this.sortDir === 1 ? ' ↑' : ' ↓') : '';
            item.textContent = this._columnLabel(th) + arrow;
            item.addEventListener('click', () => { th.click(); closeMenus(); });
            menu.appendChild(item);
          });
          if (this.sortKey) {
            const clear = document.createElement('button');
            clear.type = 'button';
            clear.className = 'dt-menu-action';
            clear.textContent = 'Original order';
            clear.addEventListener('click', () => {
              this.sortKey = null;
              this.table.querySelectorAll('th.dt-sortable').forEach((o) => o.classList.remove('dt-sort-asc', 'dt-sort-desc'));
              btn.classList.remove('is-active');
              this._refilter();
              closeMenus();
            });
            menu.appendChild(clear);
          }
        });
      });
    }

    _applyHidden() {
      if (!this.table) return;
      Array.from(this.table.tHead.rows).forEach((row) => {
        Array.from(row.cells).forEach((th, idx) => { th.style.display = this.hidden.has(idx) ? 'none' : ''; });
      });
      this.rows.forEach((tr) => {
        Array.from(tr.cells).forEach((td, idx) => {
          td.style.display = this.hidden.has(idx) ? 'none' : '';
        });
      });
    }

    /* Saved choice if there is one, else the columns the page marks
       data-default-hidden (e.g. transgene columns nobody has filled). */
    _loadHiddenCols() {
      try {
        const raw = localStorage.getItem(`dt:${this.id}:hidden`);
        if (raw) return new Set(JSON.parse(raw));
      } catch (_) { /* storage unavailable */ }
      const defaults = new Set();
      if (this.table && this.table.tHead) {
        Array.from(this.table.tHead.rows[0].cells).forEach((th, idx) => {
          if (th.dataset.defaultHidden === '1') defaults.add(idx);
        });
      }
      return defaults;
    }

    _saveHiddenCols() {
      try { localStorage.setItem(`dt:${this.id}:hidden`, JSON.stringify([...this.hidden])); } catch (_) {}
    }

    // -------- column resize ----------------------------------------------
    _wireResize() {
      if (!this.table || this.table.dataset.resizable !== '1') return;
      const headers = Array.from(this.table.tHead.rows[0].cells);
      headers.forEach((th, idx) => {
        if (idx === headers.length - 1) return; // no handle on last col
        const handle = document.createElement('div');
        handle.className = 'dt-col-resize';
        handle.dataset.colIndex = idx;
        th.appendChild(handle);
        handle.addEventListener('mousedown', (event) => this._startResize(event, th, idx));
      });
    }

    _startResize(event, th, idx) {
      event.preventDefault();
      event.stopPropagation();
      const startX = event.clientX;
      const startWidth = th.getBoundingClientRect().width;
      this.table.classList.add('is-resizing');
      const handle = event.currentTarget; // the resize handle, not pseudo
      handle.classList.add('is-dragging');
      const onMove = (ev) => {
        const delta = ev.clientX - startX;
        const newWidth = Math.max(48, startWidth + delta);
        th.style.width = `${newWidth}px`;
        th.style.minWidth = `${newWidth}px`;
      };
      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        this.table.classList.remove('is-resizing');
        handle.classList.remove('is-dragging');
        this._saveColWidth(idx, parseInt(th.style.width || '', 10));
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    }

    _saveColWidth(idx, width) {
      if (!width || isNaN(width)) return;
      try {
        const raw = localStorage.getItem(`dt:${this.id}:widths`) || '{}';
        const map = JSON.parse(raw);
        map[idx] = width;
        localStorage.setItem(`dt:${this.id}:widths`, JSON.stringify(map));
      } catch (_) {}
    }

    _applyResizedWidths() {
      if (!this.table || this.table.dataset.resizable !== '1') return;
      try {
        const raw = localStorage.getItem(`dt:${this.id}:widths`);
        if (!raw) return;
        const map = JSON.parse(raw);
        const headers = Array.from(this.table.tHead.rows[0].cells);
        Object.keys(map).forEach((idxStr) => {
          const idx = parseInt(idxStr, 10);
          const width = map[idxStr];
          if (headers[idx] && width) {
            headers[idx].style.width = `${width}px`;
            headers[idx].style.minWidth = `${width}px`;
          }
        });
      } catch (_) {}
    }

    _renderNoMatch(show) {
      if (!this.tbody) return;
      let row = this.tbody.querySelector('tr.dt-nomatch');
      if (!show) { if (row) row.remove(); return; }
      if (!row) {
        row = document.createElement('tr');
        row.className = 'dt-nomatch';
        const cell = document.createElement('td');
        cell.className = 'dt-empty';
        cell.colSpan = this.table.tHead.rows[0].cells.length;
        cell.appendChild(document.createElement('span')).className = 'dt-empty-msg';
        row.appendChild(cell);
        this.tbody.appendChild(row);
      }
      row.firstChild.firstChild.textContent = this.query
        ? `Nothing matches “${this.search.value.trim()}”.`
        : `No ${this.nounPlural} match this filter.`;
    }

    // -------- export & print ---------------------------------------------
    /* What a cell shows: an editable cell's value (a select's chosen
       label), otherwise its text. */
    _cellText(td) {
      const field = td.querySelector('select, textarea, input:not([type=checkbox]):not([type=hidden]):not([type=radio])');
      if (field) {
        if (field.tagName === 'SELECT') return field.selectedOptions[0] ? field.selectedOptions[0].textContent.trim() : '';
        return String(field.value || '').trim();
      }
      return (td.textContent || '').replace(/\s+/g, ' ').trim();
    }

    /* Columns worth exporting: visible, and not the tick-box or actions
       column. */
    _exportColumns() {
      const headers = Array.from(this.table.tHead.rows[0].cells);
      return headers.map((th, idx) => ({ th, idx })).filter(({ th, idx }) => {
        if (this.hidden.has(idx)) return false;
        if (th.querySelector('input[type=checkbox]')) return false;
        const label = (th.textContent || '').replace(/\s+/g, ' ').trim();
        return label && label !== 'Actions';
      }).map(({ th, idx }) => ({ idx, label: (th.textContent || '').replace(/\s+/g, ' ').trim() }));
    }

    /* Toolbar buttons .dt-btn-export (CSV of every row the filters and
       search let through, not just this page) and .dt-btn-print. */
    _wireExport() {
      const exportBtn = this.card.querySelector('.dt-btn-export');
      if (exportBtn) {
        exportBtn.addEventListener('click', () => {
          const columns = this._exportColumns();
          const quote = (v) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
          const lines = [columns.map((c) => quote(c.label)).join(',')];
          this.filtered.forEach((tr) => {
            lines.push(columns.map((c) => quote(tr.cells[c.idx] ? this._cellText(tr.cells[c.idx]) : '')).join(','));
          });
          const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
          const link = document.createElement('a');
          const stamp = new Date().toISOString().slice(0, 10);
          link.href = URL.createObjectURL(blob);
          link.download = `${this.card.dataset.exportName || this.id}-${stamp}.csv`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        });
      }
      const printBtn = this.card.querySelector('.dt-btn-print');
      if (printBtn) {
        printBtn.addEventListener('click', () => {
          // Print every filtered row, then put the page back.
          const size = this.pageSize;
          const before = size ? size.value : null;
          if (size) {
            if (!Array.from(size.options).some((o) => o.value === '100000')) size.add(new Option('All', '100000'));
            size.value = '100000';
          }
          this.page = 0;
          this.render();
          document.body.classList.add('is-printing-sheet');
          this.card.classList.add('is-print-target');
          const restore = () => {
            document.body.classList.remove('is-printing-sheet');
            this.card.classList.remove('is-print-target');
            if (size && before !== null) size.value = before;
            this.render();
            window.removeEventListener('afterprint', restore);
          };
          window.addEventListener('afterprint', restore);
          window.print();
        });
      }
    }

    // -------- render -----------------------------------------------------
    render() {
      const size = this.pageSize ? parseInt(this.pageSize.value, 10) : 50;
      const start = this.page * size;
      const end = start + size;
      this.rows.forEach((tr) => { tr.style.display = 'none'; });
      this.filtered.slice(start, end).forEach((tr) => { tr.style.display = ''; });
      const total = this.filtered.length;
      if (this.count) {
        const noun = total === 1 ? this.noun : this.nounPlural;
        this.count.textContent = `${total} ${noun}${total !== this.rows.length ? ` of ${this.rows.length}` : ''}`;
      }
      this._renderNoMatch(total === 0 && this.rows.length > 0);
      // A detail row (<tr data-detail-for="<row's data-id>">, e.g. a cage's
      // mice) follows its row through sorting and paging, and is shown
      // only while its row is; its own `hidden` still opens and closes it.
      const details = new Map();
      this.tbody.querySelectorAll(':scope > tr[data-detail-for]').forEach((d) => details.set(d.dataset.detailFor, d));
      this.filtered.forEach((tr) => {
        this.tbody.appendChild(tr);
        const detail = details.get(tr.dataset.id);
        if (detail) this.tbody.appendChild(detail);
      });
      details.forEach((detail, id) => {
        const owner = this.tbody.querySelector(`:scope > tr[data-id="${id}"]`);
        detail.style.display = owner && owner.style.display !== 'none' ? '' : 'none';
      });
      const totalPages = Math.max(1, Math.ceil(total / size));
      if (this.pageLabel) this.pageLabel.textContent = `Page ${this.page + 1} of ${totalPages}`;
      if (this.prev) this.prev.disabled = this.page === 0;
      if (this.next) this.next.disabled = this.page >= totalPages - 1;
    }
  }

  // ---------------------------------------------------------------------
  // Standalone resize binding. Works on any <table data-resizable="1"> that
  // isn't already managed by a DataTableController. The table id is taken
  // from the `data-resize-id` attribute (or the element id) — that's the
  // key used in localStorage for persisted widths.
  // ---------------------------------------------------------------------
  function makeTableResizable(table) {
    if (table.dataset.dtResizeBound === '1') return;
    table.dataset.dtResizeBound = '1';
    const tableId = table.dataset.resizeId || table.id || 'unnamed';
    const headers = Array.from(table.tHead && table.tHead.rows[0] ? table.tHead.rows[0].cells : []);
    if (!headers.length) return;

    // Apply persisted widths.
    try {
      const raw = localStorage.getItem(`dt:${tableId}:widths`);
      if (raw) {
        const map = JSON.parse(raw);
        Object.keys(map).forEach((idxStr) => {
          const idx = parseInt(idxStr, 10);
          if (headers[idx] && map[idxStr]) {
            headers[idx].style.width = `${map[idxStr]}px`;
            headers[idx].style.minWidth = `${map[idxStr]}px`;
          }
        });
      }
    } catch (_) {}

    headers.forEach((th, idx) => {
      if (idx === headers.length - 1) return;
      // Skip if a handle is already there (e.g. DataTableController added it).
      if (th.querySelector('.dt-col-resize')) return;
      const handle = document.createElement('div');
      handle.className = 'dt-col-resize';
      handle.dataset.colIndex = idx;
      th.appendChild(handle);
      handle.addEventListener('mousedown', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const startX = event.clientX;
        const startWidth = th.getBoundingClientRect().width;
        table.classList.add('is-resizing');
        handle.classList.add('is-dragging');
        const onMove = (ev) => {
          const delta = ev.clientX - startX;
          const newWidth = Math.max(40, startWidth + delta);
          th.style.width = `${newWidth}px`;
          th.style.minWidth = `${newWidth}px`;
        };
        const onUp = () => {
          document.removeEventListener('mousemove', onMove);
          document.removeEventListener('mouseup', onUp);
          table.classList.remove('is-resizing');
          handle.classList.remove('is-dragging');
          const width = parseInt(th.style.width || '', 10);
          if (width) {
            try {
              const raw = localStorage.getItem(`dt:${tableId}:widths`) || '{}';
              const map = JSON.parse(raw);
              map[idx] = width;
              localStorage.setItem(`dt:${tableId}:widths`, JSON.stringify(map));
            } catch (_) {}
          }
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
      });
    });
  }

  function init() {
    document.querySelectorAll('.data-table-card[data-table-id]').forEach((card) => {
      // Avoid double-initializing if data-table.js is loaded twice.
      if (card.dataset.dtBound === '1') return;
      card.dataset.dtBound = '1';
      new DataTableController(card);
    });
    // Bind resize to any standalone <table data-resizable="1"> not inside a
    // controlled .data-table-card (which already handles resize itself).
    document.querySelectorAll('table[data-resizable="1"]').forEach((table) => {
      if (table.closest('.data-table-card[data-table-id]')) return;
      makeTableResizable(table);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for templates that want to re-init after dynamic DOM changes.
  window.BiomanagerDataTable = { init, makeTableResizable };
})();
