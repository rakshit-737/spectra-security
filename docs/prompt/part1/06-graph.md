============================================================
20. GRAPH ENGINE
============================================================

20.1 POSITION

Implement the graph engine as the single structural substrate that every
downstream consumer reads. It holds the reconstructed security state (section
17) as a temporal property graph. It is not a visualization layer, not a
database abstraction, and not the proof kernel.

Two distinct graphs exist in SPECTRA. Keep them separate in code, in storage,
and in naming:

  (a) STATE GRAPH — this section. Directed, multi-edge, attributed, temporally
      validity-stamped. Nodes are entities and states; edges are observed or
      derived relations. Built by ingestion + entity resolution + state
      reconstruction.

  (b) ECLIPSE HYPERGRAPH — section 18. AND/OR bipartite provenance structure
      over `FactId` / `RuleInst`. It is GENERATED from the state graph by
      grounding; it is never hand-authored and never edited by graph queries.

Requirement: the state graph exposes a projection function
`ground_facts(graph, horizon) -> Iterator[Fact]` consumed by the grounder. The
state graph must not import anything from `spectra_kernel`. Enforce with an
import-linter contract in CI (`importlinter.ini`, layer order:
`graph -> kernel` forbidden).

20.2 NODE TYPES

Every node carries: `node_id` (content-addressed, see 20.5), `kind`,
`first_seen`, `last_seen`, `attrs` (typed Pydantic model per kind),
`source_event_ids` (list of `EventId`, non-empty for observed nodes),
`derivation` (`OBSERVED` | `DERIVED` | `GHOST`).

```
kind                 key attributes                              dimension
-------------------- ------------------------------------------- -----------
Identity             principal_type{human,service,machine},       identity
                     canonical_name, realm, resolved_from[]
Credential           cred_class{password,token,key,cert,cookie},  credential
                     issuer, issued_at, expires_at, rotation_gen
Session              session_key, bound_device, bound_ip_prefix,  session
                     auth_method, mfa_satisfied, issued_at, ttl
Device               device_id, trust_state{managed,unmanaged,
                     unknown}, posture_hash                       trust
Privilege            role_or_scope, grant_path, is_admin,         privilege
                     approval_required, granted_at
Process              pid, exe_path_hash, cmdline_hash, start_ts,  process
                     parent_link, integrity_level
Host                 host_id, zone, os_family                     resource
NetworkEndpoint      addr_family, ip_prefix, port, zone,          network
                     direction{ingress,egress}
NetworkFlow          five_tuple_hash, bytes, start_ts, end_ts     network
ApiCall              api_route_id, method, status, actor_link     api
ServiceAccount       sa_id, owner_service, key_ids[]              service
Resource             resource_urn, sensitivity{low,med,high},     resource
                     owner
TrustRelation        from_realm, to_realm, mechanism{federation,
                     sso, pki, assumed_role}                      trust
StateVertex          dimension, state_label, entered_at,          (meta)
                     exited_at, entity_link
Control              control_id, level (mirrors controls.toml)    (meta)
Observation          source_id, record_hash                       (meta)
```

Rules:
- `StateVertex` is the per-dimension state-machine position of exactly one
  entity node; section 17 owns the label alphabets. The graph engine stores
  them, it does not define them.
- `Control` nodes exist only so that blocker edges can be materialized for
  visualization and for the Postgres projection; the authoritative catalog is
  `controls.toml`.
- `GHOST` nodes are created ONLY by the silent-envelope pass (section 18, step
  C), must reference a `LicenseId`, and must never appear in any count,
  aggregate, or timeline rendered as observed. Every query returns ghost nodes
  in a separate list, never merged into the observed list.

20.3 EDGE TYPES

Edges are directed and carry a temporal validity interval plus evidence.

```
edge_type             tail -> head                         evidence required
--------------------- ------------------------------------ -----------------
AUTHENTICATED_AS      Identity -> Session                   yes
PRESENTED             Credential -> Session                 yes
ISSUED_BY             Credential -> Identity                yes
BOUND_TO              Session -> Device                     yes
ASSUMED               Identity -> Identity                  yes
GRANTED               Identity -> Privilege                 yes
ESCALATED_TO          Privilege -> Privilege                yes
EXERCISED             Session -> Privilege                  yes
SPAWNED               Process -> Process                    yes
EXECUTED_BY           Process -> Identity                   yes
RAN_ON                Process -> Host                       yes
CONNECTED             Process -> NetworkEndpoint            yes
FLOW                  NetworkEndpoint -> NetworkEndpoint    yes
INVOKED               Identity -> ApiCall                   yes
TOUCHED               ApiCall -> Resource                   yes
ACCESSED              Process -> Resource                   yes
IMPERSONATED          ServiceAccount -> Identity            yes
FEDERATES             TrustRelation -> Identity             yes
TRANSITIONED          StateVertex -> StateVertex            yes
DERIVED_FROM          any -> any (resolution provenance)    yes
BLOCKED_BY            any edge-id -> Control                no (declared)
LICENSED_BY           GHOST node/edge -> License            license id
```

Edge record:

```python
@dataclass(frozen=True, slots=True)
class Edge:
    edge_id: str            # blake3 content address, see 20.5
    src: str
    dst: str
    etype: EdgeType
    valid_from: int         # microseconds since epoch, inclusive
    valid_to: int | None    # exclusive; None == open interval
    observed_at: int        # ingestion-time of the record that created it
    evidence: tuple[str, ...]   # EventId list, non-empty unless GHOST
    blockers: int           # u64 mask over threshold literals x_{k,l}
    derivation: Derivation  # OBSERVED | DERIVED | GHOST
    license_id: str | None
    attrs: Mapping[str, JsonScalar]
```

Negative requirement: no edge may be mutated after insertion and no edge may be
deleted. Expiry is expressed by closing `valid_to`, which is a WRITE-ONCE
transition from `None` to an integer, checked by an assertion. Retraction is
forbidden; this is what makes the graph compatible with the monotone kernel.

20.4 TEMPORAL VALIDITY

- All timestamps are integer microseconds UTC. No floats, no naive datetimes,
  no local time anywhere in the engine.
- Interval semantics are half-open `[valid_from, valid_to)`. Point queries use
  `valid_from <= t < valid_to`.
- An edge is TEMPORALLY VALID AT `t` iff the above holds. A PATH is temporally
  valid iff, for consecutive edges `e_i, e_{i+1}`, there exists a traversal
  time assignment `t_1 <= t_2 <= ... <= t_n` with `t_i in [e_i.valid_from,
  e_i.valid_to)`. Implement this as the standard earliest-arrival scan: carry
  `t_cur`, accept `e` iff `e.valid_to > t_cur`, then set
  `t_cur = max(t_cur, e.valid_from)`.
- `--strict-causality` (default ON) additionally requires
  `t_{i+1} >= t_i + min_gap_us` with `min_gap_us = 0` by default and
  configurable per edge type in `graph.toml`. Clock-skew tolerance is a single
  declared constant `skew_us`; paths that only validate by consuming skew are
  returned with `flags: ["skew_consumed"]` and must be rendered distinctly.
- Backdated timestamps: the Bellman-Ford difference-constraint pass of section
  18A produces `voided_intervals.json`. The graph engine must load it and mark
  affected edges `attrs.timestamp_disputed = true`. Disputed edges are excluded
  from `reachable_under_config` unless `--allow-disputed` is passed, and that
  flag is recorded in every result envelope.

ASCII, one entity's session dimension across a control change:

```
 t0        t1            t2                t3            t4
  |---------|-------------|-----------------|-------------|--->
Identity ==AUTHENTICATED_AS==> Session(S1) ==BOUND_TO==> Device(D1)
             [t1, t3)                          [t1, t3)
Session(S1) ==EXERCISED==> Privilege(admin)
                          [t2, t3)      blockers = {privilege_approval>=1}
Session(S1) ==PRESENTED<-- Credential(T7)   [t1, t3)
Credential(T7) valid_to=t3 (token expiry)  -> no edge exists at t>=t3
```

20.5 IDENTITY AND DETERMINISM

- `node_id = blake3(kind || canonical_attr_bytes)[:16].hex()`, where
  `canonical_attr_bytes` is the RFC 8785 JCS canonical JSON of the identity
  attributes declared `@identity=true` in the node model. Non-identity
  attributes never affect the id.
- `edge_id = blake3(src || dst || etype || valid_from || sorted(evidence))`.
- Graph build must be deterministic: same `bundle.jsonl` + same `graph.toml` +
  same seed produces byte-identical `graph.msgpack` and identical
  `graph_hash`. Gate: build twice in CI under different `PYTHONHASHSEED` and
  different insertion shuffles; `blake3(graph.msgpack)` must match.
- Iteration order: never iterate a Python `set` or `dict` whose order depends
  on insertion in any code path that affects output. All exported orderings are
  `sorted()` by `(valid_from, edge_id)` or `(kind, node_id)`.

20.6 STORAGE

Primary in-process store: NetworkX `MultiDiGraph`, one instance per scenario
run, built once and treated as immutable after `freeze()`.

Secondary store: a normalized PostgreSQL projection, written by the same build
step, used for cross-run analytics, the degradation matrix (section 19), UI
pagination, and anything a human wants to SQL against.

Justify and enforce these choices in `docs/adr/0012-graph-store.md`:

1. Scenario graphs are bounded (see 20.11 budgets) and fit in memory. Analysis
   is whole-graph, iterated hundreds of times per replay sweep. An in-process
   graph removes per-query network cost; measured, not assumed — publish the
   benchmark in `bench/graph_traversal.json`.
2. A server database (Neo4j and every other graph server) is FORBIDDEN as a
   dependency. Reasons to state plainly: it adds a JVM service to an offline
   Docker lab, a query language whose planner is not reproducible across
   versions, and a licensing surface. SPECTRA must run with `docker compose up`
   on a laptop with no external pull beyond pinned images.
3. Postgres is already present for runs, events, and certificates. Reuse it.
   Recursive CTEs cover the projection queries that need SQL; heavy traversal
   stays in-process.
4. Hot path traversals (k-shortest evidence paths, reachability sweeps over 256
   control configurations) are implemented in Rust behind PyO3 in crate
   `spectra-graphkern`, operating on a CSR (compressed sparse row) snapshot
   exported from NetworkX. NetworkX remains the reference implementation; the
   Rust kernel must produce identical results and is differentially tested
   against it on every fixture. Rust here exists for a measured reason —
   record the speedup in `bench/graph_traversal.json` — not for language count.

Layout:

```
graph/
  __init__.py
  model.py          # Node/Edge dataclasses + Pydantic attr models
  build.py          # bundle.jsonl -> MultiDiGraph
  freeze.py         # immutability, CSR export, graph_hash
  queries.py        # the eight query functions of 20.9
  guards.py         # explosion guards, budgets, GraphBudgetExceeded
  projection.py     # MultiDiGraph -> Postgres, idempotent
  serde.py          # msgpack + JCS canonicalization
crates/spectra-graphkern/
  src/csr.rs        # CSR snapshot
  src/yen.rs        # k-shortest under temporal + evidence constraints
  src/reach.rs      # blocker-masked reachability
  src/lib.rs        # PyO3 bindings
```

20.7 POSTGRES PROJECTION DDL

The projection is append-only and keyed by `run_id`. Never UPDATE a row except
the single write-once `valid_to` closure, performed in the same transaction as
the insert batch that discovers it.

```sql
CREATE TABLE graph_node (
  run_id        UUID        NOT NULL REFERENCES run(id) ON DELETE CASCADE,
  node_id       CHAR(32)    NOT NULL,
  kind          TEXT        NOT NULL,
  derivation    TEXT        NOT NULL
                CHECK (derivation IN ('OBSERVED','DERIVED','GHOST')),
  first_seen    BIGINT      NOT NULL,
  last_seen     BIGINT      NOT NULL,
  attrs         JSONB       NOT NULL,
  evidence      TEXT[]      NOT NULL,
  license_id    CHAR(32),
  PRIMARY KEY (run_id, node_id),
  CHECK (derivation <> 'GHOST' OR license_id IS NOT NULL),
  CHECK (derivation =  'GHOST' OR cardinality(evidence) > 0)
);

CREATE TABLE graph_edge (
  run_id        UUID        NOT NULL,
  edge_id       CHAR(32)    NOT NULL,
  src           CHAR(32)    NOT NULL,
  dst           CHAR(32)    NOT NULL,
  etype         TEXT        NOT NULL,
  validity      INT8RANGE   NOT NULL,     -- [valid_from, valid_to)
  observed_at   BIGINT      NOT NULL,
  blockers      BIGINT      NOT NULL DEFAULT 0,
  derivation    TEXT        NOT NULL,
  evidence      TEXT[]      NOT NULL,
  license_id    CHAR(32),
  attrs         JSONB       NOT NULL,
  PRIMARY KEY (run_id, edge_id),
  FOREIGN KEY (run_id, src) REFERENCES graph_node(run_id, node_id),
  FOREIGN KEY (run_id, dst) REFERENCES graph_node(run_id, node_id),
  CHECK (NOT isempty(validity)),
  CHECK (derivation <> 'GHOST' OR license_id IS NOT NULL)
);

CREATE TABLE graph_meta (
  run_id        UUID PRIMARY KEY,
  graph_hash    CHAR(64) NOT NULL,
  bundle_hash   CHAR(64) NOT NULL,
  node_count    INT NOT NULL,
  edge_count    INT NOT NULL,
  ghost_nodes   INT NOT NULL,
  ghost_edges   INT NOT NULL,
  build_ms      INT NOT NULL,
  guards_fired  JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX graph_edge_src_time ON graph_edge (run_id, src, lower(validity));
CREATE INDEX graph_edge_dst_time ON graph_edge (run_id, dst, lower(validity));
CREATE INDEX graph_edge_type     ON graph_edge (run_id, etype);
CREATE INDEX graph_edge_validity ON graph_edge USING GIST (run_id, validity);
CREATE INDEX graph_edge_blockers ON graph_edge (run_id, blockers)
  WHERE blockers <> 0;
CREATE INDEX graph_node_kind     ON graph_node (run_id, kind);
CREATE INDEX graph_node_attrs    ON graph_node USING GIN (attrs jsonb_path_ops);
```

Parity gate: `tests/test_projection_parity.py` rebuilds the graph from
Postgres alone and asserts the recomputed `graph_hash` equals `graph_meta.
graph_hash` for every fixture. A projection that loses information fails CI.

20.8 IN-PROCESS API

```python
def build_graph(bundle: Path, cfg: GraphConfig) -> Graph: ...
def freeze(g: Graph) -> FrozenGraph: ...          # CSR + hash, immutable
def csr(g: FrozenGraph) -> CsrSnapshot: ...       # handed to spectra_graphkern
```

`FrozenGraph` denies `add_node` / `add_edge` by raising `FrozenGraphError`.
All queries take `FrozenGraph` and return an envelope:

```python
class QueryResult(BaseModel):
    query: str
    params_hash: str            # blake3 of JCS(params)
    graph_hash: str
    results: list[PathOrSubgraph]
    ghost_results: list[PathOrSubgraph]   # never merged with results
    truncated: bool
    guards_fired: list[str]
    elapsed_ms: int
```

Any result with `truncated=True` must be labelled TRUNCATED in the UI and in
any export, and may never be used to support a completeness claim.

20.9 QUERY SURFACE

Exactly these eight. Do not add ad-hoc traversal helpers elsewhere in the
codebase; everything else composes these.

```python
def reconstruct_path(g, src: NodeId, dst: NodeId, *,
                     max_hops: int = 12) -> QueryResult
# Shortest edge-count path ignoring time. Diagnostic only; output is always
# tagged temporal_validated=False. Never feeds a certificate.

def temporal_paths(g, src: NodeId, dst: NodeId, *,
                   t_lo: int, t_hi: int, max_hops: int = 12,
                   strict_causality: bool = True) -> QueryResult
# Earliest-arrival scan (20.4). Returns paths with per-edge traversal times.

def k_evidence_paths(g, src: NodeId, dst: NodeId, *, k: int = 10,
                     max_hops: int = 12,
                     min_evidence_per_edge: int = 1,
                     allow_ghost: bool = False) -> QueryResult
# Yen's algorithm over the temporally-valid subgraph, cost = edge count,
# ties broken by (total_evidence_count desc, edge_id asc) for determinism.
# Every returned edge carries >= min_evidence_per_edge real EventIds unless
# allow_ghost, in which case ghost edges are returned in ghost_results only.

def reachable_under_config(g, src: NodeId, *, cut: int,
                           t_lo: int, t_hi: int) -> QueryResult
# cut is the u64 threshold-literal mask. An edge is traversable iff
# (edge.blockers & cut) == 0 and it is temporally valid. Forward BFS.
# This is the GRAPH-LEVEL view; it is NOT the proof. The authoritative
# verdict comes from the kernel fixpoint (section 18D). The two must agree
# on the goal atom for every fixture -- see gate G20.4.

def blast_radius(g, node: NodeId, *, t: int, cut: int,
                 max_depth: int = 6,
                 kinds: frozenset[str] | None = None) -> QueryResult
# Forward closure from a compromised node at time t under cut, restricted to
# reachable Resource/Privilege/Host nodes, annotated with sensitivity.
# Reports (count_by_kind, count_by_sensitivity, depth_histogram).

def provenance_subgraph(g, targets: Sequence[NodeId | EdgeId]) -> QueryResult
# Backward closure over DERIVED_FROM plus the evidence edges that produced
# each target. This is the query the certificate viewer and the UI "why?"
# affordance call. Output includes the exact EventId multiset.

def state_timeline(g, entity: NodeId, *, dimension: str) -> QueryResult
# Ordered StateVertex chain with TRANSITIONED edges; the per-dimension
# reconstruction rendered in the UI timeline.

def diff_graphs(a: FrozenGraph, b: FrozenGraph) -> GraphDiff
# Set difference over node_id/edge_id with attribute deltas. Used by the
# degradation matrix to quantify reconstruction loss at 100%..30%.
```

Semantics requirements:
- `k_evidence_paths` must be stable: running it twice on the same frozen graph
  returns byte-identical JSON. Property test with shuffled adjacency.
- `reachable_under_config` must be ANTITONE in `cut`: adding a control never
  enlarges the reachable set. Property test over 256 random masks per fixture.
- No query may write to the graph, the database, or any global cache keyed by
  anything other than `(graph_hash, query, params_hash)`.

20.10 INDEXING (in-process)

Build these at `freeze()` time, store them in the CSR snapshot, document their
memory cost in `graph_meta`:

```
by_kind:        dict[kind, np.ndarray[node_idx]]
out_csr:        (indptr, indices, edge_idx)      sorted by (src, valid_from)
in_csr:         (indptr, indices, edge_idx)      sorted by (dst, valid_from)
valid_from_arr: np.int64[E]   # enables bisect for time-windowed adjacency
valid_to_arr:   np.int64[E]
blockers_arr:   np.uint64[E]
evidence_off:   (indptr, EventId table)          # CSR over evidence lists
entity_index:   dict[(kind, canonical_name), node_idx]
```

Time-windowed adjacency is `bisect_left(valid_from_arr[slice], t_lo)` inside a
per-source contiguous block; do not scan all edges of a source. Reachability
sweeps over many cuts reuse one CSR and a reusable `visited` bitset; allocate
once per sweep, not per configuration.

20.11 GRAPH EXPLOSION GUARDS

Declare budgets in `graph.toml`; load them into a `Budgets` dataclass; check
them at build time and inside every query loop.

```toml
[budgets]
max_nodes            = 250_000
max_edges            = 2_000_000
max_out_degree       = 5_000       # per (node, etype)
max_path_hops        = 12
max_paths_enumerated = 10_000
max_blast_depth      = 6
max_query_ms         = 5_000
max_ghost_fraction   = 0.25        # ghost edges / total edges
max_flow_fanout      = 1_000       # NetworkFlow per Process per minute
```

Guard behaviour, in order of preference:

1. AGGREGATE rather than truncate where the aggregation is exact. Network flows
   to the same `(zone, port, direction)` within a bucket collapse into one edge
   with `attrs.flow_count`, `attrs.bytes_total`, and the full `evidence` list
   retained. This is lossless for reachability and is the primary defence
   against network fan-out.
2. CAP with an explicit flag. When a cap binds, set the corresponding entry in
   `guards_fired` (`{"guard":"max_paths_enumerated","at":10000,
   "query":"k_evidence_paths"}`), set `truncated=true`, and propagate the flag
   into any artifact derived from the result. A run whose graph build fired a
   cap must set `grounding_capped` in the ECLIPSE certificate flags, and a
   flagged run may never be presented as ROBUST (section 18.9).
3. FAIL LOUDLY. `max_nodes` / `max_edges` raise `GraphBudgetExceeded` with the
   offending counts. There is no silent degradation path.

Additional structural guards:
- Cycle handling: the state graph may contain cycles (`ASSUMED` chains,
  process trees with re-parenting). All traversals carry a visited set keyed by
  `(node_idx, bucketed_time)`; no unbounded revisiting.
- Hub suppression is FORBIDDEN as a silent default. If a hub node (degree >
  `max_out_degree`) is encountered, aggregate per rule 1 or report the cap; do
  not drop edges to make pictures prettier.
- `max_ghost_fraction` exceeded means the telemetry is too sparse to
  reconstruct; emit `RECONSTRUCTION_INSUFFICIENT` and refuse to produce a
  hypothesis, rather than emitting a confident-looking sparse graph.

20.12 COMPLEXITY AND PUBLISHED SIZES

State the asymptotics in `docs/graph.md` and publish MEASURED sizes per fixture
in `bench/graph_sizes.json` — never claim a size you did not measure.

```
operation                     complexity                  budgeted bound
----------------------------- --------------------------- ---------------
build                         O(E log E)                  E <= 2e6
freeze / CSR                  O(V + E)                    -
temporal_paths                O(V + E) per target         hops <= 12
k_evidence_paths (Yen)        O(k * hops * (V + E log V)) k <= 10
reachable_under_config        O(V + E) per cut            256 cuts/sweep
blast_radius                  O(V + E) bounded by depth   depth <= 6
provenance_subgraph           O(|closure|)                -
diff_graphs                   O(V_a + V_b + E_a + E_b)    -
```

Expected fixture scale (assert these ranges in tests so drift is caught):
small `lab-01` ~2e3 nodes / 9e3 edges; medium `lab-07` ~4e4 / 3e5; large
`lab-12` ~2e5 / 1.6e6. Build time budget: medium fixture under 8 s, whole-graph
reachability sweep of 256 cuts under 3 s on the reference container. If a
budget is exceeded, CI fails with the measured number printed.

20.13 SERIALIZATION

- `graph.msgpack`: canonical, sorted, the hashed artifact. `graph_hash =
  blake3(graph.msgpack)` and it enters the ECLIPSE certificate hash set.
- `graph.jsonl`: human-diffable export, one record per line, `node` records
  before `edge` records, both sorted. Used in golden tests.
- Never serialize Python objects with `pickle`. Never embed absolute paths,
  hostnames, timestamps-of-run, or usernames in a hashed artifact.

20.14 HTTP SURFACE

| Method | Path                                    | Returns                       |
|--------|-----------------------------------------|-------------------------------|
| GET    | /api/v1/runs/{run_id}/graph/meta        | graph_meta row                |
| GET    | /api/v1/runs/{run_id}/graph/nodes       | paged nodes, filter kind/time |
| GET    | /api/v1/runs/{run_id}/graph/edges       | paged edges, filter type/time |
| POST   | /api/v1/runs/{run_id}/graph/paths       | k_evidence_paths              |
| POST   | /api/v1/runs/{run_id}/graph/temporal    | temporal_paths                |
| POST   | /api/v1/runs/{run_id}/graph/reachable   | reachable_under_config        |
| POST   | /api/v1/runs/{run_id}/graph/blast       | blast_radius                  |
| POST   | /api/v1/runs/{run_id}/graph/provenance  | provenance_subgraph           |
| GET    | /api/v1/runs/{run_id}/graph/timeline    | state_timeline                |
| GET    | /api/v1/runs/{a}/graph/diff/{b}         | diff_graphs                   |

Every response body embeds `graph_hash`, `guards_fired`, `truncated`. Paged
endpoints use keyset pagination on `(kind, node_id)` / `(etype, edge_id)`;
never OFFSET.

20.15 CLI

```
$ spectra graph build --bundle runs/lab-07/bundle.jsonl --out runs/lab-07/
graph: 41,882 nodes  312,405 edges  (ghost: 0 nodes, 0 edges)
aggregated: 118,402 NetworkFlow edges -> 9,110 bucketed edges (lossless)
guards fired: none
graph_hash blake3:7c41a9d2...  build 6.41s  peak_rss 812MB

$ spectra graph query paths --run lab-07 \
    --src Identity:svc-billing --dst Resource:urn:db:payments-prod \
    --k 5 --window 2024-03-11T02:00Z/2024-03-11T06:00Z
5 temporally-valid evidence-supported paths (0 ghost, truncated=false)
#1 hops=4  evidence=17
   Identity:svc-billing -AUTHENTICATED_AS[t=02:11:04]-> Session:9f2a
   Session:9f2a -EXERCISED[t=02:11:52]-> Privilege:db.read_all
   Privilege:db.read_all -TOUCHED[t=02:12:30]-> ApiCall:/v1/export
   ApiCall:/v1/export -TOUCHED[t=02:12:31]-> Resource:urn:db:payments-prod
   blockers on path: {session_binding>=1, egress_seg>=1}
```

20.16 GATES

- G20.1 Determinism: two builds, different hash seeds and insertion orders,
  identical `graph_hash`.
- G20.2 Projection parity: Postgres round-trip reproduces `graph_hash`.
- G20.3 Rust/NetworkX differential: `k_evidence_paths` and
  `reachable_under_config` identical on all fixtures, 500 randomized queries.
- G20.4 Graph/kernel agreement: for 256 random cuts per fixture,
  `reachable_under_config` agrees with the kernel fixpoint on goal
  reachability. Disagreement is a build failure, not a warning.
- G20.5 Antitonicity of reachability in the cut.
- G20.6 Immutability: mutating a `FrozenGraph` raises; no test may bypass it.
- G20.7 Ghost isolation: no observed count, timeline, or metric anywhere in the
  codebase includes a GHOST node or edge. Enforced by a test that injects a
  sentinel ghost into every fixture and asserts all published counters are
  unchanged.

20.17 NEGATIVE REQUIREMENTS

- Do NOT add Neo4j, TigerGraph, ArangoDB, JanusGraph, a Gremlin server, or any
  other graph database service. Do not add an embedded graph DB either.
- Do NOT implement a query DSL or a Cypher-alike parser.
- Do NOT compute or display PageRank, centrality, community detection, or
  "criticality scores" as security findings. Centrality is not evidence. If a
  layout algorithm needs a weight, it is a layout parameter, lives in the
  frontend, and is never surfaced as a security number.
- Do NOT infer edges by heuristic proximity ("same user, same minute, probably
  related"). Every non-GHOST edge traces to explicit evidence via a declared
  resolution rule (section 16).
- Do NOT let a graph query mutate state, emit a verdict, or bypass the kernel.
- Do NOT silently cap, sample, prune, or "simplify" a graph.

============================================================
21. ML BASELINE (OPTIONAL, SCOPED) AND BOUNDED LLM ROLE
============================================================

21.1 THE ONLY PERMITTED ROLE FOR ML

ML in SPECTRA exists for exactly one purpose: to provide a COMPARISON BASELINE
for anomaly detection, so the deterministic reconstruction can be evaluated
against the conventional approach on the same data. It is a research control
arm. It is not a detector, not a scorer, not a ranker of findings, and not an
input to anything.

Hard placement rule:

```
  bundle.jsonl
        |
        +--> [ entity resolution ] --> [ state reconstruction ] --> STATE GRAPH
        |                                                              |
        |                                                              v
        |                                                    [ ECLIPSE KERNEL ]
        |                                                              |
        |                                                              v
        |                                                    CERTIFICATE (verdict)
        |
        +--> [ feature extraction ] --> [ ML BASELINE ] --> baseline_scores.json
                                                                       |
                                                                       v
                                                        EVALUATION REPORT ONLY
                                                        (side-by-side comparison)

  There is NO arrow from ML back into reconstruction, grounding, licensing,
  cut selection, replay, or the certificate. Enforce with an import-linter
  contract: `spectra_ml` may not be imported by `spectra_kernel`,
  `spectra_graph`, `spectra_ingest`, `spectra_replay`, or `spectra_api`
  outside `spectra_api.routers.baseline`.
```

Gate G21.0: delete the entire `ml/` directory and the full test suite still
passes except the tests under `tests/ml/`. CI runs this as a job named
`no-ml-build` on every push. Same job with `ml/` and `llm/` both deleted.

21.2 FEATURE EXTRACTION

Features are computed by deterministic code from the SAME artifacts the
deterministic path uses, so the comparison is honest.

- Unit of prediction: one `(entity, time_window)` pair. Windows are fixed at
  60 s, non-overlapping, closed intervals, derived from the scenario clock, not
  from wall time.
- Feature spec lives in `ml/features/spec_v1.yaml` and is hashed; the hash goes
  into every prediction record. Changing a feature requires a new spec version;
  specs are never edited in place.

```yaml
# ml/features/spec_v1.yaml
version: 1
window_seconds: 60
entity_kinds: [Identity, ServiceAccount, Process]
features:
  - name: auth_failures
    source: events
    agg: count
    filter: {event_type: auth, outcome: failure}
  - name: auth_success
    source: events
    agg: count
    filter: {event_type: auth, outcome: success}
  - name: distinct_src_prefixes
    source: events
    agg: distinct_count
    field: src_ip_prefix
  - name: distinct_resources_touched
    source: graph
    agg: distinct_count
    field: TOUCHED.dst
  - name: privilege_delta
    source: graph
    agg: signed_delta
    field: granted_privilege_rank
  - name: new_device_flag
    source: graph
    agg: bool_first_seen
    field: BOUND_TO.dst
  - name: egress_bytes_log1p
    source: events
    agg: log1p_sum
    field: flow.bytes_out
  - name: interarrival_p50_ms
    source: events
    agg: percentile
    p: 50
    field: delta_t_ms
  - name: hour_of_day_sin
    source: clock
    agg: cyclic_sin
    period: 86400
  - name: session_count_open
    source: graph
    agg: gauge
    field: open_sessions
forbidden_fields:          # leakage blocklist, enforced at extraction time
  - scenario_label
  - attack_phase
  - ground_truth_*
  - generator_seed
  - injected_*
```

Requirements:
- Extraction must be pure: `extract(bundle, graph, spec) -> pa.Table` with no
  network, no clock, no randomness. Same inputs, byte-identical Parquet.
- No feature may be computed from information not available at the window's end
  timestamp. A look-ahead linter walks every aggregation and asserts its source
  records satisfy `ts <= window_end`. Violations fail the build.
- Any field whose name matches `forbidden_fields` is rejected at extraction
  time with `LeakageError`, not filtered silently.
- Features are stored as `ml/data/{fixture}/features_v1.parquet` alongside a
  `features_v1.sha256`.

21.3 CANDIDATE MODELS

Implement exactly these four, no more. Each is a separate module with the same
interface.

```python
class BaselineModel(Protocol):
    name: str
    version: str                       # semver, bumped on any change
    def fit(self, X: pa.Table, y: np.ndarray | None, seed: int) -> None: ...
    def score(self, X: pa.Table) -> np.ndarray: ...   # higher = more anomalous
    def card(self) -> ModelCard: ...
```

| id          | model                | supervision  | library / pinned          |
|-------------|----------------------|--------------|---------------------------|
| `iforest`   | Isolation Forest     | unsupervised | scikit-learn (pinned)     |
| `logreg`    | Logistic regression  | supervised   | scikit-learn (pinned)     |
| `gbdt`      | Gradient boosting    | supervised   | LightGBM (pinned)         |
| `gru`       | 1-layer GRU, hid=64  | supervised   | PyTorch CPU (pinned)      |

- `gru` consumes the per-entity window sequence, max length 64, left-padded,
  masked. A 2-layer, 2-head transformer encoder of the same width is permitted
  as an alternative under id `tfm`; implement at most one of `gru` / `tfm` and
  say which in the model card. Do not add a third sequence model.
- No model exceeds 2 M parameters. No pretrained weights. No downloads at
  train or inference time; CI runs with the network disabled.
- CPU only. Training the full suite on the largest fixture must complete in
  under 15 minutes on the reference container; publish the measured time.
- Supervised labels come ONLY from the generator's ground truth
  (`ground_truth.jsonl`, section 15), are used ONLY for training and
  evaluation, and never enter feature extraction.

21.4 SPLIT DISCIPLINE — NO LEAKAGE

Splitting is by SCENARIO, then by TIME, in that order. Never by random row.

```
scenarios (24 generated families, seeds 1000..1023)
  |
  +-- train : families f00..f13   (seeds 1000..1013)
  +-- val   : families f14..f18   (seeds 1014..1018)
  +-- test  : families f19..f23   (seeds 1019..1023)

Within each split, an additional temporal cut is applied per scenario:
  train uses [t0, t0+0.7T), val [t0+0.7T, t0+0.85T), test [t0+0.85T, t0+T)
only for the sequence model's context windows; the family-level split is
authoritative and no entity appears in two splits.
```

Enforced invariants (tests, not comments):
- `assert set(train.entity_id) & set(test.entity_id) == set()`
- `assert max(train.window_end) <= min(test.window_start)` per scenario
- Scalers, imputers, encoders, class weights, and any quantile computed for
  features are fit on TRAIN ONLY and applied to val/test. A
  `sklearn.Pipeline` is mandatory; manual pre-scaling of a full dataframe is
  forbidden and caught by a test that shuffles the split and asserts scores
  change.
- Hyperparameters are selected on VAL. The TEST split is scored exactly once
  per model version; the run is recorded in `ml/runs/{model}-{version}.json`
  with the number of prior test evaluations. Re-scoring test to improve a
  number is prohibited; the counter makes it visible.
- The degradation matrix (section 19) is a SEPARATE evaluation axis. Models are
  trained at 100% completeness only, then evaluated at 100%..30%. Never train
  on the degraded copy of a scenario whose full copy is in test.
- Seeds: `PYTHONHASHSEED=0`, `numpy` seed, `torch.manual_seed`,
  `torch.use_deterministic_algorithms(True)`, LightGBM `deterministic=true,
  force_row_wise=true`, single-threaded where determinism requires it. Gate:
  two training runs produce identical model bytes and identical test scores.

21.5 CALIBRATION

- Supervised models emit calibrated probabilities via isotonic regression fit
  on VAL only. The calibration status of every output is one of
  `CALIBRATED_ISOTONIC`, `CALIBRATED_PLATT`, `UNCALIBRATED`.
- `iforest` outputs an unbounded anomaly score. It is reported as
  `UNCALIBRATED` and rendered as a rank, never as a percentage or a
  probability. Do not min-max it into a fake 0-100 "risk score".
- Report Brier score and a 10-bin reliability diagram for every calibrated
  model, in `reports/ml/reliability_{model}.svg`, generated from real test
  predictions.

21.6 MODEL CARD

Every trained model ships a card at `ml/cards/{model}-{version}.yaml`, written
by the training run, not by hand. Missing or stale card = no model load.

```yaml
model_id: gbdt
version: 0.3.1
task: anomaly_detection_baseline
intended_use: >
  Comparison arm for evaluating SPECTRA's deterministic reconstruction.
  Not a detector. Outputs must not be used to trigger, rank, or justify any
  security conclusion.
out_of_scope_use:
  - production detection
  - feeding the ECLIPSE kernel or any certificate
  - ranking findings shown to an analyst as if they were evidence
training_data:
  fixtures: [f00..f13]
  seeds: [1000..1013]
  rows: 184213
  positive_rate: 0.0412
  feature_spec: spec_v1
  feature_spec_sha256: 9a1c...
  completeness: 1.0
splits: {train: f00-f13, val: f14-f18, test: f19-f23}
hyperparameters: {num_leaves: 31, learning_rate: 0.05, n_estimators: 300,
                  deterministic: true, force_row_wise: true}
seeds: {python: 0, numpy: 1337, lightgbm: 1337}
metrics_test:
  pr_auc: 0.71
  roc_auc: 0.93
  recall_at_fpr_0.01: 0.38
  brier: 0.041
  n_test_rows: 62110
  ci_method: bootstrap_2000_percentile
  pr_auc_ci95: [0.67, 0.75]
calibration: CALIBRATED_ISOTONIC
degradation_curve: reports/ml/gbdt_degradation.csv
train_seconds: 214
environment: {image: spectra/ml@sha256:..., cpu_only: true, threads: 1}
known_limitations:
  - Synthetic telemetry only; no claim of transfer to real environments.
  - Labels come from the generator; the generator's biases are the model's.
  - Windows are 60s; slower campaigns are attenuated by construction.
test_evaluations_count: 1
```

21.7 OUTPUT ENVELOPE

Every ML output anywhere in SPECTRA — API, file, UI, log — is this object.
There is no shorter form.

```json
{
  "$schema": "spectra/ml-prediction-v1.json",
  "model_id": "gbdt",
  "model_version": "0.3.1",
  "model_sha256": "4b2e...",
  "feature_spec": "spec_v1",
  "feature_spec_sha256": "9a1c...",
  "entity_id": "Identity:svc-billing",
  "window": {"start_us": 1710122400000000, "end_us": 1710122460000000},
  "feature_vector": {
    "auth_failures": 0, "auth_success": 3, "distinct_src_prefixes": 2,
    "distinct_resources_touched": 11, "privilege_delta": 1,
    "new_device_flag": 1, "egress_bytes_log1p": 14.2,
    "interarrival_p50_ms": 840, "hour_of_day_sin": -0.71,
    "session_count_open": 2
  },
  "score": 0.8312,
  "score_semantics": "calibrated_probability_of_generator_labelled_attack_window",
  "calibration": "CALIBRATED_ISOTONIC",
  "rank_in_run": 4,
  "threshold_used": null,
  "is_baseline_only": true,
  "not_evidence": true
}
```

Rules:
- `feature_vector` is always the full vector, never a subset, never a
  "top contributing features" summary invented at render time.
- If an explanation is shown, it must be a real computed attribution
  (permutation importance on the test split, or exact tree SHAP for `gbdt`)
  with its method named in the payload. Never narrate a made-up reason.
- `is_baseline_only` and `not_evidence` are constants that must be present; a
  schema test asserts they exist and are `true` in every emitted record.

21.8 UI AND REPORTING RULES

- ML results live on a single page titled "Baseline comparison". They never
  appear on the reconstruction view, the replay view, the certificate view, or
  any alert surface.
- Forbidden labels anywhere in the product: "AI risk score", "risk score",
  "threat score", "confidence", "severity" derived from a model, coloured
  gauges, 0-100 dials, letter grades. A lint rule (`scripts/lint_forbidden_
  strings.sh`, run in CI) greps the frontend and backend for these strings.
- The comparison table is generated from real runs:

```
model     pr_auc  roc_auc  rec@fpr1%  brier   calib      100%   70%    40%
--------- ------- -------- ---------- ------- ---------- ------ ------ ------
iforest   0.31    0.78     0.09       n/a     UNCALIB    0.31   0.27   0.19
logreg    0.55    0.88     0.21       0.062   ISOTONIC   0.55   0.48   0.33
gbdt      0.71    0.93     0.38       0.041   ISOTONIC   0.71   0.61   0.41
gru       0.68    0.92     0.35       0.047   ISOTONIC   0.68   0.55   0.30
SPECTRA   n/a     n/a      n/a        n/a     N/A        deterministic:
  reported as (attack chains reconstructed / total, mean corridors recovered,
  false-ROBUST count = 0) -- NOT as an AUC, because it is not a scorer.
```

  Do not manufacture an AUC for the deterministic core to make the table
  symmetric. State in the report that the two arms answer different questions
  and that the comparison is about what each recovers, not about a shared
  metric.
- Statistical reporting (bootstrap CIs, DeLong tests for ROC comparison,
  reliability diagrams) is implemented in R under `analysis/R/eval.R`, run
  offline in the `spectra/analysis` image and never in the serving path. The R
  script consumes only `predictions.parquet` and emits CSV + SVG.

21.9 ML GATES

- G21.1 No-ML build passes (21.1).
- G21.2 Leakage tests: entity disjointness, temporal ordering, forbidden-field
  rejection, look-ahead linter.
- G21.3 Training determinism: identical model bytes across two runs.
- G21.4 Card presence and freshness: `model_sha256` in the card equals the
  artifact's hash, else loading raises.
- G21.5 Envelope schema: every emitted prediction validates against
  `ml-prediction-v1.json`.
- G21.6 Isolation: import-linter contract; plus a runtime test that monkey-
  patches `spectra_ml` to raise on import and runs the full deterministic
  pipeline successfully.
- G21.7 Forbidden-string lint.

21.10 LLM ROLE — STRICTLY BOUNDED

The LLM narrates. It does not decide, detect, rank, infer, or fill gaps.

Permitted inputs: ONLY already-computed deterministic structures — the
certificate JSON, the cut, the corridor list, the counterexample derivation
trees, the license list, the blindness premium, the state timeline, the
provenance subgraph, the degradation table.

Permitted output: prose that restates those structures in readable English,
plus nothing else.

```toml
# config/llm.toml
[llm]
enabled          = false          # DEFAULT. Never true in CI, never in tests.
provider         = "ollama"       # local only; no hosted APIs, no keys
endpoint         = "http://ollama:11434"
model            = "llama3.1:8b-instruct-q4_K_M"
temperature      = 0.0
seed             = 7
max_output_chars = 4000
timeout_seconds  = 30
cache            = true           # keyed by blake3(canonical input JSON)
```

Requirements:
1. Feature-flagged off by default. The whole test suite, all gates, and the
   60-second demo must pass with `enabled = false`. Gate G21.8 runs the full
   suite with the `llm` package deleted from the image.
2. No network beyond the local Ollama container in the compose network. No API
   keys anywhere in the repo, the env files, or the docs. No paid provider.
3. The narrator receives a rendered, closed input document and a system prompt
   that forbids new facts. Implement a post-generation VALIDATOR that rejects
   the narration when it:
   - contains a number, EventId, control id, timestamp, or entity name not
     present in the input document (exact string membership check against an
     extracted token set);
   - contains any of the words `likely`, `probably`, `confidence`, `risk score`,
     `suggests that`, `we believe`, `appears to be`, `could indicate`;
   - asserts a verdict other than the exact `mode` field in the certificate;
   - exceeds `max_output_chars`.
   On rejection, retry once at the same seed; on second rejection, fall back to
   the deterministic template renderer and record `narration:
   template_fallback` in the run log.
4. A deterministic template renderer (Jinja2, `llm/templates/*.j2`) produces
   the same narrative content without any model. It is the default path. The
   LLM path is an optional upgrade in phrasing only.
5. Every narration is persisted with `{llm_enabled, provider, model, digest,
   temperature, seed, input_hash, output_hash, validator_result}` and is
   rendered in the UI inside a panel labelled "Generated narration — derived
   from the certificate above; not evidence." The certificate itself is always
   displayed next to it.
6. Narration is never an input to anything. No agentic loop, no tool calling,
   no self-critique, no LLM-written rules, no LLM-proposed controls, no
   LLM-chosen cuts. The LLM never reads `bundle.jsonl`, never sees raw
   telemetry, and never runs during ingestion, reconstruction, grounding,
   solving, or verification.

Example, showing the only acceptable shape of output:

```
INPUT (deterministic, hashed): cert.json  mode=ROBUST
  cut = [session_binding>=1, egress_seg>=1]
  corridors = 6   lower_bound = 2   licenses_used = [iam_audit@[t1,t2]]
  blindness_premium = [credential_rotation>=1]

NARRATION (llm enabled, validated):
"The minimum cut for this scenario contains two controls: session binding at
level 1 and egress segmentation at level 1. Six irreducible corridors were
enumerated, and no cut of size one satisfies the corridor clause set, so the
lower bound of two is attained. One control, credential rotation at level 1,
is present only in the robust cut; it is required because the iam_audit source
was blind between t1 and t2, which licenses unobserved steps in that window."
```

21.11 NEGATIVE REQUIREMENTS

- Do NOT let any ML output influence reconstruction, the rule table, licensing,
  cut computation, replay, the certificate, or what the UI calls a finding.
- Do NOT emit an "AI risk score", a 0-100 risk dial, a letter grade, a
  severity derived from a model, or any score without model version, feature
  vector, and calibration status attached.
- Do NOT min-max, sigmoid, or otherwise cosmetically rescale an uncalibrated
  score to look like a probability.
- Do NOT train on test data, tune on test data, or re-evaluate test to improve
  a reported number.
- Do NOT report an ML metric that was not produced by running the pinned code
  on the pinned fixtures in the pinned container.
- Do NOT use an LLM to write rules, classify events, resolve entities, choose
  controls, summarize raw telemetry, or decide anything.
- Do NOT add a hosted model provider, an API key, a vector database, a RAG
  pipeline, or an agent framework.
- Do NOT claim SPECTRA "uses AI". State exactly what is used: a deterministic
  proof kernel, plus an optional, off-by-default local narrator, plus an
  optional offline ML comparison arm.
