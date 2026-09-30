// Durations in a page's text that are steps to time ("incubate 30 min",
// "spin 10 min", "block 1 h"), for the step timers (timers.js) and run mode.
// Time points are not steps: "6, 24, 48 h", "at 24 h", "the 48 h samples",
// "48 h post-transduction" or "T = 6 h" get no ⏱.

export const DURATION_RE = /\b(\d+(?:\.\d+)?)(?:\s*[-–]\s*\d+(?:\.\d+)?)?\s*(hours?|hrs?|h|minutes?|mins?|min|seconds?|secs?|sec|s)\b(?![\w/°])/gi;

// Just before: another number in a list ("6, 24, 48 h", "24 h and 48 h"),
// "at", "T =", "time point".
const POINT_BEFORE = /(?:\d\s*(?:h|hrs?|min|s)?\s*(?:,|and|or|&|\/)\s*|\b(?:at|by|T\s*=?|t\s*=|time\s*-?points?|timepoints?)\s*)$/i;
// Just after: what a time point is followed by.
const POINT_AFTER = /^[\s-]*(?:time\s*-?points?|timepoints?|post\b|p\.?\s?[it]\.?(?=\s|$|[,;.)])|samples?\b|harvest|old\b|later\b|ago\b|(?:,|and|or|&)\s*\d+(?:\.\d+)?\s*(?:h|hrs?|hours?|min|s)\b)/i;

export function durationSeconds(amount, unit) {
  const u = unit.toLowerCase();
  const n = Number(amount);
  if (u.startsWith('h')) return n * 3600;
  if (u.startsWith('m')) return n * 60;
  return n;
}

export function findDurations(text) {
  const out = [];
  DURATION_RE.lastIndex = 0;
  let m;
  while ((m = DURATION_RE.exec(text))) {
    const seconds = durationSeconds(m[1], m[2]);
    if (!(seconds > 0 && seconds <= 72 * 3600)) continue;
    const before = text.slice(Math.max(0, m.index - 24), m.index);
    const after = text.slice(m.index + m[0].length, m.index + m[0].length + 24);
    if (POINT_BEFORE.test(before) || POINT_AFTER.test(after)) continue;
    out.push({ index: m.index, length: m[0].length, seconds, text: m[0] });
  }
  return out;
}
