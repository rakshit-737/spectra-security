// SPECTRA certificate viewer -- a static file server for opening the page locally.
//
// WHY THIS EXISTS. A module script is fetched, and a page opened from `file://` has an
// opaque origin, so every browser refuses the fetch and the viewer renders nothing. The
// page therefore has to be served over HTTP to be looked at. There is no bundler, no
// dev-server dependency and no network in this repository, so the server is forty lines
// of the Node standard library.
//
// IT SERVES `frontend/` AND NOTHING ELSE. The path is resolved against the frontend root
// and rejected if it escapes it, so a request cannot reach a run directory, a key or the
// rest of the tree. A certificate is opened through the file picker on the page, not by
// being served.
//
//   node frontend/src/serve.js [port]
//
// It prints one line: the URL. It contains no prose, which is deliberate -- a user-visible
// sentence belongs in `strings.js` and nowhere else.

import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
};

/**
 * Resolve a request path inside the frontend root, or `null` when it escapes.
 *
 * @param {string} urlPath
 * @returns {string|null}
 */
export function resolveWithinRoot(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const relative = normalize(decoded).replace(/^[/\\]+/, "");
  const target = resolve(join(ROOT, relative === "" ? "index.html" : relative));
  if (target !== ROOT && !target.startsWith(ROOT + sep)) return null;
  return target;
}

export function createViewerServer() {
  return createServer(async (request, response) => {
    const target = resolveWithinRoot(request.url || "/");
    if (target === null) {
      response.writeHead(403).end();
      return;
    }
    try {
      const info = await stat(target);
      if (!info.isFile()) {
        response.writeHead(404).end();
        return;
      }
    } catch {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "content-type": TYPES[extname(target)] || "application/octet-stream",
    });
    createReadStream(target).pipe(response);
  });
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (invokedDirectly) {
  const port = Number(process.argv[2] || 8173);
  createViewerServer().listen(port, "127.0.0.1", () => {
    process.stdout.write(`http://127.0.0.1:${port}/\n`);
  });
}
