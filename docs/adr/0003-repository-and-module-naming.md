# ADR-0003: Repository, account and module naming

## Status

Superseded by ADR-0011 — 2026-09-20

## Context

Three different names for the same repository appear in the specification and in the one
machine-readable file that already exists, and none of them agree.

- **Part I section 1.5** states the repository name as `spectra-security`, and the Go module as
  `github.com/<owner>/spectra-security/go/verifier`, with the account segment left as a placeholder.
- **Part I section 32.5** lays out the Go workspace with the module written as
  `github.com/<owner>/spectra/verify` — a different repository segment *and* a different leaf
  (`verify`, not `verifier`) from section 1.5, two sections of the same document apart.
- **`spectra.toml`**, written in this session, records `repository = "https://github.com/rakshit-737/spectra-security"`
  and `go_module = "github.com/rakshit-737/spectra-security/go/verify"`, both marked `TODO(decision): PLACEHOLDER`.
  Its comment argues for the short repository name on the grounds that the binary, the Python
  package and the certificate media type are all already `spectra`, and that "a repository name that
  differs from the artifact name by a suffix is a name people get wrong once each."
- **Part II section 74** uses `owner = "rakshit"` in an illustrative configuration block, which is
  not a real GitHub account name and was never intended as one.

So there are three open questions bundled together: which account, which repository name, and
`verify` or `verifier`. They have to be answered together because the Go module path is built from
all of them.

Why this cannot wait. A Go module path is not metadata — it is the import path. Every file in the Go
tree that imports another package in the same module writes the full module path in its import
block. `go.mod`, `go.sum`, every vendored path and every downstream `require` line carry it too. The
same account segment also appears in the container image references the specification uses for the
offline verification story: Part II section 69.2.2 shows a sceptic reproducing a published verdict
with `docker run ... ghcr.io/<owner>/spectra-verify@sha256:<digest>`. That command is meant to
appear in the README and in the artifact appendix of a paper. The account segment is baked into the
most quotable line in the project.

Deciding this after the first Go source file is committed is a mechanical rewrite of every import
line plus a coordinated edit of the documentation that quotes the URL. Deciding it now costs one
record.

## Decision

The names are fixed as follows.

| Surface | Value |
| --- | --- |
| GitHub account | `rakshit-737` |
| Repository name | `spectra-security` |
| Canonical repository URL | `https://github.com/rakshit-737/spectra-security` |
| Go module prefix | `github.com/rakshit-737/spectra-security` |
| Checker module | `github.com/rakshit-737/spectra-security/go/verify` |
| Rust crate prefix | `spectra-` |
| Python package | `spectra` |
| CLI binary | `spectra`, with subcommands `spectra prove` and `spectra verify` |

Four sub-decisions are contained in that table.

1. **The repository is `spectra-security`, not `spectra`.** Part I section 1.5 is the only place
   that names the repository normatively, and the bare word `spectra` is heavily overloaded — it is
   the plural of "spectrum" and a common term in spectroscopy, astronomy and signal processing. The
   suffixed name is searchable; the bare one is not. This supersedes the reasoning in the
   `spectra.toml` comment, which argued the opposite case.
2. **The account segment is `rakshit-737`.** It replaces the `<owner>` placeholders in Part I and
   the illustrative `rakshit` in Part II section 74. Neither of those was a real account name.
3. **The Go leaf is `verify`, not `verifier`.** Part I section 1.5 and section 32.5 disagree;
   section 32.5 wins, because the tree it draws is `go/verify/`, because the CLI subcommand fixed by
   Part II section 73.10 is `spectra verify`, and because the binary in Part II section 69 is
   `spectra-verify`. One word, everywhere.
4. **Rust crates are prefixed `spectra-`.** This is the crate-naming half of ADR-0004, recorded
   there in full; it is listed here because it is part of the same naming surface.

**These four values change together or not at all.** The places that must be edited in the same
change as any future rename:

- `spectra.toml`, `[project].repository`
- `spectra.toml`, `[names].go_module`
- `go/verify/go.mod`, the `module` line
- every Go import path in the repository
- `CITATION.cff`, `repository-code` and `url`
- every container image reference of the form `ghcr.io/<account>/...`, including digest-pinned ones
- `README.md` clone instructions and the offline verification command
- any published certificate, paper draft or release note that cites the URL

**`spectra.toml` currently disagrees with this record.** Its `repository` and `go_module` values
still carry the placeholder account and the short repository name. Until it is updated, `spectra.toml`
is the stale artifact and this ADR is the decision. Updating it is a separate change and is not made
retroactively true by this record.

What this does not decide: the crate names inside the Rust workspace beyond the prefix, the Python
module layout, the HTTP path structure, or the certificate media type string. Those are fixed by
ADR-0004 and by later records.

## Consequences

**Renaming later rewrites every import path.** This is the cost being avoided and it deserves to be
stated precisely, because it is frequently underestimated. In Go the module path is the import path:
there is no indirection layer, no alias, and no way to keep the old spelling working from inside the
repository. A rename means every `import "github.com/rakshit-737/spectra-security/go/verify/..."`
line changes, `go.mod` changes, `go.sum` entries change, and any consumer's `require` line changes.
GitHub will redirect the old web URL after a rename, but the Go module proxy treats the new path as
a different module, not an alias — a published module path is effectively permanent. The cost is
bounded and mechanical today, and grows with every file added.

**The name mismatch is accepted and has a real cost.** The repository is `spectra-security`; the
binary, the Python package and the certificate media type are all `spectra`. Somebody will type
`git clone .../spectra` and get nothing. The `spectra.toml` comment was right that this is a name
people get wrong once each. The judgement made here is that a one-time wrong guess is cheaper than a
permanently unsearchable name, and the README's clone line is the mitigation.

**The account name now appears in the project's most-quoted command.** The offline verification
invocation in Part II section 69.2.2 embeds `ghcr.io/<account>/spectra-verify@sha256:<digest>`. That
line is intended to end up in a README, in a paper's artifact appendix, and in reviewers' notes. It
is also the line that carries the project's central integration property. Binding the account
segment now is what makes that line writable.

**Three places can drift apart.** `spectra.toml`, `go.mod` and `CITATION.cff` each hold a copy of
the same name. `spectra.toml`'s own header states the principle that a second copy of a pin is a
second thing that can be wrong, but here the copies are unavoidable: `go.mod` cannot read a TOML
file and `CITATION.cff` has a fixed schema. A lint that checks the three agree is work this decision
creates, and it does not exist yet.

**What this does not establish.** Fixing a name settles nothing about whether the repository is
worth cloning. Nothing in this record is a claim about SPECTRA's behaviour; the implementation
status of every component named here is "not started".

## Alternatives considered

### Repository named `spectra`

The strongest case is the one `spectra.toml` already makes: the artifact name, the Python package,
the CLI and the certificate media type are all `spectra`, so a repository with a suffix is the only
member of the naming family that is different, and differences like that are what people get wrong.
There is also a real cost to typing the longer name in every clone command and every URL.

Rejected because the suffix is doing search work the short name cannot do, because Part I section
1.5 is the only normative statement of the repository name, and because the failure mode of the
short name — a reader who cannot find the repository at all — is worse than the failure mode of the
long one, which is a reader who guesses wrong once and is corrected by a redirect or a README.

### Leaving the account segment as a placeholder until publication

Tempting, because it defers a decision that feels administrative. Rejected because the placeholder
cannot survive contact with a Go file: the first import statement forces a real path, and a
placeholder committed into `go.mod` becomes a rename later. The whole point of deciding now is that
the cost is currently one table.

### A separate repository for the checker, so that its independence is visible in the URL

The argument is genuinely good: Part II section 69 requires the checker to be runnable by a sceptic
with no part of this repository's Python, database or network, and a separate repository would make
that independence structurally obvious rather than merely enforced by a dependency lint.

Rejected for now because the independence property the specification actually requires is a
build-graph property — `make no-service-deps` over `go list -deps` — and a second repository would
split the specification, the fixtures, the differential gates and the release process across two
places for a single maintainer. The visible-independence argument is real and is recorded here so
that a future record reversing this decision starts from the strong version of it.

## References

- Part I section 1.5 — repository name, binary name, package names, Go module.
- Part I section 32.5 — the Go workspace layout and the conflicting module path.
- Part II section 69.2.2 — the offline verification command and its image reference.
- Part II section 73.10 — the CLI subcommand names and the crate prefix.
- `spectra.toml`, `[project]` and `[names]` — the machine-readable naming surface, currently stale.
- ADR-0004 — crate naming and the banned string.
- ADR-0005 — why the checker is a standalone binary in the first place.
