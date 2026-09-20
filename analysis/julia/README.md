# Julia - independent re-implementation of the degradation statistics
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places Julia in Tier D and fixes its promise. Part I section 31.26 gave
Julia a different job entirely and is superseded; see "Not yet decided", because the Part I job
has no owner under Part II and that is a real gap rather than a tidy replacement. Nothing here
has been written.

## The promise

The narrowest promise in this directory's tier, and it should be read as narrowly as it is
written: Julia is an independently authored second implementation of the same summary
statistics that `analysis/r/` computes - per-cell median over `seed_index`, interquartile range,
and bootstrap intervals over seeds - and disagreement between the two beyond a declared
tolerance fails the build.

What "independently authored" has to mean for the promise to hold:

- Written from the statistical definitions in Part II section 70.4, not from the R source.
- Not a port. A transliteration of `analysis/r/` reproduces the R implementation's mistakes and
  turns the cross-check into a spell-checker.
- Not sharing a helper library, a serialisation routine, or a resampling implementation with
  the R side. Shared code is shared failure.

Julia promises nothing about performance here. Part I's justification for Julia was its speed
on combinatorial work; that is not the Part II role and no document may carry it over. Julia
promises nothing about numerical superiority either. It promises to disagree when R is wrong,
which is the only property a differential partner has.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `Project.toml` and `Manifest.toml` - the pinned environment, resolvable from the vendored
  depot with the network off.
- `src/DegradationStats.jl` - the module: the matrix loader, the per-cell statistics and the
  bootstrap, each written against the definitions rather than against the R code.
- `src/emit.jl` - serialisation of this side's summary artifact in the same logical schema as
  the R side, so that the comparison is over values rather than over formats.
- `bin/run_all.jl` - the entry point, taking an input path and an output path.
- `test/runtests.jl` - the unit suite, including a determinism test and a test that the module
  does not read the R artifact.
- `test/xcheck.jl` - the comparison itself, if the comparison is owned by this side rather than
  by a neutral harness. Which of those it is has not been decided.

A lint is expected to enforce the independence clause: no file in this directory may reference
`analysis/r/` or read its output artifact, except inside the comparison harness. Without that
lint the independence claim is honour-system.

## Consumer edge

This is the thinnest consumer edge in the roster, and inflating it would be exactly the failure
Part II section 73.0 is written to catch. Stated plainly:

Delete this directory and no published number changes. The R side still computes the medians,
the IQRs and the bootstrap bounds; the results documents still build; the claims gate still
finds its numerals in the support artifact. What is lost is the check - nothing downstream
stops working, and a reader who wanted the numbers still gets them.

So the consumer edge is the cross-check gate and nothing else, which raises the question
section 73.3.1 exists to ask: is that gate owned by a different component? If
`xcheck/degradation-stats::median_iqr_agree` lives in this directory and is run by this
directory's job, then Julia's only consumer is its own test suite and the audit fails it with
`SELF_CONSUMING`. The gate must therefore be owned elsewhere - by a neutral cross-check harness
or by the R component - and that ownership must be recorded in `polyglot.toml` before the first
source file is committed.

The honest summary: Julia survives the load-bearing test only if the cross-check gate is real,
is owned by someone else, and turns red under `constant_result`. If it survives on any weaker
basis than that, it is padding and section 73.6's remedy is deletion.

## How it is exercised

- CI job: `polyglot-d / degradation-stats-julia`, in the Tier D workflow.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Per section 73.9 a red Tier D job does not block a Tier A milestone
  but does block a tagged release, and may not be silenced with `continue-on-error`.
- Make target: `make analysis-julia` runs the entry point and `Pkg.test()`. The comparison and
  the mutation leg run under `make polyglot-audit`.
- Toolchain: the pinned Julia in the `spectra/toolchain-d` image from Part II section 74.1,
  with `JULIA_DEPOT_PATH` pointed at the vendored depot so that `Pkg.instantiate` resolves with
  the network off.

## Mutation check

Operator: `constant_result`, mandatory for every Tier D cross-check under Part II section 73.5.

The corruption: this side's statistics functions return a fixed median, a fixed IQR and fixed
bootstrap bounds for every cell. The emitted artifact keeps its schema, its row count and its
row order; only the values are constant.

The gate that must go red: `xcheck/degradation-stats::median_iqr_agree`. Under the mutation
Julia's constant values disagree with R's computed values on every cell whose true value is not
the constant, and the assertion fails naming the first disagreeing cell.

The point of running this mutation on the Julia side specifically: it is the test of whether
the comparison is a comparison. A cross-check harness that reads one artifact and reports
agreement with itself, or that compares within a tolerance so wide that constants pass, is
decoration. Section 73.5 says it directly - an oracle that still lets its gate pass while
returning a constant is not an oracle - and the same sentence applies to a differential partner.

The mirrored mutation on the R side must turn the same gate red. If only one direction fails,
the comparison is asymmetric and the manifest entry for one of the two components is wrong.

## Not yet decided

- **The Part I combinatorial checks have no owner.** Part I section 31.26 gave Julia a
  brute-force minimum-cardinality hitting set over the corridor set for small fixtures, whose
  optimum had to equal the kernel's cut cardinality, plus a mutation gate on the kernel's
  popcount ordering. That was the only independent check in Part I that the kernel's cut is
  actually minimal. Part II section 73.1 reassigns Julia to the statistics and names no owner
  for the hitting-set check, and section 73.1's Tier B scope clause forbids the Haskell oracle
  from absorbing it - a Haskell module that touches the hitting-set loop fails the audit with
  `TIER_B_SCOPE_CREEP`. Whether a second Julia component exists for that check, whether it is
  Tier B rather than Tier D, or whether the check is dropped, is undecided and is recorded in
  `docs/plan/CONFLICTS.md`.
- **Who owns the cross-check gate.** See "Consumer edge". Until this is fixed in
  `polyglot.toml`, the component cannot pass section 73.3.1.
- **The declared tolerance.** Section 73.1 makes disagreement "beyond declared tolerance" a
  build failure without saying where the tolerance is declared or what form it takes. The same
  gap is recorded on the R side and must be closed once, not twice.
- **Whether the bootstrap resamples must match.** If both sides must draw the same resamples
  from the same derived seed, the cross-check is strong but the two implementations are
  coupled through the resampling scheme. If only the resulting intervals must agree within
  tolerance, the implementations stay independent but the check weakens. This is a real
  trade-off and it has not been made.
- **Quantile definition.** R and Julia must pin the same estimator or the comparison produces
  spurious disagreements at some sample sizes. Undecided; see `analysis/r/README.md`.
- **Milestone.** Part I section 52.2 places "R or Julia (analysis only)" at M7; Part II section
  75.5.1's tier-order rule places all of Tier D at M9. M9 is recorded above because Part II
  governs, but the M7 row has not been formally retired.
- **Directory path.** Part II section 73 does not restate the analysis directory paths, so
  `analysis/julia/` is carried over from Part I section 31.26. Part II's repository layout
  differs from Part I's elsewhere - `octave/` at the root rather than under `analysis/` is the
  nearest example - so it is not certain the analysis directories keep their Part I homes.
