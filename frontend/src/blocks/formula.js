// Formulas for computed sheet columns, e.g. `=B/mean(B)*100` or
// `=log2({Treated}/{Control})`. Columns are named by letter (A, B, …) or by
// name in braces. Row-wise arithmetic (+ − × ÷ ^), functions (log, log2,
// log10, ln, exp, sqrt, abs, round, min, max, pow) and column aggregates
// (mean, median, sum, sd, count, first) over a whole column. Parsed by hand:
// the page's security policy forbids eval, and a sheet should never run
// code anyway.

import { mean, median, sd } from './stats.js';
import { toNumber } from '../util.js';

const FUNCS = {
  log: (x, b) => (b === undefined ? Math.log10(x) : Math.log(x) / Math.log(b)),
  log2: Math.log2, log10: Math.log10, ln: Math.log, exp: Math.exp, sqrt: Math.sqrt, abs: Math.abs,
  round: (x, n = 0) => Math.round(x * 10 ** n) / 10 ** n,
  min: Math.min, max: Math.max, pow: Math.pow,
};
const AGGREGATES = {
  mean, median, sd,
  sum: (xs) => xs.reduce((a, b) => a + b, 0),
  count: (xs) => xs.length,
  first: (xs) => xs[0],
};

export function colLetter(i) {
  let s = '';
  let n = i + 1;
  while (n > 0) {
    const r = (n - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function tokenize(src) {
  const tokens = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (/\s/.test(c)) { i++; continue; }
    if (/[0-9.]/.test(c)) {
      const m = /^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i.exec(src.slice(i));
      tokens.push({ t: 'num', v: Number(m[0]) });
      i += m[0].length;
      continue;
    }
    if (c === '{') {
      const end = src.indexOf('}', i);
      if (end < 0) throw new Error('missing }');
      tokens.push({ t: 'col', v: src.slice(i + 1, end).trim() });
      i = end + 1;
      continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(src.slice(i));
      tokens.push({ t: 'id', v: m[0] });
      i += m[0].length;
      continue;
    }
    if ('+-*/^(),×÷'.includes(c)) {
      tokens.push({ t: 'op', v: c === '×' ? '*' : c === '÷' ? '/' : c });
      i++;
      continue;
    }
    throw new Error(`unexpected “${c}”`);
  }
  return tokens;
}

export function parseFormula(src) {
  const tokens = tokenize(String(src || '').replace(/^=/, ''));
  let pos = 0;
  const peek = () => tokens[pos];
  const take = (v) => {
    const tok = tokens[pos];
    if (!tok || (v && tok.v !== v)) throw new Error(v ? `expected ${v}` : 'unexpected end');
    pos++;
    return tok;
  };
  function primary() {
    const tok = take();
    if (tok.t === 'num') return { k: 'num', v: tok.v };
    if (tok.t === 'col') return { k: 'col', v: tok.v };
    if (tok.t === 'op' && tok.v === '(') { const e = expr(); take(')'); return e; }
    if (tok.t === 'op' && tok.v === '-') return { k: 'neg', a: power() };
    if (tok.t === 'id') {
      const name = tok.v;
      if (peek() && peek().v === '(') {
        take('(');
        const args = [];
        if (peek() && peek().v !== ')') {
          args.push(expr());
          while (peek() && peek().v === ',') { take(','); args.push(expr()); }
        }
        take(')');
        const lower = name.toLowerCase();
        if (AGGREGATES[lower]) {
          if (args.length !== 1 || args[0].k !== 'col') throw new Error(`${lower}() takes one column`);
          return { k: 'agg', f: lower, col: args[0].v };
        }
        if (!FUNCS[lower]) throw new Error(`unknown function ${name}`);
        return { k: 'fn', f: lower, args };
      }
      if (/^[A-Z]{1,2}$/.test(name)) return { k: 'col', v: name };
      if (name.toLowerCase() === 'pi') return { k: 'num', v: Math.PI };
      throw new Error(`unknown name ${name}`);
    }
    throw new Error('unexpected token');
  }
  function power() {
    const base = primary();
    if (peek() && peek().v === '^') { take('^'); return { k: 'bin', op: '^', a: base, b: unary() }; }
    return base;
  }
  function unary() {
    if (peek() && peek().v === '-') { take('-'); return { k: 'neg', a: unary() }; }
    if (peek() && peek().v === '+') { take('+'); return unary(); }
    return power();
  }
  function term() {
    let a = unary();
    while (peek() && (peek().v === '*' || peek().v === '/')) { const op = take().v; a = { k: 'bin', op, a, b: unary() }; }
    return a;
  }
  function expr() {
    let a = term();
    while (peek() && (peek().v === '+' || peek().v === '-')) { const op = take().v; a = { k: 'bin', op, a, b: term() }; }
    return a;
  }
  const ast = expr();
  if (pos < tokens.length) throw new Error('unexpected text after the formula');
  return ast;
}

// columns: [{ name }], resolveColumn(ref) -> index; values(index) -> array
// of numbers for the whole column; cell(rowIndex, colIndex) -> number.
export function evaluate(ast, ctx, row) {
  switch (ast.k) {
    case 'num': return ast.v;
    case 'col': return ctx.cell(row, ctx.resolve(ast.v));
    case 'neg': return -evaluate(ast.a, ctx, row);
    case 'agg': return AGGREGATES[ast.f](ctx.values(ctx.resolve(ast.col)));
    case 'fn': return FUNCS[ast.f](...ast.args.map((a) => evaluate(a, ctx, row)));
    case 'bin': {
      const a = evaluate(ast.a, ctx, row);
      const b = evaluate(ast.b, ctx, row);
      if (ast.op === '+') return a + b;
      if (ast.op === '-') return a - b;
      if (ast.op === '*') return a * b;
      if (ast.op === '/') return a / b;
      return a ** b;
    }
    default: return NaN;
  }
}

// The value grid of a sheet with formula columns filled in (as numbers).
export function computeSheet(sheet) {
  const cols = sheet.columns || [];
  const rows = sheet.rows || [];
  const errors = {};
  const computed = rows.map((r) => cols.map((_c, i) => r[i] ?? ''));
  const resolve = (ref) => {
    const byName = cols.findIndex((c) => (c.name || '').trim().toLowerCase() === String(ref).trim().toLowerCase());
    if (byName >= 0) return byName;
    const letters = String(ref).toUpperCase();
    if (/^[A-Z]{1,2}$/.test(letters)) {
      let n = 0;
      for (const ch of letters) n = n * 26 + (ch.charCodeAt(0) - 64);
      if (n - 1 < cols.length) return n - 1;
    }
    throw new Error(`no column ${ref}`);
  };
  // Formula columns may use earlier formula columns; two passes covers
  // references in either direction without cycles running forever.
  for (let pass = 0; pass < 2; pass++) {
    cols.forEach((col, ci) => {
      if (col.type !== 'formula') return;
      let ast;
      try { ast = parseFormula(col.formula || ''); } catch (e) { errors[ci] = e.message; return; }
      const ctx = {
        resolve,
        cell: (ri, cj) => toNumber(computed[ri][cj]),
        values: (cj) => computed.map((r) => toNumber(r[cj])).filter(Number.isFinite),
      };
      delete errors[ci];
      for (let ri = 0; ri < rows.length; ri++) {
        try {
          const v = evaluate(ast, ctx, ri);
          computed[ri][ci] = Number.isFinite(v) ? v : '';
        } catch (e) {
          errors[ci] = e.message;
          computed[ri][ci] = '';
        }
      }
    });
  }
  return { values: computed, errors };
}
