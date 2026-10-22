# L3: API contract

For services: the target must answer recorded requests the same way the original does.

1. **Record**: run the original behind a recording proxy (mitmproxy `--save-stream-file`, or a small reverse proxy that logs request/response pairs to JSONL). Drive it with the existing client test suite, a scripted scenario, or real anonymized traffic.
2. **Normalize**: strip or mask volatile fields (timestamps, IDs, ETags, `Date`, trace headers). Put the masks in `.slopfork/contract/normalize.json`.
3. **Replay**: send each recorded request to the target and diff status, selected headers, and the body (JSON compared structurally, with key order ignored).
4. **Schema**: if there's an OpenAPI/GraphQL schema, diff the schemas too (`oasdiff`, `graphql-inspector`). Breaking changes must be zero unless the user approves them.
5. **Stateful flows**: replay in recorded order against a target seeded with the same fixtures. Reset state between scenarios.

Report: requests replayed, exact matches, normalized matches, mismatches (with diffs).
