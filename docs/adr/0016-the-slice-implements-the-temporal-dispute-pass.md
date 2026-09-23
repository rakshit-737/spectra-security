# ADR-0016: The slice implements the temporal-consistency pass, under the dispute protocol

## Status

Accepted — 2026-09-23

## Context

`docs/kernel/slice-spec.md` excludes the Bellman-Ford difference-constraint pass from the vertical
slice, in two places and without ambiguity:

> TAMPER: the slice does NOT implement the Bellman-Ford backdating pass. Therefore
> `tamper_suspected` is always false, `verdict_tamper_sensitive` is always false, flag bit 5 is never
> set, and the slice must never claim it detects suppression, backdating or tampering of any kind.

and, in the list of what the slice leaves out, "The Bellman-Ford backdating / difference-constraint
pass. Cost: real."

That exclusion has a consequence the slice now carries in writing. `Safety.ROBUST` may be minted only
against a `NoTamperToken`, and the token is mintable only when no source is tamper-suspected. With no
pass, nothing can ever be suspected, so the token is unconditional and every ROBUST verdict rests on
a check that does not exist. `BUILD_LOG.md` INC-0011 records this: pre-registration 0001 named a
tamper flag as its one confound, the flag did not fire, and that was not evidence of anything,
because it could not have fired. The demonstration now prints that caveat beside every ROBUST verdict
and every empty flag list.

The pass is also the one place where the specification closes an attack against SPECTRA itself.
Part II section 65.6 rewrites Part I's design for exactly this reason: Part I voids licences that
rest on provably backdated timestamps, voiding a licence shrinks `P_max`, and a smaller `P_max` can
only move a verdict toward ROBUST. An adversary who controls timestamps could therefore manufacture
a ROBUST verdict by tampering — the system would reward the attack it claims to detect. Section 65.6
replaces voiding with a dispute protocol in which a suspected licence is retained in `P_max` with
full force and the verdict is weakened instead.

Nothing in the slice exercises that property today, and an unexercised safety property is a claim,
not a mechanism. The scenario's `iam_audit` source is `chained` and carries `seq`, so the slice
already holds the evidence a detector needs.

## Decision

The slice implements the temporal-consistency pass of section 65.6, as the dispute protocol and not
as Part I's voiding pass. `docs/kernel/slice-spec.md` is amended: the two passages quoted above are
superseded by this record, and the slice-spec carries a pointer to it.

1. **A new module `spectra_vs.temporal`** builds a difference-constraint graph over event timestamps,
   runs Bellman-Ford in a canonical edge order under a step budget, and returns the negative cycles
   and a minimal correction set `C`.
2. **The graph, for this slice.** Nodes are event ids plus a zero node. Each recorded timestamp is
   pinned by a pair of edges to the zero node. Structural constraints are per-source `seq`
   monotonicity and the `seq` temporal bounds the rule table declares. Only the pinning edges are
   removable: `C` is a set of events whose recorded timestamp cannot be believed, which is the
   backdating question. Structural edges are never removed, and this narrowing is stated in the
   module.
3. **`C` is exact** while the number of edges appearing in negative cycles is at most
   `mcs_exact_cap` in `config/vs/liveness.toml`, by minimum-cardinality search with lexicographic
   tie-breaking. Above the cap it is a documented greedy cover and `mcs_greedy` is set.
4. **No licence is ever removed from `P_max`.** A licence whose interval endpoints depend on an event
   incident to `C` is marked `TEMPORALLY_DISPUTED` and retained with full force.
5. **`tamper_suspected`** is set on every source contributing an event in `C`.
   `verdict_tamper_sensitive` is set when the counterfactual verdict over `P_max` without the
   disputed licences differs from the published one; both verdicts are reported under
   `tamper_sensitivity` in `liveness.json`, which moves to `spectra.liveness/3`.
6. **The hard verdict rule of 65.6.2.** If a tamper-suspected source's licence appears in any corridor
   of `Psi_max`, or `verdict_tamper_sensitive` is set, ROBUST is unconstructible and the verdict is
   OPTIMISTIC_ONLY. The checker enforces the same rule from the pinned `liveness.json`, so a
   certificate claiming ROBUST over a disputed corridor is rejected rather than trusted.
7. **A `BACKDATE` degradation operator** (section 61.4.7) is added, so the pass has an adversary to
   face. Its cell is pre-registered in `docs/research/prereg-0002-backdate-cell.md` before either
   exists.

This decision does not implement CHAIN-FORGE, DELAY, CORRUPT or STRIP-IDENTITY, does not make the
slice a tamper detector for anything beyond recorded-order contradictions, and does not touch the
liveness classification lattice.

## Consequences

- The `NoTamperToken` stops being unconditional. ROBUST becomes a verdict that something can refuse,
  and the caveat the demonstration prints beside it can be narrowed to what remains unchecked.
- The property that tampering must not strengthen a verdict becomes executable, and its cell is
  pre-registered with falsifiers rather than asserted.
- The slice detects ONE thing: a recorded timestamp that contradicts the recorded order of its own
  source, or a declared temporal bound. Suppression on a `none`-integrity source stays undetectable
  in principle, a forged chain stays undetectable, and a consistent rewrite of every timestamp in a
  source is consistent and therefore invisible. No rendering may widen this into "SPECTRA detects
  tampering".
- `liveness.json` changes shape, so its hash changes, so every certificate's bytes change. The
  hashes recorded in `docs/research/prereg-0001-result.md` are superseded again, by a dated
  addendum rather than an edit.
- The cost the slice-spec named as "real" is accepted: a second full pass over the bundle's events, a
  minimum-cardinality search, and a counterfactual verdict computation per cell.
- Reversing this means restoring the two slice-spec passages and deleting the module, the operator,
  the liveness members and the checker obligation together.

## Alternatives considered

### Leave the pass out and keep the caveat

The honest option, and the one in force until now: the demonstration says plainly that no tamper
check exists. It costs nothing and claims nothing. But it leaves the specification's one
self-defending property untested, and an ROBUST verdict that nothing can block is weaker than it
looks even when it is correctly derived. The caveat is a description of a hole, not a substitute for
closing it.

### Implement Part I's voiding pass instead

Simpler: void the licences that rest on disputed timestamps and be done. It is also the attack.
Voiding shrinks `P_max`, which moves verdicts toward ROBUST, so an adversary who can tamper with
timestamps can buy a stronger verdict. Section 65.6 exists to forbid exactly this, and the rejected
design is the one a reader would write first, which is why the module states the direction in its
own docstring.

### Detect tampering from the hash chain alone

The chained sources already seal each record, so a rewritten timestamp breaks its chain link. That
is a real check and it is cheaper, but it only covers `chained` sources, it says nothing about a
source whose records were consistently re-sealed, and it produces no correction set, so it cannot
say which timestamps to disbelieve or which licences they support. The two are complements; this
decision implements the one the verdict rules are written against.

## References

- Part II section 65.6 (the dispute protocol) and 65.6.2 (the hard verdict rules)
- Part II section 61.4.7 (the `BACKDATE` operator)
- `docs/kernel/slice-spec.md`, the two passages this record supersedes
- `BUILD_LOG.md` INC-0011, `docs/research/prereg-0001-result.md` (the confound that could not fire)
- [ADR-0015](0015-witness-trees-are-published-flat.md), the previous contract change
