# The vertical slice: operative specification

Status: **the contract the reference implementation is built against.** The implementation is not
complete; this document describes what it must do, not what it does.

## What this is

The specification proper is 26,000 lines across 77 sections, and Part II overrides Part I in 453
places. This document is the operative extract for ONE thing: the smallest end-to-end system that
demonstrates the central idea.

It was produced by reading Part I sections 17-29 and Part II sections 63-68 directly, and it is
derived from them. Where it disagrees with the specification, the specification wins and this
document is the defect. It is not a substitute for reading sections 22-25 before touching the
kernel.

## The one thing that must survive every cut

The slice exists to show two things:

1. Missing telemetry becomes an explicit, named, re-checkable **licence** for an unobserved
   attacker step - not a silent gap, and not an assumption buried in a heuristic.
2. The separation between a control that is genuinely needed and a control that is in the cut
   **only because a sensor could not see**. That difference is the blindness premium.

Everything else here is negotiable against those two.

## Scope limits, stated up front

This describes a Python reference implementation. ADR-0013 records why: the machine has no Rust and
no Go toolchain, so the kernel and the independent checker specified in those languages cannot be
compiled. Nothing here may be read as evidence that they exist.

No result in this document is measured. The scenario, the control catalog and the two completeness
cells are a design, and the numbers in them are design parameters rather than observations.

---

# SPECTRA slice - operative specification

## pipeline

SPECTRA-VS ("vertical slice") is a PYTHON REFERENCE IMPLEMENTATION. No Rust kernel, no Go checker, no Docker range exist or are produced by it.

Layout (all paths absolute under D:/Academics/spectra):
  python/spectra_vs/            kernel-side packages (gen, ingest, er, calibrate, liveness, sglc, ground, envelope, reach, cut, cert)
  python/spectra_vs_verify/     the checker; a SEPARATE top-level package that imports nothing from spectra_vs
  config/vs/                    scenario, sources, controls catalog, catalog-bits.lock, rules.toml, liveness.toml, goal.toml
  runs/<run_id>/                all per-run artifacts
  profiles/<family>.json        calibration output (produced by a different run, different seed band)

Eleven stages, strictly ordered, each a pure function of hashed inputs, each writing one canonical artifact. `python -m spectra_vs <cmd>`:

 S0  bits-lock     controls/catalog.yaml -> config/vs/catalog-bits.lock  (append-only; assigns (control_id,level)->bit forever)
 S1  rules build   config/vs/rules.toml + facts schema + catalog-bits.lock -> runs/<id>/guards.cae, guard_ast_hash, rules_hash
                   (sglc-lite: lex, parse two sorts, typecheck, canonicalize C1-C8, DNF the control sort, assign masks)
 S2  gen           scenario.yaml + seed -> runs/<id>/raw.jsonl + runs/<id>/truth.jsonl
                   (seeded synthetic emitter; benign population + one attack chain + declared blind windows)
 S3  degrade       raw.jsonl + completeness c + dseed -> raw.c<NN>.jsonl + degradation_manifest.json
                   (delete-only; deletion sets NESTED across completeness levels for a fixed seed)
 S4  ingest        raw.c<NN>.jsonl -> runs/<id>/bundle.jsonl  (EventId assignment, per-source chain/seq sealing,
                   label-purity rejection, canonical sort, bundle_hash)
 S5  resolve       bundle.jsonl + entity tables -> runs/<id>/er.json  (exact deterministic joins only; er_hash)
 S6  calibrate     a SEPARATE clean run at completeness 1.0, seed from the calibration band -> profiles/<family>.json
                   (gap order statistics per (source, regime); profile_id)
 S7  liveness      bundle.jsonl + profile.json + liveness.toml + scenario phases -> runs/<id>/liveness.json
 S8  ground        bundle.jsonl + er.json + guards.cae -> runs/<id>/p_min.json   (semi-naive fixpoint with provenance; observed instances only)
 S9  envelope      p_min.json + liveness.json -> runs/<id>/p_max.json            (licensed silent instances + obligation-forced GHOSTs)
 S10 prove         p_min.json, p_max.json, goal.toml, catalog-bits.lock -> runs/<id>/psi_min.json, psi_max.json,
                   cut_min.json, cut_max.json, premium.json, decisive.json, residual.json, and runs/<id>/cert.spcert
 S11 verify        python -m spectra_vs_verify runs/<id>/cert.spcert --rules --controls --goal --bundle --liveness --er --profile
                   -> obligations O0..O15, ACCEPT/REJECT + reason code

S6 must be run first, on a different seed, before S7 of any analysis run. S10 runs the cut loop twice (over P_min and over P_max); that pair is the two-sided bracket.

The "seeded scenario generator" (S2) replaces the Docker cyber range, which cannot be built here. Every manifest, certificate and README produced by the slice carries `bundle_provenance: "synthetic_generator_no_range"` at manifest level (never as a per-record key, which would violate label purity).

## data_contracts

Global encoding law (SCF-lite), binding on every artifact:
- UTF-8, NFC, LF only, exactly one trailing LF. Object keys ASCII `[a-z0-9_]+`, sorted by byte value, unique. No insignificant whitespace. `json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)`.
- NO floats anywhere. `.`, `e`, `E`, `-0`, `NaN`, `Infinity` in a number position is E-CANON-FLOAT.
- JSON integers only where the field table says u8/u16/u32. Anything wider is a STRING: i64 nanoseconds as decimal text ("1707004800000000000"); u64 masks and seeds as fixed-width lowercase hex ("0x000000000000010d"). Rationals as {"num":u32,"den":u32} in lowest terms.
- `null` is never a value. Optionality is member absence. Exception: `verdict.witness_class` is present-and-null on non-UNSAFE (66.2.3 rule 2).
- Every array declared sorted is STRICTLY ascending under its declared key.
- Hash strings: "blake3:<64 lowercase hex>". Requires the `blake3` PyPI package; if it is not importable the run ABORTS. Substituting another digest silently is forbidden.
- Short ids: EventId "ev:<32hex>", FactId-key "fa:<32hex>", RuleInst "ri:<32hex>", License "lc:<16hex>", Entity "en:<32hex>", Corridor "c:<32hex>", Truth "tr_<16hex>".

--- 1. ScenarioSpec  (config/vs/scenario.yaml, hashed as goal_hash over its `goal` member, scenario_hash over the whole)
{ schema:"spectra.vs.scenario/1", scenario_id:str ^vs-[0-9]{2}-[a-z0-9-]+$, family:str,
  epoch_ns:str(i64), horizon_ticks:u32, tick_granularity_ns:u32 (=1000000000),
  sources:[SourceDecl], phases:[{regime_id:str, t0_ns:str, t1_ns:str}],
  excluded_intervals:[{t0_ns:str,t1_ns:str,reason:str}],
  entities:{principals:[{id,kind}], devices:[{id}], credentials:[{id,subject,kind}],
            services:[{id,zone}], resources:[{id,zone,sensitivity}], zones:[str]},
  noise:{benign_rate_num:u32, benign_rate_den:u32, families:[str]},
  attack:{chain_id:str ^vs-[0-9]{2}$, steps:[AttackStep]},
  blindness:[{source_id:str,t0_ns:str,t1_ns:str,basis:"blind"}],
  goal:{goal_predicate:str, goal_args:[str], horizon_k:u32} }
SourceDecl = { source_id:str, integrity_class:"chained"|"sequenced"|"none", source_rank:u8,
               emits_event_types:[str], nominal_period_ns:str(i64) (optional, F3 only) }
AttackStep = { k:u16, actor:str, action:str, event_type:str (absent iff emits==[]),
               emits:[source_id], attrs:{str:str}, observable:bool, t_offset_ns:str(i64),
               expect_transition:{dim:str,from:str,to:str} }
Loader constraints: exactly one goal; `emits: []` iff `observable:false`; every source_id in `emits` exists;
at least one source has integrity_class "none".

--- 2. RawEvent  (runs/<id>/raw.jsonl; one per line; generator -> degrade -> ingest)
{ source_id:str, seq:u32, t_evt_ns:str(i64), event_type:str, attrs:{str:str} }
Per source, `seq` is strictly ascending and dense (0,1,2,...) BEFORE degradation. attrs values are always strings.

--- 3. TruthAnnotation  (runs/<id>/truth.jsonl; co-emitted with the event; NEVER read by S4-S11)
{ truth_id:"tr_<16hex>", event_id:"ev:<32hex>" (absent iff kind=="attack_unobserved"),
  sim_tick:u32, kind:"benign"|"attack_step"|"attack_unobserved"|"noise_lookalike",
  origin:"population"|"scenario"|"degradation",
  chain_id:str (absent for benign), step_k:u16 (absent for benign), step_action:str (optional),
  actor_ref:str, subject_ref:str (optional),
  true_transition:{dim:str,from:str,to:str} (optional),
  observable:bool, producing_sources:[str] (empty iff kind=="attack_unobserved"),
  suppressed_by:"degradation" (absent otherwise) }

--- 4. BundleRecord  (runs/<id>/bundle.jsonl; the hashed telemetry artifact)
{ chain_hash:"blake3:.." (only when integrity_class!="none"),
  chain_prev:"blake3:.." (only when integrity_class!="none"; genesis = blake3 of the source_id bytes),
  event_id:"ev:<32hex>", event_type:str, seq:u32, source_id:str,
  t_evt_ns:str(i64), t_ing_ns:str(i64), attrs:{str:str} }
event_id = "ev:" + blake3(scf({attrs,event_type,seq,source_id,t_evt_ns})).digest()[:16].hex()
chain_hash = blake3(bytes.fromhex(chain_prev[7:]) + scf(record minus chain_hash)) .hex()
File order: ascending (t_evt_ns as int, source_id, seq, event_id). bundle_hash = blake3(file bytes).
Ingest REJECTS, exit 4, any raw record carrying a key in {label, is_attack, scenario, truth} or matching `__truth*`.

--- 5. DegradationManifest  (runs/<id>/degradation_manifest.json)
{ schema:"spectra.vs.degradation/1", parent_raw_hash:"blake3:..", completeness:{num:u32,den:u32},
  degradation_seed:str(0x hex u64), operators:["delete"],
  removed:[{source_id:str, seq:u32, event_id:"ev:<32hex>"}]  sorted by (source_id, seq),
  nested_parent_manifest_hash:"blake3:.." (absent at the highest completeness level) }
Invariant: removed(c1) ⊇ removed(c2) whenever c1 < c2 for a fixed degradation_seed.

--- 6. EntityMap  (runs/<id>/er.json)
{ schema:"spectra.vs.er/1",
  entities:[{entity_id:"en:<32hex>", kind:"principal"|"device"|"credential"|"session"|"service"|"resource"|"zone",
             canonical_name:str, join_rule_id:str, resolved_from:["ev:.."] sorted}] sorted by entity_id,
  bindings:[{event_id:"ev:..", role:str, entity_id:"en:.."}] sorted by (event_id, role),
  ambiguous:[{event_id:"ev:..", role:str, candidates:["en:.."] sorted}] sorted by (event_id, role) }
entity_id = "en:" + blake3(scf({canonical_name,kind})).digest()[:16].hex()
join_rule_id ∈ {r_exact_principal, r_exact_device, r_exact_token, r_exact_session_by_token, r_exact_resource}.
Only exact string joins against the scenario entity tables. No fuzzy matching, no similarity, no scores.
`ambiguous` non-empty ⇒ run flag `er_ambiguous` (bit 3, soundness class). er_hash = blake3(scf(er.json)).

--- 7. SourceProfile  (profiles/<family>.json)
{ schema:"spectra.source_profile/1", profile_id:"blake3:..",
  generator_config_hash:"blake3:..", scenario_family:str,
  degradation_spec_hash:"blake3:.." (must equal IDENTITY_SPEC_HASH),
  calibration_seed_band:[u32,u32], reference_bundle_hash:"blake3:..",
  reference_run_manifest_hash:"blake3:..", excluded_intervals_hash:"blake3:..",
  regime_collapsed:bool,
  sources:[{ source_id:str, integrity_class:str,
    regimes:[{ regime_id:str, n_gaps:u32,
               order_statistics:{"<p>/<q>": str(u64 ns)},   keys exactly the levels in liveness.toml
               min_gap_ns:str, max_gap_ns:str, gap_digest:"blake3:.." }] sorted by regime_id }] sorted by source_id }
profile_id = blake3(scf(object with profile_id removed)).
gap_digest = blake3 over LEB128(len) || LEB128(gap_i) of the full ascending u64 gap vector.

--- 8. LivenessDoc  (runs/<id>/liveness.json, schema "spectra.liveness/2") — exactly the 65.7 shape:
{ schema, mode_global:"F0_CALIBRATED"|"F1_INSUFFICIENT"|"F2_NO_PROFILE"|"F3_DECLARED",
  profile_id, quantile:"95/100", slack:"3/2", n_min:u32, m_min:u32,
  sources:[{ source_id, integrity_class, mode, threshold_ns:str(u64) (absent in F1/F2),
    threshold_provenance:{kind:"profile"|"declared", profile_id, regime, n:u32, p:"95/100", slack:"3/2"} (absent in F1/F2),
    intervals:[{ t0_ns:str, t1_ns:str, verdict:"LIVE"|"BLIND"|"SUPPRESSED", reason:str,
                 missing_seq:[u32,u32] (SUPPRESSED only), witness:["ev:..",".."] (SUPPRESSED only) }]
      sorted by t0_ns, contiguous, RLE-merged on equal (verdict,reason),
    blind_volume_ns_by_reason:{reason:str(u64)}, suppressed_volume_ns:str(u64), tamper_suspected:false }]
    sorted by source_id,
  flags:{liveness_uncalibrated:bool, liveness_unauthenticated:bool, blind_by_default:bool,
         profile_regime_collapsed:bool, verdict_tamper_sensitive:false, mcs_greedy:false} }
liveness_hash = blake3(scf(liveness.json)).

--- 9. License
{ license_id:"lc:<16hex>", source_id:str, t0_ns:str, t1_ns:str,
  basis:"BLIND"|"SUPPRESSED", reason:str,
  witness:["ev:..","ev:.."] (present iff basis=="SUPPRESSED") }
license_id = "lc:" + blake3(scf({basis,reason,source_id,t0_ns,t1_ns})).digest()[:8].hex()
A BLIND license carries a reason code and NO witness (65.5.2 override). Never call it an observation.

--- 10. Fact
fact_key = "fa:" + blake3(scf({args:[entity_id...], predicate:str, tick:u32})).digest()[:16].hex()
{ fact_key, predicate:str, args:["en:.."], tick:u32 }   facts array sorted by fact_key.

--- 11. RuleInstance
{ instance_id:"ri:<32hex>", rule_id:str ^r[0-9]{4}$, rule_version:str ^\d+\.\d+\.\d+$,
  head:"fa:..", body:["fa:.."] (<=4, in the rule's declared body order),
  blockers:["0x0000000000000001", ...] sorted by (popcount, value), each with popcount==1 in this slice,
  observed:"OBSERVED"|"LICENSED", tick:u32,
  evidence:[{binding:str, event_id:"ev:..", source_id:str, t_evt_ns:str}] sorted by (binding,event_id)
            — empty iff observed=="LICENSED",
  license_ids:["lc:.."] sorted — empty iff observed=="OBSERVED",
  ghost:bool  (true iff this instance's head is an obligation-forced unobserved transition) }
instance_id = "ri:" + blake3(scf({body,evidence_event_ids,head,license_ids,rule_id})).digest()[:16].hex()

--- 12. Program  (runs/<id>/p_min.json, p_max.json)
{ schema:"spectra.vs.program/1", kind:"PMin"|"PMax",
  facts:[Fact] sorted by fact_key, instances:[RuleInstance] sorted by instance_id,
  licenses:[License] sorted by (source_id,t0_ns,t1_ns) — empty for PMin,
  axioms:["fa:.."] sorted, goal:"fa:..",
  counts:{observed_instances:u32, silent_instances:u32, ghost_facts:u32, observed_events:u32} }
`observed_events` NEVER includes a silent instance or a GHOST fact.

--- 13. Corridor / Psi  (runs/<id>/psi_min.json, psi_max.json)
Corridor = { corridor_id:"c:<32hex>", atom_ranks:[u16] ascending, mask:"0x%016x" }
corridor_id = "c:" + blake3(LEB128(len)||LEB128(rank_0)||...).digest()[:16].hex()
Psi = { schema:"spectra.vs.psi/1", program:"PMin"|"PMax", complete:bool,
        corridors:[Corridor] sorted by corridor_id, corridor_cap:u32, bb_nodes:u32 }

--- 14. Cut / Residual
AtomRef = { control_id:str, level:u8, bit:u8, rank:u16 }
Cut = { atoms:[AtomRef] sorted ascending by rank (upward-closed: level ℓ implies ℓ-1..1 present),
        cardinality:u8 (= number of RAISED CONTROLS, never the number of atoms),
        mask:"0x%016x", minimality:"EXACT_EXHAUSTIVE"|"EXACT_PSI_RELATIVE"|"SUBSET"|"UNVERIFIED" }
Residual = { goals_derivable:["fa:.."] sorted, goals_severed:["fa:.."] sorted,
             corridors_open:["c:.."] sorted, program:"PMin"|"PMax", corridors_exhaustive:bool }
There is no scalar residual. No field named residual_score/residual_pct/coverage anywhere.

--- 15. Certificate  (runs/<id>/cert.spcert)
File = {"body":{...},"cert_hash":"blake3:<64hex>"} in SCF-lite. First 26 bytes are exactly `{"body":{"schema":{"v":`.
cert_hash = blake3(scf(body)). Only `body` is hashed.
body = {
  schema:{v:"1.1", min_checker:"1.1", profile:"eclipse-cert"},   1.1 since ADR-0015 (was 1.0)
  scope:{ rules:"b3:<64hex>", controls:"b3:..", liveness:"b3:..", er:"b3:..",
          goal:"b3:..", bundle:"b3:..", attacker:"non-adaptive" },        exactly these seven members
  inputs:{ rules_hash, rules_text_hash, guard_ast_hash, controls_hash, catalog_bits_hash,
           bundle_hash, liveness_hash, profile_hash, goal_hash, er_hash, instances_hash,
           seed:"0x%016x", k:u32, grounding_mode:"replayed",
           bundle_provenance:"synthetic_generator_no_range",
           implementation:"python-reference" },
  verdict:{ safety:"ROBUST"|"OPTIMISTIC_ONLY"|"UNSAFE"|"INDETERMINATE",
            witness_class:null|"OBSERVED"|"LICENSED"|"CONTESTED",   present-and-null unless UNSAFE
            minimality:"EXACT_EXHAUSTIVE"|"EXACT_PSI_RELATIVE"|"SUBSET"|"UNVERIFIED",
            flags:[str] sorted by BIT POSITION,
            derived_suppressed:[str] sorted,
            realizability:"CHECKED"|"UNCHECKED" },
  atoms:{ n:u8, assign:[[control_id, level:u8, bit:u8]] sorted by bit },
  cut:[AtomRef] sorted by rank,
  goals:[{ goal_key:"fa:..", derivable:bool }] sorted by goal_key,
  invariant:{ u:["fa:.."] strictly ascending }      present iff every goal is severed,
  instances:[InstRef] sorted by instance_id, InstRef = {instance_id, head, body, blockers, observed, license_ids},
  licenses:[License] sorted by (source_id,t0_ns,t1_ns),
  silent:[{instance_id, license_ids}] sorted by instance_id,
  witnesses:[{ removed_control:str, nodes:[WitnessNode] }] sorted by removed_control,
            nodes in pre-order, nodes[0] the root (ADR-0015; was a nested `tree`),
  psi:{ program:"PMax", complete:bool, corridors:[Corridor] sorted by corridor_id },
  premium:{ nec_max:[control_id] sorted, occ_min:[control_id] sorted, blindness_premium:[control_id] sorted,
            per_control:[{control_id, license_ids:[..], calibration_deficiency:{num:u32,den:u32}}] }
            — the whole `premium` member is ABSENT when its preconditions fail, and
              premium_suppressed_reason:"grounding_capped"|"corridor_cap"|"solver_budget"|"horizon_truncated"|"er_ambiguous"
              appears instead,
  cut_delta_canonical:[control_id] sorted,     never labelled or described as the blindness premium
  residual:Residual,
  budgets:{ fixpoint_steps:u32, bb_nodes:u32, step_budget:u32, budget_exhausted:bool,
            exhaustive_ran:bool, exhaustive_cuts_tested:u32 },
  observed_event_count:u32, ghost_count:u32      two separate members; a single summed member is forbidden
}
WitnessNode = { instance_id, head:"fa:..", kind:"OBSERVED"|"GHOST"|"LICENSED",
                evidence:["ev:.."] (empty iff GHOST or LICENSED), children:[u32] }
              children are indices into `nodes`, each greater than the node's own index;
              every node but the root has exactly one parent. A subtree used twice is
              written twice. GHOST cites an obligation-forced instance (ghost:true);
              LICENSED cites a licensed silent instance that is not (ghost:false,
              observed:"LICENSED"). The nesting depth is seven for a witness of any length.
body carries NO wall-clock time, no hostname, no username, no path, no pid, no duration, no `measured` member.

## liveness

Liveness is computed by S7 and is the ONLY producer of licences. No threshold is ever derived from the bundle under analysis.

CONFIG (config/vs/liveness.toml, hashed):
  schema="spectra.vs.liveness_cfg/1"; quantile="95/100"; slack_num=3; slack_den=2;
  k_tail=5; n_floor=30; m_min=3; mcs_exact_cap=64
  n_min(p,q) = max(n_floor, ceil(k_tail*q/(q-p))) = max(30, 100) = 100 for 95/100.
  Decimal literals ("0.95") are rejected at parse time. q-p==0 is rejected at parse time.

CALIBRATION (S6): run the SAME scenario family at completeness 1.0 with the identity degradation spec,
under a seed drawn from calibration_seed_band = [1000000,1000063], disjoint from the analysis band [1,999999].
For each (source s, regime r): order s's records by (t_evt_ns, seq, event_id) with a STABLE sort; emit consecutive
differences as u64 ns; keep zero gaps; drop any gap whose span intersects an excluded_interval; regime membership
comes from the scenario's hashed phase timeline, never inferred. Sort ascending, write order_statistics and gap_digest.
The generator must emit >= 2000 records per calibrated source over the horizon so that n_gaps >= n_min per regime.

QUANTILE (integer only, no interpolation, no float):
  def q_exact(D_sorted, p, q):  n=len(D_sorted); j=(n*p + (q-1))//q; j=min(max(j,1),n); return D_sorted[j-1]
  Threshold T(s,r) = ceil(Q * slack_num / slack_den) in u64 ns, saturating at 2**64-1; saturation forces BLIND
  with reason B_THRESHOLD_OVERFLOW.

BINDING GATES B1..B6, checked at prove time AND at verify time; failure aborts the run / rejects the cert:
  B1 profile.reference_bundle_hash != cert.inputs.bundle_hash   else PROFILE_SELF_CALIBRATED
  B2 profile.degradation_spec_hash == IDENTITY_SPEC_HASH        else PROFILE_FROM_DEGRADED_RUN
  B3 cert.inputs.seed not in profile.calibration_seed_band      else PROFILE_SEED_OVERLAP
  B4 profile.generator_config_hash == run generator_config_hash else PROFILE_CONFIG_MISMATCH
  B5 profile.scenario_family == run scenario_family             else PROFILE_FAMILY_MISMATCH
  B6 profile.excluded_intervals_hash == run value               else PROFILE_INTERVALS_MISMATCH

MODE LADDER, selected per (source, regime) except F2 which is global:
  F0 CALIBRATED   profile present, B1..B6 hold, n_gaps >= n_min  -> LIVE possible
  F1 INSUFFICIENT profile present but source/regime missing or n_gaps < n_min -> every window BLIND
                  (B_PROFILE_INSUFFICIENT), sets flag liveness_uncalibrated
  F2 NO_PROFILE   `--no-profile` given -> every window BLIND, sets blind_by_default;
                  premium, decisive set and redundancy index are STRUCTURALLY SUPPRESSED
  F3 DECLARED     source has nominal_period_ns AND `--allow-declared-profile` -> threshold from the declared period,
                  sets liveness_uncalibrated, premium not publishable
  F4 SELF         DOES NOT EXIST. ThresholdProvenance has no run-derived variant. `make lint-edr` fails on one.
Running `prove` with neither --profile nor --no-profile is an error, exit 2, with both options printed.

BREAKPOINT GRID (deterministic, query-order independent):
  For each source s, breakpoints = sorted unique union of { every t_evt_ns of s in the bundle } ∪ { every phase
  boundary } ∪ { every interval endpoint the envelope stage will request } ∪ { scenario t0, t1 }.
  Elementary intervals are consecutive breakpoint pairs [a,b). Verdicts are computed per elementary interval and
  then RLE-merged over equal (verdict, reason). Permuting the envelope stage's query order must yield a
  byte-identical liveness.json (property test).

WINDOW OBSERVATION for (s, [a,b)):
  regime            = the phase containing a, else None
  left_bracket      = the record of s with the greatest t <= a, else None
  right_bracket     = the record of s with the least t >= b, else None
  n_records_in_span = count of s's records with left_bracket.t <= t <= right_bracket.t (0 if a bracket is None)
  max_observed_gap_ns = max consecutive difference among those records, 0 if fewer than 2
  chain             = Absent                     if integrity_class == "none"
                    = Unverified{first_bad}      if any chain_hash in the span fails recomputation
                    = Verified{missing_seq:(i,j)} if seq jumps from i to j>i+1 inside the span
                    = Verified{missing_seq:None} otherwise
  Point timestamps only: the skew-envelope interval semantics of Part I 17.1.4 do NOT apply in this stage and
  `order_indeterminate` is not a liveness outcome.

CLASSIFICATION, first match wins, order is normative:
  R1  mode == F2                                        -> BLIND       B_FORCED_NO_PROFILE_MODE
  R2  regime is None                                    -> BLIND       B_REGIME_UNKNOWN
  R3  threshold is None (F1)                            -> BLIND       B_PROFILE_INSUFFICIENT
  R4  threshold saturated                               -> BLIND       B_THRESHOLD_OVERFLOW
  R5  chain == Unverified                               -> BLIND       B_CHAIN_UNVERIFIED
  R6  chain Verified with missing_seq, class=="chained" -> SUPPRESSED  S_CHAIN_SEQ_GAP
  R7  chain Verified with missing_seq, class=="sequenced"-> SUPPRESSED S_SEQ_GAP_UNAUTHENTICATED + liveness_unauthenticated
  R8  left_bracket is None or right_bracket is None     -> BLIND       B_UNBRACKETED
  R9  n_records_in_span < m_min                         -> BLIND       B_WINDOW_UNDERSAMPLED
  R10 max_observed_gap_ns > threshold                   -> BLIND       B_GAP_EXCEEDS_THRESHOLD
  R11 otherwise                                         -> LIVE        L_CALIBRATED_OK
R11 is the ONLY construction site of LIVE in the codebase. No exception path, no default, no `except: return LIVE`.
Any internal error in this stage is converted to BLIND with a reason code, never propagated as a run failure.

LICENCE ISSUANCE (S9 envelope):
  live(s, I) holds iff every elementary interval contained in I has verdict LIVE on s.
  A rule tau with silent_possible=true may be instantiated silently over interval I iff
        for every s in producing_sources(tau):  not live(s, I)
  Each such instance carries license_ids for exactly the (source, maximal non-LIVE run) covering I on each producing
  source. BLIND licences carry a reason and no witness; SUPPRESSED licences carry missing_seq and the two bracketing
  event ids.
  Obligation axioms: an unsatisfied obligation over interval I forces a silent instance and a GHOST head fact IF the
  above licence condition holds; if the obligation is unsatisfied AND unlicensed, no GHOST is created and the stage
  emits `permanent_blind_spot` into runs/<id>/blind_spots.json and into the per-dimension blind-spot volume.

ABSENCE (the only permitted negation), evaluated only on a sealed lookback [t_A - W, t_A):
  OBSERVED     iff all s in producing_sources(B) are live over the whole lookback  -> fact in P_min and P_max
  LICENSED     iff all s in producing_sources(B) are non-live over the whole lookback -> fact in P_max ONLY
  otherwise    UNDETERMINED                                                        -> fact in P_max ONLY,
               counter absence_undetermined incremented, run flag uses_undetermined_absence set for reporting.
Counters absence_observed / absence_licensed / absence_undetermined go into liveness.json.

BLIND-VOLUME ACCOUNTING: measured in nanoseconds per source, PARTITIONED by reason, never summarised into one number.
Reasons are split into calibration-deficiency {B_PROFILE_INSUFFICIENT, B_REGIME_UNKNOWN, B_FORCED_NO_PROFILE_MODE,
B_THRESHOLD_OVERFLOW, B_WINDOW_UNDERSAMPLED} and observed-gap {B_GAP_EXCEEDS_THRESHOLD, B_UNBRACKETED, S_*}.
Every premium control carries per_control.calibration_deficiency as an exact rational so that a control resting on
missing calibration is never described as resting on an observed sensor gap.

TAMPER: the slice does NOT implement the Bellman-Ford backdating pass. Therefore tamper_suspected is always false,
verdict_tamper_sensitive is always false, flag bit 5 is never set, and the slice must never claim it detects
suppression, backdating or tampering of any kind. The `Safety.ROBUST` constructor still takes the NoTamperToken so
that the pass can be added without reworking the type.

## grounding

RULE FORM (config/vs/rules.toml). Two disjoint sorts, per Part II 63. `admit_when` and `ctrl.` do not exist here.

[[rule]]
id            = "r0003"                    # ^r[0-9]{4}$, from an append-only registry, never reused
version       = "1.0.0"
dimension     = "privilege"
kind          = "detect" | "obligation"
head          = "privilege.escalated(P, R, T)"
body          = ["iam.role_assumed(P, R, T)"]              # <= 4 patterns after normalisation
temporal      = { op = "absence", of = "iam.approval_granted(P, R, T0)", before = "assume", within = "72h" }
when          = "a.principal == b.principal and within(a.t, b.t, 30m)"    # DATA sort: Bool, no ctl.
blocked_when  = "ctl.priv_approval >= async_ticket"                       # CONTROL sort: Ctl, positive, level by NAME
producing_sources = ["iam_audit"]          # for `absence`, the sources of the ABSENT fact
silent_possible   = true
persistence   = "instant" | "until(<expr>)" | "sticky"
evidence      = ["assume"]
causal_relation = "AUTHORIZES"
attck         = ["T1078"]
note          = "free prose; NOT hashed into guard_ast_hash"

SGL-LITE (S1, `python -m spectra_vs sglc`). Implement exactly:
- Lexer: snake_case idents, base-10 int_lit with `_`, dur_lit with ns|us|ms|s|m|h|tick, sym_lit `#ident`,
  bool_lit. Reserved: and or not in true false ctl min max abs within overlaps distinct. NO comments, NO strings.
  A `.` followed by a digit is E-LEX-004. A CR byte is E-LEX-001.
- DATA sort grammar and CONTROL sort grammar exactly as 63.3. `ctl.` inside `when` is E-SYN-010; `not`/arith/
  literal/variable inside `blocked_when` is E-SYN-009; a level written as an integer is E-SYN-012.
- Types Bool/Int/Tick/Dur/Sym<D>/Ent<K>/Src/Set<D>/Ctl exactly as 63.4. No implicit conversion, no cast, no null,
  no option. `when` root must be Bool (E-TYP-001); `blocked_when` root must be Ctl (E-TYP-002).
- Evaluation is TOTAL: every eval function returns a value, never raises. Arithmetic saturates at i64 bounds;
  a saturation site is recorded and a fixture that saturates is quarantined.
- Canonicalisation C1..C8 in order: desugar to the core node set {And,Or,Not,Eq,Lt,Add,Sub,MulLit,Min,Max,Abs,
  Slot,Field,ConstInt,ConstBool,ConstSym,Threshold}; constant-fold with saturating semantics and normalise
  durations to ticks (a non-integral duration is E-SEM-030); NNF; flatten/absorb/dedupe/sort children by
  (kind_tag, node_hash_128); hash-cons into a DAG numbered in postorder; rename bound variables to SLOT indices
  in the order they appear in the rule's `body`, not in the guard; then for the control sort only: distribute to
  DNF (>8 terms is E-SEM-041), keep only the highest level per control within a term, drop superset terms across
  terms and keep the lowest level for single-control terms, map atoms to bits from catalog-bits.lock, sort terms
  by (popcount, value); finally assert canon(canon(x)) == canon(x) bytewise on every compile.
- CAE encoding: LEB128, no padding, no floats, as in 68.4:
    cae := "CAE1" u32(rule_count) rule*        rules sorted by rule_id
    rule := u16(rule_id) atom(head) u8(n) atom{n} guard u8(n_src) srcid{n_src} u8(silent_possible) u64le(mask)
  guard_ast_hash = blake3(guards.cae). rules_hash = blake3(guards.cae) over the CAE plus the per-rule metadata
  record (rule_id, head, body sorted, producing_sources sorted, silent_possible, attck sorted).
  rules_text_hash = blake3(raw rules.toml bytes), recorded but NEVER enforced; a comment edit must not change
  rules_hash and must not invalidate a certificate.

SLICE NARROWING C-SLICE-1 (stated as a narrowing, not a claim): every DNF term must have popcount 1, i.e.
`blocked_when` is a disjunction of bare thresholds with no `and`. The compiler rejects a conjunctive term with
E-VS-BLOCK-CONJ. Consequence: `enabled(inst,S)` collapses from the general subset test to `(mask & S) == 0`, and
a corridor is a plain OR-of-atoms clause. The general conjunctive case (blockers as SmallVec<[u64;2]> with subset
containment) is DEFERRED, and the code carries the subset test behind the popcount-1 assertion so the narrowing is
visible in the source.

TEMPORAL OPERATORS IMPLEMENTED IN THE SLICE (exactly three; everything else is deferred):
  seq      : [A,B] within W, non-overlapping, t_A < t_B, t_B - t_A <= W
  absence  : B before A within W, sealed lookback, blindness-guarded per the liveness section
  distinct : distinct(field) >= N over sliding(W,S), exact HashSet, no sketches
Ticks: tick(t) = t_evt_ns // 1_000_000_000. Delta is hashed into rules_hash; changing it invalidates certificates.

GROUNDING (S8, P_min). Semi-naive evaluation with provenance over OBSERVED facts only:
  1. Seed the fact base from bundle records mapped through er.json bindings: an event of type E with bindings
     {role: entity_id} produces the axiom fact `E(entity_ids..., tick)`. Facts are interned into fact_key.
  2. Iterate to fixpoint: for each rule, join its body patterns against the delta and the accumulated base under
     the `when` predicate and the temporal operator; every match produces one RuleInstance with observed="OBSERVED",
     its evidence event ids, and blockers = the rule's compiled DNF masks.
  3. Facts are append-only. Nothing is retracted. Expiry is modelled as non-derivation via the persistence
     generator `holds(F,K+1) :- holds(F,K), K+1 <= expiry_tick(F)`; expiry_tick is a pure function of already-derived
     facts and control levels computed from the same guard AST that the kernel uses.
  4. Caps: MAX_FACTS=200000, MAX_INSTANCES=500000, MAX_ITERATIONS=1000. On any cap, set flag `grounding_capped`
     (bit 0, soundness class) and publish the measured sizes. A capped run can never be ROBUST.
  5. Determinism: instances and facts are emitted in sorted order; no set or dict iteration reaches output.

ENVELOPE (S9, P_max = P_min ∪ licensed silent instances ∪ obligation-forced GHOST instances), per the liveness rules.
P_min ⊆ P_max always. The two programs are separate files; nothing mutates P_min in place.

HYPERGRAPH SHAPE: the provenance structure is bipartite AND/OR.
  OR nodes  = facts (fact_key). A fact is derivable if ANY instance with that head fires.
  AND nodes = rule instances. An instance fires when EVERY body fact is derived AND it is enabled under the cut.
  Edges: instance -> head (one), body fact -> instance (one per body literal).
  Adjacency is stored as `by_body: dict[fact_key, list[instance_idx]]` built in sorted order.
  A GHOST is a fact whose only supporting instances are silent. GHOSTs never enter observed_event_count; the
  certificate carries observed_event_count and ghost_count as two separate members.
  A GHOST may never be the sole support of a PROPAGATES-class edge; the grounder asserts this and fails the run.

## fixpoint

REACHABILITY UNDER A CUT (Dowling-Gallier unit propagation, linear in the program):

  def reach(program, S: int) -> tuple[bool, list[str], int]:
      cnt   = [len(inst.body) for inst in program.instances]
      U     = set()                      # accumulated in a list, sorted only on output
      order = []                         # U in first-derived order; the certificate stores it SORTED
      q     = deque(program.axioms)      # facts with no supporting instance body, sorted ascending
      steps = 0
      while q:
          f = q.popleft()
          if f in U: continue
          U.add(f); order.append(f)
          for ix in program.by_body.get(f, ()):        # by_body lists are sorted by instance_id
              inst = program.instances[ix]
              if any((term & S) == term for term in inst.blockers):   # blocked under this cut
                  continue
              cnt[ix] -= 1; steps += 1
              if cnt[ix] == 0:
                  q.append(inst.head)
          steps += 1
      return (program.goal in U, sorted(U), steps)

  With C-SLICE-1 every term has popcount 1, so the blocked test is exactly `(inst.mask & S) != 0`; the general
  subset form is retained in the code behind an assertion so the narrowing is visible.
  NO early exit on reaching the goal: the full least fixpoint U is needed as the invariant the checker replays.
  `steps` is a DETERMINISTIC counter compared against step_budget; there is no wall-clock budget anywhere.

  Antitonicity obligation: S ⊆ S' implies reach(P,S').U ⊆ reach(P,S).U. Property test over the whole admissible-cut
  lattice (9 atoms, 3*3*2*3*3 = 162 downward-closed cuts) on every fixture. The grammar makes a counterexample
  unparseable; the test exists so that a mutation to the mask test turns a named gate red.

  Monotonicity in the program: P_min ⊆ P_max implies reach(P_min,S).U ⊆ reach(P_max,S).U, for every S.

THE TWO-SIDED BRACKET. The slice runs the whole cut machinery TWICE and never enumerates worlds:
  lower side  P_min = observed instances only        -> Psi_min, cut_min = canonical_min_cut(Psi_min)
  upper side  P_max = observed ∪ licensed silent     -> Psi_max, cut_max = canonical_min_cut(Psi_max)
  For any cut S:
      goal ∉ fix(P_max, S)  =>  goal ∉ fix(P_min, S)          (safe direction: ROBUST is conservative)
      goal ∈ fix(P_min, S)  =>  goal ∈ fix(P_max, S)          (witness direction)
  The bracket is reported as the pair (residual over P_min, residual over P_max) plus the two canonical cuts.
  It is NOT a confidence interval and must never be rendered as one.

P_max IS A SUPERSET OF REALIZABLE WORLDS. P_max unions all licensed silent instances and ignores mutual-exclusion
structure, so Reach(P_max) ⊇ union over realizable worlds of Reach(w). Consequences, written verbatim in
docs and in the OpenAPI/CLI text:
  - ROBUST is sound with respect to realizability: goal unreachable in P_max implies unreachable in every
    realizable world.
  - UNSAFE and every counterexample tree extracted from P_max may combine silent instances that no single
    consistent world realizes. Such a tree may depict an attack that could not have happened.
  - Every premium member, decisive-observation set and frontier point derived from Psi_max carries
    program:"PMax" so no consumer can forget it.

REALIZABILITY. Every counterexample tree carries:
  { status:"REALIZABLE"|"UNREALIZABLE"|"UNDECIDED",
    checks_run:["exclusive_group","license_window"],
    violations:[{check, group, instances:[instance_id]}],
    undecided_reason:str (absent when null) }
The slice implements TWO of the four checks:
  exclusive_group : rules may declare exclusive_group="<name>" and exclusive_key=[body slot indices]; group the
                    tree's silent instances by (group, key binding); more than one distinct head in a group is a
                    violation. O(n log n).
  license_window  : every silent instance's interval lies inside its cited licence interval, and the licence is
                    BLIND or SUPPRESSED for ALL producing_sources of its rule over that interval. O(n).
`functional_key` and `obligation_multiplicity` are DEFERRED; a tree containing a construct they would cover is
UNDECIDED with undecided_reason naming the rule. UNDECIDED is never promoted to REALIZABLE. body.verdict.
realizability is "CHECKED" only when every displayed tree carries a status object.

RESIDUAL under a cut is the set-valued object of the data contract, computed for both programs:
  goals_derivable = goal atoms in fix(P,S);  goals_severed = the complement over the goal library;
  corridors_open  = corridors of Psi not hit by S;  corridors_exhaustive = psi.complete and not grounding_capped.
Residuals are compared by SET INCLUSION only. Two incomparable residuals are reported as incomparable. There is
no total order on residuals, no better/worse string, and no scalarisation.

## cut

CORRIDOR ENUMERATION (the hitting-set loop, run once per program):

  def enumerate_psi(P, budget):
      psi, complete, nodes = [], True, 0
      while True:
          r, status, n = min_cardinality(psi, budget - nodes); nodes += n
          if status == "BUDGET_EXHAUSTED": complete = False; break
          S = canonical_select(psi, r)
          reachable, U, _ = reach(P, S)
          if not reachable: return (S, psi, complete, r, nodes, "EXACT_PSI_RELATIVE")
          tree = witness_tree(P, S, U)                 # deterministic AND/OR derivation of the goal
          mask = 0
          for inst in tree.instances():                # every instance used in the tree
              for term in inst.blockers: mask |= term  # popcount-1 terms: a plain clause
          if mask == 0:  return (S, psi, complete, r, nodes, "UNVERIFIED")   # an unblockable corridor
          psi.append(Corridor(mask))
          if len(psi) >= CORRIDOR_CAP: complete = False; break
      # cap or budget path
      return (best_subset_minimal(psi), psi, complete, r, nodes, "SUBSET")

  witness_tree is deterministic: a post-order construction that, for each derived fact, selects the supporting
  instance with the LOWEST instance_id among those whose body is fully derived, recursing on its body in declared
  body order. Ties are impossible because instance_id is a content hash of the whole instance.
  CORRIDOR_CAP = 4096 sets flag `corridor_cap` (bit 1: soundness + minimality + derived-suppressing).
  step_budget = 2_000_000 B&B nodes sets `budgets.budget_exhausted`.

CARDINALITY IS COUNTED IN RAISED CONTROLS, never in threshold atoms. A cut is stored canonically as one
(control_id, level) per raised control and is upward-closed: raising control k to level L puts atoms
x_{k,1}..x_{k,L} in the mask. A clause is hit iff the cut contains at least one of its atoms.

CANONICAL ATOM ORDER (the only order used for ordering, tie-breaking, serialisation and printing):
      x_{k,L} ≺ x_{k',L'}  iff  (control_id_k.encode("utf-8"), L) < (control_id_k'.encode("utf-8"), L')
  compared as raw bytes under LC_ALL=C, never a locale collation. control_id matches ^[a-z][a-z0-9_]{2,47}$.
  `rank` is the 0-based index in ≺ over LIVE atoms. The order is history-independent: inserting a control never
  reorders two pre-existing atoms.

BIT POSITIONS are a DIFFERENT thing and come from config/vs/catalog-bits.lock, an APPEND-ONLY registry:
      [[bit]] pos=0 control_id="egress_seg" level=1 state="live"
  A (control_id, level) keeps its pos forever. Removal sets state="tombstone"; the pos is never reused.
  max(pos) over live + tombstoned must be < 64. Gate `bits-lock-check` fails on any deletion, any renumber of an
  existing pos, or pos >= 64.
  THE NUMERIC VALUE OF A MASK IS NEVER A TIE-BREAK. The only permitted mask comparison in a decision path is
  popcount, used for cardinality bounding in the B&B. A lint fails on a mask value inside any sort key that
  feeds an output path.

MINIMUM CARDINALITY. min_cardinality(Psi, budget) is a deterministic branch-and-bound over SETS OF CONTROLS
(not atoms), because raising a control to its maximum level hits a superset of what any lower level hits:
  - candidate controls are considered in ≺ order of their level-1 atom;
  - bound: current |K| + ceil(number of unhit clauses / max clauses any single remaining control can hit);
  - node counter is deterministic and is compared against the step budget; there is no wall clock.
  Return (r, "EXACT"|"BUDGET_EXHAUSTED", nodes_consumed).

CANONICAL SELECTION at cardinality r, two phases, both order-independent by construction:
  phase 1  cut = []
           for control c in ≺ order of its level-1 atom:
               if len(cut) == r: break
               if feasible(Psi, cut + [c], r):        # the same B&B restricted to controls after c
                   cut.append(c)                      # c enters at its MAXIMUM level
  phase 2  for c in cut, in ascending rank order:
               while c.level > 1 and hits_all(cut with c lowered by one, Psi): lower c
           assert hits_all(cut, Psi) and len(cut) == r
Level-minimality is a HARD requirement, not a preference: for every raised control with level > 1, lowering it one
step while holding the others fixed must leave at least one clause unhit. The checker re-verifies this clause-wise.

TIE-BREAK (cut_cmp over canonical cuts, each a list of (rank, level) ascending by rank):
  1. fewer raised controls wins
  2. else lexicographic on the rank vector, smallest first differing rank wins
  3. else lexicographic on the level vector, weakest level wins
  4. else the cuts are equal
Because phase 1 walks ≺ ascending and takes the first extensible control, the result is the cut_cmp-minimum
admissible cut of cardinality r, independent of internal search order. Property test: 512 seeded permutations of
clause order, atom insertion order and instance order must produce byte-identical output.

WHAT THE CUT SEARCH MAY CLAIM:
  minimality = "EXACT_PSI_RELATIVE"  -- and only this -- when the hitting-set loop reached fixpoint, no cap fired
        and the B&B terminated inside budget. It renders as: "no smaller cut satisfies the enumerated corridor set".
  minimality = "EXACT_EXHAUSTIVE" requires that a fixpoint was actually run for EVERY cut of cardinality |S|-1 over
        the upward-closed lattice, that C(n_controls, |S|-1) <= 200000, and that budgets.exhaustive_ran is true
        and budgets.exhaustive_cuts_tested records the count. It is never inferred from |A| <= 64, which is a
        representation width and not a tractability statement.
  minimality = "SUBSET" when a cap or the budget fired: no control can be removed from this cut; smaller cuts were
        not ruled out.
  minimality = "UNVERIFIED" when no minimality probe ran.
WHAT IT MAY NEVER CLAIM: "the minimum cut", "minimum cut", "no smaller cut exists", "cardinality-minimal",
"prevented", "would have stopped". These are banned substrings with no allowlist and no rescuing suffix.
Minimality NEVER downgrades safety and safety NEVER downgrades minimality; they are independent fields.

BLINDNESS PREMIUM (a property of the corridor databases, NOT a difference of two chosen cuts):
  NEC(Psi) = { c : r(Psi over universe A minus atoms(c)) > r(Psi) }          # in EVERY minimum cut; infeasible counts as >
  OCC(Psi) = { c : exists L. 1 + r(Psi with clauses hit by x_{c,L} dropped) == r(Psi) }   # in SOME minimum cut
  B = NEC(Psi_max) \ OCC(Psi_min)
  Both are defined by the VALUES of optimisation problems, not by any argmin, so B is invariant to solver order,
  branch order and insertion order. Property test `prop_premium_invariant` over 512 seeded permutations is the
  proof artifact; a prose claim of invariance without it does not ship.
  Cost: |controls| + 1 extra min-cardinality solves per database, sharing the node budget. If any solve exhausts,
  the premium member is OMITTED and premium_suppressed_reason = "solver_budget".
  Precondition: B is published only when psi_min.complete and psi_max.complete and not grounding_capped and not
  budget_exhausted. Otherwise the whole `premium` member is ABSENT from the certificate -- not null, not [], not 0.
  `S_rob \ S_opt` is DELETED as a definition. The set difference of the two canonical representatives is a
  different object, is named `cut_delta_canonical`, and carries the literal caption "difference between two
  canonical representatives; not the blindness premium". The two must never appear in the same component or export.

DECISIVE OBSERVATION SET: for every corridor in Psi_max \ Psi_min, collect the licence ids in its witness tree.
Making (source, interval) live removes every licence on that source overlapping the interval, hence every silent
instance resting on it, hence those corridors. Search exhaustively for a minimum-cardinality set of
(source_id, t0_ns, t1_ns) pairs killing all of them up to size 3; beyond that, greedy set cover reported with its
`ln n + 1` bound printed INLINE with the set and flag `greedy_cover` (bit 6, derived class, does NOT block ROBUST).
Rendered as: "Making iam_audit live over [t0, t1] (NN minutes) removes corridor c:xxxx and with it priv_approval."
It may never be phrased as "enabling source s removes control c" unless this computation actually returned s as
sufficient for every corridor that forced c.

The redundancy index and the cost frontier are OUT OF SCOPE for the slice (see minimum_viable); their keys are
absent from the certificate and listed in verdict.derived_suppressed.

## certificate

FILE: runs/<run_id>/cert.spcert. Content is exactly `{"body":{...},"cert_hash":"blake3:<64hex>"}` in SCF-lite,
UTF-8 no BOM, LF only, one trailing LF, never compressed, <= 64 MiB. The first 26 bytes are exactly
`{"body":{"schema":{"v":` so a checker can reject a wrong-shaped file before parsing.

cert_hash = blake3(scf(body)). It covers the canonical serialisation of `body` and NOTHING else, so the
self-reference is well founded and is recomputable in one pass. No field is carved out of the hash.

WHAT EACH HASH COVERS (body.inputs; all values "blake3:<64hex>" unless noted):
  rules_hash        the canonical AST encoding (CAE) of rules.toml plus the per-rule metadata record
                    (rule_id, head, body sorted, producing_sources sorted, silent_possible, attck sorted).
                    NOT the file bytes: reflowing a comment must not invalidate an archived certificate.
  rules_text_hash   the raw bytes of rules.toml. Forensic only, recorded, NEVER enforced. When rules_hash matches
                    and this differs the checker prints a NOTE and continues.
  guard_ast_hash    blake3 of guards.cae, the canonical guard AST DAG including slot numbering and bit assignment.
  controls_hash     CAE of the control catalog INCLUDING the level table.
  catalog_bits_hash blake3 of catalog-bits.lock. Bit positions are hashed, so a catalog edit that shifts bits
                    invalidates certificates -- which is why the lock is append-only.
  bundle_hash       the raw bytes of bundle.jsonl (already canonical after ingest).
  liveness_hash     the canonical bytes of liveness.json.
  profile_hash      the canonical bytes of the SourceProfile. Added because the profile determines every threshold.
  goal_hash         CAE of the goal library entry.
  er_hash           canonical bytes of er.json (config + output mapping). ER is load-bearing and must be pinned.
  instances_hash    canonical bytes of the published instance set, binding grounding_mode="replayed".
  seed              "0x%016x" string, never a JSON number.
  k                 u32 horizon in ticks.
  grounding_mode    "replayed" -- the honest statement of what the checker will do with `instances`.
  bundle_provenance "synthetic_generator_no_range".
  implementation    "python-reference".

SCOPE (body.scope) is exactly seven members and travels with every rendering:
  rules, controls, liveness, er, goal, bundle (each "b3:<64hex>", full 64 nybbles on the wire) and
  attacker:"non-adaptive" (the only value the checker accepts at v1).
The scope hashes must equal the corresponding inputs hashes; a mismatch is E-SCOPE-BIND / VRD-012.

VERDICT OBJECT: safety, witness_class (present-and-null unless UNSAFE), minimality, flags (array of names sorted by
BIT POSITION, never alphabetically, never a bitmask on the wire), derived_suppressed (sorted), realizability.

BODY MEMBERS, in full: schema, scope, inputs, verdict, atoms, cut, goals, invariant (present iff every goal is
severed), instances, licenses, silent, witnesses, psi, premium (or premium_suppressed_reason),
cut_delta_canonical, residual, budgets, observed_event_count, ghost_count. Unknown members are rejected.

BUDGETS are DETERMINISTIC STEP COUNTERS ONLY: fixpoint_steps, bb_nodes, step_budget, budget_exhausted,
exhaustive_ran, exhaustive_cuts_tested. A wall-clock budget would make flags machine-dependent and destroy
byte-identical replay; there is none anywhere in the pipeline.

ABSENT IS ABSENT. `premium`, `redundancy_index` and `frontier` are OMITTED, not null, not 0, not "N/A", not {},
whenever their preconditions fail. A field that is absent is absent from the hashed bytes. Every suppression
records its reason through premium_suppressed_reason (a closed enum: grounding_capped | corridor_cap |
solver_budget | horizon_truncated | er_ambiguous) or through verdict.derived_suppressed.

ENCODING RULES enforced on emit and re-checked on verify: no floats (lexical ban); JSON integers only for u8/u16/u32
and only in the declared width, no leading `+`, no leading zeros; masks, seeds and i64 nanosecond values as strings;
strings NFC and free of control characters; no duplicate keys; every declared-sorted array strictly ascending;
no JSON object used as a map with data-dependent keys -- every collection is an array of records sorted by a
declared total key, so hash-map iteration order cannot reach the bytes; nesting depth <= 8; no `null` value except
the one present-and-null witness_class; no trailing bytes after the closing brace and the single LF.

The certificate carries NO wall-clock timestamp, hostname, username, absolute path, pid, duration or `measured`
member. Timings belong in runs/<id>/manifest.json, which is not hashed into the certificate.

## checker

`python -m spectra_vs_verify <cert>.spcert --rules --controls --goal --bundle --liveness --er --profile`
is a PURE FILE-IN/FILE-OUT program. It performs no network I/O, no DNS, no database access, no subprocess
execution, and writes no file unless --out is given. It runs with TZ=UTC and LC_ALL=C. It never repairs,
normalises, sorts, deduplicates, defaults or infers anything: every deviation from canonical form is a rejection
with a reason code. Rejection is the default; if it cannot decide an obligation it rejects.

Obligations run in EXACTLY this order, stopping at the first failure. Each may assume every earlier one passed.

  O0  canonicity   re-serialise the parsed body; bytes must equal the input bytes exactly   E-CANON-*
                   (sub-codes: E-CANON-FLOAT, -DUPKEY, -ORDER, -NFC, -NULL, -WIDTH, -ESCAPE, -TRAILING)
  O1  cert_hash    blake3(scf(body)) == cert_hash                                            E-HASH-CERT
  O2  schema       v == "1.1"; checker version >= min_checker; profile == "eclipse-cert";
                   every required member present, no unknown member         E-SCHEMA-{MISSING,UNKNOWN,DOWNGRADE}
  O3  scope        all seven members present and well formed; attacker == "non-adaptive";
                   each scope hash equals the corresponding inputs hash                      E-SCOPE-BIND / VRD-005
  O4  inputs       recompute every hash in inputs over the files named on argv: rules CAE from rules.toml,
                   controls CAE, catalog-bits.lock, bundle bytes, liveness bytes, profile bytes, goal CAE,
                   er bytes, instances bytes                                                 E-INPUT-*
  O4b profile      re-evaluate binding gates B1..B6 from the hashed inputs                   PROFILE_* (exit 1)
  O5  atoms        n <= 64; the assign table matches the bit table implied by controls_hash + catalog_bits_hash;
                   bits unique; rank recomputed from the canonical atom order and compared                E-ATOM-*
  O6  cut          sorted ascending by rank, unique, upward-closed under x_{k,L+1} -> x_{k,L};
                   cardinality equals the number of RAISED CONTROLS; level-minimality verified clause-wise
                   in O(|Psi| * |S|)                                                          E-CUT-*
  O7  invariant    U strictly ascending and unique; every axiom fact of the published program is in U   E-INV-AXIOM
  O8  closure      for every published instance: if body ⊆ U and no DNF term is a subset of the cut mask,
                   then head ∈ U. One unsatisfied-body counter per instance, each body literal touched once  E-CLOSURE
  O9  goals        for each goal atom in the SAFE case: goal ∉ U                              E-GOAL-MEMBER
  O10 licenses     every silent instance cites licence ids that are IMPLIED by liveness.json: the cited interval
                   is covered by a non-LIVE run on that source in the pinned file, and every producing_source of
                   the instance's rule is non-LIVE over it                                    E-LICENSE-{UNIMPLIED,WINDOW}
  O11 ghost        observed_event_count excludes every silent instance and every GHOST fact; ghost_count equals
                   the number of GHOST facts                                                  E-GHOST-COUNT
  O12 witnesses    each witness's node list is one tree (children after their parent, one parent each, nothing
                   unreachable) and well founded (no instance on its own ancestor path), every OBSERVED node cites
                   an event_id present in bundle.jsonl with a matching record hash, every GHOST or LICENSED node
                   carries evidence:[] and a licence and matches its instance's ghost flag, and the tree
                   re-derives the goal under S \ {removed_control}                            E-WITNESS-{CYCLE,EVENT,CUT}
  O13 psi-hit      the published cut hits every clause of the published corridor database; each corridor_id
                   recomputes from its atom ranks                                             E-PSI-HIT
  O14 flags        the flag algebra of the verdict section, from spec/verdict/flags.toml       E-FLAG-* / VRD-00n
  O15 minimality   per verdict.minimality: EXACT_PSI_RELATIVE -> verify no cut of size < |S| hits all of Psi;
                   EXACT_EXHAUSTIVE -> additionally require budgets.exhaustive_ran and run a fixpoint for every
                   cut of cardinality |S|-1, permitted only while C(n_controls,|S|-1) <= 200000;
                   SUBSET / UNVERIFIED -> no obligation, print the ABSENCE of a claim    E-MIN-{UNEARNED,SMALLER}

COST. O0..O14 are linear: O(F + sum|body| + sum|witness| + |Psi| + |L|), with no structure traversed more than a
constant number of times. O15 IS NOT LINEAR and is fenced separately in the transcript with its own cost line.
The Part I claim that the whole check is one linear pass is false and is not repeated.

THE CHECKER NEVER SORTS. Sorting would mask an emitter that emits in hash-map order, which is the determinism
defect this whole design exists to prevent. It verifies sortedness in one scan and rejects on E-CANON-ORDER.
THE CHECKER NEVER ALLOCATES FROM A DECLARED COUNT: it allocates from observed array length, then compares to any
declared count and rejects on E-LIMIT-COUNT. It never decompresses; a known compression magic in the first two
bytes is E-LIMIT-COMPRESSED.

EXIT CODES: 0 ACCEPT, 1 REJECT (reason code on stderr and in --json), 2 usage or I/O error. There is no --force,
no --skip, no --ignore-hash-mismatch; adding one is a review-blocking change.

INDEPENDENCE, STATED HONESTLY. `spectra_vs_verify` imports nothing from `spectra_vs`; a gate walks the AST of every
module in the checker package and fails on any import whose root is `spectra_vs`. The only shared artifacts are the
on-disk formats and the field table generated from config/vs/cert-schema.toml. This is module independence, not
implementation independence: both sides are Python written by the same author from the same text, so a shared
misreading of a rule or a guard is invisible to the checker. The slice must say this in these words and must never
describe the checker as "the independent Go checker" or as independent validation.

ADVERSARIAL CORPUS (fixtures/vs/certs/adversarial/, byte-frozen, each produced by a committed mutation script from
a named positive certificate). `make vs-cert-corpus` asserts the EXACT reason code per row; a wrong code is as much
a failure as a wrong verdict. Minimum rows: tampered_cut -> E-CLOSURE; invented_invariant -> E-CLOSURE;
shrunk_invariant -> E-INV-AXIOM; goal_in_u -> E-GOAL-MEMBER; witness_phantom_event -> E-WITNESS-EVENT;
witness_cyclic -> E-WITNESS-CYCLE; witness_wrong_cut -> E-WITNESS-CUT; unlicensed_silent -> E-LICENSE-UNIMPLIED;
license_window_widened -> E-LICENSE-WINDOW; ghost_counted -> E-GHOST-COUNT; truncated_psi -> E-PSI-HIT;
psi_unsorted -> E-CANON-ORDER; hash_mismatch_rules -> E-INPUT-RULES; hash_mismatch_cert -> E-HASH-CERT;
scope_stripped -> E-SCHEMA-MISSING; scope_mismatch -> E-SCOPE-BIND; float_smuggled -> E-CANON-FLOAT;
mask_as_number -> E-CANON-WIDTH; duplicate_keys -> E-CANON-DUPKEY; unknown_field -> E-SCHEMA-UNKNOWN;
null_value -> E-CANON-NULL; trailing_bytes -> E-CANON-TRAILING; flagged_robust -> VRD-001;
premium_under_cap -> E-FLAG-DERIVED; exact_unearned -> E-MIN-UNEARNED; profile_self_calibrated -> PROFILE_SELF_CALIBRATED.
POSITIVE CONTROLS ARE MANDATORY: fixtures/vs/certs/positive/ holds at least three certificates that must be
ACCEPTED -- one ROBUST/EXACT_PSI_RELATIVE, one OPTIMISTIC_ONLY, one UNSAFE with witnesses -- otherwise the corpus
could be passed by a checker that rejects everything.
REASON-CODE LIVENESS: every code declared in the checker must be produced by at least one corpus file; an
unreachable code fails the build.
MUTATION LIVENESS: injected checker bugs (skip O8, accept an unsorted U, ignore VRD-001, widen a licence window by
one tick, drop the level-minimality check) must each turn a NAMED gate red. A green gate is evidence only if a
broken implementation turns it red.

## verdict

THREE INDEPENDENT AXES. safety answers "is the goal derivable under this cut"; minimality answers "what is claimed
about |S| and subsets of S"; scope answers "relative to what". No value on one axis implies any value on another.
A cut can be exactly minimal and unsafe; a cut can be safe and of unknown minimality. `cert.mode` does not exist.

SAFETY ALPHABET, with constructibility conditions:
  ROBUST           goal ∉ fix(P_max, S).  Constructible only when F ∩ SOUNDNESS_MASK == ∅ and the P_max fixpoint
                   terminated without hitting any deterministic budget.
  OPTIMISTIC_ONLY  goal ∉ fix(P_min, S) and goal ∈ fix(P_max, S). Constructible whenever the P_min fixpoint
                   terminated.
  UNSAFE           goal ∈ fix(P_min, S), with a witness tree whose every leaf is a real EventId present in the
                   hashed bundle.
  INDETERMINATE    the fail-closed sink: none of the other three is constructible.
UNSAFE carries a mandatory witness_class: OBSERVED (no GHOST anywhere in the tree), LICENSED (at least one silent
AND-node; the tree depicts a hypothesis, not an observation, and realizability passed), CONTESTED (forced by
er_ambiguous). Emitting UNSAFE/LICENSED without GHOST markers on the affected nodes is forbidden, and no rendering
may collapse OBSERVED and LICENSED into one word.

MINIMALITY ALPHABET: EXACT_EXHAUSTIVE, EXACT_PSI_RELATIVE, SUBSET, UNVERIFIED, with the earning conditions in the
cut section. EXACT_* requires corridor_cap ∉ F and atoms_over_budget ∉ F.

CLOSED FLAG SET, nine flags at fixed bit positions, generated from config/vs/flags.toml. Bits 9..15 are reserved
and must be zero. Adding a flag is a schema version bump, never an in-place edit.
  bit 0 grounding_capped                       class S       blocks ROBUST
  bit 1 corridor_cap                           class S,M,D   blocks ROBUST; caps minimality at SUBSET; suppresses derived
  bit 2 atoms_over_budget                      class M       caps minimality at SUBSET; does NOT block ROBUST
  bit 3 er_ambiguous                           class S       blocks ROBUST; forces witness_class CONTESTED on UNSAFE
  bit 4 quarantined_records                    class S       blocks ROBUST (dropped records manufacture blind windows)
  bit 5 license_voided_by_suspected_tampering  class S       blocks ROBUST; ALWAYS FALSE in this slice (no DCG pass)
  bit 6 greedy_cover                           class D       does not block ROBUST; forces the approximation factor inline
  bit 7 sampled_matrix                         class R       does not block a per-run ROBUST; blocks aggregate claims
  bit 8 profile_missing                        class S       blocks ROBUST
SOUNDNESS_MASK = bits {0,1,3,4,5,8} = 0x013B, defined once and generated, never hand-copied.

ALGEBRA:
  A1  ROBUST requires F ∩ SOUNDNESS_MASK == ∅
  A2  UNSAFE requires a witness tree with all leaves real EventIds
  A3  witness_class OBSERVED requires er_ambiguous ∉ F and no GHOST node in the witness
  A4  witness_class CONTESTED is required if er_ambiguous ∈ F
  A5  minimality ∈ {EXACT_EXHAUSTIVE, EXACT_PSI_RELATIVE} requires corridor_cap ∉ F and atoms_over_budget ∉ F
  A6  EXACT_PSI_RELATIVE requires Psi reached fixpoint
  A7  derived_suppressed ⊇ {redundancy_index} if corridor_cap ∈ F or grounding_capped ∈ F
  A8  derived_suppressed ⊇ {pareto_frontier} if no costs file was supplied
  A9  scope is total: all six hashes present, non-empty, well formed; attacker == "non-adaptive"
  A10 if A1 fails and neither OPTIMISTIC_ONLY nor UNSAFE is constructible, safety = INDETERMINATE
Note the asymmetry and do not "fix" it: soundness flags block the universal claim (ROBUST) but not the witnessed
existential claim (UNSAFE), because a witness over real EventIds survives under-approximation. er_ambiguous is the
exception, because a bad merge fabricates the leaves themselves, so it degrades the witness class instead.

DECISION FLOW (the only permitted control flow):
  scope total? -- no --> error, NO verdict emitted
       | yes
  F ∩ SOUNDNESS_MASK == ∅ ?
       | yes                                   | no
  goal ∉ fix(P_max)?                      goal ∈ fix(P_min) with witness?
   | yes -> ROBUST                          | yes -> UNSAFE (class per A3/A4)
   | no  -> goal ∈ fix(P_min)?              | no  -> INDETERMINATE
            | yes -> UNSAFE
            | no  -> OPTIMISTIC_ONLY

WHAT MAKES ROBUST UNCONSTRUCTIBLE, AS A TYPE AND NOT AS PROSE:
  `Verdict` has private fields, no public constructor, no `Default`, and is serialisable but NOT deserialisable:
  reading a verdict from JSON goes through `VerdictProposal` and back through `Verdict.build`, so an untrusted file
  can never instantiate an illegal verdict. `Verdict.build` is the single constructor and returns an error, never a
  degraded value. In the Python reference this is a frozen dataclass whose __post_init__ raises unless it receives
  the module-private _SEAL sentinel; `Verdict()` raises VRD-010, `dataclasses.replace` is banned, and Safety has no
  __str__. Additionally, Safety.ROBUST can only be minted by a builder that has received a NoTamperToken, which the
  liveness stage produces only when zero sources are tamper_suspected and verdict_tamper_sensitive is false.
  Errors: VRD-001 ROBUST with soundness flags; VRD-002 UNSAFE without witness; VRD-003 OBSERVED witness contains a
  GHOST; VRD-004 exact minimality under a cap; VRD-005 incomplete scope or attacker != "non-adaptive";
  VRD-006 witness_class on non-UNSAFE; VRD-007 er_ambiguous without CONTESTED; VRD-008 flag name unknown,
  duplicated or out of bit order; VRD-009 reserved bits nonzero; VRD-012 scope hashes disagree with the inputs;
  VRD-014 derived_suppressed omits an entry required by A7/A8.

CONFORMANCE CORPUS (config/vs/verdict/conformance/*.json), run against the emitter and the checker:
  1. Exhaustive flag sweep: all 2^9 = 512 flag subsets crossed with safety=ROBUST. Exactly the subsets disjoint
     from SOUNDNESS_MASK accept; every other subset rejects with VRD-001. This is a design constraint, not a
     measurement.
  2. Every flag alone crossed with all four safety values and all four minimality values.
  3. atoms_over_budget with ROBUST and SUBSET must ACCEPT. This is the regression test against re-conflating the axes.
  4. er_ambiguous with UNSAFE/OBSERVED rejects VRD-007; with UNSAFE/CONTESTED accepts.
  5. Each of the six scope hashes missing in turn rejects VRD-005; attacker:"adaptive" rejects VRD-005.
  6. Reserved bit 9 set rejects VRD-009. Flags sorted alphabetically instead of by bit rejects VRD-008.

RENDERING. The bare tokens ROBUST / OPTIMISTIC_ONLY / UNSAFE / INDETERMINATE may NEVER appear as a standalone
user-visible string. They appear only as enum values inside the verdict object, where the scope travels with them.
There is exactly ONE renderer per language, in one named file, and it is the only place where a safety token may be
adjacent to a string literal. No code path builds a verdict string by concatenation, f-string, format, template or
join. Short form:
  OPTIMISTIC_ONLY(rules@b3:1a2b3c4d, controls@b3:5e6f7a8b, liveness@b3:9c0d1e2f, er@b3:3a4b5c6d,
                  goal@b3:7e8f9a0b, bundle@b3:1c2d3e4f, non-adaptive) [EXACT_PSI_RELATIVE]
Long form is the same content in prose and ALWAYS ends with the sentence, which is not optional:
  "This is a statement about the model, not about the system."

NUMERIC-JUDGEMENT BAN, enforced over the certificate schema, the checker report, the CLI and any client types:
no field name containing confidence, score, severity, probability, likelihood, certainty, risk, criticality,
priority, weight, rating, grade, percentile, pct, percent, normalized_, strength. `redundancy_index` would be the
one allowlisted exemption (a Jaccard over corridors) and is not emitted by this slice at all.

## determinism

Byte-identical replay is a build gate, not an aspiration. `make vs-repro` runs the whole pipeline twice into two
temp directories, in fresh processes, with different PYTHONHASHSEED values and different input shuffles, and diffs
every artifact byte for byte. Any difference fails the build.

1. ENVIRONMENT. Every stage runs with PYTHONHASHSEED=0, TZ=UTC, LC_ALL=C, single-threaded. No stage reads the
   environment for anything that reaches an artifact. A CI grep gate fails on datetime.now, time.time, time.monotonic,
   Date.now, os.urandom, uuid.uuid1, uuid.uuid4, random.random, secrets.* anywhere under python/spectra_vs/ and
   python/spectra_vs_verify/, with an allowlist file requiring a per-line justification.

2. TIME. All time is i64 nanoseconds since the Unix epoch, carried as decimal strings in artifacts and as int in
   memory. No float time anywhere. No wall clock is read in any stage; every timestamp comes from the scenario's
   `epoch_ns` plus integer tick offsets. Timings are measured only into runs/<id>/manifest.json, which is not hashed
   into the certificate.

3. RANDOMNESS. Exactly one PRNG construction: a ChaCha20-equivalent stream seeded from
   blake3(seed_domain || scenario_hash || substream_name || seed_le). Every entity class and every noise family has
   its OWN named substream, so adding a substream never perturbs an existing one; there is a test that generating
   with N and N+1 principals leaves the first N principals' event streams byte-identical. The PRNG is threaded, never
   re-seeded mid-run, never cloned for parallel work inside a run. Draw counters are recorded and are asserted to be
   a function of (scenario, controls, seed). Parallelism across runs is allowed; parallelism inside a run is forbidden.

4. NO FLOATS, ANYWHERE, IN ANY DECISION PATH. Thresholds, quantiles, slack, ratios and the redundancy definition are
   exact integers or Fraction. Quantiles are exact-rank on order statistics; linear-interpolating estimators
   (R type 7, numpy default, Hyndman-Fan 4..9) are forbidden. A grep gate fails on `float(`, `/` used on ints without
   `//`, `math.`, `statistics.`, and on any decimal literal in the liveness, kernel, cut and cert modules.
   Integer arithmetic that could overflow i64 saturates, and saturation is observable (a counter in the manifest).

5. ORDERING. No output-affecting code path iterates a set or a dict whose order depends on insertion. Every exported
   collection is an array sorted by a declared total key, stated in the data contract. Where a natural key could tie,
   the key is extended with a content hash so ties are impossible. Sorting of strings is by UTF-8 bytes under
   LC_ALL=C, never by locale collation.

6. ORDER-INDEPENDENCE PROPERTIES, each a property test that must go red under the matching mutation:
   G-D1 permutation invariance: 1000 shuffled input orders of raw.jsonl produce an identical bundle_hash and an
        identical fact base.
   G-D2 rule-ordering invariance: 16 randomised rule evaluation orderings produce identical p_min.json bytes.
   G-D3 shard invariance: 1/2/4/8 shard splits of the input produce identical output.
   G-D4 liveness query-order invariance: permuting the envelope stage's interval queries yields a byte-identical
        liveness.json.
   G-D5 cut canonicity: 512 seeded permutations of clause order, atom insertion order and instance order yield
        byte-identical cut bytes.
   G-D6 premium invariance: 512 seeded permutations of clause and atom insertion order yield an identical B.
   G-D7 delta sensitivity: running at tick granularity Delta and Delta/2 must not change any OBSERVED verdict; a rule
        for which it does is time-fragile and is rejected at load.
   G-D8 cut stability: appending an unrelated control to the catalog (one that blocker-masks no instance grounded by
        the fixture) and regenerating catalog-bits.lock leaves the reported cut's (control_id, level) pairs, r, |Psi|
        and every corridor_id unchanged; pre-existing bits are unchanged and ranks shift only by insertion.

7. IDENTITY. Every identifier is content-addressed: event_id, fact_key, instance_id, entity_id, license_id and
   corridor_id are blake3 over canonical bytes, never counters, so reordering inputs cannot shift an id. Bit positions
   come from an append-only lock file, never from file position or compilation order.

8. NO PATCHING IN PLACE. A late-arriving or corrected record does not mutate a fact base: the run's epoch generation
   is incremented, the full fixpoint is recomputed from the extended bundle, and the two fact bases are diffed into
   runs/<id>/late_arrival_delta.json listing facts gained, facts no longer derived, and every certificate invalidated.

9. NO WALL-CLOCK BUDGETS. Every cap in the pipeline is a deterministic step counter (fixpoint_steps, bb_nodes,
   corridor count, iteration count). A timeout would make a flag machine-dependent, so there is none.

10. HASHING. blake3 only, via the blake3 PyPI package; if it cannot be imported the run aborts with a named error.
    Silently substituting another digest is forbidden, because the digest name is part of what the scope commits to.

11. GENERATED ARTIFACTS ARE COMMITTED AND DRIFT IS GATED. guards.cae, catalog-bits.lock, the flag table and the
    cert field table are committed; `make vs-check` regenerates into a temp tree and runs a byte diff. Generated files
    carry a header naming the generator version and the hash they came from, and a gate fails if a generated path is
    edited without the hash changing.

## minimum_viable

THE ONE THING THAT MUST SURVIVE EVERY CUT: the slice exists to show (a) that missing telemetry becomes an EXPLICIT,
NAMED, RE-CHECKABLE LICENCE for an unobserved attacker step, and (b) the separation between a control that is
genuinely needed and a control that is in the cut ONLY because a sensor could not see. Anything that does not serve
those two is negotiable.

THE SMALLEST HONEST SYSTEM. One scenario family, `vs-01-token-pivot`, seeded, with two routes to one goal:

  Route A, fully observed at 100% telemetry:
    k1 token acquisition on the victim endpoint     emits nothing ever (no endpoint sensor exists)
    k2 refresh exchange at the IdP                  emits idp_auth
    k3 gateway call with the replayed token         emits gw_access
    k4 bulk resource read                           emits res_access
    corridor A atoms = {session_binding>=1, token_expiry>=1, rate_limit>=1, egress_seg>=1}
  Route B, present only as an escalation path:
    k5 admin role assumed with no preceding approval  emits iam_audit
    k6 admin export bypassing the egress path         emits res_access
    corridor B atoms = {priv_approval>=1}

  Five controls, two levels each except rate_limit: egress_seg, priv_approval, rate_limit, session_binding,
  token_expiry -> 9 atoms. Six sources: idp_auth (chained), iam_audit (chained), gw_access (sequenced),
  res_access (none), plus edr_host (none, declared, emits ZERO records) and one benign-noise source.
  Six rules plus two obligation axioms. Three temporal operators: seq-within, absence-before-within, distinct-over-window.

THE TWO CELLS THAT MAKE THE POINT. Run the pipeline at exactly two completeness levels with nested deletion sets:

  c=100%  iam_audit is live, an `iam.approval_granted` record exists, so R3's absence fires OBSERVED-negative and
          Route B is derivable in NEITHER program. Psi_min == Psi_max == {A}. r = 1. Canonical cut = {egress_seg>=1}.
          NEC(Psi_max) = {egress_seg}; OCC(Psi_min) = {egress_seg, rate_limit, session_binding, token_expiry}.
          BLINDNESS PREMIUM B = {} -- empty, because nothing is blind. That empty result is the control arm and must
          be shown, or the non-empty result below proves nothing.

  c=70%   the degrader deletes iam_audit across a window covering k5 and the approval record. Liveness classifies
          that window BLIND (B_GAP_EXCEEDS_THRESHOLD or B_UNBRACKETED, against the profile from the calibration run).
          P_min: no role_assumed observed, Route B absent, Psi_min still {A}, cut_min = {egress_seg>=1}.
          P_max: the whole window is non-LIVE on every producing source of R3, so a LICENSED silent instance is
          admitted and Route B appears. Psi_max = {A, B}. r(Psi_max) = 2, cut_max = {egress_seg>=1, priv_approval>=1}.
          NEC(Psi_max) = {priv_approval} (B is a singleton corridor). OCC(Psi_min) does not contain priv_approval.
          BLINDNESS PREMIUM B = {priv_approval}. That single line IS the central idea:
          priv_approval is in the robust cut not because anyone saw an escalation, but because for forty minutes
          nobody could have.
          Verdict pairing, from the same artifacts: prove with S = cut_min gives OPTIMISTIC_ONLY (severs in P_min,
          not in P_max); prove with S = cut_max gives ROBUST. Two verdicts, one bundle, one difference: what you
          could see.
          The decisive observation set then names (iam_audit, [t0,t1]) as the single observation whose liveness
          would remove corridor B and with it the premium.

MISSING TELEMETRY AS AN EXPLICIT LICENCE. `edr_host` is declared in sources.toml and never emits a record, so it is
INSUFFICIENT in the profile and therefore BLIND everywhere, fail-closed. Obligation axiom O2 (`token presented
implies token acquired`) is unsatisfied for step k1 and is licensed by that permanent BLIND window, producing a
GHOST fact `credential.held(cred, actor)` rendered as INFERRED, UNOBSERVED with its licensing source and window
inline. It contributes 0 to observed_event_count and 1 to ghost_count, which are two separate certificate members.
Contrast case, also mandatory: remove the obligation and the step becomes a `permanent_blind_spot` entry -- no
GHOST, no licence, and the honest admission that it is invisible rather than a pretty inferred node.

WHAT CAN HONESTLY BE CUT, AND WHAT EACH CUT COSTS:
  - The Docker range, all 15 range services, the isolation gates, the compose topology. FORCED: no Docker here.
    Cost: telemetry is generator-output, never service-output, so nothing about real service behaviour is shown.
  - The Rust kernel, the Go checker, the C guard VM, the Haskell oracle, the Z3 oracle, the four-backend
    guard-hash gate. FORCED: no toolchains. Cost: there is no cross-implementation agreement evidence at all.
  - The ML baseline arm and the entire LLM narrator. Cost: none to the central idea; they are a comparison arm and
    a phrasing layer, and the spec already requires the system to pass with both deleted.
  - Postgres, Redis, the HTTP API, the React UI, the degradation matrix beyond two cells, the sweep mode,
    the replay/counterfactual engine of section 24, hypothesis ranking and the competing-hypothesis machinery.
  - The redundancy index and the cost frontier: both are omitted entirely rather than approximated, and appear in
    verdict.derived_suppressed. Cost: none; a Jaccard over a possibly-capped corridor set is biased anyway.
  - The Bellman-Ford backdating / difference-constraint pass. Cost: real. Flag bit 5 is permanently false, and the
    slice must never claim it detects tampering, backdating or suppression of any kind.
  - Conjunctive blockers (C-SLICE-1). Cost: a step that only fails when two controls are both raised cannot be
    modelled; the general subset test stays in the code behind an assertion so the narrowing is visible.
  - Two of the four realizability checks (functional_key, obligation_multiplicity). Cost: trees touching those
    constructs are UNDECIDED, never silently REALIZABLE.
  - The 16-scenario catalog, the 1200-user population, the 5.6M-event volume targets, all published benchmarks.
    The slice publishes NO measured numbers at all.
  WHAT CANNOT BE CUT: the profile/calibration separation with gates B1..B6 (without it liveness self-calibrates and
  the whole result is circular), the fail-closed classification ladder R1..R11, the NEC/OCC definition of the
  premium (a difference of two chosen cuts is not a property of the problem), the certificate plus an independent
  module that re-checks it, the two-sided P_min/P_max bracket, GHOST accounting kept out of observed counts, and the
  verdict type that makes ROBUST unconstructible under a soundness flag.

DEFINITION OF DONE FOR THE SLICE: `make vs-demo` runs calibrate, then the c=100% and c=70% cells end to end, prints
the two premium results (empty, then {priv_approval}), emits two certificates, verifies both with the separate
checker package, runs the adversarial corpus with exact reason codes, runs the 512-case verdict conformance sweep,
and runs `make vs-repro` to prove every artifact is byte-identical across two fresh-process runs.

## forbidden_claims

- Never claim a Rust kernel exists, is built, is benchmarked, or produced any result. The kernel in this slice is Python and is labelled PYTHON REFERENCE IMPLEMENTATION everywhere it is named.
- Never claim a Go checker exists or that the certificate was independently verified in the sense of Part I section 25.2. The checker is a separate Python package with no imports from the kernel package; that is module independence, not implementation independence, and a shared misreading of a rule or a guard is invisible to it.
- Never claim the Docker cyber range, any of its fifteen services, its isolation guarantees, `make range-up`, or a boot-timing measurement exists. No container was built or run. Telemetry comes from a seeded synthetic generator and every manifest and certificate says so via bundle_provenance: synthetic_generator_no_range.
- Never present any number as measured. The slice publishes no benchmarks, no wall-clock timings, no event counts as results, no PR-AUC, no throughput, no peak RSS, no speedup. Every figure in a transcript is illustrative and is marked as such; a bare number in prose that looks like a metric is a review-blocking finding.
- Never claim a C guard VM, a Haskell admissibility oracle, a Z3 oracle, a four-backend guard-hash gate, or any cross-language agreement result. Only one guard front end exists.
- Never claim the ML baseline arm, the LLM narrator, the HTTP API, the React UI, Postgres projection, the replay/counterfactual engine, the sweep oracle, the degradation matrix from 100% to 30%, or the zero-false-ROBUST invariant across that matrix has been implemented or evaluated. Two completeness cells were run.
- Never say 'proved', 'formally verified', 'proven secure', 'guaranteed', or 'assurance' about anything. The certificate is a statement about a fixpoint over a hand-authored rule table, under a hand-authored control catalog, over the telemetry actually ingested, against a non-adaptive attacker.
- Never say a control 'prevented', 'would have prevented', 'would have stopped', or 'blocked' an attack. The only permitted phrasing is 'severs this chain in the model' or 'unreachable under cut S'.
- Never print 'minimum cut', 'the minimum cut', 'no smaller cut exists', or 'cardinality-minimal'. These are banned substrings with no allowlist. EXACT_PSI_RELATIVE renders as 'no smaller cut satisfies the enumerated corridor set'; SUBSET renders as 'no control can be removed from this cut; smaller cuts were not ruled out'.
- Never render a bare verdict token. ROBUST, OPTIMISTIC_ONLY, UNSAFE and INDETERMINATE may appear only inside the verdict object with the six scope hashes and the literal attacker=non-adaptive travelling with them, and the long rendering always ends 'This is a statement about the model, not about the system.'
- Never claim the slice detects suppression, tampering, backdating or log deletion. The difference-constraint pass is not implemented; flag bit 5 is permanently false. Suppression on a `none`-integrity source is undetectable in principle and is represented only as BLIND volume.
- Never describe a licence as an observation, or a GHOST as an event. Licences are permissions for unobserved steps. GHOSTs never enter observed_event_count, any alert count, any evidence count or any timeline rendered as observed; observed_count and ghost_count are separate fields and a single summed field is forbidden.
- Never call `S_rob \ S_opt` or `cut_delta_canonical` the blindness premium. The premium is NEC(Psi_max) \ OCC(Psi_min) and is omitted entirely when its completeness preconditions fail.
- Never say a premium control is 'needed because the sensor was blind' when its licences rest on calibration-deficiency reasons (B_PROFILE_INSUFFICIENT, B_REGIME_UNKNOWN, B_FORCED_NO_PROFILE_MODE, B_THRESHOLD_OVERFLOW, B_WINDOW_UNDERSAMPLED). The correct string is 'needed because this run was not calibrated for this source'.
- Never say 'enabling source s removes control c' unless the decisive-observation computation actually ran and returned s as sufficient for every corridor that forced c.
- Never emit or display a probability, confidence, likelihood, risk score, severity, criticality, priority, weight, rating, grade, percentile or any normalisation to [0,1], and never scalarise residual reachability into a number, a percentage or a progress bar.
- Never claim an ACCEPT from the checker says anything about the bundle's truthfulness, the correctness of entity resolution, the completeness of the control catalog, or that grounding found every instance. It says the certificate is internally consistent with the hashed inputs.
- Never claim a window is 'verified live', 'confirmed continuous', 'proven complete' or shows 'no data loss'. The supported string is 'no gap exceeding the calibrated threshold was observed, under profile <profile_id>, on a <integrity_class> source'.
- Never claim the calibration profile measures anything about real telemetry. It is a model of a seeded generator's emission behaviour under one scenario family.
- Never claim a ROBUST verdict holds against an adaptive attacker, and never claim a counterexample tree drawn from P_max depicts something that happened: P_max is a superset of realizable worlds and such a tree may depict an attack no consistent world realizes.
- Never describe the scenario as an attack that occurred. Every rendering of it carries the word 'simulated', and ATT&CK ids, if present, are read-only labels that never enter ranking, assembly or the certificate and are never aggregated into a coverage percentage.
- Never claim SPECTRA 'uses AI'. State exactly what exists: a deterministic Python reference kernel, and nothing else.
