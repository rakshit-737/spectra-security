# ADR-0005: The kernel boundary is a subprocess over content-addressed files

## Status

Accepted — 2026-09-20

## Context

SPECTRA is planned as three languages meeting at one seam. A Python service layer orchestrates:
ingest, entity resolution, the HTTP API, job state. A Rust binary — ECLIPSE (SPECTRA's proof kernel)
— does the grounding, the liveness pass, the silent envelope and the cut, and emits a certificate. A
Go binary re-validates that certificate without sharing code with the Rust one.

Part I never said how Python reaches either of them. It described the HTTP API across sections 35 to
38 and stopped there. What it did instead was name the components: section 32.4 mandated a Rust
`cdylib` with in-process Python bindings, and section 32.3 a thin Python binding package wrapping
it. That is a design decision made by naming a directory, which is the worst way to make one — the
feasibility review called this seam the single most likely place for the build to stall.

Four forces decide it.

**The checker has to be runnable by someone who does not have this repository.** This is the
project's central integration property. A sceptic must be able to take a published certificate and a
read-only content-addressed store and re-validate it with no Python, no database, no network and no
compose file. Part II section 75's non-goal 15 states it as a hard commitment: if either binary ever
needs Postgres, Redis or a running API to produce or validate a certificate, the offline
verification property has collapsed and the change is reverted. A linked extension module cannot be
that artifact. It is not a thing a stranger can run.

**Determinism is the project's first law.** Same inputs, same seed, same bytes out, on any machine.
An in-process boundary makes the kernel's inputs a function of the host process's memory state, its
allocator, its interpreter version and whatever else happens to be loaded. Replaying a run from
`argv` alone stops being possible, and "byte-identical replay" becomes a claim that can only be
checked by rerunning the whole service.

**Crash isolation.** Grounding and branch-and-bound over a large instance set can exhaust memory.
In-process, that takes the API worker down with it. Out of process, it is an exit code.

**Cost.** A subprocess per request costs a fork, an exec and a static binary start. That is not
free, and for a request that did little work it would be the dominant cost.

## Decision

The boundary between the Python layer and both binaries is **subprocess invocation over
content-addressed files**. There is no in-process binding of any kind.

1. **No in-process bindings.** No PyO3, no cffi, no ctypes, no cgo, no shared library boundary
   between Python and either binary. Part I section 32.4's `cdylib` component is removed rather than
   renamed, and Part I section 32.3's binding package is replaced by a subprocess client module.
   (That replacement sits on a recorded default rather than an answered question — see
   `docs/plan/DECISIONS.md`, D092, and ADR-0008.)

2. **No service between them either.** No kernel daemon, no gRPC service, no warm worker pool, no
   shared-memory ring, no persistent kernel session. Every proof run is a fresh process.

3. **Both binaries are pure functions of `(argv, store contents)`.** The parent passes object
   identifiers on `argv`; the child reads inputs from one content-addressed root, writes outputs
   into it, emits exactly one line of canonical JSON on stdout naming the outputs, emits
   newline-delimited JSON diagnostics on stderr, and exits with a code from a closed taxonomy.

4. **Neither binary accepts a filesystem path or a URL as an input reference.** Inputs are named
   only by hash-addressed object identifiers, plus exactly one store-root directory argument. This
   closes path traversal and server-side request forgery at the boundary itself rather than in
   request validation upstream.

5. **The verdict never travels in the exit code.** An UNSAFE result is a successful run: exit zero,
   status "ok", and the verdict inside the certificate. Code that infers a verdict from a return
   code is a build failure. A verdict string that is not bound to its scope — the rules hash, the
   catalog hash, the licences hash, and the non-adaptive attacker assumption — is not a
   representable value on either side of the boundary, and the checker refuses one.

6. **Only two codecs cross the boundary:** canonical JSON for anything a human or the checker must
   audit, and a compact binary form for the large machine-only structures. Canonical JSON here means
   sorted keys, no insignificant whitespace, integers only with floating point forbidden outright,
   no nulls, and no wall-clock time, hostname, absolute path, username or process id anywhere in the
   payload.

7. **Neither binary reads hidden configuration.** They run with stdin closed, with an environment
   containing nothing but a fixed timezone and locale, with a read-only root filesystem apart from
   the declared output directory, and with no access to a home directory, a dotfile or `/etc`.
   Hidden configuration is hidden nondeterminism.

8. **The ABI is versioned, pinned and hand-written on both sides.** The version is an integer, is
   mandatory on every invocation with no default and no auto-detection, is never reused, and is
   pinned in `spectra.toml`. The Rust and Go type definitions are each written by hand and neither
   is generated from the other; a schema directory records the third, checkable statement of the
   same contract, and is immutable after the commit that introduces it. Raising the version means a
   new schema directory, new hand-written types on both sides, and a migration note.

## Consequences

### Latency

**A process start is added to every proof run, and it is not optimised away.** The specification
budgets it as fork and exec plus static binary startup, on the order of single-digit milliseconds
(illustrative, not a target). The reasoning for accepting it: a proof request already performs
grounding over a large rule-instance set, so process startup is not expected to be on the critical
path. That expectation is unmeasured and must stay unmeasured-looking until the bench harness says
otherwise — nothing in this repository may state a latency figure that a run did not produce.

The negative form matters as much as the positive one. When process startup later looks expensive,
the permitted responses are to make the binaries start faster or to batch work into fewer
invocations. The forbidden responses are a warm pool, a daemon, a persistent session and a
shared-memory channel, because each of them reintroduces exactly the state that rules 3 and 7
remove. Reversing that requires superseding this record, not a patch.

**Timing may not influence anything.** No wall clock, no deadline, no elapsed-time measurement
anywhere that can affect a flag, a cut, a verdict or the contents of stderr. Resource limits are
expressed as deterministic step budgets, not timeouts. Timing is measured only from outside the
process, by the bench harness, into bench artifacts.

### The ABI

**Type drift moves from the compiler to a gate, and that is a real loss.** With an in-process
binding, changing a struct field breaks the build at the call site. Here, the Rust side and the Go
side can disagree silently until something checks them. The specification's answer is a contract
gate that compares the Rust types, the Go types and the schema field-for-field, plus golden tests
over the exact stdout line, the exact stderr bytes and every output object identifier, run on two
differently configured machines. Those gates are load-bearing in a way they would not otherwise be:
they are the only thing standing where a compiler used to stand. Neither exists yet.

**Two hand-written definitions is a deliberate duplication.** Generating one side from the other
would remove the drift risk and also remove the independence: a checker whose types are generated
from the kernel's types has a shared failure mode with it. The duplication is the price of the
independence claim, and the contract gate is what keeps the price bounded.

**Exit codes become an interface.** A closed taxonomy means a code outside it is itself a defect,
and every code in it needs at least one fixture that produces it. In particular, the checker
rejecting a certificate is a normal, expected outcome with its own code — the adversarial
certificate corpus depends on it — and must never be conflated with the checker failing.

**stderr becomes an interface too.** Diagnostics are byte-identical across machines for identical
inputs, which rules out progress bars, spinners, colour, elapsed time, addresses, thread
identifiers and debug-printed hash maps. The Python layer consumes structured fields and never
regex-parses prose.

### Elsewhere

**Process spawning is centralised.** Subprocess invocation appears in exactly one Python module, to
be enforced by a lint. A second spawn site is a second place where the environment, the argument
list or the working directory can differ, and therefore a second way to break determinism.

**The content-addressed store becomes the system's state.** Objects are immutable, written by
write-then-rename, never mutated, never renamed, and removed only by a garbage collector. The
database indexes runs; it does not hold facts, instances, licences, corridors or invariant sets. The
store is mounted read-only into the checker.

**Crash and memory isolation come for free**, as does the ability to run either binary under a
seccomp profile that denies the network syscall set and assert the deny counter stayed at zero.

**The independence of the checker becomes checkable rather than asserted.** A build-graph lint over
the kernel's and the checker's dependency trees can state that neither contains a database, HTTP,
DNS, queue or telemetry client. A sentence in a README saying the checker is independent is worth
nothing; a dependency lint is worth something. This is the decisive argument for the whole record.

### What this does not establish

A passing checker does not mean "verification requires no trust". It requires trusting the hash
implementation, both compilers and the hand-written rule table, and the project must say so. Nor
does this record establish that the checker re-derives everything — what it re-derives will be
stated exactly, in a checker-scope document, and the boundary only ensures it received hashed
inputs and the published instance set. The system is not stateless; the store is the state.

Byte-identical replay, when it can be stated at all, will be stated for the declared machine
configurations and the pinned image, not for "any machine".

Every component named here is unimplemented. Status: not started.

## Alternatives considered

### In-process bindings from Python to the Rust kernel

The strongest case: no serialization, no process start, no ABI to keep in sync, type errors caught
at build time, and a far simpler call site. For a system where the kernel were only ever called by
this Python layer, it would be the obvious choice.

Rejected because of the checker. The checker must be an artifact a stranger can run against a
published certificate with nothing else installed, and an extension module is not that artifact.
Once the checker has to be a standalone binary, making the kernel one too costs almost nothing and
buys crash isolation and replay from `argv`.

### A long-lived kernel service over a local socket

Removes the per-request process cost and keeps the binaries separate. Rejected because it
reintroduces persistent state across runs, makes replay depend on the service's history rather than
on `argv`, and turns the offline verification story into "run a service first". Non-goal 15 forbids
exactly that.

### Passing payloads on stdin and stdout instead of through a store

Simpler, with no store to garbage-collect. Rejected because the large inputs would be copied on
every invocation, because the same bytes could no longer be shared between the kernel run and the
checker run, and because content addressing is what makes an output object identity rather than a
file.

## References

- Part II section 69 — the boundary, the invocation contract, the store, the codecs, the exit-code
  taxonomy, the diagnostic format, the step budgets and the gates.
- Part II section 75, non-goal 15 — the kernel and checker have no service dependencies.
- Part I sections 32.3 and 32.4 — the superseded in-process binding components.
- `spectra.toml`, `[abi]` — the pinned ABI integer and why it lives there.
- `docs/plan/DECISIONS.md`, D092 — the still-open question of exactly what replaces the binding
  package.
- ADR-0003 — the module and binary names this record depends on.
- ADR-0008 — how an open decision is carried without stalling the build.
