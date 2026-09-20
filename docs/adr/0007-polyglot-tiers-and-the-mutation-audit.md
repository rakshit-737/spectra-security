# ADR-0007: The language surface is kept and made falsifiable by the mutation audit

## Status

Accepted — 2026-09-20

## Context

SPECTRA is designed with a deliberately wide language surface. This is not an accident of growth and
it is not a portfolio exercise, although it will be read as one by anybody who does not look
closely. The surface exists for a reason that is specific to what the system does.

The research property under test is *reconstruction across an estate the pipeline does not
understand*. The ingest path is supposed to take telemetry from a heterogeneous collection of
services and reconstruct how the security state evolved without knowing what wrote any of it. An
estate that is heterogeneous only in a fixture's `source` field is not evidence of anything. An
estate that is actually written in many different runtimes, emitting in their own idioms, is. That
is one tier of the roster. Another tier holds independently authored oracles and measured
alternative implementations, which are only worth having if they were written by a different tool
chain than the thing they check. A third holds narrow research artifacts that produce ground truth
nothing else can.

So the surface is a goal. The problem is that a wide surface is also the single easiest thing in
this repository to fake, and the failure mode is well known: a directory per language, a hello-world
inside it, a row in a README table, and a count that means nothing.

Part I's defence against that was prose. Section 30.1 required a written non-duplication rationale
per language in a rationale document, and section 32.1 stated the rule "a directory that could be
deleted with no loss must not exist". Both are judgement calls, and both fail in the same way: a
well-written rationale for a useless component is easier to produce than a useful component, and
"could be deleted with no loss" is a question nobody ever answers "yes" to about their own work.

Part II section 73 overrides both. It replaces the rationale document with an executable audit, and
restates the deletion rule as a mechanical predicate. The governing sentence is that every component
must be load-bearing: **something downstream must break when it is corrupted.**

There is a second, related honesty problem. A code-hosting language bar counts configuration and
markup formats alongside executing code, so the number it displays is always larger than the number
that means anything. Quoting the bar's number in prose is a small lie that is very easy to tell by
accident.

## Decision

The language surface is kept. It is not deleted, not quietly shrunk and not apologised for. What
changes is that it stops being a claim in a table and becomes a property a make target can refute.

**1. Every component declares four things, and three is a failure.**

| Check | Requirement | Failure |
| --- | --- | --- |
| Consumer edge | A named downstream artifact consuming this component's output, owned by a *different* component. Self-consumption, including "its own test suite", does not count. | `SELF_CONSUMING` |
| CI job | A named job that *executes* the component — not lints it, not builds it — on every change to its paths, at the cadence its tier permits. | — |
| Mutation | A declared, deterministic, seeded corruption of the component's **output** which, applied in a scratch worktree, turns a *named* downstream gate red, at a *named* assertion. | `MUTATION_UNDERSPECIFIED` |
| Role | One line saying what it does in the demo, in the degradation matrix, or in a published benchmark. | — |

**2. The manifest is `polyglot.toml` at the repository root**, one entry per component, with the
paths, the pinned toolchain, the offline source for that toolchain, the entrypoint, the promise, the
consumer, the CI job, the mutation and the role. Every executing source file in the tree is owned by
exactly one entry: unowned files fail `ORPHAN_SOURCE`, doubly owned files fail `AMBIGUOUS_OWNERSHIP`.
The promise field is linted for placeholder words, because a promise that says "demonstrates" or
"various" is not a promise.

**3. The mutation operator set is closed.** Corruptions are applied to a component's output, never
to its source, and are drawn from a fixed table: stub the entrypoint, empty the output, drop a
seeded fraction of records, truncate a field per record, flip a byte at a seeded offset, permute the
output under a seeded shuffle, return a constant result, widen a tolerance. Returning a constant is
mandatory for every independent oracle and every cross-check — an oracle whose gate still passes
while it returns a constant is not an oracle.

**4. `make polyglot-audit` is the only thing that licenses a component to remain in the tree.**
Prose rationale is demoted to explanatory commentary and may no longer be cited as satisfying any
gate. The audit runs offline, seeded, single-threaded in its decision path, and writes a machine
artifact plus a generated document. Its per-component verdict is load-bearing or padding, and any
padding exits non-zero.

**5. The response to a padding verdict is deletion, not documentation.** The admissible responses
are: give the component a real consumer edge, promote it to a tier whose promise it can meet, or
delete it. Writing a better rationale is not on the list. Deleted components are recorded in a
ledger with the date, the mutation that exposed them and the commit that removed them. The ledger
contains no argument for why the component was a good idea.

**6. Configuration and markup formats are never counted in a prose language claim.** JSON, YAML,
TOML, XML, HTML, CSS, SCSS, Dockerfile, Makefile, CMake and HCL are counted separately, always. The
language bar's row count is the size of a colour bar and is never used in a prose sentence.
Generated code, vendored code, fixtures and compiled artifacts are not counted at all.

**7. Counts in prose are substituted, not typed.** The README carries literal substitution tokens
which the docs build replaces from the audit's machine artifact. The tokens are what is committed;
the numbers are not. A surviving token in a built document fails `UNSUBSTITUTED_TOKEN`, and a
hand-typed numeral next to the words "language", "languages" or "polyglot" anywhere in the README or
under `docs/`, outside that generated block, fails `UNBACKED_COUNT`.

**8. The tier ladder, A through D, carries different promises and different CI cadence.** Tier A is
the critical path and runs in full on every push. Tier B adds oracles and measured comparisons, and
runs its changed-path jobs plus all differential gates per change, with the full audit and mutation
nightly. Tiers C and D run changed-path jobs per change and the full audit nightly. A red Tier C or
D job does not block a milestone — it appears in the generated status table within one commit — but
it blocks a tagged release. A job that fails intermittently is quarantined with a ledger entry and
is treated as padding at the next release gate unless it is fixed. Silencing a job with
`continue-on-error` or a disabling guard fails a lint.

**9. The ingest path contains no language-specific branch.** Adapters are keyed by wire format —
syslog, logfmt, line-delimited JSON, access-log patterns — never by the runtime that produced the
records. A grep gate fails the build if an adapter identifier, filename or conditional under the
ingest tree matches the name of an estate language. This is what turns the estate tier's promise
from a slogan into a property: the pipeline cannot be reconstructing across an unknown estate if it
has a branch that knows what wrote the records.

## Consequences

**Every component now costs a mutation harness.** Declaring a corruption, wiring it so the audit can
apply it in a scratch worktree, and naming the exact downstream assertion it must turn red is
substantially more work than writing a paragraph of rationale. This is the cost being deliberately
paid, and it is the reason the audit is credible.

**The audit has to run offline, with pinned toolchains, or it does not run at all.** Each entry
names a toolchain and an offline source for it, and the audit fails on a toolchain absent from the
lock file or an offline source missing from the vendored tree. One digest-pinned prebuilt image
holds the toolchains so that per-change jobs never install one. Keeping that image current, offline
and reproducible is standing work this decision creates.

**Deletion becomes routine, and must be allowed to be.** The predictable moment of failure is the
first time a component the maintainer likes comes back padding. The rule is written down in advance
precisely so that the argument at that moment is with this record rather than with the audit.

**A new language cannot be added casually.** Its manifest entry must pass all four checks before its
first source file is committed, and adding its path to an ignore file to dodge `ORPHAN_SOURCE` is
named as a violation rather than a workaround.

**The roster size is not a contribution and must never be presented as one.** The research property
is reconstruction across an estate whose implementation runtimes the pipeline does not know. The
size of the roster is a consequence of that, not evidence for it. A README that leads with a count
has inverted the claim.

**A specific set of things may not be said**, and they are worth listing because each is the
tempting sentence for its component: no claim of hardware acceleration, silicon or register-transfer
verification from simulated bounded-buffer models; no claim of blockchain anchoring, immutability or
tamper-proofing from a smart-contract artifact; no claim of endpoint telemetry coverage for
operating systems that are not supported; no claim of a speedup from a native comparison unless a
benchmark document shows it with its run manifest hash on declared hardware; no claim of formal
verification from an independently authored oracle, whose whole claim is that it independently
implements one relation; and no claim of compatibility with a numerical environment the code has
never been executed by.

**Two counts will always exist and must never be conflated.** The executing-component count and the
configuration-format count come from the audit artifact. The language bar's row count is the sum and
is not a sentence. Rule 7 is what keeps the distinction mechanical rather than remembered.

**Reversal cost is low, which is itself a consequence.** Cutting a whole tier is a rung on the
descope ladder in `docs/plan/PLAN_v1.md`, and the ladder cuts a tier as a unit rather than a
component at a time, so that the estate tier's promise does not decay silently into a smaller estate
that still calls itself heterogeneous.

**Which components actually survive is not decided here.** `docs/plan/DECISIONS.md` carries an open
question about the published roster — which runtimes keep a toolchain and a CI job at all — and it
sits on a recorded default under ADR-0008. This record decides the *test*, not the roster.

**What this does not establish.** No component in the roster exists yet. `polyglot.toml` does not
exist, `make polyglot-audit` does not exist, and no mutation has ever been run. Status: not started.
Nothing in this record may be cited as evidence that any component is load-bearing.

## Alternatives considered

### Shrink the surface to the critical path and delete the rest

The strongest case: it is smaller, cheaper, faster in CI, impossible to accuse of padding, and the
critical path is where all the difficult work is anyway. A reviewer sceptical of wide language
surfaces would find this repository easier to trust.

Rejected because deleting the estate tier deletes the research property. Reconstruction across an
estate the pipeline does not understand cannot be evidenced by an estate the pipeline wrote in one
runtime. The oracle and comparison tiers have the same character: their value is precisely that they
were written with different tools than the thing they check. The honest answer to the padding
accusation is an audit that could catch padding and does not, not a smaller surface.

### Keep the Part I approach: a written rationale per component

Rejected on the mechanism. A rationale is cheaper to write than a load-bearing component, which
means the enforcement pressure points the wrong way. Part II section 73 says this directly by
demoting rationale to commentary.

### Count every file the language bar counts, and say so

Honest in a narrow sense, and the simplest thing to maintain. Rejected because "counted by the
language bar" and "a language this project writes code in" are different sets, and a reader will
hear the second when told the first. Separating the counts and substituting them from an artifact
costs a docs-build step and removes a whole category of accidental overstatement.

## References

- Part II section 73 — the roster, the load-bearing test, the manifest, the operator set, the audit
  procedure, the README wording, the CI tiering and the negative requirements.
- Part I sections 30.1 and 32.1 — the superseded prose enforcement and the judgement-call rule.
- Part I section 43.1 — the superseded per-push per-language unit tier.
- `docs/plan/PLAN_v1.md` — the descope ladder, which cuts a tier as a unit.
- `docs/plan/DECISIONS.md` — the open question about which runtimes survive in the published roster.
- ADR-0008 — how that open question is carried.
- ADR-0009 — why a public repository makes the substitution rule load-bearing rather than tidy.
