// Run by tests/test_notebook_blocks.py: the qPCR block's analysis, in Node.
import assert from 'node:assert/strict';
import { analyse, parseExport } from '../../frontend/src/blocks/qpcr.js';

const text = `Well,Sample Name,Target Name,Task,CT
A1,V,GAPDH,UNKNOWN,18.1
A2,V,GAPDH,UNKNOWN,18.2
A3,V,MDM2,UNKNOWN,25.0
A4,V,MDM2,UNKNOWN,25.1
B1,N10,GAPDH,UNKNOWN,18.0
B2,N10,GAPDH,UNKNOWN,18.1
B3,N10,MDM2,UNKNOWN,22.0
B4,N10,MDM2,UNKNOWN,22.1
C1,NTC,MDM2,NTC,Undetermined
C2,noRT-1,MDM2,UNKNOWN,33.9
C3,water,GAPDH,NTC,38.5`;

const a = analyse({ rows: parseExport(text), reference: 'GAPDH', control: 'V' });
// No-template and no-RT wells are controls: not samples, not in ΔΔCt.
assert.deepEqual(a.samples, ['V', 'N10']);
assert.deepEqual(a.results.map((r) => r.sample), ['V', 'N10']);
assert.equal(a.controls.length, 3);
// One that amplified is flagged; undetermined or late ones are fine.
assert.deepEqual(a.controls.map((c) => c.amplified), [false, true, false]);
assert.ok(a.flags.some((f) => f.startsWith('noRT-1 · MDM2: control well amplified')));
assert.ok(Math.abs(a.results[1].fold - 2 ** 2.9) < 0.01);   // ΔΔCt = (22.05 − 18.05) − (25.05 − 18.15) = −2.9
console.log('ok');
