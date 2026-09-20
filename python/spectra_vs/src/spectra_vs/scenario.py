"""S2 input: the ScenarioSpec loader, validator and hasher.

The scenario is the only place the slice's world is declared, and every stage downstream
derives from its hash rather than from its text. That is why the loader validates
aggressively and refuses to normalise: a scenario that is almost well-formed would
produce a run whose artifacts hash differently from the one the author believed they
described, and the mismatch would surface only as an unverifiable certificate.

TOML RATHER THAN YAML. The operative specification names `config/vs/scenario.yaml`. There
is no YAML parser in the standard library and no package may be installed, so the fixture
is authored as TOML and read with `tomllib`. The member names, the member types and the
loader constraints are the specification's verbatim; only the surface syntax differs. The
wire contract this file parses into is unchanged, so nothing downstream can tell.

SOURCE TYPES ARE NOT REDEFINED HERE. `spectra_core.model.Source` already is the slice's
source declaration and `spectra_core.model.Interval` already is its half-open interval.
This module parses into those, and defines its own types only for the members the
foundation has no type for: phases, the attack chain, the noise population, the entity
tables and the goal.

`scenario_id` IS NOT AN `ids.ScenarioId`. The operative contract spells it
`^vs-[0-9]{2}-[a-z0-9-]+$`; section 57.2's `ScenarioId` is `sc:<snake>@<u16>` and forbids
the hyphen. The contract's spelling is what every artifact carries, so it is validated by
the contract's own grammar and typed as `str`, and no silent transliteration happens here.

NOISE FAMILIES ARE EVENT TYPES. The contract declares `noise.families` as a list of
strings and declares no binding from a family to a source. Rather than invent a member to
carry that binding, the loader requires each family name to be an event type that exactly
one declared source emits, which is a binding the contract already expresses through
`SourceDecl.emits_event_types`. The consequence is stated in `Noise`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import SchemaError
from spectra_core.ids import SourceId
from spectra_core.model import IntegrityClass, Interval, Nanos, Source, check_nanos

from spectra_vs.scf import scf_dumps

__all__ = [
    "SCENARIO_SCHEMA",
    "AttackChain",
    "AttackStep",
    "BlindnessDecl",
    "Entities",
    "ExcludedInterval",
    "Goal",
    "Noise",
    "Phase",
    "ScenarioSpec",
    "load_scenario",
    "parse_scenario",
    "scenario_summary",
    "source_key",
]


def source_key(value: str | SourceId) -> str:
    """The bare source name, with `ids.SourceId`'s `"src:"` prefix removed if present.

    Two spellings of a source exist and both are correct. Section 57.2 gives
    `SourceId` the `src:` prefix, and `spectra_core.model.Source` is typed with it. The
    operative data contracts spell `source_id` bare on every wire - raw records, bundle
    records, the degradation manifest - and ingest is written against that spelling.
    Rather than pick one and break the other, every lookup and every serialisation in the
    slice goes through this function, so a caller holding either form finds the same
    source and writes the same octets.
    """
    text = str(value)
    prefix = SourceId.PREFIX
    return text[len(prefix) :] if text.startswith(prefix) else text

#: The schema tag every scenario document must carry, so that a future shape change is a
#: load-time rejection rather than a field that quietly reads as absent.
SCENARIO_SCHEMA: Final[str] = "spectra.vs.scenario/1"

#: The operative contract's scenario-id grammar. Hyphenated, unlike section 57.2 ids.
_SCENARIO_ID: Final = re.compile(r"\A vs-[0-9]{2}-[a-z0-9-]+ \Z", re.VERBOSE)

_SNAKE_NAME: Final = re.compile(r"\A[a-z][a-z0-9_]{0,47}\Z")
_ENTITY_REF: Final = re.compile(r"\A[a-z][a-z0-9_]{0,47}\Z")
_CHAIN_ID: Final = re.compile(r"\Avs-[0-9]{2}\Z")

#: Digest domains. Distinct so that a goal payload and a whole-scenario payload can never
#: collide across concepts even if they encoded to the same octets.
_SCENARIO_KIND: Final[str] = "vsscn"
_GOAL_KIND: Final[str] = "vsgoal"


# ---------------------------------------------------------------------------
# Small helpers: every one of them rejects rather than coerces
# ---------------------------------------------------------------------------


def _require(condition: bool, message: str, *, code: str | None = None) -> None:
    if not condition:
        raise SchemaError(message, code=code)


def _text(table: dict[str, Any], key: str, *, where: str) -> str:
    value = table.get(key)
    if not isinstance(value, str):
        raise SchemaError(f"{where}.{key}: expected a string, got {type(value).__name__}")
    return canon.nfc(value)


def _opt_text(table: dict[str, Any], key: str, *, where: str) -> str | None:
    if key not in table:
        return None
    return _text(table, key, where=where)


def _u32(table: dict[str, Any], key: str, *, where: str) -> int:
    value = table.get(key)
    canon.reject_float(value, where=f"{where}.{key}")
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{where}.{key}: expected an integer, got {type(value).__name__}")
    if not 0 <= value <= (1 << 32) - 1:
        raise SchemaError(f"{where}.{key}: {value} does not fit u32", code="E-CANON-WIDTH")
    return value


def _nanos(table: dict[str, Any], key: str, *, where: str) -> Nanos:
    """Nanoseconds arrive as decimal text, never as a TOML integer.

    The contract makes every i64 a string on the wire; keeping the same rule in the
    fixture means the author cannot express a value the artifacts could not carry.
    """
    raw = _text(table, key, where=where)
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", raw) is None:
        raise SchemaError(f"{where}.{key}: {raw!r} is not i64 decimal text")
    return check_nanos(int(raw), where=f"{where}.{key}")


def _bool(table: dict[str, Any], key: str, *, where: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise SchemaError(f"{where}.{key}: expected a boolean, got {type(value).__name__}")
    return value


def _attrs(table: dict[str, Any], key: str, *, where: str) -> tuple[tuple[str, str], ...]:
    """An attribute map, flattened to bytewise-ascending pairs. Values are always strings."""
    value = table.get(key, {})
    if not isinstance(value, dict):
        raise SchemaError(f"{where}.{key}: expected a table, got {type(value).__name__}")
    pairs: list[tuple[str, str]] = []
    for name, member in value.items():
        if not isinstance(member, str):
            raise SchemaError(f"{where}.{key}.{name}: attribute values are always strings")
        pairs.append((canon.nfc(name), canon.nfc(member)))
    ordered = tuple(sorted(pairs, key=lambda kv: canon.byte_order_key(kv[0])))
    canon.check_strictly_ascending(
        [k for k, _ in ordered], canon.byte_order_key, where=f"{where}.{key}"
    )
    return ordered


def _interval(table: dict[str, Any], *, where: str) -> Interval:
    t0 = _nanos(table, "t0_ns", where=where)
    t1 = _nanos(table, "t1_ns", where=where)
    _require(t0 < t1, f"{where}: an empty or inverted interval declares nothing")
    return Interval(t0_ns=t0, t1_ns=t1)


def _tables(document: dict[str, Any], key: str, *, where: str) -> list[dict[str, Any]]:
    value = document.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise SchemaError(f"{where}.{key}: expected an array of tables")
    return value


def _strings(table: dict[str, Any], key: str, *, where: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise SchemaError(f"{where}.{key}: expected an array of strings")
    return tuple(canon.nfc(v) for v in value)


# ---------------------------------------------------------------------------
# The members the foundation has no type for
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Phase:
    """One named regime of the hashed phase timeline.

    Regime membership comes from here and is never inferred from the data: a regime
    inferred from the bundle under analysis would let the calibration profile depend on
    the run it is supposed to be independent of.
    """

    regime_id: str
    interval: Interval

    def canonical_bytes(self) -> bytes:
        return canon.ascii_text(self.regime_id) + self.interval.canonical_bytes()


@dataclass(frozen=True, slots=True)
class ExcludedInterval:
    """A span whose gaps the calibration stage drops, with the reason stated in the fixture."""

    interval: Interval
    reason: str

    def canonical_bytes(self) -> bytes:
        return self.interval.canonical_bytes() + canon.utf8_text(self.reason)


@dataclass(frozen=True, slots=True)
class BlindnessDecl:
    """A declared sensor outage: the source emits nothing at all over this span.

    Declared rather than derived. The generator honours it by emitting nothing, and the
    liveness stage will classify the span BLIND from the resulting gap; the two facts are
    kept separate so that nothing in the pipeline reads the declaration as an observation.
    """

    source_id: SourceId
    interval: Interval
    basis: str

    def __post_init__(self) -> None:
        _require(self.basis == "blind", f"BlindnessDecl.basis must be 'blind', got {self.basis!r}")

    def canonical_bytes(self) -> bytes:
        return (
            canon.ascii_text(self.basis)
            + self.interval.canonical_bytes()
            + canon.ascii_text(self.source_id)
        )


@dataclass(frozen=True, slots=True)
class AttackStep:
    """One step of the simulated chain.

    `observable` false with `emits` empty is the case the whole slice exists for: a step
    that happened in the simulation and that no declared sensor could ever have recorded.
    It produces no raw event and exactly one ground-truth annotation, and the licence
    mechanism downstream is what has to account for it.
    """

    k: int
    actor: str
    action: str
    emits: tuple[SourceId, ...]
    attrs: tuple[tuple[str, str], ...]
    observable: bool
    t_offset_ns: Nanos
    expect_transition: tuple[tuple[str, str], ...]
    event_type: str | None = None

    def __post_init__(self) -> None:
        canon.u16(self.k)
        _require(
            self.observable == bool(self.emits),
            f"AttackStep k={self.k}: `emits` is empty exactly when `observable` is false",
        )
        _require(
            (self.event_type is None) == (not self.emits),
            f"AttackStep k={self.k}: `event_type` is absent exactly when `emits` is empty",
        )
        canon.check_strictly_ascending(
            self.emits, canon.byte_order_key, where=f"AttackStep k={self.k} emits"
        )

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.utf8_text(self.action),
                canon.utf8_text(self.actor),
                canon.pairs(self.attrs),
                canon.ordered_seq(canon.ascii_text(s) for s in self.emits),
                canon.utf8_text(self.event_type or ""),
                canon.pairs(self.expect_transition),
                canon.u16(self.k),
                canon.boolean(self.observable),
                canon.i64(self.t_offset_ns),
            )
        )


@dataclass(frozen=True, slots=True)
class AttackChain:
    """The simulated chain. Every rendering of it carries the word `simulated`."""

    chain_id: str
    steps: tuple[AttackStep, ...]

    def canonical_bytes(self) -> bytes:
        return canon.ascii_text(self.chain_id) + canon.ordered_seq(
            s.canonical_bytes() for s in self.steps
        )


@dataclass(frozen=True, slots=True)
class Noise:
    """The benign background population.

    `families` names event types, not abstract family labels. The contract gives
    `families` as bare strings and gives no member binding a family to a source, so the
    loader requires each family to be an event type that exactly one declared source
    emits and uses `SourceDecl.emits_event_types` as the binding. The alternative would
    have been a scenario member the specification does not define.

    The rate is one rational for the whole scenario, applied per family, because the
    contract declares exactly one `benign_rate_num`/`benign_rate_den` pair. Phases
    therefore differ by regime identity and by declared blindness, not by emission rate.
    """

    benign_rate_num: int
    benign_rate_den: int
    families: tuple[str, ...]

    def __post_init__(self) -> None:
        canon.u32(self.benign_rate_num)
        canon.u32(self.benign_rate_den)
        _require(self.benign_rate_den > 0, "Noise.benign_rate_den must be positive")
        _require(self.benign_rate_num > 0, "Noise.benign_rate_num must be positive")
        canon.check_strictly_ascending(
            self.families, canon.byte_order_key, where="Noise.families"
        )

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.u32(self.benign_rate_den),
                canon.u32(self.benign_rate_num),
                canon.ordered_seq(canon.utf8_text(f) for f in self.families),
            )
        )


@dataclass(frozen=True, slots=True)
class Entities:
    """The exact-join tables. Entity resolution is exact string matching against these."""

    principals: tuple[tuple[str, str], ...]
    devices: tuple[str, ...]
    credentials: tuple[tuple[str, str, str], ...]
    services: tuple[tuple[str, str], ...]
    resources: tuple[tuple[str, str, str], ...]
    zones: tuple[str, ...]

    @property
    def principal_ids(self) -> tuple[str, ...]:
        return tuple(p for p, _ in self.principals)

    @property
    def resource_ids(self) -> tuple[str, ...]:
        return tuple(r for r, _, _ in self.resources)

    @property
    def service_ids(self) -> tuple[str, ...]:
        return tuple(s for s, _ in self.services)

    def credentials_of(self, principal: str) -> tuple[str, ...]:
        return tuple(c for c, subject, _ in self.credentials if subject == principal)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(
                    canon.ascii_text(c) + canon.ascii_text(s) + canon.utf8_text(k)
                    for c, s, k in self.credentials
                ),
                canon.ordered_seq(canon.ascii_text(d) for d in self.devices),
                canon.ordered_seq(
                    canon.ascii_text(p) + canon.utf8_text(k) for p, k in self.principals
                ),
                canon.ordered_seq(
                    canon.ascii_text(r) + canon.ascii_text(z) + canon.utf8_text(s)
                    for r, z, s in self.resources
                ),
                canon.ordered_seq(
                    canon.ascii_text(s) + canon.ascii_text(z) for s, z in self.services
                ),
                canon.ordered_seq(canon.ascii_text(z) for z in self.zones),
            )
        )


@dataclass(frozen=True, slots=True)
class Goal:
    """The single goal. `goal_hash` covers this member alone, so it can be cited on its own."""

    goal_predicate: str
    goal_args: tuple[str, ...]
    horizon_k: int

    def __post_init__(self) -> None:
        canon.u32(self.horizon_k)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(canon.utf8_text(a) for a in self.goal_args),
                canon.utf8_text(self.goal_predicate),
                canon.u32(self.horizon_k),
            )
        )

    def to_scf(self) -> dict[str, Any]:
        return {
            "goal_args": list(self.goal_args),
            "goal_predicate": self.goal_predicate,
            "horizon_k": self.horizon_k,
        }


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """A loaded, validated scenario. Frozen, because its hash is quoted downstream."""

    schema: str
    scenario_id: str
    family: str
    epoch_ns: Nanos
    horizon_ticks: int
    tick_granularity_ns: int
    sources: tuple[Source, ...]
    phases: tuple[Phase, ...]
    excluded_intervals: tuple[ExcludedInterval, ...]
    entities: Entities
    noise: Noise
    attack: AttackChain
    blindness: tuple[BlindnessDecl, ...]
    goal: Goal

    @property
    def horizon(self) -> Interval:
        """The half-open span the scenario runs over."""
        return Interval(
            t0_ns=self.epoch_ns,
            t1_ns=self.epoch_ns + self.horizon_ticks * self.tick_granularity_ns,
        )

    def source(self, source_id: str | SourceId) -> Source:
        wanted = source_key(source_id)
        for declared in self.sources:
            if source_key(declared.source_id) == wanted:
                return declared
        raise SchemaError(f"ScenarioSpec: no declared source {source_id!r}")

    def source_of_event_type(self, event_type: str) -> Source:
        """The unique declared source emitting `event_type`. Uniqueness is a load constraint."""
        found = [s for s in self.sources if event_type in s.emits_event_types]
        if len(found) != 1:
            raise SchemaError(
                f"ScenarioSpec: event type {event_type!r} is emitted by {len(found)} sources, "
                "expected exactly one"
            )
        return found[0]

    def blind_windows(self, source_id: str | SourceId) -> tuple[Interval, ...]:
        """Declared outages for one source, in ascending start order."""
        wanted = source_key(source_id)
        return tuple(
            decl.interval for decl in self.blindness if source_key(decl.source_id) == wanted
        )

    def is_declared_blind(self, source_id: str | SourceId, t_ns: Nanos) -> bool:
        return any(window.contains(t_ns) for window in self.blind_windows(source_id))

    def phase_of(self, t_ns: Nanos) -> Phase | None:
        """The regime containing `t_ns`, or None. None is not an error; it is BLIND later."""
        for phase in self.phases:
            if phase.interval.contains(t_ns):
                return phase
        return None

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                self.attack.canonical_bytes(),
                canon.ordered_seq(b.canonical_bytes() for b in self.blindness),
                self.entities.canonical_bytes(),
                canon.i64(self.epoch_ns),
                canon.ordered_seq(x.canonical_bytes() for x in self.excluded_intervals),
                canon.utf8_text(self.family),
                self.goal.canonical_bytes(),
                canon.u32(self.horizon_ticks),
                self.noise.canonical_bytes(),
                canon.ordered_seq(p.canonical_bytes() for p in self.phases),
                canon.utf8_text(self.schema),
                canon.utf8_text(self.scenario_id),
                canon.ordered_seq(s.canonical_bytes() for s in self.sources),
                canon.u32(self.tick_granularity_ns),
            )
        )

    def scenario_hash(self) -> str:
        """`"b2b256:<64hex>"` over the whole loaded document, not over the file octets.

        Over the parsed content rather than the text so that reflowing the fixture or
        changing a comment does not invalidate an archived run, which is the same reason
        the specification separates `rules_hash` from `rules_text_hash`.
        """
        return canon.hash_ref(_SCENARIO_KIND, self.canonical_bytes())

    def goal_hash(self) -> str:
        """`"b2b256:<64hex>"` over the `goal` member alone."""
        return canon.hash_ref(_GOAL_KIND, self.goal.canonical_bytes())

    def generator_config_hash(self) -> str:
        """What gate B4 compares: the generator's whole input, which is the scenario.

        Identical to `scenario_hash` today. It is a separate method because B4's question
        is "was the profile calibrated against this generator configuration", and if the
        generator ever gains an input the scenario does not carry, this is the one place
        that has to change rather than every call site.
        """
        return self.scenario_hash()

    def excluded_intervals_hash(self) -> str:
        """What gate B6 compares."""
        return canon.hash_ref(
            _SCENARIO_KIND + "/excl",
            canon.ordered_seq(x.canonical_bytes() for x in self.excluded_intervals),
        )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_scenario(document: dict[str, Any]) -> ScenarioSpec:
    """Validate a parsed TOML document into a `ScenarioSpec`, or raise.

    Every check here is a loader constraint from the operative contract or a direct
    consequence of one. Nothing is repaired: a scenario that needs repairing is a
    scenario whose author does not yet know what their run will produce.
    """
    where = "scenario"
    schema = _text(document, "schema", where=where)
    _require(schema == SCENARIO_SCHEMA, f"{where}.schema: expected {SCENARIO_SCHEMA!r}, got {schema!r}")

    scenario_id = _text(document, "scenario_id", where=where)
    _require(
        _SCENARIO_ID.match(scenario_id) is not None,
        f"{where}.scenario_id: {scenario_id!r} does not match ^vs-[0-9]{{2}}-[a-z0-9-]+$",
    )
    family = _text(document, "family", where=where)
    _require(_SNAKE_NAME.match(family) is not None, f"{where}.family: {family!r} is not a snake name")

    epoch_ns = _nanos(document, "epoch_ns", where=where)
    horizon_ticks = _u32(document, "horizon_ticks", where=where)
    _require(horizon_ticks > 0, f"{where}.horizon_ticks must be positive")
    granularity = _u32(document, "tick_granularity_ns", where=where)
    _require(
        granularity == 1_000_000_000,
        f"{where}.tick_granularity_ns is fixed at 1000000000 in the slice, got {granularity}",
    )

    sources = _parse_sources(document)
    source_ids = {str(s.source_id) for s in sources}
    _require(
        any(s.integrity_class is IntegrityClass.NONE for s in sources),
        f"{where}.sources: at least one source must have integrity_class 'none'",
    )

    phases = _parse_phases(document)
    excluded = _parse_excluded(document)
    entities = _parse_entities(document)
    noise = _parse_noise(document)
    attack = _parse_attack(document, source_ids)
    blindness = _parse_blindness(document, source_ids)
    goal = _parse_goal(document)

    spec = ScenarioSpec(
        schema=schema,
        scenario_id=scenario_id,
        family=family,
        epoch_ns=epoch_ns,
        horizon_ticks=horizon_ticks,
        tick_granularity_ns=granularity,
        sources=sources,
        phases=phases,
        excluded_intervals=excluded,
        entities=entities,
        noise=noise,
        attack=attack,
        blindness=blindness,
        goal=goal,
    )
    _check_cross_member(spec)
    return spec


def _parse_sources(document: dict[str, Any]) -> tuple[Source, ...]:
    declared: list[Source] = []
    for table in _tables(document, "sources", where="scenario"):
        where = f"scenario.sources[{table.get('source_id')!r}]"
        source_id = SourceId.of(_text(table, "source_id", where=where))
        integrity = _text(table, "integrity_class", where=where)
        _require(
            integrity in {c.value for c in IntegrityClass},
            f"{where}.integrity_class: {integrity!r} is not a declared class",
        )
        emits = _strings(table, "emits_event_types", where=where)
        ordered = tuple(sorted(emits, key=canon.byte_order_key))
        canon.check_strictly_ascending(
            ordered, canon.byte_order_key, where=f"{where}.emits_event_types"
        )
        period = _nanos(table, "nominal_period_ns", where=where) if "nominal_period_ns" in table else None
        declared.append(
            Source(
                source_id=source_id,
                integrity_class=IntegrityClass(integrity),
                source_rank=_u32(table, "source_rank", where=where),
                emits_event_types=ordered,
                nominal_period_ns=period,
            )
        )
    _require(bool(declared), "scenario.sources: at least one source must be declared")
    ordered_sources = tuple(canon.sorted_by_bytes(declared, key=lambda s: str(s.source_id)))
    canon.check_strictly_ascending(
        [str(s.source_id) for s in ordered_sources], canon.byte_order_key, where="scenario.sources"
    )
    return ordered_sources


def _parse_phases(document: dict[str, Any]) -> tuple[Phase, ...]:
    phases: list[Phase] = []
    for table in _tables(document, "phases", where="scenario"):
        where = f"scenario.phases[{table.get('regime_id')!r}]"
        regime = _text(table, "regime_id", where=where)
        _require(_SNAKE_NAME.match(regime) is not None, f"{where}.regime_id is not a snake name")
        phases.append(Phase(regime_id=regime, interval=_interval(table, where=where)))
    _require(bool(phases), "scenario.phases: at least one phase must be declared")
    ordered = tuple(sorted(phases, key=lambda p: p.interval.sort_key()))
    canon.check_strictly_ascending(
        [p.interval.sort_key() for p in ordered], lambda k: k, where="scenario.phases"
    )
    for left, right in zip(ordered, ordered[1:]):
        _require(
            not left.interval.overlaps(right.interval),
            f"scenario.phases: {left.regime_id!r} and {right.regime_id!r} overlap",
        )
    canon.sorted_unique([p.regime_id for p in ordered])
    return ordered


def _parse_excluded(document: dict[str, Any]) -> tuple[ExcludedInterval, ...]:
    excluded: list[ExcludedInterval] = []
    for table in _tables(document, "excluded_intervals", where="scenario"):
        where = "scenario.excluded_intervals"
        excluded.append(
            ExcludedInterval(
                interval=_interval(table, where=where),
                reason=_text(table, "reason", where=where),
            )
        )
    ordered = tuple(sorted(excluded, key=lambda x: x.interval.sort_key()))
    canon.check_strictly_ascending(
        [x.interval.sort_key() for x in ordered], lambda k: k, where="scenario.excluded_intervals"
    )
    return ordered


def _parse_entities(document: dict[str, Any]) -> Entities:
    table = document.get("entities")
    if not isinstance(table, dict):
        raise SchemaError("scenario.entities: expected a table")
    where = "scenario.entities"

    zones = tuple(canon.sorted_unique(_strings(table, "zones", where=where)))
    for zone in zones:
        _require(_ENTITY_REF.match(zone) is not None, f"{where}.zones: {zone!r} is not a snake name")

    principals: list[tuple[str, str]] = []
    for row in _tables(table, "principals", where=where):
        ident = _text(row, "id", where=f"{where}.principals")
        _require(_ENTITY_REF.match(ident) is not None, f"{where}.principals: bad id {ident!r}")
        principals.append((ident, _text(row, "kind", where=f"{where}.principals")))

    devices = tuple(
        canon.sorted_unique(
            [_text(row, "id", where=f"{where}.devices") for row in _tables(table, "devices", where=where)]
        )
    )

    credentials: list[tuple[str, str, str]] = []
    for row in _tables(table, "credentials", where=where):
        credentials.append(
            (
                _text(row, "id", where=f"{where}.credentials"),
                _text(row, "subject", where=f"{where}.credentials"),
                _text(row, "kind", where=f"{where}.credentials"),
            )
        )

    services: list[tuple[str, str]] = []
    for row in _tables(table, "services", where=where):
        services.append(
            (_text(row, "id", where=f"{where}.services"), _text(row, "zone", where=f"{where}.services"))
        )

    resources: list[tuple[str, str, str]] = []
    for row in _tables(table, "resources", where=where):
        resources.append(
            (
                _text(row, "id", where=f"{where}.resources"),
                _text(row, "zone", where=f"{where}.resources"),
                _text(row, "sensitivity", where=f"{where}.resources"),
            )
        )

    entities = Entities(
        principals=tuple(sorted(principals, key=lambda p: canon.byte_order_key(p[0]))),
        devices=devices,
        credentials=tuple(sorted(credentials, key=lambda c: canon.byte_order_key(c[0]))),
        services=tuple(sorted(services, key=lambda s: canon.byte_order_key(s[0]))),
        resources=tuple(sorted(resources, key=lambda r: canon.byte_order_key(r[0]))),
        zones=zones,
    )
    canon.sorted_unique(entities.principal_ids)
    canon.sorted_unique([c for c, _, _ in entities.credentials])
    canon.sorted_unique(entities.service_ids)
    canon.sorted_unique(entities.resource_ids)
    zone_set = set(zones)
    for ident, zone in entities.services:
        _require(zone in zone_set, f"{where}.services[{ident!r}]: undeclared zone {zone!r}")
    for ident, zone, _sensitivity in entities.resources:
        _require(zone in zone_set, f"{where}.resources[{ident!r}]: undeclared zone {zone!r}")
    principal_set = set(entities.principal_ids)
    for ident, subject, _kind in entities.credentials:
        _require(
            subject in principal_set,
            f"{where}.credentials[{ident!r}]: subject {subject!r} is not a declared principal",
        )
    _require(bool(entities.principals), f"{where}.principals must be non-empty")
    _require(bool(entities.resources), f"{where}.resources must be non-empty")
    _require(bool(entities.services), f"{where}.services must be non-empty")
    return entities


def _parse_noise(document: dict[str, Any]) -> Noise:
    table = document.get("noise")
    if not isinstance(table, dict):
        raise SchemaError("scenario.noise: expected a table")
    where = "scenario.noise"
    families = tuple(canon.sorted_unique(_strings(table, "families", where=where)))
    return Noise(
        benign_rate_num=_u32(table, "benign_rate_num", where=where),
        benign_rate_den=_u32(table, "benign_rate_den", where=where),
        families=families,
    )


def _parse_attack(document: dict[str, Any], source_ids: set[str]) -> AttackChain:
    table = document.get("attack")
    if not isinstance(table, dict):
        raise SchemaError("scenario.attack: expected a table")
    chain_id = _text(table, "chain_id", where="scenario.attack")
    _require(
        _CHAIN_ID.match(chain_id) is not None,
        f"scenario.attack.chain_id: {chain_id!r} does not match ^vs-[0-9]{{2}}$",
    )
    steps: list[AttackStep] = []
    for row in _tables(table, "steps", where="scenario.attack"):
        where = f"scenario.attack.steps[k={row.get('k')}]"
        emits = tuple(
            sorted(
                (SourceId.of(s) for s in _strings(row, "emits", where=where)),
                key=canon.byte_order_key,
            )
        )
        for source_id in emits:
            _require(str(source_id) in source_ids, f"{where}.emits: undeclared source {source_id}")
        transition = row.get("expect_transition")
        if not isinstance(transition, dict):
            raise SchemaError(f"{where}.expect_transition: expected a table")
        for key in ("dim", "from", "to"):
            _require(key in transition, f"{where}.expect_transition: missing {key!r}")
        steps.append(
            AttackStep(
                k=_u32(row, "k", where=where),
                actor=_text(row, "actor", where=where),
                action=_text(row, "action", where=where),
                emits=emits,
                attrs=_attrs(row, "attrs", where=where),
                observable=_bool(row, "observable", where=where),
                t_offset_ns=_nanos(row, "t_offset_ns", where=where),
                expect_transition=_attrs(row, "expect_transition", where=where),
                event_type=_opt_text(row, "event_type", where=where),
            )
        )
    _require(bool(steps), "scenario.attack.steps: the chain must have at least one step")
    ordered = tuple(sorted(steps, key=lambda s: s.k))
    canon.check_strictly_ascending([s.k for s in ordered], lambda k: k, where="scenario.attack.steps")
    return AttackChain(chain_id=chain_id, steps=ordered)


def _parse_blindness(document: dict[str, Any], source_ids: set[str]) -> tuple[BlindnessDecl, ...]:
    declared: list[BlindnessDecl] = []
    for table in _tables(document, "blindness", where="scenario"):
        where = "scenario.blindness"
        source_id = SourceId.of(_text(table, "source_id", where=where))
        _require(str(source_id) in source_ids, f"{where}: undeclared source {source_id}")
        declared.append(
            BlindnessDecl(
                source_id=source_id,
                interval=_interval(table, where=where),
                basis=_text(table, "basis", where=where),
            )
        )
    ordered = tuple(
        sorted(declared, key=lambda d: (canon.byte_order_key(str(d.source_id)), d.interval.sort_key()))
    )
    canon.check_strictly_ascending(
        [(canon.byte_order_key(str(d.source_id)), d.interval.sort_key()) for d in ordered],
        lambda k: k,
        where="scenario.blindness",
    )
    return ordered


def _parse_goal(document: dict[str, Any]) -> Goal:
    table = document.get("goal")
    if not isinstance(table, dict):
        raise SchemaError("scenario.goal: expected exactly one goal table")
    where = "scenario.goal"
    return Goal(
        goal_predicate=_text(table, "goal_predicate", where=where),
        goal_args=_strings(table, "goal_args", where=where),
        horizon_k=_u32(table, "horizon_k", where=where),
    )


def _check_cross_member(spec: ScenarioSpec) -> None:
    """The constraints that need more than one member to state."""
    horizon = spec.horizon

    for phase in spec.phases:
        _require(
            horizon.covers(phase.interval),
            f"scenario.phases[{phase.regime_id!r}]: phase leaves the horizon",
        )
    for excluded in spec.excluded_intervals:
        _require(
            horizon.covers(excluded.interval),
            "scenario.excluded_intervals: an excluded span leaves the horizon",
        )
    for decl in spec.blindness:
        _require(
            horizon.covers(decl.interval),
            f"scenario.blindness[{decl.source_id}]: a blind window leaves the horizon",
        )

    for family in spec.noise.families:
        source = spec.source_of_event_type(family)
        _require(
            bool(source.emits_event_types),
            f"scenario.noise.families: {family!r} names a source that emits nothing",
        )

    emitting = {
        event_type for source in spec.sources for event_type in source.emits_event_types
    }
    for step in spec.attack.steps:
        t_ns = spec.epoch_ns + step.t_offset_ns
        _require(
            horizon.contains(t_ns),
            f"scenario.attack.steps[k={step.k}]: t_offset_ns leaves the horizon",
        )
        if step.event_type is not None:
            _require(
                step.event_type in emitting,
                f"scenario.attack.steps[k={step.k}]: {step.event_type!r} is emitted by no source",
            )
            for source_id in step.emits:
                _require(
                    step.event_type in spec.source(str(source_id)).emits_event_types,
                    f"scenario.attack.steps[k={step.k}]: {source_id} does not declare "
                    f"{step.event_type!r}",
                )

    _require(
        any(not step.observable for step in spec.attack.steps),
        "scenario.attack: the slice's point requires at least one unobservable step",
    )
    _require(
        any(not source.emits_event_types for source in spec.sources),
        "scenario.sources: the slice's point requires a declared source that emits nothing",
    )


def load_scenario(path: Path | str) -> ScenarioSpec:
    """Read and validate the scenario fixture at `path`."""
    resolved = Path(path)
    with open(resolved, "rb") as handle:
        document = tomllib.load(handle)
    return parse_scenario(document)


def scenario_summary(spec: ScenarioSpec) -> str:
    """A one-object canonical rendering, for a manifest line or a test comparison."""
    return scf_dumps(
        {
            "family": spec.family,
            "goal_hash": spec.goal_hash(),
            "horizon_ticks": spec.horizon_ticks,
            "scenario_hash": spec.scenario_hash(),
            "scenario_id": spec.scenario_id,
            "source_count": len(spec.sources),
            "step_count": len(spec.attack.steps),
        }
    )
