============================================================
35. BACKEND SERVICE ARCHITECTURE
============================================================

35.1 Layering. Implement exactly four layers plus two support layers. Dependencies point downward only. There are no upward imports and no sideways imports between peers at the same layer except through explicitly declared ports.

```
        HTTP (FastAPI)            CLI (typer)            Worker (arq/Redis)
              |                       |                        |
              v                       v                        v
   +---------------------------------------------------------------------+
   | ROUTERS / ADAPTERS     thin. parse, authorize, map errors, no logic  |
   +---------------------------------------------------------------------+
              |  DTOs (pydantic v2)                    ^ error mapping
              v                                        |
   +---------------------------------------------------------------------+
   | SERVICES (use cases)   orchestration, transactions, job enqueue      |
   +---------------------------------------------------------------------+
        |                    |                          |
        v                    v                          v
   +-------------------+  +------------------------+  +--------------------+
   | ENGINES (pure)    |  | REPOSITORIES (I/O)     |  | PORTS (protocols)  |
   | deterministic     |  | SQLAlchemy, Redis, FS  |  | Clock, Rng, Hasher |
   | no FastAPI, no DB |  | no domain logic        |  | BlobStore, Queue   |
   +-------------------+  +------------------------+  +--------------------+
        |
        v
   +---------------------------------------------------------------------+
   | KERNEL BRIDGES  eclipse (Rust, pyo3), simulator (Rust), agents (Go)  |
   +---------------------------------------------------------------------+
```

35.2 Directory layout. Create exactly this tree under `services/api/`.

```
services/api/spectra/
  main.py                    # FastAPI app factory only; no route bodies
  core/
    config.py                # pydantic-settings; env only; no defaults that hide misconfig
    errors.py                # SpectraError hierarchy -> HTTP mapping table
    ids.py                   # request_id, job_id, idempotency hashing
    security.py              # JWT encode/decode, scope checks
    logging.py               # structlog JSON, request_id + job_id binding
  api/v1/
    routers/{events,entities,incidents,state,graph,integrity,scenarios,
             controls,replays,counterfactuals,eclipse,bench,datasets,
             rules,meta,auth}.py
    schemas/                 # request/response DTOs only; never reused as ORM
    deps.py                  # Depends() providers: session, current_user, limiter
  services/                  # use cases: ingest, reconstruct, replay, prove, bench
  engines/                   # PURE. see 35.3
    resolve/  state/  transition/  causal/  integrity/  degrade/
    eclipse_bridge.py        # calls Rust kernel via pyo3; still pure in/out
  repositories/              # one module per aggregate; returns domain objects
  db/
    models.py  session.py  migrations/   # alembic lives here
  workers/
    worker.py  tasks/{ingest,ground,prove,replay,bench,degrade}.py
```

35.3 The dependency rule (hard gate). Engines are pure functions over frozen dataclasses and primitives.

1. No module under `spectra/engines/**` may import `fastapi`, `starlette`, `sqlalchemy`, `psycopg`, `redis`, `httpx`, `os.environ`, `datetime.now`, `random`, `uuid4`, or any `spectra.repositories.*` / `spectra.api.*`.
2. Time, randomness, hashing and file access enter engines as constructor arguments typed by protocols in `spectra/engines/ports.py`: `Clock`, `SeededRng`, `Hasher`, `BlobReader`. Production wires the real implementations; tests wire `FrozenClock(t0)`, `SeededRng(seed)`.
3. Every engine entrypoint has the shape `def run(input: FrozenInput, *, ports: Ports) -> FrozenOutput` and is total: it raises only `EngineError` subclasses, never library exceptions.
4. Enforce with `import-linter` in CI. Ship `.importlinter`:

```ini
[importlinter]
root_package = spectra
[importlinter:contract:layers]
name = SPECTRA layering
type = layers
layers =
    spectra.api
    spectra.services
    spectra.repositories
    spectra.engines
    spectra.core
[importlinter:contract:engine-purity]
name = Engines are framework-free
type = forbidden
source_modules = spectra.engines
forbidden_modules = fastapi starlette sqlalchemy redis psycopg httpx spectra.api spectra.repositories spectra.db
```

5. Additional gate: `pytest tests/engines/` must pass with `-p no:cacheprovider` in a container that has **no** Postgres and **no** Redis reachable, and with `SPECTRA_DATABASE_URL` unset. CI runs this job as `engines-offline`. If it fails to import, the build fails.
6. Done means: `lint-imports` exits 0, `engines-offline` passes, and `grep -rE "from fastapi|import sqlalchemy" services/api/spectra/engines` returns nothing.

35.4 Async vs sync boundaries. Follow this table with no exceptions.

| Layer | Mode | Rationale |
|---|---|---|
| Routers | `async def` | I/O multiplexing only |
| Services doing DB/Redis I/O | `async def`, SQLAlchemy 2.0 async session | non-blocking |
| Engines | plain `def`, CPU-bound, no awaits | must be callable from CLI, tests, workers |
| Engine call from a router | `await run_in_threadpool(...)` only if p99 < 50 ms, else enqueue | event loop must never stall |
| Kernel bridges (Rust) | sync call that releases the GIL inside pyo3 | true parallelism |
| Workers | `arq` async loop; CPU work dispatched to a `ProcessPoolExecutor` sized `min(4, cpu_count)` | isolation from the loop |

Hard limits: any synchronous call inside a router whose measured p99 exceeds 50 ms must be moved behind the queue; add a `pytest-benchmark` assertion per router that fails the build when breached. Ban `time.sleep`, blocking `requests`, and sync `psycopg` in the app package via a `flake8` custom check.

35.5 Queue design (Redis Streams, not lists). Use Redis Streams with consumer groups for at-least-once delivery, explicit `XACK`, and a dead-letter stream.

```
spectra:q:ingest      group=ingest     maxlen~ 100000   concurrency 2
spectra:q:ground      group=ground     maxlen~  20000   concurrency 2
spectra:q:prove       group=prove      maxlen~  10000   concurrency 1   # ECLIPSE kernel
spectra:q:replay      group=replay     maxlen~  20000   concurrency 4
spectra:q:bench       group=bench      maxlen~   1000   concurrency 1
spectra:q:degrade     group=degrade    maxlen~   5000   concurrency 2
spectra:dlq                                              (no trimming)
```

Belongs on a queue (unbounded or superlinear work): bundle ingestion and entity resolution; hypergraph grounding; ECLIPSE proving (hitting-set loop); the full control-replay matrix; the 100%→30% degradation matrix; benchmark suites; dataset generation. Does **not** belong on a queue (must answer synchronously, and must be indexed so it can): single-entity state lookups, state-at-time, timeline pages, graph neighbourhood reads, evidence expansion, certificate fetch, certificate *verification* of an already-computed proof (milliseconds, see section 5 of the ECLIPSE spec). Do not enqueue reads. Do not build a generic "run anything" task.

Job record: every enqueue writes a row in `job` (section 38) **in the same transaction as the domain write**, then publishes the stream entry after commit via an outbox poller. Never publish before commit.

Job states: `queued -> running -> (succeeded | failed | cancelled)`, plus `retrying`. Retries: 3 attempts, exponential backoff 2s/8s/32s, jitter ±20%, only for `TransientError`. `DeterminismError`, `ValidationError` and `CapExceeded` are terminal — never retried, because a deterministic task that failed once fails identically.

35.6 Idempotency. Mutating POSTs accept `Idempotency-Key` (client-supplied, 16–128 chars). Servers compute `fingerprint = blake3(method || path || canonical_json(body) || subject)`.

1. First request: insert `(key, fingerprint, state='in_flight')` into `idempotency_key` with a unique index on `key`. On success store `response_status`, `response_body_hash`, `job_id`, set `state='completed'`.
2. Replay with same key and same fingerprint: return the stored response with header `Idempotent-Replay: true`. Never re-execute.
3. Same key, different fingerprint: `409 IDEMPOTENCY_KEY_REUSE`.
4. Same key while `in_flight`: `409 IDEMPOTENCY_IN_FLIGHT` with `Retry-After: 1`.
5. Keys expire after 24 h; a janitor task deletes expired rows.
6. Deterministic tasks additionally carry a **content key**: `blake3(rules_hash || bundle_hash || controls_hash || goal_hash || seed || k)`. If a completed job with the same content key exists, return that result instead of recomputing, and set `"cached": true` in the envelope. This is the mechanism that makes repeated PROVE clicks free, and it must be exercised by a test that asserts byte-identical certificates.

35.7 Backpressure. Refuse work rather than degrade silently.

1. Admission control at enqueue: if `XLEN(stream) > soft_limit` (70% of maxlen) reject with `429 QUEUE_SATURATED`, `Retry-After` computed as `ceil(depth / measured_drain_rate)`, and headers `X-Queue-Name`, `X-Queue-Depth`.
2. Per-subject concurrency cap: at most 2 running `prove` jobs and 4 running `replay` jobs per user; excess returns `429 CONCURRENCY_LIMIT`.
3. Request body caps: `10 MiB` JSON, `2 GiB` streamed NDJSON upload for bundles (chunked, hashed while streaming, never buffered whole).
4. Uvicorn `--limit-concurrency` set; connection backlog bounded; `--timeout-keep-alive 5`.
5. Worker prefetch is exactly 1 stream entry per consumer. Never batch-claim CPU-bound jobs.
6. Publish `spectra_queue_depth`, `spectra_job_duration_seconds`, `spectra_admission_rejections_total` (section on observability). A load test must show: at 3x capacity the service returns 429s with a stable p99 under 200 ms and zero dropped jobs, and queue depth returns to zero after load stops.

35.8 Negative requirements. Do not put business logic in routers. Do not let a repository import an engine. Do not pass SQLAlchemy ORM objects above the repository layer — convert to domain dataclasses. Do not use Celery. Do not add a message broker other than Redis. Do not implement a plugin system, an event bus, or a generic rule-engine abstraction over engines. Do not make engines async. Do not call an LLM anywhere in `services/` or `engines/` — narration lives behind a separate, optional, clearly-marked adapter that consumes already-computed structures. Do not retry a deterministic failure. Do not silently drop a job on queue overflow.

============================================================
36. HTTP API SPECIFICATION
============================================================

36.1 Conventions.

1. Base path `/api/v1`. Version in the path only. A breaking change requires `/api/v2` and a deprecation window documented in `docs/api-versioning.md`; `/api/v1` must keep responding until removed in a tagged major release.
2. All responses are JSON, `Content-Type: application/json; charset=utf-8`. Every response carries `X-Request-Id` (echoed from the request or generated), `X-Spectra-Version`, and for computed artifacts `X-Content-Hash` (blake3 of the canonical body).
3. Timestamps are RFC 3339 with explicit offset, always UTC (`2026-03-04T11:02:31.481Z`). Durations are integer milliseconds. Never return a float where a hash or a count is meant.
4. Pagination is cursor-based: `?limit=<1..500, default 100>&cursor=<opaque>`. Responses include `{"items": [...], "next_cursor": "..."|null, "limit": 100}`. Offset pagination is forbidden on `events` and `transitions`. Total counts are returned only when `?with_total=true` and only for indexed predicates.
5. Auth is JWT (HS256 with a local secret, or RS256 with a generated local keypair), issued by `/auth/token` against local users stored in `api_user`. Passwords are argon2id. Access token 30 min, refresh token 12 h, rotating. No SSO, no external IdP, no OAuth provider.
6. Scopes: `read:telemetry`, `read:analysis`, `write:ingest`, `run:replay`, `run:prove`, `admin:datasets`, `admin:system`. Roles map to scope sets: `viewer` = read:*, `analyst` = read:* + run:*, `operator` = analyst + write:ingest, `admin` = all. Enforce with a `require_scopes(...)` dependency; a route without an explicit scope declaration fails a unit test that enumerates the router table.
7. Rate limits, per user, token bucket in Redis: default 120 req/min; `run:prove` 10/min; `write:ingest` 20/min; `/metrics` unauthenticated but bound to the loopback network. Headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
8. Input validation limits: identifiers `^[a-z0-9][a-z0-9._:-]{0,127}$`; time ranges max 90 simulated days; `limit<=500`; graph `depth<=6`; `paths` `max_paths<=200`; arrays in request bodies max 1000 elements; JSON depth max 16. Reject with `422` and a per-field error list — never truncate silently.
9. OpenAPI 3.1 is generated from the FastAPI app, written to `docs/openapi.json` by `make openapi`, and a CI job fails if the committed file differs from the generated one. Every operation has `operationId`, summary, and at least one example.

36.2 Error envelope. Exactly this shape, for every non-2xx:

```json
{
  "error": {
    "code": "GROUNDING_CAP_EXCEEDED",
    "message": "Grounding exceeded the configured instance cap.",
    "detail": {"cap": 200000, "reached": 200000, "scenario_id": "sc-lateral-02"},
    "request_id": "01JQ2W7Q8K3F0N2B7Y5ZC6M4RD",
    "doc": "https://localhost/docs/errors#grounding_cap_exceeded"
  }
}
```

| HTTP | code | when |
|---|---|---|
| 400 | `MALFORMED_REQUEST` | unparsable body / bad cursor |
| 401 | `UNAUTHENTICATED` | missing or expired token |
| 403 | `SCOPE_DENIED` | token lacks the declared scope |
| 404 | `NOT_FOUND` | unknown id |
| 409 | `IDEMPOTENCY_KEY_REUSE`, `IDEMPOTENCY_IN_FLIGHT`, `STATE_CONFLICT` | see 35.6 |
| 413 | `PAYLOAD_TOO_LARGE` | body over cap |
| 422 | `VALIDATION_FAILED` | field-level list in `detail.fields` |
| 422 | `HASH_MISMATCH` | supplied input hash does not match stored artifact |
| 429 | `RATE_LIMITED`, `QUEUE_SATURATED`, `CONCURRENCY_LIMIT` | see 35.7 |
| 500 | `INTERNAL` | never leaks a stack trace |
| 501 | `NOT_MODELLED` | requested dimension/control absent from the catalog |
| 503 | `DEPENDENCY_UNAVAILABLE` | Postgres/Redis/kernel down; `/readyz` also fails |
| 507 | `GROUNDING_CAP_EXCEEDED` | bounded grounding refused to continue |

36.3 Endpoint table. `A` = scope required.

| Method | Path | Purpose | Request | Response | Scope | Errors |
|---|---|---|---|---|---|---|
| GET | `/healthz` | liveness, no deps touched | — | `{"status":"ok"}` | none | — |
| GET | `/readyz` | DB+Redis+kernel probe | — | `ReadinessReport` | none | 503 |
| GET | `/metrics` | Prometheus text | — | text/plain | none (loopback) | — |
| GET | `/api/v1/version` | build, git sha, rules hash, kernel version | — | `VersionInfo` | none | — |
| POST | `/api/v1/auth/token` | issue tokens | `LoginRequest` | `TokenPair` | none | 401,429 |
| POST | `/api/v1/auth/refresh` | rotate refresh | `RefreshRequest` | `TokenPair` | none | 401 |
| GET | `/api/v1/auth/me` | current subject + scopes | — | `Principal` | any | 401 |
| GET | `/api/v1/datasets` | list generated datasets | query | `Page[DatasetSummary]` | read:telemetry | — |
| POST | `/api/v1/datasets` | generate seeded dataset (queued) | `DatasetGenRequest` | `JobAccepted` | admin:datasets | 409,429 |
| GET | `/api/v1/datasets/{ds_id}` | dataset detail + seed + manifest hash | — | `Dataset` | read:telemetry | 404 |
| GET | `/api/v1/datasets/{ds_id}/manifest` | canonical manifest for hashing | — | `Manifest` | read:telemetry | 404 |
| POST | `/api/v1/ingest/bundles` | stream NDJSON bundle (queued) | NDJSON body | `JobAccepted` | write:ingest | 413,422,429 |
| GET | `/api/v1/ingest/jobs/{job_id}` | ingest progress + reject reasons | — | `IngestJob` | write:ingest | 404 |
| GET | `/api/v1/events` | filter events | `?source&entity&type&from&to&cursor` | `Page[Event]` | read:telemetry | 422 |
| GET | `/api/v1/events/{event_id}` | one event, raw + normalized + chain link | — | `EventDetail` | read:telemetry | 404 |
| POST | `/api/v1/events/search` | structured predicate search | `EventQuery` | `Page[Event]` | read:telemetry | 422 |
| GET | `/api/v1/entities` | resolved entities | `?kind&q&cursor` | `Page[Entity]` | read:telemetry | — |
| GET | `/api/v1/entities/{entity_id}` | entity + current state summary | — | `Entity` | read:telemetry | 404 |
| GET | `/api/v1/entities/{entity_id}/aliases` | alias set + merge evidence | — | `AliasSet` | read:telemetry | 404 |
| POST | `/api/v1/entities/resolve:dryrun` | re-run resolution, return diff only | `ResolveRequest` | `ResolutionDiff` | read:analysis | 422 |
| GET | `/api/v1/incidents` | incidents list | `?scenario&status&cursor` | `Page[IncidentSummary]` | read:analysis | — |
| POST | `/api/v1/incidents` | open incident over a window | `IncidentCreate` | `Incident` | read:analysis | 409,422 |
| GET | `/api/v1/incidents/{id}` | incident detail | — | `Incident` | read:analysis | 404 |
| GET | `/api/v1/incidents/{id}/timeline` | ordered reconstructed timeline | `?dimension&cursor` | `Page[TimelineEntry]` | read:analysis | 404 |
| GET | `/api/v1/incidents/{id}/hypothesis` | attack hypothesis + evidence ids | — | `Hypothesis` | read:analysis | 404 |
| GET | `/api/v1/incidents/{id}/narrative` | optional LLM narration over computed structures | `?style` | `Narrative` | read:analysis | 404,501 |
| GET | `/api/v1/state/{entity_id}` | current security state, all dimensions | — | `SecurityState` | read:analysis | 404 |
| GET | `/api/v1/state/{entity_id}/at` | state at instant | `?t=<rfc3339>` | `SecurityState` | read:analysis | 404,422 |
| GET | `/api/v1/transitions` | state transitions | `?entity&dimension&from&to&cursor` | `Page[Transition]` | read:analysis | 422 |
| GET | `/api/v1/transitions/{transition_id}` | one transition + triggering events | — | `TransitionDetail` | read:analysis | 404 |
| GET | `/api/v1/graph` | causal/temporal subgraph | `?root&depth<=6&kinds` | `Graph` | read:analysis | 422 |
| GET | `/api/v1/graph/paths` | paths between two nodes | `?src&dst&max_paths<=200` | `Paths` | read:analysis | 422 |
| GET | `/api/v1/evidence/{fact_id}` | expand a fact to raw event ids | — | `EvidenceTree` | read:telemetry | 404 |
| GET | `/api/v1/integrity/sources` | per-source chain status | — | `SourceIntegrity[]` | read:analysis | — |
| GET | `/api/v1/integrity/gaps` | detected chain gaps / suppression | `?source&from&to` | `Page[Gap]` | read:analysis | 422 |
| GET | `/api/v1/integrity/liveness` | liveness windows (LIVE/BLIND/SUPPRESSED) | `?source&from&to` | `LivenessReport` | read:analysis | 422 |
| GET | `/api/v1/scenarios` | scenario catalog | — | `Scenario[]` | read:telemetry | — |
| GET | `/api/v1/scenarios/{id}` | scenario definition + ground truth handle | — | `Scenario` | read:telemetry | 404 |
| GET | `/api/v1/controls` | control catalog with levels and costs | — | `ControlCatalog` | read:telemetry | — |
| GET | `/api/v1/controls/hash` | catalog hash used by certificates | — | `{"controls_hash":"blake3:..."}` | read:telemetry | — |
| POST | `/api/v1/replays` | run scenario under a control config | `ReplayRequest` | `JobAccepted` | run:replay | 409,422,429 |
| GET | `/api/v1/replays/{id}` | replay result: terminated step, reached stages | — | `Replay` | run:replay | 404 |
| GET | `/api/v1/replays/{id}/trace` | full deterministic step trace | `?cursor` | `Page[ReplayStep]` | run:replay | 404 |
| POST | `/api/v1/counterfactuals` | baseline vs variant config pair | `CounterfactualRequest` | `JobAccepted` | run:replay | 422,429 |
| GET | `/api/v1/counterfactuals/{id}/diff` | step-level divergence point | — | `CounterfactualDiff` | run:replay | 404 |
| POST | `/api/v1/eclipse/prove` | build cut proof (queued) | `ProveRequest` | `JobAccepted` | run:prove | 422,429,507 |
| GET | `/api/v1/eclipse/proofs/{cert_id}` | verdict + cut + flags | — | `ProofSummary` | read:analysis | 404 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/certificate` | full certificate JSON, content-addressed | — | `Cert` | read:analysis | 404 |
| POST | `/api/v1/eclipse/verify` | run the independent Go checker | `Cert` or `{cert_id}` | `VerifyResult` | read:analysis | 422 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/corridors` | enumerated irreducible corridors Psi | `?cursor` | `Page[Corridor]` | read:analysis | 404 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/redundancy` | exact redundancy index matrix | — | `RedundancyMatrix` | read:analysis | 404 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/blindness-premium` | `S_rob \ S_opt` + responsible licenses | — | `BlindnessPremium` | read:analysis | 404 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/decisive-observations` | minimal (source,window) set | — | `DecisiveObservations` | read:analysis | 404 |
| GET | `/api/v1/eclipse/proofs/{cert_id}/frontier` | Pareto set (declared cost, residual reach) | — | `Frontier` | read:analysis | 404 |
| POST | `/api/v1/eclipse/counterexample` | derivation tree when a control is removed | `{cert_id, remove: Atom}` | `CounterexampleTree` | read:analysis | 404,422 |
| GET | `/api/v1/rules` | rule table with provenance notes | `?silent_possible` | `Rule[]` | read:analysis | — |
| GET | `/api/v1/rules/{rule_id}` | one rule, guard AST, producing sources | — | `Rule` | read:analysis | 404 |
| GET | `/api/v1/rules/hash` | rules_hash bound into certificates | — | `{"rules_hash":"blake3:..."}` | read:analysis | — |
| POST | `/api/v1/bench/runs` | run a benchmark suite (queued) | `BenchRequest` | `JobAccepted` | admin:system | 429 |
| GET | `/api/v1/bench/runs` | list benchmark runs | `?suite&cursor` | `Page[BenchRun]` | read:analysis | — |
| GET | `/api/v1/bench/runs/{id}` | measured numbers + environment fingerprint | — | `BenchRun` | read:analysis | 404 |
| GET | `/api/v1/degradation/matrix` | 100%→30% completeness results | `?scenario&metric` | `DegradationMatrix` | read:analysis | 404 |
| GET | `/api/v1/jobs/{job_id}` | generic job status | — | `Job` | any (owner) | 404 |
| DELETE | `/api/v1/jobs/{job_id}` | cancel a queued job | — | `Job` | owner | 404,409 |

36.4 Representative payloads.

```json
POST /api/v1/eclipse/prove
Idempotency-Key: 8e0b-prove-lateral-02-robust
{
  "scenario_id": "sc-lateral-02",
  "bundle_id": "bn_01JQ2V...",
  "mode": "ROBUST",
  "goal": "db.prod.read@any",
  "horizon_k": 12,
  "controls_profile": "baseline",
  "cost_file": null
}
-> 202
{
  "job_id": "jb_01JQ2W7Q8K",
  "content_key": "blake3:71c2a9...",
  "cached": false,
  "poll": "/api/v1/jobs/jb_01JQ2W7Q8K",
  "queue": {"name": "prove", "depth": 3}
}
```

```json
GET /api/v1/eclipse/proofs/cert_3f9a12/blindness-premium -> 200
{
  "cert_id": "cert_3f9a12",
  "mode": "ROBUST",
  "s_opt": ["session_binding>=bound", "egress_seg>=1"],
  "s_rob": ["session_binding>=bound", "egress_seg>=1", "credential_rotation>=1"],
  "premium": [
    {"atom": "credential_rotation>=1",
     "licensed_by": [{"license_id": "lic_7", "source": "iam_audit",
                      "interval": ["2026-03-04T11:02:00Z","2026-03-04T11:42:00Z"],
                      "basis": "Blind", "witness_events": ["ev_9812","ev_9840"]}]}
  ],
  "flags": {"grounding_capped": false, "subset_minimal_only": false, "greedy_cover": false}
}
```

36.5 Negative requirements. Do not expose an endpoint that returns a probability, a confidence score, a risk score, or a dollar figure the user did not supply. Do not return `ROBUST` on any response whose `flags` contain a true value — the serializer must raise if that combination is constructed. Do not implement GraphQL. Do not implement server-side sessions or cookies. Do not add a `/api/v1/query` that accepts raw SQL. Do not allow `limit=0` to mean unlimited. Do not let `/metrics` require auth, and do not bind it to `0.0.0.0`. Do not return raw exception text in `error.message`.

============================================================
37. CLI SPECIFICATION
============================================================

37.1 Shape. One binary entrypoint `spectra` (Python, typer, installed via `pipx`/`uv tool`), plus the independent Go checker exposed as `spectra verify` shelling to `spectra-verify` so that the checker shares no code with the solver. The CLI must be able to run the entire research loop with the API server down, against a local Postgres or against files only where the command says so.

```
spectra
├── lab        up | down | status | reset | logs
├── gen        dataset | scenario | degrade-matrix
├── ingest     bundle | dir | stdin
├── entities   list | show | resolve | diff
├── state      show | at | transitions | dimensions
├── investigate open | list | timeline | hypothesis | narrate
├── reconstruct run | status | explain
├── graph      show | paths | export | stats
├── replay     run | list | show | trace
├── whatif     run | matrix | prove | explain
├── controls   list | show | set | profile
├── scenario   list | show | validate
├── bench      run | list | show | compare
├── dataset    list | show | verify | export
├── verify     cert | bundle | liveness       (Go module)
├── rules      list | show | lint | hash
├── doctor
└── version
```

37.2 Global flags. `--profile <name>` (config set), `--api <url>` (omit for direct/local mode), `--json`, `--jsonl`, `--quiet/-q`, `--verbose/-v` (repeatable, `-vv` = debug), `--no-color`, `--seed <int>`, `--timeout <s>`, `--out <path>`. `--json` prints a single object; `--jsonl` prints one record per line for streaming commands. Human output is a table; it must never be parsed by scripts, and the docs say so. When stdout is not a TTY, color is off and progress bars are suppressed automatically.

37.3 Exit codes. Identical across all subcommands.

| Code | Meaning |
|---|---|
| 0 | success; for `whatif prove`, verdict ROBUST |
| 1 | unexpected internal error |
| 2 | usage error (bad flag, missing argument) |
| 3 | referenced object not found |
| 4 | validation failed (input schema, hash mismatch) |
| 5 | integrity violation detected (chain break, backdated timestamps) |
| 6 | verdict UNSAFE |
| 7 | verification failed (checker rejected a certificate) |
| 8 | result is flagged (capped grounding, subset-minimal, greedy cover) — usable but not ROBUST |
| 9 | timeout or cap exceeded |
| 10 | dependency unavailable (Docker, DB, Redis, kernel) |
| 130 | interrupted |

CI gates use these directly: `spectra whatif prove --scenario sc-lateral-02 --mode robust` in the release pipeline must exit 0, and `spectra verify cert build/cert.json` must exit 0.

37.4 Transcripts. The following fix the *shape* of the output. Every number shown is a placeholder: the implementation must print values produced by executing real code on real generated data, never a constant.

```
$ spectra lab up --profile dev
spectra 0.9.3  profile=dev
 ✓ network spectra-net
 ✓ postgres:16.3      healthy in 4.1s
 ✓ redis:7.2          healthy in 0.6s
 ✓ api                healthy in 6.8s   http://127.0.0.1:8080
 ✓ worker x2          consumers registered on 6 streams
 ✓ ui                 http://127.0.0.1:5173
lab ready. 5 services, 0 warnings.
```

```
$ spectra gen dataset --scenario sc-lateral-02 --seed 1337 --completeness 1.0 --out data/bn_lateral02
scenario   sc-lateral-02  (credential theft -> session reuse -> privilege escalation -> db read)
seed       1337           generator spectra-gen 0.9.3
sources    8   auth, iam_audit, proc_exec, netflow, api_gw, svc_acct, dns, fs_audit
writing    data/bn_lateral02/bundle.jsonl
events     41,908   span 2026-03-04T09:00:00Z .. 2026-03-04T15:00:00Z
ground truth written to data/bn_lateral02/truth.json (not ingested)
manifest   blake3:9c41e0a7b2...   bundle blake3:2d77f1c8ee...
done in 3.42s
```

```
$ spectra ingest bundle data/bn_lateral02/bundle.jsonl --jsonl | head -4
{"phase":"parse","read":10000,"rejected":0,"elapsed_ms":412}
{"phase":"parse","read":41908,"rejected":0,"elapsed_ms":1688}
{"phase":"resolve","entities":1204,"merges":337,"alias_conflicts":2,"elapsed_ms":2201}
{"phase":"commit","bundle_id":"bn_01JQ2V8H4T","events":41908,"chain_ok":8,"chain_broken":0}
```

```
$ spectra state at --entity user:a.moreno --t 2026-03-04T11:31:00Z
entity  user:a.moreno            resolved from 3 identifiers
as of   2026-03-04T11:31:00Z     (12 transitions before this instant)

dimension     value                         since                  evidence
identity      authenticated                 2026-03-04T10:58:12Z   ev_9781
session       active:sess_4f21 (unbound)    2026-03-04T10:58:14Z   ev_9783
credential    pat_7c9 valid (rotated 41d)   2026-02-01T08:00:00Z   ev_0112
privilege     role:analyst + temp:db_ro     2026-03-04T11:29:44Z   ev_9902,ev_9903
process       none                          -                      -
network       zone:corp -> zone:data        2026-03-04T11:30:51Z   ev_9915
trust         device unverified             2026-03-04T10:58:12Z   ev_9781

coverage: iam_audit BLIND [11:02:00Z,11:42:00Z] -> privilege dimension is licensed, not observed
```

```
$ spectra whatif prove --scenario sc-lateral-02 --mode robust --goal db.prod.read@any -k 12
grounding   observed 1,842 rule instances / 2,104 total (262 silent, 7 licenses)
liveness    8 sources: 6 LIVE, 1 BLIND(iam_audit), 1 SUPPRESSED(fs_audit seq gap @ 11:18Z)
fixpoint    P_min reach=goal  P_max reach=goal
corridors   6 irreducible (Psi_min 4, Psi_max 6)
S_opt       {session_binding>=bound, egress_seg>=1}                        |S|=2
S_rob       {session_binding>=bound, egress_seg>=1, credential_rotation>=1} |S|=3
premium     credential_rotation>=1   <- licensed by iam_audit BLIND [11:02Z,11:42Z]
verdict     ROBUST        flags: none
cert        build/cert_3f9a12.json   blake3:3f9a12c70b...
elapsed     1.91s
$ echo $?
0
```

```
$ spectra verify cert build/cert_3f9a12.json --verbose
spectra-verify 0.9.3 (go1.22, independent implementation)
  inputs    rules blake3:aa41.. bundle blake3:2d77.. controls blake3:71b0.. liveness blake3:5e93..
  regrounded 2,104 instances in 6ms
  (a) axioms subset of U                     OK    (118 axioms)
  (b) closure under unblocked instances      OK    (2,104 checked)
  (c) goal not in U                          OK    (db.prod.read@any absent)
  (d) silent instances licensed              OK    (262 instances, 7 licenses recomputed)
  (e) redundancy witnesses re-derive goal    OK    (3/3, leaves are real EventIds)
  (f) no cut of size < 3 satisfies Psi       OK    (searched 3,272 masks)
OK: certificate valid. 11ms
$ echo $?
0
```

```
$ spectra whatif run --scenario sc-lateral-02 --set session_binding=off --set egress_seg=1 --json
{
  "replay_id": "rp_01JQ2X3B9M",
  "deterministic": true,
  "config_hash": "blake3:c19e7d...",
  "stages_reached": ["initial_access","credential_theft","session_reuse","privilege_escalation"],
  "terminated_at": {"stage":"lateral_movement","step":41,
                    "blocked_by":"egress_seg>=1","fact":"net.flow(zone:corp->zone:data)"},
  "goal_reached": false,
  "steps": 41,
  "elapsed_ms": 88
}
$ echo $?
0
```

```
$ spectra bench run --suite reconstruct --repeat 5 --json | jq -r '.cases[] | "\(.name)\t\(.p50_ms)\t\(.p99_ms)"'
ingest_41k_events       1688    1902
entity_resolution_1204  2201    2410
grounding_2104_inst     614     702
fixpoint_Pmax           9       12
hitting_set_6_corridors 1310    1588
checker_go              11      14
```

```
$ spectra doctor
docker            28.0.1                     OK
compose plugin    v2.29.7                    OK
postgres          16.3 reachable             OK
redis             7.2 reachable              OK
rust kernel       spectra-eclipse 0.9.3      OK  (abi matches pyo3 bindings)
go checker        spectra-verify 0.9.3       OK
rules.toml        142 rules, hash aa41c8..   OK
controls.toml     11 controls, 27 atoms      OK  (|A|=27 <= 64, exact minimality available)
clock skew        host vs container 0.3s     OK
disk              14.2 GiB free              OK
2 notes:
  - dataset data/bn_old01 manifest hash mismatch; regenerate or delete
  - SPECTRA_LLM_NARRATION unset; narration disabled (core unaffected)
$ echo $?
0
```

37.5 Negative requirements. Do not print a verdict without the flag line. Do not colorize a verdict in a way that survives `--no-color`. Do not make `--json` output differ in field names from the HTTP API models. Do not add an interactive TUI wizard. Do not make any command silently regenerate a dataset whose hash mismatches — fail with exit 4. Do not implement `spectra verify` in Python. Do not add a `--force` flag that bypasses integrity checks.

============================================================
38. DATABASE SCHEMA
============================================================

38.1 Conventions. PostgreSQL 16. Schema `spectra`. All identifiers snake_case, tables singular. Surrogate keys are `BIGINT GENERATED ALWAYS AS IDENTITY`; public identifiers are ULID-like `TEXT` (`ev_`, `en_`, `bn_`, `cert_`, `rp_`, `jb_` prefixes). `TIMESTAMPTZ` everywhere, never `TIMESTAMP`. JSONB for open attribute bags only — anything queried in a `WHERE` that is not a containment check must be promoted to a column. Hashes are `BYTEA` of 32 bytes with a `CHECK (octet_length(h)=32)`, rendered as `blake3:hex` at the API boundary.

38.2 Core DDL.

```sql
CREATE SCHEMA spectra;
SET search_path = spectra, public;

CREATE TYPE dimension_t AS ENUM ('identity','session','credential','privilege',
                                 'process','network','api','service','resource','trust');
CREATE TYPE liveness_t  AS ENUM ('LIVE','BLIND','SUPPRESSED');
CREATE TYPE verdict_t   AS ENUM ('ROBUST','OPTIMISTIC_ONLY','UNSAFE');
CREATE TYPE job_state_t AS ENUM ('queued','running','retrying','succeeded','failed','cancelled');

CREATE TABLE source (
  source_id      TEXT PRIMARY KEY CHECK (source_id ~ '^[a-z][a-z0-9_]{1,31}$'),
  display_name   TEXT NOT NULL,
  dimensions     dimension_t[] NOT NULL CHECK (cardinality(dimensions) > 0),
  chain_algo     TEXT NOT NULL DEFAULT 'blake3',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dataset (
  dataset_id     TEXT PRIMARY KEY,
  scenario_id    TEXT NOT NULL REFERENCES scenario(scenario_id),
  seed           BIGINT NOT NULL,
  completeness   NUMERIC(4,3) NOT NULL CHECK (completeness > 0 AND completeness <= 1),
  generator_ver  TEXT NOT NULL,
  manifest_hash  BYTEA NOT NULL CHECK (octet_length(manifest_hash)=32),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (scenario_id, seed, completeness, generator_ver)
);

CREATE TABLE bundle (
  bundle_id      TEXT PRIMARY KEY,
  dataset_id     TEXT NOT NULL REFERENCES dataset(dataset_id) ON DELETE RESTRICT,
  bundle_hash    BYTEA NOT NULL UNIQUE CHECK (octet_length(bundle_hash)=32),
  event_count    INTEGER NOT NULL CHECK (event_count >= 0),
  span           TSTZRANGE NOT NULL,
  ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hot table. RANGE partitioned monthly on occurred_at.
CREATE TABLE event (
  id             BIGINT GENERATED ALWAYS AS IDENTITY,
  event_uid      TEXT NOT NULL,                    -- stable EventId, content addressed
  bundle_id      TEXT NOT NULL REFERENCES bundle(bundle_id) ON DELETE CASCADE,
  source_id      TEXT NOT NULL REFERENCES source(source_id),
  seq_no         BIGINT NOT NULL,                  -- per-source monotone sequence
  prev_hash      BYTEA NOT NULL CHECK (octet_length(prev_hash)=32),
  self_hash      BYTEA NOT NULL CHECK (octet_length(self_hash)=32),
  occurred_at    TIMESTAMPTZ NOT NULL,
  received_at    TIMESTAMPTZ NOT NULL,
  event_type     TEXT NOT NULL,
  actor_entity   BIGINT REFERENCES entity(id),
  target_entity  BIGINT REFERENCES entity(id),
  dimension      dimension_t NOT NULL,
  outcome        TEXT NOT NULL CHECK (outcome IN ('success','failure','unknown')),
  attrs          JSONB NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (id, occurred_at),
  CONSTRAINT event_uid_unique UNIQUE (event_uid, occurred_at),
  CONSTRAINT event_clock_sane CHECK (received_at >= occurred_at - INTERVAL '1 hour')
) PARTITION BY RANGE (occurred_at);

CREATE TABLE event_2026_03 PARTITION OF event
  FOR VALUES FROM ('2026-03-01Z') TO ('2026-04-01Z');
CREATE TABLE event_default PARTITION OF event DEFAULT;

CREATE INDEX event_src_seq_idx      ON event (source_id, seq_no);
CREATE INDEX event_actor_time_idx   ON event (actor_entity, occurred_at DESC)
                                     WHERE actor_entity IS NOT NULL;
CREATE INDEX event_dim_time_idx     ON event (dimension, occurred_at DESC);
CREATE INDEX event_attrs_gin        ON event USING GIN (attrs jsonb_path_ops);
CREATE INDEX event_failed_auth_idx  ON event (occurred_at DESC)
                                     WHERE outcome = 'failure' AND dimension = 'identity';
CREATE INDEX event_occurred_brin    ON event USING BRIN (occurred_at) WITH (pages_per_range = 32);
```

Rationale for each non-obvious index, to be repeated as a comment in the migration: `jsonb_path_ops` GIN because attribute filtering is containment-only (`attrs @> '{"proc":"powershell"}'`); the partial failed-auth index because credential-stuffing windows scan a 0.4% slice; BRIN because monthly partitions are physically time-ordered and BRIN costs ~1/500th of a btree for range scans.

38.3 Entities, state, transitions.

```sql
CREATE TABLE entity (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_uid    TEXT NOT NULL UNIQUE,
  kind          TEXT NOT NULL CHECK (kind IN ('user','service_account','host','process',
                                              'session','credential','resource','network_zone')),
  canonical_name TEXT NOT NULL,
  first_seen    TIMESTAMPTZ NOT NULL,
  last_seen     TIMESTAMPTZ NOT NULL,
  attrs         JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK (last_seen >= first_seen)
);
CREATE INDEX entity_kind_name_idx ON entity (kind, canonical_name);
CREATE INDEX entity_name_trgm     ON entity USING GIN (canonical_name gin_trgm_ops);

CREATE TABLE entity_alias (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_id    BIGINT NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
  alias        TEXT NOT NULL,
  alias_kind   TEXT NOT NULL,
  merge_rule   TEXT NOT NULL,
  evidence_uids TEXT[] NOT NULL CHECK (cardinality(evidence_uids) > 0),
  UNIQUE (alias_kind, alias)
);
CREATE INDEX entity_alias_evidence_gin ON entity_alias USING GIN (evidence_uids);

CREATE TABLE state_transition (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entity_id     BIGINT NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
  dimension     dimension_t NOT NULL,
  from_state    TEXT NOT NULL,
  to_state      TEXT NOT NULL,
  valid_from    TIMESTAMPTZ NOT NULL,
  valid_to      TIMESTAMPTZ,                       -- NULL = open interval
  rule_id       TEXT NOT NULL REFERENCES rule(rule_id),
  trigger_uids  TEXT[] NOT NULL,
  is_silent     BOOLEAN NOT NULL DEFAULT false,
  license_id    BIGINT REFERENCES license(id),
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK (from_state <> to_state),
  CHECK ((is_silent AND license_id IS NOT NULL) OR (NOT is_silent AND license_id IS NULL))
);
CREATE INDEX st_entity_dim_time_idx ON state_transition (entity_id, dimension, valid_from DESC);
CREATE INDEX st_open_idx  ON state_transition (entity_id, dimension) WHERE valid_to IS NULL;
CREATE INDEX st_silent_idx ON state_transition (license_id) WHERE is_silent;
CREATE INDEX st_trigger_gin ON state_transition USING GIN (trigger_uids);
-- forbid overlapping intervals per (entity, dimension)
ALTER TABLE state_transition ADD CONSTRAINT st_no_overlap
  EXCLUDE USING gist (entity_id WITH =, (dimension::text) WITH =,
                      tstzrange(valid_from, valid_to) WITH &&);
```

The exclusion constraint is the database-level restatement of the time-indexing rule from the ECLIPSE spec: state is never retracted, only superseded, so two intervals for one dimension may never overlap. A migration test must attempt an overlapping insert and assert failure.

38.4 Integrity, liveness, proofs.

```sql
CREATE TABLE chain_gap (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id    TEXT NOT NULL REFERENCES source(source_id),
  bundle_id    TEXT NOT NULL REFERENCES bundle(bundle_id) ON DELETE CASCADE,
  gap_kind     TEXT NOT NULL CHECK (gap_kind IN ('seq_skip','hash_break','backdated','duplicate')),
  from_seq     BIGINT NOT NULL,
  to_seq       BIGINT NOT NULL,
  window       TSTZRANGE NOT NULL,
  detail       JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK (to_seq >= from_seq)
);

CREATE TABLE license (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  bundle_id    TEXT NOT NULL REFERENCES bundle(bundle_id) ON DELETE CASCADE,
  source_id    TEXT NOT NULL REFERENCES source(source_id),
  basis        liveness_t NOT NULL CHECK (basis <> 'LIVE'),
  window       TSTZRANGE NOT NULL,
  witness_uids TEXT[] NOT NULL,
  voided       BOOLEAN NOT NULL DEFAULT false,     -- set by the difference-constraint pass
  UNIQUE (bundle_id, source_id, window, basis)
);
CREATE INDEX license_window_gist ON license USING GIST (window);

CREATE TABLE proof_cert (
  cert_id        TEXT PRIMARY KEY,
  bundle_id      TEXT NOT NULL REFERENCES bundle(bundle_id) ON DELETE CASCADE,
  scenario_id    TEXT NOT NULL REFERENCES scenario(scenario_id),
  mode           TEXT NOT NULL CHECK (mode IN ('ROBUST','OPTIMISTIC')),
  verdict        verdict_t NOT NULL,
  cut_atoms      TEXT[] NOT NULL,
  lower_bound    INTEGER NOT NULL CHECK (lower_bound >= 0),
  corridor_count INTEGER NOT NULL CHECK (corridor_count >= 0),
  instance_count INTEGER NOT NULL,
  silent_count   INTEGER NOT NULL,
  horizon_k      SMALLINT NOT NULL CHECK (horizon_k BETWEEN 1 AND 64),
  seed           BIGINT NOT NULL,
  rules_hash     BYTEA NOT NULL, bundle_hash BYTEA NOT NULL,
  controls_hash  BYTEA NOT NULL, liveness_hash BYTEA NOT NULL, goal_hash BYTEA NOT NULL,
  cert_hash      BYTEA NOT NULL UNIQUE,
  flag_capped    BOOLEAN NOT NULL DEFAULT false,
  flag_subset_only BOOLEAN NOT NULL DEFAULT false,
  flag_greedy    BOOLEAN NOT NULL DEFAULT false,
  document       JSONB NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT robust_never_flagged CHECK (
    verdict <> 'ROBUST' OR NOT (flag_capped OR flag_subset_only OR flag_greedy))
);
CREATE UNIQUE INDEX proof_content_key_idx
  ON proof_cert (rules_hash, bundle_hash, controls_hash, goal_hash, mode, horizon_k, seed);

CREATE TABLE corridor (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cert_id    TEXT NOT NULL REFERENCES proof_cert(cert_id) ON DELETE CASCADE,
  program    TEXT NOT NULL CHECK (program IN ('P_min','P_max')),
  atom_mask  BIGINT NOT NULL,                      -- u64 over threshold literals
  fact_uids  TEXT[] NOT NULL,
  license_ids BIGINT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX corridor_cert_idx ON corridor (cert_id, program);
```

`robust_never_flagged` is the schema-level enforcement of the ECLIPSE prohibition: a flagged run can physically not be stored as ROBUST.

38.5 Jobs and idempotency.

```sql
CREATE TABLE job (
  job_id       TEXT PRIMARY KEY,
  kind         TEXT NOT NULL,
  state        job_state_t NOT NULL DEFAULT 'queued',
  subject      TEXT NOT NULL,
  content_key  BYTEA,
  payload      JSONB NOT NULL,
  result_ref   TEXT,
  attempts     SMALLINT NOT NULL DEFAULT 0 CHECK (attempts <= 3),
  error_code   TEXT, error_detail JSONB,
  enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at   TIMESTAMPTZ, finished_at TIMESTAMPTZ,
  CHECK (finished_at IS NULL OR started_at IS NOT NULL)
);
CREATE INDEX job_active_idx ON job (kind, enqueued_at) WHERE state IN ('queued','running','retrying');
CREATE UNIQUE INDEX job_content_key_idx ON job (content_key) WHERE state = 'succeeded';

CREATE TABLE idempotency_key (
  key          TEXT PRIMARY KEY,
  fingerprint  BYTEA NOT NULL,
  subject      TEXT NOT NULL,
  state        TEXT NOT NULL CHECK (state IN ('in_flight','completed')),
  response_status SMALLINT, response_body JSONB, job_id TEXT REFERENCES job(job_id),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX idem_expiry_idx ON idempotency_key (expires_at);
```

38.6 Materialized views. Each has a UNIQUE index so `REFRESH MATERIALIZED VIEW CONCURRENTLY` works; each is refreshed by a named task, never by a trigger.

```sql
CREATE MATERIALIZED VIEW mv_source_liveness AS
SELECT e.source_id, date_trunc('minute', e.occurred_at) AS minute,
       count(*) AS events,
       max(e.occurred_at) - min(e.occurred_at) AS spread,
       bool_or(g.id IS NOT NULL) AS has_gap
FROM event e
LEFT JOIN chain_gap g ON g.source_id = e.source_id AND e.occurred_at <@ g.window
GROUP BY 1,2;
CREATE UNIQUE INDEX mv_source_liveness_pk ON mv_source_liveness (source_id, minute);

CREATE MATERIALIZED VIEW mv_entity_dimension_span AS
SELECT entity_id, dimension, min(valid_from) AS first_change, max(valid_from) AS last_change,
       count(*) FILTER (WHERE is_silent) AS silent_changes, count(*) AS changes
FROM state_transition GROUP BY 1,2;
CREATE UNIQUE INDEX mv_eds_pk ON mv_entity_dimension_span (entity_id, dimension);
```

38.7 Alembic conventions.

1. `target_metadata` uses this naming convention, and every constraint in hand-written DDL matches it: `ix_%(column_0_label)s`, `uq_%(table_name)s_%(column_0_name)s`, `ck_%(table_name)s_%(constraint_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s`, `pk_%(table_name)s`.
2. Revision files are `NNNN_short_slug.py` with a linear history; branching is forbidden and CI runs `alembic heads` asserting exactly one head.
3. Every migration implements a real `downgrade()`. CI runs `upgrade head -> downgrade base -> upgrade head` on an empty database and on a seeded one.
4. DDL and data migrations never live in the same revision. Data backfills are idempotent and chunked (`LIMIT 10000` loops).
5. New partitions are created by a helper `op.execute(create_month_partition('event', '2026-04'))`; a scheduled task pre-creates the next two months and alerts if `event_default` is non-empty.
6. Index creation on `event` uses `CREATE INDEX CONCURRENTLY` inside a revision marked `transactional=False`.
7. A test asserts that the ORM metadata and the migrated database are identical (`alembic check` produces no diff).

38.8 Analytical queries. These are required deliverables in `db/queries/` and each ships with a test asserting the result against a fixture bundle.

```sql
-- Q1 chain walking: transitive causal closure from a seed fact, with cycle guard and depth cap.
WITH RECURSIVE walk AS (
  SELECT ce.src_fact, ce.dst_fact, 1 AS depth,
         ARRAY[ce.src_fact, ce.dst_fact] AS path
  FROM causal_edge ce
  WHERE ce.src_fact = $1 AND ce.cert_id = $2
  UNION ALL
  SELECT ce.src_fact, ce.dst_fact, w.depth + 1, w.path || ce.dst_fact
  FROM causal_edge ce
  JOIN walk w ON ce.src_fact = w.dst_fact AND ce.cert_id = $2
  WHERE w.depth < $3 AND NOT ce.dst_fact = ANY(w.path)      -- cycle guard
)
SELECT depth, dst_fact, path,
       (SELECT array_agg(uid) FROM fact_evidence fe WHERE fe.fact_uid = walk.dst_fact) AS event_uids
FROM walk ORDER BY depth, dst_fact;

-- Q2 session continuity: per session, find idle gaps and label continuity runs.
SELECT session_id, occurred_at, event_type,
       occurred_at - lag(occurred_at) OVER w AS idle_gap,
       sum(CASE WHEN occurred_at - lag(occurred_at) OVER w > INTERVAL '15 minutes'
                THEN 1 ELSE 0 END) OVER w AS continuity_run,
       count(*) OVER (PARTITION BY session_id) AS session_events
FROM (
  SELECT attrs->>'session_id' AS session_id, occurred_at, event_type
  FROM event
  WHERE dimension IN ('session','identity')
    AND attrs ? 'session_id'
    AND occurred_at >= $1 AND occurred_at < $2
) s
WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at)
ORDER BY session_id, occurred_at;

-- Q3 nearest preceding event: for each privilege escalation, the last authentication
--     by the same actor, using LATERAL so the index drives one backwards seek per row.
SELECT esc.event_uid AS escalation_uid, esc.occurred_at AS escalated_at,
       e.canonical_name AS actor,
       prev.event_uid AS preceding_auth_uid, prev.occurred_at AS auth_at,
       esc.occurred_at - prev.occurred_at AS lag_to_auth
FROM event esc
JOIN entity e ON e.id = esc.actor_entity
LEFT JOIN LATERAL (
  SELECT p.event_uid, p.occurred_at
  FROM event p
  WHERE p.actor_entity = esc.actor_entity
    AND p.dimension = 'identity'
    AND p.outcome = 'success'
    AND p.occurred_at < esc.occurred_at
  ORDER BY p.occurred_at DESC
  LIMIT 1
) prev ON true
WHERE esc.dimension = 'privilege' AND esc.event_type = 'privilege.granted'
  AND esc.occurred_at >= $1 AND esc.occurred_at < $2
ORDER BY esc.occurred_at;

-- Q4 integrity gap detection: per source, sequence skips and inter-arrival outliers
--     measured against this run's own q99, never a hard-coded threshold.
WITH seq AS (
  SELECT source_id, seq_no, occurred_at, self_hash, prev_hash,
         lag(seq_no)     OVER w AS prev_seq,
         lag(self_hash)  OVER w AS prev_self_hash,
         occurred_at - lag(occurred_at) OVER w AS interarrival
  FROM event
  WHERE bundle_id = $1
  WINDOW w AS (PARTITION BY source_id ORDER BY seq_no)
),
thresh AS (
  SELECT source_id,
         percentile_cont(0.99) WITHIN GROUP (ORDER BY interarrival) AS q99
  FROM seq WHERE interarrival IS NOT NULL GROUP BY source_id
)
SELECT s.source_id, s.prev_seq, s.seq_no, s.occurred_at, s.interarrival, t.q99,
       CASE
         WHEN s.prev_seq IS NOT NULL AND s.seq_no <> s.prev_seq + 1 THEN 'seq_skip'
         WHEN s.prev_self_hash IS NOT NULL AND s.prev_hash <> s.prev_self_hash THEN 'hash_break'
         WHEN s.interarrival > t.q99 THEN 'blind_candidate'
       END AS finding
FROM seq s JOIN thresh t USING (source_id)
WHERE (s.prev_seq IS NOT NULL AND s.seq_no <> s.prev_seq + 1)
   OR (s.prev_self_hash IS NOT NULL AND s.prev_hash <> s.prev_self_hash)
   OR s.interarrival > t.q99
ORDER BY s.source_id, s.seq_no;
```

38.9 Negative requirements. Do not store ground truth from the generator in any table the reconstruction path can read; it lives in a separate schema `truth` with a database role that the API user cannot access, and a test asserts the API role is denied. Do not add `ON DELETE CASCADE` from `dataset` to `bundle` — regeneration must be explicit. Do not add triggers that mutate `event`. Do not store LLM output in the same table as computed structures. Do not use `SERIAL`, `TIMESTAMP` without time zone, `float` for anything counted, or `TEXT` for a hash. Do not create an index without recording its justification in the migration comment, and drop any index whose `idx_scan` is zero after a full benchmark run.
