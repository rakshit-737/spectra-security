// The string catalog is the whole of the page's prose.
//
// This is the test that stands in for `G-UI-STRINGS`: a user-visible literal outside
// `src/strings.js` is a defect, because a gate cannot lint prose it cannot find. The
// scan below strips comments and then looks for a sentence-shaped literal in the code
// that remains.
//
// Two literals are exempt and named here rather than waved through: the `<title>` and
// the `<noscript>` of `index.html`, which must exist before or without the module graph.
// The exemption costs nothing because both are asserted byte-for-byte against the
// catalog below, so they cannot drift away from it.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { CHROME } from "../src/app.js";
import { STRINGS, catalogEntries, fill } from "../src/strings.js";
import { FRONTEND_ROOT } from "./fixtures.js";

/** The modules that build the page. `serve.js` is a developer tool and shows no prose. */
const UI_MODULES = ["cert.js", "render.js", "view.js", "app.js", "witness.js"];

const readModule = (name) => readFileSync(join(FRONTEND_ROOT, "src", name), "utf8");
const indexHtml = () => readFileSync(join(FRONTEND_ROOT, "index.html"), "utf8");
const squash = (text) => text.replace(/\s+/g, " ").trim();

/**
 * The document with its comments removed. The comment at the top of `index.html` names
 * the two tags this file checks, so a match taken over the raw bytes would find the
 * comment's mention of `<noscript>` rather than the element.
 */
const indexHtmlBody = () => indexHtml().replace(/<!--[\s\S]*?-->/g, "");

/**
 * Remove comments and keep string literals, walking the source one character at a time.
 * A regular expression cannot do this without also eating the `//` inside a string.
 *
 * @param {string} source
 * @returns {Array<{quote: string, value: string}>}
 */
export function stringLiterals(source) {
  const out = [];
  let i = 0;
  while (i < source.length) {
    const ch = source[i];
    if (ch === "/" && source[i + 1] === "/") {
      while (i < source.length && source[i] !== "\n") i += 1;
      continue;
    }
    if (ch === "/" && source[i + 1] === "*") {
      i += 2;
      while (i < source.length && !(source[i] === "*" && source[i + 1] === "/")) i += 1;
      i += 2;
      continue;
    }
    if (ch === '"' || ch === "'" || ch === "`") {
      const quote = ch;
      let value = "";
      i += 1;
      while (i < source.length && source[i] !== quote) {
        if (source[i] === "\\") {
          value += source[i + 1];
          i += 2;
          continue;
        }
        value += source[i];
        i += 1;
      }
      i += 1;
      out.push({ quote, value });
      continue;
    }
    i += 1;
  }
  return out;
}

/** A literal that reads as a sentence: four or more words, at least one of them lower case. */
function looksLikeProse(value) {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (words.length < 4) return false;
  return words.some((word) => /^[a-z]{3,}$/.test(word));
}

test("no module outside the catalog contains a sentence-shaped literal", () => {
  for (const name of UI_MODULES) {
    for (const { value } of stringLiterals(readModule(name))) {
      assert.ok(
        !looksLikeProse(value),
        `src/${name} holds a user-visible literal; move it to strings.js: ${value}`,
      );
    }
  }
});

test("the literal scan is not vacuous", () => {
  assert.equal(stringLiterals('const a = "http://x"; // "not a literal"').length, 1);
  assert.equal(stringLiterals("/* \"commented out\" */ const a = 1;").length, 0);
  assert.ok(looksLikeProse("this is a whole sentence"));
  assert.ok(!looksLikeProse("text/javascript; charset=utf-8"));
  assert.ok(!looksLikeProse("b2b256:"));
});

test("strings.js is the module that actually holds the prose", () => {
  const prose = catalogEntries().filter((entry) => looksLikeProse(entry.value));
  assert.ok(prose.length > 40, `the catalog holds ${prose.length} sentences`);
});

test("the <title> in index.html is the catalog's page title", () => {
  const match = indexHtmlBody().match(/<title>([^<]*)<\/title>/);
  assert.ok(match, "index.html has a title");
  assert.equal(squash(match[1]), STRINGS.page.title);
});

test("the <noscript> in index.html is the catalog's noscript sentence", () => {
  const match = indexHtmlBody().match(/<noscript>([\s\S]*?)<\/noscript>/);
  assert.ok(match, "index.html has a noscript block");
  assert.equal(squash(match[1].replace(/<[^>]+>/g, " ")), STRINGS.page.noscript);
});

test("every element the page fills from the catalog exists in index.html", () => {
  const html = indexHtmlBody();
  for (const id of Object.keys(CHROME)) {
    assert.ok(
      new RegExp(`id="${id}"`).test(html),
      `index.html has an element with id ${id}`,
    );
  }
  for (const id of ["sections", "plaintext", "cert-input", "liveness-input"]) {
    assert.ok(new RegExp(`id="${id}"`).test(html), `index.html has ${id}`);
  }
});

test("the chrome the page fills is all catalog text and none of it is empty", () => {
  for (const [id, text] of Object.entries(CHROME)) {
    assert.equal(typeof text, "string", `${id} is filled from a string`);
    assert.ok(text.length > 0, `${id} is not empty`);
  }
});

test("index.html loads the module by relative path and references no bundler", () => {
  const html = indexHtmlBody();
  assert.ok(html.includes('<script type="module" src="./src/app.js"></script>'));
  assert.ok(!html.includes("main.ts"), "the TypeScript stub is gone");
  assert.ok(!/https?:\/\//.test(html), "the page loads nothing over the network");
});

test("fill substitutes placeholders and leaves an unknown one visible", () => {
  assert.equal(fill("{a} and {b}", { a: "1", b: "2" }), "1 and 2");
  assert.equal(fill("{a} and {b}", { a: "1" }), "1 and {b}");
  assert.equal(fill("{{{listed}}}", { listed: "x" }), "{x}");
});

test("the catalog is frozen, so a view cannot rewrite a sentence at run time", () => {
  assert.ok(Object.isFrozen(STRINGS));
  assert.ok(Object.isFrozen(STRINGS.page));
  assert.throws(() => {
    "use strict";
    STRINGS.page.title = "something else";
  }, TypeError);
});
