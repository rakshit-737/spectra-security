# ADR-0015: Witness trees are published flat, and a licensed silent step is a witness node kind

## Status

Accepted — 2026-09-21

## Context

A certificate carries, for each control in the cut, a witness tree: the derivation of the goal
that comes back when that one control is removed. The checker (obligation O12) walks each tree,
checks every node against the published instance set, checks every OBSERVED leaf against the
pinned bundle, and checks that each node's body is covered by its children or by axioms. The tree
is the part of a certificate that says *why* a control is needed, rather than only *that* it is.

Two properties of the slice's certificate contract (`docs/kernel/slice-spec.md`, SCF-lite) made
that tree unpublishable for every derivation the demonstration actually produces:

1. **Depth.** The contract caps nesting at eight containers, counting the document object as the
   first. A tree nested at `body.witnesses[i].tree` spends five before its root node and two per
   level below it, so it admits a root and one level of children. Route A, the demonstration's
   observed attack route, is three levels deep. The emitter refused to write it, and the pipeline
   now drops it and reports the omission (`BUILD_LOG.md` INC-0008).
2. **Alphabet.** A witness node is OBSERVED, which must cite a record, or GHOST, which must cite
   none and whose instance must be obligation-forced. A licensed silent instance of a rule that is
   not obligation-forced is neither. The reachability module already has a name for it, LICENSED,
   and the published instance set already marks it (`observed: "LICENSED"`, `ghost: false`, at
   least one licence). The witness alphabet did not, so any derivation through one was dropped.

In pre-registration 0001's blackout cell both omissions fire, one per control in the cut, and the
certificate carries no witness at all (`docs/research/prereg-0001-result.md`). The certificate that
makes the demonstration's headline claim cannot say why `ctl:priv_approval` is in the cut.

`docs/plan/DECISIONS.md` D-RUN-02 recorded the choice and its default: keep the nested encoding
and omit multi-step witnesses. It also recorded that changing it is a contract change on the
emitter and the checker together and needs an ADR. This is that ADR.

The cap itself is not the problem. It exists so that a reader, including the checker, never has to
recurse to an unbounded depth over untrusted input, and that reason stands.

## Decision

1. **Flat encoding.** `body.witnesses[i]` becomes `{ removed_control, nodes }`. `nodes` is a list
   of witness nodes in pre-order; `nodes[0]` is the root. Each node's `children` is a list of
   indices into `nodes`, not of nested objects. The emitter writes a tree whose nesting depth is
   fixed by the layout (document, body, witnesses, entry, nodes, node, children: seven containers)
   and does not grow with proof length.
2. **Structural rules the checker enforces**, each rejected with `E-WITNESS-CYCLE`:
   - `nodes` is non-empty;
   - every child index of node `i` is greater than `i` and less than `len(nodes)`, so no index
     sequence can loop;
   - every node other than the root is referenced exactly once, so the list is one tree, with no
     shared subtrees and no unreachable nodes;
   - no node's instance appears on its own ancestor path, as before.
3. **A third node kind, `LICENSED`**, for a licensed silent step that is not obligation-forced. A
   LICENSED node cites no evidence, and its published instance has `observed: "LICENSED"`,
   `ghost: false` and at least one licence id. The checker also tightens the other two kinds
   against the instance they cite: an OBSERVED node's instance has `observed: "OBSERVED"`, and a
   GHOST node's instance has `ghost: true`.
4. **Witness class.** The rule that an OBSERVED witness class may not be published over a tree
   containing a GHOST now reads "containing a GHOST or LICENSED node", and a LICENSED witness class
   requires at least one node of either kind. Both are silent steps.
5. **Version.** `schema.v` and `schema.min_checker` move from `1.0` to `1.1`, and the checker's
   version from `1.0` to `1.1`. The checker accepts `schema.v == "1.1"` only. There are no `1.0`
   certificates outside run directories, which are not committed, so no reader is stranded.
6. **Pipeline.** The witness-depth refusal introduced in INC-0008 and the refusal of licensed silent
   steps are both removed; the conditions they guarded no longer exist. Any other derivation the
   certificate cannot express is still dropped and reported, never forced into the wrong kind.

This decision does not change which derivation is chosen as the witness (`reach.witness_tree`), the
depth cap, or any other obligation.

## Consequences

- The certificates of every cell the demonstration runs can carry their witness trees, including
  the one showing why `ctl:priv_approval` is needed in the blackout cell.
- A witness drawn from P_max may combine silent instances that no single consistent world realizes.
  That caveat was always true of such a tree and is already printed with every cell; publishing the
  trees makes it matter, because they will now be read.
- Every certificate's bytes change, including those whose hashes are recorded in
  `docs/research/prereg-0001-result.md`. That record describes the artifacts at the commit it was
  written against and is not rewritten; a dated addendum records the change.
- Emitter and checker change in the same commit, as the contract requires. They still share an
  author, a language and a reading of this ADR, so the checker's acceptance of the new encoding is
  not independent evidence that the encoding is right. That limit is unchanged.
- The flat encoding costs a reader one extra step: children are resolved by index. A consumer that
  printed the nested form must now rebuild it.
- Reversing this means restoring the nested member and both refusals, in both packages together.

## Alternatives considered

### Raise the depth cap

The shortest change, and the one a reader would try first. It moves the limit instead of removing
it: any cap admits a derivation one level deeper than it, and route A is only the first multi-step
route this scenario happens to contain. It also weakens the property the cap exists for, bounded
recursion over untrusted input, in exchange for nothing structural.

### Keep the nested encoding and omit multi-step witnesses

The recorded default. It keeps the contract unchanged, and the omission is reported rather than
silent. But it means the certificate cannot carry a witness for any attack of more than two steps,
which is every attack worth modelling, and a certificate that proves a cut without being able to
show why each control is in it is the weaker half of what the design promises.

### Publish a LICENSED step as GHOST

Rejected when the refusal was first written and rejected again here. GHOST names an
obligation-forced head, a step the rules say must have happened. A licensed silent step is one the
rules say might have happened unseen. Calling one the other would put a silent instance into the
certificate wearing the wrong word.

## References

- `docs/plan/DECISIONS.md` D-RUN-02
- `BUILD_LOG.md` INC-0008 (the depth refusal), INC-0011 (pre-registration 0001)
- `docs/research/prereg-0001-result.md`
- `docs/kernel/slice-spec.md`, the certificate contract this amends
