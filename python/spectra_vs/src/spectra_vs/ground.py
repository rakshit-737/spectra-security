"""S8: semi-naive fixpoint evaluation with provenance over the OBSERVED facts.

WHAT THIS STAGE PRODUCES. `P_min`: the bipartite AND/OR hypergraph of everything the
bundle actually supports. OR-nodes are facts, AND-nodes are rule instances, an instance
carries one edge to its head and one edge from each body literal, and every instance
carries the evidence that grounded it, dereferencing to real record identities in the
hashed bundle.

OBSERVED ONLY. Nothing here reads a liveness document and nothing here mints a licence.
An instance this stage emits cites evidence; a step nobody could have seen is the
envelope's business, and keeping the two stages apart is what makes `P_min` the honest
lower side of the bracket rather than a mixture.

GROUND TRUTH IS NEVER READ. This module opens no file at all: it is handed the bundle
records and the entity-resolution bindings and returns a value. `truth.jsonl` exists for
evaluation and a stage that reads it is the defect the whole design exists to prevent.

THE THREE CONTRACTS THIS STAGE FIXES, all of which the operative specification leaves to
the implementation and all of which are chosen conservatively:

  1. AXIOM ARGUMENT ORDER. An event of type `E` with entity-resolution bindings
     `{role: entity_id}` seeds the fact `E(entity_ids..., tick)` whose argument vector is
     the bindings ORDERED BY ROLE NAME ASCENDING. A rule pattern binds its variables
     positionally against that vector. Ordering by role name rather than by insertion is
     what stops the fact key from depending on the order `er.json` happened to list a
     binding in.

  2. EVIDENCE REACHES ONLY AS FAR AS THE AXIOM SLOTS. An instance's evidence is the
     records behind the body facts that came straight from the bundle. A body fact that
     was itself derived contributes no evidence here, because its own instance already
     carries it and the witness tree recurses into it. Duplicating the transitive closure
     into every instance would make evidence quadratic and would let one record appear as
     though it had been observed many times.

  3. ABSENCE WITHOUT A LIVENESS DOCUMENT. The pipeline gives this stage the bundle and
     `er.json` and no liveness. It therefore cannot distinguish an OBSERVED-negative from
     an UNDETERMINED one, so it fails closed: an absence literal is satisfied here only
     when no matching fact exists over the sealed lookback AND every producing source of
     the absent pattern has at least one record inside that lookback. A caller holding a
     real liveness document passes `absence_availability` and overrides the proxy. The
     proxy never returns LICENSED: a licence is minted by S7/S9 or not at all.

DETERMINISM. Facts, instances, licences and the adjacency lists are emitted as tuples
sorted by their declared total keys. No output path iterates a dict or a set. The fixpoint
is re-run under shuffled rule orderings by the property test and must produce byte-identical
output, which is why every ordering here is a content key and never an insertion order.

APPEND-ONLY. A fact is never retracted and an instance is never withdrawn. Expiry is a
later fact not being derived, so the fact base grows monotonically across iterations; the
loader rejects any rule that would express a deletion.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from spectra_core import canon, model
from spectra_core.errors import LimitError, SchemaError
from spectra_core.ids import EntityId, EventId, FactHash, SourceId
from spectra_vs import rules as rules_mod
from spectra_vs import scf as scf_mod
from spectra_vs.rules import CompiledRule, Pattern, RuleTable

__all__ = [
    "MAX_FACTS",
    "MAX_INSTANCES",
    "MAX_ITERATIONS",
    "Absence",
    "Binding",
    "Counts",
    "Engine",
    "GroundingResult",
    "Program",
    "axiom_fact_for",
    "bundle_absence_proxy",
    "goal_candidates",
    "ground",
    "program_document",
    "scf_dumps",
    "write_program",
]


# ---------------------------------------------------------------------------
# Caps. Every cap is a deterministic counter; there is no wall-clock budget.
# ---------------------------------------------------------------------------

MAX_FACTS: Final[int] = 200_000
MAX_INSTANCES: Final[int] = 500_000
MAX_ITERATIONS: Final[int] = 1_000


class Absence(StrEnum):
    """The three outcomes of the only permitted negation.

    OBSERVED facts enter both programs, LICENSED and UNDETERMINED ones enter `P_max` only.
    There is no fourth value and no default: a caller that cannot decide returns
    UNDETERMINED, which is the fail-closed answer, not a shrug.
    """

    OBSERVED = "OBSERVED"
    LICENSED = "LICENSED"
    UNDETERMINED = "UNDETERMINED"


#: How a caller answers "was every producing source of this absent pattern live over the
#: sealed lookback". Given the sources and the lookback interval, return an `Absence`.
AbsenceAvailability = Callable[[tuple[SourceId, ...], model.Interval], Absence]


@dataclass(frozen=True, slots=True)
class Binding:
    """One entity-resolution binding: this record's `role` resolved to this entity."""

    event_id: EventId
    role: str
    entity_id: EntityId

    def sort_key(self) -> tuple[str, str]:
        return (str(self.event_id), self.role)


@dataclass(frozen=True, slots=True)
class Counts:
    """The four published counters. `observed_events` never includes a silent instance."""

    observed_instances: int = 0
    silent_instances: int = 0
    ghost_facts: int = 0
    observed_events: int = 0


@dataclass(frozen=True, slots=True)
class Program:
    """One side of the two-sided bracket, as a bipartite AND/OR hypergraph.

    `by_body` is the adjacency the reachability pass walks: body fact -> the indices of the
    instances that fact feeds, with the index lists sorted by instance id. It is stored as
    a sorted tuple rather than a dict so that nothing downstream can iterate it in
    insertion order; `body_index` hands back a lookup table built from those sorted pairs.
    """

    kind: model.ProgramKind
    facts: tuple[model.Fact, ...]
    instances: tuple[model.RuleInstance, ...]
    licences: tuple[model.Licence, ...]
    axioms: tuple[FactHash, ...]
    goal: FactHash | None
    counts: Counts
    by_body: tuple[tuple[FactHash, tuple[int, ...]], ...]
    ghosts: tuple[FactHash, ...] = ()
    capped: bool = False

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(self.facts, lambda f: str(f.fact_key), where="Program.facts")
        canon.check_strictly_ascending(
            self.instances, lambda i: str(i.instance_id), where="Program.instances"
        )
        canon.check_strictly_ascending(
            self.licences, lambda lc: lc.sort_key(), where="Program.licences"
        )
        canon.check_strictly_ascending(self.axioms, str, where="Program.axioms")
        canon.check_strictly_ascending(self.ghosts, str, where="Program.ghosts")
        canon.check_strictly_ascending(
            self.by_body, lambda pair: str(pair[0]), where="Program.by_body"
        )
        if self.kind is model.ProgramKind.P_MIN and self.licences:
            raise SchemaError("Program: PMin carries no licences; a licence is the envelope's")

    def body_index(self) -> dict[FactHash, tuple[int, ...]]:
        """A lookup table built from the sorted pairs. Built fresh, never iterated."""
        return dict(self.by_body)

    def fact(self, fact_key: FactHash) -> model.Fact:
        for candidate in self.facts:
            if candidate.fact_key == fact_key:
                return candidate
        raise KeyError(fact_key)


@dataclass(frozen=True, slots=True)
class GroundingResult:
    """The program plus the deterministic counters the certificate publishes."""

    program: Program
    iterations: int
    fixpoint_steps: int
    capped: bool
    cap_detail: str = ""


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def axiom_fact_for(
    event: model.CanonicalEvent, roles: Sequence[tuple[str, EntityId]]
) -> model.Fact:
    """Seed one axiom fact from one bundle record.

    The argument vector is the record's bindings ordered by role name ascending; see the
    module docstring for why that order and not the order `er.json` listed them in.
    """
    ordered = tuple(
        entity_id
        for _, entity_id in sorted(roles, key=lambda pair: canon.byte_order_key(pair[0]))
    )
    return model.Fact.mint(event.event_type, ordered, event.tick)


def bundle_absence_proxy(
    events: Sequence[model.CanonicalEvent],
) -> AbsenceAvailability:
    """The fail-closed absence oracle S8 uses when no liveness document is available.

    It answers OBSERVED only when every producing source has at least one record inside the
    sealed lookback, which is the most this stage can say from the bundle alone. It never
    answers LICENSED, because a licence is minted by the liveness stage or not at all, and
    manufacturing one here would put an unobserved step into the lower side of the bracket.
    """
    by_source: dict[str, list[int]] = {}
    for event in events:
        by_source.setdefault(str(event.source_id), []).append(event.t_evt_ns)
    for times in by_source.values():
        times.sort()

    def answer(sources: tuple[SourceId, ...], window: model.Interval) -> Absence:
        for source_id in sources:
            times = by_source.get(str(source_id), ())
            if not any(window.contains(t) for t in times):
                return Absence.UNDETERMINED
        return Absence.OBSERVED

    return answer


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


class Engine:
    """The semi-naive fixpoint, shared by S8 and S9.

    S9 builds a second `Engine` over the same inputs, saturates it to reproduce `P_min`
    exactly, then adds licensed silent instances and saturates again. Sharing the engine
    rather than copying it is what makes `P_min` a subset of `P_max` structurally rather
    than by inspection.
    """

    def __init__(
        self,
        table: RuleTable,
        events: Sequence[model.CanonicalEvent],
        bindings: Sequence[Binding],
        *,
        absence_availability: AbsenceAvailability | None = None,
    ) -> None:
        self.table = table
        self.events = tuple(sorted(events, key=lambda e: e.sort_key()))
        self._roles: dict[str, list[tuple[str, EntityId]]] = {}
        for binding in sorted(bindings, key=lambda b: b.sort_key()):
            self._roles.setdefault(str(binding.event_id), []).append(
                (binding.role, binding.entity_id)
            )
        self._absence = (
            absence_availability
            if absence_availability is not None
            else bundle_absence_proxy(self.events)
        )

        self._facts: dict[str, model.Fact] = {}
        self._by_pred: dict[tuple[str, int], list[model.Fact]] = {}
        self._instances: dict[str, model.RuleInstance] = {}
        self._axioms: set[str] = set()
        self._axiom_events: dict[str, list[model.CanonicalEvent]] = {}
        self._licensed_facts: set[str] = set()
        self._ghost_facts: set[str] = set()
        self._delta: list[model.Fact] = []
        # Time-freeness is read from a snapshot taken when a saturation begins, never from
        # the live set. A predicate that changed mid-pass would make the derived instances
        # depend on the order the rules happened to be visited in, which is the one thing
        # the rule-ordering property test exists to catch.
        self._time_free_snapshot: frozenset[str] = frozenset()

        self.iterations = 0
        self.fixpoint_steps = 0
        self.capped = False
        self.cap_detail = ""

    # -- fact base ---------------------------------------------------------

    def _add_fact(self, fact: model.Fact) -> bool:
        key = str(fact.fact_key)
        if key in self._facts:
            return False
        if len(self._facts) >= MAX_FACTS:
            self.record_cap(f"MAX_FACTS={MAX_FACTS} reached at {len(self._facts)} facts")
            return False
        self._facts[key] = fact
        bucket = self._by_pred.setdefault((fact.predicate, len(fact.args)), [])
        # Inserted in place rather than appended and re-sorted. The bucket is an invariant
        # (ascending by fact key), and re-sorting a list that is already sorted except for
        # its last element costs O(n log n) per insertion, which is O(n^2 log n) over a
        # predicate the generator emits thousands of times. The resulting order is
        # identical; only the cost of maintaining it changes.
        bisect.insort(bucket, fact, key=lambda f: canon.byte_order_key(str(f.fact_key)))
        self._delta.append(fact)
        return True

    def record_cap(self, detail: str) -> None:
        """Set the grounding cap flag and record the measured size.

        A capped run can never be ROBUST, so the flag is never cleared once set and the
        first detail is kept: the earliest cap is the one that shaped everything after it.
        """
        self.capped = True
        if not self.cap_detail:
            self.cap_detail = detail

    def facts_for(self, predicate: str, arity: int) -> tuple[model.Fact, ...]:
        return tuple(self._by_pred.get((predicate, arity), ()))

    def is_licensed_fact(self, fact_key: FactHash) -> bool:
        return str(fact_key) in self._licensed_facts

    def has_fact(self, fact_key: FactHash) -> bool:
        return str(fact_key) in self._facts

    # -- seeding -----------------------------------------------------------

    def seed(self) -> None:
        """Seed the fact base from the bundle through the entity-resolution bindings."""
        for event in self.events:
            roles = self._roles.get(str(event.event_id), [])
            fact = axiom_fact_for(event, roles)
            key = str(fact.fact_key)
            self._add_fact(fact)
            self._axioms.add(key)
            self._axiom_events.setdefault(key, []).append(event)
        for bucket in self._axiom_events.values():
            bucket.sort(key=lambda e: e.sort_key())

    # -- instances ---------------------------------------------------------

    def add_instance(self, instance: model.RuleInstance, head: model.Fact) -> bool:
        """Add one instance and its head fact. Returns True when the instance is new."""
        key = str(instance.instance_id)
        if key in self._instances:
            return False
        if len(self._instances) >= MAX_INSTANCES:
            self.record_cap(f"MAX_INSTANCES={MAX_INSTANCES} reached at {len(self._instances)}")
            return False
        self._instances[key] = instance
        self._add_fact(head)
        if instance.observed is model.Observation.LICENSED:
            head_key = str(head.fact_key)
            # A fact is time-unconstrained while every instance supporting it is licensed:
            # the tick of a licensed instance represents an interval, not an observation.
            if not any(
                other.head == head.fact_key
                and other.observed is model.Observation.OBSERVED
                for other in self._instances.values()
            ):
                self._licensed_facts.add(head_key)
            if instance.ghost:
                self._ghost_facts.add(head_key)
        else:
            self._licensed_facts.discard(str(head.fact_key))
            self._ghost_facts.discard(str(head.fact_key))
        return True

    # -- the fixpoint ------------------------------------------------------

    def saturate(self) -> None:
        """Iterate the detect rules to fixpoint, semi-naively.

        Obligation rules are deliberately not evaluated: an obligation's head is by
        construction a step nobody observed, so the only honest place to instantiate one is
        the envelope, where a licence can be cited or a permanent blind spot recorded.
        """
        self._time_free_snapshot = frozenset(self._licensed_facts)
        delta = self._take_delta()
        while delta:
            self.iterations += 1
            if self.iterations > MAX_ITERATIONS:
                self.record_cap(f"MAX_ITERATIONS={MAX_ITERATIONS} reached")
                return
            delta_keys = {str(f.fact_key) for f in delta}
            for compiled in self.table.detect_rules:
                self._apply(compiled, delta_keys)
            delta = self._take_delta()

    def _take_delta(self) -> tuple[model.Fact, ...]:
        delta = tuple(
            sorted(self._delta, key=lambda f: canon.byte_order_key(str(f.fact_key)))
        )
        self._delta = []
        return delta

    def _apply(self, compiled: CompiledRule, delta_keys: set[str]) -> None:
        """Join one rule's body against the base, requiring at least one delta fact."""
        for pivot in range(len(compiled.body)):
            for chosen, bind in self._enumerate(compiled, 0, {}, [], pivot, delta_keys):
                self.fixpoint_steps += 1
                self._emit(compiled, tuple(chosen), bind)

    def _enumerate(
        self,
        compiled: CompiledRule,
        slot: int,
        bind: dict[str, object],
        chosen: list[model.Fact],
        pivot: int,
        delta_keys: set[str],
    ) -> Iterable[tuple[list[model.Fact], dict[str, object]]]:
        if slot == len(compiled.body):
            yield list(chosen), dict(bind)
            return
        pattern = compiled.body[slot]
        for fact in self.facts_for(pattern.predicate, pattern.arity):
            if slot == pivot and str(fact.fact_key) not in delta_keys:
                continue
            extended = _unify(pattern, fact, bind)
            if extended is None:
                continue
            chosen.append(fact)
            yield from self._enumerate(
                compiled, slot + 1, extended, chosen, pivot, delta_keys
            )
            chosen.pop()

    def _emit(
        self, compiled: CompiledRule, chosen: tuple[model.Fact, ...], bind: dict[str, object]
    ) -> None:
        # A licensed body fact's tick stands for an interval, so neither the temporal
        # operators nor the data guard are evaluated against it. Suspending the whole guard
        # rather than part of it is the over-approximating direction; the entity joins it
        # would have restated are still enforced, because a variable repeated across two
        # patterns is unified before the guard is ever consulted.
        time_free = any(self._time_free(fact) for fact in chosen)
        if not time_free:
            guard_env = _guard_env(compiled, chosen)
            if not rules_mod.eval_when(compiled.when, guard_env):
                return
        extra_facts = self._check_temporal(compiled, chosen, bind)
        if extra_facts is None:
            return
        evidence = self._evidence_for(compiled, chosen, extra_facts)
        if not evidence:
            # A detect rule is required at load time to carry an axiom slot, so an empty
            # evidence set here means the bundle carries no record for that slot's fact.
            return
        head = _head_fact(compiled, bind)
        if head is None:
            return
        instance = model.RuleInstance.mint(
            rule_id=compiled.rule.rule_id,
            rule_version=compiled.rule.rule_version,
            head=head.fact_key,
            body=tuple(f.fact_key for f in chosen),
            blockers=compiled.blockers,
            observed=model.Observation.OBSERVED,
            tick=head.tick,
            evidence=evidence,
        )
        self.add_instance(instance, head)

    # -- temporal operators ------------------------------------------------

    def _check_temporal(
        self,
        compiled: CompiledRule,
        chosen: tuple[model.Fact, ...],
        bind: dict[str, object],
    ) -> tuple[model.Fact, ...] | None:
        """Return the extra facts an operator consumed, or None when the operator fails."""
        temporal = compiled.temporal
        if temporal is None:
            return ()
        match temporal.op:
            case "seq":
                return self._check_seq(compiled, chosen, temporal)
            case "distinct":
                return self._check_distinct(compiled, chosen, bind, temporal)
            case "absence":
                return self._check_absence(compiled, chosen, bind, temporal)
            case _:
                return None

    def _time_free(self, fact: model.Fact) -> bool:
        """A licensed fact's tick represents an interval, so it is not compared against one.

        Skipping the comparison is the over-approximating direction, which is what keeps
        `P_max` a superset of the union over realizable worlds rather than a sample of it.
        """
        return str(fact.fact_key) in self._time_free_snapshot

    def _check_seq(
        self,
        compiled: CompiledRule,
        chosen: tuple[model.Fact, ...],
        temporal: rules_mod.Temporal,
    ) -> tuple[model.Fact, ...] | None:
        left = chosen[compiled.slot_of(temporal.left)]
        right = chosen[compiled.slot_of(temporal.right)]
        if self._time_free(left) or self._time_free(right):
            return ()
        if not left.tick < right.tick:
            return None
        if right.tick - left.tick > temporal.within_ticks:
            return None
        return ()

    def _check_distinct(
        self,
        compiled: CompiledRule,
        chosen: tuple[model.Fact, ...],
        bind: dict[str, object],
        temporal: rules_mod.Temporal,
    ) -> tuple[model.Fact, ...] | None:
        slot = compiled.slot_of(temporal.of_slot)
        pattern = compiled.body[slot]
        anchor = chosen[slot]
        if temporal.field_name not in pattern.entity_vars:
            raise SchemaError(
                f"{compiled.rule_id}: distinct field {temporal.field_name!r} is not an "
                f"argument of slot {temporal.of_slot}"
            )
        field_index = pattern.entity_vars.index(temporal.field_name)
        low = anchor.tick - temporal.within_ticks
        participating: list[model.Fact] = []
        values: set[str] = set()
        for candidate in self.facts_for(pattern.predicate, pattern.arity):
            if not low <= candidate.tick <= anchor.tick:
                continue
            if not _agrees_except(pattern, candidate, bind, field_index):
                continue
            participating.append(candidate)
            values.add(str(candidate.args[field_index]))
        if len(values) < temporal.n:
            return None
        participating.sort(key=lambda f: canon.byte_order_key(str(f.fact_key)))
        return tuple(participating)

    def _check_absence(
        self,
        compiled: CompiledRule,
        chosen: tuple[model.Fact, ...],
        bind: dict[str, object],
        temporal: rules_mod.Temporal,
    ) -> tuple[model.Fact, ...] | None:
        pattern = temporal.of_pattern
        assert pattern is not None
        anchor = chosen[compiled.slot_of(temporal.before)]
        low_tick = anchor.tick - temporal.within_ticks
        for candidate in self.facts_for(pattern.predicate, pattern.arity):
            if not low_tick <= candidate.tick < anchor.tick:
                continue
            if _unify(pattern, candidate, dict(bind), tick_free=True) is not None:
                return None
        window = model.Interval(
            low_tick * rules_mod.TICK_NS, anchor.tick * rules_mod.TICK_NS
        )
        if self._absence(compiled.rule.producing_sources, window) is not Absence.OBSERVED:
            return None
        return ()

    # -- evidence ----------------------------------------------------------

    def _evidence_for(
        self,
        compiled: CompiledRule,
        chosen: tuple[model.Fact, ...],
        extra_facts: tuple[model.Fact, ...],
    ) -> tuple[model.EvidenceRef, ...]:
        refs: list[model.EvidenceRef] = []
        seen: set[tuple[str, str]] = set()
        for index, fact in enumerate(chosen):
            binding = rules_mod.SLOT_NAMES[index]
            for event in self._axiom_events.get(str(fact.fact_key), ()):
                key = (binding, str(event.event_id))
                if key in seen:
                    continue
                seen.add(key)
                refs.append(
                    model.EvidenceRef(
                        binding=binding,
                        event_id=event.event_id,
                        source_id=event.source_id,
                        t_evt_ns=event.t_evt_ns,
                    )
                )
        if extra_facts and compiled.temporal is not None and compiled.temporal.of_slot:
            binding = compiled.temporal.of_slot
            for fact in extra_facts:
                for event in self._axiom_events.get(str(fact.fact_key), ()):
                    key = (binding, str(event.event_id))
                    if key in seen:
                        continue
                    seen.add(key)
                    refs.append(
                        model.EvidenceRef(
                            binding=binding,
                            event_id=event.event_id,
                            source_id=event.source_id,
                            t_evt_ns=event.t_evt_ns,
                        )
                    )
        refs.sort(key=lambda r: r.sort_key())
        return tuple(refs)

    # -- snapshot ----------------------------------------------------------

    def snapshot(
        self,
        kind: model.ProgramKind,
        *,
        goal: FactHash | None = None,
        licences: Sequence[model.Licence] = (),
    ) -> Program:
        facts = tuple(
            sorted(self._facts.values(), key=lambda f: canon.byte_order_key(str(f.fact_key)))
        )
        instances = tuple(
            sorted(
                self._instances.values(),
                key=lambda i: canon.byte_order_key(str(i.instance_id)),
            )
        )
        index_of = {str(inst.instance_id): position for position, inst in enumerate(instances)}
        adjacency: dict[str, list[int]] = {}
        for inst in instances:
            for fact_key in inst.body:
                adjacency.setdefault(str(fact_key), []).append(index_of[str(inst.instance_id)])
        by_body = tuple(
            (FactHash(key), tuple(sorted(set(values))))
            for key, values in sorted(adjacency.items(), key=lambda kv: canon.byte_order_key(kv[0]))
        )
        # An axiom of the published program is a fact with no supporting instance BODY,
        # which is the reachability pass's own definition: the bundle-seeded facts, plus
        # any fact whose only support is an instance with an empty body. An empty-body
        # instance can never be fired by unit propagation, because nothing decrements its
        # counter, so its head has to enter the queue as an axiom or it would be published
        # and then be unreachable.
        supported = {str(inst.head) for inst in instances if inst.body}
        axioms = tuple(
            sorted(
                (FactHash(key) for key in self._facts if key not in supported),
                key=canon.byte_order_key,
            )
        )
        observed_event_ids = {
            str(ref.event_id)
            for inst in instances
            if inst.observed is model.Observation.OBSERVED
            for ref in inst.evidence
        }
        ghosts = tuple(
            sorted((FactHash(key) for key in self._ghost_facts), key=canon.byte_order_key)
        )
        counts = Counts(
            observed_instances=sum(
                1 for i in instances if i.observed is model.Observation.OBSERVED
            ),
            silent_instances=sum(
                1 for i in instances if i.observed is model.Observation.LICENSED
            ),
            ghost_facts=len(ghosts),
            observed_events=len(observed_event_ids),
        )
        return Program(
            kind=kind,
            facts=facts,
            instances=instances,
            licences=tuple(sorted(licences, key=lambda lc: lc.sort_key())),
            axioms=axioms,
            goal=goal,
            counts=counts,
            by_body=by_body,
            ghosts=ghosts,
            capped=self.capped,
        )

    def assert_ghost_support(self) -> None:
        """A GHOST may never be the sole support of a PROPAGATES-class edge.

        Checked rather than assumed: a chain that only propagates because of an inferred,
        unobserved node would be a hypothesis rendered as a mechanism.
        """
        for inst in self._instances.values():
            compiled = self.table.get(str(inst.rule_id))
            if compiled.rule.causal_relation != "PROPAGATES":
                continue
            if inst.body and all(str(key) in self._ghost_facts for key in inst.body):
                raise SchemaError(
                    f"{inst.instance_id}: every body fact of a PROPAGATES instance of "
                    f"{inst.rule_id} is a GHOST; an inferred node may not be the sole "
                    "support of a propagation edge"
                )


# ---------------------------------------------------------------------------
# Unification helpers
# ---------------------------------------------------------------------------


def _unify(
    pattern: Pattern, fact: model.Fact, bind: dict[str, object], *, tick_free: bool = False
) -> dict[str, object] | None:
    """Bind a pattern's variables against a fact, or return None on a conflict.

    A variable repeated across two patterns is an equality join, which is why a conflict is
    a silent skip rather than an error: it simply means these two facts are not the pair
    this rule is about.
    """
    if fact.predicate != pattern.predicate or len(fact.args) != pattern.arity:
        return None
    extended = dict(bind)
    for name, value in zip(pattern.entity_vars, fact.args, strict=True):
        previous = extended.get(name)
        if previous is not None and previous != value:
            return None
        extended[name] = value
    if not tick_free:
        tick_name = pattern.tick_var
        previous_tick = extended.get(tick_name)
        if previous_tick is not None and previous_tick != fact.tick:
            return None
        extended[tick_name] = fact.tick
    return extended


def _agrees_except(
    pattern: Pattern, fact: model.Fact, bind: dict[str, object], free_index: int
) -> bool:
    """True when `fact` matches every bound argument of `pattern` except `free_index`."""
    if fact.predicate != pattern.predicate or len(fact.args) != pattern.arity:
        return False
    for index, name in enumerate(pattern.entity_vars):
        if index == free_index:
            continue
        expected = bind.get(name)
        if expected is not None and expected != fact.args[index]:
            return False
    return True


def _guard_env(
    compiled: CompiledRule, chosen: Sequence[model.Fact]
) -> dict[str, object]:
    """Build the `when` environment: `<slot>.t` for the tick, `<slot>.<var>` for arguments."""
    env: dict[str, object] = {}
    for index, fact in enumerate(chosen):
        slot = rules_mod.SLOT_NAMES[index]
        pattern = compiled.body[index]
        env[f"{slot}.t"] = fact.tick
        for name, value in zip(pattern.entity_vars, fact.args, strict=True):
            env[f"{slot}.{name}"] = str(value)
    return env


def _head_fact(compiled: CompiledRule, bind: dict[str, object]) -> model.Fact | None:
    """Mint the head fact from the bound variables, or None when a variable is unbound."""
    args: list[EntityId] = []
    for name in compiled.head.entity_vars:
        value = bind.get(name)
        if not isinstance(value, EntityId):
            return None
        args.append(value)
    tick = bind.get(compiled.head.tick_var)
    if not isinstance(tick, int) or isinstance(tick, bool):
        return None
    return model.Fact.mint(compiled.head.predicate, tuple(args), tick)


# ---------------------------------------------------------------------------
# The stage entry point
# ---------------------------------------------------------------------------


def ground(
    table: RuleTable,
    events: Sequence[model.CanonicalEvent],
    bindings: Sequence[Binding],
    *,
    goal: FactHash | None = None,
    absence_availability: AbsenceAvailability | None = None,
) -> GroundingResult:
    """Run the observed fixpoint and return `P_min` with its deterministic counters.

    `goal` is a parameter rather than something chosen here: the goal library is S10's
    input and picking one inside the grounder would make the program depend on the question
    being asked of it. `goal_candidates` is the helper a caller uses to find one.
    """
    engine = Engine(table, events, bindings, absence_availability=absence_availability)
    engine.seed()
    engine.saturate()
    engine.assert_ghost_support()
    program = engine.snapshot(model.ProgramKind.P_MIN, goal=goal)
    return GroundingResult(
        program=program,
        iterations=engine.iterations,
        fixpoint_steps=engine.fixpoint_steps,
        capped=engine.capped,
        cap_detail=engine.cap_detail,
    )


def goal_candidates(program: Program, predicate: str) -> tuple[FactHash, ...]:
    """Every derived fact of one predicate, ascending by fact key."""
    return tuple(
        sorted(
            (f.fact_key for f in program.facts if f.predicate == predicate),
            key=canon.byte_order_key,
        )
    )


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------

#: Nesting ceiling from the encoding rules. `spectra_vs.scf` owns every other clause of
#: the law; only the depth bound is added here, so there is still exactly one serialiser.
_MAX_DEPTH: Final[int] = 8


def _check_depth(value: object, depth: int) -> None:
    if depth > _MAX_DEPTH:
        raise LimitError(f"nesting deeper than {_MAX_DEPTH}", code="E-LIMIT-DEPTH")
    if isinstance(value, dict):
        for item in value.values():
            _check_depth(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_depth(item, depth + 1)


def scf_dumps(value: object) -> str:
    """Serialise under the global encoding law, with exactly one trailing newline.

    The law itself lives in `spectra_vs.scf`, which every slice artifact is written
    through: UTF-8, NFC, LF only, keys sorted by byte value, no insignificant whitespace,
    no float in a number position, no `null`, and a bare JSON integer only inside u32. This
    wrapper adds the nesting bound and nothing else, so there is one place to change if the
    law changes.
    """
    _check_depth(value, 0)
    return scf_mod.scf_line(value)


def _fact_document(fact: model.Fact) -> dict[str, object]:
    return {
        "args": [str(a) for a in fact.args],
        "fact_key": str(fact.fact_key),
        "predicate": fact.predicate,
        "tick": fact.tick,
    }


def _instance_document(instance: model.RuleInstance) -> dict[str, object]:
    document: dict[str, object] = {
        "blockers": [canon.mask_hex(m) for m in instance.blockers],
        "body": [str(b) for b in instance.body],
        "ghost": instance.ghost,
        "head": str(instance.head),
        "instance_id": str(instance.instance_id),
        "license_ids": [str(lid) for lid in instance.license_ids],
        "observed": str(instance.observed),
        "rule_id": str(instance.rule_id),
        "rule_version": instance.rule_version,
        "tick": instance.tick,
    }
    document["evidence"] = [
        {
            "binding": ref.binding,
            "event_id": str(ref.event_id),
            "source_id": str(ref.source_id),
            "t_evt_ns": str(ref.t_evt_ns),
        }
        for ref in instance.evidence
    ]
    return document


def _licence_document(licence: model.Licence) -> dict[str, object]:
    document: dict[str, object] = {
        "basis": str(licence.basis),
        "license_id": str(licence.license_id),
        "reason": licence.reason,
        "source_id": str(licence.source_id),
        "t0_ns": str(licence.t0_ns),
        "t1_ns": str(licence.t1_ns),
    }
    if licence.witness:
        document["witness"] = [str(w) for w in licence.witness]
    return document


def program_document(program: Program) -> dict[str, object]:
    """The `p_min.json` / `p_max.json` object.

    IDENTIFIER FORMS. The operative specification's data contract writes shortened ids
    (`fa:`, `ri:`, `lc:`); section 57 is normative over it and assigns `fh:`, `in:` and
    `lic:`, and its certificate width rule makes the short forms a hard rejection on sight.
    This artifact carries the section 57 forms. HASH LABELS are `b2b256:`, never `blake3:`,
    because blake2b-256 is what was computed.
    """
    document: dict[str, object] = {
        "axioms": [str(a) for a in program.axioms],
        "counts": {
            "ghost_facts": program.counts.ghost_facts,
            "observed_events": program.counts.observed_events,
            "observed_instances": program.counts.observed_instances,
            "silent_instances": program.counts.silent_instances,
        },
        "facts": [_fact_document(f) for f in program.facts],
        "ghosts": [str(g) for g in program.ghosts],
        "hash_algorithm": canon.HASH_ALGORITHM,
        "instances": [_instance_document(i) for i in program.instances],
        "kind": str(program.kind),
        "licenses": [_licence_document(lc) for lc in program.licences],
        "schema": "spectra.vs.program/1",
    }
    if program.goal is not None:
        document["goal"] = str(program.goal)
    return document


def write_program(program: Program, path: Path) -> str:
    """Write the canonical artifact and return its `b2b256:` content hash."""
    text = scf_dumps(program_document(program))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return canon.hash_ref("program", text.encode("utf-8"))
