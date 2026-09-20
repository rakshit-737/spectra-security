# ADR-0002: Apache-2.0 as the single licence

## Status

Accepted — 2026-09-20

## Context

The specification fixes the licence in one line — Part I section 1.5, "License: Apache-2.0" — and
Part II section 75 adds that there is a single licence, with no dual-licensing and no
non-commercial rider. `spectra.toml` already records `license_spdx = "Apache-2.0"`.

That is a requirement, not a reason. This record exists because the reasons are not obvious and
because the default in this neighbourhood points the other way: a solo security-research repository
with a public GitHub page is, nine times out of ten, MIT. MIT is shorter, universally recognised,
and nobody argues about it. Choosing the longer licence needs an argument, and the argument needs to
survive a reviewer asking "why did you not just use MIT?".

Four forces shape the choice here.

**The subject matter is security technique, not just code.** SPECTRA's contribution is a method —
modelling missing telemetry as an explicit licence for unobserved steps, and producing a
content-addressed certificate an independent checker can re-validate. Methods in this area are
patentable, and have been patented. MIT and BSD-3 are silent on patents: a contributor can
contribute code and separately hold a patent that reads on it, and a downstream user has no express
grant. The silence is not a grant and it is not a denial, which is the problem — it leaves the
question open for everyone downstream.

**The intended audience includes people whose employer has a licence policy.** Part I section 1.6
names security engineers and reviewers as the first two audiences. Corporate review of an
Apache-2.0 dependency is routine and largely mechanical. Corporate review of a permissive licence
with no patent clause is also routine, but it produces a different conversation, and for
security-adjacent tooling it is a conversation that sometimes ends in "no".

**There is no CLA and there will not be one.** A single maintainer cannot administer a contributor
licence agreement, and `CONTRIBUTING.md` is required to state that the repository accepts issues
while the milestone plan stays fixed. Apache-2.0 section 5 supplies inbound-equals-outbound terms in
the licence text itself, which is the only mechanism available here that does not require
administrative machinery nobody will run.

**The project has a name collision and no trademark position.** ADR-0004 records that the proof
kernel's internal acronym collides totally with the Eclipse Foundation's marks, and non-goal 19
requires the repository to disclaim any relationship. Apache-2.0 section 6 says in the licence text
that no trademark rights are granted. MIT does not address trademarks at all. Having the disclaimer
appear in the licence as well as in `docs/naming.md` costs nothing and removes one way to be
misread.

Against all of that: Apache-2.0 is longer, imposes a redistribution obligation MIT does not, and is
not compatible with GPLv2. Those are real and are recorded below rather than argued away.

## Decision

The repository is licensed under **Apache License, Version 2.0**, and under that licence only.

1. `LICENSE` at the repository root contains the unmodified Apache-2.0 text. It is not edited, not
   abridged, and not annotated.
2. Every source file in every language carries an `SPDX-License-Identifier: Apache-2.0` header in
   that language's comment syntax, to be enforced by a header lint (`make license-header-lint` in
   the specification's make-target surface). Generated files carry it too; vendored third-party
   files keep their own headers untouched.
3. `NOTICE` exists at the repository root and is deliberately minimal: the project name, the
   copyright line, and nothing else. No description, no tagline, no claim, no URL that can rot.
4. There is **no** dual-licensing, **no** commercial exception, **no** non-commercial rider and
   **no** "free for research" clause. Part II section 75 forbids them and this record does not
   reopen the question.
5. Because the build vendors its dependencies for offline use, third-party licence texts and any
   third-party `NOTICE` content are aggregated under a dedicated third-party directory, and the
   aggregation is regenerated rather than hand-maintained. The mechanism is not chosen here; the
   obligation is recorded so that vendoring cannot quietly create an unmet one.
6. Fixtures and generated corpora additionally carry the synthetic-data marker required by Part I
   section 2, so that a redistributed bundle cannot be mistaken for observed telemetry. That marker
   is a data-provenance statement and is independent of the licence.

## Consequences

**Downstream users get an express patent grant.** Apache-2.0 section 3 grants a patent licence from
every contributor covering their contribution, and terminates that grant for anyone who initiates
patent litigation alleging the work infringes. For security tooling that may be redistributed inside
a larger product, that clause is the substantive difference from MIT, and it is the reason this
record exists.

**Redistribution now carries an obligation.** Apache-2.0 section 4 requires a redistributor to
include the licence, to state changes made, to preserve attribution notices, and — section 4(d) — to
include the contents of the `NOTICE` file in their own distribution. That last one propagates
forever and cannot be trimmed by anyone downstream. This is exactly why the `NOTICE` file is kept to
a copyright line: every sentence added to it becomes a sentence every downstream redistributor is
obliged to carry. `NOTICE` is not a place for a project description and must never become one.

**Header lint becomes a real cost across an unusual language surface.** The repository's roster
includes assembly, hardware description languages, shader-adjacent and build-system formats, each
with its own comment syntax and some with constraints on where a comment may appear. The header lint
has to know all of them. This is a modest, recurring, boring cost, and it is accepted.

**GPLv2 compatibility is lost.** Apache-2.0 is compatible with GPLv3 in one direction and is not
compatible with GPLv2. If some future component must be combined with GPLv2-only code, that
component cannot live in this repository. Recorded as a known limit rather than discovered later.

**The licence is longer than anyone will read.** A reader skimming the repository in ninety seconds
will not read `LICENSE`. The SPDX header on each file and the SPDX field in `spectra.toml` are what
tooling and readers actually consume, which is why both are required rather than optional.

**What this does not establish.** The licence says nothing about the correctness, safety or fitness
of anything in this repository. Apache-2.0 sections 7 and 8 disclaim warranties and limit liability
in explicit terms, and `LIMITATIONS.md` — not the licence — is where the substantive limits of what
SPECTRA can establish are written. Nobody may cite the licence as evidence about the system.

**Reversal cost.** Changing the licence later requires the agreement of every contributor whose
contribution is still present, or the removal of their contributions. With a single contributor
today it is cheap; it stops being cheap at the first merged external contribution. That is a reason
to have decided it now rather than a reason the decision is permanent.

## Alternatives considered

### MIT

The strongest case: it is four paragraphs, every engineer and every legal department already knows
it, and for a research artifact whose main purpose is to be read and reproduced, patent exposure is
largely theoretical. Brevity has real value — a licence people actually read is worth something.

Rejected because the patent silence is the one thing that cannot be fixed later by adding a file.
The cost of Apache-2.0 over MIT is a redistribution obligation and a header lint; the cost of MIT
over Apache-2.0 is an open question for every downstream user, permanently.

### BSD-3-Clause

Adds a non-endorsement clause, which has some value given the name collision in ADR-0004. Rejected
for the same patent reason as MIT: the non-endorsement clause solves a smaller problem than
Apache-2.0 section 6 does, and does nothing about patents.

### Apache-2.0 for code, a separate licence for data and fixtures

Considered because generated corpora are not really code and a data licence would state the
synthetic-data position in licence terms. Rejected because Part II section 75 permits exactly one
licence, and because a second licence creates a boundary question — is a fixture generator code or
data? — that would have to be answered per file forever. The synthetic-data marker carries the
provenance statement instead, without splitting the licence.

### A source-available or non-commercial licence

Rejected outright by Part II section 75, and rejected on merit: a licence a reviewer cannot use
without asking their employer undermines the point of publishing an artifact for reproduction.

## References

- Part I section 1.5 — repository identity and the licence line.
- Part II section 75 — single licence, no dual-licensing, no non-commercial rider; the posture files
  required before the repository is public.
- Part I section 2 — the synthetic-data marker for fixtures and generated corpora.
- `spectra.toml`, `[project].license_spdx` — the machine-readable record of this decision.
- ADR-0004 — the name collision and the trademark disclaimer obligation.
- ADR-0009 — the repository is public from the first commit.
