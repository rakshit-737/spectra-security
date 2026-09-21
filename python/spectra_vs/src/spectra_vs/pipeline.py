"""S1..S11 wired into one runnable chain, plus the vocabulary bindings the seams need.

WHAT THIS IS. The orchestrator for the SPECTRA vertical slice, a PYTHON REFERENCE
IMPLEMENTATION. There is no Rust kernel, no Go checker, no C guard VM and no Docker cyber
range; none is built here and nothing in this module may be read as evidence that any of
them exists. Telemetry comes from a seeded synthetic generator and every artifact says so
through `bundle_provenance: "synthetic_generator_no_range"`.

NO RESULT PRODUCED BY THIS MODULE IS MEASURED. The scenario, the control catalog and the
two completeness cells are a design; every number that reaches a transcript is a design
parameter or a deterministic counter, never an observation about a system.

SHAPE. One function per stage boundary, each a pure function of its arguments, each
writing exactly one artifact under `runs/<run_id>/`. `run_cell` threads them and returns a
`CellResult`. No stage reads `truth.jsonl`; that file is written by S2 and then never
opened again by anything in this module, which is what "truth is for evaluation only"
means operationally.

DETERMINISM. No wall clock is read anywhere. `run_id` is content-addressed from the
scenario hash, the seed and the completeness rational, so the same inputs write to the
same directory and produce byte-identical artifacts. `t_ing_ns` is derived from the event
instant, not from a clock, so `bundle.jsonl` is a function of `raw.jsonl` alone.

-----------------------------------------------------------------------------
THE THREE SEAMS, STATED HERE BECAUSE THEY CROSS CONFIG FILES
-----------------------------------------------------------------------------
`config/vs/scenario.toml`, `config/vs/rules.toml` and `config/vs/goal.toml` were authored
in parallel against three different vocabularies. The pipeline carries the binding between
them rather than editing those files, because the committed test suite pins their contents
and a config edit would turn green tests red without making the underlying disagreement
any smaller. Each binding is explicit, is written into the unhashed run manifest, and is
reported by `demo.py` so that a reader sees it rather than inferring it.

  SEAM 1, event type to axiom predicate. The grounder seeds `E(entity_ids..., tick)` from a
  record of type `E`. The scenario declares `emits_event_types` in snake case
  (`iam_role_assumed`); the rule table names axiom predicates in dotted snake
  (`iam.role_assumed`). `EVENT_TYPE_PREDICATE` is the binding. An event type with no entry
  keeps its own name and simply seeds a predicate no rule consumes.

  SEAM 2, attribute to role. `ground.axiom_fact_for` orders a fact's argument vector by
  ROLE NAME ascending, and a rule's axiom pattern binds those arguments positionally. The
  scenario's records carry four or five attributes each, while the rule table's axiom
  patterns name two. The bindings written into `er.json` are every exact join the scenario
  tables admit; the argument vector handed to the grounder is PROJECTED onto exactly the
  roles the rule table's pattern for that predicate names. The projection is a narrowing of
  a hashed artifact, never an addition to it, and `AXIOM_ROLES` is derived mechanically
  from the compiled rule table rather than authored.

  SEAM 3, the goal. `config/vs/goal.toml` names `resource.bulk_read(res_customer_records)`.
  No rule in `config/vs/rules.toml` heads that predicate, and `res_customer_records` is not
  an entity the scenario declares. `GOAL_PREDICATE_BINDING` maps the authored predicate to
  the rule table's terminal head; authored arguments that resolve to a declared entity are
  used as a filter and ones that do not are reported as unresolved rather than invented.
  When the resulting goal library is empty the run says so and proves against a sentinel
  goal key that no instance heads, which is underivable under every cut. That is a real
  outcome, reported as one.

WHAT AN ACCEPT FROM S11 MEANS. The checker is a separate Python package that imports
nothing from this one. That is MODULE independence, not implementation independence: it
shares an author, a language and a reading of the specification with this emitter, so a
shared misreading is invisible to it. An ACCEPT says the certificate is internally
consistent with the hashed inputs. It says nothing about the bundle's truthfulness, the
correctness of entity resolution, the completeness of the control catalog, or whether
grounding found every instance. No certificate produced here is independently verified.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

from spectra_core import canon, errors, model
from spectra_core.ids import ControlId, EntityId, EventId, FactHash, SourceId
from spectra_vs import calibrate as calibrate_mod
from spectra_vs import cert as cert_mod
from spectra_vs import cut as cut_mod
from spectra_vs import degrade as degrade_mod
from spectra_vs import envelope as envelope_mod
from spectra_vs import gen as gen_mod
from spectra_vs import ground as ground_mod
from spectra_vs import ingest as ingest_mod
from spectra_vs import liveness as liveness_mod
from spectra_vs import premium as premium_mod
from spectra_vs import reach as reach_mod
from spectra_vs import resolve as resolve_mod
from spectra_vs import rules as rules_mod
from spectra_vs import scenario as scenario_mod
from spectra_vs import scf

__all__ = [
    "AXIOM_ROLES",
    "BUNDLE_PROVENANCE",
    "EVENT_TYPE_PREDICATE",
    "GOAL_PREDICATE_BINDING",
    "JOIN_RULES_NOTE",
    "CellResult",
    "Layout",
    "ProveResult",
    "StageArtifact",
    "join_rules_for",
    "run_cell",
    "run_id_for",
    "s0_bits_lock",
    "s1_rules",
    "s2_gen",
    "s3_degrade",
    "s4_ingest",
    "s5_resolve",
    "s6_calibrate",
    "s7_liveness",
    "s8_ground",
    "s9_envelope",
    "s10_prove",
    "s11_verify",
]

#: Carried at manifest level by every artifact this module writes. Never a per-record key,
#: which would violate label purity at ingest.
BUNDLE_PROVENANCE: Final[str] = "synthetic_generator_no_range"

#: SEAM 1. Declared event type -> the axiom predicate the rule table names.
#: An event type absent from this table seeds a predicate of its own name, which no rule
#: consumes; that is the honest outcome for background chatter.
EVENT_TYPE_PREDICATE: Final[dict[str, str]] = {
    "gw_health": "gw.health",
    "gw_request": "gw.request",
    "iam_approval_granted": "iam.approval_granted",
    "iam_list_roles": "iam.list_roles",
    "iam_role_assumed": "iam.role_assumed",
    "idp_login": "idp.login",
    "idp_refresh": "idp.refresh_exchange",
    "net_conn": "net.connection",
    "res_browse": "res.browse",
    "res_export": "res.export",
    "res_read": "res.read",
}

#: SEAM 3. Authored goal predicate -> the rule table head that can derive it.
GOAL_PREDICATE_BINDING: Final[dict[str, str]] = {
    "resource.bulk_read": "exfil.bulk_read",
}

#: SEAM 2, the half that is authored rather than derived: which scenario attribute supplies
#: which entity-resolution role, and what kind the resulting entity has.
#:
#: The closed five join rule ids name no `service` rule and no `role` rule. Two ids are
#: therefore reused for a second role each, which is admissible because a JoinRule's
#: identity is (id, role, attr_key) and two rules may target different roles from the same
#: table. The reuse is stated rather than hidden: `r_exact_resource` also carries the
#: service table, and `r_exact_session_by_token` carries the credential table under the
#: role `role`, because the scenario models an assumable admin role as a credential.
JOIN_RULES_NOTE: Final[str] = (
    "the closed five join-rule ids name no service rule and no role rule; "
    "r_exact_resource also carries the service table and r_exact_session_by_token "
    "carries the credential table under the role 'role'"
)

_JOIN_SPECS: Final[tuple[tuple[str, str, str, str], ...]] = (
    # (join_rule_id, role, attr_key, entity kind)
    ("r_exact_device", "device", "device", "host"),
    ("r_exact_principal", "principal", "principal", "user"),
    ("r_exact_resource", "resource", "resource", "resource"),
    ("r_exact_resource", "service", "service", "service"),
    ("r_exact_session_by_token", "role", "credential", "account"),
    ("r_exact_token", "credential", "credential", "credential"),
)

#: Filled by `axiom_roles_of`: axiom predicate -> the role names its pattern binds, in the
#: order the pattern writes them, which the rule loader has already checked is ascending.
AXIOM_ROLES = dict[str, tuple[str, ...]]

#: The analysis seed band. The calibration band is disjoint and lives in `calibrate`.
DEFAULT_ANALYSIS_SEED: Final[int] = 7
DEFAULT_DEGRADATION_SEED: Final[int] = 11
DEFAULT_CALIBRATION_SEED: Final[int] = 1000007


# ---------------------------------------------------------------------------
# Layout and run identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Layout:
    """Where every input and output lives. Absolute paths only, no environment reads."""

    repo_root: Path

    @property
    def config_dir(self) -> Path:
        return self.repo_root / "config" / "vs"

    @property
    def scenario_toml(self) -> Path:
        return self.config_dir / "scenario.toml"

    @property
    def rules_toml(self) -> Path:
        return self.config_dir / "rules.toml"

    @property
    def controls_toml(self) -> Path:
        return self.config_dir / "controls.toml"

    @property
    def goal_toml(self) -> Path:
        return self.config_dir / "goal.toml"

    @property
    def liveness_toml(self) -> Path:
        return self.config_dir / "liveness.toml"

    @property
    def bits_lock(self) -> Path:
        return self.config_dir / "catalog-bits.lock"

    @property
    def profiles_dir(self) -> Path:
        return self.repo_root / "profiles"

    @property
    def runs_dir(self) -> Path:
        return self.repo_root / "runs"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id


def run_id_for(
    scenario_hash: str,
    seed: int,
    completeness: degrade_mod.Completeness,
    blackout: degrade_mod.Blackout | None = None,
) -> str:
    """A content-addressed run id. No counter, no clock, no process id.

    The same scenario, seed and completeness always name the same directory, which is what
    makes a byte-for-byte replay a diff rather than a comparison of two paths.

    A blackout is mixed in ONLY when present. Without that, a blackout cell recorded at
    completeness 1/1 would name the same directory as the full-telemetry cell and overwrite
    it; and adding it unconditionally would rename every existing run.
    """
    parts = [
        canon.ascii_text(scenario_hash),
        canon.u64(seed),
        canon.u32(completeness.num),
        canon.u32(completeness.den),
    ]
    if blackout is not None:
        parts.append(canon.ascii_text("blackout"))
        parts.extend(canon.ascii_text(s) for s in blackout.sources)
        parts.append(canon.u64(blackout.t0_ns))
        parts.append(canon.u64(blackout.t1_ns))
    return "vs-" + canon.digest_hex("vsrun", b"".join(parts))[:16]


@dataclass(frozen=True, slots=True)
class StageArtifact:
    """One written artifact: what stage wrote it, where, and its digest."""

    stage: str
    name: str
    path: Path
    digest: str

    def as_row(self) -> dict[str, str]:
        return {
            "digest": self.digest,
            "name": self.name,
            "path": self.path.as_posix(),
            "stage": self.stage,
        }


# ---------------------------------------------------------------------------
# S0  bits-lock
# ---------------------------------------------------------------------------


def s0_bits_lock(layout: Layout) -> tuple[rules_mod.Catalog, rules_mod.BitTable, StageArtifact]:
    """Load the control catalog and the append-only bit lock, creating the lock once.

    Deriving bit positions is legitimate exactly once, when the lock does not yet exist.
    After that the lock is authoritative: re-deriving over an edited catalog would renumber
    pre-existing bits, and a renumber invalidates every archived certificate.
    """
    catalog = rules_mod.load_catalog(layout.controls_toml)
    if layout.bits_lock.exists():
        bits = rules_mod.load_bit_table(layout.bits_lock)
    else:
        bits = rules_mod.BitTable.derive(catalog)
        layout.bits_lock.parent.mkdir(parents=True, exist_ok=True)
        layout.bits_lock.write_bytes(bits.lock_text().encode("utf-8"))
    bits.check_covers(catalog)
    octets = layout.bits_lock.read_bytes()
    return (
        catalog,
        bits,
        StageArtifact(
            stage="S0",
            name="catalog-bits.lock",
            path=layout.bits_lock,
            digest=canon.hash_ref("catbits", octets),
        ),
    )


# ---------------------------------------------------------------------------
# S1  rules build
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RulesResult:
    """The compiled table plus the four canonical encodings the certificate pins."""

    table: rules_mod.RuleTable
    guards_cae: bytes
    rules_cae: bytes
    controls_cae: bytes
    goal_cae: bytes
    goal_spec: cut_mod.GoalSpec
    artifacts: tuple[StageArtifact, ...]


def s1_rules(
    layout: Layout,
    catalog: rules_mod.Catalog,
    bits: rules_mod.BitTable,
    run_dir: Path,
) -> RulesResult:
    """Compile the rule table and write the canonical encodings the checker re-hashes.

    Four separate artifacts because four separate digests cover four separate things, and a
    checker that took the emitter's word for what a hash covered could not disagree with it.
    `rules.cae` is the guard CAE plus the per-rule metadata record, which is what
    `rules_hash` is defined over; `guards.cae` is the guard CAE alone.
    """
    table = rules_mod.compile_rules(layout.rules_toml, catalog, bits)
    goal_spec = cut_mod.load_goal_spec(layout.goal_toml)

    guards_cae = table.cae_bytes()
    rules_cae = guards_cae + canon.ordered_seq(
        compiled.rule.metadata_bytes() for compiled in table.rules
    )
    controls_cae = catalog.canonical_bytes()
    goal_cae = b"".join(
        (
            b"CAE1",
            canon.ordered_seq(canon.utf8_text(a) for a in goal_spec.goal_args),
            canon.utf8_text(goal_spec.goal_predicate),
            canon.u32(goal_spec.horizon_k),
        )
    )

    run_dir.mkdir(parents=True, exist_ok=True)
    written: list[StageArtifact] = []
    for name, octets, domain in (
        ("guards.cae", guards_cae, "guardast"),
        ("rules.cae", rules_cae, "rules"),
        ("controls.cae", controls_cae, "controls"),
        ("goal.cae", goal_cae, "goal"),
    ):
        path = run_dir / name
        path.write_bytes(octets)
        written.append(
            StageArtifact(stage="S1", name=name, path=path, digest=canon.hash_ref(domain, octets))
        )

    return RulesResult(
        table=table,
        guards_cae=guards_cae,
        rules_cae=rules_cae,
        controls_cae=controls_cae,
        goal_cae=goal_cae,
        goal_spec=goal_spec,
        artifacts=tuple(written),
    )


def axiom_roles_of(table: rules_mod.RuleTable) -> dict[str, tuple[str, ...]]:
    """SEAM 2, derived rather than authored: axiom predicate -> the roles its pattern binds.

    An axiom predicate is a body predicate no rule in the table heads. Its pattern's entity
    variables ARE the entity-resolution role names, written in ascending byte order, which
    the rule loader has already checked. Reading them back off the compiled table is what
    keeps this projection a consequence of the rule file rather than a second copy of it.
    """
    heads = {compiled.head.predicate for compiled in table.rules}
    roles: dict[str, tuple[str, ...]] = {}
    for compiled in table.rules:
        patterns = list(compiled.body)
        temporal = compiled.temporal
        if temporal is not None and temporal.of_pattern is not None:
            patterns.append(temporal.of_pattern)
        for pattern in patterns:
            if pattern.predicate in heads:
                continue
            existing = roles.get(pattern.predicate)
            if existing is not None and existing != pattern.entity_vars:
                raise errors.SchemaError(
                    f"axiom_roles_of: {pattern.predicate} is bound to roles {existing} in one "
                    f"rule and {pattern.entity_vars} in another; an axiom predicate has one "
                    "argument vector or it has none"
                )
            roles[pattern.predicate] = pattern.entity_vars
    return roles


# ---------------------------------------------------------------------------
# S2  gen
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenStage:
    result: gen_mod.GenResult
    artifacts: tuple[StageArtifact, ...]


def s2_gen(spec: scenario_mod.ScenarioSpec, seed: int, run_dir: Path) -> GenStage:
    """Emit the raw stream and the ground-truth stream. Two files that never meet again.

    `truth.jsonl` is written here and read by NOTHING downstream. It exists so that an
    evaluation outside this pipeline has an oracle; no stage from S3 to S11 opens it, and
    ingest rejects any raw record that tries to smuggle a label across.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    result = gen_mod.gen(spec, seed)
    raw_path = run_dir / "raw.jsonl"
    truth_path = run_dir / "truth.jsonl"
    gen_mod.write_raw(raw_path, result.raw)
    gen_mod.write_truth(truth_path, result.truth)
    return GenStage(
        result=result,
        artifacts=(
            StageArtifact(stage="S2", name="raw.jsonl", path=raw_path, digest=result.raw_hash),
            StageArtifact(
                stage="S2", name="truth.jsonl", path=truth_path, digest=result.truth_hash
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S3  degrade
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DegradeStage:
    result: degrade_mod.DegradationResult
    raw_path: Path
    artifacts: tuple[StageArtifact, ...]


def s3_degrade(
    raw: tuple[gen_mod.RawEvent, ...],
    completeness: degrade_mod.Completeness,
    seed: int,
    run_dir: Path,
    parent: degrade_mod.DegradationResult | None = None,
    blackout: degrade_mod.Blackout | None = None,
) -> DegradeStage:
    """Delete down to `completeness`, nested with every other level at this seed.

    Delete-only. Nothing is edited, reordered or back-dated: the operator list in the
    manifest is exactly `["delete"]` and the removed set at a lower completeness is a
    superset of the removed set at a higher one, which is checked rather than assumed.

    With `blackout` set, the random deletion is replaced by WHOLE_SOURCE_BLACKOUT and the
    manifest names that operator instead. The two are not combined: a cell that mixed a
    controlled intervention with random loss could not attribute its effect to either.
    """
    if blackout is not None:
        if parent is not None or not completeness.is_identity:
            raise errors.SchemaError(
                "s3_degrade: a blackout cell is not part of the nested completeness chain; "
                "pass completeness 1/1 and no parent"
            )
        result = degrade_mod.blackout(raw, blackout)
    else:
        result = degrade_mod.degrade(raw, completeness, seed, parent=parent)
    raw_path = degrade_mod.write_degraded_raw(run_dir, result)
    manifest_path = degrade_mod.write_manifest(run_dir, result)
    return DegradeStage(
        result=result,
        raw_path=raw_path,
        artifacts=(
            StageArtifact(stage="S3", name=raw_path.name, path=raw_path, digest=result.raw_hash),
            StageArtifact(
                stage="S3",
                name="degradation_manifest.json",
                path=manifest_path,
                digest=result.manifest_hash(),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S4  ingest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IngestStage:
    result: ingest_mod.IngestResult
    bundle_hash: str
    artifacts: tuple[StageArtifact, ...]


def s4_ingest(
    raw_path: Path, spec: scenario_mod.ScenarioSpec, run_dir: Path
) -> IngestStage:
    """Seal the bundle. `t_ing_ns` is derived from the event instant, never from a clock."""
    result = ingest_mod.ingest(raw_path, spec.sources, ingest_time_ns=0)
    bundle_path, quarantine_path = result.write(run_dir)
    bundle_hash = canon.hash_ref("bundle", result.bundle_bytes)
    return IngestStage(
        result=result,
        bundle_hash=bundle_hash,
        artifacts=(
            StageArtifact(
                stage="S4", name="bundle.jsonl", path=bundle_path, digest=bundle_hash
            ),
            StageArtifact(
                stage="S4",
                name="ingest_quarantine.json",
                path=quarantine_path,
                digest=canon.hash_ref("quar", quarantine_path.read_bytes()),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S5  resolve
# ---------------------------------------------------------------------------


def join_rules_for(spec: scenario_mod.ScenarioSpec) -> tuple[resolve_mod.JoinRule, ...]:
    """The exact joins this scenario admits. Exact string equality only; no similarity.

    See `JOIN_RULES_NOTE` for why two of the closed five ids carry a second role each.
    """
    tables: dict[str, tuple[str, ...]] = {
        "device": spec.entities.devices,
        "principal": spec.entities.principal_ids,
        "resource": spec.entities.resource_ids,
        "service": spec.entities.service_ids,
        "credential": tuple(c for c, _s, _k in spec.entities.credentials),
    }
    built: list[resolve_mod.JoinRule] = []
    for join_rule_id, role, attr_key, kind in _JOIN_SPECS:
        names = tables.get(attr_key, ())
        if not names:
            continue
        ordered = canon.sorted_unique(names)
        built.append(
            resolve_mod.JoinRule(
                join_rule_id=join_rule_id,
                role=role,
                attr_key=attr_key,
                kind=kind,
                table=tuple((name, (name,)) for name in ordered),
            )
        )
    return tuple(sorted(built, key=lambda r: r.sort_key()))


@dataclass(frozen=True, slots=True)
class ResolveStage:
    result: resolve_mod.ResolveResult
    artifacts: tuple[StageArtifact, ...]


def s5_resolve(
    bundle: tuple[model.CanonicalEvent, ...],
    spec: scenario_mod.ScenarioSpec,
    run_dir: Path,
) -> ResolveStage:
    """Resolve every record's roles against the scenario's declared entity tables."""
    result = resolve_mod.resolve(bundle, join_rules_for(spec))
    er_path, quality_path = result.write(run_dir)
    return ResolveStage(
        result=result,
        artifacts=(
            StageArtifact(
                stage="S5",
                name="er.json",
                path=er_path,
                digest=canon.hash_ref("er", result.er_bytes),
            ),
            StageArtifact(
                stage="S5",
                name="er_quality.json",
                path=quality_path,
                digest=canon.hash_ref("erq", quality_path.read_bytes()),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S6  calibrate
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CalibrateStage:
    profile: calibrate_mod.SourceProfile
    profile_path: Path
    profile_hash: str
    reference_bundle_hash: str
    artifacts: tuple[StageArtifact, ...]


def _calibrate_phases(spec: scenario_mod.ScenarioSpec) -> tuple[calibrate_mod.Phase, ...]:
    return tuple(
        calibrate_mod.Phase(
            regime_id=p.regime_id, t0_ns=p.interval.t0_ns, t1_ns=p.interval.t1_ns
        )
        for p in spec.phases
    )


def _calibrate_excluded(
    spec: scenario_mod.ScenarioSpec,
) -> tuple[calibrate_mod.ExcludedInterval, ...]:
    return tuple(
        calibrate_mod.ExcludedInterval(
            t0_ns=x.interval.t0_ns, t1_ns=x.interval.t1_ns, reason=x.reason
        )
        for x in spec.excluded_intervals
    )


def s6_calibrate(
    layout: Layout,
    spec: scenario_mod.ScenarioSpec,
    config: liveness_mod.LivenessConfig,
    calibration_seed: int,
) -> CalibrateStage:
    """A SEPARATE clean run at completeness 1.0 under a seed from the calibration band.

    The threshold is never derived from the run under analysis. Deleting records from that
    run stretches its own gap distribution, so a quantile taken from it would rise exactly
    as degradation rose and suppression would hide itself at the levels the whole study is
    about. This is the one thing that cannot be cut from the slice.
    """
    calibration_seed = calibrate_mod.check_calibration_seed(calibration_seed)
    run_dir = layout.run_dir(f"calib-{calibration_seed}")
    run_dir.mkdir(parents=True, exist_ok=True)

    generated = gen_mod.gen(spec, calibration_seed)
    raw_path = run_dir / "raw.jsonl"
    gen_mod.write_raw(raw_path, generated.raw)
    gen_mod.write_truth(run_dir / "truth.jsonl", generated.truth)

    ingested = ingest_mod.ingest(raw_path, spec.sources, ingest_time_ns=0)
    ingested.write(run_dir)
    reference_bundle_hash = canon.hash_ref("bundle", ingested.bundle_bytes)

    by_source: dict[str, list[model.CanonicalEvent]] = {}
    for event in ingested.events:
        by_source.setdefault(str(event.source_id), []).append(event)

    events_by_source = tuple(
        (
            declared.source_id,
            declared.integrity_class,
            tuple(by_source.get(str(declared.source_id), ())),
        )
        for declared in sorted(
            spec.sources, key=lambda s: canon.byte_order_key(str(s.source_id))
        )
    )

    reference_manifest = {
        "bundle_provenance": BUNDLE_PROVENANCE,
        "completeness": {"den": 1, "num": 1},
        "kind": "calibration",
        "scenario_family": spec.family,
        "scenario_hash": spec.scenario_hash(),
        "seed": canon.mask_hex(calibration_seed),
    }
    manifest_path = run_dir / "manifest.json"
    manifest_octets = scf.write_scf(manifest_path, reference_manifest, where="manifest")

    profile = calibrate_mod.build_profile(
        scenario_family=spec.family,
        events_by_source=events_by_source,
        phases=_calibrate_phases(spec),
        excluded=_calibrate_excluded(spec),
        quantile_levels=(config.quantile,),
        generator_config_hash=spec.generator_config_hash(),
        reference_bundle_hash=reference_bundle_hash,
        reference_run_manifest_hash=canon.hash_ref("manifest", manifest_octets),
        calibration_seed=calibration_seed,
    )
    layout.profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = layout.profiles_dir / f"{spec.family}.json"
    calibrate_mod.write_profile(profile, str(profile_path))
    profile_hash = canon.hash_ref("profile", profile_path.read_bytes())

    return CalibrateStage(
        profile=profile,
        profile_path=profile_path,
        profile_hash=profile_hash,
        reference_bundle_hash=reference_bundle_hash,
        artifacts=(
            StageArtifact(
                stage="S6",
                name=profile_path.name,
                path=profile_path,
                digest=profile_hash,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S7  liveness
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LivenessStage:
    document: liveness_mod.LivenessDocument
    view: envelope_mod.LivenessView
    liveness_hash: str
    artifacts: tuple[StageArtifact, ...]


def _liveness_view(document: liveness_mod.LivenessDocument) -> envelope_mod.LivenessView:
    """Adapt the S7 document to the S9 reader without a JSON round trip.

    SEAM, recorded rather than patched around silently: `SourceLiveness.to_scf` writes
    `source_id` bare (`edr_host`), which is the form the checker reads, while
    `envelope.LivenessView.from_document` constructs a prefixed `SourceId` from it and
    rejects the bare form. Building the view from the objects avoids re-parsing bytes that
    were never meant to be re-parsed here, and leaves the written artifact in the shape the
    checker expects.
    """
    sources = []
    for entry in document.sources:
        intervals = tuple(
            envelope_mod.LivenessInterval(
                t0_ns=window.t0_ns,
                t1_ns=window.t1_ns,
                verdict=model.LivenessVerdict(str(window.verdict)),
                reason=str(window.reason),
                witness=tuple(EventId(w) for w in window.witness),
            )
            for window in entry.intervals
        )
        sources.append(
            envelope_mod.SourceLiveness(
                source_id=entry.source_id,
                integrity_class=entry.integrity_class,
                intervals=intervals,
            )
        )
    sources.sort(key=lambda s: canon.byte_order_key(str(s.source_id)))
    return envelope_mod.LivenessView(sources=tuple(sources))


def s7_liveness(
    spec: scenario_mod.ScenarioSpec,
    config: liveness_mod.LivenessConfig,
    bundle: tuple[model.CanonicalEvent, ...],
    profile: calibrate_mod.SourceProfile | None,
    binding_context: liveness_mod.BindingContext | None,
    run_dir: Path,
    *,
    no_profile: bool = False,
) -> LivenessStage:
    """Classify every source over every elementary interval. The only producer of licences.

    Running with neither a profile nor `--no-profile` is an error rather than a default: a
    run that silently proceeded without a profile would produce a document that looks
    calibrated and is not.
    """
    by_source: dict[str, list[model.CanonicalEvent]] = {}
    for event in bundle:
        by_source.setdefault(str(event.source_id), []).append(event)

    sources = tuple(
        liveness_mod.SourceInput(
            source_id=declared.source_id,
            integrity_class=declared.integrity_class,
            events=tuple(by_source.get(str(declared.source_id), ())),
            nominal_period_ns=declared.nominal_period_ns,
        )
        for declared in sorted(
            spec.sources, key=lambda s: canon.byte_order_key(str(s.source_id))
        )
    )

    document = liveness_mod.build_liveness_document(
        config=config,
        sources=sources,
        phases=_calibrate_phases(spec),
        scenario_t0_ns=spec.horizon.t0_ns,
        scenario_t1_ns=spec.horizon.t1_ns,
        profile=None if no_profile else profile,
        binding_context=None if no_profile else binding_context,
        no_profile=no_profile,
        excluded=_calibrate_excluded(spec),
    )
    path = run_dir / "liveness.json"
    liveness_mod.write_liveness(document, str(path))
    digest = canon.hash_ref("liveness", path.read_bytes())
    return LivenessStage(
        document=document,
        view=_liveness_view(document),
        liveness_hash=digest,
        artifacts=(
            StageArtifact(stage="S7", name="liveness.json", path=path, digest=digest),
        ),
    )


# ---------------------------------------------------------------------------
# The seam-2 projection
# ---------------------------------------------------------------------------


def project_bindings(
    bundle: tuple[model.CanonicalEvent, ...],
    er_bindings: tuple[resolve_mod.Binding, ...],
    axiom_roles: dict[str, tuple[str, ...]],
) -> tuple[tuple[model.CanonicalEvent, ...], tuple[ground_mod.Binding, ...], tuple[str, ...]]:
    """Bind seam 1 and seam 2 in one place, and report what did not line up.

    Returns the events as the grounder should see them, the projected bindings, and the
    complaints. An event keeps its own `event_id`, `source_id`, `seq`, `t_evt_ns` and
    `attrs`; only `event_type` is replaced by the bound axiom predicate, so every evidence
    reference the grounder mints still names a record that is in the hashed bundle exactly
    as ingest sealed it.
    """
    complaints: list[str] = []
    roles_by_event: dict[str, dict[str, EntityId]] = {}
    for binding in er_bindings:
        roles_by_event.setdefault(str(binding.event_id), {})[binding.role] = binding.entity_id

    seen_unbound: set[str] = set()
    seen_short: set[str] = set()
    events: list[model.CanonicalEvent] = []
    projected: list[ground_mod.Binding] = []

    for event in bundle:
        predicate = EVENT_TYPE_PREDICATE.get(event.event_type)
        if predicate is None:
            predicate = event.event_type
            if event.event_type not in seen_unbound:
                seen_unbound.add(event.event_type)
                complaints.append(
                    f"event type {event.event_type!r} has no axiom-predicate binding; it "
                    "seeds a predicate of its own name that no rule consumes"
                )
        wanted = axiom_roles.get(predicate)
        available = roles_by_event.get(str(event.event_id), {})
        if wanted is None:
            keep = tuple(sorted(available))
        else:
            missing = tuple(r for r in wanted if r not in available)
            if missing and predicate not in seen_short:
                seen_short.add(predicate)
                complaints.append(
                    f"{predicate}: the rule table binds roles {wanted} but records of "
                    f"{event.event_type!r} resolve {tuple(sorted(available))}; "
                    f"{missing} is unresolvable and the pattern cannot fire"
                )
            keep = tuple(r for r in wanted if r in available)
        events.append(
            model.CanonicalEvent(
                event_id=event.event_id,
                record_id=event.record_id,
                source_id=event.source_id,
                seq=event.seq,
                event_type=predicate,
                t_evt_ns=event.t_evt_ns,
                t_ing_ns=event.t_ing_ns,
                attrs=event.attrs,
                chain_prev=event.chain_prev,
                chain_hash=event.chain_hash,
            )
        )
        for role in keep:
            projected.append(
                ground_mod.Binding(
                    event_id=event.event_id, role=role, entity_id=available[role]
                )
            )

    events.sort(key=lambda e: e.sort_key())
    projected.sort(key=lambda b: b.sort_key())
    return tuple(events), tuple(projected), tuple(complaints)


def absence_oracle(
    document: liveness_mod.LivenessDocument,
) -> ground_mod.AbsenceAvailability:
    """The only permitted negation, answered from the pinned liveness document.

    OBSERVED only when every producing source is live over the whole sealed lookback;
    LICENSED only when every one of them is non-live over the whole of it; UNDETERMINED
    otherwise, which is the fail-closed answer and not a shrug.
    """

    def answer(
        sources: tuple[SourceId, ...], window: model.Interval
    ) -> ground_mod.Absence:
        status = liveness_mod.absence_status(
            document, tuple(str(s) for s in sources), window
        )
        return ground_mod.Absence(str(status))

    return answer


# ---------------------------------------------------------------------------
# S8  ground
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroundStage:
    result: ground_mod.GroundingResult
    artifacts: tuple[StageArtifact, ...]


def s8_ground(
    table: rules_mod.RuleTable,
    events: tuple[model.CanonicalEvent, ...],
    bindings: tuple[ground_mod.Binding, ...],
    availability: ground_mod.AbsenceAvailability,
    run_dir: Path,
    goal: FactHash | None = None,
) -> GroundStage:
    """The observed fixpoint. OBSERVED instances only; no licence is minted here."""
    result = ground_mod.ground(
        table, events, bindings, goal=goal, absence_availability=availability
    )
    path = run_dir / "p_min.json"
    digest = ground_mod.write_program(result.program, path)
    return GroundStage(
        result=result,
        artifacts=(StageArtifact(stage="S8", name="p_min.json", path=path, digest=digest),),
    )


# ---------------------------------------------------------------------------
# S9  envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EnvelopeStage:
    result: envelope_mod.EnvelopeResult
    artifacts: tuple[StageArtifact, ...]


def s9_envelope(
    table: rules_mod.RuleTable,
    events: tuple[model.CanonicalEvent, ...],
    bindings: tuple[ground_mod.Binding, ...],
    view: envelope_mod.LivenessView,
    entities: tuple[model.Entity, ...],
    availability: ground_mod.AbsenceAvailability,
    run_dir: Path,
    goal: FactHash | None = None,
    p_min: ground_mod.Program | None = None,
) -> EnvelopeStage:
    """P_max = P_min plus licensed silent instances plus obligation-forced GHOSTs.

    P_max unions every licensed silent instance and ignores mutual-exclusion structure, so
    it is a SUPERSET of the union of realizable worlds. A counterexample tree drawn from it
    may combine silent instances no single consistent world realizes and may therefore
    depict something that could not have happened.
    """
    result = envelope_mod.envelope(
        table,
        events,
        bindings,
        view,
        entities,
        goal=goal,
        absence_availability=availability,
        p_min=p_min,
    )
    path = run_dir / "p_max.json"
    digest = ground_mod.write_program(result.p_max, path)
    spots_path = run_dir / "blind_spots.json"
    envelope_mod.write_blind_spots(result.blind_spots, spots_path)
    return EnvelopeStage(
        result=result,
        artifacts=(
            StageArtifact(stage="S9", name="p_max.json", path=path, digest=digest),
            StageArtifact(
                stage="S9",
                name="blind_spots.json",
                path=spots_path,
                digest=canon.hash_ref("blindspots", spots_path.read_bytes()),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# S10  prove
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProveResult:
    """Everything S10 produced for one cell, as objects rather than as rendered text."""

    atoms: cut_mod.AtomTable
    goal_key: FactHash
    goal_library: tuple[FactHash, ...]
    goal_resolved: bool
    bracket: premium_mod.Bracket
    premium: premium_mod.PremiumResult
    premium_entries: tuple[cert_mod.PremiumEntry, ...]
    cut_delta: tuple[ControlId, ...]
    verdict_at_cut_min: cert_mod.Verdict
    verdict_at_cut_max: cert_mod.Verdict
    scope: cert_mod.Scope
    inputs: cert_mod.Inputs
    body: dict[str, Any]
    cert_path: Path
    flags: tuple[str, ...]
    licences: tuple[model.Licence, ...]
    silent_count: int
    ghost_count: int
    observed_event_count: int
    artifacts: tuple[StageArtifact, ...]


def _axiom_evidence(
    program: ground_mod.Program,
    events: tuple[model.CanonicalEvent, ...],
    bindings: tuple[ground_mod.Binding, ...],
) -> tuple[tuple[FactHash, tuple[EventId, ...]], ...]:
    """Which records seeded which axiom fact, so a witness leaf can cite a real record."""
    roles_by_event: dict[str, list[tuple[str, EntityId]]] = {}
    for binding in bindings:
        roles_by_event.setdefault(str(binding.event_id), []).append(
            (binding.role, binding.entity_id)
        )
    table: dict[str, set[str]] = {}
    axiom_keys = {str(k) for k in program.axioms}
    for event in events:
        fact = ground_mod.axiom_fact_for(event, roles_by_event.get(str(event.event_id), []))
        key = str(fact.fact_key)
        if key in axiom_keys:
            table.setdefault(key, set()).add(str(event.event_id))
    return tuple(
        (
            FactHash(key),
            tuple(EventId(e) for e in sorted(table[key], key=canon.byte_order_key)),
        )
        for key in sorted(table, key=canon.byte_order_key)
    )


def _build_reach(
    program: ground_mod.Program,
    goal: FactHash,
    evidence: tuple[tuple[FactHash, tuple[EventId, ...]], ...],
    library: tuple[FactHash, ...] = (),
) -> reach_mod.ReachProgram:
    """Index one program for propagation, against the WHOLE goal library.

    `goal` is the representative; `library` is every goal fact either program derives.
    Passing the library is what makes a severance mean every goal is underivable rather
    than one arbitrarily chosen goal. Before this, the representative alone decided
    derivability, and at full telemetry it was a fact only P_max derives - so the corridor
    search over P_min found nothing to sever and reported that the empty cut severs the
    attack while P_min reached the goal through route A.
    """
    axioms = {str(a) for a in program.axioms}
    kept = tuple(pair for pair in evidence if str(pair[0]) in axioms)
    goals = library if library else (goal,)
    if str(goal) not in {str(g) for g in goals}:
        goals = tuple(sorted({*goals, goal}, key=lambda g: canon.byte_order_key(str(g))))
    return reach_mod.ReachProgram.build(
        program.kind,
        program.instances,
        program.axioms,
        goal,
        axiom_evidence=kept,
        goals=goals,
    )


class _UnrepresentableWitness(Exception):
    """A derivation the certificate's witness alphabet cannot express. See `_cert_witness`."""


#: Containers the certificate spends before a witness tree's root node: the document,
#: `body`, the `witnesses` list, the entry object and the `tree` object. Fixed by the
#: certificate layout in cert.py, and stated there alongside MAX_DEPTH.
_CONTAINERS_ABOVE_WITNESS_ROOT: Final[int] = 5

#: The deepest witness tree, in NODE LEVELS, that the certificate contract can carry.
#: Each level below the root costs two containers: the parent's `children` list and the
#: child's own object. Derived from cert.MAX_DEPTH rather than written down, so that if the
#: contract ever changes on both sides together this bound follows it.
_MAX_WITNESS_LEVELS: Final[int] = (
    (cert_mod.MAX_DEPTH - _CONTAINERS_ABOVE_WITNESS_ROOT - 1) // 2 + 1
)


def _witness_levels(node: cert_mod.WitnessNode) -> int:
    """Height of a witness tree in node levels; a lone root is 1."""
    if not node.children:
        return 1
    return 1 + max(_witness_levels(child) for child in node.children)


def _cert_witness(
    node: reach_mod.WitnessNode, ghost_heads: frozenset[str]
) -> cert_mod.WitnessNode | None:
    """Translate a reach witness node into the certificate's shape, or refuse to.

    An AXIOM leaf is not an AND-node and has no instance id, so it is not published as a
    witness node; the instance above it already cites the records that seeded it.

    THE REFUSAL, recorded rather than worked around. `cert.WitnessNode` admits exactly two
    kinds. OBSERVED must cite at least one record; GHOST must cite none AND its instance
    must carry `ghost=True`, which the envelope sets only for an obligation-forced head. A
    LICENSED silent instance of a DETECT rule is neither: it cites no record, so it cannot
    be OBSERVED, and its head is not obligation-forced, so it cannot be GHOST. Such a
    derivation therefore has no representation in the certificate and is not published as
    one. Inventing a kind, or flagging the instance GHOST so that it fits, would put a
    silent instance into the certificate wearing the wrong word.
    """
    if node.instance_id is None:
        return None
    if node.kind == reach_mod.OBSERVED_KIND:
        kind = cert_mod.WitnessKind.OBSERVED
    elif str(node.head) in ghost_heads:
        kind = cert_mod.WitnessKind.GHOST
    else:
        raise _UnrepresentableWitness(str(node.instance_id))
    children = tuple(
        child
        for child in (_cert_witness(c, ghost_heads) for c in node.children)
        if child is not None
    )
    return cert_mod.WitnessNode(
        instance_id=node.instance_id,
        head=node.head,
        kind=kind,
        evidence=tuple(sorted(node.evidence, key=canon.byte_order_key)),
        children=children,
    )


def _calibration_deficiency(
    licences: tuple[model.Licence, ...], tick_granularity_ns: int
) -> tuple[int, int]:
    """The share of a control's licensed time resting on missing calibration, as u32/u32.

    WHY NOT NANOSECONDS. `liveness.calibration_deficiency` takes the exact ratio of two
    nanosecond sums and rejects it when the reduced rational does not fit u32/u32, which
    the certificate's field table requires. Over a two-hour horizon whose licence
    boundaries sit on jittered record timestamps, the reduced rational almost never fits:
    two coprime twelve-digit integers are the normal case, not the exceptional one.

    The spans are therefore quantised to the scenario's own tick granularity before the
    ratio is taken. That is a NARROWING and it is stated rather than hidden: the published
    rational is exact over tick-quantised spans, not over nanosecond spans, and a licence
    shorter than one tick contributes zero to both sides. The demonstration prints the
    nanosecond sums beside the rational so the quantisation is visible.

    The distinction this number exists to protect is not affected by the quantisation: a
    control whose licences rest on B_PROFILE_INSUFFICIENT, B_REGIME_UNKNOWN,
    B_FORCED_NO_PROFILE_MODE, B_THRESHOLD_OVERFLOW or B_WINDOW_UNDERSAMPLED is needed
    because THIS RUN WAS NOT CALIBRATED FOR THAT SOURCE, which is a different sentence from
    needed because a sensor could not see, and the two are never interchanged.
    """
    if tick_granularity_ns <= 0:
        return (0, 1)
    deficient = 0
    total = 0
    for licence in licences:
        span = (licence.t1_ns - licence.t0_ns) // tick_granularity_ns
        total += span
        try:
            reason = liveness_mod.Reason(licence.reason)
        except ValueError:
            continue
        if reason in liveness_mod.CALIBRATION_DEFICIENCY_REASONS:
            deficient += span
    if total == 0:
        return (0, 1)
    ratio = Fraction(deficient, total)
    if ratio.numerator > canon_u32_max() or ratio.denominator > canon_u32_max():
        raise errors.CanonError(
            "calibration_deficiency does not fit u32/u32 even at tick resolution; the "
            "premium entry would have to carry an inexact number and does not",
            code="E-CANON-WIDTH",
        )
    return (ratio.numerator, ratio.denominator)


def canon_u32_max() -> int:
    return (1 << 32) - 1


def _flags_for(
    *,
    grounding_capped: bool,
    corridor_cap: bool,
    er_ambiguous: bool,
    quarantined: bool,
    profile_missing: bool,
    atoms_over_budget: bool,
) -> tuple[str, ...]:
    """Flags in BIT ORDER, which is the only order the certificate admits."""
    named = (
        ("grounding_capped", grounding_capped),
        ("corridor_cap", corridor_cap),
        ("atoms_over_budget", atoms_over_budget),
        ("er_ambiguous", er_ambiguous),
        ("quarantined_records", quarantined),
        ("profile_missing", profile_missing),
    )
    chosen = [name for name, on in named if on]
    return tuple(sorted(chosen, key=lambda n: cert_mod.FLAG_BY_NAME[n].bit))


def _decide_safety(
    *,
    flags: tuple[str, ...],
    goal_in_pmax: bool,
    goal_in_pmin: bool,
    pmax_terminated: bool,
) -> cert_mod.Safety:
    """The decision flow of the verdict section, and no other control flow."""
    mask = cert_mod.flags_mask(flags)
    if mask & cert_mod.SOUNDNESS_MASK == 0:
        if not goal_in_pmax and pmax_terminated:
            return cert_mod.Safety.ROBUST
        if goal_in_pmin:
            return cert_mod.Safety.UNSAFE
        return cert_mod.Safety.OPTIMISTIC_ONLY
    if goal_in_pmin:
        return cert_mod.Safety.UNSAFE
    return cert_mod.Safety.INDETERMINATE


def _build_verdict(
    *,
    safety: cert_mod.Safety,
    minimality: model.Minimality,
    flags: tuple[str, ...],
    witness_has_ghost: bool,
    liveness: liveness_mod.LivenessDocument,
) -> cert_mod.Verdict:
    witness_class: cert_mod.WitnessClass | None = None
    if safety is cert_mod.Safety.UNSAFE:
        if "er_ambiguous" in flags:
            witness_class = cert_mod.WitnessClass.CONTESTED
        elif witness_has_ghost:
            witness_class = cert_mod.WitnessClass.LICENSED
        else:
            witness_class = cert_mod.WitnessClass.OBSERVED
    proposal = cert_mod.VerdictProposal(
        safety=safety,
        minimality=minimality,
        flags=flags,
        derived_suppressed=cert_mod.DERIVED_SUPPRESSED_ALWAYS,
        realizability=cert_mod.Realizability.UNCHECKED,
        witness_class=witness_class,
    )
    token = None
    if safety is cert_mod.Safety.ROBUST:
        # Read from the liveness document, never written here as constants. In this slice
        # both are always empty and false, because the backdating pass does not exist
        # (liveness.TAMPER_PASS_IMPLEMENTED); passing literals would have kept a future pass
        # from blocking ROBUST without any test noticing.
        token = cert_mod.mint_no_tamper_token(
            tamper_suspected_sources=tuple(
                str(entry.source_id) for entry in liveness.sources if entry.tamper_suspected
            ),
            verdict_tamper_sensitive=liveness.flags.verdict_tamper_sensitive,
            sources=len(liveness.sources),
        )
    return cert_mod.Verdict.build(
        proposal, no_tamper_token=token, pmax_fixpoint_terminated=True
    )


# ---------------------------------------------------------------------------
# The cell
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CellResult:
    """One completeness cell, end to end. Nothing here is a measurement."""

    run_id: str
    run_dir: Path
    completeness: degrade_mod.Completeness
    seed: int
    degradation_seed: int
    spec: scenario_mod.ScenarioSpec
    rules: RulesResult
    gen: GenStage
    degrade: DegradeStage
    ingest: IngestStage
    resolve: ResolveStage
    liveness: LivenessStage
    ground: GroundStage
    envelope: EnvelopeStage
    prove: ProveResult
    complaints: tuple[str, ...]
    artifacts: tuple[StageArtifact, ...]
    verify_exit: int | None = None
    verify_text: str = ""


def _entity_objects(result: resolve_mod.ResolveResult) -> tuple[model.Entity, ...]:
    return tuple(sorted(result.entities, key=lambda e: str(e.entity_id)))


def _resolve_goal(
    goal_spec: cut_mod.GoalSpec,
    programs: tuple[ground_mod.Program, ...],
    entities: tuple[model.Entity, ...],
) -> tuple[FactHash, tuple[FactHash, ...], bool, tuple[str, ...]]:
    """SEAM 3. Bind the authored goal to the rule table and pick a search target.

    The library is every fact of the bound predicate whose argument vector contains every
    authored argument that resolves to a declared entity. An authored argument that
    resolves to nothing is reported, never invented. The search target is the bytewise
    least member, which is order-independent; when the library is empty the target is a
    fact key no instance heads, so the goal is underivable under every cut.
    """
    complaints: list[str] = []
    predicate = GOAL_PREDICATE_BINDING.get(goal_spec.goal_predicate, goal_spec.goal_predicate)
    if predicate != goal_spec.goal_predicate:
        complaints.append(
            f"goal.toml names {goal_spec.goal_predicate!r}, which no rule heads; it is bound "
            f"to the rule table's terminal head {predicate!r}"
        )

    by_name: dict[str, list[EntityId]] = {}
    for entity in entities:
        by_name.setdefault(entity.canonical_name, []).append(entity.entity_id)
    wanted: list[EntityId] = []
    for arg in goal_spec.goal_args:
        found = by_name.get(arg)
        if not found:
            complaints.append(
                f"goal argument {arg!r} resolves to no entity the scenario declares; it is "
                "dropped from the goal filter rather than invented"
            )
            continue
        wanted.extend(found)

    library: set[str] = set()
    for program in programs:
        for fact in program.facts:
            if fact.predicate != predicate:
                continue
            args = {str(a) for a in fact.args}
            if all(str(w) in args for w in wanted):
                library.add(str(fact.fact_key))
    ordered = tuple(
        FactHash(key) for key in sorted(library, key=canon.byte_order_key)
    )
    if ordered:
        return ordered[0], ordered, True, tuple(complaints)

    complaints.append(
        f"no fact of {predicate!r} is derived in either program; the goal library is empty "
        "and the run proves against a sentinel key that no instance heads"
    )
    sentinel = model.Fact.mint(predicate, tuple(wanted), goal_spec.horizon_k).fact_key
    return sentinel, (), False, tuple(complaints)


def s10_prove(
    *,
    layout: Layout,
    spec: scenario_mod.ScenarioSpec,
    rules: RulesResult,
    ingest_stage: IngestStage,
    resolve_stage: ResolveStage,
    liveness_stage: LivenessStage,
    calibration: CalibrateStage,
    ground_stage: GroundStage,
    envelope_stage: EnvelopeStage,
    events: tuple[model.CanonicalEvent, ...],
    bindings: tuple[ground_mod.Binding, ...],
    bits: rules_mod.BitTable,
    catalog: rules_mod.Catalog,
    seed: int,
    run_dir: Path,
) -> tuple[ProveResult, tuple[str, ...]]:
    """Run the cut machinery twice, compute the premium, and emit one certificate.

    The two-sided bracket is reported as a pair. It is NOT a confidence interval and is
    never rendered as one.
    """
    complaints: list[str] = []
    atoms = cut_mod.AtomTable.build(bits.literals())

    p_min = ground_stage.result.program
    p_max = envelope_stage.result.p_max
    entities = _entity_objects(resolve_stage.result)

    goal_key, library, resolved, goal_complaints = _resolve_goal(
        rules.goal_spec, (p_min, p_max), entities
    )
    complaints.extend(goal_complaints)

    evidence = _axiom_evidence(p_max, events, bindings)
    lower = _build_reach(p_min, goal_key, evidence, library)
    upper = _build_reach(p_max, goal_key, evidence, library)

    bracket = premium_mod.two_sided_bracket(lower, upper, atoms)

    grounding_capped = ground_stage.result.capped or envelope_stage.result.capped
    corridor_cap = (
        bracket.lower.corridor_cap_hit or bracket.upper.corridor_cap_hit
    )
    budget_exhausted = bracket.lower.budget_exhausted or bracket.upper.budget_exhausted

    premium = premium_mod.blindness_premium(
        psi_min=bracket.lower.psi,
        psi_max=bracket.upper.psi,
        atoms=atoms,
        grounding_capped=grounding_capped,
        budget_exhausted=budget_exhausted,
        er_ambiguous=resolve_stage.result.er_ambiguous,
    )

    cut_min = bracket.lower.cut
    cut_max = bracket.upper.cut
    delta, _caption = premium_mod.cut_delta_canonical(cut_min, cut_max)

    reach_min_at_min = reach_mod.reach(lower, cut_min.mask)
    reach_max_at_min = reach_mod.reach(upper, cut_min.mask)
    reach_min_at_max = reach_mod.reach(lower, cut_max.mask)
    reach_max_at_max = reach_mod.reach(upper, cut_max.mask)

    flags = _flags_for(
        grounding_capped=grounding_capped,
        corridor_cap=corridor_cap,
        er_ambiguous=resolve_stage.result.er_ambiguous,
        quarantined=ingest_stage.result.quarantined_records,
        profile_missing=False,
        atoms_over_budget=False,
    )

    ghost_head_keys = frozenset(str(i.head) for i in p_max.instances if i.ghost)
    witnesses: list[cert_mod.WitnessEntry] = []
    witness_has_ghost = False
    raised = sorted(
        {str(a.control_id) for a in cut_max.atoms}, key=canon.byte_order_key
    )
    for control in raised:
        levels = {
            str(a.control_id): max(
                (x.level for x in cut_max.atoms if str(x.control_id) == str(a.control_id)),
                default=0,
            )
            for a in cut_max.atoms
        }
        levels.pop(control, None)
        probe = atoms.cut_of_levels(levels, model.Minimality.UNVERIFIED)
        probe_reach = reach_mod.reach(upper, probe.mask)
        if not probe_reach.derivable:
            continue
        tree = reach_mod.witness_tree(upper, probe.mask, probe_reach)
        try:
            node = _cert_witness(tree, ghost_head_keys)
        except _UnrepresentableWitness as refused:
            complaints.append(
                f"the derivation that re-appears when {control} is dropped runs through "
                f"licensed silent instance {refused}, whose head is not obligation-forced; "
                "cert.WitnessNode has no kind for it, so no witness tree is published for "
                "that control"
            )
            continue
        if node is None:
            continue
        levels = _witness_levels(node)
        if levels > _MAX_WITNESS_LEVELS:
            # The certificate contract caps nesting at cert.MAX_DEPTH containers, which
            # admits a root and one level of children. A real multi-step derivation is
            # deeper than that. Raising the cap on this side alone would emit a file the
            # checker is obliged to reject, because the two share the constant; so the
            # tree is not published and the omission is reported. Before this check the
            # refusal happened inside cert.emit and aborted the whole run instead of
            # dropping one witness.
            complaints.append(
                f"the derivation that re-appears when {control} is dropped is {levels} "
                f"levels deep; the certificate contract carries at most "
                f"{_MAX_WITNESS_LEVELS}, so no witness tree is published for that control"
            )
            continue
        witness_has_ghost = witness_has_ghost or node.contains_ghost()
        witnesses.append(
            cert_mod.WitnessEntry(removed_control=ControlId(control), tree=node)
        )
    witness_entries = tuple(
        sorted(witnesses, key=lambda w: canon.byte_order_key(str(w.removed_control)))
    )

    safety_at_max = _decide_safety(
        flags=flags,
        goal_in_pmax=reach_max_at_max.derivable,
        goal_in_pmin=reach_min_at_max.derivable,
        pmax_terminated=True,
    )
    safety_at_min = _decide_safety(
        flags=flags,
        goal_in_pmax=reach_max_at_min.derivable,
        goal_in_pmin=reach_min_at_min.derivable,
        pmax_terminated=True,
    )

    verdict_max = _build_verdict(
        safety=safety_at_max,
        minimality=bracket.upper.minimality,
        flags=flags,
        witness_has_ghost=witness_has_ghost,
        liveness=liveness_stage.document,
    )
    verdict_min = _build_verdict(
        safety=safety_at_min,
        minimality=bracket.lower.minimality,
        flags=flags,
        witness_has_ghost=witness_has_ghost,
        liveness=liveness_stage.document,
    )

    licences = envelope_stage.result.licences
    silent_refs = tuple(
        sorted(
            (
                cert_mod.SilentRef(
                    instance_id=inst.instance_id, license_ids=inst.license_ids
                )
                for inst in p_max.instances
                if inst.observed is model.Observation.LICENSED
            ),
            key=lambda s: canon.byte_order_key(str(s.instance_id)),
        )
    )
    cited = {str(lid) for ref in silent_refs for lid in ref.license_ids}
    published_licences = tuple(
        lic for lic in licences if str(lic.license_id) in cited
    )

    observed_events = {
        str(ref.event_id)
        for inst in p_max.instances
        if inst.observed is model.Observation.OBSERVED
        for ref in inst.evidence
    }
    ghost_heads = {str(inst.head) for inst in p_max.instances if inst.ghost}

    goals = tuple(
        cert_mod.GoalRef(
            goal_key=key, derivable=str(key) in {str(f) for f in reach_max_at_max.order}
        )
        for key in (library if library else (goal_key,))
    )
    goals = tuple(sorted(goals, key=lambda g: canon.byte_order_key(str(g.goal_key))))
    derivable = tuple(g.goal_key for g in goals if g.derivable)
    severed = tuple(g.goal_key for g in goals if not g.derivable)

    corridors_open = tuple(
        sorted(
            (
                c.corridor_id
                for c in bracket.upper.psi.corridors
                if c.mask & cut_max.mask == 0
            ),
            key=canon.byte_order_key,
        )
    )
    residual = cert_mod.Residual(
        program=model.ProgramKind.P_MAX,
        goals_derivable=derivable,
        goals_severed=severed,
        corridors_open=corridors_open,
        corridors_exhaustive=bracket.upper.psi.complete and not grounding_capped,
    )

    invariant: tuple[FactHash, ...] | None = None
    if goals and not derivable:
        invariant = tuple(
            sorted(
                (FactHash(str(f)) for f in reach_max_at_max.order),
                key=canon.byte_order_key,
            )
        )

    premium_entries: tuple[cert_mod.PremiumEntry, ...] = ()
    premium_member: cert_mod.Premium | None = None
    premium_reason: str | None = None
    if premium.published:
        entries: list[cert_mod.PremiumEntry] = []
        for control in premium.blindness_premium:
            relevant = tuple(
                lic
                for lic in published_licences
                if any(
                    str(lic.license_id) in {str(x) for x in inst.license_ids}
                    for inst in p_max.instances
                    if inst.observed is model.Observation.LICENSED
                    and any(term & (1 << a.bit) for term in inst.blockers
                            for a in atoms.levels_of(ControlId(str(control))))
                )
            )
            num, den = _calibration_deficiency(relevant, spec.tick_granularity_ns)
            entries.append(
                cert_mod.PremiumEntry(
                    control_id=ControlId(str(control)),
                    license_ids=tuple(
                        sorted(
                            (lic.license_id for lic in relevant), key=canon.byte_order_key
                        )
                    ),
                    calibration_deficiency=Fraction(num, den),
                )
            )
        premium_entries = tuple(
            sorted(entries, key=lambda e: canon.byte_order_key(str(e.control_id)))
        )
        premium_member = cert_mod.Premium(
            nec_max=tuple(ControlId(str(c)) for c in premium.nec_max),
            occ_min=tuple(ControlId(str(c)) for c in premium.occ_min),
            blindness_premium=tuple(
                ControlId(str(c)) for c in premium.blindness_premium
            ),
            per_control=premium_entries,
        )
    else:
        assert premium.suppressed_reason is not None
        premium_reason = str(premium.suppressed_reason)

    inputs = cert_mod.Inputs(
        rules_hash=canon.hash_ref("rules", rules.rules_cae),
        rules_text_hash=canon.hash_ref(
            "rulestext", layout.rules_toml.read_bytes()
        ),
        guard_ast_hash=canon.hash_ref("guardast", rules.guards_cae),
        controls_hash=canon.hash_ref("controls", rules.controls_cae),
        catalog_bits_hash=canon.hash_ref("catbits", layout.bits_lock.read_bytes()),
        bundle_hash=ingest_stage.bundle_hash,
        liveness_hash=liveness_stage.liveness_hash,
        profile_hash=calibration.profile_hash,
        goal_hash=canon.hash_ref("goal", rules.goal_cae),
        er_hash=canon.hash_ref("er", resolve_stage.result.er_bytes),
        instances_hash=cert_mod.instances_hash(p_max.instances),
        seed=seed,
        k=rules.goal_spec.horizon_k,
    )
    scope = cert_mod.Scope(
        rules=inputs.rules_hash,
        controls=inputs.controls_hash,
        liveness=inputs.liveness_hash,
        er=inputs.er_hash,
        goal=inputs.goal_hash,
        bundle=inputs.bundle_hash,
    )

    budgets = cert_mod.Budgets(
        fixpoint_steps=ground_stage.result.fixpoint_steps
        + bracket.lower.fixpoint_steps
        + bracket.upper.fixpoint_steps,
        bb_nodes=bracket.lower.bb_nodes + bracket.upper.bb_nodes + premium.bb_nodes,
        step_budget=cut_mod.STEP_BUDGET,
        budget_exhausted=budget_exhausted,
        exhaustive_ran=False,
        exhaustive_cuts_tested=0,
    )

    body = cert_mod.build_body(
        scope=scope,
        inputs=inputs,
        verdict=verdict_max,
        atoms=atoms.literals,
        cut=cut_max,
        goals=goals,
        invariant=invariant,
        instances=p_max.instances,
        licenses=published_licences,
        silent=silent_refs,
        witnesses=witness_entries,
        psi=cert_mod.Psi(
            program=model.ProgramKind.P_MAX,
            complete=bracket.upper.psi.complete,
            corridors=bracket.upper.psi.corridors,
        ),
        premium=premium_member,
        premium_suppressed_reason=premium_reason,
        cut_delta_canonical=tuple(ControlId(str(c)) for c in delta),
        residual=residual,
        budgets=budgets,
        observed_event_count=len(observed_events),
        ghost_count=len(ghost_heads),
        psi_min_complete=bracket.lower.psi.complete,
    )
    artifact = cert_mod.emit(body, verdict_max, scope)
    cert_path = run_dir / "cert.spcert"
    cert_mod.write_certificate(cert_path, artifact)

    side: list[StageArtifact] = [
        StageArtifact(
            stage="S10", name="cert.spcert", path=cert_path, digest=artifact.cert_hash
        )
    ]
    for name, payload in (
        ("psi_min.json", _psi_document(bracket.lower, model.ProgramKind.P_MIN)),
        ("psi_max.json", _psi_document(bracket.upper, model.ProgramKind.P_MAX)),
        ("cut_min.json", _cut_document(cut_min, atoms)),
        ("cut_max.json", _cut_document(cut_max, atoms)),
        ("premium.json", _premium_document(premium)),
        ("residual.json", residual.as_member()),
        ("decisive.json", _decisive_document(bracket, published_licences)),
    ):
        path = run_dir / name
        octets = scf.write_scf(path, payload, where=name)
        side.append(
            StageArtifact(
                stage="S10", name=name, path=path, digest=canon.hash_ref("s10", octets)
            )
        )

    manifest = {
        "bundle_provenance": BUNDLE_PROVENANCE,
        "excluded_intervals_hash": calibrate_mod.excluded_intervals_hash(
            _calibrate_excluded(spec)
        ),
        "generator_config_hash": spec.generator_config_hash(),
        "identity_spec_hash": calibrate_mod.IDENTITY_SPEC_HASH,
        "implementation": "python-reference",
        "scenario_family": spec.family,
        "scenario_hash": spec.scenario_hash(),
        "seed": canon.mask_hex(seed),
        "seam_bindings": {
            "event_type_predicate": [
                {"axiom_predicate": value, "event_type": key}
                for key, value in sorted(EVENT_TYPE_PREDICATE.items())
            ],
            "goal_predicate": [
                {"authored": key, "bound_to": value}
                for key, value in sorted(GOAL_PREDICATE_BINDING.items())
            ],
            "join_rules_note": JOIN_RULES_NOTE,
        },
    }
    manifest_path = run_dir / "manifest.json"
    manifest_octets = scf.write_scf(manifest_path, manifest, where="manifest")
    side.append(
        StageArtifact(
            stage="S10",
            name="manifest.json",
            path=manifest_path,
            digest=canon.hash_ref("manifest", manifest_octets),
        )
    )

    return (
        ProveResult(
            atoms=atoms,
            goal_key=goal_key,
            goal_library=library,
            goal_resolved=resolved,
            bracket=bracket,
            premium=premium,
            premium_entries=premium_entries,
            cut_delta=tuple(ControlId(str(c)) for c in delta),
            verdict_at_cut_min=verdict_min,
            verdict_at_cut_max=verdict_max,
            scope=scope,
            inputs=inputs,
            body=body,
            cert_path=cert_path,
            flags=flags,
            licences=published_licences,
            silent_count=len(silent_refs),
            ghost_count=len(ghost_heads),
            observed_event_count=len(observed_events),
            artifacts=tuple(side),
        ),
        tuple(complaints),
    )


def _psi_document(search: cut_mod.CutSearch, kind: model.ProgramKind) -> dict[str, Any]:
    return {
        "bb_nodes": search.psi.bb_nodes,
        "complete": search.psi.complete,
        "corridor_cap": search.psi.corridor_cap,
        "corridors": [
            {
                "atom_ranks": list(c.atom_ranks),
                "corridor_id": str(c.corridor_id),
                "mask": canon.mask_hex(c.mask),
            }
            for c in search.psi.corridors
        ],
        "program": str(kind),
        "schema": "spectra.vs.psi/1",
    }


def _cut_document(cut: model.Cut, atoms: cut_mod.AtomTable) -> dict[str, Any]:
    return {
        "atoms": [
            {
                "bit": a.bit,
                "control_id": str(a.control_id),
                "level": a.level,
                "rank": a.rank,
            }
            for a in cut.atoms
        ],
        "cardinality": cut.cardinality,
        "mask": canon.mask_hex(cut.mask),
        "minimality": str(cut.minimality),
        "schema": "spectra.vs.cut/1",
    }


def _premium_document(result: premium_mod.PremiumResult) -> dict[str, Any]:
    if not result.published:
        return {
            "published": False,
            "schema": "spectra.vs.premium/1",
            "suppressed_reason": str(result.suppressed_reason),
        }
    return {
        "bb_nodes": result.bb_nodes,
        "blindness_premium": [str(c) for c in result.blindness_premium],
        "nec_max": [str(c) for c in result.nec_max],
        "occ_min": [str(c) for c in result.occ_min],
        "published": True,
        "schema": "spectra.vs.premium/1",
        "solves": result.solves,
    }


def _decisive_document(
    bracket: premium_mod.Bracket, licences: tuple[model.Licence, ...]
) -> dict[str, Any]:
    """The corridors in Psi_max and not in Psi_min, with the licences available to kill them.

    This is NOT the decisive-observation set until the minimum-cardinality search over
    (source, interval) pairs has actually run, so the document says which corridors are new
    and which licences exist and stops there. Saying "enabling source s removes control c"
    without that computation would be a claim this slice has not earned.
    """
    lower = {str(c.corridor_id) for c in bracket.lower.psi.corridors}
    new = tuple(
        sorted(
            (
                str(c.corridor_id)
                for c in bracket.upper.psi.corridors
                if str(c.corridor_id) not in lower
            ),
            key=canon.byte_order_key,
        )
    )
    return {
        "candidate_observations": [
            {
                "basis": str(lic.basis),
                "reason": lic.reason,
                "source_id": str(lic.source_id),
                "t0_ns": str(lic.t0_ns),
                "t1_ns": str(lic.t1_ns),
            }
            for lic in licences
        ],
        "corridors_only_in_psi_max": list(new),
        "note": (
            "the minimum-cardinality search over (source, interval) pairs has not run; "
            "no observation is claimed sufficient for any corridor"
        ),
        "schema": "spectra.vs.decisive/1",
        "search_ran": False,
    }


# ---------------------------------------------------------------------------
# S11  verify
# ---------------------------------------------------------------------------


def s11_verify(
    layout: Layout, cell: CellResult, calibration: CalibrateStage
) -> tuple[int, str]:
    """Run the separate checker package in a fresh process over one certificate.

    MODULE independence only. The checker imports nothing from `spectra_vs`, but it shares
    an author, a language and a reading of the specification with the emitter, so a shared
    misreading is invisible to it. An ACCEPT establishes internal consistency with the
    hashed inputs and nothing more; no certificate here is independently verified.
    """
    run_dir = cell.run_dir
    argv = [
        sys.executable,
        "-m",
        "spectra_vs_verify",
        str(cell.prove.cert_path),
        "--rules",
        str(layout.rules_toml),
        "--rules-cae",
        str(run_dir / "rules.cae"),
        "--guards",
        str(run_dir / "guards.cae"),
        "--controls-cae",
        str(run_dir / "controls.cae"),
        "--catalog-bits",
        str(layout.bits_lock),
        "--bundle",
        str(run_dir / "bundle.jsonl"),
        "--liveness",
        str(run_dir / "liveness.json"),
        "--profile",
        str(calibration.profile_path),
        "--goal-cae",
        str(run_dir / "goal.cae"),
        "--er",
        str(run_dir / "er.json"),
        "--run-manifest",
        str(run_dir / "manifest.json"),
    ]
    env_path = str(layout.repo_root / "python" / "spectra_vs_verify" / "src")
    core_path = str(layout.repo_root / "python" / "spectra_core" / "src")
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={
            "PYTHONPATH": env_path + ";" + core_path,
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C",
            "SYSTEMROOT": _systemroot(),
            "PATH": "",
        },
        check=False,
    )
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def _systemroot() -> str:
    """Windows needs this one variable to start a subprocess at all; nothing reads it here."""
    import os

    return os.environ.get("SYSTEMROOT", "")


# ---------------------------------------------------------------------------
# The whole chain
# ---------------------------------------------------------------------------


def run_cell(
    layout: Layout,
    *,
    completeness: degrade_mod.Completeness,
    seed: int = DEFAULT_ANALYSIS_SEED,
    degradation_seed: int = DEFAULT_DEGRADATION_SEED,
    calibration: CalibrateStage | None = None,
    calibration_seed: int = DEFAULT_CALIBRATION_SEED,
    parent: degrade_mod.DegradationResult | None = None,
    verify: bool = True,
    blackout: degrade_mod.Blackout | None = None,
) -> CellResult:
    """S1 through S11 for one cell. Pure in its arguments; writes artifacts.

    A cell is either a completeness level, nested with the others at one seed, or - with
    `blackout` set - a controlled WHOLE_SOURCE_BLACKOUT at completeness 1/1.
    """
    spec = scenario_mod.load_scenario(layout.scenario_toml)
    config = liveness_mod.load_liveness_config(str(layout.liveness_toml))
    catalog, bits, lock_artifact = s0_bits_lock(layout)

    if calibration is None:
        calibration = s6_calibrate(layout, spec, config, calibration_seed)

    run_id = run_id_for(spec.scenario_hash(), seed, completeness, blackout)
    run_dir = layout.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    rules = s1_rules(layout, catalog, bits, run_dir)
    axiom_roles = axiom_roles_of(rules.table)

    generated = s2_gen(spec, seed, run_dir)
    degraded = s3_degrade(
        generated.result.raw, completeness, degradation_seed, run_dir, parent, blackout
    )
    ingested = s4_ingest(degraded.raw_path, spec, run_dir)
    resolved = s5_resolve(ingested.result.events, spec, run_dir)

    binding_context = liveness_mod.BindingContext(
        bundle_hash=ingested.bundle_hash,
        seed=seed,
        generator_config_hash=spec.generator_config_hash(),
        scenario_family=spec.family,
        excluded_intervals_hash=calibrate_mod.excluded_intervals_hash(
            _calibrate_excluded(spec)
        ),
    )
    live_stage = s7_liveness(
        spec, config, ingested.result.events, calibration.profile, binding_context, run_dir
    )

    events, bindings, complaints = project_bindings(
        ingested.result.events, resolved.result.bindings, axiom_roles
    )
    availability = absence_oracle(live_stage.document)

    grounded = s8_ground(rules.table, events, bindings, availability, run_dir)
    enveloped = s9_envelope(
        rules.table,
        events,
        bindings,
        live_stage.view,
        _entity_objects(resolved.result),
        availability,
        run_dir,
        p_min=grounded.result.program,
    )

    proved, prove_complaints = s10_prove(
        layout=layout,
        spec=spec,
        rules=rules,
        ingest_stage=ingested,
        resolve_stage=resolved,
        liveness_stage=live_stage,
        calibration=calibration,
        ground_stage=grounded,
        envelope_stage=enveloped,
        events=events,
        bindings=bindings,
        bits=bits,
        catalog=catalog,
        seed=seed,
        run_dir=run_dir,
    )

    artifacts = (
        (lock_artifact,)
        + rules.artifacts
        + generated.artifacts
        + degraded.artifacts
        + ingested.artifacts
        + resolved.artifacts
        + calibration.artifacts
        + live_stage.artifacts
        + grounded.artifacts
        + enveloped.artifacts
        + proved.artifacts
    )

    cell = CellResult(
        run_id=run_id,
        run_dir=run_dir,
        completeness=completeness,
        seed=seed,
        degradation_seed=degradation_seed,
        spec=spec,
        rules=rules,
        gen=generated,
        degrade=degraded,
        ingest=ingested,
        resolve=resolved,
        liveness=live_stage,
        ground=grounded,
        envelope=enveloped,
        prove=proved,
        complaints=complaints + prove_complaints,
        artifacts=artifacts,
    )
    if not verify:
        return cell
    code, text = s11_verify(layout, cell, calibration)
    return CellResult(
        run_id=cell.run_id,
        run_dir=cell.run_dir,
        completeness=cell.completeness,
        seed=cell.seed,
        degradation_seed=cell.degradation_seed,
        spec=cell.spec,
        rules=cell.rules,
        gen=cell.gen,
        degrade=cell.degrade,
        ingest=cell.ingest,
        resolve=cell.resolve,
        liveness=cell.liveness,
        ground=cell.ground,
        envelope=cell.envelope,
        prove=cell.prove,
        complaints=cell.complaints,
        artifacts=cell.artifacts,
        verify_exit=code,
        verify_text=text,
    )
