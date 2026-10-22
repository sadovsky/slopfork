# L2: differential testing

Run the original and the target on the same inputs and compare. This is the workhorse level for libraries and CLIs.

## Adapters
Write one adapter per side. An adapter takes a **case** as JSON on stdin and writes a **result** as JSON on stdout. Keep the protocol identical on both sides:

```json
// case
{"id": "prims-5x5-seed1", "op": "generate", "args": {"algo": "Prims", "h": 5, "w": 5}, "seed": 1}
// result
{"ok": true, "value": {"grid": ["#####", "#...#", "..."]}}
// or
{"ok": false, "error": {"kind": "ValueError", "message": "..."}}
```

Adapters can also take a JSON-lines batch (one case per line in, one result per line out) so a process isn't spawned per case. `scripts/diff_harness.py` supports both through `--batch`.

## Workflow
```
# 1. generate cases (hand-written + generated) into .slopfork/goldens/<module>/cases.jsonl
# 2. record goldens from the original
python3 scripts/diff_harness.py record --cases .slopfork/goldens/<m>/cases.jsonl \
    --cmd "python3 ../<target>-dirty/adapter_original.py" --out .slopfork/goldens/<m>/expected.jsonl --batch
# 3. compare the target
python3 scripts/diff_harness.py compare --cases ... --expected .slopfork/goldens/<m>/expected.jsonl \
    --cmd "node dist/adapter.js" --batch [--float-tol 1e-9] [--ignore-key timing]
# 4. optional invariant checker on target output (for nondeterministic ops)
python3 scripts/diff_harness.py check --cases ... --cmd "node dist/adapter.js" \
    --checker "python3 .slopfork/checkers/maze_invariants.py" --batch
```

## Comparison strategies (choose per operation)
| Situation | Strategy |
|---|---|
| Deterministic pure function | **exact** golden match (with float tolerance) |
| Randomized, but the RNG can be ported bit-for-bit | port the RNG; exact match under a fixed seed |
| Randomized, RNG not portable (e.g. NumPy PCG64 + algorithm-specific draws) | **invariant** checking on the target output, plus **distributional** checks over many seeds (e.g. mean dead-end count within tolerance of the original's) |
| Randomized op feeding deterministic ops | generate the input with the original, record it, feed the *same* recorded input to the target's deterministic op, exact match |
| Errors | match the error *kind* through a mapping table (ValueError -> RangeError / Err(InvalidArgs)); don't match messages unless they're part of the public contract |

The third and fourth rows matter a lot: most real libraries mix randomness and determinism. Split each operation into its random part and its deterministic part and test them differently.

## Case generation
- Hand-pick edge cases: empty, minimum size, degenerate shapes, max size, invalid args.
- Generate randomly with a fixed seed (store the seed in the case).
- Shrinking: when a generated case fails, minimize it and add the minimal case to the hand-picked set.
