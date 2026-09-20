# Planning documents

Session-one output. Nothing here describes code that exists.

| File | What it holds |
|---|---|
| `PLAN_v1.md` | Milestones M0-M10, the minimum publishable core, the descope ladder, the language tiers, the evidence protocol, the CI tier model, and the decisions taken so far. |
| `DECISIONS.md` | The open decision queue: 140 unresolved specification conflicts, triaged by the milestone each blocks, each with one answerable question and a conservative default. |
| `CONFLICTS.md` | The Part I / Part II conflict audit. 353 disagreements classified as resolved, silent or unresolved. |
| `CONFLICTS_FULL.md` | The same audit unabridged, with full quotations from both sides. |
| `GLOSSARY_STUB.md` | The canonical vocabulary: one concept, one name, one identifier type, one owning section. Superseded by `docs/vocab.toml` once that is generated. |

## Read order

1. `PLAN_v1.md` — what is being built and in what order.
2. `DECISIONS.md` — what must be decided before each milestone.
3. `CONFLICTS.md` — why those decisions exist.

## The state of the specification

It is not yet buildable as written. Part II was added to close structural defects in Part I, and
the audit found that it contradicts Part I in 353 places — 213 of them without saying so. The next
work item after the skeleton is a reconciliation pass, not implementation.

Building proceeds on the recorded defaults in `DECISIONS.md`. A default is a written-down
assumption, not an answer.
