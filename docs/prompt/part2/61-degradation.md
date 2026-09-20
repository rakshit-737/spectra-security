============================================================
61. TELEMETRY DEGRADATION AND TAMPERING MODEL
============================================================

61.0 SCOPE AND OVERRIDES

This section owns the second declared research axis in full. No other section may define a
perturbation operator, a completeness number, a matrix cell, or a ground-truth link.

OVERRIDES Part I: degradation is no longer an implementation detail smeared across the lab
sections (26-29) and the bench sections (48-51). The operator catalog, the seed discipline, the
completeness definition, the matrix harness and the ground-truth relinking are specified here and
are a versioned, hashed data artifact. Sections 26-29 may consume this catalog; they may not extend
it in code.

OVERRIDES Part I: the phrase "100%..30% completeness" as a single scalar is withdrawn everywhere in
the repository. It was undefined (share of records? of sources? per dimension?) and any aggregate
form of it is now forbidden output. See 61.6.

OVERRIDES Part I: generator ground truth may no longer be expressed over `EventId`s. Perturbation
rewrites, duplicates, reorders and deletes the exact records that carry them, so an `EventId`-keyed
ground truth is destroyed by the very experiment it is supposed to measure. Ground truth is keyed on
generator-side causal step identifiers that never enter telemetry. See 61.7.

OVERRIDES Part I: the Part I operator word "suppress" is ambiguous and is retired. It is replaced by
three distinct, separately parameterized, separately seeded operators: `DELETE`, `SOURCE-SILENCE`
and `STRIP-IDENTITY`.

Implement all of 61.1-61.13. The build fails on any requirement below whose gate is named and red.


61.1 PLACE IN THE PIPELINE

Perturbation is applied to serialized RAW SOURCE RECORDS, before parsing, before canonicalization,
before entity resolution, before `EventId` assignment. It is never applied to `bundle.jsonl`.

```
  generator (seed, scenario)
        |
        |-- truth/emission.jsonl      (StepId, RecordId, source, emit_time_ns)  [NEVER an ingest input]
        v
  raw/clean/<source>.log              (pristine raw records, byte-stable)
        |
        v
  +-------------------------------+
  |  PERTURBER  (this section)    |  plan.toml + root_seed + cell_id
  |  fixed operator order 61.4.0  |
  +-------------------------------+
        |-- raw/pert/<source>.log     (perturbed raw records; final emit order fixed here)
        |-- truth/ledger.jsonl        (one row per pre-perturbation RecordId + one row per synthetic line)
        v
  ingest + parser (Part I 9-12 contract)  --> per-record origin {source, line_index}
        |-- quarantine.jsonl          (reason-coded; NEVER a silent drop)
        v
  entity resolution --> bundle.jsonl  (EventId, origin{source,line_index})
        |
        v
  relinker (61.7) : ledger x origin  --> truth/anchor_map.json
        |
        v
  ECLIPSE kernel --> liveness.json, cert.json     --> Go checker --> checker.txt
        |
        v
  metrics (61.11) : cert x anchor_map x objective --> metrics.json
```

Hard rules:
- The perturber MUST NOT read entity-resolution output, `rules.toml`, `controls.toml`, `goal.toml`,
  or any kernel artifact. A build-graph gate (`make dep-audit`) fails if the perturber binary's
  dependency closure touches the kernel crate, the ER crate, or the rule table.
- `truth/` is never an input to the kernel, the checker, or the ingest pipeline. Gate: the kernel
  and checker run under a read-blocked mount of `truth/` in CI (`make truth-isolation`); any open()
  against it aborts the run and fails the build.
- The perturber is a pure function of (clean raw bytes, plan, root_seed, cell_id). Running it twice
  produces byte-identical `raw/pert/` and byte-identical `truth/ledger.jsonl`. Gate:
  `make matrix-determinism`.


61.2 THE PERTURBATION PLAN FILE

A plan is data, authored, hashed, and referenced by hash from every certificate-adjacent artifact.

```toml
# plans/p07-targeted-suppression.toml
plan_id       = "p07-targeted-suppression"
plan_version  = 3
description   = "Adversary deletes the minimum record set that hides credential reuse."

# Target retention per SOURCE. Realized retention is measured, not assumed (61.6).
[targets]
"iam_audit"       = 0.55   # (illustrative, not a target)
"proxy_access"    = 0.90   # (illustrative, not a target)
"host_proc"       = 1.00
"app_session"     = 0.70   # (illustrative, not a target)

[[operator]]
op            = "DELETE"
mode          = "TARGETED_ADVERSARIAL"
sources       = ["iam_audit", "app_session"]
objective_tag = "cred.reuse"      # steps whose witnesses the adversary prefers to remove
budget_frac   = 0.20              # (illustrative, not a target)
respect_obligations = true        # adversary avoids leaving unsatisfiable obligation pairs

[[operator]]
op            = "BACKDATE"
sources       = ["iam_audit"]
shift_ns      = -900_000_000_000  # (illustrative, not a target)
select_frac   = 0.05              # (illustrative, not a target)
monotone_repair = false           # if true, the whole source is re-sorted after shifting

[[operator]]
op            = "REORDER"
mode          = "CROSS_SOURCE"
window_ns     = 2_000_000_000     # (illustrative, not a target)
```

Schema (`schemas/degradation-plan.schema.json`, draft 2020-12) is committed. Lints, all
build-failing:
- `plan-lint-unknown-op`: every `op` value exists in `operators.toml` (61.4).
- `plan-lint-params`: every parameter is declared for that operator, typed, and in range.
- `plan-lint-floats`: probabilities and fractions are authored as decimal strings and converted to
  exact rationals (`num/den`, u32/u32) at load time. No IEEE float participates in any selection
  decision. This is a determinism-charter obligation, restated here because perturbation is the
  most float-tempting code in the repo.
- `plan-lint-sources`: every named source exists in `sources.toml` and declares a `chain_class`
  (61.5).


61.3 SEED STREAMS

Every operator instance draws from its own named stream. Adding, removing or reordering an operator
must not shift any other operator's draws.

```
stream_key   = "<plan_id>/<operator_index>/<op>/<stream_name>"
stream_seed  = BLAKE3_keyed(key = root_seed_32, data = utf8(cell_id || 0x1F || stream_key))
rng          = ChaCha20(stream_seed, counter = 0)
```

`root_seed_32` is 32 bytes, recorded in the run manifest and in `cell.json`. Named streams, one row
per operator (the registry in 61.4 is authoritative):

| op             | streams                                                   |
|----------------|-----------------------------------------------------------|
| DELETE         | `select`                                                  |
| DELAY          | `select`, `magnitude`                                     |
| DUPLICATE      | `select`, `multiplicity`, `placement`                     |
| REORDER        | `select`, `permutation`                                   |
| CORRUPT        | `select`, `field`, `value`                                |
| STRIP-IDENTITY | `select`, `field`                                         |
| BACKDATE       | `select`, `magnitude`                                     |
| CHAIN-FORGE    | `select`, `payload`                                       |
| SOURCE-SILENCE | `window`                                                  |

Selection discipline (mandatory, `make perturb-determinism` proves it): candidate records are
enumerated in a canonical total order — `(source_id_ascii_asc, emit_time_ns_asc, record_id_asc)` —
never in hash-map order, never in filesystem order. Random selection of `k` from `n` uses a seeded
Fisher-Yates over that canonical vector with integer arithmetic only.


61.4 OPERATOR CATALOG

The catalog is data: `perturb/operators.toml`, hashed into every cell identity. Each entry declares
`op`, `params` (name, type, range), `streams`, `fates` (which ledger fate variants it may emit),
`observability` (61.5), and `min_tests`. Lint `op-registry-complete`: adding a variant to the
perturber's operator enum without a registry row, a must-fire test and a must-not-fire test fails
the build.

61.4.0 Composition order. Operators compose in this fixed class order regardless of authoring order
in the plan; within a class, plan order applies:

```
1 SOURCE-SILENCE   2 DELETE      3 STRIP-IDENTITY   4 CORRUPT     5 BACKDATE
6 CHAIN-FORGE      7 DUPLICATE   8 DELAY            9 REORDER
```

Rationale, stated so it is not re-litigated: content mutation precedes fabrication, fabrication
precedes multiplicity, multiplicity precedes timing, timing precedes emit order. The final emit
order is fixed by step 9 and by nothing after it. The ledger is written after step 9.

61.4.1 DELETE — remove records.

| mode                  | params                                                        |
|-----------------------|---------------------------------------------------------------|
| UNIFORM_RANDOM        | `sources[]`, `drop_frac` (rational, 0<=f<=1)                   |
| TARGETED_ADVERSARIAL  | `sources[]`, `objective_tag`, `budget_frac`, `respect_obligations` |
| WHOLE_SOURCE_BLACKOUT | `sources[]`, `t0_ns`, `t1_ns` (simulated time)                 |

Semantics. UNIFORM_RANDOM: select `floor(drop_frac * n)` records from the canonical candidate vector
via the `select` stream; emit nothing for them; ledger fate `DELETED{mode}`.
TARGETED_ADVERSARIAL: rank candidate records by `witness_specificity(r)` = number of distinct
`StepId`s in the objective-tagged chain for which `r` is the ONLY surviving witness, descending, ties
broken by canonical order; delete greedily until `budget_frac * n` is spent. With
`respect_obligations = true`, a record is skipped if deleting it would leave an obligation pair
(e.g. `session.used` without `session.issued`) unsatisfiable on the same source — this models an
adversary who knows the obligation axioms; with `false`, it models one who does not. Both settings
MUST appear in the matrix. WHOLE_SOURCE_BLACKOUT: delete every record from `sources` with
`emit_time_ns in [t0_ns, t1_ns)`.

61.4.2 DELAY — move a record later in the delivered stream without changing its recorded timestamp.

| mode        | params                                                       |
|-------------|--------------------------------------------------------------|
| BOUNDED_JITTER | `sources[]`, `select_frac`, `max_ns`                      |
| HEAVY_TAIL     | `sources[]`, `select_frac`, `scale_ns`, `alpha_num/alpha_den` (Pareto, integer-sampled, truncated at `cap_ns`) |

Semantics. A delay changes `delivery_time_ns` only. The record's own timestamp fields are untouched
— this is the difference between DELAY and BACKDATE, and it is the whole point of having both. Delay
is expressed in SIMULATED nanoseconds. OVERRIDES Part I: no perturbation, harness step or gate may
sleep, poll, or consult a wall clock; a wall-clock-dependent delay would make matrix cells
machine-dependent and break byte-identical replay. Gate: `make no-wallclock` greps the perturber and
harness for clock APIs and fails on any hit outside an explicitly allowlisted logging path.
Heavy-tail sampling uses an integer inverse-CDF over a 2^32 quantile grid; no floating point.

61.4.3 DUPLICATE — re-emit a record.

Params: `sources[]`, `select_frac`, `mult_min`, `mult_max`, `placement` in {ADJACENT, WINDOWED(w_ns),
CROSS_SOURCE}, `byte_identical` (bool). With `byte_identical = false`, the copy differs in the
source's own sequence/serial field, which is the realistic at-least-once-delivery case.
Ledger: the original keeps `KEPT`; each copy gets its own line row with fate
`SYNTHETIC{parent_record_id, kind=DUPLICATE}`.

61.4.4 REORDER — permute delivered order.

| mode          | params                                  |
|---------------|------------------------------------------|
| WITHIN_WINDOW | `sources[]`, `window_ns`, `strength` (rational 0..1) |
| CROSS_SOURCE  | `window_ns`, `strength`                  |

Semantics. Partition the delivery sequence into windows of `window_ns`; inside each window apply a
seeded partial shuffle that performs `floor(strength * (m-1))` adjacent transpositions (`permutation`
stream). CROSS_SOURCE merges all sources into one delivery sequence before partitioning, so records
can cross source boundaries in delivery order. Timestamps are untouched.

61.4.5 CORRUPT — field-level, typed mutation.

Params: `sources[]`, `select_frac`, `fields[]` (dotted paths into the source's raw schema),
`strategy` per field type:

| field type | strategies                                                              |
|------------|-------------------------------------------------------------------------|
| string     | `TRUNCATE(n)`, `CASE_FOLD`, `CHAR_SWAP(k)`, `SUBSTITUTE_FROM_DOMAIN`     |
| integer    | `OFF_BY(k)`, `SATURATE`, `SIGN_FLIP`                                     |
| timestamp  | not permitted here — use BACKDATE (lint `corrupt-no-timestamp`)          |
| enum       | `SUBSTITUTE_FROM_DOMAIN` only                                            |
| structural | `DROP_FIELD`, `DUPLICATE_KEY`, `TRUNCATE_LINE`, `INVALID_UTF8`           |

`CORRUPT` MUST be able to produce records that the parser rejects. Those records MUST land in
`quarantine.jsonl` with a reason code, MUST appear in `anchor_map.json` as
`QUARANTINED{reason_code}`, and MUST NOT be silently dropped. A silent drop manufactures a blind
window, which manufactures a license, which manufactures a ROBUST verdict; this is the single most
dangerous failure mode in this section. Gate: `make quarantine-accounting` asserts
`accepted + quarantined == delivered_lines` for every cell.

61.4.6 STRIP-IDENTITY — remove or blank the fields entity resolution depends on.

Params: `sources[]`, `select_frac`, `fields[]` (must be declared `identity_bearing` in
`sources.toml`), `mode` in {BLANK, REMOVE, HASH_OPAQUE}. This operator exists to attack entity
resolution specifically, and its cells feed the ER quality contract. A record that survives
STRIP-IDENTITY is still a real witness of its `StepId`; the ledger link is unaffected, which is
exactly why the ledger is keyed on line position and not on content.

61.4.7 BACKDATE — rewrite recorded timestamps.

Params: `sources[]`, `select_frac`, `shift_ns` (signed), `monotone_repair` (bool),
`target` in {RANDOM, OBJECTIVE_TAGGED}.

Semantics. Add `shift_ns` to the record's own timestamp field(s). Delivery order is unchanged unless
`monotone_repair = true`, in which case the source is re-sorted by the new timestamps, which hides
the inconsistency that a difference-constraint pass would otherwise detect.

BACKDATE is adversarially special: the kernel's difference-constraint pass VOIDS licenses that rest
on provably backdated timestamps, voiding licenses shrinks P_max, and shrinking P_max can only push
verdicts toward ROBUST. An adversary who controls timestamps can therefore manufacture a ROBUST
verdict. Therefore: every BACKDATE cell is mandatory-included in every sampling plan (61.10), and
the fail-closed rule (unresolvable or contradictory timestamps yield BLIND, never a voided license)
is exercised by dedicated fixtures owned by the kernel threat-model section. This section's
obligation is to guarantee the cells exist and are never sampled away.

61.4.8 CHAIN-FORGE — fabricate records with a locally valid hash chain.

Params: `sources[]` (must have `chain_class = "CHAINED"`), `count`, `window_ns`, `template`
(a record shape drawn from the source's own observed vocabulary), `reseal` (bool).
Semantics: insert `count` fabricated records into the chosen window and, with `reseal = true`,
recompute the BLAKE3 sequence chain from the insertion point forward so no sequence gap is visible.
Ledger fate `SYNTHETIC{parent = none, kind = FORGED}`.

Hard rule: CHAIN-FORGE never creates a `StepId`. Ground truth is unchanged by fabrication. A fact the
kernel derives whose entire evidence set anchors to synthetic lines is a `phantom_derivation` and is
counted as such (61.11). Forbidden: describing a forged record as an attacker action in any output.

61.4.9 SOURCE-SILENCE — a source stops producing, entirely, over a window.

Params: `sources[]`, `t0_ns`, `t1_ns`, `announce` in {NONE, GAP_MARKER, HEARTBEAT_STOP}.
Distinct from WHOLE_SOURCE_BLACKOUT: blackout is deletion of records that were emitted (an agent
sent them and something removed them); SOURCE-SILENCE models a collector that never produced them,
and `announce` controls whether the outage is self-evident. `HEARTBEAT_STOP` ceases the source's
periodic heartbeat, which is the case liveness detection is supposed to catch;
`NONE` ceases records with no signal at all, which is the case it cannot.


61.5 OBSERVABILITY IN PRINCIPLE

Every source declares `chain_class` in `sources.toml`: `CHAINED` (BLAKE3 sequence chain),
`BRACKETED` (periodic heartbeat, no chain), `BARE` (neither). At least one source in every scenario
MUST be `BARE`. OVERRIDES Part I: results that rely on chain-detectable suppression must be reported
per `chain_class` and never pooled; demonstrating deletion detection only on chained sources and
presenting it as a result about suppressed telemetry is disallowed.

Observability classes: `OBS-C` detectable from a chain break; `OBS-B` detectable from bracketing,
inter-arrival or obligation reasoning; `OBS-N` no signal exists in the delivered bundle — only the
ledger knows.

| operator             | CHAINED | BRACKETED | BARE  |
|----------------------|---------|-----------|-------|
| DELETE uniform       | OBS-C   | OBS-B*    | OBS-N |
| DELETE targeted      | OBS-C   | OBS-B*    | OBS-N |
| DELETE blackout      | OBS-C   | OBS-B     | OBS-B |
| DELAY                | OBS-B   | OBS-B     | OBS-N |
| DUPLICATE            | OBS-C   | OBS-B     | OBS-N |
| REORDER              | OBS-B   | OBS-B     | OBS-N |
| CORRUPT (parse-fail) | OBS-B   | OBS-B     | OBS-B |
| CORRUPT (typed, valid)| OBS-N  | OBS-N     | OBS-N |
| STRIP-IDENTITY       | OBS-N   | OBS-N     | OBS-N |
| BACKDATE             | OBS-B   | OBS-B     | OBS-B |
| CHAIN-FORGE (reseal) | OBS-N   | OBS-N     | n/a   |
| SOURCE-SILENCE NONE  | OBS-N   | OBS-B     | OBS-N |

`OBS-B*`: observable only when the deletion widens an inter-arrival gap beyond the calibrated
baseline, or breaks an obligation pair. A single deletion inside a busy window is OBS-N even on a
BRACKETED source.

The `OBS-N` cells ARE the known-unsound region. The harness computes, per cell, the count of
ledger fates whose class is `OBS-N`, and publishes it as `invisible_class_volume` per dimension.
`LIMITATIONS.md` is generated from that artifact. Forbidden: any statement that SPECTRA detects
suppression, without the `chain_class` and observability-class qualifier attached in the same
sentence.


61.6 THE COMPLETENESS AXIS, DEFINED

OVERRIDES Part I: there is no scalar "completeness". The following four quantities are defined, all
are measured after the fact from the ledger and the ingest accounting, and all are reported
PER DIMENSION and PER SOURCE. Any code path, API field, chart axis, docs table or README sentence
that reduces them to one aggregate number fails the build (gate: `make completeness-lint`, a schema
and grep check for the banned identifiers `completeness_pct`, `completeness_score`,
`overall_completeness`, `data_quality`).

Let `dim` range over the declared state dimensions and `src` over declared sources.
`relevant(src, dim)` is declared in `sources.toml` as a many-to-many mapping.

1. `record_retention(src) = delivered_lines_nonsynthetic(src) / emitted_records(src)`
   Reported as an exact pair `(numerator, denominator)`, never as a bare percentage.
2. `record_retention(dim) = SUM over src in relevant(.,dim) of delivered_lines_nonsynthetic /
   SUM emitted_records`. A record relevant to several dimensions counts in each.
3. `source_coverage = |{src : delivered_lines(src) > 0}| / |declared sources|`.
4. `step_witness_coverage(dim) = |{s in steps(dim) : at least one surviving, parse-accepted,
   identity-bearing witness of s exists}| / |steps(dim)|`.

Quantity 4 is the one that matters for reconstruction and it is NOT derivable from 1-3: an adversary
who deletes 2% of records can drive `step_witness_coverage` to zero on a dimension while
`record_retention` reads 0.98. Publishing 1 without 4 is misrepresentation.

The plan's `[targets]` block states TARGET retention. `cell.json` records target AND realized values
for all four quantities. They differ, because integer flooring, quarantine, blackout windows and
operator composition all move the realized value. Gate `make realized-vs-target` fails a cell whose
realized `record_retention(src)` deviates from target by more than a declared tolerance without the
deviation being recorded in `cell.json.deviation_reason`. Forbidden: labelling a plot axis or a table
column with the target when the realized value was used, or the reverse.


61.7 GROUND-TRUTH ANCHORS AND RELINKING

This subsection exists because the zero-false-ROBUST invariant is otherwise not measurable.

61.7.1 The anchor. The generator emits a causal step list. `StepId` is the stable ground-truth
anchor. It is a string `"step:" + zero-padded ordinal`, assigned by the generator in causal order,
independent of any telemetry record, independent of any `EventId`, and IMMUNE to every operator in
61.4 because no operator can see it.

```jsonc
// truth/emission.jsonl  -- one row per emitted record. NEVER an ingest input.
{"record_id": 40219, "step_id": "step:0007", "source": "iam_audit",
 "emit_time_ns": 1712000003500000000, "dimension": ["identity","credential"],
 "identity_bearing": true, "effect_tags": ["cred.reuse"]}
```

```jsonc
// truth/steps.jsonl -- the causal chain itself
{"step_id": "step:0007", "parents": ["step:0005"], "dimension": "credential",
 "effect_tags": ["cred.reuse"], "actor": "gt:actor:1", "sim_time_ns": 1712000003400000000,
 "witness_record_ids": [40219, 40220]}
```

61.7.2 The link that survives perturbation. Content-based linking is impossible: CORRUPT rewrites
fields, DUPLICATE clones them, STRIP-IDENTITY removes them. The link is therefore PHYSICAL and is
established AFTER the final emit order is fixed:

> Every delivered line has a coordinate `(source, line_index)` in `raw/pert/<source>.log`. The
> perturber writes that coordinate into the ledger at emit time. The ingest pipeline attaches the
> same coordinate to every record it accepts or quarantines, as `origin`. The relinker joins on it.

`origin` is a physical coordinate in the perturbed artifact, not ground truth, so it may appear in
`bundle.jsonl` without leaking the generator's causal structure. Lint `origin-no-truth` fails if
`bundle.jsonl` or any kernel input contains `step_id`, `record_id`, `effect_tags` or any field
declared in `truth/*`.

```jsonc
// truth/ledger.jsonl -- written after operator step 9, one row per delivered line
// plus one row per non-delivered pre-perturbation record.
{"line": {"source":"iam_audit","line_index":881},
 "fate": "KEPT",
 "record_id": 40219, "step_ids": ["step:0007"],
 "mutations": [], "delivery_shift_ns": 0, "ops": []}

{"line": null, "fate": "DELETED", "op": {"op":"DELETE","mode":"TARGETED_ADVERSARIAL","index":0},
 "record_id": 40220, "step_ids": ["step:0007"], "obs_class": "OBS-N"}

{"line": {"source":"iam_audit","line_index":882},
 "fate": "SYNTHETIC", "kind": "DUPLICATE", "parent_record_id": 40219,
 "record_id": null, "step_ids": ["step:0007"], "ops": [{"op":"DUPLICATE","index":2}]}

{"line": {"source":"app_session","line_index":17},
 "fate": "SYNTHETIC", "kind": "FORGED", "parent_record_id": null,
 "record_id": null, "step_ids": [], "ops": [{"op":"CHAIN-FORGE","index":5}]}

{"line": {"source":"host_proc","line_index":204},
 "fate": "MUTATED", "record_id": 51102, "step_ids": ["step:0011"],
 "mutations": [{"field":"user.name","strategy":"CHAR_SWAP","k":2}], "obs_class":"OBS-N"}
```

Fate variants, closed set: `KEPT`, `DELETED`, `MUTATED`, `STRIPPED`, `BACKDATED`, `DELAYED`,
`REORDERED`, `SYNTHETIC`, `SILENCED`. A row may carry several `ops`; `fate` is the highest-priority
applied class in the 61.4.0 order. Lint `ledger-fate-total`: every pre-perturbation `record_id`
appears exactly once, and every delivered line appears exactly once. Gate `make ledger-bijection`.

61.7.3 The anchor map. The relinker produces:

```jsonc
// truth/anchor_map.json
{
  "schema": "spectra.anchor_map/2",
  "cell_id": "9c41f0b2ad7e5613",
  "entries": [
    {"event_id": "ev:000412", "origin": {"source":"iam_audit","line_index":881},
     "record_id": 40219, "step_ids": ["step:0007"], "synthetic": false},
    {"event_id": "ev:000413", "origin": {"source":"iam_audit","line_index":882},
     "record_id": null, "step_ids": ["step:0007"], "synthetic": true, "kind": "DUPLICATE"},
    {"event_id": null, "quarantine_id": "q:000031",
     "origin": {"source":"host_proc","line_index":990},
     "reason_code": "PARSE_INVALID_UTF8", "record_id": 51190, "step_ids": ["step:0013"],
     "synthetic": false}
  ],
  "unanchored_events": [],
  "orphan_lines": []
}
```

`unanchored_events` and `orphan_lines` MUST both be empty. A non-empty either way means ingest and
the perturber disagree about the delivered artifact, which invalidates every metric computed from
the cell. Gate `make anchor-closure` fails the cell, and a failed cell is recorded as
`status: "INVALID"` in the index — never dropped.

Derived relation, used everywhere downstream:

```
anchors(e : EventId) -> set<StepId>          // from anchor_map, may be empty for FORGED
witnesses(s : StepId) -> set<EventId>        // inverse
observed_support(s) = { e in witnesses(s) : not synthetic(e) }
```


61.8 CORRESPONDENCE: ANCHORS TO KERNEL GOAL ATOMS

A goal atom is a kernel object; a `StepId` is a generator object. The binding between them is
authored ONCE per scenario, at scenario-freeze time, before the rule table that could be tuned to it,
and is hashed into the cell identity.

```toml
# truth/objective.toml  -- frozen with the scenario, not with the rule table
scenario_id   = "s03-cred-reuse-to-egress"
frozen_at_git = "a71c9f0e"        # commit that froze this file; CI asserts it predates rules.toml edits

[[objective]]
goal_atom   = "attacker.exfil(dataset=finance_q3)"
# ACHIEVED in a run iff the generator executed some step carrying this effect tag.
achieved_iff = { any_step_with_effect_tag = "exfil.finance_q3" }

[[objective]]
goal_atom   = "attacker.persist(host=app-01)"
achieved_iff = { all_steps_present = ["step:0031", "step:0034"] }
```

Definitions, normative:

- `ACHIEVED_gt(scenario, run)` — a predicate over `truth/steps.jsonl` ONLY. It never consults
  telemetry, never consults the bundle, and is therefore invariant under every operator in 61.4.
  This is the property that makes the invariant measurable at all.
- `DERIVED_kernel(cell, S)` — the kernel's answer: the goal atom is in the least fixpoint under cut
  `S`. Mode `ROBUST` means not derived under P_max.
- The correspondence is a named relation `corr : goal_atom -> predicate over StepIds`, supplied by
  `objective.toml`. It is MANY-TO-ONE in the safe direction only: several goal atoms may bind to one
  effect tag; one goal atom may never bind to a disjunction authored after the run.
- Lint `objective-freeze`: CI compares the commit that last modified `truth/objective.toml` and the
  commit that last modified `rules.toml`. If the objective file was touched after the rule table for
  a scenario already in the held-out set, the scenario is marked `TUNED` and excluded from headline
  results. The comparison is mechanical and fails the build on inversion.

FALSE ROBUST, measurable form (section 62 owns the oracle and the triage; this section owns the
plumbing that makes the predicate well-formed):

```
false_robust(cell, S) :=
      cert(cell).safety == ROBUST
  AND cert(cell).cut == S
  AND ACHIEVED_gt(scenario, reexecute(scenario, seed, controls = S)) == true
```

`reexecute` is the counterfactual re-execution oracle of section 62. Note what the anchor design
buys: the right-hand conjunct is evaluated entirely on generator-side objects, so it is unaffected
by the perturbation applied to the left-hand conjunct's inputs. Without the anchors, the two sides
would reference `EventId`s that the perturbation rewrote, and the predicate would be undefined.

Negative requirement: no metric, gate, or report may substitute "the kernel derived the goal on the
clean bundle" for `ACHIEVED_gt`. That substitution is kernel-versus-kernel and passes vacuously.


61.9 THE MATRIX HARNESS

61.9.1 Cell identity. A cell is identified by the BLAKE3 of the canonical JSON of its full input
tuple, truncated to 16 hex characters:

```
cell_id = blake3_hex(canonical_json({
  scenario_id, scenario_hash, generator_version,
  plan_id, plan_hash, operators_registry_hash,
  targets_vector,                      // exact rationals, canonically ordered by source id
  seed_index, root_seed_hex,
  ingest_config_hash, er_config_hash,
  rules_hash, controls_hash, goal_hash, objective_hash,
  kernel_version, checker_version
}))[0..16]
```

Two runs with the same `cell_id` MUST produce byte-identical `cert.json`. Gate
`make matrix-crossrunner` re-runs a fixed subset on a second CI runner with a different CPU and OS
and diffs certificate hashes.

`seed_index` ranges over a declared seed set of size `n_seeds >= 5` (illustrative, not a target: the
repo ships 5 and nightly runs 20). A single run per cell is not a result; every reported quantity
carries its per-cell median and IQR over `seed_index`, and never a mean alone.

61.9.2 Artifact layout.

```
runs/matrix/<matrix_id>/
  matrix.json                 # plan set, scenario set, seed set, budget, sampling decision, git sha
  sampling.json               # strata, selection procedure, every excluded cell + reason
  index.jsonl                 # one row per DECLARED cell (sampled or not) -- see 61.10
  cells/<cell_id>/
    cell.json                 # full input tuple, target + realized completeness (61.6), deviations
    raw/pert/<source>.log.zst
    bundle.jsonl.zst
    quarantine.jsonl
    truth/{emission,steps,ledger}.jsonl.zst
    truth/{anchor_map.json,objective.toml}
    liveness.json
    cert.json
    checker.txt
    metrics.json              # 61.11
    manifest.json             # all input hashes, toolchain versions, git sha, host fingerprint
  aggregate/
    per_dimension.jsonl       # never a cross-dimension aggregate
    invisible_classes.jsonl   # feeds LIMITATIONS.md
```

`matrix_id` = `blake3_hex(canonical_json(matrix.json without host fields))[0..16]`. Wall-clock and
host identifiers live in `manifest.json` and are excluded from every hashed object.

61.9.3 CLI.

```
$ spectra matrix run --spec matrices/nightly.toml --out runs/matrix/ --budget-steps 2.5e11
declared cells      : 2160        (illustrative, not a target)
sampled cells       : 480         (illustrative, not a target)
excluded            : 1680  reason=BUDGET (recorded in sampling.json)
mandatory-included  : 96    (BACKDATE 32, red-team 40, held-out lowest-retention 24)
[cell 9c41f0b2ad7e5613] plan=p07 scenario=s03 seed=2
  realized record_retention: iam_audit 550/1000  app_session 701/1000  host_proc 1000/1000
  realized step_witness_coverage: identity 18/20  credential 11/17  session 14/14
  anchor closure: OK (unanchored_events=0 orphan_lines=0)
  cert: safety=OPTIMISTIC_ONLY minimality=SUBSET flags=[greedy_cover]
  checker: OK
  false_robust: n/a (safety != ROBUST)
[cell 3af0...] ... 
summary written: runs/matrix/7b12aa91c4d0e355/index.jsonl
gates: zero-false-robust PASS (0/480)   monotonicity PASS   anchor-closure PASS
       robust-yield 137/480  (floor 0.20 -> PASS)
```

Every printed number in this transcript is (illustrative, not a target). The demo-integrity rule
applies: the harness prints only values it computed in that run, and fails loudly on an input hash
mismatch rather than degrading.


61.10 SAMPLING PLAN

The full matrix will exceed the CI budget. That is expected and is handled explicitly.

- `index.jsonl` contains one row for EVERY DECLARED cell, whether or not it ran:
  `{"cell_id": "...", "status": "RAN"|"EXCLUDED"|"INVALID", "reason": "BUDGET"|null, "stratum": "..."}`.
  OVERRIDES Part I: a cell may be sampled out, never silently skipped. Gate `make matrix-accounting`
  fails if `|index.jsonl| != |declared cells|` or if any row lacks a status.
- Budget is expressed in DETERMINISTIC STEP UNITS (kernel fixpoint steps + corridor B&B node
  expansions), not seconds. A wall-clock budget would make cell inclusion machine-dependent and
  would break replay.
- Strata: `(plan_id, operator class set, target bucket, chain_class mix, scenario family)`. Target
  buckets are the declared retention bands, authored in `matrices/*.toml`.
- Selection: within each stratum, sort cells by `cell_id` ascending and take the first `k` where `k`
  is the stratum's budget share, rounded by largest-remainder. This is deterministic, requires no
  RNG, and is reproducible from `matrix.json` alone.
- Mandatory-included strata, never subject to budget: every BACKDATE cell; every CHAIN-FORGE cell;
  every red-team fixture; every held-out scenario at its lowest declared target vector; every cell
  whose plan sets `respect_obligations = false`; at least one `BARE`-only cell per scenario.
- Coverage disclosure: any figure, table or README sentence derived from a sampled matrix carries
  `sampled = true`, the stratum coverage fractions, and the `matrix_id`. Gate `make claims-bind`
  fails the docs build on a matrix-derived number with no `matrix_id` and no sampling disclosure.
- `make matrix-full` exists, runs the declared matrix with no exclusions, and is expected to be run
  off-CI. Its `index.jsonl` has zero `EXCLUDED` rows.


61.11 PER-CELL METRICS

All metrics are sets, counts, or exact fraction pairs. No metric in this section is a score, a
probability, a confidence, a severity, or a normalized index. Schema
`schemas/degradation-metrics.schema.json`; lint `metrics-no-scores` rejects any field name matching
`score|confidence|probability|severity|index|quality` outside an explicit allowlist.

| metric | definition |
|--------|------------|
| `step_witness_coverage[dim]` | 61.6(4), as `(num, den)` |
| `record_retention[src]`, `[dim]` | 61.6(1),(2), as `(num, den)` |
| `anchor_recall[dim]` | `|{s in steps(dim) : exists instance i in cert with evidence e, s in anchors(e), not synthetic(e)}| / |steps(dim)|` |
| `ghost_covered[dim]` | steps covered ONLY via a silent/licensed instance; disjoint from `anchor_recall` by construction |
| `phantom_derivations` | derived instances whose entire evidence set is synthetic (DUPLICATE or FORGED) |
| `blind_volume[src]` | total licensed blind duration in simulated ns, per source |
| `invisible_class_volume[dim]` | count of ledger fates classed `OBS-N` (61.5) |
| `quarantine_by_reason` | histogram over reason codes |
| `er_false_merge`, `er_false_split` | against `truth/emission.jsonl` identity-bearing fields |
| `safety`, `minimality`, `flags` | copied from `cert.json`, never recomputed |
| `false_robust` | 61.8; `null` when `safety != ROBUST` |
| `false_unsafe` | `safety in {UNSAFE, OPTIMISTIC_ONLY}` while the oracle says the cut holds |

`false_unsafe` is mandatory, not optional. OVERRIDES Part I: measuring only false ROBUST makes the
headline gate passable by returning UNSAFE, and the blindness premium is precisely the quantity a
false-UNSAFE bias inflates. Both rates are published side by side, per cell and per dimension.


61.12 GATES

All are build-failing unless marked.

| gate (make target) | assertion |
|---|---|
| `matrix-determinism` | perturber output and ledger byte-identical across two runs of the same cell |
| `perturb-determinism` | canonical candidate ordering; no hash-map, no filesystem-order iteration |
| `ledger-bijection` | every emitted record and every delivered line appears exactly once |
| `anchor-closure` | `unanchored_events` and `orphan_lines` empty for every RAN cell |
| `quarantine-accounting` | `accepted + quarantined == delivered_lines`, per source, per cell |
| `truth-isolation` | kernel, checker and ingest never read `truth/` |
| `no-wallclock` | no clock API in perturber or harness decision paths |
| `completeness-lint` | no aggregate completeness identifier anywhere in code, schema, API or docs |
| `matrix-accounting` | `index.jsonl` covers every declared cell with a status |
| `blind-monotonicity` | per source and per dimension, `blind_volume` is non-decreasing as realized `record_retention` decreases, over a monotone plan family; a non-monotone curve means the license logic is unsound |
| `op-registry-complete` | every operator variant has a registry row, a must-fire and a must-not-fire test |
| `objective-freeze` | `truth/objective.toml` commit predates `rules.toml` edits for held-out scenarios |
| `zero-false-robust` | `false_robust` is false for every RAN cell, scoped to the declared observability classes (61.5); the `OBS-N` region is stated, not hidden |
| `robust-yield-floor` | the fraction of cells where the oracle says the cut holds AND the kernel says ROBUST is at or above the declared floor; prevents `return UNSAFE` from passing the gate above |
| `gate-liveness-mutation` | injecting a known deletion-detection bug turns `zero-false-robust` or `blind-monotonicity` red; a green gate that cannot go red is decoration |


61.13 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS

- Do not apply any operator to `bundle.jsonl`, to canonical events, or to entity-resolution output.
- Do not let the perturber read the rule table, the control catalog, the goal, or the kernel.
- Do not put `StepId`, `record_id`, `effect_tags` or any `truth/` field into any kernel input.
- Do not link ground truth to telemetry by content, by timestamp, by entity, or by `EventId`.
- Do not drop a record silently at any stage. Quarantine with a reason code, always.
- Do not use wall-clock time, floating point, or unordered iteration in any perturbation decision.
- Do not report a single aggregate completeness figure, a "data quality score", or a normalized
  degradation index. There is no such quantity in this system.
- Do not skip a matrix cell without an `EXCLUDED` row and a reason.
- Do not report a matrix-derived number without its `matrix_id`, its seed count, its dispersion, and
  its sampling disclosure.
- Do not pool results across `chain_class`. Chained-source results do not transfer to bare sources.
- Do not describe a fabricated (SYNTHETIC) record as attacker activity, in the UI, the narration, the
  docs or the demo.
- Do not claim that SPECTRA detects tampering. The supported claim is narrower and must be written
  with its qualifiers attached: for the declared operator set, on sources of the declared
  `chain_class`, SPECTRA classifies certain windows as BLIND or SUPPRESSED, and the `OBS-N` classes
  are undetectable by construction and are enumerated with measured volume.
- Do not claim the degradation matrix validates reconstruction against reality. It measures the
  kernel against a generator written by the same author; that is an internal-consistency experiment
  under an explicitly declared perturbation model, and the docs say so in those words.
- Do not present a cell with `status: INVALID` as a result, and do not delete it.
