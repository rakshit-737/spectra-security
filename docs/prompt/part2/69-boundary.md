============================================================
69. KERNEL BOUNDARY, ABI AND THE PERSISTENCE BOUNDARY
============================================================

69.0 WHAT THIS SECTION OWNS

This section fixes two integration surfaces Part I left undefined and which, left undefined, are
the two most likely places for the build to stall or to silently lose the offline-verification
property.

(a) THE ABI. How the Python service layer invokes the Rust kernel (`spectra-kernel`) and the Go
    checker (`spectra-verify`): transport, serialization, version negotiation, exit codes, stderr
    diagnostics, resource contract, and every failure mode.
(b) THE PERSISTENCE BOUNDARY. What is a row in PostgreSQL, what is an immutable content-addressed
    file on disk, what Redis is permitted to hold, and the retention, sizing and garbage-collection
    rules for run artifacts.

OVERRIDES Part I: sections 35-38 described the HTTP API but never stated how Python reaches the
kernel or the checker; the feasibility critic named this "the single most likely integration stall
in the build." This section is now normative and Part I's silence is replaced.

OVERRIDES Part I: the stack line listed PostgreSQL, Redis and arq alongside a "local-first, fully
offline" claim without saying which components may depend on them. This section declares the kernel
and the checker to be service-free, file-in/file-out binaries. If any future section implies
otherwise, this section wins.

------------------------------------------------------------
69.1 THE ABI DECISION
------------------------------------------------------------

69.1.1 Implement the boundary as SUBPROCESS INVOCATION OVER CONTENT-ADDRESSED FILES. The parent
process passes CAS identifiers on argv; the child reads inputs from a CAS root, writes outputs into
the same CAS root, emits one line of canonical JSON on stdout naming the outputs, emits NDJSON
diagnostics on stderr, and exits with a code from the taxonomy in 69.8.

69.1.2 Do NOT use pyo3, do NOT use cgo, do NOT use a long-lived RPC server, do NOT use shared
memory, do NOT use a socket. These are forbidden for the kernel and checker boundaries. A pyo3
extension module is permitted nowhere in this repository.

69.1.3 Justification, stated once so it is not relitigated:

| Property required by this project      | subprocess + CAS | pyo3 in-process | cgo in-process |
|----------------------------------------|------------------|-----------------|----------------|
| Kernel usable with Python absent        | yes              | no              | no             |
| Checker usable by a third party         | yes (one binary) | no              | no             |
| Crash/OOM isolation from the API worker | yes              | no              | no             |
| Byte-identical replay from argv alone   | yes              | hard            | hard           |
| Independence of checker enforceable     | build-graph lint | fiction         | fiction        |
| ABI drift caught by a schema gate       | yes              | ad hoc          | ad hoc         |
| Build matrix cost on a clean clone      | two static bins  | ABI3 wheels     | CGO_ENABLED=1  |

    The decisive argument is the checker. ECLIPSE §5 and section 62 require `spectra-verify` to be
    an artifact a sceptic can run without this repository's Python, database, or network. A linked
    extension module cannot be that artifact. Once the checker must be a standalone binary, making
    the kernel one too costs nothing and buys crash isolation and replayability.

69.1.4 The per-invocation process cost is real and accepted. Budget it as fork/exec plus static
binary startup, on the order of single-digit milliseconds (illustrative, not a target). Because a
PROVE request already performs grounding over thousands of rule instances, process startup is not
on the critical path. Do not optimize it. Do not introduce a warm worker pool.

69.1.5 NEGATIVE: the kernel and the checker must never accept a filesystem path or a URL as an
input reference. They accept only `blake3:<64 lowercase hex>` object ids plus exactly one
`--cas-root` directory. This closes path traversal and SSRF on the ingest and PROVE endpoints at
the ABI layer rather than in request validation.

OVERRIDES Part I section 37: the checker invoked on a filesystem path
(`spectra verify cert build/cert_3f9a12.json`) is replaced by object-id-only arguments,
`--cert blake3:<64 lowercase hex>` plus exactly one `--cas-root`; a certificate supplied inline in
the body of Part I section 36's verify endpoint must be written into the CAS by the Python layer
before the checker sees it. An implementer following Part I hands the checker a path under
`data/runs/`, which the binary rejects with exit 2.

------------------------------------------------------------
69.2 PROCESS TOPOLOGY
------------------------------------------------------------

```
  +-------------------------+        +------------------------------+
  |  FastAPI / arq worker   |        |  PostgreSQL  (index, meta)   |
  |  (Python, section 35-38)|<------>|  Redis       (job state)     |
  +-----------+-------------+        +------------------------------+
              |  fork/exec, argv = CAS ids
              |  stdout: 1 line result pointer
              |  stderr: NDJSON diagnostics
              v
  +-------------------------+           +---------------------------+
  |  spectra-kernel (Rust)  |  reads /  |  CAS ROOT (disk)          |
  |  spectra-verify (Go)    |<--writes->|  immutable, content-addr. |
  |  NO db. NO net. NO clock|           |  bundles, facts, certs,   |
  +-------------------------+           |  liveness, manifests, bench|
                                        +---------------------------+

  Hard rule: no arrow exists from either binary to PostgreSQL, Redis, the network,
  the system clock, the environment, or $HOME. Enforced by 69.20.3 and 69.20.4.
```

69.2.1 The Python layer is the ONLY component that may touch PostgreSQL or Redis. The Rust kernel
and the Go checker are pure functions of (argv, CAS contents).

69.2.2 A third party reproduces any published verdict with:

```
$ docker run --rm --network none --read-only \
    -v $PWD/cas:/cas:ro -v $PWD/out:/out \
    ghcr.io/<owner>/spectra-verify@sha256:<digest> \
    --abi 1 --cas-root /cas --cert blake3:9f2c... --out-dir /out
```

    No database, no compose file, no Python. If this command ever requires a service, the
    offline-verification claim is void and the build must fail (69.20.4).

------------------------------------------------------------
69.3 THE CAS ROOT
------------------------------------------------------------

69.3.1 Layout. One directory, fanned out by the first four hex characters, one object per file,
never mutated after creation, never renamed, never appended to.

```
var/spectra/cas/
  objects/9f/2c/9f2c8ad1...e07.bin          # payload, exact bytes that were hashed
  objects/9f/2c/9f2c8ad1...e07.meta.json    # kind, abi, codec, size, created_run
  runs/<run_id>/manifest.json               # symlink-free index of this run's objects
  tmp/                                      # write-then-rename staging only
```

OVERRIDES Part I section 32: the root tree's run-artifact home `data/runs/`, and its instruction to
produce that structure exactly and invent no extra top-level directories, are replaced by the CAS
root above; section 69 additionally requires the top-level paths `abi/v1/` (69.5.4),
`budgets/default.toml` (69.10.1) and `services/kernel_client.py` (69.12.1). An implementer who
writes run artifacts to `data/runs/<run_id>/cert.json` produces files the kernel, the checker and
the GC cannot address, because every input reference is a CAS object id.

69.3.2 Object id = `blake3:` + hex of BLAKE3-256 over the payload bytes AS STORED. If the payload is
compressed, the hash covers the compressed bytes and `.meta.json` records the uncompressed hash as
well. The certificate's hashes (owned by the certificate-canonicalization section of Part II) always
reference UNCOMPRESSED canonical bytes; the CAS id is a storage detail and must never appear inside
a certificate.

69.3.3 Object kinds. Fixed, closed set; the `kind` field is validated on read:

| kind              | codec            | producer        | consumers              |
|-------------------|------------------|-----------------|------------------------|
| `bundle`          | NDJSON + zstd    | generator       | kernel, checker         |
| `rules`           | TOML (raw bytes) | author          | kernel, checker         |
| `controls`        | TOML             | author          | kernel, checker         |
| `costs`           | TOML             | author          | kernel                  |
| `goal`            | TOML             | goal library    | kernel, checker          |
| `er_config`       | TOML             | author          | resolver, kernel         |
| `factbase`        | SFB binary (69.6)| kernel          | kernel (later stages)    |
| `liveness`        | canonical JSON   | kernel          | checker, UI              |
| `cert`            | canonical JSON   | kernel          | checker, UI, narrator    |
| `instances`       | SFB binary       | kernel          | checker                  |
| `run_manifest`    | canonical JSON   | Python layer    | everything               |
| `bench_result`    | canonical JSON   | bench harness   | docs build               |
| `quarantine`      | NDJSON           | ingest          | operator, docs           |

69.3.4 Writes are atomic: write into `tmp/`, fsync, rename into place. A rename onto an existing
object is a no-op (the content is identical by construction). If the bytes differ from an existing
object under the same id, abort with exit 8 (internal invariant) — this indicates a hash collision
or a corrupt store, never a normal condition.

69.3.5 NEGATIVE: no object is ever deleted except by the garbage collector in 69.18. No process
other than the GC opens an existing object for writing. The CAS root is mounted read-only into the
checker container.

------------------------------------------------------------
69.4 INVOCATION CONTRACT
------------------------------------------------------------

69.4.1 Kernel invocation. Every argument is either a literal, an object id, or a directory.

```
spectra-kernel prove
  --abi 1
  --cas-root /var/spectra/cas
  --bundle     blake3:4c1f...   --rules   blake3:aa07...
  --controls   blake3:31bd...   --goal    blake3:7e55...
  --er-config  blake3:0c92...   [--costs  blake3:d410...]
  --budget     blake3:5f30...            # step budget object, 69.10
  --seed       0x00000000DEADBEEF
  --mode       both|robust|optimistic
  --out-dir    /var/spectra/cas
  [--emit-instances]                     # required when a checker run will follow
```

69.4.2 Checker invocation.

```
spectra-verify
  --abi 1 --cas-root /cas
  --cert blake3:9f2c...
  [--strict-minimality]                  # forces exhaustive re-check when tractable
  --out-dir /out
```

69.4.3 stdout carries EXACTLY ONE line, terminated by `\n`, and nothing else, ever:

```json
{"abi":1,"status":"ok","outputs":{"cert":"blake3:9f2c…","liveness":"blake3:1b7e…","instances":"blake3:c034…"},"budget_used":{"ground_steps":118743,"relaxations":204118,"bnb_nodes":9042},"flags":["subset_minimal_only"]}
```

    (all numerals above are illustrative, not a target)

69.4.4 The verdict is NEVER carried by the exit code and NEVER parsed out of stderr. UNSAFE is a
successful run: exit 0, `status":"ok"`, and the verdict inside the certificate. Any Python code that
branches on exit code to obtain a verdict is a build failure (69.20.1).

69.4.5 The kernel and checker must run correctly with stdin closed, with `HOME` unset, with an empty
environment except `TZ=UTC`, `LC_ALL=C`, and with a read-only root filesystem apart from `--out-dir`.

------------------------------------------------------------
69.5 SERIALIZATION: PINNED SCHEMA
------------------------------------------------------------

69.5.1 Two codecs only. Canonical JSON for anything a human or the checker must audit; SFB (Spectra
Fact Binary, 69.6) for the fact base and the rule-instance set, which are large and machine-only.

69.5.2 Canonical JSON rules (these are the same rules the certificate section imposes; restated here
because the ABI depends on them):

- UTF-8, no BOM, LF only, object keys sorted by byte value, no insignificant whitespace.
- Integers only. FLOATING POINT IS FORBIDDEN in every ABI payload. A value that is conceptually
  fractional is transported as an integer numerator with a declared fixed denominator.
- No `null`. An absent value is an absent key.
- Strings are NFC-normalized; control characters are `\u00XX` escaped.
- No wall-clock timestamps, no hostnames, no absolute paths, no usernames, no process ids, no
  environment capture anywhere in an ABI payload. Event timestamps from telemetry are data, carried
  as integer nanoseconds since the scenario epoch, and are exempt.

69.5.3 The wire types, authoritative. Rust and Go each carry a hand-written definition; neither is
generated from the other.

```rust
// rust/kernel/src/abi.rs  — ABI 1
#[derive(Serialize)] pub struct ResultPointer {
    pub abi: u16,
    pub status: Status,                    // "ok" | "rejected" | "exhausted"
    pub outputs: BTreeMap<String, ObjId>,  // sorted; kind -> blake3:<hex>
    pub budget_used: BudgetUsed,
    pub flags: Vec<Flag>,                  // sorted, deduplicated
}
#[derive(Serialize)] pub struct BudgetUsed {
    pub ground_steps: u64, pub relaxations: u64,
    pub bnb_nodes: u64, pub corridors: u32,
    pub instances: u32, pub arena_cells: u64,
}
pub struct ObjId([u8;32]);                 // rendered "blake3:" + lowercase hex
```

```go
// go/verify/abi/abi.go — ABI 1, hand-written, imports nothing generated
type ResultPointer struct {
    ABI        uint16            `json:"abi"`
    Status     string            `json:"status"`
    Outputs    map[string]string `json:"outputs"`
    BudgetUsed BudgetUsed        `json:"budget_used"`
    Flags      []string          `json:"flags"`
}
```

69.5.4 A machine-readable schema lives at `abi/v1/*.schema.json` and is hashed into every run
manifest. The gate `make abi-contract` validates: every Rust struct, every Go struct and the JSON
Schema describe the same field set with the same types and the same required-ness. Divergence fails
the build. This schema directory is append-only; editing a file under `abi/v1/` is forbidden, a new
version goes to `abi/v2/`.

------------------------------------------------------------
69.6 SFB: THE BINARY FORM FOR FACT BASES AND INSTANCE SETS
------------------------------------------------------------

69.6.1 JSON is forbidden for the fact base and the rule-instance set. They are transported as SFB, a
fixed-layout, little-endian, length-prefixed format designed so the Go checker can mmap and scan it
in one pass without allocating per record.

```
SFB v1 layout
  offset  size   field
  0       8      magic  "SPECTFB1"
  8       2      abi (u16 LE)
  10      2      section_count (u16 LE)
  12      4      reserved, zero
  16      32     blake3 of everything after byte 48
  48      ...    sections, each: [u8 kind][u8 pad3][u32 count][u64 byte_len][payload]

  section kind 0x01 STRINGS   : concatenated NFC UTF-8, u32 offset table, sorted, deduped
  section kind 0x02 FACTS     : repeat count x { u32 fact_id, u16 pred_id, u64 t_ns,
                                                u32 arg0..arg3 (entity ids, 0xFFFFFFFF = absent) }
  section kind 0x03 INSTANCES : repeat count x { u32 head, u16 rule_id, u8 body_len, u8 flags,
                                                u64 blockers, u32 body[body_len],
                                                u32 ev_len, u64 event_id[ev_len],
                                                u32 license_id (0xFFFFFFFF = observed) }
  section kind 0x04 LICENSES  : repeat count x { u32 license_id, u16 source_id, u64 t0_ns,
                                                u64 t1_ns, u8 basis, u32 witness_len,
                                                u64 witness[witness_len] }
```

69.6.2 Ordering is part of the format. FACTS are sorted by (t_ns, pred_id, arg0..arg3); INSTANCES by
(head, rule_id, body[], license_id); LICENSES by (source_id, t0_ns). Any unsorted or duplicated
record is a hard reject (exit 5). This makes the encoding a canonical function of the logical
content and lets the checker verify by streaming comparison rather than by building a hash set —
which also removes the last place a Go map iteration order could leak into output.

69.6.3 `flags` in INSTANCES: bit0 `silent`, bit1 `obligation_induced`, bit2 `er_ambiguous_input`.
Bit1 exists specifically so the UI can honour the GHOST-provenance rule: an obligation-induced
silent instance cites the observed EventIds that created the obligation, in `ev_len`, while still
being rendered GHOST and still being excluded from every observed-event count.

69.6.4 NEGATIVE: SFB is never stored in a database column, never sent over HTTP, and never
base64-encoded into JSON. The API returns object ids and projections, not fact bases.

------------------------------------------------------------
69.7 VERSION NEGOTIATION
------------------------------------------------------------

69.7.1 `--abi <n>` is MANDATORY on every invocation. There is no default and no auto-detection.

69.7.2 Each binary exposes its supported set:

```
$ spectra-kernel abi
{"binary":"spectra-kernel","abi_supported":[1],"abi_default":null,"build":"blake3:2ab4…","rules_dialect":1}
```

69.7.3 If the requested ABI is not in `abi_supported`, exit 3 immediately, before reading any input
object, with a single diagnostic naming both sets. Never attempt a best-effort parse.

69.7.4 The Python layer caches nothing about the binaries between runs. At worker start it executes
`spectra-kernel abi` and `spectra-verify abi`, records both `build` hashes in the run manifest, and
refuses to serve if either binary's ABI set does not contain the ABI pinned in `spectra.toml`.

69.7.5 ABI versions are integers and are never reused. A new ABI requires: a new `abi/vN/` directory,
new hand-written structs on both sides, and a migration note. Certificates emitted under ABI n are
verifiable forever by a checker that still lists n in `abi_supported`; dropping support for an ABI is
a breaking release and must be recorded in `docs/abi-history.md` alongside every published
certificate hash that becomes unverifiable.

69.7.6 `rules_dialect` is versioned independently of the ABI, because the guard language can change
without the transport changing. The kernel rejects a `rules` object whose declared dialect it does
not implement with exit 6.

------------------------------------------------------------
69.8 EXIT-CODE TAXONOMY
------------------------------------------------------------

OVERRIDES Part I: Part I's CLI sketches implied a conventional 0/1 convention. Replace it with this
closed taxonomy. Both binaries share codes 0-10; the checker adds 20-22. No other code may be
returned; a panic handler converts any unhandled panic into exit 8 after emitting a diagnostic.

| Code | Name                  | Meaning                                                        | Artifact written | CI treats as |
|------|-----------------------|----------------------------------------------------------------|------------------|--------------|
| 0    | OK                    | Ran to completion. Verdict is inside the artifact.             | yes              | pass         |
| 2    | USAGE                 | Malformed argv, missing flag, bad object-id syntax.            | no               | fail         |
| 3    | ABI_UNSUPPORTED       | Requested `--abi` not supported by this binary.                | no               | fail         |
| 4    | INPUT_MISSING         | A referenced object is absent from `--cas-root`.               | no               | fail         |
| 5    | INPUT_CORRUPT         | Hash mismatch, bad magic, decode error, unsorted SFB.          | no               | fail         |
| 6    | INPUT_REJECTED        | Well-formed but semantically refused (unknown rules dialect, `sum(m_k) > 64` with exact mode demanded, goal atom absent from catalog). | no | fail |
| 7    | BUDGET_EXHAUSTED      | A step budget in 69.10 hit zero. Deterministic partial output. | yes, flagged     | see 69.10.5  |
| 8    | INTERNAL_INVARIANT    | The binary caught itself violating an invariant. Fail closed.  | no               | fail         |
| 9    | ENVIRONMENT_VIOLATION | Forbidden syscall or forbidden dependency observed at runtime. | no               | fail         |
| 10   | OUTPUT_WRITE_FAILED   | CAS write, fsync or rename failed.                             | no               | fail         |
| 20   | CERT_REJECTED         | Checker: the certificate is invalid. Reason in diagnostics.    | report written   | fail         |
| 21   | CERT_UNVERIFIABLE     | Checker: inputs needed to verify are absent from the CAS.      | report written   | fail         |
| 22   | CERT_SCOPE_MISSING    | Checker: verdict string lacks its scope binding (see 69.8.2).  | report written   | fail         |

69.8.1 Exit 20 is the checker doing its job. The adversarial certificate corpus expects exit 20 on
every forged certificate; a corpus entry that yields exit 0 fails the build.

69.8.2 The checker must refuse, with exit 22, any certificate whose safety field is not scope-bound
in the form `ROBUST(rules@<hash>,catalog@<hash>,licenses@<hash>,non_adaptive)`. A bare `ROBUST`
string is not a valid ABI value and must be unrepresentable in both the Rust and Go types.

OVERRIDES Part I section 38: `CREATE TYPE verdict_t AS ENUM ('ROBUST','OPTIMISTIC_ONLY','UNSAFE')`,
the `mode` CHECK over the same bare strings, and the `"mode": "ROBUST"` value in Part I section 36's
payload are replaced by the scope-bound safety string stored as `safety text` (69.14.1). An
implementer who builds the enum stores a value the checker rejects with exit 22, and Part I's
`robust_never_flagged` CHECK stops matching any row instead of failing loudly.

------------------------------------------------------------
69.9 STDERR DIAGNOSTIC FORMAT
------------------------------------------------------------

69.9.1 stderr is NDJSON, one object per line, and is BYTE-IDENTICAL across machines for identical
inputs. It is golden-tested (69.20.2). Therefore it contains no wall-clock time, no durations, no
paths, no host identifiers, no addresses, no thread ids, no Rust `Debug` output of a HashMap.

```json
{"abi":1,"lvl":"error","code":"E0512","stage":"ground","step":118743,"msg":"rule instance body references unknown fact","ctx":{"rule_id":37,"fact_id":90211}}
{"abi":1,"lvl":"warn","code":"W0301","stage":"liveness","step":4412,"msg":"source sample below n_min; failing closed to BLIND","ctx":{"source_id":11,"n":7}}
{"abi":1,"lvl":"info","code":"I0100","stage":"cut","step":204118,"msg":"corridor enumerated","ctx":{"corridor_index":6,"popcount":2}}
```

    (all numerals above are illustrative, not a target)

69.9.2 `step` is the deterministic step counter from 69.10, not a timestamp. It is the only ordering
signal in the log.

69.9.3 Codes are stable, documented in `docs/diagnostics.md`, and namespaced: `E` fatal, `W`
non-fatal but recorded, `I` informational. Every `E` code must appear at least once in the
adversarial or red-team fixture corpus; an `E` code with no fixture that produces it is dead code and
fails `make diagnostics-audit`.

69.9.4 Verbosity is controlled by `--log-level {error,warn,info}`, default `warn`. The level changes
which lines are emitted, never their content. Golden tests run at `info`.

69.9.5 NEGATIVE: never print progress bars, spinners, ANSI colour, or elapsed time to stderr. Never
write human prose to stderr that the Python layer then regex-parses; the Python layer consumes only
`code` and `ctx`.

------------------------------------------------------------
69.10 THE TIMEOUT-FREE STEP-BUDGET CONTRACT
------------------------------------------------------------

OVERRIDES Part I: ECLIPSE §6 and §4B permitted "caps" and the feasibility critic proposed "a solver
time budget." WALL-CLOCK TIMEOUTS ARE NOW FORBIDDEN IN EVERY DECISION PATH of the kernel and the
checker. A wall-clock bound makes flags, and therefore verdicts, machine-dependent, which destroys
byte-identical replay. Replace every timeout with a deterministic step budget.

69.10.1 Budget object, a CAS-stored TOML compiled to a struct and hashed into the run manifest:

```toml
# budgets/default.toml   — every value is a hard design constraint, not a measurement
abi            = 1
ground_steps   = 20_000_000    # semi-naive derivation attempts
relaxations    = 50_000_000    # Dowling-Gallier counter decrements
bnb_nodes      = 2_000_000     # branch-and-bound nodes over u64 masks
corridors      = 4_096         # enumerated corridors before capping
instances      = 1_000_000     # rule instances materialized
arena_cells    = 268_435_456   # 8-byte cells; the memory ceiling, counted not measured
checker_steps  = 200_000_000   # checker's own single budget
```

OVERRIDES Part I section 34: the atom limit, B&B node budget, corridor cap and grounding caps held
in `config/defaults/eclipse.toml` and `config/defaults/recon.toml` under `config/schema/`
validation, with level-6 environment overrides such as `SPECTRA__ECLIPSE__CORRIDOR_CAP`, are
replaced by this single CAS-stored budget object, passed as `--budget blake3:<hex>` and hashed into
the run manifest; the binaries may not read these values from the environment at all (69.21.3). An
implementer who wires the environment override that Part I's precedence transcript requires can
change a corridor cap without changing the run manifest hash, which is exactly the hidden
nondeterminism this contract exists to prevent.

69.10.2 Every counter is decremented at a single, documented call site. Exhaustion is checked with
`if budget.ground_steps == 0 { return Exhausted(Stage::Ground) }` — never by sampling, never by a
background thread, never by signal.

69.10.3 The memory ceiling is `arena_cells`, an allocation counter inside a bump arena, NOT resident
set size. RSS depends on allocator, kernel and machine; a ceiling expressed in RSS would reintroduce
machine dependence. Any allocation outside the arena in the kernel's decision path is a build
failure (clippy lint plus `#[global_allocator]` accounting test).

69.10.4 Exhaustion is deterministic and produces output, not an abort:

```
fn run_stage(b: &mut Budget) -> Outcome {
    loop {
        if b.ground_steps == 0 {
            flags.insert(Flag::GroundingCapped);          // structurally suppresses ROBUST
            emit_partial_artifact(flags);                 // exit 7, artifact written
            return Outcome::Exhausted;
        }
        b.ground_steps -= 1;
        ...
    }
}
```

69.10.5 Exit 7 is a PASS for the API (the user gets a flagged, honest, degraded result) and a FAIL
for CI on any fixture in the core suite. `make gates` fails if any core fixture exits 7 under
`budgets/default.toml`, because that means the declared budget no longer fits the declared scale.
Nightly publishes the observed budget_used distribution so the budget can be revised deliberately,
in a commit, with a rationale — never silently.

OVERRIDES Part I section 36: the error code `GROUNDING_CAP_EXCEEDED` at HTTP 507, and Part I section
35's classification of `CapExceeded` as a terminal error, are replaced by a successful API response
carrying the flagged, degraded artifact. An implementer following Part I returns an error envelope
and discards the deterministic partial certificate that the flag and verdict machinery depends on.

69.10.6 A flagged run may never be presented as ROBUST. That rule is enforced in the type system:
the safety field is constructible only from a flag set proven empty; see the verdict-algebra section
of Part II.

69.10.7 NEGATIVE: the Python layer may impose a wall-clock guard on the SUBPROCESS as an operational
safety net (SIGKILL after a generous bound). If it fires, the run is recorded as
`INFRA_KILLED`, produces NO certificate, and is excluded from every published number. It is an
operational event, never an input to a verdict, and it must never be confused with exit 7.

------------------------------------------------------------
69.11 FAILURE MODES, ENUMERATED
------------------------------------------------------------

| # | Failure                                    | Detection                            | Response                                        |
|---|--------------------------------------------|--------------------------------------|--------------------------------------------------|
| 1 | Binary missing or not executable           | worker startup probe (69.7.4)        | worker refuses to start; API returns 503         |
| 2 | ABI mismatch                               | exit 3                               | job fails fast; no retry; operator alert          |
| 3 | Object absent from CAS                     | exit 4                               | job fails; Python re-resolves inputs once, then gives up |
| 4 | Object present but hash mismatch           | exit 5                               | quarantine the object id, fail the job, fail CI   |
| 5 | Kernel killed by OOM killer                | exit signal, no stdout line          | `INFRA_KILLED`; excluded from results; arena ceiling reviewed |
| 6 | Kernel writes stdout but exits nonzero     | contradictory state                  | treat as exit 8; this is a kernel bug; fail build |
| 7 | Partial CAS write (crash mid-write)        | object only in `tmp/`                | GC sweeps `tmp/`; no partial object is ever visible |
| 8 | Two runs race on the same object id        | rename is idempotent                 | benign; bytes are identical by construction       |
| 9 | Checker rejects a kernel-emitted cert      | exit 20                              | HARD FAIL. Never retried, never ignored, never downgraded to a warning. Publishes the certificate and the rejection report into the adversarial corpus as a regression fixture. |
|10 | stderr diverges from golden bytes          | `make abi-golden`                    | fail build; nondeterminism has entered the kernel |
|11 | Budget exhausted on a core fixture         | exit 7                               | fail CI (69.10.5)                                 |
|12 | Network syscall attempted by either binary | seccomp audit (69.20.3)              | exit 9 at runtime; fail build in CI               |

69.11.1 There is no retry policy for the kernel. The kernel is deterministic: a retry with identical
inputs produces identical output, so retrying can only mask an infrastructure fault. Python retries
ONLY on failure modes 1 and 5, at most once, and records the retry in the run manifest.

OVERRIDES Part I section 35: the retry policy of three attempts with exponential backoff and jitter
for `TransientError`, together with the `retrying` job state and the `attempts` CHECK of Part I
section 38, is replaced by at most one retry confined to failure modes 1 and 5. An implementer who
keeps Part I's policy masks the infrastructure faults this section exists to surface and builds a
job state that the `run.status` CHECK in 69.14.1 does not admit.

------------------------------------------------------------
69.12 THE PYTHON CLIENT
------------------------------------------------------------

69.12.1 Exactly one module, `services/kernel_client.py`, may spawn either binary. A lint fails the
build if `subprocess`, `asyncio.create_subprocess_exec` or `os.exec*` appears anywhere else in the
Python tree.

OVERRIDES Part I section 35: the kernel call placed in the pure engine layer as
`engines/eclipse_bridge.py`, reaching the Rust kernel in-process via pyo3 under the engine-purity
import contract, is replaced by a single spawning module `services/kernel_client.py` that runs the
binary as a subprocess. An implementer who keeps the engine-layer bridge fails
`make one-spawner-lint` and builds the pyo3 extension module 69.1.2 forbids.

```python
def prove(inputs: ProveInputs, budget: ObjId, seed: int) -> ResultPointer:
    argv = [KERNEL, "prove", "--abi", str(ABI), "--cas-root", str(CAS_ROOT),
            "--bundle", inputs.bundle, "--rules", inputs.rules,
            "--controls", inputs.controls, "--goal", inputs.goal,
            "--er-config", inputs.er_config, "--budget", budget,
            "--seed", f"0x{seed:016X}", "--mode", "both",
            "--out-dir", str(CAS_ROOT), "--emit-instances"]
    p = run(argv, stdin=DEVNULL, capture_output=True,
            env={"TZ": "UTC", "LC_ALL": "C"}, cwd="/")   # empty env otherwise
    diags = [json.loads(l) for l in p.stderr.splitlines() if l]
    if p.returncode in (0, 7):
        rp = ResultPointer.model_validate_json(p.stdout.rstrip(b"\n"))
        if rp.abi != ABI: raise AbiDrift(rp.abi)
        return rp
    raise KernelError(code=p.returncode, diagnostics=diags)   # no parsing of msg text
```

69.12.2 The client never constructs a verdict, never infers one, and never reads the certificate to
decide job status. It stores the object ids and lets the projection layer (69.14) read the
certificate.

69.12.3 Every PROVE job runs the checker immediately after the kernel, in-process-sequentially,
before the result is marked complete. A certificate that has not been accepted by
`spectra-verify` is never exposed by the API and never rendered by the frontend.

------------------------------------------------------------
69.13 THE PERSISTENCE BOUNDARY: THE THREE RULES
------------------------------------------------------------

OVERRIDES Part I: Part I named PostgreSQL, Redis and the fact base but drew no boundary. The
completeness critic predicted the fact base would be materialized in PostgreSQL, destroying both
determinism and performance. These three rules are now normative and override any contrary
implication elsewhere.

RULE P1 — TRUTH LIVES ON DISK. Every object in 69.3.3 is the authoritative record. PostgreSQL holds
only an index, metadata, the entity catalog, and API-facing projections. Every PostgreSQL row is
derivable from the CAS. `make rebuild-projections` drops every projection table and rebuilds it from
the CAS alone; the resulting `pg_dump --data-only` must be byte-identical to the dump taken before
the rebuild. If it is not, a projection has acquired state that is not in the CAS, and the build
fails.

OVERRIDES Part I section 38: `proof_cert.document JSONB`, the full certificate body held in
PostgreSQL alongside `cut_atoms`, `corridor_count`, `instance_count` and `silent_count`, is replaced
by the CAS `cert` object plus the derived `proj_cert_summary` and `proj_cut_atom` projections; a
certificate body carries the invariant set, which 69.21.5 forbids in a JSON column. An implementer
who builds the Part I table puts the invariant set into PostgreSQL and fails `make schema-lint` and
`make rebuild-projections`.

RULE P2 — THE FACT BASE IS NEVER MATERIALIZED IN POSTGRESQL. No table may contain facts, rule
instances, hypergraph nodes, hypergraph edges, corridors, invariant sets, or licenses as rows. The
fact base exists in the kernel's arena during a run and as one SFB object afterwards. It is read by
sequential scan, not by query. A migration that creates a table whose name or columns match the
banned vocabulary fails `make schema-lint`. The state graph the UI renders is a projection of a
BOUNDED SLICE (one hypothesis, one corridor set), not a materialization of the fact base.

RULE P3 — THE KERNEL AND THE CHECKER NEVER TOUCH A DATABASE OR A SERVICE. Neither binary may link,
import, vendor or dynamically load a database client, an HTTP client, a DNS resolver, a message-queue
client, or a telemetry/metrics exporter. Enforced in the build graph, not by policy text (69.20.4).
This rule is what makes third-party offline verification possible; it is not negotiable for
performance, convenience, observability, or caching.

------------------------------------------------------------
69.14 WHAT LIVES IN POSTGRESQL
------------------------------------------------------------

69.14.1 Four families only: run index, run metadata, entity catalog, API-facing projections.

OVERRIDES Part I section 35: the durable `job` and `idempotency_key` tables — the latter storing
`fingerprint`, `state`, `response_status`, `response_body_hash` and `job_id` so a replay can return
the stored response and a fingerprint mismatch can return `409 IDEMPOTENCY_KEY_REUSE` — are
replaced by the run index plus the ephemeral Redis keys in 69.15.1; neither table is one of the four
permitted families. An implementer who ships the Part I DDL adds a fifth family that
`make schema-lint` rejects, while the Redis key that replaces it holds only key -> run_id, so Part
I's fingerprint comparison and stored-response replay have no backing store.

```sql
-- RUN INDEX AND METADATA -------------------------------------------------
CREATE TABLE run (
  run_id         uuid PRIMARY KEY,           -- generated by the Python layer
  manifest_obj   char(71) NOT NULL UNIQUE,   -- 'blake3:' + 64 hex
  scenario       text NOT NULL,
  seed           bigint NOT NULL,
  git_sha        char(40) NOT NULL,
  abi            smallint NOT NULL,
  kernel_build   char(71) NOT NULL,
  checker_build  char(71) NOT NULL,
  status         text NOT NULL CHECK (status IN
                   ('queued','running','complete','failed','infra_killed')),
  exit_code      smallint,
  held_out       boolean NOT NULL,           -- section 62 protocol
  pinned         boolean NOT NULL DEFAULT false,  -- GC root, 69.18
  created_at     timestamptz NOT NULL DEFAULT now()   -- metadata only; never hashed
);
CREATE TABLE run_input (                    -- one row per hashed input
  run_id uuid REFERENCES run, kind text, obj char(71),
  PRIMARY KEY (run_id, kind));
CREATE TABLE run_artifact (                 -- the CAS index
  obj char(71) PRIMARY KEY, kind text NOT NULL, codec text NOT NULL,
  bytes bigint NOT NULL, produced_by uuid REFERENCES run);

-- ENTITY CATALOG ---------------------------------------------------------
CREATE TABLE entity (
  entity_id bigint PRIMARY KEY, kind text NOT NULL, canonical_label text NOT NULL,
  er_config char(71) NOT NULL, ambiguous boolean NOT NULL);
CREATE TABLE entity_alias (
  entity_id bigint REFERENCES entity, alias text, source_id int,
  PRIMARY KEY (entity_id, alias, source_id));

-- API-FACING PROJECTIONS (derived; rebuildable; never authoritative) ------
CREATE TABLE proj_cert_summary (
  cert_obj char(71) PRIMARY KEY, run_id uuid REFERENCES run,
  safety text NOT NULL,                     -- scope-bound string, 69.8.2
  minimality text NOT NULL CHECK (minimality IN ('EXACT','SUBSET','UNVERIFIED')),
  flags text[] NOT NULL, cut_size int NOT NULL,
  checker_accepted boolean NOT NULL);
CREATE TABLE proj_cut_atom (
  cert_obj char(71) REFERENCES proj_cert_summary, control text, level int,
  in_every_min_cut boolean, blindness_premium boolean,
  PRIMARY KEY (cert_obj, control, level));
CREATE TABLE proj_quarantine (
  run_id uuid REFERENCES run, record_index bigint, reason_code text,
  PRIMARY KEY (run_id, record_index));
```

OVERRIDES Part I section 38: hash columns declared `BYTEA` with an octet-length CHECK, and the
negative requirement forbidding `TEXT` for a hash, are replaced by `char(71)` columns holding
`'blake3:' + 64 lowercase hex`. An implementer who builds the Part I columns produces keys that
neither join to nor match those of `run_artifact` and `proj_cert_summary`, and
`make rebuild-projections` compares dumps of two different column types.

OVERRIDES Part I section 38: the ULID-like prefixed `TEXT` public identifiers (`cert_`, `jb_`,
`rp_`, `bn_`, `ev_`, `en_`) used as primary keys, including `proof_cert.cert_id` and `job.job_id`,
are replaced by `run_id uuid` for runs and the `blake3:` object id for certificates and artifacts.
An implementer who keys the certificate table on `cert_id TEXT` has no column by which Part I
section 36's `/api/v1/eclipse/proofs/{cert_id}` route can reach `proj_cert_summary`.

OVERRIDES Part I section 38: the entity catalog's `entity_uid`, `canonical_name`, `first_seen`,
`last_seen` and `attrs` columns, and `entity_alias`'s `alias_kind`, `merge_rule`, `evidence_uids`
and `(alias_kind, alias)` uniqueness, are replaced by the two tables above, with aliases keyed
`(entity_id, alias, source_id)`. An implementer who builds the Part I catalog gets key columns that
do not match this schema, and the merge evidence Part I section 36's `GET /entities/{id}/aliases`
returns has no column here to come from.

69.14.2 Projection tables are prefixed `proj_` without exception. `make schema-lint` asserts: every
`proj_` table is written only by the projection builder; no `proj_` table is read by the kernel,
the checker, the generator, or the bench harness; no non-`proj_` table is written by the projection
builder.

69.14.3 NEGATIVE, enforced by `make schema-lint` as a banned-identifier list on table and column
names: `fact`, `facts`, `rule_instance`, `instances`, `hyperedge`, `hypergraph_node`, `corridor`,
`license`, `invariant`, `factbase`, `atom`, `blocker`. Any migration introducing one fails the
build. If a projection genuinely needs to expose a bounded slice of one of these, it is named
`proj_<thing>_slice` and carries a hard row cap enforced by a CHECK constraint plus a trigger.

69.14.4 NEGATIVE: no numeric confidence, probability, score or severity column may exist anywhere in
the schema. `make schema-lint` bans the column-name substrings `score`, `confidence`, `probability`,
`severity`, `risk`, `likelihood`.

------------------------------------------------------------
69.15 WHAT REDIS MAY HOLD
------------------------------------------------------------

69.15.1 Ephemeral job state ONLY. Redis is configured with no persistence: `save ""`,
`appendonly no`. If Redis is wiped mid-operation, the system must lose in-flight progress and
nothing else.

| Key pattern                | Type | TTL      | Contents                                      |
|----------------------------|------|----------|-----------------------------------------------|
| `arq:queue:prove`          | list | none     | arq job envelopes (object ids + run_id only)  |
| `spectra:job:<run_id>`     | hash | 24h      | `stage`, `pct`, `last_diag_code`              |
| `spectra:lock:gc`          | str  | 1h       | GC mutex                                      |
| `spectra:idem:<key>`       | str  | 24h      | idempotency key -> run_id                     |
| `spectra:sse:<run_id>`     | pubsub| n/a     | progress frames for the PROVE stream          |

OVERRIDES Part I section 35: the six Redis Streams with consumer groups, per-queue `maxlen~`,
explicit `XACK` and an untrimmed dead-letter stream `spectra:dlq`, together with the admission
control that computes `XLEN(stream)` against a soft limit and returns `429 QUEUE_SATURATED`, are
replaced by the closed key set above, whose only queue is the arq list `arq:queue:prove`. An
implementer following Part I creates keys this table does not permit and a dead-letter stream that
contradicts `save ""` / `appendonly no`, and a depth check by `XLEN` has no meaning against a list.

69.15.2 NEGATIVE: Redis never holds a certificate, a verdict, a cut, a fact, an instance, a license,
an event, an entity, or any bytes from the CAS. A value larger than 4 KiB (a hard design constraint,
not a measurement) is a bug; a runtime assertion rejects it.

69.15.3 `make redis-chaos` runs the core scenario, issues `FLUSHALL` at a seeded point mid-run, and
asserts: (a) the run either completes or reports `failed`, (b) no certificate is lost or altered,
(c) re-running the same request reproduces the byte-identical certificate hash. Failure fails the
build.

------------------------------------------------------------
69.16 SIZING
------------------------------------------------------------

69.16.1 The numbers in this subsection are ILLUSTRATIVE ARITHMETIC used to size disks and to justify
the boundary. They are not targets, not measurements, and must never be copied into README, docs, or
the UI. `make sizing-report` computes the real figures from a run and writes them to a bench
artifact; only those figures may be published.

| Object per run       | Illustrative size (illustrative, not a target) | Basis                          |
|----------------------|-----------------------------------------------|--------------------------------|
| `bundle` (zstd)      | ~12 MB                                         | 200k records x ~400 B, ~6:1    |
| `factbase` (SFB)     | ~9 MB                                          | 250k facts x 36 B              |
| `instances` (SFB)    | ~4 MB                                          | 60k instances x ~70 B          |
| `liveness`           | ~200 KB                                        | per-source intervals           |
| `cert`               | ~1.5 MB                                        | invariant set dominates        |
| `run_manifest`       | ~8 KB                                          | hashes and versions            |
| TOTAL per run        | ~27 MB                                         | sum of the above               |

69.16.2 Matrix arithmetic, same caveat: a degradation sweep of 8 completeness levels x 6 operators x
10 scenarios x 3 seeds = 1,440 runs; at ~27 MB that is ~39 GB per full sweep (illustrative, not a
target). This is precisely why the fact base must not be in PostgreSQL and why 69.18 exists. A
PostgreSQL row-per-fact materialization of the same sweep would be on the order of 360 million rows
plus indexes (illustrative, not a target) and would make `make reproduce` impossible on a laptop.

69.16.3 PostgreSQL's own footprint is bounded by design: the run index and projections are O(runs)
and O(cut atoms), not O(facts). A full sweep adds on the order of 10^4 rows (illustrative, not a
target).

69.16.4 Declared ceilings (hard design constraints, enforced, not illustrative): a single bundle
object may not exceed 2 GiB; a single SFB section may not exceed 2^32 - 1 records; `arena_cells` in
69.10.1 is the memory ceiling; the CAS root has a configured `max_bytes` and the ingest path refuses
new runs at 90% occupancy with a clear error rather than failing mid-run.

------------------------------------------------------------
69.17 RETENTION CLASSES
------------------------------------------------------------

| Class       | Applies to                                                      | Retention                    |
|-------------|-----------------------------------------------------------------|------------------------------|
| PERMANENT   | Inputs and certificates of any run referenced by `docs/claims.md`, by a published figure, by the pre-registration, or by the demo fixture | forever; GC may never remove |
| PINNED      | Runs with `run.pinned = true` (operator or held-out protocol)   | forever until unpinned       |
| REGRESSION  | Adversarial and red-team corpus entries, plus any certificate a checker ever rejected | forever                      |
| MATRIX      | Degradation-sweep runs not otherwise referenced                 | last 3 sweeps, then collect  |
| SCRATCH     | Developer runs, `make demo` re-runs, failed runs                | 14 days                      |
| TMP         | `cas/tmp/` staging files                                        | swept every GC pass          |

OVERRIDES Part I section 34: run-artifact lifetime declared in `config/policies/retention.yaml` as
schema-validated data under `config/` is replaced by these six retention classes, which are
normative in this section and have no config file. An implementer who writes the retention policy as
config data gives the GC a second, editable source of truth for what may be collected.

OVERRIDES Part I section 32: the claim file whose references pin the PERMANENT class is
`docs/claims.md`, not the repository-root `CLAIMS.md`. An implementer who keeps Part I's file name
gets a GC whose PERMANENT root set is empty, and the sweep then collects claim-referenced
certificates.

69.17.1 A MATRIX run's `bundle`, `factbase` and `instances` objects may be collected while its
`run_manifest`, `liveness` and `cert` are retained, because the first three are regenerable from
(seed, scenario, degradation spec, rules) by a deterministic generator and the last three are the
evidence. Collection of a regenerable object records `regenerable_from` in `run_artifact` so a later
`make reproduce` knows how to rebuild it rather than reporting data loss.

69.17.2 NEGATIVE: a certificate is never collected while any row in `proj_cert_summary` references
it, and never collected at all if a checker ever rejected it.

------------------------------------------------------------
69.18 GARBAGE COLLECTION
------------------------------------------------------------

69.18.1 GC is mark-and-sweep over the CAS, single-threaded, deterministic in its traversal order
(objects visited in lexicographic id order), and holds `spectra:lock:gc` for its duration.

```
spectra-gc:
  1. acquire lock; refuse to run if any run.status in ('queued','running')
  2. roots := PERMANENT ∪ PINNED ∪ REGRESSION ∪ (MATRIX ∩ last 3 sweeps)
             ∪ every obj named in docs/claims.md, preregistration.md, demo fixture
  3. mark := transitive closure of roots through run_input and run_manifest references
  4. for obj in sort(all objects):
        if obj in mark: continue
        if class(obj) = TMP and age > 1 pass: unlink
        if class(obj) = SCRATCH and age > 14 days: unlink
        if class(obj) = MATRIX and regenerable(obj): unlink, set regenerable_from
        else: keep
  5. sweep cas/tmp/ unconditionally
  6. emit a GC report object into the CAS (itself PERMANENT): counts, bytes, ids removed
```

69.18.2 `--dry-run` is the default. Actual deletion requires `--commit`. Nightly CI runs
`spectra-gc --dry-run` and fails if the plan would remove any PERMANENT, PINNED or REGRESSION object
— a mark-phase bug must be caught by the gate, never discovered by data loss.

69.18.3 `make gc-safety` builds a synthetic CAS with a known root set, runs the GC, and asserts the
surviving set equals the expected set exactly. It also asserts the GC is idempotent: a second pass
removes nothing.

69.18.4 NEGATIVE: the GC never deletes a PostgreSQL row. Orphaned projection rows (referencing a
collected object) are ALLOWED and are rendered by the API as `artifact_collected`, with the
regeneration command. Deleting run history to make the index tidy destroys the audit trail.

------------------------------------------------------------
69.19 MIGRATION POLICY
------------------------------------------------------------

69.19.1 PostgreSQL migrations are forward-only, numbered, checked in, and applied by one tool.
Because every `proj_` table is derivable, a projection migration is always: drop, recreate, rebuild
from CAS. Never write a data-backfill migration for a `proj_` table.

OVERRIDES Part I section 38: the requirement that every migration implement a real `downgrade()`,
with CI running `upgrade head -> downgrade base -> upgrade head` on an empty and on a seeded
database, is replaced by a forward-only migration set. An implementer who keeps Part I's gate must
author downgrades for migrations this section declares irreversible, and the two CI gates cannot
both pass.

69.19.2 Migrations may not alter CAS objects. There is no such thing as migrating a certificate. An
old certificate is verified by a checker that still supports its ABI, or it is marked unverifiable in
`docs/abi-history.md`. Rewriting a stored certificate to a new schema is forbidden; it would break
its hash and its meaning.

69.19.3 A migration that would require reading the CAS to fill a non-`proj_` table is a design error:
the data belongs in a projection.

------------------------------------------------------------
69.20 GATES
------------------------------------------------------------

| Gate                       | Proves                                                                 |
|----------------------------|------------------------------------------------------------------------|
| `make abi-contract`        | Rust structs, Go structs and `abi/v1/*.schema.json` agree field-for-field; `abi/v1/` unmodified since its introducing commit |
| `make abi-golden`          | For each core fixture: stdout line, stderr NDJSON, and every output object id are byte-identical to committed goldens, on both CI runners |
| `make abi-exitcodes`       | Every code in 69.8 is produced by at least one fixture; no fixture produces a code outside the taxonomy; no fixture returns 1 |
| `make kernel-offline-audit`| Kernel and checker run to completion under `--network none --read-only` with an empty environment; a seccomp audit shows zero socket/connect/getaddrinfo calls |
| `make no-service-deps`     | Build-graph lint: `cargo tree` for the kernel and `go list -deps` for the checker contain no database, HTTP, DNS, queue or telemetry client; the checker's non-stdlib dependency set is empty apart from the pinned BLAKE3 implementation |
| `make one-spawner-lint`    | `subprocess`/`exec` appears in Python only inside `services/kernel_client.py` |
| `make schema-lint`         | Banned table/column identifiers absent (69.14.3, 69.14.4); `proj_` read/write discipline holds |
| `make rebuild-projections` | Projection rebuild from CAS reproduces a byte-identical data dump |
| `make redis-chaos`         | FLUSHALL mid-run loses no result and changes no certificate hash |
| `make gc-safety`           | GC mark set exact on a synthetic store; GC idempotent; dry-run plan touches no protected class |
| `make sizing-report`       | Real sizes measured and written to a bench artifact; `docs/` numerals traceable to it |
| `make verify-airgap`       | The published `spectra-verify` image verifies a published certificate from a read-only CAS with no services, on a machine that has never built this repository |

69.20.1 `make abi-exitcodes` additionally greps the Python tree for verdict inference from exit codes
(`returncode == 0` adjacent to `ROBUST`, `UNSAFE`, `safety`) and fails on a match.

69.20.2 `make abi-golden` runs on two distinct CI runners with different CPU models and different
base OS images. Divergence in any byte is a determinism defect and blocks the milestone.

69.20.3 The seccomp audit is a real audit, not policy text: the binaries run under a seccomp profile
that logs and denies the network syscall set, and the test asserts the deny counter is zero AND that
the run still exits 0. A binary that needs the network would exit 9.

69.20.4 `make no-service-deps` is the enforcement mechanism for RULE P3. A prose statement that the
checker is independent is worth nothing; a dependency lint in the build graph is worth something.

------------------------------------------------------------
69.21 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS
------------------------------------------------------------

69.21.1 Do not build a kernel daemon, a gRPC service, a warm worker pool, a shared-memory ring, or a
persistent kernel session. Every PROVE is a fresh process.

69.21.2 Do not add pyo3, cffi, ctypes bindings, cgo, or a dynamic library boundary between Python and
either binary.

69.21.3 Do not let the kernel or the checker read configuration from environment variables other than
`TZ` and `LC_ALL`, from `$HOME`, from a dotfile, from `/etc`, or from any path not given on argv.
Hidden configuration is hidden nondeterminism.

69.21.4 Do not put a wall-clock timeout, deadline, `Instant::now()`, `time.Now()`, or elapsed-time
measurement anywhere that can influence a flag, a cut, a verdict, a corridor set, or the contents of
stderr. Timing may be measured only by the bench harness, from outside the process, and only into
bench artifacts.

69.21.5 Do not store facts, instances, licenses, corridors or invariant sets in PostgreSQL, in Redis,
in a JSON column, in a materialized view, or in a "cache table."

69.21.6 Do not treat Redis as a source of truth, do not enable Redis persistence, do not recover a
run from Redis state.

69.21.7 Do not delete a rejected certificate, a red-team fixture, or a claim-referenced artifact, by
GC or by hand.

69.21.8 Do not write to stdout from either binary other than the single result-pointer line.

69.21.9 Forbidden claims. Never state or imply any of the following in README, docs, UI, commit
messages, paper text or demo narration:

- "The checker independently re-derives everything." State exactly what it re-derives, per the
  checker-scope document; the ABI guarantees only that it received the hashed inputs and the
  published instance set.
- "Verification requires no trust." It requires trusting the BLAKE3 implementation, the two
  compilers, and the rule table; say so.
- "The system is stateless." It is file-stateful by design; the CAS is the state.
- "Results are stored in the database." They are stored on disk; the database indexes them.
- "Byte-identical replay is guaranteed on any machine." The gate covers the two declared CI runner
  configurations and the pinned container image; say that.
- Any sizing, throughput, latency or row-count figure taken from 69.16. Those numbers are
  illustrative arithmetic and are traceable to nothing. Only `make sizing-report` output may be
  published, and only with its run manifest hash attached.
