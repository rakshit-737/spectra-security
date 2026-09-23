-- db/schema.sql - the index over one sealed bundle, read by python/spectra_vs store.py.
--
-- Owning sections: Part I 52.5 (M2: heterogeneous records become time-indexed, stable-id
-- records that can be queried); Part II 69.13 RULE P1 (truth lives on disk; every row
-- here is derivable from the bundle) and RULE P3 (the kernel and the checker never touch
-- a database); Part II 69.14.2 (a derived table is prefixed `proj_`).
--
-- WHY THIS FILE EXISTS SEPARATELY FROM THE LOADER. The schema is the contract between
-- whatever writes rows and whatever reads them, so there is exactly one copy of it and it
-- is in the language it is written in. A loader that carried its own CREATE statements
-- would let the two drift, and the drift would first be visible as a query that silently
-- answered about a column nobody had filled.
--
-- WHAT IS NARROWED RELATIVE TO THE SPECIFICATION, stated here because the departure is
-- deliberate and not an omission:
--
--   * The specification says PostgreSQL (Part I 52.5). This is SQLite, addressed as a
--     file or as `:memory:` through the standard library. Part II 75.1 item 15 reverted
--     "stable-ID events in Postgres" precisely because a service dependency on the path
--     to a certificate destroys offline verification; an in-process index over a file
--     keeps the query capability M2 asked for and adds no service to run. Nothing in the
--     kernel or the checker path reads this schema, which is what RULE P3 requires.
--   * Of the four families Part II 69.14.1 permits, this is the projection family and
--     nothing else. There is no run index, no run metadata and no entity catalog here.
--   * The tables carry no `score`, `confidence`, `probability`, `severity`, `risk` or
--     `likelihood` column, and no table or column is named for a fact, a rule instance,
--     a hyperedge, a corridor, a licence, an invariant or an atom (69.14.3, 69.14.4).
--
-- WHAT THIS SCHEMA DOES NOT ASSERT. Nothing here checks a chain, recomputes an event id,
-- or decides whether a bundle was tampered with. The columns `chain_hash` and
-- `chain_prev` are carried because the bundle carries them, not because anything here
-- follows them. Verification of a bundle is `ingest.read_bundle`'s and the checker's.

-- ---------------------------------------------------------------------------
-- The records
-- ---------------------------------------------------------------------------

-- STRICT, so that a REAL in a time column is an error raised by the database rather than
-- a rounded value sitting in an index that everything downstream trusts. SQLite would
-- otherwise accept a float in an INTEGER column and keep it as a float.
--
-- A rowid table, NOT `WITHOUT ROWID`, and the choice is load-bearing for the tests: a
-- rowid table scans in insertion order when a query does not say otherwise, so a query
-- that forgot its ORDER BY answers differently for two loads of the same records in two
-- orders. That is the failure this schema wants to stay reproducible, because it is what
-- the determinism test detects. A `WITHOUT ROWID` table would scan by primary key and
-- would hide the missing clause behind an accident of storage.
CREATE TABLE IF NOT EXISTS proj_event (
  -- The id the bundle carries. Taken as given: no grammar is imposed and no preimage is
  -- recomputed, because an index that re-derived ids would be a second minting authority.
  event_id   TEXT    NOT NULL PRIMARY KEY,
  source_id  TEXT    NOT NULL,
  -- The sequence number the source recorded. A bare JSON integer on the wire (u32).
  seq        INTEGER NOT NULL CHECK (seq >= 0),
  event_type TEXT    NOT NULL,
  -- Nanoseconds, as integers. On the wire they are decimal STRINGS, because the encoding
  -- law admits a bare JSON integer only in a u32 position; the loader parses them and
  -- this column holds the parsed value. There is no float anywhere on this axis.
  t_evt_ns   INTEGER NOT NULL CHECK (t_evt_ns >= 0),
  t_ing_ns   INTEGER NOT NULL CHECK (t_ing_ns >= 0),
  -- NULL means the member was absent from the line, which is how the wire spells "this
  -- source is not chained". The wire forbids a null VALUE; a column has no other way to
  -- say absent, so the two spellings are mapped here and nowhere else.
  chain_hash TEXT,
  chain_prev TEXT,
  -- The record's attributes, re-serialised as one JSON text with its keys sorted. Stored
  -- whole because no query here reads inside it; it is re-serialised rather than sliced
  -- out of the line, so these octets are this table's, not the bundle's, and nothing may
  -- hash them and call the result a bundle digest.
  attrs      TEXT    NOT NULL
) STRICT;

-- The two orders every query in store.py asks for. An index changes which plan SQLite
-- picks, and therefore the order rows arrive in when no ORDER BY is written; every query
-- in store.py writes one, so adding or dropping either index cannot change an answer.
CREATE INDEX IF NOT EXISTS proj_event_by_source_seq ON proj_event (source_id, seq);
CREATE INDEX IF NOT EXISTS proj_event_by_source_time ON proj_event (source_id, t_evt_ns);
