# SPECTRA tests

Standard library only. No pip, no network, no third-party packages, no fixtures
downloaded at run time. Everything here runs with a bare Python 3.11+ (the tree
pins 3.14) and nothing else.

## Run the whole suite

From the repository root:

```
python -m unittest discover -s tests -t . -v
```

`-t .` puts the repository root on `sys.path`, so `from tools.claims_check import
run_checks, Finding` resolves. The test module also inserts the root itself, so
these work too:

```
python -m unittest tests.test_claims_check -v
python tests/test_claims_check.py
```

On Windows, use the same commands (`py -3 -m unittest ...` if `python` is not on
PATH). None of the tests shell out to `make`: every make target in this
repository is Linux-only by design (`Makefile` refuses to run outside WSL2, the
devcontainer or CI), so the checker and this suite must stay runnable directly.

## Run one class or one test

```
python -m unittest tests.test_claims_check.TestBannedPhrases -v
python -m unittest tests.test_claims_check.TestRegistryGrammar.test_reordered_keys_fail -v
```

## The one opt-in test

`TestAgainstTheRealRepository` runs the checker over this repository rather than
over a synthetic one. It is skipped unless you ask for it, because `docs/prompt/`
is large:

```
SPECTRA_TEST_REAL_TREE=1 python -m unittest tests.test_claims_check -v      # bash
$env:SPECTRA_TEST_REAL_TREE=1; python -m unittest tests.test_claims_check -v  # PowerShell
```

`TestNoErase` is skipped when `git` is not on PATH, and the dangling-symlink test
is skipped where the platform will not create one (an unprivileged Windows
shell). Everything else always runs.

## What this suite is

`tests/test_claims_check.py` is a contract test for `tools.claims_check`. It was
written from the contract alone -- CLAIMS.md (the record grammar, the scope
rule, the banned-phrase table, the surface list, the exempt paths) and the eleven
`G-CLAIM-*` rows of `ci/gates.toml` -- with no sight of the implementation, and
no expected value copied from a program's output. That is the repository's own
rule: a component is never green on a test written after seeing what it prints.

Every test builds a throwaway repository in a temp directory, writes the two or
three files the check under test reads, and calls:

```python
findings = run_checks(root=Path(tmpdir))
```

Nothing under `D:/Academics/spectra` is read or written by a test except the
opt-in real-tree test, which only reads.

It covers, per check, a clean case that must produce no finding, a violating
case that must produce exactly the expected finding, and at least one boundary:

| area | class |
|------|-------|
| API shape, relative paths | `TestApiContract` |
| byte-identical reports across runs and trees | `TestDeterminism` |
| the tool never edits the repository | `TestNeverModifiesTheRepository` |
| G-CLAIM-PARSE record grammar | `TestRegistryGrammar` |
| scope clause lint | `TestScopeClause` |
| G-CLAIM-BANNED, exempt paths, unwaivability | `TestBannedPhrases` |
| G-CLAIM-ANCHOR, segmentation, fences | `TestAnchorGate` |
| G-CLAIM-REGISTERED: drift, orphan, undeclared surface, tuned headline | `TestRegisteredGate` |
| G-CLAIM-SUPPORT / G-CLAIM-NUMSRC, record side | `TestSupportAndNumbers` |
| G-CLAIM-PLACEHOLDER | `TestPlaceholderTokens` |
| G-LIMITS-NOHAND | `TestLimitationsNoHandWrittenNumerals` |
| G-FRAMING-README | `TestFramingReadme` |
| G-CLAIM-ALLOWCAP, the parts the contract pins down | `TestNonClaimAllowlist` |
| G-CLAIM-NOERASE over real git history | `TestNoErase` |
| undecodable and unparseable inputs | `TestUndecodableAndUnparseableInputs` |
| the cases that bit this repository | `TestCasesWithoutAContractedFindingKind` |

## Reading a failure

`Finding`'s attribute names are not fixed by the contract, so the helpers read a
finding's kind, gate, path and line through a short list of plausible names and
fall back to the rendered object. Assertions are made on the tokens the contract
*does* fix -- `BANNED`, `UNANCHORED`, `TEXT_DRIFT`, `ORPHAN`, `BP-05`,
`CLM-0001`, `G-LIMITS-NOHAND` -- never on a guessed attribute name. Every
failure message prints the whole finding list, so a mismatch shows what the
checker actually reported.

Two kinds of failure are worth separating when this suite first runs red:

- a missing or differently named finding kind: the checker does not implement,
  or does not label, something the contract requires;
- a helper that cannot see the kind at all (`kind=''` in the failure dump): the
  `Finding` object exposes its identity under a name the helper list does not
  know. Add that name to `_KIND_ATTRS` / `_GATE_ATTRS` in the test module -- that
  is a naming fix, not a contract change.

## Deliberate gaps

These are not tested, because the contract does not determine the answer. They
are listed here so nobody mistakes the silence for coverage:

- `normalise()` is undefined, so no test depends on whitespace folding, markdown
  inline markup, smart quotes or a sentence wrapped across two source lines. The
  registration tests use single-line, byte-identical sentences only.
- The anchor slug rule for `README.md#anchor` / `docs/path.md#anchor` is
  undefined, so `SURFACE_UNDECLARED` is tested only where the *path* is not
  declared at all, never on an anchor mismatch.
- The allowlist cap value, the schema of `docs/claims-nonclaims.toml` and the
  line-content-hash function are undefined, so only the robustness and
  no-suppression properties are tested.
- The rounding-rule mini-language for `note` has no grammar, so nothing tests
  re-applied rounding.
- BLAKE3 is not in the standard library, so no test supplies a true digest;
  support freshness is exercised only through `MISSING_ARTIFACT` and the
  record-side number check.
- Tiering (`MISSING_ARTIFACT` warns per-PR but fails nightly and release) needs
  an input the target does not take; the tests require only that the state is
  reported, not which exit tier it lands in.
- The CLI argument shape (`--json`, `--summary`, how the root is passed) is not
  fixed by the contract, so exit codes are asserted at the library level: a clean
  tree yields no findings, a violating tree yields findings.
- Whether `docs/prompt/` and `CLAIMS.md` are scanned for claim *candidates* (both
  are exempt from banned patterns only) is an open question, so no test asserts
  `UNANCHORED` behaviour inside either.
