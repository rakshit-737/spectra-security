"""The degradation matrix: one seed, several completeness levels, no prediction.

    python scripts/matrix.py                 # the default ladder, then write the artifact
    python scripts/matrix.py --levels 100,70 # a shorter ladder

WHY THIS IS NOT A PRE-REGISTERED CELL. The two registered cells vary ONE thing each - one
sensor over one window, one timestamp - and carry predictions committed before the code
that produces them. This does not: it sweeps random, delete-only degradation across a
ladder of completeness levels and reports what comes out. It is exploratory, it makes no
claim, and nothing here may be quoted as a result. `docs/research/preregistration.md` is
where a claim would have to be registered first.

WHAT THE LADDER IS. Levels are nested at one analysis seed: the deletion set at a lower
completeness is a superset of the deletion set at a higher one, which `degrade.degrade`
enforces rather than assumes. Nesting is what makes two rows comparable - without it each
row would be a different random experiment and a difference between rows would say
nothing.

WHAT A ROW DOES NOT SAY. Random deletion removes the attack's observed steps along with
everything else, so at low completeness neither program derives a goal and the premium
there is empty for a reason that has nothing to do with what a sensor could see
(`BUILD_LOG.md` INC-0007). A row with an empty premium is not evidence of blindness; it is
usually evidence that the goal vanished. The `goal` column is what separates the two.

NOTHING HERE IS MEASURED. The telemetry is the output of a seeded synthetic generator and
the attack in it is simulated. Every figure is a property of the model and its inputs.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_vs" / "src"))

from spectra_vs import degrade as degrade_mod  # noqa: E402
from spectra_vs import demo as demo_mod  # noqa: E402
from spectra_vs import pipeline as pipeline_mod  # noqa: E402
from spectra_vs import scf  # noqa: E402

#: The default ladder, in descending completeness. Fixed here rather than taken from the
#: command line by default, because a ladder chosen after seeing the answer is a fitted
#: parameter; the flag exists for a shorter run while developing, not for tuning.
DEFAULT_LEVELS: tuple[int, ...] = (100, 90, 80, 70, 60, 50)

_RULE = "=" * 96


def _coverage_permille(cell: pipeline_mod.CellResult) -> int:
    """LIVE share of source-time, in tenths of a percent, by integer arithmetic.

    Coverage rather than a count of LIVE intervals: intervals are run-length encoded, so
    deletion RAISES the count while lowering the share, and a count would read as
    degradation making the timeline more observed (INC-0011).
    """
    live = total = 0
    for source in cell.liveness.document.sources:
        for interval in source.intervals:
            span = interval.t1_ns - interval.t0_ns
            total += span
            if str(interval.verdict) == "LIVE":
                live += span
    return 0 if total == 0 else live * 1000 // total


def run_matrix(
    repo_root: pathlib.Path, levels: tuple[int, ...], *, verify: bool = False
) -> dict[str, object]:
    """Run the ladder and return the artifact. Rows are in the order they were run."""
    layout = pipeline_mod.Layout(repo_root=repo_root)
    from spectra_vs import liveness as liveness_mod
    from spectra_vs import scenario as scenario_mod

    spec = scenario_mod.load_scenario(layout.scenario_toml)
    config = liveness_mod.load_liveness_config(str(layout.liveness_toml))
    calibration = pipeline_mod.s6_calibrate(
        layout, spec, config, pipeline_mod.DEFAULT_CALIBRATION_SEED
    )

    rows: list[dict[str, object]] = []
    parent = None
    for level in levels:
        completeness = degrade_mod.Completeness.percent(level)
        cell = pipeline_mod.run_cell(
            layout,
            completeness=completeness,
            calibration=calibration,
            parent=parent,
            verify=verify,
        )
        parent = cell.degrade.result
        prove = cell.prove
        rows.append(
            {
                "completeness_percent": level,
                "deleted_records": len(cell.degrade.result.removed),
                "goal_derived": prove.goal_resolved,
                "licences": len(prove.licences),
                "live_permille": _coverage_permille(cell),
                "premium": sorted(str(c) for c in prove.premium.blindness_premium)
                if prove.premium.published
                else [],
                "premium_published": prove.premium.published,
                "psi_max": len(prove.bracket.upper.psi.corridors),
                "psi_min": len(prove.bracket.lower.psi.corridors),
                "run_id": cell.run_id,
                "sealed_records": len(cell.ingest.result.events),
            }
        )
    return {
        "claim": "none: this sweep is exploratory and no prediction was registered for it",
        "degradation": "random, delete-only, nested at one analysis seed",
        "rows": rows,
        "seed": pipeline_mod.DEFAULT_ANALYSIS_SEED,
        "telemetry": "seeded synthetic generator; the attack in it is simulated",
    }


def render(matrix: dict[str, object]) -> str:
    """The table, with the column that says whether a row means anything at all."""
    out = [
        _RULE,
        "THE DEGRADATION MATRIX -- exploratory, no prediction registered, nothing measured",
        _RULE,
        "  c%    sealed  deleted  LIVE%   licences  |Psi_min|  |Psi_max|  goal  premium",
    ]
    for row in matrix["rows"]:  # type: ignore[index]
        permille = int(row["live_permille"])
        premium = ", ".join(row["premium"]) or ("EMPTY" if row["premium_published"] else "ABSENT")
        out.append(
            f"  {row['completeness_percent']:>3}  {row['sealed_records']:>8}"
            f"  {row['deleted_records']:>7}  {permille // 10:>3}.{permille % 10}"
            f"  {row['licences']:>9}  {row['psi_min']:>9}  {row['psi_max']:>9}"
            f"  {'yes' if row['goal_derived'] else 'NO ':>4}  {premium}"
        )
    out.append("-" * 96)
    out.append(
        "  A row whose goal column reads NO says nothing about blindness: the deletion took "
        "the attack's observed"
    )
    out.append(
        "  steps with everything else, so neither program derives a goal and the premium is "
        "empty for a reason that"
    )
    out.append("  has nothing to do with what a sensor could see.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/matrix.py",
        description=(
            "Sweep random, delete-only degradation across a nested completeness ladder "
            "and write the exploratory artifact. Registers no claim."
        ),
    )
    parser.add_argument(
        "--levels",
        default=",".join(str(v) for v in DEFAULT_LEVELS),
        help="descending completeness percentages, comma separated",
    )
    parser.add_argument(
        "--verify", action="store_true", help="run S11 on each cell (slower)"
    )
    args = parser.parse_args(argv)
    levels = tuple(int(part) for part in args.levels.split(",") if part.strip())
    if sorted(levels, reverse=True) != list(levels):
        parser.error("levels must descend: the ladder is nested, and nesting has an order")

    matrix = run_matrix(_REPO_ROOT, levels, verify=args.verify)
    print(render(matrix), flush=True)
    path = _REPO_ROOT / demo_mod.RESULTS_DIR / "degradation-matrix.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    scf.write_scf(path, matrix, where="matrix")
    print(f"\nartifact  {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
