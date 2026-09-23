// The renderer: what the page says about each part of a certificate.
//
// Everything here works on strings. The DOM is not exercised, deliberately: `view.js`
// places text nodes and decides no wording, so a test of the wording has nothing to gain
// from a browser and would lose the ability to run at all offline.

import assert from "node:assert/strict";
import { test } from "node:test";

import { parseCertificate, parseLiveness } from "../src/cert.js";
import {
  renderBudgets,
  renderCounts,
  renderCut,
  renderCutDelta,
  renderDisputes,
  renderDocument,
  renderGoals,
  renderInputs,
  renderLicences,
  renderPlainText,
  renderPremium,
  renderVerdict,
  renderWitnesses,
  renderedStrings,
  verdictLong,
  verdictShort,
} from "../src/render.js";
import { MODEL_STATEMENT, STRINGS } from "../src/strings.js";
import {
  SCOPE,
  certificate,
  livenessWithDispute,
  livenessWithoutDispute,
  currentCertificates,
} from "./fixtures.js";

const body = () => certificate().body;
const textOf = (section) => section.lines.map((entry) => entry.text);

test("the short rendering carries the token, six digests and the attacker model", () => {
  const rendered = verdictShort(body().verdict, SCOPE);
  assert.equal(
    rendered,
    "ROBUST(rules@b2b256:aaaaaaaa, controls@b2b256:cccccccc, " +
      "liveness@b2b256:11111111, er@b2b256:eeeeeeee, goal@b2b256:99999999, " +
      "bundle@b2b256:bbbbbbbb, non-adaptive) [EXACT_PSI_RELATIVE]",
  );
});

test("the long rendering ends with the model statement", () => {
  const lines = verdictLong(body().verdict, SCOPE);
  assert.equal(lines.at(-1), MODEL_STATEMENT);
});

test("extra lines land before the ending, never after it", () => {
  const lines = verdictLong(body().verdict, SCOPE, ["an added line"]);
  assert.equal(lines.at(-1), MODEL_STATEMENT);
  assert.equal(lines.at(-3), "an added line");
});

test("the verdict section is the long rendering, so it ends with the model statement", () => {
  const section = renderVerdict(body());
  assert.equal(textOf(section).at(-1), MODEL_STATEMENT);
  assert.equal(section.lines[0].tone, "token");
});

test("an absent witness class is said to be absent rather than left blank", () => {
  const section = renderVerdict(body());
  assert.ok(
    textOf(section).some((text) => text.includes(STRINGS.verdict.witnessClassAbsent)),
  );
});

test("a published witness class is rendered with its clause", () => {
  const document = body();
  document.verdict = { ...document.verdict, witness_class: "LICENSED" };
  const lines = verdictLong(document.verdict, SCOPE);
  assert.ok(lines.some((text) => text.startsWith("Witness: the witness contains")));
});

test("a flag that is set is rendered with what it does to the verdict", () => {
  const document = body();
  document.verdict = { ...document.verdict, flags: ["corridor_cap"] };
  const text = textOf(renderVerdict(document));
  assert.ok(text.some((entry) => entry.includes("Flags set: corridor_cap.")));
  assert.ok(text.some((entry) => entry.includes("caps minimality at SUBSET")));
});

test("the cut names the raised controls and every threshold literal under them", () => {
  const text = textOf(renderCut(body()));
  assert.ok(text.some((entry) => entry.includes("ctl:egress_seg >= 2")));
  assert.ok(text.some((entry) => entry.includes("2 raised control(s)")));
  assert.equal(
    text.filter((entry) => entry.includes("at level")).length,
    3,
    "three literals, because egress_seg is raised to level two",
  );
});

test("a cut that raises nothing says so", () => {
  const text = textOf(renderCut(certificate({ cut: [] }).body));
  assert.ok(text.includes(STRINGS.cut.none));
});

test("the premium is a set of control ids and carries its definition in the heading", () => {
  const section = renderPremium(body());
  assert.ok(section.heading.includes("NEC(Psi_max)"));
  assert.ok(textOf(section).some((entry) => entry === "B   ctl:priv_approval"));
});

test("an absent premium is reported as omitted entirely, not as zero or empty", () => {
  const document = certificate({ premium_suppressed_reason: "solver_budget" }).body;
  delete document.premium;
  const text = textOf(renderPremium(document));
  assert.ok(text[0].includes("ABSENT"));
  assert.ok(text[0].includes("not null, not [] and not 0"));
});

test("a premium control with a calibration deficiency is not blamed on a blind sensor", () => {
  const document = body();
  document.premium.per_control[0].calibration_deficiency = { den: 4, num: 1 };
  const text = textOf(renderPremium(document));
  assert.ok(text.some((entry) => entry.includes("calibration_deficiency 1/4")));
  assert.ok(text.some((entry) => entry.includes(STRINGS.premium.phraseUncalibrated)));
  assert.ok(!text.some((entry) => entry.includes(STRINGS.premium.phraseObservedGap)));
});

test("a licence row carries its interval, basis, reason and whether it has a witness", () => {
  const text = textOf(renderLicences(body()));
  assert.ok(text.some((entry) => entry.includes("BLIND/B_PROFILE_INSUFFICIENT")));
  assert.ok(text.some((entry) => entry.includes(STRINGS.licences.witnessBlind)));
  assert.ok(text.some((entry) => entry.includes("bracketed by 2 record id(s)")));
});

test("licence spans are computed with BigInt, so a two-hour interval is 120 minutes", () => {
  const text = textOf(renderLicences(body()));
  assert.ok(text.some((entry) => entry.includes("120 min")));
});

test("a licence resting on a disputed instant is marked as retained", () => {
  const events = livenessWithDispute().disputed_events;
  const text = textOf(renderLicences(body(), events));
  assert.equal(
    text.filter((entry) => entry === STRINGS.licences.restsOnDisputed).length,
    1,
  );
});

test("the witness tree is rebuilt from the indices and indented by depth", () => {
  const section = renderWitnesses(body());
  const steps = section.lines.filter((entry) => entry.text.includes("rl:r000"));
  assert.deepEqual(
    steps.map((entry) => entry.indent),
    [1, 2, 3],
  );
  assert.ok(steps[0].text.includes("OBSERVED"));
  assert.ok(steps[1].text.includes("LICENSED"));
  assert.ok(steps[2].text.includes("GHOST"));
});

test("a witness entry counts its unobserved steps without calling them events", () => {
  const text = textOf(renderWitnesses(body()));
  assert.ok(
    text.some((entry) => entry.includes("without ctl:egress_seg: 3 step(s), 2 unobserved")),
  );
});

test("a malformed node list is reported and the entry is not drawn", () => {
  const document = body();
  document.witnesses = [{ removed_control: "ctl:x", nodes: [{ children: [5] }] }];
  const text = textOf(renderWitnesses(document));
  assert.ok(text.some((entry) => entry.startsWith("witness 0 could not be rebuilt")));
  assert.ok(!text.some((entry) => entry.includes("without ctl:x")));
});

test("no witness at all is said to be no witness, with why one can be dropped", () => {
  const text = textOf(renderWitnesses(certificate({ witnesses: [] }).body));
  assert.ok(text.includes(STRINGS.witnesses.none));
  assert.ok(text.includes(STRINGS.witnesses.noneNote));
});

test("with no liveness document the dispute section says it did not read one", () => {
  const text = textOf(renderDisputes(body(), null));
  assert.deepEqual(text, [STRINGS.disputes.unknown]);
  assert.ok(!text.includes(STRINGS.disputes.none), "silence is not the same as none");
});

test("with a liveness document carrying no dispute, the narrowness of the pass is stated", () => {
  const liveness = parseLiveness(livenessWithoutDispute());
  const text = textOf(renderDisputes(body(), liveness));
  assert.ok(text.includes(STRINGS.disputes.none));
  assert.ok(text.includes(STRINGS.disputes.narrowness));
});

test("a disputed timestamp names its event and the licences that rest on it", () => {
  const liveness = parseLiveness(livenessWithDispute());
  const text = textOf(renderDisputes(body(), liveness));
  assert.ok(text.some((entry) => entry.includes("1 recorded timestamp(s)")));
  assert.ok(text.some((entry) => entry.includes("ev:c9f5c0c3ef5c102158a5b662e85a6c0e")));
  assert.ok(text.some((entry) => entry.includes("1 licence(s) rest on a disputed")));
  assert.ok(
    text.some((entry) =>
      entry.includes("lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367"),
    ),
  );
});

test("no counterfactual verdict is rendered, because the certificate carries none", () => {
  const liveness = parseLiveness(livenessWithDispute());
  const text = textOf(renderDisputes(body(), liveness)).join("\n");
  for (const token of ["ROBUST", "OPTIMISTIC_ONLY", "UNSAFE", "INDETERMINATE"]) {
    assert.ok(!text.includes(token), `${token} must not appear in the dispute section`);
  }
});

test("the two counts are rendered apart and never added", () => {
  const text = textOf(renderCounts(body())).join("\n");
  assert.ok(text.includes("observed_event_count   5"));
  assert.ok(text.includes("ghost_count   41"));
  assert.ok(!/\b46\b/.test(text), "5 + 41 must not appear anywhere");
});

test("goals, residual, delta, inputs and budgets each render", () => {
  assert.ok(textOf(renderGoals(body())).length > 0);
  const delta = textOf(renderCutDelta(body()));
  assert.equal(delta[0], "cut_delta_canonical = {ctl:priv_approval}");
  assert.ok(delta[1].includes("not the blindness premium"));
  assert.ok(textOf(renderInputs(body())).some((entry) => entry.includes("blake2b-256")));
  assert.ok(textOf(renderBudgets(body())).some((entry) => entry.includes("step_budget")));
});

test("an empty canonical difference renders as empty rather than as a bare brace pair", () => {
  const delta = textOf(renderCutDelta(certificate({ cut_delta_canonical: [] }).body));
  assert.equal(delta[0], "cut_delta_canonical = {(empty)}");
});

test("a scope member disagreeing with its input digest is shown as both values", () => {
  const document = body();
  document.scope = { ...document.scope, rules: "b2b256:deadbeef" };
  const text = textOf(renderInputs(document));
  assert.ok(text.some((entry) => entry.startsWith("rules: scope b2b256:deadbeef differs")));
});

test("the whole document renders and the plain text ends with the model statement", () => {
  const sections = renderDocument(parseCertificate(certificate()), null);
  assert.equal(sections.at(-1).id, "footer");
  const text = renderPlainText(sections);
  assert.ok(text.endsWith(MODEL_STATEMENT));
  assert.ok(renderedStrings(sections).includes(MODEL_STATEMENT));
});

test("every certificate present in runs/ renders end to end", () => {
  for (const entry of currentCertificates()) {
    const parsed = parseCertificate(entry.text);
    const liveness = entry.liveness ? parseLiveness(entry.liveness) : null;
    const text = renderPlainText(renderDocument(parsed, liveness));
    assert.ok(text.endsWith(MODEL_STATEMENT), `${entry.id} ends with the statement`);
    assert.ok(text.length > 500, `${entry.id} rendered something`);
  }
});
