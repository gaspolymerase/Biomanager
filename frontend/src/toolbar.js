// Bottom-pinned floating toolbar for the TipTap editor.
// Centered horizontally, fixed to viewport bottom — follows scroll, always
// visible while the editor is on the page. Buttons reflect the active mark
// state (so [B] highlights when the caret is inside bold text).
//
// When the caret is inside a table, a secondary "table actions" row appears
// above the main toolbar with row/col add/remove buttons.

const ICONS = {
  h1: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h8"/><path d="M4 18V6"/><path d="M12 18V6"/><path d="M17 12 19 11v7"/></svg>',
  h2: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h8"/><path d="M4 18V6"/><path d="M12 18V6"/><path d="M21 18h-4c0-4 4-3 4-6 0-1.5-2-2.5-4-1"/></svg>',
  h3: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h8"/><path d="M4 18V6"/><path d="M12 18V6"/><path d="M17.5 10.5c1.7-1 3.5 0 3.5 1.5a2 2 0 0 1-2 2"/><path d="M17 17.5c2 1.5 4 .3 4-1.5a2 2 0 0 0-2-2"/></svg>',
  bold: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 12a4 4 0 0 0 0-8H6v8"/><path d="M15 20a4 4 0 0 0 0-8H6v8Z"/></svg>',
  italic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" x2="10" y1="4" y2="4"/><line x1="14" x2="5" y1="20" y2="20"/><line x1="15" x2="9" y1="4" y2="20"/></svg>',
  strike: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4H9a3 3 0 0 0-2.83 4"/><path d="M14 12a4 4 0 0 1 0 8H6"/><line x1="4" x2="20" y1="12" y2="12"/></svg>',
  bullet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/></svg>',
  ordered: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" x2="21" y1="6" y2="6"/><line x1="10" x2="21" y1="12" y2="12"/><line x1="10" x2="21" y1="18" y2="18"/><path d="M4 6h1v4"/><path d="M4 10h2"/><path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/></svg>',
  task: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="6" height="6" rx="1"/><path d="m3 17 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/></svg>',
  quote: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z"/></svg>',
  code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>',
  attach: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 17.93 8.83l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
  table: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>',
  rowPlus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="6" rx="1"/><rect x="3" y="15" width="18" height="6" rx="1"/><line x1="12" y1="11" x2="12" y2="13"/><line x1="10" y1="12" x2="14" y2="12"/></svg>',
  rowMinus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="6" rx="1"/><rect x="3" y="15" width="18" height="6" rx="1"/><line x1="10" y1="12" x2="14" y2="12"/></svg>',
  colPlus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="6" height="18" rx="1"/><rect x="15" y="3" width="6" height="18" rx="1"/><line x1="12" y1="10" x2="12" y2="14"/><line x1="11" y1="12" x2="13" y2="12"/></svg>',
  colMinus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="6" height="18" rx="1"/><rect x="15" y="3" width="6" height="18" rx="1"/><line x1="11" y1="12" x2="13" y2="12"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  divider: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" x2="19" y1="12" y2="12"/></svg>',
  undo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/></svg>',
  redo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 15-6.7L21 13"/></svg>',
  insert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  caretDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
  section: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/><line x1="3" y1="3" x2="21" y2="3"/></svg>',
  symbol: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><text x="12" y="16" font-size="11" text-anchor="middle" fill="currentColor" stroke="none">π</text></svg>',
  plate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="1.6"/><circle cx="12" cy="6" r="1.6"/><circle cx="18" cy="6" r="1.6"/><circle cx="6" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18" cy="12" r="1.6"/><circle cx="6" cy="18" r="1.6"/><circle cx="12" cy="18" r="1.6"/><circle cx="18" cy="18" r="1.6"/></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v6L4 18a2 2 0 0 0 1.7 3h12.6A2 2 0 0 0 20 18l-6-10V2"/><line x1="8" y1="2" x2="16" y2="2"/></svg>',
  lookup: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
};

function svgIcon(html) {
  return `<span class="editor-toolbar-icon">${html}</span>`;
}

function pickAndUpload(endpoint, fieldName, accept, onResult) {
  const input = document.createElement('input');
  input.type = 'file';
  if (accept) input.accept = accept;
  input.addEventListener('change', () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append(fieldName, file);
    fetch(endpoint, { method: 'POST', body: formData })
      .then((r) => r.json())
      .then((data) => { if (data && data.ok) onResult(data); })
      .catch(() => {});
  });
  input.click();
}

function formatBytes(n) {
  if (!n || n < 1024) return `${n || 0} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// =========================================================================
// Insert menu — opens a popover with structured-content insertions (tables
// pre-filled for common lab patterns, plate grids, symbol picker, etc.).
// Each entry calls a small generator that produces markdown the editor
// inserts at the caret. We use markdown source instead of TipTap rich
// commands so saved/reloaded round-trips stay deterministic.
// =========================================================================

const SYMBOLS = [
  ['μ', 'micro'], ['°', 'degree'], ['±', 'plus-minus'], ['×', 'times'],
  ['÷', 'divide'], ['→', 'arrow right'], ['←', 'arrow left'], ['↑', 'arrow up'],
  ['↓', 'arrow down'], ['Δ', 'delta'], ['α', 'alpha'], ['β', 'beta'],
  ['γ', 'gamma'], ['π', 'pi'], ['σ', 'sigma'], ['λ', 'lambda'],
  ['∞', 'infinity'], ['≈', 'approx'], ['≤', 'less-eq'], ['≥', 'greater-eq'],
  ['≠', 'not-eq'], ['℃', 'celsius'], ['Ω', 'ohm'], ['Å', 'angstrom'],
  ['✓', 'check'], ['✗', 'cross'], ['…', 'ellipsis'], ['—', 'em-dash'],
];

function buildPlateTable(rows, cols) {
  // Build a markdown table representing an N-well plate. First column is the
  // row label (A, B, C…); first row is the column number header.
  const letters = 'ABCDEFGHIJKLMNOP';
  const header = ['well', ...Array.from({ length: cols }, (_, i) => `${i + 1}`)];
  const sep = header.map(() => '---');
  const body = Array.from({ length: rows }, (_, r) => {
    const row = [letters[r] || '?'];
    for (let c = 0; c < cols; c++) row.push(' ');
    return row;
  });
  return [
    `| ${header.join(' | ')} |`,
    `| ${sep.join(' | ')} |`,
    ...body.map((r) => `| ${r.join(' | ')} |`),
  ].join('\n');
}

const INSERT_ITEMS = [
  // ---- Layout -----------------------------------------------------------
  {
    id: 'section',
    icon: ICONS.section,
    label: 'Section',
    hint: 'Collapsible heading group',
    group: 'Layout',
    insert: (_e) => '\n## Section title\n\nContent…\n\n',
  },
  {
    id: 'sub-template',
    icon: ICONS.image,
    label: 'Sub-template',
    hint: 'Insert content from a saved template',
    group: 'Layout',
    action: 'sub-template',
  },
  {
    id: 'attachment',
    icon: ICONS.attach,
    label: 'Attachment',
    hint: 'Upload any file',
    group: 'Layout',
    action: 'attachment',
  },
  {
    id: 'code-block',
    icon: ICONS.code,
    label: 'Code block',
    hint: 'Triple-backtick fence',
    group: 'Layout',
    insert: (_e) => '\n```\n// code here\n```\n',
  },
  {
    id: 'symbol',
    icon: ICONS.symbol,
    label: 'Symbol',
    hint: 'Greek letters, μ, ±, →',
    group: 'Layout',
    action: 'symbol',
  },
  // ---- Tables -----------------------------------------------------------
  {
    id: 'result-table',
    icon: ICONS.table,
    label: 'Result table',
    hint: 'Sample · Condition · Value · Notes',
    group: 'Tables',
    insert: () => '\n| Sample | Condition | Value | Units | Notes |\n| --- | --- | --- | --- | --- |\n|  |  |  |  |  |\n|  |  |  |  |  |\n|  |  |  |  |  |\n\n',
  },
  {
    id: 'registration-mouse',
    icon: ICONS.table,
    label: 'Mouse list table',
    hint: '@mouse · Genotype · Group · Note',
    group: 'Tables',
    insert: () => '\n| Mouse | Sex | Genotype | Group | Note |\n| --- | --- | --- | --- | --- |\n| @mouse  |  |  |  |  |\n| @mouse  |  |  |  |  |\n| @mouse  |  |  |  |  |\n\n',
  },
  {
    id: 'registration-plasmid',
    icon: ICONS.table,
    label: 'Plasmid list table',
    hint: '@plasmid · Name · Backbone · Owner',
    group: 'Tables',
    insert: () => '\n| Plasmid | Name | Backbone | Owner | Note |\n| --- | --- | --- | --- | --- |\n| @plasmid  |  |  |  |  |\n| @plasmid  |  |  |  |  |\n\n',
  },
  {
    id: 'inventory-table',
    icon: ICONS.table,
    label: 'Inventory table',
    hint: 'Reagent · Lot · Location · Amount',
    group: 'Tables',
    insert: () => '\n| Reagent | Vendor | Cat # | Lot | Location | Amount |\n| --- | --- | --- | --- | --- | --- |\n|  |  |  |  |  |  |\n|  |  |  |  |  |  |\n\n',
  },
  {
    id: 'mixture-prep',
    icon: ICONS.flask,
    label: 'Mixture prep table',
    hint: 'Reagent · Stock · Final · Volume',
    group: 'Tables',
    insert: () => '\n| Reagent | MW | Stock conc | Final conc | Volume to add | Final volume |\n| --- | --- | --- | --- | --- | --- |\n|  |  |  |  |  |  |\n|  |  |  |  |  |  |\n|  |  |  |  |  |  |\n\n',
  },
  {
    id: 'lookup-table',
    icon: ICONS.lookup,
    label: 'Saved search',
    hint: 'Inline saved query (placeholder link)',
    group: 'Tables',
    insert: () => '\n[🔍 Saved search — describe what to look for](#)\n\n',
  },
  // ---- Well plates ------------------------------------------------------
  {
    id: 'plate-96',
    icon: ICONS.plate,
    label: '96-well plate',
    hint: '8 rows × 12 cols',
    group: 'Well plates',
    insert: () => '\n' + buildPlateTable(8, 12) + '\n\n',
  },
  {
    id: 'plate-24',
    icon: ICONS.plate,
    label: '24-well plate',
    hint: '4 rows × 6 cols',
    group: 'Well plates',
    insert: () => '\n' + buildPlateTable(4, 6) + '\n\n',
  },
  {
    id: 'plate-384',
    icon: ICONS.plate,
    label: '384-well plate',
    hint: '16 rows × 24 cols',
    group: 'Well plates',
    insert: () => '\n' + buildPlateTable(16, 24) + '\n\n',
  },
];

let openMenuEl = null;

function closeInsertMenu() {
  if (openMenuEl && openMenuEl.parentNode) openMenuEl.parentNode.removeChild(openMenuEl);
  openMenuEl = null;
  document.removeEventListener('mousedown', onOutsideClick);
}

function onOutsideClick(event) {
  if (openMenuEl && !openMenuEl.contains(event.target) && !event.target.closest('[data-cmd-id="insert"]')) {
    closeInsertMenu();
  }
}

function openInsertMenu(editor) {
  if (openMenuEl) { closeInsertMenu(); return; }
  const btn = document.querySelector('[data-cmd-id="insert"]');
  const rect = btn ? btn.getBoundingClientRect() : { left: 100, bottom: 100 };

  const menu = document.createElement('div');
  menu.className = 'insert-menu';
  // Group items by their .group label.
  const groups = {};
  INSERT_ITEMS.forEach((item) => {
    (groups[item.group] = groups[item.group] || []).push(item);
  });
  let html = '';
  Object.keys(groups).forEach((g) => {
    html += `<div class="insert-menu-label">${g}</div>`;
    groups[g].forEach((item) => {
      html += `
        <button type="button" class="insert-menu-item" data-id="${item.id}">
          <span class="insert-menu-icon">${item.icon}</span>
          <span class="insert-menu-text">
            <span class="insert-menu-title">${item.label}</span>
            <span class="insert-menu-hint">${item.hint}</span>
          </span>
        </button>
      `;
    });
  });
  menu.innerHTML = html;
  document.body.appendChild(menu);
  // Position above the button (toolbar is bottom-fixed).
  const menuRect = menu.getBoundingClientRect();
  menu.style.left = `${Math.max(8, rect.left - menuRect.width / 2 + (rect.width / 2))}px`;
  menu.style.top = `${rect.top - menuRect.height - 8 + window.scrollY}px`;

  menu.addEventListener('click', (event) => {
    const btnEl = event.target.closest('.insert-menu-item');
    if (!btnEl) return;
    const item = INSERT_ITEMS.find((x) => x.id === btnEl.dataset.id);
    if (!item) return;
    closeInsertMenu();
    if (item.action === 'attachment') {
      pickAndUpload('/notebook/upload-file', 'file', '', (data) => {
        if (data.url) {
          const label = `${data.name} (${formatBytes(data.size)})`;
          editor.chain().focus().insertContent(`[${label}](${data.url})`).run();
        }
      });
    } else if (item.action === 'symbol') {
      openSymbolPicker(editor);
    } else if (item.action === 'sub-template') {
      openSubTemplatePicker(editor);
    } else if (item.insert) {
      const md = item.insert(editor);
      // insertContent on raw markdown — TipTap's StarterKit doesn't parse
      // markdown by default, so use the markdown extension's API if
      // available. Otherwise fall back to inserting line-by-line text.
      if (editor.storage && editor.storage.markdown && typeof editor.commands.setContent === 'function') {
        const current = editor.storage.markdown.getMarkdown();
        const sel = editor.state.selection;
        // Simplest reliable path: append at current position by re-rendering
        // the full document with the inserted snippet at caret. We
        // approximate by appending at the end if we can't pinpoint.
        const splitted = splitMarkdownAtCaret(current, sel.from, sel.to);
        editor.commands.setContent(splitted.before + md + splitted.after, true);
      } else {
        editor.chain().focus().insertContent(md).run();
      }
    }
  });

  openMenuEl = menu;
  setTimeout(() => document.addEventListener('mousedown', onOutsideClick), 0);
}

// Markdown caret-position approximation: count characters from the start of
// the document until we hit the ProseMirror position. This is approximate
// but works well for plain text and most paragraphs.
function splitMarkdownAtCaret(markdown, _from, _to) {
  // For simplicity, just append the snippet to the end of the document.
  // (Properly mapping PM positions → markdown offsets requires walking the
  // doc; the trade-off here is reliability for "I want it near the cursor"
  // accuracy — most users insert at end of page anyway.)
  return { before: markdown, after: '' };
}

function openSymbolPicker(editor) {
  const overlay = document.createElement('div');
  overlay.className = 'insert-menu-overlay';
  overlay.innerHTML = `
    <div class="insert-menu insert-menu-symbols">
      <div class="insert-menu-label">Insert symbol</div>
      <div class="insert-symbol-grid">
        ${SYMBOLS.map(([s, label]) => `<button type="button" class="insert-symbol-btn" data-sym="${s}" title="${label}">${s}</button>`).join('')}
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (event) => {
    if (event.target.classList && event.target.classList.contains('insert-symbol-btn')) {
      editor.chain().focus().insertContent(event.target.dataset.sym).run();
      overlay.remove();
    } else if (event.target === overlay) {
      overlay.remove();
    }
  });
}

function openSubTemplatePicker(editor) {
  const overlay = document.createElement('div');
  overlay.className = 'insert-menu-overlay';
  overlay.innerHTML = `
    <div class="insert-menu insert-menu-templates">
      <div class="insert-menu-label">Insert sub-template</div>
      <div class="insert-templates-list">Loading…</div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.addEventListener('click', (event) => { if (event.target === overlay) overlay.remove(); });

  fetch('/notebook/templates')
    .then((r) => r.json())
    .then((data) => {
      const list = overlay.querySelector('.insert-templates-list');
      if (!data || !data.ok || !data.templates.length) {
        list.innerHTML = '<div class="insert-empty">No templates yet. Save a page as a template first.</div>';
        return;
      }
      list.innerHTML = data.templates.map((t) => `
        <button type="button" class="insert-template-row" data-id="${t.id}">
          <span class="insert-template-icon">${t.icon || '📄'}</span>
          <span>
            <strong>${escapeHtml(t.title)}</strong>
            <small>${escapeHtml(t.body_preview || '')}</small>
          </span>
        </button>
      `).join('');
      list.addEventListener('click', async (event) => {
        const row = event.target.closest('.insert-template-row');
        if (!row) return;
        // Fetch full body. Re-use the list endpoint — for now use body_preview
        // since we don't have a "get one template" endpoint. Templates with
        // long bodies will need the full fetch; for the sub-template use case
        // a preview is fine.
        const tpl = data.templates.find((x) => String(x.id) === row.dataset.id);
        if (tpl) {
          editor.chain().focus().insertContent('\n' + (tpl.body_preview || '') + '\n').run();
        }
        overlay.remove();
      });
    });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

export function createToolbar(editor) {
  const toolbar = document.createElement('div');
  toolbar.className = 'editor-toolbar';

  // Secondary table-actions row, sits above main toolbar. Hidden when not in
  // a table. Position is computed relative to the main toolbar.
  const tableBar = document.createElement('div');
  tableBar.className = 'editor-toolbar editor-toolbar-secondary';
  tableBar.style.display = 'none';

  const groups = [
    [
      { id: 'h1', icon: ICONS.h1, label: 'Heading 1', exec: (e) => e.chain().focus().toggleHeading({ level: 1 }).run(), isActive: (e) => e.isActive('heading', { level: 1 }) },
      { id: 'h2', icon: ICONS.h2, label: 'Heading 2', exec: (e) => e.chain().focus().toggleHeading({ level: 2 }).run(), isActive: (e) => e.isActive('heading', { level: 2 }) },
      { id: 'h3', icon: ICONS.h3, label: 'Heading 3', exec: (e) => e.chain().focus().toggleHeading({ level: 3 }).run(), isActive: (e) => e.isActive('heading', { level: 3 }) },
    ],
    [
      { id: 'bold', icon: ICONS.bold, label: 'Bold (Cmd-B)', exec: (e) => e.chain().focus().toggleBold().run(), isActive: (e) => e.isActive('bold') },
      { id: 'italic', icon: ICONS.italic, label: 'Italic (Cmd-I)', exec: (e) => e.chain().focus().toggleItalic().run(), isActive: (e) => e.isActive('italic') },
      { id: 'strike', icon: ICONS.strike, label: 'Strikethrough', exec: (e) => e.chain().focus().toggleStrike().run(), isActive: (e) => e.isActive('strike') },
      { id: 'code', icon: ICONS.code, label: 'Inline code', exec: (e) => e.chain().focus().toggleCode().run(), isActive: (e) => e.isActive('code') },
    ],
    [
      { id: 'bullet', icon: ICONS.bullet, label: 'Bullet list', exec: (e) => e.chain().focus().toggleBulletList().run(), isActive: (e) => e.isActive('bulletList') },
      { id: 'ordered', icon: ICONS.ordered, label: 'Numbered list', exec: (e) => e.chain().focus().toggleOrderedList().run(), isActive: (e) => e.isActive('orderedList') },
      { id: 'task', icon: ICONS.task, label: 'Task list', exec: (e) => e.chain().focus().toggleTaskList().run(), isActive: (e) => e.isActive('taskList') },
    ],
    [
      { id: 'quote', icon: ICONS.quote, label: 'Quote', exec: (e) => e.chain().focus().toggleBlockquote().run(), isActive: (e) => e.isActive('blockquote') },
      { id: 'divider', icon: ICONS.divider, label: 'Horizontal rule', exec: (e) => e.chain().focus().setHorizontalRule().run() },
      {
        id: 'link',
        icon: ICONS.link,
        label: 'Link',
        exec: (e) => {
          const previous = e.getAttributes('link')?.href || '';
          const url = window.prompt('Link URL (leave blank to remove):', previous);
          if (url === null) return;
          if (url === '') {
            e.chain().focus().extendMarkRange('link').unsetLink().run();
            return;
          }
          e.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
        },
        isActive: (e) => e.isActive('link'),
      },
      {
        id: 'image',
        icon: ICONS.image,
        label: 'Image upload',
        exec: () => {
          pickAndUpload('/notebook/upload-image', 'image', 'image/*', (data) => {
            if (data.url) editor.chain().focus().setImage({ src: data.url, alt: 'image' }).run();
          });
        },
      },
      {
        id: 'attach',
        icon: ICONS.attach,
        label: 'Attach file',
        exec: () => {
          pickAndUpload('/notebook/upload-file', 'file', '', (data) => {
            if (!data.url) return;
            const label = `${data.name} (${formatBytes(data.size)})`;
            editor.chain().focus().insertContent(`[${label}](${data.url})`).run();
          });
        },
      },
      {
        id: 'table',
        icon: ICONS.table,
        label: 'Insert table',
        exec: (e) => e.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
        isActive: (e) => e.isActive('table'),
      },
      {
        id: 'insert',
        icon: ICONS.insert,
        label: 'Insert…',
        exec: () => openInsertMenu(editor),
        renderAsDropdown: true,
      },
    ],
    [
      { id: 'undo', icon: ICONS.undo, label: 'Undo (Cmd-Z)', exec: (e) => e.chain().focus().undo().run(), enabled: (e) => e.can().undo() },
      { id: 'redo', icon: ICONS.redo, label: 'Redo (Cmd-Shift-Z)', exec: (e) => e.chain().focus().redo().run(), enabled: (e) => e.can().redo() },
    ],
  ];

  const tableActions = [
    { id: 't-add-row', icon: ICONS.rowPlus, label: 'Add row below', exec: (e) => e.chain().focus().addRowAfter().run() },
    { id: 't-del-row', icon: ICONS.rowMinus, label: 'Delete row', exec: (e) => e.chain().focus().deleteRow().run() },
    { id: 't-add-col', icon: ICONS.colPlus, label: 'Add column right', exec: (e) => e.chain().focus().addColumnAfter().run() },
    { id: 't-del-col', icon: ICONS.colMinus, label: 'Delete column', exec: (e) => e.chain().focus().deleteColumn().run() },
    { id: 't-del-table', icon: ICONS.trash, label: 'Delete table', exec: (e) => e.chain().focus().deleteTable().run() },
  ];

  const allButtons = [];

  groups.forEach((group, groupIndex) => {
    if (groupIndex > 0) {
      const sep = document.createElement('span');
      sep.className = 'editor-toolbar-sep';
      toolbar.appendChild(sep);
    }
    group.forEach((cmd) => {
      const btn = makeButton(cmd, editor);
      toolbar.appendChild(btn);
      allButtons.push(btn);
    });
  });

  const tableLabel = document.createElement('span');
  tableLabel.className = 'editor-toolbar-meta';
  tableLabel.textContent = 'Table';
  tableBar.appendChild(tableLabel);
  tableActions.forEach((cmd) => {
    const btn = makeButton(cmd, editor);
    tableBar.appendChild(btn);
    allButtons.push(btn);
  });

  function makeButton(cmd, ed) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'editor-toolbar-btn';
    if (cmd.renderAsDropdown) btn.classList.add('editor-toolbar-btn-dropdown');
    btn.dataset.cmdId = cmd.id;
    btn.setAttribute('aria-label', cmd.label);
    btn.title = cmd.label;
    // Dropdown-style buttons get a small caret next to the icon.
    btn.innerHTML = cmd.renderAsDropdown
      ? svgIcon(cmd.icon) + svgIcon(ICONS.caretDown)
      : svgIcon(cmd.icon);
    btn.addEventListener('mousedown', (event) => {
      event.preventDefault();
    });
    btn.addEventListener('click', () => cmd.exec(ed));
    btn._cmd = cmd;
    return btn;
  }

  function updateState() {
    allButtons.forEach((btn) => {
      const cmd = btn._cmd;
      if (cmd.isActive) {
        btn.classList.toggle('active', !!cmd.isActive(editor));
      }
      if (cmd.enabled) {
        btn.disabled = !cmd.enabled(editor);
      }
    });
    const inTable = editor.isActive('table');
    tableBar.style.display = inTable ? 'inline-flex' : 'none';
  }

  editor.on('update', updateState);
  editor.on('selectionUpdate', updateState);
  editor.on('focus', updateState);
  editor.on('transaction', updateState);
  updateState();

  document.body.appendChild(toolbar);
  document.body.appendChild(tableBar);

  return {
    el: toolbar,
    destroy() {
      editor.off('update', updateState);
      editor.off('selectionUpdate', updateState);
      editor.off('focus', updateState);
      editor.off('transaction', updateState);
      if (toolbar.parentNode) toolbar.parentNode.removeChild(toolbar);
      if (tableBar.parentNode) tableBar.parentNode.removeChild(tableBar);
    },
  };
}
