// Test support for the certificate viewer. Not a test file: `node --test frontend/tests`
// runs `*.test.js`, and this module is imported by them.
//
// WHY A HAND-BUILT FIXTURE. `runs/` is not committed (`.gitignore`, Part I 32.9), and
// `data/golden/` does not exist yet, so a test that needed a real certificate on disk
// would pass on the author's machine and fail in a clean clone. The fixtures below are
// the smallest documents that exercise each shape. `realCertificates()` additionally
// picks up whatever is in `runs/` when a run directory happens to be there, so the
// renderer is exercised against real bytes when they exist and the suite still passes
// when they do not.

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

/** A scope whose six digests are distinguishable at eight characters. */
export const SCOPE = Object.freeze({
  attacker: "non-adaptive",
  bundle: "b2b256:bbbbbbbb1111111111111111111111111111111111111111111111111111bbbb",
  controls: "b2b256:cccccccc2222222222222222222222222222222222222222222222222222cccc",
  er: "b2b256:eeeeeeee3333333333333333333333333333333333333333333333333333eeee",
  goal: "b2b256:99999999444444444444444444444444444444444444444444444444444499999",
  liveness: "b2b256:1111111155555555555555555555555555555555555555555555555555551111",
  rules: "b2b256:aaaaaaaa6666666666666666666666666666666666666666666666666666aaaa",
});

const INPUTS = Object.freeze({
  bundle_hash: SCOPE.bundle,
  bundle_provenance: "synthetic_generator_no_range",
  catalog_bits_hash: "b2b256:0f0f0f0f7777777777777777777777777777777777777777777777777777f0f0",
  controls_hash: SCOPE.controls,
  er_hash: SCOPE.er,
  goal_hash: SCOPE.goal,
  grounding_mode: "replayed",
  guard_ast_hash: "b2b256:1a1a1a1a8888888888888888888888888888888888888888888888888888a1a1",
  implementation: "python-reference",
  instances_hash: "b2b256:2b2b2b2b9999999999999999999999999999999999999999999999999999b2b2",
  k: 3600,
  liveness_hash: SCOPE.liveness,
  profile_hash: "b2b256:3c3c3c3c0000000000000000000000000000000000000000000000000000c3c3",
  rules_hash: SCOPE.rules,
  rules_text_hash: "b2b256:4d4d4d4d1010101010101010101010101010101010101010101010101010d4d4",
  seed: "0x0000000000000007",
});

const INSTANCES = Object.freeze([
  {
    blockers: [],
    body: [],
    evidence: ["ev:aaaa0000aaaa0000aaaa0000aaaa0000"],
    ghost: false,
    head: "fh:1111111111111111111111111111111111111111111111111111111111111111",
    instance_id: "in:0001000100010001000100010001000100010001000100010001000100010001",
    license_ids: [],
    observed: "OBSERVED",
    rule_id: "rl:r0001",
    rule_version: "1.0.0",
    tick: 1707009420,
  },
  {
    blockers: [],
    body: [],
    evidence: [],
    ghost: false,
    head: "fh:2222222222222222222222222222222222222222222222222222222222222222",
    instance_id: "in:0002000200020002000200020002000200020002000200020002000200020002",
    license_ids: [
      "lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367",
    ],
    observed: "LICENSED",
    rule_id: "rl:r0002",
    rule_version: "1.0.0",
    tick: 1707009480,
  },
  {
    blockers: [],
    body: [],
    evidence: [],
    ghost: true,
    head: "fh:3333333333333333333333333333333333333333333333333333333333333333",
    instance_id: "in:0003000300030003000300030003000300030003000300030003000300030003",
    license_ids: [
      "lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367",
    ],
    observed: "LICENSED",
    rule_id: "rl:r0003",
    rule_version: "1.0.0",
    tick: 1707009540,
  },
]);

/** A three-node chain: OBSERVED root, LICENSED child, GHOST grandchild. */
export const WITNESS_NODES = Object.freeze([
  {
    children: [1],
    evidence: ["ev:aaaa0000aaaa0000aaaa0000aaaa0000"],
    head: INSTANCES[0].head,
    instance_id: INSTANCES[0].instance_id,
    kind: "OBSERVED",
  },
  {
    children: [2],
    evidence: [],
    head: INSTANCES[1].head,
    instance_id: INSTANCES[1].instance_id,
    kind: "LICENSED",
  },
  {
    children: [],
    evidence: [],
    head: INSTANCES[2].head,
    instance_id: INSTANCES[2].instance_id,
    kind: "GHOST",
  },
]);

/**
 * A certificate body. `patch` is merged over the top level of the body, so a test can
 * replace one member without restating the rest.
 *
 * `observed_event_count` is 5 and `ghost_count` is 41 -- deliberately two numbers whose
 * sum, 46, appears nowhere else in the fixture, so a test can assert that no rendering
 * adds them.
 *
 * @param {object} [patch]
 * @returns {{body: object, cert_hash: string}}
 */
export function certificate(patch = {}) {
  const body = {
    atoms: {
      assign: [
        ["ctl:egress_seg", 1, 0],
        ["ctl:egress_seg", 2, 1],
        ["ctl:priv_approval", 1, 2],
      ],
      n: 3,
    },
    budgets: {
      bb_nodes: 59,
      budget_exhausted: false,
      exhaustive_cuts_tested: 0,
      exhaustive_ran: false,
      fixpoint_steps: 86594,
      step_budget: 2000000,
    },
    cut: [
      { bit: 0, control_id: "ctl:egress_seg", level: 1, rank: 0 },
      { bit: 1, control_id: "ctl:egress_seg", level: 2, rank: 1 },
      { bit: 2, control_id: "ctl:priv_approval", level: 1, rank: 2 },
    ],
    cut_delta_canonical: ["ctl:priv_approval"],
    ghost_count: 41,
    goals: [{ derivable: false, goal_key: INSTANCES[0].head }],
    inputs: { ...INPUTS },
    instances: INSTANCES.map((instance) => ({ ...instance })),
    invariant: { u: [INSTANCES[0].head] },
    licenses: [
      {
        basis: "BLIND",
        license_id:
          "lic:0fe434dce80d6f47dd094735ba1fc98f34d0e9842413db8f73b880ecbb612546",
        reason: "B_PROFILE_INSUFFICIENT",
        source_id: "src:edr_host",
        t0_ns: "1707004800000000000",
        t1_ns: "1707012000000000000",
      },
      {
        basis: "SUPPRESSED",
        license_id:
          "lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367",
        reason: "S_CHAIN_SEQ_GAP",
        source_id: "src:iam_audit",
        t0_ns: "1707006599722706064",
        t1_ns: "1707006600000000000",
        witness: [
          "ev:c9f5c0c3ef5c102158a5b662e85a6c0e",
          "ev:f0d1a494a79e1d3769262021e84f93bd",
        ],
      },
    ],
    observed_event_count: 5,
    premium: {
      blindness_premium: ["ctl:priv_approval"],
      nec_max: ["ctl:priv_approval"],
      occ_min: ["ctl:egress_seg"],
      per_control: [
        {
          calibration_deficiency: { den: 1, num: 0 },
          control_id: "ctl:priv_approval",
          license_ids: [
            "lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367",
          ],
        },
      ],
    },
    psi: { complete: true, corridors: [], program: "PMax" },
    residual: {
      corridors_exhaustive: true,
      corridors_open: [],
      goals_derivable: [],
      goals_severed: [INSTANCES[0].head],
      program: "PMax",
    },
    schema: {
      hash_algorithm: "blake2b-256",
      hash_substitution_note:
        "The specification names blake3. This Python reference implementation computes " +
        "blake2b-256 because the standard library has no blake3 and no package may be " +
        "installed. Digests here are not comparable with specified digests.",
      min_checker: "1.1",
      profile: "eclipse-cert",
      v: "1.1",
    },
    scope: { ...SCOPE },
    silent: [
      {
        instance_id: INSTANCES[1].instance_id,
        license_ids: [
          "lic:d51b8f0eaabe244c6d5ad1240ac4186efd7dccafe40bc8a2c632c73a2b9a1367",
        ],
      },
    ],
    verdict: {
      derived_suppressed: ["pareto_frontier", "redundancy_index"],
      flags: [],
      minimality: "EXACT_PSI_RELATIVE",
      realizability: "UNCHECKED",
      safety: "ROBUST",
      witness_class: null,
    },
    witnesses: [
      {
        nodes: WITNESS_NODES.map((node) => ({ ...node })),
        removed_control: "ctl:egress_seg",
      },
    ],
    ...patch,
  };
  return {
    body,
    cert_hash:
      "b2b256:56315ac26e00bb0f6f40983ae4de9caf87d113acbd624230585f74cf2ce2bfb7",
  };
}

/** The fixture as the octets a viewer would be handed. */
export function certificateText(patch = {}) {
  return JSON.stringify(certificate(patch));
}

/** A liveness document carrying one disputed timestamp, as ADR-0016 records it. */
export function livenessWithDispute() {
  return {
    disputed_events: [
      {
        event_id: "ev:c9f5c0c3ef5c102158a5b662e85a6c0e",
        source_id: "iam_audit",
        t_evt_ns: "1707006600000000000",
      },
    ],
    flags: {},
    sources: [
      { source_id: "src:iam_audit", tamper_suspected: true },
      { source_id: "src:edr_host", tamper_suspected: false },
    ],
  };
}

/** A liveness document with no dispute at all. */
export function livenessWithoutDispute() {
  return {
    disputed_events: [],
    flags: {},
    sources: [{ source_id: "src:iam_audit", tamper_suspected: false }],
  };
}

/**
 * Every `runs/<id>/cert.spcert` present in the working tree, with the run's
 * `liveness.json` when it has one. Empty in a clean clone, because `runs/` is not
 * committed; a test that uses this must therefore not require it to be non-empty.
 *
 * `schemaV` is read straight out of the file and is NOT filtered here. A working tree
 * holds certificates written before ADR-0015 as well as after it, and a test that
 * silently dropped the older ones would never exercise the viewer's refusal to render
 * an encoding it cannot rebuild. `currentCertificates()` is the filtered view.
 *
 * @returns {Array<{id: string, text: string, liveness: string|null, schemaV: string|null}>}
 */
export function realCertificates() {
  const runs = join(REPO_ROOT, "runs");
  let entries;
  try {
    entries = readdirSync(runs, { withFileTypes: true });
  } catch {
    return [];
  }
  const out = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    let text;
    try {
      text = readFileSync(join(runs, entry.name, "cert.spcert"), "utf8");
    } catch {
      continue;
    }
    let liveness = null;
    try {
      liveness = readFileSync(join(runs, entry.name, "liveness.json"), "utf8");
    } catch {
      liveness = null;
    }
    let schemaV = null;
    try {
      schemaV = JSON.parse(text).body.schema.v;
    } catch {
      schemaV = null;
    }
    out.push({ id: entry.name, text, liveness, schemaV });
  }
  return out;
}

/** The subset of `realCertificates()` this viewer renders: schema 1.1 (ADR-0015). */
export function currentCertificates() {
  return realCertificates().filter((entry) => entry.schemaV === "1.1");
}

/** The frontend directory, for the tests that read `index.html` and the modules. */
export const FRONTEND_ROOT = join(REPO_ROOT, "frontend");
