"""The event store: a SQLite index over one sealed bundle, and the queries the slice asks.

WHAT THIS IS, said plainly because the milestone it answers to says something stronger.
This module INDEXES a bundle. It does not verify one. It does not walk a chain, recompute
an event id, compare a digest, decide whether a record was tampered with, or form any
opinion about whether the bundle it just read is the bundle anyone else read. Verification
of `bundle.jsonl` is `ingest.read_bundle`'s job and the checker's; an index that also
verified would be a second authority on the same question, and two authorities that can
disagree are worse than one. `chain_hash` and `chain_prev` are carried into columns
because the records carry them, and nothing here follows them.

WHY SQLITE AND NOT POSTGRESQL. Part I 52.5 declares M2's event store in PostgreSQL. Part
II 75.1 item 15 reverts any service dependency on the path to a certificate, and Part II
69.13 RULE P3 forbids the kernel and the checker to link a database client at all. What
M2 actually wanted from a store is the capability to ask questions of an ingested run;
what it must not introduce is something to run. `sqlite3` is in the standard library,
addresses a file or `:memory:`, and is imported by this module alone - no stage of the
slice pipeline, no kernel path and no checker path imports it. The narrowing is therefore
deliberate: the query capability is delivered, the service is not, and this module is the
only place the difference is recorded.

WHY THE DDL IS NOT IN THIS FILE. The schema is the contract, and it lives in
`db/schema.sql` as SQL. This module reads that file and executes it. A Python copy would
drift from the SQL copy, and the drift would first show up as a query answering about a
column nobody filled. The path is resolved from this file's location, which ties the
module to the repository layout; that is a real cost, accepted because the alternative is
two copies of the contract.

DETERMINISM IS AN ORDER BY, NOT A HABIT. A SQL result set has no order unless the query
declares one. Every query below declares one, including the lookup by primary key where
the clause is redundant, so that "every query in this module is ordered" is a property a
reader checks by reading four constants rather than by reasoning about which keys happen
to be unique. The loader inserts in file order and never sorts: sorting on the way in
would mask a query that forgot its clause, because the table would then happen to hold
the rows in the order the query wanted.

WHAT IS NARROWED RELATIVE TO THE WIRE CONTRACT, stated so the narrowing is not mistaken
for an omission:

  * `t_evt_ns` and `t_ing_ns` are read only as plain non-negative decimal strings. The
    contract's widths are wider, and `int()` is wider still - it accepts underscores,
    surrounding whitespace and a leading plus, each of which would index to a value no
    other stage computes from the same octets. The parser here is narrower on purpose.
  * Times must fit a signed 64-bit integer, which is what a SQLite INTEGER column holds.
    A wider value is refused rather than stored in a form that would compare wrongly.
  * The loader refuses exactly those deviations a JSON parser would otherwise absorb in
    silence: a float anywhere, a repeated object key, and a CR before the line's LF. It
    checks nothing else about canonical form, because checking the rest would be the
    verification this module does not do.

THERE IS NO FLOAT ANYWHERE. Times are integers in Python, in the columns, and in the
deltas SQLite computes between them. The table is declared STRICT so that a REAL reaching
an INTEGER column is an error from the database rather than a rounded value in an index
everything downstream trusts.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import CanonError, SchemaError

from spectra_vs.scf import U32_MAX

__all__ = [
    "EVENT_BY_ID_SQL",
    "EVENT_COLUMNS",
    "GAPS_SQL",
    "SCHEMA_PATH",
    "SOURCE_STATS_SQL",
    "WINDOW_SQL",
    "EventRow",
    "EventStore",
    "Gap",
    "SourceStats",
    "load_bundle",
    "schema_sql",
]

#: The one copy of the schema. Resolved from this file so that a checkout in any
#: directory finds it; a working directory would not survive being run from elsewhere.
SCHEMA_PATH: Final[Path] = Path(__file__).resolve().parents[4] / "db" / "schema.sql"

#: The widest integer a SQLite INTEGER column holds. A time beyond it is refused, not
#: wrapped: a wrapped nanosecond would order before every real one and the window query
#: would answer with a record that is not in the window.
INT64_MAX: Final[int] = (1 << 63) - 1

#: The column list of `proj_event`, written once so the projection and the row reader
#: cannot disagree about position. Ordinary select order, not an ordering of rows.
EVENT_COLUMNS: Final[str] = (
    "event_id, source_id, seq, event_type, t_evt_ns, t_ing_ns, chain_hash, chain_prev, attrs"
)

#: Records, first and last recorded event time, per source. MIN and MAX are the extremes
#: of recorded time and NOT the timestamps of the lowest and highest `seq`; the two differ
#: exactly when a source's timestamps are out of its own recorded order, and deciding
#: whether that is a contradiction belongs to the temporal pass, not to an index.
#: ORDER BY source_id is SQLite's BINARY collation, which compares UTF-8 octets, so it
#: agrees with `canon.byte_order_key` for every source id already in NFC. This module does
#: not normalise, because normalising would make the index disagree with what it indexes.
SOURCE_STATS_SQL: Final[str] = (
    "SELECT source_id, COUNT(*) AS records,"
    " MIN(t_evt_ns) AS first_t_evt_ns, MAX(t_evt_ns) AS last_t_evt_ns"
    " FROM proj_event GROUP BY source_id ORDER BY source_id"
)

#: The deltas between consecutive records of one source IN SEQ ORDER, not in time order.
#: Seq order is the order the source itself recorded, so a negative delta here is a record
#: whose timestamp contradicts that order - which is evidence, and is reported as it is
#: rather than folded into an absolute value that would erase it.
#: The window is ordered by (seq, event_id) rather than by seq alone: a bundle should carry
#: each seq once per source, but this module does not verify that, and a tie broken by
#: nothing is a tie broken by whatever SQLite scanned first.
GAPS_SQL: Final[str] = (
    "SELECT source_id, prev_seq, seq, prev_t_evt_ns, t_evt_ns,"
    " t_evt_ns - prev_t_evt_ns AS delta_ns"
    " FROM ("
    "  SELECT source_id, event_id, seq, t_evt_ns,"
    "   LAG(seq) OVER by_seq AS prev_seq,"
    "   LAG(t_evt_ns) OVER by_seq AS prev_t_evt_ns"
    "  FROM proj_event WHERE source_id = ?"
    "  WINDOW by_seq AS (ORDER BY seq, event_id)"
    " ) WHERE prev_seq IS NOT NULL ORDER BY seq, event_id"
)

#: One record by id. The ORDER BY is redundant under a primary key and is written anyway,
#: so that the "every query here is ordered" property is checkable without first deciding
#: which columns are unique.
EVENT_BY_ID_SQL: Final[str] = (
    f"SELECT {EVENT_COLUMNS} FROM proj_event WHERE event_id = ? ORDER BY event_id"
)

#: One source's records in the half-open window [t0, t1). Half-open because adjacent
#: windows must tile without a record falling into both, which is what a closed upper
#: bound would do at the boundary.
WINDOW_SQL: Final[str] = (
    f"SELECT {EVENT_COLUMNS} FROM proj_event"
    " WHERE source_id = ? AND t_evt_ns >= ? AND t_evt_ns < ?"
    " ORDER BY t_evt_ns, seq, event_id"
)

_INSERT_SQL: Final[str] = (
    f"INSERT INTO proj_event ({EVENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

_REQUIRED: Final[frozenset[str]] = frozenset(
    {"attrs", "event_id", "event_type", "seq", "source_id", "t_evt_ns", "t_ing_ns"}
)
_OPTIONAL: Final[frozenset[str]] = frozenset({"chain_hash", "chain_prev"})

_DIGITS: Final[frozenset[str]] = frozenset("0123456789")


# ---------------------------------------------------------------------------
# The answers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceStats:
    """What one source contributed: how many records, and the extremes of recorded time.

    Frozen and comparable so that two loads of the same bundle can be compared as values.
    `first_t_evt_ns` and `last_t_evt_ns` are MIN and MAX of `t_evt_ns`, which is not the
    same as the first and last record in `seq` order; see `SOURCE_STATS_SQL`.
    """

    source_id: str
    records: int
    first_t_evt_ns: int
    last_t_evt_ns: int


@dataclass(frozen=True, slots=True)
class Gap:
    """One delta between neighbours in `seq` order, carrying both ends that produced it.

    Both timestamps travel with the delta because a delta alone cannot be checked against
    anything: a reader who wants to know WHERE a silence was needs the pair, and a reader
    who computes it again from the pair should get the same number.
    """

    source_id: str
    prev_seq: int
    next_seq: int
    prev_t_evt_ns: int
    next_t_evt_ns: int
    delta_ns: int


@dataclass(frozen=True, slots=True)
class EventRow:
    """One indexed record, as its columns.

    `attrs` is a tuple of key/value pairs in bytewise key order rather than a dict,
    because a dict's order is its insertion order and an index that returned one would be
    handing a caller an order nobody declared. `chain_hash` and `chain_prev` are `None`
    when the line carried no such member; the wire spells absence by omitting a member and
    a column has no way to say that except NULL.
    """

    event_id: str
    source_id: str
    seq: int
    event_type: str
    t_evt_ns: int
    t_ing_ns: int
    chain_hash: str | None
    chain_prev: str | None
    attrs: tuple[tuple[str, Any], ...]


# ---------------------------------------------------------------------------
# The schema
# ---------------------------------------------------------------------------


def schema_sql(path: Path | str | None = None) -> str:
    """Read the DDL. Absence is an error here rather than a fallback to a built-in copy.

    A fallback copy is how two schemas come to exist, and the second one is always the
    one nobody updates.
    """
    located = SCHEMA_PATH if path is None else Path(path)
    if not located.is_file():
        raise SchemaError(f"store: the schema file {located} does not exist")
    return located.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Parsing one line
# ---------------------------------------------------------------------------


def _decimal_ns(value: object, *, where: str) -> int:
    """Parse a nanosecond count written as a plain decimal string.

    Narrower than `int()`, and that is the whole reason it exists: `int()` accepts
    `"1_000"`, `" 12"` and `"+12"`, so a line carrying any of them would be indexed at a
    value that no other stage derives from the same octets, and the disagreement would
    surface as a window query that answers differently from a scan of the file.
    """
    if isinstance(value, bool) or not isinstance(value, str):
        raise SchemaError(
            f"{where}: a time is a decimal string on the wire, not "
            f"{type(value).__name__}; the encoding law admits a bare integer only in a "
            "u32 position",
            code="E-CANON-WIDTH",
        )
    if not value or not _DIGITS.issuperset(value) or (value[0] == "0" and len(value) > 1):
        raise SchemaError(f"{where}: {value!r} is not a plain non-negative decimal string")
    parsed = int(value)
    if parsed > INT64_MAX:
        raise SchemaError(
            f"{where}: {value} exceeds the signed 64-bit range a column holds",
            code="E-CANON-WIDTH",
        )
    return parsed


def _text(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _pairs_or_refuse(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build the object and refuse a repeated key instead of keeping the last one.

    A repeated key is one of the deviations a JSON parser absorbs without a sound: the
    line would index at whichever value came last, and no column would record that another
    value had been sent.
    """
    built: dict[str, Any] = {}
    for key, value in pairs:
        if key in built:
            raise CanonError(f"store: object key {key!r} appears twice in one line")
        built[key] = value
    return built


def _refuse_float(text: str) -> object:
    raise CanonError(
        f"store: {text} is a float, and there is no float anywhere in a bundle",
        code="E-CANON-FLOAT",
    )


def _refuse_constant(text: str) -> object:
    raise CanonError(f"store: {text} is not a JSON value the contract admits")


def _optional_text(obj: dict[str, Any], key: str, *, where: str) -> str | None:
    """A member that may be absent. Absent is `None`; an explicit `null` is refused.

    The wire spells absence by omitting a member and `null` is never a value on it, so
    reading a written `null` as absence would accept a spelling the encoding law does not
    have and would leave no trace that it had been sent.
    """
    if key not in obj:
        return None
    return _text(obj[key], where=f"{where}.{key}")


def _row_from_line(text: str, *, where: str) -> tuple[Any, ...]:
    """Turn one JSONL line into the nine column values, in `EVENT_COLUMNS` order."""
    obj = json.loads(
        text,
        object_pairs_hook=_pairs_or_refuse,
        parse_float=_refuse_float,
        parse_constant=_refuse_constant,
    )
    if not isinstance(obj, dict):
        raise SchemaError(f"{where}: a bundle line is a JSON object, not a bare value")
    present = frozenset(obj)
    if not _REQUIRED <= present:
        raise SchemaError(f"{where}: missing member(s) {sorted(_REQUIRED - present)}")
    if not present <= (_REQUIRED | _OPTIONAL):
        raise SchemaError(
            f"{where}: unknown member(s) {sorted(present - _REQUIRED - _OPTIONAL)}; an "
            "unindexed member is indistinguishable from one that was never sent"
        )

    seq = obj["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq <= U32_MAX:
        raise SchemaError(f"{where}: seq {seq!r} is not a u32")

    attrs = obj["attrs"]
    if not isinstance(attrs, dict):
        raise SchemaError(f"{where}: attrs is not an object")

    return (
        _text(obj["event_id"], where=f"{where}.event_id"),
        _text(obj["source_id"], where=f"{where}.source_id"),
        seq,
        _text(obj["event_type"], where=f"{where}.event_type"),
        _decimal_ns(obj["t_evt_ns"], where=f"{where}.t_evt_ns"),
        _decimal_ns(obj["t_ing_ns"], where=f"{where}.t_ing_ns"),
        _optional_text(obj, "chain_hash", where=where),
        _optional_text(obj, "chain_prev", where=where),
        # Re-serialised, not sliced out of the line: these octets are this table's and
        # nothing may hash them and call the result a digest of anything on the wire.
        json.dumps(attrs, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    )


def _event_from_row(row: tuple[Any, ...]) -> EventRow:
    attrs = json.loads(row[8], object_pairs_hook=_pairs_or_refuse)
    return EventRow(
        event_id=row[0],
        source_id=row[1],
        seq=row[2],
        event_type=row[3],
        t_evt_ns=row[4],
        t_ing_ns=row[5],
        chain_hash=row[6],
        chain_prev=row[7],
        attrs=tuple(sorted(attrs.items(), key=lambda kv: canon.byte_order_key(kv[0]))),
    )


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------


class EventStore:
    """A SQLite database holding one bundle's records, and the queries the slice asks.

    Holds a connection, so it is closed rather than garbage-collected: `close()`, or use
    it as a context manager. It owns no state beyond the connection - every answer is a
    query, so there is no cache that could disagree with the table.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        #: Public on purpose. A caller with a question this module does not answer should
        #: ask SQLite rather than fork the loader; what it asks that way it orders itself.
        self.connection = connection

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def open(
        cls, database: Path | str = ":memory:", *, schema_path: Path | str | None = None
    ) -> EventStore:
        """Open a database and execute the DDL from `db/schema.sql` into it.

        `:memory:` is the default because the common use is one question about one run,
        and a temporary file left behind is a file somebody later mistakes for an
        artifact. A path is accepted for the case where the index outlives the process.
        """
        connection = sqlite3.connect(str(database))
        try:
            connection.executescript(schema_sql(schema_path))
        except Exception:
            connection.close()
            raise
        return cls(connection)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> EventStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- loading ------------------------------------------------------------

    def load(self, path: Path | str) -> int:
        """Index every line of `bundle.jsonl`, in file order, and return how many.

        ONE TRANSACTION, so a bundle that fails on its last line leaves the database as it
        was found. A half-loaded index does not report an error; it reports counts that
        are wrong, which is worse.

        FILE ORDER, never sorted. Sorting here would put the rows in the order the queries
        want and would therefore hide a query that forgot its ORDER BY.
        """
        raw = Path(path).read_bytes()
        if b"\r" in raw:
            raise CanonError(
                "store.load: the file carries a CR; the JSON parser would treat it as "
                "whitespace and the index would claim to have read a file the encoding "
                "law forbids"
            )
        if raw and not raw.endswith(b"\n"):
            raise CanonError("store.load: the final line has no LF", code="E-CANON-TRAILING")

        segments = raw.split(b"\n")
        if segments and segments[-1] == b"":
            segments.pop()
        rows = [
            _row_from_line(segment.decode("utf-8"), where=f"store.load[{index}]")
            for index, segment in enumerate(segments)
        ]
        with self.connection:
            for row in rows:
                try:
                    self.connection.execute(_INSERT_SQL, row)
                except sqlite3.IntegrityError as refused:
                    raise SchemaError(
                        f"store.load: the database refused the row for {row[0]}: "
                        f"{refused}; a record is indexed once and is never replaced, "
                        "because a replacement would make a second load a silent no-op"
                    ) from refused
        return len(rows)

    # -- queries ------------------------------------------------------------

    def source_stats(self) -> tuple[SourceStats, ...]:
        """Records and the extremes of recorded time, one row per source, in id order.

        Only sources with at least one indexed record appear: an index reports what it
        holds, and a source that emitted nothing is a question about a scenario, not
        about a bundle.
        """
        return tuple(
            SourceStats(source_id=row[0], records=row[1], first_t_evt_ns=row[2],
                        last_t_evt_ns=row[3])
            for row in self.connection.execute(SOURCE_STATS_SQL)
        )

    def gaps(self, source_id: str) -> tuple[Gap, ...]:
        """The deltas between consecutive records of one source, in `seq` order.

        `n` records give `n - 1` deltas, so one record gives none - not a zero-length gap,
        which would be a claim about time either side of a single record that no record
        supports. A source that is not in the bundle gives none for the same reason.
        """
        return tuple(
            Gap(source_id=row[0], prev_seq=row[1], next_seq=row[2], prev_t_evt_ns=row[3],
                next_t_evt_ns=row[4], delta_ns=row[5])
            for row in self.connection.execute(GAPS_SQL, (_text(source_id, where="gaps"),))
        )

    def event(self, event_id: str) -> EventRow | None:
        """One record by id, or `None` when the bundle does not carry it.

        `None` rather than an exception: asking whether a bundle holds an id is a
        legitimate question with two legitimate answers, and only one of them is a defect.
        """
        cursor = self.connection.execute(
            EVENT_BY_ID_SQL, (_text(event_id, where="event"),)
        )
        row = cursor.fetchone()
        return None if row is None else _event_from_row(row)

    def window(self, source_id: str, t0_ns: int, t1_ns: int) -> tuple[EventRow, ...]:
        """One source's records with `t0_ns <= t_evt_ns < t1_ns`, in recorded time order.

        An empty or inverted window is refused rather than answered with an empty tuple:
        answered, a caller's mistake would be indistinguishable from a source that said
        nothing in that interval, and the second is a liveness observation.
        """
        for name, bound in (("t0_ns", t0_ns), ("t1_ns", t1_ns)):
            if isinstance(bound, bool) or not isinstance(bound, int):
                raise SchemaError(f"window: {name} is an integer nanosecond count")
            if not 0 <= bound <= INT64_MAX:
                raise SchemaError(f"window: {name}={bound} is outside the indexed range")
        if not t0_ns < t1_ns:
            raise SchemaError(
                f"window: the window must be non-empty and half-open, [{t0_ns}, {t1_ns}) "
                "is not"
            )
        return tuple(
            _event_from_row(row)
            for row in self.connection.execute(
                WINDOW_SQL, (_text(source_id, where="window"), t0_ns, t1_ns)
            )
        )


def load_bundle(
    path: Path | str,
    *,
    database: Path | str = ":memory:",
    schema_path: Path | str | None = None,
) -> EventStore:
    """Open a store and index `path` into it. The one call most callers want."""
    opened = EventStore.open(database, schema_path=schema_path)
    try:
        opened.load(path)
    except Exception:
        opened.close()
        raise
    return opened
