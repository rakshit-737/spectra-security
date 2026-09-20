============================================================
68. CERTIFICATE FORMAT, CANONICALIZATION AND THE CHECKER CONTRACT
============================================================

## 68.0 Position and hard rules

The certificate is the only artifact SPECTRA asks anyone to trust. Treat it as a security
artifact with a hostile producer, not as a log line. This section defines its bytes, its
hashes, its version policy, the checker's obligations, and the corpus of forged certificates
the checker must reject.

Hard rules, enforced by gates named below:

1. `spectra verify` is a **pure file-in/file-out binary**. It opens the certificate and the
   input files named on the command line, writes a report to stdout, and exits. It performs
   **no network I/O, no DNS, no database access, no Redis access, no subprocess execution, no
   environment-dependent behavior other than `TZ=UTC` and `LC_ALL=C`**, and it writes no file
   unless `--out` is given. OVERRIDES Part I: the stack line implied Postgres/Redis are ambient;
   the kernel and the checker depend on neither, and `make verify-offline` proves it.
2. The checker **never repairs, normalizes, sorts, deduplicates or infers** anything. Every
   deviation from canonical form is a rejection with a reason code.
3. A certificate never contains a floating-point value, a probability, a confidence, a score,
   a severity, or any wall-clock or host-identifying field inside its hashed body.
4. Rejection is the default. If the checker cannot decide an obligation, it rejects.

============================================================

## 68.1 File identity

| Property | Value |
|---|---|
| Extension | `.spcert` |
| Encoding | UTF-8, no BOM, LF only, exactly one trailing LF |
| Container | Canonical JSON (SCF, §68.3) — never compressed, never archived |
| Magic | First 26 bytes are exactly `{"body":{"schema":{"v":` |
| Max size | 64 MiB (normative limit, not a measurement) |
| Content address | `blake3(canonical_bytes(body))`, lowercase hex, printed as `blake3:<64 hex>` |

The outer object has exactly two members:

```json
{"body":{ ... },"cert_hash":"blake3:<64hex>"}
```

`cert_hash` covers the canonical serialization of `body` **only**. Nothing else in the file is
hashed, so the self-reference is well-founded and the checker can recompute it in one pass.

============================================================

## 68.2 Schema (version 1.0)

Rust emitter type (crate `spectra-cert`, `#![forbid(unsafe_code)]`, no `f32`/`f64` anywhere):

```rust
pub struct Body {
  pub schema:    Schema,          // §68.2.1
  pub scope:     Scope,           // §68.2.2  verdict scope binding
  pub inputs:    Inputs,          // §68.2.3  every hashed input
  pub verdict:   Verdict,         // §68.2.4  safety and minimality are INDEPENDENT
  pub atoms:     Atoms,           // §68.2.5  bit assignment, |A| <= 64
  pub cut:       Vec<AtomRef>,    // sorted ascending by bit, unique, upward-closed
  pub goals:     Vec<GoalResult>, // per goal atom; never aggregated
  pub invariant: Invariant,       // SAFE case only
  pub instances: Vec<InstRef>,    // the published instance set (grounding_mode = replayed)
  pub licenses:  Vec<License>,    // sorted by (source, t0, t1)
  pub silent:    Vec<SilentInst>, // GHOST instances, each naming its LicenseId
  pub witnesses: Vec<Witness>,    // one per control in cut; counterexample derivations
  pub psi:       Psi,             // corridor clause database
  pub flags:     Flags,           // soundness-affecting flags
  pub budgets:   Budgets,         // DETERMINISTIC step counters only
  pub derived:   Option<Derived>, // redundancy / observation set / frontier; absent when suppressed
}
```

### 68.2.1 `schema`

```json
"schema":{"v":"1.0","min_checker":"1.0","profile":"eclipse-cert"}
```

* `v` — `MAJOR.MINOR`, both `u16`, no patch component, no pre-release suffix.
* `min_checker` — the lowest checker version whose semantics the emitter believes sufficient.
  A checker older than `min_checker` **rejects** (`E-SCHEMA-DOWNGRADE`). This is the
  anti-downgrade lever: a v1.1 emitter that adds an obligation sets `min_checker:"1.1"`, and an
  attacker cannot get a v1.0 checker to validate it by rewriting `v` alone, because rewriting
  `v` changes `cert_hash` and drops the obligation fields that v1.1 requires as present.
* `profile` — fixed string. Unknown profile rejects.

### 68.2.2 `scope` — verdict strings are unconstructible without scope

OVERRIDES Part I: Part I's demo prints a bare `ROBUST`. A bare verdict is forbidden. The
verdict string is **rendered from** `scope`, never concatenated by hand, and the checker
rejects any certificate whose `scope` is incomplete or whose hashes disagree with `inputs`.

```json
"scope":{"rules":"blake3:…","controls":"blake3:…","licenses":"blake3:…",
         "er":"blake3:…","attacker":"non-adaptive"}
```

Rendered form, used identically in CLI, API and UI:
`ROBUST(rules@3f9a…, catalog@a11c…, licenses@7d20…, er@c4b8…, non-adaptive)`

### 68.2.3 `inputs` — hash coverage table

| Field | Covers | Encoding hashed | Rationale |
|---|---|---|---|
| `rules_hash` | **canonical AST encoding (CAE) of `rules.toml`** | CAE bytes | See §68.4 |
| `rules_text_hash` | raw bytes of `rules.toml` | file bytes | Forensic only, non-authoritative |
| `guard_ast_hash` | the shared guard AST (Part I §22) | CAE bytes | Declares what is shared, §68.6 |
| `controls_hash` | CAE of `controls.toml` **including the bit-assignment table** | CAE bytes | Certificates stay comparable across catalog edits only if bit positions are hashed |
| `bundle_hash` | canonical ingested bundle file | file bytes | The bundle is already canonical after ingest |
| `liveness_hash` | `liveness.json` | canonical JSON bytes | Licenses are checked against it |
| `goal_hash` | CAE of `goal.toml` | CAE bytes | Goal library entry, not hand-written per run |
| `er_hash` | ER config + ER output mapping | CAE bytes | ER is load-bearing; it must be pinned |
| `instances_hash` | published instance set | canonical bytes | Binds `grounding_mode = replayed` |
| `seed` | run seed | `u64` as hex string | |
| `k` | horizon, in ticks | `u32` | Unit is ticks, per the time-lattice section |
| `grounding_mode` | `replayed` \| `reground` | enum string | Honest statement of what the checker did |

### 68.2.4 `verdict` — safety and minimality are separate fields

OVERRIDES Part I: Part I's `mode: ROBUST|OPTIMISTIC` conflated a safety claim with a
cut-size claim, so an unrelated `subset_minimal_only` flag suppressed an honest safety result.

```json
"verdict":{"safety":"ROBUST","minimality":"PSI_RELATIVE","realizability":"CHECKED"}
```

* `safety` ∈ `ROBUST | OPTIMISTIC_ONLY | UNSAFE`
* `minimality` ∈ `EXACT | PSI_RELATIVE | SUBSET | UNVERIFIED`
* `realizability` ∈ `CHECKED | UNCHECKED` — whether displayed counterexamples were tested for
  realizability in a single world (Part I's two-fixpoint shortcut quantifies over a superset of
  worlds; an `UNCHECKED` witness may depict an impossible attack and must render as such).

### 68.2.5 `atoms`, `cut`, masks

```json
"atoms":{"n":41,"assign":[["egress_seg",1,0],["egress_seg",2,1],["session_binding",1,2]]}
```

Each triple is `[control_id, level, bit]`. `n` ≤ 64. Bit assignment is derived deterministically
from `controls.toml` (documented order) and is hashed into `controls_hash`. All 64-bit masks are
encoded as fixed-width lowercase hex strings `"0x0000000000000021"` — never as JSON numbers.

### 68.2.6 `flags`, `budgets`, `derived`

```json
"flags":{"grounding_capped":false,"corridor_capped":false,"greedy_cover":false,
         "er_ambiguous":false,"license_voided_by_backdating":false,"tuned_scenario":false}
"budgets":{"fixpoint_steps":183044,"bb_nodes":9117,"step_budget":2000000,"budget_exhausted":false}
```

OVERRIDES Part I: budgets are **deterministic step counters**, never wall-clock timeouts. A
wall-clock budget makes flags machine-dependent and destroys byte-identical replay.

`derived` (redundancy index, decisive observation set, Pareto frontier) is **absent**, not
zeroed, whenever `grounding_capped` or `corridor_capped` is set; the emitter must omit it and
the checker rejects a certificate that carries it alongside those flags (`E-FLAG-DERIVED`).
`residual` inside a frontier point is a **set** — `{"goal_atoms":[…],"open_corridors":[…]}` —
never a scalar. A scalar residual is `E-FLAG-SCALAR`.

============================================================

## 68.3 SCF: canonical serialization rules

A `.spcert` is canonical iff re-serializing its parsed value reproduces the input bytes exactly.
The checker performs that comparison as obligation O0. Rules:

* **C1** UTF-8 only. Reject overlong encodings, lone surrogates, `U+0000`, and any codepoint in
  `Cc`/`Cf` other than none (control characters are banned outright in strings).
* **C2** Strings are NFC-normalized at emit; the checker rejects any string not already NFC
  (`E-CANON-NFC`). No normalization is performed by the checker.
* **C3** Object member names are ASCII `[a-z0-9_]+`, sorted by byte value, **unique**. A
  duplicate key is `E-CANON-DUPKEY` and is detected during parsing, before value construction.
* **C4** No insignificant whitespace anywhere. No `\t`, no indentation, no space after `:` or `,`.
* **C5** Escapes: only `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f`, and `\u00XX` for other C0. No
  `\uXXXX` form is permitted where the character is directly representable (`E-CANON-ESCAPE`).
* **C6** **No floating point.** `.`, `e`, `E`, `-0`, `Infinity`, `NaN` in a number position are
  `E-CANON-FLOAT`. This is a lexical ban, checked by the tokenizer.
* **C7** Integers appear only where the field table declares `u8`, `u16` or `u32`. They are
  decimal, no leading `+`, no leading zeros (except the single digit `0`), and must lie inside
  the declared width. Anything wider (masks, seeds, i64 nanosecond timestamps) is a **string**:
  masks and seeds as `0x`-prefixed fixed-width lowercase hex, timestamps as decimal `i64` text.
  Rationale: JSON numbers above 2^53 are not interoperably representable, and a 64-bit value
  that round-trips through a double is a forged value.
* **C8** No JSON object is used as a map with data-dependent keys. Every collection is an
  **array of records sorted by a declared total key**. There is no place in the format where
  iteration order of a hash map can leak into bytes.
* **C9** Arrays declared sorted must be strictly ascending under the declared comparator;
  equal-key neighbors are `E-CANON-ORDER`.
* **C10** `null` is not a value in this format. Optionality is expressed by member absence.
* **C11** Booleans are `true`/`false` literals. Enums are exact literal strings from a closed set.
* **C12** **Strict fields.** Unknown members reject (`E-SCHEMA-UNKNOWN`); missing required members
  reject (`E-SCHEMA-MISSING`). There is no forward-compatible ignore rule at MAJOR 1.
* **C13** Nesting depth ≤ 8; array length ≤ 2^24 per array; string length ≤ 4096 bytes
  (normative limits, not measurements). Violations are `E-LIMIT-*`.
* **C14** The file is **never compressed**. If the first two bytes match a known compression
  magic (`1f8b`, `28b5`, `504b`, `425a`, `fd37`), the checker rejects with `E-LIMIT-COMPRESSED`
  and does not decompress. Transport-layer compression is the caller's problem; the checker
  refuses to be a decompressor.

Both the Rust emitter and the Go checker ship an SCF encoder. `make scf-differential` fuzzes a
random in-memory `Body` through both encoders and fails on any byte difference.

============================================================

## 68.4 What `rules_hash` covers, and why

**Decision: `rules_hash` covers the canonical AST encoding (CAE), not raw file bytes.**
OVERRIDES Part I: Part I left `hashes.rules` undefined, which the critics flagged as an
unresolved choice between "a comment invalidates every certificate" and "an unspecified AST
encoding".

Justification:

1. A raw-byte hash makes the certificate hostage to formatting. Reflowing a comment invalidates
   every archived certificate and every golden hash in the demo transcript, which creates
   standing pressure to disable the check.
2. The object the verdict actually depends on is the AST. Hashing the AST makes the hash a
   statement about semantics.
3. The CAE is computed **independently in Rust and in Go** from the same text. Hash agreement is
   therefore also the strongest available evidence that the two rule-language front ends agree,
   and it is the cheapest part of the independence gate (§68.6).

The risk the raw-byte hash would have avoided — a canonicalizer that erases a semantic
difference — is discharged by three gates:

* `cert-cae-roundtrip`: property test, `decode(CAE(r)) == r` for randomly generated rule tables.
* `cert-cae-mutation`: for every single-token semantic mutation of every fixture rule file
  (rename a head, drop a body literal, flip a `silent_possible`, change a guard operator, change
  a `producing_sources` entry, change a blocker level), the CAE hash must change. An unchanged
  hash fails the build and names the mutation.
* `cert-cae-insensitivity`: for comment edits, whitespace edits, TOML key reordering and integer
  formatting (`0x10` vs `16`), the CAE hash must **not** change.

CAE grammar (prefix-length-delimited, no separators, no text):

```
cae        := "CAE1" u32(rule_count) rule*                 ; rules sorted by rule_id
rule       := u16(rule_id) atom(head) u8(n) atom{n}         ; body atoms sorted lexicographically
              guard u8(n_src) srcid{n_src}                  ; sources sorted ascending
              u8(silent_possible) u64le(blocker_mask)
atom       := u8(len) bytes(len)                            ; NFC UTF-8 predicate symbol
guard      := u8(tag) guard_payload                         ; postfix, tags from the guard spec
srcid      := u16
```

`rules_text_hash` is recorded but never enforced. When `rules_hash` matches and
`rules_text_hash` differs, the checker prints
`NOTE: rules text differs from emitter's copy; canonical AST identical` and continues.

============================================================

## 68.5 Compatibility policy (Rust emitter ↔ Go checker)

| Change | MAJOR | MINOR | Checker behavior |
|---|---|---|---|
| Add an optional field | no | yes | Older checker rejects (`E-SCHEMA-UNKNOWN`). Emitter must raise `min_checker`. |
| Add a required obligation | yes | — | Older checker rejects on `min_checker`. |
| Remove or rename a field | yes | — | |
| Widen an integer field | yes | — | Silent widening is a forgery vector. |
| Add an enum variant | yes | — | Closed enums only. |
| Tighten a limit in §68.3 | no | yes | |
| Fix a checker bug with no format change | no | no | Checker patch version, not in the format. |

Rules:

* The checker accepts exactly the MAJOR it was built for. No multi-MAJOR checker binary exists.
* `make cert-compat` runs the current checker against every certificate in
  `fixtures/certs/archive/<version>/` and asserts the recorded accept/reject verdict per file.
  Archived certificates are never regenerated to make a new checker pass; a new MAJOR gets a new
  archive directory and the old one is kept and still checked by the old pinned checker binary.
* The Go checker and the Rust emitter each carry a copy of the field table generated from one
  checked-in `cert-schema.toml`; `make cert-schema-sync` fails if either generated file is stale.
  The schema table is *data*, not guard semantics: this sharing is declared in
  `docs/checker-scope.md` and does not make the two grounders non-independent.

============================================================

## 68.6 Checker obligations, in order

Run in exactly this order. Stop at the first failure and report its code. Each obligation may
assume every earlier one passed.

```
O0  canonicity      re-serialize parsed body; bytes must equal input          E-CANON-*
O1  cert_hash       blake3(canonical body) == cert_hash                       E-HASH-CERT
O2  schema          v, min_checker, profile admissible                        E-SCHEMA-*
O3  scope           scope complete; scope hashes == inputs hashes             E-SCOPE-*
O4  inputs          recompute each hash in §68.2.3 over files given on argv   E-INPUT-*
O5  atoms           n<=64; assign matches controls_hash bit table; bits uniq  E-ATOM-*
O6  cut             sorted, unique, upward-closed under x_{k,l+1} -> x_{k,l}  E-CUT-*
O7  invariant       U sorted/unique; every axiom fact in U                    E-INV-*
O8  closure         forall inst: body subset U and (blockers & S)==0 -> head in U   E-CLOSURE
O9  goals           per goal atom g: g not in U  (SAFE case)                  E-GOAL-*
O10 licenses        every silent inst cites a license implied by liveness.json E-LICENSE-*
O11 ghost           observed_event_count excludes all silent instances        E-GHOST-COUNT
O12 witnesses       well-founded; leaves are real EventIds; derives goal under S\{c} E-WITNESS-*
O13 psi-hit         cut hits every clause of psi                              E-PSI-HIT
O14 flags           flag algebra (§68.7)                                      E-FLAG-*
O15 minimality      per verdict.minimality, §68.6.2                           E-MIN-*
```

### 68.6.1 The linear-pass argument, stated honestly

OVERRIDES Part I: Part I §5 claimed the checker "checks in one pass" including the no-smaller-cut
obligation. That is false. O0–O14 are linear; **O15 is not**, and it is fenced separately.

| Obligation | Cost | Why linear |
|---|---|---|
| O0, O1 | `O(F)` bytes | one streaming parse, one streaming re-encode, `blake3` incremental |
| O2–O6 | `O(\|A\|)` | fixed-size structures; sortedness verified in one scan, never repaired |
| O7 | `O(\|U\|)` | one scan verifies strict ascending order and axiom membership |
| O8 | `O(Σ\|body\|)` | Dowling–Gallier: one unsatisfied-body counter per instance; U is a sorted array indexed by a perfect hash built in `O(\|U\|)`; each body literal touched once |
| O9 | `O(\|G\| log \|U\|)` | binary search per goal; `\|G\|` is bounded by the goal library entry |
| O10 | `O(\|L\| + \|silent\|)` | licenses sorted by `(source,t0,t1)`; silent instances sorted by `license_id`; one merge scan |
| O11 | `O(\|silent\|)` | counter comparison |
| O12 | `O(Σ\|witness\|)` | post-order walk; EventId membership via the bundle's sorted index |
| O13 | `O(\|Ψ\| · ⌈\|A\|/64⌉)` = `O(\|Ψ\|)` | one `AND` per clause against the cut mask |
| O14 | `O(1)` | |

Total for O0–O14: `O(F + Σ|body| + Σ|witness| + |Ψ| + |L|)`. Single pass in the sense that no
structure is traversed more than a constant number of times and nothing is sorted.

**The checker never sorts.** Sorting would mask an emitter that emits in hash-map order, which is
exactly the determinism defect the charter section forbids.

**The checker never allocates from a declared count.** It allocates from observed array length,
then compares to any declared count and rejects on mismatch (`E-LIMIT-COUNT`). A `count` field
claiming 2^24 entries can therefore not cause an allocation.

### 68.6.2 O15, minimality

* `minimality: EXACT` — the checker must independently run a fixpoint for **every** cut of
  cardinality `|S|-1` over the upward-closed atom lattice. Permitted only when
  `C(n, |S|-1) <= 200000` (normative limit, not a measurement); above that the emitter must not
  claim `EXACT`. Cost `O(C(n,|S|-1) · Σ|body|)`, and it is reported separately in the transcript.
* `minimality: PSI_RELATIVE` — the checker verifies only that no cut of size `< |S|` hits all of
  Ψ. This establishes nothing about cuts outside Ψ. The checker's own output must print
  `minimality: PSI_RELATIVE (no claim that a smaller sufficient cut does not exist)`.
* `SUBSET` / `UNVERIFIED` — no minimality obligation; the checker prints the absence of a claim.

Forbidden string: the checker, the API and the UI may never print "no smaller cut exists" on a
non-`EXACT` certificate. `make claims-lint` greps for it.

============================================================

## 68.7 Flag algebra (checker-enforced)

```
safety == ROBUST  requires  no flag in {grounding_capped, corridor_capped, er_ambiguous,
                                        license_voided_by_backdating, budget_exhausted,
                                        tuned_scenario} is set
derived present   requires  not grounding_capped and not corridor_capped
realizability == UNCHECKED requires every witness carries "display": "ghost_unrealizable"
minimality == EXACT requires the exhaustive obligation was run and recorded in budgets
```

A certificate violating any implication is rejected. The algebra is implemented once, in a
generated table from `cert-schema.toml`, and a mutation test flips each implication and asserts
the checker goes red.

============================================================

## 68.8 Adversarial certificate corpus

`fixtures/certs/adversarial/` is checked in. Every file is byte-frozen. `make cert-corpus` runs
`spectra verify` over the whole corpus and asserts the **exact** reason code per row. A wrong
code is as much a failure as a wrong verdict, because a generic rejection hides which obligation
actually fired.

| # | File | Mutation | Must reject with |
|---|---|---|---|
| 01 | `tampered_cut.spcert` | one atom removed from `cut`, everything else untouched | `E-CLOSURE` |
| 02 | `invented_invariant.spcert` | `invariant.U` extended with a fabricated fact hash | `E-CLOSURE` |
| 03 | `shrunk_invariant.spcert` | axiom fact deleted from `U` | `E-INV-AXIOM` |
| 04 | `goal_in_u.spcert` | goal atom present in `U` but `safety:ROBUST` | `E-GOAL-MEMBER` |
| 05 | `witness_phantom_event.spcert` | witness leaf cites an EventId absent from the bundle | `E-WITNESS-EVENT` |
| 06 | `witness_cyclic.spcert` | witness tree contains a cycle | `E-WITNESS-CYCLE` |
| 07 | `witness_wrong_cut.spcert` | witness derives goal under `S`, not `S\{c}` | `E-WITNESS-CUT` |
| 08 | `unlicensed_silent.spcert` | silent instance cites a license not implied by `liveness.json` | `E-LICENSE-UNIMPLIED` |
| 09 | `license_window_widened.spcert` | license `t1` extended by one tick past the blind window | `E-LICENSE-WINDOW` |
| 10 | `ghost_counted.spcert` | `observed_event_count` includes GHOST instances | `E-GHOST-COUNT` |
| 11 | `truncated_psi.spcert` | last 40% of corridor clauses removed to shrink the cut | `E-PSI-HIT` |
| 12 | `psi_unsorted.spcert` | clause array reordered | `E-CANON-ORDER` |
| 13 | `hash_mismatch_rules.spcert` | `inputs.rules_hash` points at a different rule table | `E-INPUT-RULES` |
| 14 | `hash_mismatch_cert.spcert` | one byte of `body` flipped, `cert_hash` stale | `E-HASH-CERT` |
| 15 | `scope_stripped.spcert` | `scope.licenses` removed | `E-SCHEMA-MISSING` |
| 16 | `scope_mismatch.spcert` | `scope.controls` disagrees with `inputs.controls_hash` | `E-SCOPE-BIND` |
| 17 | `bounds_overflow.spcert` | `budgets.fixpoint_steps` = `4294967296` | `E-CANON-WIDTH` |
| 18 | `negative_count.spcert` | `atoms.n` = `-1` | `E-CANON-WIDTH` |
| 19 | `atom_overflow.spcert` | `atoms.n` = `65` | `E-ATOM-BUDGET` |
| 20 | `mask_as_number.spcert` | blocker mask emitted as a JSON number | `E-CANON-FLOAT` / `E-CANON-WIDTH` |
| 21 | `float_smuggled.spcert` | `"residual":0.97` | `E-CANON-FLOAT` |
| 22 | `duplicate_keys.spcert` | `"cut"` appears twice, second one smaller | `E-CANON-DUPKEY` |
| 23 | `version_downgrade.spcert` | v1.1 body relabeled `"v":"1.0"` | `E-SCHEMA-MISSING` |
| 24 | `min_checker_bump.spcert` | `min_checker:"9.0"` | `E-SCHEMA-DOWNGRADE` |
| 25 | `unknown_field.spcert` | `"trust_me":true` added | `E-SCHEMA-UNKNOWN` |
| 26 | `zip_bomb.spcert` | 8 GiB of zeros compressed to 900 KiB, gzip magic | `E-LIMIT-COMPRESSED` |
| 27 | `oversized.spcert.part` | 65 MiB of valid-looking canonical JSON | `E-LIMIT-SIZE` |
| 28 | `deep_nesting.spcert` | 4096-deep nested arrays in `derived` | `E-LIMIT-DEPTH` |
| 29 | `count_lies.spcert` | declared `psi.count` = 2^24, actual array length 3 | `E-LIMIT-COUNT` |
| 30 | `flagged_robust.spcert` | `grounding_capped:true` with `safety:ROBUST` | `E-FLAG-ROBUST` |
| 31 | `derived_under_cap.spcert` | `corridor_capped:true` with `derived` present | `E-FLAG-DERIVED` |
| 32 | `scalar_residual.spcert` | frontier point with a scalar `residual` | `E-FLAG-SCALAR` |
| 33 | `exact_unearned.spcert` | `minimality:EXACT` with no exhaustive budget recorded | `E-MIN-UNEARNED` |
| 34 | `nfc_homoglyph.spcert` | control name uses a decomposed form to alias another atom | `E-CANON-NFC` |
| 35 | `null_value.spcert` | `"derived":null` | `E-CANON-NULL` |
| 36 | `trailing_bytes.spcert` | valid certificate followed by a second JSON object | `E-CANON-TRAILING` |

`fixtures/certs/positive/` holds at least three certificates that must be **ACCEPTED**: one
`ROBUST/EXACT`, one `ROBUST/PSI_RELATIVE`, one `UNSAFE` with witnesses. Without these the corpus
could be passed by a checker that rejects everything — the same one-sided-gate defect the critics
found in the zero-false-ROBUST invariant. OVERRIDES Part I: every negative corpus in SPECTRA
carries positive controls.

**Reason-code liveness.** `make cert-corpus` additionally asserts that every reason code declared
in `checker/codes.go` is produced by at least one corpus file. An unreachable code fails the
build: either the obligation is untested or it is dead.

**Provenance of corpus files.** Each adversarial file is produced by a committed mutation script
(`fixtures/certs/mutate/NN_*.py`) from a named positive certificate, so a schema change can
regenerate the corpus deterministically. The mutation scripts are inputs; the `.spcert` bytes are
the frozen artifacts, and a regenerated file that differs from the frozen bytes fails CI unless
the change is recorded in the corpus changelog.

============================================================

## 68.9 Fuzzing the checker

Coverage-guided fuzzing is a CI job with a committed corpus. Targets:

| Target | Harness | Corpus | Invariant |
|---|---|---|---|
| `FuzzVerify` | Go native (`go test -fuzz`) | `checker/testdata/fuzz/FuzzVerify/` seeded from §68.8 plus all positive certificates | never panics; always terminates; peak heap under the declared ceiling; **never ACCEPTs input whose bytes differ from the canonical re-encoding of its parse** |
| `FuzzSCFRoundTrip` | Go native | shared | `encode(decode(b)) == b` whenever `decode` succeeds |
| `fuzz_cae` | Rust `cargo-fuzz` / libFuzzer | `kernel/fuzz/corpus/cae/` | CAE encoder total, no panic, no `unsafe` |
| `fuzz_scf_differential` | Rust harness driving both encoders through a shared FFI-free file boundary | shared | Rust and Go canonical bytes identical |
| `fuzz_guard_differential` | drives Rust and Go guard evaluators over random control assignments | `kernel/fuzz/corpus/guard/` | identical results; a divergence is a build-red independence failure |

Policy:

* Per-PR: each target runs for a short fixed budget over the committed corpus only (regression
  mode, `-runs=` bounded, deterministic).
* Nightly: coverage-guided mode with a wall-clock budget. Wall clock here is a CI scheduling
  parameter, never a decision path in the kernel or the checker.
* Any crash, hang, OOM or ACCEPT-of-non-canonical is a build failure. The minimized input is
  committed to the corpus **in the same PR as the fix**, and a row is added to §68.8 with its
  reason code.
* The corpus is committed, not regenerated. `make fuzz-corpus-check` asserts every corpus file is
  still parsed (successfully or with a known code) and that none has become a crasher.
* Fuzzing runs with the checker built under `-race` for `FuzzVerify` and with ASan for the Rust
  targets.

============================================================

## 68.10 CLI contract

```
$ spectra verify out/run-91c2/cert.spcert \
    --rules rules.toml --controls controls.toml --goal goals/priv-esc-1.toml \
    --bundle out/run-91c2/bundle.jsonl --liveness out/run-91c2/liveness.json \
    --er out/run-91c2/er.json
spectra-verify 1.0.3  (schema 1.0, offline, no network)
O0  canonical form                  ok
O1  cert_hash blake3:3f9a1c…        ok
O2  schema 1.0, min_checker 1.0     ok
O3  scope binding complete          ok
O4  inputs: rules ast ok, controls ok, bundle ok, liveness ok, goal ok, er ok
    NOTE: rules text differs from emitter's copy; canonical AST identical
O5  atoms 41/64, bit table matches   ok
O6  cut {egress_seg>=1, session_binding>=2} sorted, upward-closed   ok
O7  invariant U: 9,914 facts, axioms present                        ok
O8  closure: 2,104 instances, 0 violations                          ok
O9  goal atoms 3/3 unreachable                                      ok
O10 licenses: 4 used, all implied by liveness.json                  ok
O11 ghost accounting: 37 silent instances, 0 counted as observed    ok
O12 witnesses: 2/2 re-derive goal under S\{c} from real EventIds    ok
O13 psi: 6 corridors, all hit by cut                                ok
O14 flag algebra                                                    ok
O15 minimality: PSI_RELATIVE (no claim that a smaller sufficient cut does not exist)
ACCEPT  ROBUST(rules@3f9a1c, catalog@a11c40, licenses@7d20be, er@c4b8f1, non-adaptive)
        minimality=PSI_RELATIVE  realizability=CHECKED  flags=none
```
(all figures in this transcript are illustrative, not a target)

```
$ spectra verify fixtures/certs/adversarial/11_truncated_psi.spcert …
O13 psi: 4 corridors, cut misses corridor #3 {credential_rotation>=1, iam_audit>=1}
REJECT  E-PSI-HIT  obligation O13
        the published cut does not hit every clause of the published corridor database
exit 1
```

Exit codes: `0` ACCEPT, `1` REJECT (reason code on stderr and in `--json`), `2` usage or I/O
error. `--json` emits a canonical JSON report; the report is not a certificate and carries no
`cert_hash`. There is no `--force`, no `--skip`, no `--ignore-hash-mismatch` flag; adding one is
a review-blocking change.

============================================================

## 68.11 Gates

| Gate | make target | Proves |
|---|---|---|
| Corpus | `make cert-corpus` | all 36 adversarial files rejected with the exact code; positives accepted; every reason code reachable |
| Canonicity | `make cert-canon` | round-trip and byte-equality over every fixture; SCF differential Rust↔Go |
| CAE | `make cert-cae` | round-trip, mutation-sensitivity, formatting-insensitivity |
| Compatibility | `make cert-compat` | archived certificates verify as recorded |
| Schema sync | `make cert-schema-sync` | generated Rust and Go field tables match `cert-schema.toml` |
| Offline | `make verify-offline` | `go list -deps ./checker/...` contains none of `net`, `net/http`, `database/sql`, `os/exec`, `plugin`; and the checker passes the corpus while run in an empty network namespace with Postgres and Redis stopped |
| Fuzz regression | `make fuzz-cert` | committed corpus produces no crash, hang or non-canonical ACCEPT |
| Mutation liveness | `make cert-mutation` | each injected checker bug (skip O8, accept unsorted `U`, ignore `E-FLAG-ROBUST`, widen a license window by one tick) turns a named gate red |
| Claims | `make claims-lint` | forbidden strings of §68.12 absent outside registered entries |

============================================================

## 68.12 Negative requirements and forbidden claims

The build fails if any of the following is present.

1. Any floating-point literal or type in the certificate schema, the emitter's certificate
   module, or the checker.
2. Any `HashMap`/`map[...]` iteration that reaches certificate bytes, in either language.
3. Any wall-clock timestamp, hostname, username, absolute path, process id, or duration inside
   `body`. Timings belong in the run manifest, which is not hashed into the certificate.
4. Any network, database, Redis, or subprocess dependency reachable from `spectra verify`.
5. Any decompression performed by the checker.
6. Any checker flag that weakens an obligation.
7. Any sort, dedup, normalization, or field-defaulting performed by the checker on input.
8. Any allocation sized from an attacker-declared count.
9. Any confidence, probability, severity or score field, in the certificate, the checker report,
   the API, or the database.
10. Any aggregate verdict across goals. Verdicts are per goal atom.

Forbidden claims — these sentences may never be emitted by the checker, printed in the UI, or
written in docs or README:

* "Formally verified" / "proven secure" / "guaranteed" about any real system.
* "No smaller cut exists" on a certificate whose `minimality` is not `EXACT`.
* "The attack would have been stopped." The certificate supports "this cut severs every chain
  derivable in this model under this catalog", nothing stronger.
* "Independently verified" without naming the scope in `docs/checker-scope.md`. An ACCEPT
  establishes that the certificate is internally consistent with the hashed inputs; it does not
  establish that the rule table models reality, that entity resolution was correct, that the
  control catalog is complete, or that grounding found every instance. A shared misreading of a
  guard by both front ends is invisible to the checker and must be listed as such.
* Any statement that an ACCEPT covers the bundle's truthfulness. The bundle is an input, and
  `bundle_hash` binds which bytes were used, not whether they were honest.
