"""Unit tests for the evaluation of pre-registration 0001 in spectra_vs.demo.

Run from the repository root:

    python python/spectra_vs/tests/test_demo_prereg.py

The registration (docs/research/prereg-0001-blackout-cell.md, commit ce8ed9c) fixes a source,
a window and three predicted quantities, and says that nothing in it may change after the run.
These tests pin the constants the demo compares against to the registered values, check that
each falsifier fails on its own, and check that the prediction is evaluated only for the run
it was made for.

They build a stand-in cell with only the attributes the evaluator reads, so they run in
milliseconds and do not exercise the pipeline. The pipeline's side is the gate
G-VS-PREREG-0001 (`make vs-prereg-0001`), which runs the whole demonstration.
"""

from __future__ import annotations

import pathlib
import sys
import types
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_vs import demo  # noqa: E402


def _cell(
    *, psi_min: int = 1, psi_max: int = 2, premium: tuple[str, ...] | None = ("ctl:priv_approval",)
) -> demo.Rendered:
    """A stand-in blackout cell. `premium=None` means the premium was suppressed."""
    bracket = types.SimpleNamespace(
        lower=types.SimpleNamespace(psi=types.SimpleNamespace(corridors=(object(),) * psi_min)),
        upper=types.SimpleNamespace(psi=types.SimpleNamespace(corridors=(object(),) * psi_max)),
    )
    result = types.SimpleNamespace(
        published=premium is not None, blindness_premium=premium or ()
    )
    prove = types.SimpleNamespace(bracket=bracket, premium=result)
    return demo.Rendered(label="blackout", cell=types.SimpleNamespace(prove=prove))


class TestTheConstantsAreTheRegisteredValues(unittest.TestCase):
    """Editing one of these to match a result is the defect the registration forbids."""

    def test_the_intervention(self) -> None:
        self.assertEqual(demo.PREREG_0001_SOURCE, "iam_audit")
        self.assertEqual(demo.PREREG_0001_WINDOW_S, (4200, 4800))

    def test_the_predictions(self) -> None:
        self.assertEqual(demo.PREREG_0001_PSI_MIN, 1)
        self.assertEqual(demo.PREREG_0001_PSI_MAX, 2)
        self.assertEqual(demo.PREREG_0001_PREMIUM, ("ctl:priv_approval",))

    def test_the_seeds(self) -> None:
        self.assertEqual(demo.PREREG_0001_ANALYSIS_SEED, 7)
        self.assertEqual(demo.PREREG_0001_CALIBRATION_SEED, 1000007)


class TestEachFalsifierFailsOnItsOwn(unittest.TestCase):
    def test_the_predicted_cell_holds(self) -> None:
        self.assertTrue(demo.prereg_0001_held(_cell()))

    def test_a_suppressed_premium_fails(self) -> None:
        self.assertFalse(demo.prereg_0001_held(_cell(premium=None)))

    def test_an_empty_premium_fails(self) -> None:
        self.assertFalse(demo.prereg_0001_held(_cell(premium=())))

    def test_an_extra_control_fails(self) -> None:
        cell = _cell(premium=("ctl:egress_seg", "ctl:priv_approval"))
        self.assertFalse(demo.prereg_0001_held(cell))

    def test_a_different_control_fails(self) -> None:
        self.assertFalse(demo.prereg_0001_held(_cell(premium=("ctl:egress_seg",))))

    def test_a_disturbed_route_a_fails(self) -> None:
        self.assertFalse(demo.prereg_0001_held(_cell(psi_min=2)))

    def test_a_missing_route_b_fails(self) -> None:
        self.assertFalse(demo.prereg_0001_held(_cell(psi_max=1)))

    def test_every_check_is_reported(self) -> None:
        """Five falsifiers, rendered PASS or FAIL one per line."""
        rendered = demo.render_prereg_0001(_cell(psi_max=3))
        self.assertEqual(rendered.count("  PASS  "), 4)
        self.assertEqual(rendered.count("  FAIL  "), 1)
        self.assertIn("PREDICTION FAILED", rendered)


class TestThePredictionIsNotTransferred(unittest.TestCase):
    def test_it_applies_to_the_registered_seeds(self) -> None:
        self.assertTrue(demo.prereg_0001_applies(seed=7, calibration_seed=1000007))

    def test_another_analysis_seed_is_not_evaluated(self) -> None:
        self.assertFalse(demo.prereg_0001_applies(seed=8, calibration_seed=1000007))

    def test_another_calibration_seed_is_not_evaluated(self) -> None:
        self.assertFalse(demo.prereg_0001_applies(seed=7, calibration_seed=1000008))


class TestTheResultDocument(unittest.TestCase):
    """The machine-readable outcome a CLAIMS record points at.

    A claim that states a number may carry it on a surface only if the numerals occur in
    the artifact its record names, so the document has to hold the figures the prose uses
    and nothing that differs between machines.
    """

    def _rendered(self) -> demo.Rendered:
        upper = types.SimpleNamespace(
            psi=types.SimpleNamespace(corridors=(object(), object())),
            cut=types.SimpleNamespace(atoms=()),
        )
        lower = types.SimpleNamespace(psi=types.SimpleNamespace(corridors=(object(),)))
        prove = types.SimpleNamespace(
            bracket=types.SimpleNamespace(lower=lower, upper=upper),
            premium=types.SimpleNamespace(published=True, blindness_premium=("ctl:priv_approval",)),
            licences=(object(), object(), object()),
            verdict_at_cut_max=types.SimpleNamespace(
                safety=types.SimpleNamespace(value="OPTIMISTIC_ONLY")
            ),
        )
        cell = types.SimpleNamespace(prove=prove, run_id="vs-0123456789abcdef")
        return demo.Rendered(label="blackout cell  (PRE-REGISTERED 0001)", cell=cell)

    def _document(self) -> dict:
        checks = (("premium non-empty", True, "('ctl:priv_approval',)"),)
        return demo.result_document("prereg-0001", checks, (self._rendered(),))

    def test_it_carries_the_figures_the_prose_uses(self) -> None:
        document = self._document()
        run = document["runs"][0]
        self.assertEqual(run["psi_min"], 1)
        self.assertEqual(run["psi_max"], 2)
        self.assertEqual(run["premium"], ["ctl:priv_approval"])
        self.assertEqual(document["passed"], 1)
        self.assertEqual(document["total"], 1)
        self.assertTrue(document["held"])

    def test_it_carries_no_path_and_no_clock(self) -> None:
        """Two machines that agree must produce the same bytes, so a run directory, a
        host name and a timestamp may not appear."""
        rendered = repr(self._document())
        for forbidden in ("\\", "/", "Academics", "run_dir", "T00:", "202"):
            self.assertNotIn(forbidden, rendered, forbidden)

    def test_it_is_a_function_of_its_inputs(self) -> None:
        self.assertEqual(self._document(), self._document())


class TestExitStatuses(unittest.TestCase):
    def test_they_are_distinct(self) -> None:
        codes = {demo.EXIT_OK, demo.EXIT_CHECKER_REJECTED, demo.EXIT_PREDICTION_FAILED}
        self.assertEqual(codes, {0, 1, 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
