# `config/rules/detection/` — the rule table

Status: **not started**. Zero rules are authored. This directory contains this README and nothing
else.

Owning sections: Part I §22 (the rule table), Part I §34.4 (file shape and validation gates),
Part II §57 (naming), Part II §63 (the guard language), Part II §70 (pre-registration and the
held-out protocol).

Due: **M3**, together with the guard compiler and the control catalog. Part I §52.6 requires
`rules.toml` v1 with at least 25 rules compiled to Rust as an M3 deliverable.

## 1. What a rule is

A rule is one authored implication with a head, a body, a guard, a set of producing sources and a
provenance note. It is data. It is hashed into every run manifest and every certificate. It is
never code.

A grounding of a rule to specific facts is a **rule instance** (`InstanceId`, `in:`), an AND-node of
the hypergraph. The facts are the OR-nodes. Part II §57 rows 12, 21 and 22.

## 2. Required fields per rule

One `[[rule]]` table per rule. Part I §34.4.

| Field | Meaning |
|---|---|
| `id` | `RuleId`, rendered `rl:<snake>`. Unique. Never reused after deletion. |
| `head` | The derived predicate this rule produces. |
| `body` | Array of body predicates. Slot order in the body fixes guard slot numbering. |
| `guard` | A guard expression in the guard language of Part II §63. May be absent. |
| `producing_sources` | Array of `SourceId`. Which declared sources can witness this rule. |
| `silent_possible` | Boolean. Whether a silent instance of this rule may be licensed. |
| `evidence_fields` | Which record fields the witness carries. |
| `provenance` | Non-empty prose: what real-world behavior this rule encodes. |
| `tests` | Names of the positive and negative tests. Both are required. |

**OVERRIDE, Part II §57.8 over Part I §34.4.** Part I's example listed `event_id` in
`evidence_fields`. Evidence cites `RecordId`, never `EventId`. `EventId` is the generator's private
identity for an occurrence, carried only on the oracle channel; the kernel, the collectors, the
grounder and `spectra verify` must not read it. `make lint-oracle-channel` greps these trees for
`event_id` and fails on any hit outside the oracle crate.

**Body ordering is semantic.** Part II §63 C6 renames bound variables to slot indices in order of
their declaration in the rule's `body`. Guard hashes are therefore invariant under renaming within
the guard and **not** invariant under reordering the body. A body reorder is a semantic edit of the
rule table and invalidates certificates. Do not reorder a body for readability.

## 3. Validation gates

Enforced at startup and in `make lint`. Part I §34.4. None of these are implemented.

1. Every `guard` parses to the guard AST and references only controls declared in
   `config/controls/controls.toml`.
2. Every symbol in `body` is the head of another rule or a declared base predicate.
3. `producing_sources` names sources declared in the ingest source registry.
4. Every rule names at least one positive test and one negative test, and both must exist.
5. No rule has a delete or retract effect. The linter rejects the keyword outright.

Additionally, from Part II:

6. `make lint-vocab` check V5 rejects any identifier segment on the forbidden-synonym list. For
   this directory that most often means `detection`, `signature`, `heuristic`, `correlation_rule`
   and `policy` used as an identifier for the concept **rule**, and `match`, `hit`, `firing` or
   `derivation` used for the concept **rule instance**.
7. `make lint-vocab` check V6 rejects the retired term `atom` as a TOML key, with no allowlist.
8. The guard compiler asserts `canon(canon(x)) == canon(x)` bytewise on every compile. Failure is
   an internal compiler error and aborts the build. Part II §63 C8.

## 4. `silent_possible`

`silent_possible = true` is what permits a **silent instance** of this rule: an instance carrying a
`LicenseId` and citing no record, admitted only inside a blind window. Part II §57 rows 23, 25 and
26.

A silent instance is rendered GHOST. GHOST is the derived predicate *every derivation of this node
passes through a silent instance*. Ghost instances never appear in any observed-record count, and a
test counts both to assert it. Part I §52.7.

A license is not evidence. It is a permission granted because a source was not live. Nothing in
this directory may be written as though a silent instance were an observation.

## 5. Pre-registration

Part II §70 seals the rule table against the held-out protocol. Rules are frozen and hash-pinned
before each scenario family, and CI fails on commit-order inversion (`make leakage-gate`, MPC
component C9). Do not write a rule file before the pre-registration commit for its scenario family.
Read Part II §70 before authoring the first rule.

## 6. Negative requirements

- Do not write a rule with a delete or retract effect.
- Do not write a rule without a positive and a negative test.
- Do not write a rule without provenance.
- Do not cite `event_id` in evidence.
- Do not reorder a rule body without accepting that certificates are invalidated.
- Do not put a rule in the database. Policy lives here, under version control.
- Do not tune a rule after seeing a held-out result.
