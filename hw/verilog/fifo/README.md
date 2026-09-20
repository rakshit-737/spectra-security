# Verilog - simulated bounded FIFO log sink with exact drop ground truth
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places Verilog in Tier D and rewrites what it models. Part I section 31.28
described a different component - a synthesizable security state machine - and is superseded.
Nothing here has been written.

## The promise

One narrow thing: a simulated bounded FIFO that, when driven with a record arrival trace,
produces a loss trace with exact drop ground truth - which records were dropped, at which
positions, under which occupancy - for the bounded-buffer degradation cell.

The value is the exactness of the ground truth, not the hardware. A bounded queue could be
simulated in any language; what a cycle-accurate simulation gives is a drop set that follows
from the queue's occupancy at each cycle rather than from a sampling decision made by the same
harness that later measures the effect. The degradation study needs a loss pattern whose
structure it did not choose.

What the promise excludes, explicitly. Part II section 73.11 forbids claiming
"hardware-accelerated", "FPGA", "silicon" or "RTL-verified" from Verilog or VHDL, and section
73.1 adds that the FIFOs model a lossy buffer and do not model any real logging appliance - no
document may name one. So:

- Nothing here runs on hardware. It is a simulation, run by an open-source simulator in CI.
- This is not a model of any vendor's log forwarder, collector or appliance, and none is named.
- Nothing is verified in the formal sense. The FIFO is simulated and its output is compared
  against an independently authored FIFO in `hw/vhdl/fifo/`.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `fifo.v` - the bounded FIFO itself: depth, write and read interfaces, full and empty flags,
  and an explicit drop signal asserted when a write arrives at full occupancy.
- `drop_trace.v` - the observation wrapper that records, per cycle, the arriving record
  identifier, the occupancy, and whether the record was accepted or dropped.
- `tb/fifo_tb.v` - the testbench driving the FIFO from a committed arrival trace.
- `tb/stimulus/` - the committed arrival traces, derived from fixture record timing rather than
  invented, with their derivation recorded.
- `emit/` - the step that converts the simulator's output into the loss-trace artifact the
  degradation harness reads, in a stable field and row order.
- `Makefile` - the simulator invocation, so the entry point is one command with no arguments.

The loss trace is expected to carry, per record, the fate the degradation ledger needs: whether
it was delivered or not delivered, and if not, why. Part II section 61's ledger requires one
row per pre-perturbation record identifier and a lint - `ledger-fate-total` - that every record
has exactly one fate. A loss trace that does not account for every input record cannot feed it.

No record is ever dropped silently anywhere in SPECTRA; Part II section 61 requires a
reason-coded quarantine instead. That rule governs the ingest path, not this simulation, whose
entire purpose is to produce a loss that is known exactly. The distinction has to be kept
visible in the artifact: these drops are ground truth, not pipeline behaviour.

## Consumer edge

Real but narrow, and it depends on a cell that has not been specified.

Delete this directory and the bounded-buffer degradation cell loses its loss-trace source.
Under Part II section 61 the degradation matrix crosses completeness levels with perturbation
operators, each operator drawing from its own named random stream, and every published cell
carries median and IQR over seeds. A bounded-buffer cell that took its losses from a seeded
deletion operator rather than from a simulated queue would still produce a number - it would
just be measuring a loss pattern the harness chose. The edge is therefore the loss pattern's
provenance, not the existence of a number.

So: deleting this directory does not break the matrix, does not break the kernel, and does not
change a verdict. It removes one cell's claim to have a loss pattern that the measuring harness
did not design, and it removes the differential partner that `hw/vhdl/fifo/` exists to be
compared against.

That is worth having and it is not worth overstating. Part II section 75.5's descope ladder
puts Tier D at rung D6, cut before the checker's re-grounding and before the matrix's breadth,
and section 73.9 makes a red job here non-blocking for a milestone. A component cut sixth from
the bottom of the ladder is not on the critical path.

The binding question for section 73.3.1 is which component owns the consumer: the degradation
harness must read this loss trace, and that read must be visible in the build graph. If the
only thing that reads the loss trace is this directory's own testbench, the audit fails it with
`SELF_CONSUMING`.

## How it is exercised

- CI job: `polyglot-d / hdl-fifo-verilog`, in the Tier D workflow. The id is proposed by
  symmetry with `hdl-fifo-vhdl`, which Part II section 73.6's transcript does name.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release, and forbids silencing it.
- Make target: `make hdl-fifo-verilog` compiles the design and the testbench, runs the
  simulation over the committed stimulus and writes the loss trace. The cross-check against
  `hw/vhdl/fifo/` and the mutation leg run under `make polyglot-audit`.
- Toolchain: a pinned open-source Verilog simulator, vendored. Part II section 74.1's four
  toolchain images do not list an HDL simulator by name; see "Not yet decided".

## Mutation check

Operator: `drop_records(p, seed)`, from the closed set in Part II section 73.5.

The corruption: a seeded fraction of the rows is deleted from the emitted loss trace after the
simulation and before the artifact is written. The remaining rows are internally consistent -
correct occupancy, correct fate, correct ordering - so nothing in an individual row is wrong.
The trace simply no longer accounts for every input record.

The gate that must go red: `xcheck/fifo::drop_trace_eq`, the assertion that this side's loss
trace and the VHDL side's loss trace are identical row for row on the same stimulus. Part II
section 73.6's transcript names that gate for the VHDL component, and it is the same gate. The
VHDL side accounts for every record; under the mutation this side does not, so the comparison
fails on the first missing row.

A second gate should also go red and the audit records it: the degradation ledger's
`ledger-fate-total` lint, which requires every pre-perturbation record identifier to have
exactly one fate. A loss trace missing rows leaves records with no fate at all.

The operator is chosen because it attacks the property the component exists for. `flip_byte`
would corrupt a field and might be caught by a schema check that has nothing to do with drop
accounting; `constant_result` would produce a trace so obviously wrong that any assertion would
catch it. A partial row deletion fails only a gate that is actually checking the drop set.

## Not yet decided

- **Three mutually exclusive component definitions exist in the specification.** Part I section
  31.28 makes Verilog a synthesizable Moore FSM over the identity, session and privilege
  dimensions with an illegal-transition output, checked against the software engine cycle for
  cycle. Part I section 32.6 describes an RTL model of a unit-propagation counter datapath.
  Part II section 73.1 makes it a bounded FIFO log sink. Part II does not say the first two were
  dropped. The FIFO is recorded above because Part II governs, but the retirement of the other
  two has not been written anywhere they would be read.
- **Whether Verilog survives the roster at all.** Part II section 73.1 lists it in Tier D; Part
  II section 75.5.1 removes Verilog from the target set unless a named, executing,
  mutation-proved job exists for it, and section 75.5's ladder rung D6 names only R, Julia and
  Octave as Tier D. These are not reconciled.
- **The bounded-buffer degradation cell is not specified.** Part II section 61 enumerates
  perturbation operators and the ledger, but does not name a bounded-buffer cell or say how a
  loss trace from a simulation is applied alongside the seeded operators. Without that, the
  consumer edge above is a plan rather than a fact.
- **Directory path.** `hw/verilog/fifo/` is not stated in Part II; Part I section 31.28 used
  `hw/verilog/sec_state_fsm/`, which is the superseded role. The path above is a working choice
  and must be fixed in `polyglot.toml` before the first source file is committed.
- **Toolchain image.** Section 74.1's four images list no HDL simulator. Either an image gains
  one or this component cannot execute in CI, which under section 73.3.2 means it cannot pass
  the load-bearing test.
- **How the stimulus is derived.** "Derived from fixture record timing" is the intent, but the
  derivation is not specified, and a stimulus chosen to produce an interesting drop pattern
  would reintroduce exactly the harness-chose-the-losses problem this component exists to
  avoid.
- **Whether the two FIFOs may share a stimulus format.** They must be independently authored to
  be a differential pair, but they have to consume the same stimulus to be comparable. Where
  the line falls - shared stimulus file, shared reader, shared nothing - has not been drawn.
