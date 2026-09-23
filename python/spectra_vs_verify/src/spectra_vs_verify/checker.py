"""The sixteen obligations, in order, stopping at the first failure.

WHAT IS RE-DERIVED HERE AND WHAT IS MERELY SHARED. The octet encoders and the digest come
from `spectra_core.canon`: reimplementing `u32` or `leb128` would test nothing but an
ability to copy, and the digest must be the same function on both sides or no comparison
means anything. What IS written a second time here is every preimage -- which fields go
into which digest, in which order -- and every algorithm the certificate's claims rest on:
the reachability closure, the corridor-hitting test, the level-minimality test, the cut
search that looks for something smaller, the licence-implication test against the pinned
liveness document, and the witness-tree replay. A transcription slip on either side turns
one of those red. A misreading of the specification shared by both sides does not, and
`spectra_vs_verify.INDEPENDENCE_STATEMENT` says so in the report.

THE CHECKER NEVER SORTS. It verifies sortedness in one scan and rejects on E-CANON-ORDER.
Sorting would mask an emitter that emitted in hash-map order, which is the determinism
defect this design exists to prevent. It never allocates from a declared count: it
allocates from observed array length and then compares to any declared count. It never
decompresses; a compression magic in the first two octets is E-LIMIT-COMPRESSED.

COST. O0 through O14 are linear in the certificate: each structure is traversed a constant
number of times. O15 IS NOT LINEAR -- it searches the control lattice -- and it is fenced
in the report with its own cost line. The claim that the whole check is one linear pass is
false and is not repeated here.

TWO TRANSLATIONS, DECLARED RATHER THAN SILENT. Neither repairs an input; both map between
two file formats that spell the same concept differently, and any difference other than
the named prefix is a rejection.

  * `catalog-bits.lock` is authored with a bare `control_id = "egress_seg"`. The
    certificate carries the section 57 identifier `ctl:egress_seg`. The checker compares
    the lock row to the certificate row with that one prefix accounted for.
  * `rules.toml` is authored with `id = "r0003"`; the certificate carries `rl:r0003`.
  * A source named bare in `rules.toml` or in `liveness.json` maps to `src:<name>`. A name
    already carrying the prefix is left alone.

WHAT AN ACCEPT MEANS. The certificate is internally consistent with the hashed inputs.
Not that the bundle is truthful, not that entity resolution was right, not that the
control catalog is complete, not that grounding found every instance, and not that the
certificate was independently verified.
"""

from __future__ import annotations

import json
import re
import tomllib
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any, Final

from spectra_core import canon

__all__ = [
    "ACCEPT",
    "BODY_MEMBERS",
    "CHECKER_VERSION",
    "EXHAUSTIVE_CUT_CAP",
    "FILE_MAGIC",
    "FLAG_BITS",
    "INDEPENDENCE_STATEMENT",
    "INPUT_COVERAGE",
    "MAX_DEPTH",
    "OBLIGATIONS",
    "REJECT",
    "RESERVED_MASK",
    "SOUNDNESS_MASK",
    "USAGE",
    "CheckerInputs",
    "ObligationResult",
    "Report",
    "verify",
]

#: 1.1 since ADR-0015, which publishes witness trees flat and adds the LICENSED node kind.
#: Written here rather than imported: the checker takes nothing from the emitter's package.
CHECKER_VERSION: Final[str] = "1.1"
SCHEMA_V: Final[str] = "1.1"

#: Witness node kinds that stand for an unobserved step (ADR-0015).
_SILENT_KINDS: Final[frozenset[str]] = frozenset({"GHOST", "LICENSED"})
ACCEPT: Final[int] = 0
REJECT: Final[int] = 1
USAGE: Final[int] = 2

FILE_MAGIC: Final[bytes] = b'{"body":{'
#: Nested CONTAINERS, counting the document object as the first. A scalar inside an array
#: is not a level of its own.
MAX_DEPTH: Final[int] = 8
EXHAUSTIVE_CUT_CAP: Final[int] = 200000

INDEPENDENCE_STATEMENT: Final[str] = (
    "MODULE INDEPENDENCE ONLY. This checker imports nothing from the package that emitted "
    "the certificate, but both are Python written in one session by one author from one "
    "reading of one specification, and both share spectra_core for the octet encoders and "
    "the digest. A shared misreading of a rule, a guard or the specification is invisible "
    "to this check. The certificate this program accepts may not be described as "
    "independently verified."
)

ACCEPT_MEANING: Final[str] = (
    "ACCEPT means the certificate is internally consistent with the inputs it pins. It "
    "says nothing about whether the bundle is truthful, whether entity resolution was "
    "correct, whether the control catalog is complete, or whether grounding found every "
    "instance."
)

IMPLEMENTATION_NOTE: Final[str] = (
    "PYTHON REFERENCE IMPLEMENTATION. Digests are blake2b-256 labelled b2b256:, not the "
    "algorithm the specification names; no digest here is comparable with a specified one."
)

#: `(input member, digest domain, argv option, what octets it covers)`. Written out a
#: second time rather than imported: a checker that took the emitter's word for what a
#: hash covers could not disagree with it.
INPUT_COVERAGE: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("rules_hash", "rules", "rules_cae", "octets of the canonical rule-encoding artifact"),
    ("rules_text_hash", "rulestext", "rules", "octets of rules.toml; forensic only"),
    ("guard_ast_hash", "guardast", "guards", "octets of guards.cae"),
    ("controls_hash", "controls", "controls_cae", "octets of the control-catalog encoding"),
    ("catalog_bits_hash", "catbits", "catalog_bits", "octets of catalog-bits.lock"),
    ("bundle_hash", "bundle", "bundle", "octets of bundle.jsonl"),
    ("liveness_hash", "liveness", "liveness", "octets of liveness.json"),
    ("profile_hash", "profile", "profile", "octets of the source profile"),
    ("goal_hash", "goal", "goal_cae", "octets of the canonical goal-library encoding"),
    ("er_hash", "er", "er", "octets of er.json"),
)

#: Recomputed from the certificate's own bytes, so it names no file.
INSTANCES_DOMAIN: Final[str] = "instances"

#: Forensic only: a mismatch is a note, never a rejection.
ADVISORY_INPUTS: Final[frozenset[str]] = frozenset({"rules_text_hash"})

SCOPE_TO_INPUT: Final[tuple[tuple[str, str], ...]] = (
    ("bundle", "bundle_hash"),
    ("controls", "controls_hash"),
    ("er", "er_hash"),
    ("goal", "goal_hash"),
    ("liveness", "liveness_hash"),
    ("rules", "rules_hash"),
)

#: bit position -> flag name. Duplicated from the emitter deliberately.
FLAG_BITS: Final[tuple[tuple[int, str], ...]] = (
    (0, "grounding_capped"),
    (1, "corridor_cap"),
    (2, "atoms_over_budget"),
    (3, "er_ambiguous"),
    (4, "quarantined_records"),
    (5, "license_voided_by_suspected_tampering"),
    (6, "greedy_cover"),
    (7, "sampled_matrix"),
    (8, "profile_missing"),
)
_BIT_OF: Final[dict[str, int]] = {name: bit for bit, name in FLAG_BITS}
_SOUNDNESS_BITS: Final[tuple[int, ...]] = (0, 1, 3, 4, 5, 8)
SOUNDNESS_MASK: Final[int] = sum(1 << b for b in _SOUNDNESS_BITS)
RESERVED_MASK: Final[int] = sum(1 << b for b in range(len(FLAG_BITS), 16))
_MINIMALITY_CAP_FLAGS: Final[tuple[str, ...]] = ("atoms_over_budget", "corridor_cap")

_SAFETY: Final[frozenset[str]] = frozenset(
    {"ROBUST", "OPTIMISTIC_ONLY", "UNSAFE", "INDETERMINATE"}
)
_WITNESS_CLASS: Final[frozenset[str]] = frozenset({"OBSERVED", "LICENSED", "CONTESTED"})
_MINIMALITY: Final[frozenset[str]] = frozenset(
    {"EXACT_EXHAUSTIVE", "EXACT_PSI_RELATIVE", "SUBSET", "UNVERIFIED"}
)
_REALIZABILITY: Final[frozenset[str]] = frozenset({"CHECKED", "UNCHECKED"})
_DERIVED_SUPPRESSED_ALWAYS: Final[tuple[str, ...]] = ("pareto_frontier", "redundancy_index")

BODY_MEMBERS: Final[frozenset[str]] = frozenset(
    {
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
    }
)

_REQUIRED_BODY_MEMBERS: Final[tuple[str, ...]] = (
    "atoms",
    "budgets",
    "cut",
    "cut_delta_canonical",
    "ghost_count",
    "goals",
    "inputs",
    "instances",
    "licenses",
    "observed_event_count",
    "psi",
    "residual",
    "schema",
    "scope",
    "silent",
    "verdict",
    "witnesses",
)

#: The only path in the document where `null` is a value, per the encoding law's one
#: stated exception.
_NULL_PATH: Final[tuple[str, ...]] = ("body", "verdict", "witness_class")

_KEY: Final = re.compile(r"\A[a-z0-9_]+\Z")
_MASK: Final = re.compile(r"\A0x[0-9a-f]{16}\Z")
_I64_TEXT: Final = re.compile(r"\A-?(?:0|[1-9][0-9]*)\Z")
_U32_MAX: Final[int] = (1 << 32) - 1
_COMPRESSION_MAGICS: Final[tuple[bytes, ...]] = (b"\x1f\x8b", b"PK", b"BZ", b"\xfd7", b"\x28\xb5")


class Rejected(Exception):
    """One obligation failed. Carries the reason code the corpus asserts on."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class Usage(Exception):
    """An argv or I/O problem. Exit 2; never a verdict about the certificate."""


@dataclass(frozen=True, slots=True)
class CheckerInputs:
    """Every file the obligations need, one per pinned digest plus the run manifest.

    The specification's seven-flag command line does not name a file for every member of
    `inputs`, and guessing a preimage would be the checker inventing what a hash covers.
    There is therefore one option per hash, and a hash whose file is absent is a rejection
    rather than a skipped obligation.
    """

    rules: Path | None = None
    rules_cae: Path | None = None
    guards: Path | None = None
    controls_cae: Path | None = None
    catalog_bits: Path | None = None
    bundle: Path | None = None
    liveness: Path | None = None
    profile: Path | None = None
    goal_cae: Path | None = None
    er: Path | None = None
    run_manifest: Path | None = None

    def path_for(self, option: str) -> Path | None:
        return getattr(self, option)


@dataclass(frozen=True, slots=True)
class ObligationResult:
    """One obligation and what it decided. `cost` is a deterministic counter, never a time."""

    name: str
    ok: bool
    detail: str
    code: str = ""
    cost: int = 0


@dataclass(slots=True)
class Report:
    """The whole check. `exit_code` is 0 ACCEPT, 1 REJECT, 2 usage or I/O."""

    exit_code: int
    code: str
    results: list[ObligationResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    independence: str = INDEPENDENCE_STATEMENT
    accept_meaning: str = ACCEPT_MEANING
    implementation: str = IMPLEMENTATION_NOTE

    @property
    def accepted(self) -> bool:
        return self.exit_code == ACCEPT

    def as_json(self) -> dict[str, Any]:
        return {
            "accept": self.accepted,
            "accept_meaning": self.accept_meaning,
            "code": self.code,
            "implementation": self.implementation,
            "independence": self.independence,
            "notes": list(self.notes),
            "obligations": [
                {
                    "code": r.code,
                    "cost": r.cost,
                    "detail": r.detail,
                    "name": r.name,
                    "ok": r.ok,
                }
                for r in self.results
            ],
        }

    def render(self) -> str:
        lines = [f"checker {CHECKER_VERSION}", IMPLEMENTATION_NOTE, ""]
        for result in self.results:
            mark = "ok  " if result.ok else "FAIL"
            suffix = f"  [{result.code}]" if result.code else ""
            cost = f"  (cost {result.cost})" if result.cost else ""
            lines.append(f"{mark} {result.name}: {result.detail}{suffix}{cost}")
        lines.append("")
        for note in self.notes:
            lines.append(f"NOTE {note}")
        lines.append("")
        lines.append("ACCEPT" if self.accepted else f"REJECT {self.code}")
        lines.append(self.accept_meaning if self.accepted else "")
        lines.append(self.independence)
        return "\n".join(line for line in lines if line is not None)


# ---------------------------------------------------------------------------
# Strict reading
# ---------------------------------------------------------------------------


def _floats_are_forbidden(_text: str) -> float:  # noqa: returns nothing; it raises
    raise Rejected("E-CANON-FLOAT", "a float reached a number position")


def _reject_constant(name: str) -> Any:
    raise Rejected("E-CANON-FLOAT", f"the JSON constant {name} is not a value")


def _pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise Rejected("E-CANON-DUPKEY", f"duplicate object key {key!r}")
        if _KEY.match(key) is None:
            raise Rejected("E-CANON-FORM", f"object key {key!r} is not ASCII [a-z0-9_]+")
        seen[key] = value
    return seen


def _read_octets(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise Usage(f"cannot read {path}: {exc}") from None


def _parse_document(octets: bytes) -> dict[str, Any]:
    """Parse the certificate file under the encoding law, rejecting rather than repairing."""
    if octets[:2] in _COMPRESSION_MAGICS:
        raise Rejected("E-LIMIT-COMPRESSED", "the first two octets are a compression magic")
    if not octets.startswith(FILE_MAGIC):
        raise Rejected(
            "E-SCHEMA-MISSING", f"the file does not open with {FILE_MAGIC.decode('ascii')!r}"
        )
    if not octets.endswith(b"\n") or octets.count(b"\n") != 1:
        raise Rejected("E-CANON-TRAILING", "the file is not one line with exactly one LF")
    if b"\r" in octets:
        raise Rejected("E-CANON-FORM", "a CR octet is in the file")
    try:
        text = octets.decode("utf-8")
    except UnicodeDecodeError:
        raise Rejected("E-CANON-FORM", "the file is not valid UTF-8") from None
    try:
        document = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_float=_floats_are_forbidden,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise Rejected("E-CANON-FORM", f"the file is not JSON: {exc.msg}") from None
    if not isinstance(document, dict):
        raise Rejected("E-CANON-FORM", "the document is not an object")
    return document


def _walk_values(document: dict[str, Any]) -> None:
    """One scan for nulls, floats, over-wide integers, non-NFC text and depth."""

    def walk(value: object, path: tuple[str, ...], depth: int) -> None:
        if isinstance(value, (dict, list)) and depth > MAX_DEPTH:
            raise Rejected(
                "E-LIMIT-DEPTH", f"{'.'.join(path)} nests deeper than {MAX_DEPTH} containers"
            )
        if value is None:
            if path != _NULL_PATH:
                raise Rejected("E-CANON-NULL", f"null at {'.'.join(path)}")
            return
        if isinstance(value, bool):
            return
        if isinstance(value, float):
            raise Rejected("E-CANON-FLOAT", f"float at {'.'.join(path)}")
        if isinstance(value, int):
            if not 0 <= value <= _U32_MAX:
                raise Rejected(
                    "E-CANON-WIDTH",
                    f"{'.'.join(path)} is a bare integer outside u32; masks, seeds and "
                    "nanosecond instants are strings",
                )
            return
        if isinstance(value, str):
            if unicodedata.normalize("NFC", value) != value:
                raise Rejected("E-CANON-NFC", f"{'.'.join(path)} is not NFC")
            for ch in value:
                if ord(ch) < 0x20 or ord(ch) == 0x7F:
                    raise Rejected("E-CANON-NFC", f"{'.'.join(path)} has a control character")
            return
        if isinstance(value, dict):
            for key, member in value.items():
                walk(member, (*path, key), depth + 1)
            return
        if isinstance(value, list):
            for index, member in enumerate(value):
                walk(member, (*path, str(index)), depth + 1)
            return
        raise Rejected("E-CANON-FORM", f"{'.'.join(path)} has no SCF-lite encoding")

    walk(document, (), 1)


def _dumps(value: object, *, sort_keys: bool = True) -> str:
    return json.dumps(
        value, sort_keys=sort_keys, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _ascending(values: list[Any], *, where: str) -> None:
    """Verify strict ascent in one scan. It never sorts; sorting would mask the defect."""
    for index in range(1, len(values)):
        if not values[index - 1] < values[index]:
            raise Rejected("E-CANON-ORDER", f"{where} is not strictly ascending at {index}")


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise Rejected(code, detail)


def _member(obj: dict[str, Any], name: str, where: str) -> Any:
    if name not in obj:
        raise Rejected("E-SCHEMA-MISSING", f"{where} omits {name!r}")
    return obj[name]


def _int_text(value: object, where: str) -> int:
    if not isinstance(value, str) or _I64_TEXT.match(value) is None:
        raise Rejected("E-CANON-WIDTH", f"{where} is not a decimal integer string")
    return int(value)


def _mask_text(value: object, where: str) -> int:
    if not isinstance(value, str) or _MASK.match(value) is None:
        raise Rejected("E-CANON-WIDTH", f"{where} is not a 0x%016x mask string")
    return int(value, 16)


# ---------------------------------------------------------------------------
# Preimages, written a second time on purpose
# ---------------------------------------------------------------------------


def _src(name: str) -> str:
    """The declared translation between an authored source name and its 57.2 identifier."""
    return name if name.startswith("src:") else "src:" + name


def _fact_id_ok(value: str) -> bool:
    return value.startswith("fh:") and len(value) == 3 + 64


def _instance_preimage(inst: dict[str, Any]) -> bytes:
    """body, evidence event ids, head, licence ids, rule id. Blocker masks are excluded."""
    return b"".join(
        (
            canon.ordered_seq(canon.ascii_text(f) for f in inst["body"]),
            canon.ordered_seq(canon.ascii_text(e["event_id"]) for e in inst["evidence"]),
            canon.ascii_text(inst["head"]),
            canon.ordered_seq(canon.ascii_text(x) for x in inst["license_ids"]),
            canon.ascii_text(inst["rule_id"]),
        )
    )


def _instance_canonical(inst: dict[str, Any]) -> bytes:
    """The whole instance in the fixed field order the data contract declares."""
    return b"".join(
        (
            canon.ordered_seq(canon.u64(_mask_text(m, "blockers")) for m in inst["blockers"]),
            canon.ordered_seq(canon.ascii_text(f) for f in inst["body"]),
            canon.ordered_seq(
                canon.utf8_text(e["binding"])
                + canon.ascii_text(e["event_id"])
                + canon.ascii_text(e["source_id"])
                + canon.i64(_int_text(e["t_evt_ns"], "evidence.t_evt_ns"))
                for e in inst["evidence"]
            ),
            canon.boolean(inst["ghost"]),
            canon.ascii_text(inst["head"]),
            canon.ascii_text(inst["instance_id"]),
            canon.ordered_seq(canon.ascii_text(x) for x in inst["license_ids"]),
            canon.ascii_text(inst["observed"]),
            canon.ascii_text(inst["rule_id"]),
            canon.ascii_text(inst["rule_version"]),
            canon.u32(inst["tick"]),
        )
    )


def _licence_preimage(lic: dict[str, Any]) -> bytes:
    """basis, reason, source_id, t0_ns, t1_ns. The witness is not part of the identity."""
    return b"".join(
        (
            canon.ascii_text(lic["basis"]),
            canon.utf8_text(lic["reason"]),
            canon.ascii_text(lic["source_id"]),
            canon.i64(_int_text(lic["t0_ns"], "licenses.t0_ns")),
            canon.i64(_int_text(lic["t1_ns"], "licenses.t1_ns")),
        )
    )


def _event_preimage(record: dict[str, Any]) -> bytes:
    """attrs, event_type, seq, source_id, t_evt_ns. Ingestion time is excluded.

    THE SOURCE ID IS RE-TYPED. A bundle line spells `source_id` bare, as the data contract
    does on every wire; section 57.2 types the same value `src:<id>`, and the event-id
    preimage is taken over the typed form. This function once hashed the bare spelling,
    and every real record failed to recompute. The test fixture had hidden it by writing
    the typed spelling into its bundle, which real ingest never does (BUILD_LOG INC-0012).
    A typed spelling in the file is therefore a contract violation, not a second form.
    """
    attrs = record.get("attrs", {})
    if not isinstance(attrs, dict):
        raise Rejected("E-WITNESS-EVENT", "a bundle record's attrs is not an object")
    source = record["source_id"]
    _require(
        isinstance(source, str) and not source.startswith(_SOURCE_PREFIX),
        "E-WITNESS-EVENT",
        f"bundle source_id {source!r} is not spelled bare",
    )
    return b"".join(
        (
            canon.pairs(tuple(attrs.items())),
            canon.utf8_text(record["event_type"]),
            canon.u32(record["seq"]),
            canon.ascii_text(_SOURCE_PREFIX + source),
            canon.i64(_int_text(record["t_evt_ns"], "bundle.t_evt_ns")),
        )
    )


#: The type prefix section 57.2 gives a source id in memory and in digest preimages.
_SOURCE_PREFIX: Final[str] = "src:"


# ---------------------------------------------------------------------------
# Reachability, written a second time on purpose
# ---------------------------------------------------------------------------


def _blocked(blockers: list[int], cut_mask: int) -> bool:
    """The general subset form, kept so the slice narrowing stays visible in the source.

    Under C-SLICE-1 every term has popcount one and this collapses to `mask & S != 0`; the
    subset test is written out anyway so that a future conjunctive term does not silently
    take the wrong branch.
    """
    return any((term & cut_mask) == term for term in blockers)


def _reach(
    instances: list[dict[str, Any]], axioms: list[str], cut_mask: int
) -> tuple[set[str], int]:
    """Dowling-Gallier unit propagation. Returns the least fixpoint and a step counter.

    No early exit on reaching a goal: the whole closure is the invariant the certificate
    publishes, so the whole closure is what has to be computed.
    """
    masks = [[_mask_text(m, "blockers") for m in inst["blockers"]] for inst in instances]
    by_body: dict[str, list[int]] = {}
    for index, inst in enumerate(instances):
        for fact in inst["body"]:
            by_body.setdefault(fact, []).append(index)
    count = [len(inst["body"]) for inst in instances]
    derived: set[str] = set()
    queue: deque[str] = deque(sorted(axioms))
    for index, inst in enumerate(instances):
        if count[index] == 0 and not _blocked(masks[index], cut_mask):
            queue.append(inst["head"])
    steps = 0
    while queue:
        fact = queue.popleft()
        if fact in derived:
            continue
        derived.add(fact)
        for index in by_body.get(fact, ()):
            if _blocked(masks[index], cut_mask):
                continue
            count[index] -= 1
            steps += 1
            if count[index] == 0:
                queue.append(instances[index]["head"])
        steps += 1
    return derived, steps


def _axioms_of(instances: list[dict[str, Any]]) -> list[str]:
    """Facts that appear in a body and are the head of no published instance."""
    heads = {inst["head"] for inst in instances}
    bodies: set[str] = set()
    for inst in instances:
        bodies.update(inst["body"])
    return sorted(bodies - heads)


# ---------------------------------------------------------------------------
# The obligations
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _State:
    """Everything an obligation may assume a previous obligation established."""

    octets: bytes
    document: dict[str, Any]
    body: dict[str, Any]
    inputs: CheckerInputs
    notes: list[str]
    atom_by_rank: dict[int, tuple[str, int, int]] = field(default_factory=dict)
    atom_bits: dict[tuple[str, int], int] = field(default_factory=dict)
    control_levels: dict[str, list[int]] = field(default_factory=dict)
    cut_mask: int = 0
    cut_controls: dict[str, int] = field(default_factory=dict)
    corridor_masks: list[int] = field(default_factory=list)
    invariant: set[str] = field(default_factory=set)
    flags: tuple[str, ...] = ()
    flag_mask: int = 0


def _o0_canonicity(state: _State) -> ObligationResult:
    _walk_values(state.document)
    unknown = sorted(k for k in state.document if k not in ("body", "cert_hash"))
    _require(not unknown, "E-SCHEMA-UNKNOWN", f"document carries {unknown}")
    canonical = (_dumps(state.document) + "\n").encode("utf-8")
    if canonical != state.octets:
        as_written = (_dumps(state.document, sort_keys=False) + "\n").encode("utf-8")
        if as_written == state.octets:
            raise Rejected("E-CANON-ORDER", "object keys are not sorted by byte value")
        raise Rejected(
            "E-CANON-FORM", "re-serialising the parsed document does not reproduce the file"
        )
    return ObligationResult("O0 canonicity", True, "re-serialisation reproduces the file")


def _version(text: object) -> tuple[int, ...]:
    """A dotted version as a tuple of integers, compared numerically.

    Compared as strings, "1.10" sorts below "1.9" and a newer checker would refuse a file it
    can read. A value that is not dotted decimal digits is a downgrade attempt, not a crash.
    """
    _require(
        isinstance(text, str)
        and bool(text)
        and all(part.isdigit() and part.isascii() for part in text.split(".")),
        "E-SCHEMA-DOWNGRADE",
        f"version {text!r} is not dotted decimal digits",
    )
    assert isinstance(text, str)
    return tuple(int(part) for part in text.split("."))


def _o1_cert_hash(state: _State) -> ObligationResult:
    declared = _member(state.document, "cert_hash", "document")
    recomputed = canon.hash_ref("cert", _dumps(state.body).encode("utf-8"))
    _require(
        declared == recomputed,
        "E-HASH-CERT",
        f"cert_hash is {declared!r}; the body digests to {recomputed!r}",
    )
    return ObligationResult("O1 cert_hash", True, "the digest covers the whole body")


def _o2_schema(state: _State) -> ObligationResult:
    schema = _member(state.body, "schema", "body")
    _require(
        _member(schema, "v", "schema") == SCHEMA_V,
        "E-SCHEMA-DOWNGRADE",
        f"schema.v is not {SCHEMA_V}",
    )
    min_checker = _member(schema, "min_checker", "schema")
    _require(
        _version(CHECKER_VERSION) >= _version(min_checker),
        "E-SCHEMA-DOWNGRADE",
        f"checker {CHECKER_VERSION} is older than min_checker {min_checker}",
    )
    _require(
        _member(schema, "profile", "schema") == "eclipse-cert",
        "E-SCHEMA-UNKNOWN",
        "schema.profile is not eclipse-cert",
    )
    _require(
        _member(schema, "hash_algorithm", "schema") == canon.HASH_ALGORITHM,
        "E-HASH-ALGO",
        f"the certificate does not declare {canon.HASH_ALGORITHM}",
    )
    _require(
        _member(schema, "hash_substitution_note", "schema") == canon.HASH_SUBSTITUTION_NOTE,
        "E-HASH-ALGO",
        "the certificate does not carry the declared digest substitution note",
    )
    unknown = sorted(k for k in state.body if k not in BODY_MEMBERS)
    _require(not unknown, "E-SCHEMA-UNKNOWN", f"body carries unknown members {unknown}")
    missing = [m for m in _REQUIRED_BODY_MEMBERS if m not in state.body]
    _require(not missing, "E-SCHEMA-MISSING", f"body omits {missing}")
    premium = "premium" in state.body
    reason = "premium_suppressed_reason" in state.body
    _require(
        premium != reason,
        "E-SCHEMA-MISSING" if not (premium or reason) else "E-SCHEMA-UNKNOWN",
        "exactly one of premium and premium_suppressed_reason is present",
    )
    return ObligationResult("O2 schema", True, "member set and version are as declared")


def _o3_scope(state: _State) -> ObligationResult:
    scope = _member(state.body, "scope", "body")
    inputs = _member(state.body, "inputs", "body")
    expected = {"attacker", "bundle", "controls", "er", "goal", "liveness", "rules"}
    _require(set(scope) == expected, "VRD-005", f"scope members are {sorted(scope)}")
    _require(
        scope["attacker"] == "non-adaptive",
        "VRD-005",
        f"scope.attacker is {scope['attacker']!r}, not non-adaptive",
    )
    for scope_name, input_name in SCOPE_TO_INPUT:
        value = scope[scope_name]
        _require(bool(value), "VRD-005", f"scope.{scope_name} is empty")
        try:
            canon.parse_hash_ref(value)
        except Exception:
            raise Rejected("VRD-005", f"scope.{scope_name} is not a hash reference") from None
        _require(
            value == _member(inputs, input_name, "inputs"),
            "E-SCOPE-BIND",
            f"scope.{scope_name} disagrees with inputs.{input_name}",
        )
    return ObligationResult("O3 scope", True, "seven members, total, and bound to inputs")


def _o4_inputs(state: _State) -> ObligationResult:
    inputs = _member(state.body, "inputs", "body")
    _require(
        _member(inputs, "grounding_mode", "inputs") == "replayed",
        "E-SCHEMA-UNKNOWN",
        "grounding_mode is not replayed",
    )
    _require(
        _member(inputs, "bundle_provenance", "inputs") == "synthetic_generator_no_range",
        "E-SCHEMA-UNKNOWN",
        "bundle_provenance does not say the telemetry is generator output",
    )
    _require(
        _member(inputs, "implementation", "inputs") == "python-reference",
        "E-SCHEMA-UNKNOWN",
        "implementation is not python-reference",
    )
    _mask_text(_member(inputs, "seed", "inputs"), "inputs.seed")
    checked = 0
    for name, domain, option, coverage in INPUT_COVERAGE:
        declared = _member(inputs, name, "inputs")
        path = state.inputs.path_for(option)
        if path is None:
            raise Usage(
                f"--{option.replace('_', '-')} was not supplied; {name} covers {coverage} "
                "and cannot be recomputed without it"
            )
        recomputed = canon.hash_ref(domain, _read_octets(path))
        if declared != recomputed:
            if name in ADVISORY_INPUTS:
                state.notes.append(
                    f"{name} differs from {path}; it is forensic only and is never "
                    "enforced, so the check continues"
                )
                continue
            raise Rejected(
                f"E-INPUT-{name.removesuffix('_hash').upper()}",
                f"{name} is {declared!r}; {path} digests to {recomputed!r}",
            )
        checked += 1
    instances = _member(state.body, "instances", "body")
    recomputed = canon.hash_ref(
        INSTANCES_DOMAIN,
        canon.ordered_seq(_instance_canonical(inst) for inst in instances),
    )
    _require(
        _member(inputs, "instances_hash", "inputs") == recomputed,
        "E-HASH-CERT",
        "instances_hash does not cover the published instance set",
    )
    return ObligationResult(
        "O4 inputs", True, f"{checked + 1} digests recomputed from the pinned artifacts"
    )


def _o4b_profile(state: _State) -> ObligationResult:
    """Binding gates B1..B6, re-evaluated from the hashed inputs.

    B4, B5 and B6 compare the profile against run-side values the certificate does not
    carry, so they need the run manifest. Without it they cannot be decided, and an
    obligation that cannot be decided is a rejection.
    """
    inputs = _member(state.body, "inputs", "body")
    path = state.inputs.profile
    if path is None:
        raise Usage("--profile was not supplied; gates B1..B6 cannot be evaluated")
    profile = _parse_side_json(path, "profile")
    manifest_path = state.inputs.run_manifest
    if manifest_path is None:
        raise Rejected(
            "PROFILE_INVALID",
            "gates B4, B5 and B6 compare the profile against run-side values that the "
            "certificate does not carry; supply --run-manifest or the obligation is undecided",
        )
    manifest = _parse_side_json(manifest_path, "run manifest")

    _require(
        _member(profile, "reference_bundle_hash", "profile")
        != _member(inputs, "bundle_hash", "inputs"),
        "PROFILE_SELF_CALIBRATED",
        "B1: the profile was calibrated on the bundle under analysis",
    )
    _require(
        _member(profile, "degradation_spec_hash", "profile")
        == _member(manifest, "identity_spec_hash", "run manifest"),
        "PROFILE_FROM_DEGRADED_RUN",
        "B2: the profile was calibrated under a non-identity degradation spec",
    )
    band = _member(profile, "calibration_seed_band", "profile")
    _require(
        isinstance(band, list) and len(band) == 2,
        "PROFILE_INVALID",
        "B3: calibration_seed_band is not a pair",
    )
    seed = _mask_text(_member(inputs, "seed", "inputs"), "inputs.seed")
    _require(
        not band[0] <= seed <= band[1],
        "PROFILE_SEED_OVERLAP",
        f"B3: the run seed lies inside the calibration band {band}",
    )
    _require(
        _member(profile, "generator_config_hash", "profile")
        == _member(manifest, "generator_config_hash", "run manifest"),
        "PROFILE_CONFIG_MISMATCH",
        "B4: the profile was calibrated under a different generator configuration",
    )
    _require(
        _member(profile, "scenario_family", "profile")
        == _member(manifest, "scenario_family", "run manifest"),
        "PROFILE_FAMILY_MISMATCH",
        "B5: the profile belongs to a different scenario family",
    )
    _require(
        _member(profile, "excluded_intervals_hash", "profile")
        == _member(manifest, "excluded_intervals_hash", "run manifest"),
        "PROFILE_INTERVALS_MISMATCH",
        "B6: the profile excludes different intervals",
    )
    return ObligationResult("O4b profile", True, "gates B1 to B6 hold against the pinned inputs")


def _o5_atoms(state: _State) -> ObligationResult:
    atoms = _member(state.body, "atoms", "body")
    assign = _member(atoms, "assign", "atoms")
    declared_n = _member(atoms, "n", "atoms")
    _require(
        declared_n == len(assign),
        "E-LIMIT-COUNT",
        f"atoms.n is {declared_n} but the table holds {len(assign)} rows",
    )
    _require(len(assign) <= 64, "E-LIMIT-COUNT", "the atom table is wider than the 64-bit mask")
    bits: list[int] = []
    rows: list[tuple[str, int, int]] = []
    for row in assign:
        _require(
            isinstance(row, list) and len(row) == 3,
            "E-LITERAL-TABLE",
            "an atom row is not [control_id, level, bit]",
        )
        control_id, level, bit = row
        _require(
            isinstance(control_id, str) and control_id.startswith("ctl:"),
            "E-LITERAL-TABLE",
            f"atom row names {control_id!r}, which is not a control identifier",
        )
        _require(
            isinstance(level, int) and not isinstance(level, bool) and level >= 1,
            "E-LITERAL-TABLE",
            "an atom level is not an integer at or above one",
        )
        _require(
            isinstance(bit, int) and not isinstance(bit, bool) and 0 <= bit < 64,
            "E-LITERAL-TABLE",
            "an atom bit is outside the mask width",
        )
        bits.append(bit)
        rows.append((control_id, level, bit))
    _ascending(bits, where="atoms.assign by bit")

    lock_path = state.inputs.catalog_bits
    if lock_path is None:
        raise Usage("--catalog-bits was not supplied; the atom table cannot be re-derived")
    lock = _parse_toml(lock_path, "catalog-bits.lock")
    live: set[tuple[str, int, int]] = set()
    seen_pos: set[int] = set()
    for entry in lock.get("bit", []):
        pos = entry.get("pos")
        _require(
            isinstance(pos, int) and 0 <= pos < 64,
            "E-LITERAL-TABLE",
            f"catalog-bits.lock holds pos {pos!r}, which is outside the mask width",
        )
        _require(pos not in seen_pos, "E-LITERAL-TABLE", f"catalog-bits.lock reuses pos {pos}")
        seen_pos.add(pos)
        if entry.get("state") == "live":
            live.add((f"ctl:{entry['control_id']}", int(entry["level"]), pos))
    _require(
        live == set(rows),
        "E-LITERAL-TABLE",
        "the atom table disagrees with the live rows of catalog-bits.lock",
    )

    ordered = sorted(rows, key=lambda r: (r[0].removeprefix("ctl:").encode("utf-8"), r[1]))
    for rank, (control_id, level, bit) in enumerate(ordered):
        state.atom_by_rank[rank] = (control_id, level, bit)
        state.atom_bits[(control_id, level)] = bit
        state.control_levels.setdefault(control_id, []).append(level)
    for control_id in state.control_levels:
        state.control_levels[control_id].sort()
    return ObligationResult(
        "O5 atoms", True, f"{len(rows)} atoms match the lock and recompute their ranks"
    )


def _o6_cut(state: _State) -> ObligationResult:
    cut = _member(state.body, "cut", "body")
    ranks: list[int] = []
    raised: dict[str, int] = {}
    mask = 0
    for entry in cut:
        rank = _member(entry, "rank", "cut")
        control_id = _member(entry, "control_id", "cut")
        level = _member(entry, "level", "cut")
        bit = _member(entry, "bit", "cut")
        expected = state.atom_by_rank.get(rank)
        _require(
            expected is not None and expected == (control_id, level, bit),
            "E-LITERAL-TABLE",
            f"cut rank {rank} does not match the atom table row",
        )
        ranks.append(rank)
        raised[control_id] = max(raised.get(control_id, 0), level)
        mask |= 1 << bit
    _ascending(ranks, where="cut by rank")
    for control_id, top in raised.items():
        held = sorted(
            level for (c, level) in state.atom_bits if c == control_id and 1 <= level <= top
        )
        present = sorted(
            entry["level"] for entry in cut if entry["control_id"] == control_id
        )
        _require(
            present == held,
            "E-CUT-CLOSURE",
            f"{control_id} is raised to {top} but the cut is not upward-closed from 1",
        )
    state.cut_mask = mask
    state.cut_controls = raised
    return ObligationResult(
        "O6 cut", True, f"{len(raised)} raised controls, upward-closed, ranks re-derived"
    )


def _o6b_cardinality_and_levels(state: _State) -> ObligationResult:
    psi = _member(state.body, "psi", "body")
    corridors = _member(psi, "corridors", "psi")
    state.corridor_masks = [_mask_text(c["mask"], "psi.corridors.mask") for c in corridors]
    for control_id, top in state.cut_controls.items():
        if top <= 1:
            continue
        lowered = state.cut_mask & ~(1 << state.atom_bits[(control_id, top)])
        if all(m & lowered for m in state.corridor_masks):
            raise Rejected(
                "E-CUT-LEVEL",
                f"{control_id} at level {top} is not level-minimal: lowering it one step "
                "still satisfies every published clause",
            )
    return ObligationResult(
        "O6b level-minimality",
        True,
        "every raised level above one leaves a clause unsatisfied when lowered",
        cost=len(state.cut_controls) * max(1, len(state.corridor_masks)),
    )


def _o7_invariant(state: _State) -> ObligationResult:
    goals = _member(state.body, "goals", "body")
    every_severed = all(not g["derivable"] for g in goals)
    if "invariant" not in state.body:
        _require(
            not every_severed,
            "E-SCHEMA-MISSING",
            "every goal is severed but the closure invariant is absent",
        )
        return ObligationResult(
            "O7 invariant",
            True,
            "no invariant is published because a goal is derivable; O8 has nothing to close "
            "over and the witness obligation carries the load instead",
        )
    _require(
        every_severed,
        "E-SCHEMA-UNKNOWN",
        "an invariant is published while a goal is derivable",
    )
    universe = _member(state.body["invariant"], "u", "invariant")
    _ascending(universe, where="invariant.u")
    for fact in universe:
        _require(_fact_id_ok(fact), "E-INV-AXIOM", f"invariant.u holds {fact!r}")
    state.invariant = set(universe)
    instances = _member(state.body, "instances", "body")
    for axiom in _axioms_of(instances):
        _require(
            axiom in state.invariant, "E-INV-AXIOM", f"axiom {axiom} is absent from U"
        )
    return ObligationResult(
        "O7 invariant", True, f"U holds {len(universe)} facts and every axiom is present"
    )


def _o8_closure(state: _State) -> ObligationResult:
    if "invariant" not in state.body:
        return ObligationResult(
            "O8 closure", True, "no invariant was published, so no closure is claimed"
        )
    instances = _member(state.body, "instances", "body")
    touched = 0
    for inst in instances:
        masks = [_mask_text(m, "blockers") for m in inst["blockers"]]
        for term in masks:
            _require(
                term.bit_count() == 1,
                "E-VS-BLOCK-CONJ",
                f"{inst['instance_id']} carries a conjunctive blocker term",
            )
        unsatisfied = 0
        for fact in inst["body"]:
            touched += 1
            if fact not in state.invariant:
                unsatisfied += 1
        if unsatisfied:
            continue
        if _blocked(masks, state.cut_mask):
            continue
        _require(
            inst["head"] in state.invariant,
            "E-CLOSURE",
            f"{inst['instance_id']} fires under the cut but its head is absent from U",
        )
    return ObligationResult(
        "O8 closure", True, "U is closed under every published instance", cost=touched
    )


def _o9_goals(state: _State) -> ObligationResult:
    goals = _member(state.body, "goals", "body")
    _ascending([g["goal_key"] for g in goals], where="goals")
    if "invariant" not in state.body:
        return ObligationResult(
            "O9 goals", True, "no invariant was published, so membership is not claimed"
        )
    for goal in goals:
        if goal["derivable"]:
            continue
        _require(
            goal["goal_key"] not in state.invariant,
            "E-GOAL-MEMBER",
            f"{goal['goal_key']} is declared severed but is present in U",
        )
    return ObligationResult("O9 goals", True, "every severed goal is absent from U")


def _o10_licenses(state: _State) -> ObligationResult:
    """Every cited licence is implied by the pinned liveness document.

    A licence is a permission for a step nobody could have seen, so what is checked is that
    the pinned document says nobody could have seen it: the cited span is covered by
    non-LIVE elementary intervals on that source, and every producing source of the
    instance's rule is non-LIVE over the same span.
    """
    liveness_path = state.inputs.liveness
    rules_path = state.inputs.rules
    if liveness_path is None:
        raise Usage("--liveness was not supplied; licences cannot be checked for implication")
    if rules_path is None:
        raise Usage("--rules was not supplied; a rule's producing sources are unknown")
    liveness = _parse_side_json(liveness_path, "liveness")
    rules = _parse_toml(rules_path, "rules.toml")
    producing: dict[str, list[str]] = {}
    for rule in rules.get("rule", []):
        producing[f"rl:{rule['id']}"] = [_src(s) for s in rule.get("producing_sources", [])]

    intervals: dict[str, list[tuple[int, int, str, str]]] = {}
    for source in liveness.get("sources", []):
        rows: list[tuple[int, int, str, str]] = []
        for window in source.get("intervals", []):
            rows.append(
                (
                    _int_text(window["t0_ns"], "liveness.t0_ns"),
                    _int_text(window["t1_ns"], "liveness.t1_ns"),
                    window["verdict"],
                    window["reason"],
                )
            )
        rows.sort(key=lambda r: (r[0], r[1]))
        intervals[_src(source["source_id"])] = rows

    licences = {lic["license_id"]: lic for lic in _member(state.body, "licenses", "body")}
    _ascending(
        [
            (
                lic["source_id"],
                _int_text(lic["t0_ns"], "licenses.t0_ns"),
                _int_text(lic["t1_ns"], "licenses.t1_ns"),
            )
            for lic in state.body["licenses"]
        ],
        where="licenses",
    )
    for lic in state.body["licenses"]:
        recomputed = "lic:" + canon.digest_hex("lic", _licence_preimage(lic), 32)
        _require(
            lic["license_id"] == recomputed,
            "E-LICENSE-UNIMPLIED",
            f"{lic['license_id']} does not recompute from its own fields",
        )
        _require(
            lic["basis"] in ("BLIND", "SUPPRESSED"),
            "E-LICENSE-UNIMPLIED",
            f"{lic['license_id']} carries basis {lic['basis']!r}",
        )
        if lic["basis"] == "BLIND":
            _require(
                "witness" not in lic,
                "E-LICENSE-UNIMPLIED",
                f"{lic['license_id']} is BLIND and carries a witness; a BLIND licence "
                "records that nobody could have seen, and is never an observation",
            )
        else:
            _require(
                bool(lic.get("witness")),
                "E-LICENSE-UNIMPLIED",
                f"{lic['license_id']} is SUPPRESSED and carries no bracketing witness",
            )

    checked = 0
    silent = _member(state.body, "silent", "body")
    by_instance = {i["instance_id"]: i for i in state.body["instances"]}
    for ref in silent:
        inst = by_instance.get(ref["instance_id"])
        _require(
            inst is not None,
            "E-LICENSE-UNIMPLIED",
            f"silent cites {ref['instance_id']}, which is not published",
        )
        _require(
            inst["observed"] == "LICENSED",
            "E-LICENSE-UNIMPLIED",
            f"{inst['instance_id']} is listed silent but is marked OBSERVED",
        )
        _require(
            tuple(ref["license_ids"]) == tuple(inst["license_ids"]),
            "E-LICENSE-UNIMPLIED",
            f"silent cites licences {inst['instance_id']} does not",
        )
        sources = producing.get(inst["rule_id"])
        _require(
            sources is not None,
            "E-LICENSE-UNIMPLIED",
            f"{inst['rule_id']} is not in the pinned rule table, so its producing sources "
            "are unknown and the obligation cannot be decided",
        )
        for license_id in ref["license_ids"]:
            lic = licences.get(license_id)
            _require(
                lic is not None,
                "E-LICENSE-UNIMPLIED",
                f"{license_id} is cited but not published",
            )
            t0 = _int_text(lic["t0_ns"], "licenses.t0_ns")
            t1 = _int_text(lic["t1_ns"], "licenses.t1_ns")
            _require(
                t0 < t1,
                "E-LICENSE-WINDOW",
                f"{license_id} spans an empty or reversed interval",
            )
            for source_id in sources:
                rows = intervals.get(source_id)
                _require(
                    rows is not None,
                    "E-LICENSE-UNIMPLIED",
                    f"{source_id} is a producing source of {inst['rule_id']} but is absent "
                    "from the pinned liveness document",
                )
                _require(
                    _non_live_over(rows, t0, t1),
                    "E-LICENSE-WINDOW",
                    f"{source_id} is not non-LIVE across the whole of {license_id}",
                )
                checked += 1
            licence_source = _src(lic["source_id"])
            if licence_source in intervals:
                matched = [
                    row
                    for row in intervals[licence_source]
                    if row[0] < t1 and t0 < row[1] and row[2] == lic["basis"]
                    and row[3] == lic["reason"]
                ]
                _require(
                    bool(matched),
                    "E-LICENSE-UNIMPLIED",
                    f"{license_id} cites basis {lic['basis']} reason {lic['reason']} which "
                    "no elementary interval of that source carries",
                )
    return ObligationResult(
        "O10 licenses", True, "every cited licence is implied by the pinned liveness document",
        cost=checked,
    )


def _non_live_over(rows: list[tuple[int, int, str, str]], t0: int, t1: int) -> bool:
    """True when [t0, t1) is fully covered by intervals whose verdict is not LIVE."""
    cursor = t0
    for start, end, verdict, _reason in rows:
        if end <= cursor:
            continue
        if start > cursor:
            return False
        if verdict == "LIVE":
            return False
        cursor = end
        if cursor >= t1:
            return True
    return cursor >= t1


def _o11_ghost(state: _State) -> ObligationResult:
    instances = _member(state.body, "instances", "body")
    events: set[str] = set()
    ghosts: set[str] = set()
    for inst in instances:
        if inst["observed"] == "LICENSED":
            _require(
                not inst["evidence"],
                "E-GHOST-COUNT",
                f"{inst['instance_id']} is LICENSED and cites evidence",
            )
            _require(
                bool(inst["license_ids"]),
                "E-LICENSE-UNIMPLIED",
                f"{inst['instance_id']} is LICENSED and cites no licence",
            )
        else:
            _require(
                bool(inst["evidence"]) and not inst["license_ids"],
                "E-GHOST-COUNT",
                f"{inst['instance_id']} is OBSERVED but does not cite records alone",
            )
        for ref in inst["evidence"]:
            events.add(ref["event_id"])
        if inst["ghost"]:
            _require(
                inst["observed"] == "LICENSED",
                "E-GHOST-COUNT",
                f"{inst['instance_id']} is GHOST-headed but is not LICENSED",
            )
            ghosts.add(inst["head"])
    declared_events = _member(state.body, "observed_event_count", "body")
    declared_ghosts = _member(state.body, "ghost_count", "body")
    _require(
        declared_events == len(events),
        "E-GHOST-COUNT",
        f"observed_event_count is {declared_events}; the OBSERVED instances cite "
        f"{len(events)} distinct records",
    )
    _require(
        declared_ghosts == len(ghosts),
        "E-GHOST-COUNT",
        f"ghost_count is {declared_ghosts}; {len(ghosts)} facts are GHOST-headed",
    )
    return ObligationResult(
        "O11 ghost",
        True,
        f"{declared_events} observed records and {declared_ghosts} GHOST facts, counted "
        "separately and never summed",
    )


def _o12_witnesses(state: _State) -> ObligationResult:
    witnesses = _member(state.body, "witnesses", "body")
    _ascending([w["removed_control"] for w in witnesses], where="witnesses")
    if not witnesses:
        return ObligationResult("O12 witnesses", True, "no witness tree is published")
    bundle_path = state.inputs.bundle
    if bundle_path is None:
        raise Usage("--bundle was not supplied; witness leaves cannot be checked")
    bundle = _load_bundle(bundle_path)
    instances = _member(state.body, "instances", "body")
    by_id = {i["instance_id"]: i for i in instances}
    axioms = _axioms_of(instances)
    goals = [g["goal_key"] for g in _member(state.body, "goals", "body")]
    nodes = 0
    for entry in witnesses:
        control_id = entry["removed_control"]
        _require(
            control_id in state.cut_controls,
            "E-WITNESS-CUT",
            f"{control_id} is not raised in the published cut",
        )
        reduced = state.cut_mask
        for level in state.control_levels.get(control_id, []):
            reduced &= ~(1 << state.atom_bits[(control_id, level)])
        derived, steps = _reach(instances, axioms, reduced)
        _require(
            any(goal in derived for goal in goals),
            "E-WITNESS-CUT",
            f"removing {control_id} from the cut does not re-derive a goal",
        )
        nodes += steps
        tree = _member(entry, "nodes", "witnesses")
        _check_flat_tree(tree, control_id)
        # Iterative, not recursive: the file chooses how deep a derivation goes, and the
        # checker does not let untrusted input choose its stack depth.
        ancestors: dict[int, tuple[str, ...]] = {0: ()}
        for index, node in enumerate(tree):
            nodes += _check_node(tree, index, ancestors[index], by_id, bundle, set(axioms))
            path = (*ancestors[index], node["instance_id"])
            for child in node["children"]:
                ancestors[child] = path
    return ObligationResult(
        "O12 witnesses",
        True,
        f"{len(witnesses)} tree(s) are well founded, cite bundled records and re-derive a "
        "goal under the reduced cut",
        cost=nodes,
    )


def _check_flat_tree(tree: list[Any], control_id: str) -> None:
    """The structural rules of ADR-0015: one tree, in pre-order, that cannot loop.

    Every child index lies after its parent and inside the list, so no index sequence
    returns to a node already visited; every node but the root has exactly one parent, so
    the list is a single tree with nothing unreachable and nothing shared.
    """
    _require(
        isinstance(tree, list) and bool(tree),
        "E-WITNESS-CYCLE",
        f"the witness for {control_id} has no nodes",
    )
    parents = [0] * len(tree)
    for index, node in enumerate(tree):
        children = _member(node, "children", "witness node")
        for child in children:
            _require(
                isinstance(child, int) and not isinstance(child, bool),
                "E-WITNESS-CYCLE",
                f"witness node {index} for {control_id} names a child that is not an index",
            )
            _require(
                index < child < len(tree),
                "E-WITNESS-CYCLE",
                f"witness node {index} for {control_id} names child {child}, which does not "
                "come after it in the node list",
            )
            parents[child] += 1
    _require(
        parents[0] == 0,
        "E-WITNESS-CYCLE",
        f"the root of the witness for {control_id} is someone's child",
    )
    for index in range(1, len(tree)):
        _require(
            parents[index] == 1,
            "E-WITNESS-CYCLE",
            f"witness node {index} for {control_id} has {parents[index]} parents, not one",
        )


def _check_node(
    tree: list[dict[str, Any]],
    index: int,
    ancestors: tuple[str, ...],
    by_id: dict[str, dict[str, Any]],
    bundle: dict[str, dict[str, Any]],
    axioms: set[str],
) -> int:
    node = tree[index]
    instance_id = _member(node, "instance_id", "witness node")
    _require(
        instance_id not in ancestors,
        "E-WITNESS-CYCLE",
        f"{instance_id} supports itself; the tree is not well founded",
    )
    inst = by_id.get(instance_id)
    _require(
        inst is not None,
        "E-WITNESS-EVENT",
        f"{instance_id} is cited by a witness but is not published",
    )
    _require(
        inst["head"] == _member(node, "head", "witness node"),
        "E-WITNESS-EVENT",
        f"{instance_id} does not head {node['head']}",
    )
    kind = _member(node, "kind", "witness node")
    evidence = _member(node, "evidence", "witness node")
    if kind == "GHOST":
        _require(not evidence, "E-GHOST-COUNT", f"{instance_id} is GHOST and cites evidence")
        _require(
            inst["ghost"] is True,
            "E-GHOST-COUNT",
            f"{instance_id} is GHOST in the witness but its instance is not",
        )
        _require(
            bool(inst["license_ids"]),
            "E-LICENSE-UNIMPLIED",
            f"{instance_id} is GHOST and cites no licence",
        )
    elif kind == "LICENSED":
        _require(
            not evidence, "E-WITNESS-EVENT", f"{instance_id} is LICENSED and cites evidence"
        )
        _require(
            inst["ghost"] is False and inst["observed"] == "LICENSED",
            "E-WITNESS-EVENT",
            f"{instance_id} is LICENSED in the witness but its instance is not a licensed, "
            "non-GHOST silent instance",
        )
        _require(
            bool(inst["license_ids"]),
            "E-LICENSE-UNIMPLIED",
            f"{instance_id} is LICENSED and cites no licence",
        )
    elif kind == "OBSERVED":
        _require(bool(evidence), "E-WITNESS-EVENT", f"{instance_id} is OBSERVED and cites none")
        _require(
            inst["observed"] == "OBSERVED",
            "E-WITNESS-EVENT",
            f"{instance_id} is OBSERVED in the witness but its instance rests on a licence",
        )
        _require(
            sorted(evidence) == sorted(r["event_id"] for r in inst["evidence"]),
            "E-WITNESS-EVENT",
            f"{instance_id} cites evidence the published instance does not",
        )
        for event_id in evidence:
            record = bundle.get(event_id)
            _require(
                record is not None,
                "E-WITNESS-EVENT",
                f"{event_id} is cited by a witness but is not in the pinned bundle",
            )
            recomputed = "ev:" + canon.digest_hex("ev", _event_preimage(record), 16)
            _require(
                recomputed == event_id,
                "E-WITNESS-EVENT",
                f"{event_id} does not recompute from the bundled record",
            )
    else:
        raise Rejected("E-WITNESS-EVENT", f"witness node kind {kind!r} is not declared")
    # Children are indices already checked by _check_flat_tree to lie inside the list.
    covered = {tree[child]["head"] for child in node["children"]}
    for fact in inst["body"]:
        _require(
            fact in covered or fact in axioms,
            "E-WITNESS-EVENT",
            f"{instance_id} needs {fact}, which is neither an axiom nor a child of the node",
        )
    return 1


def _o13_psi_hit(state: _State) -> ObligationResult:
    psi = _member(state.body, "psi", "body")
    _require(
        _member(psi, "program", "psi") == "PMax",
        "E-PSI-HIT",
        "the published corridor database does not name the upper program",
    )
    corridors = _member(psi, "corridors", "psi")
    _ascending([c["corridor_id"] for c in corridors], where="psi.corridors")
    for corridor in corridors:
        ranks = _member(corridor, "atom_ranks", "psi.corridors")
        _ascending(ranks, where="psi.corridors.atom_ranks")
        recomputed = "cor:" + canon.digest_hex("cor", canon.leb128_seq(ranks), 32)
        _require(
            corridor["corridor_id"] == recomputed,
            "E-PSI-HIT",
            f"{corridor['corridor_id']} does not recompute from its atom ranks",
        )
        expected = 0
        for rank in ranks:
            row = state.atom_by_rank.get(rank)
            _require(row is not None, "E-PSI-HIT", f"corridor cites unknown rank {rank}")
            expected |= 1 << row[2]
        declared = _mask_text(corridor["mask"], "psi.corridors.mask")
        _require(
            declared == expected,
            "E-PSI-HIT",
            f"{corridor['corridor_id']} carries a mask its atom ranks do not produce",
        )
        _require(
            bool(declared & state.cut_mask),
            "E-PSI-HIT",
            f"{corridor['corridor_id']} is not satisfied by the published cut",
        )
    return ObligationResult(
        "O13 psi-hit",
        True,
        f"{len(corridors)} corridor(s) recompute and are satisfied by the cut",
        cost=len(corridors),
    )


def _o13b_premium_sets(state: _State) -> ObligationResult:
    """The premium's set arithmetic, re-derived rather than trusted.

    `blindness_premium` is defined as `NEC(Psi_max) \ OCC(Psi_min)`, and until this
    obligation existed the emitter was the only thing that computed it: O14 checks the
    preconditions under which a premium may be PUBLISHED, not the sets themselves. A defect
    in the emitter's set difference would therefore have reached a certificate this checker
    accepts, which is the failure the two-implementation design exists to catch
    (`docs/kernel/spec-drift.md`).

    The premium is the number this project is for, so it is the worst member to leave
    un-rederived. Everything needed is in the certificate: all three sets are published.
    """
    body = state.body
    if "premium" not in body:
        reason = _member(body, "premium_suppressed_reason", "body")
        return ObligationResult(
            "O13b premium sets",
            True,
            f"the premium is absent, suppressed as {reason!r}; there are no sets to check",
        )
    premium = _member(body, "premium", "body")
    nec_max = _member(premium, "nec_max", "premium")
    occ_min = _member(premium, "occ_min", "premium")
    published = _member(premium, "blindness_premium", "premium")
    _ascending(nec_max, where="premium.nec_max")
    _ascending(occ_min, where="premium.occ_min")
    _ascending(published, where="premium.blindness_premium")
    expected = [control for control in nec_max if control not in set(occ_min)]
    _require(
        published == expected,
        "E-PREMIUM-SETS",
        f"blindness_premium is {published}; NEC(Psi_max) \ OCC(Psi_min) is {expected}",
    )
    for entry in _member(premium, "per_control", "premium"):
        _require(
            entry["control_id"] in published,
            "E-PREMIUM-SETS",
            f"{entry['control_id']} carries a premium entry but is not in the premium",
        )
    return ObligationResult(
        "O13b premium sets",
        True,
        f"the premium re-derives: {len(nec_max)} necessary, {len(occ_min)} occurring, "
        f"{len(published)} in the difference",
        cost=len(nec_max) + len(occ_min),
    )


def _o14_flags(state: _State) -> ObligationResult:
    verdict = _member(state.body, "verdict", "body")
    flags = _member(verdict, "flags", "verdict")
    mask = 0
    previous = -1
    for name in flags:
        bit = _BIT_OF.get(name)
        _require(bit is not None, "VRD-008", f"{name!r} is not a declared flag")
        _require(bit > previous, "VRD-008", f"{name!r} is out of bit order or duplicated")
        previous = bit
        mask |= 1 << bit
    _require(not mask & RESERVED_MASK, "VRD-009", "a reserved flag bit is set")
    state.flags = tuple(flags)
    state.flag_mask = mask

    safety = _member(verdict, "safety", "verdict")
    minimality = _member(verdict, "minimality", "verdict")
    realizability = _member(verdict, "realizability", "verdict")
    _require(safety in _SAFETY, "VRD-008", f"safety {safety!r} is not declared")
    _require(minimality in _MINIMALITY, "VRD-008", f"minimality {minimality!r} is not declared")
    _require(
        realizability in _REALIZABILITY, "VRD-008", f"realizability {realizability!r} is not declared"
    )
    _require(
        "witness_class" in verdict,
        "E-SCHEMA-MISSING",
        "witness_class is present on every verdict and null on non-UNSAFE",
    )
    witness_class = verdict["witness_class"]
    if safety == "ROBUST":
        _require(
            not mask & SOUNDNESS_MASK,
            "VRD-001",
            "the universal claim is published with a soundness flag set",
        )
    if safety == "UNSAFE":
        _require(witness_class in _WITNESS_CLASS, "VRD-002", "UNSAFE carries no witness_class")
        _require(
            bool(_member(state.body, "witnesses", "body")),
            "VRD-002",
            "UNSAFE is published with no witness tree",
        )
        if "er_ambiguous" in flags:
            _require(
                witness_class == "CONTESTED",
                "VRD-007",
                "er_ambiguous is set but the witness class is not CONTESTED",
            )
        if witness_class == "OBSERVED":
            _require(
                not _tree_has_silent(state.body["witnesses"]),
                "VRD-003",
                "an OBSERVED witness class is published over a tree containing a GHOST or "
                "LICENSED node",
            )
        if witness_class == "LICENSED":
            _require(
                _tree_has_silent(state.body["witnesses"]),
                "VRD-003",
                "a LICENSED witness class is published over trees with no silent node",
            )
    else:
        _require(
            witness_class is None,
            "VRD-006",
            "witness_class is present on a non-UNSAFE verdict",
        )
    if minimality.startswith("EXACT_"):
        capped = [n for n in _MINIMALITY_CAP_FLAGS if n in flags]
        _require(not capped, "VRD-004", f"exact minimality is claimed while {capped} are set")
    derived = _member(verdict, "derived_suppressed", "verdict")
    _ascending(derived, where="verdict.derived_suppressed")
    missing = [n for n in _DERIVED_SUPPRESSED_ALWAYS if n not in derived]
    _require(not missing, "VRD-014", f"derived_suppressed omits {missing}")
    if "premium" in state.body:
        blocked = [n for n in ("grounding_capped", "corridor_cap") if n in flags]
        _require(
            not blocked,
            "E-FLAG-DERIVED",
            f"the premium is published while {blocked} are set",
        )
        _require(
            _member(state.body["psi"], "complete", "psi"),
            "E-FLAG-DERIVED",
            "the premium is published over an incomplete corridor database",
        )
        _require(
            not _member(state.body["budgets"], "budget_exhausted", "budgets"),
            "E-FLAG-DERIVED",
            "the premium is published while a deterministic budget was exhausted",
        )
    return ObligationResult(
        "O14 flags", True, f"flag algebra holds over {canon.mask_hex(mask)}"
    )


def _tree_has_silent(witnesses: list[dict[str, Any]]) -> bool:
    return any(node["kind"] in _SILENT_KINDS for w in witnesses for node in w["nodes"])


def _o14b_temporal_dispute(state: _State) -> ObligationResult:
    """A ROBUST verdict may not be published over a tamper-suspected source.

    Part II 65.6.2, re-derived here from the PINNED liveness document rather than trusted
    from the certificate: the emitter's own decision flow refuses the verdict, and this is
    the check that the file in front of the reader obeys the same rule.

    The rule is read in the strict direction the emitter uses - any suspected source blocks
    ROBUST - so a certificate that claims ROBUST while its liveness document suspects a
    source is rejected even when that source's licence reaches no corridor. This obligation
    also checks the direction that matters more: a disputed licence must still be THERE.
    Voiding licences would shrink P_max and move verdicts toward ROBUST, so a document that
    disputes an event while publishing no licence over it is the shape of that attack.
    """
    verdict = _member(state.body, "verdict", "body")
    safety = _member(verdict, "safety", "verdict")
    liveness_path = state.inputs.liveness
    if liveness_path is None:
        raise Usage("--liveness was not supplied; the temporal dispute cannot be checked")
    liveness = _parse_side_json(liveness_path, "liveness")
    suspected = sorted(
        str(source.get("source_id"))
        for source in liveness.get("sources", [])
        if source.get("tamper_suspected") is True
    )
    sensitive = bool(liveness.get("flags", {}).get("verdict_tamper_sensitive"))
    disputed = liveness.get("disputed_events", [])
    if safety == "ROBUST":
        _require(
            not suspected,
            "VRD-001",
            f"ROBUST is published while {suspected} are tamper-suspected",
        )
        _require(
            not sensitive,
            "VRD-001",
            "ROBUST is published while the verdict is marked tamper-sensitive",
        )
    for event in disputed:
        _require(
            str(event.get("source_id")) in suspected,
            "VRD-001",
            f"{event.get('event_id')} is disputed but its source is not suspected",
        )
    return ObligationResult(
        "O14b temporal dispute",
        True,
        f"{len(disputed)} disputed timestamp(s), {len(suspected)} suspected source(s); "
        "no licence is voided and ROBUST is consistent with them",
        cost=len(disputed),
    )


def _o15_minimality(state: _State) -> ObligationResult:
    """NOT LINEAR. This obligation searches the control lattice and is fenced accordingly."""
    verdict = _member(state.body, "verdict", "body")
    minimality = verdict["minimality"]
    if minimality in ("SUBSET", "UNVERIFIED"):
        clause = (
            "no control can be removed from this cut; smaller cuts were not ruled out"
            if minimality == "SUBSET"
            else "no minimality probe ran, so nothing is claimed about the size of this cut"
        )
        return ObligationResult(
            "O15 minimality",
            True,
            f"nothing is claimed and nothing is checked: {clause}",
        )
    controls = sorted(state.control_levels)
    target = len(state.cut_controls)
    if target == 0:
        return ObligationResult(
            "O15 minimality", True, "the cut is empty, so nothing smaller exists"
        )
    candidates = comb(len(controls), target - 1)
    _require(
        candidates <= EXHAUSTIVE_CUT_CAP,
        "E-MIN-UNEARNED",
        f"{candidates} cuts of one control fewer exceeds the {EXHAUSTIVE_CUT_CAP} cap",
    )
    if minimality == "EXACT_EXHAUSTIVE":
        _require(
            _member(state.body["budgets"], "exhaustive_ran", "budgets"),
            "E-MIN-UNEARNED",
            "EXACT_EXHAUSTIVE is claimed but budgets.exhaustive_ran is false",
        )
        declared = state.body["budgets"]["exhaustive_cuts_tested"]
        _require(
            declared == candidates,
            "E-MIN-UNEARNED",
            f"budgets.exhaustive_cuts_tested is {declared}; {candidates} cuts of cardinality "
            f"{target - 1} exist over this catalog",
        )
    instances = _member(state.body, "instances", "body")
    axioms = _axioms_of(instances)
    goals = [g["goal_key"] for g in state.body["goals"]]
    tested = 0
    for subset in combinations(controls, target - 1):
        mask = 0
        for control_id in subset:
            for level in state.control_levels[control_id]:
                mask |= 1 << state.atom_bits[(control_id, level)]
        tested += 1
        if not all(m & mask for m in state.corridor_masks):
            continue
        if minimality == "EXACT_PSI_RELATIVE":
            raise Rejected(
                "E-MIN-SMALLER",
                f"the cut of controls {list(subset)} satisfies every published clause and "
                f"raises {target - 1} controls rather than {target}",
            )
        derived, _steps = _reach(instances, axioms, mask)
        if not any(goal in derived for goal in goals):
            raise Rejected(
                "E-MIN-SMALLER",
                f"the cut of controls {list(subset)} leaves every goal underivable with "
                f"{target - 1} controls raised",
            )
    clause = (
        "no smaller cut satisfies the enumerated corridor set"
        if minimality == "EXACT_PSI_RELATIVE"
        else "a fixpoint ran for every cut one control smaller over the admissible lattice"
    )
    return ObligationResult("O15 minimality", True, clause, cost=tested)


# ---------------------------------------------------------------------------
# Side files
# ---------------------------------------------------------------------------


def _side_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Duplicate keys reject; the key-FORM rule is not applied to a side artifact.

    WHY THE TWO HOOKS DIFFER, stated rather than quietly relaxed. The encoding law says
    object keys are ASCII `[a-z0-9_]+`, and the certificate body obeys it: every one of its
    members is a fixed name and `_pairs_hook` enforces the rule there. Two SIDE artifacts
    cannot obey it, because their own field tables declare MAP-KEYED members whose keys are
    values rather than names:

      * the source profile's `order_statistics`, whose keys are "exactly the levels in
        liveness.toml", i.e. `"95/100"`, which carries a solidus;
      * `liveness.json`'s `blind_volume_ns_by_reason`, whose keys are reason codes such as
        `B_GAP_EXCEEDS_THRESHOLD`, which are upper case.

    Rejecting those two artifacts would make every certificate that pins a real profile
    uncheckable, so the form rule is enforced where the law and the field table agree and
    is not enforced where they contradict each other. Duplicate keys are still a rejection
    everywhere, because a duplicate makes the parsed value depend on parser order.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise Rejected("E-CANON-DUPKEY", f"duplicate object key {key!r}")
        seen[key] = value
    return seen


def _parse_side_json(path: Path, label: str) -> dict[str, Any]:
    octets = _read_octets(path)
    try:
        value = json.loads(
            octets.decode("utf-8"),
            object_pairs_hook=_side_pairs_hook,
            parse_float=_floats_are_forbidden,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Rejected("E-CANON-FORM", f"{label} at {path} is not canonical JSON: {exc}") from None
    if not isinstance(value, dict):
        raise Rejected("E-CANON-FORM", f"{label} at {path} is not an object")
    return value


def _parse_toml(path: Path, label: str) -> dict[str, Any]:
    octets = _read_octets(path)
    if b"\r" in octets:
        raise Rejected("E-LEX-001", f"{label} at {path} holds a CR octet")
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise Rejected("E-SYN-000", f"{label} at {path} is not TOML: {exc}") from None


def _load_bundle(path: Path) -> dict[str, dict[str, Any]]:
    """Index bundle.jsonl by event id. Allocated from observed lines, never from a count."""
    records: dict[str, dict[str, Any]] = {}
    octets = _read_octets(path)
    if octets[:2] in _COMPRESSION_MAGICS:
        raise Rejected("E-LIMIT-COMPRESSED", "the bundle opens with a compression magic")
    for number, line in enumerate(octets.decode("utf-8").splitlines(), start=1):
        if not line:
            raise Rejected("E-CANON-FORM", f"bundle line {number} is empty")
        record = json.loads(
            line,
            object_pairs_hook=_pairs_hook,
            parse_float=_floats_are_forbidden,
            parse_constant=_reject_constant,
        )
        records[record["event_id"]] = record
    return records


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

OBLIGATIONS: Final[tuple[tuple[str, Any], ...]] = (
    ("O0", _o0_canonicity),
    ("O1", _o1_cert_hash),
    ("O2", _o2_schema),
    ("O3", _o3_scope),
    ("O4", _o4_inputs),
    ("O4b", _o4b_profile),
    ("O5", _o5_atoms),
    ("O6", _o6_cut),
    ("O6b", _o6b_cardinality_and_levels),
    ("O7", _o7_invariant),
    ("O8", _o8_closure),
    ("O9", _o9_goals),
    ("O10", _o10_licenses),
    ("O11", _o11_ghost),
    ("O12", _o12_witnesses),
    ("O13", _o13_psi_hit),
    ("O13b", _o13b_premium_sets),
    ("O14", _o14_flags),
    ("O14b", _o14b_temporal_dispute),
    ("O15", _o15_minimality),
)


def verify(cert_path: Path, inputs: CheckerInputs) -> Report:
    """Run every obligation in order, stopping at the first failure.

    Rejection is the default: an obligation that raises, that cannot decide, or that finds
    a deviation from canonical form ends the run. Nothing is repaired, sorted, defaulted or
    inferred on the way.
    """
    report = Report(exit_code=ACCEPT, code="")
    try:
        octets = _read_octets(cert_path)
        document = _parse_document(octets)
        body = document.get("body")
        if not isinstance(body, dict):
            raise Rejected("E-SCHEMA-MISSING", "the document carries no body object")
        state = _State(
            octets=octets, document=document, body=body, inputs=inputs, notes=report.notes
        )
        for _name, obligation in OBLIGATIONS:
            report.results.append(obligation(state))
    except Rejected as rejection:
        report.results.append(
            ObligationResult(
                _next_name(report), False, rejection.detail, code=rejection.code
            )
        )
        report.exit_code = REJECT
        report.code = rejection.code
    except Usage as usage:
        report.results.append(
            ObligationResult(_next_name(report), False, str(usage), code="E-USAGE")
        )
        report.exit_code = USAGE
        report.code = "E-USAGE"
    return report


def _next_name(report: Report) -> str:
    index = len(report.results)
    if index < len(OBLIGATIONS):
        return OBLIGATIONS[index][0]
    return "post"
