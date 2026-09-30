// Run by tests/test_notebook_blocks.py: the plate-reader block's standard series order, in Node.
import assert from 'node:assert/strict';
import { seriesOrder } from '../../frontend/src/blocks/plate.js';

const range = (rows, cols) => rows.flatMap((r) => cols.map((c) => `${r}${c}`));
// Side-by-side duplicates, A9:G10: the series goes down the rows, each row's pair together.
assert.deepEqual(seriesOrder(range(['A', 'B', 'C'], [9, 10])), ['A9', 'A10', 'B9', 'B10', 'C9', 'C10']);
// Stacked duplicates, A1:D2: the series goes across the columns.
assert.deepEqual(seriesOrder(range(['A', 'B'], [1, 2, 3, 4])), ['A1', 'B1', 'A2', 'B2', 'A3', 'B3', 'A4', 'B4']);
// One column or one row: in its own order, whatever the clicking order was.
assert.deepEqual(seriesOrder(['C1', 'A1', 'B1']), ['A1', 'B1', 'C1']);
assert.deepEqual(seriesOrder(['A3', 'A1', 'A2']), ['A1', 'A2', 'A3']);
console.log('ok');
