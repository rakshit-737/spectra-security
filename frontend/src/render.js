// SPECTRA certificate viewer -- the renderer.
//
// Pure: a parsed certificate in, a list of sections out. Every section is
// `{ id, heading, lines }` and every line is `{ text, indent, tone }`. No DOM, no
// element, no event. `view.js` turns a section into nodes; this module decides what the
// words are, which is why the honesty rules are testable without a browser.
//
// EVERY LITERAL COMES FROM `strings.js`. A sentence assembled here is a catalog template
// filled with values read out of the certificate. That is what makes a future
// G-UI-STRINGS gate possible: one file to lint.
//
// THE FOUR RULES, AND WHERE THEY LIVE IN THIS FILE.
//
//   1. NO BARE VERDICT TOKEN. `verdictShort` is the only function in this package that
//      places a safety token next to a literal, and it carries the six scope digests and
//      the literal `non-adaptive` with it, exactly as `spectra_vs.cert.render_short`
//      does. `verdictLong` ends with `MODEL_STATEMENT`, and so does the whole page.
//   2. A LICENCE IS A PERMISSION FOR A STEP NOBODY COULD HAVE SEEN. `renderLicences`
//      never calls one an observation, and a GHOST node is never called an event.
//      `renderCounts` prints `observed_event_count` and `ghost_count` on two lines and
//      computes no total: they count different kinds, and a sum would assert they did
//      not.
//   3. THE BANNED-PHRASE TABLE in `CLAIMS.md` is normative for every template used here.
//   4. NOTHING SAYS THE CERTIFICATE WAS CHECKED. This page recomputes no digest and
//      replays no instance; `renderFooter` says so in the page rather than leaving the
//      absence to be inferred.

import {
  ATTACKER,
  CUT_DELTA_CAPTION,
  FLAG_EFFECT,
  HASH_REF_PREFIX,
  IMPLEMENTATION_NOTE,
  LICENCE_BASIS_CLAUSE,
  LICENCE_REASON_CLAUSE,
  MINIMALITY_CLAUSE,
  MODEL_STATEMENT,
  PREMIUM_SUPPRESSED_CLAUSE,
  SAFETY_CLAUSE,
  STRINGS,
  WITNESS_CLAUSE,
  WITNESS_NODE_BASIS,
  fill,
} from "./strings.js";
import {
  SCOPE_TO_INPUT,
  byteOrder,
  indexInstances,
  licenceDisputed,
  raisedControls,
  shortDigest,
} from "./cert.js";
import { WitnessShapeError, preorder, unobservedCount } from "./witness.js";

/** Nanoseconds in a minute, as a BigInt: an instant does not fit a double. */
const NS_PER_MINUTE = 60000000000n;

const line = (text, indent = 0, tone = "normal") => ({ text, indent, tone });
const note = (text, indent = 0) => line(text, indent, "note");

/**
 * The short rendering. The scope travels with the token; there is no bare-token form.
 * Mirrors `spectra_vs.cert.render_short`, member order included.
 *
 * @param {{safety: string, minimality: string}} verdict
 * @param {Record<string, string>} scope
 * @returns {string}
 */
export function verdictShort(verdict, scope) {
  const at = (member) => shortDigest(scope[member], HASH_REF_PREFIX);
  return (
    `${verdict.safety}(` +
    `rules@${at("rules")}, ` +
    `controls@${at("controls")}, ` +
    `liveness@${at("liveness")}, ` +
    `er@${at("er")}, ` +
    `goal@${at("goal")}, ` +
    `bundle@${at("bundle")}, ` +
    `${scope.attacker}) [${verdict.minimality}]`
  );
}

/**
 * The long rendering: the same content in prose, always ending with `MODEL_STATEMENT`.
 * Mirrors `spectra_vs.cert.render_long`.
 *
 * `extra` is spliced in before the implementation note and the model statement, so a
 * caller may add lines of its own and the rendering still ends with the sentence. There
 * is no parameter that moves or removes that ending.
 *
 * @param {object} verdict
 * @param {Record<string, string>} scope
 * @param {string[]} [extra]
 * @returns {string[]}
 */
export function verdictLong(verdict, scope, extra = []) {
  const lines = [verdictShort(verdict, scope)];
  const safety = SAFETY_CLAUSE[verdict.safety];
  if (safety) lines.push(`${STRINGS.verdict.safetyLabel}: ${safety}.`);
  const minimality = MINIMALITY_CLAUSE[verdict.minimality];
  if (minimality) lines.push(`${STRINGS.verdict.minimalityLabel}: ${minimality}.`);
  if (verdict.witness_class !== null && verdict.witness_class !== undefined) {
    const clause = WITNESS_CLAUSE[verdict.witness_class];
    if (clause) lines.push(`${STRINGS.verdict.witnessLabel}: ${clause}.`);
  }
  lines.push(
    `${STRINGS.verdict.scopeLabel}: ` +
      fill(STRINGS.verdict.scopeSentence, { attacker: scope.attacker || ATTACKER }),
  );
  const flags = verdict.flags || [];
  if (flags.length > 0) {
    lines.push(`${STRINGS.verdict.flagsLabel}: ${flags.join(", ")}.`);
  }
  const suppressed = verdict.derived_suppressed || [];
  if (suppressed.length > 0) {
    lines.push(`${STRINGS.verdict.derivedSuppressedLabel}: ${suppressed.join(", ")}.`);
  }
  lines.push(...extra);
  lines.push(IMPLEMENTATION_NOTE);
  lines.push(MODEL_STATEMENT);
  return lines;
}

/**
 * Section 1: the verdict, with the scope it is relative to.
 *
 * The section IS the long rendering, so it ends with `MODEL_STATEMENT` and nothing
 * follows it. Everything this page adds to `spectra_vs.cert.render_long` -- the note that
 * the token never travels alone, the realizability value, the effect of each flag set --
 * goes in through `extra`, which lands before the ending rather than after it.
 */
export function renderVerdict(body) {
  const verdict = body.verdict;
  const extra = [
    fill(STRINGS.verdict.tokenNote, { attacker: body.scope.attacker || ATTACKER }),
  ];
  if (verdict.witness_class === null || verdict.witness_class === undefined) {
    extra.unshift(
      `${STRINGS.verdict.witnessLabel}: ${STRINGS.verdict.witnessClassAbsent}.`,
    );
  }
  if (verdict.realizability) {
    extra.push(`${STRINGS.verdict.realizabilityLabel}: ${verdict.realizability}`);
  }
  const flags = verdict.flags || [];
  if (flags.length === 0) {
    extra.push(`${STRINGS.verdict.flagsLabel}: ${STRINGS.verdict.flagsNone}`);
  } else {
    for (const flag of flags) {
      const effect = FLAG_EFFECT[flag];
      if (effect) extra.push(`${flag}: ${effect}`);
    }
  }
  const lines = verdictLong(verdict, body.scope, extra).map((text, index) =>
    line(text, 0, index === 0 ? "token" : "normal"),
  );
  return { id: "verdict", heading: STRINGS.section.verdict, lines };
}

/** Section 2: the cut, and which controls it raises. */
export function renderCut(body) {
  const literals = body.cut;
  const raised = raisedControls(literals);
  const lines = [];
  if (raised.length === 0) {
    lines.push(line(STRINGS.cut.none));
  } else {
    lines.push(
      line(
        raised
          .map((entry) =>
            fill(STRINGS.cut.raisedFmt, { control: entry.control, level: entry.level }),
          )
          .join(", "),
      ),
    );
    lines.push(note(fill(STRINGS.cut.cardinalityFmt, { n: raised.length })));
    for (const literal of literals) {
      lines.push(
        line(
          fill(STRINGS.cut.literalFmt, {
            control: literal.control_id,
            level: literal.level,
            bit: literal.bit,
            rank: literal.rank,
          }),
          1,
        ),
      );
    }
    lines.push(note(STRINGS.cut.literalNote));
  }
  if (body.atoms && typeof body.atoms.n === "number") {
    lines.push(note(fill(STRINGS.cut.atomsFmt, { n: body.atoms.n, k: literals.length })));
  }
  lines.push(note(MINIMALITY_CLAUSE[body.verdict.minimality] || ""));
  return {
    id: "cut",
    heading: STRINGS.section.cut,
    lines: lines.filter((entry) => entry.text !== ""),
  };
}

/** Section 3: the blindness premium, or the reason it is absent. */
export function renderPremium(body) {
  const lines = [];
  const premium = body.premium;
  if (!premium) {
    const reason = body.premium_suppressed_reason;
    lines.push(line(fill(STRINGS.premium.absentFmt, { reason: String(reason) })));
    const clause = PREMIUM_SUPPRESSED_CLAUSE[reason];
    if (clause) lines.push(note(clause));
    return { id: "premium", heading: STRINGS.section.premium, lines };
  }
  const listOr = (values) =>
    values.length > 0 ? values.join(", ") : STRINGS.premium.empty;
  lines.push(line(`${STRINGS.premium.necLabel}   ${listOr(premium.nec_max)}`));
  lines.push(line(`${STRINGS.premium.occLabel}   ${listOr(premium.occ_min)}`));
  lines.push(
    line(`${STRINGS.premium.bLabel}   ${listOr(premium.blindness_premium)}`, 0, "strong"),
  );
  for (const entry of premium.per_control || []) {
    const num = entry.calibration_deficiency.num;
    const den = entry.calibration_deficiency.den;
    lines.push(
      line(
        fill(STRINGS.premium.perControlFmt, {
          control: entry.control_id,
          num,
          den,
          phrase:
            num > 0
              ? STRINGS.premium.phraseUncalibrated
              : STRINGS.premium.phraseObservedGap,
        }),
        1,
      ),
    );
    const licenceIds = entry.license_ids || [];
    if (licenceIds.length > 0) {
      lines.push(note(STRINGS.premium.licencesLabel, 2));
      for (const licenceId of licenceIds) lines.push(note(licenceId, 3));
    }
  }
  lines.push(note(STRINGS.premium.note));
  return { id: "premium", heading: STRINGS.section.premium, lines };
}

/**
 * Section 4: the licences relied on.
 *
 * A licence is a permission for a step nobody could have seen. Neither the heading nor
 * any row calls one an observation, and a BLIND licence says in the same breath that it
 * carries no witness -- because a reader who sees `witness` on the SUPPRESSED rows and
 * nothing on the BLIND ones would otherwise read the blank as a missing field.
 */
export function renderLicences(body, disputedEvents = null) {
  const licences = body.licenses;
  const lines = [note(STRINGS.licences.heading)];
  if (licences.length === 0) {
    lines.push(line(STRINGS.licences.none));
    return { id: "licences", heading: STRINGS.section.licences, lines };
  }
  lines.push(note(fill(STRINGS.licences.countFmt, { n: licences.length })));
  lines.push(note(fill(STRINGS.licences.silentFmt, { n: (body.silent || []).length })));
  for (const licence of licences) {
    const minutes = (BigInt(licence.t1_ns) - BigInt(licence.t0_ns)) / NS_PER_MINUTE;
    lines.push(
      line(
        fill(STRINGS.licences.rowFmt, {
          id: licence.license_id,
          source: licence.source_id,
          t0: licence.t0_ns,
          t1: licence.t1_ns,
          minutes: minutes.toString(),
          basis: licence.basis,
          reason: licence.reason,
        }),
      ),
    );
    const basisClause = LICENCE_BASIS_CLAUSE[licence.basis];
    if (basisClause) lines.push(note(basisClause, 1));
    const reasonClause = LICENCE_REASON_CLAUSE[licence.reason];
    if (reasonClause) lines.push(note(reasonClause, 1));
    lines.push(
      note(
        licence.basis === "BLIND"
          ? STRINGS.licences.witnessBlind
          : fill(STRINGS.licences.witnessBracketedFmt, {
              n: (licence.witness || []).length,
            }),
        1,
      ),
    );
    if (
      disputedEvents &&
      disputedEvents.length > 0 &&
      licenceDisputed(disputedEvents, licence.source_id, licence.t0_ns, licence.t1_ns)
    ) {
      lines.push(line(STRINGS.licences.restsOnDisputed, 1, "strong"));
    }
  }
  return {
    id: "licences",
    heading: STRINGS.section.licences,
    lines: lines.filter((entry) => entry.text !== ""),
  };
}

/**
 * Section 5: the witness trees, rebuilt from the flat node lists of ADR-0015.
 *
 * A node list that breaks one of the ADR's structural rules is reported on its own line
 * and the entry is not drawn. Repairing it would put on the screen a derivation the
 * certificate does not contain.
 */
export function renderWitnesses(body) {
  const lines = [];
  if (body.witnesses.length === 0) {
    lines.push(line(STRINGS.witnesses.none));
    lines.push(note(STRINGS.witnesses.noneNote));
    return { id: "witnesses", heading: STRINGS.section.witnesses, lines };
  }
  const instances = indexInstances(body.instances);
  lines.push(note(STRINGS.witnesses.heading));
  lines.push(note(STRINGS.witnesses.flatNote));
  body.witnesses.forEach((entry, index) => {
    const nodes = entry.nodes || [];
    let walk;
    try {
      walk = preorder(nodes);
    } catch (error) {
      if (!(error instanceof WitnessShapeError)) throw error;
      lines.push(
        line(
          fill(STRINGS.witnesses.malformedFmt, {
            index,
            reason: fill(STRINGS.witnessErrors[error.key] || error.key, error.values),
          }),
        ),
      );
      return;
    }
    lines.push(
      line(
        fill(STRINGS.witnesses.entryFmt, {
          control: entry.removed_control,
          n: nodes.length,
          unobserved: unobservedCount(nodes),
        }),
        0,
        "strong",
      ),
    );
    for (const step of walk) {
      const instance = instances.get(step.node.instance_id);
      const licenceIds = instance ? instance.license_ids || [] : [];
      const basis = fill(WITNESS_NODE_BASIS[step.node.kind] || "", {
        n: (step.node.evidence || []).length,
        lic: licenceIds.map((id) => shortDigest(id, "lic:")).join(", "),
      });
      lines.push(
        line(
          fill(STRINGS.witnesses.nodeFmt, {
            rule: instance ? instance.rule_id : step.node.instance_id,
            head: shortDigest(step.node.head, "fh:"),
            kind: step.node.kind,
            basis,
          }),
          step.depth + 1,
        ),
      );
    }
  });
  lines.push(note(STRINGS.witnesses.pmaxCaveat));
  return { id: "witnesses", heading: STRINGS.section.witnesses, lines };
}

/**
 * Section 6: the temporal dispute.
 *
 * The disputed timestamps are NOT in the certificate. ADR-0016 puts them in the run's
 * `liveness.json`, which the certificate pins by digest and does not carry. With no
 * liveness document open this section says it did not read one; it does not say there is
 * nothing disputed, because it does not know.
 */
export function renderDisputes(body, liveness = null) {
  const lines = [];
  if (liveness === null) {
    lines.push(line(STRINGS.disputes.unknown));
    return { id: "disputes", heading: STRINGS.section.disputes, lines };
  }
  const events = liveness.disputedEvents || [];
  if (events.length === 0) {
    lines.push(line(STRINGS.disputes.none));
    lines.push(note(STRINGS.disputes.narrowness));
    return { id: "disputes", heading: STRINGS.section.disputes, lines };
  }
  lines.push(line(fill(STRINGS.disputes.headingFmt, { n: events.length }), 0, "strong"));
  for (const event of events) {
    lines.push(
      line(
        fill(STRINGS.disputes.eventFmt, {
          event: event.event_id,
          source: event.source_id,
          t: event.t_evt_ns,
        }),
        1,
      ),
    );
  }
  const resting = body.licenses.filter((licence) =>
    licenceDisputed(events, licence.source_id, licence.t0_ns, licence.t1_ns),
  );
  if (resting.length === 0) {
    lines.push(line(STRINGS.disputes.licencesNone));
  } else {
    lines.push(line(fill(STRINGS.disputes.licencesFmt, { n: resting.length })));
    for (const licence of resting) lines.push(note(licence.license_id, 1));
  }
  lines.push(note(STRINGS.disputes.narrowness));
  return { id: "disputes", heading: STRINGS.section.disputes, lines };
}

/**
 * Section 7: the two counts.
 *
 * `observed_event_count` counts records. `ghost_count` counts obligation-forced heads
 * with no record behind them. They are different kinds, they are printed on separate
 * lines, and nothing here adds them: a total would be a number about a set that does not
 * exist.
 */
export function renderCounts(body) {
  return {
    id: "counts",
    heading: STRINGS.section.counts,
    lines: [
      line(fill(STRINGS.counts.observedFmt, { n: body.observed_event_count })),
      note(STRINGS.counts.observedClause, 1),
      line(fill(STRINGS.counts.ghostFmt, { n: body.ghost_count })),
      note(STRINGS.counts.ghostClause, 1),
      note(STRINGS.counts.note),
    ],
  };
}

/** Section 8: the goal library and the residual. */
export function renderGoals(body) {
  const lines = [];
  for (const goal of body.goals) {
    lines.push(
      line(
        `${goal.goal_key}   ${
          goal.derivable ? STRINGS.goals.derivableLabel : STRINGS.goals.underivableLabel
        }`,
      ),
    );
  }
  const residual = body.residual || {};
  const psi = body.psi || {};
  lines.push(
    note(
      fill(STRINGS.goals.corridorsFmt, {
        n: (psi.corridors || []).length,
        program: psi.program,
      }),
    ),
  );
  lines.push(
    note(psi.complete ? STRINGS.goals.corridorsComplete : STRINGS.goals.corridorsIncomplete),
  );
  lines.push(note(fill(STRINGS.goals.programFmt, { program: residual.program })));
  const list = (values) =>
    values && values.length > 0 ? values.join(", ") : STRINGS.goals.none;
  lines.push(line(`${STRINGS.goals.severedLabel}   ${list(residual.goals_severed)}`, 1));
  lines.push(line(`${STRINGS.goals.openLabel}   ${list(residual.corridors_open)}`, 1));
  lines.push(
    note(
      residual.corridors_exhaustive
        ? STRINGS.goals.exhaustiveTrue
        : STRINGS.goals.exhaustiveFalse,
    ),
  );
  return { id: "goals", heading: STRINGS.section.goals, lines };
}

/**
 * Section 9: the canonical-representative difference.
 *
 * Its own section, with its caption, and deliberately not adjacent to the premium panel:
 * the premium is defined by the values of two optimisation problems over the corridor
 * databases, and this is the set difference of two chosen representatives.
 */
export function renderCutDelta(body) {
  const listed = body.cut_delta_canonical;
  return {
    id: "delta",
    heading: STRINGS.section.delta,
    lines: [
      line(
        fill(STRINGS.delta.fmt, {
          listed: listed.length > 0 ? listed.join(", ") : STRINGS.delta.empty,
        }),
      ),
      note(CUT_DELTA_CAPTION),
    ],
  };
}

/** Section 10: the schema, the digests and the provenance of the inputs. */
export function renderInputs(body) {
  const schema = body.schema;
  const inputs = body.inputs;
  const lines = [
    line(
      fill(STRINGS.inputs.schemaFmt, {
        v: schema.v,
        min: schema.min_checker,
        profile: schema.profile,
      }),
    ),
    line(
      fill(STRINGS.inputs.algorithmFmt, {
        algorithm: schema.hash_algorithm,
        prefix: HASH_REF_PREFIX,
      }),
    ),
  ];
  if (schema.hash_substitution_note) lines.push(note(schema.hash_substitution_note));
  lines.push(line(fill(STRINGS.inputs.seedFmt, { seed: inputs.seed, k: inputs.k })));
  lines.push(
    line(
      fill(STRINGS.inputs.groundingFmt, {
        mode: inputs.grounding_mode,
        provenance: inputs.bundle_provenance,
      }),
    ),
  );
  lines.push(
    line(fill(STRINGS.inputs.implementationFmt, { implementation: inputs.implementation })),
  );
  const hashNames = Object.keys(inputs)
    .filter((name) => name.endsWith("_hash"))
    .sort(byteOrder);
  for (const name of hashNames) {
    lines.push(line(fill(STRINGS.inputs.hashRowFmt, { name, value: inputs[name] }), 1));
  }
  const mismatches = SCOPE_TO_INPUT.filter(
    ([member, input]) => body.scope[member] !== inputs[input],
  );
  lines.push(note(STRINGS.inputs.scopeBindNote));
  for (const [member, input] of mismatches) {
    lines.push(
      line(
        fill(STRINGS.inputs.scopeBindMismatchFmt, {
          member,
          scope: body.scope[member],
          input: inputs[input],
        }),
        1,
        "strong",
      ),
    );
  }
  return { id: "inputs", heading: STRINGS.section.inputs, lines };
}

/** Section 11: the deterministic budget counters. */
export function renderBudgets(body) {
  const budgets = body.budgets;
  const lines = Object.keys(budgets)
    .sort(byteOrder)
    .map((name) =>
      line(fill(STRINGS.budgets.rowFmt, { name, value: String(budgets[name]) }), 1),
    );
  lines.push(
    note(budgets.budget_exhausted ? STRINGS.budgets.exhausted : STRINGS.budgets.notExhausted),
  );
  return { id: "budgets", heading: STRINGS.section.budgets, lines };
}

/**
 * Section 12: what this page is.
 *
 * The last section, and the last line of the page is `MODEL_STATEMENT`. Between them:
 * that this page checked nothing, and that a checker in this repository agreeing with the
 * emitter is not a second party's agreement.
 */
export function renderFooter(certHash) {
  const lines = [];
  if (certHash) {
    lines.push(line(fill(STRINGS.footer.certHashFmt, { hash: certHash })));
    lines.push(note(STRINGS.footer.certHashNote));
  }
  lines.push(note(STRINGS.footer.whatThisIs));
  lines.push(note(STRINGS.footer.sharedAuthor));
  lines.push(note(IMPLEMENTATION_NOTE));
  lines.push(line(MODEL_STATEMENT, 0, "strong"));
  return { id: "footer", heading: STRINGS.section.footer, lines };
}

/**
 * The whole page, in order.
 *
 * @param {{body: object, certHash: string|null}} certificate
 * @param {{disputedEvents: Array<object>}|null} liveness
 * @returns {Array<{id: string, heading: string, lines: Array<object>}>}
 */
export function renderDocument(certificate, liveness = null) {
  const { body, certHash } = certificate;
  const disputedEvents = liveness ? liveness.disputedEvents : null;
  return [
    renderVerdict(body),
    renderCut(body),
    renderPremium(body),
    renderLicences(body, disputedEvents),
    renderWitnesses(body),
    renderDisputes(body, liveness),
    renderCounts(body),
    renderGoals(body),
    renderCutDelta(body),
    renderInputs(body),
    renderBudgets(body),
    renderFooter(certHash),
  ];
}

/**
 * The same rendering as text. Ends with `MODEL_STATEMENT`, because the page it mirrors
 * does.
 *
 * @param {Array<{heading: string, lines: Array<object>}>} sections
 * @returns {string}
 */
export function renderPlainText(sections) {
  const out = [];
  for (const section of sections) {
    if (out.length > 0) out.push("");
    out.push(section.heading);
    for (const entry of section.lines) {
      out.push(`${"  ".repeat(entry.indent + 1)}${entry.text}`);
    }
  }
  return out.join("\n");
}

/**
 * Every rendered string of a document, flattened. What a test scans for a bare verdict
 * token, a banned phrase or a missing model statement.
 *
 * @param {Array<{heading: string, lines: Array<object>}>} sections
 * @returns {string[]}
 */
export function renderedStrings(sections) {
  const out = [];
  for (const section of sections) {
    out.push(section.heading);
    for (const entry of section.lines) out.push(entry.text);
  }
  return out;
}
