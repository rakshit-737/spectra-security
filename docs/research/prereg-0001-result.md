# Pre-registration 0001: result

This is the result record for [`prereg-0001-blackout-cell.md`](prereg-0001-blackout-cell.md). The
pre-registration itself has not been edited since the commit that registered it; that file says
nothing in it may change after the run, so the outcome is recorded here instead.

**Outcome: PREDICTION HELD.** All five falsifiers passed. The confound named in advance could not
be tested, because the check it depends on does not exist in this slice; see below.

## Ordering

The predictions were fixed before the intervention existed. This is established by commit ancestry,
not by dates:

| Commit | Content | Relation to the registration |
| --- | --- | --- |
| `ce8ed9c` | the pre-registration | - |
| `8e33dea` | the `WHOLE_SOURCE_BLACKOUT` operator | `ce8ed9c` is an ancestor |
| `f4ab484` | tests pinning it as a single-variable intervention | `ce8ed9c` is an ancestor |
| `204602b` | the blackout cell wired through the pipeline | `ce8ed9c` is an ancestor |
| `dc96f3c` | the demo evaluating the falsifiers mechanically | `ce8ed9c` is an ancestor |

`git log -- docs/research/prereg-0001-blackout-cell.md` lists one commit, `ce8ed9c`.

## What was observed

| Quantity | Full telemetry | Blackout cell, PREDICTED | Blackout cell, OBSERVED |
| --- | --- | --- | --- |
| `\|Psi_min\|` | 1 | 1 | **1** |
| `\|Psi_max\|` | 1 | 2 | **2** |
| blindness premium | EMPTY | `{ctl:priv_approval}` | **`{ctl:priv_approval}`** |

| Falsifier | Result |
| --- | --- |
| the premium is published | PASS |
| the premium is non-empty | PASS |
| the premium is exactly `{ctl:priv_approval}` | PASS |
| `\|Psi_min\| == 1` | PASS |
| `\|Psi_max\| == 2` | PASS |

The mechanism the prediction named is the one the artifacts show. The blackout removed 601 of 21577
simulated records, all from `src:iam_audit` inside the window. Liveness then issued a SUPPRESSED
licence, reason `S_CHAIN_SEQ_GAP`, on `src:iam_audit` over
`[1707008999699266491, 1707009601892237041)` - the 10 minutes between the last record before the
window and the first record after it, bracketed by those two record ids. P_max grew from 85 to 130
instances, and the cut over P_max raised `ctl:egress_seg` and `ctl:priv_approval`, where the cut
over P_min raised `ctl:egress_seg` alone.

The premium's `ctl:priv_approval` entry reports `calibration_deficiency 0/1`: it rests on an
observed-gap licence, not on a source this run had no calibration for.

| Run | run_id |
| --- | --- |
| full telemetry, the control arm | `vs-0049b1adfb705cb3` |
| blackout cell | `vs-02830d35a09ad406` |

## The confound named in advance

The registration predicted that deleting records from a `chained` source would be classified
SUPPRESSED rather than BLIND, and that it *may* set `tamper_suspected`, which would make a ROBUST
verdict unconstructible in this cell.

The first half held: the licence is SUPPRESSED, `S_CHAIN_SEQ_GAP`.

The second half was **never testable**. `spectra_vs.liveness.TAMPER_PASS_IMPLEMENTED` is `False`:
the backdating pass that would mark a source tamper-suspected does not exist, and the liveness
types refuse a true value outright. So "no flag was set" in this cell is the absence of a check,
not a finding that the chain was untampered. And the ROBUST verdict the run printed for the cut
over P_max exists only because of that absence.

That should have been written into the registration and was not. The author named a confound
without checking whether the code could produce it. The demo now prints this caveat next to every
ROBUST verdict and every empty flag list, and the pipeline reads the tamper inputs from the
liveness document instead of passing them as constants, so a future tamper pass will block ROBUST
without further changes.

## Checker

The separate checker (S11) exited 0, ACCEPT, with obligations O0 to O15 passing.

Two limits apply, and they are the checker's own words:

- ACCEPT means the certificate is internally consistent with the inputs it pins. It says nothing
  about whether the bundle is truthful or the control catalog complete.
- The checker imports nothing from the emitter, but both are Python, written by one author from one
  reading of one specification, and both share `spectra_core`. The certificate may not be described
  as independently verified.

**No witness tree is published** in this certificate (O12). Both candidates were refused and
reported: the tree behind `ctl:egress_seg` is three levels deep where the contract carries two, and
the tree behind `ctl:priv_approval` runs through a licensed silent instance that `cert.WitnessNode`
has no kind for. The certificate therefore proves that the cut severs the goal, but carries no tree
showing *why* `ctl:priv_approval` is needed. `docs/plan/DECISIONS.md` D-RUN-02 records the open
decision that would fix this.

## Reproducibility

The demo was run three times on one machine (Windows 11, CPython 3.14), the third time after a
rendering-only change and the change to where the pipeline reads its tamper inputs. The four
artifacts compared in each of the two cells were byte-identical across all three runs:

| Cell | Artifact | SHA-256 |
| --- | --- | --- |
| blackout | `cert.spcert` | `3e20c40b3bd1258eaf22230b2f3d1c8d2b38802d8ac9387c0c86532d7b522c19` |
| blackout | `p_max.json` | `f36c5d98eda06ce169072b34f6182cb8e8eb9d5fd14b6bf05ce8ed33643bb987` |
| blackout | `psi_max.json` | `d5a88c361ad713e330d81575f6a1193c57034f146b4e5478092580decf75b248` |
| blackout | `premium.json` | `7037dfe65abb93224875f128289accdab2458137e7b7c363bc5c99b151971988` |
| full telemetry | `cert.spcert` | `830612ad6b60a2c1c26f5a3de1a93bb9e54ebdd9f92bc2c8b1714d74fbf05fda` |
| full telemetry | `p_max.json` | `e13c6a51deec0fac150838f0c87c809e5e442f70dffc7a3286b52b5455a17c6d` |
| full telemetry | `psi_max.json` | `fab155f339e946cf5002b1a922a6c3ce6c875dff7dbdd37651fb25db3614a51d` |
| full telemetry | `premium.json` | `d3844329afa6bb0716407b0bc811b3612af7ddd8d4126b458ec6c6b59abb40c5` |

That is re-execution determinism on one interpreter and one operating system. Nothing here shows the
same bytes on another platform or interpreter version. CI does not run the demonstration.

## What this result is, and what it is not

It **is** evidence that the reference implementation does what its author's model of it says it
does: blinding one sensor over one window adds exactly the control that only the hidden route needs,
and leaves everything else alone.

It is **not**:

- **A blind prediction.** The author wrote it immediately after tracing this exact mechanism while
  fixing the `seq` bug (`BUILD_LOG.md` INC-0010), and chose the window knowing where the scenario
  puts the escalation. It tests whether the code matches that understanding, not whether that
  understanding is right.
- **A pre-registration under the research protocol.** `docs/research/preregistration.md` requires
  the pre-registration commit to precede every rule, and the rule table already existed. This
  registration is a narrower commitment: predictions fixed before one intervention was built.
- **A measurement.** The telemetry is the output of a seeded synthetic generator, and the attack in
  it is simulated. One scenario, one seed and one window give one data point, with no distribution
  and no error bar.
- **A statement about a real system.** Every verdict is scoped to this rule table, this control
  catalog, these licences, the telemetry ingested, and a non-adaptive attacker.
