// Inline maths: $E = mc^2$ in the text, drawn with KaTeX. Typing a closing
// $ turns $…$ into an equation; click one to edit its LaTeX. Stored in
// Markdown as $…$ (and a block written as $$…$$ on its own lines becomes an
// equation block, see blocks/index.js).

import { InputRule, Node } from '@tiptap/core';
import { katex } from '../vendor.js';
import { ask } from '../util.js';

function mathPlugin(md) {
  if (md.__nbMath) return;
  md.__nbMath = true;
  // $…$ inline, not $ 5 and $10 prices: no space just inside the dollars,
  // and no digit straight after the closing one.
  md.inline.ruler.after('escape', 'nb_math_inline', (state, silent) => {
    const src = state.src;
    const start = state.pos;
    if (src[start] !== '$' || src[start + 1] === '$' || src[start + 1] === ' ') return false;
    let end = start + 1;
    while (end < state.posMax) {
      if (src[end] === '\\') { end += 2; continue; }
      if (src[end] === '$') break;
      end++;
    }
    if (end >= state.posMax || src[end - 1] === ' ' || /\d/.test(src[end + 1] || '')) return false;
    const content = src.slice(start + 1, end);
    if (!content.trim() || content.includes('\n\n')) return false;
    if (!silent) {
      const token = state.push('nb_math_inline', 'span', 0);
      token.content = content;
    }
    state.pos = end + 1;
    return true;
  });
  md.renderer.rules.nb_math_inline = (tokens, idx) => {
    const esc = md.utils.escapeHtml(tokens[idx].content);
    return `<span data-math-inline="${esc}">${esc}</span>`;
  };
  // $$ … $$ on lines of their own → a math block.
  md.block.ruler.before('fence', 'nb_math_block', (state, startLine, endLine, silent) => {
    const first = state.src.slice(state.bMarks[startLine] + state.tShift[startLine], state.eMarks[startLine]);
    if (!first.startsWith('$$')) return false;
    let content = first.slice(2);
    let line = startLine;
    let closed = false;
    if (content.trim().endsWith('$$') && content.trim().length >= 2) {
      content = content.trim().slice(0, -2);
      closed = true;
    }
    while (!closed && ++line < endLine) {
      const text = state.src.slice(state.bMarks[line] + state.tShift[line], state.eMarks[line]);
      if (text.trim().endsWith('$$')) {
        content += '\n' + text.trim().slice(0, -2);
        closed = true;
      } else {
        content += '\n' + text;
      }
    }
    if (!closed) return false;
    if (silent) return true;
    const token = state.push('fence', 'code', 0);
    token.info = 'math';
    token.content = content.trim() + '\n';
    token.map = [startLine, line + 1];
    state.line = line + 1;
    return true;
  });
}

export const MathInline = Node.create({
  name: 'mathInline',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,

  addAttributes() {
    return { latex: { default: '' } };
  },

  parseHTML() {
    return [{ tag: 'span[data-math-inline]', getAttrs: (el) => ({ latex: el.getAttribute('data-math-inline') || '' }) }];
  },

  renderHTML({ node }) {
    return ['span', { 'data-math-inline': node.attrs.latex, class: 'nb-math-inline' }, node.attrs.latex];
  },

  addStorage() {
    return {
      markdown: {
        serialize(state, node) {
          state.write('$' + node.attrs.latex.replace(/\$/g, '\\$') + '$');
        },
        parse: {
          setup(markdownit) {
            mathPlugin(markdownit);
          },
        },
      },
    };
  },

  addInputRules() {
    return [
      new InputRule({
        find: /(?:^|[\s(])\$([^$\s][^$]*?[^$\s]|[^$\s])\$$/,
        handler: ({ state, range, match }) => {
          const latex = match[1];
          const start = range.from + match[0].indexOf('$');
          state.tr.replaceWith(start, range.to, this.type.create({ latex }));
        },
      }),
    ];
  },

  addNodeView() {
    return ({ node, editor, getPos }) => {
      const dom = document.createElement('span');
      dom.className = 'nb-math-inline';
      dom.contentEditable = 'false';
      let current = node;
      const draw = async () => {
        try {
          const k = await katex();
          dom.innerHTML = k.renderToString(current.attrs.latex || '?', { throwOnError: false, strict: 'ignore' });
        } catch (_e) {
          dom.textContent = `$${current.attrs.latex}$`;
        }
      };
      dom.addEventListener('click', async () => {
        if (!editor.isEditable) return;
        const next = await ask.prompt('Equation (LaTeX)', current.attrs.latex, { okLabel: 'Save' });
        if (next === null) return;
        const pos = getPos();
        if (typeof pos !== 'number') return;
        if (!next.trim()) editor.chain().focus().deleteRange({ from: pos, to: pos + current.nodeSize }).run();
        else editor.view.dispatch(editor.state.tr.setNodeMarkup(pos, undefined, { latex: next }));
      });
      dom.title = 'Click to edit';
      draw();
      return {
        dom,
        update(next) {
          if (next.type !== current.type) return false;
          const changed = next.attrs.latex !== current.attrs.latex;
          current = next;
          if (changed) draw();
          return true;
        },
        ignoreMutation: () => true,
      };
    };
  },
});
