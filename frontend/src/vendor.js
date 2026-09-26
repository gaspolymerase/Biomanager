// Mermaid and KaTeX are large, and most pages use neither: they load the
// first time a page shows a diagram or an equation, from
// /static/notebook-build/vendor/ (copied there by `npm run build:vendor`).

const BASE = '/static/notebook-build/vendor/';
const loading = {};

function script(src) {
  if (!loading[src]) {
    loading[src] = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = BASE + src;
      s.async = true;
      s.onload = resolve;
      s.onerror = () => { delete loading[src]; reject(new Error(`could not load ${src}`)); };
      document.head.appendChild(s);
    });
  }
  return loading[src];
}

function css(href) {
  if (document.querySelector(`link[data-vendor="${href}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = BASE + href;
  link.dataset.vendor = href;
  document.head.appendChild(link);
}

export async function katex() {
  css('katex/katex.min.css');
  await script('katex/katex.min.js');
  return window.katex;
}

function dark() {
  const theme = document.documentElement.dataset.theme;
  if (theme === 'dark') return true;
  if (theme === 'light') return false;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

let mermaidReady = null;
export async function mermaid() {
  if (!mermaidReady) {
    mermaidReady = script('mermaid.min.js').then(() => {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: dark() ? 'dark' : 'neutral',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
      });
      return window.mermaid;
    }).catch((e) => { mermaidReady = null; throw e; });
  }
  return mermaidReady;
}
