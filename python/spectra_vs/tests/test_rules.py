"""Unit tests for S1: the rule table, the guard front end and the blocker masks.

Run from the repository root:

    python python/spectra_vs/tests/test_rules.py

Run directly rather than through a runner: there is no pytest on this machine and a stage
that needs a package manager to test itself is not testable here at all.

Each test pins a property another stage is entitled to assume. The mask tests compare
values rather than asserting that "a mask was produced", so a mutation to the bit
assignment or to the DNF canonicalisation turns a named test red instead of passing.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from spectra_core import canon, model  # noqa: E402
from spectra_core.errors import GuardError, LimitError, SchemaError  # noqa: E402
from spectra_core.ids import ControlId, EventId, RuleId, SourceId  # noqa: E402
from spectra_vs import rules  # noqa: E402

import fixture  # noqa: E402

RULES_TOML = _REPO_ROOT / "config" / "vs" / "rules.toml"


def _write(text: str) -> pathlib.Path:
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".toml", delete=False, encoding="utf-8", newline="\n"
    )
    handle.write(text)
    handle.close()
    return pathlib.Path(handle.name)


_MINIMAL = """
schema = "spectra.vs.rules/1"

[[rule]]
id                = "r0001"
version           = "1.0.0"
dimension         = "session"
kind              = "detect"
head              = "session.established(principal, credential, t)"
body              = ["idp.refresh_exchange(credential, principal, t)"]
blocked_when      = "{blocked}"
producing_sources = ["idp_auth"]
silent_possible   = false
persistence       = "{persistence}"
{extra}
"""


def _one_rule(blocked: str = "", persistence: str = "instant", extra: str = "") -> rules.RuleTable:
    path = _write(_MINIMAL.format(blocked=blocked, persistence=persistence, extra=extra))
    return rules.compile_rules(path, fixture.catalog(), fixture.bit_table())


# ---------------------------------------------------------------------------
# The catalog and the bit table
# ---------------------------------------------------------------------------


class TestBitTable(unittest.TestCase):
    def test_literals_are_the_nine_the_scenario_declares(self) -> None:
        literals = fixture.catalog().literals()
        self.assertEqual(len(literals), 9)
        self.assertEqual(
            [(str(c), lv) for c, lv in literals],
            [
                ("ctl:egress_seg", 1),
                ("ctl:egress_seg", 2),
                ("ctl:priv_approval", 1),
                ("ctl:priv_approval", 2),
                ("ctl:rate_limit", 1),
                ("ctl:session_binding", 1),
                ("ctl:session_binding", 2),
                ("ctl:token_expiry", 1),
                ("ctl:token_expiry", 2),
            ],
        )

    def test_level_zero_has_no_literal(self) -> None:
        """`at least the weakest setting` asserts nothing, so it is not a proposition."""
        for _, level in fixture.catalog().literals():
            self.assertGreaterEqual(level, 1)

    def test_bit_and_rank_are_different_things(self) -> None:
        """A tombstone keeps its bit forever and loses its rank; the two never merge."""
        table = rules.BitTable(
            (
                rules.BitEntry(0, ControlId.of("egress_seg"), 1, "tombstone"),
                rules.BitEntry(1, ControlId.of("egress_seg"), 2, "live"),
                rules.BitEntry(2, ControlId.of("rate_limit"), 1, "live"),
            )
        )
        literals = table.literals()
        self.assertEqual([(lit.bit, lit.rank) for lit in literals], [(1, 0), (2, 1)])

    def test_append_only_lock_round_trips(self) -> None:
        derived = fixture.bit_table()
        path = _write(derived.lock_text())
        self.assertEqual(rules.load_bit_table(path).entries, derived.entries)

    def test_a_lock_that_disagrees_with_the_catalog_is_rejected(self) -> None:
        short = rules.BitTable(fixture.bit_table().entries[:-1])
        with self.assertRaises(GuardError) as caught:
            short.check_covers(fixture.catalog())
        self.assertEqual(caught.exception.code, "E-LITERAL-TABLE")

    def test_bit_beyond_the_mask_width_is_a_limit_failure(self) -> None:
        with self.assertRaises(LimitError):
            rules.BitEntry(64, ControlId.of("egress_seg"), 1, "live")

    def test_catalog_digest_changes_when_a_level_is_renamed(self) -> None:
        """Renaming a level is a semantic edit, so it must move the catalog digest."""
        renamed = fixture.catalog_rows()
        renamed[2]["levels"] = ["none", "capped"]
        self.assertNotEqual(
            fixture.catalog().controls_hash,
            rules.Catalog.from_entries(renamed).controls_hash,
        )


# ---------------------------------------------------------------------------
# The control sort
# ---------------------------------------------------------------------------


class TestControlSort(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = fixture.catalog()
        self.bits = fixture.bit_table()

    def _terms(self, text: str):
        return rules.compile_blocked_when(text, self.catalog, self.bits, where="t")

    def test_a_disjunction_of_thresholds_compiles_to_single_literal_terms(self) -> None:
        terms = self._terms("ctl.token_expiry >= short_lived or ctl.session_binding >= device_bound")
        self.assertEqual(
            [[(str(c), lv) for c, lv in term] for term in terms],
            [[("ctl:session_binding", 1)], [("ctl:token_expiry", 1)]],
        )

    def test_level_is_resolved_by_name_from_the_catalog(self) -> None:
        terms = self._terms("ctl.priv_approval >= sync_two_person")
        self.assertEqual([(str(c), lv) for c, lv in terms[0]], [("ctl:priv_approval", 2)])

    def test_an_unknown_level_name_is_rejected_rather_than_defaulted(self) -> None:
        with self.assertRaises(GuardError):
            self._terms("ctl.priv_approval >= paper_form")

    def test_the_weakest_level_has_no_literal_and_is_rejected(self) -> None:
        with self.assertRaises(GuardError):
            self._terms("ctl.priv_approval >= none")

    def test_a_level_written_as_an_integer_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            self._terms("ctl.priv_approval >= 1")
        self.assertEqual(caught.exception.code, "E-SYN-012")

    def test_negation_in_the_control_sort_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            self._terms("not ctl.priv_approval >= async_ticket")
        self.assertEqual(caught.exception.code, "E-SYN-009")

    def test_a_data_field_in_the_control_sort_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            self._terms("a.principal >= async_ticket")
        self.assertEqual(caught.exception.code, "E-SYN-009")

    def test_a_conjunctive_term_is_the_narrowing_and_is_named(self) -> None:
        """C-SLICE-1 is stated as a narrowing and enforced, not silently accepted."""
        terms = self._terms("ctl.priv_approval >= async_ticket and ctl.rate_limit >= per_principal_quota")
        with self.assertRaises(GuardError) as caught:
            rules._terms_to_masks(terms, self.bits, where="t")
        self.assertEqual(caught.exception.code, "E-VS-BLOCK-CONJ")

    def test_the_strongest_level_survives_inside_a_term(self) -> None:
        terms = self._terms(
            "ctl.priv_approval >= async_ticket and ctl.priv_approval >= sync_two_person"
        )
        self.assertEqual([[(str(c), lv) for c, lv in t] for t in terms], [[("ctl:priv_approval", 2)]])

    def test_the_weakest_level_survives_across_terms(self) -> None:
        """`k >= 2` is implied by `k >= 1`, so the stronger disjunct is redundant."""
        terms = self._terms("ctl.priv_approval >= sync_two_person or ctl.priv_approval >= async_ticket")
        self.assertEqual([[(str(c), lv) for c, lv in t] for t in terms], [[("ctl:priv_approval", 1)]])

    def test_an_empty_guard_means_no_control_severs_this_edge(self) -> None:
        self.assertEqual(self._terms(""), ())

    def test_masks_are_built_from_bits_and_ordered_by_popcount_then_value(self) -> None:
        terms = self._terms("ctl.token_expiry >= short_lived or ctl.egress_seg >= allowlist_egress")
        masks = rules._terms_to_masks(terms, self.bits, where="t")
        self.assertEqual(masks, (1 << 0, 1 << 7))
        self.assertTrue(all(m.bit_count() == 1 for m in masks))

    def test_a_mask_means_nothing_without_its_table(self) -> None:
        """The same guard over a catalog with one control prepended gets a different bit."""
        extended = rules.Catalog.from_entries(
            [
                *fixture.catalog_rows(),
                {
                    "id": "aaa_new_control",
                    "title": "Prepended",
                    "levels": ["off", "on"],
                    "dimensions": ["network"],
                    "provenance": "An unrelated control appended to the catalog.",
                },
            ]
        )
        extended_bits = rules.BitTable.derive(extended)
        here = rules._terms_to_masks(self._terms("ctl.egress_seg >= allowlist_egress"), self.bits, where="t")
        there = rules._terms_to_masks(
            rules.compile_blocked_when("ctl.egress_seg >= allowlist_egress", extended, extended_bits, where="t"),
            extended_bits,
            where="t",
        )
        self.assertNotEqual(here, there)
        self.assertNotEqual(self.bits.catalog_bits_hash, extended_bits.catalog_bits_hash)


# ---------------------------------------------------------------------------
# The data sort
# ---------------------------------------------------------------------------


class TestDataSort(unittest.TestCase):
    def test_a_control_reference_in_the_data_sort_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("ctl.priv_approval >= async_ticket", where="t")
        self.assertEqual(caught.exception.code, "E-SYN-010")

    def test_a_non_bool_root_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("a.t", where="t")
        self.assertEqual(caught.exception.code, "E-TYP-001")

    def test_tick_and_duration_do_not_convert_implicitly(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("a.t < 30m", where="t")
        self.assertEqual(caught.exception.code, "E-TYP-001")

    def test_subtracting_two_ticks_yields_a_duration(self) -> None:
        node = rules.compile_when("b.t - a.t < 30m", where="t")
        self.assertIsNotNone(node)

    def test_comparing_an_entity_with_a_tick_is_rejected(self) -> None:
        with self.assertRaises(GuardError):
            rules.compile_when("a.principal == a.t", where="t")

    def test_a_cr_byte_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("a.principal\r == b.principal", where="t")
        self.assertEqual(caught.exception.code, "E-LEX-001")

    def test_a_dot_followed_by_a_digit_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("a.0principal == b.principal", where="t")
        self.assertEqual(caught.exception.code, "E-LEX-004")

    def test_a_non_integral_duration_is_rejected(self) -> None:
        with self.assertRaises(GuardError) as caught:
            rules.duration_ticks("500ms")
        self.assertEqual(caught.exception.code, "E-SEM-030")

    def test_durations_normalise_to_whole_ticks(self) -> None:
        self.assertEqual(rules.duration_ticks("30m"), 1800)
        self.assertEqual(rules.duration_ticks("72h"), 259200)
        self.assertEqual(rules.duration_ticks("1tick"), 1)

    def test_conjunct_order_does_not_change_the_compiled_bytes(self) -> None:
        """Children of a commutative connective sort by content, never by position."""
        left = rules.compile_when("a.principal == b.principal and a.t <= b.t", where="t")
        right = rules.compile_when("a.t <= b.t and a.principal == b.principal", where="t")
        assert left is not None and right is not None
        self.assertEqual(left.canonical_bytes(), right.canonical_bytes())

    def test_evaluation_is_total_over_an_unbound_field(self) -> None:
        """An unbound slot makes the guard false; it never raises out of a fixpoint."""
        node = rules.compile_when("a.principal == b.principal", where="t")
        self.assertFalse(rules.eval_when(node, {}))
        self.assertTrue(rules.eval_when(node, {"a.principal": "x", "b.principal": "x"}))

    def test_within_desugars_into_an_absolute_span_comparison(self) -> None:
        node = rules.compile_when("within(a.t, b.t, 30m)", where="t")
        self.assertTrue(rules.eval_when(node, {"a.t": 100, "b.t": 100 + 1800}))
        self.assertFalse(rules.eval_when(node, {"a.t": 100, "b.t": 100 + 1801}))
        self.assertTrue(rules.eval_when(node, {"a.t": 100 + 1800, "b.t": 100}))

    def test_adding_two_ticks_is_a_type_error(self) -> None:
        """Two instants do not add. Only a tick plus a duration is an instant."""
        with self.assertRaises(GuardError) as caught:
            rules.compile_when("a.t + b.t < 30m", where="t")
        self.assertEqual(caught.exception.code, "E-TYP-001")

    def test_arithmetic_is_clamped_to_the_declared_i64_envelope(self) -> None:
        """Python integers do not wrap, so saturation is about staying inside the declared
        width rather than about recovering from an overflow; the clamp is what keeps every
        arithmetic site total and inside what the canonical encoding can represent."""
        self.assertEqual(rules._saturate(1 << 64), (1 << 63) - 1)
        self.assertEqual(rules._saturate(-(1 << 64)), -(1 << 63))
        node = rules.compile_when("b.t - a.t < 30m", where="t")
        self.assertFalse(rules.eval_when(node, {"a.t": 0, "b.t": 1 << 70}))
        self.assertTrue(rules.eval_when(node, {"a.t": 0, "b.t": 1799}))


# ---------------------------------------------------------------------------
# Loading the shipped table
# ---------------------------------------------------------------------------


class TestShippedTable(unittest.TestCase):
    def setUp(self) -> None:
        self.table = fixture.rule_table(RULES_TOML)

    def test_six_detect_rules_and_two_obligation_axioms(self) -> None:
        self.assertEqual(len(self.table.detect_rules), 6)
        self.assertEqual(len(self.table.obligation_rules), 2)

    def test_route_a_blockers_are_the_four_corridor_atoms(self) -> None:
        """The union over route A's rules is exactly the corridor the scenario declares."""
        union = 0
        for rule_id in ("r0001", "r0002", "r0003"):
            union |= self.table.get("rl:" + rule_id).mask
        literals = {lit.bit: (lit.control_id.snake, lit.level) for lit in self.table.literals()}
        named = sorted(literals[bit] for bit in range(64) if union & (1 << bit))
        self.assertEqual(
            named,
            [("egress_seg", 1), ("rate_limit", 1), ("session_binding", 1), ("token_expiry", 1)],
        )

    def test_route_b_is_a_singleton_corridor(self) -> None:
        union = self.table.get("rl:r0004").mask | self.table.get("rl:r0005").mask
        self.assertEqual(union.bit_count(), 1)
        literals = {lit.bit: (lit.control_id.snake, lit.level) for lit in self.table.literals()}
        self.assertEqual(literals[union.bit_length() - 1], ("priv_approval", 1))

    def test_the_absence_rule_is_the_only_silent_possible_detect_rule(self) -> None:
        silent = [r.rule_id for r in self.table.detect_rules if r.rule.silent_possible]
        self.assertEqual([str(r) for r in silent], ["rl:r0004"])

    def test_the_three_temporal_operators_are_all_exercised(self) -> None:
        ops = sorted({r.temporal.op for r in self.table.detect_rules if r.temporal})
        self.assertEqual(ops, ["absence", "distinct", "seq"])

    def test_axiom_predicates_are_derived_not_declared(self) -> None:
        self.assertEqual(
            self.table.axiom_predicates,
            (
                "gw.request",
                "iam.role_assumed",
                "idp.refresh_exchange",
                "res.export",
                "res.read",
            ),
        )

    def test_rules_hash_is_stable_across_a_comment_edit(self) -> None:
        """Reflowing a comment must not invalidate an archived certificate."""
        text = RULES_TOML.read_text(encoding="utf-8")
        edited = _write(text + "\n# an added comment, and nothing else\n")
        other = rules.compile_rules(edited, fixture.catalog(), fixture.bit_table())
        self.assertEqual(self.table.rules_hash, other.rules_hash)
        self.assertEqual(self.table.guard_ast_hash, other.guard_ast_hash)
        self.assertNotEqual(self.table.rules_text_hash, other.rules_text_hash)

    def test_every_digest_declares_the_algorithm_actually_computed(self) -> None:
        for value in (
            self.table.rules_hash,
            self.table.guard_ast_hash,
            self.table.rules_text_hash,
            self.table.catalog_bits_hash,
            self.table.controls_hash,
        ):
            self.assertTrue(value.startswith(canon.HASH_REF_PREFIX))
            self.assertNotIn("blake3", value)

    def test_the_cae_carries_its_magic_and_its_rule_count(self) -> None:
        payload = self.table.cae_bytes()
        self.assertTrue(payload.startswith(b"CAE1"))
        self.assertEqual(int.from_bytes(payload[4:8], "big"), len(self.table.rules))

    def test_compilation_is_a_pure_function_of_its_inputs(self) -> None:
        again = fixture.rule_table(RULES_TOML)
        self.assertEqual(self.table.cae_bytes(), again.cae_bytes())
        self.assertEqual(self.table.rules_hash, again.rules_hash)


# ---------------------------------------------------------------------------
# The lints
# ---------------------------------------------------------------------------


class TestLints(unittest.TestCase):
    def test_a_delete_effect_is_rejected(self) -> None:
        """Facts are append-only; expiry is a later fact not being derived."""
        for line in (
            'delete = "session.established(principal, credential, t)"',
            'effect = "retract"',
            "retracts = [\"session.established(principal, credential, t)\"]",
            'expires = "1h"',
        ):
            with self.subTest(line=line):
                with self.assertRaises(SchemaError) as caught:
                    _one_rule(extra=line)
                self.assertEqual(caught.exception.code, "E-SCHEMA-UNKNOWN")

    def test_an_unimplemented_persistence_is_rejected_not_downgraded(self) -> None:
        for value in ("sticky", "until(a.t + 1h)"):
            with self.subTest(value=value):
                with self.assertRaises(SchemaError):
                    _one_rule(persistence=value)

    def test_a_detect_rule_with_no_axiom_slot_is_rejected(self) -> None:
        path = _write(
            """
schema = "spectra.vs.rules/1"

[[rule]]
id = "r0001"
version = "1.0.0"
dimension = "session"
kind = "detect"
head = "a.one(principal, t)"
body = ["a.two(principal, t)"]
producing_sources = ["idp_auth"]
silent_possible = false

[[rule]]
id = "r0002"
version = "1.0.0"
dimension = "session"
kind = "detect"
head = "a.two(principal, t)"
body = ["a.one(principal, t)"]
producing_sources = ["idp_auth"]
silent_possible = false
"""
        )
        with self.assertRaises(SchemaError):
            rules.compile_rules(path, fixture.catalog(), fixture.bit_table())

    def test_an_axiom_pattern_out_of_role_order_is_rejected(self) -> None:
        path = _write(
            _MINIMAL.format(blocked="", persistence="instant", extra="").replace(
                "idp.refresh_exchange(credential, principal, t)",
                "idp.refresh_exchange(principal, credential, t)",
            )
        )
        with self.assertRaises(Exception) as caught:
            rules.compile_rules(path, fixture.catalog(), fixture.bit_table())
        self.assertIn("E-CANON-ORDER", str(caught.exception))

    def test_t_may_not_name_an_entity_argument(self) -> None:
        with self.assertRaises(SchemaError):
            rules.parse_pattern("some.predicate(t, other, tick)")

    def test_an_unbound_head_variable_is_rejected(self) -> None:
        path = _write(
            _MINIMAL.format(blocked="", persistence="instant", extra="").replace(
                "session.established(principal, credential, t)",
                "session.established(principal, device, t)",
            )
        )
        with self.assertRaises(SchemaError):
            rules.compile_rules(path, fixture.catalog(), fixture.bit_table())

    def test_a_body_longer_than_four_patterns_is_rejected(self) -> None:
        body = ", ".join(f'"p.q{i}(principal, t{i})"' for i in range(5))
        path = _write(
            _MINIMAL.format(blocked="", persistence="instant", extra="").replace(
                '["idp.refresh_exchange(credential, principal, t)"]', f"[{body}]"
            )
        )
        with self.assertRaises(SchemaError):
            rules.compile_rules(path, fixture.catalog(), fixture.bit_table())

    def test_an_unimplemented_temporal_operator_is_rejected(self) -> None:
        path = _write(
            _MINIMAL.format(
                blocked="",
                persistence="instant",
                extra='temporal = { op = "overlaps", within = "1h" }',
            )
        )
        with self.assertRaises(SchemaError):
            rules.compile_rules(path, fixture.catalog(), fixture.bit_table())

    def test_the_foundation_rejects_a_conjunctive_blocker_on_an_instance(self) -> None:
        """The narrowing is enforced on the record type too, not only at compile time."""
        head = model.Fact.mint("p.q", (), 0)
        evidence = (
            model.EvidenceRef(
                binding="a",
                event_id=EventId.mint(b"an event"),
                source_id=SourceId.of("idp_auth"),
                t_evt_ns=0,
            ),
        )
        with self.assertRaises(SchemaError) as caught:
            model.RuleInstance.mint(
                rule_id=RuleId.of("r0001"),
                rule_version="1.0.0",
                head=head.fact_key,
                body=(),
                blockers=(0b11,),
                observed=model.Observation.OBSERVED,
                tick=0,
                evidence=evidence,
            )
        self.assertEqual(caught.exception.code, "E-VS-BLOCK-CONJ")


if __name__ == "__main__":
    unittest.main(verbosity=2)
