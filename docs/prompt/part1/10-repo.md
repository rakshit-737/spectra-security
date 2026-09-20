============================================================
32. REPOSITORY LAYOUT
============================================================

32.1 Create exactly one repository, `spectra/`, as a polyglot monorepo. Every language in the target set must occupy a directory whose purpose is load-bearing: if a directory could be deleted and replaced by code already written in another language with no loss of capability, benchmark, cross-check or lab realism, it must not exist. Record the justification for each language in `docs/polyglot-rationale.md`, one row per language, with the exact artifact it produces and the test that would fail without it.

32.2 Top-level tree. Produce this structure exactly; do not invent extra top-level directories.

```
spectra/
├── .github/                      CI, issue/PR templates, CODEOWNERS
│   └── workflows/                ci.yml, gates.yml, polyglot.yml, release.yml, bench.yml
├── .devcontainer/                devcontainer.json + postCreate.sh (VS Code / Codespaces parity)
├── docker/                       all Dockerfiles + compose files (see section 33.7)
│   ├── builder.Dockerfile        the one image containing every toolchain
│   ├── runtime.Dockerfile        slim runtime for api/worker
│   ├── web.Dockerfile            node build -> nginx static serve
│   ├── lab/                      per-lab-node images (gateway, idp, appsrv, dbsrv, opsbox)
│   ├── compose.core.yml          postgres, redis, api, worker, web
│   ├── compose.lab.yml           isolated lab network, no egress
│   └── compose.bench.yml         benchmark harness, pinned CPU/memory
├── config/                       ALL policy and tunables as data (see section 34)
├── data/                         git-ignored except fixtures/ and golden/
│   ├── fixtures/                 small, committed, byte-stable bundles for unit tests
│   ├── golden/                   committed certificates + expected checker output
│   ├── generated/                seeded generator output (git-ignored)
│   └── runs/                     run manifests, liveness.json, certs (git-ignored)
├── docs/                         mkdocs site source; ADRs; threat model; limitations
│   ├── adr/                      0001-..., one decision per file, immutable once merged
│   ├── eclipse/                  proof kernel spec, checker contract, claim boundaries
│   ├── diagrams/                 .d2 / .puml sources + rendered svg (committed)
│   └── paper/                    LaTeX for the write-up; consumes bench outputs only
├── python/                       uv workspace — ingest, API, orchestration, generation
├── rust/                         cargo workspace — ECLIPSE kernel, simulator, wasm
├── go/                           go workspace — INDEPENDENT verifier + collection agents
├── haskell/                      cabal project — reference admissibility oracle
├── jvm/                          gradle multi-project — Java/Kotlin/Scala/Groovy
├── dotnet/                       Spectra.sln — C# adapters, F# lattice oracle
├── native/                       CMake project — C, C++, x86-64 assembly
├── web/                          pnpm workspace — React 18 + TS + Vite + Tailwind + D3
├── polyglot/                     single-purpose components in the remaining languages
├── sql/                          DDL, migrations, analytic views (see section 19)
├── yara/                         rules for classifying synthetic lab artifacts only
├── lab/                          lab topology as data + attacker choreography
├── bench/                        benchmark definitions, harness glue, result schemas
├── tests/                        cross-language conformance + gate suites
├── tools/                        codegen, linters, hooks, release helpers
├── scripts/                      bash + powershell entry scripts used by the Makefile
├── Makefile                      the single orchestrator (see section 33)
├── .tool-versions                asdf/mise pinned toolchain versions
├── .editorconfig                 whitespace + newline policy, enforced in CI
├── .gitattributes                text=auto eol=lf; binary fixtures marked -diff
├── .gitignore
├── .dockerignore
├── .env.example                  every variable documented; never a real secret
├── pyproject.toml                uv workspace root (members under python/)
├── uv.lock                       committed
├── Cargo.toml                    cargo workspace root (members under rust/)
├── Cargo.lock                    committed
├── rust-toolchain.toml           exact rustc channel + components + targets
├── go.work                       go workspace (modules under go/)
├── go.work.sum                   committed
├── package.json                  pnpm workspace root scripts only
├── pnpm-workspace.yaml
├── pnpm-lock.yaml                committed
├── settings.gradle.kts           gradle multi-project root
├── gradle/libs.versions.toml     gradle version catalog
├── Spectra.sln                   .NET solution
├── Directory.Build.props         shared .NET properties (LangVersion, TreatWarningsAsErrors)
├── CMakeLists.txt                top-level CMake project (native/)
├── CMakePresets.json             configure/build presets used by the Makefile
├── cabal.project                 haskell project + index-state pin
├── .pre-commit-config.yaml       fmt + lint hooks (must match `make lint` exactly)
├── codecov.yml / .coveragerc     coverage config (no coverage gate theater: report only)
├── LICENSE                       Apache-2.0
├── SECURITY.md                   scope, offline guarantee, how to report
├── CONTRIBUTING.md               toolchain bootstrap, gate list, PR checklist
├── CLAIMS.md                     what SPECTRA proves and what it does not (see 9 of spec)
└── README.md                     60-second demo first, architecture second
```

32.3 `python/` — uv workspace. Each member is an importable package with its own `pyproject.toml` and no circular dependency; `spectra_core` depends on nothing internal.

```
python/
├── spectra_core/src/spectra_core/     config loader, typed models, IDs, hashing, errors
│   ├── config/                        schema-driven loader, precedence engine (34.6)
│   ├── model/                         Pydantic v2 entities, EventId, FactId, Cert
│   ├── ids/                           deterministic ID minting, BLAKE3 wrappers
│   └── time/                          interval algebra, clock-skew constraint graph
├── spectra_ingest/                    parsers, normalizers, entity resolution
│   ├── adapters/                      one module per source type; declares producing_sources
│   ├── resolve/                       deterministic entity resolution (no ML in core)
│   └── chain/                         BLAKE3 sequence-chain verification per source
├── spectra_recon/                     state reconstruction, temporal/causal graph assembly
├── spectra_eclipse/                   thin ctypes/PyO3 binding to the Rust kernel + cert IO
├── spectra_api/                       FastAPI app, routers, dependency wiring, OpenAPI
├── spectra_gen/                       seeded synthetic telemetry + degradation/tamper engine
├── spectra_bench/                     benchmark drivers, result serialization, no plotting
├── spectra_narrate/                   OPTIONAL LLM narration over computed structures only
├── spectra_cli/                       `spectra` console entry point (Typer)
└── spectra_ml/                        OPTIONAL scoped anomaly baseline; never in the core path
```

32.4 `rust/` — cargo workspace. The kernel is `no_std`-compatible where practical and must compile to `wasm32-unknown-unknown`.

```
rust/
├── eclipse-core/        FactId, RuleInst, License, u64 atom masks, fixpoint (Dowling–Gallier)
├── eclipse-rules/       rules.toml -> guard AST -> generated Rust (build.rs codegen)
├── eclipse-cut/         Reiter/MARCO hitting-set loop, popcount-ordered branch & bound
├── eclipse-liveness/    per-source liveness, q99 inter-arrival, Bellman–Ford skew pass
├── eclipse-cert/        certificate serialization, canonical JSON, content addressing
├── spectra-sim/         concrete control simulator, generated from the SAME guard AST
├── spectra-graph/       temporal/causal graph store + query primitives
├── spectra-ffi/         cdylib + PyO3 bindings consumed by python/spectra_eclipse
├── spectra-wasm/        wasm-bindgen surface for in-browser replay (see section 33.5)
├── spectra-bench/       criterion benches; emits JSON consumed by bench/
└── xtask/               `cargo xtask` codegen/verification tasks invoked by the Makefile
```

32.5 `go/` — go workspace. Hard rule: `go/verify/` must share no code, no generated artifact and no dependency with the Rust workspace. It re-implements grounding from hashed inputs. CI enforces this with a dependency audit.

```
go/
├── verify/              module github.com/<owner>/spectra/verify — `spectra verify`
│   ├── cmd/spectra-verify/
│   ├── internal/ground/ independent re-grounding from rules.toml + bundle.jsonl
│   ├── internal/live/   independent liveness recomputation
│   └── internal/check/  closure, goal-exclusion, witness, Psi-minimality checks
├── agent/               lab collection agents (file, process, netflow tailers)
├── labctl/              parses lab/topology.hcl (hashicorp/hcl v2), drives compose
└── shipper/             deterministic bundle writer + sequence-chain signer
```

32.6 `haskell/`, `jvm/`, `dotnet/`, `native/`, `polyglot/`.

```
haskell/
└── eclipse-ref/         reference admissibility checker for license logic; QuickCheck
                         differential oracle against eclipse-liveness (gate, section 33)

jvm/
├── adapters-java/       JDBC bulk loader + OpenTelemetry-shaped source adapter framework
├── scenario-dsl-kotlin/ typed scenario DSL that COMPILES to config/scenarios/*.toml
├── degradation-scala/   degradation-matrix batch analytics over run outputs
└── buildSrc/ (Groovy)   shared Gradle build logic + config-lint plugin

dotnet/
├── Spectra.Adapters.Windows/   (C#) synthetic Windows event-log source adapter
└── Spectra.Lattice.Oracle/     (F#) FsCheck model of the control lattice; antitonicity oracle

native/
├── c/libspectra_frame/    zero-copy record framing + ring-buffer reader (C17)
├── cpp/temporal_index/    interval index + graph layout kernels (C++20)
├── asm/x86_64/            AVX2 popcount/mask-scan kernel + CPUID dispatch; differential
│                          equality test vs the portable C path is a build gate
└── include/               public headers consumed by Rust bindgen and Python cffi

polyglot/
├── php/legacy-app/        deliberately weak lab web app; emits application telemetry
├── ruby/operator/         attacker choreography runner (synthetic actions, lab-only)
├── perl/logmangle/        gnarly legacy text-format normalizer (syslog/CEF variants)
├── lua/gateway/           OpenResty guard scripts; emit API-layer telemetry
├── swift/macshim/         macOS endpoint telemetry shim (fixtures when SDK absent)
├── objc/macshim-compat/   older CoreFoundation collection path for the same shim
├── dart/certviewer/       offline certificate inspector (Flutter desktop/web)
├── r/analysis/            degradation-curve statistics + paper figures
├── matlab/liveness_ref/   q99 inter-arrival reference impl (Octave-compatible)
├── julia/frontier_ref/    knapsack/Pareto reference impl cross-checked vs Rust
├── solidity/anchor/       OPTIONAL local-chain append-only certificate anchor registry
├── verilog/propagate/     RTL model of the unit-propagation counter datapath (Icarus)
└── vhdl/propagate/        the same datapath in VHDL (GHDL); both vector-tested vs Rust
```

32.7 `web/` — pnpm workspace. No component may fabricate a verdict, count or hash; every displayed number must trace to an API field.

```
web/
├── apps/console/        React 18 + Vite app: timeline, graph, PROVE panel, checker pane
│   └── src/{routes,features,components,hooks,api,styles}
├── packages/ui/         design system: tokens.scss, primitives, dark/light themes
├── packages/graph/      D3 hypergraph + counterexample-tree renderers (GHOST styling)
├── packages/api-client/ generated from OpenAPI; regeneration is a CI gate
├── packages/wasm/       wrapper around rust/spectra-wasm output
└── e2e/                 Playwright specs incl. the 60-second demo script
```

32.8 `lab/`, `bench/`, `tests/`, `tools/`, `scripts/`.

```
lab/
├── topology.hcl         nodes, networks, trust edges, installed controls (parsed by labctl)
├── scenarios/           per-scenario choreography referenced by config/scenarios/*.toml
└── seed/                deterministic seed material for lab identities and hosts

bench/
├── definitions/         one TOML per benchmark; declares inputs, repeats, environment
├── harness/             thin glue only; all measurement code lives in the owning language
└── results/             git-ignored; schema-validated JSON written by `make benchmark`

tests/
├── conformance/         cross-language: same config -> same canonical hash (Py/Rust/Go/TS)
├── gates/               the section-7 build gates: 256-config agreement, antitonicity,
│                        rule-ordering determinism, zero-false-ROBUST across 100%->30%
├── property/            Hypothesis / proptest / QuickCheck / FsCheck suites
└── oracle/              Z3 test-only oracle harness (never importable from src trees)

tools/
├── codegen/             JSON Schema -> Python/Rust/Go/TS config bindings (single source)
├── lint/                no-magic-numbers, no-fabricated-metric, license-header, dep-audit
└── hooks/               pre-commit shims that call `make fmt` and `make lint`

scripts/
├── *.sh                 POSIX entry scripts (bash 5); called by Makefile targets
└── *.ps1                PowerShell 7 equivalents for Windows contributors
```

32.9 Negative requirements for layout.
- Do not create a `src/` directory at the repository root.
- Do not create `common/`, `utils/`, `misc/` or `shared/` anywhere. Name directories after what they do.
- Do not vendor third-party source. Pin versions in lockfiles instead.
- Do not commit generated code except where a CI gate regenerates it and diffs it to zero (`web/packages/api-client`, `tools/codegen` outputs).
- Do not commit anything under `data/generated/`, `data/runs/`, `bench/results/`.
- `go/verify/` must not import anything from `rust/`, must not link the FFI cdylib, and must not read any artifact produced by the Rust build other than the certificate and the hashed inputs named in it. The dependency audit in `.github/workflows/gates.yml` fails the build otherwise.

============================================================
33. BUILD SYSTEM AND TOOLCHAIN
============================================================

33.1 Invariant: a contributor with only Docker installed can run every target. The Makefile is the only entry point a human or CI needs. Each target either runs natively (when `make doctor` reports the toolchain present) or transparently re-executes itself inside the builder image. Never document a second way to do the same thing.

33.2 Root Makefile skeleton. Implement it in this shape.

```make
SHELL          := /usr/bin/env bash
.SHELLFLAGS    := -euo pipefail -c
.DEFAULT_GOAL  := help
MAKEFLAGS      += --warn-undefined-variables --no-builtin-rules

REPO           := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BUILDER_IMAGE  := spectra/builder:$(shell sha256sum docker/builder.Dockerfile | cut -c1-12)
PROFILE        ?= dev
SEED           ?= 1337
SCENARIO       ?= s01_token_theft
COMPLETENESS   ?= 100
JOBS           ?= $(shell nproc)

# Re-entrancy: inside the builder image SPECTRA_IN_CONTAINER=1 is set.
ifeq ($(SPECTRA_IN_CONTAINER),1)
RUN :=
else ifeq ($(SPECTRA_NATIVE),1)
RUN :=
else
RUN := docker run --rm -t \
        -v $(REPO):/work -w /work \
        -v spectra-cargo:/root/.cargo/registry -v spectra-gomod:/root/go/pkg/mod \
        -v spectra-uv:/root/.cache/uv -v spectra-pnpm:/root/.pnpm-store \
        -e SPECTRA_IN_CONTAINER=1 -e PROFILE -e SEED -e SCENARIO -e COMPLETENESS \
        --network=none $(BUILDER_IMAGE)
endif

.PHONY: help setup dev lab lab-down gen-data ingest reconstruct replay scenario \
        benchmark bench-degrade test test-all lint fmt typecheck security-test \
        wasm native polyglot docs demo clean doctor ci-local builder
```

33.3 Target contract. Every target declares inputs, outputs and a machine-checkable done condition. Implement all of them.

| Target | Does | Outputs | Done when |
|---|---|---|---|
| `help` | prints the target table parsed from `##` comments | stdout | always |
| `builder` | builds `docker/builder.Dockerfile`, tag = hash of the Dockerfile | local image | image exists; `docker run … spectra doctor` exits 0 |
| `setup` | `uv sync --all-packages`, `cargo fetch --locked`, `go work sync`, `pnpm install --frozen-lockfile`, `gradle --offline dependencies`, `dotnet restore`, `cabal build --dependencies-only`, CMake configure | lockfile-consistent caches | no lockfile is modified (CI checks `git diff --exit-code`) |
| `doctor` | probes every toolchain, prints found vs pinned version, exits 1 on mismatch | `doctor.txt` | table printed; mismatches listed with the `.tool-versions` line |
| `dev` | `docker compose -f docker/compose.core.yml up` with hot reload for api and web | running stack | `GET /healthz` 200 and web dev server responds |
| `lab` | brings up the isolated lab from `lab/topology.hcl` via `labctl` | lab containers | every node healthy; `docker network inspect` shows no default-bridge attachment |
| `lab-down` | tears down lab, removes volumes and the lab network | none | `docker ps --filter label=spectra.lab` empty |
| `gen-data` | seeded generator: `SEED`, `SCENARIO`, `COMPLETENESS` | `data/generated/<scenario>/<seed>/<completeness>/bundle.jsonl` + `manifest.json` + `ground_truth.json` | two runs with the same inputs are byte-identical (`cmp` gate) |
| `ingest` | parse, normalize, resolve entities, verify BLAKE3 chains, load Postgres | `ingest_report.json`, DB rows | report `rejected == 0` for fixture data; chain breaks localized |
| `reconstruct` | liveness (A), grounding (B), silent envelope (C) | `liveness.json`, `hypergraph.bin`, `recon_report.json` | grounding size published; no cap hit unless flagged |
| `replay` | runs the concrete simulator for a given control configuration | `replay.json` with per-step terminations | agrees with the kernel on the same config |
| `scenario` | end-to-end: gen-data → ingest → reconstruct → prove → verify | `data/runs/<run_id>/cert.json` + checker output | `spectra verify` exits 0; verdict matches `ground_truth.json` |
| `benchmark` | runs `bench/definitions/*.toml` with declared repeats | `bench/results/<ts>/*.json` | every result validates against `bench/results.schema.json` |
| `bench-degrade` | the 100%→30% matrix across all scenarios and seeds | `degradation.json` + R/Scala analysis outputs | zero false ROBUST verdicts; matrix printed |
| `test` | fast suites: unit + property, all languages, no Docker lab | junit/xml per language | all green in < 5 min on 8 cores |
| `test-all` | `test` + gates + conformance + e2e + lab integration | reports under `data/runs/tests/` | all gates in section 7 pass |
| `lint` | ruff, clippy `-D warnings`, `go vet`+staticcheck, eslint, ktlint, detekt, scalafix, `dotnet format --verify-no-changes`, hlint, shellcheck, PSScriptAnalyzer, hadolint, `tools/lint/*` | lint report | zero findings; no suppression without an inline justification comment |
| `fmt` | ruff format, `cargo fmt`, gofmt, prettier, ktlint -F, scalafmt, `dotnet format`, ormolu, `clang-format`, `taplo fmt` | rewritten files | `make fmt && git diff --exit-code` is empty in CI |
| `typecheck` | mypy `--strict` on `python/`, `tsc --noEmit`, `cargo check --all-targets`, `go build ./...`, Gradle `compileKotlin`, `dotnet build -warnaserror` | none | zero errors |
| `security-test` | bandit, `cargo audit`, `cargo deny`, `govulncheck`, `pnpm audit --audit-level=high`, `dotnet list package --vulnerable`, trivy fs, gitleaks, semgrep ruleset in `tools/lint/semgrep/` | SARIF | no high/critical; gitleaks clean |
| `wasm` | builds `rust/spectra-wasm` to `wasm32-unknown-unknown`, `wasm-opt -Oz`, assembles `polyglot/wat` hot loop, copies to `web/packages/wasm` | `.wasm` + `.d.ts` | browser kernel and native kernel agree on all fixtures |
| `native` | CMake configure+build presets for `native/` (C, C++, asm), runs ctest | static libs + `libspectra_frame.so` | asm and portable C paths produce identical output on 10k random vectors |
| `polyglot` | builds/tests every directory under `polyglot/` plus haskell, jvm, dotnet; skips with an explicit SKIPPED line when an SDK is unavailable, never silently | per-language reports | the count of SKIPPED components is printed and must be 0 in the builder image |
| `docs` | mkdocs build, renders `docs/diagrams/*.d2`, builds the paper from real bench results | `site/`, `paper.pdf` | no broken links; no figure sourced from a file absent in `bench/results/` |
| `demo` | scripted 60-second path: seeded data, prove, unset a control, re-prove, blindness beat, stability strip | terminal + browser | Playwright demo spec passes headlessly |
| `clean` | removes build outputs and generated data; keeps caches unless `DEEP=1` | none | `git status --porcelain` clean |
| `ci-local` | exactly what CI runs: `setup lint fmt-check typecheck test-all security-test bench-degrade docs` | aggregate report | same exit code as GitHub Actions on the same commit |

33.4 Per-language build systems and how the Makefile drives them.

- Cargo workspace: root `Cargo.toml` with `[workspace] members = ["rust/*"]`, `resolver = "2"`, `[workspace.lints]` denying `unsafe_code` except in `spectra-ffi` and `native` bindings, `[profile.bench]` with `lto = "thin"` and `codegen-units = 1`. `rust-toolchain.toml` pins the channel, `rustfmt`, `clippy`, `rust-src`, and the `wasm32-unknown-unknown` target. The Makefile calls `cargo xtask` for codegen (`rules.toml` → guard AST → Rust for both `eclipse-*` and `spectra-sim`), never a bespoke script.
- CMake project: root `CMakeLists.txt` `add_subdirectory(native)`, C17 and C++20 required, `CMAKE_EXPORT_COMPILE_COMMANDS=ON`, presets `dev`, `release`, `asan`, `ubsan` in `CMakePresets.json`. Assembly is assembled with NASM through `enable_language(ASM_NASM)`; the CPUID dispatch test is a ctest.
- Gradle multi-project: `settings.gradle.kts` includes `jvm/adapters-java`, `jvm/scenario-dsl-kotlin`, `jvm/degradation-scala`; shared logic in `jvm/buildSrc` (Groovy); versions only in `gradle/libs.versions.toml`; the wrapper is committed and its SHA verified.
- .NET solution: `Spectra.sln` with `dotnet/Spectra.Adapters.Windows` (C#) and `dotnet/Spectra.Lattice.Oracle` (F#); `Directory.Build.props` sets `TreatWarningsAsErrors`, `Nullable=enable`, `Deterministic=true`, `ContinuousIntegrationBuild=true`.
- pnpm workspace: `pnpm-workspace.yaml` lists `web/apps/*`, `web/packages/*`, `web/e2e`; root `package.json` contains scripts only, no dependencies; `packageManager` field pins pnpm; `.npmrc` sets `engine-strict=true` and an offline-friendly store.
- Python: root `pyproject.toml` declares `[tool.uv.workspace] members = ["python/*"]`; every member pins `requires-python = "==3.12.*"`; `uv.lock` is committed and CI runs `uv sync --locked`.
- Haskell: `cabal.project` pins `index-state` and `with-compiler`.

33.5 Determinism requirements for the build itself.
- `SOURCE_DATE_EPOCH` is exported by the Makefile; all archives and images are reproducible.
- Cargo, Go, Node, .NET and Gradle builds run offline after `make setup`; the builder container runs with `--network=none` for every target except `setup`, `builder` and `dev`.
- `make wasm` output must be byte-identical across two consecutive runs; CI hashes it.
- No build step may read the wall clock, hostname, user name or `$RANDOM` into an artifact. `tools/lint/no-nondeterminism` greps for those and fails.

33.6 Pinned toolchain versions. Put these in `.tool-versions` (mise/asdf format) and mirror them in `docker/builder.Dockerfile` and `.devcontainer/devcontainer.json`. Never leave a version floating; never use `latest` in any Dockerfile.

```
python      3.12.7
rust        1.82.0
golang      1.23.2
nodejs      20.17.0
pnpm        9.12.0
java        temurin-21.0.4+7
kotlin      2.0.20
scala       3.5.1
gradle      8.10.2
dotnet      8.0.403
ghc         9.6.6
cabal       3.12.1.0
cmake       3.30.3
ninja       1.12.1
llvm        18.1.8          # clang, clang-format, clang-tidy
nasm        2.16.03
php         8.3.12
ruby        3.3.5
perl        5.38.2
lua         5.4.7
julia       1.10.5
R           4.4.1
dart        3.5.3
swift       5.10.1
octave      9.2.0           # MATLAB-compatible reference path
solidity    0.8.27
iverilog    12.0
ghdl        4.1.0
yara        4.5.2
z3          4.13.0          # TEST ORACLE ONLY
wasm-tools  1.217.0
binaryen    119
postgres    16.4
redis       7.4.0
docker-compose v2.29.7
```

33.7 Builder image. `docker/builder.Dockerfile` is multi-stage: one stage per heavy toolchain, a final stage that copies them in, so a change to one toolchain does not invalidate the rest. It must contain every tool in 33.6, declare `ENV SPECTRA_IN_CONTAINER=1`, run as a non-root `builder` user with a writable `/work`, and end with `RUN spectra-doctor --strict`. Publish nothing; the image is built locally and cached by CI with `actions/cache` keyed on the Dockerfile hash. `make doctor` inside it must print zero mismatches, and `make polyglot` inside it must print zero SKIPPED components — that is the definition of "the builder image is complete".

33.8 Devcontainer. `.devcontainer/devcontainer.json` sets `"build": {"dockerfile": "../docker/builder.Dockerfile"}`, mounts the repo at `/work`, forwards ports 8000 (api), 5173 (web), 5432, 6379, and runs `postCreate.sh` → `make setup doctor`. It must not add features that install a second copy of any toolchain.

33.9 Negative requirements for the build system.
- Do not add a target that is an alias for another target.
- Do not let any target succeed while printing a warning it swallowed; warnings are errors in `lint` and `typecheck`.
- Do not write a build script in a language that is not already in the toolchain pin list.
- Do not gate CI on coverage percentage. Gate on the section-7 correctness gates.
- Do not allow `make test` to require the lab, the network, or a GPU.
- Do not produce a benchmark number from a target other than `benchmark` or `bench-degrade`; documentation and the paper read results from `bench/results/` and fail to build if the file is missing.

============================================================
34. CONFIGURATION AND POLICY AS DATA
============================================================

34.1 Rule: behavior is data. Detection logic, temporal axioms, control catalogs, thresholds, scenario definitions, lab topology and benchmark plans live in `config/` and `lab/`, are schema-validated, are hashed into every run manifest and certificate, and are reloadable without recompiling anything except the generated guard code (which is regenerated by `cargo xtask` from the same file).

34.2 Config tree.

```
config/
├── schema/                              JSON Schema 2020-12, one file per config kind
│   ├── rules.detection.schema.json
│   ├── rules.temporal.schema.json
│   ├── rules.obligations.schema.json
│   ├── controls.schema.json
│   ├── costs.schema.json
│   ├── goal.schema.json
│   ├── policy.schema.json
│   ├── scenario.schema.json
│   ├── lab.schema.json
│   ├── bench.schema.json
│   ├── thresholds.schema.json
│   └── profile.schema.json
├── defaults/                            base layer; every key that has a default lives here
│   ├── core.toml       ids, hashing, canonical JSON settings
│   ├── ingest.toml     batch sizes, parser strictness, chain verification mode
│   ├── recon.toml      horizon k default, grounding caps, silent-envelope switches
│   ├── eclipse.toml    atom limit, B&B node budget, corridor cap, downgrade behavior
│   ├── api.toml        timeouts, pagination, CORS origins (lab-local only)
│   └── web.toml        feature flags surfaced to the UI build
├── profiles/{dev,ci,demo,bench}.toml    sparse overlays over defaults/
├── rules/
│   ├── detection/*.toml                 the single rule table (heads, bodies, guards)
│   ├── temporal/*.toml                  interval and ordering axioms
│   └── obligations/*.toml               ~40 hand-written obligation axioms
├── controls/controls.toml               control catalog with ordered levels
├── costs/costs.toml                     USER-AUTHORED ONLY; may be absent
├── goals/*.toml                         attacker objective atoms + horizon
├── policies/
│   ├── verdict.yaml                     flag→verdict mapping; ROBUST suppression rules
│   ├── grounding.yaml                   caps, cap-hit behavior, publication of sizes
│   ├── redaction.yaml                   what narration may and may not repeat
│   └── retention.yaml                   run-artifact lifetime in data/runs/
├── scenarios/*.toml                     scenario definitions (compiled from the Kotlin DSL)
├── thresholds/
│   ├── liveness.toml                    quantile choice, min sample count, gap tolerance
│   ├── skew.toml                        Bellman–Ford bounds for backdating detection
│   └── resolve.toml                     entity-resolution decision thresholds
└── bench/degradation.toml               the 100%→30% matrix definition
```

34.3 Example: `config/controls/controls.toml`. Levels are ordered; threshold literals `x_{k,l}` are derived, never hand-listed.

```toml
schema_version = 1

[[control]]
id          = "session_binding"
title       = "Session token binding"
levels      = ["off", "ip", "device", "bound"]   # index = level ordinal, 0..3
guard_atom  = "session.binding_level"
dimensions  = ["session", "identity"]
provenance  = "RFC 8471-style binding; modeled as a guard on session.reuse rules"

[[control]]
id          = "egress_seg"
title       = "Egress network segmentation"
levels      = ["off", "zone", "microseg"]
guard_atom  = "net.egress_level"
dimensions  = ["network"]
provenance  = "lab topology edge policy; see lab/topology.hcl"
```

Derived atom set: `A = { [session_binding >= 1], [session_binding >= 2], [session_binding >= 3], [egress_seg >= 1], [egress_seg >= 2], ... }`. The loader computes `|A|`, asserts `|A| <= 64`, and on `|A| > 64` sets `flags.subset_minimal_only = true` rather than failing (see section 6 of the ECLIPSE spec).

34.4 Example: `config/rules/detection/session.toml`. Every rule declares its provenance and its producing sources; `silent_possible` is what licenses a GHOST instance.

```toml
schema_version = 1

[[rule]]
id                = "R-SESS-014"
head              = "session.reused(S, H2, T)"
body              = [
  "session.issued(S, H1, T0)",
  "session.used(S, H2, T)",
  "host.distinct(H1, H2)",
  "within(T0, T, 'PT12H')",
]
guard             = "session.binding_level < 2"
producing_sources = ["idp_audit", "gateway_access"]
silent_possible   = true
evidence_fields   = ["event_id", "session_id", "src_host"]
provenance        = "token replay across hosts when binding is weaker than device"
tests             = ["t_sess_014_fires", "t_sess_014_does_not_fire_when_bound"]
```

Validation gates, enforced at startup and in `make lint`:
1. Every `guard` parses to the guard AST and references only atoms declared in `controls.toml`.
2. Every symbol in `body` is the head of another rule or a declared base predicate.
3. `producing_sources` names sources declared in the ingest adapter registry.
4. Every rule names at least one positive test and one negative test, and both must exist.
5. No rule has a delete or retract effect; the linter rejects the keyword outright.

34.5 Startup validation. Fail closed. Implement `spectra_core.config.load(profile, overrides)` and the equivalent in Rust, Go and TypeScript from the same generated bindings.

```
                +---------------------+
 config/*.toml  |  1. PARSE           |  TOML/YAML/HCL -> untyped tree; syntax errors
 config/*.yaml  |                     |     reported with file:line:col
 lab/*.hcl      +----------+----------+
                           v
                +---------------------+
                |  2. SCHEMA VALIDATE |  JSON Schema 2020-12; additionalProperties:false
                +----------+----------+     unknown key = fatal, never ignored
                           v
                +---------------------+
                |  3. MERGE           |  precedence order of 34.6, origin recorded per key
                +----------+----------+
                           v
                +---------------------+
                |  4. CROSS-VALIDATE  |  rule/control/source/goal referential integrity,
                +----------+----------+     |A| <= 64, horizon k > 0, caps consistent
                           v
                +---------------------+
                |  5. FREEZE + HASH   |  canonical JSON -> BLAKE3 per file and per bundle;
                +----------+----------+     config object is immutable thereafter
                           v
                  effective config + config_hashes -> run manifest -> certificate
```

- On any failure the process exits with code 78 (`EX_CONFIG`), prints every error (not just the first), and starts no server, no worker and no solver.
- The API exposes `GET /api/v1/config/effective` returning the frozen config with per-key origin and the hash set. The UI header shows the short hash; it must match the certificate.
- `additionalProperties: false` in every schema. A typo'd key is a fatal error, never a silent default.

Transcript that must work:

```
$ spectra config show --profile=bench --effective --with-origin
recon.horizon_k               = 6          [profiles/bench.toml:11]
recon.grounding.max_instances = 200000     [defaults/recon.toml:24]
eclipse.atom_limit            = 64         [defaults/eclipse.toml:7]
eclipse.corridor_cap          = 512        [env SPECTRA__ECLIPSE__CORRIDOR_CAP]
thresholds.liveness.quantile  = 0.99       [thresholds/liveness.toml:4]
costs                         = <absent>   [no config/costs/costs.toml; frontier disabled]
config_hash (bundle)          = blake3:9c41e0f7d2b8...
$ echo $?
0
```

34.6 Precedence order. Lowest to highest; document this table in `docs/configuration.md` and implement it once, in `spectra_core.config`, with the other languages reading the same resolved file.

| # | Source | Example | Mutable at runtime |
|---|---|---|---|
| 1 | Schema `default` values | `"default": 0.99` in `thresholds.liveness.schema.json` | no |
| 2 | `config/defaults/*.toml` | `recon.horizon_k = 4` | no |
| 3 | `config/profiles/<PROFILE>.toml` | `PROFILE=bench` | no |
| 4 | Scenario file `[overrides]` block | `config/scenarios/s01.toml` | no |
| 5 | Local overlay `config/local.toml` (git-ignored) | developer machine | no |
| 6 | Environment variables `SPECTRA__<SECTION>__<KEY>` | `SPECTRA__RECON__HORIZON_K=6` | no |
| 7 | CLI flags | `spectra reconstruct --horizon-k=6` | no |

Rules: later wins; merging is per-leaf-key, never whole-table replacement, except for arrays, which are replaced wholesale and never appended to. The resolved origin of every key is retained and printed by `config show --with-origin`.

Frozen keys may only be set at levels 1–4 and are rejected from env and CLI: `core.hash_algorithm`, `core.canonical_json`, `eclipse.atom_limit`, `rules.*`, `controls.*`, `costs.*`, and the generator `seed` once a run has started. Attempting to override a frozen key from level 6 or 7 is a fatal config error, not a warning.

34.7 No magic numbers in code. Enforced, not merely requested.
- Any numeric literal other than `0`, `1`, `-1`, `2`, array indices, and exponents in pure math must come from the generated config bindings.
- `tools/lint/no-magic-numbers` runs per language (ruff `PLR2004`, clippy `unreadable_literal` plus a custom xtask pass, a Go analyzer, an ESLint rule, detekt `MagicNumber`, a Roslyn analyzer) and is part of `make lint`.
- Suppression requires an inline comment of the form `# noqa: PLR2004 -- <reason>` and the reason is checked to be non-empty by the linter's own test.
- Thresholds derived from data (the liveness `q99`) are computed from the run's own data at runtime; the quantile itself is config. Never hardcode a quantile, a timeout, a window, a cap, a cost, or a level ordinal.
- `tools/codegen` generates, from the JSON Schemas: Pydantic models, Rust `serde` structs with `schemars`, Go structs, and TypeScript types. CI regenerates and diffs to zero. Hand-editing generated files fails the build.

34.8 Environment and secrets.
- SPECTRA is offline. There are no API keys, no cloud credentials, no paid services. `.env.example` lists every variable with a comment and a safe lab-local value; `.env` is git-ignored.
- Only these categories may appear in the environment: connection strings for the local Postgres and Redis, the `PROFILE` selector, `SPECTRA__*` overrides, and lab-only credentials generated by `make lab` into `data/runs/lab/credentials.env` (regenerated per lab bring-up, never committed).
- Secrets are never logged, never echoed into run manifests, never included in certificates, and are redacted by a logging filter that is unit-tested against a corpus of secret-shaped strings.
- `gitleaks` runs in `make security-test` and in a pre-commit hook.
- The optional LLM narration path reads its endpoint from config; if unset, narration is disabled and every UI surface renders the deterministic structure alone. No default endpoint, no fallback to a hosted provider, ever.

34.9 Config in the run record. Every run manifest and every certificate carries the BLAKE3 of: `rules` (the concatenated canonical form of all rule files), `controls`, `goal`, `bundle`, `liveness`, plus the `profile` name, the resolved `seed`, and the horizon `k`. `spectra verify` recomputes those hashes from the files it is given and refuses the certificate if any differs. A certificate whose config hashes cannot be reproduced is invalid — not "suspect", invalid.

34.10 Negative requirements for configuration.
- Do not read configuration at import time or in a module-level constant; the frozen config object is passed explicitly.
- Do not allow a config value to be mutated after freeze; the object is immutable and tests assert it.
- Do not add a config key without adding it to a schema, with a description, in the same commit.
- Do not add a "debug" or "unsafe" flag that relaxes a verdict rule. Flags in `config/policies/verdict.yaml` may only make verdicts weaker (ROBUST → OPTIMISTIC-ONLY), never stronger.
- Do not generate `costs.toml`. If it is absent, the Pareto frontier is disabled and the UI says so; SPECTRA never invents a cost.
- Do not put rules, thresholds or control definitions in the database. Postgres stores telemetry, derived facts and run artifacts; policy lives in `config/` under version control.
- Do not support a remote config source, a feature-flag service, or hot reload of rules mid-run. Rules change between runs, never within one.
