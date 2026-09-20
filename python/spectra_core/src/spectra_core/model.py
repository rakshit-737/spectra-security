"""The record types the pipeline stages exchange.

Every type here is a frozen dataclass, every type has a canonical byte encoding, and
every type has an identity. Frozen because a stage that could mutate a record it received
could invalidate an id that another stage already wrote into an artifact; the pipeline is
a chain of pure functions over hashed inputs, and immutable records are what make that
claim checkable rather than aspirational.

FIELD NAMES follow the operative slice specification's `data_contracts` section verbatim,
because those names are the wire contract that every other stage is written against.
IDENTIFIER STRINGS follow section 57.2, because section 57 is normative over the rest of
the specification and its prefix and width rules are what `spectra_core.ids` enforces.

THREE DIVERGENCES, recorded here rather than discovered later.

1. `event_id` and `record_id` both appear on `CanonicalEvent`. The operative spec keys
   evidence on `event_id`; section 57.8 says the kernel must never read `event_id` and
   that every evidence leaf is a `RecordId`. Both fields are therefore present and
   populated by ingest. A stage that wants to honour 57.8 cites `record_id`; a stage
   written to the operative spec cites `event_id`. Which one a certificate may carry is
   decided by `ids.reject_run_local_in_certificate`, not by this module.

2. `GroundTruth.truth_id` is a `tr_<16hex>` string, not a section 57 identifier type. The
   operative spec defines it; section 57 defines no truth-annotation concept, and
   inventing one here would add a vocabulary row that no owning section defines. It is
   validated by grammar and typed as `str` so that nothing mistakes it for a
   `TransitionId`.

3. `Cut.atoms`, `Corridor.atom_ranks` and `ThresholdLiteral` coexist. `docs/vocab.toml`
   retires the word the first two use; the operative spec's data contract spells the
   field names that way and other stages are written against them. The type is named for
   the canonical concept, the fields keep the contract's spelling, and the retirement is
   a documentation conflict for section 57's owner to close, not something to resolve by
   renaming a wire field unilaterally.

NO WALL CLOCK is read anywhere in this module, and there are no floats in any field.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, Self

from spectra_core import canon
from spectra_core.errors import CanonError, SchemaError
from spectra_core.ids import (
    CertId,
    ControlId,
    CorridorId,
    CutId,
    DimensionId,
    EntityId,
    EventId,
    FactHash,
    InstanceId,
    LicenseId,
    LiteralId,
    RecordId,
    RuleId,
    SourceId,
    Tick,
    WindowId,
    check_level,
    check_tick,
    require_id,
)

__all__ = [
    "TICK_GRANULARITY_NS",
    "BlindWindow",
    "Canonical",
    "CanonicalEvent",
    "Certificate",
    "Corridor",
    "Cut",
    "Entity",
    "EvidenceRef",
    "Fact",
    "GroundTruth",
    "IntegrityClass",
    "Interval",
    "Licence",
    "LicenceBasis",
    "LivenessVerdict",
    "Minimality",
    "Nanos",
    "Observation",
    "ProgramKind",
    "Record",
    "Rule",
    "RuleInstance",
    "RuleKind",
    "Source",
    "ThresholdLiteral",
    "TruthKind",
    "TruthOrigin",
    "check_nanos",
    "tick_of",
]


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

#: The one timestamp quantity in this layer: integer nanoseconds since the Unix epoch,
#: UTC. There is no second time type, no float seconds and no timezone-aware object,
#: because a second representation is a second place for a conversion to round.
Nanos = int

#: The slice's tick granularity. `tick(t) = t_evt_ns // 1_000_000_000`. This constant is
#: hashed into the rules digest by the guard front end; changing it invalidates every
#: certificate, which is the intended cost of changing what a tick means.
TICK_GRANULARITY_NS: Final[int] = 1_000_000_000

_NANOS_MIN: Final[int] = -(1 << 63)
_NANOS_MAX: Final[int] = (1 << 63) - 1


def check_nanos(value: int, *, where: str) -> Nanos:
    """Return `value` if it is an i64 nanosecond instant. Rejects bools and floats."""
    canon.reject_float(value, where=where)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{where}: expected int nanoseconds, got {type(value).__name__}")
    if not _NANOS_MIN <= value <= _NANOS_MAX:
        raise SchemaError(f"{where}: {value} does not fit i64 nanoseconds", code="E-CANON-WIDTH")
    return value


def tick_of(t_ns: Nanos) -> Tick:
    """Floor-divide an instant into the slice's tick index.

    Floor rather than truncate so that the mapping is monotone across zero; a truncating
    division would map two adjacent instants either side of the epoch onto the same tick.
    """
    return check_nanos(t_ns, where="tick_of") // TICK_GRANULARITY_NS


@dataclass(frozen=True, slots=True)
class Interval:
    """A half-open nanosecond interval `[t0_ns, t1_ns)`.

    Half-open everywhere, with no closed variant available, because a closed upper bound
    at a boundary changes which side of a phase change an instant falls on, and the
    liveness classification is decided at exactly those boundaries.
    """

    t0_ns: Nanos
    t1_ns: Nanos

    def __post_init__(self) -> None:
        check_nanos(self.t0_ns, where="Interval.t0_ns")
        check_nanos(self.t1_ns, where="Interval.t1_ns")
        if self.t1_ns < self.t0_ns:
            raise SchemaError(f"Interval: t1_ns {self.t1_ns} precedes t0_ns {self.t0_ns}")

    @property
    def is_empty(self) -> bool:
        return self.t0_ns == self.t1_ns

    @property
    def duration_ns(self) -> int:
        return self.t1_ns - self.t0_ns

    def contains(self, t_ns: Nanos) -> bool:
        """Half-open membership: the lower bound is in, the upper bound is out."""
        return self.t0_ns <= check_nanos(t_ns, where="Interval.contains") < self.t1_ns

    def covers(self, other: Interval) -> bool:
        """True when `other` lies entirely inside this interval."""
        return self.t0_ns <= other.t0_ns and other.t1_ns <= self.t1_ns

    def overlaps(self, other: Interval) -> bool:
        """True when the two half-open intervals share at least one instant."""
        return self.t0_ns < other.t1_ns and other.t0_ns < self.t1_ns

    def canonical_bytes(self) -> bytes:
        return canon.i64(self.t0_ns) + canon.i64(self.t1_ns)

    def sort_key(self) -> tuple[int, int]:
        return (self.t0_ns, self.t1_ns)


# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------


class IntegrityClass(StrEnum):
    """What a source's own record linking can establish. `NONE` is not a defect."""

    CHAINED = "chained"
    SEQUENCED = "sequenced"
    NONE = "none"


class LivenessVerdict(StrEnum):
    """The per-(source, interval) verdict. The fail-closed value is `BLIND`."""

    LIVE = "LIVE"
    BLIND = "BLIND"
    SUPPRESSED = "SUPPRESSED"


class LicenceBasis(StrEnum):
    """Why a licence exists. `BLIND` carries a reason and no witness, never an observation."""

    BLIND = "BLIND"
    SUPPRESSED = "SUPPRESSED"
    OBLIGATION = "OBLIGATION"


class Observation(StrEnum):
    """Whether a rule instance rests on records or on a licence.

    No rendering may collapse these two into one word: one of them cites evidence and the
    other cites permission for a step nobody could have seen.
    """

    OBSERVED = "OBSERVED"
    LICENSED = "LICENSED"


class Minimality(StrEnum):
    """What is claimed about the size of a cut. Independent of safety, in both directions."""

    EXACT_EXHAUSTIVE = "EXACT_EXHAUSTIVE"
    EXACT_PSI_RELATIVE = "EXACT_PSI_RELATIVE"
    SUBSET = "SUBSET"
    UNVERIFIED = "UNVERIFIED"


class ProgramKind(StrEnum):
    """Which side of the two-sided bracket a derived object came from."""

    P_MIN = "PMin"
    P_MAX = "PMax"


class RuleKind(StrEnum):
    DETECT = "detect"
    OBLIGATION = "obligation"


class TruthKind(StrEnum):
    """Ground-truth annotation kinds. Oracle channel only; never read by the kernel."""

    BENIGN = "benign"
    ATTACK_STEP = "attack_step"
    ATTACK_UNOBSERVED = "attack_unobserved"
    NOISE_LOOKALIKE = "noise_lookalike"


class TruthOrigin(StrEnum):
    POPULATION = "population"
    SCENARIO = "scenario"
    DEGRADATION = "degradation"


# ---------------------------------------------------------------------------
# The canonical-record base
# ---------------------------------------------------------------------------


class Canonical(ABC):
    """A record with a deterministic byte encoding and a domain-separated digest.

    `ID_KIND` is the section 57.3 domain separator for this concept. It is a class
    attribute rather than a parameter so that two concepts cannot be hashed under the
    same domain by a caller passing the wrong string.
    """

    __slots__ = ()

    ID_KIND: ClassVar[str]

    @abstractmethod
    def canonical_bytes(self) -> bytes:
        """The whole record, in fixed field order, with no JSON and no floats."""

    def identity_bytes(self) -> bytes:
        """The subset of the record its identifier is minted from.

        Defaults to the whole record. Types whose data contract mints an id from fewer
        fields override this, and the override is where that narrowing is visible.
        """
        return self.canonical_bytes()

    def content_hash(self) -> str:
        """A full-width hash reference over the whole record, `"b2b256:<64hex>"`."""
        return canon.hash_ref(type(self).ID_KIND, self.canonical_bytes())


def _text_seq(values: tuple[str, ...]) -> bytes:
    return canon.ordered_seq(canon.utf8_text(v) for v in values)


def _id_seq(values: tuple[str, ...]) -> bytes:
    return canon.ordered_seq(canon.ascii_text(v) for v in values)


def _optional(value: object, encode) -> bytes:
    """Presence octet then the value, so absence and an empty value differ in the bytes."""
    if value is None:
        return canon.boolean(False)
    return canon.boolean(True) + encode(value)


def _require_sorted_ids(values: tuple[str, ...], *, where: str) -> None:
    canon.check_strictly_ascending(values, canon.byte_order_key, where=where)


# ---------------------------------------------------------------------------
# 1. Record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Record(Canonical):
    """One serialized telemetry line as ingested, digested over its exact pre-parse bytes.

    The digest covers the bytes and nothing else, per Table A row 2, so that a degradation
    operator that alters a line alters its `RecordId` while leaving the generator's
    `EventId` for the same occurrence untouched. That is what lets an oracle re-link a
    perturbed bundle to ground truth.
    """

    ID_KIND: ClassVar[str] = "rc"

    record_id: RecordId
    source_id: SourceId
    raw_bytes: bytes

    def __post_init__(self) -> None:
        require_id(self.record_id, RecordId, where="Record.record_id")
        require_id(self.source_id, SourceId, where="Record.source_id")
        if not isinstance(self.raw_bytes, bytes):
            raise SchemaError(
                f"Record.raw_bytes must be bytes, got {type(self.raw_bytes).__name__}"
            )

    @classmethod
    def mint(cls, source_id: SourceId, raw_bytes: bytes) -> Self:
        return cls(
            record_id=RecordId.mint(raw_bytes),
            source_id=source_id,
            raw_bytes=raw_bytes,
        )

    def identity_bytes(self) -> bytes:
        return self.raw_bytes

    def canonical_bytes(self) -> bytes:
        return canon.ascii_text(self.source_id) + canon.blob(self.raw_bytes)

    def verify_id(self) -> bool:
        return self.record_id == RecordId.mint(self.identity_bytes())


# ---------------------------------------------------------------------------
# 2. CanonicalEvent
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CanonicalEvent(Canonical):
    """One bundle record: a parsed, sealed, canonically ordered telemetry line.

    `chain_hash` and `chain_prev` are present exactly when the source's integrity class is
    not `none`; they are absent, not null, on an unlinked source. Absence is how this
    layer expresses optionality everywhere, because `null` is never a value on the wire.
    """

    ID_KIND: ClassVar[str] = "ev"

    event_id: EventId
    record_id: RecordId
    source_id: SourceId
    seq: int
    event_type: str
    t_evt_ns: Nanos
    t_ing_ns: Nanos
    attrs: tuple[tuple[str, str], ...] = ()
    chain_hash: str | None = None
    chain_prev: str | None = None

    def __post_init__(self) -> None:
        require_id(self.event_id, EventId, where="CanonicalEvent.event_id")
        require_id(self.record_id, RecordId, where="CanonicalEvent.record_id")
        require_id(self.source_id, SourceId, where="CanonicalEvent.source_id")
        canon.u32(self.seq)
        check_nanos(self.t_evt_ns, where="CanonicalEvent.t_evt_ns")
        check_nanos(self.t_ing_ns, where="CanonicalEvent.t_ing_ns")
        _check_attrs(self.attrs, where="CanonicalEvent.attrs")
        if (self.chain_hash is None) != (self.chain_prev is None):
            raise SchemaError(
                "CanonicalEvent: chain_hash and chain_prev are present or absent together"
            )
        for label, value in (("chain_hash", self.chain_hash), ("chain_prev", self.chain_prev)):
            if value is not None:
                canon.parse_hash_ref(value)

    @property
    def tick(self) -> Tick:
        return tick_of(self.t_evt_ns)

    def identity_bytes(self) -> bytes:
        """The event-id preimage: attrs, event_type, seq, source_id, t_evt_ns.

        Ingestion time is deliberately excluded: two runs that ingest the same emitted
        line at different moments must mint the same event id, or nothing downstream
        replays byte-identically.
        """
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
        return b"".join(
            (
                canon.pairs(self.attrs),
                _optional(self.chain_hash, canon.ascii_text),
                _optional(self.chain_prev, canon.ascii_text),
                canon.ascii_text(self.event_id),
                canon.utf8_text(self.event_type),
                canon.ascii_text(self.record_id),
                canon.u32(self.seq),
                canon.ascii_text(self.source_id),
                canon.i64(self.t_evt_ns),
                canon.i64(self.t_ing_ns),
            )
        )

    def verify_id(self) -> bool:
        return self.event_id == EventId.mint(self.identity_bytes())

    def sort_key(self) -> tuple[int, str, int, str]:
        """The bundle file order: ascending t_evt_ns, source_id, seq, event_id."""
        return (self.t_evt_ns, str(self.source_id), self.seq, str(self.event_id))


def _check_attrs(attrs: tuple[tuple[str, str], ...], *, where: str) -> None:
    """Attribute values are always strings, and the pairs are strictly ascending by key.

    Strings only, with no coercion, because a number in an attribute position is the
    shortest path to a float reaching a hash preimage.
    """
    if not isinstance(attrs, tuple):
        raise SchemaError(f"{where}: attrs must be a tuple of pairs, got {type(attrs).__name__}")
    keys: list[str] = []
    for pair in attrs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise SchemaError(f"{where}: each attr must be a (key, value) pair")
        key, value = pair
        if not isinstance(key, str) or not isinstance(value, str):
            raise SchemaError(f"{where}: attr keys and values must both be str")
        keys.append(key)
    canon.check_strictly_ascending(keys, canon.byte_order_key, where=where)


# ---------------------------------------------------------------------------
# 3. Entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Entity(Canonical):
    """A resolved actor or object of a closed kind, produced by entity resolution.

    `join_rule_id` records which exact string join produced this entity. There is no
    fuzzy matching, no similarity and no score anywhere in resolution, so naming the rule
    is a complete account of why these records were merged.
    """

    ID_KIND: ClassVar[str] = "en"

    entity_id: EntityId
    kind: str
    canonical_name: str
    join_rule_id: str
    resolved_from: tuple[EventId, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.entity_id, EntityId, where="Entity.entity_id")
        if self.entity_id.kind != self.kind:
            raise SchemaError(
                f"Entity: kind {self.kind!r} disagrees with the id's kind {self.entity_id.kind!r}"
            )
        for event_id in self.resolved_from:
            require_id(event_id, EventId, where="Entity.resolved_from")
        _require_sorted_ids(self.resolved_from, where="Entity.resolved_from")

    @classmethod
    def mint(
        cls,
        kind: str,
        canonical_name: str,
        join_rule_id: str,
        resolved_from: tuple[EventId, ...] = (),
    ) -> Self:
        payload = canon.utf8_text(canonical_name) + canon.ascii_text(kind)
        return cls(
            entity_id=EntityId.mint(kind, payload),
            kind=kind,
            canonical_name=canonical_name,
            join_rule_id=join_rule_id,
            resolved_from=tuple(sorted(resolved_from, key=canon.byte_order_key)),
        )

    def identity_bytes(self) -> bytes:
        """The entity-id preimage: canonical_name then kind, and nothing else.

        Deliberately excludes `resolved_from`: the same entity resolved from a different
        set of records under degradation must keep the same id, or every fact naming it
        changes key and the two completeness cells become incomparable.
        """
        return canon.utf8_text(self.canonical_name) + canon.ascii_text(self.kind)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.utf8_text(self.canonical_name),
                canon.ascii_text(self.entity_id),
                canon.utf8_text(self.join_rule_id),
                canon.ascii_text(self.kind),
                _id_seq(self.resolved_from),
            )
        )

    def verify_id(self) -> bool:
        return self.entity_id == EntityId.mint(self.kind, self.identity_bytes())


# ---------------------------------------------------------------------------
# 4. Source
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Source(Canonical):
    """A declared telemetry origin with a class, a rank and an optional nominal period.

    A source that emits zero records is still declared, and that is the point: a declared
    source with no records is BLIND everywhere and fails closed, where an undeclared one
    would simply be invisible.
    """

    ID_KIND: ClassVar[str] = "src"

    source_id: SourceId
    integrity_class: IntegrityClass
    source_rank: int
    emits_event_types: tuple[str, ...] = ()
    nominal_period_ns: Nanos | None = None

    def __post_init__(self) -> None:
        require_id(self.source_id, SourceId, where="Source.source_id")
        if not isinstance(self.integrity_class, IntegrityClass):
            raise SchemaError("Source.integrity_class must be an IntegrityClass")
        canon.u8(self.source_rank)
        canon.check_strictly_ascending(
            self.emits_event_types, canon.byte_order_key, where="Source.emits_event_types"
        )
        if self.nominal_period_ns is not None:
            if check_nanos(self.nominal_period_ns, where="Source.nominal_period_ns") <= 0:
                raise SchemaError("Source.nominal_period_ns must be positive when present")

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                _text_seq(self.emits_event_types),
                canon.ascii_text(str(self.integrity_class)),
                _optional(self.nominal_period_ns, canon.i64),
                canon.ascii_text(self.source_id),
                canon.u8(self.source_rank),
            )
        )


# ---------------------------------------------------------------------------
# 5. Fact
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Fact(Canonical):
    """A ground, time-indexed predicate instance; an OR-node of the hypergraph."""

    ID_KIND: ClassVar[str] = "fh"

    fact_key: FactHash
    predicate: str
    args: tuple[EntityId, ...]
    tick: Tick

    def __post_init__(self) -> None:
        require_id(self.fact_key, FactHash, where="Fact.fact_key")
        for arg in self.args:
            require_id(arg, EntityId, where="Fact.args")
        check_tick(self.tick, where="Fact.tick")

    @classmethod
    def mint(cls, predicate: str, args: tuple[EntityId, ...], tick: Tick) -> Self:
        payload = _fact_payload(predicate, args, tick)
        return cls(fact_key=FactHash.mint(payload), predicate=predicate, args=args, tick=tick)

    def identity_bytes(self) -> bytes:
        return _fact_payload(self.predicate, self.args, self.tick)

    def canonical_bytes(self) -> bytes:
        return canon.ascii_text(self.fact_key) + self.identity_bytes()

    def verify_id(self) -> bool:
        return self.fact_key == FactHash.mint(self.identity_bytes())


def _fact_payload(predicate: str, args: tuple[EntityId, ...], tick: Tick) -> bytes:
    """args, predicate, tick. `args` is positional, so its order is content, not a set."""
    return _id_seq(args) + canon.utf8_text(predicate) + canon.u32(tick)


# ---------------------------------------------------------------------------
# 6. Rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rule(Canonical):
    """One authored implication: head, body, two guards, producing sources, provenance.

    `note` is free prose and is excluded from both `canonical_bytes` and
    `metadata_bytes`, so reflowing a comment cannot invalidate an archived certificate.
    That exclusion is the whole reason the two encodings are separate from the file bytes.
    """

    ID_KIND: ClassVar[str] = "rl"

    rule_id: RuleId
    rule_version: str
    dimension: DimensionId
    kind: RuleKind
    head: str
    body: tuple[str, ...]
    producing_sources: tuple[SourceId, ...]
    silent_possible: bool
    when: str = ""
    blocked_when: str = ""
    temporal: tuple[tuple[str, str], ...] = ()
    persistence: str = "instant"
    evidence: tuple[str, ...] = ()
    causal_relation: str = ""
    attck: tuple[str, ...] = ()
    note: str = ""

    _VERSION: ClassVar[re.Pattern[str]] = re.compile(r"\A\d+\.\d+\.\d+\Z")
    _MAX_BODY: ClassVar[int] = 4

    def __post_init__(self) -> None:
        require_id(self.rule_id, RuleId, where="Rule.rule_id")
        require_id(self.dimension, DimensionId, where="Rule.dimension")
        if self._VERSION.match(self.rule_version) is None:
            raise SchemaError(f"Rule.rule_version is not semantic: {self.rule_version!r}")
        if not isinstance(self.kind, RuleKind):
            raise SchemaError("Rule.kind must be a RuleKind")
        if len(self.body) > self._MAX_BODY:
            raise SchemaError(
                f"Rule.body has {len(self.body)} patterns; the slice narrows to {self._MAX_BODY}"
            )
        for source_id in self.producing_sources:
            require_id(source_id, SourceId, where="Rule.producing_sources")
        _require_sorted_ids(self.producing_sources, where="Rule.producing_sources")
        if not isinstance(self.silent_possible, bool):
            raise SchemaError("Rule.silent_possible must be a bool")
        _check_attrs(self.temporal, where="Rule.temporal")

    def metadata_bytes(self) -> bytes:
        """The per-rule metadata record the rules digest covers.

        Exactly rule_id, head, body sorted, producing_sources sorted, silent_possible and
        attck sorted. Nothing else: the guard AST is covered by its own digest, and the
        file bytes by a third that is recorded and never enforced.
        """
        return b"".join(
            (
                canon.sorted_set(canon.utf8_text(a) for a in self.attck),
                canon.sorted_set(canon.utf8_text(p) for p in self.body),
                canon.utf8_text(self.head),
                canon.sorted_set(canon.ascii_text(s) for s in self.producing_sources),
                canon.ascii_text(self.rule_id),
                canon.boolean(self.silent_possible),
            )
        )

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.sorted_set(canon.utf8_text(a) for a in self.attck),
                canon.utf8_text(self.blocked_when),
                _text_seq(self.body),
                canon.utf8_text(self.causal_relation),
                canon.ascii_text(self.dimension),
                _text_seq(self.evidence),
                canon.utf8_text(self.head),
                canon.ascii_text(str(self.kind)),
                canon.utf8_text(self.persistence),
                _id_seq(self.producing_sources),
                canon.ascii_text(self.rule_id),
                canon.ascii_text(self.rule_version),
                canon.boolean(self.silent_possible),
                canon.pairs(self.temporal),
                canon.utf8_text(self.when),
            )
        )


# ---------------------------------------------------------------------------
# 7. RuleInstance and its evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceRef(Canonical):
    """One body binding tied to the record that satisfied it.

    Carries the source and the event time alongside the id so that a witness tree can be
    checked against the liveness document without a second lookup into the bundle.
    """

    ID_KIND: ClassVar[str] = "ev"

    binding: str
    event_id: EventId
    source_id: SourceId
    t_evt_ns: Nanos

    def __post_init__(self) -> None:
        require_id(self.event_id, EventId, where="EvidenceRef.event_id")
        require_id(self.source_id, SourceId, where="EvidenceRef.source_id")
        check_nanos(self.t_evt_ns, where="EvidenceRef.t_evt_ns")

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.utf8_text(self.binding),
                canon.ascii_text(self.event_id),
                canon.ascii_text(self.source_id),
                canon.i64(self.t_evt_ns),
            )
        )

    def sort_key(self) -> tuple[str, str]:
        """Evidence is sorted by (binding, event_id), per the data contract."""
        return (self.binding, str(self.event_id))


@dataclass(frozen=True, slots=True)
class RuleInstance(Canonical):
    """One grounding of one rule; an AND-node of the hypergraph.

    The two mutually exclusive shapes are enforced here rather than by convention: an
    `OBSERVED` instance has evidence and no licences, a `LICENSED` instance has licences
    and no evidence. A record that had both would be a silent step wearing an
    observation's clothes, which is precisely what this project exists to prevent.
    """

    ID_KIND: ClassVar[str] = "in"

    instance_id: InstanceId
    rule_id: RuleId
    rule_version: str
    head: FactHash
    body: tuple[FactHash, ...]
    blockers: tuple[int, ...]
    observed: Observation
    tick: Tick
    evidence: tuple[EvidenceRef, ...] = ()
    license_ids: tuple[LicenseId, ...] = ()
    ghost: bool = False

    def __post_init__(self) -> None:
        require_id(self.instance_id, InstanceId, where="RuleInstance.instance_id")
        require_id(self.rule_id, RuleId, where="RuleInstance.rule_id")
        require_id(self.head, FactHash, where="RuleInstance.head")
        for fact_key in self.body:
            require_id(fact_key, FactHash, where="RuleInstance.body")
        for mask in self.blockers:
            canon.mask_hex(mask)
            if mask.bit_count() != 1:
                # C-SLICE-1, stated as a narrowing and asserted so that it stays visible:
                # every DNF term has popcount 1, which collapses the general subset test
                # `(term & S) == term` to `(mask & S) != 0`. The general form stays in the
                # reachability code behind this assertion.
                raise SchemaError(
                    f"RuleInstance.blockers: term {canon.mask_hex(mask)} has popcount "
                    f"{mask.bit_count()}; C-SLICE-1 narrows blockers to single literals",
                    code="E-VS-BLOCK-CONJ",
                )
        canon.check_strictly_ascending(
            self.blockers, lambda m: (m.bit_count(), m), where="RuleInstance.blockers"
        )
        if not isinstance(self.observed, Observation):
            raise SchemaError("RuleInstance.observed must be an Observation")
        check_tick(self.tick, where="RuleInstance.tick")
        canon.check_strictly_ascending(
            self.evidence, lambda e: e.sort_key(), where="RuleInstance.evidence"
        )
        for license_id in self.license_ids:
            require_id(license_id, LicenseId, where="RuleInstance.license_ids")
        _require_sorted_ids(self.license_ids, where="RuleInstance.license_ids")
        if self.observed is Observation.OBSERVED and (self.license_ids or not self.evidence):
            raise SchemaError(
                "RuleInstance: an OBSERVED instance cites evidence and no licences"
            )
        if self.observed is Observation.LICENSED and (self.evidence or not self.license_ids):
            raise SchemaError(
                "RuleInstance: a LICENSED instance cites licences and no evidence"
            )
        if self.ghost and self.observed is not Observation.LICENSED:
            raise SchemaError("RuleInstance: a GHOST-headed instance is always LICENSED")

    @classmethod
    def mint(
        cls,
        rule_id: RuleId,
        rule_version: str,
        head: FactHash,
        body: tuple[FactHash, ...],
        blockers: tuple[int, ...],
        observed: Observation,
        tick: Tick,
        evidence: tuple[EvidenceRef, ...] = (),
        license_ids: tuple[LicenseId, ...] = (),
        ghost: bool = False,
    ) -> Self:
        payload = _instance_payload(rule_id, head, body, evidence, license_ids)
        return cls(
            instance_id=InstanceId.mint(payload),
            rule_id=rule_id,
            rule_version=rule_version,
            head=head,
            body=body,
            blockers=blockers,
            observed=observed,
            tick=tick,
            evidence=evidence,
            license_ids=license_ids,
            ghost=ghost,
        )

    @property
    def mask(self) -> int:
        """The union of the blocker terms. Rendered, never compared as a value."""
        value = 0
        for term in self.blockers:
            value |= term
        return value

    def identity_bytes(self) -> bytes:
        return _instance_payload(
            self.rule_id, self.head, self.body, self.evidence, self.license_ids
        )

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(canon.u64(m) for m in self.blockers),
                _id_seq(self.body),
                canon.ordered_seq(e.canonical_bytes() for e in self.evidence),
                canon.boolean(self.ghost),
                canon.ascii_text(self.head),
                canon.ascii_text(self.instance_id),
                _id_seq(self.license_ids),
                canon.ascii_text(str(self.observed)),
                canon.ascii_text(self.rule_id),
                canon.ascii_text(self.rule_version),
                canon.u32(self.tick),
            )
        )

    def verify_id(self) -> bool:
        return self.instance_id == InstanceId.mint(self.identity_bytes())


def _instance_payload(
    rule_id: RuleId,
    head: FactHash,
    body: tuple[FactHash, ...],
    evidence: tuple[EvidenceRef, ...],
    license_ids: tuple[LicenseId, ...],
) -> bytes:
    """body, evidence event ids, head, licence ids, rule id.

    The blocker masks are excluded on purpose: masks are a function of the control
    catalog, and including them would make an instance's id change when an unrelated
    control is appended to the catalog, which the cut-stability property forbids.
    """
    return b"".join(
        (
            _id_seq(body),
            _id_seq(tuple(str(e.event_id) for e in evidence)),
            canon.ascii_text(head),
            _id_seq(license_ids),
            canon.ascii_text(rule_id),
        )
    )


# ---------------------------------------------------------------------------
# 8. Licence
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Licence(Canonical):
    """Permission to instantiate silent instances of a rule over an interval.

    A `BLIND` licence carries a reason code and no witness. It is never an observation and
    must never be rendered as one: it records that for this span nobody could have seen.
    A `SUPPRESSED` licence carries the two bracketing record ids as witness, which is a
    statement about a sequence discontinuity, not a claim that anything was tampered with.
    """

    ID_KIND: ClassVar[str] = "lic"

    license_id: LicenseId
    source_id: SourceId
    t0_ns: Nanos
    t1_ns: Nanos
    basis: LicenceBasis
    reason: str
    witness: tuple[EventId, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.license_id, LicenseId, where="Licence.license_id")
        require_id(self.source_id, SourceId, where="Licence.source_id")
        Interval(self.t0_ns, self.t1_ns)
        if not isinstance(self.basis, LicenceBasis):
            raise SchemaError("Licence.basis must be a LicenceBasis")
        if not self.reason:
            raise SchemaError("Licence.reason is mandatory; a licence without one is unexplained")
        for event_id in self.witness:
            require_id(event_id, EventId, where="Licence.witness")
        _require_sorted_ids(self.witness, where="Licence.witness")
        if self.basis is LicenceBasis.SUPPRESSED and not self.witness:
            raise SchemaError("Licence: a SUPPRESSED licence carries its bracketing witness")
        if self.basis is not LicenceBasis.SUPPRESSED and self.witness:
            raise SchemaError(
                f"Licence: a {self.basis} licence carries a reason and no witness"
            )

    @classmethod
    def mint(
        cls,
        source_id: SourceId,
        interval: Interval,
        basis: LicenceBasis,
        reason: str,
        witness: tuple[EventId, ...] = (),
    ) -> Self:
        payload = _licence_payload(basis, reason, source_id, interval)
        return cls(
            license_id=LicenseId.mint(payload),
            source_id=source_id,
            t0_ns=interval.t0_ns,
            t1_ns=interval.t1_ns,
            basis=basis,
            reason=reason,
            witness=witness,
        )

    @property
    def interval(self) -> Interval:
        return Interval(self.t0_ns, self.t1_ns)

    def identity_bytes(self) -> bytes:
        return _licence_payload(self.basis, self.reason, self.source_id, self.interval)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ascii_text(str(self.basis)),
                canon.ascii_text(self.license_id),
                canon.utf8_text(self.reason),
                canon.ascii_text(self.source_id),
                canon.i64(self.t0_ns),
                canon.i64(self.t1_ns),
                _id_seq(self.witness),
            )
        )

    def verify_id(self) -> bool:
        return self.license_id == LicenseId.mint(self.identity_bytes())

    def sort_key(self) -> tuple[str, int, int]:
        """Licences are ordered by (source_id, t0_ns, t1_ns) in every artifact."""
        return (str(self.source_id), self.t0_ns, self.t1_ns)


def _licence_payload(
    basis: LicenceBasis, reason: str, source_id: SourceId, interval: Interval
) -> bytes:
    """basis, reason, source_id, t0_ns, t1_ns. The witness is excluded.

    Two licences over the same span for the same reason are one licence, whichever
    records happened to bracket them, so the witness cannot be part of the identity.
    """
    return b"".join(
        (
            canon.ascii_text(str(basis)),
            canon.utf8_text(reason),
            canon.ascii_text(source_id),
            canon.i64(interval.t0_ns),
            canon.i64(interval.t1_ns),
        )
    )


# ---------------------------------------------------------------------------
# 9. BlindWindow
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BlindWindow(Canonical):
    """A maximal half-open interval over which a source's verdict is BLIND or SUPPRESSED.

    `LIVE` is rejected by construction: a window with a `LIVE` verdict is not a blind
    window, and allowing one would make the licensing condition readable two ways.
    """

    ID_KIND: ClassVar[str] = "bw"

    window_id: WindowId
    source_id: SourceId
    t0_ns: Nanos
    t1_ns: Nanos
    verdict: LivenessVerdict
    reason: str

    def __post_init__(self) -> None:
        require_id(self.window_id, WindowId, where="BlindWindow.window_id")
        require_id(self.source_id, SourceId, where="BlindWindow.source_id")
        Interval(self.t0_ns, self.t1_ns)
        if self.verdict is LivenessVerdict.LIVE:
            raise SchemaError("BlindWindow: a LIVE interval is not a blind window")
        if not isinstance(self.verdict, LivenessVerdict):
            raise SchemaError("BlindWindow.verdict must be a LivenessVerdict")
        if not self.reason:
            raise SchemaError("BlindWindow.reason is mandatory")

    @classmethod
    def mint(
        cls,
        source_id: SourceId,
        interval: Interval,
        verdict: LivenessVerdict,
        reason: str,
    ) -> Self:
        payload = b"".join(
            (
                canon.utf8_text(reason),
                canon.ascii_text(source_id),
                canon.i64(interval.t0_ns),
                canon.i64(interval.t1_ns),
                canon.ascii_text(str(verdict)),
            )
        )
        return cls(
            window_id=WindowId.mint(payload),
            source_id=source_id,
            t0_ns=interval.t0_ns,
            t1_ns=interval.t1_ns,
            verdict=verdict,
            reason=reason,
        )

    @property
    def interval(self) -> Interval:
        return Interval(self.t0_ns, self.t1_ns)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.utf8_text(self.reason),
                canon.ascii_text(self.source_id),
                canon.i64(self.t0_ns),
                canon.i64(self.t1_ns),
                canon.ascii_text(str(self.verdict)),
                canon.ascii_text(self.window_id),
            )
        )

    def sort_key(self) -> tuple[str, int, int]:
        return (str(self.source_id), self.t0_ns, self.t1_ns)


# ---------------------------------------------------------------------------
# 10. ThresholdLiteral
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThresholdLiteral(Canonical):
    """The proposition `control k is set to at least level l`.

    `rank` is position in the canonical order; `bit` is position in the append-only lock.
    They are different things and are never used for each other's job: rank orders, ties
    and prints, while bit only ever sets or tests a mask. A mask value never enters a
    sort key that feeds an output path.
    """

    ID_KIND: ClassVar[str] = "lit"

    control_id: ControlId
    level: int
    bit: int
    rank: int

    def __post_init__(self) -> None:
        require_id(self.control_id, ControlId, where="ThresholdLiteral.control_id")
        check_level(self.level, where="ThresholdLiteral.level")
        if self.level < 1:
            raise SchemaError("ThresholdLiteral.level starts at 1; level 0 asserts nothing")
        canon.u8(self.bit)
        if self.bit >= 64:
            raise SchemaError(
                f"ThresholdLiteral.bit {self.bit} is outside the 64-bit mask width",
                code="E-LIMIT-COUNT",
            )
        canon.u16(self.rank)

    @property
    def literal_id(self) -> LiteralId:
        return LiteralId.of(self.control_id, self.level)

    @property
    def order_key(self) -> tuple[bytes, int]:
        """The canonical order of section 25: control_id bytes, then level, both ascending.

        History-independent by construction: appending a control never reorders two
        pre-existing literals, it only inserts between them.
        """
        return (self.control_id.snake.encode("utf-8"), self.level)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.u8(self.bit),
                canon.ascii_text(self.control_id),
                canon.u8(self.level),
                canon.u16(self.rank),
            )
        )


# ---------------------------------------------------------------------------
# 11. Corridor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Corridor(Canonical):
    """An irreducible clause over threshold literals that every sufficient cut satisfies.

    Under the slice narrowing every blocker term has popcount one, so a corridor is a
    plain OR of literals and a cut hits it when it contains at least one of them.
    """

    ID_KIND: ClassVar[str] = "cor"

    corridor_id: CorridorId
    atom_ranks: tuple[int, ...]
    mask: int

    def __post_init__(self) -> None:
        require_id(self.corridor_id, CorridorId, where="Corridor.corridor_id")
        for rank in self.atom_ranks:
            canon.u16(rank)
        canon.check_strictly_ascending(
            self.atom_ranks, lambda r: r, where="Corridor.atom_ranks"
        )
        canon.mask_hex(self.mask)

    @classmethod
    def mint(cls, atom_ranks: tuple[int, ...], mask: int) -> Self:
        return cls(
            corridor_id=CorridorId.mint(canon.leb128_seq(atom_ranks)),
            atom_ranks=atom_ranks,
            mask=mask,
        )

    def identity_bytes(self) -> bytes:
        """LEB128(len) then LEB128 of each ascending rank. The mask is not in the preimage.

        The corridor is the set of literals; the mask is that set rendered under one
        particular bit lock. Hashing the mask would make a corridor id change when an
        unrelated control shifted a bit, which the cut-stability property forbids.
        """
        return canon.leb128_seq(self.atom_ranks)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(canon.u16(r) for r in self.atom_ranks),
                canon.ascii_text(self.corridor_id),
                canon.u64(self.mask),
            )
        )

    def verify_id(self) -> bool:
        return self.corridor_id == CorridorId.mint(self.identity_bytes())


# ---------------------------------------------------------------------------
# 12. Cut
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Cut(Canonical):
    """A set of threshold literals asserted true; the object a certificate is about.

    `cardinality` is the number of RAISED CONTROLS, never the number of literals. The
    distinction is load-bearing: raising one control to level three puts three literals in
    the mask and costs one control, and reporting three would overstate what was asked of
    the operator.
    """

    ID_KIND: ClassVar[str] = "cut"

    atoms: tuple[ThresholdLiteral, ...]
    cardinality: int
    mask: int
    minimality: Minimality

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(self.atoms, lambda a: a.rank, where="Cut.atoms")
        canon.u8(self.cardinality)
        canon.mask_hex(self.mask)
        if not isinstance(self.minimality, Minimality):
            raise SchemaError("Cut.minimality must be a Minimality")
        self._check_upward_closed()
        raised = {str(a.control_id) for a in self.atoms}
        if self.cardinality != len(raised):
            raise SchemaError(
                f"Cut.cardinality {self.cardinality} is not the number of raised controls "
                f"({len(raised)}); cardinality counts controls, never literals"
            )

    def _check_upward_closed(self) -> None:
        """Raising a control to level L implies levels 1..L-1 are also asserted."""
        by_control: dict[str, list[int]] = {}
        for literal in self.atoms:
            by_control.setdefault(str(literal.control_id), []).append(literal.level)
        for control_id in sorted(by_control):
            levels = sorted(by_control[control_id])
            if levels != list(range(1, len(levels) + 1)):
                raise SchemaError(
                    f"Cut: {control_id} levels {levels} are not upward-closed from 1",
                    code="E-CUT-CLOSURE",
                )

    @classmethod
    def mint(cls, atoms: tuple[ThresholdLiteral, ...], minimality: Minimality) -> Self:
        mask = 0
        for literal in atoms:
            mask |= 1 << literal.bit
        cardinality = len({str(a.control_id) for a in atoms})
        return cls(atoms=atoms, cardinality=cardinality, mask=mask, minimality=minimality)

    @property
    def cut_id(self) -> CutId:
        return CutId.mint(self.identity_bytes())

    def identity_bytes(self) -> bytes:
        """The literal ids in rank order. Neither the mask nor the minimality claim is in
        the preimage: minimality is a statement about the search, not about the cut."""
        return canon.ordered_seq(canon.ascii_text(a.literal_id) for a in self.atoms)

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(a.canonical_bytes() for a in self.atoms),
                canon.u8(self.cardinality),
                canon.u64(self.mask),
                canon.ascii_text(str(self.minimality)),
            )
        )

    def compare_key(self) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
        """The tie-break of the cut section, as a key: fewer controls, then the rank
        vector, then the level vector, each smallest first."""
        return (
            self.cardinality,
            tuple(a.rank for a in self.atoms),
            tuple(a.level for a in self.atoms),
        )


# ---------------------------------------------------------------------------
# 13. Certificate
# ---------------------------------------------------------------------------

_CERT_SCOPE_MEMBERS: Final[tuple[str, ...]] = (
    "attacker",
    "bundle",
    "controls",
    "er",
    "goal",
    "liveness",
    "rules",
)


@dataclass(frozen=True, slots=True)
class Certificate(Canonical):
    """The content-addressed artifact the reference kernel emits and the checker checks.

    This layer owns the certificate's *frame*: the schema triple, the seven-member scope
    that travels with every rendering, the input digests, and the declaration of which
    digest algorithm actually produced them. It does not own the verdict, the cut, the
    witnesses or the corridor database; those belong to the stages that compute them and
    arrive here as already-canonical byte sections, each under its member name.

    `hash_algorithm` is a required member and is checked against what this build computes.
    That is the mechanism by which the blake2b-for-blake3 substitution cannot be lost:
    a certificate that does not say which digest it used cannot be constructed at all.
    """

    ID_KIND: ClassVar[str] = "cert"

    schema_v: str
    min_checker: str
    profile: str
    scope: tuple[tuple[str, str], ...]
    inputs: tuple[tuple[str, str], ...]
    body_sections: tuple[tuple[str, bytes], ...] = ()
    hash_algorithm: str = canon.HASH_ALGORITHM
    hash_substitution_note: str = canon.HASH_SUBSTITUTION_NOTE

    def __post_init__(self) -> None:
        if self.hash_algorithm != canon.HASH_ALGORITHM:
            raise SchemaError(
                f"Certificate.hash_algorithm is {self.hash_algorithm!r} but this build "
                f"computes {canon.HASH_ALGORITHM!r}",
                code="E-HASH-ALGO",
            )
        if self.hash_substitution_note != canon.HASH_SUBSTITUTION_NOTE:
            raise SchemaError(
                "Certificate.hash_substitution_note must carry the declared substitution note",
                code="E-HASH-ALGO",
            )
        _check_attrs(self.scope, where="Certificate.scope")
        _check_attrs(self.inputs, where="Certificate.inputs")
        present = tuple(k for k, _ in self.scope)
        if present != _CERT_SCOPE_MEMBERS:
            missing = tuple(m for m in _CERT_SCOPE_MEMBERS if m not in present)
            unknown = tuple(m for m in present if m not in _CERT_SCOPE_MEMBERS)
            raise SchemaError(
                f"Certificate.scope must be exactly {len(_CERT_SCOPE_MEMBERS)} members; "
                f"missing={missing} unknown={unknown}",
                code="VRD-005",
            )
        if dict(self.scope)["attacker"] != "non-adaptive":
            raise SchemaError(
                "Certificate.scope.attacker must be 'non-adaptive', the only value v1 accepts",
                code="VRD-005",
            )
        section_names = tuple(name for name, _ in self.body_sections)
        canon.check_strictly_ascending(
            section_names, canon.byte_order_key, where="Certificate.body_sections"
        )
        for name, blob_bytes in self.body_sections:
            if not isinstance(blob_bytes, bytes):
                raise SchemaError(f"Certificate.body_sections[{name!r}] must be bytes")

    @property
    def cert_id(self) -> CertId:
        return CertId.mint(self.canonical_bytes())

    @property
    def cert_hash(self) -> str:
        """The recomputable digest over the whole canonical body. No field is carved out."""
        return canon.hash_ref(type(self).ID_KIND, self.canonical_bytes())

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ordered_seq(
                    canon.ascii_text(name) + canon.blob(value)
                    for name, value in self.body_sections
                ),
                canon.ascii_text(self.hash_algorithm),
                canon.utf8_text(self.hash_substitution_note),
                canon.pairs(self.inputs),
                canon.ascii_text(self.min_checker),
                canon.ascii_text(self.profile),
                canon.ascii_text(self.schema_v),
                canon.pairs(self.scope),
            )
        )


# ---------------------------------------------------------------------------
# 14. GroundTruth
# ---------------------------------------------------------------------------

_TRUTH_ID: Final[re.Pattern[str]] = re.compile(r"\Atr_[0-9a-f]{16}\Z")


@dataclass(frozen=True, slots=True)
class GroundTruth(Canonical):
    """What the generator knows about one occurrence. ORACLE CHANNEL ONLY.

    No stage from ingest onwards may read this type. It exists so that an oracle can
    answer, after the fact, what a run's telemetry was a degraded view of. A hard rule of
    section 57.8: no arrow crosses from here into the kernel path. Putting these fields on
    a bundle record instead is the label leak that ingest rejects outright.
    """

    ID_KIND: ClassVar[str] = "truth"

    truth_id: str
    sim_tick: Tick
    kind: TruthKind
    origin: TruthOrigin
    actor_ref: str
    observable: bool
    producing_sources: tuple[SourceId, ...] = ()
    event_id: EventId | None = None
    chain_id: str | None = None
    step_k: int | None = None
    step_action: str | None = None
    subject_ref: str | None = None
    true_transition: tuple[tuple[str, str], ...] = ()
    suppressed_by: str | None = None

    def __post_init__(self) -> None:
        if _TRUTH_ID.match(self.truth_id) is None:
            raise SchemaError(
                f"GroundTruth.truth_id must match tr_<16hex>, got {self.truth_id!r}"
            )
        check_tick(self.sim_tick, where="GroundTruth.sim_tick")
        if not isinstance(self.kind, TruthKind):
            raise SchemaError("GroundTruth.kind must be a TruthKind")
        if not isinstance(self.origin, TruthOrigin):
            raise SchemaError("GroundTruth.origin must be a TruthOrigin")
        if not isinstance(self.observable, bool):
            raise SchemaError("GroundTruth.observable must be a bool")
        if self.event_id is not None:
            require_id(self.event_id, EventId, where="GroundTruth.event_id")
        for source_id in self.producing_sources:
            require_id(source_id, SourceId, where="GroundTruth.producing_sources")
        _require_sorted_ids(self.producing_sources, where="GroundTruth.producing_sources")
        if self.step_k is not None:
            canon.u16(self.step_k)
        _check_attrs(self.true_transition, where="GroundTruth.true_transition")
        unobserved = self.kind is TruthKind.ATTACK_UNOBSERVED
        if unobserved and (self.event_id is not None or self.producing_sources):
            raise SchemaError(
                "GroundTruth: an attack_unobserved annotation names no event and no source"
            )
        if not unobserved and self.event_id is None:
            raise SchemaError("GroundTruth: every observed annotation names its event")

    @classmethod
    def mint_truth_id(cls, payload: bytes) -> str:
        """`tr_<16hex>`. Not a section 57 identifier type; see the module docstring."""
        return "tr_" + canon.digest_hex(cls.ID_KIND, payload, 16)[:16]

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.utf8_text(self.actor_ref),
                _optional(self.chain_id, canon.utf8_text),
                _optional(self.event_id, canon.ascii_text),
                canon.ascii_text(str(self.kind)),
                canon.boolean(self.observable),
                canon.ascii_text(str(self.origin)),
                _id_seq(self.producing_sources),
                canon.u32(self.sim_tick),
                _optional(self.step_action, canon.utf8_text),
                _optional(self.step_k, canon.u16),
                _optional(self.subject_ref, canon.utf8_text),
                _optional(self.suppressed_by, canon.utf8_text),
                canon.pairs(self.true_transition),
                canon.ascii_text(self.truth_id),
            )
        )
