# Limitations and known-unsound regions

The README's first screen links to this file with the anchor text
`Limitations and known-unsound regions`. That exact anchor text is gated; do not reword it.

This file is part hand-written frame and part generated. The prose frames a measurement; it never
states one. Every number belongs inside a generated block, and `make limitations` will regenerate
every block from `artifacts/limits/limits.json`; the target is not declared in the Makefile.

**Nothing has been measured.** `artifacts/limits/limits.json` does not exist, the validation matrix
that produces it has not been run, and every block below therefore renders its NOT MEASURED
placeholder. `make release`, once it exists, will refuse to produce a release artifact while any
required block is NOT MEASURED. The target is not declared and nothing enforces this today.

Status of this document: the stub is delivered. Status of every measurement it will carry: not
started.

TODO (decision made here): each generated block below cites `G-LIMITS-COMPLETE`, the release gate
that blocks on a missing block, because the per-block producing gate ids are not yet assigned. When
the validation matrix lands, replace each `see gate` reference with the id of the gate that produces
that block's data, and leave `G-LIMITS-COMPLETE` as the release blocker.

A limitation stated without a measured magnitude is a disclaimer, not a limitation. The frames below
are therefore not a substitute for the blocks; they are the reader's context for numbers that do not
exist yet.

## What a verdict is not

A verdict is a statement about SPECTRA's model of a recorded telemetry bundle: about the rule table,
the obligation axioms, the control catalog, the entity resolution and the licensed blind windows. It
is not a statement about what would have happened. The modelled attacker is non-adaptive: it does
not re-plan when a control is switched on, and a real adversary does. A cut may therefore be
actively misleading as defensive prioritisation advice, and this document says so rather than
burying it.

No generated block: this frame states a scope limit, not a measurement.

## What we cannot see

Suppression detection leans on sources that carry an ordering or chaining property intrinsic to the
producer. Most telemetry has no such property. Where a record can be removed without leaving a
structural trace, and the surrounding window stays inside the calibrated baseline, the removal is
permanently invisible: no obligation fires, no blind window opens, and the kernel cannot license a
hypothesis it has no reason to consider. The block below will report, per declared suppression
class, how many were injected, how many were licensed and how many went undetected, split by
completeness level. It will be generated from measured data; no data has been measured.

<!-- BEGIN GENERATED: invisible_suppression  src=artifacts/limits/limits.json#invisible_suppression  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: invisible_suppression -->

## Where the model is blind

Blind volume is reported per dimension and per completeness level, never aggregated into a single
figure, because a single figure hides exactly the dimension that is worst. The block below will
report, per dimension, the share of the observation window that is blind, the share that is
suppressed and the share that is live. It will be generated from measured data; no data has been
measured.

<!-- BEGIN GENERATED: blind_spot_volume  src=artifacts/limits/limits.json#blind_spot_volume  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: blind_spot_volume -->

## What the temporal-consistency pass cannot see

The pass of ADR-0016 answers one question: does a recorded timestamp contradict the order that its
own source recorded, or a temporal bound the rule table declares? Where it finds one it names the
fewest timestamps that would have to be disbelieved, marks their sources, and weakens the verdict.

Four things defeat it, and three of them defeat it completely:

- **A consistently rewritten source.** Move every record of one source by the same amount and the
  order is intact. There is no contradiction to find, and the pass reports nothing.
- **A forged chain.** A chained source's records can be re-sealed after modification. The chain then
  verifies, and the pass reads what it is given.
- **A source with no sequence number.** The recorded order is the only thing the pass compares
  against. Without it there is nothing to contradict.
- **A rewrite inside the noise.** A record moved by less than the gap to its neighbours contradicts
  nothing, and the pass is silent.

It is therefore not tamper detection, not backdating detection and not a suppression detector, and
no document, transcript or interface in this repository may describe it as any of those. What it
adds is narrow and real: a verdict that something can refuse. Before it existed, the strongest
verdict SPECTRA issues rested on a check that could never fire.

The pass also does not decide WHICH timestamp is wrong. A contradiction says the recorded values
cannot all be true; the correction set is the smallest set that would restore consistency, which is
a different claim and a weaker one.

## Entity resolution is the largest soundness risk

Every downstream proof is a proof about the entities the resolver produced. A false merge does not
degrade a result gracefully: it fabricates a fact, and the kernel then proves things about the
fabrication with full rigour and a clean certificate. A false split hides a chain. The block below
will report pair precision, pair recall, false merges, false splits and the count of verdict flips
under injected ambiguity, per scenario and completeness level. It will be generated from measured
data; no data has been measured.

<!-- BEGIN GENERATED: er_error  src=artifacts/limits/limits.json#er_error  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: er_error -->

## When we flag and what that costs

A run that trips a soundness-affecting flag — ambiguous entity resolution, capped grounding, a
capped corridor set, a greedy cover, subset-only minimality — is never presented as robust. The
flag for a licence voided by backdating is permanently false and is not in that list, because
nothing voids a licence: a disputed timestamp weakens the verdict and leaves the licensed set
alone (ADR-0016), and a flag that can never be set is not a flag a reader should weigh. The share of runs that carry a flag is therefore part of the honest
result, not a footnote: a kernel that flags most of its runs has answered few questions. The two
blocks below will report the flagged share by flag and the capped share by cap. They will be
generated from measured data; no data has been measured.

<!-- BEGIN GENERATED: flagged_run_share  src=artifacts/limits/limits.json#flagged_run_share  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: flagged_run_share -->

<!-- BEGIN GENERATED: capped_run_share  src=artifacts/limits/limits.json#capped_run_share  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: capped_run_share -->

## Non-vacuity

A kernel that answers unsafe to everything satisfies the no-false-robust invariant perfectly and is
worthless. The yield figure is what prevents that reading: it reports how often the kernel reaches a
robust verdict in the cells where ground truth shows the cut genuinely severs the chain. It is
published next to the invariant, always, and neither is quotable without the other. The block below
will report yield, the false-unsafe share and the false-robust count. It will be generated from
measured data; no data has been measured.

<!-- BEGIN GENERATED: verdict_yield  src=artifacts/limits/limits.json#verdict_yield  run=none  gen=tools/limits/render.py -->
**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE.
<!-- END GENERATED: verdict_yield -->

## Naming

ECLIPSE is an internal acronym for this project's proof kernel: Evidence-Licensed Cut Proofs over
Silent Envelopes. It collides with a well-known software foundation, an IDE and a Java toolchain. No
relation is asserted, no mark of theirs is used, and user-facing prose says "the SPECTRA kernel".
The string is banned outright from every crate, module, directory and file name in this repository;
it survives only in prose and in the specification.

No generated block: this frame states a naming disclaimer, not a measurement.

## How to read a stale version of this file

A generated block whose run manifest disagrees with the current rule-table, control-catalog or
entity-resolution configuration hash is stale and fails its gate. Limitations go stale exactly when
the claims that depend on them go stale. If you are reading a rendered copy of this file outside the
repository, it carries no freshness assurance at all.
