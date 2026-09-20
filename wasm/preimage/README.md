# WebAssembly - hand-authored canonical-preimage encoder
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places WebAssembly in Tier D with a role much narrower than Part I section
31.30's. The Part I role is not merely superseded; parts of it are forbidden. Nothing here has
been written.

## The promise

One narrow thing: a hand-authored WebAssembly text module that encodes a certificate body into
its canonical preimage bytes, so that a browser can re-derive the certificate's content address
offline.

Part II section 68 fixes the content address as the BLAKE3 of the canonical serialisation of
the certificate body and nothing else, printed in a fixed textual form, and makes a certificate
canonical only if re-serialising its parsed value reproduces the input bytes exactly. This
module implements that canonical serialisation, in hand-written WebAssembly text, so that the
re-derivation in a browser does not depend on a JavaScript serialiser whose object key ordering
and number formatting are the usual source of silent divergence.

What the promise excludes, in Part II section 73.1's own words: it does not compute or verify
any verdict. Part I's frontend invariant stands - the verdict is never computed client-side.
Concretely:

- No closure check, no goal exclusion, no license validation, no witness re-derivation, no
  minimality check. None of it is here, and a test asserts the module exports exactly one
  function.
- A further test asserts that no frontend code path calls that function with anything but a
  certificate preimage.
- Compiled WebAssembly is not this component. Part II section 73.1 states that Rust-to-wasm and
  any other compiled output is a build target rather than an authored language, excluded from
  the roster and from the count, and Part II section 73.8 marks every `.wasm` file as generated
  so that it never colours the language bar. This directory holds authored text only.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `preimage.wat` - the module: one exported function taking a pointer and a length into linear
  memory holding the parsed certificate body, writing the canonical bytes back into linear
  memory and returning the written length.
- `tests/` - the conformance suite: for every certificate in the fixture corpus, the bytes this
  module produces must equal the bytes the Rust serialiser produces, octet for octet.
- `tests/export_shape.*` - the test asserting the module exports exactly one function, imports
  nothing beyond its memory, and has no start section.
- `tests/callers.*` - the lint asserting that no frontend module calls the export with anything
  other than a certificate preimage.
- `Makefile` - assembling the text module and running the suite.

The module imports no host function and performs no allocation beyond the memory it is given,
because a canonical encoder that can call out is a canonical encoder whose behaviour depends on
what it called.

## Consumer edge

Real, and contingent on one piece of the frontend existing.

Delete this directory and no verdict changes, because this module computes no verdict. What
breaks is the browser's ability to re-derive a certificate's content address without asking the
server: the page can still display the address the certificate carries, but it can no longer
show that the address is the address of the bytes in front of it. The end-to-end gate
`e2e/hash-badge::matches` - which Part II section 73.6's transcript names for this component -
loses its subject and fails as an unresolved reference.

The honest qualification: this edge exists only as long as the frontend actually re-derives the
address and shows the result. If the badge is removed from the page, or reduced to echoing a
value the API returned, the consumer edge disappears entirely and this component becomes
padding under Part II section 73.3.1 - at which point section 73.6's remedy is deletion of the
directory, not a smaller badge.

So the load-bearing question is not "does the encoder work" but "does a committed frontend path
call it and assert on the result". That path has to exist and has to be owned by the frontend
component rather than by this directory, or the audit fails this component with
`SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-d / wat-preimage`. That component id is the one Part II section 73.6's
  audit transcript uses, so it is fixed rather than proposed.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release. The end-to-end badge assertion may additionally run in the
  frontend's own suite at a lower tier, since it is a browser test rather than a toolchain job;
  whether it does has not been decided.
- Make target: `make wat-preimage` assembles the module and runs the conformance, export-shape
  and caller lints. The mutation leg runs under `make polyglot-audit`.
- Toolchain: a pinned WebAssembly text assembler, vendored. Part II section 74.1's four
  toolchain images do not name one; the Tier A image carries the Node toolchain, which is the
  most likely home.

## Mutation check

Operator: `flip_byte(off, seed)`, from the closed set in Part II section 73.5.

The corruption: one byte at a seeded offset of the module's emitted preimage is flipped. The
byte count is unchanged, the structure is very nearly unchanged, and the output still looks
like a canonical serialisation. Exactly one octet differs.

The gate that must go red: `e2e/hash-badge::matches`, the browser assertion that the address
re-derived from this module's output equals the address the certificate carries. A single
flipped byte changes the BLAKE3 of the preimage completely, so the badge shows a mismatch and
the assertion fails.

A second gate must also go red and the audit records it: the byte-for-byte conformance
assertion against the Rust serialiser, which fails at the flipped offset and names it. If only
the conformance test fails and the browser gate stays green, the browser gate is not actually
re-deriving the address - it is echoing a value - and that is the specific decay this mutation
is aimed at.

`flip_byte` is chosen over `empty_output` deliberately. An empty preimage would fail any
assertion including a length check, and would prove nothing about whether the address is being
recomputed. A single-byte flip fails only a gate that hashes the bytes.

## Not yet decided

- **What computes the hash in the browser.** The module encodes the preimage; something has to
  take BLAKE3 of it. BLAKE3 is not available in the browser's built-in cryptography interface,
  so either a hash implementation ships alongside - in which case it is part of this component
  or another one, and needs its own manifest entry - or the badge is not re-derivable offline
  at all. Part II section 73.1 says the module "lets the browser re-derive a certificate's
  content address offline" and does not say what hashes. This is the largest open question on
  this page.
- **The standalone verification page.** Part I section 31.30 and section 31.4 described a
  standalone page that verifies a whole certificate from a local file with no server, built
  from the checking half of the kernel compiled to WebAssembly, with a three-way verdict
  agreement gate and a size budget. Part II section 73.1 forbids client-side verdict
  computation and reduces this component to preimage encoding. Part II does not say the
  standalone page was deleted, nor what replaces the portability claim it carried. Somebody
  reading Part I alone will rebuild the forbidden version.
- **Directory path.** `wasm/preimage/` appears in Part II section 73.8's Linguist rules, which
  marks hand-authored text under it as authored WebAssembly source while marking every compiled
  `.wasm` as generated. So the path is supported by Part II, but the Part I path it replaces
  contained a string that Part II section 73.10 bans from every directory name, which is a
  second and independent reason the Part I layout cannot be built as written.
- **The export signature.** "Exactly one function" is fixed by section 73.1. Its parameters,
  its memory model and how the parsed certificate body gets into linear memory in the first
  place are not specified anywhere, and the choice determines whether the caller lint is
  checkable at all.
- **Whether the encoder parses or only serialises.** Section 68 requires that re-serialising a
  parsed value reproduce the input bytes exactly, which is a round-trip property over a parser
  and a serialiser. If this module only serialises an already-parsed structure, the parser on
  the browser side is untested by this component and the round-trip property is not checked
  where it is claimed.
- **Where the badge assertion runs.** If it runs only in the nightly Tier D job, a frontend
  change that quietly stops calling the module is not caught until the next night. If it runs
  in the frontend suite per-PR, the component is exercised at T1 and section 73.9's Tier D
  cadence does not describe it. Neither has been chosen.
