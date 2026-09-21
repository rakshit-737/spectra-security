# ADR-0013: The vertical slice is a Python reference implementation

## Status

Superseded by ADR-0014 — 2026-09-21

## Context

The specification names Rust for the proof kernel and the concrete simulator, and Go for the
independent checker. ADR-0005 fixes the boundary between them as a subprocess over content-addressed
files, and ADR-0003 fixes the crate and module names. Those decisions stand.

The machine this work is being done on has Python 3.14, Node 24 and Java 25. It has no Rust
toolchain, no Go toolchain, no Docker, no `make`, and no WSL distribution installed. That is not a
preference; `cargo`, `rustc`, `go`, `docker` and `make` are absent from the path, and
`wsl.exe -l -v` lists no distribution.

Three consequences follow immediately, and they are worth stating before the decision rather than
discovering them later.

**`make` has never run in this repository.** Every statement made about the Makefile so far — that
57 targets exit non-zero through a shared macro, that four do real work, that the host guard aborts
at parse time — comes from reading the file and from one agent's experiment with a stub `make` on
the path. None of it comes from executing the real target. The targets claimed to work today are
unverified.

**The container range cannot be built or run.** It is already the first rung of the descope ladder
and already non-normative, so nothing downstream depends on it.

**The kernel and the checker cannot be compiled in their specified languages.** This is the
decision that matters, because the alternative to choosing is building nothing.

## Decision

The vertical slice is implemented in **Python**, as a reference implementation, and is labelled as
one everywhere it appears.

Specifically:

1. The generator, ingest, entity resolution, the rule table, the grounding, the liveness pass, the
   fixpoint, the cut search and the certificate emitter are Python under `python/`.
2. The checker is a separate Python module that shares no code with the solver: it re-derives from
   the hashed inputs rather than importing anything the solver uses. Its independence is therefore
   **weaker than the specification's**, and section 4 below says exactly how.
3. `rust/` and `go/` keep their manifests and their empty crate and module roots. Nothing is moved
   out of them and nothing in them is deleted. They remain the specified home of the eventual
   implementations.
4. No document, commit message, README line or certificate may state or imply that the Rust kernel
   or the Go checker exists. The reference implementation is named as such in the CLI banner, in
   the certificate's own producer field, and in the README.

## Consequences

**The independence claim is materially weakened, and must be stated weakly.** The specification's
design has the checker written in a different language by a different implementation path, so that
a bug in the solver is unlikely to be mirrored in the checker. Two Python modules authored in the
same session share an author, a language, a standard library and a set of assumptions. What the
Python checker does establish: that the certificate is internally consistent, that its witness trees
re-derive, that its cut is minimal against the published clause database, and that its hashes match
the inputs. What it does not establish: that a shared misreading of the specification was caught.
Section 62 of the specification requires four independent oracles; this delivers a fraction of one,
and the certificate must not be described as independently verified until the Go checker exists.

**No performance claim is available.** The specification's Tier B promise for C and C++ is a
*measured* differential against the Rust hot path. There is no Rust hot path, so there is nothing to
measure against and no such claim may appear.

**The polyglot roster is unaffected in principle and stalled in practice.** Tiers B, C and D keep
their directory records and their declared consumer edges. None can be built here, so
`make polyglot-audit` cannot run and no language beyond Python may be described as exercised.

**The eventual Rust and Go implementations gain a reference oracle.** This is the one benefit worth
naming. A working Python implementation with a fixture corpus is exactly what the Rust kernel can be
differentially tested against when it is written — which is the role section 62 assigns to a
reference implementation. Building it first is not a detour from that plan; it is the first step
that plan needs.

**The cost of reversing is low and the cost of drifting is high.** Rewriting the kernel in Rust
later is bounded work against a specification and a fixture corpus. The real risk is that the Python
implementation is quietly treated as the deliverable and the Rust one never happens, with documents
gradually written as though the specified architecture were real. The protection against that is
this record plus the labelling rule in decision 4.

**M0 cannot be closed.** Its gate is `make m0-verify`, and `make` does not exist here. M0 stays not
started, and the milestone table must continue to say so regardless of how much Python runs.

## Alternatives considered

**Wait for the toolchains.** Correct if they were arriving; they are not, and the repository would
stay at zero working components indefinitely.

**Install them.** Out of scope for this session, and a toolchain installed ad hoc is exactly the
unpinned, unreproducible environment Part II section 74 exists to prevent. The devcontainer is the
right mechanism and is unbuilt because Docker is absent.

**Implement the kernel in Java, which is present.** It would satisfy the letter of "not the same
language as the checker" while satisfying nothing else: Java is not in the specified architecture
at Tier A, the JVM service role it does have is unrelated, and the result would be a third
implementation to maintain or delete.

## References

- ADR-0003, repository and module naming, superseded by ADR-0011 but binding on crate names.
- ADR-0005, the kernel boundary is a subprocess over content-addressed files.
- ADR-0012, the tier cadence, for what the polyglot audit expects.
- `docs/plan/PLAN_v1.md` section 4, the descope ladder, rungs D1 and D2.
