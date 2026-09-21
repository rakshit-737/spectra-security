# ADR-0014: Correct the claim in ADR-0013 that make has never run here

## Status

Accepted — 2026-09-21

Supersedes ADR-0013.

## Context

ADR-0013 recorded that the vertical slice is a Python reference implementation, because the
development machine has no Rust toolchain, no Go toolchain, no Docker and no `make`. That decision
is sound and is restated below. But the record drew a wrong conclusion from the missing `make`:

> **`make` has never run in this repository.** Every statement made about the Makefile so far —
> that 57 targets exit non-zero through a shared macro, that four do real work, that the host guard
> aborts at parse time — comes from reading the file and from one agent's experiment with a stub
> `make` on the path. None of it comes from executing the real target.

and from it a consequence:

> **M0 cannot close.** Its gate is `make m0-verify`, and `make` does not exist here.

Both are false. The T1 workflow, `.github/workflows/t1.yml`, runs `make skeleton-verify` on a
GitHub `ubuntu-24.04` runner on every push, and has done so since the first commit that contained
it. At the time ADR-0013 was written it had already run roughly thirty times.

The history of those runs is the most useful evidence the repository holds about any of its gates:

- The **first eleven runs failed.** The first failing run's log reads, in part:
  `MISS dir docs/dev`, `MISS dir docs/kernel`, `MISS dir bench`, `MISS dir lab`, `MISS dir sql`,
  `MISS dir tests`, `MISS dir tools`, `MISS dir web`, `MISS file WAIVER.md`,
  `MISS file .env.example`, `MISS file docs/claims.md`, then
  `skeleton-verify: 11 required path(s) missing` and `make: *** [Makefile:231] Error 1`.
- Those are exactly the eleven paths later found missing by hand on the development machine,
  without reference to CI.
- The runs went green once the paths existed and three of them were corrected to the ones the
  repository actually uses.

So `make skeleton-verify` did not merely run. It failed honestly while the skeleton was
incomplete, named the precise gap, and passed once the gap was closed — on a machine this session
did not control. Nobody looked at it. The claim that no target had ever executed was made while
eleven red CI runs documented the opposite.

The error is a generalisation: `make` absent on one machine was recorded as `make` never having
run in the repository. The distinction is the whole point of CI.

## Decision

ADR-0013's decision is unchanged and is restated in force:

1. The vertical slice is a Python reference implementation, labelled as one everywhere it appears.
2. The checker is a separate Python package that imports nothing from the emitter. Its independence
   is weaker than the specification's, because both are Python written in one session from one
   reading of the specification. No certificate it accepts may be described as independently
   verified until the specified Go checker exists.
3. `rust/` and `go/` keep their roots and remain the specified home of the real implementations.
4. Nothing may state or imply that the Rust kernel or the Go checker exists.

Two claims are corrected:

- **`make` is absent on the development machine; it is present in CI and has run there on every
  push.** `skeleton-verify` and `guard-sandbox` are executed. Every other target is not.
- **M0 is not blocked by the missing local `make`.** Its gate can run in CI. It is blocked because
  `m0-verify` is not implemented, which is a smaller and entirely different problem.

## Consequences

- The repository's strongest evidence that a gate works is now recorded where a reader will find
  it, rather than sitting unexamined in the Actions tab.
- `docs/plan/PLAN_v1.md` carried the same false claim twice and has been corrected in place, since
  a plan is not immutable.
- ADR-0013 stays in the tree with its error intact. Its Status line is changed to
  `Superseded by ADR-0014`; nothing else in it is edited.
- A standing rule follows, and costs nothing to keep: **a claim about what has or has not run in
  this repository is checked against CI before it is written.** `gh run list` answers it in one
  command. This correction is the second in two days to arise from asserting a verification state
  without checking the place that records it.

## References

- ADR-0013, superseded by this record.
- `.github/workflows/t1.yml`, the skeleton job.
- `BUILD_LOG.md` INC-0009.
