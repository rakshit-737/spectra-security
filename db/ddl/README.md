# Schema reference (DDL)

Status: **not started**. This directory contains no SQL.

Owning spec sections: Part I 19 and 32.2; Part II 69.14 (the four families that
may exist in PostgreSQL: run index, run metadata, entity catalog and `proj_`
projections), 69.13 (RULE P1: truth lives on disk, and every row is derivable
from the content-addressed store).

TODO(conflict: directory name). See `db/migrations/README.md`; Part I 32.2 spells
this tree `sql/`.

## What belongs here

The current schema as a readable reference, plus the analytic views Part I 32.2
names. It is a **snapshot, not the source of truth**: the numbered migrations in
`db/migrations/` are authoritative, and this directory is regenerated from a
migrated database.

TODO(decision: authority and regeneration). Treating migrations as authoritative
and this tree as a regenerated snapshot is this skeleton's choice; the spec lists
both directories without ranking them. The gate that regenerates the snapshot and
diffs it to zero does not exist. To change the decision, invert this paragraph
and state which artifact the gate compares against.

## Constraints on every object declared here

- Projection tables are prefixed `proj_` without exception, are written only by
  the projection builder, and are read by neither the kernel, the checker, the
  generator nor the bench harness (Part II 69.14.2).
- The banned table and column identifiers of Part II 69.14.3 and 69.14.4 apply
  here exactly as they apply to migrations.
- No object here may be required by the kernel or the checker: both are
  file-in/file-out binaries with no database (RULE P3, Part II 69.13).

## Not implemented

No schema has been authored, no view exists, and no gate checks this directory.
