"""Unit tests for the checker: one positive control and an adversarial corpus.

Run from the repository root:

    python python/spectra_vs_verify/tests/test_verify.py

POSITIVE CONTROLS ARE MANDATORY. A corpus of rejections can be passed by a checker that
rejects everything, so the unmutated certificate must be accepted first and every mutation
below is measured against that baseline.

EACH ROW ASSERTS AN EXACT REASON CODE. A wrong code is as much a failure as a wrong
verdict: the code is what a consumer compares, and a checker that rejects for the wrong
reason has not located the defect.

MUTATION LIVENESS. Each mutation targets one obligation. If a future edit removes that
obligation, the matching row goes red rather than quietly passing, which is the only sense
in which a green gate here is evidence of anything.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Callable

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "tests"))

import cert_fixture  # noqa: E402

from spectra_core import canon  # noqa: E402
from spectra_vs_verify import INDEPENDENCE_STATEMENT, CheckerInputs, verify  # noqa: E402
from spectra_vs_verify import checker as checker_mod  # noqa: E402


def _dumps(value: object, *, sort_keys: bool = True) -> str:
    return json.dumps(
        value, sort_keys=sort_keys, separators=(",", ":"), ensure_ascii=False
    )


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.fixture = cert_fixture.build(self.root)
        self.paths = dict(self.fixture.paths)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, cert_path: pathlib.Path | None = None) -> Any:
        return verify(cert_path or self.fixture.cert_path, CheckerInputs(**self.paths))

    def _write(self, octets: bytes) -> pathlib.Path:
        path = self.root / "mutated.spcert"
        with open(path, "wb") as handle:
            handle.write(octets)
        return path

    def _mutate(
        self, mutate: Callable[[dict[str, Any]], None], *, rehash: bool = True
    ) -> pathlib.Path:
        """Apply one edit to the body, optionally re-sealing it, and write the result.

        Re-sealing by default: a mutation that left the digest stale would be caught by the
        first obligation and would tell us nothing about the obligation it was aimed at.
        """
        document = json.loads(self.fixture.octets.decode("utf-8"))
        mutate(document["body"])
        if rehash:
            document["cert_hash"] = canon.hash_ref(
                "cert", _dumps(document["body"]).encode("utf-8")
            )
        return self._write((_dumps(document) + "\n").encode("utf-8"))

    def _rewrite_side_file(self, key: str, value: object, input_name: str) -> None:
        """Replace a pinned side file and re-pin its digest, leaving the rest intact."""
        octets = (_dumps(value) + "\n").encode("utf-8")
        with open(self.paths[key], "wb") as handle:
            handle.write(octets)
        domain = {n: d for n, d, _o, _c in checker_mod.INPUT_COVERAGE}[input_name]
        self._new_hash = canon.hash_ref(domain, octets)

    def assertRejects(self, path: pathlib.Path, code: str) -> None:
        report = self._run(path)
        self.assertFalse(report.accepted, report.render())
        self.assertEqual(report.code, code, report.render())


class TestPositiveControl(_Base):
    def test_the_unmutated_certificate_is_accepted(self) -> None:
        report = self._run()
        self.assertTrue(report.accepted, report.render())
        self.assertEqual(report.code, "")
        self.assertEqual(len(report.results), len(checker_mod.OBLIGATIONS))
        self.assertTrue(all(r.ok for r in report.results))

    def test_the_report_states_what_its_independence_is_worth(self) -> None:
        report = self._run()
        self.assertEqual(report.independence, INDEPENDENCE_STATEMENT)
        self.assertIn("MODULE INDEPENDENCE ONLY", report.render())
        self.assertIn("not be described as independently verified", report.render())
        self.assertIn("independence", report.as_json())

    def test_an_accept_does_not_claim_the_bundle_is_truthful(self) -> None:
        text = self._run().render()
        self.assertIn("says nothing about whether the bundle is truthful", text)
        for banned in ("independently verified.", "proved", "guaranteed"):
            self.assertNotIn(f" {banned}", text.replace("not be described as independently verified", ""))

    def test_the_checker_imports_nothing_from_the_emitter_package(self) -> None:
        """The gate the specification names: walk the AST of every checker module."""
        import ast

        package = _REPO_ROOT / "python" / "spectra_vs_verify" / "src" / "spectra_vs_verify"
        modules = sorted(package.glob("*.py"))
        self.assertTrue(modules)
        for module in modules:
            tree = ast.parse(module.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotEqual(alias.name.split(".")[0], "spectra_vs", module)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotEqual(node.module.split(".")[0], "spectra_vs", module)

    def test_the_report_is_deterministic(self) -> None:
        first = _dumps(self._run().as_json())
        second = _dumps(self._run().as_json())
        self.assertEqual(first, second)

    def test_the_cli_accepts_and_exits_zero(self) -> None:
        env_path = [
            str(_REPO_ROOT / "python" / "spectra_core" / "src"),
            str(_REPO_ROOT / "python" / "spectra_vs_verify" / "src"),
        ]
        argv = [
            sys.executable,
            "-m",
            "spectra_vs_verify",
            str(self.fixture.cert_path),
            "--json",
        ]
        for option, key in (
            ("--rules", "rules"),
            ("--rules-cae", "rules_cae"),
            ("--guards", "guards"),
            ("--controls-cae", "controls_cae"),
            ("--catalog-bits", "catalog_bits"),
            ("--bundle", "bundle"),
            ("--liveness", "liveness"),
            ("--profile", "profile"),
            ("--goal-cae", "goal_cae"),
            ("--er", "er"),
            ("--run-manifest", "run_manifest"),
        ):
            argv += [option, str(self.paths[key])]
        # The child runs with a minimal, explicit environment so the test proves the
        # checker is importable from exactly these two source roots and nothing else.
        #
        # os.pathsep, not ";". The separator was hardcoded to the Windows one, so on
        # Linux the child saw a single nonexistent directory named "<a>;<b>" and could
        # not import the package. The test passed on the Windows machine it was written
        # on and failed on the first clean Linux runner that executed it - which is the
        # failure CI exists to catch.
        child_env = {
            "PYTHONPATH": os.pathsep.join(env_path),
            "PYTHONHASHSEED": "0",
            "PATH": "",
        }
        if os.name == "nt":
            # Windows needs SYSTEMROOT to initialise its crypto and socket libraries even
            # in a child that uses neither directly; it is meaningless elsewhere.
            child_env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "C:\\Windows")
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            env=child_env,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["accept"])


class TestAdversarialCorpus(_Base):
    def test_tampered_cut(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["cut"] = [a for a in body["cut"] if a["control_id"] != "ctl:priv_approval"]

        self.assertRejects(self._mutate(mutate), "E-CLOSURE")

    def test_shrunk_invariant(self) -> None:
        self.assertRejects(
            self._mutate(lambda body: body["invariant"].__setitem__("u", [])), "E-INV-AXIOM"
        )

    def test_goal_in_u(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["invariant"]["u"] = sorted(
                [*body["invariant"]["u"], body["goals"][0]["goal_key"]]
            )

        self.assertRejects(self._mutate(mutate), "E-GOAL-MEMBER")

    def test_ghost_counted(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["observed_event_count"] = body["observed_event_count"] + body["ghost_count"]

        self.assertRejects(self._mutate(mutate), "E-GHOST-COUNT")

    def test_unknown_field(self) -> None:
        self.assertRejects(
            self._mutate(lambda body: body.__setitem__("extra_member", 1)),
            "E-SCHEMA-UNKNOWN",
        )

    def test_scope_mismatch(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["scope"]["bundle"] = canon.hash_ref("bundle", b"a different bundle")

        self.assertRejects(self._mutate(mutate), "E-SCOPE-BIND")

    def test_scope_stripped(self) -> None:
        self.assertRejects(
            self._mutate(lambda body: body["scope"].pop("goal")), "VRD-005"
        )

    def test_attacker_is_not_adaptive(self) -> None:
        self.assertRejects(
            self._mutate(lambda body: body["scope"].__setitem__("attacker", "adaptive")),
            "VRD-005",
        )

    def test_flagged_robust(self) -> None:
        self.assertRejects(
            self._mutate(
                lambda body: body["verdict"].__setitem__("flags", ["grounding_capped"])
            ),
            "VRD-001",
        )

    def test_exact_unearned(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["verdict"]["safety"] = "OPTIMISTIC_ONLY"
            body["verdict"]["flags"] = ["corridor_cap"]

        self.assertRejects(self._mutate(mutate), "VRD-004")

    def test_premium_under_cap(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["verdict"]["safety"] = "OPTIMISTIC_ONLY"
            body["verdict"]["flags"] = ["corridor_cap"]
            body["verdict"]["minimality"] = "SUBSET"

        self.assertRejects(self._mutate(mutate), "E-FLAG-DERIVED")

    def test_witness_class_on_a_safe_verdict(self) -> None:
        self.assertRejects(
            self._mutate(
                lambda body: body["verdict"].__setitem__("witness_class", "OBSERVED")
            ),
            "VRD-006",
        )

    def test_derived_suppressed_stripped(self) -> None:
        self.assertRejects(
            self._mutate(
                lambda body: body["verdict"].__setitem__(
                    "derived_suppressed", ["redundancy_index"]
                )
            ),
            "VRD-014",
        )

    def test_witness_phantom_event(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["witnesses"][0]["tree"]["evidence"] = ["ev:" + "ab" * 16]

        self.assertRejects(self._mutate(mutate), "E-WITNESS-EVENT")

    def test_witness_cyclic(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            tree = body["witnesses"][0]["tree"]
            tree["children"] = [
                {
                    "children": [],
                    "evidence": list(tree["evidence"]),
                    "head": tree["head"],
                    "instance_id": tree["instance_id"],
                    "kind": tree["kind"],
                }
            ]

        self.assertRejects(self._mutate(mutate), "E-WITNESS-CYCLE")

    def test_witness_wrong_cut(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["witnesses"][1]["removed_control"] = "ctl:zz_not_raised"

        self.assertRejects(self._mutate(mutate), "E-WITNESS-CUT")

    def test_unlicensed_silent(self) -> None:
        self.assertRejects(
            self._mutate(lambda body: body["silent"][0].__setitem__("license_ids", [])),
            "E-LICENSE-UNIMPLIED",
        )

    def test_psi_corridor_unhit(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            ranks = [1]
            corridor = {
                "atom_ranks": ranks,
                "corridor_id": "cor:"
                + canon.digest_hex("cor", canon.leb128_seq(ranks), 32),
                "mask": canon.mask_hex(1 << 1),
            }
            body["psi"]["corridors"] = sorted(
                [*body["psi"]["corridors"], corridor], key=lambda c: c["corridor_id"]
            )

        self.assertRejects(self._mutate(mutate), "E-PSI-HIT")

    def test_psi_unsorted(self) -> None:
        self.assertRejects(
            self._mutate(
                lambda body: body["psi"].__setitem__(
                    "corridors", list(reversed(body["psi"]["corridors"]))
                )
            ),
            "E-CANON-ORDER",
        )

    def test_truncated_psi_permits_a_smaller_cut(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["psi"]["corridors"] = [
                c for c in body["psi"]["corridors"] if c["atom_ranks"] != [2]
            ]

        self.assertRejects(self._mutate(mutate), "E-MIN-SMALLER")

    def test_mask_as_number(self) -> None:
        def mutate(body: dict[str, Any]) -> None:
            body["psi"]["corridors"][0]["mask"] = 1

        self.assertRejects(self._mutate(mutate), "E-CANON-WIDTH")

    def test_instances_edited_after_the_fact(self) -> None:
        """instances_hash binds the blocker masks, so the edit fails before the replay.

        The slice narrowing to single-literal blockers is enforced by the record type at
        construction, so a conjunctive term never reaches the wire to be caught later.
        """

        def mutate(body: dict[str, Any]) -> None:
            body["instances"][0]["blockers"] = [canon.mask_hex(0b101)]

        self.assertRejects(self._mutate(mutate), "E-HASH-CERT")

    def test_hash_mismatch_cert(self) -> None:
        document = json.loads(self.fixture.octets.decode("utf-8"))
        document["cert_hash"] = canon.hash_ref("cert", b"not the body")
        path = self._write((_dumps(document) + "\n").encode("utf-8"))
        self.assertRejects(path, "E-HASH-CERT")

    def test_hash_mismatch_rules(self) -> None:
        with open(self.paths["rules_cae"], "wb") as handle:
            handle.write(b"CAE1 a different rule encoding")
        self.assertRejects(self.fixture.cert_path, "E-INPUT-RULES")

    def test_bundle_edited_after_the_fact(self) -> None:
        with open(self.paths["bundle"], "ab") as handle:
            handle.write(b'{"event_id":"ev:' + b"00" * 16 + b'"}\n')
        self.assertRejects(self.fixture.cert_path, "E-INPUT-BUNDLE")

    def test_rules_text_drift_is_a_note_and_not_a_rejection(self) -> None:
        """A comment reflow must not invalidate an archived certificate."""
        with open(self.paths["rules"], "ab") as handle:
            handle.write(b"\n# a comment added after the certificate was archived\n")
        report = self._run()
        self.assertTrue(report.accepted, report.render())
        self.assertTrue(any("rules_text_hash" in note for note in report.notes))

    def test_profile_self_calibrated(self) -> None:
        profile = dict(cert_fixture.PROFILE)
        profile["reference_bundle_hash"] = self.fixture.body["inputs"]["bundle_hash"]
        self._rewrite_side_file("profile", profile, "profile_hash")
        new_hash = self._new_hash
        self.assertRejects(
            self._mutate(
                lambda body: body["inputs"].__setitem__("profile_hash", new_hash)
            ),
            "PROFILE_SELF_CALIBRATED",
        )

    def test_profile_seed_overlap(self) -> None:
        profile = dict(cert_fixture.PROFILE)
        profile["calibration_seed_band"] = [0, 1000000]
        self._rewrite_side_file("profile", profile, "profile_hash")
        new_hash = self._new_hash
        self.assertRejects(
            self._mutate(
                lambda body: body["inputs"].__setitem__("profile_hash", new_hash)
            ),
            "PROFILE_SEED_OVERLAP",
        )

    def test_license_window_wider_than_the_pinned_liveness_document(self) -> None:
        liveness = json.loads(_dumps(cert_fixture.LIVENESS))
        liveness["sources"][0]["intervals"][0]["t1_ns"] = str(
            cert_fixture.T0_NS + 600 * 1_000_000_000
        )
        self._rewrite_side_file("liveness", liveness, "liveness_hash")
        new_hash = self._new_hash

        def mutate(body: dict[str, Any]) -> None:
            body["inputs"]["liveness_hash"] = new_hash
            body["scope"]["liveness"] = new_hash

        self.assertRejects(self._mutate(mutate), "E-LICENSE-WINDOW")

    def test_a_missing_input_file_is_a_usage_error_not_a_pass(self) -> None:
        del self.paths["bundle"]
        report = self._run()
        self.assertEqual(report.exit_code, checker_mod.USAGE)
        self.assertFalse(report.accepted)


class TestEncodingLaw(_Base):
    def _raw(self, old: bytes, new: bytes) -> pathlib.Path:
        self.assertIn(old, self.fixture.octets)
        return self._write(self.fixture.octets.replace(old, new, 1))

    def test_float_smuggled(self) -> None:
        self.assertRejects(
            self._raw(b'"ghost_count":1', b'"ghost_count":1.0'), "E-CANON-FLOAT"
        )

    def test_duplicate_keys(self) -> None:
        self.assertRejects(
            self._raw(b'"ghost_count":1', b'"ghost_count":1,"ghost_count":1'),
            "E-CANON-DUPKEY",
        )

    def test_null_value(self) -> None:
        self.assertRejects(
            self._raw(b'"ghost_count":1', b'"ghost_count":null'), "E-CANON-NULL"
        )

    def test_trailing_bytes(self) -> None:
        self.assertRejects(self._write(self.fixture.octets + b"x"), "E-CANON-TRAILING")

    def test_a_compression_magic_is_never_decompressed(self) -> None:
        self.assertRejects(
            self._write(b"\x1f\x8b" + self.fixture.octets), "E-LIMIT-COMPRESSED"
        )

    def test_a_wrong_shaped_file_is_rejected_before_parsing(self) -> None:
        self.assertRejects(self._write(b"[" + self.fixture.octets), "E-SCHEMA-MISSING")

    def test_keys_unsorted(self) -> None:
        document = json.loads(self.fixture.octets.decode("utf-8"))
        document["body"] = dict(reversed(list(document["body"].items())))
        path = self._write((_dumps(document, sort_keys=False) + "\n").encode("utf-8"))
        self.assertRejects(path, "E-CANON-ORDER")

    def test_a_carriage_return_is_rejected(self) -> None:
        self.assertRejects(
            self._write(self.fixture.octets.replace(b"\n", b"\r\n")), "E-CANON-FORM"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
