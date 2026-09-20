# BUILD LOG

Append-only. Newest entry at the bottom. History is never rewritten here.

Every increment gets an entry. An entry records what was planned, what was run, what the command
actually printed, and what was measured. A claim with no command output behind it does not belong
in this file.

Status values: `PLANNED` | `RED` | `GREEN` | `DONE` | `BLOCKED` | `REVERTED` | `DESCOPE`.

---

## INC-0001  session one: specification, plan and conflict audit

date: 2026-09-20
status: DONE
concern: single

### Goal

Execute session one as `KICKOFF.md` defines it: read the specification, produce a plan, surface
every Part I / Part II conflict, and stop for review before creating anything.

### What was produced

```
docs/prompt/part1/        sections 0-56, 15 files
docs/prompt/part2/        sections 57-76, 20 files
docs/prompt/SPECTRA_MASTER_PROMPT.md   assembled, 24,755 lines
KICKOFF.md
docs/plan/PLAN_v1.md
docs/plan/GLOSSARY_STUB.md
docs/plan/CONFLICTS.md
docs/plan/CONFLICTS_FULL.md
docs/plan/DECISIONS.md
```

### How the specification was read

Not end to end by one reader. Delegated agents each read assigned section files and returned
structured extractions. Sections 0-4, 30-34 and 52-56 of Part I were read in full, as were all
twenty sections of Part II. Part I sections 5-29 and 35-51 have so far been read only through the
conflict audit.

Consequence, recorded so it is not forgotten: **sections 17-29 must be read directly before M4
begins.** The KICKOFF checklist item "read the master prompt in full" is not satisfied and is not
claimed.

### Measured

Nothing was measured. No code exists.

### Findings

The conflict audit compared each Part II section against its Part I counterparts and found 453
disagreements:

| Class | Count |
|---|---:|
| RESOLVED — Part II overrides explicitly | 100 |
| SILENT — Part II contradicts without saying so | 213 |
| UNRESOLVED — neither part settles it | 140 |

The 213 silent contradictions are the dangerous class: an implementer working from a Part I section
builds the superseded behaviour and no test catches it. Two examples that would have caused real
damage — tick width moves from a configurable 1 ms quantum to a fixed 1 ns, and evidence leaves
change from `EventId` to `RecordId` across the kernel, the checker, the certificate schema and four
API endpoints.

Triage of the 140 unresolved conflicts by earliest blocking milestone:

| Blocks | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| M0 | 3 | 13 | 3 |
| M1 | 14 | 2 | 0 |
| M2 | 20 | 4 | 0 |
| M3 | 5 | 2 | 0 |
| M4-M7 | 44 | 16 | 2 |
| M8-M10 | 0 | 9 | 3 |

66 block M0-M3, of which 42 are HIGH.

### Notes and follow-ups

- The specification is not yet buildable as written. The next work item after the skeleton is a
  reconciliation pass, not implementation.
- The 213 silent contradictions should be pushed back into the Part II source files as explicit
  `OVERRIDES Part I:` lines. Tracked as a follow-up; not done in this increment.

---

## INC-0002  session one: decisions and repository creation

date: 2026-09-20
status: DONE
concern: single

### Human approval

The human approved proceeding past the plan checkpoint and answered two of the five outstanding
decisions directly:

- Repository name: `spectra-security`.
- Visibility: public from the first commit.

Approved in-session on 2026-09-20. What was approved: creating the repository, publishing it
publicly, and building the skeleton.

### Decisions taken

| # | Decision | Basis |
|---|---|---|
| 1 | Apache-2.0 licence | agent recommendation, not contradicted |
| 2 | Repository `spectra-security` | human |
| 3 | Public from the first commit | human |
| 4 | Module prefix `github.com/rakshit-737/spectra-security` | follows from 2 |
| 5 | Tier A package roots only this session | `KICKOFF.md` section 4 |

Decisions 4, 5 and 6 of `docs/plan/PLAN_v1.md` section 9 remain open. Building proceeds on the
conservative defaults recorded in `docs/plan/DECISIONS.md`. A default is not an answer; it is a
recorded assumption.

### Commands run

```
$ git init -b main
Initialized empty Git repository in D:/Academics/spectra/.git/

$ gh repo create rakshit-737/spectra-security --public --source=. --remote=origin --push
https://github.com/rakshit-737/spectra-security
 * [new branch]      HEAD -> main
branch 'main' set up to track 'origin/main'.
```

### Notes

Commit granularity for the skeleton is one file per commit, at the human's explicit request. The
increment protocol in section 0 of the specification already requires one concern per commit; a
single skeleton file is one concern, so the two are compatible.

---

## INC-0003  fix: dotfiles committed without their leading dot

date: 2026-09-20
status: DONE
concern: single

### What went wrong

The script that committed the skeleton normalised each authored path with
`path.lstrip("./")`. `str.lstrip` strips a CHARACTER SET, not a prefix, so every leading dot was
removed along with any leading slash. `.gitignore` was written and committed as `gitignore`,
`.github/workflows/t1.yml` as `github/workflows/t1.yml`, and so on for seven paths.

The fault was not visible in the commit output, which reported success for every file, and not
visible in a filesystem existence check, because the authoring agents had also written the correct
dotted files to disk themselves. The repository therefore held both: a tracked `gitignore` with no
effect, and an untracked `.gitignore` that git never saw.

A second, unrelated fault surfaced in the same investigation: the CI authoring agent wrote nine
files to disk but returned only one in its result array, so eight `.github/` files and
`.pre-commit-config.yaml` were never committed at all.

### How it was found

`git status` showed `.gitignore`, `.gitattributes`, `.github/` and others as untracked while the
commit log claimed they had been added. `git cat-file -e HEAD:.gitignore` failed for all seven.

### Fix

Forward-only, because the bad commits were already pushed. Five dotless files had byte-identical
dotted copies on disk and were replaced. `npmrc` and `devcontainer/` had no dotted copy and were
renamed with `git mv`. The nine never-committed files were added. `.opencode/` was added to
`.gitignore`.

### Lesson recorded

Two checks were reported as passing that did not prove what they appeared to prove:

- a commit loop reporting success per file proves the commit command returned zero, not that the
  intended path was committed;
- a filesystem existence check proves a file exists, not that git tracks it.

Any future tooling that writes files and commits them must verify with `git cat-file -e HEAD:<path>`
for the exact intended path, and the skeleton gate must assert that the working tree is clean with
no unexpected untracked files.

---

## INC-0004  reconciliation: mark the silent Part I / Part II contradictions

date: 2026-09-20
status: DONE
concern: single

### Goal

Close the SILENT class from INC-0001. 213 places where Part II contradicts Part I without marking
it, so an implementer reading a Part I section builds the superseded behaviour and no test catches
it.

### Method

Twenty agents, one per Part II section, each given its own findings and permitted to edit only its
own file. Each was instructed to insert an explicit `OVERRIDES Part I section <N>:` line adjacent
to the passage carrying the new behaviour, and to REJECT any finding where the audit had misread
one of the two parts -- a false override line instructs an implementer to change correct behaviour,
which is worse than a missing one.

### Result

230 override lines applied, 5 findings rejected as not real, 2 unplaceable.

230 exceeds 213 because several contradictions have two carrier passages and a reader of either
alone needs the marker. Section 67 took 16 lines for 12 findings, section 58 nine for eight.

### Measured

Nothing was measured. No code exists.

### Follow-up

The override lines have been sampled for correctness against the Part I text they cite. Result
recorded in INC-0005.

---

## INC-0005  self-audit of the skeleton, and two fix rounds

date: 2026-09-20
status: DONE
concern: single

### Goal

Check whether the committed skeleton actually obeys the honesty rules it declares about itself,
rather than assuming it does because it says it does.

### Round one

Six auditors over the Makefile, the CI workflows and gate registry, the claims documents, the
language surface, the source files and the planning layer. 47 findings, 9 HIGH.

The most serious was not a documentation error. Backticks inside `$(call todo,...)` descriptions
are live command substitution, because the macro passes its arguments through a double-quoted
shell word. `make core` therefore FORKED AND RAN `make build-offline` and `make -C /w core` before
printing its not-implemented message, and printed a sentence that was not the text in the file.
The auditor proved it by putting a stub `make` on PATH and catching the invocation.

Notable non-findings: 61 targets were enumerated mechanically -- 4 do real work, 57 exit non-zero
through a shared macro whose exit path is readonly, and ZERO silently succeed. Rule 5 was clean:
no committed source file contains logic that could be mistaken for an implementation.

44 of 47 fixed. Two findings landed in merged ADRs and were correctly refused: a merged record is
immutable except its Status line, so those corrections became ADR-0011 and ADR-0012.

### Round two: the fixes were verified, not trusted

Re-audited. 40 of 45 findings genuinely FIXED, 3 WRONGLY_FIXED, 2 NOT_FIXED -- and **31 new
findings introduced by the fixes themselves**.

### The finding that matters

Manual honesty auditing does not converge.

One edit -- correcting the T0 header in `ci/gates.toml` from "0 implemented" to "1 implemented" --
left four files asserting three different counts: the registry's own STATUS block, the README
status line, the README tier table, and a comment in `t1.yml`. Each was individually true when
written. Nothing mechanically relates them, so a fix in one place silently falsifies three others.

The same shape produced most of the 31: a fact changed in its owning file while other files kept
stating the old one. The first round fixed 44 findings and created 31; severity fell from 9 HIGH
to 3 HIGH, so it is converging, but slowly and by hand.

This is the argument for the claims gate described in `CLAIMS.md`, which is not implemented. Until
a machine checks that every path referenced exists, every make target named is declared, and every
count matches the artifact named in the same sentence, this class of error is found by reading --
which is how four files came to disagree about a number in the first place.

### Errors made by the agent running this session, recorded

Four claims of verification were made ahead of the evidence:

1. "Verified: every key file exists" -- the check tested the FILESYSTEM, not git. Seven dotfiles
   were untracked. See INC-0003.
2. "Verified: every .PHONY name has a rule" -- the parser matched ZERO .PHONY names, so it
   verified nothing. Caught only because the printed number looked wrong.
3. "Verified: no record's status disagrees" -- asserted before the check returned; the check then
   reported a mismatch. It was a false positive, but the claim preceded the evidence.
4. A conflict total of 353 was quoted in four files and in every report to the human for several
   hours. The correct total is 453. Corrected in ADR-0010.

All four are the same failure: a check that returns success without testing what it claims to
test. The skeleton gate must assert a clean working tree and verify by `git cat-file -e HEAD:<path>`
rather than by filesystem existence.

---
