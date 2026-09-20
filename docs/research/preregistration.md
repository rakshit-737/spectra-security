# SPECTRA pre-registration

Source: build specification Part II, section 70. This is the prose half of the pre-registration;
`research/prereg.toml` is the machine-readable, hashed half. Both are committed together, in the
same commit, **before any rule exists**.

Status of this document: skeleton delivered, every section empty. Status of `research/prereg.toml`:
not started. Status of the protocol: not started.

Ordering warning, load-bearing: if `rules/rules.toml`, `axioms/` or `controls.toml` exist in the
repository before the pre-registration commit, the protocol is dead and cannot be retrofitted.
Commit dates are not used for ordering; commit ancestry is. Do not backdate and do not rewrite
history to fake ancestry.

TODO (decision made here — milestone names): each section below states WHEN it must be filled in
terms of the protocol events this specification defines (PREREG, SEAL, DEV, FREEZE, UNSEAL, RUN,
REPORT), because the milestone identifiers M1..MN are not yet assigned. When the milestone plan is
written into `BUILD_LOG.md`, map each event to its milestone id here and keep both.

## What this protocol is, and the limit it does not exceed

The following paragraph is required and is reproduced as written in the specification:

> This protocol does not make cheating impossible. A solo author can always regenerate a pool or
> rewrite history. What it does is make every act of contamination an explicit, irreversible,
> committed event with a name and an ancestor commit, so that contamination is visible rather than
> deniable.

This document does not claim that the protocol provides blinding, independent replication or
adversarial review, because it provides none of those.

_To fill in: nothing. This section is complete as written and is not edited._

## Research questions

_Empty. To fill in: the questions this project will answer, each phrased so that an outcome could
contradict it. WHEN: before the PREREG commit — this section is the reason the commit exists._

## What would falsify each research question

_Empty. To fill in: for each question above, the outcome that would count as a refutation, stated
before any run. WHEN: before the PREREG commit._

## What this protocol does not establish

_Empty except for the mandatory minimum list below. To fill in: anything else discovered later that
the protocol cannot establish; entries are added, never removed. WHEN: the minimum list before the
PREREG commit; additions whenever a limit is discovered._

The list must contain at minimum, and must not be softened:

- Single-author generator bias: the same person wrote the generator, the ground truth, the rule
  table, the axioms, the control catalog and the liveness configuration.
- The scenario families were chosen by the same person who wrote the rules.
- The held-out seal is self-administered. It constrains the order of operations; it is not a
  security boundary against the author.
- No external dataset and no external tool were used. Every baseline is an ablation or a trivial
  reference authored by the same person.

Forbidden here and everywhere: "held-out validation", "independent evaluation", "blind evaluation",
"externally validated", "pre-registered study" (say "pre-registered protocol, self-administered"),
and "generalises to real telemetry".

## Authoring roles and their separation

_Empty. To fill in: the five authoring roles (protocol, generator, modeller, harness, reporter),
what each owns, what each may read and what each may never read, matching `research/roles.toml`.
WHEN: before the PREREG commit; `make check-roles` must be able to run from the first rule commit
onward._

## Scenario pools

_Empty. To fill in: the development pool and its binding size cap, the held-out families, the
held-out seed domain, and the red-team pool reference, matching `research/pools.toml`. WHEN: before
the PREREG commit. Pool membership is append-only thereafter._

## Held-out language component

_Empty. To fill in: which polyglot component is held out — named here **before it is written** — and
the statement that its reconstruction quality is reported as a separate labelled row wherever
reconstruction quality is reported, including when that row is worse. WHEN: before the held-out
component is authored, and before the SEAL event._

## Metric definitions

_Empty. To fill in: every quantity this project will ever publish, each with its numerator,
denominator, estimator, aggregation, suppression rule and pre-declared decision rule, matching the
metric declarations in `research/prereg.toml`. A metric defined after the curve is seen is not a
metric. WHEN: before the PREREG commit._

Negative requirement, binding on this section: no metric may be a confidence, probability, severity,
risk score, likelihood or any scalar that collapses a set-valued output. Residual reachability is a
set and is published as a sorted list of identifiers, never as a number.

## Hypotheses

_Empty. To fill in: each hypothesis with its statement, the metric that decides it, and the outcome
that would falsify it. WHEN: before the PREREG commit._

## Seeds, replication and variance

_Empty. To fill in: the binding minimum replicate count per cell, the replicate index range, the
reported statistic and its mandatory dispersion measure, and the pure seed-derivation function so
that any cell can be re-run in isolation and byte-identically. WHEN: before the PREREG commit;
raising the replicate count later is a pre-registration amendment, never a commit that also touches
the harness._

Reporting rules this section must state: every published cell carries a statistic and its
dispersion; the replicate count is printed next to every statistic; a cell with an errored, timed-out
or flagged replicate is reported as partial with its flag list and never silently averaged over the
survivors; and there is no smoothing, no curve fitting and no interpolation between degradation
levels.

## The sealing protocol

_Empty. To fill in: how the held-out pool is generated, tarred with fixed ordering and fixed
metadata, encrypted to an identity kept outside the repository, and committed as ciphertext plus a
manifest; and the statement that because generation is deterministic, anyone can later re-derive the
plaintext from the committed spec and the generator at the sealing commit and confirm it hashes to
the recorded value. WHEN: before the SEAL event, which precedes the first rule commit._

This section must state plainly that sealing is a self-discipline mechanism, not a security boundary
against the author.

## The unseal event

_Empty. To fill in: the preconditions for unsealing — a committed rules lock that is an ancestor of
HEAD, a clean and pushed working tree, a passing ledger check — and the rule that the unseal record
is committed before any held-out run. WHEN: before the UNSEAL event. There is no resealing: once
unsealed, a pool can never again produce headline numbers after any subsequent rules edit._

## The frozen-rules rule

_Empty. To fill in: what `rules.lock` pins (the canonical guard abstract syntax tree, the axioms,
the control catalog including its bit-position assignment, the liveness configuration, the goal
library, the entity-resolution configuration, the generator source tree and the metric code), and
why the lock hashes the canonical abstract syntax tree rather than file bytes. WHEN: before the
FREEZE event._

This section must state that breaking a freeze is a normal engineering event that must be cheap to
do and expensive to hide: it requires a ledger entry, increments the lock generation, and marks
every existing held-out result row superseded rather than deleting it.

## The overfit ledger

_Empty. To fill in: the rule that every rule, axiom, guard, threshold, liveness parameter, control
level or entity-resolution heuristic changed in response to a failing scenario is recorded, with no
exception for obvious bugs; the closed enumeration of change kinds; and the fact that a change
conditioned on something only one scenario exhibits is forbidden outright. WHEN: before the first
rule is authored, i.e. before the DEV phase begins._

## Tuned versus held-out reporting

_Empty. To fill in: the rule that pool labels travel with the data rather than the prose, that every
table is rendered for both pools side by side with the development column headed as tuned and not a
result, and that the README may quote held-out rows only. WHEN: before the first results table is
rendered, i.e. before the REPORT phase._

## Baselines and the fairness contract

_Empty. To fill in: the required arms, what each one does, why each exists, and the per-arm input
matrix that the harness enforces by giving each arm a read-only mount containing only its declared
inputs. A single-arm run may not produce a primary result. WHEN: before the first primary result is
produced, i.e. before the FREEZE event._

This section must state that the arms are ablations and trivial references authored by the same
person; that SPECTRA has been compared against no external tool; and that a favourable comparison
against one's own ablations is evidence that the machinery does something, not evidence that the
machinery is best. The arms are never described as prior work, competitors or the state of the art.

## Amendments

_Empty. To fill in: the rule that `research/prereg.toml` is never edited after the sealing commit,
that changes are new append-only amendment files, and that an amendment's confirmatory or
exploratory effect is computed from the seal state rather than declared by hand. WHEN: at the first
amendment; the mechanism itself is described before the SEAL event._

An amendment authored after the first unseal makes every outcome it touches exploratory for the
remaining life of that pool. Exploratory outcomes are rendered separately, are excluded from the
README, and are never described with "shows", "demonstrates" or "validates".

## Timeline and gate map

_Empty. To fill in: the ordered chain PREREG, SEAL, DEV, FREEZE, UNSEAL, RUN, REPORT, with the guard
that each transition must satisfy, and the table of per-push and docs-build gates that enforce it.
WHEN: before the PREREG commit, since the first guard applies to that commit itself._

Gates named by the specification, all **not started**: `check-roles`, `prereg-check`,
`check-ledger`, `check-freeze`, `lint-metrics`, `lint-arms`, `lint-tables`, `check-readme-pool`,
`check-ledger-backfill`, `check-pools-disjoint`.

## The strongest honest sentence available

_Empty until there is a result to attach it to. To fill in: nothing else. WHEN: at the REPORT phase._

When that time comes, the sentence is this one and no stronger: "Headline numbers were produced on
scenarios generated and hash-sealed before the rule table was authored, under a rule-table hash
frozen before the seal was opened, with every post-hoc rule change recorded in a published ledger."
