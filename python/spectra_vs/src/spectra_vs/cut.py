"""The corridor database, the minimum-cardinality search, and the canonical cut.

Stage S10, second of three modules. The question is: which controls, raised to which
levels, make the goal underivable in a given program?

THE LOOP. Start with an empty clause database. Take a minimum-cardinality set of controls
hitting every clause, render it as a cut, and run the fixpoint. If the goal is severed,
stop: no smaller cut satisfies the enumerated corridor set. If it is not, build the
witness tree of the goal under that cut, union the blocker terms of every instance it
uses, and append that union as a new clause. Every instance in that tree was enabled, so
the new clause is disjoint from the current cut and the database strictly grows; the loop
therefore terminates.

WHAT THE SEARCH MAY CLAIM, AND THE HONEST BOUND. Minimum hitting set is NP-hard in the
number of clauses and controls, and this module does not pretend otherwise: the branch and
bound is exponential in the worst case and is fenced by a deterministic node budget. When
the loop reaches fixpoint inside that budget the claim is EXACT_PSI_RELATIVE, which means
"no smaller cut satisfies the enumerated corridor set" and nothing more. EXACT_EXHAUSTIVE
is set only by `exhaustive_probe`, and only when a fixpoint actually ran for every
admissible cut one control smaller. When a cap or the budget fires the claim drops to
SUBSET: no control can be removed from the reported cut, and smaller cuts were not ruled
out. The claim never upgrades itself from a representation width; sixty-four bits of mask
is a width, not a tractability statement.

MINIMUM-CARDINALITY CUTS ARE NOT UNIQUE, SO THE REPRESENTATIVE IS MANDATED. Several
control sets can share the optimum. The canonical order on threshold literals - control_id
bytes ascending, then level ascending - is a total order, `rank` is the position in it,
and `canonical_select` returns the lexicographic-minimum member of the minimum-cardinality
family under that order. Phase one walks controls in that order and takes the first one
that is still extensible, which yields the smallest rank prefix; phase two lowers levels
in ascending rank order, which yields the smallest level vector given those controls.
Neither phase consults a mask value, a dict order or a search order, so the reported cut is
stable across solver order and across catalog edits that do not touch the chosen controls.

DETERMINISM. Clauses are indexed in insertion order but every decision ranges over them as
a whole set; controls are visited in canonical order; node counters are exact integers and
there is no wall-clock budget anywhere. No float is constructed in this module: the
branch-and-bound bound uses ceiling division on integers.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from spectra_core import canon, errors, ids, model

from spectra_vs.reach import ReachProgram, WitnessNode, reach, witness_mask, witness_tree

__all__ = [
    "CORRIDOR_CAP",
    "EXHAUSTIVE_COMBINATION_CAP",
    "STEP_BUDGET",
    "AtomTable",
    "ControlSpec",
    "CutSearch",
    "ExhaustiveProbe",
    "GoalSpec",
    "MinCardStatus",
    "MinCardinality",
    "Psi",
    "all_minimum_cuts",
    "canonical_select",
    "derive_bit_positions",
    "enumerate_psi",
    "exhaustive_probe",
    "load_control_catalog",
    "load_goal_spec",
    "min_cardinality",
]


#: Clause-database cap. Reaching it sets the `corridor_cap` flag, which blocks ROBUST and
#: caps minimality at SUBSET.
CORRIDOR_CAP: Final[int] = 4096

#: Branch-and-bound node budget, shared across every solve in one prove run.
STEP_BUDGET: Final[int] = 2_000_000

#: The exhaustive minimality probe is permitted only below this many candidate cuts.
EXHAUSTIVE_COMBINATION_CAP: Final[int] = 200_000


class MinCardStatus(StrEnum):
    """Outcome of one minimum-cardinality solve. INFEASIBLE is a value, not an error.

    NEC needs to distinguish "the optimum grew" from "no cut exists at all" and to treat
    the second as a growth, so infeasibility is returned rather than raised.
    """

    EXACT = "EXACT"
    INFEASIBLE = "INFEASIBLE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


@dataclass(frozen=True, slots=True)
class MinCardinality:
    """`value` is the optimum when `status` is EXACT and is absent otherwise."""

    value: int | None
    status: MinCardStatus
    nodes: int


@dataclass(frozen=True, slots=True)
class ControlSpec:
    """One catalog entry. `levels[0]` is the weakest setting and asserts nothing.

    The threshold literals derived from it are `control >= 1` .. `control >= len(levels)-1`;
    there is no literal for level zero, because "at least the weakest setting" is vacuous.
    """

    control_id: ids.ControlId
    title: str
    levels: tuple[str, ...]
    dimensions: tuple[str, ...]
    provenance: str

    @property
    def max_level(self) -> int:
        return len(self.levels) - 1


@dataclass(frozen=True, slots=True)
class GoalSpec:
    """The single goal the cut must sever, as authored.

    Resolving `goal_args` to entity ids and thence to a `FactHash` needs er.json and
    belongs to the prove stage; this carries the authored text and nothing more, so that
    nothing in the cut search can be tempted to resolve a goal from the bundle.
    """

    goal_predicate: str
    goal_args: tuple[str, ...]
    horizon_k: int


@dataclass(frozen=True, slots=True)
class AtomTable:
    """The literal universe, in canonical order, with its bit assignment.

    `rank` orders, ties and prints; `bit` only ever sets or tests a mask. They are
    different things and this class is the only place both are held, which is what keeps a
    mask value out of every sort key downstream.
    """

    literals: tuple[model.ThresholdLiteral, ...]

    @classmethod
    def build(cls, literals: Iterable[model.ThresholdLiteral]) -> AtomTable:
        """Verify canonical order, dense ranks, unique bits, upward-closed levels.

        Verified rather than sorted: a table that arrived out of order came from an
        emitter iterating a dict, and tidying it here would hide that.
        """
        items = tuple(literals)
        canon.check_strictly_ascending(items, lambda a: a.order_key, where="AtomTable.literals")
        if len(items) > 64:
            raise errors.LimitError(
                f"AtomTable: {len(items)} literals exceeds the 64-bit mask width",
                code="E-LIMIT-COUNT",
            )
        for index, literal in enumerate(items):
            if literal.rank != index:
                raise errors.SchemaError(
                    f"AtomTable: literal {literal.literal_id} carries rank {literal.rank} "
                    f"but is at canonical position {index}"
                )
        bits = [a.bit for a in items]
        if len(set(bits)) != len(bits):
            raise errors.SchemaError("AtomTable: two literals share a bit position")
        by_control: dict[str, list[int]] = {}
        for literal in items:
            by_control.setdefault(str(literal.control_id), []).append(literal.level)
        for control_id in sorted(by_control):
            levels = by_control[control_id]
            if levels != list(range(1, len(levels) + 1)):
                raise errors.SchemaError(
                    f"AtomTable: {control_id} levels {levels} are not 1..m dense"
                )
        return cls(literals=items)

    @classmethod
    def from_catalog(
        cls, catalog: Sequence[ControlSpec], bits: Mapping[str, int]
    ) -> AtomTable:
        """Build from the catalog plus the append-only bit lock, keyed by `LiteralId`.

        The bit lock is an input, never a derivation: deriving bits from the catalog would
        renumber them whenever a control was appended, and a renumber invalidates every
        archived certificate. `derive_bit_positions` exists for the one moment that is
        legitimate, which is creating the lock the first time.
        """
        ordered = sorted(catalog, key=lambda c: c.control_id.snake.encode("utf-8"))
        literals: list[model.ThresholdLiteral] = []
        rank = 0
        for spec in ordered:
            for level in range(1, spec.max_level + 1):
                literal_id = str(ids.LiteralId.of(spec.control_id, level))
                if literal_id not in bits:
                    raise errors.SchemaError(
                        f"AtomTable.from_catalog: {literal_id} has no bit in the lock"
                    )
                literals.append(
                    model.ThresholdLiteral(
                        control_id=spec.control_id,
                        level=level,
                        bit=bits[literal_id],
                        rank=rank,
                    )
                )
                rank += 1
        return cls.build(literals)

    @property
    def controls(self) -> tuple[ids.ControlId, ...]:
        """Distinct control ids in canonical order, each appearing once."""
        seen: list[ids.ControlId] = []
        for literal in self.literals:
            if not seen or seen[-1] != literal.control_id:
                seen.append(literal.control_id)
        return tuple(seen)

    def levels_of(self, control_id: ids.ControlId) -> tuple[model.ThresholdLiteral, ...]:
        return tuple(a for a in self.literals if a.control_id == control_id)

    def max_level(self, control_id: ids.ControlId) -> int:
        return len(self.levels_of(control_id))

    def literal_at(self, control_id: ids.ControlId, level: int) -> model.ThresholdLiteral:
        for literal in self.literals:
            if literal.control_id == control_id and literal.level == level:
                return literal
        raise errors.SchemaError(f"AtomTable: no literal {control_id}@{level}")

    def ranks_of_mask(self, mask: int) -> tuple[int, ...]:
        """The atom ranks a mask selects, ascending. The only permitted mask decomposition."""
        return tuple(a.rank for a in self.literals if mask >> a.bit & 1)

    def mask_of_ranks(self, ranks: Iterable[int]) -> int:
        mask = 0
        for rank in ranks:
            mask |= 1 << self.literals[rank].bit
        return mask

    def cut_of_levels(
        self, levels: Mapping[str, int], minimality: model.Minimality
    ) -> model.Cut:
        """Render `{control_id: level}` as an upward-closed `model.Cut`."""
        atoms: list[model.ThresholdLiteral] = []
        for literal in self.literals:
            if literal.level <= levels.get(str(literal.control_id), 0):
                atoms.append(literal)
        return model.Cut.mint(tuple(atoms), minimality)


@dataclass(frozen=True, slots=True)
class Psi:
    """The corridor clause database for one program, plus what the search spent on it."""

    program: model.ProgramKind
    complete: bool
    corridors: tuple[model.Corridor, ...]
    corridor_cap: int
    bb_nodes: int


@dataclass(frozen=True, slots=True)
class CutSearch:
    """Everything one side of the bracket produced."""

    program: model.ProgramKind
    cut: model.Cut
    psi: Psi
    minimality: model.Minimality
    severs: bool
    witness: WitnessNode | None
    fixpoint_steps: int
    bb_nodes: int
    budget_exhausted: bool
    corridor_cap_hit: bool


@dataclass(frozen=True, slots=True)
class ExhaustiveProbe:
    """Result of running a fixpoint for every admissible cut one control smaller."""

    ran: bool
    cuts_tested: int
    smaller_found: bool
    skipped_reason: str


# ---------------------------------------------------------------------------
# Deterministic node accounting
# ---------------------------------------------------------------------------


class _BudgetHit(Exception):
    """Internal. Never escapes `min_cardinality`."""


class _NodeBox:
    """A deterministic branch-and-bound node counter. Never a clock."""

    __slots__ = ("limit", "used")

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def spend(self) -> None:
        self.used += 1
        if self.used > self.limit:
            raise _BudgetHit


# ---------------------------------------------------------------------------
# Minimum cardinality over SETS OF CONTROLS
# ---------------------------------------------------------------------------


def _control_hits(
    clauses: Sequence[frozenset[int]], atoms: AtomTable
) -> tuple[tuple[frozenset[int], ...], tuple[tuple[frozenset[int], ...], ...]]:
    """For each control in canonical order: the clauses it hits at maximum level, and the
    clauses it hits at each level 1..m.

    Raising a control to its maximum level hits a superset of what any lower level hits,
    which is exactly why the cardinality search can range over controls rather than over
    literals without losing an optimum.
    """
    at_max: list[frozenset[int]] = []
    per_level: list[tuple[frozenset[int], ...]] = []
    for control_id in atoms.controls:
        levels: list[frozenset[int]] = []
        running: set[int] = set()
        for literal in atoms.levels_of(control_id):
            here = {i for i, clause in enumerate(clauses) if literal.rank in clause}
            running |= here
            levels.append(frozenset(running))
        per_level.append(tuple(levels))
        at_max.append(levels[-1] if levels else frozenset())
    return tuple(at_max), tuple(per_level)


def _ceil_div(numerator: int, denominator: int) -> int:
    """Integer ceiling division. No float is constructed anywhere in this module."""
    return -(-numerator // denominator)


def _bb(
    hits: Sequence[frozenset[int]],
    allowed: Sequence[int],
    unhit: frozenset[int],
    start: int,
    chosen: int,
    best: int | None,
    box: _NodeBox,
) -> int | None:
    """Ordered subset enumeration with the cardinality bound of the cut section.

    Controls are considered in canonical order and never revisited, so every hitting set
    is reached exactly once and the node count is a function of the instance alone.
    """
    box.spend()
    if not unhit:
        return chosen if best is None or chosen < best else best
    widest = 0
    for index in range(start, len(allowed)):
        width = len(unhit & hits[allowed[index]])
        if width > widest:
            widest = width
    if widest == 0:
        return best
    bound = chosen + _ceil_div(len(unhit), widest)
    if best is not None and bound >= best:
        return best
    for index in range(start, len(allowed)):
        control = allowed[index]
        covered = unhit & hits[control]
        if not covered:
            continue
        best = _bb(hits, allowed, unhit - covered, index + 1, chosen + 1, best, box)
    return best


def min_cardinality(
    clauses: Sequence[frozenset[int]],
    atoms: AtomTable,
    budget: int,
    excluded_controls: Iterable[ids.ControlId] = (),
) -> MinCardinality:
    """The fewest RAISED CONTROLS hitting every clause, or why that was not determined.

    Cardinality is counted in controls, never in literals: raising one control to level
    three puts three literals in the mask and costs the operator one control, and
    reporting three would overstate what was asked of them.
    """
    if budget <= 0:
        return MinCardinality(value=None, status=MinCardStatus.BUDGET_EXHAUSTED, nodes=0)
    hits, _ = _control_hits(clauses, atoms)
    excluded = {str(c) for c in excluded_controls}
    allowed = [i for i, c in enumerate(atoms.controls) if str(c) not in excluded]
    box = _NodeBox(budget)
    try:
        best = _bb(hits, allowed, frozenset(range(len(clauses))), 0, 0, None, box)
    except _BudgetHit:
        return MinCardinality(
            value=None, status=MinCardStatus.BUDGET_EXHAUSTED, nodes=box.used
        )
    if best is None:
        return MinCardinality(value=None, status=MinCardStatus.INFEASIBLE, nodes=box.used)
    return MinCardinality(value=best, status=MinCardStatus.EXACT, nodes=box.used)


def _extendable(
    hits: Sequence[frozenset[int]],
    allowed: Sequence[int],
    unhit: frozenset[int],
    start: int,
    cap: int,
    box: _NodeBox,
) -> bool:
    """True when `unhit` can be covered by at most `cap` controls drawn from `allowed[start:]`."""
    if cap < 0:
        return not unhit
    found = _bb(hits, allowed, unhit, start, 0, cap + 1, box)
    return found is not None and found <= cap


# ---------------------------------------------------------------------------
# Canonical selection: the lexicographic-minimum representative
# ---------------------------------------------------------------------------


def canonical_select(
    clauses: Sequence[frozenset[int]],
    atoms: AtomTable,
    cardinality: int,
    minimality: model.Minimality,
    budget: int = STEP_BUDGET,
) -> tuple[model.Cut, int]:
    """The lexicographic-minimum representative at the given cardinality, and the nodes it cost.

    Phase one takes, in canonical order, the first control that still leaves the rest
    coverable within the remaining budget of controls; because every literal of a lower
    control precedes every literal of a higher one, that greedy walk produces the smallest
    rank vector. Phase two lowers each chosen control while every clause stays hit,
    visiting controls in ascending rank, which produces the smallest level vector given
    those controls. Level-minimality is a hard requirement, not a preference: after phase
    two, lowering any raised control one step leaves at least one clause unhit.
    """
    hits, per_level = _control_hits(clauses, atoms)
    allowed = list(range(len(atoms.controls)))
    box = _NodeBox(budget)

    chosen: list[int] = []
    unhit = frozenset(range(len(clauses)))
    try:
        for index in range(len(allowed)):
            if len(chosen) == cardinality:
                break
            covered = unhit & hits[index]
            remaining = cardinality - len(chosen) - 1
            if _extendable(hits, allowed, unhit - covered, index + 1, remaining, box):
                chosen.append(index)
                unhit = unhit - covered
    except _BudgetHit:
        raise errors.BudgetError(
            "canonical_select: the node budget was exhausted inside selection; "
            "the caller must fall back to a subset-minimal cut and claim SUBSET"
        ) from None

    if len(chosen) != cardinality or unhit:
        raise errors.SchemaError(
            f"canonical_select: no cut of cardinality {cardinality} hits every clause; "
            "the cardinality passed in was not the optimum for this database"
        )

    levels = {str(atoms.controls[c]): atoms.max_level(atoms.controls[c]) for c in chosen}
    for control in chosen:
        control_id = atoms.controls[control]
        while levels[str(control_id)] > 1:
            trial = dict(levels)
            trial[str(control_id)] = levels[str(control_id)] - 1
            if not _hits_all(clauses, chosen, atoms, per_level, trial):
                break
            levels = trial

    if not _hits_all(clauses, chosen, atoms, per_level, levels):
        raise errors.SchemaError("canonical_select: the selected cut does not hit every clause")
    if not _level_minimal(clauses, chosen, atoms, per_level, levels):
        raise errors.SchemaError(
            "canonical_select: a raised control can be lowered one step with every clause "
            "still hit; level-minimality is a hard requirement, not a preference",
            code="E-CUT-CLOSURE",
        )
    return atoms.cut_of_levels(levels, minimality), box.used


def _hits_all(
    clauses: Sequence[frozenset[int]],
    chosen: Sequence[int],
    atoms: AtomTable,
    per_level: Sequence[tuple[frozenset[int], ...]],
    levels: Mapping[str, int],
) -> bool:
    covered: set[int] = set()
    for control in chosen:
        level = levels[str(atoms.controls[control])]
        if level >= 1:
            covered |= per_level[control][level - 1]
    return len(covered) == len(clauses)


def _level_minimal(
    clauses: Sequence[frozenset[int]],
    chosen: Sequence[int],
    atoms: AtomTable,
    per_level: Sequence[tuple[frozenset[int], ...]],
    levels: Mapping[str, int],
) -> bool:
    """True when no raised control can be lowered one step with the others held fixed."""
    for control in chosen:
        control_id = str(atoms.controls[control])
        if levels[control_id] <= 1:
            continue
        trial = dict(levels)
        trial[control_id] = levels[control_id] - 1
        if _hits_all(clauses, chosen, atoms, per_level, trial):
            return False
    return True


def _subset_minimal(
    clauses: Sequence[frozenset[int]], atoms: AtomTable
) -> model.Cut:
    """Every control at maximum level, then dropped and lowered while every clause stays hit.

    This is the cap-and-budget fallback. It claims only SUBSET: no control can be removed
    from it, and smaller cuts were not ruled out.
    """
    _, per_level = _control_hits(clauses, atoms)
    chosen = list(range(len(atoms.controls)))
    levels = {str(c): atoms.max_level(c) for c in atoms.controls}
    if not _hits_all(clauses, chosen, atoms, per_level, levels):
        raise errors.SchemaError(
            "_subset_minimal: some clause is not hit by the whole literal universe; "
            "an unblockable corridor must be reported, not hidden in a fallback cut"
        )
    for control in reversed(chosen[:]):
        trial_chosen = [c for c in chosen if c != control]
        if _hits_all(clauses, trial_chosen, atoms, per_level, levels):
            chosen = trial_chosen
    for control in chosen:
        control_id = str(atoms.controls[control])
        while levels[control_id] > 1:
            trial = dict(levels)
            trial[control_id] = levels[control_id] - 1
            if not _hits_all(clauses, chosen, atoms, per_level, trial):
                break
            levels = trial
    kept = {str(atoms.controls[c]): levels[str(atoms.controls[c])] for c in chosen}
    return atoms.cut_of_levels(kept, model.Minimality.SUBSET)


# ---------------------------------------------------------------------------
# The hitting-set loop
# ---------------------------------------------------------------------------


def enumerate_psi(
    program: ReachProgram,
    atoms: AtomTable,
    budget: int = STEP_BUDGET,
    corridor_cap: int = CORRIDOR_CAP,
) -> CutSearch:
    """Run the corridor loop over one program and return its cut and clause database."""
    clauses: list[frozenset[int]] = []
    seen_clauses: set[frozenset[int]] = set()
    nodes = 0
    steps = 0
    complete = True
    cap_hit = False
    budget_exhausted = False

    while True:
        solve = min_cardinality(clauses, atoms, budget - nodes)
        nodes += solve.nodes
        if solve.status is MinCardStatus.BUDGET_EXHAUSTED:
            complete = False
            budget_exhausted = True
            break
        if solve.status is MinCardStatus.INFEASIBLE:
            # Unreachable by construction: a clause is appended only when its mask is
            # non-zero, so every clause names at least one literal of the universe.
            raise errors.DeterminismError(
                "enumerate_psi: the clause database became infeasible; an empty corridor "
                "was appended, which the mask==0 branch is there to prevent"
            )
        cardinality = solve.value
        assert cardinality is not None
        try:
            cut, select_nodes = canonical_select(
                clauses, atoms, cardinality, model.Minimality.EXACT_PSI_RELATIVE, budget - nodes
            )
        except errors.BudgetError:
            complete = False
            budget_exhausted = True
            break
        nodes += select_nodes

        result = reach(program, cut.mask)
        steps += result.steps
        if not result.derivable:
            return _finish(
                program,
                atoms,
                clauses,
                cut,
                model.Minimality.EXACT_PSI_RELATIVE,
                complete=complete,
                severs=True,
                witness=None,
                steps=steps,
                nodes=nodes,
                corridor_cap=corridor_cap,
                budget_exhausted=False,
                cap_hit=False,
            )

        tree = witness_tree(program, cut.mask, result)
        mask = witness_mask(program, tree)
        if mask == 0:
            # Every instance in this derivation is unblockable: no control in the catalog
            # can sever it. That is not a corridor, and appending it as an empty clause
            # would make the database infeasible and the claim meaningless.
            return _finish(
                program,
                atoms,
                clauses,
                cut,
                model.Minimality.UNVERIFIED,
                complete=complete,
                severs=False,
                witness=tree,
                steps=steps,
                nodes=nodes,
                corridor_cap=corridor_cap,
                budget_exhausted=False,
                cap_hit=False,
            )
        clause = frozenset(atoms.ranks_of_mask(mask))
        if clause in seen_clauses:
            raise errors.DeterminismError(
                "enumerate_psi: the loop learned a clause it already holds, so it is not "
                "making progress; the cut it just tested should have hit that clause"
            )
        seen_clauses.add(clause)
        clauses.append(clause)
        if len(clauses) >= corridor_cap:
            complete = False
            cap_hit = True
            break

    cut = _subset_minimal(clauses, atoms)
    result = reach(program, cut.mask)
    steps += result.steps
    tree = witness_tree(program, cut.mask, result) if result.derivable else None
    return _finish(
        program,
        atoms,
        clauses,
        cut,
        model.Minimality.SUBSET,
        complete=complete,
        severs=not result.derivable,
        witness=tree,
        steps=steps,
        nodes=nodes,
        corridor_cap=corridor_cap,
        budget_exhausted=budget_exhausted,
        cap_hit=cap_hit,
    )


def _finish(
    program: ReachProgram,
    atoms: AtomTable,
    clauses: Sequence[frozenset[int]],
    cut: model.Cut,
    minimality: model.Minimality,
    *,
    complete: bool,
    severs: bool,
    witness: WitnessNode | None,
    steps: int,
    nodes: int,
    corridor_cap: int,
    budget_exhausted: bool,
    cap_hit: bool,
) -> CutSearch:
    corridors = tuple(
        sorted(
            (
                model.Corridor.mint(tuple(sorted(clause)), atoms.mask_of_ranks(clause))
                for clause in clauses
            ),
            key=lambda c: canon.byte_order_key(str(c.corridor_id)),
        )
    )
    canon.check_strictly_ascending(
        corridors, lambda c: str(c.corridor_id), where="Psi.corridors"
    )
    return CutSearch(
        program=program.kind,
        cut=cut,
        psi=Psi(
            program=program.kind,
            complete=complete,
            corridors=corridors,
            corridor_cap=corridor_cap,
            bb_nodes=nodes,
        ),
        minimality=minimality,
        severs=severs,
        witness=witness,
        fixpoint_steps=steps,
        bb_nodes=nodes,
        budget_exhausted=budget_exhausted,
        corridor_cap_hit=cap_hit,
    )


# ---------------------------------------------------------------------------
# Brute force, for the exhaustive minimality claim and for the canonicity tests
# ---------------------------------------------------------------------------


def _admissible_level_vectors(atoms: AtomTable) -> tuple[tuple[int, ...], ...]:
    """Every admissible assignment of one level per control, in canonical order.

    Admissible means upward-closed: a control at level L asserts levels 1..L, so the
    choice per control is an integer in 0..m_k and the lattice is their product.
    """
    vectors: list[tuple[int, ...]] = [()]
    for control_id in atoms.controls:
        top = atoms.max_level(control_id)
        vectors = [v + (level,) for v in vectors for level in range(top + 1)]
    return tuple(vectors)


def all_minimum_cuts(
    clauses: Sequence[frozenset[int]], atoms: AtomTable
) -> tuple[model.Cut, ...]:
    """Every level-minimal minimum-cardinality cut, ascending by the cut tie-break.

    LEVEL-MINIMALITY IS AN ADMISSIBILITY FILTER, NOT A TIE-BREAK, and it is applied before
    the tie-break rather than after. The reason is visible in `model.Cut.compare_key`: a
    cut that raises a control to level two carries an extra literal whose rank sits between
    the first control's rank and the next control's, so the rank-vector rule would prefer
    the raised level over the lower one. The cut section states level-minimality as a hard
    requirement - lowering any raised control one step must leave a clause unhit - so a cut
    that fails it is not a candidate at all and never reaches the comparison.

    Brute force over the whole admissible lattice. This exists so the canonical selection
    can be checked against the definition rather than against itself; it is not what the
    prove path calls, because the lattice is exponential in the number of controls.
    """
    _, per_level = _control_hits(clauses, atoms)
    best: int | None = None
    found: list[model.Cut] = []
    for vector in _admissible_level_vectors(atoms):
        levels = {
            str(control_id): vector[i] for i, control_id in enumerate(atoms.controls)
        }
        chosen = [i for i, level in enumerate(vector) if level >= 1]
        if not _hits_all(clauses, chosen, atoms, per_level, levels):
            continue
        if not _level_minimal(clauses, chosen, atoms, per_level, levels):
            continue
        cardinality = len(chosen)
        if best is not None and cardinality > best:
            continue
        if best is None or cardinality < best:
            best = cardinality
            found = []
        kept = {str(atoms.controls[c]): levels[str(atoms.controls[c])] for c in chosen}
        found.append(atoms.cut_of_levels(kept, model.Minimality.UNVERIFIED))
    return tuple(sorted(found, key=lambda c: c.compare_key()))


def exhaustive_probe(
    program: ReachProgram,
    atoms: AtomTable,
    cardinality: int,
    combination_cap: int = EXHAUSTIVE_COMBINATION_CAP,
) -> ExhaustiveProbe:
    """Run a fixpoint for every admissible cut one control smaller than `cardinality`.

    This is the only thing that earns EXACT_EXHAUSTIVE. It is never inferred from the mask
    width, and it refuses rather than samples when the lattice is too large: a probe that
    tested a subset would be a SUBSET claim wearing an exhaustive label.
    """
    if cardinality < 1:
        return ExhaustiveProbe(
            ran=False, cuts_tested=0, smaller_found=False, skipped_reason="cardinality_zero"
        )
    vectors = _admissible_level_vectors(atoms)
    candidates = [v for v in vectors if sum(1 for level in v if level >= 1) == cardinality - 1]
    if len(candidates) > combination_cap:
        return ExhaustiveProbe(
            ran=False,
            cuts_tested=0,
            smaller_found=False,
            skipped_reason="combination_cap",
        )
    tested = 0
    smaller = False
    for vector in candidates:
        levels = {
            str(control_id): vector[i] for i, control_id in enumerate(atoms.controls)
        }
        kept = {k: v for k, v in levels.items() if v >= 1}
        cut = atoms.cut_of_levels(kept, model.Minimality.UNVERIFIED)
        tested += 1
        if not reach(program, cut.mask).derivable:
            smaller = True
    return ExhaustiveProbe(
        ran=True, cuts_tested=tested, smaller_found=smaller, skipped_reason=""
    )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_control_catalog(path: Path) -> tuple[ControlSpec, ...]:
    """Read config/vs/controls.toml. The catalog is the universe the cut search ranges over.

    It lives here because the literal universe is an input to the cut search and to
    nothing else in this stage group. Bit positions are NOT read from this file; they come
    from the append-only lock, because a bit derived from the catalog would renumber on
    every append.
    """
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    if document.get("schema") != "spectra.vs.controls/1":
        raise errors.SchemaError(
            f"load_control_catalog: {path} is not a spectra.vs.controls/1 document"
        )
    specs: list[ControlSpec] = []
    for entry in document.get("control", ()):
        levels = tuple(entry["levels"])
        if len(levels) < 2:
            raise errors.SchemaError(
                f"load_control_catalog: control {entry.get('id')!r} declares no threshold "
                "above its weakest setting, so it can never appear in a cut"
            )
        specs.append(
            ControlSpec(
                control_id=ids.ControlId.of(entry["id"]),
                title=entry["title"],
                levels=levels,
                dimensions=tuple(entry["dimensions"]),
                provenance=entry["provenance"],
            )
        )
    ordered = tuple(
        sorted(specs, key=lambda s: s.control_id.snake.encode("utf-8"))
    )
    canon.check_strictly_ascending(
        ordered, lambda s: s.control_id.snake, where="load_control_catalog"
    )
    return ordered


def load_goal_spec(path: Path) -> GoalSpec:
    """Read config/vs/goal.toml. Exactly one goal, per the scenario loader constraint."""
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    if document.get("schema") != "spectra.vs.goal/1":
        raise errors.SchemaError(f"load_goal_spec: {path} is not a spectra.vs.goal/1 document")
    entries = document.get("goal", ())
    if len(entries) != 1:
        raise errors.SchemaError(
            f"load_goal_spec: {path} declares {len(entries)} goals; the loader constraint "
            "is exactly one"
        )
    entry = entries[0]
    horizon = entry["horizon_k"]
    if isinstance(horizon, bool) or not isinstance(horizon, int):
        raise errors.CanonError("load_goal_spec: horizon_k must be a u32 integer")
    canon.u32(horizon)
    return GoalSpec(
        goal_predicate=entry["goal_predicate"],
        goal_args=tuple(entry["goal_args"]),
        horizon_k=horizon,
    )


def derive_bit_positions(catalog: Sequence[ControlSpec]) -> tuple[tuple[str, int], ...]:
    """Bit positions for a catalog that has no lock yet, in canonical order.

    THE ONLY LEGITIMATE USE IS CREATING THE LOCK THE FIRST TIME. Once a (control, level)
    has a position it keeps it forever, removal writes a tombstone and the position is
    never reused. Re-deriving over an edited catalog renumbers bits and invalidates every
    archived certificate, which is the whole reason the lock is append-only.
    """
    ordered = sorted(catalog, key=lambda c: c.control_id.snake.encode("utf-8"))
    assignment: list[tuple[str, int]] = []
    position = 0
    for spec in ordered:
        for level in range(1, spec.max_level + 1):
            if position >= 64:
                raise errors.LimitError(
                    "derive_bit_positions: the catalog needs more than 64 bit positions",
                    code="E-LIMIT-COUNT",
                )
            assignment.append((str(ids.LiteralId.of(spec.control_id, level)), position))
            position += 1
    return tuple(assignment)
