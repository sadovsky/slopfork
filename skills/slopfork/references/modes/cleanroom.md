# Mode: cleanroom

Two roles that never share a context:

| Role | Reads source? | Writes | Agent |
|---|---|---|---|
| Dirty side | yes | specs, the original's adapter, goldens, leak-audit results | `spec-writer` |
| Clean side | **never** | target code, target tests | `builder`, `verifier`, main thread |

The guard hook enforces this. In cleanroom mode, sealed paths can be read only by a subagent whose type ends in `spec-writer`, and only while `phase` is `inventory`, `spec`, `harness`, or `audit`. The main thread is always denied. That's deliberate: the main thread writes the builders' prompts, so it has to stay clean.

## Setup
1. Put the source **outside** the target checkout (e.g. `../<name>-source`) and list it in `sealed_paths`. List public docs that clean agents may read (README, docs/) in `unsealed_paths`.
2. Add `sealed_url_patterns` for places the code can be fetched from (the GitHub blob/raw URLs of the repo, the package's sdist on PyPI or npm).
3. Keep dirty-side helpers (the original's adapter, scratch notes) **outside** the target checkout, in `../<target>-dirty/`, and add it to `sealed_paths`. Don't put them inside the target repo: a sealed directory inside the repo would make every repo-wide Grep or Glob an ancestor of a sealed path, and the guard would block it. If the original is runnable, add `probe_commands` regexes for invoking the adapter (e.g. `^python3 \.\./<target>-dirty/adapter_original\.py.*$`), so clean agents can **run** it to check behavior without reading it.

## What a spec may contain
- Public API names and signatures as documented, behavior, invariants, complexity expectations, error cases, worked input/output examples.
- Algorithm **names** and published descriptions ("Prim's algorithm, randomized; frontier picks uniformly").

## What a spec must NOT contain
- Code, pseudocode that mirrors the source line by line, private identifiers, the source's comments, distinctive structure (helper decomposition, variable naming).
- Anything copied verbatim beyond short public names.

## Leak audit
Before any spec leaves the `spec` phase:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/slopfork/scripts/leak_audit.py \
  --source <sealed source dir> --against .slopfork/spec --mode spec \
  --allow-identifiers-from <public docs dir>
```

It flags code fences, private identifiers that appear in the spec, and long verbatim token runs shared with the source. The spec-writer fixes the findings and re-runs the audit until it's clean, then records the final audit summary in `.slopfork/spec/AUDIT.md`.

After the build, in `phase: audit`, the spec-writer runs it again with `--mode code --against <target src>`. Flagged overlaps go back to the clean side as **"rewrite <file>:<lines> from spec"**, never with the source text attached.

## Prompting the builder
Give the builder only: the spec file path(s), the golden/recording paths, the target conventions, and the mapping of public API names. Never paraphrase the source to it from memory. If the builder needs more detail, it writes a question into `.slopfork/questions.md`, and the spec-writer answers it in the spec (re-audited).

## Limits
This reproduces the *structure* of a clean-room process and leaves an audit trail. It is not legal advice, and it can't remove what the model may have memorized from training data. For high-stakes work, the user should involve counsel.
