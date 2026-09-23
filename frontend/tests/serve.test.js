// The local static server: it serves `frontend/` and nothing above it.
//
// The server exists only so the page can be opened -- a module script fetched from
// `file://` has an opaque origin and is refused by every browser. It is still a server
// pointed at a directory inside a repository that holds run directories, so the one
// property worth a test is that a request cannot climb out of `frontend/`.

import assert from "node:assert/strict";
import { join, resolve, sep } from "node:path";
import { test } from "node:test";

import { resolveWithinRoot } from "../src/serve.js";
import { FRONTEND_ROOT } from "./fixtures.js";

const ROOT = resolve(FRONTEND_ROOT);
const inside = (path) => path !== null && path.startsWith(ROOT + sep);

test("the bare root serves the page", () => {
  assert.equal(resolveWithinRoot("/"), join(ROOT, "index.html"));
});

test("a module path resolves inside the frontend root", () => {
  assert.equal(resolveWithinRoot("/src/app.js"), join(ROOT, "src", "app.js"));
  assert.ok(inside(resolveWithinRoot("/src/strings.js")));
});

test("a query string is not part of the path", () => {
  assert.equal(resolveWithinRoot("/src/app.js?v=2"), join(ROOT, "src", "app.js"));
});

test("no request escapes the frontend root, encoded or not", () => {
  for (const attempt of [
    "/../Makefile",
    "/../../Makefile",
    "/%2e%2e/Makefile",
    "/%2e%2e%2f%2e%2e%2fMakefile",
    "/src/../../CLAIMS.md",
    "/..%5c..%5cCLAIMS.md",
  ]) {
    const resolved = resolveWithinRoot(attempt);
    assert.ok(
      resolved === null || resolved === ROOT || inside(resolved),
      `${attempt} resolved to ${resolved}, which is outside ${ROOT}`,
    );
  }
});

test("the escape check is not vacuous: a path inside the root is accepted", () => {
  assert.ok(inside(resolveWithinRoot("/README.md")));
});
