# ADR-NNNN: A short declarative sentence naming the decision

## Status

Proposed — YYYY-MM-DD

<!--
One line. One of:
  Proposed — YYYY-MM-DD
  Accepted — YYYY-MM-DD
  Superseded by ADR-NNNN — YYYY-MM-DD
  Deprecated — YYYY-MM-DD

This is the status of the DECISION. It is never the status of any code. Every component of SPECTRA
is currently "not started"; an Accepted ADR does not change that and must not be read as changing it.

Once this record is merged, this line is the only line in the file that may ever be edited, and only
to move to Superseded or Deprecated. Everything else is immutable. A correction is a new ADR.
-->

## Context

<!--
The forces, stated so that a reader who has not read the specification can follow the argument.
Cover, as applicable:

  - What the specification says, with section references (Part I 01-56, Part II 57-76).
    Part II overrides Part I: ADR-0006.
  - Where the two parts disagree, and whether docs/plan/CONFLICTS.md classifies the disagreement as
    RESOLVED, SILENT or UNRESOLVED.
  - Whether an UNRESOLVED conflict is involved, and if so its decision id in docs/plan/DECISIONS.md
    and what its recorded default is. Building on a default is legitimate; ADR-0008 says how.
  - What a competent reader would otherwise assume, and why that assumption is wrong or costly.
  - The constraints that are not negotiable: offline, deterministic, no fabricated numerals, the
    proof kernel and the checker have no service dependencies, the narration layer is removable.

Write the forces, not the conclusion. If the Context does not make the Decision feel forced, either
the Context is incomplete or the decision is weaker than it looks. Say which.

No measurements. No benchmark figures. Any illustrative figure carries the exact tag
"(illustrative, not a target)" in the same sentence.
-->

## Decision

<!--
What was decided, in the active voice, as a commitment: "We will ...", "The repository is named ...",
"X is banned from ...". Present tense is permitted here, because a decision is a present fact.

It is NOT permitted for the thing decided about. Nothing is implemented. Write "the checker will be
a standalone binary", never "the checker is a standalone binary".

Be specific enough to be checkable. Name the files, targets, gate ids, identifiers and paths the
decision fixes. A decision nobody can test compliance against is a preference.

If the decision has a boundary, state what it does NOT decide.
-->

## Consequences

<!--
What follows. Both directions. A Consequences section that lists only benefits is not finished.

Cover, as applicable:

  - What becomes possible, and what becomes impossible.
  - The cost accepted, named plainly. If a cost is a real risk rather than a price, say so.
  - The work this creates: files to write, gates to add, lints that now have to exist, documents
    that must be regenerated.
  - What this decision does NOT establish. This is the section most often skipped and most often
    needed later.
  - What reversing this would cost, and what would have to change together.
  - Any claim this decision must not be allowed to become. A decision is not evidence.
-->

## Alternatives considered

<!--
Optional but strongly preferred. One subsection per alternative, each with why it was not taken. An
alternative rejected without a reason reads as an alternative never examined.

Steelman each one. If the rejected option has a genuinely good argument behind it, write the
argument down; a future reader reversing this decision deserves to start from the strongest version
of the case, not a caricature of it.
-->

## References

<!--
Optional. Specification sections, planning artifacts, decision ids, external standards or licence
texts. Link by path relative to the repository root. Do not link to anything that requires a network
fetch to understand this record.
-->
