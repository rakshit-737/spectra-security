# F# - independent Pareto frontier over the enumerated corridors
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places F# in Tier D with this role. Part I section 31.13 gave F# a
different and load-bearing job which Part II does not reassign to anyone; see "Not yet
decided", because that gap is the most consequential thing on this page. Nothing here has been
written.

## The promise

One narrow thing: an independently authored implementation of the multiple-choice knapsack over
the enumerated corridor set, which must produce the identical frontier set as the Rust kernel -
not a similar one, not one within a tolerance, the same set.

The kernel's frontier is a derived field on the certificate. Part II section 66's derivation
axiom A8 suppresses `pareto_frontier` entirely when no cost declaration was supplied, and
axiom A7 suppresses the redundancy index when corridor enumeration was capped, so the frontier
is only ever published on runs where the corridor set reached fixpoint and costs were declared.
Those are exactly the runs where an independent implementation can be held to set equality
rather than to an approximation.

What the promise excludes:

- No formal verification claim. Part II section 73.11 forbids claiming formal verification from
  F# or from any Tier D artifact. Discriminated unions and exhaustive matching make certain
  classes of mistake into compiler errors; that is a property of the implementation, not a
  proof about the kernel.
- No optimality claim about the kernel. F# agreeing with the kernel means the two agree. It
  does not mean either is right, and no document may present agreement as correctness.
- No performance claim. This is not a faster solver and no document may say it is.

The research content is thin and should be described as thin: it is a second pair of eyes on
one combinatorial routine, written from the problem statement rather than from the Rust source.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `Frontier.fsproj` - the project file, pinned against the .NET version fixed in `global.json`.
- `Domain.fs` - the corridor, control-level and cost types as discriminated unions, so that an
  unrepresentable combination is a compile error rather than a runtime check.
- `Knapsack.fs` - the multiple-choice knapsack itself, written from the problem statement in
  Part II section 66 and Part I section 31.13's description of the cost model.
- `Frontier.fs` - extraction of the non-dominated set, with the domination relation stated once
  and used everywhere.
- `Io.fs` - reading the kernel's published corridor set and cost declaration, and emitting this
  side's frontier in a stable order.
- `Program.fs` - the entry point.
- `tests/` - FsCheck property tests over the domination relation and the solver, plus the
  fixture-driven comparison cases.

A lint is expected to forbid any reference from this directory into the Rust kernel's source
tree, because a cross-implementation that reads the implementation it checks is not one.

## Consumer edge

Moderate, and precise.

Delete this directory and the kernel still emits `pareto_frontier` on every run where the
derivation axioms permit it. No certificate changes, no verdict changes, the UI still renders
the frontier, and `spectra verify` still accepts the certificates it accepted before - the Go
checker validates the certificate against the published instance set and does not re-solve the
knapsack.

What is lost is the only non-Rust confirmation that the published frontier is the frontier. The
frontier is a derived field computed by exactly one implementation; without this directory,
the statement "these are the non-dominated corridors under the declared costs" rests on that
one implementation agreeing with itself. The gate `xcheck/frontier::set_eq` disappears with it.

That is a real edge, but it is a research edge rather than a product edge, and this page should
not dress it up as the latter. Under Part II section 73.9 a red job here does not block a Tier
A milestone; under section 75.5's descope ladder, Tier D is rung D6 and is cut before the Go
checker's re-grounding and before the degradation matrix's breadth. A component that is cut
sixth from the bottom of the ladder is not on the critical path and the documentation should
not imply that it is.

The gate must be owned by a different component than this one - the kernel's differential test
suite rather than this directory's own tests - or section 73.3.1 fails it with `SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-d / frontier-fsharp`. That component id is the one Part II section 73.6's
  audit transcript uses, so it is fixed rather than proposed.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release, and forbids silencing it with `continue-on-error` or an
  `if: false` guard.
- Make target: `make frontier-fsharp` builds the project and runs the FsCheck suite. The
  comparison and the mutation leg run under `make polyglot-audit`.
- Toolchain: the pinned .NET SDK, restored from the vendored NuGet cache with the network off.
  Part II section 74.1 does not list .NET in any of the four tier images by name; see "Not yet
  decided".

## Mutation check

Operator: `constant_result`, mandatory for every Tier D cross-check under Part II section 73.5.

The corruption: the solver returns a fixed frontier set - the same set of corridor selections
for every input, regardless of the corridor set and the declared costs. The emitted artifact
keeps its schema and its ordering; only the contents are constant.

The gate that must go red: `xcheck/frontier::set_eq`, the assertion that this side's frontier
and the kernel's `pareto_frontier` are the same set, element for element, on every fixture
where the derivation axioms permit the field to be present. Under the mutation the constant set
disagrees with the kernel on every fixture whose true frontier is not that constant, and the
assertion fails naming the first differing fixture and the symmetric difference.

The choice of `constant_result` over `reorder_output` is deliberate. Set equality is order
insensitive by definition, so a permutation mutation would leave the gate green and would prove
nothing about it. The mutation has to change the set, and the cheapest way for the gate to be
falsely green - a comparison that is checking cardinality, or checking a hash of a
canonicalised empty set - is exactly what a constant exposes.

## Not yet decided

- **Part I's state table has no owner.** Part I section 31.13 made F# the producer of the
  canonical state table - states, legal transitions, guards and dimension tags - which Python's
  engine and the Rust kernel both load rather than hard-coding, with a regeneration gate and a
  downstream Python gate, and from which Part I section 31.28 generated the Verilog transition
  decode. Part II section 73.1 reassigns F# to the frontier and names no owner for the state
  table or for the antitonicity oracle that Part I section 32.6 also gave to F#. The consumers
  remain and their producer is gone. Whether F# keeps two components - one of them arguably
  Tier A under section 73.1's own test, since deleting it would delete SPECTRA - or whether the
  state table moves elsewhere, is undecided and is recorded in `docs/plan/CONFLICTS.md`.
- **Directory path.** `fsharp/frontier/` is not stated anywhere in Part II; section 73.6's
  transcript gives the component id `frontier-fsharp` but no path. Part I section 31.13 used
  `dotnet/state-machine-model/`, which is the superseded role. The path above is therefore a
  working choice, not a specified one, and it should be fixed in `polyglot.toml` before any
  source file is committed - section 73.11 forbids adding a language without a manifest entry
  that passes all four load-bearing checks first.
- **Whether .NET is retained at all.** Part II section 74.1's four toolchain images list Tier A
  languages, C/C++, Haskell, the JVM, the emitter runtimes and the analysis stack. .NET appears
  in none of them by name, while section 73.1 places both F# and C# in the roster. Either an
  image gains .NET or the roster loses two entries; the specification does not say which.
- **The cost model's location.** The frontier is over declared costs, and Part II section 66's
  axiom A8 suppresses the field when no cost declaration was supplied. Part I named a
  `costs.toml`; Part II does not restate the filename in section 73. Which file this directory
  reads, and what happens on the no-costs path, is unsettled.
- **What "identical frontier set" means for ties.** When two corridor selections have equal
  cost and equal coverage, the non-dominated set may legitimately contain both, and two
  implementations may differ in whether they emit both. Set equality is only a well-defined
  gate once the tie handling is fixed on both sides; it has not been.
- **CI trigger tier.** Section 73.9 gives Tier D changed-path jobs per-PR, implying T1, while
  section 74.4 assigns Tier C/D language jobs to T2. The two have not been reconciled.
