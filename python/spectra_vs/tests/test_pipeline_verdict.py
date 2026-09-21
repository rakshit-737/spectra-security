"""Unit tests for where spectra_vs.pipeline gets the inputs to a ROBUST verdict's token.

Run from the repository root:

    python python/spectra_vs/tests/test_pipeline_verdict.py

A ROBUST verdict needs a NoTamperToken, and the token may be minted only when no source is
tamper_suspected and the liveness document is not tamper-sensitive. The pipeline used to
pass both as literals - an empty tuple and False - instead of reading them from the
liveness document. In this slice the two are the same thing, because the backdating pass
does not exist and the liveness types refuse a true value. They stop being the same the
moment the pass is added, and nothing would have noticed.

The real liveness types cannot hold a suspected source yet, so these tests hand the
builder a stand-in document with the two attributes it reads. That is the point: they pin
WHICH object the pipeline consults, which is the property the literals broke.
"""

from __future__ import annotations

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
        witness_has_ghost=False,
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


class TestTheSliceStillHasNoTamperPass(unittest.TestCase):
    """If this fails, the pass exists and the demo's caveats about it must be revisited."""

    def test_the_pass_is_not_implemented(self) -> None:
        self.assertFalse(liveness_mod.TAMPER_PASS_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
