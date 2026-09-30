// Run by tests/test_notebook_blocks.py: which durations in a page get a step timer, in Node.
import assert from 'node:assert/strict';
import { findDurations, timerLabel } from '../../frontend/src/durations.js';

const timed = (text) => findDurations(text).map((d) => d.text);
// Steps are timed.
assert.deepEqual(timed('Incubate 30 min at 37 °C, then spin 10 min.'), ['30 min', '10 min']);
assert.deepEqual(timed('Block 1 h in 5% milk'), ['1 h']);
assert.deepEqual(timed('Heat shock 45 s, ice 2 min'), ['45 s', '2 min']);
assert.deepEqual(timed('Transfect, then wait 48 h before selection'), ['48 h']);
assert.deepEqual(timed('Stain 5-10 min'), ['5-10 min']);
assert.deepEqual(timed('Run: 95 °C 2 min; 40 × (95 °C 15 s, 60 °C 60 s)'), ['2 min', '15 s', '60 s']);
// Time points are not.
assert.deepEqual(timed('4 doses × 3 time points (6, 24, 48 h) × 3 reps'), []);
assert.deepEqual(timed('Harvest at 24 h and 48 h'), []);
assert.deepEqual(timed('Lysates 6 h, 24 h and 48 h after treatment'), []);
assert.deepEqual(timed('the 48 h samples'), []);
assert.deepEqual(timed('48 h harvest: filter 0.45 µm'), []);
assert.deepEqual(timed('RNA from cells 72 h post-transduction'), []);
assert.deepEqual(timed('T = 6 h'), []);
assert.deepEqual(timed('24 h time point'), []);
// Each timer is named by its own step.
{
  const t = 'Tue: lyse in TRIzol, incubate 5 min at RT, then centrifuge 12,000 × g 15 min at 4 °C.';
  const names = findDurations(t).map((d) => timerLabel(t, d.index, d.index + d.length));
  assert.deepEqual(names, ['incubate 5 min at RT', 'centrifuge 12,000 × g 15 min at 4 °C']);
}
console.log('ok');
