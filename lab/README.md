# The container range

Status: **not started.** No container exists.

## What this is, and what it is not

The range is a set of containers that emit telemetry SPECTRA reconstructs from. It is a source of
realism, not a source of truth.

Part II section 75 demotes it: the range is the FIRST rung on the descope ladder, D1, and if it is
demoted or cut, the bundles it produces may never be used in a published number, a gate, or the
paper. The normative telemetry source is the seeded synthetic generator, a pure function of
`(seed, scenario_id, degradation_spec)` and therefore reproducible. The range is not reproducible
in that sense and cannot be, which is exactly why no result may depend on it.

## Isolation

Every container runs on an internal Docker network with no egress. That is a security property of a
repository that models attacker behaviour, and it is asserted by a gate rather than by this
sentence. Until that gate runs, the isolation is a configuration intention and not a verified fact.

## What the range does not model

`docs/range/not-modeled.md` enumerates it, and is the only place in this repository where a claim
about the range's realism may be made. No document may describe the range as realistic,
enterprise-grade, or representative.

## Layout

| Path | Holds | State |
| --- | --- | --- |
| `services/` | One directory per container in the estate | absent |
| `scenarios/` | Scenario definitions the range replays | absent |
| `topology.hcl` | The estate topology, read by the range driver | absent |
