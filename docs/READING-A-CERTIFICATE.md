# Reading a certificate

A field-by-field guide to `runs/<id>/cert.spcert`. For each member: what it is, what it is
**not**, and which checker obligation uses it.

Background on what the pipeline computes is in [OVERVIEW.md](OVERVIEW.md). The normative
contract is [`kernel/slice-spec.md`](kernel/slice-spec.md); the emitter is
`python/spectra_vs/src/spectra_vs/cert.py`; the checker is
`python/spectra_vs_verify/src/spectra_vs_verify/checker.py`. Where this document and any of
those disagree, they win and this document is the defect.

Every example below is copied from a certificate in the tree, mostly
`runs/vs-02830d35a09ad406/cert.spcert` - the pre-registered blackout cell.

## The file

```
{"body":{...},"cert_hash":"b2b256:89598adef4c5be51acf4aa6daa7a4e6bf595570e5357042cda2f44e2c8a3ea8f"}
```

UTF-8, no BOM, LF only, exactly one trailing LF, never compressed. Object keys are sorted
by byte value, there is no insignificant whitespace, and there are no floats anywhere: i64
nanosecond values are decimal strings, masks and seeds are fixed-width lowercase hex
strings, and rationals are `{"num":u32,"den":u32}`. `null` appears at exactly one place in
the whole document, and that place is named below.

The first nine octets are `{"body":{`, so a reader can reject a wrong-shaped file before
parsing it. The specification names a 26-octet prefix running through
`{"body":{"schema":{"v":`; that prefix cannot exist, because the same document's
key-sorting law puts `atoms` first inside `body` and `min_checker` before `v` inside
`schema`. Sorting is the hashing law and wins. This is divergence 2 in the emitter's module
docstring.

`cert_hash` covers the canonical serialisation of `body` and nothing else. No member is
carved out of it. The trailing LF belongs to the file, not to the hash preimage.

### Running the checker

```
python -m spectra_vs_verify runs/<id>/cert.spcert \
  --rules --rules-cae --guards --controls-cae --catalog-bits \
  --bundle --liveness --profile --goal-cae --er --run-manifest
```

Exit 0 ACCEPT, 1 REJECT with a reason code, 2 usage or I/O error. An option you leave out
is a usage error, not a skipped obligation. There is no `--force`, no `--skip` and no
`--ignore-hash-mismatch`.

**ACCEPT means the certificate is internally consistent with the inputs it pins.** It says
nothing about whether the bundle is truthful, whether entity resolution was correct,
whether the control catalog is complete, whether grounding found every instance, or whether
the certificate was independently verified. `spectra_vs_verify` imports nothing from
`spectra_vs`, but both are Python written by one author from one reading of one
specification and both share `spectra_core`, so a misreading shared by both sides is
invisible to the check.

### The member set

Twenty members are declared. Seventeen are always present:

`atoms`, `budgets`, `cut`, `cut_delta_canonical`, `ghost_count`, `goals`, `inputs`,
`instances`, `licenses`, `observed_event_count`, `psi`, `residual`, `schema`, `scope`,
`silent`, `verdict`, `witnesses`.

Three are conditional: `invariant` (present iff every goal is severed), and exactly one of
`premium` / `premium_suppressed_reason`.

An unknown member is `E-SCHEMA-UNKNOWN`; a missing required member is `E-SCHEMA-MISSING`.
Both are caught by O2.

---

## `schema`

```json
"schema":{"hash_algorithm":"blake2b-256",
          "hash_substitution_note":"The specification names blake3. This Python reference implementation computes blake2b-256 because the standard library has no blake3 and no package may be installed. Digests here are not comparable with specified digests.",
          "min_checker":"1.1","profile":"eclipse-cert","v":"1.1"}
```

**What it is.** The version triple, plus a declaration of which digest produced every hash
in the file. `v` is the certificate schema version, `min_checker` the lowest checker version
that can read it, `profile` the certificate profile name.

**What it is not.** `hash_algorithm` and `hash_substitution_note` are not in the
specification's member list; it is closed and does not name them. They are here anyway
(divergence 1 in the emitter's docstring) because a certificate whose digests are
unlabelled is exactly the silent substitution the encoding law forbids. A digest in this
file is **not** comparable with a digest computed under the specified algorithm.

**Obligation.** O2: `v` must be exactly `"1.1"`, the checker's version must be at least
`min_checker` (compared numerically, so `1.10` does not sort below `1.9`), `profile` must be
`eclipse-cert`, and both digest-declaration members must match what `spectra_core.canon`
computes (`E-HASH-ALGO`). O2 also checks the whole member set.

---

## `scope`

```json
"scope":{"attacker":"non-adaptive",
         "bundle":"b2b256:419ff4f1c7fe52cb55bbb8d0f66e486095610128b6061a9da6c581155d42594a",
         "controls":"b2b256:ded86bbf...","er":"b2b256:f94edd2e...","goal":"b2b256:aec2d790...",
         "liveness":"b2b256:15f0694a...","rules":"b2b256:af378c79..."}
```

**What it is.** Exactly seven members: six digests and the literal attacker model. This is
the "relative to what" axis, and it travels with every rendering of the verdict. Nothing in
the certificate is true except relative to these six artifacts and a non-adaptive attacker.

**What it is not.** It is not a description of an environment, a deployment or a customer.
It is not the complete list of pinned inputs: `inputs` pins five more digests
(`catalog_bits_hash`, `guard_ast_hash`, `profile_hash`, `rules_text_hash`,
`instances_hash`) that have no scope member. It is not optional and not partial - scope is
total or the run emits no verdict at all.

**Obligation.** O3: all seven members present, `attacker == "non-adaptive"` (the only value
v1 accepts, `VRD-005`), each digest well formed, and each equal to its counterpart in
`inputs` (`E-SCOPE-BIND`). The emitter makes the same check before writing anything, under
`VRD-012`.

---

## `inputs`

```json
"inputs":{"bundle_hash":"b2b256:419ff4f1...","bundle_provenance":"synthetic_generator_no_range",
          "catalog_bits_hash":"b2b256:8afd5cd2...","controls_hash":"b2b256:ded86bbf...",
          "er_hash":"b2b256:f94edd2e...","goal_hash":"b2b256:aec2d790...",
          "grounding_mode":"replayed","guard_ast_hash":"b2b256:efaf2a97...",
          "implementation":"python-reference","instances_hash":"b2b256:7ffa651a...",
          "k":3600,"liveness_hash":"b2b256:15f0694a...","profile_hash":"b2b256:18c3cc09...",
          "rules_hash":"b2b256:af378c79...","rules_text_hash":"b2b256:5d58be8c...",
          "seed":"0x0000000000000007"}
```

**What it is.** Eleven digests over named artifacts, plus five declarations. What each
digest covers is written out in `INPUT_HASH_COVERAGE` in the emitter and again, separately,
in `INPUT_COVERAGE` in the checker - duplicated on purpose, because a checker that imported
the emitter's idea of what a hash covers could not disagree with it.

Worth knowing, member by member:

- `rules_hash` covers the canonical rule-encoding artifact from S1, **not** the octets of
  `rules.toml`. Reflowing a comment must not invalidate an archived certificate.
- `rules_text_hash` covers `rules.toml` as authored. **Forensic only.** When `rules_hash`
  matches and this differs, the checker prints a note and continues; nothing is enforced.
- `catalog_bits_hash` covers `catalog-bits.lock`. Bit positions are inside the digest, which
  is why that lock is append-only: an edit that shifts a bit invalidates every certificate
  that quoted it.
- `profile_hash` covers the calibration profile. The profile fixes every liveness threshold,
  so it is pinned like any other input.
- `instances_hash` names **no file**. It covers the canonical binary encoding of the
  `instances` member in published order. It is the one digest the emitter computes over its own
  output, and it is what binds `grounding_mode: "replayed"`: a checker re-derives it from
  the certificate's own bytes and needs no side file.
- `seed` is a fixed-width hex **string**, never a JSON number. `k` is the horizon in ticks.
- `grounding_mode: "replayed"` is the honest statement of what a checker does with
  `instances`: it replays them, it does not re-ground them from the bundle.
- `bundle_provenance: "synthetic_generator_no_range"` says the telemetry is generator
  output. It is a manifest-level statement and never a per-record key, which would violate
  label purity.
- `implementation: "python-reference"`.

**What it is not.** These digests do not attest that the artifacts are correct, only that
they are the ones this certificate was computed over. `instances_hash` is not a digest of
the grounding run; it is a digest of what was published.

**Obligation.** O4 recomputes every digest over the file supplied on argv for it
(`E-INPUT-*`), except `rules_text_hash` which is advisory, and `instances_hash` which it
recomputes from the body. O4 also requires `grounding_mode == "replayed"` and
`bundle_provenance == "synthetic_generator_no_range"`. O4b then re-evaluates the profile
binding gates B1 to B6 from the pinned inputs: the profile must not have been calibrated on
this bundle, must not come from a degraded run, must not share a seed band with the
analysis, and must match the generator configuration, the scenario family and the excluded
intervals (`PROFILE_*`).

---

## `verdict`

```json
"verdict":{"derived_suppressed":["pareto_frontier","redundancy_index"],
           "flags":[],"minimality":"EXACT_PSI_RELATIVE",
           "realizability":"UNCHECKED","safety":"ROBUST","witness_class":null}
```

**What it is.** Three independent axes plus their bookkeeping.

- `safety` answers "is the goal derivable under this cut, and over which program". Four
  values: the strongest one requires the goal to be underivable in the **upper** program;
  the optimistic-only one means severed in the lower program and derivable in the upper;
  the unsafe one means derivable in the lower program, with a witness; the fourth is a
  fail-closed sink for when none of the other three is constructible.
- `minimality` answers "what is claimed about the size of this cut". Nothing about safety
  implies anything about minimality or the other way round.
- `witness_class` is **present-and-null** on every non-unsafe verdict. This is the one
  permitted `null` in the whole document. On an unsafe verdict it is mandatory and is one of
  `OBSERVED` (no silent node anywhere in the tree), `LICENSED` (at least one silent node, so
  the tree depicts a hypothesis) or `CONTESTED` (forced when entity resolution was
  ambiguous, because a bad merge fabricates the leaves themselves). No rendering may
  collapse the first two into one word.
- `flags` is an array of names **sorted by bit position**, never alphabetically and never a
  bitmask on the wire. Nine flags at fixed positions; bits 9 to 15 are reserved and must be
  zero. Six of them (bits 0, 1, 3, 4, 5, 8) are the soundness class and block the strongest
  safety value.
- `derived_suppressed` names products omitted entirely rather than approximated. It always
  contains `pareto_frontier` and `redundancy_index`, both out of scope for the slice.
- `realizability` is `CHECKED` only when every displayed tree carries a realizability status
  object. The certificates in `runs/` carry `UNCHECKED`.

**Why a bare verdict token is never written alone.** A one-word rendering is the only thing
a reader remembers, and on its own it drops everything that makes it true. There is exactly
one renderer per language, in one named file, and it is the only place a safety token may be
adjacent to a string literal; no code path builds a verdict string by concatenation,
f-string, format, template or join. The short form carries the six scope digests and the
literal `non-adaptive` with it:

```
ROBUST(rules@b2b256:af378c79, controls@b2b256:ded86bbf, liveness@b2b256:15f0694a,
       er@b2b256:f94edd2e, goal@b2b256:aec2d790, bundle@b2b256:419ff4f1,
       non-adaptive) [EXACT_PSI_RELATIVE]
```

and the long form is the same content in prose, always ending with the sentence "This is a
statement about the model, not about the system." The type system backs the rule up:
`Safety` is deliberately not a string enum and has no `__str__`, so inheriting `str` cannot
turn every f-string in the codebase into a rendering site.

**What it is not.** Not a score, not a grade, not a rating, and not comparable across
scopes. Not a claim about a real system, and not a claim that an attack was stopped. The
strongest safety value is not a statement about an adaptive attacker.

**Obligation.** O14 checks the flag algebra: names declared, strictly ascending by bit, no
reserved bit set, the soundness mask empty when the strongest value is published
(`VRD-001`), an unsafe verdict carrying a witness class and at least one tree (`VRD-002`),
`CONTESTED` forced by `er_ambiguous` (`VRD-007`), `OBSERVED` refused over a tree containing
a GHOST or LICENSED node (`VRD-003`), exact minimality refused under a cap (`VRD-004`),
`witness_class` null on non-unsafe (`VRD-006`), and `derived_suppressed` complete
(`VRD-014`). O14b applies the temporal dispute rule. O15 checks the minimality claim.

On the emitter side, `Verdict` is a frozen dataclass whose `__post_init__` raises unless it
was handed a module-private seal. `Verdict.build` is the single constructor and returns an
error rather than a degraded value. A verdict read back from an untrusted file goes through
`VerdictProposal` first, so a file cannot instantiate an illegal verdict by naming its
fields. The strongest safety value additionally requires a `NoTamperToken`.

---

## `atoms`

```json
"atoms":{"assign":[["ctl:egress_seg",1,0],["ctl:egress_seg",2,1],["ctl:priv_approval",1,2],
                   ["ctl:priv_approval",2,3],["ctl:rate_limit",1,4],["ctl:session_binding",1,5],
                   ["ctl:session_binding",2,6],["ctl:token_expiry",1,7],["ctl:token_expiry",2,8]],
         "n":9}
```

**What it is.** The bit table: one row per `(control_id, level)` pair, as
`[control_id, level, bit]`, sorted by bit. `n` is the row count. Bits come from
`catalog-bits.lock`, which is append-only: a pair keeps its bit forever, removal writes a
tombstone, and a bit is never reused.

**What it is not.** Bit position is **not** rank. Rank is the 0-based index in the canonical
atom order, which compares `(control_id.encode("utf-8"), level)` as raw bytes under
`LC_ALL=C`. The two orders are different things and the certificate stores only the bits
here; ranks appear in `cut` and `psi` and are re-derived by the checker. The numeric value
of a mask is never a tie-break anywhere in a decision path.

**Obligation.** O5: `n` equals the row count, at most 64 rows (the mask is 64 bits wide),
bits unique and ascending, every `control_id` carrying the `ctl:` prefix, and the table
matching the rows implied by `catalog-bits.lock` (with the one declared translation: the
lock is authored with a bare `control_id`, the certificate carries the prefixed form). O5
computes the rank of every atom from the canonical order and hands that table to O6 and O13.
Codes: `E-ATOM-*`, `E-LITERAL-TABLE`, `E-LIMIT-COUNT`.

---

## `cut`

```json
"cut":[{"bit":0,"control_id":"ctl:egress_seg","level":1,"rank":0},
       {"bit":2,"control_id":"ctl:priv_approval","level":1,"rank":2}]
```

**What it is.** Which controls, at which levels, make the goal underivable in the program
the search ran over. A flat array of atom references, sorted ascending by rank and
upward-closed: raising a control to level `L` puts its atoms at levels 1 through `L` in this
list.

**What it is not.** It is not a list of atoms to be counted. **Cardinality is the number of
raised controls, never the number of atoms** - the two entries above are two raised
controls, and a control raised to level 2 would contribute two entries and still be one.
There is no `cardinality`, `mask` or `minimality` member here: the size claim lives in
`verdict.minimality`, and the mask is re-derived from the bits. It is also not a
recommendation, a remediation plan, or any counterfactual about what these controls would
have done in reality; the supported phrasing is that the cut severs this chain in the
model, or that the goal is underivable under this cut.

**Obligation.** O6: every entry matches the atom table row at its rank, ranks strictly
ascending, and every raised control upward-closed from level 1 (`E-CUT-CLOSURE`). O6b checks
level-minimality clause by clause: for every control raised above level 1, lowering it one
step must leave at least one published corridor unsatisfied (`E-CUT-LEVEL`). O6 also builds
the cut mask that O12, O13 and O15 use.

---

## `psi`

```json
"psi":{"complete":true,
       "corridors":[{"atom_ranks":[0,4,5,7],"corridor_id":"cor:c79d71a6...","mask":"0x00000000000000b1"},
                    {"atom_ranks":[2],"corridor_id":"cor:e87ac903...","mask":"0x0000000000000004"}],
       "program":"PMax"}
```

**What it is.** The corridor database the cut was found against. A corridor is a **clause**
over control atoms: at least one of its atoms must be raised for the cut to satisfy it.
`atom_ranks` are ranks in the canonical atom order, ascending; `mask` is the same set as
bits; `corridor_id` is a content hash over the rank vector. `complete` says the hitting-set
loop reached fixpoint rather than stopping at a cap or a budget. `program` travels with the
database so no consumer can forget which program it came from - in a certificate it is
always `PMax`, the upper program.

**What it is not.** A corridor is not an attack path, not a kill chain and not a list of
observed events; it is a set of controls, any one of which breaks some derivation. The
database is not a complete enumeration of attacks against anything: it is the corridors this
search enumerated over this program, under a cap of 4096 and a deterministic node budget.
The certificate does not publish the lower program's corridor database; only the counts that
reach the premium are derived from it.

**Obligation.** O13: `program` is `PMax`, corridor ids strictly ascending, each `atom_ranks`
ascending, each `corridor_id` recomputed from its rank vector, each `mask` recomputed from
the atom table, and **every corridor satisfied by the published cut** (`E-PSI-HIT`). O14
additionally refuses a published `premium` over a `psi` with `complete: false`.

---

## `premium`, or `premium_suppressed_reason`

```json
"premium":{"blindness_premium":["ctl:priv_approval"],
           "nec_max":["ctl:priv_approval"],
           "occ_min":["ctl:egress_seg","ctl:rate_limit","ctl:session_binding","ctl:token_expiry"],
           "per_control":[{"calibration_deficiency":{"den":1,"num":0},
                           "control_id":"ctl:priv_approval",
                           "license_ids":["lic:2662aec5...","lic:4497caad...","lic:c2de54bf..."]}]}
```

**What it is.** The controls that are in the upper cut only because a sensor could not see.
`nec_max` is the set of controls in every cut of the smallest size over the **upper**
corridor database. `occ_min` is the set of controls in at least one cut of the smallest size
over the **lower** one. `blindness_premium` is exactly `nec_max` minus `occ_min`.
`per_control` names, for each premium control, the licences it rests on and its
`calibration_deficiency` as an exact rational.

Read `calibration_deficiency` before you read anything else about a premium control. `0/1`,
as above, means the control rests on observed-gap licences: the sensor was there and a gap
exceeded its calibrated threshold. A value above zero means some of its licences rest on
calibration-deficiency reasons (`B_PROFILE_INSUFFICIENT`, `B_REGIME_UNKNOWN`,
`B_FORCED_NO_PROFILE_MODE`, `B_THRESHOLD_OVERFLOW`, `B_WINDOW_UNDERSAMPLED`), and such a
control may **not** be described as needed because a sensor was blind. The correct string is
"needed because this run was not calibrated for this source".

**What it is not.** It is **not** `cut_max \ cut_min`. Each cut search picks one canonical
representative out of possibly many cuts of the same size, and the difference of two
representatives is a property of the tie-break, not of the problem. The premium is defined
by the *values* of optimisation problems over the two corridor databases, so it is invariant
to solver order, branch order and insertion order. The object that *is* the difference of
two representatives is `cut_delta_canonical`, and it carries its own caption.

**Why it is absent rather than empty when its preconditions fail.** An empty premium and an
uncomputable premium are different facts, and writing `[]`, `null`, `0` or `"N/A"` for the
second would make them look the same. Absent is absent: the whole member is omitted from the
hashed bytes, and a `premium_suppressed_reason` appears instead, drawn from the closed set
`corridor_cap | er_ambiguous | grounding_capped | horizon_truncated | solver_budget`. This
matters here specifically, because an **empty** premium is the demonstration's control arm -
`runs/vs-0049b1adfb705cb3` publishes `"blindness_premium":[]` with an empty `nec_max`, and
that empty result is what makes the non-empty one mean anything.

Exactly one of `premium` and `premium_suppressed_reason` is present, never both and never
neither.

**Obligation.** O2 checks that exactly one of the two is present. O14 checks that a
published `premium` is *allowed*: no `grounding_capped`, no `corridor_cap`, `psi.complete`
true, and `budgets.budget_exhausted` false (`E-FLAG-DERIVED`). The checker does **not**
re-solve the optimisation problems, so it does not verify that `blindness_premium` really
equals `nec_max` minus `occ_min`, nor that either set is right; the emitter checks the
subtraction before writing (`Premium.__post_init__`) and the invariance property is a
property test, not a checker obligation. Read the premium as an emitter claim whose
preconditions the checker confirms.

---

## `cut_delta_canonical`

```json
"cut_delta_canonical":["ctl:priv_approval"]
```

**What it is.** The set difference of the two canonical cut representatives, sorted. It
carries, wherever it is rendered, the literal caption "difference between two canonical
representatives; not the blindness premium".

**What it is not.** Not the blindness premium, and never labelled or described as one. The
two may never appear in the same component or export.

**Obligation.** None beyond presence. It is a required member, so O2 rejects a certificate
that omits it, but no obligation checks its contents. It happens to equal the premium in the
blackout cell; that coincidence is not a check and not a definition.

---

## `licenses`

```json
{"basis":"SUPPRESSED","license_id":"lic:c2de54bf...","reason":"S_CHAIN_SEQ_GAP",
 "source_id":"src:iam_audit","t0_ns":"1707008999699266491","t1_ns":"1707009601892237041",
 "witness":["ev:967c4690c8e150de45027bf18e65784d","ev:9d31c46b7e529fb15b9ecab688d76522"]}
```

```json
{"basis":"BLIND","license_id":"lic:0fe434dc...","reason":"B_PROFILE_INSUFFICIENT",
 "source_id":"src:edr_host","t0_ns":"1707004800000000000","t1_ns":"1707012000000000000"}
```

**What it is.** The permissions the upper program rested on: one source, one interval, one
reason code, and a `license_id` that is a content hash over exactly those fields. `basis` is
`BLIND` (nobody could have seen) or `SUPPRESSED` (records are missing from a sequence, with
the two bracketing record ids as `witness`). Sorted by `(source_id, t0_ns, t1_ns)`. The two
quoted above are the ten-minute blackout window on a chained source, and the permanent blind
window on a source that emits no records at all.

**What it is not.** **A licence is never an observation.** It records that a step could not
have been seen, not that anything was seen. A `BLIND` licence carries a reason code and no
witness at all, and a licence that carried one would be rejected on exactly that ground.
`witness` on a `SUPPRESSED` licence is the bracketing pair that shows where the sequence
jumped; it is not evidence for the step the licence permits. A licence is also not a
detection of suppression or tampering: it is the honest representation of a window that
cannot be believed to be live.

Licences come from stage S7 and nowhere else, and no threshold is ever derived from the
bundle under analysis.

**Obligation.** O10: each `license_id` recomputes from its own fields, `basis` is one of the
two values, a `BLIND` licence carries no witness and a `SUPPRESSED` one carries a bracketing
witness, the array is ascending by its declared key, and - the load-bearing part - **every
cited licence is implied by the pinned `liveness.json`**: the cited span is covered by
non-LIVE elementary intervals on that source, and every producing source of the citing
instance's rule is non-LIVE over the same span (`E-LICENSE-UNIMPLIED`, `E-LICENSE-WINDOW`).
Widening a licence window by one tick is one of the injected bugs the corpus requires to turn
a named gate red.

---

## `silent`

```json
"silent":[{"instance_id":"in:05edddd4...","license_ids":["lic:2662aec5..."]}, ...]
```

**What it is.** The index of which published instances rest on which licences. 121 entries
in the blackout cell, out of 130 published instances. Sorted by `instance_id`.

**What it is not.** Not a list of events, not a list of things that happened, and not a
subset of the bundle. Every entry names an instance that cites **no** record.

**Obligation.** O10: `silent` lists exactly the published instances that cite a licence -
no more and no fewer - each cited instance is marked `LICENSED`, its licence ids match the
instance's own, and every licence id is in the published licence set. An unlicensed silent
instance has no place in a certificate at all; the emitter refuses to construct the
reference.

---

## `instances`

```json
{"blockers":["0x0000000000000004"],"body":["fh:ffa9cb3f..."],"evidence":[],"ghost":false,
 "head":"fh:059333a1...","instance_id":"in:09a1ddb8...","license_ids":["lic:c2de54bf..."],
 "observed":"LICENSED","rule_id":"rl:r0004","rule_version":"1.0.0","tick":1707008999}
```

That is the licensed escalation from the worked example: rule `r0004`, blocked by bit 2
(`ctl:priv_approval` at level 1), citing no evidence and one `SUPPRESSED` licence. Its body
fact is headed by the GHOST instance one level below it in the witness.

**What it is.** The published rule instances - the AND nodes of the provenance hypergraph -
that the checker **replays**. Each carries its head fact, its body facts, its blocker masks,
whether it is `OBSERVED` or `LICENSED`, its evidence (event ids, source ids and timestamps)
or its licence ids, a `ghost` flag, and the rule it came from. Sorted by `instance_id`,
which is a content hash over body, evidence event ids, head, licence ids and rule id.

This member is **wider** than the specification's `InstRef`, which names only
`instance_id`, `head`, `body`, `blockers`, `observed` and `license_ids`. `rule_id`,
`evidence`, `tick`, `ghost` and `rule_version` are added because without them a checker
cannot re-derive the identifier it is asked to trust, and `grounding_mode: "replayed"` would
name a replay nobody can perform. That reasoning is in the emitter, at `_instance_member`.

**What it is not.** Not the grounding run and not a proof that grounding found everything.
`grounding_mode: "replayed"` says exactly what happens: the checker replays these instances,
it does not re-ground them from the bundle. If the grounder missed a derivation, nothing
here will say so. `ghost: true` marks an obligation-forced head, which is not an event.

**Obligation.** O8 replays closure: for every published instance, if every body fact is in
`U` and no blocker term is satisfied by the cut mask, the head must be in `U` (`E-CLOSURE`).
O8 also asserts the slice narrowing - every blocker term has exactly one bit set
(`E-VS-BLOCK-CONJ`). O11 checks the `OBSERVED` / `LICENSED` split: a `LICENSED` instance
cites no evidence and at least one licence, an `OBSERVED` one cites records and no licence,
and a `ghost: true` instance must be `LICENSED`. O12 resolves every witness node against
this set. `inputs.instances_hash` is recomputed over it in O4.

---

## `witnesses`

```json
"witnesses":[{"nodes":[
  {"children":[1],"evidence":["ev:22ae6b8683cebeba2efac8d84e211ce6"],"head":"fh:a5d5a0aa...",
   "instance_id":"in:163c8c45...","kind":"OBSERVED"},
  {"children":[2],"evidence":[],"head":"fh:059333a1...","instance_id":"in:09a1ddb8...","kind":"LICENSED"},
  {"children":[],"evidence":[],"head":"fh:ffa9cb3f...","instance_id":"in:ea918f13...","kind":"GHOST"}],
  "removed_control":"ctl:priv_approval"}, ...]
```

**What it is.** For each control in the cut, the derivation of the goal that comes back when
that one control is removed. This is the part of a certificate that says *why* a control is
in the cut, rather than only *that* it is. Entries sorted by `removed_control`.

Since ADR-0015 the tree is published **flat**. `nodes` is a list in pre-order, `nodes[0]` is
the root, and each node's `children` is a list of **indices into `nodes`**, not of nested
objects. This fixes the document's nesting at seven containers however long the proof is;
under the nested encoding it replaced, the depth cap admitted a root and one level of
children, and no real multi-step derivation could be published at all. The cap itself is not
the problem: it exists so that a reader, including the checker, never recurses to a depth the
input chooses, and the checker's own node walk is iterative for that reason.

**Three node kinds, and they are not interchangeable.**

- `OBSERVED` - the step was seen. Cites at least one event id, and its instance is marked
  `OBSERVED`.
- `GHOST` - an obligation forces this head: the rules say the step **must** have happened
  and it was not seen. Cites no evidence; its instance has `ghost: true`.
- `LICENSED` - a licensed silent step: the rules say it **might** have happened where nobody
  could see. Cites no evidence; its instance has `observed: "LICENSED"`, `ghost: false` and
  at least one licence id. Publishing one of these as a GHOST was considered in ADR-0015 and
  rejected, because it would put a silent instance into the certificate wearing the wrong
  word.

**What it is not.** Not a timeline, not an incident narrative, and not a record of what
happened. A witness drawn from the upper program may combine silent instances that no single
consistent world realizes, so such a tree may depict an attack that could not have happened.
A subtree used twice is written twice - the node list is one tree, with no sharing. And an
empty `witnesses` array is legitimate: O12 accepts it, so the absence of a tree is never
evidence that a cut has no justification, only that none was published.

**Obligation.** O12, the longest one. For each entry: the removed control must be raised in
the published cut; removing its atoms from the cut mask must re-derive a goal under a
replayed fixpoint (`E-WITNESS-CUT`); the node list must be one tree - non-empty, every child
index strictly greater than its parent's and inside the list so no index sequence can loop,
the root nobody's child, every other node referenced exactly once (`E-WITNESS-CYCLE`); no
node's instance may appear on its own ancestor path; each node's kind must match its
instance; and every `OBSERVED` node's event ids must be present in `bundle.jsonl` with a
matching record hash (`E-WITNESS-EVENT`). O14 uses the presence of a silent node to police
the witness class.

---

## `goals`

```json
"goals":[{"derivable":false,"goal_key":"fh:a5d5a0aa48ce20536bb8942169683896098680745cfc23fff8b66404179d0db6"},
         {"derivable":false,"goal_key":"fh:ac138e1d52ad96ea832e4b9171f462d4fc34ca178f3fdbab7d9ce2628cc15019"}]
```

**What it is.** The goal library and, for each atom, whether it is derivable under the
published cut. Sorted by `goal_key`.

**What it is not.** Not a list of attacker objectives in the world; these are fact keys in
the model. `derivable: false` is a statement about a fixpoint over this rule table and this
telemetry, not about whether anything can be achieved against a real system.

**Obligation.** O9: goal keys strictly ascending, and every goal declared severed must be
absent from the published invariant `U` (`E-GOAL-MEMBER`). If no invariant was published, O9
claims nothing and checks nothing - the witness obligation carries the load instead. The
emitter additionally cross-checks `goals` against `residual` before writing.

---

## `residual`

```json
"residual":{"corridors_exhaustive":true,"corridors_open":[],
            "goals_derivable":[],"goals_severed":["fh:a5d5a0aa...","fh:ac138e1d..."],
            "program":"PMax"}
```

**What it is.** What is left reachable under the cut, as **sets**: which goals are still
derivable, which are severed, which corridors are still unsatisfied, and whether the
corridor enumeration was exhaustive. `program` says which program it was computed over.

**What it is not.** **There is no scalar residual.** No `residual_score`, no
`residual_pct`, no `coverage`, no percentage and no progress bar exists anywhere in the
schema, and the numeric-judgement ban is enforced over field names across the certificate,
the checker report and any client type. Residuals are compared by set inclusion only; two
residuals that do not contain one another are reported as incomparable, and there is no
better/worse string.

**Obligation.** No obligation of its own. The emitter checks that `residual.goals_derivable`
and `residual.goals_severed` agree exactly with `goals`, and that no goal is in both
(`E-GOAL-MEMBER`), before any bytes are produced. O0 checks its ordering and encoding like
every other member.

---

## `invariant`

```json
"invariant":{"u":["fh:...", ... 21040 entries ... ]}
```

**What it is.** `U`, the least fixpoint under the published cut: every fact derivable in the
published program with these controls raised. Strictly ascending, unique. It is present
**iff** every goal is severed - it is the object that lets a checker confirm a negative claim
in one pass instead of re-running a search.

**What it is not.** Not a list of events, and not a list of things that happened. It is the
closure of a logic program. It is also not optional when every goal is severed: a
certificate that severs every goal and omits it is `E-SCHEMA-MISSING`, and one that publishes
it while a goal is derivable is `E-SCHEMA-UNKNOWN`.

**Obligation.** O7: strictly ascending, well-formed fact ids, and every axiom of the
published program present in `U` (`E-INV-AXIOM`). O8 then checks that `U` is closed under
every published instance (`E-CLOSURE`), and O9 that no severed goal is in it. Those three
together are what makes "the goal is underivable under this cut" checkable: shrinking `U`,
inventing entries, or tampering with the cut each fail one of them, and the adversarial
corpus pins the exact code for each.

---

## `budgets`

```json
"budgets":{"bb_nodes":79,"budget_exhausted":false,"exhaustive_cuts_tested":0,
           "exhaustive_ran":false,"fixpoint_steps":105259,"step_budget":2000000}
```

**What it is.** Deterministic step counters: unit-propagation steps, branch-and-bound nodes,
the step budget they were compared against, whether it fired, whether an exhaustive
minimality probe ran, and how many cuts it tested.

**What it is not.** **Not timings, and not a performance figure.** There is no wall-clock
budget anywhere in the pipeline, because a timeout would make a flag machine-dependent and
destroy byte-identical replay. These numbers are not measurements of speed and must not be
read as any. Timings, where they exist at all, go to `runs/<id>/manifest.json`, which is not
hashed into the certificate.

**Obligation.** O14 refuses a published `premium` when `budget_exhausted` is true. O15 reads
`exhaustive_ran` and `exhaustive_cuts_tested` when `EXACT_EXHAUSTIVE` is claimed: the first
must be true and the second must equal the number of cuts of one control fewer that exist
over this catalog (`E-MIN-UNEARNED`). `fixpoint_steps` and `bb_nodes` carry no obligation;
they are reproducibility evidence.

---

## `observed_event_count` and `ghost_count`

```json
"ghost_count":61,
"observed_event_count":6
```

**What they are.** Two separate members. `observed_event_count` is the number of **distinct
records** cited by `OBSERVED` instances. `ghost_count` is the number of facts headed by an
obligation-forced instance.

**What they are not.** **A single summed member is forbidden**, and so is any rendering that
adds them. A GHOST is not an event: it never enters `observed_event_count`, any alert count,
any evidence count or any timeline rendered as observed. Neither number is a count of
anything in the world - 6 observed records here means six distinct records reached the
published instance set, not that six things happened. Note the shape of the pair in the
blackout cell: 61 GHOST facts against 6 observed records. Summing them would produce one
number, dominated by the unobserved side, that reads as an event count. That is why the two
are kept apart.

**Obligation.** O11 recounts both from `instances` and rejects a mismatch
(`E-GHOST-COUNT`). It also enforces the split that makes the counts meaningful: a `LICENSED`
instance may cite no evidence, an `OBSERVED` one must cite records and no licence, and a
`ghost: true` instance must be `LICENSED`.

---

## Disputed events, which live in the liveness document

Not in the certificate. `runs/<id>/liveness.json`, at `spectra.liveness/3` since ADR-0016,
carries three things the certificate's temporal-dispute obligation reads from the **pinned**
file:

```json
"disputed_events":[{"event_id":"ev:c9f5c0c3ef5c102158a5b662e85a6c0e",
                    "source_id":"iam_audit","t_evt_ns":"1707006600000000000"}]
```

plus `tamper_suspected` per source, and `flags.verdict_tamper_sensitive`.

**What they are.** The output of the temporal-consistency pass: the minimal set of records
whose recorded timestamp cannot be believed, because it contradicts the order that source
itself recorded or a declared temporal bound. The example above is from
`runs/vs-07e484a067863409`, the pre-registered backdate cell, where one record was moved
2700 s earlier while keeping its sequence number.

**What they are not.** **Not a tamper detection**, and no rendering may widen them into one.
The pass finds exactly one thing: a recorded timestamp that contradicts its own source's
recorded order. A consistently rewritten source, a forged chain, and suppression on a source
with no sequence number are all invisible to it, the last in principle, and are represented
only as blind volume. Flag bit 5,
`license_voided_by_suspected_tampering`, is permanently false, because **nothing is ever
voided**.

That last point is the whole design. Voiding a licence would shrink the upper program, and a
smaller upper program can only move a verdict toward the strongest value - so an adversary
who can rewrite a timestamp could buy that verdict by tampering. Under the dispute protocol
the licence is **retained in the upper program with full force** and the verdict is weakened
instead. In the backdate cell the certificate publishes the optimistic-only value where the
same cell with the pass off publishes the strongest one, and the run prints what the design
this slice did *not* implement would have produced.

**Obligation.** O14b, read from the pinned document rather than trusted from the
certificate. If the certificate publishes the strongest safety value, no source may be
tamper-suspected and `verdict_tamper_sensitive` must be false (`VRD-001`). And in the
direction that matters more: **every disputed event's source must be suspected** - a
document that disputes an event while publishing no licence over it is the shape of the
voiding attack, and is rejected.

Note that the counterfactual comparison itself is **not** in `liveness.json`. ADR-0017
records why: that file is hashed and pinned by stage S7, and a verdict is an artifact of
S10, so writing a verdict-derived member into it needs either a rewrite after the pin or a
circular dependency. The comparison is computed and reported in the prove stage. A reader of
`liveness.json` alone cannot see it; that loss of locality is accepted, and named.

---

## What is deliberately not in the certificate

- **No wall-clock time, hostname, username, path, process id, duration or `measured`
  member.** Two runs of the same inputs produce the same octets; anything machine-dependent
  would break that.
- **No probability, confidence, likelihood, risk figure, severity, criticality, priority,
  weight, rating, grade or percentile.** The field-name ban covers the schema, the checker
  report and any client type.
- **No `redundancy_index` and no `pareto_frontier`.** Both are out of scope for the slice,
  omitted entirely rather than approximated, and always named in `verdict.derived_suppressed`.
- **No lower-program corridor database.** `psi` is the upper program's.
- **No decisive-observation set, no blind-spot list, no degradation manifest.** Those are
  separate run artifacts under `runs/<id>/`, and they are not hashed into the certificate.

## What this does not do

Reading a certificate correctly does not get you any of the following, and no field in it
supports them:

- It does not tell you whether the telemetry is truthful. The bundle digest pins *which*
  records were analysed, not that they are real; in this repository they are generator
  output and the file says so.
- It does not tell you whether entity resolution was right. `er_hash` pins the mapping;
  ambiguity raises a flag rather than being resolved.
- It does not tell you whether the control catalog is complete or the rule table correct.
  Both are hand-authored, and a cut is relative to them.
- It does not tell you that grounding found every instance. The checker replays what was
  published; a derivation the grounder missed leaves no trace here.
- It does not tell you anything about an adaptive attacker.
- It does not constitute independent verification. One author, one language, one reading,
  one shared core library.
- It does not carry a measurement. Every number in it is a property of one run over one
  seeded scenario, and nothing in this repository has been benchmarked.
