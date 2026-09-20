# Database migrations

Status: **not started**. This directory contains no SQL.

Owning spec sections: Part I 19 and 32.2; Part II 69.13 (the persistence
boundary), 69.14 (what lives in PostgreSQL), 69.19 (migration policy).

TODO(conflict: directory name). Part I 32.2 spells the SQL tree `sql/` (DDL,
migrations, analytic views). This skeleton delivers `db/`. Reconcile before the
first migration is written: rename this tree to `sql/`, or record the departure
in an ADR and correct every document that quotes the Part I 32.2 tree.

## The convention

1. Migrations are **forward-only**, numbered, checked in, and applied by exactly
   one tool (Part II 69.19.1). There are no down-migrations.
2. File name: `NNNN_<snake_case_summary>.sql`, zero-padded to four digits, in
   apply order. A merged migration is never renumbered, never edited and never
   deleted; a mistake is corrected by a later migration.
   TODO(decision): the four-digit `NNNN_` naming is chosen here, not specified.
   To change it, change this section and the migration tool in one commit.
3. Every migration opens with a comment naming the owning spec section.
4. A `proj_` table is derivable from the content-addressed store, so a projection
   change is always drop, recreate, rebuild from the CAS. **Never** write a data
   backfill for a `proj_` table (Part II 69.19.1). A migration that would have to
   read the CAS to fill a non-`proj_` table is a design error (69.19.3).
5. Migrations never alter a stored object. There is no such thing as migrating a
   certificate (Part II 69.19.2).

## What a migration may not create

- Tables or columns named `fact`, `facts`, `rule_instance`, `instances`,
  `hyperedge`, `hypergraph_node`, `corridor`, `license`, `invariant`,
  `factbase`, `atom` or `blocker` (Part II 69.14.3). The fact base is never
  materialized in PostgreSQL (RULE P2, Part II 69.13).
- Any column whose name contains `score`, `confidence`, `probability`,
  `severity`, `risk` or `likelihood` (Part II 69.14.4, 75.1.6).
- Any table holding rules, thresholds or control definitions: policy lives in
  `config/` under version control (Part I 34.10).

## Not implemented

`make schema-lint`, `make rebuild-projections` and the migration tool itself do
not exist. Nothing here has been applied to any database.
