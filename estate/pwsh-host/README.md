# PowerShell - admin host automation in the observed estate, running as pwsh on Linux
Tier: C
Status: not started
Owning spec section: 73
Milestone: M9

## The promise

The Tier C promise is stated in Part II section 73.1 and is the whole promise for this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component is evidence for that property and for nothing else. It is a subject, not a tool. It
will not import a SPECTRA library, will not wrap a collector, will not forward another component's
output into the ingest pipeline, and will not know it is observed. Its obligation is to run admin
automation on a host in the estate and to emit Windows-event-shaped JSON records, which are then
ingested by a format adapter that contains no branch naming PowerShell (section 73.3.4).

It promises no developer bootstrap, no environment parity check and no second entry point for any
make target. Its value is that the reconstruction path is indifferent to what wrote the records.

Honesty clause, mandatory under section 73.1 and repeated wherever this component is described: this
runs as `pwsh` on Linux. It emits Windows-event-shaped records. It is not Windows, and no document
may imply that a Windows endpoint was observed.

Nothing in this directory exists yet. Every statement above is a design obligation, not a
description of code.

## What lives here

When this directory is written, it is planned to contain:

- PowerShell scripts carrying `#Requires -Version 7`, running under `pwsh` on Linux, with the
  version pinned to the toolchain lock file.
- An admin automation workload: scheduled maintenance runs, service restarts, local account and
  group changes, and the privilege elevations those operations perform.
- A seeded driver so a run is reproducible from a seed alone, with no wall-clock and no random
  identifiers reaching the output.
- A record writer producing Windows-event-shaped JSON objects: an event identifier, a channel, a
  provider name, a subject account and the operation's own fields.
- A `PSScriptAnalyzer` settings file and Pester specifications for the record writer's shape.
- Golden output bytes per seed, committed with LF endings.
- The component's entry in the root `polyglot.toml` with every field required by section 73.4.
- Conformance corpus entries for the declared `format_id`.

No code, no fixtures and no manifest entry exist at this time.

## Consumer edge

This directory has a real consumer edge and it must be declared before the first source file is
committed, per section 73.11.

If this directory is deleted, the committed scenario that includes the admin host loses that source.
What breaks:

1. The privilege and local-account transitions that the rule table grounds over lose their observed
   anchor in that scenario. Steps that were derived from observed records become candidates for
   licensed unobserved steps, which changes the reconstructed state and changes the cut, so the
   scenario's assertion that the reconstructed privilege timeline matches the generator's recorded
   ground truth fails.
2. The estate loses its only subject whose record shape is event-identifier-keyed rather than
   message-text-keyed, which is the case that makes format-keyed adaptation testable against a shape
   unlike the others.

The consumer is owned by the scenario and ingest components, not by this one. A test suite inside
this directory is not a consumer and would fail the audit with `SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-c / estate-powershell-host`, declared in `.github/workflows/`, executing the
  automation rather than merely linting it (section 73.3.2). `PSScriptAnalyzer` alone is not
  exercise.
- Tier: T2. Tier C language jobs and the polyglot mutation audit run nightly on `main`. A red Tier C
  job does not block a Tier A milestone; it appears in the README status table within one commit and
  blocks any tagged release (section 73.9, rules 1 and 2).
- Make target: `make polyglot-audit`, which is the only thing that licenses this component to remain
  in the tree. `make m9-verify` is the milestone proof target that must include it.

The job runs on Linux, in a digest-pinned toolchain image, offline. There is no Windows runner.

## Mutation check

Declared operator from the closed set in section 73.5: `stub_entrypoint`.

What is corrupted: in a scratch worktree, this component's entrypoint is replaced with a successful
no-op that emits nothing. The scenario runs, the host produces no records, and the run exits zero.

Which gate goes red: the scenario gate that compares the bundle manifest hash for that scenario
against its committed expectation. The bundle is missing an entire source, so the hash differs and
the assertion fails.

The illustrative audit transcript in section 73.6 shows this component's row as
`estate-powershell-host  C  PowerShell  ok  ok  RED @ scenario/S3::bundle_hash  demo` (illustrative,
not a target - the real job name, scenario id and assertion are whatever is registered and whatever
the run prints).

The choice of the named gate is the load-bearing part and must not be relaxed to a reconstruction
gate. A source that emits nothing is, to the liveness pass, a blind source, and blindness is a legal
state the license machinery exists to represent. A reconstruction-quality assertion may therefore
stay green under `stub_entrypoint` while the source has silently vanished. The gate that must go red
is one that is sensitive to the source's presence rather than to its content: the bundle hash, or an
explicit source-inventory assertion for the scenario. If both turn out to tolerate an absent source,
this component's declared mutation is wrong and must be changed to `drop_records(p, seed)` against a
content-sensitive gate rather than left as it is.

## Not yet decided

1. **The directory path.** `estate/pwsh-host/` is proposed, not settled. Part II section 73.1
   replaced Part I section 31.34's role - a Windows-side developer bootstrap and collector wrapper
   at `scripts/win/` - with an observed admin host, and did not restate a path. The Part I path is
   invalidated twice over: it implies Windows, and it places a subject inside the tools tree. The
   repository plan records the Tier B/C/D directory layout as an open decision.
2. **Whether any developer-facing PowerShell survives at all.** The conflict ledger records that no
   make target runs on Windows, which removes Part I's contributor entry point. If some PowerShell
   is nonetheless kept for another purpose, it must be a separate component with its own paths,
   consumer edge and mutation, because section 73.4 fails a doubly-matched file with
   `AMBIGUOUS_OWNERSHIP` and would fail a tool and a subject sharing one entry.
3. **The declared format.** Section 73.1 describes the emission as Windows-event-shaped JSON
   records. `jsonl.v1` is the candidate row in section 59.6's closed set, but the field set, the
   event-identifier vocabulary and the duplicate-key rule for these records have not been written,
   and a declared format is required at manifest validation rather than inferred.
4. **The SourceId.** The service table in Part I section 26.3 has no row for an admin host and
   `range/sources.toml` has no SourceId for it. Liveness is computed per SourceId, so this blocks
   any liveness statement about this source, and it blocks the mutation's gate choice above.
5. **Whether PowerShell is the held-out language.** Section 73.1 requires exactly one Tier C
   component to be authored after the rule table and axioms are frozen and hash-pinned, with its
   reconstruction quality reported as a separate `HELD-OUT-LANGUAGE` row. Which component that is
   must be recorded in the preregistration document before it is written, and it has not been
   recorded.
6. **The gate id.** The downstream gate named in `mutation.expect_red` must be a registered id in
   `ci/gates.toml` with an owning section and a make target. No such gate is registered yet, so the
   mutation above names an assertion, not a committed identifier.
