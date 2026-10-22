#!/usr/bin/env python3
"""PreToolUse guard that enforces a slopfork provenance mode.

Reads the hook payload on stdin, finds the nearest `.slopfork/config.json`
above the session cwd, and decides whether the tool call may touch the
sealed (original) source. Every touch of a sealed path, allowed or denied,
is appended to `.slopfork/provenance.jsonl`.

Policy:
  transpile  -> always allow (still logged)
  blackbox   -> never allow, except Bash commands matching `probe_commands`
  cleanroom  -> allow only when the phase is a "dirty" phase AND the call
                comes from the spec-writer subagent (agent_type ends with
                "spec-writer"). Main-thread calls are always denied.

This is a tripwire, not a sandbox: a determined Bash command can evade
path matching. The strongest setup keeps the source outside the target
checkout (or off the machine) during clean phases.
"""

import json
import os
import re
import shlex
import sys
import time

DIRTY_PHASES = {"inventory", "spec", "harness", "audit"}
SPEC_AGENT_SUFFIX = "spec-writer"
CONFIG_REL = os.path.join(".slopfork", "config.json")
LOG_REL = os.path.join(".slopfork", "provenance.jsonl")


def find_config(start):
    d = os.path.abspath(start)
    while True:
        candidate = os.path.join(d, CONFIG_REL)
        if os.path.isfile(candidate):
            return d, candidate
        parent = os.path.dirname(d)
        if parent == d:
            return None, None
        d = parent


def norm(path, base):
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.realpath(path)


def is_within(child, parent):
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def touches(path, sealed, unsealed):
    """True if reading/searching `path` could expose a sealed path."""
    for s in sealed:
        if is_within(path, s):
            # Explicitly unsealed sub-paths (e.g. public docs) are fine.
            if any(is_within(path, u) for u in unsealed):
                continue
            return s
        # Searching an ancestor of a sealed dir would sweep it in.
        if is_within(s, path):
            return s
    return None


def candidate_paths(tool, tool_input, cwd):
    if tool in ("Read", "NotebookRead"):
        p = tool_input.get("file_path") or tool_input.get("notebook_path")
        return [norm(p, cwd)] if p else []
    if tool in ("Grep", "Glob"):
        return [norm(tool_input.get("path") or cwd, cwd)]
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        try:
            tokens = shlex.split(cmd, posix=True)
        except ValueError:
            tokens = cmd.split()
        out = []
        for t in tokens:
            # Strip redirections and option prefixes like --file=path.
            t = t.split("=", 1)[-1].lstrip("<>")
            if not t or t.startswith("-"):
                continue
            if "/" in t or t.startswith(".") or os.path.exists(os.path.join(cwd, t)):
                out.append(norm(t, cwd))
        return out
    return []


def decide(cfg, payload):
    mode = cfg.get("mode", "transpile")
    phase = cfg.get("phase", "intake")
    agent_type = payload.get("agent_type") or ""
    is_subagent = bool(payload.get("agent_id"))
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if mode == "transpile":
        return "allow", "transpile mode"

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        for pat in cfg.get("probe_commands", []):
            if re.fullmatch(pat, cmd.strip()):
                return "allow", "matches probe_commands (executes original, does not read it)"

    if mode == "blackbox":
        return "deny", "blackbox mode: the original source is sealed for every agent and phase"

    if mode == "cleanroom":
        if phase not in DIRTY_PHASES:
            return "deny", f"cleanroom mode: phase '{phase}' is a clean phase; only the spec (and goldens) may be used"
        if not is_subagent or not agent_type.endswith(SPEC_AGENT_SUFFIX):
            who = agent_type or "main thread"
            return "deny", f"cleanroom mode: only the spec-writer subagent may read the original (caller: {who})"
        return "allow", f"cleanroom {phase} phase, spec-writer"

    return "deny", f"unknown mode '{mode}'"


def emit(decision, reason):
    if decision == "deny":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "[slopfork provenance guard] " + reason,
            }
        }))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)

    cwd = payload.get("cwd") or os.getcwd()
    root, cfg_path = find_config(cwd)
    if not cfg_path:
        sys.exit(0)  # not a slopfork project

    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        # Fail closed for reads; Edit/Write are not matched, so the config can still be fixed.
        emit("deny", f"could not parse {cfg_path} ({e}); fix it before reading files")

    sealed = [norm(p, root) for p in cfg.get("sealed_paths", [])]
    unsealed = [norm(p, root) for p in cfg.get("unsealed_paths", [])]
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    hit = None
    target = None
    if tool == "WebFetch":
        url = tool_input.get("url", "")
        for pat in cfg.get("sealed_url_patterns", []):
            if re.search(pat, url):
                hit, target = pat, url
                break
    else:
        for p in candidate_paths(tool, tool_input, cwd):
            s = touches(p, sealed, unsealed)
            if s:
                hit, target = s, p
                break

    if not hit:
        sys.exit(0)

    decision, reason = decide(cfg, payload)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decision": decision,
        "reason": reason,
        "mode": cfg.get("mode"),
        "phase": cfg.get("phase"),
        "agent_id": payload.get("agent_id"),
        "agent_type": payload.get("agent_type"),
        "tool": tool,
        "target": target,
        "sealed": hit,
    }
    if tool == "Bash":
        entry["command"] = tool_input.get("command", "")[:500]
    try:
        with open(os.path.join(root, LOG_REL), "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    emit(decision, reason)


if __name__ == "__main__":
    main()
