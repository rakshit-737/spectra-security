# GNU Octave is used. MATLAB is not.

Source: build specification Part II, section 73, which overrides Part I's inclusion of MATLAB in the
target language set.

This file is the **only** file in the repository permitted to contain the string `MATLAB`.
`make polyglot-audit` fails with `BANNED_MATLAB_MENTION` on any case-insensitive match of that word
outside this path. If you are about to write it somewhere else, the answer is to write "GNU Octave"
instead, or to say nothing.

Status of the Octave component: not started. No script exists under `octave/`, no CI job runs one,
and no cross-check against the Rust liveness quantile has been performed.

## The statement

MATLAB is not present. MATLAB requires a licence and a licence server, which cannot satisfy the
offline, unlicensed, clean-clone-builds-with-the-network-off constraint. SPECTRA uses **GNU Octave**.
The numerical code in `octave/` is written for Octave, executed by Octave in CI, and has never been
executed by MATLAB. Documentation, the README, the language table and any paper say "GNU Octave".
Saying or implying "MATLAB" anywhere in this repository is a banned phrase enforced by the claims
gate.

## Why the distinction is kept sharp

1. **The offline constraint is load-bearing.** The project's central operational claim is that a
   clean clone builds and every gate runs with the network off, on one machine, with no licence
   server and no account. A licensed product cannot be in that path. Nothing about the polyglot
   surface is worth weakening that claim for.

2. **"Compatible" would be an untested claim.** The two languages share a syntax core and diverge in
   ways that matter for numerics: toolbox functions, integer and floating-point promotion rules,
   default output formatting, and the behaviour of several library functions at boundary conditions.
   Code that has never been run under a product cannot be described as working under it. The only
   checkable statement available is the negative one: the code has never been executed by MATLAB.

3. **The reader's inference is the thing being prevented.** Naming a widely licensed numerical
   product next to this project's numerical code invites a reader to assume an industry-standard
   toolchain validated the result. Nothing validated it except Octave and a cross-check against the
   Rust implementation. Saying "GNU Octave" every time is what keeps that inference from forming.

## What the Octave component is for, when it exists

The planned narrow promise, stated narrowly: Octave is the sole implementation of the exact-rank
inter-arrival quantile sweep over the liveness thresholds, cross-checked against the Rust liveness
quantile. Disagreement beyond the declared tolerance fails the build. That is the whole claim. It is
a Tier D research artifact, it sits on rung D6 of the descope ladder, and if it is cut its outputs
move into the Python analysis path.

None of that is built. The promise above describes an intention, not a component.

## Forbidden phrasings

- "MATLAB-compatible", "MATLAB-verified", "runs under MATLAB", "tested in MATLAB".
- "MATLAB/Octave" as a single toolchain name, in prose, in a table, in a path or in a CI job name.
- Any directory, file, job or identifier named after that product. The component directory is
  `octave/`; the CI job name says Octave.

The honest replacement in every case is "GNU Octave", with the non-equivalence stated rather than
glossed.
