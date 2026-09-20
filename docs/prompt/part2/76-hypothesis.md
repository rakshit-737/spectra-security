============================================================
76. THE ATTACK HYPOTHESIS OBJECT AND THE DEGRADED-RUN CONTRACT
============================================================

76.0 POSITION

This section owns two objects that Part I promised and never defined: the **Hypothesis** (the "attack hypothesis backed by explicit evidence" of the CORE IDEA) and the **DegradedState** (what the system does and shows when it cannot deliver the strong claim). Nothing else may define either.

OVERRIDES Part I: sections 17-19 end at the fact base, 20-21 at the state/hypergraph, 22-25 begin at controls and cuts. No Part I section constructs, ranks, binds evidence to, serves, renders or exports a hypothesis. From here on, the Hypothesis type defined in 76.2 is the only structure any layer may call a chain, a path, an attack story, a narrative, an incident, or a scenario reconstruction. Delete any competing struct.

OVERRIDES Part I: ECLIPSE §8's demo script assumes an uncapped, unflagged run and prints a bare verdict. 76.12-76.19 replace that assumption with a contract that fails loudly instead.

Directionality is fixed and non-negotiable:

```
   events ──► facts ──► hypergraph H ──► witness trees ──► Ψ (corridors) ──► cut S
   (17-19)   (17-19)     (20-21)          (ECLIPSE 4E)        (4E)           (4E)
                             │                  │               │             │
                             └──────────────────┴───────┬───────┴─────────────┘
                                                        ▼
                                              Hypothesis / HypothesisSet   (this section)
                                                        ▼
                                              API (35-38) ─ UI (39-42) ─ export ─ narration
```

A Hypothesis is a *rendering of provenance already computed*. The cut is never computed from a hypothesis, the ranking never feeds back into grounding or cut search, and no hypothesis field may influence any verdict. A build in which the kernel reads `Hypothesis` before emitting `Ψ` is wrong; enforce with a module-boundary lint (`make lint-layering`) that fails if the cut solver crate depends on the hypothesis crate.

76.1 VOCABULARY DELTA

| Term | Definition | Owner |
|---|---|---|
| Stage | One rule instance appearing in a derivation, with its head fact, its time bounds and its evidence binding | 76.2 |
| Hypothesis | A canonicalized, deduplicated set of rule instances that derives the goal fact under a declared program side, plus its ordered stage list | 76.2 |
| HypothesisSet | The enumerated set of hypotheses for one (run, goal, program side). Never has a winner | 76.9 |
| GHOST stage | A stage whose rule instance is silent (licensed), carrying zero observed EventIds | 76.5 |
| Corridor of h | The threshold-minimal blocker literals of h, i.e. the Ψ clause h induces | 76.7 |
| Rank key | A tuple of non-negative integers imposing a total order on a HypothesisSet | 76.8 |
| DegradedState | A monotone set of degradation codes attached to a run and to every artifact derived from it | 76.13 |

Add each row to the glossary table and to the naming lint. `chain`, `path`, `story`, `narrative`, `timeline` are banned as identifier stems in Rust, Go, Python and TypeScript; the lint fails the build on `grep -rniE '\b(attack_?chain|attack_?path|attack_?story)\b'` outside `docs/`.

76.2 THE HYPOTHESIS TYPE (NORMATIVE)

Rust is normative. Go, Python and TypeScript mirrors are generated from the JSON Schema in 76.3 and checked byte-equal in CI (`make schema-parity`).

```rust
pub struct HypothesisId([u8; 32]);        // 76.4
pub struct RuleInstId(u32);
pub struct StageOrd(u16);
pub struct Tick(i64);                     // integer ticks, the lattice declared by the determinism charter

pub enum ProgramSide { PMin, PMax }       // observed-only | observed ∪ licensed silent

pub enum StageEvidence {
    Observed { events: SmallVec<[EventId; 8]> },         // len >= 1, ascending, deduplicated
    Ghost    { license: LicenseId,
               basis: GhostBasis,
               obligation_trigger: Option<ObligationTrigger> },
}

pub enum GhostBasis { BlindWindow, Suppressed, Obligation }

/// Evidence that an obligation axiom FIRED. It is NOT evidence that the ghost step occurred.
pub struct ObligationTrigger { axiom_id: AxiomId, triggering_events: SmallVec<[EventId; 4]> }

pub struct Stage {
    ord: StageOrd,
    rule_inst: RuleInstId,
    rule_id: u16,
    head: FactId,
    dimension: DimensionId,
    t_lo: Tick, t_hi: Tick,
    parents: SmallVec<[StageOrd; 4]>,      // ords of the stages deriving this stage's body
    evidence: StageEvidence,
    blockers: u64,                         // threshold-literal mask, from the rule instance
    severed_by: u64,                       // blockers & cut, for the cut this view is bound to
}

pub struct Hypothesis {
    id: HypothesisId,
    schema_version: u16,                   // 1
    goal: FactId,
    program: ProgramSide,
    instances: Vec<RuleInstId>,            // canonical identity set, ascending, deduplicated
    stages: Vec<Stage>,                    // linear extension, ordering rule in 76.6
    corridor: CorridorId,                  // 76.7; the Ψ clause this hypothesis induces
    ghost_stage_count: u32,
    observed_stage_count: u32,
    observed_event_count: u32,             // distinct EventIds across Observed stages only
    licenses_used: Vec<LicenseId>,         // ascending, deduplicated
    rank_key: RankKey,                     // 76.8
    realizability: Realizability,          // 76.10
    derivation: DerivationRecord,
    degraded: DegradedState,               // 76.13; no Default impl, constructor takes it
}

pub struct DerivationRecord {
    hypergraph_hash: [u8; 32], liveness_hash: [u8; 32], rules_hash: [u8; 32],
    bundle_hash: [u8; 32], er_hash: [u8; 32], controls_hash: [u8; 32],
    goal_hash: [u8; 32], exclusions_hash: Option<[u8; 32]>, seed: u64,
    enumerator_version: u16, k_max: u16,
}

pub struct HypothesisSet {
    run_id: RunId, goal: FactId, program: ProgramSide,
    members: Vec<Hypothesis>,              // sorted by rank_key then id; NOT a ranking of truth
    enumeration_complete: bool,            // false => D8 is set
    rank_class_1_size: u32,                // size of the top tie class
    degraded: DegradedState,
}
```

NEGATIVE TYPE REQUIREMENTS, enforced by `make lint-no-scores` (a schema + AST lint over all five languages):

1. No `f32`/`f64`/`number`-typed field anywhere in these types or their serialized forms. Rejection is on the type, not the value.
2. No field whose name matches `(?i)(score|confidence|probab|likeli|belief|certain|plausib|weight|severity|risk|p_?value|percent|pct|ratio)`. This regex is committed at `lint/banned_field_names.re` and applies to Rust, Go, Python, TypeScript, SQL columns, OpenAPI properties and JSON Schema properties.
3. No field named `primary`, `best`, `top`, `winner`, `most_likely`, `selected`.
4. `Hypothesis::new` has no `Default` and takes `DegradedState` by value, so a hypothesis cannot be constructed without deciding its degradation state.

76.3 JSON SCHEMA (EXCERPT, NORMATIVE FOR THE WIRE)

```json
{ "$id": "https://spectra.local/schema/hypothesis/1.json",
  "type": "object", "additionalProperties": false,
  "required": ["id","schema_version","goal","program","instances","stages",
               "corridor","ghost_stage_count","observed_stage_count",
               "observed_event_count","licenses_used","rank_key",
               "realizability","derivation","degraded"],
  "properties": {
    "id":            {"type":"string","pattern":"^blake3:[0-9a-f]{64}$"},
    "schema_version":{"const":1},
    "program":       {"enum":["P_MIN","P_MAX"]},
    "realizability": {"enum":["REALIZABLE","NON_REALIZABLE","UNCHECKED"]},
    "stages": {"type":"array","minItems":1,"items":{"$ref":"#/$defs/stage"}},
    "rank_key": {"type":"array","minItems":6,"maxItems":6,
                 "items":{"type":"integer","minimum":0}},
    "degraded": {"$ref":"https://spectra.local/schema/degraded/1.json"}
  },
  "$defs": {
    "stage": { "type":"object","additionalProperties":false,
      "required":["ord","rule_inst","rule_id","head","dimension","t_lo","t_hi",
                  "parents","evidence","blockers","severed_by"],
      "properties": {
        "evidence": { "oneOf": [
          {"type":"object","additionalProperties":false,
           "required":["kind","events"],
           "properties":{"kind":{"const":"OBSERVED"},
                         "events":{"type":"array","minItems":1,
                                   "items":{"type":"string","pattern":"^ev:[0-9a-f]{16}$"}}}},
          {"type":"object","additionalProperties":false,
           "required":["kind","license","basis"],
           "properties":{"kind":{"const":"GHOST"},
                         "license":{"type":"string"},
                         "basis":{"enum":["BLIND_WINDOW","SUPPRESSED","OBLIGATION"]},
                         "obligation_trigger":{"$ref":"#/$defs/obligation_trigger"}}}]}}}}}
```

OVERRIDES Part I section 17.1.3: the 16-byte BLAKE3-128 `event_id` rendered as 32 hex digits, and the `^ev:[0-9a-f]{32}$` pattern in 18.7's finding-provenance schema and the 32-hex worked record in 19.3, are replaced by the 16-hex-digit form `^ev:[0-9a-f]{16}$` above, which is normative for the wire. An implementer emitting 32-hex ids produces stages that fail this schema outright, so no hypothesis export validates and 76.5.1's re-resolution against `bundle.jsonl` never runs.

`"number"` is forbidden anywhere in every SPECTRA schema; a schema lint (`make lint-schema-nofloat`) greps the compiled schema bundle for `"type": "number"` and fails.

76.4 IDENTITY AND HASH

`HypothesisId` is derived, never assigned:

```
canon(h) = "SPECTRA-HYP-v1\n"
         || program_side_byte                       // 0x00 P_MIN, 0x01 P_MAX
         || u32le(goal)
         || u32le(len(instances)) || u32le(i) for i in sort_ascending(instances)
         || derivation.hypergraph_hash || derivation.rules_hash || derivation.bundle_hash
         || derivation.liveness_hash  || derivation.er_hash    || derivation.controls_hash
         || derivation.goal_hash      || u64le(derivation.seed)

HypothesisId = blake3(canon(h))
```

Rules:
1. Identity is the **instance set**, not the stage list. Two derivations differing only in tree shape or traversal order are one hypothesis. Enumeration deduplicates on `HypothesisId` before ranking. OVERRIDES Part I section 19.5.1: the definition of a hypothesis as a *minimal* connected sub-DAG, and the step-5 prune of "any candidate that is a strict superset of another candidate with the same leaf set (non-minimal)", are replaced by deduplication on `HypothesisId` alone, with no minimality condition on the instance set. An implementer who keeps 19.5.1's minimality prune returns a strictly smaller set than this section's enumerator even on runs that never reach the cap.
2. `rank_key`, `stages`, `severed_by`, `degraded` and `realizability` are NOT hashed. Re-ranking or re-binding a cut does not change identity.
3. Cut-dependent views are addressed as `HypothesisId @ CutHash`, never folded into the id.
4. A property test asserts id stability under randomized rule-firing order, randomized enumeration seed and randomized `HashMap` capacity hints. `make test-hypothesis-determinism`.

76.5 EVIDENCE BINDING (THE RULE THAT MAKES THE OBJECT HONEST)

Every stage is exactly one of OBSERVED or GHOST. There is no third state and no partial state.

OVERRIDES Part I section 17.4: the three-valued `observed` status OBSERVED / LICENSED / UNDETERMINED — carried by 17.4.2's rule that an UNDETERMINED absence yields nothing in P_min and a licensed instance in P_max, by 17.4.3's `absence_undetermined` counter and `uses_undetermined_absence` run flag, by 18.7's schema enum and its SQL `CHECK (observed IN ('OBSERVED','LICENSED','UNDETERMINED'))`, and by 19.6.1's U(h) count of UNDETERMINED-supported edges — is replaced by the two-variant `StageEvidence` of 76.2, in which a stage is OBSERVED or GHOST and nothing else. An implementer who keeps the third value has no variant to serialize it into and will either drop those instances from every hypothesis, losing derivations Part I places in P_max, or record them as GHOST, which asserts a `LicenseId` implied by `liveness.json` that an UNDETERMINED absence need not have.

1. An OBSERVED stage carries at least one `EventId` that exists in `bundle.jsonl` under the hashed bundle. The checker (ECLIPSE §5) re-resolves every one; a dangling EventId is a certificate rejection, not a warning.
2. A GHOST stage carries **zero** EventIds in its `events` position. It carries a `LicenseId` that must be implied by `liveness.json`.
3. OVERRIDES Part I / ECLIPSE §9 vs §4C contradiction: obligation-induced silent instances are derived from observed events, and Part I never said what evidence they may cite. Resolution: the triggering events go in `obligation_trigger.triggering_events`, a field that is structurally separate from `evidence.events`, never counted in `observed_event_count`, and rendered with the fixed caption "axiom `<id>` fired on these events; the step itself was not observed". A GHOST stage may never surface an EventId in a position the UI renders as evidence of the step.
4. `observed_event_count` counts distinct EventIds from OBSERVED stages only. A unit test constructs a hypothesis of all-GHOST stages with populated obligation triggers and asserts `observed_event_count == 0`. `make test-ghost-accounting`.
5. Ghost basis is recorded, never inferred at render time: `BLIND_WINDOW`, `SUPPRESSED`, `OBLIGATION`.
6. Forbidden: "inferred evidence", "implied event", "reconstructed event", "probable step" as field values, captions or narration.

76.6 STAGE ORDERING

`stages` is a linear extension of the derivation DAG, computed deterministically:

```
order_stages(instances, H):
    dag  = subgraph of H induced by `instances`
    key(i) = (t_lo(i), t_hi(i), rule_id(i), head_fact_id(i), rule_inst_id(i))   # all integers
    # Kahn's algorithm with a binary heap ordered by key; ties impossible (rule_inst_id unique)
    out = []
    ready = min-heap of nodes with indegree 0, ordered by key
    while ready: n = pop(ready); out.push(n); for c in children(n): dec; if 0 push(c)
    assert len(out) == len(instances)                       # a cycle is a kernel bug
    for s in out: assert t_lo(parent) <= t_lo(s) for all parents   # time-indexing invariant
    return out
```

Both assertions abort the process with exit code 70 and a dump of the offending instance ids. They are not flags and not recoverable: time-indexed monotone grounding (ECLIPSE §3) makes them unreachable, so reaching them means the grounder is broken and no artifact from that run may be published.

OVERRIDES Part I section 19.2: the OBSERVES relation, which alone among the edge relations carries no tick condition and is defined as an edge from a later observation to the earlier GHOST it forces — the shape 18.3's R7 and 25.4's obligation construct by design — is replaced by an unconditional `t_lo(parent) <= t_lo(s)` invariant over every stage's `parents`. An implementer who follows 19.2 and records an obligation's triggering stage as a parent of the forced earlier stage gets exit 70 and a published-nothing run rather than a modelled backward-in-time edge, and must therefore not carry the OBSERVES edge into `parents`.

76.7 RELATIONSHIP TO CORRIDORS AND TO THE CUT

```
corridor_of(h) = { minimal threshold literal x_{k,ℓ} per control k
                   such that some stage of h has bit(x_{k,ℓ}) set in `blockers` }
```
Minimal means: if a hypothesis is blocked at level 2 and at level 3 of the same control, only `x_{k,2}` enters, since `x_{k,3} → x_{k,2}`. `CorridorId = blake3("SPECTRA-CORR-v1" || u64le(mask) || controls_hash)`.

OVERRIDES Part I section 19.5.2: the corridor clause as the raw union of `blockers` over a hypothesis — the same mask 25.6E computes as `corridor_mask(tree)` and 25.7 stores verbatim in the certificate's `psi` — is replaced by the threshold-minimal literal set above, and `CorridorId` is taken over that reduced mask. An implementer who unions raw blocker masks gets a different mask and therefore a different corridor identity for any hypothesis blocked at two levels of the same control, so 19.8.2(f)'s equality of the derived corridor set against the stored Ψ fails even though the sever test `S & mask != 0` still agrees under implication closure.

1. The map hypothesis → corridor is many-to-one and total. Every enumerated hypothesis has a corridor; every corridor in Ψ was induced by at least one witness tree.
2. A cut `S` **severs** h iff `S & corridor_mask(h) != 0`. `Stage.severed_by = blockers & S`; the **biting stage** is the lowest `ord` with `severed_by != 0`. The UI names it; the API returns its `ord`.
3. OVERRIDES Part I: 22-25 present cut search without any statement about what a cut means for a displayed chain. The binding is now one-directional and explicit: a HypothesisSet is always served **with respect to a named cut** (possibly the empty cut) and the response carries `cut_hash`. A hypothesis rendered without a `cut_hash` is a malformed response.
4. Forbidden inference: "S severs every hypothesis we enumerated" may **not** be rendered as "S severs the attack". The safety verdict comes from the fixpoint test under S over the whole program, never from the enumerated set. UI copy for the set is fixed at: "`<n>` of the enumerated hypotheses are severed at the stage shown. The verdict above comes from the fixpoint over the full program, not from this list." OVERRIDES Part I section 19.4.2: the per-hypothesis label "a hypothesis containing one or more GHOSTs is `OPTIMISTIC-ONLY` unless the ECLIPSE run was performed on `P_max` and returned ROBUST", printed on the hypothesis header line in 19.9's worked output, is replaced by a run-level typed verdict that carries its scope (76.14.2); `Hypothesis` has no verdict field and 76.19.11 forbids adding one. An implementer who renders that label per hypothesis is deriving a verdict from `ghost_stage_count` in the client without a scope binding, and fails `verdict-scope-required.spec.ts` and the reducer test in 76.12.5.

76.8 RANKING: THE EXPLICIT FORMULA AND THE PROBABILITY BAN

`RankKey` is a 6-tuple of non-negative integers compared lexicographically ascending. Lower sorts earlier. There is no arithmetic on the tuple, no normalization and no scalar collapse.

```
rank_key(h) = ( h.ghost_stage_count,          # fewer licensed steps first
                |h.licenses_used|,            # fewer distinct licenses first
                |h.instances|,                # shorter derivation first
                (t_hi_max(h) - t_lo_min(h)),  # tighter temporal span first, in ticks
                sum(rule_id(s) for s in h.stages),   # deterministic structural tiebreak
                first_u64_of(h.id) )          # total order, always breaks remaining ties
```

OVERRIDES Part I section 19.6.1: the 7-tuple rank(h) = ( G, U, L, S, E, D, T ) — ghost nodes, count of UNDETERMINED-supported edges, seconds of licensed blindness relied upon, summed per-source `source_rank` from `sources.toml`, edge count, temporal span in seconds, and a blake3_128 of the canonical edge id list — is replaced by the 6-tuple above: U and S are dropped, licensed blindness is counted as distinct licenses rather than seconds, the span is in ticks, and the final tiebreak is the first u64 of the `HypothesisId`. An implementer following 19.6.1 produces a different total order on the same set, ordering by seconds of blindness and by evidence quality where this section orders by license count and drops evidence quality entirely, which also leaves `source_rank` in `sources.toml` with no consumer.

1. The tuple is published verbatim in `docs/ranking.md`, in the OpenAPI description of the field, and in a UI tooltip that is also rendered as static text below the list. If the formula changes, `enumerator_version` increments and every prior certificate keeps its recorded version.
2. The ordinal shown to users is the 1-based position plus its tie class. Label is fixed: "rank (ordering rule, not a probability)". Banned labels: score, confidence, likelihood, certainty, plausibility, priority, severity, "most likely", "best explanation", star ratings, bar lengths proportional to rank, percentage.
3. Banned rendering: any visual encoding whose length, area, opacity or color intensity is a function of rank. A rank is an ordinal; a bar is a magnitude. Playwright test `hypothesis-no-magnitude-encoding.spec.ts` asserts no element in the hypothesis rail has a width, height or opacity that varies with rank.
4. Ranking is presentation-only. A gate re-runs the whole pipeline with the rank key components permuted and asserts the certificate hash, the cut, Ψ and every verdict are byte-identical. `make test-rank-is-cosmetic`.

Enumeration and exactness. The k-best enumerator is Lawler-style over the AND/OR hypergraph and is exact only with respect to an **additive** enumeration key `E(h) = (ghost_stage_count, |instances|, sum rule_id)`. `|licenses_used|` and temporal span are non-additive and therefore applied only as a stable re-sort of the enumerated set. State this in the certificate:

```
"enumeration": { "key": "E = (ghosts, instances, sum_rule_id)", "exact_wrt_key": true,
                 "rerank_applied": true, "k_max": 8, "enumeration_complete": false }
```
`k_max` is a declared constant (8), not a measurement. When the enumerator hits it, set D8 and 76.9 applies.

OVERRIDES Part I section 19.5.1: expansion of the AND/OR structure into candidate DAGs by choosing one alternative per OR node, capped at `max_hypotheses` (default 256) with the certificate flag `hypothesis_enumeration_capped`, is replaced by the Lawler-style k-best enumerator above with `k_max` = 8, whose cap sets the monotone degradation code D8 HYPO_RANK_TRUNCATED. An implementer who keeps the 256 cap and the flag enumerates up to thirty-two times as many hypotheses and reports the cap as certificate metadata, where 76.13 makes it a run-level degraded state that suppresses set-cardinality claims and counts as a failure in the ROBUST-yield metric of section 62.

76.9 COMPETING HYPOTHESES: A SET, NEVER A WINNER

1. The API, the UI and every export return a `HypothesisSet`. There is no endpoint, field or component that returns one hypothesis as "the" reconstruction.
2. If `rank_class_1_size > 1`, all members of the tie class are displayed at the same visual level, in id order, with the fixed caption "`<n>` hypotheses are tied at rank 1 under the ordering rule; the ordering rule does not distinguish them."
3. If `enumeration_complete == false`, the set header reads "at least `<k>` hypotheses; enumeration was truncated at k_max" and the phrase "all hypotheses" is unconstructible: the string table has no entry for it and the banned-phrase gate covers "the attack chain was", "the attacker did", "what actually happened".
4. Narration (the LLM boundary) receives the whole set or nothing. A narrator prompt containing exactly one hypothesis is a build failure of the narration harness. Every narrated sentence about a stage carries either its EventIds or the literal token `GHOST`. OVERRIDES Part I section 19.10: "an LLM may narrate an already-computed hypothesis" in the singular, and 21.10's exhaustive list of permitted narrator inputs — certificate JSON, cut, corridor list, counterexample derivation trees, license list, blindness premium, state timeline, provenance subgraph, degradation table, and no hypothesis set — are replaced by this rule: the narrator receives the whole `HypothesisSet` or nothing. Item 5 below does not cover this, being scoped to 39-42 and the demo script, so an implementer building the narrator from 21.10's closed list has no lawful way to pass the set at all, and one building from 19.10 passes exactly one hypothesis, which is a build failure of the narration harness.
5. OVERRIDES Part I: any place in 39-42 or in the demo script that speaks of "the reconstruction" in the singular is replaced by "the hypothesis set". The banned-phrase gate enforces it outside `docs/limitations/`.

76.10 REALIZABILITY GATE BEFORE DISPLAY

The critics established that P_max admits combinations of licensed silent instances that no single world realizes, and that a counterexample tree drawn from P_max may depict an impossible attack. OVERRIDES Part I: no hypothesis derived from P_max may be displayed, exported or narrated until it passes a realizability check.

```toml
# exclusions.toml — hand-authored, hashed into the certificate, one entry per constraint
[[mutex]]
id       = "session-issuer-unique"
kind     = "at_most_one"
selector = { rule_id = ["session.issued.idp", "session.issued.local"], key = "session_id" }
note     = "a session is issued by exactly one issuer; two silent issuances are not co-realizable"

[[mutex]]
id       = "fd-open-once"
kind     = "at_most_one"
selector = { rule_id = ["fd.open"], key = ["pid","fd"] }
```

```
check_realizable(h, exclusions):
    for c in exclusions:
        group = [s for s in h.stages if matches(c.selector, s)]
        buckets = group_by(key(c.selector), group)
        if any(len(b) > 1 for b in buckets): return NON_REALIZABLE(c.id, offending_ords)
    return REALIZABLE
```

1. `REALIZABLE` may be displayed. `NON_REALIZABLE` may never be displayed, exported or narrated; it is counted in `hypotheses_suppressed_non_realizable` and listed by id only in the certificate.
2. `UNCHECKED` (no `exclusions.toml`, or a parse failure) sets D9, and D9 suppresses the entire counterexample panel. A run with D9 may still produce a ROBUST safety verdict, because dropping non-realizable worlds only shrinks the hypothesis space and ROBUST quantifies over the superset; it may not produce any displayed attack.
3. Conservativeness statement, printed verbatim in the certificate and in `LIMITATIONS.md`: "ROBUST quantifies over a superset of realizable worlds and is therefore conservative for safety. Every artifact derived from P_max other than the safety verdict is filtered by the realizability check and is still only as complete as `exclusions.toml`."

76.11 API REPRESENTATION

```
GET  /v1/runs/{run_id}/hypotheses?program=P_MAX&cut={cut_hash}&limit=8&cursor=
GET  /v1/runs/{run_id}/hypotheses/{hypothesis_id}?cut={cut_hash}
GET  /v1/runs/{run_id}/hypotheses/{hypothesis_id}/stages?limit=200&cursor=
GET  /v1/runs/{run_id}/hypotheses/{hypothesis_id}/export?format=json|jsonl|dot
```

OVERRIDES Part I section 19.7.1: the path `GET /api/v1/runs/{id}/hypotheses`, and with it the `/api/v1` prefix Part I uses for every HTTP surface (20.14, 24.9, 25.11), is replaced by the `/v1` prefix on the four routes above. An implementer who mounts these under `/api/v1` serves paths the generated TypeScript client never calls, because 76.11.5 generates that client from this OpenAPI document and gates the build on drift.

```json
{ "run_id": "run_01J...", "goal": "fact:41207", "program": "P_MAX",
  "cut_hash": "blake3:9c4f...", "cut": ["session_binding>=2","egress_seg>=1"],
  "scope": "ROBUST(rules@blake3:1a..,catalog@blake3:7e..,licenses@blake3:c0..,non-adaptive)",
  "rank_rule": "E=(ghosts,instances,sum_rule_id); rerank=(ghosts,licenses,instances,span,sum_rule_id,id)",
  "enumeration_complete": false, "k_max": 8, "rank_class_1_size": 2,
  "degraded": { "codes": ["D4","D8"], "blocks_robust": false },
  "suppressed": { "redundancy_index": ["D4"], "minimality_claim": ["D4"] },
  "members": [ { "id": "blake3:5d0a...", "rank": 1, "rank_class": 1,
                 "ghost_stage_count": 1, "observed_stage_count": 6,
                 "observed_event_count": 14, "realizability": "REALIZABLE",
                 "corridor": "corr:blake3:2b7e...", "biting_stage_ord": 4 } ] }
```

1. Rules: `members` is always an array, even at length 1. There is no `primary`. Pagination is cursor-based on `(rank_key, id)`. Request size limits and the no-arbitrary-path rule for bundle references apply as specified for all ingest endpoints.
2. `X-Spectra-Degraded: D4,D8` is set on every response derived from a degraded run, including 200s, including `/stages`, including exports.
3. `?strict=true` returns **409 Conflict** with body `{"error":"degraded_run","codes":["D4","D8"],"detail":[...]}` instead of a degraded 200. The demo harness always sends `strict=true`.
4. PROVE is `202 Accepted` + poll; the poll response carries the DegradedState as soon as it is known, not only at completion, so the UI can raise the banner before the verdict lands.
5. The OpenAPI document is the source for the TypeScript client; a client-codegen drift gate fails the build. No endpoint returns a float. A contract test asserts every response body parses under a schema with `"number"` globally forbidden.

76.12 UI REPRESENTATION

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ !! DEGRADED RUN — D4 CORRIDOR_TRUNCATED, D8 HYPO_RANK_TRUNCATED              │
│ Minimality claim suppressed. Redundancy index suppressed. Hypothesis set is  │
│ incomplete. This run may not be cited as a result.        [why?] [codes]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ SAFETY: ROBUST      MINIMALITY: SUBSET (unverified under D4)                 │
│ scope: rules@1a.. catalog@7e.. licenses@c0.. non-adaptive                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ HYPOTHESIS SET — at least 8 hypotheses (truncated at k_max=8)                │
│ ordering rule, not a probability:                                            │
│ (ghosts, licenses, stages, span, Σrule_id, id)                               │
│                                                                              │
│  rank 1  [tie class of 2]   blake3:5d0a…   1 GHOST · 6 observed · 14 events  │
│  rank 1  [tie class of 2]   blake3:77c1…   1 GHOST · 6 observed · 12 events  │
│  rank 3                     blake3:9ee4…   3 GHOST · 5 observed ·  9 events  │
├──────────────────────────────────────────────────────────────────────────────┤
│ STAGES — blake3:5d0a…            cut: {session_binding>=2, egress_seg>=1}    │
│  1 ● identity   t=1042  idp.auth.success        ev:7c1a… ev:7c1b…            │
│  2 ● session    t=1050  session.issued          ev:7c44…                     │
│  3 ◇ credential t∈[1061,1188]  GHOST (licensed, not observed)                │
│      ╎ basis BLIND_WINDOW · license lic:iam_audit@[1061,1188]                │
│      ╎ axiom cred.used⇒cred.issued fired on ev:7d02… (the axiom fired;       │
│      ╎ the step itself was not observed)                                     │
│  4 ● privilege  t=1194  priv.escalate     ✂ SEVERED by session_binding>=2    │
│  5 ● network    t=1207  egress.connect          ev:7f31…                     │
└──────────────────────────────────────────────────────────────────────────────┘
observed events on this hypothesis: 14   (GHOST stages contribute 0)
```

Invariants, each with a named Playwright test:

1. GHOST stages are distinguished by glyph (`◇`), by dashed border, and by the literal words "GHOST (licensed, not observed)". Never by color alone. `ghost-not-color-only.spec.ts`.
2. Observed-event counters exclude GHOSTs at every zoom level, in the panel header, in the set summary and in every export. `ghost-excluded-from-counts.spec.ts`.
3. Verdict strings are never built by concatenation; they are formatted from a typed value that carries its scope. A verdict rendered without its scope line fails `verdict-scope-required.spec.ts`.
4. The degraded banner is persistent, non-dismissible, placed above the verdict, and reproduced in every screenshot export and in the PNG/SVG of the stage graph. `degraded-banner-persistent.spec.ts`, `degraded-banner-in-export.spec.ts`.
5. The verdict is never computed client-side. The client renders `safety`, `minimality`, `degraded` and `suppressed` exactly as received; a unit test asserts the reducer has no branch that derives a verdict from other fields.
6. No CDN fonts or assets. The hypothesis panel degrades to a summarized list above a declared node budget rather than attempting a force-directed layout.

76.13 THE DEGRADED-RUN CONTRACT: TRIGGER CATALOG

OVERRIDES Part I: Part I treats flags as certificate metadata, which makes tripping a flag a free escape hatch from the zero-false-ROBUST gate. From here on, degradation is a typed, monotone state with a class that determines exactly what it blocks, and a degraded run is counted as a **failure** in the ROBUST-yield metric of section 62, not as an abstention.

| Code | Condition | Detector | Class | Blocks ROBUST | Structurally suppresses |
|---|---|---|---|---|---|
| D1 GROUNDING_CAPPED | instance, entity or horizon cap reached in grounding | grounder counter vs declared cap | SOUNDNESS | yes | everything except the raw fact base view |
| D2 ER_AMBIGUOUS | any ambiguous merge/split emitted by entity resolution | ER report | SOUNDNESS | yes | hypothesis set, cut, premium |
| D3 BASELINE_PROFILE_MISSING | `baseline-arrival.json` absent, unparsable or hash mismatch | liveness pass | COMPLETENESS (fails closed to BLIND) | no | blindness premium, decisive observation set |
| D4 CORRIDOR_TRUNCATED | corridor cap or deterministic step budget exhausted in the hitting-set loop | solver counter | MINIMALITY | no | redundancy index, minimality claim, "no smaller cut exists", "all corridors" |
| D5 COVER_GREEDY | decisive observation set fell back to greedy beyond exact size | cover routine | PRESENTATION | no | nothing; forces inline approximation-factor text |
| D6 MINIMALITY_SUBSET | `|A| > 64` or B&B step budget exhausted | cut solver | MINIMALITY | no | "minimum cut", "cardinality-minimal" |
| D7 COSTS_ABSENT | `costs.toml` absent or empty | frontier stage | PRESENTATION | no | the entire Pareto frontier (disabled, never unit-defaulted) |
| D8 HYPO_RANK_TRUNCATED | enumerator hit `k_max` | enumerator | COMPLETENESS | no | "all hypotheses", set-cardinality claims |
| D9 REALIZABILITY_UNCHECKED | `exclusions.toml` absent or unparsable | realizability gate | PRESENTATION | no | the whole counterexample panel and all P_MAX exports |
| D10 QUARANTINED_RECORDS | ingest quarantined ≥1 record | ingest ledger | SOUNDNESS unless mitigated | see rule | hypothesis set, premium |

Rule for D10: every quarantined record forces the ingest layer to mark its source BLIND over the quarantine interval. When every quarantine has been converted to a BLIND interval, D10 downgrades to COMPLETENESS and records `d10_mitigated: true`; otherwise D10 stays SOUNDNESS. Silent drops are forbidden outright, because a silent drop manufactures a blind window and therefore manufactures a license.

Rule for D7: with no costs file the frontier is **disabled**, not defaulted to unit cost. Any cardinality-only view is labelled "control count, not cost" in the axis label, the API field name (`control_count`, never `cost`), the export column and the narration. OVERRIDES Part I: ECLIPSE §4H's frontier is not produced at all in this state.

76.14 THE DEGRADED STATE TYPE AND ITS MONOTONICITY

```rust
bitflags! { pub struct DegradedFlags: u32 {
    const D1_GROUNDING_CAPPED = 1<<0;  const D2_ER_AMBIGUOUS       = 1<<1;
    const D3_BASELINE_MISSING = 1<<2;  const D4_CORRIDOR_TRUNCATED = 1<<3;
    const D5_COVER_GREEDY     = 1<<4;  const D6_MINIMALITY_SUBSET  = 1<<5;
    const D7_COSTS_ABSENT     = 1<<6;  const D8_RANK_TRUNCATED     = 1<<7;
    const D9_REALIZ_UNCHECKED = 1<<8;  const D10_QUARANTINED       = 1<<9; } }

pub struct DegradeDetail { code: DegradedFlags, detector: &'static str,
                           measured: u64, limit: u64, remedy: &'static str }
pub struct DegradedState { flags: DegradedFlags, details: Vec<DegradeDetail> }

impl DegradedState {
    pub fn merge(&mut self, other: &DegradedState);   // union only
    // there is no clear(), no remove(), no Default::default() that means "clean"
    pub fn clean() -> Self;                            // explicit, greppable, auditable
    pub fn blocks_robust(&self) -> bool;               // any SOUNDNESS-class flag set
}
```

1. Monotone: flags are set-once and union-propagated. Every derived artifact takes the DegradedState of its inputs by construction. A lint fails on any code path that constructs `DegradedState::clean()` outside the two permitted sites (run start, and the unit-test builder).
2. Verdict algebra, unconstructible-by-typing:
```rust
pub struct SoundnessClean(());                       // private field: only this module can mint
pub fn attest(d: &DegradedState) -> Result<SoundnessClean, Blocked> { /* Err if blocks_robust */ }
pub enum Safety { Robust(SoundnessClean, Scope), OptimisticOnly(Scope), Unsafe(Scope) }
pub enum Minimality { Exact, Subset, Unverified }     // independent field, never fused with Safety
```
OVERRIDES Part I: safety and minimality are separate certificate fields. A `subset_minimal_only` downgrade may no longer suppress an honest safety result, and a soundness flag may no longer be laundered into a merely weaker minimality string.
3. The Go checker rejects, with a distinct non-zero exit code per case: a certificate whose `safety == ROBUST` while any SOUNDNESS flag is set (exit 3); a certificate whose verdict string lacks its scope binding (exit 4); a certificate carrying a suppressed field with a non-null value (exit 5); a certificate whose `degraded.codes` is not a superset of the codes in its inputs' manifests (exit 6). Each has an entry in the adversarial certificate corpus and must be REJECTED.

76.15 SUPPRESSED FIELDS: EXACT SEMANTICS

Suppression is by **omission plus an explicit sentinel**, never by zero, empty array, `null`, or a default.

| Suppressed field | Codes that suppress it | Wire form | UI form |
|---|---|---|---|
| `redundancy_index` | D1, D4 | key absent; `suppressed.redundancy_index:["D4"]` | "suppressed (D4): computed over a truncated corridor set" |
| `minimality_claim` | D1, D4, D6 | key absent | "SUBSET / UNVERIFIED" with the reason code, never "minimum" |
| `blindness_premium` | D1, D2, D3, D10-unmitigated | key absent | panel replaced by reason text |
| `decisive_observation_set` | D1, D2 | key absent | panel replaced by reason text |
| `pareto_frontier` | D7 | key absent | "disabled: no cost profile supplied" |
| `hypotheses` (P_MAX) | D9 | key absent | counterexample panel replaced by reason text |
| `hypothesis_set_cardinality` | D8 | replaced by `hypothesis_set_lower_bound` | "at least k" |

```json
"suppressed": { "redundancy_index": ["D4"], "blindness_premium": ["D2"] }
```
A consumer that finds a suppressed key present with a value must treat the artifact as corrupt. Contract test `suppressed-keys-absent.spec` asserts, for every code, that the key is absent rather than nulled.

76.16 BANNER SPECIFICATION

Fixed copy, one line per code, rendered above the verdict, non-dismissible, reproduced in exports, screenshots and the narration preamble:

```
D1  GROUNDING CAPPED — the fact base is incomplete. This run cannot be ROBUST.
D2  ENTITY RESOLUTION AMBIGUOUS — identities may be merged wrongly. This run cannot be ROBUST.
D3  BASELINE ARRIVAL PROFILE MISSING — liveness failed closed to BLIND. Blindness results suppressed.
D4  CORRIDOR ENUMERATION TRUNCATED — minimality and the redundancy index are suppressed.
D5  OBSERVATION COVER IS GREEDY — approximation factor ln n + 1 applies to the set shown below.
D6  MINIMALITY IS SUBSET-ONLY — do not read the cut as a minimum cut.
D7  NO COST PROFILE — frontier disabled. Counts below are control counts, not costs.
D8  HYPOTHESIS ENUMERATION TRUNCATED — the set below is incomplete.
D9  REALIZABILITY UNCHECKED — counterexamples are withheld; they may depict impossible worlds.
D10 RECORDS QUARANTINED — <n> records rejected at ingest; see the quarantine ledger.
```

The banner header is always the literal string "DEGRADED RUN" plus the codes. It is never colored-only, never an icon-only chip, never a toast, never collapsed behind a tooltip. D5's approximation factor is inline text next to the set, not in a tooltip.

76.17 FAIL LOUD IN THE DEMO

OVERRIDES Part I: ECLIPSE §8's demo path has no degraded branch; Part I therefore permits the demo to quietly render a weaker claim in a strong frame. It does not.

1. `make demo` sets `SPECTRA_STRICT=1`. Under strict mode the pipeline **aborts** on any degradation code with exit 65, printing the trigger table and the remedy for each. There is no fallback render and no partial demo.
2. `make demo` additionally verifies that the printed input hashes equal the committed expected hashes, and aborts on mismatch.
3. `make demo-degraded` exists and is a first-class, golden-transcript target: it runs a fixture engineered to trip D4 and D8 and asserts the banner, the suppressed keys and the exit behaviour. Showing the degraded path is a feature; hiding it is the failure mode.
4. Pre-recorded terminal output is banned. Both transcripts are regenerated in CI and diffed against `tests/golden/demo.txt` and `tests/golden/demo-degraded.txt` with timings and hashes normalized by a declared filter whose rules are committed.

All numerals in the two transcripts below are illustrative, not targets; CI regenerates them from actual execution.

```
$ make demo
spectra prove --scenario fixtures/held-out/h-004 --strict
  ingest     records=18422 quarantined=0
  liveness   sources=7 blind_windows=3  baseline=blake3:41cc… OK
  grounding  instances=2104 cap=65536 (illustrative, not a target)
  envelope   silent=57 licenses=3
  cut        safety=ROBUST  minimality=EXACT  |S|=2
  scope      ROBUST(rules@blake3:1a3f…, catalog@blake3:7e02…, licenses@blake3:c04d…, non-adaptive)
  hypotheses enumerated=4 complete=true realizable=4 rank_class_1=2
  degraded   none
  cert       blake3:3f9a… -> out/cert.json
$ spectra verify out/cert.json
OK closure verified (2104 instances) · goal unreachable under S · 2/2 witnesses valid
OK no cut of size 1 satisfies Psi · degraded flags: none · scope binding present
exit 0
```

```
$ make demo-degraded
spectra prove --scenario fixtures/degraded/d-002 --strict
  cut        safety=ROBUST(candidate)  minimality=SUBSET
  degraded   D4 CORRIDOR_TRUNCATED  measured=512 limit=512 (illustrative, not a target)
             D8 HYPO_RANK_TRUNCATED measured=8   limit=8
FATAL strict mode: run is degraded; refusing to present a degraded run as a result.
      suppressed: redundancy_index(D4) minimality_claim(D4) hypothesis_set_cardinality(D8)
      remedy: raise corridor cap in run.toml, or accept a SUBSET minimality claim with --no-strict
exit 65
```

76.18 GATES

| Gate | Target | Fails when |
|---|---|---|
| Hypothesis determinism | `make test-hypothesis-determinism` | id or stage order varies across rule-firing order, seed or capacity hints |
| Ghost accounting | `make test-ghost-accounting` | a GHOST contributes to `observed_event_count`, or an obligation trigger appears in an evidence position |
| Rank is cosmetic | `make test-rank-is-cosmetic` | permuting rank components changes any certificate byte |
| No scores | `make lint-no-scores` | a float or a banned field name appears in any schema, type, column or API property |
| Layering | `make lint-layering` | the cut solver depends on the hypothesis crate |
| Realizability | `make test-realizability` | a NON_REALIZABLE or UNCHECKED hypothesis reaches any display, export or narration path |
| Degraded monotonicity | `make test-degraded-monotone` | a derived artifact carries fewer codes than its inputs |
| Verdict algebra | `make test-verdict-algebra` | ROBUST is constructible with a SOUNDNESS flag set, or a verdict string is built by concatenation |
| Suppression | `make test-suppression` | a suppressed key is present, nulled, zeroed or defaulted |
| Banner | `make test-ui-degraded` | banner missing, dismissible, color-only, or absent from an export |
| Demo integrity | `make demo`, `make demo-degraded` | strict mode renders a degraded run, or a golden transcript drifts |
| Checker rejection | `make test-adversarial-certs` | a certificate in the corpus with ROBUST + soundness flag, a missing scope binding, or a present-but-suppressed field is ACCEPTED |

76.19 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS

1. Do not attach any probability, confidence, likelihood, score, severity, priority or percentage to a hypothesis, a stage, a ghost, a license or a corridor, in any layer, including internal debug output.
2. Do not present one hypothesis as the reconstruction. Do not use "the attack chain", "what happened", "the attacker then", "most likely path", "best explanation".
3. Do not let a GHOST stage display an EventId in an evidence position, and do not count a ghost in any observed-event total.
4. Do not display, export or narrate a hypothesis whose `realizability` is not `REALIZABLE`.
5. Do not say "severed the attack" when only the enumerated set was checked. Say "severed at stage k in `<n>` enumerated hypotheses"; the verdict is separate.
6. Do not say "minimum cut", "cardinality-minimal" or "no smaller cut exists" when D4 or D6 is set. Do not say "all corridors" or "all hypotheses" when D4 or D8 is set.
7. Do not default a missing cost profile to unit cost. Do not label a control count as a cost.
8. Do not clear, downgrade, hide, collapse or summarize a degradation code. Do not render the banner as color, icon or toast alone.
9. Do not implement strict mode as a warning. A strict-mode degraded run exits non-zero and produces no rendered result.
10. Do not treat a degraded run as an abstention in the research metrics: it counts against ROBUST yield in section 62, so tripping a flag is never a cheap way to pass the zero-false-ROBUST invariant.
11. Do not add a hypothesis field that influences grounding, licensing, cut search, Ψ or any verdict. The hypothesis layer is read-only with respect to the kernel.
12. Do not claim that a hypothesis is what occurred. The only supportable claim is: "this set of rule instances derives the goal atom under the hashed inputs, with these observed EventIds and these licensed GHOST steps, under the declared rule table and catalog, against a non-adaptive attacker."
