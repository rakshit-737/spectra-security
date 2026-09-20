============================================================
57. GLOSSARY, CANONICAL VOCABULARY AND ID TYPES
============================================================

This section is normative over every other section in Part I and Part II. It is the single authority binding each concept in SPECTRA to exactly one name, exactly one identifier type, exactly one owning section, and exactly one representation in each of Python, Rust, Go, TypeScript and SQL. Where any other section uses a different word for a concept named here, this section wins and the other section is wrong.

OVERRIDES Part I: Part I had no glossary. Terms collided across sections (`atom` meant both a ground fact and a control threshold literal; `event` meant both a real-world occurrence and a serialized log line; `adapter`, `parser`, `collector` and `shipper` were used interchangeably). Every such collision is resolved below and the losing term is banned from identifiers by `make lint-vocab`.

---

## 57.1 Rules of the vocabulary

1. **One concept, one name.** Every concept in Table A has exactly one canonical name. Every other word for it is a forbidden synonym (Table D) and is banned from identifiers in all source trees.
2. **One name, one type.** Every concept that has identity has exactly one identifier type with exactly one wire grammar (§57.2) and exactly one byte encoding (§57.3).
3. **One concept, one owner.** Every concept names exactly one owning section that defines its semantics. Owners are written as section numbers where already assigned, or as symbolic `PART-II/<slug>` tokens resolved through `docs/section-index.toml`. `make lint-vocab` fails on an unresolved owner.
4. **The table is machine-readable.** Tables A–D are generated from `docs/vocab.toml`. The markdown in this section is the rendered view; `vocab.toml` is the source of truth. `make lint-vocab` fails if the rendered view and `vocab.toml` disagree byte for byte.
5. **Same-commit rule.** Any commit that introduces a new concept — a new declared type, a new SQL domain, a new certificate field, a new enum variant of a closed set — MUST add its row to `vocab.toml` in that same commit. `make lint-vocab` enforces this (§57.10, check V8). There is no follow-up-PR exception.
6. **Closed sets are closed here.** `DimensionId`, `FlagId`, `OperatorId`, `OracleId`, the entity-kind enum, the `safety` enum and the `minimality` enum are closed. New members are added in this section or not at all.
7. **No bare strings in typed positions.** Every language binding is a distinct nominal or branded type. Passing a `RecordId` where a `FactHash` is expected must be a compile-time or lint-time error in Python, Rust, Go and TypeScript, and a domain violation in SQL.
8. **No aliases.** `type Ev = RecordId`, `using Fact = ...`, `pub use ... as ...` re-exports under a second name, and TypeScript `type X = Y` alias chains over vocabulary types are forbidden and are a lint failure.

---

## 57.2 Identifier grammar (ABNF)

All identifiers are US-ASCII. Lowercase only. No whitespace, no Unicode, no percent-encoding, no leading zeros in numeric fields.

```abnf
; ---------- primitives ----------
DIGIT       = %x30-39
HEXDIG      = DIGIT / %x61-66                  ; lowercase hex ONLY
lower       = %x61-7A
snake       = lower *( lower / DIGIT / "_" )   ; max 48 octets
u16         = "0" / ( %x31-39 *4DIGIT )        ; 0..65535
level       = "0" / ( %x31-39 [ DIGIT ] )      ; 0..99
h128        = 32HEXDIG                         ; run-local digests
h256        = 64HEXDIG                         ; integrity-critical digests
kind        = "user" / "host" / "process" / "session" / "credential"
            / "key" / "service" / "account" / "file" / "netflow"
            / "api_client" / "resource"

; ---------- integrity-critical (MAY appear in a certificate) ----------
record-id     = "rc:"   h256
bundle-id     = "bn:"   h256
fact-hash     = "fh:"   h256
instance-id   = "in:"   h256
license-id    = "lic:"  h256
cut-id        = "cut:"  h256
corridor-id   = "cor:"  h256
hypothesis-id = "hy:"   h256
hypergraph-id = "hg:"   h256
run-id        = "run:"  h256
cert-id       = "cert:" h256

; ---------- run-local (MUST NOT appear in a certificate) ----------
event-id      = "ev:"   h128
transition-id = "tr:"   h128
window-id     = "bw:"   h128
assignment-id = "asg:"  h128
degradation-id= "deg:"  h128

; ---------- symbolic (authored, human-written) ----------
source-id     = "src:"  snake
collector-id  = "col:"  snake "@" u16
control-id    = "ctl:"  snake
literal-id    = "lit:"  snake "@" level        ; snake = the control's snake, no "ctl:"
rule-id       = "rl:"   snake
state-id      = "st:"   snake ":" snake        ; dimension ":" state
dimension-id  = "dim:"  snake
flag-id       = "flag:" snake
scenario-id   = "sc:"   snake "@" u16          ; u16 = scenario schema version
operator-id   = "op:"   snake
oracle-id     = "orc:"  snake
```

Prefix uniqueness is a hard invariant: no prefix is a prefix of another prefix. `make lint-vocab` recomputes this from `vocab.toml` and fails on violation.

**Certificate width rule.** Any identifier matching an `h128` form appearing anywhere inside a certificate is a hard rejection by `spectra verify`, not a warning. Rationale: `h128` IDs derive from run-local structure and are never adversarially reachable; integrity-critical IDs derive in part from untrusted telemetry bytes, where 128 bits of truncated digest permits a birthday-grinding attack at roughly 2^64 work. Do not "optimize" certificate size by truncating these.

---

## 57.3 Byte encoding and canonical digest construction

1. Every digest is BLAKE3-256 over the domain-separated byte string:

```
DIGEST(kind, payload) = BLAKE3-256( "spectra/v1/" || kind || 0x1F || payload )
```

   `kind` is the ID prefix without the colon (`"rc"`, `"fh"`, `"in"`, ...), as ASCII. `0x1F` is the ASCII unit separator and may never appear inside `kind`.
2. An `h256` ID renders all 32 output octets as lowercase hex. An `h128` ID renders **the first 16 octets only**, lowercase hex. Truncation is a prefix, never a fold, never a XOR.
3. `payload` is the concept's canonical byte encoding, defined per concept in `vocab.toml` field `payload`. Canonical encodings are built only from: ASCII identifiers as written; unsigned integers as fixed-width big-endian (`u8`, `u16`, `u32`, `u64`); and ordered sequences as `count:u32` big-endian followed by elements. **No JSON, no floats, no locale-sensitive formatting, no platform-endian writes, no length-prefixed UTF-8 with implementation-defined normalization.**
4. Sequences inside a payload are sorted by plain bytewise (`memcmp`) ascending order of the element's canonical bytes before hashing. Sorting is stable and total. Never sort by a language's default collation.
5. On the wire (JSONL bundles, certificate JSON, TOML catalogs, HTTP APIs) every identifier is the ASCII string of §57.2 — never a byte array, never base64, never an integer.
6. In SQL, every identifier is `text` constrained by a `DOMAIN`, never `bytea`, never `uuid`:

```sql
CREATE DOMAIN record_id   AS text CHECK (VALUE ~ '^rc:[0-9a-f]{64}$');
CREATE DOMAIN fact_hash   AS text CHECK (VALUE ~ '^fh:[0-9a-f]{64}$');
CREATE DOMAIN entity_id   AS text CHECK (VALUE ~ '^en:(user|host|process|session|credential|key|service|account|file|netflow|api_client|resource):[0-9a-f]{32}$');
CREATE DOMAIN literal_id  AS text CHECK (VALUE ~ '^lit:[a-z][a-z0-9_]{0,47}@(0|[1-9][0-9]?)$');
CREATE DOMAIN tick        AS bigint CHECK (VALUE >= 0);
-- ... one DOMAIN per row of Table A that has an ID type.
```

7. `Tick` is `u64`, an integer count of nanoseconds since the scenario epoch (tick 0). All intervals are half-open `[t0, t1)`. There is no floating point anywhere in the time model and no wall-clock value in any hashed payload.

---

## 57.4 Table A — master binding: concept, ID type, owner, definition

`ord.` = run-local dense integer, never serialized outside the process. `—` = no identity of its own.

| # | Canonical name | ID type | Owner | Definition (normative, one sentence) |
|---|---|---|---|---|
| 1 | event | `EventId` (`ev:`) | §62 | An occurrence in the modeled system as the generator emitted it; ground-truth identity, never visible to the kernel. |
| 2 | record | `RecordId` (`rc:`) | PART-II/ingest | One serialized telemetry line as ingested, digested over its exact pre-parse bytes. |
| 3 | bundle | `BundleId` (`bn:`) | PART-II/ingest | The immutable, ordered, content-addressed set of records constituting one run's input. |
| 4 | source | `SourceId` (`src:`) | PART-II/ingest | A declared telemetry origin with a class, a format and a liveness contract. |
| 5 | collector | `CollectorId` (`col:`) | PART-II/ingest | The code that reads one source's native format and emits canonical records. |
| 6 | tick | `Tick` (u64) | §17 | Integer nanoseconds since the scenario epoch; the only time quantity in the system. |
| 7 | entity | `EntityId` (`en:`) | §9 | A resolved actor or object of a closed kind, produced by entity resolution. |
| 8 | dimension | `DimensionId` (`dim:`) | §13 | One of the ten security dimensions, each owning one finite-state machine. |
| 9 | state | `StateId` (`st:`) | §13 | A declared value of one dimension's FSM. |
| 10 | transition | `TransitionId` (`tr:`) | §13 | An evidence-bound change of one entity's state within one dimension at one tick. |
| 11 | state graph | — | §20 | The materialized view over transitions; a derived view, never a separate store of truth. |
| 12 | fact | `FactHash` (`fh:`), `FactId` ord. | §17 | A ground, time-indexed predicate instance; the OR-nodes of the hypergraph. |
| 13 | goal fact | `FactHash` | §5 | A fact declared in the goal library as an attacker objective; goals are a set, verdicts are per-goal. |
| 14 | atom | **RETIRED** | §57 | Banned term. Meant both "fact" and "threshold literal" in Part I. Use one of those. |
| 15 | threshold literal | `LiteralId` (`lit:`) | §22 | The proposition `control k is set to at least level l`; the unit of every cut and every blocker mask. |
| 16 | control | `ControlId` (`ctl:`) | §22 | A declared, levelled security control in the catalog. |
| 17 | level | `Level` (u8, 0..m_k) | §22 | An ordered strictness setting of one control; higher is never weaker. |
| 18 | control assignment | `AssignmentId` (`asg:`) | §22 | A total map from every `ControlId` to one `Level`; what the range is re-executed under. |
| 19 | cut | `CutId` (`cut:`) | §25 | A set of threshold literals asserted true; the object a certificate is about. |
| 20 | corridor | `CorridorId` (`cor:`) | §25 | An irreducible clause over threshold literals that every sufficient cut must satisfy. |
| 21 | rule | `RuleId` (`rl:`) | §22 | One authored implication in `rules.toml`, with head, body, guard, producing sources and provenance note. |
| 22 | rule instance | `InstanceId` (`in:`) | §25 | One grounding of one rule to specific facts; the AND-nodes of the hypergraph. |
| 23 | silent instance | `InstanceId` | §25 | A rule instance carrying a `LicenseId` and citing no record; admitted only inside a blind window. |
| 24 | GHOST | — (derived predicate) | §39 | The rendering predicate `every derivation of this node passes through a silent instance`. |
| 25 | license | `LicenseId` (`lic:`) | §25 | The permission to instantiate silent instances of a rule over an interval, justified by a blind window. |
| 26 | blind window | `WindowId` (`bw:`) | PART-II/liveness | A maximal half-open interval over which a source's liveness verdict is BLIND or SUPPRESSED. |
| 27 | liveness | `LivenessVerdict` enum | PART-II/liveness | The per-(source, interval) verdict `LIVE / BLIND / SUPPRESSED`; the fail-closed value is `BLIND`. |
| 28 | hypergraph | `HypergraphId` (`hg:`) | §20 | The provenance structure of one grounding: OR-nodes are facts, AND-nodes are rule instances. |
| 29 | hypothesis | `HypothesisId` (`hy:`) | §25 | One derivation of one goal fact: its instance set, its license set, and its realizability status. |
| 30 | certificate | `CertId` (`cert:`) | PART-II/certificate | The content-addressed proof artifact the kernel emits and `spectra verify` checks. |
| 31 | verdict | — (typed record) | PART-II/verdict-algebra | The pair `safety` x `minimality` plus its mandatory scope binding; never a single word. |
| 32 | flag | `FlagId` (`flag:`) | PART-II/verdict-algebra | A named boolean recording a degraded condition of a run; a closed set. |
| 33 | scenario | `ScenarioId` (`sc:`) | §5 | A named, seeded, versioned attack narrative the generator realizes deterministically. |
| 34 | degradation operator | `OperatorId` (`op:`) | PART-II/degradation | One of the six pure, seeded transforms on a bundle: delete, delay, duplicate, reorder, corrupt, suppress. |
| 35 | degradation spec | `DegradationId` (`deg:`) | PART-II/degradation | An ordered list of (operator, parameters, seed) defining one matrix cell. |
| 36 | run manifest | `RunId` (`run:`) | PART-II/determinism | The hashed core of one execution: all input digests, git SHA, toolchain versions, seeds. |
| 37 | oracle | `OracleId` (`orc:`) | §62 | An independently implemented judge of a property; a closed set of five. |

---

## 57.5 Table B — language bindings

Convention, enforced by check V4: the binding is the concept's PascalCase canonical name in Python, Rust, Go and TypeScript, and its snake_case name in SQL, inside the module named below. The table records the modules and the exceptions; it is not decorative, it is the list the lint iterates.

| Concept | Python (`spectra.vocab`) | Rust (`spectra_core::vocab`) | Go (`internal/vocab`) | TypeScript (`@spectra/vocab`) | SQL |
|---|---|---|---|---|---|
| event | `EventId = NewType(str)` | `struct EventId([u8;16])` | `type EventId string` | `type EventId = Brand<'EventId'>` | domain `event_id` (oracle schema only) |
| record | `RecordId` | `struct RecordId([u8;32])` | `type RecordId string` | `RecordId` | domain `record_id`; table `record` |
| bundle | `BundleId` | `struct BundleId([u8;32])` | `type BundleId string` | `BundleId` | domain `bundle_id`; table `bundle` |
| source | `SourceId` | `struct SourceId(SmolStr)` | `type SourceId string` | `SourceId` | domain `source_id`; table `source` |
| collector | `CollectorId` | `struct CollectorId(SmolStr)` | `type CollectorId string` | `CollectorId` | domain `collector_id` |
| tick | `Tick = NewType(int)` | `struct Tick(u64)` | `type Tick uint64` | `type Tick = bigint & Brand` | domain `tick` (`bigint`) |
| entity | `EntityId` | `struct EntityId{kind,h}` | `type EntityId string` | `EntityId` | domain `entity_id`; table `entity` |
| dimension | `Dimension(StrEnum)` | `enum Dimension` | `type Dimension string` + consts | `type Dimension = union` | enum type `dimension` |
| state | `StateId` | `struct StateId(SmolStr)` | `type StateId string` | `StateId` | domain `state_id` |
| transition | `TransitionId` | `struct TransitionId([u8;16])` | `type TransitionId string` | `TransitionId` | domain `transition_id`; table `transition` |
| state graph | — | — | — | — | view `state_graph` |
| fact | `FactHash` | `struct FactHash([u8;32])`, `FactId(u32)` | `type FactHash string` | `FactHash` | domain `fact_hash` |
| goal fact | `GoalFact` | `struct GoalFact(FactHash)` | `type GoalFact FactHash` | `GoalFact` | table `goal_fact` |
| threshold literal | `LiteralId` | `struct LiteralId{ctl,lvl}` | `type LiteralId string` | `LiteralId` | domain `literal_id` |
| control | `ControlId` | `struct ControlId(SmolStr)` | `type ControlId string` | `ControlId` | domain `control_id`; table `control` |
| level | `Level = NewType(int)` | `struct Level(u8)` | `type Level uint8` | `type Level = number & Brand` | domain `level` (`smallint`) |
| control assignment | `AssignmentId` | `struct AssignmentId([u8;16])` | `type AssignmentId string` | `AssignmentId` | table `control_assignment` |
| cut | `CutId`, `Cut = frozenset[LiteralId]` | `struct Cut(u64)`, `CutId` | `type Cut []LiteralId` | `type Cut = readonly LiteralId[]` | table `cut`, `cut_literal` |
| corridor | `CorridorId` | `struct CorridorId([u8;32])` | `type CorridorId string` | `CorridorId` | table `corridor` |
| rule | `RuleId` | `struct RuleId(SmolStr)` | `type RuleId string` | `RuleId` | domain `rule_id`; table `rule` |
| rule instance | `InstanceId` | `struct InstanceId([u8;32])` | `type InstanceId string` | `InstanceId` | domain `instance_id` |
| silent instance | `SilentInstance` | `struct SilentInstance(RuleInst)` | `type SilentInstance RuleInstance` | `SilentInstance` | column `rule_instance.license_id NOT NULL` |
| GHOST | `is_ghost()` | `fn is_ghost()` | `func IsGhost()` | `isGhost()` | view column `is_ghost boolean` |
| license | `LicenseId` | `struct LicenseId([u8;32])` | `type LicenseId string` | `LicenseId` | domain `license_id`; table `license` |
| blind window | `WindowId` | `struct WindowId([u8;16])` | `type WindowId string` | `WindowId` | table `blind_window` |
| liveness | `LivenessVerdict(StrEnum)` | `enum LivenessVerdict` | `type LivenessVerdict string` | `type LivenessVerdict = union` | enum type `liveness_verdict` |
| hypergraph | `HypergraphId` | `struct HypergraphId([u8;32])` | `type HypergraphId string` | `HypergraphId` | table `hypergraph` |
| hypothesis | `HypothesisId` | `struct HypothesisId([u8;32])` | `type HypothesisId string` | `HypothesisId` | table `hypothesis` |
| certificate | `CertId`, `Certificate` | `struct CertId`, `Certificate` | `type CertId string`, `Certificate` | `CertId`, `Certificate` | table `certificate` |
| verdict | `Verdict` (frozen dataclass) | `struct Verdict` | `type Verdict struct` | `interface Verdict` | composite type `verdict` |
| flag | `Flag(StrEnum)` | `enum Flag` | `type Flag string` + consts | `type Flag = union` | enum type `flag` |
| scenario | `ScenarioId` | `struct ScenarioId{name,ver}` | `type ScenarioId string` | `ScenarioId` | domain `scenario_id`; table `scenario` |
| degradation operator | `Operator(StrEnum)` | `enum Operator` | `type Operator string` | `type Operator = union` | enum type `operator` |
| degradation spec | `DegradationId`, `DegradationSpec` | `struct DegradationSpec` | `type DegradationSpec struct` | `DegradationSpec` | table `degradation_spec` |
| run manifest | `RunId`, `RunManifest` | `struct RunId`, `RunManifest` | `type RunManifest struct` | `RunManifest` | table `run_manifest` |
| oracle | `Oracle(StrEnum)` | `enum Oracle` | `type Oracle string` | `type Oracle = union` | enum type `oracle` |

Haskell, when the stretch admissibility oracle exists, binds the same names as Rust with `newtype` and is checked by the same lint; it is not a required column because the Haskell oracle may be descoped.

---

## 57.6 Table C — closed enumerations

```
Dimension      : identity session credential privilege process
                 network api service resource trust                 (exactly 10)
LivenessVerdict: LIVE BLIND SUPPRESSED                              (fail-closed = BLIND)
LicenseBasis   : BLIND SUPPRESSED OBLIGATION
Safety         : ROBUST OPTIMISTIC_ONLY UNSAFE
Minimality     : EXACT SUBSET UNVERIFIED
Operator       : delete delay duplicate reorder corrupt suppress    (exactly 6)
Oracle         : range_reexec go_checker generator_ground_truth
                 z3_test_only haskell_admissibility                 (exactly 5)
Flag           : grounding_capped corridor_capped subset_minimal_only
                 greedy_cover er_ambiguous liveness_uncalibrated
                 budget_exhausted realizability_unchecked
                 oracle_channel_absent quarantined_records_present
EntityKind     : user host process session credential key service
                 account file netflow api_client resource           (exactly 12)
```

OVERRIDES Part I / ECLIPSE §5: `Cert.mode: ROBUST|OPTIMISTIC` is deleted. A certificate carries independent `safety` and `minimality` fields plus a scope binding, because subset-minimality is a statement about cut size and has nothing to do with whether the goal is reachable. Collapsing them suppressed honest safety results for unrelated reasons and created an incentive to keep the control catalog small.

OVERRIDES Part I / ECLIPSE §8: a verdict is never rendered as a bare word. The only renderable form is

```
ROBUST(rules@<16hex>, catalog@<16hex>, licenses@<16hex>, non-adaptive) / minimality=SUBSET
```

No code path may build this string by concatenation; it is produced by one function per language, and `spectra verify` rejects any certificate whose verdict lacks a complete scope binding.

---

## 57.7 Table D — forbidden synonyms (banned identifier segments)

Matching is at identifier-segment granularity after splitting `snake_case`, `camelCase`, `PascalCase`, `kebab-case` and `SCREAMING_SNAKE`. Multi-word entries match adjacent segment sequences. Substring matching is NOT used, so `parser` alone is legal while `log_parser` is not.

| Canonical | Forbidden in identifiers |
|---|---|
| event | `log_event`, `logline`, `log_line`, `alert`, `datum`, `telemetry_item`, `occurrence` |
| record | `row`, `log_entry`, `entry`, `message`, `doc`, `raw_log`, `line_item` |
| bundle | `dataset`, `corpus`, `dump`, `capture`, `feed`, `log_set` |
| source | `log_source`, `sensor`, `stream`, `producer`, `channel`, `emitter` |
| collector | `source_adapter`, `log_parser`, `ingestor`, `shipper`, `agent`, `tailer` |
| tick | `ts`, `epoch_ms`, `timestamp_float`, `wall_clock`, `datetime`, `now` |
| entity | `actor`, `principal`, `subject`, `asset`, `object_id`, `node_id` |
| dimension | `axis`, `facet`, `plane`, `category`, `domain`, `aspect` |
| state | `status`, `condition`, `mode`, `phase`, `posture`, `stage` |
| transition | `change`, `step`, `move`, `action`, `state_event`, `edge` |
| fact | `tuple`, `assertion`, `belief`, `finding`, `observation`, `predicate_instance` |
| threshold literal | `atom`, `bit`, `blocker_atom`, `control_bit`, `knob_literal` |
| control | `mitigation`, `countermeasure`, `defense`, `safeguard`, `knob`, `toggle` |
| level | `strength`, `tier`, `intensity`, `grade`, `severity`, `setting` |
| cut | `solution`, `fix`, `remediation`, `recommendation`, `minimal_set`, `blocker_set` |
| corridor | `path`, `attack_path`, `kill_chain`, `route`, `clause_path` |
| rule | `heuristic`, `detection`, `signature`, `correlation_rule`, `policy` |
| rule instance | `hyperedge`, `derivation`, `firing`, `application`, `match`, `hit` |
| silent instance | `inferred_step`, `assumed_step`, `hypothetical`, `guess`, `imagined` |
| GHOST | `phantom`, `shadow`, `virtual`, `fake`, `synthetic_node` |
| license | `assumption`, `allowance`, `exception`, `waiver`, `permit` |
| blind window | `gap`, `outage`, `hole`, `dark_period`, `coverage_gap` |
| liveness | `coverage`, `health`, `uptime`, `availability`, `visibility` |
| hypergraph | `attack_graph`, `provenance_graph`, `dag`, `proof_tree` |
| hypothesis | `theory`, `story`, `narrative`, `attack_chain`, `chain` |
| certificate | `proof`, `report`, `result_blob`, `receipt`, `attestation` |
| verdict | `outcome`, `decision`, `is_safe`, `passed`, `status_word` |
| scenario | `case`, `sample`, `example`, `campaign`, `incident` |
| degradation operator | `noise`, `perturbation`, `mutation`, `fuzz`, `damage`, `attack_op` |
| run manifest | `metadata`, `run_info`, `provenance_blob`, `context` |
| oracle | `validator`, `truth`, `reference_impl`, `baseline` |

**Universally banned identifier segments**, with no canonical counterpart, because the concept itself is forbidden by the project constraints: `score`, `confidence`, `probability`, `likelihood`, `risk_score`, `severity`, `priority`, `weight`, `ranking`, `percent_certain`, `residual_reachability`, `cost_mass`, `threat_level`.

OVERRIDES Part I / ECLIPSE §4H: `residual reachability` is retired as a name and as a quantity. The frontier reports two sets — `residual_goal_facts: Vec<FactHash>` and `open_corridors: Vec<CorridorId>` — and nothing collapses them into a scalar. The lint bans the old name outright.

---

## 57.8 The three structural overrides that this vocabulary forces

**OVERRIDES Part I: `atom` is retired.** ECLIPSE §3's comment `FactId(u32) // ground, time-indexed atom` reads `// ground, time-indexed fact`. ECLIPSE §2's "atom set A" reads "literal set L". `Cert.cut: Vec<Atom>` reads `Vec<LiteralId>`. `goal.toml`'s "objective atom" reads "goal fact", and goals are a set with one verdict each.

**OVERRIDES Part I: evidence cites `RecordId`, never `EventId`.** `RuleInst.evidence: Vec<EventId>` becomes `Vec<RecordId>`, and every witness tree leaf is a `RecordId`. `EventId` is the generator's private identity for an occurrence; it is carried on the oracle channel, never in a bundle the kernel reads. This is what makes the zero-false-ROBUST invariant measurable under degradation: operators mutate records and therefore `RecordId`s, while `EventId`s survive, so §62 can re-link a perturbed bundle to ground truth through the `oracle_link(event_id, record_id)` table.

```
         GENERATOR                          KERNEL-VISIBLE                 ORACLE CHANNEL
         ---------                          --------------                 --------------
   occurrence --> EventId  ---------------------------------------------->  ev:9f1c...
        |                                                                       |
        +--> emitted lines --> [degradation ops] --> bundle.jsonl               | oracle_link
                                                         |                      |
                                                    rc:4b7e...  <---------------+
                                                         |
                          collector --> fact(fh:) --> rule instance(in:) --> hypergraph(hg:)
                                                         |                       |
                                          license(lic:) -+                   hypothesis(hy:)
                                                                                 |
                                                             corridor(cor:) --> cut(cut:) --> certificate(cert:)

   HARD RULE: no arrow crosses right-to-left from the oracle channel into the kernel path.
```

The kernel, the collectors, the grounder and `spectra verify` MUST NOT read the `event_id` field. A dedicated lint (`make lint-oracle-channel`, owned by §62) greps the kernel, collector and checker trees for `event_id` and fails on any hit outside the oracle crate. If `oracle_link` is absent for a run, the run sets `flag:oracle_channel_absent` and is excluded from every scored result.

**OVERRIDES Part I: threshold-literal bit positions are derived, not authored.** The 64-bit `blockers` mask assigns bit `i` to the `i`-th `LiteralId` in the total order: sort by `ControlId` bytewise ascending, then by `Level` ascending. Bit assignment is therefore a pure function of the control catalog, and a catalog edit renumbers bits. Consequently: masks are never compared across two different `catalog_hash` values, no mask is ever printed in a user-facing artifact, and every certificate records both the `catalog_hash` and the explicit ordered `Vec<LiteralId>` so that bit positions never need to be reconstructed by a reader. `make lint-vocab` recomputes `sum(m_k) + |controls|` and fails the build when it exceeds 64 (check V9).

---

## 57.9 `docs/vocab.toml` — the machine-readable source

```toml
schema_version = 1

[[concept]]
name        = "record"
id_type     = "RecordId"
prefix      = "rc"
width       = "h256"
certifiable = true                     # may appear inside a certificate
owner       = "PART-II/ingest"
definition  = "One serialized telemetry line as ingested, digested over its exact pre-parse bytes."
payload     = ["bytes:raw_line_without_trailing_newline"]
py = "spectra.vocab.RecordId"
rs = "spectra_core::vocab::RecordId"
go = "internal/vocab.RecordId"
ts = "@spectra/vocab#RecordId"
sql = "domain record_id"
forbidden = ["row", "log_entry", "entry", "message", "doc", "raw_log", "line_item"]

[[concept]]
name        = "threshold_literal"
id_type     = "LiteralId"
prefix      = "lit"
width       = "symbolic"
certifiable = true
owner       = "22"
definition  = "The proposition that a control is set to at least a given level."
payload     = ["ascii:control_id", "u8:level"]
py = "spectra.vocab.LiteralId"
rs = "spectra_core::vocab::LiteralId"
go = "internal/vocab.LiteralId"
ts = "@spectra/vocab#LiteralId"
sql = "domain literal_id"
forbidden = ["atom", "bit", "blocker_atom", "control_bit", "knob_literal"]

[[retired]]
name    = "atom"
reason  = "Meant both 'fact' and 'threshold literal' in Part I; ambiguous across five languages."
use     = ["fact", "threshold_literal"]
```

`[[retired]]` entries are banned everywhere with no allowlist path: a retired term cannot be justified, only replaced.

---

## 57.10 `make lint-vocab`

One target. Deterministic, offline, no network, single-threaded, exit code 0 or 1. Runs on every push in the per-PR tier; it is cheap enough that there is no nightly-only excuse.

```
INPUTS: docs/vocab.toml, docs/section-index.toml, docs/vocab-allow.toml,
        all tracked files under services/ kernel/ checker/ frontend/ sql/
        collectors/ generator/ oracle/ docs/ README.md

V1  GRAMMAR        every prefix unique, no prefix is a prefix of another;
                   every regex in Table C compiles; every ID literal found in
                   fixtures/ and docs/ matches the grammar of its declared prefix.
V2  COMPLETENESS   every [[concept]] has: id_type|"-", owner, definition,
                   py, rs, go, ts, sql, and either forbidden=[...] non-empty
                   or forbidden_none=true with a written reason.
V3  OWNER          every owner resolves in section-index.toml to a real section.
V4  BINDINGS       for each concept and each of the five language trees, the
                   declared symbol is DEFINED exactly once (regex per language:
                   `class X`/`X = NewType`, `struct X`/`enum X`, `type X `,
                   `type X =`/`interface X`, `CREATE DOMAIN x`/`CREATE TABLE x`).
                   Zero definitions -> fail. Two or more -> fail (alias ban).
V5  SYNONYMS       tokenize every identifier in every tracked source file;
                   split camel/Pascal/snake/kebab/SCREAMING; match segment
                   n-grams against the forbidden list and the universal ban list;
                   report file:line:identifier:banned_term:canonical_replacement.
V6  RETIRED        any occurrence of a [[retired]] name as an identifier segment,
                   a JSON key, a TOML key, a SQL column, or an OpenAPI field.
                   No allowlist applies.
V7  UNREGISTERED   any identifier segment appearing in >= 2 of the five language
                   trees and >= 8 times total (illustrative, not a target) that is
                   neither in vocab.toml nor in vocab-allow.toml -> fail with
                   "unregistered concept: add a row to docs/vocab.toml".
V8  SAME-COMMIT    if the staged diff adds a `CREATE DOMAIN`, a new certificate
                   JSON key, a new closed-enum variant, or a new type matching a
                   vocabulary naming pattern, and docs/vocab.toml is unchanged in
                   the same commit -> fail.
V9  ATOM BUDGET    sum over controls.toml of (m_k + 1) minus |controls| <= 64.
V10 CERT WIDTH     no concept with certifiable=true has width h128; no h128
                   prefix appears in any committed certificate fixture.
V11 RENDER         regenerate Tables A-D from vocab.toml and diff against this
                   section's markdown; any byte difference fails.
```

`docs/vocab-allow.toml` entries are narrow and must justify themselves:

```toml
[[allow]]
term  = "message"
paths = ["frontend/src/i18n/**"]
reason = "UI string catalogue; 'message' here is a localized string, not a record."
```

An allow entry with an empty `reason`, or with a `paths` glob broader than one directory, fails V2. There is no repo-wide allow.

Expected output shape (illustrative, not a target):

```
$ make lint-vocab
vocab: 37 concepts, 1 retired, 28 ID types, 5 language trees
V1 grammar .......... ok      (28 prefixes, 0 collisions)
V2 completeness ..... ok
V3 owners ........... ok      (14 Part I, 9 Part II, 0 unresolved)
V4 bindings ......... FAIL
    concept 'corridor': no definition found in tree 'go'
      expected one of: type Corridor* / CorridorId in checker/internal/vocab/*.go
V5 synonyms ......... FAIL
    kernel/src/solve/cut.rs:114  ident `atom_mask`        banned `atom`      -> use `literal`
    services/api/routes/prove.py:88 ident `recommendation` banned `recommendation` -> use `cut`
    frontend/src/panels/Verdict.tsx:31 ident `confidence`  banned (universal) -> delete
V6 retired .......... FAIL    3 occurrences of retired term `atom`
V7 unregistered ..... ok
V8 same-commit ...... ok
V9 atom budget ...... ok      (61 of 64 threshold literals used)
V10 cert width ...... ok
V11 render .......... ok
lint-vocab: FAILED (3 checks, 5 findings)
make: *** [lint-vocab] Error 1
```

CI binding: `lint-vocab` is a required check on every pull request and is listed in the milestone ratchet file. It may not be marked `continue-on-error`. A failing `lint-vocab` blocks merge with no waiver path; waivers exist only for `vocab-allow.toml` entries, which are themselves reviewed as part of the diff.

---

## 57.11 Negative requirements and forbidden claims

1. Do NOT introduce a second name for any concept in Table A, including "for readability", in a docstring, in a UI label, in an OpenAPI field, or in a commit message template.
2. Do NOT add a type alias, re-export, or wrapper that exposes a vocabulary type under a second name in any language.
3. Do NOT use `atom` for anything. It is retired, not deprecated.
4. Do NOT put an `EventId` in a bundle, a fact, a rule instance, a license, a witness tree or a certificate. Do NOT read `event_id` from any kernel, collector or checker code path.
5. Do NOT emit any field, column, JSON key, GraphQL field, metric name or UI label containing `score`, `confidence`, `probability`, `severity`, `risk`, `likelihood` or `priority`. There is no numeric grading anywhere in SPECTRA.
6. Do NOT compare two `blockers` bitmasks, two bit positions, or two cut encodings across differing `catalog_hash` values, and do NOT display a raw bitmask to a user.
7. Do NOT render a verdict as a single word, and do NOT construct a verdict string by concatenation in any language.
8. Do NOT treat `make lint-vocab` findings as style. A synonym drift across two languages is a correctness defect, because the Rust kernel and the Go checker must agree on what they are checking.
9. Do NOT claim that this section makes the five implementations semantically equivalent. It makes them *nominally* aligned. Two components can agree on the word `license` and still disagree on when one is issued; that equivalence is the job of the differential fuzz gates, not of this table.
10. Do NOT claim a "shared type system" or "single source of truth for types" in README or docs. The honest claim is: one authored vocabulary file, five hand-written bindings, and a lint that fails when they drift or when a banned synonym appears.
11. Do NOT count the tokens in this section toward any language, format, or "concepts modeled" figure in the README. `vocab.toml` is configuration.
