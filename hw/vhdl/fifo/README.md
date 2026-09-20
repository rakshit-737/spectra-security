# VHDL - independently authored bounded FIFO, differential partner to the Verilog one
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places VHDL in Tier D as the differential partner to `hw/verilog/fifo/`.
Part I section 31.29 described a different component - a hardware liveness monitor - and is
superseded. Nothing here has been written.

## The promise

One narrow thing, and it is a differential promise rather than a productive one: this directory
holds an independently authored implementation of the same bounded FIFO that `hw/verilog/fifo/`
implements, and divergent drop traces fail the build.

For the promise to mean anything, "independently authored" has to be enforced rather than
intended:

- Written from the FIFO's stated behaviour - depth, full and empty conditions, the cycle at
  which a write to a full queue is dropped, the ordering of concurrent read and write - not
  from the Verilog source.
- Not a translation. A line-by-line rendering of `fifo.v` into VHDL reproduces its off-by-one
  errors and turns the cross-check into a syntax exercise.
- Consuming the same stimulus and emitting the same loss-trace schema, because otherwise the
  two are not comparable - but sharing no code that computes the drop decision.

What the promise excludes. Part II section 73.11 forbids claiming "hardware-accelerated",
"FPGA", "silicon" or "RTL-verified" from Verilog or VHDL, and section 73.1 adds that the FIFOs
model a lossy buffer and do not model any real logging appliance. Nothing here runs on
hardware, nothing here is formally verified, and no vendor's product is being modelled.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `fifo.vhd` - the entity and architecture: the bounded queue, the full and empty conditions,
  and the drop indication when a write arrives at full occupancy.
- `drop_trace.vhd` - the observation wrapper recording, per cycle, the arriving record
  identifier, the occupancy and the fate.
- `tb/fifo_tb.vhd` - the testbench driving the design from the same committed stimulus the
  Verilog side uses.
- `emit/` - the step converting the simulator output into the loss-trace artifact, in the same
  schema as the Verilog side's.
- `Makefile` - analyse, elaborate and run, as one command.

A lint is expected to forbid any reference from this directory into `hw/verilog/fifo/`, and
vice versa, outside the comparison harness. Without it, independence is honour-system.

## Consumer edge

Weak, and this section says so rather than dressing it up. This is one of the two thinnest
edges in the roster.

Delete this directory and nothing downstream stops working. The Verilog side still simulates
the FIFO, still emits the loss trace, and the bounded-buffer degradation cell still gets its
ground truth. No verdict changes, no certificate changes, no published number loses its
producer. What is lost is the check - the only independent confirmation that the Verilog FIFO's
drop decisions are the FIFO's behaviour rather than one author's reading of it.

That means the consumer edge is `xcheck/fifo::drop_trace_eq` and nothing else, which makes
section 73.3.1's ownership question decisive rather than procedural. If that gate lives in this
directory and is run by this directory's job, this component's only consumer is its own test
suite and the audit fails it with `SELF_CONSUMING`. The gate has to be owned by a neutral
cross-check harness or by the Verilog component, and that ownership has to be recorded in
`polyglot.toml` before the first source file is committed.

Stated plainly: this component survives the load-bearing test only if the cross-check gate is
real, is owned elsewhere, and goes red under `constant_result`. There is no weaker basis on
which it survives, and section 73.6's remedy if it does not is deletion of the directory rather
than a better rationale for keeping it.

## How it is exercised

- CI job: `polyglot-d / hdl-fifo-vhdl`. That component id is the one Part II section 73.6's
  audit transcript uses, so it is fixed rather than proposed.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release, and forbids `continue-on-error` or an `if: false` guard on
  a polyglot job.
- Make target: `make hdl-fifo-vhdl` analyses, elaborates and runs the simulation over the
  committed stimulus and writes the loss trace. The comparison against `hw/verilog/fifo/` and
  the mutation leg run under `make polyglot-audit`.
- Toolchain: a pinned open-source VHDL toolchain, vendored. Part II section 74.1's four
  toolchain images do not list an HDL simulator by name; see "Not yet decided".

## Mutation check

Operator: `constant_result`, mandatory for every Tier D cross-check under Part II section 73.5.

The corruption: the drop decision returns a fixed answer regardless of occupancy - every write
accepted, or every write at any occupancy dropped. The emitted loss trace keeps its schema, has
one row per input record and passes any fate-totality check; every fate in it is the same.

The gate that must go red: `xcheck/fifo::drop_trace_eq`, the assertion that this side's loss
trace and the Verilog side's are identical row for row on the same stimulus. Part II section
73.6's transcript names exactly this gate for this component. Under the mutation the two traces
diverge on the first record whose true fate differs from the constant, and the assertion fails
naming that row, the occupancy at that cycle and the two fates.

Why `constant_result` and not `drop_records`: the Verilog side already carries the partial-row
deletion mutation, which tests whether the comparison notices missing rows. This side has to
test something different - whether the comparison notices that the fates are wrong while the
shape of the trace is right. A comparison that checks row counts, or hashes a canonicalised
record-identifier list without the fate column, stays green under a row-shaped constant trace.
That is the failure this mutation is aimed at.

If `constant_result` leaves the gate green, the cross-check is not comparing the thing the
component exists for, and the component is padding under section 73.3.3.

## Not yet decided

- **Part I's liveness monitor has no owner.** Part I section 31.29 made VHDL a hardware
  liveness monitor asserting a blind signal on inter-arrival overrun, with a chain-break output
  and an interval-equality gate against the Rust liveness pass, explicitly written from the
  liveness specification rather than from the Rust source. That was an independent check on
  interval arithmetic and boundary conditions on a decision path. Part II section 73.1 reassigns
  VHDL to the FIFO and names no owner for the interval check. Whether it moves, survives as a
  second component, or is dropped, is undecided and is recorded in `docs/plan/CONFLICTS.md`.
- **Whether VHDL survives the roster at all.** Part II section 73.1 lists it in Tier D; Part II
  section 75.5.1 removes VHDL from the target set unless a named, executing, mutation-proved
  job exists for it, and section 75.5's ladder rung D6 names only R, Julia and Octave as Tier
  D. These are not reconciled.
- **Who owns the cross-check gate.** See "Consumer edge". This decides whether the component
  can pass section 73.3.1 at all, and it has not been made.
- **Where the independence line falls.** The two FIFOs must consume the same stimulus and emit
  the same schema to be comparable, but must share no drop-decision code to be independent.
  Whether they share a stimulus reader, a schema definition, or only a file format, has not
  been decided - and the strength of the cross-check depends entirely on that answer.
- **Directory path.** `hw/vhdl/fifo/` is not stated in Part II; Part I section 31.29 used
  `hw/vhdl/liveness_monitor/`, which is the superseded role. The path above is a working choice
  and must be fixed in `polyglot.toml` before the first source file is committed.
- **Toolchain image.** Section 74.1's four images list no HDL toolchain. Without one this
  component cannot execute in CI, and under section 73.3.2 a component that cannot execute
  cannot pass the load-bearing test.
- **Whether a differential pair of simulated FIFOs earns two roster entries.** This is the
  honest version of the question a reviewer will ask. The answer has to be either a real gate
  that goes red, or deletion of one of the two directories. It should not be answered with
  prose.
