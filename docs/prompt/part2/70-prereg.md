============================================================
70. PRE-REGISTRATION, HELD-OUT PROTOCOL AND THE OVERFIT LEDGER
============================================================

70.0 THE DEFECT THIS SECTION CLOSES

One author writes the scenario generator, the ground truth it emits, the rule table, the obligation
axioms, the control catalog and the liveness configuration. Every gate in Part I therefore certifies
internal consistency and nothing else, while reading to an outside reviewer as empirical validation.
A reader cannot distinguish "the kernel reconstructs attacks" from "the rules were edited until the
fixtures passed", because both produce the same green CI.

OVERRIDES Part I: Part I §5-8 and §48-51 permit results to be produced from whatever scenarios exist
at the time of the run. They no longer do. From this section on, a measured number is publishable only
if it carries a pool label, a pre-registration id, a frozen-rules hash and a seal-and-unseal history.
Numbers without that provenance are development telemetry, not results, and may not appear in
`README.md`, `docs/`, the paper draft, the demo, the UI or any commit message.

This protocol does not make cheating impossible. A solo author can always regenerate a pool or rewrite
history. What it does is make every act of contamination an explicit, irreversible, committed event
with a name and an ancestor commit, so that contamination is visible rather than deniable. State that
limit in `docs/research/preregistration.md` verbatim; do not claim the protocol provides blinding,
independent replication or adversarial review, because it provides none of those.

Implement everything in this section before any rule is authored. The order is load-bearing: if
`rules/rules.toml` exists in the repository before the pre-registration commit, the protocol is dead
and cannot be retrofitted.

------------------------------------------------------------
70.1 ROLE SEPARATION BY TIME AND HASH
------------------------------------------------------------

There is no second person, so separation of duties is implemented as separation in commit ancestry
plus cryptographic sealing. Define five authoring roles and forbid any single commit from touching
artifacts belonging to more than one:

| Role | Owns | May read | May never read |
|---|---|---|---|
| R1 PROTOCOL | `docs/research/preregistration.md`, `research/prereg.toml` | nothing | any scenario, any result |
| R2 GENERATOR | scenario generator, degradation operators, ground-truth emitter | DEV pool only | HELD-OUT bundles while sealed |
| R3 MODELLER | `rules/rules.toml`, `axioms/`, `controls.toml`, liveness config, goal library | DEV pool only | HELD-OUT bundles while sealed, HELD-OUT results |
| R4 HARNESS | metric code, runner, results schema, baseline arms | pool labels only | ground truth, except through the metric API |
| R5 REPORTER | `docs/results/`, README tables, paper draft | complete results artifact | nothing (writes nothing executable) |

Enforcement: `make check-roles` parses the commit's changed-file set against `research/roles.toml`
and fails on a cross-role commit. A cross-role commit is not a style problem; it is the mechanism by
which held-out contamination happens silently.

------------------------------------------------------------
70.2 THE PRE-REGISTRATION DOCUMENT
------------------------------------------------------------

Two files, committed together, in the same commit, before any rule exists:

- `docs/research/preregistration.md` — prose for humans: research questions, what would falsify each
  one, what the protocol cannot establish.
- `research/prereg.toml` — machine-readable and hashed. Every results row cites its `prereg_id` and
  the BLAKE3 of this file's canonical encoding.

Canonical encoding for hashing: the file bytes, LF line endings, no trailing whitespace, UTF-8
without BOM. `make prereg-hash` prints it. Editing a single comment changes the hash; that is intended
and is why amendments are append-only files rather than edits (70.6).

```toml
# research/prereg.toml
schema_version   = 1
prereg_id        = "PR-001"
title            = "Control-cut reconstruction under telemetry degradation"
status           = "OPEN"          # OPEN -> FROZEN -> CLOSED; monotone, never reversed
rules_absent_at_authoring = true   # asserted here, verified by make prereg-check against git

[pools]
dev_scenarios_max      = 12        # binding constraint on the tuned pool size
heldout_families       = ["F1_idp_token_theft", "F2_service_acct_pivot",
                          "F3_consent_grant_abuse", "F4_stale_cred_reuse"]
heldout_seed_domain    = "PR-001/heldout"
redteam_pool_ref       = "sec-66-redteam"   # adversarial fixtures, see the kernel threat model section

[replication]
seeds_per_cell         = 5         # binding minimum, not a measurement
replicate_index_range  = [0, 4]
statistic              = "median"
dispersion             = "iqr"     # IQR mandatory; a bare mean is a build failure (70.4)
single_seed_reporting  = "forbidden"

[degradation]
axis            = "record_completeness"
levels_pct      = [100, 90, 80, 70, 60, 50, 40, 30]
operators       = ["delete", "delay", "duplicate", "reorder", "corrupt", "suppress"]
cell            = "(scenario, operator, level, arm, replicate)"

[arms]
required = ["A_eclipse", "B0_trivial_all", "B0_trivial_none", "B1_time_order",
            "B2_no_licenses", "B3_no_obligations", "B4_max_licenses",
            "B5_dev_frequency_prior", "C_ceiling_clean"]
```

OVERRIDES Part I section 50.2: the eleven-operator catalog (`none`, `delete_random`,
`delete_targeted`, `reorder`, `duplicate`, `delay_jitter`, `corrupt_field`, `strip_identity`,
`backdate`, `forge_provenance`, `silence`) is replaced by the six operators declared above, and
`research/prereg.toml` rather than `bench/manifests/*.json` is the binding matrix. An implementer
following Part I would execute `backdate`, `forge_provenance`, `strip_identity` and `none` cells that
no metric in 70.3 and no arm in 70.9 consumes, against a matrix file that 70.6 freezes and 70.10
forbids editing.

OVERRIDES Part I section 50.1 item 2: the rule that `completeness` applies only to data-removing
operators while shape-preserving operators sweep their own intensity knob and record
`completeness = 1.0` is replaced by the single `levels_pct` axis crossed with every operator in the
cell key above. An implementer following Part I would emit every `duplicate`, `reorder` and `corrupt`
row at completeness 1.0 and produce one level where the cell key declares eight.

OVERRIDES Part I section 50.3: the requirement to present `delete_random` and `delete_targeted`
adjacent at the same scale in every figure and table, and never to report `delete_random` alone, is
replaced by the single `delete` operator, which carries no random/targeted split. An implementer
following Part I would look for an adjacency the declared operator set cannot produce.

`make prereg-check` (runs on every push, and is the first gate in CI) verifies:

1. `research/prereg.toml` parses and `schema_version` is known.
2. The commit that first added `research/prereg.toml` is an **ancestor** of the commit that first
   added `rules/rules.toml`, `axioms/` or `controls.toml`, determined by
   `git log --diff-filter=A --format=%H -- <path> | tail -1` plus `git merge-base --is-ancestor`.
   Commit dates are attacker-controlled and are never used for ordering. Ancestry is.
3. The pre-registration commit's tree contains no rule table, no axiom file, no control catalog and
   no scenario bundle.
4. Every `metric.id` referenced by any row in `results/results.jsonl` exists in this file or in an
   amendment.

------------------------------------------------------------
70.3 METRIC DEFINITIONS ARE DECLARED BEFORE THEY ARE COMPUTED
------------------------------------------------------------

A metric that is defined after the curve is seen is not a metric. Every quantity the project will ever
publish is declared here with its numerator, denominator, estimator, aggregation, suppression rule and
pre-declared decision rule. The harness refuses to emit a results row whose `metric_id` is not
declared, and the docs build refuses to render a number whose `metric_id` is not declared.

```toml
[[metric]]
id            = "M1_false_robust_count"
tier          = "primary"
family        = "safety"
definition    = """Number of (scenario, operator, level, replicate) cells in which the certificate
                 carries safety=ROBUST for cut S while the ground-truth correspondence of §62 shows
                 the goal is attained under S in the re-executed run."""
denominator   = "none; reported as an absolute count with the offending cell list attached"
estimator     = "exact enumeration over executed cells"
suppress_when = ["grounding_capped", "corridor_capped", "er_ambiguous", "minimality=UNVERIFIED"]
direction     = "lower_is_better"
decision_rule = "count > 0 on HELD-OUT fails the build; count > 0 on DEV opens a ledger entry"

[[metric]]
id            = "M2_robust_yield"
tier          = "primary"
family        = "non_vacuity"
definition    = """Fraction of cells where ground truth shows the cut genuinely severs the chain AND
                 the kernel returns safety=ROBUST. Exists solely to make M1 non-gameable: a kernel
                 that always answers UNSAFE scores perfectly on M1 and zero here."""
denominator   = "cells where ground truth shows the cut severs the chain"
decision_rule = "declared floor is set in the FREEZE commit, before unseal, and never afterwards"

[[metric]]
id            = "M3_false_unsafe_rate"
tier          = "primary"
family        = "one_sidedness"
definition    = """Fraction of cells where ground truth shows the cut severs the chain and the kernel
                 returns UNSAFE or OPTIMISTIC_ONLY. Measures over-licensing, the exact bias that
                 inflates the blindness premium."""

[[metric]]
id            = "M4_premium_precision" # and M4b_premium_recall
tier          = "primary"
family        = "headline"
definition    = """Over the well-defined blindness premium (controls in EVERY minimum cut of P_max and
                 in NO minimum cut of P_min): precision = |premium ∩ ground-truth-necessary-only-
                 because-blind| / |premium|."""
suppress_when = ["corridor_capped", "minimality=UNVERIFIED"]

[[metric]]
id            = "M5_chain_edge_f1"
tier          = "secondary"
family        = "reconstruction"
definition    = "Precision/recall over derived causal edges against generator ground-truth edges."
reported_as   = "precision and recall separately; F1 additionally, never F1 alone"

[[metric]]
id            = "M6_blind_volume_monotonicity_violations"
tier          = "secondary"
family        = "soundness_probe"
definition    = "Count of (scenario, source) pairs where per-source blind volume decreases as
                 completeness drops."
decision_rule = "any violation fails the build on both pools; it indicates unsound license logic"

[[metric]]
id            = "M7_dos_exact_rate"
tier          = "secondary"
definition    = "Share of decisive-observation-set answers proved exact rather than greedy-covered."

[[metric]]
id            = "M8_adversarial_reject_rate"
tier          = "secondary"
definition    = "Share of the forged-certificate corpus the Go checker rejects. Must be 1."
```

OVERRIDES Part I section 50.7 item 13: the invariant that rows with `eclipse_verdict = ROBUST` and
`block_miss = 1` number exactly zero across the entire executed matrix, as one absolute build gate, is
replaced by `M1_false_robust_count`'s pool-split decision rule above — a nonzero count fails the build
on HELD-OUT and opens an overfit-ledger entry on DEV. This also supersedes Part I section 5.3 H0 and
section 5.4 for the DEV pool: a DEV false ROBUST is no longer a corpus-wide falsification filed to
`research/results/falsifications/`. An implementer following Part I would stop the build on exactly
the DEV cells that 70.7 expects to be diagnosed and recorded as a `CORRECTION`, `COVERAGE` or
`THRESHOLD` change.

OVERRIDES Part I section 5.7: the prohibition on the words "accuracy", "detection rate", "precision"
and "recall" for ECLIPSE outputs — permitted only when scoped by name to the optional ML anomaly
baseline — is replaced by the metric ids declared above; `M4_premium_precision`, `M4b_premium_recall`
and `M5_chain_edge_f1` are computed over `A_eclipse` and are the headline, and no ML anomaly baseline
is among the arms 70.9 requires. An implementer who also builds the Part I section 8.6 string linter
over UI strings, API schemas and report templates would have it reject this section's primary metrics.

```toml
[[hypothesis]]
id        = "H1"
statement = "ECLIPSE with licenses (A_eclipse) produces strictly fewer false ROBUST verdicts than
             B2_no_licenses across levels below 100% completeness."
outcome   = "M1_false_robust_count, per arm, per level"
falsified_if = "B2 matches or beats A at every level; then the license machinery is decoration and
                docs/ must say so."

[[hypothesis]]
id        = "H2"
statement = "The blindness premium is not an artifact of permissive licensing: M4 precision for
             A_eclipse exceeds that of B4_max_licenses."
falsified_if = "B4 matches A; then the premium is a licensing artifact and the headline is withdrawn."

[[hypothesis]]
id        = "H3"
statement = "A_eclipse beats B5_dev_frequency_prior on M4 on HELD-OUT scenarios."
falsified_if = "the prior matches the kernel; then the result is 'the catalog is small', not 'the
                kernel reconstructs'."
```

OVERRIDES Part I section 5.3: the hypotheses bound to the ids H1, H2 and H3 in
`research/questions.toml` (premium strictly increasing in telemetry loss and zero at 100%
completeness; every premium control attributable to a License, removed on re-run in at least 80% of
attributed instances; `|D| <= 3` on at least half of the degraded runs) are replaced, under the same
ids, by the three statements declared above, and it is these that `<<VERDICT:H1>>`, `<<VERDICT:H2>>`
and `<<VERDICT:H3>>` in 70.12 resolve to. An implementer following Part I would bind the section 5.4
falsifier rows, the section 5.6 `[[H1]]` claim markers and the section 8.8 `LIMITATIONS.md` status
table to these ids and report a verdict about a different hypothesis than the one measured.

Negative requirement: no metric may be a confidence, probability, severity, risk score, likelihood or
any scalar that collapses a set-valued output. Residual reachability is a set (§4H of the ECLIPSE spec
as amended by the solver well-definedness section) and appears in `results.jsonl` as a sorted list of
goal atom ids and corridor ids, never as a number. `make lint-metrics` greps the metric declarations
and the results schema for the banned nouns and fails on a hit.

------------------------------------------------------------
70.4 SEEDS, REPLICATION AND VARIANCE
------------------------------------------------------------

A single run per cell is not a result. The binding minimum is five replicates per cell (binding
constraint, not a measurement); raise it in the pre-registration only, never in a commit that also
touches the harness.

OVERRIDES Part I section 49.7 item 14: the minimum of `n = 10` seeds per reported cell, below which a
claim is not publishable and the renderer emits `NOT REPORTABLE`, is replaced by the five-replicate
minimum above, and the `sample_size_min = 40` field of the Part I section 5.5 research registry does
not bind rows produced under this protocol. An implementer who builds the section 49.7 floor would
have the renderer refuse every held-out cell this section mandates, including the `n=5` headline rows
in 70.12.

Seed derivation is a pure function so that no RNG state is shared between cells and any cell can be
re-run in isolation and byte-identically:

```
seed(cell) = u64_le( blake3( prereg_id ‖ 0x00 ‖ pool ‖ 0x00 ‖ scenario_id ‖ 0x00 ‖
                             operator ‖ 0x00 ‖ level_pct_u8 ‖ arm_id ‖ 0x00 ‖ replicate_u8 )[0..8] )
```

Reporting rules, enforced by `make lint-tables`:

- Every published cell carries median and IQR. A mean without dispersion fails the docs build.
- Replicate count is printed next to every statistic as `n=<k>`.
- If any replicate in a cell errored, timed out on its deterministic step budget, or tripped a
  suppression flag, the cell is reported as PARTIAL with the flag list; it is never silently averaged
  over the survivors.
- No smoothing, no curve fitting, no interpolation between completeness levels. Plot the points.

------------------------------------------------------------
70.5 SCENARIO POOLS AND THE SEALING PROTOCOL
------------------------------------------------------------

Three disjoint pools. Membership is declared in `research/pools.toml` and is append-only.

| Pool | Purpose | May a rule be edited in response to it? | May it appear in README? |
|---|---|---|---|
| DEV | rule authoring, debugging, fixture-driven development | yes, with a ledger entry (70.7) | only labelled TUNED, never as a headline |
| HELD-OUT | headline numbers | never | yes, and only this pool |
| RED-TEAM | adversarial fixtures that must never yield ROBUST | yes, with a ledger entry | yes, as a pass/fail list |

Sealing makes "generated before the rules were authored, and not looked at" a checkable property
rather than a promise.

```
research/heldout/
  spec.toml              # scenario families, seed domain, degradation cells. Committed in the clear.
  sealed.tar.age         # ciphertext of the generated bundles + ground truth. Committed.
  sealed.manifest        # BLAKE3 of the ciphertext, of the plaintext tar, and of spec.toml
  SEALED                 # marker file; contains the sealing commit SHA
  key.age-identity       # ABSENT until unseal. Its later addition is the unseal event.
  unseal.jsonl           # append-only ledger of unseal events
```

`make seal-heldout` (run once, before any rule exists):

1. Generates the held-out bundles and ground truth from `spec.toml` into a temp dir.
2. Tars them with fixed ordering, fixed mtimes (0), fixed uid/gid, no extended attributes.
3. Encrypts with `age` using a freshly generated X25519 identity written **outside the repository**,
   to a path recorded in `sealed.manifest` as a name only.
4. Writes `sealed.manifest`, `SEALED`, deletes the plaintext.
5. Fails if the working tree contains `rules/rules.toml`, `axioms/*` or `controls.toml`.

OVERRIDES Part I section 51.4 item 7: the held-out scenario set (`S80..S85`) authored **after the rule
table is frozen** is replaced by a held-out pool generated and sealed before any rule table, axiom
file or control catalog exists, as guard 5 above enforces. The same reordering supersedes Part I
section 8.2 IV5 and section 8.4 M3, whose held-out fixture family from unseen seeds is re-run in every
release job: here the pool is opened once, by the UNSEAL event, and never resealed. An implementer
following Part I would author the held-out set after the freeze, at which point `make prereg-check`
and `make seal-heldout` both refuse it and the protocol cannot be recovered without a new
pre-registration.

Because generation is deterministic, anyone can later re-derive the plaintext from `spec.toml` and the
generator at the sealing commit and confirm it hashes to `sealed.manifest.plaintext_blake3`. That is
the verifiable claim: the contents were fixed at the sealing commit. Encryption makes them unreadable
to the author at authoring time by construction, provided the identity file is kept out of the repo
and out of the shell history; state in `docs/research/preregistration.md` that this is a
self-discipline mechanism, not a security boundary against the author.

`make unseal-heldout` refuses unless all of the following hold, and appends an irreversible record:

- `rules.lock` exists and its `frozen_at_commit` is an ancestor of HEAD (70.6).
- The working tree is clean and HEAD is pushed.
- `research/overfit-ledger.jsonl` passes `make check-ledger`.
- The unseal record is committed **before** any held-out run: sequence is unseal → commit → run.

```jsonl
{"event":"UNSEAL","pool":"HELD-OUT","prereg_id":"PR-001","at_commit":"<sha>",
 "rules_lock_blake3":"<hex>","sealed_manifest_blake3":"<hex>","reason":"milestone M7 headline run",
 "utc":"<iso8601>","monotonic_index":1}
```

Once unsealed, the pool is permanently TUNED-adjacent: it may be re-run, but it can never again
produce headline numbers after any subsequent rules edit. A new headline requires a **new** sealed
pool built from new seed domains, sealed under a new pre-registration amendment. There is no resealing.

------------------------------------------------------------
70.6 THE FROZEN-RULES RULE
------------------------------------------------------------

Headline numbers come only from held-out scenarios executed under a rule table whose hash was fixed
before the held-out set was opened.

`rules.lock` is generated by `make freeze-rules` and committed:

```toml
schema_version   = 1
prereg_id        = "PR-001"
frozen_at_commit = "<sha, filled by the commit hook>"
guard_ast_blake3      = "<hex>"   # canonical AST encoding, NOT raw file bytes
axioms_ast_blake3     = "<hex>"
controls_catalog_blake3 = "<hex>" # includes the bit-position assignment table
liveness_config_blake3  = "<hex>" # quantile choice, n_min, baseline calibration ref
goal_library_blake3     = "<hex>"
er_config_blake3        = "<hex>"
generator_blake3        = "<hex>" # scenario generator source tree
metric_code_blake3      = "<hex>" # the harness's metric implementations
```

Hashing the canonical guard AST rather than file bytes means a comment or a reordering does not
invalidate a freeze, while any semantic change does. OVERRIDES Part I: Part I left `hashes.rules`
ambiguous between file bytes and AST; for freeze purposes it is the canonical AST encoding, and the
certificate must carry both so a reader can tell cosmetic drift from semantic drift.

`make check-freeze` runs on every results-producing invocation and fails the run, not just the report,
when any `rules.lock` field disagrees with the run manifest. The refusal is a hard error with a
diff, never a warning:

```
$ make report-headline
check-freeze: FAIL
  guard_ast_blake3
    rules.lock : 7c1e...9a2f  (frozen at commit 4b81e2c)
    this run   : 2d90...41bb
  3 rule instances differ: R014 body, R022 guard, R031 added
  HEADLINE REFUSED. This run may be reported as pool=DEV only.
  To produce a new headline: amend PR-001, seal a new held-out pool, re-freeze.
make: *** [report-headline] Error 1
```

A freeze may be broken. Breaking it is a normal engineering event and must be cheap to do and
expensive to hide: `make refreeze` requires a ledger entry, increments `rules.lock.generation`, and
marks every existing held-out result row `superseded=true` in `results/results.jsonl` rather than
deleting it. Superseded rows stay in the artifact and stay renderable; the docs build shows them in a
"superseded" table. Deleting data is the only way to hide a bad result, which is exactly the property
being engineered.

------------------------------------------------------------
70.7 THE OVERFIT LEDGER
------------------------------------------------------------

Every rule, axiom, guard, threshold, liveness parameter, control level or ER heuristic added or changed
**in response to a scenario that failed** is recorded. No exceptions for "obvious bugs": an obvious bug
in a rule table authored by the same person who authored the scenario is indistinguishable from
fitting, and the ledger is how that ambiguity is made visible instead of resolved by self-report.

`research/overfit-ledger.jsonl`, append-only, one object per change:

```jsonl
{"schema_version":1,
 "entry_id":"OL-0007",
 "utc":"<iso8601>",
 "commit":"<sha of the change commit>",
 "trigger":{"kind":"failing_scenario","pool":"DEV","scenario_id":"F2_service_acct_pivot",
            "cell":{"operator":"suppress","level_pct":60,"replicate":2},
            "failure":"M1_false_robust_count=1: kernel returned ROBUST for cut
                       {session_binding>=2}; re-executed range shows goal attained via
                       service-account token reuse across host boundary"},
 "diagnosis":"obligation axiom AX-019 (token.used => token.issued) did not fire across host
              boundaries because the head was indexed by (principal,host) not (principal)",
 "change":{"artifacts":["axioms/AX-019.toml"],
           "guard_ast_before":"7c1e...9a2f","guard_ast_after":"2d90...41bb",
           "kind":"CORRECTION"},
 "generality":{"claim":"the change is not scenario-specific",
               "evidence":"AX-019 now fires in 3 DEV scenarios it did not fire in before; no
                           scenario-id, entity-id, timestamp or seed appears in the new axiom",
               "literal_scan":"PASS"},
 "scenarios_marked_tuned":["F2_service_acct_pivot","F1_idp_token_theft"],
 "heldout_state":"SEALED",
 "post_unseal_delta":null}
```

`change.kind` is a closed enum and the distinction is reported, not editorialised:

| kind | meaning | effect on the pool |
|---|---|---|
| `CORRECTION` | the rule was wrong about the modelled semantics, independent of the fixture | marks trigger scenario TUNED |
| `COVERAGE` | a phenomenon the rule table did not model at all is now modelled | marks trigger scenario TUNED |
| `THRESHOLD` | a numeric parameter was moved | marks trigger scenario TUNED **and** requires a sensitivity sweep over the parameter, published |
| `SPECIALISATION` | the change is conditioned on something only this scenario exhibits | **forbidden**; `make check-ledger` fails the build on this value |

`make check-ledger` is a per-push gate and enforces:

1. For every commit that changes a frozen-set artifact and is a descendant of the first scenario
   commit, there exists exactly one ledger entry whose `commit` matches and whose
   `guard_ast_before` equals the parent commit's AST hash and `guard_ast_after` equals this commit's.
   A rules change with no ledger entry fails the build. This is the load-bearing gate of the section.
2. The ledger is append-only: `git diff` against the merge base must show additions at the end of the
   file only. Any modification or deletion of an existing line fails the build.
3. `generality.literal_scan` is recomputed, not trusted: the diff of the changed artifact is scanned
   for any scenario id, entity id, event id, absolute timestamp or seed from any pool. A hit fails
   the build with the offending literal quoted.
4. Every `scenarios_marked_tuned` id is flipped to `tuned=true` in `research/pools.toml`, and tuned is
   monotone — a scenario never becomes untuned.
5. After an unseal, every entry with `heldout_state:"SEALED"` must have `post_unseal_delta` filled in
   by `make ledger-backfill`, recording how each metric moved on held-out for the change. Entries
   whose corrections did not generalise are the most valuable rows in the repository and must be
   rendered in `docs/research/overfitting.md` under the heading "changes that did not generalise",
   not buried.

`docs/research/overfitting.md` is generated from the ledger by `make docs-overfit`; it is never
hand-edited, and the docs build fails if it is stale relative to the ledger hash.

------------------------------------------------------------
70.8 TUNED VS HELD-OUT REPORTING
------------------------------------------------------------

Pool labels travel with the data, not with the prose. Every results row:

```json
{"result_id":"R-000412","prereg_id":"PR-001","metric_id":"M4_premium_precision",
 "pool":"HELD-OUT","arm":"A_eclipse","scenario_id":"F3_consent_grant_abuse",
 "operator":"delete","level_pct":70,"replicate":3,"n":5,
 "value":"<<MEASURED:M4_premium_precision>>","dispersion":"<<MEASURED:M4_iqr>>",
 "flags":["corridor_capped"],"suppressed":true,"superseded":false,
 "rules_lock_generation":1,"rules_lock_blake3":"<hex>","run_manifest_blake3":"<hex>",
 "unseal_index":1,"tuned_inputs":false}
```

OVERRIDES Part I sections 48.6 and 48.2: the Pydantic v2 results schema at one row per (scenario, arm,
seed, operator, completeness, repeat), written to `bench/results/<run_id>/results.jsonl` plus
`results.parquet` under a DuckDB DDL whose `eclipse_verdict VARCHAR` holds a bare
`ROBUST|OPTIMISTIC_ONLY|UNSAFE|null`, in a directory git-ignored except `results/INDEX.json`, is
replaced by the committed, accumulating `results/results.jsonl` above, keyed per metric by
`result_id`, whose schema rejects a bare `ROBUST` in `safety`. An implementer following Part I would
git-ignore the artifact that every `README.md` and `docs/` numeral must resolve into, so no
`result_id` resolves in a fresh clone.

OVERRIDES Part I section 48.8: rendering each document from the `results.parquet` of a single run,
under "do not copy a number from an older run into a newer document", is replaced by rendering every
table and figure from the complete `results/results.jsonl` across runs and generations. An implementer
following Part I would drop the superseded rows that 70.6 requires to stay renderable, because they
belong to an earlier run than the one being rendered.

Rules, all gated:

- `make docs` renders every table and figure programmatically from the complete
  `results/results.jsonl`. There is no manual table in `docs/`. Omitting an unflattering cell
  therefore requires deleting a row, which the results-artifact hash in the run manifest exposes.
- Every table is rendered twice, side by side, DEV and HELD-OUT, with the DEV column headed
  `TUNED (rules were edited against these scenarios; not a result)`. A table with only one pool
  present fails `make lint-tables` unless it declares `single_pool_reason`.
- `README.md` may quote HELD-OUT rows only. `make check-readme-pool` extracts every numeral and every
  `<<MEASURED:...>>` token in `README.md`, resolves it to a `result_id`, and fails if the row's pool
  is not HELD-OUT, if `suppressed` is true, if `superseded` is true, or if the row is unresolvable.
- Any numeral appearing anywhere in `README.md`, `docs/`, the UI, the demo script or a figure caption
  must resolve to a `result_id`. Hard-coded numerals fail the build. This closes the Part I defect
  where illustrative figures in the prompt itself were copied into documentation as if measured.
  OVERRIDES Part I section 48.8 item 24: the `scripts/check_generated.py` exemptions that allow a
  numeric literal outside a GENERATED region when it sits in a `codeblock`, in a version string, or on
  a line ending with `<!-- static: <reason> -->` are removed for these surfaces; there is no
  exemption. An implementer who keeps the `<!-- static: -->` hatch reopens the defect this rule
  closes, because an illustrative figure passes the check by carrying a stated reason.
- Verdict strings in results and UI carry their scope binding, per the verdict algebra section; a
  results row whose `safety` field is a bare `ROBUST` string is rejected by the schema.

------------------------------------------------------------
70.9 BASELINES AND THE FAIRNESS CONTRACT
------------------------------------------------------------

No accuracy claim is falsifiable without a reference point. SPECTRA is currently compared to nothing,
which means "reconstructs correctly under degradation" has no content. OVERRIDES Part I: the benchmark
harness (§48-51) is redefined as multi-arm. A single-arm run may not produce any row with
`tier="primary"`.

Minimum required arms. All are mandatory; none may be dropped without a pre-registration amendment
that states the reason.

| Arm | What it does | Why it exists |
|---|---|---|
| `B0_trivial_all` | returns the cut containing every control at max level | upper bound on safety, zero information; any arm that cannot beat it is useless |
| `B0_trivial_none` | returns the empty cut | lower bound; calibrates M3 |
| `B1_time_order` | reconstructs the chain by timestamp ordering plus entity-identifier adjacency, then names the controls whose blocker bits touch any edge on the chain. No grounding, no licenses, no fixpoint | the "what a competent engineer does with grep and sort" reference. If SPECTRA does not beat it, the kernel is unjustified |
| `B2_no_licenses` | full ECLIPSE with `P_max := P_min` | isolates the contribution of the silent envelope |
| `B3_no_obligations` | full ECLIPSE with the obligation axioms disabled | isolates the contribution of the axiom set |
| `B4_max_licenses` | full ECLIPSE with `silent_possible` forced true on every rule and liveness forced BLIND everywhere | maximally permissive licensing; upper bound on premium inflation. H2 dies if this arm matches the real one |
| `B5_dev_frequency_prior` | ignores the bundle entirely; returns the k controls that appeared most often in DEV-pool cuts, k = median DEV cut size | catches the failure where the catalog is so small that guessing wins |
| `C_ceiling_clean` | full ECLIPSE run on the undegraded bundle for the same scenario | ceiling, not a competitor. Every table that shows it labels it CEILING (uses telemetry the other arms do not have) |

Fairness contract. Each arm receives exactly the inputs marked `Y` and no others; the harness
constructs the input set per arm and the arm process is executed with a read-only mount containing
only those paths. An arm that opens a path outside its set fails the run.

| Input | A_eclipse | B0 | B1 | B2 | B3 | B4 | B5 | C_ceiling |
|---|---|---|---|---|---|---|---|---|
| degraded `bundle.jsonl` | Y | – | Y | Y | Y | Y | – | – |
| undegraded `bundle.jsonl` | – | – | – | – | – | – | – | Y |
| `liveness.json` | Y | – | – | – | Y | forced-BLIND | – | Y |
| ER output (same config, same hash) | Y | – | Y | Y | Y | Y | – | Y |
| `rules.toml` @ `rules.lock` | Y | – | – | Y | Y (axioms off) | Y | – | Y |
| `controls.toml` @ `rules.lock` | Y | Y | Y | Y | Y | Y | Y | Y |
| `goal.toml` from the goal library | Y | Y | Y | Y | Y | Y | Y | Y |
| DEV-pool cut statistics | – | – | – | – | – | – | Y | – |
| generator ground truth | – | – | – | – | – | – | – | – |
| deterministic step budget | identical across arms, declared in `prereg.toml` | | | | | | | |
| seeds | identical `seed(cell)` per replicate, arm id included in the derivation | | | | | | | |

OVERRIDES Part I section 49.2 item 4: the requirement that every arm sees the perturbed bundle and
never the pristine one, with the resulting `bundle_hash` asserted equal across arms and a projection
violation aborting the cell, is replaced by the rows above, in which `C_ceiling_clean` alone reads the
undegraded `bundle.jsonl` and therefore necessarily carries a different `bundle_hash`. The equal-hash
assertion still holds across the other eight arms; an implementer carrying section 49.2 forward
unchanged would abort every cell of a mandatory arm.

Additional binding clauses:

1. No arm reads ground truth. Ground truth enters only through the metric code (R4), after all arms
   have written their outputs, and the metric code is hashed into `rules.lock`.
2. All arms emit the same output object: `{cut, safety, minimality, corridors, residual_goal_atoms,
   flags}`. B1 and B5 emit `minimality: UNVERIFIED` and `safety: UNSUPPORTED`; they are scored on M4
   and M5, and are scored on M1 only with `minimality` ignored. Scoring an arm on a metric it
   structurally cannot produce is forbidden and `make lint-arms` fails on it.
3. Tie-breaking is identical across arms: the total atom order defined in the solver
   well-definedness section, lexicographic-minimum representative.
4. Arms are executed in a fixed order with fixed CPU and memory limits, and the arm id is in every
   log line. No arm gets a retry that another does not.
5. An arm may not be tuned after seeing held-out results. Baseline tuning is a ledger event with
   `kind:"THRESHOLD"` and marks the baseline itself TUNED, which is reported.

Negative requirement: do not describe any of these arms as "state of the art", "prior work" or
"competitors". They are ablations and trivial references authored by the same person. `docs/` states
that SPECTRA has been compared against no external tool, and that a favourable comparison against
one's own ablations is evidence that the machinery does work, not evidence that the machinery is best.

------------------------------------------------------------
70.10 AMENDMENTS
------------------------------------------------------------

`research/prereg.toml` is never edited after the sealing commit. Changes are new files
`research/amendments/PR-001-A<NN>.toml`, append-only, each carrying:

```toml
amendment_id = "PR-001-A02"
supersedes   = []                      # metric ids or hypotheses this amendment replaces
reason       = "M5 as declared double-counted duplicate edges under the duplicate operator"
authored_at_commit = "<sha>"
heldout_state_at_authoring = "SEALED"  # SEALED | OPEN — computed by make, not typed
effect = "CONFIRMATORY"                # CONFIRMATORY iff SEALED; EXPLORATORY iff OPEN
```

`effect` is computed, never declared by hand. Any amendment authored after the first UNSEAL event
makes every outcome it touches EXPLORATORY for the remaining life of that pool. Exploratory outcomes
are rendered in a separate section of `docs/research/results.md`, are excluded from `README.md` by
`make check-readme-pool`, and may never be described with the word "shows", "demonstrates" or
"validates".

------------------------------------------------------------
70.11 TIMELINE AND GATE MAP
------------------------------------------------------------

```
 commit ancestry ──────────────────────────────────────────────────────────────▶

 [PR]  prereg.toml + preregistration.md committed
   │   guard: no rules/, no axioms/, no controls.toml in this tree
   ▼
 [SEAL] heldout spec.toml + sealed.tar.age + sealed.manifest + SEALED
   │    guard: identity file outside the repo; plaintext deleted
   ▼
 [DEV]  rule authoring, grounding, liveness, kernel, checker ── loops on DEV pool
   │    guard: every frozen-artifact commit has a matching overfit-ledger entry
   │    guard: no read of research/heldout/ except spec.toml (enforced by make check-roles)
   ▼
 [FREEZE] rules.lock committed (generation N)
   │    guard: make check-ledger green; DEV results snapshot written
   ▼
 [UNSEAL] key committed, unseal.jsonl appended, committed BEFORE any run
   │    guard: clean tree; rules.lock ancestor of HEAD
   ▼
 [RUN]  held-out matrix, all arms, all seeds → results/results.jsonl (pool=HELD-OUT)
   │    guard: make check-freeze on every row
   ▼
 [REPORT] make docs; README quotes HELD-OUT only
        any later rules edit ⇒ make refreeze ⇒ generation N+1
                             ⇒ all pool=HELD-OUT rows marked superseded=true
                             ⇒ new headline requires a NEW sealed pool
```

| Gate (make target) | Tier | Fails when |
|---|---|---|
| `check-roles` | per-push | a commit spans two authoring roles |
| `prereg-check` | per-push | prereg missing, unparseable, or not an ancestor of the rule table |
| `check-ledger` | per-push | a frozen-artifact change has no matching, append-only ledger entry; `SPECIALISATION`; literal scan hit |
| `check-freeze` | every results run | run manifest disagrees with `rules.lock` |
| `lint-metrics` | per-push | undeclared metric id; banned scalar noun; residual reachability collapsed to a number |
| `lint-arms` | per-push | an arm scored on a metric it cannot produce; an arm reading an input outside its fairness row |
| `lint-tables` | docs build | mean without dispersion; missing `n=`; single-pool table without a declared reason |
| `check-readme-pool` | docs build | a README numeral resolves to DEV, suppressed, superseded, exploratory or nothing |
| `check-ledger-backfill` | nightly | post-unseal deltas not filled in |
| `check-pools-disjoint` | per-push | a scenario id appears in two pools, or a tuned flag was cleared |

------------------------------------------------------------
70.12 CLI TRANSCRIPT
------------------------------------------------------------

All numerals below are illustrative, not a target; they are placeholders in the committed script and
are replaced at runtime by measured values.

```
$ make check-ledger
check-ledger: scanning 41 commits since first-scenario commit 9ac1f02 (illustrative, not a target)
  a71c3de  axioms/AX-019.toml         -> OL-0007  kind=CORRECTION   literal_scan=PASS
  c02e881  rules/rules.toml           -> OL-0008  kind=COVERAGE     literal_scan=PASS
  e19b740  rules/rules.toml           -> NO ENTRY
check-ledger: FAIL
  commit e19b740 changed a frozen-set artifact with no overfit-ledger entry.
  guard_ast before=7c1e...9a2f after=b4d2...0e77
  Add an entry with `make ledger-add --commit e19b740` and state what failed and what changed.
make: *** [check-ledger] Error 1

$ make unseal-heldout
unseal-heldout: rules.lock generation=1 frozen_at=4b81e2c  ancestor-of-HEAD: yes
unseal-heldout: overfit ledger: 9 entries, append-only: yes
unseal-heldout: working tree clean: yes
unseal-heldout: sealed.manifest plaintext_blake3 = 5f0a...c31d
unseal-heldout: re-deriving held-out plaintext from spec.toml @ seal commit ... match
unseal-heldout: WARNING — this is irreversible. After this event, any change to a frozen artifact
                supersedes every HELD-OUT result produced under generation 1.
unseal-heldout: appended UNSEAL monotonic_index=1 to research/heldout/unseal.jsonl
unseal-heldout: commit this file now; the runner refuses a held-out run from a dirty tree.

$ make report-headline
check-freeze: OK (generation 1)
arms: A_eclipse B0_trivial_all B0_trivial_none B1_time_order B2_no_licenses B3_no_obligations
      B4_max_licenses B5_dev_frequency_prior C_ceiling_clean
cells: 4 scenarios x 6 operators x 8 levels x 9 arms x 5 replicates (illustrative, not a target)
M1_false_robust_count  HELD-OUT  A_eclipse = <<MEASURED:M1_A>>   [floor: 0]
M1_false_robust_count  HELD-OUT  B2_no_licenses = <<MEASURED:M1_B2>>
M2_robust_yield        HELD-OUT  A_eclipse = <<MEASURED:M2_A>> (n=5, IQR <<MEASURED:M2_A_iqr>>)
M4_premium_precision   HELD-OUT  A_eclipse = <<MEASURED:M4_A>>   B4_max_licenses = <<MEASURED:M4_B4>>
suppressed rows: <<MEASURED:suppressed_n>> (corridor_capped)
H1: <<VERDICT:H1>>   H2: <<VERDICT:H2>>   H3: <<VERDICT:H3>>
wrote results/results.jsonl (+<<MEASURED:rows_n>> rows, pool=HELD-OUT, generation=1)
```

------------------------------------------------------------
70.13 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS
------------------------------------------------------------

1. Do not write `rules/rules.toml`, `axioms/*` or `controls.toml` before the pre-registration commit.
   If they already exist when this section is implemented, delete them, implement the protocol, and
   re-author them; do not backdate, do not rewrite history to fake ancestry.
2. Do not read, decrypt, list or hash the held-out plaintext before the UNSEAL event. Do not write a
   convenience target that does so.
3. Do not edit a rule, axiom, guard, threshold or ER heuristic in response to a held-out failure.
   Held-out failures are results. Record them and publish them.
   OVERRIDES Part I section 50.7 item 13: for a held-out failure, the instruction to stop, do not
   publish, write the counterexample cell to `bench/results/<run_id>/VIOLATIONS.json`, add it as a
   regression fixture and fix the kernel is replaced by recording and publishing the failure with the
   frozen artifacts untouched. An implementer following Part I would fix the kernel, which under 70.6
   forces `make refreeze` and marks every held-out row `superseded=true`, burning the sealed pool
   while withholding the result this section requires to be published.
4. Do not delete a results row. Supersede it.
5. Do not modify or reorder a line in the overfit ledger. Append only.
6. Do not report a DEV-pool number in `README.md`, in the demo, in the UI header, in a commit message
   or in a paper abstract, even when labelled.
7. Do not report a single-seed cell, a mean without dispersion, or a smoothed curve.
8. Do not aggregate across pools. There is no "overall" number spanning DEV and HELD-OUT.
9. Do not introduce a metric after seeing results without an amendment; do not present an EXPLORATORY
   outcome as confirmatory.
10. Do not describe the baseline arms as prior work, competitors, or the state of the art.
11. Do not claim "held-out validation", "independent evaluation", "blind evaluation", "externally
    validated", "pre-registered study" (say "pre-registered protocol, self-administered"), or
    "generalises to real telemetry". The generator, the rules and the ground truth still come from
    one author; sealing constrains the order of operations, not the representativeness of the data.
12. Do not state or imply that a passing protocol means the kernel is correct about reality. The
    strongest honest sentence available is: "Headline numbers were produced on scenarios generated
    and hash-sealed before the rule table was authored, under a rule-table hash frozen before the
    seal was opened, with every post-hoc rule change recorded in a published ledger."
13. `docs/research/preregistration.md` must contain a section titled "What this protocol does not
    establish" listing, at minimum: single-author generator bias, that the scenario families were
    chosen by the same person who wrote the rules, that the held-out seal is self-administered, and
    that no external dataset or external tool was used.
