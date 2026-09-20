"""Unit tests for S8: the semi-naive fixpoint with provenance.

Run from the repository root:

    python python/spectra_vs/tests/test_ground.py

The determinism tests compare BYTES, not shapes. A mutation that made an output path
iterate a dict, or that sorted on insertion order, has to turn one of them red; a test that
only asserted "the result is a list" would pass through such a mutation untouched.
"""

from __future__ import annotations

import ast
import pathlib
import random
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import canon, model  # noqa: E402
from spectra_core.errors import LimitError, SchemaError  # noqa: E402
from spectra_core.ids import SourceId  # noqa: E402
from spectra_vs import ground, rules  # noqa: E402

import fixture  # noqa: E402

RULES_TOML = _REPO_ROOT / "config" / "vs" / "rules.toml"
SECOND = fixture.SECOND


class _PermutedTable:
    """The same rule table, evaluated in a different order.

    Only the evaluation order changes; every rule, guard and mask is the object the real
    table holds. That is exactly what the rule-ordering property is about: the fixpoint is
    a least model and must not depend on the order the rules were visited in.
    """

    def __init__(self, table: rules.RuleTable, order: list[int]) -> None:
        self._table = table
        self._order = order

    @property
    def rules(self):
        return tuple(self._table.rules[i] for i in self._order)

    @property
    def detect_rules(self):
        return tuple(r for r in self.rules if not r.is_obligation)

    @property
    def obligation_rules(self):
        return tuple(r for r in self.rules if r.is_obligation)

    def get(self, rule_id: str):
        return self._table.get(rule_id)


def _table() -> rules.RuleTable:
    return fixture.rule_table(RULES_TOML)


def _bytes(program: ground.Program) -> bytes:
    return ground.scf_dumps(ground.program_document(program)).encode("utf-8")


def _predicates(program: ground.Program) -> list[str]:
    return sorted(f.predicate for f in program.facts)


# ---------------------------------------------------------------------------
# Seeding and the fact base
# ---------------------------------------------------------------------------


class TestSeeding(unittest.TestCase):
    def test_axiom_arguments_are_ordered_by_role_name(self) -> None:
        """The pattern binds positionally against the role-sorted argument vector."""
        events, bindings = fixture.cell(True)
        result = ground.ground(_table(), events, bindings)
        seeded = [f for f in result.program.facts if f.predicate == "idp.refresh_exchange"]
        self.assertEqual(len(seeded), 1)
        kinds = [arg.kind for arg in seeded[0].args]
        self.assertEqual(kinds, ["credential", "user"])

    def test_every_bundle_record_seeds_exactly_one_axiom_fact(self) -> None:
        events, bindings = fixture.cell(True)
        result = ground.ground(_table(), events, bindings)
        seeded = {
            str(f.fact_key)
            for f in result.program.facts
            if f.predicate in _table().axiom_predicates
            or f.predicate in ("iam.approval_granted", "net.connection")
        }
        self.assertEqual(len(seeded), len(events))

    def test_a_fact_key_does_not_depend_on_the_binding_order(self) -> None:
        events, bindings = fixture.cell(True)
        shuffled = list(bindings)
        random.Random(7).shuffle(shuffled)
        self.assertEqual(
            _bytes(ground.ground(_table(), events, bindings).program),
            _bytes(ground.ground(_table(), events, shuffled).program),
        )


# ---------------------------------------------------------------------------
# The routes
# ---------------------------------------------------------------------------


class TestRoutes(unittest.TestCase):
    def test_route_a_reaches_the_goal_at_full_completeness(self) -> None:
        events, bindings = fixture.cell(True)
        program = ground.ground(_table(), events, bindings).program
        self.assertIn("exfil.bulk_read", _predicates(program))
        self.assertEqual(len(ground.goal_candidates(program, "exfil.bulk_read")), 1)

    def test_route_a_still_reaches_the_goal_in_the_degraded_cell(self) -> None:
        """The degradation removed iam_audit only, so route A is untouched."""
        events, bindings = fixture.cell(False)
        program = ground.ground(_table(), events, bindings).program
        self.assertEqual(len(ground.goal_candidates(program, "exfil.bulk_read")), 1)

    def test_route_b_is_derivable_in_neither_cell_of_p_min(self) -> None:
        """At full completeness the approval exists; degraded, the record is gone. Both
        times the observed program contains no escalation."""
        for complete in (True, False):
            with self.subTest(complete=complete):
                events, bindings = fixture.cell(complete)
                program = ground.ground(_table(), events, bindings).program
                self.assertNotIn("privilege.escalated", _predicates(program))

    def test_obligation_rules_never_fire_in_p_min(self) -> None:
        events, bindings = fixture.cell(True)
        program = ground.ground(_table(), events, bindings).program
        fired = {str(i.rule_id) for i in program.instances}
        self.assertNotIn("rl:r0007", fired)
        self.assertNotIn("rl:r0008", fired)
        self.assertEqual(program.counts.silent_instances, 0)
        self.assertEqual(program.counts.ghost_facts, 0)

    def test_p_min_carries_no_licences(self) -> None:
        events, bindings = fixture.cell(True)
        program = ground.ground(_table(), events, bindings).program
        self.assertEqual(program.licences, ())
        with self.assertRaises(SchemaError):
            ground.Program(
                kind=model.ProgramKind.P_MIN,
                facts=(),
                instances=(),
                licences=(
                    model.Licence.mint(
                        SourceId.of("edr_host"),
                        model.Interval(0, 1),
                        model.LicenceBasis.BLIND,
                        "B_PROFILE_INSUFFICIENT",
                    ),
                ),
                axioms=(),
                goal=None,
                counts=ground.Counts(),
                by_body=(),
            )


# ---------------------------------------------------------------------------
# Temporal operators
# ---------------------------------------------------------------------------


class TestTemporal(unittest.TestCase):
    def _run(self, emissions):
        events = tuple(sorted((e.event for e in emissions), key=lambda ev: ev.sort_key()))
        bindings = tuple(b for e in emissions for b in e.bindings)
        return ground.ground(_table(), events, bindings).program

    def _chain(self, gateway_offset: int, resources: list[str]) -> list:
        e = fixture.ENTITIES
        out = [
            fixture.make_event(
                "idp_auth", 0, "idp.refresh_exchange", fixture.EPOCH_NS,
                {"credential": e["token"], "principal": e["mallory"]},
            ),
            fixture.make_event(
                "gw_access", 0, "gw.request", fixture.EPOCH_NS + gateway_offset * SECOND,
                {"principal": e["mallory"], "service": e["gateway"]},
            ),
        ]
        for index, name in enumerate(resources):
            out.append(
                fixture.make_event(
                    "res_access", index, "res.read",
                    fixture.EPOCH_NS + (gateway_offset + 60 + index * 10) * SECOND,
                    {"principal": e["mallory"], "resource": e[name]},
                )
            )
        return out

    def test_seq_fires_inside_the_window(self) -> None:
        program = self._run(self._chain(60, ["doc1", "doc2", "doc3"]))
        self.assertIn("access.gateway", _predicates(program))

    def test_seq_does_not_fire_outside_the_window(self) -> None:
        """A gateway call thirty-one minutes later is a different episode."""
        program = self._run(self._chain(31 * 60, ["doc1", "doc2", "doc3"]))
        self.assertNotIn("access.gateway", _predicates(program))

    def test_distinct_requires_three_distinct_values(self) -> None:
        program = self._run(self._chain(60, ["doc1", "doc2"]))
        self.assertNotIn("exfil.bulk_read", _predicates(program))

    def test_distinct_counts_values_and_not_records(self) -> None:
        """Three reads of the same resource are one distinct value, not three."""
        program = self._run(self._chain(60, ["doc1", "doc1", "doc1"]))
        self.assertNotIn("exfil.bulk_read", _predicates(program))

    def test_distinct_cites_every_participating_record(self) -> None:
        program = self._run(self._chain(60, ["doc1", "doc2", "doc3"]))
        instance = next(i for i in program.instances if str(i.rule_id) == "rl:r0003")
        self.assertEqual(len([r for r in instance.evidence if r.binding == "b"]), 3)

    def test_absence_fires_when_no_approval_precedes_the_assumption(self) -> None:
        e = fixture.ENTITIES
        emissions = [
            fixture.make_event(
                "iam_audit", 0, "iam.role_assumed", fixture.EPOCH_NS,
                {"principal": e["mallory"], "role": e["admin_role"]},
            ),
            fixture.make_event(
                "iam_audit", 1, "iam.role_assumed", fixture.EPOCH_NS - 3600 * SECOND,
                {"principal": e["alice"], "role": e["admin_role"]},
            ),
        ]
        program = self._run(emissions)
        self.assertIn("privilege.escalated", _predicates(program))

    def test_absence_does_not_fire_when_the_approval_is_in_the_lookback(self) -> None:
        e = fixture.ENTITIES
        emissions = [
            fixture.make_event(
                "iam_audit", 0, "iam.approval_granted", fixture.EPOCH_NS - 3600 * SECOND,
                {"principal": e["mallory"], "role": e["admin_role"]},
            ),
            fixture.make_event(
                "iam_audit", 1, "iam.role_assumed", fixture.EPOCH_NS,
                {"principal": e["mallory"], "role": e["admin_role"]},
            ),
        ]
        program = self._run(emissions)
        self.assertNotIn("privilege.escalated", _predicates(program))

    def test_absence_fails_closed_when_the_source_is_silent_in_the_lookback(self) -> None:
        """Without a liveness document, `no record` is not `nothing happened`."""
        e = fixture.ENTITIES
        emissions = [
            fixture.make_event(
                "iam_audit", 0, "iam.role_assumed", fixture.EPOCH_NS,
                {"principal": e["mallory"], "role": e["admin_role"]},
            )
        ]
        events = tuple(x.event for x in emissions)
        bindings = tuple(b for x in emissions for b in x.bindings)

        def never_observed(sources, window):
            return ground.Absence.UNDETERMINED

        program = ground.ground(
            _table(), events, bindings, absence_availability=never_observed
        ).program
        self.assertNotIn("privilege.escalated", _predicates(program))

    def test_the_proxy_never_licenses(self) -> None:
        """A licence is minted by the liveness stage or not at all."""
        events, _ = fixture.cell(True)
        answer = ground.bundle_absence_proxy(events)
        blind = model.Interval(fixture.SPAN_T1_NS, fixture.SPAN_T1_NS + SECOND)
        self.assertIs(answer((SourceId.of("iam_audit"),), blind), ground.Absence.UNDETERMINED)
        live = model.Interval(fixture.EPOCH_NS - SECOND, fixture.EPOCH_NS + SECOND)
        self.assertIs(answer((SourceId.of("idp_auth"),), live), ground.Absence.OBSERVED)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance(unittest.TestCase):
    def setUp(self) -> None:
        self.events, self.bindings = fixture.cell(True)
        self.program = ground.ground(_table(), self.events, self.bindings).program

    def test_every_observed_instance_carries_evidence(self) -> None:
        for instance in self.program.instances:
            with self.subTest(instance=str(instance.instance_id)):
                self.assertIs(instance.observed, model.Observation.OBSERVED)
                self.assertTrue(instance.evidence)
                self.assertEqual(instance.license_ids, ())

    def test_evidence_dereferences_to_records_in_the_bundle(self) -> None:
        present = {str(e.event_id) for e in self.events}
        for instance in self.program.instances:
            for reference in instance.evidence:
                self.assertIn(str(reference.event_id), present)

    def test_evidence_carries_the_source_and_the_instant_of_its_record(self) -> None:
        by_id = {str(e.event_id): e for e in self.events}
        for instance in self.program.instances:
            for reference in instance.evidence:
                event = by_id[str(reference.event_id)]
                self.assertEqual(reference.source_id, event.source_id)
                self.assertEqual(reference.t_evt_ns, event.t_evt_ns)

    def test_the_hypergraph_is_bipartite_and_its_edges_are_complete(self) -> None:
        index = self.program.body_index()
        keys = {str(f.fact_key) for f in self.program.facts}
        for position, instance in enumerate(self.program.instances):
            self.assertIn(str(instance.head), keys)
            for body_key in instance.body:
                self.assertIn(str(body_key), keys)
                self.assertIn(position, index[body_key])

    def test_axioms_are_the_facts_no_instance_supports(self) -> None:
        supported = {str(i.head) for i in self.program.instances if i.body}
        for key in self.program.axioms:
            self.assertNotIn(str(key), supported)
        self.assertIn("idp.refresh_exchange", {self.program.fact(a).predicate for a in self.program.axioms})

    def test_an_instance_id_does_not_move_when_the_catalog_gains_a_control(self) -> None:
        """Masks are excluded from the instance identity, so cut stability survives an
        unrelated control being appended to the catalog."""
        extended = rules.Catalog.from_entries(
            [
                *fixture.catalog_rows(),
                {
                    "id": "zz_unrelated",
                    "title": "Unrelated",
                    "levels": ["off", "on"],
                    "dimensions": ["network"],
                    "provenance": "A control no rule in the table references.",
                },
            ]
        )
        other = rules.compile_rules(RULES_TOML, extended, rules.BitTable.derive(extended))
        again = ground.ground(other, self.events, self.bindings).program
        self.assertEqual(
            [str(i.instance_id) for i in self.program.instances],
            [str(i.instance_id) for i in again.instances],
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def test_rule_ordering_invariance(self) -> None:
        """G-D2: randomised rule evaluation orderings produce identical program bytes."""
        table = _table()
        events, bindings = fixture.cell(False)
        expected = _bytes(ground.ground(table, events, bindings).program)
        for seed in range(16):
            order = list(range(len(table.rules)))
            random.Random(seed).shuffle(order)
            permuted = _PermutedTable(table, order)
            with self.subTest(seed=seed):
                self.assertEqual(
                    _bytes(ground.ground(permuted, events, bindings).program), expected
                )

    def test_input_ordering_invariance(self) -> None:
        """G-D1: shuffled record order produces an identical fact base."""
        table = _table()
        events, bindings = fixture.cell(True)
        expected = _bytes(ground.ground(table, events, bindings).program)
        for seed in range(16):
            shuffled_events = list(events)
            shuffled_bindings = list(bindings)
            random.Random(seed).shuffle(shuffled_events)
            random.Random(seed + 100).shuffle(shuffled_bindings)
            with self.subTest(seed=seed):
                self.assertEqual(
                    _bytes(ground.ground(table, shuffled_events, shuffled_bindings).program),
                    expected,
                )

    def test_the_run_is_a_pure_function_of_its_inputs(self) -> None:
        table = _table()
        events, bindings = fixture.cell(True)
        first = ground.ground(table, events, bindings)
        second = ground.ground(table, events, bindings)
        self.assertEqual(_bytes(first.program), _bytes(second.program))
        self.assertEqual(first.fixpoint_steps, second.fixpoint_steps)

    def test_the_fact_base_only_grows(self) -> None:
        """Nothing is retracted. Expiry is a later fact not being derived."""
        table = _table()
        events, bindings = fixture.cell(True)
        engine = ground.Engine(table, events, bindings)
        engine.seed()
        sizes = []
        for _ in range(3):
            engine.saturate()
            sizes.append(len(engine.snapshot(model.ProgramKind.P_MIN).facts))
        self.assertEqual(sizes, sorted(sizes))
        self.assertEqual(sizes[0], sizes[-1])

    def test_every_exported_collection_is_strictly_ascending(self) -> None:
        events, bindings = fixture.cell(False)
        program = ground.ground(_table(), events, bindings).program
        canon.check_strictly_ascending(
            [str(f.fact_key) for f in program.facts], lambda s: s, where="facts"
        )
        canon.check_strictly_ascending(
            [str(i.instance_id) for i in program.instances], lambda s: s, where="instances"
        )
        canon.check_strictly_ascending(
            [str(a) for a in program.axioms], lambda s: s, where="axioms"
        )


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


class TestCaps(unittest.TestCase):
    def test_the_iteration_cap_sets_the_flag_rather_than_running_on(self) -> None:
        table = _table()
        events, bindings = fixture.cell(True)
        original = ground.MAX_ITERATIONS
        try:
            ground.MAX_ITERATIONS = 1
            result = ground.ground(table, events, bindings)
        finally:
            ground.MAX_ITERATIONS = original
        self.assertTrue(result.capped)
        self.assertIn("MAX_ITERATIONS", result.cap_detail)

    def test_the_fact_cap_sets_the_flag(self) -> None:
        table = _table()
        events, bindings = fixture.cell(True)
        original = ground.MAX_FACTS
        try:
            ground.MAX_FACTS = 3
            result = ground.ground(table, events, bindings)
        finally:
            ground.MAX_FACTS = original
        self.assertTrue(result.capped)
        self.assertIn("MAX_FACTS", result.cap_detail)


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------


class TestArtifact(unittest.TestCase):
    def setUp(self) -> None:
        events, bindings = fixture.cell(False)
        self.program = ground.ground(_table(), events, bindings).program

    def test_the_document_ends_with_exactly_one_newline(self) -> None:
        text = ground.scf_dumps(ground.program_document(self.program))
        self.assertTrue(text.endswith("}\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_a_float_is_rejected(self) -> None:
        with self.assertRaises(Exception) as caught:
            ground.scf_dumps({"a": 1.5})
        self.assertIn("E-CANON-FLOAT", str(caught.exception))

    def test_a_null_is_rejected(self) -> None:
        """Optionality is member absence. The shared serialiser raises its own code here,
        which is why this asserts the rejection rather than restating that code."""
        with self.assertRaises(SchemaError) as caught:
            ground.scf_dumps({"a": None})
        self.assertIn("null", str(caught.exception))

    def test_a_non_ascii_key_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            ground.scf_dumps({"Key": 1})

    def test_nesting_deeper_than_eight_is_rejected(self) -> None:
        deep: object = 1
        for _ in range(10):
            deep = {"a": deep}
        with self.assertRaises(LimitError):
            ground.scf_dumps(deep)

    def test_instants_and_masks_travel_as_strings(self) -> None:
        document = ground.program_document(self.program)
        for instance in document["instances"]:
            for mask in instance["blockers"]:
                self.assertIsInstance(mask, str)
                self.assertTrue(mask.startswith("0x"))
            for reference in instance["evidence"]:
                self.assertIsInstance(reference["t_evt_ns"], str)

    def test_the_document_declares_the_digest_actually_computed(self) -> None:
        document = ground.program_document(self.program)
        self.assertEqual(document["hash_algorithm"], canon.HASH_ALGORITHM)
        self.assertNotIn("blake3", ground.scf_dumps(document))

    def test_the_document_uses_the_section_57_identifier_forms(self) -> None:
        document = ground.program_document(self.program)
        self.assertTrue(all(str(f["fact_key"]).startswith("fh:") for f in document["facts"]))
        self.assertTrue(
            all(str(i["instance_id"]).startswith("in:") for i in document["instances"])
        )

    def test_writing_is_byte_identical_across_two_writes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            first = pathlib.Path(directory) / "a" / "p_min.json"
            second = pathlib.Path(directory) / "b" / "p_min.json"
            left = ground.write_program(self.program, first)
            right = ground.write_program(self.program, second)
            self.assertEqual(left, right)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotIn(b"\r", first.read_bytes())


class TestGroundTruthIsNeverRead(unittest.TestCase):
    @staticmethod
    def _executable_nodes(source: str):
        """Every AST node of the module except the docstrings.

        Prose is allowed to name the oracle channel; code is not. Parsing rather than
        grepping is what makes that distinction hold, so a later edit that adds a real read
        turns this red while the paragraph explaining the rule stays legal.
        """
        tree = ast.parse(source)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                body = getattr(node, "body", ())
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    docstrings.add(id(body[0].value))
        return [n for n in ast.walk(tree) if id(n) not in docstrings]

    def test_neither_stage_names_the_oracle_channel_in_code(self) -> None:
        """A stage that reads ground truth is the defect the whole design prevents."""
        for name in ("ground.py", "envelope.py"):
            source = (
                _REPO_ROOT / "python" / "spectra_vs" / "src" / "spectra_vs" / name
            ).read_text(encoding="utf-8")
            for node in self._executable_nodes(source):
                text = ""
                if isinstance(node, ast.Name):
                    text = node.id
                elif isinstance(node, ast.Attribute):
                    text = node.attr
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    text = node.name
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value
                with self.subTest(name=name, text=text[:40]):
                    self.assertNotIn("truth", text.lower())

    def test_neither_stage_reads_a_file(self) -> None:
        """Both stages take their inputs as values and only ever write their artifact."""
        for name in ("ground.py", "envelope.py"):
            source = (
                _REPO_ROOT / "python" / "spectra_vs" / "src" / "spectra_vs" / name
            ).read_text(encoding="utf-8")
            for node in self._executable_nodes(source):
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "open", name)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(
                        node.attr, {"read_text", "read_bytes", "open", "readlines"}, name
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
