# SPECTRA build specification

The full build specification for SPECTRA lives here. It is written to be executed by an
autonomous coding agent, not read as prose documentation.

| File | What it is |
|---|---|
| `../../KICKOFF.md` | Paste this into a fresh Claude Code session. It points the agent here. |
| `SPECTRA_MASTER_PROMPT.md` | The assembled whole: sections 0-76, ~24.7k lines. |
| `part1/` | Sections 0-56, the platform, as 15 source files. |
| `part2/` | Sections 57-76, the hardening addendum, one file per section. |

**Part II overrides Part I wherever they conflict.** Every override is marked inline with a line
beginning `OVERRIDES Part I:`. Part II was written after three independent critics reviewed
Part I and found real structural defects in it: validation was circular, several headline outputs
were mathematically ill-defined, the honesty gates were one-sided, and the blind-window test was
self-calibrating. The front matter of `SPECTRA_MASTER_PROMPT.md` lists each defect and the section
that closes it.

Editing rules:

- Edit the per-section files under `part1/` and `part2/`, never the assembled file.
- Any number that appears in this specification is illustrative and is not a target. Do not fit
  implementation results to it.
