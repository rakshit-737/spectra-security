# Pre-registration 0002: result

This is the result record for [`prereg-0002-backdate-cell.md`](prereg-0002-backdate-cell.md). That
file has not been edited since the commit that registered it; the outcome is recorded here.

**Outcome: PREDICTION HELD.** All eight falsifiers passed, on two platforms. Tampering with a
timestamp bought the attacker nothing: the licences stayed in `P_max` and the verdict weakened.

## Ordering

| Commit | Content | Relation to the registration |
| --- | --- | --- |
| `c6f77ae` | ADR-0016, the decision to implement the pass | precedes the registration |
| `a796c41` | **the pre-registration** | - |
| `86c5e4c` | `spectra_vs.temporal`, the pass itself | `a796c41` is an ancestor |
| `00fc8b1` | the `BACKDATE` operator | `a796c41` is an ancestor |
| `9a2f435`, `cbae46c` | the liveness and pipeline wiring | `a796c41` is an ancestor |
| `d795bb4` | the demo evaluating the falsifiers mechanically | `a796c41` is an ancestor |

## What was observed

The intervention: the one `iam_role_assumed` record on `src:iam_audit`, moved 2700 s earlier, keeping
its sequence number. Every row compares the same cell with the temporal pass on and off.

| Falsifier | Observed | Result |
| --- | --- | --- |
| the pass finds a contradiction | 1 disputed timestamp | PASS |
| `C` is exactly the backdated record | `ev:c9f5c0c3ef5c102158a5b662e85a6c0e` | PASS |
| `iam_audit` is suspected, and nothing else | `src:iam_audit` | PASS |
| `p_max.json` byte-identical with the pass off | identical | PASS |
| `premium.json` byte-identical with the pass off | identical | PASS |
| the cut over `P_max` is ROBUST with the pass off | ROBUST | PASS |
| the cut over `P_max` is OPTIMISTIC_ONLY with the pass on | OPTIMISTIC_ONLY | PASS |
| the separate checker accepts the pass-on certificate | exit 0 | PASS |

| Run | run_id |
| --- | --- |
| backdate cell, pass on | `vs-07e484a067863409` |
| backdate cell, pass off | `vs-80ebfc7cfeb33e8c` |

## The number the registration was written for

With the pass on, the run prints:

```
1 licence(s) rest on a disputed timestamp and are RETAINED. Had they been voided, as Part I specifies,
the verdict at the cut over P_max would have been ROBUST, against the published OPTIMISTIC_ONLY.
```

That is the attack Part II section 65.6 exists to close, measured rather than argued. Part I voids
the licences that rest on a disputed timestamp; voiding shrinks `P_max`; a smaller `P_max` can only
move a verdict toward ROBUST. In this cell it does exactly that: had the slice followed Part I, a
single rewritten timestamp would have upgraded the verdict from OPTIMISTIC_ONLY to ROBUST — the
strongest statement SPECTRA makes — in the attacker's favour. Under the dispute protocol the licence
stays, `P_max` is byte-identical with the pass off, and the verdict moves the other way.

## What the pass found, in the artifacts

`src:iam_audit` is marked `tamper_suspected` and the record appears in `liveness.json` under
`disputed_events`, recorded at `1707006600000000000`, which is `epoch + 1800 s`: where the operator
moved it. Both `SUPPRESSED / S_CHAIN_SEQ_GAP` licences the cell issues on that source are retained.

The correction set has one member. That was the third confound the registration named: each
contradicted pair could be corrected by disbelieving either of its two records, and a naive cover
would have returned one event per pair or named an innocent neighbour. The implementation computes
the complement of a longest non-decreasing subsequence per source, which names the record that cannot
stay, and the unit tests written first are what forced that formulation (`BUILD_LOG.md` INC-0013).

## Reproducibility

The gate `G-VS-PREREG-0001` now re-runs both registrations on every push. On the CI run of `d795bb4`
(Ubuntu 24.04, CPython 3.12.3) all eight falsifiers passed and the disputed event id was the same
`ev:c9f5c0c3ef5c102158a5b662e85a6c0e` as on the development machine (Windows 11, CPython 3.14).

## What this result is, and what it is not

It **is** evidence that the dispute protocol behaves as specified against the operator it was written
for: a rewritten timestamp is found, attributed to the one record that cannot be believed, and costs
the attacker the verdict instead of buying them one.

It is **not**:

- **Tamper detection.** The pass detects a recorded timestamp that contradicts the order its own
  source recorded. A source whose every timestamp was rewritten consistently is consistent and
  invisible here; a forged chain is invisible here; suppression on a source with no sequence number
  is invisible here and in principle.
- **A blind prediction.** The author wrote the registration knowing Part II 65.6 and knowing which
  record the scenario emits. It fixes the outcome of an implementation before that implementation
  exists, which is a weaker thing than a blind test and a stronger one than a claim made afterwards.
- **A measurement.** One scenario, one seed, one record, one shift. Simulated telemetry, a simulated
  attack, and no distribution.
- **A statement about a real system.** Every verdict is scoped to this rule table, this control
  catalog, these licences, the telemetry ingested, and a non-adaptive attacker.
