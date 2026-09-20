# Java - token and identity service in the observed range, dual-instrumented
Tier: B
Status: not started
Owning spec section: 73 (Part II), which supersedes Part I section 31.10
Milestone: M9 - Polyglot surface and performance

A note on vocabulary before anything else: Part I calls the observed environment the lab or the
estate; Part II calls it **the range** throughout (sections 62.4, 74.1, 75). This file uses "range".

## The promise

A service that genuinely runs, issues and checks tokens, and is observed twice by two independent
instrumentation layers. Part II section 73.1 states the promise as "a genuinely observed service
whose two instrumentation layers form a cross-source oracle".

The cross-source property is the whole point. The service writes its own structured audit records.
A `java.lang.instrument` agent independently records token lifecycle events from bytecode, without
the service knowing it is being watched. Two views of the same events, produced by different code
paths, means a disagreement between them is detectable - and a disagreement is exactly what a
missing record, a reordered record or a suppressed window looks like from inside the pipeline.
That detectability is what makes this component an oracle rather than a source of telemetry.

What is not promised: realism. The claims gate bans "realistic" and "enterprise-grade" as
unregistered claims, and this file does not claim that any real deployment looks like this service.
Also not promised: coverage of enterprise identity behaviour, correctness of the token semantics as
a security design, or that the agent observes anything the JVM does not already expose.

Nothing has been built. The cross-source agreement has never been run, and there is no agreement
rate, disagreement count or record volume to report.

## What lives here

No file in this list exists yet.

- A Maven build (`pom.xml`, XML), a pinned JDK, and a reproducible-build configuration so the
  produced jar is byte-stable.
- The service: session issue, session check, token lifecycle, and an authorization decision point,
  on an embedded HTTP server with no application framework.
- Its structured audit emitter, writing records in a declared wire format. The format is what the
  ingest adapter keys on - never the producing language. Part II section 73.3.4 fails the build if
  any adapter identifier, filename or conditional under `ingest/` names a producing language.
- The `java.lang.instrument` agent, as a separate artifact with its own manifest attributes.
- JUnit 5 tests, including the cross-source test: every token the service issued appears in the
  agent's record stream, and every token in the agent's stream was issued by the service.
- A schema conformance test against the committed audit record schema.
- Fixture inputs and the committed scenario bindings that name this service as a source.
- This component's `polyglot.toml` fragment, with every field Part II section 73.4 requires.

## Consumer edge

Two edges, both owned by components other than this one, as Part II section 73.3.1 requires.

First, the scenario bundles. Every scenario whose attack path traverses token issue, token use or
token replay draws its identity records from this service. Delete the directory and those scenarios
have no source for that leg: their bundles cannot be produced and the gates bound to them cannot
run. The range-bound subset that Part II section 62.4.9 requires to be declared in
`validation/range-bound.txt` is where that dependency becomes explicit.

Second, the cross-source agreement gate. Delete the directory and the oracle that compares two
independent observations of one event stream disappears, along with the only Tier B evidence that
an observed source's records can be checked against a second observation of the same source rather
than against ground truth.

This is a real edge, not a gate-only edge: the scenarios lose data, not just a check.

## How it is exercised

- CI job: `polyglot-b / estate-java-identity`, following the `polyglot-<tier> / <component-id>`
  naming Part II section 73.4 fixes and the `estate-*` component-id shape used in the audit
  transcript of Part II section 73.6. The final id is not yet written into `polyglot.toml`.
- Tier: T1 on changed paths per Part II section 73.9; T2 nightly for the full run plus the mutation
  leg. The toolchain image is `spectra/toolchain-b`, which Part II section 74.1 gives the JVM.
- Component entrypoint: `make -C java verify`, in the shape Part II section 73.4 uses for the C
  component's entrypoint.
- Audit: `make polyglot-audit`.

## Mutation check

Operator `drop_records(p, seed)` from the closed set in Part II section 73.5, applied to this
component's output in a scratch worktree: a seeded fraction of the agent's emitted token-lifecycle
records is deleted, while the service's own audit records are left intact.

The gate that must go RED is `polyglot-b / estate-java-identity`, at the cross-source assertion that
every token the service issued appears in the agent's stream. Dropping agent records must produce a
set difference the assertion reports.

If that gate stays green with a seeded fraction of agent records missing, the two instrumentation
layers are not being compared to each other, "dual-instrumented" is decoration, and the component is
PADDING under Part II section 73.6 no matter how much Java is in the tree.

There is a second reason this particular mutation is the right one. Part II section 62.7's mutant
M11 makes silently dropping telemetry a soundness fault, because a silent drop manufactures a blind
window, which manufactures a license, which corrupts a verdict. A component whose records can
quietly go missing without any gate noticing is that fault waiting to happen in the range instead of
in ingest.

The operator's fraction, the seed and the fully qualified `expect_red` assertion are not yet fixed;
Part II section 73.4 requires all three before the first source file.

## Not yet decided

- **The directory path.** The roster line says `java/`. Part I section 31.10 said
  `java/lab-service/` and `java/session-agent/`. Part II renamed the observed environment to the
  range and never restated a path, so a move to `range/java/` is plausible and unresolved. Decide
  before the first source file: Part II section 73.4's `paths` glob and the `ORPHAN_SOURCE` and
  `AMBIGUOUS_OWNERSHIP` lints key on it.
- **How many Tier B slots exist.** Part II section 73.1 lists Tier B as six languages, Java and C#
  among them. Part II section 75.5.1 lists Tier B as "Haskell, C, C++, one JVM language, x86-64
  asm" - five slots, with C# absent entirely. Both are Part II. If "one JVM language" is binding,
  Java and Kotlin cannot both be where they are, and C# needs a tier. Per KICKOFF section 2 this is
  a Part II-internal conflict that is not resolved silently here.
- **Whether this service is part of the live container range.** Part II section 75 rung D1 demotes
  the live container range to a non-normative realism check and permits deleting it outright, and
  Part II section 62.4 stamps range artifacts non-normative. If this service is inside that range,
  its cross-source gate cannot be normative either, and the Tier B promise has to be restated. If it
  is a Tier B artifact that survives D1, that has to be said in `docs/range/` before D1 is ever
  pulled.
- **The relationship to Kotlin.** Kotlin is Tier C on the same runtime (Part II section 73.1, API
  gateway with a logback JSON encoder). Whether the two share one toolchain component entry or two,
  and whether they share a build, is open.
- **The vendored JDK and the name-collision gate.** Part II section 73.10 notes that Eclipse
  Temurin is a JVM toolchain this repository actually vendors for Tier B, and Part II section
  73.10.2 bans the string from every machine-readable surface, enforced by
  `ECLIPSE_IN_ARTIFACT_SURFACE`. The gate has to be written so a vendored Temurin path in
  `toolchains.lock` and `vendor/` does not trip a ban that is about names this project authors. The
  exclusion has not been written.
- **Which authorization decisions the service makes**, and therefore which control atoms in
  `range/enforcement.toml` (Part II section 62.4.2) bind to it. A control atom with no enforcement
  point here is an excluded atom under Part II section 62.4, and a cut containing an excluded atom
  may not be reported as range-corroborated.
