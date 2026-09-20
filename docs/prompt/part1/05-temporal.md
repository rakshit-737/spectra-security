============================================================
17. TEMPORAL REASONING ENGINE
============================================================

17.0 MANDATE

Implement a temporal reasoning engine whose output is a monotone, time-indexed
fact base. "Sort events by timestamp and look at the next one" is not an
implementation of this section and must not ship. Every operator below is
defined with a closed-form semantics, a state bound, and a determinism
obligation. The engine is the producer of the hypergraph consumed by section 19
and grounded by the ECLIPSE kernel (see section 12 for ECLIPSE architecture and
section 20 for the certificate format).

17.1 TIME MODEL

17.1.1 Represent all time as `Instant = i64` nanoseconds since Unix epoch, UTC.
  Forbid `f64` time anywhere in the reconstruction core. Forbid timezone-local
  values past the ingest boundary (see section 8). A `chrono`/`datetime` object
  may exist in adapters only.

17.1.2 Carry three independent clocks per record, never collapse them:

  | Clock      | Symbol   | Meaning                                    | Trust |
  |------------|----------|--------------------------------------------|-------|
  | event time | `t_evt`  | instant the source asserts the act occurred | low   |
  | ingest time| `t_ing`  | instant SPECTRA durably received the record | high  |
  | sequence   | `seq`    | per-source monotone counter in BLAKE3 chain | high  |

17.1.3 ORDERING SEMANTICS. Define the canonical total order on events as the
  lexicographic tuple:

      order_key(e) = (t_evt(e), source_id(e), seq(e), event_id(e))

  `event_id` is the 16-byte BLAKE3-128 content address from section 8, so the
  order is total even for byte-distinct records sharing all three prior fields.
  Two runs over the same bundle must produce the same order key sequence. Assert
  this with a property test over 1000 shuffled input permutations.

17.1.4 SKEW ENVELOPES. `sources.toml` declares, per source, a skew envelope
  `skew(s) = [lo_s, hi_s]` in nanoseconds. A record from `s` asserting `t_evt`
  is treated as having occurred somewhere in `[t_evt + lo_s, t_evt + hi_s]`.
  All window and sequence operators evaluate over these intervals, not points.
  An operator that requires a strict order between two intervals that overlap
  must not fire; it emits `order_indeterminate` and the pair is handed to 19.7
  as a competing-chain ambiguity, never silently resolved.

17.1.5 BACKDATING DETECTION. Build the difference-constraint graph over
  asserted instants: every pair with a causally forced ordering (same session,
  same file descriptor, same TCP flow, same chained sequence) contributes an
  edge `t_a - t_b <= w`. Run Bellman-Ford. A negative cycle proves at least one
  timestamp is fabricated. Mark every record in the cycle `BACKDATED`, exclude
  it from licensing ECLIPSE silent instances, and emit the cycle itself as
  evidence. Output `liveness.json` carries the voided license set. This pass is
  a hard input to ECLIPSE stage A; do not duplicate it in the kernel.

17.1.6 TICKS. Derived facts are indexed at a tick granularity `Δ` declared in
  `engine.toml` (default 1_000_000_000 ns = 1 s). `tick(t) = t / Δ` (floor,
  integer). Write derived facts as `p(args)@k`. `Δ` is hashed into the
  certificate; changing `Δ` changes `rules_hash` and invalidates prior certs.

17.2 FACT ALGEBRA AND MONOTONICITY

17.2.1 A fact is `(predicate_id: u16, args: SmallVec<[EntityId;4]>, tick: u32)`,
  interned to a `FactId(u32)`. Facts are append-only within a run. Nothing is
  ever retracted.

17.2.2 Model expiry as non-derivation, never as deletion. Implement persistence
  as an explicit bounded generator:

      holds(F, K+1) :- holds(F, K), K+1 <= expiry_tick(F).

  `expiry_tick` is computed at the instant the fact is first derived, from
  declared TTLs and control levels, and stored with the fact. There is no rule
  that removes a fact and the linter (18.7, V11) rejects any attempt.

17.2.3 Because the program is monotone and time-indexed, the fixpoint is
  order-independent. Gate: a property test re-derives the full fact base under
  16 randomized rule evaluation orderings and 16 randomized input shard splits
  and demands byte-identical `facts.bin` and identical `FactId` assignment.

17.3 OPERATOR CATALOG

Implement exactly these operators. Each row is a build obligation: an
implementation, a formal test, and a documented state bound.

| Op            | Surface form                          | Semantics                                                                 | State bound            | Cost per event |
|---------------|---------------------------------------|---------------------------------------------------------------------------|------------------------|----------------|
| `window.slide`| `sliding(W, S)`                        | every `S` ticks emit over `[k-W, k]`                                      | `O(W/S)` panes         | `O(1)` amortized |
| `window.tumble`| `tumbling(W)`                         | disjoint `[nW, (n+1)W)`                                                   | 1 pane                 | `O(1)`         |
| `window.session`| `session(gap=G, key=K)`              | extend while inter-arrival `<= G`; seal at `G`                            | `O(active keys)`       | `O(1)`         |
| `window.hop`  | `hopping(W, H)`                        | overlapping panes at stride `H`                                           | `O(W/H)`               | `O(1)`         |
| `seq`         | `seq: [A, B, C] within W`              | exists `t_A < t_B < t_C`, `t_C - t_A <= W`, intervals non-overlapping     | `O(partial matches)`   | `O(m)`         |
| `seq.strict`  | `seq_strict: [A, B]`                   | as `seq` plus: no event matching `deny` between them                      | as `seq` + deny index  | `O(log n)`     |
| `absence`     | `absence: B before A within W`         | A holds and no B in `[t_A - W, t_A)` — see 17.4                           | `O(W)` index           | `O(log n)`     |
| `burst`       | `burst: count>=N over sliding(W,S)`    | pane cardinality threshold                                                | ring buffer `W/S`      | `O(1)`         |
| `rate`        | `rate: >=N per W`                      | `burst` normalized to per-`W`, integer arithmetic only                    | ring buffer            | `O(1)`         |
| `distinct`    | `distinct(field) >= N over W`          | exact distinct via per-pane `HashSet`; no HLL, no sketch                  | `O(distinct)`          | `O(1)`         |
| `continuity`  | `continuity(session_id)`               | see 17.6                                                                  | `O(active sessions)`   | `O(1)`         |
| `persist`     | `persist: until <expr>`                | 17.2.2                                                                    | `O(live facts)`        | `O(1)`/tick    |
| `align`       | `align(A, B, key, tol)`                | join two streams on entity key within skew tolerance `tol`                | `O(tol)` buffer        | `O(log n)`     |
| `first/last`  | `first(A) in window`                   | deterministic by `order_key`                                              | `O(1)`                 | `O(1)`         |

17.3.1 Forbid approximate structures anywhere in the reconstruction core:
  no HyperLogLog, no Bloom filter, no Count-Min sketch, no reservoir sampling.
  Exactness is a determinism requirement, not a performance tradeoff.

17.4 NEGATION OVER A WINDOW, AND ITS BLINDNESS INTERACTION

17.4.1 `absence: B before A within W` is the only permitted form of negation.
  It is stratified by time: the engine evaluates it only when the lookback
  window `[t_A - W, t_A)` is **sealed**, i.e. `watermark >= t_A` and no source
  contributing to `B` has an open late-arrival allowance covering the window.

17.4.2 BLINDNESS GUARD (mandatory, this is the load-bearing rule of this
  section). Let `prod(B)` be the set of sources able to produce `B`, from the
  rule's `producing_sources` (18.3). Let `live(s, I)` be the liveness predicate
  from ECLIPSE stage A. Then:

      absence(B, A, W) fires as OBSERVED   iff  ∀ s ∈ prod(B): live(s, [t_A - W, t_A))
      absence(B, A, W) fires as LICENSED   iff  ∀ s ∈ prod(B): ¬live(s, [t_A - W, t_A))
      otherwise                             ->  UNDETERMINED

  An OBSERVED absence produces an ordinary fact. A LICENSED absence produces a
  fact tagged with the `LicenseId` set and is treated by ECLIPSE as a silent
  instance member of `P_max` only (never `P_min`). An UNDETERMINED absence
  produces both: nothing in `P_min`, and a licensed instance in `P_max`.
  Never let an absence silently fire because a source was merely quiet.

17.4.3 Emit per-run counters `absence_observed`, `absence_licensed`,
  `absence_undetermined` into `liveness.json`. A run where
  `absence_licensed + absence_undetermined > 0` may still be ROBUST; a run that
  reports a finding derived from an UNDETERMINED absence in OPTIMISTIC mode must
  carry the flag `uses_undetermined_absence` and the UI must show it.

17.5 REPETITION AND BURST DETECTION

17.5.1 Thresholds are integers declared in the rule. No z-scores, no percentiles
  computed against an external baseline, no learned thresholds in the
  deterministic core. Where a rule needs a data-derived threshold, it may use
  only quantiles computed from **this run's own bundle**, the quantile
  definition must be named (`q99` = nearest-rank, inclusive), and the computed
  value must be written into the run output so it is auditable.

17.5.2 Implement three burst shapes:
  - `count`: `|pane| >= N`.
  - `accel`: `|pane_k| >= N and |pane_k| >= M * |pane_{k-1}|`, `M` integer ratio
    expressed as numerator/denominator pair to avoid float compare.
  - `interarrival`: `max gap in pane <= G and |pane| >= N` (machine-speed
    signature).

17.5.3 Burst facts carry the full `Vec<EventId>` of the contributing records,
  capped at `burst_evidence_cap` (default 64) with the cap and true count both
  recorded. A truncated evidence list must set `evidence_truncated: true`; a
  certificate whose witness depends on a truncated list is not ROBUST.

17.6 SESSION AND IDENTITY CONTINUITY

17.6.1 Continuity is a first-class derived object, not an attribute. Track a
  continuity chain per `(principal_id, session_id)` resolved by the entity
  resolver (section 11).

```
                 +-----------------------------------------+
                 |             session lifecycle           |
                 +-----------------------------------------+

   [NONE] --issue--> [ISSUED] --first_use--> [ACTIVE] --idle>G--> [DORMANT]
                        |                       |                    |
                        |                       +--use-------------->+
                        |                       |
                        |                 binding_mismatch
                        |                       v
                        |                  [DIVERGED] --use--> [DIVERGED]
                        |                       |
                     expiry                  revoke / expiry
                        v                       v
                    [EXPIRED]               [TERMINATED]

   GHOST transition: [NONE] --licensed_issue--> [ISSUED]
     admitted only when every source in prod(session.issued) is BLIND or
     SUPPRESSED over the interval; rendered as a dashed edge; never counted
     as an observed event.
```

17.6.2 Define `binding_mismatch` deterministically over declared binding
  dimensions: device fingerprint id, source ASN, TLS JA3 class, user agent
  class, client certificate thumbprint. A mismatch is the set-difference of the
  declared dimension tuple, and the fact records exactly which dimensions
  changed. Do not compute a "risk score" from the change.

17.6.3 IDENTITY CONTINUITY. Maintain `same_principal(a, b)` only where the
  entity resolver produced a deterministic join with a recorded join key and
  join rule id. Probabilistic or fuzzy identity merging is forbidden in the
  core; if the resolver reports `ambiguous`, the engine forks the hypothesis and
  section 19.7 handles the competing chains.

17.6.4 OBLIGATION AXIOMS. The engine ships approximately 40 hand-written
  obligation axioms of the form `used(X) => issued(X)`, `read(FD) => open(FD)`,
  `assumed(Role) => granted(Role)`, `egress(Flow) => connect(Flow)`. Each one
  lives in `rules/obligations/*.yaml`, each has a positive fixture proving it
  fires and a negative fixture proving it does not, and each unsatisfied
  obligation forces a GHOST node (19.4) plus a licensed silent rule instance in
  `P_max`. An obligation that is unsatisfied **and** unlicensed is reported as
  `permanent_blind_spot` and counted in the per-dimension blind-spot volume.

17.7 PERSISTENCE AND EXPIRY OF DERIVED FACTS

17.7.1 Every derived fact declares one of: `instant` (holds at one tick),
  `until(expr)` (bounded persistence), `sticky` (holds to horizon `k`).
  `sticky` requires an explicit justification string in the rule and is linted
  to a whitelist.

17.7.2 `expiry_tick` must be a pure function of already-derived facts and
  control levels. Token lifetime under `token_expiry>=2` differs from
  `token_expiry>=0`; that dependence is expressed in the guard AST so the
  concrete simulator and the ECLIPSE kernel derive the same expiry from one
  source (see section 13 on guard AST generation). Gate: for 256 randomized
  control configurations per fixture, simulator expiry ticks and kernel expiry
  ticks are identical.

17.8 EVALUATION MODEL

17.8.1 Incremental, streaming, deterministic, epoch-based semi-naive evaluation.

```
 bundle.jsonl
      |
      v
 +----------+   order_key    +-----------+   seal    +------------------+
 | decode   |--------------->| reorder   |---------->| epoch scheduler  |
 | + verify |   skew env     | buffer L  | watermark | (fixed Δ ticks)  |
 +----------+                +-----------+           +--------+---------+
                                                               |
                    +------------------------------------------+
                    v
            +---------------+      delta facts      +-------------------+
            | semi-naive    |---------------------->| window operators  |
            | rule engine   |<----------------------| (panes, seq NFA)  |
            +-------+-------+     matched instances +-------------------+
                    |
                    v
            +---------------+
            | provenance    |  AND-node = RuleInst (head, body, evidence,
            | hypergraph H  |               blockers mask, silent?)
            +-------+-------+  OR-node   = FactId
                    |
                    +--> section 19 chain assembly
                    +--> ECLIPSE grounding (stage B)
```

17.8.2 WATERMARK. `watermark = max(t_evt observed) - L`, where `L` is the
  declared bounded lateness per source, `L = max over sources of lateness_s`.
  Operators fire only on sealed intervals. Watermark advance is recorded in the
  run log.

17.8.3 LATE ARRIVAL RE-EVALUATION. A record arriving with
  `t_evt < watermark - L` is a violation of the declared lateness bound. Do not
  patch incrementally. Instead:
  1. Append the record to `quarantine.jsonl` with the violated bound.
  2. Increment `epoch_generation`.
  3. Recompute the full fixpoint from the extended bundle, deterministically.
  4. Diff the two fact bases and emit `late_arrival_delta.json` listing facts
     gained, facts no longer derived, and every certificate invalidated.
  A patched-in-place fact base is forbidden: it breaks byte-identical replay.

17.8.4 Bounded-lateness re-evaluation (`watermark - L <= t_evt < watermark`) is
  handled in-engine by re-opening only the affected panes, and the result must
  equal the full recomputation. Gate: differential test, 200 randomized late
  injection schedules, in-engine result == cold recomputation, byte-identical.

17.9 COMPLEXITY

Let `n` = events, `m` = derived facts, `R` = rule instances, `W` = max window
in ticks, `P` = concurrent partial sequence matches, `A` = control atoms.

| Stage                       | Time                     | Space          |
|-----------------------------|--------------------------|----------------|
| decode + order              | `O(n log n)`             | `O(L)` buffer  |
| liveness (17.1.5, ECLIPSE A)| `O(n log n)` + BF `O(VE)`| `O(sources·W)` |
| window operators            | `O(n)` amortized         | `O(Σ panes)`   |
| sequence NFA                | `O(n · P)`               | `O(P)`         |
| semi-naive fixpoint         | `O(Σ_i |body_i|)`        | `O(m + R)`     |
| absence index               | `O(n log n)`             | `O(W)`         |
| late full recompute         | same as cold run         | same           |

Publish measured `n, m, R, P, peak RSS, wall ms` per fixture in
`bench/temporal.json`. Do not publish asymptotics as if they were measurements.

17.10 DETERMINISM GATES (build fails otherwise)

  G17.1 Permutation invariance: 1000 shuffled input orders -> identical
        `facts.bin` BLAKE3.
  G17.2 Rule-ordering invariance: 16 orderings -> identical output.
  G17.3 Shard invariance: 1/2/4/8 shard splits -> identical output.
  G17.4 Late-arrival equivalence (17.8.4).
  G17.5 Δ sensitivity documented: running at Δ and Δ/2 must not change any
        `OBSERVED` verdict; if it does, the rule is time-fragile and is
        rejected at load with `V19`.
  G17.6 No floating-point in the core: CI grep gate over `spectra-core/` for
        `f32|f64`, allowlist file required with per-line justification.

17.11 NEGATIVE REQUIREMENTS

  - Do not implement general non-stratified negation, aggregation with
    retraction, or any operator that deletes a derived fact.
  - Do not use wall-clock `now()` anywhere in the core; all time comes from the
    bundle. CI gate greps for `SystemTime::now|time.time()|Date.now`.
  - Do not infer ordering from ingest time when event times are indeterminate.
  - Do not fire an absence because a source was silent; see 17.4.2.
  - Do not emit probabilities, confidences, "risk scores" or "severity scores"
    from this engine. It emits facts, licenses, and flags.
  - Do not let an LLM participate in fact derivation, window sealing, ordering,
    or license issuance.

============================================================
18. TEMPORAL RULE DSL
============================================================

18.0 POSITION AND NORMAL FORM

18.0.1 YAML under `rules/` is the **authoring** surface. `rules.toml` is the
  **compiled normal form** and is the artifact hashed into ECLIPSE certificates
  (section 20). Authors never hand-edit `rules.toml`; `spectra rules build`
  generates it, and CI fails if the checked-in `rules.toml` differs from a fresh
  build. One rule table, two consumers: the Rust matcher for the deterministic
  engine, and the guard AST for both the concrete control simulator and the
  ECLIPSE kernel.

18.0.2 Directory layout:

```
rules/
  registry.toml              # rule_id (u16) <-> name, append-only, never reused
  detect/
    cred_replay_new_device.yaml
    priv_esc_without_approval.yaml
    token_mint_burst.yaml
    svc_acct_cross_segment.yaml
    resource_enumeration.yaml
    egress_step_change.yaml
  state/
    session_rebound.yaml
    token_validity.yaml
  obligations/
    session_used_implies_issued.yaml
    fd_read_implies_open.yaml
    ... (~40)
  tests/
    <rule_name>/pos_001.yaml
    <rule_name>/neg_001.yaml
build/
  rules.toml                 # generated normal form  (hashed)
  guards.rs                  # generated guard AST    (hashed)
  matchers.rs                # generated matchers
```

18.1 FIELD REFERENCE

| Field                 | Type                    | Req | Meaning |
|-----------------------|-------------------------|-----|---------|
| `name`                | snake_case string       | yes | unique; matches filename |
| `rule_id`             | u16                     | yes | from `registry.toml`, immutable |
| `version`             | semver                  | yes | see 18.8 |
| `dimension`           | enum                    | yes | identity/session/credential/privilege/process/network/api/service/resource/trust |
| `head`                | fact template           | yes | derived predicate + arg bindings |
| `body`                | list of patterns        | yes | event or fact patterns, `<=4` after normalization |
| `temporal`            | operator block          | no  | one of the 17.3 operators |
| `guard`               | guard expression        | no  | boolean over control atoms + fact fields |
| `producing_sources`   | list of source ids      | yes | sources that could emit each body pattern |
| `silent_possible`     | bool                    | yes | may this instance be licensed when blind |
| `persistence`         | `instant\|until(e)\|sticky` | yes | 17.7 |
| `evidence`            | list of binding names   | yes | which bindings contribute `EventId`s |
| `causal_relation`     | enum (section 19.2)     | no  | relation this rule asserts between transitions |
| `provenance`          | object                  | yes | author, rationale, references, added_in |
| `severity_class`      | enum `{state_change, obligation, composite}` | yes | classification, not a score |
| `flags`               | list                    | no  | `time_fragile_ok`, `evidence_cap_ok` |

18.2 GUARD AND EXPRESSION GRAMMAR (EBNF)

```
guard      = expr ;
expr       = or_expr ;
or_expr    = and_expr { "or" and_expr } ;
and_expr   = unary { "and" unary } ;
unary      = [ "not" ] primary ;
primary    = control_lit | field_cmp | set_test | "(" expr ")" ;
control_lit= ident ">=" integer ;                (* x_{k,l} threshold literal *)
field_cmp  = path cmp literal ;
cmp        = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
set_test   = path ( "in" | "not in" ) "[" literal { "," literal } "]" ;
path       = ident { "." ident } ;
literal    = integer | quoted_string | duration | bool ;
duration   = integer ( "ns"|"us"|"ms"|"s"|"m"|"h"|"d" ) ;
```

Rules:
  - `control_lit` is the ONLY way a rule references a control. It compiles to a
    bit in the `blockers: u64` mask. `|A| <= 64` atoms total; the compiler emits
    `E-ATOMS-OVERFLOW` past 64 and the kernel downgrades per section 12.
  - Implication `x_{k,l+1} -> x_{k,l}` is generated by the compiler, not
    written by authors.
  - No arithmetic, no regex, no user functions, no float literals in guards.
    Guards must be decidable by bitmask + integer compare so the Go checker
    (section 20) can re-evaluate them independently.

18.3 WORKED RULES

R1 — sequence within a window (credential replay from a new device).

```yaml
name: cred_replay_new_device
rule_id: 101
version: 1.3.0
dimension: credential
head: credential.replayed(cred_id, device_b, t)
body:
  - as: auth_ok
    match: { event: auth.success, cred_id: $cred_id, device: $device_a }
  - as: reuse
    match: { event: auth.success, cred_id: $cred_id, device: $device_b }
temporal:
  seq: [auth_ok, reuse]
  within: 30m
  where: $device_a != $device_b
guard: "not (session_binding >= 1)"
producing_sources: [idp_auth, edr_host]
silent_possible: false
persistence: instant
evidence: [auth_ok, reuse]
causal_relation: PROPAGATES
severity_class: state_change
provenance:
  author: core
  rationale: >
    A bearer credential presented from two distinct device identities inside the
    binding window is a state transition of the credential dimension. With
    session_binding at level >=1 the second presentation is rejected at the IdP,
    so the guard blocks the instance.
  references: [docs/model/credential.md#replay]
  added_in: 0.4.0
```

R2 — negation over a window (privileged action with no preceding MFA).

```yaml
name: priv_action_without_mfa
rule_id: 102
version: 2.0.1
dimension: privilege
head: privilege.unverified_use(principal, action, t)
body:
  - as: act
    match: { event: api.privileged_call, principal: $principal, action: $action }
temporal:
  absence: { of: { event: auth.mfa_success, principal: $principal }, before: act, within: 8h }
guard: "not (mfa >= 2)"
producing_sources: [idp_auth]          # sources that could produce the ABSENT fact
silent_possible: true
persistence: instant
evidence: [act]
causal_relation: ENABLES
severity_class: state_change
provenance:
  author: core
  rationale: >
    Absence is evaluated only on a sealed window (17.4.1) and is downgraded to
    LICENSED when idp_auth is BLIND across the whole 8h lookback. mfa>=2 means
    step-up on every privileged call, which makes the absence impossible.
  references: [docs/model/privilege.md]
  added_in: 0.3.0
```

R3 — burst (token minting acceleration).

```yaml
name: token_mint_burst
rule_id: 103
version: 1.1.0
dimension: credential
head: credential.mint_burst(principal, t)
body:
  - as: mint
    match: { event: sts.token_issued, principal: $principal }
temporal:
  burst:
    shape: accel
    window: { sliding: { size: 5m, slide: 30s } }
    count_min: 20
    ratio: { num: 4, den: 1 }
guard: "not (rate_limiting >= 2)"
producing_sources: [sts_audit]
silent_possible: false
persistence: until(t + 15m)
evidence: [mint]
causal_relation: CREATES
severity_class: state_change
provenance: { author: core, rationale: "Machine-rate minting is a credential-dimension state change.", references: [], added_in: 0.3.0 }
```

R4 — tumbling aggregate step change (egress volume).

```yaml
name: egress_step_change
rule_id: 104
version: 1.0.2
dimension: network
head: network.egress_step(host, dst_zone, t)
body:
  - as: flow
    match: { event: net.flow_close, src_host: $host, dst_zone: $dst_zone, bytes: $b }
temporal:
  tumbling: 1m
  aggregate: { sum: $b, as: total }
  where: "total >= 536870912"
guard: "not (egress_seg >= 1)"
producing_sources: [net_flow]
silent_possible: true
persistence: instant
evidence: [flow]
causal_relation: PROPAGATES
severity_class: state_change
provenance: { author: core, rationale: "Integer byte threshold, no baseline learning.", references: [], added_in: 0.4.0 }
```

R5 — session continuity break.

```yaml
name: session_rebound_without_reauth
rule_id: 105
version: 1.2.0
dimension: session
head: session.rebound(session_id, t)
body:
  - as: use_a
    match: { event: session.use, session_id: $sid, binding: $bind_a }
  - as: use_b
    match: { event: session.use, session_id: $sid, binding: $bind_b }
temporal:
  continuity:
    key: $sid
    seq_strict: [use_a, use_b]
    deny: { event: auth.reauth, session_id: $sid }
    where: "$bind_a.device != $bind_b.device or $bind_a.asn != $bind_b.asn"
guard: "not (session_binding >= 1) and not (device_trust >= 2)"
producing_sources: [idp_session, proxy_access]
silent_possible: false
persistence: sticky
evidence: [use_a, use_b]
causal_relation: PROPAGATES
severity_class: state_change
flags: [sticky_justified]
provenance: { author: core, rationale: "Divergence persists to horizon: the session identity is permanently ambiguous once rebound.", references: [docs/model/session.md], added_in: 0.2.0 }
```

R6 — persistence with control-dependent expiry.

```yaml
name: token_validity
rule_id: 106
version: 1.0.0
dimension: credential
head: credential.valid(token_id, t)
body:
  - as: issue
    match: { event: sts.token_issued, token_id: $token_id, ttl_s: $ttl }
temporal: { instant: true }
persistence: |
  until(
    t + min($ttl,
      select(token_expiry >= 2, 900,
      select(token_expiry >= 1, 3600, 86400)))
  )
producing_sources: [sts_audit]
silent_possible: true
guard: ""
evidence: [issue]
causal_relation: CREATES
severity_class: state_change
provenance: { author: core, rationale: "Single source of expiry for kernel and simulator (17.7.2).", references: [], added_in: 0.2.0 }
```

R7 — obligation axiom (forces GHOST when unsatisfied).

```yaml
name: session_used_implies_issued
rule_id: 900
version: 1.0.0
dimension: session
kind: obligation
head: session.issued(session_id, t_before)
body:
  - as: use
    match: { event: session.use, session_id: $sid }
temporal:
  obligation:
    requires: { event: session.issued, session_id: $sid }
    before: use
    within: 24h
producing_sources: [idp_session]
silent_possible: true
persistence: instant
evidence: [use]
causal_relation: CREATES
severity_class: obligation
provenance: { author: core, rationale: "A used session was issued. If no issuance is observed and idp_session is BLIND/SUPPRESSED over the lookback, admit a GHOST issuance licensed by that window. If it is LIVE, record permanent_blind_spot and do NOT admit the ghost.", references: [docs/eclipse/licenses.md], added_in: 0.3.0 }
```

R8 — cross-segment service-account reuse (lateral propagation).

```yaml
name: svc_acct_cross_segment
rule_id: 107
version: 1.4.0
dimension: service
head: service.lateral_use(svc_id, zone_b, t)
body:
  - as: home
    match: { event: api.call, principal: $svc_id, zone: $zone_a, principal_class: service }
  - as: away
    match: { event: api.call, principal: $svc_id, zone: $zone_b }
temporal:
  seq: [home, away]
  within: 1h
  where: "$zone_a != $zone_b"
guard: "not (svc_acct_isolation >= 1) and not (net_segmentation >= 2)"
producing_sources: [api_gateway, net_flow]
silent_possible: true
persistence: until(t + 1h)
evidence: [home, away]
causal_relation: PROPAGATES
severity_class: composite
provenance: { author: core, rationale: "", references: [docs/model/service.md], added_in: 0.4.0 }
```

R9 — privilege escalation blocked by an approval control (multi-level guard).

```yaml
name: priv_esc_without_approval
rule_id: 108
version: 1.1.0
dimension: privilege
head: privilege.escalated(principal, role, t)
body:
  - as: assume
    match: { event: iam.role_assumed, principal: $principal, role: $role, role_class: admin }
temporal:
  absence: { of: { event: iam.approval_granted, principal: $principal, role: $role }, before: assume, within: 72h }
guard: "not (priv_approval >= 1)"
producing_sources: [iam_audit]
silent_possible: true
persistence: sticky
flags: [sticky_justified]
evidence: [assume]
causal_relation: AUTHORIZES
severity_class: state_change
provenance: { author: core, rationale: "This rule is the usual carrier of the blindness premium: when iam_audit is blind the absence is LICENSED, which is why credential_rotation can enter S_rob but not S_opt.", references: [docs/eclipse/blindness-premium.md], added_in: 0.3.0 }
```

R10 — exact distinct-count enumeration.

```yaml
name: resource_enumeration
rule_id: 109
version: 1.0.1
dimension: resource
head: resource.enumerated(principal, resource_class, t)
body:
  - as: get
    match: { event: api.call, principal: $principal, verb: get, resource_class: $rc, resource_id: $rid }
temporal:
  window: { sliding: { size: 10m, slide: 1m } }
  distinct: { field: $rid, min: 250 }
guard: "not (rbac >= 2) and not (rate_limiting >= 1)"
producing_sources: [api_gateway]
silent_possible: false
persistence: until(t + 10m)
evidence: [get]
causal_relation: ENABLES
severity_class: state_change
provenance: { author: core, rationale: "Exact HashSet distinct; sketches forbidden (17.3.1).", references: [], added_in: 0.4.0 }
```

18.4 COMPILATION PIPELINE

```
 rules/**/*.yaml
      |
      v
 [1] parse            serde_yaml -> RawRule            errors: E-YAML-*
      |
      v
 [2] resolve          registry.toml lookup, source ids, predicate arity
      |
      v
 [3] validate         V01..V24 (18.5)                  errors: E-VALID-*
      |
      v
 [4] normalize        - flatten body to <=4 patterns (introduce aux predicates)
      |               - expand seq/absence/burst to canonical operator IR
      |               - generate control implication clauses x_{k,l+1}->x_{k,l}
      |               - assign blocker bit positions, stable by (control, level)
      |               - canonical key order, LF newlines, no trailing space
      v
 [5] typecheck        binding types from schema/events.json; unbound var = error
      |
      v
 [6] emit
      +--> build/rules.toml      canonical normal form   -> rules_hash (BLAKE3)
      +--> build/guards.rs       guard AST enum + eval   -> shared by kernel
      +--> build/matchers.rs     operator state machines -> engine
      +--> build/rules.schema.json  for the Go checker
      |
      v
 [7] verify           re-parse rules.toml, re-emit, assert byte-identical
```

  - `spectra rules build --check` is a CI gate: nonzero exit if generated files
    differ from the working tree.
  - `rules_hash` appears in every certificate. Any rule edit invalidates every
    prior certificate, and `spectra verify` must report
    `RULES_HASH_MISMATCH` rather than silently re-grounding.

18.5 LOAD-TIME VALIDATION

Implement each check with a dedicated test that a violating rule is rejected.

| Code | Check |
|------|-------|
| V01 | `name` unique and equals filename stem |
| V02 | `rule_id` present in `registry.toml`, not reused, not renumbered |
| V03 | all body variables bound; head variables ⊆ body variables |
| V04 | body length after normalization `<= 4` |
| V05 | exactly one `temporal` operator block |
| V06 | every window/duration is a positive integer with a unit suffix |
| V07 | `producing_sources` non-empty and all ids exist in `sources.toml` |
| V08 | for `absence`, `producing_sources` names the sources of the ABSENT fact |
| V09 | guard parses; only threshold literals reference controls |
| V10 | every control/level in guards exists in `controls.toml` |
| V11 | no delete/retract effect anywhere (17.2.3) |
| V12 | `persistence: sticky` requires flag `sticky_justified` + rationale ≥ 80 chars |
| V13 | `evidence` names only bindings that appear in `body` |
| V14 | `provenance.rationale` non-empty for non-obligation rules |
| V15 | predicate arity consistent with all other rules using it |
| V16 | no cycle in the non-time-indexed dependency graph (time index must strictly increase around any cycle) |
| V17 | `silent_possible: true` requires at least one source able to be BLIND |
| V18 | rule has ≥1 positive and ≥1 negative fixture in `rules/tests/<name>/` |
| V19 | rule is not time-fragile: results identical at Δ and Δ/2 unless `time_fragile_ok` |
| V20 | total distinct control threshold atoms `<= 64` |
| V21 | no float literal, no regex, no arithmetic in guards |
| V22 | `causal_relation` present whenever the head feeds section 19 chain assembly |
| V23 | semver bumped when normalized IR changes (18.8) |
| V24 | obligation rules declare `kind: obligation` and a `within` bound |

18.6 RULE VERSIONING

  - `rule_id` is permanent and never reused; `registry.toml` is append-only and
    a CI gate diffs it for deletions or renumbering.
  - `version` is semver over the **normalized IR**, not the YAML text:
    - PATCH: provenance/rationale/reference edits only.
    - MINOR: additional evidence bindings, narrower guard (strictly fewer
      instances), new negative fixture.
    - MAJOR: head/body/temporal change, wider guard, `silent_possible` flip,
      persistence class change.
  - `spectra rules diff --from <git-ref>` prints the IR diff and the required
    semver bump; CI fails on an insufficient bump (V23).
  - Certificates record `{rule_id, version}` for every instance used, so a
    stored certificate names exactly the rule versions it depended on.

18.7 RULE PROVENANCE ON EVERY FINDING

Every finding carries this object; it is not optional and has no defaults.

```json
{
  "$id": "spectra/finding_provenance.schema.json",
  "type": "object",
  "required": ["rule_id","rule_name","rule_version","rules_hash","bundle_hash",
               "instance_id","evidence","producing_sources","observed","guard_mask",
               "engine_version","seed","delta_ns"],
  "properties": {
    "rule_id":       {"type":"integer","minimum":0,"maximum":65535},
    "rule_name":     {"type":"string","pattern":"^[a-z0-9_]+$"},
    "rule_version":  {"type":"string","pattern":"^\\d+\\.\\d+\\.\\d+$"},
    "rules_hash":    {"type":"string","pattern":"^blake3:[0-9a-f]{64}$"},
    "bundle_hash":   {"type":"string","pattern":"^blake3:[0-9a-f]{64}$"},
    "instance_id":   {"type":"string","pattern":"^ri:[0-9a-f]{32}$"},
    "observed":      {"enum":["OBSERVED","LICENSED","UNDETERMINED"]},
    "evidence": {
      "type":"array","minItems":0,
      "items":{"type":"object","required":["binding","event_id","source","t_evt"],
        "properties":{
          "binding":{"type":"string"},
          "event_id":{"type":"string","pattern":"^ev:[0-9a-f]{32}$"},
          "source":{"type":"string"},
          "t_evt":{"type":"integer"}}}},
    "evidence_truncated":{"type":"boolean","default":false},
    "licenses":{"type":"array","items":{"type":"object",
      "required":["license_id","source","t0","t1","basis"],
      "properties":{"license_id":{"type":"string"},"source":{"type":"string"},
        "t0":{"type":"integer"},"t1":{"type":"integer"},
        "basis":{"enum":["BLIND","SUPPRESSED"]}}}},
    "guard_mask":{"type":"string","pattern":"^0x[0-9a-f]{1,16}$"},
    "delta_ns":{"type":"integer"},
    "seed":{"type":"integer"},
    "engine_version":{"type":"string"}
  },
  "allOf": [
    {"if":{"properties":{"observed":{"const":"OBSERVED"}}},
     "then":{"properties":{"evidence":{"minItems":1}},
             "required":["evidence"]}},
    {"if":{"properties":{"observed":{"const":"LICENSED"}}},
     "then":{"properties":{"licenses":{"minItems":1}},
             "required":["licenses"]}}
  ]
}
```

Persist findings and their provenance:

```sql
CREATE TABLE rule_instance (
    instance_id     BYTEA PRIMARY KEY,           -- 16B blake3 of canonical form
    run_id          UUID        NOT NULL REFERENCES run(run_id),
    rule_id         SMALLINT    NOT NULL,
    rule_version    TEXT        NOT NULL,
    head_fact_id    INTEGER     NOT NULL REFERENCES fact(fact_id),
    tick            INTEGER     NOT NULL,
    observed        TEXT        NOT NULL CHECK (observed IN ('OBSERVED','LICENSED','UNDETERMINED')),
    blockers_mask   BIGINT      NOT NULL,
    evidence_trunc  BOOLEAN     NOT NULL DEFAULT FALSE,
    CONSTRAINT licensed_needs_license CHECK (
        observed <> 'LICENSED' OR EXISTS_LICENSE(instance_id)   -- enforced by trigger
    )
);

CREATE TABLE rule_instance_body (
    instance_id BYTEA   NOT NULL REFERENCES rule_instance(instance_id),
    ordinal     SMALLINT NOT NULL,
    fact_id     INTEGER  NOT NULL REFERENCES fact(fact_id),
    PRIMARY KEY (instance_id, ordinal)
);

CREATE TABLE rule_instance_evidence (
    instance_id BYTEA   NOT NULL REFERENCES rule_instance(instance_id),
    binding     TEXT     NOT NULL,
    event_id    BYTEA    NOT NULL REFERENCES event(event_id),
    PRIMARY KEY (instance_id, binding, event_id)
);

CREATE TABLE rule_instance_license (
    instance_id BYTEA   NOT NULL REFERENCES rule_instance(instance_id),
    license_id  BYTEA    NOT NULL REFERENCES license(license_id),
    PRIMARY KEY (instance_id, license_id)
);

CREATE INDEX ON rule_instance (run_id, rule_id, tick);
CREATE INDEX ON rule_instance_evidence (event_id);
```

18.8 RULE UNIT-TEST HARNESS

Every rule ships fixtures. A rule without both polarities fails V18 at load.

```yaml
# rules/tests/priv_action_without_mfa/pos_001.yaml
fixture: pos_001
rule: priv_action_without_mfa
rule_version: "2.0.1"
expect: FIRES
expect_observed: OBSERVED
delta_ns: 1000000000
sources:
  idp_auth:  { live: [[0, 40000]] }        # live across the whole lookback
  api_gw:    { live: [[0, 40000]] }
events:
  - { t: 100,   source: api_gw,   event: api.privileged_call, principal: p1, action: delete_bucket }
expect_facts:
  - { fact: "privilege.unverified_use(p1, delete_bucket)", tick: 100 }
expect_evidence:
  - { binding: act, matches: 1 }
expect_no_licenses: true
```

```yaml
# rules/tests/priv_action_without_mfa/neg_001.yaml  (preceding MFA present)
fixture: neg_001
rule: priv_action_without_mfa
expect: DOES_NOT_FIRE
sources: { idp_auth: { live: [[0, 40000]] }, api_gw: { live: [[0, 40000]] } }
events:
  - { t: 40,  source: idp_auth, event: auth.mfa_success,      principal: p1 }
  - { t: 100, source: api_gw,   event: api.privileged_call,   principal: p1, action: delete_bucket }
```

```yaml
# rules/tests/priv_action_without_mfa/neg_002.yaml  (guard blocks at mfa>=2)
fixture: neg_002
rule: priv_action_without_mfa
expect: DOES_NOT_FIRE
controls: { mfa: 2 }
sources: { idp_auth: { live: [[0, 40000]] }, api_gw: { live: [[0, 40000]] } }
events:
  - { t: 100, source: api_gw, event: api.privileged_call, principal: p1, action: delete_bucket }
```

```yaml
# rules/tests/priv_action_without_mfa/lic_001.yaml  (blind source -> LICENSED)
fixture: lic_001
rule: priv_action_without_mfa
expect: FIRES
expect_observed: LICENSED
sources:
  idp_auth: { live: [[0, 20]], blind: [[20, 40000]] }
  api_gw:   { live: [[0, 40000]] }
events:
  - { t: 100, source: api_gw, event: api.privileged_call, principal: p1, action: delete_bucket }
expect_licenses:
  - { source: idp_auth, covers: [20, 100], basis: BLIND }
expect_in_program: [P_max]
expect_not_in_program: [P_min]
```

Harness obligations:
  - `spectra rules test` runs every fixture, and additionally runs each positive
    fixture under all 256 sampled control configurations asserting monotone
    behaviour (antitonicity: raising a control never creates an instance).
  - Mutation gate: for each rule, the harness perturbs one temporal bound by
    ±1 tick and one guard literal by one level and asserts that at least one
    fixture flips. A rule whose fixtures are insensitive to its own parameters
    fails with `E-TEST-INERT`.
  - Coverage gate: every rule reached by at least one scenario fixture in
    `fixtures/scenarios/`; unreached rules are listed in
    `bench/rule_coverage.json` and may not appear in demo material.

```
$ spectra rules build --check && spectra rules test
rules: parsed 63 files, 63 rules, 41 obligations, 22 detections
atoms: 38 threshold literals over 11 controls  (limit 64, ok)
normal form: build/rules.toml  blake3:9c41e8a7...  (matches tree)
guards:      build/guards.rs   blake3:1d77b0ce...  (matches tree)
tests: 63 rules x (pos>=1, neg>=1) = 214 fixtures
  fired-as-expected      214/214
  antitonicity sweep     63 rules x 256 configs   ok
  mutation sensitivity   63/63 flipped
  delta-halving (V19)    63/63 stable
ok  1.84s
```

18.9 NEGATIVE REQUIREMENTS

  - Do not add an escape hatch: no `script:`, no `python:`, no `eval:`, no
    embedded regex engine, no user-defined function field. If a rule cannot be
    expressed in this DSL, extend the DSL and the checker together.
  - Do not allow a rule to reference wall-clock time, external HTTP, a database,
    or a model.
  - Do not let an LLM author, edit, select, order, or enable rules at runtime.
    An LLM may draft a YAML file for a human to review and commit; it must then
    pass the same load-time validation as any other rule.
  - Do not ship a rule with an empty `rationale`, a fixture-free rule, or a rule
    that exists only to make a demo scenario fire.
  - Do not encode a numeric threshold in the Rust matcher. Thresholds live in
    the YAML, flow through `rules.toml`, and are hashed.

============================================================
19. CAUSAL RECONSTRUCTION ENGINE
============================================================

19.0 TERMINOLOGY DISCIPLINE (enforced, not stylistic)

19.0.1 Use exactly this vocabulary in code identifiers, API fields, UI strings,
  log lines, documentation and commit messages:

| Use                            | Never use                                   |
|--------------------------------|---------------------------------------------|
| evidence-supported dependency  | "cause", "caused by", "proves causation"    |
| causal hypothesis              | "the attack", "what happened", "root cause" |
| inferred, unobserved (GHOST)   | "likely", "probably", "assumed"             |
| ranked first among N hypotheses| "most likely chain", "confidence 0.87"      |
| unreachable under cut S        | "prevented", "would have stopped the attacker" |
| corridor                       | "attack path that works"                    |

19.0.2 The word "proved" is reserved for exactly one referent: the ECLIPSE cut
  proof over the declared model, and only when a certificate verified. Every
  such string must appear adjacent to the scope disclaimer from section 12.9.

19.0.3 CI gate `check-terminology`: grep `src/ web/ docs/` for the banned column
  as whole words, with an allowlist file requiring a per-line justification.
  Include the allowlist in the repo so a reviewer can audit the exceptions.

19.1 SCOPE

The causal reconstruction engine converts the provenance hypergraph H from
section 17 into (a) a typed dependency graph over state transitions, (b) a set
of assembled causal hypotheses (chains), (c) a deterministic ranking over those
hypotheses, and (d) a dereferenceable evidence binding for every edge. It does
not detect anything, it does not decide any control, and it never introduces an
edge that is not licensed by a rule instance.

19.2 DEPENDENCY RELATION TAXONOMY

Exactly six relations. A relation is derived only when its derivation condition
is met by rule-instance provenance. Correlation, temporal proximity, embedding
similarity and "same-user heuristics" are not derivation conditions.

| Relation    | Meaning                                                    | Derivation condition                                                                                   | Required evidence |
|-------------|------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|-------------------|
| `ENABLES`   | transition u made transition v derivable                    | ∃ rule instance `ri` with `head(ri)=v` and `u ∈ body(ri)`; `tick(u) <= tick(v)`                         | body event ids of `u` + head evidence of `v` |
| `CREATES`   | u brought into existence the entity v operates on           | `ri` head is an existence predicate (`*.issued`, `*.granted`, `*.opened`, `*.spawned`) and v references that entity id | issuance record |
| `AUTHORIZES`| u is the authorization decision permitting v                | `ri` body contains an authorization predicate bound to the same `(principal, resource, action)` triple as v | decision record |
| `PROPAGATES`| an attacker-controlled artifact moved from u's scope to v's | identical artifact identity (token id, key id, file content hash, flow 5-tuple) appears in evidence of both, and `tick(u) < tick(v)` | both artifact-bearing records |
| `CONSUMES`  | v exhausted or invalidated a capability created at u        | `ri` head is a terminal predicate (`*.revoked`, `*.expired`, `*.closed`) over u's entity                | terminal record |
| `OBSERVES`  | u is the only telemetry witness of v (bookkeeping edge)     | v is a GHOST node and u is the obligation-bearing observation forcing it                                | obligation trigger record |

19.2.1 `PROPAGATES` requires **artifact identity**, never similarity. Define
  artifact identity per dimension in `artifacts.toml` (token id, key
  thumbprint, content BLAKE3, flow 5-tuple + ISN). A near-match is not a match.
  If the resolver reports an ambiguous artifact identity, fork the hypothesis
  (19.7) rather than emitting a single edge.

19.2.2 Edges are derived, never authored. There is no `edges.yaml`. Assert this
  with a test that deletes the rule instance table and observes an empty edge
  set.

19.3 EDGE REPRESENTATION

```json
{
  "edge_id": "ed:4b9f0c1a77e2d5386a10bb94cf2d73e1",
  "relation": "AUTHORIZES",
  "from_transition": "tr:0091",
  "to_transition":   "tr:0104",
  "support": {
    "instance_id": "ri:8f2c11a0d4b76e590cc3a21ff4470b6d",
    "rule_id": 108, "rule_name": "priv_esc_without_approval", "rule_version": "1.1.0",
    "observed": "LICENSED"
  },
  "evidence": [
    {"binding":"assume","event_id":"ev:7a1c93f0b2d4451e8890ffaa3c2b6d51",
     "source":"iam_audit","t_evt":1739459231000000000,
     "excerpt_hash":"blake3:2b9e...","offset":{"file":"bundle.jsonl","line":18422}}
  ],
  "licenses": [
    {"license_id":"lc:11c4","source":"iam_audit","t0":1739459100000000000,
     "t1":1739462700000000000,"basis":"BLIND",
     "witness":["ev:5c20...","ev:5c21..."]}
  ],
  "blockers_mask": "0x0000000000000240",
  "ghost_endpoint": null
}
```

```sql
CREATE TABLE transition (
    transition_id  BYTEA PRIMARY KEY,
    run_id         UUID    NOT NULL,
    dimension      TEXT    NOT NULL,
    from_state     TEXT    NOT NULL,
    to_state       TEXT    NOT NULL,
    entity_id      BYTEA   NOT NULL,
    tick           INTEGER NOT NULL,
    kind           TEXT    NOT NULL CHECK (kind IN ('OBSERVED','GHOST')),
    fact_id        INTEGER NOT NULL REFERENCES fact(fact_id)
);

CREATE TABLE dependency_edge (
    edge_id      BYTEA PRIMARY KEY,
    run_id       UUID  NOT NULL,
    relation     TEXT  NOT NULL CHECK (relation IN
                   ('ENABLES','CREATES','AUTHORIZES','PROPAGATES','CONSUMES','OBSERVES')),
    from_tr      BYTEA NOT NULL REFERENCES transition(transition_id),
    to_tr        BYTEA NOT NULL REFERENCES transition(transition_id),
    instance_id  BYTEA NOT NULL REFERENCES rule_instance(instance_id),
    blockers     BIGINT NOT NULL
);

-- An edge must dereference. No support instance, no edge.
ALTER TABLE dependency_edge ADD CONSTRAINT edge_has_support
  FOREIGN KEY (instance_id) REFERENCES rule_instance(instance_id);

-- Every OBSERVED-supported edge must have at least one evidence row.
CREATE OR REPLACE VIEW edge_without_evidence AS
  SELECT e.edge_id FROM dependency_edge e
  JOIN rule_instance ri USING (instance_id)
  WHERE ri.observed = 'OBSERVED'
    AND NOT EXISTS (SELECT 1 FROM rule_instance_evidence v
                    WHERE v.instance_id = e.instance_id);
-- CI gate: this view must be empty after every run.
```

19.4 GHOST NODES — INFERRED, UNOBSERVED

19.4.1 A GHOST transition is admitted only by 17.6.4 obligation pressure or a
  `silent_possible` rule, and only where every producing source is BLIND or
  SUPPRESSED across the required interval. A GHOST carries:
  `{license_ids, forcing_obligation_rule_id, interval, dimension}`.

19.4.2 GHOST accounting rules, all enforced:
  - GHOSTs never increment any count of observed events, alerts, or evidence.
    API responses expose `observed_count` and `ghost_count` as separate fields;
    a single summed field is forbidden.
  - GHOSTs render as dashed nodes labelled `INFERRED, UNOBSERVED` with the
    licensing source and window inline. No solid styling, no default hiding.
  - A hypothesis containing one or more GHOSTs is `OPTIMISTIC-ONLY` unless the
    ECLIPSE run was performed on `P_max` and returned ROBUST.
  - A GHOST may never be the sole support for a `PROPAGATES` edge.
  - If an obligation is unsatisfied and unlicensed, do not create a GHOST.
    Emit `permanent_blind_spot` and add it to the per-dimension blind-spot
    volume report (section 12.9 / section 22).

19.5 CHAIN ASSEMBLY

19.5.1 A causal hypothesis is a minimal connected sub-DAG of the dependency
  graph terminating at the goal transition from `goal.toml`.

```
assemble(goal_tr) -> Vec<Hypothesis>:
  1. Backward BFS from goal_tr over dependency_edge, bounded by horizon k.
  2. At each node, group incoming edges by (relation, from_tr.entity_id).
     Disjoint groups are ALTERNATIVES (OR); edges inside a group that are body
     siblings of one rule instance are CONJUNCTS (AND).
  3. Expand the AND/OR structure into candidate DAGs by choosing exactly one
     alternative per OR node.  Cap expansion at `max_hypotheses` (default 256);
     on cap, set flag `hypothesis_enumeration_capped` and report the cap.
  4. Prune any candidate containing a cycle in (tick, entity) order.
  5. Prune any candidate that is a strict superset of another candidate with
     the same leaf set (non-minimal).
  6. Emit each survivor with its edge set, leaf event ids, ghost set, license
     set and blockers mask union.
```

19.5.2 The union of `blockers` over a hypothesis is exactly the corridor clause
  ECLIPSE stage E adds to Ψ. Chain assembly and cut computation must consume one
  data structure; do not maintain a second, parallel graph for the UI.

19.6 HYPOTHESIS RANKING

19.6.1 Ranking is a deterministic total order over integer vectors. It is a
  presentation order, not a belief. Do not name it "confidence", "likelihood",
  "score out of 100", or "severity".

  For hypothesis `h`, compute the vector (all components integers, ascending
  lexicographic order = better ranked first):

```
rank(h) = ( G(h), U(h), L(h), S(h), E(h), D(h), T(h) )

  G(h) = |ghost nodes in h|                                   # fewer inferred nodes first
  U(h) = |edges whose support.observed == UNDETERMINED|
  L(h) = ceil( total_license_span_ns(h) / 1e9 )               # seconds of blindness relied upon
  S(h) = sum over edges e of source_rank(e)                   # integer per-source rank from sources.toml
                                                              #   0 = first-party authoritative log
                                                              #   1 = host agent
                                                              #   2 = network derived
                                                              #   3 = reconstructed / inferred field
  E(h) = |edges in h|                                         # shorter derivations first
  D(h) = ceil( (t_last(h) - t_first(h)) / 1e9 )               # temporal span in seconds
  T(h) = blake3_128( canonical_edge_id_list(h) ) as u128      # deterministic tiebreak only
```

19.6.2 Every component must be recomputable by the Go checker from the
  certificate inputs alone. Publish the component vector next to the rank in
  the API and the UI; never publish the rank without the vector.

19.6.3 Forbidden ranking inputs: learned weights, embeddings, LLM judgments,
  analyst feedback, MITRE technique "popularity", CVSS, any float, any
  normalization to [0,1], any weighted sum that hides a component behind a
  coefficient. If a future component is needed, it is appended to the tuple as
  a new integer field and the ordering is documented, never blended.

19.6.4 `T(h)` exists so the order is total. If two hypotheses differ only in
  `T(h)`, the UI must label them `TIED` and show both. Do not present a
  tiebreak-only winner as preferred.

19.7 DISAMBIGUATION BETWEEN COMPETING HYPOTHESES

19.7.1 Report the full set, not the winner. `GET /api/v1/runs/{id}/hypotheses`
  returns every survivor with its rank vector, and the UI defaults to showing
  the count.

19.7.2 Declare `AMBIGUOUS` when any of the following holds:
  - the top two hypotheses differ only in `T(h)`;
  - they differ only in `D(h)` and share `G, U, L, S, E`;
  - they have disjoint leaf event sets (no shared evidence at all);
  - an entity-resolution fork (17.6.3 / 19.2.1) generated them.

19.7.3 For every AMBIGUOUS set, compute the DECISIVE OBSERVATION SET by handing
  the differing corridors to ECLIPSE stage G: the minimum-cardinality set of
  `(source, window)` pairs whose liveness would eliminate all but one
  hypothesis. Exact search to size 3; greedy beyond, flagged `greedy_cover`
  with its `ln n + 1` bound stated. Render as:

      "Two hypotheses remain. Making iam_audit live over
       [2026-02-13T14:25Z, 2026-02-13T15:05Z] (40m) eliminates one."

19.7.4 Never resolve ambiguity by picking the "more severe" hypothesis, by
  asking an LLM, by analyst preference, or by a prior over attacker behaviour.
  The only permitted resolvers are: more evidence, a rule change (with a semver
  bump), or an entity-resolution correction. Each must be recorded in the run
  log with the resulting rank-vector change.

19.8 DEREFERENCEABILITY CONTRACT

19.8.1 Every edge must dereference to concrete `EventId`s, or to licenses that
  themselves dereference to the witness events establishing blindness. There is
  no third category.

19.8.2 `spectra chain verify <run_id>` (Go, shares no code with the Rust
  reconstructor) checks, in one pass:
  a. every edge has a support rule instance present in `rule_instance`;
  b. every OBSERVED edge has ≥1 evidence row and every referenced `event_id`
     exists in `bundle.jsonl` at the recorded offset with a matching BLAKE3;
  c. every LICENSED edge names licenses present in `liveness.json`, and the
     license derivation recomputes from the bundle;
  d. no GHOST is the sole support of a `PROPAGATES` edge;
  e. every rank vector recomputes to the stored value;
  f. the corridor clause set derived from the hypotheses equals the Ψ stored in
     the certificate.
  Failure of any check is a build failure in CI and a red banner in the UI, not
  a warning.

19.9 WORKED OUTPUT

```
CAUSAL HYPOTHESIS  h1  of 2        rank=(0,0,2400,5,6,1836,0x3f9a...)   OPTIMISTIC-ONLY
run 7c1e  bundle blake3:a4d9...  rules blake3:9c41...  seed 42  k=12

 goal  resource.exfiltrated(bucket:prod-archive) @ t=15:41:07Z   tr:0131
   ^
   | PROPAGATES   ri:8b02  egress_step_change v1.0.2  OBSERVED
   |   ev:9f1a2c..  net_flow      15:40:12Z  bytes=741_249_024
   |   ev:9f1a2d..  net_flow      15:40:58Z  bytes=802_111_488
   |
 network.egress_step(host:web-07, zone:internet) @ 15:40:12Z      tr:0127
   ^
   | ENABLES      ri:41cc  resource_enumeration v1.0.1  OBSERVED
   |   ev:5511aa..  api_gateway   15:31:02Z  distinct_resources=317
   |
 resource.enumerated(svc:etl-runner, bucket) @ 15:31:02Z          tr:0119
   ^
   | AUTHORIZES   ri:8f2c  priv_esc_without_approval v1.1.0  LICENSED
   |   license lc:11c4  iam_audit BLIND [15:05:00Z, 16:05:00Z] basis=BLIND
   |     witness ev:5c20.. (last record before gap), ev:5c21.. (chain break)
   |   ev:7a1c93..  iam_audit     15:27:41Z  role_assumed=admin-etl
   |
 privilege.escalated(svc:etl-runner, admin-etl) @ 15:27:41Z       tr:0104
   ^
   | CREATES      ri:2d70  session_used_implies_issued v1.0.0  LICENSED
   |   license lc:11c4  (same blind window)
   :
   : - - - - GHOST - - - -
 [ INFERRED, UNOBSERVED ]  session.issued(sess:9931) @ [15:05Z,15:27Z]  tr:0091
   forced by obligation rule 900; licensed by iam_audit BLIND window lc:11c4
   contributes 0 to observed_count; ghost_count=1

 leaves: 6 event ids, all dereferenced   licenses: 1   ghosts: 1
 corridor blockers: {priv_approval>=1, rbac>=2, egress_seg>=1, svc_acct_isolation>=1}
```

```
$ spectra chain verify 7c1e
edges 19  observed 17  licensed 2  ghost-endpoints 1
 a. support present            19/19  ok
 b. evidence dereferenced      41/41  ok   (offsets + blake3 match)
 c. licenses recomputed         1/1   ok   (iam_audit BLIND 15:05-16:05, chain break at seq 88214)
 d. ghost-sole-propagates       0     ok
 e. rank vectors recomputed     2/2   ok
 f. corridors == cert psi       6/6   ok
VERDICT: chain output is internally consistent and fully dereferenced.  7ms
NOTE: this verifies the derivation, not reality. See section 12.9.
```

19.10 NEGATIVE REQUIREMENTS

  - Do not emit an edge from temporal adjacency, co-occurrence, shared
    principal, shared host, string similarity, embedding distance, or graph
    centrality. Only the six derivation conditions in 19.2.
  - Do not emit probabilities, confidence intervals, Bayesian posteriors,
    likelihood ratios, or any float-valued quality measure for a hypothesis.
  - Do not collapse competing hypotheses into one narrative. Do not hide
    alternatives behind a "show more" affordance that defaults to collapsed.
  - Do not let an LLM create, delete, reorder, merge, or rank edges or
    hypotheses. An LLM may narrate an already-computed hypothesis, and its
    output must be regenerable from the JSON with the LLM disabled (see
    section 24); deleting the LLM must change nothing but prose.
  - Do not present a GHOST as an event, do not include GHOSTs in event counts,
    and do not infer a GHOST without a license.
  - Do not describe a hypothesis as what happened, as the root cause, or as
    proof of attacker action. It is a causal hypothesis over the declared model.
  - Do not use MITRE ATT&CK technique ids as evidence. They may appear as
    read-only labels on a transition, sourced from the rule's `provenance`, and
    must never enter ranking, assembly, or the certificate.
