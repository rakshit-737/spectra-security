"""S1: the declarative rule table, the guard front end, and the blocker masks.

WHAT THIS STAGE OWNS. It reads `config/vs/rules.toml`, the control catalog and the
append-only bit lock, and produces a `RuleTable`: every rule as a `spectra_core.model.Rule`,
every `blocked_when` guard compiled to a DNF over threshold literals and mapped onto a
64-bit blocker mask, every `when` guard compiled to a small total-evaluation AST that S8
calls once per candidate join, and the three digests the certificate binds
(`rules_hash`, `guard_ast_hash`, `rules_text_hash`).

A LITERAL IS `control k is at least level l`. Controls carry ORDERED level names and the
guard writes the level by name; the ordinal comes from the catalog. Level 0 is the weakest
setting and has no literal, because "at least the weakest setting" asserts nothing.

WHY THE BIT TABLE IS RECORDED RATHER THAN RECOMPUTED. A mask is a set of bit positions and
a bit position means nothing without the table that assigned it. Two catalogs produce two
tables, so a mask compared across them is a comparison of unrelated numbers. Every
`RuleTable` therefore carries the `BitTable` it compiled against and that table's digest,
and `bit` (a position in the append-only lock) is kept strictly separate from `rank` (a
position in the canonical order): rank orders, ties and prints; bit only ever sets or tests
a mask.

THE DIGEST IS SUBSTITUTED AND SAYS SO. The specification names blake3. This reference
implementation computes `spectra_core.canon`'s blake2b-256 and labels it `b2b256:`. No
string written here claims blake3 was computed.

DELETE EFFECTS ARE REJECTED, NOT IGNORED. Facts are append-only. Non-monotonicity is
handled by time-indexing: expiry means a later fact is not derived, never that a fact is
retracted. `_lint_no_delete_effect` rejects any rule carrying a delete, retract, revoke,
withdraw or expire effect, so the property cannot be lost by someone adding a key the
loader would otherwise skip.

NARROWINGS, all deliberate and all loud:
  * C-SLICE-1: every DNF term of `blocked_when` must have popcount 1. A conjunctive term is
    E-VS-BLOCK-CONJ. The subset form of the enabled test stays in the reachability code
    behind an assertion so the narrowing is visible where it matters.
  * `persistence` must be "instant". "sticky" and "until(<expr>)" are deferred and are
    rejected at load rather than silently treated as "instant".
  * The data sort implements exactly the operators the slice's four temporal forms need:
    comparison, boolean structure, saturating add/sub, abs, min, max and `within`. A
    construct outside that set is a syntax error rather than a silent no-op.

No wall clock, no environment read, no randomness and no float anywhere in this module.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final, Self

from spectra_core import canon, model
from spectra_core.errors import GuardError, LimitError, SchemaError
from spectra_core.ids import (
    ControlId,
    DimensionId,
    RuleId,
    SourceId,
    check_snake,
)

__all__ = [
    "BANNED_EFFECT_KEYS",
    "MASK_WIDTH",
    "MAX_DNF_TERMS",
    "SLOT_NAMES",
    "TEMPORAL_OPS",
    "TICK_NS",
    "BitEntry",
    "BitTable",
    "Catalog",
    "CompiledRule",
    "ControlSpec",
    "GuardType",
    "Node",
    "Pattern",
    "RuleTable",
    "Temporal",
    "compile_blocked_when",
    "compile_when",
    "compile_rules",
    "duration_ticks",
    "eval_when",
    "load_bit_table",
    "load_catalog",
    "parse_pattern",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The slice's tick granularity, taken from the foundation so the two cannot drift.
TICK_NS: Final[int] = model.TICK_GRANULARITY_NS

#: Width of the blocker mask. A position at or beyond this is a hard limit failure, never
#: a wrap and never a truncation.
MASK_WIDTH: Final[int] = 64

#: Control-sort DNF ceiling, per the canonicalisation step C8.
MAX_DNF_TERMS: Final[int] = 8

#: Body slots are named by position. Four because a rule body is at most four patterns.
SLOT_NAMES: Final[tuple[str, ...]] = ("a", "b", "c", "d")

#: The temporal operators the slice implements. Everything else in Part II 63 is deferred
#: and is rejected at load rather than accepted and ignored.
TEMPORAL_OPS: Final[tuple[str, ...]] = ("seq", "absence", "distinct", "obligation")

#: Keys that would express a retraction. Rejected outright: see the module docstring.
BANNED_EFFECT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "delete",
        "deletes",
        "delete_when",
        "effect",
        "effects",
        "expire",
        "expires",
        "retract",
        "retracts",
        "revoke",
        "revokes",
        "withdraw",
        "withdraws",
    }
)

#: Effect values that would express a retraction even under an allowed key name.
_BANNED_EFFECT_VALUES: Final[frozenset[str]] = frozenset(
    {"delete", "expire", "retract", "revoke", "withdraw"}
)

#: `persistence` values this slice implements. The other two forms are deferred.
_ALLOWED_PERSISTENCE: Final[frozenset[str]] = frozenset({"instant"})

_PREDICATE: Final[re.Pattern[str]] = re.compile(r"\A[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*\Z")
_RULE_ID: Final[re.Pattern[str]] = re.compile(r"\Ar[0-9]{4}\Z")
_ATTCK: Final[re.Pattern[str]] = re.compile(r"\AT[0-9]{4}(?:\.[0-9]{3})?\Z")

#: Duration units and their nanosecond sizes. `tick` is included so a rule can be written
#: in the quantity the fixpoint actually indexes on.
_DURATION_UNITS: Final[dict[str, int]] = {
    "ns": 1,
    "us": 1_000,
    "ms": 1_000_000,
    "s": 1_000_000_000,
    "m": 60_000_000_000,
    "h": 3_600_000_000_000,
    "tick": TICK_NS,
}

_I64_MIN: Final[int] = -(1 << 63)
_I64_MAX: Final[int] = (1 << 63) - 1


def _saturate(value: int) -> int:
    """Clamp to the i64 range. Arithmetic in a guard saturates; it never wraps or raises."""
    if value < _I64_MIN:
        return _I64_MIN
    if value > _I64_MAX:
        return _I64_MAX
    return value


def duration_ticks(literal: str) -> int:
    """Normalise a duration literal such as `30m` to whole ticks.

    A duration that is not a whole number of ticks is E-SEM-030 rather than a rounding:
    rounding would make the same rule mean two different things at two tick granularities,
    which is exactly what the delta-sensitivity property forbids.
    """
    text = literal.strip()
    match = re.fullmatch(r"([0-9][0-9_]*)([a-z]+)", text)
    if match is None:
        raise GuardError(f"not a duration literal: {literal!r}", code="E-SYN-000")
    magnitude = int(match.group(1).replace("_", ""))
    unit = match.group(2)
    if unit not in _DURATION_UNITS:
        raise GuardError(f"unknown duration unit {unit!r} in {literal!r}", code="E-SYN-000")
    total_ns = magnitude * _DURATION_UNITS[unit]
    if total_ns % TICK_NS:
        raise GuardError(
            f"duration {literal!r} is {total_ns} ns, not a whole number of {TICK_NS} ns ticks",
            code="E-SEM-030",
        )
    return total_ns // TICK_NS


# ---------------------------------------------------------------------------
# The control catalog and the append-only bit lock
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ControlSpec:
    """One levelled control. `levels[0]` is the weakest setting and has no literal."""

    control_id: ControlId
    title: str
    levels: tuple[str, ...]
    dimensions: tuple[DimensionId, ...]
    provenance: str

    def __post_init__(self) -> None:
        if len(self.levels) < 2:
            raise SchemaError(
                f"{self.control_id}: a control needs at least two levels to carry a literal"
            )
        seen: list[str] = []
        for name in self.levels:
            check_snake(name, where=f"{self.control_id} level")
            if name in seen:
                raise SchemaError(f"{self.control_id}: duplicate level name {name!r}")
            seen.append(name)
        if not self.provenance:
            raise SchemaError(f"{self.control_id}: a control with no provenance is a knob")

    @property
    def max_level(self) -> int:
        return len(self.levels) - 1

    def level_ordinal(self, name: str) -> int:
        """The ordinal of a level name. Raises rather than defaulting to the weakest."""
        try:
            return self.levels.index(name)
        except ValueError:
            raise GuardError(
                f"{self.control_id}: no level named {name!r}; the catalog declares "
                f"{list(self.levels)}",
                code="E-SYN-000",
            ) from None


@dataclass(frozen=True, slots=True)
class Catalog:
    """The control catalog, ordered bytewise by control id."""

    controls: tuple[ControlSpec, ...]

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(
            self.controls, lambda c: canon.byte_order_key(str(c.control_id)), where="Catalog"
        )

    @classmethod
    def from_entries(cls, entries: Iterable[Mapping[str, object]]) -> Self:
        """Build from an iterable of mappings with the documented control fields."""
        specs: list[ControlSpec] = []
        for raw in entries:
            specs.append(
                ControlSpec(
                    control_id=ControlId.of(str(raw["id"])),
                    title=str(raw.get("title", "")),
                    levels=tuple(str(v) for v in raw["levels"]),
                    dimensions=tuple(
                        DimensionId.of(str(d)) for d in raw.get("dimensions", ())
                    ),
                    provenance=str(raw.get("provenance", "")),
                )
            )
        return cls(tuple(sorted(specs, key=lambda c: canon.byte_order_key(str(c.control_id)))))

    def get(self, control_id: ControlId) -> ControlSpec:
        for spec in self.controls:
            if spec.control_id == control_id:
                return spec
        raise GuardError(f"no control {control_id!r} in the catalog", code="E-SYN-000")

    def literals(self) -> tuple[tuple[ControlId, int], ...]:
        """Every (control, level) literal in canonical order: control bytes, then level.

        History-independent by construction: appending a control never reorders two
        pre-existing literals, it only inserts between them.
        """
        out: list[tuple[ControlId, int]] = []
        for spec in self.controls:
            for level in range(1, spec.max_level + 1):
                out.append((spec.control_id, level))
        return tuple(out)

    def canonical_bytes(self) -> bytes:
        return canon.ordered_seq(
            b"".join(
                (
                    canon.ascii_text(spec.control_id),
                    canon.ordered_seq(canon.utf8_text(name) for name in spec.levels),
                    canon.ordered_seq(canon.ascii_text(d) for d in spec.dimensions),
                )
            )
            for spec in self.controls
        )

    @property
    def controls_hash(self) -> str:
        """The catalog digest, including the level table. `"b2b256:<64hex>"`."""
        return canon.hash_ref("controls", self.canonical_bytes())


@dataclass(frozen=True, slots=True)
class BitEntry:
    """One row of the append-only lock: a (control, level) pinned to a bit position."""

    pos: int
    control_id: ControlId
    level: int
    state: str

    def __post_init__(self) -> None:
        canon.u8(self.pos)
        if self.pos >= MASK_WIDTH:
            raise LimitError(
                f"bit position {self.pos} is outside the {MASK_WIDTH}-bit mask",
                code="E-LIMIT-COUNT",
            )
        if self.level < 1:
            raise SchemaError("BitEntry.level starts at 1; level 0 asserts nothing")
        if self.state not in ("live", "tombstone"):
            raise SchemaError(f"BitEntry.state must be live or tombstone, got {self.state!r}")


@dataclass(frozen=True, slots=True)
class BitTable:
    """The (control, level) -> bit assignment, plus the canonical ranks.

    `bit` comes from the append-only lock and never moves. `rank` is the 0-based index in
    the canonical order over LIVE entries and shifts by insertion. They are different
    things: a mask is built from bits, every ordering and every printed sequence uses rank.
    """

    entries: tuple[BitEntry, ...]

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(self.entries, lambda e: e.pos, where="BitTable.entries")
        seen: set[tuple[str, int]] = set()
        for entry in self.entries:
            key = (str(entry.control_id), entry.level)
            if key in seen:
                raise SchemaError(f"BitTable: {key} appears twice in the lock")
            seen.add(key)

    @classmethod
    def derive(cls, catalog: Catalog) -> Self:
        """Assign bits in canonical order: control id bytes ascending, then level ascending.

        This is the assignment a fresh lock records. An existing lock is loaded rather than
        re-derived, because re-derivation after a catalog edit would renumber pre-existing
        bits and invalidate every archived certificate silently.
        """
        literals = catalog.literals()
        if len(literals) > MASK_WIDTH:
            raise LimitError(
                f"{len(literals)} threshold literals exceed the {MASK_WIDTH}-bit mask width",
                code="E-LIMIT-COUNT",
            )
        return cls(
            tuple(
                BitEntry(pos=index, control_id=control_id, level=level, state="live")
                for index, (control_id, level) in enumerate(literals)
            )
        )

    @property
    def live(self) -> tuple[BitEntry, ...]:
        """Live entries in canonical order. Tombstones keep their bit and lose their rank."""
        return tuple(
            sorted(
                (e for e in self.entries if e.state == "live"),
                key=lambda e: (canon.byte_order_key(str(e.control_id)), e.level),
            )
        )

    def literals(self) -> tuple[model.ThresholdLiteral, ...]:
        """Every live literal as a `ThresholdLiteral`, ascending by rank."""
        return tuple(
            model.ThresholdLiteral(
                control_id=entry.control_id, level=entry.level, bit=entry.pos, rank=rank
            )
            for rank, entry in enumerate(self.live)
        )

    def bit_of(self, control_id: ControlId, level: int) -> int:
        for entry in self.entries:
            if entry.control_id == control_id and entry.level == level and entry.state == "live":
                return entry.pos
        raise GuardError(
            f"no live bit for {control_id}@{level} in the lock; a mask built without one "
            "would not be comparable against this catalog",
            code="E-LITERAL-TABLE",
        )

    def canonical_bytes(self) -> bytes:
        return canon.ordered_seq(
            b"".join(
                (
                    canon.u8(entry.pos),
                    canon.ascii_text(entry.control_id),
                    canon.u8(entry.level),
                    canon.ascii_text(entry.state),
                )
            )
            for entry in self.entries
        )

    @property
    def catalog_bits_hash(self) -> str:
        return canon.hash_ref("bits", self.canonical_bytes())

    def lock_text(self) -> str:
        """Render the lock file. Emitted by S0; rendered here so a test can round-trip it."""
        lines = [
            "# config/vs/catalog-bits.lock",
            "# APPEND-ONLY. A (control_id, level) keeps its pos forever; removal sets",
            "# state = \"tombstone\" and the pos is never reused.",
            "",
        ]
        for entry in self.entries:
            lines.append("[[bit]]")
            lines.append(f"pos = {entry.pos}")
            lines.append(f'control_id = "{entry.control_id.snake}"')
            lines.append(f"level = {entry.level}")
            lines.append(f'state = "{entry.state}"')
            lines.append("")
        return "\n".join(lines)

    def check_covers(self, catalog: Catalog) -> None:
        """Every live literal of the catalog must have a live bit, and vice versa."""
        wanted = {(str(c), level) for c, level in catalog.literals()}
        have = {(str(e.control_id), e.level) for e in self.entries if e.state == "live"}
        missing = sorted(wanted - have)
        extra = sorted(have - wanted)
        if missing or extra:
            raise GuardError(
                f"lock and catalog disagree; missing {missing}, unexpected {extra}",
                code="E-LITERAL-TABLE",
            )


def load_catalog(path: Path) -> Catalog:
    """Read a control catalog TOML with the documented `[[control]]` field contract."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("control", ())
    if not entries:
        raise SchemaError(
            f"{path}: the catalog declares no controls; a run that needs one must exit "
            "non-zero rather than proceed with an empty-but-valid catalog"
        )
    return Catalog.from_entries(entries)


def load_bit_table(path: Path) -> BitTable:
    """Read `catalog-bits.lock`. `[[bit]] pos, control_id, level, state`."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("bit", ())
    entries = [
        BitEntry(
            pos=int(row["pos"]),
            control_id=ControlId.of(str(row["control_id"])),
            level=int(row["level"]),
            state=str(row.get("state", "live")),
        )
        for row in rows
    ]
    return BitTable(tuple(sorted(entries, key=lambda e: e.pos)))


# ---------------------------------------------------------------------------
# The guard front end: lexer
# ---------------------------------------------------------------------------

_RESERVED: Final[frozenset[str]] = frozenset(
    {
        "abs",
        "and",
        "ctl",
        "distinct",
        "false",
        "max",
        "min",
        "not",
        "or",
        "overlaps",
        "true",
        "within",
    }
)

_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"""
      (?P<space>[ \t\n]+)
    | (?P<dur>[0-9][0-9_]*(?:ns|us|ms|tick|s|m|h)\b)
    | (?P<int>[0-9][0-9_]*)
    | (?P<sym>\#[a-z][a-z0-9_]*)
    | (?P<ident>[a-z][a-z0-9_]*)
    | (?P<op>>=|<=|==|!=|[<>(),.+\-*])
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    pos: int


def _lex(text: str, *, where: str) -> tuple[_Token, ...]:
    """Lex a guard. No comments, no strings; a CR byte and a `.`-then-digit are errors."""
    if "\r" in text:
        raise GuardError(f"{where}: a CR byte in rule text", code="E-LEX-001")
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        if text[index] == "." and index + 1 < len(text) and text[index + 1].isdigit():
            raise GuardError(f"{where}: a '.' followed by a digit at {index}", code="E-LEX-004")
        match = _TOKEN.match(text, index)
        if match is None:
            raise GuardError(
                f"{where}: unlexable character {text[index]!r} at {index}", code="E-SYN-000"
            )
        index = match.end()
        kind = match.lastgroup
        assert kind is not None
        if kind == "space":
            continue
        tokens.append(_Token(kind=kind, text=match.group(), pos=match.start()))
    return tuple(tokens)


# ---------------------------------------------------------------------------
# The guard front end: the core node set
# ---------------------------------------------------------------------------


class GuardType(StrEnum):
    """Section 63.4 types, narrowed to the ones the slice's operators need.

    `TICK` and `DUR` are distinct with no implicit conversion: subtracting two ticks yields
    a duration, and comparing a tick against a duration is a type error rather than a
    comparison of two integers that happen to be in the same units.
    """

    BOOL = "Bool"
    INT = "Int"
    TICK = "Tick"
    DUR = "Dur"
    SYM = "Sym"
    ENT = "Ent"
    CTL = "Ctl"


@dataclass(frozen=True, slots=True)
class Node:
    """One canonicalised guard node. The core set only; every sugar desugars into it."""

    kind: str
    children: tuple[Node, ...] = ()
    text: str = ""
    value: int = 0

    def canonical_bytes(self) -> bytes:
        return b"".join(
            (
                canon.ascii_text(self.kind),
                canon.utf8_text(self.text),
                canon.i64(self.value),
                canon.ordered_seq(child.canonical_bytes() for child in self.children),
            )
        )


_MISSING: Final[object] = object()

#: The core node kinds, in the order their tags are assigned in the CAE encoding.
_CORE_KINDS: Final[tuple[str, ...]] = (
    "ConstBool",
    "ConstInt",
    "ConstDur",
    "ConstSym",
    "Field",
    "Not",
    "Abs",
    "And",
    "Or",
    "Eq",
    "Lt",
    "Add",
    "Sub",
    "MulLit",
    "Min",
    "Max",
    "Threshold",
)
_KIND_TAG: Final[dict[str, int]] = {kind: index for index, kind in enumerate(_CORE_KINDS)}


# ---------------------------------------------------------------------------
# The control sort
# ---------------------------------------------------------------------------


class _CtlParser:
    """`ctl_expr := or ; or := and ("or" and)* ; and := prim ("and" prim)* ;
    prim := "(" expr ")" | "ctl" "." ident ">=" ident`.

    Everything outside that grammar is rejected with the code the specification names, so
    a rule that tries to negate a control, compare it to an integer, or read a data field
    inside the control sort goes red at compile time rather than producing a mask that
    quietly means something else.
    """

    def __init__(self, tokens: tuple[_Token, ...], where: str) -> None:
        self._tokens = tokens
        self._index = 0
        self._where = where

    def parse(self) -> Node:
        node = self._parse_or()
        if self._index != len(self._tokens):
            raise GuardError(
                f"{self._where}: trailing token {self._tokens[self._index].text!r}",
                code="E-SYN-000",
            )
        return node

    def _peek(self) -> _Token | None:
        return self._tokens[self._index] if self._index < len(self._tokens) else None

    def _take(self) -> _Token:
        token = self._peek()
        if token is None:
            raise GuardError(f"{self._where}: guard ends early", code="E-SYN-000")
        self._index += 1
        return token

    def _parse_or(self) -> Node:
        terms = [self._parse_and()]
        while (token := self._peek()) is not None and token.text == "or":
            self._take()
            terms.append(self._parse_and())
        return terms[0] if len(terms) == 1 else Node("Or", tuple(terms))

    def _parse_and(self) -> Node:
        terms = [self._parse_prim()]
        while (token := self._peek()) is not None and token.text == "and":
            self._take()
            terms.append(self._parse_prim())
        return terms[0] if len(terms) == 1 else Node("And", tuple(terms))

    def _parse_prim(self) -> Node:
        token = self._take()
        if token.text == "(":
            node = self._parse_or()
            closing = self._take()
            if closing.text != ")":
                raise GuardError(f"{self._where}: unbalanced parenthesis", code="E-SYN-000")
            return node
        if token.text == "not":
            raise GuardError(
                f"{self._where}: `not` is not admissible in the control sort", code="E-SYN-009"
            )
        if token.kind in ("int", "dur", "sym"):
            raise GuardError(
                f"{self._where}: literal {token.text!r} in the control sort", code="E-SYN-009"
            )
        if token.text != "ctl":
            raise GuardError(
                f"{self._where}: {token.text!r} is not a control reference; the control sort "
                "admits only `ctl.<id> >= <level>`",
                code="E-SYN-009",
            )
        dot = self._take()
        if dot.text != ".":
            raise GuardError(f"{self._where}: expected `.` after `ctl`", code="E-SYN-000")
        name = self._take()
        if name.kind != "ident":
            raise GuardError(f"{self._where}: expected a control id", code="E-SYN-000")
        operator = self._take()
        if operator.text != ">=":
            raise GuardError(
                f"{self._where}: the control sort admits only `>=`, got {operator.text!r}",
                code="E-SYN-009",
            )
        level = self._take()
        if level.kind in ("int", "dur"):
            raise GuardError(
                f"{self._where}: level {level.text!r} written as an integer; levels are named",
                code="E-SYN-012",
            )
        if level.kind != "ident":
            raise GuardError(f"{self._where}: expected a level name", code="E-SYN-000")
        return Node("Threshold", text=name.text + "@" + level.text)


def _ctl_terms(node: Node) -> tuple[frozenset[tuple[str, str]], ...]:
    """Distribute a control guard to DNF. Each term is a set of (control, level_name)."""
    if node.kind == "Threshold":
        control, level = node.text.split("@", 1)
        return (frozenset({(control, level)}),)
    if node.kind == "Or":
        out: list[frozenset[tuple[str, str]]] = []
        for child in node.children:
            out.extend(_ctl_terms(child))
        return tuple(out)
    if node.kind == "And":
        product: tuple[frozenset[tuple[str, str]], ...] = (frozenset(),)
        for child in node.children:
            child_terms = _ctl_terms(child)
            product = tuple(
                left | right for left in product for right in child_terms
            )
            if len(product) > MAX_DNF_TERMS * MAX_DNF_TERMS:
                raise GuardError(
                    "control-sort DNF exceeded eight terms", code="E-SEM-041"
                )
        return product
    raise GuardError(f"unexpected control node {node.kind!r}", code="E-SYN-009")


def _canonical_terms(
    node: Node, catalog: Catalog, *, where: str
) -> tuple[tuple[tuple[ControlId, int], ...], ...]:
    """C1..C8 for the control sort, over (control, level) pairs rather than mask values.

    Working on pairs rather than on masks is deliberate: subsumption over masks would put a
    mask value inside a decision path, and the only permitted mask comparison in a decision
    path is popcount.
    """
    resolved: list[dict[ControlId, int]] = []
    for term in _ctl_terms(node):
        # C7, within a term: keep only the highest level per control, because requiring
        # both `k >= 1` and `k >= 2` is requiring `k >= 2`.
        strongest: dict[ControlId, int] = {}
        for control_name, level_name in sorted(term):
            control_id = ControlId.of(control_name)
            spec = catalog.get(control_id)
            ordinal = spec.level_ordinal(level_name)
            if ordinal < 1:
                raise GuardError(
                    f"{where}: level {level_name!r} of {control_id} is the weakest setting; "
                    "`at least the weakest setting` asserts nothing and has no literal",
                    code="E-SYN-000",
                )
            strongest[control_id] = max(strongest.get(control_id, 0), ordinal)
        if strongest:
            resolved.append(strongest)

    # C7, across terms: a term implied by another term is redundant. Term X is implied by
    # term Y when Y demands at most what X demands on every control X names, because then
    # satisfying X already satisfies Y.
    def implies(weaker: dict[ControlId, int], stronger: dict[ControlId, int]) -> bool:
        return all(
            control in stronger and stronger[control] >= level
            for control, level in weaker.items()
        )

    kept: list[dict[ControlId, int]] = []
    for index, term in enumerate(resolved):
        redundant = False
        for other_index, other in enumerate(resolved):
            if other_index == index:
                continue
            if implies(other, term) and (
                not implies(term, other) or other_index < index
            ):
                redundant = True
                break
        if not redundant:
            kept.append(term)

    # C8: emit each term as a tuple sorted in the canonical atom order.
    terms = tuple(
        tuple(
            sorted(
                term.items(), key=lambda kv: (canon.byte_order_key(str(kv[0])), kv[1])
            )
        )
        for term in kept
    )
    unique = tuple(sorted(set(terms)))
    if len(unique) > MAX_DNF_TERMS:
        raise GuardError(
            f"{where}: control-sort DNF has {len(unique)} terms, more than {MAX_DNF_TERMS}",
            code="E-SEM-041",
        )
    return unique


def _terms_to_masks(
    terms: tuple[tuple[tuple[ControlId, int], ...], ...], bits: BitTable, *, where: str
) -> tuple[int, ...]:
    """Map canonical terms onto blocker masks and enforce C-SLICE-1.

    Sorting by (popcount, value) is the declared total key of `RuleInstance.blockers`; it
    is an ordering of the emitted array, not a tie-break inside a search.
    """
    masks: list[int] = []
    for term in terms:
        if len(term) != 1:
            raise GuardError(
                f"{where}: conjunctive blocker term {[(str(c), lv) for c, lv in term]}; "
                "C-SLICE-1 narrows every DNF term to a single threshold literal",
                code="E-VS-BLOCK-CONJ",
            )
        mask = 0
        for control_id, level in term:
            mask |= 1 << bits.bit_of(control_id, level)
        masks.append(mask)
    return tuple(sorted(set(masks), key=lambda m: (m.bit_count(), m)))


def compile_blocked_when(
    text: str, catalog: Catalog, bits: BitTable, *, where: str
) -> tuple[tuple[tuple[ControlId, int], ...], ...]:
    """Compile a `blocked_when` guard to canonical DNF terms. Empty text means no blockers.

    An empty guard is not a type error: it says this rule's edge is not severable by any
    control in the catalog, which is a modelling statement the slice makes deliberately for
    the admin-export edge of route B.
    """
    if not text.strip():
        return ()
    node = _CtlParser(_lex(text, where=where), where).parse()
    if node.kind not in ("Threshold", "And", "Or"):
        raise GuardError(f"{where}: guard root is not Ctl", code="E-TYP-002")
    terms = _canonical_terms(node, catalog, where=where)
    # C8's final obligation: canonicalisation is idempotent, checked on every compile.
    again = _canonical_terms(node, catalog, where=where)
    if terms != again:
        raise GuardError(f"{where}: canon(canon(x)) != canon(x)", code="E-SYN-000")
    return terms


# ---------------------------------------------------------------------------
# The data sort
# ---------------------------------------------------------------------------


class _DataParser:
    """Recursive descent over the data sort, desugaring into the core node set as it goes.

    `a != b` becomes `Not(Eq(a,b))`, `a <= b` becomes `Not(Lt(b,a))`, `a > b` becomes
    `Lt(b,a)`, and `within(x,y,d)` becomes `Not(Lt(d, Abs(Sub(y,x))))`. Keeping one
    comparison node and one negation node is what makes the NNF and flattening steps
    total rather than a table of special cases.
    """

    def __init__(self, tokens: tuple[_Token, ...], where: str) -> None:
        self._tokens = tokens
        self._index = 0
        self._where = where

    def parse(self) -> Node:
        node = self._parse_or()
        if self._index != len(self._tokens):
            raise GuardError(
                f"{self._where}: trailing token {self._tokens[self._index].text!r}",
                code="E-SYN-000",
            )
        return node

    def _peek(self) -> _Token | None:
        return self._tokens[self._index] if self._index < len(self._tokens) else None

    def _take(self) -> _Token:
        token = self._peek()
        if token is None:
            raise GuardError(f"{self._where}: guard ends early", code="E-SYN-000")
        self._index += 1
        return token

    def _expect(self, text: str) -> _Token:
        token = self._take()
        if token.text != text:
            raise GuardError(
                f"{self._where}: expected {text!r}, got {token.text!r}", code="E-SYN-000"
            )
        return token

    def _parse_or(self) -> Node:
        terms = [self._parse_and()]
        while (token := self._peek()) is not None and token.text == "or":
            self._take()
            terms.append(self._parse_and())
        return terms[0] if len(terms) == 1 else Node("Or", tuple(terms))

    def _parse_and(self) -> Node:
        terms = [self._parse_not()]
        while (token := self._peek()) is not None and token.text == "and":
            self._take()
            terms.append(self._parse_not())
        return terms[0] if len(terms) == 1 else Node("And", tuple(terms))

    def _parse_not(self) -> Node:
        token = self._peek()
        if token is not None and token.text == "not":
            self._take()
            return Node("Not", (self._parse_not(),))
        return self._parse_cmp()

    def _parse_cmp(self) -> Node:
        left = self._parse_sum()
        token = self._peek()
        if token is None or token.text not in ("==", "!=", "<", "<=", ">", ">="):
            return left
        self._take()
        right = self._parse_sum()
        match token.text:
            case "==":
                return Node("Eq", (left, right))
            case "!=":
                return Node("Not", (Node("Eq", (left, right)),))
            case "<":
                return Node("Lt", (left, right))
            case "<=":
                return Node("Not", (Node("Lt", (right, left)),))
            case ">":
                return Node("Lt", (right, left))
            case _:
                return Node("Not", (Node("Lt", (left, right)),))

    def _parse_sum(self) -> Node:
        node = self._parse_prim()
        while (token := self._peek()) is not None and token.text in ("+", "-"):
            self._take()
            right = self._parse_prim()
            node = Node("Add" if token.text == "+" else "Sub", (node, right))
        return node

    def _parse_prim(self) -> Node:
        token = self._take()
        if token.text == "(":
            node = self._parse_or()
            self._expect(")")
            return node
        if token.kind == "int":
            return Node("ConstInt", value=int(token.text.replace("_", "")))
        if token.kind == "dur":
            return Node("ConstDur", value=duration_ticks(token.text))
        if token.kind == "sym":
            return Node("ConstSym", text=token.text[1:])
        if token.kind != "ident":
            raise GuardError(
                f"{self._where}: unexpected {token.text!r} in the data sort", code="E-SYN-000"
            )
        if token.text == "ctl":
            raise GuardError(
                f"{self._where}: `ctl.` is not admissible inside the data sort",
                code="E-SYN-010",
            )
        if token.text in ("true", "false"):
            return Node("ConstBool", value=1 if token.text == "true" else 0)
        if token.text in ("abs", "min", "max", "within"):
            return self._parse_call(token.text)
        # A slot field: `<slot>.<name>`.
        self._expect(".")
        name = self._take()
        if name.kind != "ident":
            raise GuardError(f"{self._where}: expected a field name", code="E-SYN-000")
        if token.text not in SLOT_NAMES:
            raise GuardError(
                f"{self._where}: {token.text!r} is not a body slot; slots are "
                f"{list(SLOT_NAMES)}",
                code="E-SYN-000",
            )
        return Node("Field", text=token.text + "." + name.text)

    def _parse_call(self, name: str) -> Node:
        self._expect("(")
        args = [self._parse_or()]
        while (token := self._peek()) is not None and token.text == ",":
            self._take()
            args.append(self._parse_or())
        self._expect(")")
        match name:
            case "abs" if len(args) == 1:
                return Node("Abs", (args[0],))
            case "min" if len(args) == 2:
                return Node("Min", tuple(args))
            case "max" if len(args) == 2:
                return Node("Max", tuple(args))
            case "within" if len(args) == 3:
                span = Node("Abs", (Node("Sub", (args[1], args[0])),))
                return Node("Not", (Node("Lt", (args[2], span)),))
            case _:
                raise GuardError(
                    f"{self._where}: {name}/{len(args)} is not a declared operator",
                    code="E-SYN-000",
                )


def _field_type(text: str) -> GuardType:
    """`<slot>.t` is a Tick; every other slot field binds an entity argument."""
    return GuardType.TICK if text.endswith(".t") else GuardType.ENT


_NUMERIC: Final[frozenset[GuardType]] = frozenset(
    {GuardType.INT, GuardType.TICK, GuardType.DUR}
)


def _type_of(node: Node, *, where: str) -> GuardType:
    """Typecheck with no implicit conversion, no cast, no null and no option."""
    match node.kind:
        case "ConstBool":
            return GuardType.BOOL
        case "ConstInt":
            return GuardType.INT
        case "ConstDur":
            return GuardType.DUR
        case "ConstSym":
            return GuardType.SYM
        case "Field":
            return _field_type(node.text)
        case "Not":
            if _type_of(node.children[0], where=where) is not GuardType.BOOL:
                raise GuardError(f"{where}: `not` applied to a non-Bool", code="E-TYP-001")
            return GuardType.BOOL
        case "And" | "Or":
            for child in node.children:
                if _type_of(child, where=where) is not GuardType.BOOL:
                    raise GuardError(
                        f"{where}: `{node.kind.lower()}` over a non-Bool", code="E-TYP-001"
                    )
            return GuardType.BOOL
        case "Eq":
            left = _type_of(node.children[0], where=where)
            right = _type_of(node.children[1], where=where)
            if left is not right:
                raise GuardError(
                    f"{where}: `==` compares {left} with {right}", code="E-TYP-001"
                )
            return GuardType.BOOL
        case "Lt":
            left = _type_of(node.children[0], where=where)
            right = _type_of(node.children[1], where=where)
            if left is not right or left not in _NUMERIC:
                raise GuardError(
                    f"{where}: `<` compares {left} with {right}", code="E-TYP-001"
                )
            return GuardType.BOOL
        case "Sub":
            left = _type_of(node.children[0], where=where)
            right = _type_of(node.children[1], where=where)
            if left is GuardType.TICK and right is GuardType.TICK:
                return GuardType.DUR
            if left is right and left in _NUMERIC:
                return left
            raise GuardError(f"{where}: cannot subtract {right} from {left}", code="E-TYP-001")
        case "Add":
            left = _type_of(node.children[0], where=where)
            right = _type_of(node.children[1], where=where)
            if left is GuardType.TICK and right is GuardType.DUR:
                return GuardType.TICK
            if left is right and left in _NUMERIC:
                return left
            raise GuardError(f"{where}: cannot add {right} to {left}", code="E-TYP-001")
        case "Abs":
            inner = _type_of(node.children[0], where=where)
            if inner not in _NUMERIC:
                raise GuardError(f"{where}: abs of {inner}", code="E-TYP-001")
            return inner
        case "Min" | "Max":
            left = _type_of(node.children[0], where=where)
            right = _type_of(node.children[1], where=where)
            if left is not right or left not in _NUMERIC:
                raise GuardError(
                    f"{where}: {node.kind.lower()} of {left} and {right}", code="E-TYP-001"
                )
            return left
        case _:
            raise GuardError(f"{where}: unknown data node {node.kind!r}", code="E-SYN-000")


def _canonicalise_data(node: Node) -> Node:
    """C2..C6: constant-fold, NNF, flatten, absorb, dedupe, sort children.

    Children of the commutative connectives are sorted by (kind tag, node digest), which is
    a content key rather than a position key, so two guards that differ only in the order
    an author wrote their conjuncts compile to the same bytes and the same hash.
    """
    node = Node(node.kind, tuple(_canonicalise_data(c) for c in node.children), node.text, node.value)

    if node.kind == "Not" and node.children[0].kind == "Not":
        return node.children[0].children[0]
    if node.kind == "Not" and node.children[0].kind in ("And", "Or"):
        inner = node.children[0]
        flipped = "Or" if inner.kind == "And" else "And"
        return _canonicalise_data(
            Node(flipped, tuple(Node("Not", (c,)) for c in inner.children))
        )
    if node.kind == "Not" and node.children[0].kind == "ConstBool":
        return Node("ConstBool", value=0 if node.children[0].value else 1)

    if node.kind in ("And", "Or"):
        flattened: list[Node] = []
        for child in node.children:
            if child.kind == node.kind:
                flattened.extend(child.children)
            else:
                flattened.append(child)
        identity = 1 if node.kind == "And" else 0
        kept = [c for c in flattened if not (c.kind == "ConstBool" and c.value == identity)]
        if any(c.kind == "ConstBool" and c.value != identity for c in kept):
            return Node("ConstBool", value=0 if node.kind == "And" else 1)
        deduped: list[Node] = []
        seen: set[bytes] = set()
        for child in kept:
            key = child.canonical_bytes()
            if key not in seen:
                seen.add(key)
                deduped.append(child)
        deduped.sort(key=lambda c: (_KIND_TAG.get(c.kind, 255), c.canonical_bytes()))
        if not deduped:
            return Node("ConstBool", value=identity)
        if len(deduped) == 1:
            return deduped[0]
        return Node(node.kind, tuple(deduped))

    if node.kind in ("Add", "Sub", "Min", "Max") and all(
        c.kind in ("ConstInt", "ConstDur") for c in node.children
    ):
        left, right = node.children[0].value, node.children[1].value
        folded = {
            "Add": _saturate(left + right),
            "Sub": _saturate(left - right),
            "Min": min(left, right),
            "Max": max(left, right),
        }[node.kind]
        kind = "ConstDur" if any(c.kind == "ConstDur" for c in node.children) else "ConstInt"
        return Node(kind, value=folded)
    if node.kind == "Abs" and node.children[0].kind in ("ConstInt", "ConstDur"):
        return Node(node.children[0].kind, value=_saturate(abs(node.children[0].value)))
    return node


def compile_when(text: str, *, where: str) -> Node | None:
    """Compile a `when` guard. Empty text means no data-sort restriction beyond the join."""
    if not text.strip():
        return None
    node = _DataParser(_lex(text, where=where), where).parse()
    if _type_of(node, where=where) is not GuardType.BOOL:
        raise GuardError(f"{where}: data-sort guard root is not Bool", code="E-TYP-001")
    canonical = _canonicalise_data(node)
    if _canonicalise_data(canonical).canonical_bytes() != canonical.canonical_bytes():
        raise GuardError(f"{where}: canon(canon(x)) != canon(x)", code="E-SYN-000")
    return canonical


def eval_when(node: Node | None, env: dict[str, object]) -> bool:
    """Evaluate a compiled `when` guard. TOTAL: returns a value, never raises.

    A field the environment does not bind evaluates to a sentinel that is equal to nothing
    and orders below nothing, so a guard over an unbound slot is false rather than an
    exception that would abort a fixpoint halfway through.
    """
    if node is None:
        return True
    return bool(_eval(node, env))


def _eval(node: Node, env: dict[str, object]) -> object:
    match node.kind:
        case "ConstBool":
            return node.value == 1
        case "ConstInt" | "ConstDur":
            return node.value
        case "ConstSym":
            return node.text
        case "Field":
            return env.get(node.text, _MISSING)
        case "Not":
            return not _eval(node.children[0], env)
        case "And":
            return all(bool(_eval(c, env)) for c in node.children)
        case "Or":
            return any(bool(_eval(c, env)) for c in node.children)
        case "Eq":
            left = _eval(node.children[0], env)
            right = _eval(node.children[1], env)
            if left is _MISSING or right is _MISSING:
                return False
            return left == right
        case "Lt":
            left = _eval(node.children[0], env)
            right = _eval(node.children[1], env)
            if not isinstance(left, int) or not isinstance(right, int):
                return False
            return left < right
        case "Add" | "Sub" | "Min" | "Max":
            left = _eval(node.children[0], env)
            right = _eval(node.children[1], env)
            if not isinstance(left, int) or not isinstance(right, int):
                return 0
            return {
                "Add": lambda: _saturate(left + right),
                "Sub": lambda: _saturate(left - right),
                "Min": lambda: min(left, right),
                "Max": lambda: max(left, right),
            }[node.kind]()
        case "Abs":
            inner = _eval(node.children[0], env)
            return _saturate(abs(inner)) if isinstance(inner, int) else 0
        case _:
            return False


# ---------------------------------------------------------------------------
# Patterns and temporal specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pattern:
    """`predicate(var, ..., tick_var)`. The last variable binds the fact's tick."""

    predicate: str
    variables: tuple[str, ...]

    def __post_init__(self) -> None:
        if _PREDICATE.match(self.predicate) is None:
            raise SchemaError(f"not a predicate: {self.predicate!r}")
        if not self.variables:
            raise SchemaError(f"{self.predicate}: a pattern needs at least a tick variable")
        seen: list[str] = []
        for name in self.variables:
            check_snake(name, where=f"{self.predicate} variable")
            if name in seen:
                raise SchemaError(f"{self.predicate}: variable {name!r} repeats in one pattern")
            seen.append(name)
        if "t" in self.variables[:-1]:
            raise SchemaError(
                f"{self.predicate}: `t` is reserved for the slot's tick field in `when` and "
                "may not name an entity argument"
            )

    @property
    def entity_vars(self) -> tuple[str, ...]:
        return self.variables[:-1]

    @property
    def tick_var(self) -> str:
        return self.variables[-1]

    @property
    def arity(self) -> int:
        return len(self.variables) - 1

    def text(self) -> str:
        return f"{self.predicate}({', '.join(self.variables)})"


def parse_pattern(text: str) -> Pattern:
    """Parse `predicate(v1, v2, t)`. Literal arguments are rejected: patterns bind, only."""
    stripped = text.strip()
    match = re.fullmatch(r"([a-z][a-z0-9_.]*)\(([^()]*)\)", stripped)
    if match is None:
        raise SchemaError(f"not a pattern: {text!r}")
    variables = tuple(part.strip() for part in match.group(2).split(",") if part.strip())
    return Pattern(predicate=match.group(1), variables=variables)


@dataclass(frozen=True, slots=True)
class Temporal:
    """One of exactly three implemented operators, plus the obligation trigger form.

    `seq`      `[left, right]` within W, `t_left < t_right` and `t_right - t_left <= W`.
    `absence`  `of` must not hold over the sealed lookback `[t_before - W, t_before)`.
    `distinct` at least `n` distinct values of `field` among the facts of slot `of` in
               `[t - W, t]`, as an exact set with no sketch.
    `obligation` the obliged head must hold over `[t_before - W, t_before)`; S9 decides
               whether that is satisfied, licensed, or a permanent blind spot.
    """

    op: str
    within_ticks: int = 0
    left: str = ""
    right: str = ""
    before: str = ""
    of_slot: str = ""
    of_pattern: Pattern | None = None
    field_name: str = ""
    n: int = 0

    def __post_init__(self) -> None:
        if self.op not in TEMPORAL_OPS:
            raise SchemaError(
                f"temporal op {self.op!r} is not implemented; the slice implements "
                f"{list(TEMPORAL_OPS)} and defers the rest"
            )


def _parse_temporal(raw: dict[str, str], body: tuple[Pattern, ...], *, where: str) -> Temporal | None:
    if not raw:
        return None
    op = str(raw.get("op", ""))
    within = duration_ticks(str(raw["within"])) if "within" in raw else 0
    match op:
        case "seq":
            left, right = str(raw["left"]), str(raw["right"])
            for slot in (left, right):
                if slot not in SLOT_NAMES[: len(body)]:
                    raise SchemaError(f"{where}: seq names slot {slot!r}, which has no pattern")
            return Temporal(op=op, within_ticks=within, left=left, right=right)
        case "absence":
            return Temporal(
                op=op,
                within_ticks=within,
                before=str(raw["before"]),
                of_pattern=parse_pattern(str(raw["of"])),
            )
        case "distinct":
            return Temporal(
                op=op,
                within_ticks=within,
                of_slot=str(raw["of"]),
                field_name=str(raw["field"]),
                n=int(str(raw["n"])),
            )
        case "obligation":
            return Temporal(op=op, within_ticks=within, before=str(raw["before"]))
        case _:
            raise SchemaError(f"{where}: temporal op {op!r} is not implemented")


# ---------------------------------------------------------------------------
# The compiled rule and the table
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CompiledRule:
    """One rule, its parsed patterns, its two compiled guards and its blocker masks."""

    rule: model.Rule
    head: Pattern
    body: tuple[Pattern, ...]
    when: Node | None
    blocker_terms: tuple[tuple[tuple[ControlId, int], ...], ...]
    blockers: tuple[int, ...]
    temporal: Temporal | None
    silent_bind_kinds: tuple[tuple[str, str], ...] = ()

    @property
    def rule_id(self) -> RuleId:
        return self.rule.rule_id

    @property
    def is_obligation(self) -> bool:
        return self.rule.kind is model.RuleKind.OBLIGATION

    @property
    def mask(self) -> int:
        value = 0
        for term in self.blockers:
            value |= term
        return value

    def slot_of(self, name: str) -> int:
        return SLOT_NAMES.index(name)

    def guard_bytes(self) -> bytes:
        """The canonical guard encoding of this rule: the data AST DAG then the DNF terms."""
        return _encode_ast_dag(self.when) + canon.ordered_seq(
            canon.ordered_seq(
                canon.ascii_text(str(control)) + canon.u8(level) for control, level in term
            )
            for term in self.blocker_terms
        )


def _encode_ast_dag(node: Node | None) -> bytes:
    """Hash-cons the data AST into a DAG numbered in postorder, then encode it.

    Postorder numbering rather than a nested encoding so that a shared subexpression is
    encoded once and the encoding length reflects the DAG rather than the tree.
    """
    if node is None:
        return canon.leb128(0)
    order: list[Node] = []
    index_of: dict[bytes, int] = {}

    def visit(current: Node) -> int:
        for child in current.children:
            visit(child)
        key = current.canonical_bytes()
        if key in index_of:
            return index_of[key]
        index_of[key] = len(order)
        order.append(current)
        return index_of[key]

    visit(node)
    out = bytearray(canon.leb128(len(order)))
    for entry in order:
        out += canon.u8(_KIND_TAG.get(entry.kind, 255))
        out += canon.utf8_text(entry.text)
        out += canon.i64(entry.value)
        out += canon.leb128(len(entry.children))
        for child in entry.children:
            out += canon.leb128(index_of[child.canonical_bytes()])
    return bytes(out)


@dataclass(frozen=True, slots=True)
class RuleTable:
    """The compiled rule table plus the catalog and lock it was compiled against."""

    rules: tuple[CompiledRule, ...]
    catalog: Catalog
    bits: BitTable
    rules_text_hash: str
    axiom_predicates: tuple[str, ...] = ()
    _by_id: dict[str, CompiledRule] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        canon.check_strictly_ascending(
            self.rules, lambda r: canon.byte_order_key(str(r.rule_id)), where="RuleTable.rules"
        )
        object.__setattr__(self, "_by_id", {str(r.rule_id): r for r in self.rules})

    def get(self, rule_id: str) -> CompiledRule:
        return self._by_id[rule_id]

    @property
    def detect_rules(self) -> tuple[CompiledRule, ...]:
        return tuple(r for r in self.rules if not r.is_obligation)

    @property
    def obligation_rules(self) -> tuple[CompiledRule, ...]:
        return tuple(r for r in self.rules if r.is_obligation)

    def cae_bytes(self) -> bytes:
        """The canonical AST encoding of 68.4.

        `cae := "CAE1" u32(rule_count) rule*` with rules sorted by rule id, and
        `rule := u16(rule_id) atom(head) u8(n) atom{n} guard u8(n_src) srcid{n_src}
        u8(silent_possible) u64le(mask)`. The mask is little-endian because the encoding
        names it that way; every other integer uses the foundation's big-endian helpers, so
        there is exactly one endianness exception and it is here.
        """
        out = bytearray(b"CAE1")
        out += canon.u32(len(self.rules))
        for compiled in self.rules:
            out += canon.u16(int(str(compiled.rule_id.snake)[1:]))
            out += canon.utf8_text(compiled.head.text())
            out += canon.u8(len(compiled.body))
            for pattern in compiled.body:
                out += canon.utf8_text(pattern.text())
            out += compiled.guard_bytes()
            sources = compiled.rule.producing_sources
            out += canon.u8(len(sources))
            for source_id in sources:
                out += canon.ascii_text(source_id)
            out += canon.u8(1 if compiled.rule.silent_possible else 0)
            out += compiled.mask.to_bytes(8, "little", signed=False)
        return bytes(out)

    @property
    def guard_ast_hash(self) -> str:
        return canon.hash_ref("cae", self.cae_bytes())

    @property
    def rules_hash(self) -> str:
        """The CAE plus the per-rule metadata record. Never the file bytes.

        Reflowing a comment must not invalidate an archived certificate, which is why this
        and `rules_text_hash` are two different digests and only this one is enforced.
        """
        payload = self.cae_bytes() + canon.ordered_seq(
            compiled.rule.metadata_bytes() for compiled in self.rules
        )
        return canon.hash_ref("rules", payload)

    @property
    def catalog_bits_hash(self) -> str:
        return self.bits.catalog_bits_hash

    @property
    def controls_hash(self) -> str:
        return self.catalog.controls_hash

    def literals(self) -> tuple[model.ThresholdLiteral, ...]:
        return self.bits.literals()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _lint_no_delete_effect(raw: dict[str, object], *, where: str) -> None:
    """Reject any rule that expresses a retraction.

    A rule table whose facts can be withdrawn is not a monotone program, and a fixpoint
    over a non-monotone program has no least model to certify. Expiry belongs in the tick
    index: a later fact is not derived. Rejecting the key is stronger than ignoring it,
    because an ignored key reads as supported.
    """
    for key, value in raw.items():
        if key in BANNED_EFFECT_KEYS:
            raise SchemaError(
                f"{where}: key {key!r} would express a delete effect; facts are append-only "
                "and expiry is modelled as a later fact not being derived",
                code="E-SCHEMA-UNKNOWN",
            )
        if isinstance(value, str) and value.strip().lower() in _BANNED_EFFECT_VALUES:
            raise SchemaError(
                f"{where}: {key} = {value!r} would express a delete effect",
                code="E-SCHEMA-UNKNOWN",
            )


def _compile_one(
    raw: dict[str, object], catalog: Catalog, bits: BitTable, index: int
) -> CompiledRule:
    rule_name = str(raw.get("id", f"<rule {index}>"))
    where = f"rules.toml[{rule_name}]"
    _lint_no_delete_effect(raw, where=where)

    if _RULE_ID.match(rule_name) is None:
        raise SchemaError(f"{where}: rule id must match ^r[0-9]{{4}}$")

    head = parse_pattern(str(raw["head"]))
    body = tuple(parse_pattern(str(p)) for p in raw.get("body", ()))
    if not body:
        raise SchemaError(f"{where}: a rule with no body would be an unconditional assertion")
    if len(body) > len(SLOT_NAMES):
        raise SchemaError(f"{where}: {len(body)} body patterns; the slice narrows to 4")

    persistence = str(raw.get("persistence", "instant"))
    if persistence not in _ALLOWED_PERSISTENCE:
        raise SchemaError(
            f"{where}: persistence {persistence!r} is deferred in this slice; only "
            f"{sorted(_ALLOWED_PERSISTENCE)} is implemented, and treating it as 'instant' "
            "would silently change what the rule means"
        )

    for code in raw.get("attck", ()):
        if _ATTCK.match(str(code)) is None:
            raise SchemaError(f"{where}: {code!r} is not an ATT&CK id")

    temporal_raw = {str(k): str(v) for k, v in dict(raw.get("temporal", {})).items()}
    temporal = _parse_temporal(temporal_raw, body, where=where)

    when = compile_when(str(raw.get("when", "")), where=f"{where}.when")
    terms = compile_blocked_when(
        str(raw.get("blocked_when", "")), catalog, bits, where=f"{where}.blocked_when"
    )
    blockers = _terms_to_masks(terms, bits, where=f"{where}.blocked_when")

    silent_bind_kinds = tuple(
        sorted(
            (str(k), str(v))
            for k, v in dict(raw.get("silent_bind_kinds", {})).items()
        )
    )

    body_vars = {name for pattern in body for name in pattern.variables}
    bound = body_vars | {name for name, _ in silent_bind_kinds}
    unbound = sorted(set(head.variables) - bound)
    if unbound:
        raise SchemaError(
            f"{where}: head variables {unbound} are not bound by the body and are not "
            "declared in silent_bind_kinds; an unbound head variable has no ground value"
        )

    rule = model.Rule(
        rule_id=RuleId.of(rule_name),
        rule_version=str(raw["version"]),
        dimension=DimensionId.of(str(raw["dimension"])),
        kind=model.RuleKind(str(raw["kind"])),
        head=head.text(),
        body=tuple(p.text() for p in body),
        producing_sources=tuple(
            sorted(
                (SourceId.of(str(s)) for s in raw.get("producing_sources", ())),
                key=lambda s: canon.byte_order_key(str(s)),
            )
        ),
        silent_possible=bool(raw.get("silent_possible", False)),
        when=str(raw.get("when", "")),
        blocked_when=str(raw.get("blocked_when", "")),
        temporal=tuple(sorted(temporal_raw.items())),
        persistence=persistence,
        evidence=tuple(str(e) for e in raw.get("evidence", ())),
        causal_relation=str(raw.get("causal_relation", "")),
        attck=tuple(sorted((str(a) for a in raw.get("attck", ())), key=canon.byte_order_key)),
        note=str(raw.get("note", "")),
    )

    if rule.silent_possible and rule.kind is model.RuleKind.DETECT and not rule.producing_sources:
        raise SchemaError(
            f"{where}: silent_possible with no producing_sources; there would be nothing "
            "whose blindness could licence the instance"
        )

    return CompiledRule(
        rule=rule,
        head=head,
        body=body,
        when=when,
        blocker_terms=terms,
        blockers=blockers,
        temporal=temporal,
        silent_bind_kinds=silent_bind_kinds,
    )


def compile_rules(rules_path: Path, catalog: Catalog, bits: BitTable) -> RuleTable:
    """Load and compile the rule table against one catalog and one bit lock.

    The catalog and the lock are parameters rather than module state, because a mask is
    only meaningful beside the table that assigned its bits and a compilation that silently
    picked up a different lock would produce masks nothing downstream could interpret.
    """
    bits.check_covers(catalog)
    text_bytes = rules_path.read_bytes()
    if b"\r" in text_bytes:
        raise GuardError(f"{rules_path}: a CR byte in rule text", code="E-LEX-001")
    document = tomllib.loads(text_bytes.decode("utf-8"))
    raw_rules = document.get("rule", ())
    if not raw_rules:
        raise SchemaError(f"{rules_path}: the table declares no rules")

    compiled = [
        _compile_one(dict(raw), catalog, bits, index) for index, raw in enumerate(raw_rules)
    ]
    compiled.sort(key=lambda c: canon.byte_order_key(str(c.rule_id)))

    heads = {c.head.predicate for c in compiled}
    axiom_predicates = tuple(
        sorted(
            {p.predicate for c in compiled for p in c.body} - heads,
            key=canon.byte_order_key,
        )
    )

    for entry in compiled:
        _check_arities(entry, compiled)
        _check_axiom_order(entry, axiom_predicates)
        if not entry.is_obligation and not any(
            p.predicate in axiom_predicates for p in entry.body
        ):
            raise SchemaError(
                f"rules.toml[{entry.rule_id.snake}]: a detect rule with no axiom body "
                "pattern would ground an OBSERVED instance carrying no evidence"
            )

    return RuleTable(
        rules=tuple(compiled),
        catalog=catalog,
        bits=bits,
        rules_text_hash=canon.hash_ref("rules_text", text_bytes),
        axiom_predicates=axiom_predicates,
    )


def _check_arities(entry: CompiledRule, table: list[CompiledRule]) -> None:
    """Every occurrence of a predicate must agree on arity, head or body."""
    arities: dict[str, int] = {}
    for other in table:
        for pattern in (other.head, *other.body):
            previous = arities.setdefault(pattern.predicate, pattern.arity)
            if previous != pattern.arity:
                raise SchemaError(
                    f"predicate {pattern.predicate!r} appears with arity {previous} and "
                    f"{pattern.arity}; a predicate has one arity"
                )
    if entry.temporal is not None and entry.temporal.of_pattern is not None:
        absent = entry.temporal.of_pattern
        declared = arities.get(absent.predicate)
        if declared is not None and declared != absent.arity:
            raise SchemaError(
                f"{entry.rule_id}: absence pattern {absent.predicate!r} has arity "
                f"{absent.arity}, declared {declared}"
            )


def _check_axiom_order(entry: CompiledRule, axiom_predicates: tuple[str, ...]) -> None:
    """An axiom pattern lists its entity variables in ascending byte order.

    Those variable names are the entity-resolution role names, and the seeded fact orders
    its argument vector by role name. Requiring the pattern to be written in the same order
    keeps that correspondence in one place: a pattern written in another order would bind
    its variables to the wrong arguments silently.
    """
    patterns = list(entry.body)
    if entry.temporal is not None and entry.temporal.of_pattern is not None:
        patterns.append(entry.temporal.of_pattern)
    for pattern in patterns:
        if pattern.predicate not in axiom_predicates:
            continue
        canon.check_strictly_ascending(
            pattern.entity_vars,
            canon.byte_order_key,
            where=f"{entry.rule_id}: axiom pattern {pattern.predicate}",
        )
