"""Unit tests for spectra_vs.premium.

Run from the repository root:

    python python/spectra_vs/tests/test_premium.py

The two completeness cells are the point of this file. The fully observed cell must
produce an EMPTY premium and the degraded cell must produce {priv_approval}; the empty
result is the control arm, and without it the non-empty one proves nothing.

`prop_premium_invariant` is the proof artifact the cut section asks for: 512 seeded
permutations of clause insertion order and of bit assignment, each recomputing B and each
required to produce the same set. A prose claim of invariance without it does not ship.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import errors, ids, model  # noqa: E402

from spectra_vs.cut import (  # noqa: E402
    CORRIDOR_CAP,
    AtomTable,
    ControlSpec,
    Psi,
    derive_bit_positions,
    enumerate_psi,
)
from spectra_vs.premium import (  # noqa: E402
    CUT_DELTA_CAPTION,
    PMAX_REALIZABILITY_NOTE,
    SuppressedReason,
    blindness_premium,
    cut_delta_canonical,
    necessary_controls,
    occurring_controls,
    two_sided_bracket,
)
from test_cut import seeded_permutation  # noqa: E402
from vs_fixtures import CONTROL_LEVELS, atom_table, cell_complete, cell_degraded  # noqa: E402


def psi_of(kind: model.ProgramKind, atoms: AtomTable, clauses) -> Psi:
    corridors = sorted(
        (
            model.Corridor.mint(tuple(sorted(clause)), atoms.mask_of_ranks(clause))
            for clause in clauses
        ),
        key=lambda c: str(c.corridor_id),
    )
    return Psi(
        program=kind,
        complete=True,
        corridors=tuple(corridors),
        corridor_cap=CORRIDOR_CAP,
        bb_nodes=0,
    )


def names(controls) -> list[str]:
    return [c.snake for c in controls]


class TestNecOcc(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()

    def test_singleton_clause_makes_its_control_necessary(self) -> None:
        psi = psi_of(model.ProgramKind.P_MAX, self.atoms, [(2,)])
        self.assertEqual(names(necessary_controls(psi, self.atoms).controls), ["priv_approval"])

    def test_a_four_way_clause_makes_nothing_necessary(self) -> None:
        # Removing any one of the four still leaves the clause hittable by the other
        # three, so the optimum does not grow and NEC is empty. The minimum_viable
        # narrative in the operative specification writes NEC = {egress_seg} for this
        # database, which does not follow from the NEC definition the cut section gives;
        # the definition is what is implemented, and it is what the premium depends on.
        psi = psi_of(model.ProgramKind.P_MAX, self.atoms, [(0, 4, 5, 7)])
        self.assertEqual(names(necessary_controls(psi, self.atoms).controls), [])

    def test_occ_names_every_control_that_can_carry_a_clause_alone(self) -> None:
        psi = psi_of(model.ProgramKind.P_MIN, self.atoms, [(0, 4, 5, 7)])
        self.assertEqual(
            names(occurring_controls(psi, self.atoms).controls),
            ["egress_seg", "rate_limit", "session_binding", "token_expiry"],
        )

    def test_nec_is_a_subset_of_occ_on_the_same_database(self) -> None:
        clauses = [(0, 2), (2, 4), (1,)]
        upper = psi_of(model.ProgramKind.P_MAX, self.atoms, clauses)
        lower = psi_of(model.ProgramKind.P_MIN, self.atoms, clauses)
        nec = set(names(necessary_controls(upper, self.atoms).controls))
        occ = set(names(occurring_controls(lower, self.atoms).controls))
        self.assertTrue(nec <= occ, f"{sorted(nec)} is not inside {sorted(occ)}")

    def test_infeasibility_after_removal_counts_as_an_increase(self) -> None:
        # rate_limit has one level and is the only control naming rank 4 in this clause,
        # so removing it leaves a clause no cut can hit.
        psi = psi_of(model.ProgramKind.P_MAX, self.atoms, [(4,)])
        self.assertEqual(names(necessary_controls(psi, self.atoms).controls), ["rate_limit"])

    def test_solver_budget_is_reported_not_guessed(self) -> None:
        psi = psi_of(model.ProgramKind.P_MAX, self.atoms, [(0,), (2,), (4,)])
        result = necessary_controls(psi, self.atoms, budget=1)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.controls, ())


class TestTheTwoCells(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()

    def test_complete_cell_premium_is_empty_and_published(self) -> None:
        cell = cell_complete(self.atoms)
        bracket = two_sided_bracket(cell.p_min, cell.p_max, self.atoms)
        self.assertEqual(
            [c.atom_ranks for c in bracket.lower.psi.corridors], [(0, 4, 5, 7)]
        )
        self.assertEqual(
            [c.atom_ranks for c in bracket.upper.psi.corridors], [(0, 4, 5, 7)]
        )
        result = blindness_premium(bracket.lower.psi, bracket.upper.psi, self.atoms)
        self.assertTrue(result.published)
        self.assertIsNone(result.suppressed_reason)
        self.assertEqual(names(result.nec_max), [])
        self.assertEqual(
            names(result.occ_min),
            ["egress_seg", "rate_limit", "session_binding", "token_expiry"],
        )
        self.assertEqual(names(result.blindness_premium), [])

    def test_degraded_cell_premium_is_priv_approval(self) -> None:
        cell = cell_degraded(self.atoms)
        bracket = two_sided_bracket(cell.p_min, cell.p_max, self.atoms)
        self.assertEqual(
            [str(a.literal_id) for a in bracket.lower.cut.atoms], ["lit:egress_seg@1"]
        )
        self.assertEqual(
            [str(a.literal_id) for a in bracket.upper.cut.atoms],
            ["lit:egress_seg@1", "lit:priv_approval@1"],
        )
        result = blindness_premium(bracket.lower.psi, bracket.upper.psi, self.atoms)
        self.assertTrue(result.published)
        self.assertEqual(names(result.nec_max), ["priv_approval"])
        self.assertEqual(
            names(result.occ_min),
            ["egress_seg", "rate_limit", "session_binding", "token_expiry"],
        )
        self.assertEqual(names(result.blindness_premium), ["priv_approval"])

    def test_the_bracket_carries_the_pmax_statement(self) -> None:
        cell = cell_degraded(self.atoms)
        bracket = two_sided_bracket(cell.p_min, cell.p_max, self.atoms)
        self.assertIs(bracket.upper.program, model.ProgramKind.P_MAX)
        self.assertIs(bracket.upper.psi.program, model.ProgramKind.P_MAX)
        self.assertIs(bracket.lower.program, model.ProgramKind.P_MIN)
        self.assertIn("no single consistent world realises", bracket.realizability_note)
        self.assertIs(bracket.realizability_note, PMAX_REALIZABILITY_NOTE)

    def test_sides_must_be_the_right_way_round(self) -> None:
        cell = cell_degraded(self.atoms)
        with self.assertRaises(errors.SchemaError):
            two_sided_bracket(cell.p_max, cell.p_max, self.atoms)
        with self.assertRaises(errors.SchemaError):
            two_sided_bracket(cell.p_min, cell.p_min, self.atoms)


class TestInvariance(unittest.TestCase):
    """prop_premium_invariant: B is invariant to clause order and to bit assignment."""

    def setUp(self) -> None:
        self.catalog = tuple(
            ControlSpec(
                control_id=ids.ControlId.of(name),
                title=name,
                levels=tuple(f"l{i}" for i in range(levels + 1)),
                dimensions=("resource",),
                provenance="fixture",
            )
            for name, levels in sorted(CONTROL_LEVELS.items())
        )
        self.lower_clauses = [(0, 4, 5, 7)]
        self.upper_clauses = [(0, 4, 5, 7), (2,), (1, 6), (3, 8)]

    def test_512_seeded_permutations_agree(self) -> None:
        reference = None
        base_bits = derive_bit_positions(self.catalog)
        for seed in range(512):
            bit_order = seeded_permutation(len(base_bits), f"premium/bits/{seed}")
            positions = [pos for _, pos in base_bits]
            bits = {
                literal: positions[bit_order[index]]
                for index, (literal, _) in enumerate(base_bits)
            }
            atoms = AtomTable.from_catalog(self.catalog, bits)
            upper_order = seeded_permutation(
                len(self.upper_clauses), f"premium/clauses/{seed}"
            )
            upper = psi_of(
                model.ProgramKind.P_MAX,
                atoms,
                [self.upper_clauses[i] for i in upper_order],
            )
            lower = psi_of(model.ProgramKind.P_MIN, atoms, self.lower_clauses)
            result = blindness_premium(lower, upper, atoms)
            self.assertTrue(result.published)
            here = (names(result.nec_max), names(result.occ_min), names(result.blindness_premium))
            if reference is None:
                reference = here
            self.assertEqual(here, reference, f"seed {seed}")
        # priv_approval is the only control whose removal leaves a clause no cut can hit,
        # and it occurs in no minimum-cardinality cut of the observed-only database.
        self.assertEqual(reference[0], ["priv_approval"])
        self.assertEqual(reference[2], ["priv_approval"])


class TestSuppression(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()
        cell = cell_degraded(self.atoms)
        bracket = two_sided_bracket(cell.p_min, cell.p_max, self.atoms)
        self.lower = bracket.lower.psi
        self.upper = bracket.upper.psi

    def _incomplete(self, psi: Psi) -> Psi:
        return Psi(
            program=psi.program,
            complete=False,
            corridors=psi.corridors,
            corridor_cap=psi.corridor_cap,
            bb_nodes=psi.bb_nodes,
        )

    def test_an_absent_premium_is_not_an_empty_one(self) -> None:
        result = blindness_premium(
            self._incomplete(self.lower), self.upper, self.atoms
        )
        self.assertFalse(result.published)
        self.assertIs(result.suppressed_reason, SuppressedReason.CORRIDOR_CAP)
        self.assertEqual(result.blindness_premium, ())

    def test_grounding_cap_wins_over_everything(self) -> None:
        result = blindness_premium(
            self.lower, self.upper, self.atoms, grounding_capped=True
        )
        self.assertIs(result.suppressed_reason, SuppressedReason.GROUNDING_CAPPED)

    def test_solver_budget_is_its_own_reason(self) -> None:
        result = blindness_premium(
            self.lower, self.upper, self.atoms, budget_exhausted=True
        )
        self.assertIs(result.suppressed_reason, SuppressedReason.SOLVER_BUDGET)

    def test_a_tiny_budget_suppresses_rather_than_approximates(self) -> None:
        result = blindness_premium(self.lower, self.upper, self.atoms, budget=1)
        self.assertFalse(result.published)
        self.assertIs(result.suppressed_reason, SuppressedReason.SOLVER_BUDGET)

    def test_horizon_and_er_have_their_own_reasons(self) -> None:
        self.assertIs(
            blindness_premium(
                self.lower, self.upper, self.atoms, horizon_truncated=True
            ).suppressed_reason,
            SuppressedReason.HORIZON_TRUNCATED,
        )
        self.assertIs(
            blindness_premium(
                self.lower, self.upper, self.atoms, er_ambiguous=True
            ).suppressed_reason,
            SuppressedReason.ER_AMBIGUOUS,
        )


class TestCutDeltaIsNotThePremium(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()

    def test_the_delta_carries_its_caption(self) -> None:
        cell = cell_degraded(self.atoms)
        bracket = two_sided_bracket(cell.p_min, cell.p_max, self.atoms)
        delta, caption = cut_delta_canonical(bracket.lower.cut, bracket.upper.cut)
        self.assertEqual(names(delta), ["priv_approval"])
        self.assertEqual(caption, CUT_DELTA_CAPTION)
        self.assertIn("not the blindness premium", caption)

    def test_the_delta_and_the_premium_are_different_objects(self) -> None:
        # Psi_min is corridor A alone; Psi_max adds a clause that rate_limit also hits, so
        # one control covers both clauses and the upper representative moves off
        # egress_seg entirely. The canonical delta names rate_limit; the premium is empty,
        # because rate_limit already occurs in a minimum-cardinality cut of the
        # observed-only database.
        lower = psi_of(model.ProgramKind.P_MIN, self.atoms, [(0, 4, 5, 7)])
        upper = psi_of(model.ProgramKind.P_MAX, self.atoms, [(0, 4, 5, 7), (2, 4)])
        from spectra_vs.cut import canonical_select, min_cardinality

        lower_clauses = [frozenset(c.atom_ranks) for c in lower.corridors]
        upper_clauses = [frozenset(c.atom_ranks) for c in upper.corridors]
        lower_cut, _ = canonical_select(
            lower_clauses,
            self.atoms,
            min_cardinality(lower_clauses, self.atoms, 100000).value,
            model.Minimality.EXACT_PSI_RELATIVE,
        )
        upper_cut, _ = canonical_select(
            upper_clauses,
            self.atoms,
            min_cardinality(upper_clauses, self.atoms, 100000).value,
            model.Minimality.EXACT_PSI_RELATIVE,
        )
        delta, _ = cut_delta_canonical(lower_cut, upper_cut)
        premium = blindness_premium(lower, upper, self.atoms)
        self.assertEqual(names(delta), ["rate_limit"])
        self.assertEqual(names(premium.nec_max), ["rate_limit"])
        self.assertEqual(names(premium.blindness_premium), [])
        self.assertNotEqual(names(delta), names(premium.blindness_premium))


class TestEndToEndCells(unittest.TestCase):
    def test_the_two_cells_side_by_side(self) -> None:
        atoms = atom_table()
        rows = []
        for label, cell in (
            ("c=100%", cell_complete(atoms)),
            ("c=70%", cell_degraded(atoms)),
        ):
            bracket = two_sided_bracket(cell.p_min, cell.p_max, atoms)
            result = blindness_premium(bracket.lower.psi, bracket.upper.psi, atoms)
            rows.append(
                (
                    label,
                    [str(a.literal_id) for a in bracket.lower.cut.atoms],
                    [str(a.literal_id) for a in bracket.upper.cut.atoms],
                    names(result.blindness_premium),
                )
            )
        self.assertEqual(
            rows,
            [
                ("c=100%", ["lit:egress_seg@1"], ["lit:egress_seg@1"], []),
                (
                    "c=70%",
                    ["lit:egress_seg@1"],
                    ["lit:egress_seg@1", "lit:priv_approval@1"],
                    ["priv_approval"],
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
