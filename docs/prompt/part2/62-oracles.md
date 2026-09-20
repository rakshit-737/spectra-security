============================================================
62. GROUND TRUTH, ORACLES AND THE VALIDATION PROTOCOL
============================================================

62.0 WHY THIS SECTION EXISTS

Part I gated correctness on the concrete simulator and the ECLIPSE kernel agreeing across randomized
control configurations, while ECLIPSE §1 generates both from one guard AST. Two artifacts emitted by
one compiler agreeing proves the compiler is self-consistent. It proves nothing about whether either
artifact models an attack. Part I also made `zero false ROBUST verdicts` a build-failing invariant
without ever defining `false ROBUST`, and supplied no counterpart gate, so the invariant is satisfied
by a kernel that returns UNSAFE unconditionally.

OVERRIDES Part I: the simulator-vs-kernel agreement test is DEMOTED from a correctness gate to a
codegen regression test named `gate:codegen-regression`. It may never be described as validation, in
docs, in README, in commit messages or in CI job names. The word `oracle` is forbidden for it.

OVERRIDES Part I: validation is now carried by four named oracles (62.3-62.7) with declared, unequal
strength. Exactly one of them (Oracle R) grounds the counterfactual claim in something other than the
model. The other three bound implementation error only.

Implement every subsection below. Every numbered requirement states its `make` target or CI gate.

------------------------------------------------------------
62.1 GROUND TRUTH: SCHEMA AND ANCHORS
------------------------------------------------------------

62.1.1 The scenario generator MUST emit `groundtruth.json` beside `bundle.jsonl` for every scenario,
before any degradation operator runs. It is an input to validation only. The kernel, the checker, the
API and the frontend MUST NOT read it; enforce with a build-graph gate `gate:gt-isolation` that fails
if any crate, module or service outside `validation/` names the path or its schema types.

62.1.2 Ground truth is anchored by content, not by EventId. Degradation deletes, corrupts and
reorders records, so any ground truth keyed on EventId becomes unresolvable exactly in the cells the
research axis is about. OVERRIDES Part I: ground truth is keyed by `AnchorId`, and EventIds are a
non-authoritative side list.

```
AnchorId = blake3_128(scenario_id || u32be(step_ordinal) || semantic_kind || entity_key)
```

`entity_key` is the generator's pre-resolution canonical identifier, NOT the output of entity
resolution. Using the ER output here would make ER unmeasurable by construction.

62.1.3 Schema (`schemas/groundtruth.v1.json`, canonical JSON, integers only, floats forbidden):

```json
{
  "schema_version": 1,
  "scenario_id": "s-idp-session-replay-002",
  "generator_seed": 40277,
  "split": "HELD_OUT",
  "attack_plan": {
    "steps": [
      { "anchor": "b3:9c41...", "ordinal": 0, "semantic_kind": "credential.obtained",
        "entity_key": "user:alice@corp.lab", "t_ns": 1731000000000000000,
        "emits_event_ids": ["ev-000131","ev-000132"],
        "blocked_by": [],
        "requires_anchors": [] },
      { "anchor": "b3:1de0...", "ordinal": 1, "semantic_kind": "session.bound_replay",
        "entity_key": "session:S-7734", "t_ns": 1731000000900000000,
        "emits_event_ids": ["ev-000144"],
        "blocked_by": ["session_binding>=2", "mfa_step_up>=1"],
        "requires_anchors": ["b3:9c41..."] }
    ],
    "goal": { "anchor": "b3:ffa2...", "semantic_kind": "resource.exfiltrated",
              "entity_key": "bucket:reports", "t_ns": 1731000004100000000 }
  },
  "declared_sufficient_cuts":   [["session_binding>=2"], ["egress_seg>=1"]],
  "declared_insufficient_cuts": [["credential_rotation>=1"]],
  "suppression_class": "S0_NONE",
  "observability": { "iam_audit": "ON", "proxy_access": "ON", "host_exec": "OFF" }
}
```

62.1.4 `blocked_by` is authored in the scenario source file. `rules.toml` blocker masks are authored
separately. A lint `gate:gt-no-import` MUST fail if the scenario source imports, includes or
textually derives `blocked_by` from `controls.toml` guards or from `rules.toml`. This does not make
the two independent — one author wrote both — and 62.5.3 states that limitation in writing.

62.1.5 Every scenario MUST declare at least one `declared_sufficient_cut` and at least one
`declared_insufficient_cut`. A scenario with an empty `declared_insufficient_cuts` is rejected by
`gate:gt-schema`, because it can only ever test one direction of the verdict.

62.1.6 `suppression_class` is drawn from the closed enumeration below. It exists because Part I
promised zero false ROBUST across the whole matrix while ECLIPSE §9 concedes some suppression is
permanently invisible. OVERRIDES Part I: the zero-false-ROBUST invariant is scoped to declared
classes, and the invisible class is enumerated, counted and published rather than excluded.

```
S0_NONE          no suppression
S1_BULK_WINDOW   contiguous deletion spanning a source window (detectable: bracketing fails)
S2_CHAIN_BREAK   deletion inside a hash-chained source (detectable: sequence gap)
S3_SPARSE_BUSY   single-record deletion inside a busy window on a chained source
S4_UNCHAINED     deletion on a declared source class with no chain and no bracketing guarantee
S5_INVISIBLE     deletion with no obligation violated, no chain, no bracketing -- KNOWN UNSOUND
```

The gate in 62.8 applies to S0-S3. S4 and S5 are measured, reported per class, and their observed
frequency is written into `LIMITATIONS.md` by `make reproduce`. Claiming the gate holds over S4 or S5
is forbidden.

------------------------------------------------------------
62.2 THE GOAL CORRESPONDENCE RELATION
------------------------------------------------------------

62.2.1 Define one relation Phi mapping ground truth to kernel atoms, declared in
`validation/correspondence.toml`, hashed into every certificate as `hashes.correspondence`.

```toml
[[map]]
semantic_kind = "resource.exfiltrated"
goal_atom     = "goal.exfil(Resource)"
entity_binder = "bucket:{name} -> Resource(kind=bucket, name={name})"

[[map]]
semantic_kind = "session.bound_replay"
fact_atom     = "session.replayed(Session, T)"
entity_binder = "session:{id} -> Session(id={id})"
```

62.2.2 Phi MUST be total on the set of `semantic_kind` values that appear as a goal in any scenario.
`gate:phi-total` enumerates goal kinds across all scenarios and fails on the first unmapped kind.

62.2.3 Phi MUST be injective on goal kinds. Two goal kinds mapping to one atom collapses distinct
outcomes into one verdict. `gate:phi-injective`.

62.2.4 OVERRIDES Part I: `goal.toml` is no longer hand-authored per run. The goal atom for a run is
derived as `Phi(groundtruth.attack_plan.goal)` by `spectra goal derive`, and `gate:goal-derived`
fails the build if any scenario ships a hand-written goal atom that differs from the derived one. A
scenario author who also picks the goal can tune the cut to a hand-picked target.

62.2.5 Multi-goal scenarios carry a goal set; verdicts are emitted per goal atom. Aggregating goals
into a single verdict, a count, a ratio or a score is forbidden.

------------------------------------------------------------
62.3 THE FOUR ORACLES
------------------------------------------------------------

```
                       what it can certify                  what it CANNOT certify
  +----------------------------------------------------------------------------------+
  | R  RANGE RE-EXECUTION   the counterfactual: the goal   | anything about a scenario
  |    (62.4)               was / was not achieved with    | with no range binding;
  |                         controls really enforced by    | exhaustiveness (a failed
  |                         real services                  | run is not a proof)
  +----------------------------------------------------------------------------------+
  | C  INDEPENDENT CHECKER  that the certificate's closure | that the rule table models
  |    (62.5)               and witnesses are internally   | reality; shared rule-table,
  |                         valid; under I-A, that the     | catalog or ER error is
  |                         instance set re-derives        | invisible to it
  +----------------------------------------------------------------------------------+
  | S  SMT DIFFERENTIAL     that the Rust solver's answer  | anything at production
  |    (62.6)               on SMALL instances matches an  | scale; anything about the
  |                         encoding-independent solver    | rule semantics
  +----------------------------------------------------------------------------------+
  | M  MUTATION             that the gates are alive --    | that the gates are
  |    (62.7)               a known injected fault turns   | sufficient; only that they
  |                         a named gate red               | are not inert
  +----------------------------------------------------------------------------------+

  strength: R >> C > S > M      (M is the only one that validates the other three)
```

62.3.1 Oracle R is the only oracle whose failure falsifies a claim about the world. C, S and M bound
implementation error. Any README, paper or demo sentence that presents C, S or M as evidence that
SPECTRA's counterfactuals are correct is a banned claim (62.11).

62.3.2 Every run record carries `oracles_applied: ["R","C","S","M"]` as a subset. A scenario with
`"R"` absent MUST NOT appear in any headline table. It may appear in a model-internal consistency
table, labelled as such.

------------------------------------------------------------
62.4 ORACLE R -- RANGE RE-EXECUTION
------------------------------------------------------------

62.4.1 OVERRIDES Part I: the range is re-executed under a control configuration. Part I sections
26-29 described isolation and determinism but never control-parameterized deployment, so the flagship
claim had no oracle. Implement the pipeline:

```
  cut S (from cert) --> spectra range plan S --> overlay: compose.controls.yaml
                                              --> per-service enforcement config files
                                              --> docker compose up (isolated, no egress)
                                              --> attacker driver replays the SAME plan
                                              --> goal probe decides ACHIEVED / NOT_ACHIEVED
                                              --> N repeats --> ReExecOutcome
                                              --> compare to cert.safety --> triage (62.4.7)
```

62.4.2 Controls are made real per service. `range/enforcement.toml` binds every threshold atom to a
concrete service configuration change. Every atom in `controls.toml` MUST have an entry.

```toml
[atom."session_binding>=1"]
kind    = "ENFORCING"
service = "idp"
render  = "config/idp/binding.json"
patch   = '{"token_binding":"client_ip"}'
probe   = "probes/idp_binding_ip.sh"          # must observe the behaviour change

[atom."session_binding>=2"]
kind    = "ENFORCING"
service = "idp"
render  = "config/idp/binding.json"
patch   = '{"token_binding":"mtls_thumbprint"}'
probe   = "probes/idp_binding_mtls.sh"

[atom."egress_seg>=1"]
kind    = "ENFORCING"
service = "netpolicy"
render  = "config/netpolicy/app.nft"
patch   = 'add rule inet filter fwd oifname "ext0" ip daddr != 10.9.0.0/16 drop'
probe   = "probes/egress_denied.sh"

[atom."iam_audit>=1"]
kind    = "OBSERVING"                          # changes telemetry, never blocks a step
service = "idp"
render  = "config/idp/audit.json"
patch   = '{"audit_sink":"enabled","level":"full"}'
probe   = "probes/iam_audit_emits.sh"

[atom."trust_attestation>=1"]
kind    = "NONE_MODELED"
reason  = "no range component implements attestation; excluded from Oracle R scope"
```

62.4.3 `gate:enforcement-total` fails if any atom lacks an entry. `gate:enforcement-effective` runs
every `probe` twice, once with the atom off and once on, and fails if the probe output is identical —
this is the inert-control gate. An atom marked `NONE_MODELED` is excluded from Oracle R and every
certificate produced for a range-bound scenario carries `oracle_r_excluded_atoms: [...]`; a cut that
contains an excluded atom MUST NOT be reported as range-corroborated.

62.4.4 Re-execution is NOT deterministic. Live containers do not replay byte-identically, and Part I
asserted byte-identical replay in a way that cannot hold here. OVERRIDES Part I: byte-identical
replay is required of the seeded synthetic generator, the kernel and the checker; it is NOT required
of the range, and the range's bundles are non-normative. Every range artifact is stamped
`normative: false`.

62.4.5 Outcome decision. The goal is decided OUT OF BAND — never from the telemetry pipeline, since
telemetry is the kernel's input and deciding the goal from it is circular.

```
  decide_repeat(sigma, S) -> ACHIEVED | NOT_ACHIEVED | INDETERMINATE
     a = attacker_driver_exit_code      # 0 = driver believes goal reached
     b = goal_state_probe(sigma.goal)   # reads target service state directly
                                        # e.g. SELECT on the app DB, object presence in the store
     if a == GOAL_REACHED and b == PRESENT:      return ACHIEVED
     if a != GOAL_REACHED and b == ABSENT:       return NOT_ACHIEVED
     return INDETERMINATE                        # driver/probe disagree -> never counted
```

62.4.6 Repeats and the asymmetry. Achievement is existential, non-achievement is not.

```
  ReExec(sigma, S, N):
     rs = [decide_repeat(sigma,S) for _ in 1..N]
     if any(r == ACHIEVED for r in rs):                       return ACHIEVED
     if all(r == NOT_ACHIEVED for r in rs) and N >= N_min:     return NOT_ACHIEVED
     return INDETERMINATE
```

`N` and `N_min` are declared in `validation-policy.toml` before the first matrix run (62.10.4).
Illustrative: `N = 5`, `N_min = 5` (illustrative, not a target). A single repeat per cell is not a
result. INDETERMINATE cells are quarantined, counted, and gated by an indeterminacy ceiling (62.9.5).

62.4.7 Disagreement triage. `make triage` prints this table and refuses to exit 0 on any row marked
BUILD RED.

```
 cert.safety | ReExec(S)      | classification            | action
 ------------+----------------+---------------------------+----------------------------------
 ROBUST      | NOT_ACHIEVED   | CORROBORATED              | record; eligible for headline
 ROBUST      | ACHIEVED       | FALSE_ROBUST_EMPIRICAL    | BUILD RED. mandatory triage T1-T5
 ROBUST      | INDETERMINATE  | UNRESOLVED                | quarantine; counts to ceiling 62.9.5
 UNSAFE      | ACHIEVED       | CORROBORATED              | record
 UNSAFE      | NOT_ACHIEVED   | see 62.4.8                | split by GHOST content
 UNSAFE      | INDETERMINATE  | UNRESOLVED                | quarantine
 OPTIMISTIC  | any            | NOT_GATED                 | record only; never headline
```

Mandatory triage branches for FALSE_ROBUST_EMPIRICAL, in order, each recorded in
`docs/research/triage/<run_id>.md`:

```
 T1 ENFORCEMENT DEFECT   the range did not actually enforce the atom -> fix enforcement.toml,
                         add a probe assertion; the verdict was not wrong, the experiment was.
 T2 BLOCKER DEFECT       rules.toml gives the corridor the wrong blocker mask -> fix rules.toml,
                         and the scenario becomes TUNED for the current rules hash (62.10).
 T3 COVERAGE DEFECT      the range achieved the goal by a technique no rule models -> the rule
                         table is incomplete; add the rule, mark TUNED, log the gap in
                         LIMITATIONS.md as a measured coverage miss.
 T4 LICENSE DEFECT       the licensed envelope excluded a hypothesis the range realized ->
                         liveness or silent-envelope logic is unsound; fix and re-run the whole
                         matrix, not just this cell.
 T5 CORRESPONDENCE DEFECT Phi maps the goal to an atom that does not capture the outcome -> fix
                         correspondence.toml; every prior certificate is invalidated by hash.
```

FORBIDDEN repairs: deleting the scenario, narrowing the goal, adding a soundness flag so the run is
no longer presented as ROBUST, raising a cap so the run trips `grounding_capped`, or moving the
scenario from HELD_OUT to DEV. `gate:triage-integrity` compares the scenario inventory and the goal
hashes across commits and fails on any of these transitions without a ledger entry (62.10.5).

62.4.8 UNSAFE with NOT_ACHIEVED splits by whether the counterexample tree contains a GHOST node.

```
 all leaves are real EventIds (no GHOST)  -> FALSE_UNSAFE_MODEL_INDUCED  -> BUILD RED
      the kernel asserts an entirely observed path the real services do not permit. That is a
      rule-table or guard defect, not conservatism.
 tree contains >= 1 GHOST (licensed) step -> FALSE_UNSAFE_LICENSE_INDUCED -> MEASURED, not zero
      designed conservatism. Counted, published per degradation cell, and bounded by 62.9.3.
```

62.4.9 Range scope, stated honestly. Oracle R applies only to scenarios with a range binding. Declare
the range-bound subset in `validation/range-bound.txt`. `make validate` prints the fraction of the
matrix covered by Oracle R. Illustrative coverage line: `oracle_r covers 3/11 scenario families`
(illustrative, not a target). Claiming that the counterfactual is validated on scenarios outside this
set is a banned claim.

------------------------------------------------------------
62.5 ORACLE C -- THE INDEPENDENT CHECKER
------------------------------------------------------------

62.5.1 Part I asserted the Go checker `shares no code with the Rust solver` while also requiring it to
re-ground from hashed inputs, which is a second full implementation of the rule language. Part I never
priced that. Decide explicitly and record the decision in the certificate.

```
  checker_independence: HANDWRITTEN | GENERATED      # certificate field, not optional
```

62.5.2 DECISION I-A (HANDWRITTEN). The Go module contains its own guard-expression lexer, parser,
type checker, evaluator, liveness derivation and semi-naive grounder. Requirements:
- `gate:checker-buildgraph` fails if the Go module's file set includes any artifact produced by the
  Rust codegen, or any generated file at all. Inputs are exactly: hashed input text files
  (`rules.toml`, `controls.toml`, `bundle.jsonl`, `liveness.json`, `goal`, `correspondence.toml`) and
  the certificate.
- `gate:guard-difffuzz` runs a seeded differential fuzz between the Rust and Go guard evaluators over
  randomly generated guard ASTs and random control assignments; any divergence fails the build.
- `gate:grounding-difffuzz` diffs the two groundings' instance-set hashes on generated micro-bundles.
- Permitted claim: `the certificate's instance set was independently re-derived by a separately
  written implementation`.
- Cost, stated so it is not discovered late: a second grounder is work of the same order as the Rust
  grounder, and every rule-language change costs two edits plus a differential re-fuzz.

62.5.3 DECISION I-B (GENERATED). The Go grounder is emitted from the same guard AST. Then
independence is FICTIONAL and MUST be written down as such:
- `docs/checker-scope.md` states verbatim: `the checker validates the certificate against the
  instance set the kernel published and against guard semantics generated from the same AST; it does
  not independently re-derive that set, and a shared misreading of a guard is invisible to it`.
- The certificate carries `checker_independence: GENERATED` and the checker refuses to print any
  string containing `independent`.
- FORBIDDEN under I-B: `independently verified`, `independent checker`, `second implementation`,
  `cross-validated`. `gate:banned-phrases` greps README, docs, UI strings, demo script and CI job
  names for these tokens and fails while the field is `GENERATED`.
- The reduced claim under I-B is exactly: `certificate-relative validation` — closure holds over the
  published instance set, witnesses re-derive, and no cut smaller than |S| satisfies Psi.

62.5.4 Under BOTH decisions, the checker's scope excludes: rule-table error, control-catalog omission,
entity-resolution error and correspondence error. `docs/checker-scope.md` lists these four and the
README links to it from the first screen.

62.5.5 Minimality is reported separately from safety. OVERRIDES Part I: the certificate carries
`minimality: EXHAUSTIVE | PSI_RELATIVE | UNVERIFIED`. The checker sets `EXHAUSTIVE` only when it ran
real fixpoints for all cuts of cardinality < |S|. Printing `no smaller cut exists` on a
`PSI_RELATIVE` certificate is forbidden in every surface; the permitted string there is
`no smaller cut satisfies the enumerated corridor set`.

------------------------------------------------------------
62.6 ORACLE S -- SMT DIFFERENTIAL (TEST ONLY)
------------------------------------------------------------

62.6.1 Z3 is a test-only differential oracle on small instances. It is NEVER in the runtime path.
`gate:no-smt-runtime` fails if any crate, module, service image or the checker binary declares a
dependency on z3, and `make verify-no-smt` MUST build and pass every runtime gate with the z3 package
absent from the image.

62.6.2 Encoding. For a grounded program P, cut S and goal g, emit the Horn/propositional encoding:

```
 for each rule instance i:   (AND_{b in body(i)} b) AND blocked(i,S)==false  ->  head(i)
 for each atom a in A:       x_{k,l+1} -> x_{k,l}                (level implication)
 query 1 (safety):           UNSAT( P[S] AND g )                 # goal unreachable under S
 query 2 (minimality):       for every S' with |S'| < |S|: SAT( P[S'] AND g )
```

62.6.3 Query 1 must agree with the kernel's fixpoint verdict. Query 2 must agree with the kernel's
minimality claim. Divergence fails `gate:smt-differential`. Bounds are declared, small, and enforced
by a harness assertion, not by hope. Illustrative bounds: instances <= 400, |A| <= 12, cuts enumerated
exhaustively (illustrative, not a target).

62.6.4 Oracle S certifies only that the Rust solver's answer on small instances matches an
encoding-independent solver. It certifies nothing about the rule semantics, nothing at production
scale, and is not evidence for any counterfactual claim.

------------------------------------------------------------
62.7 ORACLE M -- MUTATION (GATE LIVENESS)
------------------------------------------------------------

62.7.1 A green gate is decoration until a known fault turns it red. Implement `make mutate`, which
applies each mutant below to a pristine tree, runs the named gate, and asserts the gate FAILS.
A surviving mutant fails the build. Kill rate below 100% of the mandatory catalog fails the build.

```
 id    mutation                                                     gate that MUST go red
 ----  -----------------------------------------------------------  --------------------------
 M01   drop one blocker bit from a rule instance's mask             gate:false-robust
 M02   treat a BLIND source window as LIVE                          gate:false-robust
 M03   make every source unconditionally LIVE                       gate:nonvacuity-licensing
 M04   make every source unconditionally BLIND                      gate:nonvacuity-yield
 M05   skip one obligation axiom (session.used => session.issued)   gate:false-robust
 M06   return ROBUST whenever the fixpoint is empty                 gate:false-robust
 M07   return UNSAFE unconditionally                                gate:nonvacuity-yield
 M08   off-by-one in the Dowling-Gallier body counter               gate:smt-differential
 M09   emit a cut one atom larger than the B&B optimum              gate:smt-differential
 M10   truncate Psi to its first corridor                           gate:checker-minimality
 M11   silently drop malformed telemetry records instead of         gate:nonvacuity-licensing
       quarantining them (manufactures blind windows)
 M12   ignore the level implication x_{k,l+1} -> x_{k,l}            gate:antitonicity
 M13   let the goal probe read the telemetry pipeline               gate:oracle-r-outofband
 M14   merge two distinct entity_keys in ER                         gate:er-quality
 M15   accept a certificate whose licenses are not implied by       gate:adversarial-certs
       liveness.json
```

62.7.2 Each mutant is a committed patch under `validation/mutants/`, applied by `git apply`, never a
runtime flag. A runtime mutation flag is itself a path to a false verdict in production.

62.7.3 `make mutate` is a nightly gate, not per-PR. M01, M06, M07 and M10 additionally run per-PR as
the smoke subset.

------------------------------------------------------------
62.8 GATE PREDICATE: FALSE ROBUST
------------------------------------------------------------

62.8.1 Define a run `r = (sigma, cell d, bundle B, certificate C)` with `C.safety = ROBUST`, cut `S`,
goal atom `g = Phi(groundtruth(sigma).attack_plan.goal)`.

```
 FALSE_ROBUST_EMPIRICAL(r)  <=>  ReExec(sigma, S, N) == ACHIEVED
 FALSE_ROBUST_MODELED(r)    <=>  exists a path pi over groundtruth(sigma).attack_plan.steps
                                 from an ordinal-0 step to the goal, respecting requires_anchors,
                                 such that for every step s in pi: atoms(s.blocked_by) INTERSECT S = {}
```

62.8.2 `gate:false-robust` fails the build if, over the declared gate scope,
`count(FALSE_ROBUST_EMPIRICAL) > 0` OR `count(FALSE_ROBUST_MODELED) > 0`.

62.8.3 Gate scope. OVERRIDES Part I: the scope is `HELD_OUT scenarios x completeness 100%..30% x
suppression classes S0-S3`. S4 and S5 are measured and published, not gated. Scoping is stated in
the gate's own output, so a reader of CI logs sees the scope beside the result.

62.8.4 Honesty requirement. `FALSE_ROBUST_MODELED` compares two artifacts written by one author. It
is a consistency check, not empirical validation. `make validate` prints both counts on separate
lines with the qualifier `(model-internal)` on the MODELED line. Reporting a single combined
false-ROBUST figure is forbidden.

62.8.5 A run whose certificate carries any soundness-affecting flag (`grounding_capped`,
`er_ambiguous`, `subset_minimal_only` is NOT soundness-affecting, see 62.5.5) cannot be ROBUST and is
therefore outside this predicate. That escape route is closed by 62.9.4, not here.

------------------------------------------------------------
62.9 THE MISSING COUNTERPART: FALSE UNSAFE AND NON-VACUITY
------------------------------------------------------------

`return UNSAFE` passes 62.8. So does licensing everything, and so does tripping a cap flag on every
run. OVERRIDES Part I: the following five gates are mandatory and a green 62.8 without them is
meaningless. All thresholds live in `validation-policy.toml` and are author-declared policy, fixed
before the first matrix run (62.10.4).

62.9.1 THE CLEAN-TELEMETRY CONTROL SET. Define `CTRL` = every scenario at completeness 100%,
suppression class S0, paired with each of its `declared_sufficient_cuts` (positive controls) and each
of its `declared_insufficient_cuts` (negative controls). CTRL is the set on which the kernel has
every advantage: full telemetry, no tampering, ground truth known.

62.9.2 `gate:nonvacuity-yield` — ROBUST YIELD FLOOR.

```
 yield = |{ (sigma,S) in CTRL_positive : C.safety == ROBUST }| / |CTRL_positive|
 FAIL if yield < policy.robust_yield_floor
```

Illustrative floor: `robust_yield_floor = 0.90` (illustrative, not a target). Also:

```
 detect = |{ (sigma,S) in CTRL_negative : C.safety == UNSAFE }| / |CTRL_negative|
 FAIL if detect < policy.unsafe_detect_floor
```

Illustrative floor: `unsafe_detect_floor = 1.00` (illustrative, not a target). A kernel that returns
UNSAFE always fails the first; a kernel that returns ROBUST always fails the second.

62.9.3 `gate:nonvacuity-licensing` — LICENSED VOLUME BOUND. The blindness premium is manufactured by
silent instances, so permissive licensing inflates the headline finding while scoring perfectly on
62.8.

```
 lic_ratio(run)   = |silent rule instances| / |observed rule instances|
 FAIL if max over runs at completeness 100% of lic_ratio > policy.lic_ratio_clean_ceiling
 FAIL if median over runs in any cell of lic_ratio > policy.lic_ratio_cell_ceiling
 FAIL if per-source blind volume is NOT non-decreasing as completeness drops 100% -> 30%
 FAIL if S_rob is NOT non-decreasing under set inclusion as completeness drops
```

Illustrative ceilings: `lic_ratio_clean_ceiling = 0.05`, `lic_ratio_cell_ceiling = 0.60`
(illustrative, not a target). The two monotonicity conditions are the same gate that catches the
self-calibrated liveness threshold inflating under deletion. Additionally publish
`FALSE_UNSAFE_LICENSE_INDUCED` rate per cell and fail if it exceeds
`policy.false_unsafe_license_ceiling`.

62.9.4 `gate:nonvacuity-flags` — FLAGGED-RUN CEILING. Part I let a flag exempt a run from the gate,
which makes flags a free escape hatch.

```
 flagged_share = |{ runs with any soundness-affecting flag }| / |all runs in scope|
 FAIL if flagged_share > policy.flagged_share_ceiling
```

Illustrative ceiling: `flagged_share_ceiling = 0.10` (illustrative, not a target). Additionally:
`gate:flag-ratchet` fails if `flagged_share` increases between two commits without a ledger entry.

62.9.5 `gate:nonvacuity-indeterminacy` — Oracle R indeterminacy ceiling.

```
 indeterminate_share = |{ range-bound runs with ReExec == INDETERMINATE }| / |range-bound runs|
 FAIL if indeterminate_share > policy.indeterminate_ceiling
```

Illustrative ceiling: `indeterminate_ceiling = 0.05` (illustrative, not a target). A flaky goal probe
otherwise hides every disagreement.

62.9.6 `gate:baselines` — every headline number is reported beside three baselines on the identical
matrix: (a) naive timestamp-ordering correlation, (b) ECLIPSE with licenses disabled, (c) ECLIPSE with
obligation axioms disabled. A result reported without its three baseline deltas fails the docs build.

------------------------------------------------------------
62.10 HELD-OUT SPLIT, FROZEN RULES, OVERFIT LEDGER
------------------------------------------------------------

62.10.1 SPLIT. Every scenario carries `split ∈ {DEV, HELD_OUT, RED}`. DEV is tunable. HELD_OUT is
authored and hash-committed BEFORE the rules hash it will be evaluated under. RED is the adversarial
corpus (owned by the Part II kernel threat-model section) and must never yield ROBUST. Headline
numbers come from HELD_OUT only; DEV numbers are published in a separate table labelled `TUNED`.

62.10.2 FROZEN RULES. Maintain `rules.lock`:

```toml
schema_version   = 1
frozen_at_commit = "3b91c0a"
frozen_at_utc    = "2026-03-02T00:00:00Z"
rules_ast_hash   = "b3:5f2c..."      # canonical AST encoding, NOT raw file bytes
axioms_hash      = "b3:7ae1..."
controls_hash    = "b3:0d44..."
correspondence_hash = "b3:99b2..."
```

62.10.3 `gate:leakage` compares, for every HELD_OUT scenario, the commit that introduced the scenario
against the commit that last changed `rules_ast_hash`, `axioms_hash`, `controls_hash` or
`correspondence_hash`. If any of those changed AFTER the scenario's introducing commit, the scenario
is automatically re-labelled `TUNED` by the tool, its number is removed from every headline table, and
CI fails if a headline table still cites it. Re-labelling is performed by the tool; a human editing
the split field by hand fails `gate:split-integrity`.

62.10.4 PRE-REGISTRATION. `validation-policy.toml` and `docs/research/preregistration.md` are
committed before the first matrix run and pin: every threshold in 62.9, the metric definitions, the
seed list (multiple seeds per cell, variance reported), the scenario inventory and the hypotheses.
`gate:prereg-immutable` fails if any pinned value changes while results exist for it, unless a ledger
entry (62.10.5) records the change with a reason and the affected results are deleted and re-run.

62.10.5 OVERFIT LEDGER. `docs/research/overfit-ledger.tsv`, append-only, one row per rule, axiom,
catalog, correspondence or policy edit made after any scenario existed:

```
date        commit   artifact         change                          trigger_scenario     triage  split_effect
2026-03-11  9a1f2c3  rules.toml       add rule r_pkce_downgrade       s-idp-oauth-004      T3      s-idp-oauth-004 -> TUNED
2026-03-14  c07be21  axioms/fd.toml   obligation fd.read => fd.open   s-proc-exfil-001     T3      s-proc-exfil-001 -> TUNED
2026-03-19  44d9e18  enforcement.toml fix egress_seg nft rule         s-net-egress-002     T1      none (experiment defect)
2026-03-25  b12aa70  policy           lic_ratio_cell_ceiling 0.5->0.6 (matrix re-run)      --      all cells re-run
```

`gate:ledger-complete` fails if any of the four hashes changed in a commit with no corresponding
ledger row. `gate:ledger-append-only` fails on any modification or deletion of an existing row.

62.10.6 The README status table renders the HELD_OUT count, the TUNED count and the ledger row count
programmatically from these artifacts. A shrinking HELD_OUT count is visible to every reader.

------------------------------------------------------------
62.11 CLI SURFACE AND NEGATIVE REQUIREMENTS
------------------------------------------------------------

62.11.1 `make validate` runs the protocol and prints a scoped report. Values below are illustrative,
not a target; the target is that every line is printed from executed code.

```
$ make validate
== SPECTRA validation protocol ==
 rules.lock      b3:5f2c...   frozen_at 3b91c0a
 policy          b3:1a08...   preregistered 2026-03-02
 split           HELD_OUT 7   TUNED 4   RED 9          (illustrative, not a target)
 oracles         R(3/11 families)  C(HANDWRITTEN)  S(nightly)  M(nightly)

 gate:false-robust           scope HELD_OUT x 100..30% x S0-S3
     FALSE_ROBUST_EMPIRICAL  0
     FALSE_ROBUST_MODELED    0   (model-internal)
                                                                              PASS
 gate:nonvacuity-yield       robust_yield 0.94 >= 0.90 | unsafe_detect 1.00    PASS
 gate:nonvacuity-licensing   lic_ratio clean 0.02 | cell max 0.41 | monotone   PASS
     FALSE_UNSAFE_MODEL_INDUCED    0                                           PASS
     FALSE_UNSAFE_LICENSE_INDUCED  0.17 <= 0.25 (measured, not gated to zero)
 gate:nonvacuity-flags       flagged_share 0.06 <= 0.10                        PASS
 gate:nonvacuity-indeterminacy  0.02 <= 0.05                                   PASS
 gate:leakage                no post-freeze edits against HELD_OUT             PASS
 gate:ledger-complete        4 edits, 4 rows                                   PASS

 UNGATED, MEASURED AND PUBLISHED:
     suppression class S4 frequency 0.11   S5 frequency 0.03
     scenarios outside Oracle R scope: 8/11 families -- counterfactual NOT corroborated there
```

62.11.2 Per-PR tier: `gate:false-robust` on a declared sampled subset, `gate:nonvacuity-yield`,
`gate:nonvacuity-flags`, `gate:leakage`, `gate:ledger-complete`, mutation smoke subset. Nightly tier:
full matrix, Oracle R, Oracle S, full `make mutate`. The sampling plan is declared in
`validation-policy.toml` and is itself covered by `gate:prereg-immutable`.

62.11.3 NEGATIVE REQUIREMENTS. Each is enforced by `gate:banned-phrases` over README, `docs/`, UI
strings, the demo script, API field names and CI job names, or by the named gate.

- Do not call simulator-vs-kernel agreement an oracle, a validation, or evidence of correctness.
- Do not publish a single combined false-ROBUST number merging EMPIRICAL and MODELED.
- Do not claim the counterfactual is validated for any scenario outside the Oracle R scope list.
- Do not claim independence while `checker_independence: GENERATED`.
- Do not print `no smaller cut exists` on a `PSI_RELATIVE` certificate.
- Do not report a false-UNSAFE rate of zero; conservatism is designed in and a zero means the
  measurement is broken. `gate:nonvacuity-licensing` fails if the measured rate is exactly zero
  across every cell, which indicates the metric is not being computed.
- Do not let the goal probe, the attacker driver or the triage tool read `bundle.jsonl`.
  `gate:oracle-r-outofband`.
- Do not emit any probability, confidence, severity, score or normalized quality index anywhere in
  this protocol. Rates defined here are counts over declared denominators, and every published rate
  prints its numerator, denominator and scope.
- Do not resolve a FALSE_ROBUST_EMPIRICAL by deleting, re-splitting or re-goaling the scenario, or by
  raising a cap so the run trips a flag. `gate:triage-integrity`.
- Do not admit a scenario to HELD_OUT after the rules hash it is evaluated under was written.
- Do not report any headline number from a single seed per cell.
- Do not let `make validate` exit 0 while any INDETERMINATE or quarantined cell is uncounted.
