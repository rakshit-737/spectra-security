"""Identifier types and their wire grammar.

Why this module exists: section 57 makes the vocabulary normative over every other
section, and rule 7 of 57.1 requires that passing a `RecordId` where a `FactHash` is
expected be a detectable error rather than a silent success. Python's `NewType` is
erased at runtime, so a `NewType` alone would let a mislabelled string travel the whole
pipeline and land in a certificate. Every identifier here is therefore a distinct `str`
subclass: it sorts, serialises and compares like the ASCII string it is on the wire,
while `isinstance` still separates the types, so `require_id` can reject a wrong-typed
value at the call that receives it.

Grammar source: `docs/prompt/part2/57-glossary.md` section 57.2 (ABNF) and 57.3 (digest
construction), with the concept-to-id-type binding taken from `docs/vocab.toml`.

DIVERGENCE FROM THE OPERATIVE SLICE SPEC, recorded here because downstream stages will
hit it. The operative spec's `data_contracts` section lists shortened, undomained id
forms for the slice: `fa:<32hex>` for a fact key, `ri:<32hex>` for a rule instance,
`lc:<16hex>` for a licence, `en:<32hex>` for an entity and `c:<32hex>` for a corridor.
Section 57.2 is normative over every other section and assigns those concepts
`fh:` h256, `in:` h256, `lic:` h256, `en:<kind>:` h128 and `cor:` h256; 57.2's
certificate width rule additionally makes any h128 inside a certificate a hard
rejection, which the slice's `lc:<16hex>` would trip on sight. This module implements
section 57. Stages that quote the operative spec's short forms must translate at their
own boundary, not here.

No wall clock is read anywhere in this module.
"""

from __future__ import annotations

import re
from typing import ClassVar, Final, Self

from spectra_core import canon
from spectra_core.errors import IdentifierError, IdentifierTypeError, IdentifierWidthError

__all__ = [
    "ENTITY_KINDS",
    "PREFIX_TO_TYPE",
    "AssignmentId",
    "BundleId",
    "CertId",
    "CollectorId",
    "ControlId",
    "CorridorId",
    "CutId",
    "DegradationId",
    "DimensionId",
    "EntityId",
    "EntityKind",
    "EventId",
    "FactHash",
    "FlagId",
    "HypergraphId",
    "HypothesisId",
    "InstanceId",
    "Level",
    "LicenseId",
    "LiteralId",
    "OperatorId",
    "OracleId",
    "RecordId",
    "RuleId",
    "RunId",
    "ScenarioId",
    "SourceId",
    "SpectraId",
    "StateId",
    "Tick",
    "TransitionId",
    "WindowId",
    "check_level",
    "check_snake",
    "check_tick",
    "parse_id",
    "reject_run_local_in_certificate",
    "require_id",
]


# ---------------------------------------------------------------------------
# 57.2 primitives
# ---------------------------------------------------------------------------

# `snake = lower *( lower / DIGIT / "_" )`, max 48 octets, US-ASCII, lowercase only.
_SNAKE: Final = re.compile(r"\A[a-z][a-z0-9_]{0,47}\Z")
# `u16 = "0" / ( %x31-39 *4DIGIT )`, no leading zeros, value bounded below.
_U16: Final = re.compile(r"\A(?:0|[1-9][0-9]{0,4})\Z")
# `level = "0" / ( %x31-39 [ DIGIT ] )`, 0..99, no leading zeros.
_LEVEL: Final = re.compile(r"\A(?:0|[1-9][0-9]?)\Z")
_H128: Final = re.compile(r"\A[0-9a-f]{32}\Z")
_H256: Final = re.compile(r"\A[0-9a-f]{64}\Z")

#: Table C, `EntityKind`, exactly twelve members. A closed set: new members are added in
#: section 57 or not at all.
ENTITY_KINDS: Final[tuple[str, ...]] = (
    "account",
    "api_client",
    "credential",
    "file",
    "host",
    "key",
    "netflow",
    "process",
    "resource",
    "service",
    "session",
    "user",
)

#: Level is the strictness setting of one control. `Level` and `Tick` carry no identity
#: of their own, so they are plain integers with a checked constructor rather than
#: string subclasses; the check is what makes a bad value loud at the boundary.
Level = int
Tick = int

#: The tick of section 57.3 rule 7 is u64 nanoseconds since the scenario epoch. The
#: operative slice spec uses a *different* quantity under the same word: a u32 index,
#: `t_evt_ns // 1_000_000_000`. `spectra_core.model.tick_of` computes the slice's index;
#: `check_tick` here only enforces the shared property that a tick is a non-negative
#: integer, so both readings pass through it without one silently becoming the other.
_TICK_MAX: Final = (1 << 64) - 1
_LEVEL_MAX: Final = 99
_U16_MAX: Final = 65535


def check_snake(value: str, *, where: str) -> str:
    """Return `value` if it is a 57.2 `snake`, else raise. Used by every symbolic id."""
    if not isinstance(value, str) or _SNAKE.match(value) is None:
        raise IdentifierError(
            f"{where}: not a section 57.2 snake (lowercase ASCII, <= 48 octets): {value!r}"
        )
    return value


def check_level(value: int, *, where: str) -> Level:
    """Return `value` if it is a 57.2 `level`. Rejects bools, which are ints in Python."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise IdentifierError(f"{where}: level must be an int, got {type(value).__name__}")
    if not 0 <= value <= _LEVEL_MAX:
        raise IdentifierError(f"{where}: level out of range 0..{_LEVEL_MAX}: {value}")
    return value


def check_tick(value: int, *, where: str) -> Tick:
    """Return `value` if it is a non-negative u64 tick. Rejects bools and floats."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise IdentifierError(f"{where}: tick must be an int, got {type(value).__name__}")
    if not 0 <= value <= _TICK_MAX:
        raise IdentifierError(f"{where}: tick out of u64 range: {value}")
    return value


def _check_u16(value: str, *, where: str) -> str:
    if _U16.match(value) is None or int(value) > _U16_MAX:
        raise IdentifierError(f"{where}: not a section 57.2 u16: {value!r}")
    return value


# ---------------------------------------------------------------------------
# The identifier hierarchy
# ---------------------------------------------------------------------------


class SpectraId(str):
    """Base of every identifier type.

    Subclassing `str` rather than wrapping one is deliberate: identifiers are compared,
    sorted and serialised constantly, and section 58's ordering rule wants bytewise
    ascending order. These values are US-ASCII by construction, so Python's code-point
    ordering is the bytewise ordering, and a sorted list of ids needs no key function.
    The nominal type survives because the subclass does.
    """

    __slots__ = ()

    #: Wire prefix including the trailing colon, e.g. `"rc:"`.
    PREFIX: ClassVar[str] = ""
    #: True when 57.2 permits this id inside a certificate. h128 ids are run-local and
    #: are a hard rejection there; see `reject_run_local_in_certificate`.
    CERTIFIABLE: ClassVar[bool] = False

    def __new__(cls, value: str) -> Self:
        if cls is SpectraId:
            raise IdentifierError("SpectraId is abstract; construct a concrete id type")
        if not isinstance(value, str):
            raise IdentifierError(
                f"{cls.__name__}: expected str, got {type(value).__name__}"
            )
        cls._check(value)
        return super().__new__(cls, value)

    @classmethod
    def _check(cls, value: str) -> None:
        raise NotImplementedError

    @classmethod
    def digest_kind(cls) -> str:
        """The 57.3 domain-separation `kind`: the prefix without its colon."""
        return cls.PREFIX[:-1]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({str.__repr__(self)})"


class _HashId(SpectraId):
    """An identifier whose body is a hex digest minted by 57.3 `DIGEST(kind, payload)`."""

    __slots__ = ()

    #: Number of digest octets rendered: 32 for h256, 16 for h128 (a prefix, never a fold).
    OCTETS: ClassVar[int] = 32

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"{cls.__name__}: missing prefix {cls.PREFIX!r}: {value!r}")
        body = value[len(cls.PREFIX) :]
        pattern = _H256 if cls.OCTETS == 32 else _H128
        if pattern.match(body) is None:
            raise IdentifierError(
                f"{cls.__name__}: body is not {cls.OCTETS * 2} lowercase hex digits: {value!r}"
            )

    @classmethod
    def mint(cls, payload: bytes) -> Self:
        """Mint from a canonical payload using the single 57.3 digest construction."""
        return cls(cls.PREFIX + canon.digest_hex(cls.digest_kind(), payload, cls.OCTETS))


class _H256Id(_HashId):
    __slots__ = ()
    OCTETS: ClassVar[int] = 32
    CERTIFIABLE: ClassVar[bool] = True


class _H128Id(_HashId):
    __slots__ = ()
    OCTETS: ClassVar[int] = 16
    CERTIFIABLE: ClassVar[bool] = False


class _SnakeId(SpectraId):
    """An authored symbolic identifier: prefix plus one 57.2 `snake`."""

    __slots__ = ()
    CERTIFIABLE: ClassVar[bool] = True

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"{cls.__name__}: missing prefix {cls.PREFIX!r}: {value!r}")
        check_snake(value[len(cls.PREFIX) :], where=cls.__name__)

    @classmethod
    def of(cls, snake: str) -> Self:
        """Build from the bare snake, e.g. `SourceId.of("iam_audit")`."""
        return cls(cls.PREFIX + check_snake(snake, where=cls.__name__))

    @property
    def snake(self) -> str:
        """The authored name without the prefix."""
        return str(self)[len(type(self).PREFIX) :]


# --- integrity-critical, h256, MAY appear in a certificate -----------------


class RecordId(_H256Id):
    """One serialized telemetry line as ingested, digested over its exact pre-parse bytes."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "rc:"


class BundleId(_H256Id):
    """The immutable, ordered, content-addressed set of records for one run's input."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "bn:"


class FactHash(_H256Id):
    """A ground, time-indexed predicate instance; the OR-nodes of the hypergraph."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "fh:"


class InstanceId(_H256Id):
    """One grounding of one rule to specific facts; the AND-nodes of the hypergraph."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "in:"


class LicenseId(_H256Id):
    """Permission to instantiate silent instances of a rule over an interval.

    A licence is never an observation. Nothing in this package may render one as one.
    """

    __slots__ = ()
    PREFIX: ClassVar[str] = "lic:"


class CutId(_H256Id):
    """A set of threshold literals asserted true; the object a certificate is about."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "cut:"


class CorridorId(_H256Id):
    """An irreducible clause over threshold literals that every sufficient cut satisfies."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "cor:"


class HypothesisId(_H256Id):
    """One derivation of one goal fact: its instances, its licences, its realizability."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "hy:"


class HypergraphId(_H256Id):
    """The provenance structure of one grounding."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "hg:"


class RunId(_H256Id):
    """The hashed core of one execution."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "run:"


class CertId(_H256Id):
    """The content-addressed proof artifact the reference kernel emits."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "cert:"


# --- run-local, h128, MUST NOT appear in a certificate ---------------------


class EventId(_H128Id):
    """The generator's private identity for an occurrence.

    Section 57.8: this travels the oracle channel only. The grounder, the liveness stage
    and the checker must not read it. Evidence cites `RecordId`.
    """

    __slots__ = ()
    PREFIX: ClassVar[str] = "ev:"


class TransitionId(_H128Id):
    """An evidence-bound change of one entity's state within one dimension at one tick."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "tr:"


class WindowId(_H128Id):
    """A maximal half-open interval over which a source's verdict is BLIND or SUPPRESSED."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "bw:"


class AssignmentId(_H128Id):
    """A total map from every control to one level."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "asg:"


class DegradationId(_H128Id):
    """An ordered list of (operator, parameters, seed) defining one matrix cell."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "deg:"


# --- entity: the one composite form ----------------------------------------

EntityKind = str


class EntityId(SpectraId):
    """`en:` kind `:` h128, with `kind` drawn from the closed twelve of Table C.

    The kind is in the identifier rather than beside it so that a mis-joined entity is
    visible in any artifact that carries the id, without a lookup.
    """

    __slots__ = ()
    PREFIX: ClassVar[str] = "en:"
    CERTIFIABLE: ClassVar[bool] = False

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"EntityId: missing prefix 'en:': {value!r}")
        rest = value[len(cls.PREFIX) :]
        kind, sep, body = rest.partition(":")
        if not sep:
            raise IdentifierError(f"EntityId: missing kind separator: {value!r}")
        if kind not in ENTITY_KINDS:
            raise IdentifierError(
                f"EntityId: kind {kind!r} is not one of the closed twelve: {value!r}"
            )
        if _H128.match(body) is None:
            raise IdentifierError(f"EntityId: body is not 32 lowercase hex digits: {value!r}")

    @classmethod
    def mint(cls, kind: str, payload: bytes) -> Self:
        if kind not in ENTITY_KINDS:
            raise IdentifierError(f"EntityId.mint: unknown entity kind {kind!r}")
        return cls(f"en:{kind}:{canon.digest_hex(cls.digest_kind(), payload, 16)}")

    @property
    def kind(self) -> EntityKind:
        return str(self).split(":", 2)[1]


# --- symbolic, authored -----------------------------------------------------


class SourceId(_SnakeId):
    """A declared telemetry origin with a class, a format and a liveness contract."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "src:"


class ControlId(_SnakeId):
    """A declared, levelled security control in the catalog."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "ctl:"


class RuleId(_SnakeId):
    """One authored implication in the rule table."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "rl:"


class DimensionId(_SnakeId):
    """One of the ten security dimensions."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "dim:"


class FlagId(_SnakeId):
    """A named boolean recording a degraded condition of a run."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "flag:"


class OperatorId(_SnakeId):
    """One pure, seeded transform on a bundle."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "op:"


class OracleId(_SnakeId):
    """An independently implemented judge of a property."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "orc:"


class CollectorId(SpectraId):
    """`col:` snake `@` u16 — the code that reads one source's native format."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "col:"
    CERTIFIABLE: ClassVar[bool] = True

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"CollectorId: missing prefix 'col:': {value!r}")
        name, sep, version = value[len(cls.PREFIX) :].partition("@")
        if not sep:
            raise IdentifierError(f"CollectorId: missing '@' version suffix: {value!r}")
        check_snake(name, where="CollectorId")
        _check_u16(version, where="CollectorId")

    @classmethod
    def of(cls, snake: str, version: int) -> Self:
        check_snake(snake, where="CollectorId")
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= _U16_MAX:
            raise IdentifierError(f"CollectorId: version out of u16 range: {version!r}")
        return cls(f"col:{snake}@{version}")


class ScenarioId(SpectraId):
    """`sc:` snake `@` u16 — the u16 is the scenario schema version, hyphens are illegal."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "sc:"
    CERTIFIABLE: ClassVar[bool] = True

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"ScenarioId: missing prefix 'sc:': {value!r}")
        name, sep, version = value[len(cls.PREFIX) :].partition("@")
        if not sep:
            raise IdentifierError(f"ScenarioId: missing '@' version suffix: {value!r}")
        check_snake(name, where="ScenarioId")
        _check_u16(version, where="ScenarioId")

    @classmethod
    def of(cls, snake: str, version: int) -> Self:
        check_snake(snake, where="ScenarioId")
        if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= _U16_MAX:
            raise IdentifierError(f"ScenarioId: version out of u16 range: {version!r}")
        return cls(f"sc:{snake}@{version}")


class LiteralId(SpectraId):
    """`lit:` snake `@` level — the proposition `control k is set to at least level l`.

    The snake is the control's snake with no `ctl:` prefix, per 57.2. This is the unit of
    every cut and every blocker mask; the retired word for it is banned by Table D.
    """

    __slots__ = ()
    PREFIX: ClassVar[str] = "lit:"
    CERTIFIABLE: ClassVar[bool] = True

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"LiteralId: missing prefix 'lit:': {value!r}")
        name, sep, level = value[len(cls.PREFIX) :].partition("@")
        if not sep:
            raise IdentifierError(f"LiteralId: missing '@' level suffix: {value!r}")
        check_snake(name, where="LiteralId")
        if _LEVEL.match(level) is None:
            raise IdentifierError(f"LiteralId: not a section 57.2 level: {value!r}")

    @classmethod
    def of(cls, control_id: ControlId, level: int) -> Self:
        """Build from a `ControlId` and a level. Takes the typed control, not a bare str,
        so that a source id or a rule id cannot be spliced into a literal by accident."""
        require_id(control_id, ControlId, where="LiteralId.of")
        return cls(f"lit:{control_id.snake}@{check_level(level, where='LiteralId.of')}")

    @property
    def control(self) -> ControlId:
        return ControlId("ctl:" + str(self)[len(self.PREFIX) :].split("@", 1)[0])

    @property
    def level(self) -> Level:
        return int(str(self).rsplit("@", 1)[1])


class StateId(SpectraId):
    """`st:` snake `:` snake — dimension then state, lowercase, never SCREAMING_SNAKE."""

    __slots__ = ()
    PREFIX: ClassVar[str] = "st:"
    CERTIFIABLE: ClassVar[bool] = True

    @classmethod
    def _check(cls, value: str) -> None:
        if not value.startswith(cls.PREFIX):
            raise IdentifierError(f"StateId: missing prefix 'st:': {value!r}")
        dimension, sep, state = value[len(cls.PREFIX) :].partition(":")
        if not sep:
            raise IdentifierError(f"StateId: missing dimension/state separator: {value!r}")
        check_snake(dimension, where="StateId dimension")
        check_snake(state, where="StateId state")

    @classmethod
    def of(cls, dimension: str, state: str) -> Self:
        check_snake(dimension, where="StateId dimension")
        check_snake(state, where="StateId state")
        return cls(f"st:{dimension}:{state}")


# ---------------------------------------------------------------------------
# Registry, prefix uniqueness, and the wrong-type guard
# ---------------------------------------------------------------------------

_ID_TYPES: Final[tuple[type[SpectraId], ...]] = (
    AssignmentId,
    BundleId,
    CertId,
    CollectorId,
    ControlId,
    CorridorId,
    CutId,
    DegradationId,
    DimensionId,
    EntityId,
    EventId,
    FactHash,
    FlagId,
    HypergraphId,
    HypothesisId,
    InstanceId,
    LicenseId,
    LiteralId,
    OperatorId,
    OracleId,
    RecordId,
    RuleId,
    RunId,
    ScenarioId,
    SourceId,
    StateId,
    TransitionId,
    WindowId,
)

#: Wire prefix -> id type. Built once so `parse_id` never guesses.
PREFIX_TO_TYPE: Final[dict[str, type[SpectraId]]] = {t.PREFIX: t for t in _ID_TYPES}


def _assert_prefix_uniqueness() -> None:
    """57.2: no prefix is a prefix of another prefix. Checked at import, not at lint time.

    A violated prefix invariant makes `parse_id` ambiguous, and an ambiguous parse is how
    a wrong-typed id gets into an artifact without anything going red.
    """
    prefixes = sorted(PREFIX_TO_TYPE)
    if len(prefixes) != len(_ID_TYPES):
        raise IdentifierError("duplicate identifier prefix in the id registry")
    for i, outer in enumerate(prefixes):
        for inner in prefixes[i + 1 :]:
            if inner.startswith(outer) or outer.startswith(inner):
                raise IdentifierError(
                    f"identifier prefixes violate 57.2 uniqueness: {outer!r} / {inner!r}"
                )


_assert_prefix_uniqueness()


def require_id[T: SpectraId](value: object, expected: type[T], *, where: str) -> T:
    """Return `value` when it is exactly `expected`, else raise `IdentifierTypeError`.

    This is the runtime half of 57.1 rule 7. Call it at every boundary that accepts an
    identifier from another stage. A bare `str` is rejected as firmly as a sibling id
    type: an unvalidated string is precisely what the nominal types exist to keep out.
    """
    if not isinstance(value, expected):
        got = type(value).__name__
        raise IdentifierTypeError(
            f"{where}: expected {expected.__name__}, got {got} ({value!r})"
        )
    return value


def parse_id(value: str) -> SpectraId:
    """Parse any 57.2 identifier into its own type, chosen by prefix.

    Raises `IdentifierError` on an unknown prefix rather than returning the input, so a
    stage that reads an id from a file cannot end up holding a plain `str`.
    """
    if not isinstance(value, str):
        raise IdentifierError(f"parse_id: expected str, got {type(value).__name__}")
    prefix, sep, _ = value.partition(":")
    if not sep:
        raise IdentifierError(f"parse_id: no prefix separator in {value!r}")
    id_type = PREFIX_TO_TYPE.get(prefix + ":")
    if id_type is None:
        raise IdentifierError(f"parse_id: unknown identifier prefix {prefix + ':'!r}")
    return id_type(value)


def reject_run_local_in_certificate(value: SpectraId, *, where: str) -> SpectraId:
    """Enforce 57.2's certificate width rule: an h128 id inside a certificate is a hard
    rejection, not a warning, because integrity-critical ids derive in part from
    untrusted telemetry bytes and 128 truncated bits permits birthday grinding."""
    require_id(value, SpectraId, where=where)
    if not value.CERTIFIABLE:
        raise IdentifierWidthError(
            f"{where}: {type(value).__name__} is run-local and may not appear in a certificate"
        )
    return value
