# SPECTRA — Kickoff

You are building SPECTRA in this repository, starting from empty. Read this message fully, then follow it exactly.

## 1. What SPECTRA is

SPECTRA is a local-first, offline, Dockerized research platform that reconstructs how a system's **security state** evolved — identity, session, credential, privilege, process, network, API, service, resource, trust — from degraded and partially tampered telemetry, builds a temporal and causal structure over the observed state transitions, and then answers one class of counterfactual control question: *which control, at which level, severs this attack chain in the model?* The answer is not asserted by a language model and not read off a heuristic score. It is produced by a proof kernel called ECLIPSE as a content-addressed **certificate** — a cut over a declared control catalog, an inductive invariant, a counterexample derivation tree per control removed, and the licenses that permitted each unobserved step — and an independently written checker re-validates that certificate in one linear pass. What makes SPECTRA different is not the graph and not the UI; it is that missing telemetry is modeled as an explicit *license* for unobserved attacker steps, so the system can distinguish "this control is needed" from "this control is needed **only because you could not see**." What SPECTRA is *not*: it is not formal verification of any real system, it proves properties of a model and not of reality, the attacker it reasons about is non-adaptive, and every guarantee it makes is relative to a hand-written rule table, an entity resolution pass, a declared control catalog and the telemetry actually ingested. Say that plainly in every artifact you produce.

## 2. Read the master prompt first

Before you write a single line of code, a single Dockerfile, or a single directory:

- Read `docs/prompt/SPECTRA_MASTER_PROMPT.md` **in full**, both parts, top to bottom. Do not skim. Do not start from the section map.
- Part I is sections 0–56. Part II is the hardening addendum, sections 57–76, written after three independent critics found real defects in Part I.
- **Part II overrides Part I wherever they conflict.** Where Part II says it overrides something, the Part I text is dead. Do not attempt to satisfy both. Where you find a conflict Part II does not explicitly resolve, stop and ask the human — do not pick one silently.
- If the file is not present in this repository, stop and say so. Do not reconstruct it from this message.

## 3. The laws

These are non-negotiable. They are enforced by gates, not by good intentions. If you cannot satisfy one, you stop and say so — you never work around it.

1. **Deterministic core.** Same inputs, same seed, same bytes out, on any machine and any OS. No hash-map iteration order in any output path, no wall-clock timeouts in any decision path (deterministic step budgets only), no floating point in any branch that affects a verdict, no filesystem directory-order iteration, pinned `TZ=UTC` and `LC_ALL=C`, LF enforced by `.gitattributes`.
2. **The LLM is removable.** Narration consumes the certificate and nothing else. `make verify-no-llm` must pass with the model and its dependency absent. Every gate, every benchmark, every number stays green without it. The narrator never produces a number, probability, confidence or severity.
3. **No fabricated numbers, ever.** Every numeral in `README.md`, in `docs/`, in the UI and in the demo traces to a result id in a benchmark or gate artifact, or CI fails. Placeholder tokens in the master prompt are placeholders, not targets — never copy them into code, docs or fixtures.
4. **Offline and seeded.** A clean clone builds and runs with the network off. Dependencies vendored per ecosystem, base images pinned by digest. Every run emits a manifest: all input hashes, git SHA, toolchain versions, seeds, host fingerprint.
5. **Quarantine never silently drops.** A malformed or unparseable record is quarantined with a reason code and counted. A silent drop manufactures a blind window, which manufactures a license, which corrupts a verdict. This is a correctness rule, not hygiene.
6. **ROBUST is unconstructible while any soundness-affecting flag is set.** Safety and minimality are independent typed fields — `safety: ROBUST | OPTIMISTIC_ONLY | UNSAFE`, `minimality: EXACT | SUBSET | UNVERIFIED`. Verdict strings carry their scope binding (rules hash, catalog hash, licenses hash, non-adaptive attacker) and are never formatted by string concatenation. The checker rejects any certificate violating this algebra.
7. **Every claim is bound to an artifact.** Externally visible claims are registered in `docs/claims.md` with the test or benchmark that supports them and their scope qualifier. A banned-phrase gate covers "proves", "guaranteed", "prevents", "would have stopped", "formally verified", "realistic", "enterprise-grade", "state of the art" outside registered entries.
8. **No stub on the demo path.** Anything the 60-second demo touches is real, executed, and hash-checked against committed expectations. No pre-recorded terminal output, no seeded example numbers, no narrative line not derived from the certificate on screen.

## 4. What to do in session one

In this order, and no further:

1. **Read** `docs/prompt/SPECTRA_MASTER_PROMPT.md` in full.
2. **Write a plan** to `docs/plan/PLAN_v1.md`. It must cover, at minimum:
   - the **milestone list**: the ordered milestones, what each one delivers, what gate turns it green, and what it explicitly does not deliver;
   - the **descope ladder**: the minimum publishable core, then the ordered cut list — what gets dropped first, second, third when a milestone overruns, and the rule that README claims track only green milestones;
   - the **language tiering** with an honest role per language and the mutation-audit rule that deletes any language whose artifact can be stubbed without turning a CI job red;
   - open questions and every Part I / Part II conflict you found that Part II did not resolve.
3. **Confirm the plan with the human.** Present it, list the decisions you need, and wait. Do not proceed on assumed approval. An approval must come from the human in this session.
4. **Create the repo skeleton only** after approval: directory structure, `LICENSE`, `SECURITY.md`, `LIMITATIONS.md` (stub with its required headings), `README.md` (scope and status table only, no claims yet), `docs/claims.md`, `docs/research/preregistration.md` (empty with its required headings), `BUILD_LOG.md`, `.gitattributes`, `.editorconfig`, `Makefile` with targets declared and failing loudly rather than lying, CI workflow files with jobs declared and skipped, and empty package roots for the tier-A languages.
5. **Stop at the first checkpoint** and ask for review.

**Do not start implementing the kernel in session one.** No grounding, no fixpoint, no liveness pass, no guard AST compiler, no solver. Do not write the generator. Do not write the range. If you find yourself opening a `.rs` file with logic in it, you have gone too far.

## 5. First deliverables — checklist

- [ ] Confirmation that you read the master prompt in full, with a one-line statement of how many sections you read in each part.
- [ ] `docs/plan/PLAN_v1.md` — milestone list, descope ladder / minimum publishable core, language tiering with mutation-audit rule, held-out vs tuned scenario protocol, CI tiering sketch (per-PR vs nightly), open questions.
- [ ] `docs/plan/CONFLICTS.md` — every Part I / Part II conflict you found, how Part II resolves it, and the ones it does not.
- [ ] `docs/plan/GLOSSARY_STUB.md` — the canonical vocabulary table skeleton: one concept, one name, one identifier type, one owning section.
- [ ] Human approval recorded in `BUILD_LOG.md` with the date and what was approved.
- [ ] Repo skeleton as described above, committed, with a clean tree.
- [ ] `make` runs and every declared target either does its real job or exits non-zero with "not implemented" — never exits zero having done nothing.
- [ ] A checkpoint message listing what exists, what does not, and what you need next.

## 6. Reporting and what never to claim

Report progress in `BUILD_LOG.md` and in your checkpoint messages as: what you ran, what it printed, what is green, what is red, what is unimplemented. Paste real command output. Never summarize a test run you did not execute. When a gate fails, report the failure and stop; do not weaken the assertion, delete the gate, or mark the milestone green. If a gate must be relaxed, it takes a `WAIVER.md` entry with rationale and date, and the waiver surfaces in the README status table.

Never claim:

- that a test passes without having run it in this session and shown the output;
- that SPECTRA proves anything about a real system, prevents anything, or would have stopped an attacker;
- that a cut is minimum, exact, or that "no smaller cut exists" on a certificate whose minimality field is not `EXACT`;
- that a run is ROBUST when any soundness-affecting flag is set;
- any number you did not measure, including approximate, illustrative, or "roughly" numbers;
- that a language, module, or milestone is done when its gate is skipped, stubbed, or quarantined.

When you are uncertain, say so in the same sentence as the claim. Understating what works is free; overstating it is the one failure this project cannot absorb.

Begin by reading `docs/prompt/SPECTRA_MASTER_PROMPT.md`.
