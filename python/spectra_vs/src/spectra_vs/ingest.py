"""S4 ingest: raw telemetry lines become the hashed bundle.

WHAT THIS STAGE DOES. It reads `raw.c<NN>.jsonl`, validates every line against the
hardened RawEvent shape, mints an `EventId` per surviving record, seals a per-source
integrity chain on every source that declares one, sorts the survivors under the one
declared total order, and emits `bundle.jsonl` plus its digest.

WHY A DROP IS NEVER SILENT. A record that vanishes without a counter is
indistinguishable downstream from a record the sensor never produced. A manufactured
absence becomes a gap, a gap becomes a blind window in S7, a blind window becomes a
licence in S9, and a licence lets a silent attacker step into P_max. A parser bug would
then read as an unsound proof. So every rejected line becomes a `QuarantineRecord` with
a closed reason code from `spectra_core.errors.QuarantineReason`, is counted per source
and per reason, and sets the run flag `quarantined_records` (bit 4), which blocks ROBUST.

WHAT THE CHAIN IS AND IS NOT. `chain_hash` is INGEST'S seal over the records it
received, computed here, not an attestation the source produced. It establishes that the
bundle was not altered after ingest. It establishes nothing whatever about records the
source never handed over: suppression on a source is not detectable by it, and this
package never claims otherwise. That is exactly why S7's R7 calls a sequence gap on a
`sequenced` source unauthenticated.

LABEL PURITY IS AN ABORT, NOT A QUARANTINE. A raw line carrying `label`, `is_attack`,
`scenario`, `truth` or a `__truth*` key means the oracle channel has leaked into the
telemetry channel. Quarantining it would let a run continue on a corpus that has already
been contaminated, so the whole run stops with `EXIT_LABEL_IMPURITY`. No stage from S4
onward may read ground truth; truth is for evaluation only.

DETERMINISM. Nothing here reads a wall clock, an environment variable or a random
source. Input line order never reaches an output: duplicate detection is by content
digest, sequence collisions quarantine every colliding record rather than picking a
winner, and every emitted collection is sorted under a declared total key. Shuffling
`raw.jsonl` must leave `bundle_hash` unchanged.

THE DIGEST. `spectra_core.canon` computes blake2b-256 and labels it `b2b256:`. The
specification names blake3; nothing here writes a blake2b digest behind a blake3 label.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import (
    CanonError,
    LimitError,
    QuarantineReason,
    QuarantineRecord,
    SchemaError,
    SpectraError,
)
from spectra_core.ids import EventId, RecordId, SourceId, check_snake
from spectra_core.model import CanonicalEvent, IntegrityClass, Nanos, Source, check_nanos

from spectra_vs import scf

__all__ = [
    "BUNDLE_FILE_NAME",
    "CHAIN_DIGEST_KIND",
    "EXIT_LABEL_IMPURITY",
    "FORBIDDEN_KEYS",
    "FORBIDDEN_KEY_PREFIX",
    "QUARANTINE_FILE_NAME",
    "RAW_MEMBERS",
    "IngestCounts",
    "IngestLimits",
    "IngestResult",
    "LabelPurityError",
    "chain_genesis",
    "chain_seal",
    "ingest",
    "ingest_bytes",
    "read_bundle",
    "scf_dumps",
    "scf_line",
    "verify_chain",
]


# ---------------------------------------------------------------------------
# SCF-lite
# ---------------------------------------------------------------------------
#
# The encoder lives in `spectra_vs.scf` and there is exactly one of it. These two names
# are re-exported here because S4's callers reach for them on the module that writes the
# bundle; a second implementation would be a second place for the encoding law to drift,
# and two encoders that disagree by one byte are two incompatible bundle hashes.

#: Object keys are ASCII `[a-z0-9_]+`, per the global encoding law.
_KEY_FORM: Final = re.compile(r"\A[a-z0-9_]+\Z")

#: i64 decimal text: no leading `+`, no leading zeros, no `-0`, no exponent, no point.
_I64_TEXT: Final = re.compile(r"\A(?:0|-?[1-9][0-9]*)\Z")


def scf_dumps(obj: object) -> str:
    """The canonical text of one object. See `spectra_vs.scf.scf_dumps`."""
    return scf.scf_dumps(obj)


def scf_line(obj: object) -> bytes:
    """One canonical JSONL line: the SCF-lite octets plus exactly one LF."""
    return scf.scf_bytes(obj)


# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

BUNDLE_FILE_NAME: Final[str] = "bundle.jsonl"

#: This stage's account of what it dropped. The operative stage table names only
#: `bundle.jsonl` for S4; the counts have to survive somewhere or a drop is effectively
#: silent, so they are written beside the bundle under their own schema.
QUARANTINE_FILE_NAME: Final[str] = "ingest_quarantine.json"

#: The exact top-level members of a RawEvent. Nothing else, and none of these absent.
RAW_MEMBERS: Final[frozenset[str]] = frozenset(
    {"attrs", "event_type", "seq", "source_id", "t_evt_ns"}
)

#: Oracle-channel keys. Their presence anywhere in a raw line aborts the run.
FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset({"label", "is_attack", "scenario", "truth"})
FORBIDDEN_KEY_PREFIX: Final[str] = "__truth"

#: Process exit status for a contaminated corpus, per the ingest data contract.
EXIT_LABEL_IMPURITY: Final[int] = 4

#: Domain separator for the per-source integrity chain. Separate from `ev` so that a
#: chain digest and an event digest of the same bytes can never collide across concepts.
CHAIN_DIGEST_KIND: Final[str] = "chain"

#: Closed detail tokens. `QuarantineReason` is the machine-readable reason code and is a
#: closed set owned by the foundation; these are a second machine-readable field that
#: says WHICH hardening rule fired, without inventing a competing code namespace.
_D_INVALID_UTF8: Final = "invalid_utf8"
_D_EMPTY_LINE: Final = "empty_line"
_D_NO_TRAILING_NEWLINE: Final = "no_trailing_newline"
_D_LINE_TOO_LONG: Final = "line_too_long"
_D_RECORD_TOO_LARGE: Final = "record_too_large"
_D_NOT_JSON: Final = "not_json"
_D_NOT_OBJECT: Final = "not_object"
_D_MEMBER_SET: Final = "member_set"
_D_KEY_FORM: Final = "key_form"
_D_DUPLICATE_KEY: Final = "duplicate_key"
_D_RESERIALISE_DIFFERS: Final = "reserialise_differs"
_D_NOT_NFC: Final = "not_nfc"
_D_SOURCE_ID_FORM: Final = "source_id_form"
_D_SOURCE_UNDECLARED: Final = "source_undeclared"
_D_EVENT_TYPE_FORM: Final = "event_type_form"
_D_EVENT_TYPE_TOO_LONG: Final = "event_type_too_long"
_D_EVENT_TYPE_UNDECLARED: Final = "event_type_undeclared"
_D_SEQ_FORM: Final = "seq_form"
_D_SEQ_WIDTH: Final = "seq_width"
_D_SEQ_COLLISION: Final = "seq_collision"
_D_T_EVT_FORM: Final = "t_evt_ns_form"
_D_T_EVT_WIDTH: Final = "t_evt_ns_width"
_D_ATTRS_FORM: Final = "attrs_form"
_D_ATTR_COUNT: Final = "attr_count"
_D_ATTR_KEY_FORM: Final = "attr_key_form"
_D_ATTR_KEY_TOO_LONG: Final = "attr_key_too_long"
_D_ATTR_VALUE_FORM: Final = "attr_value_form"
_D_ATTR_VALUE_TOO_LONG: Final = "attr_value_too_long"
_D_IDENTICAL_LINE: Final = "identical_line"
_D_FLOAT: Final = "float_literal"

#: Every token the stage can emit, so a consumer can assert liveness over the set.
QUARANTINE_DETAILS: Final[frozenset[str]] = frozenset(
    {
        _D_INVALID_UTF8,
        _D_EMPTY_LINE,
        _D_NO_TRAILING_NEWLINE,
        _D_LINE_TOO_LONG,
        _D_RECORD_TOO_LARGE,
        _D_NOT_JSON,
        _D_NOT_OBJECT,
        _D_MEMBER_SET,
        _D_KEY_FORM,
        _D_DUPLICATE_KEY,
        _D_RESERIALISE_DIFFERS,
        _D_NOT_NFC,
        _D_SOURCE_ID_FORM,
        _D_SOURCE_UNDECLARED,
        _D_EVENT_TYPE_FORM,
        _D_EVENT_TYPE_TOO_LONG,
        _D_EVENT_TYPE_UNDECLARED,
        _D_SEQ_FORM,
        _D_SEQ_WIDTH,
        _D_SEQ_COLLISION,
        _D_T_EVT_FORM,
        _D_T_EVT_WIDTH,
        _D_ATTRS_FORM,
        _D_ATTR_COUNT,
        _D_ATTR_KEY_FORM,
        _D_ATTR_KEY_TOO_LONG,
        _D_ATTR_VALUE_FORM,
        _D_ATTR_VALUE_TOO_LONG,
        _D_IDENTICAL_LINE,
        _D_FLOAT,
    }
)


class LabelPurityError(SpectraError):
    """The oracle channel leaked into the telemetry channel. The run stops.

    Carries the offending KEY and never the offending value, so that the ground truth
    the key was smuggling does not travel onward in an exception message.
    """

    CODE = str(QuarantineReason.LABEL_LEAK)

    def __init__(self, detail: str) -> None:
        super().__init__(detail, code=type(self).CODE)
        self.exit_code: Final[int] = EXIT_LABEL_IMPURITY


# ---------------------------------------------------------------------------
# Hardening limits
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IngestLimits:
    """Configurable bounds applied before and after parsing.

    Defaults are deliberately generous relative to the slice's own generator and tight
    relative to what a hostile line could ask for: the point is that an input cannot make
    this stage allocate without bound, not that it constrains well-formed telemetry.

    `max_line_bytes` is checked on the raw byte line BEFORE the JSON parser sees it, so a
    pathological line is never parsed. `max_record_bytes` is checked on the canonical
    re-serialisation AFTER parsing, which bounds the record the bundle would carry.
    """

    max_line_bytes: int = 65_536
    max_record_bytes: int = 65_536
    max_attrs: int = 64
    max_attr_key_bytes: int = 64
    max_attr_value_bytes: int = 4_096
    max_event_type_bytes: int = 64
    max_records: int = 2_000_000

    def __post_init__(self) -> None:
        for name in (
            "max_line_bytes",
            "max_record_bytes",
            "max_attrs",
            "max_attr_key_bytes",
            "max_attr_value_bytes",
            "max_event_type_bytes",
            "max_records",
        ):
            value = getattr(self, name)
            canon.reject_float(value, where=f"IngestLimits.{name}")
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SchemaError(f"IngestLimits.{name} must be a positive int, got {value!r}")


DEFAULT_LIMITS: Final[IngestLimits] = IngestLimits()


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IngestCounts:
    """What S4 saw, kept and dropped. Every map is a sorted tuple, never a dict.

    A dict here would put insertion order into the manifest, and the manifest is compared
    byte for byte across two fresh-process runs.
    """

    lines_read: int
    records_bundled: int
    records_quarantined: int
    by_reason: tuple[tuple[str, int], ...]
    by_source_bundled: tuple[tuple[str, int], ...]
    by_source_quarantined: tuple[tuple[str, int], ...]

    def as_obj(self) -> dict[str, Any]:
        """The SCF-lite shape. Sorted arrays of records, never data-dependent keys."""
        return {
            "by_reason": [{"count": c, "reason": r} for r, c in self.by_reason],
            "by_source_bundled": [{"count": c, "source_id": s} for s, c in self.by_source_bundled],
            "by_source_quarantined": [
                {"count": c, "source_id": s} for s, c in self.by_source_quarantined
            ],
            "lines_read": self.lines_read,
            "records_bundled": self.records_bundled,
            "records_quarantined": self.records_quarantined,
        }


@dataclass(frozen=True, slots=True)
class IngestResult:
    """The sealed bundle, its digest, and the full account of what did not reach it."""

    events: tuple[CanonicalEvent, ...]
    bundle_bytes: bytes
    bundle_hash: str
    quarantined: tuple[QuarantineRecord, ...]
    counts: IngestCounts

    @property
    def quarantined_records(self) -> bool:
        """Run flag bit 4. True whenever anything was dropped; blocks ROBUST."""
        return bool(self.quarantined)

    def quarantine_report_obj(self) -> dict[str, Any]:
        """The canonical object written to `ingest_quarantine.json`."""
        rows: list[dict[str, Any]] = []
        for record in self.quarantined:
            row: dict[str, Any] = {
                "detail": record.detail,
                "reason": str(record.reason),
                "source_id": record.source_id,
            }
            if record.record_id is not None:
                row["record_id"] = record.record_id
            rows.append(row)
        return {
            "bundle_hash": self.bundle_hash,
            "counts": self.counts.as_obj(),
            "quarantined": rows,
            "quarantined_records": self.quarantined_records,
            "schema": "spectra.vs.ingest_quarantine/1",
        }

    def write(self, run_dir: Path | str) -> tuple[Path, Path]:
        """Write `bundle.jsonl` and `ingest_quarantine.json`; return both paths."""
        directory = Path(run_dir)
        directory.mkdir(parents=True, exist_ok=True)
        bundle_path = directory / BUNDLE_FILE_NAME
        bundle_path.write_bytes(self.bundle_bytes)
        quarantine_path = directory / QUARANTINE_FILE_NAME
        quarantine_path.write_bytes(scf_line(self.quarantine_report_obj()))
        return (bundle_path, quarantine_path)


# ---------------------------------------------------------------------------
# The per-source integrity chain
# ---------------------------------------------------------------------------


def chain_genesis(source_id: SourceId) -> str:
    """The `chain_prev` of a source's first record.

    The data contract says the genesis is the digest of the source id's bytes. It is
    computed here through the foundation's domain-separated construction over the
    length-prefixed id, so the genesis of one source can never be the body of another
    source's record digest.
    """
    return canon.hash_ref(CHAIN_DIGEST_KIND, canon.ascii_text(str(source_id)))


def chain_seal(event: CanonicalEvent, chain_prev: str) -> str:
    """The `chain_hash` of one record, given its predecessor's.

    PREIMAGE, in this fixed order and nothing else: the 32 raw octets of `chain_prev`,
    then `event_id`, then the event-id preimage itself (attrs, event_type, seq,
    source_id, t_evt_ns), then `t_ing_ns`.

    Every field in that preimage is present in `bundle.jsonl`, which is the property that
    matters: a reader holding only the bundle can recompute the whole chain, re-typing
    the bare `source_id` the file carries into its `src:` form first. `record_id` is
    deliberately excluded for exactly that reason - it is retained in memory but is not a
    member of the bundle record, so sealing it in would make the chain unrecomputable
    from the published artifact.
    """
    payload = b"".join(
        (
            canon.parse_hash_ref(chain_prev),
            canon.ascii_text(str(event.event_id)),
            event.identity_bytes(),
            canon.i64(event.t_ing_ns),
        )
    )
    return canon.hash_ref(CHAIN_DIGEST_KIND, payload)


def verify_chain(events: Sequence[CanonicalEvent]) -> tuple[EventId, ...]:
    """Recompute every chain link over an already-ordered bundle slice of ONE source.

    Returns the event ids whose recorded `chain_hash` does not recompute, in the order
    encountered, so S7 can name a first bad link. An empty result means every link
    recomputed; it does NOT mean the source emitted every record it should have, and this
    function's result must never be rendered as though it did.
    """
    bad: list[EventId] = []
    previous: str | None = None
    for event in events:
        if event.chain_hash is None:
            continue
        expected_prev = chain_genesis(event.source_id) if previous is None else previous
        if event.chain_prev != expected_prev or event.chain_hash != chain_seal(
            event, event.chain_prev
        ):
            bad.append(event.event_id)
        previous = event.chain_hash
    return tuple(bad)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class _FloatLiteral(Exception):
    """A float, NaN or Infinity appeared in a number position."""


class _DuplicateKey(Exception):
    """A JSON object carried the same key twice."""


def _reject_float(_text: str) -> float:
    raise _FloatLiteral


def _reject_constant(_text: str) -> float:
    raise _FloatLiteral


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise _DuplicateKey(key)
        seen.add(key)
    return dict(pairs)


def _loads(text: str) -> Any:
    return json.loads(
        text,
        parse_float=_reject_float,
        parse_constant=_reject_constant,
        object_pairs_hook=_pairs_hook,
    )


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One line that passed every per-line check, before cross-record checks run."""

    record_id: RecordId
    source_id: SourceId
    seq: int
    event_type: str
    t_evt_ns: Nanos
    attrs: tuple[tuple[str, str], ...]


def _forbidden_key(key: str) -> bool:
    return key in FORBIDDEN_KEYS or key.startswith(FORBIDDEN_KEY_PREFIX)


def _scan_bytes_for_labels(line: bytes) -> str | None:
    """Best-effort label scan for a line too long to parse.

    A line rejected before the parser runs still has to be checked for contamination, and
    the only tool left is a byte scan. It can false-positive on an attribute VALUE that
    happens to contain the token, and a false positive aborts the run. That is the
    intended asymmetry: an over-long line that also looks like it carries ground truth is
    not something to continue past.
    """
    for key in sorted(FORBIDDEN_KEYS):
        if b'"' + key.encode("ascii") + b'"' in line:
            return key
    if b'"' + FORBIDDEN_KEY_PREFIX.encode("ascii") in line:
        return FORBIDDEN_KEY_PREFIX + "*"
    return None


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------


def ingest(
    raw_path: Path | str,
    sources: Sequence[Source],
    *,
    limits: IngestLimits = DEFAULT_LIMITS,
    ingest_time_ns: int | None = None,
) -> IngestResult:
    """Read `raw_path` and produce the sealed bundle. See `ingest_bytes`."""
    return ingest_bytes(
        Path(raw_path).read_bytes(),
        sources,
        limits=limits,
        ingest_time_ns=ingest_time_ns,
    )


def ingest_bytes(
    raw: bytes,
    sources: Sequence[Source],
    *,
    limits: IngestLimits = DEFAULT_LIMITS,
    ingest_time_ns: int | None = None,
) -> IngestResult:
    """Ingest raw JSONL bytes.

    `ingest_time_ns` is the value written to every record's `t_ing_ns`. It defaults to
    each record's own `t_evt_ns`, because no stage may read a wall clock and because the
    bundle must be a pure function of its hashed inputs: a real ingestion instant would
    differ between two runs that are required to be byte-identical. A caller replaying a
    historical ingest may pin an explicit integer instead. `t_ing_ns` never enters an
    `EventId`, so this choice cannot shift a record's identity.

    Raises `LabelPurityError` on a contaminated line and `LimitError` when the input
    exceeds `limits.max_records`; truncating instead would manufacture the exact silent
    absence this stage exists to prevent.
    """
    declared = _declared_sources(sources)
    if ingest_time_ns is not None:
        check_nanos(ingest_time_ns, where="ingest_bytes.ingest_time_ns")

    lines = _split_lines(raw)
    if len(lines) > limits.max_records:
        raise LimitError(
            f"ingest: {len(lines)} lines exceeds max_records {limits.max_records}; "
            "truncating would manufacture a silent absence",
            code="E-LIMIT-COUNT",
        )

    quarantined: list[QuarantineRecord] = []
    candidates: list[_Candidate] = []
    lines_read = 0

    for line, has_newline in lines:
        lines_read += 1
        candidate = _ingest_one(
            line,
            has_newline=has_newline,
            declared=declared,
            limits=limits,
            quarantined=quarantined,
        )
        if candidate is not None:
            candidates.append(candidate)

    kept = _drop_cross_record_collisions(candidates, quarantined)
    events = _seal(kept, declared, ingest_time_ns)
    bundle_bytes = b"".join(scf_line(_bundle_obj(event)) for event in events)

    return IngestResult(
        events=events,
        bundle_bytes=bundle_bytes,
        bundle_hash=canon.hash_ref("bn", bundle_bytes),
        quarantined=_sorted_quarantine(quarantined),
        counts=_counts(lines_read, events, quarantined),
    )


def _declared_sources(sources: Sequence[Source]) -> dict[str, Source]:
    """Index the declared sources by bare snake, rejecting a duplicate declaration."""
    table: dict[str, Source] = {}
    for source in sources:
        if not isinstance(source, Source):
            raise SchemaError(f"ingest: sources must be model.Source, got {type(source).__name__}")
        snake = source.source_id.snake
        if snake in table:
            raise SchemaError(f"ingest: source {snake!r} is declared twice")
        table[snake] = source
    return table


def _split_lines(raw: bytes) -> tuple[tuple[bytes, bool], ...]:
    """Split on LF, reporting per line whether it was terminated by one.

    A final line without its LF is reported rather than silently accepted, because the
    encoding law requires exactly one trailing LF and a truncated write is exactly how a
    partial record reaches an ingest unnoticed.
    """
    if not raw:
        return ()
    parts = raw.split(b"\n")
    terminated = parts[-1] == b""
    if terminated:
        parts = parts[:-1]
    out: list[tuple[bytes, bool]] = []
    for index, part in enumerate(parts):
        is_last = index == len(parts) - 1
        out.append((part, terminated or not is_last))
    return tuple(out)


def _quarantine(
    quarantined: list[QuarantineRecord],
    reason: QuarantineReason,
    detail: str,
    *,
    line: bytes,
    source_id: str = "",
) -> None:
    """Record one drop. `record_id` is the digest of the exact pre-parse bytes.

    Digesting the received bytes even when they could not be parsed is what keeps the
    quarantine list permutation-invariant: two shuffles of the same file produce the same
    set of records with the same ids, so the account of what was dropped is itself a pure
    function of the input.
    """
    quarantined.append(
        QuarantineRecord(
            reason=reason,
            source_id=source_id,
            record_id=str(RecordId.mint(line)),
            detail=detail,
        )
    )


def _ingest_one(
    line: bytes,
    *,
    has_newline: bool,
    declared: Mapping[str, Source],
    limits: IngestLimits,
    quarantined: list[QuarantineRecord],
) -> _Candidate | None:
    """Validate one raw line. Returns a candidate, or None having quarantined it."""
    if not has_newline:
        _quarantine(quarantined, QuarantineReason.NONCANONICAL, _D_NO_TRAILING_NEWLINE, line=line)
        return None
    if line == b"":
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_EMPTY_LINE, line=line)
        return None
    if len(line) > limits.max_line_bytes:
        leaked = _scan_bytes_for_labels(line)
        if leaked is not None:
            raise LabelPurityError(
                f"raw line over max_line_bytes carries the oracle-channel key {leaked!r}"
            )
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_LINE_TOO_LONG, line=line)
        return None

    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_INVALID_UTF8, line=line)
        return None

    try:
        parsed = _loads(text)
    except _FloatLiteral:
        _quarantine(quarantined, QuarantineReason.FLOAT_PRESENT, _D_FLOAT, line=line)
        return None
    except _DuplicateKey:
        _quarantine(quarantined, QuarantineReason.NONCANONICAL, _D_DUPLICATE_KEY, line=line)
        return None
    except (ValueError, RecursionError):
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_NOT_JSON, line=line)
        return None

    if not isinstance(parsed, dict):
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_NOT_OBJECT, line=line)
        return None

    # Label purity runs before every other check on a parsed line, so a contaminated
    # record cannot hide behind a shape violation that would merely quarantine it.
    _assert_label_pure(parsed)

    if set(parsed) != RAW_MEMBERS:
        _quarantine(quarantined, QuarantineReason.UNPARSEABLE, _D_MEMBER_SET, line=line)
        return None

    raw_source = parsed["source_id"]
    if not isinstance(raw_source, str):
        _quarantine(quarantined, QuarantineReason.UNKNOWN_SOURCE, _D_SOURCE_ID_FORM, line=line)
        return None
    try:
        check_snake(raw_source, where="raw.source_id")
    except SpectraError:
        _quarantine(quarantined, QuarantineReason.UNKNOWN_SOURCE, _D_SOURCE_ID_FORM, line=line)
        return None
    source = declared.get(raw_source)
    if source is None:
        _quarantine(
            quarantined,
            QuarantineReason.UNKNOWN_SOURCE,
            _D_SOURCE_UNDECLARED,
            line=line,
            source_id=raw_source,
        )
        return None

    # From here the source id is a declared snake, so it is safe to carry into the
    # quarantine record's sort key and into an artifact.
    def drop(reason: QuarantineReason, detail: str) -> None:
        _quarantine(quarantined, reason, detail, line=line, source_id=raw_source)

    event_type = parsed["event_type"]
    if not isinstance(event_type, str) or event_type == "":
        drop(QuarantineReason.UNKNOWN_EVENT_TYPE, _D_EVENT_TYPE_FORM)
        return None
    if len(event_type.encode("utf-8")) > limits.max_event_type_bytes:
        drop(QuarantineReason.UNKNOWN_EVENT_TYPE, _D_EVENT_TYPE_TOO_LONG)
        return None
    try:
        if canon.nfc(event_type) != event_type:
            drop(QuarantineReason.NONCANONICAL, _D_NOT_NFC)
            return None
    except CanonError:
        drop(QuarantineReason.UNKNOWN_EVENT_TYPE, _D_EVENT_TYPE_FORM)
        return None
    if event_type not in source.emits_event_types:
        drop(QuarantineReason.UNKNOWN_EVENT_TYPE, _D_EVENT_TYPE_UNDECLARED)
        return None

    seq = parsed["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int):
        drop(QuarantineReason.UNPARSEABLE, _D_SEQ_FORM)
        return None
    if not 0 <= seq < (1 << 32):
        drop(QuarantineReason.UNPARSEABLE, _D_SEQ_WIDTH)
        return None

    raw_t = parsed["t_evt_ns"]
    if not isinstance(raw_t, str) or _I64_TEXT.match(raw_t) is None:
        drop(QuarantineReason.UNPARSEABLE, _D_T_EVT_FORM)
        return None
    t_evt_ns = int(raw_t)
    if not -(1 << 63) <= t_evt_ns < (1 << 63):
        drop(QuarantineReason.ARITH_SATURATION, _D_T_EVT_WIDTH)
        return None

    attrs_obj = parsed["attrs"]
    if not isinstance(attrs_obj, dict):
        drop(QuarantineReason.UNPARSEABLE, _D_ATTRS_FORM)
        return None
    if len(attrs_obj) > limits.max_attrs:
        drop(QuarantineReason.UNPARSEABLE, _D_ATTR_COUNT)
        return None
    for key, value in attrs_obj.items():
        if _KEY_FORM.match(key) is None:
            drop(QuarantineReason.UNPARSEABLE, _D_ATTR_KEY_FORM)
            return None
        if len(key.encode("ascii")) > limits.max_attr_key_bytes:
            drop(QuarantineReason.UNPARSEABLE, _D_ATTR_KEY_TOO_LONG)
            return None
        if not isinstance(value, str):
            drop(QuarantineReason.UNPARSEABLE, _D_ATTR_VALUE_FORM)
            return None
        if len(value.encode("utf-8")) > limits.max_attr_value_bytes:
            drop(QuarantineReason.UNPARSEABLE, _D_ATTR_VALUE_TOO_LONG)
            return None
        try:
            if canon.nfc(value) != value:
                drop(QuarantineReason.NONCANONICAL, _D_NOT_NFC)
                return None
        except CanonError:
            drop(QuarantineReason.UNPARSEABLE, _D_ATTR_VALUE_FORM)
            return None

    # Canonicality is checked LAST, so that a record with a specific defect is reported
    # under that defect rather than under the catch-all "this does not re-serialise".
    # The encoder is reached only by a record whose every field already validated, so the
    # CanonError arm below is a backstop against the two checks drifting apart.
    try:
        reserialised = scf_dumps(parsed).encode("utf-8")
    except (CanonError, SchemaError):
        drop(QuarantineReason.NONCANONICAL, _D_KEY_FORM)
        return None
    if len(reserialised) > limits.max_record_bytes:
        drop(QuarantineReason.UNPARSEABLE, _D_RECORD_TOO_LARGE)
        return None
    if reserialised != line:
        drop(QuarantineReason.NONCANONICAL, _D_RESERIALISE_DIFFERS)
        return None

    return _Candidate(
        record_id=RecordId.mint(line),
        source_id=SourceId.of(raw_source),
        seq=seq,
        event_type=event_type,
        t_evt_ns=t_evt_ns,
        attrs=tuple(sorted(attrs_obj.items(), key=lambda kv: canon.byte_order_key(kv[0]))),
    )


def _assert_label_pure(parsed: Mapping[str, Any]) -> None:
    """Abort on an oracle-channel key at the top level or inside `attrs`."""
    for key in sorted(parsed):
        if _forbidden_key(key):
            raise LabelPurityError(f"raw record carries the oracle-channel key {key!r}")
    attrs = parsed.get("attrs")
    if isinstance(attrs, dict):
        for key in sorted(attrs):
            if isinstance(key, str) and _forbidden_key(key):
                raise LabelPurityError(f"raw record attrs carry the oracle-channel key {key!r}")


def _drop_cross_record_collisions(
    candidates: Sequence[_Candidate], quarantined: list[QuarantineRecord]
) -> tuple[_Candidate, ...]:
    """Resolve duplicates and sequence collisions without consulting input order.

    An identical line appearing twice is one record repeated: the copies are byte-equal,
    so keeping one of them is well defined and the extras are counted as
    `Q_DUPLICATE_RECORD`.

    Two DIFFERENT records claiming the same `(source_id, seq)` is a sequence collision,
    and BOTH are quarantined as `Q_SEQ_REGRESSION`. Keeping either would be a choice made
    by file position, and a choice made by file position is a determinism defect; keeping
    both would publish a source whose sequence numbering is not a key. Note that this is
    the only honest reading of a regression here, since after degradation `seq` is sparse
    and the file carries no authoritative per-source order to go backwards in.
    """
    by_record: dict[str, list[_Candidate]] = {}
    for candidate in candidates:
        by_record.setdefault(str(candidate.record_id), []).append(candidate)

    unique: list[_Candidate] = []
    for record_id in sorted(by_record):
        group = by_record[record_id]
        unique.append(group[0])
        for extra in group[1:]:
            quarantined.append(
                QuarantineRecord(
                    reason=QuarantineReason.DUPLICATE_RECORD,
                    source_id=extra.source_id.snake,
                    record_id=record_id,
                    detail=_D_IDENTICAL_LINE,
                )
            )

    by_seq: dict[tuple[str, int], list[_Candidate]] = {}
    for candidate in unique:
        by_seq.setdefault((candidate.source_id.snake, candidate.seq), []).append(candidate)

    kept: list[_Candidate] = []
    for key in sorted(by_seq):
        group = by_seq[key]
        if len(group) == 1:
            kept.append(group[0])
            continue
        for colliding in group:
            quarantined.append(
                QuarantineRecord(
                    reason=QuarantineReason.SEQ_REGRESSION,
                    source_id=colliding.source_id.snake,
                    record_id=str(colliding.record_id),
                    detail=_D_SEQ_COLLISION,
                )
            )
    return tuple(kept)


def _seal(
    candidates: Sequence[_Candidate],
    declared: Mapping[str, Source],
    ingest_time_ns: int | None,
) -> tuple[CanonicalEvent, ...]:
    """Mint event ids, seal chains per source, and return the bundle in file order."""
    unsealed: list[CanonicalEvent] = []
    for candidate in candidates:
        t_ing_ns = candidate.t_evt_ns if ingest_time_ns is None else ingest_time_ns
        payload = b"".join(
            (
                canon.pairs(candidate.attrs),
                canon.utf8_text(candidate.event_type),
                canon.u32(candidate.seq),
                canon.ascii_text(str(candidate.source_id)),
                canon.i64(candidate.t_evt_ns),
            )
        )
        event = CanonicalEvent(
            event_id=EventId.mint(payload),
            record_id=candidate.record_id,
            source_id=candidate.source_id,
            seq=candidate.seq,
            event_type=candidate.event_type,
            t_evt_ns=candidate.t_evt_ns,
            t_ing_ns=t_ing_ns,
            attrs=candidate.attrs,
        )
        if not event.verify_id():
            raise SchemaError(
                "ingest: the event-id preimage built here disagrees with "
                "CanonicalEvent.identity_bytes"
            )
        unsealed.append(event)

    unsealed.sort(key=lambda event: event.sort_key())

    previous: dict[str, str] = {}
    sealed: list[CanonicalEvent] = []
    for event in unsealed:
        source = declared[event.source_id.snake]
        if source.integrity_class is IntegrityClass.NONE:
            sealed.append(event)
            continue
        snake = event.source_id.snake
        last = previous.get(snake)
        chain_prev = chain_genesis(event.source_id) if last is None else last
        linked = CanonicalEvent(
            event_id=event.event_id,
            record_id=event.record_id,
            source_id=event.source_id,
            seq=event.seq,
            event_type=event.event_type,
            t_evt_ns=event.t_evt_ns,
            t_ing_ns=event.t_ing_ns,
            attrs=event.attrs,
            chain_hash=chain_seal(event, chain_prev),
            chain_prev=chain_prev,
        )
        previous[snake] = chain_seal(event, chain_prev)
        sealed.append(linked)

    canon.check_strictly_ascending(
        sealed, lambda event: event.sort_key(), where="ingest: bundle order"
    )
    return tuple(sealed)


def _bundle_obj(event: CanonicalEvent) -> dict[str, Any]:
    """The BundleRecord members, exactly as the data contract enumerates them.

    `record_id` is absent on purpose: the contract lists the record's members and does
    not include it, and adding one would change `bundle_hash`, which a certificate pins.

    `source_id` is written BARE, as the contract spells it on every wire. Section 57.2
    types the same value as `src:<snake>` in memory, and the digest preimages of both
    `event_id` and `chain_hash` are taken over that typed form, so a reader recomputing
    either from this file re-types the value first. Both spellings denote one value; the
    translation happens at this boundary and nowhere else.
    """
    obj: dict[str, Any] = {
        "attrs": {key: value for key, value in event.attrs},
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "seq": event.seq,
        "source_id": event.source_id.snake,
        "t_evt_ns": str(event.t_evt_ns),
        "t_ing_ns": str(event.t_ing_ns),
    }
    if event.chain_hash is not None and event.chain_prev is not None:
        obj["chain_hash"] = event.chain_hash
        obj["chain_prev"] = event.chain_prev
    return obj


def _sorted_quarantine(records: Iterable[QuarantineRecord]) -> tuple[QuarantineRecord, ...]:
    """Total order over quarantine records, extended past `sort_key` with `detail`.

    `QuarantineRecord.sort_key` can tie on two drops that differ only in which hardening
    rule fired, and a tie would let Python's stable sort put input order into the
    artifact. The extension closes that.
    """
    return tuple(
        sorted(
            records,
            key=lambda record: (
                canon.byte_order_key(record.source_id),
                canon.byte_order_key(record.record_id or ""),
                canon.byte_order_key(str(record.reason)),
                canon.byte_order_key(record.detail),
            ),
        )
    )


def _counts(
    lines_read: int,
    events: Sequence[CanonicalEvent],
    quarantined: Sequence[QuarantineRecord],
) -> IngestCounts:
    by_reason: dict[str, int] = {}
    by_source_quarantined: dict[str, int] = {}
    for record in quarantined:
        by_reason[str(record.reason)] = by_reason.get(str(record.reason), 0) + 1
        key = record.source_id
        by_source_quarantined[key] = by_source_quarantined.get(key, 0) + 1
    by_source_bundled: dict[str, int] = {}
    for event in events:
        key = event.source_id.snake
        by_source_bundled[key] = by_source_bundled.get(key, 0) + 1
    return IngestCounts(
        lines_read=lines_read,
        records_bundled=len(events),
        records_quarantined=len(quarantined),
        by_reason=_sorted_counts(by_reason),
        by_source_bundled=_sorted_counts(by_source_bundled),
        by_source_quarantined=_sorted_counts(by_source_quarantined),
    )


def _sorted_counts(table: Mapping[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple((key, table[key]) for key in sorted(table, key=canon.byte_order_key))


# ---------------------------------------------------------------------------
# Reading the bundle back
# ---------------------------------------------------------------------------


def read_bundle(path: Path | str) -> tuple[CanonicalEvent, ...]:
    """Parse `bundle.jsonl` back into `CanonicalEvent`s, verifying it in one scan.

    Strict where ingest is forgiving, and deliberately so: `raw.jsonl` arrives from a
    degraded channel and a bad line there is quarantined, whereas `bundle.jsonl` is this
    pipeline's own canonical artifact and any deviation in it is a defect, not telemetry.
    Nothing is repaired, sorted, defaulted or inferred; the first deviation raises.
    """
    raw = Path(path).read_bytes()
    events: list[CanonicalEvent] = []
    for line, has_newline in _split_lines(raw):
        if not has_newline:
            raise CanonError("read_bundle: final line has no LF", code="E-CANON-TRAILING")
        obj = _loads(line.decode("utf-8"))
        if not isinstance(obj, dict):
            raise SchemaError("read_bundle: a line is not a JSON object")
        if scf_dumps(obj).encode("utf-8") != line:
            raise CanonError("read_bundle: a line is not canonical", code="E-CANON-FORM")
        events.append(_event_from_obj(obj, line))
    canon.check_strictly_ascending(
        events, lambda event: event.sort_key(), where="read_bundle: bundle order"
    )
    return tuple(events)


def _event_from_obj(obj: Mapping[str, Any], line: bytes) -> CanonicalEvent:
    required = {"attrs", "event_id", "event_type", "seq", "source_id", "t_evt_ns", "t_ing_ns"}
    optional = {"chain_hash", "chain_prev"}
    present = set(obj)
    if not required <= present or not present <= (required | optional):
        raise SchemaError(f"read_bundle: unexpected member set {sorted(present)}")
    attrs = obj["attrs"]
    if not isinstance(attrs, dict):
        raise SchemaError("read_bundle: attrs is not an object")
    event = CanonicalEvent(
        event_id=EventId(obj["event_id"]),
        record_id=RecordId.mint(line),
        source_id=SourceId.of(obj["source_id"]),
        seq=obj["seq"],
        event_type=obj["event_type"],
        t_evt_ns=int(obj["t_evt_ns"]),
        t_ing_ns=int(obj["t_ing_ns"]),
        attrs=tuple(sorted(attrs.items(), key=lambda kv: canon.byte_order_key(kv[0]))),
        chain_hash=obj.get("chain_hash"),
        chain_prev=obj.get("chain_prev"),
    )
    if not event.verify_id():
        raise SchemaError(f"read_bundle: event_id does not recompute for {obj['event_id']}")
    return event
