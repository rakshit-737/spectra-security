============================================================
48. BENCHMARK FRAMEWORK
============================================================

48.1 PURPOSE AND NON-PURPOSE

1. Build `bench/`, a single harness that takes a **dataset manifest** in and emits a **results artifact** out. Nothing else in the repo is allowed to produce a performance or accuracy number that appears in documentation.
2. The harness is a measurement instrument, not a demo. It must run headless, offline, inside Docker, with no API server, no browser, no LLM, and no network namespace.
3. Do NOT build a "benchmark mode" inside the FastAPI service. Do NOT let the React UI compute any statistic that is later quoted. Do NOT allow `time.time()` deltas printed to stdout to be treated as results.

48.2 DIRECTORY LAYOUT

```
bench/
├── Makefile                      # `make benchmark`, `make benchmark-quick`, `make figures`
├── manifests/
│   ├── quick.json                # 3 scenarios x 3 seeds, smoke, < 4 min
│   ├── full.json                 # 12 scenarios x 10 seeds x degradation matrix
│   └── degradation.json          # section 50 matrix only
├── runner/
│   ├── __init__.py
│   ├── cli.py                    # spectra-bench run --manifest ... --out ...
│   ├── isolation.py              # cgroup/cpuset pinning, env scrubbing, clock capture
│   ├── hardware.py               # hardware + toolchain fingerprint
│   ├── schema.py                 # Pydantic v2 models, THE normative results schema
│   ├── writer.py                 # JSONL -> Parquet, atomic publish, manifest hashing
│   └── arms/                     # one module per comparison arm (see section 49)
│       ├── arm_rules.py
│       ├── arm_seqanom.py
│       ├── arm_spectra.py
│       └── arm_graphonly.py
├── analysis/
│   ├── R/         figures.R  stats.R  bootstrap.R
│   ├── julia/     surface.jl degradation.jl
│   └── octave/    matrix_heatmap.m
└── results/                      # git-ignored except results/INDEX.json
```

48.3 DATASET MANIFEST (INPUT)

Define `bench/schema/manifest.schema.json` (JSON Schema draft 2020-12) and validate every manifest against it before a run starts. A manifest that fails validation aborts with exit code 2 and writes nothing.

```json
{
  "manifest_version": "1.0.0",
  "manifest_id": "full-v3",
  "description": "Full arm comparison plus degradation sweep",
  "spectra_version_constraint": ">=0.4.0,<0.5.0",
  "scenarios": [
    {
      "scenario_id": "S07_oauth_token_theft",
      "generator": "spectra.gen.scenarios.s07",
      "generator_params": { "hosts": 24, "identities": 60, "horizon_s": 86400 },
      "ground_truth": "required",
      "expected_events": { "min": 180000, "max": 260000 }
    }
  ],
  "arms": ["rules", "seqanom", "spectra", "graphonly"],
  "seeds": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010],
  "repeats": 5,
  "warmups": 2,
  "degradation": {
    "completeness": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3],
    "operators": ["none", "delete_random", "delete_targeted", "reorder",
                  "duplicate", "delay_jitter", "corrupt_field",
                  "strip_identity", "backdate", "forge_provenance", "silence"]
  },
  "limits": {
    "per_cell_wall_s": 900,
    "per_cell_rss_mb": 8192,
    "total_wall_s": 43200
  },
  "rates_file": "bench/rates.toml"
}
```

Requirements:

4. `seeds` are integers written in the manifest. The runner must never call an unseeded RNG. Seed every generator, every perturbation operator, every shuffle, every tie-break, and every bootstrap resample from a per-cell derived seed `seed_cell = blake3(seed || scenario_id || arm || operator || completeness)[0:8]`.
5. `repeats` are re-executions of an identical cell for timing variance. `seeds` are distinct data draws for statistical variance. They are different axes and must never be collapsed. Accuracy statistics aggregate over `seeds`; latency statistics aggregate over `seeds x repeats`.
6. `warmups` runs execute before the first measured repeat of each cell and their results are discarded but still recorded with `"warmup": true` so discarding is auditable.
7. Record `expected_events`. If a generator emits outside that band, fail the cell with `status: "MANIFEST_DRIFT"` rather than silently accepting a different dataset.

48.4 RUNNER ISOLATION

Implement `bench/runner/isolation.py` to enforce, and to record what it enforced:

8. One cell per process. Never reuse a Python interpreter across cells; a leaked cache is a fabricated speedup.
9. Container: `docker run --rm --network=none --cpuset-cpus=<pinned> --memory=<limit> --pids-limit=512 --read-only --tmpfs /tmp spectra-bench:<digest>`. Record the image digest, not the tag.
10. Scrub the environment to an allowlist. Set `PYTHONHASHSEED=0`, `RUSTFLAGS` pinned, `RAYON_NUM_THREADS`, `OMP_NUM_THREADS`, `TOKIO_WORKER_THREADS` all explicit. Record all of them.
11. Refuse to start if `/sys/devices/system/cpu/intel_pstate/no_turbo` cannot be read, or if the governor is not `performance`, unless `--allow-unstable-clocks` is passed; if passed, stamp `"clock_stability": "UNVERIFIED"` into every row of the run and have the renderer print that word next to every latency number it emits.
12. Detect background load: sample load average before and after each cell; if `loadavg_1m` before the cell exceeds `0.2 * ncpu`, mark the cell `"contended": true`. Contended cells are excluded from latency aggregates and counted in the run summary.
13. Time with `time.monotonic_ns()` and `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)`. Record both wall and CPU. Never use `datetime.now()` for measurement.
14. Memory: peak RSS via `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` plus a 50 ms sampler recording the max of `/proc/<pid>/status:VmHWM`. Report both; if they disagree by more than 10 percent, flag the cell.

48.5 HARDWARE AND TOOLCHAIN RECORD

Write `hardware.json` once per run and hash it into the run id.

```json
{
  "captured_at_utc": "2026-03-04T11:22:09Z",
  "cpu": { "model": "AMD Ryzen 7 5800H", "cores_physical": 8, "cores_logical": 16,
           "base_mhz": 3200, "governor": "performance", "turbo_disabled": true,
           "cpuset_pinned": "2-9", "flags_subset": ["avx2","bmi2","sha_ni"] },
  "memory": { "total_mb": 32768, "swap_mb": 0, "thp": "madvise" },
  "storage": { "device": "nvme0n1", "fs": "ext4", "rotational": false },
  "os": { "kernel": "6.8.0-40-generic", "container_runtime": "docker 26.1.4" },
  "toolchain": { "python": "3.12.5", "rustc": "1.79.0", "go": "1.22.5",
                 "cargo_lock_hash": "blake3:8c21...", "uv_lock_hash": "blake3:f0ab...",
                 "go_sum_hash": "blake3:1d77..." },
  "image_digest": "sha256:9ab3...",
  "clock_stability": "VERIFIED"
}
```

15. Hardware records are descriptive, never normative. Do NOT write "SPECTRA processes 1.2M events/sec" anywhere. Write "1.2M events/sec on the hardware recorded in `hardware.json` of run `<run_id>`".

48.6 RESULTS SCHEMA (OUTPUT)

The normative schema lives in `bench/runner/schema.py` as Pydantic v2 models and is exported to `bench/schema/results.schema.json` by `make schema`. CI fails if the exported file is stale.

Row granularity: one row per (scenario, arm, seed, operator, completeness, repeat).

```json
{
  "run_id": "blake3:2f7c9a1b...",
  "row_id": "blake3:aa10...",
  "manifest_id": "full-v3", "manifest_hash": "blake3:44de...",
  "spectra_version": "0.4.2", "git_commit": "e91c4f0", "git_dirty": false,
  "scenario_id": "S07_oauth_token_theft", "arm": "spectra",
  "seed": 1003, "repeat": 2, "warmup": false, "contended": false,
  "operator": "delete_targeted", "completeness": 0.7,
  "dataset": { "events": 214883, "entities": 1841, "bundle_hash": "blake3:7b21...",
               "ground_truth_hash": "blake3:0c55..." },
  "detection": { "tp": 14, "fp": 3, "fn": 2, "tn": 214864,
                 "alerts": 17, "detection_latency_s": 412.0,
                 "detection_latency_events": 9331 },
  "reconstruction": { "transition_accuracy": 0.918,
                      "path_edit_distance": 3, "path_len_truth": 11,
                      "path_accuracy": 0.727, "evidence_coverage": 0.864,
                      "evidence_precision": 0.941 },
  "eclipse": { "verdict": "ROBUST", "cut": ["session_binding>=2","egress_seg>=1"],
               "cut_size": 2, "lower_bound": 2, "corridors_min": 6, "corridors_max": 9,
               "blindness_premium": ["credential_rotation>=1"],
               "licenses_used": 3, "silent_instances": 41, "instances_total": 2104,
               "decisive_obs_set_size": 1, "redundancy_index_max": 0.42,
               "block_point_exact": true, "block_point_jaccard": 1.0,
               "flags": { "grounding_capped": false, "subset_minimal_only": false,
                          "greedy_cover": false },
               "cert_hash": "blake3:3f9a...",
               "checker": { "ok": true, "ms": 11, "instances_checked": 2104 } },
  "perf": { "wall_ms": 8421, "cpu_ms": 30118, "peak_rss_mb": 1477,
            "stage_ms": { "ingest": 1204, "resolve": 902, "state": 1631,
                          "ground": 2255, "liveness": 188, "cut": 1990, "verify": 11 },
            "throughput_eps": 25517,
            "p50_query_ms": 4.1, "p95_query_ms": 18.7, "p99_query_ms": 41.2,
            "query_n": 2000 },
  "analyst": { "actions_to_truth": 6, "reached_truth": true },
  "status": "OK",
  "error": null
}
```

16. `status` is one of `OK`, `TIMEOUT`, `OOM`, `CRASH`, `MANIFEST_DRIFT`, `SKIPPED`. Failed cells are written as rows, never omitted. A run summary that hides failures is forbidden.
17. Nullability: any metric an arm cannot produce is `null`, never `0`, never imputed. `arm_rules` has `reconstruction: null` and `eclipse: null`; the renderer prints `n/a` and the reason.
18. Write `results.jsonl` incrementally (crash-safe, one row per line, fsync per row), then convert to `results.parquet` at the end. Parquet column types are fixed by this DuckDB DDL, which `make schema` emits and CI diffs:

```sql
CREATE TABLE results (
  run_id            VARCHAR NOT NULL,
  row_id            VARCHAR NOT NULL,
  manifest_id       VARCHAR NOT NULL,
  scenario_id       VARCHAR NOT NULL,
  arm               VARCHAR NOT NULL,   -- rules|seqanom|spectra|graphonly
  seed              INTEGER NOT NULL,
  repeat            SMALLINT NOT NULL,
  warmup            BOOLEAN NOT NULL,
  contended         BOOLEAN NOT NULL,
  operator          VARCHAR NOT NULL,
  completeness      DOUBLE  NOT NULL,
  events            BIGINT  NOT NULL,
  tp INTEGER, fp INTEGER, fn INTEGER, tn BIGINT,
  detection_latency_s DOUBLE,
  transition_accuracy DOUBLE,
  path_edit_distance  INTEGER,
  path_len_truth      INTEGER,
  evidence_coverage   DOUBLE,
  eclipse_verdict     VARCHAR,          -- ROBUST|OPTIMISTIC_ONLY|UNSAFE|null
  cut_size            INTEGER,
  lower_bound         INTEGER,
  corridors_min       INTEGER,
  corridors_max       INTEGER,
  blindness_premium_n INTEGER,
  decisive_obs_size   INTEGER,
  flag_capped         BOOLEAN,
  flag_subset_only    BOOLEAN,
  flag_greedy         BOOLEAN,
  checker_ok          BOOLEAN,
  checker_ms          INTEGER,
  wall_ms BIGINT, cpu_ms BIGINT, peak_rss_mb INTEGER,
  p50_query_ms DOUBLE, p95_query_ms DOUBLE, p99_query_ms DOUBLE,
  actions_to_truth INTEGER,
  status VARCHAR NOT NULL,
  PRIMARY KEY (run_id, row_id)
);
```

48.7 RESULTS DIRECTORY CONVENTION

19. `run_id = blake3(manifest_hash || git_commit || image_digest || hardware_hash || sorted(seeds))`, truncated to 12 hex chars for the path. Identical inputs on identical hardware produce an identical `run_id`, and re-running must produce byte-identical `results.jsonl` modulo the `perf` block. Enforce this with `make benchmark-determinism`, which runs `quick.json` twice and diffs everything except `perf` and `hardware.captured_at_utc`.

```
bench/results/
├── INDEX.json                       # committed; append-only list of published runs
└── 2f7c9a1b0e44/
    ├── manifest.json                # frozen copy of the input
    ├── hardware.json
    ├── env.json                     # scrubbed environment actually used
    ├── results.jsonl                # raw rows, one per line
    ├── results.parquet              # typed, for analysis
    ├── summary.json                 # aggregates + CIs, produced by stats.R
    ├── certs/<scenario>/<seed>/<cell>.json   # every ECLIPSE certificate emitted
    ├── figures/*.pdf *.svg
    ├── logs/<cell_id>.log
    └── RUN.lock                     # removed on successful publish
```

20. A directory containing `RUN.lock` is an incomplete run. The renderer refuses to read it. `INDEX.json` gains an entry only after the lock is removed.
21. Certificates are results. Persist every one. The degradation invariant in section 50 is checked by re-running the Go checker over `certs/` offline.

48.8 THE GENERATED-NUMBERS RULE

22. No human types a number into `README.md`, `RESULTS.md`, `docs/research.md`, the UI, or any slide. Every number is rendered from `results.parquet` by `scripts/render_numbers.py`.
23. Generated regions are delimited and machine-owned:

```markdown
<!-- BEGIN GENERATED: table=arm_comparison run=2f7c9a1b0e44 -->
...machine output...
<!-- END GENERATED -->
```

24. Implement `scripts/check_generated.py` and wire it into CI and a pre-commit hook. It fails if: text inside a GENERATED region differs from a fresh render; a numeric literal matching `\d+(\.\d+)?\s*(%|ms|s|x|eps|MB|GB)?` appears outside a GENERATED region in any of the mandated documents, except in a `codeblock`, a version string, or a line ending with `<!-- static: <reason> -->`; a GENERATED region references a `run_id` absent from `INDEX.json`.
25. The renderer refuses to emit a scalar that lacks `n` and a confidence interval (see section 49). If asked for a single-seed value it emits `n=1 (NOT REPORTABLE)` and CI fails.
26. Negative requirements, absolute: do NOT round numbers upward for presentation. Do NOT copy a number from an older run into a newer document. Do NOT report a metric from a `contended`, `warmup`, `TIMEOUT`, `OOM` or `CRASH` row in any aggregate. Do NOT publish a run whose `checker_ok` is false for any `ROBUST` row. Do NOT write placeholder numbers "to be replaced later" — write the literal token `{{PENDING}}`, which CI treats as a build failure outside a draft branch.

48.9 CLI TRANSCRIPT (MUST MATCH IN SHAPE)

```
$ make benchmark MANIFEST=bench/manifests/full.json
[bench] manifest full-v3 valid (blake3:44de...)  scenarios=12 arms=4 seeds=10
[bench] image spectra-bench@sha256:9ab3...  cpuset=2-9  turbo=off  governor=performance
[bench] run_id=2f7c9a1b0e44  cells=4224 (warmups 768)  est. wall 6h12m
[bench] 0001/4224 S07 arm=spectra op=none c=1.00 seed=1001 rep=w0 ... OK   8.4s (warmup)
...
[bench] 4224/4224 S12 arm=graphonly op=silence c=0.30 seed=1010 rep=4 ... OK 5.1s
[bench] failures: 0 TIMEOUT, 0 OOM, 2 CRASH (S11/seqanom/backdate) -> rows written
[bench] contended cells: 3 (excluded from latency aggregates)
[bench] certificates: 1408 emitted, 1408 re-verified by go checker, 0 invalid
[bench] INVARIANT zero-false-ROBUST: PASS (0/1408 violations)
[bench] parquet written: bench/results/2f7c9a1b0e44/results.parquet (4224 rows)
[stats] bootstrap BCa 10000 resamples ... summary.json written
[figs]  R: 6 figures  julia: 3 figures  octave: 2 figures
[docs]  rendered 4 regions in RESULTS.md, 9 in docs/research.md, 3 in README.md
[bench] published. lock removed. INDEX.json updated.
```

============================================================
49. BASELINES AND METRICS
============================================================

49.1 COMPARISON ARMS

Implement exactly these arms. Each is a separate module with one entry point `run(bundle, config, seed) -> ArmOutput`. No arm may import another arm.

| Arm id | Name | What it is | Implementation |
|---|---|---|---|
| `rules` | Independent event rules | Stateless per-event and per-window predicates over the same bundle. The strawman that treats telemetry as independent events. | Python, ~40 hand-written rules mirroring common detection content, authored before seeing results, frozen by hash |
| `seqanom` | Sequence anomaly detection | Per-entity event-type sequence model: order-2 Markov surprisal plus a small autoencoder over sliding windows. The ML baseline. | Python + PyTorch (CPU), trained only on benign prefix of the same scenario |
| `spectra` | SPECTRA state reconstruction | Full pipeline: entity resolution, state transitions, temporal/causal graph, ECLIPSE kernel, certificate | Python + Rust kernel + Go checker |
| `graphonly` | Graph-only ablation | SPECTRA through the causal graph, then a hand-tuned path-scoring heuristic. ECLIPSE disabled: no licenses, no cut, no certificate. | SPECTRA code paths with `--no-eclipse` |

Optional fifth arm, build it and report it because it isolates the flagship mechanism:

| `spectra_nolic` | SPECTRA without silent envelopes | Full SPECTRA, `P_max = P_min` (licenses forced empty). Isolates the contribution of HF-CRC licensing to degradation robustness. |

1. Do NOT add an "LLM baseline". The LLM never participates in any measured arm. If narration is exercised at all, it is timed separately and labelled a presentation cost.
2. Do NOT tune `rules` or `seqanom` worse than you tune SPECTRA. Record tuning budget per arm in `bench/arms/TUNING.md`: hours spent, hyperparameters searched, and the search grid. If SPECTRA received more tuning, say so in the threats-to-validity section (51).

49.2 FAIRNESS CONTRACT

Write `bench/arms/FAIRNESS.md` and enforce it in code: the runner constructs each arm's input by a **projection function** from the same bundle and asserts no arm reads anything outside its projection. Violations abort the cell.

| Input | `rules` | `seqanom` | `graphonly` | `spectra` |
|---|---|---|---|---|
| Raw event stream (identical bytes, identical order after perturbation) | yes | yes | yes | yes |
| Entity resolution output | no | no | yes | yes |
| Rule table `rules.toml` | mirrored ruleset, same coverage target | no | yes | yes |
| Control catalog `controls.toml` | no | no | yes | yes |
| Liveness / blind-window computation | no | no | no | yes |
| Ground truth | never | benign-prefix labels only, for training cutoff | never | never |
| Scenario identity | never | never | never | never |
| Per-scenario threshold tuning | forbidden, one global threshold | forbidden, one global threshold | forbidden | forbidden |

3. Thresholds for `rules` and `seqanom` are selected once, on a held-out tuning scenario set (`S90..S94`) disjoint from the evaluation set, at the operating point maximizing F1, and then frozen with a hash. Re-selecting per cell is cheating and must be impossible by construction: the threshold is loaded from a signed file, not computed at run time.
4. Every arm sees the perturbed bundle, never the pristine one. The perturbation is applied once per cell and the resulting `bundle_hash` is asserted equal across arms.
5. Every arm gets the same wall and memory budget. An arm that exceeds it records `TIMEOUT`/`OOM`, which counts against it; do NOT quietly raise the budget for one arm.

49.3 DETECTION METRICS

Define the unit of detection first, because every downstream number depends on it: a detection is an **(entity, transition-class, time-bucket)** triple, bucket width 60 s, matched against ground truth by exact triple equality. Nothing else counts as a match. No partial credit, no "close enough" windows.

```
TP = |D ∩ G|      D = detections emitted   G = ground-truth malicious triples
FP = |D \ G|      FN = |G \ D|
TN = N_triples - |D ∪ G|        N_triples = |entities| * |classes| * |buckets|

precision = TP / (TP + FP)                     undefined -> null when TP+FP = 0
recall    = TP / (TP + FN)
F1        = 2 * precision * recall / (precision + recall)
FPR       = FP / (FP + TN)
alerts_per_1k = 1000 * alerts / events         alerts = emitted alert objects, not triples
```

6. Report `FPR` and `alerts_per_1k` side by side always. `FPR` looks flattering because `TN` is enormous; `alerts_per_1k` is what an analyst experiences. Never publish one without the other.

49.4 DETECTION LATENCY — CLOCK DEFINITION

Three clocks exist. Name the clock every time you print a latency.

```
t_first_mal   logical timestamp of the first ground-truth malicious event in the bundle
t_detect_log  logical timestamp of the LAST event cited as evidence by the first
              correct detection (the earliest moment at which the detection was
              derivable from data)
t_detect_wall wall-clock moment the arm emitted that detection during the run

detection_latency_s       = t_detect_log - t_first_mal      # SCENARIO clock. PRIMARY.
detection_latency_events  = index(t_detect_log) - index(t_first_mal)
processing_latency_ms     = t_detect_wall - t_ingest_start  # HARNESS clock. secondary.
```

7. `detection_latency_s` is the primary and the only one quoted in a headline. It is hardware-independent and therefore comparable across machines. Report `processing_latency_ms` only alongside `hardware.json`.
8. If an arm never detects, latency is `null` and the row contributes to recall, not to the latency distribution. Do NOT impute the horizon. Do NOT compute a mean over detected-only rows without also printing the detection rate next to it.
9. Under reordering perturbations, `t_detect_log` uses the ground-truth logical timestamp, not the arrival order, so reordering degrades correctness rather than silently improving latency.

49.5 RECONSTRUCTION METRICS

**Transition accuracy.** Ground truth is the generator's state-transition log: a sequence of `(entity, dimension, from_state, to_state, t)` records.

```
transition_accuracy = |T_pred ∩ T_true| / |T_true|
transition_precision = |T_pred ∩ T_true| / |T_pred|
match: same entity, same dimension, same from/to, |t_pred - t_true| <= 60s
```
Report per dimension (identity, session, credential, privilege, process, network, api, service, resource, trust) as well as pooled. A pooled number that hides a dimension at 0.2 is a misleading number.

**Attack-path reconstruction accuracy.** Represent a chain as a token sequence, one token per step: `"<dimension>:<transition_class>:<entity_role>"`. Entity role is the generator's abstract role (`attacker_ip`, `victim_identity`, `svc_acct_1`), never a raw id, so the metric survives entity-resolution renaming.

```
d = Levenshtein(chain_pred, chain_true)          unit costs: ins=1, del=1, sub=1
path_accuracy = 1 - d / max(|chain_pred|, |chain_true|)     clipped to [0,1]
```
Report the raw `d` and both lengths in every row. Publish the distribution (violin), not only the mean. If `chain_pred` is empty, `path_accuracy = 0`, not `null`.

**Block-point identification accuracy.** The generator knows the true minimal set of controls that severs the chain, `B_true` (computed by the generator's own exhaustive search over the declared catalog, not by SPECTRA).

```
block_exact   = 1 if S_pred == B_true else 0
block_jaccard = |S_pred ∩ B_true| / |S_pred ∪ B_true|
block_superset= 1 if B_true ⊆ S_pred            # over-blocking, still safe
block_miss    = 1 if S_pred ⊄ ... and goal reachable under S_pred   # UNSAFE, the fatal case
```
`block_miss` on a row whose verdict is `ROBUST` is the invariant violation of section 50.7 and fails the build.

**Evidence coverage and precision.**
```
E_cited = set of EventIds appearing as leaves of the emitted derivation/certificate
E_true  = set of ground-truth malicious EventIds
evidence_coverage  = |E_cited ∩ E_true| / |E_true|
evidence_precision = |E_cited ∩ E_true| / |E_cited|
```
10. Silent (GHOST) instances have no EventIds and therefore cannot inflate `E_cited`. Assert this in a test: `|E_cited|` counted from a certificate must equal the number of non-silent leaves, exactly.

**Analyst-actions-to-truth.** Define a deterministic scripted analyst, `bench/analyst/policy.py`, identical across arms, no human in the loop:

```
Action set: OPEN_ALERT, EXPAND_ENTITY, EXPAND_TIME_WINDOW, PIVOT_EDGE,
            OPEN_EVIDENCE, TOGGLE_CONTROL, READ_CERT
Policy: greedy best-first over the arm's own ranking; at each step take the
        highest-ranked unexplored object; stop when the analyst's accumulated
        view contains (a) the true entry point and (b) B_true.
actions_to_truth = number of actions; capped at 50; reached_truth = false at cap.
```
11. The policy is written once, reviewed against all arms, and frozen by hash before any results are generated. Do NOT modify it after seeing results. If you must modify it, re-run every arm and say in section 51 that you did.

49.6 PERFORMANCE AND COST METRICS

```
throughput_eps = events / (wall_ms / 1000)          end-to-end, per cell
p50/p95/p99_query_ms : over >= 2000 replayed API queries drawn from a fixed,
                       seeded query log; report n with every percentile;
                       compute from the full sample, never from a pre-binned
                       histogram; use nearest-rank, and state that.
peak_rss_mb   : as defined in 48.4
cpu_s_per_1M  = 1e6 * cpu_ms / (1000 * events)
gb_s_per_1M   = 1e6 * (peak_rss_mb/1024) * (wall_ms/1000) / events
cost_per_1M   = cpu_s_per_1M * rate_cpu_s + gb_s_per_1M * rate_gb_s
```
12. `rate_cpu_s` and `rate_gb_s` come from `bench/rates.toml`, which is **user-authored** and hashed into the results. SPECTRA never invents a price. If `rates.toml` is absent, `cost_per_1M` is `null` and the renderer prints "no rate file declared". This mirrors the ECLIPSE rule that costs are input, never generated.
13. Also report ECLIPSE-specific costs as first-class: `instances_total`, `corridors_min`, `corridors_max`, `cut_solver_ms`, `checker_ms`, `cert_bytes`. Publish measured grounding sizes; never claim a size bound you did not measure.

49.7 UNCERTAINTY AND STATISTICAL REPORTING

14. Minimum `n = 10` seeds per reported cell. A claim resting on fewer is not publishable; the renderer emits `NOT REPORTABLE`.
15. Confidence intervals: BCa bootstrap, 10 000 resamples, seeded from the run id, implemented in `bench/analysis/R/bootstrap.R`. Report 95 percent CIs for every mean, every proportion, and every ratio. Proportions additionally get a Wilson interval; if Wilson and BCa disagree materially, print both.
16. Arm comparisons are **paired on seed and scenario**. Use the paired difference distribution. Report the median paired difference with its BCa CI and a Wilcoxon signed-rank p-value, plus Cliff's delta as effect size. Never compare unpaired means across arms.
17. Multiple comparisons: Holm-Bonferroni across the family of arm-vs-arm tests within each metric. State the family size.
18. Forbidden, and enforced by `scripts/check_generated.py`: any sentence of the form "X is faster/more accurate than Y" that is not backed by a paired test row in `summary.json`; any mean without n and CI; any percentage without a denominator; any "up to" figure; any number derived from a single run or single seed; any statistic computed over a mixture of `OK` and failed rows.
19. Rendered table shape (machine-filled, this is the template):

```
| metric | rules | seqanom | graphonly | spectra | spectra-rules Δ (95% CI) | p (Holm) | δ |
|---|---|---|---|---|---|---|---|
| F1 @ 100% | 0.41 [0.36,0.46] | 0.29 [0.24,0.35] | 0.72 [0.68,0.76] | 0.88 [0.85,0.91] | +0.47 [+0.41,+0.52] | 0.0004 | 0.91 |
```
(the numerals above are illustrative of shape only and must never be copied into a document.)

============================================================
50. THE DEGRADATION AND TAMPERING EXPERIMENTS
============================================================

50.1 DESIGN

1. The experimental unit is a cell: `(scenario, arm, seed, operator, completeness, repeat)`. The full matrix is `12 scenarios x 5 arms x 10 seeds x 11 operators x 8 completeness levels x 5 repeats`, minus operator/completeness combinations excluded below. Publish the exact executed cell count; do not describe the matrix as "comprehensive".
2. `completeness` applies to operators that remove or hide data (`delete_random`, `delete_targeted`, `silence`). For shape-preserving operators (`reorder`, `duplicate`, `delay_jitter`, `corrupt_field`, `strip_identity`, `backdate`, `forge_provenance`) sweep the operator's own intensity knob instead and record `completeness = 1.0`.
3. Every operator is a pure function `apply(bundle, seed, intensity) -> (bundle', truth_delta)`. It must be deterministic given the seed, idempotent in its own hash, and must emit `truth_delta` recording exactly which ground-truth events it touched so the ground truth stays exact rather than approximate.
4. Operators compose. Composition order is part of the cell id. Run the singles for the main matrix; run a small declared set of pairs (`delete_targeted+backdate`, `silence+forge_provenance`, `reorder+duplicate`) as the adversarial-combination study.

50.2 OPERATOR CATALOG

| id | Definition | Intensity knob | What it attacks | Measured outcome | Expected curve |
|---|---|---|---|---|---|
| `none` | identity | — | — | reference row for all deltas | flat |
| `delete_random` | drop each event independently with prob `1-c` | `c` in {1.0 .. 0.3} | volume | recall, path_accuracy, evidence_coverage, corridors_max, blindness_premium | smooth monotone decline; SPECTRA's knee later than `rules` |
| `delete_targeted` | adversary with ground-truth knowledge deletes events in order of their leverage: first events that are sole evidence for a rule instance on the true corridor, then bridge events between dimensions, until budget `1-c` of the malicious set is spent; benign events untouched | `c` | evidence minimality | recall, block_miss, verdict distribution, licenses_used | step/cliff; a small deletion budget causes a large drop; SPECTRA should convert drop into `OPTIMISTIC_ONLY`/`UNSAFE`, not into a wrong `ROBUST` |
| `reorder` | permute within a sliding window of `w` seconds, preserving logical timestamps only for a fraction `1-r` of records | `w` in {1,5,30,300}s | arrival-order assumptions | transition_accuracy, detection_latency_s, `rules` FP rate | `rules`/`seqanom` degrade quickly; SPECTRA near flat because state reconstruction is timestamp-ordered, not arrival-ordered — prove it, do not assert it |
| `duplicate` | replay a fraction `d` of records 2..k times with fresh ingest ids | `d` in {0.01..0.25} | idempotence | alerts_per_1k, FP, instances_total | `rules` alert inflation roughly linear in `d`; SPECTRA flat if dedup by content hash works; any SPECTRA rise is a bug, file it |
| `delay_jitter` | add `Exp(λ)` arrival delay per source, plus per-source constant skew; logical timestamps unchanged | mean delay {1s,10s,60s,600s} | liveness q99 estimation | fraction of windows classed BLIND, licenses_used, blindness_premium size | BLIND fraction rises with delay; the premium rises with it; must not produce false ROBUST |
| `corrupt_field` | flip a fraction `f` of non-key fields to type-valid but wrong values | `f` in {0.001..0.1} | parsing and guards | transition_accuracy, schema-reject rate | graceful: rejected records counted, never silently coerced |
| `strip_identity` | null out the identity/principal field on a fraction `s` of records | `s` in {0.05..0.5} | entity resolution | entity-resolution F1, path_accuracy, corridor count | ER F1 declines; SPECTRA must report reduced confidence via more corridors, not fewer |
| `backdate` | rewrite timestamps of chosen malicious records to earlier values, consistent within a source but inconsistent across sources | fraction `b`, shift distribution | the license logic | count of licenses voided by the Bellman-Ford difference-constraint pass; false-license rate | voided-license count rises with `b`; an unvoided backdated license that enables a `ROBUST` verdict is a fatal violation |
| `forge_provenance` | rewrite BLAKE3 sequence-chain links so a deletion looks like a clean chain | fraction `p` of chains forged | SUPPRESSED detection | chain-break detection rate, misclassification BLIND vs SUPPRESSED vs LIVE | detection rate high for naive forgery; document explicitly the forgery class SPECTRA cannot detect, and show it produces `UNSAFE`/`OPTIMISTIC_ONLY`, never a confident `ROBUST` |
| `silence` | a whole collector emits nothing for interval `[t0,t1]`, no gap marker | silent fraction of horizon {5%..60%} | blind envelopes | BLIND window volume, silent_instances, decisive_obs_set_size, blindness_premium | premium grows with silence; `decisive_obs_set_size` should stay small (1-3) and its members should name the silenced collector |

50.3 ADVERSARIAL DELETION IS THE HEADLINE

5. `delete_random` is the easy case and it will flatter every arm. `delete_targeted` is the honest case. Present them adjacent, at the same scale, in every figure and table. Never report `delete_random` alone.
6. The targeted adversary is given ground truth, which is strictly stronger than a real attacker. State that this is an upper bound on adversary capability, and that results under it are conservative.
7. For `delete_targeted`, additionally report the **certificate outcome distribution** per completeness level:

```
c=1.0  ROBUST 118 | OPTIMISTIC_ONLY  2 | UNSAFE  0 | flagged 0
c=0.7  ROBUST  71 | OPTIMISTIC_ONLY 44 | UNSAFE  5 | flagged 3
c=0.3  ROBUST   9 | OPTIMISTIC_ONLY 61 | UNSAFE 50 | flagged 22
```
The shape that validates the design is ROBUST mass migrating into OPTIMISTIC_ONLY and UNSAFE as data disappears. ROBUST mass that survives while `block_miss` rises is the failure mode the invariant exists to catch.

50.4 THE BLINDNESS PREMIUM CURVE

8. For every degradation cell, record `S_opt` (on `P_min`), `S_rob` (on `P_max`), and `premium = S_rob \ S_opt` with, for each premium member, the license ids responsible. Plot `|premium|` against completeness and against silence fraction. The expected shape is monotone non-decreasing in blindness. A premium that shrinks as blindness grows indicates a licensing bug; assert monotonicity as a property test over a synthetic lattice of liveness inputs and fail the build on violation.
9. Record `decisive_obs_set_size` and whether `greedy_cover` was flagged. Report the fraction of cells resolved by exact search (size <= 3) versus greedy, and never present a greedy-flagged cell as exact.

50.5 ABLATION TABLE (MACHINE-FILLED)

```
<!-- BEGIN GENERATED: table=ablation run=<run_id> -->
| configuration                         | F1 @1.0 | F1 @0.5 | path_acc @0.5 | block_jaccard @0.5 | false ROBUST | median premium |
|---------------------------------------|---------|---------|---------------|--------------------|--------------|----------------|
| SPECTRA full                          |         |         |               |                    | 0            |                |
| − ECLIPSE (graph-only heuristic)      |         |         |               |                    | n/a          | n/a            |
| − silent envelopes (P_max = P_min)    |         |         |               |                    |              |                |
| − liveness (all sources assumed LIVE) |         |         |               |                    |              |                |
| − obligation axioms                   |         |         |               |                    |              |                |
| − backdating check (no Bellman-Ford)  |         |         |               |                    |              |                |
| − entity resolution (raw ids)         |         |         |               |                    |              |                |
| − two-sided cut (S_opt only)          |         |         |               |                    |              |                |
| sequence anomaly baseline             |         |         |               |                    | n/a          | n/a            |
| independent event rules baseline      |         |         |               |                    | n/a          | n/a            |
<!-- END GENERATED -->
```
10. Each ablation is a real code path toggled by a flag, exercised by the same harness, not an estimate. The `− liveness` and `− backdating` rows are expected to produce nonzero false-ROBUST counts; that nonzero value is the evidence that those components are load-bearing. Report it.

50.6 PLOTS

Produce these from `results.parquet`. Language assignment is fixed so each language has a real job: R owns statistics and CIs, Julia owns the 2-D degradation surfaces, Octave owns matrix heatmaps.

| id | file | producer | content |
|---|---|---|---|
| P1 | `completeness_vs_quality.pdf` | R/ggplot2 | recall, F1, path_accuracy vs completeness; one facet per arm; ribbons are BCa CIs; `delete_random` solid, `delete_targeted` dashed |
| P2 | `robust_safety.pdf` | R | false-ROBUST count vs completeness. Must be a flat line at zero across the whole matrix. Annotate n. |
| P3 | `verdict_migration.pdf` | R | stacked area of ROBUST / OPTIMISTIC_ONLY / UNSAFE / flagged vs completeness |
| P4 | `blindness_premium_surface.pdf` | Julia/Makie | surface of median `|premium|` over (completeness x silence fraction) |
| P5 | `corridor_growth.pdf` | Julia | corridors_min and corridors_max vs completeness, log y, with measured grounding caps marked |
| P6 | `tamper_matrix.pdf` | Octave | heatmap, rows = operators, cols = arms, cell = median ΔF1 from `none`, diverging palette centered at 0 |
| P7 | `dimension_heatmap.pdf` | Octave | heatmap of transition_accuracy by state dimension x completeness |
| P8 | `latency_cdf.pdf` | R | CDF of detection_latency_s per arm at c=1.0 and c=0.6, with detection-rate annotation |
| P9 | `path_edit_violin.pdf` | R | distribution of Levenshtein distance per arm |
| P10 | `pareto_frontier.pdf` | Julia | declared cost vs residual reachability Pareto points from the knapsack stage, one series per scenario |
| P11 | `analyst_actions.pdf` | R | actions_to_truth ECDF per arm, censored at the cap, censoring shown |
| P12 | `checker_cost.pdf` | R | checker_ms vs instances_total, with a fitted line and the fit's R² stated |

11. Every figure carries a footer stamp rendered from data: `run_id`, `n` seeds, manifest id, commit, and the words `synthetic data`. A figure without the stamp fails `make figures`.
12. Do NOT smooth curves. Do NOT use a spline through few points. Plot the points and the CI ribbon. Do NOT truncate an axis to exaggerate a gap. Axis ranges are set by data, and any manual range is annotated in the caption.

50.7 THE INVARIANT

13. Across the entire executed matrix, the count of rows with `eclipse_verdict = ROBUST` and `block_miss = 1` must be exactly zero. This is a build gate, not a metric. If it is ever nonzero: stop, do not publish, write the counterexample cell to `bench/results/<run_id>/VIOLATIONS.json` with the bundle hash, seed, operator and certificate, add it as a regression fixture, and fix the kernel.
14. A row with any flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) may never carry verdict `ROBUST`. Assert it in the runner, in the Rust kernel, and in the Go checker independently. Three independent assertions, because this is the one claim the whole artifact rests on.
15. Also assert: `cut_size >= lower_bound`; `corridors_min <= corridors_max`; `Reach(P_min) ⊆ Reach(P_max)` sampled per cell; `checker_ok = true` for every non-CRASH row; and certificate re-verification offline from `certs/` reproduces the same verdict byte-for-byte.

============================================================
51. RESEARCH ARTIFACT
============================================================

51.1 docs/research.md — MANDATED STRUCTURE

Write `docs/research.md` as a paper, not a feature tour. Use exactly these sections, in this order, with these numbers. Each `<!-- BEGIN GENERATED -->` region is filled by `scripts/render_numbers.py`.

```
 1. Abstract                       (<= 250 words; every number generated)
 2. Problem statement              (state-centric vs event-centric; what breaks)
 3. Research questions and hypotheses (RQ1..RQ5, each falsifiable, stated with
                                    the prediction that would refute it)
 4. Related work and delta         (detection engineering, provenance/audit graphs,
                                    attack graphs and minimal cuts, abduction under
                                    incomplete observation, diagnosis/hitting sets;
                                    a table of what each does and does not give)
 5. Threat model and scope         (non-adaptive attacker; declared catalog; what
                                    "prevention" means here)
 6. System model                   (security state dimensions; transitions; entity
                                    resolution; see sections 17-24)
 7. ECLIPSE formalism              (Horn program, licenses, two-sided cut, the two
                                    fixpoints, certificate grammar, checker; see
                                    sections 30-36)
 8. Soundness argument             (what is proved, over which objects, with the
                                    exact quantifier; and what is not proved)
 9. Implementation                 (components, languages and why, LOC table
                                    generated by tokei, pinned versions)
10. Experimental design            (arms, fairness contract, metrics, matrix;
                                    see sections 48-50)
11. Results                        (all generated; RQ-by-RQ)
12. Ablations                      (the section 50.5 table plus reading)
13. Degradation and tampering      (the section 50 curves plus reading)
14. Negative results and failures  (mandatory, non-empty)
15. Threats to validity            (structure fixed in 51.4)
16. Limitations and what ECLIPSE never claims (restate section 9 of the spec verbatim)
17. Reproduction protocol          (51.3)
18. Artifact availability          (what is in the repo, sizes, hashes)
19. Ethics and safety              (synthetic only, no real targets, no malware)
20. References
```

1. Section 14 must be non-empty. Every real system has negative results. If the first full run produces none, you have not looked hard enough or your matrix is too easy; widen the matrix.
2. Do NOT write a section about how impressive the system is. Do NOT include screenshots in place of measurements. Do NOT cite a number that is not in `results.parquet`.

51.2 RESULTS TABLE TEMPLATE (MACHINE-FILLED)

Section 11 of `docs/research.md` contains exactly this skeleton; the renderer fills it.

```markdown
<!-- BEGIN GENERATED: table=rq_summary run={{RUN_ID}} -->
Run `{{RUN_ID}}` · manifest `{{MANIFEST_ID}}` · commit `{{COMMIT}}` · {{N_SEEDS}} seeds ·
{{N_CELLS}} cells ({{N_FAILED}} failed) · hardware `{{HW_HASH}}` · synthetic data.

| RQ | Claim under test | Metric | Result (95% CI) | n | Paired p (Holm) | Supported |
|----|------------------|--------|-----------------|---|-----------------|-----------|
| RQ1 | State reconstruction beats independent-event rules on chain recovery | path_accuracy @c=1.0, spectra − rules | {{RQ1_DELTA}} | {{RQ1_N}} | {{RQ1_P}} | {{RQ1_VERDICT}} |
| RQ2 | SPECTRA identifies the true block point | block_jaccard @c=1.0 | {{RQ2_VAL}} | {{RQ2_N}} | — | {{RQ2_VERDICT}} |
| RQ3 | Certificates are never falsely ROBUST under degradation | false-ROBUST count over full matrix | {{RQ3_VAL}} | {{RQ3_N}} | — | {{RQ3_VERDICT}} |
| RQ4 | Licensing degrades gracefully vs. no-license ablation | ΔF1 @c=0.5, spectra − spectra_nolic | {{RQ4_DELTA}} | {{RQ4_N}} | {{RQ4_P}} | {{RQ4_VERDICT}} |
| RQ5 | Verification is cheap relative to solving | checker_ms / cut_solver_ms, median | {{RQ5_VAL}} | {{RQ5_N}} | — | {{RQ5_VERDICT}} |
<!-- END GENERATED -->
```

3. `{{RQ*_VERDICT}}` is rendered from a rule in code, not by a human: `SUPPORTED` if the CI excludes the null in the predicted direction after Holm correction; `NOT SUPPORTED` if it excludes it in the opposite direction; `INCONCLUSIVE` otherwise. The renderer has no branch that prints anything else.

51.3 REPRODUCTION PROTOCOL

Section 17 of `docs/research.md` is exactly this, and `make reproduce` executes it end to end.

```bash
# 0. Prerequisites: Docker >= 24, 16 GB RAM, 40 GB free disk, no network needed
#    after the first build. Verified on Linux x86-64; other platforms untested.
git clone <repo> spectra && cd spectra
git checkout v0.4.2                      # or the commit in RESULTS.md

# 1. Build the pinned image                       ~12 min first time, cached after
make image                                # -> spectra-bench@sha256:...

# 2. Verify the toolchain fingerprint matches the paper's
make hardware-report                      # prints hardware.json; expect differences,
                                          # they are recorded, not required to match

# 3. Smoke test: 3 scenarios, 3 seeds, no degradation   ~4 min
make benchmark-quick
#    expected: 0 failures, 0 false-ROBUST, all certificates verified

# 4. Determinism check                                   ~8 min
make benchmark-determinism
#    expected: byte-identical results.jsonl modulo the perf block

# 5. Full matrix                                         ~6 h 15 m on the reference
#    hardware; scales roughly linearly with core count
make benchmark MANIFEST=bench/manifests/full.json

# 6. Statistics, figures, documents
make stats && make figures && make docs

# 7. Independent verification of every certificate, Go checker, no Rust involved
make verify-certs RUN=<run_id>            # ~90 s for ~1400 certificates
```

Expected artifacts after step 6:

```
bench/results/<run_id>/results.parquet     ~ 30 MB
bench/results/<run_id>/summary.json        ~ 400 KB
bench/results/<run_id>/certs/              ~ 1400 files, ~ 60 MB
bench/results/<run_id>/figures/            12 PDFs + 12 SVGs
RESULTS.md                                 regenerated
docs/research.md                           generated regions refreshed
```

4. State the reference hardware once, in `hardware.json`, and say plainly that runtimes elsewhere will differ. Do NOT promise a runtime you have not measured on the machine you are describing.
5. `make reproduce` must succeed on a machine with no network after `make image`. If any step needs the network, it is broken; fix it.

51.4 THREATS TO VALIDITY

Write section 15 with these five subsections, each with concrete named threats and the mitigation actually implemented:

6. **Construct validity.** The metrics may not measure security value. The 60-second bucket matching is a choice; report sensitivity to bucket width {30,60,300}s. `actions_to_truth` uses a scripted analyst that no real analyst resembles.
7. **Internal validity.** Ground truth is generator-declared, so SPECTRA and the generator share a world model; a rule table and a generator authored by the same person can agree by construction. Mitigation: the rule table is written against source schemas, not against scenario scripts; a held-out scenario set (`S80..S85`) is authored after the rule table is frozen, and its results are reported separately. State whether held-out performance dropped. It probably did; that is the finding.
8. **External validity.** All telemetry is synthetic. No claim transfers to production data. Volumes, entity cardinalities and noise distributions are declared in the manifest and are not calibrated against any real environment, because no real environment was available.
9. **Statistical validity.** Seeds are not independent across operators applied to the same base scenario; pairing handles the mean but not all dependence. Bootstrap assumes exchangeability across seeds. Family sizes for Holm correction are stated per metric.
10. **Attacker model validity.** The attacker is non-adaptive and does not observe the control configuration. A control cut that severs this attacker's chain says nothing about an attacker who adapts to the cut. Say this in the abstract, not only here.
11. Each subsection ends with a line of the form `Unmitigated: <list>`. An empty `Unmitigated:` line is not credible and CI rejects it.

51.5 HONESTY CLAUSE

Put this verbatim in `docs/research.md` section 1 and in `RESULTS.md`:

> This document reports what the code produced. Every number in it was generated by
> `scripts/render_numbers.py` from `bench/results/<run_id>/results.parquet` and can be
> regenerated with `make benchmark && make docs`. Where a hypothesis was not supported,
> the table says NOT SUPPORTED and the text explains it rather than removing it.
> Results are on synthetic telemetry produced by this repository's own generators,
> against this repository's own declared control catalog. ECLIPSE proves properties of
> the model, not of any real system.

12. Enforce it: if any RQ renders `NOT SUPPORTED`, `scripts/render_numbers.py` requires a corresponding non-empty prose block keyed `<!-- discussion: RQ<n> -->` in the source document and fails the build if it is missing. You may not quietly drop a failed hypothesis.
13. Forbidden edits: removing an RQ after seeing results; renaming a metric so an unfavourable comparison disappears; adding a post-hoc filter that excludes inconvenient scenarios; reporting the best of several runs. If a run is discarded, record why in `bench/results/INDEX.json` under `discarded[]` with a reason string; discarded runs are never deleted.

51.6 RESULTS.md

14. `RESULTS.md` at the repo root is fully machine-generated by `make benchmark` (its last step) and is 100 percent inside GENERATED regions except its title. Committing a hand-edited `RESULTS.md` fails CI.

```markdown
# SPECTRA Benchmark Results
<!-- BEGIN GENERATED: doc=results run={{RUN_ID}} -->
Generated {{UTC}} from run `{{RUN_ID}}` (commit `{{COMMIT}}`, manifest `{{MANIFEST_ID}}`).
Synthetic data. Hardware: {{CPU_MODEL}}, {{CORES}} cores, turbo {{TURBO}}.
Cells executed: {{N_CELLS}} ({{N_OK}} OK, {{N_TIMEOUT}} timeout, {{N_OOM}} oom, {{N_CRASH}} crash).
Certificates: {{N_CERTS}} emitted, {{N_VERIFIED}} independently verified, {{N_INVALID}} invalid.

## Gate status
| gate | value | required | status |
| zero false ROBUST | {{FALSE_ROBUST}} | 0 | {{GATE_1}} |
| flagged rows reported ROBUST | {{FLAGGED_ROBUST}} | 0 | {{GATE_2}} |
| simulator/kernel agreement | {{AGREE}}/{{AGREE_N}} | all | {{GATE_3}} |
| determinism (byte-identical replay) | {{DET}} | pass | {{GATE_4}} |

## Headline comparison
{{TABLE_ARM_COMPARISON}}

## Degradation
{{TABLE_DEGRADATION}}
{{FIGURE_LINKS}}

## Ablations
{{TABLE_ABLATION}}

## Cost
{{TABLE_COST}}   (rates from bench/rates.toml, hash {{RATES_HASH}}; user-declared)
<!-- END GENERATED -->
```

15. `README.md` quotes at most six numbers, each inside a GENERATED region, each linking to `RESULTS.md`. Do NOT put a benchmark table in the README.

51.7 CITATION.cff

Commit `CITATION.cff` at the repo root, validated by `cffconvert --validate` in CI.

```yaml
cff-version: 1.2.0
message: "If you use SPECTRA, please cite it as below."
title: "SPECTRA: Security State Reconstruction, Causal Analysis and Attack Replay"
abstract: >-
  SPECTRA reconstructs the evolving security state of a system from heterogeneous
  telemetry, builds a temporal and causal graph, and replays the identical scenario
  under alternative control configurations. Its proof kernel, ECLIPSE, emits a
  content-addressed certificate carrying a cardinality-minimal control cut, an
  inductive invariant checked by an independently implemented linear-time verifier,
  counterexample derivations, and the minimal additional log sources that would
  remove residual ambiguity. All evaluation uses synthetic telemetry generated by
  this repository.
type: software
authors:
  - given-names: "<AUTHOR_GIVEN>"
    family-names: "<AUTHOR_FAMILY>"
    orcid: "https://orcid.org/0000-0000-0000-0000"
repository-code: "https://github.com/<user>/spectra"
url: "https://github.com/<user>/spectra"
license: Apache-2.0
version: "0.4.2"
date-released: "2026-03-04"
keywords:
  - security state reconstruction
  - provenance
  - abduction under incomplete observation
  - minimal cut
  - certifying algorithms
  - telemetry degradation
identifiers:
  - type: other
    value: "blake3:<RESULTS_RUN_ID>"
    description: "Benchmark run id backing the reported results"
references:
  - type: data
    title: "SPECTRA synthetic scenario corpus (generated, seeded)"
    notes: "Reproduced by `make datasets`; not distributed as a binary artifact."
```

16. The `version` and `date-released` fields are updated by `make release`, not by hand. The `identifiers` entry pointing at the benchmark run id is mandatory: a citation that does not name the run backing its numbers is incomplete.
17. Do NOT claim a DOI you do not have. Do NOT list co-authors who did not contribute. Do NOT cite the repository as peer-reviewed work.
