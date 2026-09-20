# Objective-C - legacy host agent in the observed estate, clang against GNUstep on Linux
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
certificate schema, and will not know it is observed. Its obligation is to emit NSLog-shaped lines,
including the mixed encodings that such an agent produces in practice, and to be ingested by a
format adapter that contains no branch naming Objective-C (section 73.3.4).

It promises no oracle, no measured performance result and no coverage of any credential API. Its
value is that the reconstruction path is indifferent to what wrote the records, and that its output
is untidy enough to exercise the ingest hardening path honestly rather than decoratively.

Honesty clause, mandatory under section 73.1 and repeated wherever this component is described: this
is compiled with clang against GNUstep on Linux. It is not an Apple platform agent. No document may
imply that macOS or iOS telemetry was observed.

Nothing in this directory exists yet. Every statement above is a design obligation, not a
description of code.

## What lives here

When this directory is written, it is planned to contain:

- Objective-C sources for a small resident agent, compiled with `clang -fobjc-arc` against the
  GNUstep base library and its Objective-C runtime.
- A build file - a plain `Makefile` or a `CMakeLists.txt` - with the compiler and GNUstep versions
  pinned to the entries in the toolchain lock file.
- The agent's own log writer producing NSLog-shaped lines: timestamp, host, process name with a pid
  in brackets, then an unstructured message.
- A seeded workload driver so a run is reproducible from a seed alone.
- Golden output committed as bytes, not as text, because some lines are deliberately not valid
  UTF-8. The `.gitattributes` treatment for those bytes is an open question below.
- The component's entry in the root `polyglot.toml` with every field required by section 73.4.
- Conformance corpus entries for the declared `format_id`, including the malformed-encoding cases,
  each with its expected quarantine reason code.

No code, no fixtures and no manifest entry exist at this time.

## Consumer edge

This directory has a real consumer edge and it must be declared before the first source file is
committed, per section 73.11.

If this directory is deleted, the committed scenario that includes the agent source loses that
source. What breaks:

1. The scenario's entity resolution loses the host-side records that link a process observation to
   the account and host identifiers other sources carry. The scenario's entity-resolution assertion
   against generator ground truth fails.
2. The scenario's bundle no longer contains the agent's records, so its bundle manifest hash gate
   fails against the committed expectation.
3. The ingest hardening corpus loses the only committed source of genuinely mixed encodings that is
   produced by a subject rather than synthesized by a fixture. Byte conservation and the quarantine
   path lose a real input.

The consumer is owned by the scenario and ingest components, not by this one. A test suite inside
this directory is not a consumer and would fail the audit with `SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-c / estate-objc-agent`, declared in `.github/workflows/`, executing the agent
  rather than merely compiling it (section 73.3.2). A compile-only job is not exercise.
- Tier: T2. Tier C language jobs and the polyglot mutation audit run nightly on `main`. A red Tier C
  job does not block a Tier A milestone; it appears in the README status table within one commit and
  blocks any tagged release (section 73.9, rules 1 and 2).
- Make target: `make polyglot-audit`, which is the only thing that licenses this component to remain
  in the tree. `make m9-verify` is the milestone proof target that must include it.

## Mutation check

Declared operator from the closed set in section 73.5: `drop_records(p, seed)`.

What is corrupted: in a scratch worktree, a seeded fraction of the lines the agent emits is deleted
after emission and before ingest. The agent's source is untouched; only its output is corrupted.

Which gate goes red: the scenario gate that asserts entity-resolution recall for that scenario
against the generator's recorded ground truth. With a seeded fraction of the agent's lines missing,
the host-side identifiers that join a process observation to an account cluster are absent for some
entities, those entities fail to merge, and recall falls below the declared floor.

The illustrative audit transcript in section 73.6 shows this component's row as
`estate-objc-agent  C  Objective-C  ok  ok  RED @ scenario/S3::er_recall  demo` (illustrative, not a
target - the real job name, scenario id and assertion are whatever is registered and whatever the
run prints).

The operator choice matters. `stub_entrypoint` would silence the source entirely, and a silent
source is a blind source, which the license machinery is built to absorb as a legal state; the
mutation would be tolerated and the component would be wrongly marked padding. `drop_records`
degrades a source that is otherwise live, which is what the entity-resolution assertion is sensitive
to.

## Not yet decided

1. **The directory path.** `estate/objc-agent/` is proposed, not settled. Part II section 73.1
   replaced Part I section 31.22's role - a keychain-shaped credential-lifecycle shim at
   `mobile/ios-keychain-shim/`, linked into the Swift package through its C interface - with a
   standalone legacy agent, and did not restate a path. The Part I path is invalidated by the
   honesty clause regardless. The repository plan records the Tier B/C/D directory layout as an open
   decision.
2. **Standalone process or linked library.** Part I linked this into the Swift component through a
   SwiftPM system-library target. Part II lists the Swift service and this agent as two separate
   estate components with separate promises, and section 73.4 requires every executing source file
   to be matched by exactly one component's `paths`, on pain of `AMBIGUOUS_OWNERSHIP`. A linked
   arrangement would have to declare which component owns which paths. Standalone is assumed here
   and has not been decided.
3. **The declared format.** Section 73.1 describes the emission as NSLog-shaped lines with mixed
   encodings. Section 59.6 defines a closed set of formats and forbids content sniffing.
   `syslog.rfc3164` is the nearest row and is described there as the deliberately hostile format,
   but NSLog's shape is not RFC 3164. Either a declared mapping is written, or the closed set gains
   a row with its own grammar, adapter and corpus. Neither has been chosen.
4. **How the mixed encodings survive the repository.** The `.gitattributes` rules set `* text=auto
   eol=lf`. Golden bytes that are deliberately not valid UTF-8 must not be normalized on the way in
   or out, so they need an explicit binary or unset attribute, and that attribute interacts with the
   Linguist rules in section 73.8. This has not been worked out.
5. **What the quarantine path does with those lines.** A malformed line is quarantined with a reason
   code and counted, never dropped, because a silent drop manufactures a blind window. Which of this
   agent's lines are expected to be accepted and which are expected to be quarantined, and with
   which codes, must be fixed in the corpus before the first assertion is written.
6. **The toolchain image.** The four-image set in Part II section 74.1 does not list clang with
   GNUstep in any image. Either that table gains it or this component has no image to run in.
7. **The SourceId.** The service table in Part I section 26.3 has no row for this agent and
   `range/sources.toml` has no SourceId for it. Liveness is computed per SourceId, so this must be
   settled before any liveness statement about this source can be made.
8. **The gate id.** The downstream gate named in `mutation.expect_red` must be a registered id in
   `ci/gates.toml`. No such gate is registered yet, so the mutation above names an assertion, not a
   committed identifier.
