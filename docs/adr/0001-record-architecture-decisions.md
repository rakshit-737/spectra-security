# ADR-0001: Record architecture decisions

## Status

Accepted — 2026-09-20

## Context

SPECTRA is being built from a specification of roughly thirty thousand lines across two parts, by a
single maintainer, in a repository that is public from its first commit (ADR-0009). Three properties
of that situation make undocumented decisions expensive.

**The specification does not settle everything.** The audit in `docs/plan/CONFLICTS.md` classifies
the disagreements between Part I and Part II into three buckets, and the bucket labelled UNRESOLVED
holds 140 conflicts that Part II does not settle. Each of those will be built on a recorded default
(ADR-0008). A default that is exercised and never explained is indistinguishable, six months later,
from a considered choice. The difference matters when the answer finally arrives.

**Several early choices are irreversible in practice rather than in principle.** Module paths,
crate names, wire field names, the process boundary between the orchestration layer and the proof
kernel, and the repository name itself are all cheap now and expensive after the first source file
that imports them. Each of those is a decision a future reader will question, and each has a reason
that is not visible in the resulting code.

**The specification is an input, not a record of what was decided.** It states requirements. It does
not state which of its own contradictions were resolved which way, why a superseded Part I passage
was abandoned, or which commitments were made in this repository rather than inherited from the
document. Reading the specification does not tell you what was decided; it tells you what was asked
for.

The usual failure mode is a decisions document that is a single growing file, edited whenever the
project's mind changes. That file eventually records only the current opinion. The thing worth
keeping — the fact that the project believed something else in March, and why — is exactly what
editing destroys.

Michael Nygard's architecture decision record format is the well-known answer: one file per
decision, four sections, numbered, append-only.

## Decision

We will record architecturally significant decisions as architecture decision records in
`docs/adr/`, one file per decision, in the Nygard format: Title, Status, Context, Decision,
Consequences.

The conventions are written in `docs/adr/README.md` and are binding:

1. **Numbering.** Four digits, zero padded, monotonically increasing, never reused, never
   renumbered, gaps never backfilled. File name `NNNN-kebab-case-title.md`.
2. **Immutability.** Once a record is merged, the only line that may ever be edited is the Status
   line, and only to move it to `Superseded by ADR-NNNN` or `Deprecated`. A reversal, a correction
   or a refinement is a new record that supersedes the old one. The old record stays in the tree,
   wrong and readable.
3. **Status is about the decision.** `Accepted` means the decision is binding on the build. It says
   nothing about whether anything has been implemented, and in this repository today nothing has.
   Implementation status belongs in the README's generated status table.
4. **Index.** `docs/adr/README.md` carries an index table. The row and the file are added in the
   same change.
5. **Numerals.** An ADR states no measurement and no benchmark figure. A count of rows in a planning
   artifact is stated together with the artifact it came from, in the same sentence.

This record is itself ADR-0001 and follows its own rules.

What this does not decide: it does not make ADRs the place where specification conflicts are
tracked. That is `docs/plan/CONFLICTS.md` for the audit and `docs/plan/DECISIONS.md` for the open
queue. An ADR appears when a conflict is *settled*, or when a commitment is made that the
specification did not dictate.

## Consequences

**A decision now costs a file.** Writing a record is friction, and friction is the point: it makes
the project notice when it is making an architectural commitment. The cost is real and accepted.
The mitigation is the scope rule in `docs/adr/README.md` section 5 — reversible local choices do
not get records.

**Wrong records stay in the tree.** A superseded ADR is not deleted and not corrected. A reader who
finds one and does not check its Status line will be misled. The mitigation is that the Status line
is the first thing under the title, and that a superseding record names its predecessor. This is a
deliberate trade: a visible wrong decision with a visible successor is safer than an invisible
edit.

**The record and the build can drift.** Nothing mechanically checks that the code obeys an accepted
ADR. Several of these records name a gate that is supposed to enforce them — `make abi-contract`,
`make polyglot-audit`, `make banned-phrase-gate` — but none of those gates exists yet. Until they
do, an ADR is a statement of intent with no enforcement behind it, and it must not be cited as
evidence that the thing it describes holds.

**A missing record is now a defect.** If a later reader finds an architectural commitment in the
tree with no ADR behind it, that is a gap to fill with a record written at the time it is noticed,
dated then, and honest about being retrospective.

**The public history is permanent.** Because the repository is public from the first commit,
superseded reasoning is visible to anyone who looks. That is intended: a project whose honesty gates
are its main contribution cannot keep a private history of what it used to believe.

## Alternatives considered

### A single `DECISIONS.md` that is edited as the project changes its mind

The strongest argument for it: one file is easier to read end to end, easier to search, and does not
require a numbering convention or an index. For a small project it is often enough.

Rejected because editing is precisely the operation that destroys the value. The question this
repository will actually be asked — by a reviewer, or by the maintainer in a year — is "why is the
kernel boundary a subprocess", and the answer has to include the option that was rejected and the
cost that was accepted. An edited file answers "what do you think now".

Note that a file of that name already exists here for a different purpose:
`docs/plan/DECISIONS.md` is the queue of *unanswered* specification conflicts and their defaults. It
is a work list, not a record of decisions taken, and ADR-0008 keeps the two apart.

### Recording decisions in commit messages only

Cheap, always in order, never out of date. Rejected because commit messages are not indexable by
topic, not supersedable, and not readable by someone who arrives at the repository through its
documentation rather than its history. A decision that can only be found by someone who already
knows to look for it is not recorded.

### Recording decisions in the specification sources

Rejected because the specification is an input artifact. ADR-0006 permits exactly one kind of edit
to it — adding explicit override lines that record contradictions the audit already found — and
nothing else. Mixing decisions into a document that is meant to be read as the requirement would
make it impossible to tell what was asked for from what was chosen.

## References

- `docs/adr/README.md` — the conventions in full.
- `docs/plan/CONFLICTS.md` — the Part I / Part II audit, and the source of the UNRESOLVED count.
- `docs/plan/DECISIONS.md` — the open decision queue and its defaults.
- Michael Nygard, "Documenting Architecture Decisions" (2011) — the origin of the format.
