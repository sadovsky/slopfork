# slopfork

A Claude Code plugin for porting a codebase from one language or stack to another, with two settings you choose up front:

- **Provenance mode**: how much of the original Claude may read.
  - `transpile`: read and translate. The output is a derivative work; the license carries over.
  - `cleanroom`: a `spec-writer` subagent reads the source and writes behavioral specs. `builder` agents implement from the specs alone. A hook blocks everyone else from reading the source and logs every attempt.
  - `blackbox`: nobody reads the source. Behavior comes from docs and from running the original.
- **Verification level**, set per module:
  - L0 build
  - L1 unit tests
  - L2 differential (goldens, invariants, distributions)
  - L3 API contract replay
  - L4 screenshot and accessibility-tree diff
  - L5 formal (TLA+ model checking, Lean proofs)

> Not legal advice. Cleanroom and blackbox reproduce the *process* of a clean-room rewrite and leave an audit trail. They don't guarantee the result is free of copyright claims, and the model may have seen the original in training.

## Install

```
/plugin marketplace add sadovsky/slopfork
/plugin install slopfork@slopfork
```

## Use

In the (empty) target repo, ask Claude something like *"slopfork ../mazelib into TypeScript, cleanroom, L2 by default"*. The skill then:

1. **Intake**: interviews you, detects the license, and writes `.slopfork/config.json`.
2. **Inventory**: writes `.slopfork/features.md`, a module list that doubles as the parity matrix.
3. **Spec**: writes `.slopfork/spec/*.md`. In cleanroom mode each spec is leak-audited.
4. **Harness**: builds adapters and goldens against the original *before* any target code exists.
5. **Build**: works leaf modules first, verifying each slice at its level.
6. **Verify and report**: writes `.slopfork/REPORT.md` with parity, deviations, and the provenance summary.

`phase` in `config.json` drives the provenance guard. In cleanroom mode, only the spec-writer can read sealed paths, and only during the `inventory`, `spec`, `harness`, and `audit` phases.

## Layout

| Path | What |
|---|---|
| `skills/slopfork/SKILL.md` | Entry point and phase driver |
| `skills/slopfork/references/modes/` | transpile / cleanroom / blackbox rules |
| `skills/slopfork/references/verify/` | L0–L5 how-tos |
| `skills/slopfork/templates/` | config, features, spec, report |
| `skills/slopfork/scripts/diff_harness.py` | L2 record / compare / invariant check over a JSON adapter protocol |
| `skills/slopfork/scripts/leak_audit.py` | Spec and code leakage audit; never prints source text |
| `agents/` | `spec-writer` (dirty side), `builder`, `verifier` (clean side) |
| `hooks/provenance_guard.py` | PreToolUse guard and `.slopfork/provenance.jsonl` audit log |
| `examples/mazelib/` | First fixture: Python mazelib → TypeScript and Rust |

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```

The guard is a tripwire, not a sandbox: it matches paths in tool inputs, so a deliberately obfuscated shell command could get around it. For the strongest separation, keep the source outside the target checkout or off the machine during clean phases.
