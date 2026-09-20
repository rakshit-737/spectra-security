# ADR-0004: The proof-kernel acronym stays in prose and out of every name

## Status

Accepted — 2026-09-20

## Context

ECLIPSE (SPECTRA's proof kernel) is an internal acronym — Evidence-Licensed Cut Proofs over Silent
Envelopes. It names the component that grounds a monotone Horn program, admits unobserved attacker
steps only inside provably blind sensor windows, and emits the content-addressed certificate an
independent checker re-validates. The acronym is good: it is memorable, it expands into the actual
mechanism, and it gives the paper a handle for the thing the paper is about.

It also collides, completely, with a large and active trademark family.

- The Eclipse Foundation, and the Eclipse Public License.
- The Eclipse IDE, which is what essentially every search for the word returns.
- Eclipse Temurin and Adoptium — a JVM toolchain this repository actually vendors, because the
  language roster includes a Java tier. The collision is therefore not hypothetical: the acronym
  and the trademark would appear in the same build.
- Eclipse Jetty, Eclipse Mosquitto, and a long tail of other Foundation projects.

Part I built the collision straight into the tree. Section 32.4 named the Rust workspace crates
after the acronym — a core crate, a rules crate, a cut crate, a liveness crate and a certificate
crate, all sharing the acronym as their prefix. Section 32.6 added a Haskell reference crate with
the same prefix, and section 32.3 a Python package built from it. Under that layout the acronym
would appear in crate names, directory names, import paths, published package names, build output
and stack traces — that is, in every machine-readable surface the project has.

Part II section 73.10 overrides that, and non-goal 19 in Part II section 75 requires the repository
to state the collision and disclaim any relationship.

The forces are in tension. Dropping the acronym entirely costs the paper its handle and costs the
specification a great deal of rewriting, for a problem that is fundamentally about search results
and trademark hygiene rather than about correctness. Keeping it in names costs the project a
permanent ambiguity, an unsearchable component, and a live trademark question in a repository whose
own continuous integration pulls the colliding mark's toolchain.

There is a third option, and it is the one the specification takes: keep the acronym where it is
useful and ban it where it is expensive.

## Decision

The acronym is kept, bound on first use, and banned from every name.

**1. Bound on first use.** The first occurrence in every document — README, any file under `docs/`,
the UI About panel, the demo script, and any paper abstract — is exactly `ECLIPSE (SPECTRA's proof
kernel)`. A bare leading occurrence is a defect, to be caught by the banned-phrase gate under the
code `UNBOUND_ECLIPSE`. In user-facing prose, "the SPECTRA kernel" is preferred wherever confusion
is possible; the acronym is reserved for internal and specification contexts.

**2. Banned from every machine-readable surface.** The lowercase form of the acronym appears in no
crate name, module name, package name, directory name, file name, binary on `PATH`, HTTP path
segment, JSON field name, file extension, or magic bytes in any certificate. A grep gate enforces
it under the code `ECLIPSE_IN_ARTIFACT_SURFACE`.

**3. The names that replace Part I's.**

| Surface | Name |
| --- | --- |
| Rust crate prefix | `spectra-` |
| Kernel crate | `spectra-kernel` |
| Prove command | `spectra prove` |
| Verify command | `spectra verify` |
| Certificate media type | carries `spectra` |

Part I section 32.4's five acronym-prefixed crates are renamed to the `spectra-` prefix; Part I
section 32.6's acronym-prefixed Haskell reference crate is renamed likewise. Part I section 32.3's
acronym-named Python binding package is not renamed but removed, because ADR-0005 removes the
in-process binding it existed to wrap; its replacement is a subprocess client module. The precise
internal crate split is not fixed by this record.

**4. This record's own file name.** An earlier working title for this record spelled the acronym in
the file name. It was changed, because rule 2 covers file names and a record that breaks its own
rule is not a record. The file is named for what it decides.

**5. `docs/naming.md` is required** and must state: the collision, this decision, the plain fact
that the project has no affiliation with the Eclipse Foundation and uses none of its marks, the
project's own licence named explicitly rather than by an abbreviation that would compound the
collision, and one reserved alternative name held for the event that the acronym has to go.

## Consequences

**A rename costs documentation only.** This is the whole point of the decision. If the collision
becomes a problem — a reviewer objects, a maintainer complains, an index conflates the two, or a
trademark question is raised — the project renames by editing prose. No crate is renamed. No import
path changes. No certificate field changes. No wire schema changes. No published artifact is
invalidated. Compare ADR-0003, where the equivalent change rewrites every import path in the Go
tree: the difference is exactly what rule 2 buys.

**The kernel is not searchable by its acronym.** Someone who reads the paper and then searches this
repository for the acronym finds prose and nothing else — no crate, no file, no symbol. That is a
genuine loss of navigability and it is accepted. `docs/naming.md` is the mitigation: it is the one
place that maps the acronym to the artifacts it names.

**The vendored toolchain will contain the banned string, and the gate has to tolerate that.** The
Java tier vendors a JVM distribution whose name contains the colliding mark, so the string will
appear in toolchain pins, lockfiles and vendored paths. A grep gate with no exceptions would make
the repository unbuildable. The specification does not resolve this, and the conservative default
adopted here is: the gate carries a narrow allowlist limited to toolchain pin files and vendored
third-party paths, every entry carrying a rationale, and covering nothing the project itself
authored. This is an unresolved detail recorded rather than assumed, in the sense of ADR-0008 — the
principle is decided, the allowlist mechanism is not.

**Two gates now have to exist that otherwise would not.** `UNBOUND_ECLIPSE` and
`ECLIPSE_IN_ARTIFACT_SURFACE` are both work this decision creates, and neither exists yet. Until
they do, rule 1 and rule 2 are conventions held by hand, and this record must not be cited as
evidence that the tree is clean.

**Every document pays a small tax on its first sentence.** Binding the acronym on first use makes
the opening of each document slightly heavier. Accepted: an unbound acronym in the first line of a
public README is precisely where the collision does its damage.

**The specification and the tree will read differently.** Part I says one thing about crate names
and the tree says another. Anyone reading Part I section 32.4 alone will build the superseded
layout. That is not unique to this decision — it is the general hazard ADR-0006 addresses — but it
is acute here, because the superseded names are concrete enough to copy.

**What this does not establish.** Renaming a component says nothing about what that component does.
The kernel is not implemented; its status is "not started". Nothing here is a claim about the
Eclipse Foundation's marks, their scope, or the legal question of whether the collision would
matter. The decision is to make the question cheap to answer either way, not to answer it.

## Alternatives considered

### Drop the acronym entirely

The strongest case: it removes the problem rather than managing it, needs no gates, needs no
allowlist, and stops a reader ever having to learn that the internal name and the artifact names
differ. A project that renames now pays once; a project that keeps a collision pays a little
forever.

Rejected because the acronym expands into the actual mechanism, which is exactly what a paper needs
a name to do, and because rule 2 already reduces the ongoing cost to prose. If the assessment turns
out wrong, this record is superseded and the cost of the reversal is the documentation edit rule 2
was designed to preserve.

### Keep the acronym in names and rely on the disclaimer

The argument is that non-goal 19 already requires a plain disclaimer, that the project is small, and
that nobody confuses a security-research repository with a Java IDE for long.

Rejected because it gets the cost structure backwards. The disclaimer handles the trademark
question; it does nothing about search, indexing, or a reviewer's index terms, and it makes a future
rename a code change instead of a prose change. It also puts the colliding string into a repository
whose own build pulls the colliding mark's toolchain, which is the one context where the confusion
is not theoretical.

### A different acronym that does not collide

Considered and not pursued here. The specification is written around this one throughout both parts,
and changing it would touch far more text than the collision costs. `docs/naming.md` holds one
reserved alternative precisely so that this option stays open and pre-decided rather than being
improvised under pressure.

## References

- Part II section 73.10 — the collision, the decision, and the two gate codes.
- Part II section 75, non-goal 19 — the required disclaimer and the preference for "the SPECTRA
  kernel" in user-facing prose.
- Part I sections 32.3, 32.4 and 32.6 — the superseded crate and package names.
- `spectra.toml`, `[names]` — the naming surface, written so that the banned string does not appear
  in it at all.
- ADR-0003 — the rest of the naming surface, and what a real rename costs.
- ADR-0005 — why the Python binding package is removed rather than renamed.
- ADR-0008 — how the unresolved allowlist detail is carried.
