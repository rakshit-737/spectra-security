============================================================
30. POLYGLOT ARCHITECTURE PRINCIPLE
============================================================

30.1 The rule

1. Every language in this repository must do a job that is materially harder, less
   trustworthy, or less honest to do in a language already present. Write that reason down
   before you write the code.
2. A language is present in SPECTRA for exactly one of four reasons, and you must state
   which one: (a) it is the production implementation language for that concern, (b) it
   provides a performance, memory-layout or concurrency property the core cannot,
   (c) it is the native language of a heterogeneous system in the observed lab and its
   telemetry must look genuinely like that system's telemetry, (d) it is a formal or
   analytical artifact whose value is that it was written independently of the core.
3. If you cannot name the reason in one sentence that survives the question "why not just
   Python or Rust?", do not add the language. Delete the directory.

30.2 The four tiers

```
            +---------------------------------------------------------------+
  TIER 1    |  PRODUCTION CORE                                              |
  ship it   |  Python (API/reconstruction/harness)  TypeScript (UI)         |
            |  SQL (schema+queries)  JSON/YAML/TOML (contracts)             |
            +---------------------------------------------------------------+
                      |                                    ^
                      v                                    |
            +---------------------------------------------------------------+
  TIER 2    |  HIGH-PERFORMANCE CORE + AGENTS                               |
  hot path  |  Rust (normalizer, hash chain, ECLIPSE kernel, wasm)          |
            |  Go (collectors, replay daemon, independent verifier)         |
            |  C (shared-memory ring buffer, syscall tap)                   |
            |  C++ (offline pcap flow reassembly, interval trees)           |
            |  WebAssembly (in-browser certificate verification)            |
            +---------------------------------------------------------------+
                      |                                    ^
                      v   telemetry                        |  fixtures
            +---------------------------------------------------------------+
  TIER 3    |  HETEROGENEOUS OBSERVED LAB  (these are SUBJECTS, not tools)  |
  observed  |  Java  Kotlin  C#  Scala  Groovy  PHP  Ruby  Perl  Lua        |
            |  Swift  Objective-C  Dart  Solidity  x86-64 Assembly  YARA    |
            |  PowerShell  Bash  XML(SAML)  HCL(segmentation topology)      |
            +---------------------------------------------------------------+
                      |                                    ^
                      v   outputs                          |  oracles
            +---------------------------------------------------------------+
  TIER 4    |  RESEARCH + FORMAL ARTIFACTS  (independence is the point)     |
  oracles   |  Haskell (admissibility / policy differential oracle)         |
            |  F# (formal state machine -> canonical state table)           |
            |  Verilog + VHDL (hardware security FSM, illegal transitions)  |
            |  R  Julia  MATLAB/Octave (statistics, numerics, signals)      |
            +---------------------------------------------------------------+
```

- TIER 1 is the only tier allowed to define product semantics.
- TIER 2 may reimplement a TIER 1 hot path only when a cross-check gate (section 7 of the
  ECLIPSE spec) proves the two agree; the agreement test is mandatory, not optional.
- TIER 3 components are *observed systems*. They emit telemetry into `bundle.jsonl`. They
  never import SPECTRA libraries, never read the rule table, and never know they are being
  watched. If a TIER 3 component starts calling SPECTRA APIs, it has become a tool and has
  lost its justification; move it or delete it.
- TIER 4 components are deliberately written against the *specification*, not against the
  Python or Rust source. Their whole value is that they disagree loudly when the core is
  wrong. A TIER 4 artifact that was ported line-by-line from the core is worthless — delete
  it and rewrite it from the spec.

30.3 Prohibition on duplication for language-count inflation

1. Do NOT reimplement the same CRUD, the same DTO set, the same HTTP client, or the same
   "hello world" service in N languages. Any file whose only content is a translation of
   logic already present elsewhere, with no gate consuming the disagreement, is dead weight.
2. There are exactly three legitimate forms of reimplementation, and each must be declared
   in `languages.toml` with `duplication_kind`:
   - `differential_oracle` — an independent implementation whose output is compared
     byte-for-byte or semantically against the core in CI, and whose disagreement fails the
     build. Examples: Haskell admissibility checker vs Rust license logic; Go certificate
     checker vs Rust kernel; VHDL liveness monitor vs Rust liveness pass.
   - `abstraction_shift` — the same property expressed at a different level of abstraction
     where that level is itself the research claim. Example: the Verilog security-state FSM
     detects illegal transitions in hardware time, cross-checked against the software engine.
   - `native_emitter` — a lab subject emitting telemetry in its ecosystem's real shape.
     Example: C# Windows-style identity events; PHP session logs.
   Anything else is `none` and must not duplicate.
3. Every `differential_oracle` must have a **mutation test**: a CI job injects a known
   deviation into the core and asserts the oracle *fails*. An oracle that cannot fail is not
   an oracle. Store these as `tests/mutation/<oracle>/mut_XX.patch` with expected exit codes.
4. Forbidden: a language added only to produce a README, only to hold a config file it did
   not need to hold, only to print a banner, or only to appear in the GitHub language bar.

30.4 Every component must be exercised

1. Define two rings and assign every non-TIER-1 component to one in `languages.toml`:
   - `DEMO_PATH` — the component executes during the 60-second demo (section 8 of the
     ECLIPSE spec). Example: Rust kernel, Go checker, WASM verifier, TypeScript UI.
   - `DEMO_ARTIFACT` — the component executes during `make demo-build`, producing a fixture,
     figure, table or trace that the 60-second demo displays. Example: x86-64 assembly
     syscall fixtures, R degradation figures, Octave liveness threshold plots.
2. `CI_ONLY` is not an allowed ring. A component that no demo output depends on and that no
   gate consumes must be deleted. Record the deletion in `docs/ADR/` rather than leaving the
   directory in place "for later".
3. Every component must have at least one CI job that (a) builds it, (b) runs its tests,
   (c) produces or consumes a real artifact under `artifacts/`. A CI job that only compiles
   is insufficient — compile-only jobs are listed in `languages.toml` as `weak_exercise` and
   the audit gate fails if more than three exist.
4. `make lang-audit` is a hard CI gate. It parses `languages.toml`, walks the repo, and
   fails on: a declared directory that does not exist; a source file in a language with no
   entry; a component with no CI job; a component with no demo ring; a `differential_oracle`
   with no mutation test; a `weak_exercise` count above three.

30.5 `languages.toml` schema (single source of truth)

```toml
[[component]]
language        = "haskell"           # linguist language name, lowercase
name            = "eclipse-oracle"
dir             = "haskell/eclipse-oracle"
tier            = 4                   # 1..4
reason          = "independent admissibility checker; disagreement must fail the build"
duplication_kind= "differential_oracle"   # none|differential_oracle|abstraction_shift|native_emitter
build           = "cabal build"
test            = "cabal test"
ci_job          = "lang-haskell"
mutation_tests  = ["tests/mutation/haskell-oracle/mut_01.patch",
                   "tests/mutation/haskell-oracle/mut_02.patch"]
demo_ring       = "DEMO_ARTIFACT"
produces        = ["artifacts/oracle/admissibility_report.json"]
consumes        = ["artifacts/eclipse/liveness.json", "rules.toml"]
weak_exercise   = false
loc_budget      = 1500                # audit warns above; padding is a smell
```

30.6 Audit transcript (this exact shape must be reproducible)

```
$ make lang-audit
spectra-lang-audit 0.1.0
  languages declared      : 43
  components declared     : 51
  source files classified : 4,812 / 4,812
  components with CI job  : 51 / 51
  demo rings              : DEMO_PATH 14, DEMO_ARTIFACT 37, CI_ONLY 0
  differential oracles    : 6  (mutation tests: 17, all failing as required)
  weak_exercise           : 2 / 3 allowed
  unjustified duplication : 0
  linguist overrides      : 9 (all vendored/generated/docs, verified)
OK
```

30.7 Negative requirements

1. Do NOT write a language's component as a thin shell wrapper around a Python or Rust
   binary and call it that language's contribution.
2. Do NOT claim a language "is used for X" in the README if the only X is a build file that
   a different language's tooling generated.
3. Do NOT let TIER 3 lab subjects import the rule table, the control catalog, or the
   certificate schema. They must be ignorant of SPECTRA.
4. Do NOT introduce a language that requires a paid toolchain, a network license server, a
   cloud account, or a non-redistributable SDK. MATLAB is permitted only because an Octave
   fallback runs the same scripts in CI; if a script does not run under Octave, it does not
   ship.
5. Do NOT treat the language count as a metric. Report it as an inventory, never as an
   achievement. The README states the count once, in a table, with the reason column visible.

============================================================
31. LANGUAGE RESPONSIBILITY MATRIX
============================================================

31.1 Directory map

```
spectra/
├── spectra/                    Python: core reconstruction, ER, degradation harness, CLI
├── services/api/               Python: FastAPI, Pydantic v2, SQLAlchemy
├── web/                        TypeScript/React/SCSS/CSS/HTML + JS standalone verifier
├── rust/                       Rust workspace: normalizer, chain, eclipse-kernel, wasm
├── go/                         Go: collectors, replay daemon, `spectra verify`
├── native/                     C (ringbuf, ptrace tap) + C++ (pcap flow) + CMake
├── fixtures/asm/               x86-64 assembly syscall-trace generators
├── java/                       Java lab service + JVM session agent (Maven/XML)
├── mobile/                     Kotlin (Android), Swift + Objective-C (iOS), Dart (Flutter)
├── dotnet/                     C# identity emitter, F# formal state machine
├── scala/                      Scala streaming baseline (sbt)
├── gradle/                     Groovy: build logic + scenario DSL
├── haskell/                    Haskell admissibility / policy oracle
├── lab/                        PHP portal, Ruby automation service, Lua transformers
├── tools/perl/                 Perl legacy log translator
├── analysis/{r,julia,matlab}/  R, Julia, MATLAB+Octave
├── chain/                      Solidity authorization fixture (Foundry/anvil)
├── hw/{verilog,vhdl}/          Icarus+cocotb, GHDL
├── rules/yara/                 YARA content rules over lab artifacts
├── db/                         SQL DDL, migrations, recursive CTE views
├── scripts/                    Bash; scripts/win/ PowerShell
├── infra/                      Dockerfile, docker-compose YAML, HCL lab topology
└── Makefile, .gitattributes, languages.toml
```

31.2 Python — `spectra/`, `services/api/`, `tools/py/`

- Implements: entity resolution, state reconstruction, temporal/causal graph construction,
  the degradation + tampering harness (100%→30% matrix), scenario orchestration, the
  FastAPI surface, Pydantic v2 contracts, SQLAlchemy models, the `spectra` CLI.
- Why: richest ecosystem for data plumbing and schema-validated APIs; the concern is
  correctness-per-engineer-hour, not throughput. Hot loops are delegated to Rust.
- Build: `uv` with a locked `uv.lock`, Python 3.12 pinned; `hatchling` wheel.
- Test: `pytest` + `hypothesis` property tests over ER and state transitions; `mypy --strict`;
  `ruff`. Golden-file tests against `artifacts/golden/`.
- CI: job `lang-python` — lint, typecheck, unit, property, golden, coverage floor 85% on
  `spectra/core/`.
- Demo: DEMO_PATH. Serves the API the UI calls; runs the scenario and degradation sweeps.

31.3 TypeScript — `web/src/`

- Implements: React 18 + Vite + Tailwind UI; control lattice toggles with level sliders; D3
  force/DAG rendering of the AND/OR hypergraph; counterexample derivation tree viewer;
  certificate header with hash, mode and corridor count; blindness-premium panel; the
  100%→30% stability strip; GHOST styling for silent (licensed) instances.
- Why: a large stateful client with a non-trivial domain model; types are the defence against
  rendering an OPTIMISTIC verdict as ROBUST.
- Build: `pnpm`, `vite build`, `tsc --noEmit` with `strict: true`, `exactOptionalPropertyTypes`.
- Test: `vitest` unit tests; `@testing-library/react`; Playwright end-to-end that toggles
  `session_binding`, presses PROVE, and asserts the verdict badge and terminal output.
- CI: job `lang-typescript` — typecheck, unit, Playwright against a compose-brought-up stack.
- Demo: DEMO_PATH. It is the demo surface.

31.4 JavaScript — `web/standalone/`, `tools/js/`

- Implements: (a) `web/standalone/verify.html` + `verify.mjs` — a zero-build, zero-dependency
  ES-module page that loads `eclipse_verifier.wasm` and verifies a certificate from `file://`
  with no server, no bundler and no network; (b) `tools/js/canonicalize.mjs` — a Node
  implementation of RFC 8785 JSON canonicalization used in CI to confirm the Rust and Python
  canonicalizers produce identical bytes before hashing.
- Why: the standalone verifier must survive the absence of the entire toolchain — a reviewer
  with a browser and a file must be able to check a certificate. TypeScript would need a build.
- Build: none. The files are shipped as-is; `node --check` in CI.
- Test: `node --test tools/js/canonicalize.test.mjs`; Playwright opens the `file://` page and
  asserts `OK` for a good certificate and a specific failure code for each of six corrupted
  certificates.
- CI: job `lang-javascript`. Also a `differential_oracle` mutation test: perturb the Rust
  canonicalizer, assert `canonicalize.mjs` disagrees and the job fails.
- Demo: DEMO_PATH. Shown last: drag the certificate onto a blank page, it verifies offline.

31.5 Rust — `rust/` workspace

- Crates: `spectra-normalize` (schema normalization, Lua transformer host via `mlua`),
  `spectra-chain` (BLAKE3 sequence chains, gap/suppression detection), `eclipse-kernel`
  (grounding, semi-naive evaluation with provenance, Dowling–Gallier fixpoint, Reiter/MARCO
  hitting-set loop over u64 masks, knapsack frontier), `eclipse-rulegen` (compiles
  `rules.toml` guard AST into both the kernel matcher and the concrete simulator),
  `eclipse-verifier-wasm` (wasm32-unknown-unknown build of the checking half).
- Why: the kernel is the hot path and the trust anchor. Requires exact control over bit masks,
  arena allocation, and determinism; must be panic-free on adversarial input; must compile to
  WASM for in-browser verification.
- Build: `cargo build --workspace --locked`, pinned toolchain in `rust-toolchain.toml`;
  `wasm-pack build` for the verifier crate.
- Test: `cargo test`, `proptest` for rule-ordering determinism (byte-identical fixpoint under
  randomized rule orderings) and control-lattice antitonicity; `cargo miri` on the mask code;
  `cargo fuzz` targets for `bundle.jsonl` and `cert.json` parsing; `#![forbid(unsafe_code)]`
  outside a single audited `unsafe` module with a written justification.
- CI: job `lang-rust` — fmt, clippy `-D warnings`, test, miri, 60s fuzz smoke, wasm build,
  plus the 256-configuration simulator-vs-kernel agreement gate.
- Demo: DEMO_PATH. PROVE runs the kernel; the WASM crate verifies in the browser.

31.6 Go — `go/cmd/spectra-verify/`, `go/cmd/spectra-collect/`, `go/cmd/spectra-replayd/`

- Implements: the independent certificate checker (`spectra verify cert.json`) that shares no
  code with the Rust solver and re-grounds from hashed inputs, checking axioms, closure, goal
  exclusion, license validity, redundancy witnesses and Ψ minimality in one linear pass; the
  telemetry collectors that tail lab services and ship canonical NDJSON; the replay daemon
  that re-runs a scenario under a different control configuration deterministically.
- Why: independence is the requirement — a second language and a second author-mindset for the
  checker. Also: static binaries, trivial cross-compile, first-class concurrency for collectors.
- Build: `go build ./...`, `CGO_ENABLED=0`, version pinned in `go.mod`.
- Test: `go test ./... -race`; table-driven checker tests over a corpus of valid and
  deliberately invalid certificates (one per failure mode a–f); `go vet`; `staticcheck`.
- CI: job `lang-go`. Mutation gate: patch the Rust kernel to emit a cut of size |S|-1 that
  does not satisfy Ψ; the Go checker must reject and CI must fail if it accepts.
- Demo: DEMO_PATH. The terminal pane in the demo is literally this binary.

31.7 C — `native/libspectra_ringbuf/`, `native/tap_ptrace/`

- Implements: a single-producer/single-consumer lock-free shared-memory ring buffer used by
  the syscall tap to hand records to the Go collector without allocation, with a stable C ABI;
  and a `ptrace`-based syscall tap for lab processes that records ordered, timestamped syscall
  events with no kernel modules and no eBPF requirement.
- Why: shared-memory layout, cache-line alignment and a stable ABI across Rust, Go and Python
  consumers. This is exactly what C is for.
- Build: CMake, C11, `-Wall -Wextra -Werror`, `-fsanitize=address,undefined` in debug.
- Test: CTest unit tests; a torture test with a producer and consumer thread for 10^7 records
  asserting zero loss and strict ordering; ASan/UBSan clean; `cppcheck`.
- CI: job `lang-c` — build, sanitize, torture test, ABI header diff gate against
  `native/abi/libspectra_ringbuf.h.golden`.
- Demo: DEMO_ARTIFACT. Produces the syscall stream in the recorded scenario bundle.

31.8 C++ — `native/pcap-flow/`

- Implements: offline pcap flow reassembly for the lab's captured east-west traffic (no live
  capture, no external targets), producing session-level network facts; plus an interval tree
  and an interval-merge engine used to compute per-source liveness windows over millions of
  records before they reach the kernel.
- Why: needs STL containers, templates and RAII over a performance-sensitive data structure;
  and `libpcap` bindings are natural here.
- Build: CMake, C++20, `-Werror`, static-linked against a pinned libpcap.
- Test: Catch2 unit tests; a differential test against a naive O(n²) interval implementation
  on 10k randomized interval sets; replay of three golden pcaps to golden flow tables.
- CI: job `lang-cpp` — build, tests, ASan/UBSan, golden pcap replay.
- Demo: DEMO_ARTIFACT. Its liveness intervals feed `liveness.json` shown in the blindness beat.

31.9 x86-64 Assembly — `fixtures/asm/`

- Implements: hand-written, deterministic syscall-sequence fixtures (`open`/`read`/`mmap`/
  `execve`/`setuid` patterns) with no libc, no ASLR-dependent behavior, no `rdtsc`, and a
  fixed instruction sequence so the emitted trace is byte-identical on every run. Used as
  ground truth for obligation axioms such as `fd.read ⇒ fd.open`.
- Why: byte-identical traces require control over the exact instruction and syscall sequence.
  Any higher-level language inserts runtime noise.
- Build: `nasm -f elf64` + `ld` (no libc), driven by the Makefile; static, PIE disabled.
- Test: run under the C `ptrace` tap and assert the produced trace equals
  `fixtures/asm/golden/<name>.trace` byte-for-byte across 50 repeated runs; assert each binary
  is reproducible (`sha256` of the ELF pinned).
- CI: job `lang-asm` — assemble, link, run under the tap, compare goldens, verify determinism.
- Demo: DEMO_ARTIFACT. Supplies the obligation-violation evidence that forces a silent
  instance in the demo scenario.

31.10 Java — `java/lab-service/`, `java/session-agent/`

- Implements: the lab's enterprise service (Spring-free, plain Servlet + embedded Jetty) that
  issues sessions, checks RBAC and writes structured audit logs; and a `java.lang.instrument`
  JVM agent that records session-token lifecycle events from bytecode, without the service
  knowing.
- Why: the most common source of enterprise audit telemetry; a JVM agent is the authentic way
  to observe token lifecycle, and reproducing that shape in another language would be a lie.
- Build: Maven (`pom.xml`, XML), JDK 21 pinned, reproducible-build plugin.
- Test: JUnit 5; a test that asserts the agent observes exactly the tokens the service issued;
  schema conformance of emitted audit records against `schemas/audit.schema.json`.
- CI: job `lang-java` — `mvn -B verify`, JUnit XML published, schema conformance gate.
- Demo: DEMO_PATH. It is the service the attacker scenario pivots through.

31.11 Kotlin — `mobile/android-session-fixture/`

- Implements: an Android session-telemetry fixture generator — device-trust attestation
  results, re-auth prompts, biometric-gate outcomes, background token refresh — emitted in the
  shape a real mobile SDK produces, seeded and deterministic.
- Why: mobile session semantics (device binding, refresh-token rotation) are a distinct
  security dimension; Kotlin is the native language of that telemetry shape.
- Build: Gradle (Kotlin JVM target only — no Android SDK download in CI; the Android-specific
  types are modelled in a pure-JVM module so CI stays offline).
- Test: `kotest` property tests that generated sequences satisfy the obligation axioms;
  golden-file test of one seeded run.
- CI: job `lang-kotlin` — `./gradlew :android-session-fixture:test`, golden compare.
- Demo: DEMO_ARTIFACT. Its events make `device_trust` a meaningful control in the lattice.

31.12 C# — `dotnet/win-identity-sim/`

- Implements: a Windows-shaped identity event emitter — logon/logoff, privilege assignment,
  service-account authentication, Kerberos-shaped ticket events — as *synthetic records in the
  documented field layout*, never captured from a real host and never containing real SIDs.
- Why: Windows identity telemetry has a specific record shape; the .NET type system and
  ecosystem make an honest, well-typed emitter straightforward.
- Build: `dotnet build -c Release`, .NET 8 pinned via `global.json`.
- Test: xUnit; schema conformance against `schemas/winident.schema.json`; a test asserting no
  field contains a value from the real host environment (no `Environment.MachineName`, no real
  SIDs) — this test is a hard requirement, not a nicety.
- CI: job `lang-dotnet` (shared with F#) — build, test, conformance, environment-leak gate.
- Demo: DEMO_ARTIFACT. Supplies the privilege-escalation leg of the scenario.

31.13 F# — `dotnet/state-machine-model/`

- Implements: the formal model of the SPECTRA security state machine — identity, session,
  credential, privilege, process, network, API, service, resource and trust dimensions — as
  total functions over discriminated unions, with exhaustive transition enumeration. Emits the
  canonical `artifacts/state_table.json` (states, legal transitions, guards, dimension tags)
  that Python's engine and the Rust kernel both load rather than hard-coding.
- Why: discriminated unions plus exhaustive matching make illegal states unrepresentable and
  make "did we enumerate every transition?" a compiler question rather than a review question.
- Build: `dotnet build`; the generator runs as `dotnet run --project state-machine-model`.
- Test: FsCheck property tests (determinism, totality, no unreachable state, no transition
  without a guard); a regeneration gate — regenerate `state_table.json` in CI and fail if it
  differs from the committed file.
- CI: job `lang-dotnet`. Downstream gate: Python's engine test suite loads the regenerated
  table, so an F# change that breaks the core fails the Python job too.
- Demo: DEMO_ARTIFACT. The state table is what the UI's dimension legend is generated from.

31.14 Scala — `scala/stream-baseline/`

- Implements: a streaming, windowed reconstruction baseline over FS2 — incremental state
  updates with bounded memory and late/out-of-order event handling — used to quantify what the
  batch reconstruction gains, and to measure degradation under reordering and delay.
- Why: the streaming/windowing/backpressure model is what this language and ecosystem are
  built around; reimplementing it in Python would measure Python, not the approach.
- Build: `sbt` with a pinned Scala 3 version and `sbt-assembly` for a fat jar.
- Test: `munit` + `scalacheck`; a test asserting the streaming baseline and the batch engine
  agree on state at end-of-stream when completeness is 100% and no reordering is injected.
- CI: job `lang-scala` — `sbt test`, plus the batch-agreement gate at 100% completeness.
- Demo: DEMO_ARTIFACT. Produces the second line on the degradation stability strip.

31.15 Groovy — `gradle/` (build logic) and `scenario-dsl/`

- Implements: Gradle build logic for the JVM components, and a scenario authoring DSL:
  `scenario "cred-theft-pivot" { actor "svc-ci"; at "+0m" { authenticate from: "10.0.3.7" } ... }`
  which compiles to a seeded scenario specification consumed by the generator.
- Why: a readable, statically-hosted DSL with closures is Groovy's actual strength, and the
  scenario files must be reviewable by a human as prose-like text while remaining executable.
- Build: Gradle, Groovy 4, compiled at build time.
- Test: Spock specifications asserting each DSL script compiles to the expected scenario JSON;
  a golden-file test per shipped scenario.
- CI: job `lang-groovy` — `./gradlew :scenario-dsl:test`, golden compare of all scenario JSON.
- Demo: DEMO_ARTIFACT. The demo scenario is authored in this DSL and shown on screen for 3s.

31.16 Haskell — `haskell/eclipse-oracle/`

- Implements: (a) a pure control/policy evaluator — given a control configuration and a rule
  instance, decide whether the instance is blocked — written from the specification, used as a
  differential oracle against the Python policy engine and the Rust guard compiler; (b) a
  reference admissibility checker for the license logic: given `liveness.json` and a silent
  instance, decide whether that instance is licensed, exactly as section 4C specifies.
- Why: the license logic is the subtlest part of ECLIPSE. An independently written,
  side-effect-free, totally-specified implementation with algebraic data types is the cheapest
  way to catch a wrong-by-one-interval bug. Independence is the deliverable.
- Build: `cabal build` with a Stackage-pinned `cabal.project.freeze`, GHC pinned.
- Test: `hspec` + `QuickCheck`; the oracle runs against every fixture in `fixtures/scenarios/`
  and every cell of the degradation matrix, comparing verdicts with the Rust kernel.
- CI: job `lang-haskell`. Mutation gate: three patches that widen a blind interval by one
  nanosecond, flip a `Blind`/`Suppressed` basis, and admit a silent instance whose source was
  live — each must be caught.
- Demo: DEMO_ARTIFACT. Produces `artifacts/oracle/admissibility_report.json`, whose "0
  disagreements over N licenses" line appears in the demo's stability strip footer.

31.17 PHP — `lab/legacy-portal/`

- Implements: the lab's legacy web portal — PHP sessions, a login form, a file-download
  endpoint, and classic `access_log` + `error_log` + `session` file telemetry. It is a subject,
  not a tool. It is the entry point of the demo scenario.
- Why: legacy PHP applications are a genuine and common source of session telemetry with its
  own quirks (session-file lifetime, `PHPSESSID` regeneration, log line format). Faking that
  shape from Python would be dishonest.
- Build: `php:8.3-apache` image, no Composer dependencies beyond a pinned lockfile.
- Test: PHPUnit for the handful of handlers; a black-box test that drives the portal with curl
  and asserts the emitted log lines match `fixtures/php/golden_access.log` modulo timestamps.
- CI: job `lang-php` — lint (`php -l`), PHPUnit, black-box log-shape gate.
- Demo: DEMO_PATH. Runs in compose; the first evidence event in the counterexample tree is one
  of its access-log lines.

31.18 Ruby — `lab/automation-runner/`

- Implements: the lab's internal automation/CI-like service running under a service account:
  schedules jobs, fetches artifacts, uses a long-lived token. Emits job-execution and
  service-account-authentication telemetry. This is the pivot the `service_account_isolation`
  control acts on.
- Why: a Sinatra-style automation service is the authentic shape for this class of internal
  tooling and for the service-account telemetry it produces.
- Build: Bundler with a committed `Gemfile.lock`, `ruby:3.3` image.
- Test: RSpec; a test asserting the service account never authenticates outside its declared
  window unless the scenario injects the compromise.
- CI: job `lang-ruby` — `bundle exec rspec`, `rubocop`.
- Demo: DEMO_PATH. Runs in compose; the pivot step in the attack chain.

31.19 Perl — `tools/perl/logxlate/`

- Implements: translation of legacy log formats into canonical NDJSON: syslog RFC 3164 and
  5424, Apache combined, CEF, LEEF, and two deliberately malformed dialects. Handles multiline
  records, embedded delimiters and mixed encodings.
- Why: this is line-oriented regex-heavy text surgery over irregular legacy formats — the task
  Perl is unambiguously best at, and the one place where a regex-first language is the right
  engineering answer rather than a stunt.
- Build: none (interpreted); `cpanfile` with pinned core-only dependencies.
- Test: `prove -l t/` — one test file per dialect; a round-trip corpus of 2,000 real-shaped
  lines with expected NDJSON; fuzz test asserting no input causes a non-zero exit or a
  malformed output record.
- CI: job `lang-perl` — `perlcritic --gentle`, `prove`, corpus gate.
- Demo: DEMO_ARTIFACT. The PHP portal's `access_log` reaches the bundle through this tool.

31.20 Lua — `lab/transformers/` (hosted by `rust/spectra-normalize`)

- Implements: user-supplied event transformers executed in a sandbox inside the Rust
  normalizer — field renames, enrichment from a static map, redaction, and timestamp
  normalization — with no I/O, no `os`, no `io`, no `require`, a bounded instruction budget
  and a bounded memory budget.
- Why: the platform must accept user logic without recompiling or granting a shell, and `mlua`
  gives a hard, auditable sandbox boundary. Embedding Python here would be a security hole.
- Build: none; loaded at runtime by the normalizer; `luacheck` in CI.
- Test: Rust-side tests asserting each shipped transformer is deterministic across 1,000 runs;
  escape tests asserting `os.execute`, `io.open`, `require`, infinite loops and 1GB allocations
  all fail closed with a specific error; `busted` unit tests for transformer logic.
- CI: job `lang-lua` — `luacheck`, `busted`, plus the Rust sandbox-escape test suite.
- Demo: DEMO_PATH. One transformer normalizes the PHP portal's timestamps live.

31.21 Swift — `mobile/ios-session-fixture/`

- Implements: an iOS session-telemetry fixture generator — app foreground/background
  transitions, session resumption, token refresh, jailbreak-check outcome, device-attestation
  result — deterministic and seeded, emitted as canonical NDJSON.
- Why: the mobile session lifecycle is platform-specific and Swift is its native expression;
  producing it elsewhere would misrepresent the telemetry's structure.
- Build: Swift Package Manager, `swift build -c release` on Linux (Foundation-only, no UIKit,
  so CI needs no macOS runner).
- Test: `swift test` with XCTest; obligation-axiom conformance (`session.used ⇒ session.issued`);
  golden run under a fixed seed.
- CI: job `lang-swift` on the `swift:5.10` container — build, test, golden compare.
- Demo: DEMO_ARTIFACT. Supplies the mobile leg that makes `session_binding` levels meaningful.

31.22 Objective-C — `mobile/ios-keychain-shim/`

- Implements: a credential-lifecycle shim emitting keychain-shaped events — item added,
  accessed, access-control policy evaluated, item deleted, protection class changed — linked
  into the Swift fixture through its C interface.
- Why: keychain APIs are Objective-C; the credential-lifecycle event shape comes from that API
  surface, and expressing it through the actual ABI keeps the fixture honest. It also exercises
  the Objective-C/Swift interop boundary that a real mobile telemetry SDK crosses.
- Build: `clang -fobjc-arc` against GNUstep libobjc in the CI container; linked by SwiftPM via
  a `systemLibrary` target.
- Test: a small XCTest suite driven from Swift asserting each emitted credential event carries
  a matching lifecycle pair; ASan clean.
- CI: job `lang-objc` (shares the Swift container) — build, interop test, ASan.
- Demo: DEMO_ARTIFACT. Produces the credential events `credential_rotation` acts on — the
  control that the blindness beat removes.

31.23 Dart — `mobile/analyst-console/`

- Implements: a read-only Flutter console (desktop + web builds) that opens a certificate file,
  displays the cut, the corridors, the licenses used and the flags, and calls the WASM verifier
  on web / the Go binary on desktop. It never computes a verdict itself.
- Why: demonstrates the certificate is portable to a client with no SPECTRA backend at all; a
  single Dart codebase covers desktop and web without duplicating the TypeScript UI's
  responsibilities (it deliberately does not render the hypergraph).
- Build: `flutter build web` and `flutter build linux`, Flutter version pinned.
- Test: `flutter test` widget tests; a test that a certificate carrying any of
  `grounding_capped`, `subset_minimal_only`, `greedy_cover` can never render the ROBUST badge.
- CI: job `lang-dart` — `dart analyze`, `flutter test`, web build artifact uploaded.
- Demo: DEMO_ARTIFACT. Screenshot shown in the README's portability section.

31.24 R — `analysis/r/`

- Implements: statistics over the degradation matrix — per-cell reconstruction quality with
  bootstrap confidence intervals over seeds, monotonicity tests across completeness levels,
  and the `ggplot2` figures (`degradation_heatmap.png`, `blindness_premium.png`,
  `corridor_count_vs_completeness.png`) used in the README and the paper.
- Why: bootstrap CIs, tidy data reshaping and publication-grade statistical graphics are R's
  core competence, and the figures must be regenerable from raw results by one command.
- Build: none; `renv.lock` pins every package; runs in the `rocker/r-ver` pinned image.
- Test: `testthat` unit tests on the summarizing functions; a gate asserting every number in
  `docs/results.md` is present in `artifacts/analysis/summary.csv` produced by this code — no
  number may exist in the docs that this pipeline did not compute.
- CI: job `lang-r` — `Rscript analysis/r/run_all.R`, testthat, figure regeneration diff.
- Demo: DEMO_ARTIFACT. The stability strip's underlying numbers and figures.

31.25 MATLAB / GNU Octave — `analysis/matlab/`

- Implements: signal analysis of telemetry timing — inter-arrival distributions per source,
  the q99 threshold used by the liveness pass, periodicity/beaconing detection via
  autocorrelation and Welch PSD, and a sensitivity sweep of how the q99 choice moves blind
  windows and therefore the blindness premium.
- Why: the liveness threshold is a signal-processing decision and must be justified with
  spectral analysis, not a guessed constant. These scripts read as the numerical method they are.
- Build: none. Every script is written to the Octave-compatible subset — no toolbox functions
  outside `signal` (Octave `signal` package pinned), no `parfor`, no OOP handles.
- Test: `test/run_octave_tests.m` asserts each function's output against golden `.mat`/CSV
  references; a compatibility gate runs the full script set under Octave and fails on any
  MATLAB-only construct.
- CI: job `lang-matlab` runs under `octave:9` — full script set, golden compare. MATLAB itself
  is never required by CI and must never be.
- Demo: DEMO_ARTIFACT. Produces `artifacts/analysis/q99_thresholds.json`, which the liveness
  pass consumes, and the PSD figure shown in the blindness beat.

31.26 Julia — `analysis/julia/`

- Implements: exact combinatorial cross-checks of the kernel's optimization results — a
  brute-force minimum-cardinality hitting set over Ψ for `|A| ≤ 20` fixtures, an independent
  multiple-choice knapsack solver for the Pareto frontier, and a sensitivity sweep over
  declared costs producing the frontier stability table.
- Why: high-performance numeric and combinatorial code with readable mathematical notation, and
  independence from the Rust implementation makes it a `differential_oracle`, not a rewrite.
- Build: `Project.toml` + `Manifest.toml` pinned; `julia --project`.
- Test: `Pkg.test()`; every small fixture's brute-force optimum must equal the kernel's
  `|S_opt|` and `|S_rob|`; every Pareto point must match the kernel's frontier exactly.
- CI: job `lang-julia`. Mutation gate: perturb the kernel's popcount ordering to return a
  non-minimal cut; Julia must disagree and fail the build.
- Demo: DEMO_ARTIFACT. Produces the "brute-force agreement: 40/40 fixtures" line in the results.

31.27 Solidity — `chain/authz-fixture/`

- Implements: an on-chain authorization fixture — a role registry contract emitting
  `RoleGranted`, `RoleRevoked`, `AuthorizationUsed` events, deployed to a local `anvil` node in
  the lab. A Go collector reads the event log as a telemetry source with immutable ordering.
- Why: it provides a telemetry source with properties no other source has — an append-only,
  totally ordered, cryptographically sequenced log that cannot be suppressed. That makes it the
  control case in the tampering study: the one source where SUPPRESSED is provably impossible.
- Build: Foundry (`forge build`), Solidity version pinned in `foundry.toml`; no mainnet, no
  testnet, no RPC provider, no keys with value.
- Test: `forge test` including fuzz tests; an invariant test that every `AuthorizationUsed`
  event has a preceding `RoleGranted` for that role — the on-chain form of an obligation axiom.
- CI: job `lang-solidity` — `forge build`, `forge test`, `slither` static analysis, plus a
  deploy-to-anvil integration test that the Go collector ingests the events.
- Demo: DEMO_ARTIFACT. Its immutability is the counterpoint in the tampering section: the
  demo shows one blind window on `iam_audit` and zero possible blind windows on `chain_authz`.

31.28 Verilog — `hw/verilog/sec_state_fsm/`

- Implements: the security state machine as synthesizable RTL — a Moore FSM over the
  identity/session/privilege dimensions with an `illegal_transition` output asserted on any
  transition not present in the F#-generated state table (the table is converted to a Verilog
  `casez` by a generator, so hardware and software share the specification, not the code).
- Why (`abstraction_shift`): expressing the state machine as hardware forces every transition to
  be total and every illegal transition to be explicitly detected in one clock; it is a
  genuinely different check from the software engine's, and disagreement is informative.
- Build: `iverilog -g2012`; also `yosys -p synth` as an elaboration sanity check.
- Test: `cocotb` testbenches driven from Python, replaying the transition sequences of every
  fixture scenario and asserting `illegal_transition` matches the Python engine's illegal-
  transition set exactly, cycle for cycle.
- CI: job `lang-verilog` — iverilog build, cocotb suite, yosys elaboration, coverage of all
  state-table transitions (100% required, since the table is finite and generated).
- Demo: DEMO_ARTIFACT. The cocotb log line "hw/sw illegal-transition agreement: 1,204/1,204" is
  shown in the gates panel.

31.29 VHDL — `hw/vhdl/liveness_monitor/`

- Implements: a hardware liveness monitor — a streaming block that consumes timestamped source
  heartbeats and asserts `blind` when inter-arrival exceeds the configured q99 threshold, with
  a separate `chain_break` output driven by a sequence-number comparator.
- Why (`differential_oracle`): the liveness pass is what licenses silent instances, and an
  incorrect blind window silently weakens every ROBUST verdict. A synchronous, bit-exact
  reimplementation in a different HDL, written from section 4A rather than from the Rust source,
  is a strong check on interval arithmetic and boundary conditions.
- Build: `ghdl -a` / `ghdl -e` with `--std=08`, `-Werror`.
- Test: `ghdl -r` with VUnit; stimulus generated from real fixture timestamps; assertion that
  the emitted blind intervals equal the Rust `liveness.json` intervals for all sources across
  all fixtures, with inclusive/exclusive boundary cases explicitly enumerated.
- CI: job `lang-vhdl` — analyze, elaborate, VUnit run, interval-equality gate. Mutation gate:
  shift one Rust interval endpoint by one tick; VHDL must disagree.
- Demo: DEMO_ARTIFACT. Its agreement line appears beside the Verilog line in the gates panel.

31.30 WebAssembly — `rust/eclipse-verifier-wasm/` → `web/public/eclipse_verifier.wasm`

- Implements: the checking half of ECLIPSE compiled to `wasm32-unknown-unknown` — closure
  check, goal exclusion, license validation, witness re-derivation and Ψ minimality — running
  entirely in the browser with no network call, so a reviewer can verify a certificate without
  trusting the server that produced it.
- Why: this is the only way to make "the certificate is independently checkable" true for a
  person who has only a browser. It is a compilation target of existing Rust, not a rewrite.
- Build: `wasm-pack build --target web --release`; `wasm-opt -Oz`; size budget 1.5 MB enforced.
- Test: `wasm-bindgen-test` in headless Chromium; a gate asserting the WASM verdict equals the
  native Rust verdict and the Go checker verdict on all fixtures and all corrupted certificates.
- CI: job `lang-wasm` — build, size gate, headless tests, three-way verdict agreement gate.
- Demo: DEMO_PATH. Powers `web/standalone/verify.html` in the final demo beat.

31.31 YARA — `rules/yara/`

- Implements: content signatures over artifacts staged inside the lab by the synthetic scenario
  (a packed helper binary, a credential dump file, a modified config). Matches become evidence
  events with stable `EventId`s and feed rules whose bodies require file-content facts.
- Why: a declarative content-matching language is the correct tool for content facts, and
  writing the same matching in Python would be slower and less auditable. Rules are data a
  reviewer can read.
- Constraint: the staged artifacts are synthetic files generated by the scenario generator. No
  real malware, no real samples, no hashes of real samples.
- Build: none; compiled by `yara-x`/`libyara` pinned in the scanner image.
- Test: for each rule, one must-match fixture and two must-not-match fixtures; a false-positive
  gate scanning 500 benign generated files with zero matches allowed.
- CI: job `lang-yara` — `yara -w -s` compile check, match/non-match corpus, FP gate.
- Demo: DEMO_ARTIFACT. A YARA match is one of the evidence leaves in the counterexample tree.

31.32 SQL — `db/ddl/`, `db/migrations/`, `db/views/`

- Implements: the PostgreSQL schema (events, entities, resolutions, states, transitions,
  scenarios, runs, certificates), the Alembic-driven migration set, partitioning of the events
  table by run, and analytical views — including recursive CTEs for causal-path queries and a
  materialized view for per-source inter-arrival statistics.
- Why: set-based reconstruction queries over millions of rows belong in the database; pulling
  them into Python would be slower and would hide the query plan.
- Build: migrations applied by Alembic; DDL is the source of truth for the ORM, not vice versa.
- Test: `pgTAP` tests for constraints and views; a golden query-plan test asserting the causal
  path query stays index-backed (no sequential scan on `events`) at 5M rows; a migration
  round-trip test (up/down/up).
- CI: job `lang-sql` — spin Postgres, migrate, pgTAP, plan gate, `sqlfluff lint`.
- Demo: DEMO_PATH. Backs every API call the UI makes.

31.33 Bash — `scripts/`

- Implements: lab bring-up and teardown, the demo driver (`scripts/demo.sh`), artifact
  collection, the reproducibility harness that runs a scenario twice and diffs the hashes, and
  the CI entrypoints.
- Why: orchestration of processes, containers and files across the toolchain.
- Build: none; `shellcheck` and `shfmt` enforced; `set -Eeuo pipefail` in every script.
- Test: `bats` tests for the non-trivial helpers (artifact collection, hash diffing); a test
  that `scripts/demo.sh` run twice produces byte-identical `cert.json`.
- CI: job `lang-bash` — shellcheck `-S style`, shfmt diff, bats.
- Demo: DEMO_PATH. `scripts/demo.sh` is what the presenter runs.

31.34 PowerShell — `scripts/win/`

- Implements: the Windows-side developer bootstrap (toolchain checks, compose bring-up) and the
  collector wrapper that forwards the C# identity emitter's output into the ingest pipeline on
  Windows hosts, plus an environment-parity check that fails loudly when a Windows dev box
  diverges from the pinned toolchain versions.
- Why: SPECTRA must be developable on Windows, and the Windows-side telemetry path needs a
  native wrapper. Bash under WSL is not the same environment and would hide real breakage.
- Build: none; `PSScriptAnalyzer` enforced; `#Requires -Version 7`.
- Test: Pester tests for the parity check and the wrapper's record handling, run on a
  `windows-latest` GitHub Actions runner.
- CI: job `lang-powershell` on `windows-latest` — PSScriptAnalyzer, Pester.
- Demo: DEMO_ARTIFACT. The Windows identity telemetry in the bundle arrives through this path.

31.35 HTML — `web/index.html`, `web/standalone/verify.html`, `docs/templates/`

- Implements: the app shell with correct landmark structure; the dependency-free standalone
  verifier page; and the printable certificate report template used to render a certificate to
  PDF for the paper appendix.
- Why: the standalone page and the print template are hand-authored documents, not framework
  output; their whole point is that they work without a build step.
- Build: none for standalone/templates; the app shell is processed by Vite.
- Test: `html-validate` on every file; axe-core accessibility checks in Playwright with zero
  serious violations allowed; a print-rendering test producing `artifacts/report/cert.pdf`.
- CI: job `lang-html` — validate, axe, PDF render.
- Demo: DEMO_PATH.

31.36 CSS — `web/src/styles/tokens.css`, `web/src/styles/print.css`

- Implements: the design-token layer (color, spacing, type scale) as custom properties with a
  light/dark pair, and the print stylesheet that makes the certificate report legible on paper
  (expanded hashes, no truncation, page-break control around derivation trees).
- Why: tokens and print rules are authored as plain CSS deliberately so they are consumable by
  the standalone page and the print template, which have no build step and no Tailwind.
- Build: none (copied verbatim); referenced by both the Vite app and the standalone page.
- Test: `stylelint`; a Playwright visual test of the printed certificate at A4; a contrast test
  asserting every token pair meets WCAG AA.
- CI: job `lang-css` — stylelint, contrast gate, print snapshot.
- Demo: DEMO_PATH.

31.37 SCSS — `web/src/styles/components/`

- Implements: component styles that Tailwind utilities do not express well — the D3 hypergraph
  layer (node/edge states: observed, GHOST/silent, blocked, in-cut, on-corridor), the derivation
  tree connectors, and the degradation strip — using nesting, mixins and `@each` loops over the
  state list so a new fact state cannot be added without a corresponding style.
- Why: the graph styling is combinatorial over states × modes; generating it from a loop is
  maintainable, and utility classes are not.
- Build: `sass` via Vite, `--load-path=web/src/styles`.
- Test: `stylelint --syntax scss`; a compile-and-diff gate on the generated CSS; a test
  asserting every value of the fact-state enum has a generated class.
- CI: job `lang-scss` — compile, lint, enum-coverage gate.
- Demo: DEMO_PATH. The GHOST rendering of silent instances is defined here.

31.38 JSON — `schemas/`, `artifacts/`, `fixtures/`

- Implements: JSON Schema 2020-12 definitions for every contract (`event`, `bundle_manifest`,
  `liveness`, `cert`, `state_table`, `scenario`), all emitted artifacts, and all golden fixtures.
- Why: the cross-language contract. Rust, Go, Python, TypeScript, Java, C#, Swift, Kotlin and
  Dart all validate against these same files; no language owns the schema.
- Build: none. Language bindings are generated from the schemas, never hand-written and never
  the reverse.
- Test: `check-jsonschema` validates every schema; every fixture is validated against its
  schema; a codegen-drift gate regenerates bindings for all consumer languages and fails on diff.
- CI: job `lang-json` — schema validation, fixture validation, codegen-drift gate.
- Demo: DEMO_PATH. `cert.json` is the demo's central object.

31.39 YAML — `.github/workflows/`, `infra/compose/`, `fixtures/scenarios/*.yaml`

- Implements: CI workflow definitions, Docker Compose service topology (including the network
  segmentation that the `network_segmentation` control maps onto), and the human-readable
  scenario front-matter.
- Why: the standard format for these tools; do not invent an alternative.
- Build: none.
- Test: `yamllint` with a strict config; `actionlint` on workflows; `docker compose config -q`
  on every compose file; scenario YAML validated against its JSON Schema.
- CI: job `lang-yaml`.
- Demo: DEMO_PATH. Compose brings the lab up.

31.40 TOML — `rules.toml`, `controls.toml`, `costs.toml`, `goal.toml`, `Cargo.toml`, `languages.toml`

- Implements: the ECLIPSE input tables. `rules.toml` is the single rule table (head, body, guard
  expression, `producing_sources`, `silent_possible`, provenance note) compiled by
  `eclipse-rulegen` into both the kernel and the concrete simulator. `controls.toml` declares
  controls with ordered levels. `costs.toml` is user-authored and never generated.
- Why: comments survive round-trips, the format is diff-friendly and reviewable, and these files
  are meant to be edited by a human and read in a pull request.
- Build: none; hashed into every certificate.
- Test: `taplo lint` against a committed TOML schema; a rule-table linter rejecting any rule with
  a delete effect, any rule whose guard references an undeclared control, and any rule with
  `silent_possible = true` and an empty `producing_sources`; every rule must have a unit test
  asserting it fires and one asserting it does not.
- CI: job `lang-toml` — taplo, rule linter, per-rule test coverage gate (100%).
- Demo: DEMO_PATH. Edited on screen when the presenter toggles a control level.

31.41 XML — `java/pom.xml`, `fixtures/saml/`, JUnit reports

- Implements: the Maven build definition; and a SAML assertion fixture set — signed-shaped
  `<saml:Assertion>` documents with `AuthnStatement`, `SessionIndex`, `AuthnContextClassRef`
  (password vs MFA) — which is the federated-identity telemetry source and the evidence that
  makes the `mfa` control's levels distinguishable.
- Why: SAML is XML; the MFA-vs-password distinction lives in an XML element, and re-encoding it
  as JSON at the source would erase the parsing risk the ingest path must actually handle.
- Build: Maven for `pom.xml`; fixtures are generated by a seeded generator, with no real keys —
  signatures use a throwaway key committed as an explicitly labelled test key.
- Test: XSD validation of every fixture against the SAML 2.0 schema; a parser test over five
  malformed variants (entity expansion, unexpected namespace, truncated) asserting the ingest
  path rejects them without crashing and without resolving external entities.
- CI: job `lang-xml` — XSD validation, XXE-rejection gate, `xmllint --noout`.
- Demo: DEMO_ARTIFACT. The `AuthnContextClassRef` value is what the MFA level reads.

31.42 Dockerfile — `infra/docker/*.Dockerfile`

- Implements: one image per service and per toolchain, multi-stage, digest-pinned base images,
  non-root users, no network access at runtime for the lab network.
- Why: reproducibility and isolation are hard constraints; the images are the isolation boundary.
- Build: `docker buildx bake -f infra/docker/bake.hcl`.
- Test: `hadolint` with no ignores; a gate asserting every `FROM` is digest-pinned; a
  reproducibility gate building the kernel image twice and comparing layer digests; Trivy scan
  with a documented allowlist.
- CI: job `lang-dockerfile`.
- Demo: DEMO_PATH.

31.43 HCL — `infra/terraform/`, `infra/docker/bake.hcl`

- Implements: the lab topology declared with the Terraform `docker` provider — networks,
  segmentation boundaries, service placement — and the buildx bake definition. The Terraform
  state is *parsed by SPECTRA* to derive the ground-truth network segmentation used by the
  `network_segmentation` control, so the declared topology and the simulated topology cannot
  drift.
- Why: the topology must be declarative and machine-readable by both Terraform and SPECTRA; HCL
  is the format Terraform consumes and the one the plan output is expressed in.
- Build: `terraform init -backend=local`, `terraform validate`, `terraform plan -out`.
- Test: `terraform fmt -check`, `tflint`, and a topology-consistency gate asserting the
  segmentation derived from the plan equals the segmentation the simulator assumes; changing one
  without the other fails the build.
- CI: job `lang-hcl`.
- Demo: DEMO_PATH. Brings up the segmented lab the scenario runs in.

31.44 Makefile — `Makefile`, `mk/*.mk`

- Implements: the top-level entrypoints — `make lab-up`, `make scenario`, `make prove`,
  `make verify`, `make degrade`, `make demo`, `make demo-build`, `make gates`, `make lang-audit`,
  `make repro` — with correct prerequisite graphs so artifacts rebuild only when inputs change.
- Why: a language-agnostic dependency graph across 43 toolchains; every other build system here
  is per-ecosystem and none can coordinate the others.
- Build: GNU Make 4.4, `.DELETE_ON_ERROR`, `.ONESHELL`, `SHELL := bash`, `-Werror`-equivalent via
  `MAKEFLAGS += --warn-undefined-variables`.
- Test: `make -n` dry-run gate for every public target; a test asserting `make prove` twice with
  no input change performs zero work; `make help` lists every target with a description.
- CI: job `lang-make` — dry-run all targets, idempotency test, help-completeness gate.
- Demo: DEMO_PATH.

31.45 CMake — `native/CMakeLists.txt` and subdirectories

- Implements: the C and C++ build — targets, sanitizer configurations, the exported C ABI
  package config consumed by Rust `build.rs` and by cgo, and CTest registration.
- Why: the standard cross-platform build system for the native tier, and the one Rust and Go
  tooling can be pointed at without bespoke glue.
- Build: `cmake -S native -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo`, CMake ≥ 3.25, presets in
  `CMakePresets.json`.
- Test: `ctest --output-on-failure`; a preset test that the `asan` and `release` presets both
  configure and build; an install test that the exported package is findable by `find_package`.
- CI: job `lang-cmake` — configure all presets, build, ctest, install test.
- Demo: DEMO_ARTIFACT. Produces the native binaries the collectors load.

31.46 `.gitattributes` — linguist configuration and the honesty rule

```gitattributes
# ---- Generated code: excluded from stats, still reviewed -------------------
rust/*/src/generated/**            linguist-generated=true
web/src/api/generated/**           linguist-generated=true
go/internal/schema/generated/**    linguist-generated=true
dotnet/**/obj/**                   linguist-generated=true
artifacts/**                       linguist-generated=true
**/*.lock                          linguist-generated=true

# ---- Vendored third-party code: excluded from stats ------------------------
third_party/**                     linguist-vendored=true
web/public/vendor/**               linguist-vendored=true

# ---- Documentation: excluded from the language bar -------------------------
docs/**                            linguist-documentation=true
*.md                               linguist-documentation=true
adr/**                             linguist-documentation=true

# ---- Detectable: these ARE real source and MUST be counted -----------------
# Linguist excludes some of these by default; they are first-class here.
rules/yara/**/*.yar                linguist-language=YARA       linguist-detectable=true
db/**/*.sql                        linguist-language=SQL        linguist-detectable=true
scripts/**/*.sh                    linguist-language=Shell      linguist-detectable=true
scripts/win/**/*.ps1               linguist-language=PowerShell linguist-detectable=true
infra/terraform/**/*.tf            linguist-language=HCL        linguist-detectable=true
infra/docker/**/*.Dockerfile       linguist-language=Dockerfile linguist-detectable=true
mk/*.mk                            linguist-language=Makefile   linguist-detectable=true
fixtures/asm/**/*.asm              linguist-language=Assembly   linguist-detectable=true
hw/verilog/**/*.v                  linguist-language=Verilog    linguist-detectable=true
hw/vhdl/**/*.vhd                   linguist-language=VHDL       linguist-detectable=true
analysis/matlab/**/*.m             linguist-language=MATLAB     linguist-detectable=true
mobile/ios-keychain-shim/**/*.m    linguist-language=Objective-C
lab/transformers/**/*.lua          linguist-language=Lua        linguist-detectable=true
schemas/**/*.json                  linguist-language=JSON       linguist-detectable=true

# ---- Line endings / diff behavior -----------------------------------------
* text=auto eol=lf
*.png binary
*.wasm binary
fixtures/**/*.trace binary
```

Honesty rules for this file — all are CI-enforced:

1. `linguist-vendored` may be applied ONLY to code SPECTRA did not author. It may never be
   applied to a SPECTRA-authored component to hide it, and never omitted to inflate a count.
2. `linguist-generated` may be applied ONLY where a committed generator produces the file and
   the regeneration gate proves it. If regeneration produces a diff, the build fails.
3. `linguist-documentation` may be applied ONLY to prose. Do not mark a source directory as
   documentation to suppress it, and do not un-mark documentation to inflate a language.
4. `linguist-language=` may be used ONLY to correct a genuine misdetection (e.g. `.m` files
   that are Objective-C vs MATLAB). It may never be used to relabel a file as a language it is
   not written in. `analysis/matlab/**/*.m` is MATLAB; `mobile/ios-keychain-shim/**/*.m` is
   Objective-C; both statements must be true of the file contents.
5. `linguist-detectable=true` is used only for languages Linguist suppresses by default but
   which are real, hand-authored source in this repository. Every path so marked must appear in
   `languages.toml` with a tier and a reason.
6. Do NOT commit a large generated file in a language solely to raise its share, and do NOT
   commit an empty or near-empty file in a language to make it appear.
7. `make lang-audit` cross-checks `.gitattributes` against `languages.toml` and against the
   actual file contents, and fails on: a path marked vendored that git history shows was
   authored in this repo; a generated path with no generator target in the Makefile; a
   `linguist-language` override whose declared language disagrees with a content sniff; any
   source directory in `languages.toml` that is excluded from stats.
8. The README reports the language inventory as a table with the tier and the one-sentence
   reason for each entry. It must not report a percentage bar as an accomplishment, and it must
   state that generated, vendored and documentation files are excluded from the count.
