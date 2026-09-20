# Contributing to SPECTRA

> Status: authored in session one. Every gate and make target named here is
> **not started** unless stated otherwise. A declared-but-unimplemented target
> prints what is missing and exits non-zero; it never exits 0 having done
> nothing. Read this file as the rules a change must satisfy once the gates
> exist, and as the rules a human reviewer applies in the meantime.

## What this repository accepts

- **Issues: yes.** Bug reports, reproducible defects, questions about scope, and
  arguments that a claim in the documentation is not supported by its artifact
  are all welcome.
- **The milestone plan is fixed.** The build order, the minimum publishable
  core, and the descope ladder are specified, not negotiated per pull request. A
  pull request that adds a feature outside the current milestone will be closed
  with a pointer to the plan, however good the code is. This is not a judgement
  about the contribution; it is how a one-person research repository stays
  finishable.
- **Pull requests: narrowly.** A pull request that fixes a defect, adds a test
  for existing behaviour, or corrects a document is in scope. Anything that
  starts a new subsystem is not.

## The increment protocol

Work proceeds in **increments**: at most about 400 changed lines, exactly one
concern. An increment is the unit of planning, the unit of logging, and normally
the unit of the commit.

```
PLAN     -> write the increment entry in BUILD_LOG.md (goal, files, tests, gate)
RED      -> write the tests; run them; paste the real failing output
GREEN    -> minimal implementation; run the tests; paste the real passing output
REFACTOR -> clean up; rerun the tests
GATE     -> run the verification gate; paste the real output tail
COMMIT   -> one conventional commit, one concern
LOG      -> append the result and the measured numbers to BUILD_LOG.md
```

Rules:

- Never run PLAN for increment N+1 while increment N is red.
- The written-plan obligation is at **increment** granularity: one `BUILD_LOG.md`
  entry per increment, not one per file.
- `BUILD_LOG.md` is append-only, newest entry at the bottom. History in it is
  never rewritten.
- A `BLOCKED` entry states what was attempted, the exact error, the two or three
  options visible, and the question that needs answering. Then work stops. A
  workaround that silently changes the design is not an option.

## Commits

Conventional commits, imperative mood, **one concern per commit**, scope is the
component directory name.

```
feat(ingest):    a new capability
fix(checker):    a defect repaired
test(liveness):  tests only
perf(grounding): a measured speed change, with the command that measured it
docs(adr):       documentation only
refactor(api):   behaviour-preserving restructuring
chore(ci):       tooling, pins, housekeeping
```

Those seven types are the whole vocabulary. Do not invent an eighth.

Hard rules:

- No commit mixes a feature and a refactor.
- No commit contains commented-out code, a `TODO` without an issue reference, or
  a dead file.
- Every commit body that reports a number cites the command that produced it.
- Never commit with failing tests. Never use `--no-verify`.
- A commit message is externally visible text: the banned-phrase rules below
  apply to it exactly as they apply to the README.

## Every change leaves the repository green

An increment ends with the verification gate passing. A red repository is never
handed forward to the next increment, and "I will fix it in the next commit" is
not an available move.

Until a gate is implemented, "green" means: every declared target either does its
real job or exits non-zero with a message naming what is missing. A target that
exits 0 having done nothing is a defect and will be treated as one. A CI job that
is not implemented is explicitly skipped with a stated reason; a green no-op job
is the same defect wearing a badge.

## The ratchet rule

Milestone gating creates pressure to weaken a test to turn a milestone green. The
ratchet makes weakening visible and expensive instead of invisible and free.

`ratchet.json` at the repository root records, per closed milestone, the gate
list and the measured counts (tests, assertions, property tests, registered
mutation tests, certificate-corpus rejections, end-to-end specs). CI regenerates
the measured fields and compares. `ratchet.json` and `make ratchet-check` are
**not started**.

The rule, once it exists:

1. For every recorded milestone, each current count must be greater than or equal
   to the recorded value, and no gate name may disappear from the gate list.
2. Any decrease, or any disappearing gate, fails CI.
3. A decrease is permitted **only** with a waiver entry in `ratchet.json`
   carrying: the field, the removed gates, the count delta, the descope rung (or
   the explicit words "not a descope"), a rationale, an author and a date.
4. A rationale that is a placeholder (`TODO`, `n/a`, `see PR`) or shorter than 40
   characters fails the lint. When a rung is named, the same commit must contain
   the matching `BUILD_LOG.md` DESCOPE entry.
5. Waivers surface in the generated README status table, with date and rationale.
   A repository whose README hides its waivers is dishonest by omission.
6. Recorded counts are append-only history. Do not edit one downward in place;
   changes go through a waiver.

What is **not** an acceptable way to satisfy the ratchet:

- Trivial assertions (`assert!(true)`, asserting a constant you just defined, an
  assertion whose expression makes no call into the code under test).
- Marking a test `#[ignore]`, `t.Skip`, `@pytest.mark.skip` or `test.skip` to make
  a milestone green. Skipped tests are counted separately and any nonzero count
  needs the same waiver.
- Lowering an assertion, loosening a tolerance, shrinking a fixture, or deleting a
  failing fixture. That is test weakening, not descoping. Descoping removes a
  *feature* and its *claim*; it never removes a *check* on a feature that remains.

## No claim enters the documentation without a backing artifact

Every externally visible claim -- README, `docs/`, UI strings, CLI strings, the
demo transcript, release notes, and any CV or portfolio text generated from this
repository -- must be registered in `docs/claims.md` and bound to the test,
gate or benchmark artifact that supports it, together with its scope qualifier.
`docs/claims.md`, `docs/banned.toml`, `make claims-check` and `make
banned-phrase-gate` are **not started**.

Concretely, in a pull request:

- **No numeral without its committed artifact.** A number in documentation must
  trace to a result file committed in the same change, and the command that
  regenerates it must appear next to it. A number obtained by reading it off a
  terminal once and typing it in is a fabrication.
- **No illustrative number copied from the specification.** Every numeral in the
  build specification's examples -- budgets, elapsed days, test counts, corpus
  sizes -- is illustrative, not a target. Copying one into code, a document or a
  fixture is a defect.
- **No status prose.** Component status, language counts and waivers are rendered
  from `mpc.toml` and `ratchet.json`. Hand-written status sentences in the README
  are rejected.
- **No capability in the present tense before its gate is green.** Unbuilt things
  are marked "planned, not implemented" and never described as if they exist.
- **Banned phrasing**, outside a registered exception: "formally verified",
  "guaranteed", "prevents", "would have stopped", "state of the art",
  "enterprise-grade", "production-ready", "realistic", "AI-powered", "detects
  attacks", a bare verdict token with no scope binding, and any bare "minimum
  cut" not qualified by "over the declared control catalog".
- **No probability, confidence, score, severity, risk rating or likelihood**
  anywhere in an output, a schema, a document or an interface.

## Dependency changes

Dependency bumps are grouped and weekly. A bump must keep hashes reproducible: if
it changes any fixture hash, the same pull request updates the recorded hashes
and states the regenerating command in its body. A bump that cannot keep the
build offline and pinned is rejected.

## Environment

- Development happens inside WSL2 or the devcontainer.
- `TZ=UTC` and `LC_ALL=C`.
- LF line endings, UTF-8, no trailing whitespace, no emoji. `.gitattributes` is
  authoritative and is itself gated.

## Pull request checklist

Copy this into the pull request body and tick it honestly. Leaving a box unticked
with an explanation is fine; ticking a box you did not verify is not.

```
- [ ] Linked issue or ADR
- [ ] One concern; increment entry present in BUILD_LOG.md
- [ ] Determinism: reruns produce byte-identical output
- [ ] No number added to docs without its generating command and committed artifact
- [ ] No claim added to docs without a docs/claims.md entry
- [ ] Test and assertion counts did not decrease, or a ratchet waiver is included
- [ ] No test skipped, ignored, loosened or deleted to make a gate pass
- [ ] The declared gates that exist were run locally and their real output pasted
```

## Code of conduct

Participation is governed by `CODE_OF_CONDUCT.md`.
