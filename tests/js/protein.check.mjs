// Run by tests/test_notebook_blocks.py: the calculator block's protein A280 maths, in Node.
import assert from 'node:assert/strict';
import { proteinConc, proteinParams } from '../../frontend/src/blocks/calc.js';

// Hen egg-white lysozyme, mature chain (6 Trp, 3 Tyr, 8 Cys): 14313.14 g/mol,
// ε280 6×5500 + 3×1490 + 4×125 = 37,970 with every Cys paired, 37,470 reduced.
const lysozyme = 'KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL';
const p = proteinParams(lysozyme);
assert.equal(p.length, 129);
assert.ok(Math.abs(p.mw - 14313.14) < 0.5, `MW ${p.mw}`);
assert.equal(p.epsilon, 37970);
assert.equal(p.epsilonReduced, 37470);
assert.equal(proteinParams('MKV JUNK1'), null);        // J and U are not amino acids here

// A280 0.5 of a 1:10 dilution, 1 cm: 0.5 / 37970 × 10 = 131.68 µM = 1.8848 mg/mL.
const c = proteinConc({ a280: 0.5, epsilon: p.epsilon, mw: p.mw, path: 1, dilution: 10 });
assert.ok(Math.abs(c.uM - 131.68) < 0.01, `µM ${c.uM}`);
assert.ok(Math.abs(c.mgPerMl - 1.8848) < 0.001, `mg/mL ${c.mgPerMl}`);
console.log('ok');
