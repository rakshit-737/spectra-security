# ADR-0012: Correct the CI cadence recorded in ADR-0007

## Status

Accepted — 2026-09-20

Supersedes ADR-0007.

## Context

ADR-0007 decided that the language surface is kept and made falsifiable: no component stays in the
tree because a rationale argues for it, only because `make polyglot-audit` finds it load-bearing.
That decision holds and is restated below in full force. One clause of it is wrong.

Clause 8 of ADR-0007's Decision section states a CI cadence:

> Tier A is the critical path and runs in full on every push. Tier B adds oracles and measured
> comparisons, and runs its changed-path jobs plus all differential gates per change, with the full
> audit and mutation nightly. Tiers C and D run changed-path jobs per change and the full audit
> nightly.

Per-change execution for Tier B, and per-change changed-path jobs for Tiers C and D, are not what
this repository planned and not what it committed.

`docs/plan/PLAN_v1.md` places the Tier C and Tier D language jobs and the polyglot mutation audit in
T2 — the nightly tier on `main` — and says in the same sentence that a Tier C or D failure never
blocks a Tier A milestone. The committed workflows agree with the plan and not with clause 8:

- `.github/workflows/t1.yml`, the per-push and per-pull-request tier, declares a single language
  job, `lang-tier-a`, and records in its comment that Tier B, C and D run in T2 because Part II
  section 74.0 overrides Part I section 43.1 so that a Tier C or D failure never blocks a Tier A
  milestone.
- `.github/workflows/t2-nightly.yml`, which runs on a nightly schedule against `main`, declares
  `lang-tier-b`, `lang-tier-c`, `lang-tier-d` and `polyglot-audit`.

Where the error came from is visible inside ADR-0007 itself. Its References section names Part I
section 43.1 — the per-push per-language unit tier — as superseded, and then clause 8 restates a
weakened form of 43.1 as if it had survived. The record cites the override and contradicts it a few
paragraphs apart.

None of this is a report about CI having run. Every language job in both workflows is guarded
`if: false` with a stated enabling milestone, and no gate in this repository has ever executed. What
was wrong is the declaration, and the declaration is what an ADR records.

ADR-0001 makes a merged record immutable except for its Status line, so this is a new record rather
than an edit to clause 8, on the precedent of ADR-0010. ADR-0007 stays in the tree stating the wrong
cadence, next to this record stating the right one, and a reader can see what changed.

## Decision

ADR-0007's decision is unchanged apart from clause 8's cadence, and is restated here in force:

1. **The language surface is kept.** It is not deleted, not quietly shrunk and not apologised for.
   `make polyglot-audit` is the only thing that licenses a component to remain in the tree, and its
   per-component verdict is load-bearing or padding.
2. **Every component declares four things, and three is a failure**: a consumer edge naming a
   downstream artifact owned by a *different* component, self-consumption and its own test suite
   excluded; a named CI job that *executes* it rather than linting or building it; a declared,
   deterministic, seeded mutation of its **output** that turns a *named* downstream gate red at a
   *named* assertion; and a role line.
3. **The mutation operator set is closed**, corruptions are applied to output and never to source,
   and returning a constant result is mandatory for every independent oracle and cross-check.
4. **`polyglot.toml` at the repository root is the manifest.** Every executing source file is owned
   by exactly one entry; unowned files fail `ORPHAN_SOURCE` and doubly owned files fail
   `AMBIGUOUS_OWNERSHIP`.
5. **The response to a padding verdict is deletion, not documentation.** Prose rationale is
   commentary and may not be cited as satisfying any gate.
6. **Configuration and markup formats are never counted in a prose language claim**, and counts in
   prose are substituted from the audit's machine artifact rather than typed.
7. **The ingest path contains no language-specific branch.**

The non-cadence parts of clause 8 also stand: a red Tier C or D job does not block a milestone, it
appears in the generated status table within one commit, and it blocks a tagged release; a job that
fails intermittently is quarantined with a ledger entry and is treated as padding at the next
release gate unless it is fixed; silencing a job with `continue-on-error` or a disabling guard fails
a lint.

**Clause 8's cadence is replaced by the cadence the committed workflows declare:**

| Tier | Job | Workflow | Trigger |
| --- | --- | --- | --- |
| A | `lang-tier-a` | `.github/workflows/t1.yml` | every push and pull request |
| B | `lang-tier-b` | `.github/workflows/t2-nightly.yml` | nightly, `main` |
| C | `lang-tier-c` | `.github/workflows/t2-nightly.yml` | nightly, `main` |
| D | `lang-tier-d` | `.github/workflows/t2-nightly.yml` | nightly, `main` |
| — | `polyglot-audit` | `.github/workflows/t2-nightly.yml` | nightly, `main` |

Tier A runs per change. Tier B, Tier C, Tier D and the polyglot mutation audit run nightly on
`main`. No tier below A has a per-change job, changed-path or otherwise.

This is the right cadence for two reasons.

**A Tier C or D failure must never block a Tier A milestone.** That is the plan's rule and the
effect of Part II section 74.0 overriding Part I section 43.1. A job that runs per change sits on
the pull request, and a red check on a pull request is a blocking check in practice whoever says
otherwise; the only durable way to keep an estate-tier regression from stopping product work is not
to put it there. Demotion to T2 is not silencing, and the difference is mechanical rather than
remembered: the job runs, the failure files an issue, the milestone loses its green and `main` is
marked degraded in the status table. Section 73 forbids hiding a job that has run and failed, and
nothing here hides one.

**Executing the roster's pinned toolchains on every change does not fit a per-change wall-clock
budget.** The estate and research tiers exist in order to be heterogeneous, which means each carries
its own toolchain image, and running them all per pull request would blow the T1 ceiling declared in
`docs/plan/PLAN_v1.md` — a ceiling that document itself marks illustrative, not a target. The
pressure that creates is the dangerous part: a tier that cannot fit the budget gets sampled,
skipped, or quietly marked `continue-on-error`, and the audit's credibility goes with it. Nightly
execution on `main` buys the whole roster a budget it can actually meet.

ADR-0007's Status line is changed to `Superseded by ADR-0012 — 2026-09-20`. No other line of
ADR-0007 is edited. It remains in the tree stating the wrong cadence, which is what the immutability
rule is for.

## Consequences

- The substance of ADR-0007 is untouched. The audit, the four checks, the closed operator set, the
  manifest, deletion over rationale and the counting rules are all still in force, and a reader who
  wants the reasoning behind them still reads ADR-0007 for it.
- A reader now needs both records to know what is in force: ADR-0007 for the audit, this one for the
  cadence and for which clause of ADR-0007 not to believe. That cost is accepted. The alternative is
  editing clause 8 in place, which would leave no trace that the repository ever declared a cadence
  its own workflows contradicted.
- The cadence recorded here is sourced to two mutable files. If a later change moves a language job
  between `t1.yml` and `t2-nightly.yml`, this record becomes wrong in exactly the way ADR-0007 was,
  and the answer will again be a superseding record rather than an edit.
- Nightly execution means an estate-tier or research-tier regression can be as old as the commits
  merged since the last run, and bisecting it costs a day of history rather than one pull request.
  That is the price of not blocking Tier A, and it is paid deliberately.
- Tier B moves further from per-change execution than clause 8 supposed: its differential gates are
  nightly too. A differential oracle that disagrees with the product is therefore found after the
  merge, not before it. The mitigation is that the product tier's own contract and determinism gates
  do run per change; the oracle is a second opinion, not the first one.
- Nothing here has been observed. Every job named in the table above is declared and skipped, no
  language job has run, `polyglot.toml` does not exist and `make polyglot-audit` does not exist.
  Status: not started. This record may not be cited as evidence that any tier's CI works.
- The index row in `docs/adr/README.md` is added in the same change as this record; that file is
  ordinary documentation, not an immutable one.

## References

- ADR-0001, the immutability rule and the Nygard format.
- ADR-0007, superseded by this record.
- ADR-0010, the precedent for correcting a merged record rather than editing it.
- `docs/plan/PLAN_v1.md` — the tier table, and the rule that a Tier C or D failure never blocks a
  Tier A milestone.
- `.github/workflows/t1.yml` and `.github/workflows/t2-nightly.yml` — the committed cadence.
- Part II section 74.0, which overrides Part I section 43.1; Part II section 73, on demotion not
  being silencing.
