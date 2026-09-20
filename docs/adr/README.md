# Architecture decision records

Status of the system these records describe: **not started.** This is session one. Nothing in
SPECTRA is implemented — no kernel, no checker, no generator, no ingest, no API, no frontend. Every
component's implementation status is "not started".

An ADR in this directory records a decision that has been **taken**. It does not record a capability
that exists. The two are different things and this directory never conflates them.

---

## 1. What an ADR is here

One file per decision, in the standard Nygard format, with exactly these headings and in this order:

```
# ADR-NNNN: Title

## Status
## Context
## Decision
## Consequences
```

- **Title** — a short declarative sentence naming the decision, not the topic. "Apache-2.0 as the
  single licence", not "Licensing".
- **Status** — see section 3. This is the status of the *decision*, never the status of any code.
- **Context** — the forces in play: what the specification says, where its two parts disagree, what
  is unresolved, what a reader would otherwise assume. Written so that someone who has not read the
  specification can follow the argument.
- **Decision** — what was decided, in the active voice, as a commitment.
- **Consequences** — what follows, good and bad, including the costs accepted and the work the
  decision creates. A Consequences section that lists only benefits is not finished.

Optional sections may follow Consequences (`## Alternatives considered`, `## References`,
`## Open questions`). Nothing may be inserted before or between the four required ones.

## 2. Numbering and file names

- Four digits, zero padded, monotonically increasing: 0001, 0002, and onward.
- File name is `NNNN-kebab-case-title.md`, lowercase ASCII, hyphen separated.
- Numbers are never reused, never renumbered, and gaps are never backfilled. A number that was
  allocated and abandoned stays abandoned.
- `0000-template.md` is the template. It is not a decision.
- The internal acronym for the proof kernel may not appear in any file name in this repository
  (ADR-0004). A record *about* that ban is named for what it decides, not for the banned string.

## 3. Status vocabulary

The Status line is one of exactly these, followed by the date the status was reached in `YYYY-MM-DD`
form:

| Status | Meaning |
| --- | --- |
| `Proposed` | Written, not yet agreed. May still be withdrawn without a superseding record. |
| `Accepted` | Agreed. Binding on the build until superseded. |
| `Superseded by ADR-NNNN` | A later record replaced this decision. The text below is unchanged and still readable. |
| `Deprecated` | The decision no longer applies and nothing replaced it — the thing it governed was removed. |

**`Accepted` says nothing about implementation.** An accepted ADR whose subject is entirely
unimplemented is the normal case in this repository today. Implementation status belongs in the
README's generated status table, never here.

## 4. The immutability rule

**An ADR is immutable once merged.**

After a record is merged, the only permitted modification to its file is its Status line, and only
to move it to `Superseded by ADR-NNNN` or `Deprecated`. Nothing else may be edited: not the Context,
not the Decision, not the Consequences, not a factual error, not a typo, not a stale link.

A reversal, a correction, a refinement or a partial retreat is **a new ADR that supersedes the old
one**. The new record names what it supersedes and says why the earlier reasoning did not hold. The
old record stays in the tree, wrong and readable.

The reason is not ceremony. These records are the only place that will explain, later, why a thing
was built the way it was. A record that can be edited records the present opinion; a record that
cannot records the decision. Editing an ADR to match what was actually built destroys the one
artifact that could have shown the drift.

Because the repository is public from the first commit (ADR-0009), an ADR's history is permanent and
visible. That is intended.

## 5. When to write one

Write an ADR when a choice is (a) architecturally significant — it constrains later work, or costs
real rework to reverse — and (b) not obvious to a competent reader from the code alone.

Write one when:

- a name enters a machine-readable surface (module paths, crate names, binaries, wire fields);
- a boundary between two components is fixed (process, protocol, serialization, ownership);
- a specification conflict is settled in a way a reader of the specification would not predict;
- a repository-wide policy is adopted (licence, honesty gates, roster rules).

Do not write one for a reversible local choice, a dependency version bump, or anything a comment at
the call site explains adequately.

## 6. Relationship to the other planning artifacts

| Artifact | Holds |
| --- | --- |
| `docs/adr/` | Decisions taken, immutable, one per file. |
| `docs/plan/CONFLICTS.md` | The audit of where Part I and Part II of the specification disagree. |
| `docs/plan/DECISIONS.md` | The queue of specification conflicts that are **not** decided, each with a conservative default (ADR-0008). |
| `docs/plan/PLAN_v1.md` | Milestones, minimum publishable core, descope ladder. |
| `docs/claims.md` (not written) | Every externally visible claim, bound to the artifact that supports it. |

A row in `DECISIONS.md` that gets answered may become an ADR. A default that is merely being built
on never becomes one — a default is not an answer, and ADR-0008 exists to keep that distinction
visible.

## 7. Numerals in these records

A numeral in an ADR is one of: a section reference into the specification, an ADR or decision
identifier, a date, or a count of rows in a named planning artifact in this repository. The last
kind is stated together with the artifact it came from, in the same sentence, every time.

The leading four digits of a record's file name are an identifier, not a count. A gate that looks
for unbacked counts next to particular words must not read an ADR file name or a link to one as a
count — `0007-polyglot-tiers-and-the-mutation-audit.md` names a record, not a quantity of anything.

No ADR states a measurement, a benchmark, a throughput, a latency, a size or a quality figure. When
`docs/claims.md` lands, the counts cited here are registered with it like any other externally
visible numeral.

## 8. Index

| ADR | Title | Status | Decides |
| --- | --- | --- | --- |
| [0000](0000-template.md) | Template | — | The shape of a record. Not a decision. |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | That this directory exists, in Nygard format, immutable once merged. |
| [0002](0002-apache-2-licence.md) | Apache-2.0 as the single licence | Accepted | Apache-2.0 over MIT; the patent grant; the NOTICE obligation. |
| [0003](0003-repository-and-module-naming.md) | Repository, account and module naming | Accepted | `rakshit-737/spectra-security`; the Go module prefix; `spectra-*` crates. |
| [0004](0004-the-kernel-acronym-is-prose-only.md) | The proof-kernel acronym stays in prose | Accepted | The acronym is bound on first use and banned from every name. |
| [0005](0005-kernel-boundary-is-a-subprocess.md) | The kernel boundary is a subprocess over content-addressed files | Accepted | No in-process bindings; file-in / file-out binaries; the ABI's shape. |
| [0006](0006-part-two-overrides-part-one.md) | Part II of the specification overrides Part I | Accepted | The override rule, and that silent contradictions go back into Part II. |
| [0007](0007-polyglot-tiers-and-the-mutation-audit.md) | The language surface is kept and made falsifiable | Accepted | `make polyglot-audit`; the load-bearing test; deletion over rationale. |
| [0008](0008-proceed-on-recorded-defaults.md) | Build proceeds on recorded conservative defaults | Accepted | How unresolved specification conflicts are carried without stalling. |
| [0009](0009-public-repository-from-day-one.md) | The repository is public from the first commit | Accepted | Public while pre-alpha, and the honesty obligations that creates. |

Add the index row in the same change that adds the record. An ADR file with no index row, or an
index row with no file, is an error.
