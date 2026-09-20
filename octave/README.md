# GNU Octave - inter-arrival quantile sensitivity for the liveness threshold
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places GNU Octave in Tier D and fixes its promise. Part I section 31.25
described a different and larger component in a different directory and is superseded; see
"Not yet decided". Nothing here has been written.

This repository uses GNU Octave. The numerical code here is written for Octave, is executed by
Octave in CI, and has never been executed by any other numerical environment. The reason, and
the non-equivalence, are stated once in `docs/polyglot/octave-not-matlab.md`, which is the only
file permitted to discuss it; Part II section 73.1 makes any mention elsewhere a build failure
with `BANNED_MATLAB_MENTION`.

## The promise

One narrow thing, and it is a sensitivity result rather than a decision.

Part II section 65.3 fixes the liveness threshold on an exact-rank order statistic over
inter-arrival gaps: integer arithmetic, no interpolation, no floating point, with the level
written as an exact rational such as `99/100` and decimal literals rejected at parse time.
Section 65.3.1 adds a minimum sample size below which the profile entry is INSUFFICIENT and
every window on it is BLIND. The level is declared in configuration, hashed into the
certificate, and selected by a pre-registered rule - never tuned after seeing a verdict.

Octave's promise is to show what that pinned choice costs. It is to be the sole implementation
of the exact-rank quantile sweep across `95/100`, `99/100` and `999/1000` over the same gap
samples, reporting how the threshold and therefore the blind-window volume move as the level
moves. That sweep is a published sensitivity artifact and nothing else.

What the promise excludes, explicitly:

- Octave does not choose the level. The level is pre-registered under Part II section 65.9.3
  and section 70; a sweep that fed back into the choice would be the tuning that section
  forbids.
- Octave computes no verdict, licenses no silent instance, and is on no decision path. Its
  output is read by people and by a cross-check gate, not by the kernel.
- Octave's implementation of the exact-rank estimator is cross-checked against the Rust
  liveness quantile at the pinned level. That cross-check is the independence claim; the sweep
  at the other levels is the artifact.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `quantile_exact_rank.m` - the estimator, implemented from the procedure in Part II section
  65.3 rather than from the Rust source, in integer arithmetic.
- `n_min.m` - the minimum-sample-size rule from section 65.3.1, so that a level whose sample is
  too small to contain its tail is reported as INSUFFICIENT rather than as a number.
- `sweep_levels.m` - the sweep across the declared levels, emitting one row per source, regime
  and level.
- `blind_volume.m` - the derived quantity: how much window volume each level's threshold
  classifies as blind, on a fixed gap profile.
- `load_profile.m` - the reader for the gap profile the liveness pass emits.
- `emit_sweep.m` - serialisation of the sweep artifact in a stable row and column order.
- `test/run_tests.m` - the suite, including golden comparisons against committed reference
  values and the boundary cases the exact-rank rule turns on.
- `test/golden/` - the committed reference values.

Every script is written to run non-interactively under `octave --no-gui --quiet`, with no
toolbox dependency beyond the pinned package set, no OOP handles and no parallel constructs.

## Consumer edge

Honest, and weaker than it looks at first reading.

Under Part II, the liveness pass does not consume this directory's output. Section 73.1 makes
Octave a downstream cross-check of the Rust liveness quantile, which reverses the direction
Part I section 31.25 specified. So deleting this directory does not stop the kernel, does not
stop a certificate being produced, and does not change any verdict.

What breaks is narrower than that, and there are two things:

1. The cross-check gate `xcheck/quantile::exact` loses one of its two sides. That gate is the
   only independent confirmation that the Rust exact-rank estimator implements the procedure in
   section 65.3 rather than a linear-interpolating estimator that happens to agree on the test
   fixtures. Section 65.3's estimator ban exists because an interpolating estimator puts
   floating point on a decision path; an independent implementation is how that ban is checked
   rather than asserted.
2. The sensitivity artifact loses its producer. Any document that reports how the blind-window
   volume moves with the level has no support artifact, and the claims gate `G-CLAIM-NUMSRC`
   under `make claims-check` fails for every numeral in that document.

The second edge only exists if a published document actually reports the sweep. If no document
does, then this component's only consumer is the cross-check gate, and it must be the case that
the gate is owned by a different component - the Rust liveness crate's differential test, not
Octave's own test suite - or section 73.3.1 fails it with `SELF_CONSUMING`. That ownership has
to be recorded in `polyglot.toml` before the first script is committed.

## How it is exercised

- CI job: `polyglot-d / quantile-sweep-octave`. That component id is the one Part II section
  73.6's audit transcript uses, so it is fixed rather than proposed.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. A red Tier D job does not block a Tier A milestone under section
  73.9 but does block a tagged release, and may not be silenced.
- Make target: `make octave-sweep` runs the scripts and the golden suite. The cross-check and
  the mutation leg run under `make polyglot-audit`.
- Toolchain: the pinned Octave in the `spectra/toolchain-d` image from Part II section 74.1,
  resolved by digest from `images.lock`, with the signal package vendored.

## Mutation check

Operator: `constant_result`, mandatory for every Tier D cross-check under Part II section 73.5.

The corruption: `quantile_exact_rank.m` returns a fixed gap value regardless of the sample and
the level. The sweep artifact keeps its schema, its row count and its row order; every
threshold in it is the same number.

The gate that must go red: `xcheck/quantile::exact`, the assertion that Octave's estimator and
the Rust liveness quantile return the identical order statistic at the pinned level, on the
same gap samples, for every source and regime in the fixture set. Under the mutation the
constant disagrees with the Rust value on every sample whose true order statistic is not the
constant, and the assertion fails naming the first disagreeing source and regime.

The mutation is chosen for a specific reason. The cheapest way for this gate to be green for
the wrong reason is for the comparison to be run against a fixture set whose gap samples are
nearly uniform, where many estimators agree. A constant-returning implementation passes any
comparison that is not actually comparing, so this mutation is the test of the gate, not of the
scripts.

## Not yet decided

- **Directory path.** `octave/` at the repository root is what Part II section 73 uses in the
  audit transcript and in the naming-gate discussion. Part I section 31.25 placed the component
  under `analysis/`. The root path is recorded above because Part II governs, but Part II never
  restates the analysis directory layout as a whole, so the placement of this directory
  relative to `analysis/r/` and `analysis/julia/` is inconsistent and has not been reconciled.
- **The scope of `BANNED_MATLAB_MENTION`.** Section 73.1 fails the build on a case-insensitive
  word match "outside this paragraph's own file", and section 73.12.5 names that file as
  `docs/polyglot/octave-not-matlab.md`. It is not stated whether the gate scans file contents
  only, or also paths, filenames, `.gitattributes` entries and pinned-version comments. The
  filename itself contains the banned token, so a document that cites the path - including this
  one - matches the pattern. Either the gate excludes paths, or the file is renamed, or every
  citation of it is an exemption. This must be settled before the gate is switched on.
- **The rest of the Part I component.** Part I section 31.25 also assigned periodicity and
  beaconing detection by autocorrelation and Welch PSD to this directory, and made the liveness
  pass a consumer of its output. Part II section 73.1 restates the role as the quantile sweep
  alone and does not say the spectral analysis was dropped. It is undecided whether it was
  dropped, moved, or simply not restated.
- **Whether the sweep is published.** The consumer edge above depends on it. If no document
  reports the sensitivity result, the component has one consumer, and section 73.3.4 then
  requires a `published_artifact` path for a Tier D component declaring `role = "none"`. That
  path has not been chosen.
- **Integer width in Octave.** Gaps are `u64` nanoseconds in section 65.3. Octave's default
  numeric type is double, which is exact only to fifty-three bits, so the estimator must use
  `int64`/`uint64` throughout or it will disagree with Rust on large gaps for reasons that have
  nothing to do with the estimator. Whether the fixture gaps can reach that range, and whether
  the scripts are required to use integer types unconditionally, has not been stated.
- **The swept levels.** `95/100`, `99/100` and `999/1000` are what section 73.1 names. Whether
  the slack multiplier from section 65.3's threshold rule is swept alongside the level, or held
  fixed, is undecided - and the blind-volume result means something different in each case.
- **CI trigger tier.** Section 73.9 gives Tier D changed-path jobs per-PR, implying T1, while
  section 74.4 assigns Tier C/D language jobs to T2. Both readings are defensible and the
  budget is drawn against one of them.
