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

The conflict audit compared each Part II section against its Part I counterparts and found 353
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
