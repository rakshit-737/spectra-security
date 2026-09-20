============================================================
13. SECURITY STATE MODEL
============================================================

13.1 PURPOSE AND NON-GOALS

Implement the security state model as ten independent, explicitly enumerated finite state machines (FSMs), one per dimension, instantiated per entity. The model is the ground truth for reconstruction: every fact leaf consumed by ECLIPSE (see section 12 for the rule table and section 18 for the kernel) is a time-indexed assertion that some entity occupied some state in some dimension.

Negative requirements:
- Do NOT model state as free-form JSON blobs, string enums invented at runtime, or ML-inferred latent states. Every state is a compile-time constant in a Rust `enum` and a Python `StrEnum`, generated from one source of truth: `spectra-core/states/dimensions.toml`.
- Do NOT add a state to any FSM without adding (a) its legal in-edges, (b) its legal out-edges, (c) at least one illegal-transition entry, (d) a unit test that the state is reachable in at least one fixture, and (e) a unit test that at least one illegal in-edge is rejected.
- Do NOT allow a "UNKNOWN" state to absorb modelling failures. `UNKNOWN` exists only where listed below and only means "no source ever observed this entity in this dimension".
- Do NOT retract states. States are never deleted or mutated. See 13.4.

13.2 CODE GENERATION CONTRACT

`dimensions.toml` is the only hand-edited artifact. `make states` regenerates:

```
spectra-core/states/dimensions.toml          # SOURCE OF TRUTH (hand-edited)
  -> crates/spectra-state/src/generated.rs   # enums, transition table, guard dispatch
  -> services/api/spectra/states/_gen.py     # StrEnum + frozen transition set
  -> checker-go/internal/states/gen_states.go# independent re-derivation for the checker
  -> docs/generated/state_machines.md        # tables below, re-rendered
  -> ui/src/generated/states.ts              # TypeScript union types
```

Build gate: `make states && git diff --exit-code` must produce no diff. A drifted generated file fails CI. The Go checker's copy is generated from the same TOML but shares no runtime code with Rust, preserving the independence requirement of section 18.

Each dimension declares:

```toml
[dimension.authentication]
entity_kind   = "principal"
initial       = "UNAUTH"
terminal      = ["LOCKED_OUT", "AUTH_REVOKED"]
criticality   = 3            # 0..3, used by section 16 severity; justified in docs/justifications/
decay         = { kind = "hard_expiry", source_field = "auth_ttl_s" }
```

13.3 THE TEN DIMENSIONS

Notation used in all tables below:
- `Ev` = event class from the normalized schema (section 9).
- `Guard` = a boolean expression over the event, prior state, and control lattice; guards are the same AST compiled for the concrete simulator and the ECLIPSE kernel (section 12).
- `Fact` = the time-indexed atom emitted. All facts are of the form `dim.state(entity, STATE, t)` plus dimension-specific payload atoms listed explicitly.
- `S?` = `silent_possible`: whether this transition may be instantiated as a GHOST (licensed, unobserved) transition inside a blind sensor window.

-- 13.3.1 AuthenticationState (entity: principal) --

States: `UNAUTH`, `PENDING_FACTOR`, `PARTIAL_AUTH`, `AUTHENTICATED`, `STEPPED_UP`, `AUTH_FAILED`, `LOCKED_OUT`, `AUTH_REVOKED`.

| # | From | Ev | Guard | To | Fact emitted | S? |
|---|------|----|-------|----|--------------|----|
| A1 | UNAUTH | auth.attempt | — | PENDING_FACTOR | `auth.attempted(p,t)` | no |
| A2 | PENDING_FACTOR | auth.factor_ok | `factors_satisfied < required` | PARTIAL_AUTH | `auth.factor(p,f,t)` | yes |
| A3 | PENDING_FACTOR | auth.factor_ok | `factors_satisfied >= required` | AUTHENTICATED | `auth.ok(p,t)` | yes |
| A4 | PARTIAL_AUTH | auth.factor_ok | `mfa >= 1` | AUTHENTICATED | `auth.ok(p,t)` | yes |
| A5 | PARTIAL_AUTH | auth.factor_fail | — | AUTH_FAILED | `auth.fail(p,t)` | no |
| A6 | PENDING_FACTOR | auth.factor_fail | — | AUTH_FAILED | `auth.fail(p,t)` | no |
| A7 | AUTH_FAILED | auth.attempt | `fail_count < lockout_threshold` | PENDING_FACTOR | `auth.attempted(p,t)` | no |
| A8 | AUTH_FAILED | auth.attempt | `fail_count >= lockout_threshold` | LOCKED_OUT | `auth.lockout(p,t)` | no |
| A9 | AUTHENTICATED | auth.stepup_ok | `mfa >= 2` | STEPPED_UP | `auth.stepup(p,t)` | yes |
| A10 | AUTHENTICATED | auth.revoke | — | AUTH_REVOKED | `auth.revoked(p,t)` | no |
| A11 | STEPPED_UP | auth.revoke | — | AUTH_REVOKED | `auth.revoked(p,t)` | no |
| A12 | LOCKED_OUT | auth.unlock | `admin_action` | UNAUTH | `auth.unlocked(p,t)` | no |
| A13 | AUTHENTICATED | clock.tick | `t > issued + auth_ttl_s` | UNAUTH | (no fact at t+1) | n/a |

Illegal (must be rejected by the linter and produce an ILLEGAL transition record per section 16):
- `UNAUTH -> AUTHENTICATED` (authentication without an attempt record or a licensing blind window).
- `UNAUTH -> STEPPED_UP`, `PARTIAL_AUTH -> STEPPED_UP` (step-up without a base authentication).
- `LOCKED_OUT -> AUTHENTICATED` (lockout bypass).
- `AUTH_REVOKED -> {AUTHENTICATED, STEPPED_UP, PARTIAL_AUTH}` (resurrection after revocation).
- `AUTHENTICATED -> PENDING_FACTOR` (backwards factor flow).
- Any transition into `AUTHENTICATED` where `mfa_control >= 1` and no `auth.factor` fact of class `possession|biometric` exists in `[t-window, t]`.

```
                 auth.attempt
      UNAUTH ────────────────► PENDING_FACTOR
        ▲  ▲                     │   │
        │  │  factor_ok(<req)    │   │ factor_fail
        │  │  ┌──────────────────┘   ▼
        │  │  ▼                    AUTH_FAILED ──┐ attempt, n<thr
        │  │ PARTIAL_AUTH ──factor_fail──►│      └──────┐
        │  │  │                            │            │
        │  │  │ factor_ok(mfa>=1)          │ attempt    ▼
        │  │  ▼                            │ n>=thr  (back to
        │  └─AUTHENTICATED ◄───────────────┘         PENDING)
        │       │      ▲                             LOCKED_OUT
        │ ttl   │      │ stepup_ok(mfa>=2)               │
        └───────┤      ▼                                 │ unlock
                │   STEPPED_UP                           │ (admin)
         revoke │      │ revoke                          │
                ▼      ▼                                 ▼
             AUTH_REVOKED  (terminal)                 UNAUTH
```

-- 13.3.2 SessionState (entity: session) --

States: `NONE`, `ISSUED`, `ACTIVE`, `IDLE`, `ELEVATED`, `MIGRATED`, `EXPIRED`, `REVOKED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| S1 | NONE | session.issue | `auth.state(p)=AUTHENTICATED\|STEPPED_UP` | ISSUED | `session.issued(s,p,ctx,t)` | yes |
| S2 | ISSUED | session.use | `binding_match(ctx_use, ctx_issue)` | ACTIVE | `session.used(s,t)` | yes |
| S3 | ISSUED | session.use | `!binding_match && session_binding == 0` | MIGRATED | `session.migrated(s,ctx',t)` | yes |
| S4 | ISSUED | session.use | `!binding_match && session_binding >= 1` | REVOKED | `session.revoked(s,"binding",t)` | no |
| S5 | ACTIVE | session.use | — | ACTIVE | `session.used(s,t)` | yes |
| S6 | ACTIVE | clock.tick | `t - last_use > idle_ttl_s` | IDLE | `session.idle(s,t)` | n/a |
| S7 | IDLE | session.use | `t - last_use <= abs_ttl_s` | ACTIVE | `session.used(s,t)` | yes |
| S8 | ACTIVE | priv.elevate_ok | `privilege.state(p)=ELEVATED_*` | ELEVATED | `session.elevated(s,t)` | yes |
| S9 | MIGRATED | session.use | — | MIGRATED | `session.used(s,t)` | yes |
| S10 | {ISSUED,ACTIVE,IDLE,ELEVATED,MIGRATED} | clock.tick | `t > issued + abs_ttl_s` | EXPIRED | (no fact at t+1) | n/a |
| S11 | any non-terminal | session.revoke | — | REVOKED | `session.revoked(s,reason,t)` | no |

Illegal:
- `NONE -> ACTIVE` (use before issue; this is the canonical obligation axiom `session.used ⇒ session.issued` of section 12.C).
- `EXPIRED -> {ACTIVE, ELEVATED}` and `REVOKED -> *` except `REVOKED -> REVOKED`.
- `ISSUED -> ELEVATED` (elevation without a use).
- `MIGRATED -> ACTIVE` (a migrated session never silently re-earns binding; it must be re-issued).
- Any `session.issued` whose principal is not `AUTHENTICATED` or `STEPPED_UP` at `t`.

```
   NONE ──issue(authed)──► ISSUED ──use(bound)──► ACTIVE ◄──use──┐
                             │  │                  │  ▲          │
        use(!bound,binding=0)│  │use(!bound,       │  │use       │
                             │  │      binding>=1) │  │          │
                             ▼  ▼                  ▼  │          │
                        MIGRATED  REVOKED        IDLE ┘          │
                             │        ▲            (idle_ttl)    │
                        use  └────────┤                          │
                                      │            ACTIVE ──priv.elevate_ok──► ELEVATED
                      revoke (any) ───┘                                            │
                                                                                   │
        any non-terminal ──clock.tick(t > issued+abs_ttl)──► EXPIRED ◄─────────────┘
```

-- 13.3.3 CredentialState (entity: credential) --

States: `NONEXISTENT`, `PROVISIONED`, `ACTIVE`, `IN_ROTATION`, `SUPERSEDED`, `EXPOSED`, `EXPIRED`, `REVOKED`, `COMPROMISE_CONFIRMED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| C1 | NONEXISTENT | cred.create | — | PROVISIONED | `cred.created(c,owner,t)` | yes |
| C2 | PROVISIONED | cred.first_use | — | ACTIVE | `cred.used(c,t)` | yes |
| C3 | ACTIVE | cred.use | — | ACTIVE | `cred.used(c,t)` | yes |
| C4 | ACTIVE | cred.rotate_begin | `rotation_control >= 1` | IN_ROTATION | `cred.rotating(c,t)` | no |
| C5 | IN_ROTATION | cred.rotate_commit | — | SUPERSEDED | `cred.superseded(c,c',t)` | no |
| C6 | {PROVISIONED,ACTIVE} | cred.read_by_other | `reader != owner` | EXPOSED | `cred.exposed(c,reader,t)` | yes |
| C7 | EXPOSED | cred.use | `actor != owner` | EXPOSED | `cred.used_by(c,actor,t)` | yes |
| C8 | EXPOSED | analyst.confirm | — | COMPROMISE_CONFIRMED | `cred.compromised(c,t)` | no |
| C9 | {ACTIVE,EXPOSED,IN_ROTATION} | clock.tick | `t > issued + cred_ttl_s` | EXPIRED | (no fact at t+1) | n/a |
| C10 | any non-terminal | cred.revoke | — | REVOKED | `cred.revoked(c,t)` | no |

Illegal: `NONEXISTENT -> ACTIVE`; `SUPERSEDED -> ACTIVE`; `REVOKED -> {ACTIVE, EXPOSED}`; `EXPIRED -> ACTIVE`; `COMPROMISE_CONFIRMED -> ACTIVE`; any `cred.used` whose credential has no `cred.created` ancestor (obligation axiom).

-- 13.3.4 PrivilegeState (entity: principal x scope) --

States: `BASELINE`, `REQUESTED`, `APPROVED`, `ELEVATED_JIT`, `ELEVATED_STANDING`, `DELEGATED`, `ESCALATED_UNAPPROVED`, `DEESCALATED`, `SUSPENDED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| P1 | BASELINE | priv.request | — | REQUESTED | `priv.requested(p,sc,t)` | no |
| P2 | REQUESTED | priv.approve | `approver != requester` | APPROVED | `priv.approved(p,sc,t)` | no |
| P3 | APPROVED | priv.activate | `approval_control >= 1` | ELEVATED_JIT | `priv.elevated(p,sc,"jit",t)` | yes |
| P4 | BASELINE | priv.grant | `approval_control == 0` | ELEVATED_STANDING | `priv.elevated(p,sc,"standing",t)` | yes |
| P5 | BASELINE | rbac.role_bind | `rbac_control == 0 \|\| !separation_violated` | ELEVATED_STANDING | `priv.role(p,r,t)` | yes |
| P6 | {ELEVATED_JIT,ELEVATED_STANDING} | priv.delegate | — | DELEGATED | `priv.delegated(p,q,sc,t)` | yes |
| P7 | BASELINE | priv.observed_use | `no approval ancestor` | ESCALATED_UNAPPROVED | `priv.escalated(p,sc,t)` | yes |
| P8 | ELEVATED_JIT | clock.tick | `t > elevated + jit_ttl_s` | DEESCALATED | (no fact at t+1) | n/a |
| P9 | any elevated | priv.suspend | — | SUSPENDED | `priv.suspended(p,sc,t)` | no |

Illegal: `REQUESTED -> ELEVATED_*` (skipping approval when `approval_control >= 1`); `BASELINE -> DELEGATED`; `SUSPENDED -> ELEVATED_*`; `DEESCALATED -> ELEVATED_JIT` without a fresh `priv.request`; any `priv.approved` where approver == requester while `separation_of_duty >= 1`.

-- 13.3.5 DeviceTrustState (entity: device) --

States: `UNKNOWN`, `ENROLLED`, `COMPLIANT`, `NONCOMPLIANT`, `ATTESTED`, `ATTESTATION_STALE`, `QUARANTINED`, `RETIRED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| D1 | UNKNOWN | dev.enroll | — | ENROLLED | `dev.enrolled(d,t)` | yes |
| D2 | ENROLLED | dev.posture_ok | — | COMPLIANT | `dev.compliant(d,t)` | yes |
| D3 | ENROLLED | dev.posture_fail | — | NONCOMPLIANT | `dev.noncompliant(d,t)` | yes |
| D4 | COMPLIANT | dev.attest_ok | `device_trust >= 2` | ATTESTED | `dev.attested(d,t)` | no |
| D5 | ATTESTED | clock.tick | `t > attested + attest_ttl_s` | ATTESTATION_STALE | (no fact at t+1) | n/a |
| D6 | {NONCOMPLIANT,ATTESTATION_STALE} | dev.quarantine | `device_trust >= 1` | QUARANTINED | `dev.quarantined(d,t)` | no |
| D7 | COMPLIANT | dev.posture_fail | — | NONCOMPLIANT | `dev.noncompliant(d,t)` | yes |
| D8 | any | dev.retire | — | RETIRED | `dev.retired(d,t)` | no |

Illegal: `UNKNOWN -> {COMPLIANT, ATTESTED}`; `QUARANTINED -> ATTESTED` without an intervening `ENROLLED`; `RETIRED -> *`; `NONCOMPLIANT -> ATTESTED`.

-- 13.3.6 ProcessState (entity: process) --

States: `NONEXISTENT`, `SPAWNED`, `RUNNING`, `IMAGE_MODIFIED`, `PRIV_CHANGED`, `SUSPENDED`, `ORPHANED`, `EXITED`, `TERMINATED_BY_CONTROL`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| R1 | NONEXISTENT | proc.exec | — | SPAWNED | `proc.spawned(pid,ppid,img,t)` | yes |
| R2 | SPAWNED | proc.syscall | — | RUNNING | `proc.running(pid,t)` | yes |
| R3 | RUNNING | proc.image_write | `target == self.image` | IMAGE_MODIFIED | `proc.image_mod(pid,t)` | yes |
| R4 | RUNNING | proc.setuid \| proc.token_dup | — | PRIV_CHANGED | `proc.privchg(pid,from,to,t)` | yes |
| R5 | RUNNING | proc.parent_exit | — | ORPHANED | `proc.orphaned(pid,t)` | yes |
| R6 | any live | proc.exit | — | EXITED | `proc.exited(pid,code,t)` | yes |
| R7 | any live | control.kill | `edr_control >= 1` | TERMINATED_BY_CONTROL | `proc.killed(pid,t)` | no |

Illegal: `NONEXISTENT -> RUNNING`; `EXITED -> *` except self-loop; any `proc.spawned` whose `ppid` has no `proc.spawned`/`proc.running` fact live at `t` (obligation axiom, forces a GHOST parent inside a blind window or an ILLEGAL record outside one).

-- 13.3.7 NetworkExposureState (entity: host x interface) --

States: `ISOLATED`, `INTERNAL_ONLY`, `SEGMENTED`, `CROSS_SEGMENT`, `EGRESS_ALLOWED`, `INGRESS_EXPOSED`, `PUBLIC`, `TUNNELED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| N1 | ISOLATED | net.iface_up | — | INTERNAL_ONLY | `net.up(h,i,t)` | yes |
| N2 | INTERNAL_ONLY | net.policy_apply | `segmentation >= 1` | SEGMENTED | `net.segmented(h,z,t)` | no |
| N3 | {INTERNAL_ONLY,SEGMENTED} | net.conn_out | `dst_zone != src_zone && segmentation == 0` | CROSS_SEGMENT | `net.crossed(h,z,z',t)` | yes |
| N4 | any | net.conn_out | `dst == external && egress_seg == 0` | EGRESS_ALLOWED | `net.egress(h,dst,t)` | yes |
| N5 | any | net.listen | `bind == 0.0.0.0` | INGRESS_EXPOSED | `net.listen(h,port,t)` | yes |
| N6 | INGRESS_EXPOSED | net.publish | — | PUBLIC | `net.public(h,port,t)` | no |
| N7 | EGRESS_ALLOWED | net.tunnel_detect | `proto_mismatch` | TUNNELED | `net.tunnel(h,dst,t)` | yes |

Illegal: `ISOLATED -> {EGRESS_ALLOWED, PUBLIC, CROSS_SEGMENT}`; `SEGMENTED -> CROSS_SEGMENT` while `segmentation >= 1` (this is a control-violation, not a legal edge); `PUBLIC -> ISOLATED` without a `net.policy_apply`.

-- 13.3.8 ResourceState (entity: resource) --

States: `UNTOUCHED`, `ENUMERATED`, `READ`, `WRITTEN`, `EXFIL_STAGED`, `EXFIL_TRANSFERRED`, `ENCRYPTED`, `DELETED`, `RESTORED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| X1 | UNTOUCHED | res.list | — | ENUMERATED | `res.enumerated(r,a,t)` | yes |
| X2 | {UNTOUCHED,ENUMERATED} | res.read | `authz_ok \|\| rbac == 0` | READ | `res.read(r,a,t)` | yes |
| X3 | READ | res.copy_local | — | EXFIL_STAGED | `res.staged(r,a,path,t)` | yes |
| X4 | EXFIL_STAGED | net.egress | `dst == external` | EXFIL_TRANSFERRED | `res.exfil(r,a,dst,t)` | yes |
| X5 | {READ,WRITTEN} | res.write | — | WRITTEN | `res.written(r,a,t)` | yes |
| X6 | WRITTEN | res.bulk_rewrite | `entropy_delta_flag` | ENCRYPTED | `res.encrypted(r,a,t)` | yes |
| X7 | any | res.delete | — | DELETED | `res.deleted(r,a,t)` | yes |
| X8 | DELETED | res.restore | — | RESTORED | `res.restored(r,t)` | no |

Illegal: `UNTOUCHED -> EXFIL_TRANSFERRED` (transfer without read; obligation axiom `res.exfil ⇒ res.read`); `DELETED -> {READ, WRITTEN}`; `EXFIL_STAGED -> UNTOUCHED`.

-- 13.3.9 ServiceIdentityState (entity: service account) --

States: `UNPROVISIONED`, `PROVISIONED`, `BOUND_TO_WORKLOAD`, `ASSUMED_BY_HUMAN`, `CHAINED`, `IMPERSONATED`, `ISOLATED`, `DECOMMISSIONED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| I1 | UNPROVISIONED | sa.create | — | PROVISIONED | `sa.created(sa,t)` | yes |
| I2 | PROVISIONED | sa.bind_workload | — | BOUND_TO_WORKLOAD | `sa.bound(sa,w,t)` | yes |
| I3 | BOUND_TO_WORKLOAD | sa.assume | `actor.kind == human && sa_isolation == 0` | ASSUMED_BY_HUMAN | `sa.assumed(sa,p,t)` | yes |
| I4 | {BOUND_TO_WORKLOAD,ASSUMED_BY_HUMAN} | sa.assume_role | `chain_depth < max_chain` | CHAINED | `sa.chained(sa,sa',depth,t)` | yes |
| I5 | any active | sa.use_from_foreign_ctx | `!binding_match` | IMPERSONATED | `sa.impersonated(sa,ctx,t)` | yes |
| I6 | any active | control.isolate | `sa_isolation >= 1` | ISOLATED | `sa.isolated(sa,t)` | no |
| I7 | any | sa.delete | — | DECOMMISSIONED | `sa.decommissioned(sa,t)` | no |

Illegal: `UNPROVISIONED -> {BOUND_TO_WORKLOAD, CHAINED}`; `ISOLATED -> {CHAINED, ASSUMED_BY_HUMAN}`; `DECOMMISSIONED -> *`; any `sa.assumed` while `sa_isolation >= 1`.

-- 13.3.10 TrustState (entity: ordered pair (zone|principal, zone|principal)) --

States: `NO_RELATION`, `DECLARED`, `VERIFIED`, `TRANSITIVE`, `ASSUMED_UNVERIFIED`, `DEGRADED`, `BROKEN`, `REVOKED`.

| # | From | Ev | Guard | To | Fact | S? |
|---|------|----|-------|----|------|----|
| T1 | NO_RELATION | trust.declare | — | DECLARED | `trust.declared(a,b,t)` | no |
| T2 | DECLARED | trust.verify | `proof_present` | VERIFIED | `trust.verified(a,b,t)` | no |
| T3 | VERIFIED | trust.derive | `trust.state(b,c) in {VERIFIED,TRANSITIVE} && depth < max_trust_depth` | TRANSITIVE | `trust.transitive(a,c,depth,t)` | yes |
| T4 | NO_RELATION | access.succeeded | `no declared edge` | ASSUMED_UNVERIFIED | `trust.assumed(a,b,t)` | yes |
| T5 | {VERIFIED,TRANSITIVE} | trust.proof_stale | `t > verified + trust_ttl_s` | DEGRADED | (no fact at t+1) | n/a |
| T6 | any | trust.violation | — | BROKEN | `trust.broken(a,b,t)` | no |
| T7 | any | trust.revoke | — | REVOKED | `trust.revoked(a,b,t)` | no |

Illegal: `NO_RELATION -> VERIFIED`; `BROKEN -> VERIFIED` without a fresh `trust.declare`; `REVOKED -> *`; `TRANSITIVE` at depth > `max_trust_depth`.

13.4 MONOTONICITY AND TIME INDEXING

Implement all ten FSMs so that no fact is ever retracted:
1. A state occupancy is the fact `dim.state(entity, STATE, t)` for each discrete tick `t` in the occupancy interval, materialized lazily as an interval `[t_enter, t_exit)`.
2. Expiry, decay and revocation are implemented as *non-derivation at `t+1`*, never as deletion of the fact at `t`. Rows marked `n/a` in the `S?` column above are clock-driven and emit no new fact.
3. `scripts/lint_rules.py` must fail the build if any rule in `rules.toml` or any generated transition declares a delete, retract, or overwrite effect. The linter greps the generated Rust for `remove(`, `retain(`, `clear(` inside the state module and fails on a hit outside an explicit `#[allow(spectra::mutation, reason = "...")]` with a non-empty reason string.
4. Property test `prop_rule_order_determinism`: re-run the fixpoint over 512 randomized rule orderings and randomized event-batch partitions; the serialized state log must be byte-identical every time.

13.5 COMPOSITE SYSTEM STATE

Define the composite security state at time `t` as the indexed product

```
  Sigma(t) = PRODUCT over e in Entities(t) of  PRODUCT over d in Dims(e)  S_d(e, t)
```

where `Dims(e)` is the set of dimensions whose `entity_kind` matches `e`. Do not materialize this product. Enforce tractability with these five mechanisms, all of which must be implemented and measured:

1. **Factored representation.** Store `Sigma(t)` as a sparse map `(entity_id, dim_id) -> (state_u8, since_t, evidence_head)`. Absent keys mean "initial state of that dimension". Memory is `O(touched entities x touched dimensions)`, not `O(product)`.
2. **Touch-set restriction.** Only entities that appear in at least one ingested event, or that are forced into existence by an obligation axiom, are ever instantiated. The generator's entity universe is never enumerated for its own sake.
3. **Declared coupling graph.** Cross-dimension dependencies are not implicit. `dimensions.toml` declares `couples_to = [...]` per dimension; the guard compiler rejects any guard that reads a dimension not listed. The coupling graph must be acyclic per tick; a cycle check runs at build time. Current legal couplings: `session -> authentication`, `session -> privilege`, `privilege -> trust`, `resource -> privilege`, `resource -> network`, `service_identity -> credential`, `network -> device_trust`.
4. **Horizon and cap.** Grounding is bounded by horizon `k` from `goal.toml` and by hard caps `max_entities`, `max_facts`, `max_rule_instances` in `limits.toml`. When a cap binds, set `flags.grounding_capped = true` in the certificate; a capped run may never be reported ROBUST (section 18).
5. **Published, not claimed, sizes.** `spectra stats states` prints the real numbers for each fixture: entity count per kind, occupied states per dimension, interval count, peak resident bytes. These numbers go into `docs/generated/state_sizes.md` and are regenerated by CI. Do NOT write a size estimate into prose; print it from a run.

Define the composite projection API precisely:

```rust
/// Point-in-time composite state. `t` is a logical tick (see section 14.4).
pub fn composite_at(&self, t: Tick) -> CompositeState;
/// Projection onto one dimension across all entities.
pub fn slice(&self, t: Tick, d: DimId) -> BTreeMap<EntityId, StateOccupancy>;
/// Projection onto one entity across all its dimensions.
pub fn profile(&self, t: Tick, e: EntityId) -> BTreeMap<DimId, StateOccupancy>;
```

All three return `BTreeMap`, never `HashMap`, so that iteration order is deterministic and serialization is byte-stable.

Negative requirements:
- Do NOT compute a "composite risk score" over `Sigma(t)`. There is no scalar summary of the composite state.
- Do NOT cross-product dimensions to create derived meta-states such as `AUTHENTICATED_AND_ELEVATED`. Guards read multiple dimensions; states do not merge.
- Do NOT introduce probabilistic or fuzzy state membership. Occupancy is boolean.

============================================================
14. TRANSITION SEMANTICS
============================================================

14.1 THE TRANSITION RECORD

A `Transition` is the single unit of the state log. It is content-addressed and immutable. Implement exactly this schema; `schemas/transition.schema.json` is the normative copy and the Rust/Python/Go types are generated from it.

```json
{
  "$id": "https://spectra.local/schemas/transition.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["tid","seq","tick","wall_ns","entity","dimension","from_state",
               "to_state","rule_id","trigger","evidence","support","determinism"],
  "properties": {
    "tid":        {"type":"string","pattern":"^blake3:[0-9a-f]{64}$"},
    "seq":        {"type":"integer","minimum":0},
    "tick":       {"type":"integer","minimum":0},
    "wall_ns":    {"type":"integer"},
    "epoch":      {"type":"integer","minimum":0},
    "entity":     {"type":"string","pattern":"^[a-z_]+:[A-Za-z0-9._@:\\-]{1,128}$"},
    "dimension":  {"enum":["authentication","session","credential","privilege",
                           "device_trust","process","network_exposure","resource",
                           "service_identity","trust"]},
    "from_state": {"type":"string"},
    "to_state":   {"type":"string"},
    "rule_id":    {"type":"integer","minimum":0,"maximum":65535},
    "trigger":    {"enum":["EVENT","CLOCK","OBLIGATION","LICENSE","BACKFILL"]},
    "evidence":   {"type":"array","items":{"type":"string","pattern":"^ev:[0-9a-f]{32}$"}},
    "support":    {"enum":["OBSERVED","PARTIAL","GHOST"]},
    "license_id": {"type":["string","null"]},
    "guard_trace":{"type":"array","items":{"type":"string"}},
    "control_mask":{"type":"integer","minimum":0},
    "classification":{"enum":["LEGAL","ILLEGAL","ANOMALOUS","POLICY_VIOLATING"]},
    "superseded_by":{"type":["string","null"]},
    "determinism":{"type":"object","required":["rules_hash","config_hash","seed"],
      "properties":{"rules_hash":{"type":"string"},"config_hash":{"type":"string"},
                    "seed":{"type":"integer"}}}
  }
}
```

Rules:
- `tid = blake3(canonical_json(record minus {tid, seq, superseded_by}))`. Canonical JSON = RFC 8785 JCS. `tid` is the FactId key used by ECLIPSE leaves.
- `support = GHOST` requires `license_id != null` and `evidence == []`. `support = OBSERVED` requires `evidence` non-empty and `license_id == null`. `support = PARTIAL` requires non-empty `evidence` and a non-null `license_id` (some body atoms observed, some licensed). The schema alone cannot express this; enforce it in `validate_transition()` with a dedicated unit test per combination (9 cases, 3 valid, 6 rejected).
- `guard_trace` records the guard AST node ids that evaluated true, in evaluation order. It exists so the Go checker can re-run the guard without the Rust evaluator.

14.2 DERIVATION FROM EVENTS

Derivation is a pure function. Implement it with this signature and no interior mutability, no global state, no wall-clock reads, no RNG:

```rust
pub fn derive(
    prior: &StateView,        // immutable snapshot at tick t-1
    batch: &[NormalizedEvent],// all events with tick == t, pre-sorted by OrderKey
    cfg:   &Config,           // rules, controls, limits; hashed into determinism
) -> Result<Vec<Transition>, DeriveError>;
```

Pipeline per tick:

```
 normalized events (tick t)
        |
        v
 [1] dedupe by dedup_key         -> drops exact + semantic duplicates (14.7)
        |
        v
 [2] total-order sort by OrderKey (14.3)
        |
        v
 [3] for each event, in order:
       match (entity, dimension, prior_state, event_class)
         against generated transition table
       -> candidate transitions (possibly several dimensions per event)
        |
        v
 [4] guard evaluation against control_mask + prior + this-tick partial state
        |
        v
 [5] conflict resolution across candidates for the same (entity,dimension) (14.8)
        |
        v
 [6] obligation closure: unsatisfied axioms force OBLIGATION/LICENSE transitions
        |
        v
 [7] clock transitions: expiry/decay for every (entity,dimension) whose deadline
       falls in (t-1, t]  -- evaluated AFTER event transitions, never before
        |
        v
 [8] classification (section 16) + tid computation + seq assignment
        |
        v
 Vec<Transition>, appended to the state log
```

Step 7 running after step 6 is normative: an event arriving in the same tick as an expiry deadline is processed against the pre-expiry state. Document this in `docs/semantics.md` and test it with fixture `tick_boundary_expiry`.

14.3 TOTAL ORDERING AND TIE-BREAKING

Define `OrderKey` as an 6-tuple compared lexicographically. Every comparison in the engine uses it; no other ordering exists anywhere in the codebase.

```rust
#[derive(PartialEq, Eq, PartialOrd, Ord)]
pub struct OrderKey {
    pub tick:        u64,   // normalized logical tick (14.5)
    pub source_rank: u16,   // from sources.toml `rank`, lower = more authoritative
    pub seq_in_src:  u64,   // per-source monotone sequence number from the BLAKE3 chain
    pub event_class: u16,   // stable numeric id from the event taxonomy
    pub entity_hash: u128,  // blake3-128 of canonical entity id
    pub event_id:    u128,  // blake3-128 of the raw record bytes; final tiebreak
}
```

Requirements:
- `event_id` is a total tiebreak: two distinct records can never compare equal. Assert this with `debug_assert!` and a property test over 10^6 synthetic records.
- Ties are NEVER broken by arrival order, file order, thread id, iteration order of a hash map, or timestamp alone. `scripts/lint_order.py` greps for `sort_by_key(|e| e.timestamp)` and similar and fails the build.
- Parallelism is allowed only in map-phase normalization. The derive step is single-threaded per partition, and partitions are keyed by `entity_hash % n` so that cross-partition ordering cannot matter; a test runs `n ∈ {1,2,4,8,16}` and demands identical output.

14.4 LOGICAL TICKS

`tick` is a monotone integer, not a timestamp. Define `tick = floor((t_norm_ns - run_origin_ns) / tick_width_ns)` with `tick_width_ns` from `config/time.toml`. Default `tick_width_ns = 1_000_000` (1 ms); this value is a declared constant with a justification entry (see 16.6). Multiple events may share a tick; ordering within a tick is `OrderKey`.

14.5 CLOCK SKEW NORMALIZATION

Sources disagree. Normalize with a deterministic, evidence-only procedure. Do NOT call NTP, do NOT read the host clock, do NOT assume any source is correct by default.

1. Build a difference-constraint graph `G`: nodes are sources, plus a reference node `Z`. For each *causal pair* observed in the bundle (a record in source `a` that references an identifier first created by a record in source `b`, e.g. a session id), add the constraint `off(b) - off(a) <= t_a - t_b`.
2. Add per-source prior bounds from `sources.toml` (`max_skew_ms`, user-declared), as edges to and from `Z`.
3. Run Bellman-Ford. If a negative cycle exists, the bundle contains provably inconsistent timestamps: emit `skew.inconsistent` with the cycle's edges and their `EventId`s, mark the participating sources' intervals as `SUPPRESSED` basis for licensing (section 12.A), and DO NOT silently pick a winner.
4. Otherwise take the shortest-path potentials as per-source offsets `off(s)`, rounded to whole ticks toward zero, and set `t_norm = t_raw + off(s)`.
5. Write `skew.json` (offsets, constraint count, cycle report) and hash it into the certificate alongside `liveness.json`.

Backdating detection: any record whose normalized time precedes the normalized time of a record it causally depends on voids every license resting on that record. This is the same Bellman-Ford pass; do not implement a second one.

14.6 IDEMPOTENCY ON RE-INGEST

Requirement: ingesting the identical bundle twice, or ingesting a bundle that is a superset containing an earlier bundle verbatim, must leave the state log identical modulo nothing. Implement:

- `dedup_key = blake3(source_id || seq_in_src || canonical_bytes(record))`. Stored in table `ingest_seen` with a unique index. A second insert is a no-op that increments `ingest_dup_count`.
- The derive function is idempotent by construction: it is a pure function of `(prior, batch, cfg)`, and a re-ingest produces the same `batch`.
- Test `test_reingest_idempotent`: ingest fixture, snapshot `state_log` hash, ingest again, assert identical hash and assert `ingest_dup_count == len(fixture)`.
- Test `test_partial_reingest`: ingest first 60% then the whole bundle; the final log hash must equal the log hash of a single full ingest.

14.7 DUPLICATE SUPPRESSION (EXACT AND SEMANTIC)

Two tiers, in this order:

1. **Exact**: identical `dedup_key`. Dropped, counted in `dup_exact`.
2. **Semantic**: same `(source_id, event_class, entity, t_norm_tick)` and equal payload after dropping fields listed as `volatile` in `sources.toml` (request ids, agent hostnames, retry counters). Dropped, counted in `dup_semantic`, and the dropped `EventId` is recorded in the surviving transition's `evidence` array so no evidence is lost.

Negative: do NOT use fuzzy similarity, edit distance, or embeddings for deduplication. Do NOT drop a record merely because it is "close" in time. The degradation harness (section 20) injects duplicates deliberately; suppression must be measurable against known ground truth, and `dup_semantic` false-drop rate must be reported per completeness level.

14.8 CONFLICTING EVIDENCE RESOLUTION

Conflict = two or more candidate transitions for the same `(entity, dimension)` at the same tick with different `to_state`. Resolve by this ladder, applied top to bottom, stopping at the first that discriminates. Record the rung used in `guard_trace` as `conflict:rung=<n>`.

| Rung | Criterion | Rationale |
|------|-----------|-----------|
| 1 | Prefer `support=OBSERVED` over `PARTIAL` over `GHOST` | Evidence beats license |
| 2 | Prefer the candidate whose source has lower `source_rank` | Declared authority, user-configured |
| 3 | Prefer the candidate with strictly more distinct `EventId`s | More corroboration |
| 4 | Prefer the transition whose `to_state` is the more restrictive one under the dimension's declared `restrictiveness` partial order | Fail closed |
| 5 | Lowest `OrderKey` wins | Total, deterministic |

Rung 4's partial order is declared per dimension in `dimensions.toml` (e.g. session: `REVOKED > EXPIRED > MIGRATED > IDLE > ACTIVE > ISSUED`). If two candidates are incomparable in that order, rung 4 does not discriminate and rung 5 applies.

Additionally: when a conflict is resolved at rung 2 or above, emit a `conflict` record listing all losing candidates with their evidence. The losing candidates are NOT discarded from the evidence store; they are retained and surfaced in the UI as "contested". A conflict resolved above rung 5 sets `flags.contested = true` on the run.

Negative: do NOT resolve conflicts by majority vote over sources, by recency alone, by a trained classifier, or by a confidence score. There are no confidence scores anywhere in SPECTRA.

14.9 OUT-OF-ORDER AND LATE EVENTS

Define `watermark W = max(t_norm) - lateness_bound_ms`, with `lateness_bound_ms` per source from `sources.toml`.

- An event with `t_norm >= W` is *in-window*: buffer it, re-sort the tick's batch, and derive normally. No special handling.
- An event with `t_norm < W` is *late*: it triggers a **reorg** (section 15.5). It is never dropped and never appended at the tail with a falsified timestamp.
- An event whose `t_norm` is in the future relative to `max(t_norm)` of its own source beyond `max_skew_ms` is *implausible*: it is ingested, flagged `implausible_future`, excluded from liveness computation, and cannot license anything.

Requirement: the final state log must be independent of arrival order. Test `test_arrival_order_invariance`: shuffle the bundle with 64 distinct seeds, ingest each shuffle with the streaming ingester, and assert all 64 final `state_log` hashes are equal to the batch-ingest hash.

14.10 EXPIRY AND DECAY

Three decay kinds only; declared per dimension in `dimensions.toml`:

| Kind | Semantics | Example |
|------|-----------|---------|
| `hard_expiry` | At `t_enter + ttl`, the occupancy interval closes and the FSM moves to the declared expiry state. The fact at `t < deadline` remains forever. | session `abs_ttl_s` |
| `sliding_expiry` | Deadline is recomputed to `t_last_use + ttl` on each refreshing event, which must be listed in `refresh_on = [...]`. | session idle |
| `none` | No decay. Only explicit events change the state. | trust `BROKEN` |

Requirements:
- Every TTL comes from configuration or from a field in the ingested event. No TTL literal appears in code (enforced by the constants gate, 16.6).
- Decay creates a `Transition` with `trigger = CLOCK` and `evidence = []` but `support = OBSERVED`, because the deadline is derived from observed facts plus declared config, not from a license.
- Decay is never "partial" or "gradual". There is no score that decays. Do NOT implement exponential decay of any risk value; no such value exists.

============================================================
15. STATE STORE AND SNAPSHOTTING
============================================================

15.1 STORAGE MODEL

Event-sourced append-only log plus periodic materialized snapshots. PostgreSQL is the store of record; Redis holds only ephemeral derived caches that are reconstructible from Postgres and are never read by the kernel or the checker.

```
 raw_event  (immutable, content-addressed)
     |  normalize + entity resolve (section 9, 10)
     v
 norm_event (immutable)
     |  derive() per tick (section 14.2)
     v
 state_log  (immutable, append-only, totally ordered by seq)
     |  fold every snapshot_interval_ticks
     v
 state_snapshot (materialized composite state at a tick)
     |  read path
     v
 composite_at(T) = latest snapshot with tick <= T, then replay state_log
                   for seq in (snap.seq_end, last seq with tick <= T]
```

15.2 SCHEMA (normative DDL)

```sql
CREATE TABLE raw_event (
  event_id      BYTEA PRIMARY KEY,               -- blake3-128 of raw bytes
  source_id     SMALLINT NOT NULL REFERENCES source(source_id),
  seq_in_src    BIGINT   NOT NULL,
  chain_hash    BYTEA    NOT NULL,               -- BLAKE3 chain for gap detection
  t_raw_ns      BIGINT   NOT NULL,
  payload       JSONB    NOT NULL,
  bundle_hash   BYTEA    NOT NULL,
  UNIQUE (source_id, seq_in_src)
);

CREATE TABLE norm_event (
  event_id      BYTEA PRIMARY KEY REFERENCES raw_event(event_id),
  t_norm_ns     BIGINT   NOT NULL,
  tick          BIGINT   NOT NULL,
  event_class   SMALLINT NOT NULL,
  entity_id     BIGINT   NOT NULL REFERENCES entity(entity_id),
  order_key     BYTEA    NOT NULL,               -- packed OrderKey, 40 bytes
  dedup_key     BYTEA    NOT NULL UNIQUE,
  late          BOOLEAN  NOT NULL DEFAULT FALSE
);
CREATE INDEX norm_event_tick_order ON norm_event (tick, order_key);

CREATE TABLE state_log (
  seq           BIGSERIAL PRIMARY KEY,           -- dense, gapless, per run
  run_id        UUID     NOT NULL REFERENCES run(run_id),
  epoch         INT      NOT NULL DEFAULT 0,     -- bumped by reorg (15.5)
  tid           BYTEA    NOT NULL,               -- blake3-256, = FactId key
  tick          BIGINT   NOT NULL,
  entity_id     BIGINT   NOT NULL,
  dimension     SMALLINT NOT NULL,
  from_state    SMALLINT NOT NULL,
  to_state      SMALLINT NOT NULL,
  rule_id       SMALLINT NOT NULL,
  trigger       SMALLINT NOT NULL,
  support       SMALLINT NOT NULL,               -- 0 OBSERVED 1 PARTIAL 2 GHOST
  license_id    BIGINT   NULL REFERENCES license(license_id),
  control_mask  BIGINT   NOT NULL,
  classification SMALLINT NOT NULL,
  superseded_by BIGINT   NULL REFERENCES state_log(seq),
  UNIQUE (run_id, epoch, tid)
);
CREATE INDEX state_log_pit ON state_log (run_id, entity_id, dimension, tick DESC, seq DESC);
CREATE INDEX state_log_tick ON state_log (run_id, epoch, tick, seq);

CREATE TABLE transition_evidence (
  seq       BIGINT NOT NULL REFERENCES state_log(seq),
  event_id  BYTEA  NOT NULL REFERENCES raw_event(event_id),
  role      SMALLINT NOT NULL,                   -- 0 trigger 1 corroborating 2 contested
  PRIMARY KEY (seq, event_id)
);

CREATE TABLE state_snapshot (
  run_id      UUID   NOT NULL,
  epoch       INT    NOT NULL,
  tick        BIGINT NOT NULL,
  seq_end     BIGINT NOT NULL,                   -- last state_log.seq folded in
  state_blob  BYTEA  NOT NULL,                   -- zstd(canonical CBOR of factored map)
  blob_hash   BYTEA  NOT NULL,                   -- blake3 of UNCOMPRESSED bytes
  entity_count INT   NOT NULL,
  PRIMARY KEY (run_id, epoch, tick)
);

CREATE TABLE run (
  run_id       UUID PRIMARY KEY,
  bundle_hash  BYTEA NOT NULL,
  rules_hash   BYTEA NOT NULL,
  controls_hash BYTEA NOT NULL,
  config_hash  BYTEA NOT NULL,
  seed         BIGINT NOT NULL,
  log_hash     BYTEA NULL,                        -- blake3 over the whole state log
  current_epoch INT NOT NULL DEFAULT 0
);
```

Constraints to enforce in migrations, not only in application code:
- `CHECK (support <> 2 OR license_id IS NOT NULL)` on `state_log`.
- `CHECK (support <> 0 OR license_id IS NULL)`.
- A trigger forbidding `UPDATE` and `DELETE` on `raw_event`, `norm_event`, `state_log` except setting `superseded_by` from NULL to a value exactly once.

15.3 SNAPSHOTS

- Take a snapshot every `snapshot_interval_ticks` (config, justified constant) and additionally at every tick where `|state_log| since last snapshot > snapshot_max_transitions`.
- `state_blob` is canonical CBOR of the factored map from 13.5, with keys sorted by `(entity_id, dimension)`. Compression is applied after hashing so the hash is compression-independent.
- Snapshot correctness test `test_snapshot_equals_replay`: for every snapshot in a fixture run, fold the log from tick 0 independently and assert the uncompressed bytes are identical to `state_blob`.
- Snapshots are a cache. Deleting every row of `state_snapshot` must change no query result, only latency. Test `test_snapshot_is_pure_cache` asserts this by running the full read-path suite twice, once with snapshots truncated.

15.4 POINT-IN-TIME QUERIES

Expose exactly these read operations; everything in the UI and the CLI goes through them.

| Operation | HTTP | Semantics |
|-----------|------|-----------|
| composite at T | `GET /runs/{run}/state?at={tick}` | full factored composite state |
| entity profile | `GET /runs/{run}/entities/{eid}/state?at={tick}` | all dimensions for one entity |
| dimension slice | `GET /runs/{run}/dimensions/{dim}/state?at={tick}` | all entities in one dimension |
| occupancy history | `GET /runs/{run}/entities/{eid}/history?dim={dim}` | interval list with evidence ids |
| transition detail | `GET /runs/{run}/transitions/{tid}` | full record + evidence + guard trace |
| diff | `GET /runs/{run}/state/diff?from={t1}&to={t2}` | added/changed occupancies only |

Every response carries `ETag: "blake3:<log_hash>:<epoch>:<tick>"`. Two requests with the same ETag must return byte-identical bodies. Test `test_pit_etag_stability` asserts this across process restarts and across a cold cache.

CLI transcript that must work verbatim:

```
$ spectra state at --run 7c1e --tick 41200 --entity principal:svc-deploy
dimension           state                 since_tick  support   evidence
authentication      AUTHENTICATED         41010       OBSERVED  ev:9a1c..,ev:9a2f..
session             ELEVATED              41180       OBSERVED  ev:9b77..
credential          EXPOSED               40990       GHOST     (license L-14: iam_audit BLIND [40900,41100])
privilege           ELEVATED_STANDING     41185       PARTIAL   ev:9b81..  (+license L-14)
device_trust        UNKNOWN               -           -
process             RUNNING               41192       OBSERVED  ev:9bb0..
network_exposure    EGRESS_ALLOWED        41199       OBSERVED  ev:9bc4..
resource            EXFIL_STAGED          41201       OBSERVED  ev:9bd1..
service_identity    ASSUMED_BY_HUMAN      41182       OBSERVED  ev:9b79..
trust               ASSUMED_UNVERIFIED    41186       GHOST     (license L-14)
3 GHOST occupancies. GHOST occupancies are licensed, not observed; they are
excluded from all observed-event counts.
```

15.5 REORG AND BACKFILL

When a late event arrives (14.9), the log is not rewritten in place. Perform an **epoch reorg**:

1. Determine `t_reorg = tick(late_event)`.
2. Allocate `epoch' = current_epoch + 1`.
3. Load the latest snapshot with `tick < t_reorg`, i.e. the last state provably unaffected.
4. Re-derive from that snapshot forward, over the union of previously ingested events and the late event, writing new rows at `epoch'`.
5. Set `superseded_by` on each old-epoch row whose `tid` does not appear in the new epoch, once, never again.
6. Recompute `liveness.json` and `skew.json` from scratch for the new epoch. A late event can *close* a blind window, which retroactively invalidates GHOST transitions; those become superseded, and any certificate referencing them is marked `STALE` (it is not deleted, and its hashes still verify against the epoch it was issued for).
7. Bump `run.current_epoch`. Re-run `spectra prove` if the run has an active certificate; the UI shows the before/after cut diff.

Requirements:
- Reorg is idempotent: reorging twice with the same late event is a no-op after step 1 detects the event is already present at the current epoch.
- Reorg is bounded: `t_reorg` must be at least `min_reorg_horizon_ticks` behind the head or the run is refused with an explicit error telling the operator to re-run the full ingest. Do NOT silently do a full rebuild while reporting an incremental one.
- Old epochs are retained for the run's lifetime. `GET /runs/{run}/epochs` lists them with their log hashes. This is how "the answer changed when we got the missing logs" is demonstrated honestly.

Negative: do NOT mutate `state_log` rows on backfill. Do NOT re-timestamp late events to the head. Do NOT hide a reorg from the UI.

15.6 DETERMINISM GUARANTEE

Normative statement, to be reproduced verbatim in `docs/determinism.md`:

> Given identical input bytes (`bundle_hash`), identical configuration (`rules_hash`, `controls_hash`, `config_hash`) and identical seed, SPECTRA produces a byte-identical state log, a byte-identical set of snapshot blobs, a byte-identical `liveness.json` and `skew.json`, and therefore a byte-identical certificate hash. This holds across process restarts, across thread counts, across partition counts, and across the supported OS/arch matrix.

Enforcement (all are CI gates; a failure fails the build):

| Gate | Command | Assertion |
|------|---------|-----------|
| `det/repeat` | run fixture 5x in one process | 5 identical `log_hash` |
| `det/restart` | run fixture in 5 fresh processes | 5 identical `log_hash` |
| `det/threads` | `SPECTRA_THREADS ∈ {1,2,4,8,16}` | identical `log_hash` |
| `det/partitions` | `SPECTRA_PARTITIONS ∈ {1,3,7,16}` | identical `log_hash` |
| `det/shuffle` | 64 seeded shuffles, streaming ingest | identical `log_hash` (14.9) |
| `det/arch` | linux-amd64, linux-arm64 containers | identical `log_hash` |
| `det/snapshot` | truncate snapshots, re-query | identical responses (15.3) |
| `det/checker` | Go checker re-derives from hashes | agrees with Rust on every `tid` |

Implementation obligations that make the above achievable; treat each as a review checklist item:
- No `HashMap`/`HashSet` iteration anywhere in the derive, ground, or serialize paths. Use `BTreeMap`/`IndexMap` with declared insertion order. `clippy.toml` denies `std::collections::HashMap` in `spectra-state` and `spectra-eclipse`.
- No floating point in any code path that affects the log. Anomaly statistics (section 16.4) use integer or rational arithmetic; if a float is unavoidable, it is computed with fixed-point `i64` scaled integers and the scale is declared.
- No wall-clock reads outside the ingest boundary. `Instant::now()` and `SystemTime::now()` are banned in `spectra-state` by a lint; timing for benchmarks lives in a separate crate.
- All RNG is seeded from `run.seed` via a pinned PRNG (`rand_chacha::ChaCha20Rng`), and RNG is used only in fixture generation and the degradation harness, never in derivation.
- Serialization is canonical CBOR (deterministic encoding, sorted keys, no indefinite lengths) or RFC 8785 JCS for JSON. Both are pinned; the serializer version is part of `config_hash`.

============================================================
16. ILLEGAL AND ANOMALOUS TRANSITIONS
============================================================

16.1 THREE DISJOINT CLASSES

Every transition record carries exactly one `classification`. The three non-LEGAL classes answer three different questions and must never be conflated in code, in the API, or in the UI.

| Class | Question it answers | Source of truth | Depends on data distribution? | Depends on config? |
|-------|--------------------|-----------------|-------------------------------|--------------------|
| `ILLEGAL` | Does this edge exist in the FSM at all? | `dimensions.toml` transition table (section 13) | No | No |
| `POLICY_VIOLATING` | Is this edge permitted under the configured controls? | `controls.toml` + `policy.toml` guards | No | Yes |
| `ANOMALOUS` | Is this edge rare in *this run's own* data? | computed statistics over the current bundle | Yes | No |

Hard separation requirements:
- The three classifiers live in three modules with no shared mutable state: `classify::legality`, `classify::policy`, `classify::anomaly`. `classify::anomaly` must not import `controls.toml` and must not be able to see the control mask; enforce with a crate-level visibility boundary and a test that removes `controls.toml` and asserts anomaly output is unchanged.
- A transition can be simultaneously illegal-shaped and policy-violating. When both apply, `classification = ILLEGAL` (legality dominates) and the policy finding is recorded separately in `finding` rows. The UI shows both. Do NOT collapse them.
- `ANOMALOUS` never overrides `ILLEGAL` or `POLICY_VIOLATING`.

16.2 ILLEGAL TRANSITIONS

An `ILLEGAL` record is produced when the derive step observes evidence that an entity moved between two states with no legal edge between them (the per-dimension illegal lists of section 13), or violated an obligation axiom with no license to cover it.

Handling:
1. The transition IS recorded. Do not drop it. An illegal transition is a finding about the model or about the telemetry, and suppressing it would hide exactly the cases that matter.
2. `from_state` and `to_state` are recorded as observed; the FSM enters `to_state` (the model follows reality) and the record is flagged.
3. The record carries a mandatory `illegal_reason` enum: `NO_SUCH_EDGE`, `OBLIGATION_UNSATISFIED`, `TERMINAL_STATE_EXIT`, `GUARD_CONTRADICTION`, `TEMPORAL_INVERSION`.
4. Illegal transitions are NOT usable as ECLIPSE leaves for a ROBUST verdict. A certificate whose derivation depends on an `ILLEGAL` transition sets `flags.illegal_dependency = true` and may not be reported ROBUST.
5. Every illegal reason has a fixture producing it, in `tests/fixtures/illegal/<reason>/`, and a test asserting the reason code.

Interaction with licensing: if an obligation is unsatisfied but every producing source for the missing step was BLIND over the relevant interval, the correct outcome is a GHOST transition (`trigger = LICENSE`), not an `ILLEGAL` record. If at least one producing source was live, the outcome is `ILLEGAL/OBLIGATION_UNSATISFIED`. This branch is the single most important test in the suite; give it a dedicated table-driven test with all four combinations of (obligation satisfied?) x (all sources blind?).

16.3 POLICY-VIOLATING TRANSITIONS

A `POLICY_VIOLATING` record is produced when a legal edge is taken while the configured control level forbids it. Policy is expressed in the same guard AST as everything else:

```yaml
# policy.toml (excerpt, rendered as YAML for readability)
- id: POL-SESSION-BIND
  dimension: session
  edge: "ISSUED -> MIGRATED"
  forbidden_when: "session_binding >= 1"
  rationale_ref: "docs/justifications/policy.md#pol-session-bind"

- id: POL-PRIV-SOD
  dimension: privilege
  edge: "REQUESTED -> APPROVED"
  forbidden_when: "separation_of_duty >= 1 and approver == requester"
  rationale_ref: "docs/justifications/policy.md#pol-priv-sod"

- id: POL-SA-HUMAN
  dimension: service_identity
  edge: "BOUND_TO_WORKLOAD -> ASSUMED_BY_HUMAN"
  forbidden_when: "sa_isolation >= 1"
  rationale_ref: "docs/justifications/policy.md#pol-sa-human"
```

Requirements:
- Every policy rule names an `edge` that exists in the FSM. A policy rule referencing a nonexistent edge fails the build.
- Every policy rule has a non-empty `rationale_ref` resolving to a real anchor in a real file. CI checks the anchor resolves.
- A policy violation under control level `L` must be consistent with the simulator: if the control at level `L` would actually have blocked the edge, then the edge cannot occur at all and there is no violation. `POLICY_VIOLATING` therefore means "the configuration declares this forbidden but the telemetry shows it happened", which is itself a finding about control enforcement gaps. Test `test_policy_vs_simulator_consistency` runs 256 randomized control configurations per fixture and asserts the two never disagree about which edges are reachable.

16.4 ANOMALOUS TRANSITIONS

`ANOMALOUS` means: within this run's own data, this transition is rare for this (entity_kind, dimension, edge) population. Requirements:

1. **Scenario-scoped, no training.** Statistics are computed from the current bundle only. There is no model file, no pretrained baseline, no cross-run learning. If the bundle is too small (`population < min_population`), the anomaly classifier abstains and emits `ANOMALY_ABSTAIN` with the population size. Abstention is reported, not hidden.
2. **Deterministic and integer-only.** Compute, per `(entity_kind, dimension, edge)`: the count `n_edge`, the population `N`, the empirical rank `r` of this entity's inter-arrival gap among all gaps for that edge, and the exact rational quantile `r/N`. Report `rank` and `population`, never a float probability.
3. **Declared detectors only.** Implement exactly these four, each with its own module, fixture and unit tests:
   - `RARE_EDGE`: `n_edge * rare_edge_denominator <= N` (an exact integer comparison, no division).
   - `OFF_HOURS`: the tick falls outside the per-entity observed activity envelope derived from this run.
   - `BURST`: `k` transitions of the same edge for one entity within `burst_window_ticks`, `k >= burst_threshold`.
   - `NOVEL_PAIR`: the `(entity, edge)` pair has no prior occurrence in the bundle before this tick.
4. **ML is optional and quarantined.** If the optional anomaly-detection baseline (section 22) is enabled, its output is written to a separate `ml_finding` table, is never written into `state_log.classification`, and can never affect a certificate. Removing the ML component must leave every gate green. Test `test_no_ml_no_change` runs the full suite with the ML feature flag off and compares all log hashes.

Negative: do NOT emit a "confidence", "probability", "risk score", "anomaly score in [0,1]", or "severity percentage" from the anomaly module. Rank and population only.

16.5 SEVERITY DERIVATION

Severity is a **lexicographic ordinal tuple**, not a scalar. This avoids inventing arithmetic weights that would be fabricated precision.

```
Sev(x) = ( K(x), D(x), R(x), E(x) )   compared lexicographically, high to low
```

| Component | Domain | Definition | Source |
|-----------|--------|------------|--------|
| `K` kind rank | 0..3 | `ILLEGAL=3`, `POLICY_VIOLATING=2`, `ANOMALOUS=1`, `LEGAL=0` | fixed by 16.1, not configurable |
| `D` dimension criticality | 0..3 | `dimension.criticality` from `dimensions.toml` | user-declared, justified |
| `R` reachability impact | 0..2 | `2` if this transition's `tid` appears as a leaf in at least one corridor of `Psi` for the current run; `1` if it appears in the grounded hypergraph but in no corridor; `0` otherwise | computed by the ECLIPSE kernel, section 18 |
| `E` evidence quality | 0..2 | `2` if `support=OBSERVED`, `1` if `PARTIAL`, `0` if `GHOST` | from the record |

Band mapping (the only presentation-level collapse, declared in one table and nowhere else):

| Band | Condition |
|------|-----------|
| `CRITICAL` | `K=3` and `D>=2` and `R=2` and `E=2` |
| `HIGH` | `K>=2` and `R=2` and `E>=1`, and not CRITICAL |
| `MEDIUM` | `K>=1` and (`R>=1` or `D>=2`), and not HIGH |
| `LOW` | everything else with `K>=1` |
| `INFO` | `K=0` |

Hard rules:
- A transition with `E=0` (GHOST) may never be banded above `MEDIUM`. A license is a permission, not an observation.
- `R` requires a completed ECLIPSE run. Before `spectra prove` has run, `R` is `null` and severity is reported as a partial tuple with band `PENDING`. Do NOT substitute a default value for `R`.
- Severity is never summed, averaged, or aggregated into a per-host or per-run number. `GET /runs/{run}/findings?band=HIGH` returns a count of findings per band; there is no "overall severity" field anywhere in the API. Test `test_no_aggregate_severity` greps the OpenAPI spec for forbidden field names (`risk_score`, `overall_severity`, `threat_level`, `confidence`) and fails on a hit.

Worked example that must appear as a doctest:

```
transition tid=blake3:41ab..  session ISSUED -> MIGRATED
  K = 2   (POLICY_VIOLATING: POL-SESSION-BIND, session_binding=1)
  D = 3   (dimension.session.criticality = 3)
  R = 2   (leaf of corridor #4 in Psi_max)
  E = 2   (OBSERVED: ev:7c31.., ev:7c44..)
  Sev = (2,3,2,2) -> band HIGH
```

16.6 NO MAGIC CONSTANTS

Every numeric literal that influences classification, severity, timing, or thresholds must live in configuration and have a written justification. Implement the gate, do not merely state the policy.

1. All such constants live in `config/constants.toml`, one table per subsystem:

```toml
[anomaly]
rare_edge_denominator = 50      # edge is RARE if n_edge*50 <= N
burst_window_ticks    = 5000
burst_threshold       = 8
min_population        = 30

[time]
tick_width_ns         = 1000000
min_reorg_horizon_ticks = 1000

[store]
snapshot_interval_ticks  = 10000
snapshot_max_transitions = 50000
```

2. Every key must have a matching section in `docs/justifications/constants.md`:

```markdown
### anomaly.rare_edge_denominator = 50
Decision: an edge is RARE when it accounts for at most 1/50 of the population
for its (entity_kind, dimension, edge) class.
Provenance: chosen so that the smallest fixture population (min_population=30)
cannot by itself mark every edge rare; verified by tests/anomaly/test_rare_edge_calibration.py
which enumerates populations 30..5000 and reports the resulting flag rate.
Sensitivity: sweep results for denominator in {20,50,100,200} are published in
docs/generated/constant_sensitivity.md, regenerated by `make sweep`.
Not derived from any external benchmark, dataset, or published paper.
```

3. CI gate `scripts/check_constants.py` must:
   - parse `config/constants.toml` and `docs/justifications/constants.md`, and fail if any key lacks a section or any section lacks a key;
   - fail if any justification section is missing the literal headings `Decision:`, `Provenance:`, `Sensitivity:`;
   - scan `crates/spectra-state`, `crates/spectra-eclipse`, and `services/api/spectra/` for integer or float literals outside an allowlist (`0`, `1`, `-1`, `2`, array indices, bit widths, and lines carrying `// const-ok: <reason>` with a non-empty reason), and fail on any hit;
   - fail if a justification cites a number that does not match the TOML value.

4. `make sweep` regenerates `docs/generated/constant_sensitivity.md` by re-running the affected fixtures across the declared sweep grid and printing real measured flag rates. Do NOT hand-write a sensitivity table.

Negative requirements for this section:
- Do NOT invent thresholds "because they look reasonable". If a value has no justification, it does not ship.
- Do NOT calibrate any constant against a public benchmark, CVE feed, MITRE frequency table, or an external dataset; SPECTRA is offline and its numbers come from its own runs.
- Do NOT emit a severity or anomaly result whose provenance cannot be traced to (a) a declared FSM edge, (b) a declared policy rule, or (c) a counted statistic over the current bundle. Every finding in the UI must be one click away from the exact `EventId`s and the exact counts behind it.
