# L0: build

The target compiles, typechecks, lints, and a smoke run succeeds. Every module needs at least L0.

- TypeScript: `tsc --noEmit` with `strict: true`, plus eslint. Target an explicit `lib`/`target`. No `any` in public signatures.
- Rust: `cargo build`, `cargo clippy -- -D warnings`, `cargo fmt --check`. Write `#![forbid(unsafe_code)]` unless the user allows unsafe code.
- Python: `ruff`, `mypy --strict` or `pyright`.
- Go: `go vet`, `staticcheck`.

Set up CI for these in the target repo early (first slice) so every later slice is checked automatically.

Smoke check: one script in `.slopfork/smoke.*` that imports the public API and exercises one happy path per module.
