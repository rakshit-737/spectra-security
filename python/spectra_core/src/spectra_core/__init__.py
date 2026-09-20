"""SPECTRA core: identifiers, canonical encoding, record types, errors, path wiring.

This package is the foundation every other stage imports. It owns four things and
deliberately owns nothing else:

  `ids`        the section 57.2 identifier grammar, as nominal types that make passing a
               RecordId where a FactHash belongs a runtime error rather than a silent pass
  `canon`      the canonical byte encoding, the domain-separated digest, and the ordering
               helpers that every output path must route through
  `model`      the frozen record types the stages exchange, each with an encoding and an id
  `errors`     the reason-code taxonomy, and quarantine as data rather than as an exception

`bootstrap` is separate from all four: it wires `sys.path` for a workspace that is not
installed, and importing this package does not run it, because an import with a side
effect on `sys.path` is an import that changes what a later import resolves to.

WHAT THIS IS. A PYTHON REFERENCE IMPLEMENTATION, per ADR-0013. The specification names
Rust for the kernel and Go for the checker; neither toolchain exists on this machine and
neither implementation exists. Nothing in this package may state or imply otherwise.

THE DIGEST IS SUBSTITUTED AND SAYS SO. The specification names BLAKE3. The standard
library has no BLAKE3, no package may be installed, so `canon` computes
`hashlib.blake2b(digest_size=32)` and labels it `blake2b-256` on every wire it reaches.
No digest produced here is ever written behind a `blake3:` label, and every certificate
carries the algorithm name as a required member. See `canon` for the full statement.

DETERMINISM IS STRUCTURAL HERE. Every exported collection is a tuple sorted by a declared
total key; `canon.check_strictly_ascending` verifies rather than sorts, so an emitter that
produced its output in hash-map order goes red instead of being tidied up on the way out.
No module in this package reads a wall clock, an environment variable or a random source.
"""

from spectra_core import bootstrap, canon, errors, ids, model

__all__ = ["bootstrap", "canon", "errors", "ids", "model"]

#: Package version. Fixed text, not derived from a tag, because a version read from the
#: environment would differ between two runs that must be byte-identical.
__version__ = "0.1.0"
