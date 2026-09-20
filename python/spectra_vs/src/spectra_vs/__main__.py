"""`python -m spectra_vs` — one subcommand per stage boundary, plus `run` and `demo`.

SCOPE, STATED BEFORE ANY OPTION. SPECTRA-VS is a PYTHON REFERENCE IMPLEMENTATION. No Rust
kernel, no Go checker, no C guard VM and no Docker cyber range exists or is produced here.
Telemetry comes from a seeded synthetic generator and every artifact says so. Nothing this
command prints is a measurement.

The stage subcommands exist so that a reader can run one boundary at a time and look at
what it wrote; `run` threads S1 through S11 for one completeness cell; `demo` runs the two
cells the slice exists to contrast and prints them side by side.

`prove` requires either `--profile` or `--no-profile`. Running it with neither is an error
with exit code 2 and both options printed, because a run that silently proceeded without a
profile would produce a document that looks calibrated and is not.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Self-bootstrap. No package in this workspace is installed, there is no pip and no
# network, so `python -m spectra_vs` has only this package's own src directory on the path
# and cannot see its siblings. Two lines put the repository root's spectra_core on the
# path; `install()` appends the rest, so a genuinely installed package still wins.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[4] / "python" / "spectra_core" / "src")
)
from spectra_core.bootstrap import install

install(Path(__file__).resolve().parents[4])

from spectra_core import canon  # noqa: E402

from spectra_vs import calibrate as calibrate_mod  # noqa: E402
from spectra_vs import degrade as degrade_mod  # noqa: E402
from spectra_vs import liveness as liveness_mod  # noqa: E402
from spectra_vs import pipeline as pipeline_mod  # noqa: E402
from spectra_vs import scenario as scenario_mod  # noqa: E402
from spectra_vs import gen as gen_mod  # noqa: E402

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2

_SCOPE_BANNER = (
    "SPECTRA-VS is a Python reference implementation. No Rust kernel, no Go checker and "
    "no Docker range exists here; telemetry is generator output, never service output."
)


def _layout(args: argparse.Namespace) -> pipeline_mod.Layout:
    return pipeline_mod.Layout(repo_root=Path(args.repo_root).resolve())


def _completeness(text: str) -> degrade_mod.Completeness:
    """`--completeness 70/100`. An exact rational; a decimal literal is rejected."""
    if "/" not in text:
        raise argparse.ArgumentTypeError(
            f"completeness {text!r} must be an exact rational num/den; a decimal literal "
            "would make the surviving record count depend on a rounding mode"
        )
    num_text, den_text = text.split("/", 1)
    if not num_text.isdigit() or not den_text.isdigit():
        raise argparse.ArgumentTypeError(f"completeness {text!r} is not two integers")
    return degrade_mod.Completeness.of(int(num_text), int(den_text))


def _scenario(layout: pipeline_mod.Layout) -> scenario_mod.ScenarioSpec:
    return scenario_mod.load_scenario(layout.scenario_toml)


def _config(layout: pipeline_mod.Layout) -> liveness_mod.LivenessConfig:
    return liveness_mod.load_liveness_config(str(layout.liveness_toml))


def _report(artifacts: tuple[pipeline_mod.StageArtifact, ...]) -> None:
    for artifact in artifacts:
        print(f"  {artifact.stage}  {artifact.name:<28} {artifact.digest}")
        print(f"        {artifact.path}")


# ---------------------------------------------------------------------------
# Stage subcommands
# ---------------------------------------------------------------------------


def cmd_bits(args: argparse.Namespace) -> int:
    layout = _layout(args)
    _catalog, bits, artifact = pipeline_mod.s0_bits_lock(layout)
    print(f"S0 bits-lock: {len(bits.entries)} positions")
    _report((artifact,))
    return EXIT_OK


def cmd_sglc(args: argparse.Namespace) -> int:
    layout = _layout(args)
    catalog, bits, _lock = pipeline_mod.s0_bits_lock(layout)
    run_dir = layout.run_dir(args.run_id)
    result = pipeline_mod.s1_rules(layout, catalog, bits, run_dir)
    print(f"S1 rules: {len(result.table.rules)} rules compiled")
    print(f"   axiom predicates: {', '.join(result.table.axiom_predicates)}")
    _report(result.artifacts)
    return EXIT_OK


def cmd_gen(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    run_dir = layout.run_dir(args.run_id)
    stage = pipeline_mod.s2_gen(spec, args.seed, run_dir)
    print(
        f"S2 gen: {len(stage.result.raw)} simulated records, "
        f"{len(stage.result.truth)} truth annotations (never read again by this pipeline)"
    )
    _report(stage.artifacts)
    return EXIT_OK


def cmd_degrade(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    run_dir = layout.run_dir(args.run_id)
    generated = gen_mod.gen(spec, args.seed)
    stage = pipeline_mod.s3_degrade(
        generated.raw, args.completeness, args.degradation_seed, run_dir
    )
    print(
        f"S3 degrade: {len(stage.result.removed)} records deleted, "
        f"{len(stage.result.raw)} survive at "
        f"{stage.result.completeness.num}/{stage.result.completeness.den}"
    )
    _report(stage.artifacts)
    return EXIT_OK


def cmd_ingest(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    run_dir = layout.run_dir(args.run_id)
    raw = Path(args.raw) if args.raw else run_dir / "raw.jsonl"
    stage = pipeline_mod.s4_ingest(raw, spec, run_dir)
    print(
        f"S4 ingest: {len(stage.result.events)} sealed records, "
        f"{len(stage.result.quarantined)} quarantined"
    )
    _report(stage.artifacts)
    return EXIT_OK


def cmd_resolve(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    run_dir = layout.run_dir(args.run_id)
    from spectra_vs import ingest as ingest_mod

    bundle = ingest_mod.read_bundle(run_dir / "bundle.jsonl")
    stage = pipeline_mod.s5_resolve(bundle, spec, run_dir)
    print(
        f"S5 resolve: {len(stage.result.entities)} entities, "
        f"{len(stage.result.bindings)} bindings, "
        f"{len(stage.result.ambiguous)} ambiguous, "
        f"{len(stage.result.unresolved)} unresolved"
    )
    print(f"   {pipeline_mod.JOIN_RULES_NOTE}")
    _report(stage.artifacts)
    return EXIT_OK


def cmd_calibrate(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    config = _config(layout)
    stage = pipeline_mod.s6_calibrate(layout, spec, config, args.calibration_seed)
    print(f"S6 calibrate: profile_id {stage.profile.profile_id}")
    print(
        "   a model of a seeded generator's emission behaviour under one scenario family; "
        "it measures nothing about real telemetry"
    )
    for source in stage.profile.sources:
        regimes = ", ".join(f"{r.regime_id}:n_gaps={r.n_gaps}" for r in source.regimes)
        print(f"   {source.source_id}: {regimes or 'no regime reached a gap vector'}")
    _report(stage.artifacts)
    return EXIT_OK


def cmd_liveness(args: argparse.Namespace) -> int:
    layout = _layout(args)
    spec = _scenario(layout)
    config = _config(layout)
    run_dir = layout.run_dir(args.run_id)
    from spectra_vs import ingest as ingest_mod

    bundle = ingest_mod.read_bundle(run_dir / "bundle.jsonl")
    profile = None
    context = None
    if not args.no_profile:
        profile_path = layout.profiles_dir / f"{spec.family}.json"
        if not profile_path.exists():
            print(
                f"no profile at {profile_path}; run `calibrate` first or pass --no-profile",
                file=sys.stderr,
            )
            return EXIT_USAGE
        profile = calibrate_mod.load_profile(str(profile_path))
        context = liveness_mod.BindingContext(
            bundle_hash=canon.hash_ref("bundle", (run_dir / "bundle.jsonl").read_bytes()),
            seed=args.seed,
            generator_config_hash=spec.generator_config_hash(),
            scenario_family=spec.family,
            excluded_intervals_hash=calibrate_mod.excluded_intervals_hash(
                pipeline_mod._calibrate_excluded(spec)
            ),
        )
    stage = pipeline_mod.s7_liveness(
        spec, config, bundle, profile, context, run_dir, no_profile=args.no_profile
    )
    print(f"S7 liveness: mode_global {stage.document.mode_global}")
    for source in stage.document.sources:
        blind = sum(v for _r, v in source.blind_volume_ns_by_reason)
        print(
            f"   {source.source_id}: mode {source.mode}, {len(source.intervals)} merged "
            f"intervals, blind volume {blind} ns partitioned by reason"
        )
    _report(stage.artifacts)
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    layout = _layout(args)
    cell = pipeline_mod.run_cell(
        layout,
        completeness=args.completeness,
        seed=args.seed,
        degradation_seed=args.degradation_seed,
        calibration_seed=args.calibration_seed,
        verify=not args.no_verify,
    )
    print(_SCOPE_BANNER)
    print()
    print(f"run_id {cell.run_id}  ->  {cell.run_dir}")
    print(
        f"completeness {cell.completeness.num}/{cell.completeness.den}, "
        f"seed 0x{cell.seed:016x}, degradation seed 0x{cell.degradation_seed:016x}"
    )
    for complaint in cell.complaints:
        print(f"  SEAM: {complaint}")
    print()
    _report(cell.artifacts)
    if cell.verify_exit is not None:
        print()
        print(f"S11 verify exit {cell.verify_exit}")
        print(cell.verify_text)
        return EXIT_OK if cell.verify_exit == 0 else EXIT_FAIL
    return EXIT_OK


def cmd_stage_only(args: argparse.Namespace) -> int:
    """`ground`, `envelope` and `prove` share one body: they need the whole chain in memory.

    Re-reading `p_min.json` to run S9 would mean S9 trusted an artifact instead of the
    construction that produced it, and the containment `P_min` subset of `P_max` would
    become an assertion about two files rather than a property of one engine.
    """
    layout = _layout(args)
    if args.stage == "prove" and not (args.profile or args.no_profile):
        print(
            "prove requires exactly one of --profile or --no-profile.\n"
            "  --profile      use profiles/<family>.json, produced by a separate "
            "calibration run under a disjoint seed band\n"
            "  --no-profile   force F2: every window BLIND, premium structurally suppressed",
            file=sys.stderr,
        )
        return EXIT_USAGE
    cell = pipeline_mod.run_cell(
        layout,
        completeness=args.completeness,
        seed=args.seed,
        degradation_seed=args.degradation_seed,
        calibration_seed=args.calibration_seed,
        verify=False,
    )
    if args.stage == "ground":
        program = cell.ground.result.program
        print(
            f"S8 ground: {len(program.facts)} facts, {len(program.instances)} OBSERVED "
            f"instances, {cell.ground.result.iterations} iterations"
        )
        _report(cell.ground.artifacts)
    elif args.stage == "envelope":
        result = cell.envelope.result
        print(
            f"S9 envelope: {len(result.p_max.instances)} instances in P_max "
            f"({len(result.p_min.instances)} in P_min), {len(result.licences)} licences, "
            f"{len(result.blind_spots)} permanent blind spots"
        )
        print(
            "   P_max is a superset of realizable worlds: a tree drawn from it may combine "
            "silent instances no consistent world realizes"
        )
        _report(cell.envelope.artifacts)
    else:
        _print_cell_summary(cell)
        _report(cell.prove.artifacts)
    for complaint in cell.complaints:
        print(f"  SEAM: {complaint}")
    return EXIT_OK


def _print_cell_summary(cell: pipeline_mod.CellResult) -> None:
    from spectra_vs import cert as cert_mod

    prove = cell.prove
    print(f"S10 prove: run {cell.run_id}")
    print(f"   cut (over P_max): {_render_cut(prove.bracket.upper.cut)}")
    print(f"   {cert_mod.render_long(prove.verdict_at_cut_max, prove.scope)}")


def _render_cut(cut) -> str:
    if not cut.atoms:
        return "no control raised"
    raised: dict[str, int] = {}
    for atom in cut.atoms:
        key = str(atom.control_id)
        raised[key] = max(raised.get(key, 0), atom.level)
    return ", ".join(f"{name} >= {level}" for name, level in sorted(raised.items()))


def cmd_verify(args: argparse.Namespace) -> int:
    layout = _layout(args)
    cell = pipeline_mod.run_cell(
        layout,
        completeness=args.completeness,
        seed=args.seed,
        degradation_seed=args.degradation_seed,
        calibration_seed=args.calibration_seed,
        verify=True,
    )
    print(f"S11 verify exit {cell.verify_exit}")
    print(cell.verify_text)
    print()
    print(
        "The checker is a separate Python package that imports nothing from the emitter. "
        "That is module independence, not implementation independence: it shares an "
        "author, a language and a reading of the specification with the emitter, so a "
        "shared misreading is invisible to it. An ACCEPT establishes internal consistency "
        "with the hashed inputs and nothing else."
    )
    return EXIT_OK if cell.verify_exit == 0 else EXIT_FAIL


def cmd_demo(args: argparse.Namespace) -> int:
    from spectra_vs import demo as demo_mod

    return demo_mod.main(
        repo_root=Path(args.repo_root).resolve(),
        seed=args.seed,
        degradation_seed=args.degradation_seed,
        calibration_seed=args.calibration_seed,
        verify=not args.no_verify,
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _add_common(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """The options every subcommand accepts, added to the root parser and to each child.

    Added twice so that `run --completeness 7/10` and `--completeness 7/10 run` both work;
    a reader should not have to know which side of the subcommand an option lives on. The
    child copies default to SUPPRESS so that parsing the child does not overwrite a value
    the root already read.
    """
    parser.add_argument(
        "--repo-root",
        help="the repository root; every other path is derived from it",
        **(
            {"default": argparse.SUPPRESS}
            if suppress
            else {"default": str(Path(__file__).resolve().parents[4])}
        ),
    )
    parser.add_argument(
        "--run-id",
        help="the runs/<run_id> directory used by the single-stage subcommands",
        **({"default": argparse.SUPPRESS} if suppress else {"default": "manual"}),
    )
    parser.add_argument(
        "--seed",
        type=int,
        **(
            {"default": argparse.SUPPRESS}
            if suppress
            else {"default": pipeline_mod.DEFAULT_ANALYSIS_SEED}
        ),
    )
    parser.add_argument(
        "--degradation-seed",
        type=int,
        **(
            {"default": argparse.SUPPRESS}
            if suppress
            else {"default": pipeline_mod.DEFAULT_DEGRADATION_SEED}
        ),
    )
    parser.add_argument(
        "--calibration-seed",
        type=int,
        **(
            {"default": argparse.SUPPRESS}
            if suppress
            else {"default": pipeline_mod.DEFAULT_CALIBRATION_SEED}
        ),
    )
    parser.add_argument(
        "--completeness",
        type=_completeness,
        help="an exact rational such as 7/10; a decimal literal is rejected",
        **({"default": argparse.SUPPRESS} if suppress else {"default": _completeness("1/1")}),
    )
    parser.add_argument(
        "--raw",
        help="an explicit raw.jsonl for `ingest`",
        **({"default": argparse.SUPPRESS} if suppress else {"default": None}),
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="prove against profiles/<family>.json",
        **({"default": argparse.SUPPRESS} if suppress else {}),
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="force F2: every window BLIND and the premium structurally suppressed",
        **({"default": argparse.SUPPRESS} if suppress else {}),
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip S11, the separate checker",
        **({"default": argparse.SUPPRESS} if suppress else {}),
    )


_SUBCOMMANDS: tuple[tuple[str, str], ...] = (
    ("bits", "S0: load or create the append-only catalog-bits lock"),
    ("sglc", "S1: compile rules.toml and write the canonical encodings"),
    ("gen", "S2: emit the simulated raw stream and the truth stream"),
    ("degrade", "S3: delete-only degradation, nested across completeness levels"),
    ("ingest", "S4: seal the bundle and reject label leakage"),
    ("resolve", "S5: exact deterministic entity joins"),
    ("calibrate", "S6: a separate clean run under the calibration seed band"),
    ("liveness", "S7: classify every window; the only producer of licences"),
    ("ground", "S8: the observed fixpoint, OBSERVED instances only"),
    ("envelope", "S9: P_max = P_min + licensed silent instances + obligation GHOSTs"),
    ("prove", "S10: the two-sided bracket, the premium and the certificate"),
    ("verify", "S11: re-check a certificate with the separate checker package"),
    ("run", "S1..S11 for one completeness cell"),
    ("demo", "the two completeness cells, side by side"),
)

_HANDLERS = {
    "bits": cmd_bits,
    "sglc": cmd_sglc,
    "gen": cmd_gen,
    "degrade": cmd_degrade,
    "ingest": cmd_ingest,
    "resolve": cmd_resolve,
    "calibrate": cmd_calibrate,
    "liveness": cmd_liveness,
    "ground": cmd_stage_only,
    "envelope": cmd_stage_only,
    "prove": cmd_stage_only,
    "verify": cmd_verify,
    "run": cmd_run,
    "demo": cmd_demo,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectra_vs",
        description=_SCOPE_BANNER,
        epilog=(
            "Nothing this program prints is measured. A cut severs a chain IN THE MODEL, "
            "under this rule table, this control catalog and the telemetry actually "
            "ingested, against a non-adaptive attacker."
        ),
    )
    _add_common(parser, suppress=False)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in _SUBCOMMANDS:
        child = sub.add_parser(name, help=help_text, description=help_text)
        _add_common(child, suppress=True)
        child.set_defaults(handler=_HANDLERS[name])
        if name in ("ground", "envelope", "prove"):
            child.set_defaults(stage=name)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "stage", None) is None:
        args.stage = args.command
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
