// SPECTRA certificate viewer -- rebuilding a witness tree from the flat node list.
//
// ADR-0015: `body.witnesses[i]` is `{ removed_control, nodes }`, `nodes` is in pre-order,
// `nodes[0]` is the root, and each node's `children` is a list of INDICES into `nodes`
// rather than a list of nested objects. The encoding exists so that a witness of any
// proof length reaches seven containers and no more, which is what lets a multi-step
// derivation be published at all. The cost the ADR names is exactly this module: a
// consumer that wants the nested form must rebuild it.
//
// THE STRUCTURAL RULES ARE REBUILT HERE, NOT TRUSTED. The checker enforces them and
// rejects with `E-WITNESS-CYCLE`; this page never sees the checker's answer and must not
// pretend it did. So the four rules are re-derived from the node list before anything is
// drawn:
//
//   1. `nodes` is non-empty.
//   2. Every child index of node `i` is greater than `i` and less than `nodes.length`.
//      Because every edge points forward, no index sequence can loop, and the depth walk
//      below terminates without a visited set.
//   3. Every node other than the root is referenced exactly once, so the list is one tree
//      with no shared subtrees and no unreachable nodes.
//   4. The root is referenced by nobody.
//
// A list that breaks one of them is REPORTED, not drawn and not repaired. Drawing a
// repaired tree would put a derivation on the screen that the certificate does not
// contain.
//
// This module holds no user-visible string. A failure comes back as a key into
// `STRINGS.witnessErrors` with the values that fill it.

/** A rejected node list. `key` names a member of `STRINGS.witnessErrors`. */
export class WitnessShapeError extends Error {
  /**
   * @param {string} key
   * @param {Record<string, number>} [values]
   */
  constructor(key, values = {}) {
    super(`${key} ${JSON.stringify(values)}`);
    this.name = "WitnessShapeError";
    this.key = key;
    this.values = values;
  }
}

/**
 * Check the four structural rules. Throws `WitnessShapeError` on the first violation.
 *
 * @param {Array<{children: number[]}>} nodes
 * @returns {number[]} the parent index of each node; -1 for the root.
 */
export function checkNodeList(nodes) {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    throw new WitnessShapeError("empty");
  }
  const parent = new Array(nodes.length).fill(-1);
  const seen = new Array(nodes.length).fill(false);
  for (let i = 0; i < nodes.length; i += 1) {
    const children = nodes[i].children;
    if (!Array.isArray(children)) {
      throw new WitnessShapeError("childRangeFmt", { i, c: -1 });
    }
    for (const child of children) {
      // The root check comes first. Index 0 also fails the forward-edge rule, and
      // reporting it as an out-of-range index would describe the wrong defect: a list
      // that names node 0 as somebody's child is one that has made the root a premise of
      // its own derivation.
      if (child === 0) {
        throw new WitnessShapeError("rootReferencedFmt", { i });
      }
      if (!Number.isInteger(child) || child <= i || child >= nodes.length) {
        throw new WitnessShapeError("childRangeFmt", { i, c: child });
      }
      if (seen[child]) {
        throw new WitnessShapeError("multipleParentsFmt", { c: child });
      }
      seen[child] = true;
      parent[child] = i;
    }
  }
  for (let i = 1; i < nodes.length; i += 1) {
    if (!seen[i]) throw new WitnessShapeError("unreachableFmt", { c: i });
  }
  return parent;
}

/**
 * The depth of every node, in the order the nodes are published.
 *
 * Every edge points forward, so one forward sweep assigns each node a depth before it is
 * read as a parent. That is the same walk `spectra_vs.demo._witness_lines` performs, and
 * it is the reason the forward-edge rule is worth enforcing rather than assuming.
 *
 * @param {Array<{children: number[]}>} nodes
 * @returns {number[]}
 */
export function nodeDepths(nodes) {
  checkNodeList(nodes);
  const depth = new Array(nodes.length).fill(0);
  for (let i = 0; i < nodes.length; i += 1) {
    for (const child of nodes[i].children) depth[child] = depth[i] + 1;
  }
  return depth;
}

/**
 * Rebuild the nested form the flat list encodes.
 *
 * The returned node carries the published node under `node`, its index under `index`, its
 * depth, and its children as rebuilt nodes -- not as indices. Nothing is copied out of
 * the published node, so a reader of the tree is reading the certificate's own object.
 *
 * @param {Array<object>} nodes
 * @returns {{index: number, depth: number, node: object, children: Array<object>}}
 */
export function buildWitnessTree(nodes) {
  const depth = nodeDepths(nodes);
  const built = nodes.map((node, index) => ({
    index,
    depth: depth[index],
    node,
    children: [],
  }));
  for (let i = 0; i < nodes.length; i += 1) {
    for (const child of nodes[i].children) built[i].children.push(built[child]);
  }
  return built[0];
}

/**
 * The tree in pre-order with a depth on each entry -- what a text or an indented HTML
 * rendering walks. Pre-order over the rebuilt tree, which is the published order for a
 * well-formed list and is derived rather than assumed to be.
 *
 * @param {Array<object>} nodes
 * @returns {Array<{index: number, depth: number, node: object}>}
 */
export function preorder(nodes) {
  const root = buildWitnessTree(nodes);
  const out = [];
  const visit = (entry) => {
    out.push({ index: entry.index, depth: entry.depth, node: entry.node });
    for (const child of entry.children) visit(child);
  };
  visit(root);
  return out;
}

/**
 * How many steps of a witness nobody could have seen.
 *
 * A step that is not OBSERVED cites no record. It is not an observation that was missed
 * and it is not an event: GHOST is a head the rules oblige, LICENSED is a step a licence
 * permits. Both are counted here under one word, `unobserved`, and that word is the only
 * thing they are said to have in common.
 *
 * @param {Array<{kind: string}>} nodes
 * @returns {number}
 */
export function unobservedCount(nodes) {
  return nodes.filter((node) => node.kind !== "OBSERVED").length;
}

/**
 * The witness class a node list would support, by the rule ADR-0015 section 4 states: an
 * OBSERVED class may not be published over a tree containing a GHOST or LICENSED node,
 * and a LICENSED class requires at least one node of either kind.
 *
 * This is NOT read back from `verdict.witness_class`; it is what the node list itself
 * says, and the renderer shows both so that a disagreement is visible rather than hidden.
 *
 * @param {Array<{kind: string}>} nodes
 * @returns {"OBSERVED"|"LICENSED"}
 */
export function impliedWitnessClass(nodes) {
  return unobservedCount(nodes) > 0 ? "LICENSED" : "OBSERVED";
}
