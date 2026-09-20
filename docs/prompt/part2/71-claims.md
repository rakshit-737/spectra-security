============================================================
71. CLAIMS REGISTRY, BANNED-PHRASE GATE AND LIMITATIONS
============================================================

71.0 PURPOSE AND OVERRIDE SCOPE

Part I stated an honesty posture in prose (ECLIPSE §9, §30.1, §48.1 "the bench harness has a
monopoly on numbers"). Prose does not stop a sentence from shipping. This section replaces every
prose honesty rule that concerns *externally visible text* with a machine-enforced binding from
sentence to artifact.

OVERRIDES Part I: §48.1's "only the benchmark harness produces published numbers" is now enforced
by `make claims-check`, not asserted; an unregistered numeral in `README.md`, `docs/`, the UI string
catalog, the CLI string catalog, the demo transcript, the paper or the release notes fails the
build.

OVERRIDES Part I: the product framing "which control would have prevented the outcome" and the
interaction name "WHAT-IF CONTROL REPLAY" are DELETED from the project. ECLIPSE §9 disclaims exactly
that counterfactual ("not 'the attacker would have been stopped'"; the attacker is non-adaptive).
The replacement wording in 71.5 is normative and is required verbatim in three places.

OVERRIDES Part I: ECLIPSE §8's demo header prints a bare one-word `ROBUST`. A bare verdict token is
now a banned phrase (71.4, BP-08). Verdicts render only with their scope binding.

Three artifacts are introduced and all three are load-bearing:

```
  docs/claims.md      registry: every externally visible claim, its surfaces, its support, its scope
  docs/banned.toml    banned patterns + mandated replacement + narrow exception list
  LIMITATIONS.md      top-level, linked from README first screen, majority GENERATED from measurement
```

ASCII view of the gate:

```
  bench/validation artifacts ──┐
  (run manifests, limits.json) │
                               ▼
  README.md ──┐          ┌──────────────┐        ┌──────────────────┐
  docs/**.md ─┤          │ claim        │        │ support resolver │
  LIMITATIONS ┤─ extract→│ candidates   │─match─▶│ hash + manifest  │─┐
  ui/*.json  ─┤  (71.2)  │ (sentences,  │  by    │ freshness (71.3) │ │
  cli/*.toml ─┤          │  numerals,   │ CLM id └──────────────────┘ │
  demo txt   ─┤          │  capability  │                             ▼
  paper/*.tex ┤          │  verbs)      │──unanchored──▶ FAIL     GREEN / STALE / UNSUPPORTED
  release/*  ─┘          └──────────────┘                             │
                               │                                      ▼
                               └──banned pattern hit──▶ FAIL     claims-check exit code
```

71.1 THE REGISTRY FILE: docs/claims.md

Implement `docs/claims.md` as the single normative registry of externally visible claims. It is a
markdown file with a machine-parseable record grammar. It is hand-authored; its *support* fields are
verified, never invented.

Grammar (EBNF; the parser rejects anything else — no tolerant parsing, no key reordering, no
optional fields except where marked):

```ebnf
registry   = header , { record } ;
header     = "# SPECTRA CLAIMS REGISTRY" , NL , "schema: " , integer , NL ;
record     = "### " , claim_id , NL , field_block , NL ;
claim_id   = "CLM-" , 4*DIGIT ;                  (* stable forever; never reused after retirement *)
field_block= text_f , kind_f , surfaces_f , support_f , scope_f , status_f , [ note_f ] ;

text_f     = "text: " , dqstring , NL ;          (* the EXACT sentence as it must appear *)
kind_f     = "kind: " , ( "QUANT" | "CAPABILITY" | "FRAMING" | "NEGATIVE" ) , NL ;
surfaces_f = "surfaces:" , NL , 1*( "  - " , surface , NL ) ;
surface    = readme | docpath | uikey | clikey | demoline | paperkey | releasekey | metakey ;
readme     = "README.md#" , anchor ;
docpath    = "docs/" , path , "#" , anchor ;
uikey      = "ui:" , dotted_key ;                (* key in frontend/src/strings/en.json *)
clikey     = "cli:" , dotted_key ;               (* key in cli/strings.toml *)
demoline   = "demo:" , tag ;                     (* tag in demo/transcript.expected.txt *)
paperkey   = "paper:" , ( "abstract" | "intro" | "eval" | "concl" ) ;
releasekey = "release:" , semver ;
metakey    = "meta:" , ( "github_about" | "github_topics" | "cv_bullets" ) ;

support_f  = "support:" , NL ,
             "  artifact: " , path , NL ,        (* the file that PRODUCED the claim's content   *)
             "  blake3: "   , 64*HEXDIG , NL ,   (* hash of that file at registration time       *)
             "  run: "      , run_id , NL ,      (* run manifest id; "n/a" only when kind=NEGATIVE *)
             "  gate: "     , gate_id , NL ,     (* e.g. G-ECL-ROBUST, G-BENCH-KERNEL            *)
             "  target: "   , make_target , NL ; (* the make target a reader can execute         *)
scope_f    = "scope: " , dqstring , NL ;         (* non-empty; >= 8 words; see 71.1.2            *)
status_f   = "status: " , ( "GREEN" | "HELD_OUT" | "TUNED" | "RETIRED" ) , NL ;
note_f     = "note: " , dqstring , NL ;
```

71.1.1 Record rules

1. `text` is byte-compared against the surface. Paraphrase is not registration. If the README
   sentence and the registry sentence differ by one character the gate fails with a unified diff.
2. Every surface occurrence carries an ANCHOR naming its claim id, so matching is exact rather than
   fuzzy:
   - markdown: an HTML comment immediately preceding the sentence's block: `<!-- CLM-0007 -->`
   - UI: the string catalog entry carries `"claim": "CLM-0007"`; no user-visible string may be
     inline in TSX (lint `G-UI-STRINGS`), so the catalog is the only surface.
   - CLI: `cli/strings.toml` entry carries `claim = "CLM-0007"`.
   - demo transcript: the expected line is prefixed `[CLM-0007]` in `transcript.expected.txt` and
     the prefix is stripped by the recorder before display.
   - paper: `\claim{CLM-0007}{...}` macro; the macro expands to its argument and emits the id into
     `paper/claims.aux`, which the gate reads.
3. `status: TUNED` claims may never appear on `README.md#*`, `paper:abstract`, `meta:*` or
   `demo:*`. Headline surfaces accept `GREEN` and `HELD_OUT` only. This binds the claims gate to the
   held-out / overfit protocol (see §62).
4. `RETIRED` records are kept forever with a `note`. Deleting a record is a separate reviewed change;
   the gate fails if a claim id vanishes from the file's history (`G-CLAIM-NOERASE`).
5. `kind: NEGATIVE` records exist for sentences that state what SPECTRA does NOT do. They require a
   scope clause but no run manifest. They are the only records allowed `run: n/a`.

71.1.2 Scope clause requirement

Every record carries a scope clause that names the conditions under which the claim holds. A scope
clause must name at least: the rule table, the control catalog, and the evidence regime. The linter
rejects scope clauses shorter than 8 words, scope clauses matching the banned list, and the strings
"always", "in general", "in practice", "for any system".

Example record (content illustrative, not a target):

```
### CLM-0007
text: "The checker validated every certificate in the held-out corpus in one pass."
kind: CAPABILITY
surfaces:
  - README.md#verification
  - paper:eval
support:
  artifact: artifacts/bench/checker-heldout.json
  blake3: 9c1f4a...   (64 hex, illustrative, not a target)
  run: run-2f7c19e4
  gate: G-CHK-CORPUS
  target: make bench-checker
scope: "Holds for the 12 held-out scenarios (illustrative, not a target) under rules@<hash>, catalog@<hash>, and the certificates those runs emitted; it establishes nothing about certificates produced by other rule tables."
status: HELD_OUT
```

71.2 THE CLAIM EXTRACTOR

Implement `tools/claimcheck/` (Python, stdlib plus the repo's pinned TOML reader; no network, no
model, no heuristics that vary between runs). Entry point `make claims-check`. It is deterministic:
same inputs, byte-identical report.

71.2.1 Surfaces scanned (the closed list; adding a surface requires editing this list and the
registry schema together)

```
README.md
LIMITATIONS.md
SECURITY.md
docs/**/*.md
paper/**/*.tex
frontend/src/strings/*.json
cli/strings.toml
demo/transcript.expected.txt
docs/release-notes/*.md
CHANGELOG.md
docs/repo-metadata.toml        (GitHub About text and topics live here, not in the web UI)
docs/cv-bullets.md             (yes, this is a surface; it is the text most likely to be reused)
.github/PULL_REQUEST_TEMPLATE.md
docs/commit-message-template.txt
```

71.2.2 Segmentation (deterministic, no NLP)

- A markdown paragraph is split into sentences at `[.?!]` followed by whitespace or EOL, except when
  preceded by a token in `tools/claimcheck/abbrev.txt` (committed, sorted, LF).
- A list item is one unit regardless of internal punctuation.
- A table cell is one unit.
- A fenced code block is skipped UNLESS it is the demo transcript or is fenced with `text claim`.
- A UI/CLI string value is one unit. A `.tex` unit is the argument of `\claim{}{}`, or any sentence
  in `abstract`/`intro`/`eval`/`concl` environments.

71.2.3 Candidate detection

A unit is a CLAIM CANDIDATE if any of:

- **NUMERAL**: matches `(?<![A-Za-z0-9_])\d[\d.,_]*\s*(%|x|×|ms|s|min|h|MB|GB|k|K|M)?` after removing
  the non-claim token classes below.
- **CAPABILITY VERB**: contains a lemma from `tools/claimcheck/verbs.txt`, which must include at
  minimum: prove, proves, proven, guarantee, ensure, verify, verified, detect, detects, prevent,
  prevents, stop, stopped, reconstruct, reconstructs, identify, minimize, minimal, exact, complete,
  sound, secure, outperform, faster, scalable, robust, real-time, automatically, all, every, any,
  never, always, zero.
- **COMPARATIVE**: contains `than`, `versus`, `vs`, `compared to`, `state of`, `first`, `only`.
- **BANNED**: matches any pattern in `docs/banned.toml` (71.4). This is a hard failure independent of
  registration.

Non-claim token classes removed before NUMERAL matching (each must be structurally recognisable, not
an English judgement): semantic versions, git SHAs, blake3 digests, ISO-8601 dates and times, section
numbers `§\d+(\.\d+)*`, list ordinals at line start, port numbers inside a `:port` form, ATT&CK ids
`T\d{4}(\.\d{3})?`, RFC numbers, HTTP status codes inside backticks, byte-width literals inside
backticks (`u32`, `u64`), CIDR blocks, and file paths.

71.2.4 Non-claim allowlist

`docs/claims-nonclaims.toml` may exempt a specific `(file, line-content-hash, reason, owner, date)`
tuple. Rules:

- Exemption is keyed by the hash of the unit's normalised text, so editing the sentence voids the
  exemption.
- `reason` must be >= 10 words and must not be "not a claim".
- The file is capped at 25 entries (illustrative, not a target); the cap is enforced by
  `G-CLAIM-ALLOWCAP` and raising it requires a `WAIVER.md` entry.
- No exemption may be granted for a unit in `README.md`'s first screen, `paper:abstract`,
  `LIMITATIONS.md`, or `meta:*`.

71.2.5 Linter pseudocode

```python
def claims_check(repo) -> int:
    reg      = parse_registry(repo/"docs/claims.md")      # strict grammar, 71.1
    banned   = load_banned(repo/"docs/banned.toml")
    allow    = load_nonclaims(repo/"docs/claims-nonclaims.toml")
    findings = []

    for unit in sorted(segment_all_surfaces(repo)):       # sorted -> deterministic report
        for pat in banned:
            if pat.regex.search(unit.text) and unit.path not in pat.exempt_paths:
                findings.append(BANNED(unit, pat))        # never waivable by allowlist

        if not is_candidate(unit):                        # 71.2.3
            continue
        if allow.covers(unit):
            continue

        cid = unit.anchor                                 # <!-- CLM-#### -->, "claim" key, [CLM-####]
        if cid is None:
            findings.append(UNANCHORED(unit)); continue
        rec = reg.get(cid)
        if rec is None:
            findings.append(UNREGISTERED(unit, cid)); continue
        if normalise(rec.text) != normalise(unit.text):
            findings.append(TEXT_DRIFT(unit, rec, diff(rec.text, unit.text))); continue
        if unit.surface_ref not in rec.surfaces:
            findings.append(SURFACE_UNDECLARED(unit, rec)); continue
        if rec.status == "TUNED" and unit.surface_ref in HEADLINE_SURFACES:
            findings.append(TUNED_ON_HEADLINE(unit, rec)); continue

        st = support_state(rec, repo)                     # 71.3
        if st != "FRESH":
            findings.append(STALE(unit, rec, st))

    for rec in reg.records_with_no_matched_surface():
        findings.append(ORPHAN(rec))                      # registered but nowhere said -> fail

    emit_report(findings, repo/"artifacts/claims/report.json")
    return 1 if findings else 0
```

71.3 SUPPORT FRESHNESS

`support_state(rec)` returns FRESH only when ALL hold:

1. `support.artifact` exists and its BLAKE3 equals `support.blake3`.
2. `support.run` resolves to a run manifest in `artifacts/runs/<run_id>.json`.
3. The run manifest's `rules_hash`, `controls_hash`, `axioms_hash`, `er_config_hash` and `git_sha`
   all equal the values the current working tree produces. A rule-table edit therefore invalidates
   every quantitative claim derived from it, which is the intended cost.
4. The run manifest carries no soundness-affecting flag (`grounding_capped`, `corridor_cap_hit`,
   `er_ambiguous`, `greedy_cover`) unless the claim's `scope` names that flag explicitly.
5. `support.gate` appears in the green-gate ledger for the current `git_sha`
   (`artifacts/ci/gates.json`), i.e. the gate actually ran and passed on this tree.
6. For `kind: QUANT`: every numeral in `text` occurs, after normalisation, as a value in
   `support.artifact`. A number in prose that is not present in the artifact is a fabrication and
   fails as `NUMBER_NOT_IN_ARTIFACT`. Rounding is permitted only through a declared rule in the
   record's `note` (e.g. "rounded down to 2 significant figures"), and the linter re-applies that
   rule rather than trusting it.

States and CI behaviour:

| state             | meaning                                        | per-PR | nightly | release |
|-------------------|------------------------------------------------|--------|---------|---------|
| FRESH             | all six conditions hold                        | pass   | pass    | pass    |
| STALE_HASH        | artifact changed since registration            | FAIL   | FAIL    | FAIL    |
| STALE_INPUTS      | rules/catalog/ER hash moved                    | FAIL   | FAIL    | FAIL    |
| GATE_NOT_GREEN    | supporting gate did not run or did not pass    | FAIL   | FAIL    | FAIL    |
| FLAGGED           | run carries a flag the scope does not name     | FAIL   | FAIL    | FAIL    |
| MISSING_ARTIFACT  | artifact absent (e.g. shallow clone)           | warn   | FAIL    | FAIL    |

`make claims-refresh` re-resolves hashes and rewrites only `support.blake3` / `support.run` fields,
never `text` and never `scope`. It refuses to run when the corresponding gate is red.

71.4 THE BANNED-PHRASE GATE

`docs/banned.toml` is the normative list. Every entry carries the honest replacement. The gate is
`G-CLAIM-BANNED` and runs on every push; it is not waivable and has no allowlist. `exempt_paths` is
limited to the files that must discuss the phrase in order to ban it: `docs/banned.toml`,
`docs/claims-policy.md` and this section's copy in `docs/prompt/`.

| id    | banned pattern (case-insensitive regex)                              | why it is false | MANDATED REPLACEMENT |
|-------|----------------------------------------------------------------------|-----------------|----------------------|
| BP-01 | `prov\w*\s+(that\s+)?the attack would have been prevented`            | The kernel reasons about derivability in its model; reality is not in scope (ECLIPSE §9). | "proves that, in SPECTRA's model of this bundle, the goal atom is not derivable under this cut" |
| BP-02 | `\bguarantee[sd]?\b`                                                 | No guarantee survives an unmodelled technique, an ER error or a shared rule-table mistake. | "establishes, relative to rules@<hash> and catalog@<hash>," |
| BP-03 | `detects? all\b` / `\bcatches every\b` / `\bzero false negatives?\b`  | Perfectly suppressed events with no obligation and no blind window are permanently invisible (ECLIPSE §9). | "detects the declared suppression classes S1..Sn; class frequencies and the undetected share are in LIMITATIONS.md" |
| BP-04 | `\bAI[- ]powered\b` / `\bAI[- ]driven\b` / `\bintelligent\b`          | The deterministic core contains no model; the LLM only narrates a certificate and is excluded from every gate. | "deterministic; an optional local model narrates the certificate and changes no result (`make verify-no-llm`)" |
| BP-05 | `real[- ]time threat detection` / `\breal[- ]time\b`                  | SPECTRA is a batch reconstructor over a finished bundle. Nothing streams. | "post-hoc reconstruction over a recorded telemetry bundle" |
| BP-06 | `enterprise[- ]grade` / `production[- ](ready\|like)` / `battle[- ]tested` / `industry[- ]standard` | Unvalidatable. The range is three to five containers on one laptop. | "a laboratory range; what it does not model is enumerated in docs/range/not-modeled.md" |
| BP-07 | `military[- ]grade` / `bank[- ]grade` / `unbreakable` / `bulletproof` | Meaningless. | delete the sentence |
| BP-08 | `(?<![A-Za-z(])ROBUST(?!\()`                                          | A bare verdict token is the only thing a viewer remembers, and it drops the scope ECLIPSE §9 requires. | `ROBUST(rules@<hash8>, catalog@<hash8>, licenses@<hash8>, non-adaptive)` — identically for `OPTIMISTIC_ONLY` and `UNSAFE` |
| BP-09 | `which control would have prevented`, `would have stopped`, `what[- ]if control replay` | Counterfactual about reality; explicitly disclaimed by the kernel. | the framing strings of 71.5 |
| BP-10 | `formally verified` / `\bproof of security\b`                        | ECLIPSE §9: "It is not formal verification of any real system." | "carries a machine-checkable certificate over the model" |
| BP-11 | `minimum cut` unqualified (not followed by `over the declared catalog`) | Minimality is relative to the catalog and may be `psi_relative`. | "cardinality-minimal cut over the declared catalog (minimality: EXACT\|SUBSET\|UNVERIFIED)" |
| BP-12 | `\brealistic\b` / `\bmimics a real\b` outside docs/range/not-modeled.md | Unvalidatable range-realism claim. | "a laboratory model of X; see docs/range/not-modeled.md" |
| BP-13 | `state[- ]of[- ]the[- ]art` / `\bnovel\b` / `\bfirst\b` in README/abstract without a citation-backed record | No baseline survey exists offline. | "related work is discussed in paper/related.tex; no priority claim is made" |
| BP-14 | `\b4[0-9]\+? languages\b` / bare polyglot count                       | Counting markup as languages is padding. | two machine-generated figures: "N languages executing code in CI" and "M configuration formats" (from the polyglot mutation audit) |
| BP-15 | `\bexact\b` applied to the redundancy index or observation set        | Both are computed over a cappable corridor set / a greedy cover. | "exact when `psi_complete` is set; otherwise suppressed" |
| BP-16 | `\bconfidence\b` / `\bprobability\b` / `\brisk score\b` / `\bseverity\b` / `\blikelihood\b` | ECLIPSE §9 forbids probabilities and scores anywhere. | delete; report the set, not a scalar |
| BP-17 | `\bsimply\b` / `\bjust\b` / `\beasily\b` / `\bobviously\b` in docs     | Hedge-free house style; these words hide unproven steps. | delete |

71.4.1 Runtime enforcement

The banned list is not only a text gate.

1. The frontend imports `banned.generated.ts` (generated by `make claims-gen`) and a unit test
   asserts no string in `en.json` matches any pattern. `G-UI-BANNED`.
2. The CLI does the same for `cli/strings.toml` at build time. `G-CLI-BANNED`.
3. The LLM narrator (Part I's narration boundary) runs its output through the same patterns. A hit
   SUPPRESSES the narration entirely and prints `narration withheld: banned phrase <id>`. It must
   never rewrite or soften the output — an edited narration is an unverifiable one.
4. `spectra verify` REJECTS a certificate whose `mode` string is a bare token without its scope
   binding, with exit code 3 and reason `E_MODE_UNSCOPED`. The Go checker owns this check.

71.5 THE CORRECTED FRAMING (NORMATIVE WORDING)

OVERRIDES Part I: the core framing sentence is replaced. Store the strings in `docs/framing.toml`,
generate every copy from it (`make claims-gen`), and gate byte-equality of every copy
(`G-FRAMING-VERBATIM`). No file may contain a near-copy.

```toml
# docs/framing.toml — the only place these sentences are authored.
schema = 1

[oneline]                 # README H1 subtitle, GitHub About, CLI banner line 1
text = "SPECTRA computes which settings of a declared control catalog make a reconstructed attacker objective underivable in SPECTRA's model of a recorded telemetry bundle, and emits a certificate an independent checker can re-verify."

[disclaimer]              # required within the same screen/banner/abstract as [oneline]
text = "This is a statement about the model, not about what would have happened. The attacker is non-adaptive, the rule table and control catalog are hand-written, and an unmodelled technique remains unmodelled. See LIMITATIONS.md."

[interaction_name]        # replaces "WHAT-IF CONTROL REPLAY"
text = "IN-MODEL CONTROL CUT"

[verdict_template]
robust    = "ROBUST(rules@{r8}, catalog@{c8}, licenses@{l8}, non-adaptive)"
optimistic= "OPTIMISTIC_ONLY(rules@{r8}, catalog@{c8}, licenses@{l8}, non-adaptive)"
unsafe    = "UNSAFE(rules@{r8}, catalog@{c8}, licenses@{l8}, non-adaptive)"
```

Placement requirements, each with its own gate:

1. **README first screen.** Define the first screen structurally: the byte range from the start of
   `README.md` to the first `\n## ` heading. It must contain, in order: the H1, `[oneline]`
   verbatim, `[disclaimer]` verbatim, and a link whose target is `LIMITATIONS.md` and whose anchor
   text is exactly `Limitations and known-unsound regions`. `G-FRAMING-README`.
2. **CLI banner.** `spectra prove`, `spectra verify` and `make demo` print `[oneline]` and
   `[disclaimer]` on stderr before any result, on every invocation, with no `--quiet` suppression of
   `[disclaimer]`. A golden-output test asserts the exact bytes. `G-FRAMING-CLI`.
3. **Paper abstract.** `paper/abstract.tex` begins with `\input{generated/framing-oneline}` and ends
   with `\input{generated/framing-disclaimer}`. Both generated files are produced by
   `make claims-gen`; the LaTeX build fails if they are stale. `G-FRAMING-PAPER`.

71.6 LIMITATIONS.md

`LIMITATIONS.md` sits at repository root and is linked from the README first screen (71.5). It is
part hand-written frame, part GENERATED. Hand-writing a limitations file alone is forbidden: a
limitation stated without a measured magnitude is a disclaimer, not a limitation.

71.6.1 Generated-block markers

```markdown
<!-- BEGIN GENERATED: er_error  src=artifacts/limits/limits.json#er_error  run=run-2f7c19e4  gen=tools/limits/render.py -->
| scenario | completeness | pair precision | pair recall | false merges | false splits |
|----------|--------------|----------------|-------------|--------------|--------------|
| ...rendered rows, values illustrative, not targets...                                  |
<!-- END GENERATED: er_error -->
```

Rules:

1. `make limitations` regenerates every block from `artifacts/limits/limits.json`. CI regenerates and
   diffs; a non-empty diff fails `G-LIMITS-FRESH`.
2. A numeral outside a generated block in `LIMITATIONS.md` fails `G-LIMITS-NOHAND`. Prose frames the
   measurement; it never states one.
3. If `limits.json` lacks a required block, the renderer emits, in place of the table:
   `**NOT MEASURED.** This block blocks release; see gate <gate_id>.` and `make release` fails
   (`G-LIMITS-COMPLETE`). Silent omission is impossible by construction.
4. A generated block whose `run` manifest disagrees with the current `rules_hash` / `controls_hash` /
   `er_config_hash` is STALE and fails. Limitations go stale exactly when the claims do.
5. `LIMITATIONS.md` is itself a claims surface (71.2.1), so its prose frames obey the banned list.

71.6.2 Required blocks and their schema

`artifacts/limits/limits.json` (produced by the validation matrix of §62; integers and rationals as
`{"num":int,"den":int}` — no floats anywhere, per the determinism charter):

```jsonc
{
  "schema": 1,
  "run": "run-2f7c19e4",
  "input_hashes": { "rules": "...", "controls": "...", "axioms": "...", "er_config": "...",
                    "baseline_calibration": "...", "generator": "..." },
  "invisible_suppression": {                 // "we cannot see this at all" — the honesty core
    "classes": [ { "id": "S1",
                   "definition": "single record deleted inside a window whose observed inter-arrival stays below the hashed baseline threshold",
                   "injected": 0, "licensed": 0, "undetected": 0,
                   "by_completeness": [ { "level": 90, "injected": 0, "undetected": 0 } ] } ],
    "enumeration_complete": true             // false => README may not claim class coverage
  },
  "blind_spot_volume": {                     // per dimension, never aggregated to one number
    "unit": "source-ticks",
    "rows": [ { "dimension": "credential", "completeness": 70,
                "blind": {"num":0,"den":1}, "suppressed": {"num":0,"den":1},
                "live": {"num":0,"den":1} } ]
  },
  "er_error": { "rows": [ { "scenario": "...", "completeness": 100,
                            "pair_precision": {"num":0,"den":1}, "pair_recall": {"num":0,"den":1},
                            "false_merges": 0, "false_splits": 0,
                            "verdict_flips_under_injection": 0 } ] },
  "flagged_run_share": { "total_runs": 0,
    "by_flag": { "er_ambiguous": 0, "grounding_capped": 0, "corridor_cap_hit": 0,
                 "greedy_cover": 0, "subset_minimal_only": 0, "license_voided_by_backdating": 0 },
    "any_flag": 0 },
  "capped_run_share": { "grounding_capped": 0, "corridor_cap_hit": 0,
                        "psi_incomplete": 0, "minimality_psi_relative": 0 },
  "verdict_yield": { "robust_yield": {"num":0,"den":1},      // non-vacuity counterpart
                     "false_unsafe": {"num":0,"den":1},
                     "false_robust": 0 }                      // must be 0; see §62
}
```

71.6.3 Required hand-written frames (each immediately followed by its generated block)

1. **What a verdict is not.** Restates ECLIPSE §9 in the reader's terms; names the non-adaptive
   attacker; states that a cut may be actively misleading as defensive prioritisation advice because
   a real adversary re-plans around it.
2. **What we cannot see.** Frame for `invisible_suppression`. States that SPECTRA's suppression
   detection leans on hash-chained sources, that most real telemetry has no such chain, and links the
   per-source-class split.
3. **Where the model is blind.** Frame for `blind_spot_volume`.
4. **Entity resolution is the largest soundness risk.** Frame for `er_error`; states that a false
   merge fabricates facts the kernel then proves things about.
5. **When we flag and what that costs.** Frame for `flagged_run_share` and `capped_run_share`;
   states that a flagged run is never presented as ROBUST and that the flagged share is therefore
   part of the honest result, not a footnote.
6. **Non-vacuity.** Frame for `verdict_yield`; states plainly that `return UNSAFE` would pass the
   zero-false-ROBUST invariant and that the yield figure is what prevents that reading.
7. **Naming.** One paragraph: ECLIPSE collides with a well-known foundation and toolchain; the name
   asserts no relation.

71.7 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS

Do not do any of the following. Each is a build failure, not a style note.

1. Do not add a numeral to any surface in 71.2.1 without a registry record whose artifact contains
   it. Do not round, do not "approximately", do not write `~`.
2. Do not write an illustrative number into shipped text at all. Illustrative numbers exist only in
   this prompt and in `docs/prompt/`, always tagged "(illustrative, not a target)". A tagged number
   that escapes into `README.md`, `docs/` outside `docs/prompt/`, `paper/` or source fails
   `G-CLAIM-PLACEHOLDER`.
3. Do not implement a `--no-banner`, `--quiet` or `SPECTRA_NO_DISCLAIMER` path that suppresses
   `[disclaimer]`. A test asserts the string is on stderr for every CLI entry point under every flag
   combination in `cli/flags.txt`.
4. Do not format a verdict string by concatenation anywhere. One constructor, in one module per
   language, taking the three hashes; a lint forbids the literal `"ROBUST"` outside it.
5. Do not let the narrator, the API, the database schema, the export formats or the frontend carry a
   field named or typed as a score, confidence, probability, severity, likelihood, rating or
   percentage-of-risk. Schema lint `G-NO-SCORES` over the OpenAPI document, the SQL DDL and the
   TypeScript types.
6. Do not claim coverage of suppression classes while `invisible_suppression.enumeration_complete`
   is false.
7. Do not publish the redundancy index, the decisive observation set size, or any Pareto point while
   the corresponding certificate flag is set. The API omits the field; the UI renders the reason, not
   a blank.
8. Do not state a language count from a hand-maintained table. Both figures come from the polyglot
   mutation audit artifact or they are not stated.
9. Do not describe the range with `realistic`, `production-like` or `enterprise`. Describe what it
   contains and link `docs/range/not-modeled.md`.
10. Do not mark a claim `GREEN` whose supporting scenario appears in the TUNED set of the overfit
    ledger. Headline numbers come from HELD_OUT only.
11. Do not repair a failing claims gate by deleting the claim from the registry while leaving the
    sentence in place, or by moving the sentence into a code fence. Both are detected: `ORPHAN` and
    the `text claim` fence rule.
12. Do not use a `WAIVER.md` entry to bypass `G-CLAIM-BANNED`, `G-FRAMING-*` or `G-LIMITS-NOHAND`.
    Those three gates are unwaivable; the waiver mechanism refuses to parse their ids.

71.8 GATES, TARGETS AND TIERING

| gate id              | make target            | tier    | fails when |
|----------------------|------------------------|---------|------------|
| G-CLAIM-PARSE        | `make claims-check`    | per-PR  | `docs/claims.md` violates the grammar of 71.1 |
| G-CLAIM-ANCHOR       | `make claims-check`    | per-PR  | a claim candidate has no `CLM-` anchor |
| G-CLAIM-REGISTERED   | `make claims-check`    | per-PR  | anchored claim absent from the registry, or text drift |
| G-CLAIM-SUPPORT      | `make claims-check`    | per-PR  | support hash / run manifest / gate ledger stale or flagged |
| G-CLAIM-NUMSRC       | `make claims-check`    | per-PR  | a numeral in a QUANT claim is absent from its artifact |
| G-CLAIM-BANNED       | `make claims-check`    | per-PR  | any banned pattern outside its exempt path (unwaivable) |
| G-CLAIM-ALLOWCAP     | `make claims-check`    | per-PR  | non-claim allowlist over cap, or an entry lacks a reason |
| G-CLAIM-NOERASE      | `make claims-check`    | per-PR  | a claim id present in an earlier commit is missing and not RETIRED |
| G-CLAIM-PLACEHOLDER  | `make claims-check`    | per-PR  | "(illustrative, not a target)" or an `<<MEASURED:*>>` token appears outside `docs/prompt/` |
| G-FRAMING-VERBATIM   | `make claims-gen`      | per-PR  | any generated framing copy differs from `docs/framing.toml` |
| G-FRAMING-README     | `make claims-check`    | per-PR  | first screen lacks oneline, disclaimer or the LIMITATIONS link |
| G-FRAMING-CLI        | `make test-cli`        | per-PR  | banner golden output differs, or a flag suppresses the disclaimer |
| G-FRAMING-PAPER      | `make paper`           | nightly | abstract does not `\input` the generated framing files |
| G-UI-STRINGS         | `make lint-frontend`   | per-PR  | a user-visible literal appears outside `strings/en.json` |
| G-UI-BANNED          | `make test-frontend`   | per-PR  | a catalog string matches a banned pattern |
| G-CLI-BANNED         | `make test-cli`        | per-PR  | a CLI string matches a banned pattern |
| G-NO-SCORES          | `make lint-schemas`    | per-PR  | a score/confidence/severity field exists in any schema |
| G-LIMITS-FRESH       | `make limitations`     | per-PR  | regenerating `LIMITATIONS.md` produces a diff |
| G-LIMITS-NOHAND      | `make claims-check`    | per-PR  | a numeral outside a generated block in `LIMITATIONS.md` (unwaivable) |
| G-LIMITS-COMPLETE    | `make release`         | release | a required block is NOT MEASURED |
| G-DEMO-CLAIMS        | `make demo-verify`     | per-PR  | a transcript line lacks its `[CLM-]` tag or its printed value differs from the live run |

`make claims-check` is fast (pure text plus hashes) and runs on every push. `make limitations`
depends on the validation matrix artifact and runs per-PR against the committed artifact, nightly
against a fresh matrix.

71.9 CLI TRANSCRIPT (illustrative, not a target — all ids, paths and values below are placeholders)

```
$ make claims-check
claimcheck 1 — surfaces=14 units=1,208 candidates=97 registry=63 records

FAIL  README.md:31  UNREGISTERED
      sentence: "SPECTRA reconstructs the attack chain even at 30% telemetry completeness."
      anchor:   none
      fix:      add <!-- CLM-#### --> and a record in docs/claims.md, or state nothing.

FAIL  README.md:44  BANNED  BP-08  bare verdict token
      sentence: "The kernel returned ROBUST in under a second."
      replace with: ROBUST(rules@<hash8>, catalog@<hash8>, licenses@<hash8>, non-adaptive)
      (this finding is unwaivable)

FAIL  docs/eval.md:12  STALE_INPUTS  CLM-0031
      support.run  = run-91ab00cd  rules_hash=4c2e...  (registered)
      working tree            rules_hash=77d1...  (current)
      the rule table changed after this number was measured; re-run `make bench-kernel`.

FAIL  frontend/src/strings/en.json:verdict.subtitle  BANNED  BP-05 real-time

FAIL  LIMITATIONS.md:58  G-LIMITS-NOHAND
      numeral outside a generated block: "roughly a third of runs are flagged"
      write it into artifacts/limits/limits.json and regenerate.

FAIL  docs/claims.md  ORPHAN  CLM-0044 registered but matched no surface.

6 findings, 0 warnings — exit 1
report: artifacts/claims/report.json
```

```
$ make claims-check
claimcheck 1 — surfaces=14 units=1,208 candidates=97 registry=63 records
0 findings — exit 0
```

71.10 RELATIONSHIP TO OTHER SECTIONS

- §62 produces `artifacts/limits/limits.json`, the run manifests and the gate ledger this section
  consumes. If §62's matrix does not run, every QUANT claim goes MISSING_ARTIFACT and release fails.
- The verdict algebra (safety and minimality as independent fields) is what makes BP-08 and BP-11
  mechanically checkable; this section owns only their appearance in text.
- The polyglot mutation audit supplies the only two language counts any surface may state (BP-14).
- The demo harness is a claims surface: its transcript is tagged, hash-checked and regenerated, so a
  recorded demo cannot drift from the registry.

71.11 DEFINITION OF DONE FOR SECTION 71

1. `docs/claims.md` parses under the 71.1 grammar and every record resolves FRESH on a clean clone.
2. `make claims-check` exits 0 on the repository and exits 1 on each of the seeded regression cases
   in `tests/claims/negative/` — one case per finding kind and one per banned pattern BP-01..BP-17.
   A finding kind with no negative test is itself a failure (`G-CLAIM-SELFTEST`).
3. Deleting `docs/framing.toml`, editing one byte of the README oneline, changing one digit of a
   published number, or adding `enterprise-grade` to a UI string each turn CI red — demonstrated by
   a recorded mutation run in `docs/research/gate-liveness.md`.
4. `LIMITATIONS.md` renders with every required block present, every numeral inside a generated
   block, and the README first screen links it with the exact anchor text.
5. `make release` refuses to produce a release artifact while any gate in 71.8 is red.
