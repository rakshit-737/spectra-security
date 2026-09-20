============================================================
5. RESEARCH FRAME
============================================================

Treat SPECTRA as an experiment with a build attached, not a product with a README attached. Everything in this section is machine-checkable. Implement the registry, the bindings, and the gate before implementing the pipeline they describe.

5.1 PRIMARY RESEARCH QUESTION

RQ0. Given an evidence-bounded reconstruction of a security incident — where some telemetry is absent, delayed, duplicated, reordered, corrupted, or deliberately suppressed — can a deterministic kernel compute a cardinality-minimal set of security controls that provably severs every attack path to the objective under *every* hypothesis the missing telemetry admits, and emit a certificate that an independently written checker validates in one linear pass?

Decompose RQ0 into exactly three measurable sub-claims and keep them separated everywhere in the codebase, the UI, and the paper:
- (a) computability — the kernel terminates within declared bounds on the declared fixture set;
- (b) soundness-relative-to-model — the certificate's claims survive independent re-checking;
- (c) informativeness — the ROBUST cut is not trivially "enable everything", and the blindness premium `S_rob \ S_opt` is non-empty on a measurable fraction of degraded runs.

Never report (a), (b), (c) as a single aggregate score. There is no "SPECTRA score". Do not invent one.

5.2 SECONDARY RESEARCH QUESTIONS

RQ1 (degradation). How does reconstruction quality degrade as telemetry completeness falls from 100% to 30%? Specifically: at what completeness level does the optimistic cut `S_opt` and the robust cut `S_rob` first diverge, and how does `|S_rob \ S_opt|` grow?

RQ2 (blindness premium). Which controls appear in the cut *only* because of blind or suppressed sensor windows, and can the responsible licenses always be named down to a concrete (source, interval, witness EventId) triple?

RQ3 (decisive observation). Is the minimum set of additional log sources that collapses the remaining ambiguity small and stable? Concretely: over the fixture corpus, what is the distribution of `|D|` where D is the decisive observation set from stage G of the ECLIPSE pipeline, and how often does exact search to size 3 succeed before the greedy `ln n + 1` fallback engages?

RQ4 (control redundancy). Does the exact corridor-based redundancy index `red(i,j)` identify control pairs that are substitutable within a scenario, and does the substitutability judgement remain stable across seeds for the same scenario family?

RQ5 (adversarial suppression). When the attacker actively suppresses telemetry rather than merely losing it, does ECLIPSE degrade to a *larger, still-sound* cut, or does it fail silently? Required outcome: larger-and-sound. Any silent failure is a defect, not a finding.

5.3 HYPOTHESES

State each hypothesis in the registry file. Do not state a hypothesis anywhere else in prose without linking to its ID.

H0 (PRIMARY). For every fixture in the corpus, at every completeness level in the 100%→30% matrix, the certificate emitted in ROBUST mode never asserts goal-unreachability for a configuration in which the generator's ground-truth attack path actually completes. Formally: zero false ROBUST verdicts, corpus-wide.

H1. `E[|S_rob|] - E[|S_opt|]` is strictly increasing in telemetry loss over the matrix, and is zero at 100% completeness with the full sensor set enabled.

H2. Every control in `S_rob \ S_opt` is attributable to at least one License, and re-running with those licenses' sources made live removes that control from the robust cut in at least 80% of attributed instances.

H3. The decisive observation set has `|D| <= 3` for at least half of the degraded runs that exhibit a non-empty blindness premium.

H4. The Go checker's verification cost is linear in `Σ|body| + |Ψ|·|A|` in measured wall time, and completes in under 50 ms on fixtures of ≤ 2,000 rule instances on the declared reference machine.

H5. The concrete simulator and the ECLIPSE kernel agree on the reachability verdict for 256 randomized control configurations per fixture, with zero disagreements.

H6. Suppression-aware liveness (Blind vs Suppressed basis) yields a strictly smaller admissible hypothesis set than treating all gaps as Blind, measured as a reduction in the number of licensed silent rule instances, without ever producing a verdict that contradicts ground truth.

5.4 FALSIFIERS

Every hypothesis must carry an explicit, pre-registered falsifier. Wire the falsifier into CI: when a falsifier triggers, CI fails loudly and the result is recorded in `research/results/falsifications/` rather than deleted.

| ID | Falsified when |
|----|----------------|
| H0 | One ROBUST certificate exists whose goal was reached by the generator's ground-truth path under the certificate's own cut. A single instance falsifies H0. No tolerance, no averaging. |
| H1 | The premium is non-monotone across three or more adjacent completeness levels on more than 20% of fixtures, or is non-zero at 100% completeness with full sensors. |
| H2 | Any control in the premium cannot be attributed to a License, or attribution-driven re-runs remove the control in fewer than 80% of attributed instances. |
| H3 | Median `|D|` exceeds 3, or exact search to size 3 succeeds in under 25% of applicable runs. |
| H4 | Measured checker time is super-linear in the declared cost model (fitted exponent > 1.2 over the size sweep), or p95 exceeds 50 ms at 2k instances. |
| H5 | One disagreement between simulator and kernel on any configuration. One is enough. |
| H6 | Suppression-aware liveness produces a verdict that contradicts ground truth, or produces no reduction in licensed silent instances on any fixture where a chain break localizes deletion. |

5.5 RESEARCH REGISTRY (required artifact)

Create `research/questions.toml`. It is the single source of truth. Nothing in the README, the UI, the paper draft, or any docstring may state a numeric research claim that is not bound here.

```toml
schema_version = 1

[[question]]
id = "RQ1"
text = "How does reconstruction quality degrade from 100% to 30% telemetry completeness?"
hypotheses = ["H1"]

[[hypothesis]]
id = "H1"
statement = "E[|S_rob|] - E[|S_opt|] is strictly increasing in telemetry loss and zero at 100% completeness."
prereg_date = "SET-AT-FIRST-COMMIT"
falsifier = "Non-monotone across >=3 adjacent levels on >20% of fixtures, or non-zero premium at 100%."
status = "UNMEASURED"          # UNMEASURED | SUPPORTED | FALSIFIED | INCONCLUSIVE
metric = "blindness_premium_mean"
produced_by = "spectra bench degradation --corpus fixtures/core --levels 100:30:10 --seed 20260101"
artifact = "research/results/degradation/{run_hash}/premium.json"
artifact_field = "$.by_level[*].premium_mean"
sample_size_min = 40
reference_machine = "machines/ref-a.toml"
```

Rules for the registry:
1. `status` starts at `UNMEASURED` for every hypothesis and may only be changed by `spectra research ingest`, never by hand. Reject hand edits in CI by comparing against the last ingest record.
2. `produced_by` must be a command that runs offline, in the lab container, from a pinned seed, and is byte-identical on re-run.
3. `artifact_field` is a JSONPath into a real output file. If the path does not resolve, CI fails.
4. A hypothesis with `status = "UNMEASURED"` may not be cited as a result anywhere. The claim linter enforces this.

5.6 CLAIM LINTER (required gate)

Implement `spectra research verify-claims`. It scans `README.md`, `docs/**/*.md`, the paper draft, and all UI string tables for numeric claims and for the marker syntax `[[H1]]`. Expected transcript:

```
$ spectra research verify-claims --strict
scanning 41 markdown files, 3 UI string tables ...
README.md:88   claim "premium grows from 0 to 2.4 controls"  -> [[H1]]  status=SUPPORTED  artifact ok (run 9c1f..)
docs/eclipse.md:210 claim "checker runs in 11 ms"            -> [[H4]]  status=SUPPORTED  artifact ok (run 9c1f..)
docs/eclipse.md:244 claim "usually under three log sources"  -> UNBOUND NUMERIC CLAIM
ui/strings/en.json:panel.premium "typically 2-3 controls"    -> UNBOUND NUMERIC CLAIM
FAIL: 2 unbound numeric claims, 0 stale bindings, 0 hand-edited statuses
```

Exit non-zero on any unbound claim. This gate runs in the default CI job. Do not make it optional, do not add a `--allow-unbound` escape hatch.

5.7 NOTHING IS PROVEN UNTIL MEASURED

Write this paragraph into `README.md` verbatim and keep it above the fold:

> Every quantitative statement in this repository is produced by executing the pinned command recorded next to it in `research/questions.toml`, on synthetic data generated by a seeded generator in this repository, inside an offline container. Hypotheses that have not been measured are labelled UNMEASURED and are not results. Hypotheses that were falsified remain in the registry with status FALSIFIED and their evidence is kept. No number in this repository was typed by a human or produced by a language model.

Negative requirements for this section:
- Do NOT write expected results into documentation before the measurement exists.
- Do NOT pre-fill `status` with `SUPPORTED`.
- Do NOT report a mean without n, seed set, and dispersion (report min/median/max and IQR; no standard deviation on non-normal corridor counts).
- Do NOT compare SPECTRA to any commercial product, benchmark, or published number you cannot re-run offline in this repository.
- Do NOT use the words "accuracy", "detection rate", "precision", or "recall" for ECLIPSE outputs. ECLIPSE emits verdicts and cuts, not classifications. The optional ML anomaly baseline is the only place those words are permitted, and there they must be scoped to that baseline by name.

5.8 SCOPE OF THE CLAIM (state up front, everywhere)

Bind this scope statement into the certificate renderer, the UI footer, the README, and `LIMITATIONS.md` (section 8):

```
SCOPE: All data is synthetic, generated by seeded generators in this repository.
       All systems are simulated. No real host, network, account, or log source was observed.
       Results characterise the behaviour of SPECTRA's model under SPECTRA's own generator.
       External validity to production environments is UNMEASURED and is not claimed.
       Verdicts are properties of the model: the rule table, the entity resolution,
       the declared control catalog, and the ingested telemetry. Nothing else.
```

External validity limits to state before any result, not after:
1. The generator and the rule table were written by the same author. Correlated blind spots are expected and are not measured away by any experiment in this repository.
2. Real telemetry loss is not i.i.d. and not uniformly distributed across sources; the degradation matrix applies parameterised loss models (see the degradation harness) which are stipulated, not fitted to field data.
3. The attacker is non-adaptive: it does not observe SPECTRA and does not re-plan against the control configuration under test.
4. Control semantics are declarative approximations of real control behaviour, authored in `controls.toml`. A real MFA deployment is not the modelled MFA guard.
5. The corpus is small by design (tens of scenario families). No claim of statistical generalisation to "attacks" as a population is made or permitted.

============================================================
6. THREAT MODEL
============================================================

The threat model is an input to the code, not a narrative. Encode it as `threat/model.toml`, load it into the generator and into the rule linter, and fail the build when a scenario or rule references a capability the model does not declare.

6.1 ASSETS

| ID | Asset | Why it matters | Where it lives |
|----|-------|----------------|----------------|
| AS1 | Identity principals and their credential material | Root of the privilege dimension | identity store (simulated) |
| AS2 | Session tokens and their bindings | Primary lateral-movement vehicle | session service (simulated) |
| AS3 | Privilege grants and role bindings | Escalation target | RBAC store (simulated) |
| AS4 | Service accounts and workload identities | Highest blast radius, weakest observation | workload plane (simulated) |
| AS5 | Protected resource (the attacker objective) | Defines the goal atom | resource plane (simulated) |
| AS6 | The telemetry bundle itself | Its integrity is what ECLIPSE licenses depend on | `bundle.jsonl` + BLAKE3 chain |
| AS7 | The certificate and its inputs' hashes | Integrity of the claim | `cert.json` |

AS6 and AS7 are first-class. An attacker who edits telemetry attacks the reconstruction, not just the system.

6.2 ATTACKER CAPABILITIES

Declare capabilities as an explicit closed set. The generator may only emit steps whose required capabilities are listed.

```toml
# threat/model.toml
schema_version = 1
profile = "INSIDER_FOOTHOLD_NONADAPTIVE"

[capabilities]
C1_credential_theft       = true   # obtain a valid credential for a non-admin principal
C2_session_replay         = true   # reuse a token from a different device/network context
C3_token_forgery_weak     = true   # only where a control level permits unsigned/long-lived tokens
C4_privilege_request      = true   # drive a legitimate privilege-elevation workflow
C5_lateral_auth           = true   # authenticate to a second service with obtained material
C6_service_account_abuse  = true   # assume a workload identity reachable from a compromised host
C7_api_enumeration        = true   # enumerate resources via modelled API surface
C8_process_exec           = true   # execute a process on a compromised host (simulated only)
C9_network_egress_attempt = true   # attempt egress; success depends on segmentation level
C10_log_tamper            = true   # see 6.6
C11_time_manipulation     = true   # backdate emitted timestamps within a bounded skew
```

6.3 ATTACKER LIMITATIONS (hard, enforced)

The attacker CANNOT:
- L1. Break cryptographic primitives. BLAKE3 chain forgery is out of scope; a break of the chain is always detectable.
- L2. Observe SPECTRA, the control configuration under test, the rule table, or any certificate. The attacker is non-adaptive; it does not re-plan against defences. Every replay uses the *same* attacker plan.
- L3. Modify the control configuration. Controls are defender-side state.
- L4. Compromise the collector's private signing state or the manifest hash. Tampering happens upstream of the sealed bundle, never after sealing.
- L5. Suppress telemetry from more sources than the profile's `max_suppressed_sources` budget, and never retroactively for records already chained and flushed.
- L6. Exceed `max_clock_skew_s` when backdating. Backdating beyond that bound is detected by the difference-constraint pass in stage A of the ECLIPSE pipeline.
- L7. Exist outside the lab. There is no external network, no real target, no real malware. See section 8.

Encode L5 and L6 as numeric budgets in the profile and assert them in the generator with a panic on violation, not a warning.

6.4 TRUST BOUNDARIES

```
                         EXTERNAL WORLD  (absent by construction: no route exists)
                                  x
  ==============================  x  ==========================================
                                  x
  +---------------------------------------------------------------------------+
  |  LAB NETWORK  docker network: internal=true, no gateway, no DNS egress     |
  |                                                                           |
  |   +-------------------- SIMULATED ENTERPRISE (untrusted) ---------------+  |
  |   |                                                                     |  |
  |   |  [identity]  [session]  [rbac]  [workload]  [api]  [resource]       |  |
  |   |      |          |         |         |         |        |            |  |
  |   |      +----------+----+----+---------+----+----+--------+            |  |
  |   |                      |                  |                          |  |
  |   |            ATTACKER SIM (plan-driven, non-adaptive)                 |  |
  |   |            capabilities C1..C11, budgets L5/L6                      |  |
  |   +---------------------|-----------------------|---------------------- +  |
  |                         |  emits raw records    |  tamper ops (C10/C11) |  |
  |  == TB1 =================v=======================v=====================  |  |
  |   +------------------- COLLECTION PLANE (semi-trusted) ---------------+  |  |
  |   |  per-source sequence numbers + BLAKE3 hash chain + seal           |  |  |
  |   |  AFTER SEAL: records are immutable; L4 holds                      |  |  |
  |   +-------------------------------|-----------------------------------+  |  |
  |  == TB2 ========================= v ====================================  |  |
  |   +------------------ SPECTRA CORE (trusted, deterministic) ----------+  |  |
  |   |  ingest -> entity resolution -> state reconstruction              |  |  |
  |   |  ECLIPSE: liveness -> grounding -> silent envelope -> cuts        |  |  |
  |   +-------------------------------|-----------------------------------+  |  |
  |  == TB3 ========================= v ====================================  |  |
  |   +-------- CERTIFICATE (content-addressed, self-describing) --------+   |  |
  |   +-------------------------------|----------------------------------+   |  |
  |  == TB4 ========================= v ====================================  |  |
  |   +--- INDEPENDENT CHECKER (Go, shares no code with the Rust kernel) -+   |  |
  |   +-------------------------------|----------------------------------+   |  |
  |  == TB5 ========================= v ====================================  |  |
  |   +--- UI / LLM NARRATION (untrusted for correctness, read-only) -----+   |  |
  +---------------------------------------------------------------------------+
```

Boundary obligations:

| Boundary | Crossing | Obligation enforced in code |
|----------|----------|------------------------------|
| TB1 | raw records enter collection | Every record gets `(source_id, seq, prev_hash, hash)`. Missing or non-contiguous `seq` is preserved, never repaired. |
| TB2 | sealed bundle enters core | Manifest hash verified before any parsing. Refuse to run on an unverified bundle. |
| TB3 | core emits certificate | Certificate embeds hashes of rules, bundle, controls, liveness, goal, plus seed and horizon k. |
| TB4 | checker consumes certificate | Checker re-derives liveness from the hashed bundle. It trusts no field it can recompute. |
| TB5 | UI/LLM consume results | LLM receives already-computed structures only. It may not alter a verdict, a cut, an EventId, or a count. |

6.5 IN-SCOPE VS OUT-OF-SCOPE ATTACKS

| In scope | Out of scope (and why) |
|----------|------------------------|
| Credential theft leading to session establishment | Exploitation of memory-safety bugs in real software (no real software is attacked) |
| Session replay across device/network context | Malware execution, packing, evasion (no real malware; see section 8) |
| Token misuse under weak expiry/binding | Supply-chain compromise of packages or build systems (that is WARDEN's domain; do not model it here) |
| Privilege escalation via approval-workflow abuse | CVE-specific exploitation and vulnerability scoring |
| Service-account assumption and workload identity abuse | Phishing content generation, social engineering payloads |
| Lateral authentication across simulated services | Physical attacks, supply of hardware implants |
| API enumeration and abuse of over-broad scopes | Cryptographic attacks on primitives (L1) |
| Egress attempts subject to segmentation level | Attacks on SPECTRA's own hosting infrastructure |
| Telemetry deletion, delay, duplication, reorder, corruption, suppression, backdating | Adaptive attackers that observe defences and re-plan (L2) |

Write this table into `threat/SCOPE.md` and have the rule linter reject any rule whose provenance note names an out-of-scope technique.

6.6 THE "ATTACKER ALSO MANIPULATES TELEMETRY" SUB-MODEL

This sub-model is what makes ECLIPSE's licenses meaningful. Implement the tamper operators as a typed, seeded, replayable transform over the pre-seal record stream.

| Op | Name | Effect | Detectable? | ECLIPSE consequence |
|----|------|--------|-------------|---------------------|
| T1 | DROP | remove records from source s in window w | Yes if chain `seq` gap survives; No if the source itself never emitted | gap -> SUPPRESSED (chain break) or BLIND (no emission expected) |
| T2 | DELAY | shift arrival, preserve event time | Via inter-arrival > q99(s) | BLIND window unless bracketed |
| T3 | DUPLICATE | repeat records with identical content | Yes, idempotent ingest dedupes by `(source,seq,hash)` | no license; must not inflate any count |
| T4 | REORDER | permute arrival order | Yes | no license; reconstruction must be order-invariant |
| T5 | CORRUPT | mutate a field, breaking the chain hash | Yes, always | record quarantined; window treated as SUPPRESSED |
| T6 | SUPPRESS | targeted deletion aligned to the attack path | Partially: chain break localizes it | SUPPRESSED basis, narrower license than BLIND |
| T7 | BACKDATE | emit with a timestamp earlier than causally possible | Via difference-constraint (Bellman–Ford) negative cycle | license VOIDED; the window may not license silent steps |

Requirements:
1. Tamper ops are applied by a separate component with its own seed, recorded in the run manifest. The tamper log is ground truth and is NEVER given to the reconstruction path. Enforce this with a module boundary and a test that fails if the reconstruction crate can even import the tamper crate.
2. T3 and T4 must produce byte-identical reconstruction output to the untampered run. That is a property test, not an aspiration.
3. T1/T2/T5/T6 must produce output that is *at least as conservative*: the robust cut may grow, the verdict may move ROBUST -> OPTIMISTIC-ONLY -> UNSAFE, and it may never move toward a stronger claim than the untampered run.
4. T7 must void, never merely weaken, any license whose interval depends on the backdated record.
5. Suppression that leaves no chain gap, no obligation violation, and no blind window is permanently invisible. Do not pretend otherwise. Publish per-dimension blind-spot volume in `liveness.json` and surface it in the UI.

6.7 ASSUMPTIONS (state them; test the testable ones)

- A1. Per-source sequence numbering and hash chaining exist in the collection plane. Without them, SUPPRESSED cannot be distinguished from BLIND, and ECLIPSE degrades to all-BLIND. Implement and test that degraded mode explicitly.
- A2. Clocks are monotone per source and skew is bounded by `max_clock_skew_s`. Violations are detected, not assumed away.
- A3. Entity resolution is correct enough that a single real principal is not split across two `EntityId`s within a scenario. Measure resolution error against generator ground truth and publish it; do not assume it is zero.
- A4. The control catalog is complete *as declared*. Cut minimality is over the catalog only.
- A5. The rule table is monotone and delete-free. Enforced by the linter, not by convention.
- A6. Costs are user-authored. SPECTRA never invents a cost. Absent `costs.toml`, the frontier reports cardinality only.

============================================================
7. SYSTEM MODEL AND FORMAL SEMANTICS
============================================================

Implement this section as code and as documentation simultaneously. Every definition below must have (i) a named type in the Rust core, (ii) a row in the schema, and (iii) at least one property test. Notation is plain text; render it identically in `docs/semantics.md` and in code comments.

7.1 NOTATION

| Symbol | Reading | Type in code |
|--------|---------|--------------|
| `T` | discrete time index set, `T = {0,1,...,N}` | `u64` tick |
| `E` | finite set of entities | `EntityId(u32)` |
| `Ty` | entity types | `enum EntityType` |
| `D` | dimension set | `enum Dimension` |
| `V_d` | value domain of dimension d | per-dimension enum |
| `sigma` | security state | `State` |
| `Act` | action alphabet | `enum Action` |
| `delta` | transition function | `fn step(...)` |
| `Obs` | observation alphabet (event records) | `Event` |
| `omega` | observation function | sensor model |
| `Src` | sensor sources | `SourceId(u16)` |
| `gamma` | control configuration | `Config` (level vector) |
| `L_k` | ordered levels of control k | `0..=m_k` |
| `A` | threshold literal atom set | `u64` bitmask |
| `P` | Horn program (rule instances) | `Vec<RuleInst>` |
| `lfp` | least fixpoint | Dowling–Gallier pass |

7.2 ENTITIES AND STATE

Definition 1 (Entity universe).
```
E = E_id U E_sess U E_cred U E_proc U E_host U E_svc U E_res U E_dev
type: ty : E -> Ty
```
Entities are created but never destroyed within a run; destruction is modelled as a state change, never as removal. This is what makes time-indexing sound.

Definition 2 (Dimensions). SPECTRA models security state across ten dimensions:
```
D = { identity, session, credential, privilege, process,
      network, api, service, resource, trust }
```

Definition 3 (Security state). A security state is a total function
```
sigma : E x D -> V_d  U  {undef}
```
with `sigma(e,d) = undef` when dimension d does not apply to `ty(e)`. Applicability is a static table `applies : Ty x D -> bool`; a state that assigns a defined value where `applies` is false is ill-formed and must be rejected by a constructor invariant, not by a runtime check in business logic.

Definition 4 (System). A system is
```
Sys = (E, D, Sigma, Act, delta, sigma_0)
```
where `Sigma` is the set of well-formed states and `sigma_0` is the seeded initial state emitted by the generator.

Persist it:

```sql
-- entities are append-only; state is time-indexed, never updated in place
CREATE TABLE entity (
  entity_id     INTEGER PRIMARY KEY,
  entity_type   TEXT    NOT NULL CHECK (entity_type IN
                  ('identity','session','credential','process','host',
                   'service','resource','device')),
  natural_key   TEXT    NOT NULL,
  first_tick    BIGINT  NOT NULL,
  run_id        UUID    NOT NULL,
  UNIQUE (run_id, natural_key)
);

CREATE TABLE state_assign (           -- one row per (entity, dimension, tick)
  run_id        UUID    NOT NULL,
  entity_id     INTEGER NOT NULL REFERENCES entity(entity_id),
  dimension     TEXT    NOT NULL,
  tick          BIGINT  NOT NULL,
  value         TEXT    NOT NULL,
  caused_by     BIGINT  NULL,          -- transition_id; NULL only for sigma_0
  PRIMARY KEY (run_id, entity_id, dimension, tick)
);

CREATE TABLE transition (
  run_id        UUID    NOT NULL,
  transition_id BIGINT  NOT NULL,
  tick          BIGINT  NOT NULL,
  action        TEXT    NOT NULL,
  actor         INTEGER NOT NULL REFERENCES entity(entity_id),
  guard_hash    CHAR(64) NOT NULL,     -- hash of the guard AST node that admitted it
  ground_truth  BOOLEAN NOT NULL,      -- generator-side only; never read by reconstruction
  PRIMARY KEY (run_id, transition_id)
);

CREATE TABLE event (
  run_id        UUID    NOT NULL,
  event_id      BIGINT  NOT NULL,
  source_id     INTEGER NOT NULL,
  seq           BIGINT  NOT NULL,
  event_time    BIGINT  NOT NULL,      -- claimed
  arrival_time  BIGINT  NOT NULL,      -- observed by collector
  prev_hash     CHAR(64) NOT NULL,
  self_hash     CHAR(64) NOT NULL,
  payload       JSONB   NOT NULL,
  PRIMARY KEY (run_id, event_id),
  UNIQUE (run_id, source_id, seq)
);
```
`transition.ground_truth` exists so experiments can be scored. Enforce with a database role and a code-level lint that the reconstruction path never selects that column. A test must fail if it does.

7.3 TRANSITIONS AND CONTROLS

Definition 5 (Transition). A transition is a tuple
```
tau = (t, a, actor, args)    with t in T, a in Act
```
and the system evolves by
```
delta : Sigma x Act x Config -> Sigma U {blocked}
sigma_{t+1} = delta(sigma_t, a_t, gamma)
```

Definition 6 (Control configuration). Controls are `c_1..c_n` with ordered levels `L_k = {0..m_k}`; a configuration is `gamma in prod_k L_k`. Threshold literals are
```
x_{k,l} == [ gamma_k >= l ],   with   x_{k,l+1} -> x_{k,l}
```
The atom set is `A = { x_{k,l} }`, `|A| <= 64`, packed into one `u64`. Above 64 atoms the kernel downgrades to subset-minimal and sets the flag; it never silently continues claiming cardinality minimality.

Definition 7 (Control blocks a transition). Each action `a` has a guard expression `g_a` over `A` and over state predicates, authored once in `rules.toml` and compiled into BOTH the concrete simulator and the ECLIPSE kernel from a single guard AST.
```
blocked(a, sigma, gamma)  iff  NOT eval(g_a, sigma, gamma)
```
A control c_k *blocks* transition tau at level l iff
```
delta(sigma, a, gamma) != blocked   AND   delta(sigma, a, gamma[c_k := l]) == blocked
```
At the kernel level this is represented negatively, as a blocker mask on each rule instance:
```
instance i is enabled under cut S  iff  (i.blockers & S) == 0
```
where S is the bitmask of threshold literals raised by the configuration.

Lemma 1 (Antitonicity). If `S ⊆ S'` then `Enabled(S') ⊆ Enabled(S)` and hence `Reach(S') ⊆ Reach(S)`.
Proof obligation: property test `tests/prop_antitone.rs` — sample 10^4 random `(S, S')` pairs with `S ⊆ S'` over the corpus and assert containment. Failure is a build failure.

Lemma 2 (Guard-AST agreement). For every fixture and every one of 256 randomized configurations, the concrete simulator's reachability of the goal equals the kernel's `goal ∈ lfp(Enabled(S))`.
Proof obligation: gate in CI; this is H5.

ASCII view of the session dimension as a state machine (one dimension of ten; author the other nine in the same form):

```
        issue                 bind_ok              use
 NONE --------> ISSUED_UNBOUND -------> BOUND -----------> ACTIVE
   ^                |     |                                  |
   |                |     | bind_fail [session_binding>=1]   | expire(t)
   |                |     v                                  v
   |                |   REJECTED                          EXPIRED
   |                | replay_from_new_ctx
   |                v
   |            REPLAYED  --[session_binding>=bound]--> REJECTED
   |                |
   +----------------+  revoke [credential_rotation>=1]

 Legend: [guard] = control threshold literal that can block the edge.
         Every edge is one Act; every edge compiles to one rule in rules.toml.
         There is NO edge that removes a fact: EXPIRED is a new t+1 fact,
         not a retraction of ACTIVE.
```

7.4 OBSERVATION

Definition 8 (Sensor). A sensor `s in Src` has coverage `cov(s) ⊆ Act`, an emission delay distribution, and a liveness profile.

Definition 9 (Observation function). Observation is partial and lossy:
```
omega : Tau x Src -> Obs U {bottom}
omega(tau, s) = bottom  if  a(tau) not in cov(s)
                bottom  if  the loss/tamper model dropped it
                e       otherwise, with e.event_time possibly != t(tau)
```
Definition 10 (Bundle). The ingested bundle is the multiset
```
B = { omega(tau, s) : tau in Tau, s in Src, omega(tau,s) != bottom }
```
sealed with a manifest hash. Reconstruction sees only `B` and the declared catalogs. It never sees `Tau`.

Definition 11 (Liveness). For source s and interval `I = [a,b]`:
```
live(s, I)  iff  (exists e1,e2 in B|s : e1.t <= a and e2.t >= b)
             and (no seq gap in the BLAKE3 chain of s over I)
             and (max inter-arrival over I <= q99(s) computed from this run)
```
Otherwise `I` is BLIND for s; it is SUPPRESSED when a chain break localizes deletion inside `I`. A Bellman–Ford pass over the difference-constraint graph of happens-before edges voids any license resting on a provably backdated timestamp (T7).

7.5 WHAT AN INCIDENT IS

Definition 12 (Run). A run is `R = (sigma_0, Tau, gamma)` where `Tau` is the executed transition sequence under `gamma`.

Definition 13 (Goal atom). `goal` is a ground, time-indexed atom over `(entity, dimension, value)` declared in `goal.toml`, e.g. `resource.read(res_17) @ <= t_k`.

Definition 14 (Incident). Run `R` is an incident with respect to `goal` iff
```
exists t <= k :  goal holds in sigma_t
```
An incident is therefore a property of the *run*, not of any event, alert, or score. There is no severity, no risk number, no likelihood. Do not add one.

Definition 15 (Attack path). A minimal `Tau' ⊆ Tau` such that executing `Tau'` from `sigma_0` still satisfies `goal`. The generator knows `Tau'`; reconstruction must not be given it.

7.6 WHAT RECONSTRUCTION IS

Definition 16 (Hypothesis). A hypothesis `h` is a set of rule instances — observed instances plus licensed silent instances — closed under the rule table.

Definition 17 (Evidence-consistency). `h` is evidence-consistent with bundle `B` and liveness `Lv` iff every observed instance in `h` cites real `EventId`s in `B`, and every silent instance in `h` carries a License `(s, I, basis, witness)` with `forall s in producing_sources(rule) : NOT live(s, I)` in `Lv`, or is forced by an unsatisfied obligation axiom.
```
H(B, Lv) = { h : h is evidence-consistent with (B, Lv) }
```

Definition 18 (Reconstruction). Reconstruction is the pair of programs
```
P_min = observed instances only                 (the least hypothesis)
P_max = observed  U  licensed silent instances  (the greatest hypothesis)
```
with the bracketing property
```
forall h in H(B,Lv) :  lfp(P_min) ⊆ lfp(h) ⊆ lfp(P_max)
```
This is the central structural claim of the system: universal quantification over hypotheses is replaced by two fixpoints. State it in `docs/semantics.md` as Theorem 1, prove it on paper in three lines from monotonicity of the instance set, and bind it to two tests: (i) a randomized-hypothesis sampler that draws `h` from `H(B,Lv)` and asserts the sandwich for 10^4 draws; (ii) a Haskell reference admissibility checker that differentially tests the license logic on the same draws.

Definition 19 (Verdict). Under cut `S`:
```
UNSAFE          iff goal in lfp(P_min restricted to Enabled(S))
OPTIMISTIC-ONLY iff goal not in lfp(P_min|S)  but goal in lfp(P_max|S)
ROBUST          iff goal not in lfp(P_max|S)
```
Only three verdicts exist. No probability, no confidence, no score. A run carrying any of the flags `grounding_capped`, `subset_minimal_only`, `greedy_cover` may never be presented as ROBUST — downgrade to OPTIMISTIC-ONLY and display the flag.

Definition 20 (Minimal cut).
```
S_opt = argmin { |S| : goal not in lfp(P_min|S) }
S_rob = argmin { |S| : goal not in lfp(P_max|S) }
blindness premium = S_rob \ S_opt
```
Both are computed by the Reiter/MARCO hitting-set loop over corridor clauses Ψ. Minimality is over the declared catalog and, for exact cardinality, only while `|A| <= 64`.

Definition 21 (Reconstruction quality). Because ground truth is known to the generator, define two measurable quantities and never conflate them:
```
covered(R)  = |{ tau in Tau' : some observed instance cites an event of tau }| / |Tau'|
ghosted(R)  = |{ tau in Tau' : only a silent instance covers tau }| / |Tau'|
```
Report both per degradation level. `ghosted` counts model permissions, not observations; never add it to any count of observed events.

Core signatures (Rust; keep these exact):

```rust
pub fn liveness(bundle: &Bundle, cfg: &LivenessCfg) -> Liveness;               // stage A
pub fn ground(bundle: &Bundle, rules: &RuleTable, k: Horizon)
        -> (Vec<RuleInst>, GroundingFlags);                                    // stage B
pub fn silent_envelope(obs: &[RuleInst], lv: &Liveness, rules: &RuleTable)
        -> Vec<RuleInst>;                                                      // stage C
pub fn reach(inst: &[RuleInst], cut: u64, goal: FactId) -> ReachResult;        // stage D
pub fn min_cut(inst: &[RuleInst], goal: FactId, atoms: &AtomSet)
        -> (u64, Vec<Clause>, LowerBound);                                     // stage E
pub fn redundancy(psi: &[Clause], atoms: &AtomSet) -> RedundancyMatrix;        // stage F
pub fn decisive_sources(psi_min: &[Clause], psi_max: &[Clause], lv: &Liveness)
        -> (Vec<(SourceId, Interval)>, CoverFlag);                             // stage G
pub fn frontier(psi: &[Clause], costs: Option<&Costs>) -> Vec<ParetoPoint>;    // stage H
```

Pipeline, end to end:

```
bundle.jsonl ─┐
rules.toml  ──┼─► [A liveness] ──► liveness.json ──┐
controls.toml─┤                                     │
goal.toml   ──┘                                     │
              └─► [B ground] ─► H(OR=facts, AND=instances)
                        │                            │
                        └────────► [C silent envelope]◄── licenses
                                      │        │
                                   P_min     P_max
                                      │        │
                          [E two-sided min cut via D fixpoints]
                                      │
                    S_opt, S_rob, Ψ_min, Ψ_max, lower_bound
                       │        │        │
              [F redundancy] [G decisive obs] [H frontier]
                                      │
                                   cert.json ──► Go checker (independent)
```

7.7 SEMANTIC INVARIANTS (all are tests, not comments)

- I1 Monotonicity: no rule has a delete effect. Linter rejects; test asserts rejection on a deliberately bad rule fixture.
- I2 Order-invariance: the fixpoint is byte-identical under randomized rule and instance orderings (`tests/prop_order_invariant.rs`).
- I3 Time-indexing: expiry, revocation and rotation are modelled as absence of a `t+1` derivation, never as retraction.
- I4 Sandwich: Theorem 1 above.
- I5 Ghost isolation: a silent instance may never contribute to any counter labelled "observed", may never cite a fabricated `EventId`, and must render as GHOST in every view.
- I6 Checker independence: the Go checker shares no code, no serialization library version pin, and no data structures with the Rust kernel; a CI job asserts zero shared modules and that the checker rejects a corpus of 12 hand-mutated certificates (one mutation per checked property (a)–(f)).

============================================================
8. LIMITATIONS, THREATS TO VALIDITY, AND ETHICS
============================================================

Write this section's content into the repository, not only into the paper. A limitation that lives only in a draft is not a limitation, it is marketing.

8.1 CONSTRUCT VALIDITY

| ID | Threat | Why it is real here | Mitigation implemented | Residual |
|----|--------|---------------------|------------------------|----------|
| CV1 | "Minimum cut" measures minimality over the declared catalog, not over defences that exist in reality | `controls.toml` is authored by one person | Certificate states catalog hash and control count; UI prints "minimal over 11 declared controls" | Unmodelled controls remain unmodelled; unquantifiable |
| CV2 | "Reconstruction quality" is operationalised as `covered`/`ghosted` against generator ground truth | These are not the quantity an analyst cares about | Both reported separately, never aggregated | Proxy gap stated in LIMITATIONS.md |
| CV3 | Liveness thresholds use q99 computed from the run's own data | Circular: the tampered run defines its own normal | Sensitivity sweep over q95/q99/q999 published as a table | Threshold choice remains a modelling decision |
| CV4 | A ROBUST verdict reads like a safety guarantee | Users will over-read it | Mandatory verdict footnote in every render (8.6) | Misreading is possible offline |
| CV5 | Blindness premium depends on which sources the generator models at all | Sources absent from the model cannot be blind | `liveness.json` publishes per-dimension blind-spot volume including "no source models this dimension" | Coverage of the dimension set is stipulated |

8.2 INTERNAL VALIDITY

| ID | Threat | Mitigation |
|----|--------|-----------|
| IV1 | The generator and the rule table share an author, so the rules may "know" the generator's transitions | Two defences: rules are written from the abstract action alphabet (section 7), never from generator internals; and a CI job asserts the rules crate cannot import the generator crate. State plainly that this does not eliminate the correlated blind spot. |
| IV2 | Ground truth leakage into reconstruction | `transition.ground_truth` and the tamper log are behind a module boundary with a compile-time-enforced ban; a test fails if the reconstruction crate references either |
| IV3 | Non-determinism producing flattering runs | Seeded everything; byte-identical replay gate; hash of outputs recorded per run |
| IV4 | Solver bugs producing an unsound "no smaller cut" claim | Independent Go checker re-verifies property (f); Z3 used as a test-only oracle on small instances |
| IV5 | Overfitting the fixture corpus by tuning until gates pass | Keep a held-out fixture family generated from unseen seeds; it is run only in the release job, and its results are published whether or not they are favourable |
| IV6 | Selective reporting | Falsified hypotheses remain in `research/questions.toml` with status FALSIFIED; deleting a falsification is a process violation and CI diffs the registry history |

8.3 EXTERNAL VALIDITY

State these four, verbatim, before any result is shown:
1. All telemetry is synthetic. No result here predicts behaviour on production logs, and no such prediction is claimed.
2. Loss models are stipulated parameterisations, not distributions fitted to field data. The 100%→30% matrix is a stress design, not an estimate of real loss.
3. The attacker is non-adaptive. Real adversaries observe defences. Everything ECLIPSE proves is against a fixed plan.
4. Scale is small: thousands of instances, tens of scenario families, tens of controls. The complexity bounds in the kernel section are measured over this range and extrapolation beyond it is unsupported.

8.4 THE SYNTHETIC-DATA PROBLEM

Name it as the central weakness. Then implement the partial mitigations and be explicit that they are partial.

Mitigations to implement:
- M1 Generator/consumer separation: generator, tamper engine, and reconstruction are separate crates with enforced one-way dependencies.
- M2 Adversarial fixture authoring: for each scenario family, author at least two fixtures designed by writing the *desired failure* first (e.g. "a suppression that leaves no obligation violation"), then generating data to realise it. These are expected to produce unfavourable results and must be kept.
- M3 Held-out seeds: the release job runs seeds never used during development; results are published unconditionally.
- M4 Structural realism checks: compare generated bundles against published, citable, open descriptive statistics of log streams only where such statistics exist and are reproducible offline; where none exist, say so and do not invent a comparison.
- M5 Negative controls: fixtures where no attack occurs at all. ECLIPSE must return UNSAFE=false with an empty cut and must not manufacture corridors. A non-empty cut on a negative control is a defect.
- M6 Blind-spot accounting: publish, per dimension and per run, the volume of time that no live source covers. This converts an unknown into a measured quantity even though the suppressed content stays unknown.

What M1–M6 do NOT fix, and must be written down: the generator can only produce attacks its author imagined; the rule table can only reconstruct mechanisms its author encoded; and the two were imagined by the same person. No experiment in this repository measures that gap.

8.5 SAFETY RAILS (enforced, not advisory)

1. No real targets. Every host, identity, service and resource is simulated inside the lab. There is no scanning, no probing, no exploitation of anything outside the container network.
2. No malware. No sample, no dropper, no packer, no shellcode, no exploit primitive. Process activity is a state transition in a model; it executes nothing.
3. No egress. All lab compose networks declare `internal: true`. CI runs with networking disabled after dependency fetch.

```yaml
# docker-compose.lab.yml (excerpt) — egress is structurally impossible
networks:
  lab:
    driver: bridge
    internal: true            # no gateway; no route off-host
services:
  attacker-sim:
    networks: [lab]
    dns: []                   # no resolver
    cap_drop: [ALL]
    read_only: true
    environment:
      SPECTRA_SIMULATED: "1"
```

4. Egress assertion test: a container-level test attempts DNS, TCP/443 and ICMP to a routable address and must fail on all three. If any succeeds, the build fails.
5. Simulated-only labelling. Every record, every API response, every export, every screenshot-bound UI surface carries the marker. Enforce at the type level so an unlabelled export cannot be constructed:

```json
{
  "spectra_simulated": true,
  "disclaimer": "SYNTHETIC DATA - generated by SPECTRA for research. Not observed from any real system.",
  "run_id": "9c1f0e2a-...",
  "generator_seed": 20260101,
  "manifest_hash": "blake3:3f9a..."
}
```
6. No credentials. No secret, token, key or password in the repository, including fake ones that look real. Generated credential material uses the reserved-looking prefix `SPECTRA-SYNTH-` and is validated by a pre-commit secret scanner that also rejects anything matching common real-credential formats.
7. No paid APIs, no cloud services, no network fetches at runtime. LLM narration, if enabled at all, runs against a local model and is strictly optional; with the LLM removed, every gate in this repository must still pass. Add a CI job `no-llm` that runs the full suite with narration disabled.
8. Reserved address space and documentation domains only (RFC 5737, RFC 3849, `.invalid`, `example.com`) for any address or hostname appearing in fixtures.

8.6 CLAIM DISCIPLINE FOR OUTPUT SURFACES

Every certificate render, API response and UI verdict panel must carry this footnote, unabridged:

```
This verdict is a property of the model. It holds relative to: the rule table
(blake3:..), the entity resolution, the declared control catalog (blake3:..),
and the telemetry ingested (blake3:..). "No smaller cut exists" means no smaller
cut over the declared catalog. ROBUST means the goal is underivable under every
hypothesis the licenses admit, against a non-adaptive attacker. It does not mean
the attacker would have been stopped. This is not formal verification of any real
system. Data is synthetic.
```

Forbidden outputs, enforced by a linter over UI strings, API schemas and report templates:
- risk scores, severity numbers, likelihoods, probabilities, confidence percentages, "cost mass";
- any monetary figure not supplied by the user in `costs.toml`;
- the words "guaranteed", "proven secure", "blocks all attacks", "detects";
- any count of events that includes GHOST instances;
- comparative claims about named commercial products.

8.7 RESPONSIBLE DISCLOSURE POSTURE

- SPECTRA discovers nothing about third-party software and therefore has nothing to disclose to third parties. Say so directly in `SECURITY.md`; do not perform disclosure theatre.
- If SPECTRA's own code has a vulnerability, `SECURITY.md` gives a contact and a 90-day coordinated-disclosure window.
- The attacker simulator is a plan executor over an abstract action alphabet. It contains no technique that provides uplift against a real system. Do not add one, do not accept a contribution that adds one, and state this in `CONTRIBUTING.md` as a hard rejection criterion.
- The scenario library describes attacker *state transitions*, not procedures. Never include command lines, payloads, or tooling invocations that would work outside the simulator.
- Licensing: permissive for code; fixtures and generated corpora carry the synthetic-data marker and a notice that they must not be presented as observed telemetry.

8.8 MANDATORY `LIMITATIONS.md`

Create `LIMITATIONS.md` at the repository root. Link it from the first screen of the README and from the UI footer. Build gate: CI fails if the file is absent, is shorter than 150 lines, contains a `TODO`, or is older than the newest commit touching `crates/eclipse/**` or `rules.toml` (measured by git history — a semantics change requires a limitations review).

Required skeleton:

```markdown
# LIMITATIONS

## 0. One-paragraph summary
What SPECTRA does not do, in plain language, before anything else.

## 1. Scope of every claim
(verbatim scope block from section 5.8)

## 2. What a verdict means
ROBUST / OPTIMISTIC-ONLY / UNSAFE, defined; what each does not mean.

## 3. Model-relative soundness
Rule table, entity resolution, control catalog, ingested telemetry.
Unmodelled techniques remain unmodelled.

## 4. Synthetic data
The central weakness. Mitigations M1-M6 and exactly what they do not fix.

## 5. Minimality caveats
Cardinality-minimal only for |A| <= 64. Subset-minimal downgrade and its flag.
Capped grounding and its flag. Greedy cover beyond size 3 and its ln n + 1 bound.
A flagged run is never presented as ROBUST.

## 6. Licenses are permissions, not observations
GHOST rendering. Perfectly suppressed events are permanently invisible.
Per-dimension blind-spot volume is published instead.

## 7. Attacker model
Non-adaptive. Capability set C1-C11. Budgets L5/L6. Out-of-scope attacks.

## 8. Costs
User-authored only. SPECTRA never invents a figure. No cost implies cardinality-only frontier.

## 9. No probabilities
No confidence scores, no risk ratings, no severity. Why.

## 10. Measured vs unmeasured
Table of every hypothesis with current status pulled from research/questions.toml
by `spectra research render-limitations`. Never hand-written.

## 11. Known defects and open questions
Dated, with issue links. Falsified hypotheses listed here with their evidence.

## 12. Not formal verification
SPECTRA proves properties of a model. It is not a verifier of any real system.
```

Section 10 of that file is generated, not typed:

```
$ spectra research render-limitations --check
reading research/questions.toml (7 hypotheses)
  H0 SUPPORTED   (corpus core+heldout, 1,920 runs, run 9c1f..)
  H1 SUPPORTED   (40 fixtures x 8 levels, run 9c1f..)
  H2 INCONCLUSIVE(attribution rate 0.71 < 0.80 threshold, run 9c1f..)
  H3 UNMEASURED
  H4 SUPPORTED   (p95 = 12.4 ms at 2,048 instances, ref-a)
  H5 SUPPORTED   (256 configs x 40 fixtures, 0 disagreements)
  H6 UNMEASURED
LIMITATIONS.md section 10 differs from registry -> rewriting
OK: LIMITATIONS.md is current (last semantics change 2026-09-14, review 2026-09-15)
```

8.9 NEGATIVE REQUIREMENTS FOR THIS SECTION

- Do NOT bury limitations in an appendix, a collapsed `<details>` block, or the last slide.
- Do NOT soften a limitation with a mitigation in the same sentence. State the limitation, then the mitigation, then the residual.
- Do NOT remove a falsified hypothesis, a negative result, or an unfavourable held-out run.
- Do NOT claim any form of compliance, certification, or alignment with a security standard.
- Do NOT describe SPECTRA as detecting, preventing, or stopping anything.
- Do NOT ship a demo, video, or screenshot in which the SIMULATED marker is cropped out.
