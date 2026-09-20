# Why every target runs inside WSL2 or the devcontainer

Status: the requirement is real and enforced today. The tooling it describes is **not started.**

## The rule

Every `make` target in this repository refuses to run outside WSL2, a Linux host, the devcontainer,
or CI. The guard is three `$(error)` calls at the top of the Makefile, evaluated at parse time, so
an unsupported host fails before any goal is considered - including `make help`. Gate `G-WIN-001`
is that guard.

## Why it is enforced rather than recommended

SPECTRA's central claim is byte-identical reproduction: the same inputs produce the same certificate
hash on every machine. Several things differ between a Windows host and a Linux one in ways that
change bytes rather than merely change convenience.

**Line endings.** Git on Windows can materialise CRLF in the working tree. Any hash taken over file
bytes then differs from the same file on Linux. `.gitattributes` pins text files to LF and
`core.autocrlf` is asserted by gate `G-WIN-003`, but the host guard is the backstop.

**Path separators and case.** A forward-slash path and a backslash path are the same file to Windows
and different strings to a hash. Case-insensitive filesystems also let two distinct declared paths
collide silently; gate `G-WIN-005` is reserved for that check.

**Filesystem ordering.** Directory iteration order differs by filesystem. The determinism charter
(Part II section 58) bans relying on it, but a cross-platform difference turns a latent bug into a
reproduction failure that only one contributor can see.

**Toolchain availability.** The container range, the offline build and most of the Tier B, C and D
toolchains are Linux-only in this project's configuration.

## How to get there

The author develops on Windows 11. Either path is supported.

**WSL2.** Install a distribution, clone the repository inside the Linux filesystem - not under
`/mnt/c`, where I/O is slow and metadata behaves differently - and run `make` from there.

**The devcontainer.** `.devcontainer/devcontainer.json` describes the environment. It references a
builder image that is not yet built, so the devcontainer will not start until that image exists.

`make doctor` reports which toolchains are present and exits non-zero if a Tier A toolchain is
missing. It does not compare found versions against the pins in `.tool-versions`; that comparison
is unwritten, and `make doctor` says so rather than printing a comparison it cannot make.

## What is not settled here

Docker Desktop resource profiles are declared in the specification, Part II section 74.10, as
`core`, `matrix` and `range` tables, and those figures are tagged illustrative rather than required.
This document does not restate them, because nothing in the repository asserts them yet.
