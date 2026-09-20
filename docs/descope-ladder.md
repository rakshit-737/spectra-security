# The descope ladder

Source: build specification Part II, section 75.5, with the procedure in 75.6. This ladder is
normative. It exists so that running out of time produces a smaller honest repository rather than a
larger dishonest one.

Status of this document: delivered. Rungs applied so far: none. `BUILD_LOG.md` does not exist yet,
so there is no DESCOPE entry to point at.

Gate note (TODO — decision made here): this file names verdict tokens inside invariant identifiers
(for example `zero-false-ROBUST`). Either register `docs/descope-ladder.md` as an exempt path in
`docs/banned.toml`, or rename the invariant so no bare verdict token appears. The first option is
taken here; change it by renaming the invariant in this file and in the gate that enforces it, in
the same commit. `docs/banned.toml` does not exist yet, so the exemption is a decision taken and
not a registration performed. TODO(M0): create `docs/banned.toml` with `docs/descope-ladder.md` as
an exempt path, in the commit that lands the `G-CLAIM-BANNED` gate.

## The rule of use

When time runs out, descend this ladder. Cut the lowest-numbered rung that is still intact, in
order. Never skip ahead to a higher rung because it is easier to delete.

A rung is not descoped until the demotion has moved **in code and in docs in the same commit**. A
cut feature whose claim is still standing is not a descope; it is a false claim, and
`make claims-check` fails on it.

Every applied rung requires a DESCOPE entry in `BUILD_LOG.md` using the fixed field order of
section 75.6, and any resulting drop in a ratchet count requires a waiver in `ratchet.json` whose
rationale names the rung.

Descoping removes a *feature* and its *claim*. It never removes a *check* on a feature that
remains. Lowering an assertion, loosening a tolerance, shrinking a fixture or marking a test skipped
is test weakening, not descoping, and is forbidden.

The ladder is D1..D12. Do not invent a rung. It is amended only by an explicit `BUILD_LOG.md` entry
that adds a numbered rung and states where it sits.

```
                     KEEP  ^
                           |   D0  MPC C1-C10                 NEVER CUT
  ---------------------    |  ----------------------------------------------
  cut last  ............   |   D12 the four UI screens -> CLI transcript
                           |   D11 degradation matrix -> fewer cells
                           |   D10 held-out set -> one family, not three
                           |   D9  UI polish, theming, animation
                           |   D8  kernel stage E exactness -> SUBSET default
                           |   D7  Go checker re-grounding -> instance-set check
                           |   D6  Tier D languages (analysis and reporting)
                           |   D5  Tier C languages (range-realism emitters)
                           |   D4  bench registry, bindings, API surface
                           |   D3  FSM dimensions beyond the first four
                           |   D2  Haskell reference checker + Z3 oracle
                           |   D1  live container range  (NON-NORMATIVE)
  cut first ............   |
                     CUT   v
```

## The rungs, with the exact demotion each performs

### D1 — Live container range

Demote to a non-normative realism check. It produces bundles that are never used in a published
number, never in a gate, never in the paper. If time is short it is deleted entirely and
`docs/range/not-modeled.md` states that the realism corroboration was not performed.

**Rule:** the range is demoted to a non-normative realism check *before* the kernel is thinned.
Kernel thinning may not begin while the range is still normative or still consuming schedule.

### D2 — Haskell reference checker and Z3 oracle

Five implementations of one semantics (Rust kernel, Rust simulator, Go checker, Haskell reference,
Z3 encoding) means five edits per rule-table change. Cut to three: kernel, simulator, Go checker.
If Haskell goes, the honest justification for Haskell in the polyglot tiers goes with it — delete
the directory, do not leave a stub.

### D3 — FSM dimensions beyond the first four

Ship identity, session, credential, privilege. The flagship counterfactual exercises exactly
session binding, egress segmentation, credential rotation and iam_audit. Ship the remaining
dimensions as one documented extension point with one worked stub and a test that the extension
point is exercised.

### D4 — Benchmark registry, kernel bindings abstraction, full API surface

Keep one results schema and one make target. Keep the subprocess plus content-addressed JSON kernel
boundary; delete any pyo3/cgo abstraction layer.

### D5 — Tier C languages

Range-realism emitters. Cut as a whole tier, not language by language: polyglot tiers are completed
in tier order, so a half-cut tier is worse than a cut tier.

### D6 — Tier D languages

Analysis and reporting. Their outputs move into the Python analysis path, which already exists. The
tier roster is the Tier D row below.

### D7 — Go checker re-grounding

Ship the linear closure check over the published instance set, witness re-derivation, and the
no-smaller-cut check against the licensed hypothesis set. Downgrade the written guarantee in the
same commit: `docs/checker-scope.md` must read "validates the certificate against the instance set
the kernel published; does not independently re-derive that set."

**Rule:** the guarantee text and the code are descoped in the same commit, or the descope is
rejected.

### D8 — Exact cardinality-minimality

Make `minimality: SUBSET` the default and `EXACT` the exception requiring exhaustive verification.
Minimum hitting set is NP-hard in the corridor count; a sixty-four-bit representation width is not a
tractability bound. The UI never prints "no smaller cut exists" on a `psi_relative` certificate.

### D9 — UI polish

Theming, animation, layout refinement. The four screens stay; they stop being pretty.

### D10 — Held-out families

Reduce from three scenario families to one. Publish that the held-out evidence is one family and
that generalization is therefore untested.

### D11 — Degradation matrix breadth

Reduce cells, never the `zero-false-ROBUST` invariant. Report the reduced grid as reduced; do not
interpolate, do not smooth, do not plot a curve through a handful of points.

### D12 — The four UI screens

Replace with a recorded, regenerated-in-CI CLI transcript that shows the same investigation and the
same counterfactual. This is the last rung. Below it there is no publishable artifact.

## The never-cut list

Under any schedule pressure, these are not cut, not thinned and not waived:

- C5 — the kernel, stages A through E.
- C6 — a checker of some scope, with its scope stated truthfully.
- C8's `zero-false-ROBUST` invariant on the declared suppression classes.
- C9 — the held-out protocol.
- The determinism charter.
- The claims-to-gate binding linter.
- `LIMITATIONS.md`.

## Polyglot tier order

Polyglot tiers are completed in tier order: A fully, then B fully, then C fully, then D. Never start
a language in tier N+1 while any language in tier N is missing its executing CI job, its
deletion-mutation proof, or its consumer edge. An unfinished repository must be coherent — three
complete tiers — rather than half-scaffolded everywhere.

```
TIER A  critical path          Python, Rust, Go, TypeScript, SQL, Bash
TIER B  independent oracles    Haskell, C, C++, one JVM language, C#, x86-64 asm
        and measured perf
TIER C  range-realism          PowerShell, PHP, Ruby, Perl, Lua, Kotlin,
        emitters               Swift, Dart, ...
TIER D  analysis & reporting   R, Julia, GNU Octave, F#, Solidity, Verilog,
                               VHDL, YARA, WebAssembly text
```

## Never carry a stub forward

A stub is any file that exists to satisfy a directory layout, has a function body that is a
placeholder or an empty test file, or is named in `mpc.toml` artifacts with no executing gate.
Stubs are deleted at descope time. `make stub-scan` enumerates them and fails the build if any stub
exists outside the single documented extension point permitted by rung D3.

Status of `make stub-scan`: not started. `mpc.toml` and `ratchet.json` are delivered; every
component they record is not started, and no target that reads them (`make mpc-status`,
`make ratchet-check`) exists.
