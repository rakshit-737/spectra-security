<!--
STATUS: not started. None of the gates referenced below is implemented, so none
of the checkboxes can honestly be ticked on the strength of a CI run yet. Tick a
box only when you have run the named target and read its output. A ticked box
that nobody verified is worse than an unticked one, because it survives into the
history as evidence.

Delete nothing from this template. If a section does not apply, write "not
applicable" and one line saying why.
-->

## What this changes

<!-- One paragraph. What a reader of the diff would not work out on their own. -->

## Why

<!-- The spec section that requires it, or the defect it fixes. If this change
     is not required by a section and does not fix a defect, say so explicitly. -->

Spec sections touched:

## Gate ids

<!-- Section 74.0: a requirement with no gate id is not a requirement.
     List every gate in ci/gates.toml this change adds, removes, re-tiers,
     re-budgets or affects. "none" is an acceptable answer for a docs-only
     change; an empty section is not. -->

| Gate id | Added / removed / re-tiered / re-budgeted | Tier before | Tier after |
|---|---|---|---|
|  |  |  |  |

## Ratchet

<!-- Section 75.6. The ratchet makes weakening a test visible and expensive
     rather than invisible and free. -->

- [ ] `make ratchet-check` was run and its output is pasted below.
- [ ] No recorded count in `ratchet.json` decreased.
- [ ] No gate name disappeared from any milestone's `gates` list.
- [ ] If a count did decrease or a gate did disappear, a waiver entry exists in
      `ratchet.json` with a rationale over the length floor that names a descope
      rung **or** states explicitly "not a descope", and the matching
      `BUILD_LOG.md` DESCOPE entry is in **this same commit**.
- [ ] No recorded `counts` value was edited downward in place. Recorded values
      are append-only history; changes go through `waivers`.
- [ ] No assertion was added whose two sides are literals, or which calls nothing
      in the unit under test (`make assert-triviality-lint`).

```text
paste `make ratchet-check` output here
```

## Claims

<!-- Section 71. Every claim is registered, anchored and bound to an artifact. -->

- [ ] `make claims-check` was run and its output is pasted below.
- [ ] Every new sentence that asserts a capability, a result or a number has a
      `CLM-` anchor and a registry entry.
- [ ] Every numeral in a quantitative claim appears in the artifact that claim
      cites, and that artifact is committed -- not merely uploaded to the CI
      artifact store, which expires (74.7).
- [ ] No claim id was removed from the registry without a RETIRED record.
- [ ] No claim is backed by an artifact whose `claim_scope` is `SAMPLED`
      (`G-SAMP-001`). A T1 run is not "the full matrix", not "exhaustive", not
      "all configurations", not "every cell".
- [ ] No banned phrase, no score, no confidence, no severity, no percentage of
      risk, no dollar figure was introduced anywhere, including internal debug
      output.
- [ ] No CI-minute figure, image size or job duration was added to README or
      docs. Those come only from the T3 budget artifact with its run manifest
      hash (74.11.9).
- [ ] `LIMITATIONS.md` regenerates with no diff, and no numeral was hand-written
      outside a generated block.

```text
paste `make claims-check` output here
```

## Determinism

- [ ] No wall clock, hostname, user name, process id, absolute path or random
      value reaches an artifact.
- [ ] No verdict depends on elapsed time. A job may be killed by its timeout;
      no decision path may read one (74.9).
- [ ] Two consecutive runs produce byte-identical artifacts on this machine.

## Offline

- [ ] No CI step installs anything from the network. A tool a job needs went
      into a tier image and `images.lock` changed in this same pull request
      (74.11.1).
- [ ] Every image, `FROM`, devcontainer and `container:` reference resolves to a
      digest in `images.lock`. No tag, no `latest`, no floating range.
- [ ] Every action reference is pinned to a full commit SHA with the version in
      a trailing comment.
- [ ] If a lockfile changed, it changed via `make toolchain-refresh` and the
      regenerated `toolchains.lock` and `images.lock` are in this diff.

## Honesty of the CI surface

- [ ] No `continue-on-error`, no `retries:`, no `--rerun-failed`, no
      `|| true`, no rerun-to-green. Flakes fail the build (74.8.1).
- [ ] No gate was demoted to a faster tier, and no assertion was lowered, to fit
      a budget. If a budget did not fit, the gate was sampled, demoted to a
      **slower** tier, or the requirement was deleted -- visibly, in
      `ci/gates.toml` (74.9, 74.11.3).
- [ ] No `if: false` guard was added to a job that has ever run and failed. A
      guard exists only on a job whose gate is not written yet, and it names the
      milestone that deletes it.
- [ ] No skipped job was added to the branch-protection required-check list.
- [ ] No quarantine row was added for a gate marked `soundness = true`; those
      cannot be quarantined at all (74.8.6).
- [ ] Every quarantine row in `ci/quarantine.toml` is within its expiry, and none
      is a second renewal of the same test id.

## Status claims

- [ ] Nothing in this diff describes an unimplemented thing in the present
      tense.
- [ ] Every status marker this diff adds reads "not started" unless the diff is
      the thing being delivered.
- [ ] Every unimplemented target this diff adds prints what is missing and exits
      non-zero. Nothing exits 0 having done nothing.
- [ ] No result, count, duration or rate appears anywhere in this diff without
      the committed artifact it came from, or the words "not measured".

## Which tiers were run locally

<!-- Name the targets you actually ran and paste the exit codes. "CI will tell
     us" is not an answer; CI is where a green result is confirmed, not where it
     is discovered. -->

```text
```
