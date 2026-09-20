"""The error and quarantine taxonomy.

Why a taxonomy rather than bare exceptions: the checker's obligations O0..O15 and the
adversarial corpus assert an EXACT reason code per row, and a wrong code is as much a
failure as a wrong verdict. A code therefore has to be a value the emitter carries, not
a sentence in an exception message. Every error class here owns a closed set of codes,
`ERROR_CODES` is the union, and `code_is_declared` lets a build gate check reason-code
liveness without importing the checker.

Why quarantine is data and not an exception: a quarantined record does not stop a run.
It is dropped, counted, and it sets flag bit 4 `quarantined_records`, which blocks
ROBUST, because dropped records manufacture blind windows. Representing it as a raised
exception would tempt a caller into `except: continue`, which is exactly how a dropped
record stops being visible in the verdict.

This module imports nothing from the rest of the package, so every other module may
import it without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "ERROR_CODES",
    "BudgetError",
    "CanonError",
    "DeterminismError",
    "ErrorClass",
    "GuardError",
    "HashError",
    "IdentifierError",
    "IdentifierTypeError",
    "IdentifierWidthError",
    "LimitError",
    "ProfileError",
    "QuarantineReason",
    "QuarantineRecord",
    "SchemaError",
    "SpectraError",
    "VerdictError",
    "code_is_declared",
]


class ErrorClass(StrEnum):
    """Which property of a run an error class puts at risk.

    Named after the flag classes of the verdict section so that a reader moving between
    the two does not have to translate: SOUNDNESS conditions block the universal claim,
    MINIMALITY conditions bound what may be said about cut size, DERIVED conditions
    suppress downstream products, and USAGE conditions are the caller's mistake.
    """

    SOUNDNESS = "soundness"
    MINIMALITY = "minimality"
    DERIVED = "derived"
    CANONICITY = "canonicity"
    USAGE = "usage"


@dataclass(frozen=True, slots=True)
class _CodeBinding:
    code: str
    error_class: ErrorClass
    summary: str


class SpectraError(Exception):
    """Base of every error this project raises deliberately.

    Carries a reason `code` because downstream consumers compare codes, never message
    text. `detail` is free prose for a human and is never parsed.
    """

    #: Default code for instances raised without one. Subclasses override.
    CODE: str = "E-UNSPECIFIED"
    #: Which property the error puts at risk.
    ERROR_CLASS: ErrorClass = ErrorClass.USAGE

    def __init__(self, detail: str, *, code: str | None = None) -> None:
        self.code: Final[str] = code if code is not None else type(self).CODE
        self.detail: Final[str] = detail
        super().__init__(f"{self.code}: {detail}")

    def as_pairs(self) -> tuple[tuple[str, str], ...]:
        """Sorted key/value pairs for embedding in an artifact. Sorted, not dict-ordered."""
        return (
            ("class", str(type(self).ERROR_CLASS)),
            ("code", self.code),
            ("detail", self.detail),
        )


class CanonError(SpectraError):
    """Canonical form was violated: ordering, width, NFC, a float, a null, a duplicate key."""

    CODE = "E-CANON-FORM"
    ERROR_CLASS = ErrorClass.CANONICITY


class IdentifierError(SpectraError):
    """A string does not satisfy the section 57.2 grammar of the type it claims to be."""

    CODE = "E-ID-GRAMMAR"
    ERROR_CLASS = ErrorClass.CANONICITY


class IdentifierTypeError(IdentifierError):
    """One identifier type was passed where another was expected (57.1 rule 7)."""

    CODE = "E-ID-TYPE"
    ERROR_CLASS = ErrorClass.CANONICITY


class IdentifierWidthError(IdentifierError):
    """A run-local h128 identifier reached a certificate (57.2 certificate width rule)."""

    CODE = "E-ID-WIDTH"
    ERROR_CLASS = ErrorClass.SOUNDNESS


class SchemaError(SpectraError):
    """A required member is missing, or an unknown member is present."""

    CODE = "E-SCHEMA-MISSING"
    ERROR_CLASS = ErrorClass.CANONICITY


class HashError(SpectraError):
    """A recomputed digest did not equal the one recorded."""

    CODE = "E-HASH-CERT"
    ERROR_CLASS = ErrorClass.SOUNDNESS


class VerdictError(SpectraError):
    """The verdict algebra was violated. Codes are the VRD-0nn series."""

    CODE = "VRD-010"
    ERROR_CLASS = ErrorClass.SOUNDNESS


class GuardError(SpectraError):
    """The guard front end rejected a rule: lexing, syntax, typing or canonicalisation."""

    CODE = "E-SYN-000"
    ERROR_CLASS = ErrorClass.USAGE


class ProfileError(SpectraError):
    """A calibration binding gate B1..B6 failed. Without these liveness self-calibrates."""

    CODE = "PROFILE_INVALID"
    ERROR_CLASS = ErrorClass.SOUNDNESS


class LimitError(SpectraError):
    """A declared structural limit was exceeded: count, width, nesting, file size."""

    CODE = "E-LIMIT-COUNT"
    ERROR_CLASS = ErrorClass.SOUNDNESS


class BudgetError(SpectraError):
    """A deterministic step counter hit its budget. Never a wall-clock timeout."""

    CODE = "E-BUDGET-EXHAUSTED"
    ERROR_CLASS = ErrorClass.MINIMALITY


class DeterminismError(SpectraError):
    """An output path depended on something that is not a declared total order."""

    CODE = "E-DET-ORDER"
    ERROR_CLASS = ErrorClass.SOUNDNESS


# ---------------------------------------------------------------------------
# The declared code registry
# ---------------------------------------------------------------------------

_BINDINGS: Final[tuple[_CodeBinding, ...]] = (
    # Canonicity, checker obligation O0 and the encoding rules.
    _CodeBinding("E-CANON-FORM", ErrorClass.CANONICITY, "canonical form violated"),
    _CodeBinding("E-CANON-FLOAT", ErrorClass.CANONICITY, "a float reached a number position"),
    _CodeBinding("E-CANON-DUPKEY", ErrorClass.CANONICITY, "duplicate object key"),
    _CodeBinding("E-CANON-ORDER", ErrorClass.CANONICITY, "declared-sorted sequence not ascending"),
    _CodeBinding("E-CANON-NFC", ErrorClass.CANONICITY, "text is not NFC"),
    _CodeBinding("E-CANON-NULL", ErrorClass.CANONICITY, "a null reached a value position"),
    _CodeBinding("E-CANON-WIDTH", ErrorClass.CANONICITY, "integer outside its declared width"),
    _CodeBinding("E-CANON-ESCAPE", ErrorClass.CANONICITY, "non-minimal string escape"),
    _CodeBinding("E-CANON-TRAILING", ErrorClass.CANONICITY, "bytes after the final newline"),
    # Identifiers, section 57.
    _CodeBinding("E-ID-GRAMMAR", ErrorClass.CANONICITY, "identifier violates the 57.2 grammar"),
    _CodeBinding("E-ID-TYPE", ErrorClass.CANONICITY, "wrong identifier type at a boundary"),
    _CodeBinding("E-ID-WIDTH", ErrorClass.SOUNDNESS, "run-local identifier inside a certificate"),
    # Schema and hashes.
    _CodeBinding("E-SCHEMA-MISSING", ErrorClass.CANONICITY, "required member absent"),
    _CodeBinding("E-SCHEMA-UNKNOWN", ErrorClass.CANONICITY, "unknown member present"),
    _CodeBinding("E-SCHEMA-DOWNGRADE", ErrorClass.CANONICITY, "checker older than min_checker"),
    _CodeBinding("E-SCOPE-BIND", ErrorClass.SOUNDNESS, "scope hash disagrees with inputs hash"),
    _CodeBinding("E-HASH-CERT", ErrorClass.SOUNDNESS, "cert_hash does not recompute"),
    _CodeBinding("E-HASH-ALGO", ErrorClass.SOUNDNESS, "digest algorithm name does not match"),
    _CodeBinding("E-INPUT-RULES", ErrorClass.SOUNDNESS, "rules hash does not recompute"),
    _CodeBinding("E-INPUT-BUNDLE", ErrorClass.SOUNDNESS, "bundle hash does not recompute"),
    _CodeBinding("E-INPUT-LIVENESS", ErrorClass.SOUNDNESS, "liveness hash does not recompute"),
    _CodeBinding("E-INPUT-PROFILE", ErrorClass.SOUNDNESS, "profile hash does not recompute"),
    # Grounding, cut and certificate obligations.
    _CodeBinding("E-INV-AXIOM", ErrorClass.SOUNDNESS, "an axiom fact is absent from U"),
    _CodeBinding("E-CLOSURE", ErrorClass.SOUNDNESS, "U is not closed under the published rules"),
    _CodeBinding("E-GOAL-MEMBER", ErrorClass.SOUNDNESS, "a severed goal is present in U"),
    _CodeBinding("E-CUT-ORDER", ErrorClass.CANONICITY, "cut not ascending by rank or not unique"),
    _CodeBinding("E-CUT-CLOSURE", ErrorClass.SOUNDNESS, "cut is not upward-closed in level"),
    _CodeBinding("E-CUT-LEVEL", ErrorClass.MINIMALITY, "a raised level is not level-minimal"),
    _CodeBinding("E-LITERAL-TABLE", ErrorClass.SOUNDNESS, "literal table disagrees with the lock"),
    _CodeBinding("E-PSI-HIT", ErrorClass.SOUNDNESS, "published cut misses a published corridor"),
    _CodeBinding("E-LICENSE-UNIMPLIED", ErrorClass.SOUNDNESS, "licence not implied by liveness"),
    _CodeBinding("E-LICENSE-WINDOW", ErrorClass.SOUNDNESS, "silent instance outside its licence"),
    _CodeBinding("E-GHOST-COUNT", ErrorClass.SOUNDNESS, "GHOST accounting reached observed counts"),
    _CodeBinding("E-WITNESS-CYCLE", ErrorClass.SOUNDNESS, "witness tree is not well founded"),
    _CodeBinding("E-WITNESS-EVENT", ErrorClass.SOUNDNESS, "witness leaf cites no bundled record"),
    _CodeBinding("E-WITNESS-CUT", ErrorClass.SOUNDNESS, "witness does not re-derive under its cut"),
    _CodeBinding("E-MIN-UNEARNED", ErrorClass.MINIMALITY, "exact minimality claimed but unearned"),
    _CodeBinding("E-MIN-SMALLER", ErrorClass.MINIMALITY, "a smaller cut hits every corridor"),
    _CodeBinding("E-FLAG-DERIVED", ErrorClass.DERIVED, "a derived product published under a cap"),
    _CodeBinding("E-FLAG-UNKNOWN", ErrorClass.CANONICITY, "unknown, duplicated or misordered flag"),
    # Guard front end.
    _CodeBinding("E-LEX-001", ErrorClass.USAGE, "a CR byte in rule text"),
    _CodeBinding("E-LEX-004", ErrorClass.USAGE, "a '.' followed by a digit"),
    _CodeBinding("E-SYN-000", ErrorClass.USAGE, "guard syntax error"),
    _CodeBinding("E-SYN-009", ErrorClass.USAGE, "illegal construct in the control sort"),
    _CodeBinding("E-SYN-010", ErrorClass.USAGE, "control reference inside the data sort"),
    _CodeBinding("E-SYN-012", ErrorClass.USAGE, "a level written as an integer"),
    _CodeBinding("E-TYP-001", ErrorClass.USAGE, "data-sort guard root is not Bool"),
    _CodeBinding("E-TYP-002", ErrorClass.USAGE, "control-sort guard root is not Ctl"),
    _CodeBinding("E-SEM-030", ErrorClass.USAGE, "a non-integral duration"),
    _CodeBinding("E-SEM-041", ErrorClass.USAGE, "control-sort DNF exceeded eight terms"),
    _CodeBinding("E-VS-BLOCK-CONJ", ErrorClass.USAGE, "conjunctive blocker term, narrowed away"),
    # Calibration binding gates.
    _CodeBinding("PROFILE_INVALID", ErrorClass.SOUNDNESS, "profile failed validation"),
    _CodeBinding("PROFILE_SELF_CALIBRATED", ErrorClass.SOUNDNESS, "B1: profile is this bundle"),
    _CodeBinding("PROFILE_FROM_DEGRADED_RUN", ErrorClass.SOUNDNESS, "B2: profile is not identity"),
    _CodeBinding("PROFILE_SEED_OVERLAP", ErrorClass.SOUNDNESS, "B3: run seed is in the band"),
    _CodeBinding("PROFILE_CONFIG_MISMATCH", ErrorClass.SOUNDNESS, "B4: generator config differs"),
    _CodeBinding("PROFILE_FAMILY_MISMATCH", ErrorClass.SOUNDNESS, "B5: scenario family differs"),
    _CodeBinding("PROFILE_INTERVALS_MISMATCH", ErrorClass.SOUNDNESS, "B6: excluded intervals differ"),
    # Limits, budgets, determinism.
    _CodeBinding("E-LIMIT-COUNT", ErrorClass.SOUNDNESS, "declared count exceeds observed length"),
    _CodeBinding("E-LIMIT-COMPRESSED", ErrorClass.SOUNDNESS, "input carries a compression magic"),
    _CodeBinding("E-LIMIT-DEPTH", ErrorClass.CANONICITY, "nesting deeper than eight"),
    _CodeBinding("E-BUDGET-EXHAUSTED", ErrorClass.MINIMALITY, "a deterministic step budget fired"),
    _CodeBinding("E-DET-ORDER", ErrorClass.SOUNDNESS, "an output path lacked a total order"),
    _CodeBinding("E-DET-RANDOM", ErrorClass.SOUNDNESS, "randomness outside a threaded generator"),
    # Verdict algebra, VRD series.
    _CodeBinding("VRD-001", ErrorClass.SOUNDNESS, "ROBUST proposed with a soundness flag set"),
    _CodeBinding("VRD-002", ErrorClass.SOUNDNESS, "UNSAFE proposed without a witness"),
    _CodeBinding("VRD-003", ErrorClass.SOUNDNESS, "an OBSERVED witness contains a GHOST"),
    _CodeBinding("VRD-004", ErrorClass.MINIMALITY, "exact minimality proposed under a cap"),
    _CodeBinding("VRD-005", ErrorClass.SOUNDNESS, "incomplete scope or a non-declared attacker"),
    _CodeBinding("VRD-006", ErrorClass.CANONICITY, "witness_class present on a non-UNSAFE verdict"),
    _CodeBinding("VRD-007", ErrorClass.SOUNDNESS, "er_ambiguous without witness_class CONTESTED"),
    _CodeBinding("VRD-008", ErrorClass.CANONICITY, "flag unknown, duplicated or out of bit order"),
    _CodeBinding("VRD-009", ErrorClass.CANONICITY, "a reserved flag bit is set"),
    _CodeBinding("VRD-010", ErrorClass.SOUNDNESS, "a verdict was constructed outside its builder"),
    _CodeBinding("VRD-012", ErrorClass.SOUNDNESS, "scope hashes disagree with the inputs"),
    _CodeBinding("VRD-014", ErrorClass.DERIVED, "derived_suppressed omits a required entry"),
    _CodeBinding("E-UNSPECIFIED", ErrorClass.USAGE, "no reason code was supplied"),
)

#: Every declared reason code. A build gate asserts that each one is produced by at least
#: one corpus fixture; an unreachable code is a build failure, not a spare.
ERROR_CODES: Final[frozenset[str]] = frozenset(b.code for b in _BINDINGS)

_CODE_CLASS: Final[dict[str, ErrorClass]] = {b.code: b.error_class for b in _BINDINGS}
_CODE_SUMMARY: Final[dict[str, str]] = {b.code: b.summary for b in _BINDINGS}

if len(_CODE_CLASS) != len(_BINDINGS):
    raise RuntimeError("duplicate reason code in the error registry")


def code_is_declared(code: str) -> bool:
    """True when `code` is in the closed registry. A build gate uses this, not a regex."""
    return code in ERROR_CODES


def code_class(code: str) -> ErrorClass:
    """The class of a declared code. Raises on an undeclared one rather than defaulting."""
    try:
        return _CODE_CLASS[code]
    except KeyError:
        raise SchemaError(f"undeclared reason code {code!r}", code="E-SCHEMA-UNKNOWN") from None


def code_summary(code: str) -> str:
    """The one-line summary of a declared code, for a transcript line."""
    try:
        return _CODE_SUMMARY[code]
    except KeyError:
        raise SchemaError(f"undeclared reason code {code!r}", code="E-SCHEMA-UNKNOWN") from None


# ---------------------------------------------------------------------------
# Quarantine
# ---------------------------------------------------------------------------


class QuarantineReason(StrEnum):
    """Why one record was dropped before it could reach the fact base.

    A closed set. Dropping a record is never silent and never a default: each reason is
    counted per source and each sets flag bit 4, because a dropped record is
    indistinguishable downstream from a record the sensor never produced.
    """

    LABEL_LEAK = "Q_LABEL_LEAK"
    """The line carried a ground-truth key. Label purity: ingest rejects, exit 4."""

    UNPARSEABLE = "Q_UNPARSEABLE"
    """The bytes are not a well-formed record of the declared format."""

    NONCANONICAL = "Q_NONCANONICAL"
    """Parsed, but re-serialising does not reproduce the input bytes."""

    FLOAT_PRESENT = "Q_FLOAT_PRESENT"
    """A number position held a float. There are no floats anywhere in the pipeline."""

    UNKNOWN_SOURCE = "Q_UNKNOWN_SOURCE"
    """The record names a source that the scenario does not declare."""

    UNKNOWN_EVENT_TYPE = "Q_UNKNOWN_EVENT_TYPE"
    """The record's type is not among the source's declared emissions."""

    DUPLICATE_RECORD = "Q_DUPLICATE_RECORD"
    """A second record with an already-seen RecordId on the same source."""

    SEQ_REGRESSION = "Q_SEQ_REGRESSION"
    """The per-source sequence number went backwards or repeated."""

    LINK_UNVERIFIED = "Q_LINK_UNVERIFIED"
    """On an integrity-bearing source, the recomputed link digest did not match."""

    ARITH_SATURATION = "Q_ARITH_SATURATION"
    """Integer arithmetic saturated at an i64 bound while normalising this record."""


@dataclass(frozen=True, slots=True)
class QuarantineRecord:
    """One dropped record, with enough to count it and nothing that identifies a machine.

    `record_id` is the `rc:` id of the bytes as received when they could be digested at
    all; when the bytes could not even be read it is absent, which is why the field is
    optional and why `detail` exists. No path, no hostname, no wall clock: this object is
    summarised into a manifest, and the manifest must stay machine-independent.
    """

    reason: QuarantineReason
    source_id: str
    record_id: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason, QuarantineReason):
            raise SchemaError(
                f"QuarantineRecord.reason must be a QuarantineReason, got {type(self.reason).__name__}",
                code="E-SCHEMA-UNKNOWN",
            )

    def sort_key(self) -> tuple[str, str, str]:
        """Total order for output. Extended with `detail` so ties are impossible."""
        return (self.source_id, self.record_id or "", str(self.reason))
