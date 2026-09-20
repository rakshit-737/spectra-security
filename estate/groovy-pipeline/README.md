# Groovy - build and deploy pipeline in the observed estate
Tier: C
Status: not started
Owning spec section: 73
Milestone: M9

## The promise

The Tier C promise is stated in Part II section 73.1 and is the whole promise for this directory:

> SPECTRA reconstructs security state across services written in implementation languages the
> reconstruction pipeline knows nothing about.

This component is evidence for that property and for nothing else. It is a subject, not a tool. It
will not import a SPECTRA library, will not compile any SPECTRA component, will not author a
scenario, and will not know it is observed. Its obligation is to run a build and deploy pipeline
inside the estate and to emit the build and deploy events such a pipeline produces, which are then
ingested by a format adapter that contains no branch naming Groovy (section 73.3.4).

It promises no build system, no scenario authoring language and no readability result. Its value is
that the reconstruction path is indifferent to what wrote the records, and that it contributes the
events that give a deployed artifact an origin in the reconstructed state.

Nothing in this directory exists yet. Every statement above is a design obligation, not a
description of code.

## What lives here

When this directory is written, it is planned to contain:

- Groovy scripts for a pipeline in the estate: check out, build, publish an artifact, deploy it to a
  service host, record the outcome. Groovy version and JVM pinned to the toolchain lock file.
- A seeded driver so a run is reproducible from a seed alone, with no wall-clock and no random
  identifiers reaching the output.
- The pipeline's own event writer: build started, build finished, artifact published with its
  identity, deploy started, deploy finished, with the service account the pipeline ran as.
- Golden output bytes per seed, committed with LF endings.
- The component's entry in the root `polyglot.toml` with every field required by section 73.4.
- Conformance corpus entries for the declared `format_id`.

No code, no fixtures and no manifest entry exist at this time.

## Consumer edge

This is the component in this group whose consumer edge is least settled, and that has to be said
plainly rather than argued around. Section 73.6 allows exactly three responses to a padding verdict:
give the component a real consumer edge, promote it to a tier whose promise it can meet, or delete
it. Writing a better rationale is not one of them.

The intended edge: a committed scenario in which a deployed artifact is the origin of a later
process execution and of the service account that runs it. If this directory is deleted, that
scenario loses its build and deploy source, and:

1. The deployed artifact has no observed origin, so the process execution that follows it is no
   longer anchored to anything the pipeline recorded. The scenario's assertion that the running
   process resolves to the published artifact fails.
2. The scenario's bundle no longer contains the pipeline's records, so its bundle manifest hash gate
   fails against the committed expectation.

The risk, stated honestly: that edge exists only if a committed scenario actually grounds a rule on
a build or deploy event. No such scenario exists yet, and no rule table exists yet. If, when the
scenarios are written, nothing downstream depends on these events, then this component has no
consumer edge, `make polyglot-audit` will report it as padding, and the correct action is to delete
this directory and its manifest entry - not to document it more carefully.

Whatever the consumer turns out to be, it must be owned by a different component. Build logic whose
only consumer is its own build output would fail the audit with `SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-c / estate-groovy-pipeline`, declared in `.github/workflows/`, executing the
  pipeline rather than merely compiling the scripts (section 73.3.2).
- Tier: T2. Tier C language jobs and the polyglot mutation audit run nightly on `main`. A red Tier C
  job does not block a Tier A milestone; it appears in the README status table within one commit and
  blocks any tagged release (section 73.9, rules 1 and 2).
- Make target: `make polyglot-audit`, which is the only thing that licenses this component to remain
  in the tree. `make m9-verify` is the milestone proof target that must include it.

## Mutation check

Declared operator from the closed set in section 73.5: `truncate_output_fields`.

What is corrupted: in a scratch worktree, the final field is dropped from each emitted pipeline
record, so the artifact identity that the publish and deploy events carry is absent. The pipeline's
source is untouched; only its output is corrupted.

Which gate goes red: the scenario gate that asserts the running process resolves to the artifact the
pipeline published. Without the artifact identity on the deploy event, entity resolution cannot join
the deployment to the later process execution, the join is absent from the reconstructed state, and
the assertion fails.

The operator choice matters. `stub_entrypoint` would silence the source entirely, and a silent
source is a blind source, which the license machinery is built to absorb as a legal state; against a
content-sensitive assertion that mutation would be tolerated. `truncate_output_fields` keeps the
source live and removes exactly the field the downstream join depends on, which is what the
assertion is sensitive to.

## Not yet decided

1. **The directory path.** `estate/groovy-pipeline/` is proposed, not settled. Part II section 73.1
   replaced Part I section 31.15's role - Gradle build logic at `gradle/` plus a scenario authoring
   DSL at `scenario-dsl/` - with an observed build pipeline, and did not restate a path. The
   repository plan records the Tier B/C/D directory layout as an open decision.
2. **Whether any Gradle build logic remains in the repository, and who owns it.** Part I made Groovy
   the build system for the JVM components. Part II makes Groovy a subject. These cannot be one
   component: section 73.3.1 forbids self-consumption and section 73.4 fails a doubly-matched file
   with `AMBIGUOUS_OWNERSHIP`. Either the JVM components are built by something that is not authored
   Groovy, or the build logic becomes its own component with its own consumer edge and mutation.
   Undecided.
3. **Whether the scenario DSL survives at all.** Part II never restates it. A DSL that compiles to a
   scenario specification is a SPECTRA tool, which the estate rule forbids this component from
   being. If the DSL is kept, it is a separate component in a different tier; if it is not kept,
   scenarios are authored in a declared configuration format instead. Undecided.
4. **The declared format.** Section 73.1 describes the emission as build and deploy events without
   naming a shape. Section 59.6 defines a closed set of formats and forbids content sniffing, so one
   of its rows must be declared - `kv.logfmt` and `jsonl.v1` are the candidates - or the closed set
   must gain a row with its own grammar, adapter and corpus. Undecided.
5. **The toolchain image.** Section 74.1 puts the JVM in `spectra/toolchain-b` and the range-emitter
   runtimes in `spectra/toolchain-c`, and lists Groovy in neither. A subject that runs on the JVM
   sits awkwardly across that split. Undecided.
6. **The SourceId.** The service table in Part I section 26.3 has no row for a build pipeline and
   `range/sources.toml` has no SourceId for it. Liveness is computed per SourceId, so this blocks
   any liveness statement about this source.
7. **The gate id.** The downstream gate named in `mutation.expect_red` must be a registered id in
   `ci/gates.toml` with an owning section and a make target. No such gate is registered yet, so the
   mutation above names an assertion, not a committed identifier.
