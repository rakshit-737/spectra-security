============================================================
22. CONTROL MODEL
============================================================

22.1 Position. Controls are DATA. There is exactly one authored catalog, `controls/catalog.yaml`. A build step (`spectra controls compile`) normalizes it into `build/controls.toml`, the machine artifact consumed by the Rust kernel (section 25), the deterministic simulator (section 23) and the API. Any behavior that depends on a control MUST be expressed as a guard expression in the catalog or in `rules/rules.toml`. You MUST NOT write `if control_enabled("mfa")` anywhere in the reconstruction, simulation or proof code. A CI gate (`gates/no_control_branches.py`) greps the Rust, Go, Python and TypeScript sources for control ids appearing as string literals outside loader/serialization modules and fails the build on a hit. The only permitted appearances are: the catalog, the compiled TOML, test fixtures, and the UI label table generated from the catalog.

22.2 Levels and threshold atoms. Every control `c_k` declares an ordered level list `0..m_k`, where level 0 is "absent" and levels increase in strictness. Level ordering MUST be a total order with monotone semantics: anything refused at level `ℓ` is refused at level `ℓ+1`. Compilation emits threshold atoms `x_{k,ℓ} ≡ [c_k ≥ ℓ]` for `ℓ ∈ 1..m_k` with implications `x_{k,ℓ+1} → x_{k,ℓ}`. The global atom budget is `Σ_k m_k ≤ 64`; the compiler fails with `E_ATOM_BUDGET` above it, printing the current count. Publish the count in `build/controls.meta.json` and render it in the UI footer.

22.3 Guard language. One grammar, one parser (`crates/spectra-guard`), two lowerings: to the simulator's evaluator and to ECLIPSE's `blockers` masks.

```
Guard    := Disj
Disj     := Conj ( "or" Conj )*
Conj     := Unary ( "and" Unary )*
Unary    := "not" Unary | Prim
Prim     := "(" Disj ")" | CtrlCmp | StateCmp | "true" | "false"
CtrlCmp  := "ctrl." Ident ">=" ( Int | LevelName )
StateCmp := Path CmpOp Literal | "has(" Path ")" | "in(" Path "," ListLit ")"
Path     := Ident ( "." Ident )*          // resolves against the security state (section 17)
CmpOp    := "==" | "!=" | "<" | "<=" | ">" | ">="
```

Rules for `admit_when` (the condition under which a gated transition is still permitted):
- It MUST be antitone in the control vector: raising any level may only turn `true` into `false`. The linter rejects any `ctrl.*` comparison appearing under an even number of `not`s in `admit_when`. Equivalently, control literals may appear only negated.
- Lowering: put `admit_when` in DNF over `(¬x_{k,ℓ})` and state predicates. Each DNF term becomes ONE rule instance / ONE technique variant whose `blockers` mask is the OR of the bits of the threshold atoms it negates. A step that only fails when two controls are both raised is therefore two variants, not one mask. `blockers & S == 0` is then exactly "this variant survives cut S".
- State predicates are evaluated at grounding time against the reconstructed state and are NOT part of the mask.

22.4 Enforcement points. Enumerate them once; the catalog references them by id. Each enforcement point is a named interception site in the pipeline, and each has a Python/Rust hook registry keyed by enforcement point id, never by control id.

```
EP-IDP-AUTHN       identity provider, primary authentication
EP-IDP-STEPUP      identity provider, re-authentication for sensitive transitions
EP-SESSION-MINT    session/token issuance
EP-SESSION-PRESENT token presentation at a resource server
EP-AUTHZ-COARSE    role/endpoint authorization
EP-AUTHZ-OBJECT    per-object ownership/tenancy authorization
EP-PRIV-GRANT      privilege grant / role assignment path
EP-NET-EAST-WEST   intra-zone lateral connection admission
EP-NET-EGRESS      outbound connection admission
EP-SVCID-ASSERT    service identity assertion / workload token exchange
EP-DEVICE-POSTURE  device registration and posture assertion
EP-RATE            request-rate and volume admission
EP-CRED-LIFECYCLE  credential issuance, rotation, revocation
EP-LOG-WRITE       telemetry emission and integrity sealing
EP-DETECT          detection-only analytic (emits, never refuses)
```

22.5 Catalog schema. `controls/catalog.yaml` validates against `schemas/controls.schema.json` (JSON Schema 2020-12). Unknown keys are an error.

```yaml
version: 1
controls:
  - id: session_binding               # ^[a-z][a-z0-9_]{2,31}$, unique
    name: "Session binding"
    dimension: session                # one of section 17 dimensions
    description: "Binds a session artifact to network/device context."
    enforcement_points: [EP-SESSION-MINT, EP-SESSION-PRESENT]
    levels:                           # index == level; index 0 is mandatory and is 'absent'
      - id: off
        summary: "Bearer token, no binding."
        params: {}
      - id: network
        summary: "Token bound to source ASN + /24."
        params: { rebind_grace_s: 0, scope: "asn+prefix24" }
      - id: device
        summary: "Token bound to device key (DPoP/mTLS)."
        params: { proof_alg: "ES256", rebind_grace_s: 0 }
    gates:                            # transitions this control can refuse
      - transition: session.token.replay_from_new_context
        admit_when: "not ctrl.session_binding >= network"
        effect: refuse
      - transition: session.token.replay_from_new_device
        admit_when: "not ctrl.session_binding >= device"
        effect: refuse
    bypass:                           # every entry MUST name a modeled path
      - id: same_prefix_replay
        condition: "attacker.network.prefix24 == victim.network.prefix24"
        defeats_from_level: network
        modeled_by_variant: "replay_same_prefix"
      - id: device_key_theft
        condition: "attacker.capabilities has device_key"
        defeats_from_level: device
        modeled_by_variant: "replay_with_stolen_key"
    coverage_limits:
      - "Does not constrain server-side session objects reused by a compromised service."
      - "No effect on tokens minted after full device compromise."
    telemetry:
      emits_sources: [idp_audit, gateway_access]
      emits_event_types: [session.bind.ok, session.bind.reject]
    interacts_with: [token_expiry, device_trust]
    provenance: "ATT&CK T1550.004; OAuth DPoP RFC 9449 (structure only, no vendor claim)."
```

Required keys per control: `id, name, dimension, enforcement_points, levels, gates, bypass, coverage_limits, telemetry, provenance`. Required per gate: `transition, admit_when, effect ∈ {refuse, degrade, detect}`. `degrade` and `detect` gates MUST NOT contribute blocker bits to ECLIPSE (they do not sever a corridor); the compiler enforces this and records them in `build/controls.meta.json` under `non_severing_gates`.

22.6 Catalog contents. Implement all fifteen. Levels are listed `0/1/2[/3]`.

```yaml
- id: mfa            dimension: identity      eps: [EP-IDP-AUTHN, EP-IDP-STEPUP]
  levels: off / otp / phishing_resistant / stepup_on_privilege
  gates: identity.authn.password_only(admit: not ctrl.mfa>=otp)
         identity.authn.otp_relay(admit: not ctrl.mfa>=phishing_resistant)
         privilege.role.assign(admit: not ctrl.mfa>=stepup_on_privilege)
  params: {otp_window_s:30, webauthn_rp_id:"lab.local", stepup_max_age_s:300}
  bypass: token_theft_post_authn (all levels); session_cookie_replay (off,otp)
  limits: "Never constrains a step that starts from an already-minted session."

- id: token_expiry   dimension: session       eps: [EP-SESSION-MINT, EP-SESSION-PRESENT]
  levels: never / h8 / h1 / m15_bound_refresh
  gates: session.token.use_after(admit: not ctrl.token_expiry>=L where age>ttl(L))
  params: {ttl_s per level: [0, 28800, 3600, 900], refresh_binding: bool}
  bypass: replay_within_ttl (all levels); refresh_token_theft (h8,h1)
  limits: "Reduces the window, never removes it; ttl=0 is not modeled."

- id: rbac           dimension: privilege     eps: [EP-AUTHZ-COARSE]
  levels: flat / role_scoped / resource_scoped / deny_by_default
  gates: privilege.access.cross_role, privilege.access.cross_resource,
         privilege.access.undeclared_endpoint
  params: {default_decision:"deny"|"allow", wildcard_grants_allowed:bool}
  bypass: role_inheritance_chain (role_scoped); over-broad grant in fixture data
  limits: "Cannot stop actions inside the legitimate scope of a stolen identity."

- id: object_authz   dimension: api           eps: [EP-AUTHZ-OBJECT]
  levels: off / tenant_check / owner_check
  gates: api.object.read_other_tenant, api.object.enumerate_ids
  params: {id_space:"sequential"|"uuid", check_on:["read","write","list"]}
  bypass: shared_object_grant; confused-deputy via service identity
  limits: "Only covers objects whose owner edge exists in the model."

- id: priv_approval  dimension: privilege     eps: [EP-PRIV-GRANT]
  levels: none / async_ticket / sync_human_jit
  gates: privilege.role.self_assign, privilege.role.assign_offhours
  params: {jit_ttl_s:3600, approver_disjoint_from_requester:bool}
  bypass: approver_account_also_compromised; ticket auto-approval rule
  limits: "Refuses the grant path only; does not revoke standing privilege."

- id: net_segment    dimension: network       eps: [EP-NET-EAST-WEST]
  levels: flat / zone_acl / microseg
  gates: network.lateral.connect_cross_zone, network.lateral.connect_peer
  params: {zones:[...], default_policy:"deny", allowed_pairs:[[a,b],...]}
  bypass: pivot through an allowed shared service; DNS rebinding not modeled
  limits: "Zone graph is fixture data; unmodeled links are invisible."

- id: egress_seg     dimension: network       eps: [EP-NET-EGRESS]
  levels: off / domain_allowlist / proxy_deny_default
  gates: network.egress.exfil_bulk, network.egress.c2_beacon
  params: {allowlist:[...], max_bytes_per_window:int, window_s:int}
  bypass: exfil via allowlisted SaaS host; low-and-slow under threshold
  limits: "No payload inspection is modeled; volume and destination only."

- id: svc_isolation  dimension: service       eps: [EP-SVCID-ASSERT]
  levels: shared_account / per_service / audience_scoped / no_interactive
  gates: service.identity.reuse_across_services,
         service.identity.interactive_login
  params: {audience_claim_required:bool, token_exchange_allowed:bool}
  bypass: service compromised at its own scope; sidecar key readable on host
  limits: "Does not constrain what the service is legitimately allowed to do."

- id: device_trust   dimension: trust         eps: [EP-DEVICE-POSTURE]
  levels: off / registered / attested
  gates: identity.authn.unknown_device, session.token.mint_unmanaged
  params: {attestation:"tpm_quote"|"none", posture_max_age_s:900}
  bypass: enrollment of attacker device during a valid session
  limits: "Attestation is simulated structurally; no real TPM is used."

- id: rate_limit     dimension: api           eps: [EP-RATE]
  levels: off / per_principal / per_principal_resource_lockout
  gates: api.object.enumerate_ids, identity.authn.spray
  params: {limit:int, window_s:int, lockout_s:int, burst:int}
  bypass: distribute across principals; stay under threshold
  limits: "Slows enumeration; a targeted single-object read is never limited."

- id: cred_rotation  dimension: credential    eps: [EP-CRED-LIFECYCLE]
  levels: never / d90 / d7 / single_use
  gates: credential.static.reuse_after(admit: not ctrl.cred_rotation>=L
                                       where age>max_age(L))
  params: {max_age_s per level, revoke_on_rotate:bool}
  bypass: use inside the rotation window; rotation does not revoke live sessions
  limits: "Does nothing to a credential used minutes after theft."

- id: secret_storage dimension: credential    eps: [EP-CRED-LIFECYCLE]
  levels: plaintext / vault_static / vault_dynamic_lease
  gates: credential.secret.read_from_disk, credential.secret.read_from_env
  params: {lease_ttl_s:int, audit_on_fetch:bool}
  bypass: process memory read after fetch (modeled); lease reuse within TTL
  limits: "Protects at rest only; a running process holding the secret is out of scope."

- id: audit_integrity dimension: trust        eps: [EP-LOG-WRITE]
  levels: plain / append_only / hash_chain_offhost
  gates: (none: effect=detect)  # feeds liveness, see section 25 pipeline A
  params: {chain_alg:"blake3", replication_lag_s:int}
  bypass: suppress before write (pre-emission gap remains BLIND, not SUPPRESSED)
  limits: "Detects deletion of already-written records; cannot create records."

- id: anomaly_detect dimension: identity      eps: [EP-DETECT]
  levels: off / rules / rules_plus_baseline
  gates: (effect=detect on impossible_travel, new_asn, volume_spike)
  params: {baseline_window_s:int, min_support:int}
  bypass: below-threshold behavior; detection is not refusal
  limits: "NEVER severs a corridor. Contributes only to the
           DETECTED_NOT_BLOCKED outcome class in section 24."

- id: session_binding  (fully specified in 22.5)
```

22.7 Compiler output and gates.
- `spectra controls compile` writes `build/controls.toml`, `build/controls.meta.json` (atom count, atom table, level implications, non-severing gates, per-control gated transition list) and `build/controls.d.ts` (UI types). All three are committed and diffed in CI; a stale artifact fails the build.
- Every `transition` named in a gate MUST exist in the transition registry of section 17. Unknown transition => `E_UNKNOWN_TRANSITION`.
- Every `bypass.modeled_by_variant` MUST resolve to a technique variant in the scenario/technique library of section 23. An unmodeled bypass claim is an error: you may not document a bypass you have not implemented.
- Property test `antitone_catalog`: for 512 random control vectors and every gated transition, raising one level never flips `refuse` to `admit`.
- Property test `dnf_mask_equivalence`: for every gate, brute-force evaluate `admit_when` over all `2^|atoms in guard|` assignments and compare against the lowered variant masks. Must agree on every assignment.
- Coverage report `reports/control_coverage.md`: for each control, the transitions it gates, the scenarios in which it is exercised, and the scenarios in which it is inert. Generated, never hand-written.

22.8 Negative requirements.
- Do NOT attach cost, price, ROI, risk score, maturity score or "effectiveness percentage" to a control. Costs live only in `costs.toml`, are user-authored, and are never generated (section 25).
- Do NOT model a control as globally "on/off" if the catalog gives it levels; the UI toggle emits a level, not a boolean.
- Do NOT add a control whose only gate is `effect: detect` and then let it appear in an ECLIPSE cut.
- Do NOT claim any control corresponds to a named vendor product. `provenance` cites technique or RFC structure only.

============================================================
23. SCENARIO MODEL AND THE DETERMINISTIC SIMULATOR
============================================================

23.1 Separation of concerns. A scenario describes what an attacker and the environment ATTEMPT. It MUST NOT mention any control id. The simulator decides, per step, whether the attempt is admitted, refused, degraded or merely detected, using only the active control configuration and the current state. A CI gate rejects any scenario file containing a string from the control id table. This separation is what makes the counterfactual in section 24 honest: the same scenario bytes drive every run.

23.2 Scenario schema. `scenarios/<id>.yaml`, validated against `schemas/scenario.schema.json`.

```yaml
id: sc_oauth_token_pivot
version: 1
title: "Stolen refresh token to cross-tenant object read"
horizon_ticks: 240            # virtual ticks; 1 tick = 1 simulated second
tick_unit_s: 1
seed_domain: "spectra/scenario/v1"
entities:
  principals:
    - {id: u_alice, kind: human, roles: [analyst], home_asn: 64500, device: d_laptop1}
    - {id: sa_report, kind: service, roles: [report_runner], zone: app}
  devices:
    - {id: d_laptop1, registered: true, attested: true}
    - {id: d_attacker, registered: false, attested: false}
  resources:
    - {id: obj_tenantB_001, tenant: B, owner: u_bob, id_space: sequential}
  zones: [edge, app, data]
  zone_links: [[edge, app], [app, data]]
actors:
  - id: adv1
    kind: adversary
    start_capabilities: [refresh_token:rt_alice_7]
    start_position: {zone: external, device: d_attacker, asn: 65010}
initial_state:                # partial; unspecified slots take registry defaults
  sessions: []
  credentials:
    - {id: rt_alice_7, subject: u_alice, kind: refresh_token, issued_tick: -3600,
       last_rotated_tick: -3600}
intent:                       # ordered attempts; ordering is intent, not guarantee
  - step: s1
    actor: adv1
    transition: session.token.replay_from_new_context
    variants: [replay_plain, replay_same_prefix]   # tried in declared order
    requires: [refresh_token:rt_alice_7]
    preconditions:
      - "credential(rt_alice_7).revoked == false"
    effects_on_admit:
      - "mint session sess_a bound_to actor.position"
      - "grant capability session:sess_a"
    emits: [{source: idp_audit, type: session.mint, on: admit}
           ,{source: idp_audit, type: session.mint.reject, on: refuse}]
    on_refuse: continue        # continue | abort | fallback(step_id)
  - step: s2
    actor: adv1
    transition: api.object.enumerate_ids
    requires: [session:sess_a]
    preconditions: ["has(session.sess_a)"]
    effects_on_admit: ["learn object_ids in tenant B"]
    effects_on_degrade: ["learn <= rate_limit.limit object_ids"]
    emits: [{source: gateway_access, type: api.list, on: any}]
    on_refuse: abort
  - step: s3
    actor: adv1
    transition: api.object.read_other_tenant
    requires: [session:sess_a, knowledge:object_ids]
    goal: true                 # exactly one step in a scenario carries goal: true
    effects_on_admit: ["exfil obj_tenantB_001"]
    emits: [{source: gateway_access, type: api.read, on: any}]
noise:
  benign_actors: 12
  events_per_tick_lambda: 3.0   # consumed through the seeded PRNG only
```

Constraints the loader enforces: exactly one `goal: true` step; every `requires` capability is either in `start_capabilities` or granted by an earlier step's `effects_on_admit`; every `transition` exists in the section 17 registry; every `variant` exists in the technique library; `horizon_ticks ≤ 10_000`.

23.3 The stepper. `crates/spectra-sim`, exposed to Python via PyO3 and to the CLI directly.

```
fn run(scenario: &Scenario, config: &ControlVector, seed: u64) -> Trace {
    let root = blake3(seed_domain || scenario.hash || config.canonical_bytes || seed_le);
    let mut rng = ChaCha20Rng::from_seed(root);          // only source of randomness
    let mut st  = State::from_initial(scenario);          // section 17 state machine
    let mut clk = VClock::new(0);                         // virtual, never wall-clock
    let mut tr  = Trace::new(root);
    for step in scenario.intent.iter() {                  // declaration order, stable
        clk.advance(step.duration_ticks(&mut rng));       // rng draw #, logged
        if !eval_preconditions(step, &st) {
            tr.push(Record::skipped(step, PRECONDITION_FALSE, &st, &clk)); continue;
        }
        let mut decision = Decision::Refused { by: AtomSet::empty(), variant: None };
        for v in step.variants_or_default() {             // declared order
            let g = guard_for(step.transition, v, config); // compiled from section 22
            match g.evaluate(&st, config) {
                Admit            => { decision = Decision::Admitted{variant:v}; break }
                Degrade{cap}     => { decision = Decision::Degraded{variant:v, cap}; break }
                Refuse{atoms}    => { decision.merge_refusal(v, atoms); continue }
            }
        }
        let detections = eval_detect_gates(step, &st, config);   // never changes decision
        let delta = apply_effects(&mut st, step, &decision, &mut rng);
        let events = emit(step, &decision, &detections, &st, &clk, &mut rng);
        tr.push(Record::new(step, &decision, &detections, delta, events, &clk,
                            rng.draw_count()));
        match (&decision, step.on_refuse) {
            (Decision::Refused{..}, OnRefuse::Abort)        => break,
            (Decision::Refused{..}, OnRefuse::Fallback(id)) => { jump(id); }
            _ => {}
        }
    }
    tr.finalize()   // sets outcome, chain head, trace_hash
}
```

Hard requirements:
- One PRNG, threaded, never re-seeded mid-run, never cloned for parallel work inside a run. Record `rng_draws_before` and `rng_draws_after` on every record; the determinism test asserts the draw counter is a function of `(scenario, config, seed)`.
- No wall-clock reads in `spectra-sim` or its dependencies used at simulation time. CI gate `gates/no_clock.sh` greps for `SystemTime|Instant::now|chrono::Utc::now|time.Now|datetime.now|Date.now` under the simulator tree and fails on any hit outside `#[cfg(test)]` benchmarking harnesses.
- No floating point in any value that reaches the trace or the hash. `events_per_tick_lambda` is converted to a fixed-point integer rate at load time. A serde-level guard rejects `f32/f64` in trace types at compile time via a trait bound test.
- No hash-map iteration in emission order. All maps serialized as key-sorted arrays.
- Parallelism across runs is allowed; parallelism inside a run is forbidden.

23.4 Trace record format. NDJSON, one record per line, plus a final `trace_footer` line. Canonical serialization: JCS-style, sorted keys, integers only, no whitespace.

```json
{"seq":7,
 "vclock_tick":41,
 "actor":"adv1",
 "step":"s2",
 "transition":"api.object.enumerate_ids",
 "variant":"enumerate_sequential",
 "decision":"DEGRADED",
 "refused_by":[],
 "degraded_by":[{"control":"rate_limit","level":1,"atom":"x_rate_limit_1"}],
 "detected_by":[{"control":"anomaly_detect","level":2,"analytic":"volume_spike"}],
 "precondition_eval":[{"expr":"has(session.sess_a)","value":true}],
 "state_delta":[{"op":"add","path":"knowledge.adv1.object_ids","value_count":100}],
 "capabilities_after":["session:sess_a","knowledge:object_ids"],
 "emitted":[{"event_id":"ev_000173","source":"gateway_access","type":"api.list",
             "tick":41,"suppressed":false}],
 "rng_draws_before":118,"rng_draws_after":121,
 "prev":"blake3:9c1e...","hash":"blake3:4ab0..."}
```

`hash = blake3(prev || canonical_json(record_without_hash))`. The footer carries `{"outcome":..., "goal_step":"s3", "goal_reached":false, "first_block":{"step":"s1","atoms":["x_session_binding_1"]}, "records":9, "events":412, "trace_hash":"blake3:4ab0...", "inputs":{"scenario":"blake3:..","controls":"blake3:..","seed":42,"sim_version":"1.4.0"}}`. `trace_hash` equals the last record hash; an empty trace hashes the root.

23.5 Emitted telemetry. Emission is the ONLY bridge from the simulator to ingestion. Each emitted event carries a stable `event_id` derived as `blake3(trace_root || seq || emit_index)[0..8]`, so the same event in two runs of the same configuration has the same id, and ids never collide across configurations. Degradation and tampering (section on telemetry degradation) operate on the emitted stream AFTER the simulator, never inside it; the simulator's own trace is always complete and is the ground truth against which reconstruction is scored. The simulator MUST NOT read the degraded stream.

23.6 Determinism test suite (`tests/determinism/`).
- `replay_identity`: for every fixture scenario × 8 control vectors × 4 seeds, run 32 times in-process and 4 times in fresh processes; all 36 `trace_hash` values MUST be identical.
- `cross_arch`: CI runs the same matrix on linux/amd64 and linux/arm64; hashes MUST match across architectures. Golden hashes are committed to `tests/golden/traces.json`; a change requires an explicit `GOLDEN_UPDATE=1` commit that shows the diff in review.
- `seed_sensitivity`: different seeds MUST produce different traces for at least one fixture, proving the seed is actually threaded (guards against a stubbed PRNG).
- `config_sensitivity`: for every control, there exists at least one fixture where raising that control changes the trace hash. Failure means the control is inert everywhere and either the catalog or the scenario library is wrong.
- `record_chain`: recompute every record hash from `prev` and the canonical body; any mismatch fails.
- `no_state_leak`: two runs in the same process with different scenarios interleaved produce the same hashes as isolated runs.

23.7 CLI.

```
$ spectra sim run --scenario sc_oauth_token_pivot \
      --controls configs/baseline.toml --seed 42 --out runs/base/
outcome=SUCCEEDED goal=s3 records=9 events=412
trace_hash=blake3:4ab0c7d21f9e5a83
wrote runs/base/trace.ndjson runs/base/events.jsonl runs/base/footer.json

$ spectra sim verify runs/base/       # rehash chain, revalidate schema
OK chain 9/9, schema OK, no floats, 121 rng draws accounted
```

23.8 Negative requirements.
- Do NOT let the simulator consult reconstruction output, the knowledge graph, or ECLIPSE. It runs on scenario + controls + seed only.
- Do NOT model attacker adaptivity. Variant order is declared, fixed, and exhausted in order; the attacker does not learn across steps beyond declared `effects`. Say so in every UI surface that reports a proof.
- Do NOT introduce probabilistic control failure ("MFA fails 3% of the time"). Bypass is structural and modeled as a variant with a precondition, or it is not modeled.
- Do NOT write wall-clock timestamps into events; all times are virtual ticks mapped to a fixed epoch `2024-01-01T00:00:00Z + tick*tick_unit_s` at export time.

============================================================
24. WHAT-IF CONTROL REPLAY
============================================================

24.1 Definition. A replay is a pair of simulator runs over IDENTICAL scenario bytes and IDENTICAL seed with two control vectors `C_base` and `C_cf`, plus a structured diff. Nothing in the counterfactual is estimated, extrapolated or reasoned about by an LLM. If a number appears in the replay output, a run produced it.

24.2 Engine.

```
replay(scenario, C_base, C_cf, seed):
    T_b = sim.run(scenario, C_base, seed)      # cached by (scn,ctrl,seed) hash
    T_c = sim.run(scenario, C_cf,  seed)
    align = align_steps(T_b, T_c)
    diff  = field_diff(align)
    bp    = block_point(T_b, T_c, align)
    out_b = classify(T_b); out_c = classify(T_c)
    return ReplayResult{T_b,T_c,align,diff,bp,out_b,out_c,delta_atoms(C_base,C_cf)}
```

24.3 Alignment. Step identity is `key = (actor, step_id, attempt_ordinal)`. Because the scenario is control-independent, keys are stable across runs; alignment is therefore a Myers diff over the key sequence, not a fuzzy match. Outcomes: `MATCHED` (key in both), `ONLY_BASE`, `ONLY_CF` (produced by `fallback` branches). Never align two records with different `step` ids. Assert in tests that for fixture scenarios without fallbacks the alignment is a bijection.

24.4 Field diff. For each `MATCHED` pair compare, in this order: `decision`, `variant`, `refused_by`, `degraded_by`, `detected_by`, `capabilities_after`, `state_delta`, `emitted[].type` multiset. Emit a typed change list; do not diff `hash`, `prev`, `rng_draws_*` (they are expected to differ and are reported separately as `divergence_seq`, the first seq where hashes differ).

24.5 Block point. The block point is the first `MATCHED` seq where base is `ADMITTED` and counterfactual is `REFUSED`, such that the counterfactual never afterwards acquires the capability set that the base run held at that seq. Formally: let `cap_b(i)` be base capabilities after seq `i`; block point `i*` is the minimum `i` with `decision_b(i)=ADMITTED ∧ decision_c(i)=REFUSED ∧ ∀j>i: cap_c(j) ⊉ cap_b(i)`. If no such `i` exists, there is no block point even if refusals occurred (the attacker routed around them) — report `block_point: null` and `routed_around: [seq...]`. The block point record names the exact atoms in `refused_by`, and those atoms are the control levels the UI attributes the block to. Never attribute a block to a control that does not appear in `refused_by`.

24.6 Outcome classification. Computed from the footer of a single run; evaluated top to bottom, first match wins.

```
SUCCEEDED              goal step decision == ADMITTED
DEGRADED               goal step decision == DEGRADED, or goal ADMITTED but at least
                       one prerequisite step was DEGRADED and the declared
                       degrade-cap reduced the effect magnitude
BLOCKED                goal step never reached ADMITTED/DEGRADED and a block point
                       exists (see 24.5)
DETECTED_NOT_BLOCKED   outcome would be SUCCEEDED or DEGRADED and at least one record
                       has non-empty detected_by  -> reported as a modifier flag
                       alongside the base class, never as a standalone "win"
INCONCLUSIVE           horizon exhausted with goal step never evaluated
                       (preconditions never satisfied)
```

`DETECTED_NOT_BLOCKED` is a MODIFIER: the API returns `{"class":"SUCCEEDED","detected":true,"detections":[...]}`. The UI must render it as "succeeded (detected)". Do NOT present detection as prevention anywhere.

24.7 Side-by-side output.

```
$ spectra replay --scenario sc_oauth_token_pivot --seed 42 \
    --base configs/baseline.toml --cf 'session_binding=device,rate_limit=2'

SCENARIO sc_oauth_token_pivot   seed 42   scenario blake3:7e12a9c4
DELTA    session_binding 0 -> 2 (device) | rate_limit 0 -> 2 (per_principal_resource_lockout)

  BASELINE                                 COUNTERFACTUAL
  outcome SUCCEEDED (detected)             outcome BLOCKED
  trace blake3:4ab0c7d2                    trace blake3:b19f0e57
+---------------------------------------+---------------------------------------+
| 1 s1 session.token.replay_from_new_ctx | 1 s1 session.token.replay_from_new_ctx|
|    variant replay_plain                |    variant replay_plain               |
|    ADMIT                               |    REFUSE  x_session_binding_1        |
|    +cap session:sess_a                 |    variant replay_same_prefix         |
|                                        |    REFUSE  x_session_binding_2   <== BLOCK POINT
|                                        |    (no further variants declared)     |
+---------------------------------------+---------------------------------------+
| 2 s2 api.object.enumerate_ids          | 2 s2 api.object.enumerate_ids         |
|    ADMIT   learned 100 ids             |    SKIPPED precondition has(sess_a)=F |
|    detect anomaly_detect/volume_spike  |                                       |
+---------------------------------------+---------------------------------------+
| 3 s3 api.object.read_other_tenant GOAL | 3 s3 api.object.read_other_tenant GOAL|
|    ADMIT   exfil obj_tenantB_001       |    NOT REACHED                        |
+---------------------------------------+---------------------------------------+
  first hash divergence at seq 1
  block point   seq 1 / step s1 / atoms [x_session_binding_1, x_session_binding_2]
  routed around none
  attributable  session_binding>=network is sufficient here; rate_limit changed
                nothing in this scenario (inert, see control_coverage.md)
```

The last line is mandatory: whenever a toggled control produced no field difference, the replay MUST say it was inert rather than let the user infer it helped. Machine form: `"inert_controls":["rate_limit"]`.

24.8 Sweep mode. `spectra replay sweep --scenario X --axis session_binding --axis token_expiry` runs the Cartesian product of the named axes (capped at 4096 runs, cached by content hash) and emits `sweep.json` with one row per configuration: `{config, outcome, detected, block_point, trace_hash}`, plus `reports/sweep_<scenario>.md` containing an ASCII outcome matrix. This is the honest, brute-force complement to ECLIPSE; section 25's test plan uses it as the cross-check oracle.

24.9 API.

```
POST /api/v1/replay              {scenario_id, seed, base:{...}, counterfactual:{...}}
   -> 200 {replay_id, base:{trace_hash,outcome,detected}, cf:{...},
           block_point, routed_around, inert_controls, diff_url}
GET  /api/v1/replay/{id}/diff    -> aligned diff document (JSON)
GET  /api/v1/replay/{id}/trace/{base|cf}  -> NDJSON stream
POST /api/v1/replay/sweep        {scenario_id, seed, axes:[...]} -> sweep_id
GET  /api/v1/replay/sweep/{id}   -> matrix
```

Results are cached under `cache/replay/<blake3(scenario,base,cf,seed,sim_version)>`; a cache hit MUST return `"cached":true` and the identical `trace_hash`.

24.10 Negative requirements.
- Do NOT compare runs with different seeds or different scenario bytes and call it a counterfactual. The API rejects mismatched hashes with `E_REPLAY_INPUTS_DIFFER`.
- Do NOT say "this control would have prevented the breach". The permitted sentence is: "under this scenario, this seed and this control catalog, the modeled attack path terminated at step s1."
- Do NOT aggregate outcomes across scenarios into a single effectiveness percentage for a control.
- Do NOT let an LLM produce the block point, the classification or the diff. LLM narration may only restate fields already present in `ReplayResult`, and the narration endpoint receives only that JSON.

============================================================
25. ECLIPSE — EVIDENCE-LICENSED CUT PROOFS OVER SILENT ENVELOPES
============================================================

25.1 What it is. ECLIPSE is SPECTRA's proof kernel. Section 24 answers "what happened when I toggled this?" by running the simulator. ECLIPSE answers the quantified question — "which minimum set of control levels severs every evidence-consistent attack path, including the paths I cannot see because a sensor was blind?" — without enumerating control configurations, and emits a content-addressed certificate that an independently written checker validates in one linear pass. It proves properties OF THE MODEL, never of reality (25.13).

25.2 Layout.

```
crates/spectra-eclipse/        Rust: liveness, grounding, envelope, fixpoint, cuts, frontier
  src/{liveness,ground,envelope,fixpoint,hitting,redundancy,decisive,frontier,cert}.rs
crates/spectra-guard/          shared guard parser + DNF lowering (section 22)
cmd/spectra-verify/            Go: independent checker. MUST NOT link any Rust crate.
reference/admissibility/       Haskell: reference license-admissibility checker (tests only)
tests/oracles/z3/              Z3 models. Test-only. Never in the runtime path.
```

CI gate `gates/checker_independence.sh`: the Go module's `go.mod` has no cgo, no FFI, no generated-from-Rust sources; `go list -deps` must not include any path under `crates/`; the only shared artifacts are the on-disk formats (`rules.toml`, `bundle.jsonl`, `controls.toml`, `liveness.json`, `cert.json`) and their JSON Schemas.

25.3 Inputs (all content-hashed with BLAKE3; the hashes go in the certificate).

| input | producer | contents |
|---|---|---|
| `bundle.jsonl` | ingestion + entity resolution | resolved telemetry, stable `EventId`, manifest hash, generator seed |
| `rules.toml` | authored | head, body, guard, `producing_sources`, `silent_possible`, provenance note |
| `controls.toml` | section 22 compiler | controls, levels, threshold atoms, implications |
| `costs.toml` | USER ONLY | per (control, level) declared cost; may be absent |
| `goal.toml` | authored per scenario | goal atom, horizon `k` |

25.4 Rule table. One table, two consumers (kernel and simulator), no second source of truth.

```toml
[[rule]]
id = "r_session_replay"
head = "session.active(S, T+1)"
body = ["session.issued(S, T)", "token.presented(S, CTX, T)"]
guard = "not ctrl.session_binding >= network or ctx_matches_bind(CTX, S)"
producing_sources = ["idp_audit", "gateway_access"]
silent_possible = true
provenance = "T1550.004; a replayed token produces a presentation record only if the gateway logs it."

[[obligation]]                       # ~40 hand-written axioms, each with 2 unit tests
id = "o_session_used_implies_issued"
requires = "session.issued(S, T0) with T0 <= T"
whenever = "session.used(S, T)"
on_unsatisfied = "force_silent('r_session_issue', S, window_of(T))"
```

Every obligation MUST ship a `must_fire` test and a `must_not_fire` test. A linter rejects any rule with a delete/retract effect: non-monotonicity is expressed by time-indexing only (expiry means the `t+1` fact is never derived).

25.5 Data structures.

```rust
pub struct FactId(u32);                 // ground, time-indexed atom
pub struct EventId(u64);
pub struct LicenseId(u32);

pub struct RuleInst {
    head: FactId,
    body: SmallVec<[FactId; 4]>,
    blockers: u64,                      // mask over threshold atoms; see 22.3
    evidence: Vec<EventId>,             // empty iff silent
    silent: Option<LicenseId>,
    rule_id: u16,
}
pub struct License {
    source: SourceId, interval: (Tick, Tick),
    basis: Basis,                       // Blind | Suppressed
    witness: Vec<EventId>,              // records bracketing / chain break evidence
}
pub struct Program { insts: Vec<RuleInst>, by_body: Vec<Vec<InstIdx>>, atoms: AtomTable }
pub type Cut = u64;                     // bitset over threshold atoms, |A| <= 64
pub struct Clause(u64);                 // a corridor: "cut must intersect this mask"
```

25.6 Pipeline.

```
 bundle.jsonl ──► A. LIVENESS ────────► liveness.json  (per source, per window: LIVE|BLIND|SUPPRESSED)
      │                │
      │                ▼
      └──► B. GROUNDING (semi-naive, provenance) ──► H_obs  (OR=facts, AND=rule instances)
                        │
                        ▼
              C. SILENT ENVELOPE ──► H_lic = H_obs ∪ licensed silent instances
                        │                     (+ obligation-forced instances)
                        ▼
        ┌──── P_min = H_obs ────┐        ┌──── P_max = H_lic ────┐
        ▼                       ▼        ▼                       ▼
   D/E. CUT LOOP (Reiter/MARCO)      D/E. CUT LOOP
        │  S_opt, Psi_min                │  S_rob, Psi_max
        └──────────┬─────────────────────┘
                   ▼
   F. REDUNDANCY   G. DECISIVE OBSERVATIONS   H. COST FRONTIER
                   └────────────► cert.json ────► cmd/spectra-verify (Go)
```

**A. Liveness.** For each source `s` and each candidate window `[a,b]`: `live(s,[a,b])` iff (i) observed records bracket the window, (ii) the BLAKE3 sequence chain over that source has no gap, (iii) max inter-arrival ≤ `q99(s)` computed from THIS run's own data (never a constant, never a tuned hyperparameter). Otherwise BLIND; if a chain break localizes deletion, SUPPRESSED. Run Bellman–Ford over the difference-constraint graph built from `happens-before` edges (causal links, sequence numbers, request/response pairs) to detect negative cycles; any license resting on a provably backdated timestamp is voided and recorded in `liveness.json` as `voided_by_dcg`. Output is hashed into the certificate; the Go checker recomputes it.

**B. Grounding.** Semi-naive evaluation with provenance over observed facts only, bounded by observed entities and horizon `k`. Hard caps: `MAX_INSTANCES = 2_000_000`, `MAX_FACTS = 500_000`, `MAX_GROUND_SECONDS = 120`. On a cap, set `flags.grounding_capped = true` and publish the measured sizes; NEVER claim ROBUST on a flagged run (25.9).

**C. Silent envelope.** For each rule with `silent_possible = true`, instantiate a silent instance ONLY where `∀s ∈ producing_sources(rule): ¬live(s, I)` for the instance's interval `I`. Additionally, every unsatisfied obligation forces its declared silent instance. Silent instances carry `evidence: []` and `silent: Some(license)`. `P_min` = observed instances; `P_max` = observed ∪ silent.

**D. Reachability under a cut.** Dowling–Gallier unit propagation: one unsatisfied-body counter per instance; queue facts; an instance fires when its counter hits zero and `blockers & S == 0`.

```
fn reach(p: &Program, S: Cut) -> (bool, Marking) {
    let mut cnt: Vec<u8> = p.insts.iter().map(|i| i.body.len() as u8).collect();
    let mut U = FixedBitSet::with_capacity(p.n_facts);
    let mut q: VecDeque<FactId> = p.axioms();               // bodies of length 0
    while let Some(f) = q.pop_front() {
        if !U.put(f.0 as usize) { continue }
        if f == p.goal { return (true, U) }                  // early exit
        for &ix in &p.by_body[f.0 as usize] {
            let inst = &p.insts[ix];
            if inst.blockers & S != 0 { continue }
            cnt[ix] -= 1;
            if cnt[ix] == 0 { q.push_back(inst.head) }
        }
    }
    (false, U)                                               // U is the invariant
}
```

**E. Two-sided minimal cut.** `Reach_goal` is antitone in `S` and monotone in the instance set, hence `Reach(P_min) ⊆ Reach(P_max)`; "breaks the attack in every evidence-consistent world" is obtained from TWO fixpoints, not world enumeration. Run the hitting-set loop once on each program.

```
fn min_cut(p: &Program) -> (Cut, Vec<Clause>) {
    let mut psi: Vec<Clause> = vec![];
    loop {
        let S = min_cardinality_model(&psi);        // B&B over u64, popcount-ordered,
                                                     // respecting level implications
        let (reachable, _) = reach(p, S);
        if !reachable { return (S, psi) }
        let tree = witness_tree(p, S);               // AND/OR derivation of the goal
        psi.push(Clause(corridor_mask(&tree)));      // atoms that could break this path
    }
}
```

`min_cardinality_model` is branch and bound over 64-bit masks ordered by popcount with the implication constraint `x_{k,ℓ+1} → x_{k,ℓ}` applied as a closure operation; it maintains `lower_bound` (the best proven bound so far) for the certificate. `corridor_mask(tree)` = OR of `blockers` over the instances used in the witness tree — any cut that breaks this corridor must intersect it. Outputs: `S_opt, Psi_min` from `P_min`; `S_rob, Psi_max` from `P_max`.

**Blindness premium.** `S_rob \ S_opt` — the controls required ONLY because a sensor was blind. Each such atom is annotated with the licenses responsible, and each license with its `(source, interval, basis, witness)`. This is the headline object; the UI leads with it.

**F. Redundancy index.** From `Psi`: `red(i,j) = |{corridors hit by both i and j}| / |{corridors hit by either}|`. Exact, O(|Psi|·|A|²) with popcounts, scenario-scoped. No Shapley values, no game-theoretic attribution, no probability.

**G. Decisive observation set.** Every corridor in `Psi_max \ Psi_min` exists only because of a license set. Find the minimum-cardinality set of `(source, window)` pairs whose liveness would kill all of them: exhaustive search up to size 3; above that, greedy set cover reported with its `ln n + 1` guarantee and `flags.greedy_cover = true`. Output: "enable `iam_audit` over `[t1,t2]` (40 minutes) and `credential_rotation` leaves the cut."

**H. Cost frontier.** Multiple-choice knapsack DP over `∏_k L_k` restricted to the enumerated corridors: `O(Σ_k m_k · B)` where `B` is the declared budget grid. Yields the exact Pareto set of `(declared_cost, residual_reachability)`, each point annotated with its cut and the `EventId`s of the evidence. If `costs.toml` is absent, the frontier is computed over cardinality instead and is labeled `cost_basis: "cardinality"`. SPECTRA never invents a currency figure.

25.7 Certificate.

```jsonc
{
  "mode": "ROBUST",                      // ROBUST | OPTIMISTIC_ONLY | UNSAFE
  "cut": ["x_session_binding_2", "x_egress_seg_1"],
  "hashes": {"rules":"blake3:..","bundle":"blake3:..","controls":"blake3:..",
             "liveness":"blake3:..","goal":"blake3:.."},
  "seed": 42, "k": 12, "eclipse_version": "1.0.0",
  "invariant_U": ["blake3:fact:..", "..."],        // present iff goal unreachable
  "redundancy_witnesses": [{"removed":"x_session_binding_2","tree":{...}}],
  "psi": [{"mask":"0x0000000000000024","corridor_id":3}],
  "lower_bound": 2,
  "licenses_used": [{"source":"iam_audit","interval":[1710,4110],
                     "basis":"Blind","witness":["ev_000102","ev_000188"]}],
  "measured": {"instances":2104,"facts":911,"corridors":6,"ground_ms":381,"solve_ms":44},
  "flags": {"grounding_capped": false, "subset_minimal_only": false,
            "greedy_cover": false}
}
```

25.8 The Go checker. `spectra verify cert.json --bundle b.jsonl --rules r.toml --controls c.toml`. Re-grounds from the hashed inputs and checks, in one pass:
(a) axioms ⊆ `U`;
(b) closure: every instance with `blockers & S == 0` and `body ⊆ U` has `head ∈ U`;
(c) `goal ∉ U`;
(d) every silent instance used is licensed by `liveness.json`, whose derivation it RECOMPUTES from the bundle (it does not trust the file);
(e) each redundancy witness re-derives the goal under `S \ {c}` from real `EventId` leaves;
(f) no cut smaller than `|S|` satisfies `Psi`.
Cost `O(Σ|body| + |Psi|·|A|)`. Exit codes: `0` OK, `2` invariant violated, `3` license unlicensed, `4` witness invalid, `5` smaller cut exists, `6` input hash mismatch. It prints one line per check.

```
$ spectra verify runs/sc1/cert.json
OK: inputs match hashes (5/5)
OK: closure verified (2104 instances, 911 facts)
OK: goal sess_exfil@t=1187 not in U
OK: 3 silent instances licensed; liveness recomputed, 0 voided differences
OK: 2/2 redundancy witnesses re-derive goal from real event ids
OK: no cut of size 1 satisfies Psi (6 corridors)
VERDICT ROBUST  11ms
```

25.9 Verdict rules. `ROBUST` = the cut severs the goal in `P_max`. `OPTIMISTIC_ONLY` = it severs in `P_min` but not in `P_max`. `UNSAFE` = the goal is reachable in `P_min` under the user's current configuration. A run with ANY flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) MUST NOT be presented as ROBUST: the API returns `mode: "OPTIMISTIC_ONLY"` with `downgraded_by: ["grounding_capped"]`, and the UI badge is grey, never green. Exact cardinality-minimality holds only for `|A| ≤ 64`; above that the kernel downgrades to subset-minimal and says so in the flags.

25.10 Caching. Content-addressed, under `cache/eclipse/`:
`liveness/<H(bundle,liveness_params)>`, `ground/<H(bundle,rules,k)>`, `envelope/<H(ground,liveness)>`, `psi/<H(envelope,controls,goal)>`, `cert/<H(psi,mode,costs)>`. `Psi` is the expensive artifact and is reused across the frontier DP, the redundancy index and every cut query for the same program; recomputing it when the inputs are unchanged is a bug caught by `tests/cache/psi_reuse.rs`, which asserts one solve per unique key over a 50-query workload. Cache entries store the producing `eclipse_version` and are invalidated on version change. `--no-cache` must reproduce byte-identical output.

25.11 Surfaces.

```
spectra eclipse prove      --bundle B --rules R --controls C --goal G [--mode robust|optimistic]
spectra eclipse corridors  --limit N [--explain <corridor_id>]
spectra eclipse premium                     # blindness premium + responsible licenses
spectra eclipse decisive                    # minimum (source,window) observation set
spectra eclipse redundancy --format csv|md
spectra eclipse frontier   --costs costs.toml --budget-grid 0:100:5
spectra eclipse explain    --atom x_cred_rotation_1   # why it is in the cut
spectra verify cert.json                              # Go, separate binary

POST /api/v1/eclipse/prove          -> {cert_hash, mode, cut, measured, flags}
GET  /api/v1/eclipse/cert/{hash}    -> full certificate JSON
POST /api/v1/eclipse/verify         -> checker stdout + exit code (runs the Go binary)
GET  /api/v1/eclipse/corridors      -> [{corridor_id, mask, atoms, witness_tree_url}]
GET  /api/v1/eclipse/premium        -> [{atom, licenses:[{source,interval,basis}]}]
GET  /api/v1/eclipse/decisive       -> [{source, interval, kills_corridors:[..]}]
GET  /api/v1/eclipse/redundancy     -> matrix
GET  /api/v1/eclipse/frontier       -> [{cost, residual, cut, evidence:[EventId]}]
GET  /api/v1/eclipse/counterexample/{atom} -> derivation tree with EventId leaves
```

UI (route `/prove`): a control lattice panel (level sliders generated from `controls.meta.json`), a PROVE button, a result header `Minimum cut {session_binding>=device, egress_seg>=1} — ROBUST — 6 corridors — blake3:3f9a…`, an embedded terminal pane that streams the Go checker's real stdout (never a mocked string), a corridor list with expandable AND/OR derivation trees whose leaves are clickable `EventId`s linking to the raw record, a BLINDNESS PREMIUM panel listing each premium atom with its licenses and the decisive observation that would remove it, a redundancy heatmap, a cost-frontier scatter (only when `costs.toml` is present), and the degradation stability strip across 100%→30%. Silent instances render as dashed GHOST nodes with a distinct legend entry and are excluded from every observed-event count in the UI.

25.12 Test plan (build fails otherwise).
1. `sim_kernel_agreement`: 256 randomized control configurations per fixture; for each, the concrete simulator's outcome (section 23) and the kernel's reachability under the same cut MUST agree on goal-reachability. Disagreement is a P0 bug and prints the config, the trace hash and the witness tree.
2. `antitonicity`: over the control lattice, raising any level never makes the goal reachable when it was unreachable — checked exhaustively for `|A| ≤ 16` fixtures, and on 10k random comparable pairs otherwise.
3. `rule_order_determinism`: property test re-derives the fixpoint under randomized rule and instance orderings; output must be byte-identical.
4. `haskell_admissibility_diff`: the Haskell reference checker independently decides whether each silent instance is admissible; differential test over 5k generated liveness scenarios; any divergence fails.
5. `z3_oracle` (test-only): for small fixtures, Z3 computes the true minimum cut; the kernel must match cardinality exactly. Z3 is never invoked at runtime and is not a runtime dependency.
6. `brute_force_cross_check`: for fixtures with `Σ m_k ≤ 12`, section 24's sweep enumerates every configuration; the kernel's `S_opt` must be a true minimum among the configurations the sweep shows as BLOCKED.
7. `degradation_invariant` (headline gate): across the entire 100%→30% telemetry completeness matrix, with ground truth known to the generator, the number of FALSE ROBUST verdicts MUST be zero. Any single occurrence fails the build.
8. `checker_catches_tampering`: mutation tests that flip a bit in `invariant_U`, drop a corridor from `Psi`, forge a license, and swap a witness leaf; the Go checker must reject all four with the correct exit code.
9. `obligation_axioms`: 2 unit tests per obligation (must fire / must not fire); coverage gate requires 100% of obligations tested.
10. `golden_certificates`: committed certificates for 6 fixtures; regenerated output must be byte-identical including `measured` fields' presence (values allowed to vary only in `*_ms`, which are excluded from the hash).
11. `performance`: 2k-instance scenario proves in < 2s and verifies in < 50ms on the reference container; numbers are measured and published in `reports/eclipse_bench.md`, never asserted in prose.

25.13 FORBIDDEN CLAIMS. ECLIPSE and every surface that renders it MUST NOT state or imply any of the following.
- That it proves anything about a real system. It proves properties OF THE MODEL. Soundness is relative to the rule table, the entity resolution, the declared control catalog and the telemetry ingested. An unmodeled technique remains unmodeled.
- That "no smaller cut exists" in general. The only licensed phrasing is "no smaller cut exists over the declared control catalog".
- That ROBUST means the attacker would have been stopped. ROBUST means "holds for every hypothesis the licenses admit under this catalog". The attacker is non-adaptive (section 23.8).
- That a license is an observation. Licenses are PERMISSIONS for unobserved steps. Silent instances are GHOSTs and must never be counted as observed events, detections, or evidence.
- That absence of a blind window means absence of attack. A perfectly suppressed event with no obligation and no blind window is permanently invisible; publish per-dimension blind-spot volume instead of pretending otherwise.
- Any probability, confidence score, likelihood, risk score, severity score or "cost mass". Verdicts are exactly `ROBUST / OPTIMISTIC_ONLY / UNSAFE`.
- Any dollar figure, ROI, or cost not supplied by the user in `costs.toml`.
- Any result from a flagged run presented as ROBUST (25.9).
- That it is formal verification of any real system, a compliance attestation, or an assurance case.
- Any LLM-generated element inside a certificate. LLM narration may read a certificate and restate it in prose; the narration endpoint receives only the certificate JSON, its output is stored separately as `narration.md`, and no narration text is ever hashed into, or read back out of, the certificate.
