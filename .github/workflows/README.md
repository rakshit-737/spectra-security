# CI tiers

**Status: not started.** One gate in this repository is implemented. Every other
job in every workflow here is declared and explicitly skipped. Nothing in this
directory has ever produced a passing gate result, because nothing in this
directory has ever run a gate.

## The one rule that governs this directory

> A requirement with no gate id is not a requirement.
> -- section 74.0

Every gate is a row in [`../../ci/gates.toml`](../../ci/gates.toml). That file is
the only place a gate may be declared (section 74.4). The workflows here are
*runners* of gates, not *declarers* of them:

- A job that names a gate id absent from the registry fails `G-REG-001`.
- A registry row assigned to a tier with no job in that tier's workflow fails
  `G-REG-001`.
- A sentence in `docs/` that says "the build fails if X" without a resolvable
  gate id fails the registry linter, which deletes the claim or fails the build.

This is deliberately harsh. Fifty-seven sections of specification say "the build
fails otherwise". Without this rule, most of those sentences would be decoration.
With it, each one either has a row in the registry and a job in a workflow, or it
is not a requirement and must be deleted from the prose that asserts it.

## The four tiers

Section 74.4 is normative. A gate has **exactly one** tier.

| Tier | Workflow | Trigger | Wall-clock ceiling | A failure means | Measured runtime |
|---|---|---|---|---|---|
| T0 | `../../.pre-commit-config.yaml` | pre-commit hook, local, inside WSL2 or the devcontainer | 60 s (illustrative, not a target) | the commit is refused locally; never authoritative | not measured |
| T1 | `t1.yml` | every push and every pull request | 20 min end-to-end, all jobs (illustrative, not a target) | the pull request is red; the merge is blocked | not measured |
| T2 | `t2-nightly.yml` | nightly, `main` only | 90 min (illustrative, not a target) | an issue is auto-filed; the milestone loses its green; `main` is marked degraded in the README status table | not measured |
| T3 | `t3-weekly.yml` | weekly, `main` only | 6 h (illustrative, not a target) | the release is blocked; headline numbers in docs are invalidated until green | not measured |

T0 is never authoritative. A green pre-commit run proves something to the author
and nothing to anybody else. The authoritative answer for a lint-class gate is
its T1 run.

### Why a gate sits where it sits

Section 74.4's tier-assignment table decides, and it OVERRIDES the "per-PR"
wording used by sections 43, 60, 64, 68 and 70. The shape of it:

- **T1** buys the things that are cheap and load-bearing: formatting, naming,
  vocabulary and banned-phrase lints; the claims linter; guard-AST hash equality
  across backends; byte-identical replay on one runner; `make build-offline` on
  `toolchain-a`; the Tier A language unit tiers; the flagship demo hash; and the
  *spine subsets* of the two combinatorially large gates.
- **T2** buys everything that needs a second runner, a second toolchain image, a
  compose set, or more than a couple of minutes: cross-runner byte identity, the
  full degradation matrix, the differential oracles, the Tier B/C/D language
  jobs, the polyglot mutation audit, the cold offline build, the end-to-end UI.
- **T3** buys everything whose cost scales with time budget or whose numbers get
  published: the benchmark harness, `make reproduce`, long-horizon fuzz, the
  mutation suites, and the flake sweep that runs the whole T1 tier repeatedly
  across two CPU models.

Two consequences worth stating plainly, both from section 74.0:

- **Tier C and Tier D language failures never block a Tier A milestone.** They
  run in T2. Demoting them there is not the same as silencing them: the job
  runs, the result is recorded, and section 73 forbids hiding it behind
  `continue-on-error` or a permanent `if: false`.
- **"Green twice in a row on a clean clone" is a T2 obligation**, not a per-push
  one.

### Sampled gates

Two gates are combinatorially large: the randomized-configuration
simulator-versus-kernel agreement gate, and the degradation matrix. Running
either exhaustively on every push is not affordable, so T1 runs a declared,
deterministic sample: the spine cells always, plus a stride rotation over
`ci/epoch.txt` (section 74.5).

The cost of that is a hard rule, `G-SAMP-001`: **an artifact whose
`claim_scope` is `SAMPLED` may not back a sentence in `docs/`.** A T1 run is
never "the full matrix", never "exhaustive", never "all configurations", never
"every cell". Headline numbers bind to T2 and T3 artifacts with full coverage,
and to nothing else.

## What "skipped" means here, and what it does not mean

Every job in these three workflows except `skeleton` in `t1.yml` carries:

```yaml
    if: false # enabled at M<n> (<what that milestone delivers>)
```

and a body of exactly one step that prints `not implemented: <gate id>` for each
gate the job owns and then exits 1.

- GitHub renders such a job **grey / skipped**. It is not a green check.
- **No skipped job may be added to the branch-protection required-check list.**
  A required check that never runs is a required check that always passes.
- **No skipped job may be described as green, passing or covered** in the README,
  in a milestone claim, in a status table or in a badge.
- If the guard is ever removed while the gate is still unwritten, the job runs,
  prints what is missing, and exits non-zero. That is the intended failure mode.
  Nothing in this directory exits 0 having done nothing.

Section 73 forbids silencing a red Tier C or D job with `continue-on-error` or an
`if: false` guard. That prohibition is about hiding a job that *has run and has
failed*. These guards sit on jobs whose gate does not exist yet, each names the
milestone that deletes it, and the commit that implements a gate is the commit
that removes its guard.

## Zero flake, and no retries anywhere

Section 74.8.1: **flakes fail the build.** Automatic retry is forbidden.
`continue-on-error`, `retries:`, `--rerun-failed`, `pytest-rerunfailures`,
`go test ... || true` and every equivalent are banned outright.
`G-FLAKE-001` is a linter that greps every file under `.github/workflows/` and
`ci/` for them and fails on a hit. Do not add one to make a job green.

A test may be quarantined only by a row in `ci/quarantine.toml`, with an expiry
no more than 14 days out, evidence, a hypothesis and an owner. Expiry is
enforced by `G-FLAKE-003`, not by good intentions. Some gate classes are marked
`soundness = true` in the registry and **cannot be quarantined at all** -- the
zero-false-ROBUST gate, the must-reject certificate corpus, determinism and
byte-identity, the guard-AST equality lint, the antitonicity property,
`make build-offline`, the egress sentinel and the claims linter. If one of those
flakes, the system is wrong, not the CI.

## Budget

`make ci-budget` is the authority and `G-BUDGET-001` is the gate. Adding a gate
without removing time elsewhere fails there. Raising a `budget_s` to fit is
forbidden; the permitted responses are to sample the gate, demote it to a slower
tier, or delete the requirement it enforces -- each of them visible in the diff of
`ci/gates.toml`.

| Tier | Gates declared | Gates implemented | Declared sum vs ceiling | Measured runtime | Measured CI minutes |
|---|---|---|---|---|---|
| T0 | 3 | 0 | within ceiling | not measured | not measured |
| T1 | 96 | 1 | over ceiling -- unreconciled | not measured | not measured |
| T2 | 88 | 0 | over ceiling -- unreconciled | not measured | not measured |
| T3 | 14 | 0 | over ceiling -- unreconciled | not measured | not measured |

The "over ceiling" rows are not a formatting accident. The specification names
more gates than its own CI budget can hold, and `ci/gates.toml` records the
arithmetic rather than hiding it. `G-BUDGET-001`, once implemented, will fail on
the registry as it stands; that is the gate doing its job. Reconciling it is a
precondition for enabling any job in these workflows beyond the skeleton gate.
See `TODO(budget)` at the head of `ci/gates.toml`.

## Runtime environment

- Every target runs inside WSL2, the devcontainer or CI. `make` is not supported
  on Windows `cmd.exe` or PowerShell; a guard in the Makefile refuses (74.10).
- `TZ=UTC` and `LC_ALL=C` everywhere, including the schedule expressions in these
  workflows, which are UTC so they do not drift twice a year.
- Supported platform set: Linux `amd64`, and Windows 11 via WSL2 or the
  devcontainer. Not macOS. Not `linux/arm64`. Not Windows natively.
- Every action reference must be pinned to a full commit SHA with the version in
  a trailing comment (74.11.2). No `latest`, no floating range, no tag.
- No CI step may install anything from the network. A tool a job needs goes into
  a tier image, and `images.lock` changes in the same pull request (74.11.1).
  `make toolchain-refresh` is the only target permitted to touch the network.

## Artifacts, and the fact that they expire

Section 74.7: **an artifact that has expired can never be cited.** CI artifact
storage silently evicts. The durable record is the committed ledger under
`ci/ledger/`, plus results files committed under `docs/research/results/` when
they back a documented claim. Raw CI logs are never citable and are never a
source for a number.

No artifact exists yet.

## Adding a gate

1. Add the row to `ci/gates.toml`: id, title, tier, owner section, make target,
   `sampled`, `soundness`, artifact, `budget_s`. Remove time elsewhere in the
   same tier, or the budget gate fails.
2. Implement the make target. A target that is not implemented prints what is
   missing and exits non-zero; it never exits 0 having done nothing.
3. Add or extend the job in the tier's workflow, and delete that job's
   `if: false` guard in the same commit that makes the gate real.
4. Only then may prose refer to the property the gate enforces, and only in the
   tense the evidence supports.
