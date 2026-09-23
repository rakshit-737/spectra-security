"""S3: the degradation operator. `raw + completeness + seed -> raw.c<NN>.jsonl + manifest`.

ONE OPERATOR PER CELL. This module holds the small operator catalog the slice implements
from specification Part II section 61: the completeness operator `degrade`, and the
controlled single-variable interventions `blackout`, `backdate`, `strip_identity` and
`chain_forge`. A cell applies exactly one of them, and a result carrying two specs is
refused: a cell that mixed a controlled intervention with random loss, or two controlled
interventions with each other, could not attribute its effect to either. The manifest
always names the operator that actually ran.

DELETE ONLY, AND THAT PARAGRAPH IS ABOUT `degrade`. The completeness operator removes
whole records and never alters one. A degraded record would change its own event id, and
an oracle could then no longer re-link the degraded bundle to the truth stream by id -
which is the one thing the truth stream is for. The interventions that do alter a record
(`backdate`, `strip_identity`) and the one that fabricates records (`chain_forge`)
therefore carry both ids of everything they touch in the manifest, which is what keeps
the re-link possible for them too.

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
    "ChainForge",
    "Completeness",
    "DegradationResult",
    "ForgedRef",
    "RemovedRef",
    "ResealedRef",
    "StripIdentity",
    "StrippedRef",
    "backdate",
    "blackout",
    "chain_forge",
    "degrade",
    "strip_identity",
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
class StrippedRef:
    """One record that lost named attribute keys, the keys it lost, and both of its ids.

    Both ids travel for the same reason they do on a rewrite: a raw event's id is minted
    from its members and `attrs` is one of them, so removing a key mints a new id. A
    reader holding only the degraded stream could not otherwise say which record of the
    parent stream this was.
    """

    source_id: str
    seq: int
    fields: tuple[str, ...]
    was_event_id: str
    now_event_id: str

    def sort_key(self) -> tuple[bytes, int]:
        return (canon.byte_order_key(self.source_id), self.seq)

    def to_scf(self) -> dict[str, Any]:
        return {
            "fields": list(self.fields),
            "now_event_id": self.now_event_id,
            "seq": self.seq,
            "source_id": self.source_id,
            "was_event_id": self.was_event_id,
        }


@dataclass(frozen=True, slots=True)
class ForgedRef:
    """One fabricated line. It has no parent record and it witnesses nothing.

    `fate` and `kind` are the specification's ledger vocabulary (61.7.2): SYNTHETIC, kind
    FORGED, no parent. They are written into the manifest so that a reader counting
    witnesses cannot count a fabrication as an observation - a derivation whose whole
    evidence set is synthetic is a phantom derivation, not support.

    A forged line is this operator's fabrication. It is never attacker activity and the
    specification forbids describing it as one, here or in any other output.
    """

    source_id: str
    seq: int
    t_evt_ns: int
    event_type: str
    event_id: str

    def sort_key(self) -> tuple[bytes, int]:
        return (canon.byte_order_key(self.source_id), self.seq)

    def to_scf(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "fate": "synthetic",
            "kind": "forged",
            "seq": self.seq,
            "source_id": self.source_id,
            "t_evt_ns": str(self.t_evt_ns),
        }


@dataclass(frozen=True, slots=True)
class ResealedRef:
    """One real record whose sequence number the reseal moved, with both seqs and both ids.

    `seq` is a hashed member of a raw event, so renumbering a record mints a new id for it
    even though nothing a reader would call content changed. Both are recorded, because a
    reseal that silently re-identified half a source would make the pre-forgery stream
    uncitable.
    """

    source_id: str
    was_seq: int
    now_seq: int
    was_event_id: str
    now_event_id: str

    def sort_key(self) -> tuple[bytes, int]:
        return (canon.byte_order_key(self.source_id), self.now_seq)

    def to_scf(self) -> dict[str, Any]:
        return {
            "now_event_id": self.now_event_id,
            "now_seq": self.now_seq,
            "source_id": self.source_id,
            "was_event_id": self.was_event_id,
            "was_seq": self.was_seq,
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
class StripIdentity:
    """STRIP-IDENTITY, specification Part II section 61.4.6, mode REMOVE.

    Remove the named attribute keys from every record of `source_id` that carries one, and
    change nothing else. This is how a record survives while the entity it named does not:
    the line is still delivered, still parses, still holds its place in the source's
    sequence, and no longer joins to anything.

    WHAT IT DOES NOT DO. It deletes no record, moves no timestamp, renumbers no sequence
    and touches no other source, so nothing that would make an ABSENCE visible moves: the
    chain still verifies, the numbering is still dense, the inter-arrival profile is
    unchanged. The specification classes this operator OBS-N on every chain class for
    exactly that reason, and an implementation that also dropped the line would be
    measuring deletion while claiming to measure identity loss.

    It does not blank and it does not hash. The specification's BLANK and HASH_OPAQUE modes
    leave a key present with an empty or opaque value, which is a different observable - a
    field that is there and useless rather than a field that is gone - and is a second
    operator rather than a parameter of this one.

    A raw event's id is minted from its members and `attrs` is one of them, so every
    stripped record arrives under a NEW event id. That is stated rather than hidden: the
    manifest carries both ids for every record this operator touches.

    Selecting a source that delivered nothing, or fields no record carries, is refused
    rather than silently doing nothing, because an intervention that quietly did not happen
    is reported downstream as a cell that found nothing.
    """

    source_id: str
    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_id:
            raise SchemaError("StripIdentity: source_id is required")
        if not isinstance(self.fields, tuple):
            raise SchemaError("StripIdentity: fields must be a tuple of attribute keys")
        if not self.fields:
            raise SchemaError("StripIdentity: at least one field is required")
        if any(not isinstance(name, str) or not name for name in self.fields):
            raise SchemaError("StripIdentity: a field name must be a non-empty string")
        if tuple(sorted(set(self.fields), key=canon.byte_order_key)) != self.fields:
            raise SchemaError("StripIdentity: fields must be unique and in bytewise order")

    def selects(self, record: RawEvent) -> bool:
        return source_key(record.source_id) == self.source_id

    def strips(self, record: RawEvent) -> tuple[str, ...]:
        """The named keys this record actually carries, in the spec's declared order.

        The declared order, never the record's and never a set's, so that two records
        carrying the same keys produce identical manifest rows whatever order their attrs
        arrived in.
        """
        if not self.selects(record):
            return ()
        present = frozenset(key for key, _ in record.attrs)
        return tuple(name for name in self.fields if name in present)

    def to_scf(self) -> dict[str, Any]:
        return {"fields": list(self.fields), "source_id": self.source_id}


@dataclass(frozen=True, slots=True)
class ChainForge:
    """CHAIN-FORGE, specification Part II section 61.4.8: fabricate records a chained
    source's integrity chain cannot distinguish from the ones it handed over.

    `count` fabricated records are inserted immediately after the record numbered
    `after_seq` on `source_id`, and every later record of that source is renumbered forward
    by `count`. That renumbering IS the reseal at this layer and it is not a flag: leaving
    the numbering alone would either reuse a sequence number, which ingest quarantines as a
    collision, or leave a hole, which S7 reads as SUPPRESSED on a chained source. Either
    outcome is a forgery that announces itself, and the operator exists to produce one that
    does not.

    WHY THERE IS NOTHING TO RE-HASH HERE, AND WHY THAT IS THE POINT. The chain is INGEST'S
    seal, computed after degradation over the records ingest received (`ingest.chain_seal`
    with `ingest.chain_genesis`). A forgery inserted before ingest is therefore sealed by
    ingest along with everything else, and the chain verifies link for link over a bundle
    that contains fabrications. `chain_hash` establishes that the bundle was not altered
    AFTER ingest and nothing whatever about what the source actually emitted. This operator
    makes that limit demonstrable instead of asserted.

    WHAT IT DOES NOT DO. It deletes nothing and conceals no deletion: the specification
    withdrew Part I's `forge_provenance` - which rewrote chain links so an existing
    deletion looked clean - for exactly that reason, and no operator in the closed catalog
    conceals a deletion. It creates no ground-truth step, so fabrication leaves ground truth
    unchanged and a fabricated line witnesses nothing. It never touches another source, and
    it never moves a real record's timestamp.

    `template`, in the specification's words, is drawn from the source's own observed
    vocabulary: `event_type` must be one the source actually emitted in this stream, or the
    fabrication would be distinguishable by vocabulary alone and the operator would be
    demonstrating nothing.

    `seq` is a hashed member of a raw event, so every renumbered record arrives under a NEW
    event id. The manifest carries both ids for every record the reseal moved.
    """

    source_id: str
    after_seq: int
    count: int
    event_type: str
    attrs: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id or not self.event_type:
            raise SchemaError("ChainForge: source_id and event_type are required")
        if isinstance(self.after_seq, bool) or isinstance(self.count, bool):
            raise SchemaError("ChainForge: a bool is not a sequence number or a count")
        canon.u32(self.after_seq)
        canon.u32(self.count)
        if self.count == 0:
            raise SchemaError("ChainForge: a count of zero fabricates nothing")
        if not isinstance(self.attrs, tuple):
            raise SchemaError("ChainForge: attrs must be a tuple of pairs")
        keys = tuple(key for key, _ in self.attrs)
        if tuple(sorted(set(keys), key=canon.byte_order_key)) != keys:
            raise SchemaError(
                "ChainForge: template attribute keys must be unique and in bytewise order"
            )

    def to_scf(self) -> dict[str, Any]:
        return {
            "after_seq": self.after_seq,
            "attrs": {key: value for key, value in self.attrs},
            "count": self.count,
            "event_type": self.event_type,
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
    strip_identity: StripIdentity | None = None
    stripped: tuple[StrippedRef, ...] = ()
    chain_forge: ChainForge | None = None
    forged: tuple[ForgedRef, ...] = ()
    resealed: tuple[ResealedRef, ...] = ()

    def __post_init__(self) -> None:
        """A cell varies one thing, and no manifest row describes a change nothing made.

        The specification orders operators (61.4.0) for a plan that applies several; this
        slice runs one operator per cell, so a result carrying two specs is refused here
        rather than reported under whichever name `_operator_name` happens to check first.
        A cell that mixed two interventions could not attribute its effect to either.
        """
        applied = [
            name
            for name, spec in (
                ("whole_source_blackout", self.blackout),
                ("backdate", self.backdate),
                ("strip_identity", self.strip_identity),
                ("chain_forge", self.chain_forge),
            )
            if spec is not None
        ]
        if len(applied) > 1:
            raise SchemaError(
                "DegradationResult: a cell applies one operator; "
                f"{' with '.join(applied)} could not attribute an effect to either"
            )
        for rows, owner, name in (
            (self.rewritten, self.backdate, "rewritten"),
            (self.stripped, self.strip_identity, "stripped"),
            (self.forged, self.chain_forge, "forged"),
            (self.resealed, self.chain_forge, "resealed"),
        ):
            if rows and owner is None:
                raise SchemaError(
                    f"DegradationResult: {name} rows without the operator that produced "
                    "them would describe a change that nothing did"
                )

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
        if self.strip_identity is not None:
            document["strip_identity"] = {
                **self.strip_identity.to_scf(),
                "stripped": [r.to_scf() for r in self.stripped],
            }
        if self.chain_forge is not None:
            document["chain_forge"] = {
                **self.chain_forge.to_scf(),
                "forged": [r.to_scf() for r in self.forged],
                "resealed": [r.to_scf() for r in self.resealed],
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


def strip_identity(raw: tuple[RawEvent, ...], spec: StripIdentity) -> DegradationResult:
    """Apply STRIP-IDENTITY: remove `spec.fields` from the records of one source.

    Deterministic and seedless - which records lose which keys is fixed by the source and
    the field list and by nothing else, so there is nothing for a seed to choose. Every
    record of the source carrying one of the named keys loses it; a record that never
    carried one is passed through as the same object rather than rebuilt, which is what
    makes the operator a genuine no-op exactly where there is nothing to remove.

    Nothing is deleted, nothing is reordered and no other source is read, so `completeness`
    is the identity 1/1 and `removed` is empty. The manifest names the operator, the fields
    and both ids of every record touched.

    A selection that matches nothing - an unknown source, or fields no record carries - is
    refused rather than returned as an empty intervention, because a cell whose operator
    quietly did nothing is reported downstream as a cell that found nothing.
    """
    if not isinstance(spec, StripIdentity):
        raise SchemaError("strip_identity: spec must be a StripIdentity")

    stripped: list[StrippedRef] = []
    survivors: list[RawEvent] = []
    for record in raw:
        removed_keys = spec.strips(record)
        if not removed_keys:
            survivors.append(record)
            continue
        dropped = frozenset(removed_keys)
        kept = RawEvent(
            source_id=record.source_id,
            seq=record.seq,
            t_evt_ns=record.t_evt_ns,
            event_type=record.event_type,
            attrs=tuple((key, value) for key, value in record.attrs if key not in dropped),
        )
        survivors.append(kept)
        stripped.append(
            StrippedRef(
                source_id=source_key(record.source_id),
                seq=record.seq,
                fields=removed_keys,
                was_event_id=str(record.event_id),
                now_event_id=str(kept.event_id),
            )
        )

    if not stripped:
        raise SchemaError(
            f"strip_identity: no record on {spec.source_id!r} carries any of "
            f"{list(spec.fields)} to remove",
            code="E-DEGRADE-SELECT",
        )

    ordered = tuple(sorted(survivors, key=lambda r: r.sort_key()))
    canon.check_strictly_ascending(
        [r.sort_key() for r in ordered], lambda k: k, where="strip_identity.raw"
    )
    return DegradationResult(
        raw=ordered,
        removed=(),
        completeness=Completeness.of(1, 1),
        degradation_seed=0,
        parent_raw_hash=canon.hash_ref(RAW_FILE_KIND, render_raw(raw)),
        strip_identity=spec,
        stripped=tuple(sorted(stripped, key=lambda ref: ref.sort_key())),
    )


def chain_forge(raw: tuple[RawEvent, ...], spec: ChainForge) -> DegradationResult:
    """Apply CHAIN-FORGE: insert fabricated records and reseal the numbering after them.

    Deterministic and seedless - the insertion point, the count and the template fix every
    member of every fabricated record, and their instants are an integer interpolation of
    the gap the insertion point leaves, so there is nothing for a seed to choose. The
    fabricated instants land strictly inside that gap: a record outside it would contradict
    its own sequence number and a temporal-consistency pass would catch the forgery for a
    reason that has nothing to do with the chain.

    Nothing is deleted, so `completeness` is the identity 1/1 and `removed` is empty. The
    manifest names the operator, marks every fabricated line SYNTHETIC/FORGED so it cannot
    be counted as an observation, and records both seqs and both ids of every real record
    the reseal renumbered.

    Refused rather than quietly turned into something else: a source that delivered no
    record; an `after_seq` that source does not have; an `after_seq` that is its last
    record, where a forgery would extend the tail and need no reseal, which is a different
    operator; an `event_type` the source never emitted, which would be distinguishable by
    vocabulary alone; and a gap too narrow to hold `count` distinct instants strictly
    inside it.
    """
    if not isinstance(spec, ChainForge):
        raise SchemaError("chain_forge: spec must be a ChainForge")

    source = sorted(
        (r for r in raw if source_key(r.source_id) == spec.source_id), key=lambda r: r.seq
    )
    if not source:
        raise SchemaError(
            f"chain_forge: {spec.source_id!r} delivered no record to forge onto",
            code="E-DEGRADE-SELECT",
        )
    canon.check_strictly_ascending(
        [r.seq for r in source], lambda k: k, where=f"chain_forge.{spec.source_id}.seq"
    )
    vocabulary = tuple(sorted({r.event_type for r in source}, key=canon.byte_order_key))
    if spec.event_type not in vocabulary:
        raise SchemaError(
            f"chain_forge: {spec.source_id!r} never emitted {spec.event_type!r}; a "
            "fabrication outside the source's own vocabulary is distinguishable without "
            "looking at the chain at all",
            code="E-DEGRADE-SELECT",
        )

    host_index = next(
        (index for index, r in enumerate(source) if r.seq == spec.after_seq), None
    )
    if host_index is None:
        raise SchemaError(
            f"chain_forge: {spec.source_id!r} has no record numbered {spec.after_seq}",
            code="E-DEGRADE-SELECT",
        )
    if host_index + 1 == len(source):
        raise SchemaError(
            f"chain_forge: record {spec.after_seq} is the last on {spec.source_id!r}; "
            "appending past the end needs no reseal and is not this operator",
            code="E-DEGRADE-SELECT",
        )

    host = source[host_index]
    successor = source[host_index + 1]
    gap = successor.t_evt_ns - host.t_evt_ns
    if gap < spec.count + 1:
        raise SchemaError(
            f"chain_forge: the {gap} ns between records {host.seq} and {successor.seq} of "
            f"{spec.source_id!r} cannot hold {spec.count} distinct instants strictly "
            "inside it",
            code="E-DEGRADE-SELECT",
        )
    step = gap // (spec.count + 1)

    forged: list[ForgedRef] = []
    fabricated: list[RawEvent] = []
    for index in range(spec.count):
        record = RawEvent(
            source_id=host.source_id,
            seq=spec.after_seq + 1 + index,
            t_evt_ns=host.t_evt_ns + step * (index + 1),
            event_type=spec.event_type,
            attrs=spec.attrs,
        )
        fabricated.append(record)
        forged.append(
            ForgedRef(
                source_id=spec.source_id,
                seq=record.seq,
                t_evt_ns=record.t_evt_ns,
                event_type=record.event_type,
                event_id=str(record.event_id),
            )
        )

    resealed: list[ResealedRef] = []
    out: list[RawEvent] = list(fabricated)
    for record in raw:
        if source_key(record.source_id) != spec.source_id or record.seq <= spec.after_seq:
            out.append(record)
            continue
        moved = RawEvent(
            source_id=record.source_id,
            seq=record.seq + spec.count,
            t_evt_ns=record.t_evt_ns,
            event_type=record.event_type,
            attrs=record.attrs,
        )
        out.append(moved)
        resealed.append(
            ResealedRef(
                source_id=spec.source_id,
                was_seq=record.seq,
                now_seq=moved.seq,
                was_event_id=str(record.event_id),
                now_event_id=str(moved.event_id),
            )
        )

    ordered = tuple(sorted(out, key=lambda r: r.sort_key()))
    canon.check_strictly_ascending(
        [r.sort_key() for r in ordered], lambda k: k, where="chain_forge.raw"
    )
    return DegradationResult(
        raw=ordered,
        removed=(),
        completeness=Completeness.of(1, 1),
        degradation_seed=0,
        parent_raw_hash=canon.hash_ref(RAW_FILE_KIND, render_raw(raw)),
        chain_forge=spec,
        forged=tuple(sorted(forged, key=lambda ref: ref.sort_key())),
        resealed=tuple(sorted(resealed, key=lambda ref: ref.sort_key())),
    )


def _operator_name(result: DegradationResult) -> str:
    """The operator that actually ran, so a manifest never describes one as another."""
    if result.backdate is not None:
        return "backdate"
    if result.blackout is not None:
        return "whole_source_blackout"
    if result.strip_identity is not None:
        return "strip_identity"
    if result.chain_forge is not None:
        return "chain_forge"
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
