============================================================
67. ADVERSARIAL THREAT MODEL OF THE PROOF KERNEL
============================================================

## 67.0 Why this section exists

Part I treats telemetry as untrusted and the kernel as trusted, and then never writes down what
an adversary who knows the kernel's source can do to it. The repository is public. `rules.toml`,
`axioms/`, `controls.toml`, the liveness pass and the license logic are all readable by the
attacker being modeled. Assume total specification knowledge. Every defense below must work
against an attacker who has read this section.

OVERRIDES Part I: ECLIPSE §9's sentence "soundness is relative to the telemetry ingested" is
upgraded from a caveat to an enforced boundary. Telemetry is not merely incomplete; it is
adversarially authored. Any kernel behavior in which *more attacker-supplied evidence* produces
*a smaller cut* or *a stronger verdict* is a defect, not a trade-off.

Implement this section as code and fixtures, not as prose in `docs/`. Its acceptance surface is
`make redteam-gate` (67.10), `make redteam-mutation` (67.11), and the linters named inline.

## 67.1 Trust boundary

```
        UNTRUSTED — attacker-writable                TRUSTED — author-controlled, hashed
 ┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
 │ record bytes, field values, identifiers  │  │ rules.toml   axioms/     controls.toml   │
 │ timestamps, sequence numbers, chain MACs │  │ er.toml      goals/      costs.toml      │
 │ record volume, inter-arrival pattern     │  │ baseline.json (calibration)              │
 │ entity cardinality, archive framing      │  │ generator + simulator source, budgets    │
 │ ORDER of records within a source         │  │ kernel, Go checker, step budgets         │
 └──────────────────────────────────────────┘  └──────────────────────────────────────────┘
                    │                                           │
                    v                                           v
   ingest ──> quarantine ──> ER ──> liveness ──> grounding ──> silent envelope ──> cut ──> cert
              [A5]           [A4]   [A2][A3]     [A5]          [A1]                [A6][A7]

 Legend: [Ax] = attack id from 67.2. The bracketed stage is where the attack lands.
 The generator's ground-truth stream is OUTSIDE this pipeline and is never an input to the
 kernel (see §62); it is only ever compared against kernel output.
```

Attacker capability classes, declared per fixture in `attack.toml`:

| class | can do | cannot do |
|---|---|---|
| `C0_observer` | read telemetry | write anything |
| `C1_emitter` | cause records to be written (normal actions) | delete, edit, forge |
| `C2_local_deleter` | delete/edit records on a host it compromised, after compromise time | touch other hosts, touch the sealer |
| `C3_local_chain_holder` | C2 plus re-chain that host's log with the host-local chain key | forge sealer digests |
| `C4_namer` | choose identifiers, hostnames, usernames, token prefixes, UA strings | modify existing records |
| `C5_flooder` | emit unbounded volume and unbounded distinct entities | exceed the range's declared resource limits |
| `C6_catalog_author` | contribute rules, blocker bits, controls, goals (supply-chain-of-the-model) | modify the kernel or the checker |

`C6` is included deliberately: a control catalog is a contribution surface, and 67.7/67.8 are the
only defenses SPECTRA has against a contributor who authors a flattering model.

## 67.2 Attack table

Every row is implemented as at least one checked-in fixture under `fixtures/redteam/<id>/`.

| id | strategy | unsound outcome | detection | fail-closed rule |
|---|---|---|---|---|
| A1 | obligation-evading suppression | false ROBUST (no license issued) | anchor-coverage audit, volume envelope vs `baseline.json`, static evasion-depth analysis | window BLIND on envelope breach; `obligation_orphan` flag bars ROBUST |
| A2 | backdating to void licenses | false ROBUST (P_max shrinks) | time-consistency pass is restriction-only; infeasible constraint system | timestamp evidence may never delete a license; infeasibility ⇒ BLIND |
| A3 | hash-chain forgery / re-chaining | false ROBUST (gap hidden, source judged LIVE) | sealer divergence; source-class weighting; post-compromise blackout | chain continuity is never sufficient for LIVE; unsealed ⇒ `unsealed` flag |
| A4 | ER poisoning by chosen identifiers | fabricated or severed chain, either verdict direction | single-source-evidence merges, normalization collisions | ambiguous ER splits into P_min/P_max bracketing; `er_ambiguous` bars ROBUST |
| A5 | grounding blowup (DoS) | truncated P_max sold as an answer, or denial | per-rule expansion ratio, entity admission control, step budgets | cap trip ⇒ verdict `INCOMPLETE`, no cut emitted, exit 3 |
| A6 | blocker-bit authoring (cheap cut) | headline cut of size 1 that enforces nothing | inert/universal atom lints, enforcement-point audit, ablation report | unwaived universal atom ⇒ `catalog_dominant`; inert atom ⇒ build failure |
| A7 | goal gaming | cut tuned to a hand-picked chokepoint | `goal_provenance`, whole-library chokepoint report | `AD_HOC` goals are never ROBUST-eligible; per-goal verdicts only |
| A8 | adaptive re-planning (assumption, not a bug) | the cut is read as a guarantee | adaptivity probe; claims registry | min-cut is a LOWER BOUND; "prevent/stop" banned in every surface |

## 67.3 A1 — Suppression engineered to avoid every obligation axiom

Mechanism. The obligation axioms (`session.used ⇒ session.issued`, `fd.read ⇒ fd.open`, and the
rest of `axioms/`) are the only thing that manufactures a silent instance when a source looks LIVE.
An attacker reading `axioms/` deletes exactly the records that are *leaves* of the obligation
dependency graph — records nothing else obliges — and deletes them inside a busy window so the
observed inter-arrival gap never exceeds the arrival envelope. Nothing is flagged, no license is
issued, `P_max = P_min`, the corridor the deleted records would have opened never exists, and the
kernel emits a small cut with mode ROBUST.

This is the class ECLIPSE §9 admits is "invisible permanently". Part I then contradicts itself by
gating on "zero false ROBUST across the entire degradation matrix".

OVERRIDES Part I: the zero-false-ROBUST invariant is scoped to declared suppression classes, and
the undetectable class is given a name, a measurement and a fail-closed consequence instead of a
footnote.

Required implementation:

1. **Static evasion-depth analysis**, `make evasion-audit`, run at build time over `rules.toml` +
   `axioms/` alone (no telemetry). For each rule τ, compute `d_evade(τ)` = the smallest number of
   record deletions that removes every observed derivation of τ's head while leaving every
   obligation axiom satisfied. Search to a declared depth bound; report `>bound` otherwise.
   Emit `artifacts/evasion.json`. Every τ with `d_evade(τ) < ∞` is written into `LIMITATIONS.md`
   by the docs build. The build fails if `LIMITATIONS.md` is stale relative to `evasion.json`.
2. **Anchor coverage.** Every fact in `invariant_U` and every node of every witness tree is
   `OBSERVED` (cites ≥1 real `EventId`), `LICENSED` (cites a `LicenseId`), or `UNANCHORED`.
   `UNANCHORED` must be unconstructible; if the grounder ever produces one, abort with exit 4.
3. **Volume envelope.** Liveness no longer self-calibrates. Per source `s`, the admissible record
   count and inter-arrival distribution for a window come from `baseline.json`, produced by a
   declared clean calibration run of the *same generator config*, hashed into the certificate as
   an input. A window whose observed count falls below the envelope floor is BLIND regardless of
   chain continuity and regardless of gap size. Deleting records can now only ever *add* licenses.
4. **Obligation-orphan flag.** If any derivation used in the cut proof rests on a source-window
   pair for which no obligation axiom applies and no bracketing corroboration exists, set
   `obligation_orphan`. A run with this flag may not be ROBUST.

Negative requirement: never compute any liveness threshold from the bundle under analysis. A
quantile taken from evidence the attacker authored is not a control on that evidence.

## 67.4 A2 — Backdating to void licenses and shrink P_max

Mechanism. Part I §4A runs Bellman–Ford over a difference-constraint graph and "voids licenses
resting on provably backdated timestamps." Voiding removes silent instances. Removing silent
instances shrinks `P_max`. A smaller `P_max` admits a smaller `S_rob` and flips OPTIMISTIC-ONLY to
ROBUST. Therefore: an attacker who can write timestamps can manufacture a stronger verdict by
making the evidence look tampered. The tamper-detection pass is itself the exploit.

OVERRIDES Part I: license voiding is **deleted**. The timestamp-consistency pass is redefined as a
restriction operator on liveness that can only ever remove LIVE, never remove BLIND.

Formal invariant (property-tested, build-failing):

```
Let L0 = set of (source, interval) judged LIVE by positive evidence only
        (bracketing records + chain/sealer status + baseline volume envelope).
Let L1 = set of (source, interval) LIVE after the time-consistency pass.

INV-T1   L1 ⊆ L0                      (time analysis only takes liveness away)
INV-T2   licenses(L1) ⊇ licenses(L0)  (equivalently: P_max grows monotonically)
INV-T3   for any mutation m that alters ONLY timestamp fields of any records:
             Reach(P_max(m(B))) ⊇ Reach(P_max(B)) is NOT required,
             but  |licenses(m(B))| ≥ |licenses(B)| IS required whenever the
             mutation makes the constraint system less satisfiable.
```

Implementation rules:

- An infeasible constraint system (negative cycle) marks every source participating in the cycle
  BLIND over the disputed span and sets `time_inconsistent`. It never marks anything LIVE and never
  removes a license.
- Certificate field `adversarial.time_pass.licenses_voided` exists and **must be 0**. The Go
  checker rejects any certificate with a nonzero value, reason code `E_TIME_VOID`. The field is
  retained precisely so the removed behavior stays refuted rather than forgotten.
- Unresolvable or unorderable timestamps (missing, out-of-range, duplicated sequence positions)
  yield BLIND, never a guess and never a void.
- Fixture `A2/backdate_to_robust`: a bundle whose only difference from its benign twin is
  backdated timestamps. Requirement: the verdict may not be *stronger* than the twin's.

## 67.5 A3 — Hash-chain forgery

Mechanism. Part I's liveness rests on "no sequence gap in the BLAKE3 chain". The chain is produced
by the source. A `C3_local_chain_holder` deletes records and recomputes the chain from the
deletion point. No gap exists. The source is LIVE. No license. False ROBUST. Separately: real
telemetry sources overwhelmingly do not have tamper-evident chains, so results obtained on chained
sources do not transfer, and presenting them as suppression-detection results is padding.

OVERRIDES Part I: chain continuity is demoted from a liveness criterion to one evidence input
whose weight depends on a declared source class. Chain continuity alone can never establish LIVE.

`sources.toml` (new, hashed into the certificate):

```toml
[[source]]
id            = "iam_audit"
class         = "CHAINED_SEALED"   # key held by the sealer container only
sealer        = "spectra-sealer"
bracketing    = true

[[source]]
id            = "app_access"
class         = "CHAINED_LOCAL"    # key co-resident with the source: C3-reachable
sealer        = false
bracketing    = true

[[source]]
id            = "proxy_flow"
class         = "UNCHAINED"        # models the common real-world case
sealer        = false
bracketing    = false
```

Liveness admissibility by class:

| class | chain gap absent | sealer digest matches | volume envelope met | cross-source corroboration | LIVE? |
|---|---|---|---|---|---|
| `CHAINED_SEALED` | required | required | required | not required | yes |
| `CHAINED_LOCAL` | contributes nothing | n/a | required | required (≥1 source of a different class) | yes |
| `UNCHAINED` | n/a | n/a | required | required (≥1 source of a different class) | yes |

Additional fail-closed rules:

- **Post-compromise blackout.** If the scenario's ground truth (§62) places a host in the
  compromised set at time `t`, every `CHAINED_LOCAL` and `UNCHAINED` source resident on that host
  is BLIND for all `t' ≥ t`. No exceptions, no reinstatement by later clean-looking records.
- **Sealer divergence.** A mismatch between a source-local chain head and the sealer's digest is
  `SUPPRESSED` with flag `chain_divergence` — it localizes deletion and *adds* licenses.
- **Unsealed honesty.** A bundle with no sealer digests carries `unsealed`. Any document reporting
  suppression-detection results must split them by source class; a claim stated over all classes
  without the split fails the claims-registry lint.
- At least one scenario family in the held-out set must consist entirely of `UNCHAINED` sources.

## 67.6 A4 — Entity-resolution poisoning by attacker-chosen identifiers

Mechanism. `C4_namer` picks identifiers that collide under the ER normalization function: a user
named to normalize onto a service account, a hostname differing by a trailing dot or a homoglyph,
a session token sharing a prefix used as a join key, a UA string crafted to match a device
heuristic. A false merge fabricates an edge and can *either* invent a corridor (false UNSAFE,
inflated blindness premium) *or* absorb a real actor into a benign one so the corridor vanishes
(false ROBUST). ER sits upstream of everything the kernel proves, so every soundness statement
inherits its errors silently.

Required implementation:

1. **ER is adversarial input.** `er.toml` declares, per identifier namespace,
   `attacker_writable = true|false`. Any merge whose supporting evidence consists solely of
   attacker-writable fields is `WEAK`.
2. **Two-source rule.** A `STRONG` merge requires either an authoritative binding record from a
   non-attacker-writable namespace, or co-observation by two sources of different declared classes
   (67.5) within the same window.
3. **Ambiguity is bracketed, never guessed.** OVERRIDES Part I: a `WEAK` merge is not resolved.
   It is materialized as two grounding candidates, and the existing two-sided sandwich carries it:

```
   P_min  grounds over  ER_meet   = merges that are STRONG                 (conservative-low)
   P_max  grounds over  ER_join   = STRONG ∪ WEAK, both readings admitted  (conservative-high)
   Invariant: Reach(P_min) ⊆ Reach(P_max) must still hold; property-tested.
```

4. **Normalization is total and byte-level.** One documented function; NFKC then case-fold then
   namespace-specific canonicalization, in that order, with the exact steps enumerated in code and
   mirrored in the Go checker. Two distinct raw identifiers from different sources that normalize
   to the same key do not merge: they emit an `er_collision` quarantine record with a reason code,
   and the window is `er_ambiguous`.
5. **Flags.** `er_ambiguous` bars ROBUST. `er_poisoning_suspected` is set when any merge used only
   attacker-writable evidence *and* that merge is load-bearing for the cut (removing it changes
   `S`). Both appear in the certificate and in the UI banner, not only in JSON.
6. **Injection experiment.** `make er-injection` deliberately introduces false merges and false
   splits at declared rates and publishes the verdict-flip rate per rate. Published per scenario,
   separately for held-out scenarios.

Negative requirement: never merge on string equality of a single attacker-writable field, however
distinctive it looks. Token prefixes, UUID-shaped strings and hostnames are all attacker-writable.

## 67.7 A5 — Grounding blowup as denial of service

Mechanism. `C5_flooder` emits records with high distinct-entity cardinality and dense timestamps.
Grounding expands combinatorially, a cap trips, and one of two bad things happens: the run is
denied (availability), or — much worse — the cap trips during silent-instance instantiation, so
`P_max` is truncated, the corridor set is incomplete, and a *smaller* cut is reported. A truncated
`P_max` presented with a `grounding_capped` flag still gets read as an answer.

OVERRIDES Part I: a capped run does not produce a downgraded verdict. It produces no verdict.

```rust
/// OVERRIDES Part I §5: `mode: ROBUST|OPTIMISTIC|UNSAFE` is replaced.
pub enum Safety { Robust, OptimisticOnly, Unsafe, Incomplete }

pub enum Minimality { Exact, Subset, Unverified }
```

- `Safety::Incomplete` carries `reason: CapKind` and **no cut, no Psi, no redundancy index, no
  frontier**. The emitter refuses to populate those fields; the Go checker rejects a certificate
  that has both `Incomplete` and a non-empty `cut` (reason code `E_INCOMPLETE_CUT`). CLI exit 3.
- All budgets are deterministic step/instruction counts, never wall-clock. A wall-clock bound in
  any decision path is a build failure (lint `no-clock-in-decision-path`). Two machines must agree
  on whether a cap tripped.
- **Admission control before grounding.** Per-scenario declared ceilings on distinct entities per
  dimension, records per source, and distinct ticks. Excess is *quarantined with a reason code*,
  never silently truncated — silent drops manufacture blind windows and therefore licenses, which
  converts a DoS into a license-injection attack (see A1 inverted).
- **Per-rule expansion ratio.** `rules.toml` declares `max_expansion` per rule (instances per
  observed event). `make expansion-audit` runs every fixture and fails the build if any rule
  exceeds its declared bound; the measured ratios are published, never asserted.
- Silent-instance instantiation is budgeted *first*: if the combined budget cannot cover both
  observed expansion and the full licensed silent envelope, the run is `Incomplete`. Never spend
  the budget on observed instances and then run out before the envelope.

## 67.8 A6 — Control-catalog gaming

Mechanism. Cut size is a direct function of which rules carry which blocker bits — an authoring
choice with no gate in Part I. Two dishonest authorings:

- **Universal atom.** Attach one control's bit to every rule instance in every corridor. Every
  minimum cut is `{that control}`. The headline becomes "one control severs this chain."
- **Inert atom.** Add controls that block nothing, to inflate "N controls modeled" in the README.

Both are invisible to every Part I gate and both survive the Go checker, because the checker
validates the model against itself.

Required gates:

1. **Enforcement-point audit**, `make blocker-enforcement-audit`. For every asserted blocking
   triple `(rule τ, control k, level ℓ)` there must exist an independently authored simulator test
   (§62's re-execution oracle) showing the concrete action fails at level `ℓ` and succeeds at
   `ℓ-1`. A blocker bit with no enforcement point is deleted, not documented. Build fails on any
   unmatched triple.
2. **Inert-atom lint.** Every atom `x_{k,ℓ}` must change the outcome of at least one checked-in
   fixture (cut membership, corridor set, or reachability). An atom that changes nothing fails the
   build; it may not be counted in any "controls modeled" figure.
3. **Dominance lint.** An atom that single-handedly severs every corridor in every fixture is
   `universal`. Universal atoms require an entry in `docs/catalog-dominance.md` naming the
   enforcement points that justify the breadth. A cut containing an unwaived universal atom sets
   `catalog_dominant`, which bars ROBUST.
4. **Blocker provenance lint.** Every blocker assignment carries a non-empty justification citing
   a public technique description (e.g. an ATT&CK technique id) and the simulator enforcement
   point. Placeholder strings (`TODO`, `n/a`, empty, the rule id repeated) fail the lint.
5. **Ablation report.** `make catalog-sensitivity` publishes `|S_opt|`, `|S_rob|` and the blindness
   premium under one-at-a-time ablation of each control's blocker set, each obligation axiom, and
   each `silent_possible` flag. The report is an artifact; the numbers are measured, never quoted
   in the prompt or in docs without a result id.
6. **Bit-position stability.** Atom-to-bit assignment is derived deterministically from a total
   order over `(control_id, level)` and recorded in the certificate. A catalog edit that reorders
   existing bits fails the lint; new atoms append. Certificates stay comparable across edits.

Contributor rule (`C6_catalog_author`): a pull request touching `controls.toml`, blocker masks,
`axioms/` or `goals/` must include the red-team fixture that would catch the corresponding
dishonest authoring. Reviewed as a security change, not as content.

## 67.9 A7 — Goal gaming

Mechanism. The scenario author also writes `goal.toml`. Choosing an objective atom that sits
behind a narrow chokepoint yields a cut of size 1. Choosing a late-stage objective makes most of
the attack irrelevant to the proof. Neither is detectable from the certificate as Part I defines it.

OVERRIDES Part I: `goal.toml` no longer carries a hand-written objective atom per run.

```toml
# goals/library.toml  — frozen, hash-pinned, edits require a leakage-ledger entry
[[goal]]
id        = "G_DATA_EXFIL"
atoms     = ["exfil.bytes_out(actor, external_dst)"]   # disjunction allowed, multi-atom
derivable_from_ground_truth = true

[[goal]]
id        = "G_PERSIST_IDP"
atoms     = ["idp.persistent_credential(actor)", "idp.federation_trust_added(actor)"]
derivable_from_ground_truth = true
```

Rules:

- `goal_provenance ∈ { DERIVED, LIBRARY, AD_HOC }` is a mandatory certificate field.
  - `DERIVED`: the goal set is computed from the generator's ground truth via the correspondence
    relation of §62 — the objectives the scenario script actually achieved. Required for every
    headline number and for the demo fixture.
  - `LIBRARY`: a frozen library goal not achieved in this scenario; permitted, clearly labeled.
  - `AD_HOC`: hand-authored for this run. **Never ROBUST-eligible.** Watermarked in UI and in
    every export. The Go checker refuses `Safety::Robust` with `goal_provenance = AD_HOC`
    (reason code `E_ADHOC_GOAL`).
- **Multi-goal semantics.** Per-goal verdicts only. There is no aggregate verdict and no score.
  A scenario-level ROBUST requires every goal atom in the derived goal set to be unreachable
  under `S`. Disjunctive goals are cut as a disjunction; reporting the cut for the cheapest
  disjunct is forbidden and is caught by a lint on the frontier exporter.
- **Chokepoint report.** Every run publishes `|S_opt|` and `|S_rob|` for *every* goal in the
  frozen library against this bundle, in `artifacts/goal-chokepoints.json`. Cherry-picking is then
  visible in the same artifact that would have hidden it.

## 67.10 A8 — The non-adaptive attacker assumption

This is not a defect to be fixed. It is the load-bearing limit of the entire result, and Part I
carries it as one clause. State it structurally.

```
Let  H      = the grounded hypergraph over observed ∪ licensed instances.
Let  Corr(H)= the corridors enumerated from H (possibly incomplete; see Psi caps).
Let  A*     = the set of corridors a real adversary could use against the real system.

The kernel computes  S  minimizing |S| s.t. S hits every corridor in Corr(H).

Facts:
  (1) Corr(H) ⊆ A*  is the ONLY relationship SPECTRA can argue, and even that only
      under the rule table, the catalog, the ER output and the ingested telemetry.
  (2) Therefore  mincut(Corr(H))  ≤  mincut(A*).
  (3) Therefore |S| is a LOWER BOUND on the control effort required. It is never an
      upper bound, never sufficiency, and never a guarantee.
  (4) The modeled attacker DOES NOT RE-PLAN. S is computed against a recorded,
      fixed hypothesis set. A real adversary observes the deployed controls and
      selects a path S does not cover. Deploying S is therefore consistent with the
      attacker still reaching the goal.
```

Required consequences:

- **Verdict strings are unconstructible without scope.** Render as
  `ROBUST(rules@<hash>, catalog@<hash>, licenses@<hash>, goals@<hash>, non-adaptive)`.
  No code path formats a verdict by string concatenation; there is one constructor and one
  formatter, and a unit test asserts no other path produces a verdict string. The Go checker
  rejects a certificate whose mode string lacks its scope binding (`E_UNSCOPED_VERDICT`).
- **Banned vocabulary**, enforced by the claims-registry lint across README, docs, UI strings, API
  field names, demo script and commit-message templates: "prevents", "would have stopped", "stops
  the attack", "guaranteed", "formally verified", "proves the system is secure". The permitted
  phrasing is "severs every recorded corridor in the model" and "lower bound on control effort".
- **Adaptivity probe** (required for the demo fixture and for every held-out scenario family). Run
  the generator a second time with the cut `S` enforced *and* the scenario script permitted to take
  its declared alternate branch. If the alternate branch reaches a goal atom, the certificate
  carries `adaptive_bypass_known: true` and the UI shows it next to the verdict, not in a tooltip.
  A demo fixture with a known adaptive bypass must say so on screen.
- `LIMITATIONS.md` opens with (3) and (4), verbatim, above the fold, linked from the README's
  first screen.

## 67.11 Fail-closed algebra

Make dishonest states unconstructible in the type system, in both the Rust emitter and the Go
checker.

```rust
bitflags! {
    /// Any flag set ⇒ Safety::Robust is unconstructible.
    pub struct SoundnessFlags: u32 {
        const GROUNDING_CAPPED       = 1 << 0;  // ⇒ Safety::Incomplete, not a downgrade
        const OBLIGATION_ORPHAN      = 1 << 1;  // A1
        const TIME_INCONSISTENT      = 1 << 2;  // A2
        const CHAIN_DIVERGENCE       = 1 << 3;  // A3
        const UNSEALED               = 1 << 4;  // A3
        const ER_AMBIGUOUS           = 1 << 5;  // A4
        const ER_POISONING_SUSPECTED = 1 << 6;  // A4
        const CATALOG_DOMINANT       = 1 << 7;  // A6
        const ADHOC_GOAL             = 1 << 8;  // A7
        const BASELINE_MISSING       = 1 << 9;  // A1/A3: no calibration input
        const QUARANTINE_NONEMPTY    = 1 << 10; // A5: records refused at ingest
    }
}

pub struct Verdict { safety: Safety, minimality: Minimality, flags: SoundnessFlags, scope: ScopeHashes }

impl Verdict {
    /// The ONLY constructor. There is no `Verdict { .. }` literal outside this module.
    pub fn new(s: Safety, m: Minimality, f: SoundnessFlags, sc: ScopeHashes) -> Verdict {
        let safety = match (s, f.is_empty()) {
            (Safety::Robust, false) => Safety::OptimisticOnly,   // fail closed, never up
            (s, _) => s,
        };
        Verdict { safety, minimality: m, flags: f, scope: sc }
    }
}
```

- OVERRIDES Part I: safety and minimality are **independent** fields. `subset_minimal_only` (a
  statement about cut size) no longer suppresses a safety result. A fully verified unreachability
  result with `Minimality::Subset` is still `Safety::Robust`. This removes Part I's standing
  incentive to keep the control catalog artificially small.
- The Go checker recomputes the algebra from the flags it independently derives and rejects any
  certificate where the emitted safety is stronger than the recomputed one
  (reason code `E_ALGEBRA`). It never accepts the emitter's word for a flag.
- `make no-score-lint`: no field, column, API key or UI string anywhere in the repo may be named
  or typed as a probability, confidence, score, severity, risk or likelihood. Schema-level lint.

## 67.12 Red-team fixture corpus and the build gate

Checked in under `fixtures/redteam/`. This corpus is the acceptance evidence for 67.3–67.9.

```
fixtures/redteam/
  A1_obligation_evading_delete/
    attack.toml            # manifest (below)
    bundle.jsonl           # adversarial bundle
    baseline.json          # calibration input for the same generator config
    expected.json          # required verdict, required flags, required reason codes
    benign_twin/           # SAME scenario, adversarial transform removed
      bundle.jsonl
      expected.json        # MUST be ROBUST — this is the anti-vacuity half
  A1_busy_window_hide/  A2_backdate_to_robust/  A2_negative_cycle/
  A3_rechained_delete/  A3_unsealed_only/       A3_post_compromise_reuse/
  A4_homoglyph_merge/   A4_token_prefix_join/   A4_service_account_shadow/
  A5_entity_flood/      A5_tick_density_bomb/   A5_silent_envelope_starve/
  A6_universal_atom/    A6_inert_atom/          A6_unenforced_blocker/
  A7_adhoc_chokepoint/  A7_disjunct_cherrypick/
  A8_adaptive_branch/
```

```toml
# fixtures/redteam/A2_backdate_to_robust/attack.toml
id              = "A2_backdate_to_robust"
attack          = "A2"
capability      = ["C2_local_deleter", "C3_local_chain_holder"]
summary         = "Backdate 3 records so the difference-constraint system is infeasible, hoping the kernel voids the licenses that make the corridor visible."
transform       = { op = "shift_timestamp", records = ["ev:0x41f2", "ev:0x41f5", "ev:0x4200"], delta_ms = -900000 }
benign_twin     = "benign_twin/"
must_not_yield  = "ROBUST"
must_set_flags  = ["TIME_INCONSISTENT"]
must_not_set    = ["GROUNDING_CAPPED"]          # fixture must fail for the RIGHT reason
must_exit_code  = 0
defense_mutation = "kernel/src/liveness/time.rs::restriction_only"   # see 67.13
```

Gate semantics — `make redteam-gate`, blocking on every push:

1. For every fixture: the kernel runs to completion and the verdict is **not** ROBUST.
2. The declared `must_set_flags` are present and the declared `must_not_set` flags are absent. A
   fixture that fails by crashing, by tripping an unrelated cap, or by a generic refusal is a
   **gate failure**, not a pass. Failing for the wrong reason is failing.
3. For every fixture: the benign twin **does** yield its declared benign verdict, normally ROBUST.
   This is non-negotiable. Without it, `fn verdict() -> UNSAFE` passes the entire corpus.
4. The Go checker independently accepts the benign twin's certificate and independently derives the
   same flag set for the adversarial bundle.
5. Every attack id A1–A8 has ≥1 fixture, and every fixture is referenced by id in `LIMITATIONS.md`.
   A new attack id with no fixture fails the build.

```
$ make redteam-gate
spectra-redteam 0.1.0  (rules@b3:9c1e… catalog@b3:40aa… goals@b3:7d52…)

id                          verdict          flags                     twin     result
A1_obligation_evading_delete OPTIMISTIC_ONLY OBLIGATION_ORPHAN         ROBUST   PASS
A1_busy_window_hide          OPTIMISTIC_ONLY OBLIGATION_ORPHAN         ROBUST   PASS
A2_backdate_to_robust        OPTIMISTIC_ONLY TIME_INCONSISTENT         ROBUST   PASS
A3_rechained_delete          OPTIMISTIC_ONLY CHAIN_DIVERGENCE          ROBUST   PASS
A3_unsealed_only             OPTIMISTIC_ONLY UNSEALED                  ROBUST   PASS
A4_homoglyph_merge           OPTIMISTIC_ONLY ER_AMBIGUOUS|ER_POISON…   ROBUST   PASS
A5_entity_flood              INCOMPLETE      GROUNDING_CAPPED          ROBUST   PASS
A6_universal_atom            OPTIMISTIC_ONLY CATALOG_DOMINANT          ROBUST   PASS
A7_adhoc_chokepoint          OPTIMISTIC_ONLY ADHOC_GOAL                ROBUST   PASS
A8_adaptive_branch           ROBUST(+bypass) adaptive_bypass_known     ROBUST   PASS

18 fixtures, 18 benign twins, 0 ROBUST on adversarial bundles, 0 wrong-reason passes.
checker: 36/36 certificates independently re-derived.
```

(The transcript above is an illustrative shape, not a target — the committed expected output is
regenerated by CI from actual execution.)

Note on A8: the adaptive fixture is the one case where the adversarial bundle *may* be ROBUST,
because adaptivity is outside the modeled quantifier. Its requirement is instead that
`adaptive_bypass_known` is set and surfaced. Encode that in `expected.json`; do not special-case it
in the gate's code.

## 67.13 Gate-liveness mutation testing

A green gate is evidence only if it can go red. `make redteam-mutation` (nightly) applies each
fixture's declared `defense_mutation` — a named, checked-in patch that disables exactly the defense
the fixture targets — and asserts the fixture flips to ROBUST or loses its required flag. A
mutation that leaves the gate green means the defense is not load-bearing and the fixture is
decoration; the build fails with `E_DEAD_DEFENSE`, naming both.

Mandatory mutations, one per defense: baseline-envelope bypass (A1), time-pass voiding restored
(A2), chain-continuity-implies-LIVE restored (A3), weak-merge auto-resolution (A4), silent-envelope
budgeted last (A5), dominance lint disabled (A6), `AD_HOC` goals ROBUST-eligible (A7). Each
mutation is a patch file under `fixtures/redteam/mutations/`, applied by the harness, never merged.

## 67.14 Negative requirements and forbidden claims

The build fails, or the checker rejects, on each of the following:

1. Any code path where *more* attacker-supplied evidence yields a *smaller* cut or a *stronger*
   safety value, other than through the declared LIVE-establishing evidence of 67.5. Property-tested
   by monotonicity fixtures across the degradation matrix.
2. Any liveness threshold computed from the bundle under analysis.
3. Any mechanism that removes a license. Licenses are append-only within a run.
4. Chain continuity used as a sufficient condition for LIVE.
5. Resolving an ambiguous entity merge by heuristic, tie-break, most-recent-wins, or confidence.
6. Emitting a cut, `Psi`, a redundancy index or a frontier alongside `Safety::Incomplete`.
7. Wall-clock in any decision path, including cap and solver budgets.
8. A blocker bit with no simulator enforcement point.
9. A hand-authored goal reaching any headline number, table, figure or demo.
10. Silent drop of a malformed or excess record. Quarantine with a reason code, always.
11. A verdict string produced by concatenation, or a verdict rendered without its scope hashes.
12. Any numeric confidence, probability, severity, risk or score, anywhere, in any layer.

Forbidden claims, in the repository and in any paper drawn from it:

- "SPECTRA detects log tampering." It detects declared tampering classes on declared source
  classes, and publishes the classes it cannot detect.
- "The minimum cut would have prevented this attack." The cut severs every recorded corridor in
  the model; the attacker is non-adaptive; the cut is a lower bound (67.10).
- "The proof kernel is resistant to adversarial telemetry." It fails closed on the enumerated
  strategies A1–A7 and has an unbounded residual against strategies not enumerated.
- "Zero false ROBUST." Only ever: "zero false ROBUST on suppression classes S1..Sn, enumerated in
  `LIMITATIONS.md`, at the measured frequencies published in the degradation-matrix artifact."
- Any statement that the red-team corpus is complete. It is a floor. State in
  `docs/redteam-scope.md` what a passing corpus does **not** establish: an attack strategy nobody
  wrote a fixture for, an error shared between the rule table and the simulator, an omission in the
  control catalog, and any behavior of a real adversary who read this section first.
