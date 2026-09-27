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
      document.querySelectorAll('[data-bell-menu]').forEach((other) => { other.hidden = true; });
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

  /* --------------------------------------------------------- notifications */

  // The bell (app/notify.py). The list is rendered by the server and fetched
  // when the bell opens; the unread count refreshes every minute while the
  // tab is visible, so a transfer or a finished order shows up by itself.
  function initBell() {
    const root = document.querySelector('[data-bell]');
    if (!root) return;
    const button = root.querySelector('[data-bell-toggle]');
    const menu = root.querySelector('[data-bell-menu]');
    const badge = root.querySelector('[data-bell-count]');

    const setCount = (n) => {
      badge.textContent = n > 99 ? '99+' : String(n);
      badge.hidden = !n;
      button.setAttribute('aria-label', n ? `Notifications: ${n} unread` : 'Notifications');
    };
    const load = async () => {
      try {
        const response = await fetch(root.dataset.panelUrl, { credentials: 'same-origin' });
        if (response.ok) menu.innerHTML = await response.text();   // our own escaped template
      } catch (_) {
        menu.textContent = 'Could not load notifications.';
      }
    };
    const close = () => {
      menu.hidden = true;
      button.setAttribute('aria-expanded', 'false');
    };
    // On a phone the bell is not at the screen's edge, so a menu hung from
    // it would run off the left side: pin it under the header instead.
    const place = () => {
      if (window.innerWidth > 480) {
        menu.style.cssText = '';
        return;
      }
      const below = Math.round(button.getBoundingClientRect().bottom + 6);
      menu.style.cssText = `position: fixed; top: ${below}px; left: 8px; right: 8px; width: auto; max-width: none;`;
    };

    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const opening = menu.hidden;
      document.querySelectorAll('[data-account-menu]').forEach((other) => { other.hidden = true; });
      menu.hidden = !opening;
      button.setAttribute('aria-expanded', String(opening));
      if (opening) {
        place();
        load();
      }
    });
    window.addEventListener('resize', () => { if (!menu.hidden) place(); });
    document.addEventListener('click', (event) => {
      if (!menu.hidden && !root.contains(event.target)) close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
    menu.addEventListener('submit', async (event) => {
      const form = event.target.closest('form[data-mark-read]');
      if (!form) return;
      event.preventDefault();
      await fetch(form.action, { method: 'POST', credentials: 'same-origin',
                                 headers: { Accept: 'application/json' } });
      setCount(0);
      load();
    });

    const poll = async () => {
      if (document.hidden) return;
      try {
        const response = await fetch(root.dataset.countUrl, { credentials: 'same-origin' });
        if (response.ok) setCount((await response.json()).unread || 0);
      } catch (_) { /* offline for a moment: try again next minute */ }
    };
    setInterval(poll, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
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

    // The omnibox searches in the tab you are already in; "+" (below) opens
    // a new tab on your start page.
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
      // A new tab opens on the person's start page, as a browser's opens on
      // its home page; the palette (Cmd/Ctrl+K) is for going somewhere else.
      newTabButton.addEventListener('click', (event) => {
        event.preventDefault();
        const start = newTabButton.dataset.newTab || '/';
        if (window.BiomanagerTabs) window.BiomanagerTabs.open(start);
        else window.location.href = start;
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
    initBell();
    initShortcuts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.BiomanagerShell = { toast, toggleRail, setRail, setDrawer };
})();

/* Confirm before a destructive submit: <form data-confirm="Delete V12?">.
   The text lives in an attribute (escaped by Jinja), never inside an
   onsubmit string, where a name containing a quote could break out and
   run as script. Selection-bar forms handle their own ({n}) prompt. */
document.addEventListener('submit', (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.hasAttribute('data-selection-form')) return;
  const text = form.getAttribute('data-confirm');
  if (!text) return;
  // Answered yes a moment ago: this is the submit that follows (see below).
  if (form.dataset.confirmed === '1') { delete form.dataset.confirmed; return; }
  // Ask in the app (BioDialog), then submit again with the same button.
  event.preventDefault();
  event.stopImmediatePropagation();
  const submitter = event.submitter;
  window.BioDialog.confirm(text, { danger: window.BioDialog.looksDestructive(text) }).then((ok) => {
    if (!ok) return;
    form.dataset.confirmed = '1';
    if (typeof form.requestSubmit === 'function') form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
    else { delete form.dataset.confirmed; form.submit(); }
  });
}, true);
