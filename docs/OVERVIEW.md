# SPECTRA: what it computes, and how much of it exists

Audience: an engineer who has found this repository and has not read the specification.
This document explains what the working code does, in order, and ends with the one worked
example the repository actually runs. Companion: [READING-A-CERTIFICATE.md](READING-A-CERTIFICATE.md),
a field-by-field guide to the output file.

## What exists, before anything else

Read this first, because most of the specification is not built.

- **What exists**: a Python reference implementation of an eleven-stage pipeline
  (`python/spectra_vs/`), a separate Python package that re-checks its output
  (`python/spectra_vs_verify/`), a seeded synthetic telemetry generator, and the run
  artifacts under `runs/`.
- **What does not exist**: the Rust kernel, the Go checker, and the Docker range with its
  services. None of them has been built or run, and no statement anywhere in this document
  rests on any of them. ADR-0013 records why: the machine has no Rust and no Go toolchain.
- **Nothing in the result path is a service.** There is no HTTP API. The pipeline and the
  checker are file-in, file-out: no network, no DNS, no database access and no subprocess
  execution reaches a certificate, and every artifact quoted below is a file under `runs/`.
  Anything in the tree that indexes or displays those files afterwards is a reader over
  them and produces no result of its own.
- **The telemetry is generated.** It is the output of a seeded synthetic emitter, and the
  attack inside it is simulated. Every certificate says so in its own bytes, under
  `inputs.bundle_provenance: "synthetic_generator_no_range"`. Nothing here is evidence
  about a real system, a real sensor or a real attacker.
- **The checker is not independent.** `spectra_vs_verify` imports nothing from
  `spectra_vs`, and a gate enforces that. But both are Python, both were written by one
  author from one reading of one specification, and both share `spectra_core` for the
  octet encoders and the digest. That is module independence. A misreading of a rule or a
  guard shared by both sides is invisible to the check, and the checker says so in its own
  report. No certificate in this repository has been independently verified.
- **The digest is substituted, and says so.** The specification names blake3. The standard
  library has no blake3 and no package may be installed here, so every digest is
  blake2b-256, labelled `b2b256:` rather than `blake3:`, and each certificate carries
  `schema.hash_algorithm` and `schema.hash_substitution_note` declaring the substitution.
  A digest here is not comparable with a specified one.
- **No number in this repository is a measurement.** The slice publishes no benchmarks, no
  timings, no throughput and no accuracy figures. The counts quoted below are properties of
  one run over one seeded scenario.

## The problem

Telemetry has gaps. A sensor is down for ten minutes; a source loses records; a log stream
was never wired up at all. Reasoning over the records that survived gives you one answer.
Reasoning over the records that might have existed gives you another. Most tooling picks
one silently.

That silence matters most when the output is a list of controls. Suppose an analysis says
"raise `priv_approval`". There are two very different reasons it could say that:

1. Somebody assumed a privileged role without approval, it was recorded, and the control
   blocks that step.
2. Nobody assumed anything that anyone saw - but for ten minutes the identity audit log
   emitted nothing, so an escalation in that window is consistent with every record that
   exists, and the control blocks that hypothetical step.

Those are not the same finding. The first is about what happened. The second is about what
you could not see. A system that reports them with the same word is telling you less than
it knows.

SPECTRA's slice exists to keep the two apart, and to make the second one explicit, named
and re-checkable rather than an assumption buried inside a heuristic.

## The two programs

The pipeline builds two logic programs over the same rule table and the same telemetry.

**P_min is what the records support.** Stage S8 seeds a fact base from the bundle's records
(mapped through entity resolution), then runs a semi-naive fixpoint with provenance. Every
rule instance it produces is marked `OBSERVED` and cites the event ids that made it fire.
Nothing in P_min rests on anything unseen.

**P_max is P_min plus steps that could have happened unseen.** Stage S9 adds, to a copy of
P_min, the rule instances that could have fired in a window where nobody could have seen
them. Each such instance is marked `LICENSED`, cites no evidence, and cites one or more
**licences**.

A licence is the unit that makes this auditable. It is a record of the form

```json
{
 "basis": "SUPPRESSED",
 "license_id": "lic:c2de54bf5f92f9c09ce7ea79e356bbcb183d94a2a8274d52f83339a69b1f05f1",
 "reason": "S_CHAIN_SEQ_GAP",
 "source_id": "src:iam_audit",
 "t0_ns": "1707008999699266491",
 "t1_ns": "1707009601892237041",
 "witness": ["ev:967c4690c8e150de45027bf18e65784d", "ev:9d31c46b7e529fb15b9ecab688d76522"]
}
```

taken verbatim from `runs/vs-02830d35a09ad406/cert.spcert`. It names one source, one
interval, and a reason code for why that source could not be believed to be live there. A
licence is a permission for an unobserved step. **It is never an observation**, and the
emitter and the checker both refuse a `BLIND` licence that carries a witness, on exactly
that ground.

Where do licences come from? Only from stage S7, liveness, and never from the bundle under
analysis. S7 compares each source's observed inter-record gaps against a threshold taken
from a **calibration profile** - built by a separate run, at full completeness, under a seed
from a band disjoint from the analysis band. Six binding gates (B1 to B6) refuse a profile
that was calibrated on this same bundle, on a degraded run, under an overlapping seed, or
against a different scenario family or generator configuration. Without that separation the
liveness stage would set its own thresholds from the data it is judging, and the result
would be circular. The classification ladder is fail-closed: eleven rules, first match wins,
and `LIVE` is constructed at exactly one site at the bottom of the ladder, reached only when
every other rule declined.

Two kinds of unobserved step live in P_max, and they are not the same:

- A **licensed silent instance**: the rules say this step *might* have happened, in a window
  where nobody could have seen it.
- A **GHOST**: an unsatisfied obligation forces a head fact, so the rules say this step
  *must* have happened, and it was not seen. A GHOST is not an event. It never enters
  `observed_event_count`, any evidence count, or any timeline rendered as observed.

When an obligation is unsatisfied and *no* licence covers it, no GHOST is created at all.
The stage writes a `permanent_blind_spot` entry instead, which is the honest admission that
the step is invisible rather than a tidy inferred node.

P_min is always a subset of P_max, they are separate files, and nothing mutates P_min in
place. Running the whole cut machinery over both is the two-sided bracket. It is not a
confidence interval and must never be rendered as one.

## The cut

A **control catalog** declares controls and levels. Each `(control_id, level)` pair is an
atom and gets a bit from `config/vs/catalog-bits.lock`, an append-only registry: a pair
keeps its bit forever, removal writes a tombstone, and the bit is never reused. In the
demonstration scenario there are five controls and nine atoms.

Each rule instance carries **blockers**: the control atoms that stop it from firing. Given
a set of raised controls, reachability is a linear unit-propagation fixpoint (Dowling and
Gallier) over the bipartite AND/OR provenance graph: facts are OR nodes, instances are AND
nodes, and an instance fires when every body fact is derived and no blocker is satisfied by
the cut.

A **corridor** is a clause: the set of control atoms that appear in some derivation of the
goal. Enumerating corridors and searching for a set of raised controls that satisfies all
of them is the hitting-set loop. The result is the **cut**: which controls, at which levels,
make the attacker's goal underivable in the program the search ran over.

Three things about the cut are worth knowing before you read one:

- **Cardinality is counted in raised controls, never in atoms.** A cut is upward-closed:
  raising a control to level 2 puts its level-1 and level-2 atoms in the mask. Two atoms of
  one control are one raised control.
- **Level-minimality is a hard requirement.** For every control raised above level 1,
  lowering it one step must leave some clause unsatisfied. The checker re-verifies this
  clause by clause.
- **What may be claimed about size is a separate field from what may be claimed about
  safety**, and neither downgrades the other. `EXACT_PSI_RELATIVE` renders as "no smaller
  cut satisfies the enumerated corridor set". `SUBSET` renders as "no control can be removed
  from this cut; smaller cuts were not ruled out". `UNVERIFIED` claims nothing. The phrase
  `minimum cut` is on the banned list with no allowlist, because minimality here is
  relative to the declared catalog and to the corridors that were actually enumerated.

## The blindness premium

Run the cut search over P_min and you get the controls the records demand. Run it over
P_max and you get the controls the records demand *plus* the controls that only a
could-have-happened step demands. The blindness premium is the second set minus the first.

It is deliberately **not** the set difference of the two chosen cuts. Two cut searches each
pick one canonical representative out of possibly many cuts of the same size, and
subtracting two representatives tells you about the tie-break, not about the problem. The
premium is defined over the corridor databases instead, by the *values* of optimisation
problems:

- `NEC(Psi)` is the set of controls whose removal from the universe makes every satisfying
  set strictly larger (or infeasible): the controls in every cut of the smallest size.
- `OCC(Psi)` is the set of controls that appear in at least one cut of the smallest size.
- The premium `B = NEC(Psi_max) \ OCC(Psi_min)`.

Because both sides are values rather than arguments-of-the-minimum, `B` is invariant to
solver order, branch order and insertion order.

The set difference of the two canonical representatives still exists in the certificate,
under the name `cut_delta_canonical`, and carries the literal caption "difference between
two canonical representatives; not the blindness premium". The two are never rendered
together.

One more distinction the premium keeps. A licence can rest on an **observed gap** (the
sensor was there and a gap exceeded its calibrated threshold) or on a **calibration
deficiency** (this run never had a usable profile for that source). Every premium control
therefore carries `calibration_deficiency` as an exact rational. A control resting on
missing calibration may not be described as resting on a sensor gap; the correct phrasing
is "needed because this run was not calibrated for this source".

The premium is published only when both corridor databases reached fixpoint, no cap fired
and no deterministic budget was exhausted. When any precondition fails, the whole `premium`
member is **absent from the hashed bytes** - not null, not `[]`, not `0`, not `"N/A"` - and
a `premium_suppressed_reason` from a closed set appears in its place.

## The certificate

The prove stage writes one file, `runs/<id>/cert.spcert`. It is the whole result: the
scope, the pinned input digests, the verdict, the atom table, the cut, the corridor
database, the published instance set, the licences, the silent instances, the witness trees,
the premium, the residual, the deterministic step counters and two separate event counts.
It carries no wall-clock time, no hostname, no username, no path, no process id and no
duration, so two runs of the same inputs produce the same bytes.

A separate program re-derives it:

```
python -m spectra_vs_verify runs/<id>/cert.spcert \
  --rules --rules-cae --guards --controls-cae --catalog-bits \
  --bundle --liveness --profile --goal-cae --er --run-manifest
```

It is pure file-in, file-out: no network, no database, no subprocess, and it writes nothing
unless `--out` is given. It never sorts, never repairs, never defaults and never infers; any
deviation from canonical form is a rejection with a reason code. There is no `--force`, no
`--skip` and no `--ignore-hash-mismatch`. Exit 0 is ACCEPT, 1 is REJECT, 2 is a usage error,
and an option not supplied is a usage error rather than a skipped obligation - a digest
nobody recomputed is a digest nobody checked.

It runs sixteen obligations in a fixed order, stopping at the first failure: canonical
re-serialisation, the certificate digest, the schema and member set, the scope binding, the
input digests, the profile gates B1 to B6, the atom table, the cut and its level-minimality,
the closure invariant, closure under every published instance, goal membership, licence
implication against the pinned liveness document, the two event counts, the witness trees,
the temporal dispute rule, the corridor-hitting test, the flag algebra and the minimality
claim. O0 through O14 are linear in the certificate; O15 searches the control lattice and is
fenced in the report with its own cost line.

**What ACCEPT means**, in the checker's own words: the certificate is internally consistent
with the inputs it pins.

**What ACCEPT does not mean**: it says nothing about whether the bundle is truthful, whether
entity resolution was correct, whether the control catalog is complete, whether grounding
found every instance, or whether the certificate was independently verified. It is not a
statement about a real system, and it is not a claim that any attack was stopped. The only
supported phrasing for what a cut does is "severs this chain in the model" or "the goal is
underivable under this cut".

## The worked example: the pre-registered blackout cell

This is the one result the repository runs, and it was registered before it was built.
[`docs/research/prereg-0001-blackout-cell.md`](research/prereg-0001-blackout-cell.md) fixes
the intervention and the predictions; `git log` on that file lists one commit, and every
commit that implements the intervention has it as an ancestor.
[`docs/research/prereg-0001-result.md`](research/prereg-0001-result.md) records the outcome,
because the registration says nothing in it may change after the run.

### The design

One scenario family, `vs-01-token-pivot`, seeded, with two routes to one goal. Route A is
the observed attack: a token taken on an endpoint with no sensor, a refresh at the identity
provider, a gateway call with the replayed token, a bulk resource read. Route B is an
escalation path: an admin role assumed with no preceding approval, then an export that
bypasses the egress path. Five controls, nine atoms, six sources - one of which,
`edr_host`, is declared and emits zero records, so it is blind everywhere by construction.

The intervention is `WHOLE_SOURCE_BLACKOUT`: delete every record emitted by `src:iam_audit`
within `[epoch + 4200 s, epoch + 4800 s)` and nothing else. The window was chosen from the
scenario definition, not from any run output: the scenario puts the approval record and the
escalation step inside it. Every other source and every other parameter is unchanged from
the full-telemetry cell.

### The predictions, fixed in advance

| Quantity | Full telemetry | Blackout cell, predicted |
| --- | --- | --- |
| `\|Psi_min\|` | 1 | 1 - route A, unaffected |
| `\|Psi_max\|` | 1 | 2 - route A, plus route B through a licensed escalation |
| blindness premium | EMPTY | `{ctl:priv_approval}` |

Four falsifiers were named in the registration: an empty premium; a premium containing any
other control; `|Psi_min|` other than 1; `|Psi_max|` other than 2. The result record
evaluates five, splitting the first into "the premium is published" and "the premium is
non-empty", because a suppressed premium and an empty one are different outcomes.

### What came out

The control arm is `runs/vs-0049b1adfb705cb3`, the blackout cell `runs/vs-02830d35a09ad406`.
Both certificates are in the tree. All five recorded falsifiers passed.

The blackout removed 601 of 21577 simulated records, all from `src:iam_audit` inside the
window. Liveness classified the resulting sequence gap on that chained source as
`SUPPRESSED`, reason `S_CHAIN_SEQ_GAP`, over the ten minutes between the last record before
the window and the first record after it, bracketed by those two record ids - the licence
quoted earlier in this document. P_max grew from 85 instances to 130.

The corridor database over the upper program, straight out of the blackout cell's
certificate:

```json
"psi":{"complete":true,"corridors":[
  {"atom_ranks":[0,4,5,7],"corridor_id":"cor:c79d71a6...","mask":"0x00000000000000b1"},
  {"atom_ranks":[2],"corridor_id":"cor:e87ac903...","mask":"0x0000000000000004"}],
 "program":"PMax"}
```

Two corridors where the control arm has one. Rank 0, 4, 5 and 7 are
`ctl:egress_seg` level 1, `ctl:rate_limit` level 1, `ctl:session_binding` level 1 and
`ctl:token_expiry` level 1 - route A. Rank 2 alone is `ctl:priv_approval` level 1 - route B,
a singleton corridor.

The cut over the upper program raises two controls where the control arm raises one:

```json
"cut":[{"bit":0,"control_id":"ctl:egress_seg","level":1,"rank":0},
       {"bit":2,"control_id":"ctl:priv_approval","level":1,"rank":2}]
```

And the premium:

```json
"premium":{"blindness_premium":["ctl:priv_approval"],
           "nec_max":["ctl:priv_approval"],
           "occ_min":["ctl:egress_seg","ctl:rate_limit","ctl:session_binding","ctl:token_expiry"],
           "per_control":[{"calibration_deficiency":{"den":1,"num":0},
                           "control_id":"ctl:priv_approval",
                           "license_ids":["lic:2662aec5...","lic:4497caad...","lic:c2de54bf..."]}]}
```

In the control arm the same member reads `"blindness_premium":[]` with an empty `nec_max`.
That empty result is the control arm and it has to be shown, or the non-empty result proves
nothing.

`calibration_deficiency` is `0/1`, so `ctl:priv_approval` rests on observed-gap licences
here, not on a source this run had no calibration for.

That one line is the whole idea: **`ctl:priv_approval` is in the upper cut not because
anyone saw an escalation, but because for the length of a blind window nobody could have.**

### The witness

The certificate carries, for each control in the cut, the derivation that comes back when
that one control is removed. The tree behind `ctl:priv_approval` has three nodes:

```json
[{"children":[1],"evidence":["ev:22ae6b8683cebeba2efac8d84e211ce6"],"kind":"OBSERVED",...},
 {"children":[2],"evidence":[],"kind":"LICENSED",...},
 {"children":[],"evidence":[],"kind":"GHOST",...}]
```

Read it downward: an observed export, derived through a **licensed** privilege escalation -
a step the rules say might have happened where nobody could see - which in turn rests on a
**GHOST** premise, a step an obligation forces. Only the root cites a record. This is the
tree ADR-0015 exists to make publishable; before that change the certificate could carry no
witness at all for this cell, and the result record says so.

A witness drawn from P_max may combine silent steps that no single consistent world
realizes. Such a tree may depict an attack that could not have happened. That caveat is part
of the design, not an apology for it.

### The verdict

The blackout cell's certificate publishes the strongest of the four safety values, with
`minimality: "EXACT_PSI_RELATIVE"` and no flags set. A safety token is never written alone;
assembled from that certificate's own `scope` member by the single renderer in `cert.py`,
the short rendering reads:

```
ROBUST(rules@b2b256:af378c79, controls@b2b256:ded86bbf, liveness@b2b256:15f0694a,
       er@b2b256:f94edd2e, goal@b2b256:aec2d790, bundle@b2b256:419ff4f1,
       non-adaptive) [EXACT_PSI_RELATIVE]
```

and every long rendering ends with the sentence "This is a statement about the model, not
about the system."

Proving the same bundle with the *lower* cut instead gives the optimistic-only verdict: it
severs the goal in P_min and does not sever it in P_max. Two verdicts, one bundle, one
difference - what you could see.

### What the result record says it is not

The result record is blunter about this than a summary can be, and it is worth reading in
full. In short: it is one scenario, one seed and one window of simulated telemetry, so it is
a data point and not a measurement. The author wrote the prediction immediately after
tracing this exact mechanism while fixing an unrelated defect, so it tests whether the code
matches the author's understanding, not whether that understanding is right. And one
confound named in the registration - a tamper flag blocking the strongest verdict - could
not fire at the time, because the check it depends on did not exist. "No flag was set" was
the absence of a check, not a finding.

That gap has since been closed, by ADR-0016 and ADR-0017, and tested under a second
registration.

## The three most recent contract changes

- **[ADR-0015](adr/0015-witness-trees-are-published-flat.md)** (accepted 2026-09-21).
  Witness trees are published flat: `witnesses[i].nodes` is a pre-order node list and
  `children` holds indices, so a witness of any length reaches seven nested containers and
  no more. It also adds a third node kind, `LICENSED`, for a licensed silent step that no
  obligation forces. Before this, the depth cap admitted a root and one level of children,
  and the demonstration's certificates carried no witness at all. Schema and checker moved
  from 1.0 to 1.1 in the same commit. Publishing a licensed step as a GHOST was considered
  and rejected: a GHOST is a step the rules say must have happened, a licensed step is one
  they say might have.

- **[ADR-0016](adr/0016-the-slice-implements-the-temporal-dispute-pass.md)** (2026-09-23).
  The slice implements the temporal-consistency pass, as Part II's **dispute protocol** and
  never as Part I's voiding pass. The reason is an attack on SPECTRA itself: voiding a
  licence shrinks P_max, a smaller P_max can only move a verdict toward the strongest one,
  so an adversary who can rewrite timestamps could buy that verdict by tampering. Under the
  dispute protocol a suspected licence is **retained in P_max with full force** and the
  verdict is weakened instead. Flag bit 5 stays permanently false, because nothing is ever
  voided. What the pass finds is one thing: a recorded timestamp that contradicts the order
  its own source recorded, or a declared temporal bound. A consistently rewritten source, a
  forged chain, and suppression on a source with no sequence number are all invisible to it.

- **[ADR-0017](adr/0017-the-tamper-counterfactual-is-computed-in-the-prove-stage.md)**
  (2026-09-23). Corrects ADR-0016 point 5 only. The counterfactual verdict cannot be written
  into `liveness.json`, because that file is hashed and pinned by stage S7 and the verdict
  is an artifact of S10; writing it there needs either a rewrite after the pin or a circular
  dependency. The comparison moves to the prove stage. `liveness.json` carries what S7
  knows - the disputed events, `tamper_suspected` per source, and `mcs_greedy` - and the
  checker keeps reading `verdict_tamper_sensitive` from the pinned document, because an
  obligation that stops checking a field is how a field becomes unchecked.

Pre-registration 0002 exercises that pass against a backdated record, and its result record
is at [`docs/research/prereg-0002-result.md`](research/prereg-0002-result.md).

## What this does not do

- It does not detect attacks, and it is not a detector. It is a post-hoc reconstruction over
  a finished, recorded bundle. Nothing streams.
- It does not say an attack was prevented, or would have been prevented. It says a goal atom
  is underivable under a cut, in a model built from a hand-authored rule table and a
  hand-authored control catalog.
- It does not detect suppression, tampering, backdating or log deletion in general. Since
  ADR-0016 it finds exactly one thing, described above, and a blind window is represented as
  blind volume rather than as a finding.
- It does not emit a probability, a confidence, a likelihood, a risk figure, a severity, a
  ranking or any normalisation to [0,1]. Residual reachability is a set, never a number, and
  two residuals that do not contain one another are reported as incomparable.
- It does not verify the bundle. Entity resolution is exact string joins only, with no fuzzy
  matching; an ambiguous join raises a soundness flag rather than picking a winner.
- It does not model an adaptive attacker. Every scope says `attacker: "non-adaptive"`, and
  that is the only value the checker accepts.
- It does not model a step that only fails when two controls are both raised. The slice
  narrows every blocker term to a single control atom, and the compiler rejects a
  conjunctive term.
- It does not check two of the four realizability conditions. The certificates in `runs/`
  carry `realizability: "UNCHECKED"`.
- It has not been evaluated. There is no degradation matrix, no baseline comparison, no
  scenario pool and no repeated-seed study. Two completeness cells and two pre-registered
  interventions were run.

## Where to read next

| You want | Read |
| --- | --- |
| a field-by-field guide to the output | [READING-A-CERTIFICATE.md](READING-A-CERTIFICATE.md) |
| the contract the code is built against | [kernel/slice-spec.md](kernel/slice-spec.md) |
| the worked example, registered and resolved | [research/prereg-0001-blackout-cell.md](research/prereg-0001-blackout-cell.md), [research/prereg-0001-result.md](research/prereg-0001-result.md) |
| the three most recent contract changes | [adr/](adr/) 0015, 0016, 0017 |
| the phrases this project may not use | [../CLAIMS.md](../CLAIMS.md) |
| what is known to be missing | [../LIMITATIONS.md](../LIMITATIONS.md) |
