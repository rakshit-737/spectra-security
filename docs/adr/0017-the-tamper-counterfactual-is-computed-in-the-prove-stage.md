# ADR-0017: Correct ADR-0016: the tamper counterfactual belongs to the prove stage

## Status

Accepted — 2026-09-23

Supersedes ADR-0016 point 5, and only that point.

## Context

ADR-0016 brought the temporal-consistency pass into the slice. Its fifth numbered decision reads:

> `verdict_tamper_sensitive` is set when the counterfactual verdict over `P_max` without the disputed
> licences differs from the published one; both verdicts are reported under `tamper_sensitivity` in
> `liveness.json`, which moves to `spectra.liveness/3`.

That follows Part II section 65.6.1 step 6, which places the comparison in `liveness.json`. It cannot
be implemented where it is placed, and the reason is ordering rather than difficulty:

- `liveness.json` is the artifact of S7. It is written, hashed, and that hash is pinned into the
  certificate's `inputs` and bound again in its `scope`.
- A verdict is the artifact of S10, which runs after S8 grounding, S9 envelope and the cut search.
  The counterfactual verdict is a second verdict, computed over the upper program with the disputed
  licences dropped, and it needs the whole of S8 to S10 to exist.
- Writing a verdict-derived member into `liveness.json` therefore requires either rewriting the file
  after its hash was pinned, which breaks every downstream digest, or a circular dependency between
  S7 and S10.

The rest of ADR-0016 is unaffected. The dispute protocol, the retention of disputed licences, the
`tamper_suspected` marking, the hard verdict rule and the checker obligation are all implemented as
that record describes, and are not reopened here.

## Decision

1. **`liveness.json` carries what S7 knows**: the disputed events, `tamper_suspected` per source, and
   `mcs_greedy`. It stays at `spectra.liveness/3`. `LivenessFlags.verdict_tamper_sensitive` remains a
   representable member that S7 never sets, and the liveness module says so where it is defined.
2. **The counterfactual is computed in S10**, where both verdicts exist, and is published there: the
   prove stage computes the verdict over `P_max` with the disputed licences dropped, compares it with
   the published verdict, and reports both. The demonstration prints the comparison.
3. **The checker's O14b keeps reading `verdict_tamper_sensitive`** from the pinned document and keeps
   refusing a ROBUST verdict when it is true. The member is not removed, because a later stage or a
   later kernel may set it, and an obligation that stops checking a field is how a field becomes
   unchecked.
4. **The counterfactual is reporting only.** It does not change the published verdict, which was
   already weakened by the hard rule of ADR-0016 point 6. What it adds is the number that says what
   the tampering would have bought: the verdict SPECTRA would have published had it voided the
   disputed licences the way Part I specifies.

## Consequences

- The anti-attack property becomes visible rather than argued. A run that disputes a timestamp can
  print, side by side, the verdict it published and the stronger verdict it would have published had
  it voided instead — which is what Part I would have done, and what Part II 65.6 forbids.
- The slice diverges from 65.6.1 step 6 in WHERE the comparison is recorded, and the divergence is
  this record. Nothing about which comparison is made changes.
- A reader of `liveness.json` alone cannot see the counterfactual; they must read the certificate or
  the transcript. That is a real loss of locality, accepted because the alternative is a hash cycle.
- The cost is one extra reachability computation over the upper program per cell.
- Reversing this means moving the comparison back into S7, which requires the verdict to be
  computable there, which is the ordering problem this record documents.

## Alternatives considered

### Write `liveness.json` twice

S7 writes the document, S10 appends the counterfactual and rewrites the file. The certificate pins
the hash of the file as it was when the licences were read, so either the pin goes stale or the
artifact the pin refers to no longer exists on disk. A checker re-reading the file would recompute a
different digest and reject the certificate, correctly.

### Put the counterfactual in a side file that liveness.json references

Keeps the comparison near the document, at the cost of a second artifact whose relationship to the
certificate is unpinned. An unpinned artifact is one a reader cannot trust and a checker cannot
check, which is the opposite of what the comparison is for.

### Drop the counterfactual

Defensible: the hard rule already weakens the verdict, so the comparison changes no outcome. It is
kept because it is the only place the project can show, with numbers from a run rather than from a
paragraph, that the attack Part II 65.6 exists to close is actually closed.

## References

- [ADR-0016](0016-the-slice-implements-the-temporal-dispute-pass.md), point 5, which this supersedes
- Part II section 65.6.1 step 6
- `docs/research/prereg-0002-backdate-cell.md`
