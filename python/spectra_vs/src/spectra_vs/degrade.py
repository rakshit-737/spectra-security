"""S3: the degradation operator. `raw + completeness + seed -> raw.c<NN>.jsonl + manifest`.

DELETE ONLY. The operator removes whole records and never alters one. A degraded record
would change its own event id, and an oracle could then no longer re-link the degraded
bundle to the truth stream by id - which is the one thing the truth stream is for.

NESTING IS THE WHOLE POINT, AND IT IS STRUCTURAL HERE. Two cells of the completeness axis
are comparable only if the lower cell saw strictly less than the higher one. If the 70%
run deleted records the 90% run kept AND kept records the 90% run deleted, the difference
between their verdicts would mix "less telemetry" with "different telemetry", and the
degradation axis would be noise.

The nesting is not asserted after the fact, it is a consequence of the construction: this
module defines ONE total order over the records of each source, depending only on
`(seed, record)` and never on the completeness level, and deletes a PREFIX of it. Prefixes
of a fixed order are nested by definition, so `removed(c1) superset-of removed(c2)`
whenever `c1 < c2` holds for every pair of levels without a pairwise check. A caller that
passes the higher cell's result as `parent` gets the containment re-verified anyway, and
the manifest then cites the parent's hash.

LOSS IS CORRELATED, NOT SPRINKLED. Real telemetry loss is an outage, not an independent
coin flip per record, and the two produce completely different liveness verdicts: uniform
thinning leaves small gaps everywhere while an outage leaves one large gap in one place.
The deletion order is therefore keyed by an outage block first and by the individual
record second, so deleting a prefix removes whole blocks in a seeded block order and
thins only within the last block it reaches.

`OUTAGE_BLOCK_SPAN_NS` IS A CONSTANT, NOT A PARAMETER. It is part of what the operator
is, so it is code rather than an argument: with it as an argument, two runs at the same
completeness and the same seed could differ, and the artifact would not be a pure
function of its hashed inputs. Changing it changes every degraded artifact, which is the
intended cost of changing what an outage means.

LOSS IS STRATIFIED BY SOURCE. Each source loses the same fraction of its own records
rather than a fraction drawn from the pooled population. Pooled deletion at a low
completeness can erase a low-volume source entirely by chance, and a source that vanished
by accident is indistinguishable from a source that was never there.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import SchemaError
from spectra_core.ids import EventId, SourceId

from spectra_vs.gen import RAW_FILE_KIND, RawEvent, raw_to_scf, render_raw
from spectra_vs.scenario import source_key
from spectra_vs.scf import scf_bytes, write_jsonl, write_scf

__all__ = [
    "DEGRADATION_SCHEMA",
    "MANIFEST_KIND",
    "OUTAGE_BLOCK_SPAN_NS",
    "Backdate",
    "Blackout",
    "Completeness",
    "DegradationResult",
    "RemovedRef",
    "backdate",
    "blackout",
    "degrade",
    "write_degraded_raw",
    "write_manifest",
]

#: The schema tag every degradation manifest carries.
DEGRADATION_SCHEMA: Final[str] = "spectra.vs.degradation/1"

#: The digest domain for a manifest, distinct from the raw-file domain.
MANIFEST_KIND: Final[str] = "vsdegmanifest"

#: The span of one correlated outage block: twenty minutes in nanoseconds.
#:
#: Chosen against the slice's two-hour horizon so that the block layer does at the
#: completeness levels the slice runs what it claims to do. Six blocks per source means a
#: thirty-per-cent deletion empties one whole block before it begins thinning a second.
#: A forty-minute block would give only three blocks per source, thirty per cent would not
#: fill even one, and every deletion would degrade into the uniform thinning this layer
#: exists to avoid. A shorter block would empty more blocks but each silence would be
#: shorter, and what the absence operator needs is one CONTIGUOUS non-live run long enough
#: to contain a whole sealed lookback, not a larger number of short ones.
#:
#: CONSEQUENCE FOR THE RULE TABLE, stated here because it crosses a stage boundary: an
#: `absence` lookback window longer than this span cannot lie wholly inside a single
#: emptied block, so its licence condition cannot be met from one outage. A rule that
#: needs a longer lookback needs a longer block, and changing this constant changes every
#: degraded artifact.
#:
#: The grid is anchored at the Unix epoch, not at the scenario epoch, so that the key
#: below is a function of the record alone and needs no scenario to compute.
OUTAGE_BLOCK_SPAN_NS: Final[int] = 1_200_000_000_000

_BLOCK_KIND: Final[str] = "vsdegblk"
_RECORD_KIND: Final[str] = "vsdegrec"


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Completeness:
    """An exact rational in lowest terms. There is no float anywhere on this axis.

    A completeness of 0.7 stored as a float would make the surviving record count depend
    on a rounding mode, and two implementations that disagree by one record produce
    different bundle hashes and therefore incomparable certificates.
    """

    num: int
    den: int

    def __post_init__(self) -> None:
        canon.u32(self.num)
        canon.u32(self.den)
        if self.den == 0:
            raise SchemaError("Completeness: denominator must be positive")
        if not 0 <= self.num <= self.den:
            raise SchemaError(f"Completeness: {self.num}/{self.den} is not in [0, 1]")
        if gcd(self.num, self.den) != 1:
            raise SchemaError(
                f"Completeness: {self.num}/{self.den} is not in lowest terms; "
                "the contract requires a reduced rational"
            )

    @classmethod
    def of(cls, num: int, den: int) -> Completeness:
        """Reduce and construct. The one place a caller's unreduced pair is normalised."""
        if isinstance(num, bool) or isinstance(den, bool):
            raise SchemaError("Completeness.of: a bool is not a rational part")
        if not isinstance(num, int) or not isinstance(den, int):
            raise SchemaError("Completeness.of: numerator and denominator must be ints")
        if den <= 0:
            raise SchemaError("Completeness.of: denominator must be positive")
        divisor = gcd(num, den) or 1
        return cls(num=num // divisor, den=den // divisor)

    @classmethod
    def percent(cls, value: int) -> Completeness:
        """`Completeness.percent(70)` is seven tenths. Integer percent only, never a float."""
        return cls.of(value, 100)

    @property
    def is_identity(self) -> bool:
        """True at completeness 1. The identity spec is what calibration gate B2 requires."""
        return self.num == self.den

    def keep(self, population: int) -> int:
        """How many of `population` records survive: floor, so the target is never exceeded."""
        return (population * self.num) // self.den

    def tag(self) -> str:
        """The `c<NN>` file-name tag.

        Integer percent when the rational is one, because the contract's file name is
        `raw.c<NN>.jsonl` and every cell the slice runs is a whole percent. Anything else
        renders as `<num>_<den>` rather than rounding, because a rounded tag would make
        two different degradations write the same file name.
        """
        if (self.num * 100) % self.den == 0:
            return str((self.num * 100) // self.den)
        return f"{self.num}_{self.den}"

    def to_scf(self) -> dict[str, int]:
        return {"den": self.den, "num": self.num}

    def __lt__(self, other: Completeness) -> bool:
        return self.num * other.den < other.num * self.den


# ---------------------------------------------------------------------------
# The manifest rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemovedRef:
    """One deleted record, named by what survives its deletion: its source, seq and id."""

    source_id: SourceId
    seq: int
    event_id: EventId

    def sort_key(self) -> tuple[bytes, int]:
        return (canon.byte_order_key(source_key(self.source_id)), self.seq)

    def to_scf(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "seq": self.seq,
            "source_id": source_key(self.source_id),
        }


@dataclass(frozen=True, slots=True)
class RewrittenRef:
    """One record whose timestamp an operator rewrote, and both of its ids.

    Both ids travel because a raw event's id is minted from its members: rewriting the
    timestamp mints a new one, and a reader holding only the degraded stream could not
    otherwise say which record of the parent stream this was.
    """

    source_id: str
    seq: int
    was_t_evt_ns: int
    now_t_evt_ns: int
    was_event_id: str
    now_event_id: str

    def sort_key(self) -> tuple[bytes, int]:
        return (canon.byte_order_key(self.source_id), self.seq)

    def to_scf(self) -> dict[str, Any]:
        return {
            "now_event_id": self.now_event_id,
            "now_t_evt_ns": str(self.now_t_evt_ns),
            "seq": self.seq,
            "source_id": self.source_id,
            "was_event_id": self.was_event_id,
            "was_t_evt_ns": str(self.was_t_evt_ns),
        }


@dataclass(frozen=True, slots=True)
class Blackout:
    """WHOLE_SOURCE_BLACKOUT, specification Part II section 61.

    Delete every record emitted by one of `sources` whose event time lies in the half-open
    window `[t0_ns, t1_ns)`, and nothing else. It is a CONTROLLED intervention: it varies
    exactly one thing, which is what a single demonstration needs and random completeness
    does not provide. Random completeness remains the right operator for the degradation
    matrix, where the question is how quality falls off across many cells.

    It is deletion of records that were emitted, not a collector that never produced them;
    the specification keeps those apart (SOURCE-SILENCE is the latter). On a chained source
    the gap is therefore visible in the chain, and liveness may classify it as suppression.
    """

    sources: tuple[str, ...]
    t0_ns: int
    t1_ns: int

    def __post_init__(self) -> None:
        if not self.sources:
            raise SchemaError("Blackout: at least one source is required")
        if tuple(sorted(set(self.sources), key=canon.byte_order_key)) != self.sources:
            raise SchemaError("Blackout: sources must be unique and in bytewise order")
        canon.u64(self.t0_ns)
        canon.u64(self.t1_ns)
        if not self.t0_ns < self.t1_ns:
            raise SchemaError("Blackout: the window must be non-empty, t0 < t1")

    def covers(self, record: RawEvent) -> bool:
        return (
            source_key(record.source_id) in self.sources
            and self.t0_ns <= record.t_evt_ns < self.t1_ns
        )

    def to_scf(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "t0_ns": str(self.t0_ns),
            "t1_ns": str(self.t1_ns),
        }


@dataclass(frozen=True, slots=True)
class Backdate:
    """BACKDATE, specification Part II section 61.4.7: rewrite recorded timestamps.

    Nothing is added, removed or reordered by this operator; one record's `t_evt_ns` moves
    by `shift_ns`, which is negative to move it earlier. The record keeps its `seq`, so
    moving it behind its predecessors contradicts the order its own source recorded - which
    is exactly what the temporal-consistency pass looks for (ADR-0016).

    RESEALING IS NOT DONE HERE, and does not need to be. Degradation runs on RAW records,
    before ingest mints ids and seals chains, so the rewritten record reaches the bundle
    with a chain that verifies and a timestamp that contradicts its neighbours. An operator
    that rewrote a sealed bundle would break the chain instead, and the record would be
    quarantined before any pass could see it.

    `occurrence` selects among the records matching `(source_id, event_type)` in `seq`
    order: 0 is the first, -1 the last. Selecting a record that does not exist is refused
    rather than silently doing nothing, because an intervention that quietly did not happen
    is reported as a cell that found nothing.
    """

    source_id: str
    event_type: str
    shift_ns: int
    occurrence: int = 0

    def __post_init__(self) -> None:
        if not self.source_id or not self.event_type:
            raise SchemaError("Backdate: source_id and event_type are required")
        if self.shift_ns == 0:
            raise SchemaError("Backdate: a zero shift rewrites nothing")
        canon.i64(self.shift_ns)

    def selects(self, record: RawEvent) -> bool:
        return (
            source_key(record.source_id) == self.source_id
            and record.event_type == self.event_type
        )

    def to_scf(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurrence": self.occurrence,
            "shift_ns": str(self.shift_ns),
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class DegradationResult:
    """The surviving stream and the manifest that accounts for every deletion."""

    raw: tuple[RawEvent, ...]
    removed: tuple[RemovedRef, ...]
    completeness: Completeness
    degradation_seed: int
    parent_raw_hash: str
    nested_parent_manifest_hash: str | None = None
    blackout: Blackout | None = None
    backdate: Backdate | None = None
    rewritten: tuple[RewrittenRef, ...] = ()

    @property
    def raw_bytes(self) -> bytes:
        return render_raw(self.raw)

    @property
    def raw_hash(self) -> str:
        return canon.hash_ref(RAW_FILE_KIND, self.raw_bytes)

    @property
    def removed_keys(self) -> frozenset[tuple[str, int]]:
        """The deletion set as `(source_id, seq)` pairs, for a containment check."""
        return frozenset((source_key(r.source_id), r.seq) for r in self.removed)

    def manifest(self) -> dict[str, Any]:
        """Data contract 5 on the wire.

        `nested_parent_manifest_hash` is omitted rather than written as null at the
        highest completeness level, because on this wire absence is how optionality is
        expressed and `null` is never a value.
        """
        document: dict[str, Any] = {
            "completeness": self.completeness.to_scf(),
            "degradation_seed": canon.mask_hex(self.degradation_seed),
            # The operator that actually ran, so a manifest never describes a blackout as
            # a random deletion or the reverse.
            "operators": [_operator_name(self)],
            "parent_raw_hash": self.parent_raw_hash,
            "removed": [r.to_scf() for r in self.removed],
            "schema": DEGRADATION_SCHEMA,
        }
        if self.blackout is not None:
            document["blackout"] = self.blackout.to_scf()
        if self.backdate is not None:
            document["backdate"] = {
                **self.backdate.to_scf(),
                "rewritten": [r.to_scf() for r in self.rewritten],
            }
        if self.nested_parent_manifest_hash is not None:
            document["nested_parent_manifest_hash"] = self.nested_parent_manifest_hash
        return document

    def manifest_hash(self) -> str:
        return canon.hash_ref(MANIFEST_KIND, scf_bytes(self.manifest(), where="manifest"))


# ---------------------------------------------------------------------------
# The operator
# ---------------------------------------------------------------------------


def degrade(
    raw: tuple[RawEvent, ...],
    completeness: Completeness,
    seed: int,
    *,
    parent: DegradationResult | None = None,
) -> DegradationResult:
    """Delete records down to `completeness`, nested with every other level at this seed.

    `parent` is the result at the next HIGHER completeness level. Passing it is optional
    and changes nothing about which records are deleted; it makes the manifest cite the
    parent's hash and it re-verifies the containment that the construction already
    guarantees. The re-verification is kept because a structural guarantee that nobody
    ever checks is a structural guarantee until the day somebody edits the ordering key.
    """
    canon.u64(seed)
    if not isinstance(completeness, Completeness):
        raise SchemaError("degrade: completeness must be a Completeness")

    by_source: dict[str, list[RawEvent]] = {}
    for record in raw:
        by_source.setdefault(source_key(record.source_id), []).append(record)

    removed: list[RemovedRef] = []
    survivors: list[RawEvent] = []
    for name in sorted(by_source, key=canon.byte_order_key):
        records = by_source[name]
        canon.check_strictly_ascending(
            [r.seq for r in sorted(records, key=lambda r: r.seq)],
            lambda k: k,
            where=f"degrade.{name}.seq",
        )
        order = sorted(records, key=lambda r: _deletion_key(r, seed))
        cut = len(records) - completeness.keep(len(records))
        for record in order[:cut]:
            removed.append(
                RemovedRef(
                    source_id=record.source_id, seq=record.seq, event_id=record.event_id
                )
            )
        survivors.extend(order[cut:])

    ordered_removed = tuple(sorted(removed, key=lambda r: r.sort_key()))
    canon.check_strictly_ascending(
        [r.sort_key() for r in ordered_removed], lambda k: k, where="degrade.removed"
    )
    ordered_survivors = tuple(sorted(survivors, key=lambda r: r.sort_key()))
    canon.check_strictly_ascending(
        [r.sort_key() for r in ordered_survivors], lambda k: k, where="degrade.raw"
    )

    parent_hash: str | None = None
    if parent is not None:
        if not completeness < parent.completeness:
            raise SchemaError(
                f"degrade: parent completeness {parent.completeness.num}/{parent.completeness.den} "
                f"must be strictly greater than {completeness.num}/{completeness.den}"
            )
        if parent.degradation_seed != seed:
            raise SchemaError("degrade: a nested chain must hold the degradation seed fixed")
        child_keys = frozenset((source_key(r.source_id), r.seq) for r in ordered_removed)
        if not parent.removed_keys <= child_keys:
            raise SchemaError(
                "degrade: nesting violated; the lower completeness level must delete a "
                "superset of the higher level's deletions"
            )
        parent_hash = parent.manifest_hash()

    return DegradationResult(
        raw=ordered_survivors,
        removed=ordered_removed,
        completeness=completeness,
        degradation_seed=seed,
        parent_raw_hash=canon.hash_ref(RAW_FILE_KIND, render_raw(raw)),
        nested_parent_manifest_hash=parent_hash,
    )


def blackout(raw: tuple[RawEvent, ...], spec: Blackout) -> DegradationResult:
    """Apply WHOLE_SOURCE_BLACKOUT: delete exactly the records `spec` covers.

    Deterministic and seedless - which records a blackout removes is fixed by the window and
    the source list alone, so there is nothing for a seed to choose. `completeness` is
    recorded as 1/1 because no random deletion happens; the blackout is carried separately
    in the manifest, and `operators` names it.
    """
    if not isinstance(spec, Blackout):
        raise SchemaError("blackout: spec must be a Blackout")
    removed = tuple(
        sorted(
            (
                RemovedRef(source_id=r.source_id, seq=r.seq, event_id=r.event_id)
                for r in raw
                if spec.covers(r)
            ),
            key=lambda ref: ref.sort_key(),
        )
    )
    survivors = tuple(
        sorted((r for r in raw if not spec.covers(r)), key=lambda r: r.sort_key())
    )
    canon.check_strictly_ascending(
        [r.sort_key() for r in survivors], lambda k: k, where="blackout.raw"
    )
    return DegradationResult(
        raw=survivors,
        removed=removed,
        completeness=Completeness.of(1, 1),
        degradation_seed=0,
        parent_raw_hash=canon.hash_ref(RAW_FILE_KIND, render_raw(raw)),
        blackout=spec,
    )


def backdate(raw: tuple[RawEvent, ...], spec: Backdate) -> DegradationResult:
    """Apply BACKDATE: move one selected record's timestamp by `spec.shift_ns`.

    Deterministic and seedless - which record moves is fixed by the source, the event type
    and the occurrence, and by nothing else. `completeness` is 1/1 because nothing is
    deleted; the manifest names the operator and records both timestamps and both ids.
    """
    if not isinstance(spec, Backdate):
        raise SchemaError("backdate: spec must be a Backdate")
    matching = sorted(
        (r for r in raw if spec.selects(r)), key=lambda r: (r.seq, str(r.event_id))
    )
    if not matching:
        raise SchemaError(
            f"backdate: no record of {spec.event_type!r} on {spec.source_id!r} to rewrite",
            code="E-DEGRADE-SELECT",
        )
    try:
        target = matching[spec.occurrence]
    except IndexError as exhausted:
        raise SchemaError(
            f"backdate: occurrence {spec.occurrence} of {len(matching)} does not exist",
            code="E-DEGRADE-SELECT",
        ) from exhausted

    moved_to = target.t_evt_ns + spec.shift_ns
    if moved_to < 0:
        raise SchemaError(
            "backdate: the shift moves the record before the epoch",
            code="E-DEGRADE-SELECT",
        )
    moved = RawEvent(
        source_id=target.source_id,
        seq=target.seq,
        t_evt_ns=moved_to,
        event_type=target.event_type,
        attrs=target.attrs,
    )
    survivors = tuple(
        sorted(
            (moved if r is target else r for r in raw),
            key=lambda r: r.sort_key(),
        )
    )
    canon.check_strictly_ascending(
        [r.sort_key() for r in survivors], lambda k: k, where="backdate.raw"
    )
    return DegradationResult(
        raw=survivors,
        removed=(),
        completeness=Completeness.of(1, 1),
        degradation_seed=0,
        parent_raw_hash=canon.hash_ref(RAW_FILE_KIND, render_raw(raw)),
        backdate=spec,
        rewritten=(
            RewrittenRef(
                source_id=source_key(target.source_id),
                seq=target.seq,
                was_t_evt_ns=target.t_evt_ns,
                now_t_evt_ns=moved_to,
                was_event_id=str(target.event_id),
                now_event_id=str(moved.event_id),
            ),
        ),
    )


def _operator_name(result: DegradationResult) -> str:
    """The operator that actually ran, so a manifest never describes one as another."""
    if result.backdate is not None:
        return "backdate"
    if result.blackout is not None:
        return "whole_source_blackout"
    return "delete"


def _deletion_key(record: RawEvent, seed: int) -> tuple[bytes, int, bytes, int]:
    """The one total order deletion walks. Depends on `(seed, record)` and nothing else.

    Independence from the completeness level is what makes nesting a property of the
    construction rather than a post-hoc check. The block digest leads, so a prefix of this
    order removes whole outage blocks in a seeded block order before it thins inside one.
    """
    block = record.t_evt_ns // OUTAGE_BLOCK_SPAN_NS
    block_key = canon.digest(
        _BLOCK_KIND,
        canon.u64(seed) + canon.ascii_text(source_key(record.source_id)) + canon.i64(block),
    )
    record_key = canon.digest(
        _RECORD_KIND, canon.u64(seed) + canon.ascii_text(str(record.event_id))
    )
    return (block_key, block, record_key, record.seq)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def write_degraded_raw(run_dir: Path, result: DegradationResult) -> Path:
    """Write `raw.c<NN>.jsonl` under `run_dir` and return the path."""
    path = Path(run_dir) / f"raw.c{result.completeness.tag()}.jsonl"
    write_jsonl(path, [raw_to_scf(r) for r in result.raw], where="raw")
    return path


def write_manifest(run_dir: Path, result: DegradationResult) -> Path:
    """Write `degradation_manifest.json` under `run_dir` and return the path."""
    path = Path(run_dir) / "degradation_manifest.json"
    write_scf(path, result.manifest(), where="manifest")
    return path
