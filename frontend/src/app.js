// SPECTRA certificate viewer -- the entry point.
//
// Owning spec sections: Part I 32.7, 39; Part II 75.2 C10. What C10 pins and this file
// obeys: the verdict is NEVER computed client-side. Nothing below derives a safety value,
// a minimality value, a cut or a count. Every value on the screen is read out of the
// certificate, and the only thing this page computes for itself is the shape of a witness
// tree from the indices the certificate publishes (ADR-0015) and which licences fall
// inside a disputed instant (ADR-0016) -- both of which are re-derivations of what is
// already in the file, checked against the published data and reported when they do not
// hold.
//
// NO NETWORK. A file arrives through `<input type="file">` and is read with `File.text()`.
// Nothing is fetched, nothing is uploaded, no certificate leaves the browser.
//
// This module holds no user-visible string literal. It wires the catalog to the view.

import { CertificateError, parseCertificate, parseLiveness } from "./cert.js";
import { renderDocument, renderPlainText } from "./render.js";
import { STRINGS, fill } from "./strings.js";
import { mountMessage, mountPlainText, mountSections } from "./view.js";

/**
 * The element id of every piece of page chrome, and the catalog string that fills it.
 * The document ships these empty; nothing here is a literal.
 */
export const CHROME = Object.freeze({
  title: STRINGS.page.title,
  subtitle: STRINGS.page.subtitle,
  "cert-label": STRINGS.page.openLabel,
  "cert-hint": STRINGS.page.openHint,
  "liveness-label": STRINGS.page.livenessLabel,
  "liveness-hint": STRINGS.page.livenessHint,
  "plaintext-label": STRINGS.page.plainTextLabel,
  "plaintext-hint": STRINGS.page.plainTextHint,
});

/** Everything the page is currently showing. Replaced wholesale, never patched. */
const state = {
  /** @type {{body: object, certHash: string|null}|null} */
  certificate: null,
  /** @type {{disputedEvents: Array<object>}|null} */
  liveness: null,
};

/**
 * Turn a `CertificateError` into the sentence the catalog holds for it.
 *
 * @param {unknown} error
 * @returns {string}
 */
export function describeError(error) {
  if (error instanceof CertificateError) {
    const template = STRINGS.errors[error.key];
    if (template) return fill(template, error.values);
  }
  return STRINGS.page.parseFailed;
}

function redraw(root, plainText) {
  if (state.certificate === null) {
    mountMessage(root, STRINGS.page.empty, STRINGS.page.emptyHint);
    mountPlainText(plainText, "");
    return;
  }
  const sections = renderDocument(state.certificate, state.liveness);
  mountSections(root, sections);
  mountPlainText(plainText, renderPlainText(sections));
}

/**
 * Wire the two file inputs to the two parsers. Exported so that a page with a different
 * layout can reuse it; `main` below is the default wiring.
 *
 * @param {Document} doc
 */
export function attach(doc) {
  const root = doc.getElementById("sections");
  const plainText = doc.getElementById("plaintext");
  const certInput = doc.getElementById("cert-input");
  const livenessInput = doc.getElementById("liveness-input");

  // The chrome is empty in the document and is filled from the catalog here. The two
  // literals index.html keeps -- the <title> and the <noscript> -- are the two that must
  // exist before or without this module, and `tests/catalog.test.js` holds them to the
  // catalog's wording.
  for (const [id, text] of Object.entries(CHROME)) {
    const node = doc.getElementById(id);
    if (node) node.textContent = text;
  }

  certInput.addEventListener("change", async () => {
    const file = certInput.files && certInput.files[0];
    if (!file) return;
    try {
      state.certificate = parseCertificate(await file.text());
    } catch (error) {
      state.certificate = null;
      mountMessage(root, STRINGS.page.parseFailed, describeError(error));
      mountPlainText(plainText, "");
      return;
    }
    redraw(root, plainText);
  });

  livenessInput.addEventListener("change", async () => {
    const file = livenessInput.files && livenessInput.files[0];
    if (!file) return;
    try {
      state.liveness = parseLiveness(await file.text());
    } catch (error) {
      state.liveness = null;
      mountMessage(root, STRINGS.page.parseFailed, describeError(error));
      mountPlainText(plainText, "");
      return;
    }
    redraw(root, plainText);
  });

  redraw(root, plainText);
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  attach(document);
}
