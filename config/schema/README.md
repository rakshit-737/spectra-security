# `config/schema/` — JSON Schema for every config kind

Status: **not started**. No schema file in the table below exists yet. This README declares the
convention and the inventory so that the first schema written has nothing left to decide.

Owning sections: Part I §34.2 (the inventory), Part I §34.5 (validation), Part I §34.7 (codegen).

## 1. Convention

1. **Dialect.** JSON Schema 2020-12. Every file declares
   `"$schema": "https://json-schema.org/draft/2020-12/schema"` explicitly. No other dialect, no
   implicit dialect.
2. **`$id`.** Every file declares a stable `$id` of the form
   `https://spectra.invalid/schema/v1/<name>.schema.json`. The host is a reserved-for-testing name
   because SPECTRA is offline and no schema is ever fetched over a network.
   TODO(decision: schema `$id` host): `spectra.invalid` was chosen because it can never resolve.
   To change it, edit every `$id` and every `$ref` in one commit; resolution is local-file only, so
   the host string is cosmetic.
3. **`additionalProperties: false` everywhere.** On every object, including nested ones. An unknown
   key is a fatal error, never a silent default.
4. **Every property has a `description`.** A property without one fails the schema lint.
5. **`default` is precedence level 1.** A `default` in a schema is the lowest layer of the
   precedence order in `config/README.md` §2. A key that has no sensible default has no `default`
   and is `required`.
6. **Integers, not floats, wherever the value participates in a decision.** Part II §69.5.2 forbids
   IEEE floating point in every ABI payload, and Part II §61.2 requires fractions to be authored as
   decimal strings and converted to exact rationals at load time. Schemas for anything the kernel,
   the checker or the perturber reads therefore use `"type": "integer"` or a
   `"type": "string"` with a rational `pattern`, never `"type": "number"`.
7. **Identifier properties are pattern-constrained** against the ABNF of Part II §57.2 and the
   pattern is copied from `docs/vocab.toml`, not retyped.
8. **No schema is hand-mirrored into code.** `tools/codegen` generates Pydantic models, Rust
   `serde` structs with `schemars`, Go structs and TypeScript types from these files. CI
   regenerates and diffs to zero. Hand-editing a generated file fails the build.
9. **Same-commit vocabulary rule.** A commit that adds a new concept to a schema — a new certificate
   key, a new closed-enum variant, a new identifier type — must add its row to `docs/vocab.toml` in
   the same commit. `make lint-vocab` check V8 enforces this. There is no follow-up-PR exception.

## 2. Inventory

The milestone column says which milestone must add the file. Milestone definitions are in Part I
§52. Every row is **not started**.

TODO(decision: per-schema milestone assignment): Part I §34.2 lists the schema files but does not
assign each to a milestone. The assignments below follow the deliverables in Part I §52.3-§52.13 —
a schema is due at the milestone that first ships the data it validates. To change one, edit this
table and the corresponding milestone acceptance list together.

| File | Validates | Milestone | Status |
|---|---|---|---|
| `profile.schema.json` | `config/profiles/*.toml` overlays and the profile selector | M0 | not started |
| `scenario.schema.json` | `config/scenarios/*.toml` | M1 | not started |
| `lab.schema.json` | `lab/*.hcl` topology and attacker choreography | M3 | not started |
| `rules.detection.schema.json` | `config/rules/detection/*.toml` | M3 | not started |
| `rules.temporal.schema.json` | `config/rules/temporal/*.toml` | M3 | not started |
| `controls.schema.json` | `config/controls/controls.toml` | M3 | not started |
| `rules.obligations.schema.json` | `config/rules/obligations/*.toml` | M4 | not started |
| `thresholds.schema.json` | `config/thresholds/{liveness,skew,resolve}.toml` | M4 | not started |
| `goal.schema.json` | `config/goals/*.toml` | M4 | not started |
| `policy.schema.json` | `config/policies/*.yaml` | M5 | not started |
| `bench.schema.json` | benchmark plans and `bench/results/*.json` | M7 | not started |
| `costs.schema.json` | `config/costs/costs.toml` (optional; may be absent) | M7 | not started |

## 3. Schemas that are owned elsewhere

These exist, or will exist, outside `config/schema/`. They are listed so that nobody adds a second
copy here.

| Schema | Path | Owner | Status |
|---|---|---|---|
| ABI 1 wire types | `abi/v1/*.schema.json` | Part II §69.5.4 | not started |
| Degradation plan | see below | Part II §61.2 | not started |
| Certificate | owned by the certificate section | Part II §68 | not started |

TODO(decision: degradation-plan schema path): Part II §61.2 places the plan schema at
`schemas/degradation-plan.schema.json`, a top-level directory that Part I §32.2 does not list and
explicitly forbids inventing. Part II overrides Part I, so the Part II path is recorded here as
stated. Resolve at M7 by either adding `schemas/` to the §32.2 tree in the same commit that creates
it, or by relocating the file to `config/schema/degradation-plan.schema.json` and correcting the
§61.2 reference. Do not create the directory before that decision is written down.

## 4. Negative requirements

- Do not omit `additionalProperties: false` anywhere, including in `$defs`.
- Do not use `"type": "number"` for a value the kernel, the checker or the perturber reads.
- Do not add a schema property without a `description`.
- Do not add a config key to a schema without adding the key to the relevant `config/` file's
  documentation in the same commit.
- Do not hand-write a model that a schema can generate.
- Do not make a schema fetchable over a network. SPECTRA is offline.
