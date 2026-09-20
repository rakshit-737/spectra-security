"""Contract tests for ``tools.claims_check``.

These tests were written from the claims-check CONTRACT only -- CLAIMS.md (the
record grammar, the scope-clause rule, the banned-phrase table, the surface
list, the exempt paths) and the eleven ``G-CLAIM-*`` rows of ci/gates.toml --
without sight of the implementation.  Nothing here was calibrated against
observed output: where the contract does not determine an outcome, the test
asserts only what the contract *does* determine, and the gap is recorded in
tests/README.md rather than guessed at.

Public API under test::

    from tools.claims_check import run_checks, Finding
    findings = run_checks(root=Path(tmpdir))

Each test builds a tiny synthetic repository in a temp directory, writes the
two or three files the check reads, and asserts on the findings.

Field-name tolerance
--------------------
The contract fixes the *finding kinds* (BANNED, UNANCHORED, UNREGISTERED,
TEXT_DRIFT, SURFACE_UNDECLARED, TUNED_ON_HEADLINE, ORPHAN, STALE_*,
NUMBER_NOT_IN_ARTIFACT, ...) and the *gate ids* (G-CLAIM-BANNED,
G-LIMITS-NOHAND, ...).  It does not fix the attribute names of ``Finding``.
The helpers below therefore read a finding's kind/gate/path/line through a
small set of plausible attribute names, falling back to the object's rendered
form.  Assertions are made on the contract-fixed tokens, never on a guessed
attribute name.

Run with::

    python -m unittest discover -s tests -t . -v      # from the repo root

See tests/README.md.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.claims_check import Finding, run_checks  # noqa: E402


# ---------------------------------------------------------------------------
# finding introspection helpers (tolerant about attribute spelling only)
# ---------------------------------------------------------------------------

_KIND_ATTRS = (
    "kind",
    "code",
    "finding_kind",
    "finding_type",
    "kind_name",
    "category",
    "type",
    "rule",
    "check",
)
#: ``check`` is in this list as well as in ``_KIND_ATTRS``: the contract fixes
#: that a finding carries its gate id, not what the attribute holding it is
#: called, and a tool that keys its gates by id in a ``CHECKS`` table naturally
#: calls the field ``check``.  Without it ``gate_of`` returns "" for such a
#: tool and ``tags_of`` silently degrades to kind-only, which makes a
#: gate-scoped filter (``"G-LIMITS" in tags_of(f)``) match nothing and a test
#: that filters that way pass vacuously.
_GATE_ATTRS = ("gate", "gate_id", "gates", "gate_ids", "check")
_PATH_ATTRS = (
    "path",
    "file",
    "filename",
    "file_path",
    "relpath",
    "surface",
    "location",
)
_LINE_ATTRS = ("line", "lineno", "line_no", "line_number")


def _fields(finding: Any) -> dict[str, Any]:
    """Best-effort mapping of a Finding's public data."""
    if dataclasses.is_dataclass(finding) and not isinstance(finding, type):
        try:
            return dict(dataclasses.asdict(finding))
        except Exception:  # pragma: no cover - defensive
            pass
    if isinstance(finding, dict):
        return dict(finding)
    out: dict[str, Any] = {}
    for name in dir(finding):
        if name.startswith("_"):
            continue
        try:
            value = getattr(finding, name)
        except Exception:  # pragma: no cover - defensive
            continue
        if callable(value):
            continue
        out[name] = value
    return out


#: a default object repr carries a memory address, which is not stable between
#: runs; scrub it so that these helpers cannot themselves make a deterministic
#: checker look non-deterministic.
_ADDRESS = re.compile(r"0[xX][0-9A-Fa-f]+")


def scrub(text: str) -> str:
    return _ADDRESS.sub("0xADDR", text)


def blob(finding: Any) -> str:
    """Everything the finding carries, rendered and uppercased for matching."""
    parts = [repr(finding), str(finding)]
    for key, value in sorted(_fields(finding).items(), key=lambda kv: kv[0]):
        parts.append("{0}={1!r}".format(key, value))
    return scrub(" ".join(parts)).upper()


def _first_str(finding: Any, names: Sequence[str]) -> str:
    data = _fields(finding)
    for name in names:
        if name not in data:
            continue
        value = data[name]
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (list, tuple)) and value:
            return " ".join(str(v) for v in value)
    return ""


def kind_of(finding: Any) -> str:
    return _first_str(finding, _KIND_ATTRS).upper()


def gate_of(finding: Any) -> str:
    return _first_str(finding, _GATE_ATTRS).upper()


def path_of(finding: Any) -> str:
    return _first_str(finding, _PATH_ATTRS).replace("\\", "/")


def line_of(finding: Any) -> int | None:
    data = _fields(finding)
    for name in _LINE_ATTRS:
        value = data.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def tags_of(finding: Any) -> str:
    """Identity tokens only (kind + gate), so that a negative assertion does
    not trip over the same word appearing in another finding's prose.  Falls
    back to the whole rendered finding when neither a kind nor a gate
    attribute is exposed."""
    tags = "{0} {1}".format(kind_of(finding), gate_of(finding)).strip()
    return tags if tags else blob(finding)


def sel(findings: Iterable[Any], *tokens: str) -> list[Any]:
    """Findings whose kind/gate identity contains every token."""
    wanted = [t.upper() for t in tokens]
    return [f for f in findings if all(t in tags_of(f) for t in wanted)]


def sel_any(findings: Iterable[Any], *tokens: str) -> list[Any]:
    """Findings whose full rendered form contains every token.  Used for
    positive assertions about sub-kinds and ids (BP-05, CLM-0001,
    MISSING_ARTIFACT) that the contract names but does not promise to expose as
    a dedicated attribute."""
    wanted = [t.upper() for t in tokens]
    return [f for f in findings if all(t in blob(f) for t in wanted)]


def render(findings: Iterable[Any]) -> str:
    items = list(findings)
    if not items:
        return "<no findings>"
    lines = ["{0} finding(s):".format(len(items))]
    for finding in items:
        lines.append(
            "  kind={kind!r} gate={gate!r} path={path!r} line={line!r} :: {raw}".format(
                kind=kind_of(finding),
                gate=gate_of(finding),
                path=path_of(finding),
                line=line_of(finding),
                raw=scrub(str(finding))[:400],
            )
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# fixture material
# ---------------------------------------------------------------------------

REGISTRY_HEADER = "# SPECTRA CLAIMS REGISTRY\n\nschema: 1\n"

# 64 hex characters, as the grammar demands.  The tests cannot compute a true
# BLAKE3 digest with the standard library, so the support-freshness tests
# assert only the states that do not depend on a correct digest.
BLAKE3 = "0123456789abcdef" * 4

# >= 8 words, names the rule table / the control catalog / the evidence regime,
# and contains none of the four forbidden scope strings.
SCOPE_OK = (
    "under the shipped rule table, the declared control catalog "
    "and the recorded evidence regime"
)
# exactly eight whitespace-separated words -- the boundary the contract sets.
SCOPE_EIGHT = "rule table, control catalog, evidence regime, nonadaptive attacker"
# seven words -- one under the boundary.
SCOPE_SEVEN = "rule table, control catalog, evidence regime, nonadaptive"

MAKEFILE = (
    "claims-check: ## the claims gate\n"
    "\t@python -m tools.claims_check\n"
    "\n"
    "claims-refresh: ## re-resolve support hashes\n"
    "\t@python -m tools.claims_check --refresh\n"
)

SENTENCE = "The kernel reconstructs 42 attack paths in the sample bundle."
SENTENCE_DRIFTED = "The kernel reconstructs 7 attack paths in the sample bundle."


def record(
    claim_id: str = "CLM-0001",
    *,
    text: str = SENTENCE,
    kind: str = "CAPABILITY",
    surfaces: Sequence[str] = ("README.md#claims",),
    artifact: str = "artifacts/demo/summary.json",
    blake3: str = BLAKE3,
    run: str = "run-0000abcd",
    gate: str = "G-CLAIM-REGISTERED",
    target: str = "claims-check",
    scope: str = SCOPE_OK,
    status: str = "GREEN",
    note: str | None = None,
) -> str:
    """One record in the fixed record grammar."""
    lines = ["### " + claim_id, 'text: "{0}"'.format(text), "kind: " + kind, "surfaces:"]
    lines += ["  - " + surface for surface in surfaces]
    lines += [
        "support:",
        "  artifact: " + artifact,
        "  blake3: " + blake3,
        "  run: " + run,
        "  gate: " + gate,
        "  target: " + target,
        'scope: "{0}"'.format(scope),
        "status: " + status,
    ]
    if note is not None:
        lines.append('note: "{0}"'.format(note))
    return "\n".join(lines) + "\n"


def registry(*records: str) -> str:
    """A registry file.  With no records this is the shape of the file as it
    stands today, which the parser must accept without error."""
    body = "\n### Records\n\n"
    if not records:
        return REGISTRY_HEADER + body + "_None._\n"
    return REGISTRY_HEADER + body + "\n".join(records)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    """{relative posix path: sha256} for every file under root."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        try:
            if path.is_file():
                out[path.relative_to(root).as_posix()] = sha256_of(path)
        except OSError:  # dangling symlink, unreadable entry
            out[path.relative_to(root).as_posix()] = "<unreadable>"
    return out


# ---------------------------------------------------------------------------
# base case
# ---------------------------------------------------------------------------


class ClaimsCase(unittest.TestCase):
    """Builds a synthetic repository and runs the checker over it."""

    #: written into every fixture unless a test overrides or deletes them
    DEFAULTS: dict[str, Any] = {
        "CLAIMS.md": registry(),
        "Makefile": MAKEFILE,
    }

    def repo(self, files: dict[str, Any] | None = None) -> Path:
        tmp = tempfile.TemporaryDirectory(
            prefix="spectra-claims-", ignore_cleanup_errors=True
        )
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        merged: dict[str, Any] = dict(self.DEFAULTS)
        merged.update(files or {})
        for rel, content in merged.items():
            if content is None:  # explicit deletion of a default
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                with open(target, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)
        return root

    def check(self, root: Path) -> list[Any]:
        """run_checks twice; assert the API contract and determinism."""
        try:
            first = run_checks(root=root)
        except Exception as exc:  # pragma: no cover - failure path
            raise AssertionError(
                "run_checks must not raise on any tree; it raised {0!r}".format(exc)
            ) from exc
        self.assertIsInstance(first, list, "run_checks must return a list of Finding")
        for item in first:
            self.assertIsInstance(
                item,
                Finding,
                "every element must be a Finding, got {0!r}".format(type(item)),
            )
        second = run_checks(root=root)
        self.assertEqual(
            [render([f]) for f in first],
            [render([f]) for f in second],
            "run_checks must be deterministic: two runs over one tree differ",
        )
        return first

    # -- assertion sugar ---------------------------------------------------

    def assert_one(self, findings: Sequence[Any], *tokens: str) -> Any:
        hits = sel(findings, *tokens)
        self.assertEqual(
            1,
            len(hits),
            "expected exactly one {0} finding\n{1}".format("+".join(tokens), render(findings)),
        )
        return hits[0]

    def assert_some(self, findings: Sequence[Any], *tokens: str) -> Any:
        hits = sel_any(findings, *tokens)
        self.assertTrue(
            hits,
            "expected at least one finding carrying {0}\n{1}".format(
                "+".join(tokens), render(findings)
            ),
        )
        return hits[0]

    def assert_none(self, findings: Sequence[Any], *tokens: str) -> None:
        hits = sel(findings, *tokens)
        self.assertEqual(
            [],
            hits,
            "expected no {0} finding\n{1}".format("+".join(tokens), render(hits)),
        )

    def assert_none_any(self, findings: Sequence[Any], *tokens: str) -> None:
        hits = sel_any(findings, *tokens)
        self.assertEqual(
            [],
            hits,
            "expected no finding carrying {0}\n{1}".format("+".join(tokens), render(hits)),
        )


# ---------------------------------------------------------------------------
# 1. API, determinism, read-only
# ---------------------------------------------------------------------------


class TestApiContract(ClaimsCase):
    def test_run_checks_returns_list_of_findings(self) -> None:
        findings = self.check(self.repo())
        self.assertIsInstance(findings, list)

    def test_run_checks_accepts_root_as_keyword_path(self) -> None:
        root = self.repo()
        self.assertIsInstance(run_checks(root=root), list)

    def test_empty_tree_does_not_crash(self) -> None:
        # No CLAIMS.md, no Makefile, no surfaces at all.  The contract does not
        # fix what is reported here; it does fix that the tool reports rather
        # than raises.
        root = self.repo({"CLAIMS.md": None, "Makefile": None})
        self.check(root)

    def test_findings_name_repository_relative_paths(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nSPECTRA guarantees the bundle is whole.\n"}
        )
        findings = self.check(root)
        banned = self.assert_one(findings, "BANNED")
        reported = path_of(banned) or blob(banned)
        self.assertIn("README.MD", reported.upper())
        self.assertNotIn(
            str(root).upper().replace("\\", "/"),
            reported.upper().replace("\\", "/"),
            "paths must be repository-relative so the report is diffable",
        )


class TestDeterminism(ClaimsCase):
    def _busy_files(self) -> dict[str, Any]:
        return {
            "README.md": (
                "# Demo\n\nSPECTRA guarantees the bundle is whole.\n\n"
                "<!-- CLM-0009 -->\n" + SENTENCE + "\n"
            ),
            "docs/guide.md": (
                "# Guide\n\nThe kernel proves the goal atom is absent.\n\n"
                "(illustrative, not a target)\n"
            ),
            "LIMITATIONS.md": "# Limitations\n\nRoughly 33 percent of runs are flagged.\n",
            "CLAIMS.md": registry(
                record("CLM-0002", text="A claim nobody makes on any surface.")
            ),
        }

    def test_identical_trees_in_different_directories_report_identically(self) -> None:
        first = self.check(self.repo(self._busy_files()))
        second = self.check(self.repo(self._busy_files()))
        self.assertEqual(
            [render([f]) for f in first],
            [render([f]) for f in second],
            "two byte-identical trees must produce byte-identical reports",
        )

    def test_report_order_is_stable_across_runs(self) -> None:
        root = self.repo(self._busy_files())
        runs = [run_checks(root=root) for _ in range(3)]
        rendered = [[render([f]) for f in run] for run in runs]
        self.assertEqual(rendered[0], rendered[1])
        self.assertEqual(rendered[1], rendered[2])


class TestNeverModifiesTheRepository(ClaimsCase):
    def test_no_file_is_changed_added_or_removed(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nSPECTRA guarantees the bundle is whole.\n\n"
                    "<!-- CLM-0001 -->\n" + SENTENCE + "\n"
                ),
                "LIMITATIONS.md": "# Limitations\n\nRoughly 33 percent of runs are flagged.\n",
                "SECURITY.md": "# Security\n\nReport issues privately.\n",
                "docs/guide.md": "# Guide\n\n(illustrative, not a target)\n",
                "docs/prompt/part2/71-claims.md": "# 71\n\nSPECTRA guarantees nothing.\n",
                "docs/banned.toml": 'exempt_paths = ["CLAIMS.md", "docs/prompt/"]\n',
                "CLAIMS.md": registry(record("CLM-0001")),
                ".github/PULL_REQUEST_TEMPLATE.md": "# PR\n\nNo score, no severity.\n",
            }
        )
        before = snapshot(root)
        run_checks(root=root)
        after = snapshot(root)

        changed = sorted(k for k in before if k in after and before[k] != after[k])
        self.assertEqual([], changed, "run_checks modified files: {0}".format(changed))

        removed = sorted(set(before) - set(after))
        self.assertEqual([], removed, "run_checks deleted files: {0}".format(removed))

        # A report file is the CLI's business, not run_checks'; if anything new
        # appears it may only be under artifacts/.
        created = sorted(
            k for k in set(after) - set(before) if not k.startswith("artifacts/")
        )
        self.assertEqual(
            [], created, "run_checks created files outside artifacts/: {0}".format(created)
        )


# ---------------------------------------------------------------------------
# 2. G-CLAIM-PARSE -- the record grammar
# ---------------------------------------------------------------------------


class TestRegistryGrammar(ClaimsCase):
    """The parser is strict: no key reordering, no tolerant parsing, no
    optional fields except note."""

    def parse_findings(self, registry_text: str) -> list[Any]:
        root = self.repo({"CLAIMS.md": registry_text})
        return sel(self.check(root), "PARSE")

    # -- clean -------------------------------------------------------------

    def test_empty_registry_parses(self) -> None:
        self.assertEqual([], self.parse_findings(registry()), "zero records must parse")

    def test_well_formed_record_parses(self) -> None:
        self.assertEqual([], self.parse_findings(registry(record())))

    def test_optional_note_is_accepted(self) -> None:
        self.assertEqual(
            [],
            self.parse_findings(
                registry(record(note="rounded down to 2 significant figures"))
            ),
        )

    def test_negative_kind_may_carry_run_not_applicable(self) -> None:
        self.assertEqual(
            [],
            self.parse_findings(
                registry(
                    record(
                        kind="NEGATIVE",
                        run="n/a",
                        text="SPECTRA emits no scalar verdict.",
                    )
                )
            ),
        )

    def test_every_declared_surface_form_parses(self) -> None:
        surfaces = (
            "README.md#claims",
            "docs/eval.md#results",
            "ui:verdict.subtitle",
            "cli:banner.oneline",
            "demo:reconstruct",
            "paper:abstract",
            "release:1.2.3",
            "meta:github_about",
        )
        self.assertEqual([], self.parse_findings(registry(record(surfaces=surfaces))))

    def test_four_digit_ids_at_both_ends_of_the_range_parse(self) -> None:
        self.assertEqual(
            [],
            self.parse_findings(
                registry(
                    record("CLM-0000"),
                    record("CLM-9999", text="A second registered sentence."),
                )
            ),
        )

    # -- violations --------------------------------------------------------

    def test_reordered_keys_fail(self) -> None:
        good = record()
        bad = good.replace(
            'text: "{0}"\nkind: CAPABILITY\n'.format(SENTENCE),
            'kind: CAPABILITY\ntext: "{0}"\n'.format(SENTENCE),
        )
        self.assertNotEqual(good, bad, "fixture did not actually reorder the keys")
        self.assertTrue(
            self.parse_findings(registry(bad)), "key reordering must fail the parse"
        )

    def test_missing_required_field_fails(self) -> None:
        bad = record().replace("status: GREEN\n", "")
        self.assertTrue(
            self.parse_findings(registry(bad)), "a missing status must fail the parse"
        )

    def test_missing_support_line_fails(self) -> None:
        bad = record().replace("  blake3: " + BLAKE3 + "\n", "")
        self.assertTrue(self.parse_findings(registry(bad)))

    def test_unknown_kind_token_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(kind="METRIC"))))

    def test_unknown_status_token_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(status="PROVISIONAL"))))

    def test_blake3_shorter_than_sixty_four_hex_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(blake3="abc123"))))

    def test_blake3_of_sixty_four_non_hex_characters_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(blake3="z" * 64))))

    def test_blake3_of_sixty_five_hex_characters_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(blake3=BLAKE3 + "a"))))

    def test_run_not_applicable_on_a_non_negative_record_fails(self) -> None:
        self.assertTrue(
            self.parse_findings(registry(record(kind="CAPABILITY", run="n/a")))
        )

    def test_duplicate_claim_id_fails(self) -> None:
        self.assertTrue(
            self.parse_findings(
                registry(record("CLM-0001"), record("CLM-0001", text="Another sentence."))
            )
        )

    def test_three_digit_heading_fails(self) -> None:
        bad = record().replace("### CLM-0001", "### CLM-001")
        self.assertTrue(self.parse_findings(registry(bad)))

    def test_five_digit_heading_fails(self) -> None:
        bad = record().replace("### CLM-0001", "### CLM-00011")
        self.assertTrue(self.parse_findings(registry(bad)))

    def test_unknown_surface_form_fails(self) -> None:
        self.assertTrue(self.parse_findings(registry(record(surfaces=("wiki:home",)))))

    def test_paper_surface_outside_the_four_sections_fails(self) -> None:
        self.assertTrue(
            self.parse_findings(registry(record(surfaces=("paper:appendix",))))
        )

    def test_meta_surface_outside_the_three_keys_fails(self) -> None:
        self.assertTrue(
            self.parse_findings(registry(record(surfaces=("meta:twitter_bio",))))
        )

    def test_empty_surfaces_block_fails(self) -> None:
        bad = record().replace("  - README.md#claims\n", "")
        self.assertTrue(
            self.parse_findings(registry(bad)), "surfaces: needs one or more entries"
        )

    def test_unquoted_text_fails(self) -> None:
        bad = record().replace('text: "{0}"'.format(SENTENCE), "text: " + SENTENCE)
        self.assertTrue(self.parse_findings(registry(bad)))

    def test_unknown_field_fails(self) -> None:
        bad = record() + 'owner: "someone"\n'
        self.assertTrue(
            self.parse_findings(registry(bad)), "no optional fields except note"
        )

    def test_parse_finding_names_the_registry_file(self) -> None:
        findings = self.parse_findings(registry(record(kind="METRIC")))
        reported = " ".join(path_of(f) or blob(f) for f in findings).upper()
        self.assertIn("CLAIMS.MD", reported)


# ---------------------------------------------------------------------------
# 3. scope clause lint (reported under G-CLAIM-PARSE)
# ---------------------------------------------------------------------------


class TestScopeClause(ClaimsCase):
    def scope_findings(self, scope: str) -> list[Any]:
        root = self.repo({"CLAIMS.md": registry(record(scope=scope))})
        findings = self.check(root)
        # the scope lint is declared under G-CLAIM-PARSE; accept either the
        # gate id or a SCOPE-named kind
        return sel(findings, "PARSE") + [f for f in findings if "SCOPE" in tags_of(f)]

    def test_eight_word_scope_passes(self) -> None:
        self.assertEqual(8, len(SCOPE_EIGHT.split()), "fixture is not eight words")
        self.assertEqual([], self.scope_findings(SCOPE_EIGHT))

    def test_long_scope_passes(self) -> None:
        self.assertEqual([], self.scope_findings(SCOPE_OK))

    def test_seven_word_scope_fails(self) -> None:
        self.assertEqual(7, len(SCOPE_SEVEN.split()), "fixture is not seven words")
        self.assertTrue(self.scope_findings(SCOPE_SEVEN), "under eight words must fail")

    def test_empty_scope_fails(self) -> None:
        self.assertTrue(self.scope_findings(""))

    def test_scope_containing_always_fails(self) -> None:
        self.assertTrue(self.scope_findings(SCOPE_OK + " and always holds"))

    def test_scope_containing_in_general_fails(self) -> None:
        self.assertTrue(self.scope_findings(SCOPE_OK + ", in general"))

    def test_scope_containing_in_practice_fails(self) -> None:
        self.assertTrue(self.scope_findings(SCOPE_OK + ", in practice"))

    def test_scope_containing_for_any_system_fails(self) -> None:
        self.assertTrue(self.scope_findings(SCOPE_OK + " for any system"))


# ---------------------------------------------------------------------------
# 4. G-CLAIM-BANNED
# ---------------------------------------------------------------------------


class TestBannedPhrases(ClaimsCase):
    """The banned scan is a hard failure independent of registration, it has no
    allowlist, and it is unwaivable."""

    def test_banned_phrase_in_a_non_exempt_file_is_reported_once(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nSPECTRA guarantees the bundle is whole.\n"}
        )
        findings = self.check(root)
        banned = self.assert_one(findings, "BANNED")
        self.assertIn("BP-02", blob(banned), render(findings))

    def test_banned_finding_carries_the_line_number(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nFiller line.\n\nSPECTRA guarantees the bundle is whole.\n"
                )
            }
        )
        banned = self.assert_one(self.check(root), "BANNED")
        line = line_of(banned)
        if line is not None:
            self.assertEqual(5, line, "banned phrase sits on line 5: " + blob(banned))
        else:
            self.assertIn(":5", str(banned), "the finding must locate the sentence")

    def test_real_time_is_reported_as_bp_05(self) -> None:
        root = self.repo({"README.md": "# Demo\n\nSPECTRA does real-time reconstruction.\n"})
        findings = self.check(root)
        banned = self.assert_one(findings, "BANNED")
        self.assertIn("BP-05", blob(banned), render(findings))

    def test_banned_match_is_case_insensitive(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nSPECTRA GUARANTEES the bundle is whole.\n"}
        )
        self.assert_one(self.check(root), "BANNED")

    def test_banned_phrase_in_each_exempt_path_is_not_reported(self) -> None:
        sentence = "SPECTRA guarantees the bundle is whole."
        for rel in (
            "CLAIMS.md",
            "docs/banned.toml",
            "docs/claims-policy.md",
            "docs/prompt/part2/71-claims.md",
            "docs/NON-GOALS.md",
            "docs/descope-ladder.md",
        ):
            with self.subTest(exempt=rel):
                if rel == "CLAIMS.md":
                    content = registry() + "\n" + sentence + "\n"
                elif rel.endswith(".toml"):
                    content = 'note = "{0}"\n'.format(sentence)
                else:
                    content = "# Doc\n\n{0}\n".format(sentence)
                root = self.repo({rel: content})
                self.assert_none(self.check(root), "BANNED")

    def test_exemption_does_not_extend_to_a_sibling_file(self) -> None:
        root = self.repo(
            {
                "docs/prompt/part2/71-claims.md": "# 71\n\nSPECTRA guarantees the bundle.\n",
                "docs/plan/notes.md": "# Notes\n\nSPECTRA guarantees the bundle.\n",
            }
        )
        findings = self.check(root)
        banned = sel(findings, "BANNED")
        self.assertEqual(1, len(banned), render(findings))
        self.assertIn(
            "DOCS/PLAN/NOTES.MD", (path_of(banned[0]) or blob(banned[0])).upper()
        )

    def test_banned_scan_ignores_anchoring_and_registration(self) -> None:
        # Anchored, registered and byte-identical -- still banned.
        text = "SPECTRA guarantees the bundle is whole."
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n{0}\n".format(text),
                "CLAIMS.md": registry(record("CLM-0001", text=text)),
            }
        )
        self.assert_one(self.check(root), "BANNED")

    def test_banned_finding_is_not_suppressed_by_a_waiver(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\nSPECTRA guarantees the bundle is whole.\n",
                "WAIVER.md": (
                    "# SPECTRA WAIVERS\n\n"
                    "| gate | reason | expires |\n"
                    "|------|--------|---------|\n"
                    "| G-CLAIM-BANNED | attempted waiver of an unwaivable gate | 2099-01-01 |\n"
                ),
            }
        )
        self.assert_one(self.check(root), "BANNED")

    def test_two_banned_phrases_are_two_findings(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nSPECTRA guarantees the bundle is whole.\n\n"
                    "SPECTRA does real-time reconstruction.\n"
                )
            }
        )
        findings = self.check(root)
        self.assertEqual(2, len(sel(findings, "BANNED")), render(findings))

    def test_clean_document_reports_no_banned_finding(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nSPECTRA reads a recorded telemetry bundle and reports a set.\n"
                )
            }
        )
        self.assert_none(self.check(root), "BANNED")


# ---------------------------------------------------------------------------
# 5. G-CLAIM-ANCHOR
# ---------------------------------------------------------------------------


class TestAnchorGate(ClaimsCase):
    def test_numeral_without_an_anchor_is_unanchored(self) -> None:
        root = self.repo({"README.md": "# Demo\n\n" + SENTENCE + "\n"})
        findings = self.check(root)
        finding = self.assert_one(findings, "UNANCHORED")
        self.assertIn("README.MD", (path_of(finding) or blob(finding)).upper())

    def test_anchored_and_registered_sentence_is_not_unanchored(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        self.assert_none(self.check(root), "UNANCHORED")

    def test_capability_verb_without_an_anchor_is_unanchored(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nThe kernel proves the goal atom is absent.\n"}
        )
        self.assert_one(self.check(root), "UNANCHORED")

    def test_comparative_without_an_anchor_is_unanchored(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nThe kernel runs faster than the baseline.\n"}
        )
        self.assert_one(self.check(root), "UNANCHORED")

    def test_prose_with_neither_numeral_nor_verb_nor_comparative_is_not_a_candidate(
        self,
    ) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nThis document describes the layout of the tree.\n"}
        )
        self.assert_none(self.check(root), "UNANCHORED")

    def test_non_claim_token_classes_are_removed_before_numeral_matching(self) -> None:
        # semantic version, ISO date, section number, RFC number: none of these
        # is a measurement, and the contract names each as a removed class.
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nThe pinned toolchain is v1.2.3 as at 2026-01-01; see "
                    "§71.2 and RFC 2119.\n"
                )
            }
        )
        self.assert_none(self.check(root), "UNANCHORED")

    def test_numeral_inside_a_plain_code_fence_is_skipped(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nThis document describes the layout of the tree.\n\n"
                    "```\n" + SENTENCE + "\n```\n"
                )
            }
        )
        self.assert_none(self.check(root), "UNANCHORED")

    def test_numeral_inside_a_text_claim_fence_is_a_candidate(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\nThis document describes the layout of the tree.\n\n"
                    "```text claim\n" + SENTENCE + "\n```\n"
                )
            }
        )
        self.assert_one(self.check(root), "UNANCHORED")

    def test_moving_a_banned_sentence_into_a_fence_does_not_hide_it(self) -> None:
        # the fence-skip applies to candidate detection; repairing a banned
        # phrase by fencing it is a named evasion the contract forbids
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\n```\nSPECTRA guarantees the bundle is whole.\n```\n"
                )
            }
        )
        self.assert_one(self.check(root), "BANNED")

    def test_list_item_is_one_unit(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\n"
                    "- The kernel reconstructs 42 attack paths in the sample bundle.\n"
                    "- This item describes the layout of the tree.\n"
                )
            }
        )
        self.assert_one(self.check(root), "UNANCHORED")

    def test_two_unanchored_sentences_are_two_findings(self) -> None:
        root = self.repo(
            {
                "README.md": (
                    "# Demo\n\n"
                    "The kernel reconstructs 42 attack paths in the sample bundle. "
                    "The kernel proves the goal atom is absent.\n"
                )
            }
        )
        findings = self.check(root)
        self.assertEqual(2, len(sel(findings, "UNANCHORED")), render(findings))


# ---------------------------------------------------------------------------
# 6. G-CLAIM-REGISTERED
# ---------------------------------------------------------------------------


class TestRegisteredGate(ClaimsCase):
    def test_anchor_without_a_record_is_unregistered(self) -> None:
        root = self.repo({"README.md": "# Demo\n\n<!-- CLM-0009 -->\n" + SENTENCE + "\n"})
        findings = self.check(root)
        finding = self.assert_one(findings, "UNREGISTERED")
        self.assertIn("CLM-0009", blob(finding), render(findings))

    def test_registered_sentence_is_not_unregistered(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        self.assert_none(self.check(root), "UNREGISTERED")

    def test_paraphrase_is_text_drift(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE_DRIFTED + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        findings = self.check(root)
        drift = self.assert_one(findings, "TEXT_DRIFT")
        self.assertIn("CLM-0001", blob(drift), render(findings))

    def test_two_documents_stating_different_counts_drift(self) -> None:
        # README matches the record; the guide states a different count for the
        # same registered claim.
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "docs/guide.md": "# Guide\n\n<!-- CLM-0001 -->\n" + SENTENCE_DRIFTED + "\n",
                "CLAIMS.md": registry(
                    record(
                        "CLM-0001",
                        text=SENTENCE,
                        surfaces=("README.md#claims", "docs/guide.md#claims"),
                    )
                ),
            }
        )
        findings = self.check(root)
        drift = self.assert_one(findings, "TEXT_DRIFT")
        self.assertIn("GUIDE.MD", (path_of(drift) or blob(drift)).upper(), render(findings))

    def test_text_drift_finding_carries_a_diff(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE_DRIFTED + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        drift = self.assert_one(self.check(root), "TEXT_DRIFT")
        body = blob(drift)
        self.assertIn("42", body, "the diff must show the registered text")
        self.assertIn("7 ATTACK PATHS", body, "the diff must show the surface text")

    def test_unit_on_a_surface_the_record_does_not_declare(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(
                    record("CLM-0001", text=SENTENCE, surfaces=("docs/guide.md#claims",))
                ),
                "docs/guide.md": "# Guide\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
            }
        )
        findings = self.check(root)
        undeclared = self.assert_one(findings, "SURFACE_UNDECLARED")
        self.assertIn("README.MD", (path_of(undeclared) or blob(undeclared)).upper())

    def test_record_matching_no_surface_is_an_orphan(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\nThis document describes the layout of the tree.\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        findings = self.check(root)
        orphan = self.assert_one(findings, "ORPHAN")
        self.assertIn("CLM-0001", blob(orphan), render(findings))
        self.assertIn(
            "CLAIMS.MD",
            (path_of(orphan) or blob(orphan)).upper(),
            "ORPHAN is reported against the registry, not a surface",
        )

    def test_matched_record_is_not_an_orphan(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        self.assert_none(self.check(root), "ORPHAN")

    def test_deleting_the_sentence_but_keeping_the_record_is_caught(self) -> None:
        # repair-by-deletion, half one: the record survives the sentence
        root = self.repo(
            {
                "README.md": "# Demo\n\nThis document describes the layout of the tree.\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE)),
            }
        )
        self.assert_one(self.check(root), "ORPHAN")

    def test_deleting_the_record_but_keeping_the_sentence_is_caught(self) -> None:
        # repair-by-deletion, half two: the sentence survives the record
        root = self.repo({"README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n"})
        self.assert_one(self.check(root), "UNREGISTERED")

    def test_tuned_record_on_the_readme_is_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE, status="TUNED")),
            }
        )
        findings = self.check(root)
        tuned = self.assert_one(findings, "TUNED_ON_HEADLINE")
        self.assertIn("CLM-0001", blob(tuned), render(findings))

    def test_green_record_on_the_readme_is_not_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE, status="GREEN")),
            }
        )
        self.assert_none(self.check(root), "TUNED_ON_HEADLINE")

    def test_held_out_record_on_the_readme_is_not_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(record("CLM-0001", text=SENTENCE, status="HELD_OUT")),
            }
        )
        self.assert_none(self.check(root), "TUNED_ON_HEADLINE")

    def test_tuned_record_on_a_non_headline_surface_is_not_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\nThis document describes the layout of the tree.\n",
                "docs/eval.md": "# Eval\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(
                    record(
                        "CLM-0001",
                        text=SENTENCE,
                        surfaces=("docs/eval.md#results",),
                        status="TUNED",
                    )
                ),
            }
        )
        self.assert_none(self.check(root), "TUNED_ON_HEADLINE")


# ---------------------------------------------------------------------------
# 7. G-CLAIM-SUPPORT / G-CLAIM-NUMSRC (record-side half only)
# ---------------------------------------------------------------------------


class TestSupportAndNumbers(ClaimsCase):
    """The resolver half of G-CLAIM-SUPPORT needs an artifacts/ tree that does
    not exist yet.  These tests cover the record-side states the contract does
    determine without a true BLAKE3 digest."""

    def test_support_artifact_that_does_not_exist_is_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(
                    record("CLM-0001", text=SENTENCE, artifact="artifacts/demo/summary.json")
                ),
            }
        )
        findings = self.check(root)
        finding = self.assert_some(findings, "MISSING_ARTIFACT")
        self.assertIn("ARTIFACTS/DEMO/SUMMARY.JSON", blob(finding).replace("\\\\", "/"))

    def test_quant_numeral_absent_from_the_artifact_is_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\nThe audit resolved 84 findings.\n",
                "artifacts/demo/summary.json": '{"resolved": 12}\n',
                "CLAIMS.md": registry(
                    record("CLM-0001", text="The audit resolved 84 findings.", kind="QUANT")
                ),
            }
        )
        self.assert_some(self.check(root), "NUMBER_NOT_IN_ARTIFACT")

    def test_quant_numeral_present_in_the_artifact_is_not_reported(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\nThe audit resolved 84 findings.\n",
                "artifacts/demo/summary.json": '{"resolved": 84}\n',
                "CLAIMS.md": registry(
                    record("CLM-0001", text="The audit resolved 84 findings.", kind="QUANT")
                ),
            }
        )
        self.assert_none_any(self.check(root), "NUMBER_NOT_IN_ARTIFACT")

    def test_non_quant_record_is_not_number_checked(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\nThe audit resolved 84 findings.\n",
                "artifacts/demo/summary.json": '{"resolved": 12}\n',
                "CLAIMS.md": registry(
                    record(
                        "CLM-0001",
                        text="The audit resolved 84 findings.",
                        kind="CAPABILITY",
                    )
                ),
            }
        )
        self.assert_none_any(self.check(root), "NUMBER_NOT_IN_ARTIFACT")


# ---------------------------------------------------------------------------
# 8. G-CLAIM-PLACEHOLDER
# ---------------------------------------------------------------------------


TAG = "(illustrative, not a target)"
MEASURED = "<<MEASURED:flagged_run_share>>"


class TestPlaceholderTokens(ClaimsCase):
    def test_illustrative_tag_inside_docs_prompt_is_allowed(self) -> None:
        root = self.repo(
            {"docs/prompt/part2/71-claims.md": "# 71\n\nbudget 5 s " + TAG + "\n"}
        )
        self.assert_none(self.check(root), "PLACEHOLDER")

    def test_measured_token_inside_docs_prompt_is_allowed(self) -> None:
        root = self.repo({"docs/prompt/part2/71-claims.md": "# 71\n\n" + MEASURED + "\n"})
        self.assert_none(self.check(root), "PLACEHOLDER")

    def test_illustrative_tag_in_the_readme_is_reported(self) -> None:
        root = self.repo({"README.md": "# Demo\n\nThe budget is 5 s " + TAG + "\n"})
        findings = self.check(root)
        finding = self.assert_one(findings, "PLACEHOLDER")
        self.assertIn("README.MD", (path_of(finding) or blob(finding)).upper())

    def test_illustrative_tag_in_docs_outside_prompt_is_reported(self) -> None:
        root = self.repo(
            {"docs/adr/0001-example.md": "# ADR\n\nThe budget is 5 s " + TAG + "\n"}
        )
        self.assert_one(self.check(root), "PLACEHOLDER")

    def test_measured_token_outside_docs_prompt_is_reported(self) -> None:
        root = self.repo({"docs/guide.md": "# Guide\n\n" + MEASURED + "\n"})
        self.assert_one(self.check(root), "PLACEHOLDER")

    def test_clean_tree_reports_no_placeholder(self) -> None:
        root = self.repo({"docs/guide.md": "# Guide\n\nThis document describes the tree.\n"})
        self.assert_none(self.check(root), "PLACEHOLDER")


# ---------------------------------------------------------------------------
# 9. G-LIMITS-NOHAND
# ---------------------------------------------------------------------------


def generated_block(block_id: str, body: str) -> str:
    return (
        "<!-- BEGIN GENERATED: {0}  src=artifacts/limits/limits.json  "
        "run=none  gen=make-limitations -->\n"
        "{1}\n"
        "<!-- END GENERATED: {0} -->\n"
    ).format(block_id, body)


class TestLimitationsNoHandWrittenNumerals(ClaimsCase):
    NOT_MEASURED = "**NOT MEASURED.** This block blocks release; see gate G-LIMITS-COMPLETE."

    def limits_findings(self, body: str) -> list[Any]:
        root = self.repo({"LIMITATIONS.md": body})
        findings = self.check(root)
        return [f for f in findings if "NOHAND" in tags_of(f) or "G-LIMITS" in tags_of(f)]

    def test_current_shape_of_the_file_passes(self) -> None:
        body = (
            "# Limitations\n\nProse frames the measurement; it never states one.\n\n"
            + generated_block("er_error", self.NOT_MEASURED)
            + "\n"
            + generated_block("flagged_run_share", self.NOT_MEASURED)
        )
        self.assertEqual([], self.limits_findings(body))

    def test_numeral_inside_a_generated_block_passes(self) -> None:
        body = (
            "# Limitations\n\nProse frames the measurement.\n\n"
            + generated_block("flagged_run_share", "Flagged runs: 33 of 100.")
        )
        self.assertEqual([], self.limits_findings(body))

    def test_numeral_outside_a_generated_block_fails(self) -> None:
        body = (
            "# Limitations\n\nRoughly 33 percent of runs are flagged.\n\n"
            + generated_block("flagged_run_share", self.NOT_MEASURED)
        )
        findings = self.limits_findings(body)
        self.assertEqual(1, len(findings), render(findings))
        line = line_of(findings[0])
        if line is not None:
            self.assertEqual(3, line, render(findings))

    def test_numeral_after_the_end_marker_fails(self) -> None:
        body = (
            "# Limitations\n\nProse frames the measurement.\n\n"
            + generated_block("flagged_run_share", self.NOT_MEASURED)
            + "\nRoughly 33 percent of runs are flagged.\n"
        )
        self.assertEqual(1, len(self.limits_findings(body)))

    def test_version_outside_a_block_is_not_a_hand_written_numeral(self) -> None:
        # the same non-claim token classes as the NUMERAL candidate regex
        body = (
            "# Limitations\n\nThe pinned toolchain is v1.2.3 as at 2026-01-01; "
            "see §71.2.\n\n"
            + generated_block("flagged_run_share", self.NOT_MEASURED)
        )
        self.assertEqual([], self.limits_findings(body))

    def test_a_numeral_in_another_document_is_not_a_limits_finding(self) -> None:
        root = self.repo(
            {
                "LIMITATIONS.md": "# Limitations\n\nProse frames the measurement.\n",
                "docs/guide.md": "# Guide\n\nRoughly 33 percent of runs are flagged.\n",
            }
        )
        findings = self.check(root)
        self.assertEqual(
            [], [f for f in findings if "NOHAND" in tags_of(f)], render(findings)
        )


# ---------------------------------------------------------------------------
# 10. G-FRAMING-README
# ---------------------------------------------------------------------------


ONELINE = (
    "SPECTRA reconstructs a recorded telemetry bundle into a machine-checkable certificate."
)
DISCLAIMER = (
    "SPECTRA reasons about its own model of a bundle and makes no statement about reality."
)
FRAMING_TOML = '[oneline]\ntext = "{0}"\n\n[disclaimer]\ntext = "{1}"\n'.format(
    ONELINE, DISCLAIMER
)
LIMITS_LINK = "[Limitations and known-unsound regions](LIMITATIONS.md)"


class TestFramingReadme(ClaimsCase):
    """The first screen is the byte range from the start of README.md to the
    first ``\\n## `` heading."""

    def framing_findings(self, readme: str, framing: str | None = FRAMING_TOML) -> list[Any]:
        files: dict[str, Any] = {"README.md": readme}
        if framing is not None:
            files["docs/framing.toml"] = framing
        findings = self.check(self.repo(files))
        return [f for f in findings if "FRAMING" in tags_of(f)]

    def clean_readme(self) -> str:
        return (
            "# SPECTRA\n\n"
            + ONELINE
            + "\n\n"
            + DISCLAIMER
            + "\n\n"
            + LIMITS_LINK
            + "\n\n## Install\n\nNothing is implemented.\n"
        )

    def test_first_screen_with_all_three_in_order_passes(self) -> None:
        self.assertEqual([], self.framing_findings(self.clean_readme()))

    def test_missing_oneline_fails(self) -> None:
        readme = self.clean_readme().replace(ONELINE + "\n\n", "")
        self.assertTrue(self.framing_findings(readme))

    def test_missing_disclaimer_fails(self) -> None:
        readme = self.clean_readme().replace(DISCLAIMER + "\n\n", "")
        self.assertTrue(self.framing_findings(readme))

    def test_missing_limitations_link_fails(self) -> None:
        readme = self.clean_readme().replace(LIMITS_LINK + "\n\n", "")
        self.assertTrue(self.framing_findings(readme))

    def test_near_copy_of_the_disclaimer_fails(self) -> None:
        readme = self.clean_readme().replace(
            DISCLAIMER, DISCLAIMER.replace("reality", "the world")
        )
        self.assertTrue(self.framing_findings(readme), "the copy must be byte-identical")

    def test_out_of_order_framing_fails(self) -> None:
        readme = (
            "# SPECTRA\n\n"
            + DISCLAIMER
            + "\n\n"
            + ONELINE
            + "\n\n"
            + LIMITS_LINK
            + "\n\n## Install\n\nNothing is implemented.\n"
        )
        self.assertTrue(self.framing_findings(readme))

    def test_framing_after_the_first_heading_is_not_on_the_first_screen(self) -> None:
        readme = (
            "# SPECTRA\n\n## Install\n\n"
            + ONELINE
            + "\n\n"
            + DISCLAIMER
            + "\n\n"
            + LIMITS_LINK
            + "\n"
        )
        self.assertTrue(self.framing_findings(readme))

    def test_wrong_link_anchor_text_fails(self) -> None:
        readme = self.clean_readme().replace(
            LIMITS_LINK, "[Limitations](LIMITATIONS.md)"
        )
        self.assertTrue(self.framing_findings(readme))

    def test_link_to_the_wrong_target_fails(self) -> None:
        readme = self.clean_readme().replace(
            LIMITS_LINK, "[Limitations and known-unsound regions](docs/limits.md)"
        )
        self.assertTrue(self.framing_findings(readme))


# ---------------------------------------------------------------------------
# 11. G-CLAIM-ALLOWCAP -- only the parts the contract pins down
# ---------------------------------------------------------------------------


class TestNonClaimAllowlist(ClaimsCase):
    def test_absent_allowlist_does_not_crash(self) -> None:
        self.check(self.repo({"README.md": "# Demo\n\nThis document describes the tree.\n"}))

    def test_unparseable_allowlist_is_reported_not_raised(self) -> None:
        root = self.repo({"docs/claims-nonclaims.toml": "this is [not toml\n"})
        findings = self.check(root)
        self.assert_some(findings, "CLAIMS-NONCLAIMS.TOML")

    def test_allowlist_does_not_suppress_a_banned_phrase(self) -> None:
        # G-CLAIM-BANNED has no allowlist; the non-claim allowlist does not
        # cover it, whatever the entry says.
        root = self.repo(
            {
                "README.md": "# Demo\n\nSPECTRA guarantees the bundle is whole.\n",
                "docs/claims-nonclaims.toml": (
                    "[[entry]]\n"
                    'file = "README.md"\n'
                    'hash = "' + "0" * 64 + '"\n'
                    'reason = "this entry attempts to exempt a banned phrase from an '
                    'unwaivable gate"\n'
                    'owner = "tests"\n'
                    'date = "2026-01-01"\n'
                ),
            }
        )
        self.assert_one(self.check(root), "BANNED")


# ---------------------------------------------------------------------------
# 12. G-CLAIM-NOERASE
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="spectra tests",
        GIT_AUTHOR_EMAIL="tests@example.invalid",
        GIT_COMMITTER_NAME="spectra tests",
        GIT_COMMITTER_EMAIL="tests@example.invalid",
        GIT_CONFIG_NOSYSTEM="1",
        HOME=str(root),
        USERPROFILE=str(root),
    )
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class TestNoErase(ClaimsCase):
    def history(self, first: str, second: str) -> list[Any]:
        root = self.repo({"CLAIMS.md": first})
        if _git(root, "init", "-q").returncode != 0:
            self.skipTest("git init failed in this environment")
        _git(root, "add", "-A")
        if _git(root, "commit", "-q", "-m", "first", "--no-gpg-sign").returncode != 0:
            self.skipTest("git commit failed in this environment")
        with open(root / "CLAIMS.md", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(second)
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "second", "--no-gpg-sign")
        return self.check(root)

    def test_id_deleted_from_the_registry_is_reported(self) -> None:
        findings = self.history(registry(record("CLM-0001", text=SENTENCE)), registry())
        self.assert_some(findings, "CLM-0001", "NOERASE")

    def test_id_kept_as_retired_is_not_reported(self) -> None:
        retired = registry(
            record(
                "CLM-0001",
                text=SENTENCE,
                status="RETIRED",
                note="retired after the supporting run was withdrawn",
            )
        )
        findings = self.history(registry(record("CLM-0001", text=SENTENCE)), retired)
        self.assert_none_any(findings, "NOERASE")

    def test_id_still_live_is_not_reported(self) -> None:
        live = registry(record("CLM-0001", text=SENTENCE))
        findings = self.history(live, live)
        self.assert_none_any(findings, "NOERASE")

    def test_non_git_tree_does_not_crash(self) -> None:
        self.check(self.repo({"CLAIMS.md": registry(record("CLM-0001", text=SENTENCE))}))


# ---------------------------------------------------------------------------
# 13. files that cannot be decoded or parsed
# ---------------------------------------------------------------------------


class TestUndecodableAndUnparseableInputs(ClaimsCase):
    def test_markdown_surface_with_invalid_utf8_is_reported_not_raised(self) -> None:
        root = self.repo({"docs/broken.md": b"# Broken\n\n\xff\xfe\x00not utf-8\xff\n"})
        findings = self.check(root)
        self.assert_some(findings, "BROKEN.MD")

    def test_registry_with_invalid_utf8_is_reported_not_raised(self) -> None:
        root = self.repo({"CLAIMS.md": b"# SPECTRA CLAIMS REGISTRY\n\n\xff\xfe\x00\n"})
        findings = self.check(root)
        self.assert_some(findings, "CLAIMS.MD")

    def test_unparseable_toml_surface_is_reported_not_raised(self) -> None:
        root = self.repo({"docs/repo-metadata.toml": "github_about = [unclosed\n"})
        findings = self.check(root)
        self.assert_some(findings, "REPO-METADATA.TOML")

    def test_unparseable_json_string_catalog_is_reported_not_raised(self) -> None:
        root = self.repo({"frontend/src/strings/en.json": '{"verdict.subtitle": '})
        findings = self.check(root)
        self.assert_some(findings, "EN.JSON")

    def test_unparseable_banned_table_is_reported_not_raised(self) -> None:
        root = self.repo({"docs/banned.toml": "[[pattern]\nid = BP-01\n"})
        findings = self.check(root)
        self.assert_some(findings, "BANNED.TOML")

    def test_a_broken_file_does_not_stop_the_other_checks(self) -> None:
        root = self.repo(
            {
                "docs/broken.md": b"\xff\xfe\x00\n",
                "README.md": "# Demo\n\nSPECTRA guarantees the bundle is whole.\n",
            }
        )
        self.assert_one(self.check(root), "BANNED")

    def test_dangling_symlink_where_a_surface_is_expected_does_not_crash(self) -> None:
        root = self.repo({"README.md": "# Demo\n\nThis document describes the tree.\n"})
        link = root / "docs" / "dangling.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(root / "docs" / "missing.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available in this environment")
        self.check(root)


# ---------------------------------------------------------------------------
# 14. cases this repository actually hit, whose finding kind the contract does
#     not fix.  These assert what the contract DOES fix everywhere: no crash, a
#     deterministic report, an unmodified tree, and -- when the tool does report
#     the case -- a finding that names the offending path.
# ---------------------------------------------------------------------------


class TestCasesWithoutAContractedFindingKind(ClaimsCase):
    def _stable_and_named(self, root: Path, needle: str) -> None:
        before = snapshot(root)
        findings = self.check(root)
        self.assertEqual(before, snapshot(root), "the tool must not edit the tree")
        hits = sel_any(findings, needle.upper())
        for hit in hits:
            self.assertTrue(
                (path_of(hit) or str(hit)).strip(),
                "a finding about {0} must name a path:\n{1}".format(needle, render(hits)),
            )

    def test_document_referencing_a_path_that_does_not_exist(self) -> None:
        root = self.repo(
            {"README.md": "# Demo\n\nSee [the range notes](docs/range/not-modeled.md).\n"}
        )
        self._stable_and_named(root, "docs/range/not-modeled.md")

    def test_document_naming_a_make_target_that_is_not_declared(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\nRun `make claims-gen` to regenerate the copies.\n",
                "CLAIMS.md": registry(
                    record("CLM-0001", text=SENTENCE, target="claims-gen")
                ),
                "Makefile": MAKEFILE,  # declares claims-check and claims-refresh only
            }
        )
        self._stable_and_named(root, "claims-gen")

    def test_declared_make_target_is_not_reported_as_missing(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + SENTENCE + "\n",
                "CLAIMS.md": registry(
                    record("CLM-0001", text=SENTENCE, target="claims-check")
                ),
            }
        )
        findings = self.check(root)
        for finding in findings:
            identity = "{0} {1}".format(kind_of(finding), gate_of(finding)).upper()
            self.assertNotIn(
                "TARGET",
                identity,
                "a declared make target must not be reported as undeclared:\n"
                + render([finding]),
            )

    def test_two_documents_stating_different_counts_without_anchors(self) -> None:
        root = self.repo(
            {
                "README.md": "# Demo\n\nThe registry declares 11 gates.\n",
                "docs/guide.md": "# Guide\n\nThe registry declares 9 gates.\n",
            }
        )
        before = snapshot(root)
        findings = self.check(root)
        self.assertEqual(before, snapshot(root))
        # what the contract does fix: both numerals are unanchored candidates
        self.assertEqual(2, len(sel(findings, "UNANCHORED")), render(findings))

    def test_count_cited_with_its_artifact_named_in_the_same_sentence(self) -> None:
        # the contract-fixed form of "the artifact is named but the count is
        # wrong": a QUANT record whose numeral is absent from support.artifact
        text = "The gate registry in ci/gates.toml declares 9 claim gates."
        root = self.repo(
            {
                "README.md": "# Demo\n\n<!-- CLM-0001 -->\n" + text + "\n",
                "artifacts/demo/summary.json": '{"claim_gates": 11}\n',
                "CLAIMS.md": registry(record("CLM-0001", kind="QUANT", text=text)),
            }
        )
        self.assert_some(self.check(root), "NUMBER_NOT_IN_ARTIFACT")


# ---------------------------------------------------------------------------
# 15. optional: the real tree.  Opt-in, because docs/prompt/ is large.
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    os.environ.get("SPECTRA_TEST_REAL_TREE"),
    "set SPECTRA_TEST_REAL_TREE=1 to run the checker over this repository",
)
class TestAgainstTheRealRepository(unittest.TestCase):
    def test_runs_without_crashing_and_changes_nothing(self) -> None:
        before = snapshot(REPO_ROOT / "docs")
        findings = run_checks(root=REPO_ROOT)
        self.assertIsInstance(findings, list)
        self.assertEqual(before, snapshot(REPO_ROOT / "docs"))


if __name__ == "__main__":
    unittest.main()
