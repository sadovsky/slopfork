# Example: mazelib (Python) → TypeScript and Rust

First real fixture for slopfork. [`config.json`](config.json) is a starting `.slopfork/config.json` for the port repo.

- **Source**: [john-science/mazelib](https://github.com/john-science/mazelib) @ `56cd882`, MIT. About 3.2k lines of Python with Cython `.pxd` type stubs: 14 generators, 7 solvers, 3 transmuters, and a `Maze` façade.
- **Mode**: `transpile`. MIT allows it; keep the copyright notice and add a "ported from" note.
- **Non-license signal**: the repo's `AGENTS.md` says the maintainer doesn't want AI contributions to *that* repository. A port in a separate repo doesn't contribute upstream, but tell the user before starting and don't open issues or PRs upstream.

## Key decisions surfaced by inventory
- **RNG**: generators draw from Python's `random` (MT19937) and `numpy.random.shuffle` (legacy `RandomState`, also MT19937). `rng_strategy: port-mt19937` means implementing both draw paths bit-exactly so a seeded TS/Rust generator produces the *same maze* as Python. The fallback is `invariants`: compare generators only by properties (perfect maze = spanning tree, every cell reachable, borders intact) plus distribution stats over many seeds.
- **Grids**: NumPy `int8` 2-D arrays → `Uint8Array` with stride (TS) / `Vec<u8>` or `ndarray` (Rust).
- **Solvers and transmuters** run on mazes recorded from the original, so they get exact comparison regardless of the RNG strategy.
- **L5 pilot**: Lean proof that `BacktrackingGenerator` output is a spanning tree of the cell graph, used as a third adapter in L2.

## Two targets
Record goldens once from the Python original. Both the TS and the Rust ports compare against the same `.slopfork/goldens/`, so the second port is cheaper and the two ports cross-check each other.
