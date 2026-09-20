# ADR-0010: Correct the conflict count recorded in ADR-0006

## Status

Accepted — 2026-09-20

Supersedes ADR-0006.

## Context

ADR-0006 recorded the decision that Part II of the specification overrides Part I, and cited the
size of the problem as evidence for rejecting an immediate merge of the two parts. It stated:

> The merge is a rewrite of roughly thirty thousand lines with 353 known reconciliations in it, of
> which 140 are not yet decided [...]

The figure 353 is wrong. `docs/plan/CONFLICTS.md` records three classes, and its own summary table
gives them as 100 RESOLVED after deduplication, 213 SILENT and 140 UNRESOLVED. The total is **453**,
not 353. The error was arithmetic, made when the audit results were first summarised, and it
propagated from there into ADR-0006, `BUILD_LOG.md`, `CONTRIBUTORS.md` and `docs/plan/README.md`.

It was found by the skeleton self-audit, which checks that every numeral reading as a measurement
either carries the illustrative tag or is a correct count of rows in a named artifact. 353 was
neither.

ADR-0001 establishes that a merged record is immutable, and that the only permitted edit to it is
its Status line. A factual correction is therefore a new record that supersedes the old one, not an
edit. That rule exists so that a reader can see what was believed at the time and what changed;
editing 353 to 453 in place would have hidden the error instead of recording it.

This record exists to demonstrate that the rule is followed even when the correction is small and
the edit would have been trivial. A rule that is suspended for small cases is not a rule.

## Decision

ADR-0006's decision is unchanged and is restated here in full force:

1. Part II of the specification overrides Part I wherever they conflict.
2. Every override is marked inline in the Part II source with a line beginning `OVERRIDES Part I:`.
3. The two parts are not merged into one document until the unresolved conflicts are decided.

The only change is the figure. The corrected sentence reads:

> The merge is a rewrite of roughly thirty thousand lines with 453 known reconciliations in it, of
> which 140 are not yet decided.

The corrected class breakdown, sourced to `docs/plan/CONFLICTS.md`:

| Class | Count | Meaning |
| --- | ---: | --- |
| RESOLVED | 100 | Part II overrides Part I explicitly. Follow Part II. |
| SILENT | 213 | Part II contradicts Part I without marking it. |
| UNRESOLVED | 140 | Neither part settles it. Needs a decision. |
| **Total** | **453** | |

ADR-0006's Status line is changed to `Superseded by ADR-0010`. No other line of ADR-0006 is edited.
It remains in the tree carrying the wrong number, which is the point of the immutability rule.

## Consequences

- The reasoning in ADR-0006 is strengthened, not weakened: a larger reconciliation burden is a
  stronger argument against merging the two parts now, so the decision it reached holds a fortiori.
- ADR-0006 stays readable with its error intact. Anyone comparing the two records can see exactly
  what was wrong and when it was caught.
- Every other occurrence of 353 as the conflict total is corrected in place, because those files
  are not immutable: `BUILD_LOG.md`, `CONTRIBUTORS.md` and `docs/plan/README.md`.
- A superseding record for a single wrong numeral is heavy. That cost is accepted. The alternative
  is a case-by-case judgement about which corrections are small enough to make silently, and that
  judgement is exactly what the immutability rule removes.
- The claims gate described in `CLAIMS.md` would have caught this before it was committed. It is
  not implemented. Until it is, numerals in this repository are checked by reading, which is how
  this one survived four files.

## References

- ADR-0001, the immutability rule.
- ADR-0006, superseded by this record.
- `docs/plan/CONFLICTS.md`, the artifact the counts are read from.
