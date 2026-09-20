# Weaponization posture and the weaponization scan

> Status: authored in session one. `make weaponization-scan` is **not started**:
> it is declared and exits non-zero naming what is missing. No scan has been
> implemented, so no scan has been run, so this document reports no result. The
> statement below is a constraint on everything that will be written; it is not a
> report that anything has been checked.

## The statement

This text is normative and is required **verbatim** in three places.

> SPECTRA's scenario generators model attacker behavior **at the telemetry level
> only**. They emit synthetic log records describing what an attack would have
> looked like in an authentication log, a proxy log, an audit log or a process
> table. They contain no exploit, no payload, no shellcode, no credential-stealing
> code, no lateral-movement tooling, and no code that interacts with any system
> other than the local file it writes. Nothing in this repository can be
> repurposed to attack anything. The generators cannot compromise a host because
> they do not act on hosts; they write lines to a file.

| Required location | Present |
|---|---|
| `README.md`, first screen | not started |
| `SECURITY.md` | yes |
| `scenarios/README.md` | not started |

## What this means in practice

- A scenario generator's entire effect on the world is the bytes it writes to the
  run directory it was given. It opens no socket, spawns no process, and touches
  no host other than the one running it, and then only under that directory.
- SPECTRA does not execute, contain, store or analyze malware. No sample is
  downloaded, stored, detonated, or referenced by a hash intended for retrieval.
- SPECTRA does not attack any host it does not own. There is no external target,
  no scanning, and no network egress from any container in the scenario stack.
  There is no exploitation code path, and none is a stretch goal.
- A real CVE may appear in a provenance note as a bare citation explaining why a
  rule or a telemetry pattern is shaped the way it is. It may never appear
  alongside a code path that acts on it.

## What `make weaponization-scan` will check

The target fails the build on any hit. It is **not started**; the rows below are
the specification it must satisfy, not a description of behaviour that exists.
No row has ever run, so every result is "not measured".

| # | Check | Trees scanned | Implementation | Last result |
|---|---|---|---|---|
| W1 | Any network client call (`socket`, `requests`, `net/http`, `curl`, `Invoke-WebRequest`, or an equivalent in any language present) | `scenarios/`, `generators/` | not started | not measured |
| W2 | Any process-spawn primitive (`subprocess`, `os/exec`, `system`, `fork`, `Start-Process`, or an equivalent) | `scenarios/`, `generators/` | not started | not measured |
| W3 | Any embedded base64 or hex blob longer than the declared limit | `scenarios/`, `generators/` | not started | not measured |
| W4 | Any file write outside the declared run directory | `scenarios/`, `generators/` | not started | not measured |
| W5 | Any reference to a real CVE that is accompanied by a code path rather than being a bare citation in a provenance note | `scenarios/`, `generators/` | not started | not measured |
| W6 | Every allowlist entry carries a non-empty rationale | `scenarios/weaponization-allowlist.toml` | not started | not measured |

Open decisions the scan must close when it is implemented:

<!-- TODO(decision: blob-limit) W3's "declared limit" for an embedded base64 or
     hex blob has no value yet. Declare it once, in
     scenarios/weaponization-allowlist.toml or in the scan's own configuration,
     and reference it from this table rather than repeating it. -->
<!-- TODO(decision: scan-trees) The scan is specified over scenarios/ and
     generators/. If a third tree ever emits telemetry, add it in the same commit
     that creates the tree, and update this table. -->

## The allowlist

Exceptions live in `scenarios/weaponization-allowlist.toml` (**not started**).
Every entry carries a rationale, and the rationale is linted for non-emptiness by
the same target. An allowlist entry without a rationale is a scan failure, not a
warning.

An allowlist entry is an admission that the scan cannot express something, and it
is reviewed as such. It is not a way to keep a network call.

## Why this is enforced rather than asserted

A sentence in a README that says "contains no exploit code" is worth exactly as
much as the reader's trust in the author. A grep that fails the build is worth
what it checks. Until `make weaponization-scan` exists and runs in CI, this
document states an intention and a design constraint, and claims nothing about
what the repository has been proven to contain.
