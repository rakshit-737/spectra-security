# Haskell - license admissibility relation and guard evaluator, used as a differential oracle
Tier: B
Status: not started
Owning spec section: 73 (Part II), with the oracle's scope set by Part II sections 62.5 and 63; supersedes Part I section 31.16
Milestone: M6 - Independent checker and differential gates

## The promise

An independently authored implementation of two things and nothing else: the license admissibility
relation, and the guard evaluator. Given a liveness record and a silent instance, decide whether
that instance is licensed. Given a control configuration and a rule instance, decide whether that
instance is blocked. Part II section 73.1 states the promise as "independently authored oracle for
the license logic and guard semantics only".

Independence is the entire deliverable. The value of this component is that it was written from the
specification text rather than derived from the Rust implementation, so a misreading in one is not
automatically present in the other. Part II section 63 forbids generating this oracle from the guard
AST, from `sglc`, or from any Rust crate in this repository. If it were generated, the two
implementations would be one implementation with two spellings and the differential would prove only
that the generator is self-consistent - the exact error Part II section 62.0 demotes the
simulator-versus-kernel test for.

The promise has a hard ceiling. This component must not implement semi-naive grounding, the
fixpoint, the hitting-set loop, or the certificate format. Part II section 73.1 makes that a build
failure: a Haskell module that imports or reimplements grounding fails the audit with
`TIER_B_SCOPE_CREEP`.

What it is not: formal verification. Part II section 73.11 forbids claiming formal verification from
Haskell. This is an independently authored oracle for one relation and one evaluator. That is the
whole claim and there is no larger one available.

This component also sits on rung D2 of the descope ladder in Part II section 75, alongside the Z3
test-only oracle, and Part II section 63 already marks it stretch tier. If schedule pressure reaches
D2, the ladder's instruction is explicit: delete the directory, do not leave a stub, and the
justification for Haskell in the polyglot roster goes with it. That is a documented outcome, not a
failure, and this file records it up front so the deletion does not later read as a retreat.

## What lives here

No file in this list exists yet.

- A cabal project with a Stackage-pinned `cabal.project.freeze` and a pinned GHC, resolvable from
  the vendored local package repository that Part II section 74.2 requires for offline builds.
- An admissibility module: the relation over liveness windows and silent instances, as algebraic
  data types with total functions.
- A guard evaluator module over the guard expression language, independent of the Rust guard
  compiler.
- `newtype` bindings for the canonical vocabulary, matching the names Part II section 57 fixes and
  checked by the same glossary lint that checks the Rust bindings.
- An hspec suite and QuickCheck properties, including the property the relation exists to protect:
  widening a blind window by the smallest representable amount must change the admissibility verdict
  for an instance sitting on that boundary.
- A runner that consumes the hashed inputs and emits the oracle report to the declared artifact
  path, in canonical JSON with integers only.
- This component's `polyglot.toml` fragment, with every field Part II section 73.4 requires.

Ordered containers only. Part II section 58 lists `Data.Map` and `Data.Set` as permitted here and
`Data.HashMap` and `Data.HashSet` as forbidden.

## Consumer edge

The declared consumer is the admissibility differential gate and the oracle report it reads - the
gate Part II section 73.6's audit transcript names `gates/admissibility::diff`. The gate is owned by
the validation component, not by this directory, which satisfies the non-self-consumption rule of
Part II section 73.3.1.

If this directory is deleted, the kernel, the checker, the API and the frontend all keep running.
The license admissibility relation then has exactly one implementation, and there is no
cross-implementation check on the subtlest relation in the system. The differential gate resolves to
nothing and the Tier B roster loses a row.

Stated plainly: this component's edge is a gate, not a product path. Deleting it removes evidence,
not function. Part II section 75 rung D2 accepts exactly that trade when schedule requires it, which
is why the ladder puts this component low rather than in the never-cut set.

## How it is exercised

- CI job: `polyglot-b / license-oracle-haskell`, the component id Part II section 73.6's audit
  transcript uses for this row.
- Tier: T1 on changed paths per Part II section 73.9; T2 nightly for the full run plus the mutation
  leg. Part II section 74.4's cost table places the Haskell admissibility gate in T2, on the
  `spectra/toolchain-b` image that carries GHC and cabal.
- Component entrypoint: `make -C haskell/policy-oracle oracle`, in the shape Part II section 73.4
  uses for the C component's entrypoint.
- Audit: `make polyglot-audit`, which is the only thing that licenses this directory to stay in the
  tree under Part II section 73.0.

Note that `make mutate` is a different thing: it is Oracle M of Part II section 62.7, which checks
gate liveness across the whole system by applying committed mutant patches. The mutation described
below is the polyglot audit's own, applied to this component's output.

## Mutation check

Operator `constant_result`. Part II section 73.5 makes this the mandatory operator for every Tier B
oracle, in one sentence that is also the reason: "an oracle that still lets its gate pass while
returning a constant is not an oracle".

The corruption: the oracle returns the same admissibility verdict for every input - every silent
instance reported as licensed, regardless of what the liveness record says about the producing
sources. The relation is discarded and a constant is returned in its place.

The gate that must go RED is `polyglot-b / license-oracle-haskell`, at `gates/admissibility::diff`,
the assertion Part II section 73.6's transcript records for this component. Under a constant
oracle, the differential against the Rust kernel must disagree on every fixture where the kernel
refuses a license, and the gate must fail on that disagreement.

If the gate stays green under a constant result, the differential is not consuming the oracle's
verdicts and this component is PADDING under Part II section 73.6. The admissible responses are a
real consumer edge or deletion. Not a better rationale.

## Not yet decided

- **The directory name.** Part I section 31.16 called this `haskell/eclipse-oracle/`. That name is
  illegal under Part II section 73.10.2, which bans the string from every crate, module, package and
  directory name, and enforces it with the `ECLIPSE_IN_ARTIFACT_SURFACE` grep gate. Part II
  superseded the role without restating a path. `haskell/policy-oracle/` is the working name used
  here. `haskell/license-oracle/` has a specific argument in its favour: Part II section 73.6's
  transcript names the component `license-oracle-haskell`, and a directory matching the component id
  is one fewer mapping to get wrong. `haskell/admissibility-oracle/` is the third candidate. Decide
  before the first file, because the `paths` glob and the `ORPHAN_SOURCE` lint key on it.
- **One package or two.** The admissibility relation and the guard evaluator are separate
  responsibilities with separate differentials. Whether they ship as one cabal package with two
  modules or two packages is open, and it affects how narrowly `TIER_B_SCOPE_CREEP` can be scoped.
- **Coverage of the differential.** Part I section 31.16 ran the oracle against every scenario
  fixture and every cell of the degradation matrix. The full matrix is a T2/T3 artifact under Part
  II section 74.4, so full coverage would put this oracle on the matrix's critical path. Whether it
  runs over the whole matrix, a declared spine, or the fixtures only is not settled.
- **The D2 trigger.** Part II section 75.6 defines the scope degradation protocol but the budget
  this milestone is measured against lives in `BUILD_LOG.md`, which has no entry for it yet. Until
  that budget is declared, the condition that would delete this directory is undeclared too.
- **Whether the guard evaluator's differential is the same gate as the admissibility differential.**
  Part II section 73.6 names one gate; Part II section 63 treats guard semantics and admissibility
  as distinct surfaces. One `expect_red` assertion is required per component, so if they are two
  gates, one of them is the declared one and the other is unenforced by the audit.
