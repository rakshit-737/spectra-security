# C# - resource and service host in the observed range, dual-instrumented
Tier: B
Status: not started
Owning spec section: 73 (Part II), which supersedes Part I section 31.12
Milestone: M9 - Polyglot surface and performance

A note on vocabulary before anything else: Part I calls the observed environment the lab or the
estate; Part II calls it **the range** throughout (sections 62.4, 74.1, 75). This file uses "range".

## The promise

A resource and service host that genuinely runs and is observed twice by two independent
instrumentation layers, on a second runtime. Part II section 73.1 states the promise for this
component as "as above, on a second runtime" - the same cross-source oracle as the Java service,
deliberately not on the JVM.

The second runtime is the point, and it is a narrow point. A cross-source oracle that only ever
runs on one runtime cannot distinguish a semantics problem from a runtime-specific artifact of how
that one runtime is instrumented. Running the same two-layer construction on .NET is what turns a
single observation into a comparison.

One correction, recorded here because it is the kind of thing that survives in a README long after
the spec has moved: Part I section 31.12 cast C# as a *Windows-shaped identity event emitter*
producing synthetic records in a documented field layout. Part II section 73.1 supersedes that with
a genuinely observed host. The synthetic-emitter role is gone. And Part II section 73.11 forbids
claiming Windows, macOS or iOS endpoint telemetry from anything in this repository: this host runs
.NET on Linux, and no document may imply a Windows endpoint was observed.

Part I's environment-leak test survives the role change and is kept: no field in any emitted record
may carry a value read from the real host environment - no machine name, no real security
identifier, no real user. Part I section 31.12 called that a hard requirement rather than a nicety,
and it is more so now that the records are observed rather than synthesized.

Nothing has been built. No agreement has been measured and there is no number to report.

## What lives here

No file in this list exists yet.

- A `global.json` pinning the SDK, and a project layout that builds reproducibly.
- The host: resource access, service-account authentication, and an authorization decision point,
  with its own structured record emitter in a declared wire format. The format is what the ingest
  adapter keys on, never the producing language (Part II section 73.3.4).
- A second, independent instrumentation layer over the same host, whichever mechanism the runtime
  offers that does not require the host's cooperation.
- xUnit tests, including the cross-source test that the two layers agree on the event set.
- A schema conformance test against the committed record schema.
- The environment-leak test described above.
- Fixture inputs and the scenario bindings that name this host as a source.
- This component's `polyglot.toml` fragment, with every field Part II section 73.4 requires.

The `dotnet/` root is also where Part I section 31.13 placed the F# Pareto-frontier component, which
Part II section 73.1 keeps as a Tier D artifact. Those are two components with two manifest entries
and two disjoint `paths` globs. Part II section 73.4 requires every executing source file to be
matched by exactly one component's `paths`; overlapping globs fail with `AMBIGUOUS_OWNERSHIP` and
uncovered files fail with `ORPHAN_SOURCE`.

## Consumer edge

Two edges, both owned by components other than this one, as Part II section 73.3.1 requires.

First, the scenario bundles. Scenarios whose attack path traverses resource access or service-
account authentication draw those records from this host. Delete the directory and those scenarios
lose that leg: their bundles cannot be produced and the gates bound to them cannot run. The
dependency becomes explicit in the range-bound subset that Part II section 62.4.9 requires to be
declared.

Second, the cross-source agreement gate on the second runtime. Delete the directory and the
cross-source construction exists on one runtime only, which means any disagreement it does or does
not find can no longer be separated from a property of that runtime.

This is a real edge, not a gate-only edge: scenarios lose data, and the Java oracle loses its
control.

## How it is exercised

- CI job: `polyglot-b / estate-dotnet-host`, following the `polyglot-<tier> / <component-id>` naming
  Part II section 73.4 fixes and the `estate-*` id shape used in the audit transcript of Part II
  section 73.6. The final id is not yet written into `polyglot.toml`.
- Tier: T1 on changed paths per Part II section 73.9; T2 nightly for the full run plus the mutation
  leg.
- Component entrypoint: `make -C dotnet verify`, in the shape Part II section 73.4 uses for the C
  component's entrypoint.
- Audit: `make polyglot-audit`.

Part II section 74.1's four toolchain images do not name a .NET SDK in any row. Which image carries
it, or whether a fifth image is needed, is an open item below rather than an assumption made here.

## Mutation check

Operator `drop_records(p, seed)` from the closed set in Part II section 73.5, applied to this
component's output in a scratch worktree: a seeded fraction of the records emitted by one of the two
instrumentation layers is deleted, while the other layer's records are left intact.

The gate that must go RED is `polyglot-b / estate-dotnet-host`, at the cross-source assertion that
the two layers describe the same event set. Dropping records from one side must produce a set
difference the assertion reports.

If that gate stays green with records missing from one side, the two layers are not being compared
and "dual-instrumented" is a word rather than a property. The component is then PADDING under Part
II section 73.6, and the admissible responses are a real consumer edge or deletion in the same
commit.

A second candidate, if the host's own records rather than the instrumentation layer's are the
declared output, is `truncate_output_fields`, dropping the final field of each emitted record so
that schema conformance fails. Only one operator can be the declared one, and the choice, the seed
and the fully qualified `expect_red` assertion are not yet fixed; Part II section 73.4 requires all
three before the first source file.

## Not yet decided

- **The directory path.** The roster line says `dotnet/`. Part I section 31.12 said
  `dotnet/win-identity-sim/`, a name that encodes the superseded Windows-emitter role and should not
  survive the role change - and a directory named for Windows telemetry would sit badly against the
  Part II section 73.11 ban on implying a Windows endpoint. A name matching the Part II role is
  needed. Part II did not restate a path.
- **The split with F#.** Whether this component and the Tier D frontier component share the
  `dotnet/` root with disjoint globs, or move to separate roots such as `dotnet/host/` and
  `dotnet/frontier/`. The second is easier to keep unambiguous under `AMBIGUOUS_OWNERSHIP`.
- **Whether C# is in Tier B at all.** Part II section 73.1 lists it as one of six Tier B languages.
  Part II section 75.5.1 lists Tier B as "Haskell, C, C++, one JVM language, x86-64 asm" and does
  not include C# in any tier. Both are Part II. This is a Part II-internal conflict and per KICKOFF
  section 2 it is not resolved silently here.
- **Whether this host is part of the live container range.** Part II section 75 rung D1 demotes the
  live container range to a non-normative realism check and permits deleting it, and Part II section
  62.4 stamps range artifacts non-normative. If this host is inside that range, its cross-source
  gate cannot be normative and the Tier B promise has to be restated before D1 is ever pulled.
- **Which toolchain image carries the .NET SDK.** Part II section 74.1 lists four images and no row
  names .NET. Adding it to `spectra/toolchain-b` alongside the JVM, or creating a fifth image, are
  both open, and Part II section 73.9 requires that per-PR jobs never install a toolchain.
- **Which second instrumentation mechanism is used**, and whether it can observe the host without
  the host's cooperation in the way the JVM agent can. If it cannot, the two layers are not
  independent in the same sense and the promise must be narrowed rather than the mechanism stretched.
- **Which control atoms bind here** in `range/enforcement.toml` (Part II section 62.4.2). An atom
  with no enforcement point on this host is an excluded atom, and a cut containing an excluded atom
  may not be reported as range-corroborated.
