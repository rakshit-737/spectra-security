"""Unit tests for the spectra_core foundation.

Run from the repository root:

    python python/spectra_core/tests/test_core.py

The prelude below is the documented two-line bootstrap of `spectra_core.bootstrap`: this
file is run directly rather than through a test runner, because there is no pytest to
rely on and a foundation that needs a package manager to test itself is not a foundation.

What these tests are for, stated so that a later edit does not soften them: each one
pins a property that another stage is entitled to assume. The determinism tests in
particular must go red under a mutation, which is why they compare bytes rather than
asserting that a function "returns something sorted".
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))

from spectra_core import canon, errors, ids, model  # noqa: E402
from spectra_core.bootstrap import find_repo_root, install, workspace_src_dirs  # noqa: E402


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


class TestIdentifierGrammar(unittest.TestCase):
    def test_h256_round_trip(self) -> None:
        rid = ids.RecordId.mint(b"a telemetry line")
        self.assertTrue(str(rid).startswith("rc:"))
        self.assertEqual(len(str(rid)), 3 + 64)
        self.assertEqual(rid, ids.RecordId(str(rid)))

    def test_h128_is_a_prefix_of_h256(self) -> None:
        """57.3 rule 2: truncation is a prefix, never a fold and never an XOR."""
        payload = b"one occurrence"
        wide = canon.digest_hex("ev", payload, 32)
        narrow = canon.digest_hex("ev", payload, 16)
        self.assertEqual(wide[:32], narrow)
        self.assertEqual(str(ids.EventId.mint(payload)), "ev:" + narrow)

    def test_every_declared_type_validates_its_own_mint(self) -> None:
        for id_type in (
            ids.RecordId,
            ids.BundleId,
            ids.FactHash,
            ids.InstanceId,
            ids.LicenseId,
            ids.CutId,
            ids.CorridorId,
            ids.HypothesisId,
            ids.HypergraphId,
            ids.RunId,
            ids.CertId,
            ids.EventId,
            ids.TransitionId,
            ids.WindowId,
            ids.AssignmentId,
            ids.DegradationId,
        ):
            with self.subTest(id_type=id_type.__name__):
                value = id_type.mint(b"payload")
                self.assertIsInstance(value, id_type)
                self.assertEqual(value, ids.parse_id(str(value)))

    def test_wrong_hex_width_is_rejected(self) -> None:
        with self.assertRaises(errors.IdentifierError):
            ids.RecordId("rc:" + "ab" * 16)  # an h128 body in an h256 type
        with self.assertRaises(errors.IdentifierError):
            ids.EventId("ev:" + "ab" * 32)  # an h256 body in an h128 type

    def test_uppercase_hex_is_rejected(self) -> None:
        with self.assertRaises(errors.IdentifierError):
            ids.FactHash("fh:" + "AB" * 32)

    def test_symbolic_grammar(self) -> None:
        self.assertEqual(str(ids.SourceId.of("iam_audit")), "src:iam_audit")
        self.assertEqual(ids.SourceId.of("iam_audit").snake, "iam_audit")
        for bad in ("Iam", "1iam", "iam-audit", "", "i" * 49, "iam audit"):
            with self.subTest(bad=bad), self.assertRaises(errors.IdentifierError):
                ids.SourceId.of(bad)

    def test_literal_id_is_built_from_a_typed_control(self) -> None:
        control = ids.ControlId.of("priv_approval")
        literal = ids.LiteralId.of(control, 2)
        self.assertEqual(str(literal), "lit:priv_approval@2")
        self.assertEqual(literal.control, control)
        self.assertEqual(literal.level, 2)
        with self.assertRaises(errors.IdentifierTypeError):
            ids.LiteralId.of(ids.SourceId.of("priv_approval"), 2)  # type: ignore[arg-type]
        with self.assertRaises(errors.IdentifierError):
            ids.LiteralId("lit:priv_approval@100")  # level is 0..99

    def test_entity_id_carries_a_closed_kind(self) -> None:
        entity = ids.EntityId.mint("credential", b"token-7")
        self.assertEqual(entity.kind, "credential")
        with self.assertRaises(errors.IdentifierError):
            ids.EntityId.mint("principal", b"x")  # a Table D synonym, not a kind
        with self.assertRaises(errors.IdentifierError):
            ids.EntityId("en:" + "ab" * 16)  # missing the kind segment

    def test_collector_and_scenario_versions(self) -> None:
        self.assertEqual(str(ids.CollectorId.of("idp_reader", 3)), "col:idp_reader@3")
        self.assertEqual(str(ids.ScenarioId.of("token_pivot", 1)), "sc:token_pivot@1")
        with self.assertRaises(errors.IdentifierError):
            ids.ScenarioId("sc:token_pivot@01")  # no leading zeros
        with self.assertRaises(errors.IdentifierError):
            ids.ScenarioId("sc:token-pivot@1")  # hyphens are illegal

    def test_state_id_is_lowercase_and_two_part(self) -> None:
        self.assertEqual(str(ids.StateId.of("session", "active")), "st:session:active")
        with self.assertRaises(errors.IdentifierError):
            ids.StateId("st:session:ACTIVE")


class TestIdentifierTypeSeparation(unittest.TestCase):
    """57.1 rule 7: the wrong id type must be detectable, not a silent success."""

    def test_sibling_types_do_not_substitute(self) -> None:
        fact = ids.FactHash.mint(b"f")
        with self.assertRaises(errors.IdentifierTypeError):
            ids.require_id(fact, ids.RecordId, where="test")

    def test_a_bare_string_is_rejected(self) -> None:
        raw = str(ids.RecordId.mint(b"f"))
        self.assertIsInstance(raw, str)
        with self.assertRaises(errors.IdentifierTypeError):
            ids.require_id(raw, ids.RecordId, where="test")

    def test_a_valid_id_string_of_another_type_cannot_be_reconstructed(self) -> None:
        fact = str(ids.FactHash.mint(b"f"))
        with self.assertRaises(errors.IdentifierError):
            ids.RecordId(fact)  # the prefix belongs to a different concept

    def test_parse_id_returns_the_declared_type(self) -> None:
        self.assertIsInstance(ids.parse_id("src:iam_audit"), ids.SourceId)
        self.assertIsInstance(ids.parse_id("lit:egress_seg@1"), ids.LiteralId)
        with self.assertRaises(errors.IdentifierError):
            ids.parse_id("zz:whatever")
        with self.assertRaises(errors.IdentifierError):
            ids.parse_id("no-prefix-at-all")

    def test_prefixes_are_mutually_non_prefixing(self) -> None:
        prefixes = sorted(ids.PREFIX_TO_TYPE)
        for i, outer in enumerate(prefixes):
            for inner in prefixes[i + 1 :]:
                self.assertFalse(inner.startswith(outer), f"{outer} prefixes {inner}")

    def test_run_local_ids_are_refused_by_the_certificate_gate(self) -> None:
        with self.assertRaises(errors.IdentifierWidthError):
            ids.reject_run_local_in_certificate(ids.EventId.mint(b"e"), where="test")
        certifiable = ids.FactHash.mint(b"f")
        self.assertIs(
            ids.reject_run_local_in_certificate(certifiable, where="test"), certifiable
        )

    def test_ids_sort_bytewise_as_plain_strings(self) -> None:
        values = [ids.SourceId.of(n) for n in ("res_access", "gw_access", "iam_audit")]
        self.assertEqual(
            [str(v) for v in sorted(values)],
            ["src:gw_access", "src:iam_audit", "src:res_access"],
        )


# ---------------------------------------------------------------------------
# Canonical encoding and hashing
# ---------------------------------------------------------------------------


class TestDigestDeclaration(unittest.TestCase):
    def test_the_algorithm_is_named_honestly(self) -> None:
        self.assertEqual(canon.HASH_ALGORITHM, "blake2b-256")
        self.assertEqual(canon.SPEC_HASH_ALGORITHM, "blake3")
        self.assertNotEqual(canon.HASH_ALGORITHM, canon.SPEC_HASH_ALGORITHM)
        self.assertEqual(canon.HASH_REF_PREFIX, "b2b256:")
        self.assertIn("blake3", canon.HASH_SUBSTITUTION_NOTE)
        self.assertIn("blake2b-256", canon.HASH_SUBSTITUTION_NOTE)

    def test_no_digest_is_ever_labelled_blake3(self) -> None:
        reference = canon.hash_ref("rc", b"bytes")
        self.assertTrue(reference.startswith("b2b256:"))
        self.assertNotIn("blake3", reference)
        with self.assertRaises(errors.CanonError):
            canon.parse_hash_ref("blake3:" + "ab" * 32)

    def test_hash_ref_round_trips(self) -> None:
        reference = canon.hash_ref("rc", b"bytes")
        self.assertEqual(canon.parse_hash_ref(reference).hex(), reference[len("b2b256:") :])

    def test_domain_separation_changes_the_digest(self) -> None:
        self.assertNotEqual(canon.digest("rc", b"x"), canon.digest("fh", b"x"))

    def test_the_domain_construction_matches_57_3(self) -> None:
        import hashlib

        expected = hashlib.blake2b(
            b"spectra/v1/" + b"rc" + bytes([0x1F]) + b"payload", digest_size=32
        ).digest()
        self.assertEqual(canon.digest("rc", b"payload"), expected)

    def test_a_unit_separator_in_kind_is_refused(self) -> None:
        with self.assertRaises(errors.CanonError):
            canon.digest("rc\x1ffh", b"x")


class TestCanonicalEncoding(unittest.TestCase):
    def test_integers_are_big_endian_fixed_width(self) -> None:
        self.assertEqual(canon.u8(1), b"\x01")
        self.assertEqual(canon.u16(1), b"\x00\x01")
        self.assertEqual(canon.u32(1), b"\x00\x00\x00\x01")
        self.assertEqual(canon.u64(1), b"\x00" * 7 + b"\x01")
        self.assertEqual(canon.i64(-1), b"\xff" * 8)

    def test_width_violations_are_loud(self) -> None:
        for encoder, value in ((canon.u8, 256), (canon.u16, 65536), (canon.u32, 1 << 32)):
            with self.subTest(encoder=encoder.__name__), self.assertRaises(errors.CanonError):
                encoder(value)
        with self.assertRaises(errors.CanonError):
            canon.u8(-1)

    def test_floats_are_refused_everywhere_an_integer_is_expected(self) -> None:
        for encoder in (canon.u8, canon.u16, canon.u32, canon.u64, canon.i64, canon.leb128):
            with self.subTest(encoder=encoder.__name__):
                with self.assertRaises(errors.CanonError) as raised:
                    encoder(1.0)
                self.assertEqual(raised.exception.code, "E-CANON-FLOAT")

    def test_bools_are_not_integers_here(self) -> None:
        with self.assertRaises(errors.CanonError):
            canon.u8(True)
        with self.assertRaises(errors.CanonError):
            canon.boolean(1)

    def test_leb128_is_minimal(self) -> None:
        self.assertEqual(canon.leb128(0), b"\x00")
        self.assertEqual(canon.leb128(127), b"\x7f")
        self.assertEqual(canon.leb128(128), b"\x80\x01")
        self.assertEqual(canon.leb128(300), b"\xac\x02")
        with self.assertRaises(errors.CanonError):
            canon.leb128(-1)

    def test_sequences_are_length_prefixed_and_unambiguous(self) -> None:
        """Two different splits of the same octets must not encode identically."""
        left = canon.ordered_seq([canon.blob(b"ab"), canon.blob(b"c")])
        right = canon.ordered_seq([canon.blob(b"a"), canon.blob(b"bc")])
        self.assertNotEqual(left, right)

    def test_sorted_set_is_order_independent_and_rejects_duplicates(self) -> None:
        a = canon.sorted_set([canon.ascii_text("b"), canon.ascii_text("a")])
        b = canon.sorted_set([canon.ascii_text("a"), canon.ascii_text("b")])
        self.assertEqual(a, b)
        with self.assertRaises(errors.CanonError):
            canon.sorted_set([canon.ascii_text("a"), canon.ascii_text("a")])

    def test_ordered_seq_is_order_dependent(self) -> None:
        a = canon.ordered_seq([canon.ascii_text("b"), canon.ascii_text("a")])
        b = canon.ordered_seq([canon.ascii_text("a"), canon.ascii_text("b")])
        self.assertNotEqual(a, b)

    def test_pairs_are_sorted_and_reject_duplicate_keys(self) -> None:
        self.assertEqual(canon.pairs([("b", "2"), ("a", "1")]), canon.pairs([("a", "1"), ("b", "2")]))
        with self.assertRaises(errors.CanonError) as raised:
            canon.pairs([("a", "1"), ("a", "2")])
        self.assertEqual(raised.exception.code, "E-CANON-DUPKEY")

    def test_text_is_normalised_to_nfc_before_encoding(self) -> None:
        composed = "é"
        decomposed = "é"
        self.assertNotEqual(composed, decomposed)
        self.assertEqual(canon.utf8_text(composed), canon.utf8_text(decomposed))

    def test_control_characters_are_refused_in_text(self) -> None:
        with self.assertRaises(errors.CanonError) as raised:
            canon.utf8_text("a\nb")
        self.assertEqual(raised.exception.code, "E-CANON-NFC")

    def test_mask_rendering_is_fixed_width(self) -> None:
        self.assertEqual(canon.mask_hex(0), "0x0000000000000000")
        self.assertEqual(canon.mask_hex(269), "0x000000000000010d")
        with self.assertRaises(errors.CanonError):
            canon.mask_hex(1 << 64)

    def test_no_json_appears_in_any_preimage(self) -> None:
        """A structural check: the encoders emit no JSON punctuation of their own."""
        encoded = canon.pairs([("k", "v")]) + canon.ordered_seq([canon.ascii_text("x")])
        for punctuation in (b"{", b"}", b"[", b"]", b'":'):
            self.assertNotIn(punctuation, encoded)


class TestOrderingHelpers(unittest.TestCase):
    def test_sorted_by_bytes_uses_byte_order(self) -> None:
        values = ["Zebra", "apple", "Apple"]
        self.assertEqual(canon.sorted_by_bytes(values, lambda s: s), ["Apple", "Zebra", "apple"])

    def test_sorted_unique_refuses_a_duplicate(self) -> None:
        self.assertEqual(canon.sorted_unique(["b", "a"]), ("a", "b"))
        with self.assertRaises(errors.CanonError):
            canon.sorted_unique(["a", "a"])

    def test_check_strictly_ascending_verifies_and_never_sorts(self) -> None:
        ordered = ("a", "b", "c")
        self.assertIs(
            canon.check_strictly_ascending(ordered, canon.byte_order_key, where="t"), ordered
        )
        for bad in (("b", "a"), ("a", "a")):
            with self.subTest(bad=bad):
                with self.assertRaises(errors.CanonError) as raised:
                    canon.check_strictly_ascending(bad, canon.byte_order_key, where="t")
                self.assertEqual(raised.exception.code, "E-CANON-ORDER")


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


class TestTime(unittest.TestCase):
    def test_tick_floors_across_zero(self) -> None:
        self.assertEqual(model.tick_of(0), 0)
        self.assertEqual(model.tick_of(999_999_999), 0)
        self.assertEqual(model.tick_of(1_000_000_000), 1)
        self.assertEqual(model.tick_of(-1), -1)

    def test_nanos_rejects_floats_and_bools(self) -> None:
        for bad in (1.0, True):
            with self.subTest(bad=bad), self.assertRaises(errors.SpectraError):
                model.check_nanos(bad, where="t")

    def test_intervals_are_half_open(self) -> None:
        span = model.Interval(10, 20)
        self.assertTrue(span.contains(10))
        self.assertFalse(span.contains(20))
        self.assertEqual(span.duration_ns, 10)
        self.assertTrue(span.covers(model.Interval(12, 18)))
        self.assertFalse(span.covers(model.Interval(12, 21)))
        self.assertTrue(span.overlaps(model.Interval(19, 25)))
        self.assertFalse(span.overlaps(model.Interval(20, 25)))

    def test_an_inverted_interval_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            model.Interval(20, 10)

    def test_no_wall_clock_is_read_in_this_layer(self) -> None:
        """A grep gate in source form: no module here may name a clock or a random source."""
        import spectra_core

        package_dir = pathlib.Path(spectra_core.__file__).parent
        banned = (
            "datetime.now",
            "time.time(",
            "time.monotonic",
            "os.urandom",
            "uuid.uuid1",
            "uuid.uuid4",
            "random.random",
            "secrets.",
        )
        for path in sorted(package_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for needle in banned:
                self.assertNotIn(needle, text, f"{path.name} names {needle}")


# ---------------------------------------------------------------------------
# Model types
# ---------------------------------------------------------------------------


def _source(name: str) -> ids.SourceId:
    return ids.SourceId.of(name)


def _entity(kind: str, name: str) -> ids.EntityId:
    return model.Entity.mint(kind, name, "r_exact_principal").entity_id


class TestRecordAndEvent(unittest.TestCase):
    def test_record_id_is_over_the_exact_bytes(self) -> None:
        raw = b'{"source_id":"src:idp_auth","seq":0}'
        record = model.Record.mint(_source("idp_auth"), raw)
        self.assertTrue(record.verify_id())
        self.assertEqual(record.record_id, ids.RecordId.mint(raw))
        # A one-octet change changes the record id; the occurrence's EventId would not.
        other = model.Record.mint(_source("idp_auth"), raw + b" ")
        self.assertNotEqual(record.record_id, other.record_id)

    def _event(self, **overrides: object) -> model.CanonicalEvent:
        fields: dict[str, object] = {
            "source_id": _source("idp_auth"),
            "seq": 7,
            "event_type": "idp.refresh_exchange",
            "t_evt_ns": 1_707_004_800_000_000_000,
            "attrs": (("actor", "u-1"), ("token", "t-9")),
        }
        fields.update(overrides)
        payload = b"".join(
            (
                canon.pairs(fields["attrs"]),  # type: ignore[arg-type]
                canon.utf8_text(fields["event_type"]),  # type: ignore[arg-type]
                canon.u32(fields["seq"]),  # type: ignore[arg-type]
                canon.ascii_text(fields["source_id"]),  # type: ignore[arg-type]
                canon.i64(fields["t_evt_ns"]),  # type: ignore[arg-type]
            )
        )
        return model.CanonicalEvent(
            event_id=ids.EventId.mint(payload),
            record_id=ids.RecordId.mint(b"line"),
            t_ing_ns=fields["t_evt_ns"] + 1000,  # type: ignore[operator]
            **fields,  # type: ignore[arg-type]
        )

    def test_event_id_excludes_ingestion_time(self) -> None:
        event = self._event()
        self.assertTrue(event.verify_id())
        later = model.CanonicalEvent(
            event_id=event.event_id,
            record_id=event.record_id,
            source_id=event.source_id,
            seq=event.seq,
            event_type=event.event_type,
            t_evt_ns=event.t_evt_ns,
            t_ing_ns=event.t_ing_ns + 10_000_000,
            attrs=event.attrs,
        )
        self.assertTrue(later.verify_id())
        self.assertEqual(event.identity_bytes(), later.identity_bytes())

    def test_event_id_depends_on_every_identity_field(self) -> None:
        base = self._event().identity_bytes()
        for overrides in (
            {"seq": 8},
            {"event_type": "idp.other"},
            {"t_evt_ns": 1_707_004_800_000_000_001},
            {"attrs": (("actor", "u-2"), ("token", "t-9"))},
            {"source_id": _source("iam_audit")},
        ):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(base, self._event(**overrides).identity_bytes())

    def test_unsorted_attrs_are_refused(self) -> None:
        with self.assertRaises(errors.SpectraError):
            self._event(attrs=(("token", "t-9"), ("actor", "u-1")))

    def test_non_string_attribute_values_are_refused(self) -> None:
        """Attribute values are always strings; a bare int is the shortest path to a float."""
        template = self._event()
        with self.assertRaises(errors.SchemaError):
            model.CanonicalEvent(
                event_id=template.event_id,
                record_id=template.record_id,
                source_id=template.source_id,
                seq=template.seq,
                event_type=template.event_type,
                t_evt_ns=template.t_evt_ns,
                t_ing_ns=template.t_ing_ns,
                attrs=(("seq", 3),),  # type: ignore[arg-type]
            )

    def test_link_members_are_present_or_absent_together(self) -> None:
        event = self._event()
        with self.assertRaises(errors.SchemaError):
            model.CanonicalEvent(
                event_id=event.event_id,
                record_id=event.record_id,
                source_id=event.source_id,
                seq=event.seq,
                event_type=event.event_type,
                t_evt_ns=event.t_evt_ns,
                t_ing_ns=event.t_ing_ns,
                attrs=event.attrs,
                chain_hash=canon.hash_ref("ev", b"x"),
            )

    def test_bundle_sort_key_is_the_declared_file_order(self) -> None:
        early = self._event(seq=1, t_evt_ns=100)
        late = self._event(seq=0, t_evt_ns=200)
        self.assertLess(early.sort_key(), late.sort_key())

    def test_records_are_frozen(self) -> None:
        record = model.Record.mint(_source("idp_auth"), b"x")
        with self.assertRaises(Exception):
            record.source_id = _source("other")  # type: ignore[misc]


class TestEntityAndSource(unittest.TestCase):
    def test_entity_id_is_stable_under_a_different_record_set(self) -> None:
        a = model.Entity.mint("credential", "token-9", "r_exact_token", (ids.EventId.mint(b"1"),))
        b = model.Entity.mint("credential", "token-9", "r_exact_token", ())
        self.assertEqual(a.entity_id, b.entity_id)
        self.assertTrue(a.verify_id())

    def test_entity_kind_must_agree_with_its_id(self) -> None:
        entity = model.Entity.mint("host", "h-1", "r_exact_device")
        with self.assertRaises(errors.SchemaError):
            model.Entity(
                entity_id=entity.entity_id,
                kind="service",
                canonical_name="h-1",
                join_rule_id="r_exact_device",
            )

    def test_a_source_that_emits_nothing_is_still_declarable(self) -> None:
        source = model.Source(
            source_id=_source("edr_host"),
            integrity_class=model.IntegrityClass.NONE,
            source_rank=5,
            emits_event_types=(),
        )
        self.assertEqual(source.emits_event_types, ())
        self.assertIsInstance(source.canonical_bytes(), bytes)

    def test_unsorted_event_types_are_refused(self) -> None:
        with self.assertRaises(errors.CanonError):
            model.Source(
                source_id=_source("idp_auth"),
                integrity_class=model.IntegrityClass.CHAINED,
                source_rank=1,
                emits_event_types=("b", "a"),
            )


class TestFactAndRule(unittest.TestCase):
    def test_fact_key_depends_on_argument_order(self) -> None:
        a = _entity("user", "u-1")
        b = _entity("resource", "r-1")
        self.assertNotEqual(
            model.Fact.mint("accessed", (a, b), 3).fact_key,
            model.Fact.mint("accessed", (b, a), 3).fact_key,
        )

    def test_fact_key_verifies(self) -> None:
        fact = model.Fact.mint("privilege_escalated", (_entity("user", "u-1"),), 12)
        self.assertTrue(fact.verify_id())
        self.assertNotEqual(
            fact.fact_key,
            model.Fact.mint("privilege_escalated", (_entity("user", "u-1"),), 13).fact_key,
        )

    def _rule(self, **overrides: object) -> model.Rule:
        fields: dict[str, object] = {
            "rule_id": ids.RuleId.of("r0003"),
            "rule_version": "1.0.0",
            "dimension": ids.DimensionId.of("privilege"),
            "kind": model.RuleKind.DETECT,
            "head": "privilege.escalated(P, R, T)",
            "body": ("iam.role_assumed(P, R, T)",),
            "producing_sources": (_source("iam_audit"),),
            "silent_possible": True,
            "note": "free prose",
        }
        fields.update(overrides)
        return model.Rule(**fields)  # type: ignore[arg-type]

    def test_the_metadata_digest_ignores_the_note(self) -> None:
        self.assertEqual(
            self._rule(note="one wording").metadata_bytes(),
            self._rule(note="a completely different comment").metadata_bytes(),
        )

    def test_the_metadata_digest_covers_the_declared_members(self) -> None:
        base = self._rule().metadata_bytes()
        for overrides in (
            {"head": "privilege.escalated(P, R, T0)"},
            {"body": ("iam.other(P, R, T)",)},
            {"producing_sources": (_source("idp_auth"),)},
            {"silent_possible": False},
            {"attck": ("T1078",)},
            {"rule_id": ids.RuleId.of("r0004")},
        ):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(base, self._rule(**overrides).metadata_bytes())

    def test_a_body_longer_than_the_narrowing_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._rule(body=("a(X)", "b(X)", "c(X)", "d(X)", "e(X)"))

    def test_a_bad_version_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._rule(rule_version="1.0")


class TestRuleInstance(unittest.TestCase):
    def setUp(self) -> None:
        self.head = model.Fact.mint("privilege_escalated", (_entity("user", "u-1"),), 5).fact_key
        self.body = (model.Fact.mint("role_assumed", (_entity("user", "u-1"),), 4).fact_key,)
        self.evidence = (
            model.EvidenceRef("assume", ids.EventId.mint(b"e1"), _source("iam_audit"), 100),
        )
        self.licence = model.Licence.mint(
            _source("iam_audit"),
            model.Interval(90, 200),
            model.LicenceBasis.BLIND,
            "B_GAP_EXCEEDS_THRESHOLD",
        )

    def _observed(self, **overrides: object) -> model.RuleInstance:
        fields: dict[str, object] = {
            "rule_id": ids.RuleId.of("r0003"),
            "rule_version": "1.0.0",
            "head": self.head,
            "body": self.body,
            "blockers": (1 << 3,),
            "observed": model.Observation.OBSERVED,
            "tick": 5,
            "evidence": self.evidence,
        }
        fields.update(overrides)
        return model.RuleInstance.mint(**fields)  # type: ignore[arg-type]

    def test_an_observed_instance_verifies(self) -> None:
        instance = self._observed()
        self.assertTrue(instance.verify_id())
        self.assertEqual(instance.mask, 1 << 3)

    def test_an_observed_instance_may_not_carry_a_licence(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._observed(license_ids=(self.licence.license_id,))

    def test_a_licensed_instance_may_not_carry_evidence(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._observed(
                observed=model.Observation.LICENSED, license_ids=(self.licence.license_id,)
            )

    def test_a_licensed_instance_is_well_formed(self) -> None:
        instance = self._observed(
            observed=model.Observation.LICENSED,
            evidence=(),
            license_ids=(self.licence.license_id,),
            ghost=True,
        )
        self.assertTrue(instance.ghost)
        self.assertEqual(instance.evidence, ())
        self.assertTrue(instance.verify_id())

    def test_a_ghost_may_not_be_observed(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._observed(ghost=True)

    def test_a_conjunctive_blocker_is_refused_by_the_narrowing(self) -> None:
        with self.assertRaises(errors.SchemaError) as raised:
            self._observed(blockers=(0b101,))
        self.assertEqual(raised.exception.code, "E-VS-BLOCK-CONJ")

    def test_the_instance_id_excludes_the_blocker_masks(self) -> None:
        """A catalog edit that renumbers bits must not renumber instance ids."""
        self.assertEqual(
            self._observed(blockers=(1 << 3,)).instance_id,
            self._observed(blockers=(1 << 9,)).instance_id,
        )

    def test_the_instance_id_covers_the_declared_members(self) -> None:
        base = self._observed().instance_id
        other_evidence = (
            model.EvidenceRef("assume", ids.EventId.mint(b"e2"), _source("iam_audit"), 100),
        )
        self.assertNotEqual(base, self._observed(evidence=other_evidence).instance_id)
        self.assertNotEqual(base, self._observed(rule_id=ids.RuleId.of("r0004")).instance_id)


class TestLicenceAndWindow(unittest.TestCase):
    def test_a_blind_licence_carries_no_witness(self) -> None:
        licence = model.Licence.mint(
            _source("iam_audit"),
            model.Interval(0, 100),
            model.LicenceBasis.BLIND,
            "B_UNBRACKETED",
        )
        self.assertEqual(licence.witness, ())
        self.assertTrue(licence.verify_id())
        with self.assertRaises(errors.SchemaError):
            model.Licence(
                license_id=licence.license_id,
                source_id=licence.source_id,
                t0_ns=0,
                t1_ns=100,
                basis=model.LicenceBasis.BLIND,
                reason="B_UNBRACKETED",
                witness=(ids.EventId.mint(b"e"),),
            )

    def test_a_suppressed_licence_requires_its_witness(self) -> None:
        with self.assertRaises(errors.SchemaError):
            model.Licence.mint(
                _source("gw_access"),
                model.Interval(0, 10),
                model.LicenceBasis.SUPPRESSED,
                "S_SEQ_GAP_UNAUTHENTICATED",
            )

    def test_a_licence_id_ignores_its_witness(self) -> None:
        witness = tuple(sorted((ids.EventId.mint(b"a"), ids.EventId.mint(b"b"))))
        with_witness = model.Licence.mint(
            _source("gw_access"),
            model.Interval(0, 10),
            model.LicenceBasis.SUPPRESSED,
            "S_SEQ_GAP_UNAUTHENTICATED",
            witness,
        )
        self.assertEqual(
            with_witness.license_id,
            ids.LicenseId.mint(
                b"".join(
                    (
                        canon.ascii_text("SUPPRESSED"),
                        canon.utf8_text("S_SEQ_GAP_UNAUTHENTICATED"),
                        canon.ascii_text("src:gw_access"),
                        canon.i64(0),
                        canon.i64(10),
                    )
                )
            ),
        )

    def test_a_licence_without_a_reason_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            model.Licence.mint(
                _source("iam_audit"), model.Interval(0, 1), model.LicenceBasis.BLIND, ""
            )

    def test_a_live_window_is_not_a_blind_window(self) -> None:
        with self.assertRaises(errors.SchemaError):
            model.BlindWindow.mint(
                _source("iam_audit"),
                model.Interval(0, 10),
                model.LivenessVerdict.LIVE,
                "L_CALIBRATED_OK",
            )

    def test_a_blind_window_verifies_and_orders(self) -> None:
        window = model.BlindWindow.mint(
            _source("iam_audit"),
            model.Interval(0, 10),
            model.LivenessVerdict.BLIND,
            "B_PROFILE_INSUFFICIENT",
        )
        self.assertEqual(window.sort_key(), ("src:iam_audit", 0, 10))
        self.assertEqual(window.interval, model.Interval(0, 10))


class TestLiteralCorridorAndCut(unittest.TestCase):
    def _literal(self, control: str, level: int, bit: int, rank: int) -> model.ThresholdLiteral:
        return model.ThresholdLiteral(ids.ControlId.of(control), level, bit, rank)

    def test_literal_order_is_control_bytes_then_level(self) -> None:
        literals = [
            self._literal("token_expiry", 1, 7, 8),
            self._literal("egress_seg", 2, 1, 1),
            self._literal("egress_seg", 1, 0, 0),
        ]
        self.assertEqual(
            [str(x.literal_id) for x in sorted(literals, key=lambda x: x.order_key)],
            ["lit:egress_seg@1", "lit:egress_seg@2", "lit:token_expiry@1"],
        )

    def test_level_zero_asserts_nothing_and_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._literal("egress_seg", 0, 0, 0)

    def test_a_bit_outside_the_mask_width_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._literal("egress_seg", 1, 64, 0)

    def test_corridor_id_is_over_the_ranks_only(self) -> None:
        corridor = model.Corridor.mint((0, 2, 5), mask=0b100101)
        self.assertTrue(corridor.verify_id())
        relabelled = model.Corridor.mint((0, 2, 5), mask=0b111)
        self.assertEqual(corridor.corridor_id, relabelled.corridor_id)

    def test_corridor_ranks_must_be_ascending(self) -> None:
        with self.assertRaises(errors.CanonError):
            model.Corridor.mint((2, 0), mask=0b101)

    def test_cut_cardinality_counts_controls_not_literals(self) -> None:
        cut = model.Cut.mint(
            (
                self._literal("egress_seg", 1, 0, 0),
                self._literal("egress_seg", 2, 1, 1),
                self._literal("priv_approval", 1, 2, 2),
            ),
            model.Minimality.EXACT_PSI_RELATIVE,
        )
        self.assertEqual(len(cut.atoms), 3)
        self.assertEqual(cut.cardinality, 2)
        self.assertEqual(cut.mask, 0b111)

    def test_a_cut_must_be_upward_closed(self) -> None:
        with self.assertRaises(errors.SchemaError) as raised:
            model.Cut.mint(
                (self._literal("egress_seg", 2, 1, 1),), model.Minimality.SUBSET
            )
        self.assertEqual(raised.exception.code, "E-CUT-CLOSURE")

    def test_a_cut_must_be_ascending_by_rank(self) -> None:
        with self.assertRaises(errors.CanonError):
            model.Cut.mint(
                (
                    self._literal("egress_seg", 2, 1, 1),
                    self._literal("egress_seg", 1, 0, 0),
                ),
                model.Minimality.SUBSET,
            )

    def test_the_cut_id_ignores_the_minimality_claim(self) -> None:
        atoms = (self._literal("egress_seg", 1, 0, 0),)
        self.assertEqual(
            model.Cut.mint(atoms, model.Minimality.SUBSET).cut_id,
            model.Cut.mint(atoms, model.Minimality.EXACT_EXHAUSTIVE).cut_id,
        )

    def test_the_compare_key_orders_by_controls_then_ranks_then_levels(self) -> None:
        small = model.Cut.mint(
            (self._literal("egress_seg", 1, 0, 0),), model.Minimality.SUBSET
        )
        large = model.Cut.mint(
            (
                self._literal("egress_seg", 1, 0, 0),
                self._literal("priv_approval", 1, 2, 2),
            ),
            model.Minimality.SUBSET,
        )
        self.assertLess(small.compare_key(), large.compare_key())


class TestCertificate(unittest.TestCase):
    SCOPE = (
        ("attacker", "non-adaptive"),
        ("bundle", "b2b256:" + "11" * 32),
        ("controls", "b2b256:" + "22" * 32),
        ("er", "b2b256:" + "33" * 32),
        ("goal", "b2b256:" + "44" * 32),
        ("liveness", "b2b256:" + "55" * 32),
        ("rules", "b2b256:" + "66" * 32),
    )
    INPUTS = (("k", "16"), ("seed", "0x000000000000000d"))

    def _cert(self, **overrides: object) -> model.Certificate:
        fields: dict[str, object] = {
            "schema_v": "1.0",
            "min_checker": "1.0",
            "profile": "eclipse-cert",
            "scope": self.SCOPE,
            "inputs": self.INPUTS,
        }
        fields.update(overrides)
        return model.Certificate(**fields)  # type: ignore[arg-type]

    def test_the_algorithm_name_is_a_required_member(self) -> None:
        cert = self._cert()
        self.assertEqual(cert.hash_algorithm, canon.HASH_ALGORITHM)
        self.assertIn("blake3", cert.hash_substitution_note)
        self.assertTrue(cert.cert_hash.startswith("b2b256:"))

    def test_a_certificate_cannot_claim_another_algorithm(self) -> None:
        with self.assertRaises(errors.SchemaError) as raised:
            self._cert(hash_algorithm="blake3")
        self.assertEqual(raised.exception.code, "E-HASH-ALGO")

    def test_the_substitution_note_cannot_be_dropped(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._cert(hash_substitution_note="")

    def test_the_scope_is_exactly_seven_members(self) -> None:
        # The surplus member is inserted in sorted position, so the member check is what
        # rejects it rather than the ordering check firing first.
        surplus = tuple(sorted(self.SCOPE + (("extra", "x"),), key=lambda kv: kv[0]))
        for bad in (self.SCOPE[:-1], surplus):
            with self.subTest(n=len(bad)):
                with self.assertRaises(errors.SchemaError) as raised:
                    self._cert(scope=bad)
                self.assertEqual(raised.exception.code, "VRD-005")

    def test_the_attacker_value_is_pinned(self) -> None:
        bad = tuple(("attacker", "adaptive") if k == "attacker" else (k, v) for k, v in self.SCOPE)
        with self.assertRaises(errors.SchemaError) as raised:
            self._cert(scope=bad)
        self.assertEqual(raised.exception.code, "VRD-005")

    def test_the_hash_covers_every_member(self) -> None:
        base = self._cert().cert_hash
        self.assertNotEqual(base, self._cert(schema_v="1.1").cert_hash)
        self.assertNotEqual(base, self._cert(inputs=(("k", "17"),)).cert_hash)
        self.assertNotEqual(
            base, self._cert(body_sections=(("cut", b"\x00"),)).cert_hash
        )

    def test_body_sections_must_be_sorted(self) -> None:
        with self.assertRaises(errors.CanonError):
            self._cert(body_sections=(("verdict", b"a"), ("cut", b"b")))


class TestGroundTruth(unittest.TestCase):
    def _truth(self, **overrides: object) -> model.GroundTruth:
        fields: dict[str, object] = {
            "truth_id": model.GroundTruth.mint_truth_id(b"occurrence-1"),
            "sim_tick": 4,
            "kind": model.TruthKind.ATTACK_STEP,
            "origin": model.TruthOrigin.SCENARIO,
            "actor_ref": "u-1",
            "observable": True,
            "event_id": ids.EventId.mint(b"e1"),
            "producing_sources": (_source("iam_audit"),),
        }
        fields.update(overrides)
        return model.GroundTruth(**fields)  # type: ignore[arg-type]

    def test_a_truth_id_is_not_a_section_57_identifier(self) -> None:
        truth = self._truth()
        self.assertTrue(truth.truth_id.startswith("tr_"))
        with self.assertRaises(errors.IdentifierError):
            ids.parse_id(truth.truth_id)  # underscore, so it has no id prefix at all

    def test_an_unobserved_step_names_no_event_and_no_source(self) -> None:
        truth = self._truth(
            kind=model.TruthKind.ATTACK_UNOBSERVED,
            observable=False,
            event_id=None,
            producing_sources=(),
        )
        self.assertIsNone(truth.event_id)
        with self.assertRaises(errors.SchemaError):
            self._truth(kind=model.TruthKind.ATTACK_UNOBSERVED, producing_sources=())

    def test_an_observed_annotation_must_name_its_event(self) -> None:
        with self.assertRaises(errors.SchemaError):
            self._truth(event_id=None)

    def test_truth_encodes_canonically(self) -> None:
        self.assertEqual(self._truth().canonical_bytes(), self._truth().canonical_bytes())


# ---------------------------------------------------------------------------
# Errors and quarantine
# ---------------------------------------------------------------------------


class TestErrorTaxonomy(unittest.TestCase):
    def test_every_raised_code_is_declared(self) -> None:
        for error_type in (
            errors.CanonError,
            errors.IdentifierError,
            errors.IdentifierTypeError,
            errors.IdentifierWidthError,
            errors.SchemaError,
            errors.HashError,
            errors.VerdictError,
            errors.GuardError,
            errors.ProfileError,
            errors.LimitError,
            errors.BudgetError,
            errors.DeterminismError,
        ):
            with self.subTest(error_type=error_type.__name__):
                self.assertTrue(
                    errors.code_is_declared(error_type.CODE),
                    f"{error_type.__name__}.CODE {error_type.CODE} is not in the registry",
                )

    def test_the_registry_is_a_closed_set(self) -> None:
        self.assertFalse(errors.code_is_declared("E-MADE-UP"))
        with self.assertRaises(errors.SchemaError):
            errors.code_class("E-MADE-UP")
        self.assertIs(errors.code_class("VRD-001"), errors.ErrorClass.SOUNDNESS)
        self.assertIs(errors.code_class("E-CANON-FLOAT"), errors.ErrorClass.CANONICITY)

    def test_the_named_checker_codes_are_present(self) -> None:
        for code in (
            "E-CANON-FLOAT",
            "E-CANON-DUPKEY",
            "E-CANON-ORDER",
            "E-CANON-NULL",
            "E-CANON-WIDTH",
            "E-CANON-TRAILING",
            "E-SCHEMA-MISSING",
            "E-SCHEMA-UNKNOWN",
            "E-SCOPE-BIND",
            "E-HASH-CERT",
            "E-INV-AXIOM",
            "E-CLOSURE",
            "E-GOAL-MEMBER",
            "E-PSI-HIT",
            "E-LICENSE-UNIMPLIED",
            "E-LICENSE-WINDOW",
            "E-GHOST-COUNT",
            "E-WITNESS-CYCLE",
            "E-WITNESS-EVENT",
            "E-WITNESS-CUT",
            "E-MIN-UNEARNED",
            "E-MIN-SMALLER",
            "E-FLAG-DERIVED",
            "PROFILE_SELF_CALIBRATED",
            "VRD-001",
            "VRD-009",
            "VRD-014",
        ):
            with self.subTest(code=code):
                self.assertTrue(errors.code_is_declared(code))

    def test_an_error_carries_its_code_and_sorted_pairs(self) -> None:
        raised = errors.CanonError("a float appeared", code="E-CANON-FLOAT")
        self.assertEqual(raised.code, "E-CANON-FLOAT")
        self.assertIn("E-CANON-FLOAT", str(raised))
        keys = [k for k, _ in raised.as_pairs()]
        self.assertEqual(keys, sorted(keys))


class TestQuarantine(unittest.TestCase):
    def test_quarantine_is_data_not_an_exception(self) -> None:
        entry = errors.QuarantineRecord(
            reason=errors.QuarantineReason.LABEL_LEAK,
            source_id="src:iam_audit",
            record_id=str(ids.RecordId.mint(b"line")),
            detail="carried a truth key",
        )
        self.assertNotIsInstance(entry, Exception)
        self.assertEqual(str(entry.reason), "Q_LABEL_LEAK")

    def test_a_bad_reason_is_refused(self) -> None:
        with self.assertRaises(errors.SchemaError):
            errors.QuarantineRecord(reason="Q_LABEL_LEAK", source_id="src:x")  # type: ignore[arg-type]

    def test_quarantine_entries_sort_totally(self) -> None:
        entries = [
            errors.QuarantineRecord(errors.QuarantineReason.UNPARSEABLE, "src:b"),
            errors.QuarantineRecord(errors.QuarantineReason.LABEL_LEAK, "src:a"),
        ]
        self.assertEqual(
            [e.source_id for e in sorted(entries, key=lambda e: e.sort_key())],
            ["src:a", "src:b"],
        )

    def test_the_reason_set_covers_the_declared_drops(self) -> None:
        names = {str(r) for r in errors.QuarantineReason}
        self.assertIn("Q_LABEL_LEAK", names)
        self.assertIn("Q_FLOAT_PRESENT", names)
        self.assertIn("Q_LINK_UNVERIFIED", names)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    def test_encoding_is_stable_across_construction_order(self) -> None:
        forward = model.Entity.mint("user", "u-1", "r_exact_principal")
        backward = model.Entity.mint("user", "u-1", "r_exact_principal")
        self.assertEqual(forward.canonical_bytes(), backward.canonical_bytes())

    def test_set_valued_members_are_insertion_order_independent(self) -> None:
        a = ids.EventId.mint(b"a")
        b = ids.EventId.mint(b"b")
        first = model.Entity.mint("user", "u-1", "r_exact_principal", (a, b))
        second = model.Entity.mint("user", "u-1", "r_exact_principal", (b, a))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())

    def test_digests_do_not_depend_on_hash_randomisation(self) -> None:
        """Runs the encoders in a fresh interpreter with a different PYTHONHASHSEED."""
        import os
        import subprocess

        snippet = (
            "import sys, pathlib;"
            f"sys.path.insert(0, {str(_REPO_ROOT / 'python' / 'spectra_core' / 'src')!r});"
            "from spectra_core import canon, ids, model;"
            "e = model.Entity.mint('user', 'u-1', 'r_exact_principal',"
            "  (ids.EventId.mint(b'b'), ids.EventId.mint(b'a')));"
            "print(e.content_hash())"
        )
        outputs = set()
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            result = subprocess.run(
                [sys.executable, "-c", snippet],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            outputs.add(result.stdout.strip())
        self.assertEqual(len(outputs), 1, f"digest varied with PYTHONHASHSEED: {outputs}")

    def test_no_output_path_iterates_a_set_or_a_dict(self) -> None:
        """A source-level check that the ordering discipline is structural, not a habit."""
        import spectra_core

        package_dir = pathlib.Path(spectra_core.__file__).parent
        for path in sorted(package_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(".values()", text, f"{path.name} iterates dict values")
            self.assertNotIn("for _ in set(", text, f"{path.name} iterates a set")


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


class TestBootstrap(unittest.TestCase):
    def test_the_repo_root_is_found_by_markers(self) -> None:
        root = find_repo_root()
        self.assertEqual(root, _REPO_ROOT)
        for marker in ("pyproject.toml", "docs", "python"):
            self.assertTrue((root / marker).exists())

    def test_src_dirs_are_sorted_and_non_empty(self) -> None:
        dirs = workspace_src_dirs()
        self.assertTrue(dirs, "no python/*/src directories found")
        self.assertEqual(list(dirs), sorted(dirs, key=lambda s: s.encode("utf-8")))
        self.assertTrue(
            any(pathlib.Path(d).parent.name == "spectra_core" for d in dirs),
            f"spectra_core's src directory is missing from {dirs}",
        )

    def test_install_is_idempotent(self) -> None:
        install()
        before = list(sys.path)
        self.assertEqual(install(), ())
        self.assertEqual(sys.path, before)

    def test_install_makes_a_sibling_package_importable(self) -> None:
        install()
        import importlib

        module = importlib.import_module("spectra_ingest")
        self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main(verbosity=2)
