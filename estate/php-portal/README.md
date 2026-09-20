# PHP - legacy self-service web app in the observed estate, emitting error_log and access logs
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise, stated once in Part II 73.1 and shared by this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component's share of it is a legacy self-service web application that emits what such an
application actually emits: an access log and an `error_log`, the second of which has no field
structure worth the name. The ingest path must reconstruct across it without containing a PHP
branch, a PHP-named adapter, or a PHP-named conditional anywhere in `ingest/` (73.3.4).

What is not promised: no claim is made about the application's quality, its vulnerabilities, or its
resemblance to any deployed system. It is a subject, not a tool, and under Part I 30.7.3 it may not
import the rule table, the control catalog, the axioms or the certificate schema. It knows nothing
about SPECTRA and must be able to be read as an ordinary small web application.

Nothing here is implemented. No page has been served, no log line emitted, no record ingested.

## What lives here

Planned contents, none of which exist yet:

- The application itself: a login form, a session-bearing self-service area, a file-download
  endpoint, and the handful of handlers the committed scenario script actually drives.
- The web server and PHP configuration that fix the access log format and the `error_log`
  destination. These configuration files are the emission contract.
- A dependency lockfile pinned for offline install, with the vendor path recorded in `polyglot.toml`.
- A seeded driver script that walks the committed request sequence so a run reproduces without a
  wall clock or an RNG deciding content.
- Committed goldens for both emitted streams, compared modulo the fields the pipeline is forbidden
  to depend on.
- A `Makefile` exposing the declared entrypoint, and a manifest fragment declaring a `format_id` per
  emitted stream, since format is declared in the manifest and never sniffed (59.6).

No SPECTRA code of any kind.

## Consumer edge

Required edge (73.3.1): a downstream artifact owned by a different component must read this
component's output. The intended consumer is the demo-path expectation: Part I 31.17 places the
portal on the demo path with the first evidence item in the counterexample tree being one of its
access-log lines, and the corresponding downstream artifact is the end-to-end assertion - owned by
the frontend and certificate side, not by this directory - that the witness leaf resolves to a real
event identifier backed by a real raw record from this source. Remove the portal's output and that
leaf has nothing behind it.

Plainly, for session one: nothing exists, so deleting this directory today breaks nothing. The edge
is therefore a precondition on the commit that creates it. Self-consumption fails the audit with
`SELF_CONSUMING`; a component with no consumer is deleted under 73.6 rather than explained.

## How it is exercised

- CI job: `polyglot-c / estate-php-portal`, named in the component's `ci.job` field in
  `polyglot.toml`.
- Tier: T2 (Part II 74.4 places Tier C/D language jobs and the mutation audit in the nightly tier),
  with a changed-path per-PR run permitted by 73.9. The job must execute the application and collect
  its emitted streams; a lint-and-compile job does not satisfy 73.3.2.
- Make target: the declared entrypoint `make -C estate/php-portal emit`, with `make polyglot-audit`
  running the load-bearing checks.

A red job here does not block a milestone, surfaces in the README status table within one commit,
and blocks any tagged release.

## Mutation check

- Operator: `drop_records(p, seed)` (73.5, the telemetry-emitter operator), applied to this
  component's output.
- Corruption, concretely: after a seeded run, a seeded fraction of the emitted access-log lines is
  deleted from the collected stream before ingest. The remaining file is well-formed, the run exits
  zero, and the deletion is invisible to anything that only checks exit status.
- Gate that must go RED: the end-to-end demo assertion named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-php-portal :: e2e/demo::witness_leaf_resolves`. When the line behind the
  first witness leaf is gone, the leaf cannot resolve to a stored raw record and the assertion
  fails. The audit runs exactly that job in a scratch worktree and requires the named assertion to
  be the one that fails.
- If the gate stays green, the component is `PADDING`, the audit exits non-zero, and
  `estate/php-portal/` is deleted with a ledger entry - not documented into safety.

## Not yet decided

1. The directory path is not settled. Part II 73.1 keeps PHP as the legacy self-service web app but
   does not restate a directory; Part I 31.17 placed it at `lab/legacy-portal/`. `estate/php-portal/`
   is proposed here, not decided.
2. The format id for the access log. The closed table in 59.6 offers `nginx.combined` for access
   logs, which is named after one server; whether this portal is served in a way that produces that
   exact grammar, or whether the grammar's name is simply the format's name, has to be settled
   before the manifest is written. The set is closed and additions are deliberate, not incidental.
3. The format id for `error_log`. That stream has no field structure and no entry in the closed
   table obviously covers it. The candidates - treat it as a constrained syslog subset, declare a new
   format id, or accept that a defined portion of it is quarantined by design - are open. Whichever
   is chosen must be decided in the ingest section's terms, not invented here, and quarantine must
   remain quarantine rather than becoming silent truncation.
4. Whether both emitted streams are separate manifest sources with separate liveness, or one source
   with two formats. This matters for blind-window accounting and is unresolved.
5. The scenario id, the mutation fraction `p` and the seed.
6. Whether Tier C changed-path per-PR runs get their own T1 rows in `ci/gates.toml`, or whether only
   the T2 nightly row exists (73.9 and 74.4 need reconciling).
7. Whether PHP is the held-out language under 73.1, which must be recorded in
   `docs/research/preregistration.md` before the component is authored.
