"""S5 entity resolution: bundle records become entity bindings, by exact joins only.

WHAT THIS STAGE DOES. For every bundle record and every declared join rule, it looks the
record's attribute value up in the scenario's entity table by EXACT STRING EQUALITY and
binds a role to an entity. There is no fuzzy matching, no edit distance, no similarity,
no scoring and no threshold anywhere in this module, so naming the join rule that fired
is a complete account of why two records were merged.

THREE OUTCOMES, AND AMBIGUOUS IS ONE OF THEM. A role on a record is RESOLVED when the
declared rules produce exactly one entity for it, UNRESOLVED when a rule's attribute is
present but joins to nothing, and AMBIGUOUS when they produce more than one. AMBIGUOUS is
a first-class state that propagates: it is written into `er.json`, it raises the run flag
`er_ambiguous` (bit 3, soundness class), which blocks ROBUST and forces witness_class
CONTESTED on an UNSAFE verdict. It is never resolved by picking a candidate, because a
bad merge fabricates the leaves of a witness tree rather than merely weakening it.

WHY A ROLE WITH NO CANDIDATES IS NOT A BINDING. An unresolved role produces no binding at
all. It is counted and reported so that the later evaluation can compare this stage's
counts against the generator's truth, but a guess in a binding position would put an
entity into a fact that no record supports.

KINDS. The data contract for this stage lists kinds `principal`, `device`, `credential`,
`session`, `service`, `resource`, `zone`. Section 57.2 is normative over every other
section and fixes `EntityKind` as a closed twelve that contains none of `principal`,
`device` or `zone`. This module implements section 57 and translates at its own boundary:
`principal` joins mint an `account`, `device` joins mint a `host`. `zone` and `service`
have no join rule in the contract's closed five, so this stage resolves neither; a zone
is a scenario attribute of a resource, not a joined entity.

DETERMINISM. No wall clock, no environment, no randomness. Rules are applied in sorted
order, candidates are accumulated into sorted tuples, and every emitted array is strictly
ascending under its declared key, so the input order of the rule table cannot reach
`er.json`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import SchemaError
from spectra_core.ids import ENTITY_KINDS, EntityId, EventId, check_snake
from spectra_core.model import CanonicalEvent, Entity

from spectra_vs.ingest import scf_line

__all__ = [
    "ER_FILE_NAME",
    "ER_QUALITY_FILE_NAME",
    "ER_SCHEMA",
    "JOIN_RULE_IDS",
    "AmbiguousRole",
    "Binding",
    "JoinRule",
    "ResolveCounts",
    "ResolveResult",
    "Resolution",
    "UnresolvedRole",
    "join_rules_from_tables",
    "resolve",
]

ER_FILE_NAME: Final[str] = "er.json"

#: Resolution quality is reported beside `er.json` rather than inside it. `er_hash` is
#: pinned by the certificate and `er.json`'s member set is enumerated by the contract, so
#: a counts member added there would be rejected as an unknown member on verify.
ER_QUALITY_FILE_NAME: Final[str] = "er_quality.json"

ER_SCHEMA: Final[str] = "spectra.vs.er/1"

#: The closed set of join rules. Exact string joins against the scenario entity tables,
#: and nothing else exists.
JOIN_RULE_IDS: Final[frozenset[str]] = frozenset(
    {
        "r_exact_principal",
        "r_exact_device",
        "r_exact_token",
        "r_exact_session_by_token",
        "r_exact_resource",
    }
)

_ATTR_KEY_FORM: Final = re.compile(r"\A[a-z0-9_]+\Z")


class Resolution(StrEnum):
    """The outcome of one (record, role) join. AMBIGUOUS is not a failure mode."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# The rule table
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JoinRule:
    """One exact join: an attribute key, a role, a kind, and the table to look in.

    The table is carried by the rule rather than looked up globally so that a rule is
    self-contained and two rules may target the same role from different tables - which
    is precisely how an honest AMBIGUOUS arises rather than being contrived.

    `table` maps a join key to the CANDIDATE canonical names it denotes. More than one
    name for a key is how the scenario declares a genuine collision, for example one
    credential id issued to two subjects. Keys are strictly ascending; so is each
    candidate tuple.
    """

    join_rule_id: str
    role: str
    attr_key: str
    kind: str
    table: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if self.join_rule_id not in JOIN_RULE_IDS:
            raise SchemaError(
                f"JoinRule: {self.join_rule_id!r} is not one of the closed five "
                f"{sorted(JOIN_RULE_IDS)}"
            )
        check_snake(self.role, where="JoinRule.role")
        if _ATTR_KEY_FORM.match(self.attr_key) is None:
            raise SchemaError(f"JoinRule: attr_key {self.attr_key!r} is not ASCII [a-z0-9_]+")
        if self.kind not in ENTITY_KINDS:
            raise SchemaError(f"JoinRule: kind {self.kind!r} is not a section 57.2 EntityKind")
        canon.check_strictly_ascending(
            [key for key, _ in self.table], canon.byte_order_key, where="JoinRule.table keys"
        )
        for key, names in self.table:
            if not names:
                raise SchemaError(f"JoinRule: table key {key!r} denotes no entity")
            canon.check_strictly_ascending(
                names, canon.byte_order_key, where=f"JoinRule.table[{key!r}]"
            )

    def sort_key(self) -> tuple[bytes, bytes, bytes]:
        return (
            canon.byte_order_key(self.join_rule_id),
            canon.byte_order_key(self.role),
            canon.byte_order_key(self.attr_key),
        )

    def lookup(self, value: str) -> tuple[str, ...]:
        """Exact string membership. A miss is `()`, never a nearest neighbour."""
        for key, names in self.table:
            if key == value:
                return names
        return ()


def _table(names: Iterable[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Build the identity table: each declared id joins to itself, exactly once."""
    ordered = canon.sorted_unique(names)
    return tuple((name, (name,)) for name in ordered)


def join_rules_from_tables(
    *,
    principals: Sequence[str] = (),
    devices: Sequence[str] = (),
    credentials: Sequence[str] = (),
    resources: Sequence[str] = (),
    principal_attr: str = "principal",
    device_attr: str = "device",
    token_attr: str = "token",
    resource_attr: str = "resource",
) -> tuple[JoinRule, ...]:
    """Build the closed five from the scenario's entity tables.

    The attribute keys are parameters rather than constants because the attribute
    vocabulary belongs to the scenario and its generator, not to this stage; the defaults
    are the obvious names and a caller whose scenario differs passes its own. A rule whose
    table is empty is omitted rather than declared, so a scenario that has no devices does
    not report every device attribute as UNRESOLVED against an empty table.

    `r_exact_session_by_token` mints a `session` whose canonical name is the credential id
    that established it. The contract declares no session table, so the token is the only
    exact join available; naming the session after it is the conservative reading and is
    stated here rather than inferred at the call site.
    """
    rules: list[JoinRule] = []
    if principals:
        rules.append(
            JoinRule("r_exact_principal", "principal", principal_attr, "account", _table(principals))
        )
    if devices:
        rules.append(JoinRule("r_exact_device", "device", device_attr, "host", _table(devices)))
    if credentials:
        credential_table = _table(credentials)
        rules.append(JoinRule("r_exact_token", "token", token_attr, "credential", credential_table))
        rules.append(
            JoinRule("r_exact_session_by_token", "session", token_attr, "session", credential_table)
        )
    if resources:
        rules.append(
            JoinRule("r_exact_resource", "resource", resource_attr, "resource", _table(resources))
        )
    return tuple(sorted(rules, key=lambda rule: rule.sort_key()))


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Binding:
    """One resolved role on one record."""

    event_id: EventId
    role: str
    entity_id: EntityId
    join_rule_id: str

    def sort_key(self) -> tuple[bytes, bytes]:
        return (canon.byte_order_key(str(self.event_id)), canon.byte_order_key(self.role))


@dataclass(frozen=True, slots=True)
class AmbiguousRole:
    """One role that exact joins bound to more than one entity. Never guessed."""

    event_id: EventId
    role: str
    candidates: tuple[EntityId, ...]

    def sort_key(self) -> tuple[bytes, bytes]:
        return (canon.byte_order_key(str(self.event_id)), canon.byte_order_key(self.role))


@dataclass(frozen=True, slots=True)
class UnresolvedRole:
    """One role whose attribute was present and joined to nothing.

    `value` is the telemetry string that failed to join. It is telemetry, not truth, and
    keeping it is what lets the later evaluation say WHICH identifiers the entity tables
    are missing rather than only how many.
    """

    event_id: EventId
    role: str
    attr_key: str
    value: str

    def sort_key(self) -> tuple[bytes, bytes, bytes]:
        return (
            canon.byte_order_key(str(self.event_id)),
            canon.byte_order_key(self.role),
            canon.byte_order_key(self.attr_key),
        )


@dataclass(frozen=True, slots=True)
class ResolveCounts:
    """Resolution quality, for comparison against the generator's truth at evaluation.

    These are counts of what this stage did. They are not a score, not a rate and not a
    quality percentage; nothing here is normalised to [0,1] and nothing may render them
    as an accuracy.
    """

    events_total: int
    events_with_bindings: int
    roles_resolved: int
    roles_ambiguous: int
    roles_unresolved: int
    entities: int
    by_role: tuple[tuple[str, int, int, int], ...]
    by_join_rule: tuple[tuple[str, int], ...]
    by_kind: tuple[tuple[str, int], ...]

    def as_obj(self) -> dict[str, Any]:
        return {
            "by_join_rule": [
                {"join_rule_id": rule, "resolved": count} for rule, count in self.by_join_rule
            ],
            "by_kind": [{"entities": count, "kind": kind} for kind, count in self.by_kind],
            "by_role": [
                {"ambiguous": amb, "resolved": res, "role": role, "unresolved": unres}
                for role, res, amb, unres in self.by_role
            ],
            "entities": self.entities,
            "events_total": self.events_total,
            "events_with_bindings": self.events_with_bindings,
            "roles_ambiguous": self.roles_ambiguous,
            "roles_resolved": self.roles_resolved,
            "roles_unresolved": self.roles_unresolved,
        }


@dataclass(frozen=True, slots=True)
class ResolveResult:
    """The entity map, its digest, and the account of what did not resolve."""

    entities: tuple[Entity, ...]
    bindings: tuple[Binding, ...]
    ambiguous: tuple[AmbiguousRole, ...]
    unresolved: tuple[UnresolvedRole, ...]
    counts: ResolveCounts
    er_bytes: bytes
    er_hash: str

    @property
    def er_ambiguous(self) -> bool:
        """Run flag bit 3. Blocks ROBUST; forces witness_class CONTESTED on UNSAFE."""
        return bool(self.ambiguous)

    def er_obj(self) -> dict[str, Any]:
        """Exactly the members the EntityMap contract enumerates, and no others."""
        return {
            "ambiguous": [
                {
                    "candidates": [str(candidate) for candidate in row.candidates],
                    "event_id": str(row.event_id),
                    "role": row.role,
                }
                for row in self.ambiguous
            ],
            "bindings": [
                {
                    "entity_id": str(row.entity_id),
                    "event_id": str(row.event_id),
                    "role": row.role,
                }
                for row in self.bindings
            ],
            "entities": [
                {
                    "canonical_name": entity.canonical_name,
                    "entity_id": str(entity.entity_id),
                    "join_rule_id": entity.join_rule_id,
                    "kind": entity.kind,
                    "resolved_from": [str(event_id) for event_id in entity.resolved_from],
                }
                for entity in self.entities
            ],
            "schema": ER_SCHEMA,
        }

    def quality_obj(self) -> dict[str, Any]:
        return {
            "counts": self.counts.as_obj(),
            "er_ambiguous": self.er_ambiguous,
            "er_hash": self.er_hash,
            "schema": "spectra.vs.er_quality/1",
            "unresolved": [
                {
                    "attr_key": row.attr_key,
                    "event_id": str(row.event_id),
                    "role": row.role,
                    "value": row.value,
                }
                for row in self.unresolved
            ],
        }

    def write(self, run_dir: Path | str) -> tuple[Path, Path]:
        """Write `er.json` and `er_quality.json`; return both paths."""
        directory = Path(run_dir)
        directory.mkdir(parents=True, exist_ok=True)
        er_path = directory / ER_FILE_NAME
        er_path.write_bytes(self.er_bytes)
        quality_path = directory / ER_QUALITY_FILE_NAME
        quality_path.write_bytes(scf_line(self.quality_obj()))
        return (er_path, quality_path)


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------


def resolve(bundle: Sequence[CanonicalEvent], rules: Sequence[JoinRule]) -> ResolveResult:
    """Resolve every record's roles against the declared exact joins.

    `rules` is required and has no default. A default rule table would make this stage
    guess the scenario's attribute vocabulary, and a silently wrong guess resolves nothing
    while reporting a clean run; `join_rules_from_tables` builds the closed five from the
    scenario's own entity tables.
    """
    ordered_rules = _check_rules(rules)

    minted: dict[str, Entity] = {}
    resolved_from: dict[str, set[str]] = {}
    bindings: list[Binding] = []
    ambiguous: list[AmbiguousRole] = []
    unresolved: list[UnresolvedRole] = []
    events_with_bindings = 0
    by_role: dict[str, list[int]] = {}
    by_join_rule: dict[str, int] = {}

    for event in bundle:
        if not isinstance(event, CanonicalEvent):
            raise SchemaError(
                f"resolve: bundle must hold CanonicalEvent, got {type(event).__name__}"
            )
        attrs = dict(event.attrs)
        # role -> attr_key present at all, and role -> {entity_id: (join_rule_id, kind, name)}
        present: dict[str, str] = {}
        candidates: dict[str, dict[str, tuple[str, str, str]]] = {}
        for rule in ordered_rules:
            value = attrs.get(rule.attr_key)
            if value is None:
                continue
            present.setdefault(rule.role, rule.attr_key)
            bucket = candidates.setdefault(rule.role, {})
            for name in rule.lookup(value):
                entity_id = _entity_id(rule.kind, name)
                if entity_id not in bucket:
                    bucket[entity_id] = (rule.join_rule_id, rule.kind, name)

        bound_here = False
        for role in sorted(present, key=canon.byte_order_key):
            counters = by_role.setdefault(role, [0, 0, 0])
            bucket = candidates.get(role) or {}
            if not bucket:
                unresolved.append(
                    UnresolvedRole(
                        event_id=event.event_id,
                        role=role,
                        attr_key=present[role],
                        value=attrs[present[role]],
                    )
                )
                counters[2] += 1
                continue
            entity_ids = sorted(bucket, key=canon.byte_order_key)
            for entity_id in entity_ids:
                join_rule_id, kind, name = bucket[entity_id]
                _remember(minted, resolved_from, entity_id, kind, name, join_rule_id)
            if len(entity_ids) == 1:
                entity_id = entity_ids[0]
                join_rule_id = bucket[entity_id][0]
                bindings.append(
                    Binding(
                        event_id=event.event_id,
                        role=role,
                        entity_id=EntityId(entity_id),
                        join_rule_id=join_rule_id,
                    )
                )
                resolved_from[entity_id].add(str(event.event_id))
                counters[0] += 1
                by_join_rule[join_rule_id] = by_join_rule.get(join_rule_id, 0) + 1
                bound_here = True
            else:
                ambiguous.append(
                    AmbiguousRole(
                        event_id=event.event_id,
                        role=role,
                        candidates=tuple(EntityId(value) for value in entity_ids),
                    )
                )
                counters[1] += 1
        if bound_here:
            events_with_bindings += 1

    entities = _finalise_entities(minted, resolved_from)
    bindings.sort(key=lambda row: row.sort_key())
    ambiguous.sort(key=lambda row: row.sort_key())
    unresolved.sort(key=lambda row: row.sort_key())

    counts = ResolveCounts(
        events_total=len(bundle),
        events_with_bindings=events_with_bindings,
        roles_resolved=len(bindings),
        roles_ambiguous=len(ambiguous),
        roles_unresolved=len(unresolved),
        entities=len(entities),
        by_role=tuple(
            (role, by_role[role][0], by_role[role][1], by_role[role][2])
            for role in sorted(by_role, key=canon.byte_order_key)
        ),
        by_join_rule=tuple(
            (rule, by_join_rule[rule]) for rule in sorted(by_join_rule, key=canon.byte_order_key)
        ),
        by_kind=_by_kind(entities),
    )

    partial = ResolveResult(
        entities=entities,
        bindings=tuple(bindings),
        ambiguous=tuple(ambiguous),
        unresolved=tuple(unresolved),
        counts=counts,
        er_bytes=b"",
        er_hash="",
    )
    er_bytes = scf_line(partial.er_obj())
    return ResolveResult(
        entities=partial.entities,
        bindings=partial.bindings,
        ambiguous=partial.ambiguous,
        unresolved=partial.unresolved,
        counts=partial.counts,
        er_bytes=er_bytes,
        er_hash=canon.hash_ref("er", er_bytes),
    )


def _check_rules(rules: Sequence[JoinRule]) -> tuple[JoinRule, ...]:
    ordered = tuple(sorted(rules, key=lambda rule: rule.sort_key()))
    seen: set[tuple[str, str, str]] = set()
    for rule in ordered:
        if not isinstance(rule, JoinRule):
            raise SchemaError(f"resolve: rules must be JoinRule, got {type(rule).__name__}")
        key = (rule.join_rule_id, rule.role, rule.attr_key)
        if key in seen:
            raise SchemaError(f"resolve: join rule {key} is declared twice")
        seen.add(key)
    return ordered


def _entity_id(kind: str, canonical_name: str) -> str:
    """The id preimage is `canonical_name` then `kind`, and deliberately nothing else.

    Excluding the records it was resolved from is what keeps one entity's id stable
    across completeness levels; if it shifted under degradation, every fact naming the
    entity would change key and the two cells could not be compared at all.
    """
    payload = canon.utf8_text(canonical_name) + canon.ascii_text(kind)
    return str(EntityId.mint(kind, payload))


def _remember(
    minted: dict[str, Entity],
    resolved_from: dict[str, set[str]],
    entity_id: str,
    kind: str,
    canonical_name: str,
    join_rule_id: str,
) -> None:
    """Record a candidate entity, keeping the bytewise-least join rule that produced it.

    An entity reachable through two rules needs one `join_rule_id` in the artifact, and
    the smallest is a total, history-independent choice; taking the first seen would put
    record order into the bytes.
    """
    resolved_from.setdefault(entity_id, set())
    existing = minted.get(entity_id)
    if existing is None:
        minted[entity_id] = Entity(
            entity_id=EntityId(entity_id),
            kind=kind,
            canonical_name=canonical_name,
            join_rule_id=join_rule_id,
        )
        return
    if canon.byte_order_key(join_rule_id) < canon.byte_order_key(existing.join_rule_id):
        minted[entity_id] = Entity(
            entity_id=existing.entity_id,
            kind=existing.kind,
            canonical_name=existing.canonical_name,
            join_rule_id=join_rule_id,
        )


def _finalise_entities(
    minted: Mapping[str, Entity], resolved_from: Mapping[str, set[str]]
) -> tuple[Entity, ...]:
    """Attach `resolved_from` and return the entities sorted by `entity_id`.

    Candidates named only in an `ambiguous` row are included with an empty
    `resolved_from`, so every id an artifact cites is defined in the same artifact. An
    empty `resolved_from` is the honest statement that no record resolved to this entity
    unambiguously.
    """
    out: list[Entity] = []
    for entity_id in sorted(minted, key=canon.byte_order_key):
        entity = minted[entity_id]
        event_ids = tuple(
            EventId(value) for value in sorted(resolved_from.get(entity_id, set()), key=canon.byte_order_key)
        )
        out.append(
            Entity(
                entity_id=entity.entity_id,
                kind=entity.kind,
                canonical_name=entity.canonical_name,
                join_rule_id=entity.join_rule_id,
                resolved_from=event_ids,
            )
        )
    canon.check_strictly_ascending(
        out, lambda entity: canon.byte_order_key(str(entity.entity_id)), where="resolve: entities"
    )
    return tuple(out)


def _by_kind(entities: Sequence[Entity]) -> tuple[tuple[str, int], ...]:
    table: dict[str, int] = {}
    for entity in entities:
        table[entity.kind] = table.get(entity.kind, 0) + 1
    return tuple((kind, table[kind]) for kind in sorted(table, key=canon.byte_order_key))
