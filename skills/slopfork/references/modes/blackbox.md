# Mode: blackbox

Nobody reads the source: not the main thread, not any subagent, in any phase. Allowed inputs:
- Public documentation (README, docs site, man pages, API reference). List local copies in `unsealed_paths`.
- Running the original through `probe_commands` (CLI invocations, an adapter that only *imports and calls* the public API, HTTP requests to a running instance).
- Observed output: goldens, recorded traffic, screenshots.

## Setup
- `sealed_paths`: the source checkout **and** the installed package location (e.g. `site-packages/<pkg>`, `node_modules/<pkg>`). Installed Python/JS packages ship their source, so leaving the install dir unsealed defeats blackbox.
- `sealed_url_patterns`: the repo's blob/raw/tree URLs and package-registry source downloads.
- Write the adapter for the original at `.slopfork/adapters/original.*` using **only documented API** (README/API docs). It isn't sealed, because it contains nothing that came from the source. Running it is execution, not reading: the installed package is only touched by the interpreter, which the guard doesn't see.

## Discovering behavior
1. Inventory from the docs: every documented function, option, and output format.
2. Probe systematically: boundary values, empty inputs, invalid inputs (record the error type and message), large inputs (record timing). Save every probe as a case in `.slopfork/goldens/`.
3. Use property discovery: for randomized APIs, sample many seeds and infer invariants (e.g. "every generated maze is a spanning tree over the cells").
4. Write the spec from the observations, marking each claim as **documented** or **observed**.

Expect gaps. Undocumented behavior that the probes never trigger won't be ported. List known unknowns in the report.
