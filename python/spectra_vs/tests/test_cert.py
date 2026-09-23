"""Unit tests for the verdict algebra and the certificate emitter.

Run from the repository root:

    python python/spectra_vs/tests/test_cert.py

Run directly rather than through a runner, because there is no pytest on this machine and
a stage that needs a package manager to test itself is not testable here at all.

What these tests are for. The algebra tests exist so that a mutation which relaxes a
constructor check turns a named case red rather than producing a quietly stronger verdict.
The determinism tests compare bytes, not shapes, because a serialiser that sorts sometimes
is the cheapest way to lose byte-identical replay. The banned-substring test exists because
a one-word verdict is what a reader remembers.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from fractions import Fraction

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))

import cert_fixture as fixture  # noqa: E402

from spectra_core import canon  # noqa: E402
from spectra_core.errors import SchemaError, VerdictError  # noqa: E402
from spectra_core.model import Minimality, ProgramKind  # noqa: E402
from spectra_vs import cert  # noqa: E402


def _proposal(**overrides: object) -> cert.VerdictProposal:
    base = {
        "safety": cert.Safety.OPTIMISTIC_ONLY,
        "minimality": Minimality.UNVERIFIED,
        "flags": (),
        "derived_suppressed": cert.DERIVED_SUPPRESSED_ALWAYS,
        "realizability": cert.Realizability.CHECKED,
        "witness_class": None,
    }
    base.update(overrides)
    return cert.VerdictProposal(**base)  # type: ignore[arg-type]


def _token() -> cert.NoTamperToken:
    return cert.mint_no_tamper_token(
        tamper_suspected_sources=(), verdict_tamper_sensitive=False, sources=2
    )


class TestFlagTable(unittest.TestCase):
    def test_soundness_mask_is_derived_from_the_table(self) -> None:
        self.assertEqual(cert.SOUNDNESS_MASK, 0x013B)
        self.assertEqual(len(cert.FLAGS), 9)
        self.assertEqual(tuple(f.bit for f in cert.FLAGS), tuple(range(9)))

    def test_reserved_bits_are_nine_through_fifteen(self) -> None:
        self.assertEqual(cert.RESERVED_MASK, 0xFE00)
        with self.assertRaises(VerdictError) as caught:
            cert.check_reserved_bits(1 << 9)
        self.assertEqual(caught.exception.code, "VRD-009")

    def test_flags_are_ordered_by_bit_not_alphabetically(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.flags_mask(("er_ambiguous", "corridor_cap"))
        self.assertEqual(caught.exception.code, "VRD-008")

    def test_unknown_flag_is_rejected(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.flags_mask(("not_a_flag",))
        self.assertEqual(caught.exception.code, "VRD-008")

    def test_tamper_flag_is_declared_but_never_set_here(self) -> None:
        """It is still never set, and the REASON changed with ADR-0016.

        It used to be false because no pass could suspect anything. A pass exists now, and
        the flag is false because a dispute RETAINS the licence: voiding one would shrink
        P_max, and a smaller P_max can only move a verdict toward the universal claim,
        which is the attack Part II 65.6 closes. The test pins the property and the current
        reason, because the old wording survived the change that falsified it.
        """
        flag = cert.FLAG_BY_NAME["license_voided_by_suspected_tampering"]
        self.assertTrue(flag.blocks_robust)
        self.assertIn("never set", flag.effect)
        self.assertIn("nothing is voided", flag.effect)


class TestVerdictConstruction(unittest.TestCase):
    def test_direct_construction_is_refused(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict(
                safety=cert.Safety.INDETERMINATE,
                minimality=Minimality.UNVERIFIED,
                flags=(),
                derived_suppressed=cert.DERIVED_SUPPRESSED_ALWAYS,
                realizability=cert.Realizability.UNCHECKED,
                witness_class=None,
            )
        self.assertEqual(caught.exception.code, "VRD-010")

    def test_robust_requires_a_no_tamper_token(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(safety=cert.Safety.ROBUST), pmax_fixpoint_terminated=True
            )
        self.assertEqual(caught.exception.code, "VRD-001")

    def test_robust_requires_a_terminated_upper_fixpoint(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(safety=cert.Safety.ROBUST),
                no_tamper_token=_token(),
                pmax_fixpoint_terminated=False,
            )
        self.assertEqual(caught.exception.code, "VRD-001")

    def test_robust_is_unconstructible_under_every_soundness_subset(self) -> None:
        """The exhaustive sweep: 512 flag subsets crossed with the universal claim.

        Exactly the subsets disjoint from the soundness mask may be constructed. This is a
        design constraint expressed as a test, not a measurement of anything.
        """
        accepted = 0
        for encoding in range(1 << len(cert.FLAGS)):
            names = tuple(f.name for f in cert.FLAGS if encoding & (1 << f.bit))
            proposal = _proposal(safety=cert.Safety.ROBUST, flags=names)
            if encoding & cert.SOUNDNESS_MASK:
                with self.assertRaises(VerdictError) as caught:
                    cert.Verdict.build(
                        proposal, no_tamper_token=_token(), pmax_fixpoint_terminated=True
                    )
                self.assertEqual(caught.exception.code, "VRD-001", names)
            else:
                cert.Verdict.build(
                    proposal, no_tamper_token=_token(), pmax_fixpoint_terminated=True
                )
                accepted += 1
        free_bits = len(cert.FLAGS) - cert.SOUNDNESS_MASK.bit_count()
        self.assertEqual(accepted, 1 << free_bits)

    def test_safety_and_minimality_are_independent_axes(self) -> None:
        """atoms_over_budget caps minimality and does not block the universal claim.

        This is the regression test against re-conflating the two axes: a cut may be safe
        with nothing claimed about its size.
        """
        verdict = cert.Verdict.build(
            _proposal(
                safety=cert.Safety.ROBUST,
                flags=("atoms_over_budget",),
                minimality=Minimality.SUBSET,
            ),
            no_tamper_token=_token(),
            pmax_fixpoint_terminated=True,
        )
        self.assertIs(verdict.safety, cert.Safety.ROBUST)
        self.assertIs(verdict.minimality, Minimality.SUBSET)

    def test_exact_minimality_under_a_cap_is_refused(self) -> None:
        for flag in ("corridor_cap", "atoms_over_budget"):
            with self.subTest(flag=flag):
                with self.assertRaises(VerdictError) as caught:
                    cert.Verdict.build(
                        _proposal(
                            safety=cert.Safety.OPTIMISTIC_ONLY,
                            flags=(flag,),
                            minimality=Minimality.EXACT_PSI_RELATIVE,
                        )
                    )
                self.assertEqual(caught.exception.code, "VRD-004")

    def test_unsafe_without_a_witness_is_refused(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(
                    safety=cert.Safety.UNSAFE, witness_class=cert.WitnessClass.OBSERVED
                ),
                witness_present=False,
            )
        self.assertEqual(caught.exception.code, "VRD-002")

    def test_observed_witness_class_over_a_ghost_is_refused(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(
                    safety=cert.Safety.UNSAFE, witness_class=cert.WitnessClass.OBSERVED
                ),
                witness_present=True,
                witness_contains_silent=True,
            )
        self.assertEqual(caught.exception.code, "VRD-003")

    def test_er_ambiguous_forces_contested(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(
                    safety=cert.Safety.UNSAFE,
                    flags=("er_ambiguous",),
                    witness_class=cert.WitnessClass.LICENSED,
                ),
                witness_present=True,
                witness_contains_silent=True,
            )
        self.assertEqual(caught.exception.code, "VRD-007")
        cert.Verdict.build(
            _proposal(
                safety=cert.Safety.UNSAFE,
                flags=("er_ambiguous",),
                witness_class=cert.WitnessClass.CONTESTED,
            ),
            witness_present=True,
            witness_contains_silent=True,
        )

    def test_witness_class_on_a_non_unsafe_verdict_is_refused(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(
                _proposal(
                    safety=cert.Safety.OPTIMISTIC_ONLY,
                    witness_class=cert.WitnessClass.OBSERVED,
                )
            )
        self.assertEqual(caught.exception.code, "VRD-006")

    def test_derived_suppressed_must_name_both_omitted_products(self) -> None:
        with self.assertRaises(VerdictError) as caught:
            cert.Verdict.build(_proposal(derived_suppressed=("redundancy_index",)))
        self.assertEqual(caught.exception.code, "VRD-014")

    def test_scope_must_be_total_and_non_adaptive(self) -> None:
        digest = canon.hash_ref("x", b"x")
        with self.assertRaises(VerdictError) as caught:
            cert.Scope(
                rules=digest,
                controls=digest,
                liveness=digest,
                er=digest,
                goal=digest,
                bundle=digest,
                attacker="adaptive",
            )
        self.assertEqual(caught.exception.code, "VRD-005")


class TestRendering(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = cert.Scope(
            rules=canon.hash_ref("rules", b"r"),
            controls=canon.hash_ref("controls", b"c"),
            liveness=canon.hash_ref("liveness", b"l"),
            er=canon.hash_ref("er", b"e"),
            goal=canon.hash_ref("goal", b"g"),
            bundle=canon.hash_ref("bundle", b"b"),
        )
        self.verdict = cert.Verdict.build(
            _proposal(minimality=Minimality.EXACT_PSI_RELATIVE)
        )

    def test_safety_has_no_bare_token_string_form(self) -> None:
        self.assertNotEqual(str(cert.Safety.ROBUST), "ROBUST")
        self.assertEqual(cert.Safety.ROBUST.value, "ROBUST")

    def test_short_rendering_carries_the_scope_and_the_attacker(self) -> None:
        text = cert.render_short(self.verdict, self.scope)
        self.assertIn("non-adaptive", text)
        for member in ("rules@", "controls@", "liveness@", "er@", "goal@", "bundle@"):
            self.assertIn(member, text)
        self.assertIn("[EXACT_PSI_RELATIVE]", text)

    def test_long_rendering_ends_with_the_model_statement(self) -> None:
        text = cert.render_long(self.verdict, self.scope)
        self.assertTrue(text.endswith(cert.MODEL_STATEMENT))
        self.assertIn("non-adaptive", text)

    def test_no_banned_claim_appears_in_any_rendering(self) -> None:
        banned = (
            "minimum cut",
            "no smaller cut exists",
            "cardinality-minimal",
            "prevented",
            "would have stopped",
            "would have prevented",
            "formally verified",
            "proven secure",
            "independently verified",
        )
        texts = [
            cert.render_long(self.verdict, self.scope),
            cert.render_short(self.verdict, self.scope),
            cert.render_cut_delta_canonical(("ctl:priv_approval",)),
        ]
        for value in Minimality:
            texts.append(cert.render_minimality(value))
        for text in texts:
            for phrase in banned:
                self.assertNotIn(phrase, text.lower(), f"{phrase!r} in {text!r}")

    def test_exact_psi_relative_renders_as_the_permitted_clause(self) -> None:
        self.assertEqual(
            cert.render_minimality(Minimality.EXACT_PSI_RELATIVE),
            "no smaller cut satisfies the enumerated corridor set",
        )
        self.assertEqual(
            cert.render_minimality(Minimality.SUBSET),
            "no control can be removed from this cut; smaller cuts were not ruled out",
        )

    def test_cut_delta_always_carries_its_caption(self) -> None:
        text = cert.render_cut_delta_canonical(("ctl:priv_approval",))
        self.assertIn(cert.CUT_DELTA_CAPTION, text)
        self.assertNotIn("blindness premium", text.replace(cert.CUT_DELTA_CAPTION, ""))


class TestBody(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        _paths, self.inputs = fixture.write_side_files(root)
        self.fixture = fixture.build(root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_file_opens_with_the_recognisable_prefix(self) -> None:
        self.assertTrue(self.fixture.octets.startswith(cert.FILE_MAGIC))
        self.assertTrue(self.fixture.octets.endswith(b"\n"))
        self.assertEqual(self.fixture.octets.count(b"\n"), 1)
        self.assertNotIn(b"\r", self.fixture.octets)

    def test_cert_hash_covers_the_body_and_nothing_else(self) -> None:
        document = json.loads(self.fixture.octets.decode("utf-8"))
        recomputed = canon.hash_ref(
            "cert",
            json.dumps(
                document["body"],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        self.assertEqual(document["cert_hash"], recomputed)

    def test_the_digest_algorithm_is_declared_on_the_wire(self) -> None:
        document = json.loads(self.fixture.octets.decode("utf-8"))
        schema = document["body"]["schema"]
        self.assertEqual(schema["hash_algorithm"], canon.HASH_ALGORITHM)
        self.assertEqual(schema["hash_algorithm"], "blake2b-256")
        self.assertIn("b2b256:", document["cert_hash"])

    def test_no_wall_clock_or_machine_identity_reaches_the_body(self) -> None:
        text = self.fixture.octets.decode("utf-8")
        for forbidden in (
            "timestamp",
            "hostname",
            "username",
            "duration",
            "measured",
            "elapsed",
            "pid",
            "wall",
        ):
            self.assertNotIn(f'"{forbidden}"', text)

    def test_no_numeric_judgement_field_name_reaches_the_body(self) -> None:
        text = self.fixture.octets.decode("utf-8")
        for banned in (
            "confidence",
            "score",
            "severity",
            "probability",
            "likelihood",
            "certainty",
            "risk",
            "criticality",
            "priority",
            "weight",
            "rating",
            "grade",
            "percentile",
            "pct",
            "percent",
            "normalized_",
            "strength",
        ):
            self.assertNotIn(banned, text)

    def test_witness_class_is_present_and_null_on_a_non_unsafe_verdict(self) -> None:
        document = json.loads(self.fixture.octets.decode("utf-8"))
        verdict = document["body"]["verdict"]
        self.assertIn("witness_class", verdict)
        self.assertIsNone(verdict["witness_class"])

    def test_observed_and_ghost_counts_are_separate_members(self) -> None:
        body = self.fixture.body
        self.assertEqual(body["observed_event_count"], 2)
        self.assertEqual(body["ghost_count"], 1)
        self.assertNotIn("event_count", body)

    def test_instances_hash_covers_the_published_instance_set(self) -> None:
        self.assertEqual(
            self.fixture.body["inputs"]["instances_hash"],
            cert.instances_hash(fixture.INSTANCES),
        )

    def test_every_input_hash_states_what_it_covers(self) -> None:
        named = {name for name, _kind, _coverage in cert.INPUT_HASH_COVERAGE}
        for name in named:
            self.assertIn(name, self.fixture.body["inputs"])
        for _name, _kind, coverage in cert.INPUT_HASH_COVERAGE:
            self.assertTrue(coverage and coverage[0].islower())

    def test_serialisation_is_insertion_order_independent(self) -> None:
        reordered = dict(reversed(list(self.fixture.body.items())))
        self.assertEqual(cert.certificate_bytes(reordered), self.fixture.octets)

    def test_emitting_twice_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            again = fixture.build(pathlib.Path(other))
            self.assertEqual(again.octets, self.fixture.octets)

    def test_counts_that_disagree_with_the_instances_are_refused(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(observed_event_count=3)
        self.assertEqual(caught.exception.code, "E-GHOST-COUNT")

    def test_premium_is_absent_rather_than_empty_when_a_cap_fired(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(
                psi=cert.Psi(
                    program=ProgramKind.P_MAX, complete=False, corridors=fixture.CORRIDORS
                )
            )
        self.assertEqual(caught.exception.code, "E-FLAG-DERIVED")

    def test_premium_and_its_reason_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(premium_suppressed_reason="corridor_cap")
        self.assertEqual(caught.exception.code, "E-FLAG-DERIVED")

    def test_blindness_premium_is_nec_minus_occ_and_not_a_cut_difference(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            cert.Premium(
                nec_max=(fixture.EGRESS, fixture.PRIV),
                occ_min=(fixture.EGRESS,),
                blindness_premium=(fixture.EGRESS, fixture.PRIV),
                per_control=(),
            )
        self.assertEqual(caught.exception.code, "E-FLAG-DERIVED")

    def test_calibration_deficiency_is_an_exact_rational(self) -> None:
        entry = cert.PremiumEntry(
            control_id=fixture.PRIV,
            license_ids=(fixture.LICENCE.license_id,),
            calibration_deficiency=Fraction(2, 4),
        )
        self.assertEqual(entry.as_member()["calibration_deficiency"], {"den": 2, "num": 1})

    def test_a_cut_that_misses_a_corridor_is_refused(self) -> None:
        from spectra_core.model import Corridor

        unhit = Corridor.mint(atom_ranks=(1,), mask=1 << 1)
        corridors = tuple(
            sorted(
                (*fixture.CORRIDORS, unhit),
                key=lambda c: canon.byte_order_key(str(c.corridor_id)),
            )
        )
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(
                psi=cert.Psi(program=ProgramKind.P_MAX, complete=True, corridors=corridors)
            )
        self.assertEqual(caught.exception.code, "E-PSI-HIT")

    def _three_level_entry(self) -> cert.WitnessEntry:
        """A root, a child and a grandchild: the shape of route A, which the nested
        encoding could not carry. The fixture's instances are reused for their ids."""
        deep = fixture.witness_entries()
        root = deep[1].tree
        child = root.children[0]
        grandchild = cert.WitnessNode(
            instance_id=fixture.INSTANCE_1.instance_id,
            head=fixture.FACT_G,
            kind=cert.WitnessKind.OBSERVED,
            evidence=(fixture.EVENT_1,),
        )
        return cert.WitnessEntry(
            removed_control=deep[1].removed_control,
            tree=cert.WitnessNode(
                instance_id=root.instance_id,
                head=root.head,
                kind=root.kind,
                evidence=root.evidence,
                children=(
                    cert.WitnessNode(
                        instance_id=child.instance_id,
                        head=child.head,
                        kind=child.kind,
                        children=(grandchild,),
                    ),
                ),
            ),
        )

    def test_a_three_level_witness_is_published_within_the_depth_cap(self) -> None:
        """ADR-0015. Under the nested encoding this tree was refused with E-LIMIT-DEPTH,
        because the cap of eight containers admitted a root and one level of children."""
        deep = fixture.witness_entries()
        body = self._rebuild(witnesses=(deep[0], self._three_level_entry()))
        cert.certificate_bytes(body)

    def test_a_witness_is_flat_pre_order_with_children_as_indices(self) -> None:
        member = self._three_level_entry().as_member()
        self.assertEqual(sorted(member), ["nodes", "removed_control"])
        nodes = member["nodes"]
        self.assertEqual([n["children"] for n in nodes], [[1], [2], []])
        self.assertEqual(
            [n["kind"] for n in nodes], ["OBSERVED", "GHOST", "OBSERVED"]
        )

    def test_a_subtree_used_twice_is_written_twice(self) -> None:
        """Each node but the root has exactly one parent, so sharing is by copy."""
        leaf = cert.WitnessNode(
            instance_id=fixture.INSTANCE_1.instance_id,
            head=fixture.FACT_G,
            kind=cert.WitnessKind.OBSERVED,
            evidence=(fixture.EVENT_1,),
        )
        root = cert.WitnessNode(
            instance_id=fixture.INSTANCE_3.instance_id,
            head=fixture.FACT_G,
            kind=cert.WitnessKind.OBSERVED,
            evidence=(fixture.EVENT_2,),
            children=(leaf, leaf),
        )
        nodes = root.flatten()
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[0]["children"], [1, 2])

    def test_a_licensed_node_cites_no_evidence(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            cert.WitnessNode(
                instance_id=fixture.INSTANCE_2.instance_id,
                head=fixture.FACT_H,
                kind=cert.WitnessKind.LICENSED,
                evidence=(fixture.EVENT_1,),
            )
        self.assertEqual(caught.exception.code, "E-WITNESS-EVENT")

    def test_a_ghost_instance_is_not_published_as_licensed(self) -> None:
        """The fixture's silent instance is obligation-forced; calling it LICENSED is the
        wrong word, and the emitter refuses it."""
        deep = fixture.witness_entries()
        root = deep[1].tree
        relabelled = cert.WitnessEntry(
            removed_control=deep[1].removed_control,
            tree=cert.WitnessNode(
                instance_id=root.instance_id,
                head=root.head,
                kind=root.kind,
                evidence=root.evidence,
                children=(
                    cert.WitnessNode(
                        instance_id=root.children[0].instance_id,
                        head=root.children[0].head,
                        kind=cert.WitnessKind.LICENSED,
                    ),
                ),
            ),
        )
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(witnesses=(deep[0], relabelled))
        self.assertEqual(caught.exception.code, "E-WITNESS-EVENT")

    def test_both_silent_kinds_count_as_silent(self) -> None:
        self.assertEqual(
            cert.SILENT_WITNESS_KINDS,
            frozenset({cert.WitnessKind.GHOST, cert.WitnessKind.LICENSED}),
        )
        self.assertTrue(fixture.witness_entries()[1].tree.contains_silent())
        self.assertFalse(fixture.witness_entries()[0].tree.contains_silent())

    def test_invariant_is_published_exactly_when_every_goal_is_severed(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            self._rebuild(invariant=None)
        self.assertEqual(caught.exception.code, "E-SCHEMA-MISSING")

    def _rebuild(self, **overrides: object) -> dict[str, object]:
        """Rebuild the body with one member replaced, so one check can be isolated."""
        kwargs = fixture.body_kwargs(self.inputs)
        kwargs.update(overrides)
        return cert.build_body(**kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
