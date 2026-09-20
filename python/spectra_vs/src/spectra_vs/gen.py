"""S2: the seeded generator. `scenario + seed -> raw.jsonl + truth.jsonl`.

This is the stage that replaces the container cyber range, which cannot be built on this
machine. Nothing here is a measurement and nothing here happened: the output is a
simulation, and every manifest derived from it says so through
`bundle_provenance: "synthetic_generator_no_range"`.

TWO STREAMS, NEVER ONE FILE. `raw.jsonl` is telemetry. `truth.jsonl` is what the
generator knows, and no stage from ingest onwards may read it. Keeping them in separate
files rather than in one file with a label member is not tidiness: a truth key on a
telemetry record is the label leak that ingest rejects outright, and the whole design
exists to make a stage that peeks at the answer a structural impossibility rather than a
code-review finding.

THE UNOBSERVABLE STEP IS REPRESENTABLE. A step with `observable: false` produces no raw
record and exactly one annotation of kind `attack_unobserved`, carrying no `event_id` and
no producing sources. That annotation is the only record anywhere that such a step
occurred, and the licence mechanism downstream is what has to account for it. If this
stream could not represent it, the blindness premium would have nothing to be a premium
over.

DETERMINISM IS BY KEYING, NOT BY SEQUENCE. Every pseudo-random value is drawn from a
digest over (seed, a domain string, the identity of the thing being drawn for). No
draw depends on how many draws came before it, so permuting the generator's loops, or
adding a family, cannot shift another family's values. The alternative - a sequential
stream - is deterministic only as long as nobody reorders a loop, and that is exactly the
kind of invariant that is violated silently.

NO WALL CLOCK, NO AMBIENT RANDOMNESS, NO FLOAT. The emission schedule is integer
Bresenham over the rational benign rate; the sub-tick offset is an integer draw below the
tick granularity; there is no `random` module import and no `time` import in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Final

from spectra_core import canon
from spectra_core.errors import DeterminismError, SchemaError
from spectra_core.ids import EventId, SourceId, Tick
from spectra_core.model import Canonical, Nanos, TruthKind, TruthOrigin, check_nanos
from spectra_core.model import GroundTruth

from spectra_vs.scenario import AttackStep, ScenarioSpec, source_key
from spectra_vs.scf import render_jsonl, write_jsonl

__all__ = [
    "RAW_FILE_KIND",
    "TRUTH_FILE_KIND",
    "GenResult",
    "RawEvent",
    "draw_below",
    "draw_u64",
    "gen",
    "pick",
    "raw_to_scf",
    "render_raw",
    "render_truth",
    "truth_to_scf",
    "write_raw",
    "write_truth",
]

#: Digest domains for the two file-level hashes. Distinct so that a raw file and a truth
#: file of identical octets could not produce the same reference.
RAW_FILE_KIND: Final[str] = "vsraw"
TRUTH_FILE_KIND: Final[str] = "vstruth"

_DRAW_KIND: Final[str] = "vsdraw"

#: Rejection-sampling bound. A u64 draw is uniform over 2**64 values; `draw_below` rejects
#: the short tail so the result is exactly uniform rather than nearly uniform. Bounded so
#: that a pathological modulus cannot loop without end.
_DRAW_ATTEMPTS: Final[int] = 64


# ---------------------------------------------------------------------------
# Keyed pseudo-random draws
# ---------------------------------------------------------------------------


def draw_u64(seed: int, domain: str, *parts: str | int) -> int:
    """A u64 drawn from (seed, domain, parts). A pure function, and the only draw here.

    `domain` separates one kind of draw from another so that the jitter for a record and
    the principal chosen for the same record cannot be the same value. `parts` names the
    thing being drawn for, which is what makes the draw independent of call order.
    """
    canon.u64(seed)
    payload = [canon.u64(seed), canon.ascii_text(domain)]
    for part in parts:
        if isinstance(part, bool):
            raise SchemaError("draw_u64: a bool is not a draw key part")
        if isinstance(part, int):
            payload.append(canon.i64(part))
        elif isinstance(part, str):
            payload.append(canon.utf8_text(part))
        else:
            raise SchemaError(f"draw_u64: key parts are str or int, got {type(part).__name__}")
    return int.from_bytes(canon.digest(_DRAW_KIND + "/" + domain, b"".join(payload))[:8], "big")


def draw_below(bound: int, seed: int, domain: str, *parts: str | int) -> int:
    """A uniform integer in `[0, bound)`, by rejection sampling rather than by modulo.

    Modulo of a u64 by a small bound is biased by less than 2**-50 here, which would be
    harmless. Rejection is used anyway because "harmless bias" is a claim that has to be
    re-argued every time the bound changes, and exactness does not.
    """
    if isinstance(bound, bool) or not isinstance(bound, int) or bound <= 0:
        raise SchemaError(f"draw_below: bound must be a positive int, got {bound!r}")
    limit = (1 << 64) - ((1 << 64) % bound)
    for attempt in range(_DRAW_ATTEMPTS):
        value = draw_u64(seed, domain, *parts, attempt)
        if value < limit:
            return value % bound
    raise DeterminismError(
        f"draw_below: rejection sampling did not terminate in {_DRAW_ATTEMPTS} attempts"
    )


def pick[T](choices: tuple[T, ...], seed: int, domain: str, *parts: str | int) -> T:
    """Choose one element of a declared, already-ordered tuple. Never from a set or a dict."""
    if not choices:
        raise SchemaError(f"pick: nothing to choose from in domain {domain!r}")
    return choices[draw_below(len(choices), seed, domain, *parts)]


# ---------------------------------------------------------------------------
# The raw record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawEvent(Canonical):
    """One pre-ingest telemetry line: exactly the five members of data contract 2.

    This is NOT `spectra_core.model.CanonicalEvent`. A canonical event carries a
    `record_id`, an ingestion time and a chain seal, and the generator knows none of the
    three: they are assigned by S4 when the line is read. What the generator does know is
    the event-id preimage, because contract 4 mints `event_id` from exactly these five
    members - so the id computed here is the id ingest will compute, and the truth stream
    can cite it without ever touching the telemetry path.

    `ID_KIND` is `"ev"` for that reason: the domain separator must match
    `CanonicalEvent`'s or the two would mint different ids for the same occurrence. The
    test suite pins that equality so the two cannot drift apart unnoticed.
    """

    ID_KIND: ClassVar[str] = "ev"

    source_id: SourceId
    seq: int
    t_evt_ns: Nanos
    event_type: str
    attrs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        canon.u32(self.seq)
        check_nanos(self.t_evt_ns, where="RawEvent.t_evt_ns")
        canon.check_strictly_ascending(
            [k for k, _ in self.attrs], canon.byte_order_key, where="RawEvent.attrs"
        )

    def identity_bytes(self) -> bytes:
        """The event-id preimage, in the same field order as `CanonicalEvent.identity_bytes`."""
        return b"".join(
            (
                canon.pairs(self.attrs),
                canon.utf8_text(self.event_type),
                canon.u32(self.seq),
                canon.ascii_text(self.source_id),
                canon.i64(self.t_evt_ns),
            )
        )

    def canonical_bytes(self) -> bytes:
        return self.identity_bytes()

    @property
    def event_id(self) -> EventId:
        return EventId.mint(self.identity_bytes())

    def sort_key(self) -> tuple[int, str, int]:
        """The raw file order: ascending t_evt_ns, source_id, seq."""
        return (self.t_evt_ns, source_key(self.source_id), self.seq)


def raw_to_scf(event: RawEvent) -> dict[str, Any]:
    """Data contract 2 on the wire. `t_evt_ns` is decimal text because it is an i64."""
    return {
        "attrs": {key: value for key, value in event.attrs},
        "event_type": event.event_type,
        "seq": event.seq,
        "source_id": source_key(event.source_id),
        "t_evt_ns": str(event.t_evt_ns),
    }


def truth_to_scf(truth: GroundTruth) -> dict[str, Any]:
    """Data contract 3 on the wire. Absent members are omitted, never written as null."""
    document: dict[str, Any] = {
        "actor_ref": truth.actor_ref,
        "kind": str(truth.kind),
        "observable": truth.observable,
        "origin": str(truth.origin),
        "producing_sources": [source_key(s) for s in truth.producing_sources],
        "sim_tick": truth.sim_tick,
        "truth_id": truth.truth_id,
    }
    if truth.event_id is not None:
        document["event_id"] = str(truth.event_id)
    if truth.chain_id is not None:
        document["chain_id"] = truth.chain_id
    if truth.step_k is not None:
        document["step_k"] = truth.step_k
    if truth.step_action is not None:
        document["step_action"] = truth.step_action
    if truth.subject_ref is not None:
        document["subject_ref"] = truth.subject_ref
    if truth.true_transition:
        document["true_transition"] = {key: value for key, value in truth.true_transition}
    if truth.suppressed_by is not None:
        document["suppressed_by"] = truth.suppressed_by
    return document


# ---------------------------------------------------------------------------
# The result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenResult:
    """What one seeded generation produced. Two streams that never meet."""

    scenario_hash: str
    seed: int
    raw: tuple[RawEvent, ...]
    truth: tuple[GroundTruth, ...]

    @property
    def raw_bytes(self) -> bytes:
        return render_raw(self.raw)

    @property
    def raw_hash(self) -> str:
        return canon.hash_ref(RAW_FILE_KIND, self.raw_bytes)

    @property
    def truth_bytes(self) -> bytes:
        return render_truth(self.truth)

    @property
    def truth_hash(self) -> str:
        return canon.hash_ref(TRUTH_FILE_KIND, self.truth_bytes)

    def records_of(self, source_id: str) -> tuple[RawEvent, ...]:
        return tuple(r for r in self.raw if source_key(r.source_id) == source_key(source_id))

    def unobserved_steps(self) -> tuple[GroundTruth, ...]:
        """The annotations for steps no declared sensor could have recorded."""
        return tuple(t for t in self.truth if t.kind is TruthKind.ATTACK_UNOBSERVED)


def render_raw(raw: tuple[RawEvent, ...]) -> bytes:
    return render_jsonl([raw_to_scf(r) for r in raw], where="raw")


def render_truth(truth: tuple[GroundTruth, ...]) -> bytes:
    return render_jsonl([truth_to_scf(t) for t in truth], where="truth")


def write_raw(path: Path, raw: tuple[RawEvent, ...]) -> bytes:
    return write_jsonl(path, [raw_to_scf(r) for r in raw], where="raw")


def write_truth(path: Path, truth: tuple[GroundTruth, ...]) -> bytes:
    return write_jsonl(path, [truth_to_scf(t) for t in truth], where="truth")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Occurrence:
    """An emission before sequence numbers exist. Ordered by content, never by discovery."""

    t_evt_ns: Nanos
    source_id: SourceId
    event_type: str
    attrs: tuple[tuple[str, str], ...]
    actor_ref: str
    subject_ref: str | None
    step: AttackStep | None

    def order_key(self) -> tuple[int, bytes, bytes, bytes]:
        return (
            self.t_evt_ns,
            canon.byte_order_key(source_key(self.source_id)),
            canon.byte_order_key(self.event_type),
            canon.pairs(self.attrs),
        )


def gen(scenario: ScenarioSpec, seed: int) -> GenResult:
    """Produce the raw stream and the ground-truth stream for one seed.

    Pure: the same scenario and the same seed give byte-identical output, in this process
    and in any other. The scenario is the generator's whole configuration, which is why
    `ScenarioSpec.generator_config_hash` is the scenario hash and why gate B4 can compare
    them.

    ORDER OF WORK. Emissions are collected, then totally ordered by content, then given
    dense per-source sequence numbers, then rendered. Sequence numbers are assigned last
    because contract 2 requires them dense and ascending per source BEFORE degradation,
    and assigning them during collection would make them depend on collection order.
    """
    canon.u64(seed)
    occurrences: list[_Occurrence] = []
    occurrences.extend(_benign_occurrences(scenario, seed))
    occurrences.extend(_attack_occurrences(scenario))

    ordered = sorted(occurrences, key=lambda o: o.order_key())
    canon.check_strictly_ascending(
        [o.order_key() for o in ordered], lambda k: k, where="gen.occurrences"
    )

    next_seq: dict[str, int] = {}
    numbered: list[tuple[RawEvent, _Occurrence]] = []
    for occurrence in ordered:
        key = source_key(occurrence.source_id)
        seq = next_seq.get(key, 0)
        next_seq[key] = seq + 1
        numbered.append(
            (
                RawEvent(
                    source_id=occurrence.source_id,
                    seq=seq,
                    t_evt_ns=occurrence.t_evt_ns,
                    event_type=occurrence.event_type,
                    attrs=occurrence.attrs,
                ),
                occurrence,
            )
        )

    raw = tuple(sorted((event for event, _ in numbered), key=lambda e: e.sort_key()))
    canon.check_strictly_ascending([e.sort_key() for e in raw], lambda k: k, where="gen.raw")

    seen: set[str] = set()
    for event in raw:
        event_id = str(event.event_id)
        if event_id in seen:
            raise DeterminismError(f"gen: two occurrences minted the same event id {event_id}")
        seen.add(event_id)

    truth = _truth_stream(scenario, numbered)
    return GenResult(scenario_hash=scenario.scenario_hash(), seed=seed, raw=raw, truth=truth)


def _benign_occurrences(scenario: ScenarioSpec, seed: int) -> list[_Occurrence]:
    """The background population, one schedule per declared noise family.

    Emission times come from integer Bresenham over the rational rate rather than from a
    modulo test, so a rate whose denominator does not divide the horizon still emits the
    exact declared count and no tick is silently skipped. The sub-tick offset is a draw,
    which is what stops every gap from being identical and the calibration profile from
    being degenerate.
    """
    num = scenario.noise.benign_rate_num
    den = scenario.noise.benign_rate_den
    granularity = scenario.tick_granularity_ns
    entities = scenario.entities
    occurrences: list[_Occurrence] = []

    for family in scenario.noise.families:
        source = scenario.source_of_event_type(family)
        emitted = 0
        for tick in range(scenario.horizon_ticks):
            target = ((tick + 1) * num) // den
            for index in range(target - emitted):
                offset = draw_below(granularity, seed, "jitter", family, tick, index)
                t_evt_ns = scenario.epoch_ns + tick * granularity + offset
                if scenario.is_declared_blind(source.source_id, t_evt_ns):
                    continue
                principal = pick(entities.principal_ids, seed, "principal", family, tick, index)
                attrs: list[tuple[str, str]] = [("principal", principal)]
                credentials = entities.credentials_of(principal)
                if credentials:
                    attrs.append(
                        ("credential", pick(credentials, seed, "credential", family, tick, index))
                    )
                attrs.append(
                    ("resource", pick(entities.resource_ids, seed, "resource", family, tick, index))
                )
                attrs.append(
                    ("service", pick(entities.service_ids, seed, "service", family, tick, index))
                )
                occurrences.append(
                    _Occurrence(
                        t_evt_ns=t_evt_ns,
                        source_id=source.source_id,
                        event_type=family,
                        attrs=tuple(sorted(attrs, key=lambda kv: canon.byte_order_key(kv[0]))),
                        actor_ref=principal,
                        subject_ref=None,
                        step=None,
                    )
                )
            emitted = target
    return occurrences


def _attack_occurrences(scenario: ScenarioSpec) -> list[_Occurrence]:
    """One emission per (observable step, emitting source). Unobservable steps emit nothing.

    A declared blind window suppresses an attack emission exactly as it suppresses a
    benign one. The generator does not make an exception for the chain: a sensor that is
    declared blind cannot see an attack step either, and an exception here would be the
    generator quietly guaranteeing the attack is visible.
    """
    occurrences: list[_Occurrence] = []
    for step in scenario.attack.steps:
        if not step.observable:
            continue
        t_evt_ns = scenario.epoch_ns + step.t_offset_ns
        for source_id in step.emits:
            if scenario.is_declared_blind(source_id, t_evt_ns):
                continue
            assert step.event_type is not None
            occurrences.append(
                _Occurrence(
                    t_evt_ns=t_evt_ns,
                    source_id=source_id,
                    event_type=step.event_type,
                    attrs=step.attrs,
                    actor_ref=step.actor,
                    subject_ref=dict(step.attrs).get("resource"),
                    step=step,
                )
            )
    return occurrences


def _truth_stream(
    scenario: ScenarioSpec, numbered: list[tuple[RawEvent, _Occurrence]]
) -> tuple[GroundTruth, ...]:
    """One annotation per emitted record, plus one per step nobody could have seen.

    `observable` on an annotation records whether the STEP was observable at all, not
    whether the record survived. A step that no declared sensor could record is the case
    the licence mechanism has to account for, so it must be representable here even though
    it has no event to point at.
    """
    annotations: list[GroundTruth] = []

    for event, occurrence in numbered:
        step = occurrence.step
        sim_tick = _sim_tick(scenario, event.t_evt_ns)
        if step is None:
            annotations.append(
                _mint_truth(
                    kind=TruthKind.BENIGN,
                    origin=TruthOrigin.POPULATION,
                    sim_tick=sim_tick,
                    actor_ref=occurrence.actor_ref,
                    observable=True,
                    producing_sources=(event.source_id,),
                    event_id=event.event_id,
                )
            )
            continue
        annotations.append(
            _mint_truth(
                kind=TruthKind.ATTACK_STEP,
                origin=TruthOrigin.SCENARIO,
                sim_tick=sim_tick,
                actor_ref=step.actor,
                observable=True,
                producing_sources=(event.source_id,),
                event_id=event.event_id,
                chain_id=scenario.attack.chain_id,
                step_k=step.k,
                step_action=step.action,
                subject_ref=occurrence.subject_ref,
                true_transition=step.expect_transition,
            )
        )

    for step in scenario.attack.steps:
        if step.observable:
            continue
        annotations.append(
            _mint_truth(
                kind=TruthKind.ATTACK_UNOBSERVED,
                origin=TruthOrigin.SCENARIO,
                sim_tick=_sim_tick(scenario, scenario.epoch_ns + step.t_offset_ns),
                actor_ref=step.actor,
                observable=False,
                producing_sources=(),
                event_id=None,
                chain_id=scenario.attack.chain_id,
                step_k=step.k,
                step_action=step.action,
                subject_ref=dict(step.attrs).get("credential"),
                true_transition=step.expect_transition,
            )
        )

    ordered = tuple(canon.sorted_by_bytes(annotations, key=lambda t: t.truth_id))
    canon.check_strictly_ascending(
        [t.truth_id for t in ordered], canon.byte_order_key, where="gen.truth"
    )
    return ordered


def _sim_tick(scenario: ScenarioSpec, t_evt_ns: Nanos) -> Tick:
    """Ticks since the scenario epoch, not since the Unix epoch.

    Ticks since the Unix epoch would be a u32 that runs out in 2106 and would make the
    annotation stream depend on a calendar. Ticks since the scenario epoch are bounded by
    the declared horizon and mean what the member name says.
    """
    return Tick((t_evt_ns - scenario.epoch_ns) // scenario.tick_granularity_ns)


def _mint_truth(
    *,
    kind: TruthKind,
    origin: TruthOrigin,
    sim_tick: Tick,
    actor_ref: str,
    observable: bool,
    producing_sources: tuple[SourceId, ...],
    event_id: EventId | None,
    chain_id: str | None = None,
    step_k: int | None = None,
    step_action: str | None = None,
    subject_ref: str | None = None,
    true_transition: tuple[tuple[str, str], ...] = (),
) -> GroundTruth:
    """Mint one annotation, with the id taken over the members that identify it.

    The id preimage deliberately excludes `actor_ref`, `subject_ref` and the transition:
    two annotations that agree on kind, origin, event, tick and step index are the same
    annotation, and letting a descriptive member into the preimage would make the id
    change when prose changes.
    """
    payload = canon.pairs(
        (
            ("chain_id", chain_id or ""),
            ("event_id", str(event_id) if event_id is not None else ""),
            ("kind", str(kind)),
            ("origin", str(origin)),
            ("sim_tick", str(int(sim_tick))),
            ("step_k", str(step_k) if step_k is not None else ""),
        )
    )
    return GroundTruth(
        truth_id=GroundTruth.mint_truth_id(payload),
        sim_tick=sim_tick,
        kind=kind,
        origin=origin,
        actor_ref=actor_ref,
        observable=observable,
        producing_sources=producing_sources,
        event_id=event_id,
        chain_id=chain_id,
        step_k=step_k,
        step_action=step_action,
        subject_ref=subject_ref,
        true_transition=true_transition,
    )
