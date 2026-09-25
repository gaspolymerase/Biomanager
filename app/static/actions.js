/* Declarative event handlers, so pages need no inline onclick="…".
 *
 * The Content-Security-Policy (app/security.py) refuses inline event
 * handlers, because a policy that allows them also allows any that an
 * attacker manages to inject. Markup says what should happen instead:
 *
 *   <button data-on-click="close-dialog">            built-in action
 *   <button data-on-click="renameTab" data-arg="7">  a page's own function
 *   <form   data-on-submit="submitNewTemplate" data-prevent>
 *   <span   data-on-dblclick="renameTab" data-arg="7" data-stop>
 *
 * Only actions registered by name can run: a page registers its functions
 * with BioActions.register({ renameTab: renameTab }). Looking names up on
 * window instead would let injected markup call any global, eval included.
 *
 * Handlers are bound on the element itself, exactly where an inline
 * handler would sit, so stopPropagation() and preventDefault() behave as
 * they did; elements added later (rendered by script) are bound as they
 * appear. `this` is the element, as it was inline.
 *
 * Loaded synchronously in <head>, before any page script registers.
 */
(function () {
  "use strict";

  var EVENTS = ["click", "dblclick", "submit", "input", "change"];
  var actions = Object.create(null);

  function register(map) {
    Object.keys(map).forEach(function (name) {
      if (typeof map[name] === "function") actions[name] = map[name];
    });
  }

  // Digits become numbers, as they were when written into inline handlers
  // (renameTab({{ tab.id }})); anything else is passed as a string.
  function argOf(el) {
    var raw = el.getAttribute("data-arg");
    if (raw === null) return undefined;
    return /^-?\d+$/.test(raw) ? Number(raw) : raw;
  }

  function byId(id) {
    var target = document.getElementById(id);
    if (!target) console.warn("BioActions: no element #" + id);
    return target;
  }

  register({
    "none": function () {},
    "close-dialog": function () {
      var dialog = this.closest("dialog");
      if (dialog) dialog.close();
    },
    "open-dialog": function (id) {
      var dialog = byId(id);
      if (dialog) dialog.showModal();
    },
    "close-dialog-id": function (id) {
      var dialog = byId(id);
      if (dialog) dialog.close();
    },
    "click": function (id) {
      var target = byId(id);
      if (target) target.click();
    },
    "print": function () { window.print(); },
    "remove-row": function () {
      var row = this.closest("tr");
      if (row) row.remove();
    }
  });

  function bind(el) {
    EVENTS.forEach(function (type) {
      var name = el.getAttribute("data-on-" + type);
      if (!name) return;
      var mark = "boundOn" + type;
      if (el[mark]) return;
      el[mark] = true;
      el.addEventListener(type, function (event) {
        if (el.hasAttribute("data-prevent")) event.preventDefault();
        if (el.hasAttribute("data-stop")) event.stopPropagation();
        var fn = actions[name];
        if (!fn) {
          console.warn("BioActions: no action named \"" + name + "\"");
          return;
        }
        fn.call(el, argOf(el), event);
      });
    });
  }

  var SELECTOR = EVENTS.map(function (t) { return "[data-on-" + t + "]"; }).join(",");

  function bindAll(root) {
    if (root.nodeType !== 1) return;
    if (root.matches(SELECTOR)) bind(root);
    Array.prototype.forEach.call(root.querySelectorAll(SELECTOR), bind);
  }

  function start() {
    bindAll(document.documentElement);
    new MutationObserver(function (records) {
      records.forEach(function (record) {
        Array.prototype.forEach.call(record.addedNodes, bindAll);
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  // <script data-loaded-flag="__oveLoaded" data-missing-flag="__oveMissing">:
  // pages check these globals to show a message when a bundle failed to
  // load. Load and error events do not bubble, but they do pass through
  // the document in the capture phase, and this runs before any bundle.
  document.addEventListener("load", function (event) {
    var flag = event.target && event.target.getAttribute && event.target.getAttribute("data-loaded-flag");
    if (flag) window[flag] = true;
  }, true);
  document.addEventListener("error", function (event) {
    var flag = event.target && event.target.getAttribute && event.target.getAttribute("data-missing-flag");
    if (flag) window[flag] = true;
  }, true);

  window.BioActions = { register: register };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
  // Elements parsed before DOMContentLoaded are bound then; the observer
  // is only started at that point, so nothing is bound twice.
})();
