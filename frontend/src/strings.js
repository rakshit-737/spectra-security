// SPECTRA certificate viewer -- THE STRING CATALOG.
//
// Owning spec sections: Part I 32.7, 39; Part II 75.2 C10. Gates that will read this
// file: G-UI-STRINGS (no user-visible literal outside the catalog) and G-UI-BANNED (no
// catalog string matches a banned pattern in CLAIMS.md).
//
// THE RULE THIS FILE EXISTS FOR. Every literal the reader can see is declared here and
// nowhere else. No other module in `frontend/src/` may contain a user-visible string
// literal; they compose the ones below with data read out of a certificate. A gate that
// has one file to lint can be written; a gate that has to find strings scattered over a
// view layer cannot.
//
// FOUR STANDING PROHIBITIONS, each of which a string below could violate:
//
//   1. No bare verdict token. `ROBUST`, `OPTIMISTIC_ONLY`, `UNSAFE` and `INDETERMINATE`
//      are placed next to a literal only by `verdictShort` in `render.js`, which carries
//      the six scope digests and the literal `non-adaptive` with them. This file holds no
//      safety token at all except inside the clause tables keyed BY the token, where the
//      token is a key and never a rendered word.
//   2. A licence is a permission for a step nobody could have seen. Never an observation.
//      A GHOST is never called an event. `observed_event_count` and `ghost_count` count
//      different kinds and are never summed.
//   3. The banned-phrase table in `CLAIMS.md` is normative for this file.
//   4. Nothing here says the certificate was independently verified, because nothing
//      checked it here. The viewer reads a file; it re-derives no digest and replays no
//      instance.
//
// The catalog is frozen at module load, so a view cannot mutate a sentence at runtime.

/** The sentence every long rendering ends with. Not optional and not paraphrasable. */
export const MODEL_STATEMENT =
  "This is a statement about the model, not about the system.";

/** Mirrors `spectra_vs.cert.IMPLEMENTATION_NOTE`. Carried into every long rendering. */
export const IMPLEMENTATION_NOTE =
  "PYTHON REFERENCE IMPLEMENTATION. Telemetry comes from a seeded synthetic generator, " +
  "never from a service. Digests are blake2b-256 labelled b2b256:, not the algorithm " +
  "the specification names.";

/** Mirrors `spectra_vs.cert.CUT_DELTA_CAPTION`. Travels wherever the delta is rendered. */
export const CUT_DELTA_CAPTION =
  "difference between two canonical representatives; not the blindness premium";

/** The attacker model the scope pins. Travels inside every verdict rendering. */
export const ATTACKER = "non-adaptive";

/** The label the hash prefix carries. Mirrors `spectra_core.canon.HASH_REF_PREFIX`. */
export const HASH_REF_PREFIX = "b2b256:";

/**
 * One sentence per safety value, keyed by the token. Mirrors
 * `spectra_vs.cert._SAFETY_CLAUSE` word for word. The key is a key; the value is what a
 * reader is shown, and none of the values contains a token.
 */
export const SAFETY_CLAUSE = Object.freeze({
  ROBUST:
    "the goal is underivable under this cut in the upper program, which unions every " +
    "licensed silent instance",
  OPTIMISTIC_ONLY:
    "the goal is underivable under this cut in the lower program and derivable in the " +
    "upper one, so the difference is what could not be seen",
  UNSAFE: "the goal is derivable under this cut in the lower program, with a witness",
  INDETERMINATE:
    "no other safety value was constructible, which is the fail-closed sink",
});

/** Mirrors `spectra_vs.cert._MINIMALITY_CLAUSE`. */
export const MINIMALITY_CLAUSE = Object.freeze({
  EXACT_EXHAUSTIVE:
    "a fixpoint was run for every cut one control smaller over the admissible lattice",
  EXACT_PSI_RELATIVE: "no smaller cut satisfies the enumerated corridor set",
  SUBSET:
    "no control can be removed from this cut; smaller cuts were not ruled out",
  UNVERIFIED:
    "no minimality probe ran, so nothing is claimed about the size of this cut",
});

/** Mirrors `spectra_vs.cert._WITNESS_CLAUSE`. */
export const WITNESS_CLAUSE = Object.freeze({
  OBSERVED: "every leaf of the witness cites a record in the hashed bundle",
  LICENSED:
    "the witness contains at least one silent step and depicts a hypothesis, not an " +
    "observation; the upper program may combine silent steps no single world realizes",
  CONTESTED: "entity resolution was ambiguous, so the leaves themselves are contested",
});

/**
 * One line per witness node kind. `{n}` is the record count, `{lic}` the licence ids.
 * OBSERVED cites records. The other two cite permission, and say so in that word.
 */
export const WITNESS_NODE_BASIS = Object.freeze({
  OBSERVED: "cites {n} record(s)",
  GHOST: "unobserved, obligation-forced; licence {lic}",
  LICENSED: "unobserved, licensed silent step; licence {lic}",
});

/** Why a licence exists. Mirrors `spectra_core.model.LicenceBasis`. */
export const LICENCE_BASIS_CLAUSE = Object.freeze({
  BLIND:
    "nobody could have seen this interval, so a step inside it is permitted without a record",
  SUPPRESSED:
    "the source's own sequence skipped, so a step between the two bracketing records is permitted",
  OBLIGATION:
    "a rule obliges the head, so the step is permitted with no record behind it",
});

/**
 * The closed reason vocabulary of `spectra_vs.liveness.Reason`, each in one clause.
 * The partition between the two families is load-bearing: a control that rests on a
 * calibration-deficiency reason may not be described as needed because a sensor was
 * blind.
 */
export const LICENCE_REASON_CLAUSE = Object.freeze({
  L_CALIBRATED_OK: "the interval was calibrated and carries no permission",
  B_FORCED_NO_PROFILE_MODE: "the run was forced to a mode that names no profile",
  B_REGIME_UNKNOWN: "this run was not calibrated for this source in this regime",
  B_PROFILE_INSUFFICIENT: "this run was not calibrated for this source",
  B_THRESHOLD_OVERFLOW: "the calibrated threshold saturated, so nothing was measured",
  B_CHAIN_UNVERIFIED: "the source's chain could not be verified over this span",
  B_UNBRACKETED: "no record brackets this span on either side",
  B_WINDOW_UNDERSAMPLED: "the calibration window held too few records to measure",
  B_GAP_EXCEEDS_THRESHOLD: "the delivered gap is longer than the calibrated threshold",
  S_CHAIN_SEQ_GAP: "the source's own sequence numbers skip across this span",
  S_SEQ_GAP_UNAUTHENTICATED: "the sequence skips and the chain is unauthenticated",
  B_INTERNAL_ERROR: "an internal failure was converted to blindness rather than raised",
});

/** `spectra_vs.cert.FLAGS`: one clause per flag, saying what it does to the verdict. */
export const FLAG_EFFECT = Object.freeze({
  grounding_capped: "blocks the universal claim",
  corridor_cap:
    "blocks the universal claim, caps minimality at SUBSET, suppresses derived products",
  atoms_over_budget: "caps minimality at SUBSET only",
  er_ambiguous: "blocks the universal claim and forces witness_class CONTESTED",
  quarantined_records: "blocks the universal claim",
  license_voided_by_suspected_tampering:
    "never set in this slice: the difference-constraint pass is not implemented",
  greedy_cover: "forces the approximation factor inline",
  sampled_matrix: "blocks aggregate claims, not a per-run verdict",
  profile_missing: "blocks the universal claim",
});

/** Why the blindness premium is absent. `spectra_vs.cert.PREMIUM_SUPPRESSED_REASONS`. */
export const PREMIUM_SUPPRESSED_CLAUSE = Object.freeze({
  corridor_cap: "the corridor set was capped, so the two optimisations are not comparable",
  er_ambiguous: "entity resolution was ambiguous, so the instance set is contested",
  grounding_capped: "grounding was capped, so the upper program is not the whole upper program",
  horizon_truncated: "the horizon was truncated, so the two programs cover different spans",
  solver_budget: "the solver budget ran out before both optimisations finished",
});

/** Everything else the page can say, grouped by the panel that says it. */
export const STRINGS = Object.freeze({
  page: Object.freeze({
    title: "SPECTRA certificate viewer",
    subtitle: "A reader for one runs/<id>/cert.spcert. It renders; it checks nothing.",
    noscript:
      "This page renders a certificate with ES modules and no framework. With scripting " +
      "off there is nothing to show.",
    openLabel: "Open a certificate (.spcert)",
    openHint:
      "Pick a runs/<id>/cert.spcert. The file is read in the browser and is not uploaded.",
    livenessLabel: "Open the run's liveness.json (optional)",
    livenessHint:
      "The temporal dispute pass records disputed timestamps in liveness.json, not in " +
      "the certificate. Without it this page cannot say whether any timestamp is disputed.",
    empty: "No certificate is open.",
    emptyHint: "Open a certificate file to render it.",
    parseFailed: "This file could not be read as a certificate.",
    plainTextLabel: "Plain text",
    plainTextHint: "The same rendering as text, for pasting into a report.",
  }),

  section: Object.freeze({
    verdict: "Verdict, with the scope it is relative to",
    cut: "The cut: the controls it raises",
    premium: "Blindness premium   B = NEC(Psi_max) \\ OCC(Psi_min)",
    licences: "Licences relied on",
    witnesses: "Witness trees",
    disputes: "Temporal dispute",
    counts: "Two counts, kept apart",
    goals: "Goals and residual",
    delta: "Canonical-representative difference",
    inputs: "Inputs and digests",
    budgets: "Deterministic budget counters",
    footer: "What this page is",
  }),

  verdict: Object.freeze({
    safetyLabel: "Safety",
    minimalityLabel: "Minimality",
    witnessLabel: "Witness",
    scopeLabel: "Scope",
    scopeSentence:
      "this rule table, this control catalog, these licences, the telemetry actually " +
      "ingested, and a {attacker} attacker.",
    flagsLabel: "Flags set",
    flagsNone: "none",
    derivedSuppressedLabel: "Derived products omitted entirely",
    realizabilityLabel: "Realizability",
    witnessClassAbsent:
      "no witness class is published, so nothing is claimed about the leaves",
    tokenNote:
      "The token above never travels alone. It is true under this rule table, this " +
      "control catalog, these licences and a {attacker} attacker, and under nothing else.",
  }),

  cut: Object.freeze({
    none: "no control is raised",
    raisedFmt: "{control} >= {level}",
    cardinalityFmt: "{n} raised control(s)",
    literalFmt: "{control} at level {level}   bit {bit}   rank {rank}",
    literalNote:
      "One row per threshold literal. Raising a control to level L asserts levels 1..L, " +
      "so a control raised to level two contributes two rows.",
    atomsFmt:
      "The admissible lattice holds {n} threshold literal(s) in total; this cut names {k}.",
  }),

  premium: Object.freeze({
    necLabel: "NEC(Psi_max)",
    occLabel: "OCC(Psi_min)",
    bLabel: "B",
    empty: "EMPTY",
    absentFmt:
      "ABSENT. premium_suppressed_reason = {reason}. The member is omitted entirely, " +
      "not null, not [] and not 0.",
    perControlFmt: "{control}: calibration_deficiency {num}/{den} -- {phrase}",
    phraseUncalibrated: "needed because this run was not calibrated for this source",
    phraseObservedGap: "rests on observed-gap licences",
    licencesLabel: "resting on licence(s)",
    note:
      "B is the set difference of two optimisation results over the corridor databases. " +
      "It is a set of control ids and is not a number, a rank or an ordering.",
  }),

  licences: Object.freeze({
    none: "no licence is relied on",
    heading:
      "A licence is a permission for a step nobody could have seen. It is not an " +
      "observation, it cites no record for the step it permits, and a step taken under " +
      "one is a hypothesis.",
    rowFmt: "{id}   {source}   [{t0}, {t1})   {minutes} min   {basis}/{reason}",
    witnessBlind:
      "no witness (a BLIND licence records that nobody could have seen)",
    witnessBracketedFmt: "bracketed by {n} record id(s)",
    countFmt: "{n} licence(s)",
    restsOnDisputed:
      "rests on a disputed timestamp and is RETAINED in P_max; voiding it would reward " +
      "the tampering",
    silentFmt:
      "{n} instance(s) in the published set are silent steps taken under one of these " +
      "licences. A silent step cites no record for the step it takes.",
  }),

  witnesses: Object.freeze({
    none: "the certificate carries no witness tree",
    noneNote:
      "A derivation the certificate cannot express is dropped and reported, never forced " +
      "into the wrong node kind.",
    heading:
      "The derivation that returns when one control is dropped from the cut over P_max.",
    flatNote:
      "Published flat (ADR-0015): each node's children are indices into the entry's node " +
      "list, nodes[0] is the root, and every child index is greater than its parent's. " +
      "The indentation below is this page rebuilding the tree from those indices.",
    entryFmt: "without {control}: {n} step(s), {unobserved} unobserved",
    nodeFmt: "{rule}   {head}   {kind}   {basis}",
    pmaxCaveat:
      "Drawn from P_max: one tree may combine silent steps that no single consistent " +
      "world realizes.",
    malformedFmt: "witness {index} could not be rebuilt: {reason}",
  }),

  witnessErrors: Object.freeze({
    empty: "the node list is empty",
    childRangeFmt: "node {i} names child {c}, which is not a later node in the list",
    multipleParentsFmt: "node {c} is named by more than one parent",
    unreachableFmt: "node {c} is named by no parent and is not the root",
    rootReferencedFmt: "node 0 is named as a child of node {i}",
  }),

  disputes: Object.freeze({
    unknown:
      "Not read. The disputed timestamps live in the run's liveness.json, which is not " +
      "part of the certificate. Open that file to see them.",
    none:
      "No recorded timestamp contradicts the order its own source recorded. That is what " +
      "the pass checks and all it checks.",
    headingFmt:
      "{n} recorded timestamp(s) contradict their source's own order. The licences " +
      "resting on them are RETAINED in P_max; only the verdict is weakened. Voiding them " +
      "would reward the tampering.",
    eventFmt: "{event}   {source}   recorded at {t}",
    licencesFmt:
      "{n} licence(s) rest on a disputed timestamp and are RETAINED, recomputed on this " +
      "page from the licence intervals and the disputed instants.",
    licencesNone:
      "No licence rests on a disputed timestamp, so voiding them would have changed " +
      "nothing here either.",
    narrowness:
      "The pass compares recorded timestamps against the order their own source recorded, " +
      "and nothing else: a consistently rewritten source, a forged chain and suppression " +
      "on a source without a sequence number are all invisible to it.",
    mismatch:
      "This liveness document does not hash to the certificate's liveness digest, so the " +
      "two are not from the same run and nothing below is rendered.",
  }),

  counts: Object.freeze({
    observedFmt: "observed_event_count   {n}",
    observedClause: "records the bundle actually carries for the derivation",
    ghostFmt: "ghost_count   {n}",
    ghostClause:
      "obligation-forced heads with no record behind them; a ghost is not an event",
    note:
      "Two different kinds, counted separately and never added together. There is no " +
      "total here because a total would claim they were the same kind of thing.",
  }),

  goals: Object.freeze({
    derivableLabel: "derivable under this cut",
    underivableLabel: "underivable under this cut",
    severedLabel: "goals severed",
    openLabel: "corridors open",
    exhaustiveTrue: "the corridor set is enumerated exhaustively",
    exhaustiveFalse: "the corridor set is not exhaustive, so residual is partial",
    programFmt: "computed over {program}",
    corridorsFmt: "{n} corridor(s) enumerated over {program}",
    corridorsComplete: "the enumeration reached a fixpoint",
    corridorsIncomplete:
      "the enumeration did not reach a fixpoint, so corridors outside it are unexamined",
    none: "(empty)",
  }),

  delta: Object.freeze({
    fmt: "cut_delta_canonical = {{{listed}}}",
    empty: "(empty)",
  }),

  inputs: Object.freeze({
    schemaFmt: "schema {v}   min_checker {min}   profile {profile}",
    algorithmFmt: "digests: {algorithm}, labelled {prefix}",
    seedFmt: "seed {seed}   horizon k = {k} ticks",
    groundingFmt: "grounding_mode {mode}   bundle_provenance {provenance}",
    implementationFmt: "implementation {implementation}",
    hashRowFmt: "{name}   {value}",
    scopeBindNote:
      "Six scope members repeat an input digest. Where they differ the certificate is " +
      "not self-consistent, and this page shows both values rather than choosing one.",
    scopeBindMismatchFmt: "{member}: scope {scope} differs from inputs {input}",
  }),

  budgets: Object.freeze({
    rowFmt: "{name}   {value}",
    exhausted:
      "A budget was exhausted, so what was not explored is unexplored rather than absent.",
    notExhausted: "No budget was exhausted on this run.",
  }),

  footer: Object.freeze({
    whatThisIs:
      "This page reads one certificate file and renders it. It recomputes no digest, " +
      "replays no instance and checks no obligation, so nothing it shows is a second " +
      "opinion about the certificate.",
    sharedAuthor:
      "The emitter and the checker in this repository share an author, a language and a " +
      "reading of the same ADRs. A checker's acceptance is therefore not evidence from a " +
      "second party that the encoding is right.",
    certHashFmt: "cert_hash   {hash}",
    certHashNote:
      "Copied from the file. This page did not compute it and cannot say whether the " +
      "bytes hash to it.",
  }),

  errors: Object.freeze({
    notJson: "the file is not JSON",
    notObject: "the top level is not an object",
    missingFmt: "the member {member} is missing",
    typeFmt: "the member {member} has the wrong shape",
    schemaFmt:
      "schema.v is {v}; this page renders {expected}, and an older encoding nests witness " +
      "children instead of indexing them",
    magicFmt: "the file does not begin with the nine octets {magic}",
  }),
});

/**
 * Every string in the catalog, flattened, for a gate or a test that has to scan them.
 * Ordered by the path that reaches each one, so a failure names where to look.
 *
 * @returns {Array<{path: string, value: string}>}
 */
export function catalogEntries() {
  const roots = {
    MODEL_STATEMENT,
    IMPLEMENTATION_NOTE,
    CUT_DELTA_CAPTION,
    ATTACKER,
    HASH_REF_PREFIX,
    SAFETY_CLAUSE,
    MINIMALITY_CLAUSE,
    WITNESS_CLAUSE,
    WITNESS_NODE_BASIS,
    LICENCE_BASIS_CLAUSE,
    LICENCE_REASON_CLAUSE,
    FLAG_EFFECT,
    PREMIUM_SUPPRESSED_CLAUSE,
    STRINGS,
  };
  const out = [];
  const walk = (node, path) => {
    if (typeof node === "string") {
      out.push({ path, value: node });
      return;
    }
    if (node && typeof node === "object") {
      for (const key of Object.keys(node)) {
        walk(node[key], path ? `${path}.${key}` : key);
      }
    }
  };
  walk(roots, "");
  return out;
}

/**
 * Substitute `{name}` placeholders. Unknown placeholders are left in place rather than
 * replaced with the empty string, so a missing value shows up in the page as its own
 * name instead of as a silent blank.
 *
 * `{{` and `}}` are literal braces, which is how `delta.fmt` renders a set.
 *
 * @param {string} template
 * @param {Record<string, string|number>} values
 * @returns {string}
 */
export function fill(template, values) {
  return template.replace(/\{\{|\}\}|\{(\w+)\}/g, (match, name) => {
    if (match === "{{") return "{";
    if (match === "}}") return "}";
    return Object.prototype.hasOwnProperty.call(values, name)
      ? String(values[name])
      : match;
  });
}
