# L5: formal

Opt-in per module. Two separate tools for two separate questions:

## TLA+ (state machines, concurrency, protocols)
"Does the design have the same safe and live behaviors?"
- Model the **original's** behavior as a TLA+ spec (state variables, `Init`, `Next`, invariants, temporal properties). In cleanroom, the spec-writer writes it. It's a spec, so clean agents may read it.
- Check it with TLC (`java -jar tla2tools.jar -config M.cfg M.tla`) or Apalache for larger state spaces.
- Link the target through **trace validation**: instrument the target to log state transitions and check each logged trace against the TLA+ `Next` relation. This catches implementation drift that the model alone can't.
- Good fit: job schedulers, caches with invalidation, retry/backoff, lock managers, sync protocols, anything with `async` interleavings.

## Lean 4 (pure functions, algorithms)
"Does the target function compute the same thing (or satisfy the property)?"
- Write a reference definition in Lean that mirrors the spec, then prove properties (e.g. "generated maze is a spanning tree", "solver output is a valid path from start to end", "parser round-trips").
- Equivalence to the actual target code is the hard part. Options, cheapest first:
  1. Prove properties of the Lean reference, then differentially test target vs Lean reference (compile the Lean reference and run it as a third L2 adapter).
  2. For Rust, extract to Lean with Aeneas or Charon and prove equivalence on the extracted model.
  3. Write the core in Lean and generate the target from it. Rarely worth it.
- Use Mathlib for graph and combinatorics lemmas. Budget time accordingly: L5 proofs can take longer than the port itself.

Report what was proved, what was only model-checked (with bounds: TLC checks finite instances), and the trusted assumptions.
