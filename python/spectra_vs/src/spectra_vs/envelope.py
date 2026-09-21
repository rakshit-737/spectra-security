"""S9: the silent envelope. `P_max = P_min` plus licensed silent instances and GHOSTs.

WHAT A LICENSED SILENT INSTANCE IS, AND IS NOT. It is a rule instance admitted with NO
evidence, over an interval where every producing source of that rule was non-LIVE, citing
the licence ids that cover the interval. It is a permission for a step nobody could have
seen. It is never an observation, a GHOST is never an event, and no rendering may collapse
OBSERVED and LICENSED into one word.

THE TWO WAYS A SILENT INSTANCE ARISES.

  1. A detect rule with `silent_possible = true`, over a window where every producing
     source is non-LIVE. Its absent body slots are represented by GHOST PREMISE facts, one
     per absent slot, each supported by its own empty-body licensed instance. The premise
     instance carries no blockers, because no control severs "a sensor could not see"; the
     detect instance above it carries the rule's blockers, so a corridor over that route
     still names the control that would sever it. Representing the absent step as a fact
     rather than as an empty body is what keeps the blocker mask enforceable: an instance
     with no body is never fired by unit propagation, so collapsing the two levels would
     silently make the route unblockable.

  2. An OBLIGATION AXIOM whose head is not derived. Its body is the observed trigger, its
     head is a GHOST, and it cites a licence instead of evidence. If the obligation is
     unsatisfied AND unlicensed there is no GHOST: the stage records a
     `permanent_blind_spot` instead, which is the honest admission that the step is
     invisible rather than a pretty inferred node.

HOW TEMPORAL OPERATORS TREAT A LICENSED FACT. A licensed fact's tick is a representative of
a blind window, not an observation, so comparing that single tick against a time bound would
either invent precision or drop a real possibility. The envelope therefore hands the engine
the window itself, and `seq` asks whether SOME placement inside it satisfies the bound (see
`ground.seq_feasible`). That keeps `P_max` a superset of every realizable world while no
longer admitting a combination impossible for every placement.

An earlier version skipped the comparison outright. That admitted an escalation licensed in
the first second of the horizon paired with an export 76 minutes later under a 30-minute
rule, which put a control in the blindness premium at full telemetry for no reason a sensor
could explain.

NOT YET INTERVAL-AWARE: `absence` and `distinct` still skip the comparison for a licensed
fact. That remains sound - it over-approximates - but it is coarser than it needs to be.

P_MAX IS A SUPERSET OF REALIZABLE WORLDS. It unions all licensed silent instances and
ignores mutual-exclusion structure. A counterexample tree drawn from it may combine silent
instances that no single consistent world realizes and may therefore depict an attack that
could not have happened. Everything derived from it carries `PMax`.

BINDING A SILENT INSTANCE. The absent step's entity arguments cannot come from the records,
because there are none. They are drawn from the run's resolved entity universe, restricted
by the kinds the rule declares in `silent_bind_kinds`. Every such combination is admitted,
because the envelope does not know which one occurred and guessing would be the opposite of
the point. The combination count is capped by a deterministic counter.

GROUND TRUTH IS NEVER READ. This module opens no file. `P_min` is recomputed from the same
inputs rather than trusted, so `P_min` is a subset of `P_max` structurally; the containment
is asserted before the result is returned.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Final, Self

from spectra_core import canon, model
from spectra_core.errors import SchemaError
from spectra_core.ids import EventId, FactHash, LicenseId, SourceId
from spectra_vs import ground as ground_mod
from spectra_vs import rules as rules_mod
from spectra_vs.ground import Binding, Engine, Program
from spectra_vs.rules import CompiledRule, RuleTable

__all__ = [
    "MAX_SILENT_BINDINGS",
    "MAX_SILENT_INSTANCES",
    "BlindSpot",
    "EnvelopeResult",
    "LivenessInterval",
    "LivenessView",
    "NonLiveRun",
    "SourceLiveness",
    "blind_spots_document",
    "envelope",
    "write_blind_spots",
]


#: Per (rule, window), the ceiling on entity-argument combinations drawn from the universe.
MAX_SILENT_BINDINGS: Final[int] = 4_096

#: The ceiling on silent instances admitted in one run. A deterministic counter, never a
#: wall clock: a timeout would make the cap flag machine-dependent.
MAX_SILENT_INSTANCES: Final[int] = 100_000


# ---------------------------------------------------------------------------
# The liveness document, as this stage reads it
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LivenessInterval:
    """One elementary or RLE-merged interval of a source's liveness timeline."""

    t0_ns: int
    t1_ns: int
    verdict: model.LivenessVerdict
    reason: str
    witness: tuple[EventId, ...] = ()

    def __post_init__(self) -> None:
        model.Interval(self.t0_ns, self.t1_ns)
        if not isinstance(self.verdict, model.LivenessVerdict):
            raise SchemaError("LivenessInterval.verdict must be a LivenessVerdict")
        if not self.reason:
            raise SchemaError("LivenessInterval.reason is mandatory")

    @property
    def interval(self) -> model.Interval:
        return model.Interval(self.t0_ns, self.t1_ns)

    @property
    def is_live(self) -> bool:
        return self.verdict is model.LivenessVerdict.LIVE


@dataclass(frozen=True, slots=True)
class SourceLiveness:
    """One source's timeline: contiguous intervals ascending by `t0_ns`."""

    source_id: SourceId
    integrity_class: model.IntegrityClass
    intervals: tuple[LivenessInterval, ...]

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(
            self.intervals, lambda iv: iv.t0_ns, where=f"SourceLiveness[{self.source_id}]"
        )


@dataclass(frozen=True, slots=True)
class NonLiveRun:
    """A maximal contiguous run of equal (verdict, reason) that is not LIVE."""

    source_id: SourceId
    t0_ns: int
    t1_ns: int
    verdict: model.LivenessVerdict
    reason: str
    witness: tuple[EventId, ...] = ()

    @property
    def interval(self) -> model.Interval:
        return model.Interval(self.t0_ns, self.t1_ns)

    def licence(self) -> model.Licence:
        """Mint the licence this run implies.

        A BLIND licence carries a reason code and NO witness. A SUPPRESSED one carries the
        bracketing record ids, which is a statement about a sequence discontinuity and not
        a claim that anything was tampered with; this slice implements no backdating pass
        and never claims to detect suppression, tampering or log deletion.
        """
        basis = (
            model.LicenceBasis.SUPPRESSED
            if self.verdict is model.LivenessVerdict.SUPPRESSED
            else model.LicenceBasis.BLIND
        )
        witness = self.witness if basis is model.LicenceBasis.SUPPRESSED else ()
        return model.Licence.mint(
            source_id=self.source_id,
            interval=self.interval,
            basis=basis,
            reason=self.reason,
            witness=tuple(sorted(witness, key=canon.byte_order_key)),
        )


@dataclass(frozen=True, slots=True)
class LivenessView:
    """The read-only view of `liveness.json` that the envelope needs.

    Fail-closed on absence: a source the document does not describe, or an instant no
    interval covers, is NOT licensable. A licence must be IMPLIED by the pinned liveness
    document, because that is exactly what the checker re-derives; manufacturing one over
    an uncovered instant would produce a certificate that cannot be re-checked.
    """

    sources: tuple[SourceLiveness, ...]

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(
            self.sources, lambda s: canon.byte_order_key(str(s.source_id)), where="LivenessView"
        )

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> Self:
        """Parse the `spectra.liveness/2` shape S7 writes."""
        sources: list[SourceLiveness] = []
        for raw in document.get("sources", ()):
            intervals = tuple(
                LivenessInterval(
                    t0_ns=int(entry["t0_ns"]),
                    t1_ns=int(entry["t1_ns"]),
                    verdict=model.LivenessVerdict(str(entry["verdict"])),
                    reason=str(entry["reason"]),
                    witness=tuple(EventId(str(w)) for w in entry.get("witness", ())),
                )
                for entry in raw.get("intervals", ())
            )
            sources.append(
                SourceLiveness(
                    source_id=SourceId(str(raw["source_id"])),
                    integrity_class=model.IntegrityClass(str(raw["integrity_class"])),
                    intervals=tuple(sorted(intervals, key=lambda iv: iv.t0_ns)),
                )
            )
        return cls(
            tuple(sorted(sources, key=lambda s: canon.byte_order_key(str(s.source_id))))
        )

    def timeline(self, source_id: SourceId) -> tuple[LivenessInterval, ...]:
        for entry in self.sources:
            if entry.source_id == source_id:
                return entry.intervals
        return ()

    def live(self, source_id: SourceId, window: model.Interval) -> bool:
        """True iff every instant of `window` is covered by a LIVE interval on this source.

        R11 of the classification ladder is the only construction site of LIVE, and this
        function only reads it. An uncovered instant is not LIVE, which is the fail-closed
        direction for the absence operator.
        """
        if window.is_empty:
            return False
        cursor = window.t0_ns
        for interval in self.timeline(source_id):
            if interval.t1_ns <= cursor:
                continue
            if interval.t0_ns > cursor:
                return False
            if not interval.is_live:
                return False
            cursor = interval.t1_ns
            if cursor >= window.t1_ns:
                return True
        return False

    def runs(self, source_id: SourceId) -> tuple[NonLiveRun, ...]:
        """Maximal non-LIVE runs, merged over contiguous equal (verdict, reason)."""
        merged: list[NonLiveRun] = []
        for interval in self.timeline(source_id):
            if interval.is_live:
                continue
            if (
                merged
                and merged[-1].t1_ns == interval.t0_ns
                and merged[-1].verdict is interval.verdict
                and merged[-1].reason == interval.reason
            ):
                previous = merged[-1]
                merged[-1] = NonLiveRun(
                    source_id=source_id,
                    t0_ns=previous.t0_ns,
                    t1_ns=interval.t1_ns,
                    verdict=previous.verdict,
                    reason=previous.reason,
                    witness=tuple(
                        sorted(set(previous.witness) | set(interval.witness), key=canon.byte_order_key)
                    ),
                )
                continue
            merged.append(
                NonLiveRun(
                    source_id=source_id,
                    t0_ns=interval.t0_ns,
                    t1_ns=interval.t1_ns,
                    verdict=interval.verdict,
                    reason=interval.reason,
                    witness=interval.witness,
                )
            )
        return tuple(merged)

    def covering_runs(
        self, source_id: SourceId, window: model.Interval
    ) -> tuple[NonLiveRun, ...] | None:
        """The non-LIVE runs that jointly cover `window`, or None if any instant is not.

        None rather than a partial list: a licence that covers only part of the interval a
        silent instance rests on is exactly the `license_window_widened` defect, and the
        checker rejects it with E-LICENSE-WINDOW.
        """
        if window.is_empty:
            return None
        found: list[NonLiveRun] = []
        cursor = window.t0_ns
        for run in self.runs(source_id):
            if run.t1_ns <= cursor:
                continue
            if run.t0_ns > cursor:
                return None
            found.append(run)
            cursor = run.t1_ns
            if cursor >= window.t1_ns:
                return tuple(found)
        return None

    def joint_blind_windows(
        self, sources: Sequence[SourceId]
    ) -> tuple[model.Interval, ...]:
        """The maximal windows over which EVERY named source is non-LIVE.

        A rule may be instantiated silently over an interval only where this holds for all
        of its producing sources; one live source over any part of the interval is enough
        to say somebody could have seen it.
        """
        if not sources:
            return ()
        points: set[int] = set()
        for source_id in sources:
            for interval in self.timeline(source_id):
                points.add(interval.t0_ns)
                points.add(interval.t1_ns)
        ordered = sorted(points)
        kept: list[model.Interval] = []
        for low, high in zip(ordered, ordered[1:], strict=False):
            elementary = model.Interval(low, high)
            if elementary.is_empty:
                continue
            if all(
                self.covering_runs(source_id, elementary) is not None
                for source_id in sources
            ):
                if kept and kept[-1].t1_ns == low:
                    kept[-1] = model.Interval(kept[-1].t0_ns, high)
                else:
                    kept.append(elementary)
        return tuple(kept)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BlindSpot:
    """An obligation that is unsatisfied AND unlicensed. No GHOST is created for it."""

    rule_id: str
    head_predicate: str
    t0_ns: int
    t1_ns: int
    producing_sources: tuple[SourceId, ...]
    reason: str

    def sort_key(self) -> tuple[str, str, int, int]:
        return (self.rule_id, self.head_predicate, self.t0_ns, self.t1_ns)


@dataclass(frozen=True, slots=True)
class EnvelopeResult:
    """Both sides of the bracket, the licences, and the blind spots.

    The two programs are separate objects. Nothing mutates `P_min` in place, and the
    containment `P_min` subset of `P_max` is asserted rather than assumed.
    """

    p_min: Program
    p_max: Program
    licences: tuple[model.Licence, ...]
    blind_spots: tuple[BlindSpot, ...]
    capped: bool = False
    cap_detail: str = ""


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------


def _fresh_engine(
    table: RuleTable,
    events: Sequence[model.CanonicalEvent],
    bindings: Sequence[Binding],
    absence_availability: ground_mod.AbsenceAvailability | None,
) -> Engine:
    engine = Engine(table, events, bindings, absence_availability=absence_availability)
    engine.seed()
    engine.saturate()
    return engine


def _entities_by_kind(
    entities: Iterable[model.Entity],
) -> dict[str, tuple[model.Entity, ...]]:
    buckets: dict[str, list[model.Entity]] = {}
    for entity in entities:
        buckets.setdefault(entity.kind, []).append(entity)
    return {
        kind: tuple(sorted(items, key=lambda e: canon.byte_order_key(str(e.entity_id))))
        for kind, items in buckets.items()
    }


def _silent_bindings(
    compiled: CompiledRule, by_kind: dict[str, tuple[model.Entity, ...]]
) -> tuple[dict[str, model.Entity], ...]:
    """Every entity-argument combination the rule declares as drawable, in a fixed order.

    Every combination is admitted rather than one: the envelope does not know which
    principal or which role the unobserved step involved, and choosing one would be a guess
    dressed as a derivation.
    """
    names = [name for name, _ in compiled.silent_bind_kinds]
    pools = [by_kind.get(kind, ()) for _, kind in compiled.silent_bind_kinds]
    if any(not pool for pool in pools):
        return ()
    combinations: list[dict[str, model.Entity]] = []
    for chosen in product(*pools):
        combinations.append(dict(zip(names, chosen, strict=True)))
        if len(combinations) >= MAX_SILENT_BINDINGS:
            break
    return tuple(combinations)


def _licences_for_window(
    view: LivenessView, sources: Sequence[SourceId], window: model.Interval
) -> tuple[model.Licence, ...] | None:
    """Every licence covering `window` on every one of `sources`, or None if any is live."""
    found: list[model.Licence] = []
    for source_id in sorted(sources, key=lambda s: canon.byte_order_key(str(s))):
        runs = view.covering_runs(source_id, window)
        if runs is None:
            return None
        found.extend(run.licence() for run in runs)
    unique = {str(lc.license_id): lc for lc in found}
    return tuple(sorted(unique.values(), key=lambda lc: lc.sort_key()))


def _licence_ids(licences: Sequence[model.Licence]) -> tuple[LicenseId, ...]:
    return tuple(
        sorted({lc.license_id for lc in licences}, key=canon.byte_order_key)
    )


def _add_silent_detect(
    engine: Engine,
    view: LivenessView,
    compiled: CompiledRule,
    by_kind: dict[str, tuple[model.Entity, ...]],
    minted: dict[str, model.Licence],
    counter: list[int],
) -> None:
    """Admit the licensed silent instances of one `silent_possible` detect rule."""
    sources = compiled.rule.producing_sources
    for window in view.joint_blind_windows(sources):
        licences = _licences_for_window(view, sources, window)
        if licences is None:
            continue
        for licence in licences:
            minted.setdefault(str(licence.license_id), licence)
        licence_ids = _licence_ids(licences)
        # The representative instant of the unobserved step. The envelope does not
        # enumerate every tick of the window: the tick of a licensed fact stands for the
        # interval, the temporal operators are not evaluated against it, and enumerating
        # would multiply the fact base without adding a corridor.
        tick = window.t0_ns // rules_mod.TICK_NS
        # The closed tick range the unobserved step could have occupied. The window is
        # half-open, so its last tick is (t1 - 1). Handed to the engine so a temporal
        # operator can test whether SOME placement satisfies it, instead of skipping the
        # test and admitting placements that are impossible anywhere in the window.
        span = (tick, max(tick, (window.t1_ns - 1) // rules_mod.TICK_NS))
        for bound in _silent_bindings(compiled, by_kind):
            if counter[0] >= MAX_SILENT_INSTANCES:
                engine.record_cap(f"MAX_SILENT_INSTANCES={MAX_SILENT_INSTANCES} reached")
                return
            body_keys: list[FactHash] = []
            premises: list[tuple[model.RuleInstance, model.Fact]] = []
            usable = True
            for pattern in compiled.body:
                args = []
                for name in pattern.entity_vars:
                    entity = bound.get(name)
                    if entity is None:
                        usable = False
                        break
                    args.append(entity.entity_id)
                if not usable:
                    break
                premise_fact = model.Fact.mint(pattern.predicate, tuple(args), tick)
                body_keys.append(premise_fact.fact_key)
                if not engine.has_fact(premise_fact.fact_key):
                    premise = model.RuleInstance.mint(
                        rule_id=compiled.rule.rule_id,
                        rule_version=compiled.rule.rule_version,
                        head=premise_fact.fact_key,
                        body=(),
                        blockers=(),
                        observed=model.Observation.LICENSED,
                        tick=tick,
                        license_ids=licence_ids,
                        ghost=True,
                    )
                    premises.append((premise, premise_fact))
            if not usable:
                continue
            head_args = []
            for name in compiled.head.entity_vars:
                entity = bound.get(name)
                if entity is None:
                    usable = False
                    break
                head_args.append(entity.entity_id)
            if not usable:
                continue
            head_fact = model.Fact.mint(compiled.head.predicate, tuple(head_args), tick)
            instance = model.RuleInstance.mint(
                rule_id=compiled.rule.rule_id,
                rule_version=compiled.rule.rule_version,
                head=head_fact.fact_key,
                body=tuple(body_keys),
                blockers=compiled.blockers,
                observed=model.Observation.LICENSED,
                tick=tick,
                license_ids=licence_ids,
                ghost=False,
            )
            for premise, premise_fact in premises:
                if engine.add_instance(premise, premise_fact, span):
                    counter[0] += 1
            if engine.add_instance(instance, head_fact, span):
                counter[0] += 1


def _add_obligations(
    engine: Engine,
    view: LivenessView,
    table: RuleTable,
    minted: dict[str, model.Licence],
    counter: list[int],
) -> tuple[BlindSpot, ...]:
    """Force a silent instance and a GHOST head for every unsatisfied, licensed obligation.

    An unsatisfied obligation that is NOT licensed produces no GHOST. It produces a
    `permanent_blind_spot`, because inventing an inferred node over a window where somebody
    could have seen the step would be a claim the telemetry does not support.
    """
    spots: list[BlindSpot] = []
    for compiled in table.obligation_rules:
        temporal = compiled.temporal
        if temporal is None or temporal.op != "obligation":
            raise SchemaError(
                f"{compiled.rule_id}: an obligation rule needs an `obligation` temporal "
                "clause naming the trigger slot and the window it obliges"
            )
        pattern = compiled.body[0]
        for trigger in engine.facts_for(pattern.predicate, pattern.arity):
            bound = dict(zip(pattern.entity_vars, trigger.args, strict=True))
            head_args = []
            usable = True
            for name in compiled.head.entity_vars:
                value = bound.get(name)
                if value is None:
                    usable = False
                    break
                head_args.append(value)
            if not usable:
                continue
            head_fact = model.Fact.mint(
                compiled.head.predicate, tuple(head_args), trigger.tick
            )
            if engine.has_fact(head_fact.fact_key):
                continue  # the obligation is satisfied; nothing to licence
            low = max(0, trigger.tick - temporal.within_ticks)
            window = model.Interval(low * rules_mod.TICK_NS, trigger.tick * rules_mod.TICK_NS)
            licences = _licences_for_window(view, compiled.rule.producing_sources, window)
            if licences is None:
                spots.append(
                    BlindSpot(
                        rule_id=str(compiled.rule_id),
                        head_predicate=compiled.head.predicate,
                        t0_ns=window.t0_ns,
                        t1_ns=window.t1_ns,
                        producing_sources=compiled.rule.producing_sources,
                        reason="obligation_unsatisfied_and_unlicensed",
                    )
                )
                continue
            for licence in licences:
                minted.setdefault(str(licence.license_id), licence)
            if counter[0] >= MAX_SILENT_INSTANCES:
                engine.record_cap(f"MAX_SILENT_INSTANCES={MAX_SILENT_INSTANCES} reached")
                break
            instance = model.RuleInstance.mint(
                rule_id=compiled.rule.rule_id,
                rule_version=compiled.rule.rule_version,
                head=head_fact.fact_key,
                body=(trigger.fact_key,),
                blockers=compiled.blockers,
                observed=model.Observation.LICENSED,
                tick=trigger.tick,
                license_ids=_licence_ids(licences),
                ghost=True,
            )
            if engine.add_instance(instance, head_fact):
                counter[0] += 1
    spots.sort(key=lambda s: s.sort_key())
    return tuple(spots)


def envelope(
    table: RuleTable,
    events: Sequence[model.CanonicalEvent],
    bindings: Sequence[Binding],
    view: LivenessView,
    entities: Sequence[model.Entity],
    *,
    goal: FactHash | None = None,
    absence_availability: ground_mod.AbsenceAvailability | None = None,
    p_min: Program | None = None,
) -> EnvelopeResult:
    """Build `P_max` beside `P_min` and return both, with the licences and blind spots.

    `P_min` is recomputed here from the same inputs rather than read back, so the
    containment is a property of the construction: the same engine is saturated, and only
    then are licensed instances added. A caller that already has `P_min` passes it and the
    containment is checked against that object too.
    """
    lower_engine = _fresh_engine(table, events, bindings, absence_availability)
    lower = lower_engine.snapshot(model.ProgramKind.P_MIN, goal=goal)

    engine = _fresh_engine(table, events, bindings, absence_availability)
    by_kind = _entities_by_kind(entities)
    minted: dict[str, model.Licence] = {}
    counter = [0]

    for compiled in table.detect_rules:
        if compiled.rule.silent_possible:
            _add_silent_detect(engine, view, compiled, by_kind, minted, counter)
    engine.saturate()

    spots = _add_obligations(engine, view, table, minted, counter)
    engine.saturate()
    engine.assert_ghost_support()

    licences = tuple(sorted(minted.values(), key=lambda lc: lc.sort_key()))
    upper = engine.snapshot(model.ProgramKind.P_MAX, goal=goal, licences=licences)

    _assert_contains(lower, upper)
    if p_min is not None:
        _assert_contains(p_min, upper)

    return EnvelopeResult(
        p_min=lower,
        p_max=upper,
        licences=licences,
        blind_spots=spots,
        capped=engine.capped or lower_engine.capped,
        cap_detail=engine.cap_detail or lower_engine.cap_detail,
    )


def _assert_contains(lower: Program, upper: Program) -> None:
    """`P_min` is a subset of `P_max` in both facts and instances, always."""
    upper_facts = {str(f.fact_key) for f in upper.facts}
    upper_instances = {str(i.instance_id) for i in upper.instances}
    missing_facts = sorted(
        str(f.fact_key) for f in lower.facts if str(f.fact_key) not in upper_facts
    )
    missing_instances = sorted(
        str(i.instance_id)
        for i in lower.instances
        if str(i.instance_id) not in upper_instances
    )
    if missing_facts or missing_instances:
        raise SchemaError(
            "PMin is not contained in PMax; missing facts "
            f"{missing_facts[:4]} and instances {missing_instances[:4]}"
        )


# ---------------------------------------------------------------------------
# The blind-spot artifact
# ---------------------------------------------------------------------------


def blind_spots_document(spots: Sequence[BlindSpot]) -> dict[str, object]:
    """The `blind_spots.json` object: the steps that are invisible and carry no GHOST."""
    return {
        "schema": "spectra.vs.blind_spots/1",
        "permanent_blind_spots": [
            {
                "head_predicate": spot.head_predicate,
                "producing_sources": [str(s) for s in spot.producing_sources],
                "reason": spot.reason,
                "rule_id": spot.rule_id,
                "t0_ns": str(spot.t0_ns),
                "t1_ns": str(spot.t1_ns),
            }
            for spot in spots
        ],
    }


def write_blind_spots(spots: Sequence[BlindSpot], path: Path) -> str:
    """Write the canonical artifact and return its `b2b256:` content hash."""
    text = ground_mod.scf_dumps(blind_spots_document(spots))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return canon.hash_ref("blind_spots", text.encode("utf-8"))
