"""Unit tests for S2, the seeded generator.

Run from the repository root:

    python python/spectra_vs/tests/test_gen.py

What these tests are for. The generator's whole value is that it is reproducible and that
its two output streams never meet. The determinism tests therefore compare OCTETS rather
than asserting that something "looks sorted", so that a mutation to an ordering key turns
a named gate red instead of producing a differently-ordered file that still passes.

The label-purity tests are the ones that matter most: a truth key reaching a raw record
is the defect the whole design exists to prevent, and it has to be caught here rather
than at ingest, because by ingest the leak is already in a file somebody hashed.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import canon  # noqa: E402
from spectra_core.errors import SchemaError  # noqa: E402
from spectra_core.ids import EventId, RecordId, SourceId  # noqa: E402
from spectra_core.model import CanonicalEvent, TruthKind, TruthOrigin  # noqa: E402

from spectra_vs import gen  # noqa: E402
from spectra_vs import scenario as scn  # noqa: E402

FIXTURE = _REPO_ROOT / "config" / "vs" / "scenario.toml"

#: Analysis-band seeds, disjoint from the calibration band [1000000, 1000063].
SEED_A = 20240204
SEED_B = 20240205

#: Truth keys ingest rejects outright, from data contract 4.
_FORBIDDEN_KEYS = ("label", "is_attack", "scenario", "truth")

_SPEC = scn.load_scenario(FIXTURE)
_RESULT_A = gen.gen(_SPEC, SEED_A)


class TestDraws(unittest.TestCase):
    def test_draw_is_a_pure_function(self) -> None:
        self.assertEqual(
            gen.draw_u64(7, "jitter", "idp_login", 3), gen.draw_u64(7, "jitter", "idp_login", 3)
        )

    def test_domain_separates(self) -> None:
        self.assertNotEqual(
            gen.draw_u64(7, "jitter", "idp_login", 3),
            gen.draw_u64(7, "principal", "idp_login", 3),
        )

    def test_seed_separates(self) -> None:
        self.assertNotEqual(
            gen.draw_u64(7, "jitter", "idp_login", 3), gen.draw_u64(8, "jitter", "idp_login", 3)
        )

    def test_draw_below_respects_its_bound(self) -> None:
        for index in range(500):
            value = gen.draw_below(7, 11, "test", index)
            self.assertTrue(0 <= value < 7)

    def test_draw_below_covers_its_range(self) -> None:
        seen = {gen.draw_below(4, 11, "test", index) for index in range(200)}
        self.assertEqual(seen, {0, 1, 2, 3})

    def test_zero_bound_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            gen.draw_below(0, 1, "test")

    def test_bool_key_part_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            gen.draw_u64(1, "test", True)

    def test_pick_is_stable(self) -> None:
        choices = ("a", "b", "c")
        self.assertEqual(gen.pick(choices, 3, "d", 1), gen.pick(choices, 3, "d", 1))


class TestRawEvent(unittest.TestCase):
    def test_event_id_matches_the_canonical_event_it_will_become(self) -> None:
        raw = gen.RawEvent(
            source_id=SourceId.of("iam_audit"),
            seq=17,
            t_evt_ns=1707004800000000000,
            event_type="iam_role_assumed",
            attrs=(("principal", "p_attacker"),),
        )
        canonical = CanonicalEvent(
            event_id=raw.event_id,
            record_id=RecordId.mint(b"whatever bytes ingest happened to read"),
            source_id=raw.source_id,
            seq=raw.seq,
            event_type=raw.event_type,
            t_evt_ns=raw.t_evt_ns,
            t_ing_ns=raw.t_evt_ns + 1_000_000,
            attrs=raw.attrs,
        )
        self.assertTrue(canonical.verify_id())
        self.assertEqual(raw.event_id, EventId.mint(canonical.identity_bytes()))

    def test_ingestion_time_does_not_move_the_id(self) -> None:
        raw = gen.RawEvent(
            source_id=SourceId.of("gw_access"),
            seq=0,
            t_evt_ns=1707004800000000000,
            event_type="gw_request",
        )
        first = CanonicalEvent(
            event_id=raw.event_id,
            record_id=RecordId.mint(b"a"),
            source_id=raw.source_id,
            seq=0,
            event_type="gw_request",
            t_evt_ns=raw.t_evt_ns,
            t_ing_ns=raw.t_evt_ns + 1,
        )
        second = CanonicalEvent(
            event_id=raw.event_id,
            record_id=RecordId.mint(b"b"),
            source_id=raw.source_id,
            seq=0,
            event_type="gw_request",
            t_evt_ns=raw.t_evt_ns,
            t_ing_ns=raw.t_evt_ns + 900_000,
        )
        self.assertEqual(first.event_id, second.event_id)

    def test_unsorted_attrs_are_rejected(self) -> None:
        with self.assertRaises(Exception):
            gen.RawEvent(
                source_id=SourceId.of("gw_access"),
                seq=0,
                t_evt_ns=1,
                event_type="gw_request",
                attrs=(("z", "1"), ("a", "2")),
            )

    def test_wire_shape_is_the_contract(self) -> None:
        raw = _RESULT_A.raw[0]
        document = gen.raw_to_scf(raw)
        self.assertEqual(
            sorted(document), ["attrs", "event_type", "seq", "source_id", "t_evt_ns"]
        )
        self.assertIsInstance(document["t_evt_ns"], str)
        self.assertIsInstance(document["seq"], int)
        self.assertNotIn(":", document["source_id"])


class TestDeterminism(unittest.TestCase):
    def test_same_seed_is_byte_identical(self) -> None:
        again = gen.gen(_SPEC, SEED_A)
        self.assertEqual(_RESULT_A.raw_bytes, again.raw_bytes)
        self.assertEqual(_RESULT_A.truth_bytes, again.truth_bytes)
        self.assertEqual(_RESULT_A.raw_hash, again.raw_hash)

    def test_a_different_seed_differs(self) -> None:
        other = gen.gen(_SPEC, SEED_B)
        self.assertNotEqual(_RESULT_A.raw_bytes, other.raw_bytes)
        self.assertEqual(len(_RESULT_A.raw), len(other.raw))

    def test_raw_file_order_is_strictly_ascending(self) -> None:
        keys = [r.sort_key() for r in _RESULT_A.raw]
        canon.check_strictly_ascending(keys, lambda k: k, where="test.raw")

    def test_truth_file_order_is_strictly_ascending(self) -> None:
        keys = [t.truth_id for t in _RESULT_A.truth]
        canon.check_strictly_ascending(keys, canon.byte_order_key, where="test.truth")

    def test_hash_label_names_what_was_computed(self) -> None:
        self.assertTrue(_RESULT_A.raw_hash.startswith("b2b256:"))
        self.assertNotIn("blake3", _RESULT_A.raw_hash)
        self.assertNotEqual(_RESULT_A.raw_hash, _RESULT_A.truth_hash)

    def test_output_has_no_cr_and_ends_in_one_lf(self) -> None:
        payload = _RESULT_A.raw_bytes
        self.assertNotIn(b"\r", payload)
        self.assertTrue(payload.endswith(b"\n"))
        self.assertFalse(payload.endswith(b"\n\n"))

    def test_no_float_reaches_the_wire(self) -> None:
        text = _RESULT_A.raw_bytes.decode("utf-8")
        for token in ("NaN", "Infinity", "e+", "E+"):
            self.assertNotIn(token, text)


class TestSequencing(unittest.TestCase):
    def test_seq_is_dense_and_ascending_per_source(self) -> None:
        for source in _SPEC.sources:
            name = scn.source_key(source.source_id)
            seqs = [r.seq for r in _RESULT_A.raw if scn.source_key(r.source_id) == name]
            self.assertEqual(seqs, sorted(seqs))
            self.assertEqual(seqs, list(range(len(seqs))))

    def test_event_ids_are_unique(self) -> None:
        ids = [str(r.event_id) for r in _RESULT_A.raw]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_record_is_inside_the_horizon(self) -> None:
        for record in _RESULT_A.raw:
            self.assertTrue(_SPEC.horizon.contains(record.t_evt_ns))

    def test_every_record_type_is_declared_by_its_source(self) -> None:
        for record in _RESULT_A.raw:
            declared = _SPEC.source(record.source_id).emits_event_types
            self.assertIn(record.event_type, declared)


class TestDeclaredBlindness(unittest.TestCase):
    def test_the_silent_source_emits_nothing_ever(self) -> None:
        self.assertEqual(_RESULT_A.records_of("edr_host"), ())

    def test_no_record_falls_inside_a_declared_blind_window(self) -> None:
        for record in _RESULT_A.raw:
            self.assertFalse(_SPEC.is_declared_blind(record.source_id, record.t_evt_ns))

    def test_the_declared_gateway_outage_is_a_real_hole(self) -> None:
        window = _SPEC.blind_windows("gw_access")[0]
        inside = [
            r
            for r in _RESULT_A.records_of("gw_access")
            if window.contains(r.t_evt_ns)
        ]
        self.assertEqual(inside, [])


class TestCalibrationVolume(unittest.TestCase):
    def test_every_emitting_source_clears_the_calibration_floor(self) -> None:
        for source in _SPEC.sources:
            if not source.emits_event_types:
                continue
            count = len(_RESULT_A.records_of(source.source_id))
            self.assertGreaterEqual(count, 2000, scn.source_key(source.source_id))

    def test_gaps_are_not_all_identical(self) -> None:
        times = sorted(r.t_evt_ns for r in _RESULT_A.records_of("idp_auth"))
        gaps = {b - a for a, b in zip(times, times[1:])}
        self.assertGreater(len(gaps), 100)


class TestTruthStream(unittest.TestCase):
    def test_one_annotation_per_record_plus_the_unobservable_steps(self) -> None:
        unobservable = [s for s in _SPEC.attack.steps if not s.observable]
        self.assertEqual(len(_RESULT_A.truth), len(_RESULT_A.raw) + len(unobservable))

    def test_the_unobservable_step_is_representable(self) -> None:
        unobserved = _RESULT_A.unobserved_steps()
        self.assertEqual(len(unobserved), 1)
        annotation = unobserved[0]
        self.assertEqual(annotation.step_k, 1)
        self.assertEqual(annotation.step_action, "token_acquire")
        self.assertEqual(annotation.chain_id, "vs-01")
        self.assertFalse(annotation.observable)
        self.assertIsNone(annotation.event_id)
        self.assertEqual(annotation.producing_sources, ())
        self.assertIs(annotation.origin, TruthOrigin.SCENARIO)

    def test_the_unobservable_step_emitted_no_record(self) -> None:
        step = next(s for s in _SPEC.attack.steps if not s.observable)
        t_ns = _SPEC.epoch_ns + step.t_offset_ns
        self.assertEqual([r for r in _RESULT_A.raw if r.t_evt_ns == t_ns], [])

    def test_every_observable_step_has_an_annotation_citing_its_record(self) -> None:
        by_event = {str(t.event_id): t for t in _RESULT_A.truth if t.event_id is not None}
        for step in _SPEC.attack.steps:
            if not step.observable:
                continue
            found = [
                t
                for t in _RESULT_A.truth
                if t.kind is TruthKind.ATTACK_STEP and t.step_k == step.k
            ]
            self.assertEqual(len(found), len(step.emits), f"k={step.k}")
            for annotation in found:
                self.assertIn(str(annotation.event_id), by_event)
                self.assertTrue(annotation.observable)
                self.assertEqual(annotation.true_transition, step.expect_transition)

    def test_attack_annotations_cite_exactly_the_chain(self) -> None:
        attack = [t for t in _RESULT_A.truth if t.kind is TruthKind.ATTACK_STEP]
        self.assertEqual(sorted({t.step_k for t in attack}), [2, 3, 4, 5, 6, 7, 8])
        for annotation in attack:
            self.assertEqual(annotation.chain_id, "vs-01")

    def test_benign_annotations_carry_no_chain(self) -> None:
        for annotation in _RESULT_A.truth:
            if annotation.kind is not TruthKind.BENIGN:
                continue
            self.assertIsNone(annotation.chain_id)
            self.assertIsNone(annotation.step_k)
            self.assertIs(annotation.origin, TruthOrigin.POPULATION)

    def test_sim_tick_is_relative_to_the_scenario_epoch(self) -> None:
        for annotation in _RESULT_A.truth:
            self.assertTrue(0 <= annotation.sim_tick < _SPEC.horizon_ticks)

    def test_truth_wire_shape_omits_absent_members(self) -> None:
        annotation = _RESULT_A.unobserved_steps()[0]
        document = gen.truth_to_scf(annotation)
        self.assertNotIn("event_id", document)
        self.assertEqual(document["producing_sources"], [])
        self.assertIs(document["observable"], False)
        self.assertNotIn(None, document.values())


class TestLabelPurity(unittest.TestCase):
    def test_no_raw_record_carries_a_truth_key(self) -> None:
        for record in _RESULT_A.raw:
            document = gen.raw_to_scf(record)
            for key in _FORBIDDEN_KEYS:
                self.assertNotIn(key, document)
                self.assertNotIn(key, document["attrs"])
            for key in document["attrs"]:
                self.assertFalse(key.startswith("__truth"))

    def test_raw_bytes_contain_no_truth_vocabulary(self) -> None:
        payload = _RESULT_A.raw_bytes
        for token in (b'"label"', b'"is_attack"', b'"truth"', b"__truth", b"attack_step"):
            self.assertNotIn(token, payload)

    def test_no_raw_record_names_a_chain_or_a_step(self) -> None:
        for record in _RESULT_A.raw:
            self.assertNotIn("chain_id", dict(record.attrs))
            self.assertNotIn("step_k", dict(record.attrs))

    def test_the_two_streams_share_only_the_event_id(self) -> None:
        raw_ids = {str(r.event_id) for r in _RESULT_A.raw}
        truth_ids = {str(t.event_id) for t in _RESULT_A.truth if t.event_id is not None}
        self.assertEqual(raw_ids, truth_ids)


class TestWriters(unittest.TestCase):
    def test_render_matches_write(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "raw.jsonl"
            written = gen.write_raw(path, _RESULT_A.raw)
            self.assertEqual(written, _RESULT_A.raw_bytes)
            self.assertEqual(path.read_bytes(), _RESULT_A.raw_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
