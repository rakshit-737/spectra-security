# Security Policy

> Status of this document: authored in session one, before any SPECTRA code
> exists. Every enforcement mechanism named below is **not started**: the make
> target is declared and exits non-zero with a message naming what is missing.
> This file states policy. It reports no measurement and makes no claim that a
> control is in place.

## What SPECTRA is, for the purposes of this policy

SPECTRA is a local-first, offline research artifact. It is not a product. It is
not deployed. There is no hosted instance, no SaaS, no demo server on the public
internet, and no multi-tenancy. It is single-user and local-only, and it accepts
no network input at runtime. See `docs/NON-GOALS.md` items 14, 15 and 16 (that
file is not started).

There is therefore no production service to compromise, and no user data held by
anyone but the person running the repository on their own machine.

## Scope

The security-relevant attack surface is:

1. the ingest parser, which processes untrusted telemetry files;
2. `spectra verify`, which processes untrusted certificates;
3. the archive and decompression paths used by both.

### Parser hardening is a security boundary

SPECTRA processes **untrusted telemetry**. A bundle handed to `spectra ingest`
is attacker-influenced input by assumption: it may be malformed, truncated,
adversarially nested, adversarially large, encoding-hostile, or crafted to drive
the parser into pathological behaviour. A certificate handed to `spectra verify`
is likewise untrusted input, because the whole point of an independent checker is
that it does not trust the producer of the artifact it is checking.

Parser hardening in SPECTRA is a boundary in two distinct senses, and both are
in scope for a report:

- **Memory and resource safety.** Crashes, unbounded allocation, unbounded
  recursion, decompression amplification, and any path that lets an input file
  determine resource consumption without a declared limit.
- **Correctness.** A record that is dropped without being quarantined and
  counted is a security defect, not a cosmetic one. A silent drop manufactures a
  blind window; a blind window manufactures a license for an unobserved attacker
  step; a license changes a verdict. A parser that loses input quietly corrupts
  the proof that the rest of the system exists to produce.

The declared parser limits and quarantine reason codes live in the ingest
specification. They are **not implemented**, so this document cannot and does not
state what the limits are or that they hold.

## Reporting

Report through the repository's private vulnerability reporting channel on its
hosting platform, or, if that is unavailable, open an issue on the repository
issue tracker **only if the report contains nothing sensitive**.

<!-- TODO(decision: security-contact) The contact is the repository issue
     tracker plus platform private advisories, chosen because this repository has
     no deployed service and no security team. If a dedicated address is ever
     created, replace the two sentences above with it and update
     CODE_OF_CONDUCT.md, which points at the same tracker. -->

A useful report contains:

- the input file that triggers the issue, or the smallest reduction of it you can
  produce;
- the commit SHA you observed it on;
- the exact command and its real output.

What you should expect:

- **Acknowledgement target: 14 days.** This is a stated intention of a
  one-person research repository, not a service-level agreement, and no
  measurement of past response time is claimed.
  <!-- TODO(decision: ack-window) 14 days was chosen as the obvious conservative
       value for a single maintainer. Change the number here and nowhere else. -->
- **No bug bounty.** None is offered, none is planned, and no payment will be
  made for any report.
- **No SLA and no embargo negotiation.** Fixes land when they land, in public.
- No security team exists. This policy says so rather than implying one.

## Explicitly out of scope

- Findings in the container scenario stack, which is non-normative, offline,
  egress-blocked, and never exposed.
- "Missing authentication" on the local API. SPECTRA is single-user, local-only,
  and binds to loopback. See `docs/NON-GOALS.md` item 16.
- Denial of service by supplying an enormous bundle. Parser limits are declared
  in the ingest specification; exceeding a declared limit is a documented
  quarantine, not a bug. (A resource blow-up *below* a declared limit, or on a
  path with no declared limit, is in scope.)
- Anything that requires the reporter to already have code execution as the user
  running SPECTRA.

## Handling of telemetry

SPECTRA processes only telemetry you supply. It transmits nothing, phones home
never, performs no update check, contacts no license server, and writes only
under the run directory you name.

## No weaponizable code

> SPECTRA's scenario generators model attacker behavior **at the telemetry level
> only**. They emit synthetic log records describing what an attack would have
> looked like in an authentication log, a proxy log, an audit log or a process
> table. They contain no exploit, no payload, no shellcode, no credential-stealing
> code, no lateral-movement tooling, and no code that interacts with any system
> other than the local file it writes. Nothing in this repository can be
> repurposed to attack anything. The generators cannot compromise a host because
> they do not act on hosts; they write lines to a file.

This statement is required verbatim in three places. Present state:

| Location | Present |
|---|---|
| `SECURITY.md` (this file) | yes |
| `README.md`, first screen | not started |
| `scenarios/README.md` | not started |

The statement is enforced rather than merely asserted by `make
weaponization-scan`. That target is **not started**: it is declared and exits
non-zero naming what is missing. What it will check, and the allowlist that
governs its exceptions, are specified in `docs/WEAPONIZATION.md`.

## Name collision

ECLIPSE here is an internal acronym for this project's proof kernel
(Evidence-Licensed Cut Proofs over Silent Envelopes). It is unrelated to the
Eclipse Foundation, the Eclipse IDE, Eclipse Temurin or Eclipse Adoptium, and
uses none of their marks.
