// The words an @link can start with: mouse, plasmid and order, and every
// inventory the notebook page lists in #nb-mention-types, by its key
// ("@antibodies 12" is antibody #12). Read once, on first use.

const BUILTIN = { mouse: 'Mouse', plasmid: 'Plasmid', order: 'Order' };

let cached = null;

export function mentionTypes() {
  if (cached) return cached;
  const labels = { ...BUILTIN };
  try {
    const el = typeof document !== 'undefined' && document.getElementById('nb-mention-types');
    const list = el ? JSON.parse(el.textContent || '[]') : [];
    list.forEach((t) => {
      if (t && /^[a-z0-9_]+$/.test(t.key) && !labels[t.key]) labels[t.key] = t.label || t.key;
    });
  } catch (_) { /* a page without the list links the built-in three */ }
  // Longest first, so "@samples_2 4" is not read as "@samples".
  const alt = Object.keys(labels).sort((a, b) => b.length - a.length).join('|');
  cached = { labels, alt };
  return cached;
}

export const isBuiltin = (type) => Object.prototype.hasOwnProperty.call(BUILTIN, type);

// The class suffix for chips and tags: built-ins have their own icon and
// colour; every inventory shares one.
export const styleOf = (type) => (isBuiltin(type) ? type : 'item');

export function mentionRe() {
  return new RegExp(`@(${mentionTypes().alt})\\s+(\\d+)(?!\\d)`, 'g');
}

export function typedTriggerRe() {
  return new RegExp(`@(${mentionTypes().alt})\\s+([\\w-]*)$`);
}
