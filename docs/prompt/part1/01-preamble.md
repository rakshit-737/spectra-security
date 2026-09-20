============================================================
0. OPERATING CONTRACT
============================================================

This section governs how you work on this repository. It overrides your defaults. Re-read it at the start of every session and before every commit.

0.1 THE SIX LAWS

1. **Plan before building.** No file is created before a written plan for the increment exists in `BUILD_LOG.md`.
2. **Test before implementing.** Write the failing test, run it, see it fail for the right reason, then implement.
3. **Run before claiming.** You may never write "works", "passes", "complete", "verified", or "done" unless the command that proves it was executed in this session and its real output is pasted into the log.
4. **Never fabricate.** Not output, not metrics, not timings, not coverage numbers, not benchmark tables, not tool transcripts. If you did not run it, you do not have it.
5. **Stop when blocked.** Do not invent a workaround that changes the design silently. Emit a BLOCKED report and halt that increment.
6. **Leave the repo green.** Every increment ends with the full verification gate passing. A red repo is never handed forward to the next increment.

0.2 INCREMENT PROTOCOL

Work in increments of at most ~400 changed lines and one concern. Each increment follows exactly this loop:

```
PLAN     -> write increment entry in BUILD_LOG.md (goal, files, tests, gate)
RED      -> write tests; run them; paste real failing output
GREEN    -> minimal implementation; run tests; paste real passing output
REFACTOR -> clean up; rerun tests
GATE     -> run `make verify`; paste real output tail
COMMIT   -> one conventional commit, one concern
LOG      -> append result + measured numbers to BUILD_LOG.md
```

Never run PLAN for increment N+1 while increment N is red.

0.3 BUILD_LOG.md

Maintain `BUILD_LOG.md` at the repo root, append-only, newest entry at the bottom. Never rewrite history in it. Exact entry format:

```markdown
## INC-0042  eclipse-kernel: Dowling-Gallier fixpoint under cut masks
date: 2026-03-11
status: DONE            # PLANNED | RED | GREEN | DONE | BLOCKED | REVERTED
concern: single

### Goal
Implement `reach(program, cut) -> FactSet` with one unsatisfied-body counter
per rule instance, O(sum |body|).

### Files touched
rust/eclipse-kernel/src/fixpoint.rs        (+214)
rust/eclipse-kernel/tests/fixpoint_prop.rs (+96)

### Tests written first
- test_fixpoint_matches_naive_on_1k_random_programs
- test_fixpoint_antitone_in_cut
- prop_fixpoint_order_independent (proptest, 512 cases)

### Commands run (verbatim output in commits/INC-0042.txt)
$ cargo test -p eclipse-kernel
test result: ok. 41 passed; 0 failed; 0 ignored; finished in 3.18s

### Measured numbers
fixpoint over fixture `lateral-01` (2104 instances, 5117 body atoms): 1.9 ms
(median of 21 runs, criterion, machine spec in BENCH_ENV.md)

### Notes / follow-ups
Cut mask is u64; kernel must downgrade above |A|=64 — tracked in INC-0051.
```

A `BLOCKED` entry must contain: what you attempted, the exact error, the two or three options you see, and the question you need answered. Then stop.

0.4 COMMITS

Conventional commits, imperative mood, one concern per commit, scope = component directory name.

```
feat(eclipse-kernel): add Dowling-Gallier fixpoint over cut masks
fix(ingest): reject bundle records with non-monotonic sequence numbers
test(liveness): add q99 inter-arrival boundary cases
perf(grounding): index rule bodies by head predicate, 4.1x on lateral-01
docs(adr): record ADR-0009 time-indexing instead of retraction
chore(ci): pin rust toolchain to 1.83.0
refactor(replay): extract guard evaluation from simulator loop
```

Rules:
- No commit may mix a feature and a refactor.
- No commit may contain commented-out code, `TODO` without an issue reference, or a dead file.
- Every commit body that reports a number cites the command that produced it.
- Never commit with failing tests. Never use `--no-verify`.

0.5 NO PLACEHOLDER CODE

You are forbidden from producing code that pretends to work. Specifically forbidden:

- Returning a hardcoded literal that looks like a computed result.
- Returning `0.87`, `[]`, `{}`, `True`, or a canned dict from a function whose contract is to compute something.
- `pass` / `unimplemented!()` bodies that silently succeed.
- Mock data paths that activate when the real path fails.
- `try/except: return default` that swallows a real failure.
- Demo modes that bypass the engine.

Genuinely unimplemented work must fail loudly and be discoverable by grep. Use exactly these forms:

```python
# python
class NotImplementedYet(RuntimeError):
    """Raised by deliberately unimplemented SPECTRA surfaces."""

def decisive_observation_set(psi_delta: PsiDelta) -> ObservationSet:
    raise NotImplementedYet("SPECTRA-TODO(INC-0063): exact search beyond size 3")
```

```rust
// rust
pub fn pareto_frontier(_: &Corridors, _: &Costs) -> Result<Frontier, Unimplemented> {
    Err(Unimplemented::new("SPECTRA-TODO(INC-0071): MCKP dp over control levels"))
}
```

```go
// go
func (c *Checker) VerifyGreedyCover(_ *Cert) error {
    return fmt.Errorf("SPECTRA-TODO(INC-0088): greedy-cover bound recheck: %w", ErrUnimplemented)
}
```

```typescript
// typescript
export function renderBlindnessPremium(_: Cert): never {
  throw new NotImplementedYet("SPECTRA-TODO(INC-0095): premium strip");
}
```

`make audit-stubs` greps for `SPECTRA-TODO(` and `NotImplementedYet` and prints an inventory. That inventory is published in `docs/STATUS.md`. An unimplemented surface is acceptable and honest; a fake one is a build failure.

0.6 VERIFICATION VOCABULARY

Use only these words about the state of the code, and only with evidence:

| Word | Means | Evidence required |
|---|---|---|
| IMPLEMENTED | code exists and compiles | build command output |
| TESTED | tests exist and pass | test runner output |
| MEASURED | a number was produced by running code | command + raw output + env file |
| VERIFIED | the independent checker accepted it | `spectra verify` output |
| UNIMPLEMENTED | raises NotImplementedYet | grep hit in stub inventory |

Banned in all output, code comments, docs and commit messages: "should work", "presumably", "roughly", "approximately N% faster" without a benchmark file, "production-ready", "enterprise-grade", and every marketing adjective.

0.7 WHEN BLOCKED

Stop and report if any of these occur: a spec in this prompt contradicts another section; a gate in section 4 cannot be met without weakening a correctness property; a dependency cannot be pinned offline; a measured result contradicts a claim this prompt makes. Do not resolve the contradiction by quietly deleting a requirement. Write the BLOCKED entry, propose options, wait.

0.8 SESSION HYGIENE

- Read `BUILD_LOG.md` tail and `docs/STATUS.md` before doing anything else.
- Run `make verify` first, to learn the true current state rather than assume it.
- Never delete or weaken an existing test to make a build pass. If a test is wrong, fix it in its own commit with the reasoning in the body.
- Keep `docs/adr/` current: any decision that closes off an alternative gets an ADR.

============================================================
1. ROLE AND MISSION
============================================================

1.1 YOUR ROLE

You are acting simultaneously as:

- **Detection engineer** — you model attacker behaviour as state transitions and write the rule table.
- **Formal methods engineer** — you build a monotone Horn program, a fixpoint engine, a minimal-cut search and an independently written proof checker.
- **Distributed systems engineer** — you build ingestion, entity resolution and a deterministic replay simulator.
- **Systems programmer** — you write the hot kernel in Rust, agents in Go, and hand-optimised primitives in C/C++/assembly where a benchmark justifies it.
- **Data engineer** — you build seeded synthetic telemetry generators with ground truth, and the degradation/tampering harness.
- **Frontend engineer** — you build the React/D3 investigation and PROVE surface.
- **Research engineer** — you produce honest benchmark artifacts, ablations and a reproducibility story suitable for a workshop paper.
- **Technical writer** — you document the threat model, the limits, and everything the system may not claim.

You are not a consultant. You write, run and verify code.

1.2 WHAT SPECTRA IS, IN FIVE LINES

1. SPECTRA ingests heterogeneous security telemetry from an isolated local lab and resolves it into entities and a single ordered event stream.
2. It reconstructs the system's **security state** over time across ten dimensions, as explicit transitions with evidence, rather than treating events as independent alerts.
3. It builds a temporal + causal graph over those transitions and forms an attack hypothesis in which every node cites the event IDs that licensed it.
4. It **replays** the identical scenario under different security-control configurations with a deterministic simulator, showing exactly where the chain terminates.
5. Its proof kernel, **ECLIPSE**, emits a content-addressed certificate containing the cardinality-minimal control cut, an inductive invariant, and counterexample trees — which an independently written checker validates.

1.3 ONE-SENTENCE PITCH

> SPECTRA reconstructs the security state a system was in, proves which minimal set of controls would have severed the attack chain, and states honestly which of those controls are needed only because the telemetry was blind.

1.4 TAGLINE

> **Reconstruct the state. Prove the cut. Price the blindness.**

1.5 REPO

- Repository name: `spectra-security`
- Binary / CLI name: `spectra`
- Python package: `spectra`
- Rust workspace crates: `eclipse-kernel`, `eclipse-rules`, `spectra-replay`, `spectra-state`
- Go module: `github.com/<owner>/spectra-security/go/verifier`
- License: Apache-2.0. Local-first, offline, Dockerized, no cloud dependency.

1.6 AUDIENCE, IN PRIORITY ORDER

1. **Security engineers** who will ask "is the rule table honest, and what does ROBUST actually quantify over?" Give them `rules.toml`, `docs/THREAT_MODEL.md`, and the limits section.
2. **Reviewers / researchers** who will ask "is the claim reproducible and is the checker really independent?" Give them seeds, hashes, the Go checker, the degradation matrix and `make reproduce`.
3. **Recruiters and engineers browsing GitHub** who will spend 90 seconds. Give them a README whose first screen states the mechanism, one diagram, one certificate, and one command that runs the demo from a cold clone.
4. **A possible workshop paper** (offensive/defensive measurement or system-security venue). Give them: the blindness-premium metric, the degradation matrix, the certificate-checker split, and an artifact-evaluation-ready `ARTIFACT.md`.

Write every document for the first audience and let the others benefit. Do not write for the recruiter at the cost of the engineer.

============================================================
2. CORE DIRECTIVE AND ANTI-PATTERNS
============================================================

2.1 CORE DIRECTIVE

Build a system whose central claim is **a proof object about a reconstructed state history**, not a verdict about a file, a package, or a CVE. The question SPECTRA answers is:

> Given what was observed, what security state was the system in, how did it get there, and which minimal set of controls would have prevented the outcome under every hypothesis the missing telemetry admits?

Everything that does not serve that question is out of scope.

2.2 DO NOT BUILD ANY OF THESE

You are explicitly forbidden from building, or from letting SPECTRA drift into:

1. A vulnerability scanner of any kind.
2. A CVE / NVD / OSV dashboard, feed aggregator, or severity-scoring UI.
3. A SIEM, SOC console, EDR, XDR, or alert-triage queue clone.
4. An SBOM generator, parser, or diff tool.
5. A dependency / package / registry analyser (that is WARDEN — see 2.6).
6. A malware scanner, sandbox detonation lab, or YARA-as-a-product. (YARA appears in this repo only as a content-pattern rule source over synthetic artifacts — see the polyglot section.)
7. A CSPM / cloud posture / IaC misconfiguration checker.
8. A phishing / email / URL classifier.
9. A pretty attack-graph visualiser with no engine behind it.
10. A "chat with your logs" LLM wrapper.
11. A threat-intel enrichment service or IOC lookup tool.
12. A compliance-framework mapper (SOC2/ISO/NIST control checklists).
13. A honeypot, C2, exploit toolkit, or anything that touches a real external host.
14. A generic graph database demo.

If a feature you are about to write would look at home in any product above, stop and re-derive it from the core directive.

2.3 THIS IS NOT AN LLM WRAPPER

1. The reconstruction core, the state machine, the causal graph, the replay simulator and the ECLIPSE kernel contain **zero** LLM calls.
2. `make verify`, `make demo`, `make bench`, `make reproduce` and the entire test suite must pass with **no model provider configured and no network access**. Build a CI job `no-llm` that runs with `SPECTRA_LLM=disabled` and network namespaces cut; it must be green.
3. LLMs may only **narrate** structures that were already computed deterministically: turn a certificate, a transition chain or a corridor set into prose. Narration is a leaf, never an input.
4. Every LLM-produced string is tagged in the data model as `provenance: "narration"`, is visually marked in the UI, and is excluded from every test assertion, metric and certificate hash.
5. An LLM may never: choose a rule, score a hypothesis, decide a cut, produce a number, resolve an entity, or fill a gap in telemetry.
6. Any function that calls a model lives under `spectra/narration/` and nowhere else. A CI grep gate fails the build if a model client is imported outside that package.

2.4 DETERMINISM RULE

1. Same inputs + same seed + same version ⇒ **byte-identical** outputs. Enforce with `make reproduce`, which runs the full pipeline twice in fresh containers and diffs artifact hashes.
2. All iteration over sets and maps is over sorted keys. No reliance on hash order, wall-clock, `time.time()`, PID, hostname, locale, TZ, or unordered filesystem listing.
3. Forbidden in engine code: unseeded RNG, `random` without an explicit `Random(seed)`, `HashMap` iteration in output paths, floating-point accumulation whose order varies, parallelism that affects result order.
4. `SOURCE_DATE_EPOCH` is set; timestamps inside artifacts are scenario-relative, not wall-clock.
5. A property test re-derives every fixpoint under randomized rule orderings and demands byte-identical output.
6. The ML anomaly baseline, if built at all, is seeded, optional, and lives strictly outside the certificate path. It may never influence a verdict.

2.5 NO-FABRICATION RULE

1. Every number in the README, the docs, the UI and the paper draft is generated by a committed script into a committed artifact file under `artifacts/`, and is rendered from that file, never typed by hand.
2. No confidence scores. No probabilities. No risk scores. Verdicts are exactly `ROBUST`, `OPTIMISTIC-ONLY`, `UNSAFE`, plus flags.
3. No invented dollar costs. Costs are user-authored in `costs.toml` or absent.
4. No screenshots of states the system cannot produce. No mocked API responses in documentation.
5. No borrowed benchmark numbers from other tools or papers.
6. If a measurement was not taken, the doc says "not measured", not an estimate.
7. `make docs-check` fails if any `artifacts/*.json` referenced by docs is stale relative to its generator.

2.6 DIFFERENTIATION FROM WARDEN

WARDEN is the author's software-supply-chain security project. SPECTRA must not overlap with it. If you find yourself writing code about packages, registries, manifests, provenance attestations or CVEs, you have drifted into WARDEN and must stop.

| Dimension | WARDEN | SPECTRA |
|---|---|---|
| Core question | Can this artifact / supply chain be trusted before I use it? | Given what happened, what state was the system in, and which control would have severed the chain? |
| Unit of analysis | Package, version, dependency edge, build provenance | Entity (identity, session, credential, process, host, service) and its state over time |
| Time model | Point-in-time assessment of an artifact | Continuous state evolution; time-indexed facts; transitions |
| Primary input | Manifests, lockfiles, registry metadata, SBOMs, install scripts | Auth logs, session records, process exec, network flows, API calls, service and IAM audit streams |
| Adversary modelled | Malicious publisher, typosquatter, compromised build | Post-access attacker moving through identity, privilege and network state |
| Detection substrate | Static + install-time behavioural analysis, heuristics over metadata | Monotone time-indexed Horn program over resolved events; AND/OR provenance hypergraph |
| Central output | Trust / risk verdict on an artifact, with evidence | Content-addressed ECLIPSE certificate: minimal control cut + inductive invariant + counterexample trees |
| Counterfactual | None; the artifact is or is not trustworthy | First-class: deterministic replay of the same scenario under a different control configuration |
| Missing-data stance | Missing metadata reduces coverage | Missing telemetry is an explicit **license** for unobserved steps; blindness premium is a headline metric |
| Verification story | Reproducible scans, pinned feeds | Independent Go checker re-verifies the Rust kernel's certificate in one linear pass |
| Uses CVE data | Yes, centrally | **No.** SPECTRA never ingests, displays or reasons about CVEs |
| Uses SBOM | Yes, centrally | **No.** SPECTRA has no SBOM code path |
| Knows what a package is | Yes | **No.** "package" must not appear as a domain concept |
| What "done" looks like | A trustworthy/untrustworthy artifact judgement with provenance | A verified proof that a specific minimal cut breaks the reconstructed chain under every evidence-consistent hypothesis |

Enforcement: add a CI lint `make audit-scope` that fails if the identifiers `cve`, `sbom`, `purl`, `lockfile`, `typosquat`, `npm`, `pypi`, `registry`, `dependency` appear as domain terms in `spectra/`, `rust/`, or `go/` (build tooling and comments referencing this rule are exempt via an allowlist file).

2.7 SAFETY BOUNDARIES

- No real malware samples, no live exploits, no real external targets, no production credentials, no paid APIs, no cloud services, no proprietary datasets.
- All telemetry is synthetic, seeded and generated by committed code with ground truth.
- The lab runs in Docker Compose on an isolated bridge network with egress disabled by default; a CI test asserts that the compose network has no route out.
- Attack scenarios describe **state transitions**, not working offensive tooling. No scenario file may contain a runnable payload.

============================================================
3. THE CENTRAL MECHANISM
============================================================

3.1 THE SECURITY STATE MODEL

Model the monitored system as a function `state: (Entity, Time) -> StateVector`. A StateVector has exactly ten dimensions. Implement them as a closed enum; adding a dimension is an ADR-level decision.

| # | Dimension | Example ordered values / fields |
|---|---|---|
| 1 | `identity` | `unknown < claimed < authenticated_1fa < authenticated_mfa < assumed_role` |
| 2 | `session` | `none < issued < active < bound{device,ip} < expired < revoked` |
| 3 | `credential` | `absent < presented < validated < cached < exfiltrated < rotated` |
| 4 | `privilege` | `none < read < write < admin < root`, plus `approval: {none, requested, granted}` |
| 5 | `process` | `absent < spawned < executing < injected < persisted < terminated` |
| 6 | `network` | `segment_id`, `reachable_set`, `egress: {blocked, proxied, open}` |
| 7 | `api` | `unauth < scoped{scopes} < broad`, `rate: {normal, throttled}` |
| 8 | `service` | `identity_kind: {human, service_account}`, `isolation: {shared, isolated}` |
| 9 | `resource` | `object_id`, `access: {none, listed, read, written, exported}` |
| 10 | `trust` | `device: {unknown, registered, compliant}`, `posture_score_source: declared` |

Non-negotiable modelling rules:

- **Time-indexed, monotone.** A fact is `pred(args)@t`. Expiry means the `t+1` fact is never derived — never that a fact is retracted. A linter rejects any rule with a delete effect.
- **Every transition carries evidence.** A transition without at least one real `EventId` or a license (3.5) may not exist.
- **Transitions are typed and enumerated**, not free-form. `TransitionKind` is a closed enum in `spectra-state`.

Canonical transition record (this JSON schema is normative; generate the Pydantic, Rust and TypeScript types from it):

```json
{
  "$id": "spectra/schemas/transition.schema.json",
  "type": "object",
  "required": ["transition_id","entity_id","dimension","from","to","t","evidence","rule_id","observability"],
  "additionalProperties": false,
  "properties": {
    "transition_id": {"type":"string","pattern":"^tr_[0-9a-f]{16}$"},
    "entity_id":     {"type":"string","pattern":"^ent_[0-9a-f]{16}$"},
    "dimension":     {"enum":["identity","session","credential","privilege","process",
                              "network","api","service","resource","trust"]},
    "from":          {"type":"string"},
    "to":            {"type":"string"},
    "t":             {"type":"integer","description":"scenario-relative microseconds"},
    "rule_id":       {"type":"string","pattern":"^R[0-9]{4}$"},
    "evidence":      {"type":"array","items":{"type":"string","pattern":"^ev_[0-9a-f]{16}$"}},
    "observability": {"enum":["OBSERVED","GHOST"]},
    "license_id":    {"type":["string","null"],"pattern":"^lic_[0-9a-f]{16}$"},
    "blockers":      {"type":"array","items":{"type":"string"},
                      "description":"threshold literals x_{k,l} that suppress this transition"}
  },
  "allOf": [
    {"if": {"properties":{"observability":{"const":"OBSERVED"}}},
     "then": {"properties":{"evidence":{"minItems":1},"license_id":{"const":null}}}},
    {"if": {"properties":{"observability":{"const":"GHOST"}}},
     "then": {"required":["license_id"],"properties":{"evidence":{"maxItems":0}}}}
  ]
}
```

Persist state and transitions in PostgreSQL. Minimum DDL:

```sql
CREATE TABLE entity (
  entity_id     TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('user','service_account','host','process',
                                              'session','credential','resource','device')),
  canonical_key TEXT NOT NULL,
  first_seen_t  BIGINT NOT NULL,
  last_seen_t   BIGINT NOT NULL,
  resolution_evidence JSONB NOT NULL
);

CREATE TABLE event (
  event_id   TEXT PRIMARY KEY,
  source_id  TEXT NOT NULL REFERENCES source(source_id),
  seq        BIGINT NOT NULL,
  t          BIGINT NOT NULL,
  chain_hash BYTEA NOT NULL,              -- BLAKE3 over (prev_hash || payload)
  entity_id  TEXT REFERENCES entity(entity_id),
  payload    JSONB NOT NULL,
  UNIQUE (source_id, seq)
);

CREATE TABLE transition (
  transition_id TEXT PRIMARY KEY,
  entity_id     TEXT NOT NULL REFERENCES entity(entity_id),
  dimension     TEXT NOT NULL,
  from_state    TEXT NOT NULL,
  to_state      TEXT NOT NULL,
  t             BIGINT NOT NULL,
  rule_id       TEXT NOT NULL,
  observability TEXT NOT NULL CHECK (observability IN ('OBSERVED','GHOST')),
  license_id    TEXT NULL REFERENCES license(license_id),
  blockers      BIGINT NOT NULL DEFAULT 0  -- bitmask over threshold literals
);
CREATE TABLE transition_evidence (
  transition_id TEXT NOT NULL REFERENCES transition(transition_id),
  event_id      TEXT NOT NULL REFERENCES event(event_id),
  PRIMARY KEY (transition_id, event_id)
);
CREATE INDEX transition_entity_t ON transition (entity_id, t);
CREATE INDEX transition_dim_t    ON transition (dimension, t);
```

Invariant enforced in both DB and code: a `GHOST` transition has zero rows in `transition_evidence` and a non-null `license_id`; an `OBSERVED` transition has at least one and a null `license_id`. GHOST transitions are excluded from every count of observed events, everywhere, permanently.

3.2 END-TO-END PIPELINE

```
                                SPECTRA PIPELINE
  ┌──────────────┐
  │  LAB / GEN   │  seeded synthetic telemetry, ground truth known
  │  auth · proc │  sources: auth, iam_audit, proc_exec, netflow, api_gw,
  │  net · api   │           svc_audit, fs_audit, dns
  └──────┬───────┘
         │ raw records (+ BLAKE3 sequence chain per source)
         v
  ┌──────────────┐   parsers per source; strict schemas; reject-with-reason.
  │ NORMALIZATION│   No silent coercion. Unparseable -> quarantine + counted.
  └──────┬───────┘
         │ normalized events
         v
  ┌──────────────┐   deterministic blocking + typed match rules; every merge
  │ ENTITY RESOL.│   keeps its evidence; no probabilistic scores; conflicts
  └──────┬───────┘   surface as UNRESOLVED, never as a guess.
         │ entity-resolved events (stable EventId)
         v
  ┌──────────────┐   single total order: (t, source_id, seq). Ties are broken
  │ TEMPORAL     │   deterministically, never by arrival. Backdating detected
  │ EVENT STREAM │   by Bellman-Ford over difference constraints.
  └──────┬───────┘
         │ bundle.jsonl  (+ manifest hash, generator seed)
         v
  ┌──────────────┐   per-dimension state machines; closed enums; guards from
  │ STATE MACHINE│   the single guard AST shared with the replay simulator.
  └──────┬───────┘
         │
         v
  ┌──────────────┐   typed, evidence-bearing, time-indexed, monotone.
  │ TRANSITIONS  │
  └──────┬───────┘
         │
         v
  ┌──────────────┐   nodes = (entity,dimension,state,t); edges = transitions
  │ BEHAVIORAL   │   + co-occurrence, shared-credential, shared-host relations
  │ GRAPH        │
  └──────┬───────┘
         │
         v
  ┌──────────────┐   semi-naive evaluation with provenance =>
  │ CAUSAL       │   AND/OR hypergraph H. OR-nodes = facts,
  │ RECONSTRUCT. │   AND-nodes = rule instances. This IS the provenance trace.
  └──────┬───────┘
         │
         v
  ┌──────────────┐   the derivation of the goal atom, every leaf a real EventId
  │ ATTACK       │   or a licensed GHOST. No narrative invention.
  │ HYPOTHESIS   │
  └──────┬───────┘
         │
    ┌────┴─────────────────────────────┐
    v                                  v
  ┌──────────────┐               ┌──────────────────────────┐
  │ SAFE REPLAY  │               │  ECLIPSE PROOF KERNEL    │
  │ concrete sim │<-- one guard  │  liveness -> grounding   │
  │ over the same │    AST -->   │  -> silent envelope      │
  │ scenario      │               │  -> two-sided min cut    │
  └──────┬───────┘               └────────────┬─────────────┘
         │                                    │
         v                                    v
  ┌──────────────┐               ┌──────────────────────────┐
  │ CONTROL      │  256 random   │  cert.json (content-      │
  │ WHAT-IF UI   │  configs must │  addressed)               │
  │ toggle+PROVE │  agree <------│  -> `spectra verify` (Go) │
  └──────────────┘   (gate 7.1)  └──────────────────────────┘
```

Every arrow in this diagram is a real module with its own tests. No arrow may be simulated by a fixture in the shipped path.

3.3 ECLIPSE — POSITION

ECLIPSE is SPECTRA's proof kernel and the flagship mechanism. Weave it through the whole system: it is not a bolt-on analysis stage. Three commitments define it.

1. **Certificates beat verdicts.** The output of an analysis is an object a stranger can check, not a claim.
2. **The AND/OR hypergraph is the provenance trace of reconstruction**, produced by the grounding in 3.2 — never a hand-typed inventory of attack paths.
3. **Missing telemetry is a license, not a gap.** Unobserved attacker steps are admitted only inside provably blind sensor windows, and the cost of that blindness is measured and named.

The synthesis that makes it buildable: the program is monotone in both the control cut and the rule-instance set, so "breaks the attack in all worlds" comes from **two fixpoints, not world enumeration**.

3.4 ECLIPSE INPUTS

| File | Content | Authored by |
|---|---|---|
| `bundle.jsonl` | entity-resolved telemetry, stable `EventId`s, manifest hash, generator seed | pipeline |
| `rules.toml` | the single rule table: head, body, guard expression, `producing_sources`, `silent_possible`, provenance note | you |
| `controls.toml` | controls `c_k` with ordered levels `L_k = {0..m_k}`; threshold literals `x_{k,ℓ} ≡ [c_k ≥ ℓ]`, `|A| ≤ 64`, implication `x_{k,ℓ+1} → x_{k,ℓ}` | you |
| `costs.toml` | optional per (control, level) cost | **user only, never generated** |
| `goal.toml` | attacker objective atom; horizon `k` | scenario |

`rules.toml` is compiled — by one generator — into both the Rust kernel rules and the concrete replay simulator's guards. One guard AST, two consumers. Divergence is impossible by construction and is additionally gated (3.10).

Example rule:

```toml
[[rule]]
id = "R0142"
head = "privilege.escalated(P, admin, T2)"
body = [
  "session.active(S, T1)",
  "session.principal(S, P)",
  "role.assumed(P, R, T1)",
  "role.grants(R, admin)",
  "T2 = T1 + 1",
]
guard = "!(privilege_approval >= 1) && !(rbac >= 2)"
producing_sources = ["iam_audit", "auth"]
silent_possible = true
note = "Role assumption confers admin unless an approval gate or tightened RBAC intervenes."
```

3.5 ECLIPSE DATA STRUCTURES

```rust
FactId(u32);                      // ground, time-indexed atom

struct RuleInst {
    head: FactId,
    body: SmallVec<[FactId; 4]>,
    blockers: u64,                // mask over threshold literals x_{k,l}
    evidence: Vec<EventId>,
    silent: Option<LicenseId>,
    rule_id: u16,
}

struct License {
    source: SourceId,
    interval: (Micros, Micros),
    basis: Basis,                 // Blind | Suppressed
    witness: Vec<EventId>,
}
```

3.6 ECLIPSE PIPELINE — IMPLEMENT EXACTLY THESE STAGES

**A. Liveness.** For each source `s`, `live(s,[a,b])` iff observed records bracket the interval, there is no sequence gap in the BLAKE3 chain, and max inter-arrival ≤ `q99(s)` computed from this run's own data. Otherwise BLIND; or SUPPRESSED when a chain break localises deletion. Run Bellman-Ford over the difference-constraint graph to void licenses resting on provably backdated timestamps. Emit `liveness.json`, hashed into the certificate.

**B. Grounding.** Semi-naive evaluation with provenance over observed facts produces hypergraph H. Bound grounding by observed entities and horizon `k`, with hard caps. Publish measured sizes; never claim a bound you did not measure. Exceeding a cap sets `grounding_capped`.

**C. Silent envelope.** For each rule with `silent_possible`, instantiate a silent rule instance only where `∀s ∈ producing_sources(τ): ¬live(s, I)`. Additionally, ~40 hand-written obligation axioms (`session.used ⇒ session.issued`, `fd.read ⇒ fd.open`, …) force silent instances when unsatisfied; each axiom gets a unit test that it **must** fire and a unit test that it **must not** fire. Define `P_min` = observed instances only, `P_max` = observed ∪ licensed silent.

**D. Reachability.** Under cut `S ⊆ A`, compute the least fixpoint over instances with `blockers & S == 0` by Dowling–Gallier unit propagation: one unsatisfied-body counter per instance, `O(Σ|body|)`.

**E. Two-sided minimal cut.** `Reach_goal` is antitone in `S` and monotone in the instance set, so `Reach(P_min) ⊆ Reach(P_max)`. Run the Reiter/MARCO hitting-set loop twice. Maintain clause DB `Ψ`; take a minimum-cardinality model of `Ψ` by branch-and-bound over u64 masks ordered by popcount; test with D; if the goal is still reachable, extract a witness tree and add the clause "any cut must hit this corridor"; repeat to fixpoint. Output `S_opt` (on `P_min`), `S_rob` (on `P_max`), and the irreducible corridors `Ψ_min`, `Ψ_max`.

The headline object is the **blindness premium** `S_rob \ S_opt`: controls needed *only because you cannot see*. Each such control names the licenses responsible. Surface this in the UI, the CLI and the paper draft.

**F. Redundancy index.** From `Ψ`: `red(i,j) = |corridors hit by both| / |corridors hit by either|`. Exact, free, scenario-scoped. No Shapley values. No approximations.

**G. Decisive observation set.** Every corridor in `Ψ_max \ Ψ_min` depends on a license set. Compute the minimum-cardinality set of `(source, window)` pairs whose liveness kills all of them: exact search to size 3; greedy beyond, with its documented `ln n + 1` bound, flagged as `greedy_cover`.

**H. Frontier.** Multiple-choice knapsack DP over `∏ L_k`, restricted to the enumerated corridors, yields the exact Pareto set of (declared cost, residual reachability). Annotate each point with its cut and evidence IDs.

3.7 CERTIFICATE

```rust
struct Cert {
    mode: Mode,                        // ROBUST | OPTIMISTIC
    cut: Vec<Atom>,
    hashes: Hashes,                    // rules, bundle, controls, liveness, goal
    seed: u64,
    k: u32,
    invariant_U: Vec<FactHash>,        // SAFE case: the closed, goal-free set
    redundancy_witnesses: Vec<Tree>,   // one per control in the cut
    psi: Vec<Clause>,
    lower_bound: u32,
    licenses_used: Vec<License>,
    flags: Flags,                      // grounding_capped, subset_minimal_only, greedy_cover
}
```

The certificate is content-addressed by BLAKE3 over its canonical serialization. The hash appears in the UI header, in the CLI output and in every artifact that cites it.

3.8 THE INDEPENDENT CHECKER

`spectra verify cert.json` is a separate **Go** module that shares **no code** with the Rust solver — no generated types, no vendored crate, no shared parser. A CI gate fails the build if the Go module imports anything generated from the Rust tree other than the normative JSON schemas.

It re-grounds from the hashed inputs and checks, in one pass:

- (a) axioms ⊆ `U`;
- (b) closure — every unblocked instance with body ⊆ `U` has head ∈ `U`;
- (c) goal ∉ `U`;
- (d) every silent instance used is licensed by `liveness.json`, whose derivation it **recomputes**;
- (e) each redundancy witness re-derives the goal under `S \ {c}` from real `EventId` leaves;
- (f) no cut smaller than `|S|` satisfies `Ψ`.

Cost `O(Σ|body| + |Ψ|·|A|)`; milliseconds on a 2k-instance scenario.

3.9 COMPLEXITY YOU MUST HONOUR AND MEASURE

| Stage | Bound | Measured artifact |
|---|---|---|
| Fixpoint | `O(Σ|body|)` | `artifacts/bench/fixpoint.json` |
| Hitting-set loop | one fixpoint + one popcount-ordered B&B per corridor found | `artifacts/bench/hittingset.json` (corridor count measured and capped, never assumed) |
| Liveness | `O(n log n)` | `artifacts/bench/liveness.json` |
| Knapsack | `O(Σ m_k · B)` | `artifacts/bench/frontier.json` |
| Checker | linear | `artifacts/bench/verify.json` |

Exact cardinality-minimality holds only for `|A| ≤ 64`. Above that the kernel **downgrades to subset-minimal and records `subset_minimal_only` in the flags**. It never silently continues claiming minimality.

3.10 GATES — THE BUILD FAILS OTHERWISE

1. Concrete simulator and kernel agree on **256 randomized control configurations per fixture**.
2. Antitonicity test over the control lattice: adding a control never increases reachability.
3. Rule-ordering determinism property test: byte-identical fixpoint output under randomized orderings.
4. A **Haskell** reference admissibility checker differentially tests the license logic against the Rust implementation.
5. Because the generator knows ground truth: **zero false ROBUST verdicts across the entire 100% → 30% degradation matrix**.
6. Z3 is a **test-only** oracle. It may not appear in any runtime dependency of the kernel, the API or the checker.

3.11 SIXTY-SECOND DEMO SCRIPT (must actually run)

Toggle controls, press **PROVE**. Header reads:

```
Minimum cut {session_binding>=bound, egress_seg>=1} — ROBUST
6 corridors · blake3:3f9a...
```

A terminal pane runs the Go checker:

```
$ spectra verify artifacts/demo/cert.json
OK: closure verified (2104 instances), goal unreachable,
    2/2 witnesses valid, no cut of size 1 satisfies Psi.  11ms
```

Untick `session_binding` → verdict flips to **UNSAFE** and the counterexample tree lights up with real event IDs. Then the blindness beat:

```
credential_rotation is in the cut ONLY because iam_audit was blind over
[t1,t2]. Enabling that one source for 40 minutes removes it.
```

Finish with the stability strip across 100% → 30% telemetry completeness.

3.12 WHAT ECLIPSE MAY NEVER CLAIM

State these limits in `docs/LIMITS.md`, in the README, in the UI footer and in the CLI `--about` output. They are requirements, not disclaimers.

1. ECLIPSE proves properties **of the model**, not of reality. Soundness is relative to the rule table, the entity resolution, the declared control catalog and the telemetry ingested. An unmodelled technique remains unmodelled.
2. "No smaller cut exists" means no smaller cut **over the declared catalog**.
3. ROBUST means "holds for every hypothesis the licenses admit under this catalog" — **not** "the attacker would have been stopped". The attacker is non-adaptive.
4. Licenses are permissions, not observations. Silent instances render as GHOST and never enter any count of observed events.
5. A perfectly suppressed event with no obligation and no blind window is invisible permanently. Publish per-dimension blind-spot volume rather than pretending otherwise.
6. Costs are user input. SPECTRA never invents a dollar figure.
7. No probabilities, no confidence scores, no cost mass. Verdicts are `ROBUST` / `OPTIMISTIC-ONLY` / `UNSAFE`.
8. Any capped grounding, subset-minimal downgrade or greedy cover must appear as a flag, and **a flagged run may never be presented as ROBUST**. Enforce this in the type system if you can, in a unit test if you cannot.
9. This is not formal verification of any real system. Do not let any doc imply that it is.

============================================================
4. SUCCESS CRITERIA AND DEFINITION OF DONE
============================================================

A third party with Docker, `make` and no prior knowledge must be able to verify this project is real by running the commands below. Everything in this section is a testable obligation.

4.1 MAKE TARGETS THAT MUST WORK FROM A COLD CLONE

| Target | Must do | Must finish in | Exit 0 means |
|---|---|---|---|
| `make bootstrap` | build all images, pin every version, no network after first pull | < 10 min | toolchain reproducible |
| `make lint` | ruff+mypy, clippy -D warnings, go vet+staticcheck, eslint, hlint, shellcheck, PSScriptAnalyzer | < 3 min | zero warnings |
| `make test` | all unit + integration tests, every language | < 12 min | all green |
| `make gates` | the six gates of 3.10 | < 15 min | all six pass |
| `make verify` | `lint` + `test` + `gates` + `audit-scope` + `audit-stubs` + `audit-llm` | < 25 min | repo is green |
| `make demo` | cold-start the stack, run scenario `lateral-01`, print cert hash, run Go checker | < 10 min | demo is real |
| `make bench` | regenerate every file under `artifacts/bench/` | < 20 min | numbers are fresh |
| `make matrix` | regenerate the 100%→30% degradation matrix | < 30 min | matrix is fresh |
| `make reproduce` | run full pipeline twice in fresh containers, diff all artifact hashes | < 30 min | byte-identical |
| `make docs-check` | fail if any doc number is stale w.r.t. its generator | < 1 min | docs honest |
| `make audit-scope` | fail on WARDEN-domain identifiers (2.6) | < 30 s | no scope drift |
| `make audit-stubs` | inventory `SPECTRA-TODO(` / `NotImplementedYet` into `docs/STATUS.md` | < 30 s | stubs disclosed |
| `make audit-llm` | fail if a model client is imported outside `spectra/narration/` | < 30 s | not an LLM wrapper |
| `make no-llm` | run `make test` with `SPECTRA_LLM=disabled` and egress blocked | < 12 min | core is LLM-free |

4.2 THE TEN-MINUTE COLD-CLONE DEMO

This exact transcript must be reproducible on a clean machine. Commit the expected shape as `docs/DEMO.md` and assert it in CI.

```
$ git clone https://github.com/<owner>/spectra-security && cd spectra-security
$ make bootstrap
[...]
bootstrap: 14 images built, 0 unpinned dependencies, offline-ready.

$ make demo
spectra: ingesting fixtures/lateral-01/ (8 sources, 41,208 records)
spectra: normalization    41,208 accepted, 0 quarantined
spectra: entity resolution  1,904 entities, 12 UNRESOLVED (reported, not guessed)
spectra: temporal stream   total order established, 0 backdating violations
spectra: state machine     7,731 transitions (7,731 OBSERVED, 0 GHOST)
spectra: liveness          8 sources, 3 BLIND windows, 1 SUPPRESSED window
spectra: grounding         2,104 rule instances, 6,918 facts (caps not hit)
spectra: silent envelope   61 licensed silent instances, 4 obligation-forced
spectra: min cut (P_min)   {session_binding>=bound}                      OPTIMISTIC
spectra: min cut (P_max)   {session_binding>=bound, egress_seg>=1}       ROBUST
spectra: blindness premium {egress_seg>=1}  <- licensed by netflow BLIND [t1,t2]
spectra: certificate       artifacts/demo/cert.json  blake3:3f9a1c...
spectra: elapsed           6.4s

$ spectra verify artifacts/demo/cert.json
OK: closure verified (2104 instances), goal unreachable,
    2/2 witnesses valid, no cut of size 1 satisfies Psi.  11ms

$ spectra replay --scenario lateral-01 --set session_binding=0
UNSAFE: goal reachable. counterexample derivation tree:
  goal: data.exported(res_7f2a, t=4188)
   +- api.broad_scope(svc_11, t=4180)   [ev_9c1a..., ev_9c1b...]
   +- session.reused(sess_44, t=4120)   [ev_71f0...]
       +- credential.cached(cred_09)     [ev_6a33...]
  all leaves are real EventIds; 0 GHOST nodes in this tree.

$ open http://localhost:5173     # toggle controls, press PROVE
```

Done means: a reviewer running these four commands sees these kinds of lines, with numbers produced by the run, not by this prompt.

4.3 ARTIFACTS THAT MUST REGENERATE

Every file below is produced by a committed script, is committed, and is regenerated byte-identically by its make target.

```
artifacts/
├── demo/
│   ├── cert.json                 # content-addressed ECLIPSE certificate
│   ├── liveness.json
│   └── verify.txt                # real Go checker output
├── bench/
│   ├── fixpoint.json             # criterion, median of >=21 runs
│   ├── hittingset.json           # corridor counts, measured
│   ├── liveness.json
│   ├── frontier.json
│   └── verify.json
├── matrix/
│   ├── degradation.csv           # completeness 100..30 x {delete,delay,dup,
│   │                             #   reorder,corrupt,suppress} x scenario
│   ├── false_robust.json         # MUST be exactly zero, always
│   └── blindness_premium.csv     # |S_rob \ S_opt| vs completeness
├── scope/
│   ├── grounding_sizes.json      # measured, with cap-hit flags
│   └── stub_inventory.json
└── BENCH_ENV.md                  # CPU, RAM, kernel, image digests, commit
```

4.4 CORRECTNESS OBLIGATIONS

1. `artifacts/matrix/false_robust.json` reports **0** false ROBUST verdicts across every cell of the degradation matrix. Any non-zero value is a build failure, never a documented caveat.
2. Simulator/kernel agreement: 256 randomized configurations per fixture, all agree, for every fixture.
3. `make reproduce` produces identical hashes for `cert.json`, `liveness.json` and every `artifacts/**` file.
4. Every corridor in a shipped certificate is independently re-derivable by the Go checker.
5. Every `GHOST` transition in any shipped output has a license, and the license's derivation is recomputed by the checker.
6. Mutation testing on `eclipse-kernel` and `spectra-state`: report the measured mutation score in `docs/STATUS.md`. Do not state a target you did not measure.

4.5 SCOPE AND HONESTY OBLIGATIONS

- `make audit-scope` green: no WARDEN-domain concept has leaked in.
- `make audit-llm` green and `make no-llm` green: the core runs with no model available.
- `docs/STATUS.md` lists every `NotImplementedYet` surface, generated by `make audit-stubs`. The README links to it.
- `docs/LIMITS.md` contains all nine items of 3.12 verbatim, and the UI footer and `spectra --about` render them from that file.
- No number anywhere in the repo is hand-typed. `make docs-check` proves it.
- The README's first screen states: the question SPECTRA answers, one pipeline diagram, one real certificate, one command.

4.6 POLYGLOT OBLIGATION

The language surface required by the project brief is only satisfied when each language has a **justified reason to exist**, recorded in `docs/POLYGLOT.md` as a table of (language, component, why this language, how it is tested, how it is built in CI). A language whose only artifact is a rewrite of logic that already exists elsewhere does not count and must be removed. CI builds and tests every listed component; `make verify` fails if any listed language has no executing test.

4.7 DEFINITION OF DONE — THE CHECKLIST

The project is done when all of the following are true and each was observed by running a command:

```
[ ] make bootstrap succeeds on a machine that has never seen the repo
[ ] make verify is green, end to end, with real pasted output
[ ] make demo completes in under 10 minutes from a cold clone
[ ] spectra verify accepts the demo certificate, in Go, sharing no code with Rust
[ ] flipping one control in the UI flips the verdict, driven by a real fixpoint
[ ] the blindness premium is non-empty on at least two fixtures and names its licenses
[ ] make reproduce yields byte-identical artifacts across two fresh containers
[ ] make matrix regenerates the degradation matrix; false_robust == 0
[ ] make bench regenerates every benchmark file; BENCH_ENV.md matches the machine
[ ] all six gates of 3.10 pass, including the Haskell differential checker
[ ] make no-llm is green: the engine works with no model provider configured
[ ] make audit-scope, audit-stubs, audit-llm, docs-check are green
[ ] docs/LIMITS.md, docs/THREAT_MODEL.md, docs/POLYGLOT.md, docs/STATUS.md,
    docs/adr/*, ARTIFACT.md and BUILD_LOG.md are current
[ ] every shipped claim in README maps to a file under artifacts/
[ ] no placeholder, no mock fallback, no fabricated output anywhere in the repo
```

If any line is unchecked, the project is not done. Do not declare it done. Report exactly which lines are unchecked and why.
