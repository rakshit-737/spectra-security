"""One command, from the repository root:  python scripts/demo.py

This exists because `make` is not installed on this machine, so `make vs-demo` is not a
thing a reader can type. It does the sys.path wiring the workspace needs (no package here
is installed, there is no pip and no network) and then runs the two-cell demonstration.

    python scripts/demo.py                # both cells, then run the separate checker
    python scripts/demo.py --no-verify    # both cells, skip S11

SPECTRA-VS is a PYTHON REFERENCE IMPLEMENTATION. No Rust kernel, no Go checker, no C guard
VM and no Docker cyber range exists or is built by this script. The telemetry it analyses
is the output of a seeded synthetic generator and the attack inside it is simulated:
nothing it prints happened, and no number it prints is measured.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "python" / "spectra_core" / "src"))

from spectra_core.bootstrap import install  # noqa: E402

install(_REPO_ROOT)

from spectra_vs import demo as demo_mod  # noqa: E402
from spectra_vs import pipeline as pipeline_mod  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/demo.py",
        description=(
            "Run the SPECTRA vertical slice at two completeness levels with nested "
            "deletion sets and print the two cells side by side."
        ),
        epilog=(
            "The completeness levels, the seeds and the thresholds are fixed by the "
            "design and are not options, because a level chosen after seeing the answer "
            "is a fitted parameter."
        ),
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="skip S11, the separate checker"
    )
    parser.add_argument("--seed", type=int, default=pipeline_mod.DEFAULT_ANALYSIS_SEED)
    parser.add_argument(
        "--degradation-seed", type=int, default=pipeline_mod.DEFAULT_DEGRADATION_SEED
    )
    parser.add_argument(
        "--calibration-seed", type=int, default=pipeline_mod.DEFAULT_CALIBRATION_SEED
    )
    args = parser.parse_args(argv)
    return demo_mod.main(
        repo_root=_REPO_ROOT,
        seed=args.seed,
        degradation_seed=args.degradation_seed,
        calibration_seed=args.calibration_seed,
        verify=not args.no_verify,
    )


if __name__ == "__main__":
    raise SystemExit(main())
