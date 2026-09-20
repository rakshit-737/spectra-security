"""Unit tests for S5 entity resolution.

Run from the repository root:

    python python/spectra_vs/tests/test_resolve.py

What these tests pin: that only exact string joins ever fire, that AMBIGUOUS survives
into the artifact and raises the run flag instead of being collapsed to a guess, that an
entity keeps its id when records are deleted underneath it, and that the rule table's
own ordering cannot reach `er.json`.
"""

from __future__ import annotations

import json
import pathlib
import random
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_core import canon  # noqa: E402
from spectra_core.errors import SchemaError  # noqa: E402
from spectra_core.ids import SourceId  # noqa: E402
from spectra_core.model import IntegrityClass, Source  # noqa: E402

from spectra_vs import ingest as S4  # noqa: E402
from spectra_vs import resolve as S5  # noqa: E402

SOURCES = (
    Source(
        source_id=SourceId.of("gw_access"),
        integrity_class=IntegrityClass.SEQUENCED,
        source_rank=2,
        emits_event_types=("gw_call",),
    ),
    Source(
        source_id=SourceId.of("idp_auth"),
        integrity_class=IntegrityClass.CHAINED,
        source_rank=1,
        emits_event_types=("auth_refresh",),
    ),
)

RULES = S5.join_rules_from_tables(
    principals=("alice", "svc_export"),
    devices=("lap_alice",),
    credentials=("tok_a", "tok_b"),
    resources=("res_bulk",),
)


def raw_line(source: str, seq: int, t_ns: int, event_type: str, **attrs: str) -> bytes:
    return S4.scf_line(
        {
            "attrs": dict(attrs),
            "event_type": event_type,
            "seq": seq,
            "source_id": source,
            "t_evt_ns": str(t_ns),
        }
    )


BASE_LINES = (
    raw_line(
        "idp_auth", 0, 1_000_000_000, "auth_refresh", principal="alice", token="tok_a",
        device="lap_alice",
    ),
    raw_line("gw_access", 0, 2_000_000_000, "gw_call", token="tok_a", resource="res_bulk"),
    raw_line("gw_access", 1, 3_000_000_000, "gw_call", token="tok_zz", resource="res_bulk"),
)


def bundle(lines=BASE_LINES):
    return S4.ingest_bytes(b"".join(lines), SOURCES).events


# ---------------------------------------------------------------------------
# The rule table
# ---------------------------------------------------------------------------


class TestJoinRule(unittest.TestCase):
    def test_the_closed_five_are_built_and_sorted(self) -> None:
        self.assertEqual(
            [rule.join_rule_id for rule in RULES],
            [
                "r_exact_device",
                "r_exact_principal",
                "r_exact_resource",
                "r_exact_session_by_token",
                "r_exact_token",
            ],
        )
        for rule in RULES:
            self.assertIn(rule.join_rule_id, S5.JOIN_RULE_IDS)

    def test_an_empty_table_yields_no_rule(self) -> None:
        self.assertEqual(S5.join_rules_from_tables(principals=("alice",)).__len__(), 1)
        self.assertEqual(S5.join_rules_from_tables(), ())

    def test_an_undeclared_join_rule_id_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            S5.JoinRule("r_fuzzy_principal", "principal", "principal", "account", (("a", ("a",)),))

    def test_a_kind_outside_the_closed_twelve_is_rejected(self) -> None:
        with self.assertRaises(SchemaError):
            S5.JoinRule("r_exact_principal", "principal", "principal", "zone", (("a", ("a",)),))

    def test_an_unsorted_table_is_rejected_rather_than_sorted(self) -> None:
        with self.assertRaises(Exception):
            S5.JoinRule(
                "r_exact_principal", "principal", "principal", "account",
                (("b", ("b",)), ("a", ("a",))),
            )

    def test_lookup_is_exact_and_has_no_nearest_neighbour(self) -> None:
        rule = [r for r in RULES if r.join_rule_id == "r_exact_principal"][0]
        self.assertEqual(rule.lookup("alice"), ("alice",))
        self.assertEqual(rule.lookup("alic"), ())
        self.assertEqual(rule.lookup("Alice"), ())
        self.assertEqual(rule.lookup("alice "), ())


# ---------------------------------------------------------------------------
# RESOLVED
# ---------------------------------------------------------------------------


class TestResolved(unittest.TestCase):
    def setUp(self) -> None:
        self.result = S5.resolve(bundle(), RULES)

    def test_roles_bound_on_the_first_record(self) -> None:
        first = bundle()[0]
        roles = sorted(
            row.role for row in self.result.bindings if row.event_id == first.event_id
        )
        self.assertEqual(roles, ["device", "principal", "session", "token"])

    def test_a_token_yields_both_a_credential_and_a_session(self) -> None:
        kinds = {entity.kind for entity in self.result.entities}
        self.assertEqual(kinds, {"account", "credential", "host", "resource", "session"})

    def test_entity_ids_carry_their_kind_and_recompute(self) -> None:
        for entity in self.result.entities:
            self.assertTrue(str(entity.entity_id).startswith(f"en:{entity.kind}:"))
            self.assertTrue(entity.verify_id())

    def test_resolved_from_lists_every_record_that_bound_the_entity(self) -> None:
        token = [
            entity
            for entity in self.result.entities
            if entity.kind == "credential" and entity.canonical_name == "tok_a"
        ][0]
        self.assertEqual(len(token.resolved_from), 2)
        self.assertEqual(token.join_rule_id, "r_exact_token")

    def test_counts_are_reported_per_role_and_per_join_rule(self) -> None:
        counts = self.result.counts
        self.assertEqual(counts.events_total, 3)
        self.assertEqual(counts.events_with_bindings, 3)
        self.assertEqual(counts.roles_resolved, 8)
        self.assertEqual(counts.roles_ambiguous, 0)
        self.assertEqual(counts.roles_unresolved, 2)
        self.assertEqual(dict((role, (r, a, u)) for role, r, a, u in counts.by_role)["token"],
                         (2, 0, 1))
        self.assertEqual(
            counts.by_join_rule,
            (
                ("r_exact_device", 1),
                ("r_exact_principal", 1),
                ("r_exact_resource", 2),
                ("r_exact_session_by_token", 2),
                ("r_exact_token", 2),
            ),
        )

    def test_er_json_members_are_exactly_the_contract(self) -> None:
        obj = json.loads(self.result.er_bytes)
        self.assertEqual(set(obj), {"ambiguous", "bindings", "entities", "schema"})
        self.assertEqual(obj["schema"], "spectra.vs.er/1")
        for entity in obj["entities"]:
            self.assertEqual(
                set(entity),
                {"canonical_name", "entity_id", "join_rule_id", "kind", "resolved_from"},
            )
        for binding in obj["bindings"]:
            self.assertEqual(set(binding), {"entity_id", "event_id", "role"})

    def test_declared_sorted_arrays_are_strictly_ascending(self) -> None:
        obj = json.loads(self.result.er_bytes)
        canon.check_strictly_ascending(
            [e["entity_id"] for e in obj["entities"]], canon.byte_order_key, where="entities"
        )
        canon.check_strictly_ascending(
            [(b["event_id"], b["role"]) for b in obj["bindings"]], lambda k: k, where="bindings"
        )

    def test_er_hash_is_the_digest_of_the_er_bytes(self) -> None:
        self.assertEqual(self.result.er_hash, canon.hash_ref("er", self.result.er_bytes))
        self.assertTrue(self.result.er_hash.startswith("b2b256:"))

    def test_flag_is_clear_when_nothing_is_ambiguous(self) -> None:
        self.assertFalse(self.result.er_ambiguous)


# ---------------------------------------------------------------------------
# UNRESOLVED
# ---------------------------------------------------------------------------


class TestUnresolved(unittest.TestCase):
    def test_an_unjoinable_value_binds_nothing_and_is_reported(self) -> None:
        result = S5.resolve(bundle(), RULES)
        rows = [row for row in result.unresolved if row.role == "token"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, "tok_zz")
        self.assertEqual(rows[0].attr_key, "token")
        self.assertNotIn("tok_zz", {e.canonical_name for e in result.entities})

    def test_an_absent_attribute_produces_no_outcome_at_all(self) -> None:
        lines = (raw_line("gw_access", 0, 1, "gw_call"),)
        result = S5.resolve(bundle(lines), RULES)
        self.assertEqual(result.counts.roles_resolved, 0)
        self.assertEqual(result.counts.roles_unresolved, 0)
        self.assertEqual(result.counts.roles_ambiguous, 0)
        self.assertEqual(result.counts.events_with_bindings, 0)

    def test_unresolved_is_absent_from_er_json(self) -> None:
        result = S5.resolve(bundle(), RULES)
        self.assertTrue(result.unresolved)
        self.assertNotIn(b"tok_zz", result.er_bytes)


# ---------------------------------------------------------------------------
# AMBIGUOUS
# ---------------------------------------------------------------------------


AMBIGUOUS_RULES = (
    S5.JoinRule(
        "r_exact_principal",
        "principal",
        "principal",
        "account",
        (("shared", ("alice", "bob")),),
    ),
)


class TestAmbiguous(unittest.TestCase):
    def setUp(self) -> None:
        lines = (raw_line("idp_auth", 0, 1, "auth_refresh", principal="shared"),)
        self.result = S5.resolve(bundle(lines), AMBIGUOUS_RULES)

    def test_ambiguity_is_never_collapsed_into_a_binding(self) -> None:
        self.assertEqual(self.result.bindings, ())
        self.assertEqual(len(self.result.ambiguous), 1)
        self.assertEqual(len(self.result.ambiguous[0].candidates), 2)

    def test_the_run_flag_is_raised(self) -> None:
        self.assertTrue(self.result.er_ambiguous)

    def test_candidates_are_sorted_and_defined_in_the_same_artifact(self) -> None:
        obj = json.loads(self.result.er_bytes)
        candidates = obj["ambiguous"][0]["candidates"]
        self.assertEqual(candidates, sorted(candidates))
        defined = {entity["entity_id"] for entity in obj["entities"]}
        for candidate in candidates:
            self.assertIn(candidate, defined)

    def test_a_candidate_that_never_resolved_carries_an_empty_resolved_from(self) -> None:
        obj = json.loads(self.result.er_bytes)
        for entity in obj["entities"]:
            self.assertEqual(entity["resolved_from"], [])

    def test_two_rules_on_one_role_from_different_tables_are_ambiguous(self) -> None:
        rules = (
            S5.JoinRule("r_exact_principal", "actor", "principal", "account", (("x", ("x",)),)),
            S5.JoinRule("r_exact_device", "actor", "principal", "host", (("x", ("x",)),)),
        )
        lines = (raw_line("idp_auth", 0, 1, "auth_refresh", principal="x"),)
        result = S5.resolve(bundle(lines), rules)
        self.assertEqual(result.counts.roles_ambiguous, 1)
        self.assertEqual(result.counts.roles_resolved, 0)
        self.assertTrue(result.er_ambiguous)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def test_rule_table_order_never_reaches_er_json(self) -> None:
        reference = S5.resolve(bundle(), RULES)
        rng = random.Random(20260921)
        for _ in range(64):
            shuffled = list(RULES)
            rng.shuffle(shuffled)
            candidate = S5.resolve(bundle(), shuffled)
            self.assertEqual(candidate.er_bytes, reference.er_bytes)
            self.assertEqual(candidate.er_hash, reference.er_hash)

    def test_bundle_order_never_reaches_er_json(self) -> None:
        reference = S5.resolve(bundle(), RULES)
        rng = random.Random(11)
        for _ in range(32):
            shuffled = list(BASE_LINES)
            rng.shuffle(shuffled)
            candidate = S5.resolve(bundle(tuple(shuffled)), RULES)
            self.assertEqual(candidate.er_bytes, reference.er_bytes)

    def test_an_entity_id_survives_deletion_of_its_records(self) -> None:
        """Degradation deletes records; an entity's id must not move when it does.

        If the id shifted, every fact naming the entity would change key and the two
        completeness cells could not be compared at all.
        """
        full = S5.resolve(bundle(), RULES)
        degraded = S5.resolve(bundle(BASE_LINES[1:]), RULES)
        # Keyed by (kind, name): one token mints both a credential and a session, so a
        # canonical name alone is not an identity and must not be treated as one.
        full_ids = {(e.kind, e.canonical_name): str(e.entity_id) for e in full.entities}
        self.assertLess(len(degraded.entities), len(full.entities))
        for entity in degraded.entities:
            self.assertEqual(
                str(entity.entity_id), full_ids[(entity.kind, entity.canonical_name)]
            )

    def test_a_duplicate_join_rule_is_a_usage_error(self) -> None:
        with self.assertRaises(SchemaError):
            S5.resolve(bundle(), RULES + (RULES[0],))

    def test_write_emits_both_artifacts(self) -> None:
        result = S5.resolve(bundle(), RULES)
        with tempfile.TemporaryDirectory() as tmp:
            er_path, quality_path = result.write(tmp)
            self.assertEqual(er_path.read_bytes(), result.er_bytes)
            quality = json.loads(quality_path.read_bytes())
        self.assertEqual(quality["schema"], "spectra.vs.er_quality/1")
        self.assertFalse(quality["er_ambiguous"])
        self.assertEqual(quality["counts"]["roles_unresolved"], 2)

    def test_no_numeric_judgement_field_is_emitted(self) -> None:
        banned = (
            "confidence", "score", "severity", "probability", "likelihood", "certainty",
            "risk", "criticality", "priority", "weight", "rating", "grade", "percentile",
            "pct", "percent", "normalized_", "strength",
        )
        result = S5.resolve(bundle(), RULES)
        text = result.er_bytes.decode("utf-8") + S4.scf_dumps(result.quality_obj())
        for word in banned:
            self.assertNotIn(word, text, word)


if __name__ == "__main__":
    unittest.main(verbosity=2)
