# Swift - Linux-hosted session service in the observed estate
Tier: C
Status: not started
Owning spec section: 73
Milestone: M9

## The promise

The Tier C promise is stated in Part II section 73.1 and is the whole promise for this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component is evidence for that property and for nothing else. It is a subject, not a tool. It
will not import a SPECTRA library, will not read the rule table, the control catalog or the
certificate schema, and will not know it is observed. Its only obligation is to emit its own
idiomatic telemetry - swift-log structured output - and to be ingested by a format adapter that
contains no branch naming Swift (section 73.3.4).

It promises no performance result, no oracle and no independent check. Its value is that the
reconstruction path is indifferent to what wrote the records.

Honesty clause, mandatory under section 73.1 and repeated wherever this component is described:
this is the open-source Swift toolchain running on Linux. It is not an Apple platform agent. No
document may imply that macOS or iOS telemetry was observed.

Nothing in this directory exists yet. Every statement above is a design obligation, not a
description of code.

## What lives here

When this directory is written, it is planned to contain:

- A Swift Package Manager package - `Package.swift` with a pinned toolchain version, Foundation
  only, no platform-specific frameworks - building a long-running session service.
- The service itself: session establishment, resumption, refresh and expiry over an HTTP surface
  reachable from the range network only.
- A swift-log handler configured to write structured records to a file sink, with the field set
  fixed by a committed schema note rather than by whatever the logging library defaults to.
- A seeded, scripted workload driver that replays a fixed sequence of session operations so that a
  run is reproducible from a seed alone.
- Golden output bytes per seed, committed with LF endings, used by the component's own test leg.
- The component's entry in the root `polyglot.toml`, carrying `id`, `language`, `tier`, `paths`,
  `toolchain`, `offline_source`, `entrypoint`, `promise`, and the `consumer`, `ci`, `mutation` and
  `role` tables required by section 73.4.
- Conformance corpus entries under the ingest corpus tree for whichever declared `format_id` this
  output is ingested as.

No code, no fixtures and no manifest entry exist at this time.

## Consumer edge

This directory has a real consumer edge and it must be declared before the first source file is
committed, per section 73.11.

If this directory is deleted, the committed scenario that includes the session source loses that
source. Three things break, in order:

1. The scenario's bundle no longer contains the session records, so the bundle manifest hash gate
   for that scenario fails against its committed expectation.
2. The session-lifecycle obligations that the rule table grounds over lose their observed anchor in
   that scenario. Steps that were derived from observed records become candidates for licensed
   unobserved steps instead, which changes the reconstructed state and changes the cut.
3. The estate loses one of the members that makes the no-language-branch property in `ingest/`
   testable at all. That property is the Tier C promise; a promise with fewer witnesses is a weaker
   promise.

The consumer must be an artifact owned by a different component (section 73.3.1). The scenario gate
and the ingest corpus are owned by the scenario and ingest components respectively, not by this one.
A test suite living inside this directory is not a consumer and would fail the audit with
`SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-c / estate-swift-session`, declared in `.github/workflows/`, executing the
  component's entrypoint rather than merely building it (section 73.3.2).
- Tier: T2. Tier C language jobs and the polyglot mutation audit run nightly on `main`. A red Tier C
  job does not block a Tier A milestone; it appears in the README status table within one commit and
  blocks any tagged release (section 73.9, rules 1 and 2).
- Make target: `make polyglot-audit` is the target that licenses this component to remain in the
  tree. `make m9-verify` is the milestone proof target that must include it.

The job runs offline, from a digest-pinned toolchain image, and installs no toolchain of its own.

## Mutation check

Declared operator from the closed set in section 73.5: `drop_records(p, seed)`.

What is corrupted: in a scratch worktree, a seeded fraction of the session records this service
emits is deleted after emission and before ingest. The service's source is untouched; only its
output is corrupted, which is what section 73.5 requires.

Which gate goes red: the scenario gate that asserts the reconstructed session lifecycle for that
scenario matches the generator's recorded ground truth. With a seeded fraction of session records
missing, established sessions lose their issuing record and the reconstruction either drops those
transitions or admits them as unobserved steps, and the assertion comparing the reconstruction to
ground truth fails.

The operator choice matters and is not interchangeable. `stub_entrypoint` is the wrong operator
here: a source that emits nothing is, to the liveness pass, a source that is blind, and blindness is
a legal state that the license machinery is designed to absorb. An operator whose effect the system
is built to tolerate would leave every gate green and would wrongly mark this component padding.
`drop_records` corrupts the content of a source that is otherwise live, which is the condition the
reconstruction gate is sensitive to.

The audit applies the mutation, runs exactly the job named in `mutation.expect_red`, and requires
both that the job is RED and that the failing assertion is the one named. The mutated run must touch
no network socket.

## Not yet decided

1. **The directory path.** `estate/swift-session/` is proposed, not settled. Part II section 73.1
   replaced Part I section 31.21's role - an iOS session-telemetry fixture generator at
   `mobile/ios-session-fixture/` - with a Linux-hosted session service, and did not restate a path.
   The Part I path is invalidated by the honesty clause regardless, since it names a platform this
   component is not. The repository plan records the Tier B/C/D directory layout as an open decision.
2. **The declared format.** Section 73.1 describes the emission as "swift-log structured output".
   Section 59.6 defines a closed set of supported raw formats and content sniffing is forbidden, so
   the output must be declared as one of the existing rows - `kv.logfmt` or `jsonl.v1` are the
   candidates - or the closed set must gain a row with its own adapter, grammar and conformance
   corpus. Neither has been chosen.
3. **Whether this is a range compose service or an offline emitter.** The service table in Part I
   section 26.3 has no row for a Swift service and `range/sources.toml` has no SourceId for it. Part
   II did not add one. Until that table is amended, this component has no declared SourceId, and
   liveness is computed per SourceId.
4. **The toolchain image.** The four-image set in Part II section 74.1 puts the range-emitter
   runtimes in `spectra/toolchain-c` and does not list Swift in any image. Either that table gains
   Swift or this component has no image to run in.
5. **Whether Swift is the held-out language.** Section 73.1 requires exactly one Tier C component to
   be authored after the rule table and axioms are frozen and hash-pinned, with its reconstruction
   quality reported as a separate `HELD-OUT-LANGUAGE` row. Which component that is must be recorded
   in the preregistration document before it is written, and it has not been recorded.
6. **The CI cadence.** Section 73.9 assigns Tier C "changed-path jobs only" per PR with the full run
   and mutation nightly; section 74's gate-tier table places Tier C language jobs and the polyglot
   mutation audit at T2 outright. This file states T2. If a changed-path per-PR leg is also wanted,
   it needs its own gate row in `ci/gates.toml`.
7. **The gate id.** The downstream gate named in `mutation.expect_red` must be a registered id in
   `ci/gates.toml` with an owning section and a make target. No such gate is registered yet, so the
   mutation above names an assertion, not a committed identifier.
