// Every page: the English ⇄ 中文 link remembers the choice, so a Chinese
// browser is not sent back to the Chinese page after picking English.
// Guide pages: highlight the section being read in the contents, and
// copy buttons (<button data-copy="id-of-element">).
(function () {
  document.querySelectorAll('a[data-lang]').forEach(function (a) {
    a.addEventListener('click', function () {
      try { localStorage.setItem('bm-lang', a.dataset.lang); } catch (e) {}
      if (location.hash && a.getAttribute('href').indexOf('#') < 0) a.href = a.getAttribute('href') + location.hash;
    });
  });
  // The contents: always open beside the text on a wide screen; on a phone
  // a closed box above it (it is a screen tall), closed again after a jump.
  var box = document.querySelector('.toc-box');
  if (box && window.matchMedia) {
    var wide = window.matchMedia('(min-width: 960px)');
    var fit = function () { box.open = wide.matches; };
    fit();
    if (wide.addEventListener) wide.addEventListener('change', fit);
    box.addEventListener('click', function (e) {
      if (!wide.matches && e.target.closest('a')) box.open = false;
    });
  }
  var links = {};
  document.querySelectorAll('.toc a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && links[e.target.id]) {
          document.querySelectorAll('.toc a.on').forEach(function (a) { a.classList.remove('on'); });
          links[e.target.id].classList.add('on');
        }
      });
    }, { rootMargin: '-70px 0px -70% 0px' });
    document.querySelectorAll('.guide-body section[id], .guide-body h3[id]').forEach(function (s) { io.observe(s); });
  }
  document.querySelectorAll('[data-copy]').forEach(function (button) {
    button.addEventListener('click', function () {
      var source = document.getElementById(button.dataset.copy);
      if (!source || !navigator.clipboard) return;
      navigator.clipboard.writeText(source.innerText.trim()).then(function () {
        var was = button.textContent;
        button.textContent = document.documentElement.lang.indexOf('zh') === 0 ? '已复制' : 'Copied';
        setTimeout(function () { button.textContent = was; }, 1500);
      });
    });
  });
})();
