"""`python -m spectra_vs_verify <cert>.spcert --bundle ... --liveness ...`

Pure file in, file out. No network, no DNS, no database, no subprocess. Nothing is written
unless `--out` is given. There is no `--force`, no `--skip` and no `--ignore-hash-mismatch`;
adding one would be a review-blocking change, because the value of a checker that can be
told to ignore a mismatch is zero.

Exit codes: 0 ACCEPT, 1 REJECT with the reason code on stderr, 2 usage or I/O error.

The specification's seven-flag command line does not name a file for every digest the
certificate pins, so there is one option per digest instead. An option that is not supplied
is a usage error rather than a skipped obligation: a digest nobody recomputed is a digest
nobody checked.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spectra_vs_verify.checker import (
    ACCEPT,
    CHECKER_VERSION,
    INPUT_COVERAGE,
    USAGE,
    CheckerInputs,
    verify,
)

_OPTIONS: tuple[tuple[str, str], ...] = (
    ("rules", "rules.toml as authored; covers rules_text_hash"),
    ("rules-cae", "the canonical rule-encoding artifact; covers rules_hash"),
    ("guards", "guards.cae; covers guard_ast_hash"),
    ("controls-cae", "the canonical control-catalog encoding; covers controls_hash"),
    ("catalog-bits", "catalog-bits.lock; covers catalog_bits_hash and the atom table"),
    ("bundle", "bundle.jsonl; covers bundle_hash and every witness leaf"),
    ("liveness", "liveness.json; covers liveness_hash and every licence implication"),
    ("profile", "the source profile; covers profile_hash and gates B1 to B6"),
    ("goal-cae", "the canonical goal-library encoding; covers goal_hash"),
    ("er", "er.json; covers er_hash"),
    ("run-manifest", "run-side values for gates B4, B5 and B6"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectra_vs_verify",
        description=(
            f"Check a SPECTRA slice certificate (checker {CHECKER_VERSION}). Module "
            "independence only: this program shares an author, a language and a reading "
            "of the specification with the emitter, so a shared misreading is invisible "
            "to it and the certificate it accepts is not independently verified."
        ),
        epilog="; ".join(f"{name} covers {what}" for name, _d, _o, what in INPUT_COVERAGE),
    )
    parser.add_argument("certificate", type=Path, help="the .spcert file to check")
    for option, help_text in _OPTIONS:
        parser.add_argument(f"--{option}", type=Path, default=None, help=help_text)
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--out", type=Path, default=None, help="write the report here instead of stdout"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    inputs = CheckerInputs(
        **{
            option.replace("-", "_"): getattr(args, option.replace("-", "_"))
            for option, _help in _OPTIONS
        }
    )
    report = verify(args.certificate, inputs)
    text = (
        json.dumps(report.as_json(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if args.json
        else report.render()
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "wb") as handle:
            handle.write((text + "\n").encode("utf-8"))
    else:
        stream = sys.stdout if report.exit_code == ACCEPT else sys.stderr
        print(text, file=stream)
    if report.exit_code == USAGE:
        return USAGE
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
