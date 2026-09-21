# SPECTRA — PLAN v1

Status: **APPROVED IN-SESSION 2026-09-20; SKELETON BUILT; A PYTHON REFERENCE SLICE RUNS END TO
END.** The slice implements a generator, ingest, entity resolution, grounding, liveness, the
envelope, reachability, a cut search, a certificate and a checker, in Python rather than the
specified Rust and Go (ADR-0013). Three gates run: `G-SKELETON-001` and `G-PYREF-001` in CI on
every push, and `G-WIN-001` as the Makefile's host guard. No milestone is green. The approval `KICKOFF.md` §4
requires is recorded in `BUILD_LOG.md`, increment INC-0002.

---

## 0. How this plan was produced, honestly

The specification is 25,919 lines across 77 sections (`docs/prompt/part1/` and
`docs/prompt/part2/`, counted 2026-09-20). It was **not** read end to end by one reader. It was
read by delegated agents, each assigned specific section files, each returning a structured
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
| **M2** | Heterogeneous records become entity-resolved, time-indexed, stable-ID records in Postgres. New: SQL. | `make m2-verify` |
| **M3** | **Vertical slice.** One command: scenario → generation → replayed control configuration rendered in the browser. | `make demo-slice`, `make m3-verify` |
| **M4** | Kernel stages A–D: liveness, licenses, silent envelope, fixpoint. New: C, only if the liveness hot loop demonstrably needs it. | `make m4-verify` |
| **M5** | Kernel stage E and the certificate object: two-sided minimal cut. No new languages. | `make m5-verify` |
| **M6** | The certificate is verifiable by code sharing nothing with the solver: independent Go checker, differential gates. New: Haskell. | `make m6-verify` |
| **M7** | Second research axis + stages F, G, H: degradation, tampering, redundancy, decisive observation set, frontier. New: R or Julia. | `make m7-verify` |
| **M8** | The flagship interaction complete: full UI and PROVE flow. New: HTML, CSS/SCSS. | `make m8-verify` |
| **M9** | The polyglot long tail, each language with a stated technical reason, plus measured performance. | `make m9-verify`, `make polyglot-report` |
| **M10** | The repository is presentable and the demo cannot rot: docs, demo, release. | `make release-check` |

None of the names in the Gate column has a row in `ci/gates.toml`. Each is a declared `Makefile`
target that exits non-zero as not implemented — honest, but not a gate: per §7, a gate is a row in
`ci/gates.toml` in exactly one tier and there is no other place a gate may be declared. The column
records the target each milestone is INTENDED to carry. TODO(M0): register each name in
`ci/gates.toml`, or replace it with the registered gate id that will cover the milestone.

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
| **C2** | Ingest + canonical record schema | Every raw record parsed or quarantined with a reason code; zero silent drops; hardening limits enforced |
| **C3** | Entity resolution + quality contract | Deterministic; precision/recall published against C1 ground truth across the matrix |
| **C4** | Rule table + guard language + codegen | One canonical AST, one AST hash, both backends assert equal hash |
| **C5** | Kernel stages A–E | Liveness, semi-naive grounding with provenance, silent envelope, Dowling–Gallier fixpoint under cut, hitting-set loop |
| **C6** | Independent Go checker | Closure, goal-unreachability, license implication, witness re-derivation, no-smaller-cut |
| **C7** | One end-to-end scenario | One **held-out** scenario runs clone → generate → ingest → resolve → prove → verify with no manual step |
| **C8** | Degradation matrix | Completeness axis defined; per-operator seeds; ground-truth re-linking under perturbation defined |
| **C9** | Held-out / overfit protocol | Rules frozen and hash-pinned before each scenario family; TUNED vs HELD-OUT published separately |
| **C10** | UI: one investigation, one counterfactual | Four screens: control toggles + PROVE, scoped verdict header, indented counterexample tree with the GHOST distinction, degradation strip |

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
scope stated truthfully; C8's zero-false-ROBUST invariant on declared suppression classes; C9, the
held-out protocol; the determinism charter; the claims-to-gate binding linter; and
`LIMITATIONS.md`.
Below D12 the project is not publishable, and the honest response is to publish less — not to
publish weaker claims in a stronger frame.

Every rung taken is recorded in `docs/descope-ladder.md` with the exact demotion it performs, and
gets a `DESCOPE` entry in `BUILD_LOG.md`.

---

## 5. Language tiering

The polyglot surface is a deliberate goal, not accidental scope. It is kept, and made honest by
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
| B | C++ | `cpp/entity_interner/` | Deterministic entity-key interner on the same hot path — the Rust interner it is to be measured against has no owner (see CONFLICTS) |
| B | Haskell | `haskell/policy-oracle/` | Policy oracle: license admissibility relation + guard evaluator |
| B | Java | `java/` | Token/identity service in the observed estate, dual-instrumented |
| B | C# | `dotnet/` | Resource/service host in the observed estate, dual-instrumented |
| B | x86-64 Assembly | `fixtures/asm/` | Syscall-trace fixture emitter, byte-exact |
| C | Kotlin | `estate/kotlin-gateway/` (proposed, decision 4) | API gateway; emits logback JSON |
| C | PHP | `estate/php-portal/` (proposed, decision 4) | Legacy self-service web app; emits `error_log` + access logs |
| C | Ruby | `estate/ruby-console/` (proposed, decision 4) | Internal admin console; Rails-style tagged logger |
| C | Perl | `estate/perl-rotator/` (proposed, decision 4) | Cron/rotation utility; plain syslog lines, no field structure |
| C | Lua | `estate/lua-proxy/` (proposed, decision 4) | OpenResty reverse proxy; nginx `log_format` |
| C | Scala | `estate/scala-batch/` (proposed, decision 4) | Nightly batch reconciliation; log4j2 pattern layout |
| C | Groovy | `estate/groovy-pipeline/` (proposed, decision 4) | Build pipeline; emits build/deploy events |
| C | Swift | `estate/swift-session/` (proposed, decision 4) | Linux-hosted session service; swift-log structured output |
| C | Objective-C | `estate/objc-agent/` (proposed, decision 4) | Legacy agent, clang + GNUstep on Linux |
| C | Dart | `estate/dart-client/` (proposed, decision 4) | Desktop client issuing API calls |
| C | PowerShell | `estate/pwsh-host/` (proposed, decision 4) | Admin host automation running as `pwsh` on Linux |
| D | R | `analysis/r/` | Degradation-matrix statistics: median, IQR, bootstrap |
| D | Julia | `analysis/julia/` | Independent re-implementation of the same degradation statistics |
| D | GNU Octave | `octave/` | Inter-arrival quantile sensitivity (q95/q99/q999) |
| D | F# | `fsharp/frontier/` | Pareto frontier over enumerated corridors |
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

### What is actually installed, as of 2026-09-21

| Toolchain | State | Consequence |
|---|---|---|
| Python 3.14 | present | the reference slice is built in it |
| Node 24 | present | unused so far |
| Java 25 | present | unused so far |
| Rust (`cargo`, `rustc`) | **absent** | the kernel cannot be compiled |
| Go | **absent** | the independent checker cannot be compiled |
| Docker | **absent** | the range cannot run; the devcontainer cannot start |
| `make` | **absent locally**; present on the CI runner | targets run in CI on every push, not on this machine |
| WSL distribution | **none installed** | the host guard cannot be satisfied |

Consequences, recorded because they change what any status in this plan can mean.

**`make` is absent on this machine, and has been running in CI all along.** CORRECTED 2026-09-21.
An earlier version of this section said "`make` has never run in this repository". That was false:
it generalised from the development machine to the repository without checking the remote. The T1
workflow runs `make skeleton-verify` on a GitHub Ubuntu runner on every push, and has since the first
CI commit. Its first eleven runs FAILED, correctly, reporting exactly the eleven required paths that
were then missing; it went green once they existed. That is the strongest evidence in this
repository that a gate works, and it was produced by a machine this session did not control. Every
Makefile target other than `skeleton-verify` and `guard-sandbox` is still unexecuted.

**M0 is not blocked by the missing local `make`.** Its gate `make m0-verify` can run in CI. It is
blocked because `m0-verify` is not implemented, which is a different and smaller problem. The
milestone table keeps saying `not started` until that gate exists and passes.

**The kernel and checker are Python.** ADR-0013 records the decision and its cost: two Python
modules written in one session do not give the checker the independence the specification's design
provides, so no certificate may be described as independently verified until the Go checker exists.
`rust/` and `go/` keep their roots and remain the specified home of the real implementations.

---

## 9. Decisions

### Settled, 2026-09-20

1. **Licence — Apache-2.0.** Chosen for the patent grant, which matters for security tooling.
   Recorded in `docs/adr/0002`. Requires a `NOTICE` file.
2. **Repository and module name — `spectra-security`.** Published at
   `github.com/rakshit-737/spectra-security`. Go module prefix
   `github.com/rakshit-737/spectra-security`; Rust crates named `spectra-*`. Recorded in
   `docs/adr/0003`. Renaming later rewrites every import path, so this is now fixed.
3. **Remote — public from the first commit.** The consequence is that every status marker and every
   claim must be honest from day one; the README claims nothing and every milestone reads
   "not started". Enforced going forward by the claims registry. Recorded in `docs/adr/0009`.

### Still open

4. **Tier B/C/D directory layout.** Part II superseded most Part I language roles without restating
   their paths, and §73.10's ban on `eclipse` in names invalidates several Part I directories
   outright. Proposed scheme: Tier B keeps its own top-level directory per language; Tier C lives
   under `estate/<lang>-<role>/`; Tier D under its research directory. This is proposed, not
   settled — each language's directory record says so.
5. **Scope commitment.** How far down the descope ladder is acceptable *up front*? Committing now to
   "MPC + Tier A and B" yields a far better repository than discovering it at M9.
6. **The 140 specification conflicts.** See `DECISIONS.md`. 66 block M0-M3 and 42 of those are HIGH
   severity. Each carries a conservative default, so building proceeds without answers — on record,
   not on a guess. Recorded in `docs/adr/0008`.

---

## 10. What session one will not do

No kernel. No grounding, no fixpoint, no liveness pass, no guard AST compiler, no solver. No
generator. No range. No `.rs` file containing logic.

After approval, and only that: directories, root files, declared-but-failing make targets,
declared-but-skipped CI jobs, and empty package roots for **Tier A only**.
