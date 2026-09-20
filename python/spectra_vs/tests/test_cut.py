"""Unit tests for spectra_vs.cut.

Run from the repository root:

    python python/spectra_vs/tests/test_cut.py

The canonicity tests compare `canonical_select` against a brute-force enumeration of the
whole admissible lattice, so the selection is checked against the definition rather than
against itself. The permutation tests feed the solver 512 seeded orderings of clauses and
of bit assignment; a mutation that let insertion order reach the output turns them red.

Permutations are derived from the foundation's digest rather than from a random module:
this package reads no ambient random source, and a test that did would be exempting itself
from the property it is testing.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import canon, errors, ids, model  # noqa: E402

from spectra_vs.cut import (  # noqa: E402
    AtomTable,
    ControlSpec,
    MinCardStatus,
    all_minimum_cuts,
    canonical_select,
    derive_bit_positions,
    enumerate_psi,
    exhaustive_probe,
    load_control_catalog,
    load_goal_spec,
    min_cardinality,
)
from spectra_vs.reach import ReachProgram, reach  # noqa: E402
from vs_fixtures import CONTROL_LEVELS, atom_table, cell_complete, cell_degraded  # noqa: E402


def seeded_permutation(count: int, seed: str) -> tuple[int, ...]:
    """A deterministic permutation of `range(count)` keyed by `seed`.

    Fisher-Yates driven by digest octets. No random module, no clock, no environment.
    """
    stream = bytearray()
    block = 0
    order = list(range(count))
    for index in range(count - 1, 0, -1):
        while len(stream) < 8:
            stream.extend(
                canon.digest("test", f"{seed}/{block}".encode("utf-8"))
            )
            block += 1
        draw = int.from_bytes(bytes(stream[:8]), "big")
        del stream[:8]
        swap = draw % (index + 1)
        order[index], order[swap] = order[swap], order[index]
    return tuple(order)


def control(name: str) -> ids.ControlId:
    return ids.ControlId.of(name)


class TestAtomTable(unittest.TestCase):
    def test_canonical_order_and_dense_ranks(self) -> None:
        atoms = atom_table()
        self.assertEqual(len(atoms.literals), 9)
        self.assertEqual(
            [str(c) for c in atoms.controls],
            [
                "ctl:egress_seg",
                "ctl:priv_approval",
                "ctl:rate_limit",
                "ctl:session_binding",
                "ctl:token_expiry",
            ],
        )
        self.assertEqual([a.rank for a in atoms.literals], list(range(9)))
        self.assertEqual(atoms.max_level(control("rate_limit")), 1)
        self.assertEqual(atoms.max_level(control("egress_seg")), 2)

    def test_duplicate_bit_is_refused(self) -> None:
        literals = list(atom_table().literals)
        literals[1] = model.ThresholdLiteral(
            control_id=literals[1].control_id,
            level=literals[1].level,
            bit=literals[0].bit,
            rank=literals[1].rank,
        )
        with self.assertRaises(errors.SchemaError):
            AtomTable.build(literals)

    def test_wrong_rank_is_refused(self) -> None:
        literals = list(atom_table().literals)
        literals[2] = model.ThresholdLiteral(
            control_id=literals[2].control_id,
            level=literals[2].level,
            bit=literals[2].bit,
            rank=7,
        )
        with self.assertRaises(errors.SchemaError):
            AtomTable.build(literals)

    def test_mask_round_trip(self) -> None:
        atoms = atom_table()
        ranks = (0, 4, 5, 7)
        self.assertEqual(atoms.ranks_of_mask(atoms.mask_of_ranks(ranks)), ranks)


class TestMinCardinality(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()

    def test_empty_database_needs_no_control(self) -> None:
        solve = min_cardinality((), self.atoms, 1000)
        self.assertIs(solve.status, MinCardStatus.EXACT)
        self.assertEqual(solve.value, 0)

    def test_two_disjoint_clauses_need_two_controls(self) -> None:
        clauses = (frozenset({0}), frozenset({2}))
        solve = min_cardinality(clauses, self.atoms, 1000)
        self.assertEqual(solve.value, 2)

    def test_one_control_can_hit_two_clauses(self) -> None:
        clauses = (frozenset({0, 2}), frozenset({0, 4}))
        solve = min_cardinality(clauses, self.atoms, 1000)
        self.assertEqual(solve.value, 1)

    def test_excluding_the_only_hitter_is_infeasible(self) -> None:
        clauses = (frozenset({2}),)
        solve = min_cardinality(
            clauses, self.atoms, 1000, excluded_controls=(control("priv_approval"),)
        )
        self.assertIs(solve.status, MinCardStatus.INFEASIBLE)
        self.assertIsNone(solve.value)

    def test_budget_exhaustion_is_a_status_not_a_guess(self) -> None:
        clauses = (frozenset({0}), frozenset({2}), frozenset({4}))
        solve = min_cardinality(clauses, self.atoms, 1)
        self.assertIs(solve.status, MinCardStatus.BUDGET_EXHAUSTED)
        self.assertIsNone(solve.value)

    def test_node_count_is_deterministic(self) -> None:
        clauses = (frozenset({0, 2}), frozenset({4, 5}), frozenset({7}))
        first = min_cardinality(clauses, self.atoms, 100000)
        second = min_cardinality(clauses, self.atoms, 100000)
        self.assertEqual(first.nodes, second.nodes)


class TestCanonicalSelection(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()

    def _select(self, clauses):
        solve = min_cardinality(clauses, self.atoms, 100000)
        cut, _ = canonical_select(
            clauses, self.atoms, solve.value, model.Minimality.EXACT_PSI_RELATIVE
        )
        return cut

    def test_matches_the_brute_force_lexicographic_minimum(self) -> None:
        databases = [
            (frozenset({0, 4, 5, 7}),),
            (frozenset({0, 4, 5, 7}), frozenset({2})),
            (frozenset({1}), frozenset({3})),
            (frozenset({1, 3}), frozenset({6, 8})),
            (frozenset({0, 2}), frozenset({2, 4}), frozenset({4, 5})),
            (frozenset({8}),),
            (frozenset({1, 6}), frozenset({3, 8}), frozenset({0, 5})),
        ]
        for clauses in databases:
            with self.subTest(clauses=sorted(map(sorted, clauses))):
                mine = self._select(clauses)
                every = all_minimum_cuts(clauses, self.atoms)
                self.assertTrue(every)
                best = every[0]
                self.assertEqual(
                    [str(a.literal_id) for a in mine.atoms],
                    [str(a.literal_id) for a in best.atoms],
                )
                self.assertEqual(mine.cardinality, best.cardinality)

    def test_level_minimality_is_hard(self) -> None:
        # Only the level-2 literal of egress_seg hits this clause, so the cut must raise
        # it to level 2 and lowering it one step must leave the clause unhit.
        clauses = (frozenset({1}),)
        cut = self._select(clauses)
        self.assertEqual([str(a.literal_id) for a in cut.atoms],
                         ["lit:egress_seg@1", "lit:egress_seg@2"])
        self.assertEqual(cut.cardinality, 1)
        lowered = self.atoms.cut_of_levels({"ctl:egress_seg": 1}, model.Minimality.UNVERIFIED)
        self.assertEqual(lowered.mask & self.atoms.mask_of_ranks({1}), 0)

    def test_cardinality_counts_controls_not_literals(self) -> None:
        clauses = (frozenset({1}), frozenset({3}))
        cut = self._select(clauses)
        self.assertEqual(len(cut.atoms), 4)
        self.assertEqual(cut.cardinality, 2)

    def test_clause_order_does_not_reach_the_output(self) -> None:
        base = [
            frozenset({0, 4, 5, 7}),
            frozenset({2}),
            frozenset({1, 6}),
            frozenset({3, 8}),
        ]
        reference = self._select(tuple(base))
        signature = reference.canonical_bytes()
        for seed in range(512):
            order = seeded_permutation(len(base), f"clause/{seed}")
            shuffled = tuple(base[i] for i in order)
            self.assertEqual(self._select(shuffled).canonical_bytes(), signature)

    def test_bit_assignment_does_not_reach_the_reported_cut(self) -> None:
        catalog = tuple(
            ControlSpec(
                control_id=control(name),
                title=name,
                levels=tuple(f"l{i}" for i in range(levels + 1)),
                dimensions=("resource",),
                provenance="fixture",
            )
            for name, levels in sorted(CONTROL_LEVELS.items())
        )
        clauses_by_rank = (frozenset({0, 4, 5, 7}), frozenset({2}))
        reference = None
        for seed in range(512):
            positions = [pos for _, pos in derive_bit_positions(catalog)]
            order = seeded_permutation(len(positions), f"bits/{seed}")
            permuted = {
                literal: positions[order[index]]
                for index, (literal, _) in enumerate(derive_bit_positions(catalog))
            }
            atoms = AtomTable.from_catalog(catalog, permuted)
            solve = min_cardinality(clauses_by_rank, atoms, 100000)
            cut, _ = canonical_select(
                clauses_by_rank, atoms, solve.value, model.Minimality.EXACT_PSI_RELATIVE
            )
            literals = tuple(str(a.literal_id) for a in cut.atoms)
            if reference is None:
                reference = literals
            self.assertEqual(literals, reference)
        self.assertEqual(reference, ("lit:egress_seg@1", "lit:priv_approval@1"))


class TestCorridorLoop(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()
        self.complete = cell_complete(self.atoms)
        self.degraded = cell_degraded(self.atoms)

    def test_complete_cell_finds_corridor_a_alone(self) -> None:
        for program in (self.complete.p_min, self.complete.p_max):
            search = enumerate_psi(program, self.atoms)
            self.assertTrue(search.severs)
            self.assertIs(search.minimality, model.Minimality.EXACT_PSI_RELATIVE)
            self.assertTrue(search.psi.complete)
            self.assertEqual(len(search.psi.corridors), 1)
            self.assertEqual(search.psi.corridors[0].atom_ranks, (0, 4, 5, 7))
            self.assertEqual(
                [str(a.literal_id) for a in search.cut.atoms], ["lit:egress_seg@1"]
            )
            self.assertEqual(search.cut.cardinality, 1)

    def test_degraded_upper_side_finds_a_second_corridor(self) -> None:
        lower = enumerate_psi(self.degraded.p_min, self.atoms)
        upper = enumerate_psi(self.degraded.p_max, self.atoms)
        self.assertEqual(len(lower.psi.corridors), 1)
        self.assertEqual(len(upper.psi.corridors), 2)
        self.assertEqual(
            sorted(c.atom_ranks for c in upper.psi.corridors), [(0, 4, 5, 7), (2,)]
        )
        self.assertEqual(
            [str(a.literal_id) for a in upper.cut.atoms],
            ["lit:egress_seg@1", "lit:priv_approval@1"],
        )
        self.assertEqual(upper.cut.cardinality, 2)
        self.assertTrue(upper.severs)

    def test_the_reported_cut_actually_severs_the_goal(self) -> None:
        upper = enumerate_psi(self.degraded.p_max, self.atoms)
        self.assertFalse(reach(self.degraded.p_max, upper.cut.mask).derivable)

    def test_corridors_are_sorted_by_corridor_id(self) -> None:
        upper = enumerate_psi(self.degraded.p_max, self.atoms)
        canon.check_strictly_ascending(
            upper.psi.corridors, lambda c: str(c.corridor_id), where="test"
        )

    def test_corridor_cap_downgrades_to_subset(self) -> None:
        search = enumerate_psi(self.degraded.p_max, self.atoms, corridor_cap=1)
        self.assertTrue(search.corridor_cap_hit)
        self.assertFalse(search.psi.complete)
        self.assertIs(search.minimality, model.Minimality.SUBSET)

    def test_node_budget_downgrades_to_subset(self) -> None:
        search = enumerate_psi(self.degraded.p_max, self.atoms, budget=1)
        self.assertTrue(search.budget_exhausted)
        self.assertFalse(search.psi.complete)
        self.assertIs(search.minimality, model.Minimality.SUBSET)

    def test_unblockable_derivation_is_unverified(self) -> None:
        seed = model.Fact.mint("s.p", (ids.EntityId.mint("resource", b"s"),), 1)
        goal = model.Fact.mint("g.p", (ids.EntityId.mint("resource", b"g"),), 2)
        instance = model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0020"),
            rule_version="1.0.0",
            head=goal.fact_key,
            body=(seed.fact_key,),
            blockers=(),
            observed=model.Observation.OBSERVED,
            tick=2,
            evidence=(
                model.EvidenceRef(
                    binding="b",
                    event_id=ids.EventId.mint(b"b"),
                    source_id=ids.SourceId.of("res_access"),
                    t_evt_ns=1_707_004_800_000_000_000,
                ),
            ),
        )
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN,
            instances=(instance,),
            axioms=(seed.fact_key,),
            goal=goal.fact_key,
        )
        search = enumerate_psi(program, self.atoms)
        self.assertIs(search.minimality, model.Minimality.UNVERIFIED)
        self.assertFalse(search.severs)
        self.assertEqual(search.psi.corridors, ())

    def test_loop_output_is_byte_stable(self) -> None:
        first = enumerate_psi(self.degraded.p_max, self.atoms)
        second = enumerate_psi(self.degraded.p_max, self.atoms)
        self.assertEqual(first.cut.canonical_bytes(), second.cut.canonical_bytes())
        self.assertEqual(
            [c.canonical_bytes() for c in first.psi.corridors],
            [c.canonical_bytes() for c in second.psi.corridors],
        )
        self.assertEqual(first.bb_nodes, second.bb_nodes)
        self.assertEqual(first.fixpoint_steps, second.fixpoint_steps)


class TestExhaustiveProbe(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()
        self.degraded = cell_degraded(self.atoms)

    def test_no_smaller_cut_severs_the_upper_side(self) -> None:
        search = enumerate_psi(self.degraded.p_max, self.atoms)
        probe = exhaustive_probe(self.degraded.p_max, self.atoms, search.cut.cardinality)
        self.assertTrue(probe.ran)
        self.assertFalse(probe.smaller_found)
        self.assertGreater(probe.cuts_tested, 0)

    def test_probe_refuses_rather_than_samples(self) -> None:
        search = enumerate_psi(self.degraded.p_max, self.atoms)
        probe = exhaustive_probe(
            self.degraded.p_max, self.atoms, search.cut.cardinality, combination_cap=1
        )
        self.assertFalse(probe.ran)
        self.assertEqual(probe.skipped_reason, "combination_cap")
        self.assertEqual(probe.cuts_tested, 0)


class TestConfigLoaders(unittest.TestCase):
    def test_controls_catalog_matches_the_slice_narrowing(self) -> None:
        catalog = load_control_catalog(_REPO_ROOT / "config" / "vs" / "controls.toml")
        self.assertEqual(
            [c.control_id.snake for c in catalog],
            ["egress_seg", "priv_approval", "rate_limit", "session_binding", "token_expiry"],
        )
        self.assertEqual({c.control_id.snake: c.max_level for c in catalog}, CONTROL_LEVELS)
        bits = dict(derive_bit_positions(catalog))
        self.assertEqual(len(bits), 9)
        atoms = AtomTable.from_catalog(catalog, bits)
        self.assertEqual(len(atoms.literals), 9)

    def test_goal_is_exactly_one(self) -> None:
        goal = load_goal_spec(_REPO_ROOT / "config" / "vs" / "goal.toml")
        self.assertEqual(goal.goal_predicate, "resource.bulk_read")
        self.assertEqual(goal.goal_args, ("res_customer_records",))
        self.assertEqual(goal.horizon_k, 3600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
