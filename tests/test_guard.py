import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "provenance_guard.py")


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = os.path.realpath(self.tmp.name)
        self.src = os.path.join(base, "orig")
        self.tgt = os.path.join(base, "port")
        os.makedirs(os.path.join(self.src, "docs"))
        os.makedirs(os.path.join(self.tgt, ".slopfork"))
        write(os.path.join(self.src, "lib.py"), "x = 1\n")
        write(os.path.join(self.src, "docs", "API.md"), "# API\n")

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, **kw):
        cfg = {"mode": "cleanroom", "phase": "build", "sealed_paths": ["../orig"],
               "unsealed_paths": ["../orig/docs"], "probe_commands": [r"^python3 run_orig\.py$"],
               "sealed_url_patterns": [r"github\.com/x/orig/blob/"]}
        cfg.update(kw)
        write(os.path.join(self.tgt, ".slopfork", "config.json"), json.dumps(cfg))

    def call(self, tool, tool_input, **extra):
        payload = {"cwd": self.tgt, "tool_name": tool, "tool_input": tool_input, **extra}
        p = subprocess.run([sys.executable, GUARD], input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout.strip():
            return "allow"
        return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]

    def log(self):
        path = os.path.join(self.tgt, ".slopfork", "provenance.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(l) for l in f]

    def test_no_config_is_noop(self):
        self.assertEqual(self.call("Read", {"file_path": os.path.join(self.src, "lib.py")}), "allow")

    def test_transpile_allows_and_logs(self):
        self.config(mode="transpile")
        self.assertEqual(self.call("Read", {"file_path": os.path.join(self.src, "lib.py")}), "allow")
        self.assertEqual(self.log()[0]["decision"], "allow")

    def test_unrelated_paths_not_logged(self):
        self.config()
        self.assertEqual(self.call("Read", {"file_path": os.path.join(self.tgt, "README.md")}), "allow")
        self.assertEqual(self.log(), [])

    def test_cleanroom_build_denies_everyone(self):
        self.config(phase="build")
        f = os.path.join(self.src, "lib.py")
        self.assertEqual(self.call("Read", {"file_path": f}), "deny")
        self.assertEqual(self.call("Read", {"file_path": f}, agent_id="a1", agent_type="slopfork:spec-writer"), "deny")
        self.assertEqual(len(self.log()), 2)

    def test_cleanroom_spec_phase_only_spec_writer(self):
        self.config(phase="spec")
        f = os.path.join(self.src, "lib.py")
        self.assertEqual(self.call("Read", {"file_path": f}), "deny")  # main thread
        self.assertEqual(self.call("Read", {"file_path": f}, agent_id="a1", agent_type="slopfork:builder"), "deny")
        self.assertEqual(self.call("Read", {"file_path": f}, agent_id="a2", agent_type="slopfork:spec-writer"), "allow")
        # agent_type without agent_id (a --agent main session) is not a subagent
        self.assertEqual(self.call("Read", {"file_path": f}, agent_type="spec-writer"), "deny")

    def test_unsealed_docs_readable(self):
        self.config(mode="blackbox")
        self.assertEqual(self.call("Read", {"file_path": os.path.join(self.src, "docs", "API.md")}), "allow")

    def test_relative_and_ancestor_paths(self):
        self.config(mode="blackbox")
        self.assertEqual(self.call("Read", {"file_path": "../orig/lib.py"}), "deny")
        self.assertEqual(self.call("Grep", {"pattern": "x", "path": os.path.dirname(self.src)}), "deny")
        self.assertEqual(self.call("Glob", {"pattern": "**/*.py"}), "allow")  # cwd = target, not an ancestor

    def test_sealed_dir_inside_repo_blocks_repo_wide_search(self):
        # Documented trade-off: keep dirty dirs outside the target checkout.
        self.config(mode="blackbox", sealed_paths=["../orig", ".slopfork/dirty"])
        self.assertEqual(self.call("Grep", {"pattern": "x"}), "deny")
        self.config(mode="blackbox", sealed_paths=["../orig", "../port-dirty"])
        self.assertEqual(self.call("Grep", {"pattern": "x"}), "allow")

    def test_bash(self):
        self.config(mode="blackbox")
        self.assertEqual(self.call("Bash", {"command": "cat ../orig/lib.py"}), "deny")
        self.assertEqual(self.call("Bash", {"command": f"grep -r x {self.src}"}), "deny")
        self.assertEqual(self.call("Bash", {"command": "npm test"}), "allow")

    def test_probe_commands(self):
        self.config(mode="blackbox", sealed_paths=["../orig", "run_orig.py"])
        write(os.path.join(self.tgt, "run_orig.py"), "")
        self.assertEqual(self.call("Bash", {"command": "python3 run_orig.py"}), "allow")
        self.assertEqual(self.call("Bash", {"command": "cat run_orig.py"}), "deny")

    def test_webfetch(self):
        self.config(mode="blackbox")
        self.assertEqual(self.call("WebFetch", {"url": "https://github.com/x/orig/blob/main/lib.py"}), "deny")
        self.assertEqual(self.call("WebFetch", {"url": "https://github.com/x/orig#readme"}), "allow")

    def test_bad_config_fails_closed(self):
        write(os.path.join(self.tgt, ".slopfork", "config.json"), "{nope")
        self.assertEqual(self.call("Read", {"file_path": os.path.join(self.tgt, "a")}), "deny")


if __name__ == "__main__":
    unittest.main()
