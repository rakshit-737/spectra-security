# Pre-registration 0001: the controlled blackout cell

Status: **REGISTERED 2026-09-21, before the intervention was implemented or run.** The commit
that adds this file is the timestamp. Nothing below may be changed after the run; a revision is a
new pre-registration that cites this one.

## Why this exists

The two-cell demonstration compares full telemetry against a degraded cell. The degraded cell was
70% completeness with random, delete-only, block-structured removal. Its runs showed that it cannot
test the thing it was meant to test: the deletion removed route A's observed reads along with
everything else, so neither program derives any goal fact and the blindness premium there is empty
for a reason that has nothing to do with what a sensor could see (`BUILD_LOG.md` INC-0007,
INC-0008).

Random completeness is the right design for the degradation MATRIX, where the question is how
quality falls off across many cells. It is the wrong design for a single demonstration, where the
question is whether blinding ONE sensor produces the predicted premium. That needs a controlled
intervention that varies one thing.

## The intervention

`WHOLE_SOURCE_BLACKOUT`, as defined in specification Part II section 61: delete every record emitted
by the named source within a window, and nothing else.

| Parameter | Value |
| --- | --- |
| source | `src:iam_audit` |
| window | `[epoch + 4200 s, epoch + 4800 s)` - 10 minutes |
| every other source | untouched |
| every other parameter | as in the full-telemetry cell: same scenario, same generator seed, same rule table, same controls, same liveness configuration, same calibration profile |

### Why this window

It is chosen from the SCENARIO DEFINITION, not from any run output. `config/vs/scenario.toml` places
the escalation route's two iam_audit records at `+4499 s` (the approval) and `+4500 s` (step k7,
`role_assumed`). The window covers both with margin on each side. It does not touch route A, whose
observed steps are on `idp_auth`, `gw_access` and `res_access`.

## Predictions

The full-telemetry cell has already been run and is restated here only as the reference.

| Quantity | Full telemetry (observed) | Blackout cell (PREDICTED) |
| --- | --- | --- |
| `|Psi_min|` | 1 | **1** - route A, fully observed, unaffected |
| `|Psi_max|` | 1 | **2** - route A, plus route B through a licensed escalation |
| blindness premium | EMPTY | **{ctl:priv_approval}** |

### The mechanism the prediction rests on

With the approval and the escalation deleted, iam_audit has no records in the window, so the window
is not LIVE. Rule r0004 (`privilege.escalated <- iam.role_assumed`, `silent_possible = true`) is
then licensed there. Rule r0005 requires that escalation to precede the observed export at
`+4560 s` by at most 30 minutes; the licensed escalation's window overlaps `[+2760 s, +4560 s)`, so
some placement satisfies it and route B becomes derivable in P_max. Route B is severed only by
`priv_approval`, and route A in P_min does not need it. Hence the premium.

At full telemetry the same rule is licensed only in the horizon's edge windows, which cannot meet
the export under the 30-minute bound. That is why the control arm is empty and this cell is
predicted not to be.

## What falsifies it

Any of these is a failed prediction and is reported as one:

- the premium in the blackout cell is empty;
- it contains any control other than `ctl:priv_approval`;
- `|Psi_min|` differs from 1, meaning the blackout disturbed route A;
- `|Psi_max|` differs from 2.

## A confound named in advance

`src:iam_audit` has integrity class `chained`. Deleting records from a chained source leaves a
sequence gap, which the liveness stage is designed to classify as SUPPRESSED rather than BLIND, and
it may set `tamper_suspected`. A SUPPRESSED window still licenses silent instances, so the premium
prediction is unaffected. But a tamper flag is soundness-affecting, so a ROBUST verdict becomes
unconstructible in that cell. If that happens it is the system behaving correctly - a sensor whose
records vanished from a hash chain IS suspicious - and it is reported as such, not treated as a
failure of the prediction.

## Commitments

- The source, the window and the predictions above are fixed by this commit.
- If the prediction fails, the window will not be moved, widened or narrowed afterwards. A different
  window is a new pre-registration.
- The random 70% cell is not deleted. It is kept, and reported, as a degradation-matrix cell.
