"""S11: the certificate checker. A separate top-level package.

WHAT IT DOES. `python -m spectra_vs_verify <cert>.spcert --rules ... --bundle ...` is a
pure file-in, file-out program. It performs no network access, no DNS, no database access
and no subprocess execution, and it writes no file unless `--out` is given. It never
repairs, normalises, sorts, deduplicates, defaults or infers: every deviation from
canonical form is a rejection with a reason code. Rejection is the default, and an
obligation it cannot decide is a rejection rather than a pass.

WHAT ITS INDEPENDENCE IS WORTH, STATED PLAINLY AND NOT SOFTENED.

This package imports nothing from `spectra_vs`. That is MODULE independence, and it is
the whole of what is on offer here. The specification's design has the checker written in
a different language, by a different implementation path, so that a defect in the solver
is unlikely to be mirrored in the checker. That checker does not exist. Both sides of this
pair are Python, written in one session, by one author, from one reading of one
specification, and they share `spectra_core` for the octet encoders and the digest.

So: this establishes that the certificate is internally consistent with the inputs it
pins, that its identifiers recompute, that its published closure is closed, that its
witness trees re-derive from records that are in the bundle, that its licences are implied
by the pinned liveness document, and that no smaller cut satisfies its published clause
database. It does NOT establish that a shared misreading of a rule, a guard, a temporal
operator or the specification itself was caught; a misreading present in the emitter is
present here too and is invisible to both.

An ACCEPT from this package therefore says: the certificate is internally consistent with
the hashed inputs. It says nothing about whether the bundle is truthful, whether entity
resolution was correct, whether the control catalog is complete, or whether grounding
found every instance. The certificate it accepts may NOT be described as independently
verified, and this package may never be called the independent checker the specification
names in another language.

THE DIGEST. `spectra_core.canon` computes blake2b-256 and labels it `b2b256:`. The
specification names an algorithm the standard library does not provide and which no
package may be installed to supply. Nothing here writes that name as though it were what
was computed.
"""

from __future__ import annotations

from spectra_vs_verify.checker import (
    ACCEPT,
    INDEPENDENCE_STATEMENT,
    OBLIGATIONS,
    REJECT,
    CheckerInputs,
    ObligationResult,
    Report,
    verify,
)

__all__ = [
    "ACCEPT",
    "INDEPENDENCE_STATEMENT",
    "OBLIGATIONS",
    "REJECT",
    "CheckerInputs",
    "ObligationResult",
    "Report",
    "__version__",
    "verify",
]

#: Fixed text. A version read from the environment would differ between two runs that must
#: agree byte for byte.
__version__ = "1.0"
