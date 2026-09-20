# ADR-0011: Correct the stale artifact named in ADR-0003

## Status

Accepted — 2026-09-20

Supersedes ADR-0003.

## Context

ADR-0003 fixed the GitHub account, the repository name, the Go module path and the crate prefix. Its
Decision section closes by naming the one artifact that had not yet caught up with the record:

> **`spectra.toml` currently disagrees with this record.** Its `repository` and `go_module` values
> still carry the placeholder account and the short repository name. Until it is updated,
> `spectra.toml` is the stale artifact and this ADR is the decision.

That is false. `spectra.toml` agrees with ADR-0003 on both keys:

| Key in `spectra.toml` | Value it carries | Against ADR-0003's table |
| --- | --- | --- |
| `[project].repository` | `https://github.com/rakshit-737/spectra-security` | identical |
| `[names].go_module` | `github.com/rakshit-737/spectra-security/go/verify` | identical |

The account segment is `rakshit-737`, not a placeholder, and the repository segment is the full
`spectra-security`, not the short name. Neither value carries the `TODO(decision): PLACEHOLDER`
marker ADR-0003 quotes; the comment under each one names `docs/adr/0003` as the record that fixed
it and lists the files that must change with it. ADR-0003's References entry describing that file as
"the machine-readable naming surface, currently stale" is wrong for the same reason.

The history settles how the sentence came to be wrong, and the answer is worse than a later edit
overtaking it. ADR-0003 was committed at 16:18. `spectra.toml` was first committed at 16:52, and
carried `https://github.com/rakshit-737/spectra-security` in that first commit and in every commit
since. ADR-0003 therefore asserted the staleness of a file that did not yet exist, and described
values it had never held. The claim was not overtaken; it was never true.

That is the instructive part. The sentence reads as an observation of the tree, and it was an
assumption about it. ADR-0003 is merged, and a merged record cannot be edited.

**The artifact that actually disagrees is `go/verify/go.mod`**, and not in the way ADR-0003's
checklist would lead a reader to expect. Its `module` line is correct:

```
module github.com/rakshit-737/spectra-security/go/verify
```

That is the value in ADR-0003's table, character for character: right account, full repository name,
`verify` and not `verifier`. What contradicts the record is the header comment standing above it:

```
// TODO(module path owner): github.com/rakshit-737/spectra-security is a placeholder chosen
// for this skeleton. Change it here and in every import path when the
// repository's final owner is fixed.
```

The owner is fixed. ADR-0003 fixed it, and the path is not a placeholder chosen for a skeleton. The
file carries the decided value under a standing instruction to change it.

**What this costs, precisely.** Nothing today, and that is what makes it dangerous. The Go toolchain
reads the `module` directive and ignores comments, so `go build`, `go vet` and `go list -deps` all
resolve the correct path; `go.work` lists `./go/verify` and resolves; `go/verify/doc.go` and
`go/verify/abi/doc.go` declare packages and import nothing, so no import line spells the path yet.
No build breaks, and none will break while the comment stands. The defect is entirely in what the
comment instructs a reader to do. A contributor who obeys it performs exactly the rename ADR-0003's
Consequences section describes as the cost being avoided: every import path, `go.sum`, every
downstream `require` line, and a module path that the Go module proxy treats as a different module
rather than an alias once it has been published. The comment is an invitation to break the decision,
sitting in the file the decision names.

It is also why the error survived. An audit that greps `go/verify/go.mod` for the module path finds
agreement with ADR-0003 and stops. The disagreement is in prose that no gate reads, in a file whose
machine-readable content is correct.

A smaller residue of the same kind sits in `spectra.toml`. Its `[project].name` value, `spectra`, is
correct — ADR-0003 fixes the CLI binary and the Python package as `spectra`. The comment above it
still argues the case for naming the *repository* `spectra`, and still carries a `TODO(decision)`
for reversing it. That is the reasoning ADR-0003 sub-decision 1 explicitly supersedes, preserved
without saying that it was superseded. The value is right; the justification under it is the losing
side of a settled argument.

ADR-0001 establishes that a merged record is immutable and that the only permitted edit to it is its
Status line. ADR-0010 applied that rule to a wrong numeral rather than editing the digit in place.
The same rule applies here, to a wrong claim about the state of the tree. Editing ADR-0003 to name a
different file would leave no trace that the record had ever pointed at the wrong one, and the
pointing is the instructive part: ADR-0003 looked for staleness in the file it had just written, and
did not look at the file it had listed second on its own change checklist.

## Decision

ADR-0003's decision is unchanged and is restated here in full force.

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

The sub-decisions inside that table stand as ADR-0003 records them:

1. The repository is `spectra-security`, not `spectra`, because the bare word is overloaded and
   unsearchable, and Part I section 1.5 is the only normative statement of the name.
2. The account segment is `rakshit-737`, replacing the `<owner>` placeholders in Part I and the
   illustrative `rakshit` in Part II section 74.
3. The Go leaf is `verify`, not `verifier`: Part I section 32.5 wins over section 1.5, matching the
   `spectra verify` subcommand and the `spectra-verify` binary.
4. Rust crates are prefixed `spectra-`, as recorded in full in ADR-0004.

These values change together or not at all, and the change checklist in ADR-0003 stands unaltered:
`spectra.toml` `[project].repository`, `spectra.toml` `[names].go_module`, the `module` line in
`go/verify/go.mod`, every Go import path, `CITATION.cff`, every `ghcr.io/<account>/...` image
reference including digest-pinned ones, the `README.md` clone and offline-verification lines, and
any published certificate, paper draft or release note citing the URL.

The only thing this record changes is the claim about which artifact is stale. The corrected
statement:

> **`spectra.toml` agrees with this record.** Its `repository` and `go_module` values carry the
> decided account and the full repository name, and each cites `docs/adr/0003` as the record that
> fixed it. The artifact that disagrees is `go/verify/go.mod`: its `module` line is correct, but its
> header comment declares the path a placeholder and instructs a future reader to rename it. The
> comment is the stale thing, not the value.

The repair follows from that and is a separate change from this record: delete the
`TODO(module path owner)` comment from `go/verify/go.mod` and replace it with a line naming
`docs/adr/0003` as the record that fixed the path and this record as the one that corrected the
audit, in the shape the comments in `spectra.toml` already use. The `module` line itself is not
touched. Nothing else under `go/verify/` changes, because nothing else spells the path.

The comment above `[project].name` in `spectra.toml` is corrected in the same change, to state that
the repository-name argument it makes was rejected by ADR-0003 sub-decision 1, and that the value
remains `spectra` because that is the artifact name and not the repository name. Its
`TODO(decision)` marker goes with it; the decision was taken.

ADR-0003's Status line is changed to `Superseded by ADR-0011`. No other line of ADR-0003 is edited.
It stays in the tree naming the wrong file, which is what the immutability rule is for.

## Consequences

- The naming decision is untouched. Every name ADR-0003 fixed is still fixed, and a reader who needs
  the values can read them off the table above without consulting the superseded record.
- **Superseding a whole record to correct one sentence puts the entire naming decision behind a
  `Superseded by` banner.** A reader who stops at ADR-0003's Status line may conclude the names are
  open again, which is precisely wrong. That cost is accepted rather than avoided, because the
  alternative is a judgement about which corrections are small enough to make silently, and ADR-0001
  exists to remove that judgement. The mitigations are the full restatement above and the index row
  for this record, which says what it decides.
- The error corrected here is not arithmetic, as in ADR-0010, but a claim about the state of the
  tree. Claims like that go stale as the tree changes, which is an argument for making fewer of them
  in immutable records. ADR-0003 asserted the condition of a file; the assertion is now false and
  the record cannot be updated. A future ADR that needs to talk about a file should say what the
  decision requires of that file, not what the file currently contains.
- ADR-0003's change checklist survives this correction intact, and is the better audit artifact of
  the two: it named `go/verify/go.mod`, and reading the checklist against the tree is what surfaces
  the contradiction. The prose sentence that singled out one file as stale is what was wrong.
- The drift ADR-0003 warned about, between `spectra.toml`, `go.mod` and `CITATION.cff` each holding
  a copy of the same name, is confirmed as a real failure mode on the first look — even though all
  three copies of the value currently agree. The drift appeared in the commentary around the copies
  instead. The lint ADR-0003 identified as work it creates, which still does not exist, would check
  the values and would not have caught this. Checking prose is harder, and for now the only check is
  reading.
- Repairing `go/verify/go.mod` costs the deletion of a comment today. There are no import paths to
  rewrite, because there is no Go implementation: the status of the checker is "not started". The
  same repair after the module path is published is not available at any price.
- Nothing in this record is a claim about SPECTRA's behaviour. It corrects a statement about two
  files in this repository and restates a decision about names.

## References

- ADR-0001, the immutability rule and the required format.
- ADR-0003, superseded by this record, whose naming decision is restated above in force.
- ADR-0004, crate naming and the banned acronym.
- ADR-0010, the precedent for correcting a merged record with a new one.
- `spectra.toml`, `[project]` and `[names]` — the machine-readable naming surface, which agrees with
  ADR-0003.
- `go/verify/go.mod` — a correct `module` line under a contradictory header comment.
- Part I section 1.5 and section 32.5 — the conflicting statements ADR-0003 settled.
