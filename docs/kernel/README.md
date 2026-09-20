# Proof kernel documentation

Status: **not started.** No kernel code exists.

This directory is named `kernel/` rather than after the kernel's internal acronym because Part II
section 73.10 bans that string from every directory, crate, module and file name in the repository.
ADR-0004 records the decision and the reason: a collision with a very well known foundation and
toolchain. The acronym appears in prose only, bound on first use.

## What will live here

| Document | Covers | Milestone |
| --- | --- | --- |
| `spec.md` | The kernel's stages, its data structures and its complexity bounds | M4 |
| `certificate.md` | The certificate format, its canonical serialisation, and what each hash covers | M5 |
| `checker.md` | The independent checker's obligations, and the precise scope of its independence | M6 |
| `claims.md` | What the kernel is forbidden from claiming, in one place | M5 |

Until those exist, the authoritative text is the specification: Part I sections 22-25 and Part II
sections 63 through 68. Part II overrides Part I.

## The one thing worth knowing before reading any of it

The kernel proves properties of a model - a hand-written rule table, an entity resolution pass, a
declared control catalog, and the telemetry actually ingested. It proves nothing about any real
system, and the attacker it reasons about does not re-plan against the cut it finds. Every document
in this directory carries that scope or it is a defect.
