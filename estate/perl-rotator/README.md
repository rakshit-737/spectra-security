# Perl - cron and rotation utility in the observed estate, emitting plain syslog lines with no field structure
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3; padding example in 73.6)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise, from Part II 73.1:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component is the hardest case for that promise and is meant to be. It is a scheduled
maintenance and rotation utility that emits plain syslog lines with no field structure at all - the
deliberately worst-structured source in the estate. Part II 59.6 marks legacy BSD syslog as the
deliberately hostile format: no year and no time zone in the timestamp. If reconstruction holds
across this source, it holds across a source that gives the pipeline nothing to lean on.

What is not promised: no text-processing claim, no translation capability, no statement that this
utility is good at anything. It is a subject of reconstruction, not a tool of the pipeline, and
under Part I 30.7.3 it may not import the rule table, the control catalog, the axioms or the
certificate schema.

One warning is recorded here on purpose: Part II 73.6's worked failure transcript uses
`estate-perl-rotator` as its example of a component whose mutation left every gate green and which
was therefore deleted. That is a caution written into the specification about this exact directory.
The consumer edge below is not decoration; it is the condition under which this directory is allowed
to exist at all.

Nothing here is implemented. No rotation has run and no line has been emitted or ingested.

## What lives here

Planned contents, none of which exist yet:

- The utility itself: scheduled rotation and cleanup of files belonging to other estate services,
  with the schedule committed rather than inherited from a host.
- Its logging path, writing plain syslog lines to the collected destination. The line shape is the
  emission contract and is reviewed as one.
- A dependency declaration pinned to what can be vendored offline, with the vendor path recorded in
  `polyglot.toml`.
- A seeded driver that runs the utility over a committed fixture tree so that what is emitted is
  reproducible.
- A committed golden of one seeded run.
- A `Makefile` exposing the declared entrypoint and a manifest fragment declaring the emitted
  `format_id` (format is declared in the manifest, never sniffed - 59.6).

No SPECTRA code, and specifically no log translation or normalization code: normalization belongs to
the ingest adapters, and a Perl component that pre-digested its own telemetry for the pipeline would
destroy the very property Tier C exists to test.

## Consumer edge

Required edge (73.3.1): a downstream artifact owned by a different component must consume this
output. The intended consumer is the liveness and blind-window expectation owned by the kernel side.
The rotation utility's lines are what bracket the periods in which other sources are rotated and
therefore quiet: they are the evidence that a quiet window is an expected quiet window rather than
an unexplained one. The downstream artifact is the committed expectation over the scenario's blind
windows and the resulting verdict.

Plainly, for session one: nothing exists, so deleting this directory today breaks nothing. Given
73.6's example, this component carries the heaviest burden of proof in the tier: if no downstream
expectation can be made to depend on its output, it is padding by the specification's own worked
case and must be deleted rather than documented.

## How it is exercised

- CI job: `polyglot-c / estate-perl-rotator`, named in the component's `ci.job` field.
- Tier: T2 (74.4 assigns Tier C/D language jobs and the mutation audit to the nightly tier), with a
  changed-path per-PR run permitted by 73.9. The job must run the utility and collect its emitted
  lines; a `perlcritic` and unit-test job alone does not satisfy 73.3.2.
- Make target: the declared entrypoint `make -C estate/perl-rotator emit`, with `make polyglot-audit`
  running the load-bearing checks.

A red job here does not block a milestone, appears in the README status table within one commit, and
blocks any tagged release. Under 73.9 rule 2 it may not be silenced: it is fixed, or the component
is deleted.

## Mutation check

- Operator: `drop_records(p, seed)` (73.5, the telemetry-emitter operator), applied to output only.
- Corruption, concretely: after a seeded run, a seeded fraction of the emitted syslog lines is
  deleted from the collected stream before ingest - specifically including the lines that announce a
  rotation of another source. The stream stays well-formed and the run exits zero.
- Gate that must go RED: the assertion named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-perl-rotator :: scenario/<id>::verdict_matches_expected`. With the rotation
  announcements gone, the quiet window in the rotated source is no longer bracketed by anything, the
  window's treatment changes, and the scenario's committed verdict expectation no longer holds. The
  audit applies the mutation in a scratch worktree, runs exactly that job, and requires that named
  assertion to fail.
- If the gate stays green - the case 73.6 writes out in full for this component - the audit prints
  `PADDING: estate-perl-rotator` and exits non-zero, and the action is to delete `estate/perl-rotator/`
  and its manifest entry, or to give it a real consumer and re-run.

## Not yet decided

1. The directory path is not settled. Part II 73.1 gives Perl the cron and rotation role and
   supersedes Part I 31.19, which placed Perl at `tools/perl/logxlate/` as a legacy log translator,
   but Part II does not restate a directory. `estate/perl-rotator/` is proposed here, not decided.
   The role change also moves Perl from a pipeline tool to an estate subject, which is the more
   consequential part of the supersession.
2. Whether the superseded log-translation work is dropped entirely, given that Part II places
   parsing in the Rust adapters. Nothing here assumes it survives.
3. The format id. Plain, structureless syslog lines point at the legacy BSD syslog entry in the
   closed table (59.6), whose grammar has no year and no time zone. Whether the emitted lines fall
   inside the accepted subset committed under the grammar directory, and what happens to the ones
   that do not, is open.
4. How the missing year and zone interact with this component's own role as the bracket for other
   sources' quiet windows. There is a real tension between being the least informative source and
   being the source that explains other sources' silence, and it is unresolved.
5. The scenario id, the mutation fraction `p` and the seed.
6. Whether Tier C changed-path per-PR runs are registered as T1 rows in `ci/gates.toml` or only as
   the T2 nightly row (73.9 and 74.4 need reconciling).
7. Whether Perl is the held-out language under 73.1, recorded in
   `docs/research/preregistration.md` before the component is written.
