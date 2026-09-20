============================================================
58. DETERMINISM AND REPRODUCIBILITY CHARTER
============================================================

This section is a contract, not an aspiration. Part I asserted "byte-identical replay" in its
preamble and then left every mechanism that would produce it unowned. Part II makes it a
mechanism. Every requirement below states what "done" looks like and which gate proves it.

OVERRIDES Part I: wherever Part I permits a wall-clock timeout, a float, an unordered-collection
iteration, an ambient clock read, a locale-dependent comparison, or an unpinned thread count in
any path that can change a printed artifact, that permission is revoked. The rules here win.

Scope word used throughout: a **decision path** is any code path whose execution can change the
bytes of a hashed artifact — `liveness.json`, the fact base, the hypergraph, `Psi`, a cut, a
certificate, a run manifest, a golden fixture, or any number that reaches `docs/`. Everything
else (UI layout, log prettification, progress bars, plot rendering) is a **presentation path**.
Presentation paths may not feed values back into decision paths. There is no third category.


58.1 THE ONE CLOCK: TIMESTAMP TYPE AND WIDTH
------------------------------------------------------------

OVERRIDES Part I: sections 17-19 (temporal) and 25 (kernel) are hereby bound to a single time
type. Any Allen-interval or string-timestamp representation in those sections is a derived view,
never a stored or hashed value.

1. The one physical timestamp type is `i64` nanoseconds since 1970-01-01T00:00:00Z, no leap
   seconds, no timezone field, no offset field. It is named `TsNanos` in every language:

   ```
   Rust:       #[repr(transparent)] pub struct TsNanos(pub i64);
   Go:         type TsNanos int64
   Python:     TsNanos = NewType("TsNanos", int)        # int, never float, never datetime
   TypeScript: type TsNanos = bigint;                    // never number
   Haskell:    newtype TsNanos = TsNanos Int64
   C:          typedef int64_t ts_nanos_t;
   SQL:        BIGINT NOT NULL                           -- never TIMESTAMP, never TIMESTAMPTZ
   ```

2. Forbidden as stored or hashed time representations: `float`/`double` seconds, `time.Time`,
   `datetime`, JS `number` milliseconds, `NUMERIC`, RFC 3339 strings, monotonic clock readings,
   and any value carrying a timezone. RFC 3339 exists only at the ingest boundary (parsed to
   `TsNanos` exactly, with a reject-on-loss rule) and at the presentation boundary (formatted
   from `TsNanos` with a pure function, always in UTC, always `%Y-%m-%dT%H:%M:%S.%9NZ`).

3. Representable range is clamped to `[0, 4102444800000000000)` (1970-01-01 to 2100-01-01).
   A record outside this range is quarantined with reason code `TS_OUT_OF_RANGE` per the
   ingestion section. It is never silently clamped, because a silent clamp manufactures a gap
   and therefore manufactures a license.

4. Durations are `i64` nanoseconds (`DurNanos`). Subtraction of `TsNanos` is checked; overflow
   is a hard error, never a wrap.

5. No component may read the system clock inside a decision path. The only permitted clock reads
   are: (a) the run manifest's `environment.started_at_wall`, which is excluded from every hash;
   (b) benchmark timers in the bench harness, which produce no input to any decision. A lint
   (58.6) fails the build on `SystemTime::now`, `time.Now`, `datetime.now`, `Date.now`,
   `getTimeOfDay`, `clock_gettime` outside an allowlisted file list committed at
   `tools/lint/clock-allowlist.txt`.

6. `TZ=UTC` and `LC_ALL=C` are set in every Dockerfile, every CI job, every devcontainer and the
   `Makefile` itself (`export TZ := UTC`, `export LC_ALL := C`). A gate asserts both are set
   inside the toolchain image and that a run launched with `TZ=Asia/Kolkata` still produces the
   identical certificate hash.


58.2 TICK DISCRETIZATION
------------------------------------------------------------

OVERRIDES Part I: "time-indexed fact" is now defined. Part I left the index unspecified, which
made grounding and `t+1` expiry semantics ill-defined.

1. A **tick** is a fixed-granularity integer index, not a rank over observed timestamps. Rank
   discretization is forbidden: it makes tick identity depend on which events survived
   degradation, so deleting one event would renumber the whole fact base.

2. `tick_nanos` is declared once per scenario in `scenario.toml`, is hashed into the certificate,
   and must be one of exactly `{1_000, 1_000_000, 1_000_000_000}` (microsecond, millisecond,
   second). No other value parses. The default committed for fixtures is `1_000_000`.

3. Discretization rule, floor toward negative infinity, no rounding, no banker's rounding:

   ```
   fn tick_of(t: TsNanos, tick_nanos: i64) -> TickId {
       debug_assert!(t.0 >= 0);
       TickId((t.0 / tick_nanos) as u32)          // exact, integer division, t >= 0 enforced
   }
   ```

4. `TickId` is `u32`. The horizon `k` in `goal.toml` is measured in **ticks**, never in seconds,
   never in "steps". Renaming it is forbidden; the glossary section owns the word.

5. Two events in the same tick are still totally ordered by 58.3. A tick is a fact index, not an
   event ordering device.

6. Granularity-invariance property test (build gate `make test-tick-invariance`): for every
   fixture, grounding at `tick_nanos = 1_000_000` and at `1_000` must produce the same set of
   derived predicate-argument pairs modulo tick rescaling, for every rule whose guards contain no
   window shorter than 2 ticks at the coarser granularity. Rules that do contain such a window
   are listed in `rules/granularity-sensitive.txt`, must carry a written justification, and the
   test asserts exactly that list, so adding a sensitive rule silently is impossible.


58.3 THE TOTAL ORDER ON EVENTS AND THE TIE-BREAK CHAIN
------------------------------------------------------------

1. Define `EventKey` as the 5-tuple below. The comparison is lexicographic over the tuple, and
   the chain is total by construction because component 5 is unique per bundle.

   | # | Component        | Type          | Ordering rule                                        |
   |---|------------------|---------------|------------------------------------------------------|
   | 1 | `t_nanos`        | `i64`         | ascending, raw nanoseconds (NOT the tick)            |
   | 2 | `source_id`      | `[u8;32]`     | ascending byte-lexicographic BLAKE3 of source name   |
   | 3 | `seq`            | `u64`         | ascending; unchained sources use `SEQ_ABSENT = u64::MAX` |
   | 4 | `content_hash`   | `[u8;32]`     | ascending byte-lexicographic, BLAKE3-256 of canonical record |
   | 5 | `line_ordinal`   | `u64`         | ascending, 0-based line index in `bundle.jsonl`      |

2. String comparison anywhere in the order is **byte-lexicographic over UTF-8**, never
   locale-aware, never case-folded, never normalized at compare time. Unicode normalization
   (NFC) happens once at ingest; after ingest all strings are opaque bytes.

3. `EventId` is assigned as the 0-based rank in this order, computed after the whole bundle is
   read. `EventId` is therefore a pure function of the bundle contents. It is not an ingest
   counter, not a database sequence, and not stable across bundles. A gate asserts that shuffling
   the physical lines of `bundle.jsonl` produces a byte-identical fact base and a byte-identical
   certificate.

4. If component 5 is ever reached between two distinct events, the pipeline emits diagnostic
   `DUP_EVENT_SAME_KEY` into the run manifest with both `EventId`s. This is not an error (exact
   duplicates are a declared degradation operator) but the count is published, because a bundle
   where this is common indicates a source whose `seq` is not doing its job.

5. Derived identifiers follow the same discipline: every identifier is the rank of a canonical
   key, never an allocation counter.

   ```
   FactId       := rank of (tick, predicate_id, arg0..arg3)          ascending, args are EntityIds
   RuleInstId   := rank of (rule_id, head_fact, body_facts_sorted, silent_license_or_MAX)
   AtomId (bit) := rank of (control_name_bytes, level)               see the 64-atom section
   LicenseId    := rank of (source_id, t0, t1, basis_tag)
   CorridorId   := rank of the corridor's blocker mask, ascending as u64
   ```

   Bit positions in the `blockers: u64` mask are therefore a pure function of `controls.toml`
   and are written to `build/atom-positions.txt`, which is committed and diffed in CI so a
   catalog edit that renumbers atoms is visible in review rather than silently invalidating
   every stored certificate.

6. Sorts are **stable sorts only**, or unstable sorts over keys proved total by 58.3. Rust:
   `sort_by` / `sort_by_key` (stable) or `sort_unstable_by` only where the key includes
   `line_ordinal`. Go: `sort.SliceStable` or `slices.SortStableFunc`. Python: `sorted` (stable by
   contract). TypeScript: `Array.prototype.sort` with an explicit total comparator (never the
   default string coercion). A lint fails on `sort.Slice`, `sort_unstable` without a documented
   total key, and any `.sort()` with no comparator.


58.4 BAN ON UNORDERED-COLLECTION ITERATION IN OUTPUT PATHS
------------------------------------------------------------

OVERRIDES Part I: Part I named this risk nowhere. It is now a build gate with a per-language rule.

Unordered collections may be used as *lookup* structures. Iterating one inside a decision path is
forbidden, because iteration order is unspecified, allocator-dependent, hash-seed-dependent, and
in Go deliberately randomized.

| Language   | Allowed in decision paths                              | Banned (lint-enforced)                                    |
|------------|--------------------------------------------------------|-----------------------------------------------------------|
| Rust       | `BTreeMap`, `BTreeSet`, `IndexMap`, `IndexSet`, `Vec`  | iterating `HashMap`/`HashSet`; `.iter()` on them at all in decision crates |
| Go         | sorted key slice then range over the slice             | bare `for k := range m`; `maps.Keys` without `slices.Sort` |
| Python     | `list`, `dict` with insertion order *plus* explicit `sorted()` at every boundary | iterating a `set`/`frozenset`; relying on `dict` order from a `set`-derived source; `PYTHONHASHSEED` reliance |
| TypeScript | `Map` (insertion order) and arrays                      | `Set` iteration for output; `Object.keys` on a dynamically keyed object without `.sort()` |
| Haskell    | `Data.Map`, `Data.Set` (ordered)                        | `Data.HashMap`, `Data.HashSet`                             |
| C / C++    | sorted arrays, `std::map`, `std::set`                   | `std::unordered_map`/`unordered_set` iteration             |
| Java/Kotlin| `TreeMap`, `LinkedHashMap`                              | `HashMap`/`HashSet` iteration                              |
| SQL        | `ORDER BY` on every query feeding an artifact           | any `SELECT` without `ORDER BY` whose rows reach a file    |

Enforcement artifacts (all committed, all wired to `make lint-determinism`):

```toml
# clippy.toml  — applies to spectra-kernel, spectra-ground, spectra-cert
disallowed-types = [
  { path = "std::collections::HashMap", reason = "58.4: use BTreeMap or IndexMap in decision paths" },
  { path = "std::collections::HashSet", reason = "58.4: use BTreeSet or IndexSet in decision paths" },
]
```

```go
// tools/vet/maprange: a golang.org/x/tools analyzer.
// Reports every *ast.RangeStmt whose X has type *types.Map, unless the enclosing
// function carries the comment directive //spectra:nondet-ok with a justification.
// Run as: go vet -vettool=$(PWD)/bin/maprange ./...
// The checker module (spectra verify) is compiled with zero //spectra:nondet-ok directives;
// a gate asserts that count is exactly 0.
```

```python
# tools/lint/nondet_ast.py — flake8 plugin, error codes:
#   SPD001 iteration over a set/frozenset literal or variable
#   SPD002 dict/set comprehension whose result is iterated without sorted()
#   SPD003 os.listdir / os.scandir / glob.glob without sorted()
#   SPD004 float literal or float() call inside a module listed in decision_paths.txt
```

```jsonc
// .eslintrc.determinism.json
{ "rules": {
    "spectra/no-set-iteration-in-output": "error",
    "spectra/no-object-keys-without-sort": "error",
    "spectra/require-sort-comparator": "error" } }
```

Filesystem order is an unordered collection too: every directory listing, glob and `find` result
that reaches a decision path is sorted byte-wise before use. `Makefile` wildcards are wrapped in
`$(sort ...)`. A gate creates a fixture directory whose entries are created in reverse order and
asserts identical output.


58.5 FLOAT BAN AND FIXED-POINT ARITHMETIC
------------------------------------------------------------

OVERRIDES Part I: Part I permitted quantiles, ratios and cost arithmetic without stating a
numeric type. IEEE-754 is banned in decision paths outright — not "discouraged".

1. No `f32`/`f64`/`float`/`double`/`number`/`Double`/`NUMERIC` value may be computed, compared,
   stored or serialized in a decision path. `SPD004` and the Rust/Go/TS equivalents fail the
   build on any occurrence outside `presentation/` and `bench/`.

2. Replacements, all exact integer types with a declared denominator:

   | Quantity                    | Type      | Denominator      | Notes                                   |
   |-----------------------------|-----------|------------------|-----------------------------------------|
   | ratios, rates, fractions    | `i64`     | `1_000_000` (ppm)| `Ppm(i64)`; construct only via `Ppm::from_ratio(num, den)` which uses `i128` intermediates |
   | Jaccard redundancy `red(i,j)`| `Ppm`    | `1_000_000`      | `red = 1_000_000 * both / either`, integer division, remainder discarded and the truncation direction documented |
   | declared costs              | `i64`     | `1` (integer minor units) | `costs.toml` parses integers only; a decimal point is a parse error |
   | inter-arrival quantiles     | `DurNanos`| `1`              | exact-rank estimator, 58.5(3)           |
   | approximation factors       | rendered as an exact rational `p/q` string, never evaluated |          |

3. Quantile estimator (binds the liveness pass): exact rank, no interpolation, no float.

   ```
   fn quantile_exact(sorted: &[DurNanos], q_ppm: u32) -> DurNanos {
       // rank = ceil(q_ppm * n / 1_000_000) - 1, clamped to [0, n-1], i128 intermediate
       let n = sorted.len() as i128;
       let r = ((q_ppm as i128 * n + 999_999) / 1_000_000) - 1;
       sorted[r.clamp(0, n - 1) as usize]
   }
   // Ties: duplicates are retained before sorting; the estimator is order-of-input independent
   // because `sorted` is produced by a stable sort over (value, EventId).
   ```
   The *statistical* objection to a self-calibrated `q99` is not this section's problem; it is
   fixed by the calibration-baseline requirement in the liveness/ground-truth sections. This
   section only guarantees that whatever quantile is chosen is computed identically everywhere.

4. Floats are permitted, and only permitted, in: D3/canvas geometry, chart axes, CSS, and the
   bench harness's reported latencies. None of these may be hashed, and none may be read back.
   A gate asserts the certificate JSON and the run manifest's `inputs` block contain zero values
   matching `/^-?\d+\.\d/` and zero `e`/`E` exponents.

5. Integer overflow is a hard error, never a wrap: Rust decision crates build with
   `overflow-checks = true` in **all** profiles including `release` (set in
   `[profile.release] overflow-checks = true`); Go uses checked helpers for every
   accumulator that can exceed `1<<40`; the Go checker rejects a certificate whose
   `lower_bound`, counts or budgets fail a range precondition rather than wrapping.


58.6 DETERMINISTIC STEP BUDGETS, NOT WALL-CLOCK TIMEOUTS
------------------------------------------------------------

OVERRIDES Part I: Part I's `§6`/`§4B` caps and the feasibility critic's proposed "solver time
budget" are replaced. A wall-clock cap makes identical inputs produce different flags on
different machines, which voids byte-identical replay and makes the `grounding_capped` and
`subset_minimal_only` flags — which gate the ROBUST verdict — host-dependent. Wall-clock caps
are banned in every decision path.

1. Every bounded loop in the pipeline draws from a **step budget**: a declared integer counter
   decremented by a declared unit of work. Budgets live in `budgets.toml`, are hashed into the
   certificate, and are identical across machines.

   ```toml
   # budgets.toml — schema_version = 1. All values are step counts, not times.
   # The committed values are whatever the fixture corpus requires plus headroom; they are
   # configuration, not measurements. Values shown here are illustrative, not a target.
   [grounding]
   rule_instances_max      = 2_000_000   # (illustrative, not a target)
   derivation_steps_max    = 50_000_000  # one step = one body-literal check (illustrative, not a target)
   frontier_bytes_max      = 1_073_741_824

   [fixpoint]
   propagations_max        = 20_000_000  # (illustrative, not a target)

   [hitting_set]
   corridors_max           = 4_096       # (illustrative, not a target)
   bnb_nodes_max           = 5_000_000   # one node = one mask expansion (illustrative, not a target)
   fixpoint_calls_max      = 100_000     # (illustrative, not a target)

   [liveness]
   constraint_relaxations_max = 10_000_000  # Bellman-Ford edge relaxations (illustrative, not a target)
   ```

2. Budget accounting rule: a step is counted at exactly one place per budget, the counting site
   is annotated `// BUDGET: <name>`, and a gate greps that each budget has >= 1 counting site and
   that no budget is decremented by a value computed from a timer.

   ```rust
   pub struct Budget { pub name: &'static str, remaining: u64, limit: u64, hit: bool }
   impl Budget {
       #[inline] pub fn spend(&mut self, n: u64) -> Result<(), CapHit> {
           match self.remaining.checked_sub(n) {
               Some(r) => { self.remaining = r; Ok(()) }
               None => { self.hit = true; Err(CapHit { budget: self.name, limit: self.limit }) }
           }
       }
   }
   ```

3. Exhaustion is deterministic and *observable*: the exact step index at which each budget was
   exhausted is recorded in the run manifest as `caps_hit[].at_step`, and the same bundle on any
   machine must report the same `at_step`. A gate diffs `caps_hit` across the three
   reproduction environments of 58.10 and fails on any difference.

4. Exhaustion sets the corresponding certificate flag and, per the verdict-algebra section,
   makes ROBUST unconstructible. Exhaustion never silently truncates an output.

5. Wall-clock is still measured, purely as an operational signal, and recorded in the
   **unhashed** `environment` block. If a run exceeds `environment.soft_deadline_seconds` the
   process prints a warning and **continues**. It may not abort, because aborting on time is a
   wall-clock decision. CI kills runaway jobs at the job level, and a job killed that way is a
   red build, not a flagged certificate.

6. Forbidden constructs in decision paths, lint-enforced: `tokio::time::timeout`,
   `context.WithTimeout`, `signal.alarm`, `SIGALRM`, `setTimeout` gating a computation,
   `select` on a `time.After`, retry-with-backoff, any `sleep`.


58.7 CONCURRENCY: FIXED WIDTH AND DETERMINISTIC REDUCTION
------------------------------------------------------------

1. The default and the fixture configuration is **single-threaded decision paths**. The kernel,
   the grounder, the liveness pass, the hitting-set loop and `spectra verify` are single-threaded
   unless 58.7(2) applies.

2. Parallelism is permitted only in a *map* phase whose work items are indexed `0..n`, are pure,
   and whose results are merged in **index order** afterwards. Reduction never happens in
   completion order. Pattern:

   ```rust
   // ALLOWED: fixed width, index-ordered reduction.
   let width: usize = cfg.threads;                  // from SPECTRA_THREADS, hashed into manifest
   let mut out: Vec<Option<Partial>> = (0..n).map(|_| None).collect();
   pool.install(|| out.par_iter_mut().enumerate().for_each(|(i, slot)| *slot = Some(work(i))));
   let merged = out.into_iter().map(Option::unwrap).fold(Acc::default(), Acc::merge_ordered);
   // FORBIDDEN: channel-receive-order merges, par_iter().reduce() with a non-associative op,
   // work-stealing that affects which partial result wins, atomics as accumulators for anything
   // other than exact integer addition.
   ```

3. `SPECTRA_THREADS` defaults to `1`. `rayon` is initialized with an explicit
   `ThreadPoolBuilder::num_threads(cfg.threads)`; the global pool is never used. Go decision code
   sets `GOMAXPROCS` explicitly and uses no goroutine whose scheduling affects output.
   `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `RAYON_NUM_THREADS` are
   exported by the Makefile.

4. Gate `make test-thread-invariance`: every fixture runs at `SPECTRA_THREADS in {1, 2, 8}` and
   all three must produce the identical certificate hash and identical `caps_hit`. The value used
   is recorded in the manifest's `environment` block (unhashed), *not* in `inputs`, precisely
   because it must not matter.

5. Any associativity requirement of a merge operator is stated in a doc comment and covered by a
   property test asserting `merge(a, merge(b, c)) == merge(merge(a, b), c)` over generated
   partials.


58.8 SEED REGISTRY
------------------------------------------------------------

OVERRIDES Part I: "generator seed" (ECLIPSE §2) was a single scalar. One scalar consumed by
several components couples them: adding a shuffle in the generator changes the degradation
operators' stream and silently invalidates every fixture. Seeds are now derived and registered.

1. There is exactly one root seed per run, `root_seed`, a 32-byte value written as 64 lowercase
   hex characters. Every consumer derives its own stream by domain separation:

   ```
   seed(consumer_id) = BLAKE3::keyed(root_seed, "spectra/seed/v1|" || consumer_id)   -> 32 bytes
   ```

2. The only permitted PRNG in any decision path, in every language, is **ChaCha20** with a
   64-bit counter starting at 0 and a zero nonce, producing a byte stream consumed
   little-endian. Rust `rand_chacha::ChaCha20Rng::from_seed`; Python a vendored pure-Python or
   `PyCryptodome`-free ChaCha20 in `spectra_rng/`; Go `golang.org/x/crypto/chacha20`; TS a
   vendored implementation. Banned: `rand::thread_rng`, `math/rand`, `random.*` module-level
   functions, `Math.random`, `numpy.random.seed` legacy global state, and any RNG whose stream is
   not specified by a public algorithm.

3. Uniform-integer draws use rejection sampling with a documented rejection rule (Lemire with the
   rejection branch retained), not modulo bias, so the draw sequence is identical across
   languages. A cross-language gate asserts Rust, Go and Python produce the identical first
   1024 draws from the same seed for `bound in {2, 3, 7, 100, 1<<31}`.

4. `seeds.toml` is committed, is hashed into the certificate, and every consumer that draws a
   random value must appear in it. A gate scans the source tree for PRNG constructions and fails
   if a `consumer_id` used in code is absent from the registry, or if a registered consumer is
   never constructed (dead seed).

   ```toml
   # seeds.toml — schema_version = 1
   root_seed = "0000000000000000000000000000000000000000000000000000000000000000"

   [[consumer]]
   id       = "generator.scenario_topology"
   owner    = "generators/topology.py"
   purpose  = "entity estate shape: host count, account count, group nesting"
   draws    = "uniform ints only"

   [[consumer]]
   id       = "generator.attack_path_choice"
   owner    = "generators/attack.py"
   purpose  = "which modeled technique sequence the scenario instantiates"

   [[consumer]]
   id       = "degrade.delete"          # one consumer PER degradation operator, never shared
   owner    = "degrade/ops/delete.py"
   purpose  = "record selection for deletion at a given completeness level"

   [[consumer]]
   id       = "degrade.delay"
   owner    = "degrade/ops/delay.py"

   [[consumer]]
   id       = "degrade.duplicate"
   owner    = "degrade/ops/duplicate.py"

   [[consumer]]
   id       = "degrade.reorder"
   owner    = "degrade/ops/reorder.py"

   [[consumer]]
   id       = "degrade.corrupt"
   owner    = "degrade/ops/corrupt.py"

   [[consumer]]
   id       = "degrade.suppress"
   owner    = "degrade/ops/suppress.py"

   [[consumer]]
   id       = "kernel.config_sampler"   # the randomized simulator-vs-kernel configurations
   owner    = "crates/kernel/tests/configs.rs"
   purpose  = "control-assignment sampling for the agreement gate"

   [[consumer]]
   id       = "fuzz.guard_differential"
   owner    = "fuzz/guard_diff/"
   ```

5. The kernel itself draws **zero** random values. A gate asserts `crates/kernel` links no RNG
   crate at all. Randomness exists in generators, degradation, test config sampling and fuzzing —
   nowhere in the proof path. If a solver heuristic ever wants randomization, it takes a
   registered seed as an explicit input and that seed enters the certificate.


58.9 RUN MANIFEST
------------------------------------------------------------

1. Every pipeline invocation writes `runs/<run_id>/manifest.json`, where
   `run_id = blake3(canonical(manifest.inputs))[0..16]` in hex. The manifest has exactly two
   top-level blocks and the split is the whole point:

   - `inputs` — everything that may affect output. Hashed. `run_id` and every certificate hash
     derive from this block alone.
   - `environment` — everything that must not affect output. Recorded for debugging, excluded
     from every hash.

   OVERRIDES Part I: Part I's certificate carried no host or toolchain provenance and no
   statement of what is excluded from hashing. Host fingerprints, wall-clock and thread counts
   are recorded but **never hashed**; if they were, cross-environment byte-identity would be
   impossible by construction.

```jsonc
{
  "schema_version": 1,
  "inputs": {
    "git_sha": "0000000000000000000000000000000000000000",
    "git_dirty": false,                      // a dirty tree taints the run: see 58.9(3)
    "files": [                               // sorted by path, byte-lexicographic
      { "path": "bundle.jsonl",   "blake3": "…", "bytes": "104857600" },
      { "path": "rules.toml",     "blake3": "…", "bytes": "39102",  "ast_blake3": "…" },
      { "path": "controls.toml",  "blake3": "…", "bytes": "8811" },
      { "path": "costs.toml",     "blake3": "…", "bytes": "0", "present": false },
      { "path": "goal.toml",      "blake3": "…", "bytes": "412" },
      { "path": "scenario.toml",  "blake3": "…", "bytes": "1904" },
      { "path": "seeds.toml",     "blake3": "…", "bytes": "2210" },
      { "path": "budgets.toml",   "blake3": "…", "bytes": "961" },
      { "path": "er-config.toml", "blake3": "…", "bytes": "1533" }
    ],
    "tick_nanos": "1000000",
    "horizon_ticks": "600",
    "root_seed": "0000…",
    "derived_seeds": [ { "consumer": "degrade.delete", "seed": "…" } ],   // sorted by consumer
    "toolchains": [                          // sorted by name; exact versions, never ranges
      { "name": "rustc",  "version": "1.83.0", "hash": "…" },
      { "name": "cargo-lock", "version": "Cargo.lock", "hash": "…" },
      { "name": "go",     "version": "1.23.4", "hash": "…" },
      { "name": "python", "version": "3.12.7", "hash": "…" },
      { "name": "uv-lock","version": "uv.lock", "hash": "…" }
    ],
    "image_digest": "sha256:0000…",          // the toolchain image, pinned by digest not tag
    "schema_hashes": { "certificate": "…", "manifest": "…", "bundle_record": "…" }
  },
  "environment": {                            // NEVER hashed, NEVER read by a decision path
    "started_at_wall": "2026-01-01T00:00:00.000000000Z",
    "wall_ns": "0",
    "host": { "os": "linux", "arch": "aarch64", "kernel": "6.8.0", "cpu_model": "…",
              "cores": 8, "container": true, "wsl2": false },
    "threads": 1,
    "peak_rss_bytes": "0",
    "soft_deadline_seconds": 0
  },
  "caps_hit": [                               // hashed; part of the result, not the environment
    { "budget": "hitting_set.corridors_max", "limit": "4096", "at_step": "4096" }
  ],
  "outputs": [                                // sorted by path
    { "path": "liveness.json", "blake3": "…" },
    { "path": "cert.json",     "blake3": "…" }
  ],
  "diagnostics": { "dup_event_same_key": "0", "quarantined_records": "0" }
}
```

2. Canonical serialization, used for the manifest, the certificate and every hashed artifact
   (**SCJ — SPECTRA Canonical JSON**): UTF-8 without BOM; object keys sorted byte-lexicographic;
   no insignificant whitespace; `\n` as the only line terminator and exactly one trailing `\n`;
   strings NFC-normalized at ingest and emitted with minimal escaping (`"` `\` and C0 only, lowercase `\u00xx`);
   **all integers emitted as decimal strings**, so no consumer's JSON number type can lose
   precision or reintroduce a float; booleans and `null` permitted; floats and exponents
   forbidden by the writer, which panics rather than emitting one. A round-trip conformance
   corpus at `tests/scj/` must produce byte-identical output from the Rust writer, the Go writer
   and the Python writer. Disagreement fails the build.

3. `git_dirty: true` forces `flags.dirty_tree` on the certificate, and per the verdict-algebra
   section a dirty run is never ROBUST and its numbers may never reach `docs/`.

4. `.gitattributes` enforces `* text=auto eol=lf` plus `*.jsonl -text`, `*.json -text`,
   `tests/golden/** -text` (binary, never CRLF-munged). A gate runs
   `git ls-files --eol | grep -v 'w/lf'` and fails on any hit, so the author's Windows host and
   Linux CI produce identical golden bytes.


58.10 CROSS-ENVIRONMENT REPRODUCTION GATES
------------------------------------------------------------

OVERRIDES Part I: reproducibility was asserted and tested nowhere. It is now a required CI job
with three environments, and a green build requires all three to agree.

1. The **reproduction triple**. The same bundle, the same inputs block, must yield the identical
   `cert.json` BLAKE3 and the identical `caps_hit` on:

   | Env id     | Platform                         | Runner                                  |
   |------------|----------------------------------|-----------------------------------------|
   | `lin-x64`  | Linux x86-64, glibc              | `ubuntu-24.04`                          |
   | `lin-a64`  | Linux arm64, glibc               | `ubuntu-24.04-arm` (or qemu, declared)  |
   | `wsl2`     | Windows 11 + WSL2 Ubuntu         | self-hosted, the author's machine       |

   `wsl2` is mandatory, not optional: it is the author's development environment, and a charter
   that only holds in CI does not hold.

2. All three run the same digest-pinned toolchain image. The arm64 variant is a separate digest;
   both digests are recorded in `docker/digests.txt` and a gate asserts the running image digest
   matches the manifest's `image_digest`.

3. `SOURCE_DATE_EPOCH=0` is exported for every build. Build IDs, embedded paths and archive
   timestamps are normalized (`--remap-path-prefix`, `-trimpath`, `tar --sort=name --mtime=@0
   --owner=0 --group=0 --numeric-owner`). The certificate never embeds a build path.

4. Binary reproducibility of the tools themselves is a separate, weaker gate: `lin-x64` builds
   the kernel twice from a clean clone and diffs the binary hashes. Failure here is a warning
   with a required ticket, not a red build, because toolchain-level nondeterminism is outside the
   project's control. Certificate reproducibility is never a warning; it is always red.

5. Divergence localization. Every stage emits a stage digest into
   `runs/<run_id>/stages.tsv` so a mismatch names the first divergent stage instead of producing
   a bare hash diff:

```
          bundle.jsonl
               |  S0  ingest_digest        (canonical records, EventId order)
               v
          fact base
               |  S1  er_digest            (EntityId assignment + merge decisions)
               v
          liveness
               |  S2  liveness_digest      (licenses, windows, basis tags)
               v
          grounding
               |  S3  hypergraph_digest    (FactIds, RuleInstIds, blockers masks)
               v
          fixpoint / cut
               |  S4  psi_digest           (corridor set, ascending CorridorId)
               |  S5  cut_digest           (S_opt, S_rob, lexicographic representative)
               v
          certificate
                  S6  cert_blake3
```

   `spectra repro-diff runs/A runs/B` prints the first stage whose digest differs and exits
   non-zero. A determinism bug is then localized to one stage before any debugging begins.


58.11 `make repro-check` AND THE CI WIRING
------------------------------------------------------------

1. `make repro-check` runs the full pipeline **twice** on the same inputs, into two distinct
   output directories, with deliberately perturbed non-semantic conditions between the runs, and
   diffs every stage digest. Perturbations applied to run B: different `$TMPDIR`, different
   working-directory path depth, `SPECTRA_THREADS=8`, `TZ=Asia/Kolkata`, shuffled
   `bundle.jsonl` line order, reversed directory-creation order in the fixture tree, and an
   inserted environment variable of 4 KiB to shift the stack layout.

```make
REPRO_FIXTURE ?= fixtures/held-out/s07
.PHONY: repro-check
repro-check:
	rm -rf out/reproA out/reproB
	TZ=UTC LC_ALL=C SPECTRA_THREADS=1 SOURCE_DATE_EPOCH=0 \
	  ./bin/spectra run --inputs $(REPRO_FIXTURE) --out out/reproA
	python3 tools/shuffle_lines.py --seed-consumer repro.shuffle \
	  $(REPRO_FIXTURE)/bundle.jsonl out/bundle_shuffled.jsonl
	TZ=Asia/Kolkata LC_ALL=C SPECTRA_THREADS=8 SOURCE_DATE_EPOCH=0 TMPDIR=$(PWD)/out/tmpB \
	  PADDING=$$(head -c 4096 /dev/zero | tr '\0' 'x') \
	  ./bin/spectra run --inputs $(REPRO_FIXTURE) \
	                    --bundle out/bundle_shuffled.jsonl --out out/reproB
	./bin/spectra repro-diff out/reproA out/reproB
	diff <(jq -S '.inputs, .caps_hit' out/reproA/manifest.json) \
	     <(jq -S '.inputs, .caps_hit' out/reproB/manifest.json)
	./bin/spectra verify out/reproA/cert.json
	./bin/spectra verify out/reproB/cert.json
```

2. Expected transcript. All durations below are illustrative, not a target; the committed
   expected file records only hashes and `caps_hit`, never timings.

```
$ make repro-check
run A  lin-x64  threads=1  TZ=UTC
  S0 ingest_digest      b3:9c41e0d2…   1 482 391 records
  S1 er_digest          b3:77af10bc…
  S2 liveness_digest    b3:0be5c934…   licenses=41
  S3 hypergraph_digest  b3:a1d4772f…   instances=2104   (illustrative, not a target)
  S4 psi_digest         b3:6f08bb15…   corridors=6      (illustrative, not a target)
  S5 cut_digest         b3:2dd9c604…
  S6 cert_blake3        b3:3f9a55e1…
run B  lin-x64  threads=8  TZ=Asia/Kolkata  shuffled bundle  deep TMPDIR
  S0..S6 identical
repro-diff: no divergent stage (7/7 equal)
manifest: inputs and caps_hit identical
verify A: OK      verify B: OK
PASS
```

   On failure the target exits non-zero and prints exactly one line naming the first divergent
   stage, e.g. `repro-diff: FIRST DIVERGENCE at S2 liveness_digest (A b3:0be5… B b3:41c7…)`.

3. CI wiring. `repro-check` runs on the `lin-x64` runner on **every push** (it is a single
   fixture and cheap). The three-environment job `repro-matrix` runs `lin-x64`, `lin-a64` and
   `wsl2` over the held-out fixture set nightly and on every tag, and compares the three
   `cert.json` hashes pairwise. Both jobs are blocking for a release tag; `repro-check` is
   blocking for a merge. These are the only determinism gates permitted to be quarantined, and
   quarantining either requires a `WAIVER.md` entry per the delivery sections.

4. `make lint-determinism` runs every linter in 58.4/58.5/58.6 and is blocking on every push.

5. Golden bytes: `tests/golden/**` holds committed certificate and manifest bytes for the demo
   fixture. `make test-golden` diffs bytes, not parsed structures. Regenerating goldens requires
   `make bless-golden`, which refuses to run unless the working tree is clean and prints the
   before/after hashes into `BUILD_LOG.md`.


58.12 NEGATIVE REQUIREMENTS
------------------------------------------------------------

The following are build failures, not code-review opinions:

1. Do not call the system clock, a monotonic timer, `getpid`, `gethostname`, `uname`, an
   environment variable not listed in `config/env-allowlist.txt`, or a network socket from a
   decision path. `spectra` and `spectra verify` are pure file-in/file-out binaries with no
   service dependency; a gate runs them with no network namespace, no `$HOME`, no Postgres and
   no Redis and requires success.
2. Do not iterate a hash-ordered or filesystem-ordered collection to produce output.
3. Do not introduce a float into a decision path, including "just for a percentage in a log line
   that also goes into the certificate".
4. Do not bound any decision loop by time, by retry count derived from time, or by an
   externally-signalled cancellation.
5. Do not make output depend on thread count, CPU count, available memory, allocator behaviour,
   pointer values, `Instant`, or iteration over a work-stealing queue's completion order.
6. Do not store a `TsNanos` as a float, a string, or a database `TIMESTAMP`.
7. Do not add a seed consumer without registering it in `seeds.toml`; do not share one seed
   between two consumers; do not reseed mid-run.
8. Do not hash the `environment` block, and do not read any field of it from a decision path.
9. Do not "fix" a repro-check failure by loosening the comparison (parsed-structure diff instead
   of byte diff, tolerance windows, excluding a stage). Any such change requires a `WAIVER.md`
   entry, appears in the README status table, and per the ratchet rule cannot be made silently.
10. Do not regenerate goldens as a routine step of making a build green.


58.13 FORBIDDEN CLAIMS
------------------------------------------------------------

1. Never claim "bit-for-bit reproducible on any machine". The proven claim is exactly:
   *the same input bundle and the same pinned toolchain image produce the same certificate hash
   on `lin-x64`, `lin-a64` and `wsl2`, as of the run recorded in the latest `repro-matrix`
   artifact.* README states it in that form, with the artifact id.
2. Never claim "deterministic" for a component that has not passed `make lint-determinism` and is
   not covered by a stage digest.
3. Never claim reproducibility across toolchain versions, across base-image digests, or across
   `tick_nanos` values. Those are different inputs and produce different, legitimately different,
   hashes.
4. Never present a certificate whose manifest carries `git_dirty: true`, any `caps_hit` entry, or
   a `repro-matrix` disagreement as evidence of anything. The verdict-algebra section makes
   ROBUST unconstructible in those states; this section forbids quoting the numbers at all.
5. Never describe the determinism work as "formal verification", "provably deterministic", or
   "guaranteed". The mechanisms are lints, pinned types and differential gates. They catch the
   enumerated failure modes and nothing more, and `LIMITATIONS.md` says so.
