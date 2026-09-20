# `abi/v1/` — ABI 1 wire schema

Status: **not started**. This directory contains this README and nothing else. No
`*.schema.json` file exists yet.

Owning section: Part II §69 (the boundary), specifically §69.5.4, §69.7 and §69.8.

## 1. The append-only rule

**Editing a file under `abi/v1/` is forbidden.** Not discouraged — forbidden. A change to the ABI
goes to `abi/v2/`.

This follows from what an ABI version means here:

- ABI versions are integers and are **never reused** (§69.7.5).
- A new ABI requires a new `abi/vN/` directory, new hand-written structs on both the Rust side and
  the Go side, and a migration note.
- Certificates emitted under ABI *n* are verifiable **forever** by a checker that still lists *n* in
  `abi_supported`. Editing `abi/v1/` retroactively changes what an already-published certificate
  claimed, which is the one thing a proof artifact may never permit.
- Dropping support for an ABI is a breaking release and must be recorded in `docs/abi-history.md`
  alongside every published certificate hash that becomes unverifiable.

The schema directory is hashed into every run manifest (§69.5.4), so an edit here is visible in
every downstream artifact whether or not anyone notices it in review.

The gate `make abi-contract` is specified to check two things (§69, gate table): that the Rust
structs, the Go structs and `abi/v1/*.schema.json` agree field-for-field, and that **`abi/v1/` is
unmodified since its introducing commit**. That gate does not exist. Until it does, the append-only
rule is enforced by review alone, which is weaker than the specification requires.

TODO(M5, blocking): implement `make abi-contract`, including the unmodified-since-introduction
check. Until it exists, do not treat a green build as evidence that `abi/v1/` is intact.

## 2. What lands here, and when

**Milestone M5** (Part I §52.8, two-sided minimal cut and certificate). M5 is the milestone at which
the kernel first emits a certificate, so it is the milestone at which the kernel-to-checker boundary
first carries a payload that must be pinned.

What M5 adds:

| Artifact | Describes | Status |
|---|---|---|
| `abi/v1/result-pointer.schema.json` | `ResultPointer`: `abi`, `status`, `outputs`, `budget_used`, `flags` | not started |
| `abi/v1/budget-used.schema.json` | `BudgetUsed`: `ground_steps`, `relaxations`, `bnb_nodes`, `corridors`, `instances`, `arena_cells` | not started |
| `abi/v1/obj-id.schema.json` | `ObjId`: a 32-byte digest rendered `blake3:` + lowercase hex | not started |

TODO(decision: one file or three): §69.5.4 says `abi/v1/*.schema.json`, plural, without fixing the
split. Three files, one per wire type, is chosen so that a diff names the type that changed. To use
a single file instead, merge them under `$defs` and update `make abi-contract` in the same commit.

The Rust and Go definitions are **hand-written on both sides and neither is generated from the
other** (§69.5.3). That redundancy is the point: the Go checker shares no code, no generated
artifact and no dependency with the Rust workspace, so a bug in one side's serialization cannot
silently reproduce itself in the other. `make abi-contract` is what turns that redundancy into a
check.

## 3. Constraints every schema here inherits

From §69.5.2, the canonical JSON rules, restated because the ABI depends on them:

- UTF-8, no BOM, LF only, object keys sorted by byte value, no insignificant whitespace.
- **Integers only. Floating point is forbidden in every ABI payload.** A conceptually fractional
  value is transported as an integer numerator with a declared fixed denominator.
- No `null`. An absent value is an absent key.
- Strings are NFC-normalized; control characters are `\u00XX` escaped.
- No wall-clock timestamps, no hostnames, no absolute paths, no usernames, no process ids, no
  environment capture. Event timestamps from telemetry are data, carried as integer nanoseconds
  since the scenario epoch, and are exempt.

From §69.7.1: `--abi <n>` is mandatory on every invocation. There is no default and no
auto-detection. A requested ABI outside `abi_supported` exits 3 immediately, before reading any
input object, with a single diagnostic naming both sets. Never a best-effort parse.

From §69.7.6: `rules_dialect` is versioned **independently** of the ABI, because the guard language
can change without the transport changing. Do not couple them, and do not add a dialect field to an
ABI schema.

## 4. What does not belong here

- **SFB.** The fact base and the rule-instance set are transported as SFB (§69.6), a fixed-layout
  binary form, not as JSON. SFB is never stored in a database column, never sent over HTTP and
  never base64-encoded into JSON. Its layout is specified in §69.6, not here.
- **The certificate schema.** That is owned by Part II §68.
- **Config schemas.** Those live in `config/schema/`.

## 5. Negative requirements

- Do not edit a file in this directory after it is introduced. Add `abi/v2/`.
- Do not reuse an ABI integer.
- Do not generate the Go structs from the Rust structs, or the reverse.
- Do not put a float in any ABI payload.
- Do not put `null` in any ABI payload.
- Do not add a default ABI or an auto-detection path.
- Do not drop support for an ABI without a `docs/abi-history.md` entry naming every certificate hash
  that becomes unverifiable.
