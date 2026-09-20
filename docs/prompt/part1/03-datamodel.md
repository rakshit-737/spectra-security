============================================================
9. ENTITY MODEL
============================================================

9.1 Purpose

Implement a closed entity catalog. Every canonical event references entities only through stable
`EntityId` values. Reconstruction, the security-state machine, the causal graph and the ECLIPSE
kernel address entities exclusively by `EntityId`; raw strings from telemetry never reach them.

9.2 Entity kinds (closed set — do not add kinds without extending this table and the migration)

| Kind code | Entity            | Natural key (anchor tuple)                                  | Mutable? |
|-----------|-------------------|-------------------------------------------------------------|----------|
| `idn`     | Identity          | (realm, canonical_subject)                                   | no       |
| `acct`    | Account           | (realm, provider, account_ref)                               | no       |
| `svcacct` | ServiceAccount    | (realm, provider, account_ref)                               | no       |
| `cred`    | Credential        | (realm, cred_class, cred_ref_hash)                           | no       |
| `sess`    | Session           | (realm, issuer, session_ref)                                 | no       |
| `tok`     | Token             | (realm, issuer, token_ref_hash)                              | no       |
| `dev`     | Device            | (realm, device_ref)                                          | no       |
| `host`    | Host              | (realm, host_ref)                                            | no       |
| `ctr`     | Container         | (realm, host_ref, container_ref)                             | no       |
| `proc`    | Process           | (host_id, pid, start_time_ns)                                | no       |
| `svc`     | Service           | (realm, service_name)                                        | no       |
| `api`     | ApiEndpoint       | (service_id, method, normalized_path)                        | no       |
| `res`     | Resource          | (realm, res_class, resource_ref)                             | no       |
| `role`    | Role              | (realm, role_name)                                           | no       |
| `grant`   | Grant             | (principal_id, role_id, scope_ref, granted_at_ns)            | no       |
| `netif`   | NetworkEndpoint   | (realm, zone, addr, port, proto)                             | no       |
| `flow`    | NetworkFlow       | (src_netif_id, dst_netif_id, first_seen_ns)                  | no       |
| `zone`    | NetworkZone       | (realm, zone_name)                                           | no       |
| `ctl`     | ControlInstance   | (realm, control_id, scope_ref)                               | no       |
| `src`     | TelemetrySource   | (realm, source_name)                                         | no       |
| `col`     | Collector         | (source_id, collector_instance)                              | no       |

`Principal` is not a kind; it is the union type `{idn, acct, svcacct}` used by grants, sessions and
process ownership. Implement it as a Rust enum and a Python `Literal` union, not as a table.

9.3 Stable identifier format

```
EntityId   := kind "-" b32                     ; e.g. "sess-k4m2q9x7t1b0dfe3"
kind       := one of the kind codes in 9.2
b32        := 16 chars, RFC4648 lowercase base32 alphabet, no padding
             = base32( BLAKE3_128( anchor_bytes ) )
anchor_bytes := scenario_id LF kind LF field_1 US field_2 US ... US field_n
             ; LF = 0x0A, US = 0x1F
             ; fields in the exact order given in 9.2, NFC-normalized,
             ; case-folded ONLY for fields declared case-insensitive in the realm profile
```

Requirements:
- IDs are deterministic and content-addressed. Two runs of the same seeded scenario must produce
  byte-identical `EntityId` sets. Gate this with a test that hashes the sorted entity table.
- IDs are never sequential, never database-assigned, never time-based beyond the declared anchor.
- `scenario_id` is in the anchor, so entities from different scenarios can never collide or merge.
- `realm` is the trust domain string from the source registry (e.g. `corp.idp`, `prod.k8s`). It is
  declared in configuration, never inferred.
- Secret-bearing anchors (`cred_ref_hash`, `token_ref_hash`) are BLAKE3-256 of the raw value,
  computed at the adapter boundary. Raw credential material must never be stored, logged, printed
  in errors, or placed in a certificate. Enforce with a repository-wide secret-scan test.
- Do not use `EntityId` as a foreign key alone in Postgres; store `(scenario_id, entity_id)` as the
  composite primary key so a single database can hold many scenarios.

9.4 Common entity envelope

Every entity row carries: `entity_id`, `kind`, `scenario_id`, `realm`, `display_name`,
`first_seen_ns`, `last_seen_ns`, `resolution_state` (`RESOLVED` | `PROVISIONAL` | `UNRESOLVED` |
`SPLIT_SUSPECT`), `alias_count`, `evidence_ids[]` (the `EventId`s that witnessed it),
`attributes` (JSONB, kind-specific, schema-validated), `derived` (boolean — true when the entity
exists only because of an obligation axiom and was never directly observed).

A `derived` entity is a modelling artifact. It must render as GHOST in the UI, must never be
counted as an observed entity in any metric, and must carry the license that admitted it.

9.5 Kind-specific fields (abridged to the load-bearing ones)

- `idn`: `canonical_subject`, `employee_ref`, `is_human` (bool, declared by the source registry,
  never guessed), `department`, `status` ∈ {active, suspended, deprovisioned}.
- `acct` / `svcacct`: `provider`, `account_ref`, `owner_identity_id` (nullable), `created_at_ns`,
  `is_shared` (bool, declared).
- `cred`: `cred_class` ∈ {password, api_key, ssh_key, cert, refresh_token, access_token,
  session_cookie, kubeconfig, cloud_key, service_token}, `issued_at_ns`, `expires_at_ns`,
  `rotation_generation` (u32), `bound_to` (nullable `dev`/`host`/`netif` id), `scopes[]`.
- `sess`: `issuer`, `principal_id`, `auth_strength` ∈ {password, mfa_otp, mfa_hardware, federated,
  none}, `bound_device_id`, `bound_netif_id`, `issued_at_ns`, `expires_at_ns`,
  `state` (see 9.6), `parent_session_id` (for exchange/impersonation chains).
- `proc`: `host_id`, `pid`, `start_time_ns`, `exit_time_ns`, `argv_hash`, `exe_path`,
  `parent_proc_id`, `euid`, `egid`, `capabilities[]`, `container_id` (nullable).
- `res`: `res_class` ∈ {file, object, db_table, secret, queue, repo, image, config}, `sensitivity`
  ∈ {public, internal, confidential, restricted} (declared in the scenario fixture, never inferred),
  `owner_principal_id`, `zone_id`.
- `ctl`: `control_id` (must exist in `controls.toml`), `level` (u8, within `L_k`), `scope_ref`,
  `enforced_by_service_id`. Control instances are the bridge between telemetry and the ECLIPSE
  control catalog; a control observed in telemetry but absent from `controls.toml` is an ingest
  error, not a silently created control.

9.6 Lifecycles (state machines — implement literally, one transition table per kind)

```
SESSION
  (none) --session.created--> ACTIVE
  ACTIVE --session.refreshed--> ACTIVE
  ACTIVE --session.ip_changed / device_changed--> ACTIVE(rebound)   [flags binding_violation]
  ACTIVE --session.expired--> EXPIRED
  ACTIVE --session.revoked--> REVOKED
  ACTIVE --session.terminated--> CLOSED
  EXPIRED|REVOKED|CLOSED --session.used--> ZOMBIE_USE   [obligation violation, see 11.6]
  Terminal: EXPIRED, REVOKED, CLOSED, ZOMBIE_USE

CREDENTIAL
  (none) --credential.issued--> VALID
  VALID --credential.rotated--> SUPERSEDED  (new cred entity, rotation_generation+1)
  VALID --credential.revoked--> REVOKED
  VALID --(clock >= expires_at_ns)--> EXPIRED      [time-indexed, never a retraction]
  VALID|SUPERSEDED --credential.presented--> VALID|SUPERSEDED (no state change; records use)
  Terminal: REVOKED, EXPIRED

PROCESS
  (none) --process.exec--> RUNNING
  RUNNING --process.setuid / capability_change--> RUNNING(privileged)
  RUNNING --process.exit--> EXITED
  RUNNING --(host down, no exit observed)--> ORPHANED
  Terminal: EXITED, ORPHANED

GRANT
  (none) --privilege.granted--> ACTIVE
  ACTIVE --privilege.assumed--> ACTIVE(in_use)
  ACTIVE --privilege.dropped / role_removed--> RELINQUISHED
  ACTIVE --(expiry tick)--> LAPSED
  Terminal: RELINQUISHED, LAPSED
```

State is time-indexed. Never mutate a past state row. Each transition writes a new
`(entity_id, t_ns, state, cause_event_id)` tuple to `entity_state_history`. A linter must reject any
code path that issues `UPDATE` on a state row; only `INSERT` is permitted.

9.7 Entity-relationship diagram

```
                       +-----------+          owns          +------------+
                       | Identity  |-----------------------▶|  Account   |
                       |  (idn)    |◀--------+              |  (acct)    |
                       +-----------+         |              +-----+------+
                            │ human          | owner              │ principal
                            │                |                    │
                            │          +-----+--------+           │
                            │          | ServiceAcct  |           │
                            │          |  (svcacct)   |           │
                            │          +-----+--------+           │
                            └───────────┬────┴────────────────────┘
                                        ▼ principal_id
     +----------+   binds   +-----------+-----------+   authenticates_with   +-----------+
     | Device   |◀──────────|        Session        |───────────────────────▶|Credential |
     |  (dev)   |           |        (sess)         |                        |  (cred)   |
     +----+-----+           +-----+-----------+-----+                        +-----+-----+
          │ runs_on               │ drives    │ exchanged_for                      │ issued_for
          ▼                       ▼           ▼                                    │
     +----------+  hosts   +-----------+   +-------+                               │
     |   Host   |─────────▶| Process   |   | Token |◀──────────────────────────────┘
     |  (host)  |          |  (proc)   |   | (tok) |
     +----+-----+          +-----+-----+   +---+---+
          │ hosts                │ opens       │ presented_to
          ▼                      ▼             ▼
     +----------+          +-----------+   +------------+  exposes  +-------------+
     |Container |          | Resource  |   |  Service   |──────────▶| ApiEndpoint |
     |  (ctr)   |          |  (res)    |   |   (svc)    |           |    (api)    |
     +----+-----+          +-----+-----+   +-----+------+           +------+------+
          │ attached_to          │ in_zone      │ enforces                │ guarded_by
          ▼                      ▼              ▼                         ▼
     +-----------+  in    +-----------+   +--------------+        +--------------+
     |NetworkEP  |───────▶|   Zone    |◀--| ControlInst  |───────▶|    Grant     |
     |  (netif)  |        |  (zone)   |   |    (ctl)     | gates  |   (grant)    |
     +-----+-----+        +-----------+   +--------------+        +------+-------+
           │ endpoint_of                                                  │ confers
           ▼                                                              ▼
     +-----------+                                                  +-----------+
     |   Flow    |                                                  |   Role    |
     |  (flow)   |                                                  |  (role)   |
     +-----------+                                                  +-----------+

     Every box is also an edge target of:  TelemetrySource (src) --emits--> Collector (col)
                                           Collector --witnessed--> (any entity, via EventId)
```

9.8 Relationship table (edges are first-class rows, time-bounded, evidence-backed)

| Edge                     | From      | To        | Cardinality | Valid interval | Evidence required |
|--------------------------|-----------|-----------|-------------|----------------|-------------------|
| `owns`                   | idn       | acct      | 1:N         | yes            | yes               |
| `principal_of`           | acct/svcacct | sess   | 1:N         | yes            | yes               |
| `authenticates_with`     | sess      | cred      | N:M         | yes            | yes               |
| `bound_to_device`        | sess      | dev       | 0..1        | yes            | yes               |
| `bound_to_endpoint`      | sess      | netif     | 0..1        | yes            | yes               |
| `exchanged_for`          | sess/tok  | tok       | 1:N         | yes            | yes               |
| `runs_as`                | proc      | acct/svcacct | N:1      | yes            | yes               |
| `parent_of`              | proc      | proc      | 1:N         | yes            | yes               |
| `accesses`               | proc/sess | res       | N:M         | yes            | yes               |
| `connects`               | netif     | netif     | N:M         | yes            | yes               |
| `confers`                | grant     | role      | N:1         | yes            | yes               |
| `gates`                  | ctl       | api/res/zone/grant | N:M | yes          | declared          |
| `derived_from`           | any       | any       | N:M         | yes            | license required  |

Every edge row stores `first_seen_ns`, `last_seen_ns`, `evidence_ids[]`, and `license_id` (null
unless the edge exists only under a silent envelope). An edge with `license_id != null` is a GHOST
edge and is excluded from every observed-count metric.

9.9 Negative requirements

- Do not invent entities to make a graph look complete. An entity exists only if an event witnessed
  it or an obligation axiom forced it under a valid license.
- Do not store raw secrets, raw tokens or raw passwords in any entity attribute.
- Do not attach risk scores, confidence values, severity numbers or "threat levels" to entities.
- Do not mutate an entity's `EntityId` after creation. Merges produce alias rows (see 12.7), never
  rewrites.
- Do not model an entity kind that only exists to support a UI panel.

============================================================
10. CANONICAL EVENT MODEL
============================================================

10.1 Position

One canonical event form. Every adapter emits it, every downstream component consumes only it.
Adapters are the only code permitted to read a vendor format. Reconstruction code that string-parses
raw telemetry is a build failure; enforce with an import lint that forbids `spectra.adapters.*`
symbols outside the adapter package.

10.2 Canonical event JSON Schema (`schemas/event/1.0.0.json`, draft 2020-12, complete)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://spectra.local/schema/event/1.0.0.json",
  "title": "SpectraCanonicalEvent",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","event_id","event_type","dimension","occurred_at_ns",
               "observed_at_ns","time_trust","scenario_id","run_id","source","outcome","evidence"],
  "properties": {
    "schema_version": { "type": "string", "pattern": "^1\\.[0-9]+\\.[0-9]+$" },
    "event_id":       { "$ref": "#/$defs/EventId" },
    "event_type":     { "type": "string",
                        "pattern": "^(authentication|session|credential|privilege|process|network|api|resource|service|control|config)\\.[a-z0-9_]+(\\.[a-z0-9_]+)*$" },
    "dimension":      { "enum": ["identity","session","credential","privilege","process",
                                 "network","api","service","resource","trust"] },
    "occurred_at_ns": { "$ref": "#/$defs/Ns" },
    "observed_at_ns": { "$ref": "#/$defs/Ns" },
    "ingested_at_ns": { "$ref": "#/$defs/Ns" },
    "time_trust":     { "enum": ["authoritative","collector","inferred","untrusted"] },
    "time_skew_ns":   { "type": "integer" },
    "scenario_id":    { "type": "string", "pattern": "^[a-z0-9][a-z0-9_-]{2,63}$" },
    "run_id":         { "type": "string", "pattern": "^[0-9a-f]{32}$" },
    "source":         { "$ref": "#/$defs/Source" },
    "actor":          { "$ref": "#/$defs/EntityRef" },
    "target":         { "$ref": "#/$defs/EntityRef" },
    "on_behalf_of":   { "$ref": "#/$defs/EntityRef" },
    "session_ref":    { "$ref": "#/$defs/EntityRef" },
    "credential_ref": { "$ref": "#/$defs/EntityRef" },
    "process_ref":    { "$ref": "#/$defs/EntityRef" },
    "host_ref":       { "$ref": "#/$defs/EntityRef" },
    "container_ref":  { "$ref": "#/$defs/EntityRef" },
    "service_ref":    { "$ref": "#/$defs/EntityRef" },
    "resource_ref":   { "$ref": "#/$defs/EntityRef" },
    "network":        { "$ref": "#/$defs/Network" },
    "outcome":        { "enum": ["success","failure","denied","error","unknown"] },
    "reason_code":    { "type": "string", "maxLength": 64 },
    "control_context":{ "type": "array", "items": { "$ref": "#/$defs/ControlObservation" },
                        "maxItems": 32 },
    "attributes":     { "type": "object" },
    "raw_identifiers":{ "type": "array", "items": { "$ref": "#/$defs/RawIdentifier" },
                        "maxItems": 32 },
    "evidence":       { "$ref": "#/$defs/Evidence" },
    "integrity":      { "enum": ["OK","GAP_BEFORE","CHAIN_BREAK","DUPLICATE","REORDERED",
                                 "CORRUPT_FIELD","BACKDATED"] },
    "degradation":    { "$ref": "#/$defs/Degradation" },
    "ground_truth":   { "$ref": "#/$defs/GroundTruth" }
  },
  "$defs": {
    "Ns": { "type": "integer", "minimum": 0, "maximum": 9223372036854775807 },
    "EventId": { "type": "string", "pattern": "^evt-[a-z2-7]{26}$" },
    "B3": { "type": "string", "pattern": "^b3:[0-9a-f]{64}$" },
    "EntityRef": {
      "type": "object", "additionalProperties": false,
      "required": ["entity_id","kind"],
      "properties": {
        "entity_id": { "type": "string", "pattern": "^[a-z]{3,7}-[a-z2-7]{16}$" },
        "kind": { "type": "string" },
        "resolution_state": { "enum": ["RESOLVED","PROVISIONAL","UNRESOLVED","SPLIT_SUSPECT"] },
        "resolved_by_rule": { "type": "string", "pattern": "^R[0-9]{1,2}$" },
        "raw": { "type": "string", "maxLength": 512 }
      }
    },
    "Source": {
      "type": "object", "additionalProperties": false,
      "required": ["source_id","collector_id","stream_id","seq","input_format","sensor_kind"],
      "properties": {
        "source_id":    { "type": "string", "pattern": "^src-[a-z2-7]{16}$" },
        "collector_id": { "type": "string", "pattern": "^col-[a-z2-7]{16}$" },
        "stream_id":    { "type": "string", "maxLength": 128 },
        "seq":          { "type": "integer", "minimum": 0 },
        "input_format": { "enum": ["json","jsonl","csv","xml","yaml","syslog","winxml","binlog"] },
        "sensor_kind":  { "enum": ["idp","os_audit","ebpf","netflow","proxy","api_gateway",
                                   "k8s_audit","db_audit","app_log","control_plane"] },
        "adapter_version": { "type": "string" },
        "source_record_ref": { "type": "string", "maxLength": 256 }
      }
    },
    "Network": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "src_addr": { "type": "string" }, "src_port": { "type": "integer","minimum":0,"maximum":65535 },
        "dst_addr": { "type": "string" }, "dst_port": { "type": "integer","minimum":0,"maximum":65535 },
        "proto": { "enum": ["tcp","udp","icmp","other"] },
        "l7": { "enum": ["http","https","dns","ssh","rdp","smb","postgres","grpc","other"] },
        "src_zone": { "type": "string" }, "dst_zone": { "type": "string" },
        "bytes_out": { "type": "integer","minimum":0 }, "bytes_in": { "type": "integer","minimum":0 },
        "direction": { "enum": ["inbound","outbound","lateral","loopback"] },
        "verdict": { "enum": ["allowed","blocked","reset","unknown"] }
      }
    },
    "ControlObservation": {
      "type": "object", "additionalProperties": false,
      "required": ["control_id","level","evaluated"],
      "properties": {
        "control_id": { "type": "string", "pattern": "^[a-z0-9_]{3,48}$" },
        "level": { "type": "integer", "minimum": 0, "maximum": 8 },
        "evaluated": { "type": "boolean" },
        "result": { "enum": ["pass","fail","not_applicable","bypassed","unknown"] }
      }
    },
    "RawIdentifier": {
      "type": "object", "additionalProperties": false,
      "required": ["class","value"],
      "properties": {
        "class": { "enum": ["username","upn","email","uid","gid","sid","account_ref","token_hash",
                            "cred_hash","session_ref","device_ref","host_ref","container_ref",
                            "ip","mac","cert_fp","pid","service_name","resource_ref"] },
        "value": { "type": "string", "maxLength": 512 },
        "realm": { "type": "string", "maxLength": 64 }
      }
    },
    "Evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["content_hash","chain_hash"],
      "properties": {
        "content_hash": { "$ref": "#/$defs/B3" },
        "chain_prev":   { "$ref": "#/$defs/B3" },
        "chain_hash":   { "$ref": "#/$defs/B3" },
        "raw_blob_ref": { "type": "string", "maxLength": 256 },
        "adapter_lossy": { "type": "boolean" },
        "dropped_fields": { "type": "array", "items": { "type": "string" }, "maxItems": 64 }
      }
    },
    "Degradation": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "completeness_pct": { "type": "integer", "minimum": 0, "maximum": 100 },
        "mutation": { "enum": ["none","delayed","duplicated","reordered","corrupted","suppressed"] },
        "delay_ns": { "type": "integer", "minimum": 0 }
      }
    },
    "GroundTruth": {
      "type": "object", "additionalProperties": false,
      "properties": {
        "is_attack_step": { "type": "boolean" },
        "technique_label": { "type": "string", "maxLength": 64 },
        "chain_position": { "type": "integer", "minimum": 0 }
      }
    }
  },
  "allOf": [
    { "if": { "properties": { "dimension": { "const": "network" } }, "required": ["dimension"] },
      "then": { "required": ["network"] } },
    { "if": { "properties": { "dimension": { "const": "session" } }, "required": ["dimension"] },
      "then": { "required": ["session_ref","actor"] } },
    { "if": { "properties": { "dimension": { "const": "credential" } }, "required": ["dimension"] },
      "then": { "required": ["credential_ref"] } },
    { "if": { "properties": { "dimension": { "const": "process" } }, "required": ["dimension"] },
      "then": { "required": ["process_ref","host_ref"] } },
    { "if": { "properties": { "dimension": { "const": "api" } }, "required": ["dimension"] },
      "then": { "required": ["service_ref","actor"] } },
    { "if": { "properties": { "dimension": { "const": "resource" } }, "required": ["dimension"] },
      "then": { "required": ["resource_ref","actor"] } },
    { "if": { "properties": { "dimension": { "const": "trust" } }, "required": ["dimension"] },
      "then": { "required": ["control_context"] } }
  ]
}
```

`event_id` is content-addressed: `evt-` + base32(BLAKE3_128(canonical_json_without_event_id)),
where canonical JSON is RFC 8785 JCS. Two adapters that normalize the same record to the same
canonical content produce the same `EventId`; this is what makes certificate leaf references stable.

10.3 Event taxonomy (implement all of these; the type string is a closed enum generated from
`schemas/event_types.toml` and compiled into Python, Rust and Go)

```
authentication.  attempt | password.verified | password.failed | success | failure | denied
                 mfa.challenged | mfa.satisfied | mfa.failed | mfa.bypassed | mfa.enrolled
                 federated.assertion | device_code.issued | step_up.required | lockout
                 anonymous.allowed
session.         created | resumed | refreshed | reassigned | binding.checked | binding.violated
                 ip_changed | device_changed | idle_timeout | expired | revoked | terminated
                 used | replayed | impersonation.started | impersonation.ended
credential.      issued | presented | accepted | rejected | rotated | revoked | expired
                 exported | stored | read | reused_elsewhere | scope_expanded | delegated
                 exchanged | brute_forced | shared_detected
privilege.       requested | approval_requested | approval_granted | approval_denied | granted
                 denied | assumed | dropped | role_assigned | role_removed | escalation_observed
                 sudo_invoked | setuid_observed | impersonation_granted
process.         exec | fork | exit | signal | module_load | injected | setuid | capability_change
                 namespace_change | file_open | file_read | file_write | file_delete | file_chmod
                 socket_open | ptrace
network.         flow.open | flow.close | connection.denied | dns.query | dns.response
                 tls.handshake | tls.failed | segment.crossed | egress.blocked | egress.allowed
                 lateral.attempt | port.listen | proxy.request | vpn.connect
api.             request | response | auth.rejected | rate_limited | scope.denied
                 token.introspected | bulk_read | object.enumerated | webhook.registered
                 pagination.exhausted | error
resource.        created | read | modified | deleted | permission_changed | shared
                 snapshot_taken | downloaded | listed | exfil_candidate
service.         account.used | account.created | deployed | started | stopped
                 config_reloaded | health_changed | dependency_called | scaled
control.         evaluated | enforced | bypassed | exempted | misconfigured | state_changed
                 disabled | enabled
config.          changed | policy_updated | rbac_updated | secret_rotated | logging_changed
                 collector_disabled | collector_enabled | clock_adjusted | retention_changed
```

Rules:
- `resource.exfil_candidate` is a structural marker (volume + zone crossing + sensitivity), never a
  verdict. It must not appear in any UI element labelled "detection".
- `config.collector_disabled` and `config.logging_changed` are first-class: they are the primary
  producers of SUPPRESSED liveness basis for the ECLIPSE kernel.
- No `*.suspicious`, `*.malicious`, `*.anomaly` event types. Scoring is not an event.

10.4 Required vs optional

| Field group | Always required | Required by dimension | Optional |
|-------------|-----------------|------------------------|----------|
| identity of the record | `schema_version`, `event_id`, `event_type`, `dimension`, `scenario_id`, `run_id` | — | — |
| time | `occurred_at_ns`, `observed_at_ns`, `time_trust` | — | `ingested_at_ns`, `time_skew_ns` |
| provenance | `source`, `evidence` | — | `integrity`, `degradation` |
| semantics | `outcome` | per the `allOf` block in 10.2 | `reason_code`, `attributes` |
| entities | — | see `allOf` | all other `*_ref` fields |
| generator-only | — | — | `ground_truth` |

`ground_truth` is written only by the scenario generator and only into fixture bundles. The ingest
path must strip it into a separate sidecar file before any reconstruction code can read the bundle.
Gate: a test that loads every fixture through the analysis API and asserts `ground_truth` is absent
from every object reachable by the reconstruction package.

10.5 Schema versioning and migration policy

- Version is semver on the schema, stored in every event. Directory `schemas/event/<version>.json`.
- PATCH: documentation, description, pattern tightening that rejects nothing previously accepted.
- MINOR: new optional field, new enum member in a non-required position, new event type. Consumers
  must accept unknown MINOR versions within the same MAJOR by ignoring unknown optional fields —
  except `additionalProperties:false` forbids unknown properties, so a MINOR bump always ships a new
  schema file and a bumped `MAX_MINOR` constant in every language binding.
- MAJOR: any removal, rename, retype, or required-field addition.
- Migrations live in `migrations/events/<from>__<to>/` with `forward.py`, `forward.rs`, a fixture
  pair `in.jsonl` / `expected.jsonl`, and a note. Forward-only. No down-migrations.
- `spectra events migrate --bundle b.jsonl --to 1.2.0` rewrites and re-derives `event_id`. Because
  `event_id` is content-addressed, a migration changes IDs; it therefore also emits `idmap.json`
  and any certificate produced against the old bundle is marked stale by hash mismatch.
- Ingesting an event whose MAJOR exceeds the binary's is a hard error. Ingesting a lower MAJOR
  without a migration chain is a hard error. Never silently coerce.
- Every language binding (Python Pydantic v2, Rust serde, Go struct, TypeScript type) is generated
  from the JSON Schema by `make schemas`. Hand-written duplicates are a build failure; CI regenerates
  and fails on diff.

10.6 Normalization contract

Each adapter is a pure function `bytes -> Vec<CanonicalEvent> + Vec<NormalizationError>`. It must be
deterministic, must not perform network I/O, must not consult the entity store, and must emit
`raw_identifiers` rather than `EntityId`s. Entity resolution runs after normalization (section 12),
so adapters fill `*_ref` fields only after the resolver pass rewrites them.

| Input format | Framing | Field mapping source | Time source | Loss policy |
|--------------|---------|----------------------|-------------|-------------|
| `json`       | one object or array | `adapters/<name>/map.toml` | declared field | record `dropped_fields` |
| `jsonl`      | line-delimited, `\n` | same | declared field | same |
| `csv`        | RFC 4180, declared header | positional map + type coercion table | declared column | unmapped columns → `attributes.raw_<col>` |
| `xml`        | single root, streaming | XPath map | XPath | text nodes preserved |
| `yaml`       | multi-document `---` | same as json | declared key | anchors expanded before mapping |
| `syslog`     | RFC 3164/5424-ish line | named regex with mandatory `ts`, `host`, `app`, `msg` + per-app kv grammar | syslog ts + year from stream epoch | unparsed tail → `attributes.raw_tail` |
| `winxml`     | `<Event>` elements | `EventID` → type table, `EventData/Data[@Name]` | `TimeCreated/@SystemTime` | all `Data` retained in `attributes` |

Mandatory adapter behaviors:
1. Compute `evidence.content_hash` over the exact raw record bytes before any parsing.
2. Set `time_trust`: `authoritative` when the record carries a timestamp from the enforcing system
   with a declared clock source; `collector` when only the collector timestamp exists; `inferred`
   when derived from neighboring records; `untrusted` when the timestamp fails the monotonicity
   constraints in the difference-constraint pass (see the liveness section of the ECLIPSE kernel).
3. Never invent `occurred_at_ns`. If absent, set `occurred_at_ns = observed_at_ns` and
   `time_trust = "collector"`, and record `attributes._time_synthesized = true`.
4. Emit one canonical event per source record. Never fan a record into multiple events unless the
   format is inherently a batch (XML `<EventList>`, JSON array); never merge records.
5. A record that cannot be mapped produces a `NormalizationError` with the raw hash and reason, and
   is counted in `ingest_report.json`. Silent drops are a build failure; assert
   `records_in == events_out + errors_out` in a test on every fixture.
6. Unit-normalize: all times to UTC nanoseconds, all addresses to canonical form (IPv6 compressed,
   IPv4-mapped kept as IPv4), all paths to POSIX-style with the source's declared root, all
   usernames NFC-normalized and case-folded only per realm profile.

10.7 Worked example A — syslog-ish sshd line

Before (`sshd.log`, `input_format: syslog`, `sensor_kind: os_audit`):
```
Mar 11 04:17:22 app-07 sshd[21884]: Accepted publickey for deploy from 10.40.2.19 port 51022 ssh2: RSA SHA256:9c0f...e1
```
After (canonical, abridged to non-null fields):
```json
{
  "schema_version":"1.0.0",
  "event_id":"evt-3f9ak2m7qz1x8b4tn6wcdr5pjy",
  "event_type":"authentication.success",
  "dimension":"identity",
  "occurred_at_ns":1741666642000000000,
  "observed_at_ns":1741666642143000000,
  "time_trust":"collector",
  "scenario_id":"s07-token-pivot",
  "run_id":"9b1c7f0a2e4d46b38a5c0d1e2f334455",
  "source":{"source_id":"src-h2q9x7t1b0dfe3k4","collector_id":"col-m4n8p2r6s0v1w3y5",
            "stream_id":"app-07/sshd","seq":10482,"input_format":"syslog",
            "sensor_kind":"os_audit","adapter_version":"sshd/1.4.0"},
  "outcome":"success",
  "reason_code":"publickey",
  "raw_identifiers":[{"class":"username","value":"deploy","realm":"prod.linux"},
                     {"class":"host_ref","value":"app-07","realm":"prod.linux"},
                     {"class":"ip","value":"10.40.2.19","realm":"prod.net"},
                     {"class":"cert_fp","value":"SHA256:9c0f...e1","realm":"prod.linux"}],
  "network":{"src_addr":"10.40.2.19","src_port":51022,"dst_port":22,"proto":"tcp","l7":"ssh",
             "verdict":"allowed","direction":"lateral"},
  "control_context":[{"control_id":"mfa","level":0,"evaluated":false,"result":"not_applicable"}],
  "attributes":{"auth_method":"publickey","sshd_pid":21884},
  "evidence":{"content_hash":"b3:7c1e...","chain_prev":"b3:0a42...","chain_hash":"b3:be93..."},
  "integrity":"OK"
}
```

10.8 Worked example B — Windows-style XML 4624

Before (`security.evtx.xml`, `input_format: winxml`):
```xml
<Event><System><EventID>4624</EventID>
  <TimeCreated SystemTime="2026-03-11T04:19:03.4412Z"/><Computer>WIN-FS01</Computer>
  <EventRecordID>884120</EventRecordID></System>
 <EventData>
  <Data Name="TargetUserName">svc_backup</Data><Data Name="TargetUserSid">S-1-5-21-77-1104</Data>
  <Data Name="LogonType">3</Data><Data Name="LogonId">0x3E7A91</Data>
  <Data Name="IpAddress">10.40.2.19</Data><Data Name="AuthenticationPackageName">NTLM</Data>
 </EventData></Event>
```
After (abridged): `event_type: "authentication.success"`, `dimension: "identity"`,
`occurred_at_ns: 1741666743441200000`, `time_trust: "authoritative"`,
`raw_identifiers: [{username, svc_backup, corp.ad}, {sid, S-1-5-21-77-1104, corp.ad},
{session_ref, 0x3E7A91, corp.ad}, {host_ref, WIN-FS01, corp.ad}, {ip, 10.40.2.19, prod.net}]`,
`attributes: {logon_type: 3, auth_package: "NTLM", event_record_id: 884120}`,
`control_context: [{control_id:"mfa", level:0, evaluated:false, result:"not_applicable"}]`,
`source.source_record_ref: "884120"`.
A second canonical event `session.created` is NOT emitted here; the `session.created` fact is
derived by the rule table from the `LogonId` identifier, not fabricated by the adapter.

10.9 Worked example C — CSV API gateway log

Before (`gw.csv`, header `ts,method,path,status,principal,token_id,bytes,src_ip,route`):
```
2026-03-11T04:21:58.001Z,GET,/api/v2/customers?page=41,200,svc_backup,tk_9f31,184320,10.40.2.19,customers-v2
```
After (abridged): `event_type: "api.bulk_read"` (selected because the route map declares
`customers-v2` as a bulk route and `bytes > declared threshold`; the threshold lives in the adapter
map, is printed in `ingest_report.json`, and is not a score), `dimension: "api"`, `outcome: "success"`,
`network: {src_addr:"10.40.2.19", l7:"https", dst_zone:"app"}`,
`raw_identifiers: [{account_ref, svc_backup, corp.idp}, {token_hash, b3:..of tk_9f31.., corp.idp}]`,
`attributes: {method:"GET", path_template:"/api/v2/customers", page:41, status:200, bytes:184320}`.
Note the query string is split into `path_template` + `attributes.page`; raw paths with identifiers
must be templated so `api` entities do not explode.

10.10 Negative requirements

- Do not add vendor-specific fields to the canonical schema. They belong in `attributes`.
- Do not let an adapter assign `EntityId`s, consult the database, or read other records' state.
- Do not emit an event with a timestamp the adapter guessed without setting `time_trust` correctly.
- Do not normalize away the raw record: `evidence.raw_blob_ref` must resolve to the original bytes.
- Do not use floating-point timestamps anywhere. Nanosecond integers only.

============================================================
11. EVIDENCE AND PROVENANCE MODEL
============================================================

11.1 Evidence record

Every canonical event has exactly one evidence record. Evidence is the leaf of every ECLIPSE
derivation; a rule instance whose `evidence` vector references an `EventId` with no evidence row is
rejected by the kernel and by the independent Go checker.

```sql
CREATE TABLE evidence (
  scenario_id     text        NOT NULL,
  event_id        text        NOT NULL,
  collector_id    text        NOT NULL,
  stream_id       text        NOT NULL,
  seq             bigint      NOT NULL,
  content_hash    bytea       NOT NULL,          -- BLAKE3-256 over raw record bytes
  chain_prev      bytea       NOT NULL,
  chain_hash      bytea       NOT NULL,
  raw_blob_ref    text        NOT NULL,          -- content-addressed path in the blob store
  raw_byte_len    integer     NOT NULL,
  observed_at_ns  bigint      NOT NULL,
  adapter_version text        NOT NULL,
  adapter_lossy   boolean     NOT NULL DEFAULT false,
  integrity       text        NOT NULL,          -- OK|GAP_BEFORE|CHAIN_BREAK|DUPLICATE|...
  PRIMARY KEY (scenario_id, event_id),
  UNIQUE (scenario_id, collector_id, stream_id, seq, content_hash)
);
CREATE INDEX evidence_stream_seq ON evidence (scenario_id, collector_id, stream_id, seq);
```

11.2 Collector identity and streams

- A `Collector` (`col-…`) is one process instance emitting one or more `stream_id`s. A
  `TelemetrySource` (`src-…`) is the logical sensor; many collectors may serve one source over time.
- `(collector_id, stream_id)` defines an ordered sequence space. `seq` is a gapless
  monotonically increasing `u64` assigned by the collector at emission, starting at 0 for each
  stream epoch. `seq` is never re-used and never reset without a new `stream_epoch`.
- Every collector declares itself once per epoch with a `collector.declare` record carrying
  `collector_id`, `source_id`, `stream_epoch`, `clock_source`, `declared_flush_interval_ns`. Streams
  without a declaration are ingested but marked `UNDECLARED` and can never support a liveness claim.

11.3 Content hashing and per-stream chaining

```
content_hash_n = BLAKE3_256( raw_record_bytes_n )
chain_hash_0   = BLAKE3_256( "spectra.chain.v1" || collector_id || stream_id || u64le(epoch) )
chain_hash_n   = BLAKE3_256( chain_hash_{n-1} || content_hash_n || u64le(seq_n) )
```
The chain is computed by the collector at emission and recomputed by the ingester. A mismatch is
`CHAIN_BREAK`. Chain state per stream is checkpointed every N records into `chain_checkpoints`
so verification can start mid-stream.

11.4 Gap and anomaly detection (exact semantics)

Process each stream in `seq` order. For consecutive stored records `a` then `b`:

| Condition | Classification | Effect |
|-----------|----------------|--------|
| `b.seq == a.seq + 1` and `b.chain_prev == a.chain_hash` | `OK` | none |
| `b.seq > a.seq + 1` and chain recomputes only if the missing records existed | `GAP_BEFORE`, gap length `b.seq - a.seq - 1` | interval `[a.observed_at_ns, b.observed_at_ns]` becomes a SUPPRESSED-basis candidate |
| `b.seq == a.seq` and `b.content_hash == a.content_hash` | `DUPLICATE` | deduplicate; keep first; count |
| `b.seq == a.seq` and `b.content_hash != a.content_hash` | `CHAIN_BREAK` (fork) | both retained, stream marked forked, no liveness claim permitted anywhere in the epoch |
| `b.seq < a.seq` on arrival order | `REORDERED` | reorder by `seq`; record transport reorder count |
| `b.chain_prev != a.chain_hash` with contiguous `seq` | `CHAIN_BREAK` | record mutated or rewritten |
| record parses but a mandatory field fails type coercion | `CORRUPT_FIELD` | event dropped, `NormalizationError` emitted |
| `occurred_at_ns` violates the difference constraints derived from the stream and its peers | `BACKDATED` | timestamp marked `untrusted`; any license resting on it is voided |

Outputs: `integrity_report.json` per run, containing per-stream record counts, gap count and total
gap length, duplicate count, reorder count, fork flag, and the derived candidate intervals. This
file is an input to the liveness pass and is hashed into the ECLIPSE certificate.

11.5 Tamper detection semantics

- **Truncation** (records removed from the tail): detected only if a later record or a checkpoint
  references the missing `seq`, or if the stream declaration promised a flush cadence that is
  violated. Otherwise it is indistinguishable from a quiet sensor and must be reported as BLIND,
  not SUPPRESSED.
- **Excision** (records removed from the middle): detected as `GAP_BEFORE` + `CHAIN_BREAK`.
- **Mutation** (record edited in place): detected as `CHAIN_BREAK` at the mutated record.
- **Forgery with recomputation** (adversary rewrites the record and the entire downstream chain):
  **not detected**. State this in the UI and in the certificate.
- Detection localizes tampering to a `(collector, stream, seq-interval, time-interval)` tuple. That
  tuple is what the ECLIPSE liveness pass consumes as `License { basis: Suppressed }`.

11.6 Obligation-based evidence of absence

Obligation axioms (`session.used ⇒ session.issued`, `process.file_read ⇒ process.file_open`,
`credential.presented ⇒ credential.issued`, ~40 total) are the second source of evidence-of-absence.
An unsatisfied obligation is a structural fact, not a heuristic: it either forces a silent rule
instance under a valid license, or — when no license covers the window — is reported as an
`UNEXPLAINED_OBLIGATION` in `integrity_report.json` and must appear in the UI. It must never be
quietly satisfied by inventing an event.

11.7 What integrity property is and is NOT provided

Provided:
- Detection of accidental loss, transport reordering, duplication, and naive deletion or in-place
  edit of stored records by an actor who does not recompute the chain.
- Deterministic localization of a break to a stream and an index/time interval.
- Content addressing: any event referenced by a certificate can be re-fetched and re-hashed, so a
  certificate cannot silently refer to different bytes than the ones analyzed.

NOT provided — write this verbatim in `docs/evidence.md`, in `spectra verify` output, and in the
certificate's `flags`:
- **No cryptographic authenticity.** Collectors are unsigned. There is no key, no signature, no MAC.
  Anyone who can write to the evidence store can rewrite the chain from the break forward and the
  result will verify. BLAKE3 here provides integrity against corruption and naive tampering only.
- **No non-repudiation, no proof of origin, no trusted timestamping.** `time_trust` is a declared
  property of the source, not a verified one.
- **No append-only guarantee.** Postgres is not a ledger. There is no external anchor, no
  transparency log, no TPM, no remote attestation.
- **No claim about reality.** Evidence attests what was ingested, not what happened.

An optional `--signed-collectors` mode may implement Ed25519 per-collector signing over
`chain_hash`. It is off by default. When on, the certificate must record the public key set hash and
the flag `signed_collectors: true`; when off, the flag must read `false` and any language in the UI
implying authenticity must be absent. Do not ship the signing path as the default to make the
integrity story sound stronger than it is.

============================================================
12. ENTITY RESOLUTION
============================================================

12.1 Contract

Entity resolution is a pure, deterministic function from
`(ordered canonical events, source registry, realm profiles)` to
`(entity table, alias table, edge table, resolution report)`. No randomness, no thresholds tuned by
eye, no embeddings, no similarity scores, no machine learning. Running it twice on the same input
must produce byte-identical output; running it on a shuffled input must produce the same output
after canonical sorting. Gate both.

12.2 Identifier classes and strength tiers

| Tier | Meaning | Classes |
|------|---------|---------|
| A — authoritative | globally unique within a realm, issued by a naming authority | `sid`, `uid` (with realm), `account_ref`, `session_ref`, `token_hash`, `cred_hash`, `container_ref`, `cert_fp`, `resource_ref` |
| B — strong-local | unique within a declared scope | `username` (realm-scoped), `upn`, `email`, `host_ref`, `device_ref`, `service_name`, `mac` |
| C — weak | reusable, shared, or address-like | `ip`, `pid`, `gid` |

Tier C identifiers may never, alone, merge two entities. Tier B merges only within one realm and
only when the realm profile declares the class unique. Tier A merges across realms only when an
explicit `identity_link` event or a declared mapping in the source registry authorizes it.

12.3 Deterministic resolution rules (evaluated in this fixed order; rule id is recorded on every
resolved reference as `resolved_by_rule`)

```
R1  Same realm + same Tier-A class + same value            -> same entity
R2  Same realm + same Tier-B class + realm declares unique  -> same entity
R3  authentication.* carrying both username and sid in one record -> link(username, sid)  [same realm]
R4  session.created carrying session_ref + principal ref    -> bind session to principal
R5  credential.issued carrying cred_hash + principal ref    -> bind credential to principal
R6  credential.exchanged / session.exchanged_for            -> link parent/child token+session
R7  process.exec on host H with pid P at t                  -> proc entity (H, P, exec_time_ns)
R8  process.* with pid P on H at t, no exec observed        -> attach to the unique proc with
                                                               start<=t<exit; if not unique -> UNRESOLVED
R9  container_ref + host_ref in one record                  -> bind container to host
R10 netif (zone, addr, port, proto): zone from the source registry, never from the address alone
R11 flow endpoints resolve to netif only within the declared zone's validity interval
R12 declared mapping in source_registry.toml (e.g. corp.ad:S-1-5-21-77-1104 == corp.idp:svc_backup)
                                                            -> cross-realm link, Tier-A only
R13 identity_link event emitted by a control-plane source   -> cross-realm link, evidence recorded
R14 nothing above matched                                   -> UNRESOLVED entity (12.6)
```

Each rule is implemented as a named function, has at least one positive and one negative unit test,
and declares which identifier tiers it may consume. A rule that consumes a Tier-C identifier as its
sole basis is rejected by a lint.

12.4 Algorithm

```python
def resolve(events, registry, profiles) -> Resolution:
    # Phase 0 — canonical order. Ties broken deterministically, never by arrival.
    events = sorted(events, key=lambda e: (e.occurred_at_ns, e.source.collector_id,
                                           e.source.stream_id, e.source.seq, e.event_id))

    uf = TypedUnionFind()            # nodes = (realm, class, value); merges only within a kind
    claims: dict[Node, list[Claim]] = defaultdict(list)

    # Phase 1 — node creation. Every raw_identifier becomes a node. No merging yet.
    for e in events:
        for rid in e.raw_identifiers:
            uf.add(Node(rid.realm, rid.class, normalize(rid, profiles)), witness=e.event_id)

    # Phase 2 — intra-record linking. Apply R1..R11 in order, recording the rule and witness.
    for e in events:
        for rule in RULES_INTRA:                      # ordered, total, side-effect-free predicates
            for (a, b) in rule.links(e, profiles):
                uf.union(a, b, rule=rule.id, witness=e.event_id, t=e.occurred_at_ns)

    # Phase 3 — declared and evidenced cross-realm links (R12, R13).
    for link in registry.declared_links() + collect_identity_link_events(events):
        uf.union(link.a, link.b, rule=link.rule, witness=link.witness, t=link.t)

    # Phase 4 — conflict detection BEFORE materialization.
    conflicts = detect_conflicts(uf, profiles)         # 12.5
    uf = apply_conflict_policy(uf, conflicts)          # may split components

    # Phase 5 — materialization. One component -> one entity; anchor tuple per section 9.2 is built
    # from the component's HIGHEST-tier identifiers in class order, so the EntityId is stable even
    # if a weak identifier is later added.
    entities = {}
    for comp in uf.components_sorted():                # sorted by min node key: deterministic
        kind   = infer_kind(comp, profiles)            # table-driven, total; unknown -> error
        anchor = anchor_tuple(kind, comp)              # highest-tier identifiers only
        eid    = entity_id(kind, scenario_id, anchor)
        entities[eid] = Entity(eid, kind, comp, state=comp.state, evidence=comp.witnesses)

    # Phase 6 — reference rewriting. Each event's raw_identifiers are mapped to EntityIds.
    # A raw identifier in no component, or in a component whose kind is ambiguous, yields an
    # UNRESOLVED entity reference (12.6). Never drop the reference.
    return Resolution(entities, aliases=uf.alias_rows(), report=build_report(...))
```

Complexity: `O(N·k·α(N))` for N events with k identifiers each (α = inverse Ackermann); conflict
detection is `O(E)` over union edges. Publish the measured wall time and component-size histogram in
`resolution_report.json`; do not state complexity as a substitute for measurement.

12.5 Conflict handling

| Conflict | Detection | Policy |
|----------|-----------|--------|
| Type conflict — a component contains nodes whose `infer_kind` disagrees | during phase 4 | Split at the lowest-tier union edge. Both halves become `SPLIT_SUSPECT`. Record both in the report. Never guess a kind. |
| Cardinality conflict — two distinct Tier-A values of the same class in one component (two `sid`s for one identity) | during phase 4 | Split by rule provenance: drop the union edge with the highest rule number (weakest rule); if tied, drop the one with the later witness timestamp; if still tied, drop the lexicographically larger witness `EventId`. Deterministic by construction. |
| Temporal conflict — a link asserted at `t1` contradicted at `t2` (pid reuse, token rotation, DHCP lease change) | validity intervals on edges | Do not merge across the boundary. Emit two entities with disjoint validity intervals and a `succeeded_by` edge. |
| Shared identifier — realm profile declares the class non-unique (e.g. `shared_admin`) | registry-declared | Never merge on it. Mark the account `is_shared=true`; all sessions attach to the account, none to an identity. |
| Realm collision — same value, different realms, no declared link | phase 3 | Keep separate. Emit a `POSSIBLE_CROSS_REALM` note in the report. Do not merge. |

Conflicts are never resolved by scoring, voting, majority, or recency heuristics beyond the fixed
tie-break above. Every split is recorded with the dropped edge, its rule and its witness so a human
can audit it and so the degradation harness can measure split/merge error against generator truth.

12.6 Unresolved entity state

```
UnresolvedId := "unres-" base32(BLAKE3_128(scenario_id LF kind_guess LF sorted_raw_identifiers))
```
An unresolved reference is a real, addressable, persisted entity with
`resolution_state = "UNRESOLVED"`. It carries the raw identifiers that produced it and the reason
code (`NO_RULE_MATCHED`, `AMBIGUOUS_PID`, `KIND_AMBIGUOUS`, `SPLIT_SUSPECT`, `REALM_UNKNOWN`).

Requirements:
- Unresolved entities participate in the graph and in ECLIPSE grounding. They are never dropped and
  never silently merged into the nearest plausible entity.
- A derivation whose leaves include an unresolved entity is marked `ambiguous_entity` in the
  certificate flags, and such a run may not be presented as ROBUST without that flag shown.
- The UI renders unresolved entities with a distinct shape and an "unresolved: <reason>" label.
- `resolution_report.json` publishes counts: resolved, provisional, unresolved, split_suspect,
  merges performed per rule, and the largest component size. These are measured, never estimated.

12.7 Aliasing

Aliases are rows, not rewrites: `(scenario_id, entity_id, realm, class, value, first_seen_ns,
last_seen_ns, rule_id, witness_event_id)`. `EntityId` never changes once materialized. A later merge
that would change an entity's anchor tuple is forbidden mid-run; the resolver is a single batch pass
over the complete bundle. Incremental resolution is explicitly out of scope — do not implement it.

12.8 Failure modes (document each, test each, measure each against generator ground truth)

1. **Over-merge** — two principals collapsed into one because a realm profile wrongly declared a
   class unique. Effect: fabricated lateral movement. Detection: cardinality conflict, or truth
   comparison on fixtures. Metric: `over_merge_rate` per scenario.
2. **Under-merge** — one principal split across realms because no declared link existed. Effect: the
   attack chain breaks and ECLIPSE reports a smaller cut than reality requires. Detection: truth
   comparison; symptom is an unexplained obligation. Metric: `under_merge_rate`.
3. **PID reuse** — R8 finds two candidate processes. Must yield UNRESOLVED, never the most recent.
   Regression test with a fixture that reuses a pid within 200 ms.
4. **NAT / shared egress collapse** — many hosts behind one address. Prevented structurally: R10
   forbids deriving identity from an address; zone comes from the registry.
5. **Token rotation** — a rotated credential is a new entity with `rotation_generation+1` and a
   `succeeded_by` edge, never the same entity. Test that a rotation does not merge generations.
6. **Clock skew across realms** — phase 0 ordering becomes wrong. Mitigated by the difference-
   constraint pass; events with `time_trust = "untrusted"` are ordered by `(collector, seq)` within
   their stream and may not be used by rules that depend on inter-realm ordering (R3, R6, R13).
7. **Adversarial identifier injection** — telemetry contains attacker-chosen usernames designed to
   collide. Structurally limited: cross-realm merges require Tier-A plus a declared or evidenced
   link, so a free-text field cannot cause a merge. Add a fixture that attempts it and assert no
   merge occurs.

12.9 Negative requirements

- Do not use fuzzy matching, Levenshtein distance, embeddings, clustering, or any learned model in
  the resolver. The optional ML baseline elsewhere in SPECTRA must never write to the entity table.
- Do not produce a confidence score for a resolution. The output is a rule id and a witness, or
  UNRESOLVED.
- Do not silently drop a raw identifier that resolves to nothing.
- Do not allow the resolver to read `ground_truth`. Enforce by running it in a process that receives
  the stripped bundle only, and by a test that fails if `ground_truth` keys are reachable.
- Do not let resolution depend on iteration order of a hash map in any language. Use sorted
  iteration everywhere; add a test that runs the resolver under three different insertion orders and
  diffs the serialized output byte for byte.
