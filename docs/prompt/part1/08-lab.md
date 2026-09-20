============================================================
26. THE LOCAL CYBER RANGE
============================================================

The range is the only place SPECTRA telemetry comes from. It is a closed, deterministic,
egress-blocked Docker lab that impersonates a mid-size enterprise identity and application
estate. Build it before anything that consumes telemetry.

26.1 NON-NEGOTIABLE ISOLATION GUARANTEES

1. No container in the range may reach any host outside the Docker network set. Enforce this
   structurally, not by policy text.
2. Every range network is declared with `internal: true` except `spectra_front`, which is a
   bridge with IP masquerade disabled:
   `com.docker.network.bridge.enable_ip_masquerade: "false"`.
   This permits inbound DNAT (published UI/API ports) while removing the NAT path outbound.
3. Every service sets `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`,
   `read_only: true` with explicit `tmpfs` mounts, `pids_limit`, and a non-root `user:`.
4. No service may mount the Docker socket. A CI grep gate fails the build on
   `/var/run/docker.sock` appearing in any compose file.
5. `attack-simulator` is behind `profiles: ["attack"]`. `docker compose up` must never start it.
   Its binary refuses to run unless every resolved target IP is inside `10.77.0.0/16`; the
   allowed CIDR is a compile-time constant and there is a unit test that a public IP aborts.
6. No image may be pulled at run time. All images are pinned by digest in `range/images.lock`
   and pre-pulled by `make range-images`.
7. No real credentials, no real domains, no external DNS. The compose file sets `dns: ["127.0.0.1"]`
   plus per-service `extra_hosts` for the in-range names only.

Verification target: `make range-verify-isolation` runs, inside every service container, a
connect attempt to three routable external IPs and one external DNS name and asserts all four
fail. It writes `artifacts/range/isolation_report.json` with one row per container. The CI
gate fails if any row is `reachable: true` or if any container was skipped.

26.2 TOPOLOGY

```
                         host :5173  :8000            (only published ports)
                              |         |
      ==================== spectra_front (bridge, masquerade OFF) ================
                              |         |
                        +----------+  +-------------+
                        | frontend |  | spectra-api |   React18/TS/Vite ; Python/FastAPI
                        +----------+  +------+------+
                                             |
      ================= spectra_plane (internal) ===============================
                     |               |                |
            +----------------+ +-----------+  +--------------+
            | spectra-worker | | postgres  |  |    redis     |
            |    (Python)    | | (16.x)    |  |   (7.x)      |
            +--------+-------+ +-----+-----+  +------+-------+
                     |               |               |
      ================= range_telemetry (internal) =============================
                     |                               |
          +----------+---------+          +----------+---------+
          |     normalizer     |<---------| telemetry-collector|
          |      (Rust)        |  frames  |        (Go)        |
          +--------------------+          +----------+---------+
                                                     ^ emit (unix socket + TCP 9700)
      ===================== range_core (internal) ====|=========================
        +------------------+   +-------------+   +---------------------+
        | identity-service |<--| api-gateway |-->|  enterprise-service |
        |     (Java 21)    |   |  (Kotlin)   |   |       (C# .NET8)    |
        +--------+---------+   +------+------+   +----------+----------+
                 |                    |                     |
                 |            +-------+--------+   +--------+---------+
                 |            | resource-service|  |   batch-jobs     |
                 |            |      (Go)       |  |     (Perl)       |
                 |            +-----------------+  +------------------+
      ===================== range_edge (internal) ==============================
        +-------------+   +------------------+   +--------------------+
        | legacy-web  |   | partner-service  |   | edge-transformer   |
        |   (PHP 8.3) |   |   (Ruby 3.3)     |   |   (Lua/OpenResty)  |
        +-------------+   +------------------+   +--------------------+
                 ^                                          ^
                 +-------- attack-simulator (profile: attack, Python+Go)
```

Edge services reach core only through `api-gateway`. `legacy-web`, `partner-service` and
`edge-transformer` are on `range_edge` and `range_core` is reachable from them **only** via the
gateway alias; there is no direct route from `range_edge` to `postgres`. That asymmetry is what
makes `egress_seg` a meaningful control in the replay engine (see section 9).

26.3 SERVICE TABLE

| service | lang | internal port | role in the estate | SourceIds emitted | silent_possible rules it feeds |
|---|---|---|---|---|---|
| identity-service | Java 21 / Spring Boot | 8081 | OIDC IdP: login, MFA, token issue/refresh, device registration, role grants | `iam_audit`, `auth_log`, `mfa_log` | `session.issued`, `cred.rotated`, `role.granted` |
| api-gateway | Kotlin / Ktor | 8080 | edge auth, token introspection, rate limiting, routing | `gw_access`, `token_introspect` | `session.used`, `api.call` |
| enterprise-service | C# / .NET 8 | 8082 | HR + finance records, approval workflows, privilege approvals | `app_audit_ent`, `approval_log` | `priv.approved`, `record.read` |
| resource-service | Go | 8083 | object store front, bulk download, presigned links | `res_access`, `egress_bytes` | `data.read`, `data.exfil` |
| legacy-web | PHP 8.3 | 8084 | unmaintained intranet, cookie sessions, no session binding | `legacy_access`, `php_session_log` | `session.fixated` |
| partner-service | Ruby 3.3 / Sinatra | 8085 | B2B OAuth consent, partner API keys | `oauth_consent`, `partner_api` | `consent.granted`, `token.delegated` |
| batch-jobs | Perl | n/a (cron) | nightly ETL under service accounts, report mailers | `batch_log`, `svc_exec` | `svc.burst` |
| edge-transformer | Lua / OpenResty | 8086 | header rewriting, request shaping, IP forwarding | `edge_rewrite` | `identity.spoofed` |
| telemetry-collector | Go | 9700 | receives emitter frames, BLAKE3 sequence-chains per source, writes `raw.jsonl` | (meta) `collector_health` | — |
| normalizer | Rust | 9701 | schema normalization, entity resolution, `EventId` assignment, `bundle.jsonl` | (meta) `normalizer_health` | — |
| spectra-api | Python 3.12 / FastAPI | 8000 | REST + WS, replay, ECLIPSE invocation | — | — |
| spectra-worker | Python 3.12 | n/a | grounding jobs, degradation matrix runs | — | — |
| frontend | TS / Vite | 5173 | UI, PROVE pane, checker terminal | — | — |
| postgres | 16.x | 5432 | state store, graph tables, certificates | — | — |
| redis | 7.x | 6379 | job queue, replay run cache | — | — |
| attack-simulator | Python + Go | n/a | scripted scenario execution (section 28) | `sim_control` (out-of-band) | — |

The `SourceIds emitted` column is authoritative: it is generated from `range/sources.toml` and
`rules.toml` must reference no SourceId absent from it. A CI gate diffs the two and fails on any
orphan. Liveness (ECLIPSE step A, see section 12) is computed per SourceId in this table, so an
unhealthy or stopped container produces a real BLIND window, not a simulated one.

26.4 COMPOSE SKELETON (shape to reproduce exactly)

```yaml
# range/docker-compose.range.yml
x-hardened: &hardened
  restart: "no"
  read_only: true
  init: true
  pids_limit: 256
  cap_drop: ["ALL"]
  security_opt: ["no-new-privileges:true"]
  tmpfs: ["/tmp:size=64m,mode=1777"]
  logging: { driver: "json-file", options: { max-size: "10m", max-file: "3" } }

networks:
  range_core:      { internal: true, ipam: { config: [{ subnet: 10.77.10.0/24 }] } }
  range_edge:      { internal: true, ipam: { config: [{ subnet: 10.77.20.0/24 }] } }
  range_telemetry: { internal: true, ipam: { config: [{ subnet: 10.77.30.0/24 }] } }
  spectra_plane:   { internal: true, ipam: { config: [{ subnet: 10.77.40.0/24 }] } }
  spectra_front:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_ip_masquerade: "false"
    ipam: { config: [{ subnet: 10.77.50.0/24 }] }

services:
  identity-service:
    <<: *hardened
    image: spectra/identity-service@sha256:<pinned>
    user: "10001:10001"
    networks: [range_core, range_telemetry]
    environment:
      SPECTRA_SEED: "${SPECTRA_SEED:?seed required}"
      SPECTRA_CLOCK_EPOCH: "${SPECTRA_CLOCK_EPOCH:?epoch required}"
      TELEMETRY_ENDPOINT: "telemetry-collector:9700"
    healthcheck:
      test: ["CMD", "/app/healthcheck", "--strict"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 25s
    deploy:
      resources:
        limits:   { cpus: "1.00", memory: 768M }
        reservations: { cpus: "0.25", memory: 256M }
    depends_on:
      postgres: { condition: service_healthy }
      telemetry-collector: { condition: service_healthy }
```

Apply the same shape to every service. Resource limit budget for the whole range must fit
4 vCPU / 12 GiB; publish the actual sum in `range/RESOURCES.md` computed by a script, not typed.

26.5 STARTUP ORDERING

Use `depends_on` with `condition: service_healthy` only — never `sleep` in an entrypoint.

```
phase 0  postgres, redis, telemetry-collector
phase 1  normalizer                 (needs collector healthy)
phase 2  identity-service
phase 3  enterprise-service, resource-service, partner-service, legacy-web, edge-transformer
phase 4  api-gateway                (needs identity-service healthy: it fetches JWKS at boot)
phase 5  batch-jobs                 (cron daemon; first job fires at epoch+00:15 sim time)
phase 6  spectra-api, spectra-worker, frontend
phase 7  attack-simulator           (profile "attack", manual only)
```

Every healthcheck must be semantic, not `curl /`. `identity-service` health = "JWKS served AND
one synthetic login round-trips AND one telemetry frame acknowledged by the collector".
`normalizer` health = "collector stream attached AND last 60s produced a monotone EventId range".
A healthcheck that can pass while the service emits no telemetry is a bug; add a test that stubs
the collector down and asserts the service reports unhealthy within 15s.

26.6 MAKE TARGETS

```
make range-images      # build all range images, write range/images.lock (digests)
make range-up          # cold bring-up, all phases healthy
make range-down        # down -v, prune range volumes
make range-verify-isolation
make range-smoke       # 60s of benign traffic, assert >=1 event per SourceId
make range-attack SCENARIO=SC-07 SEED=20260214
```

`make range-up` must bring the range from `docker compose down -v` to all-healthy in **under
6 minutes** on the reference machine (4 vCPU, 16 GiB, warm image cache; cold image build budget
is separate and measured by `make range-images`). The target itself measures and records:

```
$ make range-up
[range] seed=20260214 epoch=2026-02-14T00:00:00Z
[range] phase 0 .................. healthy in  38.2s  (postgres, redis, telemetry-collector)
[range] phase 1 .................. healthy in   6.4s  (normalizer)
[range] phase 2 .................. healthy in  41.9s  (identity-service)
[range] phase 3 .................. healthy in  52.7s  (5 services)
[range] phase 4 .................. healthy in  19.1s  (api-gateway)
[range] phase 5 .................. healthy in   4.8s  (batch-jobs)
[range] phase 6 .................. healthy in  27.3s  (spectra-api, spectra-worker, frontend)
[range] TOTAL 190.4s  budget 360s  OK
[range] wrote artifacts/range/boot_timing.json
```

The timing JSON is real measurement written by the target. Do not hardcode a number anywhere in
docs; `README` and `range/RESOURCES.md` must interpolate from `artifacts/range/boot_timing.json`
or say "not yet measured". If total exceeds the budget, the target exits non-zero.

26.7 NEGATIVE REQUIREMENTS

- Do NOT install or run real malware, real exploit code, or any tool that touches a host outside
  `10.77.0.0/16`.
- Do NOT add a network without `internal: true` other than `spectra_front`, and do not enable
  masquerade on `spectra_front`.
- Do NOT use `latest` tags, `depends_on` without a condition, or retry-until-up entrypoint loops.
- Do NOT let `attack-simulator` start under the default profile, and do not give it a healthcheck
  that makes other services wait on it.
- Do NOT generate telemetry inside SPECTRA's own code path. Every event must originate in a range
  service and traverse collector -> normalizer. Synthesizing an event directly into `bundle.jsonl`
  is forbidden outside `tools/fixture-mint`, which stamps `synthetic_bypass: true` and which the
  ECLIPSE kernel refuses to accept as evidence.

============================================================
27. SYNTHETIC POPULATION AND BENIGN NOISE
============================================================

The discriminative difficulty of SPECTRA lives here. A detector that fires on "login at 03:00"
is worthless; the population must contain many honest 03:00 logins. Build the generator so that
every attacker step type has a dense population of benign lookalikes.

27.1 GENERATOR PLACEMENT

- Core sampler: Rust crate `crates/spectra-popgen` (deterministic, ChaCha20 PRNG, explicit
  substream per entity class so adding a class does not shift other draws).
- Config: `datasets/config/population.toml` (schema below), validated by a JSON Schema derived
  from the Rust types and checked in at `schemas/population.schema.json`.
- Driver: Python `spectra-gen population --config ... --seed ...` shells to the Rust binary and
  drives the range through its real APIs. The population is materialized by **calling the range
  services** (identity-service admin API, enterprise-service HR API), never by SQL inserts.
- Distribution validation: `analysis/population_fit.R` re-reads the emitted events and asserts
  the realized hour-of-day, session-length and burst-size distributions match the configured
  parameters within declared tolerance. It is a test, not a report generator.

27.2 CONFIG SCHEMA (population.toml)

```toml
schema_version = 3
seed           = 20260214           # master seed; all substreams derive from it
epoch          = "2026-02-14T00:00:00Z"
days           = 14
tick_seconds   = 1                  # simulation clock granularity

[org]
name            = "Northwind Analytics"
timezones       = ["UTC-8", "UTC-5", "UTC+0", "UTC+1", "UTC+5:30"]
tz_weights      = [0.22, 0.31, 0.12, 0.20, 0.15]
departments     = ["eng","sre","finance","hr","sales","support","legal","contractors"]
dept_weights    = [0.28,0.09,0.08,0.06,0.18,0.17,0.04,0.10]

[users]
count               = 1200
contractor_fraction = 0.10
dormant_fraction    = 0.06          # no login in the window unless reactivated
executive_fraction  = 0.015
devices_per_user    = { dist = "zipf", s = 1.6, min = 1, max = 5 }
mfa_enrolled_frac   = 0.88          # the 12% gap is real and exploitable in SC-11

[roles]
count               = 74
max_depth           = 4             # role inheritance DAG depth
overprivileged_frac = 0.07          # roles granting more than their department needs
[roles.drift]
enabled             = true
grants_per_day      = { dist = "poisson", lambda = 9.0 }
revokes_per_day     = { dist = "poisson", lambda = 4.5 }   # deliberately < grants: privilege creep

[service_accounts]
count               = 65
owned_by_dept       = true
key_rotation_days   = { dist = "choice", values = [30, 90, 180, 365], weights = [0.1,0.4,0.3,0.2] }
burst_jobs          = 18            # nightly batch identities
burst_window_utc    = ["01:40", "03:20"]
burst_rps           = { dist = "lognormal", mu = 2.9, sigma = 0.55 }

[schedule]
work_start_local    = { dist = "normal", mu = 9.1,  sigma = 0.85 }   # hours
work_end_local      = { dist = "normal", mu = 17.9, sigma = 1.10 }
lunch_gap_minutes   = { dist = "normal", mu = 41,   sigma = 13 }
weekend_work_frac   = 0.08
late_night_frac     = 0.055         # honest 23:00-04:00 activity
oncall_rota_size    = 14
oncall_shift_hours  = 12

[travel]
travelers_per_week  = 26
trip_days           = { dist = "choice", values = [2,3,4,5], weights = [0.3,0.35,0.2,0.15] }
vpn_exit_hop_frac   = 0.34          # VPN exits produce geo jumps that look like impossible travel

[noise]
typo_login_failures_per_user_day = { dist = "poisson", lambda = 0.21 }
password_reset_per_day           = { dist = "poisson", lambda = 6.0 }
new_device_enroll_per_day        = { dist = "poisson", lambda = 4.0 }
mfa_flaky_device_frac            = 0.03   # devices producing 4-11 prompts in 3 minutes
token_refresh_storm_per_day      = 3      # mobile client bug, 40-90 refreshes in 5 min
deployments_per_day              = { dist = "poisson", lambda = 5.5 }
oncall_escalations_per_day       = { dist = "poisson", lambda = 1.4 }
bulk_export_legit_per_day        = 2.2    # finance and sales legitimately pull large datasets
offboarding_per_week             = 7
reactivation_per_week            = 2      # returning from leave: dormant account wakes legitimately
consent_grants_per_week          = 11     # legitimate OAuth consent to partner apps
config_change_per_day            = { dist = "poisson", lambda = 3.2 }

[telemetry]
sources_enabled = ["iam_audit","auth_log","mfa_log","gw_access","token_introspect",
                   "app_audit_ent","approval_log","res_access","egress_bytes",
                   "legacy_access","php_session_log","oauth_consent","partner_api",
                   "batch_log","svc_exec","edge_rewrite"]
# natural, non-adversarial gaps. These create honest BLIND windows for ECLIPSE liveness.
[[telemetry.maintenance_window]]
source = "iam_audit"; start = "2026-02-19T02:10:00Z"; duration_minutes = 40; reason = "idp_upgrade"
[[telemetry.maintenance_window]]
source = "edge_rewrite"; start = "2026-02-22T23:05:00Z"; duration_minutes = 15; reason = "nginx_reload"
```

27.3 BENIGN LOOKALIKE CATALOG

Each attacker primitive must have benign twins. Implement every row; each row has a unit test
asserting the realized count over a 14-day base dataset falls in the stated band.

| attacker primitive | benign lookalike generated | target count / 14d | discriminator that remains |
|---|---|---|---|
| impossible travel | VPN exit-hop change; airport transit login | 180-260 | device fingerprint continuity + prior travel booking event |
| credential stuffing | typo burst, expired-password loop | 900-1400 failures | distinct-username fanout per source IP |
| dormant reactivation | return-from-leave, seasonal contractor | 4-8 | HR `leave.ended` record precedes the login |
| privilege escalation | approved role grant via ticket | 110-150 grants | `approval_log` entry with approver != subject |
| service-account burst | nightly ETL, quarter-close reports | 18 jobs/night | destination set is the job's declared allowlist |
| MFA fatigue | flaky authenticator retry storm | 25-45 storms | storm ends in success from the *same* device |
| token replay | mobile refresh storm | 3/day | refresh chain is monotone, same device binding |
| mass data read | finance/sales legitimate export | ~30 exports | export initiated inside the reporting app, not resource-service direct |
| lateral movement | SRE on-call cross-service access | 18-24 per rota cycle | on-call schedule record covers the window |
| CI/CD identity abuse | real deployments | 70-90 deploys | pipeline run id resolves to a real commit + approver |
| consent abuse | legitimate partner consent | 20-24 | app id is on the partner allowlist with a prior review event |
| config drift exposure | planned config change | 40-50 | change has a change-record id and a rollback plan field |
| session fixation | legacy-web cookie reuse after idle | 300+ resumptions | cookie was issued to the same UA/IP pair |

Hard rule, enforced by `tests/population/test_lookalike_density.py`: for every attack scenario in
section 28 and every step in it, the count of benign events of the same *event type* within the
scenario's time window must be **at least 20**. A scenario whose steps are unique in their window
is rejected at dataset build time with a non-zero exit and the message
`LOOKALIKE_DENSITY_FAIL scenario=SC-xx step=k type=... found=n need=20`.

27.4 VOLUME TARGETS (base dataset `base-14d-v1`)

| quantity | target | tolerance |
|---|---|---|
| users | 1200 | exact |
| devices | 2600-3100 | band |
| service accounts | 65 | exact |
| roles / role edges | 74 / 210-260 | band |
| total events, 14 days | 5.6M - 6.4M | band |
| events/day, weekday | 460k - 520k | band |
| events/day, weekend | 90k - 140k | band |
| sessions | 210k - 250k | band |
| distinct SourceIds | 16 | exact |
| natural BLIND minutes (all sources summed) | 55-75 | band |
| bundle.jsonl size | 3.1 - 3.9 GiB | band |
| generation wall time (reference machine) | <= 18 min | budget |

The band table lives in `datasets/config/volume_targets.toml` and the generator asserts against
it. Bands are not aspirations: a run outside a band fails the build.

27.5 NEGATIVE REQUIREMENTS

- Do NOT make benign activity trivially separable (no "benign = business hours only").
- Do NOT let attacker steps use an event type, user-agent, IP block, or field value that never
  occurs benignly. Add a linter that diffs the attacker event field-value sets against the benign
  field-value sets and fails on any attacker-exclusive value that is not itself a modeled
  observable (for example a genuinely new device id is fine; a literal `attack=true` field is not).
- Do NOT write a label into any event record. Labels live only in the ground-truth stream
  (section 29) and the normalizer must reject a `bundle.jsonl` line carrying a label key.
- Do NOT reuse one PRNG stream across entity classes; adding one contractor must not change any
  other user's schedule. There is a test: generate with `users.count = 1200` and `1201` and assert
  the first 1200 users' event streams are byte-identical.
- Do NOT model the attacker here. This section produces an organization, not an incident.

============================================================
28. ATTACK SCENARIO CATALOG
============================================================

All scenarios are **simulations executed by `attack-simulator` against the local range**. No real
exploit, no real malware, no real target. MITRE ATT&CK IDs are given where the simulated behavior
honestly corresponds to the technique's observable, and are labeled `approximate` otherwise; they
are documentation, never detection logic.

28.1 SCENARIO FILE FORMAT

One file per scenario at `datasets/scenarios/SC-XX-<slug>.yaml`. The file is executable input to
`attack-simulator` and to the ground-truth emitter simultaneously (section 29): the simulator
cannot perform a step that the file does not declare, and cannot declare a step it does not
perform. A step executes through the range's real APIs.

```yaml
# datasets/scenarios/SC-03-token-theft.yaml
id: SC-03
slug: token-theft-and-misuse
schema_version: 2
simulation: true            # required literal; loader rejects the file without it
narrative: >
  A refresh token is lifted from a compromised developer laptop's token cache during a
  legitimate session, exchanged for an access token from a second device, and used through the
  gateway to read finance records the developer's role can reach transitively.
actor:
  kind: external
  persona: opportunistic-operator
  adaptivity: none          # ECLIPSE assumes a non-adaptive attacker; do not claim otherwise
  entry: stolen-artifact
preconditions:
  - user.mfa_enrolled: true
  - user.device_count: ">=2"
  - control.session_binding: 0        # level 0 = off
  - role.transitive_reach: ["finance.records.read"]
  - token.refresh_ttl_days: ">=7"
timing:
  start: "epoch+6d09h41m"
  duration_minutes: 74
  jitter_seconds: 180        # drawn from the scenario substream, seed-stable
steps:
  - k: 1
    action: token.cache_read
    where: victim_device_a
    emits: []                                  # deliberately unobserved: no endpoint sensor
    ground_truth_only: true
  - k: 2
    action: token.refresh_exchange
    where: identity-service
    emits: [iam_audit, auth_log]
    expect_transition: { dim: credential, from: token_bound_device_a, to: token_active_device_b }
  - k: 3
    action: api.call
    where: api-gateway
    target: enterprise-service
    emits: [gw_access, token_introspect]
    expect_transition: { dim: session, from: none, to: session_active_unbound }
  - k: 4
    action: record.read
    where: enterprise-service
    scope: finance.records
    count: 412
    emits: [app_audit_ent]
    expect_transition: { dim: resource, from: untouched, to: bulk_read }
  - k: 5
    action: data.stage
    where: resource-service
    bytes: 88_400_000
    emits: [res_access, egress_bytes]
    expect_transition: { dim: resource, from: bulk_read, to: staged_for_egress }
goal_atom: "data.exfiltrated(finance.records, actor_b)"
expected_block_points:
  - control: session_binding
    level: 1                 # bind token to device fingerprint
    blocks_at_step: 3
    mechanism: "introspection rejects token whose device claim != presenting device"
  - control: token_expiry
    level: 2                 # refresh TTL <= 24h
    blocks_at_step: 2
    mechanism: "stolen refresh token is past TTL at exchange time"
  - control: rbac_tightening
    level: 2
    blocks_at_step: 4
    mechanism: "transitive finance reach removed from developer role closure"
  - control: egress_seg
    level: 1
    blocks_at_step: 5
    mechanism: "resource-service staging path unreachable from gateway-originated session"
  - control: mfa
    level: any
    blocks_at_step: null     # declared explicitly: MFA does NOT block this chain
    mechanism: "no interactive authentication occurs after step 1"
noise_bed:
  - token_refresh_storm      # 3/day, overlapping window
  - bulk_export_legit        # finance export same afternoon
  - new_device_enroll        # 4/day
blindness:
  # sources deliberately blind during part of the chain; feeds ECLIPSE licenses
  - source: token_introspect
    window: ["epoch+6d09h52m", "epoch+6d10h07m"]
    basis: blind             # collector restart, NOT suppression
attack_ids:
  - { id: "T1528", name: "Steal Application Access Token", fidelity: exact }
  - { id: "T1550.001", name: "Use Alternate Authentication Material: App Access Token", fidelity: exact }
  - { id: "T1530", name: "Data from Cloud Storage", fidelity: approximate }
ground_truth:
  chain_id: "SC-03"
  malicious_event_selector: "emitted_by_step"     # see section 29
  unobserved_steps: [1]
  expected_verdict_full_telemetry: ROBUST
  expected_min_cut_size: 1
```

`expected_block_points` is not a claim: `tests/scenarios/test_block_points.py` runs the concrete
simulator at that control level and asserts the chain actually terminates at `blocks_at_step`,
and that with the control one level lower it does not. A scenario whose declared block point does
not reproduce fails the build. `blocks_at_step: null` rows are tested too: the chain must still
complete.

28.2 THE CATALOG

Sixteen scenarios. Every row below has a full YAML file with the structure above.

| id | name | actor | key preconditions | steps | primary expected block (control >= level) | buried in | ATT&CK |
|---|---|---|---|---|---|---|---|
| SC-01 | Session hijack via stolen cookie | external | legacy-web session, no binding | 5 | session_binding>=1 @ s2; device_trust>=2 @ s2 | 300+ benign legacy resumptions | T1539, T1185(approx) |
| SC-02 | Credential stuffing to single-account takeover | external botnet | reused password, mfa off for 12% | 6 | mfa>=1 @ s4; rate_limiting>=2 @ s2 | 900-1400 benign typo failures | T1110.004, T1078.004 |
| SC-03 | Token theft and misuse | external | refresh TTL 7d, binding off | 5 | session_binding>=1 @ s3; token_expiry>=2 @ s2 | refresh storms, finance exports | T1528, T1550.001 |
| SC-04 | OAuth consent abuse (malicious partner app) | external app | partner self-service consent | 6 | consent_review>=1 @ s2; token_expiry>=1 @ s5 | 20-24 legit consents | T1528, T1550.001 |
| SC-05 | Privilege escalation via role misconfiguration | insider (low priv) | overprivileged role 7%, no approval gate | 7 | priv_approval>=1 @ s3; rbac_tightening>=2 @ s3 | 110-150 approved grants | T1078, T1098 |
| SC-06 | Service-account key abuse | external | key age 365d, shared secret in repo mirror | 6 | cred_rotation>=2 @ s1; svc_isolation>=1 @ s4 | 18 nightly ETL bursts | T1078.004, T1552.001(approx) |
| SC-07 | Lateral movement, gateway to internal services | external | session from SC-01, flat east-west | 9 | egress_seg>=1 @ s5; svc_isolation>=2 @ s7 | on-call cross-service access | T1021, T1570(approx) |
| SC-08 | Insider slow exfiltration (14-day drip) | insider | legitimate read rights | 22 | rate_limiting>=3 @ s9; egress_seg>=2 @ s14 | daily legitimate exports | T1567(approx), T1030 |
| SC-09 | Config-drift-enabled exposure | none (latent) + external | config change removes auth on an endpoint | 4 | config_attest>=1 @ s1; egress_seg>=1 @ s3 | 40-50 planned config changes | T1190(approx), T1562.001 |
| SC-10 | CI/CD identity abuse | external | pipeline token with deploy scope | 7 | priv_approval>=2 @ s4; cred_rotation>=1 @ s2 | 70-90 real deploys | T1195.002(approx), T1078.004 |
| SC-11 | Dormant-account reactivation | external | dormant 6%, no mfa, stale role | 6 | dormancy_lock>=1 @ s2; mfa>=1 @ s3 | 4-8 legitimate reactivations | T1078, T1098 |
| SC-12 | MFA fatigue / push bombing | external | valid password, push MFA | 5 | mfa>=3 (number-match) @ s3; rate_limiting>=2 @ s2 | 25-45 flaky-device storms | T1621 |
| SC-13 | Session fixation on legacy-web | external | PHP session id accepted pre-auth | 6 | session_binding>=2 @ s4; egress_seg>=1 @ s6 | legacy idle resumptions | T1185(approx) |
| SC-14 | Multi-stage combination (SC-02 -> SC-05 -> SC-08) | external -> insider path | chained preconditions of all three | 31 | no single control blocks; min cut size 2 | full noise bed | composite |
| SC-15 | Partner API key replay across tenants | external | partner key, weak tenant scoping | 6 | svc_isolation>=2 @ s3; rate_limiting>=1 @ s5 | partner_api normal traffic | T1550.001(approx) |
| SC-16 | Suppression-assisted intrusion | external w/ log access | attacker can delete iam_audit segment | 8 | cred_rotation>=1 @ s2 under P_max only | deletion hidden in maintenance window | T1070.002 |

SC-14 and SC-16 are the ECLIPSE showcases. SC-14 must have `expected_min_cut_size: 2` and a
verified certificate proving no single control from the declared catalog severs it. SC-16 must
produce a SUPPRESSED (not BLIND) liveness basis via a BLAKE3 chain break, and its
`blindness_premium` (`S_rob \ S_opt`) must be non-empty — that is the scenario that demonstrates
"this control is in the cut only because you cannot see".

28.3 PER-SCENARIO REQUIREMENTS

For every scenario file, all of the following must hold or the build fails:

1. Every `emits` SourceId exists in `range/sources.toml` and is produced by the service named in
   `where`.
2. Every `expect_transition` names a dimension and state pair that exists in the state model
   (see section 17), and the reconstructed transition from real telemetry matches it.
3. Every `expected_block_points` row is reproduced by the concrete simulator at the stated level
   and not at level-1, including the `null` rows.
4. The kernel and the concrete simulator agree on the outcome for 256 randomized control
   configurations of this scenario (the gate in section 7 of the ECLIPSE spec).
5. `unobserved_steps` are exactly the steps with `emits: []`, and each one must be inside a
   licensed window under P_max or be forced by an obligation axiom — otherwise the scenario is
   permanently invisible and must be labeled `visibility: none` in the catalog rather than
   silently shipped.
6. The scenario's ground truth (section 29) is emitted by the same simulator call that performs
   the step.
7. A `noise_bed` entry that is not actually generated in the scenario window fails the build.

28.4 NEGATIVE REQUIREMENTS

- Do NOT describe these as attacks that occurred. Every rendering surface — UI, report, README,
  certificate narration — must carry the word "simulated" next to the scenario name.
- Do NOT claim ATT&CK coverage. State per-technique fidelity (`exact` / `approximate`) and never
  aggregate it into a coverage percentage.
- Do NOT implement an adaptive attacker that reacts to the control configuration. ECLIPSE's
  guarantees are stated for a non-adaptive attacker; an adaptive simulator would invalidate them.
  If adaptivity is added later it requires a separate verdict class.
- Do NOT write scenario-specific logic anywhere in the detector, reconstructor, or kernel. Grep
  gate: no scenario id (`SC-\d\d`) may appear outside `datasets/`, `tests/`, and `docs/`.
- Do NOT tune a rule until a scenario passes. Rules are declared in `rules.toml` with a provenance
  note; a rule whose note says "added to detect SC-09" is a review-blocking finding.

============================================================
29. GROUND TRUTH AND DATASET GENERATION
============================================================

Ground truth is generated *with* events, by the same code path, in the same transaction. There is
no labeling pass, no heuristic tagging, no human annotation, and no post-hoc join by timestamp
proximity.

29.1 THE CO-EMISSION RULE

The simulator and population generator expose exactly one emit primitive:

```rust
// crates/spectra-popgen/src/emit.rs
pub fn emit(
    ctx: &mut RunCtx,
    ev: RangeEvent,                    // what the range service will actually produce
    truth: Option<TruthAnnotation>,    // None for benign; Some(..) for scenario-driven
) -> EmitReceipt;                      // { event_id: EventId, truth_id: Option<TruthId> }
```

- `emit` writes the event to the range service call path **and** appends the annotation to
  `truth.jsonl` in one operation, returning both ids. There is no other way to produce an event.
- `TruthAnnotation` never travels into `RangeEvent`. A compile-time test (a negative trybuild case)
  asserts `RangeEvent` has no field of a truth type.
- The normalizer rejects any bundle line containing a key in the reserved truth namespace
  (`__truth*`, `label`, `is_attack`, `scenario`), exit code 4.
- CI gate `no_posthoc_labeling`: fails if the string `truth` appears in any module that imports
  the reconstruction, detection, or ECLIPSE kernel crates.

29.2 GROUND-TRUTH SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "schemas/truth.schema.json",
  "title": "TruthAnnotation",
  "type": "object",
  "additionalProperties": false,
  "required": ["truth_id","event_id","emitted_at","kind","origin"],
  "properties": {
    "truth_id":    { "type": "string", "pattern": "^tr_[0-9a-f]{16}$" },
    "event_id":    { "type": "string", "pattern": "^ev_[0-9a-f]{16}$" },
    "emitted_at":  { "type": "string", "format": "date-time" },
    "sim_tick":    { "type": "integer", "minimum": 0 },
    "kind":        { "enum": ["benign","attack_step","attack_unobserved","noise_lookalike","control_artifact"] },
    "origin":      { "enum": ["population","scenario","degradation","range_internal"] },
    "chain_id":    { "type": ["string","null"], "pattern": "^SC-[0-9]{2}$" },
    "step_k":      { "type": ["integer","null"], "minimum": 1 },
    "step_action": { "type": ["string","null"] },
    "actor_ref":   { "type": "string" },
    "subject_ref": { "type": ["string","null"] },
    "true_transition": {
      "type": ["object","null"],
      "required": ["dim","from","to"],
      "properties": {
        "dim":  { "enum": ["identity","session","credential","privilege","process","network","api","service","resource","trust"] },
        "from": { "type": "string" },
        "to":   { "type": "string" }
      }
    },
    "true_causal_parents": { "type": "array", "items": { "type": "string", "pattern": "^tr_[0-9a-f]{16}$" } },
    "observable":  { "type": "boolean", "description": "false iff no configured source could ever record it" },
    "producing_sources": { "type": "array", "items": { "type": "string" } },
    "lookalike_of": { "type": ["string","null"], "description": "benign twin of this attack step type" },
    "suppressed_by": { "type": ["string","null"], "enum": [null,"degradation","scenario_actor"] },
    "notes":       { "type": ["string","null"], "maxLength": 512 }
  }
}
```

29.3 TRUTH STORAGE DDL

```sql
-- migrations/0031_ground_truth.sql
CREATE TABLE truth_annotation (
    truth_id            TEXT PRIMARY KEY,
    dataset_id          TEXT NOT NULL REFERENCES dataset(dataset_id) ON DELETE CASCADE,
    event_id            TEXT NOT NULL,
    emitted_at          TIMESTAMPTZ NOT NULL,
    sim_tick            BIGINT NOT NULL,
    kind                TEXT NOT NULL CHECK (kind IN
                          ('benign','attack_step','attack_unobserved','noise_lookalike','control_artifact')),
    origin              TEXT NOT NULL CHECK (origin IN
                          ('population','scenario','degradation','range_internal')),
    chain_id            TEXT NULL,
    step_k              INT  NULL,
    step_action         TEXT NULL,
    actor_ref           TEXT NOT NULL,
    subject_ref         TEXT NULL,
    true_dim            TEXT NULL,
    true_from           TEXT NULL,
    true_to             TEXT NULL,
    observable          BOOLEAN NOT NULL,
    producing_sources   TEXT[] NOT NULL DEFAULT '{}',
    lookalike_of        TEXT NULL,
    suppressed_by       TEXT NULL,
    CONSTRAINT chain_step_pair CHECK ((chain_id IS NULL) = (step_k IS NULL)),
    CONSTRAINT unobserved_has_no_sources CHECK
        (kind <> 'attack_unobserved' OR cardinality(producing_sources) = 0)
);
CREATE UNIQUE INDEX truth_event_uniq ON truth_annotation (dataset_id, event_id)
    WHERE kind <> 'attack_unobserved';
CREATE INDEX truth_chain_idx ON truth_annotation (dataset_id, chain_id, step_k);

CREATE TABLE truth_edge (        -- the ground-truth causal DAG
    dataset_id TEXT NOT NULL,
    parent_id  TEXT NOT NULL REFERENCES truth_annotation(truth_id) ON DELETE CASCADE,
    child_id   TEXT NOT NULL REFERENCES truth_annotation(truth_id) ON DELETE CASCADE,
    PRIMARY KEY (dataset_id, parent_id, child_id)
);

CREATE TABLE dataset (
    dataset_id        TEXT PRIMARY KEY,        -- e.g. base-14d-v1@blake3:3f9a1c...
    name              TEXT NOT NULL,
    version           INT  NOT NULL,
    parent_dataset_id TEXT NULL REFERENCES dataset(dataset_id),  -- degradation lineage
    manifest_hash     TEXT NOT NULL,
    seed              BIGINT NOT NULL,
    epoch             TIMESTAMPTZ NOT NULL,
    generator_version TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);
```

29.4 MANIFEST

`datasets/<name>/<version>/manifest.json`, content-addressed, BLAKE3 throughout:

```json
{
  "manifest_version": 2,
  "dataset_id": "base-14d-v1",
  "manifest_hash": "blake3:3f9a1c47bd2e0915c8...",
  "parent": null,
  "seed": 20260214,
  "epoch": "2026-02-14T00:00:00Z",
  "days": 14,
  "generator": {
    "popgen": "spectra-popgen 0.9.3 (rustc 1.83.0, target x86_64-unknown-linux-gnu)",
    "simulator": "attack-simulator 0.9.3",
    "normalizer": "spectra-normalizer 0.9.3",
    "range_images": "range/images.lock@blake3:71c0d2..."
  },
  "config_hashes": {
    "population.toml": "blake3:aa14...",
    "volume_targets.toml": "blake3:0e77...",
    "scenarios/": "blake3:c391..."
  },
  "scenarios": ["SC-01","SC-03","SC-05","SC-07","SC-08","SC-14","SC-16"],
  "files": [
    { "path": "bundle.jsonl", "bytes": 3612884991, "blake3": "blake3:9d41..." , "lines": 5981442 },
    { "path": "truth.jsonl",  "bytes": 214553102,  "blake3": "blake3:be02...", "lines": 5981911 },
    { "path": "liveness_inputs.json", "bytes": 88211, "blake3": "blake3:44f1..." },
    { "path": "population_snapshot.json", "bytes": 9911204, "blake3": "blake3:1c8e..." }
  ],
  "counts": {
    "events": 5981442, "truth_annotations": 5981911,
    "attack_steps": 402, "attack_unobserved": 67,
    "benign": 5980, "lookalike": 129503,
    "sources": 16, "blind_minutes_natural": 63
  },
  "degradation": null,
  "signed_by_run": "run_2026-09-12T11:04:21Z_b7c1",
  "reproducible": true
}
```

Degraded variants set `parent` to the base `dataset_id` and fill `degradation`:

```json
"degradation": { "completeness": 0.70, "operators": ["delete","delay","duplicate","reorder","corrupt","suppress"],
                 "degradation_seed": 7710, "operator_config_hash": "blake3:5511..." }
```

A degraded dataset is derived, never regenerated: it is a deterministic transform of the parent's
`bundle.jsonl` plus the parent's `truth.jsonl` carried through unchanged except that dropped
events acquire `suppressed_by: "degradation"`. Truth is never degraded — that is what makes the
"zero false ROBUST across 100%->30%" invariant checkable.

29.5 MAKE TARGETS AND BIT-IDENTICAL REGENERATION

```
make dataset-base SEED=20260214 DAYS=14 NAME=base-14d VERSION=1
make dataset-degrade PARENT=base-14d-v1 COMPLETENESS=0.70 DSEED=7710
make dataset-matrix  PARENT=base-14d-v1          # 100,90,80,70,60,50,40,30
make dataset-verify  DATASET=base-14d-v1
make dataset-reproduce DATASET=base-14d-v1       # regenerate into a temp dir, diff hashes
make dataset-gc
```

`make dataset-reproduce` is the determinism gate and runs in CI nightly:

```
$ make dataset-reproduce DATASET=base-14d-v1
[repro] reading manifest datasets/base-14d/1/manifest.json (blake3:3f9a1c47...)
[repro] pinning range images from range/images.lock (blake3:71c0d2...)
[repro] seed=20260214 epoch=2026-02-14T00:00:00Z generator=spectra-popgen 0.9.3
[repro] cold range-up .................................. 192.7s
[repro] population generation .......................... 611.4s
[repro] scenario execution (7 scenarios) ............... 148.9s
[repro] normalize + entity resolution .................. 231.0s
[repro] comparing artifacts against manifest
        bundle.jsonl            blake3:9d41...  MATCH
        truth.jsonl             blake3:be02...  MATCH
        liveness_inputs.json    blake3:44f1...  MATCH
        population_snapshot.json blake3:1c8e...  MATCH
[repro] counts MATCH (events=5981442, attack_steps=402, attack_unobserved=67)
[repro] OK  bit-identical  total 1184.0s
```

Determinism requirements that make this possible, all mandatory:

1. Simulated clock only. No service may call wall-clock time; the range injects
   `SPECTRA_CLOCK_EPOCH` and a monotonic tick source, and a CI gate greps for forbidden time
   calls per language (`System.currentTimeMillis`, `time.Now`, `DateTime.Now`, `Time.now`,
   `time()`, `os.time`, `datetime.now`) outside an approved clock shim.
2. EventIds are assigned by the normalizer as `ev_ = blake3(canonical_event_bytes)[0:16]`, not by
   a counter, so ordering changes cannot shift ids.
3. `bundle.jsonl` is written in canonical JSON (sorted keys, no floats without fixed formatting,
   RFC3339 UTC with fixed precision) and sorted by `(sim_tick, source_id, ev_)`.
4. Every random draw comes from a named substream: `blake3(seed || substream_name)` seeds a
   ChaCha20 instance. Adding a substream never perturbs existing ones; there is a test.
5. No container concurrency may reach the artifact: the collector serializes per source, and the
   normalizer's final sort makes inter-source interleaving irrelevant.
6. Image digests are part of the manifest; a digest change invalidates reproducibility and the
   verify target says so rather than failing silently.

29.6 THE MANIFEST RULE

No benchmark, evaluation, figure, table, or README number may be produced from a dataset that
lacks a recorded manifest. Enforcement, not convention:

- The benchmark harness takes `--dataset <dataset_id>` only. It resolves the id through the
  `dataset` table, recomputes the manifest hash of the on-disk files, and aborts with
  `MANIFEST_MISMATCH` if it differs.
- Every result row written by the harness carries `dataset_id`, `manifest_hash`, `seed`,
  `generator_version`, `git_commit`, and `run_id`. The results table has
  `NOT NULL` on all six and a foreign key on `dataset_id`.
- Every ECLIPSE certificate embeds `hashes.bundle`; the Go checker recomputes it. A certificate
  whose bundle hash is absent from the `dataset` table is reported as `UNREGISTERED_DATASET` and
  may not be displayed as a result.
- Docs gate: `tools/docs-numbers-check` scans markdown for numeric claims marked with the
  `{{metric:...}}` macro and fails if the referenced metric has no backing row in the results
  table. A bare number in prose that looks like a metric and is not macro-wrapped is a
  review-blocking finding.

29.7 GROUND-TRUTH-DERIVED INVARIANTS (build fails otherwise)

| invariant | statement | where enforced |
|---|---|---|
| I-1 | Zero false ROBUST: across the whole 100%->30% matrix, no certificate with `mode: ROBUST` and no flags may have a cut that, per ground truth, fails to sever the true chain | `tests/eclipse/test_no_false_robust.py` |
| I-2 | Truth completeness: every `attack_step` with `observable: true` has at least one `producing_source` that was live at its time in the base dataset | dataset build |
| I-3 | Unobserved coverage: every `attack_unobserved` is either inside a licensed window or forced by an obligation axiom, else the scenario is marked `visibility: none` | dataset build |
| I-4 | Label purity: `bundle.jsonl` contains no key in the truth namespace | normalizer, exit 4 |
| I-5 | Lineage: every degraded dataset's `truth.jsonl` differs from its parent's only in `suppressed_by` fields | `make dataset-verify` |
| I-6 | Cardinality: `truth.jsonl` line count == event count + unobserved step count | manifest check |
| I-7 | Monotone visibility: reconstruction recall at completeness c1 >= recall at c2 for c1 > c2 on the same seed, or the violation is reported as a finding with the two runs' ids — never smoothed away | benchmark harness |

29.8 NEGATIVE REQUIREMENTS

- Do NOT derive labels from detector output, rule matches, timestamp windows, or an LLM. Any
  labeling function that reads `bundle.jsonl` is forbidden; truth is write-only at generation.
- Do NOT edit a published dataset in place. Datasets are immutable; a change is a new version with
  a new manifest and a recorded `parent_dataset_id`.
- Do NOT report a metric from an unregistered, uncommitted, or locally-modified dataset, and do not
  add a `--force` flag to the harness that would allow it.
- Do NOT carry ground truth into the reconstruction, ECLIPSE kernel, certificate, or UI request
  path. Truth is used only by tests, the benchmark harness, and the degradation evaluator. The
  dependency graph gate fails if the kernel crate transitively depends on the truth crate.
- Do NOT invent completeness levels, confidence scores, or interpolated points between measured
  matrix cells. Plot only cells that were run.
