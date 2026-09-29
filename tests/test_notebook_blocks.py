"""The notebook's blocks are JavaScript (frontend/src/blocks); their
arithmetic is checked in Node, when Node is there."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "needs Node")
class Blocks(unittest.TestCase):
    def check(self, name: str) -> None:
        r = subprocess.run(["node", str(ROOT / "tests" / "js" / name)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)

    def test_qpcr_leaves_control_wells_out_and_flags_one_that_amplified(self):
        self.check("qpcr.check.mjs")


if __name__ == "__main__":
    unittest.main()
