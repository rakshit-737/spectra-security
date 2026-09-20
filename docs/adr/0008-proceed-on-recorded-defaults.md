# ADR-0008: Build proceeds on recorded conservative defaults

## Status

Accepted — 2026-09-20

## Context

`docs/plan/CONFLICTS.md` classifies 140 disagreements between Part I and Part II of the
specification as UNRESOLVED: the two parts disagree and Part II does not settle it. ADR-0006 fixes
the override rule for everything else; these are the cases the override rule cannot decide, because
there is nothing to override — Part II simply does not address the point, or addresses it in a way
that contradicts itself.

`KICKOFF.md` section 2 is explicit about what to do: "Where you find a conflict Part II does not
resolve, stop and ask the human — do not pick one silently." That instruction is correct and it is
also, taken literally, a deadlock. The distribution in `docs/plan/DECISIONS.md` shows why: 66 of the
140 block milestones M0 through M3, and 42 of those are classified HIGH severity, meaning that
deciding wrongly means rewritten code or invalidated published results. The earliest milestone —
a clone that builds, lints and tests an empty system offline — is itself blocked by 19 of them.

So there are three available postures and each has a failure mode.

**Stop and wait for all of them.** Honest and unworkable. Nothing is built until a human answers
140 questions, most of which cannot be answered well in the abstract, and several of which will
only become answerable once something exists to answer them against.

**Pick one and move on.** This is what happens by default and it is the posture this record exists
to forbid. The problem is not that a guess is made; it is that a guess becomes indistinguishable
from a decision within about a week. The code compiles, the test passes, and six months later
nobody can tell which lines rest on a considered choice and which rest on whatever seemed
reasonable on a Tuesday. When the real answer arrives, there is no way to find the sites that
assumed otherwise.

**Proceed on a written default.** The middle path, and the one already prepared: the triage in
`docs/plan/DECISIONS.md` reduced each of the 140 to one answerable question and attached a default
to it, chosen to be the conservative option — the one that fails closed, keeps a claim weaker, or
keeps a type wider. That file's own framing states the principle: proceeding on defaults is
legitimate; silently proceeding on a guess is not, which is why each one is written down.

## Decision

The build proceeds on the recorded defaults in `docs/plan/DECISIONS.md`, under six rules.

**1. A default exists in writing before it is built on.** Every default has a decision identifier, a
severity, the milestone it blocks, the question stated so that it can be answered yes or no, the
context with the conflicting passages, and the default itself. A conflict discovered later that has
no row gets a row before any code depends on it. There is no such thing as an unwritten default.

**2. A default is conservative by construction.** Where the options differ, the default is the one
that fails closed, states a weaker claim, keeps a type wider, keeps a gate stricter, or preserves
the ability to change its mind. This is what makes proceeding safe: the cost of a wrong default is
work, not a false claim. A default that would make an output stronger, a verdict more confident or
a gate more permissive is not a valid default and the question has to be answered instead.

**3. Building on a default is cited at the site.** An implementation that rests on a default names
the decision identifier where it rests — in a comment at the site, and in the commit that
introduces it. This is the rule that makes the default findable later. Without it, rule 1 produces
a document nobody can connect to the code.

**4. A default is not an answer.** It may not be cited as a settled decision, in an ADR, in the
claims registry, in a paper, in a README, or in a commit message that describes it as decided. It
may not be used to close the question it defaults. A row in `DECISIONS.md` stays open until a human
answers it, regardless of how much code has been written on top of it.

**5. An answer is recorded where the default was, and escalates if it is architectural.** When a
question is answered, the answer and its date go into `docs/plan/DECISIONS.md` against the same
identifier. If the answer changes an architectural commitment, it additionally becomes an ADR — a
new one, superseding an earlier record if there is one to supersede, never an edit (ADR-0001).

**6. Severity drives the order of asking, and survival is visible.** The HIGH-severity defaults
blocking the earliest milestones are surfaced for answering first. A HIGH-severity default that
survives to a tagged release is named in the release notes as an open question the release was
built on. Shipping on defaults is permitted; shipping while implying the questions were answered is
not.

What this does not decide: any of the 140 questions. This record decides only how they are carried.

## Consequences

**Rework is accepted, and rule 2 is what bounds it.** Some defaults will turn out wrong, and the
code resting on them will be rewritten. Because every default fails closed, the failure mode of a
wrong default is wasted work rather than a published result that has to be withdrawn. That
asymmetry is the entire argument for this posture, and it is why rule 2 is not negotiable: a
default chosen for convenience rather than conservatism converts a work risk into a correctness
risk and breaks the deal.

**The decision queue becomes a standing artifact, not a one-off audit.** `docs/plan/DECISIONS.md`
has to stay accurate — its status line, currently recording that all 140 are open and none are
answered, is a claim like any other and goes stale the moment an answer is given anywhere but
there. A queue that drifts from reality is worse than no queue, because it will be trusted.

**Citation discipline is the rule most likely to erode.** Rules 1, 2 and 4 are policy and are
checked by reading; rule 3 is a habit, applied dozens of times, under time pressure, at the moment
of writing code. If it lapses, the whole scheme degenerates into the "pick one and move on" posture
with a document beside it that nobody can use. A lint that checks decision identifiers cited in the
tree resolve to rows in the queue — and, eventually, that HIGH-severity rows blocking a completed
milestone have citations somewhere — is work this decision creates and does not yet exist.

**Some questions get easier by waiting, and that is a legitimate reason to wait.** Several of the
140 concern behaviour under conditions nothing can produce yet. Carrying those on defaults until
there is something to try them against is better than answering them in the abstract. Rule 6's
ordering by severity and milestone is meant to separate those from the ones that are simply
unanswered.

**The count is a claim and is bound to its artifact.** The figures in this record — 140, 66, 42, 19
— come from `docs/plan/CONFLICTS.md` and `docs/plan/DECISIONS.md` and from nowhere else. They move
as questions are answered. Any document quoting them quotes the artifact in the same sentence.

**Honesty at release time has a specific shape.** A release built on open HIGH-severity defaults
says so. This is uncomfortable in exactly the place where it is most valuable: a reader evaluating
the repository can see which of its commitments are decided and which are merely unchallenged.
ADR-0009 explains why that visibility is the price of being public early.

**What this does not establish.** Nothing here makes a default correct, and nothing here is a claim
about SPECTRA's behaviour. Every component the 140 questions concern is unimplemented. Status: not
started.

## Alternatives considered

### Answer all 140 before writing any code

The strongest case, and it is the instruction in `KICKOFF.md`: it is the only posture with no
rework, no citation discipline to maintain, and no risk that a default hardens into an assumption.
For a smaller queue it would plainly be right.

Rejected on arithmetic. A meaningful answer to many of these requires context that only exists once
something runs, and the earliest milestone is itself blocked by 19 of them. The likely outcome of
attempting it is not 140 good answers; it is 140 fast ones, made in a batch, with no code to test
any of them against, and no record of which were solid. Rule 4 preserves the part of the
instruction that matters — nothing is silently decided — while letting the build start.

### Answer only the HIGH-severity ones blocking the early milestones, then start

A reasonable middle position, and in practice it is what rule 6 produces. It is not adopted as the
*rule* because it still stops the build on a batch of 42 decisions, and because the distinction
between "must answer now" and "can ride on a default" is exactly the judgement the severity and
milestone columns already encode. Rule 6 orders the asking without blocking on it.

### Proceed on defaults without recording them

The status quo of most projects, and it is fast. Rejected because it is the specific failure this
record exists to prevent: the code becomes the only record of the decision, and the decision becomes
unfindable at the moment it is finally answered.

### Treat each default as a decision and write an ADR for it

Rejected because it would produce 140 records for questions nobody has answered, and would break the
meaning of `Accepted` in ADR-0001's status vocabulary. The distinction between the two directories
is the point: `docs/adr/` holds decisions taken, `docs/plan/DECISIONS.md` holds questions open. A
default that is promoted to an ADR before it is answered is a default that has stopped being visible
as one.

## References

- `docs/plan/DECISIONS.md` — the queue, the severities, the blocking milestones and the defaults.
- `docs/plan/CONFLICTS.md` — the audit that produced the UNRESOLVED class.
- `KICKOFF.md` section 2 — the stop-and-ask instruction this record works within.
- `docs/plan/PLAN_v1.md` — the milestones the severities are keyed to.
- ADR-0001 — why an answered question becomes a new record rather than an edit.
- ADR-0006 — the override rule that handles everything outside the UNRESOLVED class.
- ADR-0009 — why open questions are stated publicly rather than held back.
