#!/usr/bin/env python3
"""Assemble docs/prompt/SPECTRA_MASTER_PROMPT.md from the per-section sources.

The assembled document is generated output. Edit the section files under
docs/prompt/part1/ and docs/prompt/part2/ and re-run this; never edit the
assembled file directly.

Usage:
    python scripts/assemble-prompt.py            # write the assembled file
    python scripts/assemble-prompt.py --check    # exit 1 if it is out of date

--check is what a docs gate calls: it regenerates into memory and compares, so
a section edited without reassembly fails rather than silently drifting.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P1 = os.path.join(ROOT, "docs", "prompt", "part1")
P2 = os.path.join(ROOT, "docs", "prompt", "part2")
DST = os.path.join(ROOT, "docs", "prompt", "SPECTRA_MASTER_PROMPT.md")

HEADER = re.compile(r"^={60}\n(\d+)\.\s+(.+?)\n={60}$", re.M)

FRONT = """# SPECTRA — MASTER BUILD PROMPT

**Security State Reconstruction, Causal Analysis & Attack Replay**

Reconstruct the security state. Replay the attack. Prove the control.

> **GENERATED FILE.** Assembled from `part1/` and `part2/` by
> `scripts/assemble-prompt.py`. Edit the section sources, not this file.

---

## WHAT THIS DOCUMENT IS

This is the complete build specification for SPECTRA, written to be executed by an autonomous
coding agent. It is addressed to that agent in the imperative second person.

It is in two parts.

- **PART I (sections 0-56)** — the platform: operating contract, research frame, data and state
  models, temporal and causal engines, the proof kernel, the control-replay flagship, the local
  cyber range, the polyglot architecture, repository layout, API, CLI, database, frontend,
  verification, benchmarks and delivery.
- **PART II (sections 57-76)** — the hardening addendum, written after three independent critics
  found structural defects in Part I.

> **PART II OVERRIDES PART I WHEREVER THEY CONFLICT.**
> Every override is marked inline with a line beginning `OVERRIDES Part I:`.
> Read Part II before trusting any claim made in Part I.

## THE DEFECTS PART II EXISTS TO FIX

1. **Validation was circular.** Part I generated the concrete simulator and the proof kernel from
   one guard AST, then used their agreement as the correctness gate. Two artifacts generated from
   one source agreeing proves codegen works, not that either models an attack. Closed by section
   62, which introduces four independent oracles.
2. **Headline outputs were mathematically ill-defined.** The blindness premium was a set
   difference of non-unique minimum cuts; "residual reachability" was an unnamed magnitude in a
   project that bans invented scores; the redundancy index was called exact while computed over a
   cappable set. Closed by section 64.
3. **The honesty gates were one-sided.** "Zero false ROBUST" is passed by always returning UNSAFE.
   Closed by sections 62 and 66.
4. **Liveness was self-calibrating.** The blind-window test used a quantile computed from the
   run's own data, so deletion inflated the threshold that detects deletion. Closed by section 65.
5. **Scope was unbounded and evaluation was circular by construction.** Closed by sections 70,
   73, 74 and 75.

## RECONCILIATION STATUS

An audit compared every Part II section against its Part I counterparts and classified 453
disagreements: 100 already marked as overrides, 213 that contradicted Part I silently, and 140
that neither part settles. The silent class has since been marked inline; the unresolved class is
tracked in `docs/plan/DECISIONS.md`, each with a conservative default.

Consequence for a reader: an unmarked disagreement between the two parts may still exist. Part II
wins in every case.

## HOW TO USE IT

Paste `KICKOFF.md` into a fresh agent session in the repository root. It points the agent here.
Do not paste this whole document into a chat window — it is a repository artifact read from disk.

## THE LAWS THAT OVERRIDE EVERYTHING

1. The core is deterministic. Remove the LLM and the system still works, fully.
2. No fabricated numbers. Ever. Every figure in every document is produced by executing real code
   on real inputs, and is bound to the artifact that produced it.
3. Offline, seeded, byte-identical. Same inputs produce the same certificate hash on every machine.
4. A malformed record is quarantined with a reason code, never silently dropped — a silent drop
   manufactures a blind window, which manufactures a proof license, which turns a parser bug into
   an unsound proof.
5. A verdict is never rendered without its scope clause.
6. No stub on the demo path.
7. Any number written in this prompt that looks like a measurement is illustrative. It is not a
   target. Do not fit to it.

---

## TABLE OF CONTENTS

"""


def section_titles(path: str) -> list[tuple[int, str]]:
    text = open(path, encoding="utf-8").read()
    return [(int(n), t.strip()) for n, t in HEADER.findall(text)]


def build() -> str:
    p1 = sorted(glob.glob(os.path.join(P1, "*.md")))
    p2 = sorted(glob.glob(os.path.join(P2, "*.md")),
                key=lambda p: int(os.path.basename(p).split("-")[0]))
    if not p1 or not p2:
        sys.exit("no section sources found under docs/prompt/")

    toc: list[tuple[int, str, str]] = []
    for p in p1:
        toc += [(n, t, "I") for n, t in section_titles(p)]
    for p in p2:
        toc += [(n, t, "II") for n, t in section_titles(p)]
    toc.sort(key=lambda x: x[0])

    out = [FRONT]
    part = None
    for n, t, pt in toc:
        if pt != part:
            out.append(f"\n### PART {pt}\n\n")
            part = pt
        out.append(f"- **{n}.** {t}\n")
    out.append("\n---\n\n")

    out.append("# PART I — THE PLATFORM (SECTIONS 0-56)\n\n")
    for p in p1:
        out.append(open(p, encoding="utf-8").read().rstrip() + "\n\n")
    out.append("\n# PART II — HARDENING ADDENDUM (SECTIONS 57-76)\n\n")
    out.append("Part II overrides Part I wherever they conflict.\n\n")
    for p in p2:
        out.append(open(p, encoding="utf-8").read().rstrip() + "\n\n")
    return "".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the assembled file is out of date")
    args = ap.parse_args()

    built = build()
    if args.check:
        if not os.path.exists(DST):
            print(f"MISSING: {DST}", file=sys.stderr)
            return 1
        current = open(DST, encoding="utf-8").read()
        if current != built:
            print("OUT OF DATE: docs/prompt/SPECTRA_MASTER_PROMPT.md does not match its sources.",
                  file=sys.stderr)
            print("Run: python scripts/assemble-prompt.py", file=sys.stderr)
            return 1
        print("up to date")
        return 0

    with open(DST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(built)
    print(f"wrote {os.path.relpath(DST, ROOT)}: "
          f"{len(built)} chars, {built.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
