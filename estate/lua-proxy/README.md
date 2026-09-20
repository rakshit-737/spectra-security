# Lua - OpenResty reverse proxy in the observed estate, emitting an nginx log_format stream
Tier: C
Status: not started
Owning spec section: 73 (Part II, 73.1 Tier C roster; load-bearing test 73.3)
Milestone: M9 - Polyglot surface and performance (Part I 52.12), audited by `make polyglot-audit` from the same milestone onward

## The promise

The Tier C promise, from Part II 73.1:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component's share is a reverse proxy whose request-handling logic is Lua running inside
OpenResty, emitting the access stream its `log_format` directive defines. The proxy sits in front of
other estate services, so its records are the one view in which requests to several differently
written services appear in a single shape. Reconstruction across it must happen with no Lua-specific
branch, identifier or filename in `ingest/` (73.3.4).

What is not promised: nothing about the proxy's performance, its security posture, or its
equivalence to any deployment. It is a subject of reconstruction, and under Part I 30.7.3 it may not
import the rule table, the control catalog, the axioms or the certificate schema.

One boundary is worth stating because Part I 31.20 placed Lua on the other side of it: this Lua does
not run inside SPECTRA. It is not a sandboxed transformer hosted by the normalizer and it performs
no normalization, enrichment or redaction of telemetry on the pipeline's behalf. It is observed, not
trusted.

Nothing here is implemented. No request has been proxied and no line emitted or ingested.

## What lives here

Planned contents, none of which exist yet:

- The proxy configuration, including the `log_format` directive that fixes the emitted field set.
  This directive is the emission contract and is reviewed as one.
- The Lua request-handling scripts: upstream selection, header handling, and whatever admission
  behaviour the committed scenario script actually drives.
- Pinned runtime and module versions resolvable from the offline vendor path recorded in
  `polyglot.toml`.
- A seeded driver that replays a committed request sequence through the proxy so that emitted
  content is reproducible.
- A committed golden of one seeded run's access stream.
- A `Makefile` exposing the declared entrypoint and a manifest fragment declaring the emitted
  `format_id`, since format is declared and never sniffed (59.6).

No SPECTRA code, and no telemetry transformation performed for the pipeline's benefit.

## Consumer edge

Required edge (73.3.1): a downstream artifact owned by a different component must consume this
output. The intended consumer is the scenario expectation owned by the kernel and scenario-fixture
side: because the proxy fronts several estate services, its records are the cross-service view that
ties a request observed at one service to the same request observed at another, and the downstream
expectation is the committed reconstruction for that scenario. There is a second, sharper dependency:
this source's liveness. If the proxy stream is absent for a period, that period is a window in which
the pipeline cannot see requests at all, and the verdict must react accordingly.

Plainly, for session one: nothing exists, so deleting this directory today breaks nothing. The edge
is a precondition on the commit that creates it. A component consumed only by its own tests fails
with `SELF_CONSUMING` and is deleted under 73.6 rather than documented.

## How it is exercised

- CI job: `polyglot-c / estate-lua-proxy`, named in the component's `ci.job` field.
- Tier: T2 (74.4 assigns Tier C/D language jobs and the polyglot mutation audit to the nightly
  tier), with a changed-path per-PR run permitted by 73.9. The job must run the proxy and collect
  its access stream; `luacheck` and unit tests alone do not satisfy 73.3.2.
- Make target: the declared entrypoint `make -C estate/lua-proxy emit`, with the load-bearing checks
  run by `make polyglot-audit`.

A red job here does not block a milestone, appears in the README status table within one commit, and
blocks any tagged release.

## Mutation check

- Operator: `empty_output` from the closed set in 73.5 - a zero-byte artifact with exit code zero.
  It is applied to output, never to source.
- Corruption, concretely: after a seeded run, the proxy's collected access stream is replaced with a
  zero-byte file while the run still reports success. The proxy appears to have handled nothing at
  all for the entire scenario, which is the single most consequential thing a fronting source can
  falsely appear to do.
- Gate that must go RED: the assertion named in `mutation.expect_red`, of the shape
  `polyglot-c / estate-lua-proxy :: scenario/<id>::verdict_matches_expected`. With no records from
  the proxy, the scenario's cross-service correspondence is unsupported and the period the proxy
  should have covered is a window in which nothing was observed; the committed verdict expectation
  no longer holds. The audit applies the mutation in a scratch worktree, runs exactly that job, and
  requires that named assertion to be the failing one.
- If every gate stays green under a source that emitted nothing, the component is `PADDING`, the
  audit exits non-zero, and `estate/lua-proxy/` is deleted with a ledger entry.

## Not yet decided

1. The directory path is not settled. Part II 73.1 gives Lua the OpenResty reverse-proxy role and
   supersedes Part I 31.20, which placed Lua at `lab/transformers/` as sandboxed transformers hosted
   inside the Rust normalizer, but Part II does not restate a directory. `estate/lua-proxy/` is
   proposed here, not decided.
2. Whether the superseded in-pipeline transformer role, and the sandbox-escape test surface that
   went with it, is dropped entirely. It is not assumed here to survive, and if any part of it does,
   it belongs to a different component than this one because the trust boundaries are opposite.
3. The format id. An `nginx.combined` entry exists in the closed table in 59.6, but a `log_format`
   directive can be configured to emit fields that entry does not define. Either the directive is
   constrained to the committed grammar or the format set is extended deliberately; it is not
   inferred at ingest.
4. Whether the proxy is treated as one source or as one source per fronted upstream. This changes
   liveness accounting and the meaning of the `empty_output` mutation, and is unresolved.
5. The scenario id and the exact verdict expectation the mutation must break.
6. Whether Tier C changed-path per-PR runs are registered as T1 rows in `ci/gates.toml` or only as
   the T2 nightly row (73.9 and 74.4 need reconciling).
7. Whether Lua is the held-out language under 73.1, recorded in
   `docs/research/preregistration.md` before the component is written.
