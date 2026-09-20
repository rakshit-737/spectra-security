# `config/rules/obligations/` — obligation axioms

Status: **not started**. Zero obligation axioms are authored. This directory contains this README
and nothing else.

Owning sections: Part I §22 and §25 (the axiom set and the silent envelope), Part I §34.2 (file
placement), Part II §64 (well-definedness checks), Part II §67 (the threat model that motivates
them), Part II §76 (what an obligation witness is and is not).

Due: **M4**. Part I §52.7 lists the obligation axioms as an M4 deliverable, each with a must-fire
and a must-not-fire unit test, and the acceptance criterion is that every axiom has both tests and
both pass.

## 1. What an obligation axiom is

An obligation axiom states that one observed fact structurally entails an earlier unobserved one:
if `session.used` is observed, then `session.issued` happened, whether or not any record survived
to witness it. `fd.read` entails `fd.open`. These are the axioms that let the kernel admit a step
it cannot see.

An obligation axiom therefore licenses an **obligation-induced silent instance**: a rule instance
carrying a `LicenseId` whose basis is `OBLIGATION`, citing the observed facts that created the
obligation. Part II §57.6 lists `LicenseBasis` as the closed set `BLIND SUPPRESSED OBLIGATION`.

## 2. The honesty rule that governs this directory

Evidence that an obligation axiom FIRED is not evidence that the ghost step occurred. Part II §76
states this directly, and it constrains every surface:

- An obligation-induced silent instance is rendered **GHOST**, like any other silent instance.
- It is excluded from every observed-record count, even though it cites observed records.
- Part II §69.6.3 gives it a dedicated bit in the SFB instance flags — bit1 `obligation_induced`,
  distinct from bit0 `silent` — precisely so the UI can cite the observed records that created the
  obligation while still rendering the node GHOST.
- No narration, no chart, no README sentence may present an obligation-induced step as observed.

## 3. Required fields per axiom

TODO(decision: the axiom file shape is not fully specified): Part I §34.2 says obligation axioms
live in `config/rules/obligations/*.toml` and Part I §52.7 counts roughly forty of them, but no
section gives the complete field list the way Part I §34.4 does for detection rules. The fields
below are the ones sections actually name. Fix the shape at M4 in
`config/schema/rules.obligations.schema.json`, and record the decision in `docs/adr/`.

| Field | Meaning | Named by |
|---|---|---|
| `id` | Stable axiom identifier, unique, never reused. | implied by every other catalog |
| `consequent` | The observed fact that triggers the obligation. | Part II §67.3 |
| `antecedent` | The entailed earlier fact that may be admitted silently. | Part II §67.3 |
| `max_witnesses` | Upper bound on how many observed facts may cite one obligation-induced silent instance. Checked by the `obligation_multiplicity` well-definedness check. | Part II §64 |
| `provenance` | Non-empty prose: why this entailment holds in the modeled system. | consistent with Part I §34.4 |
| `tests` | The must-fire test and the must-not-fire test. Both required. | Part I §52.7 |

## 4. Checks

None of these are implemented.

- **`obligation_multiplicity`** (Part II §64): an obligation-induced silent instance may be cited by
  at most `max_witnesses` observed facts. Linear in the instance count.
- **Must-fire / must-not-fire** (Part I §52.7): every axiom has both tests and both pass. An axiom
  with only one of the two is not counted and fails the M4 gate.
- **`make lint-vocab`** V5/V6: the forbidden-synonym and retired-term checks apply here as
  everywhere. In particular, do not name an obligation-induced step an `assumption`, an
  `allowance`, an `exception`, a `waiver`, a `permit`, a `guess`, a `hypothetical`, an
  `inferred_step` or an `assumed_step`. The concepts are **license** and **silent instance**.

## 5. Why the adversary cares

Part II §67.3 models an adversary who suppresses telemetry specifically to avoid leaving an
unsatisfiable obligation pair — an attacker who knows the axiom set. Part II §61.4.1 makes this an
explicit operator mode: `respect_obligations = true` models an adversary who knows the axioms,
`false` one who does not, and the degradation matrix must contain both.

That is the reason each axiom needs a must-not-fire test as much as a must-fire test: an axiom that
fires too eagerly manufactures steps that did not happen, and the zero-false-ROBUST invariant is
exactly the thing it would break.

## 6. Negative requirements

- Do not present an obligation-induced step as observed, anywhere, in any form.
- Do not count an obligation-induced silent instance in an observed-record count.
- Do not add an axiom without both tests.
- Do not add an axiom without provenance.
- Do not add an axiom to make a scenario reach its goal. Read Part II §70 first.
- Do not put an obligation axiom in the detection rule table. The two are separately hashed and
  separately ablated; Part II §70 defines a `B3_no_obligations` baseline that requires the axiom set
  to be independently disableable.
