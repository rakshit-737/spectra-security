# SPECTRA — PLAN v1

Status: **DRAFT, AWAITING HUMAN APPROVAL.** No implementation has started. No repository skeleton
has been created. Per `KICKOFF.md` §4, nothing is built until this plan is approved in-session.

---

## 0. How this plan was produced, honestly

The specification is 24,755 lines across 77 sections. It was **not** read end to end by one reader.
It was read by delegated agents, each assigned specific section files, each returning a structured
extraction. Coverage:

| Part | Sections | Read for this plan |
|---|---|---|
| I | 0–56 | 0–4, 30–34, 52–56 read in full; 5–29 and 35–51 read only through the conflict audit |
| II | 57–76 | all 20 sections read, each by at least one agent |

The KICKOFF checklist item *"confirmation that you read the master prompt in full"* is therefore
**not ticked**. What is true: every section was read by some agent, and the sections governing the
skeleton, milestones, descope ladder and language tiering were read in full. The engine sections
(17–29, 35–51) have been read only against their Part II counterparts. **Before M4 begins,
sections 17–29 must be read directly.**

---

## 1. What is being built

SPECTRA reconstructs how a system's security state evolved from degraded and partly tampered
telemetry, then proves which security control, at which level, severs the attack chain **in the
model**. The proof kernel is ECLIPSE. Its distinguishing idea: missing telemetry is modeled as an
explicit *license* for unobserved attacker steps, so the system separates "this control is needed"
from "this control is needed **only because you could not see**" — the blindness premium.

Naming, already settled by the spec: §73.10 bans the string `eclipse` from every crate, module and
directory name, and non-goal 19 disclaims any relationship to the Eclipse Foundation. ECLIPSE is an
internal acronym only. The crate is `spectra-kernel`; the binary is `spectra prove`.

---

## 2. Milestones

Source: Part I §52, amended by Part II §75. **A milestone does not start until the previous one is
green.** Per §74.0, "the build fails otherwise" now means "a named gate exists in `ci/gates.toml`,
in exactly one tier, and fails the build in that tier".

| ID | Goal | Gate |
|---|---|---|
| **M0** | A clone builds, lints and tests an empty system, offline, on Linux/macOS/WSL2. New: Bash, Make, Docker, YAML. | `make m0-verify` |
| **M1** | Seeded synthetic telemetry with recorded ground truth, honestly generated. New: Python. | `make m1-verify` |
| **M2** | Heterogeneous records become entity-resolved, time-indexed, stable-ID events in Postgres. New: SQL. | `make m2-verify` |
| **M3** | **Vertical slice.** One command: scenario → generation → replayed control configuration rendered in the browser. | `make demo-slice`, `make m3-verify` |
| **M4** | Kernel stages A–D: liveness, licenses, silent envelope, fixpoint. New: C, only if the liveness hot loop demonstrably needs it. | `make m4-verify` |
| **M5** | Kernel stage E and the certificate object: two-sided minimal cut. No new languages. | `make m5-verify` |
| **M6** | The certificate is verifiable by code sharing nothing with the solver: independent Go checker, differential gates. New: Haskell. | `make m6-verify` |
| **M7** | Second research axis + stages F, G, H: degradation, tampering, redundancy, decisive observation set, frontier. New: R or Julia. | `make m7-verify` |
| **M8** | The flagship interaction complete: full UI and PROVE flow. New: HTML, CSS/SCSS. | `make m8-verify` |
| **M9** | The polyglot long tail, each language with a stated technical reason, plus measured performance. | `make m9-verify`, `make polyglot-report` |
| **M10** | The repository is presentable and the demo cannot rot: docs, demo, release. | `make release-check` |

M3 is the mandatory early vertical slice. Everything before it is scaffolding; everything after
deepens a slice that already runs end to end.

### What each milestone explicitly does *not* deliver

The part most likely to be violated under pressure.

- M0–M2 deliver **no** state reconstruction and **no** kernel.
- M4 delivers stages A–D but **no** cut and **no** certificate.
- M5 delivers the cut and certificate but **no** independent verification — until M6 lands, a
  certificate is self-attested and must be described that way in every artifact.
- Before M7, **no** claim about robustness under missing telemetry may appear anywhere.
- M9 is the polyglot long tail. It is an early rung on the descope ladder, not a late one.

---

## 3. Minimum publishable core

The smallest artifact set that makes SPECTRA a defensible public repository and a submittable
workshop paper. Recorded machine-readably in `mpc.toml`, one `[[component]]` per row, each with
`id`, `name`, `gate`, `artifacts`.

| ID | Component | Done means |
|---|---|---|
| **C1** | Seeded synthetic generator | Pure function `(seed, scenario_id, degradation_spec) → bundle.jsonl + ground_truth.json` |
| **C2** | Ingest + canonical event schema | Every raw record parsed or quarantined with a reason code; zero silent drops; hardening limits enforced |
| **C3** | Entity resolution + quality contract | Deterministic; precision/recall published against C1 ground truth across the matrix |
| **C4** | Rule table + guard language + codegen | One canonical AST, one AST hash, both backends assert equal hash |
| **C5** | Kernel stages A–E | Liveness, semi-naive grounding with provenance, silent envelope, Dowling–Gallier fixpoint under cut, hitting-set loop |
| **C6** | Independent Go checker | Closure, goal-unreachability, license implication, witness re-derivation, no-smaller-cut |
| **C7** | One end-to-end scenario | One **held-out** scenario runs clone → generate → ingest → resolve → prove → verify with no manual step |
| **C8** | Degradation matrix | Completeness axis defined; per-operator seeds; ground-truth re-linking under perturbation defined |
| **C9** | Held-out / overfit protocol | Rules frozen and hash-pinned before each scenario family; TUNED vs HELD-OUT published separately |
| **C10** | UI: one investigation, one counterfactual | Four screens: control toggles + PROVE, scoped verdict header, indented derivation, evidence inspector |

Hard rules: there is **no eleventh component** — adding one requires deleting one, recorded in
`BUILD_LOG.md`. A component is never green on a test written after seeing the implementation's
output. A component whose gate is `true`, or whose test file contains zero assertions, does not
ship — the ratchet counts assertions precisely to make that detectable.

This **overrides Part I §5.0**, which ordered the registry and bindings built before the pipeline
they describe. Build C7 end to end on one scenario first.

---

## 4. Descope ladder

When a milestone overruns: descend this ladder, cutting the lowest-numbered intact rung. Never skip
ahead because a higher rung is easier to cut.

| Rung | Cut |
|---|---|
| **D1** | **Live container range.** Demote to a non-normative realism check producing bundles never used in a published number, a gate, or the paper. |
| **D2** | Haskell reference checker and Z3 oracle. Five implementations of one semantics is too many; keep Rust kernel, Rust simulator, Go checker. |
| **D3** | FSM dimensions 5–10. Ship identity, session, credential, privilege — exactly what the flagship counterfactual exercises. |
| **D4** | Benchmark registry, kernel bindings abstraction, full API surface. Keep one results schema, one make target, the subprocess + content-addressed JSON kernel boundary. |
| **D5** | Tier C languages, **as a whole tier**, never language by language. |
| **D6** | Tier D languages (R, Julia, Octave). Their outputs move into the existing Python analysis path. |
| **D7** | Go checker re-grounding. Keep linear closure, witness re-derivation, no-smaller-cut against Ψ; downgrade the independence claim in writing. |
| **D8** | Exact cardinality-minimality. `minimality: SUBSET` becomes the default, `EXACT` the exception. |
| **D9** | UI polish: theming, animation, layout. The four screens stay; they stop being pretty. |
| **D10** | Held-out families: three → one. Publish that held-out evidence is one family and generalization is untested. |
| **D11** | Degradation matrix breadth: fewer cells, never the zero-false-ROBUST invariant. Report the reduced grid as reduced; do not interpolate. |
| **D12** | The four UI screens → a recorded, CI-regenerated CLI transcript showing the same investigation and counterfactual. |

**Never cut under any schedule pressure:** C5 (kernel A–E); C6, a checker of *some* scope with its
scope stated truthfully; and C8's zero-false-ROBUST invariant on declared suppression classes.
Below D12 the project is not publishable, and the honest response is to publish less — not to
publish weaker claims in a stronger frame.

Every rung taken is recorded in `docs/descope-ladder.md` with the exact demotion it performs, and
gets a `DESCOPE` entry in `BUILD_LOG.md`.

---

## 5. Language tiering

The 40+ language surface is a deliberate goal, not accidental scope. It is kept, and made honest by
enforcement rather than by a rationale table. Tiers are completed **in order** — A, B, C, D — so an
unfinished repository is coherent rather than half-scaffolded everywhere.

| Tier | Promise | Cut at |
|---|---|---|
| **A** | The product. Critical path. | never |
| **B** | Independent oracles and measured performance. Each must be consumed by something. | D2 (partial) |
| **C** | The heterogeneous observed estate. The promise is "SPECTRA reconstructs state across implementation languages it knows nothing about" — a real research property. | D5, whole tier |
| **D** | Research and formal artifacts, each with a narrow stated promise. | D6 |

### The rule that keeps it honest

`make polyglot-audit` requires, per language: (a) a CI job executing it on every relevant change,
(b) a declared consumer edge, and (c) a **mutation** — corrupting that component's output must turn
a downstream gate red. A language failing the mutation check is padding, and is deleted rather than
documented.

**Counting honesty.** JSON, YAML, TOML, XML, HTML, CSS, SCSS, Dockerfile, Makefile, CMake and HCL
are configuration and markup. They may appear in the GitHub language bar. They may **never** be
counted in a prose claim such as "N languages". Nothing is miscategorized in `.gitattributes` to
inflate the bar.

**MATLAB is not used.** GNU Octave is, and the docs say Octave.
`docs/polyglot/octave-not-matlab.md` is mandatory.

### Roster

| Tier | Language | Directory | Role |
|---|---|---|---|
| A | Bash | `scripts/` | Make targets' shell layer; range compose driver |
| A | Go | `go/` | `spectra verify` — independent certificate checker sharing no code with the solver |
| A | Python | `python/` | Generator, ingest orchestration, entity resolution, API |
| A | Rust | `rust/` | The proof kernel: grounder, fixpoint, cut solver, simulator |
| A | SQL | `db/` | Fact-base schema, recursive-CTE state view, migrations |
| A | TypeScript | `frontend/src/` | Frontend, proof UX, demo pane |
| B | C | `c/ingest_scanner/` | Ingest hot path: record framing + field scanner, with a **measured** differential against Rust |
| B | C++ | *(unassigned — see CONFLICTS)* | Deterministic entity-key interner on the same hot path |
| B | Haskell | *(rename required — see CONFLICTS)* | Policy oracle: license admissibility relation + guard evaluator |
| B | Java | `java/` | Token/identity service in the observed estate, dual-instrumented |
| B | C# | `dotnet/` | Resource/service host in the observed estate, dual-instrumented |
| B | x86-64 Assembly | `fixtures/asm/` | Syscall-trace fixture emitter, byte-exact |
| C | Kotlin | *(role superseded)* | API gateway; emits logback JSON |
| C | PHP | `lab/legacy-portal/` | Legacy self-service web app; emits `error_log` + access logs |
| C | Ruby | `lab/automation-runner/` | Internal admin console; Rails-style tagged logger |
| C | Perl | `perl/` | Cron/rotation utility; plain syslog lines, no field structure |
| C | Lua | `lab/transformers/` | OpenResty reverse proxy; nginx `log_format` |
| C | Scala | *(role superseded)* | Nightly batch reconciliation; log4j2 pattern layout |
| C | Groovy | `gradle/`, `scenario-dsl/` | Build pipeline; emits build/deploy events |
| C | Swift | *(role superseded)* | Linux-hosted session service; swift-log structured output |
| C | Objective-C | *(role superseded)* | Legacy agent, clang + GNUstep on Linux |
| C | Dart | `mobile/analyst-console/` | Desktop client issuing API calls |
| C | PowerShell | `scripts/win/` | Admin host automation running as `pwsh` on Linux |
| D | R | `analysis/r/` | Degradation-matrix statistics: median, IQR, bootstrap |
| D | Julia | `analysis/julia/` | Independent re-implementation of the same degradation statistics |
| D | GNU Octave | `octave/` | Inter-arrival quantile sensitivity (q95/q99/q999) |
| D | F# | *(role superseded)* | Pareto frontier over enumerated corridors |
| D | Solidity | `chain/authz-fixture/` | Offline EVM event-log source class (Foundry/anvil, offline) |
| D | Verilog | `hw/verilog/` | Bounded FIFO log sink, simulated; generates a loss trace |
| D | VHDL | `hw/vhdl/` | Independently authored implementation of the *same* FIFO |
| D | WebAssembly | `wasm/preimage/*.wat` | Hand-authored canonical-preimage encoder |
| D | YARA | `rules/yara/` | Declarative labelling of generator artifact blobs |

Tier B/C/D directories are a **known problem**: Part II superseded most Part I language roles
without restating directories, and §73.10's ban on `eclipse` in names invalidates several Part I
paths outright. See `CONFLICTS.md` and decision 4 below.

---

## 6. Evidence protocol

- **Held-out vs tuned.** A held-out scenario set is generated and sealed — hash committed, contents
  unread — *before* the rule table is authored. Headline numbers come only from held-out scenarios
  under a rule table whose hash was fixed before the held-out set was opened. Tuned and held-out
  results are reported separately; the README quotes held-out only.
- **Overfit ledger.** Every rule, axiom or threshold added in response to a failing scenario is
  recorded with what failed and what changed.
- **Pre-registration.** Metric definitions, seed counts, variance reporting and the scenario
  inventory are committed before the rule table exists.
- **Claims registry.** Every externally visible claim is a row in `CLAIMS.md` bound to the artifact
  and gate that produced it. A claim with no backing artifact fails CI.

---

## 7. CI tiering

Every gate is a row in `ci/gates.toml`, in exactly one tier. There is no other place a gate may be
declared; a requirement with no gate id is not a requirement.

| Tier | Trigger | Ceiling | A failure means |
|---|---|---|---|
| T0 | pre-commit, local, in WSL2 | ~60 s | commit refused locally; never authoritative |
| T1 | every push and PR | ~20 min | PR red, merge blocked |
| T2 | nightly, `main` | ~90 min | milestone loses green; `main` marked degraded in README |
| T3 | weekly, `main` | ~6 h | release blocked; headline numbers invalidated until green |

(Ceilings are illustrative, not targets.) Tier C/D language jobs and the polyglot mutation audit are
**T2** — a Tier C/D failure never blocks a Tier A milestone. Benchmarks are **T3 only**: the
variance protocol needs a quiet runner. "Green twice in a row on a clean clone" applies to T2 only.

---

## 8. Environment

Development is on Windows 11. **Every make target runs inside WSL2 or the devcontainer.** `TZ=UTC`,
`LC_ALL=C`, LF enforced by `.gitattributes`. The offline claim is a T1 gate: `make build-offline`
builds from a clean clone with networking disabled.

---

## 9. Decisions needed — these block the skeleton

Each has a recommendation. None has been assumed.

1. **Licence.** Not chosen in the spec. → Apache-2.0 (patent grant, standard for security tooling).
2. **Repository and module name.** `spectra-security` was the working name. It must be fixed before
   Go module paths and crate names exist — changing it later rewrites `go.work`, every `go.mod` and
   every import path.
3. **GitHub account and remote.** Needed for CI to exist at all. Not yet known.
4. **Tier B/C/D directory layout.** Part II superseded roles without restating paths. One naming
   scheme must be chosen now or the long tail is laid out inconsistently.
5. **Scope commitment.** How far down the descope ladder is acceptable *up front*? Committing now to
   "MPC + Tier A and B" yields a far better repository than discovering it at M9.

---

## 10. What session one will not do

No kernel. No grounding, no fixpoint, no liveness pass, no guard AST compiler, no solver. No
generator. No range. No `.rs` file containing logic.

After approval, and only that: directories, root files, declared-but-failing make targets,
declared-but-skipped CI jobs, and empty package roots for **Tier A only**.
