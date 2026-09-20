# ADR-0006: Part II of the specification overrides Part I

## Status

Accepted — 2026-09-20

## Context

The build specification for SPECTRA is in two parts, in `docs/prompt/`.

**Part I** is sections 0 to 56, in `docs/prompt/part1/`. It is the original, complete design
document: the data model, the state model, the temporal and causal layer, the kernel stages, the
replay interaction, the lab range, the language roster, the repository layout, the API, the
frontend, the verification tiers, the benchmark harness and the delivery plan.

**Part II** is sections 57 to 76, in `docs/prompt/part2/`. It is a hardening addendum, written
afterwards, in response to three independent critical reviews that found real defects in Part I. It
does not replace Part I. It re-opens twenty specific areas — vocabulary, determinism, ingest, entity
resolution, degradation, oracles, the guard language, well-definedness, liveness, the verdict
algebra, the kernel threat model, the certificate, the kernel boundary, pre-registration, the claims
registry, the narration boundary, the language roster, the build and CI budget, the non-goals, and
the hypothesis object — and states what should have been said the first time.

Two documents describing one system will disagree. The question is what an implementer does when
they do.

The audit is in `docs/plan/CONFLICTS.md`. Twenty agents each compared one Part II section against
its Part I counterparts, and the findings fall into three classes:

| Class | Count in `docs/plan/CONFLICTS.md` | Meaning |
| --- | --- | --- |
| RESOLVED | 100 after deduplication | Part II explicitly overrides and says so. Follow Part II. No decision needed. |
| SILENT | 213 | Part II contradicts Part I **without** marking it an override. |
| UNRESOLVED | 140 | The two disagree and Part II does not settle it. A human decision is required. |

The SILENT class is the dangerous one, and it is the reason this record exists rather than being a
single line in a README. A silent contradiction is not visible from either document alone. An
implementer who opens Part I section 32.4 and builds the crate layout it specifies has done exactly
what the document in front of them said, and has built the superseded thing. The same is true of
Part I's exit-code convention, its enforcement mechanism for the language roster, its per-push CI
schedule, and two hundred and nine others. Nothing in the Part I text warns them.

The volume is itself a finding. A specification needing this many reconciliations is not buildable
as written. That is the expected state after a hardening pass is bolted onto a finished draft, and
it is why Part II exists — but it means the next work item is reconciliation, not implementation.

## Decision

**Part II overrides Part I wherever they conflict.** Where Part II marks an override, the Part I
text is dead and must not be satisfied. No attempt is made to satisfy both.

Four rules follow.

**1. The override applies whether or not Part II says so.** A contradiction that Part II did not
mark is still an override; it is a documentation defect, not a licence to choose. The classification
in `docs/plan/CONFLICTS.md` decides which is which, not the reader's judgement at the call site.

**2. The 213 SILENT contradictions are pushed back into the Part II sources as explicit override
lines, before any engine section is implemented.** Part II's own sections already carry lines of the
form "OVERRIDES Part I: ..." where the addendum's authors noticed. The reconciliation work is to add
the missing ones, so that a reader of Part II sees every place Part I has been superseded, and a
reader who then opens Part I has been warned.

**3. Editing the specification sources is permitted in exactly this one way and no other.** Files
under `docs/prompt/` are input artifacts. The only admissible edit is adding an explicit override
line that records a contradiction the audit already found, and each such edit cites the finding
identifier from `docs/plan/CONFLICTS.md`. No requirement may be changed, softened, added or removed
under cover of reconciliation. If a reconciliation looks like it needs a requirement changed, it is
not a SILENT finding — it is an UNRESOLVED one, and rule 4 applies.

**4. An unresolved conflict is not settled silently.** Where the two disagree and Part II does not
settle it, the implementer stops and asks. In practice the 140 UNRESOLVED findings are carried on
recorded conservative defaults so that work is not blocked; that mechanism is ADR-0008, and its
first rule is that a default is not an answer.

What this does not decide: it does not say which side is right in any particular UNRESOLVED
finding, and it does not make Part II internally consistent. Part II contradicts itself in at least
one recorded case, and contradicts Part I's own internal numbering in another; those are UNRESOLVED
findings like any other.

## Consequences

**A reader of Part I alone is not a competent implementer, and every artifact must say so.** This is
the sharpest consequence and the easiest to forget. Part I is longer, more complete, better
organised and reads like the authoritative document, because for a while it was. Any document,
comment or record that cites a Part I section for a superseded behaviour is wrong, and the reader
has no local way to tell. Until rule 2's work is done, the only reliable procedure is to check
`docs/plan/CONFLICTS.md` before relying on a Part I passage in a contested area.

**Reconciliation is the next work item, ahead of implementation.** Two hundred and thirteen override
lines is real work, it produces no running code, and it will be tempting to skip in favour of
building something. Skipping it means building superseded behaviour in some unknown subset of the
engine, discovering it at gate time, and rewriting. The ordering is stated here so that departing
from it is a visible decision rather than a drift.

**The specification becomes partly a living document, which is a risk.** Rule 3 exists to bound it.
Once edits to `docs/prompt/` are permitted at all, the pressure to make one more small clarifying
edit is continuous, and every such edit erodes the distinction between what was asked for and what
was chosen. The citation requirement — every override line naming a finding identifier — is what
makes an out-of-scope edit visible in review. ADR-0001 keeps decisions in `docs/adr/` precisely so
that they never have to be made inside the specification.

**The counts are claims and are bound to their artifact.** The three numbers in the table above come
from `docs/plan/CONFLICTS.md` and from nowhere else. They will move: deduplication is imperfect, and
pushing override lines into Part II converts SILENT findings into RESOLVED ones, which is the point.
Any document quoting them quotes the artifact in the same sentence, and when the claims registry
lands they are registered like any other externally visible numeral.

**Two documents stay in the tree, and the older one stays wrong.** Part I is not edited into
correctness and not deleted. This is the same trade ADR-0001 makes for superseded records: a visible
wrong document with a visible successor is safer than a silent rewrite, and in this case Part I is
also the only record of what the design looked like before three reviews hit it.

**What this does not establish.** Nothing here is a statement that the specification is now
consistent, correct or complete. It is a rule for what to do when it is not. The implementation
status of every section either part describes is "not started".

## Alternatives considered

### Merge Part I and Part II into one reconciled document

The strongest case by far: one document, no override rule, no audit to consult, no chance of reading
a superseded passage. It is what a specification should look like, and anyone joining the project
would thank whoever did it.

Rejected for now on scope and on evidence. The merge is a rewrite of roughly thirty thousand lines
with 353 known reconciliations in it, of which 140 are not yet decided — so the merge cannot even be
performed until ADR-0008's queue is largely answered. Attempting it first would mean making 140
decisions under merge pressure rather than on their merits. The override lines required by rule 2
are the cheap approximation: they put the warning where the reader is, without rewriting the text.
If the queue is answered, a merge becomes possible and this record should be superseded by one that
orders it.

### Treat Part I as advisory and Part II as normative

Simple to state. Rejected because it is false: Part II re-opens twenty areas and is silent on
everything else. The data model, the state model, the temporal layer, the replay interaction and
most of the engine exist only in Part I. Demoting it would leave most of the system unspecified.

### Decide conflicts at the call site, case by case

Rejected because it makes the specification's meaning a function of who is implementing which part
on which day, and leaves no artifact behind. It is also precisely what the audit exists to prevent:
the value of `docs/plan/CONFLICTS.md` is that the comparison was done once, deliberately, by readers
who were looking for contradictions rather than implementing around them.

## References

- `docs/prompt/part1/` — Part I, sections 0 to 56.
- `docs/prompt/part2/` — Part II, sections 57 to 76.
- `docs/plan/CONFLICTS.md` — the audit, its three classes and its per-section coverage table.
- `docs/plan/CONFLICTS_FULL.md` — the unabridged audit with quotations from both sides.
- `docs/plan/DECISIONS.md` — the 140 unresolved findings reduced to answerable questions.
- `KICKOFF.md` section 2 — the origin of the override rule.
- ADR-0008 — how the unresolved findings are carried without stalling.
