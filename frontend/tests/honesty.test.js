// The honesty rules, as executable checks.
//
// These are the tests that make the viewer's claims about itself falsifiable. They scan
// two populations: every string in the catalog, and every string the renderer produces
// from a fixture certificate, from a fixture with the opposite shape (absent premium,
// no witness, flags set, a disputed timestamp), and from every real certificate present
// in `runs/`.
//
// The three gates these stand in for are `G-UI-BANNED` (no catalog string matches a
// banned pattern in CLAIMS.md), `G-UI-STRINGS` (no user-visible literal outside the
// catalog) and the runtime half of BP-08 (a mode string is never a bare token). None of
// the three exists yet; when they do, they read the same two populations these do.

import assert from "node:assert/strict";
import { test } from "node:test";

import { parseCertificate, parseLiveness } from "../src/cert.js";
import { renderDocument, renderPlainText, renderedStrings } from "../src/render.js";
import { MODEL_STATEMENT, catalogEntries } from "../src/strings.js";
import {
  certificate,
  livenessWithDispute,
  livenessWithoutDispute,
  currentCertificates,
} from "./fixtures.js";

/** The four safety tokens BP-08 governs. */
const VERDICT_TOKENS = ["ROBUST", "OPTIMISTIC_ONLY", "UNSAFE", "INDETERMINATE"];

/**
 * A rendering of every shape the page has to handle, as flat strings with a label saying
 * which shape produced each one.
 *
 * @returns {Array<{label: string, text: string}>}
 */
function everyRenderedString() {
  const out = [];
  const push = (label, sections) => {
    for (const text of renderedStrings(sections)) out.push({ label, text });
    out.push({ label: `${label} (plain text)`, text: renderPlainText(sections) });
  };

  push("fixture", renderDocument(parseCertificate(certificate()), null));
  push(
    "fixture with a dispute",
    renderDocument(
      parseCertificate(certificate()),
      parseLiveness(livenessWithDispute()),
    ),
  );
  push(
    "fixture without a dispute",
    renderDocument(
      parseCertificate(certificate()),
      parseLiveness(livenessWithoutDispute()),
    ),
  );

  // The opposite shape of every optional member, so a sentence that only appears in the
  // unusual case is scanned too.
  const sparse = certificate({
    cut: [],
    cut_delta_canonical: [],
    licenses: [],
    premium_suppressed_reason: "corridor_cap",
    witnesses: [],
  });
  delete sparse.body.premium;
  sparse.body.residual = { ...sparse.body.residual, corridors_exhaustive: false };
  sparse.body.budgets = { ...sparse.body.budgets, budget_exhausted: true };
  sparse.body.verdict = {
    ...sparse.body.verdict,
    flags: ["corridor_cap", "er_ambiguous"],
    minimality: "SUBSET",
    witness_class: "CONTESTED",
  };
  push("sparse fixture", renderDocument(parseCertificate(sparse), null));

  // Each safety value in turn, so every clause in the table is scanned.
  for (const safety of VERDICT_TOKENS) {
    const document = certificate();
    document.body.verdict = { ...document.body.verdict, safety };
    push(`fixture with safety ${safety}`, renderDocument(parseCertificate(document), null));
  }

  // A malformed witness, so the refusal wording is scanned.
  const malformed = certificate({
    witnesses: [{ removed_control: "ctl:x", nodes: [{ children: [9] }] }],
  });
  push("fixture with a malformed witness", renderDocument(parseCertificate(malformed), null));

  for (const entry of currentCertificates()) {
    push(
      `runs/${entry.id}`,
      renderDocument(
        parseCertificate(entry.text),
        entry.liveness ? parseLiveness(entry.liveness) : null,
      ),
    );
  }
  return out;
}

/**
 * Every occurrence of a verdict token that is not immediately followed by `(`. That is
 * BP-08's own test: the token in a verdict position is the one the reader remembers, and
 * the scope binding is what makes it true of anything.
 *
 * @param {string} text
 * @returns {string[]}
 */
export function bareVerdictTokens(text) {
  const pattern = new RegExp(`\\b(${VERDICT_TOKENS.join("|")})\\b`, "g");
  const found = [];
  for (const match of text.matchAll(pattern)) {
    const next = text[match.index + match[0].length];
    if (next !== "(") found.push(match[0]);
  }
  return found;
}

test("no rendered string contains a bare verdict token", () => {
  for (const { label, text } of everyRenderedString()) {
    assert.deepEqual(
      bareVerdictTokens(text),
      [],
      `${label}: a verdict token must be followed by its scope: ${text}`,
    );
  }
});

test("no catalog string contains a verdict token at all", () => {
  // Stronger than BP-08 and deliberately so: the only place a token may be placed next
  // to a literal is `verdictShort`, which reads it out of the certificate. A token
  // written into the catalog would be a token some future caller could print alone.
  for (const { path, value } of catalogEntries()) {
    assert.deepEqual(
      bareVerdictTokens(value),
      [],
      `${path}: the catalog holds no verdict token`,
    );
  }
});

test("the bare-token check is not vacuous", () => {
  assert.deepEqual(bareVerdictTokens("the verdict is ROBUST"), ["ROBUST"]);
  assert.deepEqual(bareVerdictTokens("mode: UNSAFE"), ["UNSAFE"]);
  assert.deepEqual(bareVerdictTokens("ROBUST(rules@b2b256:aaaaaaaa, non-adaptive)"), []);
});

test("the model statement is present, exact, and last", () => {
  for (const { label, text } of everyRenderedString()) {
    if (!text.includes("\n")) continue;
    assert.ok(
      text.endsWith(MODEL_STATEMENT),
      `${label}: a long rendering ends with the model statement`,
    );
  }
  const sections = renderDocument(parseCertificate(certificate()), null);
  assert.ok(renderedStrings(sections).includes(MODEL_STATEMENT));
  assert.equal(
    MODEL_STATEMENT,
    "This is a statement about the model, not about the system.",
  );
});

test("the verdict section itself ends with the model statement, not only the page", () => {
  const sections = renderDocument(parseCertificate(certificate()), null);
  const verdict = sections.find((section) => section.id === "verdict");
  assert.equal(verdict.lines.at(-1).text, MODEL_STATEMENT);
});

/**
 * The banned-phrase table of `CLAIMS.md`, as far as it is mechanical. The rows that
 * depend on reading a sentence -- BP-08's verdict POSITION, BP-13's citation backing,
 * BP-14's language count, BP-15's subject -- are covered by the dedicated tests above
 * and below rather than by a regular expression that would be wrong.
 */
const BANNED = [
  { id: "BP-01", re: /prov\w*\s+(that\s+)?the attack would have been prevented/i },
  { id: "BP-02", re: /\bguarantee[sd]?\b/i },
  { id: "BP-03", re: /\bdetects? all\b|\bcatches every\b|\bzero false negatives?\b/i },
  { id: "BP-04", re: /\bAI[- ]powered\b|\bAI[- ]driven\b|\bintelligent\b/i },
  { id: "BP-05", re: /\breal[- ]time\b/i },
  {
    id: "BP-06",
    re: /enterprise[- ]grade|production[- ](ready|like)|battle[- ]tested|industry[- ]standard/i,
  },
  { id: "BP-07", re: /military[- ]grade|bank[- ]grade|unbreakable|bulletproof/i },
  {
    id: "BP-09",
    re: /which control would have prevented|would have stopped|what[- ]if control replay/i,
  },
  { id: "BP-10", re: /formally verified|\bproof of security\b/i },
  { id: "BP-11", re: /minimum cut(?! over the declared catalog)/i },
  { id: "BP-12", re: /\brealistic\b|\bmimics a real\b/i },
  {
    id: "BP-16",
    re: /\b(risk|confidence|threat|severity|likelihood)[ _-]?(score|rating|level|band|value|metric|index|weight)s?\b/i,
  },
  { id: "BP-16", re: /\b(score|confidence|severity|likelihood)\s*[:=]\s*[0-9]/i },
  {
    id: "BP-16",
    re: /\b(numeric|overall|aggregate|computed|final|scalar)\s+(score|confidence|severity|likelihood)\b/i,
  },
  { id: "BP-17", re: /\beasily\b|\b(simply|just)\s+(run|add|install|use|call|open|read)\b/i },
];

test("no catalog string matches a banned pattern", () => {
  for (const { path, value } of catalogEntries()) {
    for (const { id, re } of BANNED) {
      assert.ok(!re.test(value), `${path} matches ${id}: ${value}`);
    }
  }
});

test("no rendered string matches a banned pattern", () => {
  for (const { label, text } of everyRenderedString()) {
    for (const { id, re } of BANNED) {
      assert.ok(!re.test(text), `${label} matches ${id}: ${text}`);
    }
  }
});

test("the banned-phrase check is not vacuous", () => {
  const hits = (text) => BANNED.filter(({ re }) => re.test(text)).map(({ id }) => id);
  assert.deepEqual(hits("real-time threat detection"), ["BP-05"]);
  assert.ok(hits("SPECTRA guarantees the outcome").includes("BP-02"));
  assert.ok(hits("the minimum cut is two controls").includes("BP-11"));
  assert.ok(hits("confidence: 0.92").includes("BP-16"));
  assert.ok(hits("just run the server").includes("BP-17"));
});

/**
 * A licence is a permission for a step nobody could have seen. A GHOST is not an event.
 * These patterns are the four ways the viewer could have collapsed the distinction.
 */
const COLLAPSES = [
  { why: "a licence called an observation", re: /licen[cs]e[^.]{0,40}\bobservation\b/i },
  { why: "a licensed step called observed", re: /licen[cs]ed[^.]{0,20}\bobserved\b/i },
  { why: "a ghost called an event", re: /\bghost[^.]{0,20}\bevents?\b/i },
  { why: "ghosts and events counted together", re: /\btotal (events?|records?)\b/i },
  { why: "a silent step called a missed detection", re: /\bmissed (event|detection)/i },
];

test("no rendering collapses a licence into an observation or a ghost into an event", () => {
  for (const { label, text } of everyRenderedString()) {
    for (const { why, re } of COLLAPSES) {
      const match = text.match(re);
      // `licences.heading` says a licence "is not an observation", which is a mention of
      // the collapse in order to forbid it, not a use of it. That is the use/mention rule
      // CLAIMS.md states; it is applied here by requiring a negation before the match.
      if (match && !/\bis not\b|\bnever\b|\bnot an?\b/i.test(match[0])) {
        assert.fail(`${label}: ${why}: ${match[0]}`);
      }
    }
  }
});

test("the two counts are never summed in any rendering", () => {
  for (const entry of [certificate(), ...currentCertificates().map((r) => r.text)]) {
    const parsed = parseCertificate(entry);
    const observed = parsed.body.observed_event_count;
    const ghosts = parsed.body.ghost_count;
    const sum = observed + ghosts;
    const sections = renderDocument(parsed, null);
    const counts = sections.find((section) => section.id === "counts");
    const text = counts.lines.map((l) => l.text).join("\n");
    assert.ok(text.includes(String(observed)), "the observed count is shown");
    assert.ok(text.includes(String(ghosts)), "the ghost count is shown");
    if (sum !== observed && sum !== ghosts) {
      assert.ok(
        !new RegExp(`\\b${sum}\\b`).test(text),
        `the counts section must not contain ${sum}`,
      );
    }
  }
});

/** Ways a page could claim someone else checked the certificate. */
const INDEPENDENCE_CLAIMS = [
  /independently (verified|checked|validated|audited|confirmed)/i,
  /verified by an? (independent|third)/i,
  /third[- ]party (verification|check|audit)/i,
  /\bhas been verified\b/i,
  /\bthis certificate is valid\b/i,
  /\bsignature (is )?valid\b/i,
  /\bchecked by\b/i,
];

test("no string claims the certificate was checked here or by anyone else", () => {
  const population = [
    ...catalogEntries().map((entry) => ({ label: entry.path, text: entry.value })),
    ...everyRenderedString(),
  ];
  for (const { label, text } of population) {
    for (const re of INDEPENDENCE_CLAIMS) {
      assert.ok(!re.test(text), `${label} claims verification: ${text}`);
    }
  }
});

test("the page says in so many words that it checked nothing", () => {
  const sections = renderDocument(parseCertificate(certificate()), null);
  const text = renderPlainText(sections);
  assert.ok(text.includes("recomputes no digest"));
  assert.ok(text.includes("nothing it shows is a second opinion about the certificate"));
});
