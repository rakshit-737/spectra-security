// SPECTRA certificate viewer -- the only module that touches the DOM.
//
// It turns the sections `render.js` produced into elements. It decides nothing about
// wording: every string it places came from `strings.js` through `render.js`, and the
// only literals below are element names, attribute names and class names, none of which
// a reader sees as prose.
//
// TEXT NODES ONLY. Every string reaches the page through `textContent`, never through
// `innerHTML`. A certificate is a file a reader opened from somewhere; it is untrusted
// input, and an id inside it that happened to look like markup must appear on the screen
// as the characters it is.

const TONE_CLASS = {
  normal: "line",
  note: "line note",
  token: "line token",
  strong: "line strong",
};

/**
 * @param {string} name
 * @param {string|null} className
 * @param {string} [text]
 */
function element(name, className, text) {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * Render one section as a `<section>` with a heading and one `<p>` per line.
 *
 * The indent is carried as a data attribute and turned into padding by the stylesheet,
 * so a witness tree's shape is one number per line rather than leading spaces that a
 * copy-paste would keep.
 *
 * @param {{id: string, heading: string, lines: Array<{text: string, indent: number, tone: string}>}} section
 */
export function sectionElement(section) {
  const node = element("section", "panel");
  node.id = `panel-${section.id}`;
  node.appendChild(element("h2", null, section.heading));
  for (const entry of section.lines) {
    const paragraph = element("p", TONE_CLASS[entry.tone] || TONE_CLASS.normal, entry.text);
    paragraph.dataset.indent = String(entry.indent);
    node.appendChild(paragraph);
  }
  return node;
}

/**
 * Replace the contents of `root` with the rendered sections.
 *
 * @param {HTMLElement} root
 * @param {Array<object>} sections
 */
export function mountSections(root, sections) {
  root.replaceChildren(...sections.map(sectionElement));
}

/**
 * Show a single message in `root`: the empty state, or a refusal to read a file.
 *
 * @param {HTMLElement} root
 * @param {string} heading
 * @param {string} detail
 */
export function mountMessage(root, heading, detail) {
  const node = element("section", "panel");
  node.appendChild(element("h2", null, heading));
  node.appendChild(element("p", "line note", detail));
  root.replaceChildren(node);
}

/**
 * Put the plain-text rendering into a `<pre>` so a reader can select all of it.
 *
 * @param {HTMLElement} target
 * @param {string} text
 */
export function mountPlainText(target, text) {
  target.textContent = text;
}
