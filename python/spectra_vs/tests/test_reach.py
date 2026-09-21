"""Unit tests for spectra_vs.reach.

Run from the repository root:

    python python/spectra_vs/tests/test_reach.py

Each test pins a property another stage is entitled to assume. The antitonicity and
monotonicity tests walk the whole admissible-cut lattice rather than sampling it, so a
mutation to the blocker test turns a named gate red instead of shifting a statistic.
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

from spectra_vs.reach import (  # noqa: E402
    AXIOM_KIND,
    GHOST_KIND,
    LICENSED_KIND,
    OBSERVED_KIND,
    ReachProgram,
    admissible_cut_masks,
    instance_blocked,
    reach,
    witness_mask,
    witness_tree,
)
from vs_fixtures import atom_table, cell_complete, cell_degraded  # noqa: E402


class _FakeInstance:
    """A stand-in carrying a conjunctive blocker term.

    `model.RuleInstance` refuses popcount > 1 under C-SLICE-1, so the general subset test
    in `instance_blocked` cannot be exercised through a real record. This shim exists only
    to prove the subset form is what is implemented, which is what makes lifting the
    narrowing a change to the index build rather than to the fixpoint.
    """

    def __init__(self, blockers: tuple[int, ...]) -> None:
        self.blockers = blockers
        self.instance_id = ids.InstanceId.mint(b"fake")
        self.head = model.Fact.mint(
            "fake.head", (ids.EntityId.mint("resource", b"fake"),), 1
        ).fact_key
        self.body: tuple[ids.FactHash, ...] = ()


class TestBlockerTest(unittest.TestCase):
    def test_single_literal_is_the_narrowed_form(self) -> None:
        inst = _FakeInstance((1 << 3,))
        self.assertTrue(instance_blocked(inst, 1 << 3))
        self.assertFalse(instance_blocked(inst, 1 << 4))

    def test_conjunctive_term_needs_every_literal(self) -> None:
        inst = _FakeInstance(((1 << 3) | (1 << 5),))
        self.assertFalse(instance_blocked(inst, 1 << 3))
        self.assertFalse(instance_blocked(inst, 1 << 5))
        self.assertTrue(instance_blocked(inst, (1 << 3) | (1 << 5)))

    def test_build_refuses_a_conjunctive_blocker(self) -> None:
        atoms = atom_table()
        cell = cell_complete(atoms)
        with self.assertRaises(errors.SchemaError) as caught:
            ReachProgram.build(
                kind=model.ProgramKind.P_MIN,
                instances=[_FakeInstance(((1 << 1) | (1 << 2),))],
                axioms=(),
                goal=cell.goal,
            )
        self.assertEqual(caught.exception.code, "E-VS-BLOCK-CONJ")


class TestFixpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()
        self.complete = cell_complete(self.atoms)
        self.degraded = cell_degraded(self.atoms)

    def test_goal_derivable_under_the_empty_cut(self) -> None:
        result = reach(self.complete.p_min, 0)
        self.assertTrue(result.derivable)
        self.assertIn(self.complete.goal, result.closure)

    def test_closure_is_strictly_ascending(self) -> None:
        result = reach(self.complete.p_max, 0)
        canon.check_strictly_ascending(result.closure, str, where="test")

    def test_severing_one_literal_removes_the_goal(self) -> None:
        bit = self.atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        result = reach(self.complete.p_min, 1 << bit)
        self.assertFalse(result.derivable)

    def test_steps_are_a_function_of_program_and_cut(self) -> None:
        first = reach(self.complete.p_min, 0)
        second = reach(self.complete.p_min, 0)
        self.assertEqual(first.steps, second.steps)
        self.assertEqual(first.closure, second.closure)
        self.assertEqual(first.order, second.order)

    def test_route_b_is_licensed_into_the_upper_side_only(self) -> None:
        bit = self.atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        self.assertFalse(reach(self.degraded.p_min, 1 << bit).derivable)
        self.assertTrue(reach(self.degraded.p_max, 1 << bit).derivable)

    def test_antitonicity_over_the_whole_lattice(self) -> None:
        masks = admissible_cut_masks(self.atoms.literals)
        self.assertEqual(len(masks), 162)
        closures = {m: set(map(str, reach(self.degraded.p_max, m).closure)) for m in masks}
        for smaller in masks:
            for larger in masks:
                if smaller & larger == smaller:
                    self.assertTrue(
                        closures[larger] <= closures[smaller],
                        f"cut {canon.mask_hex(larger)} derives more than "
                        f"its subset {canon.mask_hex(smaller)}",
                    )

    def test_monotonicity_in_the_program(self) -> None:
        for mask in admissible_cut_masks(self.atoms.literals):
            lower = set(map(str, reach(self.degraded.p_min, mask).closure))
            upper = set(map(str, reach(self.degraded.p_max, mask).closure))
            self.assertTrue(lower <= upper, canon.mask_hex(mask))

    def test_the_bracket_direction_holds_for_every_cut(self) -> None:
        for mask in admissible_cut_masks(self.atoms.literals):
            in_min = reach(self.degraded.p_min, mask).derivable
            in_max = reach(self.degraded.p_max, mask).derivable
            if not in_max:
                self.assertFalse(in_min)
            if in_min:
                self.assertTrue(in_max)


class TestIndexContract(unittest.TestCase):
    def test_unsorted_instances_are_refused(self) -> None:
        atoms = atom_table()
        cell = cell_complete(atoms)
        reversed_instances = tuple(reversed(cell.p_min.instances))
        with self.assertRaises(errors.CanonError):
            ReachProgram.build(
                kind=model.ProgramKind.P_MIN,
                instances=reversed_instances,
                axioms=cell.p_min.axioms,
                goal=cell.goal,
            )

    def test_empty_body_instance_fires(self) -> None:
        atoms = atom_table()
        head = model.Fact.mint(
            "resource.bulk_read", (ids.EntityId.mint("resource", b"r"),), 1
        )
        inst = model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0009"),
            rule_version="1.0.0",
            head=head.fact_key,
            body=(),
            blockers=(1 << atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit,),
            observed=model.Observation.OBSERVED,
            tick=1,
            evidence=(
                model.EvidenceRef(
                    binding="seed",
                    event_id=ids.EventId.mint(b"seed"),
                    source_id=ids.SourceId.of("res_access"),
                    t_evt_ns=1_707_004_800_000_000_000,
                ),
            ),
        )
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN,
            instances=(inst,),
            axioms=(),
            goal=head.fact_key,
        )
        self.assertTrue(reach(program, 0).derivable)
        blocked = 1 << atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        self.assertFalse(reach(program, blocked).derivable)

    def test_repeated_body_literal_still_fires(self) -> None:
        seed = model.Fact.mint("identity.actor", (ids.EntityId.mint("account", b"a"),), 1)
        head = model.Fact.mint("resource.bulk_read", (ids.EntityId.mint("resource", b"r"),), 2)
        inst = model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0010"),
            rule_version="1.0.0",
            head=head.fact_key,
            body=(seed.fact_key, seed.fact_key),
            blockers=(),
            observed=model.Observation.OBSERVED,
            tick=2,
            evidence=(
                model.EvidenceRef(
                    binding="both",
                    event_id=ids.EventId.mint(b"e"),
                    source_id=ids.SourceId.of("res_access"),
                    t_evt_ns=1_707_004_800_000_000_000,
                ),
            ),
        )
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN,
            instances=(inst,),
            axioms=(seed.fact_key,),
            goal=head.fact_key,
        )
        self.assertTrue(reach(program, 0).derivable)


class TestGoalIsASet(unittest.TestCase):
    """Regression for the false-severance found by the second end-to-end run.

    The goal library is the union of every goal fact either program derives. The
    pipeline picked ONE search target from it - the bytewise-least key - and asked each
    program about that key alone. At full telemetry the least key happened to be a fact
    only P_max derives, so the corridor search over P_min found it unreachable under the
    empty cut, returned zero corridors with complete=True, and reported that the empty
    cut severs the attack - while P_min derived the other goal fact through route A.

    `docs/vocab.toml` already defines a goal as a SET ("goals are a set, verdicts are
    per-goal"). The attack reaches its objective if ANY goal fact is derivable, so a cut
    severs only when EVERY goal fact is underivable. These tests pin that.
    """

    def _two_goals_one_dead(self) -> tuple[ReachProgram, ids.FactHash, ids.FactHash, int]:
        atoms = atom_table()
        a = model.Fact.mint("exfil.bulk_read", (ids.EntityId.mint("resource", b"A"),), 1)
        b = model.Fact.mint("exfil.bulk_read", (ids.EntityId.mint("resource", b"B"),), 1)
        # Make the DEAD goal the bytewise-least key whatever the digests turn out to be,
        # because the least key is exactly the one the buggy pipeline selected.
        dead, live = sorted((a, b), key=lambda f: canon.byte_order_key(str(f.fact_key)))
        blocker = 1 << atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        inst = model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0003"),
            rule_version="1.0.0",
            head=live.fact_key,
            body=(),
            blockers=(blocker,),
            observed=model.Observation.OBSERVED,
            tick=1,
            evidence=(
                model.EvidenceRef(
                    binding="b",
                    event_id=ids.EventId.mint(b"read"),
                    source_id=ids.SourceId.of("res_access"),
                    t_evt_ns=1_707_004_800_000_000_000,
                ),
            ),
        )
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN,
            instances=(inst,),
            axioms=(),
            goal=dead.fact_key,
            goals=tuple(sorted((dead.fact_key, live.fact_key), key=canon.byte_order_key)),
        )
        return program, dead.fact_key, live.fact_key, blocker

    def test_any_derivable_goal_makes_the_goal_derivable(self) -> None:
        program, _dead, _live, _blocker = self._two_goals_one_dead()
        # The representative `goal` is the dead key. Under single-key semantics this
        # returned False, which is the false severance.
        self.assertTrue(reach(program, 0).derivable)

    def test_severing_requires_every_goal_underivable(self) -> None:
        program, _dead, _live, blocker = self._two_goals_one_dead()
        self.assertTrue(reach(program, 0).derivable)
        self.assertFalse(reach(program, blocker).derivable)

    def test_witness_is_rooted_at_a_goal_that_was_actually_derived(self) -> None:
        program, dead, live, _blocker = self._two_goals_one_dead()
        result = reach(program, 0)
        tree = witness_tree(program, 0, result)
        self.assertEqual(str(tree.head), str(live))
        self.assertNotEqual(str(tree.head), str(dead))

    def test_a_single_goal_program_keeps_its_old_meaning(self) -> None:
        atoms = atom_table()
        head = model.Fact.mint("exfil.bulk_read", (ids.EntityId.mint("resource", b"S"),), 1)
        inst = model.RuleInstance.mint(
            rule_id=ids.RuleId.of("r0003"),
            rule_version="1.0.0",
            head=head.fact_key,
            body=(),
            blockers=(1 << atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit,),
            observed=model.Observation.OBSERVED,
            tick=1,
            evidence=(
                model.EvidenceRef(
                    binding="b",
                    event_id=ids.EventId.mint(b"single"),
                    source_id=ids.SourceId.of("res_access"),
                    t_evt_ns=1_707_004_800_000_000_000,
                ),
            ),
        )
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN, instances=(inst,), axioms=(), goal=head.fact_key
        )
        self.assertEqual(tuple(str(g) for g in program.goals), (str(head.fact_key),))
        self.assertTrue(reach(program, 0).derivable)

    def test_goals_must_contain_the_representative(self) -> None:
        a = model.Fact.mint("exfil.bulk_read", (ids.EntityId.mint("resource", b"X"),), 1)
        b = model.Fact.mint("exfil.bulk_read", (ids.EntityId.mint("resource", b"Y"),), 1)
        with self.assertRaises(errors.SchemaError):
            ReachProgram.build(
                kind=model.ProgramKind.P_MIN,
                instances=(),
                axioms=(),
                goal=a.fact_key,
                goals=(b.fact_key,),
            )


class TestWitnessTree(unittest.TestCase):
    def setUp(self) -> None:
        self.atoms = atom_table()
        self.complete = cell_complete(self.atoms)
        self.degraded = cell_degraded(self.atoms)

    def test_tree_is_well_founded_and_reaches_an_axiom(self) -> None:
        result = reach(self.complete.p_min, 0)
        tree = witness_tree(self.complete.p_min, 0, result)
        seen: set[str] = set()
        stack = [tree]
        depth = 0
        while stack:
            node = stack.pop()
            depth += 1
            self.assertNotIn(str(node.head), seen, "a fact appears twice on one path")
            stack.extend(node.children)
        self.assertGreaterEqual(depth, 4)
        leaves = []
        stack = [tree]
        while stack:
            node = stack.pop()
            if not node.children:
                leaves.append(node)
            stack.extend(node.children)
        self.assertTrue(all(leaf.kind == AXIOM_KIND for leaf in leaves))

    def test_corridor_a_is_the_union_of_the_route_a_blockers(self) -> None:
        result = reach(self.complete.p_min, 0)
        tree = witness_tree(self.complete.p_min, 0, result)
        mask = witness_mask(self.complete.p_min, tree)
        self.assertEqual(self.atoms.ranks_of_mask(mask), (0, 4, 5, 7))

    def test_licensed_node_is_not_rendered_as_observed(self) -> None:
        bit = self.atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        result = reach(self.degraded.p_max, 1 << bit)
        tree = witness_tree(self.degraded.p_max, 1 << bit, result)
        kinds = []
        stack = [tree]
        while stack:
            node = stack.pop()
            kinds.append(node.kind)
            stack.extend(node.children)
        self.assertIn(LICENSED_KIND, kinds)
        self.assertNotIn(GHOST_KIND, kinds)
        self.assertNotIn(OBSERVED_KIND, kinds)

    def test_tree_instances_are_sorted_and_unique(self) -> None:
        result = reach(self.complete.p_min, 0)
        tree = witness_tree(self.complete.p_min, 0, result)
        instances = tree.instances()
        canon.check_strictly_ascending(instances, str, where="test")

    def test_tree_of_an_underived_fact_is_refused(self) -> None:
        bit = self.atoms.literal_at(ids.ControlId.of("egress_seg"), 1).bit
        result = reach(self.complete.p_min, 1 << bit)
        with self.assertRaises(errors.SchemaError):
            witness_tree(self.complete.p_min, 1 << bit, result)

    def test_a_cycle_cannot_be_selected_as_support(self) -> None:
        left = model.Fact.mint("a.p", (ids.EntityId.mint("resource", b"x"),), 1)
        right = model.Fact.mint("b.p", (ids.EntityId.mint("resource", b"y"),), 1)
        seed = model.Fact.mint("s.p", (ids.EntityId.mint("resource", b"z"),), 1)
        evidence = (
            model.EvidenceRef(
                binding="e",
                event_id=ids.EventId.mint(b"e"),
                source_id=ids.SourceId.of("res_access"),
                t_evt_ns=1_707_004_800_000_000_000,
            ),
        )
        instances = [
            model.RuleInstance.mint(
                rule_id=ids.RuleId.of("r0011"),
                rule_version="1.0.0",
                head=left.fact_key,
                body=(seed.fact_key,),
                blockers=(),
                observed=model.Observation.OBSERVED,
                tick=1,
                evidence=evidence,
            ),
            model.RuleInstance.mint(
                rule_id=ids.RuleId.of("r0012"),
                rule_version="1.0.0",
                head=right.fact_key,
                body=(left.fact_key,),
                blockers=(),
                observed=model.Observation.OBSERVED,
                tick=1,
                evidence=evidence,
            ),
            model.RuleInstance.mint(
                rule_id=ids.RuleId.of("r0013"),
                rule_version="1.0.0",
                head=left.fact_key,
                body=(right.fact_key,),
                blockers=(),
                observed=model.Observation.OBSERVED,
                tick=1,
                evidence=evidence,
            ),
        ]
        program = ReachProgram.build(
            kind=model.ProgramKind.P_MIN,
            instances=sorted(instances, key=lambda i: str(i.instance_id)),
            axioms=(seed.fact_key,),
            goal=right.fact_key,
        )
        result = reach(program, 0)
        tree = witness_tree(program, 0, result)
        heads: list[str] = []
        stack = [tree]
        while stack:
            node = stack.pop()
            heads.append(str(node.head))
            stack.extend(node.children)
        self.assertEqual(len(heads), len(set(heads)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
