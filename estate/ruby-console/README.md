# Ruby - internal admin console in the observed estate, emitting a Rails-style tagged logger stream
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise, from Part II 73.1, stated once and shared by this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

Here that means an internal administrative console written in Ruby, logging the way such a console
logs: a Rails-style tagged logger, where the structure a reader perceives is a bracketed prefix
convention rather than a schema. The pipeline must reconstruct across it with no Ruby-specific
branch, identifier or filename anywhere in `ingest/` (73.3.4).

What is not promised: nothing about the console's design, its access-control model or its fitness
for any purpose. It is a subject of reconstruction. Part I 30.7.3 forbids it from importing the rule
table, the control catalog, the axioms or the certificate schema; it knows nothing about SPECTRA.

Nothing here is implemented. No console has run and no tagged line has been emitted or ingested.

## What lives here

Planned contents, none of which exist yet:

- The console application: an operator login path, a small number of administrative actions against
  other estate services, and a job or task surface - only as much as the committed scenario script
  drives.
- The logger configuration that fixes the tag set and the line layout. This file is the emission
  contract and is reviewed as one.
- A committed dependency lockfile pinned for offline install, with the vendor path recorded in
  `polyglot.toml`.
- A seeded driver that replays a committed action sequence, so emitted content does not depend on a
  wall clock or an RNG.
- A committed golden of one seeded run.
- A `Makefile` exposing the declared entrypoint and a manifest fragment declaring the emitted
  `format_id`, since format is declared and never sniffed (59.6).

No SPECTRA rules, axioms, certificate code or ingest code.

## Consumer edge

Required edge (73.3.1): a downstream artifact owned by a different component must consume this
output. The intended consumer is the scenario's expected-cut golden owned by the kernel and
scenario-fixture side - the administrative action this console performs is the step a named control
in the catalog is expected to sever, so the console's records are the evidence that the step
occurred. Take the records away and the step is unsupported, the cut the kernel computes changes,
and the expectation fails.

For session one, plainly: nothing exists, so deleting this directory today breaks nothing. That is
exactly why the edge must be designed before the first line of Ruby is written. A component whose
only consumer is its own RSpec suite fails with `SELF_CONSUMING` and is deleted under 73.6 rather
than argued for.

## How it is exercised

- CI job: `polyglot-c / estate-ruby-console`, named in the component's `ci.job` field.
- Tier: T2 (74.4 assigns Tier C/D language jobs and the polyglot mutation audit to the nightly
  tier); 73.9 additionally permits a changed-path run per PR. The job must execute the console and
  collect its output - a `rubocop` and unit-test job alone does not satisfy 73.3.2.
- Make target: the declared entrypoint `make -C estate/ruby-console emit`, with the load-bearing
  checks run by `make polyglot-audit`.

A red job here does not block a milestone, appears in the README status table within one commit, and
blocks any tagged release.

## Mutation check

- Operator: `drop_records(p, seed)` (73.5, the designated telemetry-emitter operator), applied to
  output only.
- Corruption, concretely: after a seeded run, a seeded fraction of the emitted tagged lines is
  deleted from the collected stream before ingest, including lines carrying the administrative
  action that the scenario's control is expected to sever. The file stays well-formed and the run
  exits zero.
- Gate that must go RED: the assertion named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-ruby-console :: scenario/<id>::expected_cut_matches_golden`. With the
  console's evidence removed, the reconstructed chain no longer contains the step that control cuts,
  the computed cut no longer matches the committed golden, and the named assertion fails. The audit
  runs exactly that job in a scratch worktree and requires that named assertion to be the failure.
- A green gate under this mutation makes the component `PADDING`: the audit exits non-zero and
  `estate/ruby-console/` is deleted with a ledger entry naming the date, the mutation and the commit.

## Not yet decided

1. The directory path is not settled. Part II 73.1 gives Ruby the internal admin console role and
   supersedes Part I 31.18, which placed Ruby at `lab/automation-runner/` as a service-account
   automation runner, but Part II does not restate a directory. `estate/ruby-console/` is proposed
   here, not decided.
2. Whether the superseded automation-runner role - and with it the service-account pivot that Part I
   31.18 attached to a named control - moves to this console, moves to another estate component, or
   disappears. This is open and is not assumed here.
3. The format id. A Rails-style tagged logger line is not in the closed format table in 59.6. The
   options are to configure the logger into a format that is in the table, to add a format id to the
   closed set deliberately, or to change the role. Guessing here would contradict the rule that
   format is declared and never inferred.
4. Whether the tag prefix is treated as fields by the adapter or as opaque message text. This
   decision determines how much of the promise this component actually tests and should be made
   explicitly rather than by adapter convenience.
5. The scenario id, the named control, the mutation fraction `p` and the seed.
6. Whether Tier C changed-path per-PR runs are registered as T1 rows in `ci/gates.toml` or only as
   the T2 nightly row (73.9 and 74.4 need reconciling).
7. Whether Ruby is the held-out language under 73.1, which is recorded in
   `docs/research/preregistration.md` before the component is written.
