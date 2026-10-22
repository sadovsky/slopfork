# mazelib port experiment: transpile vs cleanroom, TypeScript vs Rust

Four autonomous Claude Code sessions ported [mazelib](https://github.com/john-science/mazelib) (Python, ~3.2k lines, MIT) with slopfork. They had identical setups and differed only in target language and provenance mode. All four were checked against the same 2,396 recorded cases in [slopfork-mazelib-goldens](https://github.com/sadovsky/slopfork-mazelib-goldens).

| Arm | Repo |
|---|---|
| TS transpile | [mazelib-ts-tx](https://github.com/sadovsky/mazelib-ts-tx) |
| Rust transpile | [mazelib-rs-tx](https://github.com/sadovsky/mazelib-rs-tx) |
| TS cleanroom | [mazelib-ts-cr](https://github.com/sadovsky/mazelib-ts-cr) |
| Rust cleanroom | [mazelib-rs-cr](https://github.com/sadovsky/mazelib-rs-cr) |

All numbers below were **re-measured by the coordinating session**, not copied from the ports' self-reports, except where marked *(self-reported)*. Run date: 2026-10-22, one run per arm.

## Results

| | TS transpile | Rust transpile | TS cleanroom | Rust cleanroom |
|---|---|---|---|---|
| Goldens, own profile (7 sets, compare + check) | **2,396 / 2,396** | **2,396 / 2,396** | **2,396 / 2,396** | **2,396 / 2,396** |
| Language checks | tsc, 73 tests | fmt, clippy, 67 tests | tsc, 113 tests | fmt, clippy, 115 tests |
| Wall time | 21.9 min | 24.9 min | 29.2 min | 35.0 min |
| Cost (session total) | $8.96 | $11.64 | $16.84 | $21.81 |
| Output tokens | 144k | 168k | 327k | 408k |
| Source / test LOC *(self-reported)* | 2,712 / 900 | 4,087 / 1,099 | 2,842 / 897 | 3,939 / 2,594 |
| Spec questions from builders | n/a | n/a | 2 | 14 |
| Behavioral deviations from the original *(self-reported)* | 2 | 2 | 9 | 15 |
| Sealed-source reads by clean agents | n/a | n/a | **0** | **0** |
| Guard denials (all false positives) | 0 | 0 | 4 | 6 |

The two transpile deviations are the same in both languages: the 20 `KNOWN_BUGS` cases (an Ellers int8 overflow, and the Collision solver crashing on mazes with loops), where the ports return valid results instead of crashing.

### How independent are the cleanroom ports? Exact-match rate against the original

Each cleanroom port was run under the transpile (`tx`, exact) profile, which it wasn't required to meet:

| Case set | TS cleanroom | Rust cleanroom |
|---|---|---|
| generate (1,480 valid seeded mazes) | 33 (2.2%) | 100 (6.8%) |
| entrances | **200 / 200** | 150 / 200 |
| solve | 178 / 372 | 196 / 372 |
| transmute | 76 / 120 | 72 / 120 |
| monte_carlo | 1 / 37 | 1 / 37 |

Generator matches are coincidental: they cluster on low-entropy algorithms and the smallest sizes (TrivialMaze, Sidewinder, Ellers). Solver and transmuter matches are expected, because many of those outputs are uniquely determined by the input maze.

## Findings

1. **Both approaches reach full test parity quickly; the clean room costs about twice as much.** Cleanroom arms took 1.3–1.4x the wall time and 1.9x the cost of the transpile arm in the same language. Rust cost more than TypeScript in both modes.

2. **Exact replication has a hidden dependency beyond the RNG.** Both transpile ports independently discovered that matching the original bit for bit requires emulating **CPython's `set` iteration order**: Prims rebuilds its frontier with `list(set(...))`, and ShortestPath(s) return solutions in set order. Both ported `setobject.c` probing and resizing plus the xxHash-based tuple hash. "Port the RNG" was necessary but not sufficient. That kind of dependency is invisible until differential testing exposes it.

3. **The cleanroom ports are behaviorally independent, and the guard held.** No clean agent (main thread or builder) ever got a read of the original; every allowed sealed read came from the spec-writer during a dirty phase (38 and 57 reads). Seeded generator output matches the original only 2–7% of the time, so the cleanroom generators really do use randomness differently.

4. **Specs leak through structure, not just text, and the text audit can't see it.** The TS cleanroom port reproduces entrance placement **exactly on all 200 cases**. Its spec lists the four sides as *North, South, West, East*: an unusual order that matches the index order of the original's `randrange(4)`. With a bit-compatible RNG and the most natural draws, that ordering alone reproduces the original's choices. The spec passed the leak audit with zero findings. Orderings, enumerations, and tie-breaking rules are a leakage channel that `leak_audit.py` doesn't model.

5. **Token-overlap code audits are a weak provenance signal.**
   - Against the Python original at the default 25-token window, even the transpile ports barely register (0 and 1 findings). At 12 tokens, transpile (49, 44) and cleanroom (20, 36) overlap ranges.
   - Within the same language, cleanroom vs transpile shows 90 (TS) and 167 (Rust) findings at 25 tokens. Inspection shows they're dominated by API-forced boilerplate: import blocks, the public `Maze` fields, constructor defaults, `turn` parsing. Implementing the same public API converges at the token level.
   - The best independence evidence here was **behavioral** (finding 3), not textual.

6. **Without a reference implementation, cleanroom ports drift on untested behavior.** The transpile ports deviate only on the known bugs. The cleanroom ports changed 9 and 15 behaviors, mostly edge cases the goldens don't exercise: different error kinds on bad input, bounded random walks instead of hangs, clamped parameters, ShortestPaths returning a capped set. Most are arguably improvements, but each is a compatibility break nobody tested for. In a clean room, **the test suite is the contract**, and anything outside it is up for grabs.

7. **Rust cleanroom asked 7x as many spec questions as TS (14 vs 2)** and wrote 2.9x the test code. Rust's typed errors and explicit edge cases forced ambiguities into the open that TS silently resolved.

8. **The guard over-blocked but never under-blocked.** All 10 denials were false positives: heredoc bodies containing `//` comments, and `cd ..`, which resolved to an ancestor of the sealed source. Fixed in slopfork `d52624a`. Replaying the logged commands, 9 of the 10 are now allowed. The remaining one, `cd .. && ... ls -R`, is still denied by design, since the guard doesn't follow `cd`.

9. **The maintainer's AI policy surfaced on its own.** The TS cleanroom spec-writer read mazelib's `AGENTS.md`, treated it as data rather than instructions, and flagged in its report that the maintainers object to AI agents working with their repo, recommending the experiment's owner weigh that before publishing. That's the intended behavior.

## Caveats

- One run per arm, one model. Times and costs will vary run to run.
- The clean room can't exclude what the model learned in training; mazelib is a public repo.
- The goldens were recorded on CPython 3.13 with pure-Python mazelib (no compiled Cython). The transpile ports' set-order emulation is specific to that CPython version.
- Costs are the sessions' reported totals at completion, including setup and report writing.

## Follow-ups for slopfork

- **leak_audit:** skip import blocks and API declarations in code mode; report against a same-language control baseline rather than an absolute count; flag enumerations whose order matches the source (finding 4).
- **Behavioral independence metric:** make "exact-match rate under the transpile profile" a standard cleanroom report item.
- **Drift:** in cleanroom mode, have the verifier list behaviors the goldens don't cover, and generate edge-case goldens (invalid parameters, unreachable ends, degenerate grids) before the build phase.
- **Cost model:** note in SKILL.md that cleanroom roughly doubles cost compared with transpile.
