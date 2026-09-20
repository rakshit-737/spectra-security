# Waiver ledger

Status: **zero waivers.** Nothing has been waived.

## What a waiver is

A gate in `ci/gates.toml` fails, and the failure is accepted rather than fixed. That is a waiver,
and it is recorded here or it did not happen.

The ledger exists because the alternative is silent erosion. A gate that can be quietly relaxed to
turn a milestone green is not a gate, and the pressure to relax one is highest exactly when the
gate is telling the truth. Writing the reason down in a file that a reviewer reads is the cheapest
available check on that pressure.

## What may never be waived

A gate whose `soundness` field is `true` in `ci/gates.toml` is **non-waivable**. There is no
process for waiving it, no expiry, and no appeal. A soundness gate failing means a claim this
repository makes is not supported, and the remedy is to stop making the claim.

`G-CLAIM-BANNED` is also non-waivable and has no allowlist.

## Record format

Each waiver is a section. Every field is required.

```markdown
### W-0001  <gate id>

date:       YYYY-MM-DD
gate:       <id from ci/gates.toml>
soundness:  false          # a waiver with soundness true is invalid and must be deleted
expires:    YYYY-MM-DD     # mandatory; a waiver with no expiry is not a waiver
requested:  <who>
reason:     <why the failure is accepted, not why it is inconvenient to fix>
scope:      <exactly what is exempted; never "this gate" in general>
revisit:    <what must become true for this to be removed>
```

An expired waiver fails the build. That is the point of the expiry: a waiver is a decision to defer,
and a deferral with no deadline is a decision to abandon.

## Relationship to the ratchet

`ratchet.json` records per-milestone gate counts, test counts and assertion counts, and CI fails if
any of them decreases. A decrease accompanied by a waiver entry here is permitted. A decrease
without one is not, and no judgement call is involved: the ratchet compares numbers.

## Records

None. This section stays empty until a gate exists, fails, and the failure is accepted.
