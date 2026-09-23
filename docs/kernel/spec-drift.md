# Where the slice specification and the code disagree

Status: a list, not a plan. Each row is a place where `docs/kernel/slice-spec.md` says one
thing and the emitted artifacts say another. None of them is a defect in the sense of a
wrong answer; every one of them is a place where a reader who trusts the specification
would be surprised by a real file.

The list was produced while writing `docs/OVERVIEW.md` and `docs/READING-A-CERTIFICATE.md`
against real certificates. Writing a document that had to be true of both turned these up;
reading either side alone did not.

WHICH SIDE WINS, for now. The documents describe what the code emits, because that is what
a reader will open. The specification is not edited to match, because it is the contract
several of these fields were designed against and a silent rewrite would destroy the record
of the disagreement. Closing a row means an ADR that says which side moves.

| # | The specification says | The artifacts say | Why it is not urgent |
| --- | --- | --- | --- |
| 1 | digests are blake3, and substituting another silently is forbidden | every digest is blake2b-256, labelled `b2b256:` | The substitution is DECLARED, not silent: each certificate carries `schema.hash_algorithm` and `schema.hash_substitution_note`. No ADR covers it, which is the gap. |
| 2 | short identifiers `fa:`, `ri:`, `lc:`, `c:` at 16 or 32 hex | `fh:`, `in:`, `lic:`, `cor:` at 64 hex, plus `ctl:`, `rl:`, `src:` which the list omits entirely | Only the spelling differs; the domain separation the prefixes exist for is intact. `ev:` matches on both sides. |
| 3 | the first 26 bytes are `{"body":{"schema":{"v":` | `FILE_MAGIC` is the nine octets `{"body":{` | The longer prefix cannot exist under the same document's key-sorting law, which `cert.py` states where it defines the constant. The specification contradicts itself here, not the code. |
| 4 | `body.cut` carries `cardinality`, `mask` and `minimality` | `body.cut` is a bare atom-reference array; minimality lives in `verdict` | Nothing is lost: the checker recomputes cardinality from the array and reads minimality where it is. |
| 5 | `disputed_events` sits in the source profile | it sits in the liveness document | Corrected in the specification on 2026-09-23; recorded here because the error was introduced by the ADR-0016 amendment itself. |
| 6 | route B is steps k5/k6, and the tree holds `scenario.yaml`, `controls/catalog.yaml`, `sources.toml` | eight steps with the escalation at k7, and `scenario.toml`, `controls.toml`, no `sources.toml` | The scenario was edited after the specification was written. The documents avoid step numbers for this reason. |
| 7 | the checker and the emitter share only the on-disk formats and a generated field table | `config/vs/cert-schema.toml` does not exist, and both sides share `spectra_core.canon` | The checker's own independence statement is accurate and is the one every report prints. The specification's version overstates the separation. |
| 8 | `realizability` has two of four checks implemented | every certificate carries `UNCHECKED` | Not investigated. The field is honest about itself, which is why it is low priority and why it is written down here rather than forgotten. |

## Two checker gaps, which are a different kind of finding

These are not disagreements; they are obligations nobody wrote.

- `cut_delta_canonical` is checked for presence and canonical order, and for nothing else.
  Its relationship to the two cuts is not re-derived by the checker.
- The premium's set arithmetic - that `blindness_premium` equals `nec_max \ occ_min` - is
  enforced by the emitter and is not re-derived by the checker. O14 verifies the
  publication preconditions, not the sets.

Both mean a defect in the emitter's premium computation would reach a certificate that the
checker accepts. That is the failure mode the two-implementation design exists to catch, so
these two are the most valuable obligations still missing.
