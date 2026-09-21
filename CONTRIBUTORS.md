# Contributors

SPECTRA is written by a human author working with an AI coding agent. This file records who did
what, because a reader of the commit history deserves to know, and because the project's own
honesty rules (see `CLAIMS.md`) apply to claims about its authorship as much as to claims about
its results.

## People

**Rakshit** ([@rakshit-737](https://github.com/rakshit-737)) — author and maintainer.

Owns the project: its subject, its scope, and every decision recorded in `docs/adr/` and
`docs/plan/DECISIONS.md`. Chose the research question, set the constraints that shaped the design
(local-first, offline, deterministic core, no fabricated numbers, a large polyglot surface with
each language earning its place), settled the naming and licensing, and reviews the work.

## Agents

**Claude** ([Claude Code](https://claude.com/claude-code), Anthropic) — generated the substance of
the repository as it currently stands.

Specifically, as of the skeleton commits:

- the build specification in `docs/prompt/` — all 77 sections across both parts;
- the adversarial critique that produced Part II, and the Part I / Part II conflict audit in
  `docs/plan/CONFLICTS.md`;
- the planning documents: `PLAN_v1.md`, `DECISIONS.md`, `GLOSSARY_STUB.md`;
- the architecture decision records in `docs/adr/`;
- the repository skeleton: manifests, configuration, CI declarations, the Makefile, the language
  directory records, and the documentation set.

This is stated plainly rather than buried in a tool acknowledgement. The work was generated, not
merely assisted, and the commit history reflects that.

## What this division does not mean

It does not mean the content is unreviewed, and it does not mean it is correct. The audit in
`docs/plan/CONFLICTS.md` found 453 disagreements inside the specification that Claude itself
wrote — 213 of them silent contradictions between its two parts. That is the honest state of the
artifact: substantial, internally inconsistent in known and catalogued ways, and not yet
implemented.

The gates declared in `ci/gates.toml` — all but three of them not implemented —
are written down precisely because neither a human nor an agent should be trusted on assertion.
Nothing in this repository is claimed to work until a named gate proves it, and no number may
appear in any document unless the artifact that produced it is recorded alongside.

## Adding yourself

See `CONTRIBUTING.md`. Contributors are listed here in the commit that first lands their work,
with a one-line description of what they own — not a generic thanks.
