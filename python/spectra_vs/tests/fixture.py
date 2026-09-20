"""The shared fixture: one simulated scenario, two completeness cells, one liveness view.

WHAT THIS IS NOT. It is not a measurement, not a benchmark, not a record of anything that
happened. It is a hand-built model of the `vs-01-token-pivot` family, small enough to read
and large enough to exercise both routes to the goal, the three temporal operators, the
obligation axioms and the two completeness cells the slice exists to contrast.

It builds the bundle records directly rather than running S2/S3/S4, because those stages
are not this commit's. The records are the shape those stages produce: canonical events
with entity-resolution bindings beside them. No ground truth is constructed and none is
read; the annotations that would carry it are the oracle channel's and never the kernel's.

Every instant is an integer nanosecond offset from a fixed epoch constant. Nothing here
reads a wall clock, an environment variable or a random source.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Final

from spectra_core import model
from spectra_core.ids import EventId, RecordId, SourceId
from spectra_vs import envelope as envelope_mod
from spectra_vs import rules as rules_mod
from spectra_vs.ground import Binding

#: A fixed instant, chosen once and never derived from a clock.
EPOCH_NS: Final[int] = 1_760_000_000_000_000_000
SECOND: Final[int] = 1_000_000_000

#: The liveness span the fixture's document covers.
SPAN_T0_NS: Final[int] = EPOCH_NS - 4 * 3600 * SECOND
SPAN_T1_NS: Final[int] = EPOCH_NS + 3600 * SECOND

#: The blind window of the degraded cell: the forty minutes covering the escalation.
BLIND_T0_NS: Final[int] = EPOCH_NS + 150 * SECOND
BLIND_T1_NS: Final[int] = EPOCH_NS + 300 * SECOND


#: The repository root, found by walking up from this file rather than by a fixed hop count.
_REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parents[3]

#: The real catalog and the real lock. The fixture loads them rather than restating them,
#: so a level name this scenario references and the catalog stops defining turns a test red
#: instead of drifting quietly apart from the file the pipeline actually compiles against.
CONTROLS_TOML: Final[pathlib.Path] = _REPO_ROOT / "config" / "vs" / "controls.toml"
BITS_LOCK: Final[pathlib.Path] = _REPO_ROOT / "config" / "vs" / "catalog-bits.lock"


def catalog() -> rules_mod.Catalog:
    return rules_mod.load_catalog(CONTROLS_TOML)


def catalog_rows() -> list[dict[str, object]]:
    """The catalog as plain mappings, for a test that appends an unrelated control."""
    return [
        {
            "id": spec.control_id.snake,
            "title": spec.title,
            "levels": list(spec.levels),
            "dimensions": [d.snake for d in spec.dimensions],
            "provenance": spec.provenance,
        }
        for spec in catalog().controls
    ]


def bit_table() -> rules_mod.BitTable:
    """The committed lock when it exists, the canonical derivation when it does not.

    Deriving is only correct for a catalog that has never been edited; once the lock exists
    it is authoritative, because re-deriving after an edit would renumber pre-existing bits
    and silently invalidate every archived certificate.
    """
    if BITS_LOCK.exists():
        return rules_mod.load_bit_table(BITS_LOCK)
    return rules_mod.BitTable.derive(catalog())


def rule_table(rules_path) -> rules_mod.RuleTable:
    return rules_mod.compile_rules(rules_path, catalog(), bit_table())


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def entity(kind: str, name: str) -> model.Entity:
    return model.Entity.mint(kind, name, f"r_exact_{kind}")


ENTITIES: Final[dict[str, model.Entity]] = {
    "mallory": entity("user", "p_mallory"),
    "alice": entity("user", "p_alice"),
    "token": entity("credential", "c_token_1"),
    "gateway": entity("service", "s_gateway"),
    "doc1": entity("resource", "r_doc_1"),
    "doc2": entity("resource", "r_doc_2"),
    "doc3": entity("resource", "r_doc_3"),
    "export": entity("resource", "r_export_bundle"),
    "admin_role": entity("account", "a_role_admin"),
}


def entity_universe() -> tuple[model.Entity, ...]:
    return tuple(
        sorted(ENTITIES.values(), key=lambda e: str(e.entity_id))
    )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Emission:
    """One record plus the entity-resolution bindings S5 would have produced for it."""

    event: model.CanonicalEvent
    bindings: tuple[Binding, ...]


def make_event(
    source: str,
    seq: int,
    event_type: str,
    t_ns: int,
    roles: dict[str, model.Entity],
) -> Emission:
    """Build one canonical event and its bindings.

    The event id is minted from the event's own identity bytes, which is what ingest does;
    building it twice rather than guessing is how the fixture stays consistent with the
    foundation's identity rule instead of restating it.
    """
    draft = model.CanonicalEvent(
        event_id=EventId.mint(b"draft"),
        record_id=RecordId.mint(b"draft"),
        source_id=SourceId.of(source),
        seq=seq,
        event_type=event_type,
        t_evt_ns=t_ns,
        t_ing_ns=t_ns + SECOND,
        attrs=(),
    )
    identity = draft.identity_bytes()
    event = model.CanonicalEvent(
        event_id=EventId.mint(identity),
        record_id=RecordId.mint(identity),
        source_id=draft.source_id,
        seq=seq,
        event_type=event_type,
        t_evt_ns=t_ns,
        t_ing_ns=t_ns + SECOND,
        attrs=(),
    )
    bindings = tuple(
        Binding(event_id=event.event_id, role=role, entity_id=target.entity_id)
        for role, target in sorted(roles.items())
    )
    return Emission(event=event, bindings=bindings)


def _emissions(*, include_iam: bool) -> tuple[Emission, ...]:
    """The simulated chain. `include_iam` is the difference between the two cells.

    At the lower completeness the degrader has deleted the iam_audit records covering the
    escalation and its approval, which is what makes that window blind rather than empty.
    """
    e = ENTITIES
    out = [
        make_event(
            "idp_auth", 0, "idp.refresh_exchange", EPOCH_NS,
            {"credential": e["token"], "principal": e["mallory"]},
        ),
        make_event(
            "gw_access", 0, "gw.request", EPOCH_NS + 60 * SECOND,
            {"principal": e["mallory"], "service": e["gateway"]},
        ),
        make_event(
            "res_access", 0, "res.read", EPOCH_NS + 120 * SECOND,
            {"principal": e["mallory"], "resource": e["doc1"]},
        ),
        make_event(
            "res_access", 1, "res.read", EPOCH_NS + 130 * SECOND,
            {"principal": e["mallory"], "resource": e["doc2"]},
        ),
        make_event(
            "res_access", 2, "res.read", EPOCH_NS + 140 * SECOND,
            {"principal": e["mallory"], "resource": e["doc3"]},
        ),
        make_event(
            "res_access", 3, "res.export", EPOCH_NS + 220 * SECOND,
            {"principal": e["mallory"], "resource": e["export"]},
        ),
        make_event(
            "net_flow", 0, "net.connection", EPOCH_NS + 10 * SECOND,
            {"principal": e["alice"], "service": e["gateway"]},
        ),
    ]
    if include_iam:
        out.append(
            make_event(
                "iam_audit", 0, "iam.approval_granted", EPOCH_NS - 3600 * SECOND,
                {"principal": e["mallory"], "role": e["admin_role"]},
            )
        )
        out.append(
            make_event(
                "iam_audit", 1, "iam.role_assumed", EPOCH_NS + 200 * SECOND,
                {"principal": e["mallory"], "role": e["admin_role"]},
            )
        )
    return tuple(out)


def cell(complete: bool) -> tuple[tuple[model.CanonicalEvent, ...], tuple[Binding, ...]]:
    """The bundle of one completeness cell: `True` for c=100%, `False` for the degraded one."""
    emissions = _emissions(include_iam=complete)
    events = tuple(sorted((em.event for em in emissions), key=lambda ev: ev.sort_key()))
    bindings = tuple(
        sorted(
            (b for em in emissions for b in em.bindings),
            key=lambda b: b.sort_key(),
        )
    )
    return events, bindings


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------

_LIVE = model.LivenessVerdict.LIVE
_BLIND = model.LivenessVerdict.BLIND


def _timeline(source: str, integrity: str, intervals) -> envelope_mod.SourceLiveness:
    return envelope_mod.SourceLiveness(
        source_id=SourceId.of(source),
        integrity_class=model.IntegrityClass(integrity),
        intervals=tuple(intervals),
    )


def liveness(complete: bool) -> envelope_mod.LivenessView:
    """The liveness document of one cell, as S7 would have written it.

    `edr_host` is declared and emits nothing ever, so it is INSUFFICIENT in the profile and
    therefore BLIND everywhere, fail-closed. That is not a defect of the fixture: it is the
    permanent blind window that licenses the obligation axiom's GHOST.
    """
    full_live = (
        envelope_mod.LivenessInterval(SPAN_T0_NS, SPAN_T1_NS, _LIVE, "L_CALIBRATED_OK"),
    )
    if complete:
        iam = full_live
    else:
        iam = (
            envelope_mod.LivenessInterval(SPAN_T0_NS, BLIND_T0_NS, _LIVE, "L_CALIBRATED_OK"),
            envelope_mod.LivenessInterval(
                BLIND_T0_NS, BLIND_T1_NS, _BLIND, "B_GAP_EXCEEDS_THRESHOLD"
            ),
            envelope_mod.LivenessInterval(BLIND_T1_NS, SPAN_T1_NS, _LIVE, "L_CALIBRATED_OK"),
        )
    return envelope_mod.LivenessView(
        sources=tuple(
            sorted(
                (
                    _timeline("idp_auth", "chained", full_live),
                    _timeline("iam_audit", "chained", iam),
                    _timeline("gw_access", "sequenced", full_live),
                    _timeline("res_access", "none", full_live),
                    _timeline("net_flow", "none", full_live),
                    _timeline(
                        "edr_host",
                        "none",
                        (
                            envelope_mod.LivenessInterval(
                                SPAN_T0_NS, SPAN_T1_NS, _BLIND, "B_PROFILE_INSUFFICIENT"
                            ),
                        ),
                    ),
                ),
                key=lambda s: str(s.source_id),
            )
        )
    )
