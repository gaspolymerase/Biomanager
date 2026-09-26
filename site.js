// Guide pages: highlight the section being read in the contents, and
// copy buttons (<button data-copy="id-of-element">).
(function () {
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
        button.textContent = 'Copied';
        setTimeout(function () { button.textContent = was; }, 1500);
      });
    });
  });
})();
