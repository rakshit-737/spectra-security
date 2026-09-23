"""Unit tests for spectra_vs.store, the SQLite index over one sealed bundle.

Run from the repository root:

    python python/spectra_vs/tests/test_store.py

WHY THESE TESTS AND NOT OTHERS. The store answers five questions about a bundle that is
already sealed: how many records a source emitted, when its first and last recorded event
times are, what the deltas between its consecutive records are, what one record is, and
which records of one source fall in a half-open time window. Every test below pins one of
those answers, the refusal of an input the store cannot index honestly, or the fact that
an answer is ordered by an ORDER BY rather than by luck.

WHAT IS DELIBERATELY NOT TESTED HERE, because the module does not do it: chain
verification, tamper detection, event-id recomputation and canonical-form checking. Those
belong to `ingest.read_bundle` and to the checker. `TestWhatThisDoesNotDo` at the end
pins the absence, so that a later edit which quietly adds a verification claim to an
indexer goes red instead of going unnoticed.

THE DETERMINISM PAIR that the house rules require is `TestDeterminism`: one test loads the
same bundle twice and compares every answer, and one strips the ORDER BY off a query and
shows the answer stops being a function of the bundle alone. The second is the load-bearing
one - it is the evidence that the ordering is explicit rather than inherited from whatever
order SQLite happened to scan.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core.errors import SpectraError  # noqa: E402

from spectra_vs import store  # noqa: E402

SECOND = 1_000_000_000


def _record(source: str, seq: int, t_evt_s: int, *, chained: bool = False) -> dict[str, object]:
    """One bundle line as a plain object, with the members the wire contract carries.

    `t_evt_ns` and `t_ing_ns` are decimal STRINGS here because that is how they appear in
    `bundle.jsonl`: the encoding law permits a bare JSON integer only in a u32 position.
    The `attrs` are written service-before-principal, so a test that asserts they come
    back key-sorted is asserting the sort and not the input order arriving intact.
    """
    line: dict[str, object] = {
        "attrs": {"service": "sv_idp", "principal": "p_ops"},
        "event_id": f"ev:{source}-{seq:04d}",
        "event_type": "probe",
        "seq": seq,
        "source_id": source,
        "t_evt_ns": str(t_evt_s * SECOND),
        "t_ing_ns": "0",
    }
    if chained:
        line["chain_hash"] = f"b2b256:{seq:064x}"
        line["chain_prev"] = f"b2b256:{seq - 1:064x}" if seq else f"b2b256:{0:064x}"
    return line


#: Three sources with three shapes: a chained one that ascends, an unchained one with a
#: long silence, and one whose second record is recorded BEFORE its first.
_BUNDLE: tuple[dict[str, object], ...] = (
    _record("gw_access", 0, 10, chained=True),
    _record("gw_access", 1, 20, chained=True),
    _record("gw_access", 2, 25, chained=True),
    _record("iam_audit", 0, 5),
    _record("iam_audit", 1, 100),
    _record("net_flow", 0, 50),
    _record("net_flow", 1, 40),
)


def _write_bundle(directory: str, records: object) -> pathlib.Path:
    """Render records as JSONL and write them with LF endings and no BOM.

    Binary mode on purpose: text mode on Windows would translate LF to CRLF, and the
    loader refuses a CR, so a test fixture written in text mode would fail for a reason
    that has nothing to do with the property under test.
    """
    path = pathlib.Path(directory) / "bundle.jsonl"
    body = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records  # type: ignore[union-attr]
    )
    path.write_bytes(body.encode("utf-8"))
    return path


class _BundleCase(unittest.TestCase):
    """Builds a bundle on disk and loads it, cleaning both up when the test ends."""

    def bundle_path(self, records: object = None) -> pathlib.Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return _write_bundle(directory.name, _BUNDLE if records is None else records)

    def loaded(self, records: object = None) -> store.EventStore:
        opened = store.load_bundle(self.bundle_path(records))
        self.addCleanup(opened.close)
        return opened


class TestLoading(_BundleCase):
    def test_every_line_of_the_bundle_becomes_one_row(self) -> None:
        indexed = self.loaded()
        self.assertEqual(sum(s.records for s in indexed.source_stats()), len(_BUNDLE))

    def test_the_ddl_lives_in_the_sql_file_and_is_not_duplicated_in_python(self) -> None:
        """The schema is the contract, so there is exactly one copy of it."""
        self.assertTrue(store.SCHEMA_PATH.is_file(), store.SCHEMA_PATH)
        self.assertIn("proj_event", store.schema_sql())
        source = pathlib.Path(store.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CREATE TABLE", source)
        self.assertNotIn("CREATE INDEX", source)

    def test_an_absent_chain_member_arrives_as_none_and_not_as_a_string(self) -> None:
        """Absence on the wire is member absence; in a table it is NULL, never 'null'."""
        indexed = self.loaded()
        unchained = indexed.event("ev:iam_audit-0000")
        chained = indexed.event("ev:gw_access-0000")
        self.assertIsNone(unchained.chain_hash)
        self.assertIsNone(unchained.chain_prev)
        self.assertEqual(chained.chain_hash, f"b2b256:{0:064x}")

    def test_a_time_is_stored_as_an_integer_parsed_from_its_decimal_string(self) -> None:
        row = self.loaded().event("ev:iam_audit-0001")
        self.assertIsInstance(row.t_evt_ns, int)
        self.assertEqual(row.t_evt_ns, 100 * SECOND)
        self.assertEqual(row.t_ing_ns, 0)

    def test_a_time_that_is_not_a_plain_decimal_string_is_refused(self) -> None:
        """`int()` accepts underscores, surrounding space and a leading plus. A bundle
        that carried any of them would index to a value no other stage would compute, so
        the parser is narrower than `int()` on purpose."""
        for bad in ("1_000", " 12", "+12", "1.0", "0x10", "", "12 ", 12):
            with self.subTest(bad=bad):
                broken = [dict(_record("gw_access", 0, 10), t_evt_ns=bad)]
                with self.assertRaises(SpectraError):
                    self.loaded(broken)

    def test_a_float_time_is_refused_rather_than_rounded(self) -> None:
        broken = [dict(_record("gw_access", 0, 10), t_evt_ns=1.5)]
        with self.assertRaises(SpectraError):
            self.loaded(broken)

    def test_a_duplicate_event_id_is_refused_rather_than_replaced(self) -> None:
        """Replacing would make a second load a silent no-op and hide the defect."""
        with self.assertRaises(SpectraError):
            self.loaded([_record("gw_access", 0, 10), _record("gw_access", 0, 10)])

    def test_a_member_written_as_null_is_refused_rather_than_read_as_absent(self) -> None:
        """The wire spells absence by omitting a member, so reading a written null as
        absence would accept a spelling the encoding law does not have."""
        with self.assertRaises(SpectraError):
            self.loaded([dict(_record("gw_access", 0, 10), chain_hash=None)])

    def test_a_load_that_fails_leaves_the_index_as_it_found_it(self) -> None:
        """One transaction. A half-loaded index does not report an error; it reports
        counts that are wrong, which is worse."""
        indexed = store.EventStore.open()
        self.addCleanup(indexed.close)
        clashing = [_record("gw_access", 0, 10), _record("gw_access", 0, 20)]
        with self.assertRaises(SpectraError):
            indexed.load(self.bundle_path(clashing))
        self.assertEqual(indexed.source_stats(), ())

    def test_a_missing_member_is_refused(self) -> None:
        line = dict(_record("gw_access", 0, 10))
        del line["event_type"]
        with self.assertRaises(SpectraError):
            self.loaded([line])

    def test_an_unknown_member_is_refused(self) -> None:
        """An unknown member would be dropped on the floor, and a column nobody indexed
        is indistinguishable from a member that was never sent."""
        with self.assertRaises(SpectraError):
            self.loaded([dict(_record("gw_access", 0, 10), verdict="ROBUST")])

    def test_a_carriage_return_is_refused_rather_than_swallowed_by_the_parser(self) -> None:
        """`json.loads` treats a trailing CR as whitespace, so a CRLF bundle would load
        and the index would claim to have read a file the encoding law forbids."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "bundle.jsonl"
        body = json.dumps(_record("gw_access", 0, 10), sort_keys=True, separators=(",", ":"))
        path.write_bytes((body + "\r\n").encode("utf-8"))
        with self.assertRaises(SpectraError):
            store.load_bundle(path)

    def test_a_file_whose_last_line_has_no_newline_is_refused(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "bundle.jsonl"
        body = json.dumps(_record("gw_access", 0, 10), sort_keys=True, separators=(",", ":"))
        path.write_bytes(body.encode("utf-8"))
        with self.assertRaises(SpectraError):
            store.load_bundle(path)

    def test_a_bundle_loads_into_a_file_database_as_well_as_into_memory(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        database = pathlib.Path(directory.name) / "index.sqlite3"
        opened = store.load_bundle(self.bundle_path(), database=database)
        self.addCleanup(opened.close)
        self.assertTrue(database.is_file())
        self.assertEqual(
            [s.records for s in opened.source_stats()],
            [s.records for s in self.loaded().source_stats()],
        )


class TestPerSourceQueries(_BundleCase):
    def test_the_record_count_of_each_source_is_the_number_of_its_lines(self) -> None:
        stats = {s.source_id: s.records for s in self.loaded().source_stats()}
        self.assertEqual(stats, {"gw_access": 3, "iam_audit": 2, "net_flow": 2})

    def test_sources_come_back_in_bytewise_order_of_their_ids(self) -> None:
        names = [s.source_id for s in self.loaded().source_stats()]
        self.assertEqual(names, sorted(names, key=lambda name: name.encode("utf-8")))

    def test_first_and_last_are_the_time_extremes_not_the_ends_of_seq_order(self) -> None:
        """They differ exactly when a source's timestamps are out of seq order, which is
        the backdating shape. The store reports the extremes and says nothing about
        whether the order is a contradiction; that verdict is the temporal pass's."""
        stats = {s.source_id: s for s in self.loaded().source_stats()}
        self.assertEqual(stats["gw_access"].first_t_evt_ns, 10 * SECOND)
        self.assertEqual(stats["gw_access"].last_t_evt_ns, 25 * SECOND)
        self.assertEqual(stats["net_flow"].first_t_evt_ns, 40 * SECOND)
        self.assertEqual(stats["net_flow"].last_t_evt_ns, 50 * SECOND)

    def test_a_source_that_is_not_in_the_bundle_has_no_statistics(self) -> None:
        indexed = self.loaded()
        self.assertNotIn("dns_log", [s.source_id for s in indexed.source_stats()])
        self.assertEqual(indexed.gaps("dns_log"), ())
        self.assertEqual(indexed.window("dns_log", 0, 10 ** 18), ())


class TestGaps(_BundleCase):
    def test_a_gap_is_the_delta_between_neighbours_in_seq_order(self) -> None:
        gaps = self.loaded().gaps("gw_access")
        self.assertEqual([g.delta_ns for g in gaps], [10 * SECOND, 5 * SECOND])
        self.assertEqual([(g.prev_seq, g.next_seq) for g in gaps], [(0, 1), (1, 2)])

    def test_a_gap_is_negative_when_a_record_is_recorded_before_its_predecessor(self) -> None:
        """A negative delta is data, not an error: it is what a backdated record looks
        like from here, and hiding it behind an absolute value would erase the evidence."""
        gaps = self.loaded().gaps("net_flow")
        self.assertEqual([g.delta_ns for g in gaps], [-10 * SECOND])
        self.assertEqual(gaps[0].prev_t_evt_ns, 50 * SECOND)
        self.assertEqual(gaps[0].next_t_evt_ns, 40 * SECOND)

    def test_a_source_with_one_record_has_no_gaps(self) -> None:
        """n records give n-1 deltas, so one record gives none - not a zero-length gap."""
        self.assertEqual(self.loaded([_record("iam_audit", 0, 5)]).gaps("iam_audit"), ())

    def test_gaps_name_one_source_and_never_cross_two(self) -> None:
        gaps = self.loaded().gaps("iam_audit")
        self.assertEqual([g.source_id for g in gaps], ["iam_audit"])
        self.assertEqual([g.delta_ns for g in gaps], [95 * SECOND])


class TestLookup(_BundleCase):
    def test_one_record_is_found_by_its_event_id(self) -> None:
        row = self.loaded().event("ev:gw_access-0001")
        self.assertEqual(row.source_id, "gw_access")
        self.assertEqual(row.seq, 1)
        self.assertEqual(row.event_type, "probe")
        self.assertEqual(row.t_evt_ns, 20 * SECOND)

    def test_an_event_id_that_is_not_in_the_bundle_returns_nothing(self) -> None:
        self.assertIsNone(self.loaded().event("ev:gw_access-9999"))

    def test_the_attrs_of_a_record_come_back_sorted_by_key(self) -> None:
        """The fixture writes them in the other order, so this is the sort and not the
        input order arriving intact."""
        row = self.loaded().event("ev:gw_access-0000")
        self.assertEqual(row.attrs, (("principal", "p_ops"), ("service", "sv_idp")))


class TestWindow(_BundleCase):
    def test_the_window_includes_its_lower_bound_and_excludes_its_upper(self) -> None:
        rows = self.loaded().window("gw_access", 10 * SECOND, 20 * SECOND)
        self.assertEqual([r.event_id for r in rows], ["ev:gw_access-0000"])

    def test_the_window_sees_one_source_and_no_other(self) -> None:
        rows = self.loaded().window("iam_audit", 0, 200 * SECOND)
        self.assertEqual({r.source_id for r in rows}, {"iam_audit"})
        self.assertEqual([r.t_evt_ns for r in rows], [5 * SECOND, 100 * SECOND])

    def test_a_window_that_is_not_half_open_is_refused(self) -> None:
        """An empty or inverted window is a caller's mistake, and answering it with an
        empty tuple would make the mistake look like a source that said nothing."""
        indexed = self.loaded()
        for t0, t1 in ((20 * SECOND, 20 * SECOND), (20 * SECOND, 10 * SECOND)):
            with self.subTest(t0=t0, t1=t1):
                with self.assertRaises(SpectraError):
                    indexed.window("gw_access", t0, t1)


class TestDeterminism(_BundleCase):
    def test_the_same_bundle_loaded_twice_answers_identically(self) -> None:
        path = self.bundle_path()
        first = store.load_bundle(path)
        self.addCleanup(first.close)
        second = store.load_bundle(path)
        self.addCleanup(second.close)
        self.assertEqual(first.source_stats(), second.source_stats())
        for name in ("gw_access", "iam_audit", "net_flow"):
            self.assertEqual(first.gaps(name), second.gaps(name))
            self.assertEqual(
                first.window(name, 0, 200 * SECOND), second.window(name, 0, 200 * SECOND)
            )
        self.assertEqual(first.event("ev:net_flow-0001"), second.event("ev:net_flow-0001"))

    def test_the_order_by_is_what_makes_a_query_deterministic(self) -> None:
        """Two stores hold the same records in opposite insertion orders. A SELECT with no
        ORDER BY reads them back in opposite orders - that is the disorder underneath -
        and every query the module exposes carries the clause that absorbs it, so every
        answer is equal across the two. The loader never sorts, exactly so that the first
        assertion below can see the difference the clause is removing."""
        forward = self.loaded()
        backward = self.loaded(tuple(reversed(_BUNDLE)))
        unordered = f"SELECT {store.EVENT_COLUMNS} FROM proj_event"
        self.assertNotIn("ORDER BY", unordered)
        self.assertNotEqual(
            list(forward.connection.execute(unordered)),
            list(backward.connection.execute(unordered)),
        )
        for sql in (
            store.SOURCE_STATS_SQL,
            store.GAPS_SQL,
            store.EVENT_BY_ID_SQL,
            store.WINDOW_SQL,
        ):
            self.assertIn("ORDER BY", sql)
        self.assertEqual(forward.source_stats(), backward.source_stats())
        self.assertEqual(forward.gaps("gw_access"), backward.gaps("gw_access"))
        self.assertEqual(forward.gaps("net_flow"), backward.gaps("net_flow"))
        self.assertEqual(
            forward.window("gw_access", 0, 200 * SECOND),
            backward.window("gw_access", 0, 200 * SECOND),
        )

    def test_no_answer_carries_a_float(self) -> None:
        indexed = self.loaded()
        answers: list[object] = []
        for stat in indexed.source_stats():
            answers.extend([stat.records, stat.first_t_evt_ns, stat.last_t_evt_ns])
        for gap in indexed.gaps("gw_access"):
            answers.extend([gap.prev_t_evt_ns, gap.next_t_evt_ns, gap.delta_ns])
        row = indexed.event("ev:gw_access-0000")
        answers.extend([row.seq, row.t_evt_ns, row.t_ing_ns])
        for answer in answers:
            self.assertNotIsInstance(answer, float)
            self.assertIsInstance(answer, int)


class TestWhatThisDoesNotDo(_BundleCase):
    """The module indexes a bundle. It verifies nothing, and that is pinned here."""

    def test_a_bundle_whose_chain_does_not_join_up_still_loads(self) -> None:
        """`chain_prev` here points at a digest no record in the bundle carries. A
        verifier would reject it; an index has no opinion, and a store that quietly
        rejected it would be a second verifier nobody declared."""
        broken = [
            dict(_record("gw_access", 0, 10, chained=True), chain_prev="b2b256:" + "f" * 64),
            _record("gw_access", 1, 20, chained=True),
        ]
        indexed = self.loaded(broken)
        self.assertEqual(indexed.source_stats()[0].records, 2)

    def test_the_module_offers_no_verification_entry_point(self) -> None:
        for name in store.__all__:
            lowered = name.lower()
            for claim in ("verify", "valid", "tamper", "attest", "prove", "check"):
                self.assertNotIn(claim, lowered, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
