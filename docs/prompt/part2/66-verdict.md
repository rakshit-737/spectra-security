============================================================
66. VERDICT AND FLAG ALGEBRA
============================================================

## 66.0 Purpose and standing

A verdict is the only artifact of SPECTRA that a human will remember. Part I protected verdict
honesty with prose ("a flagged run may never be presented as ROBUST"). Prose is not an enforcement
mechanism. This section replaces that prose with a type.

The governing principle: **a dishonest verdict state must be unconstructible, not forbidden.** If a
combination of (safety claim, minimality claim, flags, scope binding) is not defensible, no function
in any of the four implementation languages may return a value in that combination, and the Go
checker must reject any certificate that encodes it.

OVERRIDES Part I: the certificate field `mode: ROBUST|OPTIMISTIC` (ECLIPSE §5) is deleted. It is
replaced by a structured `verdict` object specified in 66.2. Any code, schema, fixture or document
still referencing `cert.mode` fails `make lint-verdict`.

OVERRIDES Part I: the flag `subset_minimal_only` (ECLIPSE §5) is deleted. It conflated a claim about
cut size with a claim about reachability, so that an honest, fully verified safety result was
suppressed for an unrelated reason and the author was given a standing incentive to keep the control
catalog artificially small. Minimality is now an independent field (66.2.2) and the atom-budget
condition is carried by the flag `atoms_over_budget` (66.3), which does **not** block ROBUST.

OVERRIDES Part I: the verdict alphabet {ROBUST, OPTIMISTIC-ONLY, UNSAFE} is extended with
INDETERMINATE (66.2.1). A run that cannot defend any of the other three must be able to say so
instead of degrading to UNSAFE, because a false UNSAFE inflates the blindness premium — the very
headline finding — and Part I measured false UNSAFE nowhere.

OVERRIDES Part I / ECLIPSE §8: the demo header string "Minimum cut {...} — ROBUST" is forbidden.
Every rendering of a verdict anywhere carries its scope clause (66.5).

---

## 66.1 The three independent axes

A verdict is a product of three axes that Part I conflated. They are independent: no value on one
axis implies any value on another.

```
            SAFETY                MINIMALITY              SCOPE
      (is the goal derivable    (what is claimed about   (relative to WHAT
       under this cut?)          |S| and subsets of S?)   is any of this true?)

      ROBUST                    EXACT_EXHAUSTIVE         rules@hash
      OPTIMISTIC_ONLY           EXACT_PSI_RELATIVE       controls@hash
      UNSAFE                    SUBSET                   liveness@hash
      INDETERMINATE             UNVERIFIED               er@hash
                                                         goal@hash
                                                         bundle@hash
                                                         attacker=non-adaptive
                    ^                    ^                        ^
                    |                    |                        |
                    +--------- all three are MANDATORY -----------+
                              on every rendering, every export,
                              every API response, every UI node.
```

OVERRIDES Part I sections 40.4, 40.8 and 42.4: the verdict vocabulary "ROBUST / OPTIMISTIC-ONLY /
UNSAFE / FLAGGED", the FLAGGED palette row with its cross-hatch overlay and flag icon, and the rule
that any non-exact value renders with the FLAGGED treatment are replaced by the three independent
axes above; the safety alphabet is exactly {ROBUST, OPTIMISTIC_ONLY, UNSAFE, INDETERMINATE} and
flags are a separate u16 that is never a verdict value. An implementer who keeps FLAGGED keeps a
palette entry and a vocabulary term the Part II type cannot produce, and paints `greedy_cover` and
`sampled_matrix` runs as "flagged — not a ROBUST result", which is a false statement about a
legitimately constructible ROBUST verdict.

Rationale, stated once so no implementer re-litigates it: `EXACT_*` is a statement about the search
over cut cardinalities. `ROBUST` is a statement about a fixpoint over the licensed program. A cut can
be exactly minimal and unsafe; a cut can be robust and of unknown minimality. Cross-contamination
between the axes was a Part I contradiction and is now a type error.

---

## 66.2 The verdict type

### 66.2.1 Safety

| Value | Meaning | Constructible only when |
|---|---|---|
| `ROBUST` | The goal atom is not in the least fixpoint of **P_max** under cut S. | No soundness-class flag is set (66.4), and the P_max fixpoint terminated without hitting any deterministic budget. |
| `OPTIMISTIC_ONLY` | The goal is not derivable in **P_min** but is derivable in **P_max**. | Always, provided the P_min fixpoint terminated. |
| `UNSAFE` | The goal is derivable in **P_min**, with a witness derivation tree. | A witness tree is present and every leaf is a real `EventId` present in the hashed bundle. |
| `INDETERMINATE` | Neither a safety claim nor a witness can be defended under this run's flags. | Whenever the other three are not constructible. This is the fail-closed sink. |

OVERRIDES Part I section 25.9: the automatic downgrade, under which a run carrying a flag is
relabelled `mode: "OPTIMISTIC_ONLY"` with a `downgraded_by` list regardless of the fixpoint results,
is replaced by the constructibility conditions in this table — `OPTIMISTIC_ONLY` requires that the
goal is not derivable in P_min and is derivable in P_max, and a flagged run that cannot defend that
claim falls to `INDETERMINATE` (66.4 A10). An implementer following section 25.9 emits
OPTIMISTIC_ONLY for a run whose goal is unreachable in P_max, which is a factually false safety
claim under this section's own definition, and attaches a `downgraded_by` field that does not exist
in the canonical object of 66.2.3.

`UNSAFE` carries a mandatory `witness_class`:

| `witness_class` | Meaning |
|---|---|
| `OBSERVED` | Every AND-node in the witness tree is an observed rule instance. No GHOST. |
| `LICENSED` | At least one AND-node is a licensed silent instance. The witness depicts a hypothesis, not an observation, and §65's realizability check passed on it. |
| `CONTESTED` | The witness depends on at least one entity-resolution decision below the declared decision margin. Forced by `er_ambiguous`. |

Forbidden: emitting `UNSAFE` with `witness_class: LICENSED` and no GHOST markers on the affected
nodes. Forbidden: any rendering that collapses `OBSERVED` and `LICENSED` into one word.

### 66.2.2 Minimality

| Value | Meaning | Constructible only when |
|---|---|---|
| `EXACT_EXHAUSTIVE` | Every cut of cardinality < \|S\| was fixpoint-tested and every one failed. | The exhaustive enumeration completed within its deterministic step budget. |
| `EXACT_PSI_RELATIVE` | No cut of cardinality < \|S\| satisfies Ψ, and Ψ reached fixpoint. | `corridor_cap` is clear. |
| `SUBSET` | No proper subset of S severs the chain. Nothing is claimed about cardinality. | Always, once the subset probes ran. |
| `UNVERIFIED` | No minimality claim. | Always. |

Forbidden strings: "no smaller cut exists", "minimum cut", "cardinality-minimal" on any certificate
whose minimality is not `EXACT_EXHAUSTIVE`. `make lint-claims` (§72) greps for them and fails.
`EXACT_PSI_RELATIVE` renders as "no smaller cut satisfies the enumerated corridor set", never as
"minimum".

### 66.2.3 Canonical JSON

```json
{
  "$schema": "spectra/verdict/v1",
  "verdict": {
    "safety": "OPTIMISTIC_ONLY",
    "witness_class": null,
    "minimality": "EXACT_PSI_RELATIVE",
    "flags": ["greedy_cover"],
    "scope": {
      "rules":    "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "controls": "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "liveness": "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "er":       "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "goal":     "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "bundle":   "b3:0000000000000000000000000000000000000000000000000000000000000000",
      "attacker": "non-adaptive"
    },
    "derived_suppressed": ["redundancy_index"]
  }
}
```

OVERRIDES Part I sections 25.7 and 38.2: the five-hash scope `{rules, bundle, controls, liveness,
goal}` with no entity-resolution hash and no attacker field is replaced by a six-hash scope that
adds `er` and by the mandatory literal `attacker: "non-adaptive"`; the `proof_cert` DDL needs an
`er_hash` column and the content-key unique index must include it, and the checker invocation takes
`--er` (66.8). An implementer building the section 25.7 certificate emits a scope the Go checker
rejects with `VRD-005`, and a content key over the five old hashes collides for two runs that differ
only in entity resolution.

Canonicalization rules (binding on emitter and checker alike):
1. `flags` is a JSON array of flag names sorted by **bit position** (66.3), never alphabetically,
   never a bitmask in the wire format. The checker recomputes the mask and rejects duplicates.

   OVERRIDES Part I sections 25.7, 36.4 and 38.2: the wire representation of flags as a three-key
   object of booleans `{grounding_capped, subset_minimal_only, greedy_cover}`, and its storage as
   the three boolean columns `flag_capped, flag_subset_only, flag_greedy`, are replaced by a
   bit-ordered array of flag names drawn from the closed nine-flag set of 66.3. An implementer
   emitting the Part I flags object, or serializing those three columns, produces a certificate the
   checker cannot parse or rejects with `VRD-008` for out-of-bit-order names, and has no storage at
   all for six of the nine flags.
2. `witness_class` is `null` unless `safety == "UNSAFE"`. Present-and-null, never absent.
3. Hashes are lowercase hex, exactly 64 nybbles, prefixed `b3:`. No truncation on the wire.
   Truncation to 8 nybbles happens only in the short rendering (66.5.2).
4. `attacker` is the literal `"non-adaptive"`. No other value is accepted by the checker in v1.
5. No float, no integer score, no timestamp, no host identifier anywhere in this object.

---

## 66.3 The closed flag set

The flag set is **closed**. Exactly nine flags exist, at fixed bit positions. Bits 9..15 of the u16
mask are reserved and MUST be zero; a certificate with a nonzero reserved bit is rejected with
`VRD-009`. Fixed positions exist so that certificates remain comparable across catalog edits.
Adding a flag is a schema-version bump (`spectra/verdict/v2`), never an in-place edit.

| bit | flag | set when | class | effect |
|---|---|---|---|---|
| 0 | `grounding_capped` | A grounding hard cap (fact count, instance count, or horizon expansion) was reached, so the derived fact set is an under-approximation. | **S** | Blocks ROBUST. |
| 1 | `corridor_cap` | The hitting-set loop terminated on its deterministic corridor budget before Ψ reached fixpoint. | **S + M + D** | Blocks ROBUST; caps minimality at `SUBSET`; suppresses the redundancy index. |
| 2 | `atoms_over_budget` | Σ m_k > 64, so exact cardinality search over u64 masks is unavailable. | **M** | Caps minimality at `SUBSET`. Does **not** block ROBUST. |
| 3 | `er_ambiguous` | At least one entity-resolution merge or split fell below the declared decision margin, or measured ER error exceeded the declared threshold. | **S** | Blocks ROBUST; forces `witness_class: CONTESTED` on any UNSAFE. |
| 4 | `quarantined_records` | At least one input record was quarantined by the ingest hardening pass. Dropped records lengthen observed gaps and therefore manufacture blind windows and licenses. | **S** | Blocks ROBUST. |
| 5 | `license_voided_by_suspected_tampering` | The difference-constraint pass voided at least one license on suspected backdating. Voiding shrinks P_max and can only push a verdict toward ROBUST, so an attacker who controls timestamps could otherwise manufacture one. | **S** | Blocks ROBUST. Fail-closed by construction. |
| 6 | `greedy_cover` | The decisive observation set used the greedy cover beyond the exact search bound. | **D** | Does not block ROBUST. Forces the approximation factor to render inline with the set, never in a tooltip. |
| 7 | `sampled_matrix` | The degradation matrix cells backing this run's aggregate context were sampled, not executed exhaustively. | **R** | Does not block a per-run ROBUST. Blocks every aggregate claim built from the run; any docs table derived from it must carry the sampling clause. |
| 8 | `profile_missing` | The hashed clean-baseline arrival profile was absent for at least one source. Without it the liveness threshold would have to be self-calibrated from the run's own (possibly deleted) data — the known false-ROBUST path. Sources with no profile are forced BLIND. | **S** | Blocks ROBUST. |

OVERRIDES Part I sections 25.6 A, 25.8 and 38.2 (bit 5): the treatment of a license voided by the
difference-constraint pass as routine hygiene, recorded as `voided_by_dcg` in `liveness.json` and in
the `license.voided` column with no verdict consequence, is replaced by
`license_voided_by_suspected_tampering`, a soundness-class flag that makes ROBUST unconstructible.
An implementer following Part I emits ROBUST on a run with voided licenses, which the Go checker
rejects with `VRD-001`, and the Part I liveness output exposes no field the verdict builder can read
to set bit 5.

OVERRIDES Part I sections 25.9, 36.5, 37.3, 38.2 and 40.4 (bits 6 and 7): the rule that a run with
ANY flag set must never be presented as ROBUST — enforced by the serializer guard, the
`robust_never_flagged` CHECK constraint, the exit-8 gate and the chip rule — is replaced by the
class system in this table, under which only **S**-class flags block ROBUST, so `greedy_cover` and
`sampled_matrix` are compatible with a constructible ROBUST verdict. An implementer who writes the
Part I constraint, serializer guard or visual-regression test makes those two combinations
unstorable, unserializable and unpaintable, and fails the exhaustive flag sweep of 66.9, which
requires exactly the subsets disjoint from `SOUNDNESS_MASK` to accept.

OVERRIDES Part I sections 25.6 A and 38 query Q4 (bit 8): the liveness inter-arrival threshold
computed as `q99(s)` from the run's own data — mandated there as "never a constant, never a tuned
hyperparameter" — is replaced by a hashed clean-baseline arrival profile per source, because
self-calibration is the known false-ROBUST path; sources with no profile are forced BLIND and
`profile_missing` blocks ROBUST. An implementer who builds liveness to section 25.6 A produces no
profile artifact at all, so bit 8 is set on every run and no run in the system can ever reach a
constructible ROBUST verdict; the profile is also a hashed input that appears in neither section
25.3's input table nor the scope of 66.2.3.

Classes: **S** soundness-affecting, **M** minimality-affecting, **D** derived-output-suppressing,
**R** reporting-affecting. A flag may carry several classes.

`SOUNDNESS_MASK = bits {0,1,3,4,5,8} = 0x013B`. This constant is defined once, in
`spec/verdict/flags.toml`, and generated into all four languages. Hand-written copies are a lint
failure (`VRD-013`).

```toml
# spec/verdict/flags.toml  -- single source of truth, hashed into the certificate scope
schema = "spectra/verdict/v1"
reserved_bits = [9, 10, 11, 12, 13, 14, 15]

[[flag]] bit = 0  name = "grounding_capped"                      classes = ["S"]
[[flag]] bit = 1  name = "corridor_cap"                          classes = ["S","M","D"]
[[flag]] bit = 2  name = "atoms_over_budget"                     classes = ["M"]
[[flag]] bit = 3  name = "er_ambiguous"                          classes = ["S"]
[[flag]] bit = 4  name = "quarantined_records"                   classes = ["S"]
[[flag]] bit = 5  name = "license_voided_by_suspected_tampering" classes = ["S"]
[[flag]] bit = 6  name = "greedy_cover"                          classes = ["D"]
[[flag]] bit = 7  name = "sampled_matrix"                        classes = ["R"]
[[flag]] bit = 8  name = "profile_missing"                       classes = ["S"]
```

---

## 66.4 The algebra

Let `F` be the flag set of a run, `S_MASK` the soundness mask.

```
A1  safety = ROBUST           requires  F ∩ S_MASK = ∅
A2  safety = UNSAFE           requires  witness tree present, all leaves real EventIds
A3  witness_class = OBSERVED  requires  er_ambiguous ∉ F  and  no GHOST node in the witness
A4  witness_class = CONTESTED required  if er_ambiguous ∈ F
A5  minimality ∈ {EXACT_EXHAUSTIVE, EXACT_PSI_RELATIVE}
                              requires  corridor_cap ∉ F  and  atoms_over_budget ∉ F
A6  minimality = EXACT_PSI_RELATIVE requires Ψ reached fixpoint
A7  derived_suppressed ⊇ {redundancy_index}        if corridor_cap ∈ F or grounding_capped ∈ F
A8  derived_suppressed ⊇ {pareto_frontier}         if no costs.toml was supplied
A9  scope is total: all six hashes present, non-empty, well-formed; attacker = "non-adaptive"
A10 if A1 fails and OPTIMISTIC_ONLY / UNSAFE are also not constructible, safety = INDETERMINATE
```

OVERRIDES Part I sections 25.6 F, 25.11 and 36.3 (A7): the unconditional redundancy index — computed
from Ψ on every run and exposed through `GET /api/v1/eclipse/redundancy`, the per-certificate
redundancy route, the `spectra eclipse redundancy` command and the /prove heatmap, with a cap
requiring only that `grounding_capped` be set and the measured sizes published — is replaced by
mandatory suppression: under `corridor_cap` or `grounding_capped` the index must be listed in
`derived_suppressed` and withheld. An implementer following Part I serves the matrix on a capped run
and emits an empty `derived_suppressed`, which the checker rejects with `VRD-014`.

OVERRIDES Part I section 25.6 H (A8): the rule that an absent `costs.toml` causes the frontier to be
computed over cardinality and labeled `cost_basis: "cardinality"` is replaced by mandatory
suppression — with no `costs.toml` supplied, `pareto_frontier` must appear in `derived_suppressed`
and no frontier is published on any basis. An implementer of section 25.6 H publishes a
cardinality-basis frontier and takes `VRD-014` on every costs-free run.

A1 is the headline rule the critics demanded: **ROBUST is unconstructible while any
soundness-affecting flag is set.** A5 is the Part I contradiction fix: `atoms_over_budget` now
degrades minimality only, and never suppresses an honest safety result.

Decision flow (this is the only permitted control flow; no other ordering is allowed):

```
            flags F, fixpoint results
                     |
                     v
        +------------------------------+
        |  A9: scope total & well-formed? |--no--> ERROR VRD-005 (no verdict emitted)
        +------------------------------+
                     | yes
                     v
        +------------------------------+
        |  F ∩ SOUNDNESS_MASK = ∅ ?    |
        +------------------------------+
           |yes                   |no
           v                      v
   goal ∉ fix(P_max)?      goal ∈ fix(P_min) with witness?
    |yes        |no           |yes            |no
    v           v             v                v
  ROBUST   goal ∈ fix(P_min)? UNSAFE      INDETERMINATE
             |yes      |no    (witness_class per A3/A4)
             v         v
          UNSAFE   OPTIMISTIC_ONLY
```

Note the asymmetry and do not "fix" it: soundness flags block the universal claim (ROBUST) but not
the witnessed existential claim (UNSAFE), because a witness over real EventIds survives
under-approximation. `er_ambiguous` is the exception, since a bad merge fabricates the leaves
themselves; it therefore degrades the witness class rather than the verdict.

---

## 66.5 Verdict strings

### 66.5.1 The bare verdict is forbidden

NEGATIVE REQUIREMENT. The tokens `ROBUST`, `OPTIMISTIC_ONLY`, `UNSAFE`, `INDETERMINATE` may never
appear as a standalone user-visible string in CLI output, API response bodies rendered for display,
UI text nodes, docs, README, the demo script, commit-message templates, slide decks, or exported
images. They may appear only as enum values inside machine-readable JSON, and only inside the
`verdict` object where the scope travels with them.

### 66.5.2 Canonical scope string

```abnf
verdict-string = safety "(" scope-body ")" [ " " minimality-clause ]
safety         = "ROBUST" / "OPTIMISTIC_ONLY" / "UNSAFE" / "INDETERMINATE"
scope-body     = "rules@" h SEP "controls@" h SEP "liveness@" h SEP
                 "er@" h SEP "goal@" h SEP "bundle@" h SEP "non-adaptive"
SEP            = ", "
h              = "b3:" 8HEXDIG          ; short form, exactly 8 nybbles
minimality-clause = "[" minimality "]"
minimality     = "EXACT_EXHAUSTIVE" / "EXACT_PSI_RELATIVE" / "SUBSET" / "UNVERIFIED"
```

Short rendering (CLI headers, UI header bar, one line):

```
OPTIMISTIC_ONLY(rules@b3:1a2b3c4d, controls@b3:5e6f7a8b, liveness@b3:9c0d1e2f,
                er@b3:3a4b5c6d, goal@b3:7e8f9a0b, bundle@b3:1c2d3e4f, non-adaptive)
                [EXACT_PSI_RELATIVE]
```

Long rendering (docs, exports, API `verdict_prose`, LLM narration input):

> OPTIMISTIC_ONLY under rule table b3:1a2b3c4d, control catalog b3:5e6f7a8b, the licenses derived in
> b3:9c0d1e2f, entity resolution b3:3a4b5c6d, goal b3:7e8f9a0b, bundle b3:1c2d3e4f, against a
> non-adaptive attacker. No proper subset of the cut severs the chain and no smaller cut satisfies
> the enumerated corridor set. This is a statement about the model, not about the system.

The trailing sentence "This is a statement about the model, not about the system." is part of the
long rendering and is not optional. Removing it fails `make lint-verdict-scope`.

OVERRIDES Part I section 42.8.6: the verbatim Proof-screen footer beginning "Soundness is relative
to the rule table..." and containing "ROBUST means:" is deleted and replaced by the long rendering
above, whose scope body and trailing sentence carry the same limitation; the Proof screen is not an
allowlisted file under 66.5.1, so the footer's standalone `ROBUST` token is a lint violation rather
than a release blocker to preserve. An implementer who ships the section 42.8.6 footer, believing it
non-negotiable, fails `make lint-verdict-scope` and leaves the build with two competing mandatory
closing sentences.

### 66.5.3 One renderer per language, no concatenation

Each language has exactly one function that turns a `Verdict` into a string, and it lives in one
file listed in `spec/verdict/renderers.toml`. That function is the only place in the repository
where a safety token may be adjacent to a string literal.

NEGATIVE REQUIREMENT. No code path anywhere may build a verdict string by concatenation,
interpolation, template substitution, f-string, `format!`, `fmt.Sprintf`, template literal, JSX
expression, Jinja template, or string join. The UI test asserts that the header bar's text content
equals the renderer's output byte for byte.

---

## 66.6 Rust: the smart constructor

```rust
// crates/spectra-verdict/src/lib.rs   -- no other module may construct a Verdict
#![forbid(unsafe_code)]

#[derive(Clone, Copy, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Safety { Robust, OptimisticOnly, Unsafe, Indeterminate }

#[derive(Clone, Copy, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Minimality { ExactExhaustive, ExactPsiRelative, Subset, Unverified }

#[derive(Clone, Copy, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum WitnessClass { Observed, Licensed, Contested }

/// Generated from spec/verdict/flags.toml by build.rs. Do not hand-edit.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct FlagSet(u16);
impl FlagSet {
    pub const SOUNDNESS_MASK: u16 = 0x013B;   // generated constant
    pub fn intersects_soundness(self) -> bool { self.0 & Self::SOUNDNESS_MASK != 0 }
    pub fn soundness_names(self) -> Vec<&'static str> { /* generated */ }
    pub fn reserved_clear(self) -> bool { self.0 & 0xFE00 == 0 }
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct Verdict {
    safety: Safety,                       // private
    witness_class: Option<WitnessClass>,  // private
    minimality: Minimality,               // private
    flags: FlagSet,                       // private
    scope: ScopeBinding,                  // private
    derived_suppressed: Vec<DerivedId>,   // private
    #[serde(skip)] _seal: Seal,           // private ZST: blocks struct-literal construction
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum VerdictError {
    #[error("VRD-001: ROBUST requested while soundness flags set: {0:?}")]
    RobustWithSoundnessFlag(Vec<&'static str>),
    #[error("VRD-002: UNSAFE requested without a witness tree")]
    UnsafeWithoutWitness,
    #[error("VRD-003: witness_class OBSERVED but witness contains a GHOST node at {0}")]
    ObservedWitnessContainsGhost(NodeId),
    #[error("VRD-004: exact minimality requested with corridor_cap or atoms_over_budget set")]
    ExactMinimalityUnderCap,
    #[error("VRD-005: scope binding incomplete: missing {0}")]
    IncompleteScope(&'static str),
    #[error("VRD-006: witness_class present on non-UNSAFE safety")]
    WitnessClassOnNonUnsafe,
    #[error("VRD-007: er_ambiguous set but witness_class is not CONTESTED")]
    ErAmbiguousWitnessNotContested,
    #[error("VRD-009: reserved flag bits are nonzero")]
    ReservedBitsSet,
}

impl Verdict {
    /// The ONLY constructor. There is no `pub fn new`, no `Default`, no `Deserialize`.
    pub fn build(p: VerdictProposal) -> Result<Verdict, VerdictError> {
        if !p.flags.reserved_clear() { return Err(VerdictError::ReservedBitsSet); }
        p.scope.assert_total()?;                                     // A9 -> VRD-005
        if p.safety == Safety::Robust && p.flags.intersects_soundness() {
            return Err(VerdictError::RobustWithSoundnessFlag(p.flags.soundness_names()));
        }                                                            // A1
        match (p.safety, p.witness_class) {
            (Safety::Unsafe, None)    => return Err(VerdictError::UnsafeWithoutWitness),
            (s, Some(_)) if s != Safety::Unsafe
                                      => return Err(VerdictError::WitnessClassOnNonUnsafe),
            _ => {}
        }                                                            // A2, and shape of A3/A4
        if matches!(p.minimality, Minimality::ExactExhaustive | Minimality::ExactPsiRelative)
            && (p.flags.has(Flag::CorridorCap) || p.flags.has(Flag::AtomsOverBudget)) {
            return Err(VerdictError::ExactMinimalityUnderCap);
        }                                                            // A5
        /* A3, A4, A7, A8 checks elided here are implemented in the same function and
           are covered by the conformance corpus in 66.9. */
        Ok(Verdict { /* ... */ _seal: Seal })
    }

    pub fn render_short(&self) -> String { /* the ONE renderer; see 66.5.3 */ }
    pub fn render_long(&self)  -> String { /* ... */ }
}
```

Hard requirements on this crate:
1. `Verdict` implements `Serialize` but **not** `Deserialize`. Reading a verdict from JSON goes
   through `VerdictProposal` and back through `build`, so an untrusted file can never instantiate an
   illegal verdict. A `#[derive(Deserialize)]` on `Verdict` fails `make lint-verdict`.
2. `Verdict` has no public fields and no public field-mutating method. It is immutable after
   construction.
3. `Display` for `Safety` is **not implemented**. Printing a bare safety token must not compile.
   A clippy lint plus a grep gate enforces the absence of `impl fmt::Display for Safety`.
4. `build` is total and deterministic: no clock, no RNG, no HashMap iteration, no float.

---

## 66.7 Python and TypeScript mirrors

Both mirrors are generated from `spec/verdict/flags.toml` plus `spec/verdict/algebra.toml` by
`make gen-verdict`. Generated files carry a header line with the spec hash; `make gen-verdict-check`
regenerates and diffs, and CI fails on drift.

```python
# services/spectra/verdict.py  (generated; hand edits fail gen-verdict-check)
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

SOUNDNESS_MASK = 0x013B          # generated from flags.toml

class VerdictError(ValueError): ...

_SEAL = object()

@dataclass(frozen=True, slots=True)
class Verdict:
    safety: "Safety"
    witness_class: Optional["WitnessClass"]
    minimality: "Minimality"
    flags: "FlagSet"
    scope: "ScopeBinding"
    derived_suppressed: Sequence[str]
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SEAL:
            raise VerdictError("VRD-010: construct via Verdict.build(), not Verdict()")

    @staticmethod
    def build(p: "VerdictProposal") -> "Verdict":
        if p.flags.mask & 0xFE00:
            raise VerdictError("VRD-009: reserved flag bits set")
        p.scope.assert_total()
        if p.safety is Safety.ROBUST and (p.flags.mask & SOUNDNESS_MASK):
            raise VerdictError(
                f"VRD-001: ROBUST with soundness flags {p.flags.soundness_names()}")
        ...
        return Verdict(..., _seal=_SEAL)

    def __str__(self) -> str:                      # the ONE renderer
        raise VerdictError("VRD-011: use render_short()/render_long(); str() is not a renderer")
```

Python-specific requirements: no Pydantic `model_construct`, no `dataclasses.replace`, no
`copy.deepcopy` re-hydration path that bypasses `build`; `Safety.__str__` raises. The FastAPI
response model serializes the `verdict` object as specified in 66.2.3 and never exposes `Safety`
alone as a top-level field.

```typescript
// web/src/verdict/verdict.ts  (generated)
export const SOUNDNESS_MASK = 0x013b;

declare const VerdictBrand: unique symbol;

export class Verdict {
  private constructor(
    readonly safety: Safety,
    readonly witnessClass: WitnessClass | null,
    readonly minimality: Minimality,
    readonly flags: FlagSet,
    readonly scope: ScopeBinding,
    readonly derivedSuppressed: readonly DerivedId[],
  ) {}
  declare readonly [VerdictBrand]: true;

  static build(p: VerdictProposal): Result<Verdict, VerdictError> { /* A1..A10 */ }

  renderShort(): string { /* the ONE renderer */ }
  renderLong(): string  { /* ... */ }

  toString(): never { throw new Error("VRD-011: use renderShort()/renderLong()"); }
}
```

TypeScript-specific requirements: `Safety` is a string-literal union but is **not exported** from
the module barrel, so no component can import it and render it alone; the only export surface is
`Verdict`, `Verdict.build` and the two renderers. `JSON.parse` of an API response produces a
`VerdictProposal`, never a `Verdict`. The verdict is never computed client-side (§39-42 invariant);
`Verdict.build` in the frontend is a *validator* of a server-produced proposal and, on `Err`,
renders the error panel instead of any verdict.

---

## 66.8 The Go checker: rejection is mandatory

`spectra verify` rejects, with a nonzero exit code, any certificate violating the algebra. The
checker re-derives the algebra from `spec/verdict/flags.toml` and `spec/verdict/algebra.toml` (text
inputs, hashed) and shares no code with the Rust crate, consistent with §63's independence gate.

| Code | Condition | Exit |
|---|---|---|
| `VRD-001` | `safety == ROBUST` and `flags & SOUNDNESS_MASK != 0` | 2 |
| `VRD-002` | `safety == UNSAFE` and no witness tree | 2 |
| `VRD-003` | `witness_class == OBSERVED` and witness contains a licensed (GHOST) instance | 2 |
| `VRD-004` | exact minimality with `corridor_cap` or `atoms_over_budget` set | 2 |
| `VRD-005` | scope binding incomplete, malformed, or `attacker != "non-adaptive"` | 2 |
| `VRD-006` | `witness_class` non-null on non-UNSAFE | 2 |
| `VRD-007` | `er_ambiguous` set and `witness_class != CONTESTED` | 2 |
| `VRD-008` | flag name unknown, duplicated, or out of bit order | 2 |
| `VRD-009` | reserved bits nonzero | 2 |
| `VRD-012` | scope hashes do not match the inputs the checker was given | 2 |
| `VRD-014` | `derived_suppressed` omits an entry required by A7/A8 | 2 |

Exit codes: `0` accept, `1` certificate internally consistent but a proof obligation failed
(closure, witness, Ψ), `2` verdict-algebra violation, `3` malformed input. The checker prints the
code, never a bare word.

OVERRIDES Part I sections 25.8 and 37.3: the exit tables `0` OK, `2` invariant violated, `3`
unlicensed, `4` witness invalid, `5` smaller cut exists, `6` input hash mismatch, and the CLI-wide
table in which `4` is validation failure, `5` integrity violation and `7` a checker rejection, are
replaced by the four codes above for `spectra verify`; a failed proof obligation, including a
smaller cut existing, is exit `1`, and every algebra rejection is exit `2`. An implementer who keeps
either Part I table wires CI gates and the /eclipse/verify endpoint to classify every
verdict-algebra rejection as "invariant violated" or to miss checker rejections entirely, since
exit `7` is never produced.

```
$ spectra verify out/cert-4f1c.json --rules rules.toml --controls controls.toml \
      --bundle bundle.jsonl --liveness out/liveness.json --er out/er.json
OK  closure verified            instances=<<MEASURED:instances>>
OK  goal unreachable in P_max
OK  witnesses re-derived        witnesses=<<MEASURED:witnesses>>
OK  no cut smaller than |S| satisfies Psi
OK  verdict algebra             flags=[] soundness=0
ACCEPT
ROBUST(rules@b3:1a2b3c4d, controls@b3:5e6f7a8b, liveness@b3:9c0d1e2f, er@b3:3a4b5c6d,
       goal@b3:7e8f9a0b, bundle@b3:1c2d3e4f, non-adaptive) [EXACT_PSI_RELATIVE]
  This is a statement about the model, not about the system.
elapsed=<<MEASURED:checker_ms>>ms
```

```
$ spectra verify corpus/forged/robust-with-corridor-cap.json ...
OK  closure verified
REJECT VRD-001: safety=ROBUST with soundness flags [corridor_cap]
  soundness mask 0x013b, certificate flags 0x0002
  A ROBUST safety claim is unconstructible while corridor enumeration was capped,
  because Psi is then an under-enumeration and the cut may miss an open corridor.
exit=2
```

The `<<MEASURED:...>>` tokens above are placeholder tokens per §70, not values; a CI grep fails if
any survives into `docs/` or source. The hex hashes above are syntactic examples only
(illustrative, not a target).

---

## 66.9 Cross-language conformance corpus

`spec/verdict/conformance/*.json` holds one file per case: a `VerdictProposal` plus the expected
outcome (`ACCEPT` with a canonical rendered string, or `REJECT` with a `VRD-nnn` code). Every
implementation runs the whole corpus:

```
make verdict-conformance      # runs corpus against Rust, Python, TypeScript, Go
```

Mandatory corpus contents:
1. **Exhaustive flag sweep.** All 2^9 = 512 flag subsets crossed with `safety = ROBUST`. Exactly the
   subsets disjoint from `SOUNDNESS_MASK` accept; every other subset must reject with `VRD-001`.
   This is a hard design constraint, not a measurement.
2. Every flag alone, crossed with all four safety values and all four minimality values.
3. `atoms_over_budget` with `safety = ROBUST` and `minimality = SUBSET` — must **ACCEPT**. This case
   is the regression test for the Part I contradiction; if it ever rejects, the conflation is back.
4. `er_ambiguous` with `UNSAFE`/`OBSERVED` — reject `VRD-007`; with `UNSAFE`/`CONTESTED` — accept.
5. Scope with each of the six hashes missing in turn — reject `VRD-005`.
6. `attacker: "adaptive"` — reject `VRD-005`.
7. Reserved bit 9 set — reject `VRD-009`.
8. Flags array alphabetically sorted instead of bit-ordered — reject `VRD-008`.
9. A certificate whose rendered `verdict_string` field disagrees with the renderer output — reject.

The build fails if the four implementations disagree on any case. Disagreement is reported as a
table of (case id, rust, python, typescript, go) and triaged per §62's oracle-disagreement
procedure.

---

## 66.10 The scope lint

`make lint-verdict-scope` runs on every push and fails the build on any violation.

```toml
# tools/lint/verdict-scope.toml
tokens = ["ROBUST", "OPTIMISTIC_ONLY", "OPTIMISTIC-ONLY", "UNSAFE", "INDETERMINATE"]

# Files scanned for user-visible strings.
scan = ["README.md", "docs/**/*.md", "web/src/**/*.{ts,tsx}", "services/**/*.py",
        "crates/**/*.rs", "checker/**/*.go", "demo/**", "spec/**/*.toml",
        "**/*.snap", "**/*.golden", "tests/e2e/**"]

# A token occurrence is LEGAL only if it is:
#   (a) an enum variant declaration or match arm in a generated verdict module, OR
#   (b) a JSON value inside a `"safety":` key, OR
#   (c) followed on the same logical line by a well-formed scope-body per the 66.5.2 grammar, OR
#   (d) inside a file listed in `allow_files` with an inline `# verdict-lint: rationale=...`.
allow_files = ["spec/verdict/flags.toml", "spec/verdict/algebra.toml", "LIMITATIONS.md"]

# Always illegal, anywhere, no allowlist:
banned_substrings = [
  "verdict: ROBUST",            # bare label
  "— ROBUST", "- ROBUST",       # the Part I demo header form
  "minimum cut",                # unless minimality == EXACT_EXHAUSTIVE (checked separately)
  "no smaller cut exists",
  "would have prevented", "would have stopped", "guaranteed", "formally verified",
]
```

OVERRIDES Part I section 25.13: the licensed phrasing "no smaller cut exists over the declared
control catalog" is withdrawn — "no smaller cut exists" and "minimum cut" are banned substrings with
no allowlist and no qualifying suffix that rescues them, and the permitted rendering for
`EXACT_PSI_RELATIVE` is "no smaller cut satisfies the enumerated corridor set" (66.2.2). An
implementer who writes the section 25.13 sentence into docs or the UI, or who builds the Part I
section 41.11 Proof header that renders the "minimum cut" as atoms, fails `make lint-verdict-scope`
on a rule that admits no exemption.

Additional gates in the same target:
- **Concatenation gate.** An AST pass per language flags any expression in which a safety token
  literal is an operand of string concatenation/interpolation outside the sanctioned renderer files
  listed in `spec/verdict/renderers.toml`. Failure code `VRD-015`.
- **DOM gate.** A Playwright assertion that the UI verdict header's `textContent` equals
  `Verdict.renderShort()` exactly, and that a sibling node carries the long rendering. Failure if
  the scope clause is in a tooltip, a popover, an `aria-label`, a collapsed accordion, or any node
  hidden at the default viewport.
- **Export gate.** PNG/SVG/PDF exports of the verdict header are rendered headlessly and OCR'd (or,
  preferably, asserted against the source DOM before rasterization); an export whose visible text
  lacks the scope body fails.
- **Demo gate.** The `make demo` transcript is diffed against a committed golden; a bare token in
  the transcript fails.
- **Narration gate.** The LLM narrator (§68) receives the rendered long form, never the enum, and a
  golden test asserts narration output contains no safety token that is not immediately followed by
  the scope body.

---

## 66.11 Hard ban on numeric judgement

NEGATIVE REQUIREMENT, enforced by `make lint-no-scores` over the OpenAPI document, the SQL DDL, the
TypeScript types, the Rust structs, the Go structs and the certificate schema. The following field
names, and any name containing them, are banned across the API, the database, the certificate and
the frontend:

```
confidence  score  severity  probability  likelihood  certainty  risk
criticality  priority  weight  rating  grade  percentile  pct  percent
_p50 _p95  normalized_  index_  strength
```

Exempt by explicit allowlist, because they are not judgements: `redundancy_index` (a Jaccard ratio
over corridors, suppressed under A7), `bit`, `cardinality`, `count`, `bytes`, `millis` in benchmark
artifacts only. Every exemption carries a one-line rationale in `spec/verdict/score-ban.toml`.

OVERRIDES Part I section 41.2: the investigations route
`GET /api/v1/investigations?q&status&severity&sort&page` is replaced by the same route with the
`severity` query parameter removed — the ban here covers field and parameter names across the API,
not only returned values as in Part I section 36.5, and `severity` is not on the exemption
allowlist. An implementer who ships the section 41.2 route as written puts a banned name into the
OpenAPI document and the TypeScript query types, fails `make lint-no-scores`, and has to rework the
frontend filter control built on that parameter.

FORBIDDEN CLAIMS. No implementation, document, UI string, API field, commit message, README line,
paper abstract or CV bullet generated from this repository may say, of any verdict:
- that it is a probability, a confidence, a risk level or a severity;
- that the control "would have prevented", "would have stopped", or "blocked" the attack — the
  permitted phrasing is "severs this chain in the model";
- that anything is "formally verified", "proven secure", or "guaranteed";
- that a `SUBSET` or `EXACT_PSI_RELATIVE` cut is "the minimum cut";
- that a ROBUST verdict holds against an adaptive attacker;
- that a verdict says anything about a real system rather than about the model.

A verdict is a claim about a fixpoint over a hand-authored rule table, under a hand-authored control
catalog, over the telemetry actually ingested, against an attacker who does not re-plan. The type
system in 66.6-66.8 exists so that no build of SPECTRA can emit a sentence that says more than that.
