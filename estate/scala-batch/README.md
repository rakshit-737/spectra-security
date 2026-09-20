# Scala - nightly batch reconciliation job in the observed estate, emitting a log4j2 pattern layout stream
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise, from Part II 73.1:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component's share is a scheduled batch reconciliation job written in Scala, logging through a
log4j2 pattern layout - a format whose fields exist only as positions in a formatting string chosen
by the service author. It is also the estate's only source whose activity is bursty and scheduled
rather than request-driven, which is a different shape of evidence from everything else in the tier.
Reconstruction across it must contain no Scala-specific branch, identifier or filename in `ingest/`
(73.3.4).

What is not promised: nothing about throughput, streaming behaviour or the job's correctness as a
reconciliation. No comparison against any SPECTRA component is offered, and no timing number is
claimed anywhere. It is a subject of reconstruction, and under Part I 30.7.3 it may not import the
rule table, the control catalog, the axioms or the certificate schema.

One boundary is stated because Part I 31.14 placed Scala on the other side of it: this component is
not a reconstruction baseline. It does not reconstruct state, it does not compete with the batch
engine, and nothing it produces is compared against the pipeline's output as an alternative
implementation. Under Part II's tiers, an independently authored alternative implementation would be
Tier B and would carry a measured-comparison promise; this is Tier C and carries the reconstruction
promise only.

Nothing here is implemented. No batch has run and no line has been emitted or ingested.

## What lives here

Planned contents, none of which exist yet:

- The batch job: a scheduled pass that reads records belonging to other estate services, reconciles
  them against an internal ledger, and acts on the differences it finds.
- The log4j2 configuration whose pattern layout fixes the emitted line shape. This configuration is
  the emission contract and is reviewed as one.
- A build definition with a pinned compiler version and dependencies resolvable from the offline
  vendor path recorded in `polyglot.toml`.
- A seeded driver that runs the job over a committed input fixture so emitted content is
  reproducible, with no wall clock deciding what the records say.
- A committed golden of one seeded run.
- A `Makefile` exposing the declared entrypoint and a manifest fragment declaring the emitted
  `format_id` (format is declared in the manifest, never sniffed - 59.6).

No SPECTRA code and no reconstruction logic of any kind.

## Consumer edge

Required edge (73.3.1): a downstream artifact owned by a different component must consume this
output. The intended consumer is the scenario expectation owned by the kernel and scenario-fixture
side, on the step where the batch job acts with its own scheduled identity against another service's
data - that action is a link in the chain and these records are its only evidence. Because the job is
scheduled rather than continuous, it is also the natural source for a degradation cell in which the
gap between bursts must not be mistaken for an unexplained silence.

Plainly, for session one: nothing exists, so deleting this directory today breaks nothing. That is
why the edge is a precondition on the commit that creates the directory; a component consumed only
by its own test suite fails with `SELF_CONSUMING` and is deleted under 73.6 rather than defended.

## How it is exercised

- CI job: `polyglot-c / estate-scala-batch`, named in the component's `ci.job` field.
- Tier: T2 (74.4 assigns Tier C/D language jobs and the polyglot mutation audit to the nightly
  tier), with a changed-path per-PR run permitted by 73.9. The job must run the batch and collect
  its emitted stream; compiling it does not satisfy 73.3.2.
- Make target: the declared entrypoint `make -C estate/scala-batch emit`, with the load-bearing
  checks run by `make polyglot-audit`.

A red job here does not block a milestone, appears in the README status table within one commit, and
blocks any tagged release. JVM build times make this component a candidate for the changed-path rule
rather than for any per-push execution.

## Mutation check

- Operator: `drop_records(p, seed)` (73.5, the designated telemetry-emitter operator), applied to
  output only.
- Corruption, concretely: after a seeded run, a seeded fraction of the emitted pattern-layout lines
  is deleted from the collected stream before ingest, including the lines recording the batch
  identity's action against another service's data. The file stays well-formed and the run exits
  zero.
- Gate that must go RED: the assertion named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-scala-batch :: scenario/<id>::chain_step_supported`. With the batch's records
  gone, the step it evidences has no support, the reconstructed chain for that scenario no longer
  matches the committed expectation, and the named assertion fails. The audit applies the mutation
  in a scratch worktree, runs exactly that job, and requires that named assertion to be the failure.
- If the gate stays green, the component is `PADDING`, the audit exits non-zero, and
  `estate/scala-batch/` is deleted with a ledger entry naming the date, the mutation and the commit.

## Not yet decided

1. The directory path is not settled. Part II 73.1 gives Scala the nightly batch reconciliation role
   and supersedes Part I 31.14, which placed Scala at `scala/stream-baseline/` as a streaming
   reconstruction baseline, but Part II does not restate a directory. `estate/scala-batch/` is
   proposed here, not decided. The role change is the larger point: Scala moves from a pipeline
   baseline to an observed subject, and the baseline's agreement gate does not follow it.
2. Whether anything of the superseded streaming-baseline role survives. It is not assumed here to.
3. The format id, and this one is a genuine inconsistency rather than an omission. Part II 73.3.4
   lists `log4j-pattern` among the format keys adapters may use, while the closed supported-format
   table in 59.6 does not contain such an entry. Either the closed set gains one deliberately or the
   job's layout is configured into a format the table already defines. It may not be sniffed and it
   may not be assumed.
4. Whether a pattern layout, whose field boundaries are a formatting string rather than a grammar,
   can be admitted at all under the requirement that adapters use no backtracking regular
   expressions. If it cannot, the layout changes, not the adapter.
5. The scenario id, the mutation fraction `p` and the seed. `reorder_output(seed)` was considered as
   the operator and is recorded here as probably inert, since ingest imposes a canonical ordering;
   that expectation is itself untested and could change the choice.
6. Whether Tier C changed-path per-PR runs are registered as T1 rows in `ci/gates.toml` or only as
   the T2 nightly row (73.9 and 74.4 need reconciling).
7. Whether Scala is the held-out language under 73.1, recorded in
   `docs/research/preregistration.md` before the component is written.
