# Dart - desktop analyst client in the observed estate, issuing API calls
Tier: C
Status: not started
Owning spec section: 73
Milestone: M9

## The promise

The Tier C promise is stated in Part II section 73.1 and is the whole promise for this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component is evidence for that property and for nothing else. It is a subject, not a tool. It
will not import a SPECTRA library, will not open a certificate, will not call a checker, and will
not know it is observed. Its obligation is to behave like an analyst's desktop client - issuing a
scripted sequence of API calls against the estate's services - and to write its own client-side JSON
telemetry, which is then ingested by a format adapter that contains no branch naming Dart (section
73.3.4).

It promises no verification, no portability result and no user interface claim. Its value is that
the reconstruction path is indifferent to what wrote the records, and that it contributes the one
view of a request that is recorded from the client's side rather than the server's.

Nothing in this directory exists yet. Every statement above is a design obligation, not a
description of code.

## What lives here

When this directory is written, it is planned to contain:

- A Dart package - `pubspec.yaml` with the SDK version pinned to the toolchain lock file, and a
  vendored package cache so the build runs with the network off.
- A headless client that issues a scripted sequence of API calls against the estate's services:
  authenticate, list, open, export, sign out.
- A seeded driver so a run is reproducible from a seed alone, with no wall-clock and no random
  identifiers in anything that reaches the output.
- A client-side telemetry writer emitting one JSON object per line: the operation attempted, the
  identifiers the client used, and the client's own view of the outcome.
- Golden output bytes per seed, committed with LF endings.
- The component's entry in the root `polyglot.toml` with every field required by section 73.4.
- Conformance corpus entries for the declared `format_id`.

No code, no fixtures and no manifest entry exist at this time.

## Consumer edge

This directory has a real consumer edge and it must be declared before the first source file is
committed, per section 73.11.

If this directory is deleted, the committed scenario that includes the client source loses that
source. What breaks:

1. Every API call in that scenario becomes single-sourced, observed only from the gateway side. The
   scenario's cross-source corroboration assertion fails, and the records that had two independent
   observers have one.
2. The scenario's bundle no longer contains the client's records, so its bundle manifest hash gate
   fails against the committed expectation.
3. The estate loses the only subject that observes a request from the initiating side, which is the
   case that makes the difference between an unobserved step and a differently observed step
   testable at all.

The consumer is owned by the scenario and ingest components, not by this one. A test suite inside
this directory is not a consumer and would fail the audit with `SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-c / estate-dart-client`, declared in `.github/workflows/`, executing the client
  against the range rather than merely analyzing or building it (section 73.3.2).
- Tier: T2. Tier C language jobs and the polyglot mutation audit run nightly on `main`. A red Tier C
  job does not block a Tier A milestone; it appears in the README status table within one commit and
  blocks any tagged release (section 73.9, rules 1 and 2).
- Make target: `make polyglot-audit`, which is the only thing that licenses this component to remain
  in the tree. `make m9-verify` is the milestone proof target that must include it.

## Mutation check

Declared operator from the closed set in section 73.5: `drop_records(p, seed)`.

What is corrupted: in a scratch worktree, a seeded fraction of the client's emitted JSON lines is
deleted after emission and before ingest. The client's source is untouched; only its output is
corrupted.

Which gate goes red: the scenario gate that asserts cross-source corroboration for that scenario -
that each API call the gateway recorded also carries the client's own record of the same operation.
With a seeded fraction of client lines missing, calls that were observed twice are observed once,
the corroboration count for that scenario falls below its committed expectation, and the assertion
fails.

Two operators are explicitly rejected here, and the reasons are the point of the mutation rule:

- `reorder_output(seed)` would be absorbed. The total order of the bundle is defined in section 59
  to be independent of input file order, so permuting this component's output lines changes nothing
  downstream. Declaring it would leave every gate green and would wrongly mark this component
  padding.
- `stub_entrypoint` would also be absorbed. A source that emits nothing is a blind source, and
  blindness is a legal state the license machinery is built to represent rather than to reject.

`drop_records` degrades a source that is otherwise live, which is the condition the corroboration
assertion is sensitive to.

## Not yet decided

1. **The directory path.** `estate/dart-client/` is proposed, not settled. Part II section 73.1
   replaced Part I section 31.23's role - a read-only Flutter console at `mobile/analyst-console/`
   that opened a certificate file and called a checker - with an estate subject issuing API calls,
   and did not restate a path. The repository plan records the Tier B/C/D directory layout as an
   open decision.
2. **Whether the certificate-reading console survives anywhere.** Part I's console read SPECTRA
   certificates. Part II's estate rule forbids a Tier C subject from knowing SPECTRA exists. The two
   roles cannot be the same component. Either the console is dropped, or it becomes a separate
   component in a different tier with its own promise, consumer edge and mutation. Neither has been
   decided, and this file assumes only the estate-subject role.
3. **Flutter or plain Dart.** A graphical client cannot be exercised headlessly and offline in a
   nightly job without a display stack, and section 74.1 lists Dart in the range-emitter image
   without stating whether Flutter is present. A headless Dart client is assumed here and has not
   been decided.
4. **The declared format.** Section 73.1 describes the emission as client-side JSONL telemetry, and
   `jsonl.v1` is the obvious row in section 59.6's closed set, but the field set, the duplicate-key
   rule and the depth cap for these records have not been written, and a declared format is required
   at manifest validation rather than inferred.
5. **The SourceId and the range topology.** The service table in Part I section 26.3 has no row for
   a desktop client and `range/sources.toml` has no SourceId for it. Where the client runs on the
   range network, and whether it is a compose service or a driver invoked by the scenario runner,
   has not been settled. Liveness is computed per SourceId, so this blocks any liveness statement
   about this source.
6. **The gate id.** The downstream gate named in `mutation.expect_red` must be a registered id in
   `ci/gates.toml` with an owning section and a make target. No such gate is registered yet, so the
   mutation above names an assertion, not a committed identifier.
