import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "slopfork", "scripts")
HARNESS = os.path.join(SCRIPTS, "diff_harness.py")
AUDIT = os.path.join(SCRIPTS, "leak_audit.py")

# Adapter: {"op": "div", "args": [a, b]} -> floor division, Python semantics unless TRUNC=1.
ADAPTER = r'''
import json, math, os, sys
def run(c):
    a, b = c["args"]
    if b == 0:
        return {"ok": False, "error": {"kind": os.environ.get("ERR", "ZeroDivisionError"), "message": "boom"}}
    q = math.trunc(a / b) if os.environ.get("TRUNC") else a // b
    return {"ok": True, "value": q, "timing": 0.1}
if os.environ.get("BATCH"):
    for line in sys.stdin:
        print(json.dumps(run(json.loads(line))))
else:
    print(json.dumps(run(json.load(sys.stdin))))
'''

CHECKER = r'''
import json, sys
for line in sys.stdin:
    d = json.loads(line)
    v = d["result"].get("value")
    print(json.dumps({"ok": v is None or isinstance(v, int), "why": "value not int"}))
'''


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.adapter = os.path.join(d, "adapter.py")
        self.checker = os.path.join(d, "checker.py")
        self.cases = os.path.join(d, "cases.jsonl")
        self.goldens = os.path.join(d, "expected.jsonl")
        write(self.adapter, ADAPTER)
        write(self.checker, CHECKER)
        cases = [{"id": "pos", "args": [7, 2]}, {"id": "neg", "args": [-7, 2]},
                 {"id": "zero", "args": [1, 0]}, {"id": "rand", "args": [3, 3], "compare": "invariant"}]
        write(self.cases, "".join(json.dumps(c) + "\n" for c in cases))

    def tearDown(self):
        self.tmp.cleanup()

    def run_h(self, *args, env=None):
        e = dict(os.environ, **(env or {}))
        return subprocess.run([sys.executable, HARNESS, *args], capture_output=True, text=True, env=e)

    def record(self):
        p = self.run_h("record", "--cases", self.cases, "--cmd", f"{sys.executable} {self.adapter}", "--out", self.goldens)
        self.assertEqual(p.returncode, 0, p.stderr)

    def compare(self, env=None, *extra):
        return self.run_h("compare", "--cases", self.cases, "--expected", self.goldens, "--batch",
                          "--cmd", f"{sys.executable} {self.adapter}", *extra, env=dict(BATCH="1", **(env or {})))

    def test_identical_passes(self):
        self.record()
        p = self.compare()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("3/3 passed, 1 not compared", p.stdout)

    def test_semantic_drift_detected(self):
        self.record()
        p = self.compare({"TRUNC": "1"})
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAIL neg: $.value: -4 != -3", p.stdout)

    def test_error_kind_mapping(self):
        self.record()
        self.assertEqual(self.compare({"ERR": "RangeError"}).returncode, 1)
        emap = os.path.join(self.tmp.name, "errors.json")
        write(emap, json.dumps({"RangeError": "ZeroDivisionError"}))
        self.assertEqual(self.compare({"ERR": "RangeError"}, "--error-map", emap).returncode, 0)

    def test_ignore_key(self):
        self.record()
        self.assertEqual(self.compare({}, "--ignore-key", "timing").returncode, 0)

    def test_profiles(self):
        write(self.cases, json.dumps({"id": "neg", "args": [-7, 2], "compare": {"tx": "exact", "cr": "invariant"}}) + "\n")
        self.record()
        tx = self.compare({"TRUNC": "1"}, "--profile", "tx")
        self.assertEqual(tx.returncode, 1)
        cr = self.compare({"TRUNC": "1"}, "--profile", "cr")
        self.assertEqual(cr.returncode, 0, cr.stdout)
        self.assertIn("0/0 passed, 1 not compared", cr.stdout)
        self.assertNotEqual(self.compare({}).returncode, 0)  # missing --profile is an error

    def test_check(self):
        p = self.run_h("check", "--cases", self.cases, "--cmd", f"{sys.executable} {self.adapter}",
                       "--checker", f"{sys.executable} {self.checker}")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("4/4 passed", p.stdout)


class LeakAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        for sub in ("src", "spec", "docs", "target"):
            os.makedirs(os.path.join(d, sub))
        write(os.path.join(d, "src", "grid.py"),
              "def _carve_passages(grid, row, col, visited_cells):\n"
              "    for nr, nc in neighbours(row, col):\n"
              "        if (nr, nc) not in visited_cells and grid[nr][nc] == 1:\n"
              "            visited_cells.add((nr, nc))\n"
              "            grid[(row + nr) // 2][(col + nc) // 2] = 0\n"
              "            _carve_passages(grid, nr, nc, visited_cells)\n")
        write(os.path.join(d, "docs", "API.md"), "Call `generate_grid(h, w)` to build a maze.\n")
        self.d = d

    def tearDown(self):
        self.tmp.cleanup()

    def audit(self, mode, against):
        return subprocess.run([sys.executable, AUDIT, "--source", os.path.join(self.d, "src"), "--against", against,
                               "--mode", mode, "--allow-identifiers-from", os.path.join(self.d, "docs")],
                              capture_output=True, text=True)

    def test_clean_spec(self):
        write(os.path.join(self.d, "spec", "gen.md"),
              "# generate_grid\nEvery generated maze is a spanning tree over the odd cells.\n")
        p = self.audit("spec", os.path.join(self.d, "spec"))
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_leaky_spec(self):
        write(os.path.join(self.d, "spec", "gen.md"),
              "Recursively call _carve_passages using visited_cells.\n```\nfor nr, nc in neighbours(row, col):\n```\n")
        p = self.audit("spec", os.path.join(self.d, "spec"))
        self.assertEqual(p.returncode, 1)
        self.assertIn("code fence", p.stdout)
        self.assertIn("'_carve_passages'", p.stdout)
        self.assertIn("'visited_cells'", p.stdout)
        self.assertNotIn("def _carve", p.stdout)  # never echoes source text

    def test_renamed_copy_detected_in_code_mode(self):
        write(os.path.join(self.d, "target", "grid.py"),
              "def carve(g, r, c, seen):\n"
              "    for a, b in nbrs(r, c):\n"
              "        if (a, b) not in seen and g[a][b] == 1:\n"
              "            seen.add((a, b))\n"
              "            g[(r + a) // 2][(c + b) // 2] = 0\n"
              "            carve(g, a, b, seen)\n")
        p = self.audit("code", os.path.join(self.d, "target"))
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("shared with source grid.py", p.stdout)


if __name__ == "__main__":
    unittest.main()
