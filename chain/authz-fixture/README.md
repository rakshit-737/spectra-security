# Solidity - offline EVM event-log source class
Tier: D
Status: not started
Owning spec section: 73
Milestone: M9

Part II section 73.1 places Solidity in Tier D and rewrites its role. Part I section 31.27 gave
it a role Part II explicitly forbids; the forbidden reading is recorded below so that nobody
reintroduces it from Part I. Nothing here has been written.

## The promise

One narrow thing: this directory supplies one estate source class, and the property that makes
it worth having is that its ordering guarantee is intrinsic to the producer rather than granted
by the lab harness. Every other source in the observed estate is ordered because the harness
says so. An EVM event log is ordered because of how the producer works.

That is the whole promise, and the negative half of it is longer than the positive half. Part
II section 73.1's Tier D negative requirements state it in these words: Solidity provides no
security property that the BLAKE3 sequence chain does not already provide for SPECTRA's own
artifacts. It is an estate source class, not a notary.

Forbidden, by section 73.1 and repeated in section 73.11:

- "blockchain-anchored"
- "immutable audit anchor"
- "tamper-proof certificates"

No SPECTRA certificate, hash or verdict is ever written to a chain. There is no anchor
registry. Part I section 32.6's optional certificate anchor registry is exactly the artifact
Part II says must not exist, and it is not built.

Everything runs offline: Foundry for the build and the test suite, `anvil` for a local node.
No mainnet, no testnet, no RPC provider, no keys with value, no network access of any kind. The
mutation leg of the audit additionally requires that the run touched no network socket, so an
accidental RPC dependency is caught by the audit rather than by a reviewer.

## What lives here

No code exists yet. When it does, this directory is expected to hold:

- `foundry.toml` - the pinned Solidity version and the offline profile.
- `src/AuthorizationRegistry.sol` - a role registry emitting the authorization events that make
  up this source class: a grant, a revocation, and a use of an authorization.
- `test/AuthorizationRegistry.t.sol` - the Foundry suite, including an invariant test that a
  use is always preceded by a grant for that role, which is the on-chain form of an obligation
  pair.
- `script/Emit.s.sol` - the deterministic scenario script that drives the contract to produce a
  fixed event sequence against a local node.
- `emit/` - the harness that runs `anvil`, applies the script, reads the event log back and
  writes it out in the format the ingest adapters expect.
- `fixtures/` - the committed expected event log for the deterministic scenario, so that a
  change in the contract or the toolchain shows up as a diff rather than as a silent drift.

The emitted log is consumed by a format adapter, not by a Solidity-aware one. Part II section
73.3.4 forbids any language-specific branch in the ingest path and a grep gate fails the build
if an adapter identifier, filename or conditional names a producer language. This source is
keyed by its format like every other.

## Consumer edge

Weak in the way that matters, and this section says so rather than working around it.

Delete this directory and one source disappears from whichever scenarios include it. Those
scenarios' bundle hashes change, so any gate pinned to a bundle hash goes red - but that is the
edge of removing any source at all, not an edge specific to this one. It would be dishonest to
count a hash change as evidence that the component is load-bearing.

The edge that is specific to this component is the intrinsic-ordering property. If a scenario
or a gate actually depends on having one source whose ordering is not granted by the harness -
for instance, a tampering or suppression study that needs a control case with a different
ordering provenance from every other source - then deleting this directory deletes that control
case and the study loses its comparison arm. If no scenario depends on it, then this component
is a source among sources, its only distinguishing property is unused, and it is padding.

Section 73.6's remedy for padding is deletion of the directory in the same commit that
discovers it, not a better rationale. Part II section 75.5.1 goes further and removes Solidity
from the target set outright unless a named, executing, mutation-proved job exists for it, and
states in the same sentence that duplicating the BLAKE3 chain does not qualify. So the question
this directory has to answer before any Solidity is written is: which committed scenario needs
the intrinsic-ordering control case, and which assertion in it fails without one?

That scenario has not been named. Until it is, this component's consumer edge is a claim rather
than a fact.

## How it is exercised

- CI job: `polyglot-d / chain-authz-solidity`, in the Tier D workflow. The component id is
  proposed; Part II section 73.6's transcript does not include a Solidity row.
- Tier: T2. Part II section 74.4 places Tier C/D language jobs and the polyglot mutation audit
  at T2, nightly on `main`. Section 73.9 makes a red Tier D job non-blocking for a milestone
  and blocking for a tagged release.
- Make target: `make chain-authz` builds the contract, runs the Foundry suite, starts the local
  node, applies the emission script and writes the event log. The mutation leg and the
  consumer-edge resolution run under `make polyglot-audit`.
- Toolchain: pinned Foundry, vendored. Part II section 74.1's four toolchain images do not list
  a Solidity toolchain by name; see "Not yet decided".

## Mutation check

Operator: `drop_records(p, seed)`, from the closed set in Part II section 73.5.

The corruption: a seeded fraction of the emitted authorization events is deleted from the log
after it is read back from the node and before it reaches the bundle. The remaining records are
well-formed, correctly ordered and individually valid. Only some of them are missing.

The gate that must go red: the scenario gate for whichever scenario includes this source -
proposed as `scenario/S4::chain_authz_ordering`, the assertion that this source's records
arrive as a contiguous sequence with no gap in the producer's own ordering. A drop breaks that
sequence, and because the ordering is intrinsic rather than harness-granted, the gap is
visible in the record contents themselves rather than only in the harness's bookkeeping. That
visibility is the entire point of the source class, so an undetected drop means the property
is not actually being checked.

This operator is chosen over `empty_output` on purpose. An empty log would fail almost any
gate, including gates that merely count records, and would prove nothing about whether the
ordering property is checked. A partial drop fails only a gate that looks at the ordering.

If the drop leaves every gate green, this component is padding under section 73.3.3 and the
directory is deleted.

## Not yet decided

- **The scenario that needs this source.** See "Consumer edge". No committed scenario has been
  named, and without one the component cannot pass section 73.3.1. This is the open question
  that decides whether the directory exists at all.
- **Whether Solidity survives the roster.** Part II section 73.1 lists it in Tier D. Part II
  section 75.5.1 removes Solidity, Verilog and VHDL from the target set unless a named,
  executing, mutation-proved job exists for each. The two sections are in the same part and are
  not reconciled; section 75.5's descope ladder rung D6 names only R, Julia and Octave as Tier
  D, which reads as though the other Tier D entries were not considered when the ladder was
  written.
- **Directory path.** `chain/authz-fixture/` is carried over from Part I section 31.27. Part II
  section 73 does not restate it and gives no component id for Solidity in its transcript. The
  path is therefore a working choice, not a specified one.
- **The Part I role must be actively retired, not just superseded.** Part I section 31.27
  describes this fixture as the control case in the tampering study, the one source where
  suppression is provably impossible, and Part I's demo beat contrasts blind windows on an
  audit source against zero possible blind windows here. Part II forbids the notary reading but
  does not say whether the tampering-study control case survives in some weaker form. Somebody
  reading Part I alone will rebuild the forbidden version; a retirement note is needed where
  Part I's text lives, not only here.
- **Toolchain image.** Foundry appears in none of section 74.1's four images by name. Either an
  image gains it or the component cannot run in CI.
- **The chain class of this source.** Part II section 61 distinguishes sources by whether
  deletion is chain-detectable and requires results to be reported per chain class and never
  pooled. This source's ordering is intrinsic, which suggests it belongs to a distinct chain
  class, but section 61's classes are not mapped onto section 73's source classes anywhere.
