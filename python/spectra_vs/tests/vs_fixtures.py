"""Fixtures for the S10 tests: the atom table and the two completeness cells.

These build the minimum viable scenario's PROGRAM SHAPE directly out of foundation
records, without running S2 through S9. That is deliberate: the S10 modules take a program
and an atom table and nothing else, so testing them against a hand-built program pins
their contract rather than the behaviour of stages that are not theirs.

NOTHING HERE READS GROUND TRUTH. There is no truth file in this fixture and no stage under
test could read one if there were.

THE TWO CELLS, in the language of the operative specification's minimum viable scenario:

  c=100%  Route A only. Both programs are identical, the clause database is the single
          corridor A, and the canonical cut raises one control.
  c=70%   Route A is unchanged. Route B exists in P_max only, resting on a licensed silent
          instance that a blind window on iam_audit permits. Corridor B joins the upper
          clause database and the upper cut raises a second control.
"""

from __future__ import annotations

from dataclasses import dataclass

from spectra_core import ids, model

from spectra_vs.cut import AtomTable, ControlSpec, derive_bit_positions
from spectra_vs.reach import ReachProgram

CONTROL_LEVELS: dict[str, int] = {
    "egress_seg": 2,
    "priv_approval": 2,
    "rate_limit": 1,
    "session_binding": 2,
    "token_expiry": 2,
}


def atom_table() -> AtomTable:
    """The nine-literal universe, with bits assigned as a fresh lock would assign them."""
    catalog = tuple(
        ControlSpec(
            control_id=ids.ControlId.of(name),
            title=name,
            levels=tuple(f"l{i}" for i in range(levels + 1)),
            dimensions=("resource",),
            provenance="fixture",
        )
        for name, levels in sorted(CONTROL_LEVELS.items())
    )
    return AtomTable.from_catalog(catalog, dict(derive_bit_positions(catalog)))


def _entity(kind: str, name: str) -> ids.EntityId:
    return ids.EntityId.mint(kind, name.encode("utf-8"))


def _fact(predicate: str, name: str, tick: int) -> model.Fact:
    return model.Fact.mint(predicate, (_entity("resource", name),), tick)


def _evidence(binding: str, marker: str, source: str, t_ns: int) -> model.EvidenceRef:
    return model.EvidenceRef(
        binding=binding,
        event_id=ids.EventId.mint(marker.encode("utf-8")),
        source_id=ids.SourceId.of(source),
        t_evt_ns=t_ns,
    )


def _blind_licence() -> model.Licence:
    """The licence the degraded cell rests on: a blind window on iam_audit.

    BLIND carries a reason and no witness. It is a permission for a step nobody could have
    seen, and it is never an observation.
    """
    return model.Licence.mint(
        source_id=ids.SourceId.of("iam_audit"),
        interval=model.Interval(1_707_004_800_000_000_000, 1_707_007_200_000_000_000),
        basis=model.LicenceBasis.BLIND,
        reason="B_GAP_EXCEEDS_THRESHOLD",
    )


@dataclass(frozen=True, slots=True)
class Cell:
    """One completeness cell: the two programs, the goal, and the licence, if any."""

    p_min: ReachProgram
    p_max: ReachProgram
    goal: ids.FactHash
    licence: model.Licence | None


def _bit(atoms: AtomTable, control: str, level: int) -> int:
    return 1 << atoms.literal_at(ids.ControlId.of(control), level).bit


def _route_a(atoms: AtomTable) -> tuple[tuple[model.RuleInstance, ...], model.Fact, model.Fact]:
    """k2 refresh exchange, k3 gateway call, k4 bulk read. Fully observed at c=100%."""
    seed = _fact("credential.held", "cred_victim_refresh", 1)
    goal = _fact("resource.bulk_read", "res_customer_records", 4)
    f_exchanged = _fact("credential.exchanged", "cred_victim_refresh", 2)
    f_gateway = _fact("api.called", "svc_gateway", 3)

    instances = (
        model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0001"),
            rule_version="1.0.0",
            head=f_exchanged.fact_key,
            body=(seed.fact_key,),
            blockers=(_bit(atoms, "token_expiry", 1),),
            observed=model.Observation.OBSERVED,
            tick=2,
            evidence=(_evidence("exchange", "k2", "idp_auth", 1_707_004_810_000_000_000),),
        ),
        model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0002"),
            rule_version="1.0.0",
            head=f_gateway.fact_key,
            body=(f_exchanged.fact_key,),
            blockers=(_bit(atoms, "session_binding", 1),),
            observed=model.Observation.OBSERVED,
            tick=3,
            evidence=(_evidence("call", "k3", "gw_access", 1_707_004_820_000_000_000),),
        ),
        model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0003"),
            rule_version="1.0.0",
            head=goal.fact_key,
            body=(f_gateway.fact_key,),
            blockers=tuple(
                sorted(
                    (_bit(atoms, "egress_seg", 1), _bit(atoms, "rate_limit", 1)),
                    key=lambda m: (m.bit_count(), m),
                )
            ),
            observed=model.Observation.OBSERVED,
            tick=4,
            evidence=(_evidence("read", "k4", "res_access", 1_707_004_830_000_000_000),),
        ),
    )
    return instances, seed, goal


def _route_b(
    atoms: AtomTable, goal: model.Fact, licence: model.Licence
) -> tuple[tuple[model.RuleInstance, ...], model.Fact]:
    """k5 unapproved role assumption, k6 admin export. Licensed, so P_max only.

    k6 carries no blocker: the export bypasses the egress path by construction, so no
    control in this catalog blocks it and corridor B is the singleton {priv_approval >= 1}
    that k5 contributes.
    """
    seed = _fact("identity.actor", "prn_operator", 1)
    f_assumed = _fact("privilege.escalated", "prn_operator", 5)
    instances = (
        model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0004"),
            rule_version="1.0.0",
            head=f_assumed.fact_key,
            body=(seed.fact_key,),
            blockers=(_bit(atoms, "priv_approval", 1),),
            observed=model.Observation.LICENSED,
            tick=5,
            license_ids=(licence.license_id,),
        ),
        model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0005"),
            rule_version="1.0.0",
            head=goal.fact_key,
            body=(f_assumed.fact_key,),
            blockers=(),
            observed=model.Observation.LICENSED,
            tick=6,
            license_ids=(licence.license_id,),
        ),
    )
    return instances, seed


def _program(
    kind: model.ProgramKind,
    instances: tuple[model.RuleInstance, ...],
    axioms: tuple[model.Fact, ...],
    goal: model.Fact,
) -> ReachProgram:
    keys = tuple(sorted((a.fact_key for a in axioms), key=str))
    return ReachProgram.build(
        kind=kind,
        instances=tuple(sorted(instances, key=lambda i: str(i.instance_id))),
        axioms=keys,
        goal=goal.fact_key,
        axiom_evidence=tuple(
            (key, (ids.EventId.mint(b"axiom:" + key.encode("utf-8")),))
            for key in keys
        ),
    )


def cell_complete(atoms: AtomTable) -> Cell:
    """c=100%: Route B is derivable in neither program, so the two sides coincide."""
    route_a, seed_a, goal = _route_a(atoms)
    return Cell(
        p_min=_program(model.ProgramKind.P_MIN, route_a, (seed_a,), goal),
        p_max=_program(model.ProgramKind.P_MAX, route_a, (seed_a,), goal),
        goal=goal.fact_key,
        licence=None,
    )


def cell_degraded(atoms: AtomTable) -> Cell:
    """c=70%: the blind window on iam_audit licenses Route B into P_max alone."""
    licence = _blind_licence()
    route_a, seed_a, goal = _route_a(atoms)
    route_b, seed_b = _route_b(atoms, goal, licence)
    return Cell(
        p_min=_program(model.ProgramKind.P_MIN, route_a, (seed_a,), goal),
        p_max=_program(
            model.ProgramKind.P_MAX, route_a + route_b, (seed_a, seed_b), goal
        ),
        goal=goal.fact_key,
        licence=licence,
    )
