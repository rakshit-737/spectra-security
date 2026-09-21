"""Unit tests for the witness-depth bound in spectra_vs.pipeline.

Run from the repository root:

    python python/spectra_vs/tests/test_pipeline_witness.py

Regression for the third end-to-end run. Once the goal library became a set, route A was
correctly found derivable in P_min, and for the first time a real multi-step derivation
reached the certificate emitter as a witness tree. The certificate contract caps nesting
at cert.MAX_DEPTH containers, which admits a root and one level of children, so the deeper
tree was refused inside cert.emit - and that refusal aborted the whole run rather than
dropping one witness.

The fix detects the depth before emission and sends the tree down the existing, reported
refusal path. These tests pin the bound, its derivation from the shared contract
constant, and the height measure it is compared against.
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import ids, model  # noqa: E402

from spectra_vs import cert as cert_mod  # noqa: E402
from spectra_vs import pipeline  # noqa: E402


def _node(tag: bytes, *children: cert_mod.WitnessNode) -> cert_mod.WitnessNode:
    """An OBSERVED witness node, which must cite at least one record."""
    head = model.Fact.mint(
        "test.head", (ids.EntityId.mint("resource", tag),), 1
    ).fact_key
    return cert_mod.WitnessNode(
        instance_id=ids.InstanceId.mint(tag),
        head=head,
        kind=cert_mod.WitnessKind.OBSERVED,
        evidence=(ids.EventId.mint(tag),),
        children=tuple(children),
    )


class TestWitnessDepthBound(unittest.TestCase):
    def test_the_bound_follows_the_contract_constant(self) -> None:
        """The bound is derived from cert.MAX_DEPTH, not written down separately."""
        expected = (cert_mod.MAX_DEPTH - pipeline._CONTAINERS_ABOVE_WITNESS_ROOT - 1) // 2 + 1
        self.assertEqual(pipeline._MAX_WITNESS_LEVELS, expected)

    def test_at_the_current_contract_it_is_a_root_and_one_level(self) -> None:
        """cert.py documents the cap as 'a root node and one level of children'."""
        self.assertEqual(cert_mod.MAX_DEPTH, 8)
        self.assertEqual(pipeline._MAX_WITNESS_LEVELS, 2)

    def test_a_lone_root_is_one_level(self) -> None:
        self.assertEqual(pipeline._witness_levels(_node(b"root")), 1)

    def test_a_root_with_leaves_is_two_levels(self) -> None:
        tree = _node(b"root", _node(b"a"), _node(b"b"))
        self.assertEqual(pipeline._witness_levels(tree), 2)
        self.assertLessEqual(pipeline._witness_levels(tree), pipeline._MAX_WITNESS_LEVELS)

    def test_the_route_a_shape_is_over_the_bound(self) -> None:
        """exfil.bulk_read <- access.gateway <- session.established: three levels, which
        is the derivation that aborted the run."""
        tree = _node(b"exfil", _node(b"gateway", _node(b"session")))
        self.assertEqual(pipeline._witness_levels(tree), 3)
        self.assertGreater(pipeline._witness_levels(tree), pipeline._MAX_WITNESS_LEVELS)

    def test_height_follows_the_deepest_branch_not_the_widest(self) -> None:
        tree = _node(b"root", _node(b"shallow"), _node(b"deep", _node(b"deeper")))
        self.assertEqual(pipeline._witness_levels(tree), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
