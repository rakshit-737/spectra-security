// SPECTRA certificate viewer -- reading a certificate document.
//
// This module is pure: text or an already-parsed object in, a normalized certificate or a
// thrown `CertificateError` out. It touches no DOM, imports no view, and holds no
// user-visible string literal -- every message it raises is a key into `strings.js` plus
// the values that fill it, so a caller decides how to show it and a gate has one file to
// lint.
//
// WHAT IT CHECKS AND WHAT IT DOES NOT. It checks shape: the nine-octet magic, the top
// level pair, the schema version, the presence and container type of every body member
// the viewer reads. It does NOT recompute `cert_hash`, does not recompute `instances_hash`
// over `body.instances`, does not replay an instance and does not walk an obligation.
// Reading this file is not checking it, and no rendering built on this module may say it
// is.
//
// SCHEMA 1.1 ONLY. ADR-0015 moved witness trees from a nested encoding to a flat node
// list indexed by integer, and moved `schema.v` and `schema.min_checker` from 1.0 to 1.1
// in the same commit. A 1.0 witness cannot be rebuilt by `witness.js`, so a 1.0 document
// is refused here rather than rendered wrongly.

/** Mirrors `spectra_vs.cert.SCHEMA_V`. The only version this page renders. */
export const SCHEMA_V = "1.1";

/** Mirrors `spectra_vs.cert.FILE_MAGIC`: nine octets, not the twenty-six the spec names. */
export const FILE_MAGIC = '{"body":{';

/**
 * Body members this viewer reads, each with the container it must be. A subset of
 * `spectra_vs.cert.BODY_MEMBERS`; a member absent from this table is carried through
 * untouched rather than refused, because a future schema may add one.
 */
export const REQUIRED_BODY_MEMBERS = Object.freeze({
  atoms: "object",
  budgets: "object",
  cut: "array",
  cut_delta_canonical: "array",
  ghost_count: "number",
  goals: "array",
  inputs: "object",
  instances: "array",
  licenses: "array",
  observed_event_count: "number",
  psi: "object",
  residual: "object",
  schema: "object",
  scope: "object",
  silent: "array",
  verdict: "object",
  witnesses: "array",
});

/** The seven scope members. Mirrors `spectra_vs.cert.SCOPE_MEMBERS`. */
export const SCOPE_MEMBERS = Object.freeze([
  "attacker",
  "bundle",
  "controls",
  "er",
  "goal",
  "liveness",
  "rules",
]);

/**
 * The scope member each input digest must equal. Mirrors `spectra_vs.cert.SCOPE_TO_INPUT`.
 * A disagreement is not repaired here; both values are carried to the renderer.
 */
export const SCOPE_TO_INPUT = Object.freeze([
  ["bundle", "bundle_hash"],
  ["controls", "controls_hash"],
  ["er", "er_hash"],
  ["goal", "goal_hash"],
  ["liveness", "liveness_hash"],
  ["rules", "rules_hash"],
]);

/**
 * A refusal to read a file. `key` names a member of `STRINGS.errors` and `values` fills
 * its placeholders, so the message is composed by the view and never by this module.
 */
export class CertificateError extends Error {
  /**
   * @param {string} key
   * @param {Record<string, string|number>} [values]
   */
  constructor(key, values = {}) {
    super(`${key} ${JSON.stringify(values)}`);
    this.name = "CertificateError";
    this.key = key;
    this.values = values;
  }
}

const isObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function requireMember(body, name, kind) {
  if (!Object.prototype.hasOwnProperty.call(body, name)) {
    throw new CertificateError("missingFmt", { member: name });
  }
  const value = body[name];
  const ok =
    kind === "array"
      ? Array.isArray(value)
      : kind === "object"
        ? isObject(value)
        : kind === "number"
          ? typeof value === "number" && Number.isFinite(value)
          : typeof value === "string";
  if (!ok) throw new CertificateError("typeFmt", { member: name });
  return value;
}

/**
 * Parse the octets of a `cert.spcert` (or an already-parsed document).
 *
 * @param {string|object} input
 * @returns {{body: object, certHash: string|null}}
 */
export function parseCertificate(input) {
  let document;
  if (typeof input === "string") {
    const text = input.replace(/^﻿/, "");
    if (!text.startsWith(FILE_MAGIC)) {
      throw new CertificateError("magicFmt", { magic: FILE_MAGIC });
    }
    try {
      document = JSON.parse(text);
    } catch {
      throw new CertificateError("notJson");
    }
  } else {
    document = input;
  }
  if (!isObject(document)) throw new CertificateError("notObject");

  const body = requireMember(document, "body", "object");
  const schema = requireMember(body, "schema", "object");
  if (schema.v !== SCHEMA_V) {
    throw new CertificateError("schemaFmt", {
      v: String(schema.v),
      expected: SCHEMA_V,
    });
  }
  for (const [name, kind] of Object.entries(REQUIRED_BODY_MEMBERS)) {
    requireMember(body, name, kind);
  }
  if (body.observed_event_count < 0 || body.ghost_count < 0) {
    throw new CertificateError("typeFmt", { member: "observed_event_count" });
  }
  for (const member of SCOPE_MEMBERS) {
    if (typeof body.scope[member] !== "string") {
      throw new CertificateError("typeFmt", { member: `scope.${member}` });
    }
  }
  const certHash =
    typeof document.cert_hash === "string" ? document.cert_hash : null;
  return { body, certHash };
}

/**
 * The first eight hex characters of a digest, behind the algorithm label. Mirrors
 * `spectra_vs.cert._short_digest`, which is what the scope carries in a rendered verdict.
 *
 * @param {string} value
 * @param {string} prefix
 * @returns {string}
 */
export function shortDigest(value, prefix) {
  const body = value.includes(":") ? value.slice(value.indexOf(":") + 1) : value;
  return prefix + body.slice(0, 8);
}

/**
 * The raised controls of a cut: one entry per control, at the highest level any of its
 * threshold literals asserts. Mirrors `spectra_vs.demo._raised`, including the byte order
 * of the control id.
 *
 * @param {Array<{control_id: string, level: number}>} literals
 * @returns {Array<{control: string, level: number}>}
 */
export function raisedControls(literals) {
  const levels = new Map();
  for (const literal of literals) {
    const key = literal.control_id;
    const previous = levels.get(key);
    levels.set(key, previous === undefined ? literal.level : Math.max(previous, literal.level));
  }
  return [...levels.entries()]
    .map(([control, level]) => ({ control, level }))
    .sort((a, b) => byteOrder(a.control, b.control));
}

/**
 * Byte order over UTF-8, which is the certificate's sort order everywhere. JavaScript's
 * default comparison is UTF-16 code-unit order, which differs above the BMP; the ids in a
 * certificate are ASCII, so this is the same order for them and stays correct if they
 * stop being.
 *
 * @param {string} a
 * @param {string} b
 */
export function byteOrder(a, b) {
  const left = new TextEncoder().encode(a);
  const right = new TextEncoder().encode(b);
  const n = Math.min(left.length, right.length);
  for (let i = 0; i < n; i += 1) {
    if (left[i] !== right[i]) return left[i] - right[i];
  }
  return left.length - right.length;
}

/**
 * Index the published instance set by instance id, so a witness node can be read against
 * the instance it cites.
 *
 * @param {Array<object>} instances
 * @returns {Map<string, object>}
 */
export function indexInstances(instances) {
  const out = new Map();
  for (const instance of instances) out.set(instance.instance_id, instance);
  return out;
}

/**
 * Whether a licence over `[t0, t1]` on `source` rests on a disputed instant. Mirrors
 * `spectra_vs.liveness.licence_disputed`, including its conservative reading: any
 * disputed event of the same source whose recorded instant lies in the CLOSED interval
 * disputes the licence.
 *
 * Nanosecond instants arrive as decimal strings because they do not fit a double, so the
 * comparison is done with BigInt and never with Number.
 *
 * @param {Array<{source_id: string, t_evt_ns: string|number}>} disputedEvents
 * @param {string} sourceId
 * @param {string|number} t0
 * @param {string|number} t1
 * @returns {boolean}
 */
export function licenceDisputed(disputedEvents, sourceId, t0, t1) {
  const wanted = sourceId.startsWith("src:") ? sourceId.slice(4) : sourceId;
  const lo = BigInt(t0);
  const hi = BigInt(t1);
  for (const event of disputedEvents) {
    const source = event.source_id.startsWith("src:")
      ? event.source_id.slice(4)
      : event.source_id;
    if (source !== wanted) continue;
    const instant = BigInt(event.t_evt_ns);
    if (lo <= instant && instant <= hi) return true;
  }
  return false;
}

/**
 * Read a run's `liveness.json` for the one thing the certificate cannot carry: the
 * disputed timestamps of the temporal pass (ADR-0016). Returns the disputed events and
 * whether any source is marked tamper-suspected.
 *
 * @param {string|object} input
 * @returns {{disputedEvents: Array<object>, tamperSuspected: Array<string>}}
 */
export function parseLiveness(input) {
  let document;
  if (typeof input === "string") {
    try {
      document = JSON.parse(input.replace(/^﻿/, ""));
    } catch {
      throw new CertificateError("notJson");
    }
  } else {
    document = input;
  }
  if (!isObject(document)) throw new CertificateError("notObject");
  const disputed = document.disputed_events;
  const disputedEvents = Array.isArray(disputed) ? disputed : [];
  const sources = Array.isArray(document.sources) ? document.sources : [];
  const tamperSuspected = sources
    .filter((source) => source && source.tamper_suspected === true)
    .map((source) => String(source.source_id));
  return { disputedEvents, tamperSuspected };
}
