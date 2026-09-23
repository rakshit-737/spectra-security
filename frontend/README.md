# SPECTRA certificate viewer

A reader for one `runs/<id>/cert.spcert`. It renders the certificate; it checks nothing.

Owning spec sections: Part I 32.7 and 39; Part II 75.2 C10. This is the M8 deliverable's
certificate screen.

## Running it

There is no build step, no bundler, no framework and no dependency. The page is plain
HTML plus ES modules, and everything it uses is either in this directory or in the Node
standard library.

```
node frontend/src/serve.js        # prints http://127.0.0.1:8173/
node frontend/src/serve.js 9000   # or pick a port
```

Then open the printed URL and pick a certificate with the file picker.

**Opening `index.html` from the filesystem does not work**, and the server is not a
convenience. A `<script type="module">` is fetched, and a document loaded from `file://`
has an opaque origin, so the browser refuses the fetch and the page renders nothing.
`src/serve.js` is forty lines of `node:http` that serve this directory and refuse any
path that resolves outside it.

Nothing is fetched and nothing is uploaded. The certificate is read in the browser with
`File.text()` and never leaves it.

## Tests

```
node --test frontend/tests
```

90 tests, all pure functions. The DOM is not exercised: `src/view.js` places text nodes
and decides no wording, so a test of the wording gains nothing from a browser and would
lose the ability to run offline.

Two other invocations work and run the same suite:

```
node --test "frontend/tests/*.test.js"   # from the repository root
cd frontend && node --test               # from here
```

`tests/index.js` exists because of the first command. On Node 24.14.0 the test runner does
not expand a bare directory positional; it resolves it as a module specifier, which for a
directory is `index.js`. Without that file `node --test frontend/tests` fails with
`Cannot find module` before a single test runs. The file is a manifest: it imports the six
`*.test.js` files and nothing else, and because it is not itself named `*.test.js` the
glob and the `cd frontend` forms do not match it and register nothing twice.

`tests/fixtures.js` is test support, not a test. It builds certificate bodies by hand,
because `runs/` is not committed (Part I 32.9) and `data/golden/` does not exist yet, so a
suite that required a real certificate on disk would pass here and fail in a clean clone.
It also picks up whatever is in `runs/` when a run directory happens to be present, so the
renderer is exercised against real bytes when there are any.

## What the page renders

Twelve panels, in this order.

| panel | what it says |
|-------|--------------|
| Verdict | the long rendering of `spectra_vs.cert.render_long`: the token with its six scope digests and `non-adaptive`, the safety clause, the minimality clause, the witness clause, the scope sentence, the flags with what each one does, and the model statement last |
| The cut | the raised controls as `ctl:x >= L`, then every threshold literal under them with its bit and rank |
| Blindness premium | `NEC(Psi_max)`, `OCC(Psi_min)`, `B`, and per control the calibration deficiency and the licences it rests on -- or, when the member is absent, `premium_suppressed_reason` and the sentence saying it is omitted entirely |
| Licences | one row per licence: interval, span, basis, reason, and whether it has a witness; plus, when a liveness document is open, which of them rest on a disputed timestamp |
| Witness trees | each entry rebuilt from its flat node list, indented by depth, one line per step with its rule, head, kind and basis |
| Temporal dispute | the disputed timestamps, the licences resting on them, and how narrow the pass that found them is |
| Two counts | `observed_event_count` and `ghost_count`, on separate lines, with no total |
| Goals and residual | each goal and whether it is derivable under this cut; severed goals and open corridors |
| Canonical difference | `cut_delta_canonical` with its caption, in its own panel |
| Inputs and digests | the schema triple, the hash algorithm and its substitution note, the seed, the horizon, every input digest, and any disagreement between a scope member and its input digest |
| Budgets | the deterministic counters, and whether a budget was exhausted |
| What this page is | `cert_hash` as copied, that this page computed nothing, and the model statement |

Below the panels, the same rendering as plain text, for pasting into a report.

### The witness trees

ADR-0015 publishes a witness tree flat: `body.witnesses[i]` is
`{ removed_control, nodes }`, `nodes` is in pre-order, `nodes[0]` is the root, and each
node's `children` is a list of **indices** into `nodes`. The encoding exists so a witness
of any proof length reaches seven containers and no more, which is what lets a multi-step
derivation be published at all. The cost the ADR names is that a consumer must rebuild the
nested form, and `src/witness.js` is that rebuild.

The four structural rules the checker enforces are re-derived here rather than assumed,
because this page never sees the checker's answer: the node list is non-empty, every child
index is greater than its parent's and inside the list, every node but the root is
referenced exactly once, and the root is referenced by nobody. A list that breaks one is
**reported and not drawn**. Drawing a repaired tree would put a derivation on the screen
that the certificate does not contain.

### The disputed timestamps

They are not in the certificate. ADR-0016 puts them in the run's `liveness.json`, which
the certificate pins by digest and does not carry. So the dispute panel has three states,
and the difference between the second and the third is the point:

* no liveness document open -- it says it did not read one;
* a liveness document with no `disputed_events` -- it says no recorded timestamp
  contradicts the order its own source recorded, and how little that checks;
* a liveness document with disputed events -- it names them, and names the licences that
  rest on them, recomputed from the licence intervals with the same conservative closed-
  interval reading as `spectra_vs.liveness.licence_disputed`.

The counterfactual verdict that `spectra_vs.demo` prints is **not** rendered. It is not in
the certificate, and it is a safety token that would have no scope of its own to travel
with.

## The honesty rules, and where each one lives

These are not style preferences. A violation is a defect.

**1. No bare verdict token.** `render.js`'s `verdictShort` is the only function in this
package that places `ROBUST`, `OPTIMISTIC_ONLY`, `UNSAFE` or `INDETERMINATE` next to a
literal, and it carries the six scope digests and `non-adaptive` with them, in the member
order `spectra_vs.cert.render_short` uses. The verdict panel is the long rendering, so it
ends with

> This is a statement about the model, not about the system.

and the page ends with it too. `verdictLong` takes extra lines through a parameter that
splices them in *before* that ending; there is no parameter that moves or removes it.
`tests/honesty.test.js` scans every rendered string of every shape and fails on any verdict
token not immediately followed by `(` -- which is BP-08's own test -- and additionally
refuses to let a token appear in the catalog at all.

**2. A licence is a permission for a step nobody could have seen.** It is never called an
observation. A GHOST is never called an event. `observed_event_count` and `ghost_count`
are rendered on separate lines and never summed; the fixture's two counts are 5 and 41
precisely so a test can assert that 46 appears nowhere. `unobservedCount` counts GHOST and
LICENSED steps under one word, `unobserved`, and that word is the only thing they are said
to have in common.

**3. The banned-phrase table in `CLAIMS.md`.** `tests/honesty.test.js` carries the
mechanical rows of that table and scans both the catalog and every rendered string. The
rows that need a sentence read rather than a pattern matched -- BP-08's verdict position,
BP-13's citation backing, BP-14's language count, BP-15's subject -- are covered by the
dedicated tests instead of by a regular expression that would be wrong.

**4. Nothing claims the certificate was checked.** This page recomputes no digest,
recomputes no `instances_hash` over `body.instances`, replays no instance and walks no
obligation. It says so in the footer rather than leaving the absence to be inferred, and
it says that a checker in this repository agreeing with the emitter is not a second
party's agreement -- both share an author, a language and a reading of the same ADRs.
A test scans for every phrasing that would claim otherwise.

## The string catalog

Every user-visible sentence is in `src/strings.js` and nowhere else, which is what a future
`G-UI-STRINGS` gate needs: one file to lint. `catalogEntries()` flattens it for such a gate,
and `tests/catalog.test.js` walks the other modules, strips their comments, and fails on any
sentence-shaped literal that remains.

Two literals are exempt, and they are asserted rather than waved through. `index.html`
carries its own `<title>` and `<noscript>`, because the first must exist before any script
runs and the second exists precisely when none does. Both are held byte-for-byte against
`STRINGS.page.title` and `STRINGS.page.noscript` by a test, so they cannot drift. Every
other label, hint and heading in the document is empty and filled from the catalog at load.

`CLAIMS.md`'s surface list names `frontend/src/strings/*.json`. This catalog is
`frontend/src/strings.js` instead, because it holds the clause tables keyed by enum value
that mirror `spectra_vs.cert`, and JSON cannot carry the comment that says which Python
constant each table mirrors. Reconciling the two is a one-line edit to that surface list,
which this change does not own.

## Files

```
index.html          the host document: no build step, two literals, everything else empty
src/strings.js      THE STRING CATALOG. Every user-visible sentence.
src/cert.js         parse and shape-check a certificate; read a liveness document
src/witness.js      rebuild a witness tree from the flat node list (ADR-0015)
src/render.js       certificate in, sections of lines out. Pure. Holds no literal.
src/view.js         the only module that touches the DOM. Text nodes only, never innerHTML.
src/app.js          entry point: wires the file pickers to the parsers and the view
src/serve.js        a local static server, so the page can be opened at all
tests/*.test.js     90 tests
tests/fixtures.js   test support: hand-built certificates, plus whatever is in runs/
tests/index.js      a manifest, so `node --test frontend/tests` resolves
```

## Two things in this directory that this change did not own

`package.json` and `tsconfig.json` still describe a TypeScript-and-bundler path. There is
no TypeScript toolchain in this repository offline and no bundler, `src/main.ts` has been
replaced by ES modules that a browser loads directly, and `tsconfig.json`'s `include` now
points at a `src/` with no `.ts` file in it. `package.json`'s `test` script still reports
that console tests are not implemented, which is no longer true. Both files are outside
what this change was scoped to touch, and both should be reconciled with what is actually
here.
