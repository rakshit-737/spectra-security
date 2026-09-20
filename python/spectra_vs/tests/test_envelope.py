"""Unit tests for S9: licensed silent instances, GHOSTs and the permanent blind spots.

Run from the repository root:

    python python/spectra_vs/tests/test_envelope.py

The two completeness cells are the point of this file. The calibrated cell is the CONTROL
ARM: nothing is blind on the escalation path, so no silent instance is admitted and the two
programs agree about route B. Without that empty result the degraded cell proves nothing,
which is why it is tested first and just as hard.
"""

from __future__ import annotations

import pathlib
import random
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import canon, model  # noqa: E402
from spectra_core.errors import SchemaError  # noqa: E402
from spectra_core.ids import SourceId  # noqa: E402
from spectra_vs import envelope, ground  # noqa: E402

import fixture  # noqa: E402
from test_ground import _PermutedTable  # noqa: E402

RULES_TOML = _REPO_ROOT / "config" / "vs" / "rules.toml"
SECOND = fixture.SECOND
_LIVE = model.LivenessVerdict.LIVE
_BLIND = model.LivenessVerdict.BLIND
_SUPPRESSED = model.LivenessVerdict.SUPPRESSED


def _table():
    return fixture.rule_table(RULES_TOML)


def _run(complete: bool, **kwargs) -> envelope.EnvelopeResult:
    events, bindings = fixture.cell(complete)
    return envelope.envelope(
        _table(),
        events,
        bindings,
        fixture.liveness(complete),
        fixture.entity_universe(),
        **kwargs,
    )


def _bytes(program: ground.Program) -> bytes:
    return ground.scf_dumps(ground.program_document(program)).encode("utf-8")


def _predicates(program: ground.Program) -> set[str]:
    return {f.predicate for f in program.facts}


# ---------------------------------------------------------------------------
# The liveness view
# ---------------------------------------------------------------------------


class TestLivenessView(unittest.TestCase):
    def setUp(self) -> None:
        self.view = fixture.liveness(False)

    def test_a_window_inside_a_live_run_is_live(self) -> None:
        window = model.Interval(fixture.EPOCH_NS, fixture.EPOCH_NS + SECOND)
        self.assertTrue(self.view.live(SourceId.of("idp_auth"), window))

    def test_a_window_straddling_a_blind_run_is_not_live(self) -> None:
        window = model.Interval(fixture.BLIND_T0_NS - SECOND, fixture.BLIND_T0_NS + SECOND)
        self.assertFalse(self.view.live(SourceId.of("iam_audit"), window))

    def test_an_undescribed_source_is_not_live_and_is_not_licensable(self) -> None:
        """Fail-closed in both directions: silence in the document licenses nothing."""
        window = model.Interval(fixture.EPOCH_NS, fixture.EPOCH_NS + SECOND)
        unknown = SourceId.of("no_such_source")
        self.assertFalse(self.view.live(unknown, window))
        self.assertIsNone(self.view.covering_runs(unknown, window))

    def test_an_uncovered_instant_is_not_licensable(self) -> None:
        beyond = model.Interval(fixture.SPAN_T1_NS, fixture.SPAN_T1_NS + SECOND)
        self.assertIsNone(self.view.covering_runs(SourceId.of("edr_host"), beyond))

    def test_partial_coverage_licenses_nothing(self) -> None:
        """A licence covering part of the interval is the widened-window defect."""
        half = model.Interval(fixture.BLIND_T0_NS, fixture.BLIND_T1_NS + SECOND)
        self.assertIsNone(self.view.covering_runs(SourceId.of("iam_audit"), half))

    def test_runs_merge_only_over_equal_verdict_and_reason(self) -> None:
        source = SourceId.of("x_source")
        view = envelope.LivenessView(
            (
                envelope.SourceLiveness(
                    source_id=source,
                    integrity_class=model.IntegrityClass.NONE,
                    intervals=(
                        envelope.LivenessInterval(0, 10, _BLIND, "B_UNBRACKETED"),
                        envelope.LivenessInterval(10, 20, _BLIND, "B_UNBRACKETED"),
                        envelope.LivenessInterval(20, 30, _BLIND, "B_REGIME_UNKNOWN"),
                    ),
                ),
            )
        )
        runs = view.runs(source)
        self.assertEqual([(r.t0_ns, r.t1_ns, r.reason) for r in runs],
                         [(0, 20, "B_UNBRACKETED"), (20, 30, "B_REGIME_UNKNOWN")])

    def test_joint_blind_windows_need_every_source_blind(self) -> None:
        sources = (SourceId.of("iam_audit"), SourceId.of("idp_auth"))
        self.assertEqual(self.view.joint_blind_windows(sources), ())
        self.assertEqual(
            [(w.t0_ns, w.t1_ns) for w in self.view.joint_blind_windows((SourceId.of("iam_audit"),))],
            [(fixture.BLIND_T0_NS, fixture.BLIND_T1_NS)],
        )

    def test_a_blind_licence_carries_a_reason_and_no_witness(self) -> None:
        run = self.view.runs(SourceId.of("iam_audit"))[0]
        licence = run.licence()
        self.assertIs(licence.basis, model.LicenceBasis.BLIND)
        self.assertEqual(licence.witness, ())
        self.assertEqual(licence.reason, "B_GAP_EXCEEDS_THRESHOLD")

    def test_a_suppressed_licence_carries_its_bracketing_witness(self) -> None:
        source = SourceId.of("gw_access")
        witness = tuple(
            sorted(
                (fixture.make_event("gw_access", i, "gw.request", i * SECOND, {}).event.event_id
                 for i in (0, 1)),
                key=canon.byte_order_key,
            )
        )
        view = envelope.LivenessView(
            (
                envelope.SourceLiveness(
                    source_id=source,
                    integrity_class=model.IntegrityClass.SEQUENCED,
                    intervals=(
                        envelope.LivenessInterval(
                            0, 10, _SUPPRESSED, "S_SEQ_GAP_UNAUTHENTICATED", witness
                        ),
                    ),
                ),
            )
        )
        licence = view.runs(source)[0].licence()
        self.assertIs(licence.basis, model.LicenceBasis.SUPPRESSED)
        self.assertEqual(licence.witness, witness)

    def test_the_document_shape_parses(self) -> None:
        document = {
            "schema": "spectra.liveness/2",
            "sources": [
                {
                    "source_id": "src:iam_audit",
                    "integrity_class": "chained",
                    "intervals": [
                        {"t0_ns": "0", "t1_ns": "10", "verdict": "LIVE", "reason": "L_CALIBRATED_OK"},
                        {
                            "t0_ns": "10",
                            "t1_ns": "20",
                            "verdict": "BLIND",
                            "reason": "B_GAP_EXCEEDS_THRESHOLD",
                        },
                    ],
                }
            ],
        }
        view = envelope.LivenessView.from_document(document)
        self.assertEqual(len(view.runs(SourceId.of("iam_audit"))), 1)
        self.assertTrue(view.live(SourceId.of("iam_audit"), model.Interval(0, 10)))


# ---------------------------------------------------------------------------
# The calibrated cell: the control arm
# ---------------------------------------------------------------------------


class TestCalibratedCell(unittest.TestCase):
    def setUp(self) -> None:
        self.result = _run(True)

    def test_no_silent_detect_instance_is_admitted(self) -> None:
        """iam_audit is live across the escalation, so nothing licenses route B."""
        silent = [
            i
            for i in self.result.p_max.instances
            if str(i.rule_id) == "rl:r0004"
        ]
        self.assertEqual(silent, [])

    def test_route_b_is_absent_from_both_programs(self) -> None:
        for program in (self.result.p_min, self.result.p_max):
            self.assertNotIn("privilege.escalated", _predicates(program))

    def test_the_only_licence_is_the_permanently_blind_declared_source(self) -> None:
        """edr_host is declared and emits nothing ever, so it is blind everywhere."""
        self.assertEqual(
            [(str(lc.source_id), lc.reason) for lc in self.result.licences],
            [("src:edr_host", "B_PROFILE_INSUFFICIENT")],
        )

    def test_the_obligation_produces_exactly_one_ghost(self) -> None:
        self.assertEqual(self.result.p_max.counts.ghost_facts, 1)
        ghost = self.result.p_max.fact(self.result.p_max.ghosts[0])
        self.assertEqual(ghost.predicate, "credential.held")

    def test_the_ghost_contributes_nothing_to_the_observed_count(self) -> None:
        """GHOSTs never enter observed_event_count; the two counters stay separate."""
        self.assertEqual(
            self.result.p_max.counts.observed_events,
            self.result.p_min.counts.observed_events,
        )
        self.assertGreater(self.result.p_max.counts.ghost_facts, 0)


# ---------------------------------------------------------------------------
# The degraded cell: the central idea
# ---------------------------------------------------------------------------


class TestDegradedCell(unittest.TestCase):
    def setUp(self) -> None:
        self.result = _run(False)

    def test_route_b_appears_only_in_the_upper_program(self) -> None:
        self.assertNotIn("privilege.escalated", _predicates(self.result.p_min))
        self.assertIn("privilege.escalated", _predicates(self.result.p_max))

    def test_the_upper_program_reaches_the_goal_by_a_second_route(self) -> None:
        lower = ground.goal_candidates(self.result.p_min, "exfil.bulk_read")
        upper = ground.goal_candidates(self.result.p_max, "exfil.bulk_read")
        self.assertEqual(len(lower), 1)
        self.assertEqual(len(upper), 2)
        self.assertTrue(set(lower).issubset(set(upper)))

    def test_the_silent_instance_carries_the_rule_blocker_and_no_evidence(self) -> None:
        """The blocker survives the silent construction, so a corridor still names the
        control that severs the route."""
        table = _table()
        expected = table.get("rl:r0004").blockers
        silent = [
            i
            for i in self.result.p_max.instances
            if str(i.rule_id) == "rl:r0004" and i.body
        ]
        self.assertTrue(silent)
        for instance in silent:
            self.assertIs(instance.observed, model.Observation.LICENSED)
            self.assertEqual(instance.evidence, ())
            self.assertTrue(instance.license_ids)
            self.assertEqual(instance.blockers, expected)

    def test_the_ghost_premise_carries_no_blocker(self) -> None:
        """No control severs `a sensor could not see`, so the premise is unblockable and
        the rule above it is where the control appears."""
        premises = [
            i
            for i in self.result.p_max.instances
            if str(i.rule_id) == "rl:r0004" and not i.body
        ]
        self.assertTrue(premises)
        for premise in premises:
            self.assertEqual(premise.blockers, ())
            self.assertTrue(premise.ghost)
            self.assertTrue(premise.license_ids)

    def test_the_silent_instance_cites_the_blind_source_and_window(self) -> None:
        cited = {
            str(lid)
            for i in self.result.p_max.instances
            if str(i.rule_id) == "rl:r0004"
            for lid in i.license_ids
        }
        by_id = {str(lc.license_id): lc for lc in self.result.licences}
        self.assertTrue(cited)
        for licence_id in cited:
            licence = by_id[licence_id]
            self.assertEqual(str(licence.source_id), "src:iam_audit")
            self.assertEqual(licence.t0_ns, fixture.BLIND_T0_NS)
            self.assertEqual(licence.t1_ns, fixture.BLIND_T1_NS)

    def test_every_silent_instance_lies_inside_its_cited_licence(self) -> None:
        """The `license_window` realizability check, asserted at the source."""
        by_id = {str(lc.license_id): lc for lc in self.result.licences}
        for instance in self.result.p_max.instances:
            if instance.observed is not model.Observation.LICENSED:
                continue
            instant = instance.tick * model.TICK_GRANULARITY_NS
            for licence_id in instance.license_ids:
                self.assertTrue(by_id[str(licence_id)].interval.contains(instant))

    def test_every_producing_source_is_non_live_over_the_cited_interval(self) -> None:
        view = fixture.liveness(False)
        table = _table()
        by_id = {str(lc.license_id): lc for lc in self.result.licences}
        for instance in self.result.p_max.instances:
            if instance.observed is not model.Observation.LICENSED:
                continue
            rule = table.get(str(instance.rule_id))
            for licence_id in instance.license_ids:
                licence = by_id[str(licence_id)]
                for source_id in rule.rule.producing_sources:
                    self.assertFalse(view.live(source_id, licence.interval))

    def test_one_silent_instance_per_declared_binding(self) -> None:
        """The envelope does not know who escalated, so it admits every candidate."""
        detect = [
            i
            for i in self.result.p_max.instances
            if str(i.rule_id) == "rl:r0004" and i.body
        ]
        users = [e for e in fixture.entity_universe() if e.kind == "user"]
        accounts = [e for e in fixture.entity_universe() if e.kind == "account"]
        self.assertEqual(len(detect), len(users) * len(accounts))

    def test_a_licensed_fact_is_not_constrained_by_a_temporal_window(self) -> None:
        """The representative tick stands for an interval, so the seq window is suspended;
        that is the over-approximating direction and is what keeps PMax a superset."""
        downstream = [i for i in self.result.p_max.instances if str(i.rule_id) == "rl:r0005"]
        self.assertEqual(len(downstream), 1)
        self.assertIs(downstream[0].observed, model.Observation.OBSERVED)

    def test_the_blindness_is_named_rather_than_assumed(self) -> None:
        reasons = sorted({lc.reason for lc in self.result.licences})
        self.assertEqual(reasons, ["B_GAP_EXCEEDS_THRESHOLD", "B_PROFILE_INSUFFICIENT"])


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestStructure(unittest.TestCase):
    def test_p_min_is_contained_in_p_max_in_both_cells(self) -> None:
        for complete in (True, False):
            with self.subTest(complete=complete):
                result = _run(complete)
                lower_facts = {str(f.fact_key) for f in result.p_min.facts}
                upper_facts = {str(f.fact_key) for f in result.p_max.facts}
                self.assertTrue(lower_facts.issubset(upper_facts))
                lower_inst = {str(i.instance_id) for i in result.p_min.instances}
                upper_inst = {str(i.instance_id) for i in result.p_max.instances}
                self.assertTrue(lower_inst.issubset(upper_inst))

    def test_p_min_is_not_mutated_in_place(self) -> None:
        events, bindings = fixture.cell(False)
        alone = ground.ground(_table(), events, bindings).program
        result = _run(False, p_min=alone)
        self.assertEqual(_bytes(alone), _bytes(result.p_min))

    def test_a_containment_violation_is_an_error_not_a_warning(self) -> None:
        events, bindings = fixture.cell(True)
        full = ground.ground(_table(), events, bindings).program
        with self.assertRaises(SchemaError):
            _run(False, p_min=full)

    def test_a_licensed_instance_never_carries_evidence(self) -> None:
        """The record type enforces it; this asserts the stage never tries."""
        for complete in (True, False):
            result = _run(complete)
            for instance in result.p_max.instances:
                if instance.observed is model.Observation.LICENSED:
                    self.assertEqual(instance.evidence, ())
                else:
                    self.assertEqual(instance.license_ids, ())

    def test_a_ghost_is_never_the_sole_support_of_a_propagation(self) -> None:
        table = _table()
        result = _run(False)
        ghosts = {str(g) for g in result.p_max.ghosts}
        for instance in result.p_max.instances:
            rule = table.get(str(instance.rule_id))
            if rule.rule.causal_relation != "PROPAGATES" or not instance.body:
                continue
            self.assertFalse(all(str(key) in ghosts for key in instance.body))

    def test_every_ghost_head_has_a_licensed_instance_behind_it(self) -> None:
        result = _run(False)
        by_head: dict[str, list] = {}
        for instance in result.p_max.instances:
            by_head.setdefault(str(instance.head), []).append(instance)
        for ghost in result.p_max.ghosts:
            supports = by_head[str(ghost)]
            self.assertTrue(supports)
            self.assertTrue(all(i.observed is model.Observation.LICENSED for i in supports))
            self.assertTrue(any(i.license_ids for i in supports))


# ---------------------------------------------------------------------------
# Blind spots
# ---------------------------------------------------------------------------


class TestBlindSpots(unittest.TestCase):
    def test_an_unsatisfied_unlicensed_obligation_makes_no_ghost(self) -> None:
        """The honest admission that the step is invisible, not a pretty inferred node."""
        result = _run(True)
        self.assertEqual(
            [(s.rule_id, s.head_predicate) for s in result.blind_spots],
            [("rl:r0008", "session.issued")],
        )
        self.assertNotIn("session.issued", _predicates(result.p_max))

    def test_an_unsatisfied_licensed_obligation_makes_a_ghost(self) -> None:
        result = _run(True)
        self.assertIn("credential.held", _predicates(result.p_max))
        self.assertNotIn(
            "credential.held", {s.head_predicate for s in result.blind_spots}
        )

    def test_the_blind_spot_names_the_sources_that_could_have_seen(self) -> None:
        result = _run(True)
        spot = result.blind_spots[0]
        self.assertEqual([str(s) for s in spot.producing_sources], ["src:idp_auth"])
        self.assertEqual(spot.reason, "obligation_unsatisfied_and_unlicensed")

    def test_the_blind_spot_artifact_is_canonical(self) -> None:
        result = _run(False)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "blind_spots.json"
            digest = envelope.write_blind_spots(result.blind_spots, path)
            self.assertTrue(digest.startswith(canon.HASH_REF_PREFIX))
            raw = path.read_bytes()
            self.assertTrue(raw.endswith(b"}\n"))
            self.assertNotIn(b"\r", raw)
            self.assertNotIn(b"blake3", raw)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def test_rule_ordering_invariance_over_p_max(self) -> None:
        """The same property as G-D2, over the upper side of the bracket."""
        table = _table()
        events, bindings = fixture.cell(False)
        view = fixture.liveness(False)
        entities = fixture.entity_universe()
        expected = _bytes(envelope.envelope(table, events, bindings, view, entities).p_max)
        for seed in range(16):
            order = list(range(len(table.rules)))
            random.Random(seed).shuffle(order)
            permuted = _PermutedTable(table, order)
            with self.subTest(seed=seed):
                self.assertEqual(
                    _bytes(
                        envelope.envelope(permuted, events, bindings, view, entities).p_max
                    ),
                    expected,
                )

    def test_entity_ordering_invariance(self) -> None:
        table = _table()
        events, bindings = fixture.cell(False)
        view = fixture.liveness(False)
        entities = list(fixture.entity_universe())
        expected = _bytes(envelope.envelope(table, events, bindings, view, entities).p_max)
        for seed in range(8):
            shuffled = list(entities)
            random.Random(seed).shuffle(shuffled)
            with self.subTest(seed=seed):
                self.assertEqual(
                    _bytes(envelope.envelope(table, events, bindings, view, shuffled).p_max),
                    expected,
                )

    def test_licence_ordering_and_identity_are_content_addressed(self) -> None:
        result = _run(False)
        canon.check_strictly_ascending(
            result.licences, lambda lc: lc.sort_key(), where="licences"
        )
        for licence in result.licences:
            self.assertTrue(licence.verify_id())

    def test_the_run_is_a_pure_function_of_its_inputs(self) -> None:
        first, second = _run(False), _run(False)
        self.assertEqual(_bytes(first.p_max), _bytes(second.p_max))
        self.assertEqual(_bytes(first.p_min), _bytes(second.p_min))


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


class TestCaps(unittest.TestCase):
    def test_the_silent_instance_cap_sets_the_flag(self) -> None:
        original = envelope.MAX_SILENT_INSTANCES
        try:
            envelope.MAX_SILENT_INSTANCES = 1
            result = _run(False)
        finally:
            envelope.MAX_SILENT_INSTANCES = original
        self.assertTrue(result.capped)
        self.assertIn("MAX_SILENT_INSTANCES", result.cap_detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
