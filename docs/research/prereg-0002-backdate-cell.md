# Pre-registration 0002: the backdate cell, and whether tampering can buy a stronger verdict

Status: **REGISTERED 2026-09-23, before the `BACKDATE` operator and the temporal-consistency pass
were implemented or run.** The commit that adds this file is the timestamp. Nothing below may be
changed after the run; a revision is a new pre-registration that cites this one.

## Why this exists

Part II section 65.6 rewrites Part I's backdating design because Part I's version is an attack on
SPECTRA. Part I voids licences resting on provably backdated timestamps; voiding a licence shrinks
`P_max`; a smaller `P_max` can only move a verdict toward ROBUST. An adversary who can rewrite
timestamps could therefore manufacture the strongest verdict SPECTRA issues. Section 65.6 replaces
voiding with a dispute protocol: a suspected licence stays in `P_max` with full force, and the
verdict is weakened instead.

[ADR-0016](../adr/0016-the-slice-implements-the-temporal-dispute-pass.md) brings that pass into the
slice. This registration fixes, in advance, what its first adversarial cell must show.

It also settles the confound pre-registration 0001 named and could not test. That registration said a
chained source with records missing "may set `tamper_suspected`", and no flag fired — not because the
chain was clean, but because no code could set one (`BUILD_LOG.md` INC-0011). The mechanism now
exists, so the claim becomes testable. This cell is not that test: it backdates rather than deletes,
and a separate registration would be needed to revisit 0001's cell.

## The intervention

`BACKDATE`, as defined in specification Part II section 61.4.7: rewrite recorded timestamps, and
nothing else. No record is added, removed or reordered by the operator.

| Parameter | Value |
| --- | --- |
| source | `src:iam_audit` |
| select | the single record of event type `iam_role_assumed`, which the scenario emits once |
| magnitude | `-2700 s` (45 minutes earlier) |
| every other record, source and parameter | untouched; completeness 1/1, same scenario, seed, rule table, controls, liveness configuration and calibration profile as the full-telemetry cell |

### Why this record and this magnitude

Both are read off `config/vs/scenario.toml`, not off any run. Attack step k7 emits exactly one
`iam_role_assumed` record on `iam_audit` at `epoch + 4500 s`. `iam_audit` is `chained` and carries
`seq`, and the scenario's noise families put many `iam_audit` records between `epoch + 1800 s` and
`epoch + 4500 s`. Moving k7's record to `epoch + 1800 s` while it keeps its sequence number puts it
before records that precede it in `seq`, which contradicts the source's own recorded order. That is
the smallest intervention that makes a timestamp provably inconsistent rather than merely surprising.

## The comparison

Every prediction below compares the SAME backdated cell with the temporal pass ON and OFF. The pass
is a switch on the cell, so nothing else differs between the two runs. Comparing the backdate cell
against the full-telemetry cell would confound the pass with the backdating itself: moving k7 by 45
minutes changes what the rule table grounds, and the absolute cut, premium and verdict of this cell
are NOT predicted here.

## Predictions

| Quantity | Pass OFF | Pass ON (PREDICTED) |
| --- | --- | --- |
| negative cycles found | not computed | **at least one** |
| correction set `C` | not computed | **exactly one event: the backdated `iam_role_assumed` record** |
| `tamper_suspected` sources | none, always | **`src:iam_audit`, and no other** |
| `p_max.json` | the baseline | **byte-identical to it** |
| `premium.json` | the baseline | **byte-identical to it** |
| verdict at the cut over `P_max` | **ROBUST** | **OPTIMISTIC_ONLY** |

P_max and the premium are predicted to be unchanged **because that is the whole point**: the disputed
licence is retained with full force, so the tampering buys the attacker nothing. Those two rows are
true by construction if the protocol is implemented as specified. They are registered anyway, because
the implementation a reader writes first is the one that voids, and it would fail exactly here.

The verdict row is a conditional: it predicts ROBUST with the pass off. If the pass-off run does not
produce ROBUST at that cut, the prediction has failed and is reported as failed; the cell will not be
re-chosen to make it hold.

## What falsifies it

Any of these is a failed prediction and is reported as one:

- the pass finds no negative cycle;
- `C` is empty, or has more than one event, or names an event other than the backdated one;
- any source other than `src:iam_audit` is marked `tamper_suspected`, or `src:iam_audit` is not;
- `p_max.json` or `premium.json` differs between the pass-on and pass-off runs — in particular, any
  shrinkage of `P_max`, which would mean licences were voided rather than disputed;
- the verdict at the cut over `P_max` is not ROBUST with the pass off;
- the verdict at the cut over `P_max` is not OPTIMISTIC_ONLY with the pass on;
- the separate checker (S11) rejects the certificate emitted with the pass on.

## Confounds named in advance

1. **The backdated record may stop supporting the derivation it supported.** Moving k7 to `+1800 s`
   puts it more than 30 minutes before the export that rule r0005 pairs it with, so route B may not
   ground at all in this cell. That is expected and is not predicted against: it is why no absolute
   value of this cell is registered, and why every prediction is a pass-on / pass-off comparison.
2. **`iam_audit` is `chained`, so rewriting a timestamp also breaks that record's chain link.** If
   ingest quarantines the record for a broken chain before the pass ever sees it, there is no
   backdated record left to detect, `C` is empty, and the prediction fails. The operator therefore
   re-seals the chain it rewrites, and if it does not, the failure is reported rather than repaired
   after the fact.
3. **The correction set may be ambiguous.** Each violated pair could be corrected by disbelieving
   either of its two timestamps. The backdated record is in every violated pair, so a
   minimum-cardinality set is the single backdated record; if the implementation instead returns one
   event per pair, `|C| > 1` and the prediction fails.

## Commitments

- The source, the record, the magnitude and the predictions above are fixed by this commit.
- If a prediction fails, the magnitude will not be increased, the record will not be swapped, and the
  cell will not be re-selected. A different cell is a new pre-registration.
- The pass-off run is produced by the same code path with the pass disabled, not by an earlier commit.
