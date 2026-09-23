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

## INC-0006  the reference slice: foundation layer

date: 2026-09-21
status: DONE
concern: single

### Goal

Build the layer every pipeline stage imports: identifiers, canonical byte encoding, the record
types the stages exchange, the error taxonomy, and the workspace path bootstrap.

### Context that changed the plan

This machine has Python 3.14, Node 24 and Java 25, and no Rust, Go, Docker, make or WSL
distribution. ADR-0013 records the consequence: the slice is a Python reference implementation and
nothing may claim the Rust kernel or Go checker exists.

### Commands run

```
$ python python/spectra_core/tests/test_core.py
Ran 113 tests in 0.840s
OK
```

### Measured

113 tests pass. No other number is measured; nothing has been benchmarked.

### The hash substitution

The specification names BLAKE3. The standard library does not provide it and there is no pip here.
The implementation computes blake2b-256 and labels it `b2b256:` rather than `blake3:`, carries the
algorithm into every certificate, and rejects any other algorithm label when parsing. A digest that
claimed to be BLAKE3 and was not would verify against nothing while appearing to verify.

### ERROR MADE IN THIS INCREMENT, recorded because the history is now wrong

Commit b14d36f is titled `fix: normalise CLAIMS.md to LF`. It also added
`python/spectra_core/src/spectra_core/canon.py`, `ids.py` and `errors.py` - roughly 58 KB of
foundation code that a subagent had just written to disk.

Cause: that commit staged with `git add -A` while a subagent was mid-write in another directory.
The message describes one concern; the commit contains two, and the second is not mentioned.

It cannot be repaired. Both that commit and the one after it are pushed, and rewriting published
history to fix a commit message is a worse trade than carrying the error. The three files show
`git log --diff-filter=A` attribution to a line-endings fix, and anyone bisecting for the origin of
the canonical encoder will land on the wrong commit.

Rule adopted: **never `git add -A` or `git add .` in this repository.** Stage explicit paths. The
one-concern-per-commit rule in section 0 of the specification is not enforceable by intention while
background agents are writing files; it is only enforceable by naming the paths.

This is the fifth verification-shaped failure recorded in this log. The others are in INC-0003 and
INC-0005. All five share a shape: an action that appeared to do exactly what was intended, with
nothing checking that it had.

---

## INC-0007  the slice runs end to end, and the experiment fails

date: 2026-09-21
status: DONE
concern: single

### Goal

Wire the eleven stages into a runnable pipeline and run the two-cell demonstration: the blindness
premium at full telemetry, where it should be EMPTY, against the premium at a degraded cell, where
it should name a control required only because a sensor could not see.

### What was built

`pipeline.py` threading S1 to S11, a CLI at `python -m spectra_vs`, `demo.py`, and a make-free
entry point at `scripts/demo.py`. Two seams found by running the pipeline rather than by reading
it, one in grounding and one in the checker.

### Commands run

```
$ python scripts/demo.py
[exited with code 0]

$ for t in <17 suites>; do python "$t"; done
17 suites passing, 0 failing        (860 tests)
```

The pipeline executes end to end. The checker returns ACCEPT on both certificates, with every
obligation O0 to O15 satisfied.

### THE RESULT: the experiment does not demonstrate what it was designed to demonstrate

```
full telemetry   |Psi_min|=0 |Psi_max|=1  licences=5   premium=ctl:priv_approval
degraded cell    |Psi_min|=0 |Psi_max|=0  licences=94  premium=EMPTY
```

The control arm is not clean. The premium at FULL telemetry is already non-empty, so it is not
evidence about degradation, and the degraded cell has nothing to be contrasted against. Worse, the
premium LOST its member under degradation, which is the opposite of the predicted direction.

Nothing was adjusted afterwards. The scenario, the seeds, the thresholds and the two completeness
levels are as they were when the run was launched.

### Why, read off the artifacts

1. **No source is LIVE in either cell, so blindness is total at every completeness level.** With
   `m_min = 3` and a breakpoint at every record instant, an elementary interval brackets exactly
   two records, so the rule `n_records_in_span < m_min -> BLIND` fires on every interval and the
   only construction site of LIVE is unreachable. `config/vs/liveness.toml` states this
   contradiction in its own comment and ships the value anyway. A full-telemetry cell in which
   every source is blind cannot be a control arm for blindness.

2. **Psi_min is empty in both cells**, so the premium degenerates to the whole of NEC(Psi_max) and
   cannot distinguish a control needed because of blindness from a control needed at all. The
   observed route never fires: rule r0003 requires three distinct resources read inside ten
   minutes and the scenario emits exactly one `res_read`.

3. **At the degraded cell the goal library is empty.** The delete-only degrader removes whole
   twenty-minute outage blocks, and the block holding the escalation route's observed leaf went
   with it. Degradation removed the route rather than licensing it, so the empty premium there has
   nothing to do with what a sensor could see.

4. **The one premium member rests 7198/7199 on calibration-deficiency licences.** The sentence the
   artifact supports is "needed because this run was not calibrated for this source", not "needed
   because a sensor could not see".

### What this is worth

The instrument is broken, not the idea. Three of the four causes are configuration contradictions
in files authored against each other in parallel - a threshold whose own comment says it is wrong,
a rule needing three events from a scenario that emits one, a degrader whose block size is larger
than the route it is meant to perforate.

The part that worked is the part that matters: the system reported its own failure precisely,
attributed the premium to calibration deficiency rather than to blindness, and refused to describe
a bundle whose sources were all undersampled as anything other than blind. The fail-closed
direction held under a case where failing open would have produced a much prettier result.

A premium that appeared only after tuning the scenario would have been worthless. This one did not
appear, and that is a more useful thing to have in the log.

### Follow-up

Repair the instrument, then re-run ONCE and report whatever it says. The repairs are to the
experimental setup and not to the engine: `m_min` against its own documented contradiction, the
scenario's resource count so the observed route can fire at all, and the degradation block
granularity. Fixing a broken instrument is legitimate; iterating on it until the answer is pretty
is not, and the difference is that the repairs are justified by the artifacts above rather than by
the result they produce.

### ERROR MADE IN THIS INCREMENT, recorded because the history is wrong again

Commit f20746c is titled `fix: normalise the runner modules to LF`. It also contains the two
substantive seam fixes - nine changed lines in `ground.py` and twenty-nine in `checker.py`.

Cause: the commit staged with `git add -- $(git diff --name-only)`. That is a glob over every
modified file, which is `git add -A` wearing a different shape, one commit after INC-0006 adopted
the rule against it.

`git log --diff-filter=M` on `ground.py` now attributes its only post-creation change to a
line-endings fix. It is pushed and will not be rewritten.

Rule restated, since the first statement of it was too narrow to bind: **stage only paths written
out literally in the command.** Not `-A`, not `.`, not a glob, not a command substitution, not a
variable. If the path is not visible in the commit invocation, it is not staged.

This is the sixth verification-shaped failure in this log, and the second of exactly this kind.

---

## INC-0008  repairing the instrument, and what the control arm actually shows

date: 2026-09-21
status: DONE
concern: single

### Goal

INC-0007 found the two-cell demonstration did not show what it was designed to show, and read four
causes off the artifacts. Repair the instrument where the cause was a defect, run once, and report.

### Repairs made, each justified by an artifact and not by the result it would produce

1. **`m_min` 3 -> 2.** The breakpoint grid places a breakpoint at every record instant, so an
   elementary interval brackets exactly two records; 3 made LIVE unconstructible. 2 is the largest
   value the grid admits.
2. **The bulk read made bulk.** Rule r0003 heads the goal and needs three distinct resources within
   ten minutes; the scenario read one. The scenario was changed to match its own description, not
   the rule weakened to match the scenario - lowering r0003's `n` to 1 would have run and would
   have been fitting.
3. **Goal derivability over the whole goal library** (kernel bug, see below).
4. **Over-deep witnesses refused rather than fatal** (see below).
5. **Two diagnostic lines stopped asserting causes they never checked**, and the LIVE metric
   changed from a window count to coverage.

### Kernel bug: a false severance

With route A now able to fire, P_min held one derived goal fact while Psi_min held zero corridors
with `complete=True`. That combination is a contradiction.

Cause: reachability decided derivability over ONE goal key, the bytewise-least member of the goal
library, which is the union of goal facts either program derives. At full telemetry that key was a
fact only P_max derives. The corridor search over P_min asked about a fact P_min cannot reach,
found it unreachable under the empty cut, and reported that the empty cut severs the attack -
while P_min derived the other goal fact through route A.

`docs/vocab.toml` already defined the goal as a set. The code did not follow it. Fixed: any member
derivable means the objective is reached; a cut severs only when every member is underivable. Five
regression tests, written and seen failing before the fix.

It never became a false safety verdict, because the certificate re-checks every goal: it listed
route A's fact as `derivable: True` and the verdict came out OPTIMISTIC_ONLY. The false claim stayed
inside the cut, Psi_min and the premium.

### Consequence of that fix: the first real witness, and a contract limit

Route A becoming derivable produced the first multi-step witness tree to reach the emitter. The
certificate contract caps nesting at 8 containers, which admits a root and one level of children;
route A is three levels. `cert.emit` refused it and the refusal aborted the whole run. Now the
pipeline measures depth first and drops the one witness through the existing reported path.

Recorded, not fixed: **under this contract no real multi-step attack can ever carry a published
witness.** Nested encoding makes certificate depth grow with proof length. The fix is a flat
encoding (nodes plus parent indices). It is a contract change on the emitter AND the checker and
needs its own ADR.

### Commands run

```
$ python scripts/demo.py
full telemetry   |Psi_min|=1 |Psi_max|=2  licences=3   premium=ctl:priv_approval
degraded cell    |Psi_min|=0 |Psi_max|=0  licences=54  premium=EMPTY

LIVE share of source-time:  c=100% 83.1%   c=70% 56.1%

$ <every suite>
18 suites passing, 0 failing
```

Psi_min went from 0 to 1 at full telemetry. The control arm is still not clean.

### The finding: full telemetry is not zero blindness

Four hypotheses were tested against the artifacts for why the premium is non-empty at full
telemetry. Three were wrong, and each was checked before anything was changed:

- "More LIVE windows at 70% than at 100%, so liveness is broken." Wrong. The metric counted
  windows; coverage falls from 83.1% to 56.1% as it should.
- "Step k7 carries no `role`, so the escalation cannot bind." Wrong. The pipeline binds `role` from
  `credential`, and entity resolution produced the binding correctly.
- "The escalation rule is broken." Wrong. Its absence guard sees the real approval at +4499 s and
  correctly refuses to fire in P_min.

The fourth held. **All 80 licensed escalations in P_max sit in the first 10 s or the last 10 s of
the horizon; none in the middle.**

A finite observation window is always blind at its edges: liveness cannot be proved before the
first record or after the last. r0004's absence lookback is 72 h against a 2 h horizon - 36 times
longer - so for an escalation in the leading edge almost the whole lookback lies before observation
began and the absence can never be falsified. The envelope therefore correctly admits that some
principal escalated in the unobservable first second, route B becomes derivable in P_max, and
`ctl:priv_approval` lands in the premium. **Correctly**: it genuinely is needed only on account of
blindness. The blindness is the edge of the window.

The design assumption that failed is that full telemetry means zero blindness. It never does.

### Decision left open, deliberately

Making the control arm clean needs a methodology choice, and that choice determines the result:

- a burn-in period so the horizon begins at least one lookback before the attack window;
- bounding absence lookbacks to the observed horizon, and recording the truncation;
- or treating edge windows as out of scope and saying so in every certificate.

None was made. Choosing one after seeing which produces a clean control arm is fitting, and this
log exists to make that visible. It is recorded in `docs/plan/DECISIONS.md` for a human decision.

### The pattern across this increment

Each fix exposed the next layer. The goal-set bug was invisible until the scenario fix let route A
fire; the witness limit was invisible until the goal-set fix made route A derivable. Earlier runs
were failing early enough that most of the kernel never executed. A green suite of 860 unit tests
said nothing about that, because every module had only ever been exercised in isolation.

---

## INC-0009  CI had been running all along; the reference suites now run there too

date: 2026-09-21
status: DONE
concern: single

### What was believed, and what was true

This log, ADR-0013 and `docs/plan/PLAN_v1.md` all recorded that `make` had never run in this
repository, that every claim about the Makefile was therefore unverified, and that M0 could not
close. The development machine has no `make`, and that was generalised to the repository without
checking the remote.

The T1 workflow had been running `make skeleton-verify` on a GitHub `ubuntu-24.04` runner on every
push since its first commit - roughly thirty times by then. Its history:

| Runs | Conclusion | What they reported |
|---|---|---|
| first 11 | failure | `skeleton-verify: 11 required path(s) missing`, naming them |
| the rest | success | every required path present |

The eleven paths named in the first failing run are exactly the eleven later found missing by hand
on the development machine, without reference to CI. The gate failed honestly, named the precise
gap, and passed once it was closed - on a machine this session did not control. Nobody looked.

Corrected in `docs/plan/PLAN_v1.md` in place, and by ADR-0014 superseding ADR-0013, which is
immutable. M0 is not blocked by the missing local `make`; it is blocked because `m0-verify` is not
implemented.

Rule adopted: **a claim about what has or has not run in this repository is checked against CI
before it is written.** `gh run list` answers it in one command.

### The reference suites as a CI gate

With CI established as a place `make` runs, the suites stopped needing to be a claim made from one
machine. Added:

- `make test-reference`, which runs every suite and fails if any fails;
- gate `G-PYREF-001`, tier T1, registered in `ci/gates.toml`;
- a `reference` job in `.github/workflows/t1.yml`, using the runner's system `python3`.

The job deliberately uses Python 3.12, the version the workspace pins, rather than the 3.14 the
slice was written and run on. That made its first run the first test of whether the code runs on
the interpreter the repository declares.

### First run: red, and correctly so

```
interpreter: Python 3.12.3
  ... 17 ok ...
  FAIL  python/spectra_vs_verify/tests/test_verify.py
        AssertionError: 1 != 0 : /usr/bin/python3: No module named spectra_vs_verify
suites: 17 passing, 1 failing
```

The failing test launches the checker as a subprocess and built its `PYTHONPATH` with `";"`, the
Windows path separator. On Linux the child saw one nonexistent directory named `<a>;<b>`. The test
passed on the Windows machine it was written on and failed on the first clean Linux runner. Fixed
with `os.pathsep`; no other hardcoded separator exists in the test tree.

### Second run: green

```
T1 skeleton / G-SKELETON-001 | success
T1 reference / G-PYREF-001   | success
interpreter: Python 3.12.3
suites: 18 passing, 0 failing
```

### Measured

18 suites pass on Python 3.12.3 on `ubuntu-24.04`, in CI, run `35609317811`. That is the first
result in this repository produced by a machine other than the one the code was written on.

### Two version claims corrected on evidence

- `spectra_vs` declared `requires-python >=3.14`, because that was the installed interpreter. CI
  disproves the need. Now `>=3.12`.
- The README said the slice needs "Python 3.11 or later". Three modules use PEP 695 type parameter
  lists, which do not parse before 3.12. Now 3.12. That line was written in this session without
  being checked.

### The cascade, measured on one change

Registering one gate required updating eight statements across five files that each state how many
gates are implemented: the registry's STATUS block, its T1 header, its row count, a NOTE calling the
skeleton gate the only one in CI, the README, `CONTRIBUTORS.md`, the plan, and a comment in
`t1.yml`. All eight were changed together and a grep confirms none is stale. INC-0005 argued these
counts should be generated rather than written; this is that argument with a number on it.

### Heredoc escaping, third occurrence

Makefile content written through a bash heredoc lost its line continuations and had its `\n`
escapes turned into real newlines - the third time this session. Makefile and other
backslash-bearing content is now written with the file-writing tool, which writes exact bytes, and
spliced in. A structural check (every recipe line tab-indented and continued, balanced quotes,
rule/phony parity) runs after every such edit.

---

## INC-0010  the control arm is clean, and INC-0008's diagnosis was wrong

date: 2026-09-21
status: DONE
concern: single

### What INC-0008 concluded, and why it was wrong

INC-0008 recorded, as its central finding, that the non-empty blindness premium at full telemetry
was genuine: that a finite observation window is always blind at its edges, that r0004's 72-hour
absence lookback can never be falsified for an escalation in the first second, and therefore that
`ctl:priv_approval` really was needed only on account of blindness. It opened decision D-RUN-01 to
choose how to handle the edges.

That diagnosis stopped one step short. It established WHERE the licensed escalations were - all 80
in the first or last 10 s - and inferred that they reached the goal. It did not check whether they
could. They cannot: route B completes through rule r0005, which requires the escalation to precede
the export by at most 30 minutes, and the only export is at +4560 s. An escalation in the first
second is 76 minutes early; one in the last second comes after the export.

Reading P_max directly showed ten r0005 instances pairing exactly those impossible times. The rule's
time bound was not being applied.

### Cause

`ground.Engine._check_seq` returned success without comparing anything whenever either side was a
licensed fact, on the documented grounds that a licensed fact's tick is only a representative of a
blind window. The reasoning about precision was right; the remedy of skipping was too coarse, and
admitted combinations impossible for every placement of the unobserved step.

### Fix

`seq` now asks whether SOME time in each side's range satisfies `left < right <= left + within`
(`ground.seq_feasible`). An observed fact's range is a single point, reproducing the old behaviour
exactly; a licensed fact's range is the hull of the blind windows that licensed it, which the
envelope now hands to the engine. P_max stays a superset of every realizable world. Eight
regression tests were written and seen failing first.

`absence` and `distinct` still skip the comparison for a licensed fact - still sound, coarser than
necessary, recorded in the envelope's docstring.

### Commands run

```
$ <every suite>
18 suites passing, 0 failing

$ python scripts/demo.py
full telemetry   |Psi_min|=1 |Psi_max|=1  premium=EMPTY
degraded cell    |Psi_min|=0 |Psi_max|=0  premium=EMPTY
```

### Measured

The full-telemetry premium is empty. That is the control arm behaving as the design requires, and
it is the first time any run has shown it. D-RUN-01 is withdrawn: no methodology choice was needed.

### What is still not demonstrated

The degraded cell's premium is also empty, and that means nothing: its random deletion removes the
attack's observed steps outright, so neither program derives a goal. A controlled replacement - a
whole-source blackout of iam_audit over a window chosen from the scenario definition - is
pre-registered in `docs/research/prereg-0001-blackout-cell.md`, with quantitative predictions and
falsifiers, BEFORE it is implemented or run.

### The record of wrong explanations

INC-0008 tested four hypotheses for the non-empty premium and reported the fourth as correct. It
was the fifth that held. Each of the four was checked against an artifact before being accepted or
rejected; the fourth was accepted on an artifact that showed where the licensed steps were without
showing whether they could reach the goal. The general form of the mistake: confirming a mechanism
exists, and taking that as proof it is the one producing the effect. INC-0008 is left as written,
and D-RUN-01 is withdrawn with its original text kept beneath the notice, so the error stays
readable.

---

## INC-0011  pre-registration 0001 held; its named confound was never testable

date: 2026-09-21
status: DONE
concern: single

### What was run

The blackout cell registered in `ce8ed9c` - a whole-source blackout of `src:iam_audit` over
`[+4200 s, +4800 s)`, everything else as in the control arm - was built in the four commits that
follow the registration and run through the demo, which evaluates the five falsifiers mechanically.

### Commands run

```
$ python scripts/demo.py
full telemetry   |Psi_min|=1 |Psi_max|=1  r_min=1 r_max=1  licences=3  premium=EMPTY
blackout cell    |Psi_min|=1 |Psi_max|=2  r_min=1 r_max=2  licences=4  premium=ctl:priv_approval
PASS  premium published
PASS  premium non-empty
PASS  premium == ('ctl:priv_approval',)
PASS  |Psi_min| == 1
PASS  |Psi_max| == 2
PREDICTION HELD.
```

### Measured

All five falsifiers passed. The blackout produced a SUPPRESSED licence, `S_CHAIN_SEQ_GAP`, on
`src:iam_audit` over the 10 minutes bracketing the window, which is the mechanism the registration
named. S11 accepted the certificate. The demo was run three times on this machine; four artifacts in
each of the two cells were byte-identical every time. The full record, with hashes, is
`docs/research/prereg-0001-result.md`. The registration itself is unedited.

### The confound that could not fire

The registration named one confound: a chained source with records missing may be marked
`tamper_suspected`, which would block ROBUST. No flag was set, and a ROBUST verdict was printed for
the cut over P_max.

That is not a finding. `liveness.TAMPER_PASS_IMPLEMENTED` is `False`; the pass that would set the
flag does not exist, and the liveness types refuse a true value. The confound was named without
checking whether the code could produce it. Two things followed from noticing:

- The demo printed "FLAGS SET none" and a ROBUST verdict with no caveat, which is exactly what the
  liveness module says no rendering may do: present an absent check as a clean result. Both now
  carry the caveat.
- The pipeline minted the no-tamper token from literals - an empty tuple and `False` - instead of
  reading the liveness document. Identical today, since nothing can be flagged; silently wrong the
  day the pass exists. It now reads the document, and `test_pipeline_verdict.py` pins which object
  it consults.

### Also found while reading the output

The demo's list of findings used fixed numbers, so withdrawing finding 2 in INC-0010 had left it
reading "1, 3". It printed `c=100%=83.1%` and referred to "the degraded cell" when there are now two.
Fixed.

### What this result does not show

It is a prediction about the author's own code, made just after tracing this mechanism in INC-0010,
with a window chosen from the scenario definition. It tests the implementation against the author's
understanding, not the understanding itself. It is one scenario, one seed and one window of
simulated telemetry, and it is not a pre-registration under `docs/research/preregistration.md`,
whose protocol required the registration to precede every rule. The certificate carries no witness
tree for `ctl:priv_approval` (D-RUN-02).

---

## INC-0012  the result reproduces on Linux, and certificates carry their witnesses

date: 2026-09-21
status: DONE
concern: single

### The gate's first run

G-VS-PREREG-0001 (`make vs-prereg-0001`) ran on GitHub's ubuntu-24.04 runner under CPython 3.12.3.
The prediction held there, with all five falsifiers passing. The job still failed, and it was right
to: the S11 checker could not start.

```
S11 checker       exit 1 (REJECT)
  | /usr/bin/python3: No module named spectra_vs_verify
```

The pipeline joined the checker's PYTHONPATH with a literal `;`, the Windows separator. On Linux that
names one nonexistent directory. `test_verify.py` had the same defect and was fixed in INC-0009; this
copy was missed. Fixed in `b6f0463` with `os.pathsep` and a test that runs on whichever platform CI
uses. The next run was green, with the gate taking about 70 seconds.

### Measured: the same bytes on two platforms

The gate prints the sha256 of four artifacts per cell. All twelve from the CI run matched the
development machine's byte for byte:

| | Development machine | CI |
| --- | --- | --- |
| OS | Windows 11 | Ubuntu 24.04 |
| Interpreter | CPython 3.14 | CPython 3.12.3 |
| run ids | `vs-0049b1adfb705cb3`, `vs-8c9a9bf854d401bf`, `vs-02830d35a09ad406` | the same |
| 12 artifact hashes | recorded in `docs/research/prereg-0001-result.md` | identical |

That is two platforms and two interpreter versions, for these twelve files at one commit. It is not a
claim about any other artifact, platform or commit.

### D-RUN-02 closed: witnesses are published

ADR-0015 publishes witness trees flat, as a pre-order node list with children as indices, and adds
a LICENSED node kind for a licensed silent step that is not obligation-forced. Schema, min_checker
and the checker move to 1.1 together. The pipeline's two refusals, one for depth (INC-0008) and one
for licensed steps, are gone.

### What publishing them exposed

The first real witness to reach the checker was rejected:

```
FAIL O12: ev:0193e789a4573faada6d70411fe62fb3 does not recompute from the bundled record  [E-WITNESS-EVENT]
```

A bundle line spells `source_id` bare, and the event-id preimage is taken over the typed `src:` form.
Ingest documents that at the one place it writes the bare spelling. The checker hashed the bare
spelling unchanged, so **every one of the 21577 records** in the full-telemetry bundle failed to
recompute. Nobody had noticed, because O12 had only ever checked the test fixture's witnesses, and
the fixture wrote the typed spelling into its bundle, which real ingest never does. So the fixture
agreed with the checker's mistake instead of with ingest.

Fixed in `e7cc496`: the fixture writes the bare spelling, the checker re-types it and refuses a typed
spelling in the file. Against the checker as it was, the corrected fixture fails the positive control
and most of the adversarial corpus.

The same session's demo output also labelled a GHOST step with its rule's head predicate
(`privilege.escalated`) instead of the fact it heads (`iam.role_assumed`). That was caught while
reading the first rendering, before it was committed.

### Measured

```
$ python scripts/demo.py
suites: 20 passing, 0 failing
S11 checker  exit 0 (ACCEPT)   O12: 1 tree(s)   full telemetry
S11 checker  exit 0 (ACCEPT)   O12: no witness tree is published   c=70%
S11 checker  exit 0 (ACCEPT)   O12: 2 tree(s)   blackout cell
PREDICTION HELD.
```

The blackout cell's certificate now carries the witness the registration's mechanism describes:

```
without ctl:priv_approval: 3 step(s), 2 unobserved
  rl:r0005 exfil.bulk_read      OBSERVED  cites 1 record(s)
    rl:r0004 privilege.escalated  LICENSED  unobserved, licensed silent step; licence lic:c2de54bf5f92f9c0
      rl:r0004 iam.role_assumed     GHOST     unobserved, obligation-forced; licence lic:c2de54bf5f92f9c0
```

`lic:c2de54bf…` is the SUPPRESSED licence on `iam_audit` from the blackout. Only the three
`cert.spcert` files changed bytes; `p_max.json`, `psi_max.json` and `premium.json` did not. The gate's
CI run at `24b5a6f` was green and printed the same new certificate hashes as the development machine.

### The pattern

Two defects in this increment passed every unit suite. A path separator that happens to be right
on Windows was found by running the real pipeline on a second platform. A fixture that agreed with
the checker instead of with ingest was found by giving the checker real input for the first time.
A fixture written against the code it tests can confirm that code's mistake; each of these was
broken by something the author did not write: another operating system, or the actual bundle.

---

## INC-0013  the tamper pass exists, and tampering now costs the attacker the verdict

date: 2026-09-23
status: DONE
concern: single

### What was missing

INC-0011 recorded a hole and could not close it: `Safety.ROBUST` may be minted only against a
`NoTamperToken`, the token requires that no source is tamper-suspected, and nothing in the slice could
suspect one. Every ROBUST verdict therefore rested on a check that did not exist, and
pre-registration 0001's single named confound - a tamper flag - could not have fired.

The slice-spec excluded the pass deliberately ("Cost: real"). ADR-0016 reverses that, and ADR-0017
corrects one point of ADR-0016 that turned out not to be implementable.

### The attack the pass is written against

Part I runs the pass and VOIDS licences resting on provably backdated timestamps. Part II 65.6
refuses that design, because voiding shrinks P_max, and a smaller P_max can only move a verdict
toward ROBUST: an adversary who can rewrite a timestamp could buy the strongest verdict SPECTRA
issues. The dispute protocol retains the licence and weakens the verdict instead.

This increment implements the protocol, an operator to attack it with, and the measurement that says
whether the defence holds.

### Pre-registration 0002, committed before any of it existed

`a796c41` fixed eight falsifiers for a cell that backdates one record by 45 minutes, comparing the
SAME cell with the pass on and off. All eight passed, on the development machine and on CI:

```
PASS  the pass finds a contradiction                       observed 1 disputed timestamp(s)
PASS  C is exactly the backdated record                    observed ev:c9f5c0c3ef5c102158a5b662e85a6c0e
PASS  iam_audit is suspected, and nothing else             observed src:iam_audit
PASS  p_max.json is byte-identical with the pass off       observed identical
PASS  premium.json is byte-identical with the pass off     observed identical
PASS  the cut over P_max is ROBUST with the pass off       observed ROBUST
PASS  the cut over P_max is OPTIMISTIC_ONLY with the pass on observed OPTIMISTIC_ONLY
PASS  the separate checker accepts the pass-on certificate observed exit 0
```

### Measured: what the tampering would have bought

```
1 licence(s) rest on a disputed timestamp and are RETAINED. Had they been voided, as Part I specifies,
the verdict at the cut over P_max would have been ROBUST, against the published OPTIMISTIC_ONLY.
```

One rewritten timestamp would have upgraded the verdict to the strongest one SPECTRA issues, in the
attacker's favour, under the design Part II replaced. Under the implemented one, `p_max.json` is
byte-identical with the pass off and the verdict moves the other way. The full record is
`docs/research/prereg-0002-result.md`.

### Two things the tests caught before any run

**The correction set was being computed wrongly.** The first formulation covered the violated
neighbour pairs: a record moved far back contradicts only its neighbour, so a cover of that one pair
names the innocent neighbour as readily as the record that moved. Written as a minimum vertex cover
it was both wrong and NP-hard; written as the complement of a longest non-decreasing subsequence per
source it is exact at any size, n log n, and names the record that cannot stay. The unit tests were
written first and failed on exactly that case.

**A guard test fired on schedule.** `test_the_pass_is_not_implemented` had been written earlier to
assert the absence of the pass, with a docstring saying that if it ever failed, the demo's caveats
about the absent check had to be revisited. It failed the moment the pass landed, and the caveats
were rewritten to say how narrow the check is instead of that there is none.

### And one the tests did not catch

The first end-to-end run of the backdate cell passed seven falsifiers and failed the eighth: the
checker rejected the certificate with `ev:... is disputed but its source is not suspected`. The
disputed events were written with the typed `src:iam_audit` spelling while `liveness.json` spells its
sources bare, so the checker compared two spellings of one value.

That is INC-0012's defect exactly, in a member added three commits earlier, and it was found the same
way: by giving the checker real input. The test added with the fix pins the invariant rather than the
instance - every `disputed_events` source id must be one of the spellings the `sources` list uses.

### Scope, stated because this is the increment most likely to be overstated

The pass detects a recorded timestamp that contradicts the order its own source recorded, or a
temporal bound the rule table declares. It does not detect a consistently rewritten source, a forged
chain, or suppression on a source without a sequence number. `flag bit 5` remains permanently false,
because a dispute never voids a licence. `docs/kernel/slice-spec.md` carries the same sentence in the
two places that used to say the pass does not exist.

### Commands run

```
$ <every suite>
21 suites passing, 0 failing

$ python scripts/demo.py
5 cells; S11 ACCEPT on all five; PREDICTION HELD (0001) and PREDICTION HELD (0002)

$ CI run 35870003427 (ubuntu-24.04, CPython 3.12.3)
3 gates green; both predictions held; same disputed event id as this machine
```

---
