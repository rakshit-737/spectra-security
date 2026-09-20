# SPECTRA NON-GOALS

Source: build specification Part II, section 75.1. This list is normative and prior to any
ambition stated elsewhere in the specification. It is linked from the README's first screen next
to `LIMITATIONS.md`.

Status of this document: delivered. Status of every subsystem it names: not started.

Gate note (TODO — decision made here, change it deliberately): the claims gate bans several
phrases from every externally visible artifact, and this file must quote some of them in order to
ban them. `docs/NON-GOALS.md` is therefore registered as an exempt path in `docs/banned.toml`,
alongside `docs/claims-policy.md`. To change this later: either stop quoting the phrases in items
10 and 11, or drop the exemption — but never leave the file unexempted while it still quotes them,
because the gate will then fail on the project's own policy document.

Registration note (TODO — decision made here): every item below is a `kind: NEGATIVE` claim and
must acquire a `CLM-####` record in the claims registry before the docs gate is switched on. No
records exist yet; see `CLAIMS.md`, which currently has zero rows.

## The list

1. **SPECTRA is not a detector.** It does not classify live traffic, score alerts, or decide that
   an attack is occurring. It reconstructs over a finished, bounded telemetry bundle. There is no
   streaming mode, no online inference, and no "real-time" claim anywhere in the repository.

2. **SPECTRA is not an incident-response product and produces no defensive prioritization advice.**
   The minimum cut is a statement about a recorded, non-adaptive hypothesis set under a declared
   catalog. A real adversary re-plans around the cut. Forbidden claim: "SPECTRA tells you which
   control to buy."

3. **SPECTRA does not prove anything about a real system.** It proves properties of the model: the
   rule table, the entity resolution, the control catalog, and the ingested telemetry. Forbidden
   claims: "formally verified", "guaranteed", "would have stopped the attacker", "prevents".

4. **SPECTRA does not execute, contain, or analyze malware.** No sample is downloaded, stored,
   detonated, or referenced by hash-for-retrieval. Scenario generators emit telemetry records only.

5. **SPECTRA does not attack any host it does not own.** No external target, no scanning, no
   network egress from any container in the scenario stack. There is no exploitation code path, and
   none is a stretch goal.

6. **SPECTRA emits no probability, confidence, score, severity, risk rating or likelihood.**
   Verdicts are structural: safety is one of `ROBUST(...)`, `OPTIMISTIC_ONLY(...)`, `UNSAFE(...)`,
   each rendered only with its scope binding; minimality is one of `EXACT`, `SUBSET`, `UNVERIFIED`.
   A numeric confidence field anywhere in the API, the database, the certificate or the frontend is
   a build failure, not a design choice.

7. **SPECTRA invents no costs.** With no user-authored `costs.toml` the Pareto frontier is
   disabled, never defaulted to unit cost. Any cardinality-mode axis is labelled "control count,
   not cost" in every axis label, API field name and export.

8. **SPECTRA does not claim completeness over attacker behavior.** The silent envelope admits
   exactly the hypotheses the hand-written rule table can express inside provably blind windows. It
   is not "every evidence-consistent hypothesis". This overrides Part I: the kernel one-liner's
   phrase "under every evidence-consistent hypothesis" is retired from every artifact and replaced
   by "under every hypothesis this rule table admits inside the licensed blind windows".

9. **SPECTRA is not a graph database, a SIEM, a log shipper, or a telemetry pipeline.** It does not
   compete with, replace or integrate into one. No connector, no agent, no forwarder.

10. **SPECTRA does not analyze software supply chains, build provenance, dependencies, SBOMs,
    signatures or artifact integrity.** That is WARDEN's domain and the boundary is non-negotiable:
    no SPECTRA subsystem may ingest a package manifest, a lockfile or a build attestation, and no
    WARDEN code may be vendored here. A CI grep over the source tree for supply-chain vocabulary
    outside `docs/NON-GOALS.md` fails the build.

11. **SPECTRA does not model an enterprise.** The scenario stack is a handful of containers. Banned
    phrases outside `docs/range/not-modeled.md`: "realistic", "enterprise-grade", "production-like",
    "real-world environment".

12. **SPECTRA is not a benchmark suite and publishes no leaderboard.** It reports its own
    measurements against its own baselines and ablations, with the run manifest hash attached, and
    compares itself to no third-party tool.

13. **SPECTRA does not use a language model anywhere in the deterministic core.** Narration is an
    optional, removable surface over the certificate. `make verify-no-llm` proves every gate stays
    green with the model absent and the dependency uninstalled. A failure of that target is a
    failure of the project's core claim, not of an optional feature.

14. **SPECTRA does not require a network at any point after clone.** No remote font, no remote
    schema, no package fetch at build or test time, no telemetry, no update check, no license
    server.

15. **SPECTRA's kernel and checker have no service dependencies.** `spectra prove` and
    `spectra verify` are pure file-in/file-out binaries. If either ever needs Postgres, Redis or a
    running API to produce or validate a certificate, the offline-verification claim has collapsed
    and the change is reverted.

16. **SPECTRA does not support multi-tenancy, authentication, RBAC, audit-for-compliance, or any
    deployment posture beyond one user on one machine.** No hosted instance is offered. No SaaS. No
    demo server on the public internet.

17. **SPECTRA does not guarantee that a language present in the repository is production-grade in
    that language.** Tier C and Tier D artifacts are small, single-purpose, and exist because they
    do one job the audit can prove is load-bearing. The repository never advertises expertise it has
    not demonstrated.

18. **SPECTRA does not claim novelty it has not tested.** The README's claim table, once it exists,
    will cite only green milestones and held-out results under a frozen rules hash. No claim table
    exists and the registry has zero records. An unbacked quantitative claim in `README.md` or
    `docs/` will fail the docs gate; the gate is not implemented and nothing enforces this today.

19. **SPECTRA is not the Eclipse Foundation, the Eclipse IDE, Eclipse Temurin, or Eclipse
    Adoptium.** The kernel name ECLIPSE is an internal acronym (Evidence-Licensed Cut Proofs over
    Silent Envelopes). The collision is stated in `README.md` and will be stated in
    `docs/naming.md` (not yet written); no Eclipse Foundation mark is used; user-facing prose
    prefers "the SPECTRA kernel" wherever confusion is possible. The string is banned outright in
    every crate, module, directory and file name.

20. **SPECTRA does not promise the polyglot surface will be complete.** The language surface is
    tiered and completed in tier order. An unfinished tier is stated as unfinished in the README's
    language table, which is hand-written until `make status` is implemented, never scaffolded
    to look finished.

## Negative requirement

Do not soften a non-goal into a "future work" bullet. A non-goal that acquires a roadmap entry
stops being a non-goal and must be deleted from this list, with the deletion recorded in
`BUILD_LOG.md`.

## Related documents

- `LIMITATIONS.md` — what the project does do, and how badly, once anything has been measured.
- `docs/descope-ladder.md` — what gets cut, in what order, when time runs out.
- `docs/range/not-modeled.md` — what the container range does not contain.
- `CLAIMS.md` — the registry binding every externally visible sentence to an artifact.
