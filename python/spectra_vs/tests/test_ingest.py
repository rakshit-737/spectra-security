"""Unit tests for S4 ingest.

Run from the repository root:

    python python/spectra_vs/tests/test_ingest.py

Run directly rather than through a runner, for the same reason the foundation's tests
are: there is no pytest here and a stage that needs a package manager to test itself is
not testable on this machine.

What these tests pin: that no line is ever dropped without a counted reason, that input
order cannot reach the bundle bytes, that a contaminated line stops the run rather than
being quarantined, and that the chain a bundle carries is recomputable from the bundle
alone. Each compares bytes or exact reason codes, so a mutation turns one of them red
rather than merely making a count look different.
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

from spectra_core import canon  # noqa: E402
from spectra_core.errors import CanonError, LimitError, QuarantineReason, SchemaError  # noqa: E402
from spectra_core.ids import SourceId  # noqa: E402
from spectra_core.model import IntegrityClass, Source  # noqa: E402

from spectra_vs import ingest as S4  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SOURCES = (
    Source(
        source_id=SourceId.of("idp_auth"),
        integrity_class=IntegrityClass.CHAINED,
        source_rank=1,
        emits_event_types=("auth_refresh", "auth_success"),
    ),
    Source(
        source_id=SourceId.of("gw_access"),
        integrity_class=IntegrityClass.SEQUENCED,
        source_rank=2,
        emits_event_types=("gw_call",),
    ),
    Source(
        source_id=SourceId.of("res_access"),
        integrity_class=IntegrityClass.NONE,
        source_rank=3,
        emits_event_types=("res_read",),
    ),
    Source(
        source_id=SourceId.of("edr_host"),
        integrity_class=IntegrityClass.NONE,
        source_rank=4,
        emits_event_types=(),
    ),
)


def raw_line(source: str, seq: int, t_ns: int, event_type: str, **attrs: str) -> bytes:
    return S4.scf_line(
        {
            "attrs": dict(attrs),
            "event_type": event_type,
            "seq": seq,
            "source_id": source,
            "t_evt_ns": str(t_ns),
        }
    )


BASE_LINES = (
    raw_line("idp_auth", 0, 1_000_000_000, "auth_refresh", principal="alice", token="tok_a"),
    raw_line("idp_auth", 1, 3_000_000_000, "auth_success", principal="alice", token="tok_a"),
    raw_line("gw_access", 0, 2_000_000_000, "gw_call", token="tok_a", resource="res_bulk"),
    raw_line("res_access", 7, 4_000_000_000, "res_read", resource="res_bulk"),
)


def ingest_lines(lines, **kwargs):
    return S4.ingest_bytes(b"".join(lines), SOURCES, **kwargs)


def reasons(result) -> list[tuple[str, str]]:
    return [(str(record.reason), record.detail) for record in result.quarantined]


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


class TestBundle(unittest.TestCase):
    def test_every_line_is_bundled_and_nothing_is_quarantined(self) -> None:
        result = ingest_lines(BASE_LINES)
        self.assertEqual(result.counts.lines_read, 4)
        self.assertEqual(result.counts.records_bundled, 4)
        self.assertEqual(result.counts.records_quarantined, 0)
        self.assertFalse(result.quarantined_records)

    def test_file_order_is_t_evt_then_source_then_seq(self) -> None:
        result = ingest_lines(BASE_LINES)
        self.assertEqual(
            [(event.t_evt_ns, event.source_id.snake, event.seq) for event in result.events],
            [
                (1_000_000_000, "idp_auth", 0),
                (2_000_000_000, "gw_access", 0),
                (3_000_000_000, "idp_auth", 1),
                (4_000_000_000, "res_access", 7),
            ],
        )

    def test_event_ids_recompute_from_the_declared_preimage(self) -> None:
        for event in ingest_lines(BASE_LINES).events:
            self.assertTrue(event.verify_id(), event.event_id)

    def test_bundle_hash_is_the_digest_of_the_bundle_bytes(self) -> None:
        result = ingest_lines(BASE_LINES)
        self.assertEqual(result.bundle_hash, canon.hash_ref("bn", result.bundle_bytes))
        self.assertTrue(result.bundle_hash.startswith("b2b256:"))

    def test_bundle_record_members_are_exactly_the_contract(self) -> None:
        import json

        rows = [json.loads(line) for line in ingest_lines(BASE_LINES).bundle_bytes.splitlines()]
        core = {"attrs", "event_id", "event_type", "seq", "source_id", "t_evt_ns", "t_ing_ns"}
        for row in rows:
            extra = set(row) - core
            self.assertTrue(extra <= {"chain_hash", "chain_prev"}, extra)
            self.assertTrue(core <= set(row))
            self.assertNotIn("record_id", row)
            self.assertIsInstance(row["t_evt_ns"], str)
            self.assertIsInstance(row["seq"], int)

    def test_t_ing_defaults_to_t_evt_and_can_be_pinned(self) -> None:
        default = ingest_lines(BASE_LINES)
        for event in default.events:
            self.assertEqual(event.t_ing_ns, event.t_evt_ns)
        pinned = ingest_lines(BASE_LINES, ingest_time_ns=9_000_000_000)
        for event in pinned.events:
            self.assertEqual(event.t_ing_ns, 9_000_000_000)
        self.assertEqual(
            [str(e.event_id) for e in default.events],
            [str(e.event_id) for e in pinned.events],
            "t_ing_ns must not enter the event id",
        )

    def test_source_ids_are_written_bare_as_the_contract_spells_them(self) -> None:
        result = ingest_lines(BASE_LINES)
        self.assertIn(b'"source_id":"idp_auth"', result.bundle_bytes)
        self.assertNotIn(b"src:", result.bundle_bytes)
        self.assertEqual(result.events[0].source_id, "src:idp_auth")


# ---------------------------------------------------------------------------
# G-D1: input order never reaches an output
# ---------------------------------------------------------------------------


class TestPermutationInvariance(unittest.TestCase):
    def test_shuffled_input_gives_an_identical_bundle(self) -> None:
        reference = ingest_lines(BASE_LINES)
        rng = random.Random(20260921)
        for _ in range(64):
            shuffled = list(BASE_LINES)
            rng.shuffle(shuffled)
            candidate = ingest_lines(shuffled)
            self.assertEqual(candidate.bundle_bytes, reference.bundle_bytes)
            self.assertEqual(candidate.bundle_hash, reference.bundle_hash)

    def test_shuffled_input_gives_an_identical_quarantine_account(self) -> None:
        lines = list(BASE_LINES) + [
            b"not json at all\n",
            raw_line("nope_src", 0, 5_000_000_000, "res_read"),
            b"\n",
        ]
        reference = ingest_lines(lines)
        report = S4.scf_line(reference.quarantine_report_obj())
        rng = random.Random(7)
        for _ in range(64):
            shuffled = list(lines)
            rng.shuffle(shuffled)
            candidate = ingest_lines(shuffled)
            self.assertEqual(candidate.bundle_bytes, reference.bundle_bytes)
            self.assertEqual(S4.scf_line(candidate.quarantine_report_obj()), report)


# ---------------------------------------------------------------------------
# Label purity
# ---------------------------------------------------------------------------


class TestLabelPurity(unittest.TestCase):
    def test_top_level_truth_key_aborts(self) -> None:
        line = S4.scf_dumps(
            {
                "attrs": {},
                "event_type": "res_read",
                "seq": 0,
                "source_id": "res_access",
                "t_evt_ns": "1",
                "truth": "tr_0000000000000001",
            }
        ).encode("utf-8") + b"\n"
        with self.assertRaises(S4.LabelPurityError) as raised:
            ingest_lines([line])
        self.assertEqual(raised.exception.code, "Q_LABEL_LEAK")
        self.assertEqual(raised.exception.exit_code, 4)
        self.assertNotIn("tr_0000000000000001", str(raised.exception))

    def test_every_forbidden_top_level_key_aborts(self) -> None:
        for key in sorted(S4.FORBIDDEN_KEYS) + ["__truth_step"]:
            line = S4.scf_dumps(
                {
                    "attrs": {},
                    "event_type": "res_read",
                    "seq": 0,
                    "source_id": "res_access",
                    "t_evt_ns": "1",
                    key: "x",
                }
            ).encode("utf-8") + b"\n"
            with self.assertRaises(S4.LabelPurityError, msg=key):
                ingest_lines([line])

    def test_a_label_inside_attrs_aborts(self) -> None:
        line = raw_line("res_access", 0, 1, "res_read", is_attack="true")
        with self.assertRaises(S4.LabelPurityError):
            ingest_lines([line])

    def test_an_oversized_line_is_still_scanned_for_labels(self) -> None:
        padded = raw_line("res_access", 0, 1, "res_read", truth_pad="x" * 400)
        limits = S4.IngestLimits(max_line_bytes=64)
        # The padded line has no forbidden key, so it is merely quarantined.
        result = ingest_lines([padded], limits=limits)
        self.assertEqual(reasons(result), [("Q_UNPARSEABLE", "line_too_long")])
        leaking = raw_line("res_access", 0, 1, "res_read", truth="x" * 400)
        with self.assertRaises(S4.LabelPurityError):
            ingest_lines([leaking], limits=limits)


# ---------------------------------------------------------------------------
# Quarantine: every drop is counted under a closed reason code
# ---------------------------------------------------------------------------


class TestQuarantine(unittest.TestCase):
    def one(self, line: bytes, **kwargs) -> tuple[str, str]:
        result = ingest_lines([line], **kwargs)
        self.assertEqual(result.counts.records_bundled, 0)
        self.assertEqual(len(result.quarantined), 1)
        self.assertTrue(result.quarantined_records)
        return reasons(result)[0]

    def test_invalid_utf8(self) -> None:
        self.assertEqual(self.one(b"\xff\xfe not utf8\n"), ("Q_UNPARSEABLE", "invalid_utf8"))

    def test_empty_line(self) -> None:
        self.assertEqual(self.one(b"\n"), ("Q_UNPARSEABLE", "empty_line"))

    def test_missing_trailing_newline(self) -> None:
        line = raw_line("res_access", 0, 1, "res_read").rstrip(b"\n")
        self.assertEqual(self.one(line), ("Q_NONCANONICAL", "no_trailing_newline"))

    def test_not_json(self) -> None:
        self.assertEqual(self.one(b"{not json\n"), ("Q_UNPARSEABLE", "not_json"))

    def test_not_an_object(self) -> None:
        self.assertEqual(self.one(b"[1,2,3]\n"), ("Q_UNPARSEABLE", "not_object"))

    def test_a_float_anywhere(self) -> None:
        line = b'{"attrs":{},"event_type":"res_read","seq":0.5,"source_id":"res_access","t_evt_ns":"1"}\n'
        self.assertEqual(self.one(line), ("Q_FLOAT_PRESENT", "float_literal"))

    def test_nan_is_a_float(self) -> None:
        line = b'{"attrs":{},"event_type":"res_read","seq":NaN,"source_id":"res_access","t_evt_ns":"1"}\n'
        self.assertEqual(self.one(line), ("Q_FLOAT_PRESENT", "float_literal"))

    def test_duplicate_object_key(self) -> None:
        line = (
            b'{"attrs":{},"event_type":"res_read","seq":0,"seq":1,'
            b'"source_id":"res_access","t_evt_ns":"1"}\n'
        )
        self.assertEqual(self.one(line), ("Q_NONCANONICAL", "duplicate_key"))

    def test_unsorted_keys_are_noncanonical(self) -> None:
        line = (
            b'{"source_id":"res_access","attrs":{},"event_type":"res_read","seq":0,'
            b'"t_evt_ns":"1"}\n'
        )
        self.assertEqual(self.one(line), ("Q_NONCANONICAL", "reserialise_differs"))

    def test_insignificant_whitespace_is_noncanonical(self) -> None:
        line = (
            b'{"attrs": {}, "event_type": "res_read", "seq": 0, '
            b'"source_id": "res_access", "t_evt_ns": "1"}\n'
        )
        self.assertEqual(self.one(line), ("Q_NONCANONICAL", "reserialise_differs"))

    def test_member_set_must_be_exact(self) -> None:
        line = b'{"attrs":{},"event_type":"res_read","seq":0,"source_id":"res_access"}\n'
        self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "member_set"))
        extra = S4.scf_dumps(
            {
                "attrs": {},
                "event_type": "res_read",
                "extra": "x",
                "seq": 0,
                "source_id": "res_access",
                "t_evt_ns": "1",
            }
        ).encode("utf-8") + b"\n"
        self.assertEqual(self.one(extra), ("Q_UNPARSEABLE", "member_set"))

    def test_undeclared_source(self) -> None:
        line = raw_line("nope_src", 0, 1, "res_read")
        self.assertEqual(self.one(line), ("Q_UNKNOWN_SOURCE", "source_undeclared"))

    def test_source_id_not_a_snake(self) -> None:
        line = raw_line("Res-Access", 0, 1, "res_read")
        self.assertEqual(self.one(line), ("Q_UNKNOWN_SOURCE", "source_id_form"))
        self.assertEqual(ingest_lines([line]).quarantined[0].source_id, "")

    def test_event_type_not_declared_by_the_source(self) -> None:
        line = raw_line("res_access", 0, 1, "auth_refresh")
        self.assertEqual(self.one(line), ("Q_UNKNOWN_EVENT_TYPE", "event_type_undeclared"))

    def test_a_source_that_emits_nothing_accepts_nothing(self) -> None:
        line = raw_line("edr_host", 0, 1, "res_read")
        self.assertEqual(self.one(line), ("Q_UNKNOWN_EVENT_TYPE", "event_type_undeclared"))

    def test_t_evt_ns_must_be_i64_decimal_text(self) -> None:
        for bad in ('"01"', '"-0"', '"1e9"', "1"):
            line = (
                b'{"attrs":{},"event_type":"res_read","seq":0,"source_id":"res_access",'
                b'"t_evt_ns":' + bad.encode("ascii") + b"}\n"
            )
            self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "t_evt_ns_form"), bad)

    def test_t_evt_ns_outside_i64_saturates(self) -> None:
        line = raw_line("res_access", 0, 1 << 70, "res_read")
        self.assertEqual(self.one(line), ("Q_ARITH_SATURATION", "t_evt_ns_width"))

    def test_seq_outside_u32(self) -> None:
        # Written as literal bytes: the canonical encoder will not emit a bare integer
        # this wide, which is the point, so the fixture has to be hand-made.
        line = (
            b'{"attrs":{},"event_type":"res_read","seq":8589934592,'
            b'"source_id":"res_access","t_evt_ns":"1"}\n'
        )
        self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "seq_width"))

    def test_seq_must_not_be_a_bool(self) -> None:
        line = b'{"attrs":{},"event_type":"res_read","seq":true,"source_id":"res_access","t_evt_ns":"1"}\n'
        self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "seq_form"))

    def test_attribute_count_limit(self) -> None:
        attrs = {f"k{index:02d}": "v" for index in range(12)}
        line = raw_line("res_access", 0, 1, "res_read", **attrs)
        self.assertEqual(
            self.one(line, limits=S4.IngestLimits(max_attrs=8)),
            ("Q_UNPARSEABLE", "attr_count"),
        )

    def test_attribute_value_must_be_a_string(self) -> None:
        line = b'{"attrs":{"n":1},"event_type":"res_read","seq":0,"source_id":"res_access","t_evt_ns":"1"}\n'
        self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "attr_value_form"))

    def test_attribute_key_form(self) -> None:
        line = b'{"attrs":{"Bad":"v"},"event_type":"res_read","seq":0,"source_id":"res_access","t_evt_ns":"1"}\n'
        self.assertEqual(self.one(line), ("Q_UNPARSEABLE", "attr_key_form"))

    def test_attribute_value_length_limit(self) -> None:
        line = raw_line("res_access", 0, 1, "res_read", v="x" * 40)
        self.assertEqual(
            self.one(line, limits=S4.IngestLimits(max_attr_value_bytes=8)),
            ("Q_UNPARSEABLE", "attr_value_too_long"),
        )

    def test_record_size_limit_applies_after_parsing(self) -> None:
        line = raw_line("res_access", 0, 1, "res_read", v="x" * 400)
        self.assertEqual(
            self.one(line, limits=S4.IngestLimits(max_record_bytes=64)),
            ("Q_UNPARSEABLE", "record_too_large"),
        )

    def test_identical_lines_keep_one_and_count_the_rest(self) -> None:
        line = raw_line("res_access", 0, 1, "res_read")
        result = ingest_lines([line, line, line])
        self.assertEqual(result.counts.records_bundled, 1)
        self.assertEqual(reasons(result), [("Q_DUPLICATE_RECORD", "identical_line")] * 2)

    def test_a_seq_collision_quarantines_every_colliding_record(self) -> None:
        first = raw_line("res_access", 3, 1, "res_read", tag="a")
        second = raw_line("res_access", 3, 2, "res_read", tag="b")
        result = ingest_lines([first, second])
        self.assertEqual(result.counts.records_bundled, 0)
        self.assertEqual(reasons(result), [("Q_SEQ_REGRESSION", "seq_collision")] * 2)

    def test_counts_are_sorted_tuples_not_dicts(self) -> None:
        result = ingest_lines(
            list(BASE_LINES) + [b"garbage\n", raw_line("nope_src", 0, 9, "res_read")]
        )
        self.assertEqual(
            result.counts.by_reason, (("Q_UNKNOWN_SOURCE", 1), ("Q_UNPARSEABLE", 1))
        )
        self.assertEqual(
            result.counts.by_source_bundled,
            (("gw_access", 1), ("idp_auth", 2), ("res_access", 1)),
        )
        self.assertEqual(
            [key for key, _ in result.counts.by_source_quarantined], ["", "nope_src"]
        )

    def test_every_emitted_detail_token_is_declared(self) -> None:
        lines = [
            b"\xff\n",
            b"\n",
            b"{not json\n",
            b"[1]\n",
            raw_line("nope_src", 0, 1, "res_read"),
            raw_line("res_access", 0, 1, "auth_refresh"),
        ]
        for reason, detail in reasons(ingest_lines(lines)):
            self.assertIn(detail, S4.QUARANTINE_DETAILS, detail)
            self.assertIn(reason, {str(value) for value in QuarantineReason})


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


class TestChain(unittest.TestCase):
    def test_only_integrity_bearing_sources_carry_chain_members(self) -> None:
        result = ingest_lines(BASE_LINES)
        for event in result.events:
            if event.source_id.snake in ("idp_auth", "gw_access"):
                self.assertIsNotNone(event.chain_hash)
                self.assertIsNotNone(event.chain_prev)
            else:
                self.assertIsNone(event.chain_hash)
                self.assertIsNone(event.chain_prev)

    def test_the_first_record_of_a_source_links_to_its_genesis(self) -> None:
        result = ingest_lines(BASE_LINES)
        first = [e for e in result.events if e.source_id.snake == "idp_auth"][0]
        self.assertEqual(first.chain_prev, S4.chain_genesis(first.source_id))

    def test_genesis_is_per_source(self) -> None:
        self.assertNotEqual(
            S4.chain_genesis(SourceId.of("idp_auth")), S4.chain_genesis(SourceId.of("gw_access"))
        )

    def test_the_chain_recomputes_from_the_bundle_alone(self) -> None:
        result = ingest_lines(BASE_LINES)
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path, _ = result.write(tmp)
            reread = S4.read_bundle(bundle_path)
        for snake in ("idp_auth", "gw_access"):
            slice_ = [event for event in reread if event.source_id.snake == snake]
            self.assertEqual(S4.verify_chain(slice_), ())

    def test_a_tampered_link_is_reported(self) -> None:
        result = ingest_lines(BASE_LINES)
        idp = [event for event in result.events if event.source_id.snake == "idp_auth"]
        import dataclasses

        broken = list(idp)
        broken[1] = dataclasses.replace(
            broken[1], chain_hash=S4.chain_genesis(SourceId.of("gw_access"))
        )
        self.assertEqual(S4.verify_chain(broken), (broken[1].event_id,))

    def test_a_reordered_source_slice_breaks_verification(self) -> None:
        result = ingest_lines(BASE_LINES)
        idp = [event for event in result.events if event.source_id.snake == "idp_auth"]
        self.assertNotEqual(S4.verify_chain(list(reversed(idp))), ())


# ---------------------------------------------------------------------------
# Limits, files and round trip
# ---------------------------------------------------------------------------


class TestFilesAndLimits(unittest.TestCase):
    def test_max_records_aborts_rather_than_truncating(self) -> None:
        with self.assertRaises(LimitError):
            ingest_lines(BASE_LINES, limits=S4.IngestLimits(max_records=2))

    def test_limits_reject_a_non_positive_bound(self) -> None:
        with self.assertRaises(SchemaError):
            S4.IngestLimits(max_attrs=0)

    def test_a_source_declared_twice_is_a_usage_error(self) -> None:
        with self.assertRaises(SchemaError):
            S4.ingest_bytes(b"", SOURCES + (SOURCES[0],))

    def test_ingest_from_a_path_matches_ingest_from_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = pathlib.Path(tmp) / "raw.c70.jsonl"
            raw_path.write_bytes(b"".join(BASE_LINES))
            self.assertEqual(
                S4.ingest(raw_path, SOURCES).bundle_hash, ingest_lines(BASE_LINES).bundle_hash
            )

    def test_read_bundle_round_trips(self) -> None:
        result = ingest_lines(BASE_LINES)
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path, quarantine_path = result.write(tmp)
            reread = S4.read_bundle(bundle_path)
            self.assertTrue(quarantine_path.exists())
        self.assertEqual(
            [str(event.event_id) for event in reread],
            [str(event.event_id) for event in result.events],
        )
        self.assertEqual(
            [event.chain_hash for event in reread], [event.chain_hash for event in result.events]
        )

    def test_read_bundle_never_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bundle.jsonl"
            path.write_bytes(b'{"event_id": "ev:00"}\n')
            with self.assertRaises((CanonError, SchemaError, ValueError)):
                S4.read_bundle(path)

    def test_empty_input_is_an_empty_bundle(self) -> None:
        result = S4.ingest_bytes(b"", SOURCES)
        self.assertEqual(result.bundle_bytes, b"")
        self.assertEqual(result.counts.lines_read, 0)


# ---------------------------------------------------------------------------
# SCF-lite
# ---------------------------------------------------------------------------


class TestScf(unittest.TestCase):
    def test_keys_are_sorted_and_whitespace_is_absent(self) -> None:
        self.assertEqual(S4.scf_dumps({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_floats_null_and_bad_keys_are_rejected(self) -> None:
        for bad in ({"a": 1.5}, {"a": None}, {"A": 1}, {"a": float("nan")}):
            with self.assertRaises((CanonError, SchemaError), msg=repr(bad)):
                S4.scf_dumps(bad)

    def test_a_bare_integer_wider_than_u32_is_rejected(self) -> None:
        """Anything wider than u32 is a string on the wire, per the encoding law."""
        S4.scf_dumps({"a": (1 << 32) - 1})
        with self.assertRaises(SchemaError):
            S4.scf_dumps({"a": 1 << 32})

    def test_the_encoder_is_the_packages_only_one(self) -> None:
        from spectra_vs import scf

        self.assertEqual(S4.scf_dumps({"b": 1, "a": 2}), scf.scf_dumps({"b": 1, "a": 2}))
        self.assertEqual(S4.scf_line({"a": 1}), scf.scf_bytes({"a": 1}))

    def test_exactly_one_trailing_newline(self) -> None:
        line = S4.scf_line({"a": 1})
        self.assertTrue(line.endswith(b"\n"))
        self.assertEqual(line.count(b"\n"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
