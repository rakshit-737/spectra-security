"""Unit tests for spectra_vs.temporal, the temporal-consistency pass of ADR-0016.

Run from the repository root:

    python python/spectra_vs/tests/test_temporal.py

The pass answers one question: does any recorded timestamp contradict the recorded order of
its own source, or a temporal bound the rule table declares? It answers it as a
difference-constraint system, and it returns the timestamps that would have to be
disbelieved to restore consistency. It never removes a licence; that rule is enforced in
the liveness stage and tested there.

THE DIRECTION THAT MATTERS, tested in `TestNothingIsVoided` at the end: a correction set
names timestamps, not licences. An implementation that took the next step and dropped the
disputed licences would shrink P_max, and a smaller P_max can only move a verdict toward
ROBUST, which hands the attacker the verdict. Part II 65.6 forbids it.
"""

from __future__ import annotations

import pathlib
import sys
import types
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_vs import temporal  # noqa: E402

SECOND = 1_000_000_000


def _event(source: str, seq: int, t_s: int, tag: str = "") -> types.SimpleNamespace:
    """The four members the pass reads from a canonical event."""
    return types.SimpleNamespace(
        event_id=f"ev:{source}-{seq:04d}{tag}",
        source_id=f"src:{source}",
        seq=seq,
        t_evt_ns=t_s * SECOND,
    )


def _clean() -> tuple[types.SimpleNamespace, ...]:
    """One source, three records, ascending in seq and in time."""
    return (_event("iam", 0, 10), _event("iam", 1, 20), _event("iam", 2, 30))


def _backdated() -> tuple[types.SimpleNamespace, ...]:
    """The last record moved before both of its predecessors, keeping its seq."""
    return (_event("iam", 0, 10), _event("iam", 1, 20), _event("iam", 2, 5))


class TestConstraints(unittest.TestCase):
    def test_seq_monotonicity_is_built_per_source_between_neighbours(self) -> None:
        constraints = temporal.build_constraints(_clean())
        monotonic = [c for c in constraints if c.kind == temporal.KIND_SEQ_MONOTONIC]
        self.assertEqual(len(monotonic), 2)
        for constraint in monotonic:
            self.assertEqual(constraint.weight, 0)

    def test_two_sources_never_constrain_each_other(self) -> None:
        events = (_event("iam", 0, 10), _event("gw", 0, 99))
        monotonic = [
            c
            for c in temporal.build_constraints(events)
            if c.kind == temporal.KIND_SEQ_MONOTONIC
        ]
        self.assertEqual(monotonic, [])

    def test_every_event_is_pinned_by_its_recorded_timestamp(self) -> None:
        """A pin is a PAIR of edges, an upper and a lower, so three events give six."""
        constraints = temporal.build_constraints(_clean())
        pins = [c for c in constraints if c.kind == temporal.KIND_PIN]
        self.assertEqual(len(pins), 6)
        self.assertEqual({c.event_id for c in pins}, {e.event_id for e in _clean()})

    def test_constraints_are_canonically_ordered(self) -> None:
        forward = temporal.build_constraints(_clean())
        backward = temporal.build_constraints(tuple(reversed(_clean())))
        self.assertEqual(forward, backward)


class TestViolations(unittest.TestCase):
    def test_a_consistent_source_has_none(self) -> None:
        result = temporal.run_pass(_clean(), cap=8)
        self.assertEqual(result.violations, ())
        self.assertEqual(result.correction_set, ())
        self.assertEqual(result.disputed_sources, ())

    def test_a_backdated_record_contradicts_its_neighbour_in_seq_order(self) -> None:
        """Constraints are built between neighbours, and any inversion shows in at least
        one of them, so one record moved back is one violated pair, not one per
        predecessor."""
        result = temporal.run_pass(_backdated(), cap=8)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].events, ("ev:iam-0002", "ev:iam-0001"))

    def test_each_violation_is_a_negative_cycle(self) -> None:
        result = temporal.run_pass(_backdated(), cap=8)
        for violation in result.violations:
            cycle = violation.cycle()
            self.assertLess(sum(c.weight for c in cycle), 0)
            self.assertEqual(len(cycle), 3)

    def test_equal_timestamps_do_not_violate_monotonicity(self) -> None:
        """seq requires non-decreasing time, not strictly increasing."""
        events = (_event("iam", 0, 10), _event("iam", 1, 10))
        self.assertEqual(temporal.run_pass(events, cap=8).violations, ())


class TestCorrectionSet(unittest.TestCase):
    def test_one_backdated_record_is_one_correction(self) -> None:
        """And it is the record that moved, not its innocent neighbour. A cover of the one
        violated pair could name either; the subsequence formulation names this one."""
        result = temporal.run_pass(_backdated(), cap=8)
        self.assertEqual(result.correction_set, ("ev:iam-0002",))
        self.assertFalse(result.greedy)

    def test_a_record_moved_far_back_is_named_over_its_many_neighbours(self) -> None:
        """The shape of the pre-registered cell: one record moved behind a long ascending
        run. Disbelieving it costs one timestamp; disbelieving the run costs many."""
        events = [_event("iam", index, 100 + index * 10) for index in range(12)]
        events.append(_event("iam", 12, 50))
        result = temporal.run_pass(tuple(events), cap=4)
        self.assertEqual(result.correction_set, ("ev:iam-0012",))
        self.assertEqual(result.disputed_sources, ("src:iam",))

    def test_the_disputed_source_is_named_and_no_other(self) -> None:
        events = (*_backdated(), _event("gw", 0, 7), _event("gw", 1, 8))
        result = temporal.run_pass(events, cap=8)
        self.assertEqual(result.disputed_sources, ("src:iam",))

    def test_two_independent_backdates_need_two_corrections(self) -> None:
        events = (
            _event("iam", 0, 10),
            _event("iam", 1, 5),
            _event("gw", 0, 10),
            _event("gw", 1, 4),
        )
        result = temporal.run_pass(events, cap=8)
        self.assertEqual(len(result.correction_set), 2)
        self.assertEqual(result.disputed_sources, ("src:gw", "src:iam"))

    def test_a_tie_is_broken_lexicographically(self) -> None:
        """Two records, each of which alone explains the single contradiction."""
        events = (_event("iam", 0, 20), _event("iam", 1, 10))
        result = temporal.run_pass(events, cap=8)
        self.assertEqual(result.correction_set, ("ev:iam-0000",))

    def test_removing_the_correction_set_restores_feasibility(self) -> None:
        result = temporal.run_pass(_backdated(), cap=8)
        self.assertTrue(
            temporal.feasible(
                result.constraints,
                {e.event_id: e.t_evt_ns for e in _backdated()},
                removed=frozenset(result.correction_set),
            )
        )

    def test_the_unreduced_system_is_infeasible(self) -> None:
        self.assertFalse(
            temporal.feasible(
                temporal.build_constraints(_backdated()),
                {e.event_id: e.t_evt_ns for e in _backdated()},
                removed=frozenset(),
            )
        )

    def test_many_disordered_sources_stay_exact(self) -> None:
        """The subsequence formulation is exact at any size, so the cap does not apply to
        it: six disordered sources cost six corrections and nothing is flagged greedy."""
        events = []
        for index in range(6):
            events.append(_event(f"s{index}", 0, 10))
            events.append(_event(f"s{index}", 1, 1))
        result = temporal.run_pass(tuple(events), cap=4)
        self.assertFalse(result.greedy)
        self.assertEqual(len(result.correction_set), 6)

    def test_the_rule_cover_goes_greedy_above_the_cap_and_says_so(self) -> None:
        """The cap governs the rule-derived cover only. This table never reaches it: every
        seq rule here binds one slot, so the greedy branch is unreachable in this
        configuration and is exercised directly instead."""
        pairs = [(f"ev:a{i:02d}", f"ev:b{i:02d}") for i in range(6)]
        violations = tuple(
            temporal.Violation(
                constraint=temporal.Constraint(
                    u=left, v=right, weight=0, kind=temporal.KIND_RULE_SEQ
                ),
                excess_ns=1,
                pins=(
                    temporal.Constraint(u=right, v=temporal.ZERO_NODE, weight=0, kind=temporal.KIND_PIN),
                    temporal.Constraint(u=temporal.ZERO_NODE, v=left, weight=0, kind=temporal.KIND_PIN),
                ),
            )
            for left, right in pairs
        )
        chosen, greedy = temporal.correction_set(violations, cap=4)
        self.assertTrue(greedy)
        self.assertEqual(len(chosen), 6)
        exact, exact_greedy = temporal.correction_set(violations, cap=64)
        self.assertFalse(exact_greedy)
        self.assertEqual(len(exact), 6)

    def test_a_pair_already_corrected_is_not_covered_twice(self) -> None:
        violations = (
            temporal.Violation(
                constraint=temporal.Constraint(
                    u="ev:a", v="ev:b", weight=0, kind=temporal.KIND_RULE_SEQ
                ),
                excess_ns=1,
                pins=(
                    temporal.Constraint(u="ev:b", v=temporal.ZERO_NODE, weight=0, kind=temporal.KIND_PIN),
                    temporal.Constraint(u=temporal.ZERO_NODE, v="ev:a", weight=0, kind=temporal.KIND_PIN),
                ),
            ),
        )
        self.assertEqual(temporal.correction_set(violations, cap=8, already=("ev:a",)), ((), False))


class TestRuleBounds(unittest.TestCase):
    def test_a_seq_rule_with_one_evidence_slot_constrains_no_pair(self) -> None:
        """Every seq rule in this table carries evidence for one slot, so the pass builds
        no rule-derived edge from it. The narrowing is real and is pinned here."""
        instance = types.SimpleNamespace(
            rule_id="rl:r0005",
            evidence=(types.SimpleNamespace(binding="b", event_id="ev:iam-0001"),),
        )
        rule = types.SimpleNamespace(op="seq", left="a", right="b", within_ns=1800 * SECOND)
        constraints = temporal.build_constraints(
            _clean(), instances=(instance,), rule_seq={"rl:r0005": rule}
        )
        self.assertEqual([c for c in constraints if c.kind == temporal.KIND_RULE_SEQ], [])

    def test_a_seq_rule_with_both_slots_bound_constrains_the_pair(self) -> None:
        instance = types.SimpleNamespace(
            rule_id="rl:r0005",
            evidence=(
                types.SimpleNamespace(binding="a", event_id="ev:iam-0000"),
                types.SimpleNamespace(binding="b", event_id="ev:iam-0001"),
            ),
        )
        rule = types.SimpleNamespace(op="seq", left="a", right="b", within_ns=1800 * SECOND)
        constraints = temporal.build_constraints(
            _clean(), instances=(instance,), rule_seq={"rl:r0005": rule}
        )
        derived = [c for c in constraints if c.kind == temporal.KIND_RULE_SEQ]
        self.assertEqual(len(derived), 2)
        self.assertEqual(
            sorted(c.weight for c in derived), [-1, 1800 * SECOND]
        )

    def test_a_violated_rule_bound_is_found(self) -> None:
        """The two records are 40 minutes apart; the rule allows 30."""
        events = (_event("iam", 0, 0), _event("iam", 1, 2400))
        instance = types.SimpleNamespace(
            rule_id="rl:r0005",
            evidence=(
                types.SimpleNamespace(binding="a", event_id="ev:iam-0000"),
                types.SimpleNamespace(binding="b", event_id="ev:iam-0001"),
            ),
        )
        rule = types.SimpleNamespace(op="seq", left="a", right="b", within_ns=1800 * SECOND)
        result = temporal.run_pass(events, instances=(instance,), rule_seq={"rl:r0005": rule}, cap=8)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].constraint.kind, temporal.KIND_RULE_SEQ)


class TestDeterminism(unittest.TestCase):
    def test_the_result_does_not_depend_on_input_order(self) -> None:
        events = _backdated()
        forward = temporal.run_pass(events, cap=8)
        backward = temporal.run_pass(tuple(reversed(events)), cap=8)
        self.assertEqual(forward.correction_set, backward.correction_set)
        self.assertEqual(forward.constraints, backward.constraints)
        self.assertEqual(
            [v.constraint for v in forward.violations],
            [v.constraint for v in backward.violations],
        )


class TestNothingIsVoided(unittest.TestCase):
    """Part II 65.6: the pass names timestamps, never licences."""

    def test_the_result_carries_no_licence_and_no_instance(self) -> None:
        import dataclasses

        result = temporal.run_pass(_backdated(), cap=8)
        members = {field.name for field in dataclasses.fields(result)}
        self.assertNotIn("voided", members)
        for name in members:
            self.assertNotIn("licen", name, name)

    def test_a_correction_names_events_not_licences(self) -> None:
        result = temporal.run_pass(_backdated(), cap=8)
        for event_id in result.correction_set:
            self.assertTrue(event_id.startswith("ev:"), event_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
