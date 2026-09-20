################################################################################
# SPECTRA -- root Makefile
#
# This file is the single entry point. There is never a second documented way to
# do the same thing (Part I section 33.1).
#
# SESSION ONE STATUS: skeleton only. Four targets do real work today -- help,
# doctor, skeleton-verify and guard-sandbox. Every other target is DECLARED so
# that this file reads as a map of the project, and every one of them exits
# NON-ZERO with the spec section that owns it, what it will do, and the
# milestone that implements it. No target ever exits 0 having done nothing.
#
# Two documents govern this file:
#   Part I  section 32  repository layout
#   Part I  section 33  build system and toolchain
#   Part I  section 52  build order and milestones
#   Part II section 74  offline build, toolchain matrix, CI budget, Windows
# Part II OVERRIDES Part I wherever they conflict. Overrides are marked inline.
#
# Nothing in this file measures anything, claims anything, or reports a status
# other than "not started" for work that has not started.
################################################################################

# ---------------------------------------------------------------------------
# Make and shell settings (Part I section 33.2)
# ---------------------------------------------------------------------------
SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -euo pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS     += --warn-undefined-variables --no-builtin-rules --no-builtin-variables
.SUFFIXES:
.DELETE_ON_ERROR:

# ---------------------------------------------------------------------------
# Sandbox guard (Part II section 74.10.3) -- evaluated before any target runs
# ---------------------------------------------------------------------------
# OVERRIDES Part I: no make target is supported on Windows cmd.exe or PowerShell.
# Every target runs inside WSL2, the devcontainer, or CI on Linux.
#
# TODO(decision: guard location) Section 74.10.3 specifies this guard as
# `ci/guard.mk`, included before any other target. It is inline here because
# ci/ does not exist yet. To change: create ci/guard.mk with this block verbatim
# and replace it here with `include ci/guard.mk`.

CI                   ?=
SPECTRA_DEVCONTAINER ?=

UNAME_S := $(shell uname -s 2>/dev/null)
IS_WSL  := $(shell grep -qi microsoft /proc/version 2>/dev/null && echo 1)

ifneq ($(UNAME_S),Linux)
  $(error SPECTRA targets run on Linux only. Detected "$(UNAME_S)". From Windows 11: open WSL2 (wsl -d <distro>) or the devcontainer and re-run there. PowerShell and cmd.exe are not supported and will not be.)
endif

ifeq ($(or $(IS_WSL),$(SPECTRA_DEVCONTAINER),$(CI)),)
  $(error not running in WSL2, the devcontainer or CI. Set SPECTRA_DEVCONTAINER=1 only from inside the container image. See docs/dev/wsl.md.)
endif

ifneq ($(filter /mnt/%,$(CURDIR)),)
  $(error repo is on a Windows drive mount ($(CURDIR)). Working from /mnt/c gives case-insensitive path collisions, wrong file modes and slow I/O, all of which corrupt the determinism gates. Clone into the WSL2 filesystem instead, for example ~/src/spectra. Gate G-WIN-001.)
endif

# ---------------------------------------------------------------------------
# Determinism environment (Part I section 33.5, Part II section 74.3)
# ---------------------------------------------------------------------------
export TZ     := UTC
export LC_ALL := C
export LANG   := C

# Derived from the committed history, never from the wall clock. Falls back to
# the epoch so a shallow or absent git dir cannot inject a varying value.
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || echo 0)
export SOURCE_DATE_EPOCH

# ---------------------------------------------------------------------------
# Repository variables
# ---------------------------------------------------------------------------
REPO   := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMMON := scripts/lib/common.sh

# Host resource profile (Part II section 74.10.4): core | matrix | range.
# OVERRIDES Part I section 33.2, where PROFILE named a *config* profile. Part II
# gives PROFILE to the host sizing profile, so the config profile is renamed.
# TODO(decision: PROFILE collision) If the config profile should keep the short
# name, swap these two variables and update docs/configuration.md in the same
# commit. Do not let two things be called PROFILE.
PROFILE        ?= core
CONFIG_PROFILE ?= dev

SEED         ?= 1337
SCENARIO     ?= s01_token_theft
COMPLETENESS ?= 100
JOBS         ?= $(shell nproc 2>/dev/null || echo 1)

# Digest-pinned tier images (Part II section 74.1). Deliberately empty: there is
# no images.lock yet, and a placeholder digest here would be a fabricated pin.
# Every target that needs one is not implemented, so nothing reads these.
# TODO(decision: image digests) Populate from images.lock once
# `make toolchain-refresh` has been run for the first time and its diff reviewed.
TOOLCHAIN_A_DIGEST ?=
TOOLCHAIN_B_DIGEST ?=
TOOLCHAIN_C_DIGEST ?=
TOOLCHAIN_D_DIGEST ?=

# Container re-entrancy (Part I section 33.2) is DELIBERATELY ABSENT.
# Section 33.2 wraps every target in a `docker run ... $(BUILDER_IMAGE)` when the
# toolchain is not present natively. Section 74.1 OVERRIDES the single builder
# image with four digest-pinned tier images, and there is no images.lock yet, so
# any wrapper written here would reference an image that does not exist and would
# fail with a Docker error instead of a stated reason. It is therefore not
# written. Every target runs natively today; `make doctor` says what is missing.
# TODO(decision: re-entrancy wrapper) Add the wrapper once images.lock exists.
# It belongs next to the guard, keyed on SPECTRA_IN_CONTAINER and the tier the
# target needs, and the tier per target belongs in ci/gates.toml, not here.

# ---------------------------------------------------------------------------
# The single shared not-implemented macro
# ---------------------------------------------------------------------------
# $(call todo,<spec section>,<what it will do>,<milestone>)
#
# Prints the owning spec section, the promised behaviour and the implementing
# milestone, then exits 1. There is no variant of this that exits 0, and there
# must never be one. Descriptions must not contain commas: make would split them
# into extra arguments.
define todo
@. "$(COMMON)"; spectra_not_implemented "$@" "$(1)" "$(2)" "$(3)"
endef

# ---------------------------------------------------------------------------
# Target vocabulary
# ---------------------------------------------------------------------------
# NOTE ON COMPLETENESS: this declares the target vocabulary of Part I sections
# 33 and 52 and Part II section 74. It is NOT the final set. Part II section
# 74.4 makes `ci/gates.toml` the only place a gate may be declared, and gate
# G-REG-001 asserts that every `make_target` named by a gate exists here. The
# remaining per-gate targets are added when that registry is written; until it
# exists, this file must not pretend to be the whole map.

.PHONY: \
  help doctor skeleton-verify guard-sandbox \
  bootstrap setup builder toolchain-refresh lint-images build-offline core \
  clean status anti-slop ci-budget ci-local m0-verify \
  lint fmt fmt-check typecheck security-test test test-all claims-check \
  test-t0 test-t1 test-t2 test-t3 \
  gen-data m1-verify \
  ingest m2-verify \
  dev reconstruct replay scenario demo-slice m3-verify \
  native m4-verify \
  m5-verify \
  m6-verify \
  bench-degrade gate-false-robust m7-verify \
  wasm m8-verify \
  lab lab-down polyglot polyglot-audit polyglot-report benchmark m9-verify \
  docs demo reproduce verify-no-llm release-check m10-verify

##@ Works today (session one)

help: ## Print this grouped target map
	@printf 'SPECTRA -- make target map\n'
	@printf 'Repository: %s\n' "$(REPO)"
	@printf '\n'
	@printf 'Session one is a skeleton. Only the targets under "Works today" are\n'
	@printf 'implemented. Every other target below exits 1 and names the spec\n'
	@printf 'section that owns it and the milestone that will build it.\n'
	@awk 'BEGIN { FS = ":[^#]*## " } \
	  /^##@ / { printf "\n%s\n", substr($$0, 5); next } \
	  /^[a-zA-Z0-9][a-zA-Z0-9._-]*:[^=]*## / { printf "  %-20s %s\n", $$1, $$2 }' \
	  $(MAKEFILE_LIST)
	@printf '\n'
	@printf 'CI tiers (Part II section 74.4) -- the registry in ci/gates.toml is the\n'
	@printf 'truth; this is a reminder of what each tier means:\n'
	@printf '  T0  pre-commit hook   local only        never authoritative\n'
	@printf '  T1  every push and PR merge blocked on failure\n'
	@printf '  T2  nightly on main   milestone loses green on failure\n'
	@printf '  T3  weekly on main    release blocked on failure\n'
	@printf '\n'
	@printf 'Variables: PROFILE=%s CONFIG_PROFILE=%s SEED=%s SCENARIO=%s COMPLETENESS=%s JOBS=%s\n' \
	  "$(PROFILE)" "$(CONFIG_PROFILE)" "$(SEED)" "$(SCENARIO)" "$(COMPLETENESS)" "$(JOBS)"

guard-sandbox: ## Assert the sandbox guard passed (WSL2 / devcontainer / CI on Linux)
	@. "$(COMMON)"; \
	  spectra_log "sandbox=$$(spectra_host_sandbox) cwd=$(CURDIR) ok"

doctor: ## Report which toolchains are present; non-zero if a Tier A toolchain is missing
	@. "$(COMMON)"; \
	  spectra_rule; \
	  printf 'SPECTRA doctor\n'; \
	  spectra_rule; \
	  printf '  sandbox        %s\n' "$$(spectra_host_sandbox)"; \
	  printf '  repo           %s\n' "$(CURDIR)"; \
	  printf '  TZ / LC_ALL    %s / %s\n' "$$TZ" "$$LC_ALL"; \
	  printf '  cpus           %s\n' "$$(spectra_host_cpus)"; \
	  printf '  memtotal_kb    %s\n' "$$(spectra_host_mem_kb)"; \
	  printf '  disk free      %s\n' "$$(spectra_host_disk_free .)"; \
	  printf '  host profile   %s (requested)\n' "$(PROFILE)"; \
	  printf '\n'; \
	  printf 'Tier A toolchains (Part II section 74.1 -- image spectra/toolchain-a).\n'; \
	  printf 'A missing entry here fails this target.\n'; \
	  missing=0; \
	  spectra_probe "bash"    bash                 || missing=$$((missing+1)); \
	  spectra_probe "make"    make                 || missing=$$((missing+1)); \
	  spectra_probe "git"     git                  || missing=$$((missing+1)); \
	  spectra_probe "jq"      jq                   || missing=$$((missing+1)); \
	  spectra_probe "b3sum"   b3sum                || missing=$$((missing+1)); \
	  spectra_probe "python"  python3              || missing=$$((missing+1)); \
	  spectra_probe "rustc"   rustc                || missing=$$((missing+1)); \
	  spectra_probe "cargo"   cargo                || missing=$$((missing+1)); \
	  spectra_probe "go"      go version           || missing=$$((missing+1)); \
	  spectra_probe "node"    node                 || missing=$$((missing+1)); \
	  spectra_probe "pnpm"    pnpm                 || missing=$$((missing+1)); \
	  spectra_probe "psql"    psql                 || missing=$$((missing+1)); \
	  printf '\n'; \
	  printf 'Tier B / C / D toolchains: not probed. Their directories are not started\n'; \
	  printf 'and images spectra/toolchain-{b,c,d} are not built (section 74.1).\n'; \
	  printf '\n'; \
	  printf 'NOT CHECKED by this target yet:\n'; \
	  printf '  * version pins        .tool-versions does not exist (section 33.6)\n'; \
	  printf '  * image digests       images.lock does not exist (section 74.1)\n'; \
	  printf '  * host sizing         profile minimums are undeclared (section 74.10.4)\n'; \
	  printf 'Presence is all this target asserts. It does not assert a version matches\n'; \
	  printf 'a pin, because there is no pin file to compare against.\n'; \
	  spectra_rule; \
	  if [ "$$missing" -ne 0 ]; then \
	    spectra_err "doctor: $$missing Tier A toolchain(s) missing"; \
	    spectra_err "install them inside WSL2 or use the devcontainer; do not install a second copy on the Windows host"; \
	    exit 1; \
	  fi; \
	  spectra_log "doctor: all probed Tier A toolchains present"

skeleton-verify: ## Check the session-one repo layout and required root files exist
	@. "$(COMMON)"; \
	  spectra_rule; \
	  printf 'SPECTRA skeleton-verify\n'; \
	  printf 'Existence only. This target does not read file contents and makes no\n'; \
	  printf 'claim that anything it finds is correct or complete. It is a layout\n'; \
	  printf 'check for session one; the real M0 gate is `make m0-verify` (section\n'; \
	  printf '52.3) and that is not implemented.\n'; \
	  spectra_rule; \
	  bad=0; \
	  printf 'Required directories (Part I section 32.2)\n'; \
	  for d in $(SKELETON_DIRS); do spectra_require_dir "$$d" || bad=$$((bad+1)); done; \
	  printf '\n'; \
	  printf 'Required root files (KICKOFF section 4 skeleton deliverable)\n'; \
	  for f in $(SKELETON_FILES); do spectra_require_file "$$f" || bad=$$((bad+1)); done; \
	  printf '\n'; \
	  printf 'Owed by a later milestone -- reported only. Absence here is not a failure.\n'; \
	  spectra_note_owed "ci/gates.toml"      "M0 (section 74.4)"; \
	  spectra_note_owed "ci/guard.mk"        "M0 (section 74.10.3)"; \
	  spectra_note_owed "ci/budget.toml"     "M0 (section 74.9)"; \
	  spectra_note_owed "ci/quarantine.toml" "M0 (section 74.8)"; \
	  spectra_note_owed "images.lock"        "M0 (section 74.1)"; \
	  spectra_note_owed "toolchains.lock"    "M0 (section 74.2)"; \
	  spectra_note_owed "mpc.toml"           "M0 (minimum publishable core)"; \
	  spectra_note_owed "polyglot.toml"      "M9 (section 73.5)"; \
	  spectra_note_owed "data/fixtures"      "M1 (section 32.2)"; \
	  spectra_note_owed "data/golden"        "M1 (section 32.2)"; \
	  spectra_note_owed "polyglot"           "M9 (section 32.2 -- directory name unresolved)"; \
	  spectra_rule; \
	  if [ "$$bad" -ne 0 ]; then \
	    spectra_err "skeleton-verify: $$bad required path(s) missing"; \
	    exit 1; \
	  fi; \
	  spectra_log "skeleton-verify: layout ok"; \
	  spectra_log "this says the skeleton exists. It says nothing about whether anything works."

# The layout skeleton-verify asserts. Kept as data so the list is editable without
# touching a recipe.
#
# TODO(decision: directory layout) These paths track Part I section 32.2, amended
# by Part II section 73.10, which bans the proof kernel's internal acronym from
# every directory name -- the docs subdirectory section 32.2 named after it is
# therefore docs/kernel/ here.
# docs/plan/PLAN_v1.md proposes a different roster (db/ for sql/, frontend/ for
# web/, analysis/ for the Tier D languages) and that conflict is open. When it is
# resolved, edit these two lists and nothing else in this file.
#
# Tier B / C / D package roots are deliberately absent: session one gives them a
# directory with a README stating the tier and "not started", and those READMEs
# are not part of the required set until their tier begins.
SKELETON_DIRS := \
  .devcontainer \
  .github/workflows \
  config \
  docker \
  docs \
  docs/adr \
  docs/dev \
  docs/kernel \
  docs/plan \
  docs/prompt \
  docs/research \
  bench \
  lab \
  go \
  python \
  rust \
  scripts \
  scripts/lib \
  sql \
  tests \
  tools \
  web

SKELETON_FILES := \
  Makefile \
  LICENSE \
  README.md \
  SECURITY.md \
  LIMITATIONS.md \
  BUILD_LOG.md \
  WAIVER.md \
  .editorconfig \
  .gitattributes \
  .gitignore \
  .dockerignore \
  .env.example \
  scripts/lib/common.sh \
  docs/claims.md \
  docs/plan/PLAN_v1.md \
  docs/research/preregistration.md

##@ M0 -- Skeleton and toolchain (section 52.3) -- tier T1 unless noted

bootstrap: ## Install nothing outside the repo and the container images
	$(call todo,52.3,pull the digest-pinned tier images and prepare the repo-local caches; installs nothing on the host,M0)

setup: ## Restore every ecosystem from its committed lockfile without modifying it
	$(call todo,33.3,restore cargo go uv pnpm and the JVM/.NET/Haskell caches from committed lockfiles; CI asserts git diff --exit-code afterwards,M0)

builder: ## SUPERSEDED single builder image -- see toolchain-refresh
	@. "$(COMMON)"; \
	  spectra_warn "section 74.1 OVERRIDES section 33.3: there is no single builder image."; \
	  spectra_warn "four digest-pinned tier images exist instead: toolchain-a through toolchain-d."; \
	  spectra_warn "use 'make toolchain-refresh' to build them and 'make lint-images' to check pins."; \
	  spectra_not_implemented "$@" "74.1" "nothing -- this target is retained only so the override is discoverable from the build system" "never"

toolchain-refresh: ## THE ONLY NETWORK-PERMITTED TARGET -- rebuild toolchains.lock and images.lock
	$(call todo,74.1,resolve and lock every ecosystem; fetch the vendor bundles; build the four tier images from digest-pinned bases; export OCI tarballs to cas/oci/ and record digests in images.lock,M0)

lint-images: ## Assert every image reference resolves to a digest in images.lock
	$(call todo,74.0,fail any FROM / docker run / devcontainer / CI container reference that is pinned by tag rather than by sha256 digest -- gates G-IMG-001 and G-IMG-002,M0)

build-offline: ## Clean clone built with --network=none -- the offline claim (G-OFF-001)
	$(call todo,74.3,clone the repo from file:// into a scratch dir; build and run the T1 tier inside toolchain-a with --network=none and a tmpfs HOME; assert the egress sentinel counted zero packets,M0)

core: ## Build the core the offline gate runs inside the container
	$(call todo,74.3,build the Tier A artifacts that `make build-offline` then tests; invoked as `make -C /w core` inside the container,M0)

clean: ## Remove build outputs and generated data; keeps caches unless DEEP=1
	$(call todo,33.3,remove build outputs and data/generated and data/runs until git status --porcelain is empty; keep the ecosystem caches unless DEEP=1,M0)

status: ## Regenerate docs/STATUS.md from real CI artifacts -- never hand-edited
	$(call todo,52.1,generate one row per milestone in docs/STATUS.md from the committed CI ledger; refuse to emit a row for which no artifact exists,M0)

anti-slop: ## The pre-milestone honesty gate (section 56.1)
	$(call todo,56.1,run the anti-slop table -- stub scan; fabricated-number scan; banned-phrase gate; skipped-test count -- and fail the milestone on a single FAIL row,M0)

ci-budget: ## Sum declared gate budgets per tier and compare to the declared ceiling
	$(call todo,74.9,read ci/gates.toml and ci/budget.toml; print jobs and summed budget_s and headroom per tier; fail when a tier exceeds its ceiling -- gate G-BUDGET-001,M0)

ci-local: ## Run exactly what CI runs, in CI order
	$(call todo,33.3,run setup lint fmt-check typecheck test-all security-test bench-degrade docs and exit with the same code CI would on this commit,M0)

m0-verify: ## M0 proof target -- toolchain versions plus the compose health table
	$(call todo,52.3,print every toolchain version and the compose health table and the offline-build result then print M0 OK; exit non-zero on any failure,M0)

##@ Quality gates -- grow with every milestone (section 33.3)

lint: ## All linters across all languages; zero findings; suppressions need a justification
	$(call todo,33.3,run ruff and clippy -D warnings and go vet and staticcheck and eslint and shellcheck and hadolint and the tools/lint/* checks; fail on any finding,M0)

fmt: ## Rewrite files to canonical format
	$(call todo,33.3,run the canonical formatter for every language in the tree,M0)

fmt-check: ## Assert the tree is already canonically formatted
	$(call todo,33.3,run the formatters and fail when git diff --exit-code is non-empty,M0)

typecheck: ## Static types across all languages; zero errors; warnings are errors
	$(call todo,33.3,run mypy --strict and tsc --noEmit and cargo check --all-targets and go build ./... and fail on any error,M0)

security-test: ## Dependency and secret scanning; no high or critical findings
	$(call todo,33.3,run bandit cargo-audit cargo-deny govulncheck pnpm audit trivy gitleaks and semgrep; emit SARIF; fail on high or critical or any leaked secret,M0)

test: ## Fast suites -- unit and property; no Docker lab; no network
	$(call todo,33.3,run the unit and property suites for every language that exists and emit junit xml per language; must not require the lab or the network or a GPU,M0)

test-all: ## test plus gates plus conformance plus end-to-end plus lab integration
	$(call todo,33.3,run test then every registered gate then the cross-language conformance suite then the end-to-end and lab integration suites,M0)

claims-check: ## Every externally visible claim resolves to a committed artifact
	$(call todo,71,check that every row in docs/claims.md binds to a committed artifact and a gate id and that no numeral in README or docs lacks a source id,M0)

##@ CI tiers (section 74.4) -- the registry in ci/gates.toml is the only truth

test-t0: ## T0 -- pre-commit tier; local only; never authoritative
	$(call todo,74.4,run every gate whose tier is T0 in ci/gates.toml,M0)

test-t1: ## T1 -- every push and PR; a failure blocks the merge
	$(call todo,74.4,run every gate whose tier is T1 in ci/gates.toml and fail the job on the first red gate,M0)

test-t2: ## T2 -- nightly on main; a failure costs the milestone its green
	$(call todo,74.4,run every gate whose tier is T2 in ci/gates.toml,M0)

test-t3: ## T3 -- weekly on main; a failure blocks the release
	$(call todo,74.4,run every gate whose tier is T3 in ci/gates.toml,M0)

##@ M1 -- Generator and ground truth (section 52.4)

gen-data: ## Seeded synthetic telemetry for SEED SCENARIO COMPLETENESS
	$(call todo,33.3,emit data/generated/<scenario>/<seed>/<completeness>/ containing bundle.jsonl and manifest.json and ground_truth.json; two runs with the same inputs must be byte-identical,M1)

m1-verify: ## M1 proof target -- hash triple-run equality and truth isolation
	$(call todo,52.4,assert three runs at one seed are byte-identical and that no ingest or kernel code can import ground_truth and that every scenario validates against its schema,M1)

##@ M2 -- Ingest entity resolution and event store (section 52.5)

ingest: ## Parse normalize resolve entities verify hash chains and load Postgres
	$(call todo,33.3,parse and normalize every record or quarantine it with a reason code; resolve entities deterministically; verify the BLAKE3 chains; load Postgres; emit ingest_report.json with zero silent drops,M2)

m2-verify: ## M2 proof target -- stable EventIds and no wall-clock in any id
	$(call todo,52.5,assert re-ingesting one bundle yields an identical EventId set and that the no-nondeterminism lint finds no clock or random or hostname input to any id,M2)

##@ M3 -- Vertical slice (section 52.2) -- frozen once green

dev: ## Bring up the core stack with hot reload for api and web
	$(call todo,33.3,docker compose up the core stack from docker/compose.core.yml with hot reload until GET /healthz returns 200 and the web dev server responds,M3)

reconstruct: ## Liveness then grounding then the silent envelope
	$(call todo,33.3,run stages A through C and emit liveness.json and hypergraph.bin and recon_report.json with the grounding size published rather than capped silently,M3)

replay: ## Run the concrete simulator for one control configuration
	$(call todo,33.3,run the simulator for a given control configuration and emit replay.json with per-step terminations that must agree with the kernel on the same configuration,M3)

scenario: ## End to end -- gen-data then ingest then reconstruct then prove then verify
	$(call todo,33.3,run the full pipeline for SCENARIO and SEED and emit data/runs/<run_id>/cert.json that `spectra verify` accepts and whose verdict matches ground_truth.json,M3)

demo-slice: ## The thin vertical slice; runs in every later milestone verify target
	$(call todo,52.1,run generate through ingest through reconstruct through replay and assert the result is visible in the UI; nothing after M3 may break this,M3)

m3-verify: ## M3 proof target -- the vertical slice is alive
	$(call todo,52.2,run demo-slice from a clean clone and assert every stage produced its declared artifact,M3)

##@ M4 -- Liveness licenses silent envelope and fixpoint (section 52.2)

native: ## Build and test the C / C++ / assembly hot paths
	$(call todo,33.3,configure and build the CMake presets under native/ and run ctest; the assembly and portable C paths must produce identical output on random vectors,M4)

m4-verify: ## M4 proof target -- kernel stages A through D
	$(call todo,52.2,assert liveness and licenses and the silent envelope and the fixpoint agree with the reference oracle on every fixture; delivers no cut and no certificate,M4)

##@ M5 -- Two-sided cut and the certificate (section 52.2)

m5-verify: ## M5 proof target -- the certificate object exists and is self-consistent
	$(call todo,52.2,assert the two-sided cut and the certificate validate against their schema; until M6 lands a certificate is self-attested and must be described that way,M5)

##@ M6 -- Independent checker and differential gates (section 52.2)

m6-verify: ## M6 proof target -- a checker sharing no code with the solver accepts the certificate
	$(call todo,52.2,assert the Go checker re-validates every certificate in one linear pass and shares no code or generated artifact or dependency with the Rust workspace,M6)

##@ M7 -- Degradation tampering and the matrix (section 52.2)

bench-degrade: ## The completeness matrix across scenarios and seeds
	$(call todo,33.3,run the completeness matrix across every scenario and seed and emit degradation.json; zero false ROBUST verdicts is the invariant that may never be relaxed,M7)

gate-false-robust: ## G-KERNEL-FALSE-ROBUST -- zero false ROBUST on declared suppression classes
	$(call todo,74.4,run the sampled false-ROBUST matrix declared in ci/gates.toml and emit false-robust-matrix.json; soundness gate -- non-quarantinable,M7)

m7-verify: ## M7 proof target -- degradation and tampering
	$(call todo,52.2,assert the degradation matrix is complete for its declared cells and that no cell reported ROBUST while a soundness-affecting flag was set,M7)

##@ M8 -- Full UI and PROVE flow (section 52.2)

wasm: ## Build the kernel to wasm32-unknown-unknown for the browser
	$(call todo,33.3,build rust/spectra-wasm to wasm32-unknown-unknown and run wasm-opt -Oz and copy the artifact into the web workspace; two consecutive builds must be byte-identical,M8)

m8-verify: ## M8 proof target -- the four screens and the PROVE flow
	$(call todo,52.2,assert every displayed number traces to an API field and that no component fabricates a verdict or count or hash,M8)

##@ M9 -- Polyglot surface and measured performance (section 52.2)

lab: ## Bring up the isolated lab from lab/topology.hcl
	$(call todo,33.3,start every lab node on an isolated network with no egress and assert docker network inspect shows no default-bridge attachment,M9)

lab-down: ## Tear down the lab including its volumes and network
	$(call todo,33.3,stop and remove every container and volume and network labelled spectra.lab until docker ps for that label is empty,M9)

polyglot: ## Build and test every polyglot component; SKIPPED is printed never implied
	$(call todo,33.3,build and test every component under the polyglot roster and print an explicit SKIPPED line with a reason for any absent SDK; the SKIPPED count must be zero inside the tier images,M9)

polyglot-audit: ## Per language -- a CI job a consumer edge and a mutation that turns a gate red
	$(call todo,73.5,assert every executing source file is owned by exactly one polyglot.toml component and that each component has a recorded mutation run whose named gate went red; a PADDING verdict deletes the language,M9)

polyglot-report: ## Emit the language table the README renders
	$(call todo,73.5,emit artifacts/polyglot/audit.json and the generated language table; no prose may state a language count derived from anything else,M9)

benchmark: ## Run bench/definitions with the declared repeats -- T3 only
	$(call todo,33.3,run every benchmark definition with its declared repeats and emit results that validate against bench/results.schema.json; no other target may produce a benchmark number,M9)

m9-verify: ## M9 proof target -- the polyglot surface is honest and measured
	$(call todo,52.2,assert polyglot-audit reports zero padding and that every performance claim in docs traces to a committed benchmark result,M9)

##@ M10 -- Docs demo and release (section 52.2)

docs: ## Build the docs site and the paper from real results only
	$(call todo,33.3,build the mkdocs site and render the diagrams and build the paper; fail when any figure sources a file absent from bench/results/,M10)

demo: ## The scripted demo path; every byte on screen is hash-checked
	$(call todo,33.3,run the scripted demo -- seeded data then prove then unset a control then re-prove then the blindness beat -- and assert the transcript matches its committed expectation,M10)

reproduce: ## Regenerate every number in the docs from a clean clone with the network off
	$(call todo,74.4,regenerate every docs number and figure from a clean offline clone and fail when any regenerated value differs from the committed one,M10)

verify-no-llm: ## Assert every gate benchmark and number stays green with the model absent
	$(call todo,72,run the full gate set with the narration model and its dependency removed and assert nothing changes; the narrator never produces a number or probability or severity,M10)

release-check: ## The release gate -- M10 proof target
	$(call todo,52.2,assert every milestone is green and every claim is bound to an artifact and no quarantine entry or waiver is open and the demo transcript still matches,M10)

m10-verify: ## Not a target -- M10's proof target is release-check
	@. "$(COMMON)"; \
	  spectra_warn "section 33.9 forbids a target that is only an alias for another target."; \
	  spectra_warn "M10's proof target is 'make release-check' (section 52.2)."; \
	  spectra_not_implemented "$@" "52.2" "nothing -- use release-check; this target exists only so the M0..M10 naming is not silently incomplete" "never"
