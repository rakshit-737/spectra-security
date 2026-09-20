# YARA - declarative labelling of generator artifact blobs
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places YARA in Tier D and narrows its role sharply from Part I section
31.31's. Nothing here has been written.

## The promise

One narrow thing: YARA is the sole pattern language in which the technique labels on generator
artifact blobs are written, and those labels are used by the goal-correspondence test.

The case for a declarative pattern language here is small and specific. The fixture generator
stages synthetic artifact blobs as part of a scenario. Something has to say which technique
each blob is an instance of. Written as patterns in a rule file, those labels are data a
reviewer reads directly and a diff shows completely; written as procedural matching inside the
generator, the same labels are a function of generator control flow and a reviewer has to
reconstruct them. The promise is about auditability of the labelling, not about detection.

What the promise excludes, and the exclusions matter because this language carries a great deal
of unearned connotation:

- No detection claim. Nothing here detects anything in any real environment. These rules match
  blobs that the generator itself wrote, in a fixture set, offline.
- No real samples. Part I section 31.31's constraint stands: the staged artifacts are synthetic
  files produced by the scenario generator. No real malware, no real samples, no hashes of real
  samples, at any point, for any reason.
- No evidence role. Under Part II section 73.1 these matches label fixtures for a test. They do
  not become facts the kernel grounds over. See "Not yet decided" - this is a change from Part
  I and it is a significant one.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `techniques/` - one rule file per technique family, each rule carrying the technique
  identifier as metadata so that the label is the rule's declared output rather than its name.
- `index.yar` - the include set, so that the scan is one invocation over one entry point.
- `tests/must_match/` - for every rule, at least one generated blob it must match.
- `tests/must_not_match/` - for every rule, blobs it must not match, including the near-misses
  that a loosely written pattern would catch.
- `tests/benign/` - a corpus of generated benign blobs over which the whole rule set must
  produce no match at all.
- `emit/` - the step that runs the scan and writes the label artifact in a stable order: one
  row per blob, with its technique label or an explicit absence.
- `Makefile` - compile, scan, and run the match, non-match and false-positive suites.

Every blob in the fixture set must receive exactly one label or an explicit unlabelled marker.
A labelling artifact that silently omits blobs cannot support a correspondence test, because
the test cannot distinguish "no technique" from "not scanned".

## Consumer edge

Honest answer: currently unverifiable, because the consumer named in the specification is named
only once and defined nowhere.

Part II section 73.1 says the labels are "used by the goal-correspondence test". That phrase
appears exactly once in the whole specification - in that table cell - and no section defines
what the goal-correspondence test asserts, which component owns it, or what it consumes. Until
it is defined, this component cannot satisfy Part II section 73.3.1, which requires a named
downstream artifact owned by a different component. A consumer that exists only as a phrase in
the table that assigns the component is not a consumer edge; it is the same claim restated.

What can be said now:

- If the goal-correspondence test asserts that the techniques a scenario's goal implies are the
  techniques actually staged in its fixtures, then deleting this directory removes the label
  side of that correspondence and the test has nothing to compare the goal against. That is a
  genuine edge.
- If no such test is written, deleting this directory breaks nothing at all, and the component
  is padding. Part II section 73.6's remedy is deletion of `rules/yara/` in the same commit
  that discovers it, recorded in the deletion ledger with the mutation that exposed it.

This page states that plainly rather than constructing a plausible-sounding consumer, because
constructing one is precisely the behaviour section 73.0 exists to prevent.

## How it is exercised

- CI job: `polyglot-d / fixture-labels-yara`, in the Tier D workflow. The component id is
  proposed; Part II section 73.6's transcript does not include a YARA row.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release, and forbids silencing it with `continue-on-error`.
- Make target: `make yara-labels` compiles the rule set, runs the scan over the fixture blobs,
  writes the label artifact and runs the match, non-match and false-positive suites. The
  mutation leg runs under `make polyglot-audit`.
- Toolchain: a pinned YARA engine, vendored. Part II section 74.1's four toolchain images do
  not name one; see "Not yet decided".

## Mutation check

Operator: `empty_output`, from the closed set in Part II section 73.5.

The corruption: the scan step writes a zero-byte label artifact and exits successfully. Nothing
is malformed, nothing errors, and every step reports success. There are simply no labels.

The gate that must go red: the goal-correspondence assertion - proposed as
`gates/goal-correspondence::technique_labels` - which compares the techniques a scenario's goal
implies against the techniques its staged fixtures are labelled with. With no labels, every
expected technique is unmatched and the assertion fails naming the scenario and the missing
techniques.

This operator is the right one specifically because it is the cheapest possible failure. A
labelling component whose gate survives an empty label set is a component whose labels nobody
reads. `constant_result` - every blob labelled with the same technique - is the natural second
mutation and should also turn the same gate red; if it does not, the correspondence test is
checking that labels exist rather than what they say.

Because the gate is not yet defined, this mutation cannot yet be run. That is the correct state
for session one and it is also the reason this component's manifest entry cannot be written
yet: Part II section 73.4's lint requires `expect_red` to name both a job and a specific
assertion, and a missing assertion fails with `MUTATION_UNDERSPECIFIED`.

## Not yet decided

- **The goal-correspondence test is undefined.** See "Consumer edge". This is the open question
  that decides whether this directory exists. It needs a section, an owner and an assertion
  before any rule is written, because section 73.11 forbids adding a language without a
  manifest entry that passes all four load-bearing checks first.
- **YARA's demotion from evidence to labelling is not stated as a change.** Part I section
  31.31 made YARA matches into evidence events with stable identifiers, feeding rules whose
  bodies require file-content facts, with a match appearing as a leaf in the counterexample
  tree in the demo. Part II section 73.1 reduces YARA to fixture labelling for one test. Part
  II section 73.9 additionally makes a red Tier D job non-blocking for a milestone, so under
  Part I's reading a component the counterexample tree depends on would be allowed to stay red
  through a milestone. Either the file-content facts have another producer, or that rule body
  class is gone; neither is stated.
- **Directory path.** `rules/yara/` is carried over from Part I section 31.31 and is not
  restated in Part II section 73. It is a working choice rather than a specified one.
- **Toolchain image.** Section 74.1's four images name no YARA engine. Without one the
  component cannot execute in CI, and under section 73.3.2 a component that cannot execute
  cannot pass the load-bearing test.
- **Whether labels are metadata or rule names.** A label carried as rule metadata survives a
  rule rename; a label that is the rule name does not. This determines whether a refactor of
  the rule set silently changes the correspondence test's input, and it has not been chosen.
- **How the false-positive corpus is generated.** Part I section 31.31 specified a benign
  corpus with zero matches allowed. The corpus has to be generated by the same generator under
  a declared seed, or the gate measures the corpus rather than the rules. The derivation has
  not been specified.
- **The `linguist-language` question.** Part II section 73.8 permits that attribute only to
  correct a genuine misdetection and requires a comment naming the misdetection, failing with
  `LINGUIST_OVERRIDE_UNJUSTIFIED` otherwise. Part I section 31.46 applied it to this directory
  without such a comment. Whether the rule files are detected correctly without an override has
  not been checked, and an override added to make the language appear in the bar would be the
  inflation section 73.8 bans.
