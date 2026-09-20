# ADR-0009: The repository is public from the first commit

## Status

Accepted — 2026-09-20

## Context

The repository is public now, while nothing in it is implemented. The kernel, the checker, the
generator, the ingest path, the entity resolver, the API and the frontend all have the same
implementation status: not started. What exists is a specification, a plan, a conflict audit, a
decision queue and the beginnings of a skeleton.

A public pre-alpha repository has one hazard, and it is not the one people expect. The hazard is not
that somebody will steal the idea or file a bad issue. It is that **a reader cannot distinguish a
skeleton from a prototype unless the repository tells them**, and every default in the surrounding
tooling pushes toward implying the latter. A directory named for a kernel implies a kernel. A make
target implies something that runs. A README section heading implies a feature under it. A badge
implies a gate. None of these require anyone to write a false sentence; the false impression
assembles itself out of true fragments.

That hazard is sharpened by three things specific to this project.

**The audience includes people who will spend ninety seconds.** Part I section 1.6 names them
explicitly, third in priority after security engineers and reviewers. A reader with ninety seconds
reads the first screen and the status table and nothing else. Whatever those say is what the
repository claims, regardless of what the careful prose further down says.

**The subject matter invites overstatement.** The system's output is a security argument. The
vocabulary of the field — proves, guarantees, prevents, detects, formally verified, would have
stopped — is exactly the vocabulary that would make this repository sound finished, and every one
of those words is either false here or true only under scope qualifiers that vanish when the word is
used alone.

**The project's actual contribution is its honesty machinery.** The distinguishing idea is that
missing telemetry is modelled as an explicit licence for unobserved steps, so the system can
separate "this control is needed" from "this control is needed only because you could not see", and
that the resulting certificate is re-validated by an independently written checker. A repository
making that argument cannot afford a single unbacked sentence, because the argument is precisely
about the difference between an asserted result and a checkable one.

The alternative — stay private until the vertical slice runs — removes the hazard and removes
something else with it, which is the reason this record exists rather than a decision to wait.

## Decision

The repository is public from the first commit and stays public through pre-alpha. The consequence
accepted in exchange is that **every status marker and every claim is honest from the first commit**,
and honest by mechanism rather than by intention.

**1. Status is generated, never written.** The README's status table, roster table and waiver table
are produced from machine artifacts. Hand-written status prose does not survive the docs gate. A
component that is not started says "not started", including in the table, including when that makes
the table read as a column of the same phrase.

**2. Every externally visible claim is registered.** `docs/claims.md` binds each claim to the
surfaces it may appear on, the artifact that supports it, and its scope qualifier. A sentence on a
registered surface that is not registered fails the claims gate, as does a numeral that traces to
nothing. This covers the README, `docs/`, the UI string catalog, the CLI string catalog, the demo
transcript, paper text and release notes — everywhere an outside reader can reach.

**3. A banned-phrase gate covers the tempting words.** The forbidden list is authored once and
enforced everywhere: proves, guaranteed, prevents, would have stopped, formally verified, state of
the art, enterprise-grade, production-ready, realistic, AI-powered, detects attacks, and a bare
verdict token printed without its scope binding. A hit outside a registered entry fails the build.

**4. `LIMITATIONS.md` is linked from the README's first screen** and is majority generated from
measurement rather than written as a disclaimer. The limits are part of the first screen, not a page
a reader has to go looking for.

**5. The version stays at zero until a gate has run.** No tool and no reader may mistake a skeleton
for a prototype because a version number implied otherwise.

**6. No badge that a gate does not back**, and no badge of the decorative kind. A badge is a claim
in compressed form and is registered like any other.

**7. Waivers and quarantines surface in the README, not only in git history.** A relaxed gate takes
a written waiver with a date and a rationale, and that waiver appears in the generated table. A
repository whose README hides its waivers is dishonest by omission even if every individual
sentence in it is true.

**8. Open questions are stated, not held back.** The conflict audit, the decision queue and the
count of specification questions being built on defaults are published artifacts (ADR-0006,
ADR-0008). A release built on open high-severity defaults says so in its release notes.

**9. Nothing real is published as data.** The repository contains no observed telemetry, no
credentials, no customer data and no live environment. Generated corpora carry a synthetic-data
marker so that a redistributed bundle cannot be presented as observed telemetry, and the scenario
and generator trees are scanned for the primitives that would turn a research artifact into
something operational.

**10. The posture files are a debt, and it is named here.** Part II section 75 lists documents
required before the repository is made public: the limitations file, the non-goals document, the
claims registry, a document stating what a passing checker does *not* establish, the generated
roster audit, an adversarial review, a contributing file, and a citation file. The repository is
already public and most of these are not yet written. That ordering is a debt this record names
rather than hides; until they exist, the README's first screen carries the shortest honest
substitute, which is that nothing is implemented.

## Consequences

**Every honesty gate becomes load-bearing rather than tidy.** In a private repository the claims
registry and the banned-phrase gate would be good discipline. Public and pre-alpha, they are the
only thing standing between a reader and a wrong impression, because the reader is arriving before
there is anything to check the impression against. This raises the cost of the gates not existing
yet: today the rules in this record are held by hand.

**The history is permanent.** A sentence that overstates is not fixed by editing it later; the
commit stands, and on a public repository it is quotable forever. This cuts both ways and is
deliberate. It is also what makes ADR-0001's immutability rule cheap to honour — the history is
already immutable, so the records may as well be.

**Understating is free; overstating is not.** The asymmetry is the working rule. A reader who finds
that the repository does more than it said loses nothing. A reader who finds that it does less has
learned something about everything else it says, including the parts that were true.

**The first screen has to be written for the sceptic, repeatedly.** Every change that adds a
capability is also a change to what the first screen implies, and the generated tables only cover
the part that is mechanical. A new directory, a new make target or a new heading can move the
implication without touching a registered claim.

**Pressure to look finished will be continuous and will not announce itself.** It arrives as a
request for a nicer README, a screenshot, a demo video, a badge, a shorter status column. Each is
individually reasonable. The mechanisms above exist because judgement at the moment of the request
is not reliable, and because the person making the request will usually be the maintainer.

**Issues and external attention arrive before the project is ready for them.** The contributing
file is required to state that issues are accepted while the milestone plan stays fixed. That is a
real cost in attention, and it is the price of the benefit below.

**The benefit: the honesty machinery gets tested by strangers.** A claims registry that only its
author reads is a formatting exercise. A banned-phrase gate that has never had to stop a real
sentence has never been tested. Publishing early is what turns this project's central discipline
from a design into something with evidence behind it — and if it cannot survive being read while
incomplete, that is worth finding out at the skeleton stage rather than at the paper stage.

**What this does not establish.** Being public establishes nothing about the system. No claim in
this record or anywhere else in the repository today is backed by a run, because there have been no
runs. Status: not started.

## Alternatives considered

### Stay private until the vertical slice runs, then publish

The strongest case: no chance of a wrong impression, no pressure to look finished, no issues to
triage while the foundation is being laid, and a first public commit that actually does something.
Most projects do this and most are right to.

Rejected for two reasons. The first is that publishing later invites a curated history — a first
commit that presents a polished state and hides the reasoning, which is the opposite of what a
project whose contribution is auditability should produce. The second is that it removes the
pressure that makes the honesty gates real. A claims registry built against an imaginary reader is a
formatting exercise; built against an actual one, it is a gate. The decision is to take the harder
posture while the cost of a mistake is lowest, because a skeleton misrepresented is a smaller
failure than a result misrepresented.

### Public, with claims and limitations deferred until there is something to claim

Superficially sensible: there is nothing to register, so why build a registry. Rejected because a
claim deferred is a claim made by silence. A repository with a kernel directory, a prove target and
no limitations document has made several claims without writing any of them down, and those are
exactly the claims no gate can catch.

### Public with a prominent pre-alpha banner and nothing else

Cheap and common. Rejected because a banner is a single sentence competing with an entire page of
structural implication, and because it decays: the banner stays long after parts of the repository
have become real, at which point it is itself inaccurate and readers have learned to skip it.
Generated per-component status does not decay in that way.

## References

- Part I section 1.6 — the audiences, in priority order.
- Part II section 71 — the claims registry, the banned-phrase gate and the limitations document.
- Part II section 75 — the non-goals, the posture files required before publication, and the rule
  that waivers surface in the status table.
- `KICKOFF.md` section 6 — what may never be claimed, and the rule that understating is free.
- `spectra.toml`, `[project].version` — the version held at zero until a gate has run.
- ADR-0001 — immutability, which a permanent public history makes cheap.
- ADR-0002 — the licence, and what it does and does not say about the system.
- ADR-0007 — generated counts, which exist for the same reason as generated status.
- ADR-0008 — open questions published rather than held back.
