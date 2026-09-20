============================================================
59. INGESTION, PARSING AND SOURCE ADAPTERS
============================================================

OVERRIDES Part I: telemetry ingestion now has an owning section. Part I (sections 9-12, 26-29) treated `bundle.jsonl` as a pre-existing input and never said who produces it, what parses the raw bytes, or what happens to a record that fails to parse. This section owns the boundary from raw source bytes to `bundle.jsonl`, and it is the only component permitted to create a `CanonicalEvent`.

Read this section as a security boundary, not a data-plumbing chore. Telemetry is untrusted input. A parser defect here does not merely corrupt a report: it changes which windows ECLIPSE believes are blind, which changes which silent instances are licensed, which changes the verdict. Ingestion is therefore inside the proof's trusted computing base and is treated as such.

------------------------------------------------------------
59.1 THE LICENSE-MANUFACTURING HAZARD (why this section exists)
------------------------------------------------------------

Implement ingestion under the following two-sided failure analysis. Both directions must be stated in `docs/ingest/hazard.md` and both must have a test.

1. **Silent drop widens a gap.** A record is discarded without a trace. The inter-arrival gap for that source lengthens. ECLIPSE's liveness pass (ECLIPSE §4A) judges the window BLIND, issues a `License`, and admits silent rule instances inside it. The parser bug has fabricated evidence of absence. Downstream: `S_rob` grows, the blindness premium (`S_rob \ S_opt`) is inflated, and the decisive observation set names a source that was never actually blind. The headline research finding becomes an artifact of a parser bug.

2. **Silent drop inside a busy window.** A record is discarded and the surrounding traffic still brackets the interval, so the source is judged LIVE, no license is issued, and the attack step that the lost record witnessed is neither observed nor admitted. ECLIPSE can then emit ROBUST for a chain it structurally cannot see. This is a **false ROBUST caused by a parser**, and no gate elsewhere in the system can detect it.

Therefore: **a malformed, oversized, unparseable, or policy-violating record is QUARANTINED with a machine-readable reason code and counted. It is never dropped, never truncated, never "best-effort repaired", and never skipped with a log line.** A quarantined record is a recorded, located, hashed absence — which liveness can reason about — rather than an unrecorded absence, which liveness cannot.

------------------------------------------------------------
59.2 PIPELINE POSITION AND BYTE CONSERVATION
------------------------------------------------------------

```
 raw source files (read-only, mounted)
        |
        v
 [1] BUNDLE UNPACKER        -- container formats, decompression limits
        |    \
        |     +--> quarantine (container-level codes Q022..Q026)
        v
 [2] FRAMER (per adapter)   -- bytes -> Frames with exact byte spans
        |    \
        |     +--> quarantine (framing codes Q001, Q042)
        v
 [3] ADAPTER::parse         -- pure function, no clock/fs/net/RNG
        |    \
        |     +--> quarantine (syntax/schema/charset codes)
        v
 [4] NORMALIZER             -- charset, clock, canonical attrs, EventId
        |    \
        |     +--> quarantine (timestamp/number codes)
        v
 [5] DEDUP + TOTAL ORDER    -- content-addressed idempotency
        |
        v
 bundle.jsonl + bundle.manifest.json + quarantine.jsonl + quarantine-report.json
        |
        v
 entity resolution -> fact base -> ECLIPSE kernel
```

**BYTE CONSERVATION LAW.** For every input file, the byte ranges of accepted frames, quarantined frames, and declared skip regions (file headers, CSV header line, trailing newline) must form a partition of `[0, file_len)`: pairwise disjoint, covering, with no gaps. Implement `spectra ingest --audit-bytes`, which recomputes the partition and fails non-zero on any uncovered or double-covered byte. This makes a silent drop structurally impossible rather than merely forbidden, and it is the gate `gate-byte-conservation`. A byte that is neither accepted, quarantined, nor explicitly declared skippable is a build failure.

------------------------------------------------------------
59.3 SOURCE CLASSES AND THE CHAIN-OF-CUSTODY HONESTY CLAUSE
------------------------------------------------------------

OVERRIDES Part I sections 26-29: the hash chain is no longer a universal property of SPECTRA telemetry.

Every source is declared in the source manifest with exactly one `source_class`:

| source_class | seq | hash chain | bracketing guarantee | role |
|---|---|---|---|---|
| `chained` | required, dense | required (BLAKE3) | yes | models sources with real chain-of-custody (signed audit pipelines) |
| `sequenced` | required, dense | none | yes | models sources with a monotonic counter but no integrity chain |
| `unchained` | absent | none | none | models the common real case: rotating text logs, syslog over UDP |
| `derived` | absent | none | n/a | produced by SPECTRA itself; never counts as evidence of liveness |

At least one `unchained` source class must be present in every scenario family, and results must be reported **split by source class**. `docs/ingest/chain-of-custody.md` must state plainly which real-world source types have sequence and chain guarantees and which do not, and must state that suppression detection on `chained` sources is a laboratory affordance rather than a general result. A repo that demonstrates deletion localization only on hash-chained logs and presents it as a result about suppressed telemetry is padding; the gate `gate-source-class-coverage` fails if any degradation-matrix cell was executed with `unchained` sources absent.

------------------------------------------------------------
59.4 CANONICAL EVENT SCHEMA (v1)
------------------------------------------------------------

OVERRIDES Part I sections 17-19: the timestamp type is fixed here, at the adapter edge, for the whole system.

```rust
// crate: spectra-ingest-core
#[derive(Serialize)]           // canonical JSON: keys emitted in this declared order
pub struct CanonicalEvent {
    pub schema_version: u16,          // 1; unknown => Q041, never best-effort
    pub event_id: EventId,            // 64 lowercase hex chars, BLAKE3-256, see 59.10
    pub source_id: SourceId,          // from the manifest, never from the record
    pub source_class: SourceClass,
    pub seq: Option<u64>,             // None iff source_class in {unchained, derived}
    pub chain_prev: Option<Hash32>,   // Some iff source_class == chained
    pub chain_self: Option<Hash32>,
    pub t_utc_ns: i64,                // nanoseconds since UNIX epoch, UTC, no leap smearing
    pub t_resolution_ns: u32,         // declared precision of the SOURCE, not of the parse
    pub t_basis: TimeBasis,           // SourceUtc | SourceOffset | MappedTz | AssumedTz
    pub t_source_raw: String,         // verbatim timestamp text as it appeared
    pub dim: Dimension,               // closed enum, section 13-16
    pub action: ActionId,             // closed enum; unknown action => Q011, never "other"
    pub actor_raw: RawRef,            // pre-entity-resolution identifier strings
    pub target_raw: RawRef,
    pub attrs: CanonicalMap,          // sorted keys, values: I64 | Str | Bool | HexBytes
    pub raw: RawProvenance,           // { file_id, byte_start, byte_len, raw_b3 }
    pub format: FormatRef,            // { format_id, format_version, adapter_b3 }
}
```

Negative requirements on the schema:
- `attrs` may not contain a floating-point value. A source number that is not exactly representable as `i64` is quarantined `Q034`, never rounded. There is no `f64` anywhere in the ingest crate; `gate-no-float-ingest` greps the crate for `f32`/`f64` and fails on a hit.
- There is no `other`, `unknown`, `misc`, or free-text escape hatch in `dim` or `action`. An unrecognized action is a quarantine, because an unmodeled action silently reclassified as `other` is an invisible hole in the rule table.
- `source_id` is taken from the manifest entry that the bytes came from, never from a field inside the record. A record claiming to be from another source is quarantined `Q037`. Attacker-chosen source identity is otherwise free entity-resolution poisoning.
- Ingest performs no entity resolution. `actor_raw`/`target_raw` carry the strings as they appeared. Merging identifiers is the entity-resolution section's job and its uncertainty must not be laundered through the parser.

------------------------------------------------------------
59.5 ADAPTER INTERFACE
------------------------------------------------------------

The ingest core and all adapters are Rust (crate `spectra-ingest-adapters`). Python orchestrates by subprocess over content-addressed files and may not parse telemetry itself.

```rust
pub enum Outcome {
    Accept(Box<CanonicalEvent>),
    Quarantine(QuarantineReason),          // code + detail, see 59.9
    Skip(SkipReason),                      // declared, byte-accounted, e.g. CsvHeader
}

pub struct Frame<'a> {
    pub bytes: &'a [u8],                   // raw, undecoded
    pub file_id: FileId,
    pub byte_start: u64,
    pub byte_len: u32,
    pub frame_index: u64,                  // dense, per file, from 0
}

pub struct AdapterCtx<'a> {
    pub source_id: SourceId,
    pub source_class: SourceClass,
    pub declared_tz: TzDecl,               // see 59.8
    pub limits: &'a Limits,                // from ingest.toml, hashed
    pub schema_version: u16,
}

pub trait SourceAdapter: Sync {
    const FORMAT_ID: &'static str;         // e.g. "syslog.rfc5424"
    const FORMAT_VERSION: u16;
    fn framer(&self) -> Framer;            // Lines | LengthPrefixed | SingleDocument | Records(delim)
    fn parse(&self, f: Frame<'_>, cx: &AdapterCtx<'_>) -> Outcome;
}
```

Hard constraints on every adapter, each with a gate:
1. **`parse` is a pure total function of `(Frame, AdapterCtx)`.** No clock, no filesystem, no network, no RNG, no global mutable state, no environment reads. Enforced by `clippy.toml` `disallowed-methods` covering `std::time::*`, `std::fs::*`, `std::net::*`, `std::env::*`, and by a dependency-graph gate (`gate-adapter-purity`) that fails if the adapters crate depends on `rand`, `chrono::Local`, `reqwest`, `tokio::net`, or any transitive socket-capable crate.
2. **`parse` never panics.** No `unwrap`, `expect`, `panic!`, `unreachable!`, slicing by unchecked range, or integer arithmetic that can overflow in release. `#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects, clippy::unwrap_used, clippy::expect_used)]`. A panic in an adapter is a build failure, not a quarantine, because a panicking parser cannot account for its bytes.
3. **`parse` allocates bounded memory**, bounded by `limits` and the frame length. No adapter may buffer beyond the current frame except the `SingleDocument` framer, which is itself capped.
4. **Framing is separate from parsing** so that a parse failure still yields an exact byte span for the quarantine record.
5. **No adapter writes anywhere.** Outputs are returned by value.
6. Every adapter ships a conformance corpus (59.13). An adapter written in any additional language (a C hot path, for example) must pass the identical corpus byte-for-byte and be differentially fuzzed against the Rust adapter; otherwise it is deleted rather than documented.

------------------------------------------------------------
59.6 SUPPORTED RAW FORMATS — ONE ADAPTER EACH
------------------------------------------------------------

The supported set is closed. An input whose declared `format_id` is not in this table is refused at manifest validation with a non-zero exit, not sniffed. **Content sniffing is forbidden**: format is declared in the manifest, never inferred from magic bytes, extension, or first-line heuristics.

| format_id | framer | shape | notes / hardening focus |
|---|---|---|---|
| `jsonl.v1` | Lines | one JSON object per line | native generator output; duplicate-key rejection, depth cap |
| `json.array.v1` | SingleDocument | one top-level array | streaming array walk, never `serde_json::Value` of the whole doc |
| `syslog.rfc5424` | Lines | structured syslog | numeric offset present; SD-PARAM escaping |
| `syslog.rfc3164` | Lines | legacy BSD syslog | **no year, no timezone** — the deliberately hostile format, see 59.8 |
| `csv.rfc4180` | Records(CRLF-aware) | tabular export | field-count lock, unterminated quote, embedded NUL |
| `kv.logfmt` | Lines | `k=v k="v w"` | key duplication, unquoted whitespace |
| `nginx.combined` | Lines | access log | fixed grammar, no backtracking regex |
| `xml.audit.v1` | SingleDocument | audit record set | DTD and external entities disabled, see 59.7 |
| `yaml.config.v1` | SingleDocument | service config snapshot | safe loader only; **config snapshots only, never event streams** |
| `flow.summary.v1` | Lines | textual flow records | a declared text summary, not pcap |

Negative requirements:
- **No binary packet parsing in the core.** `libpcap`, `tshark`, and any binary capture parser are forbidden as ingest dependencies. Network evidence enters as `flow.summary.v1` text produced by the generator or range emitter. Rationale: a binary parser is the largest attack surface in the system for the least proof value, and it cannot be audited by byte conservation as cleanly.
- **No regex with unbounded backtracking** in any adapter. Use hand-written scanners or a linear-time engine; `gate-regex-linear` fails on a `regex`-crate pattern exceeding a declared size limit or on any use of a backtracking engine.
- **No dynamic adapter loading.** No plugin path, no `dlopen`, no code loaded from the bundle.

Grammars are committed under `spec/grammars/` and are the normative definition. Example, the legacy syslog subset:

```abnf
; spec/grammars/syslog-rfc3164.abnf   (subset accepted by SPECTRA)
msg        = pri timestamp SP hostname SP tag content
pri        = "<" 1*3DIGIT ">"
timestamp  = month SP day SP hour ":" minute ":" second     ; NO year, NO zone
month      = "Jan"/"Feb"/"Mar"/"Apr"/"May"/"Jun"/"Jul"/"Aug"/"Sep"/"Oct"/"Nov"/"Dec"
day        = (SP DIGIT) / (("1"/"2") DIGIT) / ("3" ("0"/"1"))
hostname   = 1*255(ALPHA/DIGIT/"-"/".")
tag        = 1*32(ALPHA/DIGIT/"_"/"-") [ "[" 1*10DIGIT "]" ] ":"
content    = *OCTET                                          ; capped by max_line_bytes
```

```abnf
; spec/grammars/logfmt.abnf
line   = pair *(SP pair)
pair   = key "=" value
key    = 1*64(ALPHA/DIGIT/"_"/".")
value  = bare / quoted
bare   = *(%x21-3C / %x3E-7E)                                ; no '=', no SP, no quotes
quoted = DQUOTE *(qchar / escape) DQUOTE
escape = "\" (DQUOTE / "\" / "n" / "t")                      ; closed escape set
```

------------------------------------------------------------
59.7 HARDENING LIMITS
------------------------------------------------------------

All limits live in `config/ingest.toml`, are config-driven, are enforced at runtime, and the file's BLAKE3 hash is recorded in the bundle manifest and hashed into the certificate. There is no compiled-in fallback: a missing or unparseable `ingest.toml` aborts ingestion.

**Every numeral in the file below is illustrative, not a target.** They are starting defaults chosen to be enforceable, not measurements, and none of them may be quoted in `README.md`, `docs/`, or any paper text as a capability figure.

```toml
# config/ingest.toml
schema_version = 1

[limits.framing]
max_line_bytes              = 1048576      # (illustrative, not a target)
max_record_bytes            = 4194304      # (illustrative, not a target)
max_records_per_file        = 5000000      # (illustrative, not a target)
max_frame_index             = 5000000      # (illustrative, not a target)

[limits.structure]
max_nesting_depth           = 32           # (illustrative, not a target)
max_object_keys             = 512          # (illustrative, not a target)
max_array_len               = 4096         # (illustrative, not a target)
max_string_field_bytes      = 65536        # (illustrative, not a target)
max_total_keys_per_record   = 2048         # (illustrative, not a target)

[limits.bundle]
max_files_per_bundle        = 1024         # (illustrative, not a target)
max_bundle_input_bytes      = 8589934592   # (illustrative, not a target)
max_output_events           = 20000000     # (illustrative, not a target)

[limits.decompression]
allowed_codecs              = ["gzip", "zstd"]   # zip and 7z are forbidden outright
max_ratio                   = 200          # (illustrative, not a target)
ratio_check_every_bytes     = 1048576      # (illustrative, not a target)
max_entry_output_bytes      = 1073741824   # (illustrative, not a target)
max_archive_entries         = 4096         # (illustrative, not a target)
max_nested_archives         = 0            # archive inside archive is refused

[limits.xml]
max_depth                   = 24           # (illustrative, not a target)
max_attributes_per_element  = 64           # (illustrative, not a target)
allow_dtd                   = false        # MUST remain false
allow_external_entities     = false        # MUST remain false
allow_entity_expansion      = false        # MUST remain false
allow_xinclude              = false        # MUST remain false
allow_network_resolver      = false        # MUST remain false

[limits.yaml]
loader                      = "safe"       # MUST remain "safe"
allow_custom_tags           = false
allow_merge_keys            = false
max_aliases                 = 64           # (illustrative, not a target)
max_document_bytes          = 262144       # (illustrative, not a target)

[limits.json]
duplicate_keys              = "reject"     # MUST remain "reject"
allow_nan_inf               = false        # MUST remain false
allow_big_integers          = false        # out of i64 range => Q034
allow_comments              = false
allow_trailing_commas       = false

[charset]
accept                      = ["utf-8"]
bom                         = "reject"     # a BOM is a declaration mismatch, not a hint
invalid_utf8                = "quarantine" # never "replace", never "lossy"
forbid_c0_controls          = true         # except TAB inside quoted fields
forbid_bidi_and_zero_width  = true         # U+202A..202E, U+2066..2069, U+200B..200F

[quarantine]
max_quarantine_ratio        = 0.01         # (illustrative, not a target)
on_unlocatable_quarantine   = "source_blind"   # or "abort"
strict_abort_on_any         = false            # make certify sets this true

[clock]
min_t_utc_ns                = 0                      # 1970-01-01T00:00:00Z
max_t_utc_ns                = 4102444800000000000    # 2100-01-01T00:00:00Z
allow_silent_offset_fix     = false        # MUST remain false
```

Enforcement rules that override any generic parser behaviour:
- **Exceeding a limit is a quarantine, never a truncation.** No adapter may emit a `CanonicalEvent` built from a clipped field. `gate-no-truncation` includes a fixture whose only defect is an oversized field and asserts the output contains zero accepted events and exactly one quarantine record with code `Q038`.
- **Decompression is streamed with a running ratio check** every `ratio_check_every_bytes`, aborting the entry the moment `output_bytes / input_bytes > max_ratio`. A ratio computed only at the end is not compliant, because the memory is already gone. Nested archives are refused outright (`max_nested_archives = 0`).
- **Archive entry names are never used as filesystem paths.** Entries are extracted to a content-addressed temporary name; any entry whose name contains `..`, an absolute prefix, a drive letter, a NUL, or a path separator that is not a plain `/` is quarantined `Q025`. Symlink, hardlink, device, FIFO, and setuid entries are quarantined `Q026` and never materialized.
- **Limits are checked before allocation**, not after. A declared length field in a length-prefixed framer is validated against `max_record_bytes` before any buffer is reserved.

------------------------------------------------------------
59.8 CHARSET, CLOCK AND TIMEZONE NORMALIZATION
------------------------------------------------------------

Charset:
- The only accepted encoding is UTF-8. Invalid UTF-8 is quarantined `Q007` with the byte offset of the first invalid sequence. Lossy decoding (`U+FFFD` substitution) is forbidden everywhere in the ingest path; `gate-no-lossy-utf8` greps for `from_utf8_lossy` and equivalents and fails on a hit. Rationale: replacement characters silently mutate identifiers, and a mutated identifier is a fabricated entity.
- A byte-order mark is a quarantine (`Q008`), not a hint, because accepting it means accepting a declaration the manifest did not make.
- Bidirectional-override and zero-width codepoints in any identifier-bearing field are quarantined `Q009`. An identifier that renders as one thing and compares as another is an entity-resolution attack delivered through the UI.

Clock normalization at the adapter edge (OVERRIDES Part I sections 17-19, which left time semantics per-component):
- Every `CanonicalEvent` carries `t_utc_ns: i64` and the verbatim `t_source_raw`. Downstream components read only `t_utc_ns`. No component below ingest parses a timestamp string.
- `t_basis` records how the value was obtained and is propagated into liveness:
  - `SourceUtc` — the record declared UTC (`Z`).
  - `SourceOffset` — the record carried an explicit numeric offset.
  - `MappedTz` — the manifest declared an IANA zone for the source and the local time mapped unambiguously.
  - `AssumedTz` — the manifest declared a zone for a format that carries none (`syslog.rfc3164`). **`AssumedTz` is a soundness-affecting basis**: any interval containing an `AssumedTz` event is ineligible to be certified LIVE; it may only be BLIND or TAINTED. Assumed time may admit attacker steps; it may never withhold a license.
- Ambiguity and non-existence are quarantines, not guesses: a local time falling in a DST fold is `Q014`; a local time falling in a DST gap is `Q014` with a distinct detail; a source with no declared zone for a zoneless format is a manifest validation failure (`Q016`) that aborts before any parsing.
- The zoneless-year problem in `syslog.rfc3164` is solved by a manifest-declared `epoch_year` per file, not by inferring the year from the wall clock or from neighbouring records. Inference from neighbours lets a single crafted record retro-date a whole file.
- Timestamps outside `[min_t_utc_ns, max_t_utc_ns]` are `Q015`. Leap seconds are not smeared and not represented: a `:60` second field is `Q013`.
- **No clock correction, ever.** Ingest does not shift, skew-correct, or reorder by time. Backdating is a kernel-level concern (ECLIPSE §4A's difference-constraint pass) and is handled there, with the fail-closed rule stated in the Part II threat-model section: an unresolvable timestamp yields BLIND, never a voided license. Ingest's contribution is to preserve `t_source_raw` and `t_basis` so that pass has something honest to work with.
- `ingest_ord` is a deterministic tie-break key derived from `(file_id, byte_start)`. It is not a time and may never be used as one.

------------------------------------------------------------
59.9 QUARANTINE: RECORD FORMAT, REASON CODES, REPORT
------------------------------------------------------------

Every quarantined frame produces exactly one record in `quarantine.jsonl`, in ingest order:

```json
{
  "schema_version": 1,
  "quarantine_id": "q3f9a0c7e...64hex",
  "source_id": "idp_audit",
  "source_class": "chained",
  "file_id": "f07",
  "byte_start": 918273,
  "byte_len": 4096,
  "frame_index": 12044,
  "raw_b3": "b3:9c1d...",
  "raw_excerpt_hex": "7b22757365...",
  "excerpt_truncated": true,
  "format": { "format_id": "jsonl.v1", "format_version": 1, "adapter_b3": "b3:41aa..." },
  "code": "Q006",
  "code_class": "SEMANTIC",
  "detail": "duplicate key \"session_id\" at depth 1, offsets 41 and 118",
  "t_utc_ns_recovered": 1731330061000000000,
  "t_recovery_basis": "PartialParse",
  "locatable": true,
  "seq_recovered": 88213,
  "affects_liveness": true
}
```

- `raw_excerpt_hex` is a bounded hex excerpt (cap in `ingest.toml`) of the offending bytes. It is hex, never re-encoded text, because a quarantined record is by definition not trustworthy text. `raw_b3` always covers the full frame, so the excerpt cap never loses accountability.
- `locatable` is true iff a timestamp was recovered well enough to place the record in the source's timeline. `t_recovery_basis` is one of `FullParse | PartialParse | FrameNeighbourBound | None`. `FrameNeighbourBound` records only an interval `[t_prev, t_next]` from the surrounding accepted records and never a point.
- Quarantine records are **not** events. They have no `EventId`, never enter the fact base, never appear in any observed-event count, and may never be rendered as evidence.

Reason-code registry (`spec/quarantine-codes.toml`, closed set, codes never reused or renumbered; adding a code requires a corpus fixture):

| code | class | meaning |
|---|---|---|
| Q001 | STRUCTURAL | line exceeds `max_line_bytes` |
| Q002 | STRUCTURAL | record exceeds `max_record_bytes` |
| Q003 | STRUCTURAL | nesting depth exceeds cap |
| Q004 | STRUCTURAL | object key count / array length exceeds cap |
| Q005 | STRUCTURAL | syntax error in declared format |
| Q006 | SEMANTIC | duplicate key in JSON object |
| Q007 | STRUCTURAL | invalid UTF-8 |
| Q008 | STRUCTURAL | BOM or undeclared charset marker |
| Q009 | SEMANTIC | forbidden control / bidi / zero-width codepoint in identifier field |
| Q010 | SEMANTIC | required field missing |
| Q011 | SEMANTIC | field type mismatch or unknown `action` / `dim` value |
| Q012 | SEMANTIC | unknown field under strict schema |
| Q013 | SEMANTIC | timestamp unparseable |
| Q014 | SEMANTIC | timestamp ambiguous or non-existent in declared zone |
| Q015 | SEMANTIC | timestamp outside declared range |
| Q016 | MANIFEST | source lacks a required timezone / epoch-year declaration |
| Q018 | PROVENANCE | sequence conflict (same `seq`, divergent content) |
| Q019 | PROVENANCE | hash-chain link mismatch |
| Q020 | PROVENANCE | unknown chain algorithm |
| Q021 | PROVENANCE | `EventId` collision with divergent preimage |
| Q022 | CONTAINER | decompression ratio ceiling exceeded |
| Q023 | CONTAINER | bundle or entry size ceiling exceeded |
| Q024 | CONTAINER | archive entry count exceeded / nested archive |
| Q025 | CONTAINER | unsafe archive entry name (traversal, absolute, NUL) |
| Q026 | CONTAINER | forbidden archive entry type (symlink, device, FIFO, setuid) |
| Q027 | STRUCTURAL | XML DTD present |
| Q028 | STRUCTURAL | XML entity reference or XInclude present |
| Q029 | STRUCTURAL | YAML custom tag / non-safe construct |
| Q030 | STRUCTURAL | YAML alias budget exceeded |
| Q031 | STRUCTURAL | YAML merge key present |
| Q032 | SEMANTIC | CSV field-count mismatch against locked header |
| Q033 | STRUCTURAL | CSV unterminated quote |
| Q034 | SEMANTIC | number not representable as `i64`, or NaN/Inf |
| Q037 | SEMANTIC | in-record source identity contradicts manifest |
| Q038 | STRUCTURAL | field exceeds `max_string_field_bytes` |
| Q041 | SEMANTIC | unsupported record `schema_version` |
| Q042 | STRUCTURAL | truncated input at EOF (frame incomplete) |

Sequence **gaps** are deliberately absent from this table: a gap is not a malformed record, it is a liveness observation, and it is emitted into `ingest-signals.json` for ECLIPSE §4A rather than into quarantine. Quarantine describes bytes that arrived and could not be trusted; gaps describe bytes that never arrived.

`quarantine-report.json` accompanies every run:

```json
{
  "schema_version": 1,
  "ingest_manifest_b3": "b3:77cc...",
  "total_frames": 0,
  "accepted": 0,
  "quarantined": 0,
  "skipped_declared": 0,
  "quarantine_ratio": "0/0",
  "by_code":  { "Q006": 0, "Q013": 0 },
  "by_source": { "idp_audit": { "quarantined": 0, "locatable": 0, "unlocatable": 0 } },
  "tainted_windows": [
    { "source_id": "idp_audit", "t0_ns": 0, "t1_ns": 0, "codes": ["Q006"], "count": 0 }
  ],
  "unlocatable_sources": [],
  "clean": true
}
```

`quarantine_ratio` is emitted as an exact integer pair `"n/d"`, never a decimal, because no float may enter a hashed artifact.

------------------------------------------------------------
59.10 CONTENT-ADDRESSED EventId AND INGEST IDEMPOTENCY
------------------------------------------------------------

```
EventIdPreimage := canonical-CBOR({
    1: schema_version (u16),
    2: format_id (text), 3: format_version (u16),
    4: source_id (text), 5: source_class (u8),
    6: seq (u64 or null),
    7: t_utc_ns (i64), 8: t_basis (u8),
    9: raw_b3 (bstr[32])
})
EventId := lowercase_hex(BLAKE3-256(EventIdPreimage))
```

Rules:
- Canonical CBOR means definite-length items, integer keys in ascending order, shortest-form integers, no floats, no tags. The encoder is committed with a round-trip property test and a cross-language vector file (`spec/vectors/eventid.jsonl`) that the Go checker reproduces independently.
- **Idempotency.** Ingesting the same raw inputs twice yields a byte-identical `bundle.jsonl`. Ingesting an input twice, or ingesting overlapping bundles, collapses to one event per `EventId`. Collapses are counted in the manifest as `duplicates_collapsed` per source and per code path — **never silently absorbed**, because the degradation model has a `duplicate` operator and an ingest that quietly deduplicates it would erase the very perturbation the experiment applies.
- Two frames with the same `EventId` but different `raw_b3` are impossible by construction; if the invariant is ever violated (hash collision, or a preimage-construction bug), the run aborts with `Q021`. Do not "pick the first".
- **Total order of `bundle.jsonl`** is `(source_id, t_utc_ns, seq.unwrap_or(0), raw_b3, file_id, byte_start)` — total, deterministic, independent of input file order and of directory iteration order. No `HashMap`/`HashSet` iteration may reach the output path; use `BTreeMap` or an explicit sort with a stable comparator. This is the ingest instance of the determinism charter.
- Chain verification for `chained` sources recomputes `chain_self = BLAKE3(chain_prev || canonical_frame_bytes)` and emits per-source `chain_ok`, `first_break_seq`, and `break_count` into `ingest-signals.json`. A break localizes suppression; ingest reports it and never repairs it.

------------------------------------------------------------
59.11 QUARANTINE-TO-ECLIPSE COUPLING AND THE CERTIFICATE GATE
------------------------------------------------------------

OVERRIDES ECLIPSE §4A and §5: liveness consumes quarantine taint, and the certificate carries ingest state.

1. `ingest-signals.json` is a hashed input to liveness, containing per source: observed frame count, sequence gaps, chain breaks, `AssumedTz` intervals, and **tainted windows** derived from locatable quarantine records.
2. **A tainted window may never be certified LIVE.** For liveness purposes it is treated as BLIND (fail-closed toward admitting attacker steps, conservative for ROBUST, honest about the blindness premium because the taint is named as the cause rather than attributed to the source).
3. **Quarantined records never contribute to the arrival-statistics sample** used for the liveness threshold. Including them would let malformed input tune the detector that is supposed to police it.
4. If a source has any quarantine record with `locatable = false`, apply `on_unlocatable_quarantine`: `source_blind` marks the source BLIND over its entire covered interval for this run; `abort` refuses to produce a bundle. `make certify` sets `strict_abort_on_any = true`. There is no third option in which unlocated malformed bytes are ignored.
5. **Certificate flag.** `Cert.flags` gains `ingest_quarantine: { count, by_code_b3, tainted_window_count }` and `Cert.hashes` gains `ingest_manifest` and `quarantine_report`. Per the verdict-and-flag algebra of Part II, a run with `count > 0` is a soundness-affecting flagged run: it may not be rendered, exported, narrated, or printed as an unqualified ROBUST. The Go checker must recompute the quarantine-report hash from the shipped report and **reject** any certificate whose safety field is unqualified ROBUST while `ingest_quarantine.count > 0`. Gate name: `gate-quarantine-blocks-robust`, proved by a fixture whose only defect is one malformed record and which must produce a flagged certificate that the checker accepts as flagged and rejects if the flag is stripped.
6. If `quarantined / total_frames` exceeds `max_quarantine_ratio`, ingestion fails non-zero and produces no bundle. A run that cannot parse its own telemetry is not a degraded run, it is a broken one.

------------------------------------------------------------
59.12 SOURCE REFERENCES: NO PATHS, NO URLS
------------------------------------------------------------

OVERRIDES Part I sections 35-38, which left bundle references unconstrained.

- The API and CLI accept a `SourceRef` that is **either** a content-addressed digest already present in the local blob store (`b3:<64hex>`) **or** a symbolic name resolved against a committed, hashed registry (`scenario:acme-01/source:idp_audit`). They never accept a filesystem path, a glob, a URL, a URI scheme, a hostname, an IP, or a base64 blob to be written to disk.
- The ingest worker's filesystem view is a single read-only mount of the blob store plus a single writable output directory. Path construction from any user- or record-supplied string is forbidden; `gate-no-path-join-from-input` fails on any `Path::join` / `os.path.join` whose argument traces to request data or record data.
- No component in the ingest path may open a socket. Enforced structurally: the ingest container runs with `network_mode: none`, and a CI job attempts DNS, TCP, and ICMP egress from it and fails the build if any succeeds. Policy text is not acceptable here; the egress test result is published with the milestone block.
- Symlinks are not followed anywhere in ingestion (`O_NOFOLLOW` semantics, or explicit `symlink_metadata` checks). Archive entries never become filesystem names (59.7).
- Error responses from ingest endpoints may not echo any filesystem path, cwd, or hostname. They carry `{ code, quarantine_id, byte_start }` and nothing else.

Forbidden request shapes (each has a rejection test in the API suite):
```
POST /ingest {"path": "/var/log/auth.log"}          -> 400 E_SOURCEREF_PATH_FORBIDDEN
POST /ingest {"url": "http://169.254.169.254/..."}  -> 400 E_SOURCEREF_URL_FORBIDDEN
POST /ingest {"ref": "b3:../../etc/passwd"}         -> 400 E_SOURCEREF_MALFORMED
POST /ingest {"ref": "scenario:../other/source:x"}  -> 400 E_SOURCEREF_MALFORMED
```

------------------------------------------------------------
59.13 CLI SURFACE
------------------------------------------------------------

All figures in the transcript below are illustrative, not targets, and are placeholders for measured output.

```
$ spectra ingest --manifest scenario/acme-01/sources.toml --out out/acme-01 --strict
spectra-ingest 0.1.0  ingest.toml b3:2c41...  adapters b3:91de...
[unpack]  6 files, 2 codecs (gzip, zstd), max ratio observed 41/1 (limit 200/1)
[frame ]  idp_audit        chained    124030 frames
[frame ]  proxy_access     unchained   88112 frames
[parse ]  accepted 212137  quarantined 5  skipped(declared) 6
[quar  ]  Q006 x3  Q013 x1  Q038 x1   ratio 5/212142 (limit 1/100)
[clock ]  t_basis: SourceUtc 200001  SourceOffset 12136  AssumedTz 0
[order ]  total order stable; duplicates_collapsed 0
[audit ]  byte conservation OK: 6/6 files partitioned, 0 uncovered bytes
ERROR: --strict and quarantined>0; no bundle written
exit 2

$ spectra ingest --manifest scenario/acme-01/sources.toml --out out/acme-01
... (same lines) ...
[write ]  out/acme-01/bundle.jsonl            b3:7ad3...  212137 events
[write ]  out/acme-01/bundle.manifest.json    b3:0b58...
[write ]  out/acme-01/quarantine.jsonl        b3:4e02...  5 records
[write ]  out/acme-01/quarantine-report.json  b3:1f77...  clean=false
[write ]  out/acme-01/ingest-signals.json     b3:aa90...  tainted_windows=2
WARNING: quarantine present; certificates from this bundle cannot be unqualified ROBUST
exit 0

$ spectra ingest explain --quarantine out/acme-01/quarantine.jsonl --id q3f9a0c7e
Q006 SEMANTIC  duplicate key "session_id" at depth 1, offsets 41 and 118
source idp_audit (chained)  file f07  bytes [918273,922369)
recovered time 2025-11-11T13:01:01Z (PartialParse)  locatable=true
effect: window [13:00:31Z,13:01:31Z] on idp_audit marked TAINTED -> BLIND for licensing
```

Subcommands: `ingest`, `ingest explain`, `ingest --audit-bytes`, `ingest verify-manifest`, `ingest conformance` (runs the corpus). `spectra ingest` is a pure file-in/file-out binary with zero service dependencies: no Postgres, no Redis, no HTTP.

------------------------------------------------------------
59.14 CONFORMANCE CORPUS, FUZZING AND GATES
------------------------------------------------------------

`tests/ingest-corpus/` contains, per format, a directory of input files each paired with an expected-outcome file:

```
tests/ingest-corpus/jsonl.v1/
  ok-minimal.in            ok-minimal.expected.json
  bad-dupkey.in            bad-dupkey.expected.json      # {"code":"Q006", ...}
  bad-depth-33.in          bad-depth-33.expected.json
  bad-utf8-truncated.in    bad-utf8-truncated.expected.json
  bad-bigint.in            bad-bigint.expected.json
  edge-empty-file.in       edge-empty-file.expected.json
  edge-no-trailing-nl.in   edge-no-trailing-nl.expected.json
```

Required corpus contents (minimum, per applicable format): oversized line; oversized record; depth overflow; duplicate key; invalid UTF-8 at three positions (start, middle, EOF boundary); BOM; embedded NUL; bidi override in an identifier; unknown `action`; missing required field; unparseable timestamp; DST-fold and DST-gap local times; out-of-range timestamp; zoneless legacy syslog with declared and undeclared zone; CSV field-count drift and unterminated quote; YAML alias bomb, merge key, custom tag; XML with internal DTD, external entity, XInclude, billion-laughs; gzip and zstd bombs at and above the ratio ceiling; archive with `../` entry, absolute entry, symlink entry, nested archive; truncated final frame; sequence conflict; chain break.

Gates (each is a named CI target; failure fails the build):

| gate | proves |
|---|---|
| `gate-byte-conservation` | every input byte is accepted, quarantined, or declared-skipped exactly once |
| `gate-no-silent-drop` | for each corpus file, `accepted + quarantined + skipped == frames`; mutation test that deletes a quarantine emission turns this red |
| `gate-adapter-purity` | adapters crate has no clock/fs/net/RNG capability in its dependency graph |
| `gate-adapter-no-panic` | corpus plus fuzz corpus produce zero panics; lint denies `unwrap`/`expect`/indexing |
| `gate-no-float-ingest` | no `f32`/`f64` in ingest crates; no decimal in any hashed artifact |
| `gate-no-lossy-utf8` | no lossy decoding API anywhere in the ingest path |
| `gate-no-truncation` | oversized-field fixture yields quarantine, not a clipped event |
| `gate-xxe` | XML fixtures with DTD/entity/XInclude are quarantined and no resolver call occurs |
| `gate-yaml-safe` | YAML fixtures with tags/merge/alias-bomb are quarantined |
| `gate-zipbomb` | ratio ceiling aborts the entry mid-stream, bounded peak RSS |
| `gate-ingest-idempotent` | double ingest and shuffled input file order yield byte-identical `bundle.jsonl` |
| `gate-ingest-cross-os` | Linux CI and WSL2 produce identical `bundle.jsonl` hash for the same inputs |
| `gate-quarantine-blocks-robust` | a certificate from a quarantined bundle cannot be unqualified ROBUST; checker rejects a stripped flag |
| `gate-taint-to-blind` | a single injected malformed record produces a TAINTED window that liveness treats as BLIND |
| `gate-sourceref-hardening` | path/URL/traversal ingest requests are rejected with the declared error codes |
| `gate-ingest-egress` | DNS/TCP/ICMP egress from the ingest container fails |
| `gate-source-class-coverage` | no degradation-matrix cell ran without an `unchained` source |

Fuzzing: `cargo-fuzz` targets per adapter, seeded from the corpus, run nightly with a committed crash-regression corpus. Any crash, hang beyond a deterministic step budget, or byte-conservation violation found by the fuzzer is committed as a corpus entry before the fix. Fuzz timing budgets are wall-clock and therefore live only in the nightly tier; no wall-clock budget may appear in any path that affects a bundle's bytes.

Differential check: the Go checker contains an independently written `bundle.jsonl` reader and `EventId` recomputation (it re-derives `EventId` from the shipped `raw_b3` preimage fields). A differential harness feeds the corpus to both and fails on any disagreement in `EventId` or canonical ordering. The Go side does **not** reuse the Rust adapters and does not re-parse raw source formats; the scope of what it therefore does and does not establish is stated in `docs/checker-scope.md`.

------------------------------------------------------------
59.15 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS
------------------------------------------------------------

Do not, under any circumstance:
- Drop, skip, ignore, or `continue` past a record that failed to parse. There is no code path in ingest that discards bytes without emitting a quarantine record.
- Add a "lenient", "best-effort", "relaxed", or "recover" mode, or a flag that downgrades a quarantine to a warning.
- Repair a record: no field clipping, no key deduplication by last-wins, no charset transliteration, no timestamp guessing, no inferred year, no inferred timezone, no clock skew correction, no reordering by time.
- Sniff a format, follow a symlink, resolve a URL, open a socket, read an environment variable, or consult the wall clock inside a parser.
- Enable a DTD, an external entity, an entity expansion, an XInclude, a YAML custom tag, a YAML merge key, or a non-safe YAML loader, in any configuration, including tests. The corpus tests pass with these disabled; a test that enables them is itself the defect.
- Accept `zip` or `7z` containers, or any archive-in-archive.
- Let quarantined bytes influence liveness statistics, appear in an observed-event count, appear as evidence in a certificate, be cited by the narrator, or be rendered in the graph as anything other than a quarantine marker.
- Let a record's own contents determine its `source_id`, its trust class, or its limits.
- Materialize `bundle.jsonl` or the quarantine artifacts in Postgres. They are immutable content-addressed files; Postgres holds only the index.

Forbidden claims in `README.md`, `docs/`, UI strings, commit messages, and paper text:
- "Parses arbitrary telemetry", "supports any log format", "universal ingest", "schema-agnostic". The supported set is the ten declared formats and nothing else.
- "Lossless ingestion" without the qualifier that it holds for the declared formats under the declared limits, with quarantine as the defined behaviour outside them.
- "Tamper-evident telemetry" as a property of SPECTRA. It is a property of the `chained` source class only, which is a laboratory affordance; say so in the same sentence or do not say it.
- "Validated", "hardened", or "secure parser" as a bare adjective. State the gate: "quarantines the declared corpus of 40-odd malformed inputs" is sayable only if that corpus is committed and the count is generated from it by the claims-binding linter, never typed by hand.
- Any capability figure (records per second, bundle size, event count) quoted from this section's illustrative defaults. Every published number comes from the benchmark harness with its run-manifest hash attached.
