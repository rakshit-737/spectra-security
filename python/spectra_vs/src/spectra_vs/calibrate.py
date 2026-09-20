"""S6 calibration: the baseline arrival profile, taken from a run that is not this run.

WHY THIS STAGE EXISTS AT ALL. The liveness stage needs a number that says how long a
silence has to be before it stops being normal. The obvious way to get that number is to
take a high quantile of the gaps observed in the telemetry under analysis. That is the
self-calibration trap, and it is the single defect this module exists to make
structurally impossible: deleting records stretches the observed gap distribution, so
the quantile rises with the degradation level, so the threshold rises, so fewer windows
are called blind exactly where more of them are blind. Suppression would then hide
itself most effectively at the highest degradation, which is the region the research is
about, and the result would be circular rather than wrong in a visible way.

So the profile is produced by a SEPARATE run: the same scenario family at completeness
1.0, under the identity degradation spec, under a seed drawn from the calibration band
[1000000, 1000063], which is disjoint from the analysis band [1, 999999]. The profile is
written to a file, the file is hashed, and the hash travels in the certificate. The six
binding gates B1..B6 that re-check the separation live in `liveness`, because they are
evaluated against the run rather than against the profile alone.

WHAT IT IS NOT. It is not a measurement of any real telemetry. It is a model of one
seeded generator's emission behaviour under one scenario family, and nothing here may be
rendered as a property of a real sensor.

THE DIGEST. The specification names blake3. This reference implementation has the
standard library only, so `spectra_core.canon` computes blake2b-256 and labels every
reference it emits `b2b256:`. Nothing in this module writes a digest behind a different
label.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final

from spectra_core import canon
from spectra_core.errors import CanonError, ProfileError, SchemaError
from spectra_core.ids import SourceId
from spectra_core.model import CanonicalEvent, IntegrityClass, Nanos, check_nanos

__all__ = [
    "ANALYSIS_SEED_BAND",
    "CALIBRATION_SEED_BAND",
    "IDENTITY_SPEC_HASH",
    "MIN_CALIBRATION_RECORDS",
    "PROFILE_SCHEMA",
    "SCF_MAX_DEPTH",
    "U32_MAX",
    "U64_MAX",
    "ExcludedInterval",
    "Phase",
    "RegimeProfile",
    "SourceCalibration",
    "SourceProfile",
    "build_profile",
    "check_calibration_seed",
    "excluded_intervals_hash",
    "gap_digest",
    "gap_vectors",
    "identity_spec_hash",
    "load_profile",
    "parse_quantile",
    "phase_of",
    "profile_hash",
    "q_exact",
    "scf_bytes",
    "scf_dumps",
    "scf_loads",
    "write_profile",
]


PROFILE_SCHEMA: Final[str] = "spectra.source_profile/1"

#: Seeds a calibration run may use. Disjoint from the analysis band by construction, so
#: gate B3 can reject a profile that was calibrated on a seed an analysis run could draw.
CALIBRATION_SEED_BAND: Final[tuple[int, int]] = (1000000, 1000063)

#: Seeds an analysis run may use.
ANALYSIS_SEED_BAND: Final[tuple[int, int]] = (1, 999999)

#: What the generator is asked to emit per calibrated source over the horizon so that a
#: regime can reach n_min. This module does not enforce it: a short calibration run
#: yields a regime below n_min, and `liveness` then fails that regime closed into F1
#: rather than producing a threshold from too few samples. Aborting here instead would
#: turn a fail-closed outcome into a run failure and lose the honest BLIND verdict.
MIN_CALIBRATION_RECORDS: Final[int] = 2000

U32_MAX: Final[int] = (1 << 32) - 1
U64_MAX: Final[int] = (1 << 64) - 1

#: SCF-lite nesting bound. Deeper structures are rejected rather than serialised,
#: because a parser that must recurse without a bound is a parser an input can exhaust.
SCF_MAX_DEPTH: Final[int] = 8

_SCF_KEY: Final[re.Pattern[str]] = re.compile(r"\A[a-z0-9_]+\Z")
_SCF_MAP_KEY: Final[re.Pattern[str]] = re.compile(r"\A[A-Za-z0-9_/]+\Z")
_QUANTILE: Final[re.Pattern[str]] = re.compile(r"\A([0-9]+)/([0-9]+)\Z")
_U64_TEXT: Final[re.Pattern[str]] = re.compile(r"\A(?:0|[1-9][0-9]*)\Z")

#: The only two members whose keys are data rather than field names, both declared that
#: way by the data contracts: `order_statistics` is keyed by "<p>/<q>" and
#: `blind_volume_ns_by_reason` by a reason code. The global encoding law's key grammar
#: `[a-z0-9_]+` admits neither, so the exception is enumerated here rather than relaxed
#: everywhere; a third data-keyed member has to be added to this set deliberately.
_MAP_KEYED_MEMBERS: Final[frozenset[str]] = frozenset(
    {"blind_volume_ns_by_reason", "order_statistics"}
)


# ---------------------------------------------------------------------------
# SCF-lite for the two artifacts that carry data-keyed members
# ---------------------------------------------------------------------------
#
# WHY THIS IS NOT `spectra_vs.scf`. That module is the slice's general serialiser and
# enforces the encoding law's object-key grammar `[a-z0-9_]+` without exception. The
# SourceProfile contract declares `order_statistics` keyed by "<p>/<q>" and the
# LivenessDoc contract declares `blind_volume_ns_by_reason` keyed by a reason code, and
# neither key matches that grammar. Rather than relax the grammar for every artifact in
# the slice, the exception is enumerated in `_MAP_KEYED_MEMBERS` and confined to the two
# files that declare it. Everything else - key sorting, separators, the float ban, the
# null ban, the u32 bound on a bare integer, the single trailing LF - is the same law,
# and `test_calibrate` asserts the two serialisers agree wherever both accept an object.


def _scf_check(value: object, *, where: str, depth: int, data_keyed: bool = False) -> None:
    """Reject anything SCF-lite forbids before `json.dumps` gets a chance to accept it.

    `json.dumps` will happily serialise a float, a None and a 2**64 integer. Each of
    those breaks byte-identical replay or the no-floats law, so the check happens on the
    object graph rather than on the resulting text, where a regex would have to guess
    which `.` is inside a string.
    """
    if depth > SCF_MAX_DEPTH:
        raise CanonError(f"{where}: nesting deeper than {SCF_MAX_DEPTH}", code="E-LIMIT-DEPTH")
    if value is None:
        raise CanonError(f"{where}: null is never a value; use member absence", code="E-CANON-NULL")
    if isinstance(value, bool):
        return
    if isinstance(value, (float, complex)):
        raise CanonError(f"{where}: floats are forbidden", code="E-CANON-FLOAT")
    if isinstance(value, int):
        if not 0 <= value <= U32_MAX:
            raise CanonError(
                f"{where}: {value} is outside u32; wider integers travel as decimal strings",
                code="E-CANON-WIDTH",
            )
        return
    if isinstance(value, str):
        canon.nfc(value)
        return
    if isinstance(value, dict):
        pattern = _SCF_MAP_KEY if data_keyed else _SCF_KEY
        for key, member in value.items():
            if not isinstance(key, str) or pattern.match(key) is None:
                raise CanonError(f"{where}: object key {key!r} does not match {pattern.pattern}")
            _scf_check(
                member,
                where=f"{where}.{key}",
                depth=depth + 1,
                data_keyed=key in _MAP_KEYED_MEMBERS,
            )
        return
    if isinstance(value, (list, tuple)):
        for index, member in enumerate(value):
            _scf_check(member, where=f"{where}[{index}]", depth=depth + 1, data_keyed=data_keyed)
        return
    raise CanonError(f"{where}: {type(value).__name__} has no SCF-lite encoding")


def scf_dumps(obj: object, *, where: str = "scf") -> str:
    """The canonical text of an artifact object, with no trailing newline."""
    _scf_check(obj, where=where, depth=0)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def scf_bytes(obj: object, *, where: str = "scf") -> bytes:
    """The canonical bytes of an artifact: UTF-8, LF, exactly one trailing LF."""
    return (scf_dumps(obj, where=where) + "\n").encode("utf-8")


def _reject_float_literal(text: str) -> Any:
    raise CanonError(f"scf_loads: a float literal {text!r} in a number position", code="E-CANON-FLOAT")


def _reject_constant(text: str) -> Any:
    raise CanonError(f"scf_loads: {text!r} in a number position", code="E-CANON-FLOAT")


def _reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in items:
        if key in out:
            raise CanonError(f"scf_loads: duplicate object key {key!r}", code="E-CANON-DUPKEY")
        out[key] = value
    return out


def scf_loads(text: str, *, where: str = "scf") -> Any:
    """Parse canonical text back, rejecting every form the emitter could not have made.

    Reading back through the same law the emitter wrote under is what lets `load_profile`
    treat a file as canonical without re-serialising it to compare: a float, a duplicate
    key or a null in the file is a rejection here rather than a value that survives one
    more stage.
    """
    if not isinstance(text, str):
        raise CanonError(f"{where}: expected str, got {type(text).__name__}")
    parsed = json.loads(
        text,
        parse_float=_reject_float_literal,
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicate_keys,
    )
    _scf_check(parsed, where=where, depth=0)
    return parsed


# ---------------------------------------------------------------------------
# Scenario inputs this stage reads
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Phase:
    """One half-open regime of the scenario's hashed phase timeline, `[t0_ns, t1_ns)`.

    Regime membership comes from here and is never inferred from the arrival pattern:
    inferring a regime from the data would make the regime boundary move when records
    are deleted, which is the self-calibration trap wearing a different hat.
    """

    regime_id: str
    t0_ns: Nanos
    t1_ns: Nanos

    def __post_init__(self) -> None:
        canon.nfc(self.regime_id)
        if not self.regime_id:
            raise SchemaError("Phase.regime_id is mandatory")
        check_nanos(self.t0_ns, where="Phase.t0_ns")
        check_nanos(self.t1_ns, where="Phase.t1_ns")
        if self.t1_ns <= self.t0_ns:
            raise SchemaError(f"Phase {self.regime_id}: t1_ns must exceed t0_ns")

    def contains(self, t_ns: Nanos) -> bool:
        return self.t0_ns <= t_ns < self.t1_ns


@dataclass(frozen=True, slots=True)
class ExcludedInterval:
    """A span the scenario declares uninformative, `[t0_ns, t1_ns)`, with its reason.

    A gap whose span touches one of these is dropped from the calibration vector rather
    than kept, because a maintenance window is not evidence about arrival behaviour and
    keeping it would raise the quantile for every window that follows.
    """

    t0_ns: Nanos
    t1_ns: Nanos
    reason: str

    def __post_init__(self) -> None:
        check_nanos(self.t0_ns, where="ExcludedInterval.t0_ns")
        check_nanos(self.t1_ns, where="ExcludedInterval.t1_ns")
        if self.t1_ns < self.t0_ns:
            raise SchemaError("ExcludedInterval: t1_ns precedes t0_ns")
        canon.nfc(self.reason)
        if not self.reason:
            raise SchemaError("ExcludedInterval.reason is mandatory")

    def intersects_closed(self, a_ns: Nanos, b_ns: Nanos) -> bool:
        """True when this exclusion meets the CLOSED span `[a_ns, b_ns]`.

        Closed on both ends so that a zero-length gap sitting exactly on an exclusion
        boundary is still dropped; a half-open test would silently keep it.
        """
        return self.t0_ns <= b_ns and a_ns < self.t1_ns


def phase_of(phases: tuple[Phase, ...], t_ns: Nanos) -> str | None:
    """The regime containing `t_ns`, or None when no declared phase does.

    None is a real answer and is propagated rather than defaulted: `liveness` turns it
    into BLIND with B_REGIME_UNKNOWN, which is the fail-closed reading of a timestamp
    the scenario never described.
    """
    for phase in phases:
        if phase.contains(t_ns):
            return phase.regime_id
    return None


def check_phases(phases: tuple[Phase, ...]) -> tuple[Phase, ...]:
    """Verify the timeline is ascending and non-overlapping, and return it unchanged.

    Verifying rather than sorting keeps a caller that built the timeline from a dict
    visible instead of tidied up on the way through.
    """
    canon.check_strictly_ascending(phases, lambda p: (p.t0_ns, p.t1_ns), where="phases")
    for left, right in zip(phases, phases[1:]):
        if right.t0_ns < left.t1_ns:
            raise SchemaError(f"phases: {left.regime_id} overlaps {right.regime_id}")
    seen: set[str] = set()
    for phase in phases:
        if phase.regime_id in seen:
            raise SchemaError(f"phases: regime_id {phase.regime_id!r} declared twice")
        seen.add(phase.regime_id)
    return phases


# ---------------------------------------------------------------------------
# Hashes this stage owns
# ---------------------------------------------------------------------------


def identity_spec_hash() -> str:
    """The degradation-spec hash of the identity spec: no operators, completeness 1/1.

    Gate B2 compares a profile's `degradation_spec_hash` against this value, so the
    identity spec needs exactly one definition in the repository. It lives here because
    calibration is the only stage that is required to have run under it.
    """
    payload = canon.ordered_seq(()) + canon.u32(1) + canon.u32(1)
    return canon.hash_ref("degspec", payload)


IDENTITY_SPEC_HASH: Final[str] = identity_spec_hash()


def excluded_intervals_hash(excluded: tuple[ExcludedInterval, ...]) -> str:
    """Hash the exclusion list so gate B6 can reject a profile built under a different one.

    The reason text is included: two runs that excluded the same spans for different
    stated reasons excluded them under different scenarios, and the gate should see that.
    """
    ordered = sorted(excluded, key=lambda e: (e.t0_ns, e.t1_ns, canon.byte_order_key(e.reason)))
    payload = canon.ordered_seq(
        canon.i64(e.t0_ns) + canon.i64(e.t1_ns) + canon.utf8_text(e.reason) for e in ordered
    )
    return canon.hash_ref("excl", payload)


def gap_digest(gaps: tuple[int, ...]) -> str:
    """`LEB128(len) || LEB128(gap_i)` over the full ascending gap vector.

    The digest covers every gap, not just the order statistics, so a profile cannot be
    edited to move a quantile while the vector it claims to summarise stays plausible.
    """
    for gap in gaps:
        if isinstance(gap, bool) or not isinstance(gap, int) or not 0 <= gap <= U64_MAX:
            raise CanonError(f"gap_digest: {gap!r} is not a u64 nanosecond gap", code="E-CANON-WIDTH")
    canon.check_strictly_ascending(
        tuple(enumerate(gaps)), lambda pair: (pair[1], pair[0]), where="gap_digest"
    )
    return canon.hash_ref("gapv", canon.leb128_seq(gaps))


# ---------------------------------------------------------------------------
# The gap vector
# ---------------------------------------------------------------------------


def _calibration_sort_key(event: CanonicalEvent) -> tuple[int, int, bytes]:
    return (event.t_evt_ns, event.seq, canon.byte_order_key(str(event.event_id)))


def gap_vectors(
    events: tuple[CanonicalEvent, ...],
    phases: tuple[Phase, ...],
    excluded: tuple[ExcludedInterval, ...],
) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Consecutive arrival gaps of one source, partitioned by regime, each sorted ascending.

    Three choices are made here and each narrows the vector rather than widening it,
    because every gap kept can only raise the quantile and a raised quantile is a
    threshold that calls more silence normal:

      * a gap is attributed to a regime only when BOTH its endpoints lie in that same
        regime. A gap that straddles a phase boundary is dropped. Straddling gaps are
        systematically the long ones, and charging them to either neighbouring regime
        would inflate that regime's tail with a span the regime did not produce.
      * a gap whose closed span meets any excluded interval is dropped.
      * zero gaps are kept, per the specification: two records at the same instant are
        a real arrival pattern and dropping them would thin the low end of the vector.
    """
    ordered = sorted(events, key=_calibration_sort_key)
    by_regime: dict[str, list[int]] = {}
    for previous, current in zip(ordered, ordered[1:]):
        span = current.t_evt_ns - previous.t_evt_ns
        if span < 0:
            raise ProfileError(
                f"gap_vectors: {previous.source_id} is not ascending in t_evt_ns",
                code="PROFILE_INVALID",
            )
        left = phase_of(phases, previous.t_evt_ns)
        right = phase_of(phases, current.t_evt_ns)
        if left is None or left != right:
            continue
        if any(e.intersects_closed(previous.t_evt_ns, current.t_evt_ns) for e in excluded):
            continue
        by_regime.setdefault(left, []).append(span)
    return tuple(
        (regime_id, tuple(sorted(by_regime[regime_id])))
        for regime_id in sorted(by_regime, key=canon.byte_order_key)
    )


def parse_quantile(text: str) -> tuple[int, int]:
    """Split `"<p>/<q>"` into two integers, rejecting a decimal literal outright.

    Parsed rather than accepted as a pair so that the string in the config file and the
    string in the artifact are the same bytes, and a rendering cannot drift from what
    was computed.
    """
    match = _QUANTILE.match(text) if isinstance(text, str) else None
    if match is None:
        raise CanonError(f"parse_quantile: {text!r} is not '<p>/<q>' with integer members")
    p_text, q_text = match.group(1), match.group(2)
    if (p_text != "0" and p_text.startswith("0")) or (q_text != "0" and q_text.startswith("0")):
        raise CanonError(f"parse_quantile: {text!r} has a leading zero")
    p, q = int(p_text), int(q_text)
    if q == 0:
        raise CanonError(f"parse_quantile: {text!r} has a zero denominator")
    if p > q:
        raise CanonError(f"parse_quantile: {text!r} exceeds one")
    return (p, q)


def q_exact(sorted_gaps: tuple[int, ...], p: int, q: int) -> int:
    """The exact-rank order statistic at `p/q`. No interpolation, no float, no estimator.

    Interpolating estimators (R type 7 and the Hyndman-Fan family) produce a value that
    is not in the sample and whose last bits depend on the arithmetic order. An
    exact-rank statistic is an element of the vector, so two implementations that agree
    on the vector agree on the threshold.
    """
    n = len(sorted_gaps)
    if n == 0:
        raise ProfileError("q_exact: the gap vector is empty", code="PROFILE_INVALID")
    j = (n * p + (q - 1)) // q
    if j < 1:
        j = 1
    if j > n:
        j = n
    return sorted_gaps[j - 1]


def check_calibration_seed(seed: int) -> int:
    """Reject a calibration seed outside the calibration band.

    Checked at the producing end as well as at gate B3, because a profile built on an
    analysis-band seed is unusable and finding that out at prove time wastes the run
    that produced it.
    """
    low, high = CALIBRATION_SEED_BAND
    if isinstance(seed, bool) or not isinstance(seed, int) or not low <= seed <= high:
        raise ProfileError(
            f"check_calibration_seed: {seed!r} is outside the calibration band {CALIBRATION_SEED_BAND}",
            code="PROFILE_SEED_OVERLAP",
        )
    return seed


# ---------------------------------------------------------------------------
# The profile record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegimeProfile:
    """The calibrated arrival behaviour of one source inside one regime."""

    regime_id: str
    n_gaps: int
    order_statistics: tuple[tuple[str, int], ...]
    min_gap_ns: int
    max_gap_ns: int
    gap_digest: str

    def __post_init__(self) -> None:
        canon.nfc(self.regime_id)
        canon.u32(self.n_gaps)
        if self.n_gaps < 1:
            raise SchemaError(
                "RegimeProfile: a regime with no gaps is omitted from the profile, not "
                "published with an empty vector"
            )
        canon.check_strictly_ascending(
            self.order_statistics, lambda kv: canon.byte_order_key(kv[0]), where="order_statistics"
        )
        if not self.order_statistics:
            raise SchemaError("RegimeProfile.order_statistics is mandatory")
        for level, value in self.order_statistics:
            parse_quantile(level)
            if not 0 <= value <= U64_MAX:
                raise CanonError(f"RegimeProfile: order statistic {value} is not u64")
        for label, value in (("min_gap_ns", self.min_gap_ns), ("max_gap_ns", self.max_gap_ns)):
            if not 0 <= value <= U64_MAX:
                raise CanonError(f"RegimeProfile.{label}: {value} is not u64")
        if self.max_gap_ns < self.min_gap_ns:
            raise SchemaError("RegimeProfile: max_gap_ns precedes min_gap_ns")
        canon.parse_hash_ref(self.gap_digest)

    def order_statistic(self, level: str) -> int | None:
        for key, value in self.order_statistics:
            if key == level:
                return value
        return None

    def to_scf(self) -> dict[str, object]:
        return {
            "gap_digest": self.gap_digest,
            "max_gap_ns": str(self.max_gap_ns),
            "min_gap_ns": str(self.min_gap_ns),
            "n_gaps": self.n_gaps,
            "order_statistics": {level: str(value) for level, value in self.order_statistics},
            "regime_id": self.regime_id,
        }


@dataclass(frozen=True, slots=True)
class SourceCalibration:
    """One source's regimes. A source with no calibrated regime is still published.

    Publishing a source with `regimes: []` is the point of declaring a sensor that emits
    nothing: it is present, it is insufficient, and `liveness` fails it closed into F1.
    An undeclared source would simply be invisible, and invisible is the outcome this
    project exists to remove.
    """

    source_id: SourceId
    integrity_class: IntegrityClass
    regimes: tuple[RegimeProfile, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise SchemaError("SourceCalibration.source_id must be a SourceId")
        if not isinstance(self.integrity_class, IntegrityClass):
            raise SchemaError("SourceCalibration.integrity_class must be an IntegrityClass")
        canon.check_strictly_ascending(
            self.regimes, lambda r: canon.byte_order_key(r.regime_id), where="regimes"
        )

    def regime(self, regime_id: str) -> RegimeProfile | None:
        for entry in self.regimes:
            if entry.regime_id == regime_id:
                return entry
        return None

    def to_scf(self) -> dict[str, object]:
        return {
            "integrity_class": str(self.integrity_class),
            "regimes": [r.to_scf() for r in self.regimes],
            "source_id": self.source_id.snake,
        }


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """The whole calibration artifact, `profiles/<family>.json`.

    Everything a binding gate needs to decide whether this profile may be used on a
    given run is a member here, so the gates are a comparison of hashed values rather
    than a judgement about provenance.
    """

    scenario_family: str
    generator_config_hash: str
    degradation_spec_hash: str
    calibration_seed_band: tuple[int, int]
    reference_bundle_hash: str
    reference_run_manifest_hash: str
    excluded_intervals_hash: str
    regime_collapsed: bool
    sources: tuple[SourceCalibration, ...]
    schema: str = PROFILE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROFILE_SCHEMA:
            raise SchemaError(f"SourceProfile.schema must be {PROFILE_SCHEMA!r}")
        canon.nfc(self.scenario_family)
        if not self.scenario_family:
            raise SchemaError("SourceProfile.scenario_family is mandatory")
        for label in (
            "generator_config_hash",
            "degradation_spec_hash",
            "reference_bundle_hash",
            "reference_run_manifest_hash",
            "excluded_intervals_hash",
        ):
            canon.parse_hash_ref(getattr(self, label))
        low, high = self.calibration_seed_band
        canon.u32(low)
        canon.u32(high)
        if high < low:
            raise SchemaError("SourceProfile.calibration_seed_band is descending")
        if not isinstance(self.regime_collapsed, bool):
            raise SchemaError("SourceProfile.regime_collapsed must be a bool")
        canon.check_strictly_ascending(
            self.sources, lambda s: canon.byte_order_key(str(s.source_id)), where="sources"
        )

    def source(self, source_id: str) -> SourceCalibration | None:
        """Look a source up by its prefixed id or by its bare snake.

        Both spellings are accepted because the in-memory type carries the `src:` prefix
        while the artifact carries the bare name, and a lookup that silently missed would
        drop a source into F1 rather than reporting a mismatch.
        """
        wanted = str(source_id)
        for entry in self.sources:
            if str(entry.source_id) == wanted or entry.source_id.snake == wanted:
                return entry
        return None

    def to_scf(self) -> dict[str, object]:
        """The artifact object, including `profile_id`."""
        body = self._body()
        body["profile_id"] = self.profile_id
        return body

    def _body(self) -> dict[str, object]:
        return {
            "calibration_seed_band": [self.calibration_seed_band[0], self.calibration_seed_band[1]],
            "degradation_spec_hash": self.degradation_spec_hash,
            "excluded_intervals_hash": self.excluded_intervals_hash,
            "generator_config_hash": self.generator_config_hash,
            "reference_bundle_hash": self.reference_bundle_hash,
            "reference_run_manifest_hash": self.reference_run_manifest_hash,
            "regime_collapsed": self.regime_collapsed,
            "scenario_family": self.scenario_family,
            "schema": self.schema,
            "sources": [s.to_scf() for s in self.sources],
        }

    @property
    def profile_id(self) -> str:
        """Content address of the profile with `profile_id` itself removed.

        Removing the member before hashing is what makes the self-reference well
        founded; folding a placeholder into the preimage instead would make the id
        depend on the shape of the placeholder.
        """
        return canon.hash_ref("prof", scf_bytes(self._body(), where="profile_body"))

    def canonical_bytes(self) -> bytes:
        """The exact file bytes, which are what `profile_hash` covers."""
        return scf_bytes(self.to_scf(), where="profile")


def profile_hash(profile: SourceProfile) -> str:
    """The certificate's `profile_hash`: a digest of the profile's canonical file bytes.

    Distinct from `profile_id`, which omits the id member. The certificate pins the file
    it actually read, so that editing an order statistic after the fact invalidates the
    certificate rather than quietly changing a threshold.
    """
    return canon.hash_ref("proffile", profile.canonical_bytes())


# ---------------------------------------------------------------------------
# Building the profile
# ---------------------------------------------------------------------------


def build_profile(
    *,
    scenario_family: str,
    events_by_source: tuple[tuple[SourceId, IntegrityClass, tuple[CanonicalEvent, ...]], ...],
    phases: tuple[Phase, ...],
    excluded: tuple[ExcludedInterval, ...],
    quantile_levels: tuple[str, ...],
    generator_config_hash: str,
    reference_bundle_hash: str,
    reference_run_manifest_hash: str,
    calibration_seed: int,
    collapse_regimes: bool = False,
) -> SourceProfile:
    """Compute the profile from one clean calibration run.

    `quantile_levels` comes from liveness.toml and nothing else, so the order-statistic
    keys in the profile are exactly the levels the liveness stage will ask for; a profile
    that carries a level nobody reads, or is missing the one that is read, is a
    configuration error rather than something to interpolate around.

    `collapse_regimes` merges every regime of a source into one vector under the regime
    id `"collapsed"`. It is off by default and, when on, sets `regime_collapsed`, which
    reaches the liveness flags: a collapsed profile describes a source whose regimes were
    not separately calibrated, and that has to be visible in the certificate rather than
    inferred from a thin vector.
    """
    check_calibration_seed(calibration_seed)
    check_phases(phases)
    if not quantile_levels:
        raise ProfileError("build_profile: no quantile level was requested", code="PROFILE_INVALID")
    levels = canon.sorted_unique(quantile_levels)
    parsed_levels = tuple((level, *parse_quantile(level)) for level in levels)

    calibrations: list[SourceCalibration] = []
    for source_id, integrity_class, events in events_by_source:
        vectors = gap_vectors(events, phases, excluded)
        if collapse_regimes:
            merged: list[int] = []
            for _, gaps in vectors:
                merged.extend(gaps)
            vectors = (("collapsed", tuple(sorted(merged))),) if merged else ()
        regimes = tuple(
            RegimeProfile(
                regime_id=regime_id,
                n_gaps=len(gaps),
                order_statistics=tuple(
                    (level, q_exact(gaps, p, q)) for level, p, q in parsed_levels
                ),
                min_gap_ns=gaps[0],
                max_gap_ns=gaps[-1],
                gap_digest=gap_digest(gaps),
            )
            for regime_id, gaps in vectors
            if gaps
        )
        calibrations.append(
            SourceCalibration(
                source_id=source_id, integrity_class=integrity_class, regimes=regimes
            )
        )

    ordered = tuple(canon.sorted_by_bytes(calibrations, lambda s: str(s.source_id)))
    return SourceProfile(
        scenario_family=scenario_family,
        generator_config_hash=generator_config_hash,
        degradation_spec_hash=IDENTITY_SPEC_HASH,
        calibration_seed_band=CALIBRATION_SEED_BAND,
        reference_bundle_hash=reference_bundle_hash,
        reference_run_manifest_hash=reference_run_manifest_hash,
        excluded_intervals_hash=excluded_intervals_hash(excluded),
        regime_collapsed=collapse_regimes,
        sources=ordered,
    )


def write_profile(profile: SourceProfile, path: str) -> str:
    """Write the artifact and return its `profile_id`.

    Binary mode with explicit bytes, never text mode: text mode on this platform would
    translate the LF into CRLF and every hash downstream would be over different bytes
    than the ones the emitter computed.
    """
    data = profile.canonical_bytes()
    with open(path, "wb") as handle:
        handle.write(data)
    return profile.profile_id


def load_profile(path: str) -> SourceProfile:
    """Read a profile back, re-deriving `profile_id` rather than trusting the member.

    A profile whose stored id does not recompute is rejected here rather than at gate
    time, because every gate downstream compares fields of an object that has already
    been assumed to be the object its id names.
    """
    with open(path, "rb") as handle:
        raw = handle.read()
    text = raw.decode("utf-8")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ProfileError(
            f"load_profile: {path} does not end in exactly one LF", code="PROFILE_INVALID"
        )
    obj = scf_loads(text[:-1], where="profile")
    if not isinstance(obj, dict):
        raise ProfileError("load_profile: the profile is not an object", code="PROFILE_INVALID")
    stored_id = obj.get("profile_id")
    if not isinstance(stored_id, str):
        raise ProfileError("load_profile: profile_id is absent", code="PROFILE_INVALID")

    sources: list[SourceCalibration] = []
    for entry in _require_list(obj, "sources"):
        regimes: list[RegimeProfile] = []
        for regime in _require_list(entry, "regimes"):
            statistics = regime["order_statistics"]
            if not isinstance(statistics, dict):
                raise ProfileError(
                    "load_profile: order_statistics is not an object", code="PROFILE_INVALID"
                )
            regimes.append(
                RegimeProfile(
                    regime_id=regime["regime_id"],
                    n_gaps=regime["n_gaps"],
                    order_statistics=tuple(
                        (level, _u64_text(statistics[level], where="order_statistics"))
                        for level in sorted(statistics, key=canon.byte_order_key)
                    ),
                    min_gap_ns=_u64_text(regime["min_gap_ns"], where="min_gap_ns"),
                    max_gap_ns=_u64_text(regime["max_gap_ns"], where="max_gap_ns"),
                    gap_digest=regime["gap_digest"],
                )
            )
        sources.append(
            SourceCalibration(
                source_id=SourceId.of(entry["source_id"]),
                integrity_class=IntegrityClass(entry["integrity_class"]),
                regimes=tuple(regimes),
            )
        )

    band = obj["calibration_seed_band"]
    if not isinstance(band, list) or len(band) != 2:
        raise ProfileError("load_profile: calibration_seed_band is not a pair", code="PROFILE_INVALID")
    profile = SourceProfile(
        schema=obj["schema"],
        scenario_family=obj["scenario_family"],
        generator_config_hash=obj["generator_config_hash"],
        degradation_spec_hash=obj["degradation_spec_hash"],
        calibration_seed_band=(band[0], band[1]),
        reference_bundle_hash=obj["reference_bundle_hash"],
        reference_run_manifest_hash=obj["reference_run_manifest_hash"],
        excluded_intervals_hash=obj["excluded_intervals_hash"],
        regime_collapsed=obj["regime_collapsed"],
        sources=tuple(sources),
    )
    if profile.profile_id != stored_id:
        raise ProfileError(
            f"load_profile: {path} carries profile_id {stored_id} but recomputes to "
            f"{profile.profile_id}",
            code="PROFILE_INVALID",
        )
    return profile


def _require_list(obj: dict[str, Any], key: str) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        raise ProfileError(f"load_profile: {key} is absent or not an array", code="PROFILE_INVALID")
    return value


def _u64_text(value: object, *, where: str) -> int:
    """Decode a u64 carried as decimal text, rejecting any other spelling of the number."""
    if not isinstance(value, str) or _U64_TEXT.match(value) is None:
        raise ProfileError(
            f"load_profile: {where} is not a canonical decimal u64 string: {value!r}",
            code="PROFILE_INVALID",
        )
    parsed = int(value)
    if parsed > U64_MAX:
        raise ProfileError(f"load_profile: {where} exceeds u64", code="PROFILE_INVALID")
    return parsed
