"""Unit tests for S7 liveness.

Run from the repository root:

    python python/spectra_vs/tests/test_liveness.py

What these pin: that LIVE has exactly one construction site and is unreachable except
through R11; that a threshold can only come from a profile or from a declared period;
that the six binding gates each reject; that a licence is never silently withheld; and
that permuting the envelope stage's queries leaves the artifact byte-identical.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import canon  # noqa: E402
from spectra_core.errors import CanonError, ProfileError, SchemaError  # noqa: E402
from spectra_core.ids import EventId, RecordId, SourceId  # noqa: E402
from spectra_core.model import (  # noqa: E402
    CanonicalEvent,
    IntegrityClass,
    Interval,
    LicenceBasis,
    Licence,
    LivenessVerdict,
)
from spectra_vs import calibrate, liveness  # noqa: E402

SECOND = 1000000000
EPOCH = 1700000000000000000
SPAN_END = EPOCH + 200 * SECOND
PHASES = (calibrate.Phase("steady", EPOCH, EPOCH + 100000 * SECOND),)

LIVENESS_TOML = _REPO_ROOT / "config" / "vs" / "liveness.toml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _payload(source: str, seq: int, t_ns: int, event_type: str) -> bytes:
    return b"".join(
        (
            canon.pairs(()),
            canon.utf8_text(event_type),
            canon.u32(seq),
            canon.ascii_text("src:" + source),
            canon.i64(t_ns),
        )
    )


def make_stream(
    source: str,
    entries: tuple[tuple[int, int], ...],
    integrity: IntegrityClass,
    break_link_at: int | None = None,
) -> tuple[CanonicalEvent, ...]:
    """Build a source's records from `(seq, t_ns)` pairs, threading the chain when linked."""
    events: list[CanonicalEvent] = []
    previous_hash: str | None = None
    for seq, t_ns in entries:
        payload = _payload(source, seq, t_ns, "idp.auth")
        chain_prev: str | None = None
        chain_hash: str | None = None
        if integrity is not IntegrityClass.NONE:
            chain_prev = previous_hash or canon.hash_ref("chain", source.encode("ascii"))
            if break_link_at is not None and seq == break_link_at:
                chain_prev = canon.hash_ref("chain", b"a link that was never emitted")
            chain_hash = canon.hash_ref("chain", canon.parse_hash_ref(chain_prev) + payload)
            previous_hash = chain_hash
        events.append(
            CanonicalEvent(
                event_id=EventId.mint(payload),
                record_id=RecordId.mint(payload),
                source_id=SourceId.of(source),
                seq=seq,
                event_type="idp.auth",
                t_evt_ns=t_ns,
                t_ing_ns=t_ns,
                chain_hash=chain_hash,
                chain_prev=chain_prev,
            )
        )
    return tuple(events)


def dense(source: str, count: int, start_ns: int, step_ns: int) -> tuple[tuple[int, int], ...]:
    return tuple((i, start_ns + i * step_ns) for i in range(count))


def config(m_min: int = 2) -> liveness.LivenessConfig:
    """A config identical to the shipped one except for m_min; see `test_shipped_config`."""
    return liveness.LivenessConfig(
        quantile_num=95,
        quantile_den=100,
        slack_num=3,
        slack_den=2,
        k_tail=5,
        n_floor=30,
        m_min=m_min,
        mcs_exact_cap=64,
    )


GENERATOR_CONFIG_HASH = canon.hash_ref("gencfg", b"vs-01-token-pivot")
CALIBRATION_BUNDLE_HASH = canon.hash_ref("bundle", b"the calibration run")
ANALYSIS_BUNDLE_HASH = canon.hash_ref("bundle", b"the run under analysis")


def reference_profile() -> calibrate.SourceProfile:
    """A profile with 199 one-second gaps on iam_audit, and edr_host declared but empty."""
    calibration = make_stream(
        "iam_audit", dense("iam_audit", 200, EPOCH, SECOND), IntegrityClass.CHAINED
    )
    return calibrate.build_profile(
        scenario_family="vs-01-token-pivot",
        events_by_source=(
            (SourceId.of("iam_audit"), IntegrityClass.CHAINED, calibration),
            (SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            (SourceId.of("gw_access"), IntegrityClass.SEQUENCED, calibration),
        ),
        phases=PHASES,
        excluded=(),
        quantile_levels=("95/100",),
        generator_config_hash=GENERATOR_CONFIG_HASH,
        reference_bundle_hash=CALIBRATION_BUNDLE_HASH,
        reference_run_manifest_hash=canon.hash_ref("manifest", b"calibration"),
        calibration_seed=1000007,
    )


def binding_context(**overrides: object) -> liveness.BindingContext:
    values: dict[str, object] = {
        "bundle_hash": ANALYSIS_BUNDLE_HASH,
        "seed": 4242,
        "generator_config_hash": GENERATOR_CONFIG_HASH,
        "scenario_family": "vs-01-token-pivot",
        "excluded_intervals_hash": calibrate.excluded_intervals_hash(()),
    }
    values.update(overrides)
    return liveness.BindingContext(**values)  # type: ignore[arg-type]


#: Twenty-one records one second apart, a sixty-second silence, then twenty more.
GAPPED = (
    dense("iam_audit", 21, EPOCH, SECOND)
    + tuple((21 + i, EPOCH + (80 + i) * SECOND) for i in range(20))
)


def build(
    *,
    sources: tuple[liveness.SourceInput, ...],
    m_min: int = 2,
    profile: calibrate.SourceProfile | None = None,
    no_profile: bool = False,
    allow_declared_profile: bool = False,
    query_endpoints: tuple[int, ...] = (),
    context: liveness.BindingContext | None = None,
) -> liveness.LivenessDocument:
    resolved = profile if (profile is not None or no_profile) else reference_profile()
    return liveness.build_liveness_document(
        config=config(m_min),
        sources=sources,
        phases=PHASES,
        scenario_t0_ns=EPOCH,
        scenario_t1_ns=SPAN_END,
        profile=resolved,
        binding_context=None if resolved is None else (context or binding_context()),
        query_endpoints=query_endpoints,
        no_profile=no_profile,
        allow_declared_profile=allow_declared_profile,
    )


def gapped_source() -> liveness.SourceInput:
    return liveness.SourceInput(
        source_id=SourceId.of("iam_audit"),
        integrity_class=IntegrityClass.CHAINED,
        events=make_stream("iam_audit", GAPPED, IntegrityClass.CHAINED),
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfig(unittest.TestCase):
    def test_shipped_config_parses(self) -> None:
        cfg = liveness.load_liveness_config(str(LIVENESS_TOML))
        self.assertEqual(cfg.schema, liveness.LIVENESS_CONFIG_SCHEMA)
        self.assertEqual(cfg.quantile, "95/100")
        self.assertEqual(cfg.slack, "3/2")
        self.assertEqual(cfg.n_min, 100)
        self.assertEqual(cfg.m_min, 3)
        self.assertEqual(cfg.mcs_exact_cap, 64)

    def test_a_decimal_literal_is_rejected_at_parse_time(self) -> None:
        text = LIVENESS_TOML.read_text(encoding="utf-8").replace(
            'quantile = "95/100"', "quantile = 0.95"
        )
        with self.assertRaises(CanonError) as caught:
            liveness.parse_liveness_config(text)
        self.assertEqual(caught.exception.code, "E-CANON-FLOAT")

    def test_a_quantile_of_one_is_rejected_because_q_minus_p_is_zero(self) -> None:
        with self.assertRaises(SchemaError):
            liveness.LivenessConfig(
                quantile_num=100, quantile_den=100, slack_num=3, slack_den=2,
                k_tail=5, n_floor=30, m_min=3, mcs_exact_cap=64,
            )

    def test_an_unknown_member_is_rejected(self) -> None:
        text = LIVENESS_TOML.read_text(encoding="utf-8") + "\nself_calibrate = true\n"
        with self.assertRaises(SchemaError) as caught:
            liveness.parse_liveness_config(text)
        self.assertEqual(caught.exception.code, "E-SCHEMA-UNKNOWN")

    def test_a_missing_member_is_rejected(self) -> None:
        text = LIVENESS_TOML.read_text(encoding="utf-8").replace("m_min = 3", "")
        with self.assertRaises(SchemaError) as caught:
            liveness.parse_liveness_config(text)
        self.assertEqual(caught.exception.code, "E-SCHEMA-MISSING")

    def test_n_min_is_the_tail_requirement_not_the_floor_at_95_over_100(self) -> None:
        self.assertEqual(config().n_min, 100)


# ---------------------------------------------------------------------------
# Binding gates B1..B6
# ---------------------------------------------------------------------------


class TestBindingGates(unittest.TestCase):
    def test_a_correctly_separated_profile_passes_every_gate(self) -> None:
        self.assertEqual(liveness.check_binding_gates(reference_profile(), binding_context()), ())

    def test_b1_rejects_a_profile_calibrated_on_the_bundle_under_analysis(self) -> None:
        failures = liveness.check_binding_gates(
            reference_profile(), binding_context(bundle_hash=CALIBRATION_BUNDLE_HASH)
        )
        self.assertEqual([f.code for f in failures], ["PROFILE_SELF_CALIBRATED"])

    def test_b2_rejects_a_profile_from_a_degraded_run(self) -> None:
        degraded = dataclasses.replace(
            reference_profile(), degradation_spec_hash=canon.hash_ref("degspec", b"delete 30%")
        )
        failures = liveness.check_binding_gates(degraded, binding_context())
        self.assertEqual([f.code for f in failures], ["PROFILE_FROM_DEGRADED_RUN"])

    def test_b3_rejects_a_run_seed_inside_the_calibration_band(self) -> None:
        failures = liveness.check_binding_gates(reference_profile(), binding_context(seed=1000007))
        self.assertEqual([f.code for f in failures], ["PROFILE_SEED_OVERLAP"])

    def test_b4_rejects_a_different_generator_config(self) -> None:
        failures = liveness.check_binding_gates(
            reference_profile(),
            binding_context(generator_config_hash=canon.hash_ref("gencfg", b"other")),
        )
        self.assertEqual([f.code for f in failures], ["PROFILE_CONFIG_MISMATCH"])

    def test_b5_rejects_a_different_scenario_family(self) -> None:
        failures = liveness.check_binding_gates(
            reference_profile(), binding_context(scenario_family="vs-02-other")
        )
        self.assertEqual([f.code for f in failures], ["PROFILE_FAMILY_MISMATCH"])

    def test_b6_rejects_different_excluded_intervals(self) -> None:
        other = calibrate.excluded_intervals_hash(
            (calibrate.ExcludedInterval(EPOCH, EPOCH + SECOND, "maintenance"),)
        )
        failures = liveness.check_binding_gates(
            reference_profile(), binding_context(excluded_intervals_hash=other)
        )
        self.assertEqual([f.code for f in failures], ["PROFILE_INTERVALS_MISMATCH"])

    def test_the_run_aborts_rather_than_degrading_to_blind(self) -> None:
        with self.assertRaises(ProfileError) as caught:
            liveness.require_binding_gates(
                reference_profile(), binding_context(bundle_hash=CALIBRATION_BUNDLE_HASH)
            )
        self.assertEqual(caught.exception.code, "PROFILE_SELF_CALIBRATED")

    def test_building_a_document_runs_the_gates(self) -> None:
        with self.assertRaises(ProfileError):
            build(
                sources=(gapped_source(),),
                context=binding_context(bundle_hash=CALIBRATION_BUNDLE_HASH),
            )


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


class TestThreshold(unittest.TestCase):
    def test_slack_is_an_integer_ceiling(self) -> None:
        self.assertEqual(liveness.threshold_from_order_statistic(1000000000, 3, 2), (1500000000, False))
        self.assertEqual(liveness.threshold_from_order_statistic(1, 3, 2), (2, False))

    def test_saturation_is_reported_rather_than_clamped_silently(self) -> None:
        value, saturated = liveness.threshold_from_order_statistic(liveness.U64_MAX, 3, 2)
        self.assertEqual(value, liveness.U64_MAX)
        self.assertTrue(saturated)

    def test_provenance_has_no_run_derived_variant(self) -> None:
        with self.assertRaises(SchemaError):
            liveness.ThresholdProvenance(kind="self", regime="steady", slack="3/2")


# ---------------------------------------------------------------------------
# The grid
# ---------------------------------------------------------------------------


class TestBreakpoints(unittest.TestCase):
    def test_the_grid_is_a_sorted_unique_clipped_union(self) -> None:
        grid = liveness.breakpoints(
            (EPOCH + 5, EPOCH + 5, EPOCH + 1),
            (EPOCH + 3,),
            (EPOCH + 2, SPAN_END + 10 * SECOND),
            EPOCH,
            EPOCH + 6,
        )
        self.assertEqual(grid, (EPOCH, EPOCH + 1, EPOCH + 2, EPOCH + 3, EPOCH + 5, EPOCH + 6))

    def test_permuting_query_order_leaves_the_artifact_byte_identical(self) -> None:
        endpoints = (EPOCH + 30 * SECOND, EPOCH + 90 * SECOND, EPOCH + 150 * SECOND)
        first = build(sources=(gapped_source(),), query_endpoints=endpoints)
        second = build(
            sources=(gapped_source(),),
            query_endpoints=(endpoints[2], endpoints[0], endpoints[1], endpoints[0]),
        )
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def observation(**overrides: object) -> liveness.WindowObservation:
    values: dict[str, object] = {
        "regime": "steady",
        "left_bracket_t_ns": EPOCH,
        "right_bracket_t_ns": EPOCH + SECOND,
        "n_records_in_span": 3,
        "max_observed_gap_ns": SECOND,
        "chain": liveness.ChainState(liveness.ChainStatus.VERIFIED),
    }
    values.update(overrides)
    return liveness.WindowObservation(**values)  # type: ignore[arg-type]


class TestClassification(unittest.TestCase):
    def call(self, obs: liveness.WindowObservation, **kwargs: object) -> liveness._Outcome:
        values: dict[str, object] = {
            "mode": liveness.LivenessMode.F0_CALIBRATED,
            "threshold_ns": 2 * SECOND,
            "saturated": False,
            "integrity_class": IntegrityClass.CHAINED,
            "m_min": 2,
        }
        values.update(kwargs)
        return liveness.classify(obs, **values)  # type: ignore[arg-type]

    def test_r1_no_profile_mode(self) -> None:
        out = self.call(observation(), mode=liveness.LivenessMode.F2_NO_PROFILE)
        self.assertEqual((out.verdict, out.reason), (LivenessVerdict.BLIND, liveness.Reason.B_FORCED_NO_PROFILE_MODE))

    def test_r2_regime_unknown(self) -> None:
        out = self.call(observation(regime=None))
        self.assertEqual(out.reason, liveness.Reason.B_REGIME_UNKNOWN)

    def test_r3_profile_insufficient(self) -> None:
        out = self.call(observation(), threshold_ns=None, mode=liveness.LivenessMode.F1_INSUFFICIENT)
        self.assertEqual(out.reason, liveness.Reason.B_PROFILE_INSUFFICIENT)

    def test_r4_threshold_overflow(self) -> None:
        out = self.call(observation(), saturated=True)
        self.assertEqual(out.reason, liveness.Reason.B_THRESHOLD_OVERFLOW)

    def test_r5_chain_unverified(self) -> None:
        out = self.call(
            observation(chain=liveness.ChainState(liveness.ChainStatus.UNVERIFIED, first_bad="ev:" + "0" * 32))
        )
        self.assertEqual(out.reason, liveness.Reason.B_CHAIN_UNVERIFIED)

    def test_r6_chained_seq_gap_is_suppressed(self) -> None:
        witness = canon.sorted_unique(("ev:" + "1" * 32, "ev:" + "2" * 32))
        out = self.call(
            observation(
                chain=liveness.ChainState(
                    liveness.ChainStatus.VERIFIED, missing_seq=(1, 3), witness=witness
                )
            )
        )
        self.assertEqual((out.verdict, out.reason), (LivenessVerdict.SUPPRESSED, liveness.Reason.S_CHAIN_SEQ_GAP))
        self.assertEqual(out.missing_seq, (1, 3))
        self.assertEqual(out.witness, witness)

    def test_r7_sequenced_seq_gap_is_unauthenticated(self) -> None:
        witness = canon.sorted_unique(("ev:" + "1" * 32, "ev:" + "2" * 32))
        out = self.call(
            observation(
                chain=liveness.ChainState(
                    liveness.ChainStatus.VERIFIED, missing_seq=(1, 3), witness=witness
                )
            ),
            integrity_class=IntegrityClass.SEQUENCED,
        )
        self.assertEqual(out.reason, liveness.Reason.S_SEQ_GAP_UNAUTHENTICATED)

    def test_r8_unbracketed(self) -> None:
        out = self.call(observation(left_bracket_t_ns=None, n_records_in_span=0))
        self.assertEqual(out.reason, liveness.Reason.B_UNBRACKETED)

    def test_r9_window_undersampled(self) -> None:
        out = self.call(observation(n_records_in_span=1))
        self.assertEqual(out.reason, liveness.Reason.B_WINDOW_UNDERSAMPLED)

    def test_r10_gap_exceeds_threshold(self) -> None:
        out = self.call(observation(max_observed_gap_ns=3 * SECOND))
        self.assertEqual(out.reason, liveness.Reason.B_GAP_EXCEEDS_THRESHOLD)

    def test_r10_is_strictly_greater_so_a_gap_equal_to_the_threshold_is_live(self) -> None:
        out = self.call(observation(max_observed_gap_ns=2 * SECOND))
        self.assertEqual(out.verdict, LivenessVerdict.LIVE)

    def test_r11_is_the_only_live(self) -> None:
        out = self.call(observation())
        self.assertEqual((out.verdict, out.reason), (LivenessVerdict.LIVE, liveness.Reason.L_CALIBRATED_OK))

    def test_the_source_has_exactly_one_live_construction_site(self) -> None:
        """A structural gate: adding a second place that mints LIVE turns this red."""
        source = (
            _REPO_ROOT / "python" / "spectra_vs" / "src" / "spectra_vs" / "liveness.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count("_Outcome(LivenessVerdict.LIVE"), 1)

    def test_an_internal_failure_becomes_blind_rather_than_reaching_the_caller(self) -> None:
        broken = observation(n_records_in_span="not an integer")
        out = liveness._classify_guarded(
            broken, liveness.LivenessMode.F0_CALIBRATED, 2 * SECOND, False, IntegrityClass.CHAINED, 2
        )
        self.assertEqual((out.verdict, out.reason), (LivenessVerdict.BLIND, liveness.Reason.B_INTERNAL_ERROR))
        self.assertIn(liveness.Reason.B_INTERNAL_ERROR, liveness.CALIBRATION_DEFICIENCY_REASONS)


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


class TestDocument(unittest.TestCase):
    def test_a_gap_beyond_the_calibrated_threshold_is_blind(self) -> None:
        doc = build(sources=(gapped_source(),))
        entry = doc.source("iam_audit")
        self.assertEqual(entry.mode, liveness.LivenessMode.F0_CALIBRATED)
        self.assertEqual(entry.threshold_ns, 1500000000)
        reasons = {i.reason for i in entry.intervals}
        self.assertIn(liveness.Reason.B_GAP_EXCEEDS_THRESHOLD, reasons)
        self.assertIn(liveness.Reason.L_CALIBRATED_OK, reasons)
        self.assertIn(liveness.Reason.B_UNBRACKETED, reasons)

    def test_the_blind_window_covers_the_silence_and_nothing_else(self) -> None:
        doc = build(sources=(gapped_source(),))
        blind = [
            i
            for i in doc.source("iam_audit").intervals
            if i.reason is liveness.Reason.B_GAP_EXCEEDS_THRESHOLD
        ]
        self.assertEqual(len(blind), 1)
        self.assertEqual(blind[0].t0_ns, EPOCH + 20 * SECOND)
        self.assertEqual(blind[0].t1_ns, EPOCH + 80 * SECOND)
        self.assertEqual(blind[0].duration_ns, 60 * SECOND)

    def test_intervals_are_contiguous_and_cover_the_scenario_span(self) -> None:
        intervals = build(sources=(gapped_source(),)).source("iam_audit").intervals
        self.assertEqual(intervals[0].t0_ns, EPOCH)
        self.assertEqual(intervals[-1].t1_ns, SPAN_END)
        for left, right in zip(intervals, intervals[1:]):
            self.assertEqual(left.t1_ns, right.t0_ns)

    def test_blind_volume_is_partitioned_by_reason_not_summarised(self) -> None:
        entry = build(sources=(gapped_source(),)).source("iam_audit")
        by_reason = dict(entry.blind_volume_ns_by_reason)
        self.assertEqual(by_reason[liveness.Reason.B_GAP_EXCEEDS_THRESHOLD], 60 * SECOND)
        self.assertGreater(by_reason[liveness.Reason.B_UNBRACKETED], 0)
        self.assertEqual(entry.suppressed_volume_ns, 0)

    def test_a_declared_source_that_never_emits_is_blind_everywhere(self) -> None:
        doc = build(
            sources=(
                liveness.SourceInput(SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            )
        )
        entry = doc.source("edr_host")
        self.assertEqual(entry.mode, liveness.LivenessMode.F1_INSUFFICIENT)
        self.assertIsNone(entry.threshold_ns)
        self.assertEqual(
            [i.reason for i in entry.intervals], [liveness.Reason.B_PROFILE_INSUFFICIENT]
        )
        self.assertTrue(doc.flags.liveness_uncalibrated)

    def test_no_profile_mode_blinds_everything_and_says_so(self) -> None:
        doc = build(sources=(gapped_source(),), no_profile=True)
        entry = doc.source("iam_audit")
        self.assertEqual(doc.mode_global, liveness.LivenessMode.F2_NO_PROFILE)
        self.assertIsNone(doc.profile_id)
        self.assertTrue(doc.flags.blind_by_default)
        self.assertEqual(
            [i.reason for i in entry.intervals], [liveness.Reason.B_FORCED_NO_PROFILE_MODE]
        )

    def test_neither_a_profile_nor_no_profile_is_an_error(self) -> None:
        with self.assertRaises(ProfileError):
            liveness.build_liveness_document(
                config=config(), sources=(), phases=PHASES,
                scenario_t0_ns=EPOCH, scenario_t1_ns=SPAN_END,
            )

    def test_both_a_profile_and_no_profile_is_an_error(self) -> None:
        with self.assertRaises(ProfileError):
            liveness.build_liveness_document(
                config=config(), sources=(), phases=PHASES,
                scenario_t0_ns=EPOCH, scenario_t1_ns=SPAN_END,
                profile=reference_profile(), binding_context=binding_context(), no_profile=True,
            )

    def test_a_declared_period_is_only_used_when_it_was_explicitly_allowed(self) -> None:
        source = liveness.SourceInput(
            SourceId.of("edr_host"), IntegrityClass.NONE, (), nominal_period_ns=5 * SECOND
        )
        without = build(sources=(source,))
        self.assertEqual(without.source("edr_host").mode, liveness.LivenessMode.F1_INSUFFICIENT)
        with_declared = build(sources=(source,), allow_declared_profile=True)
        entry = with_declared.source("edr_host")
        self.assertEqual(entry.mode, liveness.LivenessMode.F3_DECLARED)
        self.assertEqual(entry.threshold_ns, 7500000000)
        self.assertEqual(entry.threshold_provenance.kind, "declared")
        self.assertIsNone(entry.threshold_provenance.profile_id)
        self.assertTrue(with_declared.flags.liveness_uncalibrated)

    def test_a_chained_seq_gap_is_suppressed_with_its_witness(self) -> None:
        entries = ((0, EPOCH), (1, EPOCH + SECOND), (3, EPOCH + 2 * SECOND), (4, EPOCH + 3 * SECOND))
        doc = build(
            sources=(
                liveness.SourceInput(
                    SourceId.of("iam_audit"),
                    IntegrityClass.CHAINED,
                    make_stream("iam_audit", entries, IntegrityClass.CHAINED),
                ),
            )
        )
        suppressed = [
            i for i in doc.source("iam_audit").intervals if i.verdict is LivenessVerdict.SUPPRESSED
        ]
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0].reason, liveness.Reason.S_CHAIN_SEQ_GAP)
        self.assertEqual(suppressed[0].missing_seq, (1, 3))
        self.assertEqual(len(suppressed[0].witness), 2)
        self.assertGreater(doc.source("iam_audit").suppressed_volume_ns, 0)

    def test_a_sequenced_seq_gap_sets_the_unauthenticated_flag(self) -> None:
        entries = ((0, EPOCH), (1, EPOCH + SECOND), (3, EPOCH + 2 * SECOND), (4, EPOCH + 3 * SECOND))
        doc = build(
            sources=(
                liveness.SourceInput(
                    SourceId.of("gw_access"),
                    IntegrityClass.SEQUENCED,
                    make_stream("gw_access", entries, IntegrityClass.SEQUENCED),
                ),
            )
        )
        self.assertTrue(doc.flags.liveness_unauthenticated)

    def test_a_broken_chain_link_is_blind_not_suppressed(self) -> None:
        entries = dense("iam_audit", 6, EPOCH, SECOND)
        doc = build(
            sources=(
                liveness.SourceInput(
                    SourceId.of("iam_audit"),
                    IntegrityClass.CHAINED,
                    make_stream("iam_audit", entries, IntegrityClass.CHAINED, break_link_at=3),
                ),
            )
        )
        reasons = {i.reason for i in doc.source("iam_audit").intervals}
        self.assertIn(liveness.Reason.B_CHAIN_UNVERIFIED, reasons)
        self.assertNotIn(LivenessVerdict.SUPPRESSED, {i.verdict for i in doc.source("iam_audit").intervals})

    def test_the_fail_closed_chain_verifier_blinds_every_linked_span(self) -> None:
        doc = liveness.build_liveness_document(
            config=config(),
            sources=(gapped_source(),),
            phases=PHASES,
            scenario_t0_ns=EPOCH,
            scenario_t1_ns=SPAN_END,
            profile=reference_profile(),
            binding_context=binding_context(),
            chain_verifier=liveness.chain_always_unverified,
        )
        self.assertNotIn(
            LivenessVerdict.LIVE, {i.verdict for i in doc.source("iam_audit").intervals}
        )

    def test_the_artifact_is_canonical(self) -> None:
        raw = build(sources=(gapped_source(),)).canonical_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        self.assertNotIn(b"\r", raw)
        self.assertNotIn(b"blake3", raw)
        self.assertNotIn(b"null", raw)

    def test_the_artifact_is_a_pure_function_of_its_inputs(self) -> None:
        self.assertEqual(
            build(sources=(gapped_source(),)).canonical_bytes(),
            build(sources=(gapped_source(),)).canonical_bytes(),
        )

    def test_liveness_hash_is_over_the_artifact_bytes(self) -> None:
        doc = build(sources=(gapped_source(),))
        self.assertEqual(
            liveness.liveness_hash(doc), canon.hash_ref("live", doc.canonical_bytes())
        )

    def test_tamper_suspected_cannot_be_set_in_this_slice(self) -> None:
        self.assertFalse(liveness.TAMPER_PASS_IMPLEMENTED)
        doc = build(sources=(gapped_source(),))
        self.assertFalse(doc.flags.verdict_tamper_sensitive)
        with self.assertRaises(SchemaError):
            dataclasses.replace(doc.source("iam_audit"), tamper_suspected=True)


class TestSelfCalibrationTrapIsClosed(unittest.TestCase):
    def test_deleting_records_widens_the_blind_window_instead_of_the_threshold(self) -> None:
        """The whole point: degradation must not move the threshold it is measured against."""
        clean = build(sources=(gapped_source(),))
        degraded_entries = tuple(e for e in GAPPED if not 5 <= e[0] <= 15)
        degraded = build(
            sources=(
                liveness.SourceInput(
                    SourceId.of("iam_audit"),
                    IntegrityClass.CHAINED,
                    make_stream("iam_audit", degraded_entries, IntegrityClass.CHAINED),
                ),
            )
        )
        self.assertEqual(
            clean.source("iam_audit").threshold_ns, degraded.source("iam_audit").threshold_ns
        )

        def non_live_ns(document: liveness.LivenessDocument) -> int:
            entry = document.source("iam_audit")
            return (
                sum(v for _, v in entry.blind_volume_ns_by_reason) + entry.suppressed_volume_ns
            )

        self.assertGreater(non_live_ns(degraded), non_live_ns(clean))


class TestMinimumSampleIsFailClosed(unittest.TestCase):
    def test_below_n_min_the_verdict_is_blind_and_not_live(self) -> None:
        short = calibrate.build_profile(
            scenario_family="vs-01-token-pivot",
            events_by_source=(
                (
                    SourceId.of("iam_audit"),
                    IntegrityClass.CHAINED,
                    make_stream("iam_audit", dense("iam_audit", 40, EPOCH, SECOND), IntegrityClass.CHAINED),
                ),
            ),
            phases=PHASES,
            excluded=(),
            quantile_levels=("95/100",),
            generator_config_hash=GENERATOR_CONFIG_HASH,
            reference_bundle_hash=CALIBRATION_BUNDLE_HASH,
            reference_run_manifest_hash=canon.hash_ref("manifest", b"calibration"),
            calibration_seed=1000007,
        )
        self.assertEqual(short.source("iam_audit").regimes[0].n_gaps, 39)
        doc = build(sources=(gapped_source(),), profile=short)
        entry = doc.source("iam_audit")
        self.assertEqual(entry.mode, liveness.LivenessMode.F1_INSUFFICIENT)
        self.assertNotIn(LivenessVerdict.LIVE, {i.verdict for i in entry.intervals})
        self.assertTrue(doc.flags.liveness_uncalibrated)

    def test_the_shipped_m_min_makes_every_elementary_interval_undersampled(self) -> None:
        """A pinned contradiction, not an aspiration; see the header of liveness.toml.

        The grid places a breakpoint at every record time, so an elementary interval
        brackets two records. The shipped m_min of three therefore fires R9 everywhere
        and no window can reach R11. This test exists so that resolving the
        contradiction in the specification turns a named test red rather than changing
        a demo silently.
        """
        doc = build(sources=(gapped_source(),), m_min=3)
        entry = doc.source("iam_audit")
        self.assertNotIn(LivenessVerdict.LIVE, {i.verdict for i in entry.intervals})
        self.assertIn(
            liveness.Reason.B_WINDOW_UNDERSAMPLED, {i.reason for i in entry.intervals}
        )


# ---------------------------------------------------------------------------
# Licences
# ---------------------------------------------------------------------------


class TestLicences(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = build(sources=(gapped_source(),))
        self.blind = Interval(EPOCH + 30 * SECOND, EPOCH + 60 * SECOND)
        self.live_span = Interval(EPOCH + 2 * SECOND, EPOCH + 5 * SECOND)

    def test_live_is_true_only_when_every_contained_interval_is_live(self) -> None:
        self.assertTrue(liveness.live(self.doc, "iam_audit", self.live_span))
        self.assertFalse(liveness.live(self.doc, "iam_audit", self.blind))

    def test_an_interval_outside_the_grid_is_not_live(self) -> None:
        self.assertFalse(
            liveness.live(self.doc, "iam_audit", Interval(EPOCH - SECOND, EPOCH + SECOND))
        )

    def test_a_blind_licence_carries_a_reason_and_no_witness(self) -> None:
        licences = liveness.licences_for(self.doc, "iam_audit", self.blind)
        self.assertEqual(len(licences), 1)
        licence = licences[0]
        self.assertEqual(licence.basis, LicenceBasis.BLIND)
        self.assertEqual(licence.reason, str(liveness.Reason.B_GAP_EXCEEDS_THRESHOLD))
        self.assertEqual(licence.witness, ())
        self.assertTrue(licence.verify_id())

    def test_a_licence_over_live_time_is_refused_loudly(self) -> None:
        with self.assertRaises(liveness.LicenceError):
            liveness.licences_for(self.doc, "iam_audit", self.live_span)

    def test_a_suppressed_licence_carries_its_bracketing_witness(self) -> None:
        entries = ((0, EPOCH), (1, EPOCH + SECOND), (3, EPOCH + 2 * SECOND), (4, EPOCH + 3 * SECOND))
        doc = build(
            sources=(
                liveness.SourceInput(
                    SourceId.of("iam_audit"),
                    IntegrityClass.CHAINED,
                    make_stream("iam_audit", entries, IntegrityClass.CHAINED),
                ),
            )
        )
        window = [
            i for i in doc.source("iam_audit").intervals if i.verdict is LivenessVerdict.SUPPRESSED
        ][0]
        licences = liveness.licences_for(doc, "iam_audit", window.interval)
        self.assertEqual(licences[0].basis, LicenceBasis.SUPPRESSED)
        self.assertEqual(len(licences[0].witness), 2)

    def test_the_condition_needs_every_producing_source_non_live(self) -> None:
        doc = build(
            sources=(
                gapped_source(),
                liveness.SourceInput(SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            )
        )
        self.assertTrue(liveness.licence_condition(doc, ("iam_audit", "edr_host"), self.blind))
        self.assertFalse(
            liveness.licence_condition(doc, ("iam_audit", "edr_host"), self.live_span)
        )

    def test_issue_refuses_and_names_the_live_source(self) -> None:
        issue = liveness.issue_licences(self.doc, ("iam_audit",), self.live_span)
        self.assertFalse(issue.granted)
        self.assertEqual(issue.blocked_sources, ("iam_audit",))
        self.assertEqual(issue.licences, ())

    def test_issue_grants_one_licence_per_producing_source(self) -> None:
        doc = build(
            sources=(
                gapped_source(),
                liveness.SourceInput(SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            )
        )
        issue = liveness.issue_licences(doc, ("iam_audit", "edr_host"), self.blind)
        self.assertTrue(issue.granted)
        self.assertEqual({lic.source_id.snake for lic in issue.licences}, {"edr_host", "iam_audit"})
        self.assertFalse(issue.license_voided_by_suspected_tampering)

    def test_voiding_a_licence_raises_a_flag_and_refuses_the_instance(self) -> None:
        granted = liveness.issue_licences(self.doc, ("iam_audit",), self.blind)
        target = str(granted.licences[0].license_id)
        voided = liveness.issue_licences(
            self.doc, ("iam_audit",), self.blind, voided_license_ids=(target,)
        )
        self.assertFalse(voided.granted)
        self.assertTrue(voided.license_voided_by_suspected_tampering)
        self.assertEqual([v.license_id for v in voided.voided], [target])
        self.assertEqual(voided.licences, ())

    def test_maximal_non_live_runs_merge_across_reasons(self) -> None:
        runs = liveness.maximal_non_live_runs(self.doc, "iam_audit")
        self.assertIn(Interval(EPOCH + 20 * SECOND, EPOCH + 80 * SECOND), runs)

    def test_licence_ids_are_content_addressed_and_stable(self) -> None:
        first = liveness.licences_for(self.doc, "iam_audit", self.blind)
        second = liveness.licences_for(build(sources=(gapped_source(),)), "iam_audit", self.blind)
        self.assertEqual(
            [str(a.license_id) for a in first], [str(b.license_id) for b in second]
        )


class TestAbsence(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = build(
            sources=(
                gapped_source(),
                liveness.SourceInput(SourceId.of("edr_host"), IntegrityClass.NONE, ()),
            )
        )

    def test_all_live_is_observed(self) -> None:
        self.assertEqual(
            liveness.absence_status(self.doc, ("iam_audit",), Interval(EPOCH + 2 * SECOND, EPOCH + 5 * SECOND)),
            liveness.AbsenceStatus.OBSERVED,
        )

    def test_none_live_is_licensed(self) -> None:
        self.assertEqual(
            liveness.absence_status(
                self.doc, ("iam_audit", "edr_host"), Interval(EPOCH + 30 * SECOND, EPOCH + 60 * SECOND)
            ),
            liveness.AbsenceStatus.LICENSED,
        )

    def test_a_mixture_is_undetermined(self) -> None:
        self.assertEqual(
            liveness.absence_status(
                self.doc, ("iam_audit", "edr_host"), Interval(EPOCH + 2 * SECOND, EPOCH + 5 * SECOND)
            ),
            liveness.AbsenceStatus.UNDETERMINED,
        )


class TestCalibrationDeficiency(unittest.TestCase):
    def licence(self, reason: liveness.Reason, span_ns: int) -> Licence:
        return Licence.mint(
            source_id=SourceId.of("iam_audit"),
            interval=Interval(EPOCH, EPOCH + span_ns),
            basis=LicenceBasis.BLIND,
            reason=str(reason),
        )

    def test_a_purely_observed_gap_licence_is_zero_over_one(self) -> None:
        self.assertEqual(
            liveness.calibration_deficiency((self.licence(liveness.Reason.B_GAP_EXCEEDS_THRESHOLD, 10),)),
            (0, 1),
        )

    def test_a_purely_uncalibrated_licence_is_one_over_one(self) -> None:
        self.assertEqual(
            liveness.calibration_deficiency((self.licence(liveness.Reason.B_PROFILE_INSUFFICIENT, 10),)),
            (1, 1),
        )

    def test_a_mixture_is_an_exact_rational_in_lowest_terms(self) -> None:
        licences = (
            self.licence(liveness.Reason.B_PROFILE_INSUFFICIENT, 4),
            self.licence(liveness.Reason.B_GAP_EXCEEDS_THRESHOLD, 8),
        )
        self.assertEqual(liveness.calibration_deficiency(licences), (1, 3))

    def test_the_two_reason_partitions_do_not_overlap(self) -> None:
        self.assertEqual(
            liveness.CALIBRATION_DEFICIENCY_REASONS & liveness.OBSERVED_GAP_REASONS, frozenset()
        )


class TestNoTamperToken(unittest.TestCase):
    def test_a_consumer_cannot_mint_the_token(self) -> None:
        with self.assertRaises(SchemaError):
            liveness.NoTamperToken(object())

    def test_the_stage_mints_it_because_nothing_is_ever_tamper_suspected(self) -> None:
        self.assertIsNotNone(liveness.no_tamper_token(build(sources=(gapped_source(),))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
