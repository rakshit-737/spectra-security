"""The two-sided bracket and the blindness premium.

Stage S10, third of three modules, and the headline object of the whole slice.

THE BRACKET. The cut machinery runs twice and never enumerates worlds. The lower side is
P_min, the observed instances only; the upper side is P_max, the observed instances plus
the licensed silent ones plus obligation-forced GHOSTs. Each side produces its own clause
database and its own canonical cut. The pair is reported as a pair. It is not a confidence
interval, it has no midpoint, and nothing here renders it as one.

WHAT P_max IS, STATED PLAINLY. P_max unions every licensed silent instance and ignores
mutual-exclusion structure between them, so its reachable set is a SUPERSET of the union
of the reachable sets of the realizable worlds. Two consequences travel with every object
this module returns:

  * Unreachability in P_max is sound with respect to realizability: if the goal is not
    derivable in P_max it is not derivable in any realizable world.
  * A counterexample drawn from P_max may combine silent instances that no single
    consistent world realizes, so such a tree may depict an attack that could not have
    happened. Every object derived from the upper side carries `program = PMax` so that no
    consumer can forget which side it came from.

THE PREMIUM IS A PROPERTY OF THE TWO CLAUSE DATABASES, NOT A DIFFERENCE OF TWO CUTS.

    NEC(Psi) = { c : r(Psi over the universe minus the literals of c) > r(Psi) }
    OCC(Psi) = { c : there is a level L with 1 + r(Psi minus the clauses x_{c,L} hits) == r(Psi) }
    B        = NEC(Psi_max) \\ OCC(Psi_min)

NEC is the set of controls in EVERY minimum-cardinality cut; infeasibility after removing
a control counts as an increase, because a database no cut can satisfy is worse than one
that needs more controls. OCC is the set of controls in SOME minimum-cardinality cut. Both
are defined by the VALUES of optimisation problems and not by any argmin, which is the
entire point: minimum-cardinality cuts are not unique, so a set difference of two arbitrarily chosen
representatives is not a well-defined object and changes with solver order. `B` does not.

The set difference of the two canonical representatives is a different object. It is named
`cut_delta_canonical`, it carries the caption below wherever it is shown, and it and the
premium must never appear in the same component or the same export.

WHEN THE PREMIUM IS NOT PUBLISHED IT IS ABSENT, NOT EMPTY. An empty premium is a real
result - it is the control arm, and it is what a fully observed run produces. A suppressed
premium is a different thing and carries a reason from the closed enum instead. Conflating
them would let a capped run look like a clean one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from spectra_core import canon, errors, ids, model

from spectra_vs.cut import (
    STEP_BUDGET,
    AtomTable,
    CutSearch,
    MinCardStatus,
    Psi,
    enumerate_psi,
    min_cardinality,
)
from spectra_vs.reach import ReachProgram

__all__ = [
    "CUT_DELTA_CAPTION",
    "PMAX_REALIZABILITY_NOTE",
    "Bracket",
    "PremiumResult",
    "SuppressedReason",
    "blindness_premium",
    "cut_delta_canonical",
    "necessary_controls",
    "occurring_controls",
    "two_sided_bracket",
]


#: The literal caption that travels with `cut_delta_canonical`, everywhere it is shown.
CUT_DELTA_CAPTION: Final[str] = (
    "difference between two canonical representatives; not the blindness premium"
)

#: The statement that travels with every object derived from the upper side.
PMAX_REALIZABILITY_NOTE: Final[str] = (
    "P_max unions all licensed silent instances and ignores mutual-exclusion structure, "
    "so it admits combinations no single consistent world realises. Unreachability in "
    "P_max is conservative and safe; a counterexample drawn from P_max may depict an "
    "attack that no consistent world realises."
)


class SuppressedReason(StrEnum):
    """The closed enum of `premium_suppressed_reason`. No other value is emitted."""

    GROUNDING_CAPPED = "grounding_capped"
    CORRIDOR_CAP = "corridor_cap"
    SOLVER_BUDGET = "solver_budget"
    HORIZON_TRUNCATED = "horizon_truncated"
    ER_AMBIGUOUS = "er_ambiguous"


@dataclass(frozen=True, slots=True)
class Bracket:
    """The pair of cut searches. Reported as a pair, never collapsed into one number."""

    lower: CutSearch
    upper: CutSearch

    @property
    def realizability_note(self) -> str:
        return PMAX_REALIZABILITY_NOTE


@dataclass(frozen=True, slots=True)
class PremiumResult:
    """NEC, OCC and B, or the reason none of them may be published.

    When `published` is false the caller OMITS the whole `premium` member of the
    certificate and writes `premium_suppressed_reason` instead. It does not write null, or
    an empty array, or zero: an empty premium is a result and an absent one is not.
    """

    published: bool
    suppressed_reason: SuppressedReason | None
    nec_max: tuple[ids.ControlId, ...]
    occ_min: tuple[ids.ControlId, ...]
    blindness_premium: tuple[ids.ControlId, ...]
    solves: int
    bb_nodes: int


def two_sided_bracket(
    p_min: ReachProgram,
    p_max: ReachProgram,
    atoms: AtomTable,
    budget: int = STEP_BUDGET,
    corridor_cap: int | None = None,
) -> Bracket:
    """Run the whole cut machinery twice, once per side, and return the pair.

    The two runs share nothing but their inputs: separate clause databases, separate node
    accounting, separate cuts. Nothing mutates the lower side while the upper side runs.
    """
    if p_min.kind is not model.ProgramKind.P_MIN:
        raise errors.SchemaError("two_sided_bracket: the lower side must be a PMin program")
    if p_max.kind is not model.ProgramKind.P_MAX:
        raise errors.SchemaError("two_sided_bracket: the upper side must be a PMax program")
    kwargs = {} if corridor_cap is None else {"corridor_cap": corridor_cap}
    lower = enumerate_psi(p_min, atoms, budget, **kwargs)
    upper = enumerate_psi(p_max, atoms, budget, **kwargs)
    return Bracket(lower=lower, upper=upper)


def _clauses_of(psi: Psi, atoms: AtomTable) -> tuple[frozenset[int], ...]:
    """The clause database as rank sets. Corridor ids are the artifact key, ranks are the
    solver's view of the same thing; the mask is never decomposed by value here."""
    return tuple(frozenset(c.atom_ranks) for c in psi.corridors)


@dataclass(frozen=True, slots=True)
class _Solves:
    controls: tuple[ids.ControlId, ...]
    nodes: int
    solves: int
    exhausted: bool


def necessary_controls(
    psi: Psi, atoms: AtomTable, budget: int = STEP_BUDGET
) -> _Solves:
    """NEC(Psi): the controls that appear in EVERY minimum-cardinality cut.

    A control is necessary when deleting its literals from the universe makes the optimum
    strictly larger, or makes the database unsatisfiable at all. Infeasibility counts as an
    increase: if no cut exists without `c`, then `c` is in every cut there is.

    This is a statement about the VALUE of the optimisation problem, so it does not depend
    on which minimum-cardinality cut a solver happened to return.
    """
    clauses = _clauses_of(psi, atoms)
    spent = 0
    baseline = min_cardinality(clauses, atoms, budget - spent)
    spent += baseline.nodes
    solves = 1
    if baseline.status is MinCardStatus.BUDGET_EXHAUSTED:
        return _Solves(controls=(), nodes=spent, solves=solves, exhausted=True)
    if baseline.status is MinCardStatus.INFEASIBLE:
        raise errors.SchemaError(
            "necessary_controls: the clause database is unsatisfiable over the whole "
            "universe, which means an unblockable corridor reached it"
        )
    found: list[ids.ControlId] = []
    for control_id in atoms.controls:
        probe = min_cardinality(clauses, atoms, budget - spent, excluded_controls=(control_id,))
        spent += probe.nodes
        solves += 1
        if probe.status is MinCardStatus.BUDGET_EXHAUSTED:
            return _Solves(controls=(), nodes=spent, solves=solves, exhausted=True)
        if probe.status is MinCardStatus.INFEASIBLE:
            found.append(control_id)
            continue
        assert probe.value is not None and baseline.value is not None
        if probe.value > baseline.value:
            found.append(control_id)
    ordered = tuple(sorted(found, key=lambda c: canon.byte_order_key(str(c))))
    canon.check_strictly_ascending(ordered, str, where="necessary_controls")
    return _Solves(controls=ordered, nodes=spent, solves=solves, exhausted=False)


def occurring_controls(
    psi: Psi, atoms: AtomTable, budget: int = STEP_BUDGET
) -> _Solves:
    """OCC(Psi): the controls that appear in SOME minimum-cardinality cut.

    A control occurs when raising it to some level L pays for itself: one control spent,
    plus the optimum over the clauses L does not hit, equals the optimum over everything.
    The sub-problem excludes `c` itself, because re-spending a control already paid for
    would let the sum undercount.
    """
    clauses = _clauses_of(psi, atoms)
    spent = 0
    baseline = min_cardinality(clauses, atoms, budget - spent)
    spent += baseline.nodes
    solves = 1
    if baseline.status is MinCardStatus.BUDGET_EXHAUSTED:
        return _Solves(controls=(), nodes=spent, solves=solves, exhausted=True)
    if baseline.status is MinCardStatus.INFEASIBLE:
        raise errors.SchemaError(
            "occurring_controls: the clause database is unsatisfiable over the whole universe"
        )
    assert baseline.value is not None
    found: list[ids.ControlId] = []
    for control_id in atoms.controls:
        occurs = False
        for level in range(1, atoms.max_level(control_id) + 1):
            ranks = {
                atoms.literal_at(control_id, l).rank for l in range(1, level + 1)
            }
            kept = tuple(c for c in clauses if not (c & ranks))
            probe = min_cardinality(
                kept, atoms, budget - spent, excluded_controls=(control_id,)
            )
            spent += probe.nodes
            solves += 1
            if probe.status is MinCardStatus.BUDGET_EXHAUSTED:
                return _Solves(controls=(), nodes=spent, solves=solves, exhausted=True)
            if probe.status is MinCardStatus.INFEASIBLE:
                continue
            assert probe.value is not None
            if 1 + probe.value == baseline.value:
                occurs = True
                break
        if occurs:
            found.append(control_id)
    ordered = tuple(sorted(found, key=lambda c: canon.byte_order_key(str(c))))
    canon.check_strictly_ascending(ordered, str, where="occurring_controls")
    return _Solves(controls=ordered, nodes=spent, solves=solves, exhausted=False)


def blindness_premium(
    psi_min: Psi,
    psi_max: Psi,
    atoms: AtomTable,
    budget: int = STEP_BUDGET,
    grounding_capped: bool = False,
    budget_exhausted: bool = False,
    horizon_truncated: bool = False,
    er_ambiguous: bool = False,
) -> PremiumResult:
    """B = NEC(Psi_max) \\ OCC(Psi_min): the controls required ONLY because of blindness.

    A control in NEC(Psi_max) is in every cut that severs the goal once the licensed silent
    instances are admitted. A control outside OCC(Psi_min) is in no minimum-cardinality cut of the
    observed-only database. A control in both positions is therefore in the robust cut
    because a sensor could not see, and for no other reason available to this model.

    The preconditions are checked before any solve: both databases complete, grounding not
    capped, no budget exhausted, horizon not truncated, entity resolution unambiguous. When
    any fails the whole premium is suppressed with a reason from the closed enum, and the
    caller omits the member rather than emitting an empty one.
    """
    if grounding_capped:
        return _suppressed(SuppressedReason.GROUNDING_CAPPED)
    if not psi_min.complete or not psi_max.complete:
        return _suppressed(SuppressedReason.CORRIDOR_CAP)
    if budget_exhausted:
        return _suppressed(SuppressedReason.SOLVER_BUDGET)
    if horizon_truncated:
        return _suppressed(SuppressedReason.HORIZON_TRUNCATED)
    if er_ambiguous:
        return _suppressed(SuppressedReason.ER_AMBIGUOUS)
    if psi_max.program is not model.ProgramKind.P_MAX:
        raise errors.SchemaError("blindness_premium: NEC is taken over the PMax database")
    if psi_min.program is not model.ProgramKind.P_MIN:
        raise errors.SchemaError("blindness_premium: OCC is taken over the PMin database")

    nec = necessary_controls(psi_max, atoms, budget)
    if nec.exhausted:
        return _suppressed(SuppressedReason.SOLVER_BUDGET, nodes=nec.nodes, solves=nec.solves)
    occ = occurring_controls(psi_min, atoms, budget - nec.nodes)
    if occ.exhausted:
        return _suppressed(
            SuppressedReason.SOLVER_BUDGET,
            nodes=nec.nodes + occ.nodes,
            solves=nec.solves + occ.solves,
        )

    occ_set = {str(c) for c in occ.controls}
    premium = tuple(c for c in nec.controls if str(c) not in occ_set)
    canon.check_strictly_ascending(premium, str, where="blindness_premium")
    return PremiumResult(
        published=True,
        suppressed_reason=None,
        nec_max=nec.controls,
        occ_min=occ.controls,
        blindness_premium=premium,
        solves=nec.solves + occ.solves,
        bb_nodes=nec.nodes + occ.nodes,
    )


def _suppressed(
    reason: SuppressedReason, nodes: int = 0, solves: int = 0
) -> PremiumResult:
    return PremiumResult(
        published=False,
        suppressed_reason=reason,
        nec_max=(),
        occ_min=(),
        blindness_premium=(),
        solves=solves,
        bb_nodes=nodes,
    )


def cut_delta_canonical(
    lower: model.Cut, upper: model.Cut
) -> tuple[tuple[ids.ControlId, ...], str]:
    """The controls raised in the upper representative and not in the lower one, with its caption.

    THIS IS NOT THE BLINDNESS PREMIUM AND MUST NEVER BE LABELLED AS ONE.
    Minimum-cardinality cuts are not unique; this is a difference of two arbitrarily
    chosen representatives, and the
    caption returned beside it says exactly that. The premium is `blindness_premium`, is a
    property of the two clause databases, and never appears in the same component or the
    same export as this value.
    """
    in_lower = {str(a.control_id) for a in lower.atoms}
    delta = sorted(
        {str(a.control_id) for a in upper.atoms} - in_lower,
        key=canon.byte_order_key,
    )
    return tuple(ids.ControlId(c) for c in delta), CUT_DELTA_CAPTION
