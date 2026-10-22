# Mode: transpile

You may read the source freely and translate it. The output is a **derivative work** of the source.

## Obligations
- Keep the source's license where it requires that (MIT/BSD/Apache: keep the copyright notice; Apache-2.0: also NOTICE and a statement of changes; GPL/LGPL/AGPL/MPL: the target must use a compatible copyleft license for the covered parts). Check `../license-matrix.md`.
- Add a `NOTICE` or README section: "Ported from <source>@<sha> by <author>, licensed <license>."
- If the source has no license, stop and tell the user: all rights are reserved, so transpiling it is not permitted without permission. Offer cleanroom or blackbox instead, and mention that those carry their own risk.

## How to translate well
- Translate **behavior**, not syntax. Map source idioms to target idioms (Python exceptions -> Rust `Result`; NumPy arrays -> typed arrays or `ndarray`; duck typing -> interfaces or traits).
- Keep a **mapping table** in `.slopfork/mapping.md`: source symbol -> target symbol, plus notes on semantic gaps. Builders and reviewers rely on it.
- Port the source tests first (L1). They are the cheapest oracle.
- Watch for silent semantic drift:
  - Integer width and overflow (Python int is unbounded; JS number is f64; Rust panics in debug and wraps in release).
  - Division and modulo with negative numbers (`-7 // 2` in Python is -4, `Math.trunc(-7/2)` is -3; `%` signs differ too).
  - Sorting stability, dict/map iteration order, string indexing (UTF-16 in JS, bytes in Rust, code points in Python).
  - Mutable default arguments, shared references, copy vs view semantics (NumPy slices are views).
  - RNG: see `../verify/l2-differential.md` on randomness. If byte-identical output is a goal, port the RNG too (e.g. implement MT19937 to match Python's `random`).
- Comments: translate the ones that explain intent. Don't carry over stale or TODO noise.
