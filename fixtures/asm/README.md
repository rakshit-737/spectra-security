# x86-64 Assembly - byte-exact syscall-trace fixture emitter
Tier: B
Status: not started
Owning spec section: 73 (Part II), which supersedes Part I section 31.9
Milestone: M9 - Polyglot surface and performance

## The promise

Hand-authored syscall sequences whose emitted trace is byte-identical on every run, on every machine
that runs them. Part II section 73.1 states the promise as "byte-exact, hand-authored lowest-level
observed source".

Byte-exactness is the whole promise and it is not a stylistic preference. The obligation axioms -
the rules of the form `fd.read` implies `fd.open` - need two kinds of ground truth: a trace in which
the prerequisite genuinely occurred, and a trace in which it genuinely did not. Part I section 52.7
requires a must-fire and a must-not-fire test for every obligation axiom. Both need traces whose
content is authored rather than incidental, because a trace that varies between runs turns an axiom
test into a measurement of the emitter's noise. No libc, no address-space randomization dependence,
no timestamp counter, a fixed instruction sequence: these are the conditions under which the trace
is the same bytes twice, and every one of them is a reason assembly is here and a higher-level
language is not.

What is not promised: anything about a real kernel, a real workload, real hardware, or performance.
Part II section 73.11 forbids claiming "hardware-accelerated", "FPGA", "silicon" or "RTL-verified"
from the low-level components, and none of those words describe this one either. Part I section
52.12 also mentioned an assembly implementation of a hash inner loop benchmarked against a portable
baseline; Part II section 73.1 names this component's role as the fixture emitter only, and this
file does not promise the benchmark.

Nothing has been built. No trace has been emitted and no determinism has been demonstrated.

## What lives here

No file in this list exists yet.

- `.asm` sources, assembled for ELF64 with no libc and with position-independent execution disabled,
  one file per named fixture.
- The link step and its flags, driven from this directory's makefile.
- Golden traces, one per fixture, committed as the expected bytes.
- A pinned hash of each produced binary, so a toolchain change that alters the binary is visible
  before the trace comparison rather than after.
- A determinism runner that repeats each fixture and asserts the emitted trace is byte-identical
  across repetitions, and a second runner that asserts it across the CI runners Part II section 74.4
  places in T2.
- A manifest of which obligation axiom each fixture is ground truth for, on the must-fire side or
  the must-not-fire side.
- This component's `polyglot.toml` fragment, with every field Part II section 73.4 requires.

## Consumer edge

The declared consumer is the obligation-axiom test suite, owned by the kernel component and not by
this directory, plus the trace-hash assertion that Part II section 73.6's audit transcript records
for this component as `oracles/asm::trace_hash`.

If this directory is deleted, the obligation axioms lose the only trace source whose syscall
sequence is authored rather than produced as a side effect of running something larger. The
must-not-fire side is where that bites hardest: proving an axiom does not fire needs a trace that is
known to omit the prerequisite, and a trace emitted by any runtime with a standard library cannot be
known to omit anything.

That is a real edge. The axiom tests do not merely lose a check, they lose their inputs.

## How it is exercised

- CI job: `polyglot-b / asm-syscall-fixtures`, the component id Part II section 73.6's audit
  transcript uses for this row.
- Tier: T1 on changed paths per Part II section 73.9; T2 nightly for the full run plus the mutation
  leg, and T2 for the cross-runner byte-identity check that Part II section 74.4 places there
  because it needs a second runner. The toolchain image is `spectra/toolchain-b`, which Part II
  section 74.1 gives binutils and nasm.
- Component entrypoint: `make -C fixtures/asm traces`, in the shape Part II section 73.4 uses for
  the C component's entrypoint.
- Audit: `make polyglot-audit`.

## Mutation check

Operator `flip_byte(off, seed)` from the closed set in Part II section 73.5, which Part II names as
the operator for fixtures and encoders. Applied to this component's output in a scratch worktree:
one byte of the emitted trace is flipped at a seeded offset.

The gate that must go RED is `polyglot-b / asm-syscall-fixtures`, at the assertion Part II section
73.6's transcript records as `oracles/asm::trace_hash`. A single flipped byte must change the trace
hash and the comparison against the golden trace must fail on it.

This is the strictest mutation in Tier B and it should be, because it is the only one that matches
the promise exactly. The promise is byte-exactness; the mutation is one wrong byte. If one wrong
byte does not turn the gate red, the component is not byte-exact in any sense that is being checked,
and it is PADDING under Part II section 73.6 regardless of how carefully the assembly was written.

A flipped byte landing in the syscall number of a prerequisite call should also turn the
corresponding obligation axiom's must-fire test red. That is a second, seed-dependent consequence
and it is not the declared one: Part II section 73.4 requires exactly one `expect_red` naming one
job and one specific assertion, and the trace-hash assertion is the one that fails deterministically
for every seed.

The offset and the seed are not yet fixed.

## Not yet decided

- **`fixtures/asm/` against the committed `.gitattributes`.** Part II section 73.8 sets
  `fixtures/** linguist-detectable=false`, and the repository's `.gitattributes` already carries
  that line together with a second one covering `data/fixtures/**`. Part II section 73.1 counts
  x86-64 assembly as one of the authored executing languages. These are not automatically in
  conflict - Part II section 73.7 derives the prose figure from `artifacts/polyglot/audit.json` and
  not from Linguist - but Part II section 73.8's `BAR_INFLATION` check compares the authored-source
  byte count a language is credited with against the bar row it occupies, and a component that is
  counted in one place and invisible in the other has not been reasoned through. Either the assembly
  moves out of `fixtures/`, or the attribute is narrowed to the data files inside it, or
  `BAR_INFLATION` is defined to skip languages with no bar row. Decide before the first `.asm` file.
- **What captures the trace.** The fixture emits syscalls; something has to record them. Part I
  section 31.9 ran the binaries under the `ptrace` tap that Part I section 31.7 assigned to C. Part
  II section 73.1 gives C a different role - record framing and field scanning on the ingest hot
  path - and provides no Part II home for the tap. The capture path for this component is therefore
  currently unowned, and it is on this component's critical path rather than on C's.
- **Where the golden traces live.** Under `fixtures/asm/golden/`, which the committed
  `.gitattributes` already marks `linguist-generated=true` via its `golden/**` rule, or in the
  committed fixture tree at `data/fixtures/` that Part I section 32.2 describes. The two are marked
  differently and the choice interacts with the item above.
- **How far byte-identity is asserted.** Across repetitions on one runner is the minimum. Across two
  distinct runners is a T2 gate under Part II section 74.4. Across all four toolchain images is
  neither required nor excluded anywhere.
- **Which obligation axioms get fixtures.** Part I section 52.7 requires a must-fire and a
  must-not-fire test per axiom, and does not say that every axiom's ground truth comes from here.
  The split between assembly fixtures and generator-produced traces is not written down.
- **Whether this directory is the component root.** Part II section 73.4 requires the `paths` glob to
  match every executing source file exactly once, and `fixtures/` is otherwise a data tree. A
  component root inside a data tree is unusual enough that it should be an explicit decision rather
  than an inherited Part I path.
