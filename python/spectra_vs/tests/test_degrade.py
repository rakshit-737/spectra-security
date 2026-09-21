"""Unit tests for S3, the degradation operator.

Run from the repository root:

    python python/spectra_vs/tests/test_degrade.py

What these tests are for. NESTING is the property the whole completeness axis rests on:
if the 70% cell did not see a subset of what the 90% cell saw, the two cells differ by
"different telemetry" as well as by "less telemetry", and no conclusion drawn from their
difference means anything. It is checked here over a whole ladder of levels and in both
directions, not just at the two cells the slice actually runs, because a construction
that happens to nest at two points is not a construction that nests.

DELETE-ONLY is the other property. Every surviving record must be octet-identical to the
record the generator emitted, including its sequence number: renumbering survivors to
close the gaps would destroy the very evidence the liveness stage reads a gap from.

The synthetic fixture spans several outage blocks deliberately. `OUTAGE_BLOCK_SPAN_NS` is
a constant rather than an argument, so a test that wanted smaller blocks would have to
change what the operator is; the fixture uses real nanosecond spans instead.
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
from spectra_core.errors import SchemaError  # noqa: E402
from spectra_core.ids import SourceId  # noqa: E402

from spectra_vs import degrade as dg  # noqa: E402
from spectra_vs import gen  # noqa: E402
from spectra_vs import scenario as scn  # noqa: E402
from spectra_vs import scf  # noqa: E402

DSEED = 918273645

#: Three sources over eight outage blocks, so that block-level deletion has somewhere to
#: land and per-source stratification has more than one stratum to keep separate.
_SOURCES = ("gw_access", "iam_audit", "res_access")
_PER_SOURCE = 400
_EPOCH = 1_707_004_800_000_000_000
_SPAN = dg.OUTAGE_BLOCK_SPAN_NS * 8


def _fixture() -> tuple[gen.RawEvent, ...]:
    records: list[gen.RawEvent] = []
    for name in _SOURCES:
        for seq in range(_PER_SOURCE):
            records.append(
                gen.RawEvent(
                    source_id=SourceId.of(name),
                    seq=seq,
                    t_evt_ns=_EPOCH + (seq * _SPAN) // _PER_SOURCE,
                    event_type=f"{name}_tick",
                    attrs=(("principal", f"p_{seq % 4}"),),
                )
            )
    return tuple(sorted(records, key=lambda r: r.sort_key()))


RAW = _fixture()


class TestCompleteness(unittest.TestCase):
    def test_reduces_to_lowest_terms(self) -> None:
        value = dg.Completeness.percent(70)
        self.assertEqual((value.num, value.den), (7, 10))

    def test_unreduced_is_rejected_on_direct_construction(self) -> None:
        with self.assertRaises(SchemaError):
            dg.Completeness(num=70, den=100)

    def test_above_one_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            dg.Completeness.of(3, 2)

    def test_zero_denominator_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            dg.Completeness.of(1, 0)

    def test_identity_is_recognised(self) -> None:
        self.assertTrue(dg.Completeness.percent(100).is_identity)
        self.assertFalse(dg.Completeness.percent(99).is_identity)

    def test_keep_floors(self) -> None:
        self.assertEqual(dg.Completeness.percent(70).keep(401), 280)

    def test_tag_is_integer_percent(self) -> None:
        self.assertEqual(dg.Completeness.percent(100).tag(), "100")
        self.assertEqual(dg.Completeness.percent(70).tag(), "70")
        self.assertEqual(dg.Completeness.of(1, 3).tag(), "1_3")

    def test_ordering_is_exact(self) -> None:
        self.assertTrue(dg.Completeness.of(7, 10) < dg.Completeness.of(9, 10))
        self.assertFalse(dg.Completeness.of(9, 10) < dg.Completeness.of(7, 10))


class TestDeleteOnly(unittest.TestCase):
    def setUp(self) -> None:
        self.result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)

    def test_survivors_are_octet_identical_originals(self) -> None:
        originals = {str(r.event_id): r for r in RAW}
        for record in self.result.raw:
            self.assertEqual(record.canonical_bytes(), originals[str(record.event_id)].canonical_bytes())

    def test_survivors_keep_their_original_seq(self) -> None:
        by_id = {str(r.event_id): r.seq for r in RAW}
        for record in self.result.raw:
            self.assertEqual(record.seq, by_id[str(record.event_id)])

    def test_seq_is_no_longer_dense(self) -> None:
        seqs = [r.seq for r in self.result.raw if scn.source_key(r.source_id) == "iam_audit"]
        self.assertNotEqual(seqs, list(range(len(seqs))))

    def test_nothing_was_invented(self) -> None:
        self.assertTrue(
            {str(r.event_id) for r in self.result.raw} <= {str(r.event_id) for r in RAW}
        )

    def test_survivors_plus_removed_account_for_everything(self) -> None:
        self.assertEqual(len(self.result.raw) + len(self.result.removed), len(RAW))
        self.assertEqual(
            {str(r.event_id) for r in self.result.raw}
            | {str(r.event_id) for r in self.result.removed},
            {str(r.event_id) for r in RAW},
        )

    def test_identity_completeness_removes_nothing(self) -> None:
        identity = dg.degrade(RAW, dg.Completeness.percent(100), DSEED)
        self.assertEqual(identity.removed, ())
        self.assertEqual(identity.raw, RAW)
        self.assertEqual(identity.raw_bytes, gen.render_raw(RAW))


class TestNesting(unittest.TestCase):
    def test_deletion_sets_nest_across_a_whole_ladder(self) -> None:
        ladder = [100, 95, 90, 80, 70, 50, 30, 10]
        previous: frozenset[tuple[str, int]] | None = None
        for percent in ladder:
            result = dg.degrade(RAW, dg.Completeness.percent(percent), DSEED)
            current = result.removed_keys
            if previous is not None:
                self.assertTrue(
                    previous <= current,
                    f"c={percent}% did not delete a superset of the level above it",
                )
            previous = current

    def test_the_two_cells_the_slice_runs_nest(self) -> None:
        full = dg.degrade(RAW, dg.Completeness.percent(100), DSEED)
        partial = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.assertTrue(full.removed_keys <= partial.removed_keys)

    def test_ninety_nests_inside_seventy(self) -> None:
        ninety = dg.degrade(RAW, dg.Completeness.percent(90), DSEED)
        seventy = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.assertTrue(ninety.removed_keys < seventy.removed_keys)

    def test_survivors_nest_in_the_other_direction(self) -> None:
        ninety = dg.degrade(RAW, dg.Completeness.percent(90), DSEED)
        seventy = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.assertTrue(
            {str(r.event_id) for r in seventy.raw} < {str(r.event_id) for r in ninety.raw}
        )

    def test_a_different_seed_gives_a_different_deletion_set(self) -> None:
        one = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        other = dg.degrade(RAW, dg.Completeness.percent(70), DSEED + 1)
        self.assertNotEqual(one.removed_keys, other.removed_keys)
        self.assertEqual(len(one.removed), len(other.removed))

    def test_parent_chaining_records_the_parent_hash(self) -> None:
        ninety = dg.degrade(RAW, dg.Completeness.percent(90), DSEED)
        seventy = dg.degrade(RAW, dg.Completeness.percent(70), DSEED, parent=ninety)
        self.assertEqual(seventy.nested_parent_manifest_hash, ninety.manifest_hash())
        self.assertIn("nested_parent_manifest_hash", seventy.manifest())

    def test_the_highest_level_omits_the_parent_member(self) -> None:
        full = dg.degrade(RAW, dg.Completeness.percent(100), DSEED)
        self.assertIsNone(full.nested_parent_manifest_hash)
        self.assertNotIn("nested_parent_manifest_hash", full.manifest())

    def test_parent_chaining_does_not_change_which_records_go(self) -> None:
        ninety = dg.degrade(RAW, dg.Completeness.percent(90), DSEED)
        alone = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        chained = dg.degrade(RAW, dg.Completeness.percent(70), DSEED, parent=ninety)
        self.assertEqual(alone.removed_keys, chained.removed_keys)
        self.assertEqual(alone.raw_bytes, chained.raw_bytes)

    def test_a_parent_at_a_lower_level_is_rejected(self) -> None:
        low = dg.degrade(RAW, dg.Completeness.percent(50), DSEED)
        with self.assertRaises(SchemaError):
            dg.degrade(RAW, dg.Completeness.percent(70), DSEED, parent=low)

    def test_a_parent_from_another_seed_is_rejected(self) -> None:
        foreign = dg.degrade(RAW, dg.Completeness.percent(90), DSEED + 7)
        with self.assertRaises(SchemaError):
            dg.degrade(RAW, dg.Completeness.percent(70), DSEED, parent=foreign)


class TestStratification(unittest.TestCase):
    def test_each_source_loses_its_own_share(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        for name in _SOURCES:
            survivors = [r for r in result.raw if scn.source_key(r.source_id) == name]
            self.assertEqual(len(survivors), dg.Completeness.percent(70).keep(_PER_SOURCE))

    def test_no_source_is_wiped_out(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(30), DSEED)
        for name in _SOURCES:
            survivors = [r for r in result.raw if scn.source_key(r.source_id) == name]
            self.assertGreater(len(survivors), 0)


class TestCorrelatedLoss(unittest.TestCase):
    def test_deletion_leaves_a_contiguous_outage_rather_than_a_sprinkle(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        uniform_expectation = (_SPAN // _PER_SOURCE) * 4
        for name in _SOURCES:
            times = sorted(
                r.t_evt_ns for r in result.raw if scn.source_key(r.source_id) == name
            )
            widest = max(b - a for a, b in zip(times, times[1:]))
            self.assertGreater(
                widest,
                uniform_expectation,
                f"{name}: loss looks sprinkled, not like an outage",
            )

    def test_whole_blocks_go_before_records_are_thinned(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        removed = {(scn.source_key(r.source_id), r.seq) for r in result.removed}
        emptied = 0
        for name in _SOURCES:
            blocks: dict[int, list[int]] = {}
            for record in RAW:
                if scn.source_key(record.source_id) != name:
                    continue
                blocks.setdefault(record.t_evt_ns // dg.OUTAGE_BLOCK_SPAN_NS, []).append(record.seq)
            for seqs in blocks.values():
                if all((name, seq) in removed for seq in seqs):
                    emptied += 1
        self.assertGreater(emptied, 0)


class TestManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.document = self.result.manifest()

    def test_shape_is_the_contract(self) -> None:
        self.assertEqual(
            sorted(self.document),
            [
                "completeness",
                "degradation_seed",
                "operators",
                "parent_raw_hash",
                "removed",
                "schema",
            ],
        )
        self.assertEqual(self.document["schema"], dg.DEGRADATION_SCHEMA)
        self.assertEqual(self.document["operators"], ["delete"])

    def test_seed_is_fixed_width_hex(self) -> None:
        self.assertEqual(self.document["degradation_seed"], canon.mask_hex(DSEED))
        self.assertEqual(len(self.document["degradation_seed"]), 18)

    def test_completeness_is_an_exact_rational(self) -> None:
        self.assertEqual(self.document["completeness"], {"den": 10, "num": 7})

    def test_removed_is_sorted_by_source_then_seq(self) -> None:
        keys = [(row["source_id"], row["seq"]) for row in self.document["removed"]]
        self.assertEqual(keys, sorted(keys))
        canon.check_strictly_ascending(keys, lambda k: k, where="test.removed")

    def test_removed_rows_name_the_event_they_deleted(self) -> None:
        by_key = {(scn.source_key(r.source_id), r.seq): str(r.event_id) for r in RAW}
        for row in self.document["removed"]:
            self.assertEqual(by_key[(row["source_id"], row["seq"])], row["event_id"])

    def test_parent_raw_hash_covers_the_undegraded_stream(self) -> None:
        self.assertEqual(
            self.document["parent_raw_hash"], canon.hash_ref(gen.RAW_FILE_KIND, gen.render_raw(RAW))
        )
        self.assertTrue(self.document["parent_raw_hash"].startswith("b2b256:"))

    def test_manifest_serialises_under_the_encoding_law(self) -> None:
        payload = scf.scf_bytes(self.document, where="manifest")
        self.assertNotIn(b"\r", payload)
        self.assertNotIn(b"null", payload)
        self.assertTrue(payload.endswith(b"\n"))

    def test_manifest_hash_is_stable(self) -> None:
        again = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.assertEqual(self.result.manifest_hash(), again.manifest_hash())


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_are_byte_identical(self) -> None:
        one = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        other = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        self.assertEqual(one.raw_bytes, other.raw_bytes)
        self.assertEqual(
            scf.scf_bytes(one.manifest(), where="m"), scf.scf_bytes(other.manifest(), where="m")
        )

    def test_input_order_does_not_change_the_output(self) -> None:
        shuffled = tuple(reversed(RAW))
        one = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        other = dg.degrade(shuffled, dg.Completeness.percent(70), DSEED)
        self.assertEqual(one.raw_bytes, other.raw_bytes)
        self.assertEqual(one.removed_keys, other.removed_keys)

    def test_output_order_is_strictly_ascending(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        canon.check_strictly_ascending(
            [r.sort_key() for r in result.raw], lambda k: k, where="test.degraded"
        )


class TestWriters(unittest.TestCase):
    def test_file_names_carry_the_completeness_tag(self) -> None:
        result = dg.degrade(RAW, dg.Completeness.percent(70), DSEED)
        with tempfile.TemporaryDirectory() as directory:
            raw_path = dg.write_degraded_raw(pathlib.Path(directory), result)
            manifest_path = dg.write_manifest(pathlib.Path(directory), result)
            self.assertEqual(raw_path.name, "raw.c70.jsonl")
            self.assertEqual(manifest_path.name, "degradation_manifest.json")
            self.assertEqual(raw_path.read_bytes(), result.raw_bytes)
            self.assertEqual(
                manifest_path.read_bytes(), scf.scf_bytes(result.manifest(), where="m")
            )


class TestAgainstTheRealScenario(unittest.TestCase):
    """One end-to-end pass over the fixture, to pin the two cells the slice actually runs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = scn.load_scenario(_REPO_ROOT / "config" / "vs" / "scenario.toml")
        cls.generated = gen.gen(cls.spec, 20240204)
        cls.full = dg.degrade(cls.generated.raw, dg.Completeness.percent(100), DSEED)
        cls.partial = dg.degrade(
            cls.generated.raw, dg.Completeness.percent(70), DSEED, parent=cls.full
        )

    def test_the_full_cell_is_the_generator_output(self) -> None:
        self.assertEqual(self.full.raw_bytes, self.generated.raw_bytes)
        self.assertEqual(self.full.removed, ())

    def test_the_seventy_cell_nests_inside_the_full_cell(self) -> None:
        self.assertTrue(self.full.removed_keys <= self.partial.removed_keys)
        self.assertEqual(self.partial.nested_parent_manifest_hash, self.full.manifest_hash())

    def test_the_seventy_cell_kept_about_seven_tenths(self) -> None:
        self.assertLess(len(self.partial.raw), len(self.generated.raw))
        self.assertGreater(len(self.partial.raw), 0)
        for source in self.spec.sources:
            if not source.emits_event_types:
                continue
            population = len(self.generated.records_of(source.source_id))
            kept = len(
                [
                    r
                    for r in self.partial.raw
                    if scn.source_key(r.source_id) == scn.source_key(source.source_id)
                ]
            )
            self.assertEqual(kept, dg.Completeness.percent(70).keep(population))

    def test_the_silent_source_has_nothing_to_delete(self) -> None:
        removed = [
            r for r in self.partial.removed if scn.source_key(r.source_id) == "edr_host"
        ]
        self.assertEqual(removed, [])

    def test_degradation_never_touches_the_truth_stream(self) -> None:
        self.assertEqual(
            self.generated.truth_bytes, gen.render_truth(self.generated.truth)
        )
        self.assertEqual(len(self.generated.unobserved_steps()), 1)


class TestTheTwoCells(unittest.TestCase):
    """The operator must be ABLE to produce the cell the slice's central result rests on.

    The operative specification's two cells differ in exactly one way: at full
    completeness `iam_audit` is continuous across step k5 and an approval record precedes
    it, and at seventy per cent the source is silent across a span that contains both. If
    the degradation operator could not produce that shape at any seed, the premium result
    would be unreachable and the difference between the cells would not be "what you could
    see".

    The seed is pinned here so the shape is a regression rather than a coincidence. It
    selects which outage block goes; it is not a tuning knob on the result, and a
    different seed simply silences a different span.
    """

    #: The degradation seed whose seventy-per-cent cell silences the block containing k5.
    DEGRADATION_SEED = 1

    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = scn.load_scenario(_REPO_ROOT / "config" / "vs" / "scenario.toml")
        generated = gen.gen(cls.spec, 20240204)
        cls.full = dg.degrade(generated.raw, dg.Completeness.percent(100), cls.DEGRADATION_SEED)
        cls.partial = dg.degrade(
            generated.raw,
            dg.Completeness.percent(70),
            cls.DEGRADATION_SEED,
            parent=cls.full,
        )
        step = next(s for s in cls.spec.attack.steps if s.k == 5)
        cls.t_k5 = cls.spec.epoch_ns + step.t_offset_ns

    def _holds(self, result, event_type: str, t_ns: int) -> bool:
        return any(r.event_type == event_type and r.t_evt_ns == t_ns for r in result.raw)

    def test_at_full_completeness_the_escalation_is_observed(self) -> None:
        self.assertTrue(self._holds(self.full, "iam_role_assumed", self.t_k5))

    def test_at_full_completeness_an_approval_precedes_the_escalation(self) -> None:
        approvals = [
            r.t_evt_ns
            for r in self.full.raw
            if r.event_type == "iam_approval_granted" and r.t_evt_ns < self.t_k5
        ]
        self.assertGreater(len(approvals), 0)
        self.assertLess(self.t_k5 - max(approvals), 60_000_000_000)

    def test_at_seventy_the_escalation_record_is_gone(self) -> None:
        self.assertFalse(self._holds(self.partial, "iam_role_assumed", self.t_k5))

    def test_at_seventy_the_source_is_silent_across_the_escalation(self) -> None:
        times = sorted(
            r.t_evt_ns for r in self.partial.raw if scn.source_key(r.source_id) == "iam_audit"
        )
        before = [t for t in times if t < self.t_k5]
        after = [t for t in times if t > self.t_k5]
        self.assertTrue(before and after)
        silence = after[0] - before[-1]
        self.assertGreater(silence, dg.OUTAGE_BLOCK_SPAN_NS)
        self.assertGreater(self.t_k5 - before[-1], 600_000_000_000)

    def test_the_other_route_survives_the_same_degradation(self) -> None:
        step = next(s for s in self.spec.attack.steps if s.k == 4)
        self.assertTrue(
            self._holds(self.partial, "res_read", self.spec.epoch_ns + step.t_offset_ns)
        )

    def test_the_two_cells_are_nested_and_chained(self) -> None:
        self.assertEqual(self.full.removed, ())
        self.assertTrue(self.full.removed_keys <= self.partial.removed_keys)
        self.assertEqual(self.partial.nested_parent_manifest_hash, self.full.manifest_hash())


class TestBlackout(unittest.TestCase):
    """WHOLE_SOURCE_BLACKOUT: a controlled, single-variable intervention.

    The random completeness operator deletes across every source, so a demonstration that
    uses it cannot say which sensor's absence produced an effect. The blackout removes one
    named source over one named window and nothing else; these tests pin exactly that.
    """

    T0 = _EPOCH + _SPAN // 4
    T1 = _EPOCH + _SPAN // 2

    def setUp(self) -> None:
        self.spec = dg.Blackout(sources=("iam_audit",), t0_ns=self.T0, t1_ns=self.T1)
        self.result = dg.blackout(RAW, self.spec)

    def _covered(self, r: gen.RawEvent) -> bool:
        return scn.source_key(r.source_id) == "iam_audit" and self.T0 <= r.t_evt_ns < self.T1

    def test_it_removes_exactly_the_covered_records(self) -> None:
        expected = {(scn.source_key(r.source_id), r.seq) for r in RAW if self._covered(r)}
        self.assertTrue(expected)
        self.assertEqual(self.result.removed_keys, frozenset(expected))

    def test_every_other_source_is_untouched(self) -> None:
        for name in ("gw_access", "res_access"):
            before = [r for r in RAW if scn.source_key(r.source_id) == name]
            after = [r for r in self.result.raw if scn.source_key(r.source_id) == name]
            self.assertEqual(before, after, name)

    def test_the_blacked_out_source_is_untouched_outside_the_window(self) -> None:
        outside = [
            r for r in RAW
            if scn.source_key(r.source_id) == "iam_audit" and not self._covered(r)
        ]
        kept = [r for r in self.result.raw if scn.source_key(r.source_id) == "iam_audit"]
        self.assertEqual(outside, kept)

    def test_the_window_is_half_open(self) -> None:
        at_t1 = [r for r in RAW if scn.source_key(r.source_id) == "iam_audit" and r.t_evt_ns == self.T1]
        for r in at_t1:
            self.assertIn(r, self.result.raw)

    def test_it_is_seedless_and_deterministic(self) -> None:
        again = dg.blackout(RAW, self.spec)
        self.assertEqual(self.result.raw_bytes, again.raw_bytes)
        self.assertEqual(self.result.manifest_hash(), again.manifest_hash())

    def test_the_manifest_names_the_operator_and_the_window(self) -> None:
        m = self.result.manifest()
        self.assertEqual(m["operators"], ["whole_source_blackout"])
        self.assertEqual(m["blackout"]["sources"], ["iam_audit"])
        self.assertEqual(m["blackout"]["t0_ns"], str(self.T0))
        self.assertEqual(m["blackout"]["t1_ns"], str(self.T1))

    def test_a_random_deletion_manifest_is_unchanged(self) -> None:
        """Adding the operator must not alter what a random-deletion manifest says."""
        m = dg.degrade(RAW, dg.Completeness.of(7, 10), DSEED).manifest()
        self.assertEqual(m["operators"], ["delete"])
        self.assertNotIn("blackout", m)

    def test_an_empty_or_inverted_window_is_refused(self) -> None:
        with self.assertRaises(SchemaError):
            dg.Blackout(sources=("iam_audit",), t0_ns=self.T1, t1_ns=self.T1)
        with self.assertRaises(SchemaError):
            dg.Blackout(sources=("iam_audit",), t0_ns=self.T1, t1_ns=self.T0)

    def test_sources_must_be_unique_and_ordered(self) -> None:
        with self.assertRaises(SchemaError):
            dg.Blackout(sources=("res_access", "iam_audit"), t0_ns=self.T0, t1_ns=self.T1)
        with self.assertRaises(SchemaError):
            dg.Blackout(sources=(), t0_ns=self.T0, t1_ns=self.T1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
