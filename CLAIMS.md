# SPECTRA CLAIMS REGISTRY

schema: 1

Source: build specification Part II, section 71. This file is the single normative registry of
every externally visible claim SPECTRA makes, and the normative list of phrases it may never use.

Status of this document: delivered, with zero claim records. Status of the claims gate
(`make claims-check`, `tools/claimcheck/`): not started. Nothing in this repository is currently
checked against this file.

TODO (decision made here — path): section 71.1 names the registry `docs/claims.md`. This repository
puts it at the root as `CLAIMS.md`, next to `LIMITATIONS.md`, so that both honesty artifacts are
visible on the repository's front page. To change this later, move the file to `docs/claims.md` and
update the registry path in `tools/claimcheck/` and in the surface list below, in the same commit.
There must be exactly one registry file; a second copy is a fork of the truth.

TODO (decision made here — exemption): this file quotes banned patterns in order to ban them, so it
must be listed in the `exempt_paths` of `docs/banned.toml` alongside `docs/claims-policy.md` and
`docs/prompt/`. Do not extend that exemption to any other file.

## The rule

**A claim with no backing artifact fails CI.** A sentence on any surface below that states a number,
uses a capability verb, or makes a comparison must carry a `CLM-####` anchor, must have a record in
this file whose `text` is byte-identical to the sentence, and that record's `support.artifact` must
exist, must hash to the registered value, must come from a resolvable run manifest, and must have
been produced by a gate that actually ran and passed on the current tree. Any of those failing is a
build failure, not a warning.

The corollaries, all gated:

- A registered record that matches no surface is an orphan and fails. You may not register a claim
  you do not make.
- A claim id that existed in an earlier commit and has vanished without being retired fails.
  Retirement is recorded; deletion is not permitted.
- A record whose supporting scenario pool is the tuned pool may never appear on the README, the
  paper abstract, the repository metadata or the demo transcript. Headline surfaces take held-out
  results only.
- A number in prose that does not occur in its supporting artifact is a fabrication and fails as
  `NUMBER_NOT_IN_ARTIFACT`.
- Repairing a failing gate by deleting the record while leaving the sentence, or by moving the
  sentence into a code fence, is detected and fails.
- The banned-phrase gate, the framing gates and the no-hand-written-numbers gate in `LIMITATIONS.md`
  are unwaivable. The waiver mechanism refuses to parse their ids.

## The registry

Zero records. No claim has been registered, because no artifact has been produced and no gate has
run.

### Record index

| claim id | text | kind | surfaces | support artifact | gate | scope | status |
|----------|------|------|----------|------------------|------|-------|--------|

(The table above is the human index and is intentionally empty. It is regenerated from the records
below once `make claims-gen` exists.)

### Record grammar

Records are appended below this heading, one per claim, in the following fixed shape. The parser is
strict: no key reordering, no tolerant parsing, no optional fields except `note`.

```
### CLM-####
text: "the exact sentence, as it must appear on every surface"
kind: QUANT | CAPABILITY | FRAMING | NEGATIVE
surfaces:
  - README.md#anchor
  - docs/path.md#anchor
  - ui:dotted.key
  - cli:dotted.key
  - demo:tag
  - paper:abstract | paper:intro | paper:eval | paper:concl
  - release:semver
  - meta:github_about | meta:github_topics | meta:cv_bullets
support:
  artifact: path/to/the/file/that/produced/the/content
  blake3: <sixty-four hex characters>
  run: <run manifest id, or n/a only when kind is NEGATIVE>
  gate: <gate id>
  target: <the make target a reader can execute>
scope: "names the rule table, the control catalog and the evidence regime; at least eight words"
status: GREEN | HELD_OUT | TUNED | RETIRED
note: "optional"
```

Claim ids are stable forever and are never reused after retirement. The scope clause may not contain
"always", "in general", "in practice" or "for any system".

### Records

_None._

## Surfaces scanned

The closed list. Adding a surface requires editing this list and the registry schema together.

```
README.md
LIMITATIONS.md
SECURITY.md
CLAIMS.md
docs/**/*.md
paper/**/*.tex
frontend/src/strings/*.json
cli/strings.toml
demo/transcript.expected.txt
docs/release-notes/*.md
CHANGELOG.md
docs/repo-metadata.toml
docs/cv-bullets.md
.github/PULL_REQUEST_TEMPLATE.md
docs/commit-message-template.txt
```

Of these, only `README.md`, `LIMITATIONS.md`, `SECURITY.md`, `CLAIMS.md`,
`.github/PULL_REQUEST_TEMPLATE.md` and part of `docs/` exist yet.

## The banned-phrase list

Every entry carries the honest replacement. The gate is `G-CLAIM-BANNED`, it runs on every push, it
is not waivable, and it has no allowlist. Exempt paths are this file, `docs/banned.toml`,
`docs/claims-policy.md` and `docs/prompt/`, plus the two narrowly exempted documents noted in
`docs/NON-GOALS.md` and `docs/descope-ladder.md`.

`docs/banned.toml` is the machine-readable form of this table and does not exist yet. Until it does,
this table is documentation, not enforcement.

| id | banned pattern (case-insensitive) | why it is false | mandated replacement |
|----|-----------------------------------|-----------------|----------------------|
| BP-01 | `prov\w*\s+(that\s+)?the attack would have been prevented` | The kernel reasons about derivability in its model; reality is not in scope. | "proves that, in SPECTRA's model of this bundle, the goal atom is not derivable under this cut" |
| BP-02 | `\bguarantee[sd]?\b` | No guarantee survives an unmodelled technique, an entity-resolution error or a shared rule-table mistake. | "establishes, relative to rules@<hash> and catalog@<hash>," |
| BP-03 | `detects? all\b`, `\bcatches every\b`, `\bzero false negatives?\b` | Perfectly suppressed events with no obligation and no blind window are permanently invisible. | "detects the declared suppression classes; class frequencies and the undetected share are in LIMITATIONS.md" |
| BP-04 | `\bAI[- ]powered\b`, `\bAI[- ]driven\b`, `\bintelligent\b` | The deterministic core contains no model; the optional narrator only describes a certificate and is excluded from every gate. | "deterministic; an optional local model narrates the certificate and changes no result (`make verify-no-llm`)" |
| BP-05 | `real[- ]time threat detection`, `\breal[- ]time\b` | SPECTRA is a batch reconstructor over a finished bundle. Nothing streams. | "post-hoc reconstruction over a recorded telemetry bundle" |
| BP-06 | `enterprise[- ]grade`, `production[- ](ready\|like)`, `battle[- ]tested`, `industry[- ]standard` | Unvalidatable. The range is a handful of containers on one laptop. | "a laboratory range; what it does not model is enumerated in docs/range/not-modeled.md" |
| BP-07 | `military[- ]grade`, `bank[- ]grade`, `unbreakable`, `bulletproof` | Meaningless. | delete the sentence |
| BP-08 | a bare verdict token, i.e. `ROBUST` not followed by `(` | A bare verdict token is the only thing a reader remembers, and it drops the scope the kernel requires. | `ROBUST(rules@<hash8>, catalog@<hash8>, licenses@<hash8>, non-adaptive)`, identically for the optimistic-only and unsafe tokens |
| BP-09 | `which control would have prevented`, `would have stopped`, `what[- ]if control replay` | A counterfactual about reality, explicitly disclaimed by the kernel. | the normative framing strings in `docs/framing.toml`; the interaction is named IN-MODEL CONTROL CUT |
| BP-10 | `formally verified`, `\bproof of security\b` | It is not formal verification of any real system. | "carries a machine-checkable certificate over the model" |
| BP-11 | `minimum cut` not followed by `over the declared catalog` | Minimality is relative to the catalog and may be relative to the licensed hypothesis set. | "cardinality-minimal cut over the declared catalog (minimality: EXACT, SUBSET or UNVERIFIED)" |
| BP-12 | `\brealistic\b`, `\bmimics a real\b` outside `docs/range/not-modeled.md` | Unvalidatable range-realism claim. | "a laboratory model of X; see docs/range/not-modeled.md" |
| BP-13 | `state[- ]of[- ]the[- ]art`, `\bnovel\b`, `\bfirst\b` in the README or the abstract without a citation-backed record | No baseline survey exists offline. | "related work is discussed in paper/related.tex; no priority claim is made" |
| BP-14 | a bare polyglot language count | Counting markup as languages is padding. | the two machine-generated figures from the polyglot mutation audit: languages executing code in CI, and configuration formats |
| BP-15 | `\bexact\b` applied to the redundancy index or the observation set | Both are computed over a cappable corridor set or a greedy cover. | "exact when the corridor set is complete; otherwise suppressed" |
| BP-16 | `\bconfidence\b`, `\bprobability\b`, `\brisk score\b`, `\bseverity\b`, `\blikelihood\b` | Probabilities and scores are forbidden anywhere in the project. | delete; report the set, not a scalar |
| BP-17 | `\bsimply\b`, `\bjust\b`, `\beasily\b`, `\bobviously\b` in docs | House style is hedge-free; these words hide unproven steps. | delete |

### Runtime enforcement, once it exists

The banned list is not only a text gate. The frontend and the CLI test their own string catalogs
against it at build time; the optional narrator runs its output through it and withholds the
narration entirely on a hit rather than rewriting it; and `spectra verify` rejects a certificate
whose mode string is a bare token without its scope binding. None of these is implemented.

## Gates this file will be enforced by

| gate id | make target | fails when |
|---------|-------------|------------|
| G-CLAIM-PARSE | `make claims-check` | this file violates the record grammar |
| G-CLAIM-ANCHOR | `make claims-check` | a claim candidate has no `CLM-` anchor |
| G-CLAIM-REGISTERED | `make claims-check` | an anchored claim is absent from the registry, or its text has drifted |
| G-CLAIM-SUPPORT | `make claims-check` | support hash, run manifest or gate ledger is stale or flagged |
| G-CLAIM-NUMSRC | `make claims-check` | a numeral in a quantitative claim is absent from its artifact |
| G-CLAIM-BANNED | `make claims-check` | any banned pattern outside its exempt path (unwaivable) |
| G-CLAIM-ALLOWCAP | `make claims-check` | the non-claim allowlist is over cap, or an entry lacks a reason |
| G-CLAIM-NOERASE | `make claims-check` | a claim id present in an earlier commit is missing and not retired |
| G-CLAIM-PLACEHOLDER | `make claims-check` | an illustrative-value tag or a measured-value token escapes `docs/prompt/` |
| G-FRAMING-VERBATIM | `make claims-gen` | a generated framing copy differs from `docs/framing.toml` |
| G-FRAMING-README | `make claims-check` | the README first screen lacks the one-liner, the disclaimer or the limitations link |
| G-FRAMING-CLI | `make test-cli` | the banner golden output differs, or a flag suppresses the disclaimer |
| G-FRAMING-PAPER | `make paper` | the abstract does not include the generated framing files |
| G-UI-STRINGS | `make lint-frontend` | a user-visible literal appears outside the string catalog |
| G-UI-BANNED | `make test-frontend` | a catalog string matches a banned pattern |
| G-CLI-BANNED | `make test-cli` | a CLI string matches a banned pattern |
| G-NO-SCORES | `make lint-schemas` | a score, confidence or severity field exists in any schema |
| G-LIMITS-FRESH | `make limitations` | regenerating `LIMITATIONS.md` produces a diff |
| G-LIMITS-NOHAND | `make claims-check` | a numeral appears outside a generated block in `LIMITATIONS.md` (unwaivable) |
| G-LIMITS-COMPLETE | `make release` | a required limitations block is NOT MEASURED |
| G-DEMO-CLAIMS | `make demo-verify` | a transcript line lacks its claim tag, or its printed value differs from the live run |

Every gate in this table is **not started**. None of these targets exists.
