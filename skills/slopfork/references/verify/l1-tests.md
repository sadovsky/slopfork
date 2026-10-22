# L1: unit tests

- **transpile**: port the source's test suite test by test. Keep a table in `features.md` mapping source test -> target test. Tests that can't be ported (they test internals that don't exist in the target) get a note, not a silent drop.
- **cleanroom / blackbox**: derive tests from the spec. Each spec example becomes a test, and each invariant becomes a property test (fast-check, proptest, Hypothesis).
- Count source tests, ported tests, and skipped tests (with reasons) in the report.
- Don't weaken an assertion to make a ported test pass. A failing ported test is either a port bug or a recorded, intentional deviation.
