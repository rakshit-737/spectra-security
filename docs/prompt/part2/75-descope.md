============================================================
75. NON-GOALS, THE DESCOPE LADDER AND THE MINIMUM PUBLISHABLE CORE
============================================================

This section is the schedule kernel. Part I enumerated 57 sections each written as mandatory ("build fails otherwise"), with no ranked cut list; the feasibility critic judged the result unbuildable by one engineer in one semester and predicted a half-finished monorepo. This section makes the cut list normative, machine-checked, and prior to every other section's ambition.

OVERRIDES Part I: every Part I section is hereby re-tiered as CORE, STRETCH or APPENDIX by the table in 75.4. Where a Part I section says "build fails otherwise" and this section classifies it STRETCH or APPENDIX, that gate is demoted to a nightly non-blocking job and its absence is not a build failure. Where Part I and this section disagree about what is mandatory, this section wins.

------------------------------------------------------------
75.1 NON-GOALS
------------------------------------------------------------

Write `docs/NON-GOALS.md` containing exactly the following numbered list, verbatim in substance, before milestone M1 ends. Link it from the README's first screen next to `LIMITATIONS.md`. Every item states the thing SPECTRA does not do and why it does not do it.

1. **SPECTRA is not a detector.** It does not classify live traffic, score alerts, or decide that an attack is occurring. It reconstructs over a finished, bounded telemetry bundle. There is no streaming mode, no online inference, and no "real-time" claim anywhere in the repo.

2. **SPECTRA is not an IR product and produces no defensive prioritization advice.** The minimum cut is a statement about a recorded, non-adaptive hypothesis set under a declared catalog. A real adversary re-plans around the cut. Forbidden claim: "SPECTRA tells you which control to buy."

3. **SPECTRA does not prove anything about a real system.** It proves properties of the model: the rule table, the entity resolution, the control catalog, and the ingested telemetry. Forbidden claims: "formally verified", "guaranteed", "would have stopped the attacker", "prevents".

4. **SPECTRA does not execute, contain, or analyze malware.** No sample is downloaded, stored, detonated, or referenced by hash-for-retrieval. Scenario generators emit telemetry records only (see 75.8).

5. **SPECTRA does not attack any host it does not own.** No external target, no scanning, no network egress from any container in the scenario stack. There is no exploitation code path, and none is a stretch goal.

6. **SPECTRA emits no probability, confidence, score, severity, risk rating or likelihood.** Verdicts are structural: `safety ∈ {ROBUST, OPTIMISTIC_ONLY, UNSAFE}`, `minimality ∈ {EXACT, SUBSET, UNVERIFIED}`. A numeric confidence field anywhere in the API, database, certificate or frontend is a build failure, not a design choice. OVERRIDES Part I section 3.7: the certificate's single `mode` field (ROBUST | OPTIMISTIC) carrying minimality as the `subset_minimal_only` entry in `flags` (sections 3.9, 2.5.2 and 3.12.7) is replaced by two independent enum fields, `safety` and `minimality`, where `minimality` has a third state `UNVERIFIED` that Part I's schema cannot encode. An implementer following section 3.7 emits a `mode`-plus-flags certificate, and the Go checker, the adversarial certificate corpus, the API and the UI verdict header built against it cannot validate the structural verdict this section requires.

7. **SPECTRA invents no costs.** With no user-authored `costs.toml` the Pareto frontier is disabled, never defaulted to unit cost. Any cardinality-mode axis is labelled "control count, not cost" in every axis label, API field name and export.

8. **SPECTRA does not claim completeness over attacker behavior.** The silent envelope admits exactly the hypotheses the hand-written rule table can express inside provably blind windows. It is not "every evidence-consistent hypothesis". OVERRIDES Part I: the ECLIPSE one-liner's phrase "under every evidence-consistent hypothesis" is retired from every artifact and replaced by "under every hypothesis this rule table admits inside the licensed blind windows".

9. **SPECTRA is not a graph database, a SIEM, a log shipper, or a telemetry pipeline.** It does not compete with, replace or integrate into one. No connector, no agent, no forwarder.

10. **SPECTRA does not analyze software supply chains, build provenance, dependencies, SBOMs, signatures or artifact integrity.** That is WARDEN's domain and the boundary is non-negotiable: no SPECTRA subsystem may ingest a package manifest, a lockfile or a build attestation, and no WARDEN code may be vendored here. A CI grep over the source tree for supply-chain vocabulary outside `docs/NON-GOALS.md` fails the build. OVERRIDES Part I section 2.6: `make audit-scope`, scoped to the identifiers appearing as domain terms in `spectra/`, `rust/` and `go/` with build tooling and rule-referencing comments exempted through an allowlist file, is replaced by a grep over the whole source tree whose only exempt file is `docs/NON-GOALS.md`. An implementer who builds only the scoped, allowlisted `audit-scope` leaves the vocabulary unflagged everywhere else in the tree, and the artifacts Part I sections 53.2 and 55.7 mandate — the README's "What this is not" paragraph naming CVE, SBOM and dependency tooling, and `.github/dependabot.yml` with its `npm` and `pip` ecosystems — must be reconciled with this grep before either gate can be green.

11. **SPECTRA does not model an enterprise.** The scenario stack is a handful of containers. Banned phrases outside `docs/range/not-modeled.md`: "realistic", "enterprise-grade", "production-like", "real-world environment".

12. **SPECTRA is not a benchmark suite and publishes no leaderboard.** It reports its own measurements against its own baselines and ablations, with the run manifest hash attached, and compares itself to no third-party tool.

13. **SPECTRA does not use an LLM anywhere in the deterministic core.** Narration is an optional, removable surface over the certificate. `make verify-no-llm` proves every gate stays green with the model absent and the dependency uninstalled. A failure of that target is a failure of the project's core claim, not of an optional feature.

14. **SPECTRA does not require a network at any point after clone.** No CDN font, no remote schema, no package fetch at build or test time, no telemetry, no update check, no license server. OVERRIDES Part I sections 52.3, 52.13 and 54.1: the container-image carve-out — `make bootstrap` "installs nothing outside the repo and container images", `make release-check` green "with no network beyond image pulls", "nothing is pre-baked except container base images", and section 4.1's "no network after first pull" — is replaced by no network access of any kind after clone. An implementer following Part I builds a bootstrap that pulls images on first run, and this section's acceptance in 75.10, which is evaluated on a clean clone with the network off, can then never be demonstrated.

15. **SPECTRA's kernel and checker have no service dependencies.** `spectra prove` and `spectra verify` are pure file-in/file-out binaries. If either ever needs Postgres, Redis or a running API to produce or validate a certificate, the offline-verification claim has collapsed and the change is reverted. OVERRIDES Part I sections 3.1, 52.5 and 54.3: prove and verify operating over a run held in the PostgreSQL event store — the normative DDL for `entity`, `event` and `transition`, M2's "stable-ID events in Postgres", and `make demo` running `bootstrap up` before `spectra prove --run r1` — is replaced by a kernel and checker with no service dependency, addressed as file in, file out. An implementer following Part I routes prove through state that reconstruct persisted to Postgres, which is an architectural fork that cannot be deferred and that this item reverts on sight.

16. **SPECTRA does not support multi-tenancy, authentication, RBAC, audit-for-compliance, or any deployment posture beyond one user on one machine.** No hosted instance is offered. No SaaS. No demo server on the public internet.

17. **SPECTRA does not guarantee that a language present in the repository is production-grade in that language.** Tier C and Tier D artifacts are small, single-purpose, and exist because they do one job the audit can prove is load-bearing. The repository never advertises expertise it has not demonstrated.

18. **SPECTRA does not claim novelty it has not tested.** The README's claim table cites only green milestones and HELD-OUT results under a frozen rules hash. An unbacked quantitative claim in `README.md` or `docs/` fails the docs gate.

19. **SPECTRA is not the Eclipse Foundation, the Eclipse IDE, Eclipse Temurin, or Eclipse Adoptium.** The kernel name ECLIPSE is an internal acronym (Evidence-Licensed Cut Proofs over Silent Envelopes). State the collision in `README.md` and in `docs/naming.md`, do not use any Eclipse Foundation mark, and prefer "the SPECTRA kernel" in prose where confusion is possible.

20. **SPECTRA does not promise the polyglot surface will be complete.** The language surface is tiered and completed in tier order (75.5). An unfinished tier is stated as unfinished in the README's machine-generated language table, never scaffolded to look finished.

NEGATIVE REQUIREMENT: do not soften a non-goal into a "future work" bullet. A non-goal that acquires a roadmap entry stops being a non-goal and must be deleted from this list with the deletion recorded in `BUILD_LOG.md`.

------------------------------------------------------------
75.2 THE MINIMUM PUBLISHABLE CORE (MPC)
------------------------------------------------------------

The MPC is the smallest artifact set that makes SPECTRA a defensible public repository and a submittable workshop paper. Nothing outside the MPC may be started while any MPC row is red.

| # | Component | Owner section | "Done" means | Proven by |
|---|---|---|---|---|
| C1 | Seeded synthetic generator | 26-29 (re-scoped) | Pure function `(seed, scenario_id, degradation_spec) -> bundle.jsonl + ground_truth.json`; byte-identical across two runners | `make gen-determinism` |
| C2 | Ingest and canonical event schema | ingest addendum | Every raw record parsed or quarantined with a reason code; zero silent drops; hardening limits enforced | `make ingest-gate` |
| C3 | Entity resolution + quality contract | 9-12 + ER addendum | Deterministic; precision/recall published against C1 ground truth across the matrix; `er_ambiguous` flag wired into the certificate; flagged run cannot be ROBUST | `make er-eval` |
| C4 | Rule table + guard language + codegen | 22 + guard addendum | One canonical AST, one AST hash, both backends assert equal hash; non-threshold level predicates rejected by lint | `make guard-gate` |
| C5 | ECLIPSE kernel A–E | 25 | Liveness, semi-naive grounding with provenance, silent envelope, Dowling–Gallier fixpoint under cut, hitting-set loop with deterministic step budget | `make kernel-gate` |
| C6 | Independent Go checker | 25 + certificate addendum | Closure, goal-unreachability, license implication, witness re-derivation, no-smaller-cut-vs-Ψ; rejects every member of the adversarial certificate corpus | `make verify-gate`, `make cert-corpus` |
| C7 | One end-to-end scenario | 5-8 | One HELD-OUT scenario runs clone → generate → ingest → resolve → prove → verify with no manual step | `make e2e` |
| C8 | Degradation matrix | degradation addendum | Completeness axis defined; per-operator seeds; ground-truth re-linking under perturbation defined; zero false ROBUST on declared suppression classes; ROBUST yield floor enforced | `make matrix` |
| C9 | Held-out / overfit protocol | 62 | Rules frozen and hash-pinned before each scenario family; TUNED vs HELD-OUT split published; CI fails on commit-order inversion | `make leakage-gate` |
| C10 | UI: one investigation, one counterfactual | 39-42 (re-scoped) | Four screens: control toggles + PROVE, scoped verdict header, indented counterexample tree with GHOST distinction, degradation strip. Verdict never computed client-side | `make ui-gate`, 5 Playwright specs |

OVERRIDES Part I sections 3.10 and 4.4.1: the zero-false-ROBUST obligation stated as gate 5's "across the entire degradation matrix" and as `artifacts/matrix/false_robust.json` reporting zero "across every cell" is narrowed by C8 to the declared suppression classes, which is also the form placed on the NEVER CUT list in 75.5. An implementer following section 4.4.1 gates the invariant over every cell of the completeness-by-perturbation grid; an implementer following C8 scopes `make gate-invariant` to the suppression classes and reports zero false ROBUST without ever testing the delay, duplication, reordering or corruption cells.

MPC completion is machine-defined, not a judgement call. Check in `mpc.toml` and gate on it:

```toml
# mpc.toml — the Minimum Publishable Core. CI reads this; prose does not override it.
schema_version = 1

[[component]]
id        = "C5"
name      = "ECLIPSE kernel, stages A through E"
gate      = "make kernel-gate"
artifacts = ["crates/eclipse-kernel/", "out/cert/*.json"]
status    = "red"          # red | green | waived
blocks    = ["C6", "C7", "C8", "C10"]
descope_rung = "NEVER"     # see 75.5; NEVER = may not be cut

[[component]]
id        = "C10"
name      = "UI: one investigation, one counterfactual"
gate      = "make ui-gate"
artifacts = ["web/src/screens/Prove.tsx", "web/tests/e2e/"]
status    = "red"
blocks    = []
descope_rung = "D9"        # may be thinned to a CLI transcript, never deleted
```

```
$ make mpc-status
MPC 10 components: green 6, red 4, waived 0
  C1 generator .............. green   (make gen-determinism, 0 waivers)
  C2 ingest ................. green
  C3 entity resolution ...... green
  C4 guard/codegen .......... green
  C5 kernel A-E ............. red     blocks C6 C7 C8 C10
  C6 go checker ............. red     blocked by C5
  C7 e2e scenario ........... red     blocked by C5
  C8 degradation matrix ..... red     blocked by C5
  C9 held-out protocol ...... green
  C10 ui .................... green
PUBLISHABLE: no  (4 red)
Non-MPC work started while red: none detected.
```

`make mpc-status` exits non-zero when any component is red **and** the working tree contains new files under a path whose owning section is not CORE. This is the enforcement of "finish the core first"; it is not advice.

OVERRIDES Part I §5.0: do not implement the registry, the bindings or the gate before the pipeline they describe. Build C7 end to end on one scenario, then generalize. A registry over an unbuilt pipeline is descoped to rung D4 by default.

NEGATIVE REQUIREMENTS for the MPC:
- Do not add an eleventh MPC component. Additions to the MPC require deleting one, recorded in `BUILD_LOG.md`.
- Do not mark a component green on the strength of a passing test you wrote after seeing the implementation's output. Green requires the gate, and the gate requires a mutation test per 75.7.
- Do not ship a component whose gate is `true` or whose test file contains zero assertions. The ratchet (75.6) counts assertions precisely to make this visible.

------------------------------------------------------------
75.3 EVERYTHING ELSE IS OPTIONAL
------------------------------------------------------------

The following are explicitly OPTIONAL. None of them blocks a milestone, none of them appears in the paper's claims table unless green, and the README states their status from the machine-generated status table rather than from prose:

ECLIPSE stage F (redundancy index), stage G (decisive observation set), stage H (Pareto frontier); the Haskell reference admissibility checker; the Z3 test-only oracle; the live container range as a realism check; Go-side re-grounding from `bundle.jsonl`; the general graph explorer UI; the temporal property-graph store; FSM dimensions beyond identity, session, credential and privilege; the LLM narration surface; the benchmark registry and bindings; Tier C and Tier D language artifacts; cross-OS certificate-hash diffing on a third runner; the sensitivity sweep over q95/q99/q999 beyond the single mandated axis.

FORBIDDEN: describing any optional item in the present tense in `README.md` before its gate is green. The README renders component status from `mpc.toml` and `ratchet.json`; hand-written status prose in the README fails the docs gate.

OVERRIDES Part I section 53.2: the hand-written status banner required there in a verbatim shape ("> Status: research prototype (v0.1.0, milestone M10). Synthetic data only. Not a security product. See docs/LIMITATIONS.md.") and every other hand-written status statement in the README are replaced by tables rendered from `mpc.toml` and `ratchet.json`; that section's "exact section order" also has no slot for the first-screen elements this addendum requires — the `docs/NON-GOALS.md` link (75.1), the machine-generated language table (75.1 item 20), the generated waiver table (75.7 rule 5) and the no-weaponizable-code statement (75.9). An implementer following section 53.2 ships a README that fails the docs gate and 75.10 item 10.

------------------------------------------------------------
75.4 SECTION RE-TIERING TABLE
------------------------------------------------------------

```
TIER      SECTIONS (Part I)                        GATE POSTURE
--------  ---------------------------------------  ---------------------------------
CORE      0-4  preamble/operating contract          per-push, blocking
CORE      5-8  research questions, claims table     per-push, blocking
CORE      9-12 data model + entity resolution       per-push, blocking
CORE      17-19 temporal semantics (one lattice)    per-push, blocking
CORE      22    control catalog + guard language    per-push, blocking
CORE      25    ECLIPSE kernel A-E + certificate    per-push, blocking
CORE      32-34 repo hygiene, offline build         per-push, blocking
CORE      52-56 delivery, milestones, ratchet       per-push, blocking
--------  ---------------------------------------  ---------------------------------
STRETCH   13-16 dimensions 5-10                     nightly, non-blocking
STRETCH   20-21 graph engine (as SQL view)          nightly, non-blocking
STRETCH   26-29 live range (non-normative only)     nightly, non-blocking
STRETCH   35-38 full API contract                   nightly, non-blocking
STRETCH   43-47 verification beyond MPC gates       nightly, non-blocking
STRETCH   48-51 bench harness beyond one schema     nightly, non-blocking
--------  ---------------------------------------  ---------------------------------
APPENDIX  30-31 polyglot tiers C and D              tier-ordered, never blocking
APPENDIX  39-42 UI beyond the four screens          never blocking
```

OVERRIDES Part I §26: the live container range is no longer "the only place SPECTRA telemetry comes from". The seeded synthetic generator is the normative telemetry source; the range is a non-normative realism corroboration that produces bundles no published result depends on. Byte-identical replay is impossible with live services, and the reproducibility claim outranks the realism claim.

OVERRIDES Part I §52.1: milestones go green **once** per push on the CORE four languages (Python, Rust, Go, TypeScript) plus the full matrix nightly. "Green twice in a row on a clean clone" across 40+ toolchains is a cadence one engineer cannot sustain and creates direct pressure to weaken tests; the ratchet in 75.6 replaces it as the anti-regression mechanism.

OVERRIDES Part I §0.1 Law 1: the written-plan obligation applies at **increment** granularity (one `BUILD_LOG.md` entry per increment, typically 1-2 days of work), not per file. File-granularity planning is unaffordable with an agent that creates dozens of files per increment, and a law that is quietly violated corrodes the rest of the operating contract.

------------------------------------------------------------
75.5 THE DESCOPE LADDER
------------------------------------------------------------

When time runs out, descend this ladder. Cut the lowest-numbered rung that is still intact, in order. Never skip ahead to a higher rung because it is easier to delete.

```
                     KEEP  ^
                           |   D0  MPC C1-C10                 NEVER CUT
  ───────────────────────  |  ────────────────────────────────────────────
  cut last  ............   |   D12 the four UI screens -> CLI transcript
                           |   D11 degradation matrix -> 3 cells, not 15
                           |   D10 held-out set -> 1 family, not 3
                           |   D9  UI polish, theming, animation
                           |   D8  ECLIPSE stage E exactness -> SUBSET default
                           |   D7  Go checker re-grounding -> instance-set check
                           |   D6  Tier D languages (R, Julia, Octave)
                           |   D5  Tier C languages (range-realism emitters)
                           |   D4  bench registry, bindings, API surface
                           |   D3  FSM dimensions 5-10
                           |   D2  Haskell reference checker + Z3 oracle
                           |   D1  live container range  (NON-NORMATIVE)
  cut first ............   |
                     CUT   v
```

Rungs in cut order, with the exact demotion each rung performs:

- **D1 — Live container range.** Demote to a non-normative realism check. It produces bundles that are never used in a published number, never in a gate, never in the paper. If time is short it is deleted entirely and `docs/range/not-modeled.md` states that the realism corroboration was not performed. **RULE: the range is demoted to a non-normative realism check before the kernel is thinned.** Kernel thinning may not begin while the range is still normative or still consuming schedule.
- **D2 — Haskell reference checker and Z3 oracle.** Five implementations of one semantics (Rust kernel, Rust simulator, Go checker, Haskell reference, Z3 encoding) means five edits per rule-table change. Cut to three: kernel, simulator, Go checker. If Haskell goes, the honest justification for Haskell in the polyglot tiers goes with it — delete the directory, do not leave a stub.
- **D3 — FSM dimensions 5-10.** Ship identity, session, credential, privilege. The flagship counterfactual exercises exactly session binding, egress segmentation, credential rotation and iam_audit. Ship the remaining six as one documented extension point with one worked stub and a test that the extension point is exercised.
- **D4 — Benchmark registry, kernel bindings abstraction, full API surface.** Keep one results schema and one make target. Keep the subprocess + content-addressed JSON kernel boundary; delete any pyo3/cgo abstraction layer.
- **D5 — Tier C languages.** Range-realism emitters. Cut as a whole tier, not language by language (75.5.1).
- **D6 — Tier D languages.** Analysis and reporting. Their outputs move into the Python analysis path, which already exists.
- **D7 — Go checker re-grounding.** Ship the linear closure check over the published instance set, witness re-derivation, and the no-smaller-cut check against Ψ. Downgrade the written guarantee in the same commit: `docs/checker-scope.md` must read "validates the certificate against the instance set the kernel published; does not independently re-derive that set." **RULE: the guarantee text and the code are descoped in the same commit or the descope is rejected.**
- **D8 — Exact cardinality-minimality.** Make `minimality: SUBSET` the default and `EXACT` the exception requiring exhaustive verification. Minimum hitting set is NP-hard in the corridor count; 64 atoms is a representation width, not a tractability bound. The UI never prints "no smaller cut exists" on a `psi_relative` certificate.
- **D9 — UI polish.** Theming, animation, layout refinement. The four screens stay; they stop being pretty.
- **D10 — Held-out families.** Reduce from three scenario families to one. Publish that the held-out evidence is one family and that generalization is therefore untested.
- **D11 — Degradation matrix breadth.** Reduce cells, never the zero-false-ROBUST invariant. Report the reduced grid as reduced; do not interpolate, do not smooth, do not plot a curve through three points.
- **D12 — The four UI screens.** Replace with a recorded, regenerated-in-CI CLI transcript that shows the same investigation and the same counterfactual. This is the last rung. Below it there is no publishable artifact.

NEVER CUT, under any schedule pressure: C5 (kernel A-E), C6 (a checker of some scope, with its scope stated truthfully), C8's zero-false-ROBUST invariant on declared suppression classes, C9 (held-out protocol), the determinism charter, the claims-to-gate binding linter, and `LIMITATIONS.md`.

### 75.5.1 Polyglot tier order

**RULE: polyglot tiers are completed in tier order — A fully, then B fully, then C fully, then D.** Never start a language in tier N+1 while any language in tier N is missing its executing CI job, its mutation proof, or its consumer edge. An unfinished repository must be coherent (three complete tiers) rather than half-scaffolded everywhere (twelve directories each containing a hello-world).

```
TIER A  critical path          Python, Rust, Go, TypeScript, SQL, Bash
TIER B  independent oracles    Haskell, C, C++, one JVM language, x86-64 asm
        and measured perf
TIER C  range-realism          PowerShell, PHP, Ruby, Perl, Lua, Kotlin,
        emitters               Swift, Dart, ...
TIER D  analysis & reporting   R, Julia, GNU Octave
```

Each language earns its place by passing all three legs of `make polyglot-audit`: (a) a CI job that executes it on every push or nightly, (b) a deletion-mutation proof — stubbing the artifact turns a named CI job red, and the audit records that job name, (c) an edge in the build/consumer graph. A language failing all three is deleted in the same commit that discovers the failure, with the deletion recorded in `docs/polyglot-audit.md`. OVERRIDES Part I §30: MATLAB is replaced by GNU Octave, stated as Octave and never described as MATLAB-verified. Solidity, Verilog and VHDL are removed from the target set unless a named, executing, mutation-proved job exists for each; "immutable audit anchor" duplicates the BLAKE3 chain and does not qualify. OVERRIDES Part I section 52.12: the M9 deliverable list repeats the same target set — Verilog and VHDL for the hardware-attestation sensor model, Solidity for the append-only evidence-anchor experiment, MATLAB for analysis — and is overridden on exactly the terms stated here for section 30, with the tier order above also governing which of section 52.12's languages may be started. An implementer working M9 from section 52.12 alone still builds the Solidity evidence anchor and the Verilog/VHDL sensor model this rule deletes, still calls the analysis path MATLAB-verified, and starts Tier C and Tier D languages before Tier B is complete.

The README reports two machine-generated figures, never one: "N languages executing code in CI" and "M configuration and markup formats". Counting JSON, YAML, TOML, XML, HTML, CSS, Dockerfile or Makefile toward a language total is forbidden.

------------------------------------------------------------
75.6 THE SCOPE DEGRADATION PROTOCOL
------------------------------------------------------------

This is the procedure Claude Code follows when a milestone overruns its declared budget. It is not optional and it is not a judgement call.

```
   milestone budget exceeded
   (elapsed > budget declared in BUILD_LOG.md for this milestone)
            |
            v
   [1] STOP. Do not start the next increment. Do not "just finish this one file."
            |
            v
   [2] RECORD in BUILD_LOG.md: a DESCOPE entry (schema below).
            |
            v
   [3] Is any MPC component (C1-C10) red?
            |                          |
           yes                        no
            |                          |
            v                          v
   [4a] Descend the ladder      [4b] Stop adding scope.
        from D1 until the            Milestone closes as-is.
        freed effort covers
        the red component.
            |
            v
   [5] Apply the demotion IN CODE and IN DOCS in the same commit.
       A rung is not descoped until both moved.
            |
            v
   [6] Delete the stub. Do not carry it forward.
            |
            v
   [7] Re-run make mpc-status and make ratchet-check. Both must pass
       before the next increment begins.
```

OVERRIDES Part I sections 52.1.6, 0.1 (Law 5) and 0.7: "if a milestone cannot be completed as specified, stop and report" — halting, writing the BLOCKED entry, proposing options and waiting for a human before acceptance criteria move — is replaced, for a declared-budget overrun, by this fixed procedure, which descends the ladder, applies the demotion in code and docs and closes the milestone with no human decision point, recorded only in `BUILD_LOG.md`. An implementer following section 52.1.6 stops at step [1] and waits; an implementer following this flow deletes features, deletes directories and downgrades written guarantees on its own authority, which is the silent redefinition of section 52 acceptance criteria that Part I forbids.

**RULE: never silently carry a stub forward.** A stub is any file that (a) exists to satisfy a directory layout, (b) has a function body of `todo!()`, `panic("unimplemented")`, `pass`, `return nil` with a TODO comment, or an empty test file, or (c) is named in `mpc.toml` `artifacts` but has no executing gate. Stubs are deleted at descope time. `make stub-scan` enumerates them and fails the build if any stub exists outside `scenarios/extension-point/` (the one documented worked stub permitted by D3).

OVERRIDES Part I section 0.5: the mandated honest-stub forms (`NotImplementedYet("SPECTRA-TODO(...)")`, `Err(Unimplemented::new(...))`, `fmt.Errorf("SPECTRA-TODO(...)")`), the `make audit-stubs` inventory published in `docs/STATUS.md` and required by sections 4.5 and 4.7, and section 56.1's narrower ban on unimplemented markers only on demo-path files are replaced by whole-repo deletion: an unimplemented surface is no longer "acceptable and honest", and any stub outside `scenarios/extension-point/` fails `make stub-scan`. An implementer following section 0.5 keeps inventoried `SPECTRA-TODO(` surfaces for work this addendum makes optional, such as stage G's decisive observation set and stage H's Pareto frontier (75.3), and cannot pass 75.10 item 4.

`BUILD_LOG.md` DESCOPE entry schema — fixed field order, one entry per descope, never edited after commit:

```markdown
## DESCOPE 2026-XX-XX — M4 kernel fixpoint

- milestone:        M4
- budget_declared:  6 working days        (illustrative, not a target)
- elapsed:          11 working days       (illustrative, not a target)
- mpc_red:          C5, C6, C7, C8
- rung_applied:     D2 (Haskell reference checker + Z3 oracle)
- what_moved_in_code:
    - deleted haskell/ and its CI job `oracle-haskell`
    - deleted tests/differential/z3_*.py
- what_moved_in_docs:
    - docs/checker-scope.md: removed the differential-admissibility paragraph
    - docs/polyglot-audit.md: Haskell row moved to DELETED with reason
    - README claims table: row "differentially checked license logic" removed
- guarantee_now_reads: "license admissibility is checked by the Rust kernel and
  re-checked structurally by the Go checker; no third independent implementation
  exists."
- stubs_deleted:    haskell/src/Admissibility.hs (was todo-only)
- ratchet_effect:   gate count 14 -> 13; waiver W-0007 filed
- next_rung_if_needed: D3
```

NEGATIVE REQUIREMENTS:
- Do not descope by lowering an assertion, loosening a tolerance, shrinking a fixture, or marking a test `skip`. Those are test weakening (75.6), not descoping. Descoping removes a *feature* and its *claim*; it never removes a *check* on a feature that remains.
- Do not descope a rung and leave the README claim standing. A claim without its artifact fails `make claims-gate`.
- Do not invent a rung. The ladder is D1..D12 and is amended only by an explicit `BUILD_LOG.md` entry that adds a numbered rung and states where it sits.

------------------------------------------------------------
75.7 THE TEST RATCHET
------------------------------------------------------------

Milestone gating creates direct pressure to weaken a test to turn a milestone green. The ratchet makes weakening visible and expensive rather than invisible and free.

Check in `ratchet.json` at the repo root. CI regenerates the measured fields and compares.

```json
{
  "schema_version": 1,
  "milestones": [
    {
      "id": "M3",
      "closed_at_commit": "0000000000000000000000000000000000000000",
      "gates": [
        "gen-determinism", "ingest-gate", "er-eval", "guard-gate",
        "leakage-gate", "stub-scan", "claims-gate", "polyglot-audit"
      ],
      "counts": {
        "tests_total": 412,
        "assertions_total": 1877,
        "property_tests": 23,
        "mutation_tests": 9,
        "cert_corpus_rejections": 31,
        "e2e_specs": 5
      },
      "note": "all counts illustrative, not a target; CI writes the measured values"
    }
  ],
  "waivers": []
}
```

Rules, all enforced by `make ratchet-check`:

1. For every milestone already recorded, the current measurement of each `counts` field must be **>=** the recorded value, and the `gates` list must be a **subset-preserving superset**: no gate name may disappear.
2. A decrease in any count, or the disappearance of any gate, fails CI. The failure message names the field, the old value, the new value and the commit that recorded the old value.
3. A decrease is permitted only with a waiver entry:

```json
{
  "id": "W-0007",
  "date": "2026-XX-XX",
  "milestone": "M4",
  "field": "gates",
  "removed": ["oracle-haskell"],
  "delta": {"tests_total": -18, "assertions_total": -61},
  "rung": "D2",
  "rationale": "Haskell reference checker descoped per rung D2; its 18 tests tested only the deleted artifact. No test of a surviving feature was weakened. docs/checker-scope.md downgraded in the same commit.",
  "author": "rakshit",
  "expires": null
}
```

4. A waiver is valid only if `rationale` is non-empty, names a descope rung **or** states explicitly "not a descope", and the same commit contains the corresponding `BUILD_LOG.md` DESCOPE entry when a rung is named. A waiver whose rationale is a placeholder (`TODO`, `n/a`, `see PR`, fewer than 40 characters) fails the lint.
5. **Waivers surface in the README status table**, generated, with date and rationale — not only in git history. A repository whose README hides three waivers is dishonest by omission.
6. Assertion counting is defined, not eyeballed: `make count-assertions` parses each test tier for its assertion constructs (Rust `assert!`/`assert_eq!`/`proptest!` bodies, Go `t.Error*`/`t.Fatal*`/`require.*`, Python `assert` statements plus `pytest.raises` blocks, Playwright `expect(...)` calls) and writes the totals. The counter itself is tested against a fixture file with a known count.
7. `mutation_tests` counts only mutation tests registered in `docs/adversarial-review.md` (75.8) with a named injected defect and a named gate that must go red. A mutation test not in the registry does not count.

```
$ make ratchet-check
ratchet: M1 ok  M2 ok  M3 FAIL
  gates: 'polyglot-audit' present at M3 (commit a1b2c3d), absent now
  counts.assertions_total: 1877 recorded, 1702 measured (-175)
  counts.mutation_tests:   9 recorded, 9 measured (ok)
  no waiver found for this regression
ratchet-check: FAILED
hint: file a waiver in ratchet.json with a rationale and a BUILD_LOG DESCOPE
      entry, or restore the gate. Lowering the recorded value is not permitted.
```

NEGATIVE REQUIREMENTS:
- Do not edit a recorded `counts` value downward in place. The recorded values are append-only history; changes go through `waivers`.
- Do not satisfy the ratchet by adding trivial assertions (`assert!(true)`, `assert_eq!(1,1)`, asserting a constant you just defined). `make assert-triviality-lint` rejects assertions whose both sides are literals or whose expression contains no call into the crate under test.
- Do not mark a test `#[ignore]`, `t.Skip`, `@pytest.mark.skip` or `test.skip` to make a milestone green. Skipped tests are counted separately as `tests_skipped` and any nonzero value must be justified in the same waiver mechanism. OVERRIDES Part I sections 52.3 and 56.1: "zero test cases skipped" as an M0 acceptance condition and as a hard failure of `make test -- --strict` is replaced by a counted `tests_skipped` field that may be nonzero when a waiver carries a rationale satisfying rule 4 above. An implementer following Part I wires `--strict` to fail on any skipped test, which makes this waiver path unreachable and the `tests_skipped` field dead.

------------------------------------------------------------
75.8 THE ADVERSARIAL SELF-REVIEW OBLIGATION
------------------------------------------------------------

At every milestone close, before the milestone is marked green, write the answer to one question: **what is the cheapest way these gates could be passing for the wrong reason?** Then add a mutation test that would catch it.

Append to `docs/adversarial-review.md`, one block per milestone, never edited after the milestone closes:

```markdown
## M5 — ECLIPSE kernel, stages A-E

### Cheapest ways the gates could be green for the wrong reason

1. `zero-false-ROBUST` passes because the kernel returns UNSAFE for everything.
   Cheapness: one line. Detectability today: none — the invariant is one-sided.
   MUTATION MT-014: force `Reach_goal` to true under every cut.
   MUST turn red: `matrix-robust-yield` (ROBUST yield floor).
   Status: added, verified red, verified green after revert.

2. Liveness never declares BLIND because q99 is self-calibrated on the degraded
   run, so deletion inflates the threshold and hides itself.
   MUTATION MT-015: replace the hashed baseline calibration with the run's own
   distribution.
   MUST turn red: `blind-volume-monotonicity` (per-source blind volume must be
   non-decreasing as completeness falls).
   Status: added, verified red.

3. Simulator-vs-kernel agreement is tautological because both are generated from
   the same guard AST.
   MUTATION MT-016: perturb one guard in the AST before codegen.
   MUST turn red: nothing today — the mutation propagates to both backends.
   Action: the 256-config agreement test is DEMOTED to a codegen regression test
   in docs/checker-scope.md; real validation comes from oracle 3 in section 62.
   Status: demotion committed; MT-016 retained as a codegen check only.

4. The Go checker agrees because it consumes a Rust-generated artifact.
   MUTATION MT-017: corrupt one byte of the kernel's published instance set
   without updating the certificate hash.
   MUST turn red: `cert-corpus` case `tampered_instances`.
   Status: added, verified red.

5. ER precision looks perfect because the generator emits globally unique
   identifiers the resolver never has to merge.
   MUTATION MT-018: generator emits colliding display names across principals.
   MUST turn red: `er-eval` precision floor.
   Status: added, verified red; revealed a real false-merge path, fixed in
   commit <sha>.
```

Requirements:

1. Every milestone block lists **at least three** candidate wrong-reason hypotheses. Fewer than three is not a passing self-review; it is a failure of imagination and the milestone stays open.
2. Every hypothesis resolves to one of: a registered mutation test (`MT-NNN`) with the gate it must turn red; or an explicit admission that no gate catches it, plus the demotion or scope correction made in response. An unresolved hypothesis blocks the milestone.
3. Every registered mutation test is **verified red then green**: apply the mutation, observe the named gate fail, revert, observe it pass. `make mutation-verify` re-runs the full registry nightly and fails if any mutation no longer turns its gate red — that means the gate has decayed into decoration.
4. Mandatory gate-liveness mutations, present from M5 onward regardless of what else the review finds: break the fixpoint, break the liveness pass, break the license admissibility check, break the certificate hash comparison, break the ER merge rule. Each must turn a named gate red.
5. The adversarial review is written **before** the milestone is marked green in `mpc.toml`, and its commit precedes the status flip. `make review-order-check` fails on inversion, the same way `leakage-gate` fails on rules-hash/fixture-commit inversion.

NEGATIVE REQUIREMENT: do not write the review as reassurance. A block containing only "gates appear sound" is a lint failure. The output of this exercise is defects found, not confidence expressed.

------------------------------------------------------------
75.9 REPO POSTURE
------------------------------------------------------------

**License.** Apache-2.0. Reason, stated in `docs/licensing.md`: it carries an explicit patent grant and an explicit no-warranty clause, both of which matter for a security research artifact that a reader might run against their own telemetry, and it is unambiguously compatible with the dependency set. Do not dual-license. Do not add a non-commercial rider; that would make the repository non-open-source and is forbidden. `LICENSE` at the repo root; SPDX headers (`SPDX-License-Identifier: Apache-2.0`) on every source file, enforced by `make license-header-lint`. Third-party licenses are vendored under `third_party/licenses/` and `make license-inventory` fails on a dependency with no recorded license.

**SECURITY.md.** At the repo root, containing:

```markdown
# Security Policy

## Scope
SPECTRA is a research artifact. It is not a product, it is not deployed, and it
accepts no network input at runtime. The security-relevant attack surface is:
  1. the ingest parser, which processes untrusted telemetry files;
  2. `spectra verify`, which processes untrusted certificates;
  3. the archive/decompression paths used by both.

## Reporting
Report to <contact> with the input file that triggers the issue and the commit
SHA. Expect acknowledgement within a stated window; there is no bounty, no SLA
and no embargo negotiation — this is a one-person research repository and the
policy says so rather than implying a security team that does not exist.

## Explicitly out of scope
- Findings in the container scenario stack, which is non-normative, offline,
  egress-blocked, and never exposed.
- "Missing authentication" on the local API: SPECTRA is single-user, local-only,
  and binds to loopback. See NON-GOALS item 16.
- Denial of service by supplying an enormous bundle: parser limits are declared
  in the ingest section; exceeding them is a documented quarantine, not a bug.

## Handling of telemetry
SPECTRA processes only telemetry you supply. It transmits nothing, phones home
never, and writes only under the run directory you name.
```

**No-weaponizable-code statement.** Place verbatim in `README.md` (first screen), in `SECURITY.md`, and in `scenarios/README.md`:

> SPECTRA's scenario generators model attacker behavior **at the telemetry level only**. They emit synthetic log records describing what an attack would have looked like in an authentication log, a proxy log, an audit log or a process table. They contain no exploit, no payload, no shellcode, no credential-stealing code, no lateral-movement tooling, and no code that interacts with any system other than the local file it writes. Nothing in this repository can be repurposed to attack anything. The generators cannot compromise a host because they do not act on hosts; they write lines to a file.

Enforce it, do not merely assert it. `make weaponization-scan` fails the build on: any network client call (`socket`, `requests`, `net/http`, `curl`, `Invoke-WebRequest`) inside `scenarios/` or `generators/`; any process-spawn primitive in those trees; any embedded base64/hex blob longer than a declared limit; any file write outside the declared run directory; any reference to a real CVE with an accompanying code path rather than a bare citation in a provenance note. The scan's allowlist lives in `scenarios/weaponization-allowlist.toml` and every entry carries a rationale, linted for non-emptiness.

**Name collision.** `README.md` and `docs/naming.md` state: "ECLIPSE here is an internal acronym for this project's proof kernel (Evidence-Licensed Cut Proofs over Silent Envelopes). It is unrelated to the Eclipse Foundation, the Eclipse IDE, Eclipse Temurin or Eclipse Adoptium, and uses none of their marks." Prefer "the SPECTRA kernel" in user-facing prose; reserve "ECLIPSE" for internal and spec contexts.

**Remaining posture files**, each required before the repository is made public: `LIMITATIONS.md` (linked from the README's first screen, partly generated from measured data), `docs/NON-GOALS.md` (75.1), `docs/claims.md` (every externally visible claim bound to the gate or bench artifact that supports it), `docs/checker-scope.md` (what a passing checker does **not** establish), `docs/polyglot-audit.md` (mutation-proof table, not a rationale table), `docs/adversarial-review.md` (75.8), `CONTRIBUTING.md` stating that the repository accepts issues but that the milestone plan is fixed, and `CITATION.cff`.

OVERRIDES Part I section 53.4: `docs/claims.toml`, the machine-parsed list of claim-anchor-to-test-ID pairs read by `make docs-check`, is replaced by `docs/claims.md`, the registry binding every externally visible claim to the gate or bench artifact that supports it, read by `make claims-gate` and `make banned-phrase-gate`. An implementer who builds `claims.toml` leaves both of this section's gates with no file to read, and ratchet rule 1 in 75.7 then locks in whichever gate names were recorded first.

OVERRIDES Part I sections 3.12, 4.5 and 4.7: `docs/LIMITS.md`, required there to hold all nine limit statements verbatim and to be the file the UI footer and `spectra --about` render from, is replaced by `LIMITATIONS.md` as the single limits document — the file this section requires before the repository is made public, links from the README's first screen, and places on the NEVER CUT list in 75.5. An implementer following section 4.5 ships `docs/LIMITS.md`, which no gate in this section looks for, and the nine "may never claim" statements then live outside the document every Part II gate reads.

**Forbidden in every externally visible artifact** — README, repository description, paper abstract, UI strings, demo script, commit-message templates, and any CV or portfolio text generated from this repository: "formally verified", "guaranteed", "prevents", "would have stopped", "state of the art", "enterprise-grade", "production-ready", "realistic" (outside `docs/range/not-modeled.md`), "AI-powered", "detects attacks", and any bare "minimum cut" not qualified by "over the declared control catalog". `make banned-phrase-gate` greps for these and fails on a hit outside a registered entry in `docs/claims.md`.

------------------------------------------------------------
75.10 ACCEPTANCE FOR THIS SECTION
------------------------------------------------------------

This section is satisfied when all of the following are true simultaneously on a clean clone with the network off:

1. `make mpc-status` exists, reads `mpc.toml`, and exits non-zero when a red component coexists with new non-CORE work.
2. `docs/NON-GOALS.md` contains the twenty items of 75.1 and is linked from the README's first screen.
3. `descope-ladder` rungs D1..D12 are recorded in `docs/descope-ladder.md` with the exact demotion each performs, and `BUILD_LOG.md` contains a DESCOPE entry for every rung applied.
4. `make stub-scan` passes with zero stubs outside the single permitted extension-point stub.
5. `ratchet.json` exists, `make ratchet-check` passes, and every waiver carries a rationale over the length floor plus a matching `BUILD_LOG.md` entry.
6. `make mutation-verify` passes and every registered mutation turns its named gate red.
7. `docs/adversarial-review.md` has one block per closed milestone, each with at least three hypotheses, each resolved.
8. `LICENSE`, `SECURITY.md`, the no-weaponizable-code statement in all three required locations, and `make weaponization-scan` all present and green.
9. `make banned-phrase-gate` and `make claims-gate` both green.
10. The README's status table, language table and waiver table are machine-generated; no hand-written status prose survives the docs gate.

Every numeral appearing in this section's examples — budgets, elapsed days, test counts, assertion counts, corpus sizes, milestone identifiers — is illustrative, not a target. CI writes the measured values; a run that copies an illustrative value into a result artifact fails the docs gate.
