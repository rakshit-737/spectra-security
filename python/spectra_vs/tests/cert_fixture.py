"""One small, complete, internally consistent certificate, built from the foundation types.

Named for the stage it serves rather than `fixture`, because several stages of the slice
keep their own fixture module in this directory and a shared name would collide.

Why a builder rather than a frozen file: the certificate's identifiers are content hashes,
so a committed file would have to be regenerated whenever an encoder changed, and the
regeneration would be exactly the code below. Building it lets the emitter and the checker
agree about a run neither of them hard-codes.

THE RUN, stated once so the assertions are readable. Two controls at two levels each, four
atoms. One axiom fact A. Three instances:

  I1  A -> G   OBSERVED, cites record e1, blocked by egress_seg at level 1
  I2  A -> H   LICENSED under one BLIND licence, GHOST-headed, blocked by priv_approval
  I3  H -> G   OBSERVED, cites record e2, blocked by priv_approval at level 1

Under the cut {egress_seg>=1, priv_approval>=1} every instance is blocked, U is {A} and the
goal is severed. Two corridors, one per route, each satisfied by exactly one of the two
raised controls, so neither control alone satisfies both and nothing smaller than two
controls satisfies the enumerated corridor set.

I2 is the point of the slice in miniature: it rests on a licence, not on a record. It
contributes nothing to observed_event_count and one to ghost_count, and the witness tree
that re-derives the goal when priv_approval is dropped runs through a GHOST node that cites
no event and is never called one.

Nothing here reads a wall clock, an environment variable or a random source, and no ground
truth is constructed or read.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
from spectra_core.bootstrap import install  # noqa: E402

install(_REPO_ROOT)

from spectra_core import canon  # noqa: E402
from spectra_core.ids import ControlId, EventId, FactHash, RuleId, SourceId  # noqa: E402
from spectra_core.model import (  # noqa: E402
    Corridor,
    Cut,
    EvidenceRef,
    Interval,
    Licence,
    LicenceBasis,
    Minimality,
    Observation,
    ProgramKind,
    RuleInstance,
    ThresholdLiteral,
)
from spectra_vs import cert, scf  # noqa: E402

EGRESS = ControlId.of("egress_seg")
PRIV = ControlId.of("priv_approval")
IAM = SourceId.of("iam_audit")
GW = SourceId.of("gw_access")

T0_NS = 1707004800000000000
T1_NS = T0_NS + 2400 * 1_000_000_000
SEED = 42
HORIZON_K = 3600

ATOMS: tuple[ThresholdLiteral, ...] = (
    ThresholdLiteral(control_id=EGRESS, level=1, bit=0, rank=0),
    ThresholdLiteral(control_id=EGRESS, level=2, bit=1, rank=1),
    ThresholdLiteral(control_id=PRIV, level=1, bit=2, rank=2),
    ThresholdLiteral(control_id=PRIV, level=2, bit=3, rank=3),
)

FACT_A = FactHash.mint(b"vs-01/axiom/token_presented")
FACT_G = FactHash.mint(b"vs-01/goal/resource_exfiltrated")
FACT_H = FactHash.mint(b"vs-01/ghost/credential_held")


def _bundle_record(
    source_id: SourceId, seq: int, event_type: str, t_evt_ns: int
) -> dict[str, Any]:
    """One bundle line in the shape ingest produces, with its content-addressed event id."""
    attrs = {"actor": "p_alice", "zone": "prod"}
    payload = b"".join(
        (
            canon.pairs(tuple(attrs.items())),
            canon.utf8_text(event_type),
            canon.u32(seq),
            canon.ascii_text(str(source_id)),
            canon.i64(t_evt_ns),
        )
    )
    return {
        "attrs": attrs,
        "event_id": str(EventId.mint(payload)),
        "event_type": event_type,
        "seq": seq,
        "source_id": str(source_id),
        "t_evt_ns": str(t_evt_ns),
        "t_ing_ns": str(t_evt_ns + 1000),
    }


RECORD_1 = _bundle_record(GW, 0, "gw.call", T0_NS + 60 * 1_000_000_000)
RECORD_2 = _bundle_record(GW, 1, "res.read", T0_NS + 120 * 1_000_000_000)
EVENT_1 = EventId(RECORD_1["event_id"])
EVENT_2 = EventId(RECORD_2["event_id"])

LICENCE = Licence.mint(
    source_id=IAM,
    interval=Interval(T0_NS, T1_NS),
    basis=LicenceBasis.BLIND,
    reason="B_GAP_EXCEEDS_THRESHOLD",
)

INSTANCE_1 = RuleInstance.mint(
    rule_id=RuleId.of("r0001"),
    rule_version="1.0.0",
    head=FACT_G,
    body=(FACT_A,),
    blockers=(1 << 0,),
    observed=Observation.OBSERVED,
    tick=1,
    evidence=(
        EvidenceRef(
            binding="call",
            event_id=EVENT_1,
            source_id=GW,
            t_evt_ns=T0_NS + 60 * 1_000_000_000,
        ),
    ),
)

INSTANCE_2 = RuleInstance.mint(
    rule_id=RuleId.of("r0002"),
    rule_version="1.0.0",
    head=FACT_H,
    body=(FACT_A,),
    blockers=(1 << 2,),
    observed=Observation.LICENSED,
    tick=1,
    license_ids=(LICENCE.license_id,),
    ghost=True,
)

INSTANCE_3 = RuleInstance.mint(
    rule_id=RuleId.of("r0003"),
    rule_version="1.0.0",
    head=FACT_G,
    body=(FACT_H,),
    blockers=(1 << 2,),
    observed=Observation.OBSERVED,
    tick=2,
    evidence=(
        EvidenceRef(
            binding="read",
            event_id=EVENT_2,
            source_id=GW,
            t_evt_ns=T0_NS + 120 * 1_000_000_000,
        ),
    ),
)

INSTANCES: tuple[RuleInstance, ...] = tuple(
    sorted(
        (INSTANCE_1, INSTANCE_2, INSTANCE_3),
        key=lambda i: canon.byte_order_key(str(i.instance_id)),
    )
)

CORRIDOR_A = Corridor.mint(atom_ranks=(0,), mask=1 << 0)
CORRIDOR_B = Corridor.mint(atom_ranks=(2,), mask=1 << 2)
CORRIDORS: tuple[Corridor, ...] = tuple(
    sorted((CORRIDOR_A, CORRIDOR_B), key=lambda c: canon.byte_order_key(str(c.corridor_id)))
)

CUT = Cut.mint(atoms=(ATOMS[0], ATOMS[2]), minimality=Minimality.EXACT_PSI_RELATIVE)


# ---------------------------------------------------------------------------
# Side files
# ---------------------------------------------------------------------------

CATALOG_BITS_LOCK = """# Append-only registry of (control_id, level) -> bit.
[[bit]]
pos = 0
control_id = "egress_seg"
level = 1
state = "live"

[[bit]]
pos = 1
control_id = "egress_seg"
level = 2
state = "live"

[[bit]]
pos = 2
control_id = "priv_approval"
level = 1
state = "live"

[[bit]]
pos = 3
control_id = "priv_approval"
level = 2
state = "live"
"""

RULES_TOML = """# Authored rule table. Comments here never reach rules_hash.
[[rule]]
id = "r0001"
version = "1.0.0"
dimension = "egress"
kind = "detect"
head = "resource.exfiltrated(P, R, T)"
body = ["gw.call(P, R, T)"]
producing_sources = ["gw_access"]
silent_possible = false

[[rule]]
id = "r0002"
version = "1.0.0"
dimension = "privilege"
kind = "obligation"
head = "credential.held(C, P, T)"
body = ["token.presented(C, P, T)"]
producing_sources = ["iam_audit"]
silent_possible = true

[[rule]]
id = "r0003"
version = "1.0.0"
dimension = "egress"
kind = "detect"
head = "resource.exfiltrated(P, R, T)"
body = ["credential.held(C, P, T)"]
producing_sources = ["gw_access"]
silent_possible = false
"""

GUARDS_CAE = b"CAE1\x03\x00\x00\x00fixture-guard-encoding"
RULES_CAE = b"CAE1\x03\x00\x00\x00fixture-rule-encoding-with-metadata"
CONTROLS_CAE = b"CAE1\x02\x00\x00\x00fixture-control-catalog-with-levels"
GOAL_CAE = b"CAE1\x01\x00\x00\x00fixture-goal-library-entry"

LIVENESS: dict[str, Any] = {
    "flags": {
        "blind_by_default": False,
        "liveness_unauthenticated": False,
        "liveness_uncalibrated": False,
        "mcs_greedy": False,
        "profile_regime_collapsed": False,
        "verdict_tamper_sensitive": False,
    },
    "m_min": 3,
    "mode_global": "F0_CALIBRATED",
    "n_min": 100,
    "profile_id": "b2b256:" + "11" * 32,
    "quantile": "95/100",
    "schema": "spectra.liveness/2",
    "slack": "3/2",
    "sources": [
        {
            "blind_volume_ns_by_reason": {"b_gap_exceeds_threshold": str(T1_NS - T0_NS)},
            "integrity_class": "chained",
            "intervals": [
                {
                    "reason": "B_GAP_EXCEEDS_THRESHOLD",
                    "t0_ns": str(T0_NS),
                    "t1_ns": str(T1_NS),
                    "verdict": "BLIND",
                }
            ],
            "mode": "F0_CALIBRATED",
            "source_id": "iam_audit",
            "suppressed_volume_ns": "0",
            "tamper_suspected": False,
        },
        {
            "blind_volume_ns_by_reason": {},
            "integrity_class": "sequenced",
            "intervals": [
                {
                    "reason": "L_CALIBRATED_OK",
                    "t0_ns": str(T0_NS),
                    "t1_ns": str(T1_NS),
                    "verdict": "LIVE",
                }
            ],
            "mode": "F0_CALIBRATED",
            "source_id": "gw_access",
            "suppressed_volume_ns": "0",
            "tamper_suspected": False,
        },
    ],
}

IDENTITY_SPEC_HASH = canon.hash_ref("degspec", b"identity-degradation-spec")
GENERATOR_CONFIG_HASH = canon.hash_ref("gencfg", b"vs-01-token-pivot/generator")
EXCLUDED_INTERVALS_HASH = canon.hash_ref("excl", b"[]")
SCENARIO_FAMILY = "vs-01-token-pivot"

RUN_MANIFEST = {
    "excluded_intervals_hash": EXCLUDED_INTERVALS_HASH,
    "generator_config_hash": GENERATOR_CONFIG_HASH,
    "identity_spec_hash": IDENTITY_SPEC_HASH,
    "scenario_family": SCENARIO_FAMILY,
}

ER = {"ambiguous": [], "bindings": [], "entities": [], "schema": "spectra.vs.er/1"}

PROFILE = {
    "calibration_seed_band": [1000000, 1000063],
    "degradation_spec_hash": IDENTITY_SPEC_HASH,
    "excluded_intervals_hash": EXCLUDED_INTERVALS_HASH,
    "generator_config_hash": GENERATOR_CONFIG_HASH,
    "profile_id": "b2b256:" + "11" * 32,
    "reference_bundle_hash": canon.hash_ref("bundle", b"a different, clean bundle"),
    "reference_run_manifest_hash": canon.hash_ref("manifest", b"the calibration run"),
    "regime_collapsed": False,
    "scenario_family": SCENARIO_FAMILY,
    "schema": "spectra.source_profile/1",
    "sources": [],
}


@dataclass(frozen=True, slots=True)
class Fixture:
    """Every path the checker needs, plus the emitted certificate octets."""

    root: Path
    cert_path: Path
    body: dict[str, Any]
    octets: bytes
    paths: dict[str, Path]


def witness_entries() -> tuple[cert.WitnessEntry, ...]:
    """One tree per raised control, each re-deriving the goal without that control.

    The priv_approval tree runs through a GHOST node. It cites no event, because nothing
    was seen; it cites a licence, because for that window nothing could have been.
    """
    tree_egress = cert.WitnessNode(
        instance_id=INSTANCE_1.instance_id,
        head=FACT_G,
        kind=cert.WitnessKind.OBSERVED,
        evidence=(EVENT_1,),
    )
    tree_priv = cert.WitnessNode(
        instance_id=INSTANCE_3.instance_id,
        head=FACT_G,
        kind=cert.WitnessKind.OBSERVED,
        evidence=(EVENT_2,),
        children=(
            cert.WitnessNode(
                instance_id=INSTANCE_2.instance_id,
                head=FACT_H,
                kind=cert.WitnessKind.GHOST,
            ),
        ),
    )
    return tuple(
        sorted(
            (
                cert.WitnessEntry(removed_control=EGRESS, tree=tree_egress),
                cert.WitnessEntry(removed_control=PRIV, tree=tree_priv),
            ),
            key=lambda w: canon.byte_order_key(str(w.removed_control)),
        )
    )


def premium() -> cert.Premium:
    """priv_approval is in the cut because for forty minutes nobody could have seen."""
    return cert.Premium(
        nec_max=(EGRESS, PRIV),
        occ_min=(EGRESS,),
        blindness_premium=(PRIV,),
        per_control=(
            cert.PremiumEntry(
                control_id=PRIV,
                license_ids=(LICENCE.license_id,),
                calibration_deficiency=Fraction(0, 1),
            ),
        ),
    )


def budgets() -> cert.Budgets:
    return cert.Budgets(
        fixpoint_steps=7,
        bb_nodes=11,
        step_budget=2_000_000,
        budget_exhausted=False,
        exhaustive_ran=False,
        exhaustive_cuts_tested=0,
    )


def residual() -> cert.Residual:
    return cert.Residual(
        program=ProgramKind.P_MAX,
        goals_derivable=(),
        goals_severed=(FACT_G,),
        corridors_open=(),
        corridors_exhaustive=True,
    )


def silent() -> tuple[cert.SilentRef, ...]:
    return (
        cert.SilentRef(instance_id=INSTANCE_2.instance_id, license_ids=(LICENCE.license_id,)),
    )


def write_side_files(root: Path) -> tuple[dict[str, Path], cert.Inputs]:
    """Write every pinned artifact and return the paths beside the digests over them."""
    paths: dict[str, Path] = {}

    bundle_octets = scf.render_jsonl([RECORD_1, RECORD_2])
    scf.write_bytes(root / "bundle.jsonl", bundle_octets)
    paths["bundle"] = root / "bundle.jsonl"

    liveness_octets = scf.write_scf(root / "liveness.json", LIVENESS)
    paths["liveness"] = root / "liveness.json"

    er_octets = scf.write_scf(root / "er.json", ER)
    paths["er"] = root / "er.json"

    profile_octets = scf.write_scf(root / "profile.json", PROFILE)
    paths["profile"] = root / "profile.json"

    scf.write_scf(root / "manifest.json", RUN_MANIFEST)
    paths["run_manifest"] = root / "manifest.json"

    rules_octets = RULES_TOML.encode("utf-8")
    scf.write_bytes(root / "rules.toml", rules_octets)
    paths["rules"] = root / "rules.toml"

    lock_octets = CATALOG_BITS_LOCK.encode("utf-8")
    scf.write_bytes(root / "catalog-bits.lock", lock_octets)
    paths["catalog_bits"] = root / "catalog-bits.lock"

    for name, octets, key in (
        ("guards.cae", GUARDS_CAE, "guards"),
        ("rules.cae", RULES_CAE, "rules_cae"),
        ("controls.cae", CONTROLS_CAE, "controls_cae"),
        ("goal.cae", GOAL_CAE, "goal_cae"),
    ):
        scf.write_bytes(root / name, octets)
        paths[key] = root / name

    inputs = cert.Inputs(
        rules_hash=canon.hash_ref("rules", RULES_CAE),
        rules_text_hash=canon.hash_ref("rulestext", rules_octets),
        guard_ast_hash=canon.hash_ref("guardast", GUARDS_CAE),
        controls_hash=canon.hash_ref("controls", CONTROLS_CAE),
        catalog_bits_hash=canon.hash_ref("catbits", lock_octets),
        bundle_hash=canon.hash_ref("bundle", bundle_octets),
        liveness_hash=canon.hash_ref("liveness", liveness_octets),
        profile_hash=canon.hash_ref("profile", profile_octets),
        goal_hash=canon.hash_ref("goal", GOAL_CAE),
        er_hash=canon.hash_ref("er", er_octets),
        instances_hash=cert.instances_hash(INSTANCES),
        seed=SEED,
        k=HORIZON_K,
    )
    return paths, inputs


def scope_of(inputs: cert.Inputs) -> cert.Scope:
    return cert.Scope(
        rules=inputs.rules_hash,
        controls=inputs.controls_hash,
        liveness=inputs.liveness_hash,
        er=inputs.er_hash,
        goal=inputs.goal_hash,
        bundle=inputs.bundle_hash,
    )


def verdict() -> cert.Verdict:
    return cert.Verdict.build(
        cert.VerdictProposal(
            safety=cert.Safety.ROBUST,
            minimality=Minimality.EXACT_PSI_RELATIVE,
            flags=(),
            derived_suppressed=cert.DERIVED_SUPPRESSED_ALWAYS,
            realizability=cert.Realizability.CHECKED,
        ),
        no_tamper_token=cert.mint_no_tamper_token(
            tamper_suspected_sources=(), verdict_tamper_sensitive=False, sources=2
        ),
        pmax_fixpoint_terminated=True,
    )


def body_kwargs(inputs: cert.Inputs) -> dict[str, Any]:
    """The full argument set, so a test can replace exactly one member and isolate a check."""
    return {
        "scope": scope_of(inputs),
        "inputs": inputs,
        "verdict": verdict(),
        "atoms": ATOMS,
        "cut": CUT,
        "goals": (cert.GoalRef(goal_key=FACT_G, derivable=False),),
        "invariant": (FACT_A,),
        "instances": INSTANCES,
        "licenses": (LICENCE,),
        "silent": silent(),
        "witnesses": witness_entries(),
        "psi": cert.Psi(program=ProgramKind.P_MAX, complete=True, corridors=CORRIDORS),
        "premium": premium(),
        "premium_suppressed_reason": None,
        "cut_delta_canonical": (),
        "residual": residual(),
        "budgets": budgets(),
        "observed_event_count": 2,
        "ghost_count": 1,
        "psi_min_complete": True,
    }


def build(root: Path) -> Fixture:
    """Write every side file under `root`, emit the certificate, and return the paths."""
    paths, inputs = write_side_files(root)
    kwargs = body_kwargs(inputs)
    body = cert.build_body(**kwargs)
    artifact = cert.emit(body, kwargs["verdict"], kwargs["scope"])
    cert_path = root / "cert.spcert"
    cert.write_certificate(cert_path, artifact)
    return Fixture(
        root=root, cert_path=cert_path, body=body, octets=artifact.octets, paths=paths
    )
