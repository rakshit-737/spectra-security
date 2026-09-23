"""S7b: the temporal-consistency pass, as a difference-constraint system (ADR-0016).

WHAT THIS ANSWERS, and nothing else: does a recorded timestamp contradict the recorded
order of its own source, or a temporal bound the rule table declares? When one does, the
pass returns the smallest set of timestamps that would have to be disbelieved for the
records to be consistent, and the sources those timestamps came from.

THE DIRECTION, which is the whole reason this module has a specification of its own.
Part I ran this pass and VOIDED the licences that rested on disputed timestamps. Voiding a
licence shrinks P_max; a smaller P_max can only move a verdict toward ROBUST; so an
adversary who can rewrite timestamps could buy the strongest verdict SPECTRA issues by
tampering, and SPECTRA would reward the attack it claims to detect. Part II section 65.6
replaces that with a dispute protocol: a licence resting on a disputed timestamp is
RETAINED in P_max with full force, and the VERDICT is weakened instead. Nothing in this
module removes anything from a program, and nothing in it may be made to.

THE SYSTEM. A constraint is written `t[v] - t[u] <= weight` and is an edge u -> v of that
weight, so a negative cycle is a set of constraints no assignment of timestamps can satisfy.
Three kinds of constraint are built:

  PIN             the recorded timestamp of one event, as a pair of edges to the zero node.
                  PINS ARE THE ONLY REMOVABLE CONSTRAINT: a correction set is a set of
                  events whose recorded timestamp is not believed, which is the backdating
                  question. Structural constraints are never dropped, because dropping one
                  would mean disbelieving the rule table or the source's own sequence
                  rather than the data.
  SEQ_MONOTONIC   within one source, a record with a higher `seq` was recorded no earlier:
                  `t[next] >= t[prev]`. Built between neighbours in seq order only:
                  transitivity carries the rest, and any inversion at all shows up in at
                  least one neighbour pair. NON-DECREASING, not increasing: two records may
                  share a timestamp.
  RULE_SEQ        a `seq` temporal operator of the rule table, `t[left] < t[right]` and
                  `t[right] - t[left] <= within`, built for a grounded instance ONLY when
                  both of the operator's slots carry evidence. In the slice's rule table
                  every `seq` rule declares evidence for one slot, so this kind is built
                  zero times today. It is implemented because the constraint is the rule
                  table's, not the data's, and a table that binds both slots is a
                  configuration change rather than a code change.

FEASIBILITY IS DECIDED IN ONE PASS, not by relaxation, and the reason is worth stating
because the specification names Bellman-Ford. With every timestamp pinned, the recorded
values ARE an assignment: the system is feasible exactly when every structural constraint
holds under them, and each structural constraint it fails is one negative cycle - that
constraint plus the two pins around it. Bellman-Ford is still run, in `feasible`, over the
system that remains when a correction set's pins are removed, because there the freed
variables can form a cycle that no single constraint reveals. The edge order there is
canonical and the step budget is a count, never a clock.

WHICH TIMESTAMPS TO DISBELIEVE. Removing an event's pins frees its timestamp, and a freed
timestamp can always be placed between its neighbours, so the system that remains is
feasible exactly when the timestamps still pinned are non-decreasing in `seq` within each
source. The smallest correction set is therefore the complement of a LONGEST NON-DECREASING
SUBSEQUENCE of each source's timestamps in `seq` order - not a cover of the violated
neighbour pairs. That distinction is not cosmetic: one record moved far back contradicts
only its neighbour, and a cover of that single pair is as likely to name the innocent
neighbour as the record that moved. The subsequence formulation names the record that
cannot stay, is exact at any size, and runs in n log n.

Rule-derived violations are corrected separately, by minimum vertex cover over the pairs
they contradict, exact while the number of events involved is at most the cap and a
documented greedy cover above it.

DETERMINISM. Constraints are built into a canonical order, each correction is chosen by an
explicit tie-break, and no set iteration reaches an output. Permuting the input events
changes nothing.

WHAT IT CANNOT SEE. A source whose every timestamp was rewritten consistently is
consistent, and invisible here. A forged chain is invisible here. Suppression on a source
with no `seq` is invisible here and in principle. This module must never be described as
detecting tampering, backdating or suppression at large: it detects a contradiction between
recorded values, which is one narrow and useful thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Final, Iterable, Mapping, Protocol, Sequence

from spectra_core import canon

__all__ = [
    "KIND_PIN",
    "KIND_RULE_SEQ",
    "KIND_SEQ_MONOTONIC",
    "ZERO_NODE",
    "Constraint",
    "TemporalResult",
    "Violation",
    "build_constraints",
    "correction_set",
    "feasible",
    "find_violations",
    "longest_non_decreasing",
    "monotonic_corrections",
    "run_pass",
]

#: The node every pin is measured against. Not an event id, and never confusable with one.
ZERO_NODE: Final[str] = "t:zero"

KIND_PIN: Final[str] = "PIN"
KIND_SEQ_MONOTONIC: Final[str] = "SEQ_MONOTONIC"
KIND_RULE_SEQ: Final[str] = "RULE_SEQ"

#: Relaxation rounds are bounded by |V| - 1; this multiplier bounds the whole run so a
#: pathological graph ends with a reported budget rather than a hang. A count, not a clock.
_BUDGET_FACTOR: Final[int] = 4


class _Event(Protocol):
    """What the pass reads from a canonical event, and all it reads."""

    event_id: Any
    source_id: Any
    seq: int
    t_evt_ns: int


@dataclass(frozen=True, slots=True)
class Constraint:
    """`t[v] - t[u] <= weight`, with the provenance that produced it.

    `event_id` is set on a PIN and names the event whose timestamp the pair of pins fixes.
    It is the only handle by which a constraint can be removed.
    """

    u: str
    v: str
    weight: int
    kind: str
    detail: str = ""
    event_id: str | None = None

    def sort_key(self) -> tuple[bytes, bytes, bytes, int]:
        return (
            canon.byte_order_key(self.kind),
            canon.byte_order_key(self.u),
            canon.byte_order_key(self.v),
            self.weight,
        )


@dataclass(frozen=True, slots=True)
class Violation:
    """One structural constraint the recorded timestamps do not satisfy."""

    constraint: Constraint
    excess_ns: int
    pins: tuple[Constraint, Constraint]

    @property
    def events(self) -> tuple[str, str]:
        """The two events either of which could be the one that is wrong."""
        return (self.constraint.u, self.constraint.v)

    def cycle(self) -> tuple[Constraint, ...]:
        """The negative cycle this violation is: u -> v, then v -> zero, then zero -> u.

        Its weight is `w - t[v] + t[u]`, which is negative exactly when the constraint is
        violated. The two pins are the lower pin of `v` and the upper pin of `u`; any other
        pair of pins would not close the cycle.
        """
        return (self.constraint, *self.pins)


@dataclass(frozen=True, slots=True)
class TemporalResult:
    """What the pass found. It names timestamps and sources; never a licence."""

    constraints: tuple[Constraint, ...]
    violations: tuple[Violation, ...]
    correction_set: tuple[str, ...]
    greedy: bool
    disputed_sources: tuple[str, ...]
    budget_exhausted: bool = False

    @property
    def consistent(self) -> bool:
        return not self.violations


def _pins(event: _Event) -> tuple[Constraint, Constraint]:
    event_id = str(event.event_id)
    t = int(event.t_evt_ns)
    return (
        Constraint(
            u=ZERO_NODE,
            v=event_id,
            weight=t,
            kind=KIND_PIN,
            detail="recorded timestamp, upper",
            event_id=event_id,
        ),
        Constraint(
            u=event_id,
            v=ZERO_NODE,
            weight=-t,
            kind=KIND_PIN,
            detail="recorded timestamp, lower",
            event_id=event_id,
        ),
    )


def build_constraints(
    events: Iterable[_Event],
    *,
    instances: Sequence[Any] = (),
    rule_seq: Mapping[str, Any] | None = None,
) -> tuple[Constraint, ...]:
    """Every constraint the recorded bundle and the rule table impose, canonically ordered.

    `rule_seq` maps a rule id to its `seq` operator, which must carry `left`, `right` and
    `within_ns`. An instance contributes a RULE_SEQ pair only when its evidence binds both
    slots; a rule that carries evidence for one slot relates a derived fact to a record,
    and a derived fact has no timestamp of its own to constrain.
    """
    materialised = list(events)
    out: list[Constraint] = []
    for event in materialised:
        out.extend(_pins(event))

    by_source: dict[str, list[_Event]] = {}
    for event in materialised:
        by_source.setdefault(str(event.source_id), []).append(event)
    for source_id, records in by_source.items():
        ordered = sorted(records, key=lambda e: (int(e.seq), canon.byte_order_key(str(e.event_id))))
        for previous, following in zip(ordered, ordered[1:]):
            # t[following] >= t[previous]  <=>  t[previous] - t[following] <= 0
            out.append(
                Constraint(
                    u=str(following.event_id),
                    v=str(previous.event_id),
                    weight=0,
                    kind=KIND_SEQ_MONOTONIC,
                    detail=f"{source_id} seq {previous.seq} -> {following.seq}",
                )
            )

    for instance in instances:
        operator = (rule_seq or {}).get(str(instance.rule_id))
        if operator is None or getattr(operator, "op", None) != "seq":
            continue
        bound = {str(ref.binding): str(ref.event_id) for ref in instance.evidence}
        left = bound.get(str(operator.left))
        right = bound.get(str(operator.right))
        if left is None or right is None:
            continue
        within = int(operator.within_ns)
        # t[right] - t[left] <= within, and t[left] < t[right] as t[left] - t[right] <= -1.
        out.append(
            Constraint(
                u=left,
                v=right,
                weight=within,
                kind=KIND_RULE_SEQ,
                detail=f"{instance.rule_id} within",
            )
        )
        out.append(
            Constraint(
                u=right,
                v=left,
                weight=-1,
                kind=KIND_RULE_SEQ,
                detail=f"{instance.rule_id} strict order",
            )
        )
    return tuple(sorted(dict.fromkeys(out), key=Constraint.sort_key))


def find_violations(
    constraints: Sequence[Constraint], times: Mapping[str, int]
) -> tuple[Violation, ...]:
    """The structural constraints the recorded timestamps fail, in constraint order.

    One pass, because the recorded values are themselves an assignment: see the module
    docstring. A missing timestamp is not a violation to report here; `build_constraints`
    pins every event it was given, so an unpinned node is a caller error and is skipped.
    """
    lower: dict[str, Constraint] = {}
    upper: dict[str, Constraint] = {}
    for constraint in constraints:
        if constraint.kind != KIND_PIN or constraint.event_id is None:
            continue
        if constraint.v == ZERO_NODE:
            lower[constraint.event_id] = constraint
        else:
            upper[constraint.event_id] = constraint

    out: list[Violation] = []
    for constraint in constraints:
        if constraint.kind == KIND_PIN:
            continue
        if constraint.u not in times or constraint.v not in times:
            continue
        excess = (times[constraint.v] - times[constraint.u]) - constraint.weight
        if excess <= 0:
            continue
        closing = (lower.get(constraint.v), upper.get(constraint.u))
        if closing[0] is None or closing[1] is None:
            continue
        out.append(Violation(constraint=constraint, excess_ns=excess, pins=(closing[0], closing[1])))
    return tuple(out)


def longest_non_decreasing(values: Sequence[int]) -> tuple[int, ...]:
    """Indices of a longest non-decreasing subsequence of `values`, in ascending order.

    n log n, by patience on the tails. When several subsequences are longest, this returns
    the one the tails reconstruct, which keeps the smallest tail available at each length:
    for `[20, 10]` it keeps the 10 and the correction names the 20. That is deterministic
    and it is a function of the values alone, which is what the certificate needs; it is
    not a claim that the earlier record is the more trustworthy one. The consequence is
    pinned by `test_a_tie_is_broken_lexicographically`.
    """
    from bisect import bisect_right

    tails: list[int] = []  # tails[k] = index of the smallest tail of a length-(k+1) run
    parent: list[int] = [-1] * len(values)
    for index, value in enumerate(values):
        position = bisect_right([values[t] for t in tails], value)
        if position > 0:
            parent[index] = tails[position - 1]
        if position == len(tails):
            tails.append(index)
        else:
            tails[position] = index
    out: list[int] = []
    cursor = tails[-1] if tails else -1
    while cursor >= 0:
        out.append(cursor)
        cursor = parent[cursor]
    return tuple(reversed(out))


def monotonic_corrections(events: Iterable[_Event]) -> tuple[str, ...]:
    """The fewest events whose timestamps must be disbelieved for each source to be ordered.

    Exact at any size: the complement of a longest non-decreasing subsequence of the
    source's timestamps in `seq` order. See the module docstring for why this is the right
    set rather than a cover of the violated pairs.
    """
    by_source: dict[str, list[_Event]] = {}
    for event in events:
        by_source.setdefault(str(event.source_id), []).append(event)
    out: list[str] = []
    for _source_id, records in sorted(by_source.items(), key=lambda kv: canon.byte_order_key(kv[0])):
        ordered = sorted(
            records, key=lambda e: (int(e.seq), canon.byte_order_key(str(e.event_id)))
        )
        keep = set(longest_non_decreasing([int(e.t_evt_ns) for e in ordered]))
        out.extend(
            str(event.event_id) for index, event in enumerate(ordered) if index not in keep
        )
    return tuple(sorted(out, key=canon.byte_order_key))


def correction_set(
    violations: Sequence[Violation], *, cap: int, already: Iterable[str] = ()
) -> tuple[tuple[str, ...], bool]:
    """A minimum vertex cover of the violated pairs, for violations not already corrected.

    Used for the rule-derived violations; the monotonicity ones are corrected exactly by
    `monotonic_corrections`. Exact by minimum-cardinality search with the lexicographically
    least cover chosen among equal-sized ones, while the number of candidate events is at
    most `cap`. Above the cap it is a greedy cover - repeatedly the event covering the most
    remaining pairs, ties broken lexicographically - and the caller is told so, because a
    greedy cover may be larger than necessary and a rendering that hid that would overstate
    what was found.
    """
    covered = frozenset(already)
    pairs = [frozenset(v.events) for v in violations if not (frozenset(v.events) & covered)]
    if not pairs:
        return ((), False)
    candidates = sorted({event for pair in pairs for event in pair}, key=canon.byte_order_key)

    if len(candidates) <= cap:
        for size in range(1, len(candidates) + 1):
            for combination in combinations(candidates, size):
                chosen = frozenset(combination)
                if all(pair & chosen for pair in pairs):
                    return (tuple(combination), False)

    remaining = list(pairs)
    cover: list[str] = []
    while remaining:
        counts = {event: sum(1 for pair in remaining if event in pair) for event in candidates}
        best = min(
            (event for event in candidates if counts[event]),
            key=lambda e: (-counts[e], canon.byte_order_key(e)),
        )
        cover.append(best)
        remaining = [pair for pair in remaining if best not in pair]
    return (tuple(sorted(cover, key=canon.byte_order_key)), True)


def feasible(
    constraints: Sequence[Constraint],
    times: Mapping[str, int],
    *,
    removed: frozenset[str],
) -> bool:
    """Whether the system is satisfiable once `removed`'s pins are gone: Bellman-Ford.

    Run over the system that remains, where the freed variables can form a negative cycle
    no single constraint reveals. Edges are relaxed in the canonical constraint order and
    the rounds are counted, never timed. `times` is unused except to confirm every pinned
    event has a value; the reduced system is decided structurally.
    """
    kept = [
        c for c in constraints if not (c.kind == KIND_PIN and c.event_id in removed)
    ]
    nodes = sorted(
        {c.u for c in kept} | {c.v for c in kept} | {ZERO_NODE}, key=canon.byte_order_key
    )
    distance = {node: 0 for node in nodes}  # virtual source with a zero edge to every node
    budget = _BUDGET_FACTOR * max(len(nodes), 1)
    rounds = 0
    while rounds < min(len(nodes), budget):
        changed = False
        for constraint in kept:
            candidate = distance[constraint.u] + constraint.weight
            if candidate < distance[constraint.v]:
                distance[constraint.v] = candidate
                changed = True
        rounds += 1
        if not changed:
            return True
    for constraint in kept:
        if distance[constraint.u] + constraint.weight < distance[constraint.v]:
            return False
    return True


def run_pass(
    events: Iterable[_Event],
    *,
    instances: Sequence[Any] = (),
    rule_seq: Mapping[str, Any] | None = None,
    cap: int,
) -> TemporalResult:
    """Build, check, and name what would have to be disbelieved. Removes nothing."""
    materialised = list(events)
    constraints = build_constraints(materialised, instances=instances, rule_seq=rule_seq)
    times = {str(e.event_id): int(e.t_evt_ns) for e in materialised}
    violations = find_violations(constraints, times)
    monotonic = monotonic_corrections(materialised)
    rule_violations = [v for v in violations if v.constraint.kind != KIND_SEQ_MONOTONIC]
    extra, greedy = correction_set(rule_violations, cap=cap, already=monotonic)
    chosen = tuple(sorted(set(monotonic) | set(extra), key=canon.byte_order_key))
    source_of = {str(e.event_id): str(e.source_id) for e in materialised}
    disputed = tuple(
        sorted({source_of[event] for event in chosen if event in source_of}, key=canon.byte_order_key)
    )
    budget_exhausted = bool(chosen) and not feasible(
        constraints, times, removed=frozenset(chosen)
    )
    return TemporalResult(
        constraints=constraints,
        violations=violations,
        correction_set=chosen,
        greedy=greedy,
        disputed_sources=disputed,
        budget_exhausted=budget_exhausted,
    )
