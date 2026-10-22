# Spec: <module>

Provenance: <documented | observed | derived-from-source (cleanroom spec-writer)> · Audit: <pending | clean @ date>

## Purpose
One paragraph: what it does, in user terms.

## Public interface
Names and signatures as **documented**, given in a language-neutral form (types as `int`, `float`, `bool`, `string`, `grid<bool>`, `list<T>`, `optional<T>`).

## Behavior
Numbered, testable statements. For randomized behavior, state the **distribution** or the **invariants**, not the draw order.

## Invariants
Properties that hold for every valid input/output (these become property tests and L2 checkers).

## Errors
| Condition | Error kind | Contractual message? |
|---|---|---|

## Edge cases
| Input | Expected |
|---|---|

## Worked examples
Small input → output pairs (copy from goldens, don't invent them).

## Open questions
Questions from builders, answered here.
