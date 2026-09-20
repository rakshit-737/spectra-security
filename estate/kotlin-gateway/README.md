# Kotlin - API gateway in the observed estate, emitting logback JSON
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise is stated once, in Part II 73.1, and this directory holds one share of it:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

That is the whole promise. This component is to be one JVM service written in Kotlin whose
telemetry is emitted the way a Kotlin service would emit it - a logback JSON encoder configured in
the service's own configuration file - and nothing in `ingest/` is permitted to know that Kotlin
wrote it. The adapter that reads these records is keyed by format, never by producing language
(73.3.4).

What is not promised: nothing is promised about the gateway itself. It is not offered as a model of
any named gateway product, it carries no performance statement, and no security property is claimed
for it. It is a subject of reconstruction, not a tool of it. Part I 30.7.3 applies without
exception: this code may not import the rule table, the control catalog, the axiom set or the
certificate schema, and must remain ignorant of SPECTRA.

Nothing here is implemented. No telemetry has been emitted, no record has been ingested, and no
reconstruction has been performed across this component.

## What lives here

Planned contents, none of which exist yet:

- A Gradle build targeting the Kotlin JVM toolchain only, with dependencies resolved from the
  committed offline vendor path named in `polyglot.toml` as `offline_source`. No network fetch at
  build time.
- The gateway source set: request admission, an upstream routing shim, a token-presentation path
  and a small set of administrative endpoints - only as much surface as the committed scenario
  script actually drives.
- `logback.xml` (or the equivalent configuration file) selecting the JSON encoder and fixing the
  field set. This file is the emission contract and is reviewed as such.
- A seeded scenario driver that replays a committed request script so the run is reproducible with
  no wall-clock and no RNG in the emitted content.
- A committed golden of one seeded run's emitted records, with the fields the pipeline is not
  allowed to depend on excluded from comparison.
- A `Makefile` exposing the entrypoint declared in `polyglot.toml`.
- A manifest fragment declaring the emitted `format_id` for ingest, since format is declared and
  never sniffed (Part II 59.6).

No SPECTRA rules, no axioms, no certificate code, no ingest code.

## Consumer edge

Required edge (73.3.1): the records this component emits must be read by a downstream artifact owned
by a different component. The intended consumer is the scenario expectation golden owned by the
scenario-fixture and kernel side - the reconstructed state timeline for the scenario in which this
gateway carries a step of the chain. If the gateway's records vanish, the edges they evidence are
unsupported, the reconstructed timeline diverges from the recorded ground truth, and that
expectation fails.

Stated plainly for session one: nothing exists, so deleting this directory today breaks nothing.
That is precisely why the edge is a precondition on the first commit that creates it. A component
whose only consumer is its own test suite fails the audit with `SELF_CONSUMING`, and under 73.6 the
remedy is deletion rather than documentation. If no scenario can be written in which this gateway's
output changes a downstream expectation, this directory must not be created at all.

## How it is exercised

- CI job: `polyglot-c / estate-kotlin-gateway`, declared in `.github/workflows/*.yml` and named in
  the component's `ci.job` field in `polyglot.toml`.
- Tier: T2 (Part II 74.4 assigns Tier C/D language jobs and the polyglot mutation audit to the
  nightly tier). Part II 73.9 additionally permits a changed-path run of this job per PR. The job
  must execute the component, not merely compile it (73.3.2).
- Make target: the declared entrypoint, `make -C estate/kotlin-gateway emit`, with the audit itself
  invoked by `make polyglot-audit` (full mode nightly and at the release gate, fast mode over
  changed components per PR).

A red job here does not block a milestone; it appears in the README status table within one commit
and blocks any tagged release (73.9, rule 1).

## Mutation check

- Operator: `drop_records(p, seed)` from the closed set in 73.5 - the operator designated for
  telemetry emitters. It is applied to this component's *output*, never to its source.
- Corruption, concretely: after a seeded run, a seeded fraction of the emitted JSON lines is deleted
  from the output file before ingest. The file remains well-formed and the run still exits zero, so
  nothing upstream notices; the gateway's evidence for part of the chain is simply absent.
- Gate that must go RED: the scenario expectation job named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-kotlin-gateway :: scenario/<id>::state_timeline_matches_truth`. The audit
  applies the mutation in a scratch worktree, runs exactly that job, and requires both a red result
  and that the failing assertion is the one declared.
- If the gate stays green under the mutation, this component is `PADDING` and `make polyglot-audit`
  exits non-zero. The prescribed action is to delete `estate/kotlin-gateway/` and its manifest entry,
  or to give it a genuine consumer and re-run. Writing a defence of the directory is not an option;
  the deletion ledger records the date, the mutation and the removing commit, and contains no
  argument.

## Not yet decided

1. The directory path is not settled. Part II 73.1 supersedes Part I 31.11, which placed Kotlin at
   `mobile/android-session-fixture/` as an Android session-telemetry fixture, and replaces that role
   with an API gateway - but it does not restate a directory. `estate/kotlin-gateway/` is a proposal
   in this document, not a decision, and the final path is whatever `polyglot.toml` and the tree
   agree on when the component is created.
2. Whether anything of the superseded Android session-fixture role survives elsewhere, or is dropped
   entirely, is open. It is not assumed here to survive.
3. The emitted format id. Logback's JSON encoder produces one object per line, which points at
   `jsonl.v1` in the closed format table (59.6), but the exact field set, the timestamp shape and the
   duplicate-key and depth constraints have to be checked against that adapter before the claim is
   made. The format set is closed; if the encoder's output does not fit, either the encoder
   configuration changes or a format id is added deliberately.
4. The scenario id, the mutation fraction `p` and the seed are unassigned.
5. Whether Tier C changed-path per-PR runs are registered as their own T1 rows in `ci/gates.toml` or
   exist only as the T2 nightly row. Part II 73.9 and 74.4 can be read either way and this has to be
   reconciled in the gate registry.
6. Whether this is the held-out language under 73.1 - exactly one Tier C component is authored after
   `rules.toml` and `axioms/` are frozen and hash-pinned, and which one it is must be written into
   `docs/research/preregistration.md` before that component is written.
7. How Gradle and the JVM toolchain are vendored so a clean clone builds with the network off, and
   which toolchain image row owns them.
