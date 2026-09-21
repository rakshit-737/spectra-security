"""Reachability under a cut: the least fixpoint, and the witness tree over it.

Stage S10, first of three modules. Given a program (the AND/OR provenance hypergraph
that S8 and S9 produce) and a cut `S` rendered as a 64-bit mask, this computes the set of
facts derivable when every instance whose blocker mask is satisfied by `S` is removed.

WHY UNIT PROPAGATION AND NOT A NAIVE ROUND-BASED FIXPOINT. Every instance carries one
unsatisfied-body counter. A fact is popped once, its dependent instances are touched once
per body occurrence, and an instance fires when its counter reaches zero. That is
Dowling-Gallier: linear in the size of the program, and, more importantly here, it visits
each edge a fixed number of times, so `steps` is a deterministic function of the program
and the cut rather than of how many rounds a scheduler happened to need.

WHY NO EARLY EXIT ON THE GOAL. The full closure is the invariant the checker replays
under obligation O7/O8; stopping at the goal would leave the certificate unable to carry
it. The goal membership test is a lookup after the loop, never a break inside it.

WHY THE GENERAL SUBSET TEST IS STILL HERE. Narrowing C-SLICE-1 says every blocker term
has popcount one, which collapses `(term & S) == term` to `(mask & S) != 0`. The subset
form is what the general grammar means, so it stays in the loop and the narrowing is
enforced as an explicit check at index-build time. A reader sees both the narrowing and
what it narrowed.

DETERMINISM. Axioms are consumed in ascending order, adjacency lists are built in
instance order (which is instance_id order, a content hash), the closure is returned
sorted, and nothing in this module iterates a set or a dict whose order depends on
insertion. No wall clock, no environment, no randomness.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from spectra_core import canon, errors, ids, model

__all__ = [
    "AXIOM_KIND",
    "GHOST_KIND",
    "LICENSED_KIND",
    "OBSERVED_KIND",
    "ReachProgram",
    "ReachResult",
    "WitnessNode",
    "instance_blocked",
    "reach",
    "witness_tree",
]


#: Witness-node kinds. The certificate contract names two, OBSERVED and GHOST. A third is
#: emitted here because a LICENSED instance that is not obligation-forced is neither: it
#: cites permission rather than records, and rendering it as OBSERVED is exactly the
#: collapse the verdict section forbids. AXIOM marks a seed fact, which has no instance.
OBSERVED_KIND: Final[str] = "OBSERVED"
LICENSED_KIND: Final[str] = "LICENSED"
GHOST_KIND: Final[str] = "GHOST"
AXIOM_KIND: Final[str] = "AXIOM"


@dataclass(frozen=True, slots=True)
class WitnessNode:
    """One node of a derivation of the goal: an instance and the derivations of its body.

    `instance_id` is absent on an AXIOM leaf, which is a seed fact rather than a rule
    firing. Children are in the instance's declared body order, which is content, not a
    sort key, so they are emitted in that order and never re-sorted.
    """

    head: ids.FactHash
    kind: str
    instance_id: ids.InstanceId | None = None
    evidence: tuple[ids.EventId, ...] = ()
    children: tuple[WitnessNode, ...] = ()

    def instances(self) -> tuple[ids.InstanceId, ...]:
        """Every instance id in this tree, sorted ascending and deduplicated.

        Sorted rather than in traversal order because the caller unions blocker masks over
        it, and a traversal order would put a tree shape into a corridor's identity.
        """
        found: list[str] = []
        stack: list[WitnessNode] = [self]
        while stack:
            node = stack.pop()
            if node.instance_id is not None:
                found.append(str(node.instance_id))
            stack.extend(node.children)
        return tuple(ids.InstanceId(v) for v in sorted(set(found)))


@dataclass(frozen=True, slots=True)
class ReachResult:
    """What one fixpoint run produced. `closure` is the artifact form; `order` is not.

    `order` is the first-derived sequence. It never reaches an artifact: the certificate
    stores the closure sorted. It is kept because a well-founded witness tree needs to
    know which support was available strictly before a fact was first derived.
    """

    derivable: bool
    closure: tuple[ids.FactHash, ...]
    order: tuple[ids.FactHash, ...]
    steps: int


@dataclass(frozen=True, slots=True)
class ReachProgram:
    """The hypergraph S8/S9 publish, indexed for propagation.

    This is an index over foundation records, not a new record type: facts are
    `model.Fact`, instances are `model.RuleInstance`, and this class owns only the
    adjacency and the counters that propagation needs.
    """

    kind: model.ProgramKind
    instances: tuple[model.RuleInstance, ...]
    axioms: tuple[ids.FactHash, ...]
    goal: ids.FactHash
    goals: tuple[ids.FactHash, ...]
    axiom_evidence: tuple[tuple[ids.FactHash, tuple[ids.EventId, ...]], ...]
    _by_body: Mapping[str, tuple[int, ...]]
    _body_size: tuple[int, ...]
    _by_head: Mapping[str, tuple[int, ...]]

    @classmethod
    def build(
        cls,
        kind: model.ProgramKind,
        instances: Iterable[model.RuleInstance],
        axioms: Iterable[ids.FactHash],
        goal: ids.FactHash,
        axiom_evidence: Iterable[tuple[ids.FactHash, tuple[ids.EventId, ...]]] = (),
        goals: Iterable[ids.FactHash] | None = None,
    ) -> ReachProgram:
        """Validate the published order and build the adjacency, in that order.

        Instances arrive sorted by instance_id and axioms sorted ascending; both are
        verified rather than sorted, because an emitter that produced them in hash-map
        order must go red here rather than be tidied up on the way in.
        """
        insts = tuple(instances)
        canon.check_strictly_ascending(
            insts, lambda i: str(i.instance_id), where="ReachProgram.instances"
        )
        axs = tuple(axioms)
        canon.check_strictly_ascending(axs, str, where="ReachProgram.axioms")
        ids.require_id(goal, ids.FactHash, where="ReachProgram.goal")
        # THE GOAL IS A SET. docs/vocab.toml defines a goal fact as a member of a library,
        # "goals are a set, verdicts are per-goal". The attack reaches its objective if ANY
        # member is derivable, so a cut severs only when EVERY member is underivable.
        #
        # `goal` stays as the canonical representative so single-goal callers keep their
        # meaning, but derivability is decided over `goals`. Deciding it over `goal` alone
        # is the bug the second end-to-end run exposed: the pipeline chose the bytewise-
        # least library key, which at full telemetry was a fact only P_max derives, so the
        # corridor search over P_min found it unreachable under the empty cut and reported
        # a severance while P_min derived the other goal fact through route A.
        gs = (goal,) if goals is None else tuple(goals)
        for g in gs:
            ids.require_id(g, ids.FactHash, where="ReachProgram.goals")
        canon.check_strictly_ascending(gs, str, where="ReachProgram.goals")
        if str(goal) not in {str(g) for g in gs}:
            raise errors.SchemaError(
                f"ReachProgram: the representative goal {goal} is not a member of goals",
                code="E-VS-GOAL-REP",
            )
        evid = tuple(axiom_evidence)
        canon.check_strictly_ascending(
            evid, lambda pair: str(pair[0]), where="ReachProgram.axiom_evidence"
        )

        by_body: dict[str, list[int]] = {}
        by_head: dict[str, list[int]] = {}
        body_size: list[int] = []
        for index, inst in enumerate(insts):
            for mask in inst.blockers:
                if mask.bit_count() != 1:
                    # C-SLICE-1 is a narrowing, not a claim. The loop below keeps the
                    # general subset test; this is what makes the narrowing visible.
                    raise errors.SchemaError(
                        f"ReachProgram: instance {inst.instance_id} carries a blocker term "
                        f"of popcount {mask.bit_count()}; C-SLICE-1 admits single literals only",
                        code="E-VS-BLOCK-CONJ",
                    )
            # Distinct body literals, not body length: a body that names the same fact
            # twice is satisfied by that fact once, and counting the occurrence twice
            # would leave the instance permanently one short of firing. Under-derivation
            # is the unsafe direction here, because it manufactures unreachability.
            distinct = sorted({str(f) for f in inst.body})
            body_size.append(len(distinct))
            for fact_key in distinct:
                by_body.setdefault(fact_key, []).append(index)
            by_head.setdefault(str(inst.head), []).append(index)

        return cls(
            kind=kind,
            instances=insts,
            axioms=axs,
            goal=goal,
            goals=gs,
            axiom_evidence=evid,
            _by_body={k: tuple(v) for k, v in sorted(by_body.items())},
            _body_size=tuple(body_size),
            _by_head={k: tuple(v) for k, v in sorted(by_head.items())},
        )

    def dependents(self, fact_key: ids.FactHash) -> tuple[int, ...]:
        """Indices of instances naming `fact_key` in their body, ascending by instance_id."""
        return self._by_body.get(str(fact_key), ())

    def supports(self, fact_key: ids.FactHash) -> tuple[int, ...]:
        """Indices of instances whose head is `fact_key`, ascending by instance_id."""
        return self._by_head.get(str(fact_key), ())

    def body_size(self, index: int) -> int:
        return self._body_size[index]

    def axiom_events(self, fact_key: ids.FactHash) -> tuple[ids.EventId, ...]:
        for key, events in self.axiom_evidence:
            if key == fact_key:
                return events
        return ()


def instance_blocked(instance: model.RuleInstance, cut_mask: int) -> bool:
    """True when some DNF term of `instance` is satisfied by the cut.

    The test is the general one, `(term & S) == term`: a term is satisfied when every
    literal in it is raised. Under C-SLICE-1 every term is a single literal and this is
    `(instance.mask & S) != 0`; the general form is kept so that lifting the narrowing is
    a change to `ReachProgram.build`, not to the fixpoint.
    """
    for term in instance.blockers:
        if term & cut_mask == term:
            return True
    return False


def reach(program: ReachProgram, cut_mask: int) -> ReachResult:
    """The least fixpoint of derivable facts under cut `cut_mask`.

    One unsatisfied-body counter per instance; each body edge is decremented at most once
    because a fact is expanded only the first time it is popped. `steps` counts one per
    edge touched plus one per fact expanded, which is the counter the step budget is
    compared against; there is no wall-clock budget anywhere in the pipeline.
    """
    canon.mask_hex(cut_mask)

    remaining = list(program._body_size)
    seen: set[str] = set()
    order: list[ids.FactHash] = []
    queue: deque[ids.FactHash] = deque(program.axioms)
    steps = 0

    # An instance with an empty body fires as soon as it is enabled and is never reached
    # through an adjacency list, since it names no body fact. Seeding its head here rather
    # than dropping it is the conservative choice: omitting it would under-derive, and
    # under-derivation is what manufactures a false claim of unreachability.
    for index, inst in enumerate(program.instances):
        if remaining[index] == 0 and not instance_blocked(inst, cut_mask):
            queue.append(inst.head)

    while queue:
        fact_key = queue.popleft()
        if str(fact_key) in seen:
            continue
        seen.add(str(fact_key))
        order.append(fact_key)
        for index in program.dependents(fact_key):
            inst = program.instances[index]
            if instance_blocked(inst, cut_mask):
                continue
            remaining[index] -= 1
            steps += 1
            if remaining[index] == 0:
                queue.append(inst.head)
        steps += 1

    closure = tuple(sorted(order, key=canon.byte_order_key))
    return ReachResult(
        # Any member reached is the objective reached. See ReachProgram.build.
        derivable=any(str(g) in seen for g in program.goals),
        closure=closure,
        order=tuple(order),
        steps=steps,
    )


def witness_tree(
    program: ReachProgram, cut_mask: int, result: ReachResult, target: ids.FactHash | None = None
) -> WitnessNode:
    """A well-founded derivation of `target` (the goal by default) under `cut_mask`.

    The support of a fact is the enabled instance with the LOWEST instance_id among those
    whose body facts were all derived STRICTLY EARLIER than the fact itself. The spec text
    says "fully derived"; the refinement to "strictly earlier" is what makes the tree
    acyclic, because two mutually supporting instances are both fully derived in the
    closure and a rule that ignored derivation order could select either and cycle. The
    checker rejects a cyclic tree with E-WITNESS-CYCLE, so the conservative reading is the
    only one that produces a checkable artifact.

    Ties among admissible supports are impossible: instance_id is a content hash of the
    whole instance, so two distinct supports have distinct ids.
    """
    if target is None:
        # Root the tree at a goal that was DERIVED, not at the representative, which may
        # be a member no instance heads. Among the derived members take the first in the
        # library's strictly ascending order, so the choice is a function of the program
        # and the cut and nothing else.
        derived = {str(f) for f in result.order}
        reached = [g for g in program.goals if str(g) in derived]
        goal = reached[0] if reached else program.goal
    else:
        goal = target
    if str(goal) not in {str(f) for f in result.order}:
        raise errors.SchemaError(
            f"witness_tree: {goal} is not in the closure under this cut; "
            "a witness tree is only defined for a derived fact"
        )

    position = {str(f): i for i, f in enumerate(result.order)}
    memo: dict[str, WitnessNode] = {}

    def build(fact_key: ids.FactHash) -> WitnessNode:
        key = str(fact_key)
        cached = memo.get(key)
        if cached is not None:
            return cached
        here = position[key]
        chosen: model.RuleInstance | None = None
        for index in program.supports(fact_key):
            inst = program.instances[index]
            if instance_blocked(inst, cut_mask):
                continue
            body_keys = {str(f) for f in inst.body}
            if any(b not in position or position[b] >= here for b in body_keys):
                continue
            if chosen is None or str(inst.instance_id) < str(chosen.instance_id):
                chosen = inst
        if chosen is None:
            node = WitnessNode(
                head=fact_key,
                kind=AXIOM_KIND,
                evidence=program.axiom_events(fact_key),
            )
        else:
            if chosen.ghost:
                kind = GHOST_KIND
            elif chosen.observed is model.Observation.LICENSED:
                kind = LICENSED_KIND
            else:
                kind = OBSERVED_KIND
            node = WitnessNode(
                head=fact_key,
                kind=kind,
                instance_id=chosen.instance_id,
                evidence=tuple(e.event_id for e in chosen.evidence),
                children=tuple(build(b) for b in chosen.body),
            )
        memo[key] = node
        return node

    return build(goal)


def witness_mask(program: ReachProgram, tree: WitnessNode) -> int:
    """The union of every blocker term of every instance in `tree`.

    This is the corridor the hitting-set loop learns: severing this derivation requires
    raising at least one of these literals. A zero result means the derivation uses only
    unblockable instances, which is not a corridor at all and is reported as such by the
    caller rather than appended as an empty clause.
    """
    by_id = {str(i.instance_id): i for i in program.instances}
    mask = 0
    for instance_id in tree.instances():
        for term in by_id[str(instance_id)].blockers:
            mask |= term
    return mask


def admissible_cut_masks(
    literals: Sequence[model.ThresholdLiteral],
) -> tuple[int, ...]:
    """Every downward-closed assignment over the literal universe, as masks, ascending.

    "Downward-closed" is the upward-closure of the data contract seen from the other side:
    a control set to level L asserts levels 1..L, so an admissible cut picks one level per
    control from 0..m_k. Used by the antitonicity property test, which walks the whole
    lattice rather than sampling it.
    """
    by_control: dict[str, list[model.ThresholdLiteral]] = {}
    for literal in literals:
        by_control.setdefault(str(literal.control_id), []).append(literal)
    masks = [0]
    for control_id in sorted(by_control):
        levels = sorted(by_control[control_id], key=lambda l: l.level)
        options = [0]
        running = 0
        for literal in levels:
            running |= 1 << literal.bit
            options.append(running)
        masks = [m | o for m in masks for o in options]
    return tuple(sorted(set(masks)))
