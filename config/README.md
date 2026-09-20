# `config/` — all policy and tunables as data

Status: **not started**. This directory currently holds schemas-to-be, empty catalogs and
documentation. No rule, no control, no scenario and no threshold is defined yet.

Owning sections: Part I §34 (configuration and policy as data), Part I §32.2 (tree placement).
Part II overrides are noted inline and are authoritative where they appear.

## 1. The rule

Behavior is data. Detection logic, temporal axioms, obligation axioms, control catalogs,
thresholds, scenario definitions, lab topology and benchmark plans live in `config/` and `lab/`.
They are schema-validated, hashed into every run manifest and every certificate, and reloadable
without recompiling anything except the generated guard code, which is regenerated from the same
files.

Consequences that are not negotiable:

- A behavior change that is not a code change must be a diff under `config/`.
- A `config/` diff that changes a hashed input invalidates every certificate that cited the old
  hash. That is correct and intended.
- Rules change between runs, never within one.

## 2. Precedence order (Part I §34.6)

Lowest to highest. Later wins. Merging is per-leaf-key, never whole-table replacement, except for
arrays, which are replaced wholesale and never appended to. The resolved origin of every key is
retained and printed by `spectra config show --with-origin`.

| # | Source | Example | Mutable at runtime |
|---|---|---|---|
| 1 | Schema `default` values | `"default": 0.99` in `thresholds.liveness.schema.json` | no |
| 2 | `config/defaults/*.toml` | `recon.horizon_k = 4` | no |
| 3 | `config/profiles/<PROFILE>.toml` | `PROFILE=bench` | no |
| 4 | Scenario file `[overrides]` block | `config/scenarios/s01.toml` | no |
| 5 | Local overlay `config/local.toml` (git-ignored) | developer machine | no |
| 6 | Environment variables `SPECTRA__<SECTION>__<KEY>` | `SPECTRA__RECON__HORIZON_K=6` | no |
| 7 | CLI flags | `spectra prove --horizon-k=6` | no |

Nothing in this table is mutable at runtime. There is no hot reload, no remote config source and
no feature-flag service.

**Frozen keys** may only be set at levels 1-4 and are rejected from environment and CLI:
`core.hash_algorithm`, `core.canonical_json`, the kernel threshold-literal limit, `rules.*`,
`controls.*`, `costs.*`, and the generator seed once a run has started. Attempting to override a
frozen key from level 6 or 7 is a fatal config error, not a warning.

## 3. No magic number lives in code (Part I §34.7)

Any numeric literal other than `0`, `1`, `-1`, `2`, array indices and exponents in pure
mathematics must come from the generated config bindings. This is enforced, not requested:
`tools/lint/no-magic-numbers` runs per language and is part of `make lint`.

- Never hardcode a quantile, a timeout, a window, a cap, a cost or a level ordinal.
- Thresholds derived from data are computed from the run's own data at runtime; the parameter that
  selects them (for example a quantile) is config.
- Suppression requires an inline comment of the form `# noqa: PLR2004 -- <reason>` with a non-empty
  reason, and the linter's own test checks that the reason is non-empty.
- `tools/codegen` generates Pydantic models, Rust `serde` structs with `schemars`, Go structs and
  TypeScript types from the JSON Schemas. CI regenerates and diffs to zero. Hand-editing a
  generated file fails the build.

Status of the lint and the codegen: **not started**.

## 4. Startup validation, fail closed (Part I §34.5)

```
config/*.toml   1. PARSE           TOML/YAML/HCL -> untyped tree; errors as file:line:col
config/*.yaml   2. SCHEMA VALIDATE JSON Schema 2020-12; additionalProperties:false
lab/*.hcl       3. MERGE           precedence order of §2 above, origin recorded per key
                4. CROSS-VALIDATE  referential integrity, threshold-literal budget, horizon k > 0
                5. FREEZE + HASH   canonical JSON -> BLAKE3 per file and per bundle; immutable
```

- On any failure the process exits with code 78 (`EX_CONFIG`), prints every error rather than the
  first, and starts no server, no worker and no solver.
- An unknown key is fatal. `additionalProperties: false` in every schema. A typo is never a silent
  default.
- After freeze the config object is immutable and tests assert it.

## 5. Config in the run record (Part I §34.9)

Every run manifest and every certificate carries the BLAKE3 of the rules (the concatenated
canonical form of all rule files), the controls catalog, the goal, the bundle and the liveness
input, plus the profile name, the resolved seed and the horizon `k`. `spectra verify` recomputes
those hashes from the files it is given and refuses the certificate if any differs. A certificate
whose config hashes cannot be reproduced is invalid — not suspect, invalid.

## 6. Tree

From Part I §34.2, with Part II overrides applied.

```
config/
|-- schema/                             JSON Schema 2020-12, one file per config kind
|-- defaults/                           base layer; every key that has a default lives here
|   |-- core.toml                       ids, hashing, canonical JSON settings
|   |-- ingest.toml                     batch sizes, parser strictness, chain verification mode
|   |-- recon.toml                      horizon k default, grounding caps, silent-envelope switches
|   |-- kernel.toml                     threshold-literal limit, search budgets, downgrade behavior
|   |-- api.toml                        timeouts, pagination, CORS origins (lab-local only)
|   `-- web.toml                        feature flags surfaced to the UI build
|-- profiles/{dev,ci,demo,bench}.toml   sparse overlays over defaults/
|-- rules/
|   |-- detection/*.toml                the single rule table (heads, bodies, guards)
|   |-- temporal/*.toml                 interval and ordering axioms
|   `-- obligations/*.toml              hand-written obligation axioms
|-- controls/controls.toml              control catalog with ordered levels
|-- costs/costs.toml                    USER-AUTHORED ONLY; may be absent
|-- goals/*.toml                        goal facts + horizon
|-- policies/
|   |-- verdict.yaml                    flag -> verdict mapping; ROBUST suppression rules
|   |-- grounding.yaml                  caps, cap-hit behavior, publication of sizes
|   |-- redaction.yaml                  what narration may and may not repeat
|   `-- retention.yaml                  run-artifact lifetime in data/runs/
|-- scenarios/*.toml                    scenario definitions
|-- thresholds/
|   |-- liveness.toml                   quantile choice, min sample count, gap tolerance
|   |-- skew.toml                       difference-constraint bounds for backdating detection
|   `-- resolve.toml                    entity-resolution decision thresholds
`-- bench/degradation.toml              reference to the degradation matrix definition
```

Of these, only `defaults/core.toml`, `controls/controls.toml`, `bench/degradation.toml` and the
README files exist. Everything else is **not started**.

**OVERRIDE, Part II §73.10 over Part I §34.2.** Part I named the kernel defaults file
`config/defaults/eclipse.toml`. The string `eclipse` may not appear in any machine-readable
surface, which includes file names. The file is `config/defaults/kernel.toml`. ECLIPSE remains the
prose acronym for SPECTRA's proof kernel and appears only in documentation.

**OVERRIDE, Part II §57 over Part I §34.3/§34.4.** Part I's config examples used the word `atom`
for both a ground fact and a control threshold literal. `atom` is a retired term and is banned as
an identifier segment, a JSON key, a TOML key and a SQL column, with no allowlist path. Config keys
use `fact` or `threshold_literal` as appropriate. See `docs/vocab.toml` and `make lint-vocab`
check V6.

## 7. Negative requirements (Part I §34.10)

- Do not read configuration at import time or in a module-level constant. The frozen config object
  is passed explicitly.
- Do not allow a config value to be mutated after freeze.
- Do not add a config key without adding it to a schema, with a description, in the same commit.
- Do not add a debug or unsafe flag that relaxes a verdict rule. Flags in `policies/verdict.yaml`
  may only make verdicts weaker, never stronger.
- Do not generate `costs/costs.toml`. If it is absent the frontier is disabled and the UI says so.
  SPECTRA never invents a cost.
- Do not put rules, thresholds or control definitions in the database. Postgres stores telemetry,
  derived facts and run artifacts; policy lives here, under version control.
- Do not support a remote config source, a feature-flag service, or hot reload of rules mid-run.
