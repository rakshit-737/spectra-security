"""Unit tests for how spectra_vs.pipeline turns a derivation into a certificate witness.

Run from the repository root:

    python python/spectra_vs/tests/test_pipeline_witness.py

History. The certificate first carried witness trees nested, under a cap of eight
containers that admitted a root and one level of children. Once route A was found
derivable, a real three-level derivation reached the emitter and was refused, and that
refusal aborted the whole run (INC-0008); the pipeline then learned to drop and report it.
A derivation through a licensed silent step was dropped as well, because the witness
alphabet had no word for one. ADR-0015 published witnesses flat and added the LICENSED
kind, so both refusals were removed. These tests pin the translation that replaced them:
every reach kind maps to the certificate kind of the same name, an axiom leaf is not
published, a kind with no certificate word is refused rather than mapped to a neighbour,
and a witness of any length stays inside the nesting cap.
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
from spectra_vs import reach as reach_mod  # noqa: E402


def _head(tag: bytes) -> ids.FactHash:
    return model.Fact.mint("test.head", (ids.EntityId.mint("resource", tag),), 1).fact_key


def _reach_node(
    tag: bytes, kind: str, *children: reach_mod.WitnessNode
) -> reach_mod.WitnessNode:
    return reach_mod.WitnessNode(
        head=_head(tag),
        kind=kind,
        instance_id=ids.InstanceId.mint(tag),
        evidence=(ids.EventId.mint(tag),) if kind == reach_mod.OBSERVED_KIND else (),
        children=tuple(children),
    )


def _axiom(tag: bytes) -> reach_mod.WitnessNode:
    return reach_mod.WitnessNode(head=_head(tag), kind=reach_mod.AXIOM_KIND)


def _chain(levels: int) -> reach_mod.WitnessNode:
    """An observed derivation `levels` instances deep, ending on an axiom."""
    node = _reach_node(b"level-0", reach_mod.OBSERVED_KIND, _axiom(b"seed"))
    for level in range(1, levels):
        node = _reach_node(f"level-{level}".encode(), reach_mod.OBSERVED_KIND, node)
    return node


def _max_depth(value: object, depth: int = 1) -> int:
    """Containers deep, counting `value` itself as the first, as the contract counts."""
    if isinstance(value, dict):
        return max([depth, *(_max_depth(v, depth + 1) for v in value.values())])
    if isinstance(value, list):
        return max([depth, *(_max_depth(v, depth + 1) for v in value)])
    return depth - 1


class TestKinds(unittest.TestCase):
    def test_each_reach_kind_maps_to_the_certificate_kind_of_its_name(self) -> None:
        tree = _reach_node(
            b"root",
            reach_mod.OBSERVED_KIND,
            _reach_node(b"ghost", reach_mod.GHOST_KIND),
            _reach_node(b"licensed", reach_mod.LICENSED_KIND),
        )
        node = pipeline._cert_witness(tree)
        assert node is not None
        self.assertIs(node.kind, cert_mod.WitnessKind.OBSERVED)
        self.assertEqual(
            [child.kind for child in node.children],
            [cert_mod.WitnessKind.GHOST, cert_mod.WitnessKind.LICENSED],
        )

    def test_a_licensed_step_is_published_and_counts_as_silent(self) -> None:
        """The derivation that was dropped in pre-registration 0001's blackout cell."""
        tree = _reach_node(
            b"export",
            reach_mod.OBSERVED_KIND,
            _reach_node(b"escalation", reach_mod.LICENSED_KIND),
        )
        node = pipeline._cert_witness(tree)
        assert node is not None
        self.assertTrue(node.contains_silent())

    def test_an_axiom_leaf_is_not_published(self) -> None:
        node = pipeline._cert_witness(
            _reach_node(b"root", reach_mod.OBSERVED_KIND, _axiom(b"seed"))
        )
        assert node is not None
        self.assertEqual(node.children, ())
        self.assertIsNone(pipeline._cert_witness(_axiom(b"seed")))

    def test_a_kind_with_no_certificate_word_is_refused(self) -> None:
        tree = _reach_node(b"root", reach_mod.OBSERVED_KIND, _reach_node(b"odd", "UNHEARD_OF"))
        with self.assertRaises(pipeline._UnrepresentableWitness):
            pipeline._cert_witness(tree)


class TestLength(unittest.TestCase):
    def test_route_a_is_three_levels_and_is_published(self) -> None:
        """exfil.bulk_read <- access.gateway <- session.established: the derivation whose
        refusal aborted the third end-to-end run."""
        node = pipeline._cert_witness(_chain(3))
        assert node is not None
        entry = cert_mod.WitnessEntry(removed_control=ids.ControlId("ctl:egress_seg"), tree=node)
        self.assertEqual(len(entry.as_member()["nodes"]), 3)

    def test_nesting_does_not_grow_with_derivation_length(self) -> None:
        """document, body, witnesses, entry, nodes, node, children: seven, for any length."""
        for levels in (1, 3, 40):
            node = pipeline._cert_witness(_chain(levels))
            assert node is not None
            entry = cert_mod.WitnessEntry(
                removed_control=ids.ControlId("ctl:egress_seg"), tree=node
            )
            document = {"body": {"witnesses": [entry.as_member()]}}
            self.assertEqual(_max_depth(document), 7, levels)
            self.assertLessEqual(_max_depth(document), cert_mod.MAX_DEPTH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
