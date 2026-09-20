"""Unit tests for S6 calibration.

Run from the repository root:

    python python/spectra_vs/tests/test_calibrate.py

Run directly rather than through a runner, matching the foundation's tests, because
there is no pytest on this machine and a stage that needs a package manager to test
itself is not testable here at all.

What these pin, stated so a later edit does not soften them: that the profile is a pure
function of its inputs, that the quantile is an element of the sample rather than an
interpolation, that gaps which would inflate a threshold are dropped rather than kept,
and that the identity of the artifact recomputes from its own bytes.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import canon  # noqa: E402
from spectra_core.errors import CanonError, ProfileError  # noqa: E402
from spectra_core.ids import EventId, RecordId, SourceId  # noqa: E402
from spectra_core.model import CanonicalEvent, IntegrityClass  # noqa: E402
from spectra_vs import calibrate  # noqa: E402
from spectra_vs import scf as shared_scf  # noqa: E402

SECOND = 1000000000
EPOCH = 1700000000000000000


def make_event(
    source: str, seq: int, t_ns: int, event_type: str = "idp.auth", chained: bool = False,
    chain_prev: str | None = None,
) -> CanonicalEvent:
    """Build one bundle record with a correctly minted event id."""
    payload = b"".join(
        (
            canon.pairs(()),
            canon.utf8_text(event_type),
            canon.u32(seq),
            canon.ascii_text("src:" + source),
            canon.i64(t_ns),
        )
    )
    chain_hash = None
    if chained:
        chain_prev = chain_prev or canon.hash_ref("chain", source.encode("ascii"))
        chain_hash = canon.hash_ref("chain", canon.parse_hash_ref(chain_prev) + payload)
    return CanonicalEvent(
        event_id=EventId.mint(payload),
        record_id=RecordId.mint(payload),
        source_id=SourceId.of(source),
        seq=seq,
        event_type=event_type,
        t_evt_ns=t_ns,
        t_ing_ns=t_ns,
        chain_hash=chain_hash,
        chain_prev=chain_prev if chained else None,
    )


def stream(source: str, count: int, start_ns: int, step_ns: int) -> tuple[CanonicalEvent, ...]:
    return tuple(make_event(source, i, start_ns + i * step_ns) for i in range(count))


ONE_PHASE = (calibrate.Phase("steady", EPOCH, EPOCH + 100000 * SECOND),)


# ---------------------------------------------------------------------------
# SCF-lite
# ---------------------------------------------------------------------------


class TestScf(unittest.TestCase):
    def test_sorted_keys_and_no_whitespace(self) -> None:
        self.assertEqual(calibrate.scf_dumps({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_exactly_one_trailing_lf(self) -> None:
        raw = calibrate.scf_bytes({"a": 1})
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertNotIn(b"\r", raw)

    def test_float_is_rejected(self) -> None:
        with self.assertRaises(CanonError) as caught:
            calibrate.scf_dumps({"a": 1 + 0.5})
        self.assertEqual(caught.exception.code, "E-CANON-FLOAT")

    def test_null_is_rejected(self) -> None:
        with self.assertRaises(CanonError) as caught:
            calibrate.scf_dumps({"a": None})
        self.assertEqual(caught.exception.code, "E-CANON-NULL")

    def test_integer_wider_than_u32_is_rejected(self) -> None:
        with self.assertRaises(CanonError) as caught:
            calibrate.scf_dumps({"a": calibrate.U32_MAX + 1})
        self.assertEqual(caught.exception.code, "E-CANON-WIDTH")

    def test_field_name_key_grammar_is_enforced(self) -> None:
        with self.assertRaises(CanonError):
            calibrate.scf_dumps({"Not_A_Field": 1})

    def test_the_two_declared_data_keyed_members_may_carry_data_keys(self) -> None:
        text = calibrate.scf_dumps(
            {"order_statistics": {"95/100": "7"}, "blind_volume_ns_by_reason": {"B_X": "3"}}
        )
        self.assertIn('"95/100":"7"', text)
        self.assertIn('"B_X":"3"', text)

    def test_loads_rejects_a_float_literal(self) -> None:
        with self.assertRaises(CanonError) as caught:
            calibrate.scf_loads('{"a":1.5}')
        self.assertEqual(caught.exception.code, "E-CANON-FLOAT")

    def test_it_agrees_with_the_shared_serialiser_wherever_both_accept(self) -> None:
        """The narrowing is the key grammar and nothing else; see the note in calibrate."""
        for value in (
            {"a": 1, "b": "x", "c": [1, 2], "d": {"e": True}},
            {"z": "0", "a": calibrate.U32_MAX},
            [],
        ):
            self.assertEqual(calibrate.scf_dumps(value), shared_scf.scf_dumps(value))
            self.assertEqual(calibrate.scf_bytes(value), shared_scf.scf_bytes(value))

    def test_loads_rejects_duplicate_keys(self) -> None:
        with self.assertRaises(CanonError) as caught:
            calibrate.scf_loads('{"a":1,"a":2}')
        self.assertEqual(caught.exception.code, "E-CANON-DUPKEY")


# ---------------------------------------------------------------------------
# The gap vector
# ---------------------------------------------------------------------------


class TestGapVectors(unittest.TestCase):
    def test_gaps_are_consecutive_differences_sorted_ascending(self) -> None:
        events = (
            make_event("s", 0, EPOCH),
            make_event("s", 1, EPOCH + 3 * SECOND),
            make_event("s", 2, EPOCH + 4 * SECOND),
        )
        vectors = calibrate.gap_vectors(events, ONE_PHASE, ())
        self.assertEqual(vectors, (("steady", (SECOND, 3 * SECOND)),))

    def test_zero_gaps_are_kept(self) -> None:
        events = (make_event("s", 0, EPOCH), make_event("s", 1, EPOCH))
        self.assertEqual(calibrate.gap_vectors(events, ONE_PHASE, ()), (("steady", (0,)),))

    def test_a_gap_straddling_a_phase_boundary_is_dropped(self) -> None:
        phases = (
            calibrate.Phase("a", EPOCH, EPOCH + 10 * SECOND),
            calibrate.Phase("b", EPOCH + 10 * SECOND, EPOCH + 20 * SECOND),
        )
        events = (
            make_event("s", 0, EPOCH),
            make_event("s", 1, EPOCH + 5 * SECOND),
            make_event("s", 2, EPOCH + 15 * SECOND),
            make_event("s", 3, EPOCH + 16 * SECOND),
        )
        vectors = calibrate.gap_vectors(events, phases, ())
        self.assertEqual(vectors, (("a", (5 * SECOND,)), ("b", (SECOND,))))

    def test_a_gap_meeting_an_excluded_interval_is_dropped(self) -> None:
        excluded = (
            calibrate.ExcludedInterval(EPOCH + 2 * SECOND, EPOCH + 3 * SECOND, "maintenance"),
        )
        events = (
            make_event("s", 0, EPOCH),
            make_event("s", 1, EPOCH + 5 * SECOND),
            make_event("s", 2, EPOCH + 6 * SECOND),
        )
        vectors = calibrate.gap_vectors(events, ONE_PHASE, excluded)
        self.assertEqual(vectors, (("steady", (SECOND,)),))

    def test_a_timestamp_outside_every_phase_produces_no_gap(self) -> None:
        phases = (calibrate.Phase("a", EPOCH + 100 * SECOND, EPOCH + 200 * SECOND),)
        events = (make_event("s", 0, EPOCH), make_event("s", 1, EPOCH + SECOND))
        self.assertEqual(calibrate.gap_vectors(events, phases, ()), ())

    def test_input_order_does_not_change_the_vector(self) -> None:
        events = stream("s", 20, EPOCH, SECOND)
        forward = calibrate.gap_vectors(events, ONE_PHASE, ())
        backward = calibrate.gap_vectors(tuple(reversed(events)), ONE_PHASE, ())
        self.assertEqual(forward, backward)


class TestQuantile(unittest.TestCase):
    def test_exact_rank_is_an_element_of_the_sample(self) -> None:
        gaps = tuple(range(1, 101))
        self.assertIn(calibrate.q_exact(gaps, 95, 100), gaps)
        self.assertEqual(calibrate.q_exact(gaps, 95, 100), 95)

    def test_the_lowest_and_highest_levels_clamp_into_range(self) -> None:
        gaps = (10, 20, 30)
        self.assertEqual(calibrate.q_exact(gaps, 0, 100), 10)
        self.assertEqual(calibrate.q_exact(gaps, 100, 100), 30)

    def test_an_empty_vector_is_an_error_rather_than_a_default(self) -> None:
        with self.assertRaises(ProfileError):
            calibrate.q_exact((), 95, 100)

    def test_parse_quantile_rejects_a_decimal_literal(self) -> None:
        for bad in ("0.95", "95", "95/0", "095/100", "101/100"):
            with self.assertRaises(CanonError, msg=bad):
                calibrate.parse_quantile(bad)


class TestGapDigest(unittest.TestCase):
    def test_the_digest_covers_every_gap_not_just_the_quantile(self) -> None:
        left = calibrate.gap_digest((1, 2, 3, 4))
        right = calibrate.gap_digest((1, 2, 3, 5))
        self.assertNotEqual(left, right)

    def test_the_digest_is_labelled_with_what_was_computed(self) -> None:
        self.assertTrue(calibrate.gap_digest((1,)).startswith("b2b256:"))
        self.assertNotIn("blake3", calibrate.gap_digest((1,)))

    def test_a_descending_vector_is_rejected(self) -> None:
        with self.assertRaises(CanonError):
            calibrate.gap_digest((5, 1))


# ---------------------------------------------------------------------------
# Seeds and the identity spec
# ---------------------------------------------------------------------------


class TestSeparation(unittest.TestCase):
    def test_the_two_seed_bands_are_disjoint(self) -> None:
        a_low, a_high = calibrate.ANALYSIS_SEED_BAND
        c_low, c_high = calibrate.CALIBRATION_SEED_BAND
        self.assertTrue(a_high < c_low or c_high < a_low)

    def test_an_analysis_seed_cannot_produce_a_profile(self) -> None:
        with self.assertRaises(ProfileError) as caught:
            calibrate.check_calibration_seed(12345)
        self.assertEqual(caught.exception.code, "PROFILE_SEED_OVERLAP")

    def test_the_identity_spec_hash_is_stable_and_honestly_labelled(self) -> None:
        self.assertEqual(calibrate.IDENTITY_SPEC_HASH, calibrate.identity_spec_hash())
        self.assertTrue(calibrate.IDENTITY_SPEC_HASH.startswith("b2b256:"))


# ---------------------------------------------------------------------------
# The profile artifact
# ---------------------------------------------------------------------------


def build_reference_profile(**overrides: object) -> calibrate.SourceProfile:
    kwargs: dict[str, object] = {
        "scenario_family": "vs-01-token-pivot",
        "events_by_source": (
            (SourceId.of("iam_audit"), IntegrityClass.CHAINED, stream("iam_audit", 200, EPOCH, SECOND)),
            (SourceId.of("edr_host"), IntegrityClass.NONE, ()),
        ),
        "phases": ONE_PHASE,
        "excluded": (),
        "quantile_levels": ("95/100",),
        "generator_config_hash": canon.hash_ref("gencfg", b"vs-01"),
        "reference_bundle_hash": canon.hash_ref("bundle", b"calibration-bundle"),
        "reference_run_manifest_hash": canon.hash_ref("manifest", b"calibration-manifest"),
        "calibration_seed": 1000000,
    }
    kwargs.update(overrides)
    return calibrate.build_profile(**kwargs)  # type: ignore[arg-type]


class TestProfile(unittest.TestCase):
    def test_order_statistic_keys_are_exactly_the_configured_levels(self) -> None:
        profile = build_reference_profile()
        regime = profile.source("iam_audit").regimes[0]
        self.assertEqual(tuple(level for level, _ in regime.order_statistics), ("95/100",))

    def test_a_source_that_emitted_nothing_is_still_declared(self) -> None:
        profile = build_reference_profile()
        edr = profile.source("edr_host")
        self.assertIsNotNone(edr)
        self.assertEqual(edr.regimes, ())

    def test_profile_id_recomputes_from_the_body(self) -> None:
        profile = build_reference_profile()
        obj = profile.to_scf()
        self.assertEqual(obj["profile_id"], profile.profile_id)
        body = dict(obj)
        del body["profile_id"]
        self.assertEqual(
            profile.profile_id, canon.hash_ref("prof", calibrate.scf_bytes(body, where="b"))
        )

    def test_the_degradation_spec_hash_is_the_identity_spec(self) -> None:
        self.assertEqual(
            build_reference_profile().degradation_spec_hash, calibrate.IDENTITY_SPEC_HASH
        )

    def test_write_then_load_round_trips_byte_for_byte(self) -> None:
        profile = build_reference_profile()
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "vs-01.json")
            written = calibrate.write_profile(profile, path)
            self.assertEqual(written, profile.profile_id)
            reloaded = calibrate.load_profile(path)
            self.assertEqual(reloaded.canonical_bytes(), profile.canonical_bytes())
            self.assertEqual(reloaded.profile_id, profile.profile_id)

    def test_a_tampered_order_statistic_fails_to_reload(self) -> None:
        profile = build_reference_profile()
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "vs-01.json")
            calibrate.write_profile(profile, path)
            text = pathlib.Path(path).read_text(encoding="utf-8")
            edited = text.replace('"95/100":"1000000000"', '"95/100":"9000000000"')
            self.assertNotEqual(edited, text)
            pathlib.Path(path).write_bytes(edited.encode("utf-8"))
            with self.assertRaises(ProfileError):
                calibrate.load_profile(path)

    def test_the_artifact_is_a_pure_function_of_its_inputs(self) -> None:
        events = stream("iam_audit", 200, EPOCH, SECOND)
        first = build_reference_profile(
            events_by_source=(
                (SourceId.of("iam_audit"), IntegrityClass.CHAINED, events),
                (SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            )
        )
        second = build_reference_profile(
            events_by_source=(
                (SourceId.of("edr_host"), IntegrityClass.NONE, ()),
                (SourceId.of("iam_audit"), IntegrityClass.CHAINED, tuple(reversed(events))),
            )
        )
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())

    def test_no_artifact_byte_claims_a_digest_that_was_not_computed(self) -> None:
        self.assertNotIn(b"blake3", build_reference_profile().canonical_bytes())

    def test_collapsing_regimes_is_recorded_in_the_artifact(self) -> None:
        phases = (
            calibrate.Phase("a", EPOCH, EPOCH + 100 * SECOND),
            calibrate.Phase("b", EPOCH + 100 * SECOND, EPOCH + 300 * SECOND),
        )
        profile = build_reference_profile(phases=phases, collapse_regimes=True)
        self.assertTrue(profile.regime_collapsed)
        self.assertEqual(
            tuple(r.regime_id for r in profile.source("iam_audit").regimes), ("collapsed",)
        )


class TestProfileValidation(unittest.TestCase):
    def test_a_regime_with_no_gaps_may_not_be_published(self) -> None:
        with self.assertRaises(Exception):
            calibrate.RegimeProfile(
                regime_id="steady",
                n_gaps=0,
                order_statistics=(("95/100", 1),),
                min_gap_ns=0,
                max_gap_ns=0,
                gap_digest=canon.hash_ref("gapv", b""),
            )

    def test_a_profile_hash_differs_from_a_profile_id(self) -> None:
        profile = build_reference_profile()
        self.assertNotEqual(calibrate.profile_hash(profile), profile.profile_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
