/* Excel-style autofill for notebook tables.
 *
 * Attaches to a TipTap editor's DOM and adds a small "fill handle" at the
 * bottom-right corner of the currently-focused cell in a `.tiptap-table`.
 * Dragging the handle paints adjacent cells with extrapolated values:
 *
 *   - plain text      → copy (every target gets the source value)
 *   - integer         → increment (1, 2, 3, …)
 *   - text + integer  → increment the trailing number (Sample 1, Sample 2, …)
 *   - YYYY-MM-DD      → +1 day per step
 *   - HH:mm           → +1 hour per step
 *
 * Direction is detected from the drag axis: vertical-dominant → fill the
 * column below; horizontal-dominant → fill the row to the right (or above /
 * left for negative deltas).
 */

export function attachTableAutofill(editor, editorEl) {
  let activeCell = null;
  let dragState = null;

  const handle = document.createElement('div');
  handle.className = 'biocal-fill-handle';
  handle.title = 'Drag to fill';
  handle.style.display = 'none';
  // We position the handle relative to the editor element so it scrolls
  // with the content. Anchor element gets `position: relative` via CSS.
  editorEl.style.position = editorEl.style.position || 'relative';
  editorEl.appendChild(handle);

  // ---- Active-cell tracking --------------------------------------------
  // Update the handle position when the user clicks/types inside a table cell.
  function updateActiveCell() {
    const sel = window.getSelection();
    if (!sel || !sel.anchorNode) { hideHandle(); return; }
    const node = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
    if (!node || !editorEl.contains(node)) { hideHandle(); return; }
    const cell = node.closest('td, th');
    if (!cell || !editorEl.contains(cell)) { hideHandle(); return; }
    activeCell = cell;
    positionHandle(cell);
  }
  function positionHandle(cell) {
    const cr = cell.getBoundingClientRect();
    const er = editorEl.getBoundingClientRect();
    handle.style.left = `${cr.right - er.left - 7 + editorEl.scrollLeft}px`;
    handle.style.top = `${cr.bottom - er.top - 7 + editorEl.scrollTop}px`;
    handle.style.display = 'block';
  }
  function hideHandle() {
    if (!dragState) {
      activeCell = null;
      handle.style.display = 'none';
    }
  }

  // selection / click both trigger updateActiveCell. Use selectionchange
  // since TipTap's transactions don't always emit a DOM event.
  document.addEventListener('selectionchange', updateActiveCell);
  editorEl.addEventListener('click', updateActiveCell);
  // After the editor mutates (typing, undo, etc.) the cell rect can shift.
  editor.on('update', () => { if (activeCell) positionHandle(activeCell); });
  editor.on('selectionUpdate', updateActiveCell);
  window.addEventListener('resize', () => { if (activeCell) positionHandle(activeCell); });

  // ---- Drag --------------------------------------------------------------
  handle.addEventListener('mousedown', (e) => {
    if (!activeCell) return;
    e.preventDefault();
    e.stopPropagation();
    const table = activeCell.closest('table');
    if (!table) return;
    const startInfo = locateCell(table, activeCell);
    if (!startInfo) return;
    dragState = {
      table,
      sourceCell: activeCell,
      sourceText: cellText(activeCell),
      sourceRow: startInfo.row,
      sourceCol: startInfo.col,
      lastTarget: null,
    };
    document.body.classList.add('biocal-autofill-active');
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd, { once: true });
  });

  function onDragMove(e) {
    if (!dragState) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el) return;
    const tgtCell = el.closest('td, th');
    if (!tgtCell || tgtCell.closest('table') !== dragState.table) return;
    const tgt = locateCell(dragState.table, tgtCell);
    if (!tgt) return;
    if (dragState.lastTarget && dragState.lastTarget.row === tgt.row && dragState.lastTarget.col === tgt.col) return;
    dragState.lastTarget = tgt;
    highlightRange(dragState, tgt);
  }

  function onDragEnd() {
    document.removeEventListener('mousemove', onDragMove);
    document.body.classList.remove('biocal-autofill-active');
    if (!dragState) return;
    clearHighlight(dragState.table);
    const tgt = dragState.lastTarget;
    const state = dragState;
    dragState = null;
    if (!tgt) return;
    if (tgt.row === state.sourceRow && tgt.col === state.sourceCol) return;
    applyFill(state, tgt);
    if (activeCell) positionHandle(activeCell);
  }

  // ---- Range highlight ---------------------------------------------------
  function rangeCellsBetween(table, fromRow, fromCol, toRow, toCol) {
    const r0 = Math.min(fromRow, toRow);
    const r1 = Math.max(fromRow, toRow);
    const c0 = Math.min(fromCol, toCol);
    const c1 = Math.max(fromCol, toCol);
    const out = [];
    const rows = table.querySelectorAll('tr');
    for (let r = r0; r <= r1; r++) {
      const tr = rows[r];
      if (!tr) continue;
      const cells = tr.querySelectorAll('td, th');
      for (let c = c0; c <= c1; c++) {
        const td = cells[c];
        if (td) out.push({ row: r, col: c, el: td });
      }
    }
    return out;
  }
  function highlightRange(state, tgt) {
    clearHighlight(state.table);
    const cells = rangeCellsBetween(state.table, state.sourceRow, state.sourceCol, tgt.row, tgt.col);
    cells.forEach((c) => c.el.classList.add('biocal-autofill-target'));
    // Source stays as the "primary" — visually distinct.
    state.sourceCell.classList.add('biocal-autofill-source');
  }
  function clearHighlight(table) {
    table.querySelectorAll('.biocal-autofill-target').forEach((el) => el.classList.remove('biocal-autofill-target'));
    table.querySelectorAll('.biocal-autofill-source').forEach((el) => el.classList.remove('biocal-autofill-source'));
  }

  // ---- Fill ---------------------------------------------------------------
  function applyFill(state, tgt) {
    const cells = rangeCellsBetween(state.table, state.sourceRow, state.sourceCol, tgt.row, tgt.col);
    // Skip the source cell — only fill destinations.
    const targets = cells.filter((c) => !(c.row === state.sourceRow && c.col === state.sourceCol));
    if (!targets.length) return;
    // Distance from source = position in the sequence.
    // We treat vertical-dominant drags as filling a column; otherwise row.
    const verticalDominant = Math.abs(tgt.row - state.sourceRow) >= Math.abs(tgt.col - state.sourceCol);
    const sign = verticalDominant
      ? Math.sign(tgt.row - state.sourceRow) || 1
      : Math.sign(tgt.col - state.sourceCol) || 1;
    // Order targets by distance from source.
    targets.sort((a, b) => {
      const da = verticalDominant ? sign * (a.row - state.sourceRow) : sign * (a.col - state.sourceCol);
      const db = verticalDominant ? sign * (b.row - state.sourceRow) : sign * (b.col - state.sourceCol);
      return da - db;
    });

    // Replace each target cell's content via TipTap commands.
    targets.forEach((t, i) => {
      const step = i + 1;
      const value = extrapolate(state.sourceText, step * sign);
      writeCellText(t.el, value);
    });
  }

  function writeCellText(td, text) {
    const pos = editor.view.posAtDOM(td, 0);
    if (pos === null || pos < 0) return;
    // Each <td> wraps a <p>; replace the paragraph's content with our text.
    const $pos = editor.state.doc.resolve(pos);
    // Walk up to the cell node, find its position range.
    let depth = $pos.depth;
    while (depth > 0 && $pos.node(depth).type.name !== 'tableCell' && $pos.node(depth).type.name !== 'tableHeader') {
      depth--;
    }
    if (depth === 0) return;
    const cellStart = $pos.start(depth);
    const cellEnd = $pos.end(depth);
    editor.chain()
      .focus()
      .setTextSelection({ from: cellStart, to: cellEnd })
      .insertContent(text)
      .run();
  }

  // ---- Pattern detection -------------------------------------------------
  // Given the source text and the step number (1-based, signed), return
  // the extrapolated value.
  function extrapolate(src, step) {
    if (src == null) return '';
    const s = String(src);
    if (!s.trim()) return s;

    // Pure integer?
    if (/^-?\d+$/.test(s.trim())) {
      return String(parseInt(s, 10) + step);
    }
    // Pure float?
    if (/^-?\d+\.\d+$/.test(s.trim())) {
      const decimals = s.split('.')[1].length;
      return (parseFloat(s) + step).toFixed(decimals);
    }
    // YYYY-MM-DD → +N days.
    const dateMatch = s.trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateMatch) {
      const d = new Date(`${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}T00:00:00`);
      d.setDate(d.getDate() + step);
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }
    // HH:mm → +N hours.
    const timeMatch = s.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (timeMatch) {
      let h = parseInt(timeMatch[1], 10) + step;
      const m = timeMatch[2];
      // Wrap into 0..23.
      h = ((h % 24) + 24) % 24;
      return `${String(h).padStart(2, '0')}:${m}`;
    }
    // Text with a trailing positive integer ("Sample 1", "PCR-7", "Lane3").
    // We deliberately don't capture a leading "-" as a sign — dashes in
    // labels like "PCR-7" are separators, not negative signs.
    const trailing = s.match(/^(.*?)(\d+)(\s*)$/);
    if (trailing) {
      const prefix = trailing[1];
      const num = parseInt(trailing[2], 10) + step;
      const suffix = trailing[3] || '';
      return `${prefix}${num}${suffix}`;
    }
    // Otherwise: copy.
    return s;
  }

  // ---- Helpers -----------------------------------------------------------
  function locateCell(table, cell) {
    const rows = table.querySelectorAll('tr');
    for (let r = 0; r < rows.length; r++) {
      const cells = rows[r].querySelectorAll('td, th');
      for (let c = 0; c < cells.length; c++) {
        if (cells[c] === cell) return { row: r, col: c };
      }
    }
    return null;
  }
  function cellText(cell) {
    // Strip leading/trailing whitespace; collapse internal whitespace minimally.
    return (cell.textContent || '').replace(/ /g, ' ').trim();
  }

  return {
    destroy() {
      document.removeEventListener('selectionchange', updateActiveCell);
      handle.remove();
    },
  };
}
