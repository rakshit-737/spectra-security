# C++ - deterministic entity-key interner on the ingest hot path
Tier: B
Status: not started
Owning spec section: 73 (Part II), which supersedes Part I section 31.8
Milestone: M9 - Polyglot surface and performance

## The promise

A second implementation of the entity-key interner, written in C++, run over the same keys as the
Rust interner and timed against it. Part II section 73.1 states the promise as "a measured
alternative interner, published whether or not it wins". The artifact is the comparison. The
outcome is whatever the run prints.

The same Tier B honesty requirement that governs the C scanner governs this directory: if the Rust
interner is faster, `docs/bench/ingest.md` says so, this directory stays because it is the
comparison arm, and no document claims a speedup. Nothing has been measured. There is no number
here.

The differential half of the promise is about determinism rather than speed. Interning assigns a
dense integer to each distinct entity key, and the assignment must be a function of the input
sequence alone - Part II section 58 forbids hash-map iteration order in any output path. Two
independently written interners that produce the same assignment over the same input make an
ordering dependency visible. One interner makes it invisible until a run on a different machine
disagrees with a golden file.

Explicitly not promised: anything about entity resolution quality, which is measured by the ER
gates of Part II section 60 against ground truth and has nothing to do with which language interned
the key; and any claim that C++ is the faster language for this job.

## What lives here

No file in this list exists yet.

- C++20 sources implementing the interner: a key-to-id table with a declared, ordered iteration
  contract and a documented collision and growth policy.
- A narrow C-ABI boundary header, so the differential harness can drive both implementations without
  either one linking the other.
- A CMake build with `-Werror` and a sanitizer configuration for the debug profile.
- Unit tests, including the case the determinism charter cares about: the same key multiset
  presented in a different arrival order must produce the assignment the contract declares, and
  nothing else.
- A differential harness that replays a committed key stream through both interners and emits the
  id assignment in a canonical, line-oriented form.
- The golden id assignment the differential test compares against.
- A benchmark harness writing to the published artifact path with a run manifest attached.
- This component's fragment of `polyglot.toml`, with every field Part II section 73.4 requires,
  committed before the first source file.

## Consumer edge

The declared consumer is the Rust-side differential test over the two interners, owned by the
ingest or kernel component and not by this one, plus the interner row of the published ingest
benchmark. Part II section 73.3.1 requires the consumer to be owned by a different component;
`consumer.owned_by` equal to this component's own id fails the audit with `SELF_CONSUMING`.

If this directory is deleted, ingest keeps working and entity resolution keeps resolving. The Rust
interner is the one on the product path. What breaks is the differential test, which loses its
second arm and cannot resolve, and the interner comparison in `docs/bench/ingest.md`, which loses
the data `make reproduce` regenerates it from. That edge is a gate and a published artifact. It is
not a product outage, and this file will not describe it as one.

## How it is exercised

- CI job: `polyglot-b / entity-interner-cpp`, following the `polyglot-<tier> / <component-id>`
  naming that Part II section 73.4 fixes for the C component in the same tier. The exact id is not
  yet written into `polyglot.toml`.
- Tier: T1 on changed paths per Part II section 73.9; T2 nightly for the full run plus the mutation
  leg, on the `spectra/toolchain-b` image that Part II section 74.1 gives clang and gcc.
- Component entrypoint: `make -C cpp/entity_interner bench`, in the shape Part II section 73.4 uses
  for the C component.
- Audit: `make polyglot-audit`.
- Published comparison: `make bench`, re-derived offline by `make reproduce`.

## Mutation check

Operator `reorder_output(seed)` from the closed set in Part II section 73.5, applied to this
component's output in a scratch worktree: the emitted id-assignment lines are permuted under a
seeded shuffle. Because the interner's whole contract is that the assignment is a deterministic
function of the input sequence, a permuted assignment is a real corruption of the thing being
compared.

The gate that must go RED is `polyglot-b / entity-interner-cpp`, at the assertion that compares the
two interners' assignments in order. If a seeded permutation leaves that gate green, the comparison
is order-insensitive, which means it is not checking the property the component exists to check,
and the component is PADDING under Part II section 73.6.

A second candidate operator is `constant_result`, collapsing every distinct key to one id. That is
mandatory for Tier B oracles and Tier D cross-checks under Part II section 73.5, and this component
is a measured alternative rather than an oracle, so it is not mandatory here. It is listed because
if `reorder_output` turns out not to be applicable to the chosen output form, `constant_result`
is the fallback and the choice has to be recorded, not assumed.

The operator, the seed and the fully qualified `expect_red` assertion are not yet fixed. Part II
section 73.4 requires all three in `polyglot.toml` before the first source file, and an `expect_red`
that does not name both a job and a specific assertion fails the lint with
`MUTATION_UNDERSPECIFIED`.

## Not yet decided

- **The directory path.** Part II did not restate it. Part I section 31.8 placed C++ at
  `native/pcap-flow/`, doing offline pcap flow reassembly and interval-tree liveness windows; Part
  II section 59 forbids `libpcap`, `tshark` and any binary capture parser as an ingest dependency,
  which kills that role and the directory with it. `cpp/entity_interner/` is the working path from
  the Part II roster and is not fixed by any Part II sentence. Alternatives are
  `native/entity_interner/`, keeping the `native/` root that Part I section 31.1's directory map
  still shows, or a subdirectory under the ingest crate's FFI boundary. This must be decided before
  the first source file, because Part II section 73.4's `paths` glob and the `ORPHAN_SOURCE` and
  `AMBIGUOUS_OWNERSHIP` lints all key on it.
- **Which key is interned.** The generator's pre-resolution canonical `entity_key` of Part II
  section 62.1.2 and the entity-resolution representative of Part II section 60 are different
  objects. The differential has to name one of them, and the choice decides whether this component
  sits before or after ER.
- **The call boundary.** In-process FFI, or a separate binary over content-addressed JSON. Part II
  section 75 rung D4 keeps a subprocess and content-addressed JSON kernel boundary and deletes
  abstraction layers such as pyo3 and cgo, which argues for the subprocess shape, but that rung is
  about the kernel boundary and not obviously about this one.
- **The Part I interval-merge engine.** Part I section 31.8 also gave C++ an interval tree computing
  per-source liveness windows. Part II section 73.1 names only the interner. Whether the interval
  work moved into the Rust liveness pass or was dropped is not stated anywhere.
- **The per-PR tier**, for the same reason as the C component: Part II section 73.9 and Part II
  section 74.4 place Tier B differentials differently, and the split is a reading rather than a
  ruling.
