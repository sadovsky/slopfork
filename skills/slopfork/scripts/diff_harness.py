#!/usr/bin/env python3
"""Differential harness for slopfork L2.

Adapters speak a JSON protocol: one case object in, one result object out.
With --batch, the adapter receives all cases as JSON lines on stdin and must
emit one result line per case, in order. Without --batch, the adapter runs
once per case.

Subcommands:
  record   run an adapter (usually the original) and save results as goldens
  compare  run an adapter (usually the target) and diff against goldens
  check    run an adapter and pipe each (case, result) pair to an invariant
           checker, which replies {"ok": bool, "why": str}

Each case must have a unique "id". Cases may set "compare": "exact" (default),
"invariant" (skip golden diff, rely on `check`), or "skip". "compare" may also
be an object keyed by profile name, e.g. {"tx": "exact", "cr": "invariant"},
so ports with different obligations share one case file; select the key with
--profile.
"""

import argparse
import json
import math
import shlex
import subprocess
import sys


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def compare_kind(case, profile):
    kind = case.get("compare", "exact")
    if isinstance(kind, dict):
        if profile not in kind:
            sys.exit(f"case {case.get('id')} has per-profile compare {sorted(kind)} but --profile is {profile!r}")
        kind = kind[profile]
    return kind


def run_adapter(cmd, cases, batch, timeout):
    argv = shlex.split(cmd)
    if batch:
        payload = "".join(json.dumps(c) + "\n" for c in cases)
        p = subprocess.run(argv, input=payload, capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            sys.exit(f"adapter failed (exit {p.returncode}):\n{p.stderr[-4000:]}")
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        if len(lines) != len(cases):
            sys.exit(f"adapter returned {len(lines)} results for {len(cases)} cases\n{p.stderr[-2000:]}")
        return [json.loads(l) for l in lines]
    out = []
    for c in cases:
        p = subprocess.run(argv, input=json.dumps(c), capture_output=True, text=True, timeout=timeout)
        if p.returncode != 0:
            out.append({"ok": False, "error": {"kind": "AdapterCrash", "message": p.stderr[-1000:]}})
            continue
        out.append(json.loads(p.stdout))
    return out


def strip_keys(obj, ignore):
    if isinstance(obj, dict):
        return {k: strip_keys(v, ignore) for k, v in obj.items() if k not in ignore}
    if isinstance(obj, list):
        return [strip_keys(v, ignore) for v in obj]
    return obj


def diff(a, b, tol, path="$"):
    """Return the first difference as a string, or None if equal."""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a is b else f"{path}: {a!r} != {b!r}"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b or (tol and math.isclose(a, b, rel_tol=tol, abs_tol=tol)):
            return None
        return f"{path}: {a!r} != {b!r}"
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return f"{path}: keys differ: only-expected={sorted(a.keys() - b.keys())} only-actual={sorted(b.keys() - a.keys())}"
        for k in a:
            d = diff(a[k], b[k], tol, f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = diff(x, y, tol, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def normalize_error(result, error_map):
    """Map target error kinds onto source error kinds; messages are not compared."""
    if isinstance(result, dict) and not result.get("ok", True):
        err = dict(result.get("error") or {})
        err["kind"] = error_map.get(err.get("kind"), err.get("kind"))
        err.pop("message", None)
        return {"ok": False, "error": err}
    return result


def cmd_record(args):
    cases = load_jsonl(args.cases)
    results = run_adapter(args.cmd, cases, args.batch, args.timeout)
    write_jsonl(args.out, [{"id": c["id"], "result": r} for c, r in zip(cases, results)])
    print(f"recorded {len(results)} goldens -> {args.out}")


def cmd_compare(args):
    cases = load_jsonl(args.cases)
    expected = {row["id"]: row["result"] for row in load_jsonl(args.expected)}
    error_map = json.load(open(args.error_map)) if args.error_map else {}
    ignore = set(args.ignore_key or [])
    todo = [c for c in cases if compare_kind(c, args.profile) == "exact"]
    results = run_adapter(args.cmd, todo, args.batch, args.timeout)
    failures = []
    for c, r in zip(todo, results):
        if c["id"] not in expected:
            failures.append((c["id"], "no golden recorded"))
            continue
        want = strip_keys(normalize_error(expected[c["id"]], {}), ignore)
        got = strip_keys(normalize_error(r, error_map), ignore)
        d = diff(want, got, args.float_tol)
        if d:
            failures.append((c["id"], d))
    report(len(todo), failures, len(cases) - len(todo), args.json_report)


def cmd_check(args):
    cases = load_jsonl(args.cases)
    todo = [c for c in cases if compare_kind(c, args.profile) != "skip"]
    results = run_adapter(args.cmd, todo, args.batch, args.timeout)
    payload = "".join(json.dumps({"case": c, "result": r}) + "\n" for c, r in zip(todo, results))
    p = subprocess.run(shlex.split(args.checker), input=payload, capture_output=True, text=True, timeout=args.timeout)
    if p.returncode != 0:
        sys.exit(f"checker failed (exit {p.returncode}):\n{p.stderr[-4000:]}")
    verdicts = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
    if len(verdicts) != len(todo):
        sys.exit(f"checker returned {len(verdicts)} verdicts for {len(todo)} cases")
    failures = [(c["id"], v.get("why", "invariant violated")) for c, v in zip(todo, verdicts) if not v.get("ok")]
    report(len(todo), failures, len(cases) - len(todo), args.json_report)


def report(n, failures, skipped, json_path):
    print(f"{n - len(failures)}/{n} passed" + (f", {skipped} not compared" if skipped else ""))
    for cid, why in failures[:50]:
        print(f"  FAIL {cid}: {why}")
    if len(failures) > 50:
        print(f"  ... {len(failures) - 50} more")
    if json_path:
        with open(json_path, "w") as f:
            json.dump({"total": n, "passed": n - len(failures), "skipped": skipped,
                       "failures": [{"id": i, "why": w} for i, w in failures]}, f, indent=2)
    sys.exit(1 if failures else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="sub", required=True)

    def common(p):
        p.add_argument("--cases", required=True, help="JSONL file of cases")
        p.add_argument("--cmd", required=True, help="adapter command")
        p.add_argument("--batch", action="store_true", help="send all cases to one adapter process")
        p.add_argument("--timeout", type=float, default=600)
        p.add_argument("--json-report")
        p.add_argument("--profile", help="key into per-profile \"compare\" objects")

    p = sub.add_parser("record"); common(p)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("compare"); common(p)
    p.add_argument("--expected", required=True)
    p.add_argument("--float-tol", type=float, default=0.0)
    p.add_argument("--ignore-key", action="append", help="drop this key anywhere before comparing")
    p.add_argument("--error-map", help="JSON object mapping target error kinds to source error kinds")
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("check"); common(p)
    p.add_argument("--checker", required=True, help="reads {case,result} JSONL, writes {ok,why} JSONL")
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
