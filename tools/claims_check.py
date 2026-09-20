"""claims_check - the SPECTRA claims-registry checker (`make claims-check`).

This module implements the machine-enforced half of `CLAIMS.md`: the claims
registry grammar, the banned-phrase list, the anchoring and registration rules,
and the "no hand-written numeral in LIMITATIONS.md" rule.  It is the first real
code in this repository, so it also sets the house style: standard library only,
deterministic, read-only, and loud about what it does *not* check.

WHAT THIS TOOL WILL NEVER DO
    It never edits a file.  It reads the repository and reports.  It writes a
    machine-readable report only when `--report PATH` is passed explicitly; the
    default run touches nothing on disk.  A checker that repairs the thing it
    checks cannot be trusted to have checked it.

WHAT "SKIPPED" MEANS HERE
    Several gates declared in `ci/gates.toml` cannot run against this tree
    because their inputs do not exist yet (there is no `artifacts/` directory,
    no run manifest and no gate ledger).  Those gates are registered in
    `SKIPPED_CHECKS` and are printed on every run with the reason.  A check that
    silently does nothing is the exact defect this tool exists to catch, so the
    gap is reported rather than omitted.  Skips are not findings: they do not
    change the exit code, because a permanently-skipped gate would otherwise
    make a clean tree impossible to reach.

EXIT CONTRACT
    0   no findings
    1   one or more findings
    Warnings (currently only MISSING_ARTIFACT at tier T1, per section 71.3's
    state table) are reported but do not change the exit code at T1.  `--tier`
    selects the tier; at t2/t3 a warning is promoted to a finding.

DECISIONS THIS FILE TAKES (the contract left them open; each is marked DECIDED
at its implementation site)
    * The registry is `CLAIMS.md` at the repository root, falling back to
      `docs/claims.md` if only that exists.  `SKELETON_FILES` in the Makefile
      and `CLAIMS.md` itself both name the root path.
    * `docs/prompt/` is excluded from claim-candidate segmentation.  It is the
      specification, and `G-CLAIM-PLACEHOLDER` only makes sense if illustrative
      numbers are allowed to live there.  It is still scanned for banned
      patterns nowhere -- it is in the declared `exempt_paths`.
    * `CLAIMS.md` is parsed as the registry and scanned for banned patterns
      (it is exempt) but is NOT segmented for claim candidates: the registry
      quotes claim text and banned phrases in order to register and ban them.
    * The banned-phrase scan is NOT subject to the fenced-code-block skip.
      Section 71.7 item 11 names "move the sentence into a code fence" as a
      detected evasion, so a fence hides a sentence from candidate detection
      but never from the banned list.
    * BP-08 is case SENSITIVE.  It bans a bare verdict token, and applied
      case-insensitively it would ban the ordinary English word "robust" -
      including in `LIMITATIONS.md`, which is the honest prose the gate exists
      to protect.
    * `support.blake3` is validated for shape (64 hex) and never recomputed.
      BLAKE3 is not in the standard library and this tool has no dependencies;
      recomputation belongs to the support resolver, which is skipped.
    * The non-claim allowlist cap is declared in
      `docs/claims-nonclaims.toml` as a top-level `cap` integer.  It is not
      hard-coded here: the specification's 25 is tagged "(illustrative, not a
      target)" and `G-CLAIM-PLACEHOLDER` forbids that number escaping
      `docs/prompt/`.  An absent allowlist file is zero entries and passes.
    * A unit inside a `BEGIN/END GENERATED` block is never a claim candidate.
      Its numerals were rendered from an artifact, which is the state
      `G-LIMITS-NOHAND` exists to push numbers into.
    * An anchored unit is a candidate whether or not the numeral / verb /
      comparative test fires.  An anchor is an explicit declaration of
      claimhood, and without this a FRAMING record could be registered,
      anchored, and still reported ORPHAN.
    * `NOT_MEASURED` - this checker's own support state, meaning the resolver
      cannot decide - is a warning at T1 and a failure above it.  Raising it as
      a failure everywhere would turn the tree red on the first record ever
      registered, which is how a gate gets switched off.
    * A PATH surface (`README.md#anchor`) is matched on the FILE, not on the
      `#anchor` fragment.  Nothing in 71.1 or 71.2 says how to compute an
      anchor from a document and heading slugs are renderer-specific, so
      enforcing this tool's own derivation would report a clean registry as
      SURFACE_UNDECLARED whenever a heading was reworded.  Keyed surfaces
      (`ui:`, `cli:`, `demo:`, `paper:`, `release:`, `meta:`) stay exact.  See
      `surface_declared`.
    * A warned finding (71.3's per-PR `warn` states) is returned by
      `run_checks` carrying `severity="warn"`, not withheld from it.  It does
      not move the exit code; it is reported, because a state the contract
      says to report must not be invisible to the API consumers call.
    * `G-CLAIM-NUMSRC` runs for every QUANT record whose artifact exists and
      decodes, rather than declaring one blanket "not implementable".  The
      per-record gaps (absent artifact, undecodable artifact, a `note` whose
      rounding-rule syntax is unspecified) are skipped by name.
    * `G-CLAIM-NOERASE` reports erasure and reuse only.  A record present in
      the registry but matching no surface is ORPHAN under
      `G-CLAIM-REGISTERED`; reporting it again here made a never-erased id
      look erased.
    * `docs/banned.toml`'s state is always accounted for: absent or
      present-and-parseable is a skip naming the built-in table as the list
      that actually ran, and present-but-unparseable is a finding.
    * `G-CLAIM-PLACEHOLDER` scans the fifteen surface globs, not the whole
      tree.  The broader reading fails on `ci/gates.toml`'s 196 honest
      "illustrative, not a target" budget comments, and a gate that fights the
      labelling it mandates is a gate nobody keeps.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Sequence

__all__ = [
    "Finding",
    "Skip",
    "Report",
    "run_checks",
    "analyse",
    "CHECKS",
    "SKIPPED_CHECKS",
    "FINDING_KINDS",
    "BANNED_PATTERN_IDS",
    "normalise",
    "main",
]

SCHEMA = 1


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Finding:
    """One reported defect.

    `check` is the gate id it is reported under, `path` is repo-relative with
    forward slashes, `line` is 1-indexed or 0 when the finding is not
    line-located (a registry-level ORPHAN, for instance), and `message` is a
    single line with no newlines.  The field order is the sort order, so
    `sorted(findings)` is stable and diffable.
    """

    check: str
    path: str
    line: int
    message: str
    kind: str = ""
    """The finding kind, e.g. ``UNANCHORED``.

    Derived in `__post_init__` from the leading token of `message`, which every
    caller writes by construction.  It is a FIELD rather than a property so that
    `dataclasses.asdict` and the JSON report both carry it: a consumer routing
    on the kind must never have to pattern-match prose.  The message is for a
    human, the kind is for a machine, and the two are not the same channel.

    It is last in the field order deliberately, so the sort order stays
    `(check, path, line, message)` and reports remain diffable against earlier
    runs.

    Empty when the leading token is not a registered kind, which is a defect in
    whoever built the message rather than in the finding.
    """

    severity: str = "error"
    """``"error"`` or ``"warn"``.

    DECIDED: section 71.3's state table makes MISSING_ARTIFACT `warn` per-PR and
    FAIL nightly, so the tool needs a warning channel.  An earlier shape kept
    warnings out of `run_checks`' return value entirely, which meant the only
    way a consumer could see a warned defect was to call `analyse` and read a
    second list - and the default caller saw nothing at all.  A gate state the
    contract says to REPORT must not be invisible to the reported API.  The
    severity therefore rides on the finding, where a consumer can route on it,
    and the exit code is computed from the severity rather than from which list
    a finding landed in.
    """

    def __post_init__(self) -> None:
        head = self.message.split(" ", 1)[0]
        object.__setattr__(self, "kind", head if head in FINDING_KINDS else "")


@dataclass(frozen=True, order=True)
class Skip:
    """A check that is registered but cannot run, with the reason it cannot."""

    check: str
    reason: str


@dataclass
class Report:
    """Everything one run produced.  No wall-clock, no absolute paths."""

    schema: int = SCHEMA
    findings: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)
    surfaces: list[str] = field(default_factory=list)
    missing_surfaces: list[str] = field(default_factory=list)
    registry_path: str = ""
    unit_count: int = 0
    candidate_count: int = 0
    record_count: int = 0

    def to_json(self) -> dict[str, object]:
        """A deterministic, diffable dict; caller serialises with sort_keys."""
        return {
            "schema": self.schema,
            "registry": self.registry_path,
            "counts": {
                "surfaces": len(self.surfaces),
                "units": self.unit_count,
                "candidates": self.candidate_count,
                "records": self.record_count,
                "findings": len(self.findings),
                "warnings": len(self.warnings),
                "skipped": len(self.skipped),
            },
            "surfaces": list(self.surfaces),
            "missing_surfaces": list(self.missing_surfaces),
            "findings": [
                {
                    "check": f.check,
                    "kind": f.kind,
                    "severity": f.severity,
                    "path": f.path,
                    "line": f.line,
                    "message": f.message,
                }
                for f in self.findings
            ],
            "warnings": [
                {
                    "check": f.check,
                    "kind": f.kind,
                    "severity": f.severity,
                    "path": f.path,
                    "line": f.line,
                    "message": f.message,
                }
                for f in self.warnings
            ],
            "skipped": [{"check": s.check, "reason": s.reason} for s in self.skipped],
        }


# --------------------------------------------------------------------------
# The closed surface list and the exempt set (CLAIMS.md "Surfaces scanned")
# --------------------------------------------------------------------------

SURFACE_GLOBS: tuple[str, ...] = (
    ".github/PULL_REQUEST_TEMPLATE.md",
    "CHANGELOG.md",
    "CLAIMS.md",
    "LIMITATIONS.md",
    "README.md",
    "SECURITY.md",
    "cli/strings.toml",
    "demo/transcript.expected.txt",
    "docs/**/*.md",
    "docs/commit-message-template.txt",
    "docs/cv-bullets.md",
    "docs/release-notes/*.md",
    "docs/repo-metadata.toml",
    "frontend/src/strings/*.json",
    "paper/**/*.tex",
)

#: Paths exempt from the banned-phrase scan, exactly as CLAIMS.md declares them.
#: A trailing slash means "this directory and everything under it".
EXEMPT_PATHS: tuple[str, ...] = (
    "CLAIMS.md",
    "docs/NON-GOALS.md",
    "docs/banned.toml",
    "docs/claims-policy.md",
    "docs/descope-ladder.md",
    "docs/prompt/",
)

#: Paths excluded from claim-candidate segmentation.  See the module docstring.
NO_CANDIDATE_PATHS: tuple[str, ...] = (
    "CLAIMS.md",
    "docs/prompt/",
)

#: Directories never walked.  Build output and vendored dependencies are not
#: surfaces, and walking them would make the run slow and non-hermetic.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".opencode",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)

REGISTRY_CANDIDATE_PATHS: tuple[str, ...] = ("CLAIMS.md", "docs/claims.md")

LIMITATIONS_PATH = "LIMITATIONS.md"
README_PATH = "README.md"
FRAMING_PATH = "docs/framing.toml"
NONCLAIMS_PATH = "docs/claims-nonclaims.toml"
BANNED_TOML_PATH = "docs/banned.toml"
WAIVER_PATH = "WAIVER.md"
NEGATIVE_FIXTURE_DIR = "tests/claims/negative"

KINDS: tuple[str, ...] = ("CAPABILITY", "FRAMING", "NEGATIVE", "QUANT")
STATUSES: tuple[str, ...] = ("GREEN", "HELD_OUT", "RETIRED", "TUNED")

#: Surfaces on which a TUNED record may never appear (section 71.1.1 item 3).
HEADLINE_SURFACE_PATTERNS: tuple[str, ...] = (
    "README.md#*",
    "demo:*",
    "meta:*",
    "paper:abstract",
)

#: Strings a scope clause may not contain (section 71.1.2).
SCOPE_FORBIDDEN: tuple[str, ...] = ("always", "for any system", "in general", "in practice")

SCOPE_MIN_WORDS = 8
NONCLAIM_REASON_MIN_WORDS = 10

#: Surfaces for which no non-claim exemption may ever be granted (71.2.4).
NONCLAIM_FORBIDDEN_SURFACES: tuple[str, ...] = (
    "LIMITATIONS.md",
    "README.md",
    "meta:",
    "paper:abstract",
)

#: Gates that WAIVER.md must refuse to parse (section 71.7 item 12).
UNWAIVABLE_GATES: tuple[str, ...] = (
    "G-CLAIM-BANNED",
    "G-FRAMING-CLI",
    "G-FRAMING-PAPER",
    "G-FRAMING-README",
    "G-FRAMING-VERBATIM",
    "G-LIMITS-NOHAND",
)

#: Every finding kind this checker can emit.  `G-CLAIM-SELFTEST` iterates this
#: rather than a hand-maintained list, which is the point of exposing it.
FINDING_KINDS: tuple[str, ...] = (
    "ALLOWLIST_FORBIDDEN_SURFACE",
    "ALLOWLIST_NO_CAP",
    "ALLOWLIST_OVER_CAP",
    "ALLOWLIST_REASON_TOO_SHORT",
    "ALLOWLIST_STALE_HASH",
    "BANNED",
    "FRAMING_MISSING",
    "FRAMING_OUT_OF_ORDER",
    "ID_ERASED",
    "ID_REUSED",
    "NUMBER_NOT_IN_ARTIFACT",
    "NUMERAL_OUTSIDE_GENERATED_BLOCK",
    "ORPHAN",
    "PARSE_ERROR",
    "PLACEHOLDER_ESCAPED",
    "SCOPE_INVALID",
    "SELFTEST_FIXTURE_MISSING",
    "STALE",
    "SURFACE_UNDECLARED",
    "SURFACE_UNREADABLE",
    "TEXT_DRIFT",
    "TUNED_ON_HEADLINE",
    "UNANCHORED",
    "UNREGISTERED",
    "WAIVER_ON_UNWAIVABLE_GATE",
)

#: The sub-states of the STALE finding kind (section 71.3's state table).
SUPPORT_STATES: tuple[str, ...] = (
    "FLAGGED",
    "FRESH",
    "GATE_NOT_GREEN",
    "MISSING_ARTIFACT",
    "NOT_MEASURED",
    "STALE_HASH",
    "STALE_INPUTS",
)


# --------------------------------------------------------------------------
# The banned-phrase table (docs/banned.toml's machine-readable form)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BannedPattern:
    """One row of section 71.4's table.

    `only_paths` / `not_paths` carry the per-entry scopes that three of the
    seventeen rows state in prose ("outside docs/range/not-modeled.md", "in the
    README or the abstract", "in docs").  `requires` carries the one row whose
    scope is a co-occurrence condition rather than a path.  `narrowed` records,
    in the pattern itself, where the mechanical form is deliberately narrower
    than the prose - so the narrowing is visible in the report instead of being
    an undocumented silent gap.

    `use_only` applies the use/mention test described at `is_mention`: the row
    fires on a phrase the document *asserts*, not on one it quotes, names as a
    string, or forbids.  It defaults to True because every row on this table
    bans a claim, and a claim is something a sentence makes rather than
    something it mentions.
    """

    id: str
    patterns: tuple[str, ...]
    replacement: str
    ignore_case: bool = True
    only_paths: tuple[str, ...] = ()
    not_paths: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    narrowed: str = ""
    use_only: bool = True

    def regexes(self) -> tuple[re.Pattern[str], ...]:
        flags = re.IGNORECASE if self.ignore_case else 0
        return tuple(re.compile(p, flags) for p in self.patterns)


# --------------------------------------------------------------------------
# The use / mention test
# --------------------------------------------------------------------------
#
# DECIDED (use vs mention).  Every row of the banned table bans a CLAIM.  A
# claim is asserted, and a sentence that quotes a phrase, names it as a string,
# or forbids it is not asserting it.  Without this distinction the gate fires
# on exactly the documents that are most careful:
#
#   * `.github/PULL_REQUEST_TEMPLATE.md`'s checklist line, for listing what it
#     forbids ("No banned phrase, no score, no confidence, no severity"),
#   * `README.md`'s scope paragraph, for saying SPECTRA "emits no probability,
#     score, severity or likelihood of any kind",
#   * `docs/range/not-modeled.md`, for the sentence "do not call the range
#     enterprise-grade",
#   * `docs/adr/0009-*.md`, for naming the banned vocabulary it is introducing
#     the gate to ban,
#   * `docs/plan/CONFLICTS*.md`, which quote the specification verbatim as the
#     evidence for each conflict they report.
#
# A gate that fails a file for naming what it bans is not enforcing honesty; it
# is punishing the act of writing the prohibition down, and it teaches readers
# that its findings are noise.
#
# The test has two mechanical halves, neither of which is an English judgement:
#
#   1. The match lies inside a quotation or a backtick code span.  A phrase in
#      quotes is reported speech; a phrase in backticks is a string literal or
#      an identifier.  Neither is the sentence's own assertion.
#   2. A prohibition or metalinguistic marker occurs EARLIER IN THE SAME UNIT
#      than the match: "banned", "forbidden", "do not say", "may not", "the
#      words", "vocabulary", a `BP-##` citation, and so on.
#
# Half 2 requires the marker to precede the match on purpose.  "SPECTRA is
# production-ready, and we do not claim otherwise" must still fail, and it
# does, because its negation comes after the phrase.  The residual hole is a
# sentence that opens with an unrelated prohibition and then makes a claim
# ("nothing is forbidden here, and SPECTRA is production-ready"); that is
# reported as the narrowing it is, under G-CLAIM-BANNED/USE-MENTION, rather
# than papered over.

#: Markers that make a unit metalinguistic: it is talking ABOUT a phrase.
#: Matched case-insensitively, and only where they start before the match.
MENTION_MARKERS: tuple[str, ...] = (
    # Speech-act prohibitions.
    r"\bban(?:s|ned|ning)?\b",
    r"\bforbid(?:s|den|ding)?\b",
    r"\bprohibit(?:s|ed|ing|ion|ions)?\b",
    r"\bdisallow(?:s|ed|ing)?\b",
    r"\bunwaivable\b",
    r"\billegal\b",
    r"\bnot\s+(?:sayable|permitted|allowed|licensed|acceptable)\b",
    r"\bno\s+longer\b",
    r"\bmay\s+not\b",
    r"\bmust\s+not\b",
    r"\bnever\s+(?:say|says|use|uses|claim|claims|print|prints|emit|emits|"
    r"describe|describes|write|writes|state|states|as)\b",
    r"\bdo(?:es)?\s+not\s+(?:say|use|claim|print|emit|describe|call|state|imply)\b",
    r"\bdo\s+not\b",
    r"\bstop\s+saying\b",
    r"\b(?:emit|emits|emitted|print|prints|report|reports|produce|produces|"
    r"output|outputs|make|makes|carry|carries|contain|contains)\s+no\b",
    r"\bno\s+(?:banned|score|scores|scoring|probability|confidence|severity|"
    r"risk|likelihood|priority|dollar|percentage|verdict|guarantee|claim)\b",
    r"\bno\s+(?:metric|field|column|key|string|literal|label|output|value|"
    r"number|name|word|phrase|sentence|adjective)s?\b",
    r"\bnegative\s+requirements?\b",
    r"\blint(?:s|er|ers|ing)?\b",
    r"\bdeleted\s+from\s+the\s+project\b",
    r"\breplaced\s+by\b",
    r"\bcarve[- ]?outs?\b",
    # Metalinguistic markers: the unit is discussing wording.
    r"\bvocabular(?:y|ies)\b",
    r"\bwording\b",
    r"\bphras(?:e|es|ing)\b",
    r"\bthe\s+words?\b",
    r"\bword\s?list\b",
    r"\bsub\s?strings?\b",
    r"\bbanned_substrings\b",
    r"\bverbatim\b",
    r"\bspelling\b",
    r"\bsynonyms?\b",
    r"\blookarounds?\b",
    r"\bregexe?s?\b",
    # A unit that cites the banned table, or the gate, is discussing the ban.
    r"\bBP-\d{2}\b",
    r"\bG-CLAIM-BANNED\b",
    r"\bG-UI-BANNED\b",
    r"\bG-CLI-BANNED\b",
    r"\bno-?score[- ]lint\b",
    r"\blint-no-scores\b",
)

_MENTION_MARKER_RE = re.compile("|".join(MENTION_MARKERS), re.IGNORECASE)

#: Spans in which a phrase is named rather than asserted.  The single-quote
#: form is guarded on both ends so that the apostrophe in "Part I's" cannot
#: open a span and swallow half a sentence.
_QUOTED_SPAN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"`+[^`]*`+"),
    re.compile(r'"[^"\n]*"'),
    re.compile("“[^”\n]*”"),
    re.compile(r"(?<![A-Za-z0-9])'[^'\n]*'(?![A-Za-z0-9])"),
    re.compile("(?<![A-Za-z0-9])‘[^’\n]*’"),
)


#: Marks whose unpaired form means the unit is a FRAGMENT of a quotation.
#: Segmentation cuts a paragraph at sentence boundaries, so a quotation running
#: across two sentences arrives here split, with its opening mark on one unit
#: and its closing mark on the next.  Both halves are reported speech, and
#: neither can be told from the other without carrying quote state between
#: units, so a unit holding an unpaired mark is treated as quoted throughout.
#: Without this, §25.11's UI header - the very string the specification quotes
#: to show what BP-08 and BP-11 forbid - is read as an assertion by whichever
#: half of it lands in the second unit.
_UNPAIRED_MARKS: tuple[str, ...] = ('"', "`", "“", "”")


def quoted_spans(text: str) -> list[tuple[int, int]]:
    """Half-open spans of `text` that are quotations or backtick code spans."""
    spans: list[tuple[int, int]] = []
    for rx in _QUOTED_SPAN_RES:
        spans.extend((m.start(), m.end()) for m in rx.finditer(text))
    for i, ch in enumerate(text):
        if ch not in _UNPAIRED_MARKS:
            continue
        if any(lo <= i < hi for lo, hi in spans):
            continue
        return [(0, len(text))]
    return spans


def is_mention(text: str, start: int, end: int, spans: Sequence[tuple[int, int]]) -> bool:
    """True when the match at [start, end) is mentioned rather than asserted.

    `spans` is `quoted_spans(text)`, hoisted out so one unit is scanned once
    however many patterns are tested against it.
    """
    for lo, hi in spans:
        if lo <= start and end <= hi:
            return True
    marker = _MENTION_MARKER_RE.search(text)
    return marker is not None and marker.start() < start


#: The left guard on BP-08's verdict token.  It excludes the identifier forms
#: (`NON_ROBUST`, `ROBUST(` already bound) and the named-class forms that a
#: specification cannot avoid writing when it states the rule that PRODUCES the
#: verdict: `non-ROBUST`, `false ROBUST`, `zero-false-ROBUST`, "an unflagged
#: ROBUST verdict".  None of those is a verdict being reported to a reader.
_BARE_VERDICT_GUARD = (
    r"(?<![A-Za-z0-9_(\-])(?<!\bfalse )(?<!\bnon )(?<!\bzero )(?<!\bunflagged )"
)


# The table is hand-authored here rather than generated from CLAIMS.md's
# markdown.  CLAIMS.md escapes pipes inside table cells (`production[- ](ready\|like)`)
# and packs several alternatives into one cell; a generator that misses either
# silently corrupts a pattern, and a corrupted banned pattern is a gate that
# does not fire.  Hand-authoring keeps the regexes reviewable as regexes.
BANNED_PATTERNS: tuple[BannedPattern, ...] = (
    BannedPattern(
        id="BP-01",
        patterns=(r"prov\w*\s+(?:that\s+)?the attack would have been prevented",),
        replacement=(
            "proves that, in SPECTRA's model of this bundle, the goal atom is not "
            "derivable under this cut"
        ),
    ),
    BannedPattern(
        # DECIDED (narrowing): the bare `\bguarantee[sd]?\b` cannot tell the
        # ASSERTION apart from the NOUN.  The mandated replacement -
        # "establishes, relative to rules@<hash> and catalog@<hash>," - is a
        # verb phrase, which says what the row is aimed at: SPECTRA guaranteeing
        # something.  The noun names a property of some OTHER artifact, and this
        # tree is full of honest ones: "the determinism guarantee", "9.3's
        # no-collision guarantee", "an `ln n + 1` guarantee", "tamper-detection
        # guarantees", "bracketing guarantees".  Banning those bans the
        # vocabulary a specification needs in order to describe what it does not
        # have.  So the row fires on the assertive senses only: SPECTRA (or one
        # of its parts, or a first-person subject) as the guarantor, a guarantee
        # OF a security outcome, and `guaranteed` as a bare quality adjective.
        id="BP-02",
        patterns=(
            r"\b(?:SPECTRA|ECLIPSE|we|it|this|the\s+(?:kernel|checker|tool|engine|"
            r"system|platform|certificate|proof|cut|verdict|reconstruction|"
            r"reconstructor|project|product))\s+guarantees?\b",
            r"\bguarantee[sd]?\s+(?:that\s+)?(?:the\s+|a\s+|an\s+)?(?:attack|attacks|"
            r"breach|breaches|compromise|security|safety|soundness|correctness|"
            r"completeness|detection|prevention|coverage|protection)\b",
            r"\bguaranteed\s+(?:secure|safe|correct|sound|complete|robust|accurate|"
            r"minimal|exhaustive|reliable)\b",
        ),
        replacement="establishes, relative to rules@<hash> and catalog@<hash>,",
        narrowed=(
            "the noun sense is not matched - 'the determinism guarantee', "
            "'tamper-detection guarantees', 'an `ln n + 1` guarantee' name a "
            "property of some other artifact and are not a claim SPECTRA makes.  "
            "The row fires on SPECTRA (or a part of it, or a first-person subject) "
            "as the guarantor, on a guarantee of a security outcome, and on "
            "'guaranteed' as a bare quality adjective.  An assertion with a "
            "subject outside that list - 'the shipped catalog guarantees safety' "
            "would be caught by the second form, 'the adapter guarantees it' would "
            "not - escapes"
        ),
    ),
    BannedPattern(
        id="BP-03",
        patterns=(r"detects? all\b", r"\bcatches every\b", r"\bzero false negatives?\b"),
        replacement=(
            "detects the declared suppression classes; class frequencies and the "
            "undetected share are in LIMITATIONS.md"
        ),
    ),
    BannedPattern(
        id="BP-04",
        patterns=(r"\bAI[- ]powered\b", r"\bAI[- ]driven\b", r"\bintelligent\b"),
        replacement=(
            "deterministic; an optional local model narrates the certificate and "
            "changes no result (`make verify-no-llm`)"
        ),
    ),
    BannedPattern(
        id="BP-05",
        patterns=(r"real[- ]time threat detection", r"\breal[- ]time\b"),
        replacement="post-hoc reconstruction over a recorded telemetry bundle",
    ),
    BannedPattern(
        id="BP-06",
        patterns=(
            r"enterprise[- ]grade",
            r"production[- ](?:ready|like)",
            r"battle[- ]tested",
            r"industry[- ]standard",
        ),
        replacement=(
            "a laboratory range; what it does not model is enumerated in "
            "docs/range/not-modeled.md"
        ),
    ),
    BannedPattern(
        id="BP-07",
        patterns=(r"military[- ]grade", r"bank[- ]grade", r"\bunbreakable\b", r"\bbulletproof\b"),
        replacement="delete the sentence",
    ),
    BannedPattern(
        # DECIDED (case sensitivity): CLAIMS.md's table header declares the whole
        # table case-insensitive, but this row bans a bare VERDICT TOKEN, and the
        # spec's own regex is written in capitals.  Case-insensitively it matches
        # the ordinary English word "robust" - 373 occurrences across this tree,
        # including the LIMITATIONS.md prose the gate exists to protect.  The
        # per-row regex wins over the table-wide flag.  The lookbehind is widened
        # from the spec's `[A-Za-z(]` to also exclude digits and underscore, so
        # an identifier such as NON_ROBUST is not a hit.
        id="BP-08",
        patterns=(
            # The token announced as a verdict: after a verdict label, ...
            r"(?i:\bverdict|\bmode|\bstatus|\bsafety|\bresult|\boutcome|\bstate)"
            r"\s*[:=]\s*[\"'`]*" + _BARE_VERDICT_GUARD + r"ROBUST(?!\()",
            # ... after a verb that reports it, ...
            r"(?i:\breturns?|\breturned|\bprints?|\bprinted|\breports?|\breported"
            r"|\bemits?|\bemitted|\byields?|\bshows?|\bdisplays?|\bis|\bwas|\bare"
            r"|\bwere|\bsays?|\bsaid)\s+[\"'`]*" + _BARE_VERDICT_GUARD + r"ROBUST(?!\()",
            # ... or as a delimited field of a rendered result line, which is the
            # shape of the header the specification calls out by name:
            # "Minimum cut {...} - ROBUST - 6 corridors - blake3:3f9a...".
            r"[\u2014\u2013|\[]\s*" + _BARE_VERDICT_GUARD + r"ROBUST(?!\()",
            _BARE_VERDICT_GUARD + r"ROBUST(?!\()\s*[\u2014\u2013|\]]",
            # ... or standing alone as the whole string.
            r"^[\s\W]*" + _BARE_VERDICT_GUARD + r"ROBUST(?!\()[\s\W]*$",
        ),
        replacement=(
            "ROBUST(rules@<hash8>, catalog@<hash8>, licenses@<hash8>, non-adaptive) - "
            "identically for OPTIMISTIC_ONLY and UNSAFE"
        ),
        ignore_case=False,
        narrowed=(
            "only the ROBUST token is matched; OPTIMISTIC_ONLY and UNSAFE are named "
            "in the replacement but not given as patterns.  The row is further "
            "narrowed to the token IN A VERDICT POSITION - after a verdict label, "
            "after a verb that reports it, as a delimited field of a rendered "
            "result line, or standing alone.  The bare `ROBUST` not followed by "
            "`(` also matches the token used as a NAME in the verdict algebra - "
            "`non-ROBUST`, `false-ROBUST`, 'blocks ROBUST', '{ROBUST, "
            "OPTIMISTIC_ONLY, UNSAFE}', 'the ROBUST downgrade' - and a "
            "specification cannot state the rule that produces the verdict "
            "without naming the verdict.  A rendered verdict introduced by a "
            "label outside the list escapes"
        ),
    ),
    BannedPattern(
        id="BP-09",
        patterns=(
            r"which control would have prevented",
            r"would have stopped",
            r"what[- ]if control replay",
        ),
        replacement=(
            "the normative framing strings in docs/framing.toml; the interaction is "
            "named IN-MODEL CONTROL CUT"
        ),
    ),
    BannedPattern(
        id="BP-10",
        patterns=(r"formally verified", r"\bproof of security\b"),
        replacement="carries a machine-checkable certificate over the model",
    ),
    BannedPattern(
        id="BP-11",
        patterns=(r"minimum cut(?! over the declared catalog)",),
        replacement=(
            "cardinality-minimal cut over the declared catalog "
            "(minimality: EXACT, SUBSET or UNVERIFIED)"
        ),
    ),
    BannedPattern(
        id="BP-12",
        patterns=(r"\brealistic\b", r"\bmimics a real\b"),
        replacement="a laboratory model of X; see docs/range/not-modeled.md",
        not_paths=("docs/range/not-modeled.md",),
    ),
    BannedPattern(
        # DECIDED (narrowing): the row's scope is "in the README or the abstract
        # WITHOUT A CITATION-BACKED RECORD".  There is no mechanical test for
        # "citation-backed", so the path scope is enforced and the bare `\bfirst\b`
        # alternative is dropped: it matches "local-first", "first screen" and
        # "first commit", none of which is a priority claim, and a gate that cries
        # wolf on ordinary English gets switched off.
        id="BP-13",
        patterns=(r"state[- ]of[- ]the[- ]art", r"\bnovel\b"),
        replacement=(
            "related work is discussed in paper/related.tex; no priority claim is made"
        ),
        only_paths=("README.md", "paper/"),
        narrowed=(
            "the bare `first` alternative is not matched (no mechanical test for "
            "'without a citation-backed record'); scope is the README and paper/"
        ),
    ),
    BannedPattern(
        # DECIDED: "a bare polyglot language count" has no mechanical form.  The
        # specification's own narrow regex is used instead of CLAIMS.md's prose.
        id="BP-14",
        patterns=(r"\b4[0-9]\+? languages\b",),
        replacement=(
            "the two machine-generated figures from the polyglot mutation audit: "
            "languages executing code in CI, and configuration formats"
        ),
        narrowed=(
            "only the specification's narrow form is matched; a general 'bare "
            "polyglot count' is not mechanically recognisable"
        ),
    ),
    BannedPattern(
        # DECIDED: "applied to the redundancy index or the observation set" is
        # rendered mechanically as co-occurrence within the same text unit.
        id="BP-15",
        patterns=(r"\bexact\b",),
        replacement="exact when the corridor set is complete; otherwise suppressed",
        requires=("redundancy index", "observation set"),
        narrowed=(
            "only fires when the unit also names the redundancy index or the "
            "observation set"
        ),
    ),
    BannedPattern(
        # DECIDED (narrowing): the banned thing is A SCALAR PRESENTED AS A
        # SPECTRA OUTPUT - "report the set, not a scalar" is the replacement, and
        # the gate that enforces the same rule in code is G-NO-SCORES, which is
        # specified over SCHEMA FIELDS.  The five bare words are not that.  Taken
        # bare they fail:
        #   * `.github/PULL_REQUEST_TEMPLATE.md`, for the checklist line "No
        #     banned phrase, no score, no confidence, no severity" - the file is
        #     flagged for naming what it forbids;
        #   * `README.md`, for "it emits no probability, score, severity or
        #     likelihood of any kind", which is the disclaimer the row exists to
        #     produce;
        #   * `docs/plan/DECISIONS.md` 27 times, for using "severity" as the
        #     triage axis of a specification-conflict queue - a property of a
        #     DECISION, not of a SPECTRA result;
        #   * every honest statistical use of "confidence interval", which Part I
        #     mandates on every reported mean and which is not a verdict score.
        # So the row is narrowed to the scalar-output shapes: a named score, a
        # scalar bound to a numeral, a numeric field, and the "numeric/overall/
        # aggregate <word>" constructions.  A bare noun in prose no longer fires.
        id="BP-16",
        patterns=(
            # A named score: "risk score", "confidence_score", "threat-scoring".
            r"\b(?:risk|confidence|severity|threat|priority|trust|suspicion|belief|"
            r"certainty|plausibility)[-_ ]scor(?:e|es|ed|ing)\b",
            r"\bscor(?:e|es|ed|ing)\s+(?:of\s+)?(?:risk|severity|confidence|threat)\b",
            # A field or key bound to a number: `confidence: 0.92`, severity=3.
            r"\b(?:confidence|probability|likelihood|severity|risk|priority)\s*[:=]\s*-?\d",
            # A numeral qualified by the word: "0.92 confidence", "80% likelihood".
            r"\b\d+(?:\.\d+)?\s*%?\s+(?:confidence|probability|likelihood)\b"
            r"(?!\s+(?:interval|intervals|band|bands|region|regions|bound|bounds))",
            # The scalar named as a reported quantity.
            r"\b(?:confidence|probability|likelihood|severity|risk|threat)\s+"
            r"(?:score|rating|level|band|value|metric|number|percentage|figure|"
            r"index|weight)s?\b",
            r"\b(?:numeric|numerical|overall|aggregate|aggregated|computed|derived|"
            r"final|scalar|invented)\s+"
            r"(?:confidence|probability|likelihood|severity|risk|score)\b",
        ),
        replacement="delete; report the set, not a scalar",
        narrowed=(
            "the five bare words are not matched.  The row fires on a scalar "
            "presented as an output - a named score, a field bound to a numeral, "
            "a numeral qualified by the word, or a 'numeric/overall/aggregate' "
            "construction - and not on the English words in prose, so "
            "'confidence interval' (a statistic Part I mandates) and 'severity' "
            "as a triage axis for specification conflicts both pass.  A scalar "
            "introduced under some other noun entirely is not mechanically "
            "recognisable and is left to G-NO-SCORES, which reads the schemas"
        ),
    ),
    BannedPattern(
        # DECIDED (narrowing): the row's stated reason is "these words hide
        # unproven steps", which is the HEDGE sense - "just run make", "simply
        # add the adapter", "obviously correct".  Bare, the four words also match
        # the ordinary senses that carry no hedge at all, and this tree uses them
        # constantly and honestly: "not just code", "not just those needed to
        # force the current cut", "take just `{cert_id}`", "the file it had just
        # written" (temporal), "Part II simply does not address the point",
        # "they simply never join a component", "not obviously the same address".
        # None of those minimises a step; each means MERELY, ONLY or EVIDENTLY.
        # So `just` and `simply` fire only in front of a verb of doing, which is
        # where the hedge lives, and `obviously` is excluded after a negation,
        # where "not obviously X" asserts the opposite of the hedge.
        id="BP-17",
        patterns=(
            # The lookbehinds drop the relative and comparative frames - "an
            # implementer who just wires these in", "not just code", "rather
            # than simply dropping it" - in which the adverb means MERELY.
            r"(?<!\bnot )(?<!\bwho )(?<!\bthan )(?<!\bnor )(?<!\bbut )"
            r"\b(?:just|simply)\s+(?:run|runs|add|adds|use|uses|install|installs|"
            r"edit|edits|set|sets|call|calls|type|copy|copies|drop|drops|point|"
            r"points|open|opens|change|changes|replace|replaces|delete|deletes|"
            r"remove|removes|write|writes|clone|clones|build|builds|import|"
            r"imports|enable|enables|disable|disables|apply|applies|rerun|"
            r"re-run|swap|swaps|plug|plugs|make|makes)\b",
            r"(?<!\bnot )(?<!\bwho )(?<!\bthan )\b(?:just|simply)\s+works?\b",
            r"\b(?:just|simply)\s+a\s+matter\s+of\b",
            r"\beasily\b",
            r"(?<!\bnot )(?<!\bless )(?<!\bnone )\bobviously\b",
        ),
        replacement="delete",
        only_paths=("docs/",),
        narrowed=(
            "`just` and `simply` are matched only in front of a verb of doing, "
            "which is the hedge sense the row's reason names; the MERELY / ONLY "
            "sense ('not just code', 'take just `{cert_id}`') and the temporal "
            "sense ('the file it had just written') are not matched, and "
            "`obviously` is not matched after a negation.  A hedge in front of a "
            "verb outside the list escapes"
        ),
    ),
)

BANNED_PATTERN_IDS: tuple[str, ...] = tuple(p.id for p in BANNED_PATTERNS)


# --------------------------------------------------------------------------
# Candidate-detection wordlists
# --------------------------------------------------------------------------

#: Section 71.2.3's minimum set.  `tools/claimcheck/verbs.txt`, when it exists,
#: replaces this list; the built-in copy is what makes the checker runnable
#: before that file is authored.
CAPABILITY_VERBS: tuple[str, ...] = (
    "all",
    "always",
    "any",
    "automatically",
    "complete",
    "detect",
    "detects",
    "ensure",
    "every",
    "exact",
    "faster",
    "guarantee",
    "identify",
    "minimal",
    "minimize",
    "never",
    "outperform",
    "prevent",
    "prevents",
    "prove",
    "proven",
    "proves",
    "real-time",
    "reconstruct",
    "reconstructs",
    "robust",
    "scalable",
    "secure",
    "sound",
    "stop",
    "stopped",
    "verified",
    "verify",
    "zero",
)

COMPARATIVE_TOKENS: tuple[str, ...] = (
    "compared to",
    "first",
    "only",
    "state of",
    "than",
    "versus",
    "vs",
)

#: Tokens after which a full stop does not end a sentence.  Replaced by
#: `tools/claimcheck/abbrev.txt` when that file exists.
ABBREVIATIONS: tuple[str, ...] = (
    "al.",
    "cf.",
    "e.g.",
    "etc.",
    "fig.",
    "i.e.",
    "no.",
    "vs.",
)

VERBS_FILE = "tools/claimcheck/verbs.txt"
ABBREV_FILE = "tools/claimcheck/abbrev.txt"


# --------------------------------------------------------------------------
# Non-claim token classes (section 71.2.3)
# --------------------------------------------------------------------------

# Removed from a unit's text BEFORE the NUMERAL test.  Every class must be
# structurally recognisable rather than an English judgement.  Order matters:
# the longer, more specific forms are removed first so that a shorter class
# cannot bite a piece out of them.
#
# Four classes beyond the spec's list are removed here, each because leaving it
# in produces a false positive that would make the gate unusable, and each
# recognisable by shape alone:
#   * URLs and markdown link targets (a link is a path with a scheme).
#   * Identifiers of the project's own registries: CLM-0007, G-CLAIM-001,
#     BP-01, W-0001, M0, T1, S1.  These are names, not measurements.
#   * "section 71.2" written without the section sign.
#   * Licence identifiers such as "Apache 2.0".
NON_CLAIM_TOKEN_CLASSES: tuple[tuple[str, str], ...] = (
    ("url", r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://\S+"),
    ("markdown_link_target", r"\]\([^)\s]*\)"),
    ("attack_id", r"\bT\d{4}(?:\.\d{3})?\b"),
    ("blake3_digest", r"\b[0-9a-f]{64}\b"),
    ("git_sha", r"\b(?=[0-9a-f]{7,40}\b)[0-9a-f]*[a-f][0-9a-f]*\b"),
    ("iso_8601", r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+\-]\d{2}:?\d{2})?)?\b"),
    ("clock_time", r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    ("semver", r"\bv?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?\b"),
    ("cidr", r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b"),
    ("rfc", r"\bRFC[- ]?\d+\b"),
    ("section_sign", r"\u00a7\s*\d+(?:\.\d+)*"),
    ("section_word", r"\b[Ss]ections?\s+\d+(?:\.\d+)*"),
    ("licence_id", r"\bApache[- ]2\.0\b"),
    ("backticked_status_code", r"`[1-5]\d{2}`"),
    ("backticked_byte_width", r"`[iuf](?:8|16|32|64|128)`"),
    ("byte_width", r"\b[iuf](?:8|16|32|64|128)\b"),
    ("registry_id", r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b"),
    ("milestone_id", r"\bM(?:10|[0-9])\b"),
    ("tier_id", r"\bT[0-3]\b"),
    ("class_id", r"\bS\d{1,2}\b"),
    ("port", r"(?<=[A-Za-z0-9\]]):\d{2,5}\b"),
    ("file_path", r"(?<![\w/])[A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)+/?"),
    ("filename", r"\b[A-Za-z0-9_\-]+\.(?:md|toml|json|jsonc|txt|py|rs|ts|tsx|yml|yaml|tex|aux|sh|mk|lock|cff|c|cpp|h|go|java)\b"),
    ("list_ordinal", r"(?m)^\s*\d+[.)]\s"),
)

_NON_CLAIM_RE: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pat)) for name, pat in NON_CLAIM_TOKEN_CLASSES
)

NUMERAL_RE = re.compile(
    r"(?<![A-Za-z0-9_])\d[\d.,_]*\s*(?:%|x|\u00d7|ms|s|min|h|MB|GB|k|K|M)?"
)

CLAIM_ID_RE = re.compile(r"CLM-\d{4}")
STRICT_CLAIM_ID_RE = re.compile(r"^CLM-\d{4}$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
GENERATED_BEGIN_RE = re.compile(r"<!--\s*BEGIN GENERATED:\s*(\S+).*?-->")
GENERATED_END_RE = re.compile(r"<!--\s*END GENERATED:\s*(\S+)\s*-->")

# The tag's stable prefix, not its full literal: the repository's own documents
# carry it as "(illustrative, not a target: the repo ships 5 ...)", and a
# checker that insisted on the closing parenthesis would miss every one of
# those.  Whitespace is tolerated because markdown wraps the tag across lines.
PLACEHOLDER_TOKENS: tuple[tuple[str, str], ...] = (
    ("illustrative-tag", r"\(illustrative,\s+not\s+a\s+target\b"),
    ("measured-token", r"<<MEASURED:[^>]*>>"),
)


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

_SMART_QUOTES = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u00a0": " ",
    "\u2007": " ",
    "\u202f": " ",
    "\ufeff": "",
}

_EMPHASIS_RE = re.compile(r"(\*\*|\*|__|_)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_WS_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Canonical form used for text comparison and for allowlist hashing.

    DECIDED: neither CLAIMS.md nor section 71 defines `normalise()`, yet both
    TEXT_DRIFT and the non-claim allowlist key are specified in terms of it.
    Without *some* normalisation no claim can ever be registered, because a
    markdown sentence wrapped across two source lines is never byte-identical
    to a single-line registry string.  The rule adopted here is the smallest
    one that makes registration possible:

      1. unicode space and smart-quote folding,
      2. markdown inline markup removed - images, links (anchor text kept),
         emphasis markers, backticks, and HTML comments,
      3. whitespace runs collapsed to one space, ends stripped.

    Nothing else is touched.  Case, punctuation, digits, hyphens and dashes all
    survive, so a one-character difference in the sentence itself still fails.
    """
    out = text
    for bad, good in _SMART_QUOTES.items():
        out = out.replace(bad, good)
    out = HTML_COMMENT_RE.sub(" ", out)
    out = _IMAGE_RE.sub(r"\1", out)
    out = _LINK_RE.sub(r"\1", out)
    # Emphasis can nest (**_x_**); two passes settle every case this repo uses.
    out = _EMPHASIS_RE.sub(r"\2", out)
    out = _EMPHASIS_RE.sub(r"\2", out)
    out = out.replace("`", "")
    out = _WS_RE.sub(" ", out)
    return out.strip()


def one_line(text: str) -> str:
    """Flatten to a single line; `Finding.message` must never carry a newline."""
    return _WS_RE.sub(" ", text).strip()


def excerpt(text: str, limit: int = 120) -> str:
    """A short, quoted, single-line excerpt for a finding message."""
    flat = one_line(text)
    if len(flat) > limit:
        flat = flat[: limit - 3] + "..."
    return '"' + flat.replace('"', "'") + '"'


def slugify(heading: str) -> str:
    """GitHub-style heading anchor: lowercase, punctuation dropped, spaces to -.

    DECIDED: nothing specifies how a unit's `#anchor` is derived.  The
    GitHub slug of the nearest preceding heading is the only derivation a
    reader can predict from the rendered page, so it is the one used.
    """
    text = normalise(heading).lower()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    text = text.strip().replace(" ", "-")
    return re.sub(r"-{2,}", "-", text)


def content_hash(text: str) -> str:
    """The allowlist's line-content hash: sha256 over the normalised text.

    DECIDED: this hash is internal to the checker and never appears in the
    record grammar, so it does not have to be BLAKE3 (which is not in the
    standard library).  `support.blake3` is a different thing entirely: it is
    checked for shape here and recomputed only by the support resolver, which
    this tool reports as skipped.
    """
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def strip_non_claim_tokens(text: str) -> str:
    """Remove the structurally-recognisable non-claim token classes."""
    out = text
    for _name, rx in _NON_CLAIM_RE:
        out = rx.sub(" ", out)
    return out


# --------------------------------------------------------------------------
# Path and glob helpers
# --------------------------------------------------------------------------


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a surface glob to a regex with real `**` semantics.

    `fnmatch` cannot express these patterns: its `*` crosses `/`, so
    `docs/**/*.md` would fail to match `docs/NON-GOALS.md` while matching
    things it should not.  Here `**/` means zero or more directories and `*`
    stays inside one path segment.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append(r"(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(r".*")
            i += 2
        elif ch == "*":
            out.append(r"[^/]*")
            i += 1
        elif ch == "?":
            out.append(r"[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


def path_matches(rel: str, pattern: str) -> bool:
    """True when a repo-relative path matches a surface glob.

    Matching is case-insensitive.  The surface list names
    `.github/PULL_REQUEST_TEMPLATE.md` while the file on disk is
    `.github/pull_request_template.md`; GitHub treats those as the same file
    and so must this, or the gate silently stops covering that surface.
    """
    return bool(_glob_to_regex(pattern).match(rel))


def under_any(rel: str, prefixes: Sequence[str]) -> bool:
    """True when `rel` is one of `prefixes` or lives under one of them.

    A prefix ending in `/` is a directory; anything else is an exact path.
    """
    low = rel.lower()
    for prefix in prefixes:
        p = prefix.lower()
        if p.endswith("/"):
            if low.startswith(p):
                return True
        elif low == p:
            return True
    return False


def iter_repo_files(root: Path) -> Iterator[str]:
    """Every file in the tree, repo-relative, forward slashes, sorted."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        prefix = "" if rel_dir == "." else rel_dir + "/"
        for name in sorted(filenames):
            yield prefix + name


def read_text(root: Path, rel: str) -> tuple[str | None, str | None]:
    """Read a repo file as text.  Returns (text, error); never raises.

    Line endings are normalised to LF so that a CRLF checkout reports the same
    line numbers as an LF one.
    """
    try:
        raw = (root / rel).read_bytes()
    except OSError as exc:
        return None, f"cannot read file: {exc.strerror or exc}"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"not valid UTF-8 at byte {exc.start}"
    return text.replace("\r\n", "\n").replace("\r", "\n"), None


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Record:
    """One parsed `### CLM-####` record."""

    claim_id: str
    line: int
    text: str
    kind: str
    surfaces: tuple[str, ...]
    artifact: str
    blake3: str
    run: str
    gate: str
    target: str
    scope: str
    status: str
    note: str | None


@dataclass
class Registry:
    path: str
    schema: int | None = None
    records: dict[str, Record] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    present: bool = True


_SURFACE_FORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("readme", re.compile(r"^README\.md#[A-Za-z0-9][A-Za-z0-9\-_.]*$")),
    ("docpath", re.compile(r"^docs/[A-Za-z0-9][A-Za-z0-9\-_./]*#[A-Za-z0-9][A-Za-z0-9\-_.]*$")),
    ("uikey", re.compile(r"^ui:[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")),
    ("clikey", re.compile(r"^cli:[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")),
    ("demoline", re.compile(r"^demo:[A-Za-z0-9][A-Za-z0-9\-_.]*$")),
    ("paperkey", re.compile(r"^paper:(?:abstract|intro|eval|concl)$")),
    ("releasekey", re.compile(r"^release:\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")),
    ("metakey", re.compile(r"^meta:(?:github_about|github_topics|cv_bullets)$")),
)

BLAKE3_RE = re.compile(r"^[0-9a-f]{64}$")
DQSTRING_RE = re.compile(r'^"(.*)"$', re.DOTALL)


def surface_form(surface: str) -> str | None:
    """The name of the surface form `surface` takes, or None if it takes none."""
    for name, rx in _SURFACE_FORMS:
        if rx.match(surface):
            return name
    return None


def find_registry(root: Path) -> str:
    """Locate the registry file.

    DECIDED (registry path): three places name it and they disagree - section
    71.1 and the Makefile stub say `docs/claims.md`, CLAIMS.md records a
    decision to keep it at the root, and the Makefile's own SKELETON_FILES list
    requires root `CLAIMS.md` to exist.  Two of the three say root, and root is
    the file that exists, so root wins.  `docs/claims.md` is accepted as a
    fallback so that the eventual move does not break this tool on the commit
    that makes it.
    """
    for candidate in REGISTRY_CANDIDATE_PATHS:
        if (root / candidate).is_file():
            return candidate
    return REGISTRY_CANDIDATE_PATHS[0]


def _fence_mask(lines: Sequence[str]) -> list[bool]:
    """True for every line inside a fenced code block, including the fences.

    The registry's own `### Record grammar` block contains a literal
    `### CLM-####`.  A parser that does not respect fences reads that example
    as a malformed record and fails the file it is meant to validate.
    """
    mask = [False] * len(lines)
    delim: str | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if delim is None:
            m = re.match(r"^(`{3,}|~{3,})", stripped)
            if m:
                delim = m.group(1)[0] * 3
                mask[i] = True
            continue
        mask[i] = True
        if re.match(r"^(`{3,}|~{3,})\s*$", stripped) and stripped.startswith(delim):
            delim = None
    return mask


def parse_registry(root: Path, rel: str) -> Registry:
    """G-CLAIM-PARSE: parse the registry under the fixed record grammar.

    Strict by construction: fixed key order, no tolerant parsing, no optional
    field except `note`.  Every deviation is a finding rather than an
    exception, because a registry this tool cannot read is exactly the state it
    must report rather than crash on.
    """
    reg = Registry(path=rel)
    text, err = read_text(root, rel)
    if text is None:
        reg.present = False
        reg.findings.append(
            Finding("G-CLAIM-PARSE", rel, 0, f"PARSE_ERROR registry is not readable: {err}")
        )
        return reg

    lines = text.split("\n")
    in_fence = _fence_mask(lines)

    # Header.  The EBNF puts `schema:` on the line after the title; the file as
    # delivered separates them with a blank line, which changes nothing about
    # the grammar's meaning, so blank lines between the two are accepted.
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines) or lines[idx].rstrip() != "# SPECTRA CLAIMS REGISTRY":
        reg.findings.append(
            Finding(
                "G-CLAIM-PARSE",
                rel,
                idx + 1,
                "PARSE_ERROR first line must be '# SPECTRA CLAIMS REGISTRY'",
            )
        )
    else:
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        m = re.match(r"^schema: (\d+)$", lines[idx].rstrip()) if idx < len(lines) else None
        if not m:
            reg.findings.append(
                Finding(
                    "G-CLAIM-PARSE",
                    rel,
                    min(idx, len(lines) - 1) + 1,
                    "PARSE_ERROR header must be followed by 'schema: <integer>'",
                )
            )
        else:
            reg.schema = int(m.group(1))

    # Records.
    for i, raw in enumerate(lines):
        if in_fence[i]:
            continue
        line = raw.rstrip()
        if not line.startswith("### "):
            continue
        heading = line[4:].strip()
        if not heading.upper().startswith("CLM"):
            continue  # '### Records', '### Record grammar' and friends.
        if not STRICT_CLAIM_ID_RE.match(heading):
            reg.findings.append(
                Finding(
                    "G-CLAIM-PARSE",
                    rel,
                    i + 1,
                    f"PARSE_ERROR malformed record heading {excerpt(line)}; "
                    "expected '### CLM-' followed by exactly four digits",
                )
            )
            continue
        if heading in reg.records:
            reg.findings.append(
                Finding(
                    "G-CLAIM-PARSE",
                    rel,
                    i + 1,
                    f"PARSE_ERROR duplicate claim id {heading} "
                    f"(first defined at line {reg.records[heading].line})",
                )
            )
            continue
        record = _parse_record(rel, heading, lines, in_fence, i, reg.findings)
        if record is not None:
            reg.records[heading] = record

    return reg


def _field_lines(lines: Sequence[str], in_fence: Sequence[bool], start: int) -> list[tuple[int, str]]:
    """The field lines of the record whose heading is at `start`."""
    out: list[tuple[int, str]] = []
    i = start + 1
    while i < len(lines):
        raw = lines[i].rstrip()
        if not raw.strip():
            break
        if not in_fence[i] and raw.startswith("#"):
            break
        out.append((i + 1, raw))
        i += 1
    return out


def _dq(value: str) -> str | None:
    m = DQSTRING_RE.match(value)
    return m.group(1) if m else None


def _parse_record(
    rel: str,
    claim_id: str,
    lines: Sequence[str],
    in_fence: Sequence[bool],
    start: int,
    findings: list[Finding],
) -> Record | None:
    """Parse one record's field block in the fixed order, or report why not."""
    block = _field_lines(lines, in_fence, start)
    pos = 0
    head_line = start + 1

    def fail(line: int, message: str) -> None:
        findings.append(
            Finding("G-CLAIM-PARSE", rel, line, one_line(f"PARSE_ERROR {claim_id}: {message}"))
        )

    def take(prefix: str) -> tuple[int, str] | None:
        nonlocal pos
        if pos >= len(block):
            fail(head_line, f"missing required field '{prefix.strip()}'")
            return None
        line_no, content = block[pos]
        if not content.startswith(prefix):
            fail(line_no, f"expected '{prefix.strip()}' here, found {excerpt(content)}")
            return None
        pos += 1
        return line_no, content[len(prefix) :]

    got = take("text: ")
    if got is None:
        return None
    text_line, text_raw = got
    text_value = _dq(text_raw)
    if text_value is None:
        fail(text_line, "'text' must be a double-quoted string")
        return None

    got = take("kind: ")
    if got is None:
        return None
    kind_line, kind = got
    if kind not in KINDS:
        fail(kind_line, f"unknown kind {excerpt(kind)}; expected one of {'|'.join(KINDS)}")
        return None

    got = take("surfaces:")
    if got is None:
        return None
    _, trailing = got
    if trailing.strip():
        fail(block[pos - 1][0], "'surfaces:' takes no value on its own line")
        return None
    surfaces: list[str] = []
    while pos < len(block) and block[pos][1].startswith("  - "):
        line_no, content = block[pos]
        value = content[4:]
        if value != value.strip() or not value:
            fail(line_no, "a surface line must be exactly '  - <surface>'")
        elif surface_form(value) is None:
            fail(line_no, f"surface {excerpt(value)} matches none of the eight surface forms")
        else:
            surfaces.append(value)
        pos += 1
    if not surfaces:
        fail(head_line, "'surfaces:' needs at least one '  - <surface>' line")
        return None

    got = take("support:")
    if got is None:
        return None
    _, trailing = got
    if trailing.strip():
        fail(block[pos - 1][0], "'support:' takes no value on its own line")
        return None
    support: dict[str, str] = {}
    for key in ("artifact", "blake3", "run", "gate", "target"):
        got = take(f"  {key}: ")
        if got is None:
            return None
        line_no, value = got
        if not value.strip():
            fail(line_no, f"support.{key} is empty")
            return None
        support[key] = value.strip()
        if key == "blake3" and not BLAKE3_RE.match(support[key]):
            fail(line_no, "support.blake3 must be exactly 64 lowercase hex characters")
            return None
        if key == "run" and support[key] == "n/a" and kind != "NEGATIVE":
            fail(line_no, "support.run may be 'n/a' only when kind is NEGATIVE")
            return None

    got = take("scope: ")
    if got is None:
        return None
    scope_line, scope_raw = got
    scope_value = _dq(scope_raw)
    if scope_value is None:
        fail(scope_line, "'scope' must be a double-quoted string")
        return None

    got = take("status: ")
    if got is None:
        return None
    status_line, status = got
    if status not in STATUSES:
        fail(status_line, f"unknown status {excerpt(status)}; expected one of {'|'.join(STATUSES)}")
        return None

    note: str | None = None
    if pos < len(block) and block[pos][1].startswith("note: "):
        note_line, note_raw = block[pos]
        note = _dq(note_raw[len("note: ") :])
        if note is None:
            fail(note_line, "'note' must be a double-quoted string")
            return None
        pos += 1

    if pos < len(block):
        line_no, content = block[pos]
        fail(line_no, f"unexpected field after the record {excerpt(content)}")
        return None

    return Record(
        claim_id=claim_id,
        line=head_line,
        text=text_value,
        kind=kind,
        surfaces=tuple(surfaces),
        artifact=support["artifact"],
        blake3=support["blake3"],
        run=support["run"],
        gate=support["gate"],
        target=support["target"],
        scope=scope_value,
        status=status,
        note=note,
    )


# --------------------------------------------------------------------------
# Segmentation (section 71.2.2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """One text unit on a surface: a sentence, list item, table cell or string."""

    path: str
    line: int
    text: str
    surface_ref: str
    anchor: str | None = None
    key: str = ""
    in_fence: bool = False
    fence_info: str = ""
    generated: bool = False

    @property
    def location(self) -> str:
        return f"{self.path}:{self.key}" if self.key else f"{self.path}:{self.line}"

    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.path, self.line, self.key, self.text)


def load_wordlist(root: Path, rel: str, fallback: Sequence[str]) -> tuple[str, ...]:
    """Read a committed wordlist if present, else use the built-in list."""
    text, err = read_text(root, rel)
    if text is None or err is not None:
        return tuple(sorted(fallback))
    words = [w.strip().lower() for w in text.split("\n") if w.strip() and not w.startswith("#")]
    return tuple(sorted(set(words))) if words else tuple(sorted(fallback))


def split_sentences(text: str, abbrevs: Sequence[str]) -> list[tuple[int, str]]:
    """Split a paragraph at `[.?!]` + whitespace/EOL, honouring abbreviations.

    Returns (offset within `text`, sentence).  A decimal point never ends a
    sentence because the terminator must be followed by whitespace or the end
    of the paragraph.
    """
    abbrev_set = {a.lower() for a in abbrevs}
    out: list[tuple[int, str]] = []
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in ".?!":
            at_end = i + 1 >= len(text)
            if at_end or text[i + 1].isspace():
                word_start = i
                while word_start > 0 and not text[word_start - 1].isspace():
                    word_start -= 1
                token = text[word_start : i + 1].lower()
                if ch == "." and token in abbrev_set:
                    i += 1
                    continue
                sentence = text[start : i + 1].strip()
                if sentence:
                    lead = len(text[start : i + 1]) - len(text[start : i + 1].lstrip())
                    out.append((start + lead, sentence))
                i += 1
                while i < len(text) and text[i].isspace():
                    i += 1
                start = i
                continue
        i += 1
    tail = text[start:].strip()
    if tail:
        lead = len(text[start:]) - len(text[start:].lstrip())
        out.append((start + lead, tail))
    return out


def _anchor_in(text: str) -> str | None:
    """The claim id named by an HTML comment, or None."""
    for comment in HTML_COMMENT_RE.findall(text):
        m = CLAIM_ID_RE.search(comment)
        if m:
            return m.group(0)
    return None


def _surface_ref_for(rel: str, heading_slug: str) -> str:
    """Derive a unit's surface reference from its path and enclosing heading.

    DECIDED: the grammar lists the surface forms but nothing says how to
    compute one from a file.  The rules here are the only ones a reader can
    predict:  a release-notes filename that is a semver is `release:<semver>`;
    `docs/cv-bullets.md` is `meta:cv_bullets`; every other markdown file is
    `<path>#<slug of the nearest preceding heading>`.
    """
    if path_matches(rel, "docs/release-notes/*.md"):
        stem = rel.rsplit("/", 1)[-1][: -len(".md")]
        if re.match(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$", stem):
            return f"release:{stem}"
    if rel.lower() == "docs/cv-bullets.md":
        return "meta:cv_bullets"
    return f"{rel}#{heading_slug}" if heading_slug else rel


def segment_markdown(rel: str, text: str, abbrevs: Sequence[str]) -> list[Unit]:
    """Markdown segmentation: sentences, list items, table cells, fence lines.

    Fenced blocks are emitted with `in_fence=True` rather than dropped: they are
    skipped for candidate detection (unless fenced `text claim`) but the
    banned-phrase scan looks at them, because moving a sentence into a fence is
    a named evasion and not a fix.
    """
    lines = text.split("\n")
    units: list[Unit] = []
    heading_slug = ""
    pending_anchor: str | None = None
    para: list[tuple[int, str]] = []
    fence_delim: str | None = None
    fence_info = ""
    generated_depth = 0
    i = 0

    def ref() -> str:
        return _surface_ref_for(rel, heading_slug)

    def flush() -> None:
        nonlocal para, pending_anchor
        if not para:
            return
        joined_parts: list[str] = []
        offsets: list[int] = []
        line_nos: list[int] = []
        cursor = 0
        for line_no, content in para:
            offsets.append(cursor)
            line_nos.append(line_no)
            joined_parts.append(content)
            cursor += len(content) + 1
        joined = " ".join(joined_parts)
        for offset, sentence in split_sentences(joined, abbrevs):
            slot = max(0, bisect_right(offsets, offset) - 1)
            units.append(
                Unit(
                    path=rel,
                    line=line_nos[slot],
                    text=sentence,
                    surface_ref=ref(),
                    anchor=pending_anchor,
                )
            )
        para = []
        pending_anchor = None

    while i < len(lines):
        raw = lines[i]
        line_no = i + 1
        stripped = raw.strip()

        if fence_delim is not None:
            if re.match(r"^(`{3,}|~{3,})\s*$", stripped) and stripped.startswith(fence_delim):
                fence_delim = None
                fence_info = ""
            elif stripped:
                units.append(
                    Unit(
                        path=rel,
                        line=line_no,
                        text=raw,
                        surface_ref=ref(),
                        anchor=pending_anchor,
                        in_fence=True,
                        fence_info=fence_info,
                    )
                )
            i += 1
            continue

        fence_open = re.match(r"^(`{3,}|~{3,})\s*(.*)$", stripped)
        if fence_open:
            flush()
            fence_delim = fence_open.group(1)[0] * 3
            fence_info = fence_open.group(2).strip()
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        # HTML comments: anchors and TODO notes.  Never units.
        if stripped.startswith("<!--"):
            flush()
            block = [raw]
            j = i
            while "-->" not in lines[j] and j + 1 < len(lines):
                j += 1
                block.append(lines[j])
            joined = "\n".join(block)
            found = _anchor_in(joined)
            if found:
                pending_anchor = found
            # A generated block's contents are rendered from an artifact, so its
            # numerals are the one kind the registry does not ask anybody to
            # anchor: G-LIMITS-NOHAND exists to push numbers INTO these blocks.
            if GENERATED_BEGIN_RE.search(joined):
                generated_depth += 1
            elif GENERATED_END_RE.search(joined):
                generated_depth = max(0, generated_depth - 1)
            i = j + 1
            continue

        inline_anchor = _anchor_in(raw)
        if inline_anchor:
            pending_anchor = inline_anchor
        content = HTML_COMMENT_RE.sub("", raw).rstrip()
        if not content.strip():
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", content.strip())
        if heading:
            flush()
            title = heading.group(2).strip()
            heading_slug = slugify(title)
            units.append(
                Unit(
                    path=rel,
                    line=line_no,
                    text=title,
                    surface_ref=_surface_ref_for(rel, heading_slug),
                    anchor=pending_anchor,
                )
            )
            pending_anchor = None
            i += 1
            continue

        body = content.strip()
        if body.startswith(">"):
            body = re.sub(r"^>\s?", "", body)

        if re.match(r"^\|.*\|$", body):
            flush()
            if not re.match(r"^\|[\s:\-|]+\|$", body):
                for cell in [c.strip() for c in body.strip("|").split("|")]:
                    if cell:
                        units.append(
                            Unit(
                                path=rel,
                                line=line_no,
                                text=cell,
                                surface_ref=ref(),
                                anchor=pending_anchor,
                            )
                        )
            pending_anchor = None
            i += 1
            continue

        item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", content)
        if item:
            flush()
            parts = [item.group(1).strip()]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", nxt):
                    break
                if re.match(r"^(#{1,6})\s+", nxt.strip()) or re.match(r"^(`{3,}|~{3,})", nxt.strip()):
                    break
                parts.append(nxt.strip())
                j += 1
            units.append(
                Unit(
                    path=rel,
                    line=line_no,
                    text=" ".join(p for p in parts if p),
                    surface_ref=ref(),
                    anchor=pending_anchor,
                )
            )
            pending_anchor = None
            i = j
            continue

        para.append((line_no, body))
        i += 1

    flush()
    return units


def segment_lines(rel: str, text: str, surface_prefix: str) -> list[Unit]:
    """One unit per non-empty line: the demo transcript and the commit template.

    The transcript's `[CLM-0007]` prefix is the anchor and is stripped from the
    unit text, exactly as the recorder strips it before display.
    """
    units: list[Unit] = []
    for i, raw in enumerate(text.split("\n")):
        line = raw.rstrip()
        if not line.strip():
            continue
        anchor = None
        body = line
        m = re.match(r"^\s*\[(CLM-\d{4})\]\s*(.*)$", line)
        if m:
            anchor, body = m.group(1), m.group(2)
        if not body.strip():
            continue
        tag = body.split(":", 1)[0].strip() if ":" in body else ""
        if surface_prefix == "demo":
            ref = f"demo:{slugify(tag)}" if tag else f"demo:{anchor or 'untagged'}"
        else:
            ref = rel
        units.append(Unit(path=rel, line=i + 1, text=body.strip(), surface_ref=ref, anchor=anchor))
    return units


def _walk_catalog(
    node: object,
    prefix: str,
    inherited: str | None,
    out: list[tuple[str, str, str | None]],
) -> None:
    """Collect (dotted key, string value, anchor) from a nested string catalog."""
    if isinstance(node, dict):
        raw_claim = node.get("claim")
        anchor = inherited
        if isinstance(raw_claim, str) and STRICT_CLAIM_ID_RE.match(raw_claim):
            anchor = raw_claim
        for key in sorted(node):
            if key == "claim":
                continue
            child = f"{prefix}.{key}" if prefix else key
            _walk_catalog(node[key], child, anchor, out)
        return
    if isinstance(node, list):
        for index, item in enumerate(node):
            _walk_catalog(item, f"{prefix}.{index}", inherited, out)
        return
    if isinstance(node, str):
        out.append((prefix, node, inherited))


def segment_catalog(rel: str, data: object, surface_prefix: str) -> list[Unit]:
    """A UI or CLI string catalog: one unit per string value, keyed by its path."""
    collected: list[tuple[str, str, str | None]] = []
    _walk_catalog(data, "", None, collected)
    units: list[Unit] = []
    for key, value, anchor in sorted(collected):
        if not value.strip():
            continue
        if surface_prefix == "meta":
            top = key.split(".", 1)[0]
            ref = f"meta:{top}" if top in {"github_about", "github_topics", "cv_bullets"} else rel
        else:
            ref = f"{surface_prefix}:{key}"
        units.append(Unit(path=rel, line=0, text=value, surface_ref=ref, anchor=anchor, key=key))
    return units


_TEX_CLAIM_RE = re.compile(r"\\claim\{(CLM-\d{4})\}\{(.*?)\}", re.DOTALL)
_TEX_ENV_RE = re.compile(
    r"\\begin\{(abstract|intro|eval|concl)\}(.*?)\\end\{\1\}", re.DOTALL
)


def segment_tex(rel: str, text: str, abbrevs: Sequence[str]) -> list[Unit]:
    """A `.tex` surface: `\\claim{}{}` arguments and the four named environments.

    paper/ does not exist in this tree, so this path is unexercised until the
    paper lands.  It is implemented rather than stubbed so that the day the
    directory appears the gate already covers it.
    """
    units: list[Unit] = []
    for m in _TEX_CLAIM_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        units.append(
            Unit(
                path=rel,
                line=line,
                text=m.group(2).strip(),
                surface_ref=f"paper:{_tex_env_at(text, m.start()) or 'intro'}",
                anchor=m.group(1),
            )
        )
    for env in _TEX_ENV_RE.finditer(text):
        base = text.count("\n", 0, env.start(2)) + 1
        body = _TEX_CLAIM_RE.sub(" ", env.group(2))
        for offset, sentence in split_sentences(one_line(body), abbrevs):
            del offset
            units.append(
                Unit(
                    path=rel,
                    line=base,
                    text=sentence,
                    surface_ref=f"paper:{env.group(1)}",
                )
            )
    return units


def _tex_env_at(text: str, pos: int) -> str | None:
    for env in _TEX_ENV_RE.finditer(text):
        if env.start() <= pos <= env.end():
            return env.group(1)
    return None


# --------------------------------------------------------------------------
# Candidate detection (section 71.2.3)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidacy:
    """Why a unit is a claim candidate, or that it is not one."""

    is_candidate: bool
    reason: str = ""
    evidence: str = ""


def candidacy(unit: Unit, verbs: Sequence[str]) -> Candidacy:
    """Decide whether a text unit is a CLAIM CANDIDATE.

    Precision note: the NUMERAL test runs over the text with the non-claim
    token classes removed, so a version number, a git sha, a section number, a
    file path and a registry id are not measurements.  Everything that survives
    that filter and still looks like a digit is treated as a number a reader
    would take as a result - which is the intended bias.
    """
    text = unit.text
    stripped = strip_non_claim_tokens(text)
    m = NUMERAL_RE.search(stripped)
    if m and m.group(0).strip():
        return Candidacy(True, "NUMERAL", m.group(0).strip())

    lowered = " " + re.sub(r"[^\w\-]+", " ", text.lower()) + " "
    for verb in verbs:
        if f" {verb} " in lowered:
            return Candidacy(True, "CAPABILITY_VERB", verb)

    flat = text.lower()
    for token in COMPARATIVE_TOKENS:
        if " " in token:
            if token in flat:
                return Candidacy(True, "COMPARATIVE", token)
        elif f" {token} " in lowered:
            return Candidacy(True, "COMPARATIVE", token)

    return Candidacy(False)


# --------------------------------------------------------------------------
# The run context
# --------------------------------------------------------------------------


@dataclass
class Context:
    """Everything the checks read.  Built once, never mutated by a check."""

    root: Path
    registry: Registry
    units: list[Unit]
    candidates: list[Unit]
    surfaces: list[str]
    missing_surfaces: list[str]
    unreadable: list[Finding]
    verbs: tuple[str, ...]
    abbrevs: tuple[str, ...]
    tier: str
    warnings: list[Finding] = field(default_factory=list)
    dynamic_skips: list[Skip] = field(default_factory=list)
    matched_surface_ids: set[str] = field(default_factory=set)

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def warn(self, finding: Finding) -> None:
        """Record a warning, or promote it to a finding outside tier T1.

        Section 71.3 makes MISSING_ARTIFACT `warn` per-PR and FAIL nightly and
        release, while the pseudocode has no warning channel at all.  The tier
        is the missing input, so it is an explicit option with T1 as default.

        The finding is stamped `severity="warn"` rather than being hidden: it
        is still returned by `run_checks`, it is still in the report, and it
        simply does not move the exit code at T1.
        """
        self.warnings.append(dataclasses.replace(finding, severity="warn"))

    def skip(self, check: str, reason: str) -> None:
        self.dynamic_skips.append(Skip(check, one_line(reason)))


def build_context(root: Path, tier: str) -> Context:
    """Resolve surfaces, segment every one of them, and parse the registry."""
    verbs = load_wordlist(root, VERBS_FILE, CAPABILITY_VERBS)
    abbrevs = load_wordlist(root, ABBREV_FILE, ABBREVIATIONS)

    all_files = list(iter_repo_files(root))
    surfaces: list[str] = []
    missing: list[str] = []
    for glob in SURFACE_GLOBS:
        hits = [f for f in all_files if path_matches(f, glob)]
        if not hits:
            missing.append(glob)
        surfaces.extend(hits)
    surfaces = sorted(set(surfaces))

    units: list[Unit] = []
    unreadable: list[Finding] = []
    for rel in surfaces:
        units.extend(_segment_surface(root, rel, abbrevs, unreadable))
    units.sort(key=Unit.sort_key)

    registry_path = find_registry(root)
    registry = parse_registry(root, registry_path)

    # A fenced block is skipped unless it is the demo transcript or is fenced
    # `text claim`.  A generated block is skipped outright: its contents are
    # rendered from an artifact, which is the opposite of an unbacked claim.
    candidates = [
        u
        for u in units
        if not u.in_fence or u.fence_info == "text claim" or _is_transcript(u.path)
    ]
    candidates = [c for c in candidates if not c.generated]
    candidates = [c for c in candidates if not under_any(c.path, NO_CANDIDATE_PATHS)]
    # An anchor is an explicit declaration that the unit is a claim, so an
    # anchored unit is a candidate whether or not the numeral / verb /
    # comparative test fires.  Without this a FRAMING record - a sentence with
    # no number and no capability verb - could be registered and anchored and
    # would still be reported ORPHAN, which would make the gate unlandable for
    # exactly the claims it most wants stated carefully.
    candidates = [c for c in candidates if c.anchor is not None or candidacy(c, verbs).is_candidate]

    return Context(
        root=root,
        registry=registry,
        units=units,
        candidates=candidates,
        surfaces=surfaces,
        missing_surfaces=missing,
        unreadable=unreadable,
        verbs=verbs,
        abbrevs=abbrevs,
        tier=tier,
    )


def _is_transcript(rel: str) -> bool:
    return rel.lower() == "demo/transcript.expected.txt"


def _segment_surface(
    root: Path, rel: str, abbrevs: Sequence[str], unreadable: list[Finding]
) -> list[Unit]:
    """Segment one surface, reporting rather than raising on unreadable input."""
    low = rel.lower()
    if low.endswith(".json"):
        text, err = read_text(root, rel)
        if text is None:
            unreadable.append(Finding("G-CLAIM-PARSE", rel, 0, f"SURFACE_UNREADABLE {err}"))
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            unreadable.append(
                Finding(
                    "G-CLAIM-PARSE",
                    rel,
                    max(exc.lineno, 0),
                    f"SURFACE_UNREADABLE not valid JSON: {one_line(exc.msg)}",
                )
            )
            return []
        return segment_catalog(rel, data, "ui")

    if low.endswith(".toml"):
        try:
            with (root / rel).open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            unreadable.append(
                Finding("G-CLAIM-PARSE", rel, 0, f"SURFACE_UNREADABLE not valid TOML: {one_line(str(exc))}")
            )
            return []
        prefix = "meta" if low == "docs/repo-metadata.toml" else "cli"
        return segment_catalog(rel, data, prefix)

    text, err = read_text(root, rel)
    if text is None:
        unreadable.append(Finding("G-CLAIM-PARSE", rel, 0, f"SURFACE_UNREADABLE {err}"))
        return []

    if low.endswith(".tex"):
        return segment_tex(rel, text, abbrevs)
    if _is_transcript(rel):
        return segment_lines(rel, text, "demo")
    if low.endswith(".txt"):
        return segment_lines(rel, text, "text")
    return segment_markdown(rel, text, abbrevs)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check_parse(ctx: Context) -> list[Finding]:
    """G-CLAIM-PARSE: the registry parses under the fixed record grammar, and
    every record's scope clause satisfies section 71.1.2's lint."""
    findings: list[Finding] = list(ctx.registry.findings)
    findings.extend(ctx.unreadable)

    banned = [(p, p.regexes()) for p in BANNED_PATTERNS]
    for claim_id in sorted(ctx.registry.records):
        rec = ctx.registry.records[claim_id]
        scope = rec.scope
        words = [w for w in re.split(r"\s+", scope.strip()) if w]
        if not words:
            findings.append(
                Finding(
                    "G-CLAIM-PARSE", ctx.registry.path, rec.line, f"SCOPE_INVALID {claim_id}: scope is empty"
                )
            )
            continue
        if len(words) < SCOPE_MIN_WORDS:
            findings.append(
                Finding(
                    "G-CLAIM-PARSE",
                    ctx.registry.path,
                    rec.line,
                    f"SCOPE_INVALID {claim_id}: scope has {len(words)} words, "
                    f"the minimum is {SCOPE_MIN_WORDS}",
                )
            )
        low = scope.lower()
        for forbidden in SCOPE_FORBIDDEN:
            if forbidden in low:
                findings.append(
                    Finding(
                        "G-CLAIM-PARSE",
                        ctx.registry.path,
                        rec.line,
                        f"SCOPE_INVALID {claim_id}: scope contains the forbidden string "
                        f'"{forbidden}"',
                    )
                )
        for pattern, regexes in banned:
            for rx in regexes:
                if rx.search(scope) and _requires_ok(pattern, scope):
                    findings.append(
                        Finding(
                            "G-CLAIM-PARSE",
                            ctx.registry.path,
                            rec.line,
                            f"SCOPE_INVALID {claim_id}: scope matches banned pattern {pattern.id}",
                        )
                    )
                    break

    # The scope clause must also "name the rule table, the control catalog and
    # the evidence regime".  That is a semantic requirement with no mechanical
    # test in either document, so it is reported as an uncovered obligation
    # rather than guessed at with a keyword list that any wording would evade.
    ctx.skip(
        "G-CLAIM-PARSE",
        "scope clauses are not checked for naming the rule table, the control catalog "
        "and the evidence regime: the requirement is stated in prose and neither "
        "CLAIMS.md nor section 71.1.2 gives it a mechanical form",
    )
    return findings


def _requires_ok(pattern: BannedPattern, text: str) -> bool:
    if not pattern.requires:
        return True
    low = text.lower()
    return any(req.lower() in low for req in pattern.requires)


def check_banned(ctx: Context) -> list[Finding]:
    """G-CLAIM-BANNED: no text unit matches a banned pattern outside its exempt
    path.  Unwaivable, independent of registration, and not fence-skipped."""
    findings: list[Finding] = []
    compiled = [(p, p.regexes()) for p in BANNED_PATTERNS]
    for unit in ctx.units:
        if under_any(unit.path, EXEMPT_PATHS):
            continue
        spans: list[tuple[int, int]] | None = None
        for pattern, regexes in compiled:
            if pattern.only_paths and not under_any(unit.path, pattern.only_paths):
                continue
            if pattern.not_paths and under_any(unit.path, pattern.not_paths):
                continue
            if not _requires_ok(pattern, unit.text):
                continue
            hit = None
            for rx in regexes:
                # Every occurrence is examined, not only the first.  A unit that
                # quotes the phrase and then also asserts it must still fail, and
                # `search` would stop at the quotation and call the unit clean.
                for candidate in rx.finditer(unit.text):
                    if pattern.use_only:
                        if spans is None:
                            spans = quoted_spans(unit.text)
                        if is_mention(unit.text, candidate.start(), candidate.end(), spans):
                            continue
                    hit = candidate
                    break
                if hit is not None:
                    break
            if hit is None:
                continue
            findings.append(
                Finding(
                    "G-CLAIM-BANNED",
                    unit.path,
                    unit.line,
                    one_line(
                        f"BANNED {pattern.id} {excerpt(hit.group(0), 40)} in "
                        f"{excerpt(unit.text)} | replace with: {pattern.replacement} | "
                        "(this finding is unwaivable)"
                    ),
                )
            )

    findings.extend(_check_banned_table_file(ctx))
    if any(p.use_only for p in BANNED_PATTERNS):
        ctx.skip(
            "G-CLAIM-BANNED/USE-MENTION",
            "narrowed: a row fires on a phrase the unit asserts, not on one it "
            "quotes, writes inside backticks, or forbids.  A prohibition marker "
            "counts only where it starts before the match, so 'SPECTRA is "
            "production-ready, and we do not claim otherwise' still fails; a unit "
            "that opens with an unrelated prohibition and then makes the claim "
            "does not, and that is the gap this narrowing buys",
        )
    for pattern in BANNED_PATTERNS:
        if pattern.narrowed:
            ctx.skip(
                f"G-CLAIM-BANNED/{pattern.id}",
                f"narrowed: {pattern.narrowed}",
            )
    return findings


def _check_banned_table_file(ctx: Context) -> list[Finding]:
    """Account for `docs/banned.toml`, which 71.4 makes the normative list.

    The seventeen patterns this tool enforces are hand-authored above, for the
    reason given there.  That is a fork of a file the specification calls
    normative, so its state is reported rather than assumed:

      * absent  -> a skip naming the built-in table as what actually ran;
      * present but unparseable -> a PARSE_ERROR finding.  The normative list
        being unreadable is not a detail to swallow: whoever edited it believes
        they changed the gate, and they did not;
      * present and parseable -> a skip saying so, because the file is read for
        its shape here and is still not the list that was enforced.

    DECIDED: an earlier shape skipped only the absent case and said nothing at
    all once the file existed, so the moment the normative list appeared the
    tool went quiet about ignoring it.  A check that silently does nothing is
    the defect this tool exists to catch.
    """
    rel = BANNED_TOML_PATH
    if not (ctx.root / rel).is_file():
        ctx.skip(
            "G-CLAIM-BANNED",
            f"{rel} does not exist; the seventeen patterns are read from the "
            "table built into tools/claims_check.py, which is the same list CLAIMS.md "
            "declares but is not the machine-readable file the gate is specified to read",
        )
        return []
    text, err = read_text(ctx.root, rel)
    if text is None:
        return [
            Finding(
                "G-CLAIM-BANNED",
                rel,
                0,
                one_line(
                    f"PARSE_ERROR {rel} is the normative banned list and cannot be read: {err} | "
                    "the patterns enforced on this run are the table built into "
                    "tools/claims_check.py"
                ),
            )
        ]
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [
            Finding(
                "G-CLAIM-BANNED",
                rel,
                0,
                one_line(
                    f"PARSE_ERROR {rel} is the normative banned list and is not valid TOML: "
                    f"{exc} | the patterns enforced on this run are the table built into "
                    "tools/claims_check.py, so an edit to this file changed nothing"
                ),
            )
        ]
    ctx.skip(
        "G-CLAIM-BANNED",
        f"{rel} exists and parses, but the patterns enforced on this run are still the table "
        "built into tools/claims_check.py; the two are not compared",
    )
    return []


def check_anchor(ctx: Context) -> list[Finding]:
    """G-CLAIM-ANCHOR: every claim candidate carries a CLM- anchor."""
    allow = load_nonclaims(ctx)
    findings: list[Finding] = []
    for unit in ctx.candidates:
        if unit.anchor is not None:
            continue
        if allow.covers(unit):
            continue
        why = candidacy(unit, ctx.verbs)
        findings.append(
            Finding(
                "G-CLAIM-ANCHOR",
                unit.path,
                unit.line,
                one_line(
                    f"UNANCHORED {why.reason} {excerpt(why.evidence, 30)} in "
                    f"{excerpt(unit.text)} | fix: add <!-- CLM-#### --> and a record in "
                    f"{ctx.registry.path}, or state nothing"
                ),
            )
        )
    return findings


def check_registered(ctx: Context) -> list[Finding]:
    """G-CLAIM-REGISTERED: an anchored candidate resolves to a record with
    byte-identical text on a declared surface, and no record is an orphan."""
    findings: list[Finding] = []
    matched: set[str] = set()
    records = ctx.registry.records

    for unit in ctx.candidates:
        cid = unit.anchor
        if cid is None:
            continue
        rec = records.get(cid)
        if rec is None:
            findings.append(
                Finding(
                    "G-CLAIM-REGISTERED",
                    unit.path,
                    unit.line,
                    one_line(
                        f"UNREGISTERED {cid} has no record in {ctx.registry.path} | "
                        f"sentence: {excerpt(unit.text)}"
                    ),
                )
            )
            continue
        if normalise(rec.text) != normalise(unit.text):
            findings.append(
                Finding(
                    "G-CLAIM-REGISTERED",
                    unit.path,
                    unit.line,
                    one_line(
                        f"TEXT_DRIFT {cid} | {_inline_diff(rec.text, unit.text)}"
                    ),
                )
            )
            continue
        matched.add(cid)
        if not any(surface_declared(unit.surface_ref, s) for s in rec.surfaces):
            findings.append(
                Finding(
                    "G-CLAIM-REGISTERED",
                    unit.path,
                    unit.line,
                    one_line(
                        f"SURFACE_UNDECLARED {cid} appears in {surface_file(unit.surface_ref)}, "
                        f"which the record does not list (declared: {', '.join(rec.surfaces)})"
                    ),
                )
            )
            continue
        if rec.status == "TUNED" and is_headline(unit.surface_ref):
            findings.append(
                Finding(
                    "G-CLAIM-REGISTERED",
                    unit.path,
                    unit.line,
                    one_line(
                        f"TUNED_ON_HEADLINE {cid} has status TUNED and appears on the "
                        f"headline surface {unit.surface_ref}; headline surfaces accept "
                        "GREEN and HELD_OUT only"
                    ),
                )
            )

    ctx.matched_surface_ids = matched
    if any("#" in s for rec in records.values() for s in rec.surfaces):
        ctx.skip(
            "G-CLAIM-REGISTERED",
            "the `#anchor` half of a path surface is checked for grammar only, not resolved "
            "to a location in the document: see surface_declared()",
        )
    for cid in sorted(records):
        if cid not in matched:
            rec = records[cid]
            findings.append(
                Finding(
                    "G-CLAIM-REGISTERED",
                    ctx.registry.path,
                    rec.line,
                    one_line(
                        f"ORPHAN {cid} is registered but matched no surface occurrence; "
                        "you may not register a claim you do not make"
                    ),
                )
            )
    return findings


def _inline_diff(registered: str, surface: str) -> str:
    """A unified diff flattened onto one line, for a `Finding.message`."""
    diff = difflib.unified_diff(
        [normalise(registered)],
        [normalise(surface)],
        fromfile="registered",
        tofile="surface",
        lineterm="",
        n=0,
    )
    body = " / ".join(one_line(d) for d in diff if not d.startswith("@@"))
    return body or f"registered {excerpt(registered)} != surface {excerpt(surface)}"


def surface_file(surface_ref: str) -> str:
    """The file half of a path surface; the whole reference for a keyed one.

    `README.md#verification` -> `README.md`; `paper:abstract` -> `paper:abstract`.
    A keyed surface (`ui:`, `cli:`, `demo:`, `paper:`, `release:`, `meta:`) has
    no file half, and its key is its whole identity.
    """
    head = surface_ref.split("#", 1)[0]
    return surface_ref if ":" in head else head


def surface_declared(unit_ref: str, declared: str) -> bool:
    """Does `declared` (a record surface) cover a unit seen at `unit_ref`?

    DECIDED (granularity): a PATH surface matches on the FILE, not on the
    `#anchor` fragment.  The grammar fixes the written form `README.md#anchor`,
    but neither 71.1 nor 71.2 says how to compute an anchor from a document,
    and markdown heading slugs are renderer-specific.  Enforcing this tool's
    own invented slug derivation as a hard failure means a correctly anchored,
    byte-identical, correctly registered claim is reported SURFACE_UNDECLARED
    because someone reworded a heading - a false positive on a clean registry,
    which is how a gate gets switched off.  Matching on the file still catches
    what the rule is for: the claim turning up in a document the record never
    declared.  The fragment is validated for grammar by the registry parser and
    the residual gap is declared as a skip, not left silent.

    A KEYED surface (`ui:`, `cli:`, `demo:`, `paper:`, `release:`, `meta:`) is
    matched exactly: its key is an identity, not a location, and nothing about
    it is renderer-derived.
    """
    if unit_ref == declared:
        return True
    unit_file = surface_file(unit_ref)
    declared_file = surface_file(declared)
    if ":" in unit_file or ":" in declared_file:
        return False
    return unit_file == declared_file


def is_headline(surface_ref: str) -> bool:
    """True when a surface reference is a headline surface (71.1.1 item 3)."""
    return any(
        path_matches(surface_ref, pat) or path_matches(surface_file(surface_ref), surface_file(pat))
        for pat in HEADLINE_SURFACE_PATTERNS
    )


def check_support(ctx: Context) -> list[Finding]:
    """G-CLAIM-SUPPORT: the record side of section 71.3's six conditions.

    Conditions 1 to 6 need `artifacts/runs/`, `artifacts/ci/gates.json` and a
    working-tree hash producer, none of which exists.  What can be decided from
    the record alone is decided here; everything else resolves to
    MISSING_ARTIFACT or NOT_MEASURED and is reported, never assumed FRESH.
    """
    findings: list[Finding] = []
    for cid in sorted(ctx.registry.records):
        rec = ctx.registry.records[cid]
        state, detail = support_state(ctx, rec)
        if state == "FRESH":
            continue
        finding = Finding(
            "G-CLAIM-SUPPORT",
            ctx.registry.path,
            rec.line,
            one_line(f"STALE {state} {cid}: {detail}"),
        )
        # MISSING_ARTIFACT is the one state section 71.3 does not fail at every
        # tier: warn per-PR, FAIL nightly and release.  NOT_MEASURED is this
        # checker's own state, and it means "the resolver cannot decide", not
        # "the claim is unsupported".  Raising it as a failure would mean the
        # first record ever registered turns the tree permanently red, which is
        # how a gate gets switched off; it is a warning here and a failure at
        # t2/t3, where an undecidable support state must block.
        if state in {"MISSING_ARTIFACT", "NOT_MEASURED"} and ctx.tier == "t1":
            ctx.warn(finding)
        else:
            findings.append(finding)

    ctx.skip(
        "G-CLAIM-SUPPORT",
        "conditions 2-5 (run manifest resolution, working-tree input hashes, "
        "soundness flags and the green-gate ledger) are not evaluated: artifacts/runs/, "
        "artifacts/ci/gates.json and a producer for rules_hash/controls_hash/"
        "axioms_hash/er_config_hash do not exist in this tree",
    )
    ctx.skip(
        "G-CLAIM-SUPPORT",
        "condition 1 is shape-checked only: support.blake3 is validated as 64 hex and "
        "never recomputed, because BLAKE3 is not in the Python standard library and this "
        "tool takes no dependency and shells out to nothing",
    )
    return findings


def support_state(ctx: Context, rec: Record) -> tuple[str, str]:
    """Section 71.3's state machine, as far as this tree can evaluate it."""
    if not ctx.exists(rec.artifact):
        return "MISSING_ARTIFACT", f"support.artifact {rec.artifact} does not exist"
    if not ctx.exists("artifacts/runs"):
        return "NOT_MEASURED", "artifacts/runs/ does not exist, so support.run cannot resolve"
    if rec.run != "n/a" and not ctx.exists(f"artifacts/runs/{rec.run}.json"):
        return "NOT_MEASURED", f"artifacts/runs/{rec.run}.json does not exist"
    if not ctx.exists("artifacts/ci/gates.json"):
        return "NOT_MEASURED", "artifacts/ci/gates.json does not exist, so support.gate is unproven"
    return "NOT_MEASURED", "the support resolver is not implemented; see the skipped checks"


NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_.])\d[\d,_]*(?:\.\d+)?")


def _numeric_tokens(text: str) -> list[str]:
    """Every numeral in `text`, normalised for comparison.

    Digit-group separators are dropped and a trailing fractional zero run is
    trimmed, so `1,024`, `1024` and `1024.0` compare equal.  Nothing else is
    normalised: a rounding relation between two different numbers is exactly
    what 71.3 condition 6 refuses to assume.
    """
    out: list[str] = []
    for raw in NUMBER_TOKEN_RE.findall(text):
        token = raw.replace(",", "").replace("_", "")
        if "." in token:
            token = token.rstrip("0").rstrip(".")
        out.append(token or "0")
    return out


def check_numsrc(ctx: Context) -> list[Finding]:
    """G-CLAIM-NUMSRC: every numeral in a QUANT claim occurs in its artifact.

    Section 71.3 condition 6.  This runs for every QUANT record whose
    `support.artifact` exists and decodes as text: the numerals of `text` are
    compared, as normalised tokens, against the numerals the artifact contains.

    DECIDED: an earlier shape of this check returned nothing at all and
    declared one blanket skip, on the grounds that "no support artifact exists
    anywhere in this tree".  That is a property of today's tree, not of the
    check, and a gate that reports nothing the moment its input DOES appear is
    the exact defect this tool exists to catch.  The parts that genuinely
    cannot be decided are skipped per record, with the record named:

      * an artifact that does not exist (that state is G-CLAIM-SUPPORT's
        MISSING_ARTIFACT, and reporting it twice would double-count it);
      * an artifact that is not UTF-8 text, which this tool will not parse;
      * a record carrying a `note`, because `note` is where 71.3 puts the
        rounding rule the linter is meant to re-apply and no syntax for it is
        ever given.  Re-applying an unparseable rule is guessing; ignoring it
        would report a correctly rounded number as a fabrication.
    """
    findings: list[Finding] = []
    for cid in sorted(ctx.registry.records):
        rec = ctx.registry.records[cid]
        if rec.kind != "QUANT":
            continue
        if not ctx.exists(rec.artifact):
            ctx.skip(
                "G-CLAIM-NUMSRC",
                f"{cid} is unchecked: support.artifact {rec.artifact} does not exist "
                "(reported by G-CLAIM-SUPPORT as MISSING_ARTIFACT)",
            )
            continue
        if rec.note:
            ctx.skip(
                "G-CLAIM-NUMSRC",
                f"{cid} is unchecked: it carries a `note`, which is where 71.3 puts the "
                "rounding rule the linter must re-apply, and the rule's syntax is unspecified",
            )
            continue
        artifact_text, err = read_text(ctx.root, rec.artifact)
        if artifact_text is None:
            ctx.skip(
                "G-CLAIM-NUMSRC",
                f"{cid} is unchecked: support.artifact {rec.artifact} is not readable text "
                f"({err})",
            )
            continue
        present = set(_numeric_tokens(artifact_text))
        claimed = _numeric_tokens(strip_non_claim_tokens(normalise(rec.text)))
        for token in claimed:
            if token in present:
                continue
            findings.append(
                Finding(
                    "G-CLAIM-NUMSRC",
                    ctx.registry.path,
                    rec.line,
                    one_line(
                        f"NUMBER_NOT_IN_ARTIFACT {cid} states {token}, which does not occur in "
                        f"support.artifact {rec.artifact} | a number in prose that is not in its "
                        "artifact is a fabrication"
                    ),
                )
            )
    return findings


def check_allowcap(ctx: Context) -> list[Finding]:
    """G-CLAIM-ALLOWCAP: the non-claim allowlist is under its declared cap and
    every entry carries a real reason on a permitted surface."""
    allow = load_nonclaims(ctx)
    return allow.findings


def check_noerase(ctx: Context) -> list[Finding]:
    """G-CLAIM-NOERASE: a claim id that existed in an earlier commit of the
    registry is still present today, live or RETIRED."""
    findings: list[Finding] = []
    root = ctx.root
    if not (root / ".git").exists():
        ctx.skip("G-CLAIM-NOERASE", "not a git checkout, so the registry's history cannot be walked")
        return findings
    if _git(root, "rev-parse", "--is-shallow-repository") == "true":
        ctx.skip(
            "G-CLAIM-NOERASE",
            "shallow clone: earlier commits of the registry are absent, so an erased id "
            "cannot be distinguished from one that was never there",
        )
        return findings

    # --follow keeps the walk correct across the CLAIMS.md -> docs/claims.md
    # rename the registry file's own TODO contemplates.  Without it every id
    # would read as erased on the rename commit.
    log = _git(root, "log", "--follow", "--format=%H", "--", ctx.registry.path)
    if log is None:
        ctx.skip("G-CLAIM-NOERASE", "git log over the registry path failed; history not walked")
        return findings

    historical: dict[str, str] = {}
    ever_retired: set[str] = set()
    for sha in [s for s in log.split("\n") if s.strip()]:
        blob = _git(root, "show", f"{sha}:{ctx.registry.path}")
        if blob is None:
            continue
        for cid, status in _historical_records(blob).items():
            historical.setdefault(cid, sha)
            if status == "RETIRED":
                ever_retired.add(cid)

    for cid in sorted(historical):
        rec = ctx.registry.records.get(cid)
        if rec is None:
            findings.append(
                Finding(
                    "G-CLAIM-NOERASE",
                    ctx.registry.path,
                    0,
                    one_line(
                        f"ID_ERASED {cid} was present in commit {historical[cid][:12]} and is "
                        "absent from the registry today; retire it, do not delete it"
                    ),
                )
            )
            continue
        if cid in ever_retired and rec.status != "RETIRED":
            findings.append(
                Finding(
                    "G-CLAIM-NOERASE",
                    ctx.registry.path,
                    rec.line,
                    one_line(
                        f"ID_REUSED {cid} was RETIRED in an earlier commit and is live again "
                        f"with status {rec.status}; claim ids are never reused after retirement"
                    ),
                )
            )
            continue
    return findings


def _historical_records(blob: str) -> dict[str, str]:
    """Claim id -> status, read from an earlier revision of the registry file.

    A deliberately loose read: an old revision may predate the current grammar,
    and the question asked of history is only "did this id exist, and was it
    retired", not "did that revision parse".
    """
    out: dict[str, str] = {}
    lines = blob.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    mask = _fence_mask(lines)
    current: str | None = None
    for i, raw in enumerate(lines):
        if mask[i]:
            continue
        line = raw.rstrip()
        m = re.match(r"^### (CLM-\d{4})\s*$", line)
        if m:
            current = m.group(1)
            out.setdefault(current, "")
            continue
        if current and line.startswith("status: "):
            out[current] = line[len("status: ") :].strip()
            current = None
        elif line.startswith("#") or not line.strip():
            current = None if line.startswith("#") else current
    return out


def _git(root: Path, *args: str) -> str | None:
    """Run git read-only and return stdout, or None when it cannot be run."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def check_placeholder(ctx: Context) -> list[Finding]:
    """G-CLAIM-PLACEHOLDER: the illustrative tag and any <<MEASURED:*>> token
    appear only inside docs/prompt/."""
    findings: list[Finding] = []
    compiled = [(name, re.compile(pat)) for name, pat in PLACEHOLDER_TOKENS]
    # DECIDED (scope): the scan is the fifteen surface globs, not the whole
    # tree.  Section 71.7 item 2's broader wording would make the gate fail on
    # ci/gates.toml's 196 "# illustrative, not a target" budget comments, which
    # are the gate registry honestly labelling its own unmeasured numbers - the
    # behaviour the tag exists to produce.  A gate that fights the honest
    # labelling it mandates is a gate that gets switched off.
    for rel in ctx.surfaces:
        if under_any(rel, ("docs/prompt/",)):
            continue
        text, err = read_text(ctx.root, rel)
        if text is None:
            del err  # already reported as SURFACE_UNREADABLE by the parse check
            continue
        # Scanned over the whole file rather than line by line, so that a tag
        # wrapped across two source lines is still caught.
        for name, rx in compiled:
            for hit in rx.finditer(text):
                line_no = text.count("\n", 0, hit.start()) + 1
                line = text.split("\n")[line_no - 1]
                findings.append(
                    Finding(
                        "G-CLAIM-PLACEHOLDER",
                        rel,
                        line_no,
                        one_line(
                            f"PLACEHOLDER_ESCAPED {name} {excerpt(hit.group(0), 40)} "
                            f"outside docs/prompt/ in {excerpt(line)}"
                        ),
                    )
                )
    ctx.skip(
        "G-CLAIM-PLACEHOLDER",
        "the scan covers the fifteen surface globs only; source, ci/ and other "
        "non-surface files are not scanned, so a tagged number reaching them is not caught",
    )
    return findings


def check_limits_nohand(ctx: Context) -> list[Finding]:
    """G-LIMITS-NOHAND: every numeral in LIMITATIONS.md sits inside a
    BEGIN/END GENERATED block.  Unwaivable."""
    findings: list[Finding] = []
    rel = LIMITATIONS_PATH
    if not (ctx.root / rel).is_file():
        # The gate is about numerals inside this file.  If the file is absent
        # there is no hand-written numeral to find, and its absence is
        # G-FRAMING-README's business (the first screen must link it) rather
        # than a numeral finding invented here.
        ctx.skip("G-LIMITS-NOHAND", f"{rel} does not exist in this tree")
        return findings
    text, err = read_text(ctx.root, rel)
    if text is None:
        return [Finding("G-LIMITS-NOHAND", rel, 0, f"PARSE_ERROR {err}")]

    depth = 0
    for line_no, line in enumerate(text.split("\n"), start=1):
        if GENERATED_BEGIN_RE.search(line):
            depth += 1
            continue
        if GENERATED_END_RE.search(line):
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        stripped = strip_non_claim_tokens(HTML_COMMENT_RE.sub(" ", line))
        hit = NUMERAL_RE.search(stripped)
        if hit and hit.group(0).strip():
            findings.append(
                Finding(
                    "G-LIMITS-NOHAND",
                    rel,
                    line_no,
                    one_line(
                        f"NUMERAL_OUTSIDE_GENERATED_BLOCK {excerpt(hit.group(0), 30)} in "
                        f"{excerpt(line)} | write it into artifacts/limits/limits.json and "
                        "regenerate | (this finding is unwaivable)"
                    ),
                )
            )
    if depth:
        findings.append(
            Finding(
                "G-LIMITS-NOHAND",
                rel,
                0,
                "PARSE_ERROR a BEGIN GENERATED marker is not closed by an END GENERATED marker",
            )
        )
    return findings


def check_framing_readme(ctx: Context) -> list[Finding]:
    """G-FRAMING-README: the README first screen carries the H1, the oneline,
    the disclaimer and the LIMITATIONS link, in that order."""
    findings: list[Finding] = []
    if not (ctx.root / FRAMING_PATH).is_file():
        ctx.skip(
            "G-FRAMING-README",
            f"{FRAMING_PATH} does not exist, so there is nothing to byte-compare the "
            "README's hand-copied framing strings against; authoring it from the "
            "specification's normative wording is a content decision this tool will not take",
        )
        return findings

    try:
        with (ctx.root / FRAMING_PATH).open("rb") as handle:
            framing = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [
            Finding(
                "G-FRAMING-README",
                FRAMING_PATH,
                0,
                f"PARSE_ERROR not valid TOML: {one_line(str(exc))}",
            )
        ]

    text, err = read_text(ctx.root, README_PATH)
    if text is None:
        return [Finding("G-FRAMING-README", README_PATH, 0, f"PARSE_ERROR {err}")]

    # The first screen is defined structurally: start of file to the first
    # '\n## ' heading (section 71.5 item 1).
    cut = text.find("\n## ")
    first_screen = text if cut < 0 else text[: cut + 1]

    positions: list[tuple[str, int]] = []
    h1 = re.search(r"(?m)^#\s+\S", first_screen)
    if h1 is None:
        findings.append(
            Finding("G-FRAMING-README", README_PATH, 1, "FRAMING_MISSING the first screen has no H1")
        )
    else:
        positions.append(("H1", h1.start()))

    for key, label in (("oneline", "[oneline]"), ("disclaimer", "[disclaimer]")):
        section = framing.get(key)
        value = section.get("text") if isinstance(section, dict) else None
        if not isinstance(value, str) or not value.strip():
            findings.append(
                Finding(
                    "G-FRAMING-README",
                    FRAMING_PATH,
                    0,
                    f"FRAMING_MISSING {label}.text is absent or empty in {FRAMING_PATH}",
                )
            )
            continue
        at = first_screen.find(value)
        if at < 0:
            findings.append(
                Finding(
                    "G-FRAMING-README",
                    README_PATH,
                    1,
                    one_line(
                        f"FRAMING_MISSING the first screen does not contain {label} verbatim; "
                        "a near-copy is not a copy"
                    ),
                )
            )
        else:
            positions.append((label, at))

    link = re.search(r"\[Limitations and known-unsound regions\]\(([^)]*)\)", first_screen)
    if link is None:
        findings.append(
            Finding(
                "G-FRAMING-README",
                README_PATH,
                1,
                one_line(
                    "FRAMING_MISSING the first screen has no link whose anchor text is exactly "
                    '"Limitations and known-unsound regions"'
                ),
            )
        )
    elif link.group(1).strip() != LIMITATIONS_PATH:
        findings.append(
            Finding(
                "G-FRAMING-README",
                README_PATH,
                first_screen.count("\n", 0, link.start()) + 1,
                one_line(
                    f"FRAMING_MISSING the limitations link targets {excerpt(link.group(1), 40)}, "
                    f"expected {LIMITATIONS_PATH}"
                ),
            )
        )
    else:
        positions.append(("LIMITATIONS link", link.start()))

    ordered = [name for name, _ in positions]
    expected = [n for n in ("H1", "[oneline]", "[disclaimer]", "LIMITATIONS link") if n in ordered]
    got = [name for name, _ in sorted(positions, key=lambda p: p[1])]
    if got != expected:
        findings.append(
            Finding(
                "G-FRAMING-README",
                README_PATH,
                1,
                one_line(
                    f"FRAMING_OUT_OF_ORDER the first screen has {' then '.join(got)}; "
                    f"required order is {' then '.join(expected)}"
                ),
            )
        )
    return findings


def check_selftest(ctx: Context) -> list[Finding]:
    """G-CLAIM-SELFTEST: every finding kind and every banned pattern has a
    negative fixture under tests/claims/negative/."""
    findings: list[Finding] = []
    fixtures_dir = ctx.root / NEGATIVE_FIXTURE_DIR
    required = sorted(set(FINDING_KINDS) | set(BANNED_PATTERN_IDS))

    if not fixtures_dir.is_dir():
        # One finding, not forty-three.  The directory is absent; saying so once
        # is the actionable form, and a wall of identical findings is how a gate
        # trains its readers to ignore it.
        return [
            Finding(
                "G-CLAIM-SELFTEST",
                NEGATIVE_FIXTURE_DIR,
                0,
                one_line(
                    f"SELFTEST_FIXTURE_MISSING the negative fixture directory does not exist; "
                    f"{len(required)} cases are required, one per finding kind and one per "
                    "banned pattern BP-01..BP-17"
                ),
            )
        ]

    present = {p.name for p in fixtures_dir.iterdir()}
    stems = {name.split(".", 1)[0].upper() for name in present}
    for name in required:
        if name.upper().replace("-", "_") not in {s.replace("-", "_") for s in stems}:
            findings.append(
                Finding(
                    "G-CLAIM-SELFTEST",
                    NEGATIVE_FIXTURE_DIR,
                    0,
                    one_line(
                        f"SELFTEST_FIXTURE_MISSING no negative case for {name}; a finding kind "
                        "with no negative test is itself a failure"
                    ),
                )
            )
    return findings


def check_claim_001(ctx: Context) -> list[Finding]:
    """G-CLAIM-001: no numeral on a surface without a backing artifact and a
    source id.

    DECIDED: this row is a ROLL-UP of G-CLAIM-ANCHOR, G-CLAIM-REGISTERED and
    G-CLAIM-NUMSRC, not a distinct finding kind.  It is declared in
    ci/gates.toml and absent from CLAIMS.md's gate table, and its asserts is
    exactly the conjunction of three gates that are in both.  Reporting the
    same sentence under four ids would inflate every count without adding a
    single fact, so it emits nothing and reports itself as a roll-up.
    """
    ctx.skip(
        "G-CLAIM-001",
        "roll-up id: its content is the conjunction of G-CLAIM-ANCHOR, G-CLAIM-REGISTERED "
        "and G-CLAIM-NUMSRC, and its artifact half is unimplementable while artifacts/ "
        "does not exist; findings are reported under the three constituent gates",
    )
    return []


def check_waiver(ctx: Context) -> list[Finding]:
    """G-CLAIM-BANNED (unwaivability): WAIVER.md must refuse to parse a waiver
    naming an unwaivable gate id."""
    findings: list[Finding] = []
    text, err = read_text(ctx.root, WAIVER_PATH)
    if text is None:
        del err  # WAIVER.md is optional as far as this checker is concerned.
        return findings
    lines = text.split("\n")
    mask = _fence_mask(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = re.match(r"^\s*gate:\s*(\S+)\s*$", line)
        if m and m.group(1) in UNWAIVABLE_GATES:
            findings.append(
                Finding(
                    "G-CLAIM-BANNED",
                    WAIVER_PATH,
                    i + 1,
                    one_line(
                        f"WAIVER_ON_UNWAIVABLE_GATE {m.group(1)} cannot be waived; the waiver "
                        "mechanism refuses to parse its id"
                    ),
                )
            )
    return findings


# --------------------------------------------------------------------------
# The non-claim allowlist
# --------------------------------------------------------------------------


@dataclass
class NonClaims:
    entries: list[dict[str, object]] = field(default_factory=list)
    hashes: set[tuple[str, str]] = field(default_factory=set)
    findings: list[Finding] = field(default_factory=list)

    def covers(self, unit: Unit) -> bool:
        return (unit.path.lower(), content_hash(unit.text)) in self.hashes


_NONCLAIMS_CACHE: dict[str, NonClaims] = {}


def load_nonclaims(ctx: Context) -> NonClaims:
    """Load and validate docs/claims-nonclaims.toml.

    DECIDED (absent file): an absent allowlist is zero entries and passes.  A
    missing exemption file cannot hide anything; treating its absence as a
    failure would mean a repository that exempts nothing cannot be green.
    """
    key = str(ctx.root)
    if key in _NONCLAIMS_CACHE:
        return _NONCLAIMS_CACHE[key]

    allow = NonClaims()
    _NONCLAIMS_CACHE[key] = allow
    path = ctx.root / NONCLAIMS_PATH
    if not path.is_file():
        return allow

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        allow.findings.append(
            Finding(
                "G-CLAIM-ALLOWCAP",
                NONCLAIMS_PATH,
                0,
                f"PARSE_ERROR not valid TOML: {one_line(str(exc))}",
            )
        )
        return allow

    # DECIDED (cap): the cap lives in the allowlist file, as a required
    # top-level `cap` integer.  The specification's 25 is tagged "(illustrative,
    # not a target)" and G-CLAIM-PLACEHOLDER forbids that tag's numbers escaping
    # docs/prompt/, so hard-coding 25 here would import an illustrative number
    # into an implementation.  The repository declares its own cap, reviewably.
    cap = data.get("cap")
    entries = data.get("entry", [])
    if not isinstance(entries, list):
        allow.findings.append(
            Finding("G-CLAIM-ALLOWCAP", NONCLAIMS_PATH, 0, "PARSE_ERROR 'entry' must be a table array")
        )
        entries = []

    if not isinstance(cap, int):
        allow.findings.append(
            Finding(
                "G-CLAIM-ALLOWCAP",
                NONCLAIMS_PATH,
                0,
                one_line(
                    "ALLOWLIST_NO_CAP the file must declare a top-level integer 'cap'; "
                    "raising it requires a WAIVER.md entry"
                ),
            )
        )
    elif len(entries) > cap:
        allow.findings.append(
            Finding(
                "G-CLAIM-ALLOWCAP",
                NONCLAIMS_PATH,
                0,
                one_line(
                    f"ALLOWLIST_OVER_CAP {len(entries)} entries exceed the declared cap of {cap}; "
                    "raising the cap requires a WAIVER.md entry"
                ),
            )
        )

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            allow.findings.append(
                Finding(
                    "G-CLAIM-ALLOWCAP", NONCLAIMS_PATH, 0, f"PARSE_ERROR entry {index} is not a table"
                )
            )
            continue
        file_value = str(entry.get("file", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        digest = str(entry.get("hash", "")).strip()
        label = f"entry {index} ({file_value or 'no file'})"

        words = [w for w in re.split(r"\s+", reason) if w]
        if reason.lower() == "not a claim" or len(words) < NONCLAIM_REASON_MIN_WORDS:
            allow.findings.append(
                Finding(
                    "G-CLAIM-ALLOWCAP",
                    NONCLAIMS_PATH,
                    0,
                    one_line(
                        f"ALLOWLIST_REASON_TOO_SHORT {label}: reason must be at least "
                        f"{NONCLAIM_REASON_MIN_WORDS} words and may not be \"not a claim\""
                    ),
                )
            )
        for forbidden in NONCLAIM_FORBIDDEN_SURFACES:
            if file_value.lower().startswith(forbidden.lower()):
                allow.findings.append(
                    Finding(
                        "G-CLAIM-ALLOWCAP",
                        NONCLAIMS_PATH,
                        0,
                        one_line(
                            f"ALLOWLIST_FORBIDDEN_SURFACE {label}: no exemption may be granted "
                            f"for {forbidden}"
                        ),
                    )
                )
                break

        if not digest:
            allow.findings.append(
                Finding(
                    "G-CLAIM-ALLOWCAP",
                    NONCLAIMS_PATH,
                    0,
                    one_line(f"PARSE_ERROR {label}: 'hash' of the normalised unit text is required"),
                )
            )
            continue
        live = {content_hash(u.text) for u in ctx.units if u.path.lower() == file_value.lower()}
        if digest not in live:
            allow.findings.append(
                Finding(
                    "G-CLAIM-ALLOWCAP",
                    NONCLAIMS_PATH,
                    0,
                    one_line(
                        f"ALLOWLIST_STALE_HASH {label}: no unit in that file hashes to "
                        f"{digest[:12]}; the sentence was edited, so the exemption is void"
                    ),
                )
            )
            continue
        allow.entries.append(entry)
        allow.hashes.add((file_value.lower(), digest))

    return allow


# --------------------------------------------------------------------------
# The check registry
# --------------------------------------------------------------------------

CheckFn = Callable[[Context], list[Finding]]

#: Gate id -> the function that runs it.  Every implemented gate is here; a
#: gate that is declared but cannot run is in SKIPPED_CHECKS instead.
CHECKS: dict[str, CheckFn] = {
    "G-CLAIM-001": check_claim_001,
    "G-CLAIM-ALLOWCAP": check_allowcap,
    "G-CLAIM-ANCHOR": check_anchor,
    "G-CLAIM-BANNED": check_banned,
    "G-CLAIM-NOERASE": check_noerase,
    "G-CLAIM-NUMSRC": check_numsrc,
    "G-CLAIM-PARSE": check_parse,
    "G-CLAIM-PLACEHOLDER": check_placeholder,
    "G-CLAIM-REGISTERED": check_registered,
    "G-CLAIM-SELFTEST": check_selftest,
    "G-CLAIM-SUPPORT": check_support,
    "G-FRAMING-README": check_framing_readme,
    "G-LIMITS-NOHAND": check_limits_nohand,
    "G-CLAIM-BANNED/WAIVER": check_waiver,
}

#: Gates that cannot run at all against a tree in this state, with the reason.
#: These are reported on every run.  A gate that is partly implemented reports
#: its gap from inside its check function instead (see `Context.skip`).
SKIPPED_CHECKS: dict[str, str] = {
    "G-CLAIM-001": (
        "roll-up id with no distinct finding kind: its artifact half needs artifacts/, which "
        "does not exist; see G-CLAIM-ANCHOR, G-CLAIM-REGISTERED and G-CLAIM-NUMSRC"
    ),
    "G-FRAMING-VERBATIM": (
        "not run here: it belongs to `make claims-gen`, which is not declared in the Makefile, "
        "and docs/framing.toml does not exist to generate from"
    ),
    "G-LIMITS-COMPLETE": (
        "not run here: it is a `make release` gate over artifacts/limits/limits.json, which "
        "does not exist; all six LIMITATIONS.md blocks currently render NOT MEASURED"
    ),
}


def analyse(root: Path, tier: str = "t1") -> Report:
    """Run every registered check over `root` and return the whole report."""
    root = Path(root).resolve()
    _NONCLAIMS_CACHE.pop(str(root), None)
    ctx = build_context(root, tier)

    findings: list[Finding] = []
    for gate in sorted(CHECKS):
        try:
            findings.extend(CHECKS[gate](ctx))
        except Exception as exc:  # noqa: BLE001 - a crashing check is a finding.
            findings.append(
                Finding(
                    gate.split("/", 1)[0],
                    ctx.registry.path,
                    0,
                    one_line(f"PARSE_ERROR check {gate} raised {type(exc).__name__}: {exc}"),
                )
            )

    warnings = sorted(ctx.warnings)
    if tier != "t1":
        # Outside T1 there is no warning channel: section 71.3 makes every
        # state a failure at nightly and release.
        findings.extend(warnings)
        warnings = []

    skipped = sorted(
        {Skip(gate, one_line(reason)) for gate, reason in SKIPPED_CHECKS.items()}
        | set(ctx.dynamic_skips)
    )

    return Report(
        schema=SCHEMA,
        findings=sorted(set(findings)),
        warnings=warnings,
        skipped=skipped,
        surfaces=list(ctx.surfaces),
        missing_surfaces=list(ctx.missing_surfaces),
        registry_path=ctx.registry.path,
        unit_count=len(ctx.units),
        candidate_count=len(ctx.candidates),
        record_count=len(ctx.registry.records),
    )


def run_checks(root: Path) -> list[Finding]:
    """Run every registered check over `root` and return the findings, sorted.

    This is the public API.  It reads the repository and returns; it writes
    nothing, and it never raises on a malformed input file - an unreadable or
    unparseable surface is reported as a finding like any other defect.

    Warned findings (section 71.3's `warn` states at T1) are returned here too,
    carrying `severity="warn"`.  They do not fail the build - `main` derives
    the exit code from the severity - but they are reported, because a gate
    state the contract says to report must not vanish from the API the
    contract's consumers call.
    """
    report = analyse(Path(root))
    return sorted(set(report.findings) | set(report.warnings))


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def format_finding(finding: Finding, severity: str = "FAIL") -> str:
    """One finding, one line: `FAIL  path:line  GATE  message`."""
    where = finding.path if finding.line == 0 else f"{finding.path}:{finding.line}"
    return f"{severity}  {where}  {finding.check}  {finding.message}"


def header_line(report: Report) -> str:
    return (
        f"claimcheck {report.schema} \u2014 surfaces={len(report.surfaces):,} "
        f"units={report.unit_count:,} candidates={report.candidate_count:,} "
        f"registry={report.record_count:,} records"
    )


def render(report: Report, summary_only: bool) -> str:
    """The human report.  Deterministic: no timestamps, no absolute paths."""
    out: list[str] = [header_line(report)]
    exit_code = 1 if report.findings else 0

    if not summary_only:
        out.append("")
        for finding in report.findings:
            out.append(format_finding(finding, "FAIL"))
        for warning in report.warnings:
            out.append(format_finding(warning, "WARN"))
        for glob in report.missing_surfaces:
            out.append(f"NOTE  {glob}  surface glob matched no file in this tree")
        for skip in report.skipped:
            out.append(f"SKIP  {skip.check}  {skip.reason}")
        out.append("")

    out.append(
        f"{len(report.findings)} findings, {len(report.warnings)} warnings, "
        f"{len(report.skipped)} skipped checks \u2014 exit {exit_code}"
    )
    return "\n".join(out) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claims-check",
        description=(
            "Check the SPECTRA claims registry, the banned-phrase list and the framing "
            "and limitations rules. Reads the repository; never edits it."
        ),
    )
    parser.add_argument(
        "root", nargs="?", default=".", help="repository root to check (default: the cwd)"
    )
    parser.add_argument("--json", action="store_true", help="emit the machine-readable report")
    parser.add_argument("--summary", action="store_true", help="print counts only")
    parser.add_argument(
        "--tier",
        choices=("t1", "t2", "t3"),
        default="t1",
        help=(
            "CI tier. At t1 a MISSING_ARTIFACT support state is a warning, as section 71.3's "
            "state table requires; at t2 and t3 it is a failure."
        ),
    )
    parser.add_argument(
        "--report",
        metavar="PATH",
        default=None,
        help=(
            "also write the machine-readable report to PATH. Off by default: this tool "
            "writes nothing unless asked to."
        ),
    )
    args = parser.parse_args(argv)

    # Surface text is UTF-8 and the report quotes it back.  Without this a
    # non-UTF-8 console (cp1252 on Windows) turns a finding into a traceback,
    # which is the one way a checker must never fail.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):  # pragma: no cover - not a TextIO
            pass

    root = Path(args.root)
    if not root.is_dir():
        print(f"claims-check: not a directory: {args.root}", file=sys.stderr)
        return 1

    report = analyse(root, args.tier)
    payload = json.dumps(report.to_json(), indent=2, sort_keys=True, ensure_ascii=False)

    if args.json:
        print(payload)
    else:
        sys.stdout.write(render(report, args.summary))

    if args.report:
        out = Path(args.report)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload + "\n", encoding="utf-8", newline="\n")
        except OSError as exc:
            print(f"claims-check: cannot write {args.report}: {exc}", file=sys.stderr)
            return 1
        if not args.json:
            print(f"report: {args.report}")

    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
