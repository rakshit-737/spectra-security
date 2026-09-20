"""S7 liveness: LIVE, BLIND or SUPPRESSED per source and interval, and the licences.

WHAT THIS STAGE DECIDES. For every source and every elementary interval of the
breakpoint grid, one of three verdicts. LIVE means no gap exceeding the calibrated
threshold was observed, under a named profile, on a source of a named integrity class.
It is not a claim that the window was checked and found complete, nor that nothing was
lost from it, and no rendering built on this module's output may make one. BLIND means
liveness could not be established. SUPPRESSED means the source's own sequence numbering
shows records are missing from the span.

THE FAIL-CLOSED DIRECTION IS BLIND. There is exactly one construction site of LIVE in
this module, rule R11 at the end of `classify`, and it is reachable only after every
earlier rule has declined. There is no default branch that yields LIVE, no `except:
return LIVE`, and the broad exception handler in `classify_interval` converts any
internal failure into BLIND with a reason code rather than letting it reach the caller.
A stage that crashed and a stage that saw nothing are the same thing for a consumer, and
the safe reading of both is that nothing was seen.

THE THRESHOLD COMES FROM SOMEWHERE ELSE. Never from the bundle under analysis. See
`calibrate` for why; the six binding gates B1..B6 in `check_binding_gates` are the
re-checkable form of that separation, and they are evaluated here because only here are
both the profile and the run's own hashed inputs in scope.

A LICENCE IS A PERMISSION, NOT AN OBSERVATION. `issue_licences` returns permission to
instantiate an unobserved step over a blind interval, with its basis, its reason, its
interval and, for SUPPRESSED only, its bracketing witness. Nothing here may describe a
licence as evidence that something happened.

VOIDING A LICENCE RAISES A FLAG RATHER THAN QUIETLY STRENGTHENING THE ANSWER. Removing
a licence shrinks the licensed set, which shrinks P_max, which can only make a verdict
look safer. An attacker who controlled timestamps could therefore manufacture safety by
making licences look untrustworthy. So `issue_licences` never silently drops a licence:
a voided licence is recorded, the instance is refused rather than admitted, and the flag
`license_voided_by_suspected_tampering` (bit 5, soundness class) is set, which blocks
ROBUST. In this slice the difference-constraint backdating pass does not exist, so
nothing ever voids a licence, `tamper_suspected` is always false and the flag is always
false. This module must never claim it detects suppression, backdating or tampering.

THE DIGEST. The specification names blake3; this reference implementation computes
blake2b-256 through `spectra_core.canon` and labels it `b2b256:`.
"""

from __future__ import annotations

import bisect
import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Final

from spectra_core import canon
from spectra_core.errors import CanonError, ProfileError, SchemaError, SpectraError
from spectra_core.ids import EventId, SourceId
from spectra_core.model import (
    CanonicalEvent,
    IntegrityClass,
    Interval,
    Licence,
    LicenceBasis,
    LivenessVerdict,
    Nanos,
    check_nanos,
)
from spectra_vs.calibrate import (
    IDENTITY_SPEC_HASH,
    U32_MAX,
    U64_MAX,
    ExcludedInterval,
    Phase,
    SourceProfile,
    check_phases,
    parse_quantile,
    phase_of,
    scf_bytes,
    scf_dumps,
)

__all__ = [
    "CALIBRATION_DEFICIENCY_REASONS",
    "CHAIN_LINK_CONTINUITY_ONLY",
    "LIVENESS_CONFIG_SCHEMA",
    "LIVENESS_SCHEMA",
    "OBSERVED_GAP_REASONS",
    "TAMPER_PASS_IMPLEMENTED",
    "AbsenceCounters",
    "AbsenceStatus",
    "BindingContext",
    "BindingGateFailure",
    "ChainState",
    "ChainStatus",
    "LicenceIssue",
    "LivenessConfig",
    "LivenessDocument",
    "LivenessFlags",
    "LivenessInterval",
    "LivenessMode",
    "NoTamperToken",
    "Reason",
    "SourceInput",
    "SourceLiveness",
    "ThresholdProvenance",
    "VoidedLicence",
    "WindowObservation",
    "absence_status",
    "breakpoints",
    "build_liveness_document",
    "calibration_deficiency",
    "chain_always_unverified",
    "check_binding_gates",
    "classify",
    "issue_licences",
    "licence_condition",
    "licences_for",
    "live",
    "liveness_hash",
    "load_liveness_config",
    "maximal_non_live_runs",
    "no_tamper_token",
    "observe_window",
    "parse_liveness_config",
    "require_binding_gates",
    "threshold_from_order_statistic",
    "write_liveness",
]


LIVENESS_SCHEMA: Final[str] = "spectra.liveness/2"
LIVENESS_CONFIG_SCHEMA: Final[str] = "spectra.vs.liveness_cfg/1"

#: The slice does not implement the Bellman-Ford backdating pass, so no source is ever
#: tamper_suspected and flag bit 5 is permanently false. The constant exists so that the
#: claim is a value a test can assert rather than a sentence in a comment.
TAMPER_PASS_IMPLEMENTED: Final[bool] = False


class LivenessMode(StrEnum):
    """The mode ladder. F4 SELF does not exist and no variant may be added for it.

    A run-derived threshold is the defect the calibration separation exists to prevent,
    so the type has no way to spell one.
    """

    F0_CALIBRATED = "F0_CALIBRATED"
    F1_INSUFFICIENT = "F1_INSUFFICIENT"
    F2_NO_PROFILE = "F2_NO_PROFILE"
    F3_DECLARED = "F3_DECLARED"


#: How much a mode establishes, weakest first. Used only to summarise a set of per-regime
#: modes into the document's per-source and global member; the weakest always wins, so a
#: summary can never read stronger than the weakest thing it summarises.
_MODE_STRENGTH: Final[dict[LivenessMode, int]] = {
    LivenessMode.F2_NO_PROFILE: 0,
    LivenessMode.F1_INSUFFICIENT: 1,
    LivenessMode.F3_DECLARED: 2,
    LivenessMode.F0_CALIBRATED: 3,
}


class Reason(StrEnum):
    """The closed reason vocabulary. Every non-LIVE verdict carries exactly one of these."""

    L_CALIBRATED_OK = "L_CALIBRATED_OK"
    B_FORCED_NO_PROFILE_MODE = "B_FORCED_NO_PROFILE_MODE"
    B_REGIME_UNKNOWN = "B_REGIME_UNKNOWN"
    B_PROFILE_INSUFFICIENT = "B_PROFILE_INSUFFICIENT"
    B_THRESHOLD_OVERFLOW = "B_THRESHOLD_OVERFLOW"
    B_CHAIN_UNVERIFIED = "B_CHAIN_UNVERIFIED"
    B_UNBRACKETED = "B_UNBRACKETED"
    B_WINDOW_UNDERSAMPLED = "B_WINDOW_UNDERSAMPLED"
    B_GAP_EXCEEDS_THRESHOLD = "B_GAP_EXCEEDS_THRESHOLD"
    S_CHAIN_SEQ_GAP = "S_CHAIN_SEQ_GAP"
    S_SEQ_GAP_UNAUTHENTICATED = "S_SEQ_GAP_UNAUTHENTICATED"
    B_INTERNAL_ERROR = "B_INTERNAL_ERROR"


#: Blindness that says this run was not calibrated for this source. A premium control
#: resting on these may never be described as needed because a sensor was blind; the
#: supported phrasing is that the run was not calibrated for that source.
CALIBRATION_DEFICIENCY_REASONS: Final[frozenset[Reason]] = frozenset(
    {
        Reason.B_PROFILE_INSUFFICIENT,
        Reason.B_REGIME_UNKNOWN,
        Reason.B_FORCED_NO_PROFILE_MODE,
        Reason.B_THRESHOLD_OVERFLOW,
        Reason.B_WINDOW_UNDERSAMPLED,
        # An internal failure is not an observed sensor gap either, and charging it to
        # the observed-gap partition would let a bug be rendered as evidence of silence.
        Reason.B_INTERNAL_ERROR,
    }
)

#: Blindness that says something about what the sensor did or did not deliver.
OBSERVED_GAP_REASONS: Final[frozenset[Reason]] = frozenset(
    {
        Reason.B_GAP_EXCEEDS_THRESHOLD,
        Reason.B_UNBRACKETED,
        Reason.B_CHAIN_UNVERIFIED,
        Reason.S_CHAIN_SEQ_GAP,
        Reason.S_SEQ_GAP_UNAUTHENTICATED,
    }
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DECIMAL: Final[re.Pattern[str]] = re.compile(
    r"(?:[0-9][0-9_]*)?\.[0-9]|[0-9][eE][+-]?[0-9]|\b(?:nan|inf)\b"
)
_QUOTED: Final[re.Pattern[str]] = re.compile(r"'[^']*'|\"[^\"]*\"")


@dataclass(frozen=True, slots=True)
class LivenessConfig:
    """config/vs/liveness.toml, hashed into the certificate.

    Every member is an integer or a rational spelled as two integers. There is no float
    anywhere, because a quantile read as a binary float is a quantile whose value depends
    on the platform that read it, and the threshold it produces would not replay.
    """

    quantile_num: int
    quantile_den: int
    slack_num: int
    slack_den: int
    k_tail: int
    n_floor: int
    m_min: int
    mcs_exact_cap: int
    schema: str = LIVENESS_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != LIVENESS_CONFIG_SCHEMA:
            raise SchemaError(f"LivenessConfig.schema must be {LIVENESS_CONFIG_SCHEMA!r}")
        for label in ("quantile_num", "quantile_den", "slack_num", "slack_den",
                      "k_tail", "n_floor", "m_min", "mcs_exact_cap"):
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SchemaError(f"LivenessConfig.{label} must be a non-negative int")
            canon.u32(value)
        if self.quantile_den == 0 or self.slack_den == 0:
            raise SchemaError("LivenessConfig: a zero denominator")
        if self.quantile_num > self.quantile_den:
            raise SchemaError("LivenessConfig: quantile exceeds one")
        if self.quantile_den == self.quantile_num:
            raise SchemaError(
                "LivenessConfig: q - p is zero, so n_min would be unbounded; "
                "a quantile of one has no tail to require samples from"
            )
        if self.m_min < 1:
            raise SchemaError("LivenessConfig.m_min must be at least one")

    @property
    def quantile(self) -> str:
        """The order-statistic level as it is spelled in the profile and the document."""
        return f"{self.quantile_num}/{self.quantile_den}"

    @property
    def slack(self) -> str:
        return f"{self.slack_num}/{self.slack_den}"

    @property
    def n_min(self) -> int:
        """`max(n_floor, ceil(k_tail * q / (q - p)))`, the gaps a regime needs for F0.

        The second term is what stops a quantile being taken from a vector too short to
        have a tail at that level: at 95/100 it demands a hundred gaps, so a regime with
        ninety is INSUFFICIENT and every window in it is BLIND rather than measured
        against a threshold that rests on five samples.
        """
        span = self.quantile_den - self.quantile_num
        tail = _ceil_div(self.k_tail * self.quantile_den, span)
        return self.n_floor if self.n_floor > tail else tail


def _ceil_div(numerator: int, denominator: int) -> int:
    """Integer ceiling for non-negative operands. No float division reaches any threshold."""
    if denominator <= 0:
        raise SchemaError("_ceil_div: denominator must be positive")
    return (numerator + denominator - 1) // denominator


_CONFIG_MEMBERS: Final[tuple[str, ...]] = (
    "k_tail",
    "m_min",
    "mcs_exact_cap",
    "n_floor",
    "quantile",
    "schema",
    "slack_den",
    "slack_num",
)


def _strip_comment(line: str) -> str:
    """Drop a TOML comment, honouring quotes so a `#` inside a string is not a comment."""
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def _reject_decimal_literals(text: str) -> None:
    """Reject a decimal or exponent literal in the config text before TOML parses it.

    TOML would parse a decimal quantile into a float and the value would then have to be
    rounded back, so the rejection happens on the text, where the literal is the bytes the
    author wrote. Comments go first and quoted substrings second, so that a quantile
    spelled `"95/100"` and a sentence in a comment are both out of scope.
    """
    for number, line in enumerate(text.split("\n"), start=1):
        if "\r" in line:
            raise CanonError(f"liveness.toml line {number}: a CR byte", code="E-LEX-001")
        stripped = _QUOTED.sub("", _strip_comment(line))
        if _DECIMAL.search(stripped) is not None:
            raise CanonError(
                f"liveness.toml line {number}: a decimal literal in a value position; "
                "rationals are spelled as two integers or as a '<p>/<q>' string",
                code="E-CANON-FLOAT",
            )


def _reject_floats(value: object, *, where: str) -> None:
    if isinstance(value, (float, complex)):
        raise CanonError(f"{where}: a float in the parsed config", code="E-CANON-FLOAT")
    if isinstance(value, dict):
        for key, member in value.items():
            _reject_floats(member, where=f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, member in enumerate(value):
            _reject_floats(member, where=f"{where}[{index}]")


def parse_liveness_config(text: str) -> LivenessConfig:
    """Parse the config text, rejecting every spelling the law forbids."""
    _reject_decimal_literals(text)
    parsed = tomllib.loads(text)
    _reject_floats(parsed, where="liveness_cfg")
    present = set(parsed)
    expected = set(_CONFIG_MEMBERS)
    if present - expected:
        raise SchemaError(
            f"liveness.toml: unknown member(s) {sorted(present - expected)}",
            code="E-SCHEMA-UNKNOWN",
        )
    if expected - present:
        raise SchemaError(
            f"liveness.toml: missing member(s) {sorted(expected - present)}",
            code="E-SCHEMA-MISSING",
        )
    quantile = parsed["quantile"]
    if not isinstance(quantile, str):
        raise SchemaError("liveness.toml: quantile must be the string '<p>/<q>'")
    p, q = parse_quantile(quantile)
    return LivenessConfig(
        schema=parsed["schema"],
        quantile_num=p,
        quantile_den=q,
        slack_num=parsed["slack_num"],
        slack_den=parsed["slack_den"],
        k_tail=parsed["k_tail"],
        n_floor=parsed["n_floor"],
        m_min=parsed["m_min"],
        mcs_exact_cap=parsed["mcs_exact_cap"],
    )


def load_liveness_config(path: str) -> LivenessConfig:
    with open(path, "rb") as handle:
        raw = handle.read()
    return parse_liveness_config(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# Binding gates B1..B6
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BindingContext:
    """The run-side values the gates compare a profile against.

    Every one of these is already hashed into the certificate, so a gate result is
    re-derivable by the checker from the same bytes rather than from this process.
    """

    bundle_hash: str
    seed: int
    generator_config_hash: str
    scenario_family: str
    excluded_intervals_hash: str

    def __post_init__(self) -> None:
        canon.parse_hash_ref(self.bundle_hash)
        canon.parse_hash_ref(self.generator_config_hash)
        canon.parse_hash_ref(self.excluded_intervals_hash)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise SchemaError("BindingContext.seed must be a non-negative int")
        canon.nfc(self.scenario_family)


@dataclass(frozen=True, slots=True)
class BindingGateFailure:
    gate: str
    code: str
    detail: str


def check_binding_gates(
    profile: SourceProfile, context: BindingContext
) -> tuple[BindingGateFailure, ...]:
    """Evaluate B1..B6 and return every failure, in gate order.

    Every failure is returned rather than the first, because a profile that fails three
    gates is a different diagnosis from one that fails one, and re-running to discover
    the next failure wastes the run that produced the evidence.
    """
    failures: list[BindingGateFailure] = []
    if profile.reference_bundle_hash == context.bundle_hash:
        failures.append(
            BindingGateFailure(
                "B1",
                "PROFILE_SELF_CALIBRATED",
                "the profile was calibrated on the bundle under analysis, so the "
                "threshold would rise with the degradation it is meant to detect",
            )
        )
    if profile.degradation_spec_hash != IDENTITY_SPEC_HASH:
        failures.append(
            BindingGateFailure(
                "B2",
                "PROFILE_FROM_DEGRADED_RUN",
                "the profile was calibrated under a degradation spec other than identity",
            )
        )
    low, high = profile.calibration_seed_band
    if low <= context.seed <= high:
        failures.append(
            BindingGateFailure(
                "B3",
                "PROFILE_SEED_OVERLAP",
                f"the run seed {context.seed} lies inside the calibration band",
            )
        )
    if profile.generator_config_hash != context.generator_config_hash:
        failures.append(
            BindingGateFailure("B4", "PROFILE_CONFIG_MISMATCH", "generator config differs")
        )
    if profile.scenario_family != context.scenario_family:
        failures.append(
            BindingGateFailure("B5", "PROFILE_FAMILY_MISMATCH", "scenario family differs")
        )
    if profile.excluded_intervals_hash != context.excluded_intervals_hash:
        failures.append(
            BindingGateFailure("B6", "PROFILE_INTERVALS_MISMATCH", "excluded intervals differ")
        )
    return tuple(failures)


def require_binding_gates(profile: SourceProfile, context: BindingContext) -> None:
    """Abort the run on the first gate failure.

    Aborting rather than degrading to BLIND: a profile that fails a gate is not weak
    evidence about arrival behaviour, it is evidence about a different run, and using it
    at all would put a number in the certificate that no honest reading supports.
    """
    failures = check_binding_gates(profile, context)
    if failures:
        first = failures[0]
        raise ProfileError(f"{first.gate}: {first.detail}", code=first.code)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


def threshold_from_order_statistic(
    q_value: int, slack_num: int, slack_den: int
) -> tuple[int, bool]:
    """`(ceil(Q * slack_num / slack_den), saturated)` in u64 nanoseconds.

    Saturation is returned rather than silently clamped, because a clamped threshold is
    the largest number there is and would call every silence normal. The caller turns a
    saturated threshold into BLIND with B_THRESHOLD_OVERFLOW.
    """
    if isinstance(q_value, bool) or not isinstance(q_value, int) or q_value < 0:
        raise SchemaError("threshold_from_order_statistic: Q must be a non-negative int")
    if slack_den <= 0 or slack_num < 0:
        raise SchemaError("threshold_from_order_statistic: slack must be a positive rational")
    raw = _ceil_div(q_value * slack_num, slack_den)
    if raw > U64_MAX:
        return (U64_MAX, True)
    return (raw, False)


@dataclass(frozen=True, slots=True)
class ThresholdProvenance:
    """Where a threshold came from. There is no run-derived variant and none may be added."""

    kind: str
    regime: str
    slack: str
    profile_id: str | None = None
    n: int | None = None
    p: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("profile", "declared"):
            raise SchemaError(
                "ThresholdProvenance.kind is 'profile' or 'declared'; a run-derived "
                "threshold is the defect the calibration separation exists to prevent"
            )
        if self.kind == "profile" and (self.profile_id is None or self.n is None or self.p is None):
            raise SchemaError("ThresholdProvenance: a profile threshold names its profile, n and p")
        if self.kind == "declared" and self.profile_id is not None:
            raise SchemaError("ThresholdProvenance: a declared threshold rests on no profile")

    def to_scf(self) -> dict[str, object]:
        out: dict[str, object] = {"kind": self.kind, "regime": self.regime, "slack": self.slack}
        if self.profile_id is not None:
            out["profile_id"] = self.profile_id
        if self.n is not None:
            out["n"] = self.n
        if self.p is not None:
            out["p"] = self.p
        return out


# ---------------------------------------------------------------------------
# Chain state
# ---------------------------------------------------------------------------


class ChainStatus(StrEnum):
    ABSENT = "ABSENT"
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True, slots=True)
class ChainState:
    status: ChainStatus
    first_bad: str | None = None
    missing_seq: tuple[int, int] | None = None
    witness: tuple[str, ...] = ()


#: A chain link check: `(previous, current)` returns True when `current` links to
#: `previous`, with `previous` None at the genesis of the span.
ChainVerifier = Callable[[CanonicalEvent | None, CanonicalEvent], bool]


def CHAIN_LINK_CONTINUITY_ONLY(previous: CanonicalEvent | None, current: CanonicalEvent) -> bool:
    """Check that each record's `chain_prev` is the predecessor's `chain_hash`.

    THIS IS WEAKER THAN THE SPECIFIED CHECK AND THE NARROWING IS DELIBERATE. The
    specification recomputes `chain_hash` from the record's own sealing preimage, which
    is owned by the ingest stage; recomputing it here would mean a second, independent
    spelling of that preimage, and the two spellings disagreeing would turn every
    chained source BLIND for a reason that has nothing to do with the sensor. Link
    continuity uses only what the bundle record carries, so it detects a break in the
    chain but not a record whose body was edited and whose hash was recomputed to match.
    Ingest owns the full recomputation and injects it as `chain_verifier` when it has
    one. Nothing here may be rendered as tamper detection.
    """
    if current.chain_hash is None or current.chain_prev is None:
        return False
    if previous is None:
        return True
    if previous.chain_hash is None:
        return False
    return current.chain_prev == previous.chain_hash


def chain_always_unverified(previous: CanonicalEvent | None, current: CanonicalEvent) -> bool:
    """The fail-closed verifier: every span on a linked source is UNVERIFIED, hence BLIND.

    Supplied for a caller that has no sealing implementation at all and would rather
    have every linked source blind than have liveness rest on a check it cannot make.
    """
    return False


# ---------------------------------------------------------------------------
# The breakpoint grid and the window observation
# ---------------------------------------------------------------------------


def breakpoints(
    event_times: tuple[int, ...],
    phase_boundaries: tuple[int, ...],
    query_endpoints: tuple[int, ...],
    t0_ns: Nanos,
    t1_ns: Nanos,
) -> tuple[int, ...]:
    """The grid for one source: sorted unique union, clipped to the scenario span.

    The envelope stage's query endpoints are part of the union, which is what makes the
    result independent of the order those queries arrive in: an endpoint that is already
    a breakpoint changes nothing, and permuting the queries permutes a set union.
    """
    check_nanos(t0_ns, where="breakpoints.t0_ns")
    check_nanos(t1_ns, where="breakpoints.t1_ns")
    if t1_ns < t0_ns:
        raise SchemaError("breakpoints: t1_ns precedes t0_ns")
    points = {t0_ns, t1_ns}
    for group in (event_times, phase_boundaries, query_endpoints):
        for value in group:
            check_nanos(value, where="breakpoints")
            if t0_ns <= value <= t1_ns:
                points.add(value)
    return tuple(sorted(points))


@dataclass(frozen=True, slots=True)
class WindowObservation:
    """What the bundle says about one source over one elementary interval.

    Point timestamps only. The skew-envelope interval semantics do not apply in this
    stage and `order_indeterminate` is not a liveness outcome, so there is no member for
    one.
    """

    regime: str | None
    left_bracket_t_ns: Nanos | None
    right_bracket_t_ns: Nanos | None
    n_records_in_span: int
    max_observed_gap_ns: int
    chain: ChainState


def observe_window(
    events: tuple[CanonicalEvent, ...],
    times: tuple[int, ...],
    a_ns: Nanos,
    b_ns: Nanos,
    phases: tuple[Phase, ...],
    integrity_class: IntegrityClass,
    chain_verifier: ChainVerifier,
) -> WindowObservation:
    """Bracket `[a_ns, b_ns)` with the records either side of it and read the span.

    The brackets reach outside the interval on purpose: a window with no record inside it
    is not evidence of silence unless we know when the source last spoke and when it
    spoke next, and a window with no bracket on either side is unbracketed rather than
    quiet.
    """
    regime = phase_of(phases, a_ns)
    left_index = bisect.bisect_right(times, a_ns) - 1
    right_index = bisect.bisect_left(times, b_ns)
    if left_index < 0 or right_index >= len(times):
        return WindowObservation(
            regime=regime,
            left_bracket_t_ns=None if left_index < 0 else times[left_index],
            right_bracket_t_ns=None if right_index >= len(times) else times[right_index],
            n_records_in_span=0,
            max_observed_gap_ns=0,
            chain=ChainState(ChainStatus.ABSENT)
            if integrity_class is IntegrityClass.NONE
            else ChainState(ChainStatus.VERIFIED),
        )

    span = events[left_index : right_index + 1]
    max_gap = 0
    for previous, current in zip(span, span[1:]):
        delta = current.t_evt_ns - previous.t_evt_ns
        if delta > max_gap:
            max_gap = delta

    return WindowObservation(
        regime=regime,
        left_bracket_t_ns=times[left_index],
        right_bracket_t_ns=times[right_index],
        n_records_in_span=len(span),
        max_observed_gap_ns=max_gap,
        chain=_chain_state(span, integrity_class, chain_verifier),
    )


def _chain_state(
    span: tuple[CanonicalEvent, ...],
    integrity_class: IntegrityClass,
    chain_verifier: ChainVerifier,
) -> ChainState:
    if integrity_class is IntegrityClass.NONE:
        return ChainState(ChainStatus.ABSENT)
    previous: CanonicalEvent | None = None
    for event in span:
        if not chain_verifier(previous, event):
            return ChainState(ChainStatus.UNVERIFIED, first_bad=str(event.event_id))
        previous = event
    for left, right in zip(span, span[1:]):
        if right.seq > left.seq + 1:
            witness = canon.sorted_unique((str(left.event_id), str(right.event_id)))
            return ChainState(
                ChainStatus.VERIFIED,
                missing_seq=(left.seq, right.seq),
                witness=witness,
            )
    return ChainState(ChainStatus.VERIFIED)


# ---------------------------------------------------------------------------
# Classification R1..R11
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Outcome:
    verdict: LivenessVerdict
    reason: Reason
    missing_seq: tuple[int, int] | None = None
    witness: tuple[str, ...] = ()


def classify(
    observation: WindowObservation,
    mode: LivenessMode,
    threshold_ns: int | None,
    saturated: bool,
    integrity_class: IntegrityClass,
    m_min: int,
) -> _Outcome:
    """Rules R1..R11, first match wins, in the normative order.

    R11 is the only place in this package that constructs LIVE. Every earlier rule is a
    reason to decline, and the ordering matters: the chain rules sit above the gap rules
    so that a span the source itself says is incomplete is never called live because the
    surviving records happened to arrive close together.
    """
    if mode is LivenessMode.F2_NO_PROFILE:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_FORCED_NO_PROFILE_MODE)
    if observation.regime is None:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_REGIME_UNKNOWN)
    if threshold_ns is None:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_PROFILE_INSUFFICIENT)
    if saturated:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_THRESHOLD_OVERFLOW)
    if observation.chain.status is ChainStatus.UNVERIFIED:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_CHAIN_UNVERIFIED)
    if observation.chain.missing_seq is not None:
        if integrity_class is IntegrityClass.CHAINED:
            return _Outcome(
                LivenessVerdict.SUPPRESSED,
                Reason.S_CHAIN_SEQ_GAP,
                observation.chain.missing_seq,
                observation.chain.witness,
            )
        if integrity_class is IntegrityClass.SEQUENCED:
            return _Outcome(
                LivenessVerdict.SUPPRESSED,
                Reason.S_SEQ_GAP_UNAUTHENTICATED,
                observation.chain.missing_seq,
                observation.chain.witness,
            )
    if observation.left_bracket_t_ns is None or observation.right_bracket_t_ns is None:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_UNBRACKETED)
    if observation.n_records_in_span < m_min:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_WINDOW_UNDERSAMPLED)
    if observation.max_observed_gap_ns > threshold_ns:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_GAP_EXCEEDS_THRESHOLD)
    return _Outcome(LivenessVerdict.LIVE, Reason.L_CALIBRATED_OK)


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LivenessInterval:
    """One RLE-merged run of elementary intervals sharing a verdict and a reason."""

    t0_ns: Nanos
    t1_ns: Nanos
    verdict: LivenessVerdict
    reason: Reason
    missing_seq: tuple[int, int] | None = None
    witness: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        Interval(self.t0_ns, self.t1_ns)
        if self.verdict is LivenessVerdict.SUPPRESSED:
            if self.missing_seq is None or not self.witness:
                raise SchemaError(
                    "LivenessInterval: a SUPPRESSED interval carries missing_seq and its "
                    "two bracketing record ids"
                )
        elif self.missing_seq is not None or self.witness:
            raise SchemaError(
                "LivenessInterval: missing_seq and witness belong to SUPPRESSED only; a "
                "BLIND interval carries a reason and no witness"
            )

    @property
    def interval(self) -> Interval:
        return Interval(self.t0_ns, self.t1_ns)

    @property
    def duration_ns(self) -> int:
        return self.t1_ns - self.t0_ns

    def to_scf(self) -> dict[str, object]:
        out: dict[str, object] = {
            "reason": str(self.reason),
            "t0_ns": str(self.t0_ns),
            "t1_ns": str(self.t1_ns),
            "verdict": str(self.verdict),
        }
        if self.missing_seq is not None:
            out["missing_seq"] = [self.missing_seq[0], self.missing_seq[1]]
        if self.witness:
            out["witness"] = list(self.witness)
        return out


@dataclass(frozen=True, slots=True)
class SourceLiveness:
    """One source's whole verdict timeline plus its blind-volume accounting."""

    source_id: SourceId
    integrity_class: IntegrityClass
    mode: LivenessMode
    intervals: tuple[LivenessInterval, ...]
    blind_volume_ns_by_reason: tuple[tuple[Reason, int], ...]
    suppressed_volume_ns: int
    threshold_ns: int | None = None
    threshold_provenance: ThresholdProvenance | None = None
    regime_thresholds: tuple[tuple[str, int], ...] = ()
    tamper_suspected: bool = False

    def __post_init__(self) -> None:
        if self.tamper_suspected:
            raise SchemaError(
                "SourceLiveness.tamper_suspected is always false in this slice: the "
                "difference-constraint backdating pass is not implemented and this "
                "package must never claim it detects tampering"
            )
        canon.check_strictly_ascending(
            self.intervals, lambda i: (i.t0_ns, i.t1_ns), where="intervals"
        )
        for left, right in zip(self.intervals, self.intervals[1:]):
            if left.t1_ns != right.t0_ns:
                raise SchemaError(
                    f"SourceLiveness {self.source_id}: intervals are not contiguous at "
                    f"{left.t1_ns}"
                )
        canon.check_strictly_ascending(
            self.blind_volume_ns_by_reason,
            lambda kv: canon.byte_order_key(str(kv[0])),
            where="blind_volume_ns_by_reason",
        )
        if (self.threshold_ns is None) != (self.threshold_provenance is None):
            raise SchemaError(
                "SourceLiveness: a threshold and its provenance are present or absent together"
            )
        if self.mode in (LivenessMode.F1_INSUFFICIENT, LivenessMode.F2_NO_PROFILE):
            if self.threshold_ns is not None:
                raise SchemaError(
                    f"SourceLiveness {self.source_id}: {self.mode} publishes no threshold"
                )

    def to_scf(self) -> dict[str, object]:
        out: dict[str, object] = {
            "blind_volume_ns_by_reason": {
                str(reason): str(volume) for reason, volume in self.blind_volume_ns_by_reason
            },
            "integrity_class": str(self.integrity_class),
            "intervals": [i.to_scf() for i in self.intervals],
            "mode": str(self.mode),
            "source_id": self.source_id.snake,
            "suppressed_volume_ns": str(self.suppressed_volume_ns),
            "tamper_suspected": self.tamper_suspected,
        }
        if self.threshold_ns is not None and self.threshold_provenance is not None:
            out["threshold_ns"] = str(self.threshold_ns)
            out["threshold_provenance"] = self.threshold_provenance.to_scf()
        return out


@dataclass(frozen=True, slots=True)
class LivenessFlags:
    liveness_uncalibrated: bool = False
    liveness_unauthenticated: bool = False
    blind_by_default: bool = False
    profile_regime_collapsed: bool = False
    verdict_tamper_sensitive: bool = False
    mcs_greedy: bool = False

    def __post_init__(self) -> None:
        if self.verdict_tamper_sensitive:
            raise SchemaError(
                "LivenessFlags.verdict_tamper_sensitive is always false in this slice"
            )

    def to_scf(self) -> dict[str, object]:
        return {
            "blind_by_default": self.blind_by_default,
            "liveness_unauthenticated": self.liveness_unauthenticated,
            "liveness_uncalibrated": self.liveness_uncalibrated,
            "mcs_greedy": self.mcs_greedy,
            "profile_regime_collapsed": self.profile_regime_collapsed,
            "verdict_tamper_sensitive": self.verdict_tamper_sensitive,
        }


@dataclass(frozen=True, slots=True)
class LivenessDocument:
    """runs/<id>/liveness.json. The only producer of licences in the pipeline."""

    mode_global: LivenessMode
    quantile: str
    slack: str
    n_min: int
    m_min: int
    sources: tuple[SourceLiveness, ...]
    flags: LivenessFlags
    profile_id: str | None = None
    schema: str = LIVENESS_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != LIVENESS_SCHEMA:
            raise SchemaError(f"LivenessDocument.schema must be {LIVENESS_SCHEMA!r}")
        parse_quantile(self.quantile)
        canon.u32(self.n_min)
        canon.u32(self.m_min)
        canon.check_strictly_ascending(
            self.sources, lambda s: canon.byte_order_key(str(s.source_id)), where="sources"
        )
        if self.profile_id is not None:
            canon.parse_hash_ref(self.profile_id)
        if self.mode_global is LivenessMode.F2_NO_PROFILE and self.profile_id is not None:
            raise SchemaError("LivenessDocument: F2_NO_PROFILE names no profile")

    def source(self, source_id: str) -> SourceLiveness | None:
        wanted = str(source_id)
        for entry in self.sources:
            if str(entry.source_id) == wanted or entry.source_id.snake == wanted:
                return entry
        return None

    def to_scf(self) -> dict[str, object]:
        out: dict[str, object] = {
            "flags": self.flags.to_scf(),
            "m_min": self.m_min,
            "mode_global": str(self.mode_global),
            "n_min": self.n_min,
            "quantile": self.quantile,
            "schema": self.schema,
            "slack": self.slack,
            "sources": [s.to_scf() for s in self.sources],
        }
        if self.profile_id is not None:
            out["profile_id"] = self.profile_id
        return out

    def canonical_bytes(self) -> bytes:
        return scf_bytes(self.to_scf(), where="liveness")

    def canonical_text(self) -> str:
        return scf_dumps(self.to_scf(), where="liveness")


def liveness_hash(document: LivenessDocument) -> str:
    """The certificate's `liveness_hash`, over the canonical bytes of the document."""
    return canon.hash_ref("live", document.canonical_bytes())


def write_liveness(document: LivenessDocument, path: str) -> str:
    """Write the artifact in binary mode and return its hash.

    Binary mode because text mode on this platform would translate the LF and every
    downstream hash would then be over bytes the emitter never computed.
    """
    data = document.canonical_bytes()
    with open(path, "wb") as handle:
        handle.write(data)
    return canon.hash_ref("live", data)


# ---------------------------------------------------------------------------
# Building the document
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceInput:
    """One declared source and the bundle records it produced, which may be none."""

    source_id: SourceId
    integrity_class: IntegrityClass
    events: tuple[CanonicalEvent, ...] = ()
    nominal_period_ns: Nanos | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, SourceId):
            raise SchemaError("SourceInput.source_id must be a SourceId")
        if not isinstance(self.integrity_class, IntegrityClass):
            raise SchemaError("SourceInput.integrity_class must be an IntegrityClass")
        if self.nominal_period_ns is not None and self.nominal_period_ns <= 0:
            raise SchemaError("SourceInput.nominal_period_ns must be positive when present")


def _sorted_events(events: tuple[CanonicalEvent, ...]) -> tuple[CanonicalEvent, ...]:
    return tuple(
        sorted(events, key=lambda e: (e.t_evt_ns, e.seq, canon.byte_order_key(str(e.event_id))))
    )


def _regime_threshold(
    profile: SourceProfile | None,
    source: SourceInput,
    regime_id: str,
    config: LivenessConfig,
    allow_declared_profile: bool,
) -> tuple[LivenessMode, int | None, bool, ThresholdProvenance | None]:
    """The mode, threshold and provenance for one (source, regime).

    F0 is reachable only with a profile entry that carries the configured order statistic
    over at least n_min gaps. Everything else lands in F3 when a declared period was
    explicitly allowed, and in F1 otherwise, and F1 means every window in that regime is
    BLIND. There is no fourth outcome that derives a number from the run.
    """
    if profile is not None:
        entry = profile.source(source.source_id.snake)
        regime = entry.regime(regime_id) if entry is not None else None
        if regime is not None and regime.n_gaps >= config.n_min:
            q_value = regime.order_statistic(config.quantile)
            if q_value is not None:
                threshold, saturated = threshold_from_order_statistic(
                    q_value, config.slack_num, config.slack_den
                )
                provenance = ThresholdProvenance(
                    kind="profile",
                    regime=regime_id,
                    slack=config.slack,
                    profile_id=profile.profile_id,
                    n=regime.n_gaps,
                    p=config.quantile,
                )
                return (LivenessMode.F0_CALIBRATED, threshold, saturated, provenance)
    if allow_declared_profile and source.nominal_period_ns is not None:
        threshold, saturated = threshold_from_order_statistic(
            source.nominal_period_ns, config.slack_num, config.slack_den
        )
        provenance = ThresholdProvenance(kind="declared", regime=regime_id, slack=config.slack)
        return (LivenessMode.F3_DECLARED, threshold, saturated, provenance)
    return (LivenessMode.F1_INSUFFICIENT, None, False, None)


def _merge(outcomes: list[tuple[int, int, _Outcome]]) -> tuple[LivenessInterval, ...]:
    """RLE-merge consecutive elementary intervals sharing a verdict and a reason.

    The merge key includes `missing_seq` and the witness as well as the verdict and the
    reason. Two SUPPRESSED runs that name different missing sequence numbers are two
    different statements, and merging them would force one of the two witnesses to be
    discarded; a narrower merge only ever emits more intervals, never fewer.
    """
    merged: list[LivenessInterval] = []
    for t0, t1, outcome in outcomes:
        if merged:
            last = merged[-1]
            same = (
                last.verdict is outcome.verdict
                and last.reason is outcome.reason
                and last.missing_seq == outcome.missing_seq
                and last.witness == outcome.witness
            )
            if same and last.t1_ns == t0:
                merged[-1] = LivenessInterval(
                    t0_ns=last.t0_ns,
                    t1_ns=t1,
                    verdict=last.verdict,
                    reason=last.reason,
                    missing_seq=last.missing_seq,
                    witness=last.witness,
                )
                continue
        merged.append(
            LivenessInterval(
                t0_ns=t0,
                t1_ns=t1,
                verdict=outcome.verdict,
                reason=outcome.reason,
                missing_seq=outcome.missing_seq,
                witness=outcome.witness,
            )
        )
    return tuple(merged)


def build_liveness_document(
    *,
    config: LivenessConfig,
    sources: tuple[SourceInput, ...],
    phases: tuple[Phase, ...],
    scenario_t0_ns: Nanos,
    scenario_t1_ns: Nanos,
    profile: SourceProfile | None = None,
    binding_context: BindingContext | None = None,
    query_endpoints: tuple[int, ...] = (),
    no_profile: bool = False,
    allow_declared_profile: bool = False,
    chain_verifier: ChainVerifier = CHAIN_LINK_CONTINUITY_ONLY,
    excluded: tuple[ExcludedInterval, ...] = (),
) -> LivenessDocument:
    """Classify every source over every elementary interval and assemble the artifact.

    `no_profile` and `profile` are mutually exclusive and one of them is required. The
    caller is made to say which, because a run that silently proceeded without a profile
    would produce a document that looks calibrated and is not; F2 sets
    `blind_by_default` so that the absence travels with the result.
    """
    if no_profile and profile is not None:
        raise ProfileError(
            "build_liveness_document: --no-profile and a profile are mutually exclusive",
            code="PROFILE_INVALID",
        )
    if not no_profile and profile is None:
        raise ProfileError(
            "build_liveness_document: pass a profile or state --no-profile; proceeding "
            "without saying which would hide an uncalibrated run",
            code="PROFILE_INVALID",
        )
    if profile is not None:
        if binding_context is None:
            raise ProfileError(
                "build_liveness_document: a profile requires the run values that gates "
                "B1..B6 compare it against",
                code="PROFILE_INVALID",
            )
        require_binding_gates(profile, binding_context)
    check_phases(phases)
    check_nanos(scenario_t0_ns, where="scenario_t0_ns")
    check_nanos(scenario_t1_ns, where="scenario_t1_ns")
    if scenario_t1_ns <= scenario_t0_ns:
        raise SchemaError("build_liveness_document: the scenario span is empty")
    for value in query_endpoints:
        check_nanos(value, where="query_endpoints")

    phase_bounds = tuple(sorted({p.t0_ns for p in phases} | {p.t1_ns for p in phases}))
    built: list[SourceLiveness] = []
    unauthenticated = False

    for source in canon.sorted_by_bytes(sources, lambda s: str(s.source_id)):
        events = _sorted_events(source.events)
        times = tuple(e.t_evt_ns for e in events)
        grid = breakpoints(
            times, phase_bounds, tuple(query_endpoints), scenario_t0_ns, scenario_t1_ns
        )
        cache: dict[str, tuple[LivenessMode, int | None, bool, ThresholdProvenance | None]] = {}
        outcomes: list[tuple[int, int, _Outcome]] = []
        modes_used: list[LivenessMode] = []

        for a_ns, b_ns in zip(grid, grid[1:]):
            observation, mode, threshold, saturated = _observe_and_mode(
                events=events,
                times=times,
                a_ns=a_ns,
                b_ns=b_ns,
                phases=phases,
                source=source,
                profile=profile,
                config=config,
                no_profile=no_profile,
                allow_declared_profile=allow_declared_profile,
                chain_verifier=chain_verifier,
                cache=cache,
            )
            if observation.regime is not None:
                modes_used.append(mode)
            outcomes.append(
                (
                    a_ns,
                    b_ns,
                    _classify_guarded(
                        observation, mode, threshold, saturated, source.integrity_class, config.m_min
                    ),
                )
            )

        intervals = _merge(outcomes)
        blind_volume: dict[Reason, int] = {}
        suppressed_volume = 0
        for entry in intervals:
            if entry.verdict is LivenessVerdict.BLIND:
                blind_volume[entry.reason] = blind_volume.get(entry.reason, 0) + entry.duration_ns
            elif entry.verdict is LivenessVerdict.SUPPRESSED:
                suppressed_volume += entry.duration_ns
                if entry.reason is Reason.S_SEQ_GAP_UNAUTHENTICATED:
                    unauthenticated = True

        source_mode = _weakest_mode(modes_used, no_profile)
        thresholds = tuple(
            sorted(
                {
                    (regime_id, value[1])
                    for regime_id, value in cache.items()
                    if value[1] is not None
                },
                key=lambda kv: (canon.byte_order_key(kv[0]), kv[1]),
            )
        )
        published_threshold: int | None = None
        published_provenance: ThresholdProvenance | None = None
        if len(cache) == 1:
            only = next(iter(cache.values()))
            if only[1] is not None and only[3] is not None and not only[2]:
                published_threshold, published_provenance = only[1], only[3]

        built.append(
            SourceLiveness(
                source_id=source.source_id,
                integrity_class=source.integrity_class,
                mode=source_mode,
                intervals=intervals,
                blind_volume_ns_by_reason=tuple(
                    sorted(
                        blind_volume.items(), key=lambda kv: canon.byte_order_key(str(kv[0]))
                    )
                ),
                suppressed_volume_ns=suppressed_volume,
                threshold_ns=published_threshold,
                threshold_provenance=published_provenance,
                regime_thresholds=thresholds,
            )
        )

    source_modes = [entry.mode for entry in built]
    mode_global = (
        LivenessMode.F2_NO_PROFILE if no_profile else _weakest_mode(source_modes, no_profile)
    )
    flags = LivenessFlags(
        liveness_uncalibrated=any(
            entry.mode in (LivenessMode.F1_INSUFFICIENT, LivenessMode.F3_DECLARED)
            for entry in built
        ),
        liveness_unauthenticated=unauthenticated,
        blind_by_default=no_profile,
        profile_regime_collapsed=bool(profile is not None and profile.regime_collapsed),
    )
    return LivenessDocument(
        mode_global=mode_global,
        profile_id=None if profile is None else profile.profile_id,
        quantile=config.quantile,
        slack=config.slack,
        n_min=config.n_min,
        m_min=config.m_min,
        sources=tuple(built),
        flags=flags,
    )


def _observe_and_mode(
    *,
    events: tuple[CanonicalEvent, ...],
    times: tuple[int, ...],
    a_ns: int,
    b_ns: int,
    phases: tuple[Phase, ...],
    source: SourceInput,
    profile: SourceProfile | None,
    config: LivenessConfig,
    no_profile: bool,
    allow_declared_profile: bool,
    chain_verifier: ChainVerifier,
    cache: dict[str, tuple[LivenessMode, int | None, bool, ThresholdProvenance | None]],
) -> tuple[WindowObservation, LivenessMode, int | None, bool]:
    observation = observe_window(
        events, times, a_ns, b_ns, phases, source.integrity_class, chain_verifier
    )
    if no_profile:
        return (observation, LivenessMode.F2_NO_PROFILE, None, False)
    if observation.regime is None:
        return (observation, LivenessMode.F1_INSUFFICIENT, None, False)
    if observation.regime not in cache:
        cache[observation.regime] = _regime_threshold(
            profile, source, observation.regime, config, allow_declared_profile
        )
    mode, threshold, saturated, _ = cache[observation.regime]
    return (observation, mode, threshold, saturated)


def _classify_guarded(
    observation: WindowObservation,
    mode: LivenessMode,
    threshold: int | None,
    saturated: bool,
    integrity_class: IntegrityClass,
    m_min: int,
) -> _Outcome:
    """Convert any internal failure into BLIND rather than failing the run.

    This is the one place a broad exception handler is correct: it can only produce
    BLIND, never LIVE, so a bug here loses information instead of manufacturing it. The
    reason code is in the calibration-deficiency partition, so a control resting on it
    is never described as resting on an observed sensor gap.
    """
    try:
        return classify(observation, mode, threshold, saturated, integrity_class, m_min)
    except Exception:
        return _Outcome(LivenessVerdict.BLIND, Reason.B_INTERNAL_ERROR)


def _weakest_mode(modes: list[LivenessMode], no_profile: bool) -> LivenessMode:
    if no_profile:
        return LivenessMode.F2_NO_PROFILE
    if not modes:
        return LivenessMode.F1_INSUFFICIENT
    weakest = modes[0]
    for mode in modes[1:]:
        if _MODE_STRENGTH[mode] < _MODE_STRENGTH[weakest]:
            weakest = mode
    return weakest


# ---------------------------------------------------------------------------
# Licences
# ---------------------------------------------------------------------------


class LicenceError(SpectraError):
    """A licence was asked for over an interval the pinned document does not license."""

    CODE = "E-LICENSE-UNIMPLIED"


def _intervals_of(document: LivenessDocument, source_id: str) -> tuple[LivenessInterval, ...]:
    entry = document.source(source_id)
    if entry is None:
        raise LicenceError(f"source {source_id!r} is absent from the liveness document")
    return entry.intervals


def live(document: LivenessDocument, source_id: str, interval: Interval) -> bool:
    """True iff every elementary interval contained in `interval` is LIVE on this source.

    An interval reaching outside the document's grid is NOT live. Uncovered time is time
    nothing was said about, and the fail-closed reading of silence about silence is that
    the source was not live.
    """
    intervals = _intervals_of(document, source_id)
    if not intervals:
        return False
    if interval.is_empty:
        return False
    if interval.t0_ns < intervals[0].t0_ns or interval.t1_ns > intervals[-1].t1_ns:
        return False
    for entry in intervals:
        if entry.interval.overlaps(interval) and entry.verdict is not LivenessVerdict.LIVE:
            return False
    return True


def maximal_non_live_runs(document: LivenessDocument, source_id: str) -> tuple[Interval, ...]:
    """The maximal runs over which this source is not LIVE, merged across reasons.

    Used for rendering a decisive observation as one span rather than as a list of
    differently-reasoned fragments. Licences are issued per fragment, not per run, so
    that each one keeps its own reason.
    """
    runs: list[Interval] = []
    for entry in _intervals_of(document, source_id):
        if entry.verdict is LivenessVerdict.LIVE:
            continue
        if runs and runs[-1].t1_ns == entry.t0_ns:
            runs[-1] = Interval(runs[-1].t0_ns, entry.t1_ns)
        else:
            runs.append(entry.interval)
    return tuple(runs)


def licences_for(
    document: LivenessDocument, source_id: str, interval: Interval
) -> tuple[Licence, ...]:
    """Every licence covering `interval` on one source, one per merged non-LIVE fragment.

    Raises rather than returning an empty tuple when the interval is not fully covered by
    non-LIVE time. An empty tuple would read as `no licence needed`, which is the same
    shape as `licence granted with nothing to show`, and those two must not be confusable
    at a call site.
    """
    entry_list = _intervals_of(document, source_id)
    if interval.is_empty:
        raise LicenceError(f"{source_id}: an empty interval licenses nothing")
    covering = [e for e in entry_list if e.interval.overlaps(interval)]
    if not covering:
        raise LicenceError(f"{source_id}: {interval} lies outside the liveness grid")
    if covering[0].t0_ns > interval.t0_ns or covering[-1].t1_ns < interval.t1_ns:
        raise LicenceError(f"{source_id}: {interval} is not fully covered by the liveness grid")
    for fragment in covering:
        if fragment.verdict is LivenessVerdict.LIVE:
            raise LicenceError(
                f"{source_id}: {interval} overlaps LIVE time and is therefore not licensed"
            )
    licences = [
        Licence.mint(
            source_id=SourceId.of(source_id) if not str(source_id).startswith("src:") else SourceId(source_id),
            interval=fragment.interval,
            basis=(
                LicenceBasis.SUPPRESSED
                if fragment.verdict is LivenessVerdict.SUPPRESSED
                else LicenceBasis.BLIND
            ),
            reason=str(fragment.reason),
            witness=tuple(EventId(w) for w in fragment.witness),
        )
        for fragment in covering
    ]
    return tuple(sorted(licences, key=lambda lic: lic.sort_key()))


def licence_condition(
    document: LivenessDocument, producing_sources: tuple[str, ...], interval: Interval
) -> bool:
    """The S9 admissibility test: not live on EVERY producing source over `interval`.

    Every, not any. One producing source that was live over the span is a source that
    would have recorded the step, so the step being absent is evidence of absence rather
    than absence of evidence.
    """
    if not producing_sources:
        return False
    return all(not live(document, source_id, interval) for source_id in producing_sources)


@dataclass(frozen=True, slots=True)
class VoidedLicence:
    """A licence that was withheld, kept as data so that withholding is never invisible."""

    license_id: str
    source_id: str
    t0_ns: Nanos
    t1_ns: Nanos
    reason: str


@dataclass(frozen=True, slots=True)
class LicenceIssue:
    """The result of asking for permission to instantiate a silent step over an interval."""

    granted: bool
    licences: tuple[Licence, ...] = ()
    voided: tuple[VoidedLicence, ...] = ()
    blocked_sources: tuple[str, ...] = ()
    license_voided_by_suspected_tampering: bool = False


def issue_licences(
    document: LivenessDocument,
    producing_sources: tuple[str, ...],
    interval: Interval,
    voided_license_ids: tuple[str, ...] = (),
) -> LicenceIssue:
    """Grant or refuse permission to instantiate an unobserved step over `interval`.

    On a refusal the reason is returned, not swallowed: `blocked_sources` names the
    sources that were live.

    ON VOIDING. If any licence this instance would rest on is in `voided_license_ids`,
    the instance is REFUSED and the flag is raised. It is not quietly issued with a
    smaller licence set. Shrinking the licensed set shrinks P_max, and a smaller P_max
    can only make a verdict look safer, so an attacker able to make licences look
    untrustworthy could otherwise manufacture safety by discrediting them. The flag is
    in the soundness class and blocks ROBUST, which is what makes the attack cost the
    attacker the verdict they wanted. In this slice nothing ever populates
    `voided_license_ids`; the path exists so that adding the backdating pass does not
    require rewriting this decision.
    """
    if not producing_sources:
        return LicenceIssue(granted=False)
    blocked: list[str] = []
    collected: list[Licence] = []
    for source_id in canon.sorted_unique(producing_sources):
        if live(document, source_id, interval):
            blocked.append(source_id)
            continue
        try:
            collected.extend(licences_for(document, source_id, interval))
        except LicenceError:
            blocked.append(source_id)
    if blocked:
        return LicenceIssue(granted=False, blocked_sources=tuple(blocked))

    voided = tuple(
        VoidedLicence(
            license_id=str(lic.license_id),
            source_id=lic.source_id.snake,
            t0_ns=lic.t0_ns,
            t1_ns=lic.t1_ns,
            reason=lic.reason,
        )
        for lic in collected
        if str(lic.license_id) in set(voided_license_ids)
    )
    if voided:
        return LicenceIssue(
            granted=False,
            voided=tuple(sorted(voided, key=lambda v: (v.source_id, v.t0_ns, v.t1_ns))),
            license_voided_by_suspected_tampering=True,
        )
    return LicenceIssue(
        granted=True, licences=tuple(sorted(collected, key=lambda lic: lic.sort_key()))
    )


# ---------------------------------------------------------------------------
# Absence, the only permitted negation
# ---------------------------------------------------------------------------


class AbsenceStatus(StrEnum):
    """How an absence over a sealed lookback may be read.

    LICENSED and UNDETERMINED both keep the fact out of P_min: a fact nobody could have
    seen the negation of is not an observation, and it may enter only the upper side of
    the bracket.
    """

    OBSERVED = "OBSERVED"
    LICENSED = "LICENSED"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True, slots=True)
class AbsenceCounters:
    """Tallies S9 folds into its own reporting; see the note in `absence_status`."""

    observed: int = 0
    licensed: int = 0
    undetermined: int = 0


def absence_status(
    document: LivenessDocument, producing_sources: tuple[str, ...], lookback: Interval
) -> AbsenceStatus:
    """Classify an absence over a sealed lookback into the three permitted readings.

    THE COUNTERS ARE NOT IN THE DOCUMENT. The specification's liveness prose says
    absence_observed / absence_licensed / absence_undetermined go into liveness.json,
    while the LivenessDoc field table gives the document's members exactly and has no
    place for them. The field table is what a checker is generated from, so adding a
    member it does not declare would make every document unparseable to that checker,
    whereas omitting the counters loses only a tally. They are returned from here instead
    and S9 reports them.
    """
    if not producing_sources:
        return AbsenceStatus.UNDETERMINED
    all_live = all(live(document, s, lookback) for s in producing_sources)
    if all_live:
        return AbsenceStatus.OBSERVED
    none_live = all(not live(document, s, lookback) for s in producing_sources)
    if none_live:
        return AbsenceStatus.LICENSED
    return AbsenceStatus.UNDETERMINED


# ---------------------------------------------------------------------------
# Blind-volume accounting
# ---------------------------------------------------------------------------


def _gcd(a: int, b: int) -> int:
    """Euclid, written out because the liveness module may not import a maths library."""
    while b:
        a, b = b, a % b
    return a


def calibration_deficiency(licences: tuple[Licence, ...]) -> tuple[int, int]:
    """The share of a control's licensed time that rests on missing calibration.

    Returned as an exact rational in lowest terms so that a premium control can be
    described correctly: a control resting on B_PROFILE_INSUFFICIENT is needed because
    this run was not calibrated for that source, which is a different sentence from
    needed because a sensor could not see, and the two must never be interchanged.
    """
    deficient = 0
    total = 0
    for licence in licences:
        span = licence.t1_ns - licence.t0_ns
        total += span
        try:
            reason = Reason(licence.reason)
        except ValueError:
            continue
        if reason in CALIBRATION_DEFICIENCY_REASONS:
            deficient += span
    if total == 0:
        return (0, 1)
    divisor = _gcd(deficient, total)
    if divisor == 0:
        return (0, 1)
    num, den = deficient // divisor, total // divisor
    if den > U32_MAX or num > U32_MAX:
        raise CanonError(
            "calibration_deficiency: the exact rational does not fit u32/u32",
            code="E-CANON-WIDTH",
        )
    return (num, den)


# ---------------------------------------------------------------------------
# The no-tamper token
# ---------------------------------------------------------------------------

_SEAL: Final[object] = object()


@dataclass(frozen=True, slots=True)
class NoTamperToken:
    """Evidence that no source is tamper_suspected, required to mint a ROBUST verdict.

    The token exists so that the backdating pass can be added later without reworking the
    verdict type. It cannot be constructed outside this module, so a caller cannot
    assert the property it stands for.
    """

    _seal: object

    def __post_init__(self) -> None:
        if self._seal is not _SEAL:
            raise SchemaError(
                "NoTamperToken is minted by the liveness stage, not by its consumers",
                code="VRD-010",
            )


def no_tamper_token(document: LivenessDocument) -> NoTamperToken | None:
    """Mint the token, or None when the document cannot support it.

    In this slice the token is always minted, because the backdating pass does not exist
    and therefore nothing is ever tamper_suspected. That is an absence of a check, not a
    finding of cleanliness, and no rendering may present it as one.
    """
    if document.flags.verdict_tamper_sensitive:
        return None
    if any(entry.tamper_suspected for entry in document.sources):
        return None
    return NoTamperToken(_SEAL)
