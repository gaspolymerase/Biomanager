/* Global Cmd+K search palette.
 *
 * Triggered by Cmd+K (Ctrl+K on Windows/Linux) or by clicking the topbar
 * search input. Hits /search?q=… and displays grouped results. Arrow keys
 * navigate, Enter opens the selected result, Esc closes.
 */
(function () {
  'use strict';

  let overlayEl = null;
  let inputEl = null;
  let resultsEl = null;
  let currentResults = [];
  let activeIndex = 0;
  let pendingFetch = null;
  let debounceTimer = null;

  const TYPE_LABEL = {
    mouse: 'Mouse', plasmid: 'Plasmid', order: 'Order',
    sample: 'Sample', page: 'Notebook',
  };

  function build() {
    if (overlayEl) return;
    overlayEl = document.createElement('div');
    overlayEl.className = 'cmdk-overlay';
    overlayEl.hidden = true;
    overlayEl.innerHTML = `
      <div class="cmdk-backdrop"></div>
      <div class="cmdk-card" role="dialog" aria-label="Global search">
        <div class="cmdk-input-row">
          <svg class="icon cmdk-icon" aria-hidden="true"><use href="/static/icons.svg#search"></use></svg>
          <input id="cmdk-input" type="text" placeholder="Search mice, plasmids, orders, samples, notebook…" autocomplete="off">
          <kbd class="cmdk-kbd">esc</kbd>
        </div>
        <div id="cmdk-results" class="cmdk-results"></div>
        <div class="cmdk-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> to navigate</span>
          <span><kbd>↵</kbd> to open</span>
          <span><kbd>esc</kbd> to close</span>
        </div>
      </div>
    `;
    document.body.appendChild(overlayEl);

    inputEl = overlayEl.querySelector('#cmdk-input');
    resultsEl = overlayEl.querySelector('#cmdk-results');
    overlayEl.querySelector('.cmdk-backdrop').addEventListener('click', close);
    inputEl.addEventListener('input', onInput);
    inputEl.addEventListener('keydown', onKey);
  }

  function open(seed) {
    build();
    overlayEl.hidden = false;
    inputEl.value = seed || '';
    activeIndex = 0;
    currentResults = [];
    resultsEl.innerHTML = '<div class="cmdk-hint">Start typing to search…</div>';
    setTimeout(() => inputEl.focus(), 0);
    if (seed) runFetch(seed);
  }

  function close() {
    if (!overlayEl || overlayEl.hidden) return;
    overlayEl.hidden = true;
    // Lets the shell know a pending "new tab" request was abandoned.
    document.dispatchEvent(new CustomEvent('biomanager:palette-closed'));
  }

  function onInput() {
    const q = inputEl.value.trim();
    if (debounceTimer) clearTimeout(debounceTimer);
    if (!q) {
      currentResults = [];
      resultsEl.innerHTML = '<div class="cmdk-hint">Start typing to search…</div>';
      return;
    }
    debounceTimer = setTimeout(() => runFetch(q), 120);
  }

  function runFetch(q) {
    if (pendingFetch && pendingFetch.abort) pendingFetch.abort();
    const controller = new AbortController();
    pendingFetch = controller;
    fetch(`/search?q=${encodeURIComponent(q)}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || !data.ok) return;
        currentResults = data.results || [];
        activeIndex = 0;
        render();
      })
      .catch(() => {});
  }

  function render() {
    if (!currentResults.length) {
      resultsEl.innerHTML = '<div class="cmdk-empty">No matches.</div>';
      return;
    }
    // Group by type, preserving overall ordering.
    const groups = {};
    currentResults.forEach((item, idx) => {
      if (!groups[item.type]) groups[item.type] = [];
      groups[item.type].push({ ...item, _idx: idx });
    });
    const order = ['mouse', 'plasmid', 'order', 'sample', 'page'];
    let html = '';
    order.forEach((type) => {
      if (!groups[type]) return;
      html += `<div class="cmdk-group-label">${escapeHtml(TYPE_LABEL[type] || type)}</div>`;
      groups[type].forEach((item) => {
        const active = item._idx === activeIndex ? 'is-active' : '';
        html += `
          <a href="${escapeAttr(item.url)}" class="cmdk-row ${active}" data-idx="${item._idx}">
            <span class="cmdk-row-type cmdk-row-type-${item.type}">${escapeHtml(TYPE_LABEL[item.type] || item.type)}</span>
            <span class="cmdk-row-text">
              <span class="cmdk-row-label">${escapeHtml(item.label)}</span>
              <span class="cmdk-row-sublabel">${escapeHtml(item.sublabel || '')}</span>
            </span>
          </a>
        `;
      });
    });
    resultsEl.innerHTML = html;
    resultsEl.querySelectorAll('.cmdk-row').forEach((row) => {
      row.addEventListener('mouseenter', () => {
        activeIndex = parseInt(row.dataset.idx, 10);
        refreshActive();
      });
    });
  }

  function refreshActive() {
    resultsEl.querySelectorAll('.cmdk-row').forEach((row) => {
      const idx = parseInt(row.dataset.idx, 10);
      row.classList.toggle('is-active', idx === activeIndex);
      if (idx === activeIndex) row.scrollIntoView({ block: 'nearest' });
    });
  }

  function onKey(event) {
    if (event.key === 'Escape') { close(); event.preventDefault(); return; }
    if (event.key === 'ArrowDown') {
      activeIndex = Math.min(currentResults.length - 1, activeIndex + 1);
      refreshActive();
      event.preventDefault();
      return;
    }
    if (event.key === 'ArrowUp') {
      activeIndex = Math.max(0, activeIndex - 1);
      refreshActive();
      event.preventDefault();
      return;
    }
    if (event.key === 'Enter') {
      const result = currentResults[activeIndex];
      if (result && result.url) window.location.href = result.url;
      event.preventDefault();
      return;
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  }
  const escapeAttr = escapeHtml;

  // Activate Cmd+K (or Ctrl+K) globally. Also enables the topbar search input
  // (which is rendered disabled in base.html) by hijacking click/focus.
  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      open();
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    const topbarInput = document.getElementById('app-global-search');
    if (topbarInput) {
      topbarInput.disabled = false;
      topbarInput.placeholder = 'Search Cmd+K';
      topbarInput.readOnly = true;
      topbarInput.addEventListener('focus', (event) => {
        event.target.blur();
        open();
      });
      topbarInput.addEventListener('click', (event) => {
        event.preventDefault();
        open();
      });
    }
  });

  window.BiomanagerSearch = { open, close };
})();
