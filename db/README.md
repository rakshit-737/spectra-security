# `db/` - the schema tree

This tree holds SQL. One file in it is real and is executed by code; the two
subdirectories are still empty skeletons with READMEs of their own.

| Path          | Status      | What it is                                          |
|---------------|-------------|-----------------------------------------------------|
| `schema.sql`  | **in use**  | DDL of the bundle index, executed by `store.py`     |
| `ddl/`        | not started | Reference snapshot of a schema. Contains no SQL     |
| `migrations/` | not started | Forward-only numbered migrations. Contains no SQL   |

## `schema.sql`

`schema.sql` declares one table, `proj_event`, and two indexes on it. It is read
at run time by `python/spectra_vs/src/spectra_vs/store.py`, which opens a SQLite
database (a file, or `:memory:`), executes this file into it, and loads the
records of one sealed `runs/<id>/bundle.jsonl`. The loader holds no second copy
of the DDL: the schema is the contract between whatever writes the rows and
whatever reads them, so there is exactly one copy of it and it is written in SQL.

What the index answers, and nothing else:

- how many records each source contributed, and the extremes of its recorded
  event time;
- the deltas between one source's consecutive records **in `seq` order**, which
  is the order the source itself recorded;
- one record, by `event_id`;
- one source's records inside a half-open time window `[t0, t1)`.

Every one of those queries carries an explicit `ORDER BY`, including the lookup
by primary key where the clause is redundant. A SQL result set has no order
unless the query declares one, and "every query here is ordered" is meant to be
checkable by reading four constants in `store.py` rather than by reasoning about
which columns happen to be unique.

### What it does not do

The index does not verify anything. It does not walk a chain, recompute an
`event_id`, compare a digest, or decide whether a bundle was tampered with.
`chain_hash` and `chain_prev` are columns because the records carry those
members, and nothing follows them. Verification of `bundle.jsonl` belongs to
`ingest.read_bundle` and to the checker; a second authority on the same question
is worse than one, because two authorities can disagree.

Nothing in the kernel path or the checker path reads this schema, and nothing in
the slice pipeline does either. `store.py` is the only module in the repository
that imports `sqlite3`.

### SQLite, not PostgreSQL - a deliberate narrowing

Part I 52.5 (milestone M2) puts the event store in PostgreSQL. Part II 75.1 item
15 reverts any service dependency on the path to a certificate, and Part II 69.13
RULE P3 forbids the kernel and the checker to link a database client at all. What
M2 wanted from a store is the capability to ask questions of an ingested run;
what it must not add is something to run. SQLite is in the Python standard
library, addresses a file or memory, and adds no process, no port and no
container.

The table is named `proj_event` because every row in it is derived from
`bundle.jsonl` and is rebuilt by re-reading that file, which is what Part II
69.14.2 requires of a projection. Of the four families Part II 69.14.1 permits
this is the projection family alone: there is no run index, no run metadata and
no entity catalog here. No table or column is named for a fact, a rule instance,
a hyperedge, a corridor, a licence, an invariant or an atom, and no column name
contains `score`, `confidence`, `probability`, `severity`, `risk` or `likelihood`
(69.14.3, 69.14.4).

### Conventions this file follows

- The table is declared `STRICT`, so a REAL reaching an INTEGER column is an
  error from the database rather than a rounded value in an index that
  everything downstream trusts. There is no float anywhere: times are integers,
  parsed by the loader from the decimal strings the wire carries.
- The table is a rowid table, **not** `WITHOUT ROWID`. That is load-bearing for
  the determinism test: a rowid table scans in insertion order when a query does
  not say otherwise, so a query that lost its `ORDER BY` answers two loads of the
  same records differently and the test catches it.
- `NULL` in `chain_hash` or `chain_prev` means the line carried no such member.
  The wire forbids a null value and spells absence by omitting a member; a column
  has no other way to say absent, and this is the only place the two spellings
  are mapped to each other.

## What is still not implemented

- No migration exists. `schema.sql` is applied by executing it into a fresh
  database, which is adequate while the only consumer builds its database from a
  bundle every time and never carries one forward. The first schema that must
  survive a change to an existing database needs `db/migrations/` to start.
- `make schema-lint`, `make rebuild-projections` and the migration tool named in
  `db/migrations/README.md` do not exist. The banned-identifier and `proj_`
  disciplines above are honoured by hand and checked by no gate.
- `db/ddl/` holds no regenerated snapshot, and nothing regenerates one.
- No PostgreSQL schema exists anywhere in this repository.

## Open conflict, unresolved

Part I 32.2 spells this tree `sql/`. The skeleton delivers `db/`, and
`store.py` now resolves `db/schema.sql` by path, so renaming the tree is a code
change and no longer only a documentation change. The conflict is recorded in
`db/migrations/README.md` and is not resolved here.
