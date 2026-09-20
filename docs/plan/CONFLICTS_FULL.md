# SPECTRA — Part I / Part II conflicts, unabridged

The complete audit output, undeduplicated, with full quotations. `CONFLICTS.md` is the working document; this is the record behind it.

## 57 Glossary / vocabulary

### UNRESOLVED

#### The threshold-literal budget arithmetic

**Tension.** Three formulas are in play. §22.2: "The global atom budget is `Sigma_k m_k <= 64`", with `E_ATOM_BUDGET` above it. §57.8: "`make lint-vocab` recomputes `sum(m_k) + |controls|` and fails the build when it exceeds 64 (check V9)." §57.10's V9: "sum over controls.toml of (m_k + 1) minus |controls| <= 64" — which equals `sum(m_k)` and therefore agrees with Part I and contradicts §57.8 two pages earlier.

**Decision needed.** Which is normative: `sum(m_k) <= 64`, or `sum(m_k) + |controls| <= 64`? With the fifteen controls of §22.6, the stricter form spends 15 of the 64 bits on nothing and may make the shipped catalog uncompilable.

**Recommended.** Adopt `sum(m_k) <= 64` (Part I and V9 agree; level 0 is 'absent' and needs no literal), correct §57.8's prose, and have V9 print both counts so the discrepancy cannot silently return.

#### Part I certificate flags with no member in the closed Flag set

**Tension.** Table C declares `Flag` closed — "New members are added in this section or not at all" — yet three Part I flags have no member: `illegal_dependency` (§16.2.4, where a certificate depending on an ILLEGAL transition "may not be reported ROBUST"), `contested` (§14.8, set when a conflict resolves above rung 5), and `signed_collectors` (§11.7, which the certificate "must record" as true or false).

**Decision needed.** Are these three added to Table C, or are the behaviors they gate — the ROBUST downgrade on illegal dependency, the contested-conflict disclosure, and the authenticity disclaimer — deleted?

**Recommended.** Add all three to Table C and `vocab.toml`. `illegal_dependency` is a safety gate, not cosmetics: dropping it lets a run whose derivation rests on an illegal transition be reported ROBUST, which is the failure mode §25.12.7 exists to make impossible.

#### `tid` as the fact key consumed by the kernel

**Tension.** §14.1 states "`tid` is the FactId key used by ECLIPSE leaves" and gives it the form `^blake3:[0-9a-f]{64}$`; §16.5's `R` component is 2 "if this transition's `tid` appears as a leaf in at least one corridor of Psi". Part II makes these two distinct concepts with different widths and opposite certificate eligibility: `TransitionId` is `tr:` h128, run-local, and §57.2 hard-rejects any h128 form appearing anywhere inside a certificate, while `FactHash` is `fh:` h256. No override mentions the identification.

**Decision needed.** Is a transition a fact, or does it produce one? If the latter, what is the normative mapping from `TransitionId` to `FactHash`, and what identifiers populate `invariant_U` and the corridor witness trees?

**Recommended.** State the mapping in `vocab.toml` — a transition produces exactly one fact whose payload is the transition's canonical bytes — so `tr:` stays run-local and only `fh:` reaches a certificate. Until that is written, §16.5's `R` component and §25.7's `invariant_U` have no well-typed content.

#### The `event_id` ban versus entity resolution and derivation

**Tension.** §57.11.4 forbids reading `event_id` "from any kernel, collector or checker code path", and `make lint-oracle-channel` "greps the kernel, collector and checker trees for `event_id` and fails on any hit outside the oracle crate". Part I keys reconstruction on EventId throughout: §12.4's resolver records `witness=e.event_id` on every union; §12.5's cardinality tie-break drops "the lexicographically larger witness `EventId`"; §12.7's alias rows carry `witness_event_id`; §9.4 and §9.8 store `evidence_ids[]` on entities and edges; §14.7 records the dropped `EventId` in the surviving transition's evidence; §14.8's rung 3 prefers "strictly more distinct `EventId`s".

**Decision needed.** Which source tree owns entity resolution and the derive step, and is every one of these witnesses re-typed to `RecordId`? §12.5's tie-break is determinism-affecting: ordering by RecordId instead of EventId drops a different union edge and yields a different entity table.

**Recommended.** Re-type every witness to `RecordId` and say so explicitly beside the §57.8 evidence override, then re-bless the §12 golden fixtures, because split/merge outcomes and `over_merge_rate`/`under_merge_rate` will move.

#### Table A's `owner` column versus Part I's own section numbering

**Tension.** §57.1 rule 3 requires every owner to resolve through `docs/section-index.toml`, with V3 failing on an unresolved owner, and §57.10's sample output claims "14 Part I, 9 Part II, 0 unresolved". But Part I is internally inconsistent about its own numbers: 04-state numbers the state model 13-16 while 07-replay calls the same content "section 17" (§22.3 "the security state (section 17)", §22.5 "one of section 17 dimensions", §22.7 "the transition registry of section 17"); 04-state calls the kernel "section 18" and the rule table "section 12", while 07-replay numbers the kernel 25 and 03-datamodel numbers entity resolution 12. Table A mixes both: dimension/state/transition are owned by §13 while tick and fact are owned by §17, and tick is actually defined in §14.4.

**Decision needed.** Which numbering does `section-index.toml` encode, and where does `Tick` actually live? Under either scheme at least one Table A owner resolves to the wrong section.

**Recommended.** Repair Part I's cross-references first, then regenerate the owner column from the corrected index. V3 currently passes only because `section-index.toml` does not yet exist.

#### `LicenseBasis = OBLIGATION` has no admissibility rule

**Tension.** Table C adds a third basis, `OBLIGATION`, to Part I's `Basis { Blind | Suppressed }` (§25.5). But Table A row 25 defines a license as "justified by a blind window", row 23 admits a silent instance "only inside a blind window", §25.6 C instantiates a silent instance "ONLY where `forall s in producing_sources(rule): !live(s, I)`", and §16.2 is explicit that "if at least one producing source was live, the outcome is `ILLEGAL/OBLIGATION_UNSATISFIED`" — which §16.2 calls "the single most important test in the suite".

**Decision needed.** Can an obligation license a silent instance over an interval in which a producing source was LIVE? If yes, §16.2's four-way branch and §11.6's `UNEXPLAINED_OBLIGATION` outcome are both wrong; if no, `OBLIGATION` is not a distinct basis.

**Recommended.** Remove `OBLIGATION` from `LicenseBasis` and keep obligation-forcing as a reason a Blind/Suppressed license is consulted, preserving §16.2's fail-closed branch. If it stays, it needs its own admissibility rule and a case in the Haskell differential oracle.

#### The stream concept has no canonical name

**Tension.** Part I's ordering, gap detection and tamper localization all rest on the stream: §11.2 "`(collector_id, stream_id)` defines an ordered sequence space" with a gapless `seq`; the evidence table's `UNIQUE (scenario_id, collector_id, stream_id, seq, content_hash)`; §11.5's localization tuple `(collector, stream, seq-interval, time-interval)` that the liveness pass consumes as `License { basis: Suppressed }`; §14.3's `seq_in_src` in `OrderKey`. Table A has no row for it, and Table D bans `stream` outright as a forbidden synonym for `source`. Check V7 would independently fail `stream_id` as an unregistered concept.

**Decision needed.** Is a stream a distinct concept that needs a Table A row and an ID type, or is `CollectorId`'s `@u16` suffix intended to be the stream/epoch with `stream_id` deleted? If deleted, what key replaces `(collector_id, stream_id, seq)` in the evidence uniqueness constraint and in the BLAKE3 chain construction?

**Recommended.** Add a `stream` row to Table A with its own ID and drop `stream` from the source synonym list. §11's entire integrity and SUPPRESSED-basis model is not expressible without it.

#### Table A's completeness versus check V7

**Tension.** §57.1 rule 1 says every concept has exactly one canonical name, and V7 fails the build on "any identifier segment appearing in >= 2 of the five language trees and >= 8 times total that is neither in `vocab.toml` nor in `vocab-allow.toml`". At least a dozen load-bearing Part I concepts have no Table A row: evidence chain, stream, stream epoch, adapter, alias, resolution state, snapshot, log epoch/reorg, watermark, obligation, guard AST, enforcement point, technique variant, trace, finding, and the ILLEGAL/POLICY_VIOLATING/ANOMALOUS classification.

**Decision needed.** Does every one of these get a Table A row before the lint becomes a required check, or does `vocab-allow.toml` cover them? §57.10 forbids an allow entry whose `paths` glob is "broader than one directory", which rules out allowlisting concepts that appear across all five trees.

**Recommended.** Extend `vocab.toml` with the missing concepts in the same change that lands §57, and run V7 as warn-only until the unregistered count reaches zero. Landing V7 as a required check against today's Table A blocks every merge.

#### The closed oracle set omits Part I's simulator cross-check

**Tension.** Table C declares `Oracle: range_reexec go_checker generator_ground_truth z3_test_only haskell_admissibility (exactly 5)`, closed. §25.12 defines six independent judges: `sim_kernel_agreement` (the §23 simulator versus the kernel, where "Disagreement is a P0 bug"), `brute_force_cross_check` (§24.8's sweep), `z3_oracle`, `haskell_admissibility_diff`, `degradation_invariant` against generator truth, and the Go checker. The simulator-versus-kernel gate maps to no OracleId unless `range_reexec` is meant to cover both it and the sweep.

**Decision needed.** Is the deterministic simulator an oracle with an OracleId? If `range_reexec` denotes §24.8's sweep, what identifies §25.12.1's agreement gate?

**Recommended.** Either add a sixth member or state in Table A row 37 that `range_reexec` subsumes both the sweep and the simulator. The parenthetical "exactly 5" should not be what silently drops a P0 gate from the oracle registry.

#### `adapter` and `collector` are one concept in Part II and two in Part I

**Tension.** §57's preamble says `adapter`, `parser`, `collector` and `shipper` "were used interchangeably" and that "Every such collision is resolved below", and Table D bans `source_adapter`, `log_parser`, `ingestor`, `shipper`, `agent` and `tailer` as collector synonyms. But Part I treats them as different things: §10.6 makes an adapter "a pure function `bytes -> Vec<CanonicalEvent> + Vec<NormalizationError>`" in the `spectra.adapters.*` package guarded by an import lint, while §11.2 makes a Collector "one process instance emitting one or more `stream_id`s" with a declared clock source and flush interval. Bare `adapter` is not in Table D, so `adapter_version` (a required `Source` field), `adapter_lossy` (an evidence column) and `adapters/<name>/map.toml` survive the lint only by omission.

**Decision needed.** Is bare `adapter` banned or permitted? If banned, Part I's pure normalization function loses its name and §10.1's import lint has nothing to guard; if permitted, the collision §57 claims to have resolved is still open and `adapter_version`/`adapter_lossy` remain a second name for collector-owned data.

**Recommended.** Keep them as two concepts and give `adapter` its own Table A row (the pure format-reading function) distinct from `collector` (the emitting process instance), rather than resolving the collision by deleting one side of it.

### SILENT

#### What one tick means

**Part I.** §14.4: "`tick` is a monotone integer, not a timestamp. Define `tick = floor((t_norm_ns - run_origin_ns) / tick_width_ns)`", with `tick_width_ns = 1_000_000` (1 ms) declared in `config/constants.toml` (§16.6). §23.2 uses a third unit: `tick_unit_s: 1`, "1 tick = 1 simulated second", exported by §23.8 as `2024-01-01T00:00:00Z + tick*tick_unit_s`.

**Part II.** §57.3.7: "`Tick` is `u64`, an integer count of nanoseconds since the scenario epoch (tick 0). All intervals are half-open `[t0, t1)`." Table A row 6 repeats "Integer nanoseconds since the scenario epoch; the only time quantity in the system." No `OVERRIDES` line is attached.

**Impact.** Every TTL, idle/absolute expiry deadline, blind-window bound, `horizon_ticks`, `burst_window_ticks`, `snapshot_interval_ticks` and `min_reorg_horizon_ticks` shifts by 10^6 (10^9 against the simulator). An implementer reading §14.4 builds a configurable 1 ms quantized clock; Part II fixes tick width at 1 ns and deletes the `tick_width_ns` constant. The half-open rule also silently contradicts §11.4's closed gap interval `[a.observed_at_ns, b.observed_at_ns]`, which is the interval that becomes a SUPPRESSED licensing basis.

#### Wall-clock values inside hashed payloads

**Part I.** §14.1 makes `wall_ns` a required field of the transition record and defines `tid = blake3(canonical_json(record minus {tid, seq, superseded_by}))`, so `wall_ns` is hashed into the transition's content address.

**Part II.** §57.3.7: "There is no floating point anywhere in the time model and no wall-clock value in any hashed payload."

**Impact.** Under §14.1 two byte-identical runs on different machines produce different `tid`s, quietly breaking the §15.6 determinism guarantee asserted a page later. Part II forbids it but never says it is fixing §14.1, so an implementer following the transition schema verbatim ships a non-deterministic fact key.

#### Canonical digest construction

**Part I.** Part I hashes five different ways: §9.3 `base32(BLAKE3_128(anchor_bytes))` over LF/US-delimited fields; §10.2 `event_id = "evt-" + base32(BLAKE3_128(RFC 8785 JCS JSON))`; §11.3 `chain_hash_0 = BLAKE3_256("spectra.chain.v1" || collector_id || stream_id || u64le(epoch))` (little-endian); §14.1 and §23.4 hash canonical JSON bodies; §23.5 `event_id = blake3(trace_root || seq || emit_index)[0..8]` (64-bit truncation).

**Part II.** §57.3: every digest is `BLAKE3-256("spectra/v1/" || kind || 0x1F || payload)`; payloads are built only from ASCII identifiers, fixed-width big-endian unsigned integers and `count:u32`-prefixed sequences — "No JSON, no floats, no locale-sensitive formatting, no platform-endian writes". Truncation is only ever the first 16 octets, for h128.

**Impact.** Every hash recipe in Part I is invalid: JCS-JSON payloads are banned, `u64le` is a little-endian write, the domain prefixes (`spectra.chain.v1`, `spectra/scenario/v1`) do not match `spectra/v1/<kind>`, and §23.5's 8-octet truncation is neither h128 nor h256. Every golden hash, `tests/golden/traces.json` entry and committed certificate fixture changes value, with no override telling the implementer to expect it.

#### EntityId format and the entity-kind closed set

**Part I.** §9.2 declares a closed set of 21 kind codes (`idn, acct, svcacct, cred, sess, tok, dev, host, ctr, proc, svc, api, res, role, grant, netif, flow, zone, ctl, src, col`) and says Principal is a union type, not a kind. §9.3: `EntityId := kind "-" b32`, b32 = 16 lowercase base32 chars of `BLAKE3_128(anchor_bytes)`; §10.2 enforces `^[a-z]{3,7}-[a-z2-7]{16}$`.

**Part II.** Table C: `EntityKind: user host process session credential key service account file netflow api_client resource (exactly 12)`, closed by §57.1 rule 6 ("New members are added in this section or not at all"). §57.3.6's SQL domain is `^en:(user|host|...|resource):[0-9a-f]{32}$`. Table A row 7 still names §9 as the owner and no override line mentions entities.

**Impact.** Nine Part I kinds (token, device, container, role, grant, zone, network endpoint, control instance, telemetry source, collector) have no Part II kind, and three Part II kinds (`key`, `file`, `api_client`) have no Part I anchor tuple. The wire form changes from `sess-k4m2q9x7t1b0dfe3` to `en:session:<32 hex>` — prefix, separator, alphabet and digest rendering all differ — invalidating §10.2's `EntityRef` pattern and §9.3's determinism gate. §57.2's ABNF also omits an `entity-id` production entirely, so `en:` is absent from the prefix-uniqueness check it declares a hard invariant.

#### The ten dimension names

**Part I.** §14.1's transition schema pins the dimension enum to `authentication, session, credential, privilege, device_trust, process, network_exposure, resource, service_identity, trust`, and §13.3 defines one FSM per name (AuthenticationState, DeviceTrustState, NetworkExposureState, ServiceIdentityState), with §13.5's coupling graph using the same names.

**Part II.** Table C: `Dimension: identity session credential privilege process network api service resource trust (exactly 10)`, closed; Table A row 8 defines a dimension as "one of the ten security dimensions, each owning one finite-state machine".

**Impact.** Part II silently adopts §10.2's event-level list and orphans §13's FSMs: `authentication`, `device_trust`, `network_exposure` and `service_identity` become illegal DimensionIds, while `api` becomes a dimension with no FSM, no transition table and no illegal-edge list. The generated Rust/Python/Go/TS enums, the `dimension` SQL type, every `st:` StateId and §13.5's declared couplings (`service_identity -> credential`, `network -> device_trust`) all reference names that no longer exist.

#### SourceId and CollectorId are authored, not content-addressed

**Part I.** §10.2 requires `source_id` to match `^src-[a-z2-7]{16}$` and `collector_id` `^col-[a-z2-7]{16}$` — content-addressed base32 digests, shown in §10.7 as `"source_id":"src-h2q9x7t1b0dfe3k4"`. §9.2 makes TelemetrySource (`src`) and Collector (`col`) entity kinds with anchor tuples, i.e. outputs of §12's resolver.

**Part II.** §57.2: `source-id = "src:" snake` and `collector-id = "col:" snake "@" u16` — symbolic, authored, human-written. Table A rows 4 and 5 make them first-class concepts owned by PART-II/ingest with their own ID types, not entity kinds.

**Impact.** Both worked examples in §10.7 become invalid, every event's `source` block changes shape, the `src`/`col` rows leave the entity table, and §12's resolver loses two kinds it was required to materialize. The `@u16` suffix has no Part I counterpart; §11.2's `stream_epoch` is the nearest concept and is not the same thing.

#### How an EventId is derived and how wide it is

**Part I.** §10.2: "`event_id` is content-addressed: `evt-` + base32(BLAKE3_128(canonical_json_without_event_id)) ... Two adapters that normalize the same record to the same canonical content produce the same `EventId`; this is what makes certificate leaf references stable." §10.5 says a schema migration re-derives `event_id`. §15.2 gives a second definition (`raw_event.event_id` = blake3-128 of raw bytes) and §23.5 a third (64-bit truncation of the trace root).

**Part II.** §57.2: `event-id = "ev:" h128` — 32 lowercase hex, no base32. Table A row 1: "An occurrence in the modeled system as the generator emitted it; ground-truth identity, never visible to the kernel." §57.8 depends on EventIds surviving degradation while RecordIds change.

**Impact.** The override covers only "evidence cites RecordId", not the ID's derivation or encoding. An implementer keeps §10.2's adapter-side content addressing, which makes EventId a function of the possibly corrupted ingested bytes — precisely the property §57.8's `oracle_link(event_id, record_id)` re-linking requires to be false, so the zero-false-ROBUST measurement silently stops working under the corrupt operator.

#### The raw-bytes digest: name, width, and certifiability

**Part I.** §11.3 `content_hash_n = BLAKE3_256(raw_record_bytes_n)`, stored as `evidence.content_hash` keyed by `event_id`; §15.2 separately stores `raw_event.event_id BYTEA PRIMARY KEY -- blake3-128 of raw bytes`; §10.6.1 computes `evidence.content_hash` "over the exact raw record bytes before any parsing".

**Part II.** Table A row 2: record = "One serialized telemetry line as ingested, digested over its exact pre-parse bytes"; `RecordId` = `rc:` h256 with `certifiable = true` (§57.9), stored as SQL `domain record_id` on table `record`; `row`, `log_entry`, `entry`, `message` and `raw_log` are banned synonyms.

**Impact.** Part I carries the raw-bytes digest twice, at two widths and under the wrong name; neither is a `rc:` value. The 128-bit `raw_event.event_id` would be a hard `spectra verify` rejection under §57.2's certificate width rule if it ever reached a certificate. An implementer following §11/§15 builds a `raw_event`/`evidence` pair rather than the `record` table Table B requires.

#### Identifier widths in code and storage types in SQL

**Part I.** §25.5 declares `FactId(u32)`, `EventId(u64)`, `LicenseId(u32)`, `Cut = u64`, `Clause(u64)`. §15.2's DDL stores `event_id BYTEA`, `tid BYTEA`, `chain_hash BYTEA`, `run_id UUID`, `entity_id BIGINT`, `license_id BIGINT`, and `dimension/from_state/to_state/trigger/support/classification` as `SMALLINT`. §10.2 requires `run_id` to match `^[0-9a-f]{32}$`.

**Part II.** §57.3.6: "In SQL, every identifier is `text` constrained by a `DOMAIN`, never `bytea`, never `uuid`", one DOMAIN per Table A row with an ID type. Table B requires `LicenseId([u8;32])`, `EventId([u8;16])`, `FactHash([u8;32])`, `RunId` = `run:` h256, `StateId` as text `domain state_id`, `Dimension` as a SQL enum type.

**Impact.** Every column in §15.2 changes type and every foreign key with it. `LicenseId` goes from a 32-bit run-local integer to a 256-bit certifiable ID, and `run_id` from a 32-hex/UUID value to `run:` + 64 hex, invalidating the required-field pattern on every canonical event in §10.2 and every fixture.

#### Severity

**Part I.** §16.5 defines severity normatively as a lexicographic tuple `Sev(x) = (K, D, R, E)` with a `CRITICAL/HIGH/MEDIUM/LOW/INFO` band table, a required doctest, `dimension.criticality` in `dimensions.toml` (§13.2) feeding `D`, and `GET /runs/{run}/findings?band=HIGH`. Its own gate (`test_no_aggregate_severity`) forbids only `risk_score`, `overall_severity`, `threat_level` and `confidence`.

**Part II.** §57.11.5: "Do NOT emit any field, column, JSON key, GraphQL field, metric name or UI label containing `score`, `confidence`, `probability`, `severity`, `risk`, `likelihood` or `priority`. There is no numeric grading anywhere in SPECTRA." Table D additionally bans `severity` as a forbidden synonym for `level` and in the universal ban list.

**Impact.** All of §16.5 becomes unbuildable: `Sev`, the band table, `/findings?band=`, `dimension.criticality`'s stated purpose ("used by section 16 severity") and the mandatory doctest all fail V5, which §57.11.8 says is a correctness defect with no waiver path. An implementer reading Part I alone ships a severity subsystem that cannot merge.

#### Table D bans required field names in the canonical event and control schemas

**Part I.** §10.2 makes `outcome` a required property of every canonical event, `stream_id` and `sensor_kind` required properties of `Source`, `actor` required for the session/api/resource dimensions, and `control_context` (items of type `ControlObservation`) required for `dimension=trust`; `ground_truth`/`GroundTruth` is the generator-only block. §22.5 makes `coverage_limits` and `bypass[].condition` required control-catalog keys; §23.2 makes `step` a required scenario key and §24.8/§24.9 expose `--axis`/`axes`.

**Part II.** Table D bans, at identifier-segment granularity: `outcome` (verdict), `stream` and `sensor` (source), `actor` and `principal` (entity), `observation` and `finding` (fact), `context` (run manifest), `truth` and `baseline` (oracle), `condition`, `status`, `mode`, `phase`, `posture`, `stage` (state), `step`, `action`, `change`, `edge` (transition), `coverage` (liveness), `path` and `route` (corridor), `axis` and `domain` (dimension).

**Impact.** Part I's own normative JSON Schemas, DDL, catalog schema and CLI cannot pass `make lint-vocab`: `outcome`, `actor`, `stream_id`, `sensor_kind`, `control_context`, `ControlObservation`, `ground_truth`, `coverage_limits`, `seed_domain`, `--axis`, `exe_path`/`normalized_path`/`path_template`, `status` (§9.5), `posture_max_age_s` (§22.6). Table A supplies no legal replacement name for most of them, so this is not a rename an implementer can perform mechanically.

#### Table D bans the evidence-chain and classification vocabulary

**Part I.** §11.3 defines `chain_hash`, `chain_prev` and `chain_checkpoints` as the integrity backbone, reused in §15.2's DDL and §23.4's trace records. §16.1 defines `POLICY_VIOLATING` as one of three disjoint classifications with `policy.toml`, the `classify::policy` module, `POL-*` ids and a required `edge:` key per rule; §16.1-16.5 make `finding` a first-class table and API resource; §11.4 defines `GAP_BEFORE` and gap counts; §11/§12 emit `ingest_report.json`, `integrity_report.json` and `resolution_report.json`.

**Part II.** Table D bans `chain` (hypothesis synonym), `policy` and `signature` (rule synonyms), `finding` (fact synonym), `gap`, `outage` and `hole` (blind-window synonyms), `edge` and `change` (transition synonyms), and `report`, `proof` and `attestation` (certificate synonyms), matched after splitting snake_case/PascalCase.

**Impact.** `chain_hash`, `chain_prev`, `chain_checkpoints`, `policy.toml`, `POLICY_VIOLATING`, `classify::policy`, `finding` rows and `/findings`, `GAP_BEFORE`, the `edge:` keys in §22.5 gates and §16.3 policy rules, §9.8's edge table, and every `*_report.json` producer are lint failures. Part II offers no canonical replacement for "policy", "chain" or "edge", so an implementer building §11/§16 to spec cannot merge.

#### What a transition is scoped to, and how its entity is written

**Part I.** §13.3.4 scopes PrivilegeState to `principal x scope`, §13.3.7 scopes NetworkExposureState to `host x interface`, and §13.3.10 scopes TrustState to an "ordered pair (zone|principal, zone|principal)". §14.1's transition record writes the entity as `^[a-z_]+:[A-Za-z0-9._@:\-]{1,128}$`, shown in §15.4 as `principal:svc-deploy`.

**Part II.** Table A row 10: a transition is "An evidence-bound change of one entity's state within one dimension at one tick", keyed by a single `EntityId`. §57.2 requires all identifiers be lowercase US-ASCII with no uppercase and no `@` outside `col:`/`lit:`/`sc:`.

**Impact.** Three of the ten FSMs have a composite subject that Part II's `(entity, dimension)` key cannot express, and `principal` is neither a Part I entity kind (§9.2 explicitly says it is a union type) nor a Part II EntityKind. An implementer following §14.1/§15.4 emits transitions whose `entity` field matches no ID domain in either part.

#### State identifiers: case and storage

**Part I.** All §13 state names are SCREAMING_SNAKE (`AUTHENTICATED`, `EXFIL_STAGED`, `ELEVATED_JIT`), printed that way in §15.4's mandatory CLI transcript and stored in §15.2 as `from_state SMALLINT` / `to_state SMALLINT`.

**Part II.** §57.2: "All identifiers are US-ASCII. Lowercase only." `state-id = "st:" snake ":" snake` (dimension ":" state). Table B binds state to SQL `domain state_id`, i.e. text.

**Impact.** Every state name must be lowercased and prefixed (`st:session:active`), changing the generated Rust `enum` and Python `StrEnum` variant spellings mandated by §13.2's codegen contract. §15.2's SMALLINT state columns must become text domains, changing indexes and the canonical CBOR snapshot encoding of §15.3.

#### Degradation operator names

**Part I.** §10.2's `Degradation.mutation` enum is `["none","delayed","duplicated","reordered","corrupted","suppressed"]` — past participles, with `none` as a member and no delete operator.

**Part II.** Table C: `Operator: delete delay duplicate reorder corrupt suppress (exactly 6)`, closed, with `OperatorId` = `op:` snake; Table D bans `noise`, `perturbation`, `mutation`, `fuzz` and `damage` as synonyms of degradation operator.

**Impact.** The event field name `mutation` is itself banned, every member's spelling changes, `none` has no OperatorId, and `delete` has no representation in the canonical event. An implementer following §10.2 emits enum values that fail the Operator domain and a field name that fails V5.

#### Scenario identifier grammar

**Part I.** §10.2 requires `scenario_id` to match `^[a-z0-9][a-z0-9_-]{2,63}$` (hyphens allowed, no version component), with `"scenario_id":"s07-token-pivot"` in the §10.7 worked example; §23.2 keeps the version in a separate `version: 1` key next to `id: sc_oauth_token_pivot`.

**Part II.** §57.2: `scenario-id = "sc:" snake "@" u16` where u16 is the scenario schema version, and `snake = lower *( lower / DIGIT / "_" )` — no hyphens, mandatory `sc:` prefix, mandatory version suffix.

**Impact.** Both `s07-token-pivot` and `sc_oauth_token_pivot` are invalid. Because §9.3 anchors every `EntityId` on `scenario_id`, changing its spelling changes every entity digest in every fixture, and §23.2's separate `version` key becomes a second source of truth for the same value.

#### Certificate flag name for ambiguous entity resolution

**Part I.** §12.6: "A derivation whose leaves include an unresolved entity is marked `ambiguous_entity` in the certificate flags, and such a run may not be presented as ROBUST without that flag shown."

**Part II.** Table C's closed `Flag` set contains `er_ambiguous` and no `ambiguous_entity`; §57.1 rule 6 closes the set.

**Impact.** A silent rename of a certificate JSON key. An implementer following §12.6 emits a flag that fails the closed-enum check, and `spectra verify` sees an unknown flag on exactly the runs Part I says must not be shown as ROBUST without it.

### RESOLVED

#### `atom` retired (§57.4 row 14, §57.8, §57.9 [[retired]], check V6)

**Part I.** §22.2 compiles "threshold atoms x_{k,l}" with budget error `E_ATOM_BUDGET`; §25.5 declares `pub struct FactId(u32); // ground, time-indexed atom`; §25.3 lists `goal.toml` as carrying the "goal atom"; §13.3 says "`Fact` = the time-indexed atom emitted"; §25.7's certificate cut is `["x_session_binding_2","x_egress_seg_1"]` and §24.7's CLI prints `atoms [x_session_binding_1, x_session_binding_2]`.

**Part II.** Table A row 14 marks `atom` RETIRED and bans it outright; §57.8 renames FactId's comment to "fact", "atom set A" to "literal set L", `Cert.cut: Vec<Atom>` to `Vec<LiteralId>`, and goal.toml's "objective atom" to "goal fact". §57.9 says `[[retired]]` entries have "no allowlist path".

**Impact.** Every Part I identifier containing `atom` fails `make lint-vocab` V6: the atom table in `build/controls.meta.json`, `AtomSet`, `E_ATOM_BUDGET`, the `atoms` field in trace records (§23.4/§24.7) and the `x_*` strings in the certificate `cut`. An implementer following §25.7 emits a certificate whose `cut` is a list of atom-name strings; Part II requires `lit:` LiteralIds.

#### Evidence leaves are RecordId, not EventId (§57.8)

**Part I.** §25.5: `RuleInst { ... evidence: Vec<EventId> }` and `License { ... witness: Vec<EventId> }`; §11.1 "a rule instance whose `evidence` vector references an `EventId` with no evidence row is rejected by the kernel and by the independent Go checker"; §25.7's certificate carries `"witness":["ev_000102","ev_000188"]`; §25.8(e) requires witnesses to "re-derive goal from real `EventId` leaves"; §25.11 exposes `GET /frontier -> [{..., evidence:[EventId]}]` and `/counterexample/{atom} -> derivation tree with EventId leaves`; §15.2 defines `transition_evidence(seq, event_id)`; §14.1 transition `evidence` items match `^ev:[0-9a-f]{32}$`.

**Part II.** §57.8: `RuleInst.evidence: Vec<EventId>` becomes `Vec<RecordId>` and every witness-tree leaf is a `RecordId`. `EventId` is the generator's private identity carried only on the oracle channel; §57.11.4 forbids putting an `EventId` in a bundle, fact, rule instance, license, witness tree or certificate, and `make lint-oracle-channel` fails on any `event_id` outside the oracle crate.

**Impact.** The kernel, the Go checker, the certificate schema, the evidence table and four HTTP endpoints all change their leaf identifier type from `ev:`-h128 to `rc:`-h256. §57.2's certificate width rule additionally makes any `ev:` value inside a certificate a hard rejection by `spectra verify`, so a Part I certificate built to §25.7 is rejected outright rather than merely deprecated.

#### `Cert.mode` split into independent `safety` and `minimality` (§57.6)

**Part I.** §25.7's certificate has a single `"mode": "ROBUST"` field (`ROBUST | OPTIMISTIC_ONLY | UNSAFE`); §25.9 downgrades a flagged run by returning `mode: "OPTIMISTIC_ONLY"` with `downgraded_by: ["grounding_capped"]`, and folds subset-minimality into the same field via the `subset_minimal_only` flag.

**Part II.** "OVERRIDES Part I / ECLIPSE §5: `Cert.mode: ROBUST|OPTIMISTIC` is deleted. A certificate carries independent `safety` and `minimality` fields plus a scope binding", with `Safety: ROBUST OPTIMISTIC_ONLY UNSAFE` and `Minimality: EXACT SUBSET UNVERIFIED` as separate closed enums.

**Impact.** §25.9's downgrade rule is no longer expressible: a cardinality-uncertain but genuinely robust run must now report `safety=ROBUST, minimality=SUBSET` rather than `mode=OPTIMISTIC_ONLY`. An implementer following §25.9 suppresses honest ROBUST safety results for unrelated minimality reasons — exactly the defect §57.6 names.

#### A verdict may never be rendered as a bare word (§57.6)

**Part I.** §25.8's checker transcript ends `VERDICT ROBUST 11ms`; §25.11's UI result header reads `... — ROBUST — 6 corridors — blake3:3f9a...`; §25.9's API returns `mode: "OPTIMISTIC_ONLY"`. Both transcripts are stated as output that must work verbatim.

**Part II.** "a verdict is never rendered as a bare word. The only renderable form is `ROBUST(rules@<16hex>, catalog@<16hex>, licenses@<16hex>, non-adaptive) / minimality=SUBSET`". No code path may build the string by concatenation; `spectra verify` rejects any certificate whose verdict lacks a complete scope binding.

**Impact.** The literal CLI and UI strings in §25.8 and §25.11 become invalid output. Each language needs one verdict-rendering function, and the certificate must carry a rules/catalog/licenses scope binding that §25.7's `hashes` block does not provide under those names (it has `controls`, not `catalog`).

#### Blocker bit positions are derived from the catalog, and masks are never shown (§57.8)

**Part I.** §22.2/§22.3 have the controls compiler emit threshold atoms and lower `admit_when` into `blockers` masks, with §22.7 committing the atom table in `build/controls.meta.json` as the authored ordering. §25.7's certificate publishes `"psi": [{"mask":"0x0000000000000024","corridor_id":3}]`, and §25.11's `GET /api/v1/eclipse/corridors` returns `[{corridor_id, mask, atoms, witness_tree_url}]` to the UI.

**Part II.** §57.8: bit `i` is the `i`-th LiteralId in the total order (ControlId bytewise ascending, then Level ascending), so a catalog edit renumbers bits. "masks are never compared across two different `catalog_hash` values, no mask is ever printed in a user-facing artifact, and every certificate records both the `catalog_hash` and the explicit ordered `Vec<LiteralId>`"; §57.11.6 repeats the display ban.

**Impact.** The `mask` field must disappear from the certificate's `psi` entries and from the corridors API, replaced by an ordered `Vec<LiteralId>` plus `catalog_hash`. Part I's certificate has no `catalog_hash` field at all, so a §25.7-shaped certificate cannot satisfy the cross-catalog comparison rule.

#### `residual reachability` retired as a name and as a quantity (§57.7)

**Part I.** §25.6 H: the cost frontier "yields the exact Pareto set of `(declared_cost, residual_reachability)`, each point annotated with its cut and the `EventId`s of the evidence"; §25.11 exposes `GET /api/v1/eclipse/frontier -> [{cost, residual, cut, evidence:[EventId]}]`.

**Part II.** "OVERRIDES Part I / ECLIPSE §4H: `residual reachability` is retired as a name and as a quantity. The frontier reports two sets — `residual_goal_facts: Vec<FactHash>` and `open_corridors: Vec<CorridorId>` — and nothing collapses them into a scalar. The lint bans the old name outright."

**Impact.** The knapsack DP's objective changes from a scalar to two sets, so §25.6 H's Pareto ordering has to be redefined (there is no total order on set pairs). The `residual` field in the frontier API is a lint failure and must be replaced by the two vectors.

## 58 Determinism charter

### UNRESOLVED

#### Exact-duplicate records: suppressed at ingest or retained as distinct events

**Tension.** Part I §14.6/§14.7 make exact-duplicate suppression mandatory and lossy: `dedup_key = blake3(source_id || seq_in_src || canonical_bytes(record))` is stored in `ingest_seen` with a unique index, a second insert is a no-op incrementing `ingest_dup_count`, and exact duplicates are "Dropped, counted in `dup_exact`"; §44.2 asserts `duplicates_suppressed == len(B)` on re-ingest and that "a replayed identical record IS collapsed", with the hypothesis property "the resulting event set equals `set(records)`". Part II §58.3(4) instead assumes both copies survive into the order: reaching component 5 (`line_ordinal`) "between two distinct events" emits `DUP_EVENT_SAME_KEY` into the run manifest "with both `EventId`s", explicitly "not an error (exact duplicates are a declared degradation operator)", and the manifest publishes a `dup_event_same_key` count; §58.5(3) likewise says "duplicates are retained before sorting". Part II never mentions `dedup_key`, `ingest_seen` or `dup_exact`.

**Decision needed.** Does exact-duplicate suppression happen before EventKey assignment (in which case `line_ordinal` is dead code, `DUP_EVENT_SAME_KEY` can never fire, and Part II's diagnostic and counter should be deleted), or do duplicates survive into the ordered event stream (in which case Part I's `dedup_key`/`ingest_seen` table, `dup_exact` counter and the §44.2 `set(records)` property must be rewritten)? Whichever is chosen, the degradation harness's duplicate operator and every evidence-count assertion change.

**Recommended.** Keep the Part I dedup at ingest, since it is load-bearing for re-ingest idempotency and for the §20 degradation matrix, and redefine Part II's `line_ordinal` as a pure determinism backstop over the pre-dedup bundle with `DUP_EVENT_SAME_KEY` reporting only records that survive dedup with colliding keys (i.e. semantic near-duplicates).

#### Rank-based EventIds are incompatible with the metamorphic invariance tests

**Tension.** Part II §58.3(3) makes `EventId` the 0-based rank of an event in the whole-bundle order, so inserting or deleting any record renumbers every later event. Part I §44.8 requires `test_noise_invariance`: append N synthetic events from entities disjoint from the incident and "verdict, cut `S`, corridor set `Psi` and `trace_hash` of the proof segment unchanged"; and `test_irrelevant_event_removal`: delete an unused event and the "chain, cut and verdict unchanged". Certificates, witness trees and evidence arrays cite EventIds, so under ranking the proof-segment trace hash necessarily moves when noise is appended. Part II never mentions §44.8.

**Decision needed.** Either (a) EventIds go back to content addresses (as §17.1.3 specifies) so they are insertion-stable, or (b) §44.8's invariance relation is weakened to "unchanged after canonical renumbering" / "unchanged modulo the EventId relabeling bijection" and the proof-segment trace hash is computed over content hashes rather than ranks. This has to be settled before the certificate schema is frozen.

**Recommended.** Keep content-addressed EventIds for anything a certificate cites and use the §58.3 rank only as an internal dense index that is never serialized; that preserves both the §58.3 shuffle gate and the §44.8 metamorphic properties.

#### Two competing run identities: trace_hash vs run_id and stage digests

**Tension.** Part I §44.1 defines `trace_hash = BLAKE3(canonical_json(manifest) || canonical_json(control_config) || 0x1e || concat over steps in emission order of step_index || step_kind || canonical_json(step_payload_without_wallclock))` as "the identity of the run", requires the certificate to record it, and §44.1(7) asserts the recorded value equals an independently recomputed one. Part II §58.9 defines `run_id = blake3(canonical(manifest.inputs))[0..16]` and §58.10(5) defines a chain of stage digests S0..S6 ending in `cert_blake3`; neither mentions `trace_hash`, and §58.9's manifest schema has no field for it.

**Decision needed.** Does the certificate still carry `trace_hash`, and if so what is its relationship to `run_id` and to S6 `cert_blake3`? Note the two are not interchangeable: `run_id` is a function of inputs only, while `trace_hash` is a function of emitted steps, so `run_id` is knowable before the run and `trace_hash` only after. Also: §44.1 hashes `canonical_json(manifest)` wholesale, which under §58.9 would pull in the `environment` block that §58.12(8) forbids hashing.

**Recommended.** Keep `run_id` as the input fingerprint, redefine `trace_hash` as the replay-simulator stage digest so it slots into the S0..S6 chain, and state explicitly that it is computed over the `inputs` block only, never the whole manifest.

#### Clock-skew normalization: is EventKey.t_nanos raw or normalized, and where did skew.json go

**Tension.** Part I §14.5 mandates a deterministic skew-normalization pass — Bellman-Ford over a difference-constraint graph, per-source offsets `off(s)` from shortest-path potentials "rounded to whole ticks toward zero", `t_norm = t_raw + off(s)` — and §14.5(5) requires writing `skew.json` and "hash it into the certificate alongside `liveness.json`". `t_norm` is then used for dedup (`t_norm_tick`), for the watermark (§14.9) and for implausible-future detection. Part II §58.3(1) says EventKey component 1 is "`t_nanos` ... ascending, raw nanoseconds (NOT the tick)", and §58 nowhere mentions skew offsets, `t_norm` or `skew.json`: it is absent from the manifest's `inputs.files`, absent from `outputs`, and absent from the S0..S6 stage-digest chain (which goes ingest -> er -> liveness -> grounding -> psi/cut -> cert).

**Decision needed.** Is the `t_nanos` that fixes the total order the asserted timestamp or the skew-normalized one? And is skew normalization a stage that gets its own digest and a hashed `skew.json` (per §14.5), or has it been absorbed into S0/S2? Relatedly: `sources.toml`, which declares `max_skew_ms` and the `volatile` field list that both feed this pass, does not appear in Part II's hashed `inputs.files` list.

**Recommended.** Order on normalized time, insert an explicit skew stage between S0 and S1 with its own digest, add `skew.json` to `outputs` and `sources.toml` to `inputs.files`; otherwise two runs differing only in `sources.toml` share a `run_id` while producing different certificates.

#### Cap configuration: limits.toml vs budgets.toml, and the caps Part II drops

**Tension.** Part I §13.x: "Grounding is bounded by horizon `k` from `goal.toml` and by hard caps `max_entities`, `max_facts`, `max_rule_instances` in `limits.toml`. When a cap binds, set `flags.grounding_capped = true`." Part II §58.6 puts all budgets in `budgets.toml` (hashed into the certificate) under different names and a different unit of account — `[grounding] rule_instances_max`, `derivation_steps_max`, `frontier_bytes_max`; `[fixpoint] propagations_max`; `[hitting_set] corridors_max`, `bnb_nodes_max`, `fixpoint_calls_max`; `[liveness] constraint_relaxations_max` — with no `max_entities` and no `max_facts`. §58.6's override line names "Part I's §6/§4B caps", which does not obviously refer to §13.x's `limits.toml`.

**Decision needed.** Does `limits.toml` still exist alongside `budgets.toml`, or is it folded in? Are `max_entities` and `max_facts` still enforced caps (they are entity/fact-count bounds, not step counts, so they do not fit Part II's step-budget model), and if a cap is dropped, what now bounds grounding by entity count? Only `budgets.toml` is in the hashed `inputs.files` list, so a surviving `limits.toml` would be an unhashed input that changes output.

**Recommended.** Fold `limits.toml` into `budgets.toml` as a `[grounding] entities_max` / `facts_max` pair counted the same way as the other budgets, delete `limits.toml`, and keep `flags.grounding_capped` wired to any `[grounding]` budget exhaustion.

#### Whether the manifest's inputs.files list is exhaustive

**Tension.** Part II §58.9(1) defines `inputs` as "everything that may affect output. Hashed. `run_id` and every certificate hash derive from this block alone", and the schema lists exactly nine files: `bundle.jsonl`, `rules.toml`, `controls.toml`, `costs.toml`, `goal.toml`, `scenario.toml`, `seeds.toml`, `budgets.toml`, `er-config.toml`. Part I declares several other hand-edited files that demonstrably change output: `sources.toml` (skew envelopes, lateness bounds, volatile fields — §14.5, §14.9, §17.1.4), `dimensions.toml` (the state enums, coupling graph, decay kinds, restrictiveness order — §13.2, §14.8, §14.10), `engine.toml` (§17.1.6), `limits.toml` (§13.x), `config/constants.toml` (§16.6), `artifacts.toml` (§19.2.1), and the `rules/**.yaml` authoring sources plus `rules/obligations/*.yaml` (§17.6.4, §18.0.2).

**Decision needed.** Is the nine-file list normative and closed, or illustrative? If closed, every omitted file either must be proven output-irrelevant or merged into a listed file; if illustrative, the spec must say so, because as written two runs that differ in `sources.toml` or `dimensions.toml` produce the same `run_id` while producing different certificates — which defeats the content-addressing claim in §58.9 and the forbidden-claims discipline in §58.13.

**Recommended.** Declare the list closed and add `sources.toml`, `dimensions.toml`, `constants.toml`, `artifacts.toml` and a single rolled-up digest of `rules/**` (alongside the existing `rules.toml` `ast_blake3`); add a gate that fails if any file read by a decision path is absent from `inputs.files`.

#### CI surface: a closed workflow set and an audited required-checks list vs two new mandatory jobs and a self-hosted runner

**Tension.** Part I §46.1 says "Create exactly these files under `.github/workflows/`" and enumerates nine; §46.4 fixes the branch-protection required-check list and adds `tools/ci/verify_required_checks.py`, "which queries the GitHub API and fails if the configured list drifts from the document" (`docs/ci/required-checks.md`); every job in §46.2 runs on GitHub-hosted `ubuntu-24.04`. Part II §58.11(3)-(4) requires `repro-check` on every push and blocking for merge, `repro-matrix` over three environments nightly and on every tag and blocking for a release tag, and `make lint-determinism` blocking on every push; §58.10(1) makes the `wsl2` environment — "self-hosted, the author's machine" — mandatory, "not optional".

**Decision needed.** Which existing workflow hosts `repro-check`, `repro-matrix` and `lint-determinism`, or is a tenth workflow file added (which §46.1's "exactly these files" forbids)? And `docs/ci/required-checks.md` plus branch protection must be amended in the same change or `verify_required_checks.py` goes red. Separately, Part I's CI model (`permissions: contents: read`, no secrets on fork PRs, all hosted runners) has no provision for a self-hosted Windows/WSL2 runner, which is a different trust boundary.

**Recommended.** Add one `determinism.yml` workflow, amend §46.1's list and `docs/ci/required-checks.md` in the same commit, and restrict the self-hosted `wsl2` runner to non-fork triggers (nightly and tag) so it never executes fork PR code.

#### make reproduce vs make repro-check / repro-matrix

**Tension.** Part I §4.1 defines `make reproduce` ("run full pipeline twice in fresh containers, diff all artifact hashes", < 30 min, exit 0 means byte-identical), §4.4(3) requires it to produce identical hashes for `cert.json`, `liveness.json` and every `artifacts/**` file, and the §4.7 Definition-of-Done checklist has the line "[ ] make reproduce yields byte-identical artifacts across two fresh containers". §2.4(1) also names `make reproduce` as the enforcement of byte-identical output. Part II §58.10's override line asserts "reproducibility was asserted and tested nowhere" and introduces `make repro-check` (two runs on one machine with perturbed non-semantic conditions) and the `repro-matrix` CI job, never mentioning `make reproduce`.

**Decision needed.** Does `make reproduce` survive as a distinct target, become an alias for `repro-check`, or get deleted — and which target satisfies the DoD checklist line and §4.4(3)? They are not equivalent: Part I's runs are in two fresh containers and diff all `artifacts/**`; Part II's run B is the same machine with a different TMPDIR, TZ, thread count and shuffled bundle, and diffs stage digests plus the manifest's `inputs`/`caps_hit`.

**Recommended.** Keep `repro-check` as the per-push gate, redefine `make reproduce` as the fresh-container pair required by §4.4(3) (it tests something `repro-check` does not), and update the DoD checklist to require both plus the latest green `repro-matrix` artifact id that §58.13(1) makes the README cite.

#### Property-test randomness sits outside the seed registry

**Tension.** Part I §44.11 requires "Do NOT use randomness without a recorded seed. Every property test prints its seed; CI exports `HYPOTHESIS_SEED`, `PROPTEST_CASES` and `QUICKCHECK_SEED` into the job summary", and §43.4 builds fixtures with `spectra fixtures build --seed 0xSPECTRA`; §44.4 generates 10,000 cases per run with hypothesis, §44.5 uses FsCheck, §44.6 drives RTL with randomized sequences. Part II §58.8(2) permits only ChaCha20 seeded from the registry and bans "`rand::thread_rng`, `math/rand`, `random.*` module-level functions, `Math.random`, `numpy.random.seed` legacy global state, and any RNG whose stream is not specified by a public algorithm"; §58.8(4) requires that "every consumer that draws a random value must appear in `seeds.toml`" with a gate that fails on an unregistered consumer; §58.12(7) repeats it. The registry does list test-side consumers (`kernel.config_sampler` pointing at `crates/kernel/tests/configs.rs`, `fuzz.guard_differential`), so "consumer" is clearly not limited to production code — yet hypothesis, proptest, FsCheck and QuickCheck all use their own unregistered PRNGs seeded from env vars.

**Decision needed.** Are property-test frameworks in scope of the seed registry? If yes, either their seeds must be derived from `root_seed` via registered consumer ids (replacing the `HYPOTHESIS_SEED`/`PROPTEST_CASES`/`QUICKCHECK_SEED` env-var scheme) or the frameworks must be replaced by ChaCha20-driven generators. If no, §58.8(4) and §58.12(7) need an explicit carve-out naming the frameworks, or the registry gate will either fail the build or, worse, pass while a whole class of RNG use goes unregistered.

**Recommended.** Carve out test-harness generators explicitly: they do not write hashed artifacts, so they are not decision paths. Register only the samplers whose draws reach a fixture or a certificate (`generator.*`, `degrade.*`, `kernel.config_sampler`), and keep the env-var seed reporting from §44.11 for the frameworks, with a gate that the env vars are echoed into the job summary.

### SILENT

#### The total order on events and the meaning of EventId

**Part I.** §17.1.3: "order_key(e) = (t_evt(e), source_id(e), seq(e), event_id(e))" — a 4-tuple — and "`event_id` is the 16-byte BLAKE3-128 content address from section 8, so the order is total even for byte-distinct records sharing all three prior fields." `source_id` is TEXT in the §3.1 DDL and the §3.1 transition schema constrains evidence ids to `^ev_[0-9a-f]{16}$`.

**Part II.** §58.3 defines `EventKey` as a 5-tuple (t_nanos, source_id as `[u8;32]` BLAKE3 of the source name ordered byte-lexicographically, seq with `SEQ_ABSENT = u64::MAX`, content_hash as BLAKE3-256, line_ordinal in `bundle.jsonl`), and `EventId` is "the 0-based rank in this order, computed after the whole bundle is read ... not an ingest counter, not a database sequence, and not stable across bundles." §58.3 carries no "OVERRIDES Part I" line.

**Impact.** Two incompatible orderings and two incompatible EventId types. Ordering by TEXT `source_id` (Part I) and by BLAKE3(source name) (Part II) produce different permutations for the same bundle, hence different EventId assignment, different fact base, different certificate. And EventId is a content address in Part I (stable, 16 hex chars, matches the `ev_` schema pattern) but a dense integer rank in Part II (unstable across bundles, does not match the schema pattern). An implementer reading only Part I builds content-addressed ids and the §58.3 shuffle gate, the `DUP_EVENT_SAME_KEY` diagnostic and the `line_ordinal` tie-break have nothing to attach to.

#### Derived identifiers: content addresses vs rank of a canonical key

**Part I.** §17.2.1 facts are "interned to a `FactId(u32)`"; §19.3's normative edge record uses content-addressed identifiers — `"edge_id": "ed:4b9f0c1a77e2d5386a10bb94cf2d73e1"`, `"instance_id": "ri:8f2c11a0d4b76e590cc3a21ff4470b6d"`, `"event_id": "ev:7a1c93f0..."`, `"license_id": "lc:11c4"` — stored as BYTEA primary keys in the §19.3 DDL; §3.1 constrains `transition_id` to `^tr_[0-9a-f]{16}$`.

**Part II.** §58.3(5): "every identifier is the rank of a canonical key, never an allocation counter" — `FactId := rank of (tick, predicate_id, arg0..arg3)`, `RuleInstId := rank of (rule_id, head_fact, body_facts_sorted, silent_license_or_MAX)`, `LicenseId := rank of (source_id, t0, t1, basis_tag)`, `CorridorId := rank of the corridor's blocker mask`. No override marker.

**Impact.** Interning (Part I, first-appearance order) and ranking (Part II, sort-order) give different FactId values; content-addressed `ri:`/`lc:`/`ed:` identifiers are fixed-width hashes, ranks are small dense integers. The §19.3 JSON shape, the BYTEA primary keys, the `tr_`/`ev_` regex patterns and the Go checker's parsing all change. An implementer who builds §19.3 as written produces a hypergraph the §58.3 discipline rejects.

#### Timestamp origin: absolute Unix epoch vs scenario-relative, and TickId width

**Part I.** §2.4(4): "timestamps inside artifacts are scenario-relative, not wall-clock"; §3.1's normative transition schema (from which the Pydantic, Rust and TypeScript types are generated) declares `"t": {"type":"integer","description":"scenario-relative microseconds"}`; §3.5's `License` struct carries `interval: (Micros, Micros)`.

**Part II.** §58.1: the one physical timestamp type is `TsNanos` = i64 nanoseconds since 1970-01-01T00:00:00Z, clamped to [0, 4102444800000000000) (1970 to 2100), with out-of-range records quarantined as `TS_OUT_OF_RANGE`. The §58.1 override line binds only "sections 17-19 (temporal) and 25 (kernel)"; it does not name §2, §3 or §13-16.

**Impact.** Microseconds vs nanoseconds and scenario-relative vs absolute-epoch are both unresolved for the schema that generates the types in three languages, and for the License interval. Worse, the combination is unimplementable: §58.2(4) fixes `TickId` at u32 while §58.2(3) computes `TickId((t.0 / tick_nanos) as u32)` from absolute epoch nanos — at the committed default `tick_nanos = 1_000_000` a 2026 timestamp gives ~1.77e12 ticks, which silently wraps a u32 (max ~4.29e9, i.e. only ~49.7 days of millisecond ticks). Part I's scenario-relative convention is exactly what made the u32 tick (and §17.2.1's `tick: u32`) viable, and Part II revokes it without saying so.

#### Canonical JSON encoding of hashed artifacts

**Part I.** §44.1: "Canonical JSON: UTF-8, sorted keys, no insignificant whitespace, integers only (no floats; fixed-point millis for time), `\u` escapes uppercase."

**Part II.** §58.9(2) SCJ: "UTF-8 without BOM; object keys sorted byte-lexicographic; no insignificant whitespace; `\n` as the only line terminator and exactly one trailing `\n`; ... minimal escaping (`"` `\` and C0 only, lowercase `\u00xx`); all integers emitted as decimal strings". The §58.9 override line covers only host/toolchain provenance and hash exclusion, not the encoding.

**Impact.** Three byte-level contradictions in the serializer that defines every hash: uppercase vs lowercase `\u` escapes, JSON numbers vs decimal strings for integers, and fixed-point milliseconds vs TsNanos nanoseconds for time. An implementer following §44.1 produces artifacts whose bytes differ from the §58.9 writer for the same data, so `tests/scj/` cross-language conformance, `make test-golden` byte diffs, the stage digests and the Go checker's re-serialization all fail against each other. This is the single highest-blast-radius silent conflict.

#### Ingest time (t_ing) requires a system-clock read that feeds hashed bytes

**Part I.** §17.1.2 mandates carrying three independent clocks per record and never collapsing them, including `t_ing` = "instant SPECTRA durably received the record", trust high; §13.x negative requirements say "No wall-clock reads outside the ingest boundary" — i.e. the ingest boundary may read the host clock.

**Part II.** §58.1(5): "No component may read the system clock inside a decision path. The only permitted clock reads are: (a) the run manifest's `environment.started_at_wall`, which is excluded from every hash; (b) benchmark timers in the bench harness." A lint fails the build on `SystemTime::now`, `time.Now`, `datetime.now`, `Date.now`, `clock_gettime` outside `tools/lint/clock-allowlist.txt`. §58.12(1) repeats the ban. §58.1(2) forbids "monotonic clock readings" as stored or hashed time.

**Impact.** Ingest is squarely a decision path under §58's own definition: the record it writes feeds `content_hash`, which is EventKey component 4, which fixes EventId ranks and therefore the certificate. Part II's permitted-clock-read list has no entry for ingest, and `t_ing` is never mentioned anywhere in §58. An implementer who builds the three-clock record per §17.1.2 trips the §58.6/§58.12 lint, or, if they allowlist ingest, puts a host-clock value inside a hashed artifact.

#### Granularity-sensitive (time-fragile) rules: rejected at load vs allowlisted

**Part I.** §17.10 G17.5: "Δ sensitivity documented: running at Δ and Δ/2 must not change any `OBSERVED` verdict; if it does, the rule is time-fragile and is rejected at load with `V19`." §18.1 offers a per-rule `flags: time_fragile_ok` field as the only opt-out.

**Part II.** §58.2(6): granularity-invariance is required only "for every rule whose guards contain no window shorter than 2 ticks at the coarser granularity. Rules that do contain such a window are listed in `rules/granularity-sensitive.txt`, must carry a written justification, and the test asserts exactly that list." The §58.2 override line claims only that Part I "left the index unspecified".

**Impact.** Two different regimes with two different mechanisms. Part I rejects a time-fragile rule at load time with diagnostic V19 unless the rule's own YAML carries `time_fragile_ok`; Part II admits it as long as it appears in a separate committed text file. An implementer must choose whether the exemption lives in the rule file or in `rules/granularity-sensitive.txt`, and whether V19 still fires. Part II also tests at 1_000_000 vs 1_000 (1000x) rather than Part I's Δ vs Δ/2.

#### Whether a timeout can appear as a certificate flag

**Part I.** §47.6(6): "Degradation is always visible: any run that hit a cap, a timeout, a voided license, a dead-lettered record or a partial source appears with those flags in the API response, in the certificate, and in the UI header."

**Part II.** §58.6(5): wall-clock is measured "purely as an operational signal" in the unhashed `environment` block; exceeding `soft_deadline_seconds` prints a warning and the process "may not abort, because aborting on time is a wall-clock decision"; "CI kills runaway jobs at the job level, and a job killed that way is a red build, not a flagged certificate." No override marker covers §47.

**Impact.** Part I's degradation contract enumerates a timeout flag as a required, renderable certificate state; under Part II no such state can exist, because nothing may abort on time and nothing time-derived may be hashed. An implementer building the §47.6 flag set adds a `timeout` flag to the certificate schema that the §58.9 hashing rules make either unproducible or non-reproducible.

#### Crate names the determinism lints are scoped to

**Part I.** §1.5 declares the Rust workspace crates as `eclipse-kernel`, `eclipse-rules`, `spectra-replay`, `spectra-state`; §13.x scopes the existing lint as "`clippy.toml` denies `std::collections::HashMap` in `spectra-state` and `spectra-eclipse`", and §44.5/§13.2 generate into `crates/spectra-state/` and `crates/eclipse-kernel/`.

**Part II.** §58.4's committed `clippy.toml` is headed "# applies to spectra-kernel, spectra-ground, spectra-cert"; §58.8(5) asserts "`crates/kernel` links no RNG crate at all"; §58.4 also refers to "decision crates" generically.

**Impact.** None of `spectra-kernel`, `spectra-ground`, `spectra-cert` or `crates/kernel` is a crate Part I declares. As written, the §58.4 disallowed-types config and the §58.8(5) RNG gate would be scoped to packages that do not exist, so they silently pass while `eclipse-kernel` and `spectra-state` go unchecked. Part I's own `spectra-eclipse` scoping is also dropped without comment.

### RESOLVED

#### Tick granularity: definition, config file, and default value

**Part I.** §17.1.6: derived facts are indexed at a tick granularity Δ declared in `engine.toml`, default 1_000_000_000 ns (1 s); `tick(t) = t / Δ` floor; Δ is hashed into the certificate and changing Δ changes `rules_hash`.

**Part II.** §58.2 (marked "OVERRIDES Part I: 'time-indexed fact' is now defined"): `tick_nanos` is declared in `scenario.toml`, must parse as exactly one of {1_000, 1_000_000, 1_000_000_000}, default committed for fixtures is 1_000_000 (1 ms), hashed into the certificate; rank discretization forbidden; `TickId` is u32 and the horizon `k` in `goal.toml` is measured in ticks.

**Impact.** The override is explicit, but it silently relocates the knob (`engine.toml` -> `scenario.toml`) and changes the default by 1000x (1 s -> 1 ms). An implementer who builds `engine.toml` per Part I ends up with a config file that Part II's manifest `inputs.files` list never hashes, so a Δ change would not alter `run_id`. Part I's continuously-valued Δ must also be narrowed to the three-value enum.

#### Floating point: allowlisted exception vs absolute ban

**Part I.** §17.10 G17.6: "No floating-point in the core: CI grep gate over `spectra-core/` for `f32|f64`, allowlist file required with per-line justification." §13.x negative requirements: "if a float is unavoidable, it is computed with fixed-point i64 scaled integers and the scale is declared." §16.6 constants gate allows float literals carrying a `// const-ok: <reason>` comment. §2.4(3) forbids only "floating-point accumulation whose order varies".

**Part II.** §58.5 (marked "OVERRIDES Part I: ... IEEE-754 is banned in decision paths outright — not 'discouraged'"): no float may be computed, compared, stored or serialized in a decision path; floats are permitted only in D3/canvas geometry, chart axes, CSS and the bench harness; lints fail on any occurrence outside `presentation/` and `bench/`; a gate asserts the certificate JSON and manifest `inputs` contain zero values matching /^-?\d+\.\d/ and zero exponents.

**Impact.** Part I's three escape hatches (the G17.6 allowlist file, the "if a float is unavoidable" fixed-point clause, and the `// const-ok` float-literal exemption) are all revoked. An implementer who builds the allowlist mechanism will ship a gate that Part II forbids; the allowlist file must not exist.

#### Wall-clock caps replaced by deterministic step budgets

**Part I.** Part I bounds work by hard caps and time: §13.x `limits.toml` caps, §4.1's per-target "Must finish in" column, and §47.6(6) treats "a timeout" as a first-class degradation condition.

**Part II.** §58.6 (marked "OVERRIDES Part I: Part I's §6/§4B caps and the feasibility critic's proposed 'solver time budget' are replaced"): every bounded loop draws from an integer step budget in `budgets.toml`, hashed into the certificate; exhaustion records `caps_hit[].at_step` which must be identical on every machine; wall-clock is recorded only in the unhashed `environment` block and a run exceeding `soft_deadline_seconds` prints a warning and continues; `tokio::time::timeout`, `context.WithTimeout`, `signal.alarm`, `setTimeout`, `time.After`, retry-with-backoff and any `sleep` are lint-banned in decision paths.

**Impact.** Explicit and well marked. The implementer must not build any abort-on-time path, and must make cap exhaustion reproducible down to the step index — which is a much stronger obligation than Part I's "set grounding_capped".

#### Seed model: one scalar vs root seed plus per-consumer registry

**Part I.** §2.4(3) requires "`random` without an explicit `Random(seed)`" to be banned; §3.4 lists a single "generator seed" in `bundle.jsonl`; §3.7 the certificate struct carries `seed: u64`; §43.4 builds fixtures with `spectra fixtures build --seed 0xSPECTRA`.

**Part II.** §58.8 (marked "OVERRIDES Part I: 'generator seed' (ECLIPSE §2) was a single scalar"): exactly one 32-byte `root_seed` per run written as 64 lowercase hex; every consumer derives its stream by `BLAKE3::keyed(root_seed, "spectra/seed/v1|" || consumer_id)`; ChaCha20 is the only permitted PRNG; `seeds.toml` is committed, hashed into the certificate, and a gate fails on an unregistered or dead consumer; the kernel links no RNG crate at all.

**Impact.** Part I's `Cert.seed: u64` field cannot hold a 32-byte root seed and Part II never restates the certificate struct, so the field must be widened (or replaced by `root_seed` + `derived_seeds` as in the §58.9 manifest) without Part II saying so. The `--seed 0xSPECTRA` CLI form in §43.4 also no longer matches the registry model.

#### Certificate provenance and what is excluded from hashing

**Part I.** §3.7: the certificate carries `hashes: Hashes // rules, bundle, controls, liveness, goal` plus `seed` and `k`; §14.5(5) additionally requires `skew.json` to be hashed into the certificate. No host, toolchain or image provenance is recorded and nothing states what must be excluded from a hash.

**Part II.** §58.9 (marked "OVERRIDES Part I: Part I's certificate carried no host or toolchain provenance and no statement of what is excluded from hashing"): the manifest has exactly two top-level blocks, `inputs` (hashed; `run_id` and every certificate hash derive from it alone) and `environment` (host fingerprint, wall-clock, thread count, peak RSS — never hashed, never read by a decision path); `inputs` adds git sha/dirty flag, per-file BLAKE3, exact toolchain versions and the toolchain image digest.

**Impact.** Correctly marked. Note that the expanded hashed-input file set (adding `scenario.toml`, `seeds.toml`, `budgets.toml`, `er-config.toml`, `costs.toml`) also silently widens Part I's five-hash `Hashes` struct, and §58.12(8) ("do not read any field of the environment block from a decision path") revokes any use of host or thread information Part I's pipeline might have assumed.

## 59 Ingest and adapters

### UNRESOLVED

#### The 1% quarantine ratio ceiling makes the `corrupt` degradation matrix unrunnable

**Tension.** Part II 59.7 sets `max_quarantine_ratio = 0.01` and 59.11.6 states `If quarantined / total_frames exceeds max_quarantine_ratio, ingestion fails non-zero and produces no bundle. A run that cannot parse its own telemetry is not a degraded run, it is a broken one.` Part I 29.4/29.5 requires `make dataset-matrix` across completeness 100,90,...,30 with operators including `corrupt`, and Part I 29.7 invariant I-1 (`Zero false ROBUST`) is defined as a property `across the whole 100%->30% matrix`. At 30% completeness with a `corrupt` operator the quarantine ratio is far above 1%, so those cells produce no bundle at all. Compounding this, Part II 59.11.5 says any run with `ingest_quarantine.count > 0` `may not be rendered, exported, narrated, or printed as an unqualified ROBUST` — so I-1's test population (certificates with `mode: ROBUST` and no flags) is empty for every cell containing even one corrupted record. Part II is aware the degradation model exists (it cites the `duplicate` operator in 59.10 and degradation-matrix cells in `gate-source-class-coverage`) but never reconciles either rule with it.

**Decision needed.** Decide whether degradation-injected corruption is exempt from `max_quarantine_ratio` and from the `ingest_quarantine` certificate flag (e.g. a manifest-declared degradation provenance that ingest recognises), or whether Part I's headline invariant I-1 is restated to cover flagged certificates rather than unqualified ROBUST ones. Without a decision the flagship `zero false ROBUST across 100%->30%` claim cannot be produced.

**Recommended.** Keep the ratio gate and the flag for real telemetry, and have the degradation harness stamp a declared `degradation_provenance` in the bundle manifest that raises the ceiling for derived datasets while forcing the certificate flag. Then restate I-1 over flagged certificates, since the invariant is about the cut being wrong, not about the flag being absent.

#### The `reorder` degradation operator becomes unobservable and unmeasurable

**Tension.** Part I 29.4 lists `reorder` among the degradation operators and Part I 11.4 classifies `b.seq < a.seq on arrival order` as `REORDERED`, with the effect `reorder by seq; record transport reorder count`, surfaced through the per-event `integrity` field (10.2 enum includes `REORDERED`) and `integrity_report.json`. Part II 59.10 imposes a total order `independent of input file order and of directory iteration order`, and `gate-ingest-idempotent` explicitly requires that `double ingest and shuffled input file order yield byte-identical bundle.jsonl`. Part II's CanonicalEvent has no `integrity` field and 59.9 emits no reorder signal. Part II reasons carefully about why the `duplicate` operator must not be silently absorbed, but says nothing about `reorder`.

**Decision needed.** Decide whether the `reorder` operator is retired from the degradation matrix, or whether ingest must emit a reorder signal (e.g. an `arrival_inversion_count` per source into `ingest-signals.json`) that survives the canonical re-sort. As specified, shuffling input order is required to change nothing, so a reorder-degraded dataset is byte-identical to its parent and that matrix dimension measures nothing.

**Recommended.** Emit an arrival-order inversion count per source into `ingest-signals.json` derived from `(file_id, byte_start)` versus the canonical order, keeping bundle.jsonl byte-identical (so `gate-ingest-idempotent` still holds) while preserving a measurable reorder signal. Alternatively retire the operator explicitly rather than leaving it in 29.4 as a no-op.

#### The collector and normalizer listen on sockets; the ingest path may not open one

**Tension.** Part I 26.2/26.3 put `telemetry-collector` (Go) on TCP 9700 plus a unix socket and `normalizer` (Rust) on 9701, both attached to the internal `range_telemetry` network, with a semantic healthcheck requiring `collector stream attached`. Part II 59.12 states `No component in the ingest path may open a socket. Enforced structurally: the ingest container runs with network_mode: none, and a CI job attempts DNS, TCP, and ICMP egress from it and fails the build if any succeeds`, proved by `gate-ingest-egress`; 59.13 adds `spectra ingest is a pure file-in/file-out binary with zero service dependencies: no Postgres, no Redis, no HTTP.` Part II never mentions the collector or the normalizer. Separately, 59.12 itself specifies `POST /ingest` endpoints with rejection codes, implying ingest does have an HTTP surface somewhere.

**Decision needed.** Decide the boundary: is the socket-listening collector inside or outside the `ingest path` that must run with `network_mode: none`? If outside, name the trusted component that receives live emitter frames and writes the raw source files ingest reads, and state what integrity property that hand-off has. If inside, the 26.2/26.3 topology and healthchecks must be rewritten. Also reconcile the `POST /ingest` API surface with the no-socket rule (presumably an API front-end that only hands content-addressed refs to a networkless worker).

**Recommended.** Split explicitly: collector = network-facing frame receiver writing content-addressed raw blobs; `spectra ingest` = networkless worker over that blob store; API = separate process that only resolves `SourceRef`s. Then scope `gate-ingest-egress` to the worker container only, and say so, because as written the gate would fail on the collector.

#### Two competing hashed liveness-input artifacts

**Tension.** Part I 11.4 states `Outputs: integrity_report.json per run, containing per-stream record counts, gap count and total gap length, duplicate count, reorder count, fork flag, and the derived candidate intervals. This file is an input to the liveness pass and is hashed into the ECLIPSE certificate.` Part I 11.6 also routes `UNEXPLAINED_OBLIGATION` into it, and Part I 10.6 #5 / 10.9 reference a third file, `ingest_report.json`. Part II 59.11 states `ingest-signals.json is a hashed input to liveness` and that `Cert.hashes gains ingest_manifest and quarantine_report` — it never mentions `integrity_report.json` or `ingest_report.json`, and the 59.13 CLI transcript writes only `bundle.manifest.json`, `quarantine.jsonl`, `quarantine-report.json` and `ingest-signals.json`.

**Decision needed.** Decide which artifacts are the certificate-hashed liveness inputs and whether `integrity_report.json` and `ingest_report.json` are retired, renamed, or retained alongside `ingest-signals.json`. If retained, say which component writes them now that ingest is the only producer of the bundle, and where `UNEXPLAINED_OBLIGATION` (11.6) is emitted.

**Recommended.** Fold the per-stream integrity counters into `ingest-signals.json` and retire `integrity_report.json` and `ingest_report.json` by name, since Part II already owns every quantity 11.4 listed except the obligation findings, which belong downstream of the fact base anyway.

#### Three different behaviours for a record carrying `ground_truth`

**Tension.** Part I 10.4: `ground_truth is written only by the scenario generator and only into fixture bundles. The ingest path must strip it into a separate sidecar file before any reconstruction code can read the bundle`, gated by a test asserting `ground_truth` is unreachable. Part I 29.1: `The normalizer rejects any bundle line containing a key in the reserved truth namespace (__truth*, label, is_attack, scenario), exit code 4.` Part II 59.4 declares a closed struct with no `ground_truth` field, 59.9 code Q012 covers `unknown field under strict schema`, and 59.15 forbids repairing a record including `no field clipping` — so stripping a field is itself prohibited.

**Decision needed.** Decide the single behaviour when a `jsonl.v1` generator record carries `ground_truth` or a truth-namespace key: strip to a sidecar (10.4), abort the run with exit 4 (29.1), or quarantine the record Q012 (59.4/59.9). Note that quarantining would put every fixture-bundle record into quarantine, blowing `max_quarantine_ratio` and producing no bundle, and that stripping conflicts with Part II's never-repair rule.

**Recommended.** Make it a manifest-validation abort (Part I 29.1's behaviour, promoted to ingest): truth keys in an input file are an operator error, not untrusted-input handling, and should fail before parsing rather than consume the quarantine budget. Then delete 10.4's strip-to-sidecar instruction, since Part II forbids the repair it asks for.

#### `derived` source class versus the synthetic-bypass ban

**Tension.** Part II 59.3 introduces `derived | absent seq | no chain | n/a bracketing | produced by SPECTRA itself; never counts as evidence of liveness` — a source class whose records become ordinary `CanonicalEvent`s in `bundle.jsonl`. Part I 26.7 states the opposite: `Do NOT generate telemetry inside SPECTRA's own code path. Every event must originate in a range service and traverse collector -> normalizer. Synthesizing an event directly into bundle.jsonl is forbidden outside tools/fixture-mint, which stamps synthetic_bypass: true and which the ECLIPSE kernel refuses to accept as evidence.` Part II's CanonicalEvent has no `synthetic_bypass` field, and 59.3 disclaims only liveness evidence, saying nothing about whether a `derived` event may ground a rule instance.

**Decision needed.** Decide whether a `derived`-class event may appear as a leaf in an ECLIPSE derivation. Part I says the kernel refuses such events as evidence outright; Part II excludes them only from liveness. If they may ground rule instances, say so and explain why that does not reintroduce the self-generated-evidence hazard 26.7 exists to prevent; if not, add the kernel-side rejection to 59.3 and restore an equivalent of the `synthetic_bypass` marker to the schema.

**Recommended.** Treat `derived` as evidence-ineligible across the board, matching 26.7, and carry that as a hard kernel check keyed on `source_class`, since `source_class` is already in the `EventId` preimage and therefore cannot be forged after the fact.

#### Which file is the authoritative source manifest, and where the new per-source declarations live

**Tension.** Part I 26.3 states `The SourceIds emitted column is authoritative: it is generated from range/sources.toml and rules.toml must reference no SourceId absent from it. A CI gate diffs the two and fails on any orphan.` Part I 9.3 and 12.3 R12 additionally reference a `source registry` / `source_registry.toml` carrying realms and declared cross-realm links. Part II 59.3 requires `Every source is declared in the source manifest with exactly one source_class`, 59.8 requires a manifest-declared IANA zone and a per-file `epoch_year`, and 59.6 requires a declared `format_id` — with the CLI showing all of this at `scenario/acme-01/sources.toml`. None of Part I's 16 SourceIds carries a class, a format, a timezone or an epoch year.

**Decision needed.** Decide whether `range/sources.toml`, `source_registry.toml` and the Part II per-scenario `sources.toml` are one file or three, which one the Part I orphan-SourceId CI gate runs against, and assign a `source_class`, `format_id`, `declared_tz` and (where applicable) `epoch_year` to each of Part I's 16 range SourceIds. Without that assignment `gate-source-class-coverage` (`no degradation-matrix cell ran without an unchained source`) cannot be satisfied by any existing range configuration.

**Recommended.** Make the Part II per-scenario manifest the single authoritative source registry, generate the `SourceIds emitted` column and the orphan gate from it, and add the class/format/tz/epoch_year columns to the 26.3 service table so the range and the ingest manifest cannot drift.

#### Nothing produces `observed_at_ns`, which Part I's gap intervals depend on

**Tension.** Part I 10.2/10.4 make `observed_at_ns` an always-required field, and Part I 11.4 derives the SUPPRESSED-basis candidate window as `interval [a.observed_at_ns, b.observed_at_ns]` — the collector-stamped observation time is the only thing that turns a `seq` gap into a time interval. Part II 59.5 forbids any adapter from reading a clock (`No clock, no filesystem, no network, no RNG`, enforced by `gate-adapter-purity`), Part II's CanonicalEvent carries no observation timestamp at all, and Part II has no collector to stamp one.

**Decision needed.** Decide who stamps observation time under Part II, or declare 11.4's `[a.observed_at_ns, b.observed_at_ns]` interval derivation replaced by the gap windows in `ingest-signals.json` and state what those windows are bounded by instead (presumably `t_utc_ns` of the bracketing accepted records). Leaving both in place means an always-required field with no producer and a liveness interval that cannot be computed.

**Recommended.** Retire `observed_at_ns` from the canonical event and define the gap interval in `ingest-signals.json` as `[t_utc_ns(prev accepted), t_utc_ns(next accepted)]` for the same source — which is what 59.9's `FrameNeighbourBound` recovery basis already does for quarantine records, so the two mechanisms would then agree.

#### New BLIND-producing mechanisms versus the hard 55-75 natural-BLIND-minutes band

**Tension.** Part I 27.4 sets `natural BLIND minutes (all sources summed) | 55-75 | band` and states `Bands are not aspirations: a run outside a band fails the build`; Part I 27.2 produces that budget from exactly two declared maintenance windows. Part II adds two new mechanisms that force non-LIVE windows: 59.8 makes `AssumedTz` a soundness-affecting basis such that `any interval containing an AssumedTz event is ineligible to be certified LIVE`, and 59.11.2 states `A tainted window may never be certified LIVE`, treating it as BLIND. Any range source emitting zoneless legacy syslog (Part I 10.6 covers RFC 3164, and `legacy_access`/`php_session_log` come from the PHP legacy-web service) would be permanently non-LIVE under 59.8.

**Decision needed.** Decide whether the 55-75 band counts only maintenance-window blindness or all non-LIVE minutes, and whether any range source is permitted to be `AssumedTz`. If the band is total non-LIVE minutes, it must be recomputed or the range's zoneless sources must be given a `SourceOffset`/`MappedTz` basis so the whole source is not permanently blind.

**Recommended.** Redefine the band as maintenance-window blind minutes only, measure taint-induced and AssumedTz-induced blind minutes as separate reported quantities, and require every range source to emit an explicit numeric offset so `AssumedTz` appears only in the hostile-format conformance corpus rather than in the base dataset.

### SILENT

#### The entire CanonicalEvent schema is replaced, but only the timestamp type is declared as an override

**Part I.** Part I 10.2 is a `complete` JSON Schema (`schemas/event/1.0.0.json`) with `additionalProperties: false` and 14 required fields: `schema_version, event_id, event_type, dimension, occurred_at_ns, observed_at_ns, time_trust, scenario_id, run_id, source, outcome, evidence`. It also carries `actor`, `target`, `network`, `control_context`, `raw_identifiers`, `integrity`, `degradation`, `ground_truth`, and an `allOf` block making e.g. `dimension: session` require `session_ref` and `actor`. Part I 10.5 generates Python/Rust/Go/TypeScript bindings from this schema by `make schemas` and fails CI on diff.

**Part II.** Part II 59.4 declares a different struct (`CanonicalEvent`, crate `spectra-ingest-core`) whose fields are `schema_version, event_id, source_id, source_class, seq, chain_prev, chain_self, t_utc_ns, t_resolution_ns, t_basis, t_source_raw, dim, action, actor_raw, target_raw, attrs, raw, format`. It has no `scenario_id`, `run_id`, `outcome`, `evidence`, `observed_at_ns`, `time_trust`, `integrity`, `degradation`, `network`, `control_context`, or `ground_truth`. The only override declared is `the timestamp type is fixed here`.

**Impact.** Every Part II event fails Part I's schema validator (`additionalProperties: false` plus 8 missing required fields), and the generated bindings from `make schemas` type-check nothing the ingest crate emits. All seven `allOf` dimension conditionals in 10.2 are unsatisfiable because the fields they require do not exist. An implementer reading Part I alone builds and gates the wrong record entirely.

#### `schema_version` type and the version-compatibility policy

**Part I.** Part I 10.2: `schema_version` is a string matching `^1\.[0-9]+\.[0-9]+$` (semver). Part I 10.5: MINOR bumps add optional fields and new enum members, and `Consumers must accept unknown MINOR versions within the same MAJOR by ignoring unknown optional fields`, shipping a new schema file and a bumped `MAX_MINOR` per binding.

**Part II.** Part II 59.4: `schema_version: u16, // 1; unknown => Q041, never best-effort`, with Q041 defined in 59.9 as `unsupported record schema_version`. 59.15 forbids any `lenient`, `best-effort`, or `relaxed` mode.

**Impact.** An integer `1` cannot be validated against `^1\.[0-9]+\.[0-9]+$`, so no Part II event passes Part I's own schema. More seriously the policies are opposite: Part I requires accepting an unknown MINOR within the same MAJOR; Part II quarantines any version it does not know. A bundle written at 1.1.0 is compatible under Part I and entirely quarantined under Part II.

#### `EventId` algorithm, format, and what it is a hash of

**Part I.** Part I 10.2: `EventId` matches `^evt-[a-z2-7]{26}$` and is `evt-` + base32(BLAKE3_128(canonical_json_without_event_id)) where canonical JSON is RFC 8785 JCS; `Two adapters that normalize the same record to the same canonical content produce the same EventId; this is what makes certificate leaf references stable.` Part I 10.5: `spectra events migrate` re-derives `event_id`, `Because event_id is content-addressed, a migration changes IDs`, emitting `idmap.json`.

**Part II.** Part II 59.4/59.10: `event_id: EventId, // 64 lowercase hex chars, BLAKE3-256`, computed as `lowercase_hex(BLAKE3-256(canonical-CBOR({schema_version, format_id, format_version, source_id, source_class, seq, t_utc_ns, t_basis, raw_b3})))` — nine fields only, not the event's normalized content.

**Impact.** Different length, different alphabet, different preimage. The Part I regex rejects every Part II id and vice versa; certificate leaf references, the `evidence` primary key, and the truth-annotation join key all change shape. The semantics invert too: under Part I two adapters that normalize the same record identically produce the same id, while under Part II the id is tied to `raw_b3` and the source, so identical content from two sources gets two ids and a content-changing MINOR migration does NOT change the id — breaking 10.5's `a migration changes IDs` and the stale-certificate detection built on it.

#### Canonical JSON key ordering for `bundle.jsonl`

**Part I.** Part I 10.2: canonical JSON is `RFC 8785 JCS`, which mandates lexicographic key ordering. Part I 29.5 #3: `bundle.jsonl is written in canonical JSON (sorted keys, no floats without fixed formatting, RFC3339 UTC with fixed precision)`.

**Part II.** Part II 59.4: `#[derive(Serialize)] // canonical JSON: keys emitted in this declared order` — i.e. struct declaration order (`schema_version, event_id, source_id, source_class, seq, ...`), which is not lexicographic. Only `attrs` is specified as `sorted keys`.

**Impact.** Two mutually exclusive canonicalization rules for the same file. Whichever the writer picks, the other side's recomputation produces a different `b3:` hash, so `gate-ingest-cross-os`, `make dataset-reproduce`'s bundle MATCH check, and the Go checker's certificate hash verification fail for reasons no one can localize. Part I also mandates RFC3339 UTC timestamps with fixed precision in bundle.jsonl, while Part II emits `t_utc_ns` as an integer and forbids any decimal in a hashed artifact.

#### Total order of lines in `bundle.jsonl`

**Part I.** Part I 29.5 #3: bundle.jsonl is `sorted by (sim_tick, source_id, ev_)`, and 29.5 #5 relies on `the normalizer's final sort` to make inter-source interleaving irrelevant.

**Part II.** Part II 59.10: `Total order of bundle.jsonl is (source_id, t_utc_ns, seq.unwrap_or(0), raw_b3, file_id, byte_start) — total, deterministic, independent of input file order and of directory iteration order. This is the ingest instance of the determinism charter.`

**Impact.** Different sort keys produce a different line order and therefore a different file hash for identical inputs. `sim_tick` does not exist anywhere in Part II's CanonicalEvent, so Part I's primary sort key is unavailable — an implementer following 29.5 cannot produce the ordering at all, and `make dataset-reproduce` will report a bundle.jsonl hash mismatch against any manifest written under the other rule.

#### Hash chain construction formula

**Part I.** Part I 11.3: `chain_hash_0 = BLAKE3_256("spectra.chain.v1" || collector_id || stream_id || u64le(epoch))` and `chain_hash_n = BLAKE3_256(chain_hash_{n-1} || content_hash_n || u64le(seq_n))`, computed by the collector at emission and recomputed by the ingester, with per-stream `chain_checkpoints` every N records so verification can start mid-stream.

**Part II.** Part II 59.10: `Chain verification for chained sources recomputes chain_self = BLAKE3(chain_prev || canonical_frame_bytes)` — no domain separation, no genesis block, no `collector_id`/`stream_id`/`epoch` binding, no `seq` in the preimage, and over raw frame bytes rather than `content_hash_n`. No checkpoints are mentioned.

**Impact.** A chain produced per Part I 11.3 fails Part II verification and is reported as Q019 `hash-chain link mismatch` on every single record — which under 59.11 marks the whole source's windows tainted and therefore BLIND, and under 59.11.6 likely blows the 1% quarantine ratio and produces no bundle at all. Dropping `seq` and the epoch-bound genesis also removes Part I 11.5's ability to detect tail truncation and to bind a chain to a specific collector epoch.

#### `seq` and `chain_hash` are mandatory in the Part I schema and DDL

**Part I.** Part I 10.2 `Source` has `required: ["source_id","collector_id","stream_id","seq","input_format","sensor_kind"]`, and `Evidence` has `required: ["content_hash","chain_hash"]`. Part I 11.1 DDL: `chain_prev bytea NOT NULL, chain_hash bytea NOT NULL, seq bigint NOT NULL`, with `UNIQUE (scenario_id, collector_id, stream_id, seq, content_hash)`.

**Part II.** Part II 59.4: `seq: Option<u64>, // None iff source_class in {unchained, derived}` and `chain_prev: Option<Hash32>, // Some iff source_class == chained`. 59.3 requires at least one `unchained` source in every scenario family.

**Impact.** The 59.3 override marker names Part I sections 26-29 only; it never names 10.2 or 11.1, so the schema's required fields and the NOT NULL columns are never retracted. The mandatory `unchained` source therefore cannot produce a schema-valid event or a storable evidence row, and the evidence UNIQUE constraint (which includes `seq`) is undefined when `seq` is NULL. An implementer running the Part I migration will have a database that physically cannot hold the source class Part II makes mandatory.

#### Lossy adapters: recorded field loss vs. quarantine

**Part I.** Part I 10.2 `Evidence` carries `adapter_lossy: boolean` and `dropped_fields: array (maxItems 64)`; Part I 11.1 DDL has `adapter_lossy boolean NOT NULL DEFAULT false`. Part I 10.6's loss-policy column instructs adapters to `record dropped_fields` for json/jsonl, route `unmapped columns -> attributes.raw_<col>` for CSV, and `unparsed tail -> attributes.raw_tail` for syslog.

**Part II.** Part II 59.7: `Exceeding a limit is a quarantine, never a truncation. No adapter may emit a CanonicalEvent built from a clipped field`, proved by `gate-no-truncation` (`oversized-field fixture yields quarantine, not a clipped event`, code Q038). 59.15 forbids `no field clipping`. The Part II CanonicalEvent has no lossiness fields at all.

**Impact.** Part I explicitly designs for and records partial parses; Part II makes a partial parse a quarantine. An implementer following 10.6 emits an accepted event with `adapter_lossy: true` where Part II requires zero accepted events and one Q038 record — exactly the case `gate-no-truncation` is built to catch, but nothing in Part I warns them.

#### Timestamp synthesis and inference from neighbouring records

**Part I.** Part I 10.6 #3: `Never invent occurred_at_ns. If absent, set occurred_at_ns = observed_at_ns and time_trust = "collector", and record attributes._time_synthesized = true.` Part I 10.6 #2 defines `time_trust: inferred` as the value to use `when derived from neighboring records`.

**Part II.** Part II 59.8: an unparseable timestamp is Q013; ambiguous or non-existent local times are Q014; `Ambiguity and non-existence are quarantines, not guesses`. The zoneless-year problem `is solved by a manifest-declared epoch_year per file, not by inferring the year from the wall clock or from neighbouring records. Inference from neighbours lets a single crafted record retro-date a whole file.` 59.15 forbids `no timestamp guessing, no inferred year, no inferred timezone`.

**Impact.** Part I instructs the adapter to fabricate a timestamp and accept the record; Part II requires quarantine. The 59.8 override marker cites Part I sections 17-19, never section 10, so an implementer reading 03-datamodel keeps a substitution path that Part II 59.1 identifies as a license-manufacturing hazard. Part I also blesses exactly the neighbour-inference that Part II names as a retro-dating attack.

#### `time_trust` vocabulary and the BACKDATED-voids-license rule

**Part I.** Part I 10.2: `time_trust: enum [authoritative, collector, inferred, untrusted]`, required on every event. Part I 11.4: when `occurred_at_ns` violates the difference constraints the record is `BACKDATED` and `timestamp marked untrusted; any license resting on it is voided`. Part I 12.8 #6 orders `time_trust = "untrusted"` events by `(collector, seq)` within their stream.

**Part II.** Part II 59.4/59.8 replaces this with `t_basis: TimeBasis // SourceUtc | SourceOffset | MappedTz | AssumedTz`, a disjoint vocabulary describing how the value was obtained rather than how much it is trusted. 59.8: `Backdating is a kernel-level concern ... with the fail-closed rule stated in the Part II threat-model section: an unresolvable timestamp yields BLIND, never a voided license.`

**Impact.** Part II directly negates Part I 11.4's remedy without ever citing it: Part I voids the license, Part II forbids voiding it and requires BLIND. These have opposite soundness directions — voiding a license withholds admission of silent attacker steps, which is exactly the failure Part II 59.1 warns produces false ROBUST. Part I 12.8 #6's fallback ordering by `(collector, seq)` is also unimplementable: Part II has no collector field and `unchained` sources have no `seq`.

#### Where entity resolution runs relative to `bundle.jsonl`

**Part I.** Part I 26.3 service table, described as authoritative: `normalizer | Rust | 9701 | schema normalization, entity resolution, EventId assignment, bundle.jsonl`. Its healthcheck is `collector stream attached AND last 60s produced a monotone EventId range`.

**Part II.** Part II 59.4: `Ingest performs no entity resolution. actor_raw/target_raw carry the strings as they appeared. Merging identifiers is the entity-resolution section's job and its uncertainty must not be laundered through the parser.` The 59.2 pipeline diagram places `entity resolution -> fact base -> ECLIPSE kernel` strictly after `bundle.jsonl`.

**Impact.** Part I's buildable artifact (the service table and its healthcheck) puts entity resolution inside the streaming component that writes bundle.jsonl. Under Part II that ordering is forbidden. An implementer building the 26.3 normalizer produces a bundle whose identifiers are already merged, defeating 59.4's poisoning defence and contradicting Part I 12.7's own requirement that the resolver be `a single batch pass over the complete bundle`.

#### Value space of `source_id` (and the missing `collector_id`)

**Part I.** Part I 10.2 `Source` requires `source_id` matching `^src-[a-z2-7]{16}$` and `collector_id` matching `^col-[a-z2-7]{16}$` — both are resolved EntityIds of kinds `src` and `col` per 9.2/9.3, produced by hashing an anchor tuple that includes `scenario_id` and `realm`.

**Part II.** Part II 59.4: `source_id: SourceId, // from the manifest, never from the record`, with concrete values shown as bare names (`idp_audit`, `proxy_access`), also used in the `SourceRef` form `scenario:acme-01/source:idp_audit`. There is no `collector_id` field anywhere in the Part II event.

**Impact.** Producing a `src-…` EntityId requires the entity-resolution step that 59.4 forbids ingest from performing, so the Part I `source_id` pattern is unsatisfiable at the ingest boundary. Every Part II event also fails 10.2's `Source.required`, which includes `collector_id` and `stream_id` — fields Part II never defines. Downstream code keyed on `src-…`/`col-…` will not match anything ingest writes.

#### No collector declaration record exists under Part II

**Part I.** Part I 11.2: `Every collector declares itself once per epoch with a collector.declare record carrying collector_id, source_id, stream_epoch, clock_source, declared_flush_interval_ns. Streams without a declaration are ingested but marked UNDECLARED and can never support a liveness claim.` Part I 11.5 makes tail-truncation detection depend on `the stream declaration promised a flush cadence`.

**Part II.** Part II 59 defines no collector, no stream, no epoch declaration and no flush cadence. Sources are declared in a source manifest carrying only `source_class`, format, timezone and epoch-year. 59.11 nonetheless makes `ingest-signals.json` the hashed input to liveness for all sources.

**Impact.** Taken together with 11.2 every Part II source is UNDECLARED, so `can never support a liveness claim` would make ECLIPSE liveness vacuous for the entire system — an implementer who keeps the 11.2 rule and the Part II manifest gets a build in which no window can ever be certified LIVE. Losing `declared_flush_interval_ns` also silently removes Part I 11.5's only mechanism for distinguishing tail truncation from a quiet sensor.

#### Same-seq divergent-content records: retained fork vs. quarantine

**Part I.** Part I 11.4: `b.seq == a.seq and b.content_hash != a.content_hash` is classified `CHAIN_BREAK (fork)`, and `both retained, stream marked forked, no liveness claim permitted anywhere in the epoch`.

**Part II.** Part II 59.9 code Q018 PROVENANCE: `sequence conflict (same seq, divergent content)` is a quarantine. 59.9 also states `Quarantine records are not events. They have no EventId, never enter the fact base, never appear in any observed-event count, and may never be rendered as evidence.` 59.11.2 treats the resulting tainted window as BLIND rather than banning liveness claims epoch-wide.

**Impact.** Opposite retention policy (both records kept as events vs. neither kept) and opposite liveness blast radius (whole epoch barred from any liveness claim vs. one tainted window forced to BLIND). An implementer following 11.4 keeps forked records in the fact base where Part II forbids them from being evidence at all.

#### YAML: multi-document event stream vs. single-document config snapshot

**Part I.** Part I 10.6 normalization table, `yaml` row: framing is `multi-document ---`, mapping `same as json`, `Time source: declared key`, loss policy `anchors expanded before mapping` — i.e. YAML is a first-class event input format whose anchors are resolved during parsing.

**Part II.** Part II 59.6: `yaml.config.v1 | SingleDocument | service config snapshot | safe loader only; config snapshots only, never event streams`. 59.7 sets `allow_merge_keys = false`, `max_aliases = 64`; 59.9 gives Q029/Q030/Q031 for custom tags, alias-budget overrun and merge keys.

**Impact.** Part I treats YAML as a multi-document event source with free anchor expansion; Part II forbids it as an event stream, caps it to one document, and quarantines merge keys and alias overruns. An adapter written to 10.6 is rejected by `gate-yaml-safe`, and any range source configured to emit YAML events has no legal format_id under the closed Part II table.

#### `winxml` and `binlog` input formats no longer exist

**Part I.** Part I 10.2 `Source.input_format` is a closed enum including `winxml` and `binlog`. Part I 10.6 specifies the `winxml` adapter in full (framing on `<Event>` elements, `EventID -> type table`, `EventData/Data[@Name]` mapping, time from `TimeCreated/@SystemTime`), and Part I 10.8 is an entire worked example built on it.

**Part II.** Part II 59.6: `The supported set is closed` at ten `format_id`s — none of which is winxml or binlog — and `An input whose declared format_id is not in this table is refused at manifest validation with a non-zero exit, not sniffed.` The negative requirements add `No binary packet parsing in the core.`

**Impact.** Part I 10.8's worked example is unbuildable and the `binlog` enum member has no adapter at all. Part II never says it is narrowing the format set relative to 10.2, so an implementer building the winxml adapter from 10.6/10.8 produces code that cannot be registered in any manifest and a `Source.input_format` enum that disagrees with `spec/grammars/`.

### RESOLVED

#### Ownership of the raw-bytes-to-bundle.jsonl boundary and the fate of unparseable records

**Part I.** Part I 10.6 #5: a record that cannot be mapped produces a `NormalizationError` counted in `ingest_report.json`, with the identity `records_in == events_out + errors_out`. Part I 11.4: a record that parses but whose mandatory field fails type coercion is classified `CORRUPT_FIELD` and the `event [is] dropped`, with a `NormalizationError` emitted.

**Part II.** Part II 59 preamble states `OVERRIDES Part I: telemetry ingestion now has an owning section. Part I (sections 9-12, 26-29) treated bundle.jsonl as a pre-existing input and never said who produces it, what parses the raw bytes, or what happens to a record that fails to parse.` 59.1: a malformed record `is QUARANTINED with a machine-readable reason code and counted. It is never dropped, never truncated, never best-effort repaired, and never skipped with a log line.` 59.2 adds a byte-conservation partition law and `gate-byte-conservation`.

**Impact.** The override is stated, but its stated premise is false: Part I 11.4 and 10.6 #5 DO say what happens (drop the event, emit a NormalizationError). Neither row is struck by Part II, so an implementer working from Part I 11.4 will still drop CORRUPT_FIELD events silently at the event level while believing Part II only filled a gap. Part I's weaker accounting identity (records_in == events_out + errors_out, at record granularity, into `ingest_report.json`) also survives alongside Part II's stronger one (accepted + quarantined + skipped == frames, plus a byte-level partition, into `quarantine-report.json`).

#### Hash chain is no longer a universal property of telemetry

**Part I.** Part I 26.3 service table: `telemetry-collector` (Go, port 9700) `receives emitter frames, BLAKE3 sequence-chains per source, writes raw.jsonl` — i.e. every one of the 16 SourceIds is chained. Part I 11.3 defines per-stream chaining computed by the collector at emission for all streams; 11.5 builds excision/mutation tamper detection on top of it.

**Part II.** Part II 59.3: `OVERRIDES Part I sections 26-29: the hash chain is no longer a universal property of SPECTRA telemetry.` Four source classes — `chained` (seq dense + BLAKE3 chain + bracketing), `sequenced` (seq, no chain), `unchained` (neither), `derived`. `At least one unchained source class must be present in every scenario family`, results must be `split by source class`, and `suppression detection on chained sources is a laboratory affordance rather than a general result`. Enforced by `gate-source-class-coverage`.

**Impact.** The collector in Part I 26.3 must stop chaining at least some sources, and Part I 11.5's tamper-detection guarantees now hold only for the `chained` subset. Part I never assigns a class to any of its 16 SourceIds, so which sources become `unchained` is undefined — see the unresolved item on the source manifest.

#### Timestamp type and clock semantics fixed at the adapter edge

**Part I.** Part I 10.2/10.4 carry `occurred_at_ns`, `observed_at_ns`, `time_trust` (required) plus optional `ingested_at_ns` and `time_skew_ns`; Part I 10.6 makes each adapter responsible for setting `time_trust` per its own rules.

**Part II.** Part II 59.4: `OVERRIDES Part I sections 17-19: the timestamp type is fixed here, at the adapter edge, for the whole system.` 59.8: `OVERRIDES Part I sections 17-19, which left time semantics per-component` — every event carries `t_utc_ns: i64` plus verbatim `t_source_raw`, `Downstream components read only t_utc_ns. No component below ingest parses a timestamp string.`

**Impact.** The override is marked, but it cites sections 17-19 only. The concrete time fields and the `time_trust` enum live in 03-datamodel (10.2, 10.4, 10.6, 11.4), which the marker never names, so the specific contradictions there are reported separately as silent.

## 60 Entity resolution

### UNRESOLVED

#### EntityId string shape vs the canonical event schema patterns

**Tension.** §10.2 constrains `EntityRef.entity_id` with `"pattern": "^[a-z]{3,7}-[a-z2-7]{16}$"` under `additionalProperties:false`, and `resolved_by_rule` with `^R[0-9]{1,2}$`. Part II's `ent:3a0c7f21b4e59d88…` (prefix `ent:`, 32 hex chars) fails the first, and its rule ordinals (00-44) fail the second. §12.6's `unres-…` ids fail both specs' expectations. Part II's blanket 'OVERRIDES Part I sections 9-12' never mentions §10.2, the event schema, or the migration policy in §10.5 that classifies a retype as MAJOR.

**Decision needed.** Does the canonical event schema go to 2.0.0 with new `entity_id` and `resolved_by_rule` patterns (and a `migrations/events/1.x__2.0.0/` chain per §10.5), or does Part II's EntityId adopt a Part I-compatible shape? Note that §10.5 also says `event_id` is content-addressed and a migration re-derives it, so every EventId cited in `er-mergelog.jsonl` and every certificate leaf changes with the bump.

**Recommended.** Bump to event schema 2.0.0 and widen the patterns to `^(ent:[0-9a-f]{32}|[a-z]{3,7}-[a-z2-7]{16})$` only if both id spaces must coexist; otherwise adopt `ent:` uniformly, and state in Part II that §10.2, §10.5 and the language bindings are in scope of the §9-12 override.

#### scenario_id dropped from the entity key

**Tension.** §9.3: '`scenario_id` is in the anchor, so entities from different scenarios can never collide or merge', and 'store `(scenario_id, entity_id)` as the composite primary key so a single database can hold many scenarios'. Part II 60.5 derives `EntityKey` from the component's sorted bindings only — no scenario_id, no run scope. Two scenarios that contain the same identifier (`svc_deploy@corp.local` is used in fixtures across scenarios) produce the same EntityId.

**Decision needed.** Is the Part I cross-scenario isolation guarantee retained (fold `scenario_id` into `canonical_encode` or into the EntityKey preimage), or is the id deliberately scenario-independent so the same principal is one id across scenarios? The certificate's `er_output` hash and the Postgres composite PK both depend on the answer.

**Recommended.** Retain isolation: prefix the EntityKey preimage with `scenario_id`, which preserves Part II's content-addressing property and §9.3's no-collision guarantee at once. If scenario-independent ids are wanted, say so explicitly and drop §9.3's guarantee in writing.

#### Tick time base vs nanosecond integers

**Tension.** Part I is nanoseconds everywhere: `occurred_at_ns`/`observed_at_ns` are integers 0..2^63-1 (§10.2 `Ns`), every entity and edge row carries `first_seen_ns`/`last_seen_ns`, process anchors use `start_time_ns`, and §10.10 forbids floating-point timestamps. Part II's `Binding.t_lo`/`t_hi` are `Tick` ('integer ticks (Part II determinism charter)'), `Tick::MAX` means open, and `Proposal.t_key` — part of the total ordering that determines the output — is a Tick. The examples show small values like `[1204, MAX)` and `[1731,1791)`. No conversion between ns and ticks is defined in either part.

**Decision needed.** What is a Tick, and what is the exact, total, order-preserving map from `occurred_at_ns` to Tick? If it is a quantization, two events in the same tick become simultaneous, which changes `overlap`, `adjacent` (which requires exact `a.t_hi == b.t_lo`) and the merge order — so the map must be specified before ER is implementable or its confluence gate (G-ER-1) is meaningful.

**Recommended.** Define Tick = the nanosecond integer itself (identity map), so `adjacent`'s exact-equality test keeps its Part I meaning and no quantization is introduced; if the determinism charter needs a coarser tick, publish the quantization constant in `er.toml`, hash it into `er_config`, and state what happens to two distinct-ns events that land on the same tick.

#### Declared and evidenced cross-realm identity links have no Part II rule

**Tension.** §12.2: 'Tier A merges across realms only when an explicit `identity_link` event or a declared mapping in the source registry authorizes it', implemented by R12 (`source_registry.toml`, e.g. `corp.ad:S-1-5-21-77-1104 == corp.idp:svc_backup`) and R13 (`identity_link` event from a control-plane source), applied in §12.4 phase 3. Part II's rule table has no ordinal for a declared or evidenced cross-realm link; rule 44 `cross_realm_name` makes cross-realm name matches AMBIG, rule 00 excludes distinct same-realm SIDs, and `er.toml` has no declared-links section. The rule list is closed, enabled-by-ordinal, and hashed.

**Decision needed.** Do legitimately federated identities (one human as `corp.ad` SID and `corp.idp` account) remain resolvable? If yes, a new rule ordinal and an `er.toml` section (or a re-admitted source registry input) must be specified, together with its evidence class — a declared mapping is configuration, not telemetry, so 60.1's ANCHOR/LINK/HINT algebra does not currently classify it. If no, §12.2, R12, R13 and §12.8(2) under-merge must be struck.

**Recommended.** Add an ordinal in the 10-range (e.g. 16 `declared_cross_realm_link`) fed by a hashed `[cross_realm]` table in `er.toml` plus an `identity_link` telemetry path, and treat the declared mapping as ANCHOR-equivalent only because it is hashed into `er_config` and therefore certificate-visible.

#### Alias rows, edge rows and the persistence boundary

**Tension.** Part I makes ER produce an alias table (§12.7: 'Aliases are rows, not rewrites: (scenario_id, entity_id, realm, class, value, first_seen_ns, last_seen_ns, rule_id, witness_event_id)') and an edge table (§9.8: thirteen edge types, each a first-class row with validity interval, `evidence_ids[]` and `license_id`), and specifies DB structures (§9.4 envelope, §9.6 `entity_state_history` with an UPDATE-rejecting linter). Part II's artifact list is `er.jsonl` / `er-mergelog.jsonl` / `er-report.json`, all 'immutable content-addressed blobs on disk (never in Postgres)', and 60.14(8) says '`er.jsonl` on disk is the truth; Postgres holds an index of it for query and nothing else'. Neither the alias table nor the edge table is mentioned.

**Decision needed.** Which stage now emits §9.8 edges and §12.7 aliases, and what is their authoritative store? Part II's bindings subsume aliases for merged identifiers, but they do not carry `rule_id`/`witness_event_id` per alias in the shape §12.7 specifies, and edges between entities are not an ER output at all under Part II's model — yet §9.8 edges are evidence-backed and license-bearing, which the kernel consumes.

**Recommended.** State explicitly that `er.jsonl` bindings replace the alias table (adding `rule_ord` and witness EventIds per binding so §12.7's audit fields survive), and name the stage that owns §9.8 edges — most likely the grounding stage, reading `er.jsonl` — so the Postgres-as-index rule does not silently orphan the edge and state-history tables.

#### Derived (GHOST) entities have no bindings, hence no distinct content-addressed id

**Tension.** §9.4 requires a `derived` boolean, 'true when the entity exists only because of an obligation axiom and was never directly observed', rendered GHOST, excluded from observed-count metrics, and carrying the license that admitted it; §9.9 and §11.6 make obligation-forced entities a first-class outcome. Part II derives `EntityId` as `BLAKE3(concat over sorted(bindings) of canonical_encode(binding))` — a derived entity has no observed binding, so either it has no id, or every derived entity hashes the same empty preimage and collides. 60.8's `er.jsonl` record shape has no `derived` field and no license reference.

**Decision needed.** How are obligation-forced entities identified and represented under content-addressed ids? Options: give them a synthetic binding derived from the obligation instance and its license id (keeps them distinct and content-addressed), or move them out of ER's id space entirely into a separate `ghost:` namespace owned by the kernel.

**Recommended.** Give each derived entity a synthetic binding of a new IdKind (class-excluded from all merge rules) whose value is the obligation instance id plus the license id, and add `derived` and `license_id` to the `er.jsonl` record so §9.4's GHOST rendering and metric exclusion remain enforceable.

### SILENT

#### Cross-kind merging collapses session, token, credential and principal into one entity

**Part I.** §9.2 makes `sess`, `tok`, `cred`, `acct`, `svcacct`, `idn` distinct entity kinds, each with its own anchor tuple and its own EntityId; §9.8 makes `principal_of`, `authenticates_with`, `exchanged_for` first-class time-bounded edge rows between them; §12.4 phase 1 uses a `TypedUnionFind()` with the comment 'merges only within a kind'. §9.2 also states 'Principal is not a kind; it is the union type {idn, acct, svcacct}'.

**Part II.** 60.4 rules 11 `token_to_subject`, 12 `session_to_subject`, 14 `sa_key_binding` and 15 `cert_to_subject` all emit MERGE joining a TOKEN_JTI / SESSION_ID / API_KEY_ID / CERT_FINGERPRINT binding with a SID_WINDOWS or SERVICE_ACCOUNT binding into one union-find component, i.e. one EntityId. The 60.15 CLI shows this outcome: `ent:3a0c… kind=PRINCIPAL status=RESOLVED` whose bindings are a SERVICE_ACCOUNT, a TOKEN_JTI and a UID_POSIX.

**Impact.** The most dangerous silent conflict. Under Part II a token, a session and a certificate are bindings inside the subject's entity, not entities; the §9.7 ER diagram and the §9.8 `authenticates_with` / `exchanged_for` / `bound_to_device` edges have no endpoints left to connect, and §9.5's per-kind session and credential fields have no row to live on. The Part II CLI even uses a kind (`PRINCIPAL`) that Part I explicitly forbids as a kind. An implementer building Part I's typed union-find will find rules 11-15 unimplementable; one building Part II will silently destroy the session/credential graph the kernel and UI are specified against.

#### Resolution status vocabulary

**Part I.** §9.4 and the §10.2 `EntityRef` schema fix `resolution_state` to a four-valued enum: `RESOLVED | PROVISIONAL | UNRESOLVED | SPLIT_SUSPECT`. §12.5 produces SPLIT_SUSPECT on type and cardinality conflicts; §12.6 lists `SPLIT_SUSPECT` as an unresolved reason code.

**Part II.** 60.6: '`EntityStatus` is a closed, three-valued type... `enum EntityStatus { Resolved, Ambiguous, Unresolved }`', and 'It is not a score and it may not be flattened'. `AMBIGUOUS` is new; `PROVISIONAL` and `SPLIT_SUSPECT` do not exist as statuses.

**Impact.** No override marker anywhere. Two closed enums with the same job and different members, one of them embedded in a `additionalProperties:false` JSON Schema. Part II reuses the token `PROVISIONAL` for an unrelated concept (interval EdgeKind), so a reader of both will conflate an unknown interval endpoint with an entity state. Any code or fixture emitting `resolution_state: "PROVISIONAL"` or `"SPLIT_SUSPECT"` is now unrepresentable, and `AMBIGUOUS` fails §10.2 validation.

#### Rule identity and numbering

**Part I.** §12.3 defines rules `R1`..`R14` evaluated in fixed order, each recorded on every resolved reference as `resolved_by_rule`, constrained by §10.2 to the pattern `^R[0-9]{1,2}$`. §12.3 requires one positive and one negative unit test per named rule function.

**Part II.** 60.4 defines a different table of 26 rules with two-digit ordinals 00-44 plus 99, names like `anchor_identity` and `cross_realm_name`, verdicts MERGE/EXCLUDE/AMBIG/PASS, ordinals burned on retirement and hashed into `er_config`; `er.toml` `[rules] enabled = [0,1,2,...,44]`. 60.11 requires the checker to verify each merge record cites a `rule_ord` enabled in the hashed config.

**Impact.** Silent replacement of the rule catalog. `resolved_by_rule` in the canonical event schema can no longer hold a Part II ordinal (pattern mismatch), and the mergelog's `rule_ord` has no counterpart field on the event. Part I rules R3, R8, R10, R11, R12, R13 have no Part II ordinal at all — see the separate findings on each.

#### Token rotation: merge or two entities

**Part I.** §12.5 temporal conflict (explicitly naming token rotation): 'Do not merge across the boundary. Emit two entities with disjoint validity intervals and a `succeeded_by` edge.' §12.8(5): 'a rotated credential is a new entity with `rotation_generation+1` and a `succeeded_by` edge, never the same entity. Test that a rotation does not merge generations.' §9.5 gives `cred` a `rotation_generation` u32.

**Part II.** 60.4 rule 13 `token_rotation`: 'two `REFRESH_TOKEN_ID` with `adjacent` and a witnessed rotation record naming both' -> MERGE. 60.2 states `adjacent` exists precisely to 'license continuity across a witnessed handoff (a token rotation, a session renewal)'.

**Impact.** Flatly opposite, with a mandatory regression test on the Part I side asserting the behavior Part II mandates. Part I's `rotation_generation` counter and `succeeded_by` edge become dead. An implementer who keeps the Part I test will see rule 13 fail CI; one who implements rule 13 loses the generation boundary that §12.8(5) exists to preserve.

#### Conflict resolution by tie-break

**Part I.** §12.5 cardinality conflict: 'Split by rule provenance: drop the union edge with the highest rule number (weakest rule); if tied, drop the one with the later witness timestamp; if still tied, drop the lexicographically larger witness `EventId`. Deterministic by construction.' Type conflict: 'Split at the lowest-tier union edge. Both halves become SPLIT_SUSPECT.'

**Part II.** 60.14(4): 'Do not resolve an ambiguity by any tie-break, heuristic, recency preference, size preference, or "most likely" argument.' 60.6: 'There is no step at which an ambiguity is resolved by picking the more likely branch, the earlier branch, the larger component... There is no tie-break here.' 60.4/60.7: a MERGE proposal across a standing exclusion 'does not apply and does not fail — it produces AMBIG'.

**Impact.** Part I's conflict policy is exactly the class of tie-break Part II bans, including the recency preference named in the ban. Neither side acknowledges the other. Part I's answer is a deterministic split into two SPLIT_SUSPECT components; Part II's is an unsplit component carrying an `AmbiguityId`. An implementer following Part I will ship a rule Part II's lint and reviewers are told to reject; following Part II, §12.5's table has no implementation.

#### Identifier strength classification

**Part I.** §12.2 tiers: Tier A (authoritative, merges on its own under R1) includes `uid` (with realm), `container_ref`, `cert_fp`, `account_ref`, `resource_ref`; Tier B (strong-local, merges within a realm when the realm profile declares the class unique, R2) includes `username`, `upn`, `email`, `host_ref`, `device_ref`, `service_name`, `mac`; Tier C (never alone) is `ip`, `pid`, `gid`.

**Part II.** 60.1 classes: `HOST_NAME` is HINT — 'MAY NEVER CAUSE A MERGE'; `UID_POSIX`, `MAC`, `CONTAINER_ID`, `DEVICE_ID` are LINK (need a corroborating ANCHOR or a second independent LINK); `CONTAINER_ID` merges on a short prefix only with a matching `IMAGE_DIGEST` (rule 25); `MAC` is 'never sole basis'.

**Impact.** No override marker. Three classes replace three tiers with different memberships and different merge licenses. An implementer following §12.2/R2 merges two entities on a matching hostname inside a realm that declares `host_ref` unique — which is exactly the poisoning vector Part II's ER-POISON-01(c) fixture asserts must produce nothing. Likewise Part I's R1 merges on `container_ref` or `uid` alone, which Part II forbids.

#### Merging on an IP address

**Part I.** §12.2: 'Tier C identifiers may never, alone, merge two entities' and 'A rule that consumes a Tier-C identifier as its sole basis is rejected by a lint'; `ip` is Tier C. §12.3 R10: 'zone from the source registry, never from the address alone'. §12.8(4) NAT/shared egress collapse is 'prevented structurally: R10 forbids deriving identity from an address'.

**Part II.** 60.4 rule 30 `ip_within_lease`: 'same `IP_ADDR` in same vrf, both inside ONE lease with WITNESSED or INFERRED endpoints' -> MERGE. `IP_ADDR` is class LINK, and the lease interval, not a second identifier, is what licenses the merge.

**Impact.** Rule 30's sole identifier basis is an address, so Part I's mandated lint would reject it. Part I's structural NAT-collapse defense is gone: two principals behind one NATed address inside one lease window merge. Part II's own ERF-4 addresses lease reuse but never the many-hosts-one-address case §12.8(4) exists for.

#### Normalization form and where it is declared

**Part I.** §9.3: anchor fields are 'NFC-normalized, case-folded ONLY for fields declared case-insensitive in the realm profile'. §10.6(6): 'all usernames NFC-normalized and case-folded only per realm profile'.

**Part II.** 60.1: 'Normalization is per-kind, declared in `er.toml`, and applied before any comparison.' `USERNAME`, `UPN_EMAIL`: 'Unicode NFKC, then ASCII-lowercase only (NOT full Unicode casefold)'; `HOST_NAME`: 'NFKC, ASCII-lowercase, trailing dot stripped'. Any post-NFKC non-ASCII codepoint is flagged `NON_ASCII` and demoted a class.

**Impact.** NFC vs NFKC are different functions (NFKC folds compatibility characters, which is why Part II needs a `NORM_COLLISION` record at all), and the control locus moves from per-realm profiles to a single global `er.toml`. Unmarked. Two implementations will produce different normal forms, hence different components and different content-addressed EntityIds, for the same bundle. The realm profile's case-sensitivity declaration becomes dead configuration with no stated replacement.

#### ER configuration surface: realm profiles and source registry vs er.toml

**Part I.** §12.1: ER is a pure function of '(ordered canonical events, source registry, realm profiles)'. Realm profiles carry class-uniqueness declarations (R2), case-sensitivity (§9.3), and non-unique/shared-account declarations (§12.5 shared identifier -> `is_shared=true`, 'never merge on it'). `source_registry.toml` carries declared cross-realm mappings (R12) and zone assignment (R10).

**Part II.** 60.8: '`er.toml` is the only ER tunable surface.' Its sections are `[determinism]`, `[classes]`, `[normalization.*]`, `[rules]`, `[crossref]` (B7 field pairs per source schema) and `[leases]`. No realm profile, no source registry, no uniqueness declaration, no shared-account flag, no zone map.

**Impact.** Unmarked retirement of two configuration inputs that Part I's rules depend on. R2 (realm declares class unique) and §12.5's shared-account policy have nowhere to read their input; §9.5's declared `is_shared` flag no longer influences merging, so a shared admin account can now be merged by rules 21/22. An implementer wiring realm profiles into ER per §12.1 will also break Part II's config-hash story, since only `er.toml` is hashed into the certificate.

#### ER's input: canonical events vs raw source records

**Part I.** §10.6: 'Each adapter is a pure function bytes -> Vec<CanonicalEvent>... must emit `raw_identifiers` rather than `EntityId`s. Entity resolution runs after normalization (section 12).' §10.1: 'Adapters are the only code permitted to read a vendor format. Reconstruction code that string-parses raw telemetry is a build failure; enforce with an import lint.' §12.4 phase 1 builds nodes from `e.raw_identifiers`.

**Part II.** 60.0: `er_resolve : (bundle_raw.jsonl, er.toml) -> ...`. 60.7 pseudocode: `for field in cfg.extractors_for(rec.source, rec.schema_version) { normalize(field.kind, rec.get(field.path), cfg) }` — ER reads per-source field paths out of records, and `[crossref] idp_audit.v2 = [["sub","jti"],...]` names vendor field names. The pseudocode also takes a third input, `liveness`, that 60.0's signature omits.

**Impact.** Unmarked change of ER's position in the pipeline and of its input contract. If `bundle_raw.jsonl` means pre-adapter records, ER now reads vendor formats and violates Part I's import lint and §10.1 build-failure rule; if it means canonical events, then `extractors_for(source, schema_version)` and the `[crossref]` field-path pairs are redundant with `raw_identifiers` and must be rewritten. The declared input tuple also changed (raw bundle + er.toml + liveness vs events + source registry + realm profiles) with no statement that it did.

#### Identifier kind catalog

**Part I.** §10.2 `RawIdentifier.class` is a closed schema enum of 19 values under `additionalProperties:false`: username, upn, email, uid, gid, sid, account_ref, token_hash, cred_hash, session_ref, device_ref, host_ref, container_ref, ip, mac, cert_fp, pid, service_name, resource_ref.

**Part II.** 60.1 defines a different closed catalog of 24 `IdKind`s: SID_WINDOWS, OBJECT_GUID, UID_POSIX, UPN_EMAIL, USERNAME, SERVICE_ACCOUNT, CLIENT_ID, TOKEN_JTI, REFRESH_TOKEN_ID, API_KEY_ID, SESSION_ID, CERT_FINGERPRINT, DEVICE_ID, HOST_NAME, MAC, CONTAINER_ID, POD_UID, IMAGE_DIGEST, PROCESS_KEY, IP_ADDR, USER_AGENT, DISPLAY_NAME, CONTAINER_NAME, plus PID_BARE in `er.toml [classes] hint`.

**Impact.** Neither catalog is a superset. Part I's `resource_ref`, `service_name`, `gid`, `cred_hash`, `account_ref` and `email` have no Part II IdKind, so identifiers for the `res`, `svc`, `api`, `role`, `grant`, `zone`, `netif` and `flow` entity kinds of §9.2 never become bindings and those entities are never resolved at all. Part II's OBJECT_GUID, CLIENT_ID, POD_UID, IMAGE_DIGEST and the PROCESS_KEY triple cannot be carried in a §10.2 `raw_identifiers` array without a schema MAJOR bump. Adapters written to Part I emit classes ER will not extract.

#### Representation of unresolved entities

**Part I.** §12.6: `UnresolvedId := "unres-" base32(BLAKE3_128(scenario_id LF kind_guess LF sorted_raw_identifiers))`, persisted with `resolution_state = "UNRESOLVED"`, carrying the raw identifiers and a reason code from the closed set `NO_RULE_MATCHED | AMBIGUOUS_PID | KIND_AMBIGUOUS | SPLIT_SUSPECT | REALM_UNKNOWN`. The UI renders 'unresolved: <reason>'.

**Part II.** 60.6: 'UNRESOLVED — a singleton with no qualifying merge', carrying an ordinary `ent:`-prefixed content-addressed id like any other entity, with no distinct prefix and no reason code field; `er.jsonl` per 60.8 carries 'EntityId, kind, status, bindings with intervals and evidence, ambiguity ids, display label'.

**Impact.** Unmarked. The `unres-` id space and the reason-code enum disappear with no replacement, so the §12.6 UI requirement ('unresolved: <reason>') cannot be satisfied and any consumer keying off the `unres-` prefix breaks. Part II also has no `kind_guess` concept, so the kind of a singleton is unspecified.

#### Whether an UNRESOLVED entity blocks an unflagged ROBUST verdict

**Part I.** §12.6: 'A derivation whose leaves include an unresolved entity is marked `ambiguous_entity` in the certificate flags, and such a run may not be presented as ROBUST without that flag shown.'

**Part II.** 60.9/60.11: `ROBUST` is blocked only when `corridor_ambiguities` is non-empty, an entity referenced by a corridor fact has status `AMBIGUOUS`, or an `ErFlags` bit is set. `ErFlags` is the closed set `{block_overflow, norm_collision, provisional_lease, budget_exhausted}` — nothing about UNRESOLVED. 60.6 states 'UNRESOLVED is not an error and is not a failure'.

**Impact.** Unmarked contradiction on the verdict gate. Part II's checker obligation 4 will pass a plain `ROBUST` certificate whose corridor facts are grounded on UNRESOLVED entities; Part I forbids presenting that run as ROBUST without the `ambiguous_entity` flag. The `ambiguous_entity` flag itself has no slot in Part II's `ErFlags`.

#### Attaching process events that carry only a bare pid

**Part I.** §12.3 R8: 'process.* with pid P on H at t, no exec observed -> attach to the unique proc with start<=t<exit; if not unique -> UNRESOLVED'. §12.8(3) mandates a regression fixture that reuses a pid within 200 ms and asserts UNRESOLVED rather than most-recent.

**Part II.** 60.1: '`PROCESS_KEY` is the triple `(host_entity, pid, start_time_ns)` — never the bare pid. A bare pid is a `HINT`.' `PID_BARE` is in `er.toml [classes] hint`, and 60.7 skips HINT pairs before rule evaluation ('if bindings[i].class == HINT || bindings[j].class == HINT { continue }'). The only process rule is 26 `process_key`, requiring an identical triple.

**Impact.** Unmarked capability removal. Under Part II a `process.file_read` or `process.setuid` record that carries only host+pid produces a HINT binding that can never attach to anything, so its `process_ref` cannot be filled — while §10.2's `allOf` makes `process_ref` required for `dimension: process`. Part I's R8 and its pid-reuse fixture become unimplementable; the events are not resolved to UNRESOLVED either, they simply never join a component.

#### Intra-record username-to-SID linking (R3)

**Part I.** §12.3 R3: 'authentication.* carrying both username and sid in one record -> link(username, sid) [same realm]'. §10.8's worked Windows 4624 example is built on exactly this pair (`TargetUserName: svc_backup` plus `TargetUserSid: S-1-5-21-77-1104`), and §12.8(6) lists R3 among the rules that require trustworthy inter-realm ordering.

**Part II.** 60.4's B7-based merge rules are enumerated by kind and cover only token-to-subject (11), session-to-subject (12), SA-key (14) and cert-to-subject (15). A `USERNAME`+`SID_WINDOWS` co-occurrence matches none of them; `USERNAME` can merge only via rule 21 (requires the two sides to already share an ANCHOR) or rule 22 (requires a second independent LINK), otherwise rule 41 `username_one_link` -> AMBIG.

**Impact.** Unmarked. The single most common real linking signal in Part I — a logon record naming both the account name and its SID — no longer produces a merge, so the §10.8 worked example does not resolve as documented. An implementer who adds the obvious `username_to_sid` rule is changing a hashed, ordinal-stable rule table (60.4) outside the spec.

### RESOLVED

#### EntityId derivation and format

**Part I.** §9.3: `EntityId := kind "-" b32`, where b32 = 16 chars RFC4648 lowercase base32 of BLAKE3_128(anchor_bytes), and anchor_bytes = scenario_id LF kind LF field_1 US ... US field_n using the per-kind anchor tuple from the closed table in §9.2 (e.g. `sess-k4m2q9x7t1b0dfe3`). §12.4 phase 5 builds the anchor from the component's highest-tier identifiers.

**Part II.** 60.0 and 60.5: 'OVERRIDES Part I sections 9-12: EntityId is not author-assigned and is not a closed catalog. It is derived and content-addressed.' `EntityKey(component) = BLAKE3(concat over sorted(bindings) of canonical_encode(binding))`, `EntityId = "ent:" || hex(EntityKey[0..16])` — 32 hex chars with an `ent:` prefix and no kind code, no anchor tuple, no scenario_id.

**Impact.** Marked override, but the override rationale misstates Part I (Part I ids are already content-addressed and deterministic, §9.3 bullet 1). The real change is the key material and the string shape. An implementer must retire the §9.2 anchor-tuple column entirely; every id-shaped regex, DB column width and UI id renderer built from Part I breaks. See the UNRESOLVED items on the event-schema pattern and on scenario_id.

#### ER output artifacts

**Part I.** §12.1: ER is a function to `(entity table, alias table, edge table, resolution report)`; §12.6 requires `resolution_report.json` publishing resolved/provisional/unresolved/split_suspect counts, merges per rule and largest component size; §12.7 requires an alias table.

**Part II.** 60.0: ER is 'a named, versioned, hashed pipeline stage with its own input, its own output artifact' — `er_resolve : (bundle_raw.jsonl, er.toml) -> (er.jsonl, er-mergelog.jsonl, er-report.json)`. 60.8 defines those three artifacts; there is no alias table, no edge table, no `resolution_report.json`.

**Impact.** The artifact rename is covered by the stated override, but nothing says the Part I alias and edge tables are retired or relocated (tracked separately as UNRESOLVED). `resolution_report.json` consumers must be repointed at `er-report.json`, whose count vocabulary differs (no provisional, no split_suspect).

#### PROVISIONAL interval endpoints must fail closed

**Part I.** §12.5 temporal conflict: 'Do not merge across the boundary'; §12.6 treats missing information as an UNRESOLVED entity, and §9.4 has a `PROVISIONAL` resolution_state that is a usable, non-blocking state.

**Part II.** 60.2: 'a merge whose licensing interval overlap depends on a PROVISIONAL endpoint MAY NOT produce RESOLVED. It produces AMBIGUOUS... OVERRIDES Part I: Part I lets missing telemetry widen the hypothesis space in the kernel while leaving ER free to guess; both stages now fail closed on the same liveness artifact.'

**Impact.** Marked override. Note the term collision it creates: Part I's `PROVISIONAL` is an entity resolution_state, Part II's `PROVISIONAL` is an interval EdgeKind with an unrelated meaning, and Part II deletes the state of the same name (see SILENT: status enum).

#### Caps degrade to uncertainty rather than dropping work

**Part I.** §10.2 caps `raw_identifiers` at `maxItems: 32` and `control_context` at `maxItems: 32` under `additionalProperties:false`; §12 has no candidate cap.

**Part II.** 60.3: `max_candidates_per_block`; 'If a block exceeds it, the block is NOT truncated — the whole block is marked BLOCK_OVERFLOW, every binding in it is marked AMBIGUOUS... OVERRIDES Part I: caps in Part I silently drop work; here a cap degrades to uncertainty, never to a guess.'

**Impact.** Marked override for the ER stage. It does not reach the §10.2 schema caps, which remain: a record with 33 identifiers still fails schema validation rather than degrading, so the 'never drop work' principle is enforced in ER but not at ingest.

#### ER quality measurement

**Part I.** §12.8 requires `over_merge_rate` and `under_merge_rate` per scenario, measured against generator truth, plus named regression fixtures (pid reuse within 200 ms, rotation-does-not-merge, adversarial identifier injection); §12.6 requires published counts.

**Part II.** 60.10: 'OVERRIDES Part I: Part I never measures ER.' It then defines a different, pre-registered metric set — pairwise precision/recall/F1, `false_merge_components`, `false_split_principals`, `ambiguity_rate`, `unresolved_rate`, `corridor_er_error`, `verdict_flip_rate` — published in `bench/er-quality.json` per degradation-matrix cell.

**Impact.** Marked override, but the premise is false: Part I does specify ER metrics. Because Part II asserts none existed, it never says `over_merge_rate`/`under_merge_rate` are retired. An implementer may build both metric families, or keep Part I's names as the reported headline while Part II's gates (G-ER-4) key off `false_merge_components`.

## 61 Degradation and tampering

### UNRESOLVED

#### Wall-clock time: banned by Part II, mandatory throughout Part I's harness

**Tension.** §61.4.2 states as a marked override that 'no perturbation, harness step or gate may sleep, poll, or consult a wall clock; a wall-clock-dependent delay would make matrix cells machine-dependent and break byte-identical replay', enforced by `make no-wallclock`, which 'greps the perturber and harness for clock APIs and fails on any hit outside an explicitly allowlisted logging path'. §61.10 adds that budget is in deterministic step units because 'a wall-clock budget would make cell inclusion machine-dependent'. §61.13 repeats 'Do not use wall-clock time ... in any perturbation decision'. Part I's harness is built on wall-clock: §48.3 `limits: {per_cell_wall_s: 900, total_wall_s: 43200}`; §48.4 item 12 samples loadavg before and after each cell and excludes `contended` cells from aggregates; item 13 requires `time.monotonic_ns()` and `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` for every cell; §48.6's `perf` block and the `TIMEOUT` status; §49.6's `throughput_eps`, `p50/p95/p99_query_ms` and `cost_per_1M`. Part II's prose ban is absolute over 'any harness step', its gate is scoped to 'decision paths', and it never mentions §§48.4-49.6.

**Decision needed.** Decide whether the clock ban is scoped to inclusion/selection decisions (in which case `no-wallclock` needs an explicit allowlist for the measurement path, and §48.3's wall budgets and §48.4's contention-based exclusion must be replaced by step-unit budgets) or is total (in which case the entire `perf` block, the latency percentiles, `throughput_eps`, `cost_per_1M` and the `TIMEOUT` status are withdrawn and §49.6 must be rewritten).

**Recommended.** Scope the ban to decisions, not measurement: forbid any clock read that can change which cells run, which rows enter an aggregate, or any byte of `cert.json`/`ledger.jsonl`, and allowlist `perf`-block instrumentation that is excluded from every hashed object (Part II already does this for host fields in §61.9.2). Then replace §48.3's `per_cell_wall_s`/`total_wall_s` and §48.4 item 12's contention exclusion with the §61.10 step-unit budget, since both currently make cell inclusion machine-dependent — the exact failure Part II names.

#### Two harnesses, two result stores, two provenance gates for the same numbers

**Tension.** §48.1 item 1: 'Build `bench/`, a single harness... Nothing else in the repo is allowed to produce a performance or accuracy number that appears in documentation.' §48.7 fixes the layout `bench/results/<run_id>/` with `results.jsonl`, `results.parquet`, `summary.json`, `certs/` and a committed `INDEX.json`; §48.8 requires every documented number to be rendered from `results.parquet` by `scripts/render_numbers.py` inside a GENERATED region, and `scripts/check_generated.py` fails if a region 'references a `run_id` absent from `INDEX.json`'; §29.6 requires the harness to take `--dataset <dataset_id>` only. §61.9.2 defines a different tree, `runs/matrix/<matrix_id>/` with `cell.json`, `metrics.json`, `index.jsonl`, `sampling.json` and `aggregate/`; §61.9.3 defines a different CLI, `spectra matrix run --spec matrices/nightly.toml`, which prints gate verdicts and yields; §61.10 defines a different docs gate, `make claims-bind`, which 'fails the docs build on a matrix-derived number with no `matrix_id` and no sampling disclosure'. Neither side mentions the other's store, id or gate.

**Decision needed.** Decide whether `spectra matrix run` is a front-end that writes into `bench/results/<run_id>/` (so `render_numbers.py` and `INDEX.json` stay authoritative and `matrix_id` becomes an extra column) or a second first-class harness (in which case §48.1's exclusivity clause and §29.6's `--dataset`-only rule must be amended to name it, and the two docs gates must be reconciled so a degradation number can satisfy both at once).

**Recommended.** Make the matrix harness a mode of `bench/`, writing one row per cell into `results.parquet` with `cell_id`, `matrix_id` and the §61.6 numerator/denominator pairs as columns, and extend `check_generated.py` to demand both `run_id` and `matrix_id` plus the sampling disclosure. Two independent stores means the zero-false-ROBUST gate can pass in one and fail in the other with no mechanism to notice. Also settle at the same time whether §48.4's Linux-only isolation (it refuses to start if `/sys/devices/system/cpu/intel_pstate/no_turbo` is unreadable or the governor is not `performance`) applies to matrix cells, because §61.9.1's `make matrix-crossrunner` requires a second CI runner 'with a different CPU and OS'.

#### The `arm` axis has no cell to live in

**Tension.** Part I's experimental unit is '(scenario, arm, seed, operator, completeness, repeat)' (§50.1, §48.6), with five arms (`rules`, `seqanom`, `spectra`, `graphonly`, `spectra_nolic`), a fairness contract enforced by projection functions (§49.2), an ablation table whose rows are configurations (§50.5), and figures P1 (facet per arm) and P6 (cols = arms, cell = median ΔF1 from `none`). §61.9.1's `cell_id` tuple is scenario + plan + targets + seed_index + ingest/er/rules/controls/goal/objective hashes + kernel and checker versions — no `arm`, no `repeat`, and no identity/`none` operator to take deltas from. §61.11's metric table has no detection metrics (no TP/FP, no F1) at all, and §61.0 forbids any other section from defining 'a matrix cell'.

**Decision needed.** Decide whether the baseline arms survive the rewrite. If they do, `arm` (and the `none` reference plan) must be added to §61.9.1's cell identity and the detection metrics must be added to §61.11, because no other section is permitted to define a cell. If they do not, §§49.1-49.2, §50.5 and figures P1/P6/P8/P9/P11 must be withdrawn, along with RQ1 and RQ4 in §51.2.

**Recommended.** Keep the arms — RQ1 and the `spectra_nolic` ablation are the only evidence that licensing is load-bearing — and add `arm` plus `repeat` to the cell tuple, with an explicit `none` plan as the delta reference. Note that Part II's move of perturbation upstream to raw records actually improves the fairness contract: every arm now receives the same perturbed bytes before any SPECTRA-specific processing, which is what §49.2 was trying to approximate.

#### Content-addressed EventIds vs. one anchored event per delivered line

**Tension.** §29.5 item 2: 'EventIds are assigned by the normalizer as `ev_ = blake3(canonical_event_bytes)[0:16]`, not by a counter, so ordering changes cannot shift ids', and §50.2 expects duplicates to be absorbed: 'SPECTRA flat if dedup by content hash works; any SPECTRA rise is a bug, file it'. §61.4.3 permits `byte_identical = true` duplicates, and §61.7.3's `anchor_map` gives the original and its duplicate two distinct event ids (`ev:000412` at line 881, `ev:000413` at line 882) while §61.7.3 requires `unanchored_events` and `orphan_lines` to be empty, with `make anchor-closure` failing the cell otherwise.

**Decision needed.** Decide how a byte-identical duplicate line is represented downstream. Either `origin{source,line_index}` enters the canonical event bytes (so the two lines get distinct EventIds, content-hash dedup stops working as §50.2 assumes, and `EventId` becomes perturbation-dependent, contradicting the stated reason for content addressing), or dedup collapses them (and the second line becomes an `orphan_line`, which fails `anchor-closure` and marks the cell INVALID). Part II also writes ids as `ev:000412`, which does not match §29.2's mandated `^ev_[0-9a-f]{16}$`.

**Recommended.** Keep content-addressed EventIds, and let `anchor_map` carry a many-to-one line-to-event mapping: allow several `origin` coordinates per `event_id`, with `orphan_lines` meaning 'a delivered line that reached neither an event nor quarantine' rather than 'a line without its own event'. That preserves §29.5's determinism property and keeps duplicate absorption measurable, but it must be written down explicitly, because §61.11's `phantom_derivations` (evidence set entirely synthetic) is computed off this mapping and silently changes meaning under either reading.

#### Ablation rows are expected to produce false ROBUST; the gate forbids any

**Tension.** §50.5 item 10: the ablation rows are real code paths run through the same harness, and 'the `− liveness` and `− backdating` rows are expected to produce nonzero false-ROBUST counts; that nonzero value is the evidence that those components are load-bearing. Report it.' §61.12's `zero-false-robust` gate is build-failing and unqualified: '`false_robust` is false for every RAN cell'. Part II's `gate-liveness-mutation` even requires that injecting a known deletion-detection bug turns `zero-false-robust` red — so a deliberately weakened configuration going red is Part II's definition of the gate working.

**Decision needed.** Decide how ablation and mutation cells are separated from the headline matrix. Either they are declared as a distinct stratum in `index.jsonl` with the gate scoped to exclude them (and the ablation table then reports their false-ROBUST counts as a result), or the ablation table is dropped and §50.5 withdrawn.

**Recommended.** Add an explicit `stratum: ABLATION` / `MUTATION` class to §61.10's strata, scope `zero-false-robust` to non-ablation RAN cells, and require the ablation strata to report a nonzero false-ROBUST count — a `− liveness` ablation that shows zero is itself a red flag and should fail its own inverted gate, which is exactly the `gate-liveness-mutation` pattern generalized.

#### Two files define the goal atom for a scenario

**Tension.** §28.1 puts `goal_atom: "data.exfiltrated(finance.records, actor_b)"` inside the scenario YAML, alongside `expected_verdict_full_telemetry: ROBUST` and `expected_min_cut_size`, and §28.3 makes the scenario file the single executable input shared by the simulator and the ground-truth emitter ('the simulator cannot perform a step that the file does not declare, and cannot declare a step it does not perform'). §61.8 requires the goal-atom-to-StepId binding to be authored 'ONCE per scenario, at scenario-freeze time' in `truth/objective.toml`, hashed into the cell identity, with `objective-freeze` comparing its last-modified commit against `rules.toml` and marking the scenario `TUNED` if inverted. Part II does not mention the scenario YAML's `goal_atom` field or `expected_verdict_full_telemetry`.

**Decision needed.** Decide which file owns the goal atom and what happens to §28.1's `goal_atom`, `expected_verdict_full_telemetry` and `expected_min_cut_size`. If `objective.toml` is authoritative, the YAML fields must become derived or be deleted, and a lint must assert they agree. Related: Part I names two disjoint held-out sets (S90..S94 for threshold tuning in §49.2, S80..S85 authored after the rule table in §51.4) and §61.10 requires 'every held-out scenario at its lowest declared target vector' as a mandatory stratum without saying which set is meant.

**Recommended.** Make `truth/objective.toml` authoritative, since it is the only one with a freeze check and the only one expressed over StepIds, and reduce the YAML `goal_atom` to a cross-reference validated by a lint. Then state explicitly that S80..S85 is the held-out set §61.10 protects from sampling, and that `expected_verdict_full_telemetry: ROBUST` in a scenario file is an expectation about a clean cell, not a substitute for `ACHIEVED_gt` — §61.8's negative requirement already forbids that substitution but does not name the YAML field that currently makes it.

### SILENT

#### Minimum seed count per reported cell

**Part I.** §49.7 item 14: 'Minimum `n = 10` seeds per reported cell. A claim resting on fewer is not publishable; the renderer emits `NOT REPORTABLE`.' §48.3 ships ten seeds (1001-1010) and §50.1's matrix is '10 seeds'. §48.8 item 25 makes the renderer refuse any scalar lacking `n` and a CI, and §49.7 mandates BCa bootstrap with 10 000 resamples plus Wilcoxon signed-rank tests, all sized for n=10.

**Part II.** §61.9.1: '`seed_index` ranges over a declared seed set of size `n_seeds >= 5` (illustrative, not a target: the repo ships 5 and nightly runs 20). A single run per cell is not a result; every reported quantity carries its per-cell median and IQR over `seed_index`, and never a mean alone.' Part II never mentions Part I's n=10 floor.

**Impact.** An implementer builds a five-seed matrix that satisfies §61.9.1 and then finds every number in it rendered as `NOT REPORTABLE` by the §48.8 renderer, or — worse — silently publishes five-seed BCa intervals that Part I declared unpublishable. Both floors are stated as hard rules and only one can be the floor.

#### Where telemetry comes from at all

**Part I.** §26.7: 'Do NOT generate telemetry inside SPECTRA's own code path. Every event must originate in a range service and traverse collector -> normalizer. Synthesizing an event directly into `bundle.jsonl` is forbidden outside `tools/fixture-mint`.' §26.3: `telemetry-collector` 'receives emitter frames, BLAKE3 sequence-chains per source, writes `raw.jsonl`'. §29.1: one `emit` primitive writes the event 'to the range service call path' and appends the truth annotation in one operation; §27.1: the population 'is materialized by calling the range services ... never by SQL inserts'.

**Part II.** §61.1's pipeline diagram starts at 'generator (seed, scenario)' writing `truth/emission.jsonl` and `raw/clean/<source>.log` — 'pristine raw records, byte-stable' — which the perturber reads and rewrites into `raw/pert/<source>.log` for ingest. There is no range, no collector and no `raw.jsonl` in the diagram, and §61.7.1 requires a generator-assigned `record_id` and `emit_time_ns` on every emitted record.

**Impact.** These are two different provenance architectures and Part II never says it is replacing Part I's. Part I's sixteen live containers cannot produce byte-stable per-source raw log files with generator-assigned record ids, and Part I forbids producing telemetry any other way. An implementer reading Part I alone builds the Docker range and then finds nothing in the repo writes `raw/clean/<source>.log`, which is the input every gate in §61 is defined over.

#### Every source is hash-chained (Part I) vs. at least one source must be BARE (Part II)

**Part I.** §26.3 gives one collector for all sixteen SourceIds and its role is 'BLAKE3 sequence-chains per source' — chaining is a property of the collector, so every source has it. `range/sources.toml` is described as the authoritative source list with no observability attribute, and §28.2 SC-16 relies on a BLAKE3 chain break to produce a SUPPRESSED liveness basis.

**Part II.** §61.5: 'Every source declares `chain_class` in `sources.toml`: `CHAINED` (BLAKE3 sequence chain), `BRACKETED` (periodic heartbeat, no chain), `BARE` (neither). At least one source in every scenario MUST be `BARE`.' §61.2's `plan-lint-sources` fails the build if any named source lacks a `chain_class`, and §61.10 makes 'at least one `BARE`-only cell per scenario' a mandatory-included stratum.

**Impact.** Part II's central honesty argument — that the OBS-N region is real and must be measured — depends on sources that have no chain and no heartbeat. Part I's collector architecture makes that unbuildable: an implementer following §26.3 chains everything, every deletion becomes OBS-C, and the `invisible_class_volume` artifact that `LIMITATIONS.md` is generated from comes out empty, which would read as a much stronger result than the system supports.

#### Resealing a hash chain after a deletion (Part I's `forge_provenance`)

**Part I.** §50.2 defines `forge_provenance` as 'rewrite BLAKE3 sequence-chain links so a deletion looks like a clean chain', intensity = fraction `p` of chains forged, attacking SUPPRESSED detection, measured by 'chain-break detection rate, misclassification BLIND vs SUPPRESSED vs LIVE', with the mandate to 'document explicitly the forgery class SPECTRA cannot detect'. §48.3 lists `forge_provenance` in the manifest operator set.

**Part II.** §61.4.8 `CHAIN-FORGE` is defined only as fabrication: params `count`, `window_ns`, `template`, `reseal`, and 'insert `count` fabricated records into the chosen window and, with `reseal = true`, recompute the BLAKE3 sequence chain from the insertion point forward so no sequence gap is visible.' §61.4.0 fixes DELETE at position 2 and CHAIN-FORGE at position 6 with no operator that reseals a chain around deleted records without inserting new ones. Part II's §61.0 explicitly names only 'suppress' as a retired Part I operator word.

**Impact.** The operator that makes a deletion invisible on a CHAINED source has no Part II equivalent, so in §61.5's matrix DELETE is OBS-C on every chained source and the 'forgery class SPECTRA cannot detect' experiment disappears. An implementer mapping `forge_provenance` onto `CHAIN-FORGE` will believe they have kept the experiment while actually having replaced 'hide a deletion' with 'add records', and SC-16's suppression-assisted intrusion loses its adversary.

#### Degraded datasets as versioned children with an edited truth stream

**Part I.** §29.4: degraded variants set `parent` to the base `dataset_id` and carry the parent's `truth.jsonl` 'unchanged except that dropped events acquire `suppressed_by: "degradation"`'. §29.3 gives `dataset.parent_dataset_id` for 'degradation lineage' and `truth_annotation.suppressed_by`. Invariant I-5, build-failing, checked by `make dataset-verify`: 'every degraded dataset's `truth.jsonl` differs from its parent's only in `suppressed_by` fields'. §29.5 ships `make dataset-degrade` and `make dataset-matrix`.

**Part II.** §61.7 records what perturbation did in `truth/ledger.jsonl`, a separate artifact written after operator step 9 with a closed set of fates, and leaves `truth/emission.jsonl` and `truth/steps.jsonl` untouched — the anchor is 'IMMUNE to every operator in 61.4 because no operator can see it'. There is no degraded dataset, no `parent_dataset_id` for degradation, no `suppressed_by` write-back, and per §61.9.2 the per-cell artifacts live under `runs/matrix/<matrix_id>/cells/<cell_id>/`.

**Impact.** Part II never retires I-5, `make dataset-degrade`, `make dataset-matrix` or the `suppressed_by` column, all of which are build-failing or shipped targets in Part I. Worse, writing `suppressed_by` per dropped event requires exactly the EventId-keyed truth that §61.0 bans, so an implementer trying to satisfy both produces a truth stream that the perturbation destroys.

### RESOLVED

#### Ownership of the degradation model (catalog, plan format, seed derivation, matrix definition)

**Part I.** Degradation is defined in pieces across the lab and bench sections: §29.4 defines a `degradation` manifest block with `operators` and `operator_config_hash`; §29.5 ships `make dataset-degrade COMPLETENESS=0.70 DSEED=7710` and `make dataset-matrix`; §48.3 defines the operator list and the per-cell seed as `seed_cell = blake3(seed || scenario_id || arm || operator || completeness)[0:8]`; §50.1-50.2 define the cell, the composition rule and the 11-row operator catalog.

**Part II.** §61.0: 'OVERRIDES Part I: degradation is no longer an implementation detail smeared across the lab sections (26-29) and the bench sections (48-51). The operator catalog, the seed discipline, the completeness definition, the matrix harness and the ground-truth relinking are specified here and are a versioned, hashed data artifact... No other section may define a perturbation operator, a completeness number, a matrix cell, or a ground-truth link.' §61.2 makes the plan a hashed TOML file with a JSON Schema; §61.3 replaces the seed derivation with per-operator named streams `BLAKE3_keyed(root_seed_32, cell_id || 0x1F || stream_key)` fed to ChaCha20, so that adding or reordering an operator does not shift another operator's draws.

**Impact.** Part I's `seed_cell` formula keys on `arm`, `operator` and `completeness` — two of which no longer exist as cell coordinates under Part II. An implementer who keeps §48.3 item 4 will produce a seed discipline that (a) collides across Part II's multi-stream operators and (b) shifts every draw when a plan gains an operator, which `make perturb-determinism` is written to catch.

#### Where perturbation is applied: raw source records vs. bundle.jsonl

**Part I.** §50.1 item 3: 'Every operator is a pure function `apply(bundle, seed, intensity) -> (bundle', truth_delta)`.' §29.4: a degraded dataset 'is a deterministic transform of the parent's `bundle.jsonl` plus the parent's `truth.jsonl`'. Operators therefore act on canonical, entity-resolved events after `EventId` assignment.

**Part II.** §61.1: 'Perturbation is applied to serialized RAW SOURCE RECORDS, before parsing, before canonicalization, before entity resolution, before `EventId` assignment. It is never applied to `bundle.jsonl`.' §61.13 repeats it as a negative requirement, and `make dep-audit` fails if the perturber's dependency closure touches the ER crate or the kernel.

**Impact.** Every Part I operator signature, the `truth_delta` return value, and the whole idea of a 'degraded bundle' are void. CORRUPT and STRIP-IDENTITY only make sense pre-parse (they must be able to produce parser rejects that land in `quarantine.jsonl`), which is impossible if the operator input is already a parsed bundle.

#### Scalar 'completeness' as an axis

**Part I.** Completeness is a first-class scalar everywhere: §48.3 manifest `"completeness": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]`; §48.6 row granularity includes `completeness` and the DuckDB DDL declares `completeness DOUBLE NOT NULL`; §29.4 `"degradation": {"completeness": 0.70, ...}`; §29.5 `make dataset-matrix # 100,90,80,70,60,50,40,30`; invariant I-1 'across the whole 100%->30% matrix'; plots P1, P2, P3, P4, P5 and P7 all use completeness as an axis.

**Part II.** §61.0: 'OVERRIDES Part I: the phrase "100%..30% completeness" as a single scalar is withdrawn everywhere in the repository. It was undefined (share of records? of sources? per dimension?) and any aggregate form of it is now forbidden output.' §61.6 replaces it with four quantities — `record_retention(src)`, `record_retention(dim)`, `source_coverage`, `step_witness_coverage(dim)` — all reported per dimension and per source as exact `(numerator, denominator)` pairs, all measured after the fact, with target vs. realized values both recorded in `cell.json`.

**Impact.** Six of the twelve mandated figures in §50.6 have an x-axis that no longer exists, and the normative Parquet schema has a NOT NULL column for a withdrawn quantity. §61.6 also makes the point that matters for the invariant: `step_witness_coverage` is not derivable from `record_retention` — 2% of records deleted can drive it to zero on a dimension while retention reads 0.98 — so Part I's completeness sweep could report 0.98 for a cell where the chain is entirely unwitnessed.

#### Ground-truth key: EventId vs StepId

**Part I.** §29.2 `TruthAnnotation` requires `event_id` matching `^ev_[0-9a-f]{16}$`; §29.3 enforces `CREATE UNIQUE INDEX truth_event_uniq ON truth_annotation (dataset_id, event_id)`; §49.5 defines `E_true` as 'the set of ground-truth malicious EventIds' and computes `evidence_coverage`/`evidence_precision` against it.

**Part II.** §61.0: 'OVERRIDES Part I: generator ground truth may no longer be expressed over `EventId`s. Perturbation rewrites, duplicates, reorders and deletes the exact records that carry them, so an `EventId`-keyed ground truth is destroyed by the very experiment it is supposed to measure. Ground truth is keyed on generator-side causal step identifiers that never enter telemetry.' §61.7 defines `StepId`, `truth/emission.jsonl`, `truth/steps.jsonl`, and a physical `(source, line_index)` ledger join producing `truth/anchor_map.json`; §61.13 forbids linking truth to telemetry 'by content, by timestamp, by entity, or by `EventId`'.

**Impact.** Part I's truth table, its unique index, and the `evidence_coverage`/`evidence_precision` metrics (§48.6 schema, §49.5, §50.2 expected-curve column) are all built on the banned key. Part II supplies `anchor_recall`, `ghost_covered` and `phantom_derivations` instead but never restates `evidence_coverage`, so those Part I schema fields are orphaned.

#### The operator word 'suppress'

**Part I.** §29.4 lists the degraded-dataset operators as `["delete","delay","duplicate","reorder","corrupt","suppress"]`, and §29.2 has a `suppressed_by` enum of `[null,"degradation","scenario_actor"]`, treating suppression as one undifferentiated operation.

**Part II.** §61.0: 'OVERRIDES Part I: the Part I operator word "suppress" is ambiguous and is retired. It is replaced by three distinct, separately parameterized, separately seeded operators: `DELETE`, `SOURCE-SILENCE` and `STRIP-IDENTITY`.' §61.4.9 draws the distinction that the single word erased: `WHOLE_SOURCE_BLACKOUT` deletes records that were emitted, `SOURCE-SILENCE` models a collector that never produced them, and its `announce` parameter (NONE / GAP_MARKER / HEARTBEAT_STOP) decides whether the outage is self-evident at all.

**Impact.** The three replacements have different observability classes (§61.5): `SOURCE-SILENCE` with `announce = NONE` is OBS-N on a CHAINED source while `DELETE blackout` is OBS-C. An implementer who keeps one 'suppress' operator cannot report the invisible-class volume the LIMITATIONS artifact is generated from.

#### Measuring only false ROBUST

**Part I.** §50.7 item 13 makes the single headline gate 'the count of rows with `eclipse_verdict = ROBUST` and `block_miss = 1` must be exactly zero'; §51.2 RQ3 is 'Certificates are never falsely ROBUST under degradation'; §50.3 treats ROBUST mass migrating into OPTIMISTIC_ONLY and UNSAFE as the validating shape. No false-UNSAFE quantity is defined anywhere.

**Part II.** §61.11: '`false_unsafe` is mandatory, not optional. OVERRIDES Part I: measuring only false ROBUST makes the headline gate passable by returning UNSAFE, and the blindness premium is precisely the quantity a false-UNSAFE bias inflates. Both rates are published side by side, per cell and per dimension.' §61.12 adds the `robust-yield-floor` gate: the fraction of cells where the oracle says the cut holds and the kernel says ROBUST must be at or above a declared floor, explicitly to prevent `return UNSAFE` from passing `zero-false-robust`.

**Impact.** A Part I-only implementation can pass its flagship invariant with a kernel that never emits ROBUST, and its §50.3 'verdict migration' figure would read as a success while showing exactly that.

#### Skipped vs. sampled-out matrix cells

**Part I.** §50.1 item 1 describes the full matrix 'minus operator/completeness combinations excluded below' and says only 'publish the exact executed cell count'. Failed cells are written as rows (§48.6 item 16) but excluded-by-design combinations have no row at all.

**Part II.** §61.10: 'OVERRIDES Part I: a cell may be sampled out, never silently skipped.' `index.jsonl` carries one row for EVERY DECLARED cell with `status: RAN|EXCLUDED|INVALID` and a reason; `make matrix-accounting` fails if the row count differs from the declared cell count. Budget is in deterministic step units, selection is deterministic by `cell_id` sort with largest-remainder rounding, mandatory-included strata (every BACKDATE cell, every CHAIN-FORGE cell, every red-team fixture, every `respect_obligations = false` plan, at least one BARE-only cell per scenario) are never subject to budget, and a failed cell is recorded `status: INVALID`, 'never dropped'.

**Impact.** Under Part I the adversarially-important cells are exactly the expensive ones most likely to be excluded, and nothing records that they were.

#### Pooling results across sources of different detectability

**Part I.** §49.5 instructs 'report per dimension ... as well as pooled'; §50.2's `forge_provenance` row measures a single pooled 'chain-break detection rate'; §50.6 P6 is a heatmap of median ΔF1 with rows = operators and cols = arms, pooled over all sources.

**Part II.** §61.5: 'OVERRIDES Part I: results that rely on chain-detectable suppression must be reported per `chain_class` and never pooled; demonstrating deletion detection only on chained sources and presenting it as a result about suppressed telemetry is disallowed.' §61.13 repeats: 'Do not pool results across `chain_class`. Chained-source results do not transfer to bare sources.' The §61.5 matrix shows why: DELETE is OBS-C on CHAINED and OBS-N on BARE — the same operator is trivially detectable on one source class and invisible on another.

**Impact.** P6 as specified in Part I is a forbidden artifact: one number per (operator, arm) cell averages a detectable and an undetectable regime together.

## 62 Ground truth and oracles

### UNRESOLVED

#### Checker independence: Part II offers a choice one branch of which Part I forbids by gate

**Tension.** Part I hard-codes the handwritten branch. §25.2 CI gate `gates/checker_independence.sh`: "the Go module's `go.mod` has no cgo, no FFI, **no generated-from-Rust sources**; `go list -deps` must not include any path under `crates/`." §25.1 calls it "an independently written checker"; §25.8(d) requires the checker to recompute liveness "from the bundle (it does not trust the file)". §44.11 generalizes: "Do NOT let a differential test pass by having both sides call the same library." Part II §62.5.1 instead says "Decide explicitly and record the decision in the certificate" and presents I-A (HANDWRITTEN) and I-B (GENERATED) as live alternatives. Choosing I-B — "The Go grounder is emitted from the same guard AST" — violates §25.2's no-generated-sources gate outright and makes §25.1's "independently written" a banned phrase under §62.5.3. Choosing I-A conflicts with §22.3's "One grammar, one parser (`crates/spectra-guard`)", since §62.5.2 requires the Go module to contain "its own guard-expression lexer, parser, type checker, evaluator, liveness derivation and semi-naive grounder". Part II states the cost of I-A but does not pick a branch, and does not say what happens to §25.2's gate under either.

**Decision needed.** Choose I-A or I-B for this build, and state explicitly which Part I artifacts are repealed: under I-B, §25.2's `gates/checker_independence.sh` and every "independent checker" claim in §25.1/§25.8; under I-A, §22.3's one-parser rule and the budget for a second grounder plus `gate:guard-difffuzz` and `gate:grounding-difffuzz`.

**Recommended.** Pick I-A and amend §22.3 to say "one parser per implementation, two implementations". I-B collapses Oracle C to certificate-relative validation, and since §62.3.1 already says only Oracle R falsifies a claim about the world and §62.4.9 expects Oracle R to cover a minority of scenario families, I-B would leave most of the matrix with no independent check of any kind.

#### Fate of Part I's Haskell admissibility oracle under the four-oracle taxonomy

**Tension.** Part I builds a fifth oracle that Part II's taxonomy does not contain. §25.2 layout reserves `reference/admissibility/` ("Haskell: reference license-admissibility checker"); §25.12.4 `haskell_admissibility_diff` runs a differential over 5k generated liveness scenarios, "any divergence fails"; §44.4 specifies it as "an independently written, deliberately naive implementation ... written from the specification text, not from the Python or Rust source", CODEOWNERS-protected, with `tools/lint/oracle_isolation.py` asserting no shared first-party dependency, and 10,000 agreeing cases per run; §43.2 gives Haskell an 85% coverage gate. Part II §62.0 states "validation is now carried by four named oracles (62.3-62.7)" and §62.3.2 makes `oracles_applied` a subset of `["R","C","S","M"]`. The Haskell oracle appears nowhere in §62 and has no letter.

**Decision needed.** Is the Haskell admissibility differential retained, and if so where does it sit — folded into Oracle C, given its own letter in the `oracles_applied` enum, or deleted? If deleted, say so explicitly, because it is currently the only Part I check with genuine written-from-spec implementation independence on license admissibility, which is exactly the property §62.5.3 says Oracle C loses under I-B.

**Recommended.** Retain it and give it a letter (e.g. Oracle H) with declared strength between C and S, or state in §62.3 that it is subsumed by `gate:grounding-difffuzz` under I-A. Silently dropping it removes the strongest independence evidence in the build while §62.3.1 is simultaneously tightening what C, S and M are allowed to claim.

#### Which telemetry artifact is normative: the live range or the seeded synthetic generator

**Tension.** Part I §26 opens: "The range is the only place SPECTRA telemetry comes from." §26.7: "Do NOT generate telemetry inside SPECTRA's own code path. Every event must originate in a range service and traverse collector -> normalizer. Synthesizing an event directly into `bundle.jsonl` is forbidden outside `tools/fixture-mint`, which stamps `synthetic_bypass: true` and **which the ECLIPSE kernel refuses to accept as evidence**." §27.1 has the population generator drive "the range through its real APIs ... never by SQL inserts", and §29.5's bit-identical `make dataset-reproduce` gate regenerates `bundle.jsonl` from a cold range-up. Part II §62.4.4 inverts this: "byte-identical replay is required of the seeded synthetic generator, the kernel and the checker; it is NOT required of the range, and the range's bundles are non-normative. Every range artifact is stamped `normative: false`." §62.1.1 likewise has "the scenario generator" emitting `groundtruth.json` beside `bundle.jsonl`. Part II's override is written as if there were two ranges — a deterministic generation path and a live Oracle R re-execution range — but Part I defines exactly one, and it is both.

**Decision needed.** State whether the build has one range or two. If two, name them separately and say which one §29.5's bit-identical determinism gate and §26.3's SourceId liveness table apply to. If one, say explicitly whether §29.5's `make dataset-reproduce` bit-identical requirement survives, and whether §26.7's rule that the kernel refuses synthetically-minted bundles as evidence is repealed — because every HELD_OUT matrix cell in §62.8.3 runs on generator-produced bundles.

**Recommended.** Split them explicitly: a deterministic dataset-generation range (normative, keeps §29.5's bit-identical gate) and a separate control-parameterized Oracle R re-execution range (non-normative, stamped `normative: false`, exempt from byte-identity). Then amend §26.7 so that generator output is not treated as `synthetic_bypass` evidence, or the kernel will refuse the very bundles the validation protocol depends on.

#### Mutation testing: does Oracle M replace or supplement Part I's mutmut/cargo-mutants gate

**Tension.** Part I §43.5.4: "Mutation testing is the real gate on the kernel. Run `mutmut` on `spectra/eclipse/` and `cargo-mutants` on `crates/eclipse-kernel/`; required surviving-mutant ratio <= 10%. Mutation runs nightly, not per-PR; the score is committed to `docs/testing/mutation.json` and regressions of more than 3 points fail the nightly." Part II §62.7.1: "`make mutate`, which applies each mutant below to a pristine tree, runs the named gate, and asserts the gate FAILS. A surviving mutant fails the build. Kill rate below 100% of the mandatory catalog fails the build," over a hand-authored 15-mutant catalog committed as patches under `validation/mutants/` and applied by `git apply` (§62.7.2). The two suites have different populations (automated source mutation vs a curated catalog) and irreconcilable standards (10% survivor tolerance vs 100% kill), and Part II never mentions §43.5.4.

**Decision needed.** Does Oracle M replace §43.5.4's automated mutation gate, or run alongside it? If alongside, confirm the ≤10% survivor tolerance and the 3-point regression rule still apply to the automated suite while the curated catalog requires 100%. If it replaces it, say so, since §43.5.4 is described as "the real gate on the kernel" and covers code paths the 15-mutant catalog does not touch.

**Recommended.** Keep both, and say so in one sentence in §62.7: the curated catalog at 100% kill proves each named gate is alive; the automated suite at ≤10% survivors measures coverage of the kernel source. They answer different questions, and §62.7's own framing — "that the gates are ... not inert" versus "that the gates are sufficient" — is exactly the distinction.

#### Whether HELD_OUT scenarios may carry Part I's authored expected results

**Tension.** Part I authors the answer into the scenario file and gates on it. §28.1's scenario carries `expected_block_points` (control, level, `blocks_at_step`, mechanism), `expected_verdict_full_telemetry: ROBUST` and `expected_min_cut_size: 1`; §28.3.3 makes the build fail unless every `expected_block_points` row "is reproduced by the concrete simulator at the stated level and not at level-1, including the `null` rows"; §28.2 designates SC-14 and SC-16 as "the ECLIPSE showcases" with SC-14 required to have `expected_min_cut_size: 2`. Part II §62.10.1 requires HELD_OUT scenarios to be "authored and hash-committed BEFORE the rules hash it will be evaluated under" and §62.2.4 forbids the scenario author from also picking the goal because "[they] can tune the cut to a hand-picked target". An authored `expected_min_cut_size` and a build gate that fails until the rules reproduce it is the same failure mode one level up, and §62.10.3's `gate:leakage` would auto-relabel any such scenario TUNED the moment the rules hash moves.

**Decision needed.** May a HELD_OUT scenario carry `expected_verdict_full_telemetry`, `expected_min_cut_size` and `expected_block_points`, and does §28.3.3's build gate still run against HELD_OUT scenarios? If yes, say in writing that HELD_OUT means "rules frozen before the scenario" and not "outcome unknown to the author". If no, §28.3.3 and §28.2's showcase designations must be restricted to DEV.

**Recommended.** Restrict §28.1's expected-result fields and §28.3.3's gate to DEV and RED scenarios, and let HELD_OUT carry only §62.1.5's `declared_sufficient_cuts` / `declared_insufficient_cuts` — which §62.8.4 already labels model-internal. Otherwise §62.10.1's held-out claim is hollow: SC-14 and SC-16 are, by §28.2's own wording, scenarios built to demonstrate a specific ECLIPSE result.

#### Suppression class as a matrix axis Part I's dataset pipeline does not produce

**Tension.** Part II §62.8.3 scopes the headline gate over "`HELD_OUT scenarios x completeness 100%..30% x suppression classes S0-S3`" and §62.11.1 reports "suppression class S4 frequency 0.11 S5 frequency 0.03" as measured per-cell rates. Part I's degradation matrix has one axis: §29.5 `make dataset-matrix PARENT=base-14d-v1 # 100,90,80,70,60,50,40,30`, produced by six operators (`delete, delay, duplicate, reorder, corrupt, suppress`) under a single `degradation_seed`, and §29.2's truth schema records suppression as a three-valued field `suppressed_by ∈ {null, "degradation", "scenario_actor"}`. Nothing in Part I classifies a deletion as bulk-window vs chain-break vs sparse-busy vs unchained vs invisible. Compounding this, Part II places `suppression_class` in `groundtruth.json` (§62.1.3), which §62.1.1 says is emitted "before any degradation operator runs" — yet the class is a property of what the degradation operator did to which source, and §62.11.1 reports it as an observed frequency.

**Decision needed.** Decide whether `suppression_class` is (a) an authored per-scenario property fixed before degradation, or (b) a per-cell classification computed by the degradation operator from the source's chain and bracketing guarantees. Then specify which component computes it, and extend §29.5's `make dataset-matrix` with the second axis so the §62.8.3 gate scope is actually generatable.

**Recommended.** Make it (b), computed by the degradation operator and written to a per-cell sidecar, and keep `groundtruth.json` free of it — a field that §62.1.1 forbids the degradation stage to influence cannot record what degradation did. Then declare the source-class inputs it needs (chain present, bracketing guarantee present) in `range/sources.toml`, which §26.3 already makes the authoritative source table.

#### Status of the `greedy_cover` flag

**Tension.** Part I §25.9 and §44.9 both name exactly three flags that force a non-ROBUST verdict: `grounding_capped`, `subset_minimal_only`, `greedy_cover`. §25.6.G sets `flags.greedy_cover = true` whenever the decisive-observation search exceeds size 3 and falls back to greedy set cover with an `ln n + 1` guarantee. Part II §62.8.5 re-enumerates the soundness-affecting set as "`grounding_capped`, `er_ambiguous`, `subset_minimal_only` is NOT soundness-affecting" — adding a flag Part I does not have, explicitly demoting one, and omitting `greedy_cover` entirely. `gate:nonvacuity-flags` (§62.9.4) computes `flagged_share` over "runs with any soundness-affecting flag", so the set must be closed and definite for that gate to be implementable.

**Decision needed.** Publish the closed list of soundness-affecting flags used by `gate:nonvacuity-flags` and by the ROBUST-eligibility rule, and state for each of `grounding_capped`, `greedy_cover`, `subset_minimal_only`, `er_ambiguous` whether it downgrades the verdict, counts toward `flagged_share`, both, or neither.

**Recommended.** `greedy_cover` bounds only the decisive-observation set (§25.6.G), not the cut or the verdict, so treat it like `subset_minimal_only`: move it out of the soundness-affecting set into its own reported field, and say so explicitly in §62.8.5 rather than by omission. Also add `er_ambiguous` to §25.7's certificate `flags` object, which currently has no such field.

### SILENT

#### `subset_minimal_only` reclassified as not soundness-affecting

**Part I.** §25.9: "A run with ANY flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) MUST NOT be presented as ROBUST." §44.9 restates it as a build assertion: "assert that every run carrying `grounding_capped`, `subset_minimal_only` or `greedy_cover` in `flags` reports a mode other than ROBUST." §25.13 repeats "Any result from a flagged run presented as ROBUST" as a forbidden claim.

**Part II.** §62.8.5, parenthetically and with no OVERRIDES marker: "A run whose certificate carries any soundness-affecting flag (`grounding_capped`, `er_ambiguous`, `subset_minimal_only` is NOT soundness-affecting, see 62.5.5) cannot be ROBUST." §62.5.5 moves minimality out of the flags entirely into a separate `minimality` field precisely so it no longer downgrades safety.

**Impact.** Directly contradictory and unmarked. An implementer reading §25.9 and §44.9 downgrades every subset-minimal run to OPTIMISTIC_ONLY with a grey badge; Part II expects those runs to be ROBUST with `minimality: PSI_RELATIVE`. Because §62.5.5 makes PSI_RELATIVE the normal case, the Part I behaviour would downgrade nearly every certificate — which then fails Part II's own `gate:nonvacuity-yield` robust-yield floor (§62.9.2) and inflates `flagged_share` against the §62.9.4 ceiling. The same sentence also introduces a flag, `er_ambiguous`, that does not exist in §25.7's three-flag certificate schema.

#### Oracle S / Z3 differential coverage shrinks from every fixture to tiny instances

**Part I.** §44.10: "The test encodes Ψ and asserts Z3 finds no model of cardinality `< |S|`, cross-checking the branch-and-bound result on every fixture with `|A| <= 64`." Since §22.2 caps the whole atom budget at 64, that is every fixture. §25.12.5 states Z3 "computes the true minimum cut; the kernel must match cardinality exactly."

**Part II.** §62.6.3: "Bounds are declared, small, and enforced by a harness assertion, not by hope. Illustrative bounds: instances <= 400, |A| <= 12, cuts enumerated exhaustively." §62.6.4: Oracle S "certifies only that the Rust solver's answer on small instances matches an encoding-independent solver. It certifies nothing about the rule semantics, nothing at production scale."

**Impact.** Unmarked and material. §44.10 promises SMT corroboration of the minimality claim across the whole fixture set; §62.6 caps it at instances two to four orders of magnitude smaller. An implementer who builds §44.10 as written will attempt exhaustive cut enumeration over 2^64 masks. More importantly, the two sections support different public claims: under §44.10 the kernel's minimality is SMT-checked everywhere; under §62.6.4 it is checked only on toy instances, and §62.5.5's `EXHAUSTIVE` marking cannot rest on Oracle S at production size.

#### Multi-goal scenarios versus the single-goal loader constraint

**Part I.** §23.2: "Constraints the loader enforces: exactly one `goal: true` step." §25.3 lists `goal.toml` as carrying "goal atom" (singular) and horizon `k`; §25.7's certificate has one `mode` and one `cut`; §28.1's scenario file carries a single scalar `goal_atom`.

**Part II.** §62.2.5: "Multi-goal scenarios carry a goal set; verdicts are emitted per goal atom. Aggregating goals into a single verdict, a count, a ratio or a score is forbidden." §62.1.3's ground-truth schema likewise has `attack_plan.goal` as a single object, but §62.2.2/62.2.3 speak of "goal kinds" appearing "as a goal in any scenario" across a set.

**Impact.** Part II introduces a scenario class Part I's loader hard-rejects at load time, and never says the `exactly one goal: true step` constraint is lifted. An implementer building §23.2 as written cannot load a multi-goal scenario at all; one who lifts the constraint must also decide how §25.7's single-verdict certificate and §24.6's single outcome classification become per-goal, which neither part specifies.

#### Observability modeled as a control threshold atom

**Part I.** Part I models observability as a telemetry-source property, not a control. §26.3 lists `iam_audit` as a SourceId emitted by identity-service. §22.6's catalog has exactly fifteen controls and none is `iam_audit`. §22.5: "`degrade` and `detect` gates MUST NOT contribute blocker bits to ECLIPSE (they do not sever a corridor)." §22.8: "Do NOT add a control whose only gate is `effect: detect` and then let it appear in an ECLIPSE cut." §25.6.G treats observability as the *decisive observation* set, deliberately outside the cut: "enable `iam_audit` over `[t1,t2]` (40 minutes) and `credential_rotation` leaves the cut."

**Part II.** §62.4.2 requires `range/enforcement.toml` to bind "every threshold atom" and states "Every atom in `controls.toml` MUST have an entry," then lists `[atom."iam_audit>=1"]` with `kind = "OBSERVING" # changes telemetry, never blocks a step`. §62.1.3's ground truth carries a separate `observability` map, and §62.1.3's `blocked_by` cites `mfa_step_up>=1` while `declared_insufficient_cuts` cites `credential_rotation>=1` — neither is a §22.6 control id (Part I has `mfa` with a `stepup_on_privilege` level and `cred_rotation`).

**Impact.** Unmarked structural change. If `iam_audit>=1` is genuinely an atom in `controls.toml`, it consumes §22.2's hard `Σ_k m_k ≤ 64` budget (16 SourceIds in §26.3 would eat a quarter of it), and §22.8's ban on non-severing controls appearing in a cut has to be reconciled with a new OBSERVING kind that §62.4.3 does not exclude from cuts the way it excludes `NONE_MODELED`. If it is not an atom, then "every atom in controls.toml MUST have an entry" and the OBSERVING kind are describing something the control compiler will never emit, and `gate:enforcement-total` cannot be satisfied as written.

### RESOLVED

#### Simulator-vs-kernel agreement demoted from correctness gate to codegen regression test

**Part I.** 13-verification / 07-replay §25.12.1 `sim_kernel_agreement` is a build-failing test-plan item: "256 randomized control configurations per fixture; ... the concrete simulator's outcome and the kernel's reachability under the same cut MUST agree on goal-reachability. Disagreement is a P0 bug." §28.3.4 repeats it as a per-scenario build requirement, and §24.8 calls the brute-force sweep "the honest, brute-force complement to ECLIPSE; section 25's test plan uses it as the cross-check oracle."

**Part II.** §62.0: "OVERRIDES Part I: the simulator-vs-kernel agreement test is DEMOTED from a correctness gate to a codegen regression test named `gate:codegen-regression`. It may never be described as validation, in docs, in README, in commit messages or in CI job names. The word `oracle` is forbidden for it." Rationale: both artifacts are lowered from one guard AST (§22.3), so agreement only proves compiler self-consistency.

**Impact.** An implementer must rename the CI job, strip the word "oracle" from §24.8's sweep description (`gate:banned-phrases` in §62.11.3 greps CI job names), and stop counting this as evidence of correctness. Collateral Part II does not address: §25.12.6 `brute_force_cross_check` (sweep enumerates every config; kernel's S_opt must be a true minimum) is also simulator-vs-kernel agreement, and it is the only Part I check on minimality at fixture scale. Its gate status is left unstated.

#### Ground truth keyed by AnchorId, not EventId

**Part I.** §29.2 `TruthAnnotation` requires `truth_id` and `event_id` on every row; §29.3 DDL puts a unique index on `(dataset_id, event_id)`; §29.4 says a degraded dataset carries the parent's `truth.jsonl` through unchanged "except that dropped events acquire `suppressed_by: \"degradation\"`"; §29.7 I-6 asserts `truth.jsonl` line count == event count + unobserved step count.

**Part II.** §62.1.2: "OVERRIDES Part I: ground truth is keyed by `AnchorId`, and EventIds are a non-authoritative side list," with `AnchorId = blake3_128(scenario_id || u32be(step_ordinal) || semantic_kind || entity_key)`. Rationale: "any ground truth keyed on EventId becomes unresolvable exactly in the cells the research axis is about." `entity_key` must be the generator's pre-resolution identifier, "NOT the output of entity resolution."

**Impact.** The §29.3 schema, the unique index, and the I-6 cardinality invariant all need reworking; anchors are per attack-plan step, not per event, so line counts no longer align. Note also that Part II puts ground truth in a new artifact at a new path with a new schema (`groundtruth.json`, `schemas/groundtruth.v1.json`, one per scenario beside `bundle.jsonl`) while Part I's is `truth.jsonl` plus the `truth_annotation`/`truth_edge` tables — Part II never says whether the Part I artifact is replaced or kept alongside.

#### Goal atom is derived, not hand-authored

**Part I.** §25.3 input table lists `goal.toml` as "authored per scenario" carrying the "goal atom, horizon `k`". §28.1's scenario file carries `goal_atom: "data.exfiltrated(finance.records, actor_b)"` as a hand-written field, and §23.2's scenario schema marks the goal with `goal: true` on a step.

**Part II.** §62.2.4: "OVERRIDES Part I: `goal.toml` is no longer hand-authored per run. The goal atom for a run is derived as `Phi(groundtruth.attack_plan.goal)` by `spectra goal derive`, and `gate:goal-derived` fails the build if any scenario ships a hand-written goal atom that differs from the derived one. A scenario author who also picks the goal can tune the cut to a hand-picked target."

**Impact.** A new artifact (`validation/correspondence.toml`), a new hash in the certificate (`hashes.correspondence`), and two new gates (`gate:phi-total`, `gate:phi-injective`) are required before any goal can be resolved. Part II does not say where the other `goal.toml` field, horizon `k`, now comes from — §25.3 makes it part of the same authored file, and nothing in §62 derives it.

#### Zero-false-ROBUST invariant scope narrowed

**Part I.** §25.12.7 `degradation_invariant` ("headline gate"): "across the entire 100%→30% telemetry completeness matrix, with ground truth known to the generator, the number of FALSE ROBUST verdicts MUST be zero. Any single occurrence fails the build." §29.7 I-1 says "across the whole 100%->30% matrix"; §44.9 says "the entire 100%→30% completeness matrix for every scenario and every tampering mode ... One violation fails the build with no override flag, no xfail, no skip marker."

**Part II.** §62.8.3: "OVERRIDES Part I: the scope is `HELD_OUT scenarios x completeness 100%..30% x suppression classes S0-S3`. S4 and S5 are measured and published, not gated." §62.1.6 adds: "OVERRIDES Part I: the zero-false-ROBUST invariant is scoped to declared classes, and the invisible class is enumerated, counted and published rather than excluded," with S5_INVISIBLE marked "KNOWN UNSOUND". §62.8.1 also supplies the definition of `false ROBUST` Part I never gave, splitting it into EMPIRICAL and MODELED.

**Impact.** The gate now covers a strict subset of Part I's matrix on two axes at once: DEV and RED scenarios are excluded, and two of six suppression classes are excluded. An implementer following §44.9 builds a gate over every scenario and every tampering mode and will fail the build on S4/S5 cells Part II intends to publish as measured limitations. §62.8.4 further forbids reporting a single combined false-ROBUST figure, which is exactly what §25.12.7 and §29.7 I-1 describe.

#### Byte-identical replay no longer required of the range

**Part I.** §29.5 "MAKE TARGETS AND BIT-IDENTICAL REGENERATION": "`make dataset-reproduce` is the determinism gate and runs in CI nightly," with a transcript showing a cold range-up, live population generation and scenario execution ending in "[repro] OK bit-identical". Six determinism requirements (clock shim, content-addressed EventIds, canonical sorted JSON, named PRNG substreams, serialized collector, pinned image digests) are listed as "all mandatory" to make it possible.

**Part II.** §62.4.4: "Re-execution is NOT deterministic. Live containers do not replay byte-identically, and Part I asserted byte-identical replay in a way that cannot hold here. OVERRIDES Part I: byte-identical replay is required of the seeded synthetic generator, the kernel and the checker; it is NOT required of the range, and the range's bundles are non-normative. Every range artifact is stamped `normative: false`."

**Impact.** Range outputs now need a `normative: false` stamp and the §62.4.6 N-repeat/N_min machinery replaces hash equality as the range's correctness notion. See the unresolved item on telemetry provenance: Part I has exactly one range, and it is the source of the normative dataset, so this override has consequences for §29.5 and §26.7 that Part II does not state.

#### Minimality reported separately from safety; "minimum cut" phrasing restricted

**Part I.** §25.9: "Exact cardinality-minimality holds only for `|A| ≤ 64`; above that the kernel downgrades to subset-minimal and says so in the flags" — and §22.2 caps the atom budget at `Σ_k m_k ≤ 64`, so Part I effectively claims exact cardinality-minimality on every run. §25.8(f) makes "no cut smaller than `|S|` satisfies `Psi`" a checker obligation discharged in one linear pass at cost `O(Σ|body| + |Psi|·|A|)`, exit code 5. §25.11's UI result header reads "Minimum cut {session_binding>=device, egress_seg>=1} — ROBUST".

**Part II.** §62.5.5: "OVERRIDES Part I: the certificate carries `minimality: EXHAUSTIVE | PSI_RELATIVE | UNVERIFIED`. The checker sets `EXHAUSTIVE` only when it ran real fixpoints for all cuts of cardinality < |S|. Printing `no smaller cut exists` on a `PSI_RELATIVE` certificate is forbidden in every surface; the permitted string there is `no smaller cut satisfies the enumerated corridor set`." §62.11.3 enforces this via `gate:banned-phrases`.

**Impact.** Part I's linear-pass checker is Ψ-relative by construction, so under Part II essentially every certificate is `PSI_RELATIVE` and §25.11's "Minimum cut …" header becomes a banned string. Running real fixpoints for all cuts of cardinality < |S| is combinatorial in |A| (2080 fixpoints for |A|=64, |S|=3) and cannot be done in §25.8's stated cost bound — so `EXHAUSTIVE` will be rare, and §25.9's blanket exact-minimality claim must be withdrawn.

#### Soundness flags no longer a free exemption from the gate

**Part I.** §25.9: "A run with ANY flag set ... MUST NOT be presented as ROBUST: the API returns `mode: \"OPTIMISTIC_ONLY\"` with `downgraded_by: [...]`, and the UI badge is grey, never green." Part I places no limit on how many runs may be flagged, and §45's `test_graph_explosion_dos.py` actively requires runs to terminate with `grounding_capped=true`.

**Part II.** §62.9 (marked OVERRIDES Part I) adds `gate:nonvacuity-flags`: "Part I let a flag exempt a run from the gate, which makes flags a free escape hatch." `flagged_share = |{runs with any soundness-affecting flag}| / |all runs in scope|`, FAIL above `policy.flagged_share_ceiling`, plus `gate:flag-ratchet` failing on any increase between commits without a ledger entry. §62.4.7 additionally lists "raising a cap so the run trips `grounding_capped`" among FORBIDDEN repairs.

**Impact.** Flagged runs must now be counted against a preregistered ceiling and ratcheted across commits. Part II does not define "all runs in scope", and Part I's adversarial suite deliberately manufactures `grounding_capped` runs — if those land in the denominator, the adversarial suite itself can trip the gate.

## 63 Guard language

### UNRESOLVED

#### Conjunctive blocking: one variant per DNF term (§22.3) vs multi-term blockers inside one instance (§63.5/63.6 C7)

**Tension.** Part I 22.3 lowers `admit_when` to DNF and states: "Each DNF term becomes ONE rule instance / ONE technique variant whose `blockers` mask is the OR of the bits of the threshold atoms it negates. A step that only fails when two controls are both raised is therefore two variants, not one mask. `blockers & S == 0` is then exactly 'this variant survives cut S'." Under that lowering the single-u64 test is correct by construction. Part II 63.5 instead keeps the whole DNF inside one instance (`SmallVec<[u64; 2]>`, subset test) and asserts the Part I test "is wrong for any conjunctive blocker" - true only if variant splitting has been abandoned, which Part II never says. 63.6 C7 caps a control guard at 8 DNF terms (E-SEM-041, "split the rule; do not silently cap"), which is a different splitting rule at a different layer than 22.3's one-variant-per-term.

**Decision needed.** Decide whether 22.3's one-DNF-term-equals-one-technique-variant lowering survives. If it does, instances never carry conjunctive blockers and 63.5's SmallVec is dead weight; if it does not, the technique-variant library, 22.5's `bypass.modeled_by_variant`, 23.2's per-step `variants:` list, witness trees and `corridor_mask` all change shape and instance counts, and 22.7's `dnf_mask_equivalence` test must be rewritten against the new lowering.

**Recommended.** Abolish 22.3's variant splitting for control blocking and make 63.5's DNF the single mechanism - variant splitting duplicates instances, inflates corridor counts and makes blindness-premium attribution ambiguous. Keep variants for genuinely different attacker techniques only, and add an explicit "OVERRIDES Part I 22.3" line saying so.

#### Catalog gate expressions have no SGL environment

**Tension.** Part I 22.1 requires that "Any behavior that depends on a control MUST be expressed as a guard expression in the catalog or in `rules/rules.toml`", and 22.5/22.6 author gate conditions and bypass conditions inside `controls/catalog.yaml` (`admit_when: "not ctrl.session_binding >= network"`, `condition: "attacker.network.prefix24 == victim.network.prefix24"`, `condition: "attacker.capabilities has device_key"`). Part II 63.0 declares that "Nothing else in SPECTRA may define, extend, or reinterpret guard semantics", but SGL is defined only over a rule's `when`/`blocked_when`, where DATA-sort paths resolve against "bound fact variables" whose slots come from "the rule's `body`" (63.6 C6). A catalog gate has no rule body and therefore no slots, and `has` is not an SGL construct.

**Decision needed.** Decide whether catalog gate and bypass conditions are SGL at all. If yes, specify the environment Γ for an expression with no rule body (what `attacker.*`/`victim.*` resolve to, and how `has` is expressed given 63.14(3) forbids absence tests). If no, name the second guard language and reconcile it with 63.0's exclusivity claim and 22.1's mandate.

**Recommended.** Make catalog gates SGL by giving each enforcement point a declared fact-schema record whose fields are the slots (so `attacker.network.prefix24` typechecks), and express `has(x)` as equality against a declared `Sym` domain member per 63.14(3). Anything less leaves the catalog outside the hash gate that 63.9 claims covers "every guard in the table".

#### The concrete simulator's guard front end is unspecified

**Tension.** Part I 22.3 makes the simulator one of two lowerings of the single guard parser, 23.3 evaluates `guard_for(step.transition, v, config) // compiled from section 22` inside the stepper with results `Admit | Degrade{cap} | Refuse{atoms}`, and 25.4 states "One table, two consumers (kernel and simulator), no second source of truth." Part II forbids the simulator from reading `crates/eclipse-kernel`, `generated/guards.rs` or `guards/ast.sglb` (enforced by `make sim-independence`), requires its enforcement semantics to be independently authored (63.10(b)), and omits the simulator entirely from 63.8's table of guard consumers - so no row says what parses or evaluates the simulator's guards, or whether it reads `rules.toml` at all.

**Decision needed.** Decide whether the simulator (a) writes its own independent SGL front end from §63 like the Go checker, (b) reads only the catalog and never `rules.toml`, or (c) keeps Part I's shared lowering and the `sim-independence` gate is narrowed to exclude a pure front-end crate. Then state what replaces 25.4's "no second source of truth" guarantee that simulator and kernel masks agree, now that 25.12.1 has been demoted to a codegen regression.

**Recommended.** Option (a): add a simulator row to 63.8's table requiring an independently authored SGL front end, make it publish `--print-guard-ast-hash` into the 63.9 gate, and restore the sim-vs-kernel agreement test at P0 severity - with independent front ends it is real differential evidence, which is exactly what 63.10 says the demoted gate is not.

#### `degrade` and `detect` gate effects have no representation in SGL

**Tension.** Part I 22.5 requires every gate to declare `effect ∈ {refuse, degrade, detect}` and requires the compiler to enforce that degrade/detect gates contribute no blocker bits (recorded in `build/controls.meta.json` under `non_severing_gates`); 23.3's evaluator returns `Degrade{cap}`; 24.6 classifies a DEGRADED outcome from the declared degrade cap; 22.6's `anomaly_detect` and `audit_integrity` are detect-only controls. SGL has exactly two sorts - `when : Bool` and `blocked_when : Ctl` - and nothing that expresses a degrade cap or a detect-only effect, and 63.0 forbids any other artifact from defining guard semantics.

**Decision needed.** Decide where degrade and detect gate conditions are expressed and typed now. Either add a third sort or an effect annotation to SGL, or declare explicitly that degrade/detect live only in the simulator's independently authored enforcement layer and are outside `guard_ast_hash` - in which case say so, because 63.9's "every guard in the table" and 22.1's "any behavior that depends on a control" currently both claim them.

**Recommended.** Keep SGL two-sorted and state explicitly that degrade/detect gates are simulator-only, non-severing, and excluded from `guard_ast_hash`; then move 22.5's non-severing compiler check into the control-catalog section so the exclusion is still enforced rather than merely assumed.

#### Tick granularity: global and hashed (§63) vs per-scenario (§23.2)

**Tension.** Part II 63.5 converts duration literals to ticks at compile time "using `tick_granularity_ns` from the time lattice", emits that value into the `.sglb` header (63.7) so it is part of `guard_ast_hash`, and makes a non-integral literal a hard error (E-SEM-030, "SGL never rounds"). 63.13's worked example compiles `30m` to `ConstInt(1800000)`, i.e. a 1 ms tick. Part I 23.2 declares the tick unit per scenario in the scenario YAML (`horizon_ticks: 240`, `tick_unit_s: 1`, "1 tick = 1 simulated second"), and 23.2 caps `horizon_ticks <= 10_000`. Under Part I's 1-second tick, `30m` compiles to 1800, not 1,800,000, so the same guard source has two different canonical ASTs and two different `guard_ast_hash` values depending on which spec the implementer follows.

**Decision needed.** Decide who owns tick granularity and whether it is global. If it is global and hashed into the guard AST, 23.2's per-scenario `tick_unit_s` must become a fixed constant or a derived display factor; if it stays per-scenario, `guard_ast_hash` is scenario-dependent and the single-hash gate in 63.9 cannot hold.

**Recommended.** Make `tick_granularity_ns` a single repo-wide constant owned by the time-lattice section, hashed into `.sglb` as 63.7 says, and demote 23.2's `tick_unit_s` to a per-scenario display mapping only (with a loader check that it is an integral multiple of the global granularity). A per-scenario granularity breaks the one-hash-for-all-backends gate outright.

#### `controls.lock` vs Part I's compiled control artifacts and bit-assignment rule

**Tension.** Part II makes `controls.lock` a hashed input to `sglc` (63.9 diagram, `sglc check --controls controls.lock`), requires bit positions "sorted by ASCII name, levels ascending, positions assigned by running offset", requires positions to be append-only across catalog versions, and fails with E-CFG-050 if the lock is "missing, stale relative to `controls.toml`, or assigns a bit >= 64". Part I 22.2/22.7 has the catalog compiler emit atoms and their table into `build/controls.toml` and `build/controls.meta.json` (plus `build/controls.d.ts`), all three committed and diffed in CI, with `E_ATOM_BUDGET` above 64 - and no lock file, no ASCII-name ordering rule and no append-only constraint. 25.3 lists `controls.toml` (not `controls.lock`) as the certificate-hashed control input.

**Decision needed.** Decide whether `controls.lock` is a new fourth artifact or a rename of `build/controls.meta.json`'s atom table, which section owns bit assignment, which file's hash goes into the certificate, and whether Part I's existing atom ordering is compatible with the new ASCII-sorted append-only rule (if not, every existing certificate is invalidated once).

**Recommended.** Fold the lock into the existing compiler output as `build/controls.lock`, make the control-catalog section the sole owner of bit assignment under Part II's ASCII-sorted append-only rule, and hash the lock (not `controls.toml`) into the certificate alongside `rules_table_hash`, so bit drift and rule drift are separately attributable.

#### How guard identifiers bind to rule-body variables

**Tension.** Part I rules bind uppercase logic variables in head and body (`head = "session.active(S, T+1)"`, `body = ["session.issued(S, T)", "token.presented(S, CTX, T)"]`) and the guard references them directly (`ctx_matches_bind(CTX, S)`); 22.3 says a guard `Path` "resolves against the security state (section 17)". Part II's lexer admits only lowercase snake_case idents, resolves paths against the fact schema Σ ("every segment is a declared field", E-TYP-014), and its worked example has body `["session.issued(S, T0)", "auth.event(E, T)"]` while the guard says `s.subject`, `s.issued_at`, `e.t`, `e.verb` - a mapping from body variable `S`/`E` to guard prefix `s`/`e` that is never stated, and which collides on any two body atoms whose variables share a first letter.

**Decision needed.** Specify the binding rule from body variables to guard identifiers (lowercasing? an explicit alias syntax? positional slots?), and settle whether guard paths resolve against the section-17 security state (22.3) or against the fact schema record of a bound body variable (63.4). C6's hash-invariance claim - guard hashes invariant under variable renaming but not under body reordering - depends on the answer.

**Recommended.** Require an explicit binder in `body` (e.g. `s = session.issued(S, T0)`) so the guard prefix is declared rather than inferred, and state plainly that guard paths resolve only against bound fact records, never against simulator state - otherwise two rules with variables `S` and `SESSION` are ambiguous and the Go checker and `sglc` will disagree without any gate catching it.

### SILENT

#### Control-reference keyword: `ctrl.` vs `ctl.`

**Part I.** 22.3 grammar: `CtrlCmp := "ctrl." Ident ">=" ( Int | LevelName )`, and every authored example uses it - 22.5 `admit_when: "not ctrl.session_binding >= network"`, 22.6 `admit: not ctrl.mfa>=otp`, 25.4 `guard = "not ctrl.session_binding >= network or ..."`.

**Part II.** 63.2 reserves `ctl` (not `ctrl`) and 63.3's only control production is `threshold = "ctl" , "." , ident , ">=" , ident`. 63.11 defines E-SYN-010 for a `ctl.` reference in a `when` expression. No override notice anywhere.

**Impact.** Every control expression shipped in Part I fails to lex under `sglc` (`ctrl` is not reserved, so it parses as an `ident` and then fails as an unknown field path, E-TYP-014). An implementer who authors the catalog from Part I 22.5/22.6 has to rewrite all fifteen controls' gates, and nothing in Part II warns them.

#### Level named by integer is legal in Part I, a hard error in Part II

**Part I.** 22.3: `CtrlCmp := "ctrl." Ident ">=" ( Int | LevelName )` - the level operand may be an integer. Part I's atom and UI vocabulary is index-based throughout (`x_session_binding_1`, `x_session_binding_2` in 23.4 traces, 24.7 replay output, 25.7 certificates), and 22.2 defines levels as indices `0..m_k`.

**Part II.** 63.3: `threshold = "ctl" , "." , ident , ">=" , ident ; (* level by NAME, never by number *)`, with E-SYN-012 "level named by integer instead of symbol in a threshold". The marked override in 63.1(2) covers only non-threshold level predicates (`==`, `<`, `!=`, `not`), not the name-vs-number operand.

**Impact.** Guards written as `ctrl.session_binding >= 2` (permitted and natural under Part I, and matching the index-based atom names used in traces and certificates) become build failures. The level-name-to-index mapping direction is only implied by 63.7's atom record `(control, level_name, level, bit)`.

#### Gate polarity: `admit_when` (antitone, negated controls) vs `blocked_when` (positive monotone)

**Part I.** 22.3 defines the guard field for control gates as `admit_when` - "the condition under which a gated transition is still permitted" - which "MUST be antitone... control literals may appear only negated". 22.5 makes `admit_when` a required key of every gate, and all fifteen controls in 22.6 are authored in that polarity (`admit: not ctrl.mfa>=otp`). 22.7's property test `dnf_mask_equivalence` brute-forces `admit_when` over all `2^|atoms|` assignments against the lowered masks.

**Part II.** 63.1(1): the CONTROL sort is the field `blocked_when`, "a positive monotone formula over threshold literals only", and `not` inside it is E-SYN-009. 63.13's `rules.toml` shape has `blocked_when = "ctl.session_binding >= bound or (ctl.egress_seg >= l1 and ctl.mtls >= required)"`. Part II never mentions `admit_when`, the catalog schema, or the polarity inversion.

**Impact.** The two specs disagree on the sense of every authored control expression in the repository. An implementer reading Part I writes the admit-side formula; `sglc` rejects it on the `not`, and if the `not`s are mechanically stripped the meaning silently inverts (permit becomes block). The required catalog key `admit_when` in 22.5's JSON Schema, and the `dnf_mask_equivalence` test that brute-forces it, have no counterpart in Part II.

#### One mixed `guard` expression vs two disjoint sorts, and the loss of Part I's guard constructs

**Part I.** 25.4's shipped rule has a single field mixing both kinds in one formula: `guard = "not ctrl.session_binding >= network or ctx_matches_bind(CTX, S)"`. 22.3's one grammar admits `Prim := "(" Disj ")" | CtrlCmp | StateCmp | "true" | "false"`, with `StateCmp := Path CmpOp Literal | "has(" Path ")" | "in(" Path "," ListLit ")"` and `Path := Ident ( "." Ident )*` (unbounded depth). 22.3 notes state predicates are evaluated at grounding time and "are NOT part of the mask".

**Part II.** 63.1(1): two disjoint sorts that "cannot mix" - `when` (data) may not mention `ctl.`, `blocked_when` may not mention a variable, a literal, an arithmetic operator or `not`. 63.3 drops `has(...)`, changes `in` to an infix operator over a symbol-set literal (`e.verb in {#auth, #refresh}`), caps `path` depth at 3, admits no user-defined predicates (builtins are exactly `min max abs within overlaps distinct`), and allows no string literals. 63.13 replaces `guard` with `when` + `blocked_when`.

**Impact.** Part I's own worked rule `r_session_replay` is unparseable under SGL on three counts (mixed sorts in one `or`, `not` over a control literal, the call `ctx_matches_bind`). Part II supplies no migration for user-defined state predicates such as `ctx_matches_bind` or for `has(path)` - see the UNRESOLVED entries. 63.0's blanket clause supersedes text implying guards are "expressions in rules.toml compiled to Rust", which does not obviously reach the removal of specific constructs an implementer has already authored against.

#### Crate and binary layout

**Part I.** 25.2: `crates/spectra-eclipse/` (kernel), `crates/spectra-guard/` ("shared guard parser + DNF lowering (section 22)"), `cmd/spectra-verify/` (Go checker), `reference/admissibility/` (Haskell), `tests/oracles/z3/`; 22.3 names `crates/spectra-guard` as the single parser; 23.3 names `crates/spectra-sim`. Independence is enforced by `gates/checker_independence.sh`.

**Part II.** 63.8's consumer table names `crates/eclipse-kernel` (with `src/generated/guards.rs`), `sglc`, `c/sglvm`, `go/spectra-verify`, and a "Haskell admissibility oracle". `crates/spectra-guard` is never mentioned; 63.10's `make sim-independence` gate greps for `crates/eclipse-kernel`, `generated/guards.rs`, `guards/ast.sglb`.

**Impact.** The kernel crate is renamed and the Go checker moves from `cmd/` to `go/` with no notice, and the fate of the shared `crates/spectra-guard` crate (mandated by 22.3, listed in 25.2, referenced by the simulator in 23.3) is left implicit. Grep-based CI gates written from either part will miss the other part's paths.

#### Rule provenance field: `provenance` prose vs `note` + `attck`

**Part I.** 25.3/25.4: each rule carries `provenance` as free prose that embeds the technique id - `provenance = "T1550.004; a replayed token produces a presentation record only if the gateway logs it."`

**Part II.** 63.13's `rules.toml` shape splits this into `note = "free prose; NOT hashed into guard_ast_hash"` and `attck = ["T1550.004"]`, and 63.7's `rules_table_hash` record hashes `attck_refs sorted` while excluding prose notes.

**Impact.** A rule table authored from Part I has no `attck` field, so `rules_table_hash` cannot be computed as specified, and the "a comment does not invalidate a certificate" property depends on the prose living in `note` rather than `provenance`.

### RESOLVED

#### RuleInst.blockers representation and the blocked test (§25.5/25.6D/25.8b vs §63.5)

**Part I.** `blockers: u64, // mask over threshold atoms; see 22.3`; the Dowling-Gallier loop skips an instance with `if inst.blockers & S != 0 { continue }`, and the Go checker's closure check (b) is "every instance with `blockers & S == 0` and `body ⊆ U` has `head ∈ U`".

**Part II.** Marked "OVERRIDES Part I / ECLIPSE §3": `blockers: SmallVec<[u64; 2]>`, a canonical monotone DNF, evaluated as `enabled(inst, S) == forall t in inst.blockers : (t & S) != t` (blocked iff some term is a subset of the cut). The Part I single-mask test "is wrong for any conjunctive blocker and must be replaced everywhere, including in the Go checker and in the Dowling-Gallier unit-propagation loop of ECLIPSE §4D".

**Impact.** An implementer following Part I 25.5/25.6/25.8 literally ships a u64 field and an intersection test; every conjunctive blocker is then treated as blocked when any one of its controls is raised, producing cuts that are too small and certificates the corrected checker would reject. The certificate `psi` mask format and `corridor_mask` (OR of `blockers`) in 25.6 also need re-derivation for multi-term blockers.

#### What `Cert.hashes.rules` commits to (§25.3/25.7/25.8 vs §63.7)

**Part I.** 25.3: all inputs including `rules.toml` are "content-hashed with BLAKE3; the hashes go in the certificate"; 25.7 shows `"hashes": {"rules":"blake3:..", ...}`; the checker's exit code 6 is "input hash mismatch" and it prints "OK: inputs match hashes (5/5)".

**Part II.** Marked "OVERRIDES Part I / ECLIPSE §5": `Cert.hashes.rules` is `rules_table_hash` = BLAKE3 over per-rule metadata `(rule_id, head_predicate, body_predicates, producing_sources sorted, silent_possible, attck_refs sorted)` plus `guard_ast_hash` as a trailing field, with prose notes excluded. The raw file digest survives only as non-load-bearing `rules_source_sha256` in the run manifest.

**Impact.** The checker must recompute a structured metadata hash rather than digesting the file, and a prose edit to `rules.toml` must no longer invalidate certificates. A Part I implementation fails every certificate after a comment or `note` change.

#### Identity and ownership of the guard language; simulator as a lowering target (§22.3/§23.3 vs §63.0/63.8/63.10)

**Part I.** 22.3: "One grammar, one parser (`crates/spectra-guard`), two lowerings: to the simulator's evaluator and to ECLIPSE's `blockers` masks." 23.3's stepper calls `guard_for(step.transition, v, config) // compiled from section 22` and evaluates it inside `crates/spectra-sim`.

**Part II.** Marked "OVERRIDES Part I": the language is SGL with its own compiler `sglc`, binary form `.sglb` and `guard_ast_hash`; "Any Part I text that implies guards are 'expressions in rules.toml compiled to Rust' is superseded by 63.1-63.14." Marked "OVERRIDES Part I / ECLIPSE §1": "the concrete simulator is NOT generated from the guard AST. Only the kernel's guard evaluator is generated." 63.10 adds a `make sim-independence` build-graph gate that fails on any simulator edge into `crates/eclipse-kernel`, `generated/guards.rs` or `guards/ast.sglb`.

**Impact.** The "two lowerings from one parser" architecture is dead; a shared `spectra-guard` lowering into the simulator now fails a CI gate. See the UNRESOLVED item on what the simulator's guard front end actually is.

#### Status of the simulator-vs-kernel agreement test (§25.12.1 vs §63.10)

**Part I.** Test plan item 1 `sim_kernel_agreement`: "256 randomized control configurations per fixture; for each, the concrete simulator's outcome (section 23) and the kernel's reachability under the same cut MUST agree on goal-reachability. Disagreement is a P0 bug" - and the build fails otherwise.

**Part II.** "OVERRIDES Part I: the ECLIPSE §7 'simulator vs kernel agree on randomized configurations' gate is hereby DEMOTED to a codegen regression test and renamed `guard-codegen-regression`. It is not validation and may not be described as validation anywhere. Validation comes from §62's independent oracles."

**Impact.** The gate is renamed and its claim strength reduced. Note the demotion's stated rationale (it is only a codegen regression) sits oddly with 63.10's own requirement that the simulator be independently authored and forbidden from reading kernel or guard artifacts - if the simulator shares no code, the test is a genuine differential check, not a codegen regression. Reviewers should not let the rename delete the P0 severity without deciding that explicitly.

#### Control-level antitonicity: linter vs grammar (§22.3/§22.7 vs §63.1(2))

**Part I.** 22.3: `admit_when` "MUST be antitone in the control vector... The linter rejects any `ctrl.*` comparison appearing under an even number of `not`s"; 22.7 adds property test `antitone_catalog` over 512 random control vectors.

**Part II.** Marked "OVERRIDES Part I": the linter "is upgraded from a lint to a grammar-level impossibility". The CONTROL sort has no negation, no equality, no `<` and no level predicate other than `ctl.X >= LEVEL`; `ctl.X == 2`, `ctl.X < 3`, `not (ctl.X >= 2)` are parse errors (E-SYN-009/E-SYN-012), and "the antitonicity that ECLIPSE §4E's two-fixpoint shortcut depends on is unconstructible-to-violate, not tested-for".

**Impact.** The parity-of-`not`s linter cannot be implemented as described because `not` no longer exists in the control sort. Part I's antitonicity safety net is replaced by grammar plus `make guard-lattice-test`.

## 64 Well-definedness

### UNRESOLVED

#### `psi_complete` may be unreachable under Part I's hitting-set loop, permanently suppressing the headline outputs

**Tension.** Part I 25.6E's loop is `loop { S = min_cardinality_model(psi); if !reach(p,S) return (S,psi); psi.push(corridor_mask(witness_tree)) }` — it stops as soon as the current minimum hitting set severs the goal, so Psi holds only the corridors discovered along the way and is generally NOT an exhaustive corridor enumeration. Part II 64.5.1 makes `psi_complete` a precondition for `redundancy_index` and defines it as "set only by the hitting-set loop reaching fixpoint with no cap and no budget exhaustion — never inferred, never defaulted to true", and 64.3.2 requires psi_min_complete AND psi_max_complete before the blindness premium may be published. 64.7.5 ties `frontier_scope: "exhaustive"` to the same list.

**Decision needed.** Define what 'the hitting-set loop reaching fixpoint' means operationally: does it require a second, exhaustive corridor-enumeration pass (MARCO-style MCS enumeration over Psi) beyond the cut-finding loop of 25.6E, and if so what bounds it and what is its cost? As written, a compliant Part I kernel can never set psi_complete, so `blindness_premium`, `redundancy_index` and `frontier_scope: exhaustive` are omitted on every run — including the demo.

**Recommended.** Specify the completeness pass explicitly (enumerate all minimal corridors, not just those needed to force the current cut), give it its own deterministic node budget and its own flag, and state in 64.5.1/64.3.2 that psi_complete refers to that pass, not to termination of the cut loop.

#### Grounding is still bounded by wall-clock in Part I, which makes Part II's suppression flags and hashed bytes machine-dependent

**Tension.** Part I 25.6B sets hard caps `MAX_INSTANCES = 2_000_000`, `MAX_FACTS = 500_000`, `MAX_GROUND_SECONDS = 120`, the last of which sets `flags.grounding_capped` from elapsed wall-clock time. Part II 64.0 forbids any headline output whose value is not a function of the hashed inputs, 64.2.1 requires the solver budget to be "a deterministic node budget ... never by wall-clock", and 64.8 makes `grounding_capped` a suppression trigger that decides whether `blindness_premium` and `redundancy_index` appear at all — while 64.8.2 states "A field that is absent is absent from the hashed bytes." Part II never mentions MAX_GROUND_SECONDS.

**Decision needed.** Replace the 120-second grounding cap with a deterministic budget (instance/fact/step count) or explicitly rule that grounding_capped may be time-derived. Until then the certificate's field set, and therefore its hash, differs between a fast and a slow machine on identical inputs.

**Recommended.** Delete MAX_GROUND_SECONDS as a correctness-affecting cap, keep MAX_INSTANCES/MAX_FACTS as the deterministic triggers for grounding_capped, and keep elapsed time only as a non-hashed `measured` field.

#### The mandatory ML baseline envelope violates the no-scores lint

**Tension.** Part I 21.7 mandates a single output envelope for "Every ML output anywhere in SPECTRA — API, file, UI, log", containing `"score": 0.8312`, `"score_semantics": "calibrated_probability_of_generator_labelled_attack_window"`, `"calibration"`, and validated against the JSON Schema `spectra/ml-prediction-v1.json`; 21.1 exposes it through `spectra_api.routers.baseline`, so it is in the OpenAPI surface and the generated TS client. Part II 64.4.2 states there is "no field named ... `score` ... `confidence`, `probability` ... on any type reachable from the certificate, the OpenAPI schema, the Postgres schema or the TypeScript client", and `make lint-no-scores` fails on any regex match of `(?i)(score|confidence|probability|severity|risk|rating|pct|percent|ratio|weight)` in the JSON Schema, SQL DDL or generated TS types outside an allowlist. Part II never mentions section 21.

**Decision needed.** Decide whether the ML baseline arm is exempt from the no-scores ban (allowlist `ml-prediction-v1.json` and the baseline router with a written justification), or whether the envelope and its route must be renamed/removed from the OpenAPI and TS surfaces. As written the two sections cannot both be satisfied and `make lint-no-scores` fails the build on a Part I-mandated artifact.

**Recommended.** Allowlist the baseline schema by exact file path with the justification "comparison arm, `is_baseline_only`/`not_evidence` constants, never reachable from a certificate", and narrow 64.4.2's scope statement to types reachable from the certificate and the proof endpoints.

#### Does declared cost still order the frontier when costs.toml is present?

**Tension.** Part I 25.6H: the frontier "Yields the exact Pareto set of `(declared_cost, residual_reachability)`". Part II 64.7.2 keeps a `declared_cost` axis when costs.toml is present, but 64.7.4's dominance relation is defined purely as `cardinality(C1) <= cardinality(C2) ∧ R1.goals_derivable ⊆ R2.goals_derivable ∧ R1.corridors_open ⊆ R2.corridors_open` — declared cost appears in no term, and points are serialised in ascending `cut_cmp` order. 64.7 carries an override marker for §4H but never says cost has been dropped from the dominance order.

**Decision needed.** State whether, with costs.toml present, dominance is over declared cost, over cardinality, or over both as a three-component product order — and correspondingly what `frontier` points are sorted by and which representative survives within an equivalence class.

**Recommended.** Make dominance a product order over (declared_cost when present else cut_cardinality, goals_derivable, corridors_open) and say explicitly that the cost component is omitted, not defaulted, when costs.toml is absent.

#### Realizability declarations live in files that are not hashed kernel inputs and that the independent checker may not read

**Tension.** Part I 25.3 gives a closed table of ECLIPSE inputs (`bundle.jsonl`, `rules.toml`, `controls.toml`, `costs.toml`, `goal.toml`), "all content-hashed with BLAKE3; the hashes go in the certificate", and 25.2's gate `gates/checker_independence.sh` states "the only shared artifacts are the on-disk formats (`rules.toml`, `bundle.jsonl`, `controls.toml`, `liveness.json`, `cert.json`) and their JSON Schemas." Part II 64.6 declares the realizability checks in `rules.toml` (exclusive_group), `facts.toml` (functional_on), `liveness.json` and obligation axioms (`max_witnesses`), and 64.1 adds `controls/catalog-bits.lock`. Only the bits lock is given a hash entry (64.1.3 `hashes.catalog_bits`); `facts.toml` is introduced with no hash entry and is not in the permitted shared-artifact list.

**Decision needed.** Add `facts.toml` (and confirm `catalog-bits.lock`) to the hashed input table of 25.3 and to the checker-independence allowlist in 25.2, or move `functional_on` declarations into `rules.toml`/`controls.toml`. Otherwise the certificate does not bind the declarations that determine a counterexample's REALIZABLE/UNREALIZABLE status, and the Go checker either cannot read them or trips the independence gate.

**Recommended.** Fold `functional_on` into `rules.toml`, and amend 25.3's input table plus the `hashes` object to carry `facts`/`catalog_bits` so realizability status is reproducible from hashed inputs alone.

#### Which flags still downgrade `safety`, given that Part II decouples minimality from safety

**Tension.** Part I 25.9 is a single crisp rule: any of `grounding_capped`, `subset_minimal_only`, `greedy_cover` forces `mode: "OPTIMISTIC_ONLY"` with `downgraded_by` and a grey badge. Part II 64.8's suppression lattice lists a different flag set (`grounding_capped`, `corridor_cap_fired`, `solver_budget_exhausted`, `horizon_truncated`, `er_ambiguous`), uses it only to omit dependent fields, emits `safety` "always" with the checker rule "must be one of ROBUST / OPTIMISTIC_ONLY / UNSAFE, scope-bound", and 64.2.2 decouples minimality from safety. `greedy_cover` and `subset_minimal_only` appear nowhere in Part II, and 64.8.1's `premium_suppressed_reason` enum is closed without them. The 64.8 CLI transcript shows `safety: OPTIMISTIC_ONLY` on a run whose only defects are budget exhaustion and a corridor cap, which reads as if caps still downgrade safety, contradicting the independence principle in the same section.

**Decision needed.** State explicitly, per flag, whether it downgrades `safety` or only suppresses fields: does `grounding_capped` still force OPTIMISTIC_ONLY (25.9), and what becomes of `greedy_cover` and `subset_minimal_only` now that minimality is a separate field?

**Recommended.** Publish a single flag-to-effect table: `grounding_capped`/`horizon_truncated`/`er_ambiguous` bound the scope of the safety claim and downgrade it; `solver_budget_exhausted` sets `minimality: SUBSET` only; `corridor_cap_fired` suppresses Psi-relative fields only; retire `subset_minimal_only` in favour of the `minimality` field and map `greedy_cover` onto the decisive-observation output alone.

#### The premium's extra solves are unbudgeted against Part I's build-failing performance gate

**Tension.** Part II 64.3.5 requires roughly `|A| + 1` additional minimum-cardinality solves per corridor database (so ~2 x 65 for Psi_min and Psi_max at full atom width), each sharing the node budget, plus per-clause level-minimality verification in the checker. Part I 25.12.11 is a build-failing gate: "2k-instance scenario proves in < 2s and verifies in < 50ms on the reference container", and 25.10's cache keys (`psi/…`, `cert/…`) do not contemplate per-atom restricted programs.

**Decision needed.** Either restate the 25.12.11 performance budget to cover the NEC/OCC computation and the checker's O(|Psi|·|S|) level-minimality pass, or scope the premium computation (e.g. compute it only on demand behind the `/eclipse/premium` endpoint rather than on every prove), and extend the cache key set to the restricted solves.

**Recommended.** Keep prove under 2s for the canonical cut alone, move NEC/OCC to a separately budgeted and separately cached stage with its own published measurement, and make the premium's absence from a fast path an explicit omission with `premium_suppressed_reason = "solver_budget"` rather than a gate failure.

### SILENT

#### control_id lint regex disagrees on the maximum identifier length

**Part I.** 22.5, catalog schema: `id: session_binding # ^[a-z][a-z0-9_]{2,31}$, unique` — 3 to 32 characters, validated by `schemas/controls.schema.json`, where unknown/invalid keys are an error.

**Part II.** 64.1: "`control_id` is constrained by lint to `^[a-z][a-z0-9_]{2,47}$`" — 3 to 48 characters. No override marker anywhere in 64.1.

**Impact.** Two authoritative regexes for the same identifier. A 40-character control id passes the Part II lint and the bit-lock generator but is rejected by the Part I JSON Schema at catalog compile time (or vice versa if the stricter one is applied late), and the atom-order guarantee in 64.1 is stated over an id space the catalog validator will not accept.

#### Atom budget: live atoms only (Part I) vs live + tombstoned bit positions (Part II)

**Part I.** 22.2: "The global atom budget is `Σ_k m_k ≤ 64`; the compiler fails with `E_ATOM_BUDGET` above it, printing the current count" — a count of currently declared (live) threshold atoms, published in `build/controls.meta.json`. 22.7 makes `build/controls.toml` the compiled artifact and says nothing about bit assignment, so bits follow compilation order.

**Part II.** 64.1.2: "Live + tombstoned positions must satisfy `max(pos) < 64`", gated by `make atom-budget`, with removal setting `state = "tombstone"` and the position never reused; 64.1.1 makes `controls/catalog-bits.lock` append-only with CI failing on any deletion or renumber; exhaustion requires a `lock_version = 2` epoch and a `catalog_epoch` certificate field. No override marker.

**Impact.** The two budgets diverge the first time a control is removed. A catalog with 50 live atoms and 20 tombstones passes Part I's `E_ATOM_BUDGET` check and fails Part II's `make atom-budget`; conversely a Part I implementer who assigns bits from the compiled catalog (file/compilation order) silently renumbers every existing bit on any catalog edit, which is precisely what 64.1.1 forbids and what `make stability-cut` step 4 tests for.

#### `corridor_id` is an enumeration ordinal in Part I and a content hash in Part II

**Part I.** 25.7 certificate: `"psi": [{"mask":"0x0000000000000024","corridor_id":3}]` — a small integer assigned as corridors are discovered by the hitting-set loop; 25.11 exposes `spectra eclipse corridors --explain <corridor_id>` and `GET /api/v1/eclipse/corridors -> [{corridor_id, mask, atoms, witness_tree_url}]` keyed by that integer.

**Part II.** 64.4.1: "`CorridorId` is `blake3-128` over the canonical encoding `LEB128(len) || LEB128(rank_i)...` of the corridor's atom ranks in ascending ≺ order, rendered as 32 lowercase hex characters ... and is the join key for every residual, redundancy and frontier output." The CLI transcript prints `corridors_open=[c:9a13…, c:4fe0…]`. No override marker, and 64.0's blanket override names only §4E/§4F/§4G/§4H, not the §5 certificate schema.

**Impact.** An implementer reading Part I emits discovery-ordinal corridor ids — the exact class of solver-order-dependent identifier 64.0 forbids — and the join keys of residual/redundancy/frontier outputs silently change between runs. Note also that because Part II's id hashes *ranks*, appending any control that sorts before an existing one shifts ranks and therefore changes pre-existing corridor ids, which collides with `make stability-cut` step 4's assertion that "every `corridor_id` is unchanged" after an unrelated catalog append.

#### Subset-minimality downgrades the verdict (Part I) but never affects safety (Part II)

**Part I.** 25.9: "A run with ANY flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) MUST NOT be presented as ROBUST: the API returns `mode: \"OPTIMISTIC_ONLY\"` with `downgraded_by: [...]`, and the UI badge is grey, never green." `mode` is a single field carrying both the safety verdict and the degradation.

**Part II.** 64.2.2: "`safety` and `minimality` are independent certificate fields. A `SUBSET` minimality never degrades `safety`." 64.8's table emits `safety` always ("must be one of ROBUST / OPTIMISTIC_ONLY / UNSAFE, scope-bound") and `minimality` always, with the suppression lattice governing field omission, not verdicts. Neither 64.2.2 nor 64.8 says it is overriding 25.9.

**Impact.** Directly opposite rules for the same run. Part I forces a budget-exhausted or subset-minimal run to display OPTIMISTIC_ONLY with a grey badge; Part II lets it display ROBUST with `minimality: SUBSET`. An implementer reading Part I alone suppresses a sound ROBUST verdict; one reading Part II alone ships a green ROBUST badge on a run Part I classifies as non-ROBUST.

#### The licensed minimality phrasing differs and Part I's mandated sentence is now a banned string

**Part I.** 25.13: "That 'no smaller cut exists' in general. The only licensed phrasing is 'no smaller cut exists over the declared control catalog'." 25.11 mandates the UI result header "Minimum cut {session_binding>=device, egress_seg>=1} — ROBUST — 6 corridors — …"; 25.8's checker prints "OK: no cut of size 1 satisfies Psi (6 corridors)".

**Part II.** 64.8.3: "A `psi_relative` minimality claim may never render as 'no smaller cut exists'"; the only permitted strings, registered in `docs/claims.md`, are EXACT → "no cut raising fewer controls satisfies the enumerated corridors, and enumeration reached fixpoint" and SUBSET → "no control can be removed from this cut; smaller cuts were not ruled out", with the Go checker rejecting certificates whose `render_strings` do not match the registry. 64.10: "Do not print 'the minimum cut' — print 'a cardinality-minimum cut over the declared catalog, canonical representative'." No override marker on either.

**Impact.** Part I's licensed sentence omits both the enumeration-fixpoint qualifier and the controls-vs-atoms distinction, and Part I's mandated UI header and checker line use exactly the forms 64.10 bans. An implementer who follows 25.11/25.13 ships strings that fail the claims-registry check and the banned-phrase gate.

#### Counterexample and witness trees: real EventId leaves (Part I) vs GHOST-bearing P_max trees (Part II)

**Part I.** 25.8 check (e): "each redundancy witness re-derives the goal under `S \ {c}` **from real `EventId` leaves**" (exit code 4 otherwise); 25.11: `GET /api/v1/eclipse/counterexample/{atom} -> derivation tree with EventId leaves`; 25.9 defines "`UNSAFE` = the goal is reachable in `P_min` under the user's current configuration", i.e. an observed-only property.

**Part II.** 64.6.2: "An UNSAFE verdict, and any counterexample derivation tree extracted from P_max, may combine silent instances that no single consistent world realizes. The tree may depict an attack that could not have happened." 64.6.7 requires every such silent instance to render as GHOST, and 64.8 rejects any counterexample lacking a realizability object. No override marker for the P_min definition of UNSAFE or for check (e).

**Impact.** Silent instances carry `evidence: []` (25.5/25.6C), so a P_max-derived tree cannot satisfy Part I's "real EventId leaves" requirement — the Part I checker rejects with exit code 4 exactly the trees Part II mandates. An implementer reading Part I also builds counterexamples from P_min only, so the whole realizability apparatus of 64.6 has nothing to run on and the demo climax described in 64.6.2 cannot occur.

### RESOLVED

#### Cut cardinality is counted in raised controls, not threshold atoms

**Part I.** Part I 25.5 types `Cut = u64` as a bitset over threshold atoms; 25.6E's `min_cardinality_model` is "branch and bound over 64-bit masks ordered by popcount" (popcount = atom count); 25.8 check (f) is "no cut smaller than |S| satisfies Psi" with |S| in atoms and prints "no cut of size 1 satisfies Psi"; cert field `lower_bound: 2` is an atom count; 25.12.5 z3_oracle requires the kernel to "match cardinality exactly" against Z3's minimum.

**Part II.** 64.0 definitions table plus an explicit "OVERRIDES Part I": cardinality of a cut is the **number of raised controls, never the number of threshold atoms**, because x_{k,3} entails x_{k,1} and x_{k,2} and a 3-level control would otherwise count as three.

**Impact.** Every minimisation objective, bound, checker check and oracle in Part I minimises the wrong quantity. popcount-ordered B&B, check (f), `lower_bound`, the Z3 oracle (25.12.5) and the brute-force cross-check (25.12.6) must all be re-expressed over raised controls; a naive Part I implementation returns a 1-control/3-level cut as 'size 3' and prefers a worse 2-control cut.

#### "Minimum cut" replaced by a canonical cut with a total comparator and mandatory level-minimality

**Part I.** 25.6E: `let S = min_cardinality_model(&psi)` — take a minimum-cardinality model of Psi. No tie-break is specified; the certificate carries `"cut": ["x_session_binding_2", "x_egress_seg_1"]` (atom name strings).

**Part II.** 64.2 ("OVERRIDES Part I: ECLIPSE §4E said 'take a minimum-cardinality model of Ψ' ... that instruction does not name an object"): a cut must be admissible AND level-minimal (hard requirement, checker-verified clause-wise), and is selected as the `cut_cmp`-minimum (fewer controls, then lexicographic on canonical ranks, then weakest levels) by an ascending-rank greedy with feasibility tests. 64.1.3: the certificate records `control_id`, `level`, `bit`, `rank` for every atom plus `hashes.catalog_bits`, and the Go checker recomputes `rank`.

**Impact.** A Part I implementer emits whichever minimum-cardinality model the solver found first, with no level-minimality check and no rank/bit fields; that certificate is rejected by the Part II checker (64.8 row `canonical_cut`: "recompute rank, verify hits-all + level-minimal + cut_cmp-minimal") and fails `make prop-cut` / `make stability-cut`.

#### "Exact cardinality-minimality for |A| <= 64" is withdrawn; EXACT is earned per run from a deterministic node budget

**Part I.** 25.9: "Exact cardinality-minimality holds only for |A| <= 64; above that the kernel downgrades to subset-minimal and says so in the flags" (flag `subset_minimal_only`).

**Part II.** 64.2.1 ("OVERRIDES Part I: ECLIPSE §6's 'exact for |A| <= 64' is false as a tractability statement; 64 is a representation width"): `minimality: EXACT` is earned per run by the B&B terminating inside a deterministic `solver.max_nodes` budget and is never inferred from atom count; exhaustion yields `minimality: SUBSET` with the exact node count.

**Impact.** Part I ties exactness to a representation width, so an implementer stamps EXACT on every |A|<=64 run regardless of whether the search actually completed — publishing unearned minimality claims that 64.8.3's permitted-string registry forbids.

#### Blindness premium is no longer a difference of two chosen cuts

**Part I.** 25.6, "Blindness premium": `S_rob \ S_opt` — the controls required ONLY because a sensor was blind; "This is the headline object; the UI leads with it." 25.11 exposes `GET /api/v1/eclipse/premium -> [{atom, licenses:[...]}]` and a UI panel of premium atoms.

**Part II.** 64.3 ("OVERRIDES Part I: ... That is a difference of representatives, not a property of the problem ... It is hereby deleted as a definition"): B := NEC(Psi_max) \ OCC(Psi_min), defined over raised controls by the *values* of restricted min-cardinality problems; published only when psi_min_complete AND psi_max_complete AND not grounding_capped, otherwise the key is omitted with `premium_suppressed_reason`; the old set difference survives only as `cut_delta_canonical`, which must carry the caption "difference between two canonical representatives; not the blindness premium" and triggers a banned-phrase build failure if rendered near the words "blindness premium".

**Impact.** A Part I implementation ships a solver-order-dependent headline number under the name the paper uses, exposed at /eclipse/premium keyed by atom rather than control, with no suppression path. 64.10 explicitly deletes the expression `S_rob \ S_opt`.

#### Residual reachability is a set, never a magnitude

**Part I.** 25.6H: the frontier yields "the exact Pareto set of `(declared_cost, residual_reachability)`" — residual reachability used as a numeric frontier axis; 25.11: `GET /api/v1/eclipse/frontier -> [{cost, residual, cut, evidence:[EventId]}]`.

**Part II.** 64.4 ("OVERRIDES Part I: ECLIPSE §4H used 'residual reachability' as a frontier axis, which implies a magnitude"): Residual is a struct of `goals_derivable`, `goals_severed`, `corridors_open`, `program`, `corridors_exhaustive`; scalarisation is banned (64.4.2: no field named residual_reachability/residual_score/coverage/score/... enforced by `make lint-no-scores`); comparison is by set inclusion only, with incomparable residuals reported as incomparable and no better/worse string anywhere (64.4.4).

**Impact.** Part I's frontier axis and API field cannot exist as specified; any chart or sort that treats residual reachability as a number fails the no-scores lint, and the Playwright rule in 64.4.3 requires counts to sit adjacent to the list they count.

#### Redundancy index is no longer unconditionally exact and must be omitted on capped runs

**Part I.** 25.6F: `red(i,j)` over atom pairs, "Exact, O(|Psi|·|A|^2) with popcounts, scenario-scoped"; 25.11 exposes `GET /api/v1/eclipse/redundancy -> matrix` and `spectra eclipse redundancy --format csv|md` unconditionally, while 25.6B permits corridor/grounding caps.

**Part II.** 64.5 ("OVERRIDES Part I: ECLIPSE §4F called red(i,j) 'exact, free, scenario-scoped' while §6 permitted corridor enumeration to be capped ... The unconditional exactness claim is withdrawn"): Jaccard is defined over controls (`hits(c_k, κ) ⟺ ∃ℓ. x_{k,ℓ} ∈ κ`), emitted only when psi_complete AND no grounding cap AND no corridor cap AND no horizon truncation AND no budget exhaustion; suppression is key-absence, never null/0/-1/"N/A"; serialised as a reduced rational {num, den}, no floats; new Go checker check (g) rejects a certificate carrying it while any suppressing flag is set.

**Impact.** A Part I implementer computes atom-pair Jaccard over a truncated Psi, calls it exact, returns a dense matrix on capped runs, and renders a float — all four are now build/checker failures.

#### P_max is a superset of realizable worlds; ROBUST's meaning and counterexample soundness restated

**Part I.** 25.13: "ROBUST means 'holds for every hypothesis the licenses admit under this catalog'"; 25.6E presents the two-fixpoint construction as delivering "breaks the attack in every evidence-consistent world"; counterexample trees (25.11) carry no realizability information.

**Part II.** 64.6 ("OVERRIDES Part I: ECLIPSE §9 asserted ... as if the two-fixpoint construction computed exactly that quantifier. It does not."): P_max ignores mutual-exclusion structure, so Reach(P_max) is a strict superset of the union over realizable worlds. ROBUST stays sound (64.6.1) but UNSAFE verdicts and every P_max-derived counterexample may be unrealizable (64.6.2). Every counterexample must carry a `realizability` object with status REALIZABLE/UNREALIZABLE/UNDECIDED and four mandatory decidable checks (exclusive_group, functional_key, license_window, obligation_multiplicity); no tree may be displayed, exported or narrated without its badge, and `make demo` fails unless its headline counterexample is REALIZABLE.

**Impact.** Part I's licensed ROBUST sentence is now a forbidden claim, and a Part I implementation has no realizability computation at all, so every counterexample it emits is rejected by 64.8's row `counterexamples[].realizability` and the demo gate.

#### Cost frontier with no costs.toml: the label `cost_basis` is itself now banned

**Part I.** 25.6H: "If `costs.toml` is absent, the frontier is computed over cardinality instead and is labeled `cost_basis: \"cardinality\"`"; CLI `spectra eclipse frontier --costs costs.toml --budget-grid 0:100:5`.

**Part II.** 64.7 ("OVERRIDES Part I: ECLIPSE §4H described a Pareto frontier over '(declared cost, residual reachability)' without saying what happens when costs.toml is absent"): with no costs.toml the axis is named `cut_cardinality` / "controls raised", and the words cost, price, budget, spend, ROI, investment, $ and USD are forbidden in that mode, enforced by `make lint-no-costs` over the API schema, TS types, chart config and export writers; no unit-cost mode, flag or env var may exist; a missing (control, level) entry in a present costs.toml is a hard error, not a zero.

**Impact.** Part II's own override text mis-states Part I (Part I did specify the absent-costs behaviour), so the concrete conflict is easy to miss: the field name Part I mandates, `cost_basis`, contains a banned cost word and fails `make lint-no-costs` in exactly the mode Part I requires it. The key must be renamed to `cut_cardinality` / `frontier_scope`-style naming everywhere.

## 65 Liveness estimation

### UNRESOLVED

#### License intervals: ticks (Part I) vs. nanoseconds on a record-timestamp grid (Part II)

**Tension.** Part I indexes derived facts at tick granularity Δ (17.1.6, default 1 s, hashed into the certificate) and types licenses as `interval: (Tick, Tick)` (§25.5), with the certificate example `"interval":[1710,4110]`. Part II computes verdicts on a nanosecond grid whose breakpoints are record timestamps, regime boundaries and envelope-stage endpoints (65.5.3), reports intervals as `u64` ns (`t0: 1700000000000000000`) and measures blind volume in nanoseconds, 'never in number of windows' (65.8.1). Neither part says how one maps to the other. Part I is itself split — 19.3's edge JSON already uses ns license bounds while §25.5 uses ticks — so Part II does not settle it. Separately, 17.4.2 and §25.6-C need a single boolean `live(s, I)` over a caller-supplied interval, while Part II only produces a run-length-encoded sequence of per-elementary-interval verdicts and never defines the composition.

**Decision needed.** Decide (a) whether `License.interval` and `liveness.json` intervals are ns or ticks, and if ticks, which rounding direction applies when an ns-grid BLIND interval is shorter than Δ or straddles a tick boundary; and (b) define `live(s, I)` for a composite interval as a function of the elementary verdicts it spans.

**Recommended.** Make all liveness and license bounds `u64` ns (Part II's form), convert to ticks only at the grounding boundary, and define `live(s, I) = every elementary sub-interval of I is LIVE` — i.e. any BLIND or SUPPRESSED sub-interval makes the whole interval non-LIVE, which is the fail-closed direction the EDR demands. Fix 19.3/§25.5 to match.

#### Rule thresholds may still be self-calibrated from the run's own bundle

**Tension.** 05-temporal.md 17.5.1 explicitly permits data-derived rule thresholds: 'Where a rule needs a data-derived threshold, it may use only quantiles computed from **this run's own bundle**, the quantile definition must be named (`q99` = nearest-rank, inclusive)'. Part II's ban is scoped: 65.12.1 forbids run-derived statistics 'for any purpose that feeds a liveness verdict', and the estimator ban, float ban and dependency gates (65.3.3, 65.9.4 G65.1/G65.5) apply to the liveness crate and profile parser only. Section 65 never mentions 17.5.1. But the exploit 65.0 diagrams is not liveness-specific: a run-derived burst threshold is computed from the same evidence an adversary deletes, and a threshold that moves the wrong way suppresses rule instances, which shrinks `P_max` without any positive recorded evidence — a direct EDR clause-2 violation outside the stage EDR governs.

**Decision needed.** Is 17.5.1 retained, or does the profile mechanism extend to rule thresholds? If retained, state explicitly why a tamper-movable threshold in the grounding path is acceptable when the same construct is a build-failing defect in the liveness path, and say what flag a run using one must set.

**Recommended.** Extend the `SourceProfile` mechanism (or a rule-threshold equivalent with the same B1-style anti-self-calibration gate) to any data-derived rule threshold, and delete 17.5.1's 'this run's own bundle' allowance. If any exception survives, it needs its own soundness-blocking flag. Note also that 17.5.1's 'nearest-rank, inclusive q99' and 65.3's exact-rank `ceil(n*p/q)` are two distinct estimator definitions shipping in one binary; they should be unified on the 65.3 form.

#### Rule-test fixtures declare liveness directly, which section 65 makes underivable

**Tension.** 05-temporal.md 18.8 fixtures supply liveness as fixture input — `sources: { idp_auth: { live: [[0, 40000]] }, api_gw: { live: [[0, 40000]] } }` with `expect_observed: OBSERVED`, and `lic_001` asserts `expect_licenses: [{ source: idp_auth, covers: [20, 100], basis: BLIND }]`. V17 also requires `silent_possible: true` rules to have 'at least one source able to be BLIND'. Under section 65 a verdict is a pure function of a hashed `SourceProfile`, the observed records and `liveness.toml`: LIVE is constructible only at R11 (65.5.2), requires `n_gaps >= n_min` (default floor 30, 500 at 99/100 with K_TAIL=5) and `n_records_in_span >= m_min`, and with no profile every window is BLIND under F1/F2. A fixture with a handful of synthetic events can satisfy none of that, so every `expect_observed: OBSERVED` fixture in the Part I corpus becomes unreachable.

**Decision needed.** Do rule fixtures inject liveness verdicts through a test-only oracle that bypasses the classifier, or must every fixture ship a synthetic `SourceProfile` and enough events to clear `n_min`/`m_min`? If an injection path exists, how is it kept out of production given 65.1's lint that `Verdict::Live` is constructed at exactly one site?

**Recommended.** Give the harness a test-only `Verdict` source behind a cfg(test)-gated type that the `lint-edr` gate explicitly whitelists by path, keep fixture-declared liveness as harness input, and add a gate asserting the production binary contains no reference to it. Then restate 18.8 and V17 in terms of Part II's LIVE/BLIND/SUPPRESSED lattice and reason codes.

#### Absolute zero-false-ROBUST gate vs. a pre-registered nonzero false-LIVE ceiling

**Tension.** §25.12.7 (`degradation_invariant`, called the headline gate) requires that across the entire 100%→30% completeness matrix 'the number of FALSE ROBUST verdicts MUST be zero. Any single occurrence fails the build.' 65.9.2 gates the false-LIVE (Type-L) rate differently: 'build fails if the rate at any cell exceeds the pre-registered ceiling in the ratchet file, or regresses against it' — i.e. a nonzero ceiling is contemplated, on the very error class Part II's own table labels 'path to false ROBUST'. Part II never says whether §25.12.7 survives unchanged.

**Decision needed.** Is the pre-registered false-LIVE ceiling required to be zero, or is §25.12.7 relaxed? If both stand as written, state the argument for why a nonzero per-cell false-LIVE rate cannot produce a false ROBUST — that argument does not exist in either part today.

**Recommended.** Keep §25.12.7 absolute and additionally keep the 65.9.2 ceiling as a leading indicator, but set the shipped ceiling to zero for any cell where the goal is reachable in `P_min`. Otherwise the headline 'zero false ROBUST' claim in the README and §25.12.7 is not supported by the gate that is actually enforced.

#### ROBUST resting on an unauthenticated LIVE verdict

**Tension.** 65.6.3 concedes that inserting a record inside a gap to make a BLIND window look LIVE 'is not detectable' for `sequenced` and `none` sources, and responds only by setting `liveness_unauthenticated` and adding a docs caveat — LIVE is still issued, the license is still withheld, `P_max` still shrinks. Part I §25.9 takes the opposite stance for its own flags: 'A run with ANY flag set ... MUST NOT be presented as ROBUST', returning `OPTIMISTIC_ONLY` with `downgraded_by`, and §25.12.7 demands zero false ROBUST. Section 65 also declares that at least one source per scenario family MUST be `none` (65.5.1), so this path is present in every run by construction.

**Decision needed.** Does `liveness_unauthenticated` (and the `sequenced`-class `S_SEQ_GAP_UNAUTHENTICATED` path) block ROBUST the way Part I's flags do, or may ROBUST be claimed with a scope caveat? Equivalently: may a withheld license rest on a forgeable LIVE verdict at all?

**Recommended.** Treat LIVE on a non-`chained` source as soundness-affecting: either block ROBUST whenever a corridor's absence depends on such a verdict (consistent with §25.9 and with 65.1's EDR clause 2, since a forgeable LIVE is not 'positive, recorded, re-checkable evidence'), or forbid LIVE on `none`-class sources entirely and let 65.6.3's caveat cover `sequenced` only. Decide before the flag semantics are frozen.

#### Ownership of the difference-constraint pass vs. the liveness crate's dependency isolation

**Tension.** 17.1.5 places the backdating pass in the temporal engine and says it 'is a hard input to ECLIPSE stage A; do not duplicate it in the kernel' — while §25.6-A runs Bellman-Ford inside stage A, so Part I already contradicts itself. Part II 65.6 puts the whole dispute protocol inside the liveness section and requires it to consume event timestamps, rule-table happens-before edges and the resulting license set. But 65.2.5 requires `classify` to take 'no bundle handle, no fact base, no `&[u64]` sample' and `make lint-liveness-deps` asserts the `spectra-liveness` crate's dependency closure excludes the ingest and grounding crates — the exact inputs 65.6.1 needs. Step 4 additionally needs licenses, which only exist after the silent-envelope stage that consumes liveness output.

**Decision needed.** Which crate owns the difference-constraint pass, at what point in the pipeline does it run relative to grounding and the silent envelope, and what typed, hashed artifact carries the constraint graph and license set into it without reintroducing the bundle dependency the anti-self-calibration design is built on?

**Recommended.** Split it: keep `spectra-liveness` narrow (threshold + classification, no bundle) and put the DCG/dispute protocol in a separate `spectra-temporal-consistency` crate that runs after grounding and emits a `tamper_suspected` set plus `tamper_sensitivity` block merged into `liveness.json`. Then amend 17.1.5's 'do not duplicate it in the kernel' and §25.6-A to name that one owner.

### SILENT

#### 17.1.5 still excludes BACKDATED records from licensing

**Part I.** 05-temporal.md 17.1.5: 'Mark every record in the cycle `BACKDATED`, exclude it from licensing ECLIPSE silent instances, and emit the cycle itself as evidence. Output `liveness.json` carries the voided license set.'

**Part II.** 65.6 quotes and overrides only ECLIPSE §4A's wording ('voids licenses resting on provably backdated timestamps'). It never mentions 17.1.5, which states the same behaviour at record granularity rather than license granularity, and which additionally says this pass is a hard input to ECLIPSE stage A.

**Impact.** An implementer building the temporal engine from 05-temporal.md alone implements exactly the attack 65.6 exists to close: tampered timestamps remove licensing power, `P_max` shrinks, and the verdict moves toward ROBUST. The record-level exclusion in 17.1.5 must be explicitly struck and replaced by the `TEMPORALLY_DISPUTED` marking, or the two mechanisms will both ship and the record-level one wins first.

#### Difference-constraint graph edge set is defined differently in the two parts

**Part I.** 17.1.5: edges come from 'every pair with a causally forced ordering (same session, same file descriptor, same TCP flow, same chained sequence)', contributing `t_a - t_b <= w`.

**Part II.** 65.6.1 step 1: build the graph 'over event timestamps from happens-before edges declared by the rule table plus per-source `seq` monotonicity', with a canonical `(src_event, dst_event)` lexicographic edge order and a step budget. Session / file-descriptor / TCP-flow pairing is gone; rule-table-declared happens-before is new. No override marker.

**Impact.** Two different graphs yield different negative cycles, hence different correction sets `C`, different `tamper_suspected` sets and different `verdict_tamper_sensitive` values. Since 65.6.2 requires the Go checker to independently recompute `tamper_suspected` and reject disagreeing certificates, a Rust implementation following 17.1.5 and a Go checker following 65.6.1 will reject valid certificates (or vice versa) with no diagnostic pointing at the edge-set definition.

#### Skew envelopes are ignored by the liveness computation

**Part I.** 17.1.4: `sources.toml` declares a per-source skew envelope `skew(s) = [lo_s, hi_s]`; a record asserting `t_evt` 'is treated as having occurred somewhere in `[t_evt + lo_s, t_evt + hi_s]`. All window and sequence operators evaluate over these intervals, not points.' An operator needing a strict order between overlapping intervals must not fire; it emits `order_indeterminate` and is never silently resolved.

**Part II.** 65.2.2 emits gaps as consecutive differences of point timestamps; 65.2.5 defines brackets as 'record at t <= window.0' / 't >= window.1' and carries a single scalar `max_observed_gap_ns`; 65.5.3 builds the breakpoint grid from 'every observed record timestamp on s' as points. Skew is not mentioned anywhere in section 65.

**Impact.** Silently converts an interval-valued time model into a point-valued one inside the one stage whose soundness the whole hardening addendum is about. The error is anti-conservative in exactly the wrong direction: with skew, a true gap can be up to `(hi_s - lo_s)` larger than the point difference, so a window whose real worst-case gap exceeds `T(s,r)` can be classified LIVE, the license is withheld, `P_max` shrinks — an EDR clause-2 violation produced by following Part I faithfully. Bracket determination has the same problem: a 'bracketing' record whose interval straddles the window edge does not bracket it.

#### BLIND licenses lose their witness events and their identity

**Part I.** §25.5 `License { source, interval, basis, witness: Vec<EventId> }` with the comment 'records bracketing / chain break evidence'; §25.7 `licenses_used` publishes `witness`; §25.8(c/d) and 05-temporal.md 19.8.1 make this load-bearing: 'Every edge must dereference to concrete `EventId`s, or to licenses that themselves dereference to the witness events establishing blindness. There is no third category.' 19.9's worked output shows a BLIND license with `witness ev:5c20.. (last record before gap), ev:5c21.. (chain break)`, and 18.7's finding-provenance schema requires `license_id` on every license.

**Part II.** 65.5.2: 'a SUPPRESSED window carries `witness: [event_of_seq_i, event_of_seq_j]` and a missing-`seq` count; a BLIND window carries a reason code only.' The 65.7 schema confirms this — BLIND intervals have `verdict` and `reason` and nothing else, and no interval carries a `license_id`. No override marker.

**Impact.** Breaks the dereferenceability contract for every BLIND-based license, which is the common case (and the case the blindness premium is built from). An implementer cannot populate `cert.licenses_used[].witness`, `dependency_edge` license objects (19.3), or `finding_provenance.licenses[].license_id`, and the Go checker's checks 25.8(c)/(d) and 19.8.2(c) have nothing to resolve. Either 65.7 must carry license ids and bracketing witnesses on BLIND intervals, or 19.8.1's 'no third category' rule must be formally relaxed — but Part II does neither.

#### Liveness cache key does not include the profile

**Part I.** §25.10: content-addressed cache with key `liveness/<H(bundle, liveness_params)>`, and '`--no-cache` must reproduce byte-identical output'. The profile did not exist when this key was defined.

**Part II.** 65.2 makes `profile.json` a determining input to every threshold, and 65.2.4 binds it into the certificate — but section 65 never amends the cache-key derivation.

**Impact.** Two runs over the same bundle with different profiles (different `p/q`, different `slack`, different calibration seed band, or an INSUFFICIENT vs. CALIBRATED source) collide on the same cache key and the second run is served the first run's verdicts. That silently defeats gates B1..B6 at emit time on a warm cache and makes the 65.9.3 sensitivity sweep — which varies exactly `(p/q, slack)` over a fixed bundle set — return the first cell's results for every cell.

#### F2 suppresses outputs Part I mandates unconditionally

**Part I.** §25.6 F/G/H make the redundancy index, decisive observation set and blindness premium mandatory stage outputs; §25.7 carries `redundancy_witnesses` in the certificate and §25.8(e) has the checker re-derive them; §25.11 mandates `GET /api/v1/eclipse/premium`, `/decisive`, `/redundancy` and a UI that 'leads with' the premium; 19.7.3 requires a decisive observation set 'For every AMBIGUOUS set'.

**Part II.** 65.4: under F2 the blindness premium, decisive observation set and redundancy index 'are structurally suppressed from the certificate, the API response and the UI. Emitting them under F2 fails the schema lint.' 65.8.5 repeats it. There is no 'OVERRIDES Part I' marker on this rule.

**Impact.** An implementer reading Part I builds endpoints and a certificate with these fields always present, and a checker that re-derives `redundancy_witnesses`; under `--no-profile` the schema lint then fails the build, or the API contract breaks for consumers that assume the fields exist. 19.7.3's AMBIGUOUS rendering ('Making iam_audit live over [...] eliminates one') is also unproducible under F2, and nothing says what the UI shows instead.

### RESOLVED

#### Liveness threshold source: self-calibrated q99 vs. external SourceProfile

**Part I.** 07-replay.md §25.6 stage A: `live(s,[a,b])` iff (i) records bracket the window, (ii) the BLAKE3 sequence chain has no gap, (iii) `max inter-arrival <= q99(s)` computed from THIS run's own data — explicitly '(never a constant, never a tuned hyperparameter)'. Cache key §25.10 is `liveness/<H(bundle,liveness_params)>`.

**Part II.** 65.0 marks the clause OVERRIDDEN and deleted in its entirety: 'No liveness threshold may ever be derived from the bundle under analysis.' 65.2 makes the arrival model an input (`profile.json`) produced by `spectra calibrate` on a disjoint-seed identity-degradation reference run; 65.2.4 gates B1..B6 reject a profile whose `reference_bundle_hash == cert.hashes.bundle`; 65.2.5 removes any `Empirical`/`FromRun` variant from `ThresholdProvenance` and forbids the liveness crate from depending on ingest/grounding; 65.3 replaces the estimator with exact-rank integer order statistics plus a `slack` multiplier.

**Impact.** Correct direction, but note the residue: Part I's same sentence also forbade 'a constant' and 'a tuned hyperparameter', and Part II reintroduces both — F3 DECLARED uses a constant `nominal_period_ns`, and `(p/q, slack)` are selected by the 65.9.3 sweep. The 'OVERRIDES' quote covers only the q99 fragment, so an implementer could read the constant/hyperparameter prohibition as surviving. Worth restating the deletion as covering the whole clause.

#### Universal hash-chain assumption vs. declared integrity classes

**Part I.** §25.6 stage A conditions liveness on 'the BLAKE3 sequence chain over that source has no gap' for every source, and 05-temporal.md 17.1.2 lists `seq` as 'per-source monotone counter in BLAKE3 chain' with trust 'high' as one of three clocks carried on every record. §25.6-A: 'if a chain break localizes deletion, SUPPRESSED' — unconditionally.

**Part II.** 65.5.1 OVERRIDES: every source declares `integrity_class` of `chained` | `sequenced` | `none`. SUPPRESSED is authenticated only for `chained`, unauthenticated (forgeable) for `sequenced`, and never issuable for `none` (gaps can only ever be BLIND). At least one source per scenario family MUST be `none`, and results must be reported split by integrity class — an aggregate detection figure mixing classes is forbidden.

**Impact.** 17.1.2's three-clock table and any code treating `seq`/chain as always present must change: `seq` becomes optional, chain state becomes the `ChainState::{Verified,Unverified,Absent}` enum of 65.2.5, and the SUPPRESSED path of §25.6-A must be gated on class. Every scenario family also needs a new `none`-class source it did not have in Part I.

#### Backdating: voiding licenses vs. the dispute protocol

**Part I.** §25.6 stage A: 'any license resting on a provably backdated timestamp is voided and recorded in `liveness.json` as `voided_by_dcg`.' 05-temporal.md 17.1.5: a negative cycle 'proves at least one timestamp is fabricated. Mark every record in the cycle BACKDATED, exclude it from licensing ECLIPSE silent instances'; `liveness.json` 'carries the voided license set'.

**Part II.** 65.6 OVERRIDES: 'No license is ever removed from `P_max` by the temporal consistency pass.' A negative cycle does not identify which timestamp is wrong; compute the deterministic minimal correction set `C`, mark affected licenses `TEMPORALLY_DISPUTED` and retain them with full force, set `tamper_suspected` on contributing sources, compute the counterfactual verdict for reporting, and make ROBUST unconstructible (`Safety::Robust` needs a `NoTamperToken`) whenever a tamper flag is set or `verdict_tamper_sensitive` is true.

**Impact.** Removes the reward-the-attacker path, but it inverts the `liveness.json` contents (no `voided_by_dcg` set, new `tamper_sensitivity` block) and adds a private-constructor requirement to the certificate builder plus an independent Go-checker recomputation of `tamper_suspected`. See the SILENT entry: the parallel Part I statement at 17.1.5 is not amended.

#### ECLIPSE inputs, certificate hashes, liveness.json schema, and checker obligations

**Part I.** §25.3 lists the hashed inputs (bundle, rules, controls, costs, goal); §25.7 `hashes` carries rules/bundle/controls/liveness/goal; §25.8(d) requires the Go checker to verify every silent instance is licensed by `liveness.json`, 'whose derivation it RECOMPUTES from the bundle'; the `liveness.json` format is whatever stage A emits (per source, per window: LIVE|BLIND|SUPPRESSED, plus `voided_by_dcg`).

**Part II.** 65.2.1 OVERRIDES: the input list gains a mandatory `profile.json` and `Cert.hashes` gains a `profile` field. 65.2.4 OVERRIDES checker obligation (d): the checker recomputes the liveness derivation AND re-evaluates B1..B6 from the hashed inputs, rejecting with `PROFILE_SELF_CALIBRATED` etc. 65.7 OVERRIDES the output: `liveness.json` becomes `spectra.liveness/2` with per-source mode, threshold provenance, RLE intervals, `blind_volume_ns_by_reason`, `suppressed_volume_ns`, a fixed flag object and `tamper_sensitivity`, canonically serialized with integers only.

**Impact.** `spectra prove` must now refuse to start without `--profile` or `--no-profile` (65.10), the certificate schema version must bump, and the Go checker gains six new rejection codes at both emit and verify time. Note Part II calls `profile.json` 'a fifth mandatory input' while Part I §25.3 already lists five inputs — the cross-reference is off by one and should be corrected to avoid an implementer deleting `costs.toml`.

## 66 Verdict and flag algebra

### UNRESOLVED

#### Does the `mode` *request* parameter survive the deletion of `cert.mode`?

**Tension.** Part II deletes only 'the certificate field `mode`' but its algebra (§66.4) derives safety from both fixpoints on every run, so selecting a mode up front is meaningless. Part I uses `mode` in three other load-bearing places that Part II does not touch: the request body `POST /api/v1/eclipse/prove {"mode": "ROBUST", ...}` (11-api.md §36.4), the CLI flag `spectra eclipse prove [--mode robust|optimistic]` / `spectra whatif prove --mode robust` (07-replay.md §25.11, 11-api.md §37.4) — which §37.3 names as a release-pipeline CI gate that 'must exit 0' — and the DB uniqueness/content key `proof_content_key_idx ON proof_cert (rules_hash, bundle_hash, controls_hash, goal_hash, mode, horizon_k, seed)` plus `cache/eclipse/cert/<H(psi,mode,costs)>` (07-replay.md §25.10).

**Decision needed.** Decide whether `mode` is deleted everywhere (request, CLI flag, cache key, content key) or survives as a request-only knob. If deleted, the proof content key and the eclipse cache key both lose a discriminator and must be respecified; the release CI gate command must be rewritten. If retained, specify what a `--mode optimistic` request means now that safety is computed from both fixpoints unconditionally.

**Recommended.** Delete `mode` everywhere: drop the flag and the request field, and replace `mode` in `proof_content_key_idx` and the `cert/` cache key with the flags mask plus the `er` scope hash, which are the inputs that actually discriminate two certificates under §66.

#### `atoms_over_budget` is unreachable under Part I's control compiler and u64 cut type

**Tension.** §66.3 bit 2 defines `atoms_over_budget` as set when 'Σ m_k > 64', and §66.9 corpus case 3 makes an `atoms_over_budget` + ROBUST + SUBSET certificate a mandatory, must-ACCEPT regression test. But 07-replay.md §22.2 says 'The global atom budget is `Σ_k m_k ≤ 64`; the compiler fails with `E_ATOM_BUDGET` above it, printing the current count' — the pipeline cannot produce a catalog with more than 64 atoms at all. §25.5 reinforces this physically: `pub type Cut = u64`, `blockers: u64`, `// |A| <= 64`, and §38.2 stores `corridor.atom_mask BIGINT`. Part I §25.9's 'above that the kernel downgrades to subset-minimal' was already unreachable for the same reason; Part II inherits the dead branch without mentioning §22.2.

**Decision needed.** Decide whether the 64-atom hard compile failure is lifted (requiring a wider mask type, a new corridor storage representation, and a redesigned `min_cardinality_model` B&B) or kept (in which case `atoms_over_budget` can only ever be set by some other condition, and conformance case 3 must be reclassified as a pure unit-level check of the algebra rather than an end-to-end regression).

**Recommended.** Keep the §22.2 compile-time cap and re-state case 3 explicitly as an algebra-level conformance case over synthetic VerdictProposals, with a note in §66.3 bit 2 that the flag is currently unreachable from the production pipeline. Widening the cut type touches the fixpoint, the hitting-set solver, the certificate and the DDL and is a far larger change than §66 implies.

#### No exit code for INDETERMINATE, and exit 8 is now wrong for non-soundness flags

**Tension.** 11-api.md §37.3's exit table — declared 'Identical across all subcommands' — maps `0` = 'success; for `whatif prove`, verdict ROBUST', `6` = 'verdict UNSAFE', `8` = 'result is flagged (capped grounding, subset-minimal, greedy cover) — usable but not ROBUST'. Part II adds a fourth safety value with no exit code, and makes ROBUST legally co-occur with `greedy_cover`/`sampled_matrix`, so a run can simultaneously satisfy the exit-0 condition (ROBUST) and the exit-8 condition (flagged). Part II's §66.8 exit table covers only `spectra verify`, not `prove`.

**Decision needed.** Assign an exit code to INDETERMINATE and redefine exit 8 — either narrow it to 'a soundness-class flag is set' (making it mutually exclusive with ROBUST) or delete it in favour of exit codes keyed on the safety axis alone. Also state whether OPTIMISTIC_ONLY has a distinct code.

**Recommended.** Key `prove` exit codes on the safety axis only (0 = ROBUST, 6 = UNSAFE, new 11 = INDETERMINATE, keep OPTIMISTIC_ONLY at 0 or give it its own code) and repurpose exit 8 to mean 'a soundness-class flag is set', which is now the only condition that makes ROBUST unconstructible.

#### Who renders the verdict string, given the frontend may not derive displayed values

**Tension.** 12-frontend.md §42.2 is a non-negotiable: 'Every number, label, verdict and colour on screen maps to a field in a validated API response... The frontend may format and lay out. It may not derive', enforced by `no-derived-values.spec.ts`, which 'snapshots every numeric DOM node on each route against the API response bodies captured in the same run and asserts each value appears verbatim in a response'. Part II §66.7 acknowledges the §39-42 invariant for *computing* the verdict but then mandates a client-side renderer: `Verdict.renderShort()` composes the header string from 8-nybble truncated hashes (§66.2.3 rule 3: 'No truncation on the wire. Truncation to 8 nybbles happens only in the short rendering'), so the exact rendered text provably does not appear in any response body. §66.10's DOM gate then asserts 'the UI verdict header's `textContent` equals `Verdict.renderShort()` exactly', while 12-frontend.md §41.11 region 1 composes that header from a verdict chip, mode, the cut atoms, |S|, lower bound, corridor count, a cert-hash chip and a flags strip.

**Decision needed.** Decide (a) whether the server ships the rendered short string alongside `verdict_prose`, or the client renderer is explicitly exempted from the §42.2 no-derive gate — and update `no-derived-values.spec.ts`'s contract accordingly; and (b) which DOM node the 'verdict header' is, since the Part I header carries six other fields that would break a byte-for-byte equality assertion.

**Recommended.** Have the API return both `verdict_string` (short) and `verdict_prose` (long) as fields — §66.9 case 9 already assumes a certificate-level `verdict_string` — keep `Verdict.renderShort()` in the client purely as the validator that the returned string matches, and scope the DOM gate to a dedicated `[data-verdict-header]` element holding only that string, with the cut, |S| and flags strip as siblings.

### SILENT

#### greedy_cover (and sampled_matrix) no longer block ROBUST

**Part I.** 07-replay.md §25.9: 'A run with ANY flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) MUST NOT be presented as ROBUST: the API returns `mode: "OPTIMISTIC_ONLY"`... and the UI badge is grey, never green.' 11-api.md §36.5: 'Do not return `ROBUST` on any response whose `flags` contain a true value — the serializer must raise if that combination is constructed.' §38.2: `CONSTRAINT robust_never_flagged CHECK (verdict <> 'ROBUST' OR NOT (flag_capped OR flag_subset_only OR flag_greedy))`. §37.3 exit 8 for any flagged result. 12-frontend.md §40.4 rule 1: a run carrying greedy_cover 'must never be painted with the plain ROBUST chip'.

**Part II.** §66.3 bit 6 `greedy_cover` is class **D** — 'Does not block ROBUST'; bit 7 `sampled_matrix` is class **R** — 'Does not block a per-run ROBUST'. `SOUNDNESS_MASK = bits {0,1,3,4,5,8} = 0x013B` deliberately excludes bits 6 and 7, and §66.4 A1 makes ROBUST unconstructible only when `F ∩ S_MASK ≠ ∅`. §66.9 corpus item 1 requires that 'exactly the subsets disjoint from `SOUNDNESS_MASK` accept'.

**Impact.** Part II's override notes cover only `subset_minimal_only`; they never say Part I's 'ANY flag' rule is repealed. An implementer who writes the Part I DB CHECK constraint, the Part I serializer guard, or the Part I visual-regression test will make ROBUST+greedy_cover and ROBUST+sampled_matrix unstorable, unserializable and unpaintable — and will fail Part II's mandatory 512-subset conformance sweep, which requires those exact combinations to be accepted.

#### Automatic downgrade to OPTIMISTIC_ONLY versus the INDETERMINATE fail-closed sink

**Part I.** 07-replay.md §25.9: when a flag is set 'the API returns `mode: "OPTIMISTIC_ONLY"` with `downgraded_by: ["grounding_capped"]`' — i.e. a blocked ROBUST is relabelled OPTIMISTIC_ONLY regardless of the fixpoint results.

**Part II.** §66.2.1 makes OPTIMISTIC_ONLY constructible only when 'the goal is not derivable in P_min but is derivable in P_max'; §66.4's decision flow sends a run with a soundness flag whose goal is not derivable in P_min (no witness) to INDETERMINATE, not OPTIMISTIC_ONLY. §66.2.3's canonical object has no `downgraded_by` field.

**Impact.** Part II never mentions the downgrade rule or the `downgraded_by` field. An implementer following §25.9 emits OPTIMISTIC_ONLY for a run whose goal is in fact unreachable in P_max — a factually false safety claim under Part II's own definition — for precisely the flagged runs Part II created INDETERMINATE to describe. The certificate also carries a field absent from the canonical schema.

#### Scope binding requires an ER hash and an attacker literal the Part I certificate does not have

**Part I.** 07-replay.md §25.7 certificate: `"hashes": {"rules", "bundle", "controls", "liveness", "goal"}` — five hashes, no entity-resolution hash and no attacker field. 11-api.md §38.2 proof_cert has exactly `rules_hash, bundle_hash, controls_hash, liveness_hash, goal_hash` and the content-key index over the same set. §25.8's checker invocation takes `--bundle --rules --controls` only.

**Part II.** §66.2.3 and §66.4 A9: 'scope is total: all six hashes present, non-empty, well-formed; attacker = "non-adaptive"', the six being rules, controls, liveness, er, goal, bundle. §66.8 VRD-005 rejects (exit 2) any certificate with an incomplete scope or `attacker != "non-adaptive"`; §66.9 case 5 requires rejection with each of the six missing in turn. §66.8's checker invocation adds `--er out/er.json`.

**Impact.** Part II never states that it is adding the ER hash or the attacker binding to the certificate. Every certificate built to Part I §25.7 and every row storable in the Part I proof_cert table lacks `er@` and `attacker`, so the Go checker rejects 100% of them with VRD-005. The DDL needs an `er_hash` column and the content-key unique index needs to include it, or two runs with different entity resolution collide on one cache key.

#### Flag wire representation changed from a boolean object to a bit-ordered name array

**Part I.** 07-replay.md §25.7: `"flags": {"grounding_capped": false, "subset_minimal_only": false, "greedy_cover": false}` — a three-key object of booleans; repeated identically in 11-api.md §36.4's /blindness-premium payload. §38.2 stores them as three boolean columns `flag_capped, flag_subset_only, flag_greedy`.

**Part II.** §66.2.3 canonicalization rule 1: '`flags` is a JSON array of flag names sorted by **bit position**, never alphabetically, never a bitmask in the wire format. The checker recomputes the mask and rejects duplicates.' §66.3 fixes nine flags at fixed bit positions with reserved bits 9..15 that must be zero. §66.8 VRD-008 rejects a flag name that is 'unknown, duplicated, or out of bit order'; §66.9 case 8 requires rejection of an alphabetically sorted array.

**Impact.** The only override Part II declares about flags concerns `subset_minimal_only`'s semantics, not the representation. An implementer emitting the Part I flags object (or a serializer built from the three boolean columns) produces a certificate the checker cannot parse; a naive migration that serializes the columns in declaration order yields alphabetical-ish ordering and fails VRD-008. Six of the nine flags have no storage at all in the Part I DDL.

#### Checker exit codes redefined

**Part I.** 07-replay.md §25.8: 'Exit codes: `0` OK, `2` invariant violated, `3` license unlicensed, `4` witness invalid, `5` smaller cut exists, `6` input hash mismatch.' 11-api.md §37.3 declares its exit table 'Identical across all subcommands' with `4` = validation failed (hash mismatch), `5` = integrity violation, `7` = verification failed (checker rejected a certificate).

**Part II.** §66.8: 'Exit codes: `0` accept, `1` certificate internally consistent but a proof obligation failed (closure, witness, Ψ), `2` verdict-algebra violation, `3` malformed input.' The sample rejection transcript ends `exit=2`.

**Impact.** Part II gives no override notice. The same integer now means different things in three places: exit 2 is 'invariant violated' in §25.8 but 'verdict-algebra violation' in §66.8; a smaller-cut-exists failure is exit 5 in Part I and exit 1 in Part II; a checker rejection is exit 7 under the Part I CLI table and exit 2 under Part II. CI gates and the /eclipse/verify endpoint, which surfaces 'checker stdout + exit code', will classify rejections wrongly — in particular a Part I gate treating only 0 as pass but 2 as 'invariant violated' will mislabel every algebra violation.

#### Liveness threshold: self-calibrated q99 versus a hashed clean-baseline profile

**Part I.** 07-replay.md §25.6 A: liveness holds iff '(iii) max inter-arrival ≤ `q99(s)` computed from THIS run's own data (never a constant, never a tuned hyperparameter)'. 11-api.md §38 query Q4 implements it: 'inter-arrival outliers measured against this run's own q99, never a hard-coded threshold', via `percentile_cont(0.99) WITHIN GROUP (ORDER BY interarrival)` over the run's own events.

**Part II.** §66.3 bit 8 `profile_missing`: 'The hashed clean-baseline arrival profile was absent for at least one source. Without it the liveness threshold would have to be self-calibrated from the run's own (possibly deleted) data — the known false-ROBUST path. Sources with no profile are forced BLIND.' Class **S**: blocks ROBUST.

**Impact.** Part II declares the exact mechanism Part I mandates to be the known false-ROBUST path, without ever saying it overrides §25.6 A. An implementer who builds liveness to Part I has no clean-baseline profile artifact at all, so `profile_missing` is set on every run, every source is forced BLIND, and no run in the system can ever produce a constructible ROBUST verdict. This also silently adds a new hashed input (the arrival profile) that appears in neither §25.3's input table nor the certificate's scope.

#### Voided licenses now block ROBUST

**Part I.** 07-replay.md §25.6 A: the Bellman-Ford difference-constraint pass voids any license resting on a provably backdated timestamp and records it in `liveness.json` as `voided_by_dcg` — with no verdict consequence. §25.8's accepting transcript prints 'OK: 3 silent instances licensed; liveness recomputed, 0 voided differences' and then 'VERDICT ROBUST'. 11-api.md §38.2 `license.voided BOOLEAN NOT NULL DEFAULT false, -- set by the difference-constraint pass`, with no link to the verdict.

**Part II.** §66.3 bit 5 `license_voided_by_suspected_tampering`: set when 'the difference-constraint pass voided at least one license on suspected backdating... an attacker who controls timestamps could otherwise manufacture one.' Class **S**: 'Blocks ROBUST. Fail-closed by construction.'

**Impact.** No override notice. Part I treats voiding as routine hygiene that tightens P_max; Part II treats it as evidence of tampering that makes ROBUST unconstructible. An implementer following Part I emits ROBUST on a run with voided licenses and the Go checker rejects it with VRD-001; conversely, the Part I liveness output carries no field the verdict builder can read to set bit 5.

#### Redundancy index must be suppressed under caps

**Part I.** 07-replay.md §25.6 F computes the redundancy index unconditionally from Psi; §25.11 exposes `GET /api/v1/eclipse/redundancy -> matrix` and `spectra eclipse redundancy --format csv|md`, and the /prove UI always shows 'a redundancy heatmap'. 11-api.md §36.3 lists `GET /api/v1/eclipse/proofs/{cert_id}/redundancy` returning `RedundancyMatrix` with no conditionality. Part I's only cap behaviour is §25.6 B: 'On a cap, set `flags.grounding_capped = true` and publish the measured sizes.'

**Part II.** §66.4 A7: '`derived_suppressed ⊇ {redundancy_index}` if `corridor_cap ∈ F` or `grounding_capped ∈ F`'; §66.3 bit 1 'suppresses the redundancy index'. §66.8 VRD-014 rejects (exit 2) a certificate whose `derived_suppressed` 'omits an entry required by A7/A8'.

**Impact.** Part II never says it is overriding the unconditional redundancy surface. An implementer following Part I serves a redundancy matrix on a grounding_capped run and emits a certificate with an empty `derived_suppressed`, which the checker rejects with VRD-014 — and the UI heatmap displays a quantity the spec now requires to be withheld.

#### Cardinality-basis cost frontier versus mandatory pareto_frontier suppression

**Part I.** 07-replay.md §25.6 H: 'If `costs.toml` is absent, the frontier is computed over cardinality instead and is labeled `cost_basis: "cardinality"`.' §25.3 marks costs.toml 'may be absent'.

**Part II.** §66.4 A8: '`derived_suppressed ⊇ {pareto_frontier}` if no costs.toml was supplied', enforced by VRD-014 in §66.8.

**Impact.** Part II never mentions §25.6 H. The two rules are opposite: Part I says compute and label a cardinality-basis frontier when costs are absent; Part II says the frontier must be listed as suppressed. An implementer of §25.6 H gets VRD-014 on every costs-free run. (12-frontend.md §41.11 region 6 already sides with hiding it, so Part I is internally split and Part II resolves it without saying so.)

#### 'no smaller cut exists' is licensed phrasing in Part I and an unconditional banned substring in Part II

**Part I.** 07-replay.md §25.13 FORBIDDEN CLAIMS: it must not be claimed 'That "no smaller cut exists" in general. The only licensed phrasing is "no smaller cut exists over the declared control catalog".'

**Part II.** §66.10 `banned_substrings`, introduced as 'Always illegal, anywhere, no allowlist', lists `"no smaller cut exists"` and `"minimum cut"`. §66.2.2 adds: 'Forbidden strings: "no smaller cut exists", "minimum cut", "cardinality-minimal" on any certificate whose minimality is not `EXACT_EXHAUSTIVE`', and `EXACT_PSI_RELATIVE` 'renders as "no smaller cut satisfies the enumerated corridor set", never as "minimum"'.

**Impact.** Part II never states it is withdrawing Part I's licensed phrasing. An implementer who writes the §25.13-approved sentence into docs or the UI trips `make lint-verdict-scope` via a substring rule that explicitly admits no allowlist. The same collision hits 12-frontend.md §41.11 region 1, which requires the Proof header to show the 'minimum cut rendered as atoms'.

#### Part I's mandatory verbatim Proof-screen footer is itself a lint violation under Part II

**Part I.** 12-frontend.md §42.8.6: 'The Proof screen footer states verbatim: "Soundness is relative to the rule table, entity resolution, the declared control catalogue and the telemetry ingested. ROBUST means: holds for every hypothesis the licenses admit under this catalogue. This is not formal verification of any real system."' (Non-negotiable; each §42 rule is a release blocker.) The same sentence pattern appears in 07-replay.md §25.13.

**Part II.** §66.5.1: the token `ROBUST` 'may never appear as a standalone user-visible string in ... UI text nodes, docs, README...'; a token occurrence is legal only if followed on the same logical line by a well-formed scope body, or in an allowlisted file (`spec/verdict/flags.toml`, `spec/verdict/algebra.toml`, `LIMITATIONS.md` — the Proof screen is not among them). §66.5.2 mandates a different trailing sentence: 'This is a statement about the model, not about the system.' — 'is not optional. Removing it fails `make lint-verdict-scope`.'

**Impact.** Part II never mentions §42.8.6. Implementing the verbatim footer Part I calls non-negotiable fails the scope lint on the phrase 'ROBUST means:'. The build now has two different mandatory closing scope sentences with no statement about whether the footer is replaced, rewritten, or kept alongside the long rendering.

#### FLAGGED is no longer a verdict value

**Part I.** 12-frontend.md §40.4 lists FLAGGED as a fourth row of the Verdict palette ('inherits verdict hue ... mandatory cross-hatch overlay + flag icon'), and §40.6 states 'SPECTRA's verdict vocabulary is ROBUST / OPTIMISTIC-ONLY / UNSAFE / FLAGGED'. §42.4 rule 3 requires any value whose `exactness` is not `exact` to render 'with the FLAGGED cross-hatch treatment'. 07-replay.md §25.9 adds 'the UI badge is grey, never green'.

**Part II.** §66.1 makes safety, minimality and flags three independent axes, with the safety alphabet being exactly {ROBUST, OPTIMISTIC_ONLY, UNSAFE, INDETERMINATE}; flags are a separate u16 with per-class effects and are not a verdict value. §66.5.2's grammar admits only the four safety tokens plus a minimality clause — there is no FLAGGED token and no grey-badge state.

**Impact.** Part II's declared alphabet override only mentions adding INDETERMINATE, not removing FLAGGED. An implementer keeps a palette entry and a vocabulary that Part II's type cannot produce, and keeps painting greedy_cover/sampled_matrix runs as 'flagged — not a ROBUST result', which is now a false statement about a legitimately constructible ROBUST verdict.

#### `severity` survives as an API field name that Part II bans outright

**Part I.** 12-frontend.md §41.2 and its route table specify `GET /api/v1/investigations?q&status&severity&sort&page` (server-side filter/sort/page) — `severity` is a query parameter of the public API. 11-api.md §36.5 bans only *returning* a risk/confidence/severity score, not the parameter.

**Part II.** §66.11: 'NEGATIVE REQUIREMENT, enforced by `make lint-no-scores` over the OpenAPI document, the SQL DDL, the TypeScript types, the Rust structs, the Go structs and the certificate schema. The following field names, and any name containing them, are banned across the API, the database, the certificate and the frontend: confidence score severity probability ... percentile ...' The exemption allowlist is `redundancy_index`, `bit`, `cardinality`, `count`, `bytes`, `millis`.

**Impact.** Part II does not mention the investigations filter. Implementing 12-frontend.md §41.2 as written puts a banned name in the OpenAPI document and the TypeScript query types, failing `make lint-no-scores`; the parameter must be renamed or dropped, and the frontend filter UI reworked. A literal name-substring lint over the SQL also hits Part I's §38 integrity query, which uses `percentile_cont(0.99) ... AS q99` — the alias is clean but the function name contains a banned token, so the lint needs a function-call carve-out that Part II does not define.

### RESOLVED

#### cert.mode deleted and replaced by a structured verdict object

**Part I.** 07-replay.md §25.7 emits a certificate whose first field is `"mode": "ROBUST" // ROBUST | OPTIMISTIC_ONLY | UNSAFE`; 11-api.md §36.4 returns `"mode": "ROBUST"` on /eclipse/prove and /blindness-premium; §38.2 DDL has `mode TEXT NOT NULL CHECK (mode IN ('ROBUST','OPTIMISTIC'))` plus a separate `verdict verdict_t` column, and the content-key unique index `proof_content_key_idx ... mode, horizon_k, seed`; 12-frontend.md §41.11 region 1 renders `mode (ROBUST / OPTIMISTIC)` in the Proof header.

**Part II.** §66.0: 'OVERRIDES Part I: the certificate field `mode: ROBUST|OPTIMISTIC` (ECLIPSE §5) is deleted. It is replaced by a structured `verdict` object specified in 66.2. Any code, schema, fixture or document still referencing `cert.mode` fails `make lint-verdict`.' §66.2.3 gives the replacement: `verdict {safety, witness_class, minimality, flags[], scope{...}, derived_suppressed[]}`.

**Impact.** Explicitly flagged. Implementers must delete the `mode` column and response field, drop the duplicate `mode`/`verdict` split in proof_cert, and rebuild the Proof header. The Part I content-key unique index and the /eclipse/prove request body both keyed on `mode` and are left dangling (see unresolved).

#### subset_minimal_only flag deleted; atom-budget condition no longer blocks ROBUST

**Part I.** 07-replay.md §25.7 cert flags object contains `subset_minimal_only`; §25.9 'A run with ANY flag set (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) MUST NOT be presented as ROBUST'; 11-api.md §38.2 has column `flag_subset_only` and `CONSTRAINT robust_never_flagged CHECK (verdict <> 'ROBUST' OR NOT (flag_capped OR flag_subset_only OR flag_greedy))`; §37.3 exit code 8 = 'result is flagged (capped grounding, subset-minimal, greedy cover) — usable but not ROBUST'; 12-frontend.md §40.4 rule 1 and §42.8.5 name `subset_minimal_only` as a mandatory FLAGGED chip.

**Part II.** §66.0: 'OVERRIDES Part I: the flag `subset_minimal_only` (ECLIPSE §5) is deleted... Minimality is now an independent field (66.2.2) and the atom-budget condition is carried by the flag `atoms_over_budget` (66.3), which does **not** block ROBUST.' §66.3 bit 2 classes = [M] only; §66.4 A5 caps minimality at SUBSET; §66.9 corpus case 3 requires `atoms_over_budget` + `safety = ROBUST` + `minimality = SUBSET` to ACCEPT.

**Impact.** Explicitly flagged. The Part I DB CHECK constraint and the Part I API serializer would both reject the exact certificate Part II's mandatory conformance case 3 requires to be accepted. Every Part I artifact naming `subset_minimal_only` (cert schema, DDL column, exit-code table, UI flag chip list) must be rewritten.

#### Verdict alphabet extended with INDETERMINATE

**Part I.** 07-replay.md §25.9 defines exactly three verdicts and §25.13 states 'Verdicts are exactly `ROBUST / OPTIMISTIC_ONLY / UNSAFE`'; 11-api.md §38.2 `CREATE TYPE verdict_t AS ENUM ('ROBUST','OPTIMISTIC_ONLY','UNSAFE')`; 12-frontend.md §40.6 'SPECTRA's verdict vocabulary is ROBUST / OPTIMISTIC-ONLY / UNSAFE / FLAGGED'.

**Part II.** §66.0: 'OVERRIDES Part I: the verdict alphabet {ROBUST, OPTIMISTIC-ONLY, UNSAFE} is extended with INDETERMINATE (66.2.1)... because a false UNSAFE inflates the blindness premium.' §66.2.1 makes INDETERMINATE the fail-closed sink; §66.4 A10.

**Impact.** Explicitly flagged. The `verdict_t` enum needs a migration, the verdict palette needs a fourth entry, and any exhaustive match/switch over three values becomes non-total. Part I has no exit code, colour token or chip glyph for INDETERMINATE (see unresolved).

#### Bare verdict headers forbidden; scope clause mandatory on every rendering

**Part I.** 07-replay.md §25.11 specifies the UI result header verbatim as 'Minimum cut {session_binding>=device, egress_seg>=1} — ROBUST — 6 corridors — blake3:3f9a…'; §25.8 checker prints `VERDICT ROBUST 11ms`; 11-api.md §37.4 CLI transcript prints `verdict ROBUST flags: none`; 12-frontend.md §41.3 header chip `[ROBUST] [flags:0]` and §41.11 'VERDICT: ROBUST'.

**Part II.** §66.0: 'OVERRIDES Part I / ECLIPSE §8: the demo header string "Minimum cut {...} — ROBUST" is forbidden. Every rendering of a verdict anywhere carries its scope clause (66.5).' §66.5.1 makes the bare tokens illegal in CLI output, UI text nodes, docs, demo script and exports; §66.5.2 fixes the grammar `safety "(" scope-body ")" [minimality-clause]`; §66.5.3 forbids building the string by concatenation or interpolation.

**Impact.** Explicitly flagged, but the override names only the ECLIPSE §8 demo header. Every other Part I transcript and UI header listed above is also now illegal and each must be rewritten to the 66.5.2 grammar, including the `[ROBUST] [flags:0]` chip pair in the investigation header, which is the form §66.10's `banned_substrings` targets.

## 67 Kernel threat model

### UNRESOLVED

#### The `greedy_cover` flag is left without a home in the new verdict algebra

**Tension.** Part I §7.5 Def 19 and §44.9 treat `greedy_cover` exactly like `grounding_capped` and `subset_minimal_only`: any of the three bars ROBUST, and §44.9 asserts it as a build-failing gate. Part II re-homes the other two explicitly - `grounding_capped` becomes `Safety::Incomplete` (67.7), `subset_minimal_only` becomes a `Minimality` value that no longer suppresses safety (67.11) - but `greedy_cover` appears nowhere in the 67.11 `SoundnessFlags` bitflags, nowhere in `enum Minimality`, and nowhere in 67.14. Since 67.11's rule is "Any flag set => Safety::Robust is unconstructible" over its own enumerated set, an omitted flag silently stops barring ROBUST.

**Decision needed.** Does a run whose cut came from the greedy `ln n + 1` cover (beyond exact search to size 3) still bar ROBUST, or does it become `Minimality::Unverified` with `Safety::Robust` permitted - and if the latter, is `Minimality::Unverified` reported anywhere a reader will see it?

**Recommended.** Treat `greedy_cover` as a minimality statement, not a safety one, for consistency with 67.11's stated rationale: map it to `Minimality::Unverified`, allow `Safety::Robust`, and require the Go checker to reject a certificate claiming `Minimality::Exact` without the exact-search witness. Then amend §44.9 and §8.8 section 5 in the same change so the old assertion does not linger as a false gate.

#### Obligation-forced silent instances become unconstructible under anchor coverage

**Tension.** Part I §7.6 Def 17 admits two ways a silent instance can be evidence-consistent: "every silent instance in `h` carries a License `(s, I, basis, witness)` ... **or is forced by an unsatisfied obligation axiom**." An obligation-forced instance therefore cites no `EventId` and no `LicenseId`. Part II 67.3 item 2 requires that "Every fact in `invariant_U` and every node of every witness tree is `OBSERVED` (cites >=1 real `EventId`), `LICENSED` (cites a `LicenseId`), or `UNANCHORED`. `UNANCHORED` must be unconstructible; if the grounder ever produces one, abort with exit 4." There is no third anchor category for obligation-forced instances, and Part II does not mention Def 17.

**Decision needed.** Do obligation-forced silent instances get a synthetic `LicenseId` (and if so, what are its `(source, interval, basis, witness)` fields, given no source is blind), or is Def 17's second disjunct deleted so obligations only ever set the `obligation_orphan` flag rather than manufacture instances?

**Recommended.** Mint an explicit license basis - e.g. `basis = OBLIGATION` with the obliging `EventId` as witness - so anchor coverage stays total and the certificate can name why the instance exists. Deleting the disjunct instead would remove the only mechanism 67.3 itself credits with manufacturing a silent instance when a source looks LIVE.

#### Red-team attacker capabilities exceed Part I's hard, generator-enforced attacker limits

**Tension.** Part I §6.3 states as hard, enforced limitations that the attacker cannot "Break cryptographic primitives. BLAKE3 chain forgery is out of scope; a break of the chain is always detectable" (L1), cannot compromise the collector's signing state (L4), and cannot "Suppress telemetry ... retroactively for records already chained and flushed" (L5), and requires "Encode L5 and L6 as numeric budgets in the profile and assert them in the generator with a panic on violation, not a warning." Part II 67.1 grants `C2_local_deleter` the ability to "delete/edit records on a host it compromised, after compromise time" and `C3_local_chain_holder` the ability to "re-chain that host's log with the host-local chain key" - which is exactly retroactive suppression of already-chained records, and produces an undetectable chain (contradicting L1's "always detectable"), even though no primitive is broken. Fixtures `A3_rechained_delete` and `A1_obligation_evading_delete` depend on it.

**Decision needed.** Is `threat/model.toml` amended to declare post-compromise local deletion and local re-chaining as in-scope capabilities (which requires relaxing L1's detectability claim and L5's retroactivity ban and re-deriving `max_suppressed_sources`), or do the red-team fixtures run under a separate profile that the generator's panic-on-violation assertion exempts?

**Recommended.** Amend `threat/model.toml` with an explicit `C12_local_rechain` bound to the `CHAINED_LOCAL`/`UNCHAINED` source classes of 67.5, restate L1 as "the attacker cannot forge a sealer digest" (which is what 67.1 actually assumes) and restate L5 as applying only to `CHAINED_SEALED` sources. A second profile would fork the threat model and leave §6.5's scope table describing a system that no longer exists.

#### The required adaptivity probe conflicts with the non-adaptive attacker limitation

**Tension.** Part I §6.3 L2 states the attacker "CANNOT ... Observe SPECTRA, the control configuration under test, the rule table, or any certificate. The attacker is non-adaptive; it does not re-plan against defences. **Every replay uses the same attacker plan.**" §6.5 lists "Adaptive attackers that observe defences and re-plan (L2)" as out of scope, and the §6 preamble fails the build when a scenario references an undeclared capability. Part II 67.10 nonetheless requires, "for the demo fixture and for every held-out scenario family", an adaptivity probe that reruns the generator "with the cut `S` enforced *and* the scenario script permitted to take its declared alternate branch", setting `adaptive_bypass_known: true` if the branch reaches a goal atom.

**Decision needed.** Is branch selection conditioned on the deployed cut a new declared generator capability (making a bounded form of adaptivity in scope, and requiring §6.5's out-of-scope row and §8.3 item 3 to be rewritten), or is the alternate branch pre-declared and cut-independent, so that 'every replay uses the same attacker plan' still literally holds?

**Recommended.** Keep the probe but define the alternate branch as pre-declared in the scenario script and selected without reading `S` - the probe then measures whether a fixed alternate plan survives the cut, which is enough to justify `adaptive_bypass_known` without granting the attacker observation. Say so explicitly in 67.10, because as written "with the cut `S` enforced" reads as the generator being told what was deployed.

#### Named Part I gates still require the license-voiding behavior Part II deleted

**Tension.** 67.4's override removes license voiding from the kernel but never names the downstream artifacts that assert it. §45.2 `test_timestamp_backdating.py` is a required adversarial-suite test whose required defensive assertion is "the Bellman-Ford difference-constraint pass detects the negative cycle and voids the license; assert the voided license id appears in `liveness.json.voided[]` with its witness." §47.5 failure-mode row 2 requires "void affected licenses, log `liveness.license_voided` with witness event ids". §47.2 requires span attribute `voided_licenses`, §47.3 requires counter `spectra_licenses_voided_total`, and §47.6 rule 6 lists "a voided license" among the degradations that must appear in the API response, certificate and UI header. Under Part II, `licenses_voided` must be 0 and any nonzero value is rejected with `E_TIME_VOID`.

**Decision needed.** Are `test_timestamp_backdating.py`, failure-mode row 2, the `voided_licenses` span attribute and the `spectra_licenses_voided_total` counter rewritten around the new `time_inconsistent` / BLIND-restriction behavior, or deleted? 67.4 keeps the certificate field "precisely so the removed behavior stays refuted rather than forgotten" - does the same reasoning apply to the metric and the test?

**Recommended.** Rewrite rather than delete, mirroring 67.4's own logic: keep `test_timestamp_backdating.py` but assert `licenses_voided == 0`, `TIME_INCONSISTENT` set, the disputed span BLIND and `|licenses| >= |licenses(benign twin)|`; keep the counter as a permanently-zero refutation witness with a `REASON:` comment; rewrite row 2 to say the pass removes LIVE and never removes a license.

#### Deterministic step budgets versus resource-threshold aborts

**Tension.** Part II 67.7 requires that "All budgets are deterministic step/instruction counts, never wall-clock. A wall-clock bound in any decision path is a build failure (lint `no-clock-in-decision-path`). Two machines must agree on whether a cap tripped." Part I specifies machine-dependent bounds as required behavior on the same code path: §47.5 row 12 requires the run to "abort ... cooperatively with `E-RESOURCE-MEMORY`" when RSS crosses a soft limit, and §45.2 `test_graph_explosion_dos` states the required defensive behavior as "run terminates with `grounding_capped=true`, verdict is never ROBUST, **wall time < 30 s, RSS < 2 GiB**". An RSS-triggered abort decides whether a run produces a verdict, and it will not agree across machines.

**Decision needed.** Is the RSS soft-limit abort of §47.5 row 12 inside the decision path (in which case it must be replaced by a deterministic allocation-count or arena-size budget), or is it an outer safety net whose trip is reported as a distinct non-verdict error that the determinism gate exempts? And are §45.2's wall-time and RSS figures demoted from required behavior to non-gating observations?

**Recommended.** Make the deterministic step/arena budget the only thing that can produce `Safety::Incomplete`, and classify an RSS or wall-clock abort as an infrastructure error (`E-RESOURCE-MEMORY`, no certificate at all) that is explicitly outside the two-machines-agree property. Then restate §45.2's wall-time and RSS numbers as published measurements rather than assertions, consistent with 67.8's "measured, never asserted" posture.

#### Post-hoc narrowing of a pre-registered primary hypothesis

**Tension.** Part I §5.4 requires that "Every hypothesis must carry an explicit, **pre-registered** falsifier", §5.5 makes `research/questions.toml` the single source of truth with a `prereg_date` and forbids hand edits to status, and §8.2 IV6 guards against selective reporting by keeping falsified hypotheses and having "CI diffs the registry history". Part II 67.3 narrows H0's falsifier after the fact - "the zero-false-ROBUST invariant is scoped to declared suppression classes" - and 67.14 bans the unscoped claim. Narrowing a pre-registered primary hypothesis so that a known-undetectable class can no longer falsify it is the exact move the pre-registration discipline exists to prevent, and Part II offers no amendment procedure.

**Decision needed.** Is H0 amended in place (new statement, new falsifier, new `prereg_date`), or superseded by a new H0' with H0 retained at its original scope and marked FALSIFIED or AMENDED with the evasion class as its evidence? And does the registry gain an amendment record that CI's history diff recognizes as legitimate rather than as tampering?

**Recommended.** Supersede rather than edit: keep H0 verbatim with an `amended_by = "H0b"` field and a dated rationale citing the A1 evasion class and `artifacts/evasion.json`, and add H0b carrying the scoped statement with its own `prereg_date`. That preserves §8.2 IV6's audit trail and makes the narrowing itself a published result, which is the strongest version of what 67.3 is trying to achieve.

### SILENT

#### Liveness thresholds may no longer be computed from the run's own data

**Part I.** §7.4 Def 11 makes self-calibration part of the definition of liveness: `live(s, I)` requires "(max inter-arrival over I <= q99(s) **computed from this run**)". §8.1 CV3 acknowledges the circularity ("the tampered run defines its own normal") and mitigates it only with "Sensitivity sweep over q95/q99/q999 published as a table", leaving "Threshold choice remains a modelling decision". §6.6 T2 detects DELAY "Via inter-arrival > q99(s)". §44.8 `test_irrelevant_event_removal` even asserts that any liveness change "is confined to that source's q99".

**Part II.** 67.3 item 3: "Liveness no longer self-calibrates. Per source `s`, the admissible record count and inter-arrival distribution for a window come from `baseline.json`, produced by a declared clean calibration run of the *same generator config*, hashed into the certificate as an input." Plus the negative requirement "never compute any liveness threshold from the bundle under analysis", restated as 67.14 #2 as a build failure, and a new `BASELINE_MISSING` flag. None of this carries an OVERRIDES marker.

**Impact.** This is the single largest silent change in the section. An implementer reading Part I builds q99-from-this-run into Def 11, ships CV3's sensitivity sweep as the mitigation, and writes the `test_irrelevant_event_removal` assertion around q99 - and then trips 67.14 #2, which is a build failure. It also silently adds a new required kernel input (`baseline.json`) and a new calibration run to the fixture pipeline that Part I's §43.4 fixture builder does not produce.

#### Generator ground truth is pulled into the kernel and checker path

**Part I.** §6.6 rule 1: "The tamper log is ground truth and is NEVER given to the reconstruction path. Enforce this with a module boundary and a test that fails if the reconstruction crate can even import the tamper crate." §7.2: `transition.ground_truth` is "generator-side only; never read by reconstruction", enforced "with a database role and a code-level lint that the reconstruction path never selects that column. A test must fail if it does." §8.2 IV2 makes it a compile-time-enforced ban. §7.4 Def 10: "Reconstruction sees only `B` and the declared catalogs."

**Part II.** 67.5 post-compromise blackout: "If the scenario's ground truth (§62) places a host in the compromised set at time `t`, every `CHAINED_LOCAL` and `UNCHAINED` source resident on that host is BLIND for all `t' >= t`." 67.9: `goal_provenance = DERIVED` means "the goal set is computed from the generator's ground truth via the correspondence relation of §62", and DERIVED is "Required for every headline number and for the demo fixture." 67.1's diagram simultaneously claims the ground-truth stream "is never an input to the kernel".

**Impact.** Directly contradictory, and Part II contradicts itself on the same page. Liveness is a kernel stage and the goal is a kernel input (§7.6 pipeline), so both requirements route ground truth across the boundary that §8.2 IV2 makes a compile error and §7.2 makes a test failure. It also breaks §6.4 TB4, under which the Go checker "re-derives liveness from the hashed bundle" - it would now need the compromised-host set too. An implementer will either fail the IV2 test or silently disable it, which destroys the internal-validity defense the whole research frame rests on.

#### Two incompatible attacker-capability taxonomies both numbered C1..C6

**Part I.** §6.2: "Declare capabilities as an explicit closed set. The generator may only emit steps whose required capabilities are listed", with `threat/model.toml` defining C1_credential_theft, C2_session_replay, C3_token_forgery_weak, C4_privilege_request, C5_lateral_auth, C6_service_account_abuse, ... C11_time_manipulation. The §6 preamble requires the build to "fail ... when a scenario or rule references a capability the model does not declare."

**Part II.** 67.1 defines a different closed set - C0_observer, C1_emitter, C2_local_deleter, C3_local_chain_holder, C4_namer, C5_flooder, C6_catalog_author - "declared per fixture in `attack.toml`", and 67.12's fixture manifest uses it: `capability = ["C2_local_deleter", "C3_local_chain_holder"]`. Part II never mentions `threat/model.toml` or the C1..C11 set.

**Impact.** Every red-team fixture references capabilities `threat/model.toml` does not declare, so Part I's capability linter fails the build on the entire Part II corpus. Worse, the identifiers collide: `C5` means lateral authentication in one file and unbounded flooding in the other, and `C6` means service-account abuse in one and catalog authorship in the other. Any cross-file reading of "C5" is ambiguous. The two taxonomies must be namespaced or unified.

#### UNCHAINED and unsealed sources contradict the mandatory collection-plane schema

**Part I.** §6.4 TB1 boundary obligation: "Every record gets `(source_id, seq, prev_hash, hash)`." §7.2's `event` table declares `prev_hash CHAR(64) NOT NULL`, `self_hash CHAR(64) NOT NULL` and `UNIQUE (run_id, source_id, seq)`. §6.4 TB2: "Manifest hash verified before any parsing. Refuse to run on an unverified bundle." L4: "Tampering happens upstream of the sealed bundle, never after sealing."

**Part II.** 67.5 introduces source class `UNCHAINED` ("models the common real-world case", `sealer = false`, `bracketing = false`) and requires "At least one scenario family in the held-out set must consist entirely of `UNCHAINED` sources." It also defines an `unsealed` flag for "a bundle with no sealer digests" and a separate `spectra-sealer` container holding per-source keys.

**Impact.** An UNCHAINED source cannot populate `prev_hash`/`self_hash`, which are NOT NULL, and has no `seq` for the uniqueness constraint - the required held-out family is unrepresentable in Part I's schema. Part I also assumes one collector-level seal for the whole bundle (TB2 refuses to run without it), while Part II makes sealing per-source and optional. The schema, TB1 and TB2 all need rewriting and Part II never says so.

#### Catalog contributors are modeled as attackers although Part I puts that out of scope

**Part I.** §6.3 L3: "The attacker CANNOT ... Modify the control configuration. Controls are defender-side state." §6.5 out-of-scope column: "Supply-chain compromise of packages or build systems (that is WARDEN's domain; do not model it here)", and the section requires the rule linter to "reject any rule whose provenance note names an out-of-scope technique."

**Part II.** 67.1 declares capability class `C6_catalog_author` - "contribute rules, blocker bits, controls, goals (supply-chain-of-the-model)" - and states "`C6` is included deliberately: a control catalog is a contribution surface, and 67.7/67.8 are the only defenses SPECTRA has against a contributor who authors a flattering model." 67.8 builds five build-failing gates and a contributor rule around it.

**Impact.** Part II makes a class of attack that Part I's `threat/SCOPE.md` declares out of scope into a first-class, gated threat, without amending the scope table. An implementer maintaining §6.5's linter will reject the provenance notes on 67.8's own fixtures (A6_universal_atom, A6_inert_atom, A6_unenforced_blocker), and `threat/SCOPE.md` will publish a scope statement the code no longer honors.

#### Verdict strings must carry scope hashes, breaking the asserted demo/e2e header shape

**Part I.** §46.6 pins the demo-path output as a required CI check, including the literal header shape "verdict: ROBUST cut: {session_binding>=bound, egress_seg>=1} corridors: 6" and "flags: none", and `e2e.yml` "drives the same path through the UI with Playwright and asserts the header string shape".

**Part II.** 67.10: "**Verdict strings are unconstructible without scope.** Render as `ROBUST(rules@<hash>, catalog@<hash>, licenses@<hash>, goals@<hash>, non-adaptive)`. No code path formats a verdict by string concatenation; there is one constructor and one formatter ... The Go checker rejects a certificate whose mode string lacks its scope binding (`E_UNSCOPED_VERDICT`)." No OVERRIDES marker.

**Impact.** The Part I e2e assertion and the §46.6 demo transcript encode the bare form. Under Part II that certificate is rejected by the checker with `E_UNSCOPED_VERDICT`, so the required demo-path check and the Playwright header assertion both fail. Also `flags: none` is no longer expressible the same way given 67.11's flag set.

#### The no-score lint forbids the `severity` field the findings log requires

**Part I.** §45.3 mandates front matter for every security finding containing `severity: high # informational | low | medium | high | critical`, and rule 5 explicitly permits it: "No finding may be recorded with an invented severity score, CVSS vector or exploitability percentage. **Severity is the declared ordinal only.**"

**Part II.** 67.11: "`make no-score-lint`: no field, column, API key or UI string anywhere in the repo may be named or typed as a probability, confidence, score, severity, risk or likelihood. Schema-level lint." 67.14 #12 repeats it: "Any numeric confidence, probability, severity, risk or score, anywhere, in any layer."

**Impact.** `docs/security/findings/*.md` and `docs/security/findings/index.json` carry a field literally named `severity`, which the new repo-wide schema lint rejects. Either the findings schema loses its ordinal (and §45.3's own rule 5 becomes vacuous) or the lint needs a carve-out; Part II grants none. §47.5 row 2's "reduce confidence by degrading mode" wording trips the same lint.

#### Closed, lint-enforced metric and label sets do not admit the new verdict or flags

**Part I.** §47.3 fixes the metric set and states `tests/observability/test_metric_names.py` "asserts the full set exists with the documented labels **and no others**", including `spectra_proofs_total{mode,verdict} verdict=robust|optimistic_only|unsafe`, `spectra_proof_flags_total{flag} flag=grounding_capped|subset_minimal_only|greedy_cover`, and `spectra_licenses_voided_total{source_id,reason}`. §47.2 requires span attribute `voided_licenses` on `spectra.liveness.compute`. §47.1 rule 1 makes log `event` names a closed registry.

**Part II.** 67.7 adds a fourth safety value `Incomplete`; 67.11 defines eleven `SoundnessFlags` (OBLIGATION_ORPHAN, TIME_INCONSISTENT, CHAIN_DIVERGENCE, UNSEALED, ER_AMBIGUOUS, ER_POISONING_SUSPECTED, CATALOG_DOMINANT, ADHOC_GOAL, BASELINE_MISSING, QUARANTINE_NONEMPTY, GROUNDING_CAPPED) and drops SUBSET_MINIMAL_ONLY and GREEDY_COVER; 67.4 makes voided licenses permanently zero. Part II never mentions the observability surface.

**Impact.** The observability contract is enumerated and lint-enforced as closed, so it cannot represent an INCOMPLETE run or any of the eight new soundness flags, while retaining a counter and a span attribute for a behavior 67.4 deletes. An implementer following Part I will ship a metrics test that fails the moment the new flags are emitted.

#### Relabeling-invariance metamorphic test conflicts with identifier-sensitive ER

**Part I.** §44.8 `test_relabeling_invariance`: "Consistently rename all entity identifiers under a bijection" must leave the "certificate identical after applying the inverse bijection; hashes differ only through the bundle hash", with the stated rationale "reconstruction must not key on identifier spelling". It runs "over all fixture scenarios and over the full degradation matrix rows".

**Part II.** 67.6 makes reconstruction deliberately sensitive to identifier spelling: "Normalization is total and byte-level ... NFKC then case-fold then namespace-specific canonicalization", and "Two distinct raw identifiers from different sources that normalize to the same key do not merge: they emit an `er_collision` quarantine record with a reason code, and the window is `er_ambiguous`" - which bars ROBUST. Merge strength also depends on `attacker_writable` namespace declarations in `er.toml`.

**Impact.** An arbitrary bijection over identifiers can map two non-colliding names onto a homoglyph/NFKC collision, setting `er_ambiguous`, barring ROBUST and changing the certificate - so the Part I metamorphic test fails on a correct Part II implementation. The test needs restricting to bijections that preserve normalization classes and namespace writability, and Part II does not say so.

#### Red-team fixtures are checked in as bundles, against the generated-fixtures rule

**Part I.** §43.4: "Fixtures are generated, never hand-edited. `spectra fixtures build --seed 0xSPECTRA` writes `tests/fixtures/scenarios/<name>/{bundle.jsonl,ground_truth.json,manifest.sha256}`. A fixture whose manifest hash does not match is a hard test failure ... Committing a fixture without its `manifest.sha256` fails `tools/lint/fixture_guard.py`." §46.8: "Do NOT cache the fixture bundles; they are generated from seeds in-job so the generator stays exercised."

**Part II.** 67.12: "Checked in under `fixtures/redteam/`", with each directory holding a hand-specified `attack.toml`, an adversarial `bundle.jsonl`, a `baseline.json`, an `expected.json` and a `benign_twin/`. No `manifest.sha256` appears in the layout, and the directory root differs from `tests/fixtures/scenarios/`.

**Impact.** `tools/lint/fixture_guard.py` fails on every red-team fixture for the missing manifest, and the committed adversarial bundles violate the generated-in-job rule. It is also left undefined whether the adversarial bundle is reproducible: `attack.toml` declares a `transform`, which suggests derivation from the benign twin in-job, but the layout commits `bundle.jsonl` directly. Pick one and state the hash discipline.

#### Two conflicting mandates for what LIMITATIONS.md opens with

**Part I.** §8.8 fixes the file's skeleton, beginning "## 0. One-paragraph summary / What SPECTRA does not do, in plain language, before anything else", with section 10 generated by `spectra research render-limitations` and a CI gate that fails if the file is absent, under 150 lines, contains a TODO, or is stale relative to `crates/eclipse/**` or `rules.toml`.

**Part II.** 67.10: "`LIMITATIONS.md` opens with (3) and (4), verbatim, above the fold" (the lower-bound and non-adaptive facts). 67.3 adds a second generated region - "Every tau with `d_evade(tau) < infinity` is written into `LIMITATIONS.md` by the docs build. The build fails if `LIMITATIONS.md` is stale relative to `evasion.json`" - and 67.12 requires "every fixture is referenced by id in `LIMITATIONS.md`".

**Impact.** Two specs claim the first position in the same file and two independent staleness gates now guard it (git-history-based in Part I, `evasion.json`-based in Part II), with no stated ordering. An implementer will satisfy one gate and break the other.

#### Part II's own prescribed wording uses a word Part I bans outright

**Part I.** §8.9: "Do NOT describe SPECTRA as detecting, preventing, or stopping anything." §8.6 lists among forbidden outputs, enforced by a linter over UI strings, API schemas and report templates: "the words 'guaranteed', 'proven secure', 'blocks all attacks', 'detects'."

**Part II.** 67.14's prescribed replacement claim is: "It **detects** declared tampering classes on declared source classes, and publishes the classes it cannot detect." 67.2's attack table has a column headed "detection", and 67.5 requires that "Any document reporting suppression-detection results must split them by source class". 67.10's own banned-vocabulary list does not include "detects".

**Impact.** The two claim linters have incompatible word lists over overlapping surfaces. Part II's mandated sentence fails Part I's §8.6/§8.9 lint. Related: Part I's §8.6 certificate footnote, required verbatim in every render, contains "the attacker would have been stopped", which is one token away from 67.10's banned "would have stopped" - decide whether the Part I footnote is exempt before implementing a substring lint.

### RESOLVED

#### License voiding on backdated timestamps is deleted

**Part I.** §6.6 op T7 (BACKDATE): "license VOIDED; the window may not license silent steps", and requirement 4: "T7 must void, never merely weaken, any license whose interval depends on the backdated record." §7.4 Def 11: "A Bellman-Ford pass over the difference-constraint graph of happens-before edges voids any license resting on a provably backdated timestamp (T7)."

**Part II.** 67.4, marked "OVERRIDES Part I: license voiding is **deleted**. The timestamp-consistency pass is redefined as a restriction operator on liveness that can only ever remove LIVE, never remove BLIND." Certificate field `adversarial.time_pass.licenses_voided` must be 0; the Go checker rejects nonzero with `E_TIME_VOID`. Infeasible constraint systems mark participating sources BLIND and set `time_inconsistent` instead.

**Impact.** Correctly flagged. Rationale is that voiding lets an attacker who writes timestamps shrink P_max and manufacture a stronger verdict. An implementer must delete the void path in stage A, not merely gate it. Note the downstream Part I artifacts that still encode voiding are NOT mentioned by Part II - see the unresolved entry on `test_timestamp_backdating.py` / failure-mode row 2 / `spectra_licenses_voided_total`.

#### Capped grounding: downgrade replaced by no verdict at all

**Part I.** §7.5 Def 19: a run carrying `grounding_capped` "may never be presented as ROBUST - downgrade to OPTIMISTIC-ONLY and display the flag." §47.5 row 11: "stop grounding at the cap, set grounding_capped=true, force mode away from ROBUST, log `ground.capped` with the measured sizes, return the partial graph with an explicit banner." §45.2 `test_graph_explosion_dos`: "run terminates with `grounding_capped=true`, verdict is never ROBUST".

**Part II.** 67.7, marked "OVERRIDES Part I: a capped run does not produce a downgraded verdict. It produces no verdict." `Safety::Incomplete` carries a `CapKind` reason and "no cut, no Psi, no redundancy index, no frontier"; the Go checker rejects a certificate with both `Incomplete` and a non-empty `cut` (`E_INCOMPLETE_CUT`); CLI exit 3. 67.14 #6 forbids emitting a cut/Psi/frontier alongside `Incomplete`.

**Impact.** Correctly flagged for the verdict itself, but §47.5 row 11's "return the partial graph with an explicit banner" is a direct casualty that Part II never names. An implementer following Part I's failure-mode table will still ship the partial graph and cut that 67.14 #6 makes a build failure.

#### Verdict algebra: fourth safety value and independent minimality field

**Part I.** §7.5 Def 19 defines UNSAFE / OPTIMISTIC-ONLY / ROBUST and states "Only three verdicts exist." It also makes `subset_minimal_only` a ROBUST-barring flag; §44.9 asserts as a build gate that "every run carrying `grounding_capped`, `subset_minimal_only` or `greedy_cover` in `flags` reports a mode other than ROBUST."

**Part II.** 67.7: "OVERRIDES Part I §5: `mode: ROBUST|OPTIMISTIC|UNSAFE` is replaced" by `enum Safety { Robust, OptimisticOnly, Unsafe, Incomplete }` plus a separate `enum Minimality { Exact, Subset, Unverified }`. 67.11: "OVERRIDES Part I: safety and minimality are **independent** fields. `subset_minimal_only` ... no longer suppresses a safety result. A fully verified unreachability result with `Minimality::Subset` is still `Safety::Robust`."

**Impact.** Correctly flagged. The concrete consequence Part II does not spell out: §44.9's second assertion is now a false gate for `subset_minimal_only` and must be rewritten, and §7.3 Def 6's "Above 64 atoms the kernel downgrades to subset-minimal and sets the flag" no longer implies a safety downgrade.

#### Zero-false-ROBUST is narrowed from corpus-wide to declared suppression classes

**Part I.** §5.3 H0 (PRIMARY): "For every fixture in the corpus, at every completeness level ... zero false ROBUST verdicts, corpus-wide", with falsifier "A single instance falsifies H0. No tolerance, no averaging." §44.9 implements it over "the entire 100%->30% completeness matrix for every scenario and every tampering mode". §5.2 RQ5 states the required outcome for adversarial suppression is "larger-and-sound" and "Any silent failure is a defect, not a finding."

**Part II.** 67.3: "OVERRIDES Part I: the zero-false-ROBUST invariant is scoped to declared suppression classes, and the undetectable class is given a name, a measurement and a fail-closed consequence instead of a footnote." 67.14 forbids the bare claim "Zero false ROBUST", permitting only "zero false ROBUST on suppression classes S1..Sn, enumerated in `LIMITATIONS.md`, at the measured frequencies published in the degradation-matrix artifact."

**Impact.** Correctly flagged, and it resolves a contradiction internal to Part I (§6.6 rule 5 already concedes that suppression leaving no chain gap, no obligation violation and no blind window is "permanently invisible"). The implementer must rewrite H0's statement and falsifier in `research/questions.toml`; Part II does not say so, and §5.5 makes that file the single source of truth.

#### Chain continuity is no longer a liveness criterion

**Part I.** §7.4 Def 11: `live(s, I)` requires "(no seq gap in the BLAKE3 chain of s over I)"; a chain break localizes deletion and yields SUPPRESSED. §6.6 T1: "gap -> SUPPRESSED (chain break) or BLIND". §6.7 A1 assumes per-source sequence numbering and hash chaining exist.

**Part II.** 67.5: "OVERRIDES Part I: chain continuity is demoted from a liveness criterion to one evidence input whose weight depends on a declared source class. Chain continuity alone can never establish LIVE." A new hashed `sources.toml` declares `CHAINED_SEALED` / `CHAINED_LOCAL` / `UNCHAINED`; for the latter two, chain-gap absence "contributes nothing" and cross-source corroboration plus the volume envelope are required. 67.14 #4 makes chain continuity as a sufficient LIVE condition a build failure.

**Impact.** Correctly flagged. Rationale: a C3 attacker holding the host-local chain key re-chains after deletion, so no gap exists. The implementer must rewrite Def 11's conjunction as a per-class admissibility table.

#### Ambiguous entity merges are bracketed, not resolved

**Part I.** §6.7 A3 assumes "Entity resolution is correct enough that a single real principal is not split across two `EntityId`s within a scenario" and directs measuring resolution error, not bracketing it. §47.5 row 6 handles only the unresolvable-singleton case: "create an explicit `unknown-principal:<hash>` node, never merge on weak similarity". §7.6 Def 17/18 define the P_min/P_max sandwich over a single, fixed ER output.

**Part II.** 67.6 item 3, marked "OVERRIDES Part I: a `WEAK` merge is not resolved. It is materialized as two grounding candidates": `P_min` grounds over `ER_meet` (STRONG merges only) and `P_max` over `ER_join` (STRONG union WEAK). `er_ambiguous` bars ROBUST; `er_poisoning_suspected` is set when an attacker-writable-only merge is load-bearing for the cut.

**Impact.** Correctly flagged. The implementer must note that the Part I sandwich (I4 / Theorem 1) is now stated over two different entity graphs, so the property test `Reach(P_min) subset-of Reach(P_max)` needs an explicit meet-to-join entity mapping that neither part specifies.

#### Hand-authored goal atoms are removed from goal.toml

**Part I.** §7.5 Def 13: "`goal` is a ground, time-indexed atom over `(entity, dimension, value)` declared in `goal.toml`, e.g. `resource.read(res_17) @ <= t_k`." §7.6's pipeline diagram takes `goal.toml` as a kernel input alongside rules/controls/bundle.

**Part II.** 67.9: "OVERRIDES Part I: `goal.toml` no longer carries a hand-written objective atom per run." Goals come from a frozen hash-pinned `goals/library.toml`; `goal_provenance in {DERIVED, LIBRARY, AD_HOC}` is a mandatory certificate field; `AD_HOC` is "Never ROBUST-eligible" (checker code `E_ADHOC_GOAL`); multi-atom and disjunctive goals are allowed with per-goal verdicts only and no aggregate verdict.

**Impact.** Correctly flagged. Def 13's single-ground-atom typing must become a goal set, and the "no aggregate verdict" rule interacts with §46.6's demo header, which prints one verdict for the run.

## 68 Certificate and checker

### UNRESOLVED

#### Does the checker re-ground, and what does `grounding_mode: reground` oblige?

**Tension.** Part I §25.8 states flatly that the Go checker "Re-grounds from the hashed inputs" and §37.4 shows `regrounded 2,104 instances in 6ms`; the whole point of the independent checker in §25.2 is a second grounder. Part II's obligation list (§68.6, "Run in exactly this order") contains no grounding step: the certificate publishes `instances` and `instances_hash` which bind `grounding_mode = replayed`, and O8 only checks closure over the instances the certificate itself supplies. Yet §68.2.3 keeps `reground` as a legal enum value for `grounding_mode` with no obligations defined for it anywhere in §68.

**Decision needed.** Is the v1.0 checker a replay checker over a published instance set, or a re-grounding checker as Part I requires? If both modes survive, what obligations does `grounding_mode = reground` add (and what happens to the O(F) linear-pass argument, which assumes no grounding)? Under `replayed`, what stops a hostile emitter from omitting instances that would derive the goal — O8 only checks closure over the instances that are present.

**Recommended.** Make `replayed` the only legal value at MAJOR 1 and delete `reground` from the enum (adding it back is a MAJOR bump per §68.5), and explicitly withdraw Part I §25.8's re-grounding sentence. Then add an obligation that the published instance set is complete with respect to `rules_hash` + `bundle_hash` — otherwise replay-mode ACCEPT is a statement about the emitter's chosen instances only, and §68.12's 'independently verified' caveat list must say so.

#### The API/DB content key omits the inputs Part II added to the certificate scope

**Tension.** Part I §35.6 #6 defines the deterministic content key as `blake3(rules_hash || bundle_hash || controls_hash || goal_hash || seed || k)`, and §38.2 enforces it as `CREATE UNIQUE INDEX proof_content_key_idx ON proof_cert (rules_hash, bundle_hash, controls_hash, goal_hash, mode, horizon_k, seed)`. Part II §68.2.3 makes `er_hash`, `liveness_hash`, `guard_ast_hash` and `instances_hash` authoritative hashed inputs, and §68.2.2 binds `er` and `attacker` into the verdict scope — none of which appear in the content key. Part II never mentions §35.6 or the index.

**Decision needed.** Does the content key (and the uniqueness index) have to cover `er_hash`, `liveness_hash`, `guard_ast_hash` and the attacker model? As written, two proofs that differ only in ER configuration or liveness parameters collide on the content key, so §35.6 returns the first one with `"cached": true` — a certificate whose `scope` string names an ER hash the caller never used.

**Recommended.** Redefine the content key as `blake3(canonical_bytes(scope) || bundle_hash || goal_hash || seed || k)` so it is derived from the same block the verdict string is rendered from, and replace `proof_content_key_idx` with a unique index on `cert_hash` plus a non-unique index on the scope hashes. A test should assert that changing only the ER config produces a different content key.

#### Storing the certificate as `JSONB` destroys byte-exact canonicity

**Tension.** Part I §38.2 stores the certificate body as `document JSONB NOT NULL` in `proof_cert`, and §36.3 serves it from `GET /api/v1/eclipse/proofs/{cert_id}/certificate`. Part II's O0 requires that re-serializing the parsed body reproduce the input bytes exactly, and O1 recomputes `blake3` over those bytes. PostgreSQL `JSONB` does not preserve member order, duplicate keys, integer text formatting or whitespace — it is a normalizing parse, exactly what §68.0 rule 2 forbids the pipeline to do.

**Decision needed.** Where do the authoritative certificate bytes live? A certificate that round-trips through `JSONB` and is served by the API can fail O0 (`E-CANON-*`) or O1 (`E-HASH-CERT`) on the downloader's machine even though the emitter produced a valid file — and the §36.4/§35.6 test asserting 'byte-identical certificates' cannot hold through a JSONB column.

**Recommended.** Store the canonical bytes verbatim (`BYTEA`, or `TEXT` with a CHECK on the 26-byte magic), keep a derived `JSONB` copy only for querying, and have the certificate endpoint stream the stored bytes with `Content-Type: application/octet-stream` (or a `.spcert` media type) rather than re-serializing a parsed document. Add a CI test that pulls a certificate through the API and runs `spectra verify` on the downloaded bytes.

#### `proof_cert` flag columns cannot express Part II's flag algebra

**Tension.** Part I §38.2 hard-codes three boolean columns — `flag_capped`, `flag_subset_only`, `flag_greedy` — and the `robust_never_flagged` CHECK over exactly those three, described as "the schema-level enforcement of the ECLIPSE prohibition". Part II §68.2.6/§68.7 define six soundness-affecting flags (`grounding_capped`, `corridor_capped`, `greedy_cover`, `er_ambiguous`, `license_voided_by_backdating`, `tuned_scenario`) plus `budget_exhausted`, and drops `subset_minimal_only` in favor of the `minimality` field. Part II never mentions the table.

**Decision needed.** Which flags gate ROBUST at the database level, and how is the constraint kept in sync with the generated flag-algebra table from `cert-schema.toml`? As written, a certificate with `er_ambiguous: true` and `safety: ROBUST` is rejected by the checker but accepted by the database, so §38.2's claim that a flagged run 'can physically not be stored as ROBUST' becomes false.

**Recommended.** Replace the three columns with a `flags JSONB` (or one boolean per flag) plus a generated `flagged BOOLEAN` and rewrite the CHECK as `verdict <> 'ROBUST' OR NOT flagged`, generating both the DDL and the checker table from `cert-schema.toml` so §68.7 and the schema cannot drift. Drop `flag_subset_only` and add a `minimality` column.

#### Synchronous verification vs O4 re-hashing the whole bundle

**Tension.** Part I §35.5 explicitly puts "certificate *verification* of an already-computed proof (milliseconds)" in the list of work that must NOT be queued and must answer synchronously, §35.4 fails the build on any synchronous router whose p99 exceeds 50 ms, and §36.3 lets `POST /api/v1/eclipse/verify` take just `{cert_id}` with no input files at all. Part II O4 requires the checker to "recompute each hash in §68.2.3 over files given on argv", which includes `bundle_hash` over a bundle that §35.7 allows to be up to 2 GiB streamed.

**Decision needed.** Is verification still a synchronous sub-50 ms endpoint once O4 must blake3 the entire bundle (and the rules/controls/goal/ER/liveness files)? And can `POST /eclipse/verify` accept `{cert_id}` alone, when O4 needs every input file on argv — resolving them server-side from the database reintroduces exactly the DB coupling §68.0 rule 1 removes from the binary.

**Recommended.** Move `/eclipse/verify` behind the queue (or bound it: synchronous only when the resolved bundle is under a declared size, else `202` + job), and require the request to name input artifacts by id so the router materializes files to a temp dir and execs the checker with an explicit argv. Publish the measured hash-throughput in `reports/eclipse_bench.md` rather than asserting 'milliseconds' in prose.

#### 64 MiB certificate cap vs the published instance set and invariant U

**Tension.** Part II §68.1 sets a normative max certificate size of 64 MiB (corpus row 27 rejects 65 MiB with `E-LIMIT-SIZE`) while §68.2 requires the body to carry `instances` (the published instance set), `invariant` U, `psi`, `witnesses`, `licenses` and `silent`. Part I §25.6 B caps grounding at `MAX_INSTANCES = 2_000_000` and `MAX_FACTS = 500_000`, and §25.7 renders U as a list of `"blake3:fact:.."` strings. At those caps the body alone is far over 64 MiB (500k fact hashes at ~70 canonical bytes is ~35 MB before a single instance is listed).

**Decision needed.** Do the grounding caps come down, does the size cap go up, or does the certificate stop publishing the full instance set and U verbatim (e.g. a Merkle commitment plus on-demand fetch)? Part II never reconciles its own size limit with Part I's grounding caps, and each choice changes what O7/O8 can check offline.

**Recommended.** Keep the 64 MiB cap and derive the real grounding caps from it (state the per-instance and per-fact canonical byte budgets in §68.2), so a run that would exceed the certificate size sets `grounding_capped` rather than producing an unpublishable proof. If full instance publication is required at Part I's caps, the cap must rise and §68.1 should say what it is protecting against.

#### A second, independently written guard front end in Go

**Tension.** Part I §22.3 mandates "One grammar, one parser (`crates/spectra-guard`), two lowerings", and §25.2 lists `crates/spectra-guard` as the shared guard parser. Part II requires the CAE — which encodes `guard := u8(tag) guard_payload` — to be "computed **independently in Rust and in Go** from the same text" (§68.4.3), ships `fuzz_guard_differential` "drives Rust and Go guard evaluators over random control assignments" where "a divergence is a build-red independence failure" (§68.9), and warns that "A shared misreading of a guard by both front ends is invisible to the checker" (§68.12). Part II cites Part I §22 for `guard_ast_hash` but never says §22.3's one-parser rule is withdrawn.

**Decision needed.** Is a second guard parser and evaluator in Go in scope? Part I's one-parser rule and Part II's Rust↔Go guard differential gate cannot both hold. This is a large scope decision (a second implementation of the §22.3 grammar, DNF lowering and blockers-mask derivation) and it also determines whether `guard_ast_hash` documents something shared or something independently recomputed.

**Recommended.** Decide explicitly and record it in `docs/checker-scope.md`, since §68.12's forbidden claim about 'independently verified' depends on the answer. If Go gets its own front end, amend §22.3 to say 'one grammar, two independent parsers' and keep `fuzz_guard_differential`; if not, delete the Rust↔Go guard differential and the independent-CAE claim in §68.4.3, and state plainly that guard semantics are single-sourced and therefore outside what an ACCEPT establishes.

#### Horizon `k`: `u32` ticks vs a `SMALLINT` column constrained to 1..64

**Tension.** Part II §68.2.3 declares `k` as a `u32` ("horizon, in ticks"), and §68.3 C7 requires it to be in-range for its declared width. Part I §38.2 stores `horizon_k SMALLINT NOT NULL CHECK (horizon_k BETWEEN 1 AND 64)`, while §23.2 allows `horizon_ticks ≤ 10_000` per scenario and §25.7's certificate shows `"k": 12`. Part II never mentions the column or the 1..64 bound.

**Decision needed.** What is the legal range of `k`, and is it in ticks or in rule-derivation rounds? If ticks, a scenario with `horizon_ticks: 240` (Part I §23.2's own example) already produces a certificate that cannot be stored, and the checker's declared `u32` width lets in values two orders of magnitude beyond anything the pipeline supports.

**Recommended.** State the unit once and pick one bound: keep `k` in ticks, declare it `u32` in the certificate with a normative upper limit matching §23.2's `horizon_ticks ≤ 10_000`, and widen the column to `INTEGER CHECK (horizon_k BETWEEN 1 AND 10000)`. Add a corpus row for an out-of-range `k` so the limit is actually tested.

### SILENT

#### Checker exit codes are incompatible

**Part I.** §25.8: "Exit codes: `0` OK, `2` invariant violated, `3` license unlicensed, `4` witness invalid, `5` smaller cut exists, `6` input hash mismatch." §37.3 additionally fixes CLI-wide codes: `7` = verification failed (checker rejected a certificate), `8` = result is flagged, `4` = validation/hash mismatch, `2` = usage error.

**Part II.** §68.10: "Exit codes: `0` ACCEPT, `1` REJECT (reason code on stderr and in `--json`), `2` usage or I/O error." No override marker anywhere in §68.

**Impact.** Code 2 means "invariant violated" in Part I and "usage error" in Part II — the same number flips from a security rejection to an operator typo. Any CI script or API mapping written from §25.8 or §37.3 (e.g. treating 7 as verification failure, 5 as 'smaller cut exists') silently mis-classifies every rejection; a caller checking `exit != 0 && exit != 2` would treat a tampered certificate as a usage error and ignore it. §37.3's table also has no room for a checker that only ever emits 0/1/2.

#### `measured` timings inside the certificate body

**Part I.** §25.7 certificate includes `"measured": {"instances":2104,"facts":911,"corridors":6,"ground_ms":381,"solve_ms":44}`, and §25.12 #10 `golden_certificates` requires regenerated output to be byte-identical "including `measured` fields' presence (values allowed to vary only in `*_ms`, which are excluded from the hash)".

**Part II.** §68.0 rule 3 and §68.12 #3: no wall-clock timestamp, hostname, username, absolute path, pid "or duration inside `body`. Timings belong in the run manifest, which is not hashed into the certificate." The `Body` struct has no `measured` member, and §68.3 C12 makes unknown members a hard reject (`E-SCHEMA-UNKNOWN`). The budgets override text covers wall-clock *budgets*, not the `measured` durations, and §68.12 #3 cites no Part I text.

**Impact.** Every certificate emitted per Part I §25.7 is rejected with `E-SCHEMA-UNKNOWN` at O2. Also, Part I's design of excluding `*_ms` from the hash is impossible under §68.1, where `cert_hash` covers the whole canonical `body` with no exclusions — an implementer who keeps `measured` and carves it out of the hash breaks O0/O1 as well. The §25.12 #10 golden test asserts exactly the thing Part II forbids.

#### Whether the checker recomputes liveness from the bundle

**Part I.** §25.6 A: "Output is hashed into the certificate; the Go checker recomputes it." §25.8(d): every silent instance "is licensed by `liveness.json`, whose derivation it RECOMPUTES from the bundle (it does not trust the file)", including the Bellman–Ford difference-constraint pass that voids backdated licenses; §37.4 transcript: "262 instances, 7 licenses recomputed", "0 voided differences".

**Part II.** §68.6 O10 is only "every silent inst cites a license implied by `liveness.json`", and §68.6.1 prices it at `O(|L| + |silent|)` — "licenses sorted by `(source,t0,t1)`; silent instances sorted by `license_id`; one merge scan". `liveness.json` is just a hashed input (§68.2.3 `liveness_hash`), backdating appears only as the emitter-set flag `license_voided_by_backdating`, and no obligation re-derives liveness or runs the DCG. No override marker.

**Impact.** An implementer reading Part I builds a Go re-implementation of liveness (bracketing, blake3 chain-gap detection, per-run q99 inter-arrival, Bellman–Ford negative-cycle detection); an implementer reading Part II builds a merge scan. Security posture differs sharply: under Part II a hostile emitter that ships a fabricated-but-self-consistent `liveness.json` (and a matching `liveness_hash`) gets silent instances licensed, because nothing recomputes liveness from the bundle. Part II's whole linear-cost argument depends on *not* recomputing it, but it never says Part I §25.8(d) is withdrawn.

#### Certificate container and file identity (`cert.json` vs `.spcert`)

**Part I.** The certificate is `cert.json`, ordinary JSON, with top-level members `mode`, `cut`, `hashes`, `seed` (JSON number `42`), `k`, `eclipse_version`, `invariant_U`, `redundancy_witnesses`, `psi`, `lower_bound`, `licenses_used`, `measured`, `flags`. §25.2's independence gate names `cert.json` as one of the shared on-disk formats; §25.8/§25.11/§37.4 all invoke `spectra verify cert.json` / `build/cert_3f9a12.json`.

**Part II.** §68.1: extension `.spcert`, UTF-8 no BOM, LF only, exactly one trailing LF, canonical SCF JSON, never compressed, ≤ 64 MiB, first 26 bytes exactly `{"body":{"schema":{"v":`, and an outer object with exactly two members `{"body":…,"cert_hash":…}`. §68.3 C7 forces `seed` to be a `0x`-prefixed hex string, not a number. §68.2's `Body` has no `mode`, `lower_bound`, `eclipse_version`, `redundancy_witnesses` or `measured`. No override marker on §68.1.

**Impact.** A Part I certificate fails at the magic-byte check before parsing (it starts with `"mode"`), and even reshaped it fails C12 on `lower_bound`/`eclipse_version` and C6/C7 on the numeric `seed`. Everything that names the artifact — the §25.2 independence gate's shared-format list, `GET /eclipse/proofs/{id}/certificate`, `spectra verify cert build/cert.json`, the release-pipeline CI gate — points at a file that no longer exists under that name or shape.

#### `spectra verify` command grammar and required inputs

**Part I.** §37.1: `spectra verify` is a Python typer subcommand tree — `verify cert | bundle | liveness` — that shells out to the `spectra-verify` Go binary; §37.3's CI gate is `spectra verify cert build/cert.json`; §25.8's invocation is `spectra verify cert.json --bundle b.jsonl --rules r.toml --controls c.toml` (four inputs, no goal, no liveness, no ER).

**Part II.** §68.10: `spectra verify <cert>.spcert --rules --controls --goal --bundle --liveness --er` — no `cert`/`bundle`/`liveness` subcommand, and six input files, because O4 recomputes every hash in §68.2.3 "over files given on argv" (including `goal_hash` and the new `er_hash`). §68.0 rule 1 calls `spectra verify` itself "a pure file-in/file-out binary" and §68.12 #4 forbids "any network, database, Redis, or subprocess dependency reachable from `spectra verify`". No override marker.

**Impact.** Two incompatible CLIs with the same name: Part I's `spectra verify cert <file>` is a usage error under Part II (exit 2), and Part II's invocation is a usage error under Part I. Worse, §68.12 #4 read literally outlaws Part I §37.1's design of `spectra verify` as a Python wrapper that execs `spectra-verify`. An implementer following §25.8 also omits `--goal`, `--liveness` and `--er`, so O4 cannot run at all.

#### When `minimality: EXACT` may be claimed

**Part I.** §25.9: "Exact cardinality-minimality holds only for `|A| ≤ 64`; above that the kernel downgrades to subset-minimal and says so in the flags" — i.e. the atom budget is the only precondition. §37.4 `spectra doctor` prints `controls.toml 11 controls, 27 atoms OK (|A|=27 <= 64, exact minimality available)`.

**Part II.** §68.6.2: `EXACT` is "permitted only when `C(n, |S|-1) <= 200000`"; above that "the emitter must not claim EXACT", and §68.7 additionally requires that the exhaustive obligation was actually run and recorded in `budgets` (corpus row 33, `E-MIN-UNEARNED`). No override marker.

**Impact.** `|A| ≤ 64` no longer implies EXACT is available: with n=41 atoms and |S|=6, C(41,5) ≈ 750k exceeds the cap, so the honest value is `PSI_RELATIVE` even though Part I's rule says exact minimality holds. The `doctor` line "exact minimality available" computed from |A| alone is wrong, and an emitter that trusts §25.9 emits `EXACT` certificates the checker refuses to accept or, worse, forces the checker into an unbounded exhaustive search.

#### `derived` artifacts must be omitted on a capped run

**Part I.** §25.6 B: on a grounding cap, "set `flags.grounding_capped = true` and publish the measured sizes" — the pipeline continues through F (redundancy index), G (decisive observations) and H (cost frontier) regardless, and the flagged run is merely downgraded to `OPTIMISTIC_ONLY` (§25.9). §36.3 exposes `/redundancy`, `/decisive-observations` and `/frontier` per certificate, with 404 as the only documented failure.

**Part II.** §68.2.6: `derived` (redundancy index, decisive observation set, Pareto frontier) is "**absent**, not zeroed, whenever `grounding_capped` or `corridor_capped` is set; the emitter must omit it and the checker rejects a certificate that carries it alongside those flags (`E-FLAG-DERIVED`)"; §68.7 repeats it as flag algebra; corpus row 31 enforces it. No override marker.

**Impact.** An emitter built from §25.6 publishes redundancy/decisive/frontier on every capped run, and every such certificate is rejected with `E-FLAG-DERIVED`. The three API endpoints need a defined 'suppressed under cap' response that Part I never specifies — as written they can only 404 or return a matrix that must not exist.

#### Frontier `residual` is a set, not a scalar

**Part I.** §25.6 H: the frontier yields "the exact Pareto set of `(declared_cost, residual_reachability)`"; §25.11/§36.3 expose it as `[{cost, residual, cut, evidence:[EventId]}]` — `residual` reads as a single scalar per point.

**Part II.** §68.2.6: "`residual` inside a frontier point is a **set** — `{"goal_atoms":[…],"open_corridors":[…]}` — never a scalar. A scalar residual is `E-FLAG-SCALAR`." Corpus row 32 freezes it. No override marker.

**Impact.** The Part I frontier row shape is a hard rejection, and a scalar residual expressed as a fraction would additionally trip `E-CANON-FLOAT` (corpus row 21 is literally `"residual":0.97`). The `Frontier` API model and the §25.11 cost-frontier scatter must be re-typed; a scatter plot that needs one number per axis has no single residual to plot.

#### Cut representation: named atom strings vs bit-sorted, upward-closed AtomRefs

**Part I.** §25.7: `"cut": ["x_session_binding_2", "x_egress_seg_1"]` — a list of atom names, level 2 of `session_binding` present without level 1; §36.4 renders the same object as `["session_binding>=bound", "egress_seg>=1"]`; §38.2 stores `cut_atoms TEXT[]`.

**Part II.** §68.2: `cut: Vec<AtomRef>` "sorted ascending by bit, unique, upward-closed", with O6 checking "sorted, unique, upward-closed under `x_{k,l+1} -> x_{k,l}`" (`E-CUT-*`), over a bit assignment derived deterministically from `controls.toml` and hashed into `controls_hash` (O5, `E-ATOM-*`). No override marker.

**Impact.** Part I's own example cut is not upward-closed (it contains `x_session_binding_2` without `x_session_binding_1`) and would be rejected at O6. Beyond the encoding change, cut *cardinality* changes meaning: under closure, `session_binding>=device` costs two atoms, so `|S|`, `lower_bound`, the `|S|-1` exhaustive obligation and Part I's `no cut of size 1 satisfies Psi` transcript line are all computed over a different set than Part I assumes.

#### A shared `cert-schema.toml` between the Rust emitter and the Go checker

**Part I.** §25.2's gate `gates/checker_independence.sh`: the Go module must have no cgo, no FFI, no generated-from-Rust sources, `go list -deps` must not include any path under `crates/`, and "the only shared artifacts are the on-disk formats (`rules.toml`, `bundle.jsonl`, `controls.toml`, `liveness.json`, `cert.json`) and their JSON Schemas."

**Part II.** §68.5: "The Go checker and the Rust emitter each carry a copy of the field table generated from one checked-in `cert-schema.toml`; `make cert-schema-sync` fails if either generated file is stale," and §68.7's flag algebra is "implemented once, in a generated table from `cert-schema.toml`". Part II asserts this is acceptable ("The schema table is *data*, not guard semantics") but never says it overrides §25.2's exhaustive shared-artifact list.

**Impact.** A new shared source of truth and generated code on both sides that §25.2's gate, read literally, forbids — and the flag algebra is now *semantics*, not just a field table, generated from that one file. Either the gate script must be amended (with `docs/checker-scope.md` naming the sharing) or `make cert-schema-sync` and `checker_independence.sh` will contradict each other in CI.

### RESOLVED

#### Verdict field: `mode` replaced by safety/minimality/realizability triple

**Part I.** §25.7/§25.9: the certificate carries `"mode": "ROBUST"` from the closed set `ROBUST | OPTIMISTIC_ONLY | UNSAFE`, and cut-size weakness is expressed by `flags.subset_minimal_only`; §36.4 returns `"mode": "ROBUST"`; §38.2 stores `mode TEXT CHECK (mode IN ('ROBUST','OPTIMISTIC'))` plus `verdict verdict_t`.

**Part II.** §68.2.4 (marked OVERRIDES Part I): `"verdict":{"safety":...,"minimality":...,"realizability":...}`. `safety ∈ ROBUST|OPTIMISTIC_ONLY|UNSAFE`, `minimality ∈ EXACT|PSI_RELATIVE|SUBSET|UNVERIFIED`, `realizability ∈ CHECKED|UNCHECKED`. Rationale given: Part I's `mode` conflated a safety claim with a cut-size claim so `subset_minimal_only` suppressed an honest safety result.

**Impact.** `flags.subset_minimal_only` ceases to exist (it becomes `minimality`), and a brand-new `realizability` field is required. Every downstream Part I surface keyed on `mode` must change: `ProofSummary`, the §36.4 payloads, the CLI verdict line, and the `proof_cert.mode`/`flag_subset_only` columns and the `robust_never_flagged` CHECK that references them.

#### Bare verdict strings are forbidden; the verdict must be rendered from `scope`

**Part I.** Part I prints bare verdicts everywhere: §25.11 UI header `Minimum cut {...} — ROBUST — 6 corridors — blake3:3f9a…`, §25.8 checker `VERDICT ROBUST 11ms`, §37.4 CLI `verdict ROBUST flags: none`, §36.4 `"mode":"ROBUST"`. There is no `scope` object in the certificate.

**Part II.** §68.2.2 (marked OVERRIDES Part I): a bare verdict is forbidden. The body must carry `scope:{rules,controls,licenses,er,attacker}` (all blake3 except `attacker`), the checker rejects an incomplete scope or one whose hashes disagree with `inputs` (E-SCOPE-*), and every surface renders `ROBUST(rules@3f9a…, catalog@a11c…, licenses@7d20…, er@c4b8…, non-adaptive)`.

**Impact.** A new required certificate member (`scope`) plus a shared renderer. Any API/UI/CLI string built by concatenation is now non-conformant; corpus rows 15/16 make a missing or mismatched scope a hard reject (`E-SCHEMA-MISSING` / `E-SCOPE-BIND`).

#### The checker does not validate minimality in one linear pass

**Part I.** §25.8: the Go checker checks (a)–(f) "in one pass", where (f) is `no cut smaller than |S| satisfies Psi`, at cost `O(Σ|body| + |Psi|·|A|)`; §37.4 transcript shows `(f) no cut of size < 3 satisfies Psi OK (searched 3,272 masks)` inside an 11 ms run.

**Part II.** §68.6.1 (marked OVERRIDES Part I): "Part I §5 claimed the checker 'checks in one pass' including the no-smaller-cut obligation. That is false. O0–O14 are linear; O15 is not, and it is fenced separately." §68.6.2: `EXACT` requires independently running a fixpoint for every cut of cardinality `|S|-1`, permitted only when `C(n,|S|-1) <= 200000`; `PSI_RELATIVE` only checks that no cut of size `< |S|` hits all of Ψ and must print `(no claim that a smaller sufficient cut does not exist)`.

**Impact.** Part I's single unconditional obligation (f) splits into a cheap Ψ-relative check and an expensive, optional, separately-reported exhaustive check. The performance gate in §25.12 #11 ("verifies in < 50ms") only holds for the non-EXACT path.

#### Budgets are deterministic step counters, not wall-clock caps

**Part I.** §25.6 B: grounding hard caps are `MAX_INSTANCES = 2_000_000`, `MAX_FACTS = 500_000`, `MAX_GROUND_SECONDS = 120`; hitting a cap sets `flags.grounding_capped = true`.

**Part II.** §68.2.6 (marked OVERRIDES Part I): `budgets` are deterministic step counters only — `{fixpoint_steps, bb_nodes, step_budget, budget_exhausted}` — "never wall-clock timeouts. A wall-clock budget makes flags machine-dependent and destroys byte-identical replay."

**Impact.** `MAX_GROUND_SECONDS` must be deleted as a flag-setting cap and replaced by a step budget; otherwise the same inputs on a slower machine produce a different `grounding_capped` flag and therefore a different `cert_hash`, breaking §35.6's byte-identical-certificate caching test and §25.10's `--no-cache` byte-identity requirement.

#### `rules_hash` covers the canonical AST encoding, not the file bytes

**Part I.** §25.7 certificate carries `"hashes": {"rules":"blake3:..", ...}` with no statement of what is hashed; §36.3 exposes `GET /api/v1/rules/hash` as "rules_hash bound into certificates"; §37.4 `spectra doctor` prints `rules.toml 142 rules, hash aa41c8..`, which reads as a file hash.

**Part II.** §68.4 (marked OVERRIDES Part I, calling the Part I omission a critic-flagged unresolved choice): `rules_hash` covers the canonical AST encoding (CAE) of `rules.toml`, with a fully specified prefix-length-delimited grammar; the raw file hash is recorded separately as non-authoritative `rules_text_hash`, and a text-only difference prints a NOTE and continues.

**Impact.** Naively hashing `rules.toml` bytes (the obvious reading of Part I) produces a certificate the checker rejects with `E-INPUT-RULES`. `GET /rules/hash` must now serve the CAE hash, and both Rust and Go must implement the CAE independently (gates `cert-cae-roundtrip`, `-mutation`, `-insensitivity`).

#### Adversarial corpora must carry positive controls

**Part I.** §25.12 #8 `checker_catches_tampering` is purely negative: four mutations (flip a bit in `invariant_U`, drop a corridor, forge a license, swap a witness leaf) that the checker must reject with the correct exit code. No accept-side fixtures are required.

**Part II.** §68.8 (marked OVERRIDES Part I): `fixtures/certs/positive/` must hold at least three certificates that must be ACCEPTED (ROBUST/EXACT, ROBUST/PSI_RELATIVE, UNSAFE-with-witnesses), "Without these the corpus could be passed by a checker that rejects everything"; plus a 36-row adversarial corpus asserting the exact reason code per row, and reason-code liveness (every code in `checker/codes.go` produced by some corpus file).

**Impact.** The four-mutation test is replaced by a 36-file byte-frozen corpus with per-row exact codes, positive controls, committed mutation scripts, and a corpus changelog. A checker that passes Part I's test can trivially be a reject-everything stub.

#### `spectra verify` must run with no Postgres, Redis or network

**Part I.** Part I's service architecture (§35.1) treats Postgres and Redis as ambient dependencies of the stack, and §36.3/§25.11 expose `POST /api/v1/eclipse/verify` which "runs the Go binary" server-side; §36.2 maps `503 DEPENDENCY_UNAVAILABLE` to "Postgres/Redis/kernel down".

**Part II.** §68.0 rule 1 (marked OVERRIDES Part I): `spectra verify` is a pure file-in/file-out binary with no network, DNS, database, Redis, subprocess or environment-dependent behavior beyond `TZ=UTC`/`LC_ALL=C`, writing no file unless `--out` is given; §68.11 `make verify-offline` proves it via `go list -deps` (no `net`, `net/http`, `database/sql`, `os/exec`, `plugin`) and a corpus run in an empty network namespace with Postgres and Redis stopped.

**Impact.** The checker binary must be buildable and testable with the whole stack down; any convenience path that reads the certificate from Postgres inside the checker is now a gate failure. The API may still exec it, but the binary itself must take everything from argv.

## 69 Kernel / persistence boundary

### UNRESOLVED

#### Does the `event` telemetry table survive the persistence boundary?

**Tension.** Part I 38.2 makes `event` the backbone of the system: a monthly RANGE-partitioned table with six indexes, feeding `GET /api/v1/events`, `POST /events/search`, `/state/{id}/at`, `/transitions`, `/graph`, `/integrity/*`, and analytical queries Q2, Q3 and Q4 in 38.8; 33.3's `ingest` target is defined as "parse, normalize, resolve entities, verify BLAKE3 chains, load Postgres". Part II 69.14.1 says PostgreSQL holds "Four families only: run index, run metadata, entity catalog, API-facing projections" and RULE P1 says every row must be derivable from the CAS and reproduced byte-identically by `make rebuild-projections`. Raw telemetry is none of the four families, yet Part II never says events leave PostgreSQL and never proposes another store for them. 69.16.2's own argument against row-per-record materialization (~200k records per bundle) cuts against an `event` table as much as against a fact table.

**Decision needed.** Rule explicitly on whether the `event` table (and `chain_gap`, `state_transition`, `dataset`, `bundle`, `source`) is permitted. If permitted, state which family it belongs to, whether it must carry the `proj_` prefix (69.14.2 says the prefix applies "without exception"), and whether `make rebuild-projections` must rebuild millions of event rows from bundle objects and still produce a byte-identical dump. If not permitted, name the replacement store for every Part I endpoint that reads it.

**Recommended.** Declare telemetry a fifth explicit family — an ingest-derived, CAS-rebuildable store — and exempt it by name from 69.14.2's `proj_` rule and from `make rebuild-projections`' byte-identical dump comparison, which is infeasible at event scale with partitioned tables and `now()` defaults.

#### Fate of the Part I endpoints and queries that read the now-banned tables

**Tension.** RESOLVED item 3 removes `license`, `corridor`, `fact_evidence` and `causal_edge` from PostgreSQL, but Part I depends on them from the API and from required deliverables: 36.3 serves `/eclipse/proofs/{cert_id}/corridors` (paginated), `/evidence/{fact_id}` ("expand a fact to raw event ids"), `/integrity/liveness`, `/graph` and `/graph/paths`; 38.8 makes Q1 (recursive causal closure over `causal_edge` + `fact_evidence`) a required deliverable "with a test asserting the result against a fixture bundle"; 38.6's `mv_entity_dimension_span` counts silent transitions via `license_id`. Part II offers only `proj_cert_summary`, `proj_cut_atom`, `proj_quarantine`, and a general permission to build `proj_<thing>_slice` tables with a hard row cap — but names none of these endpoints and defines no slice for corridors, evidence trees or causal paths.

**Decision needed.** For each affected endpoint and for query Q1, decide whether it is (a) served from a capped `proj_*_slice` table, (b) served by streaming the SFB objects from the CAS at request time, or (c) withdrawn. Fix the row cap for any slice, since 69.14.3 requires a CHECK constraint plus a trigger.

**Recommended.** Serve corridor and evidence expansion by scanning the run's `instances`/`cert` CAS objects on demand and cap the response, rather than adding slice tables — it keeps P1 intact and avoids reintroducing the banned vocabulary. Q1 then has no SQL implementation and 38.8 should drop it explicitly.

#### Checker dependency budget versus the input codecs the checker must read

**Tension.** 69.20's `make no-service-deps` requires "the checker's non-stdlib dependency set is empty apart from the pinned BLAKE3 implementation". But 69.3.3 makes the checker a consumer of `bundle` (NDJSON + **zstd**), `rules`, `controls` and `goal` (**TOML**), and Part I 32.5 specifies `go/verify/internal/ground/` as "independent re-grounding from rules.toml + bundle.jsonl". The Go standard library provides neither a TOML parser nor a zstd decoder, so the constraint and the codecs cannot both hold without hand-writing both decoders inside `go/verify`.

**Decision needed.** Either (a) widen the checker's allowed dependency set to a named, pinned list (BLAKE3 + a TOML parser + a zstd decoder) and update `make no-service-deps` accordingly, or (b) change the checker-visible codecs — e.g. require the kernel to emit a canonical-JSON projection of rules/controls/goal and an uncompressed bundle into the CAS for the checker — or (c) mandate hand-written decoders and accept them as part of the checker's audited surface.

**Recommended.** Option (b): the checker's independence argument is weakened, not strengthened, by two hand-rolled decoders in its trusted path. Hashed canonical-JSON projections keep the dependency set empty and keep the bytes auditable.

#### How much does the checker actually re-derive, and is exhaustive minimality the default?

**Tension.** Part I 32.5 states `go/verify` "re-implements grounding from hashed inputs" and its 37.4 transcript shows the checker regrounding all 2,104 instances and completing check (f) "no cut of size < 3 satisfies Psi OK (searched 3,272 masks)" as ordinary default behaviour. Part II 69.4.1 makes the kernel emit an `instances` SFB object "required when a checker run will follow" and lists the checker as its consumer; 69.4.2 makes `--strict-minimality` an opt-in flag that "forces exhaustive re-check when tractable"; 69.21.9 forbids claiming "the checker independently re-derives everything" and says the ABI guarantees only "that it received the hashed inputs and the published instance set". Part II never says it is narrowing 32.5.

**Decision needed.** State the checker's default obligations precisely: does it reground from `rules` + `bundle` and compare against the kernel's `instances` set, or does it accept that set as given? Is exhaustive minimality search on or off by default, and what does 37.4's transcript become? This also determines whether `spectra verify`'s release-pipeline gate is running the strict path.

**Recommended.** Make regrounding mandatory and the published `instances` set a cross-check (a mismatch being exit 20), and make `--strict-minimality` default-on in CI and default-off in the API path — then correct 32.5 and the 37.4 transcript to match, since the transcript is what implementers will build to.

#### Config that governs kernel behaviour but has no channel in the ABI

**Tension.** 69.4.1 fixes the kernel's entire input surface: `bundle`, `rules`, `controls`, `goal`, `er_config`, optional `costs`, `budget`, `seed`, `mode`, `out-dir`. 69.21.3 forbids the kernel reading configuration from anywhere but argv. Yet Part I 34.2 defines config that demonstrably governs kernel-side computation and has no argv slot: `config/thresholds/liveness.toml` (quantile choice, min sample count, gap tolerance — and 69.3.3 makes `liveness` a kernel-produced object), `config/thresholds/skew.toml` (Bellman–Ford bounds for backdating detection, a kernel pass per 32.4's `eclipse-liveness`), `config/policies/verdict.yaml` ("flag→verdict mapping; ROBUST suppression rules") and `config/policies/grounding.yaml`. Part I 34.9 further requires every certificate to carry the `profile` name, which has no argv slot either.

**Decision needed.** Decide for each of these whether it becomes (a) an additional hashed CAS input object with its own `--flag`, (b) folded into an existing object such as `controls` or `rules`, or (c) compiled into the binary — which would violate 34.1 ("behavior is data") and 34.7 (never hardcode a quantile or threshold).

**Recommended.** Add one `--thresholds blake3:…` object and one `--policy blake3:…` object to 69.4.1 and to the run manifest. Anything that changes a flag, a liveness interval or a verdict must be hashed into the certificate, and today's argv cannot express that.

#### Which exit-code table governs the Python `spectra` CLI

**Tension.** 69.8 replaces the exit-code convention but its taxonomy is written for the two binaries ("Both binaries share codes 0-10; the checker adds 20-22"). Part I 37.3's table governs the Python `spectra` CLI and is explicitly verdict-bearing: 0 = "success; for `whatif prove`, verdict ROBUST", 6 = "verdict UNSAFE", 8 = "result is flagged", 7 = "checker rejected a certificate" — and 37.3 states "CI gates use these directly". Part II 69.4.4 forbids obtaining a verdict from an exit code and calls any such Python branch "a build failure", and 69.20.1 greps the Python tree for `returncode == 0` adjacent to `ROBUST`/`UNSAFE`/`safety`. 69.12.2 additionally says the client "never reads the certificate to decide job status", which is the only other way the CLI could compute exit 6 or 8.

**Decision needed.** Rule on whether 37.3 survives for the `spectra` CLI. If it does, say explicitly that the prohibition in 69.4.4 applies only to reading the *subprocess's* return code, and carve the CLI's own verdict→exit mapping out of the 69.20.1 grep (and say which component is permitted to read the certificate to produce it). If it does not, replace 37.3 and the release-pipeline gates that depend on exit 0 meaning ROBUST.

**Recommended.** Keep 37.3 for the CLI as a deliberate, documented presentation-layer mapping computed from the checker-accepted certificate, and narrow 69.20.1's grep to `services/kernel_client.py` plus anything that reads `p.returncode` — otherwise the gate will fire on the CLI it was never aimed at.

#### Disposition of `rust/spectra-ffi` and `python/spectra_eclipse`

**Tension.** 69.1.2 and 69.21.2 ban pyo3/ctypes/cdylib boundaries outright, which removes the entire purpose of two mandated components: 32.4's `rust/spectra-ffi/ cdylib + PyO3 bindings consumed by python/spectra_eclipse` and 32.3's `python/spectra_eclipse/ thin ctypes/PyO3 binding to the Rust kernel + cert IO`. Part I 32.1 further states that a directory which "could be deleted and replaced by code already written in another language with no loss of capability... must not exist", and requires a row per language in `docs/polyglot-rationale.md` naming "the exact artifact it produces and the test that would fail without it". Part II never names either component, and 33.4's `unsafe_code` lint exemption for `spectra-ffi` is likewise left standing.

**Decision needed.** Say explicitly that `rust/spectra-ffi` is deleted and that `python/spectra_eclipse` becomes either `services/kernel_client.py` or a cert-IO-only package, and update 32.2/32.3/32.4, the 33.4 lint exemption, `docs/polyglot-rationale.md` and the 37.4 `doctor` line ("abi matches pyo3 bindings") accordingly. If `spectra-ffi` is retained for the wasm surface in 32.4/33.3, state that it produces no artifact Python may load.

**Recommended.** Delete `spectra-ffi` and fold cert IO into `spectra_core`. `rust/spectra-wasm` already covers the browser target through wasm-bindgen and does not need the cdylib.

### SILENT

#### Hash column type: BYTEA(32) vs char(71) text

**Part I.** 38.1: "Hashes are `BYTEA` of 32 bytes with a `CHECK (octet_length(h)=32)`, rendered as `blake3:hex` at the API boundary." 38.9 negative requirement: "Do not use `SERIAL`, `TIMESTAMP` without time zone, `float` for anything counted, or `TEXT` for a hash." All of 38.2-38.5 follow this (`manifest_hash BYTEA`, `bundle_hash BYTEA`, `rules_hash BYTEA`, `cert_hash BYTEA`, `prev_hash/self_hash BYTEA`, `fingerprint BYTEA`, `content_key BYTEA`).

**Part II.** 69.14.1 stores every hash as `char(71)` text ('blake3:' + 64 hex): `manifest_obj char(71)`, `kernel_build char(71)`, `checker_build char(71)`, `run_input.obj char(71)`, `run_artifact.obj char(71) PRIMARY KEY`, `entity.er_config char(71)`, `proj_cert_summary.cert_obj char(71)`. Part II never mentions 38.1 or 38.9.

**Impact.** Direct violation of a Part I negative requirement that Part II does not acknowledge. An implementer who builds section 38 first gets BYTEA columns that neither join to nor match Part II's `run_artifact`/`proj_cert_summary` keys; `make rebuild-projections` (byte-identical `pg_dump` comparison) and `make schema-lint` are written against the char(71) form.

#### Queue substrate: Redis Streams with consumer groups vs arq lists

**Part I.** 35.5, titled "Queue design (Redis Streams, not lists)": six named streams (`spectra:q:ingest|ground|prove|replay|bench|degrade`) with consumer groups, per-queue `maxlen~`, explicit `XACK`, at-least-once delivery, an untrimmed dead-letter stream `spectra:dlq`, an outbox poller that publishes only after commit, and prefetch of exactly 1. 35.7.1 computes admission control from `XLEN(stream) > soft_limit` (70% of maxlen) and returns `429 QUEUE_SATURATED` with `X-Queue-Name`/`X-Queue-Depth`.

**Part II.** 69.15.1 gives a closed table of permitted Redis keys: `arq:queue:prove` of type **list** holding "arq job envelopes", `spectra:job:<run_id>` hash, `spectra:lock:gc`, `spectra:idem:<key>`, `spectra:sse:<run_id>` pubsub. No streams, no consumer groups, no dead-letter key, and no ingest/ground/replay/bench/degrade queues. 69.15.2 is a NEGATIVE closing the set. Part II never mentions 35.5 or 35.7.

**Impact.** An implementer following Part I builds six Redis Streams plus a DLQ; every one of those keys is outside Part II's permitted set, and `XLEN`-based admission control has no meaning against an arq list. An untrimmed DLQ also contradicts 69.15.1's "no persistence / lose in-flight progress and nothing else". The two designs cannot both be built.

#### Where the certificate document is stored

**Part I.** 38.4 `proof_cert` includes `document JSONB NOT NULL` — the full certificate body stored in PostgreSQL — plus `cut_atoms TEXT[]`, `corridor_count`, `instance_count`, `silent_count`. 36.3 serves `GET /api/v1/eclipse/proofs/{cert_id}/certificate` as "full certificate JSON, content-addressed".

**Part II.** 69.13 RULE P1: PostgreSQL holds "only an index, metadata, the entity catalog, and API-facing projections". 69.21.5: "Do not store facts, instances, licenses, corridors or invariant sets in PostgreSQL, in Redis, in a JSON column, in a materialized view, or in a 'cache table.'" 69.16.1 notes the `cert` object is ~1.5 MB with "invariant set dominates". The only permitted cert-derived table is `proj_cert_summary` (safety, minimality, flags, cut_size, checker_accepted).

**Impact.** A certificate document contains the invariant set, so `proof_cert.document JSONB` is exactly the JSON-column storage 69.21.5 forbids — but Part II never names `proof_cert` or `document`. An implementer building 38.4 puts ~1.5 MB of invariant set per run into PostgreSQL and then fails `make schema-lint`/P1 review.

#### Public identifier scheme: prefixed ULID text vs uuid + blake3 object ids

**Part I.** 38.1: "public identifiers are ULID-like `TEXT` (`ev_`, `en_`, `bn_`, `cert_`, `rp_`, `jb_` prefixes)". 36.3/36.4 route on them (`/eclipse/proofs/cert_3f9a12`, `"job_id":"jb_01JQ2W7Q8K"`, `"bundle_id":"bn_01JQ2V..."`), and 38.4/38.5 key `proof_cert` on `cert_id TEXT` and `job` on `job_id TEXT`.

**Part II.** 69.14.1 keys the run table on `run_id uuid PRIMARY KEY -- generated by the Python layer`, and keys cert projections on `cert_obj char(71)` (the BLAKE3 object id). 69.15.1's Redis keys are all `<run_id>`-shaped. There is no `cert_id`, no `jb_`/`rp_`/`bn_` identifier anywhere in section 69.

**Impact.** Part I's entire URL surface and job API are built on prefixed ULIDs; Part II's persistence layer is built on uuids and content hashes with no mapping table between them. An implementer gets either unroutable API paths or a `proj_cert_summary` that cannot be joined to `/api/v1/eclipse/proofs/{cert_id}`.

#### Grounding-cap exhaustion: HTTP error vs successful flagged result

**Part I.** 36.2 defines error code `GROUNDING_CAP_EXCEEDED` at HTTP **507** — "bounded grounding refused to continue" — with `detail: {cap, reached, scenario_id}`, and 36.3 lists 507 among the errors of `POST /api/v1/eclipse/prove`. 35.5 classifies `CapExceeded` as a terminal error alongside `DeterminismError` and `ValidationError`.

**Part II.** 69.10.4-69.10.5: budget exhaustion "is deterministic and produces output, not an abort" — the artifact is written with `Flag::GroundingCapped` set, and "Exit 7 is a PASS for the API (the user gets a flagged, honest, degraded result)". Exit 7 fails only CI, on core fixtures. Part II never mentions 507 or `GROUNDING_CAP_EXCEEDED`.

**Impact.** Opposite user-visible behaviour for the same event. Part I returns an error envelope and no artifact; Part II requires a 2xx result carrying a flagged certificate. An implementer following Part I discards the deterministic partial artifact that Part II's flag/verdict machinery depends on.

#### Checker input surface: file paths and inline certificate bodies

**Part I.** 37.1/37.4: `spectra verify cert build/cert_3f9a12.json` — the checker is handed a filesystem path, and 33.3's `scenario` target produces `data/runs/<run_id>/cert.json` which `spectra verify` must accept (exit 0). 36.3: `POST /api/v1/eclipse/verify` accepts "`Cert` or `{cert_id}`" — i.e. the whole certificate document in the request body.

**Part II.** 69.1.5 NEGATIVE: "the kernel and the checker must never accept a filesystem path or a URL as an input reference. They accept only `blake3:<64 lowercase hex>` object ids plus exactly one `--cas-root` directory." 69.4.2's checker argv is `--abi 1 --cas-root /cas --cert blake3:… --out-dir /out`. Part II never mentions `spectra verify cert <path>` or the verify endpoint.

**Impact.** Both Part I invocation forms are unimplementable as written. An implementer must insert a CAS-ingest step (hash the supplied document, write it into the CAS, pass the id) that Part II never specifies and Part I never mentions — and Part I's committed `data/golden/` certificates are not in any CAS.

#### Which module may invoke the kernel

**Part I.** 35.2 places the kernel call in the pure engine layer: `engines/eclipse_bridge.py # calls Rust kernel via pyo3; still pure in/out`, and 35.3 governs it with the engine-purity import contract.

**Part II.** 69.12.1: "Exactly one module, `services/kernel_client.py`, may spawn either binary. A lint fails the build if `subprocess`, `asyncio.create_subprocess_exec` or `os.exec*` appears anywhere else in the Python tree," enforced by `make one-spawner-lint` (69.20).

**Impact.** Under Part II the kernel call moves out of `engines/` into a service module, but Part II neither says so nor mentions `eclipse_bridge.py`. An implementer who keeps Part I's layout fails `make one-spawner-lint`; one who moves it must decide unprompted what happens to 35.3's engine-purity contract and to the `engines/` → kernel arrow in the 35.1 diagram. The path `services/kernel_client.py` also does not exist in either Part I tree (32.2's root layout or 35.2's `services/api/spectra/` tree).

#### Where solver budgets live and whether they are runtime-overridable

**Part I.** 34.1: "behavior is data... thresholds... live in `config/`, are schema-validated, are hashed into every run manifest and certificate". 34.2 places the solver bounds in `config/defaults/eclipse.toml` ("atom limit, B&B node budget, corridor cap") and `config/defaults/recon.toml` ("grounding caps"), with `config/schema/*.schema.json` validation. 34.5's required transcript shows `eclipse.corridor_cap = 512 [env SPECTRA__ECLIPSE__CORRIDOR_CAP]`, and 34.6 makes level-6 env overrides legal for any key not on the frozen list (which does not include the budget keys).

**Part II.** 69.10.1 puts the same quantities (`bnb_nodes`, `corridors`, `instances`, `ground_steps`, `arena_cells`, `checker_steps`) in `budgets/default.toml`, "a CAS-stored TOML compiled to a struct and hashed into the run manifest", passed to the kernel as `--budget blake3:…` (69.4.1). 69.21.3 forbids the binaries reading configuration from environment variables other than `TZ` and `LC_ALL`, or "from any path not given on argv". Part II never mentions `config/defaults/eclipse.toml` or the precedence table.

**Impact.** Two authoritative homes for the same numbers, with incompatible mutability: Part I's corridor cap is env-overridable at runtime and lives under `config/` with a JSON Schema; Part II's is an immutable hashed CAS object and env override is forbidden. An implementer who wires `SPECTRA__ECLIPSE__CORRIDOR_CAP` (as 34.5's required transcript demands) introduces exactly the hidden nondeterminism 69.21.3 exists to prevent.

#### Retry policy for kernel jobs

**Part I.** 35.5: "Retries: 3 attempts, exponential backoff 2s/8s/32s, jitter ±20%, only for `TransientError`", with job state `retrying`; 38.5 encodes `attempts SMALLINT NOT NULL DEFAULT 0 CHECK (attempts <= 3)` and `job_state_t` includes `'retrying'`.

**Part II.** 69.11.1: "There is no retry policy for the kernel. The kernel is deterministic... Python retries ONLY on failure modes 1 and 5 [binary missing, OOM kill], at most once, and records the retry in the run manifest." 69.14.1's `run.status` CHECK list is `('queued','running','complete','failed','infra_killed')` — no `retrying`.

**Impact.** An implementer following 35.5 retries a prove job up to three times with backoff, masking infrastructure faults Part II wants surfaced, and builds a `retrying` state and an `attempts<=3` constraint that Part II's status enum has no room for.

#### Migration direction: forward-only vs mandatory tested downgrades

**Part I.** 38.7.3: "Every migration implements a real `downgrade()`. CI runs `upgrade head -> downgrade base -> upgrade head` on an empty database and on a seeded one." 38.7 also fixes Alembic naming conventions, linear history and `alembic check`.

**Part II.** 69.19.1: "PostgreSQL migrations are forward-only, numbered, checked in, and applied by one tool." 69.19.3 adds that a migration reading the CAS to fill a non-`proj_` table is a design error. Alembic and `downgrade()` are never mentioned.

**Impact.** Mutually exclusive CI gates: Part I's pipeline fails if a migration has no working `downgrade()`; Part II declares the migration set forward-only. An implementer cannot satisfy both without a ruling.

#### Entity catalog schema redefined

**Part I.** 38.3: `entity (id BIGINT IDENTITY PK, entity_uid TEXT UNIQUE, kind CHECK IN (8 values), canonical_name, first_seen, last_seen, attrs JSONB)` with a trigram index; `entity_alias (id PK, entity_id, alias, alias_kind, merge_rule, evidence_uids TEXT[] CHECK cardinality>0, UNIQUE (alias_kind, alias))`.

**Part II.** 69.14.1: `entity (entity_id bigint PRIMARY KEY, kind text, canonical_label text, er_config char(71), ambiguous boolean)`; `entity_alias (entity_id, alias, source_id, PRIMARY KEY (entity_id, alias, source_id))`. Different key columns, different column names (`canonical_label` vs `canonical_name`), no `entity_uid`, no `first_seen`/`last_seen`, no `merge_rule`, no `evidence_uids`, and a different uniqueness rule for aliases.

**Impact.** Two incompatible definitions of the same two tables, with no override marker. Part I's 36.3 `GET /entities/{id}/aliases` returns "alias set + merge evidence" — the evidence and merge-rule columns Part II's version drops — so building Part II's catalog silently breaks a documented endpoint.

#### Durable job and idempotency records in PostgreSQL

**Part I.** 35.6 requires an `idempotency_key` row storing `fingerprint`, `state`, `response_status`, `response_body_hash`, `job_id`, so a replay can return the stored response with `Idempotent-Replay: true` and a fingerprint mismatch can return `409 IDEMPOTENCY_KEY_REUSE`; 38.5 ships the `job` and `idempotency_key` DDL; 35.5 requires the job row to be written "in the same transaction as the domain write".

**Part II.** 69.14.1: "Four families only: run index, run metadata, entity catalog, API-facing projections" — neither `job` nor `idempotency_key` appears. 69.15.1 puts idempotency in Redis as `spectra:idem:<key>` (a 24h string mapping "idempotency key -> run_id") and job state in `spectra:job:<run_id>`, with Redis explicitly non-persistent and values capped at 4 KiB (69.15.2).

**Impact.** Part II's Redis mapping stores only key→run_id, which cannot implement 35.6's fingerprint comparison or stored-response replay, and a `FLUSHALL` (which 69.15.3 exercises deliberately) would make every replayed `Idempotency-Key` re-execute. An implementer must choose, unprompted, between a durable Postgres table that Part II's "four families only" excludes and a Redis key that cannot satisfy 35.6.

#### Bare ROBUST as a stored and transported verdict value

**Part I.** 38.4: `CREATE TYPE verdict_t AS ENUM ('ROBUST','OPTIMISTIC_ONLY','UNSAFE')` with `proof_cert.verdict verdict_t` and `mode TEXT CHECK (mode IN ('ROBUST','OPTIMISTIC'))`; 36.4's payload returns `"mode": "ROBUST"`; 37.4's transcript prints `verdict ROBUST`.

**Part II.** 69.8.2: the checker must exit 22 on "any certificate whose safety field is not scope-bound in the form `ROBUST(rules@<hash>,catalog@<hash>,licenses@<hash>,non_adaptive)`. A bare `ROBUST` string is not a valid ABI value and must be unrepresentable in both the Rust and Go types." 69.14.1 stores `safety text NOT NULL -- scope-bound string, 69.8.2`.

**Impact.** An implementer who builds `verdict_t` as specified stores the exact value Part II declares unrepresentable, and 38.4's `robust_never_flagged` CHECK (`verdict <> 'ROBUST' OR NOT (...)`) silently stops matching anything once verdicts are scope-bound strings — the schema-level safety net becomes a no-op rather than failing loudly.

#### Artifact locations, retention home, and new top-level directories

**Part I.** 32.2 ships an exact root tree — "Produce this structure exactly; do not invent extra top-level directories" — with run artifacts under `data/runs/` and committed certificates under `data/golden/`, and `CLAIMS.md` at the repository root. 33.3's `scenario` target outputs `data/runs/<run_id>/cert.json`. 34.2 places run-artifact lifetime in `config/policies/retention.yaml`, and 34.1 requires all policy and tunables to be schema-validated data under `config/`.

**Part II.** 69.3.1 puts every artifact in `var/spectra/cas/` (objects/, runs/, tmp/); 69.5.4 requires a top-level `abi/v1/`; 69.10.1 requires `budgets/default.toml`; 69.12.1 requires `services/kernel_client.py`; 69.17 defines six retention classes in prose rather than in `config/policies/retention.yaml`; 69.18.1 and 69.17 make `docs/claims.md` a GC root (Part I's file is `CLAIMS.md` at the root); 69.7.5 adds `docs/abi-history.md` and 69.9.3 `docs/diagnostics.md`.

**Impact.** At least four new top-level paths that 32.2 forbids, an artifact root that is not `data/runs/`, and a retention policy that lives in spec prose rather than as validated config data (contradicting 34.1). Most dangerous concretely: the GC's root set keys off `docs/claims.md`, so an implementer who builds Part I's root `CLAIMS.md` gets a GC whose PERMANENT root set is empty and which will happily collect claim-referenced certificates.

### RESOLVED

#### Python↔kernel transport: pyo3/ctypes FFI replaced by subprocess over content-addressed files

**Part I.** Part I hard-wires an in-process FFI boundary in four places: 32.3 `python/spectra_eclipse/ thin ctypes/PyO3 binding to the Rust kernel + cert IO`; 32.4 `rust/spectra-ffi/ cdylib + PyO3 bindings consumed by python/spectra_eclipse`; 33.4 workspace lints deny `unsafe_code` "except in `spectra-ffi` and `native` bindings"; 35.1 bottom layer of the architecture diagram is "KERNEL BRIDGES eclipse (Rust, pyo3), simulator (Rust), agents (Go)"; 35.2 `engines/eclipse_bridge.py # calls Rust kernel via pyo3`; 35.4 "Kernel bridges (Rust) | sync call that releases the GIL inside pyo3 | true parallelism"; 37.4 `spectra doctor` prints "rust kernel spectra-eclipse 0.9.3 OK (abi matches pyo3 bindings)".

**Part II.** 69.1.1 mandates "SUBPROCESS INVOCATION OVER CONTENT-ADDRESSED FILES"; 69.1.2 "Do NOT use pyo3, do NOT use cgo, do NOT use a long-lived RPC server, do NOT use shared memory, do NOT use a socket... A pyo3 extension module is permitted nowhere in this repository." 69.21.2 repeats the ban on pyo3, cffi, ctypes and any dynamic-library boundary. The 69.0 header is marked "OVERRIDES Part I".

**Impact.** Override is explicit and unambiguous for the transport itself, but 69.0's override text claims Part I "never stated how Python reaches the kernel" — which is false. Part I states it six times. An implementer who takes the override wording at face value may assume 69.1 fills a gap rather than deletes concrete Part I deliverables (`rust/spectra-ffi`, `python/spectra_eclipse`, the GIL-release line in 35.4, the doctor probe wording, the `unsafe_code` lint exemption).

#### The fact base, licenses and corridors as PostgreSQL rows

**Part I.** 34.10: "Postgres stores telemetry, derived facts and run artifacts; policy lives in `config/`." 38.4 creates `CREATE TABLE license (...)` and `CREATE TABLE corridor (... atom_mask BIGINT, fact_uids TEXT[], license_ids BIGINT[])`; 38.3 `state_transition` carries `license_id BIGINT REFERENCES license(id)` with index `st_silent_idx ON state_transition (license_id) WHERE is_silent`; 38.8 Q1 queries tables `causal_edge` and `fact_evidence(fact_uid)`.

**Part II.** 69.13 RULE P2: "THE FACT BASE IS NEVER MATERIALIZED IN POSTGRESQL. No table may contain facts, rule instances, hypergraph nodes, hypergraph edges, corridors, invariant sets, or licenses as rows." 69.14.3 bans the identifiers `fact`, `facts`, `rule_instance`, `instances`, `hyperedge`, `hypergraph_node`, `corridor`, `license`, `invariant`, `factbase`, `atom`, `blocker` on table and column names, enforced by `make schema-lint`. Marked "OVERRIDES Part I".

**Impact.** The principle is explicitly overridden, but again the override text says Part I "drew no boundary" when Part I in fact ships the DDL. Under 69.14.3 at least four Part I tables (`license`, `corridor`, `fact_evidence`, `causal_edge`) and several columns (`state_transition.license_id`, `proof_cert.cut_atoms`) fail `make schema-lint` on the first migration. An implementer who builds section 38 as written cannot pass Part II's gate.

#### Exit-code convention for the kernel and the checker

**Part I.** 37.3 defines a 13-code table for the `spectra` toolchain: 0 success / ROBUST, 1 internal error, 2 usage, 3 not found, 4 validation, 5 integrity violation, 6 verdict UNSAFE, 7 verification failed (checker rejected a certificate), 8 result flagged, 9 timeout or cap exceeded, 10 dependency unavailable, 130 interrupted.

**Part II.** 69.8, marked "OVERRIDES Part I": "Part I's CLI sketches implied a conventional 0/1 convention. Replace it with this closed taxonomy." Codes 0, 2-10 shared, 20-22 checker-only; 4=INPUT_MISSING, 5=INPUT_CORRUPT, 6=INPUT_REJECTED, 7=BUDGET_EXHAUSTED, 9=ENVIRONMENT_VIOLATION, 20=CERT_REJECTED. `make abi-exitcodes` asserts "no fixture returns 1".

**Impact.** The override is declared, but it mischaracterises Part I (a 13-code table is not "0/1"), and every shared code number is reassigned to a different meaning: 5 goes from integrity violation to input corrupt, 6 from verdict UNSAFE to input rejected, 7 from checker rejection to budget exhausted, 9 from timeout to environment violation. See the UNRESOLVED entry on which process each table governs.

#### Wall-clock timeouts and caps replaced by deterministic step budgets

**Part I.** 34.2 puts solver bounds in `config/defaults/eclipse.toml` ("atom limit, B&B node budget, corridor cap, downgrade behavior") and `config/defaults/recon.toml` ("horizon k default, grounding caps"); 37.2 gives every CLI command a global `--timeout <s>` flag; 37.3 exit code 9 is "timeout or cap exceeded"; 34.7 lists "a timeout" among values that must come from config rather than being hardcoded.

**Part II.** 69.10, marked "OVERRIDES Part I": "WALL-CLOCK TIMEOUTS ARE NOW FORBIDDEN IN EVERY DECISION PATH of the kernel and the checker... Replace every timeout with a deterministic step budget." 69.21.4 forbids `Instant::now()`, `time.Now()` or any elapsed-time measurement that can influence a flag, cut, verdict, corridor set or stderr content. 69.10.7 permits only an outer SIGKILL guard recorded as `INFRA_KILLED`, never as exit 7.

**Impact.** Correctly overridden in principle. The implementer must notice that `--timeout` can no longer be plumbed into the kernel from the CLI and that exit 9 no longer means timeout. The separate question of where the budget lives is a silent conflict, reported below.

## 70 Pre-registration and held-out

### UNRESOLVED

#### Two competing single-sources-of-truth for research claims

**Tension.** Part I §5.5 makes `research/questions.toml` "the single source of truth. Nothing in the README, the UI, the paper draft, or any docstring may state a numeric research claim that is not bound here", with `status` (UNMEASURED|SUPPORTED|FALSIFIED|INCONCLUSIVE) changeable only by `spectra research ingest`, a `[[H1]]` marker syntax enforced by `spectra research verify-claims --strict` (§5.6, "Do not make it optional, do not add a `--allow-unbound` escape hatch"), a `prereg_date = "SET-AT-FIRST-COMMIT"` field, and LIMITATIONS.md section 10 generated from it by `spectra research render-limitations` (§8.8). Part II §70.2 makes `research/prereg.toml` the hashed, ancestry-checked registry of metrics and hypotheses, with amendments as separate append-only files (§70.10) and numerals resolved to `result_id`s by `make check-readme-pool` (§70.8). Part II never mentions `questions.toml`, `verify-claims`, `ingest`, the `[[Hn]]` marker syntax, or the status enum; Part I never mentions prereg.toml. Part II also states that "Commit dates are attacker-controlled and are never used for ordering", which undercuts §5.5's `prereg_date` as the pre-registration record.

**Decision needed.** Does `research/questions.toml` survive alongside `research/prereg.toml`, and if so which one owns hypothesis text, status transitions and the claim-linter binding? If it is retired, §5.6's verify-claims gate, the `[[Hn]]` marker convention and §8.8's generated LIMITATIONS.md section 10 all need replacements named.

**Recommended.** Retire `questions.toml` and make `prereg.toml` plus its amendments the only registry; re-implement `verify-claims` as a wrapper over `check-readme-pool` + `lint-metrics`, and regenerate LIMITATIONS.md section 10 from `results/results.jsonl` hypothesis verdicts. Whatever is chosen, say it in §70 explicitly, because §5.5's wording claims exclusivity.

#### How a hypothesis is adjudicated: bootstrap CIs and significance tests vs pre-declared floors on medians

**Tension.** Part I §49.7 requires BCa bootstrap with 10,000 resamples and 95% CIs "for every mean, every proportion, and every ratio", Wilson intervals for proportions, arm comparisons paired on seed and scenario with Wilcoxon signed-rank p-values and Cliff's delta, and Holm-Bonferroni across each metric family; §51.2 item 3 renders the verdict from exactly one rule — SUPPORTED iff the CI excludes the null in the predicted direction after Holm — and "The renderer has no branch that prints anything else." §48.8 item 18 forbids "any mean without n and CI". Part II §70.2/§70.4 declares `statistic = "median"`, `dispersion = "iqr"`, five replicates per cell, and enforces only median+IQR+`n=` via `make lint-tables`; §70.3's M2 decision rule is "declared floor is set in the FREEZE commit, before unseal". Part II mentions no CI, no bootstrap and no significance test — and at n=5 a paired Wilcoxon cannot reach any Holm-corrected threshold, so Part I's verdict rule would render every held-out RQ INCONCLUSIVE by construction.

**Decision needed.** Which rule declares a hypothesis supported — Part I's CI-excludes-null-after-Holm, or Part II's pre-declared floor fixed at the FREEZE commit? And does Part II's median/IQR reporting satisfy or violate Part I's "no mean without n and CI" gate?

**Recommended.** Keep Part II's pre-declared floors as the adjudication rule (they are the part that makes the freeze meaningful), and either raise replicates to the n=10 Part I demands so bootstrap CIs remain computable as a secondary report, or delete the §49.7 inferential apparatus and say plainly in docs/ that the design is descriptive at n=5.

#### Part I's metric set is not declared in Part II's frozen metric namespace

**Tension.** Part II §70.3: "Every quantity the project will ever publish is declared here ... The harness refuses to emit a results row whose `metric_id` is not declared, and the docs build refuses to render a number whose `metric_id` is not declared", and it declares only M1-M8. Part I §48.6's results schema and §49.3-49.6 mandate a far larger published set: TP/FP/FN/TN, precision, recall, F1, FPR, `alerts_per_1k`, `detection_latency_s`, `detection_latency_events`, `transition_accuracy` (per dimension and pooled), `path_edit_distance`, `path_accuracy`, `evidence_coverage`, `evidence_precision`, `block_exact`, `block_jaccard`, `block_superset`, `block_miss`, `actions_to_truth`, `throughput_eps`, `p50/p95/p99_query_ms`, `peak_rss_mb`, `cpu_s_per_1M`, `gb_s_per_1M`, `cost_per_1M`, `cut_solver_ms`, `checker_ms`, `cert_bytes`. None appears in prereg.toml. §70.10 forbids editing prereg.toml after the sealing commit, and any amendment authored after the first UNSEAL makes the outcomes it touches EXPLORATORY "for the remaining life of that pool" and excluded from README.

**Decision needed.** Which of Part I's metrics are kept, and are they written into `research/prereg.toml` before the sealing commit? Anything added later is permanently exploratory for that pool, so this must be decided before `make seal-heldout` runs.

**Recommended.** Before sealing, port the Part I metrics that are still wanted into prereg.toml as `tier = "secondary"` declarations (renaming the ones §5.7 bans as ECLIPSE-facing), and delete the rest from `bench/runner/schema.py` rather than leaving undeclared columns that `lint-metrics` will block.

#### Pool taxonomy: Part I has tuning and held-out scenario sets that Part II's three-pool model has no slot for

**Tension.** Part II §70.5 defines exactly three disjoint, append-only pools — DEV, HELD-OUT, RED-TEAM — declared in `research/pools.toml`, with `check-pools-disjoint` failing "when a scenario id appears in two pools, or a tuned flag was cleared", and `tuned` monotone. Part I §49.2 item 3 requires thresholds for `rules` and `seqanom` to be selected "on a held-out tuning scenario set (`S90..S94`) disjoint from the evaluation set", and §51.4 item 7 requires a further held-out scenario set `S80..S85` authored after the rule freeze. Part II §70.9 item 5 says baseline tuning is a ledger event with `kind:"THRESHOLD"` that marks the baseline itself TUNED and requires a published sensitivity sweep (§70.7).

**Decision needed.** Where do S90-S94 and S80-S85 live in the three-pool model — are they DEV, a fourth pool, or deleted? And does selecting a baseline threshold on S90-S94 mark those scenarios TUNED and require the §70.7 THRESHOLD sensitivity sweep?

**Recommended.** Fold S90-S94 into DEV, declare baseline threshold selection as a `THRESHOLD` ledger entry with the sweep published, and either seal S80-S85 as a second held-out pool under its own pre-registration amendment or drop them, since §70.0's ordering rule forbids authoring them after the rule table exists.

#### Seeds and repeats are two axes in Part I and one axis in Part II

**Tension.** Part I §48.3 item 5: "`repeats` are re-executions of an identical cell for timing variance. `seeds` are distinct data draws for statistical variance. They are different axes and **must never be collapsed**. Accuracy statistics aggregate over `seeds`; latency statistics aggregate over `seeds x repeats`." Part II's cell is `(scenario, operator, level, arm, replicate)` with `seed(cell)` derived from a hash that includes `replicate_u8` — so each replicate is a distinct data draw, i.e. Part I's seed axis under a new name — and Part II requires each cell to be re-runnable "in isolation and byte-identically", which leaves no axis carrying timing variance at all. Part II also never mentions `warmups` (§48.3 item 6) or `contended` cells (§48.4 item 12), both of which Part I requires to be recorded and excluded from latency aggregates.

**Decision needed.** Is Part II's `replicate` the seed axis, the repeat axis, or both? If timing is still to be reported (Part I §49.6, §51.2 RQ5 `checker_ms / cut_solver_ms`), where does its variance come from, and do warmups and contention flags survive into Part II's row schema?

**Recommended.** Treat `replicate` as the seed axis, add an explicit `repeat` field to the Part II row for latency-only aggregation, and declare warmup/contended as suppression flags in prereg.toml so `lint-tables`'s PARTIAL rule covers them.

#### Ban on curve fitting vs Part I figures and falsifiers that require a fit

**Tension.** Part II §70.4: "No smoothing, no curve fitting, no interpolation between completeness levels. Plot the points." Part I §50.6 mandates figure P12 (`checker_cost.pdf`) "with a fitted line and the fit's R² stated" and P4 (`blindness_premium_surface.pdf`) as a Julia/Makie surface over (completeness x silence fraction), which interpolates between exactly those levels; Part I §5.4's falsifier for H4 is "Measured checker time is super-linear in the declared cost model (**fitted exponent > 1.2** over the size sweep)". Part I §50.6 item 12 independently bans smoothing and splines but clearly permits CI ribbons and the P12 fit.

**Decision needed.** Is the no-fitting rule scoped to degradation curves over completeness levels, or global? If global, H4's fitted-exponent falsifier and figures P4 and P12 must be redefined, and Part I §49.7's CI ribbons need an explicit exemption.

**Recommended.** Scope the ban to the degradation axis (no smoothing or interpolation across completeness levels), and explicitly permit a declared regression for the checker cost model, since H4 is unfalsifiable without one.

### SILENT

#### Hypothesis identifiers H1/H2/H3 mean different things in the two parts

**Part I.** §5.3: H1 = "E[|S_rob|] - E[|S_opt|] is strictly increasing in telemetry loss ... and zero at 100% completeness"; H2 = "Every control in S_rob \ S_opt is attributable to at least one License, and re-running with those licenses' sources made live removes that control ... in at least 80% of attributed instances"; H3 = "|D| <= 3 for at least half of the degraded runs". Each has a falsifier row in §5.4 and lives in `research/questions.toml`; §5.3 adds "Do not state a hypothesis anywhere else in prose without linking to its ID."

**Part II.** §70.3 declares, with no reference to Part I's set: H1 = "A_eclipse produces strictly fewer false ROBUST verdicts than B2_no_licenses across levels below 100% completeness"; H2 = "M4 precision for A_eclipse exceeds that of B4_max_licenses"; H3 = "A_eclipse beats B5_dev_frequency_prior on M4 on HELD-OUT scenarios". §70.12 prints `H1: <<VERDICT:H1>> H2: ... H3: ...`.

**Impact.** Same ids, disjoint meanings, no override marker. Part I's `[[H1]]` claim markers (§5.6), the §5.4 falsifier table, the §8.8 LIMITATIONS.md section-10 status table and Part II's `<<VERDICT:H1>>` tokens all collide in one namespace. A number bound to "H2" is ambiguous between the license-attribution claim and the premium-vs-B4 claim; an implementer will wire one registry's H2 to the other's falsifier and report a verdict about the wrong hypothesis.

#### The words precision / recall / accuracy / F1 applied to ECLIPSE output

**Part I.** §5.7 negative requirement: "Do NOT use the words 'accuracy', 'detection rate', 'precision', or 'recall' for ECLIPSE outputs. ECLIPSE emits verdicts and cuts, not classifications. The optional ML anomaly baseline is the only place those words are permitted, and there they must be scoped to that baseline by name." §8.6 has a linter over UI strings, API schemas and report templates.

**Part II.** §70.3 declares as primary/headline metrics `M4_premium_precision` (and `M4b_premium_recall`) computed over the blindness premium of the ECLIPSE arm, plus `M5_chain_edge_f1` "Precision/recall over derived causal edges", `M3_false_unsafe_rate`, `M7_dos_exact_rate`, `M8_adversarial_reject_rate` — all on `A_eclipse`, with no override marker.

**Impact.** Part II's headline metric is named with a word Part I's string linter is specified to reject, and Part II deletes the ML baseline that was the only sanctioned home for those words. Whichever gate is built first fails the other: either `lint-metrics` blocks nothing and §5.7's linter red-flags M4/M4b/M5, or the §5.7 rule is quietly dropped without anyone recording that the anti-classification framing was abandoned.

#### How many runs a reportable cell needs

**Part I.** §49.7 item 14: "Minimum n = 10 seeds per reported cell. A claim resting on fewer is not publishable; the renderer emits NOT REPORTABLE." §48.8 item 25: a single-seed value emits "n=1 (NOT REPORTABLE)" and CI fails. §48.3 sets `seeds` = 10 distinct draws and `repeats` = 5. §5.5 registry field `sample_size_min = 40`.

**Part II.** §70.2 `[replication] seeds_per_cell = 5, replicate_index_range = [0,4]`; §70.4: "The binding minimum is five replicates per cell (binding constraint, not a measurement)"; §70.12 transcript reports `n=5` cells as headline HELD-OUT results, and the held-out pool is 4 scenario families.

**Impact.** Every Part II headline cell (n=5, 4 families) is NOT REPORTABLE under Part I's renderer rule and falls below the registry's `sample_size_min = 40`. An implementer who builds the §49.7 gate will find the entire §70 held-out matrix refused at render time; one who builds §70 first will silently weaken a floor Part I called non-publishable. Part II never says it is lowering the floor.

#### Degradation operator catalog and how levels cross operators

**Part I.** §48.3/§50.2: eleven operators — `none`, `delete_random`, `delete_targeted`, `reorder`, `duplicate`, `delay_jitter`, `corrupt_field`, `strip_identity`, `backdate`, `forge_provenance`, `silence` — with `completeness` as doubles [1.0 .. 0.3]. §50.1 item 2: completeness applies only to data-removing operators; shape-preserving operators sweep their own intensity knob and record `completeness = 1.0`. §50.3: "`delete_targeted` is the honest case. Present them adjacent ... Never report `delete_random` alone." The matrix lives in `bench/manifests/*.json`.

**Part II.** §70.2 `[degradation]`: `operators = ["delete","delay","duplicate","reorder","corrupt","suppress"]`, `levels_pct = [100,90,80,70,60,50,40,30]`, `cell = "(scenario, operator, level, arm, replicate)"` — six operators, every one crossed with every completeness level, declared in `research/prereg.toml`, which §70.6 freezes and §70.10 forbids editing after the seal.

**Impact.** `backdate`, `forge_provenance`, `strip_identity` and `none` vanish, so Part I's §50.2 checks on the Bellman-Ford license-voiding path, on chain-forgery misclassification (BLIND vs SUPPRESSED), on entity-resolution degradation, and the `none` reference row for all deltas have no cells to run in. The random/targeted deletion split collapses into one `delete` operator, making §50.3's mandated adjacency impossible. Crossing shape-preserving operators (`duplicate`, `reorder`, `corrupt`) with completeness levels contradicts §50.1's explicit rule. There are now two authorities for the matrix (the manifest and prereg.toml) and no statement of which binds.

#### When the held-out scenarios are created relative to the rule table

**Part I.** §51.4 item 7: "a held-out scenario set (`S80..S85`) is authored **after the rule table is frozen**, and its results are reported separately." §8.2 IV5 and §8.4 M3 similarly describe a held-out fixture family from unseen seeds run only in the release job.

**Part II.** §70.0: "Implement everything in this section before any rule is authored. The order is load-bearing: if `rules/rules.toml` exists in the repository before the pre-registration commit, the protocol is dead and cannot be retrofitted." §70.5: `make seal-heldout` is "run once, before any rule exists" and "Fails if the working tree contains `rules/rules.toml`, `axioms/*` or `controls.toml`". §70.11 ancestry: [PR] → [SEAL] → [DEV rule authoring] → [FREEZE] → [UNSEAL].

**Impact.** Opposite orderings of the same two events. Following Part I (author held-out after the freeze) produces scenarios that `make prereg-check` and `make seal-heldout` will both refuse, and §70.5's "There is no resealing" means the mistake is unrecoverable without a new pre-registration. Part II never mentions §51.4's held-out set or §8.4's M3, so an implementer reading Part I alone builds exactly the sequence Part II says destroys the protocol.

#### Whether a false-ROBUST result on the development pool fails the build

**Part I.** §50.7 item 13: "Across the entire executed matrix, the count of rows with `eclipse_verdict = ROBUST` and `block_miss = 1` must be exactly zero. This is a build gate, not a metric." §5.3 H0 is corpus-wide zero false ROBUST; §5.4: "A single instance falsifies H0. No tolerance, no averaging."

**Part II.** §70.3 `M1_false_robust_count` decision rule: "count > 0 on HELD-OUT fails the build; count > 0 on DEV opens a ledger entry." §70.7 then treats the DEV failure as the normal trigger for a rule change recorded as `CORRECTION`/`COVERAGE`/`THRESHOLD`.

**Impact.** Part II splits by pool a gate Part I declared absolute over the whole matrix, and never says so. Under Part II a DEV false-ROBUST is an ordinary engineering event; under Part I it is an H0 falsification that stops the build and must be filed in `research/results/falsifications/`. Two CI gates with the same name and different pass conditions; the looser one silently becomes authoritative for the pool where most runs happen.

#### What to do when a held-out run produces a false-ROBUST verdict

**Part I.** §50.7 item 13: "If it is ever nonzero: stop, **do not publish**, write the counterexample cell to `bench/results/<run_id>/VIOLATIONS.json` ..., add it as a regression fixture, and **fix the kernel**."

**Part II.** §70.13 item 3: "Do not edit a rule, axiom, guard, threshold or ER heuristic in response to a held-out failure. Held-out failures are results. Record them and publish them." §70.6: any later rules edit forces `make refreeze`, marks every held-out row `superseded=true`, and a new headline requires a brand-new sealed pool.

**Impact.** Directly opposite instructions on the single most consequential event in the project: Part I says fix the kernel and withhold publication; Part II says publish the failure and do not touch the kernel. Following Part I burns the sealed pool permanently (the fix supersedes every held-out row) while also suppressing the result Part II requires to be published. No override marker anywhere in §70.

#### The ceiling arm violates Part I's fairness assertion

**Part I.** §49.2 item 4: "Every arm sees the perturbed bundle, never the pristine one. The perturbation is applied once per cell and the resulting `bundle_hash` is asserted equal across arms." Violations of the projection contract "abort the cell".

**Part II.** §70.9 mandates `C_ceiling_clean` — "full ECLIPSE run on the **undegraded** bundle for the same scenario" — and its fairness row gives it `undegraded bundle.jsonl` = Y and `degraded bundle.jsonl` = –, with every arm executed "with a read-only mount containing only those paths".

**Impact.** A runner built to §49.2 aborts every `C_ceiling_clean` cell, because its `bundle_hash` cannot equal the other arms'. Part II's override marker in §70.9 covers the arm list but says nothing about the equal-bundle-hash assertion, so an implementer carrying §49.2 forward hits a hard abort on a mandatory arm.

#### Where results live, at what granularity, and whether they are committed

**Part I.** §48.6: the normative schema is Pydantic v2; row granularity is (scenario, arm, seed, operator, completeness, repeat); output is `bench/results/<run_id>/results.jsonl` plus `results.parquet` with a fixed DuckDB DDL including `eclipse_verdict VARCHAR -- ROBUST|OPTIMISTIC_ONLY|UNSAFE|null`. §48.2: `bench/results/` is **git-ignored except `results/INDEX.json`**. §48.8: documents render from `results.parquet` of one run, and "Do NOT copy a number from an older run into a newer document."

**Part II.** §70.8: rows live in `results/results.jsonl` at metric granularity (`result_id`, `prereg_id`, `metric_id`, `pool`, `arm`, `scenario_id`, `operator`, `level_pct`, `replicate`, `n`, `value`, `dispersion`, `flags`, `suppressed`, `superseded`, `rules_lock_generation`, `rules_lock_blake3`, `unseal_index`, `tuned_inputs`); "`make docs` renders every table and figure programmatically from the **complete** `results/results.jsonl`"; superseded rows "stay in the artifact and stay renderable"; and "a results row whose `safety` field is a bare `ROBUST` string is rejected by the schema."

**Impact.** Different path, different key, different retention model, and Part I's DDL stores exactly the bare verdict string Part II's schema rejects. Part I git-ignores the results file, so Part II's requirement that every README/docs numeral resolve to a durable `result_id` and that superseded rows remain renderable cannot hold in a fresh clone. Part I renders per-run and forbids mixing runs; Part II renders from the accumulated all-runs artifact. Neither is marked as overriding the other.

#### Escape hatches for hard-coded numerals in documentation

**Part I.** §48.8 item 24: `scripts/check_generated.py` fails on a numeric literal outside a GENERATED region "except in a `codeblock`, a version string, or a line ending with `<!-- static: <reason> -->`."

**Part II.** §70.8: "Any numeral appearing anywhere in `README.md`, `docs/`, the UI, the demo script or a figure caption must resolve to a `result_id`. Hard-coded numerals fail the build." No exemptions are listed, and §70.0 forbids unprovenanced numbers in README.md, docs/, the demo and the UI outright.

**Impact.** Part I's `<!-- static: -->` line is precisely the mechanism §70.8 exists to close ("This closes the Part I defect where illustrative figures in the prompt itself were copied into documentation as if measured"), but Part II never names the exemption, so an implementer keeps it and the closure fails.

### RESOLVED

#### What makes a number publishable (provenance, pool labels, README contents)

**Part I.** §48.8/§51.6: every number is rendered from `bench/results/<run_id>/results.parquet` by `scripts/render_numbers.py`; RESULTS.md is fully machine-generated from one run; README may quote up to six numbers, each in a GENERATED region linking to RESULTS.md. Any validly executed run's numbers are publishable — there is no pool concept, no seal, no rules hash. §5.5 binds claims to `research/questions.toml` instead.

**Part II.** §70.0 (marked OVERRIDES Part I §5-8 and §48-51): "a measured number is publishable only if it carries a pool label, a pre-registration id, a frozen-rules hash and a seal-and-unseal history. Numbers without that provenance are development telemetry, not results, and may not appear in README.md, docs/, the paper draft, the demo, the UI or any commit message." §70.8: README may quote HELD-OUT rows only, enforced by `make check-readme-pool`; every table rendered twice (DEV headed TUNED, HELD-OUT).

**Impact.** The whole Part I evaluation corpus (`bench/manifests/full.json`, 12 scenarios x 10 seeds) is DEV/TUNED under Part II, so Part I's mandated RESULTS.md "Headline comparison", "Degradation" and "Ablations" tables and the §51.2 RQ summary table can no longer be published as results without a sealed held-out pool behind them. An implementer who builds §48-51 first produces a reporting pipeline with no pool column, which check-readme-pool rejects wholesale.

#### Benchmark comparison arms

**Part I.** §49.1: "Implement exactly these arms" — `rules` (~40 hand-written detection rules, Python), `seqanom` (order-2 Markov + autoencoder, PyTorch, "The ML baseline", trained on the benign prefix), `spectra`, `graphonly` (hand-tuned path-scoring heuristic, ECLIPSE disabled), plus optional `spectra_nolic`. §48.2 fixes `bench/runner/arms/arm_rules.py`, `arm_seqanom.py`, `arm_spectra.py`, `arm_graphonly.py`. §49.2 lets `seqanom` read "benign-prefix labels only, for training cutoff" from ground truth.

**Part II.** §70.9 (marked OVERRIDES Part I: "the benchmark harness (§48-51) is redefined as multi-arm"): mandatory arms are `A_eclipse`, `B0_trivial_all`, `B0_trivial_none`, `B1_time_order`, `B2_no_licenses`, `B3_no_obligations`, `B4_max_licenses`, `B5_dev_frequency_prior`, `C_ceiling_clean`; "none may be dropped without a pre-registration amendment". Clause 1: "No arm reads ground truth. Ground truth enters only through the metric code (R4), after all arms have written their outputs."

**Impact.** No Part I arm id survives. The ML baseline and the graph-only ablation disappear, and with them Part I's §51.2 RQ1 row ("spectra − rules"), RQ4 row ("spectra − spectra_nolic"), the §49.7 rendered table template whose columns are rules/seqanom/graphonly/spectra, plot P6 (`tamper_matrix`, cols = arms), and `bench/arms/TUNING.md` (§49.1 item 2). Part II's no-ground-truth clause also kills `seqanom`'s training protocol, and its "do not describe these arms as prior work or competitors" contradicts Part I's framing of `rules`/`seqanom` as external-style references.

#### Meaning of the rules hash in the certificate and in freezes

**Part I.** §6.4 TB3: "Certificate embeds hashes of rules, bundle, controls, liveness, goal, plus seed and horizon k"; §8.6 footnote prints "the rule table (blake3:..)" — never says whether the hash is over file bytes or over the compiled guard AST (only §7.2's `guard_hash` column is AST-scoped).

**Part II.** §70.6 (marked OVERRIDES Part I): "Part I left `hashes.rules` ambiguous between file bytes and AST; for freeze purposes it is the canonical AST encoding, and the certificate must carry both so a reader can tell cosmetic drift from semantic drift."

**Impact.** Certificate schema and checker must carry two rule hashes, not one; a comment-only edit must not break a freeze but must still be visible.

## 71 Claims registry

### UNRESOLVED

#### Machine-generated numeric documents have no route through the CLM anchor gate

**Tension.** Part I §48.8(22-24) makes every published number live inside an HTML-comment-delimited `<!-- BEGIN GENERATED ... -->` region rendered by `scripts/render_numbers.py`: docs/research.md §11-13 (§51.1, §51.2), the ablation table (§50.5), RESULTS.md (§51.6(14), "100 percent inside GENERATED regions except its title"), and docs/STATUS.md (§52.1(3), generated by `make status`, "Never hand-edit"). Part II §71.2.3 makes every such numeral a claim candidate; §71.2.5 fails it as UNANCHORED unless it carries a CLM anchor, and §71.1.1(2) defines the markdown anchor as "an HTML comment immediately preceding the sentence's block" — yet §71.2.2 declares "A table cell is one unit", so a table of generated values has more units than anchorable blocks. Part II grants a generated-block carve-out only inside LIMITATIONS.md (§71.6.1), and §71.2.4 forbids exemptions for README's first screen, paper:abstract, LIMITATIONS.md and meta:*, with a 25-entry cap elsewhere.

**Decision needed.** Does `make claims-check` skip `<!-- BEGIN GENERATED -->` regions the way it skips fenced code blocks (treating the region header's run id as the support binding), or must every generated table cell carry its own CLM record? If the former, §71.2.2 and §71.2.5 need an explicit generated-region rule; if the latter, §51.2/§51.6/§50.5/§52.1(3) must be rewritten because a renderer cannot emit per-cell anchors under the current anchor grammar.

**Recommended.** Add a generated-region rule to §71.2.2 mirroring §71.6.1: a region header `<!-- BEGIN GENERATED: ... run=<run_id> ... -->` acts as the anchor for every unit inside it, and the support resolver validates the region's run id against the gate ledger and input hashes exactly as §71.3 does for a CLM record. This preserves both models and keeps §48.1's monopoly intact.

#### Root RESULTS.md is not on the closed surface list

**Tension.** Part I §51.6(14) makes `RESULTS.md` at the repo root the headline results document, fully machine-generated, and §51.6(15) has the README quote numbers that link to it; §51.5 requires the honesty clause verbatim in it. Part I is itself split on location — §53.1's tree lists `RESULTS.md` under `docs/`, and §52.10 renders figures "into `docs/RESULTS.md`". Part II §71.2.1 declares its surface list "the closed list; adding a surface requires editing this list and the registry schema together" and includes `README.md`, `LIMITATIONS.md`, `SECURITY.md`, `docs/**/*.md`, `CHANGELOG.md`, `docs/release-notes/*.md` — but no root `RESULTS.md`.

**Decision needed.** Is RESULTS.md at the repo root or under docs/, and is it a claims surface? As written, the repo's most number-dense published file escapes the gate entirely if it sits at the root, and is fully gated (and fully failing, per the generated-regions item) if it sits under docs/.

**Recommended.** Settle the location in favour of one path, add it explicitly to §71.2.1, and pair it with the generated-region rule above so a wholly machine-generated file passes by construction rather than by omission.

#### BP-16 bans the vocabulary of Part I's mandated statistics

**Tension.** Part I §49.7(15) requires "Confidence intervals: BCa bootstrap, 10 000 resamples ... Report 95 percent CIs for every mean, every proportion, and every ratio"; §48.8(25) has the renderer refuse "a scalar that lacks `n` and a confidence interval"; §49.7(18) forbids "any mean without n and CI"; §50.2 defines `delete_random` as "drop each event independently with prob `1-c`" and says SPECTRA "must report reduced confidence via more corridors"; the rendered table template (§49.7(19)) and RESULTS.md are full of CI brackets. Part II BP-16 bans `\bconfidence\b` / `\bprobability\b` / `\brisk score\b` / `\bseverity\b` / `\blikelihood\b` with the mandated replacement "delete; report the set, not a scalar", under the unwaivable G-CLAIM-BANNED whose `exempt_paths` (§71.4) is limited to docs/banned.toml, docs/claims-policy.md and docs/prompt/. §71.7(5) extends the same ban to schema field names.

**Decision needed.** BP-16's stated rationale is ECLIPSE §9's prohibition on verdict scores, not on statistics. Does the ban carve out the statistical senses — "confidence interval", "BCa CI", "probability" as a generator parameter — or must Part I's statistical reporting be reworded (e.g. "95% interval", "BCa interval", "drop rate")?

**Recommended.** Narrow BP-16 to the scoring senses with explicit negative lookarounds (allow `confidence interval`, `confidence band`, and `probability` inside operator definitions), and state the carve-out in banned.toml so it is machine-checkable rather than left to reviewer judgement. Without this, §49.7's mandated reporting cannot ship.

#### Part I's own prohibition texts trip the unwaivable banned-phrase gate

**Tension.** Part I requires the project to publish lists of forbidden words: §55.1 forbids topics "`ai`, `agent`, `enterprise`, `production-ready`"; §55.5 forbids badges "'made with love', 'awesome', 'production ready', 'AI powered'"; §56.1 row 21 is "No probability, confidence, cost-mass or invented dollar figure in any output or doc"; §56.3(2) is "Never say 'should work', 'is production ready', 'fully verified', 'proves the system is secure'"; §53.5 puts the anti-slop checklist link in CONTRIBUTING.md and lint rules in docs/DEVELOPMENT.md; §55.3's PR template requires "Anti-slop checklist (section 56) run and pasted". Part II BP-04, BP-06 and BP-16 match `AI[- ]powered`, `production[- ](ready|like)`, `enterprise[- ]grade`, `confidence`, `probability` anywhere outside three exempt paths (docs/banned.toml, docs/claims-policy.md, docs/prompt/), and §71.2.1 scans `docs/**/*.md` and `.github/PULL_REQUEST_TEMPLATE.md`. §71.7(12) makes G-CLAIM-BANNED unwaivable and says the waiver mechanism refuses to parse its id.

**Decision needed.** Where do Part I's mandated prohibition lists live, and how are they exempted? As written, publishing the §55.5/§56.1/§56.3 lists anywhere under docs/ or in the PR template is an unwaivable build failure, and there is no mechanism to grant an exception.

**Recommended.** Extend §71.4's `exempt_paths` to cover the documents whose job is to enumerate forbidden wording (docs/DEVELOPMENT.md's lint section, CONTRIBUTING.md, the anti-slop checklist document, .github/PULL_REQUEST_TEMPLATE.md), or require those lists to be generated from docs/banned.toml so there is exactly one authoring site — the same pattern §71.5 uses for framing.

#### Does the scope binding live in the verdict data or only in rendered text?

**Tension.** Part II §71.4.1(4): "`spectra verify` REJECTS a certificate whose `mode` string is a bare token without its scope binding, with exit code 3 and reason `E_MODE_UNSCOPED`", and §71.7(4) lints the literal "ROBUST" outside the single constructor. Part I §48.6's normative results schema stores `"eclipse": {"verdict": "ROBUST"}` and the DuckDB DDL declares `eclipse_verdict VARCHAR -- ROBUST|OPTIMISTIC_ONLY|UNSAFE|null`; §50.7(13) states the build gate as "the count of rows with `eclipse_verdict = ROBUST` and `block_miss = 1` must be exactly zero"; §51.6's RESULTS.md gate table and §52.10's M7 acceptance are phrased the same way. Part II never mentions §48.6's schema or §50.7's query.

**Decision needed.** If the certificate `mode` and the stored verdict become `ROBUST(rules@..., catalog@..., licenses@..., non-adaptive)`, every equality filter in §50.7, §50.3, §50.5, §51.6 and the parquet DDL breaks, since the string now embeds per-run hashes. Is the scope binding a rendering-layer concern (data keeps the bare enum, one constructor renders the bound form), or does it change the certificate and the results schema?

**Recommended.** Keep the enum in data (certificate `mode`, parquet `eclipse_verdict`) and make the scope binding a required rendering step plus separate `rules_hash`/`controls_hash`/`licenses_hash` fields the checker validates; restate §71.4.1(4) as "rejects a certificate whose mode lacks the accompanying hash fields". Otherwise §48.6 and §50.7 must be reissued with the new string form and hash-stripping queries.

#### Support freshness requires run-manifest fields the §48.6 schema does not carry

**Tension.** Part II §71.3 requires `support.run` to resolve to `artifacts/runs/<run_id>.json` whose `rules_hash`, `controls_hash`, `axioms_hash`, `er_config_hash` and `git_sha` all equal what the current working tree produces, that the run carry no `grounding_capped` / `corridor_cap_hit` / `er_ambiguous` / `greedy_cover` flag unnamed by the scope, and that `support.gate` appear in `artifacts/ci/gates.json` for the current git_sha. Part I §48.6's normative row carries only `manifest_hash`, `spectra_version`, `git_commit`, `bundle_hash`, `ground_truth_hash` and a three-flag block (`grounding_capped`, `subset_minimal_only`, `greedy_cover`) — no rules/controls/axioms/ER-config hashes and no `corridor_cap_hit` or `er_ambiguous` flag — and §48.7 fixes the layout as `bench/results/<run_id>/`, not `artifacts/runs/`. §71.10 attributes the run manifests and gate ledger to §62 but says nothing about amending §48.

**Decision needed.** Must §48.6's Pydantic/JSON-Schema/DuckDB schema gain `rules_hash`, `controls_hash`, `axioms_hash`, `er_config_hash` and the two extra flags, and does `artifacts/runs/` replace or mirror `bench/results/<run_id>/`? Until this is settled, `support_state()` cannot be implemented against the only normative results schema Part I defines.

**Recommended.** State explicitly in §71.3 (or in §62) that §48.6's row schema is extended with the four input hashes and the two additional flags, and give one canonical location for run manifests, with §48.7's directory either renamed or declared a symlinked view.

#### README first screen: the §53.2 status banner vs the §71.5 mandated order

**Tension.** Part I §53.2 fixes the README section order as (1) name + one-sentence definition + status banner, (2) the status banner verbatim `> Status: research prototype (v0.1.0, milestone M10). Synthetic data only. Not a security product. See docs/LIMITATIONS.md.`, (3) hero asset, then quickstart and the flagship. Part II §71.5(1) defines the first screen structurally as "the byte range from the start of README.md to the first `\n## ` heading" and requires it to contain, "in order: the H1, [oneline] verbatim, [disclaimer] verbatim, and a link whose target is `LIMITATIONS.md` and whose anchor text is exactly `Limitations and known-unsound regions`", gated by G-FRAMING-README. Separately, §55.1 caps the GitHub description at 120 characters while §71.5's [oneline] is far longer and §71.2.1 relocates the About text to `docs/repo-metadata.toml`.

**Decision needed.** Does the §53.2 status banner survive, and if so does it sit before or after [oneline]/[disclaimer]? Its "See docs/LIMITATIONS.md" link conflicts with the mandated root target and exact anchor text, and its content largely duplicates [disclaimer]. Relatedly: what goes in the 120-character GitHub About field now that [oneline] cannot fit?

**Recommended.** Fold the banner's unique content ("research prototype", "synthetic data only", "not a security product") into [disclaimer] so there is one authored source, drop §53.2(2) as a separate verbatim element, and add a short `[about]` string to docs/framing.toml for the 120-character metadata field, gated the same way.

#### "No floats anywhere" in limits.json vs float-valued metrics and bootstrap CIs

**Tension.** Part II §71.6.2 specifies `artifacts/limits/limits.json` with "integers and rationals as `{"num":int,"den":int}` — no floats anywhere, per the determinism charter", and it is produced by the same validation matrix that feeds LIMITATIONS.md. Part I §48.6 and §49 define every accuracy metric as a float (`transition_accuracy: 0.918`, `completeness DOUBLE`, `p50_query_ms DOUBLE`, `path_accuracy = 1 - d/max(...)`), and §49.7 requires BCa bootstrap confidence intervals and Wilson intervals on every mean, proportion and ratio. §71.3(6) additionally requires every numeral in a QUANT claim's text to "occur, after normalisation, as a value in `support.artifact`".

**Decision needed.** Does the rational-only rule apply only to limits.json, or also to results.parquet and summary.json (which are the support artifacts for most QUANT claims)? How is a BCa interval — inherently a pair of resampled floats — represented under a no-float rule, and what is the normalisation that lets a rendered decimal in prose match a `{num,den}` value in the artifact?

**Recommended.** Define the normalisation explicitly in §71.3(6) (rational → decimal at a declared precision, compared exactly) and state whether §48.6's float schema is unchanged with conversion happening at the limits.json boundary. Bootstrap endpoints likely need a declared fixed-precision rational encoding, or an explicit exemption, or §49.7's CIs cannot be represented at all.

### SILENT

#### LIMITATIONS.md lives at the repo root (Part II) or under docs/ (Part I)

**Part I.** §53.1's required tree places `LIMITATIONS.md` inside `docs/`. §53.2(2) mandates the status banner verbatim ending "See docs/LIMITATIONS.md." §54.2's demo ends "Close on docs/LIMITATIONS.md open on screen for 5 seconds." §53.5 specifies the contents of `LIMITATIONS.md` as a docs/ document.

**Part II.** §71.6: "`LIMITATIONS.md` sits at repository root and is linked from the README first screen." §71.2.1's closed surface list contains a root-level `LIMITATIONS.md` entry separate from `docs/**/*.md`. §71.5's [disclaimer] text ends "See LIMITATIONS.md." (root-relative), and §71.5(1) requires a README first-screen link "whose target is `LIMITATIONS.md`". Part II never states it is moving the file.

**Impact.** An implementer following Part I creates `docs/LIMITATIONS.md`; G-FRAMING-README then fails (no root LIMITATIONS.md link), G-LIMITS-FRESH/G-LIMITS-NOHAND never fire on the real file, and §53.2's banner link and §54.2's demo close point at a path Part II's gates do not recognise. Two divergent files can also both exist and drift.

#### Two incompatible claim registries: docs/claims.toml (claim→test id) vs docs/claims.md (claim→artifact/run/gate)

**Part I.** §53.4: "`make docs-check` maps README claim anchors to test IDs listed in `docs/claims.toml` and fails on an unmapped claim." §52.13 acceptance: "every README claim maps to a passing test or a command in the demo transcript". §56.1 rows 11/24 route claim checking through `make docs-check`.

**Part II.** §71.1 makes `docs/claims.md` "the single normative registry of externally visible claims", a markdown file with a strict EBNF grammar whose support block is `artifact` + `blake3` + `run` + `gate` + `target` (§71.1 support_f, §71.3). The non-claim allowlist is `docs/claims-nonclaims.toml` (§71.2.4). Part II never mentions `docs/claims.toml`, `make docs-check`, or claim→test-ID mapping, and never says it is replacing them.

**Impact.** An implementer reading Part I builds a TOML registry binding claims to test IDs; Part II's parser requires a markdown registry binding claims to measurement artifacts and gate-ledger entries. Two registries, two gates, two anchor conventions, and a claim that passes `docs-check` can still fail `claims-check`. Support semantics also differ: "a passing test" is not the same evidence as "a fresh artifact hash plus a green gate for this git_sha".

#### Demo expected-output source of truth, and the §54.2 script's own banned phrases

**Part I.** §53.5: `DEMO.md` contains "The section 54 script verbatim, with copy-pasteable commands and expected output excerpts"; §54.3: `demo-verify` = "demo + diff against docs/DEMO.md expected excerpts". The §54.2 script text includes "Minimum cut {...} - ROBUST", "Decisive observation set: {(iam_audit, [09:12,09:52])}, exact, size 1", "false ROBUST verdicts: 0 / 350 cells", and many untagged numerals.

**Part II.** §71.2.1 lists `demo/transcript.expected.txt` as the demo surface; §71.1.1(2) requires every expected line to be prefixed `[CLM-0007]`, stripped by the recorder; G-DEMO-CLAIMS (§71.8) fails "when a transcript line lacks its `[CLM-]` tag or its printed value differs from the live run". BP-11 bans unqualified "minimum cut"; BP-15 bans `\bexact\b` applied to the observation set; BP-08 bans the bare ROBUST token. Part II flags only ECLIPSE §8's header as overridden and never mentions §54.2 or docs/DEMO.md.

**Impact.** An implementer keeps docs/DEMO.md as the golden source and copies the §54.2 script verbatim; claims-check then fails on docs/DEMO.md (it is under `docs/**/*.md`) for BP-08, BP-11 and BP-15, while `demo/transcript.expected.txt` — the file the gate actually reads — is never created. Which file is normative, and whether §54.2's wording is rewritten, is never stated.

#### POLYGLOT.md's hand-maintained language and LOC table

**Part I.** §53.5 requires `POLYGLOT.md` to be a "Table of language -> component -> why this language -> tests -> lines; an explicit 'not used and why' list"; §52.12 requires each language to ship "with a justification line in `POLYGLOT.md`". §51.1(9) requires a "LOC table generated by tokei" in docs/research.md.

**Part II.** §71.7(8): "Do not state a language count from a hand-maintained table. Both figures come from the polyglot mutation audit artifact or they are not stated." BP-14 bans a bare polyglot count and mandates two machine-generated figures, "N languages executing code in CI" and "M configuration formats", from the polyglot mutation audit. Every numeral in the `lines` column is also a QUANT claim candidate needing a CLM record whose artifact contains that exact value (§71.3(6)).

**Impact.** POLYGLOT.md is under `docs/**/*.md` and is therefore a scanned surface. A hand-authored justification table with a lines column fails G-CLAIM-ANCHOR on every LOC value and, if it states or implies a language count, BP-14. Part II never says §53.5's POLYGLOT.md format is superseded, so an implementer writes the hand-maintained table Part II forbids.

#### Publishing redundancy index / decisive-observation-set size / Pareto points for flagged runs

**Part I.** §48.6's row schema always records `decisive_obs_set_size` and `redundancy_index_max` regardless of flags; §50.4(9) says to "Report the fraction of cells resolved by exact search (size <= 3) versus greedy", i.e. greedy-flagged cells still appear in reported aggregates; figure P10 (§50.6) plots "declared cost vs residual reachability Pareto points from the knapsack stage, one series per scenario" with no flag filter; §54.2 T+9:00 shows the Frontier tab's Pareto points.

**Part II.** §71.7(7): "Do not publish the redundancy index, the decisive observation set size, or any Pareto point while the corresponding certificate flag is set. The API omits the field; the UI renders the reason, not a blank."

**Impact.** Part I's figures, RESULTS.md tables and API/UI surfaces would publish exactly the values Part II forbids for flagged runs. An implementer building §50.6/P10 and the §54.2 Frontier tab as specified ships a UI and an API that violate §71.7(7), and must additionally decide how a Pareto figure renders "the reason" instead of a suppressed point.

### RESOLVED

#### Who enforces the "numbers monopoly" and how (§48.1/§48.8 vs §71.0/§71.2)

**Part I.** §48.1(1): the bench harness is the only thing allowed to produce a number that appears in documentation. §48.8(22-24): no human types a number into README.md, RESULTS.md, docs/research.md or the UI; every number is rendered from results.parquet by `scripts/render_numbers.py` into `<!-- BEGIN GENERATED -->` regions, and `scripts/check_generated.py` (CI + pre-commit) fails on a numeric literal outside such a region, with exceptions for code blocks, version strings, and lines ending `<!-- static: <reason> -->`.

**Part II.** §71.0 marks this an explicit override: "§48.1's 'only the benchmark harness produces published numbers' is now enforced by `make claims-check`, not asserted; an unregistered numeral in README.md, docs/, the UI string catalog, the CLI string catalog, the demo transcript, the paper or the release notes fails the build." Enforcement moves to `tools/claimcheck/` with a registry (docs/claims.md), per-sentence CLM anchors, support-hash/run-manifest/gate-ledger freshness (§71.3) and gates G-CLAIM-* (§71.8).

**Impact.** Implementers must build `tools/claimcheck/` and the CLM registry, not just `scripts/check_generated.py`. Note Part II does not say whether check_generated.py is retired, kept as a second gate, or folded in; see the unresolved item on generated regions.

#### "what-if control replay" framing and the GitHub description (§55.1/§53.2 vs §71.0/§71.5)

**Part I.** §55.1 mandates the repo description verbatim: "Deterministic security-state reconstruction, evidence-licensed cut proofs, and what-if control replay. Offline, synthetic data." §53.2(1) requires a README "one-sentence definition"; §53.2(7) calls the flagship "control replay and ECLIPSE".

**Part II.** §71.0: "the product framing 'which control would have prevented the outcome' and the interaction name 'WHAT-IF CONTROL REPLAY' are DELETED from the project." BP-09 makes `what[- ]if control replay` and `would have stopped` hard, unwaivable failures. §71.5 replaces the framing with `docs/framing.toml`: [oneline], [disclaimer], and [interaction_name] = "IN-MODEL CONTROL CUT", generated into every copy and byte-gated by G-FRAMING-VERBATIM.

**Impact.** The §55.1 description string as written is itself a BP-09 banned-phrase hit. It must be replaced by [oneline] (which also exceeds §55.1's "<= 120 chars" limit — see the unresolved README/metadata item). All UI/CLI/doc uses of "what-if control replay" must become "IN-MODEL CONTROL CUT".

#### Bare verdict tokens in rendered text (ECLIPSE §8 / §54.2 demo header vs BP-08)

**Part I.** §54.2's mandated demo screen prints a bare verdict: "Minimum cut {session_binding>=bound, egress_seg>=1} - ROBUST", and later "Banner flips to UNSAFE"; §52.8's acceptance speaks of `mode: ROBUST`.

**Part II.** §71.0: "ECLIPSE §8's demo header prints a bare one-word ROBUST. A bare verdict token is now a banned phrase (71.4, BP-08). Verdicts render only with their scope binding." BP-08 regex `(?<![A-Za-z(])ROBUST(?!\()`; mandated form `ROBUST(rules@<hash8>, catalog@<hash8>, licenses@<hash8>, non-adaptive)`, identically for OPTIMISTIC_ONLY and UNSAFE. §71.5 [verdict_template] is the only authoring site; §71.7(4) forbids concatenating a verdict string and lints the literal "ROBUST" outside the single constructor.

**Impact.** Every verdict rendering in the UI, CLI, demo transcript, README and docs must carry the three hashes plus `non-adaptive`. The override names ECLIPSE §8 only; §54.2's demo header and banner are the same defect and must be rewritten too.

## 72 LLM narration boundary

### UNRESOLVED

#### 72.2.4 declares narration's timeout the only wall-clock budget in SPECTRA, but §20.11 requires one on a decision path

**Tension.** 72.2.4: "timeout_ms is a rendering budget on a non-decision path and is therefore exempt from the determinism charter's ban on wall-clock budgets. Assert that exemption in a comment at the definition site and nowhere else: no other wall-clock budget is permitted anywhere in SPECTRA." But §20.11 (06-graph.md) mandates `max_query_ms = 5_000` in graph.toml, "check them at build time and inside every query loop", and when it binds the query sets `truncated=true` and an entry in `guards_fired` — and §20.11 rule 2 says "A run whose graph build fired a cap must set grounding_capped in the ECLIPSE certificate flags, and a flagged run may never be presented as ROBUST". §20.12 adds measured time budgets that fail CI ("medium fixture under 8 s, whole-graph reachability sweep of 256 cuts under 3 s"), and §21.3 adds "under 15 minutes" for training. Part II's blanket sentence outlaws all of these and names none of them.

**Decision needed.** Decide whether (a) 72.2.4's sentence is narrowed to 'no other wall-clock budget may exist on a path that produces a decision or an artifact', leaving §20.12/§21.3 CI timing assertions alone, and (b) whether §20.11's max_query_ms survives at all — it is a genuine determinism hole independent of §72, because a slow machine changes truncated/guards_fired, which changes grounding_capped, which changes whether a run may be presented as ROBUST. If it is removed, §20.11 needs a deterministic replacement bound (e.g. an edge-visit or expansion counter) so queries are still bounded.

**Recommended.** Narrow 72.2.4 to non-decision paths explicitly, and replace §20.11's max_query_ms with a deterministic work counter (visited-edge budget) that fires the same guards_fired/truncated machinery. Keep §20.12/§21.3 as CI performance assertions, not runtime budgets, and say so in both places.

#### Three different narration kill-switches; Part II does not say which survives

**Tension.** Part I §2.3.2 (01-preamble.md) mandates a CI job `no-llm` running with `SPECTRA_LLM=disabled` and network namespaces cut; the make-target table defines `make no-llm` (<12 min) and `make audit-llm` (<30 s), and `make verify` is defined as lint + test + gates + audit-scope + audit-stubs + audit-llm; the milestone checklist requires "make no-llm is green" and "make audit-scope, audit-stubs, audit-llm, docs-check are green". Part I §11 (11-api.md) mentions a third name, `SPECTRA_LLM_NARRATION`. Part II 72.12 introduces `make verify-no-llm` driven by `SPECTRA_NARRATION_LLM=0`, run "on every push", and never mentions no-llm, audit-llm, SPECTRA_LLM or the composition of `make verify`. Compounding it, 72.3.1 says the narrator "never reads... environment variables" while 72.12.1 controls it with one.

**Decision needed.** State whether `make verify-no-llm` replaces `make no-llm` (and whether `make verify` still contains `audit-llm`, given that gate's grep target no longer exists under Part II's layout), and collapse SPECTRA_LLM / SPECTRA_LLM_NARRATION / SPECTRA_NARRATION_LLM to one canonical name. Also clarify which process reads that env var — the make/CI layer or the narrator itself, since 72.3.1 forbids the latter.

**Recommended.** Make `verify-no-llm` the single successor to `no-llm`, retire `audit-llm` in favour of 72.12.2's build-graph assertion, standardise on SPECTRA_NARRATION_LLM, and state that it is consumed by the build/CI layer only (the narrator's own switch is the Cargo feature plus narration.toml).

#### May narration state the verdict?

**Tension.** Part I §21.10.3 (06-graph.md) has the validator reject narration that "asserts a verdict other than the exact `mode` field in the certificate" — which presupposes that restating the certificate's own mode is permitted, and the worked example is headed "cert.json mode=ROBUST". Part II's ClaimKind is a closed enum — "pub enum ClaimKind { Scope, Step, Cut, Blindness, Flag, Limitation }" (72.4.1) — with no verdict kind, 72.6.3's mandatory Scope claim never names the verdict, and 72.11.1(6) says "The frontend computes no verdict and displays no narration-derived verdict text."

**Decision needed.** Decide whether narration may contain a sentence naming the certificate verdict. If yes, add a Verdict ClaimKind with a Structural evidence pointer at the cert's mode field and a template that substitutes it byte-identically. If no, strike §21.10.3's verdict clause and state plainly that the verdict appears only in the certificate header, never in narrated text.

**Recommended.** Add `Verdict` as a seventh ClaimKind rendered as a Structural claim pointing at /mode, placed immediately after Scope and never paraphrased. It keeps 72.0's rule (asserts nothing the certificate does not assert) while preserving the one sentence readers most expect.

#### The closed relation table cannot express the state-graph transitions Part I tells narration to narrate

**Tension.** Part I §2.3.3 (01-preamble.md) permits the LLM to "turn a certificate, a transition chain or a corridor set into prose", and §20.3 (06-graph.md) defines the transition vocabulary: AUTHENTICATED_AS, PRESENTED, BOUND_TO, ASSUMED, GRANTED, ESCALATED_TO, EXERCISED, SPAWNED, CONNECTED, TOUCHED, IMPERSONATED, TRANSITIONED and eight more. Part II 72.6.1 closes the narrator's relation vocabulary to eight certificate-level relations (rel.derives, rel.blocked_by, rel.evidenced_by, rel.licensed_by, rel.reaches, rel.in_cut, rel.premium, rel.flagged) and 72.6.2 puts "escalated to", "pivoted to" and "compromised" on the forbidden-verb list enforced by narr.no_causal_verbs. Nothing in §72 maps a graph edge type to a narratable relation, and 72.3.1 forbids reading the graph anyway.

**Decision needed.** Decide whether narration describes the attack chain at all. If yes, the certificate must carry the step's edge type as a first-class field and 72.6.1's table must gain a licensed entry per permitted edge type (with an observed verb and a GHOST verb each), plus an explicit carve-out so the edge-type identifier ESCALATED_TO is not caught by the forbidden-verb scan. If no, §2.3.3's "transition chain" clause must be struck so implementers stop expecting chain prose.

**Recommended.** Keep the closed table but extend it with one entry per certificate-representable step type, sourced from a `step_kind` field on the cert's derivation steps rather than from the graph; scope the forbidden-verb scan to lowercase prose tokens so uppercase edge-type identifiers in slot substitutions are unaffected.

#### G20.7 forbids any counter anywhere including a GHOST, but 72.8's narration footer counts GHOST claims

**Tension.** §20.16 G20.7 (06-graph.md): "Ghost isolation: no observed count, timeline, or metric anywhere in the codebase includes a GHOST node or edge. Enforced by a test that injects a sentinel ghost into every fixture and asserts all published counters are unchanged." Part II 72.8's transcript prints "claims=4" over a list in which c0002 is a GHOST claim, and 72.4.4 carves out only "every observed-event count". Part II never mentions G20.7. Under G20.7's sentinel test, injecting one ghost into a fixture changes the narration claim count from N to N+1 and the gate goes red.

**Decision needed.** Decide whether the narration claim count (and 72.7.3's withheld-claim count, and the graph_meta ghost_nodes/ghost_edges columns of §20.7, which are also counters that count ghosts) fall under G20.7, or whether G20.7 means only 'no counter presents a ghost as observed'. Then reword one side: either narration prints observed and ghost claim counts separately (claims=3 +1 ghost), or G20.7 is restated as a presentation rule rather than a blanket counter rule.

**Recommended.** Reword G20.7 to "no counter, timeline or metric presents a GHOST as observed, and any counter that includes ghosts must report the ghost count separately", and change 72.8's footer to `claims=3 ghost=1`. That keeps the sentinel test meaningful and makes §20.7's existing ghost_nodes/ghost_edges columns legal by the same rule.

### SILENT

#### Model transport: Ollama HTTP service vs in-process llama.cpp + GGUF blob

**Part I.** §21.10 (06-graph.md), `config/llm.toml`: provider = "ollama", endpoint = "http://ollama:11434", model = "llama3.1:8b-instruct-q4_K_M"; requirement 2: "No network beyond the local Ollama container in the compose network." G21.8 runs the suite "with the `llm` package deleted from the image".

**Part II.** 72.1.1: "one local... model executed by a vendored llama.cpp build against a single GGUF blob", pinned by narration/model.lock with a blake3 and runtime_rev. 72.3.2: "The crate's dependency list contains no database driver, no HTTP client, no socket crate. A cargo deny-style allowlist gate fails the build if one appears." 72.1.4 runs the narrator with no network namespace at all.

**Impact.** Directly incompatible and nowhere marked as an override. An implementer building Part I's design ships an HTTP client to reach ollama:11434; that fails Part II's dependency allowlist gate at build time and cannot work under network_mode: none at runtime. The Ollama compose service, its pinned image and its model tag all have to be deleted, and nothing in Part II says so.

#### Permitted narration inputs shrink from nine structures to exactly one cert.json

**Part I.** §21.10 (06-graph.md) permits the narrator to consume "the certificate JSON, the cut, the corridor list, the counterexample derivation trees, the license list, the blindness premium, the state timeline, the provenance subgraph, the degradation table". The state timeline and provenance subgraph are graph-engine outputs (§20.9 `state_timeline`, `provenance_subgraph`, returned as QueryResult envelopes), and the degradation table is §19's matrix — none of them live inside cert.json.

**Part II.** 72.3.1: "The narrator's universe of discourse is one canonical cert.json. It never reads bundle.jsonl, raw or parsed events, liveness.json, rules.toml, controls.toml, the fact base, the hypergraph, Postgres... There is no code path that opens a second input." 72.3.2 enforces it with a single positional CLI argument, a read-only rootfs and a filesystem tracer that fails on any path outside {certificate, model blob, /tmp}.

**Impact.** Six of Part I's nine permitted inputs are silently withdrawn. 72.3.3's override notice covers only how certificate content reaches the prompt, not which artifacts the narrator may open. An implementer who wires `state_timeline()` or the degradation table into the narrator (as Part I explicitly authorises) trips the filesystem-tracer test and the Postgres-driver dependency gate. Anything Part I expected narration to say about state transitions or degradation is now unsourceable.

#### Configuration surface: config/llm.toml vs narration.toml + narration/model.lock

**Part I.** §21.10 (06-graph.md) commits `config/llm.toml` with `[llm]` keys enabled=false, provider, endpoint, model, temperature=0.0, seed=7, max_output_chars=4000, timeout_seconds=30, cache=true ("keyed by blake3(canonical input JSON)").

**Part II.** 72.2.2 commits `narration.toml` with `[narration] enabled=true, max_claims=64, max_chars_total=6000` and `[narration.llm] enabled=false, model_lock, max_tokens_claim=48, timeout_ms=4000, on_violation, on_timeout`, plus `narration/model.lock` (72.1.2). 72.2.3: "A CI lint asserts the committed default of narration.llm.enabled is false and that the Cargo feature is not in default = [...]".

**Impact.** Two different config files, key paths, and budget values (4000 chars vs 6000; 30 s vs 4 s), with no override note. A repo built to Part I has no `narration.llm.enabled` literal, so Part II's CI lint fails on a correct-per-Part-I tree; a repo built to Part II has no `config/llm.toml`, so any Part I-derived loader or doc reference dangles. Part I's `cache` and `seed` keys have no Part II home at all.

#### Where narration code lives, and in what language

**Part I.** §2.3.6 (01-preamble.md): "Any function that calls a model lives under `spectra/narration/` and nowhere else. A CI grep gate fails the build if a model client is imported outside that package" — operationalised as `make audit-llm` ("fail if a model client is imported outside spectra/narration/"), which is a component of `make verify`. §21.10.4 (06-graph.md) puts the deterministic renderer in Python Jinja2 at `llm/templates/*.j2`; G21.0 runs a CI job with "`ml/` and `llm/` both deleted"; G21.8 deletes "the `llm` package".

**Part II.** 72.0 and 72.3.2 make narration two Rust binaries, `spectra-narrate` and `spectra-narrate-llm`, behind Cargo feature `narrate-llm`; 72.7.1 puts templates at `narration/templates/*.tmpl` expanded by pure Rust; 72.12.1 disables the model path with `cargo build --no-default-features --features core`.

**Impact.** Unmarked relocation across languages and directories. `make audit-llm` as specified (grep for a model client outside `spectra/narration/`) fails permanently once the inference code is in a Rust crate, and Part I's §2.3.6 wording forbids it being there. G21.0's second job and G21.8 both key on a `llm/` directory that Part II's layout never creates, so both gates become unsatisfiable rather than green. Part I §21.10.4 also names Jinja2 as the default renderer, which Part II replaces with printf-class Rust templates.

#### Validator rejection handling: retry-once vs single-shot fallback

**Part I.** §21.10.3 (06-graph.md): "On rejection, retry once at the same seed; on second rejection, fall back to the deterministic template renderer and record `narration: template_fallback` in the run log."

**Part II.** 72.9.3(4): "any surface failing 72.5.3 causes fallback to stage 0 with fallback_reason = ValidatorRejected, recorded in generator." No retry exists; 72.2.2's `on_violation` is "fallback | fail ; never 'emit'". 72.1.5 fixes decoding to temperature 0, greedy, top_k=1, fixed seed, so a retry at the same seed is bit-identical by construction.

**Impact.** Small but concrete: an implementer following Part I writes a retry loop that can never change the outcome, doubles worst-case latency against the 4 s budget, and records `template_fallback` in the run log instead of the typed `FallbackReason::ValidatorRejected` that 72.4.1 and gate narr.* expect.

#### The mandated UI panel label differs verbatim

**Part I.** §21.10.5 (06-graph.md): narration "is rendered in the UI inside a panel labelled 'Generated narration — derived from the certificate above; not evidence.' The certificate itself is always displayed next to it." No collapse requirement.

**Part II.** 72.11.2: "The narration panel is labeled 'Generated narration — not part of the proof', is collapsed by default, and carries a persistent badge reading LLM PARAPHRASE whenever generator.mode == LlmParaphrase." Screenshot tests cover four modes.

**Impact.** Two different exact strings are each mandated. Part I §21.8's forbidden-string lint (`scripts/lint_forbidden_strings.sh`) and any copy test written against Part I's literal will not match Part II's panel, and vice versa. Part II also never restates Part I's "certificate is always displayed next to it" requirement while adding collapse-by-default.

#### Part I's worked narration example is unproducible under Part II's grammar

**Part I.** §21.10 (06-graph.md) presents a paragraph as "the only acceptable shape of output": "The minimum cut for this scenario contains two controls: session binding at level 1 and egress segmentation at level 1. Six irreducible corridors were enumerated, and no cut of size one satisfies the corridor clause set, so the lower bound of two is attained... it is required because the iam_audit source was blind between t1 and t2..."

**Part II.** 72.5.2's GBNF "admits no digit, no capital-letter identifier, no URL, no backtick... no newline"; 72.5.3 requires `surface` to match `^[a-z ,.;:'()\-<>]*$` with "zero characters in [0-9]" pre-substitution and every word drawn from a committed closed lexicon; 72.5.4 forbids "counts computed by the narrator" and "arithmetic of any kind"; 72.6.2 forbids "because" and "so that". 72.8's CLI transcript shows the actual permitted shape: one short slotted sentence per claim.

**Impact.** An implementer treating Part I's paragraph as the acceptance target builds a narrator whose every output is rejected by the validator: the spelled-out counts ("two controls", "Six", "size one"), the derived assertion that "the lower bound of two is attained", and the causal "because"/"so" are each independently fatal. Part II never retracts the example.

#### What is persisted per narration, and under what key

**Part I.** §21.10.5 (06-graph.md): "Every narration is persisted with {llm_enabled, provider, model, digest, temperature, seed, input_hash, output_hash, validator_result}"; §21.10's config caches "keyed by blake3(canonical input JSON)".

**Part II.** 72.11.1(7): narration "is written to the content-addressed blob store keyed by (cert_hash, narration_version, generator.mode), and Postgres holds at most a pointer". The only recorded provenance is 72.4.1's `Generator { mode, model_id, model_blake3, fallback_reason }`.

**Impact.** Unmarked replacement of both the record shape and the key. Part I's provider/temperature/seed/validator_result fields have no Part II type to live in. More seriously, Part II's key omits model identity, so two different GGUF blobs (or the same blob at two runtime_revs) paraphrasing the same certificate collide on one blob-store key — the second write either silently shadows the first or is silently dropped, and `generator.model_blake3` inside the blob then disagrees with what a reader expected.

#### Narration excluded from every test assertion vs 19 build-failing narration gates

**Part I.** §2.3.4 (01-preamble.md): "Every LLM-produced string is tagged in the data model as provenance: 'narration', is visually marked in the UI, and is excluded from every test assertion, metric and certificate hash."

**Part II.** 72.10 specifies nineteen `narr.*` tests as "build-failing tests" asserting over narration content (surface text, claim order, evidence sets, byte-equality of narration.json across injection fixture pairs), of which only four are quarantined to the nightly job; the other fifteen run per-PR. 72.11.1(3) separately says "No gate consumes narrated text."

**Impact.** An implementer obeying Part I §2.3.4 writes no assertions over narrated strings and therefore ships none of narr.no_causal_verbs, narr.ghost_marked, narr.scope_first, narr.injection_pairs, etc. — losing the entire enforcement layer §72 depends on. Part II never says §2.3.4's "excluded from every test assertion" is narrowed to "excluded from every gate that decides a verdict".

#### Narration and the determinism / reproduction contract

**Part I.** §2.4.1 (01-preamble.md): "Same inputs + same seed + same version ⇒ byte-identical outputs. Enforce with `make reproduce`, which runs the full pipeline twice in fresh containers and diffs artifact hashes." §21.10's config pins temperature 0.0 and seed 7, i.e. narration is treated as a reproducible artifact.

**Part II.** 72.11.1(8): "Reproduction (`make reproduce`) does not regenerate narration and no figure or table in docs/ derives from it." 72.13.5 forbids claiming "that narration is deterministic across hardware. It is not relied upon to be... stage 1 is excluded from every determinism claim." 72.1.5 explicitly says fixed decoding exists for content control, "not reproducibility of the text (which is never relied upon)".

**Impact.** Unmarked carve-out from the determinism charter. An implementer following Part I adds narration.json to the artifact set that `make reproduce` diffs; on any hardware or BLAS difference in llama.cpp that diff goes red and looks like a kernel determinism regression. Conversely, Part I's committed `seed = 7` implies a guarantee Part II forbids stating.

#### GHOST items interleaved in one list vs returned in a separate list

**Part I.** §20.2 (06-graph.md): GHOST nodes "must never appear in any count, aggregate, or timeline rendered as observed. Every query returns ghost nodes in a separate list, never merged into the observed list", mirrored by §20.8's `QueryResult.ghost_results` ("never merged with results").

**Part II.** 72.4.3/72.8 render GHOST claims inline in a single ordered claim list, distinguished by a `[GHOST]` prefix and styling — the CLI transcript shows c0002 (GHOST) sitting between c0001 and c0003 in one sequence, and 72.4.4 excludes GHOST only from "every observed-event count".

**Impact.** Part I's separation rule is structural (two lists); Part II's is typographic (one list, marked). An implementer who applies §20.2's rule to the narration panel emits two blocks and breaks 72.10's narr.scope_first / paraphrase-equivalence ordering assumptions; one who follows Part II ships a merged list that a reviewer citing §20.2 will reject. See also the unresolved G20.7 counter question.

### RESOLVED

#### Narration gets an owner, an interface and a gate (72.0)

**Part I.** Part I states the constraint only as prose: §2.3.3 (01-preamble.md) "LLMs may only narrate structures that were already computed deterministically... Narration is a leaf, never an input", and §21.10 (06-graph.md) "The LLM narrates. It does not decide, detect, rank, infer, or fill gaps." No projection function, no output type, no validator contract, no build-graph enforcement.

**Part II.** 72.0 marks itself "OVERRIDES Part I: Part I named no owner for LLM narration anywhere in sections 0-56... This section is that owner. Where any Part I section, demo script or UI copy implies narrated text may assert a step, a relation, a time or a number, this section overrides it: narrated text asserts nothing that the certificate does not already assert." It mandates a two-stage design (deterministic renderer always on, model paraphrase off by default), a projection P, a validator V, a substitution S, and build-graph enforcement (72.12.2).

**Impact.** Correctly flagged. Everything downstream in §72 inherits this override, including the pieces that Part I stated differently.

#### What the model is allowed to see (72.3.3)

**Part I.** §21.10 (06-graph.md): "Permitted inputs: ONLY already-computed deterministic structures — the certificate JSON, the cut, the corridor list, the counterexample derivation trees, the license list, the blindness premium, the state timeline, the provenance subgraph, the degradation table", and §21.10.3 has the model receive "a rendered, closed input document" whose tokens the validator then checks by "exact string membership check against an extracted token set" — i.e. real entity names, EventIds and numbers are in the prompt.

**Part II.** 72.3.3: "OVERRIDES Part I: any Part I phrasing suggesting narration 'consumes the certificate JSON' is narrowed here — passing raw certificate JSON to a model would place attacker-controlled telemetry strings into the prompt, which 72.9 forbids." P emits into the prompt ONLY claim kind, template id, relation id and slot placeholder names; no EventId text, no entity name, no numeral, no hash.

**Impact.** Marked. Note the override is worded to cover only the phrase "consumes the certificate JSON" — it does not cover the six non-certificate inputs Part I also permits (see the SILENT finding on permitted inputs).

#### The flagship "would have prevented" sentence is unsayable by the narrator (72.6.2)

**Part I.** §2.2 core question (01-preamble.md, line 220): "...which minimal set of controls would have prevented the outcome under every hypothesis the missing telemetry admits?", and the one-line pitch at line 188 "proves which minimal set of controls would have severed the attack chain".

**Part II.** 72.6.2: "OVERRIDES Part I: the flagship copy 'which control would have prevented the outcome' is not sayable by the narrator; the permitted form is 'severs this chain in the model under this catalog'." Plus a closed forbidden-verb list ("caused", "led to", "because", "therefore", "so that", "escalated to", "compromised"...) enforced by validator and by gate narr.no_causal_verbs.

**Impact.** Marked. Scoped explicitly to the narrator, so Part I's README/positioning copy is untouched — an implementer should not "fix" the preamble, only the narrated surface.

#### Narrator network isolation is tested, not declared (72.1.4)

**Part I.** §2.7 (01-preamble.md): "The lab runs in Docker Compose on an isolated bridge network with egress disabled by default; a CI test asserts that the compose network has no route out" — i.e. isolation is a property of the lab network, and services inside it may talk to each other.

**Part II.** 72.1.4: "Run the narrator process with the network unavailable, not merely unused: Linux — unshare -rn, or a compose service with network_mode: none... OVERRIDES Part I: §26.1-style isolation is not satisfied by policy text; the narrator's isolation is tested, like the range's." A CI job attempts DNS/TCP/ICMP egress from inside the narrator container and fails the build if any succeeds.

**Impact.** Marked (though the override names §26.1, not §2.7). Consequence the override does not spell out: a narrator in a `network_mode: none` namespace cannot reach a sibling container — which is exactly how Part I §21.10 wires the model. See the SILENT Ollama finding.

## 73 Polyglot tiers

### UNRESOLVED

#### JavaScript is a mandated Part I language with no place in Part II's roster of exactly 32

**Tension.** §31.4 mandates JavaScript as a first-class language: `web/standalone/verify.mjs` ("a zero-build, zero-dependency ES-module page … verifies a certificate from `file://` with no server, no bundler and no network") and `tools/js/canonicalize.mjs` ("a Node implementation of RFC 8785 JSON canonicalization used in CI to confirm the Rust and Python canonicalizers produce identical bytes"), with CI job `lang-javascript` and a `differential_oracle` mutation test. §73.1 enumerates the roster as "Authored executing languages: 32" and the four tier tables list exactly 32 — JavaScript appears in none of them. §73.4 then requires that "Every file in the tree whose extension maps to an executing language must be matched by exactly one component's `paths` — unmatched files fail `ORPHAN_SOURCE`." Part II never mentions JavaScript, so it is impossible to tell whether it was dropped deliberately (consistent with §73.1's Tier D removal of the in-browser verifier) or overlooked.

**Decision needed.** Decide whether JavaScript is a 33rd executing language with its own `polyglot.toml` component and tier, or whether §31.4's standalone verifier and Node canonicalizer are deleted. If deleted, name the replacement owner of the RFC 8785 cross-canonicalizer check, which §31.4 makes the only gate proving Rust and Python produce identical preimage bytes.

**Recommended.** Keep JavaScript as a Tier B component owning `tools/js/canonicalize.mjs` only (consumer: the canonicalization differential gate; mutation: `constant_result`), and delete `web/standalone/verify.mjs` along with the client-side verdict path §73.1 already removes. That makes the count 33 executing / 11 config / 44 bar rows and requires the §73.1 and §73.7 numbers to be restated.

#### No component owns `state_table.json` or the control-lattice antitonicity oracle

**Tension.** §31.13 makes F# emit "the canonical `artifacts/state_table.json` (states, legal transitions, guards, dimension tags) that Python's engine and the Rust kernel both load rather than hard-coding", with a regeneration gate and a downstream Python gate; §31.28 generates the Verilog `casez` from the same table; §32.6 separately calls F# the "FsCheck model of the control lattice; antitonicity oracle", and §32.8's `tests/gates/` lists antitonicity as a required section-7 gate. §73.1 reassigns F# to the Pareto frontier knapsack and lists no owner for either the state table or the antitonicity oracle. Under §73.3.1 every component needs a named consumer, so this is not a silent renaming — the consumers (`python/`, `rust/`, the Verilog generator) remain and their producer is gone.

**Decision needed.** Decide whether `artifacts/state_table.json` still exists, and if so which component generates it and in which tier — or declare that the state machine is hard-coded in Rust/Python and strike §31.13's regeneration gate, §31.28's table-driven `casez` and §32.8's antitonicity gate from the spec.

**Recommended.** Give F# two components in `polyglot.toml` (`state-table-fsharp`, Tier A by §73.1's "deleting this deletes SPECTRA" test since Python and Rust load its output, and `frontier-fsharp`, Tier D), rather than reassigning the language wholesale.

#### No component owns the brute-force Ψ-minimality cross-check

**Tension.** §31.26 gives Julia "a brute-force minimum-cardinality hitting set over Ψ for `|A| ≤ 20` fixtures" whose "optimum must equal the kernel's `|S_opt|` and `|S_rob|`", plus a mutation gate that perturbs the kernel's popcount ordering. This is the only independent check in Part I that the kernel's cut is actually minimal. §73.1 reassigns Julia to re-implementing R's median/IQR/bootstrap statistics and names no owner for the hitting-set check. §73.1 also constrains the Haskell oracle to "the admissibility relation and guard evaluation **only**", failing with `TIER_B_SCOPE_CREEP` if it touches "the hitting-set loop" — so Haskell cannot absorb it either.

**Decision needed.** Decide which component performs the brute-force Ψ-minimality agreement check, or record explicitly that minimality is now attested only by the Go checker's single linear pass (§31.6) and accept the loss of an independent optimality oracle.

**Recommended.** Add a second Julia component (`hitting-set-bruteforce-julia`, Tier B, `constant_result` mutation) rather than dropping the check; §73.5's rule that `constant_result` is mandatory for every Tier B oracle applies cleanly to it.

#### The MATLAB ban collides with Part I-mandated directory and job names

**Tension.** §73.1 fails the build with `BANNED_MATLAB_MENTION` "on any match of `/\bMATLAB\b/i` outside this paragraph's own file" (and §73.12.5 names that file as `docs/polyglot/octave-not-matlab.md`). But the OVERRIDES marker covers only "the target language set's inclusion of MATLAB", while Part I independently mandates the token in several non-prose places: §32.6's `polyglot/matlab/liveness_ref/` directory, §31.25's `analysis/matlab/` directory and CI job `lang-matlab`, §31.46's `.gitattributes` line `analysis/matlab/**/*.m linguist-language=MATLAB` together with honesty rule 4's assertion that those files are MATLAB, and §33.6's `.tool-versions` comment `octave 9.2.0 # MATLAB-compatible reference path`. Part II does not say whether the gate scans paths, `.gitattributes` and pinned-version comments, nor mandate the renames.

**Decision needed.** Fix the exact scope of `BANNED_MATLAB_MENTION` (file contents only, or paths and filenames too), and mandate the renames it implies: `polyglot/matlab/` → `octave/`, job `lang-matlab` → an Octave name, removal of the `linguist-language=MATLAB` override and of the `.tool-versions` comment.

**Recommended.** Scan paths as well as contents — a directory named `matlab/` is exactly the implication §73.1 says must not exist — and add the renames to §73.12's done criteria so the gate is satisfiable rather than permanently red.

#### XML and HCL carry load-bearing evidence in Part I but are outside Part II's roster

**Tension.** §30.2 lists "XML(SAML)" and "HCL(segmentation topology)" as Tier 3 observed-lab languages, and Part I makes both genuinely load-bearing: §31.41 says the SAML `AuthnContextClassRef` element "is the federated-identity telemetry source and the evidence that makes the `mfa` control's levels distinguishable", with an XXE-rejection gate; §31.43 says "The Terraform state is *parsed by SPECTRA* to derive the ground-truth network segmentation used by the `network_segmentation` control", with a topology-consistency gate that fails if declared and simulated segmentation drift. §73.2 reclassifies both as "configuration and markup … **not languages doing a job** for counting purposes", which puts them outside the §73.1 roster and therefore outside §73.3's four load-bearing checks — no consumer edge, no mutation, no declared role. §73.4's `ORPHAN_SOURCE` lint also covers only "executing language" extensions, so nothing notices.

**Decision needed.** Decide whether a config/markup format that supplies evidence (SAML assertions, Terraform topology) must still carry a `polyglot.toml` component with a consumer edge and a mutation, even though it is excluded from the prose count. As written, the two most consequential non-executing inputs to the control lattice are the only inputs with no load-bearing proof.

**Recommended.** Separate the counting question from the auditing question: keep §73.2's ban on counting these in prose, but require manifest components for any format that produces facts the kernel grounds over, so a `flip_byte` on a SAML fixture or a `truncate_output_fields` on the Terraform plan turns a named gate red.

#### The held-out Tier C language cannot satisfy "manifest entry before the first source file"

**Tension.** §73.1's held-out language rule requires that "exactly one Tier C component is authored *after* `rules.toml` and `axioms/` are frozen and hash-pinned", with the choice recorded in `docs/research/preregistration.md` "before it is written". §73.11 simultaneously requires: "Do not add a language without a `polyglot.toml` entry that passes all four load-bearing checks before the first source file is committed", and §30.1.1/§30.3.2 require the reason written and the entry declared before the code. A component that does not yet exist cannot have a verified consumer edge (§73.3.1), an executing CI job (§73.3.2), or a mutation run proving a named gate goes RED (§73.3.3). §30.4.4 additionally fails `lang-audit` on "a component with no demo ring", which the held-out component cannot have until after the freeze.

**Decision needed.** Define the manifest state of a pre-registered but unwritten held-out component: a declared-but-exempt status with an explicit deadline, or an ordering in which the freeze happens early enough that the component is authored and audited before any gate runs. Also state whether the held-out component's audit failure blocks a milestone or only a tagged release under §73.9.

**Recommended.** Add a `status = "preregistered"` value to `polyglot.toml` that suppresses the four checks and the demo-ring check until a named milestone, and make an expired `preregistered` status a PADDING verdict, so the exemption cannot become permanent.

#### Two deletion ledgers with incompatible rules

**Tension.** §30.4.2 requires that a deleted component's removal be recorded in `docs/ADR/`, and §32.2 specifies ADRs as "one decision per file, immutable once merged" — an ADR by construction argues for the decision. §73.6 requires deletions in `docs/polyglot/deleted.md` "with the date, the mutation that exposed them and the commit that removed them", and states "That file is a ledger, not a defence; it contains no argument for why the language was a good idea." §73.12.4 makes the existence of `docs/polyglot/deleted.md` "even if empty, with its ledger schema in place" a done criterion. Part II never retires the ADR requirement.

**Decision needed.** Decide whether a language deletion produces an ADR, a ledger row, or both — and if both, which one the release gate reads and whether the ADR's rationale prose violates §73.6's "no argument" rule and §73.0's demotion of prose rationale.

**Recommended.** Keep both with distinct jobs: the ledger row is machine-read by `make polyglot-audit` and carries only date, mutation and commit; the ADR is optional prose that may not be cited by any gate, consistent with §73.0's demotion.

### SILENT

#### The string "eclipse" is banned from every machine-readable surface

**Part I.** §31.5 mandates crates `eclipse-kernel`, `eclipse-rulegen`, `eclipse-verifier-wasm`; §32.4 mandates `rust/eclipse-core/`, `eclipse-rules/`, `eclipse-cut/`, `eclipse-liveness/`, `eclipse-cert/`; §32.3 `python/spectra_eclipse/`; §32.6 `haskell/eclipse-ref/`; §32.2 `docs/eclipse/`; §31.4 loads the file `eclipse_verifier.wasm`; §34.2 mandates `config/defaults/eclipse.toml` with keys `eclipse.atom_limit`, `eclipse.corridor_cap` and the env override `SPECTRA__ECLIPSE__CORRIDOR_CAP`.

**Part II.** §73.10.2: "The string `eclipse` appears in **no machine-readable surface**: not as a crate, module, package or directory name; not as a binary on PATH; not as an HTTP path segment; not as a JSON field name, a file extension or magic bytes in any certificate. The kernel crate is `spectra-kernel` … A grep gate enforces this with `ECLIPSE_IN_ARTIFACT_SURFACE`." Presented as a "DECISION", with no OVERRIDES marker.

**Impact.** An implementer who builds Part I's repository cannot pass the §73.10 grep gate: roughly ten mandated crate names, two directory names, one shipped wasm filename, one config file and three config/env key paths all contain `eclipse`. §73.12.6 makes "no machine-readable surface contains the string `eclipse`" a done criterion, so Part I's §32.4 workspace layout is unbuildable as specified.

#### WebAssembly is no longer the in-browser verifier

**Part I.** §31.30: WebAssembly is "the checking half of ECLIPSE compiled to `wasm32-unknown-unknown` — closure check, goal exclusion, license validation, witness re-derivation and Ψ minimality — running entirely in the browser", DEMO_PATH, with a "three-way verdict agreement gate" (wasm = native Rust = Go) and a 1.5 MB size budget. §31.4's standalone `verify.html` loads it and verifies a certificate from `file://`. §32.4 mandates the `spectra-wasm` crate, §32.7 `web/packages/wasm`.

**Part II.** §73.1 Tier D: WebAssembly is a "hand-authored `.wat` canonical-preimage encoder" that "lets the browser re-derive a certificate's content address offline; it does **not** compute or verify any verdict", with a test asserting the module "exports exactly one function". The Tier D negative requirements add: "Rust-to-wasm and any other compiled output is a **build target, not an authored language**. It is excluded from the roster, excluded from the count, and marked `linguist-generated=true`."

**Impact.** Part II asserts "Part I's frontend invariant stands: the verdict is never computed client-side" — but that invariant is §32.7's rule for the React console, and §31.30/§31.4 explicitly do compute the verdict client-side as the project's headline portability claim. An implementer reading Part I alone builds a wasm verifier that Part II forbids; one reading Part II alone deletes the standalone verifier, the three-way agreement gate and the demo's final beat without ever being told that is a change.

#### Solidity: notary vs. estate source class

**Part I.** §31.27: the Solidity fixture "provides a telemetry source with properties no other source has — an append-only, totally ordered, cryptographically sequenced log that cannot be suppressed. That makes it the control case in the tampering study: the one source where SUPPRESSED is provably impossible", and the demo "shows one blind window on `iam_audit` and zero possible blind windows on `chain_authz`". §32.6 goes further: `solidity/anchor/ OPTIONAL local-chain append-only certificate anchor registry`.

**Part II.** §73.1 Tier D negative requirement: "Solidity provides **no** security property that the BLAKE3 sequence chain does not already provide for SPECTRA's own artifacts. It is an estate source class, not a notary … Forbidden claims: 'blockchain-anchored', 'immutable audit anchor', 'tamper-proof certificates'. No SPECTRA certificate, hash or verdict is ever written to a chain." §73.11 repeats the ban. No OVERRIDES marker.

**Impact.** §32.6's certificate anchor registry is exactly the artifact §73.1 says must not exist. §31.27's "zero possible blind windows / SUPPRESSED provably impossible" demo line is exactly the claim §73.11 forbids. An implementer following Part I ships a component and a demo beat that the claims gate will reject.

#### Verilog/VHDL model a different thing entirely

**Part I.** §31.28: Verilog is "the security state machine as synthesizable RTL — a Moore FSM … with an `illegal_transition` output", built with `iverilog` plus "`yosys -p synth` as an elaboration sanity check", gated on "hw/sw illegal-transition agreement: 1,204/1,204". §31.29: VHDL is "a hardware liveness monitor" asserting `blind` on q99 inter-arrival overrun, a `differential_oracle` against the Rust liveness pass. §32.6 describes both as an "RTL model of the unit-propagation counter datapath".

**Part II.** §73.1 Tier D: Verilog is a "bounded FIFO log sink, simulated" that "generates a loss trace with exact drop ground truth"; VHDL is "independently authored same FIFO" as its differential partner. §73.1 negative: "The Verilog/VHDL FIFOs model a lossy buffer. They do not model any real logging appliance." §73.11: "Do not claim 'hardware-accelerated', 'FPGA', 'silicon' or 'RTL-verified' from Verilog or VHDL."

**Impact.** Three mutually exclusive component definitions exist across the spec (security FSM, unit-propagation datapath, bounded FIFO) and Part II does not say it is replacing either Part I version. §31.28's mandated `yosys` synthesis step and the state-table-derived `casez` generator have no counterpart in Part II, and the liveness differential oracle in §31.29 silently loses its owner.

#### Swift and Objective-C are Apple-platform components in Part I and Linux-only in Part II

**Part I.** §31.21: Swift is an "iOS session-telemetry fixture generator — app foreground/background transitions … jailbreak-check outcome, device-attestation result". §31.22: Objective-C is an "`mobile/ios-keychain-shim/`" emitting "keychain-shaped events" because "keychain APIs are Objective-C". §32.6 names them `swift/macshim/ macOS endpoint telemetry shim` and `objc/macshim-compat/ older CoreFoundation collection path`.

**Part II.** §73.1 Tier C: Swift is a "Linux-hosted session service" and Objective-C a "legacy agent (clang + GNUstep on Linux)". Honesty clauses that must appear in `docs/polyglot/tier-c.md`: "Objective-C is compiled with clang against GNUstep on Linux. It is not an Apple platform agent and no document may imply macOS or iOS telemetry. Swift is the open-source Linux toolchain. Same clause." §73.11 repeats the ban.

**Impact.** Part I's component names (`ios-session-fixture`, `ios-keychain-shim`, `macshim`, `macshim-compat`), its keychain/jailbreak/attestation event vocabulary and its stated rationale all imply exactly the platform claim §73.1 bans. Following Part I produces components whose names alone fail the claims gate.

#### PowerShell: Windows CI runner vs. pwsh on Linux in a single toolchain image

**Part I.** §31.34: PowerShell implements "the Windows-side developer bootstrap" and "the collector wrapper that forwards the C# identity emitter's output into the ingest pipeline on Windows hosts", with "Pester tests … run on a `windows-latest` GitHub Actions runner" and "CI: job `lang-powershell` on `windows-latest`". Its demo role: "The Windows identity telemetry in the bundle arrives through this path."

**Part II.** §73.1 Tier C: PowerShell is "admin host automation (pwsh on Linux)" emitting "Windows-event-shaped JSON records", with the mandatory clause "PowerShell runs as `pwsh` on Linux … It is not Windows, and no document may imply a Windows endpoint was observed." §73.9.3: "One digest-pinned prebuilt toolchain image holds all 32 toolchains. Per-PR jobs never install a toolchain."

**Impact.** A `windows-latest` runner cannot be served by one Linux toolchain image, and §31.34's wrapper is a SPECTRA ingest tool while §73.1 makes PowerShell an observed estate subject that §73.3.4 forbids the ingest path from knowing about. An implementer who builds §31.34 gets a CI job that cannot exist under §73.9 and a demo claim that §73.11 forbids.

#### Seven Part I SPECTRA tools are reclassified as observed estate subjects

**Part I.** Lua (§31.20) is "user-supplied event transformers executed in a sandbox inside the Rust normalizer" via `mlua`, DEMO_PATH. Perl (§31.19) is `tools/perl/logxlate/`, translating legacy formats into canonical NDJSON — "The PHP portal's `access_log` reaches the bundle through this tool." Scala (§31.14) is a streaming reconstruction baseline used "to quantify what the batch reconstruction gains". Groovy (§31.15) is Gradle build logic plus the scenario authoring DSL that "the demo scenario is authored in". Kotlin (§31.11) is an Android session-telemetry fixture generator (and in §32.6, the typed scenario DSL). Dart (§31.23) is a read-only certificate console that "calls the WASM verifier on web / the Go binary on desktop". Ruby in §32.6 is the "attacker choreography runner".

**Part II.** §73.1 Tier C makes all seven observed estate components whose sole job is to emit idiomatic telemetry: Lua = "OpenResty reverse proxy" (nginx log_format output); Perl = "cron/rotation utility" (plain syslog lines); Scala = "nightly batch reconciliation job" (log4j2 pattern layout); Groovy = "build pipeline scripts"; Kotlin = "API gateway" (logback JSON); Dart = "desktop client issuing API calls"; Ruby = "internal admin console". §73.1 states Tier C's promise is that "the reconstruction pipeline knows nothing about" these languages.

**Impact.** Part I's versions of these components read the rule table, are hosted inside the Rust normalizer, parse telemetry into the bundle, or call the verifier — all of which §30.2's own Tier 3 rule and §73.1's Tier C promise forbid. Concretely: §31.20's Lua-in-normalizer and §31.19's Perl translator sit inside the ingest path, which §73.3.4 requires to contain "no language-specific branch"; §73.6's failure transcript even uses `estate-perl-rotator` as its worked example. Building Part I's Perl and Lua guarantees the new grep gate fails.

#### C and C++ components are different programs with a different justification

**Part I.** §31.7: C is "a single-producer/single-consumer lock-free shared-memory ring buffer" plus "a `ptrace`-based syscall tap"; the rationale is capability — "shared-memory layout, cache-line alignment and a stable ABI … This is exactly what C is for." §31.8: C++ is "offline pcap flow reassembly … plus an interval tree … used to compute per-source liveness windows". §32.6: `c/libspectra_frame/` (record framing + ring-buffer reader) and `cpp/temporal_index/` (interval index + graph layout kernels).

**Part II.** §73.1 Tier B: C is the "ingest hot path: record framing + field scanner", promised as "a *measured* alternative to the Rust scanner, published whether or not it wins"; C++ is a "deterministic entity-key interner used by the same hot path", also "a *measured* alternative interner". §73.1 adds a Tier B honesty requirement: "the C and C++ components are justified by the existence of the benchmark, not by its outcome" and forbids the sentence "we rewrote the hot path in C for speed."

**Impact.** C++'s pcap reassembly and interval tree (which §31.8 says feed `liveness.json`) have no owner in Part II, and Part I's C rationale is a capability argument that §73.4's `promise` lint and Tier B honesty requirement do not accept. A Rust scanner and a Rust interner must exist as the comparison arm — Part I specifies neither.

#### F# loses the state machine model; Julia loses the combinatorial cross-checks

**Part I.** §31.13: F# "emits the canonical `artifacts/state_table.json` (states, legal transitions, guards, dimension tags) that Python's engine and the Rust kernel both load rather than hard-coding", with a regeneration gate; §31.28's Verilog `casez` is generated from that same table; §32.6 additionally calls F# the "FsCheck model of the control lattice; antitonicity oracle". §31.26: Julia does "a brute-force minimum-cardinality hitting set over Ψ for `|A| ≤ 20` fixtures, an independent multiple-choice knapsack solver for the Pareto frontier, and a sensitivity sweep", with a mutation gate on the kernel's popcount ordering.

**Part II.** §73.1 Tier D: F# is the "Pareto frontier over the enumerated corridors — independent implementation of the multiple-choice knapsack; must produce the identical frontier set as Rust." Julia is an "independent re-implementation of the same statistics" as R (median, IQR, bootstrap over the degradation matrix), where "disagreement beyond declared tolerance fails the build."

**Impact.** The two components swap jobs and two Part I gates lose their owner entirely: nothing generates `state_table.json` (which §31.13 says Python and Rust load and §31.28's RTL is generated from) and nothing performs the brute-force Ψ-minimality agreement check. An implementer following Part II deletes load-bearing artifacts that Part I's core depends on.

#### Octave's relationship to the liveness pass is inverted

**Part I.** §31.25: the Octave scripts do "signal analysis of telemetry timing — inter-arrival distributions per source, the q99 threshold used by the liveness pass, periodicity/beaconing detection via autocorrelation and Welch PSD". Demo role: "Produces `artifacts/analysis/q99_thresholds.json`, which the liveness pass consumes." §32.6: `matlab/liveness_ref/ q99 inter-arrival reference impl`.

**Part II.** §73.1 Tier D: GNU Octave does "inter-arrival quantile sensitivity (q95/q99/q999)" and is "sole implementation of the exact-rank quantile sweep; cross-checked against the Rust liveness quantile."

**Impact.** Part I makes the liveness pass a consumer of Octave's output; Part II makes Octave a downstream cross-check of the Rust quantile. The dependency edge reverses, which changes §73.3.1's consumer edge and §73.3.3's mutation target. The beaconing/PSD analysis in §31.25 also disappears with no statement that it was dropped.

#### YARA's output is evidence in Part I and fixture labelling in Part II

**Part I.** §31.31: YARA implements "content signatures over artifacts staged inside the lab … Matches become evidence events with stable `EventId`s and feed rules whose bodies require file-content facts." Demo role: "A YARA match is one of the evidence leaves in the counterexample tree." §30.2 places YARA in Tier 3, the observed lab.

**Part II.** §73.1 Tier D: YARA is "declarative labelling of generator artifact blobs — sole pattern language for fixture technique labels used by the goal-correspondence test."

**Impact.** In Part I a YARA match produces facts the kernel grounds over and the demo displays; in Part II it labels fixtures for one test. §73.9 additionally makes Tier D non-blocking for milestones, so a red YARA job would no longer block a build whose counterexample tree Part I says depends on it.

#### Vendoring is forbidden in Part I and required in Part II

**Part I.** §32.9 negative requirement: "Do not vendor third-party source. Pin versions in lockfiles instead." §33.4/§33.6 pin every toolchain via `.tool-versions`, lockfiles and the builder image; §33.5 achieves offline by running the builder container with `--network=none` after `make setup`.

**Part II.** §73.4 makes `offline_source` a required per-component field, with the example `offline_source = "vendor/llvm/clang-17.0.6.tar.zst"`. §73.6: "FAIL_ON any component whose offline_source is missing from vendor/ (network stays off)". §73.8 marks `vendor/**` and `third_party/**` as `linguist-vendored=true`, and the transcript prints "toolchains resolved from vendor/ : 32/32".

**Impact.** Part I's `vendor/` and `third_party/` directories are not merely absent from §32.2's "produce this structure exactly" tree — §32.9 bans their contents outright. An implementer who obeys §32.9 fails §73.6 on all 32 components on the first run of `make polyglot-audit`.

#### Part II's file paths contradict §32.2's mandated repository tree

**Part I.** §32.2: "Produce this structure exactly; do not invent extra top-level directories", then fixes the tree. Relevant placements: `native/c/libspectra_frame/`, `native/cpp/temporal_index/`, `polyglot/perl/logmangle/`, `polyglot/matlab/liveness_ref/`, `polyglot/lua/gateway/`, `web/` (the frontend), `rust/eclipse-core/` … `rust/spectra-sim/`, `python/spectra_ingest/`, `data/fixtures/`, `data/golden/`, `bench/results/`. §32.9 also bans a root `src/` and any `common/`, `utils/`, `misc/`, `shared/`.

**Part II.** §73.4 and §73.8 assume a different tree: `c/ingest_scanner/**`, `rust/ingest/**`, `rust/kernel/src/guards_generated.rs`, `rust/sim/src/guards_generated.rs`, `frontend/src/api/generated/**`, `wasm/preimage/*.wat`, `ingest/` (the grep-gated path), `fixtures/**`, `golden/**`, `artifacts/**`, `vendor/**`, `third_party/**`, `octave/`, and §73.6's remediation line "delete `perl/` and its manifest entry". Part II also requires `docs/polyglot/`, `docs/bench/`, `docs/research/` and `docs/naming.md`, none of which appear in §32.2's `docs/` subtree (adr, eclipse, diagrams, paper).

**Impact.** The two layouts are not reconcilable: `frontend/` vs `web/`, `ingest/` vs `python/spectra_ingest/`, `rust/kernel/` vs `rust/eclipse-core/`, root-level `perl/`, `octave/`, `c/`, `fixtures/`, `golden/`, `artifacts/`, `vendor/` vs their Part I homes. §73.3.4's ingest grep gate is specified against a path (`ingest/`) that does not exist in Part I's tree, so the gate silently passes on a repository built to §32.2.

#### Mutation testing is inverted: mutate the core vs. mutate the component's output

**Part I.** §30.3.3: "Every `differential_oracle` must have a **mutation test**: a CI job injects a known deviation into the core and asserts the oracle *fails*. An oracle that cannot fail is not an oracle. Store these as `tests/mutation/<oracle>/mut_XX.patch` with expected exit codes." The worked instances follow that direction: §31.6 patches the Rust kernel so the Go checker must reject; §31.16 applies three patches that widen a blind interval, flip a Blind/Suppressed basis and admit an unlicensed silent instance; §31.26 perturbs the kernel's popcount ordering; §31.29 shifts a Rust interval endpoint; §31.4 perturbs the Rust canonicalizer.

**Part II.** §73.3.3: mutation is "a declared, deterministic corruption of the component's *output* which, when applied, turns a named downstream gate RED", applied "in a scratch worktree". §73.5: "Applied to the component's *output*, never to its source, except for `stub_entrypoint`", from a closed eight-operator set recorded in `polyglot.toml` as `mutation.op` + `seed` + `expect_red`.

**Impact.** Opposite directions and incompatible storage. Part I proves the oracle catches a wrong core; Part II proves a downstream gate catches a wrong component. Neither subsumes the other, and none of Part I's five mutation gates can be expressed in §73.5's operator set (there is no "patch another component's source" operator). §73.4's required `mutation.*` fields have no slot for `tests/mutation/<oracle>/mut_XX.patch`, so an implementer following Part I has no valid manifest entry — and the strongest existing safety property, "the oracle fails when the core is wrong", quietly disappears.

#### Two competing manifests, audit targets and tier vocabularies

**Part I.** §30.4.4: "`make lang-audit` is a hard CI gate. It parses `languages.toml` …" §30.5 fixes the schema: `language, name, dir, tier (1..4), reason, duplication_kind, build, test, ci_job, mutation_tests, demo_ring, produces, consumes, weak_exercise, loc_budget`. §32.2 lists `languages.toml` among the mandated root files, and §31.46 rule 7 makes `make lang-audit` cross-check `.gitattributes` against it. §31.44 lists `make lang-audit` and `make repro` as public Makefile targets.

**Part II.** §73.4: "`polyglot.toml` — the manifest. One file at the repository root." Required fields: `id, language, tier (A..D), paths, toolchain, offline_source, entrypoint, promise, consumer.*, ci.*, mutation.*, role.*`. §73.6 defines `make polyglot-audit` with fast/full modes, and §73.3.4/§73.12.3 require `make reproduce`. Part II never mentions `languages.toml`, `make lang-audit`, `duplication_kind`, `demo_ring`, `weak_exercise` or `loc_budget`.

**Impact.** §73.0's override names only §30.1's rationale document, so §30.5's `languages.toml` and §30.4.4's `lang-audit` gate are left standing. An implementer reasonably builds both, with `tier = 2` and `tier = "B"` meaning different things for the same component, and §31.46 rule 7's `.gitattributes` cross-check pointing at the wrong manifest. Part II's `make reproduce` also collides with §31.44's `make repro` under §33.9's "Do not add a target that is an alias for another target."

#### Tier membership is reassigned across the board without a tier-mapping statement

**Part I.** §30.2 fixes four numbered tiers. Tier 1 (production core, "the only tier allowed to define product semantics"): Python, TypeScript, SQL, JSON/YAML/TOML. Tier 2 (hot path): Rust, Go, C, C++, WebAssembly. Tier 3 ("HETEROGENEOUS OBSERVED LAB — these are SUBJECTS, not tools"): Java, Kotlin, C#, Scala, Groovy, PHP, Ruby, Perl, Lua, Swift, Objective-C, Dart, Solidity, x86-64 Assembly, YARA, PowerShell, Bash, XML(SAML), HCL. Tier 4: Haskell, F#, Verilog, VHDL, R, Julia, MATLAB/Octave.

**Part II.** §73.1 fixes four lettered tiers with different membership. Tier A (6): Rust, Go, Python, TypeScript, SQL, Bash. Tier B (6): Haskell, C, C++, Java, C#, x86-64 asm. Tier C (11): PHP, Ruby, Perl, Lua, Kotlin, Swift, Objective-C, Dart, PowerShell, Groovy, Scala. Tier D (9): R, Julia, Octave, F#, Solidity, Verilog, VHDL, WebAssembly, YARA. JSON/YAML/TOML/XML/HCL are removed from the tier system entirely into §73.2's config-format list.

**Impact.** No mapping between the two schemes is given and no OVERRIDES marker appears on §73.1's tables. The moves are load-bearing, not cosmetic: Bash goes from an observed subject to critical path; Solidity, asm and YARA leave the observed lab; WebAssembly drops from hot path to research artifact; Java and C# move from subjects to oracle duty. §30.2's rule "TIER 3 components … never import SPECTRA libraries, never read the rule table" therefore stops applying to Bash, asm, YARA and Solidity without anyone saying so.

#### README format: inventory table vs. fixed generated prose block

**Part I.** §31.46 rule 8: "The README reports the language inventory as a table with the tier and the one-sentence reason for each entry. It must not report a percentage bar as an accomplishment, and it must state that generated, vendored and documentation files are excluded from the count." §30.7.5: "The README states the count once, in a table, with the reason column visible."

**Part II.** §73.7: "`README.md` contains this block and no other sentence anywhere in the repository states a language count", then fixes the exact markdown — three prose paragraphs with `<<AUDIT:executing_languages>>`, `<<AUDIT:config_formats>>` and `<<AUDIT:linguist_rows>>` substituted by `make docs`. Gate: `UNBACKED_COUNT` fails "if a numeral adjacent to the word 'language', 'languages' or 'polyglot' appears anywhere in `README.md` or `docs/` outside the generated block."

**Impact.** A 32-row table with a numeric tier column next to the word "language" is precisely what `UNBACKED_COUNT` rejects, and §73.7's block carries no per-entry reason column. An implementer who writes the Part I table fails the docs gate; one who writes the Part II block silently drops the per-language reason that §30.1 and §32.1 exist to surface.

#### The number 43 is a language count in Part I and a bar-row count in Part II

**Part I.** §30.6's required audit transcript prints "languages declared : 43" and "components declared : 51". §31.44 justifies the Makefile as "a language-agnostic dependency graph across 43 toolchains".

**Part II.** §73.1: "Authored executing languages: 32. Configuration and markup formats: 11. Linguist language-bar rows: 43. The number 43 is the size of the colour bar and is never used in a prose sentence (§73.7)." §73.11: "Do not claim '43 languages'. The bar has 43 rows; the sentence has <<AUDIT:executing_languages>>." §73.2: counting a config format into the prose figure fails with `COUNT_CONTAMINATED`.

**Impact.** §30.6's mandated transcript emits the exact claim §73.11 forbids, and the two 43s are not even the same set — Part I's includes JavaScript and MATLAB, Part II's includes neither. An implementer reproducing §30.6's "exact shape" transcript produces an artifact that contradicts the audit JSON the README is generated from.

#### `.gitattributes`: fourteen `linguist-language=` overrides vs. a hard ban on them

**Part I.** §31.46 applies `linguist-language=` to fourteen paths, most of which are not misdetections: `db/**/*.sql → SQL`, `scripts/**/*.sh → Shell`, `scripts/win/**/*.ps1 → PowerShell`, `infra/terraform/**/*.tf → HCL`, `infra/docker/**/*.Dockerfile → Dockerfile`, `mk/*.mk → Makefile`, `fixtures/asm/**/*.asm → Assembly`, `hw/**/*.v → Verilog`, `hw/**/*.vhd → VHDL`, `analysis/matlab/**/*.m → MATLAB`, `lab/transformers/**/*.lua → Lua`, `schemas/**/*.json → JSON`, `rules/yara/**/*.yar → YARA`. None carries a comment naming a misdetection. Rule 5 pairs most of them with `linguist-detectable=true` specifically so these languages are counted.

**Part II.** §73.8: "`linguist-language=` may be used **only** to correct a genuine misdetection, and every use requires a one-line comment stating the misdetection it corrects. Using it to relabel a file as a language it is not — renaming `.txt` fixtures to a source extension, declaring config as code, tagging generated output as authored, splitting one component across extensions to add a bar row — is inflation." `make polyglot-audit` "fails with `LINGUIST_OVERRIDE_UNJUSTIFIED` if any override lacks a comment". §73.8's own file marks `fixtures/** linguist-detectable=false` and `*.jsonl linguist-generated=true`.

**Impact.** Part I's `.gitattributes` fails `LINGUIST_OVERRIDE_UNJUSTIFIED` on thirteen lines for missing comments, and several (`schemas/**/*.json → JSON`, `infra/**/*.tf → HCL`, `mk/*.mk → Makefile`) are "declaring config as code" — the inflation §73.8 names explicitly. §31.46's `fixtures/**` handling is also the inverse of §73.8's `linguist-detectable=false`.

#### Compile-only CI jobs: three allowed vs. none allowed

**Part I.** §30.4.3: "A CI job that only compiles is insufficient — compile-only jobs are listed in `languages.toml` as `weak_exercise` and the audit gate fails if more than three exist." §30.6's transcript prints "weak_exercise : 2 / 3 allowed".

**Part II.** §73.3.2: the declared CI job must be one "that executes the component (not merely lints or builds it) on every change to its paths". There is no `weak_exercise` concept and no allowance; a component failing any of the four checks is `PADDING` and §73.6 exits 1.

**Impact.** Part I permits a steady state with up to three build-only components; Part II deletes them. An implementer who ships the two `weak_exercise` components §30.6's transcript shows as acceptable will have them flagged PADDING and deleted under §73.6's "The failure action is **deletion, not documentation**."

#### A component with no demo role: banned in Part I, permitted in Part II

**Part I.** §30.4.1 defines exactly two rings, `DEMO_PATH` and `DEMO_ARTIFACT`, and assigns "every non-TIER-1 component" to one. §30.4.2: "`CI_ONLY` is not an allowed ring. A component that no demo output depends on and that no gate consumes must be deleted." §30.4.4 makes `make lang-audit` fail on "a component with no demo ring", and §30.6's transcript asserts "CI_ONLY 0".

**Part II.** §73.3.4 requires a "demo or benchmark role", and "Tier D components may declare `role = "none"` only if they additionally declare `published_artifact`". §73.4's worked `polyglot.toml` example sets `demo = "none"` with only a benchmark anchor — for a **Tier B** component, which §73.3.4 does not cover.

**Impact.** Part II legitimises a benchmark-only component that Part I would classify as CI_ONLY and delete; §73.6 also relocates the deletion record from §30.4.2's `docs/ADR/` to `docs/polyglot/deleted.md`. Part II's own example additionally contradicts its §73.3.4 restriction of `role = "none"` to Tier D.

### RESOLVED

#### MATLAB removed in favour of GNU Octave (§30.7.4, §31.25 → §73.1)

**Part I.** §30.7.4: "MATLAB is permitted only because an Octave fallback runs the same scripts in CI." §31.25 titles the component "MATLAB / GNU Octave — analysis/matlab/", every script is "written to the Octave-compatible subset", the CI job is `lang-matlab`, and §31.46 honesty rule 4 asserts `analysis/matlab/**/*.m` IS MATLAB and that "both statements must be true of the file contents". §33.6 pins `octave 9.2.0 # MATLAB-compatible reference path`.

**Part II.** §73.1 marked "OVERRIDES Part I: the target language set's inclusion of MATLAB is deleted and replaced by GNU Octave, with the non-equivalence stated rather than glossed." MATLAB "is not present"; the code "has never been executed by MATLAB"; `/\bMATLAB\b/i` anywhere outside `docs/polyglot/octave-not-matlab.md` fails `BANNED_MATLAB_MENTION`; §73.11 additionally forbids the phrase "MATLAB-compatible".

**Impact.** Clean override of the language choice, but it invalidates §31.25's compatibility-gate design ("a compatibility gate runs the full script set under Octave and fails on any MATLAB-only construct" presupposes a MATLAB-targeted source) and §33.6's pin comment. Part II is the binding text.

#### Prose rationale per language is no longer a gate (§30.1/§32.1 → §73.0/§73.4)

**Part I.** §30.1.1: "Write that reason down before you write the code." §32.1: "Record the justification for each language in `docs/polyglot-rationale.md`, one row per language, with the exact artifact it produces and the test that would fail without it."

**Part II.** §73.0, marked OVERRIDES: the written rationale is "replaced by the executable audit in §73.4. Prose rationale is demoted to explanatory commentary and may no longer be cited as satisfying any gate. `make polyglot-audit` is now the only thing that licenses a language to remain in the tree."

**Impact.** Resolved, but misattributed: `docs/polyglot-rationale.md` is mandated by §32.1, not §30.1. The override text names §30.1, so a literal reader may conclude §32.1's rationale file remains a gate. Also §73.4 replaces the `promise` field with a ≥120-character lint (`PROMISE_PLACEHOLDER`), which the Part I one-row-per-language table would fail.

#### "A directory that could be deleted must not exist" becomes a mechanical predicate (§32.1 → §73.3)

**Part I.** §32.1: "if a directory could be deleted and replaced by code already written in another language with no loss of capability, benchmark, cross-check or lab realism, it must not exist" — a reviewer judgement.

**Part II.** §73.0, marked OVERRIDES: the rule "is restated as a mechanical predicate (§73.3) rather than a judgement call" — four declarations (consumer edge, CI job, mutation, demo/benchmark role), "Three is a failure", verdict `LOAD_BEARING | PADDING(reason)`, exit 1 on any PADDING.

**Impact.** Clean. The operative consequence changes from review-time argument to a `make polyglot-audit` exit code, and §73.6 fixes the remedy as "deletion, not documentation".

## 74 Offline build and CI budget

### UNRESOLVED

#### Where the integration tier runs, given --network=none and a read-only single container

**Tension.** Part I §43.7 forbids mocking: "Do NOT mock PostgreSQL, Redis, or the Rust kernel in the integration tier. Use real services from compose.test.yml", ~300 integration tests own "ingest->resolve->ground->prove->cert"; §46.2 supplies them as GitHub services: postgres/redis; §46.4 makes ci/python (integration) a branch-protection required check. Part II's §74.3 build-offline — the T1 gate — is a single `docker run --network=none --read-only --tmpfs /tmp` of toolchain-a executing `make -C /w core && make -C /w test-t1`, and §74.4 assigns "Rust/Go/Python/TS unit + contract tests (Tier A languages)" to T1. Part II never mentions PostgreSQL, Redis, compose, or an integration tier anywhere, and toolchain-a's contents list only a "SQL client", not a server.

**Decision needed.** Decide which tier owns the real-service integration tier, and how a real Postgres and Redis are reachable under a posture Part II declares absolute ("--network=none is mandatory. Do not substitute a proxy, an allowlist or a firewall rule. A gate that permits any resolver is not this gate."). Then register it in ci/gates.toml with an id, tier and budget_s, or explicitly demote it out of T1.

**Recommended.** Split the posture: keep --network=none for build-offline (G-OFF-001) as written, and give the integration tier its own gate id on a compose network with no default-route egress, tiered T1 only if it fits the budget (see the T1 budget item) and T2 otherwise. State explicitly in §74.3 that a container-local compose network is not an exception to the no-resolver rule, since §74.3.4's sentinel already measures the host default route separately.

#### The T1 20-minute ceiling cannot hold Part I's per-PR required checks

**Tension.** Part II §74.4 sets T1 at "20 min end-to-end, all jobs" and §74.9's budget table shows T1 sum(budget_s) = 1043 s across 12 jobs, enforced by G-BUDGET-001. But §74.3's own expected transcript shows build-offline at 9m47s (587 s) and §74.4 puts build-offline (toolchain-a) in T1. Part I's declared budgets for work Part II also places in T1: §43.6 "Unit tier total wall time <= 4 min per language job" (Tier A is four languages = 16 min), "Integration tier <= 12 min", "E2E <= 15 min"; §33.3 `test` "all green in < 5 min on 8 cores"; §46.4 requires e2e/*, native/*, frontend/*, security/*, docs/* as per-PR checks that §74.4's tier table never assigns a tier to.

**Decision needed.** Either raise the T1 ceiling, or move named Part I per-PR checks (e2e, native ASan/UBSan/TSan matrices, frontend Lighthouse, docs strict build) to T2 and remove them from branch protection. The T1 table must be made arithmetically consistent with §43.6's budgets before G-BUDGET-001 can pass on day one.

**Recommended.** Keep the 20-minute ceiling, and demote e2e, the native sanitizer matrices and the docs link check to T2, leaving T1 = format/lint/guard-AST/determinism-2-repeat/build-offline/Tier-A unit+contract/demo hash/spine adversarial. Then amend §43.6's budgets to be per-tier rather than per-tier-of-pyramid, since the two budget systems currently use the same units for different things.

#### Languages Part I mandates that have no toolchain image and no fifth image is allowed

**Tension.** §74.0 states "Any language absent from languages.toml gets no toolchain, no image layer and no CI job, and its source directory must not exist", and §74.11.4 forbids "a fifth toolchain image, a per-language image, or a language whose toolchain cannot be installed offline into one of the four images". The four image rows in §74.1 name: Rust, Go, Python, Node/TS, SQL client, Bash; C/C++, GHC/cabal, JVM (temurin), binutils/nasm; PowerShell, PHP, Ruby, Perl, Lua, Kotlin, Dart; R, Julia, Octave, Python scientific. Part I mandates, as load-bearing directories with required harnesses and CI jobs, at least: .NET/C#/F# (§32.6 dotnet/, §43.2 rows, §46.1 polyglot.yml), Scala and Groovy (§32.6 jvm/, §43.2), Swift and Objective-C (§32.6 polyglot/, §43.2 "macOS runner only", §46.1), Solidity (§32.6, §43.2 Foundry), Verilog and VHDL (§32.6, §43.2, §44.6), YARA (§32.2 yara/, §43.2), Z3 (§32.8 tests/oracle/, §44.10), HCL/terraform (§43.2). §74.2 muddies it further by listing vendor rows for .NET (NuGet) and OCaml — OCaml appears nowhere in Part I — while no image row contains .NET. Part II never mentions the deletion this implies.

**Decision needed.** Publish languages.toml and state, per language, whether it survives. If .NET does not, §44.5 must be rewritten: the F# Spectra.StateModel is declared the source of truth for the legal-transition relation and generates transitions.{json,sql,py,rs,sv,vhd} consumed by Python, Rust, SQL and both RTL FSMs, with a drift test (§44.5) and an RTL cross-check (§44.6) that depend on it. Deleting .NET removes the generator that four other languages' artifacts are derived from.

**Recommended.** Treat the four-image constraint as the binding one and cut scope explicitly rather than by omission: keep .NET (it is a generator, not decoration) by adding it to toolchain-b, drop Swift/Objective-C outright (Part II already forbids claiming macOS support, and §46.1's macOS runners have no tier), and decide Solidity/Verilog/VHDL/YARA/Z3 one by one with the §32.1 'load-bearing' test — each deletion must also delete the Part I gate that depends on it, in the same PR.

#### security.yml: required per-PR checks built on network-fetched, time-varying databases

**Tension.** Part I §46.1 makes security.yml a required check (CodeQL, Semgrep, Bandit, gosec, cargo-audit, clippy, pnpm audit, Trivy on built images, gitleaks, dependency review) and §46.4 requires security/* on main; §33.3's security-test target is part of ci-local, and §46.8 pointedly exempts security.yml from the no-external-dependency rule ("Do NOT require any secret, paid API, cloud account or external registry for ci.yml, e2e.yml or polyglot.yml"). Part II §74.11.1 bans any CI step that installs from the network, §74.1.5 permits only toolchain-refresh to touch it, and §74.4's tier table has no row for any security scanner — so under G-REG-001 these gates have no id and no tier, and under §74.0 they are "not a requirement".

**Decision needed.** Decide whether vulnerability scanning is a gate at all under the new model, and if so which tier owns it and how advisory databases enter a digest-pinned offline image without going stale between toolchain-refresh runs. A gate whose corpus is frozen at image-build time reports a different answer than the same gate run online, and Part II gives no rule for that.

**Recommended.** Make the advisory databases a vendored, hash-recorded artifact in toolchains.lock refreshed by make toolchain-refresh, and tier the scanners T2 (nightly) with an explicit note that a T2 security result is as fresh as the last refresh. Do not leave them as unregistered required checks; either register them or remove them from branch protection.

#### The §45 adversarial suite has no gate row and needs a live stack

**Tension.** Part I §45 defines a 28-file adversarial suite run as a required CI job (§46.2's adversarial job: make compose-test-up, sudo tools/ci/block_egress.sh, pytest -m adversarial, findings_guard.py) and a branch-protection required check ci/adversarial (§46.4). Part II's §74.4 tier table contains only "Adversarial certificate corpus (must-reject) | T1 (spine subset) / T2 (full corpus)", which is the must-reject certificate corpus, not the suite that attacks the API, ingest path, Lua sandbox, UI and replay store. G-REG-001 requires every gate to have exactly one tier and a budget_s, and §74.3's single read-only --network=none container cannot host compose, a database or a browser.

**Decision needed.** Assign the §45 suite one or more gate ids and tiers, decide whether its egress-blocking approach (sudo iptables on the runner) is compatible with §74.3.4's egress sentinel, and state whether the §45.3 findings_guard lint is a T0/T1 lint or part of the suite. Also decide whether any §45 test is soundness = true and therefore non-quarantinable.

**Recommended.** Split it: register the pure-function subset (regex ReDoS, YAML/XML/archive parsers, path traversal helpers, JSON limits) as a T1 gate runnable inside toolchain-a with no services, and register the stack-dependent subset (auth, IDOR, CSRF, XSS/Playwright, race conditions, SSRF) as a T2 gate alongside whatever decision the integration-tier item produces. Mark test_provenance_forgery and test_replay_trace_tampering soundness = true, since they defend the same property as the must-reject corpus.

#### `make ci-local` promising the same exit code as CI

**Tension.** Part I §33.3 defines ci-local as "exactly what CI runs: setup lint fmt-check typecheck test-all security-test bench-degrade docs", done when it produces "same exit code as GitHub Actions on the same commit". Under Part II, CI is four tiers with different triggers (T0 pre-commit, T1 per push, T2 nightly main-only, T3 weekly main-only), sampled gates whose plan is a function of the committed ci/epoch.txt, per-job budget timeouts, and a main-only cache that PRs may read but not write. A single local target cannot reproduce that exit code, and it invokes setup (network) and bench-degrade (full matrix, now T2/T3) which Part II moves off the per-push path.

**Decision needed.** Redefine ci-local — most plainly as `make ci-local TIER=T0|T1` driven from ci/gates.toml — or delete the same-exit-code claim. Also decide whether a local run may advance or must pin ci/epoch.txt, since §74.5 forbids any sample chosen by anything other than the committed epoch.

**Recommended.** Generate ci-local from the gate registry (run every gate whose tier <= the requested tier, in registry order, with the committed epoch pinned) and restate the done-condition as 'same exit code as the T1 tier on the same commit and epoch'. That keeps §33.1's one-entry-point invariant intact while making it true.

#### Coverage gates and kernel mutation thresholds have no gate id

**Tension.** Part I §43.2 attaches a line-coverage gate to ~30 language rows, several enforced in the command itself (`pytest -q --cov=spectra --cov-fail-under=90`, 97% on spectra/eclipse, 95% on eclipse-kernel and cmd/spectra-verify, 100% lines on the anchor contract), and §43.5.4 requires mutation testing with "surviving-mutant ratio <= 10%" and "regressions of more than 3 points fail the nightly". Part I is already self-contradictory here (§32.2 "no coverage gate theater: report only" and §33.9 "Do not gate CI on coverage percentage"). Part II's §74.4 tier table has no coverage row at all and only "polyglot mutation audit" at T2 — which is not obviously the same thing as mutmut on spectra/eclipse plus cargo-mutants on the kernel. Under §74.0, a requirement with no gate id "is not a requirement" and the registry linter "deletes the claim or fails the build".

**Decision needed.** Decide whether coverage is a gate or a report, and settle Part I's own §43.2-vs-§33.9 conflict at the same time. If mutation remains a gate, give it an id, a tier and a budget_s, and state whether it is soundness = true (the kernel mutation score is the real gate on the kernel per §43.5.4, which argues yes).

**Recommended.** Coverage: report only, per §33.9, and strip the --cov-fail-under flags from §43.2's commands so no unregistered gate exists. Mutation: register two gates, G-MUT-KERNEL (T3, soundness = true, cargo-mutants + mutmut, <=10% survivors) and the existing polyglot audit (T2), and delete the ambiguous 3-point regression rule in favour of an absolute threshold, since a delta rule cannot be evaluated by a gate that has no prior artifact on a clean clone.

### SILENT

#### One builder image containing every toolchain vs exactly four tier images

**Part I.** §32.2 tree: "docker/builder.Dockerfile — the one image containing every toolchain". §33.7: it "must contain every tool in 33.6 ... Publish nothing; the image is built locally and cached by CI with actions/cache keyed on the Dockerfile hash. make doctor inside it must print zero mismatches, and make polyglot inside it must print zero SKIPPED components — that is the definition of 'the builder image is complete'." §33.1: targets "transparently re-execute [themselves] inside the builder image".

**Part II.** §74.1: "Build exactly four images. Do not build one image per language and do not build one image for everything" — spectra/toolchain-{a,b,c,d}, each "self-contained and offline-complete for its tier", published to a registry AND exported as OCI tarballs to cas/oci/<digest>.tar. §74.11.4 forbids a fifth image. No 'OVERRIDES Part I' marker anywhere in §74.1.

**Impact.** The single largest divergence in the section, and it is unmarked. An implementer reading Part I builds docker/builder.Dockerfile and the §33.2 Makefile that references it; every §74 gate (G-IMG-001/002, images.lock, the four-image tier assignment, the build-offline recipe) then has nothing to bind to. §33.7's completeness definition is also unsatisfiable under Part II: toolchain-a contains no PHP/Ruby/Perl/Lua, so `make polyglot` inside it can never print zero SKIPPED. 'Publish nothing' also directly contradicts 'published to a registry'.

#### Which targets may touch the network

**Part I.** §33.5: "the builder container runs with --network=none for every target except setup, builder and dev", and §33.3 defines setup as `uv sync --all-packages`, `cargo fetch --locked`, `go work sync`, `pnpm install --frozen-lockfile`, `dotnet restore`, `cabal build --dependencies-only`. §46.2's ci.yml literally runs `pip install -e ".[dev]" ... -r requirements/dev.txt`, `uses: actions/setup-python@v5`, `dtolnay/rust-toolchain@1.83.0`, `actions/setup-go@v5`, and `make contract-deps # ghc, dotnet, iverilog, ghdl`.

**Part II.** §74.1.5: "make toolchain-refresh is the ONLY target permitted to touch the network." §74.11.1: "Do not add a CI step that installs anything from the network. If a job needs a tool, the tool goes in a tier image and images.lock changes in the same PR." §74.0's diagram puts every target except toolchain-refresh in NETWORK-FORBIDDEN. No override marker.

**Impact.** Three named network-permitted targets (setup, builder, dev) silently become zero. Worse, the entire §46.2 workflow skeleton — the one an implementer will copy — is a sequence of network installs that Part II bans outright; under Part II every CI job must instead declare a container: field resolving to an images.lock digest. `make setup` as specified also stops being meaningful, since all resolution happens at image build.

#### Vendoring third-party source into the repository

**Part I.** §32.9, a negative requirement: "Do not vendor third-party source. Pin versions in lockfiles instead." The §32.2 tree has no vendor/ directory and states "Produce this structure exactly; do not invent extra top-level directories."

**Part II.** §74.2 mandates vendoring per ecosystem: "cargo vendor vendor/cargo + .cargo/config.toml source replacement", "go mod vendor into vendor/", and §74.2.1 "Nothing over ~50 MB ... is vendored into git" — i.e. smaller vendor trees are in git. §74.10.5's normative .gitattributes contains "vendor/** linguist-vendored". No override marker.

**Impact.** A flat contradiction on a negative requirement. An implementer following §32.9 refuses to create vendor/, and then G-VEND-001/002 and the whole offline story have no vendor path to verify. This also silently adds top-level vendor/ (plus ci/, cas/, languages.toml, images.lock, toolchains.lock) to a tree §32.2 says to produce exactly.

#### Benchmark and degradation results: git-ignored vs committed

**Part I.** §32.2: "bench/results/ git-ignored; schema-validated JSON written by make benchmark" and "data/runs/ run manifests, liveness.json, certs (git-ignored)". §32.9: "Do not commit anything under data/generated/, data/runs/, bench/results/." §33.9 has docs read results from bench/results/ at build time.

**Part II.** §74.7: degradation matrix results — "full file committed under docs/research/results/ when it backs a docs claim"; benchmark results (T3) — "committed; a number in docs without its committed file fails G-CLAIM-001"; certificates survive expiry as "blake3 + verdict row appended to ci/ledger/certs.tsv, committed". Rule: "an artifact that has expired can never be cited. The committed ledger, not the CI artifact store, is the durable record." No override marker.

**Impact.** §32.9's .gitignore policy and Part II's citation policy cannot both be implemented. Following Part I, every docs number loses its backing file the moment the CI artifact expires, which is exactly the failure §74.7 exists to prevent; following Part II, the linter enforcing §32.9 fires on every committed result.

#### Devcontainer: built from the builder Dockerfile vs a pinned toolchain-a digest

**Part I.** §33.8: ".devcontainer/devcontainer.json sets \"build\": {\"dockerfile\": \"../docker/builder.Dockerfile\"}, mounts the repo at /work, forwards ports 8000 (api), 5173 (web), 5432, 6379, and runs postCreate.sh → make setup doctor." §32.2 lists ".devcontainer/ devcontainer.json + postCreate.sh". §33.6 requires the pinned versions be mirrored into devcontainer.json.

**Part II.** §74.10.8: "image": "spectra/toolchain-a@sha256:<digest from images.lock>", runArgs ["--cpus=6","--memory=16g","--network=none"], postCreateCommand "make doctor PROFILE=core", workspaceFolder /w, no forwarded ports, no postCreate.sh, "no marketplace fetch at create time". No override marker.

**Impact.** Two incompatible devcontainer.json files. Part II's --network=none default makes Part I's forwarded ports and `make setup` (a network-resolving target) inoperative, and a `build:` stanza cannot satisfy G-IMG-001, which requires the devcontainer reference to resolve to a digest in images.lock.

#### Makefile container re-entrancy and $HOME toolchain cache volumes

**Part I.** §33.1: each target "either runs natively ... or transparently re-executes itself inside the builder image", so a contributor "with only Docker installed can run every target". §33.2 implements this with RUN := docker run ... -v spectra-cargo:/root/.cargo/registry -v spectra-gomod:/root/go/pkg/mod -v spectra-uv:/root/.cache/uv -v spectra-pnpm:/root/.pnpm-store, gated on SPECTRA_IN_CONTAINER=1 / SPECTRA_NATIVE=1.

**Part II.** §74.10.3's guard.mk errors out unless uname -s is Linux and one of IS_WSL / SPECTRA_DEVCONTAINER / CI is set — no transparent re-exec, and a different env-var protocol. §74.1.2: a test run "must never consult a network resolver, a proxy, or a user-level cache in $HOME". §74.3.3: "$HOME inside the container is a tmpfs. Any ecosystem that silently falls back to a user cache fails here, which is the point." No override marker.

**Impact.** The four named persistent cache volumes in the §33.2 skeleton are precisely the failure mode §74.3.3 is designed to detect; keeping them makes build-offline pass while vendoring is broken. The two re-entrancy protocols (SPECTRA_IN_CONTAINER/SPECTRA_NATIVE vs SPECTRA_DEVCONTAINER/IS_WSL/CI) also cannot coexist in one root Makefile.

#### What `make doctor` does

**Part I.** §33.3: doctor "probes every toolchain, prints found vs pinned version, exits 1 on mismatch"; output doctor.txt; done when "table printed; mismatches listed with the .tool-versions line". §33.7 requires `make doctor` inside the builder image to print zero mismatches.

**Part II.** §74.10.4: "make doctor prints detected CPUs/RAM/disk, compares to the profile requested via PROFILE=core|matrix|range, and exits nonzero with the exact .wslconfig edit required", asserted against the Docker Desktop resource minimums table. §74.10.8 runs it as postCreateCommand "make doctor PROFILE=core". No override marker.

**Impact.** Two different done-conditions for the same target name, and §33.9 forbids aliases. An implementer building Part I's doctor gets no host-resource check (so under-provisioned runs produce timeouts that look like defects — the exact case §74.10.4 calls out); building Part II's gets no toolchain-version drift check, which §33.7's image-completeness definition depends on.

#### How a flaky test is quarantined

**Part I.** §43.7: "A flaky test is quarantined in tests/quarantine/ with an open issue link and does not count toward coverage." No expiry, no cap, no execution requirement.

**Part II.** §74.8.3-5: "A test may be quarantined only by adding a row to ci/quarantine.toml" with opened/expires ("opened + 14 days, hard maximum"), measured observed_rate, evidence path, hypothesis and owner; max_open = 5; G-FLAKE-003 (T0+T1) fails the build on every tier once today > expires; renewal of the same test_id more than once is forbidden; "A quarantined test still executes in T2/T3". §74.8.6 makes a list of gate classes non-quarantinable. No override marker.

**Impact.** Moving a test into tests/quarantine/ per Part I removes it from execution entirely and is invisible to G-FLAKE-003, so it never expires — the indefinite quarantine Part II exists to prevent. Both mechanisms cannot be the single source of truth for the README status table required by §74.8.7.

#### Caching fixture bundles

**Part I.** §46.8, a negative requirement: "Do NOT cache the fixture bundles; they are generated from seeds in-job so the generator stays exercised."

**Part II.** §74.6's cache table includes a row "fixture/bundle CAS | cas-${blake3(generator_inputs)} | exact only | main only, read-only from PRs". No override marker.

**Impact.** Direct conflict on a negative requirement. Enabling the CAS row stops exercising the seeded generator on every run, which is the property §46.8 protects and which §43.4 ("Fixtures are generated, never hand-edited") relies on.

#### Concurrency groups and cancellation

**Part I.** §46.4: "Every workflow declares concurrency: { group: <name>-${{ github.ref }}, cancel-in-progress: true } except release.yml and benchmark.yml, which set cancel-in-progress: false."

**Part II.** §74.7: cancel-in-progress: true only for the T1 per-PR group; "T2 nightly / T3 weekly / anything that publishes an artifact or mutates ci/epoch.txt" uses a single shared group t2-main with "cancel-in-progress: false # never cancel a run whose artifacts back a published number". No override marker.

**Impact.** Under Part I's rule, e2e.yml, security.yml, docs.yml and polyglot.yml nightly runs are cancellable; under Part II they publish artifacts or advance ci/epoch.txt and must not be. Cancelling an epoch-advancing run corrupts the §74.5 stride rotation and the coverage_debt accounting. The group is also global (t2-main), not per-ref, which serializes T2/T3 — a behaviour change Part I's per-ref rule does not produce.

#### arm64 and multi-arch images

**Part I.** §44.1 required test 5 for the trace-hash determinism suite: "Run on x86-64 and on the arm64 container; hashes equal." §46.1 release.yml: "build multi-arch images, SBOM, sign, changelog, GitHub release." §44.1 also requires 5 in-process repeats and 3 fresh containers per fixture.

**Part II.** §74.1.3: "Images are built for linux/amd64 only. linux/arm64 is explicitly unsupported and README must say so; do not emit a multi-arch manifest that implies otherwise." §74.11.7: "Do not claim the platform builds on Windows natively, on macOS, or on linux/arm64." §74.4 tiers determinism as "byte-identical replay, same runner, 2 repeats | T1" and "byte-identity across two distinct runners/CPUs | T2". No override marker.

**Impact.** A mandatory sub-assertion of the §44.1 determinism suite (the arm64 container) becomes unbuildable — there is no arm64 toolchain image — so the test as written cannot pass, and release.yml's multi-arch build is forbidden. The repeat count also silently drops from 5 to 2 with no statement that §44.1's list is superseded.

#### Which committed paths are protected from EOL normalization

**Part I.** §32.2 puts committed byte-stable artifacts at data/fixtures/ ("small, committed, byte-stable bundles for unit tests") and data/golden/ ("committed certificates + expected checker output"), with .gitattributes described only as "text=auto eol=lf; binary fixtures marked -diff". §43.3/43.4 instead put fixtures at tests/fixtures/scenarios/<name>/{bundle.jsonl,ground_truth.json,manifest.sha256}.

**Part II.** §74.10.5 mandates a byte-exact golden .gitattributes (G-WIN-002, T1: "this file must exist and match the committed golden copy byte for byte") whose protective rules cover tests/golden/**, **/*.cert.json, **/*.expected and cas/** — none of which is data/golden/, data/fixtures/ or tests/fixtures/. No override marker.

**Impact.** Under the mandated golden .gitattributes, `* text=auto eol=lf` applies to data/fixtures/*.jsonl and to data/golden/ files that do not end in .cert.json or .expected. On the declared Windows/WSL2 host that is exactly the single-CRLF scenario §74.10.5 warns about: "a single CRLF in a golden file would change every downstream hash and silently invalidate certificates." The golden copy must be reconciled with whichever fixture/golden path convention survives.

#### Source of truth for pinned toolchain versions

**Part I.** §32.2 requires top-level ".tool-versions asdf/mise pinned toolchain versions"; §33.6 lists ~30 exact versions and says "Put these in .tool-versions (mise/asdf format) and mirror them in docker/builder.Dockerfile and .devcontainer/devcontainer.json." §33.3's doctor compares against "the .tool-versions line".

**Part II.** §74.1 derives every image's contents from languages.toml; §74.2.3 records "per ecosystem: the resolver version, the lockfile path, the lockfile blake3, the vendor bundle blake3, and the in-image path" in toolchains.lock, regenerated only by make toolchain-refresh and checked by G-VEND-001. The devcontainer is a digest reference, so there is nothing to mirror into. No override marker.

**Impact.** Three competing pin registries (.tool-versions, languages.toml, toolchains.lock) with no stated precedence and no gate reconciling them. An implementer updating .tool-versions per §33.6 changes nothing that any Part II gate reads, and the §33.6 mirroring requirement is unsatisfiable against a digest-pinned devcontainer.

### RESOLVED

#### "the build fails otherwise" now requires a registered gate id

**Part I.** Part I asserts build failure in free prose throughout the counterparts, with no gate identifier: §43.2 "A language present in the repo with no test target is a build failure"; §44.9 "One violation fails the build with no override flag, no xfail, no skip marker"; §32.9 "The dependency audit in .github/workflows/gates.yml fails the build otherwise"; §34.7 "Hand-editing generated files fails the build."

**Part II.** §74.0: "OVERRIDES Part I: the phrase 'the build fails otherwise', wherever it appears in sections 0-56, no longer means 'on every push'. It means 'a named gate exists, it is registered in ci/gates.toml, it is assigned to exactly one tier, and it fails the build in that tier'. A requirement with no gate id is not a requirement; the registry linter ... deletes the claim or fails the build." G-REG-001 (T1) enforces it.

**Impact.** Every prose 'fails the build' sentence in 10-repo.md and 13-verification.md must be converted into a row in ci/gates.toml with an id, a tier, a make_target and a budget_s, or deleted. An implementer who just wires these assertions into ci.yml produces gates the registry linter will fail on.

#### Tier C/D language test jobs move off the per-PR path

**Part I.** §43.1 "Every language in the polyglot set carries its own unit tier"; §43.2 "Each row is a required make target and a required CI job"; §46.1 polyglot.yml triggers on "PR touching the long tail, plus nightly" with Required check = yes; §46.4 branch protection on main requires polyglot/*.

**Part II.** §74.0 and the §74.4 tier table: "OVERRIDES Part I (§43.1): Tier C and Tier D language unit tiers do not run per-PR. They run in T2. A Tier C/D failure never blocks a Tier A milestone." T2 = nightly, main only.

**Impact.** polyglot.yml must lose its pull_request trigger and be removed from the branch-protection required-check list in docs/ci/required-checks.md; a Tier C/D red no longer blocks a merge. Building per §46.4 leaves a required check that Part II says must not gate.

#### Tag pins replaced by digest pins everywhere

**Part I.** §33.2 BUILDER_IMAGE := spectra/builder:$(shell sha256sum docker/builder.Dockerfile | cut -c1-12) (a tag); §33.6 pins toolchains by version string and only forbids `latest`; §46.2 uses image: postgres:16.4-alpine and redis:7.4-alpine as service tags.

**Part II.** §74.0: "OVERRIDES Part I: every base image reference pinned by tag is replaced by a digest pin. A FROM line without @sha256: fails make lint-images." §74.1.1 and G-IMG-001 (T1) extend this to every docker run, FROM, devcontainer reference and CI container: field, each of which must resolve to a digest in images.lock.

**Impact.** The hash-of-Dockerfile tag scheme in the §33.2 Makefile skeleton and every tagged service image in the §46.2 workflow must be rewritten as sha256 digests recorded in images.lock, or lint-images/G-IMG-001 fails.

#### MATLAB deleted; languages.toml is the gate on a language existing at all

**Part I.** §32.6 mandates the directory polyglot/matlab/liveness_ref/ ("q99 inter-arrival reference impl (Octave-compatible)"); §43.2 carries a "MATLAB/Octave" harness row (MOxUnit under Octave) as a required make target and CI job.

**Part II.** §74.0: "OVERRIDES Part I: MATLAB has no toolchain image and no CI job. The toolchain matrix carries GNU Octave. Any language absent from languages.toml gets no toolchain, no image layer and no CI job, and its source directory must not exist." §74.1 puts Octave in toolchain-d only.

**Impact.** polyglot/matlab/ must be renamed/removed rather than created, and the §43.2 row must be re-labelled Octave-only. More broadly this override makes languages.toml, not §32.6's tree, the authority on which language directories may exist.

#### No make target runs on Windows cmd.exe or PowerShell

**Part I.** §32.2 lists "scripts/ bash + powershell entry scripts used by the Makefile"; §32.8 "scripts/*.ps1 PowerShell 7 equivalents for Windows contributors"; §43.2 lists a PowerShell harness row (Pester + PSScriptAnalyzer, `Invoke-Pester -CI`) as a required make target and CI job.

**Part II.** §74.0: "OVERRIDES Part I: no make target is supported on Windows cmd.exe or PowerShell. Every target runs inside WSL2 or the devcontainer (74.11), enforced by a guard in the Makefile." §74.10.3 gives the guard, which errors unless uname -s is Linux and /proc/version contains microsoft.

**Impact.** The scripts/*.ps1 'Windows contributor equivalent entry point' role disappears entirely — the §33.1 rule "never document a second way to do the same thing" now resolves in favour of the bash path only. Note PowerShell Core survives as a range emitter runtime in toolchain-c, so the §43.2 Pester row is not itself deleted, only its role as a host entry point.

#### Full degradation matrix and 256-config agreement are T2/T3, not per-PR

**Part I.** §44.9 "tests/determinism/test_no_false_robust.py iterates the entire 100%→30% completeness matrix for every scenario and every tampering mode" with no tier qualifier; §32.8 describes tests/gates/ as "the section-7 build gates: 256-config agreement, antitonicity, rule-ordering determinism, zero-false-ROBUST across 100%->30%"; §33.3 makes bench-degrade run "the 100%→30% matrix across all scenarios and seeds" and ci-local run it.

**Part II.** §74.5: "OVERRIDES Part I (§7 / ECLIPSE §7): '256 randomized configurations per fixture' and 'the entire 100%→30% degradation matrix' are T2/T3 obligations. T1 runs a declared, deterministic sample." §74.4 tier table: "Degradation matrix + zero-false-ROBUST + false-UNSAFE reporting | T1 spine cells / T2 full matrix / T3 all seeds"; §74.5 adds G-SAMP-001 forbidding a SAMPLED artifact from backing any docs sentence.

**Impact.** The override cites §7/ECLIPSE §7 but not §44.9, which is where the full-matrix requirement actually lives in this counterpart; an implementer reading 13-verification.md alone still builds a per-PR exhaustive matrix run. The tier table does settle it, but the §44.9 wording should be amended to say 'the T2 full-matrix run' and to carry the sample_plan/claim_scope contract.

## 75 Non-goals and descope

### UNRESOLVED

#### Haskell differential oracle and Z3: a build-failing gate in Part I, OPTIONAL and cuttable in Part II

**Tension.** 01-preamble.md §3.10 is titled "GATES — THE BUILD FAILS OTHERWISE" and lists gate 4 ("A **Haskell** reference admissibility checker differentially tests the license logic against the Rust implementation") and gate 6 (Z3 test-only oracle). §4.1 `make gates` = "the six gates of 3.10"; §4.7 DoD: "all six gates of 3.10 pass, **including the Haskell differential checker**". 15-delivery.md §52.9 makes both M6 deliverables and "Rust-kernel vs Go-checker vs Haskell-oracle disagreement on any fixture fails the build"; §56.1 row 16 gates `make gate-haskell`; §55.5 allows a `[checker-differential]` badge. Part II 75.3 lists "the Haskell reference admissibility checker; the Z3 test-only oracle" as explicitly OPTIONAL, and D2 deletes both outright. But 75.0's blanket override only demotes a "build fails otherwise" gate "where this section classifies it STRETCH or APPENDIX" — and 75.4 tiers sections 0-4 CORE/per-push-blocking and 52-56 CORE/per-push-blocking. So the very sections that mandate the Haskell gate are re-tiered CORE, while 75.3 calls the artifact optional.

**Decision needed.** Decide whether `make gate-haskell` / the Z3 oracle are (a) blocking CORE gates as §3.10, §4.7, §52.9 and §56.1 require, (b) nightly non-blocking, or (c) deleted per D2 — and, if (b) or (c), strike §4.7's "including the Haskell differential checker" DoD line, §56.1 row 16, §52.9's tri-implementation disagreement gate, and the `[checker-differential]` badge in §55.5 in the same edit.

**Recommended.** Make it explicit in 75.3 that items on the OPTIONAL list are demoted even when their owning Part I section is tiered CORE, and add the corresponding OVERRIDES lines against §3.10 gates 4 and 6, §4.7 and §52.9 — otherwise 75.0's own scoping rule keeps them blocking.

#### The 256-config simulator-vs-kernel agreement gate: blocking in Part I, declared tautological and demoted in Part II's example block

**Tension.** 01-preamble.md §3.10 gate 1: "Concrete simulator and kernel agree on **256 randomized control configurations per fixture**" (build fails otherwise); §4.4.2 repeats it as a correctness obligation "for every fixture"; 15-delivery.md §52.9 lists it as an M6 deliverable and §56.1 row 14 gates it as `make gate-agreement`; §3.2's pipeline diagram labels it "(gate 7.1)". Part II 75.8's worked M5 block states: "Simulator-vs-kernel agreement is tautological because both are generated from the same guard AST... MUST turn red: nothing today — the mutation propagates to both backends. **Action: the 256-config agreement test is DEMOTED to a codegen regression test in docs/checker-scope.md; real validation comes from oracle 3 in section 62. Status: demotion committed.**" This appears inside an illustrative `docs/adversarial-review.md` template with no OVERRIDES marker, and 75.10's illustrative-values disclaimer covers only numerals, not the demotion.

**Decision needed.** Decide whether the 256-config agreement gate remains a build-failing gate (Part I) or is demoted to a non-load-bearing codegen regression check (Part II 75.8 hypothesis 3). If demoted, §3.10 gate 1, §4.4.2, §52.9 and §56.1 row 14 must be amended and `docs/checker-scope.md` must state that simulator/kernel agreement establishes nothing about semantics — and 75.7's ratchet rule 1 ("no gate name may disappear") requires a waiver if `gate-agreement` is removed.

**Recommended.** State the demotion as a first-class OVERRIDES line in 75.3 or 75.4 rather than inside a template block, and name the replacement ("oracle 3 in section 62") in the same place, since Part I's whole simulator/kernel design (§3.4 "One guard AST, two consumers") was justified by this gate.

#### The UI is simultaneously CORE-blocking (via 52-56) and APPENDIX-never-blocking (via 39-42)

**Tension.** 75.4's re-tiering table lists "CORE 52-56 delivery, milestones, ratchet — per-push, blocking" and "APPENDIX 39-42 UI beyond the four screens — never blocking". But the UI requirements live in both bands: 15-delivery.md §52.11 (M8) mandates the full UI — per-control levels, PROVE, certificate header, counterexample tree expandable to raw records, blindness-premium panel, GHOST legend, embedded checker pane streaming real `spectra verify` output, stability strip, unhideable flag badges — with a Playwright suite asserting every on-screen number; §53.3 mandates a hero GIF generated by `make demo-assets` from a real UI run ("A hero that is a logo, a stock illustration, or a hand-drawn mockup is forbidden"); §54.2's demo script spends T+3:00 through T+9:30 in the browser; §52.1.4 requires a vertical slice "visible in UI" at M3 that "nothing after M3 may break", with `make demo-slice` in every later verify target. Part II 75.2 C10 shrinks the UI to four screens, D9 strips polish and D12 replaces the screens with a CLI transcript.

**Decision needed.** Decide which tier wins for §52.11/§53.3/§54.2/§52.1.4, and specify what replaces them when the UI is thinned or cut: does M8 close with four screens, is the hero asset allowed to be an asciinema cast, and is the §52.1.4 slice redefined to drop its "visible in UI" leg (Part II C7's e2e path is clone→generate→ingest→resolve→prove→verify, with no UI and no replay step)?

**Recommended.** Add an explicit OVERRIDES against §52.11, §53.3 and §52.1.4 stating the four-screen C10 replaces M8's deliverable list, that the hero asset may be a regenerated CLI cast below rung D9, and that the M3 slice's terminal leg is the CLI transcript — otherwise the CORE tiering of 52-56 keeps the full UI blocking and D12 is unreachable.

#### Ordering authority: MPC-first dependency graph vs strict M0→M10 milestone sequence

**Tension.** 15-delivery.md §52.1.1 orders milestones strictly M0→M10 with no milestone started before the previous is green; §52.1.5 forbids scattering languages before M9; §52.2 places the degradation matrix and stages F/G/H at M7, the full UI at M8. Part II 75.2 states "**Nothing outside the MPC may be started while any MPC row is red**" and `make mpc-status` "exits non-zero when any component is red **and** the working tree contains new files under a path whose owning section is not CORE", with ordering driven by each component's `blocks = [...]` list (C5 blocks C6, C7, C8, C10). This inverts Part I's order: C10 (UI) is MPC and must go green before non-MPC work, while stages F/G/H — M7 deliverables sitting earlier in Part I's sequence — are declared OPTIONAL in 75.3. Part II's only override of §52.1 concerns the green-twice cadence, not the ordering rules.

**Decision needed.** Decide whether the M0→M10 sequence or the `mpc.toml` dependency graph is the scheduling authority, and restate §52.2's milestone table accordingly (in particular whether M7 can close with stages F/G/H absent, and whether M8's UI may be built before M7).

**Recommended.** Make `mpc.toml` authoritative and republish §52.2's table as a view over the MPC graph, since 75.6's descope protocol and `make mpc-status` both key off MPC state, not milestone numbers — but say so explicitly, because §52.1.1 is currently CORE and blocking.

#### Stages F, G, H and degradation-matrix breadth: M7 deliverables vs Part II's OPTIONAL list and rung D11

**Tension.** 15-delivery.md §52.10 makes M7 deliver ECLIPSE stages F (redundancy index), G (decisive observation set) and H (Pareto frontier) plus "degradation matrix from 100% to 30% completeness in 10-point steps, crossed with the six perturbation modes (deletion, delay, duplication, reordering, corruption, targeted suppression), ≥ 20 seeds per cell"; 01-preamble.md §3.6 F/G/H are "IMPLEMENT EXACTLY THESE STAGES", §4.1 `make matrix` regenerates the 100%→30% matrix, §4.3 requires `artifacts/matrix/degradation.csv` over that full grid, and §54.2 shows "0 / 350 cells". Part II 75.3 lists "ECLIPSE stage F..., stage G..., stage H (Pareto frontier)" as OPTIONAL, 75.4 keeps 52-56 CORE/blocking, and rung D11 reduces the matrix to "3 cells, not 15" (a cell count that matches neither §52.10's grid nor C8's description). 75.2 C8 describes only "Completeness axis defined; per-operator seeds".

**Decision needed.** Decide whether M7 can close green with F/G/H unbuilt, and fix the normative matrix shape: §52.10's 8 completeness steps × 6 perturbation modes × ≥20 seeds, or C8's single completeness axis with per-operator seeds, or D11's 15-cell baseline reducible to 3. `make matrix`, `artifacts/matrix/*.csv` and the demo's cell count all depend on the answer.

**Recommended.** Add an OVERRIDES against §52.10 stating that F/G/H are optional and that C8's axis definition replaces the 10-point × 6-mode × 20-seed grid, and give the pre-descope cell count explicitly so D11's "15 → 3" has a defined starting point.

#### Where a milestone budget is declared — 75.6's trigger reads a field Part I never creates

**Tension.** 75.6's descope protocol fires when "elapsed > budget declared in `BUILD_LOG.md` for this milestone", and the DESCOPE entry schema has `milestone`, `budget_declared` and `elapsed` fields. But 01-preamble.md §0.3 specifies the "Exact entry format" for BUILD_LOG.md as a per-**increment** entry (INC-NNNN, goal, files touched, tests written first, commands run, measured numbers, notes) with no budget field and no milestone field, and it is append-only; 15-delivery.md §52 declares no per-milestone budgets anywhere, and §56.3's reporting format has no budget line either.

**Decision needed.** Specify who declares a milestone budget, in what entry format, and when — and reconcile the new milestone-scoped BUILD_LOG entry types (declaration + DESCOPE) with §0.3's "Exact entry format" for increment entries.

**Recommended.** Add a MILESTONE-OPEN entry schema to 75.6 (milestone id, budget_declared, opened_at_commit) alongside the DESCOPE schema, and state that §0.3's format governs increment entries only — otherwise the descope trigger can never evaluate and 75.6 is inert.

#### Increment size: ~400 changed lines (Part I §0.2) vs "1-2 days of work, dozens of files" (Part II 75.4)

**Tension.** 01-preamble.md §0.2: "Work in increments of at most **~400 changed lines and one concern**", each running the full PLAN/RED/GREEN/REFACTOR/GATE/COMMIT/LOG loop, with "Never run PLAN for increment N+1 while increment N is red"; §0.4 "one concern per commit" and "No commit may mix a feature and a refactor". Part II 75.4's override redefines the planning unit as "one `BUILD_LOG.md` entry per increment, **typically 1-2 days of work**" and justifies it by "an agent that creates **dozens of files per increment**". The override names only §0.1 Law 1; §0.2's line cap and one-concern rule are untouched and are incompatible with the new sizing in practice.

**Decision needed.** Decide the normative increment size: keep the ~400-line/one-concern cap (which forces several increments per day and contradicts the stated justification), or raise/remove it and state the new cap — and say whether the one-concern-per-commit rule still applies to a 1-2 day increment.

**Recommended.** Extend the 75.4 override to §0.2 explicitly with a stated cap (e.g. one concern, no line limit, but one gate run per increment); leaving a cap in force that the spec itself expects to be violated is exactly the "law that is quietly violated corrodes the operating contract" failure 75.4 cites as its reason.

#### Pareto frontier with no costs.toml: disabled vs expressed in control counts

**Tension.** 15-delivery.md §52.10 (M7 acceptance): "costs come only from `costs.toml` and **the test suite includes a case with no `costs.toml` where the frontier is expressed in control counts and says so**"; 01-preamble.md §3.6 H computes the exact Pareto set and §2.5.3 says "Costs are user-authored in `costs.toml` or absent". Part II 75.1 item 7: "**With no user-authored `costs.toml` the Pareto frontier is disabled, never defaulted to unit cost.** Any cardinality-mode axis is labelled 'control count, not cost' in every axis label, API field name and export." The two sentences of item 7 are themselves in tension — the first disables the frontier, the second presumes a cardinality mode exists — and neither mentions §52.10's mandatory no-costs test case.

**Decision needed.** Decide whether the absence of `costs.toml` disables the frontier entirely (delete §52.10's no-costs test case and §54.2's Frontier tab beat) or yields a cardinality-mode frontier labelled "control count, not cost" (rewrite item 7's first sentence). The UI Frontier tab, the API field names and the exports all follow from this.

**Recommended.** Keep the cardinality mode with mandatory labelling and rewrite item 7's first clause to forbid only defaulting to unit **cost**, since 75.3 already makes stage H optional and §52.10's no-costs test is the only thing currently preventing an invented cost axis.

### SILENT

#### Skipped tests: forbidden outright vs permitted under waiver

**Part I.** 15-delivery.md §52.3 (M0 acceptance): "`make lint test build` exits 0 with **zero test cases skipped**"; §56.1 row 2: "All tests green, zero skipped, zero xfail-without-issue — `make test -- --strict`"; §56.2: "Do not mark a test skipped to make a milestone green."

**Part II.** 75.7 negative requirements: "Do not mark a test `#[ignore]`, `t.Skip`, `@pytest.mark.skip` or `test.skip` to make a milestone green. **Skipped tests are counted separately as `tests_skipped` and any nonzero value must be justified in the same waiver mechanism.**" No OVERRIDES marker.

**Impact.** Part II creates a legal path to a nonzero skipped-test count (a ratchet waiver with a 40+ character rationale); Part I makes any skipped test a hard failure of the anti-slop gate and of M0 acceptance. An implementer reading Part I wires `--strict` to fail on skip>0, which makes Part II's `tests_skipped` waiver field dead and unreachable; an implementer reading Part II ships a repo whose M0 acceptance is violated.

#### Unimplemented surfaces: honest stubs required and inventoried vs stubs deleted and build-failing

**Part I.** 01-preamble.md §0.5: "Genuinely unimplemented work must fail loudly and be discoverable by grep. Use exactly these forms" — `NotImplementedYet("SPECTRA-TODO(INC-0063)")`, `Err(Unimplemented::new(...))`, `fmt.Errorf("SPECTRA-TODO(...)")`. "`make audit-stubs` greps for `SPECTRA-TODO(` and `NotImplementedYet` and prints an inventory. That inventory is **published in `docs/STATUS.md`**. An unimplemented surface is **acceptable and honest**." §4.5 and §4.7 require that inventory to exist and the README to link it. 15-delivery.md §56.1 row 9 scopes the prohibition narrowly: "No TODO / FIXME / unimplemented!() / panic!(\"todo\") / NotImplementedError **on any demo-path file**." §56.2: "If a function is not implemented, it raises/panics and its caller is not on the demo path."

**Part II.** 75.6: "**RULE: never silently carry a stub forward.** A stub is any file that (a) exists to satisfy a directory layout, (b) has a function body of `todo!()`, `panic(\"unimplemented\")`, `pass`, `return nil` with a TODO comment, or an empty test file, or (c) is named in `mpc.toml` `artifacts` but has no executing gate. Stubs are deleted at descope time. `make stub-scan` enumerates them and **fails the build if any stub exists outside `scenarios/extension-point/`**." 75.10 acceptance item 4 repeats zero stubs. No OVERRIDES marker and no mention of §0.5.

**Impact.** Directly opposed defaults for the whole-repo stub policy. Part I's mandated `NotImplementedYet`/`SPECTRA-TODO(` surfaces — exactly the way Part I says to represent unbuilt work such as `decisive_observation_set` (stage G) and `pareto_frontier` (stage H), both of which Part II 75.3 makes OPTIONAL — are stubs under 75.6(a)/(b)/(c) and would fail `make stub-scan`. An implementer following §0.5 ships a documented stub inventory in STATUS.md and cannot pass 75.10; an implementer following 75.6 deletes the surfaces Part I §4.5/§4.7 require to be listed.

#### Who authorizes a descope: autonomous ladder descent vs stop-and-report-to-human

**Part I.** 15-delivery.md §52.1.6: "If a milestone cannot be completed as specified, **stop and report** per section 56. **Do not silently redefine the acceptance criteria.**" §56.4 step 5: build M0, report in the §56.3 format, "Do not touch M1 until M0 is GREEN", after stopping for human confirmation of the milestone list. 01-preamble.md §0.1 Law 5: "Stop when blocked. Do not invent a workaround that changes the design silently." §0.7: stop and report if "a spec in this prompt contradicts another section" or "a gate in section 4 cannot be met without weakening a correctness property"; "Do not resolve the contradiction by quietly deleting a requirement. Write the BLOCKED entry, propose options, wait."

**Part II.** 75.6: "This is the procedure Claude Code follows when a milestone overruns its declared budget. **It is not optional and it is not a judgement call.**" Flow: STOP → record DESCOPE entry → if any MPC component is red, "[4a] Descend the ladder from D1 until the freed effort covers the red component" → "[5] Apply the demotion IN CODE and IN DOCS in the same commit" → "[6] Delete the stub" → "[7] Re-run make mpc-status and make ratchet-check ... before the next increment begins." No human confirmation step anywhere; no OVERRIDES marker.

**Impact.** Part II instructs the agent to unilaterally delete features, delete directories (D2: "delete the directory, do not leave a stub"), downgrade written guarantees and remove README claim rows on a schedule trigger, recording it only in BUILD_LOG.md. Part I requires it to halt and wait for a human when acceptance criteria cannot be met. An implementer following Part II will silently redefine §52 acceptance criteria — precisely what §52.1.6 and §0.7 forbid.

#### Network access during bootstrap: container image pulls permitted vs no network after clone

**Part I.** 15-delivery.md §52.3 (M0 acceptance): `docker compose up -d` reaches healthy for all services in <90s, `make bootstrap` "installs nothing outside the repo **and container images**"; §52.13 (M10 acceptance): "`make release-check` green from a clean clone with **no network beyond image pulls**"; §54.1: "Nothing is pre-baked **except container base images**"; §54.2 T+0:00 screen shows "Image pulls". 01-preamble.md §4.1: `make bootstrap` — "build all images, pin every version, **no network after first pull**".

**Part II.** 75.1 item 14: "**SPECTRA does not require a network at any point after clone.** No CDN font, no remote schema, **no package fetch at build or test time**, no telemetry, no update check, no license server." 75.10: "This section is satisfied when all of the following are true simultaneously **on a clean clone with the network off**" — including item 1 (`make mpc-status`), item 8 (`make weaponization-scan`) and item 9 (gates green). No OVERRIDES marker.

**Impact.** Part I's mandatory stack (postgres, redis, api, web, worker with pinned digests) cannot come up on a clean clone with the network off unless images are vendored into the repo, which nothing specifies. An implementer reading Part I builds a bootstrap that pulls images once; the 75.10 acceptance for section 75 can then never be demonstrated as written. Needs either an explicit image-pull carve-out in item 14 or a vendored-image requirement.

#### Supply-chain / WARDEN vocabulary scan: scoped grep with an allowlist vs whole-tree grep with one exempt file

**Part I.** 01-preamble.md §2.6 enforcement: "add a CI lint `make audit-scope` that fails if the identifiers `cve`, `sbom`, `purl`, `lockfile`, `typosquat`, `npm`, `pypi`, `registry`, `dependency` appear **as domain terms in `spectra/`, `rust/`, or `go/`** (build tooling and comments referencing this rule are **exempt via an allowlist file**)." 15-delivery.md §53.2 item 5 requires the README to say in prose: "not a vulnerability or CVE scanner, not an SBOM or dependency tool ... not a supply-chain tool (that is the author's other project, WARDEN, linked)". §55.7 requires Dependabot configured for `npm`, `pip`, `docker`, `cargo`, `gomod`, `github-actions`.

**Part II.** 75.1 item 10: "no SPECTRA subsystem may ingest a package manifest, a lockfile or a build attestation, and no WARDEN code may be vendored here. **A CI grep over the source tree for supply-chain vocabulary outside `docs/NON-GOALS.md` fails the build.**" No OVERRIDES marker; no allowlist mechanism, no directory scoping, no "as domain terms" qualifier, and no exemption for README.md or CI config.

**Impact.** Taken literally, Part II's grep fails the build on artifacts Part I makes mandatory: the README's required "What this is not" paragraph (§53.2 item 5), `.github/dependabot.yml` with `npm`/`pip` ecosystems (§55.7), `package.json`, and Part I §2.6's own allowlist file. An implementer must decide whether `make audit-scope` (Part I, scoped + allowlisted) or the item-10 whole-tree grep is the real gate; they cannot both be green.

#### Claim registry format and gate name (docs/claims.toml + make docs-check vs docs/claims.md + make claims-gate)

**Part I.** 15-delivery.md §53.4: "Every feature stated in the README must be reachable by a command in `DEMO.md` or covered by a named test; **`make docs-check` maps README claim anchors to test IDs listed in `docs/claims.toml`** and fails on an unmapped claim." §53.1's required doc tree contains no claims file at all. 01-preamble.md §4.1 defines `make docs-check` as "fail if any doc number is stale w.r.t. its generator".

**Part II.** 75.9: required posture file "`docs/claims.md` (every externally visible claim bound to the gate or bench artifact that supports it)"; `make banned-phrase-gate` "fails on a hit outside a registered entry in `docs/claims.md`"; 75.6: "Do not descope a rung and leave the README claim standing. A claim without its artifact fails `make claims-gate`." 75.10 item 9 requires `make claims-gate` green. No OVERRIDES marker and no mention of `claims.toml`.

**Impact.** Two incompatible registries for the same obligation: a machine-parsed TOML of claim-anchor→test-ID pairs read by `docs-check`, versus a Markdown file of claim→gate bindings read by `claims-gate` and `banned-phrase-gate`. An implementer building `docs/claims.toml` per Part I will have no file for Part II's two gates to read, and 75.7's ratchet rule 1 ("no gate name may disappear") then locks in whichever set was recorded first.

#### README composition: hand-written status banner and fixed section order vs machine-generated status only

**Part I.** 15-delivery.md §53.2 gives the README's "exact section order" as 13 numbered items, item 2 being a hand-written banner "verbatim shape: `> Status: research prototype (v0.1.0, milestone M10). Synthetic data only. Not a security product. See docs/LIMITATIONS.md.`", item 5 a hand-written "What this is not" list, item 10 "Results summary — at most 4 numbers". §53.3 mandates a hero GIF on the first screen.

**Part II.** 75.3: "The README renders component status from `mpc.toml` and `ratchet.json`; **hand-written status prose in the README fails the docs gate.**" 75.1 item 1 requires `docs/NON-GOALS.md` "linked from the README's first screen next to `LIMITATIONS.md`"; item 20 requires a "machine-generated language table"; 75.7 rule 5 requires a generated waiver table in the README; 75.9 requires the no-weaponizable-code statement verbatim in `README.md` (first screen); 75.10 item 10: "The README's status table, language table and waiver table are machine-generated; **no hand-written status prose survives the docs gate.**" No OVERRIDES marker.

**Impact.** §53.2's mandated verbatim status banner is hand-written status prose and would fail Part II's docs gate; Part II also adds at least four first-screen elements (NON-GOALS link, LIMITATIONS link, the ~90-word weaponization statement, generated status/language/waiver tables) that have no slot in §53.2's "exact" 13-item order. An implementer following §53.2 produces a README that fails 75.10 item 10.

#### M9 polyglot target set: MATLAB/Solidity/Verilog/VHDL required vs removed

**Part I.** 15-delivery.md §52.12 (M9 deliverables): each additional language ships "with a justification line in `POLYGLOT.md`... e.g. YARA for artifact-pattern fixtures, **Verilog/VHDL for the hardware-attestation sensor model, Solidity for the append-only evidence-anchor experiment**, WebAssembly for the in-browser fixpoint replayer, Assembly for the BLAKE3 chain inner loop..., **MATLAB**/R/Julia for analysis, Swift/Kotlin/ObjC/Dart for platform telemetry collectors"; acceptance requires every language in the target list to have a component+test+justification or an explicit "not used" entry, proven by `make m9-verify` + `make polyglot-report`.

**Part II.** 75.5.1: "**OVERRIDES Part I §30**: MATLAB is replaced by GNU Octave... **Solidity, Verilog and VHDL are removed from the target set** unless a named, executing, mutation-proved job exists for each; 'immutable audit anchor' duplicates the BLAKE3 chain and does not qualify." The override cites only §30; §52.12 is never mentioned, and 75.4 additionally tiers only "30-31 polyglot tiers C and D" as APPENDIX while leaving 52-56 CORE and per-push blocking.

**Impact.** The same target list appears in two Part I sections and only one is overridden. An implementer working M9 from §52.12 (a CORE, blocking section under 75.4) still builds the Solidity evidence anchor and Verilog/VHDL sensor model that 75.5.1 deletes, and still calls the analysis path MATLAB-verified, which NON-GOAL 17 and 75.5.1 forbid. §52.12 also lists no tier ordering, so it licenses starting Tier C/D languages that 75.5.1's tier rule forbids.

#### Certificate verdict encoding: one `mode` field plus flags vs separate `safety` and `minimality` fields

**Part I.** 01-preamble.md §3.7: `struct Cert { mode: Mode, // ROBUST | OPTIMISTIC ... flags: Flags, // grounding_capped, subset_minimal_only, greedy_cover }`; §3.9: above |A|=64 "the kernel **downgrades to subset-minimal and records `subset_minimal_only` in the flags**"; §2.5.2/§3.12.7: "Verdicts are exactly `ROBUST`, `OPTIMISTIC-ONLY`, `UNSAFE`, plus flags."

**Part II.** 75.1 item 6: "Verdicts are structural: `safety ∈ {ROBUST, OPTIMISTIC_ONLY, UNSAFE}`, **`minimality ∈ {EXACT, SUBSET, UNVERIFIED}`**." 75.5 rung D8 then speaks of "`minimality: SUBSET` the default" and of a "`psi_relative` certificate". No OVERRIDES marker.

**Impact.** Part II replaces a single-valued `mode` + boolean flag with two independent enum fields, adds a third minimality state (`UNVERIFIED`) and a certificate property (`psi_relative`) that Part I's schema has no representation for. The Go checker (§3.8), the certificate mutation corpus (§52.9: "wrong invariant U", "flipped cut atom"), the API and the UI header (§52.11) are all specified against Part I's `mode`+flags shape; an implementer building either shape gets a schema the other half of the spec cannot validate.

#### Scope of the zero-false-ROBUST invariant: every matrix cell vs declared suppression classes

**Part I.** 01-preamble.md §3.10 gate 5: "**zero false ROBUST verdicts across the entire 100% → 30% degradation matrix**"; §4.4.1: "`artifacts/matrix/false_robust.json` reports **0** false ROBUST verdicts **across every cell** of the degradation matrix. Any non-zero value is a build failure, never a documented caveat." 15-delivery.md §52.10 asserts and prints the count across the whole matrix; §56.1 row 18 gates it as `make gate-invariant`; §54.2 shows "false ROBUST verdicts: 0 / 350 cells".

**Part II.** 75.2 C8 "Done" means "...**zero false ROBUST on declared suppression classes**; ROBUST yield floor enforced"; 75.5 NEVER CUT list: "**C8's zero-false-ROBUST invariant on declared suppression classes**". No OVERRIDES marker, and no definition of "declared suppression classes" anywhere in section 75.

**Impact.** Part II narrows the project's single hardest correctness obligation from every cell of the completeness × perturbation grid to an undefined subset ("declared suppression classes"), and D11 further permits reducing the grid to 3 cells while claiming the invariant is untouched. An implementer scoping `make gate-invariant` to suppression cells alone will report "zero false ROBUST" while never testing deletion, delay, duplication, reordering or corruption — a claim Part I §4.4.1 intends to be exhaustive.

#### Limits document filename: docs/LIMITS.md vs LIMITATIONS.md

**Part I.** 01-preamble.md §3.12: "State these limits in **`docs/LIMITS.md`**, in the README, in the UI footer and in the CLI `--about` output"; §4.5: "**`docs/LIMITS.md`** contains all nine items of 3.12 verbatim, and the UI footer and `spectra --about` render them from that file"; §4.7 checklist lists `docs/LIMITS.md`. (15-delivery.md §53.1/§53.5/§52.13 independently name `docs/LIMITATIONS.md` — Part I is already split against itself.)

**Part II.** 75.1 item 1 links NON-GOALS.md "next to `LIMITATIONS.md`"; 75.5 NEVER CUT list ends with "`LIMITATIONS.md`"; 75.9 lists "`LIMITATIONS.md` (linked from the README's first screen, partly generated from measured data)" among the files "required before the repository is made public". `LIMITS.md` is never mentioned. No OVERRIDES marker.

**Impact.** Part II silently settles a Part I internal split in favour of LIMITATIONS.md but attaches it to a never-cut gate, while 01-preamble §4.5/§4.7 still require `docs/LIMITS.md` to exist and to be the source the UI footer and `spectra --about` render from. An implementer following 01-preamble produces a file no Part II gate looks for, and the nine "may never claim" items end up in the wrong document (Part II also calls LIMITATIONS.md "partly generated from measured data", whereas §53.5 requires the nine items verbatim).

#### `spectra prove` / `spectra verify` as service-free binaries vs a Postgres-backed pipeline

**Part I.** 01-preamble.md §3.1: "**Persist state and transitions in PostgreSQL**" with normative DDL for `entity`, `event`, `transition`; §4.1 requires `make demo` to "cold-start the stack". 15-delivery.md §52.3 (M0) mandates `docker-compose.yml` with postgres, redis, api, web, worker reaching healthy; §52.5 (M2) "heterogeneous records become entity-resolved, time-indexed, stable-ID events **in Postgres**"; §53.5 mandates an ADR for "Postgres as the event store"; §54.3's `make demo` runs `$(MAKE) bootstrap up` and then `spectra reconstruct --run r1` / `spectra prove --run r1 --mode robust`, i.e. prove addresses a run held in the store.

**Part II.** 75.1 item 15: "**SPECTRA's kernel and checker have no service dependencies.** `spectra prove` and `spectra verify` are **pure file-in/file-out binaries. If either ever needs Postgres, Redis or a running API to produce or validate a certificate, the offline-verification claim has collapsed and the change is reverted.**" 75.2 C7 defines the e2e path as "clone → generate → ingest → resolve → prove → verify with no manual step" and C5/C6 artifacts are files (`out/cert/*.json`). No OVERRIDES marker; Postgres, Redis and compose are never mentioned in section 75.

**Impact.** Part I's `--run r1` addressing model routes prove through state that reconstruct persisted to Postgres; Part II makes any such dependency an automatic revert. An implementer must decide up front whether the kernel consumes files (bundle.jsonl, liveness.json, rules/controls/goal) directly or reads the event store — this is an architectural fork that cannot be deferred, and Part I's mandatory ADR list and DDL point one way while NON-GOAL 15 points the other.

### RESOLVED

#### Definition of a green milestone / CI cadence (Part I §52.1.1 vs Part II 75.4)

**Part I.** D:/Academics/spectra/docs/prompt/part1/15-delivery.md §52.1.1: milestones are strictly ordered M0→M10 and "'Green' means: its `make` proof target exits 0 on a clean clone, in CI, **twice in a row**, with no manual step." §52.2 lists new languages per milestone, implying the double clean-clone run covers whatever toolchains exist at that milestone.

**Part II.** 75.4: "OVERRIDES Part I §52.1: milestones go green **once** per push on the CORE four languages (Python, Rust, Go, TypeScript) plus the full matrix nightly. 'Green twice in a row on a clean clone' across 40+ toolchains is a cadence one engineer cannot sustain... the ratchet in 75.6 replaces it as the anti-regression mechanism." (The ratchet is actually specified in 75.7, not 75.6 — a stale cross-reference.)

**Impact.** Correctly flagged. An implementer must build CI as one per-push run on four languages + a nightly full-matrix job + `make ratchet-check`, not a doubled clean-clone run. Note the override touches only the cadence clause of §52.1; §52.1.2–§52.1.6 (machine-parsable mN-verify, generated STATUS.md, M3 slice preservation, M9 polyglot start, stop-and-report) are left standing and are separately contradicted elsewhere (see SILENT #3 and UNRESOLVED items).

#### Granularity of the written-plan obligation (Part I §0.1 Law 1 vs Part II 75.4)

**Part I.** D:/Academics/spectra/docs/prompt/part1/01-preamble.md §0.1 Law 1: "Plan before building. No file is created before a written plan for the increment exists in `BUILD_LOG.md`." §0.2 requires one PLAN→RED→GREEN→REFACTOR→GATE→COMMIT→LOG loop per increment.

**Part II.** 75.4: "OVERRIDES Part I §0.1 Law 1: the written-plan obligation applies at **increment** granularity (one `BUILD_LOG.md` entry per increment, typically 1-2 days of work), not per file. File-granularity planning is unaffordable with an agent that creates dozens of files per increment."

**Impact.** Resolved as stated, though Part II misdescribes Part I (Law 1 was already increment-scoped, not per-file). The operative change is the new sizing — "1-2 days of work"/"dozens of files" per increment — which collides with §0.2's unmentioned ~400-changed-line cap (see UNRESOLVED).

#### The "under every evidence-consistent hypothesis" claim wording (Part I §2.1/§2.6/§3.12.3 vs Part II NON-GOAL 8)

**Part I.** 01-preamble.md §2.6 differentiation table, "What 'done' looks like" row: "A verified proof that a specific minimal cut breaks the reconstructed chain **under every evidence-consistent hypothesis**." §2.1 core directive asks "...which minimal set of controls would have prevented the outcome under every hypothesis the missing telemetry admits?" §3.12.3 defines ROBUST as "holds for every hypothesis the licenses admit under this catalog".

**Part II.** 75.1 item 8: "OVERRIDES Part I: the ECLIPSE one-liner's phrase 'under every evidence-consistent hypothesis' is retired from every artifact and replaced by 'under every hypothesis this rule table admits inside the licensed blind windows'." The silent envelope "admits exactly the hypotheses the hand-written rule table can express inside provably blind windows. It is not 'every evidence-consistent hypothesis'."

**Impact.** Resolved and explicit, but the retirement is repo-wide ("every artifact"), so §2.6's table row and §2.1's core-directive sentence in Part I must themselves be rewritten — if copied verbatim into README/docs they would be caught by 75.9's `make banned-phrase-gate`/`make claims-gate` posture.

## 76 Hypothesis object

### UNRESOLVED

#### The banned-field-name lint collides with mandated rule-DSL field names

**Tension.** 76.2 negative requirement 2 bans "No field whose name matches `(?i)(score|confidence|probab|likeli|belief|certain|plausib|weight|severity|risk|p_?value|percent|pct|ratio)`" and states the regex "applies to Rust, Go, Python, TypeScript, SQL columns, OpenAPI properties and JSON Schema properties"; the 76.18 gate row restates it as "a float or a banned field name appears in any schema, type, column or API property". Part I 18.1 makes `severity_class` a REQUIRED field on every rule ("enum {state_change, obligation, composite} | yes | classification, not a score"), present in all ten worked rules R1-R10, and 17.5.2/R3 make `ratio: { num: 4, den: 1 }` the mandated way to express burst acceleration without floats. Both names match the banned regex. Part II never mentions section 18 or the rule DSL.

**Decision needed.** Is the banned-name lint scoped to the Hypothesis/DegradedState types and their serialized forms (76.2's requirement 1 wording), or is it repo-wide (76.2's requirement 2 and 76.18's wording)? If repo-wide, `severity_class` and `ratio` must be renamed in the YAML authoring surface, in build/rules.toml and in the compiled matcher structs.

**Recommended.** Scope the lint to the hypothesis, degraded-state and API-response surfaces and add an explicit allowlist for the rule DSL. Renaming `severity_class` and `ratio` is a MAJOR semver bump on all 63 rules under 18.6 and changes `rules_hash`, which by 18.4 invalidates every prior certificate and forces `spectra verify` to report RULES_HASH_MISMATCH - a very high price for a name.

#### "No endpoint returns a float" versus the mandated ML baseline arm

**Tension.** 76.3: "`\"number\"` is forbidden anywhere in every SPECTRA schema; a schema lint (`make lint-schema-nofloat`) greps the compiled schema bundle for `\"type\": \"number\"` and fails." 76.11.5: "No endpoint returns a float. A contract test asserts every response body parses under a schema with `\"number\"` globally forbidden." Part I section 21 mandates the opposite for the baseline arm: 21.7's `ml-prediction-v1.json` envelope is served with `"score": 0.8312`, float feature values (`egress_bytes_log1p: 14.2`, `hour_of_day_sin: -0.71`), 21.5 requires calibrated probabilities via isotonic regression, 21.6's model cards carry pr_auc/brier floats, and 21.1 mounts it at `spectra_api.routers.baseline`. Part I 20.11 likewise declares `max_ghost_fraction = 0.25` in graph.toml. Part II never mentions section 20 budgets or section 21 at all.

**Decision needed.** Does the float ban apply to the whole product (killing the ML comparison arm, which is the research control that section 21 exists to provide) or only to the deterministic reconstruction, hypothesis and certificate surfaces? And is `max_ghost_fraction` exempt as a config threshold?

**Recommended.** Bound the ban explicitly: no float in the reconstruction core, the kernel, the hypothesis types, the certificate, or any endpoint under /v1/runs/**; the baseline router keeps its floats behind its `is_baseline_only`/`not_evidence` envelope. Say this in 76.3 and 76.11.5 rather than leaving "every SPECTRA schema" and "no endpoint" unqualified, or the no-ML-build gate G21.0 and the no-float gate cannot both pass.

#### Part I degradation flags that have no D-code

**Tension.** 76.13 presents a closed 10-code catalog as the whole of degradation ("From here on, degradation is a typed, monotone state with a class that determines exactly what it blocks"), and 76.14.3 has the Go checker reject, with exit 6, "a certificate whose `degraded.codes` is not a superset of the codes in its inputs' manifests". But Part I emits degradation signals with no counterpart code: `uses_undetermined_absence` (17.4.3, "the UI must show it"); `evidence_truncated` (17.5.3, where "a certificate whose witness depends on a truncated list is not ROBUST" - a soundness-class blocker in Part I); `RECONSTRUCTION_INSUFFICIENT` when `max_ghost_fraction` is exceeded (20.11, "refuse to produce a hypothesis"); the graph query envelope's `truncated` / `guards_fired` including `max_paths_enumerated` (20.8, 20.11); `skew_consumed` paths (20.4); and `timestamp_disputed` edges under `--allow-disputed` (20.4).

**Decision needed.** For each of these, either assign a D-code with a class (does `evidence_truncated` block ROBUST as 17.5.3 says? does `max_ghost_fraction` suppress the hypothesis set entirely, which 76.9.1's "every export returns a HypothesisSet" appears to forbid?) or state that the signal is retired. Until then the exit-6 superset check cannot be implemented, because input manifests carry codes the state type has no bit for.

**Recommended.** Extend the bitflags with D11 EVIDENCE_TRUNCATED (SOUNDNESS, to preserve 17.5.3), D12 UNDETERMINED_ABSENCE (COMPLETENESS), D13 GRAPH_QUERY_TRUNCATED (COMPLETENESS) and D14 RECONSTRUCTION_INSUFFICIENT (SOUNDNESS, suppresses the hypothesis set), and make 76.9.1's "always a HypothesisSet" explicitly subject to D14 suppression the way D9 suppresses P_MAX.

#### Fate of the dependency-edge layer beneath the Hypothesis

**Tension.** 76.2's Stage has `rule_inst`, `head`, `parents` and evidence, and no relation type. Part I 19.2 mandates exactly six typed relations (ENABLES, CREATES, AUTHORIZES, PROPAGATES, CONSUMES, OBSERVES) with per-relation derivation conditions, 19.2.1's artifact-identity rule for PROPAGATES, 19.3's `transition` and `dependency_edge` tables with the `edge_has_support` constraint and the `edge_without_evidence` CI view, 19.4.2's "A GHOST may never be the sole support for a PROPAGATES edge", and 19.8.2's Go `spectra chain verify` checks (a)-(f). The rule DSL depends on it too: 18.1's `causal_relation` field and V22 ("`causal_relation` present whenever the head feeds section 19 chain assembly"). 76.0 says "Delete any competing struct" but names no Part I structure, and 76.18's gate table contains none of these checks.

**Decision needed.** Is the dependency-edge layer deleted (in which case `causal_relation`, V22, `spectra chain verify`, the ghost-sole-PROPAGATES ban and the artifact-identity rule all go with it, and Part II must say where those safety checks re-land), or retained as an internal substrate the Hypothesis renders from (in which case 76.2's Stage needs a relation field and 76.0's "only structure" claim needs qualifying)?

**Recommended.** Retain the relation taxonomy as a per-stage attribute and keep the two checks that are safety-relevant - ghost-sole-PROPAGATES and evidence dereferenceability - as named gates in 76.18. Deleting them removes the only structural bar against a fully inferred lateral-movement claim, which is precisely the failure mode section 76 exists to prevent.

#### AMBIGUOUS and the trigger for the decisive observation set

**Tension.** 19.7.2 declares a set AMBIGUOUS when "the top two hypotheses differ only in T(h)", or "differ only in D(h) and share G, U, L, S, E", or have disjoint leaf event sets, or came from an entity-resolution fork - a predicate defined over rank components U(h) and S(h) that Part II's 6-tuple no longer computes. 19.7.3 then makes AMBIGUOUS the trigger: "For every AMBIGUOUS set, compute the DECISIVE OBSERVATION SET by handing the differing corridors to ECLIPSE stage G". Part II replaces this with `rank_class_1_size > 1` and a fixed tie caption (76.9.2), and never mentions AMBIGUOUS - yet it keeps `decisive_observation_set` alive as a suppressible field in 76.15 (suppressed by D1, D2) and keeps D5 COVER_GREEDY for the cover routine.

**Decision needed.** What now triggers computation of the decisive observation set, and do the three non-rank AMBIGUOUS conditions (disjoint leaf event sets, entity-resolution fork, differing only in temporal span) survive? A tie at rank 1 under Part II's key is a strictly different condition from Part I's AMBIGUOUS.

**Recommended.** Redefine the trigger on Part II's own terms - compute the decisive observation set whenever `rank_class_1_size > 1` OR any two members have disjoint observed-event sets OR the set came from an ER fork - and state it in 76.9, otherwise the surviving `decisive_observation_set` field and D5 have no producer.

#### Identifier-stem ban versus Part I's mandated query and endpoint names

**Tension.** 76.1: "`chain`, `path`, `story`, `narrative`, `timeline` are banned as identifier stems in Rust, Go, Python and TypeScript; the lint fails the build on `grep -rniE '\\b(attack_?chain|attack_?path|attack_?story)\\b'` outside `docs/`." The prose bans five stems; the committed grep catches only three compound forms. Part I 20.9 mandates "exactly these eight" query functions including `reconstruct_path`, `temporal_paths`, `k_evidence_paths` and `state_timeline` ("Do not add ad-hoc traversal helpers elsewhere in the codebase"), 20.14 exposes `/graph/paths` and `/graph/timeline`, 20.11 declares `max_path_hops`, 20.2 has attributes `grant_path` and `exe_path_hash`, and 21.10 lists "the state timeline" among the narrator's permitted inputs.

**Decision needed.** Does the stem ban govern (forcing a rename of Part I's mandated eight-function query surface, its HTTP routes, its budget keys and its node attributes) or does the committed grep govern (in which case the prose in 76.1 should be narrowed to the `attack_*` compounds it actually enforces)?

**Recommended.** Narrow 76.1's prose to match its own lint: ban `attack_chain`, `attack_path`, `attack_story`, `attack_narrative` and any identifier that names a hypothesis as a chain or a story, and leave graph-level `path`/`timeline` identifiers alone. Renaming the section 20 query surface breaks 20.9's closed function list, the 20.14 routes and the 21.10 narrator input list for no honesty gain - those names describe graph traversals, not attack claims.

### SILENT

#### The ranking formula itself: 7-tuple vs 6-tuple

**Part I.** 19.6.1: rank(h) = ( G(h), U(h), L(h), S(h), E(h), D(h), T(h) ) - ghost nodes; count of UNDETERMINED-supported edges; ceil(total_license_span_ns/1e9) i.e. seconds of blindness relied upon; sum of per-source integer `source_rank` from sources.toml (0 first-party authoritative .. 3 reconstructed); edge count; temporal span in seconds; blake3_128 of the canonical edge id list as u128. 19.6.2: "Publish the component vector next to the rank in the API and the UI; never publish the rank without the vector", and 19.8.2(e) makes the Go checker recompute "every rank vector... to the stored value".

**Part II.** 76.8: rank_key is a 6-tuple ( ghost_stage_count, |licenses_used|, |instances|, t_hi_max - t_lo_min in ticks, sum(rule_id), first_u64_of(id) ). U(h) and S(h) are gone; license span in seconds becomes a count of distinct licenses; span is in ticks not seconds; the tiebreak is 64 bits of the hypothesis id, not 128 bits over edge ids. 76.4 rule 2: "rank_key... NOT hashed"; 76.8.4: permuting the components must leave the certificate byte-identical. The 76.11 API member object publishes "rank": 1, "rank_class": 1 with no rank_key array.

**Impact.** 76.8 carries no OVERRIDES line, and 76.0's blanket claim ("No Part I section... ranks... a hypothesis") is false of 19.6, so nothing cleanly retires 19.6. Two different total orders result - Part II reorders by license count where Part I ordered by seconds of blindness, and Part II drops evidence-quality (source_rank) from the order entirely, orphaning `source_rank` in sources.toml. Part I's "never publish the rank without the vector" is violated by Part II's own API example, and 19.8.2(e)'s checker recomputation has nothing to check against once rank_key is excluded from the hash.

#### Hypothesis enumeration cap: 256 vs 8, and the algorithm

**Part I.** 19.5.1: backward BFS then "Expand the AND/OR structure into candidate DAGs by choosing exactly one alternative per OR node. Cap expansion at `max_hypotheses` (default 256); on cap, set flag `hypothesis_enumeration_capped` and report the cap." Step 5 prunes "any candidate that is a strict superset of another candidate with the same leaf set (non-minimal)", and 19.5.1 defines a hypothesis as "a minimal connected sub-DAG".

**Part II.** 76.8: "The k-best enumerator is Lawler-style over the AND/OR hypergraph and is exact only with respect to an **additive** enumeration key E(h) = (ghost_stage_count, |instances|, sum rule_id)... `k_max` is a declared constant (8), not a measurement. When the enumerator hits it, set D8." 76.2 defines a Hypothesis as "a canonicalized, deduplicated set of rule instances that derives the goal fact" - no minimality condition - and deduplication is on HypothesisId only.

**Impact.** A 32x change in how many hypotheses a run produces, with no override line anywhere. Part I's flag name `hypothesis_enumeration_capped` and Part II's D8 HYPO_RANK_TRUNCATED are the same condition under two names with different semantics (certificate metadata vs monotone degraded state). Part II also silently drops subset-minimality pruning: an implementer following 19.5.1 prunes non-minimal candidates, one following 76.2 returns them, so the two produce different sets even below the cap.

#### Three-valued instance status collapsed to a binary

**Part I.** The `observed` status of a rule instance is three-valued throughout Part I: 17.4.2 "An UNDETERMINED absence produces both: nothing in P_min, and a licensed instance in P_max"; 17.4.3 emits counters `absence_observed/absence_licensed/absence_undetermined` and a run flag `uses_undetermined_absence` that "the UI must show"; 18.7's finding-provenance schema is `"observed":{"enum":["OBSERVED","LICENSED","UNDETERMINED"]}` and the SQL is `CHECK (observed IN ('OBSERVED','LICENSED','UNDETERMINED'))`; 19.6.1's U(h) rank component counts "edges whose support.observed == UNDETERMINED".

**Part II.** 76.5: "Every stage is exactly one of OBSERVED or GHOST. There is no third state and no partial state." StageEvidence is a two-variant enum; the JSON schema's oneOf admits only OBSERVED and GHOST.

**Impact.** No override line. Part II gives no mapping for an UNDETERMINED-supported instance - it is neither fully observed nor fully blind (some producing sources live, some not), so it fits neither variant, and 76.5.2 requires a GHOST to carry a LicenseId "implied by liveness.json" which an UNDETERMINED instance may not have. An implementer either drops those instances from every hypothesis (silently losing derivations Part I puts in P_max) or mislabels them GHOST. Part I's `uses_undetermined_absence` flag also has no D-code (see UNRESOLVED on the degradation catalog).

#### EventId wire format: 32 hex digits vs 16

**Part I.** 17.1.3: "`event_id` is the 16-byte BLAKE3-128 content address from section 8". 18.7's finding-provenance schema: `"event_id":{"type":"string","pattern":"^ev:[0-9a-f]{32}$"}`. 19.3's worked edge record uses `"event_id":"ev:7a1c93f0b2d4451e8890ffaa3c2b6d51"` (32 hex).

**Part II.** 76.3, normative for the wire: `"events":{"type":"array","minItems":1,"items":{"type":"string","pattern":"^ev:[0-9a-f]{16}$"}}` - exactly 16 hex digits - and the 76.12 UI mock shows `ev:7c1a…`.

**Impact.** Flat, unannounced schema conflict inside my counterparts. A bundle built to 17.1.3/18.7 emits 32-hex ids that fail Part II's schema outright, so every hypothesis export from a conforming bundle is rejected; 76.5.1's requirement that the checker "re-resolves every one" against bundle.jsonl cannot pass. (Part I is itself split here - 25.5 declares `pub struct EventId(u64)` and 23.5 derives ids as `blake3(...)[0..8]`, both 16 hex - so Part II picked one side of an existing Part I inconsistency without saying so.)

#### Per-hypothesis OPTIMISTIC-ONLY verdict label

**Part I.** 19.4.2: "A hypothesis containing one or more GHOSTs is `OPTIMISTIC-ONLY` unless the ECLIPSE run was performed on `P_max` and returned ROBUST." 19.9's worked output prints the label on the hypothesis header line: "CAUSAL HYPOTHESIS h1 of 2 rank=(...) OPTIMISTIC-ONLY".

**Part II.** Verdicts are run-level and typed: 76.14.2's `Safety { Robust(SoundnessClean, Scope), OptimisticOnly(Scope), Unsafe(Scope) }`; 76.7.4 "The safety verdict comes from the fixpoint test under S over the whole program, never from the enumerated set"; 76.12.3 verdict strings "are formatted from a typed value that carries its scope"; 76.12.5 "a unit test asserts the reducer has no branch that derives a verdict from other fields". The Hypothesis type carries `program` and `realizability` but no verdict field, and 76.19.11 forbids any hypothesis field that influences a verdict.

**Impact.** No override line. 19.4.2's rule is exactly the forbidden pattern - deriving a verdict string from another field (ghost_stage_count > 0) client-side, without a scope binding. An implementer following 19.4.2/19.9 renders "OPTIMISTIC-ONLY" per hypothesis and fails `verdict-scope-required.spec.ts` and the reducer test in 76.12.

#### Corridor mask definition: union of blockers vs threshold-minimal literals

**Part I.** 19.5.2: "The union of `blockers` over a hypothesis is exactly the corridor clause ECLIPSE stage E adds to Ψ." 25.6E agrees: "`corridor_mask(tree)` = OR of `blockers` over the instances used in the witness tree", and that raw mask is what is stored in the certificate's psi (25.7: `"psi": [{"mask":"0x0000000000000024","corridor_id":3}]`). 19.8.2(f) makes the Go checker assert "the corridor clause set derived from the hypotheses equals the Ψ stored in the certificate".

**Part II.** 76.7: "corridor_of(h) = { minimal threshold literal x_{k,ℓ} per control k such that some stage of h has bit(x_{k,ℓ}) set in `blockers` }... if a hypothesis is blocked at level 2 and at level 3 of the same control, only x_{k,2} enters". `CorridorId = blake3("SPECTRA-CORR-v1" || u64le(mask) || controls_hash)`.

**Impact.** Two different bit masks for the same corridor, hence two different corridor identities, with no override line. Equality check 19.8.2(f) fails on any hypothesis blocked at more than one level of a control, and CorridorIds computed per 76.7 will not match the psi masks the kernel stored per 25.6E/25.7. Part II's own claim in 76.7.1 that "every corridor in Ψ was induced by at least one witness tree" cannot be checked by mask equality. (Under implication closure the sever test `S & mask != 0` still agrees; it is the identity and the equality gate that break.)

#### Backward-in-time obligation derivations abort the run

**Part I.** Obligation axioms derive a head that is time-indexed BEFORE the body that forces it: 18.3 R7 has `head: session.issued(session_id, t_before)` from `body: session.use`; 25.4's obligation is `requires = "session.issued(S, T0) with T0 <= T"` `whenever = "session.used(S, T)"`. 19.2 encodes this as the OBSERVES relation, and unlike ENABLES (`tick(u) <= tick(v)`) and PROPAGATES (`tick(u) < tick(v)`), the OBSERVES row carries no tick condition at all - it is explicitly an edge from a later observation to an earlier GHOST.

**Part II.** 76.6: `for s in out: assert t_lo(parent) <= t_lo(s) for all parents # time-indexing invariant`, where `parents` are "ords of the stages deriving this stage's body". 76.6: "Both assertions abort the process with exit code 70... They are not flags and not recoverable: time-indexed monotone grounding (ECLIPSE §3) makes them unreachable, so reaching them means the grounder is broken and no artifact from that run may be published."

**Impact.** Part II asserts a condition is unreachable that Part I constructs by design. Whenever an obligation's body fact is itself derived rather than a raw event - e.g. an `egress(Flow) => connect(Flow)` axiom (17.6.4) whose body is the derived `network.egress_step` fact of rule 104 - the forced ghost stage's t_lo precedes its parent's t_lo and the process aborts with exit 70, publishing nothing. No override line, and the failure is unrecoverable by design, so this turns a modelled Part I behaviour into a hard run-killer.

#### What the narrator is allowed to receive

**Part I.** 19.10: "An LLM may narrate an already-computed hypothesis" (singular), "and its output must be regenerable from the JSON with the LLM disabled". 21.10 lists the narrator's permitted inputs exhaustively: "ONLY already-computed deterministic structures - the certificate JSON, the cut, the corridor list, the counterexample derivation trees, the license list, the blindness premium, the state timeline, the provenance subgraph, the degradation table" - a closed list that does not include a hypothesis set.

**Part II.** 76.9.4: "Narration (the LLM boundary) receives the whole set or nothing. A narrator prompt containing exactly one hypothesis is a build failure of the narration harness. Every narrated sentence about a stage carries either its EventIds or the literal token GHOST." 76.16 additionally requires the degraded banner in "the narration preamble".

**Impact.** Direct contradiction of 19.10, and 76.9.5's override is scoped only to "any place in 39-42 or in the demo script", so it does not reach 19.10 or 21.10. An implementer building the narrator from 21.10's closed input list has no lawful way to pass a HypothesisSet at all, and one building from 19.10 passes exactly one hypothesis, which Part II makes a build failure.

#### API path prefix

**Part I.** Every HTTP surface in Part I is under `/api/v1`: 19.7.1 `GET /api/v1/runs/{id}/hypotheses`, 20.14 `/api/v1/runs/{run_id}/graph/*`, 24.9 `/api/v1/replay`, 25.11 `/api/v1/eclipse/*`.

**Part II.** 76.11: `GET /v1/runs/{run_id}/hypotheses`, `/v1/runs/{run_id}/hypotheses/{hypothesis_id}`, `/stages`, `/export` - no `/api` segment.

**Impact.** Minor but concrete and unannounced. 76.11.5 makes the OpenAPI document the source for the generated TypeScript client with a drift gate, so the generated client will call `/v1/...` while the rest of the product is mounted at `/api/v1/...`. Either the hypothesis routes 404 or the service ends up with two prefixes.

### RESOLVED

#### Ownership of the hypothesis object (76.0 vs 19.1/19.5/19.6/19.7/19.9)

**Part I.** Section 19 is titled "CAUSAL RECONSTRUCTION ENGINE" and explicitly owns hypotheses: 19.1 says it produces "(b) a set of assembled causal hypotheses (chains), (c) a deterministic ranking over those hypotheses, and (d) a dereferenceable evidence binding for every edge". 19.5 assembles them, 19.6 ranks them, 19.7 disambiguates them, 19.8 verifies them with a Go checker, 19.9 renders one.

**Part II.** 76.0: "OVERRIDES Part I: sections 17-19 end at the fact base, 20-21 at the state/hypergraph, 22-25 begin at controls and cuts. No Part I section constructs, ranks, binds evidence to, serves, renders or exports a hypothesis. From here on, the Hypothesis type defined in 76.2 is the only structure any layer may call a chain, a path, an attack story... Delete any competing struct."

**Impact.** The override is declared, so it is resolved in form, but its stated premise is factually false: 19.1-19.9 do exactly the things 76.0 says no Part I section does. An implementer who checks the premise against Part I finds it wrong and cannot tell how far "delete any competing struct" reaches - whether it deletes only the Hypothesis struct of 19.5 or the whole dependency-edge substrate beneath it (see UNRESOLVED: fate of the dependency-edge layer). Every subsequent 76 override that leans on this framing inherits the ambiguity.

#### Flags no longer downgrade the safety verdict (25.9 vs 76.13/76.14.2)

**Part I.** 25.9: "A run with ANY flag set (grounding_capped, subset_minimal_only, greedy_cover) MUST NOT be presented as ROBUST: the API returns mode: \"OPTIMISTIC_ONLY\" with downgraded_by: [\"grounding_capped\"], and the UI badge is grey, never green." The certificate (25.7) carries a single `mode` field plus a `flags` object.

**Part II.** 76.13 preamble: "OVERRIDES Part I: Part I treats flags as certificate metadata, which makes tripping a flag a free escape hatch from the zero-false-ROBUST gate." 76.14.2: "OVERRIDES Part I: safety and minimality are separate certificate fields. A subset_minimal_only downgrade may no longer suppress an honest safety result." In the D-table only SOUNDNESS-class codes (D1, D2, D10-unmitigated) block ROBUST; D4 CORRIDOR_TRUNCATED, D5 COVER_GREEDY (= Part I's greedy_cover) and D6 MINIMALITY_SUBSET (= subset_minimal_only) explicitly do NOT.

**Impact.** Behaviour inverts for two of Part I's three flags. A greedy-cover or subset-minimal run that Part I forces to OPTIMISTIC_ONLY is ROBUST under Part II (with a suppressed minimality claim). The certificate shape changes too: `mode` + `flags` + `downgraded_by` become `safety` + `minimality` + `degraded.codes` + `suppressed`, so 25.7's golden certificates and the 25.8 checker exit codes have to be rewritten.

#### Cost frontier when costs.toml is absent (25.6H vs 76.13 D7 rule)

**Part I.** 25.6H: "If costs.toml is absent, the frontier is computed over cardinality instead and is labeled cost_basis: \"cardinality\"." 25.11 serves it at GET /api/v1/eclipse/frontier -> [{cost, residual, cut, evidence:[EventId]}].

**Part II.** 76.13 Rule for D7: "with no costs file the frontier is **disabled**, not defaulted to unit cost. Any cardinality-only view is labelled 'control count, not cost' in the axis label, the API field name (`control_count`, never `cost`)... OVERRIDES Part I: ECLIPSE §4H's frontier is not produced at all in this state." 76.15 lists `pareto_frontier` as suppressed by D7 with the key absent.

**Impact.** Marked as an override, but it cites "ECLIPSE §4H", not 25.6H, and the two texts are not obviously the same address. An implementer reading 25.6H alone ships a cardinality-basis frontier with a field literally named `cost`, which Part II both forbids as a field name and forbids producing at all.

#### Obligation-trigger events as evidence (19.2 OBSERVES vs 76.5.3)

**Part I.** 19.2 defines the OBSERVES relation - "u is the only telemetry witness of v (bookkeeping edge)", derivation condition "v is a GHOST node and u is the obligation-bearing observation forcing it" - and its "Required evidence" column is "obligation trigger record". So in Part I the triggering observation is carried in the edge's evidence position.

**Part II.** 76.5.3: "OVERRIDES Part I / ECLIPSE §9 vs §4C contradiction... the triggering events go in `obligation_trigger.triggering_events`, a field that is structurally separate from `evidence.events`, never counted in `observed_event_count`, and rendered with the fixed caption 'axiom <id> fired on these events; the step itself was not observed'. A GHOST stage may never surface an EventId in a position the UI renders as evidence of the step."

**Impact.** Resolved, but the override names ECLIPSE §9/§4C and never names 19.2, so the OBSERVES row's "Required evidence: obligation trigger record" is left standing in Part I. An implementer following that row puts the trigger EventIds in the evidence field and trips `make test-ghost-accounting`.

#### Hypotheses must be served with respect to a cut (19.7.1 vs 76.7.3)

**Part I.** 19.7.1: "GET /api/v1/runs/{id}/hypotheses returns every survivor with its rank vector" - no cut parameter, no cut in the response, and 19.9's worked output prints a hypothesis with a corridor blocker set but no cut binding.

**Part II.** 76.7.3: "OVERRIDES Part I: 22-25 present cut search without any statement about what a cut means for a displayed chain. The binding is now one-directional and explicit: a HypothesisSet is always served **with respect to a named cut** (possibly the empty cut) and the response carries `cut_hash`. A hypothesis rendered without a `cut_hash` is a malformed response." Stage gains `severed_by: u64` and the set gains a biting stage ord.

**Impact.** Resolved, though the override cites sections 22-25 rather than 19.7.1, which is the endpoint actually being changed. The 19.7.1 response shape becomes malformed under Part II; `?cut=` is required and `Stage.severed_by` must be recomputed per cut.

#### Realizability gate before any P_max artifact is displayed (19.4.2/25.11 vs 76.10)

**Part I.** 19.4.2: "A hypothesis containing one or more GHOSTs is OPTIMISTIC-ONLY unless the ECLIPSE run was performed on P_max and returned ROBUST" - i.e. P_max hypotheses are displayable as-is. 25.11 mandates a UI with "a corridor list with expandable AND/OR derivation trees whose leaves are clickable EventIds" and GET /api/v1/eclipse/counterexample/{atom}, with no co-realizability filter.

**Part II.** 76.10: "OVERRIDES Part I: no hypothesis derived from P_max may be displayed, exported or narrated until it passes a realizability check" against a hand-authored `exclusions.toml`; NON_REALIZABLE is never displayed; a missing or unparsable exclusions file sets D9, and "D9 suppresses the entire counterexample panel" and all P_MAX exports.

**Impact.** Resolved and marked. Note the default consequence: `exclusions.toml` is hand-authored, so until someone writes one, every run carries D9 and the counterexample panel plus all P_MAX exports vanish - including the blindness-premium counterexample trees that 25.6/25.11 call the headline object the UI leads with.

