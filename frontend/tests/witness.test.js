// Rebuilding a witness tree from the flat node list of ADR-0015.
//
// The ADR names four structural rules the checker enforces. This page does not see the
// checker's answer, so it re-derives them; these tests are that re-derivation held to the
// ADR's wording.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  WitnessShapeError,
  buildWitnessTree,
  checkNodeList,
  impliedWitnessClass,
  nodeDepths,
  preorder,
  unobservedCount,
} from "../src/witness.js";
import { WITNESS_NODES } from "./fixtures.js";

const nodes = (...children) => children.map((c) => ({ children: c, kind: "OBSERVED" }));

test("a well-formed chain yields each node's parent", () => {
  const parents = checkNodeList(nodes([1], [2], []));
  assert.deepEqual(parents, [-1, 0, 1]);
});

test("a well-formed fan-out yields each node's parent", () => {
  const parents = checkNodeList(nodes([1, 2], [], []));
  assert.deepEqual(parents, [-1, 0, 0]);
});

test("rule 1: an empty node list is refused", () => {
  assert.throws(
    () => checkNodeList([]),
    (error) => error instanceof WitnessShapeError && error.key === "empty",
  );
});

test("rule 2: a child index that is not greater than its parent is refused", () => {
  assert.throws(
    () => checkNodeList(nodes([1], [1], [])),
    (error) => error instanceof WitnessShapeError && error.key === "childRangeFmt",
  );
  assert.throws(
    () => checkNodeList([{ children: [0] }]),
    (error) => error instanceof WitnessShapeError && error.key === "rootReferencedFmt",
  );
});

test("rule 2: a child index past the end of the list is refused", () => {
  assert.throws(
    () => checkNodeList(nodes([1], [7], [])),
    (error) =>
      error instanceof WitnessShapeError &&
      error.key === "childRangeFmt" &&
      error.values.c === 7,
  );
});

test("rule 2: a non-integer child index is refused", () => {
  assert.throws(
    () => checkNodeList(nodes([1.5], [], [])),
    (error) => error instanceof WitnessShapeError && error.key === "childRangeFmt",
  );
});

test("rule 3: a node named by two parents is refused, so there are no shared subtrees", () => {
  assert.throws(
    () => checkNodeList(nodes([1, 2], [3], [3], [])),
    (error) =>
      error instanceof WitnessShapeError &&
      error.key === "multipleParentsFmt" &&
      error.values.c === 3,
  );
});

test("rule 3: a node named by no parent is refused, so there are no unreachable nodes", () => {
  assert.throws(
    () => checkNodeList(nodes([1], [], [])),
    (error) =>
      error instanceof WitnessShapeError &&
      error.key === "unreachableFmt" &&
      error.values.c === 2,
  );
});

test("forward-only edges mean a node list cannot encode a cycle", () => {
  // Every attempt to point backwards is refused by rule 2, which is exactly why the depth
  // walk below needs no visited set and cannot loop.
  for (const attempt of [
    [{ children: [1] }, { children: [0] }],
    [{ children: [1] }, { children: [1] }],
  ]) {
    assert.throws(() => checkNodeList(attempt), WitnessShapeError);
  }
});

test("depth is one more than the parent's, for a chain and for a fan-out", () => {
  assert.deepEqual(nodeDepths(nodes([1], [2], [])), [0, 1, 2]);
  assert.deepEqual(nodeDepths(nodes([1, 2], [3], [], [])), [0, 1, 1, 2]);
});

test("the rebuilt tree nests the children the indices named", () => {
  const root = buildWitnessTree(WITNESS_NODES);
  assert.equal(root.index, 0);
  assert.equal(root.node.kind, "OBSERVED");
  assert.equal(root.children.length, 1);
  assert.equal(root.children[0].node.kind, "LICENSED");
  assert.equal(root.children[0].children[0].node.kind, "GHOST");
  assert.equal(root.children[0].children[0].children.length, 0);
});

test("the rebuilt tree holds the published node object, not a copy of it", () => {
  const root = buildWitnessTree(WITNESS_NODES);
  assert.equal(root.node, WITNESS_NODES[0]);
});

test("pre-order visits a parent before its children, with the depth on each entry", () => {
  const walk = preorder(nodes([1, 3], [2], [], []));
  assert.deepEqual(
    walk.map((entry) => [entry.index, entry.depth]),
    [
      [0, 0],
      [1, 1],
      [2, 2],
      [3, 1],
    ],
  );
});

test("unobservedCount counts every step nobody could have seen, of either kind", () => {
  assert.equal(unobservedCount(WITNESS_NODES), 2);
  assert.equal(unobservedCount([{ kind: "OBSERVED" }, { kind: "OBSERVED" }]), 0);
  assert.equal(unobservedCount([{ kind: "GHOST" }]), 1);
  assert.equal(unobservedCount([{ kind: "LICENSED" }]), 1);
});

test("a tree with a silent step cannot imply an OBSERVED witness class", () => {
  assert.equal(impliedWitnessClass(WITNESS_NODES), "LICENSED");
  assert.equal(impliedWitnessClass([{ kind: "GHOST" }]), "LICENSED");
  assert.equal(impliedWitnessClass([{ kind: "OBSERVED" }]), "OBSERVED");
});
