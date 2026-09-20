"""S10-tail: the verdict algebra and the certificate emitter.

WHAT THIS MODULE PRODUCES. One file, `runs/<run_id>/cert.spcert`, whose content is
exactly `{"body":{...},"cert_hash":"b2b256:<64hex>"}` in SCF-lite with one trailing LF.
`body` carries the schema triple, the seven-member scope, the input digests, the verdict,
the atom table, the cut, the goal library, the closure invariant, the published instance
set, the licences relied on, the silent instances, the witness trees, the corridor
database, the premium (or the reason it is absent), the canonical-representative
difference, the residual, the deterministic budget counters and the two separate event
counts.

THE DIGEST. `spectra_core.canon` computes blake2b-256 and labels it `b2b256:`. The
specification names a different algorithm which the standard library does not provide and
which no package may be installed to supply; `spectra_core.canon.SPEC_HASH_ALGORITHM`
records the name that was asked for and `HASH_ALGORITHM` records what was computed. Both
travel inside `body.schema`, so a certificate that does not say which digest produced its
hashes cannot be constructed here at all.

WHAT EACH HASH COVERS. Every member of `body.inputs` whose name ends in `_hash` is
`canon.hash_ref(kind, octets)` over the exact octets of one named artifact, listed in
`INPUT_HASH_COVERAGE` and repeated here so that a reader never has to guess:

  rules_hash         the octets of the canonical rule-encoding artifact that S1 writes
                     (`guards.cae` plus its per-rule metadata record). NOT the octets of
                     `rules.toml`: a comment reflow must not invalidate an archived
                     certificate.
  rules_text_hash    the octets of `rules.toml` as authored. Forensic only. A checker that
                     finds `rules_hash` matching and this differing prints a note and
                     continues; nothing is enforced on it.
  guard_ast_hash     the octets of `guards.cae`, the canonical guard AST including slot
                     numbering and bit assignment.
  controls_hash      the octets of the canonical control-catalog encoding, level table
                     included.
  catalog_bits_hash  the octets of `catalog-bits.lock`. Bit positions are inside the
                     digest, which is why that lock is append-only: an edit that shifts a
                     bit invalidates every certificate that quoted it.
  bundle_hash        the octets of `bundle.jsonl`, already canonical after ingest.
  liveness_hash      the octets of `liveness.json`.
  profile_hash       the octets of the source profile. The profile fixes every threshold,
                     so it is pinned like any other input.
  goal_hash          the octets of the canonical encoding of the goal library entry.
  er_hash            the octets of `er.json`.
  instances_hash     NOT a file. The canonical binary encoding of the published instance
                     set in `body.instances`, in published order, under the `instances`
                     domain. This is the one digest this module computes itself, and it is
                     what binds `grounding_mode: "replayed"`: a checker re-derives it from
                     the certificate's own bytes and needs no side file.

`seed` is a fixed-width hex string, never a JSON number. `k` is the horizon in ticks.
`grounding_mode` is `replayed`, which is the honest statement of what a checker does with
`instances`: it replays them, it does not re-ground them from the bundle.

THE VERDICT ALGEBRA IS ENFORCED BY THE CONSTRUCTOR. `Verdict` is a frozen dataclass whose
`__post_init__` raises unless it was handed the module-private seal, so the only way to
obtain one is `Verdict.build`, and a verdict read back from an untrusted file goes through
`VerdictProposal` and is re-checked. `Safety.ROBUST` additionally requires a
`NoTamperToken`, which is mintable only from a liveness result in which no source is
tamper-suspected and the tamper-sensitivity flag is false. Safety and minimality are
independent fields and neither downgrades the other: a cut may be exactly minimal against
the enumerated corridor set and unsafe, and a cut may be safe with nothing claimed about
its size.

NO BARE VERDICT WORD. `render_short` and `render_long` are the only functions in this
package that may place a safety token next to a string literal, and both carry the six
scope digests and the literal `non-adaptive` with them. `render_long` always ends with
`MODEL_STATEMENT`. A one-word rendering is what a reader remembers, and it would be true
only under this rule table, this control catalog, these licences and a non-adaptive
attacker.

THREE DIVERGENCES FROM THE OPERATIVE SPECIFICATION, recorded rather than resolved.

1. `body.schema` carries `hash_algorithm` and `hash_substitution_note` in addition to
   `v`, `min_checker` and `profile`. The specification's member list is closed and does
   not name them; `spectra_core.model.Certificate` refuses to be constructed without the
   algorithm declaration, and a certificate whose digests are unlabelled is exactly the
   silent substitution the encoding law forbids. The declaration wins.

2. The specification says the first 26 octets of the file are a fixed prefix running
   through `{"body":{"schema":{"v":`. That assumes `schema` is the first member of `body`
   and `v` the first member of `schema`. The same document's key-sorting law puts `atoms`
   first inside `body` and `min_checker` before `v` inside `schema`, so the prefix it
   names cannot exist. Sorting is the hashing law and wins; `FILE_MAGIC` is therefore the
   nine octets `{"body":{`, which is still enough to reject a wrong-shaped file before
   parsing it.

3. Evidence leaves and licence witnesses cite `ev:` event identifiers, which are h128 and
   which `spectra_core.ids.reject_run_local_in_certificate` would reject inside a
   certificate. The operative specification's certificate contract names `ev:` and is
   authoritative for this work. Every other identifier placed in the body is run through
   that gate, so the exemption is one named concept rather than a disabled check.

NO WALL CLOCK, no hostname, no username, no path, no process id, no duration and no
`measured` member reaches the body. Timings belong in the run manifest, which is not
hashed into the certificate.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, Self

from spectra_core import canon
from spectra_core.errors import SchemaError, VerdictError
from spectra_core.ids import (
    ControlId,
    CorridorId,
    EventId,
    FactHash,
    InstanceId,
    LicenseId,
    reject_run_local_in_certificate,
)
from spectra_core.model import (
    Corridor,
    Cut,
    Licence,
    Minimality,
    ProgramKind,
    RuleInstance,
    ThresholdLiteral,
)
from spectra_vs import scf

__all__ = [
    "ATTACKER",
    "BODY_MEMBERS",
    "BUNDLE_PROVENANCE",
    "CERT_PROFILE",
    "CUT_DELTA_CAPTION",
    "DERIVED_SUPPRESSED_ALWAYS",
    "FILE_MAGIC",
    "FLAGS",
    "FLAG_BY_NAME",
    "GROUNDING_MODE",
    "IMPLEMENTATION",
    "INPUT_HASH_COVERAGE",
    "INPUT_MEMBERS",
    "IMPLEMENTATION_NOTE",
    "MAX_DEPTH",
    "MIN_CHECKER",
    "MODEL_STATEMENT",
    "PREMIUM_SUPPRESSED_REASONS",
    "RESERVED_MASK",
    "SCHEMA_V",
    "SCOPE_MEMBERS",
    "SOUNDNESS_MASK",
    "Budgets",
    "CertificateArtifact",
    "Flag",
    "GoalRef",
    "Inputs",
    "NoTamperToken",
    "Premium",
    "PremiumEntry",
    "Psi",
    "Realizability",
    "Residual",
    "Safety",
    "Scope",
    "SilentRef",
    "Verdict",
    "VerdictProposal",
    "WitnessClass",
    "WitnessEntry",
    "WitnessKind",
    "WitnessNode",
    "build_body",
    "certificate_bytes",
    "emit",
    "flags_mask",
    "instances_hash",
    "mint_no_tamper_token",
    "render_cut_delta_canonical",
    "render_long",
    "render_minimality",
    "render_short",
    "write_certificate",
]


# ---------------------------------------------------------------------------
# Frame constants
# ---------------------------------------------------------------------------

SCHEMA_V: Final[str] = "1.0"
MIN_CHECKER: Final[str] = "1.0"
CERT_PROFILE: Final[str] = "eclipse-cert"
ATTACKER: Final[str] = "non-adaptive"
GROUNDING_MODE: Final[str] = "replayed"
BUNDLE_PROVENANCE: Final[str] = "synthetic_generator_no_range"
IMPLEMENTATION: Final[str] = "python-reference"

#: The octets a reader may check before parsing. Nine, not twenty-six; see divergence 2 in
#: the module docstring.
FILE_MAGIC: Final[bytes] = b'{"body":{'

#: The contract permits nesting eight containers deep, counting the document object as the
#: first. A witness tree sits at `body.witnesses[i].tree`, which uses five of the eight, so
#: this cap bounds a published tree to a root node and one level of children. The emitter
#: refuses a deeper tree rather than writing a file a checker is obliged to reject.
MAX_DEPTH: Final[int] = 8

#: The sentence every long rendering ends with. Not optional and not paraphrasable.
MODEL_STATEMENT: Final[str] = (
    "This is a statement about the model, not about the system."
)

#: The caption `cut_delta_canonical` carries wherever it is rendered. The set difference
#: of two canonical representatives is a different object from the premium, which is
#: defined by the values of two optimisation problems over the corridor databases.
CUT_DELTA_CAPTION: Final[str] = (
    "difference between two canonical representatives; not the blindness premium"
)

#: What an accepted certificate does and does not say, carried into every report.
IMPLEMENTATION_NOTE: Final[str] = (
    "PYTHON REFERENCE IMPLEMENTATION. Telemetry comes from a seeded synthetic generator, "
    "never from a service. Digests are blake2b-256 labelled b2b256:, not the algorithm "
    "the specification names."
)

SCOPE_MEMBERS: Final[tuple[str, ...]] = (
    "attacker",
    "bundle",
    "controls",
    "er",
    "goal",
    "liveness",
    "rules",
)

INPUT_MEMBERS: Final[tuple[str, ...]] = (
    "bundle_hash",
    "bundle_provenance",
    "catalog_bits_hash",
    "controls_hash",
    "er_hash",
    "goal_hash",
    "grounding_mode",
    "guard_ast_hash",
    "implementation",
    "instances_hash",
    "k",
    "liveness_hash",
    "profile_hash",
    "rules_hash",
    "rules_text_hash",
    "seed",
)

#: `(input member, digest domain, one sentence saying exactly what octets it covers)`.
#: A checker recomputes each one over the artifact supplied for it on argv. The table is
#: duplicated in the checker package rather than imported, because a checker that imported
#: the emitter's idea of what a hash covers could not disagree with it.
INPUT_HASH_COVERAGE: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "rules_hash",
        "rules",
        "octets of the canonical rule-encoding artifact from S1, not of rules.toml",
    ),
    ("rules_text_hash", "rulestext", "octets of rules.toml as authored; forensic only"),
    ("guard_ast_hash", "guardast", "octets of guards.cae"),
    ("controls_hash", "controls", "octets of the canonical control-catalog encoding"),
    ("catalog_bits_hash", "catbits", "octets of catalog-bits.lock"),
    ("bundle_hash", "bundle", "octets of bundle.jsonl"),
    ("liveness_hash", "liveness", "octets of liveness.json"),
    ("profile_hash", "profile", "octets of the source profile"),
    ("goal_hash", "goal", "octets of the canonical goal-library encoding"),
    ("er_hash", "er", "octets of er.json"),
    (
        "instances_hash",
        "instances",
        "canonical binary encoding of body.instances in published order; no side file",
    ),
)

#: The scope member each input hash must equal. A disagreement is VRD-012 / E-SCOPE-BIND.
SCOPE_TO_INPUT: Final[tuple[tuple[str, str], ...]] = (
    ("bundle", "bundle_hash"),
    ("controls", "controls_hash"),
    ("er", "er_hash"),
    ("goal", "goal_hash"),
    ("liveness", "liveness_hash"),
    ("rules", "rules_hash"),
)

BODY_MEMBERS: Final[tuple[str, ...]] = (
    "atoms",
    "budgets",
    "cut",
    "cut_delta_canonical",
    "ghost_count",
    "goals",
    "inputs",
    "instances",
    "invariant",
    "licenses",
    "observed_event_count",
    "premium",
    "premium_suppressed_reason",
    "psi",
    "residual",
    "schema",
    "scope",
    "silent",
    "verdict",
    "witnesses",
)

#: Members that are absent rather than empty when their preconditions fail.
OPTIONAL_BODY_MEMBERS: Final[tuple[str, ...]] = (
    "invariant",
    "premium",
    "premium_suppressed_reason",
)

PREMIUM_SUPPRESSED_REASONS: Final[tuple[str, ...]] = (
    "corridor_cap",
    "er_ambiguous",
    "grounding_capped",
    "horizon_truncated",
    "solver_budget",
)

#: Both derived products are out of scope for the slice and are omitted entirely rather
#: than approximated, so both are always named in `verdict.derived_suppressed`.
DERIVED_SUPPRESSED_ALWAYS: Final[tuple[str, ...]] = ("pareto_frontier", "redundancy_index")


# ---------------------------------------------------------------------------
# The closed flag table
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Flag:
    """One run flag at a fixed bit position, with the classes it belongs to.

    `blocks_robust` is derived from membership of the soundness class rather than stored
    twice, so the two cannot drift apart.
    """

    bit: int
    name: str
    classes: tuple[str, ...]
    effect: str

    @property
    def blocks_robust(self) -> bool:
        return "S" in self.classes


FLAGS: Final[tuple[Flag, ...]] = (
    Flag(0, "grounding_capped", ("S",), "blocks the universal claim"),
    Flag(
        1,
        "corridor_cap",
        ("S", "M", "D"),
        "blocks the universal claim, caps minimality at SUBSET, suppresses derived products",
    ),
    Flag(2, "atoms_over_budget", ("M",), "caps minimality at SUBSET only"),
    Flag(
        3,
        "er_ambiguous",
        ("S",),
        "blocks the universal claim and forces witness_class CONTESTED",
    ),
    Flag(4, "quarantined_records", ("S",), "blocks the universal claim"),
    Flag(
        5,
        "license_voided_by_suspected_tampering",
        ("S",),
        "never set in this slice: the difference-constraint pass is not implemented",
    ),
    Flag(6, "greedy_cover", ("D",), "forces the approximation factor inline"),
    Flag(7, "sampled_matrix", ("R",), "blocks aggregate claims, not a per-run verdict"),
    Flag(8, "profile_missing", ("S",), "blocks the universal claim"),
)

FLAG_BY_NAME: Final[dict[str, Flag]] = {f.name: f for f in FLAGS}

#: Bits {0,1,3,4,5,8}. Derived from the table, never hand-copied.
SOUNDNESS_MASK: Final[int] = sum(1 << f.bit for f in FLAGS if f.blocks_robust)

#: Bits 9..15 are reserved and must be zero. Adding a flag is a schema version bump.
RESERVED_MASK: Final[int] = sum(1 << b for b in range(len(FLAGS), 16))

_MINIMALITY_CAP_FLAGS: Final[tuple[str, ...]] = ("atoms_over_budget", "corridor_cap")


def flags_mask(names: tuple[str, ...]) -> int:
    """The bit mask of a flag name array, rejecting unknown, duplicated or misordered names.

    The array on the wire is sorted by BIT POSITION and never alphabetically, because the
    bit order is the table's order and an alphabetical array would silently reorder when a
    flag is renamed.
    """
    mask = 0
    previous = -1
    for name in names:
        flag = FLAG_BY_NAME.get(name)
        if flag is None:
            raise VerdictError(f"flags: {name!r} is not a declared flag", code="VRD-008")
        if flag.bit <= previous:
            raise VerdictError(
                f"flags: {name!r} at bit {flag.bit} does not follow bit {previous} ascending",
                code="VRD-008",
            )
        previous = flag.bit
        mask |= 1 << flag.bit
    return mask


def check_reserved_bits(mask: int) -> int:
    """Raise VRD-009 when a reserved bit is set. Used where a mask arrives from a file."""
    if mask & RESERVED_MASK:
        raise VerdictError(
            f"flags: reserved bit set in {canon.mask_hex(mask)}; bits 9..15 must be zero",
            code="VRD-009",
        )
    return mask


# ---------------------------------------------------------------------------
# The verdict alphabets
# ---------------------------------------------------------------------------


class Safety(Enum):
    """Is the goal derivable under this cut, and over which program.

    Deliberately not a `StrEnum` and deliberately without a `__str__`: a bare safety token
    as a user-visible string is forbidden, and inheriting `str` would make every f-string
    in the codebase a rendering site. The token reaches the wire through `.value` inside
    the serialiser, where the scope travels with it.
    """

    ROBUST = "ROBUST"
    OPTIMISTIC_ONLY = "OPTIMISTIC_ONLY"
    UNSAFE = "UNSAFE"
    INDETERMINATE = "INDETERMINATE"


class WitnessClass(Enum):
    """What an UNSAFE witness rests on. No rendering may collapse the first two."""

    OBSERVED = "OBSERVED"
    LICENSED = "LICENSED"
    CONTESTED = "CONTESTED"


class Realizability(Enum):
    """Whether every displayed tree carries a realizability status object."""

    CHECKED = "CHECKED"
    UNCHECKED = "UNCHECKED"


class WitnessKind(Enum):
    """A witness node either cites records or is a GHOST. A GHOST is never an event."""

    OBSERVED = "OBSERVED"
    GHOST = "GHOST"


@dataclass(frozen=True, slots=True)
class NoTamperToken:
    """Evidence that no source was tamper-suspected. Required to mint the universal claim.

    The slice does not implement the difference-constraint backdating pass, so this token
    is always mintable and flag bit 5 is never set. It exists anyway so that adding the
    pass later is a change to `mint_no_tamper_token` rather than a rework of the verdict
    type, and so that nothing here can be read as a claim that tampering is detected.
    """

    sources_checked: int


def mint_no_tamper_token(
    *, tamper_suspected_sources: tuple[str, ...], verdict_tamper_sensitive: bool, sources: int
) -> NoTamperToken:
    """Mint the token, or raise. The only construction site.

    This says nothing about whether records were suppressed or backdated. The slice cannot
    detect either, and a token minted here records only that the liveness stage marked no
    source as suspected, which in this slice it never does.
    """
    if verdict_tamper_sensitive:
        raise VerdictError(
            "NoTamperToken: the liveness document is tamper-sensitive", code="VRD-001"
        )
    if tamper_suspected_sources:
        raise VerdictError(
            f"NoTamperToken: {len(tamper_suspected_sources)} source(s) are tamper-suspected",
            code="VRD-001",
        )
    canon.u32(sources)
    return NoTamperToken(sources_checked=sources)


_SEAL: Final[object] = object()


@dataclass(frozen=True, slots=True)
class VerdictProposal:
    """The deserialisable half of the verdict. Carries no authority of its own.

    A verdict read back from an untrusted file lands here first and reaches `Verdict` only
    through `Verdict.build`, so a file cannot instantiate an illegal verdict by naming its
    fields.
    """

    safety: Safety
    minimality: Minimality
    flags: tuple[str, ...]
    derived_suppressed: tuple[str, ...]
    realizability: Realizability
    witness_class: WitnessClass | None = None


@dataclass(frozen=True, slots=True)
class Verdict:
    """The sealed verdict. Three independent axes; no value on one implies any on another.

    Constructing this directly raises VRD-010. `Verdict.build` is the single constructor
    and returns an error rather than a degraded value, so there is no path that produces a
    universal claim under a soundness flag by forgetting a check.
    """

    safety: Safety
    minimality: Minimality
    flags: tuple[str, ...]
    derived_suppressed: tuple[str, ...]
    realizability: Realizability
    witness_class: WitnessClass | None
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SEAL:
            raise VerdictError(
                "Verdict has no public constructor; build it through Verdict.build",
                code="VRD-010",
            )
        _check_verdict_algebra(
            safety=self.safety,
            minimality=self.minimality,
            flags=self.flags,
            derived_suppressed=self.derived_suppressed,
            witness_class=self.witness_class,
            realizability=self.realizability,
        )

    @property
    def mask(self) -> int:
        return flags_mask(self.flags)

    @classmethod
    def build(
        cls,
        proposal: VerdictProposal,
        *,
        no_tamper_token: NoTamperToken | None = None,
        witness_present: bool = False,
        witness_contains_ghost: bool = False,
        pmax_fixpoint_terminated: bool = False,
    ) -> Self:
        """The single constructor. Raises a VRD code rather than returning a weaker verdict.

        `witness_present` and `witness_contains_ghost` are facts about the trees the caller
        is about to publish; passing them in rather than inspecting a global is what lets
        the algebra be checked before any bytes are produced.
        """
        _check_verdict_algebra(
            safety=proposal.safety,
            minimality=proposal.minimality,
            flags=proposal.flags,
            derived_suppressed=proposal.derived_suppressed,
            witness_class=proposal.witness_class,
            realizability=proposal.realizability,
        )
        if proposal.safety is Safety.ROBUST:
            if no_tamper_token is None:
                raise VerdictError(
                    "the universal claim requires a NoTamperToken from the liveness stage",
                    code="VRD-001",
                )
            if not pmax_fixpoint_terminated:
                raise VerdictError(
                    "the universal claim requires the upper-program fixpoint to have "
                    "terminated inside its deterministic budget",
                    code="VRD-001",
                )
        if proposal.safety is Safety.UNSAFE:
            if not witness_present:
                raise VerdictError("UNSAFE requires a witness tree", code="VRD-002")
            if proposal.witness_class is WitnessClass.OBSERVED and witness_contains_ghost:
                raise VerdictError(
                    "an OBSERVED witness class was proposed for a tree containing a GHOST "
                    "node; a GHOST is a licensed unobserved step, never an event",
                    code="VRD-003",
                )
            if proposal.witness_class is WitnessClass.LICENSED and not witness_contains_ghost:
                raise VerdictError(
                    "a LICENSED witness class was proposed for a tree with no silent node",
                    code="VRD-003",
                )
        return cls(
            safety=proposal.safety,
            minimality=proposal.minimality,
            flags=proposal.flags,
            derived_suppressed=proposal.derived_suppressed,
            realizability=proposal.realizability,
            witness_class=proposal.witness_class,
            _seal=_SEAL,
        )

    def as_member(self) -> dict[str, Any]:
        """The `verdict` body member. `witness_class` is present-and-null on non-UNSAFE."""
        return {
            "derived_suppressed": list(self.derived_suppressed),
            "flags": list(self.flags),
            "minimality": str(self.minimality),
            "realizability": self.realizability.value,
            "safety": self.safety.value,
            "witness_class": None if self.witness_class is None else self.witness_class.value,
        }


def _check_verdict_algebra(
    *,
    safety: Safety,
    minimality: Minimality,
    flags: tuple[str, ...],
    derived_suppressed: tuple[str, ...],
    witness_class: WitnessClass | None,
    realizability: Realizability,
) -> None:
    """A1..A10 of the verdict section, in one place, called from both the builder and
    `__post_init__` so that a sealed instance cannot carry an illegal combination."""
    if not isinstance(safety, Safety):
        raise VerdictError("safety must be a Safety member", code="VRD-008")
    if not isinstance(minimality, Minimality):
        raise VerdictError("minimality must be a Minimality member", code="VRD-008")
    if not isinstance(realizability, Realizability):
        raise VerdictError("realizability must be a Realizability member", code="VRD-008")
    mask = check_reserved_bits(flags_mask(flags))

    if safety is Safety.ROBUST and mask & SOUNDNESS_MASK:
        raised = tuple(f.name for f in FLAGS if f.blocks_robust and mask & (1 << f.bit))
        raise VerdictError(
            f"the universal claim is unconstructible while {raised} are set", code="VRD-001"
        )
    if safety is not Safety.UNSAFE and witness_class is not None:
        raise VerdictError(
            "witness_class is present-and-null on every non-UNSAFE verdict", code="VRD-006"
        )
    if safety is Safety.UNSAFE:
        if witness_class is None:
            raise VerdictError("UNSAFE carries a mandatory witness_class", code="VRD-002")
        if "er_ambiguous" in flags and witness_class is not WitnessClass.CONTESTED:
            raise VerdictError(
                "er_ambiguous fabricates the leaves themselves, so the witness class is "
                "CONTESTED",
                code="VRD-007",
            )
    if minimality in (Minimality.EXACT_EXHAUSTIVE, Minimality.EXACT_PSI_RELATIVE):
        capped = tuple(name for name in _MINIMALITY_CAP_FLAGS if name in flags)
        if capped:
            raise VerdictError(
                f"exact minimality is unearned while {capped} are set", code="VRD-004"
            )
    canon.check_strictly_ascending(
        derived_suppressed, canon.byte_order_key, where="verdict.derived_suppressed"
    )
    missing = tuple(n for n in DERIVED_SUPPRESSED_ALWAYS if n not in derived_suppressed)
    if missing:
        raise VerdictError(
            f"derived_suppressed omits {missing}; both are out of scope for the slice and "
            "are omitted entirely rather than approximated",
            code="VRD-014",
        )


# ---------------------------------------------------------------------------
# The single renderer
# ---------------------------------------------------------------------------

_MINIMALITY_CLAUSE: Final[dict[str, str]] = {
    "EXACT_EXHAUSTIVE": (
        "a fixpoint was run for every cut one control smaller over the admissible lattice"
    ),
    "EXACT_PSI_RELATIVE": "no smaller cut satisfies the enumerated corridor set",
    "SUBSET": "no control can be removed from this cut; smaller cuts were not ruled out",
    "UNVERIFIED": "no minimality probe ran, so nothing is claimed about the size of this cut",
}

_SAFETY_CLAUSE: Final[dict[str, str]] = {
    "ROBUST": (
        "the goal is underivable under this cut in the upper program, which unions every "
        "licensed silent instance"
    ),
    "OPTIMISTIC_ONLY": (
        "the goal is underivable under this cut in the lower program and derivable in the "
        "upper one, so the difference is what could not be seen"
    ),
    "UNSAFE": "the goal is derivable under this cut in the lower program, with a witness",
    "INDETERMINATE": "no other safety value was constructible, which is the fail-closed sink",
}

_WITNESS_CLAUSE: Final[dict[str, str]] = {
    "OBSERVED": "every leaf of the witness cites a record in the hashed bundle",
    "LICENSED": (
        "the witness contains at least one silent step and depicts a hypothesis, not an "
        "observation; the upper program may combine silent steps no single world realizes"
    ),
    "CONTESTED": "entity resolution was ambiguous, so the leaves themselves are contested",
}


def _short_digest(value: str) -> str:
    body = value.split(":", 1)[1] if ":" in value else value
    return canon.HASH_REF_PREFIX + body[:8]


def render_short(verdict: Verdict, scope: Scope) -> str:
    """The short rendering. The scope travels with the token; there is no bare-token form."""
    return (
        f"{verdict.safety.value}("
        f"rules@{_short_digest(scope.rules)}, "
        f"controls@{_short_digest(scope.controls)}, "
        f"liveness@{_short_digest(scope.liveness)}, "
        f"er@{_short_digest(scope.er)}, "
        f"goal@{_short_digest(scope.goal)}, "
        f"bundle@{_short_digest(scope.bundle)}, "
        f"{scope.attacker}) [{verdict.minimality}]"
    )


def render_long(verdict: Verdict, scope: Scope) -> str:
    """The long rendering: the same content in prose, always ending with MODEL_STATEMENT."""
    lines = [
        render_short(verdict, scope),
        f"Safety: {_SAFETY_CLAUSE[verdict.safety.value]}.",
        f"Minimality: {_MINIMALITY_CLAUSE[str(verdict.minimality)]}.",
    ]
    if verdict.witness_class is not None:
        lines.append(f"Witness: {_WITNESS_CLAUSE[verdict.witness_class.value]}.")
    lines.append(
        "Scope: this rule table, this control catalog, these licences, the telemetry "
        f"actually ingested, and a {scope.attacker} attacker."
    )
    if verdict.flags:
        lines.append("Flags set: " + ", ".join(verdict.flags) + ".")
    if verdict.derived_suppressed:
        lines.append(
            "Derived products omitted entirely: " + ", ".join(verdict.derived_suppressed) + "."
        )
    lines.append(IMPLEMENTATION_NOTE)
    lines.append(MODEL_STATEMENT)
    return "\n".join(lines)


def render_minimality(minimality: Minimality) -> str:
    """The one permitted sentence per minimality value."""
    return _MINIMALITY_CLAUSE[str(minimality)]


def render_cut_delta_canonical(control_ids: tuple[str, ...]) -> str:
    """Render the canonical-representative difference, always with its caption.

    It is never rendered in the same breath as the premium: the premium is defined by the
    values of two optimisation problems over the corridor databases and is invariant to
    solver order, while this is a set difference of two chosen representatives.
    """
    listed = ", ".join(control_ids) if control_ids else "(empty)"
    return f"cut_delta_canonical = {{{listed}}} -- {CUT_DELTA_CAPTION}"


# ---------------------------------------------------------------------------
# Body sub-objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Scope:
    """The seven-member scope. Total or the run emits no verdict at all."""

    rules: str
    controls: str
    liveness: str
    er: str
    goal: str
    bundle: str
    attacker: str = ATTACKER

    def __post_init__(self) -> None:
        if self.attacker != ATTACKER:
            raise VerdictError(
                f"scope.attacker must be {ATTACKER!r}, the only value v1 accepts",
                code="VRD-005",
            )
        for name in ("rules", "controls", "liveness", "er", "goal", "bundle"):
            value = getattr(self, name)
            if not value:
                raise VerdictError(f"scope.{name} is empty; scope is total", code="VRD-005")
            canon.parse_hash_ref(value)

    def as_member(self) -> dict[str, str]:
        return {
            "attacker": self.attacker,
            "bundle": self.bundle,
            "controls": self.controls,
            "er": self.er,
            "goal": self.goal,
            "liveness": self.liveness,
            "rules": self.rules,
        }


@dataclass(frozen=True, slots=True)
class Inputs:
    """Every pinned digest plus the four declarations. See INPUT_HASH_COVERAGE."""

    rules_hash: str
    rules_text_hash: str
    guard_ast_hash: str
    controls_hash: str
    catalog_bits_hash: str
    bundle_hash: str
    liveness_hash: str
    profile_hash: str
    goal_hash: str
    er_hash: str
    instances_hash: str
    seed: int
    k: int

    def __post_init__(self) -> None:
        for name, _kind, _coverage in INPUT_HASH_COVERAGE:
            canon.parse_hash_ref(getattr(self, name))
        canon.mask_hex(self.seed)
        canon.u32(self.k)

    def as_member(self) -> dict[str, Any]:
        member: dict[str, Any] = {
            "bundle_provenance": BUNDLE_PROVENANCE,
            "grounding_mode": GROUNDING_MODE,
            "implementation": IMPLEMENTATION,
            "k": self.k,
            "seed": canon.mask_hex(self.seed),
        }
        for name, _kind, _coverage in INPUT_HASH_COVERAGE:
            member[name] = getattr(self, name)
        return member


@dataclass(frozen=True, slots=True)
class Budgets:
    """Deterministic step counters only. There is no wall-clock budget anywhere."""

    fixpoint_steps: int
    bb_nodes: int
    step_budget: int
    budget_exhausted: bool
    exhaustive_ran: bool
    exhaustive_cuts_tested: int

    def __post_init__(self) -> None:
        for name in ("fixpoint_steps", "bb_nodes", "step_budget", "exhaustive_cuts_tested"):
            canon.u32(getattr(self, name))
        for name in ("budget_exhausted", "exhaustive_ran"):
            if not isinstance(getattr(self, name), bool):
                raise SchemaError(f"budgets.{name} must be a bool")

    def as_member(self) -> dict[str, Any]:
        return {
            "bb_nodes": self.bb_nodes,
            "budget_exhausted": self.budget_exhausted,
            "exhaustive_cuts_tested": self.exhaustive_cuts_tested,
            "exhaustive_ran": self.exhaustive_ran,
            "fixpoint_steps": self.fixpoint_steps,
            "step_budget": self.step_budget,
        }


@dataclass(frozen=True, slots=True)
class GoalRef:
    """One goal atom and whether it is derivable under the published cut."""

    goal_key: FactHash
    derivable: bool

    def __post_init__(self) -> None:
        reject_run_local_in_certificate(self.goal_key, where="goals.goal_key")
        if not isinstance(self.derivable, bool):
            raise SchemaError("goals.derivable must be a bool")

    def as_member(self) -> dict[str, Any]:
        return {"derivable": self.derivable, "goal_key": str(self.goal_key)}


@dataclass(frozen=True, slots=True)
class SilentRef:
    """A silent instance and the licences it rests on. Never an observation."""

    instance_id: InstanceId
    license_ids: tuple[LicenseId, ...]

    def __post_init__(self) -> None:
        reject_run_local_in_certificate(self.instance_id, where="silent.instance_id")
        if not self.license_ids:
            raise SchemaError(
                "silent: an unlicensed silent instance has no place in a certificate",
                code="E-LICENSE-UNIMPLIED",
            )
        for license_id in self.license_ids:
            reject_run_local_in_certificate(license_id, where="silent.license_ids")
        canon.check_strictly_ascending(
            self.license_ids, canon.byte_order_key, where="silent.license_ids"
        )

    def as_member(self) -> dict[str, Any]:
        return {
            "instance_id": str(self.instance_id),
            "license_ids": [str(x) for x in self.license_ids],
        }


@dataclass(frozen=True, slots=True)
class WitnessNode:
    """One AND-node of a derivation. A GHOST cites no event and is never called one."""

    instance_id: InstanceId
    head: FactHash
    kind: WitnessKind
    evidence: tuple[EventId, ...] = ()
    children: tuple[WitnessNode, ...] = ()

    def __post_init__(self) -> None:
        reject_run_local_in_certificate(self.instance_id, where="witness.instance_id")
        reject_run_local_in_certificate(self.head, where="witness.head")
        if not isinstance(self.kind, WitnessKind):
            raise SchemaError("witness.kind must be a WitnessKind")
        canon.check_strictly_ascending(
            self.evidence, canon.byte_order_key, where="witness.evidence"
        )
        if self.kind is WitnessKind.GHOST and self.evidence:
            raise SchemaError(
                "a GHOST node carries no evidence; it is a licensed unobserved step",
                code="E-GHOST-COUNT",
            )
        if self.kind is WitnessKind.OBSERVED and not self.evidence:
            raise SchemaError(
                "an OBSERVED node cites at least one record", code="E-WITNESS-EVENT"
            )

    def contains_ghost(self) -> bool:
        return self.kind is WitnessKind.GHOST or any(c.contains_ghost() for c in self.children)

    def as_member(self) -> dict[str, Any]:
        return {
            "children": [c.as_member() for c in self.children],
            "evidence": [str(e) for e in self.evidence],
            "head": str(self.head),
            "instance_id": str(self.instance_id),
            "kind": self.kind.value,
        }


@dataclass(frozen=True, slots=True)
class WitnessEntry:
    """The tree that re-derives the goal when one control is removed from the cut."""

    removed_control: ControlId
    tree: WitnessNode

    def __post_init__(self) -> None:
        reject_run_local_in_certificate(
            self.removed_control, where="witnesses.removed_control"
        )

    def as_member(self) -> dict[str, Any]:
        return {"removed_control": str(self.removed_control), "tree": self.tree.as_member()}


@dataclass(frozen=True, slots=True)
class Psi:
    """The published corridor database. `program` travels so no consumer can forget it."""

    program: ProgramKind
    complete: bool
    corridors: tuple[Corridor, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.program, ProgramKind):
            raise SchemaError("psi.program must be a ProgramKind")
        if not isinstance(self.complete, bool):
            raise SchemaError("psi.complete must be a bool")
        canon.check_strictly_ascending(
            self.corridors, lambda c: canon.byte_order_key(str(c.corridor_id)),
            where="psi.corridors",
        )
        for corridor in self.corridors:
            reject_run_local_in_certificate(corridor.corridor_id, where="psi.corridors")
            if not corridor.verify_id():
                raise SchemaError(
                    f"psi: {corridor.corridor_id} does not recompute from its atom ranks",
                    code="E-PSI-HIT",
                )

    def as_member(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "corridors": [
                {
                    "atom_ranks": list(c.atom_ranks),
                    "corridor_id": str(c.corridor_id),
                    "mask": canon.mask_hex(c.mask),
                }
                for c in self.corridors
            ],
            "program": str(self.program),
        }


@dataclass(frozen=True, slots=True)
class Residual:
    """The set-valued residual. There is no scalar residual and no total order on two."""

    program: ProgramKind
    goals_derivable: tuple[FactHash, ...]
    goals_severed: tuple[FactHash, ...]
    corridors_open: tuple[CorridorId, ...]
    corridors_exhaustive: bool

    def __post_init__(self) -> None:
        if not isinstance(self.program, ProgramKind):
            raise SchemaError("residual.program must be a ProgramKind")
        if not isinstance(self.corridors_exhaustive, bool):
            raise SchemaError("residual.corridors_exhaustive must be a bool")
        for name in ("goals_derivable", "goals_severed", "corridors_open"):
            values = getattr(self, name)
            for value in values:
                reject_run_local_in_certificate(value, where=f"residual.{name}")
            canon.check_strictly_ascending(
                values, canon.byte_order_key, where=f"residual.{name}"
            )
        overlap = set(self.goals_derivable) & set(self.goals_severed)
        if overlap:
            raise SchemaError(
                f"residual: {sorted(overlap)} is both derivable and severed",
                code="E-GOAL-MEMBER",
            )

    def as_member(self) -> dict[str, Any]:
        return {
            "corridors_exhaustive": self.corridors_exhaustive,
            "corridors_open": [str(c) for c in self.corridors_open],
            "goals_derivable": [str(g) for g in self.goals_derivable],
            "goals_severed": [str(g) for g in self.goals_severed],
            "program": str(self.program),
        }


@dataclass(frozen=True, slots=True)
class PremiumEntry:
    """One premium control, its licences, and how much of it rests on missing calibration.

    `calibration_deficiency` is an exact rational so that a control resting on a source
    this run was never calibrated for is never described as resting on an observed gap.
    """

    control_id: ControlId
    license_ids: tuple[LicenseId, ...]
    calibration_deficiency: Fraction

    def __post_init__(self) -> None:
        reject_run_local_in_certificate(self.control_id, where="premium.control_id")
        for license_id in self.license_ids:
            reject_run_local_in_certificate(license_id, where="premium.license_ids")
        canon.check_strictly_ascending(
            self.license_ids, canon.byte_order_key, where="premium.license_ids"
        )
        if not isinstance(self.calibration_deficiency, Fraction):
            raise SchemaError(
                "premium.calibration_deficiency must be an exact Fraction, never a float",
                code="E-CANON-FLOAT",
            )
        if not 0 <= self.calibration_deficiency <= 1:
            raise SchemaError("premium.calibration_deficiency lies in [0, 1]")
        canon.u32(self.calibration_deficiency.numerator)
        canon.u32(self.calibration_deficiency.denominator)

    def as_member(self) -> dict[str, Any]:
        return {
            "calibration_deficiency": {
                "den": self.calibration_deficiency.denominator,
                "num": self.calibration_deficiency.numerator,
            },
            "control_id": str(self.control_id),
            "license_ids": [str(x) for x in self.license_ids],
        }


@dataclass(frozen=True, slots=True)
class Premium:
    """NEC over the upper corridor database minus OCC over the lower one.

    A property of the two databases, defined by the values of optimisation problems rather
    than by any argmin, so it is invariant to solver order. It is never the set difference
    of two chosen cuts; that object is `cut_delta_canonical` and carries its own caption.
    """

    nec_max: tuple[ControlId, ...]
    occ_min: tuple[ControlId, ...]
    blindness_premium: tuple[ControlId, ...]
    per_control: tuple[PremiumEntry, ...]

    def __post_init__(self) -> None:
        for name in ("nec_max", "occ_min", "blindness_premium"):
            values = getattr(self, name)
            for value in values:
                reject_run_local_in_certificate(value, where=f"premium.{name}")
            canon.check_strictly_ascending(
                values, canon.byte_order_key, where=f"premium.{name}"
            )
        canon.check_strictly_ascending(
            self.per_control,
            lambda e: canon.byte_order_key(str(e.control_id)),
            where="premium.per_control",
        )
        expected = tuple(c for c in self.nec_max if c not in set(self.occ_min))
        if tuple(self.blindness_premium) != expected:
            raise SchemaError(
                "premium.blindness_premium must be exactly nec_max minus occ_min",
                code="E-FLAG-DERIVED",
            )
        listed = {str(e.control_id) for e in self.per_control}
        missing = tuple(str(c) for c in self.blindness_premium if str(c) not in listed)
        if missing:
            raise SchemaError(
                f"premium.per_control omits {missing}; every premium control states its "
                "licences and its calibration deficiency",
                code="E-FLAG-DERIVED",
            )

    def as_member(self) -> dict[str, Any]:
        return {
            "blindness_premium": [str(c) for c in self.blindness_premium],
            "nec_max": [str(c) for c in self.nec_max],
            "occ_min": [str(c) for c in self.occ_min],
            "per_control": [e.as_member() for e in self.per_control],
        }


# ---------------------------------------------------------------------------
# instances_hash
# ---------------------------------------------------------------------------


def instances_hash(instances: tuple[RuleInstance, ...]) -> str:
    """The digest that binds `grounding_mode: "replayed"`.

    Covers the canonical binary encoding of the published instance set in published order
    under the `instances` domain, and nothing else. A checker re-derives it from the
    certificate's own `instances` member: it needs no side file, and a certificate whose
    published instances were edited after the fact fails here rather than at a later
    obligation where the failure would be harder to attribute.
    """
    return canon.hash_ref(
        "instances", canon.ordered_seq(inst.canonical_bytes() for inst in instances)
    )


def _instance_member(inst: RuleInstance) -> dict[str, Any]:
    """The published shape of one instance.

    Wider than the operative specification's `InstRef`, which names only instance_id, head,
    body, blockers, observed and license_ids. `rule_id` and `evidence` are added because
    `instance_id` is minted from body, evidence event ids, head, licence ids and rule id:
    without them a checker cannot re-derive the identifier it is asked to trust, and
    `grounding_mode: "replayed"` would name a replay nobody can perform. `tick`, `ghost`
    and `rule_version` follow for the same reason.
    """
    return {
        "blockers": [canon.mask_hex(m) for m in inst.blockers],
        "body": [str(f) for f in inst.body],
        "evidence": [
            {
                "binding": e.binding,
                "event_id": str(e.event_id),
                "source_id": str(e.source_id),
                "t_evt_ns": str(e.t_evt_ns),
            }
            for e in inst.evidence
        ],
        "ghost": inst.ghost,
        "head": str(inst.head),
        "instance_id": str(inst.instance_id),
        "license_ids": [str(x) for x in inst.license_ids],
        "observed": str(inst.observed),
        "rule_id": str(inst.rule_id),
        "rule_version": inst.rule_version,
        "tick": inst.tick,
    }


def _licence_member(lic: Licence) -> dict[str, Any]:
    member: dict[str, Any] = {
        "basis": str(lic.basis),
        "license_id": str(lic.license_id),
        "reason": lic.reason,
        "source_id": str(lic.source_id),
        "t0_ns": str(lic.t0_ns),
        "t1_ns": str(lic.t1_ns),
    }
    if lic.witness:
        member["witness"] = [str(e) for e in lic.witness]
    return member


def _cut_member(cut: Cut) -> list[dict[str, Any]]:
    return [
        {
            "bit": a.bit,
            "control_id": str(a.control_id),
            "level": a.level,
            "rank": a.rank,
        }
        for a in cut.atoms
    ]


def _atoms_member(atoms: tuple[ThresholdLiteral, ...]) -> dict[str, Any]:
    return {
        "assign": [[str(a.control_id), a.level, a.bit] for a in atoms],
        "n": len(atoms),
    }


# ---------------------------------------------------------------------------
# Body assembly
# ---------------------------------------------------------------------------


def build_body(
    *,
    scope: Scope,
    inputs: Inputs,
    verdict: Verdict,
    atoms: tuple[ThresholdLiteral, ...],
    cut: Cut,
    goals: tuple[GoalRef, ...],
    invariant: tuple[FactHash, ...] | None,
    instances: tuple[RuleInstance, ...],
    licenses: tuple[Licence, ...],
    silent: tuple[SilentRef, ...],
    witnesses: tuple[WitnessEntry, ...],
    psi: Psi,
    premium: Premium | None,
    premium_suppressed_reason: str | None,
    cut_delta_canonical: tuple[ControlId, ...],
    residual: Residual,
    budgets: Budgets,
    observed_event_count: int,
    ghost_count: int,
    psi_min_complete: bool,
) -> dict[str, Any]:
    """Assemble and check the certificate body. Pure in its arguments.

    Every cross-member consistency the checker will test is tested here first, because a
    certificate that a checker rejects is a defect in this stage, not a finding about the
    run.
    """
    _check_scope_binds_inputs(scope, inputs)
    _check_atom_table(atoms, cut)
    _check_instances(instances)
    _check_licences(licenses)
    _check_silent(silent, instances, licenses)
    _check_witnesses(witnesses, instances)
    _check_goals_against_residual(goals, residual, invariant)
    _check_psi_hit(psi, cut)
    _check_counts(instances, observed_event_count, ghost_count)
    _check_premium_preconditions(
        premium=premium,
        premium_suppressed_reason=premium_suppressed_reason,
        psi=psi,
        psi_min_complete=psi_min_complete,
        budgets=budgets,
        flags=verdict.flags,
    )

    if inputs.instances_hash != instances_hash(instances):
        raise SchemaError(
            "inputs.instances_hash does not cover the published instance set",
            code="E-HASH-CERT",
        )

    for control_id in cut_delta_canonical:
        reject_run_local_in_certificate(control_id, where="cut_delta_canonical")
    canon.check_strictly_ascending(
        cut_delta_canonical, canon.byte_order_key, where="cut_delta_canonical"
    )

    body: dict[str, Any] = {
        "atoms": _atoms_member(atoms),
        "budgets": budgets.as_member(),
        "cut": _cut_member(cut),
        "cut_delta_canonical": [str(c) for c in cut_delta_canonical],
        "ghost_count": ghost_count,
        "goals": [g.as_member() for g in goals],
        "inputs": inputs.as_member(),
        "instances": [_instance_member(i) for i in instances],
        "licenses": [_licence_member(x) for x in licenses],
        "observed_event_count": observed_event_count,
        "psi": psi.as_member(),
        "residual": residual.as_member(),
        "schema": {
            "hash_algorithm": canon.HASH_ALGORITHM,
            "hash_substitution_note": canon.HASH_SUBSTITUTION_NOTE,
            "min_checker": MIN_CHECKER,
            "profile": CERT_PROFILE,
            "v": SCHEMA_V,
        },
        "scope": scope.as_member(),
        "silent": [s.as_member() for s in silent],
        "verdict": verdict.as_member(),
        "witnesses": [w.as_member() for w in witnesses],
    }
    if invariant is not None:
        body["invariant"] = {"u": [str(f) for f in invariant]}
    if premium is not None:
        body["premium"] = premium.as_member()
    if premium_suppressed_reason is not None:
        body["premium_suppressed_reason"] = premium_suppressed_reason

    unknown = tuple(sorted(k for k in body if k not in BODY_MEMBERS))
    if unknown:
        raise SchemaError(f"body carries unknown members {unknown}", code="E-SCHEMA-UNKNOWN")
    required = tuple(m for m in BODY_MEMBERS if m not in OPTIONAL_BODY_MEMBERS)
    missing = tuple(m for m in required if m not in body)
    if missing:
        raise SchemaError(f"body omits required members {missing}", code="E-SCHEMA-MISSING")
    return body


def _check_scope_binds_inputs(scope: Scope, inputs: Inputs) -> None:
    scope_member = scope.as_member()
    for scope_name, input_name in SCOPE_TO_INPUT:
        if scope_member[scope_name] != getattr(inputs, input_name):
            raise VerdictError(
                f"scope.{scope_name} disagrees with inputs.{input_name}", code="VRD-012"
            )


def _check_atom_table(atoms: tuple[ThresholdLiteral, ...], cut: Cut) -> None:
    if len(atoms) > 64:
        raise SchemaError(
            f"atoms.n is {len(atoms)}; the mask is 64 bits wide", code="E-LIMIT-COUNT"
        )
    canon.check_strictly_ascending(atoms, lambda a: a.bit, where="atoms.assign")
    expected_rank = sorted(atoms, key=lambda a: a.order_key)
    for index, atom in enumerate(expected_rank):
        if atom.rank != index:
            raise SchemaError(
                f"atoms: {atom.control_id} level {atom.level} carries rank {atom.rank} but "
                f"the canonical atom order puts it at {index}",
                code="E-LITERAL-TABLE",
            )
    table = {(str(a.control_id), a.level): a for a in atoms}
    for atom in cut.atoms:
        published = table.get((str(atom.control_id), atom.level))
        if published is None:
            raise SchemaError(
                f"cut cites {atom.control_id} level {atom.level}, which is not in the atom "
                "table",
                code="E-LITERAL-TABLE",
            )
        if published.bit != atom.bit or published.rank != atom.rank:
            raise SchemaError(
                f"cut cites {atom.control_id} level {atom.level} with bit {atom.bit} rank "
                f"{atom.rank}; the atom table says bit {published.bit} rank {published.rank}",
                code="E-LITERAL-TABLE",
            )


def _check_instances(instances: tuple[RuleInstance, ...]) -> None:
    canon.check_strictly_ascending(
        instances, lambda i: canon.byte_order_key(str(i.instance_id)), where="instances"
    )
    for inst in instances:
        reject_run_local_in_certificate(inst.instance_id, where="instances.instance_id")
        reject_run_local_in_certificate(inst.head, where="instances.head")
        if not inst.verify_id():
            raise SchemaError(
                f"instances: {inst.instance_id} does not recompute from its own fields",
                code="E-HASH-CERT",
            )


def _check_licences(licenses: tuple[Licence, ...]) -> None:
    canon.check_strictly_ascending(licenses, lambda x: x.sort_key(), where="licenses")
    for lic in licenses:
        reject_run_local_in_certificate(lic.license_id, where="licenses.license_id")
        if not lic.verify_id():
            raise SchemaError(
                f"licenses: {lic.license_id} does not recompute from its own fields",
                code="E-HASH-CERT",
            )


def _check_silent(
    silent: tuple[SilentRef, ...],
    instances: tuple[RuleInstance, ...],
    licenses: tuple[Licence, ...],
) -> None:
    canon.check_strictly_ascending(
        silent, lambda s: canon.byte_order_key(str(s.instance_id)), where="silent"
    )
    by_id = {str(i.instance_id): i for i in instances}
    known = {str(x.license_id) for x in licenses}
    expected = tuple(
        sorted(
            (str(i.instance_id) for i in instances if i.license_ids),
            key=canon.byte_order_key,
        )
    )
    published = tuple(str(s.instance_id) for s in silent)
    if published != expected:
        raise SchemaError(
            "silent must list exactly the published instances that cite a licence",
            code="E-LICENSE-UNIMPLIED",
        )
    for ref in silent:
        inst = by_id[str(ref.instance_id)]
        if tuple(str(x) for x in ref.license_ids) != tuple(str(x) for x in inst.license_ids):
            raise SchemaError(
                f"silent: {ref.instance_id} cites licences the instance does not",
                code="E-LICENSE-UNIMPLIED",
            )
        for license_id in ref.license_ids:
            if str(license_id) not in known:
                raise SchemaError(
                    f"silent: {license_id} is not in the published licence set",
                    code="E-LICENSE-UNIMPLIED",
                )


def _check_witnesses(
    witnesses: tuple[WitnessEntry, ...], instances: tuple[RuleInstance, ...]
) -> None:
    canon.check_strictly_ascending(
        witnesses,
        lambda w: canon.byte_order_key(str(w.removed_control)),
        where="witnesses",
    )
    by_id = {str(i.instance_id): i for i in instances}
    for entry in witnesses:
        _walk_witness(entry.tree, by_id, seen=())


def _walk_witness(
    node: WitnessNode, by_id: dict[str, RuleInstance], *, seen: tuple[str, ...]
) -> None:
    key = str(node.instance_id)
    if key in seen:
        raise SchemaError(
            f"witness: {key} supports itself; the tree is not well founded",
            code="E-WITNESS-CYCLE",
        )
    inst = by_id.get(key)
    if inst is None:
        raise SchemaError(
            f"witness: {key} is not in the published instance set", code="E-WITNESS-EVENT"
        )
    if str(inst.head) != str(node.head):
        raise SchemaError(
            f"witness: {key} heads {inst.head}, not {node.head}", code="E-WITNESS-EVENT"
        )
    if node.kind is WitnessKind.GHOST and not inst.ghost:
        raise SchemaError(
            f"witness: {key} is marked GHOST but the instance is not", code="E-GHOST-COUNT"
        )
    for child in node.children:
        _walk_witness(child, by_id, seen=(*seen, key))


def _check_goals_against_residual(
    goals: tuple[GoalRef, ...], residual: Residual, invariant: tuple[FactHash, ...] | None
) -> None:
    canon.check_strictly_ascending(
        goals, lambda g: canon.byte_order_key(str(g.goal_key)), where="goals"
    )
    derivable = tuple(
        sorted((str(g.goal_key) for g in goals if g.derivable), key=canon.byte_order_key)
    )
    severed = tuple(
        sorted((str(g.goal_key) for g in goals if not g.derivable), key=canon.byte_order_key)
    )
    if derivable != tuple(str(g) for g in residual.goals_derivable):
        raise SchemaError("goals disagree with residual.goals_derivable", code="E-GOAL-MEMBER")
    if severed != tuple(str(g) for g in residual.goals_severed):
        raise SchemaError("goals disagree with residual.goals_severed", code="E-GOAL-MEMBER")
    every_goal_severed = not derivable
    if every_goal_severed and invariant is None:
        raise SchemaError(
            "every goal is severed, so the closure invariant U is required",
            code="E-SCHEMA-MISSING",
        )
    if not every_goal_severed and invariant is not None:
        raise SchemaError(
            "the closure invariant is published only when every goal is severed",
            code="E-SCHEMA-UNKNOWN",
        )
    if invariant is not None:
        canon.check_strictly_ascending(
            invariant, canon.byte_order_key, where="invariant.u"
        )
        for fact_key in invariant:
            reject_run_local_in_certificate(fact_key, where="invariant.u")
        in_u = set(str(f) for f in invariant)
        for goal in severed:
            if goal in in_u:
                raise SchemaError(
                    f"invariant: severed goal {goal} is present in U", code="E-GOAL-MEMBER"
                )


def _check_psi_hit(psi: Psi, cut: Cut) -> None:
    """Every published corridor is hit by the published cut.

    The slice narrowing makes every blocker term a single literal, so a corridor is a plain
    disjunction and `mask & cut.mask` is the whole test. The general subset form stays in
    the reachability stage behind its assertion.
    """
    for corridor in psi.corridors:
        if not corridor.mask & cut.mask:
            raise SchemaError(
                f"psi: corridor {corridor.corridor_id} is not hit by the published cut",
                code="E-PSI-HIT",
            )


def _check_counts(
    instances: tuple[RuleInstance, ...], observed_event_count: int, ghost_count: int
) -> None:
    """Two separate members. A single summed member is forbidden.

    `observed_event_count` counts distinct records cited by OBSERVED instances and nothing
    else; a silent instance cites no record and a GHOST head is not an event, so neither
    can reach it.
    """
    canon.u32(observed_event_count)
    canon.u32(ghost_count)
    events: set[str] = set()
    ghosts: set[str] = set()
    for inst in instances:
        for ref in inst.evidence:
            events.add(str(ref.event_id))
        if inst.ghost:
            ghosts.add(str(inst.head))
    if observed_event_count != len(events):
        raise SchemaError(
            f"observed_event_count is {observed_event_count} but the published OBSERVED "
            f"instances cite {len(events)} distinct records",
            code="E-GHOST-COUNT",
        )
    if ghost_count != len(ghosts):
        raise SchemaError(
            f"ghost_count is {ghost_count} but {len(ghosts)} facts are GHOST-headed",
            code="E-GHOST-COUNT",
        )


def _check_premium_preconditions(
    *,
    premium: Premium | None,
    premium_suppressed_reason: str | None,
    psi: Psi,
    psi_min_complete: bool,
    budgets: Budgets,
    flags: tuple[str, ...],
) -> None:
    """The premium is published or its reason is, never both and never neither.

    Absent is absent: when a precondition fails the whole member is omitted from the hashed
    bytes rather than written as null, zero, an empty object or the string N/A.
    """
    if (premium is None) == (premium_suppressed_reason is None):
        raise SchemaError(
            "exactly one of premium and premium_suppressed_reason is present",
            code="E-FLAG-DERIVED",
        )
    if premium_suppressed_reason is not None:
        if premium_suppressed_reason not in PREMIUM_SUPPRESSED_REASONS:
            raise SchemaError(
                f"premium_suppressed_reason {premium_suppressed_reason!r} is not in the "
                f"closed set {PREMIUM_SUPPRESSED_REASONS}",
                code="E-SCHEMA-UNKNOWN",
            )
        return
    unmet = []
    if not psi.complete:
        unmet.append("the upper corridor database did not reach fixpoint")
    if not psi_min_complete:
        unmet.append("the lower corridor database did not reach fixpoint")
    if "grounding_capped" in flags:
        unmet.append("grounding_capped is set")
    if "corridor_cap" in flags:
        unmet.append("corridor_cap is set")
    if budgets.budget_exhausted:
        unmet.append("a deterministic budget fired")
    if unmet:
        raise SchemaError(
            "premium published while " + "; ".join(unmet) + "; the member is omitted instead",
            code="E-FLAG-DERIVED",
        )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

#: The one member permitted to hold `null`, per the encoding law's single exception.
NULL_MEMBER_PATH: Final[tuple[str, ...]] = ("body", "verdict", "witness_class")


def _validate_certificate_document(document: dict[str, Any]) -> None:
    """Run the SCF-lite law over the document, with the one present-and-null exception.

    `spectra_vs.scf.validate_scf` rejects `None` outright, which is correct for every other
    artifact in the slice. The certificate has exactly one permitted null, so the value is
    lifted out, the rest is validated by the shared validator, and the depth and NFC passes
    run over the whole thing.
    """
    stripped = json.loads(json.dumps(document, default=_reject_unserialisable))
    node: Any = stripped
    for key in NULL_MEMBER_PATH[:-1]:
        node = node[key]
    if NULL_MEMBER_PATH[-1] not in node:
        raise SchemaError(
            "verdict.witness_class is present on every verdict, and null on non-UNSAFE",
            code="E-SCHEMA-MISSING",
        )
    if node[NULL_MEMBER_PATH[-1]] is None:
        del node[NULL_MEMBER_PATH[-1]]
    scf.validate_scf(stripped, where="cert")
    _check_depth(document, depth=1, where="cert")
    _check_text(document, where="cert")


def _reject_unserialisable(value: object) -> Any:
    raise SchemaError(f"cert: {type(value).__name__} has no SCF-lite encoding")


def _check_depth(value: object, *, depth: int, where: str) -> None:
    """Count nested CONTAINERS, not scalars: a string inside an array is not a level.

    The document object is depth 1. The contract's cap of eight therefore allows a witness
    tree a root node and one level of children, and the emitter refuses a deeper tree
    rather than writing a file a checker is obliged to reject.
    """
    if not isinstance(value, (dict, list)):
        return
    if depth > MAX_DEPTH:
        raise SchemaError(
            f"{where}: nesting deeper than {MAX_DEPTH} containers", code="E-LIMIT-DEPTH"
        )
    if isinstance(value, dict):
        for key, member in value.items():
            _check_depth(member, depth=depth + 1, where=f"{where}.{key}")
    else:
        for index, member in enumerate(value):
            _check_depth(member, depth=depth + 1, where=f"{where}[{index}]")


def _check_text(value: object, *, where: str) -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise SchemaError(f"{where}: text is not NFC", code="E-CANON-NFC")
        for ch in value:
            if ord(ch) < 0x20 or ord(ch) == 0x7F:
                raise SchemaError(
                    f"{where}: control character U+{ord(ch):04X}", code="E-CANON-NFC"
                )
    elif isinstance(value, dict):
        for key, member in value.items():
            _check_text(key, where=f"{where}.<key>")
            _check_text(member, where=f"{where}.{key}")
    elif isinstance(value, list):
        for index, member in enumerate(value):
            _check_text(member, where=f"{where}[{index}]")


def certificate_bytes(body: dict[str, Any]) -> bytes:
    """The exact octets of the certificate file: the document, UTF-8, one trailing LF.

    `cert_hash` covers `canon.hash_ref("cert", scf(body))` -- the canonical serialisation
    of `body` and nothing else. The self-reference is well founded because the digest is
    taken over `body` before `cert_hash` is placed beside it, and no member is carved out.
    """
    body_octets = _body_octets(body)
    document = {"body": body, "cert_hash": canon.hash_ref("cert", body_octets)}
    _validate_certificate_document(document)
    text = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    octets = (text + "\n").encode("utf-8")
    if not octets.startswith(FILE_MAGIC):
        raise SchemaError(
            f"cert: the file does not open with {FILE_MAGIC!r}", code="E-CANON-FORM"
        )
    return octets


def _body_octets(body: dict[str, Any]) -> bytes:
    """The canonical octets of `body` alone, with no trailing newline.

    The trailing LF belongs to the file, not to the hash preimage: including it would make
    the digest depend on how the body happened to be framed.
    """
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CertificateArtifact:
    """What `emit` returns: the octets, the digest, and the rendering that must accompany it."""

    octets: bytes
    cert_hash: str
    short: str
    long: str


def emit(body: dict[str, Any], verdict: Verdict, scope: Scope) -> CertificateArtifact:
    """Serialise a body and produce the renderings that must travel with it.

    The renderings are produced here, beside the bytes, so that a caller cannot obtain a
    certificate without also obtaining the scope clause that every rendering of its verdict
    must carry.
    """
    octets = certificate_bytes(body)
    return CertificateArtifact(
        octets=octets,
        cert_hash=canon.hash_ref("cert", _body_octets(body)),
        short=render_short(verdict, scope),
        long=render_long(verdict, scope),
    )


def write_certificate(path: Path, artifact: CertificateArtifact) -> Path:
    """Write the certificate octets with no newline translation and no BOM."""
    scf.write_bytes(path, artifact.octets)
    return path
