"""Unit tests for where spectra_vs.pipeline gets the inputs to a ROBUST verdict's token,
and for the environment it gives the checker subprocess.

Run from the repository root:

    python python/spectra_vs/tests/test_pipeline_verdict.py

A ROBUST verdict needs a NoTamperToken, and the token may be minted only when no source is
tamper_suspected and the liveness document is not tamper-sensitive. The pipeline used to
pass both as literals - an empty tuple and False - instead of reading them from the
liveness document. That was invisible while the pass did not exist and nothing could be
suspected; it would have been silently wrong the moment one could, which is now.

These tests hand the builder a stand-in document carrying the two attributes it reads,
because what they pin is WHICH object the pipeline consults. The real document's side of
the same property is tested in test_liveness.py and end to end by the pre-registered
backdate cell.
"""

from __future__ import annotations

import os
import pathlib
import sys
import types
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import errors, model  # noqa: E402

from spectra_vs import cert as cert_mod  # noqa: E402
from spectra_vs import liveness as liveness_mod  # noqa: E402
from spectra_vs import pipeline  # noqa: E402


def _document(*suspected: bool, tamper_sensitive: bool = False) -> types.SimpleNamespace:
    """A stand-in carrying only what _build_verdict reads from a LivenessDocument."""
    sources = tuple(
        types.SimpleNamespace(source_id=f"src:s{index}", tamper_suspected=flag)
        for index, flag in enumerate(suspected)
    )
    flags = types.SimpleNamespace(verdict_tamper_sensitive=tamper_sensitive)
    return types.SimpleNamespace(sources=sources, flags=flags)


def _build(document: types.SimpleNamespace, safety: cert_mod.Safety) -> cert_mod.Verdict:
    return pipeline._build_verdict(
        safety=safety,
        minimality=model.Minimality.EXACT_PSI_RELATIVE,
        flags=(),
        witness_has_silent=False,
        liveness=document,
    )


class TestTamperInputsComeFromTheLivenessDocument(unittest.TestCase):
    def test_a_clean_document_mints_robust(self) -> None:
        verdict = _build(_document(False, False, False), cert_mod.Safety.ROBUST)
        self.assertIs(verdict.safety, cert_mod.Safety.ROBUST)

    def test_a_suspected_source_blocks_robust(self) -> None:
        with self.assertRaises(errors.VerdictError):
            _build(_document(False, True, False), cert_mod.Safety.ROBUST)

    def test_a_tamper_sensitive_document_blocks_robust(self) -> None:
        with self.assertRaises(errors.VerdictError):
            _build(_document(False, False, tamper_sensitive=True), cert_mod.Safety.ROBUST)

    def test_a_non_robust_verdict_needs_no_token(self) -> None:
        """Only ROBUST carries the token, so suspicion does not block the others."""
        verdict = _build(_document(True), cert_mod.Safety.OPTIMISTIC_ONLY)
        self.assertIs(verdict.safety, cert_mod.Safety.OPTIMISTIC_ONLY)


class TestTheCheckerEnvironment(unittest.TestCase):
    """The checker subprocess once joined PYTHONPATH with a literal ";". That is the Windows
    separator, so the development machine never noticed; on Linux it named one nonexistent
    directory and the checker could not import itself."""

    def test_pythonpath_splits_into_existing_directories_on_this_platform(self) -> None:
        env = pipeline._checker_env(_REPO_ROOT)
        entries = env["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(len(entries), 2, env["PYTHONPATH"])
        for entry in entries:
            self.assertTrue(pathlib.Path(entry).is_dir(), entry)

    def test_the_checker_package_is_on_it_and_the_emitter_is_not(self) -> None:
        entries = pipeline._checker_env(_REPO_ROOT)["PYTHONPATH"].split(os.pathsep)
        self.assertTrue((pathlib.Path(entries[0]) / "spectra_vs_verify").is_dir())
        self.assertFalse(any(pathlib.Path(e, "spectra_vs").is_dir() for e in entries))


class TestTheTamperPassExists(unittest.TestCase):
    """This test used to assert the opposite, and it is why the caveats were revisited.

    It was written to fail the day the pass arrived (ADR-0016), so that the demo could not
    go on printing "no tamper check exists" once one did.
    """

    def test_the_pass_is_implemented(self) -> None:
        self.assertTrue(liveness_mod.TAMPER_PASS_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
