============================================================
65. LIVENESS ESTIMATION AND THE SELF-CALIBRATION PROBLEM
============================================================

## 65.0 The defect this section exists to close

Part I (ECLIPSE §4A) defines a source `s` as live over `[a,b]` iff observed records bracket the
interval, the BLAKE3 chain has no sequence gap, and `max inter-arrival <= q99(s) computed from this
run's own data`. That last clause is a soundness hole with a direct exploit path:

```
        delete records from source s
                  |
                  v
   observed inter-arrival distribution STRETCHES
                  |
                  v
          q99(s) INFLATES  (threshold derived from the evidence it polices)
                  |
                  v
     the induced gaps no longer exceed the threshold  ->  window judged LIVE
                  |
                  v
      no license issued  ->  P_max SHRINKS  ->  fewer hypotheses quantified over
                  |
                  v
   kernel emits ROBUST in exactly the high-degradation cells the research is about
```

Suppression conceals itself, monotonically harder to detect the more of it there is. The failure is
silent, is worst at the cells that carry the headline result, and defeats the build-failing
"zero false ROBUST" invariant without tripping a single flag.

OVERRIDES Part I: ECLIPSE §4A's clause "q99(s) computed from this run's own data" is deleted in its
entirety. No liveness threshold may ever be derived from the bundle under analysis. This section
replaces the estimator, the calibration source, the classification lattice, the backdating
interaction, and the output schema.

## 65.1 The Envelope Direction Rule (EDR)

Implement the following as the governing invariant of the whole liveness stage. Every other
requirement in 65 is a consequence of it.

1. `P_max` is the set of hypotheses the kernel quantifies over. Growing `P_max` weakens ROBUST and
   strengthens UNSAFE. Shrinking `P_max` strengthens ROBUST.
2. **Any decision that shrinks `P_max` must be backed by positive, recorded, re-checkable evidence.**
   Withholding a license is such a decision. It requires a CALIBRATED threshold, a verified bracket,
   and an intact integrity chain, all cited by identifier.
3. **Any decision made under uncertainty, missing input, insufficient sample, parse failure,
   unreadable profile, unknown regime, or internal error must grow `P_max`.** The window is BLIND.
4. There is no code path in which absence of information yields LIVE. A `Result::Err` in the liveness
   stage is not propagated as a run failure and is not defaulted to LIVE; it is converted to a BLIND
   verdict with a reason code, and the reason code is published.
5. Fail-closed is conservative for the verdict and **inflationary for the blindness premium**. Every
   BLIND verdict therefore carries a reason code, and blind volume is reported partitioned by reason
   so that premium attributable to missing calibration is never presented as premium attributable to
   observed sensor gaps (see 65.8).

A lint (`make lint-edr`) fails the build if the liveness crate contains `unwrap()`, `expect()`,
`panic!`, or any `?` that escapes the classification function, or if `Verdict::Live` is constructed
anywhere except the single site named in 65.5.

## 65.2 Elimination of self-calibration: the source profile

The arrival model is an **input**, produced by a separate command on a separate run, hashed into the
certificate.

### 65.2.1 Definition

A `SourceProfile` is produced by `spectra calibrate` from a **reference clean run**: the same
scenario family, at completeness 100%, with the identity degradation spec, executed under a seed
drawn from a declared calibration seed band that is disjoint from every analysis seed band.

OVERRIDES Part I: ECLIPSE §2 input list gains a fifth mandatory input, `profile.json`, and ECLIPSE
§5 `Cert.hashes` gains the field `profile`.

### 65.2.2 Gap population

For each source `s` and each declared regime `r`:

- Order `s`'s records by the canonical total order `(timestamp_ns, seq, event_id)`. Stable sort only.
- Emit consecutive differences as `u64` nanoseconds. Zero-valued gaps are retained. No deduplication.
- Discard any gap whose span intersects an interval listed in the scenario spec's
  `excluded_intervals` (setup, teardown, declared quiescence). That list is authored in the scenario
  spec, hashed, and may not be edited after a held-out scenario exists; an edit marks the scenario
  TUNED under the protocol in section 62.
- Regime membership is read from the **scenario spec's phase timeline**, a hashed input. It is never
  inferred from the data. If a scenario declares no phases, the profile is single-regime and carries
  `regime_collapsed: true`, which sets the run flag `profile_regime_collapsed`.

### 65.2.3 Canonical profile schema

```json
{
  "schema": "spectra.source_profile/1",
  "profile_id": "blake3:<64 hex>",
  "generator_config_hash": "blake3:...",
  "scenario_family": "corp-idp-pivot",
  "degradation_spec_hash": "blake3:<hash of the IDENTITY spec>",
  "calibration_seed_band": [1000000, 1000063],
  "reference_bundle_hash": "blake3:...",
  "reference_run_manifest_hash": "blake3:...",
  "excluded_intervals_hash": "blake3:...",
  "regime_collapsed": false,
  "sources": [
    {
      "source_id": "iam_audit",
      "integrity_class": "chained",
      "regimes": [
        {
          "regime_id": "baseline",
          "n_gaps": 4187,
          "order_statistics": {
            "95/100":   812000000,
            "99/100":  2140000000,
            "999/1000":6009000000
          },
          "min_gap_ns": 0,
          "max_gap_ns": 6410000000,
          "gap_digest": "blake3:<hash of the full ascending gap vector>"
        }
      ]
    }
  ]
}
```

All numerals in the example above are illustrative, not targets. `order_statistics` keys are exact
rationals written as `"<p>/<q>"`; only levels enumerated in `liveness.toml` are emitted. `gap_digest`
binds the published order statistics to the full sample so the Go checker can reject a hand-edited
profile when the full vector is supplied as a side file.

### 65.2.4 Binding gates (build fails otherwise)

`spectra prove` refuses to start, and `spectra verify` rejects the certificate, unless all hold:

| # | Predicate | Violation reason code |
|---|-----------|----------------------|
| B1 | `profile.reference_bundle_hash != cert.hashes.bundle` | `PROFILE_SELF_CALIBRATED` |
| B2 | `profile.degradation_spec_hash == IDENTITY_SPEC_HASH` | `PROFILE_FROM_DEGRADED_RUN` |
| B3 | `cert.seed not in profile.calibration_seed_band` | `PROFILE_SEED_OVERLAP` |
| B4 | `profile.generator_config_hash == cert.generator_config_hash` | `PROFILE_CONFIG_MISMATCH` |
| B5 | `profile.scenario_family == cert.scenario_family` | `PROFILE_FAMILY_MISMATCH` |
| B6 | `profile.excluded_intervals_hash == cert.excluded_intervals_hash` | `PROFILE_INTERVALS_MISMATCH` |

B1 is the anti-self-calibration gate and is checked independently by the Go checker. OVERRIDES
Part I: ECLIPSE §5 checker obligation (d) is extended — the checker recomputes the liveness
derivation **and** re-evaluates B1..B6 from the hashed inputs.

### 65.2.5 Type-level separation (Rust)

The classifier is structurally incapable of seeing the analysis run's distribution. The run supplies
the **statistic**; the profile supplies the **threshold**; there is no type by which the reverse can
be expressed.

```rust
/// Everything the classifier may know about the run. One scalar test statistic, no distribution.
pub struct WindowObservation {
    pub source: SourceId,
    pub window: (TimeNs, TimeNs),
    pub regime: Option<RegimeId>,          // None => B_REGIME_UNKNOWN
    pub left_bracket:  Option<Bracket>,    // record at t <= window.0
    pub right_bracket: Option<Bracket>,    // record at t >= window.1
    pub n_records_in_span: u32,
    pub max_observed_gap_ns: u64,          // scalar statistic, never a sample
    pub chain: ChainState,
}
pub struct Bracket { pub event: EventId, pub t: TimeNs, pub seq: Option<Seq> }

pub enum ChainState {
    Verified { missing_seq: Option<(Seq, Seq)> },
    Unverified { first_bad: EventId },
    Absent,
}

pub struct Threshold { pub value_ns: u64, pub prov: ThresholdProvenance }

pub enum ThresholdProvenance {
    Profile { profile_id: Hash, source: SourceId, regime: RegimeId,
              n: u32, p: (u32, u32), slack: (u32, u32) },
    Declared { spec_hash: Hash },      // 65.4 fallback F3 only
    // There is deliberately NO `Empirical` / `FromRun` variant. Adding one fails `make lint-edr`.
}

pub fn classify(t: Option<&Threshold>, o: &WindowObservation, cfg: &LivenessCfg) -> Verdict;
```

`liveness::classify` takes no bundle handle, no fact base, no `&[u64]` sample. A build gate
(`make lint-liveness-deps`) asserts the `spectra-liveness` crate's dependency closure excludes the
ingest and grounding crates.

## 65.3 The quantile estimator

Exact rank on order statistics. Integer arithmetic only. No interpolation, no floating point.

```
QUANTILE_EXACT_RANK(D_sorted_ascending, p, q) -> u64
  n = len(D_sorted_ascending)                       // n >= 1 guaranteed by caller
  // 1-based upper order statistic: j = ceil(n * p / q), computed in u128 to avoid overflow
  j = (n * p + (q - 1)) / q                          // integer ceiling division
  j = clamp(j, 1, n)
  return D_sorted_ascending[j - 1]
```

Requirements:

1. `p`, `q` are `u32` and are written in configuration as an exact rational string, e.g. `"99/100"`.
   No decimal literal is accepted; the parser rejects `0.99`.
2. **Tie rule.** Duplicate gap values are retained as distinct samples and are never collapsed.
   Because the returned object is a value at an index of a value-sorted vector, the result is
   invariant to the ordering of equal elements; nonetheless the sort MUST be stable over the
   canonical record order so that `gap_digest` and the serialized profile are byte-identical across
   runs and platforms.
3. **Estimator ban.** Linear-interpolating estimators (R type 7, numpy default, "nearest-rank with
   averaging", Hyndman-Fan types 4..9) are FORBIDDEN. They introduce floating point into a decision
   path and violate the determinism charter. A grep gate fails on `f32`/`f64` in the liveness crate.
4. **Threshold.** `T(s, r) = ceil( Q * slack_num / slack_den )` in `u64` nanoseconds, saturating on
   overflow to `u64::MAX` (which makes the window trivially pass the gap test — therefore overflow
   additionally sets reason `B_THRESHOLD_OVERFLOW` and forces BLIND, per the EDR).
5. `p/q` and `slack_num/slack_den` are declared in `liveness.toml`, hashed into the certificate, and
   selected by the pre-registered rule in 65.9.3 — never tuned after seeing a verdict.

### 65.3.1 Minimum sample size `n_min` and mandated fail-closed behavior

An upper order statistic at level `p/q` estimated from a sample too small to contain the tail is not
an estimate; it is the sample maximum wearing a label.

```
K_TAIL   : u32   # required expected observations strictly above the quantile
N_FLOOR  : u32   # absolute floor regardless of level
n_min(p,q) = max( N_FLOOR, ceil( K_TAIL * q / (q - p) ) )
```

- For `p/q = 99/100` and `K_TAIL = 5`, `n_min = max(N_FLOOR, 500)` (illustrative, not a target).
- If `q - p == 0` the configuration is rejected at parse time.
- **If `profile.sources[s].regimes[r].n_gaps < n_min`, the profile entry is INSUFFICIENT. Every
  window on `(s, r)` is BLIND with reason `B_PROFILE_INSUFFICIENT`. It is never LIVE.** This is the
  mandated fail-closed behavior. There is no "fall back to the sample maximum", no "use the next
  coarser quantile", no "borrow the neighbouring regime".
- A second, independent sample-size condition applies to the **window**, not the profile:
  if `o.n_records_in_span < cfg.m_min`, the window is BLIND with reason `B_WINDOW_UNDERSAMPLED`.
  A single-record span cannot evidence continuity of emission.
- NEGATIVE REQUIREMENT: `n_min` and `m_min` may not be lowered to turn a milestone green. Both are
  recorded in the ratchet file; a decrease without a `WAIVER.md` entry fails CI.

## 65.4 Fallback ladder when no profile exists

Exactly one mode is selected per run, deterministically, by the ladder below. The selected mode and
its reason are written into `liveness.json` and the certificate.

| Mode | Precondition | Threshold source | May a window be LIVE? | Flags set | Premium publishable? |
|------|--------------|------------------|-----------------------|-----------|----------------------|
| F0 CALIBRATED | profile present, B1..B6 hold, `n_gaps >= n_min` for `(s,r)` | `ThresholdProvenance::Profile` | yes | none | yes |
| F1 INSUFFICIENT | profile present, source or regime missing, or `n_gaps < n_min` | none | **no** | `liveness_uncalibrated` | per-source suppression (65.8) |
| F2 NO_PROFILE | run invoked with explicit `--no-profile` | none | **no** (all windows BLIND) | `blind_by_default` | **no** |
| F3 DECLARED | source declares a nominal emission period in the hashed scenario spec **and** `--allow-declared-profile` is passed | `ThresholdProvenance::Declared` | yes | `liveness_uncalibrated` | **no** |
| F4 SELF | — | — | — | — | — |

- **F4 does not exist.** Deriving any threshold from the analysis bundle is forbidden. It is
  unrepresentable in the type system (65.2.5), rejected by `make lint-edr`, and detected by gate
  B1 at both emit and verify time.
- F2 is the maximally conservative setting: every window BLIND, `P_max` at its largest. A ROBUST
  verdict obtained under F2 is *stronger*, not weaker, and is permitted. But the blindness premium,
  the decisive observation set and the redundancy index are **degenerate** under F2 and are
  structurally suppressed from the certificate, the API response and the UI. Emitting them under F2
  fails the schema lint.
- F3 exists so that a synthetic emitter with a declared fixed period is not penalized for lacking a
  calibration run. It is not a licence to invent a rate for a source whose rate is unknown. The
  scenario spec field is `sources.<id>.nominal_period_ns`; absent the field, F3 is unavailable and
  the ladder falls to F1.
- Mode selection is per `(source, regime)`, not per run, except F2 which is global.

## 65.5 Classification: LIVE / BLIND / SUPPRESSED

### 65.5.1 Integrity classes

OVERRIDES Part I: ECLIPSE §4A treats every source as hash-chained. Real telemetry is not. Every
source declares `integrity_class` in the scenario spec:

| Class | Guarantee | SUPPRESSED issuable? | Notes |
|-------|-----------|----------------------|-------|
| `chained` | BLAKE3 sequence chain, monotone `seq`, each record binds its predecessor | yes, authenticated | lab-only assumption; must be labelled as such in docs |
| `sequenced` | monotone `seq`, no cryptographic binding | yes, **unauthenticated** — forgeable | sets `liveness_unauthenticated` |
| `none` | timestamps only | **no** | gaps can only ever be BLIND |

At least one source in every scenario family MUST be `none`. Results are reported split by
integrity class; an aggregate detection figure that mixes classes is forbidden.

### 65.5.2 Ordered classification rules

The first matching rule wins. The order is total and is part of the spec; reordering it changes
verdicts and requires a certificate schema version bump.

```
R1  mode == F2                                   -> BLIND      B_FORCED_NO_PROFILE_MODE
R2  o.regime is None                             -> BLIND      B_REGIME_UNKNOWN
R3  threshold is None (F1)                       -> BLIND      B_PROFILE_INSUFFICIENT
R4  threshold overflowed                         -> BLIND      B_THRESHOLD_OVERFLOW
R5  chain == Unverified{..}                      -> BLIND      B_CHAIN_UNVERIFIED   + tamper_suspected(s)
R6  chain == Verified{ missing_seq: Some(i,j) }
      and class == chained                       -> SUPPRESSED S_CHAIN_SEQ_GAP
R7  chain == Verified{ missing_seq: Some(i,j) }
      and class == sequenced                     -> SUPPRESSED S_SEQ_GAP_UNAUTHENTICATED
                                                                + liveness_unauthenticated
R8  left_bracket is None or right_bracket is None-> BLIND      B_UNBRACKETED
R9  o.n_records_in_span < cfg.m_min              -> BLIND      B_WINDOW_UNDERSAMPLED
R10 o.max_observed_gap_ns > threshold.value_ns   -> BLIND      B_GAP_EXCEEDS_THRESHOLD
R11 otherwise                                    -> LIVE       L_CALIBRATED_OK
```

- R11 is the **only** construction site of `Verdict::Live` in the codebase.
- R5 before R6: a chain that does not verify does not get to localize anything. A forged chain must
  not be allowed to manufacture a tidy SUPPRESSED window, nor to certify continuity.
- SUPPRESSED and BLIND both license silent rule instances. They differ in what is published: a
  SUPPRESSED window carries `witness: [event_of_seq_i, event_of_seq_j]` and a missing-`seq` count;
  a BLIND window carries a reason code only. SUPPRESSED sets `tamper_suspected(s)` when the missing
  range intersects any corridor-relevant interval.
- A window may be SUPPRESSED on one source and LIVE on another. Licensing of a silent rule instance
  requires **all** of `producing_sources(tau)` to be non-LIVE over the interval, unchanged from
  ECLIPSE §4C.

### 65.5.3 Sub-window decomposition

Windows are evaluated on a deterministic grid, not on arbitrary caller-supplied intervals: the
breakpoint set is the union of (i) every observed record timestamp on `s`, (ii) every regime
boundary from the scenario spec, (iii) every interval endpoint requested by the silent-envelope
stage. Verdicts are computed per elementary interval and then merged by run-length encoding over
equal `(verdict, reason)` pairs. This makes `liveness.json` a function of hashed inputs alone and
independent of the order in which the envelope stage asks questions. A property test asserts that
permuting the envelope stage's query order yields a byte-identical `liveness.json`.

## 65.6 Interaction with the backdating detector

Part I runs a Bellman-Ford pass over the difference-constraint graph and **voids** licenses resting
on provably backdated timestamps. The critics found the consequence: voiding a license shrinks
`P_max`, and shrinking `P_max` can only move a verdict toward ROBUST. An adversary who controls
timestamps can therefore manufacture a ROBUST verdict by tampering — the system rewards the attack
it claims to detect.

OVERRIDES Part I: ECLIPSE §4A's "voids licenses resting on provably backdated timestamps" is
replaced by the dispute protocol below. **No license is ever removed from `P_max` by the temporal
consistency pass.**

### 65.6.1 Protocol

1. Build the difference-constraint graph over event timestamps from happens-before edges declared by
   the rule table plus per-source `seq` monotonicity. Run Bellman-Ford with a deterministic edge
   order (canonical `(src_event, dst_event)` lexicographic) and a step budget, never a wall clock.
2. **No negative cycle** -> every license is `TEMPORALLY_CONSISTENT`. Proceed.
3. **Negative cycle found** -> the timestamp set is mutually inconsistent. It does *not* identify
   which timestamp is wrong. Compute the deterministic minimal correction set `C`: the
   lexicographically least minimum-cardinality set of constraint edges whose removal restores
   feasibility, exact while `|edges in cycles| <= cfg.mcs_exact_cap`, otherwise a documented greedy
   cover with `mcs_greedy` flagged.
4. Every license whose interval endpoints depend on an event incident to `C` is marked
   `TEMPORALLY_DISPUTED`. **It is retained in `P_max` with full force.** Fail-open on the license is
   fail-closed on the verdict (EDR clause 2).
5. Set `tamper_suspected` on every source contributing an event in `C`.
6. Compute, for reporting only, the counterfactual `P_max' = P_max \ {disputed licenses}` and its
   verdict. If `verdict(P_max') != verdict(P_max)`, set `verdict_tamper_sensitive = true` and record
   both verdicts in `liveness.json` under `tamper_sensitivity`.

### 65.6.2 Hard verdict rules

```
tamper_suspected(s) for any s whose license appears in any corridor of Psi_max
        OR verdict_tamper_sensitive == true
   =>  safety field is UNCONSTRUCTIBLE as ROBUST
   =>  safety = OPTIMISTIC_ONLY, reason = TEMPORAL_DISPUTE
```

- This is enforced in the type that builds the certificate: the `Safety::Robust` constructor is
  private and takes a `NoTamperToken` that can only be minted by a pass that observed zero
  `tamper_suspected` sources and `verdict_tamper_sensitive == false`.
- The Go checker independently recomputes `tamper_suspected` from `liveness.json` and the bundle and
  **rejects** any certificate asserting ROBUST while the flag set is non-empty.
- NEGATIVE REQUIREMENT: it is forbidden to present a run in which tampering was detected as a
  stronger result than a run in which it was not. Any UI or narration string implying "tamper
  detected, therefore the conclusion is firmer" fails the banned-phrase gate.
- Red-team fixtures (owned by the Part II kernel threat-model section): a backdating fixture whose
  untampered twin yields UNSAFE must not yield ROBUST. This fixture is in the corpus that must never
  produce ROBUST.

### 65.6.3 The other direction: bridging forgery

An adversary may *insert* a record inside a gap to make a BLIND window look LIVE. For
`integrity_class = chained` this requires forging the chain and is caught by R5. For `sequenced` and
`none` it is not detectable. Therefore: any run in which a corridor's absence depends on a LIVE
verdict issued on a non-`chained` source sets `liveness_unauthenticated`, and the docs state
plainly that liveness on unchained sources is an assumption, not a measurement.

## 65.7 `liveness.json` output schema

OVERRIDES Part I: ECLIPSE §4A's `liveness.json` is replaced by the schema below and remains hashed
into the certificate.

```json
{
  "schema": "spectra.liveness/2",
  "mode_global": "F0_CALIBRATED",
  "profile_id": "blake3:...",
  "quantile": "99/100",
  "slack": "3/2",
  "n_min": 500,
  "m_min": 3,
  "sources": [
    {
      "source_id": "iam_audit",
      "integrity_class": "chained",
      "mode": "F0_CALIBRATED",
      "threshold_ns": 3210000000,
      "threshold_provenance": {
        "kind": "profile", "profile_id": "blake3:...",
        "regime": "baseline", "n": 4187, "p": "99/100", "slack": "3/2"
      },
      "intervals": [
        { "t0": 1700000000000000000, "t1": 1700000420000000000,
          "verdict": "LIVE", "reason": "L_CALIBRATED_OK" },
        { "t0": 1700000420000000000, "t1": 1700002820000000000,
          "verdict": "SUPPRESSED", "reason": "S_CHAIN_SEQ_GAP",
          "missing_seq": [4471, 4488], "witness": ["evt:9f21", "evt:9f3a"] }
      ],
      "blind_volume_ns_by_reason": {
        "B_GAP_EXCEEDS_THRESHOLD": 0,
        "B_PROFILE_INSUFFICIENT": 0,
        "B_UNBRACKETED": 90000000000
      },
      "suppressed_volume_ns": 2400000000000,
      "tamper_suspected": false
    }
  ],
  "flags": { "liveness_uncalibrated": false, "liveness_unauthenticated": false,
             "blind_by_default": false, "profile_regime_collapsed": false,
             "verdict_tamper_sensitive": false, "mcs_greedy": false },
  "tamper_sensitivity": null
}
```

All numerals above are illustrative, not targets. Serialization is canonical: keys in the fixed order
declared by the schema, integers only, no floats anywhere, `u64` nanoseconds, no wall-clock or host
fields in hashed content.

## 65.8 Blind-volume accounting and premium honesty

1. Blind volume is measured in nanoseconds of interval per source, never in "number of windows".
2. It is **partitioned by reason code**. The partition is published, not summarized.
3. The blindness premium `S_rob \ S_opt` must be annotated, per control in the premium, with the
   fraction of its supporting licenses whose reason code is a *calibration-deficiency* reason
   (`B_PROFILE_INSUFFICIENT`, `B_REGIME_UNKNOWN`, `B_FORCED_NO_PROFILE_MODE`,
   `B_THRESHOLD_OVERFLOW`, `B_WINDOW_UNDERSAMPLED`) as opposed to an *observed-gap* reason
   (`B_GAP_EXCEEDS_THRESHOLD`, `B_UNBRACKETED`, `S_*`).
4. FORBIDDEN CLAIM: presenting a premium control as "needed because the sensor was blind" when its
   licenses rest on calibration-deficiency reasons. The correct string is "needed because this run
   was not calibrated for this source". The UI must render the two causes distinctly; a screenshot
   test covers both.
5. Under F2 the premium is suppressed entirely (65.4).

## 65.9 Experiment: liveness classifier accuracy against generator ground truth

This is a first-class experiment, pre-registered under section 62, executed over the whole
degradation matrix, reported on HELD-OUT scenarios separately from TUNED ones.

### 65.9.1 Ground truth and label space

The generator emits, per `(source, elementary interval)` on the clean reference run, the record count
it *actually produced*. The degradation harness emits, per cell, the set of records it removed. Their
composition gives the ground-truth label:

```
GT(s, I) = TRULY_COMPLETE   iff no record produced in I was removed by any operator
GT(s, I) = TRULY_GAPPED     otherwise
GT_LOCALIZED(s, I) = true   iff the removal is a contiguous seq range (SUPPRESSED is achievable)
```

Requirement on the degradation model section: removal must be recorded as a set of stable
`(source_id, seq, event_id)` triples in `degradation_manifest.json`, so that ground truth survives
the transforms that alter the event stream. Without that manifest this experiment is unmeasurable.

### 65.9.2 Error taxonomy and gates

| Class | Condition | Consequence | Gate |
|-------|-----------|-------------|------|
| **false-LIVE (Type-L)** | `GT = TRULY_GAPPED`, verdict `LIVE` | license withheld, `P_max` shrinks, **path to false ROBUST** | published per cell and per integrity class; build fails if the rate at any cell exceeds the pre-registered ceiling in the ratchet file, or regresses against it |
| **false-BLIND (Type-B)** | `GT = TRULY_COMPLETE`, verdict `BLIND`/`SUPPRESSED` | conservative; inflates premium | published per cell; feeds premium precision; no build failure |
| **mislocalized** | `GT_LOCALIZED = false`, verdict `SUPPRESSED` | over-claims localization | build fails on any occurrence |
| **missed localization** | `GT_LOCALIZED = true`, verdict `BLIND` | conservative | published |

Metrics are computed **twice**: by interval count and by duration-weighted volume. Both are
published; a single headline number is forbidden. The evaluation population is the union of the
windows actually queried by the silent-envelope stage on the clean run and a fixed synthetic grid
declared in the pre-registration, so that the population does not drift with rule-table edits.

### 65.9.3 Sensitivity sweep and the parameter selection rule

Sweep `p/q in {95/100, 99/100, 999/1000}` x `slack in {1/1, 3/2, 2/1}` x the whole completeness
matrix x the declared seed set (multiple seeds; variance reported; one run per cell is not a result).
The shipped `(p/q, slack)` is chosen by a rule fixed in `docs/research/preregistration.md` before
held-out scenarios are executed:

```
choose argmin over (p/q, slack) of   max-over-cells false-LIVE volume
subject to                           mean-over-cells false-BLIND volume <= FB_CAP
tie-break                            larger q, then larger slack, then lexicographic
```

`FB_CAP` is declared in the pre-registration. Selecting parameters after inspecting verdicts, or
per-scenario, is forbidden and is detectable by comparing the preregistration commit hash recorded
in every results table against the config commit.

### 65.9.4 Companion gates

| Gate | What it asserts | Target |
|------|-----------------|--------|
| G65.1 no-self-calibration, static | `ThresholdProvenance` has no run-derived variant; liveness crate cannot reach ingest/grounding | `make lint-liveness-deps` |
| G65.2 no-self-calibration, dynamic | Deleting records from `s` **outside** the tested window leaves that window's verdict and reason byte-identical | `make test-liveness-invariance` |
| G65.3 blind-volume monotonicity | With nested deletion sets per seed, per-source blind+suppressed volume is non-decreasing as completeness drops 100% -> 30%, pointwise, and `S_rob` is non-decreasing under set inclusion | `make gate-monotonicity` |
| G65.4 fail-closed | For every reason code, a fixture exists that produces it, and none of them can produce LIVE | `make test-liveness-reasons` |
| G65.5 float ban | no `f32`/`f64`/decimal literal in the liveness crate or profile parser | `make lint-float-ban` |
| G65.6 profile binding | B1..B6 rejections, one fixture each, at both emit and verify | `make test-profile-binding` |
| G65.7 tamper blocks ROBUST | backdating fixture whose untampered twin is UNSAFE never yields ROBUST | `make gate-redteam` |
| G65.8 checker agreement | Go checker's independently written liveness derivation matches the Rust one on a differential fuzz over random bundles and profiles | `make fuzz-liveness-diff` |
| G65.9 gate liveness | deliberately inject a self-calibrating threshold; G65.2 and G65.3 must go red | `make mutate-liveness` |

G65.3 requires the degradation operators to produce **nested** deletion sets across completeness
levels for a fixed seed. That is mandated here as a constraint on the degradation model section: a
non-nested matrix makes monotonicity statistical rather than provable and the gate becomes noise.

G65.9 is mandatory. A green gate is evidence only if a broken implementation turns it red.

## 65.10 CLI

All numerals in the transcripts below are illustrative, not targets.

```
$ spectra calibrate --scenario corp-idp-pivot --seed 1000007 \
      --degradation identity --out profiles/corp-idp-pivot.json
reference run ...................... ok   (seed 1000007, band [1000000,1000063])
sources ............................ 7
  iam_audit      chained     regimes=2  n_gaps=4187/2210   >= n_min(500)   OK
  proxy_access   sequenced   regimes=2  n_gaps=19044/8812  >= n_min(500)   OK
  host_syslog    none        regimes=2  n_gaps=311/98      <  n_min(500)   INSUFFICIENT
profile_id blake3:7c41e0...  written profiles/corp-idp-pivot.json
WARNING: host_syslog is INSUFFICIENT; every window on it will be BLIND (fail-closed).
```

```
$ spectra prove --bundle runs/c70-delete/bundle.jsonl --goal goals/exfil.toml
error: no source profile supplied.

  Liveness thresholds may not be derived from the bundle under analysis (section 65.2).
  Choose one:
    --profile profiles/corp-idp-pivot.json      (mode F0, LIVE verdicts possible)
    --no-profile                                (mode F2, every window BLIND; the blindness
                                                 premium, decisive observation set and
                                                 redundancy index are suppressed)
exit 2
```

```
$ spectra prove --bundle runs/c70-delete/bundle.jsonl --goal goals/exfil.toml \
      --profile profiles/corp-idp-pivot.json
liveness  mode=F0_CALIBRATED  profile=blake3:7c41e0  q=99/100 slack=3/2
  iam_audit     LIVE 61%  BLIND 12%  SUPPRESSED 27%   [S_CHAIN_SEQ_GAP x3]
  proxy_access  LIVE 88%  BLIND 12%  SUPPRESSED  0%
  host_syslog   LIVE  0%  BLIND100%  SUPPRESSED  0%   [B_PROFILE_INSUFFICIENT]
flags: liveness_uncalibrated=true  liveness_unauthenticated=false  tamper_suspected=false
safety=OPTIMISTIC_ONLY  minimality=EXACT
note: premium control `credential_rotation` rests 100% on calibration-deficiency licenses
      (host_syslog B_PROFILE_INSUFFICIENT), not on observed sensor gaps.
```

```
$ spectra verify cert.json --profile profiles/corp-idp-pivot.json
REJECT  PROFILE_SELF_CALIBRATED
  profile.reference_bundle_hash == cert.hashes.bundle (blake3:1d90aa...)
  The arrival model was calibrated on the run it is being used to analyze.
exit 1
```

## 65.11 Configuration

```toml
# liveness.toml  — hashed into every certificate.
# The values below are illustrative defaults, not targets; the shipped values are
# selected by the pre-registered rule in 65.9.3 and recorded in the ratchet file.

schema        = "spectra.liveness_cfg/1"
quantile      = "99/100"      # exact rational; decimal literals are rejected at parse time
slack_num     = 3
slack_den     = 2
k_tail        = 5             # expected observations above the quantile
n_floor       = 30            # absolute floor on profile sample size
m_min         = 3             # minimum observed records in a window's span
mcs_exact_cap = 64            # deterministic step budget, never a wall-clock timeout

[modes]
allow_declared_profile = false   # F3 requires an explicit CLI opt-in as well

[reporting]
split_by_integrity_class = true
suppress_premium_under_f2 = true
```

## 65.12 Negative requirements and forbidden claims

1. Do NOT compute any quantile, mean, median, variance, threshold, rate or "typical gap" from the
   bundle under analysis for any purpose that feeds a liveness verdict.
2. Do NOT interpolate between order statistics. Do NOT use floating point anywhere in the liveness
   stage, the profile parser, or the threshold arithmetic.
3. Do NOT default to LIVE on missing profile, missing regime, parse error, insufficient sample,
   overflow, or internal error. Every such path is BLIND with a reason code.
4. Do NOT remove a license because timestamps are inconsistent. Mark it disputed, keep it, flag it,
   block ROBUST.
5. Do NOT emit `safety = ROBUST` while any `tamper_suspected` source contributes a license to any
   corridor, or while `verdict_tamper_sensitive` is true.
6. Do NOT report a single aggregate detection accuracy across integrity classes. Do NOT report a
   liveness accuracy figure without the duration-weighted counterpart beside it.
7. Do NOT emit the blindness premium, decisive observation set, or redundancy index under mode F2.
8. Do NOT lower `n_min`, `m_min`, `k_tail`, or `FB_CAP`, or widen `slack`, in response to a failing
   gate without a `WAIVER.md` entry that surfaces in the README status table.
9. Do NOT describe a window as "verified live", "confirmed continuous", "proven complete", or
   "no data loss". The supported string is: "no gap exceeding the calibrated threshold was observed,
   under profile `<profile_id>`, on a `<integrity_class>` source". These strings are registered in
   the claims registry; unregistered variants fail the banned-phrase gate.
10. Do NOT claim that SPECTRA detects suppression in general. The supported claim is scoped:
    detection on `chained` sources is authenticated; on `sequenced` sources it is forgeable; on
    `none` sources suppression is undetectable and is represented only as BLIND volume. A perfectly
    suppressed event on a `none` source inside a window whose gap stays under the calibrated
    threshold and which triggers no obligation axiom remains permanently invisible; its measured
    frequency is published in `LIMITATIONS.md`.
11. Do NOT present tamper detection as strengthening a verdict. Detected tampering can only weaken
    the safety field, never improve it.
12. Do NOT treat the calibration run as a measurement of the real world. The profile is a model of a
    seeded generator's emission behavior under one scenario family; it says nothing about the arrival
    process of any production telemetry source, and no document may imply otherwise.
