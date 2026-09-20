# R - degradation-matrix summary statistics
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places R in Tier D and fixes its promise. Part I section 31.24 supplies
the per-language detail and is superseded where the two differ. Nothing described below has
been written; this is session one and every file named here is a file that does not exist.

## The promise

One narrow thing. R is to be the sole implementation of the summary statistics that every
published degradation cell carries: the per-cell median over `seed_index`, the interquartile
range, and bootstrap intervals over seeds. Part II section 61.13 and section 70.4 require
median and IQR on every published cell and make a bare mean a build failure, so the statistics
are not decoration on the results - they are the form the results are required to take.

The promise is not that R is fast, not that R is the correct language for statistics in
general, and not that the statistics establish anything about the pipeline they summarise. It
is narrower than that, and it has two halves:

1. Exactly one program computes the numbers that appear in the published results. No number is
   recomputed by hand, by a spreadsheet, or by a second path inside the Python analysis code.
2. That program is cross-checked by an independently authored one in `analysis/julia/`, and
   disagreement beyond a declared tolerance fails the build rather than being reconciled.

R claims no statistical novelty. Bootstrap resampling over seeds is ordinary method; the
research content of SPECTRA lives in the kernel and in the reconstruction property, not here.
What this directory contributes is the discipline that the published numbers have exactly one
producer and that producer has an independent adversary.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `run_all.R` - the single entry point, reading the degradation matrix results and writing the
  summary artifact. Takes an input path and an output path and nothing else; no interactive
  state, no working-directory assumptions.
- `R/read_matrix.R` - loader for the per-cell results emitted by the degradation harness,
  including the completeness level, the perturbation plan id, the seed index and the
  reconstruction-quality columns.
- `R/cell_statistics.R` - median and IQR per cell, with the quantile definition pinned
  explicitly rather than inherited from a default.
- `R/bootstrap.R` - seeded bootstrap over `seed_index` producing the interval bounds, with the
  resampling seed derived from the run manifest rather than from the clock.
- `R/emit.R` - serialisation of the summary artifact in a stable column order and a stable row
  order, so that two runs on the same input are byte-identical.
- `tests/testthat/` - unit tests over each summarising function, including a test that the
  emitted artifact is byte-identical across two runs in the same container.
- `renv.lock` - the pinned package set, resolvable from the vendored offline cache with the
  network off.
- `.Rprofile` - activation of `renv` so that the pinned library is the only library.

The output artifact is expected to be a single file under `artifacts/analysis/`, holding one
row per matrix cell with its median, its IQR and its bootstrap bounds. Its exact path and
format are not settled; see "Not yet decided".

## Consumer edge

This is the strongest consumer edge in Tier D, and it is worth being precise about why.

Delete this directory and the published degradation numbers lose their producer. Part II
section 71 binds every numeral in `README.md`, `docs/` and the UI strings to a registered claim
with a support artifact, and gate `G-CLAIM-NUMSRC` fails when a numeral in a quantitative claim
is absent from the artifact it cites. With no summary artifact, every claim that cites a
degradation cell fails that gate. `make claims-check` goes red, and because Part II section
71's claims gates run per-PR, the failure is immediate rather than nightly.

Second, the cross-check gate against `analysis/julia/` has nothing to compare against and fails
as an unresolved reference rather than as a disagreement.

Third, `make reproduce` cannot regenerate the results documents from a clean clone, which is
Part II section 73.12.3's done criterion for the generated documentation.

The consumer is owned by a different component in every case - the claims linter and the
results documents are not owned by `analysis/r/` - so section 73.3.1's prohibition on
self-consumption is satisfied without argument.

## How it is exercised

- CI job: `polyglot-d / degradation-stats-r`, in the Tier D workflow.
- Tier: T2. Part II section 74.4's tier-assignment table places "Tier C/D language jobs +
  polyglot mutation audit" at T2, nightly on `main`. A red T2 job files an issue, costs the
  milestone its green, and marks `main` degraded in the README status table; per section 73.9
  it does not block a Tier A milestone but does block a tagged release.
- Make target: `make analysis-r` runs the entry point and the `testthat` suite. The mutation
  leg and the load-bearing checks run under `make polyglot-audit`, which section 73.6 fixes as
  the only target that licenses this directory to remain in the tree.
- Toolchain: a pinned R image listed in `images.lock` and resolved by digest, with `renv`
  restoring from the vendored cache under `--network=none`. Part II section 74.1 assigns the
  analysis runtimes to the `spectra/toolchain-d` image.

## Mutation check

Operator: `constant_result`, from the closed set in Part II section 73.5. Section 73.5's rule
makes `constant_result` mandatory for every Tier D cross-check, and this component is one half
of one.

The corruption: the summary emitter returns a fixed median, a fixed IQR and fixed bootstrap
bounds for every cell, regardless of the input matrix. The artifact is well-formed, has the
right number of rows, the right column order and a valid schema. Only the values are constant.

The gate that must go red: `xcheck/degradation-stats::median_iqr_agree`, the R-versus-Julia
agreement assertion. Julia reads the same matrix, computes its own statistics, and the
assertion compares them cell by cell within the declared tolerance. Under the mutation the
constant values disagree with Julia's computed values on every cell that is not coincidentally
equal to the constant, and the assertion fails naming the first disagreeing cell.

A second gate must also go red, and the audit records both: `G-CLAIM-NUMSRC` under `make
claims-check`, because the numerals registered in the results documents no longer appear in the
support artifact. If only one of the two goes red, the other is decoration and the component's
manifest entry is wrong.

A constant-returning statistics implementation that leaves every gate green is not a statistics
implementation; it is padding, and section 73.6's remedy is deletion of the directory, not a
better rationale for keeping it.

## Not yet decided

- **Milestone.** Part I section 52.2's table places "R or Julia (analysis only)" at M7, with
  the polyglot long tail at M9. Part II section 75.5.1 requires the tiers to be completed in
  tier order - A fully, then B, then C, then D - which puts all of Tier D after Tier C and
  therefore at M9. M9 is recorded above because Part II governs, but the M7 row has not been
  formally retired and the two have not been reconciled in one place.
- **The quantile definition.** R's `IQR()` and `quantile()` default to the Hyndman-Fan type 7
  estimator; Julia's `quantile` defaults to the same family but the two are not guaranteed
  identical at every sample size. The cross-check will produce spurious disagreements unless
  both sides pin the same definition explicitly. Which definition is pinned, and where it is
  recorded, is undecided. Part II section 65.3 bans linear-interpolating estimators outright,
  but that ban is scoped to the liveness crate's decision path, not to the reporting statistics
  here; whether it extends to this directory has not been stated.
- **The declared tolerance.** Section 73.1 says disagreement "beyond declared tolerance" fails
  the build and does not say where the tolerance is declared, what form it takes (absolute,
  relative, ULP), or whether it differs per statistic. An undeclared tolerance defaults in
  practice to whichever value the first implementer picks, which is the failure mode this
  section exists to prevent.
- **Bootstrap seeding and replicate count.** The resampling must be deterministic under the
  determinism charter, which means the seed derives from the run manifest by the rule in Part
  II section 58. The exact derivation string, and whether Julia must reproduce the same
  resamples or only agree on the resulting interval within tolerance, is unsettled. The second
  reading is the weaker cross-check and should be chosen deliberately if it is chosen.
- **Figures.** Part I section 31.24 assigns the `ggplot2` figures to this directory. Part II
  section 73.1 restates R's role as statistics only and does not mention figures, and Part II
  section 70.4 bans smoothing, curve fitting and interpolation between completeness levels. It
  is undecided whether figure generation remains here, moves to the Python analysis path, or is
  dropped; the Part I figure filenames are therefore not repeated above.
- **The output artifact's path and schema.** Part I section 31.24 names
  `artifacts/analysis/summary.csv`. Part II's manifest schema in section 73.4 requires a
  `published_artifact` path, and Part II's repository layout differs from Part I's in several
  places. The path is recorded here as undecided rather than guessed.
- **CI trigger tier.** Section 73.9 gives Tier D "changed-path jobs only" per-PR, which implies
  a T1 trigger, while section 74.4 assigns Tier C/D language jobs to T2. Both can be true - a
  cheap changed-path run per-PR and the full run plus mutation nightly - but no section says so
  explicitly, and the budget in section 74.9 is drawn against one reading or the other.
