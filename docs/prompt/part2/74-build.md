============================================================
74. OFFLINE BUILD, TOOLCHAIN MATRIX, CI BUDGET AND THE WINDOWS REALITY
============================================================

## 74.0 Scope and standing overrides

This section owns every question of the form "how does this actually build, and who pays for
running the gates". Nothing in Part I that contradicts it survives.

- **OVERRIDES Part I:** the phrase "the build fails otherwise", wherever it appears in sections
  0-56, no longer means "on every push". It means "a named gate exists, it is registered in
  `ci/gates.toml`, it is assigned to exactly one tier, and it fails the build in that tier".
  A requirement with no gate id is not a requirement; the registry linter in 74.6 deletes the
  claim or fails the build.
- **OVERRIDES Part I (§52.1):** "green twice in a row on a clean clone" applies to the T2 nightly
  tier only, not to every milestone push. Per-push green is required on the T1 tier.
- **OVERRIDES Part I (§43.1):** Tier C and Tier D language unit tiers do not run per-PR. They run
  in T2. A Tier C/D failure never blocks a Tier A milestone.
- **OVERRIDES Part I:** every base image reference pinned by tag is replaced by a digest pin.
  A `FROM` line without `@sha256:` fails `make lint-images`.
- **OVERRIDES Part I:** MATLAB has no toolchain image and no CI job. The toolchain matrix carries
  GNU Octave. Any language absent from `languages.toml` gets no toolchain, no image layer and no
  CI job, and its source directory must not exist.
- **OVERRIDES Part I:** no `make` target is supported on Windows `cmd.exe` or PowerShell. Every
  target runs inside WSL2 or the devcontainer (74.11), enforced by a guard in the Makefile.

Two mutually exclusive network postures exist in this repository and no third:

```
 NETWORK-PERMITTED (rare, human-initiated)        NETWORK-FORBIDDEN (everything else)
 ----------------------------------------         ------------------------------------
 make toolchain-refresh                           make build-offline / test / bench / demo
   1. resolve + lock  -> toolchains.lock            1. git clone file://$PWD /tmp/spectra-clean
   2. fetch vendor bundles per ecosystem            2. docker run --network=none \
   3. docker build FROM <base>@sha256:...                spectra/toolchain-a@sha256:<digest>
   4. record image digests -> images.lock           3. make -C /tmp/spectra-clean <target>
   5. docker save -> cas/oci/<digest>.tar           4. egress sentinel asserts 0 packets out
        |                                                |
        v                                                v
   images.lock + toolchains.lock COMMITTED          PASS/FAIL with no resolver, ever
```

Crossing from the right column to the left mid-build is a build failure, not a fallback.

## 74.1 The toolchain image set: one digest-pinned image per tier

Build exactly four images. Do not build one image per language and do not build one image for
everything.

| Image | Contents (derived from `languages.toml`) | Consumed by | Size ceiling |
|---|---|---|---|
| `spectra/toolchain-a` | Rust, Go, Python, Node/TypeScript, SQL client, Bash, make, git, jq, blake3 | T1 per-PR, every Tier A gate, devcontainer | 2.5 GB (illustrative, not a target) |
| `spectra/toolchain-b` | Tier A plus C/C++ (clang+gcc), GHC/cabal, JVM (temurin), binutils/nasm | T2 oracle and performance gates | 5 GB (illustrative, not a target) |
| `spectra/toolchain-c` | Range-emitter runtimes: PowerShell Core, PHP, Ruby, Perl, Lua, Kotlin, Dart | T2 emitter gates, range build | 4 GB (illustrative, not a target) |
| `spectra/toolchain-d` | Analysis: R, Julia, Octave, Python scientific stack | T2/T3 analysis and figure regeneration | 6 GB (illustrative, not a target) |

Rules:

1. Each image is built from a **base pinned by digest**, never by tag. Record the base digest, the
   image digest and the build date in `images.lock`.
2. Each image is **self-contained and offline-complete for its tier**: every vendored dependency
   for every ecosystem it owns is baked into the image layer at a fixed path under
   `/opt/spectra/vendor/<ecosystem>/`. A test run must never consult a network resolver, a proxy,
   or a user-level cache in `$HOME`.
3. Images are built for `linux/amd64` only. `linux/arm64` is explicitly unsupported and README
   must say so; do not emit a multi-arch manifest that implies otherwise.
4. Images are published to a registry AND exported as OCI tarballs into `cas/oci/<digest>.tar`
   with a `.blake3` sidecar, so a reviewer with no registry access can `docker load` and reproduce.
5. `make toolchain-refresh` is the ONLY target permitted to touch the network. It regenerates
   `toolchains.lock` and `images.lock`, and its diff is reviewed as a change like any other.

`images.lock` (canonical, sorted by key, no floats, LF endings):

```toml
schema_version = 1
generated_by   = "make toolchain-refresh"

[base.debian_bookworm_slim]
ref    = "docker.io/library/debian"
digest = "sha256:<64 hex>"
note   = "sole base for all four tier images"

[image.toolchain_a]
base        = "base.debian_bookworm_slim"
digest      = "sha256:<64 hex>"
dockerfile  = "docker/toolchain-a.Dockerfile"
dockerfile_blake3 = "<64 hex>"
languages   = ["rust", "go", "python", "typescript", "bash", "sql"]
oci_tarball = "cas/oci/sha256-<64 hex>.tar"
```

Gate `G-IMG-001` (T1): every `docker run`, `FROM`, devcontainer reference and CI `container:`
field resolves to a digest present in `images.lock`. Gate `G-IMG-002` (T1): `images.lock` digests
match the locally loaded images, or the job fails with "toolchain drift" and does not proceed.

## 74.2 Vendoring strategy, per ecosystem

Every ecosystem below has a declared vendor mechanism, a declared offline switch and a declared
integrity mechanism. An ecosystem with no row here may not be introduced.

| Ecosystem | Vendor mechanism | Offline switch enforced in image | Integrity |
|---|---|---|---|
| Rust (cargo) | `cargo vendor vendor/cargo` + `.cargo/config.toml` source replacement | `--offline`, `CARGO_NET_OFFLINE=true` | `Cargo.lock` checksums |
| Python (uv/pip) | PEP 503 flat index at `/opt/spectra/vendor/python/simple`, wheels only | `--no-index --find-links`, `UV_OFFLINE=1` | `requirements.lock` with `--require-hashes`; sdist builds forbidden |
| Node (pnpm) | pnpm content-addressed store at `/opt/spectra/vendor/pnpm-store` | `--offline`, `npm_config_offline=true` | `pnpm-lock.yaml` integrity hashes |
| Go | `go mod vendor` into `vendor/` | `GOFLAGS=-mod=vendor GOPROXY=off GONOSUMDB=*` | `go.sum` |
| JVM (Maven) | local repository snapshot at `/opt/spectra/vendor/m2` | `mvn -o -Dmaven.repo.local=...` | `checksums.md5/sha1` retained; artifact list pinned |
| JVM (Gradle) | `--offline` + dependency verification | `gradle --offline` | `gradle/verification-metadata.xml` (sha256, required) |
| .NET (NuGet) | offline feed dir at `/opt/spectra/vendor/nuget` | `nuget.config` with a single local source | `packages.lock.json`, `RestoreLockedMode=true` |
| Haskell | Stackage snapshot tarball unpacked to a local package repo | `cabal --offline`, `--index-state` pinned | `cabal.project.freeze` + sha256 of snapshot tarball |
| OCaml (opam) | local opam repository tarball + pre-built switch in the image | `opam --no-auto-upgrade`, `OPAMOFFLINE` | `opam.locked` per package |
| R | `renv` cache seeded into the image | `renv::restore()` from cache, `repos=NULL` | `renv.lock` hashes |
| Julia | pre-populated depot at `/opt/spectra/vendor/julia-depot` | `JULIA_PKG_OFFLINE=true` | `Manifest.toml` tree hashes |
| Dart/Flutter | pub cache seeded into the image | `PUB_OFFLINE=true` | `pubspec.lock` |
| Octave | Forge packages installed at image build from pinned tarballs | none needed at test time | sha256 per tarball in `toolchains.lock` |
| Conda/mamba | **forbidden** unless a `conda-lock` file with explicit URLs and sha256 exists, and then Tier D only | `--offline` | `conda-lock.yml` |
| System packages | apt with a pinned snapshot suite and `Packages` index sha256 | image build only | recorded in `toolchains.lock` |

Rules:

1. **Nothing over ~50 MB (illustrative, not a target) is vendored into git.** Large vendor trees
   are packed into `vendor-bundle-<ecosystem>-<blake3>.tar.zst`, fetched once during
   `make toolchain-refresh`, baked into the image, and referenced from `toolchains.lock` by hash.
   Git holds the lockfiles and the hashes, never the blobs.
2. Source builds of native extensions are forbidden at test time. If a wheel/binary does not exist
   for `linux/amd64`, the dependency is built once during image construction or dropped.
3. `toolchains.lock` records, per ecosystem: the resolver version, the lockfile path, the lockfile
   blake3, the vendor bundle blake3, and the in-image path. Gate `G-VEND-001` (T1): recompute all
   lockfile hashes and fail on mismatch.
4. Gate `G-VEND-002` (T2): for each ecosystem, delete the vendor path inside a `--network=none`
   container and assert the corresponding build FAILS. A vendoring claim nobody can break is a
   vendoring claim nobody has tested.

## 74.3 `make build-offline` — the gate that proves the claim

`build-offline` is the authoritative test of "fully offline, locally reproducible". It must do all
of the following, in order, or it is not this gate:

```make
build-offline: guard-sandbox lint-images
	rm -rf $(CLEAN)            # $(CLEAN) := /tmp/spectra-clean-$(shell date +%s)
	git clone --no-hardlinks --depth=1 "file://$(CURDIR)" $(CLEAN)
	scripts/ci/assert-clean-tree.sh $(CLEAN)      # no untracked leakage from the working copy
	docker run --rm \
	  --network=none \
	  --env TZ=UTC --env LC_ALL=C --env SOURCE_DATE_EPOCH=$(SDE) \
	  --mount type=bind,src=$(CLEAN),dst=/w \
	  --mount type=bind,src=$(CURDIR)/cas,dst=/cas,ro \
	  --read-only --tmpfs /tmp:rw,size=2g \
	  --cpus=$(CI_CPUS) --memory=$(CI_MEM) \
	  spectra/toolchain-a@$(TOOLCHAIN_A_DIGEST) \
	  bash -lc 'make -C /w core && make -C /w test-t1'
	scripts/ci/egress-sentinel.sh --assert-zero
```

Requirements:

1. `--network=none` is mandatory. Do not substitute a proxy, an allowlist or a firewall rule.
   A gate that permits any resolver is not this gate.
2. The clone is from `file://` so `.git` hooks, ignored files and stale build directories in the
   author's working copy cannot mask a missing vendored dependency.
3. `$HOME` inside the container is a tmpfs. Any ecosystem that silently falls back to a user cache
   fails here, which is the point.
4. The egress sentinel (`G-NET-001`, T1) counts packets on the container's veth and on the host's
   default route for the duration; nonzero egress fails the build and prints the destination.
5. Gate `G-OFF-001` (T1) is `make build-offline` itself. Gate `G-OFF-002` (T2) repeats it with
   every cache disabled and every tier image, cold.

Expected transcript (shape is normative; every numeral below is illustrative, not a target):

```
$ make build-offline
[guard]  sandbox=wsl2 kernel=5.15.167.4-microsoft-standard-WSL2 ok
[images] toolchain-a sha256:9c1f… matches images.lock            ok
[clone]  /tmp/spectra-clean-1758326400  (1,412 files, 18.7 MiB)
[net]    container network: none; sentinel armed on veth + default route
[build]  rust(kernel) vendor=offline ................ 4m12s
[build]  go(checker)   vendor=offline ................ 0m31s
[build]  python(svc)   --no-index --require-hashes ... 0m44s
[build]  node(ui)      pnpm --offline ................ 1m03s
[test]   T1 gates: 38 gates, 38 green
[net]    egress packets observed: 0                              ok
BUILD-OFFLINE: PASS   total 9m47s
```

## 74.4 Gate registry and the tier system

Every gate is a row in `ci/gates.toml`. There is no other place a gate may be declared.

```toml
schema_version = 1

[[gate]]
id            = "G-KERNEL-FALSE-ROBUST"
title         = "zero false ROBUST on declared suppression classes"
tier          = "T2"                       # T0 | T1 | T2 | T3
owner_section = 62
make_target   = "gate-false-robust"
sampled       = true                       # requires a [sampling] block
soundness     = true                       # => non-quarantinable (74.8)
artifact      = "false-robust-matrix.json"
budget_s      = 2700                       # declared ceiling (illustrative, not a target)
```

| Tier | Trigger | Wall-clock ceiling | Meaning of a failure |
|---|---|---|---|
| **T0** | pre-commit hook, local, inside WSL2 | 60 s (illustrative, not a target) | commit refused locally; never authoritative |
| **T1** | every push and every PR | **20 min** end-to-end, all jobs (illustrative, not a target) | PR is red; merge blocked |
| **T2** | nightly, `main` only | **90 min** (illustrative, not a target) | issue auto-filed; milestone loses green; `main` marked degraded in README status table |
| **T3** | weekly, `main` only | **6 h** (illustrative, not a target) | release blocked; headline numbers in docs are invalidated until green |

Tier assignment, normative:

| Gate class | Tier | Rationale |
|---|---|---|
| Format, lint, naming lint, glossary lint, banned-phrase/claims linter | T0 + T1 | cents, catches drift instantly |
| Guard-AST hash equality across backends; non-threshold level linter | T1 | structural, sub-second |
| Determinism: byte-identical replay, same runner, 2 repeats | T1 | fast and load-bearing |
| Determinism: byte-identity across two distinct runners/CPUs | T2 | needs a second runner |
| `make build-offline` (toolchain-a) | T1 | the offline claim is the headline |
| `make build-offline` cold, all four tier images | T2 | slow, low churn |
| Rust/Go/Python/TS unit + contract tests (Tier A languages) | T1 | critical path |
| Tier B oracle gates (Haskell admissibility, C hot path differential) | T2 | second toolchain image |
| Tier C/D language jobs + polyglot mutation audit | T2 | **OVERRIDES §43.1** |
| Adversarial certificate corpus (must-reject) | T1 (spine subset) / T2 (full corpus) | security gate, partly cheap |
| Checker parser fuzzing (time-boxed) | T2 (short) / T3 (long) | cost scales with time budget |
| Randomized-configuration simulator-vs-kernel agreement | T1 sampled / T2 full | see 74.5 |
| Degradation matrix + zero-false-ROBUST + false-UNSAFE reporting | T1 spine cells / T2 full matrix / T3 all seeds | see 74.5 |
| ER precision/recall across the matrix | T2 | depends on the matrix |
| Benchmark harness, published numbers | T3 only | variance protocol needs a quiet runner |
| `make demo` hash check | T1 | it is the flagship artifact |
| `make reproduce` (every docs number regenerated) | T3 | full pipeline |
| Range egress-isolation probe | T2 | requires the compose set up |

Gate `G-REG-001` (T1): every `make` target referenced by a gate exists; every gate has exactly one
tier; the sum of `budget_s` per tier is ≤ that tier's declared ceiling; any requirement sentence in
`docs/prompt/` containing "build fails" without a resolvable gate id fails the lint.

## 74.5 The sampling plan (mandatory for `sampled = true` gates)

Two gates are combinatorially large: the randomized-configuration agreement gate and the
degradation matrix. **OVERRIDES Part I (§7 / ECLIPSE §7):** "256 randomized configurations per
fixture" and "the entire 100%→30% degradation matrix" are T2/T3 obligations. T1 runs a declared,
deterministic sample, and no artifact produced by a sampled run may be described as covering the
whole space.

Sampler, normative pseudocode (no RNG library, no wall-clock, fully reproducible):

```
cells   = total_order(all_cells)              # lexicographic over the canonical cell key
N       = len(cells)
spine   = [c for c in cells if c.is_spine]    # always run, never sampled
k       = tier.sample_size                    # from gates.toml, e.g. 24 (illustrative)
epoch   = read_int("ci/epoch.txt")            # committed, incremented by the nightly job
stride  = tier.stride                         # fixed, coprime with N, recorded in the artifact
offset  = (epoch * k) mod N
picked  = [ cells[(offset + i*stride) mod N] for i in 0..k-1 ]
plan    = spine ++ dedup(picked)
seed(c) = blake3("spectra/sample/v1" || gate_id || c.key || epoch)[0..8]
```

- **Spine cells are never sampled away.** For the degradation matrix the spine is: completeness
  100% and 30% at both ends, plus each degradation operator at least once, plus every declared
  suppression class at least once. For the randomized-config gate the spine is: all-controls-off,
  all-controls-max, and each control alone at its top level.
- **Coverage debt.** Because `stride` is coprime with `N`, the rotation visits every cell within
  `ceil(N/k)` epochs. The artifact records `coverage_debt = cells never run in the last
  ceil(N/k) epochs`. Gate `G-SAMP-002` (T2): `coverage_debt` must be empty, or the build fails.
- **Every sampled cell is recorded in the artifact.** A results file without a `sample_plan` block
  is invalid input to the docs build.

`sample-plan.json` (embedded in every sampled gate's artifact):

```json
{
  "schema_version": 1,
  "gate_id": "G-KERNEL-FALSE-ROBUST",
  "tier": "T1",
  "space": { "key_fields": ["completeness","operator","scenario","seed"], "cardinality": 1440 },
  "sampler": { "algorithm": "stride-rotation/v1", "stride": 271, "epoch": 118, "k": 24 },
  "spine_cells": ["100|none|s_held_01|0", "30|suppress|s_held_01|0"],
  "sampled_cells": [
    {"key": "70|delay|s_held_03|2", "seed": "8f2a1c04", "verdict": "UNSAFE", "false_robust": false}
  ],
  "coverage_debt": [],
  "claim_scope": "SAMPLED — this artifact does not establish any property of unsampled cells"
}
```

- Gate `G-SAMP-001` (T1): the docs/claims linter rejects any sentence bound to an artifact whose
  `claim_scope` is `SAMPLED`. Headline numbers bind only to T2/T3 artifacts with full coverage.
- Forbidden: choosing the sample from the runner's clock, from `$RANDOM`, from the git SHA, or by
  any procedure that cannot be replayed from `ci/epoch.txt` alone.

## 74.6 Cache strategy

1. Caches accelerate; they never determine outcomes. Gate `G-CACHE-001` (T2): one job per night
   runs the full T1 tier with all caches disabled and diffs every produced artifact hash against
   the cached run. A difference is a determinism defect, filed against section 58's charter.
2. `make build-offline` runs with **no cache of any kind**. Restoring a cache into that job is a
   build failure.
3. Cache keys are content-derived and never include a date or a run number:

| Cache | Key | Restore keys | Scope |
|---|---|---|---|
| cargo target dir | `t1-cargo-${toolchain_a_digest}-${blake3(Cargo.lock)}` | `t1-cargo-${toolchain_a_digest}-` | branch + main |
| go build/test cache | `t1-go-${toolchain_a_digest}-${blake3(go.sum)}` | prefix | branch + main |
| pnpm store | `t1-pnpm-${toolchain_a_digest}-${blake3(pnpm-lock.yaml)}` | prefix | branch + main |
| docker layer cache | none (images are prebuilt and digest-pinned) | — | — |
| fixture/bundle CAS | `cas-${blake3(generator_inputs)}` | exact only | main only, read-only from PRs |

4. PRs may read `main`'s caches and may not write them. This prevents a PR from poisoning the
   cache that a release build reads.
5. Total cache footprint ceiling: 8 GB (illustrative, not a target), enforced by an eviction job;
   exceeding it is a warning in T1 and a failure in T2.

## 74.7 Concurrency groups and artifact retention

```yaml
# T1 per-PR
concurrency:
  group: t1-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
# T2 nightly / T3 weekly / anything that publishes an artifact or mutates ci/epoch.txt
concurrency:
  group: t2-main
  cancel-in-progress: false      # never cancel a run whose artifacts back a published number
```

| Artifact class | Example | Retention | Survives expiry as |
|---|---|---|---|
| Certificates from gate runs | `cert-*.json` | 14 days (illustrative, not a target) | blake3 + verdict row appended to `ci/ledger/certs.tsv`, committed |
| Degradation matrix results | `false-robust-matrix.json` | 90 days (illustrative, not a target) | full file committed under `docs/research/results/` when it backs a docs claim |
| Benchmark results (T3) | `bench-<run_manifest_hash>.json` | 400 days (illustrative, not a target) | committed; a number in docs without its committed file fails `G-CLAIM-001` |
| Sample plans | `sample-plan.json` | same as parent artifact | committed alongside results |
| Quarantine evidence | failing logs of a quarantined test | until quarantine expiry + 30 days | referenced by ledger row |
| Toolchain OCI tarballs | `cas/oci/*.tar` | not a CI artifact | committed by hash reference; blobs mirrored out-of-band |
| Raw CI logs | — | platform default | not citable; never a source for a number |

Rule: **an artifact that has expired can never be cited.** The committed ledger, not the CI
artifact store, is the durable record. Free-tier artifact storage is finite and will silently
evict; design for that rather than discovering it.

## 74.8 Zero-flake policy and the quarantine ledger

1. **Zero-flake means flakes fail the build.** Automatic retry is forbidden. `continue-on-error`,
   `retries:`, `--rerun-failed`, `pytest-rerunfailures`, `go test -count=1 || true` and every
   equivalent are banned. Gate `G-FLAKE-001` (T1) is a workflow linter that greps every file under
   `.github/workflows/` and `ci/` for these constructs and fails on a hit.
2. Flake detection is an active gate, not an observation: `G-FLAKE-002` (T3) runs the entire T1
   tier R = 5 times (illustrative, not a target) across two runners with differing CPU models and
   diffs all artifact hashes. Any nondeterministic outcome fails the week's release.
3. A test may be quarantined only by adding a row to `ci/quarantine.toml`:

```toml
schema_version = 1
max_open       = 5          # illustrative, not a target; exceeding it fails G-FLAKE-003

[[entry]]
gate_id        = "G-UI-TREE-RENDER"
test_id        = "playwright/counterexample-tree.spec.ts::expands_ghost_node"
opened         = 2026-09-18
expires        = 2026-10-02          # opened + 14 days, hard maximum
observed_rate  = "3 failures / 40 runs (measured, run ids in evidence)"
evidence       = "ci/ledger/flake/G-UI-TREE-RENDER-2026-09-18.log"
hypothesis     = "animation frame race in the expand handler; not a kernel defect"
owner          = "rakshit"
```

4. Expiry is enforced, not advisory. Gate `G-FLAKE-003` (T0 + T1): if `today > expires` for any
   open entry, **the build fails on every tier** until the entry is fixed and removed or the test
   is deleted with a note in `WAIVER.md`. Renewal of the same `test_id` more than once is
   forbidden; the second renewal attempt fails the gate and forces deletion or repair.
5. A quarantined test still executes in T2/T3; its result is recorded and reported, it simply does
   not gate. A quarantined test that has passed 20 consecutive runs (illustrative, not a target)
   must be un-quarantined; the gate fails if it is not.
6. **Non-quarantinable gate classes** (`soundness = true` in `gates.toml`): zero-false-ROBUST,
   false-UNSAFE reporting, the adversarial certificate must-reject corpus, determinism/byte-identity,
   the guard-AST equality and non-threshold-level linters, the antitonicity property test,
   `make build-offline`, the egress sentinel, and the claims linter. Adding a quarantine row for
   any of these is itself a build failure. If one of these flakes, the system is wrong, not the CI.
7. README's status table renders open quarantine entries and open waivers. Hiding them in git
   history is forbidden.

## 74.9 CI budget accounting

```
$ make ci-budget
TIER  JOBS  DECLARED CEILING   SUM(budget_s)   HEADROOM   MONTHLY MIN (est.)
T0       1            60 s            41 s       32%        —
T1      12          1200 s          1043 s       13%      ~1,250 min
T2      21          5400 s          4880 s        9%      ~2,450 min
T3       9         21600 s         19100 s       12%      ~1,270 min
TOTAL                                                     ~4,970 min / month
BUDGET (ci/budget.toml): 6,000 min/month (illustrative, not a target)     PASS
```

- Gate `G-BUDGET-001` (T1): `sum(budget_s)` per tier ≤ that tier's ceiling, and the estimated
  monthly minutes ≤ the declared budget. Adding a gate without removing time elsewhere fails here.
  This is the mechanism that keeps "57 sections of build-fails-otherwise" from becoming fiction.
- Every gate's `budget_s` is a **declared ceiling enforced by a per-job timeout**, not a measured
  runtime. A job exceeding its ceiling fails as `BUDGET_EXCEEDED`, which is a planning defect to be
  fixed by sampling or tier demotion, never by raising the number silently; the raise must appear
  in the diff of `ci/gates.toml`.
- Wall-clock ceilings exist only at the CI-job level. **They never appear inside a decision path**
  of the kernel, the checker or the sampler (see the determinism charter); a gate may be killed by
  its timeout, but no verdict may depend on elapsed time.

## 74.10 The Windows reality

The author develops on Windows 11. State this as a supported configuration with hard rules rather
than pretending the host is Linux.

1. **WSL2 is required.** Windows 11 with WSL2, a Linux distribution image pinned in
   `docs/dev/wsl.md`, and `systemd=true` in `/etc/wsl.conf`. WSL1 is unsupported: it does not give
   the filesystem and process semantics the range and the determinism gates assume.
2. **The repository must live inside the WSL2 filesystem** (e.g. `~/src/spectra`), never under
   `/mnt/c/...`. Working from `/mnt/c` produces case-insensitive path collisions, wrong file modes
   and order-of-magnitude slower I/O, all of which corrupt determinism gates.
   Gate `G-WIN-001` (T0): the Makefile guard refuses to run when `$(CURDIR)` starts with `/mnt/`.
3. **Every make target runs inside WSL2 or the devcontainer.** Guard, included first by the root
   Makefile:

```make
# ci/guard.mk — included before any other target
UNAME_S := $(shell uname -s 2>/dev/null)
IS_WSL  := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo 1)
ifneq ($(UNAME_S),Linux)
  $(error SPECTRA targets run on Linux only. From Windows: open WSL2 (`wsl -d <distro>`) \
          or the devcontainer, then re-run. PowerShell and cmd.exe are not supported.)
endif
ifeq ($(or $(IS_WSL),$(SPECTRA_DEVCONTAINER),$(CI)),)
  $(error not in WSL2, devcontainer or CI; set SPECTRA_DEVCONTAINER=1 only inside the container)
endif
ifneq ($(filter /mnt/%,$(CURDIR)),)
  $(error repo is on a Windows drive mount ($(CURDIR)); clone into the WSL2 filesystem instead)
endif
guard-sandbox: ; @true
```

4. **Docker Desktop resource minimums**, declared in `docs/dev/windows.md` and asserted by
   `make doctor`. All figures illustrative, not targets:

| Profile | CPUs | RAM | Swap | Disk free | Notes |
|---|---|---|---|---|---|
| `core` (kernel, checker, unit tests, `build-offline`) | 4 | 8 GB | 2 GB | 40 GB | minimum to run T1 locally |
| `matrix` (degradation matrix, T2 subset locally) | 6 | 16 GB | 4 GB | 80 GB | parallel kernel runs |
| `range` (compose set + emitters) | 8 | 16 GB | 4 GB | 120 GB | container count dominates |

`%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=16GB
processors=6
swap=4GB
localhostForwarding=true
kernelCommandLine=cgroup_no_v1=all
[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```

`make doctor` prints detected CPUs/RAM/disk, compares to the profile requested via
`PROFILE=core|matrix|range`, and exits nonzero with the exact `.wslconfig` edit required. It never
silently proceeds on an under-provisioned host, because a starved run produces timeouts that look
like defects.

5. **Line endings.** Committed `.gitattributes` (Gate `G-WIN-002`, T1: this file must exist and
   match the committed golden copy byte for byte):

```gitattributes
* text=auto eol=lf

*.sh        text eol=lf
*.ps1       text eol=lf
Makefile    text eol=lf
*.mk        text eol=lf
*.bat       text eol=crlf
*.cmd       text eol=crlf

# Golden bytes and certificates are compared byte-for-byte: never normalize.
tests/golden/**        -text -diff
**/*.cert.json         -text
**/*.expected          -text
cas/**                 -text -diff filter=
*.tar.zst  binary
*.png      binary
*.wasm     binary

# Keep language statistics honest (see the polyglot audit section).
vendor/**              linguist-vendored
**/generated/**        linguist-generated
```

   Additional rules: `core.autocrlf` must be `false` (or `input`) in the WSL2 clone — Gate
   `G-WIN-003` (T0) reads `git config core.autocrlf` and refuses to build otherwise. Gate
   `G-WIN-004` (T1): `git ls-files --eol` reports `w/lf` for every text-classified file; a single
   CRLF in a golden file would change every downstream hash and silently invalidate certificates.
6. **Case-collision gate** `G-WIN-005` (T1): `git ls-files | sort -f | uniq -Di` must be empty.
   Two paths differing only in case are invisible on the author's host and fatal in CI.
7. **File mode gate** `G-WIN-006` (T1): the executable bit is tracked; scripts under `scripts/`
   must be `100755` in the index, everything else `100644`.
8. **Devcontainer** is the supported alternative to raw WSL2 and pins the same image as CI:

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "spectra-toolchain-a",
  "image": "spectra/toolchain-a@sha256:<digest from images.lock>",
  "runArgs": ["--cpus=6", "--memory=16g", "--network=none"],
  "containerEnv": { "TZ": "UTC", "LC_ALL": "C", "SPECTRA_DEVCONTAINER": "1" },
  "workspaceFolder": "/w",
  "postCreateCommand": "make doctor PROFILE=core",
  "customizations": { "vscode": { "extensions": [] } }   // no marketplace fetch at create time
}
```

   Note `--network=none` is the default posture even in the devcontainer; a developer who needs
   `make toolchain-refresh` runs it deliberately outside the container.

## 74.11 Negative requirements and forbidden claims

1. Do not add a CI step that installs anything from the network. If a job needs a tool, the tool
   goes in a tier image and `images.lock` changes in the same PR.
2. Do not use `latest`, `stable`, `nightly`, floating version ranges (`^`, `~`, `*`, `>=`), or an
   unpinned action reference (`uses: actions/checkout@v4` → pin to a commit SHA).
3. Do not run a gate "just once more" to get green. Do not add `|| true`. Do not lower an
   assertion to fit a budget; demote the gate to a slower tier instead, in the registry, in the diff.
4. Do not introduce a fifth toolchain image, a per-language image, or a language whose toolchain
   cannot be installed offline into one of the four images.
5. Do not let a sampled artifact back a docs sentence. Do not describe a T1 run as "the full
   matrix", "exhaustive", "all configurations" or "every cell".
6. Do not claim "reproducible build" on the basis of `build-offline` alone. `build-offline` proves
   the build needs no network from a clean clone with pinned inputs. Bit-identical binary
   reproducibility across toolchain versions is NOT established and must not be claimed; the
   byte-identity claim is about pipeline artifacts (bundles, certificates, plans), proven by the
   determinism gates, not about compiler output.
7. Do not claim the platform builds on Windows natively, on macOS, or on `linux/arm64`. The
   supported set is: Linux `amd64`, and Windows 11 via WSL2 or the devcontainer. Say exactly that.
8. Do not claim CI "runs every gate on every push". The tier table is the truth and README must
   render it from `ci/gates.toml` rather than describing it in prose.
9. Do not report CI minute figures, image sizes or job durations in README or docs unless they come
   from the T3 budget artifact with its run manifest hash; every such number carries its source id.
10. Do not treat a quarantined test as a passing test in any status table, badge or milestone claim.
