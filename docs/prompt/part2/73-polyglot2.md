============================================================
73. POLYGLOT TIERS, LOAD-BEARING TEST AND THE MUTATION AUDIT
============================================================

73.0 Purpose and standing requirement

The large polyglot surface stays. It is not deleted, not quietly shrunk, and not apologised for.
What changes is that it stops being a claim in a markdown table and becomes a property that a make
target can refute. Every language in this repository must be load-bearing: something downstream must
break when it is corrupted. A language that cannot fail this way is padding and is deleted in the
same commit that discovers it.

OVERRIDES Part I: §30.1's enforcement mechanism (a written non-duplication rationale per language in
`docs/polyglot-rationale.md`) is replaced by the executable audit in §73.4. Prose rationale is
demoted to explanatory commentary and may no longer be cited as satisfying any gate. `make
polyglot-audit` is now the only thing that licenses a language to remain in the tree.

OVERRIDES Part I: §32.1's rule "a directory that could be deleted with no loss must not exist" is
restated as a mechanical predicate (§73.3) rather than a judgement call.

OVERRIDES Part I: §43.1's requirement that every polyglot language carry its own unit tier gated on
every push is replaced by the tiered CI schedule in §73.6. Per-language unit tiers still exist; they
no longer all run per-push.

73.1 The roster and the honest count

The repository contains exactly two kinds of files that GitHub Linguist will colour: **authored
executing languages** and **configuration/markup formats**. They are counted separately, always, in
every document and every interface.

Authored executing languages: 32. Configuration and markup formats: 11. Linguist language-bar rows:
43. The number 43 is the size of the colour bar and is never used in a prose sentence (§73.7).

OVERRIDES Part I section 30.6: the audit transcript line that prints `languages declared` as 43, and
§31.44's description of the Makefile as a dependency graph across 43 toolchains, are replaced by
three separately counted figures — 32 authored executing languages, 11 configuration formats, 43
Linguist bar rows — of which only the first may appear in a prose sentence. An implementer
reproducing §30.6's exact transcript shape emits the "43 languages" claim §73.11 forbids, over a set
that is not even this one (Part I's 43 counts JavaScript and MATLAB; this roster has neither).

TIER A — CRITICAL PATH (6). Promise: *this is the product*. Deleting any of these deletes SPECTRA.

| Language   | Component                                             | Consumer edge (what breaks)                    |
|------------|-------------------------------------------------------|------------------------------------------------|
| Rust       | ECLIPSE kernel, grounder, fixpoint, cut solver         | every certificate; `make prove` produces nothing|
| Go         | `spectra verify` independent checker                   | §62 oracle 2 disappears; all certs unvalidated  |
| Python     | generator, ingest orchestration, ER, API services      | no `bundle.jsonl`; nothing to ground            |
| TypeScript | frontend, proof UX, demo pane                          | `make demo` has no UI; Playwright tier empty    |
| SQL        | fact-base schema, recursive-CTE state view, migrations | run metadata and state view unresolvable        |
| Bash       | make targets' shell layer, range compose driver        | no reproducible entrypoints                     |

OVERRIDES Part I section 30.2: the four numbered tiers and their membership are replaced by the four
lettered tiers of this section, which assign different members — Bash moves from the observed lab to
the critical path; Java and C# move from observed subjects to oracle duty; Solidity, x86-64 assembly
and YARA leave the observed lab; WebAssembly drops from the hot path to a research artifact; and
JSON, YAML, TOML, XML and HCL leave the tier system entirely for §73.2. An implementer following
§30.2 applies its Tier 3 rule — never import SPECTRA libraries, never read the rule table, never
know they are being watched — to Bash, assembly, YARA and Solidity, which are no longer observed
subjects, and applies its Tier 2 agreement-gate obligation to a WebAssembly component that no longer
computes anything to agree about.

TIER B — INDEPENDENT ORACLES AND MEASURED PERFORMANCE (6). Promise: *each of these is consumed by a
gate or a published benchmark; none is a demonstration*. Tier B exists to make claims falsifiable,
not to make them impressive.

| Language      | Component                                                            | Promise stated exactly                                                                 |
|---------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| Haskell       | policy oracle: license admissibility relation + guard evaluator       | independently authored oracle for the license logic and guard semantics only            |
| C             | ingest hot path: record framing + field scanner                       | a *measured* alternative to the Rust scanner, published whether or not it wins           |
| C++           | deterministic entity-key interner used by the same hot path           | a *measured* alternative interner, published whether or not it wins                     |
| Java (JVM)    | token/identity service in the observed estate, dual-instrumented      | a genuinely observed service whose two instrumentation layers form a cross-source oracle|
| C# (.NET)     | resource/service host in the observed estate, dual-instrumented       | as above, on a second runtime                                                           |
| x86-64 asm    | syscall-trace fixture emitter                                        | byte-exact, hand-authored lowest-level observed source                                  |

Tier B negative requirement: the Haskell oracle implements the admissibility relation and guard
evaluation **only**. It must not implement semi-naive grounding, the fixpoint, the hitting-set loop
or the certificate format. If a Haskell module ever imports or reimplements grounding, the audit
fails with `TIER_B_SCOPE_CREEP`.

Tier B honesty requirement: the C and C++ components are justified by the existence of the
benchmark, not by its outcome. If the Rust scanner is faster, `docs/bench/ingest.md` says so, the C
and C++ components remain (they are the comparison arm), and no document anywhere claims a speedup.
Forbidden sentence: "we rewrote the hot path in C for speed."

OVERRIDES Part I section 31.7: the C component — a single-producer/single-consumer lock-free
shared-memory ring buffer plus a `ptrace`-based syscall tap, justified as a capability argument
("stable ABI and cache-line control: this is exactly what C is for") — is replaced by the record
framing and field scanner of the ingest hot path, justified solely by the existence of a published
benchmark against a Rust scanner. An implementer following §31.7 and §32.6's `c/libspectra_frame/`
builds a component with no Rust comparison arm, so the benchmark that licenses C to exist here
cannot be run at all.

OVERRIDES Part I section 31.8: the C++ component — offline pcap flow reassembly plus the interval
tree that computes the per-source liveness windows feeding `liveness.json` — is replaced by the
deterministic entity-key interner measured against a Rust interner on the same hot path. An
implementer following §31.8 and §32.6's `cpp/temporal_index/` builds pcap reassembly and an interval
index that no component in this roster owns or consumes, and no Rust interner exists to compare
against.

TIER C — HETEROGENEOUS OBSERVED ESTATE (11). Promise, stated exactly and narrowly:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

That is a real research property and Tier C is its evidence. It is therefore the tier with the
strictest emission requirement: every Tier C component must emit telemetry in its own idiomatic
format, that telemetry must be ingested in at least one committed scenario, and the ingest path must
contain no language-specific branch (§73.3.4).

| Language    | Estate component                        | Idiomatic emission                         |
|-------------|------------------------------------------|--------------------------------------------|
| PHP         | legacy self-service web app              | error_log + access log, no structure       |
| Ruby        | internal admin console                    | Rails-style tagged logger                  |
| Perl        | cron/rotation utility                     | plain syslog lines, no fields              |
| Lua         | OpenResty reverse proxy                   | nginx log_format directive output          |
| Kotlin      | API gateway                               | logback JSON encoder                       |
| Swift       | Linux-hosted session service              | swift-log structured output                |
| Objective-C | legacy agent (clang + GNUstep on Linux)   | NSLog-shaped lines, mixed encodings        |
| Dart        | desktop client issuing API calls          | client-side JSONL telemetry                |
| PowerShell  | admin host automation (pwsh on Linux)     | Windows-event-shaped JSON records          |
| Groovy      | build pipeline scripts                    | build/deploy events                        |
| Scala       | nightly batch reconciliation job          | log4j2 pattern layout                      |

OVERRIDES Part I sections 31.11, 31.14, 31.15, 31.19, 31.20, 31.23 and 32.6: Kotlin as an Android
session-telemetry fixture generator and typed scenario DSL, Scala as a streaming reconstruction
baseline used to quantify what batch reconstruction gains, Groovy as Gradle build logic plus the
scenario authoring DSL the demo scenario is written in, Perl as `tools/perl/logxlate/` translating
legacy formats into canonical NDJSON, Lua as user-supplied event transformers hosted by
`rust/spectra-normalize` through `mlua`, Dart as a certificate console that calls the verifier, and
Ruby as the attacker choreography runner are all replaced by observed estate services whose only job
is to emit idiomatic telemetry. An implementer following Part I puts Perl and Lua inside the ingest
path and lets Dart call the verifier, which §30.2's own Tier 3 rule, this tier's promise and the
§73.3.4 language-branch grep gate all forbid.

Tier C honesty clauses that must appear in `docs/polyglot/tier-c.md`:
1. PowerShell runs as `pwsh` on Linux. It emits Windows-event-*shaped* records. It is not Windows,
   and no document may imply a Windows endpoint was observed.
   OVERRIDES Part I section 31.34: PowerShell as the Windows-side developer bootstrap and as the
   collector wrapper that forwards the C# identity emitter's output into the ingest pipeline on
   Windows hosts, with Pester tests and the job `lang-powershell` on a `windows-latest` runner, is
   replaced by an observed admin-host component running as `pwsh` on Linux whose records the ingest
   path must not know are PowerShell's. An implementer following §31.34 turns an estate subject into
   a SPECTRA ingest tool and declares a `windows-latest` CI job that §73.9.3's single prebuilt Linux
   toolchain image cannot run.
2. Objective-C is compiled with clang against GNUstep on Linux. It is not an Apple platform agent
   and no document may imply macOS or iOS telemetry.
3. Swift is the open-source Linux toolchain. Same clause.
   OVERRIDES Part I sections 31.21, 31.22 and 32.6: Swift as an iOS session-telemetry fixture
   generator (app foreground/background transitions, jailbreak-check outcome, device-attestation
   result), Objective-C as `mobile/ios-keychain-shim/` emitting keychain-shaped events because the
   keychain APIs are Objective-C, and the `swift/macshim/` macOS endpoint shim with its
   `objc/macshim-compat/` CoreFoundation collection path, are replaced by Linux-hosted components
   built with the open-source Swift toolchain and with clang against GNUstep. An implementer
   following Part I ships components whose directory names and event vocabulary assert the macOS and
   iOS telemetry these clauses and §73.11 ban, before a single document is written.

Tier C load-bearing reinforcement — **the held-out language rule**: exactly one Tier C component is
authored *after* `rules.toml` and `axioms/` are frozen and hash-pinned (see §62's leakage protocol).
Its reconstruction quality is reported as a separate row in every results table, labelled
`HELD-OUT-LANGUAGE`. If reconstruction quality on the held-out language is materially worse than on
the tuned ones, that result is published, not suppressed. Which component is held out is recorded in
`docs/research/preregistration.md` before it is written.

TIER D — RESEARCH AND FORMAL ARTIFACTS (9). Promise: narrow, and stated narrowly each time.

| Language   | Artifact                                              | The narrow promise, in full                                                                                              |
|------------|-------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| R          | degradation-matrix statistics (median, IQR, bootstrap) | sole implementation of the published summary statistics; cross-checked against Julia                                     |
| Julia      | independent re-implementation of the same statistics   | disagreement beyond declared tolerance fails the build                                                                   |
| GNU Octave | inter-arrival quantile sensitivity (q95/q99/q999)      | sole implementation of the exact-rank quantile sweep; cross-checked against the Rust liveness quantile                    |
| F#         | Pareto frontier over the enumerated corridors          | independent implementation of the multiple-choice knapsack; must produce the identical frontier set as Rust              |
| Solidity   | offline EVM event-log source class                     | supplies the one estate source whose ordering guarantee is *intrinsic to the producer*, not granted by the lab harness    |
| Verilog    | bounded FIFO log sink, simulated                       | generates a loss trace with exact drop ground truth for the bounded-buffer degradation cell                               |
| VHDL       | independently authored same FIFO                       | differential partner for Verilog; divergent drop traces fail the build                                                    |
| WebAssembly| hand-authored `.wat` canonical-preimage encoder        | lets the browser re-derive a certificate's content address offline; it does **not** compute or verify any verdict         |
| YARA       | declarative labelling of generator artifact blobs      | sole pattern language for fixture technique labels used by the goal-correspondence test                                   |

OVERRIDES Part I sections 31.13 and 31.26: F# emitting the canonical `artifacts/state_table.json`
(states, legal transitions, guards, dimension tags) that Python's engine and the Rust kernel both
load rather than hard-coding, under a regeneration gate, and Julia performing the brute-force
minimum-cardinality hitting set over Ψ for `|A| ≤ 20` fixtures plus the cost sensitivity sweep, are
replaced by F# owning the multiple-choice knapsack Pareto frontier (which §31.26 gave to Julia) and
Julia owning an independent re-implementation of R's degradation statistics. An implementer
following §31.13 and §31.26 builds a state-table generator and a Ψ-minimality brute-forcer that no
component in this roster owns, while the F# and Julia promises declared above go unimplemented.

OVERRIDES Part I sections 31.25 and 32.6: Octave producing `artifacts/analysis/q99_thresholds.json`
for the liveness pass to consume, together with the periodicity and beaconing analysis by
autocorrelation and Welch PSD in `matlab/liveness_ref/`, is replaced by an exact-rank quantile
sensitivity sweep (q95/q99/q999) cross-checked downstream against the Rust liveness quantile. An
implementer following §31.25 wires the dependency edge backwards, making the Rust liveness pass a
consumer of Octave instead of its reference, which inverts both the §73.3.1 consumer edge and the
§73.3.3 mutation target for this component.

OVERRIDES Part I section 31.31: YARA matches becoming evidence events with stable `EventId`s that
feed rules whose bodies require file-content facts, and appearing as evidence leaves in the
counterexample tree, are replaced by declarative labelling of generator artifact blobs for the
goal-correspondence test only. An implementer following §31.31 makes the kernel ground over YARA
output and the demo display it, placing the counterexample tree behind a Tier D job that §73.9 rule
1 says does not block a milestone.

Tier D negative requirements:
- Solidity provides **no** security property that the BLAKE3 sequence chain does not already provide
  for SPECTRA's own artifacts. It is an estate source class, not a notary. `docs/polyglot/tier-d.md`
  states this in those words. Forbidden claims: "blockchain-anchored", "immutable audit anchor",
  "tamper-proof certificates". No SPECTRA certificate, hash or verdict is ever written to a chain.
  OVERRIDES Part I sections 31.27 and 32.6: Solidity as the control case of the tampering study —
  the one source where SUPPRESSED is provably impossible, demoed as "one blind window on
  `iam_audit`, zero possible blind windows on `chain_authz`" — and `solidity/anchor/`, the
  local-chain append-only certificate anchor registry, are replaced by an estate source class that
  anchors nothing. An implementer following Part I ships the certificate anchor registry this bullet
  says must not exist and a demo line the claims gate rejects as tamper-proofing.
- The Verilog/VHDL FIFOs model a lossy buffer. They do not model any real logging appliance and no
  document may name one.
  OVERRIDES Part I sections 31.28, 31.29 and 32.6: Verilog as the security state machine in
  synthesizable RTL (a Moore FSM with an `illegal_transition` output, `casez` generated from
  `state_table.json`, elaborated with `yosys -p synth` and gated on hw/sw illegal-transition
  agreement), VHDL as a hardware liveness monitor asserting `blind` on q99 inter-arrival overrun
  against a Rust differential oracle, and §32.6's RTL model of the unit-propagation counter
  datapath, are all replaced by a pair of independently authored simulated bounded FIFOs that
  produce drop ground truth. An implementer following Part I builds a synthesis step, a
  state-table-driven generator and a liveness differential oracle that no component in this roster
  owns, and describes the result in the RTL terms §73.11 forbids.
- The `.wat` module re-derives a content address. Part I's frontend invariant stands: the verdict is
  never computed client-side. A test asserts the `.wat` module exports exactly one function and that
  no frontend code path calls it with anything but the certificate preimage.
  OVERRIDES Part I sections 31.30, 31.4, 32.4 and 32.7: WebAssembly as the checking half of ECLIPSE
  compiled to `wasm32-unknown-unknown` — closure check, goal exclusion, license validation, witness
  re-derivation and Ψ minimality running entirely in the browser — built from the
  `eclipse-verifier-wasm`/`spectra-wasm` crates and `web/packages/wasm`, shipped as
  `web/public/eclipse_verifier.wasm`, loaded by the standalone `verify.html` to verify a certificate
  from `file://`, under a size budget and a three-way wasm/Rust/Go verdict agreement gate, is
  replaced by a hand-authored `.wat` preimage encoder that computes no verdict and exports exactly
  one function. The "frontend invariant" this bullet preserves is §32.7's rule for the React console
  only; an implementer following §31.30 and §31.4 ships a client-side verifier and the demo's final
  offline-verify beat, and a compiled wasm artifact that this section excludes from the roster
  entirely.
- Rust-to-wasm and any other compiled output is a **build target, not an authored language**. It is
  excluded from the roster, excluded from the count, and marked `linguist-generated=true`.

MATLAB — stated honestly, once, in the section that owns it:

> MATLAB is not present. MATLAB requires a licence and a licence server, which cannot satisfy the
> offline, unlicensed, clean-clone-builds-with-the-network-off constraint. SPECTRA uses **GNU
> Octave**. The numerical code in `octave/` is written for Octave, executed by Octave in CI, and has
> never been executed by MATLAB. Documentation, the README, the language table and any paper say
> "GNU Octave". Saying or implying "MATLAB" anywhere in this repository is a banned phrase enforced
> by the claims gate; `make polyglot-audit` fails with `BANNED_MATLAB_MENTION` on any match of
> `/\bMATLAB\b/i` outside this paragraph's own file.

OVERRIDES Part I: the target language set's inclusion of MATLAB is deleted and replaced by GNU
Octave, with the non-equivalence stated rather than glossed.

73.2 Configuration and markup formats (11)

JSON, YAML, TOML, XML, HTML, CSS, SCSS, Dockerfile, Makefile, CMake, HCL.

These are configuration and markup. They are real, they are load-bearing, and they are **not
languages doing a job** for counting purposes. They may appear in the Linguist bar. They may never be
counted in a prose sentence of the form "N languages". A build that counts any of them into the
prose figure fails with `COUNT_CONTAMINATED`.

73.3 THE LOAD-BEARING TEST

Every component in the roster must declare, and the audit must verify, all four of the following.
Three is a failure.

73.3.1 **Consumer edge.** A named downstream artifact that consumes this component's output, owned by
a different component. Self-consumption is forbidden: a component whose only consumer is its own test
suite fails with `SELF_CONSUMING`.

73.3.2 **CI job.** A named job in `.github/workflows/*.yml` that executes the component (not merely
lints or builds it) on every change to its paths, at the cadence its tier permits (§73.6).

OVERRIDES Part I section 30.4.3: the `weak_exercise` allowance — compile-only CI jobs declared as
such in `languages.toml`, with the audit failing only when more than three exist, and §30.6's
transcript printing `weak_exercise` as 2 / 3 allowed — is replaced by an unconditional requirement
that the declared job execute the component. An implementer following §30.4.3 keeps up to three
build-only components that this check marks PADDING and §73.6 then deletes.

73.3.3 **Mutation.** A declared, deterministic corruption of the component's *output* which, when
applied, turns a named downstream gate RED. The audit applies the mutation in a scratch worktree and
records the job name and the failing assertion. A component whose mutation leaves every gate green is
padding and is deleted.

OVERRIDES Part I section 30.3.3: the mutation test that injects a known deviation into the core so
that a `differential_oracle` fails, stored as `tests/mutation/<oracle>/mut_XX.patch` with expected
exit codes, is replaced by a seeded corruption of the component's own output, drawn from the closed
operator set of §73.5 and declared as `mutation.op`, `seed` and `expect_red` in `polyglot.toml`. An
implementer following §30.3.3 writes the core patches named in §31.4, §31.6, §31.16, §31.26 and
§31.29 — canonicalizer, kernel, blind interval, licensing, popcount ordering, interval endpoint —
for which no operator in §73.5 and no field in §73.4 provides an encoding, so those gates cannot be
declared here at all.

73.3.4 **Demo or benchmark role.** A one-line statement of what this component does in `make demo`,
in the degradation matrix, or in a published benchmark. Tier D components may declare
`role = "none"` only if they additionally declare `published_artifact = "<path>"` pointing at a
results file regenerated by `make reproduce`.

OVERRIDES Part I sections 30.4.1 and 30.4.2: the two-ring scheme that assigns every non-Tier-1
component to `DEMO_PATH` or `DEMO_ARTIFACT`, bans `CI_ONLY`, and requires that a component no demo
output depends on be deleted with the deletion recorded in `docs/ADR/`, is replaced by a role that
may equally be a benchmark or a published artifact, and by the deletion ledger
`docs/polyglot/deleted.md` (§73.6). An implementer following §30.4.2 deletes benchmark-only
components that are load-bearing here, and files the record of it in a directory no gate reads.

Additional Tier C rule: the ingest path must contain no language-specific branch. A grep gate fails
the build if any adapter identifier, filename or conditional in `ingest/` matches the name of a Tier
C language. Adapters are keyed by *format* (syslog-rfc5424, logfmt, jsonl, nginx-combined,
log4j-pattern, ...), never by producer language. This is what makes the Tier C promise a property
rather than a slogan.

```
                    ┌──────────────┐
  Tier C estate ───▶│ format       │──▶ bundle.jsonl ──▶ ER ──▶ fact base
  (11 languages)    │ adapters     │        │                      │
                    │ (no language │        │                      ▼
  Tier B services ─▶│  branches)   │        │              ECLIPSE kernel (Rust)
  (Java, C#, asm)   └──────────────┘        │                      │
                                            │            ┌─────────┴──────────┐
  Tier D sources ──────────────────────────▶┘            ▼                    ▼
  (Solidity, HDL FIFO loss traces)                  cert.json          Go checker
                                                         │                    │
  Tier B oracles ──────────────────────────────────▶ differential ◀────────────┘
  (Haskell admissibility, C/C++ bench)                  gates
                                                         │
  Tier D analysis (R, Julia, Octave, F#) ───────▶ docs/bench/*.md  ──▶ make reproduce
```

Every arrow in this diagram is an edge the audit must find in `polyglot.toml`. An edge in the
diagram with no corresponding manifest entry fails with `UNDECLARED_EDGE`; a manifest entry with no
arrow is either wrong or the diagram is stale, and the diagram is regenerated from the manifest by
`make polyglot-graph` rather than hand-drawn.

73.4 `polyglot.toml` — the manifest

One file at the repository root. Machine-authored sections are regenerated; human-authored fields are
required and linted for placeholders.

```toml
schema_version = 1

[[component]]
id            = "ingest-scanner-c"
language      = "C"
tier          = "B"
paths         = ["c/ingest_scanner/**"]
toolchain     = "clang-17.0.6"            # pinned; must match toolchain-lock.toml
offline_source = "vendor/llvm/clang-17.0.6.tar.zst"
entrypoint    = "make -C c/ingest_scanner bench"

promise       = "A measured alternative implementation of the record framing and field scanner, compared against the Rust scanner on identical input. The comparison is the artifact; the outcome is whatever it is."

[component.consumer]
kind          = "differential-gate"
artifact      = "tests/differential/scanner_rust_vs_c.rs"
owned_by      = "kernel-rust"             # MUST differ from this component's own id

[component.ci]
job           = "polyglot-b / ingest-scanner-c"
triggers      = ["c/ingest_scanner/**", "rust/ingest/**", "fixtures/ingest/**"]
cadence       = "per-pr"

[component.mutation]
op            = "truncate_output_fields"  # from the closed operator set, §73.5
seed          = 7331
expect_red    = "polyglot-b / ingest-scanner-c :: scanner_rust_vs_c::field_boundaries_agree"

[component.role]
demo          = "none"
benchmark     = "docs/bench/ingest.md#scanner-comparison"
published_artifact = "artifacts/bench/ingest/results.jsonl"
```

OVERRIDES Part I section 32.9: the negative requirement "Do not vendor third-party source. Pin
versions in lockfiles instead." is replaced by a required `offline_source` field per component,
pointing at a committed archive under `vendor/`, which §73.6 resolves with the network off and §73.8
marks `linguist-vendored=true`. An implementer who obeys §32.9 has no `vendor/` tree to resolve
against and fails `make polyglot-audit` on every component on its first run; §33.5's offline model,
which fetches each toolchain during `make setup` before the network is cut, does not satisfy
`offline_source`.

Required per-component fields: `id, language, tier, paths, toolchain, offline_source, entrypoint,
promise, consumer.*, ci.*, mutation.*, role.*`. Lints:
- `promise` must be ≥ 120 characters, must not contain "TODO", "placeholder", "various", "misc",
  "showcase", "demonstrates" — fails `PROMISE_PLACEHOLDER`.
- `consumer.owned_by != id` — fails `SELF_CONSUMING`.
- `expect_red` must name both a job and a specific assertion — fails `MUTATION_UNDERSPECIFIED`.
- Every file in the tree whose extension maps to an executing language must be matched by exactly one
  component's `paths` — unmatched files fail `ORPHAN_SOURCE`; doubly-matched files fail
  `AMBIGUOUS_OWNERSHIP`.

OVERRIDES Part I sections 30.4.4, 30.5 and 31.46 rule 7: `languages.toml` and its schema (`name`,
`dir`, `tier (1..4)`, `reason`, `duplication_kind`, `build`, `test`, `ci_job`, `mutation_tests`,
`demo_ring`, `produces`, `consumes`, `weak_exercise`, `loc_budget`), and the `make lang-audit` gate
that parses it and cross-checks `.gitattributes` against it, are replaced by `polyglot.toml` with
the fields above, lettered tiers A..D, and `make polyglot-audit` as the only manifest gate;
`.gitattributes` is cross-checked against `polyglot.toml` (§73.8). An implementer who keeps both
declares every component twice, with `tier = 2` and `tier = "B"` meaning unrelated things for the
same component, and points §31.46 rule 7's cross-check at a manifest that no gate in this section
reads.

73.5 The mutation operator set

Closed set. Deterministic, seeded, offline. Applied to the component's *output*, never to its source,
except for `stub_entrypoint`.

| Operator                | Applies to                    | Effect                                                        |
|-------------------------|-------------------------------|---------------------------------------------------------------|
| `stub_entrypoint`       | any                           | replace entrypoint with a successful no-op that emits nothing  |
| `empty_output`          | emitters, analyses            | produce a zero-byte artifact with exit code 0                  |
| `drop_records(p, seed)` | telemetry emitters            | delete a seeded fraction of emitted records                    |
| `truncate_output_fields`| scanners, parsers             | drop the final field of each parsed record                     |
| `flip_byte(off, seed)`  | fixtures, encoders            | flip one byte at a seeded offset                               |
| `reorder_output(seed)`  | emitters, statistics          | permute output lines under a seeded shuffle                    |
| `constant_result(v)`    | oracles, statistics, solvers  | return a fixed value regardless of input                       |
| `widen_tolerance`       | differential partners         | accept any disagreement                                        |

Rule: `constant_result` is the mandatory operator for every Tier B oracle and every Tier D
cross-check. An oracle that still lets its gate pass while returning a constant is not an oracle.

73.6 `make polyglot-audit`

Runs offline, single-threaded in its decision path, seeded, and writes
`artifacts/polyglot/audit.json` plus `docs/polyglot/audit.md` (generated; never hand-edited).

```
PROCEDURE polyglot_audit(manifest, mode):            # mode ∈ {fast, full}
  load manifest; verify schema_version
  FAIL_ON orphan sources, ambiguous ownership, promise placeholders, self-consumption
  FAIL_ON any component whose toolchain is absent from toolchain-lock.toml
  FAIL_ON any component whose offline_source is missing from vendor/ (network stays off)
  FAIL_ON /\bMATLAB\b/i outside docs/polyglot/octave-not-matlab.md
  FAIL_ON language-named identifiers under ingest/
  FOR each component c, in lexicographic id order:
      (a) EXECUTES:  run c.ci.job's declared entrypoint; require exit 0 and non-empty declared output
      (b) CONSUMED:  resolve c.consumer.artifact; require it reads c's output path in the build graph
      (c) MUTATES:   if mode == full, or if c.paths changed in this diff:
                        w := scratch worktree
                        apply c.mutation.op with c.mutation.seed to c's output in w
                        run exactly the job named in c.mutation.expect_red
                        require RED and require the failing assertion == c.mutation.expect_red
                        require the mutated run touched no network socket
      (d) ROLE:      require demo step, benchmark anchor, or published_artifact to resolve
  EMIT counts: executing_languages, config_formats, linguist_rows, per-tier tallies
  EMIT verdict per component: LOAD_BEARING | PADDING(reason)
  EXIT 1 if any component is PADDING
```

Cadence: `fast` per-PR over changed components; `full` nightly over all of them. `make
polyglot-audit` with no argument means `full` and is what the release gate runs.

Transcript (illustrative, not a target — the real numbers are whatever the run prints):

```
$ make polyglot-audit
polyglot-audit: manifest schema 1, 32 executing components, 11 config formats
polyglot-audit: network namespace: none (offline enforced)
polyglot-audit: toolchains resolved from vendor/ : 32/32

  id                       tier lang         exec consumed mutation                         role
  asm-syscall-fixtures     B    Assembly     ok   ok       RED @ oracles/asm::trace_hash    bench
  estate-objc-agent        C    Objective-C  ok   ok       RED @ scenario/S3::er_recall     demo
  estate-powershell-host   C    PowerShell   ok   ok       RED @ scenario/S3::bundle_hash   demo
  frontier-fsharp          D    F#           ok   ok       RED @ xcheck/frontier::set_eq    artifact
  hdl-fifo-vhdl            D    VHDL         ok   ok       RED @ xcheck/fifo::drop_trace_eq artifact
  ingest-scanner-c         B    C            ok   ok       RED @ diff/scanner::field_bounds bench
  license-oracle-haskell   B    Haskell      ok   ok       RED @ gates/admissibility::diff  gate
  quantile-sweep-octave    D    Octave       ok   ok       RED @ xcheck/quantile::exact     artifact
  wat-preimage             D    WebAssembly  ok   ok       RED @ e2e/hash-badge::matches    demo
  ...
polyglot-audit: PADDING: 0
polyglot-audit: counts -> executing=32 config=11 linguist_rows=43
polyglot-audit: wrote artifacts/polyglot/audit.json docs/polyglot/audit.md
OK
```

Failure transcript (illustrative, not a target):

```
$ make polyglot-audit
  estate-perl-rotator      C    Perl         ok   ok       GREEN (expected RED)             demo
polyglot-audit: PADDING: estate-perl-rotator
  mutation drop_records(0.5, seed=4211) applied; job 'scenario/S2' stayed GREEN
  no downstream assertion depends on this component's output
  ACTION: delete perl/ and its manifest entry, or give it a consumer and re-run
polyglot-audit: exit 1
```

The failure action is **deletion, not documentation**. Deleted languages are recorded in
`docs/polyglot/deleted.md` with the date, the mutation that exposed them and the commit that removed
them. That file is a ledger, not a defence; it contains no argument for why the language was a good
idea.

73.7 README wording, exactly

`README.md` contains this block and no other sentence anywhere in the repository states a language
count. The three numerals are substituted by `make docs` from `artifacts/polyglot/audit.json`; the
literal tokens are committed, not the numbers.

```markdown
### Languages

SPECTRA executes code in <<AUDIT:executing_languages>> programming languages in CI, across four
tiers with different promises: a six-language critical path, independent oracles and measured
performance comparisons, a heterogeneous observed estate whose only purpose is to be reconstructed
without the pipeline knowing what wrote it, and narrow research artifacts.

It also contains <<AUDIT:config_formats>> configuration and markup formats (JSON, YAML, TOML, XML,
HTML, CSS, SCSS, Dockerfile, Makefile, CMake, HCL). These are not counted as languages.

GitHub's language bar shows <<AUDIT:linguist_rows>> rows because it counts both. The number that
means something is the first one, and every language behind it passes `make polyglot-audit`: it has
a declared consumer, a CI job that runs it, and a recorded mutation that turns a named gate red.
See docs/polyglot/audit.md (generated) and docs/polyglot/deleted.md.

Numerical code is written for **GNU Octave**, not MATLAB, and has never been executed by MATLAB.
```

Gate: a CI step fails with `UNSUBSTITUTED_TOKEN` if any `<<AUDIT:...>>` token survives into a built
doc, and with `UNBACKED_COUNT` if a numeral adjacent to the word "language", "languages" or "polyglot"
appears anywhere in `README.md` or `docs/` outside the generated block.

OVERRIDES Part I sections 31.46 rule 8 and 30.7.5: the README language inventory reported as a table
with a tier column and a one-sentence reason for each entry, stated once, is replaced by the
generated prose block above, which carries no per-entry reason column and no tier numerals. An
implementer who writes Part I's table fails `UNBACKED_COUNT` on every row that places a tier number
beside the word "language", and the per-language reason it carried now lives only in
`polyglot.toml`'s `promise` field and `docs/polyglot/audit.md`.

73.8 `.gitattributes` — Linguist rules and the anti-inflation ban

```gitattributes
* text=auto eol=lf

# Vendored offline toolchains and dependency caches are never counted.
vendor/**            linguist-vendored=true
third_party/**       linguist-vendored=true
**/node_modules/**   linguist-vendored=true

# Generated code is never counted. This includes guard-AST codegen output and any wasm build product.
rust/kernel/src/guards_generated.rs   linguist-generated=true
rust/sim/src/guards_generated.rs      linguist-generated=true
frontend/src/api/generated/**         linguist-generated=true
**/*.wasm                             linguist-generated=true binary
artifacts/**                          linguist-generated=true

# Documentation and fixtures are not the product.
docs/**              linguist-documentation=true
fixtures/**          linguist-detectable=false

# Hand-authored WebAssembly text is authored source; the compiled .wasm above is not.
wasm/preimage/*.wat  linguist-language=WebAssembly

# Binary-ish artifacts that must never colour the bar.
*.jsonl              linguist-generated=true
*.pcap               binary
golden/**            linguist-generated=true

# Line endings: golden bytes must be identical on Linux CI and the author's Windows host.
*.sh                 text eol=lf
*.ps1                text eol=lf
*.golden             text eol=lf
*.cert.json          text eol=lf
```

OVERRIDES Part I section 32.2: the mandated top-level tree and the per-language homes fixed by
§32.3, §32.4, §32.6 and §32.7 are replaced by the paths this block and §73.4 name — `frontend/` for
`web/`, `rust/kernel/` and `rust/ingest/` for the `eclipse-*` crates, `ingest/` for
`python/spectra_ingest/`, root-level `fixtures/`, `golden/`, `artifacts/`, `vendor/`,
`third_party/`, `octave/`, `perl/`, `c/ingest_scanner/` and `wasm/preimage/` for their `data/`,
`native/`, `polyglot/` and `analysis/` placements — together with `docs/polyglot/`, `docs/bench/`,
`docs/research/` and `docs/naming.md` beside §32.2's `adr/`, `eclipse/`, `diagrams/` and `paper/`
subtrees. An implementer who produces §32.2's structure exactly gets a `.gitattributes` whose
patterns match nothing and a §73.3.4 ingest grep gate that reports green because the directory it
scans does not exist.

Hard ban: `linguist-language=` may be used **only** to correct a genuine misdetection, and every use
requires a one-line comment stating the misdetection it corrects. Using it to relabel a file as a
language it is not — renaming `.txt` fixtures to a source extension, declaring config as code,
tagging generated output as authored, splitting one component across extensions to add a bar row — is
inflation. `make polyglot-audit` re-derives the Linguist breakdown itself and fails with
`LINGUIST_OVERRIDE_UNJUSTIFIED` if any override lacks a comment, and with `BAR_INFLATION` if the
authored-source byte count attributed to any language falls below the declared floor for a real
component while that language still occupies a bar row.

OVERRIDES Part I section 31.46: the fourteen `linguist-language=` overrides in its `.gitattributes`
block, and rule 5's pairing of them with `linguist-detectable=true` so that those languages are
counted, are replaced by the comment-per-override requirement above and by the exclusions in this
block — `schemas/**/*.json → JSON`, `infra/terraform/**/*.tf → HCL` and `mk/*.mk → Makefile` are
declaring config as code, and `fixtures/asm/**/*.asm linguist-detectable=true` is the inverse of
`fixtures/** linguist-detectable=false` above. An implementer who commits §31.46's file fails
`LINGUIST_OVERRIDE_UNJUSTIFIED` on thirteen uncommented lines before the inflation check is even
reached.

73.9 CI tiering, budget and blocking rules

OVERRIDES Part I: §43.1 (per-language unit tier on every push) and §52.1 (milestone green twice on a
clean clone with the full matrix) are reconciled here. Running 32 toolchains per push is not
affordable for one engineer and was never going to happen; pretending otherwise is how gates get
quietly deleted.

| Tier | Per-PR                                   | Nightly        | Blocks a milestone | Blocks a tagged release |
|------|------------------------------------------|----------------|--------------------|--------------------------|
| A    | full, every push                         | full           | yes                | yes                      |
| B    | changed-path jobs + all differential gates| full + mutation| yes                | yes                      |
| C    | changed-path jobs only                   | full + mutation| no                 | yes                      |
| D    | changed-path jobs only                   | full + mutation| no                 | yes                      |

Rules:
1. A red Tier C or D job does not block a milestone. It appears in the README status table within one
   commit and blocks any tagged release.
2. A Tier C or D job that is red for more than a declared grace window is not silenced. It is either
   fixed or the component is deleted under §73.6. Deletion is a legitimate outcome; muting is not.
3. One digest-pinned prebuilt toolchain image holds all 32 toolchains. Per-PR jobs never install a
   toolchain. The image is rebuilt on a schedule and its digest is recorded in the run manifest.
4. Budget ceilings (illustrative, not a target; the real budget is recorded in the CI budget section
   and measured): per-PR polyglot minutes bounded, nightly full audit bounded, and the audit prints
   its own wall-clock next to the ceiling so an overrun is visible rather than discovered.
5. Zero-flake rule: a polyglot job that fails intermittently is quarantined with a ledger entry
   naming the component and the date; a quarantined component is treated as PADDING at the next
   release gate unless the flake is fixed.

73.10 The ECLIPSE name collision — noted and decided

The name ECLIPSE collides with the Eclipse Foundation, the Eclipse IDE, Eclipse Temurin/Adoptium (a
JVM toolchain this repository actually vendors for Tier B), Eclipse Jetty, Eclipse Mosquitto and the
Eclipse Public License. The collision is total for search, ambiguous in a paper's index terms, and
actively confusing in a repository whose CI pulls Temurin.

DECISION: keep the acronym, bind it everywhere, and keep the rename cost bounded to documentation.

1. First use in every document, including the paper abstract, the README, the UI About panel and the
   demo script, is exactly: `ECLIPSE (SPECTRA's proof kernel)`. A bare leading "ECLIPSE" at the start
   of `README.md`, `docs/**`, or any abstract fails the banned-phrase gate with `UNBOUND_ECLIPSE`.
2. The string `eclipse` appears in **no machine-readable surface**: not as a crate, module, package or
   directory name; not as a binary on PATH; not as an HTTP path segment; not as a JSON field name, a
   file extension or magic bytes in any certificate. The kernel crate is `spectra-kernel`, the binary
   is `spectra prove`, the checker is `spectra verify`, the certificate media type carries `spectra`.
   A grep gate enforces this with `ECLIPSE_IN_ARTIFACT_SURFACE`.
   OVERRIDES Part I sections 31.5, 31.4, 32.2, 32.3, 32.4, 32.6, 34.2 and 34.6: the crates
   `eclipse-kernel`, `eclipse-rulegen` and `eclipse-verifier-wasm`; the workspace members
   `eclipse-core/`, `eclipse-rules/`, `eclipse-cut/`, `eclipse-liveness/` and `eclipse-cert/`; the
   packages `python/spectra_eclipse/` and `haskell/eclipse-ref/`; the directory `docs/eclipse/`; the
   shipped `web/public/eclipse_verifier.wasm`; and `config/defaults/eclipse.toml` with the keys
   `eclipse.atom_limit`, `eclipse.corridor_cap` and the environment override
   `SPECTRA__ECLIPSE__CORRIDOR_CAP`, are all replaced by `spectra`-named equivalents. An implementer
   who builds Part I's workspace, package, config and artifact names cannot pass this grep gate or
   §73.12.6, and renaming later is the certificate- and schema-affecting change that item 3 exists
   to avoid.
3. Because of (2), the name exists only in prose. If the collision causes confusion — a reviewer
   remark, a maintainer complaint, or an indexing problem — the project renames by editing
   documentation, with no certificate, schema or API change. `docs/naming.md` records the collision,
   this decision, and one reserved alternative name held for that event.
4. `docs/naming.md` also states plainly that this project has no affiliation with the Eclipse
   Foundation and that the repository's licence is named explicitly (never described only as "the
   EPL", which would compound the collision).

73.11 Negative requirements and forbidden claims

The following fail the build, the claims gate, or both.

- Do not add a language without a `polyglot.toml` entry that passes all four load-bearing checks
  before the first source file is committed. `ORPHAN_SOURCE` catches the violation; do not work
  around it by adding the path to `.gitignore`.
- Do not keep a language by writing a better rationale. The only admissible responses to a PADDING
  verdict are: give it a real consumer edge, promote it to a tier whose promise it can meet, or
  delete it.
- Do not write "N languages" with N derived from anything but `artifacts/polyglot/audit.json`.
- Do not count JSON, YAML, TOML, XML, HTML, CSS, SCSS, Dockerfile, Makefile, CMake or HCL as
  languages in prose. Do not count generated code, vendored code, fixtures or compiled wasm at all.
- Do not claim "43 languages". The bar has 43 rows; the sentence has <<AUDIT:executing_languages>>.
- Do not claim MATLAB. Do not claim MATLAB compatibility. Do not claim the Octave code is
  "MATLAB-compatible" — it has never been executed by MATLAB and that is the only checkable statement.
- Do not claim blockchain anchoring, immutability guarantees, or tamper-proofing from Solidity.
- Do not claim macOS, iOS or Windows endpoint telemetry from Swift, Objective-C or PowerShell.
- Do not claim a speedup from C or C++ unless `docs/bench/ingest.md` shows it, with the run manifest
  hash, on the declared hardware.
- Do not claim "hardware-accelerated", "FPGA", "silicon" or "RTL-verified" from Verilog or VHDL. The
  HDL artifacts are simulated bounded buffers producing loss ground truth.
- Do not claim formal verification from Haskell, F#, or any Tier D artifact. The Haskell component is
  an independently authored oracle for one relation; that is the whole claim.
- Do not let a Tier C or D failure be silenced with `continue-on-error` or an `if: false` guard. A CI
  lint fails on either appearing in a polyglot job.
- Do not use `linguist-language=` to move a file into a language it is not written in.
- Do not present the polyglot surface as a research contribution. Tier C's *reconstruction across
  unknown implementation languages* is the research property; the roster size is not.

73.12 Done criteria for this section

1. `polyglot.toml` exists, every executing source file in the tree is owned by exactly one component,
   and `make polyglot-audit` exits 0 in `full` mode with `PADDING: 0`.
2. Every component has a recorded mutation run whose named gate went RED, with the job name and
   failing assertion stored in `artifacts/polyglot/audit.json`.
3. `docs/polyglot/audit.md` and the README language block are generated, token-free, and regenerated
   by `make reproduce` from a clean clone with the network off.
4. `docs/polyglot/deleted.md` exists, even if empty, with its ledger schema in place.
5. `docs/polyglot/octave-not-matlab.md` exists and the `BANNED_MATLAB_MENTION` gate is active.
6. `docs/naming.md` exists, the `UNBOUND_ECLIPSE` and `ECLIPSE_IN_ARTIFACT_SURFACE` gates are active,
   and no machine-readable surface contains the string `eclipse`.
7. The held-out Tier C language is named in `docs/research/preregistration.md` before it is written,
   and its results appear as a separate labelled row wherever reconstruction quality is reported.
8. The ingest language-branch grep gate is active and green.
