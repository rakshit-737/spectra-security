// Reading a certificate: the shape checks, and the two re-derivations the viewer makes.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CertificateError,
  FILE_MAGIC,
  SCHEMA_V,
  byteOrder,
  indexInstances,
  licenceDisputed,
  parseCertificate,
  parseLiveness,
  raisedControls,
  shortDigest,
} from "../src/cert.js";
import {
  certificate,
  certificateText,
  livenessWithDispute,
  realCertificates,
} from "./fixtures.js";

test("a well-formed certificate parses and keeps its body and hash", () => {
  const parsed = parseCertificate(certificateText());
  assert.equal(parsed.body.schema.v, SCHEMA_V);
  assert.equal(parsed.body.observed_event_count, 5);
  assert.ok(parsed.certHash.startsWith("b2b256:"));
});

test("an already-parsed document is accepted without the magic check", () => {
  const parsed = parseCertificate(certificate());
  assert.equal(parsed.body.verdict.minimality, "EXACT_PSI_RELATIVE");
});

test("text that does not begin with the nine octets is refused", () => {
  assert.throws(
    () => parseCertificate(`\n${certificateText()}`),
    (error) => error instanceof CertificateError && error.key === "magicFmt",
  );
  assert.equal(FILE_MAGIC.length, 9);
});

test("text that begins correctly but is not JSON is refused", () => {
  assert.throws(
    () => parseCertificate('{"body":{ this is not json'),
    (error) => error instanceof CertificateError && error.key === "notJson",
  );
});

test("a schema 1.0 document is refused rather than rendered with a nested witness", () => {
  const document = certificate();
  document.body.schema = { ...document.body.schema, v: "1.0", min_checker: "1.0" };
  assert.throws(
    () => parseCertificate(document),
    (error) =>
      error instanceof CertificateError &&
      error.key === "schemaFmt" &&
      error.values.v === "1.0",
  );
});

test("a missing body member is named in the refusal", () => {
  const document = certificate();
  delete document.body.witnesses;
  assert.throws(
    () => parseCertificate(document),
    (error) =>
      error instanceof CertificateError &&
      error.key === "missingFmt" &&
      error.values.member === "witnesses",
  );
});

test("a body member of the wrong container is refused", () => {
  const document = certificate({ licenses: {} });
  assert.throws(
    () => parseCertificate(document),
    (error) =>
      error instanceof CertificateError &&
      error.key === "typeFmt" &&
      error.values.member === "licenses",
  );
});

test("a missing scope member is refused by name", () => {
  const document = certificate();
  delete document.body.scope.liveness;
  assert.throws(
    () => parseCertificate(document),
    (error) =>
      error instanceof CertificateError && error.values.member === "scope.liveness",
  );
});

test("shortDigest keeps eight hex characters behind the algorithm label", () => {
  assert.equal(
    shortDigest("b2b256:af378c798b67bc7684236dc41b12d66078d5d1db", "b2b256:"),
    "b2b256:af378c79",
  );
  assert.equal(shortDigest("deadbeefcafe", "fh:"), "fh:deadbeef");
});

test("raisedControls takes the highest level of each control, in byte order", () => {
  const raised = raisedControls(certificate().body.cut);
  assert.deepEqual(raised, [
    { control: "ctl:egress_seg", level: 2 },
    { control: "ctl:priv_approval", level: 1 },
  ]);
});

test("byteOrder sorts by UTF-8 octets, not by UTF-16 code units", () => {
  const sorted = ["ctl:z", "ctl:a", "ctl:A"].sort(byteOrder);
  assert.deepEqual(sorted, ["ctl:A", "ctl:a", "ctl:z"]);
});

test("indexInstances finds the instance a witness node cites", () => {
  const body = certificate().body;
  const index = indexInstances(body.instances);
  const node = body.witnesses[0].nodes[1];
  assert.equal(index.get(node.instance_id).rule_id, "rl:r0002");
});

test("a licence is disputed when a disputed instant lies in its closed interval", () => {
  const events = livenessWithDispute().disputed_events;
  // The disputed instant is the licence's own upper endpoint: the interval is CLOSED,
  // which is the conservative reading `spectra_vs.liveness.licence_disputed` takes.
  assert.equal(
    licenceDisputed(events, "src:iam_audit", "1707006599722706064", "1707006600000000000"),
    true,
  );
  assert.equal(
    licenceDisputed(events, "src:iam_audit", "1707006600000000000", "1707006600000000000"),
    true,
  );
});

test("a licence on another source is not disputed by it", () => {
  const events = livenessWithDispute().disputed_events;
  assert.equal(
    licenceDisputed(events, "src:edr_host", "1707004800000000000", "1707012000000000000"),
    false,
  );
});

test("a licence whose interval ends before the disputed instant is not disputed", () => {
  const events = livenessWithDispute().disputed_events;
  assert.equal(
    licenceDisputed(events, "iam_audit", "1707004800000000000", "1707006599999999999"),
    false,
  );
});

test("the interval comparison is exact at nanosecond resolution", () => {
  // These three instants are indistinguishable as doubles: 1707006600000000000 is far
  // past 2**53, so `Number(a) === Number(b)` for all of them and a Number comparison
  // would call the second licence disputed. BigInt does not.
  const events = [
    { source_id: "iam_audit", t_evt_ns: "1707006600000000001" },
  ];
  assert.equal(
    licenceDisputed(events, "iam_audit", "1707006600000000001", "1707006600000000001"),
    true,
  );
  assert.equal(
    licenceDisputed(events, "iam_audit", "1707006599999999999", "1707006600000000000"),
    false,
  );
  assert.equal(
    Number("1707006600000000001") === Number("1707006600000000000"),
    true,
    "the two instants really are the same double, so the test above is not vacuous",
  );
});

test("parseLiveness reads the disputed events and the tamper-suspected sources", () => {
  const parsed = parseLiveness(JSON.stringify(livenessWithDispute()));
  assert.equal(parsed.disputedEvents.length, 1);
  assert.deepEqual(parsed.tamperSuspected, ["src:iam_audit"]);
});

test("a liveness document with no disputed_events member reads as no disputes", () => {
  const parsed = parseLiveness({ sources: [] });
  assert.deepEqual(parsed.disputedEvents, []);
});

test("every certificate present in runs/ either parses or is refused for its schema", () => {
  // `runs/` is not committed, so an empty list is the expected state of a clean clone
  // and is not a failure. When runs are present they are a mixture: certificates written
  // before ADR-0015 carry schema 1.0 and a nested witness this page cannot rebuild, and
  // the only correct thing to do with one is refuse it.
  for (const entry of realCertificates()) {
    if (entry.schemaV === SCHEMA_V) {
      const parsed = parseCertificate(entry.text);
      assert.equal(parsed.body.schema.v, SCHEMA_V, `${entry.id}`);
      continue;
    }
    assert.throws(
      () => parseCertificate(entry.text),
      (error) => error instanceof CertificateError && error.key === "schemaFmt",
      `${entry.id} carries schema ${entry.schemaV} and must be refused, not rendered`,
    );
  }
});
