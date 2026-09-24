/* App shell behavior: the rail, the mobile nav drawer, the account menu,
 * lightweight toasts, and the keyboard shortcuts that make the workspace
 * tabs usable without the mouse.
 *
 * Tab rendering itself lives in tab-bar.js; this file only drives it through
 * the window.BiomanagerTabs API.
 */
(function () {
  'use strict';

  const RAIL_KEY = 'biomanager:rail';
  const isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent);

  /* ---------------------------------------------------------------- toasts */

  let toastHost = null;

  function toast(message, kind) {
    if (!toastHost) {
      toastHost = document.createElement('div');
      toastHost.className = 'toast-host';
      document.body.appendChild(toastHost);
    }
    const el = document.createElement('div');
    el.className = 'toast' + (kind ? ' toast-' + kind : '');
    el.textContent = message;
    toastHost.appendChild(el);
    // Let the element land in the DOM before animating it in.
    requestAnimationFrame(() => el.classList.add('is-in'));
    setTimeout(() => {
      el.classList.remove('is-in');
      setTimeout(() => el.remove(), 220);
    }, 3200);
  }

  /* ------------------------------------------------------------------ rail */

  function setRail(state) {
    document.body.dataset.rail = state;
    try { localStorage.setItem(RAIL_KEY, state); } catch (e) {}
  }

  function toggleRail() {
    setRail(document.body.dataset.rail === 'open' ? 'closed' : 'open');
  }

  /* ---------------------------------------------------------------- drawer */

  function setDrawer(open) {
    if (open) document.body.dataset.drawer = 'open';
    else delete document.body.dataset.drawer;
  }

  /* ---------------------------------------------------------- account menu */

  function initAccountMenu() {
    const root = document.querySelector('[data-account]');
    if (!root) return;
    const button = root.querySelector('[data-account-toggle]');
    const menu = root.querySelector('[data-account-menu]');
    if (!button || !menu) return;

    const close = () => {
      menu.hidden = true;
      button.setAttribute('aria-expanded', 'false');
    };

    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const opening = menu.hidden;
      menu.hidden = !opening;
      button.setAttribute('aria-expanded', String(opening));
    });

    document.addEventListener('click', (event) => {
      if (!menu.hidden && !root.contains(event.target)) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
  }

  /* ------------------------------------------------------------- shortcuts */

  function initShortcuts() {
    document.addEventListener('keydown', (event) => {
      const tabs = window.BiomanagerTabs;
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName) ||
                     event.target.isContentEditable;

      // Cmd/Ctrl+B — collapse or expand the rail. Safe to use while typing
      // is not: browsers map it to "bold" in rich text fields.
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === 'b' && !typing) {
        event.preventDefault();
        toggleRail();
        return;
      }

      // Everything below is Alt-based so it never collides with the
      // browser's own Cmd/Ctrl+number and Cmd/Ctrl+W bindings.
      if (!event.altKey || event.metaKey || event.ctrlKey || !tabs) return;

      if (event.key >= '1' && event.key <= '9') {
        event.preventDefault();
        tabs.activate(parseInt(event.key, 10) - 1);
        return;
      }
      const key = event.key.toLowerCase();
      if (key === 'w') { event.preventDefault(); tabs.closeCurrent(); return; }
      if (event.key === 'ArrowLeft' || key === '[') { event.preventDefault(); tabs.step(-1); return; }
      if (event.key === 'ArrowRight' || key === ']') { event.preventDefault(); tabs.step(1); }
    });
  }

  /* ------------------------------------------------------------------ init */

  function init() {
    document.querySelectorAll('[data-rail-toggle]').forEach((el) => {
      el.addEventListener('click', toggleRail);
    });
    document.querySelectorAll('[data-drawer-toggle]').forEach((el) => {
      el.addEventListener('click', () => setDrawer(document.body.dataset.drawer !== 'open'));
    });
    document.querySelectorAll('[data-drawer-close]').forEach((el) => {
      el.addEventListener('click', () => setDrawer(false));
    });

    // Placeholder modules (Drosophila, "add database") explain themselves
    // instead of firing a native alert().
    document.querySelectorAll('[data-soon]').forEach((el) => {
      el.addEventListener('click', () => toast(el.dataset.soon));
    });

    // Both open the command palette, but they mean different things: the
    // omnibox searches in the tab you are already in, while "+" is a
    // request for a new tab that the next navigation fulfils.
    const omnibox = document.querySelector('#app-global-search');
    if (omnibox) {
      omnibox.addEventListener('click', (event) => {
        event.preventDefault();
        if (window.BiomanagerTabs) window.BiomanagerTabs.cancelNewTab();
        if (window.BiomanagerSearch) window.BiomanagerSearch.open();
      });
    }

    const newTabButton = document.querySelector('[data-new-tab]');
    if (newTabButton) {
      newTabButton.addEventListener('click', (event) => {
        event.preventDefault();
        if (window.BiomanagerTabs) window.BiomanagerTabs.requestNewTab();
        if (window.BiomanagerSearch) window.BiomanagerSearch.open();
      });
    }

    // Dismissing the palette abandons the request, so a link clicked
    // afterwards still navigates in place.
    document.addEventListener('biomanager:palette-closed', () => {
      if (window.BiomanagerTabs) window.BiomanagerTabs.cancelNewTab();
    });

    // Show the right modifier glyph for the platform.
    if (!isMac) {
      document.querySelectorAll('.omnibox .kbd').forEach((el) => { el.textContent = 'Ctrl K'; });
    }

    // macOS toolbars are borderless until content scrolls beneath them.
    const scroller = document.getElementById('app-scroll');
    const toolbar = document.getElementById('app-toolbar');
    if (scroller && toolbar) {
      const sync = () => toolbar.classList.toggle('is-scrolled', scroller.scrollTop > 2);
      scroller.addEventListener('scroll', sync, { passive: true });
      sync();
    }

    initAccountMenu();
    initShortcuts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.BiomanagerShell = { toast, toggleRail, setRail, setDrawer };
})();
