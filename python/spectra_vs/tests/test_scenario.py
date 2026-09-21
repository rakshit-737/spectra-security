"""Unit tests for the scenario loader and for the SCF-lite serialiser.

Run from the repository root:

    python python/spectra_vs/tests/test_scenario.py

Run directly rather than through a runner, for the same reason `spectra_core`'s suite is:
there is no pytest on this machine and a slice that needs a package manager to test itself
is not testable here at all.

What these tests are for. Each one pins a property a later stage is entitled to assume:
that the fixture loads, that its hash is stable, that the loader constraints from the
operative contract actually reject, and that the encoding law is enforced at the
serialiser rather than discovered inside an archived artifact.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import tomllib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core.errors import CanonError, SchemaError  # noqa: E402
from spectra_core.model import IntegrityClass  # noqa: E402

from spectra_vs import scenario as scn  # noqa: E402
from spectra_vs import scf  # noqa: E402

FIXTURE = _REPO_ROOT / "config" / "vs" / "scenario.toml"


def _document() -> dict:
    with open(FIXTURE, "rb") as handle:
        return tomllib.load(handle)


# ---------------------------------------------------------------------------
# SCF-lite
# ---------------------------------------------------------------------------


class TestScf(unittest.TestCase):
    def test_keys_are_sorted_and_compact(self) -> None:
        self.assertEqual(scf.scf_dumps({"b": "1", "a": "2"}), '{"a":"2","b":"1"}')

    def test_float_is_rejected(self) -> None:
        with self.assertRaises(CanonError):
            scf.scf_dumps({"x": 1.5})

    def test_null_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            scf.scf_dumps({"x": None})

    def test_wide_integer_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            scf.scf_dumps({"t_evt_ns": 1707004800000000000})

    def test_negative_integer_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            scf.scf_dumps({"n": -1})

    def test_bad_key_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            scf.scf_dumps({"Event-Type": "x"})

    def test_line_has_exactly_one_trailing_lf(self) -> None:
        line = scf.scf_line({"a": "b"})
        self.assertTrue(line.endswith("\n"))
        self.assertFalse(line.endswith("\n\n"))

    def test_jsonl_has_no_cr(self) -> None:
        payload = scf.render_jsonl([{"a": "1"}, {"a": "2"}])
        self.assertNotIn(b"\r", payload)
        self.assertEqual(payload.count(b"\n"), 2)

    def test_booleans_survive(self) -> None:
        self.assertEqual(scf.scf_dumps({"observable": False}), '{"observable":false}')


# ---------------------------------------------------------------------------
# The fixture
# ---------------------------------------------------------------------------


class TestFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = scn.load_scenario(FIXTURE)

    def test_identity(self) -> None:
        self.assertEqual(self.spec.scenario_id, "vs-01-token-pivot")
        self.assertEqual(self.spec.family, "token_pivot")
        self.assertEqual(self.spec.schema, scn.SCENARIO_SCHEMA)
        self.assertEqual(self.spec.tick_granularity_ns, 1_000_000_000)

    def test_six_sources_one_of_which_emits_nothing(self) -> None:
        self.assertEqual(len(self.spec.sources), 6)
        silent = [s for s in self.spec.sources if not s.emits_event_types]
        self.assertEqual([scn.source_key(s.source_id) for s in silent], ["edr_host"])

    def test_sources_are_byte_ordered(self) -> None:
        names = [scn.source_key(s.source_id) for s in self.spec.sources]
        self.assertEqual(names, sorted(names))

    def test_integrity_classes_cover_the_ladder(self) -> None:
        classes = {scn.source_key(s.source_id): s.integrity_class for s in self.spec.sources}
        self.assertIs(classes["idp_auth"], IntegrityClass.CHAINED)
        self.assertIs(classes["iam_audit"], IntegrityClass.CHAINED)
        self.assertIs(classes["gw_access"], IntegrityClass.SEQUENCED)
        self.assertIs(classes["res_access"], IntegrityClass.NONE)

    def test_exactly_one_source_declares_a_nominal_period(self) -> None:
        declared = [s for s in self.spec.sources if s.nominal_period_ns is not None]
        self.assertEqual([scn.source_key(s.source_id) for s in declared], ["idp_auth"])

    def test_two_routes_eight_steps_one_unobservable(self) -> None:
        steps = self.spec.attack.steps
        self.assertEqual([s.k for s in steps], [1, 2, 3, 4, 5, 6, 7, 8])
        unobservable = [s for s in steps if not s.observable]
        self.assertEqual(len(unobservable), 1)
        self.assertEqual(unobservable[0].k, 1)
        self.assertEqual(unobservable[0].emits, ())
        self.assertIsNone(unobservable[0].event_type)

    def test_the_bulk_read_reads_three_distinct_resources_in_the_window(self) -> None:
        """r0003 heads the goal and requires three distinct resources within ten
        minutes.  A scenario that reads fewer cannot fire its own observed route,
        which is what made Psi_min empty in the first end-to-end run."""
        reads = [s for s in self.spec.attack.steps if s.action == "bulk_read"]
        resources = {dict(s.attrs)["resource"] for s in reads}
        self.assertGreaterEqual(len(resources), 3)
        offsets = [int(s.t_offset_ns) for s in reads]
        self.assertLess(max(offsets) - min(offsets), 600 * 10**9)

    def test_every_observable_step_emits_a_declared_event_type(self) -> None:
        for step in self.spec.attack.steps:
            if not step.observable:
                continue
            for source_id in step.emits:
                self.assertIn(step.event_type, self.spec.source(str(source_id)).emits_event_types)

    def test_declared_blind_windows(self) -> None:
        self.assertEqual(len(self.spec.blindness), 2)
        edr = self.spec.blind_windows("edr_host")
        self.assertEqual(len(edr), 1)
        self.assertEqual(edr[0].t0_ns, self.spec.horizon.t0_ns)
        self.assertEqual(edr[0].t1_ns, self.spec.horizon.t1_ns)
        self.assertEqual(len(self.spec.blind_windows("gw_access")), 1)

    def test_no_attack_step_falls_in_a_declared_blind_window(self) -> None:
        for step in self.spec.attack.steps:
            t_ns = self.spec.epoch_ns + step.t_offset_ns
            for source_id in step.emits:
                self.assertFalse(self.spec.is_declared_blind(str(source_id), t_ns))

    def test_phases_partition_the_horizon(self) -> None:
        self.assertEqual([p.regime_id for p in self.spec.phases], ["steady", "burst"])
        self.assertEqual(self.spec.phases[0].interval.t1_ns, self.spec.phases[1].interval.t0_ns)
        self.assertEqual(self.spec.phases[0].interval.t0_ns, self.spec.horizon.t0_ns)
        self.assertEqual(self.spec.phases[-1].interval.t1_ns, self.spec.horizon.t1_ns)

    def test_phase_lookup_is_half_open(self) -> None:
        boundary = self.spec.phases[0].interval.t1_ns
        found = self.spec.phase_of(boundary)
        self.assertIsNotNone(found)
        self.assertEqual(found.regime_id, "burst")
        self.assertIsNone(self.spec.phase_of(self.spec.horizon.t1_ns))

    def test_every_noise_family_binds_to_exactly_one_source(self) -> None:
        for family in self.spec.noise.families:
            self.assertIsNotNone(self.spec.source_of_event_type(family))

    def test_goal_is_singular_and_hashes_on_its_own(self) -> None:
        self.assertEqual(self.spec.goal.goal_predicate, "resource.exfiltrated")
        self.assertEqual(self.spec.goal.goal_args, ("p_attacker", "rs_customer_db"))
        self.assertTrue(self.spec.goal_hash().startswith("b2b256:"))
        self.assertNotEqual(self.spec.goal_hash(), self.spec.scenario_hash())

    def test_hashes_are_labelled_with_what_was_computed(self) -> None:
        for value in (self.spec.scenario_hash(), self.spec.goal_hash()):
            self.assertTrue(value.startswith("b2b256:"))
            self.assertNotIn("blake3", value)
            self.assertEqual(len(value), len("b2b256:") + 64)

    def test_hash_is_stable_across_reloads(self) -> None:
        again = scn.load_scenario(FIXTURE)
        self.assertEqual(self.spec.scenario_hash(), again.scenario_hash())
        self.assertEqual(self.spec.canonical_bytes(), again.canonical_bytes())

    def test_generator_config_hash_tracks_the_scenario(self) -> None:
        self.assertEqual(self.spec.generator_config_hash(), self.spec.scenario_hash())

    def test_excluded_intervals_hash_is_independent_of_the_rest(self) -> None:
        self.assertTrue(self.spec.excluded_intervals_hash().startswith("b2b256:"))
        self.assertNotEqual(self.spec.excluded_intervals_hash(), self.spec.scenario_hash())

    def test_summary_is_canonical(self) -> None:
        summary = scn.scenario_summary(self.spec)
        self.assertIn('"scenario_id":"vs-01-token-pivot"', summary)


# ---------------------------------------------------------------------------
# Loader constraints. Each of these must reject.
# ---------------------------------------------------------------------------


class TestLoaderConstraints(unittest.TestCase):
    def _mutated(self, mutate) -> None:
        document = copy.deepcopy(_document())
        mutate(document)
        with self.assertRaises(SchemaError):
            scn.parse_scenario(document)

    def test_wrong_schema_is_rejected(self) -> None:
        self._mutated(lambda d: d.__setitem__("schema", "spectra.vs.scenario/2"))

    def test_bad_scenario_id_is_rejected(self) -> None:
        self._mutated(lambda d: d.__setitem__("scenario_id", "vs-1-token-pivot"))

    def test_integer_epoch_is_rejected(self) -> None:
        self._mutated(lambda d: d.__setitem__("epoch_ns", 1707004800000000000))

    def test_changed_tick_granularity_is_rejected(self) -> None:
        self._mutated(lambda d: d.__setitem__("tick_granularity_ns", 1_000_000))

    def test_emitting_unobservable_step_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][0]["emits"] = ["idp_auth"]

        self._mutated(mutate)

    def test_observable_step_with_no_emitter_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][1]["emits"] = []

        self._mutated(mutate)

    def test_undeclared_emitting_source_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][1]["emits"] = ["no_such_source"]

        self._mutated(mutate)

    def test_step_emitting_an_event_type_its_source_does_not_declare_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][1]["event_type"] = "res_read"

        self._mutated(mutate)

    def test_every_source_chained_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            for source in document["sources"]:
                source["integrity_class"] = "chained"

        self._mutated(mutate)

    def test_removing_the_silent_source_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["sources"] = [s for s in document["sources"] if s["source_id"] != "edr_host"]

        self._mutated(mutate)

    def test_making_every_step_observable_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][0]["observable"] = True
            document["attack"]["steps"][0]["emits"] = ["idp_auth"]
            document["attack"]["steps"][0]["event_type"] = "idp_login"

        self._mutated(mutate)

    def test_noise_family_naming_an_undeclared_event_type_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["noise"]["families"] = ["no_such_event_type"]

        self._mutated(mutate)

    def test_noise_family_emitted_by_two_sources_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            for source in document["sources"]:
                if source["source_id"] == "net_flow":
                    source["emits_event_types"] = ["gw_health", "net_conn"]

        self._mutated(mutate)

    def test_overlapping_phases_are_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["phases"][1]["t0_ns"] = "1707006000000000000"

        self._mutated(mutate)

    def test_phase_leaving_the_horizon_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["phases"][1]["t1_ns"] = "1707112000000000000"

        self._mutated(mutate)

    def test_step_outside_the_horizon_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][1]["t_offset_ns"] = "99999000000000000"

        self._mutated(mutate)

    def test_blind_window_on_an_undeclared_source_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["blindness"][0]["source_id"] = "no_such_source"

        self._mutated(mutate)

    def test_credential_with_an_undeclared_subject_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["entities"]["credentials"][0]["subject"] = "p_ghost"

        self._mutated(mutate)

    def test_resource_in_an_undeclared_zone_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["entities"]["resources"][0]["zone"] = "nowhere"

        self._mutated(mutate)

    def test_zero_denominator_noise_rate_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["noise"]["benign_rate_den"] = 0

        self._mutated(mutate)

    def test_non_string_attribute_value_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["attack"]["steps"][1]["attrs"]["principal"] = 7

        self._mutated(mutate)

    def test_bad_chain_id_is_rejected(self) -> None:
        self._mutated(lambda d: d["attack"].__setitem__("chain_id", "vs-001"))

    def test_inverted_interval_is_rejected(self) -> None:
        def mutate(document: dict) -> None:
            document["phases"][0]["t1_ns"] = "1707004700000000000"

        self._mutated(mutate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
