// Statistics for data sheets: summaries per group, t-tests (Welch,
// Student, paired), Mann–Whitney U, one-way ANOVA, Holm-corrected pairwise
// comparisons and least-squares lines. p-values come from the regularised
// incomplete beta function (Numerical Recipes, 3rd ed., §6.4).

function logGamma(x) {
  const c = [76.18009172947146, -86.50532032941677, 24.01409824083091,
    -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
  let y = x;
  const tmp = x + 5.5 - (x + 0.5) * Math.log(x + 5.5);
  let ser = 1.000000000190015;
  for (let j = 0; j < 6; j++) ser += c[j] / ++y;
  return -tmp + Math.log(2.5066282746310005 * ser / x);
}

function betacf(a, b, x) {
  const MAXIT = 300;
  const EPS = 3e-14;
  const FPMIN = 1e-300;
  const qab = a + b;
  const qap = a + 1;
  const qam = a - 1;
  let c = 1;
  let d = 1 - qab * x / qap;
  if (Math.abs(d) < FPMIN) d = FPMIN;
  d = 1 / d;
  let h = d;
  for (let m = 1; m <= MAXIT; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d; h *= d * c;
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < EPS) break;
  }
  return h;
}

export function incBeta(x, a, b) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(logGamma(a + b) - logGamma(a) - logGamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
}

// Two-sided p for Student's t with df degrees of freedom.
export function tTwoSided(t, df) {
  if (!Number.isFinite(t) || !(df > 0)) return NaN;
  return incBeta(df / (df + t * t), df / 2, 0.5);
}

// Upper tail of F(d1, d2).
export function fUpper(f, d1, d2) {
  if (!Number.isFinite(f) || f < 0) return NaN;
  return incBeta(d2 / (d2 + d1 * f), d2 / 2, d1 / 2);
}

function normalUpper(z) {
  // Abramowitz & Stegun 7.1.26 on erfc.
  const x = Math.abs(z) / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * x);
  const erfc = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))) * Math.exp(-x * x);
  return z >= 0 ? erfc / 2 : 1 - erfc / 2;
}

export function mean(xs) { return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN; }

export function variance(xs) {
  if (xs.length < 2) return NaN;
  const m = mean(xs);
  return xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1);
}

export function sd(xs) { return Math.sqrt(variance(xs)); }

export function median(xs) {
  if (!xs.length) return NaN;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export function quantile(xs, q) {
  if (!xs.length) return NaN;
  const s = [...xs].sort((a, b) => a - b);
  const pos = (s.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}

export function summary(xs) {
  const n = xs.length;
  const s = sd(xs);
  return {
    n, mean: mean(xs), sd: s, sem: n > 1 ? s / Math.sqrt(n) : NaN, median: median(xs),
    min: n ? Math.min(...xs) : NaN, max: n ? Math.max(...xs) : NaN,
    q1: quantile(xs, 0.25), q3: quantile(xs, 0.75),
  };
}

export function welch(a, b) {
  const va = variance(a) / a.length;
  const vb = variance(b) / b.length;
  const t = (mean(a) - mean(b)) / Math.sqrt(va + vb);
  const df = (va + vb) ** 2 / (va ** 2 / (a.length - 1) + vb ** 2 / (b.length - 1));
  return { test: "Welch's t-test", t, df, p: tTwoSided(t, df) };
}

export function student(a, b) {
  const df = a.length + b.length - 2;
  const sp = ((a.length - 1) * variance(a) + (b.length - 1) * variance(b)) / df;
  const t = (mean(a) - mean(b)) / Math.sqrt(sp * (1 / a.length + 1 / b.length));
  return { test: "Student's t-test", t, df, p: tTwoSided(t, df) };
}

export function paired(a, b) {
  const n = Math.min(a.length, b.length);
  const d = [];
  for (let i = 0; i < n; i++) d.push(a[i] - b[i]);
  const t = mean(d) / (sd(d) / Math.sqrt(n));
  return { test: 'Paired t-test', t, df: n - 1, p: tTwoSided(t, n - 1), note: a.length !== b.length ? 'unequal group sizes: pairs taken in row order' : '' };
}

function ranks(values) {
  const order = values.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]);
  const r = new Array(values.length);
  let ties = 0;
  for (let i = 0; i < order.length;) {
    let j = i;
    while (j + 1 < order.length && order[j + 1][0] === order[i][0]) j++;
    const avg = (i + j) / 2 + 1;
    const count = j - i + 1;
    if (count > 1) ties += count ** 3 - count;
    for (let k = i; k <= j; k++) r[order[k][1]] = avg;
    i = j + 1;
  }
  return { r, ties };
}

export function mannWhitney(a, b) {
  const { r, ties } = ranks([...a, ...b]);
  const n1 = a.length;
  const n2 = b.length;
  const r1 = r.slice(0, n1).reduce((x, y) => x + y, 0);
  const u1 = r1 - n1 * (n1 + 1) / 2;
  const u = Math.min(u1, n1 * n2 - u1);
  const n = n1 + n2;
  const sigma = Math.sqrt((n1 * n2 / 12) * ((n + 1) - ties / (n * (n - 1))));
  const z = (u - n1 * n2 / 2 + 0.5) / sigma; // continuity-corrected
  return { test: 'Mann–Whitney U', u, z, p: Math.min(1, 2 * normalUpper(Math.abs(z))), note: n < 20 ? 'normal approximation; small samples' : '' };
}

export function anova(groups) {
  const all = groups.flat();
  const grand = mean(all);
  const k = groups.length;
  const n = all.length;
  let ssb = 0;
  let ssw = 0;
  for (const g of groups) {
    const m = mean(g);
    ssb += g.length * (m - grand) ** 2;
    ssw += g.reduce((a, x) => a + (x - m) ** 2, 0);
  }
  const d1 = k - 1;
  const d2 = n - k;
  const f = (ssb / d1) / (ssw / d2);
  return { test: 'One-way ANOVA', f, df1: d1, df2: d2, p: fUpper(f, d1, d2) };
}

// Holm–Bonferroni: adjusted p-values in the original order.
export function holm(ps) {
  const idx = ps.map((p, i) => [p, i]).sort((a, b) => a[0] - b[0]);
  const m = ps.length;
  const out = new Array(m);
  let running = 0;
  idx.forEach(([p, i], rank) => {
    running = Math.max(running, Math.min(1, (m - rank) * p));
    out[i] = running;
  });
  return out;
}

export const TESTS = {
  auto: 'Automatic',
  welch: "Welch's t-test",
  student: "Student's t-test",
  paired: 'Paired t-test',
  mannwhitney: 'Mann–Whitney U',
  anova: 'One-way ANOVA',
  none: 'No test',
};

function twoGroup(kind, a, b) {
  if (kind === 'student') return student(a, b);
  if (kind === 'paired') return paired(a, b);
  if (kind === 'mannwhitney') return mannWhitney(a, b);
  return welch(a, b);
}

// groups: [{ name, values }]. Returns { overall, comparisons: [{ a, b, p, padj }] }.
export function compare(groups, kind = 'auto', control = '') {
  const usable = groups.filter((g) => g.values.length >= 2);
  if (kind === 'none' || usable.length < 2) return { overall: null, comparisons: [] };
  if (usable.length === 2 && kind !== 'anova') {
    const result = twoGroup(kind === 'auto' ? 'welch' : kind, usable[0].values, usable[1].values);
    return { overall: result, comparisons: [{ a: usable[0].name, b: usable[1].name, p: result.p, padj: result.p }] };
  }
  const overall = anova(usable.map((g) => g.values));
  const pairKind = kind === 'mannwhitney' ? 'mannwhitney' : (kind === 'student' ? 'student' : 'welch');
  const ref = usable.find((g) => g.name === control);
  const pairs = [];
  if (ref) {
    for (const g of usable) if (g !== ref) pairs.push([ref, g]);
  } else {
    for (let i = 0; i < usable.length; i++) for (let j = i + 1; j < usable.length; j++) pairs.push([usable[i], usable[j]]);
  }
  const raw = pairs.map(([x, y]) => twoGroup(pairKind, x.values, y.values).p);
  const adj = holm(raw);
  return {
    overall,
    pairTest: TESTS[pairKind] + ', Holm-corrected',
    comparisons: pairs.map(([x, y], i) => ({ a: x.name, b: y.name, p: raw[i], padj: adj[i] })),
  };
}

export function linearFit(xs, ys) {
  const n = xs.length;
  if (n < 2) return null;
  const mx = mean(xs);
  const my = mean(ys);
  let sxx = 0;
  let sxy = 0;
  let syy = 0;
  for (let i = 0; i < n; i++) {
    sxx += (xs[i] - mx) ** 2;
    sxy += (xs[i] - mx) * (ys[i] - my);
    syy += (ys[i] - my) ** 2;
  }
  if (sxx === 0) return null;
  const slope = sxy / sxx;
  const intercept = my - slope * mx;
  const r2 = syy === 0 ? 1 : (sxy * sxy) / (sxx * syy);
  return { slope, intercept, r2, n };
}
