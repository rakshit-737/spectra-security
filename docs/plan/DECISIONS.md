# SPECTRA — decision queue

Status: **140 open decisions. None answered.**

## What this is

The 140 unresolved Part I / Part II conflicts from `CONFLICTS.md`, each triaged by the earliest milestone whose implementation it blocks, by severity, and reduced to one answerable question with a safe default.

**Severity** means what deciding wrongly costs. HIGH: code is rewritten or published results are invalidated. MEDIUM: a contained refactor. LOW: cosmetic or local.

**The default column is what gets implemented if the question is never answered.** Every default was chosen by the triaging agent to be the conservative option — the one that fails closed, keeps a claim weaker, or keeps a type wider. Proceeding on defaults is legitimate; silently proceeding on a guess is not, which is why each one is written down.

## Where the decisions land

| Blocks | HIGH | MEDIUM | LOW | Total |
|---|---:|---:|---:|---:|
| M0 | 3 | 13 | 3 | 19 |
| M1 | 14 | 2 | 0 | 16 |
| M2 | 20 | 4 | 0 | 24 |
| M3 | 5 | 2 | 0 | 7 |
| M4 | 19 | 3 | 0 | 22 |
| M5 | 13 | 4 | 1 | 18 |
| M6 | 6 | 4 | 1 | 11 |
| M7 | 6 | 5 | 0 | 11 |
| M8 | 0 | 1 | 0 | 1 |
| M9 | 0 | 4 | 2 | 6 |
| M10 | 0 | 4 | 1 | 5 |

**66 decisions block M0-M3**, of which **42 are HIGH severity**. Those are the ones worth answering before the vertical slice is built; the rest can ride on their defaults until the milestone that needs them.

---

## 1. Blocks M0-M3 — answer these first

### Blocks M0

**D093 · HIGH · 70 pre-registration**

Is `research/questions.toml` retired so that `research/prereg.toml` plus its append-only amendments is the only claim registry (yes), with verify-claims reimplemented as a wrapper over check-readme-pool and lint-metrics (no)?

- Context: Part I §5.5 makes `research/questions.toml` "the single source of truth. Nothing in the README, the UI, the paper draft, or any docstring may state a numeric research claim that is not bound here", with `status` (UNMEASURED|SUPPORTED|FALSIFIED|INCONCLUSIVE) changeable only by `spectra research ingest`, a `[[H1]]` …
- Default if unanswered: Yes: retire questions.toml at the first commit, make prereg.toml the sole registry with hashed ancestry ordering instead of prereg_date, keep the no-escape-hatch claim linter over the new registry, and regenerate LIMITATIONS.md section 10 from results.jsonl …

**D119 · HIGH · 74 build and CI**

Does the real-service integration tier get its own gate id on a container-local compose network with no default-route egress, tiered T2, while `--network=none` stays absolute for the T1 build-offline gate only?

- Context: Part I §43.7 forbids mocking: "Do NOT mock PostgreSQL, Redis, or the Rust kernel in the integration tier. Use real services from compose.test.yml", ~300 integration tests own "ingest->resolve->ground->prove->cert"; §46.2 supplies them as GitHub services: postgres/redis; §46.4 makes ci/python (integration) a …
- Default if unanswered: Yes: G-OFF-001 build-offline keeps `--network=none` unchanged in T1; integration tests with real Postgres/Redis get a separate gate id in ci/gates.toml at T2 on a compose network with no default route, with §74.3 stating explicitly that a container-local …

**D121 · HIGH · 74 build and CI**

Does the published languages.toml keep .NET (added to toolchain-b, because Spectra.StateModel generates transitions.{json,sql,py,rs,sv,vhd} for four other languages) and delete Swift/Objective-C outright — yes or no?

- Context: §74.0 states "Any language absent from languages.toml gets no toolchain, no image layer and no CI job, and its source directory must not exist", and §74.11.4 forbids "a fifth toolchain image, a per-language image, or a language whose toolchain cannot be installed offline into one of the four images". The four image …
- Default if unanswered: Keep .NET in toolchain-b; delete Swift/Objective-C and their gates; keep Solidity/Verilog/VHDL/YARA/Z3 only if each passes the §32.1 load-bearing test, and delete each dropped language's directory and its dependent gate in the same PR.

**D000 · MEDIUM · 57 vocabulary**

Is the normative atom budget `sum(m_k) <= 64` (Part I and V9), yes or no — with §57.8's `sum(m_k) + |controls| <= 64` corrected to match?

- Context: Three formulas are in play. §22.2: "The global atom budget is `Sigma_k m_k <= 64`", with `E_ATOM_BUDGET` above it. §57.8: "`make lint-vocab` recomputes `sum(m_k) + |controls|` and fails the build when it exceeds 64 (check V9)." §57.10's V9: "sum over controls.toml of (m_k + 1) minus |controls| <= 64" — which equals …
- Default if unanswered: Adopt `sum(m_k) <= 64`, fix §57.8's prose, and have V9 print both counts in its output.

**D007 · MEDIUM · 57 vocabulary**

Does V7 land as warn-only until every unregistered load-bearing concept (stream, adapter, alias, snapshot, watermark, obligation, guard AST, trace, finding, the ILLEGAL/POLICY_VIOLATING/ANOMALOUS classification, …) has a Table A row, yes or no?

- Context: §57.1 rule 1 says every concept has exactly one canonical name, and V7 fails the build on "any identifier segment appearing in >= 2 of the five language trees and >= 8 times total that is neither in `vocab.toml` nor in `vocab-allow.toml`". At least a dozen load-bearing Part I concepts have no Table A row: evidence …
- Default if unanswered: Land V7 warn-only, extend vocab.toml with the missing concepts in the same change as §57, and flip V7 to required once the unregistered count is zero.

**D016 · MEDIUM · 58 determinism**

Is a tenth workflow file `determinism.yml` added (hosting `repro-check`, `repro-matrix` and `lint-determinism`) with `docs/ci/required-checks.md` and branch protection amended in the same commit, and the self-hosted `wsl2` runner restricted to non-fork nightly/tag triggers?

- Context: Part I §46.1 says "Create exactly these files under `.github/workflows/`" and enumerates nine; §46.4 fixes the branch-protection required-check list and adds `tools/ci/verify_required_checks.py`, "which queries the GitHub API and fails if the configured list drifts from the document" (`docs/ci/required-checks.md`); …
- Default if unanswered: Yes to all three: add `determinism.yml`, amend §46.1's list and required-checks.md in the same change, and never run fork PR code on the self-hosted runner.

**D017 · MEDIUM · 58 determinism**

Does `make reproduce` survive as a distinct target (two fresh containers, diff all `artifacts/**`) alongside `make repro-check` (same machine, perturbed conditions, stage digests), yes or no?

- Context: Part I §4.1 defines `make reproduce` ("run full pipeline twice in fresh containers, diff all artifact hashes", < 30 min, exit 0 means byte-identical), §4.4(3) requires it to produce identical hashes for `cert.json`, `liveness.json` and every `artifacts/**` file, and the §4.7 Definition-of-Done checklist has the line …
- Default if unanswered: Yes: keep both as distinct targets, gate pushes on `repro-check`, and make the DoD checklist require `make reproduce` plus a green `repro-matrix` artifact id.

**D092 · MEDIUM · 69 boundaries**

Is `rust/spectra-ffi` deleted (cert IO folded into spectra_core, browser target served by rust/spectra-wasm) and `python/spectra_eclipse` reduced to a subprocess client plus cert IO, yes or no?

- Context: 69.1.2 and 69.21.2 ban pyo3/ctypes/cdylib boundaries outright, which removes the entire purpose of two mandated components: 32.4's `rust/spectra-ffi/ cdylib + PyO3 bindings consumed by python/spectra_eclipse` and 32.3's `python/spectra_eclipse/ thin ctypes/PyO3 binding to the Rust kernel + cert IO`. Part I 32.1 …
- Default if unanswered: Yes: delete spectra-ffi and its unsafe_code lint exemption, replace python/spectra_eclipse with services/kernel_client.py plus cert IO, and update the polyglot rationale table and the `doctor` output accordingly.

**D102 · MEDIUM · 71 claims**

Is the single authoring site for every forbidden-wording list `docs/banned.toml`, with CONTRIBUTING.md, the anti-slop checklist, docs/DEVELOPMENT.md and the PR template generated from it, yes or no?

- Context: Part I requires the project to publish lists of forbidden words: §55.1 forbids topics "`ai`, `agent`, `enterprise`, `production-ready`"; §55.5 forbids badges "'made with love', 'awesome', 'production ready', 'AI powered'"; §56.1 row 21 is "No probability, confidence, cost-mass or invented dollar figure in any output …
- Default if unanswered: Yes: generate all prohibition lists from docs/banned.toml, and additionally add those four files to §71.4's `exempt_paths` so the unwaivable gate cannot go permanently red.

**D108 · MEDIUM · 72 narration**

Is `SPECTRA_NARRATION_LLM` the one canonical env var, read only by the build/CI layer, with `make verify-no-llm` replacing `make no-llm` and `audit-llm` dropped from `make verify` in favour of 72.12.2's build-graph assertion?

- Context: Part I §2.3.2 (01-preamble.md) mandates a CI job `no-llm` running with `SPECTRA_LLM=disabled` and network namespaces cut; the make-target table defines `make no-llm` (<12 min) and `make audit-llm` (<30 s), and `make verify` is defined as lint + test + gates + audit-scope + audit-stubs + audit-llm; the milestone …
- Default if unanswered: Yes on all four: one env var name, consumed by make/CI only (the narrator's own switch is the Cargo feature plus narration.toml), `verify-no-llm` succeeds `no-llm` in branch protection, and `audit-llm` is retired.

**D120 · MEDIUM · 74 build and CI**

Hold T1 at the 20-minute / 1043 s ceiling and demote e2e, the native ASan/UBSan/TSan matrices, frontend Lighthouse and the docs strict build to T2 (removing them from branch protection) — yes or no (no = raise the T1 ceiling and re-cost the table)?

- Context: Part II §74.4 sets T1 at "20 min end-to-end, all jobs" and §74.9's budget table shows T1 sum(budget_s) = 1043 s across 12 jobs, enforced by G-BUDGET-001. But §74.3's own expected transcript shows build-offline at 9m47s (587 s) and §74.4 puts build-offline (toolchain-a) in T1. Part I's declared budgets for work Part II …
- Default if unanswered: Hold the 20-min T1 ceiling; T1 = format/lint/guard-AST/determinism-2x/build-offline/Tier-A unit+contract/demo-hash/spine-adversarial, everything else T2, and restate §43.6's budgets as per-CI-tier.

**D122 · MEDIUM · 74 build and CI**

Do the security scanners stay gates — registered at T2/nightly against advisory databases vendored and hash-pinned in toolchains.lock and refreshed only by `make toolchain-refresh` — or are they removed from branch protection entirely?

- Context: Part I §46.1 makes security.yml a required check (CodeQL, Semgrep, Bandit, gosec, cargo-audit, clippy, pnpm audit, Trivy on built images, gitleaks, dependency review) and §46.4 requires security/* on main; §33.3's security-test target is part of ci-local, and §46.8 pointedly exempts security.yml from the …
- Default if unanswered: Keep them as registered T2 gates over vendored, hash-pinned advisory databases, with an explicit note that a T2 security result is only as fresh as the last toolchain-refresh.

**D123 · MEDIUM · 74 build and CI**

Do we split the §45 adversarial suite into a T1 pure-function gate (runnable in toolchain-a with no services) plus a T2 stack-dependent gate, drop the `sudo iptables` egress blocking in favour of §74.3.4's egress sentinel, and register findings_guard as a T0/T1 lint — yes or no?

- Context: Part I §45 defines a 28-file adversarial suite run as a required CI job (§46.2's adversarial job: make compose-test-up, sudo tools/ci/block_egress.sh, pytest -m adversarial, findings_guard.py) and a branch-protection required check ci/adversarial (§46.4). Part II's §74.4 tier table contains only "Adversarial …
- Default if unanswered: Split it exactly that way; findings_guard is a T1 lint; mark test_provenance_forgery and test_replay_trace_tampering soundness = true (non-quarantinable).

**D124 · MEDIUM · 74 build and CI**

Is `ci-local` redefined as `make ci-local TIER=T0|T1`, generated from ci/gates.toml with the committed ci/epoch.txt pinned (never advanced locally), and its done-condition restated as 'same exit code as the T1 tier on the same commit and epoch' — yes or no?

- Context: Part I §33.3 defines ci-local as "exactly what CI runs: setup lint fmt-check typecheck test-all security-test bench-degrade docs", done when it produces "same exit code as GitHub Actions on the same commit". Under Part II, CI is four tiers with different triggers (T0 pre-commit, T1 per push, T2 nightly main-only, T3 …
- Default if unanswered: Yes: generate ci-local from the gate registry in registry order, pin the committed epoch, and delete the 'same exit code as GitHub Actions' claim.

**D125 · MEDIUM · 74 build and CI**

Is line coverage report-only (strip every `--cov-fail-under` and per-row coverage gate from §43.2, per §33.9), with mutation kept as two registered gates — G-MUT-KERNEL at T3, soundness = true, ≤10% survivors, plus the existing T2 polyglot audit — yes or no?

- Context: Part I §43.2 attaches a line-coverage gate to ~30 language rows, several enforced in the command itself (`pytest -q --cov=spectra --cov-fail-under=90`, 97% on spectra/eclipse, 95% on eclipse-kernel and cmd/spectra-verify, 100% lines on the anchor contract), and §43.5.4 requires mutation testing with "surviving-mutant …
- Default if unanswered: Coverage report-only; register G-MUT-KERNEL (T3, soundness = true, absolute ≤10% survivor threshold) and the T2 polyglot mutation audit; delete the 3-point regression rule.

**D129 · MEDIUM · 75 descope**

Is `mpc.toml`'s dependency graph the scheduling authority, with §52.2's M0→M10 table republished as a derived view over it (so M7 may close with stages F/G/H absent and M8's UI may precede M7) — yes or no?

- Context: 15-delivery.md §52.1.1 orders milestones strictly M0→M10 with no milestone started before the previous is green; §52.1.5 forbids scattering languages before M9; §52.2 places the degradation matrix and stages F/G/H at M7, the full UI at M8. Part II 75.2 states "**Nothing outside the MPC may be started while any MPC row …
- Default if unanswered: Yes: mpc.toml is authoritative, §52.1.1's strict sequence is overridden, `make mpc-status` governs what may be started, and §52.2's table becomes a non-normative view.

**D004 · LOW · 57 vocabulary**

Does `docs/section-index.toml` encode 07-replay's numbering (state model = §17, kernel = §25) rather than 04-state's (13-16, §18), and does `Tick` belong to §14.4?

- Context: §57.1 rule 3 requires every owner to resolve through `docs/section-index.toml`, with V3 failing on an unresolved owner, and §57.10's sample output claims "14 Part I, 9 Part II, 0 unresolved". But Part I is internally inconsistent about its own numbers: 04-state numbers the state model 13-16 while 07-replay calls the …
- Default if unanswered: Encode the 07-replay numbering, move `Tick`'s owner to §14.4, repair Part I's stale cross-references, and regenerate Table A's owner column from the index.

**D131 · LOW · 75 descope**

Do we add a MILESTONE-OPEN entry schema to BUILD_LOG.md (milestone id, budget_declared, opened_at_commit) and scope §0.3's 'exact entry format' to increment entries only — yes or no?

- Context: 75.6's descope protocol fires when "elapsed > budget declared in `BUILD_LOG.md` for this milestone", and the DESCOPE entry schema has `milestone`, `budget_declared` and `elapsed` fields. But 01-preamble.md §0.3 specifies the "Exact entry format" for BUILD_LOG.md as a per-**increment** entry (INC-NNNN, goal, files …
- Default if unanswered: Yes: add MILESTONE-OPEN alongside the DESCOPE schema in 75.6 and state that §0.3 governs increment entries only; otherwise the descope trigger is inert.

**D132 · LOW · 75 descope**

Is §0.2's ~400-changed-line cap removed for increments (keeping one concern and one gate run per increment, sized at the 75.4 '1–2 days, dozens of files' unit) — yes or no?

- Context: 01-preamble.md §0.2: "Work in increments of at most **~400 changed lines and one concern**", each running the full PLAN/RED/GREEN/REFACTOR/GATE/COMMIT/LOG loop, with "Never run PLAN for increment N+1 while increment N is red"; §0.4 "one concern per commit" and "No commit may mix a feature and a refactor". Part II …
- Default if unanswered: Yes: extend the 75.4 override to §0.2 — no line cap, one concern and one gate run per increment, and §0.4's no-feature-plus-refactor rule still applies per commit.

### Blocks M1

**D023 · HIGH · 59 ingest**

When an input record carries `ground_truth` or a truth-namespace key, does ingest (a) abort the run with exit 4, (b) quarantine the record as Q012, or (c) strip it to a sidecar?

- Context: Part I 10.4: `ground_truth is written only by the scenario generator and only into fixture bundles. The ingest path must strip it into a separate sidecar file before any reconstruction code can read the bundle`, gated by a test asserting `ground_truth` is unreachable. Part I 29.1: `The normalizer rejects any bundle …
- Default if unanswered: (a) Abort with exit 4 at manifest/pre-parse validation; the M1 generator writes ground truth to a separate truth file and never into the bundle, so the quarantine budget is never consumed and Part II's never-repair rule is not violated.

**D025 · HIGH · 59 ingest**

Is the per-scenario `sources.toml` the single authoritative source manifest - carrying `source_class`, `format_id`, `declared_tz` and `epoch_year` for each of the 16 SourceIds - superseding `range/sources.toml` and `source_registry.toml`?

- Context: Part I 26.3 states `The SourceIds emitted column is authoritative: it is generated from range/sources.toml and rules.toml must reference no SourceId absent from it. A CI gate diffs the two and fails on any orphan.` Part I 9.3 and 12.3 R12 additionally reference a `source registry` / `source_registry.toml` carrying …
- Default if unanswered: Yes: the per-scenario manifest is authoritative, the 'SourceIds emitted' column and the orphan-SourceId CI gate are generated from it, and class/format/tz/epoch_year columns are added to the 26.3 service table so range and manifest cannot drift.

**D027 · HIGH · 59 ingest**

Does the 55-75 minute band count only maintenance-window blind minutes (taint- and AssumedTz-induced blindness reported as separate quantities), and must every range source emit an explicit numeric UTC offset so AssumedTz never appears in the base dataset?

- Context: Part I 27.4 sets `natural BLIND minutes (all sources summed) | 55-75 | band` and states `Bands are not aspirations: a run outside a band fails the build`; Part I 27.2 produces that budget from exactly two declared maintenance windows. Part II adds two new mechanisms that force non-LIVE windows: 59.8 makes `AssumedTz` …
- Default if unanswered: Yes to both: band = maintenance-window blind minutes only; every range source emits an explicit offset (or a declared SourceOffset/MappedTz basis); AssumedTz appears only in the hostile-format conformance corpus.

**D039 · HIGH · 61 degradation**

Is `truth/objective.toml` the authoritative goal atom (scenario YAML's `goal_atom` reduced to a lint-checked cross-reference, `expected_verdict_full_telemetry` and `expected_min_cut_size` kept only as clean-cell expectations), and is S80..S85 the held-out set 61.10 protects?

- Context: §28.1 puts `goal_atom: "data.exfiltrated(finance.records, actor_b)"` inside the scenario YAML, alongside `expected_verdict_full_telemetry: ROBUST` and `expected_min_cut_size`, and §28.3 makes the scenario file the single executable input shared by the simulator and the ground-truth emitter ('the simulator cannot …
- Default if unanswered: Yes: objective.toml is authoritative because it alone has a freeze check and is expressed over StepIds; the YAML fields become derived cross-references with a lint asserting agreement, and S80..S85 is the protected held-out set.

**D042 · HIGH · 62 oracles**

Does the build have two distinct ranges - a normative deterministic dataset-generation range under the bit-identical dataset-reproduce gate, plus a separate non-normative Oracle R re-execution range - yes or no?

- Context: Part I §26 opens: "The range is the only place SPECTRA telemetry comes from." §26.7: "Do NOT generate telemetry inside SPECTRA's own code path. Every event must originate in a range service and traverse collector -> normalizer. Synthesizing an event directly into `bundle.jsonl` is forbidden outside …
- Default if unanswered: Two ranges; generator output is normative and is NOT stamped synthetic_bypass, so the kernel accepts it as evidence; only the re-execution range is stamped normative:false and exempt from byte-identity.

**D044 · HIGH · 62 oracles**

May a HELD_OUT scenario file carry expected_verdict_full_telemetry, expected_min_cut_size and expected_block_points, or are those fields (and the 28.3.3 reproduction gate) restricted to DEV and RED scenarios?

- Context: Part I authors the answer into the scenario file and gates on it. §28.1's scenario carries `expected_block_points` (control, level, `blocks_at_step`, mechanism), `expected_verdict_full_telemetry: ROBUST` and `expected_min_cut_size: 1`; §28.3.3 makes the build fail unless every `expected_block_points` row "is …
- Default if unanswered: Restricted to DEV/RED; HELD_OUT scenarios carry only declared_sufficient_cuts / declared_insufficient_cuts, and HELD_OUT is defined as 'rules frozen before the scenario', not 'outcome unknown'.

**D045 · HIGH · 62 oracles**

Is suppression_class an authored per-scenario field in groundtruth.json fixed before degradation, or a per-cell value computed by the degradation operator into a sidecar file?

- Context: Part II §62.8.3 scopes the headline gate over "`HELD_OUT scenarios x completeness 100%..30% x suppression classes S0-S3`" and §62.11.1 reports "suppression class S4 frequency 0.11 S5 frequency 0.03" as measured per-cell rates. Part I's degradation matrix has one axis: §29.5 `make dataset-matrix PARENT=base-14d-v1 # …
- Default if unanswered: Per-cell, computed by the degradation operator into a sidecar; groundtruth.json carries no suppression_class, and make dataset-matrix gains a second suppression-class axis (S0-S5) with source-class inputs declared in range/sources.toml.

**D047 · HIGH · 63 guard language**

Does one DNF term still equal one technique variant with a single-u64 blockers mask (Part I 22.3), or does a single instance carry the whole DNF as a multi-word mask set with a subset test (Part II 63.5)?

- Context: Part I 22.3 lowers `admit_when` to DNF and states: "Each DNF term becomes ONE rule instance / ONE technique variant whose `blockers` mask is the OR of the bits of the threshold atoms it negates. A step that only fails when two controls are both raised is therefore two variants, not one mask. `blockers & S == 0` is …
- Default if unanswered: Adopt 63.5's in-instance DNF as the single mechanism and abolish 22.3's variant splitting for control blocking; variants remain only for genuinely different attacker techniques, and dnf_mask_equivalence is rewritten against the new lowering.

**D051 · HIGH · 63 guard language**

Is tick_granularity_ns a single repo-wide constant (1 ms, so 30m compiles to 1800000) hashed into the .sglb header, with scenario tick_unit_s demoted to a display factor?

- Context: Part II 63.5 converts duration literals to ticks at compile time "using `tick_granularity_ns` from the time lattice", emits that value into the `.sglb` header (63.7) so it is part of `guard_ast_hash`, and makes a non-integral literal a hard error (E-SEM-030, "SGL never rounds"). 63.13's worked example compiles `30m` …
- Default if unanswered: Yes: global 1 ms granularity owned by the time-lattice section and hashed into guard_ast_hash; tick_unit_s becomes display-only with a loader check that it is an integral multiple of the global granularity.

**D073 · HIGH · 67 kernel threat model**

Is threat/model.toml amended with an in-scope `C12_local_rechain` capability (restating L1 as "cannot forge a sealer digest" and L5 as applying only to CHAINED_SEALED sources, re-deriving max_suppressed_sources), rather than running red-team fixtures under a second generator profile exempt from the panic assertion?

- Context: Part I §6.3 states as hard, enforced limitations that the attacker cannot "Break cryptographic primitives. BLAKE3 chain forgery is out of scope; a break of the chain is always detectable" (L1), cannot compromise the collector's signing state (L4), and cannot "Suppress telemetry ... retroactively for records already …
- Default if unanswered: Amend the single threat model: add C12_local_rechain bound to the CHAINED_LOCAL/UNCHAINED source classes, restate L1 and L5 as above, re-derive max_suppressed_sources, and update 6.5's scope table; no forked profile.

**D095 · HIGH · 70 pre-registration**

Do we port the Part I metric list (precision/recall/F1, latency, transition and path accuracy, evidence coverage, block outcomes, throughput, RSS, cut_solver_ms, checker_ms, cert_bytes, ...) into prereg.toml as tier='secondary' declarations before the sealing commit, deleting from the results schema anything not ported?

- Context: Part II §70.3: "Every quantity the project will ever publish is declared here ... The harness refuses to emit a results row whose `metric_id` is not declared, and the docs build refuses to render a number whose `metric_id` is not declared", and it declares only M1-M8. Part I §48.6's results schema and §49.3-49.6 …
- Default if unanswered: Yes: port the wanted Part I metrics as secondary declarations before sealing (renaming any ECLIPSE-facing terms), and delete undeclared columns from bench/runner/schema.py so the metric linter has nothing to block.

**D096 · HIGH · 70 pre-registration**

Do S90-S94 fold into DEV and get marked TUNED with a published THRESHOLD sensitivity sweep, and S80-S85 get sealed as a second held-out pool under a pre-registration amendment (yes), or are S80-S85 dropped (no)?

- Context: Part II §70.5 defines exactly three disjoint, append-only pools — DEV, HELD-OUT, RED-TEAM — declared in `research/pools.toml`, with `check-pools-disjoint` failing "when a scenario id appears in two pools, or a tuned flag was cleared", and `tuned` monotone. Part I §49.2 item 3 requires thresholds for `rules` and …
- Default if unanswered: Yes: S90-S94 join DEV as TUNED with a ledger THRESHOLD entry and published sweep; S80-S85 are sealed as a second held-out pool authored before the rule table freeze, or dropped if that ordering cannot be honoured.

**D097 · HIGH · 70 pre-registration**

Is `replicate` the seed (data-draw) axis only, with a separate `repeat` field added to the row schema for timing variance plus warmup and contended suppression flags declared in prereg.toml?

- Context: Part I §48.3 item 5: "`repeats` are re-executions of an identical cell for timing variance. `seeds` are distinct data draws for statistical variance. They are different axes and **must never be collapsed**. Accuracy statistics aggregate over `seeds`; latency statistics aggregate over `seeds x repeats`." Part II's cell …
- Default if unanswered: Yes: replicate is the seed axis and feeds seed(cell); add an explicit `repeat` field aggregated only for latency, and declare warmup/contended as suppression flags covered by the table linter's PARTIAL rule.

**D101 · HIGH · 71 claims**

Does BP-16 carve out the statistical senses (allow `confidence interval`/`confidence band`/`probability` as an operator or generator parameter via negative lookaround in banned.toml), or must every statistic and config key be reworded to `interval`/`drop rate`?

- Context: Part I §49.7(15) requires "Confidence intervals: BCa bootstrap, 10 000 resamples ... Report 95 percent CIs for every mean, every proportion, and every ratio"; §48.8(25) has the renderer refuse "a scalar that lacks `n` and a confidence interval"; §49.7(18) forbids "any mean without n and CI"; §50.2 defines …
- Default if unanswered: Carve out the statistical senses in banned.toml with explicit lookarounds (`confidence interval|band` and `probability` in operator/parameter contexts allowed; bare `confidence`, `risk score`, `severity`, `likelihood` still banned), and keep §71.7(5)'s ban on …

**D018 · MEDIUM · 58 determinism**

Are property-test frameworks (hypothesis, proptest, FsCheck, QuickCheck) carved out of the `seeds.toml` consumer registry, with only samplers whose draws reach a fixture or certificate registered — yes or no?

- Context: Part I §44.11 requires "Do NOT use randomness without a recorded seed. Every property test prints its seed; CI exports `HYPOTHESIS_SEED`, `PROPTEST_CASES` and `QUICKCHECK_SEED` into the job summary", and §43.4 builds fixtures with `spectra fixtures build --seed 0xSPECTRA`; §44.4 generates 10,000 cases per run with …
- Default if unanswered: Yes, carve them out explicitly by name in §58.8(4)/§58.12(7), register `generator.*`, `degrade.*` and `kernel.config_sampler`, and keep the §44.11 env-var seed echo with a gate that the job summary contains it.

**D074 · MEDIUM · 67 kernel threat model**

Is the adaptivity probe's alternate branch pre-declared in the scenario script and selected without reading the cut S (so "every replay uses the same attacker plan" still holds), rather than branch selection being a new cut-conditioned generator capability?

- Context: Part I §6.3 L2 states the attacker "CANNOT ... Observe SPECTRA, the control configuration under test, the rule table, or any certificate. The attacker is non-adaptive; it does not re-plan against defences. **Every replay uses the same attacker plan.**" §6.5 lists "Adaptive attackers that observe defences and re-plan …
- Default if unanswered: Pre-declared and cut-independent: the probe measures whether a fixed alternate plan survives the enforced cut, 67.10 says so explicitly, and 6.5's out-of-scope adaptivity row stands unchanged.

### Blocks M2

**D003 · HIGH · 57 vocabulary**

Is every entity-resolution and derivation witness (§12.4 union witness, §12.5 tie-break, §12.7 alias rows, `evidence_ids[]`, §14.7/§14.8) re-typed from `EventId` to `RecordId`, yes or no?

- Context: §57.11.4 forbids reading `event_id` "from any kernel, collector or checker code path", and `make lint-oracle-channel` "greps the kernel, collector and checker trees for `event_id` and fails on any hit outside the oracle crate". Part I keys reconstruction on EventId throughout: §12.4's resolver records …
- Default if unanswered: Re-type all witnesses to `RecordId`, keep `event_id` confined to the oracle crate, and re-bless the §12 golden fixtures.

**D006 · HIGH · 57 vocabulary**

Does `stream` get its own Table A row and ID type (and come off Table D's banned-synonym list), or is `stream_id` deleted in favour of `CollectorId`'s `@u16` suffix?

- Context: Part I's ordering, gap detection and tamper localization all rest on the stream: §11.2 "`(collector_id, stream_id)` defines an ordered sequence space" with a gapless `seq`; the evidence table's `UNIQUE (scenario_id, collector_id, stream_id, seq, content_hash)`; §11.5's localization tuple `(collector, stream, …
- Default if unanswered: Give `stream` a Table A row and its own ID, drop it from the `source` synonym ban, and keep `(collector_id, stream_id, seq)` in the evidence uniqueness constraint and BLAKE3 chain.

**D010 · HIGH · 58 determinism**

Does exact-duplicate suppression happen at ingest via `dedup_key`/`ingest_seen` before EventKey assignment (Part I), yes or no (no = duplicates survive into the ordered stream and Part I's dedup table, `dup_exact` and the §44.2 `set(records)` property are rewritten)?

- Context: Part I §14.6/§14.7 make exact-duplicate suppression mandatory and lossy: `dedup_key = blake3(source_id || seq_in_src || canonical_bytes(record))` is stored in `ingest_seen` with a unique index, a second insert is a no-op incrementing `ingest_dup_count`, and exact duplicates are "Dropped, counted in `dup_exact`"; §44.2 …
- Default if unanswered: Keep Part I's ingest dedup, and redefine `line_ordinal` as a determinism backstop over the pre-dedup bundle with `DUP_EVENT_SAME_KEY` firing only on surviving key collisions.

**D011 · HIGH · 58 determinism**

Is the serialized `EventId` a content address (insertion-stable, per §17.1.3), with §58.3's whole-bundle rank kept only as an internal never-serialized dense index — yes or no?

- Context: Part II §58.3(3) makes `EventId` the 0-based rank of an event in the whole-bundle order, so inserting or deleting any record renumbers every later event. Part I §44.8 requires `test_noise_invariance`: append N synthetic events from entities disjoint from the incident and "verdict, cut `S`, corridor set `Psi` and …
- Default if unanswered: Yes: content-addressed EventIds everywhere a certificate, witness tree or evidence array cites one; rank stays internal, preserving both the shuffle gate and §44.8 invariance.

**D013 · HIGH · 58 determinism**

Is `EventKey.t_nanos` the skew-normalized time `t_norm` (with an explicit skew stage carrying its own digest, `skew.json` in `outputs` and `sources.toml` in hashed `inputs.files`), or the raw asserted timestamp with skew normalization deleted?

- Context: Part I §14.5 mandates a deterministic skew-normalization pass — Bellman-Ford over a difference-constraint graph, per-source offsets `off(s)` from shortest-path potentials "rounded to whole ticks toward zero", `t_norm = t_raw + off(s)` — and §14.5(5) requires writing `skew.json` and "hash it into the certificate …
- Default if unanswered: Order on normalized time: insert a skew stage between S0 and S1 with its own digest, hash `skew.json` into the certificate, and add `sources.toml` to `inputs.files`.

**D019 · HIGH · 59 ingest**

Does a manifest-declared `degradation_provenance` exempt derived datasets from `max_quarantine_ratio` (while still forcing the `ingest_quarantine` flag) and is invariant I-1 restated over flagged certificates rather than unqualified ROBUST ones — yes or no?

- Context: Part II 59.7 sets `max_quarantine_ratio = 0.01` and 59.11.6 states `If quarantined / total_frames exceeds max_quarantine_ratio, ingestion fails non-zero and produces no bundle. A run that cannot parse its own telemetry is not a degraded run, it is a broken one.` Part I 29.4/29.5 requires `make dataset-matrix` across …
- Default if unanswered: Yes to both: keep the ratio gate and flag for real telemetry, let declared degradation provenance raise the ceiling, and restate I-1 as "no wrong cut" over flagged certificates across the 100%->30% matrix.

**D021 · HIGH · 59 ingest**

Is the socket-listening collector OUTSIDE the networkless ingest path, with `gate-ingest-egress` and `network_mode: none` scoped only to the `spectra ingest` worker container - yes or no?

- Context: Part I 26.2/26.3 put `telemetry-collector` (Go) on TCP 9700 plus a unix socket and `normalizer` (Rust) on 9701, both attached to the internal `range_telemetry` network, with a semantic healthcheck requiring `collector stream attached`. Part II 59.12 states `No component in the ingest path may open a socket. Enforced …
- Default if unanswered: Yes: collector (network-facing) writes content-addressed raw blobs, `spectra ingest` is a networkless file-in/file-out worker over that blob store, and the HTTP API is a third process that only resolves SourceRefs.

**D022 · HIGH · 59 ingest**

Is `ingest-signals.json` (plus `bundle.manifest.json`, `quarantine.jsonl`, `quarantine-report.json`) the complete set of certificate-hashed ingest artifacts, with `integrity_report.json` and `ingest_report.json` retired by name?

- Context: Part I 11.4 states `Outputs: integrity_report.json per run, containing per-stream record counts, gap count and total gap length, duplicate count, reorder count, fork flag, and the derived candidate intervals. This file is an input to the liveness pass and is hashed into the ECLIPSE certificate.` Part I 11.6 also …
- Default if unanswered: Yes: fold Part I's per-stream integrity counters into ingest-signals.json, retire both older filenames, and emit UNEXPLAINED_OBLIGATION downstream of the fact base rather than from ingest.

**D026 · HIGH · 59 ingest**

Is `observed_at_ns` removed from the canonical event, with liveness gap intervals bounded by `[t_utc_ns(prev accepted), t_utc_ns(next accepted)]` of the same source instead?

- Context: Part I 10.2/10.4 make `observed_at_ns` an always-required field, and Part I 11.4 derives the SUPPRESSED-basis candidate window as `interval [a.observed_at_ns, b.observed_at_ns]` — the collector-stamped observation time is the only thing that turns a `seq` gap into a time interval. Part II 59.5 forbids any adapter from …
- Default if unanswered: Yes: retire observed_at_ns (no clock-reading producer exists under Part II) and define gap windows in ingest-signals.json by bracketing accepted-record t_utc_ns, matching 59.9's FrameNeighbourBound basis.

**D028 · HIGH · 60 entity resolution**

Do we bump the canonical event schema to 2.0.0 and adopt Part II's `ent:<32 hex>` EntityIds and two-digit rule ordinals uniformly, or reshape Part II's ids to fit the existing 1.x patterns?

- Context: §10.2 constrains `EntityRef.entity_id` with `"pattern": "^[a-z]{3,7}-[a-z2-7]{16}$"` under `additionalProperties:false`, and `resolved_by_rule` with `^R[0-9]{1,2}$`. Part II's `ent:3a0c7f21b4e59d88…` (prefix `ent:`, 32 hex chars) fails the first, and its rule ordinals (00-44) fail the second. §12.6's `unres-…` ids …
- Default if unanswered: Bump to 2.0.0 with a migrations/events/1.x__2.0.0/ chain, adopt `ent:` and 00-44 ordinals uniformly (no dual id space), and state that 10.2, 10.5 and the language bindings are in scope of the sections 9-12 override.

**D029 · HIGH · 60 entity resolution**

Is `scenario_id` part of the EntityKey preimage so entities can never collide or merge across scenarios, or are EntityIds deliberately scenario-independent?

- Context: §9.3: '`scenario_id` is in the anchor, so entities from different scenarios can never collide or merge', and 'store `(scenario_id, entity_id)` as the composite primary key so a single database can hold many scenarios'. Part II 60.5 derives `EntityKey` from the component's sorted bindings only — no scenario_id, no run …
- Default if unanswered: Scenario-scoped: prefix the EntityKey preimage with scenario_id, preserving both content-addressing and the 9.3 no-collision guarantee and the Postgres (scenario_id, entity_id) composite PK.

**D030 · HIGH · 60 entity resolution**

Is one Tick exactly one nanosecond (identity map from `occurred_at_ns`), or a coarser quantum declared in `er.toml` and hashed into `er_config`?

- Context: Part I is nanoseconds everywhere: `occurred_at_ns`/`observed_at_ns` are integers 0..2^63-1 (§10.2 `Ns`), every entity and edge row carries `first_seen_ns`/`last_seen_ns`, process anchors use `start_time_ns`, and §10.10 forbids floating-point timestamps. Part II's `Binding.t_lo`/`t_hi` are `Tick` ('integer ticks (Part …
- Default if unanswered: Tick = nanosecond, identity map: no quantization, so `adjacent`'s exact t_hi == t_lo test keeps its Part I meaning and the ER confluence gate stays well-defined.

**D031 · HIGH · 60 entity resolution**

Do we add rule ordinal 16 `declared_cross_realm_link`, fed by a hashed `[cross_realm]` table in `er.toml` plus an `identity_link` telemetry path, so federated identities remain resolvable?

- Context: §12.2: 'Tier A merges across realms only when an explicit `identity_link` event or a declared mapping in the source registry authorizes it', implemented by R12 (`source_registry.toml`, e.g. `corp.ad:S-1-5-21-77-1104 == corp.idp:svc_backup`) and R13 (`identity_link` event from a control-plane source), applied in §12.4 …
- Default if unanswered: Yes: add the ordinal, treat the declared mapping as ANCHOR-class because it is hashed into er_config and therefore certificate-visible; otherwise 12.2, R12, R13 and the 12.8(2) under-merge claim are struck in writing.

**D032 · HIGH · 60 entity resolution**

Do `er.jsonl` bindings (extended with `rule_ord` and witness EventIds) replace the 12.7 alias table, with the grounding stage owning the 9.8 edge rows and Postgres holding only an index?

- Context: Part I makes ER produce an alias table (§12.7: 'Aliases are rows, not rewrites: (scenario_id, entity_id, realm, class, value, first_seen_ns, last_seen_ns, rule_id, witness_event_id)') and an edge table (§9.8: thirteen edge types, each a first-class row with validity interval, `evidence_ids[]` and `license_id`), and …
- Default if unanswered: Yes: bindings subsume aliases with the audit fields restored, grounding emits edges (validity interval, evidence_ids, license_id) reading er.jsonl, and Postgres is a rebuildable index over on-disk content-addressed blobs.

**D037 · HIGH · 61 degradation**

Does a byte-identical duplicate line keep a single content-addressed EventId, with `anchor_map` allowing many origin coordinates per event and `orphan_lines` redefined as lines reaching neither an event nor quarantine?

- Context: §29.5 item 2: 'EventIds are assigned by the normalizer as `ev_ = blake3(canonical_event_bytes)[0:16]`, not by a counter, so ordering changes cannot shift ids', and §50.2 expects duplicates to be absorbed: 'SPECTRA flat if dedup by content hash works; any SPECTRA rise is a bug, file it'. §61.4.3 permits `byte_identical …
- Default if unanswered: Yes: origin never enters the event preimage, anchor_map is many-to-one, orphan_lines is redefined, EventId spelling is normalized to ^ev_[0-9a-f]{16}$, and phantom_derivations is restated against the many-to-one mapping.

**D086 · HIGH · 69 boundaries**

Is raw telemetry (`event`, `chain_gap`, `state_transition`, `dataset`, `bundle`, `source`) permitted in PostgreSQL as an explicit fifth family, exempt by name from the `proj_` prefix rule and from the byte-identical `make rebuild-projections` dump?

- Context: Part I 38.2 makes `event` the backbone of the system: a monthly RANGE-partitioned table with six indexes, feeding `GET /api/v1/events`, `POST /events/search`, `/state/{id}/at`, `/transitions`, `/graph`, `/integrity/*`, and analytical queries Q2, Q3 and Q4 in 38.8; 33.3's `ingest` target is defined as "parse, …
- Default if unanswered: Yes: declare telemetry a fifth ingest-derived, CAS-rebuildable family, exempt it from the proj_ prefix and from the byte-identical rebuild comparison, and keep the partitioned `event` table as Part I specifies.

**D106 · HIGH · 71 claims**

Does the no-float rational rule apply only at the `limits.json` boundary (results.parquet and summary.json keep IEEE doubles, with a declared fixed-precision decimal normalisation for QUANT matching), yes or no?

- Context: Part II §71.6.2 specifies `artifacts/limits/limits.json` with "integers and rationals as `{"num":int,"den":int}` — no floats anywhere, per the determinism charter", and it is produced by the same validation matrix that feeds LIMITATIONS.md. Part I §48.6 and §49 define every accuracy metric as a float …
- Default if unanswered: Yes: floats stay in results.parquet/summary.json, limits.json converts to `{num,den}` at its boundary, §71.3(6) normalisation is 'rational rendered to a declared fixed precision, compared exactly', and BCa/Wilson endpoints are stored as fixed-precision …

**D134 · HIGH · 76 hypothesis**

Is the banned-field-name regex scoped to the Hypothesis, DegradedState and API-response surfaces with an explicit allowlist for the rule DSL (keeping `severity_class` and `ratio`), rather than applied repo-wide to every schema, column and property?

- Context: 76.2 negative requirement 2 bans "No field whose name matches `(?i)(score|confidence|probab|likeli|belief|certain|plausib|weight|severity|risk|p_?value|percent|pct|ratio)`" and states the regex "applies to Rust, Go, Python, TypeScript, SQL columns, OpenAPI properties and JSON Schema properties"; the 76.18 gate row …
- Default if unanswered: Scope the lint to hypothesis/degraded-state/API-response surfaces and allowlist the §18 rule DSL; do not rename `severity_class` or `ratio` (a MAJOR bump on all 63 rules would change rules_hash and force RULES_HASH_MISMATCH on every prior certificate).

**D135 · HIGH · 76 hypothesis**

Is the no-float ban bounded to the reconstruction core, kernel, hypothesis types, certificate and every endpoint under /v1/runs/** — leaving the section 21 ML baseline router's floats behind its `is_baseline_only`/`not_evidence` envelope and exempting config thresholds like `max_ghost_fraction` — yes or no?

- Context: 76.3: "`\"number\"` is forbidden anywhere in every SPECTRA schema; a schema lint (`make lint-schema-nofloat`) greps the compiled schema bundle for `\"type\": \"number\"` and fails." 76.11.5: "No endpoint returns a float. A contract test asserts every response body parses under a schema with `\"number\"` globally …
- Default if unanswered: Yes: bound it exactly that way in 76.3 and 76.11.5, keep the ML comparison arm alive, and exempt config-file thresholds; otherwise G21.0 and the no-float gate cannot both pass.

**D137 · HIGH · 76 hypothesis**

Is the §19 dependency-edge layer retained as the internal substrate the Hypothesis renders from — six typed relations as a per-Stage relation field, `transition`/`dependency_edge` tables with `edge_has_support`, and the ghost-sole-PROPAGATES ban plus evidence-dereferenceability registered as named gates in 76.18 — yes or no?

- Context: 76.2's Stage has `rule_inst`, `head`, `parents` and evidence, and no relation type. Part I 19.2 mandates exactly six typed relations (ENABLES, CREATES, AUTHORIZES, PROPAGATES, CONSUMES, OBSERVES) with per-relation derivation conditions, 19.2.1's artifact-identity rule for PROPAGATES, 19.3's `transition` and …
- Default if unanswered: Retain it: add a relation field to 76.2's Stage, qualify 76.0's 'only structure' claim, keep the tables and the `edge_without_evidence` CI view, and register the two safety checks as gates.

**D009 · MEDIUM · 57 vocabulary**

Is bare `adapter` permitted as its own concept — the pure `bytes -> Vec<CanonicalEvent>` function with its own Table A row, distinct from `collector` (the emitting process instance) — yes or no?

- Context: §57's preamble says `adapter`, `parser`, `collector` and `shipper` "were used interchangeably" and that "Every such collision is resolved below", and Table D bans `source_adapter`, `log_parser`, `ingestor`, `shipper`, `agent` and `tailer` as collector synonyms. But Part I treats them as different things: §10.6 makes …
- Default if unanswered: Yes: keep adapter and collector as two concepts, give `adapter` a Table A row, and retain `adapter_version` / `adapter_lossy` as adapter-owned fields.

**D020 · MEDIUM · 59 ingest**

Does ingest emit a per-source `arrival_inversion_count` into `ingest-signals.json` (bundle.jsonl still byte-identical under shuffled inputs), or is the `reorder` degradation operator retired from the matrix entirely?

- Context: Part I 29.4 lists `reorder` among the degradation operators and Part I 11.4 classifies `b.seq < a.seq on arrival order` as `REORDERED`, with the effect `reorder by seq; record transport reorder count`, surfaced through the per-event `integrity` field (10.2 enum includes `REORDERED`) and `integrity_report.json`. Part …
- Default if unanswered: Emit `arrival_inversion_count` per source into ingest-signals.json, derived from (file_id, byte_start) versus canonical order; keep bundle.jsonl byte-identical so gate-ingest-idempotent still holds.

**D033 · MEDIUM · 60 entity resolution**

Do derived/GHOST entities get a synthetic binding of a new merge-excluded IdKind (obligation instance id + license id), or a separate kernel-owned `ghost:` id namespace outside ER's content-addressed space?

- Context: §9.4 requires a `derived` boolean, 'true when the entity exists only because of an obligation axiom and was never directly observed', rendered GHOST, excluded from observed-count metrics, and carrying the license that admitted it; §9.9 and §11.6 make obligation-forced entities a first-class outcome. Part II derives …
- Default if unanswered: Synthetic binding of a merge-excluded IdKind, plus `derived` and `license_id` fields on the er.jsonl record, so ids stay distinct and content-addressed and 9.4's GHOST rendering and metric exclusion stay enforceable.

**D139 · MEDIUM · 76 hypothesis**

Do we narrow 76.1's prose to the compounds its lint actually enforces — `attack_chain`, `attack_path`, `attack_story`, `attack_narrative` and any identifier naming a hypothesis as a chain or story — leaving graph-level `path`/`timeline` identifiers (`reconstruct_path`, `state_timeline`, /graph/paths, `max_path_hops`, `exe_path_hash`) untouched?

- Context: 76.1: "`chain`, `path`, `story`, `narrative`, `timeline` are banned as identifier stems in Rust, Go, Python and TypeScript; the lint fails the build on `grep -rniE '\\b(attack_?chain|attack_?path|attack_?story)\\b'` outside `docs/`." The prose bans five stems; the committed grep catches only three compound forms. Part …
- Default if unanswered: Yes: narrow the prose to the attack_* compounds; do not rename §20.9's closed eight-function query surface, the §20.14 routes, the §20.11 budget keys or the §20.2 node attributes.

### Blocks M3

**D012 · HIGH · 58 determinism**

Is `trace_hash` retained as a stage digest inside the S0..S6 chain computed over the manifest's `inputs` block only (with `run_id` staying the pre-run input fingerprint), or is `trace_hash` deleted in favour of `run_id` plus `cert_blake3`?

- Context: Part I §44.1 defines `trace_hash = BLAKE3(canonical_json(manifest) || canonical_json(control_config) || 0x1e || concat over steps in emission order of step_index || step_kind || canonical_json(step_payload_without_wallclock))` as "the identity of the run", requires the certificate to record it, and §44.1(7) asserts …
- Default if unanswered: Keep `run_id` as the input fingerprint, redefine `trace_hash` as the replay-simulator stage digest over the `inputs` block only, and never hash the `environment` block.

**D015 · HIGH · 58 determinism**

Is §58.9's nine-file `inputs.files` list closed and normative — extended with `sources.toml`, `dimensions.toml`, `constants.toml`, `artifacts.toml` and a rolled-up `rules/**` digest — yes or no?

- Context: Part II §58.9(1) defines `inputs` as "everything that may affect output. Hashed. `run_id` and every certificate hash derive from this block alone", and the schema lists exactly nine files: `bundle.jsonl`, `rules.toml`, `controls.toml`, `costs.toml`, `goal.toml`, `scenario.toml`, `seeds.toml`, `budgets.toml`, …
- Default if unanswered: Declare it closed, add those five entries, and add a gate that fails if any file read on a decision path is absent from `inputs.files`.

**D048 · HIGH · 63 guard language**

Are controls/catalog.yaml admit_when and bypass conditions SGL expressions typed against a declared per-enforcement-point fact-schema record, or a second guard language outside 63.0's exclusivity claim?

- Context: Part I 22.1 requires that "Any behavior that depends on a control MUST be expressed as a guard expression in the catalog or in `rules/rules.toml`", and 22.5/22.6 author gate conditions and bypass conditions inside `controls/catalog.yaml` (`admit_when: "not ctrl.session_binding >= network"`, `condition: …
- Default if unanswered: They are SGL; each enforcement point declares a fact-schema record supplying the slots for attacker.*/victim.*, and has(x) is expressed as equality against a declared Sym domain member.

**D052 · HIGH · 63 guard language**

Is controls.lock emitted as build/controls.lock by the existing catalog compiler, owning ASCII-sorted append-only bit assignment, and is its hash (not controls.toml's) the one carried in the certificate?

- Context: Part II makes `controls.lock` a hashed input to `sglc` (63.9 diagram, `sglc check --controls controls.lock`), requires bit positions "sorted by ASCII name, levels ascending, positions assigned by running offset", requires positions to be append-only across catalog versions, and fails with E-CFG-050 if the lock is …
- Default if unanswered: Yes: build/controls.lock is a fourth committed compiler artifact, the control-catalog section is the sole owner of bit assignment under the ASCII-sorted append-only rule, and hashes.controls_lock replaces controls.toml in the certificate alongside …

**D128 · HIGH · 75 descope**

Does C10's four-screen UI replace §52.11's M8 deliverable list, with the M3 vertical slice's terminal leg allowed to be a CLI transcript instead of 'visible in UI' and the hero asset allowed to be a regenerated CLI cast below rung D9 — yes or no?

- Context: 75.4's re-tiering table lists "CORE 52-56 delivery, milestones, ratchet — per-push, blocking" and "APPENDIX 39-42 UI beyond the four screens — never blocking". But the UI requirements live in both bands: 15-delivery.md §52.11 (M8) mandates the full UI — per-control levels, PROVE, certificate header, counterexample …
- Default if unanswered: Yes: add explicit OVERRIDES against §52.11, §53.3 and §52.1.4; M8 closes with the four screens, the M3 slice's terminal leg is the CLI transcript on C7's clone→generate→ingest→resolve→prove→verify path, and the hero may be an asciinema cast regenerated by …

**D049 · MEDIUM · 63 guard language**

Does the concrete simulator (a) write its own independently authored SGL front end, (b) read only the catalog and never rules.toml, or (c) keep Part I's shared lowering with sim-independence narrowed to exclude a front-end crate?

- Context: Part I 22.3 makes the simulator one of two lowerings of the single guard parser, 23.3 evaluates `guard_for(step.transition, v, config) // compiled from section 22` inside the stepper with results `Admit | Degrade{cap} | Refuse{atoms}`, and 25.4 states "One table, two consumers (kernel and simulator), no second source …
- Default if unanswered: (a): simulator gets its own SGL front end, is added as a row in 63.8's consumer table, publishes --print-guard-ast-hash into the 63.9 gate, and the sim-vs-kernel mask agreement test is restored at P0.

**D050 · MEDIUM · 63 guard language**

Are degrade and detect gate effects declared simulator-only, non-severing and excluded from guard_ast_hash, or does SGL gain a third sort / effect annotation for them?

- Context: Part I 22.5 requires every gate to declare `effect ∈ {refuse, degrade, detect}` and requires the compiler to enforce that degrade/detect gates contribute no blocker bits (recorded in `build/controls.meta.json` under `non_severing_gates`); 23.3's evaluator returns `Degrade{cap}`; 24.6 classifies a DEGRADED outcome from …
- Default if unanswered: Simulator-only and excluded from guard_ast_hash; SGL stays two-sorted, and 22.5's non-severing compiler check moves into the control-catalog section so the zero-blocker-bits rule is still enforced.

---

## 2. Blocks M4 and later

Answerable later. Listed so none is lost.

| ID | Blocks | Sev | Area | Decision | Default |
|---|---|---|---|---|---|
| D002 | M4 | HIGH | 57 vocabulary | Is a transition a fact, or does it produce exactly one fact whose payload is the transition's canonical bytes — so `tr:` h128 stays run-local and only `fh:` h256 appears in `invariant_U`, corridor … | A transition produces exactly one fact; write the `TransitionId -> FactHash` mapping into vocab.toml and cite only `fh:` in anything a certificate reaches. |
| D005 | M4 | HIGH | 57 vocabulary | Can an OBLIGATION license a silent instance over an interval where a producing source was LIVE — yes (keep `OBLIGATION` as a third `LicenseBasis` with its own admissibility rule) or no (delete it and … | No: delete `OBLIGATION` from `LicenseBasis`, keep obligation-forcing as a reason a Blind/Suppressed license is consulted, and preserve §16.2's fail-closed … |
| D024 | M4 | HIGH | 59 ingest | May a `derived`-class event ever ground a rule instance in an ECLIPSE derivation, or is it evidence-ineligible everywhere and not only for liveness? | Evidence-ineligible everywhere: a hard kernel check keyed on `source_class` (already in the EventId preimage) rejects any derivation leaf whose source class is … |
| D053 | M4 | HIGH | 63 guard language | Do guard identifiers bind through an explicit body binder (e.g. s = session.issued(S, T0)) resolving only against bound fact records, or by implicit lowercasing of body variables resolving against … | Explicit binder in body; guard paths resolve only against bound fact-schema records, never simulator state, and C6's rename-invariance claim is stated against … |
| D055 | M4 | HIGH | 64 well-definedness | Is MAX_GROUND_SECONDS deleted as a correctness-affecting cap, so grounding_capped fires only on MAX_INSTANCES/MAX_FACTS and elapsed time survives only as a non-hashed measured field? | Yes: delete the 120-second cap from the flag logic; deterministic instance/fact counts are the only grounding_capped triggers. |
| D061 | M4 | HIGH | 65 liveness | Are all License.interval and liveness.json bounds u64 nanoseconds (Part II) rather than ticks (Part I 25.5), with live(s, I) defined as LIVE only when every elementary sub-interval of I is LIVE? | Yes: u64 ns everywhere, ticks only at the grounding boundary, live(s,I) = conjunction over elementary sub-intervals (any BLIND or SUPPRESSED makes I non-LIVE), … |
| D062 | M4 | HIGH | 65 liveness | Must every data-derived rule threshold come from a hashed SourceProfile under the same anti-self-calibration gate as liveness, deleting 17.5.1's "quantiles from this run's own bundle" allowance? | Yes: extend the SourceProfile mechanism to rule thresholds, delete 17.5.1's own-bundle allowance, unify the quantile estimator on 65.3's exact-rank … |
| D065 | M4 | HIGH | 65 liveness | Does a LIVE verdict on a non-`chained` source (liveness_unauthenticated / S_SEQ_GAP_UNAUTHENTICATED) bar ROBUST the way Part I 25.9's flags do, or may ROBUST be claimed with only a scope caveat? | It bars ROBUST: any corridor whose absence depends on an unauthenticated LIVE verdict downgrades the run to OPTIMISTIC_ONLY with downgraded_by set, since a … |
| D066 | M4 | HIGH | 65 liveness | Does the Bellman-Ford difference-constraint/dispute pass live in a separate `spectra-temporal-consistency` crate that runs after grounding and feeds stage A via a typed hashed artifact, keeping … | Yes: spectra-liveness stays narrow (threshold + classification, no bundle handle), the DCG/dispute protocol moves to spectra-temporal-consistency running after … |
| D068 | M4 | HIGH | 66 verdict algebra | Is the 64-atom compile-time cap (E_ATOM_BUDGET, `type Cut = u64`, corridor.atom_mask BIGINT) kept, making `atoms_over_budget` unreachable from the pipeline and 66.9 case 3 an algebra-level unit … | Keep the cap: restate 66.9 case 3 as an algebra-level case over synthetic VerdictProposals and annotate 66.3 bit 2 as currently unreachable from production, … |
| D072 | M4 | HIGH | 67 kernel threat model | Do obligation-forced silent instances get a minted license with `basis = OBLIGATION` and the obliging EventId as witness, or is Def 17's second disjunct deleted so obligations only set … | Mint the license: basis = OBLIGATION with the obliging EventId as witness, so 67.3's anchor coverage stays total (no UNANCHORED) and the certificate can name … |
| D076 | M4 | HIGH | 67 kernel threat model | Is a deterministic step/arena budget the only thing that can produce Safety::Incomplete, with RSS and wall-clock aborts reclassified as infrastructure errors (E-RESOURCE-MEMORY, no certificate) … | Yes: deterministic step/arena budget is the sole source of Safety::Incomplete, RSS/wall-clock aborts emit E-RESOURCE-MEMORY with no certificate, and 45.2's 30s … |
| D083 | M4 | HIGH | 68 certificate | Pick one: (A) derive grounding caps downward from the 64 MiB certificate cap, (B) raise the certificate size cap to fit full instances+U at MAX_INSTANCES=2M/MAX_FACTS=500k, or (C) publish a Merkle … | (A): keep 64 MiB normative, state per-instance and per-fact canonical byte budgets in the cert spec, and make a run that would exceed it set `grounding_capped` … |
| D085 | M4 | HIGH | 68 certificate | Is `k` a horizon measured in ticks, declared u32 with a normative bound of 1..10000 matching horizon_ticks (yes), or rule-derivation rounds bounded 1..64 (no)? | Yes: k is in ticks, u32 in the certificate with a normative 1..10000 limit, the column widens to INTEGER CHECK (horizon_k BETWEEN 1 AND 10000), and a corpus … |
| D087 | M4 | HIGH | 69 boundaries | Are corridors, evidence expansion and causal paths served by streaming the run's CAS objects on demand with capped responses (yes, and query Q1 is withdrawn), rather than by new capped proj_*_slice … | Yes: the kernel emits the instances/evidence/corridor SFB objects, the API scans them from the CAS per request with a response cap, Q1 is explicitly dropped as … |
| D090 | M4 | HIGH | 69 boundaries | Do we add two hashed CAS inputs to the kernel ABI, `--thresholds` (liveness/skew/grounding) and `--policy` (verdict/flag mapping) plus a carried `profile` name, so every threshold that can change a … | Yes: add --thresholds and --policy as hashed argv objects recorded in the run manifest and certificate, keep behaviour-as-data intact, and forbid any kernel … |
| D104 | M4 | HIGH | 71 claims | Is §48.6's run/results schema extended with `rules_hash`, `controls_hash`, `axioms_hash`, `er_config_hash` and the `corridor_cap_hit` and `er_ambiguous` flags, and is `artifacts/runs/<run_id>.json` … | Yes to both: extend the §48.6 row schema with the four input hashes and two extra flags, and make `artifacts/runs/` canonical with `bench/results/<run_id>/` … |
| D107 | M4 | HIGH | 72 narration | Is §20.11's `max_query_ms` replaced by a deterministic visited-edge/expansion budget that fires the same `truncated`/`guards_fired`/`grounding_capped` machinery, with 72.2.4's ban narrowed to 'no … | Yes to both: deterministic work counter replaces max_query_ms, 72.2.4 is narrowed to decision/artifact paths, and §20.12/§21.3 remain CI performance assertions … |
| D113 | M4 | HIGH | 73 polyglot | Does `artifacts/state_table.json` still exist as the single generated source the Rust kernel and Python engine both load — owned by a Tier A `state-table-fsharp` component distinct from the Tier D … | Keep the generated state table: split F# into two polyglot.toml components, `state-table-fsharp` (Tier A, owns state_table.json and the antitonicity oracle) … |
| D014 | M4 | MEDIUM | 58 determinism | Is `limits.toml` folded into `budgets.toml` as `[grounding] entities_max` / `facts_max` and deleted, yes or no? | Fold it in and delete `limits.toml`, keeping `flags.grounding_capped` wired to any `[grounding]` budget exhaustion so no unhashed file can change output. |
| D063 | M4 | MEDIUM | 65 liveness | May rule fixtures inject liveness verdicts through a cfg(test)-only Verdict constructor that lint-edr whitelists by path, instead of every fixture shipping a synthetic SourceProfile plus enough … | Yes: a test-only Verdict source behind a cfg(test) type, whitelisted by path in lint-edr, plus a gate asserting the production binary contains no reference to … |
| D111 | M4 | MEDIUM | 72 narration | Is G20.7 restated as a presentation rule — 'no counter, timeline or metric presents a GHOST as observed, and any counter including ghosts must report the ghost count separately' — with narration … | Yes: restate G20.7 as a presentation rule, keep the sentinel test asserting observed counters are unchanged, report ghost counts in a separate field, and … |
| D001 | M5 | HIGH | 57 vocabulary | Do `illegal_dependency`, `contested` and `signed_collectors` become members of the closed `Flag` set in Table C and vocab.toml, yes or no (no = the ROBUST-downgrade, contested-disclosure and … | Add all three flags to Table C and vocab.toml before the certificate schema is frozen. |
| D046 | M5 | HIGH | 62 oracles | Is the closed soundness-affecting flag set (used by gate:nonvacuity-flags and ROBUST-eligibility) exactly {grounding_capped, er_ambiguous}, with greedy_cover and subset_minimal_only moved to their … | Yes: grounding_capped and er_ambiguous downgrade the verdict and count in flagged_share; greedy_cover and subset_minimal_only are reported-only; er_ambiguous … |
| D054 | M5 | HIGH | 64 well-definedness | Does psi_complete require a separate exhaustive minimal-corridor enumeration pass with its own deterministic node budget and its own flag, rather than mere termination of 25.6E's cut loop? | Yes: add an explicit completeness pass enumerating all minimal corridors under its own deterministic budget; psi_complete is set only by that pass, and … |
| D058 | M5 | HIGH | 64 well-definedness | Is functional_on folded into rules.toml (with catalog-bits.lock added to the hashed input table and the checker-independence allowlist), or does facts.toml become a sixth hashed, shareable kernel … | Fold functional_on into rules.toml, and extend 25.3's input table and the certificate hashes object with catalog_bits so realizability status is reproducible … |
| D059 | M5 | HIGH | 64 well-definedness | Adopt this flag-to-effect table: grounding_capped / horizon_truncated / er_ambiguous downgrade safety to OPTIMISTIC_ONLY; solver_budget_exhausted sets minimality:SUBSET only; corridor_cap_fired … | Yes: publish exactly that table in 64.8, retire subset_minimal_only in favour of the minimality field, and keep greedy_cover out of both safety and … |
| D071 | M5 | HIGH | 67 kernel threat model | Does `greedy_cover` become Minimality::Unverified with Safety::Robust permitted, or does it stay a soundness flag that bars ROBUST as in Part I 7.5 Def 19 and 44.9? | Make it a minimality statement: greedy_cover maps to Minimality::Unverified, Safety::Robust is permitted, the Go checker rejects any certificate claiming … |
| D079 | M5 | HIGH | 68 certificate | Is the content key redefined as blake3(canonical_bytes(scope) \|\| bundle_hash \|\| goal_hash \|\| seed \|\| k) — covering er_hash, liveness_hash, guard_ast_hash, instances_hash and the attacker model — with … | Yes: derive the content key from the same canonical scope block the verdict string renders from, replace the old unique index, and add a test asserting that … |
| D080 | M5 | HIGH | 68 certificate | Do the authoritative certificate bytes live verbatim in a BYTEA/TEXT column and get streamed unmodified by the API (yes), with JSONB kept only as a derived query-side copy? | Yes: store canonical bytes in BYTEA as the authority, derive a JSONB copy for querying only, serve the certificate endpoint as application/octet-stream, and … |
| D081 | M5 | HIGH | 68 certificate | Do we drop proof_cert's three hard-coded flag booleans for a full flag set plus a generated `flagged` column emitted from cert-schema.toml, with CHECK (verdict <> 'ROBUST' OR NOT flagged) and a … | Yes: generate both the DDL and the checker flag-algebra table from cert-schema.toml, drop flag_subset_only, add `minimality`, and gate ROBUST on the generated … |
| D088 | M5 | HIGH | 69 boundaries | Does the kernel emit hashed canonical-JSON, uncompressed projections of rules/controls/goal/bundle for the checker so its non-stdlib dependency set stays BLAKE3-only (yes), or do we widen the checker … | Yes: emit canonical-JSON projections plus an uncompressed checker-facing bundle into the CAS, keep `make no-service-deps` as-is, and hand-written TOML/zstd … |
| D103 | M5 | HIGH | 71 claims | Does the certificate's `mode` stay a bare enum token (ROBUST) with the scope binding carried in separate `rules_hash`/`controls_hash`/`licenses_hash`/`adaptivity` fields, or does `mode` itself become … | Bare enum in data plus separate hash fields; the composite scope-bound form is produced only by one rendering constructor, and §71.4.1(4)/E_MODE_UNSCOPED is … |
| D110 | M5 | HIGH | 72 narration | Does the certificate carry a `step_kind` field on each derivation step so narration can describe the attack chain from a closed per-step-kind relation table, or is chain prose dropped and §2.3.3's … | Yes, carry `step_kind` on certificate derivation steps and extend 72.6.1's table with one licensed entry per certificate-representable step kind (observed verb … |
| D136 | M5 | HIGH | 76 hypothesis | Do we extend the degradation bitflags with D11 EVIDENCE_TRUNCATED (SOUNDNESS), D12 UNDETERMINED_ABSENCE (COMPLETENESS), D13 GRAPH_QUERY_TRUNCATED (COMPLETENESS) and D14 RECONSTRUCTION_INSUFFICIENT … | Yes: add D11–D14 with those classes, make 76.9.1's 'every export returns a HypothesisSet' explicitly subject to D14 suppression (as D9 suppresses P_MAX), and … |
| D060 | M5 | MEDIUM | 64 well-definedness | Is the NEC/OCC premium (the ~\|A\|+1 extra minimum-cardinality solves) computed on every prove inside the 2s gate, or only on demand behind /eclipse/premium with its own separate budget, cache key and … | On demand only: prove stays under 2s for the canonical cut alone, NEC/OCC is a separately budgeted and separately cached stage, and its absence is reported as … |
| D067 | M5 | MEDIUM | 66 verdict algebra | Is `mode` deleted everywhere (prove request body, CLI flag, cert/ cache key and proof_content_key_idx) rather than surviving as a request-only knob? | Delete it everywhere; replace `mode` in proof_content_key_idx and the cert/ cache key with the flags mask plus the `er` scope hash, and rewrite the 37.3 … |
| D070 | M5 | MEDIUM | 66 verdict algebra | Does the API and certificate carry a server-rendered `verdict_string` (alongside verdict_prose) that the UI must display verbatim, with Verdict.renderShort() kept client-side only as a validator and … | Yes: server returns verdict_string and verdict_prose, renderShort() is a client-side equality validator only, and the 66.10 DOM gate binds to … |
| D091 | M5 | MEDIUM | 69 boundaries | Does the Python `spectra` CLI keep its verdict-bearing exit codes (0=ROBUST, 6=UNSAFE, 7=checker-rejected, 8=flagged) as a documented presentation-layer mapping computed from a checker-accepted … | Yes: keep the CLI table, narrow the CI grep to services/kernel_client.py and anything reading p.returncode, and document the CLI as the one component permitted … |
| D069 | M5 | LOW | 66 verdict algebra | Are `prove` exit codes keyed on the safety axis alone (0 = ROBUST and OPTIMISTIC_ONLY, 6 = UNSAFE, new 11 = INDETERMINATE) with exit 8 narrowed to mean "a soundness-class flag is set"? | Yes: 0 ROBUST/OPTIMISTIC_ONLY, 6 UNSAFE, 11 INDETERMINATE, and exit 8 repurposed to soundness-class flags only, making it mutually exclusive with ROBUST. |
| D040 | M6 | HIGH | 62 oracles | Is the Go checker hand-written from the spec text with its own lexer/parser/grounder (I-A, keeping gates/checker_independence.sh), or generated from the Rust guard AST (I-B)? | I-A handwritten; keep the no-generated-sources gate and amend Part I 22.3 to 'one parser per implementation, two implementations'. |
| D078 | M6 | HIGH | 68 certificate | Is the v1.0 Go checker replay-only over the certificate's published instance set (deleting `reground` from the grounding_mode enum and withdrawing Part I 25.8's re-grounding sentence), with a new … | Yes: `replayed` is the only legal value at MAJOR 1, 25.8's re-grounding sentence is withdrawn, an instance-set completeness obligation is added, and 68.12's … |
| D082 | M6 | HIGH | 68 certificate | Is POST /eclipse/verify an asynchronous job endpoint that must name its input artifacts by id (yes), rather than a synchronous sub-50 ms call taking {cert_id} alone (no)? | Yes: queue it (202 + job), require input artifact ids so the router materializes files and execs the checker with explicit argv, and publish measured hash … |
| D084 | M6 | HIGH | 68 certificate | Does Go get its own independently written guard parser and evaluator, keeping the Rust-vs-Go guard differential fuzz gate and the independent-CAE claim (yes), or is guard semantics single-sourced in … | No: single-source the guard front end, delete the Rust/Go guard differential and the independent-CAE claim, and state in docs/checker-scope.md that guard … |
| D089 | M6 | HIGH | 69 boundaries | Must the checker reground from rules+bundle by default and treat any mismatch against the published `instances` set as exit 20, with --strict-minimality default-on in CI and default-off in the API … | Yes: regrounding is mandatory and the published instances set is a cross-check (mismatch = exit 20); strict minimality defaults on in CI, off for API … |
| D126 | M6 | HIGH | 75 descope | Are the Haskell differential admissibility checker and the Z3 test-only oracle deleted per 75.3/D2 (striking §4.7's DoD line, §52.9's tri-implementation gate, §56.1 row 16 and the … | Delete both: state in 75.3 that OPTIONAL items are demoted even when their owning Part I section is tiered CORE, add OVERRIDES lines against §3.10 gates 4 and … |
| D008 | M6 | MEDIUM | 57 vocabulary | Does the §23 deterministic simulator get its own sixth `OracleId` (`sim_kernel_agreement`), or does `range_reexec` explicitly subsume both §24.8's sweep and §25.12.1's agreement gate? | Add `sim_kernel_agreement` as a sixth member of the Oracle set and update the "exactly 5" parenthetical. |
| D041 | M6 | MEDIUM | 62 oracles | Does the Haskell admissibility differential survive as a fifth oracle with its own letter in the oracles_applied enum, or is it deleted? | Retain it as Oracle H, add "H" to the oracles_applied enum, declared strength between C and S. |
| D114 | M6 | MEDIUM | 73 polyglot | Is the brute-force minimum-cardinality hitting-set cross-check over Ψ (\|A\| ≤ 20) kept as a second Tier B Julia component (`hitting-set-bruteforce-julia`, `constant_result` mutation), or is minimality … | Keep it: add `hitting-set-bruteforce-julia` as a second Tier B component with the mandatory `constant_result` mutation, so `\|S_opt\|`/`\|S_rob\|` still have an … |
| D127 | M6 | MEDIUM | 75 descope | Is the 256-config simulator-vs-kernel agreement test demoted to a non-blocking codegen regression check (because both backends are generated from the same guard AST), with oracle 3 of §62 named as … | Yes: demote it via a first-class OVERRIDES line against §3.10 gate 1, §4.4.2, §52.9 and §56.1 row 14; keep the gate name `gate-agreement` alive (satisfying … |
| D043 | M6 | LOW | 62 oracles | Does Oracle M's 15-mutant curated catalog replace the mutmut/cargo-mutants nightly gate, or run alongside it? | Both run: curated catalog at 100% kill per-PR proves gates are not inert; automated suite nightly at <=10% survivors with the 3-point regression rule measures … |
| D034 | M7 | HIGH | 61 degradation | Is the wall-clock ban scoped to decisions only - no clock read may change which cells run, which rows enter an aggregate, or any byte of cert.json/ledger.jsonl - with perf instrumentation allowlisted … | Yes, decisions-only: allowlist the perf/measurement path and exclude it from every hashed object, and replace per_cell_wall_s/total_wall_s and the … |
| D035 | M7 | HIGH | 61 degradation | Is `spectra matrix run` a mode of `bench/` that writes one row per cell into `bench/results/<run_id>/results.parquet` with `matrix_id` as a column, or a second first-class harness with its own store … | A mode of bench/: single store and single INDEX.json, check_generated.py extended to demand run_id + matrix_id + sampling disclosure, and 48.4's CPU-isolation … |
| D036 | M7 | HIGH | 61 degradation | Do the five baseline arms survive - adding `arm` and `repeat` to the 61.9.1 cell_id tuple, an explicit `none` reference plan, and detection metrics (TP/FP/F1) to the 61.11 metric table? | Keep the arms and extend the cell tuple and metric table accordingly; RQ1 and the spectra_nolic ablation are the only evidence that licensing is load-bearing. |
| D064 | M7 | HIGH | 65 liveness | Must the pre-registered false-LIVE (Type-L) ceiling in the ratchet file be zero at every completeness cell, so that 25.12.7's absolute zero-false-ROBUST gate stands unchanged? | Yes: 25.12.7 stays absolute, the 65.9.2 ceiling is kept as a leading indicator, and the shipped ceiling is zero for every cell where the goal is reachable in … |
| D094 | M7 | HIGH | 70 pre-registration | Is a hypothesis adjudicated solely by the pre-declared floor fixed in the FREEZE commit with median/IQR at 5 replicates (pick A), or by bootstrap-CI-excludes-null-after-Holm with 10 or more seeds per … | (A): pre-declared floors adjudicate, median/IQR/n is the reporting standard, the 'no mean without CI' gate is restated as 'no median without n and IQR', and … |
| D130 | M7 | HIGH | 75 descope | Is the normative degradation matrix C8's single completeness axis with per-operator seeds — 15 cells pre-descope, reducible to 3 by rung D11 — replacing §52.10's 8-step × 6-mode × ≥20-seed 350-cell … | Yes: OVERRIDES §52.10; matrix = C8's completeness axis with per-operator seeds, 15 cells declared as the pre-descope baseline; F/G/H optional; update `make … |
| D038 | M7 | MEDIUM | 61 degradation | Are `ABLATION` and `MUTATION` declared as distinct strata in `index.jsonl`, with `zero-false-robust` scoped to non-ablation RAN cells and the ablation strata required to report a nonzero false-ROBUST … | Yes: add the strata, scope the gate to the headline matrix, and give the ablation strata an inverted gate so a `- liveness` row showing zero false-ROBUST fails. |
| D057 | M7 | MEDIUM | 64 well-definedness | With costs.toml present, is frontier dominance a three-component product order over (declared_cost, goals_derivable, corridors_open), with the cost component omitted rather than defaulted when … | Yes: product order over (declared_cost when present else cut_cardinality, goals_derivable, corridors_open); points serialised in ascending cost then cut_cmp, … |
| D075 | M7 | MEDIUM | 67 kernel threat model | Are test_timestamp_backdating.py, failure-mode row 2, the `voided_licenses` span attribute and the `spectra_licenses_voided_total` counter rewritten around the BLIND-restriction behavior (asserting … | Rewrite, not delete: the test asserts licenses_voided == 0, TIME_INCONSISTENT set, the disputed span BLIND and \|licenses\| >= \|licenses(benign twin)\|; the … |
| D133 | M7 | MEDIUM | 75 descope | With no user-authored costs.toml, does the Pareto frontier still compute in cardinality mode labelled 'control count, not cost' in every axis label, API field name and export (yes), or is the … | Keep cardinality mode with mandatory labelling; rewrite 75.1 item 7's first clause to forbid only defaulting to unit cost, and keep §52.10's no-costs test case. |
| D138 | M7 | MEDIUM | 76 hypothesis | Is the decisive observation set computed whenever `rank_class_1_size > 1` OR any two members have disjoint observed-event sets OR the set came from an entity-resolution fork — dropping §19.7.2's … | Yes: state that three-way trigger in 76.9, retire AMBIGUOUS and its U(h)/S(h) conditions, and keep `decisive_observation_set` and D5 COVER_GREEDY with that … |
| D109 | M8 | MEDIUM | 72 narration | May narration state the certificate verdict — i.e. do we add a seventh `Verdict` ClaimKind rendered as a Structural claim pointing byte-identically at the certificate's `/mode`, yes or no? | Yes: add `Verdict` as a seventh ClaimKind, Structural evidence pointer at `/mode`, emitted immediately after the Scope claim, never paraphrased; 72.11.1(6) … |
| D056 | M9 | MEDIUM | 64 well-definedness | Is the ML baseline envelope exempt from make lint-no-scores via an exact-path allowlist of spectra/ml-prediction-v1.json plus the baseline router, or must score/calibration be renamed out of the … | Allowlist by exact file path with the justification 'comparison arm, is_baseline_only/not_evidence, never reachable from a certificate', and narrow 64.4.2's … |
| D112 | M9 | MEDIUM | 73 polyglot | Is JavaScript kept as a 33rd executing language (Tier B component owning `tools/js/canonicalize.mjs` only) with `web/standalone/verify.mjs` deleted, or is JavaScript removed entirely and the RFC 8785 … | Keep JavaScript as a Tier B component owning only `tools/js/canonicalize.mjs` (consumer: the canonicalization differential gate; mutation: `constant_result`), … |
| D116 | M9 | MEDIUM | 73 polyglot | Must a non-executing format that supplies facts the kernel grounds over (SAML XML, Terraform HCL) still carry a `polyglot.toml` component with a consumer edge and a mutation, even though §73.2 … | Yes: separate counting from auditing — keep them out of the §73.1 roster count but require manifest components with a named consumer and a mutation … |
| D117 | M9 | MEDIUM | 73 polyglot | Do we add a `status = "preregistered"` value to `polyglot.toml` that suppresses the four load-bearing checks and the demo-ring check until a named deadline milestone, with an expired status becoming … | Yes: `status = "preregistered"` with a mandatory `due_milestone`, suppressing §73.3's four checks and §30.4.4's demo-ring check until then, expiring into … |
| D115 | M9 | LOW | 73 polyglot | Does `BANNED_MATLAB_MENTION` scan paths and filenames as well as file contents, mandating the renames `polyglot/matlab/`→`polyglot/octave/`, `analysis/matlab/`→`analysis/octave/`, job … | Yes: scan paths and contents, perform all four renames, drop the linguist override and the pinned-version comment, and add the renames to §73.12's done … |
| D118 | M9 | LOW | 73 polyglot | Is `docs/polyglot/deleted.md` the only machine-read deletion record (date, mutation, commit) with the ADR reduced to optional prose no gate may cite, yes or no? | Yes: the ledger row is what `make polyglot-audit` reads and is schema-checked; the ADR becomes optional, is never cited by a gate, and §30.4.2's mandatory-ADR … |
| D077 | M10 | MEDIUM | 67 kernel threat model | Is H0 kept verbatim at its original scope with `amended_by = "H0b"` and a dated rationale while a new pre-registered H0b carries the suppression-class-scoped statement, rather than H0's falsifier … | Supersede rather than edit: H0 retained verbatim with amended_by and a dated rationale citing the A1 evasion class and artifacts/evasion.json, H0b added with … |
| D098 | M10 | MEDIUM | 70 pre-registration | Is the no-smoothing/no-curve-fitting ban scoped only to the completeness/degradation axis (yes), leaving the H4 fitted-exponent falsifier, the fitted line with R-squared on the checker-cost figure, … | Yes: scope the ban to interpolation or smoothing across completeness levels, and explicitly permit one declared regression for the checker cost model plus CI … |
| D099 | M10 | MEDIUM | 71 claims | Does the claims checker treat a `<!-- BEGIN GENERATED: ... run=<run_id> ... -->` region header as the CLM anchor for every unit inside that region (yes), instead of requiring a per-table-cell anchor … | Yes: add a generated-region rule mirroring the LIMITATIONS.md carve-out, with the support resolver validating the region's run id and input hashes exactly as … |
| D100 | M10 | MEDIUM | 71 claims | Does the generated results document live at `docs/RESULTS.md` (single path) and get added to the §71.2.1 closed claims-surface list, yes or no? | Put it at `docs/RESULTS.md`, add it explicitly to the §71.2.1 surface list, and let the generated-region rule carry it through the gate; delete the root-level … |
| D105 | M10 | LOW | 71 claims | Is the §53.2 status banner dropped as a separate element, with its content folded into the single authored `[disclaimer]` in docs/framing.toml plus a new ≤120-char `[about]` string for GitHub … | Yes: one authored `[disclaimer]` containing 'research prototype / synthetic data only / not a security product', the mandated root `LIMITATIONS.md` link with … |

---

## 3. How a decision gets closed

1. Answer it here, in place, with the date and the reason.
2. Edit the owning Part II section so the specification itself carries the answer, with an `OVERRIDES Part I:` line if it settles a Part I disagreement.
3. Record it in `BUILD_LOG.md`.
4. If it changes a schema, an identifier type or a hash preimage, it must be decided before the milestone that first writes that schema. Changing it afterwards is a migration, not an edit.

---

## 4. Raised by running the slice, not by the specification audit

These were found by executing the reference slice end to end. They are not among the 140
specification conflicts above; they are decisions the running system has shown to be necessary.

### D-RUN-01 · HIGH · the control arm — WITHDRAWN 2026-09-21: it was a bug, not a decision

**Withdrawn.** The premise below was wrong. The non-empty premium at full telemetry was caused by a
grounding defect, not by the horizon edges. Rule r0005 requires an escalation to precede an export
by at most 30 minutes; the envelope skipped that check for any licensed fact, so it paired an
escalation licensed in the first second with an export 76 minutes later, and one licensed in the
last second with an export that came before it. Both are impossible for every placement. With the
check made interval-aware (`ground.seq_feasible`), the full-telemetry premium is EMPTY and no
methodology choice was needed. See `BUILD_LOG.md` INC-0010.

The edge licences themselves are real and remain: liveness cannot be proved before the first
record or after the last. They simply cannot reach the export under the rule's time bound.

The original entry is kept below unedited, because it records what was believed and acted on.

---

**How is a finite observation window's blind edge handled, given absence lookbacks longer than the
window?**

- Context: at full telemetry every emitting source is LIVE across the horizon, yet the blindness
  premium is non-empty. All 80 licensed escalations sit in the first or last 10 s of the 2 h
  horizon. Liveness cannot be proved before the first record or after the last, and r0004's absence
  lookback is 72 h - 36 times the horizon - so an escalation in the leading edge can never be ruled
  out. `ctl:priv_approval` is therefore genuinely needed only on account of blindness. See
  `BUILD_LOG.md` INC-0008.
- Options: (a) a burn-in so the horizon begins at least one lookback before the attack window;
  (b) bound absence lookbacks to the observed horizon and record the truncation in the certificate;
  (c) treat edge windows as out of scope and state it in every certificate.
- Default if unanswered: **none is applied.** The demonstration reports the non-empty premium at
  full telemetry as the result it is. Choosing among (a)-(c) after seeing which yields a clean
  control arm would be fitting, so the choice must be made on its merits and recorded before the
  next run, not after it.

### D-RUN-02 · MEDIUM · witness encoding

**Should the certificate carry witness trees in a flat encoding (nodes plus parent indices) rather
than nested?**

- Context: nesting depth grows with proof length, and the contract caps it at 8 containers, which
  admits a root and one level of children. Route A is three levels, so no real multi-step attack
  can carry a published witness under the current contract. The pipeline now drops such a witness
  and reports it rather than aborting. See `BUILD_LOG.md` INC-0008.
- Default if unanswered: the nested encoding stays; multi-step witnesses are omitted and reported.
  Changing it is a contract change on the emitter and the checker together and needs an ADR.

