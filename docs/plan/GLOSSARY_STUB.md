# SPECTRA — canonical vocabulary (working stub)

**This file is a working stub, not the source of truth.**

- Normative text: section 57 of the master prompt (`docs/prompt/part2/57-glossary.md`).
- Eventual machine source of truth: `docs/vocab.toml`, with this markdown generated from it.
- `make lint-vocab` fails the build when the rendered view and `vocab.toml` disagree byte for byte.

The rules that matter most:

1. One concept, one name. Every other word for it is a forbidden synonym and is banned from
   identifiers in every source tree.
2. One name, one identifier type, one wire grammar, one byte encoding.
3. Same-commit rule: a commit introducing a new concept adds its row to `vocab.toml` in that same
   commit. No follow-up-PR exception.
4. No bare strings in typed positions, and no aliases — passing a `RecordId` where a `FactHash` is
   expected is a compile-time or lint-time error in Python, Rust, Go and TypeScript, and a domain
   violation in SQL.

Two retirements to be aware of before writing any code:

- **`atom` is retired.** In Part I it meant both "fact" and "threshold literal". Use one of those.
- **`residual reachability` is retired**, as a name and as a quantity. The frontier reports two
  sets, `residual_goal_facts` and `open_corridors`, and nothing collapses them into a scalar.

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

