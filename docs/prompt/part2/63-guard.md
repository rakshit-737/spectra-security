============================================================
63. THE GUARD LANGUAGE: GRAMMAR, TYPE SYSTEM AND COMPILER
============================================================

63.0 POSITION AND SCOPE

Part I (sections 22 and 25) and the ECLIPSE spec (§1, §2, §3, §4D) treat "the guard AST" as a
primitive. It is not a primitive. It is the single most load-bearing artifact in the repository:
it decides which rule instances exist, which are blocked under a cut, what the concrete simulator
enforces, what the Go checker re-derives, and what `hashes.rules` in every certificate commits to.
This section specifies it completely. Nothing else in SPECTRA may define, extend, or reinterpret
guard semantics.

OVERRIDES Part I: the guard expression language is named SGL (SPECTRA Guard Language), it is a
first-class specified artifact with its own compiler binary `sglc`, its own canonical binary
encoding `.sglb`, and its own hash `guard_ast_hash`. Any Part I text that implies guards are
"expressions in rules.toml compiled to Rust" is superseded by 63.1–63.14.

OVERRIDES Part I / ECLIPSE §1: the concrete simulator is NOT generated from the guard AST. Only
the kernel's guard evaluator is generated. See 63.10 and 63.13, and the oracle protocol in §62.

63.1 DESIGN CONSTRAINTS (non-negotiable)

1. **Two sorts, not one.** SGL has two disjoint expression sorts: the DATA sort (`when`), a
   Boolean predicate over bound fact variables evaluated at grounding time, and the CONTROL sort
   (`blocked_when`), a positive monotone formula over threshold literals only. They cannot mix.
   A data expression may not mention `ctl.`; a control expression may not mention a variable, a
   literal, an arithmetic operator, or `not`.
   OVERRIDES Part I sections 22.3, 22.5 and 22.6: the single gate field `admit_when`, an antitone
   formula in which control literals may appear only negated, is replaced by `blocked_when`, a
   positive monotone formula, alongside the separate data field `when`. The polarity is inverted:
   Part I states the condition under which a gated transition is still permitted, this section
   states the condition under which the instance is blocked. An implementer following Part I
   authors every control gate on the admit side, is rejected on the `not` (E-SYN-009), and
   silently turns permit into block if the negations are stripped mechanically; the `admit_when`
   key required by 22.5's schema and the `dnf_mask_equivalence` property test of 22.7 have no
   counterpart here and must be restated against `blocked_when`.
2. **Monotone by construction.** The CONTROL sort has no negation, no equality, no `<`, and no
   level predicate other than `ctl.X >= LEVEL`. `ctl.X == 2`, `ctl.X < 3`, `ctl.X != 0` and
   `not (ctl.X >= 2)` are parse errors, not lint warnings.
   OVERRIDES Part I: the integrity critic's "guard-AST linter that rejects non-threshold level
   predicates" is upgraded from a lint to a grammar-level impossibility. The antitonicity that
   ECLIPSE §4E's two-fixpoint shortcut depends on is unconstructible-to-violate, not tested-for.
3. **No floats.** There is no float type, no float literal, no float operator, no rounding and no
   division anywhere in SGL. A `.` followed by a digit is a lexical error (E-LEX-004).
4. **Total functions only.** Every operator and every builtin is defined on every value of its
   argument types. There is no partiality, no `null`, no option type, no absence test, no
   exception, no panic, and no error value. Evaluation cannot fail.
5. **Terminating by construction.** No recursion, no loops, no user-defined functions, no
   quantifiers, no collections other than literal symbol sets. Every expression is a finite tree;
   evaluation cost is bounded by node count.
6. **Deterministic.** Evaluation has no dependence on iteration order, hashing, locale, timezone,
   wall clock, or allocation. Required by the determinism charter (Part II).

63.2 LEXICAL STRUCTURE

```
ident       = lower , { lower | digit | "_" } ;          (* snake_case only *)
lower       = "a".."z" ;
digit       = "0".."9" ;
int_lit     = digit , { digit | "_" } ;                  (* base 10 only, no sign *)
dur_lit     = int_lit , ( "ns" | "us" | "ms" | "s" | "m" | "h" | "tick" ) ;
sym_lit     = "#" , ident ;
bool_lit    = "true" | "false" ;
```

Reserved (may never be an `ident`):
`and or not in true false ctl min max abs within overlaps distinct`

OVERRIDES Part I section 22.3: the control-reference keyword `ctrl.` is replaced by `ctl.`;
`ctrl` is not reserved in SGL and no guard spelled that way compiles. An implementer following
Part I authors the whole control catalog against `ctrl.`, and every such reference lexes as an
ordinary identifier and then fails as an unknown field path (E-TYP-014).

SGL has **no comments and no string literals**. Rationale for comments: a guard is a TOML string;
prose belongs in the sibling `note` field, which is not hashed into `guard_ast_hash` (63.7), so
commentary can be edited without invalidating certificates. Rationale for strings: every
symbolic value is a `sym_lit` drawn from a closed domain declared in the fact schema, so the
compiler can reject typos (E-TYP-011) instead of deferring them to runtime.

Whitespace is a separator only. Source encoding is UTF-8, NFC, LF-only; a CR byte anywhere in a
guard is E-LEX-001 (this is what keeps a Windows working copy and Linux CI byte-identical).

63.3 GRAMMAR (EBNF, normative)

DATA sort:

```
when_expr   = or_expr ;
or_expr     = and_expr , { "or" , and_expr } ;
and_expr    = unary_expr , { "and" , unary_expr } ;
unary_expr  = "not" , unary_expr | rel_expr ;
rel_expr    = add_expr , [ rel_tail ] ;
rel_tail    = ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) , add_expr
            | "in" , set_lit ;
add_expr    = mul_expr , { ( "+" | "-" ) , mul_expr } ;
mul_expr    = primary , [ "*" , int_lit ] ;              (* literal multiplier only *)
primary     = "(" , when_expr , ")" | call | path | literal ;
call        = builtin , "(" , when_expr , { "," , when_expr } , ")" ;
builtin     = "min" | "max" | "abs" | "within" | "overlaps" | "distinct" ;
path        = ident , { "." , ident } ;                  (* depth <= 3 *)
literal     = dur_lit | int_lit | sym_lit | bool_lit ;
set_lit     = "{" , sym_lit , { "," , sym_lit } , "}" ;  (* 1..=32 members *)
```

OVERRIDES Part I sections 22.3 and 25.4: the single `guard` field carrying one formula that mixes
control and state predicates is replaced by two disjoint sorts in two fields, and Part I's state
constructs are removed — there is no `has(path)`, no prefix `in(path, list)` form, no string
literal, no user-defined predicate such as `ctx_matches_bind`, and no unbounded `Path`; `in` is an
infix operator over a symbol-set literal, the builtins are exactly those listed above, and path
depth is capped by the structural caps of this section. An implementer following Part I's worked
rule `r_session_replay` writes a guard that does not parse, on the mixed sorts, on the negated
control literal and on the call to a predicate SGL gives no way to declare.

CONTROL sort:

```
block_expr  = b_or ;
b_or        = b_and , { "or" , b_and } ;
b_and       = b_atom , { "and" , b_atom } ;
b_atom      = threshold | "(" , block_expr , ")" ;
threshold   = "ctl" , "." , ident , ">=" , ident ;       (* level by NAME, never by number *)
```

OVERRIDES Part I section 22.3: the threshold production whose right operand may be an integer
(`Int | LevelName`) is replaced by one whose right operand must be the level's declared symbolic
name. An implementer following Part I writes the level as the index defined in 22.2 and used in
the atom names of 23.4, 24.7 and 25.7, and every such guard is E-SYN-012 (63.11) rather than a
build; the name-to-index direction exists only in the atom record of 63.7.

Precedence, loosest to tightest: `or` < `and` < `not` < rel_ops (non-associative, at most one per
`rel_expr`) < `+ -` (left) < `*` (left, literal RHS) < unary application. `a < b < c` is
E-SYN-006, not an accident waiting to happen.

Hard structural caps, enforced by `sglc` (violations are build failures, not truncations):
node depth <= 24, nodes per guard <= 256, `and`/`or` arity after flattening <= 32, set members
<= 32, path depth <= 3, DNF terms per control guard <= 8 (63.6, rule C7).

63.4 TYPE SYSTEM

Types:

| Type       | Values                                   | Eq | Ord | Arith | Notes |
|------------|------------------------------------------|----|-----|-------|-------|
| `Bool`     | true, false                              | y  | n   | n     | result type of `when` |
| `Int`      | i64                                      | y  | y   | y     | saturating (63.5) |
| `Tick`     | i64, index in the declared tick lattice  | y  | y   | +/- Dur | absolute time |
| `Dur`      | i64 ticks                                | y  | y   | y     | `Tick - Tick : Dur` |
| `Sym<D>`   | member of closed domain `D`              | y  | n   | n     | interned at compile time |
| `Ent<K>`   | entity id of kind `K`                    | y  | n   | n     | opaque; equality only |
| `Src`      | source id                                | y  | n   | n     | opaque; equality only |
| `Set<D>`   | literal set of `Sym<D>`                  | n  | n   | n     | only as RHS of `in` |
| `Ctl`      | control-sort formula                     | -  | -   | -     | separate sort, 63.6 |

There is deliberately no `Lvl` type in the DATA sort. Control levels are not values; they exist
only as the right operand of `ctl.X >= L` in the CONTROL sort. This is the type-level enforcement
of constraint 63.1(2).

Typing judgments (Γ maps bound variables to fact schema records; Σ is the fact schema; Λ is
`controls.lock`):

```
Γ,Σ |- path : t                     if Σ resolves the path and every segment is a declared field
Γ |- e1 : t , e2 : t , Eq(t)        => e1 == e2 : Bool ,  e1 != e2 : Bool
Γ |- e1 : t , e2 : t , Ord(t)       => e1 <  e2 : Bool   (and <=, >, >=)
Γ |- e : Bool                       => not e : Bool
Γ |- e1,e2 : Bool                   => e1 and e2 : Bool , e1 or e2 : Bool
Γ |- e : Sym<D> , s : Set<D>        => e in s : Bool
Γ |- e1 : Int , e2 : Int            => e1 + e2 : Int , e1 - e2 : Int
Γ |- e1 : Dur , e2 : Dur            => e1 + e2 : Dur , e1 - e2 : Dur
Γ |- e1 : Tick , e2 : Tick          => e1 - e2 : Dur
Γ |- e1 : Tick , e2 : Dur           => e1 + e2 : Tick , e1 - e2 : Tick
Γ |- e : Dur , n in 1..=1024        => e * n : Dur          (Int likewise)
Γ |- e1,e2 : t , Ord(t)             => min(e1,e2) : t , max(e1,e2) : t
Γ |- e : Dur                        => abs(e) : Dur
Γ |- a,b : Tick , d : Dur           => within(a,b,d) : Bool
Γ |- a,b,c,d : Tick                 => overlaps(a,b,c,d) : Bool
Γ |- e1,e2 : Ent<K>                 => distinct(e1,e2) : Bool     (same K required)
Λ |- name in Λ.controls , lvl in Λ.levels(name) => ctl.name >= lvl : Ctl
Γ |- e1,e2 : Ctl                    => e1 and e2 : Ctl , e1 or e2 : Ctl
```

`Tick + Tick`, `Dur < Int`, `Ent<user> == Ent<host>`, `Sym<verb> == Sym<outcome>` and
`min(entity_a, entity_b)` are all type errors. A `when` expression whose root is not `Bool` is
E-TYP-001. A `blocked_when` expression whose root is not `Ctl` is E-TYP-002.

No implicit conversion exists. `Int` and `Dur` never unify. There is no cast operator.

63.5 EVALUATION SEMANTICS

`eval : Node x Env -> Value` is total. Its signature in every backend returns a value, never a
`Result`, `Either`, `Maybe`, `error`, or an exception. A CI gate greps the generated and
hand-written evaluators for `Result<`, `panic!`, `unwrap(`, `expect(`, `throw`, `err !=` inside
the evaluator module and fails the build (`make guard-lint`). OVERRIDES Part I: "a guard may not
throw" becomes a checked property of the code, not an aspiration.

```
eval(And[c1..cn], E) = fold(&&, map(eval(*,E), c1..cn))     -- short-circuit permitted; no observable difference
eval(Or [c1..cn], E) = fold(||, map(eval(*,E), c1..cn))
eval(Not c, E)       = !eval(c,E)
eval(Eq a b, E)      = bitwise equality of the two canonical value encodings
eval(Lt a b, E)      = signed i64 comparison (Int, Tick, Dur only; guaranteed by typing)
eval(Add a b, E)     = sat_add(eval a, eval b)
eval(Sub a b, E)     = sat_sub(eval a, eval b)
eval(MulLit a n, E)  = sat_mul(eval a, n)
eval(Abs a, E)       = if v == i64::MIN then i64::MAX else |v|      -- total, documented
eval(Min a b, E)     = if a <= b then a else b                      -- Max symmetric
eval(Slot i, E)      = E.slots[i]                                   -- slot always bound (63.6 C6)
eval(Field(base,f))  = the field's value; the fact schema guarantees presence
eval(ConstX, E)      = the constant
```

`sat_add`, `sat_sub`, `sat_mul` saturate at i64::MIN / i64::MAX. Saturation is the defined
semantics in every backend, not undefined behavior and not a wrap. A saturation event is
observable: `sglc` emits `saturating_sites` in the compile report and the kernel increments a
counter that appears in the run manifest. A guard that saturates on any fixture is a modelling
error and the fixture is quarantined (see the oracle triage procedure in §62).

Duration literals are converted to ticks at compile time using `tick_granularity_ns` from the time
lattice. If a literal is not an integral number of ticks, that is E-SEM-030 — SGL never rounds.

CONTROL-sort evaluation is not an expression walk. It is compiled to masks (63.6) and evaluated as:

```
enabled(inst, S)  ==  forall t in inst.blockers : (t & S) != t
```

i.e. the instance is blocked iff some DNF term's atom set is a subset of the cut S.

OVERRIDES Part I / ECLIPSE §3: `RuleInst.blockers` is not a single `u64`. It is
`blockers: SmallVec<[u64; 2]>`, a canonical monotone DNF, tested by subset containment. A single
term (the common case) degenerates to the Part I behaviour `blockers & S != 0` only when
`popcount(t) == 1`; the Part I test is wrong for any conjunctive blocker and must be replaced
everywhere, including in the Go checker and in the Dowling–Gallier unit-propagation loop of
ECLIPSE §4D.

ANTITONICITY LEMMA (obligation on the implementation, not a claim about reality): every DNF term
is a positive set of atoms, so `S ⊆ S'` implies `{t : t ⊆ S} ⊆ {t : t ⊆ S'}`, so
`enabled(inst, S')  =>  enabled(inst, S)`. Hence the derived fact set is antitone in S. The
grammar of 63.3 makes any counterexample unparseable. `make guard-lattice-test` additionally
enumerates the full admissible-cut lattice on every fixture catalog and asserts antitonicity
empirically; it must go red when the mutation harness (63.12) negates a threshold.

Cuts are downward-closed per control: if `x_{k,l}` in S then `x_{k,l'}` in S for all `l' <= l`.
`sglc` emits `admissible_cut_mask(k)` helpers and the checker rejects any certificate whose cut
is not downward-closed (E-CERT-070, owned by the certificate section).

63.6 CANONICALIZATION

Canonicalization is a total, idempotent function from a type-checked parse tree to the canonical
AST DAG. It runs in exactly this order. Every backend that publishes a hash (63.9) implements
exactly these rules.

```
C1 DESUGAR to the core node set:
     a != b        -> Not(Eq a b)
     a >  b        -> Lt(b, a)
     a >= b        -> Not(Lt(a, b))
     a <= b        -> Not(Lt(b, a))
     x in {s1..sn} -> Or[Eq(x,#s1) .. Eq(x,#sn)]
     within(a,b,d) -> Not(Lt(d, Abs(Sub(a,b))))
     overlaps(a,b,c,d) -> And[Not(Lt(d,a)), Not(Lt(b,c))]
     distinct(a,b) -> Not(Eq(a,b))
   Core node set after C1: And Or Not Eq Lt Add Sub MulLit Min Max Abs Slot Field
                           ConstInt ConstBool ConstSym  (+ Threshold in the control sort)
C2 FOLD constants bottom-up with the saturating semantics of 63.5; normalize dur_lit to ticks.
C3 NNF: push Not to leaves by De Morgan; eliminate Not(Not(x)); Not(ConstBool b) -> ConstBool !b.
C4 FLATTEN nested And/And and Or/Or into n-ary nodes; absorb identities
   (And[..,true,..] drops true; And[..,false,..] -> false; dually for Or);
   DEDUPE identical children; SORT children ascending by (kind_tag, node_hash_128) with
   ties impossible after dedupe.
C5 HASH-CONS: intern every node into a DAG; number nodes 0..n-1 in postorder of first occurrence.
C6 SLOTS: rename bound variables to slot indices in order of their declaration in the rule's
   `body`, not in the guard. Guard hashes are therefore invariant under variable renaming and
   under reordering within the guard, and NOT invariant under reordering the rule body. State
   this in docs/guards.md; a body reorder is a semantic edit of the rule table and must
   invalidate certificates.
C7 CONTROL SORT ONLY:
   a) distribute to DNF; if term count > 8, E-SEM-041 (split the rule; do not silently cap).
   b) within a term, for each control keep only the highest required level
      (ctl.c >= 3 and ctl.c >= 5  ==  ctl.c >= 5), by x_{k,l+1} -> x_{k,l}.
   c) across terms, delete any term that is a superset of another term (absorption), and for
      single-control terms keep only the lowest level (ctl.c >= 3 or ctl.c >= 5 == ctl.c >= 3).
   d) map each atom to its bit via controls.lock; sort terms ascending by (popcount, u64 value).
C8 ASSERT idempotence: canon(canon(x)) == canon(x), bytewise. Checked on every compile, not only
   in tests; failure is an internal-compiler-error and aborts the build.
```

Bit positions come from `controls.lock`, generated by the control-catalog section: controls sorted
by ASCII name, levels ascending, positions assigned by running offset, `sum(m_k) <= 64` enforced
there. `sglc` fails with E-CFG-050 if `controls.lock` is missing, stale relative to
`controls.toml`, or assigns a bit >= 64. Bit positions are part of `guard_ast_hash`, so a catalog
edit that shifts bits invalidates certificates — which is correct, and is why positions are
append-only across catalog versions (the catalog section owns the migration rule).

63.7 CANONICAL BINARY ENCODING (`.sglb`) AND HASHES

All integers are LEB128; signed integers are zigzag-then-LEB128. There is no padding, no
alignment, no endianness, no length field that could disagree with its payload's own terminator,
and no floating point. Strings are UTF-8 matching `[a-z0-9_]+`, length-prefixed.

```
  off  field                    encoding
  ---  -----------------------  -----------------------------------------------------
   0   magic                    "SGLB" (4 bytes, no BOM)
   4   format_version           varint, currently 1
   -   tick_granularity_ns      varint
   -   n_domains                varint
        per domain              name:str, n_members:varint, members:str[]  (members ASCII-sorted)
   -   n_atoms                  varint
        per atom                control:str, level_name:str, level:varint, bit:varint
        (atoms emitted in bit order; bit must equal the emission index)
   -   n_slots                  varint
        per slot                type_tag:varint, name:str   (declaration order = slot index)
   -   n_nodes                  varint
        per node (postorder)    kind_tag:varint, type_tag:varint, payload
   -   n_rules                  varint
        per rule                rule_id:varint, when_root:varint,
                                n_terms:varint, terms:varint[]   (each term = u64 mask, zigzag-free)
```

Node payloads:

| kind | tag  | payload |
|------|------|---------|
| And / Or | 0x01 / 0x02 | arity:varint, child_idx:varint[] (ascending, per C4) |
| Not | 0x03 | child_idx:varint |
| Eq / Lt | 0x04 / 0x05 | lhs:varint, rhs:varint |
| Add / Sub | 0x06 / 0x07 | lhs:varint, rhs:varint |
| MulLit | 0x08 | child:varint, n:varint (1..=1024) |
| Min / Max | 0x09 / 0x0A | lhs:varint, rhs:varint |
| Abs | 0x0B | child:varint |
| ConstInt | 0x0C | zigzag varint |
| ConstBool | 0x0D | 0 or 1 |
| ConstSym | 0x0E | domain_idx:varint, member_idx:varint |
| Slot | 0x0F | slot_idx:varint |
| Field | 0x10 | base:varint, field_idx:varint |

Illustrative hexdump of a two-node fragment `Not(Eq(Slot 0, #ok))` (illustrative, not a target):

```
53 47 4c 42  01              "SGLB" v1
...                           header omitted
0f 03 00                      node0: Slot   type=Sym<outcome> slot=0
0e 03 02 01                   node1: ConstSym domain=2 member=1
04 01 00 01                   node2: Eq     type=Bool lhs=0 rhs=1
03 01 02                      node3: Not    type=Bool child=2
```

Hashes:

- `guard_ast_hash = BLAKE3(bytes of guards/ast.sglb)` — 32 bytes, rendered lowercase hex.
- `rules_table_hash = BLAKE3(canonical encoding of rule metadata)` where the metadata record per
  rule is `(rule_id, head_predicate, body_predicates, producing_sources sorted, silent_possible,
  attck_refs sorted)` plus `guard_ast_hash` as a trailing field. Prose notes are excluded.

OVERRIDES Part I / ECLIPSE §5: `Cert.hashes.rules` is `rules_table_hash`, **not** the SHA-256 of
`rules.toml` bytes. This closes the critics' "does a comment invalidate every certificate?"
question: it does not. The raw file digest is still recorded as `rules_source_sha256` in the run
manifest for provenance, and is explicitly non-load-bearing.

63.8 CODEGEN TARGETS AND THE COMMITTED-VS-BUILT DECISION

| Consumer | Guard implementation | Generated from AST? | Committed? |
|----------|----------------------|---------------------|-----------|
| Rust kernel (`crates/eclipse-kernel`) | `src/generated/guards.rs` — a `match` over slot-typed evaluators, plus the atom/bit tables | YES | YES |
| Rust `sglc` itself | hand-written parser, checker, canonicalizer, encoder | no | n/a |
| C guard VM (`c/sglvm`) | hand-written interpreter over `.sglb`; no generated code; independent decoder of the binary format | no | n/a |
| Go checker (`go/spectra-verify`) | hand-written lexer, parser, type checker, canonicalizer, mask compiler, evaluator, written from this section only | no | n/a |
| Haskell admissibility oracle | hand-written, stretch tier | no | n/a |
| Python services | none — shells out to `sglc`; never evaluates a guard | n/a | n/a |
| TypeScript frontend | renders a pretty-printed AST for display; **must not evaluate guards or compute verdicts** | n/a | n/a |

OVERRIDES Part I section 25.2: the paths `crates/spectra-eclipse`, `crates/spectra-guard` and
`cmd/spectra-verify` are replaced by `crates/eclipse-kernel`, the `sglc` compiler of this section
as the sole shared guard front end, and `go/spectra-verify`. An implementer following Part I ships
a separate guard-parser crate that nothing here builds against, and writes the grep-based
independence and staleness gates (63.10, 63.8) over paths that do not exist in the tree.

DECISION: generated code is **committed**, and CI regenerates and requires byte-identity.

Justification (all four must hold, or the decision is wrong):
1. Offline builds. A clean clone must build with the network off and without running a code
   generator inside every downstream toolchain. Committed artifacts remove `sglc` from the
   dependency path of `cargo build`.
2. Reviewability. The generated evaluator is the code that decides verdicts. A diff of it must
   appear in the pull request that changes a guard, so that a semantic change is visible to a
   human rather than hidden behind a build step.
3. Hermetic verification. `spectra verify` must be a pure file-in/file-out binary; a build-time
   generator is a service dependency in disguise.
4. Drift is closed by a gate, not by trust: `make guards-check` regenerates into a temp tree and
   runs `git diff --exit-code`. Stale generated code fails the build. Generated files carry a
   header `// GENERATED by sglc <version> from guard_ast_hash=<hex>; DO NOT EDIT` and a CI grep
   fails if any generated path is edited without the hash changing.

Negative requirement: no build system, container, or test may invoke `sglc` to produce code that
is then used without the `guards-check` comparison. "Generate at build time and hope" is banned.

63.9 THE AST-HASH EQUALITY GATE

Every backend that has any opinion about guard semantics exposes
`--print-guard-ast-hash` and prints one line: `guard_ast_hash=<64 hex chars>`.

```
                 rules.toml + fact schema + controls.lock   (hashed text inputs)
                     |                |                 |
        +------------+                |                 +--------------+
        v                             v                                v
  sglc (Rust)                  go/spectra-verify                 hs/oracle (stretch)
  parse->check->canon->encode  INDEPENDENT parse->check->canon    INDEPENDENT
        |                             |                                |
   guards/ast.sglb                (no file emitted)                    |
        |    \                        |                                |
        |     \--> generated/guards.rs (committed)                     |
        v                             v                                v
   kernel --print-guard-ast-hash   verify --print-guard-ast-hash    oracle --print-...
        \                             |                                /
         +--------------- must all equal guards/ast.hash -------------+
                                      ^
                          c/sglvm --print-guard-ast-hash
                          (hashes the .sglb bytes it loaded: WEAK, see 63.10)
```

`make guard-hash-gate` collects every published hash, compares them all to the contents of
`guards/ast.hash`, and fails on any mismatch, any missing backend, or any backend that prints a
malformed line. The gate runs on every push (it is seconds of CPU, not minutes) and its output is
archived with the run manifest.

Transcript (hashes and timings illustrative, not a target):

```
$ make guard-hash-gate
sglc 0.4.1: compiled 138 rules, 0 warnings
  guards/ast.sglb          4,912 bytes
  guards/ast.hash          blake3:9c41af2b6d0e57c3...
backend hashes:
  kernel (rust, generated) blake3:9c41af2b6d0e57c3...  OK
  verify (go, independent) blake3:9c41af2b6d0e57c3...  OK
  sglvm  (c, .sglb loader)  blake3:9c41af2b6d0e57c3...  OK (weak route)
  oracle (haskell)         SKIPPED (tier: stretch, not built)
guard-hash-gate: PASS (3/3 required backends agree)
```

Failure is loud and specific:

```
$ make guard-hash-gate
  kernel (rust, generated) blake3:9c41af2b6d0e57c3...
  verify (go, independent) blake3:1de07755a9c4b210...
guard-hash-gate: FAIL — backend disagreement on canonical AST
  first divergent rule: r0071 session_bound_reuse
  rust  : Or[Eq(Slot0,#ok), Lt(Slot3, Slot4)]
  go    : Or[Lt(Slot3, Slot4), Eq(Slot0,#ok)]
  hint  : child ordering (canonicalization rule C4) disagrees; compare node_hash_128
make: *** [guard-hash-gate] Error 1
```

63.10 WHAT THE HASH GATE AND SHARED-AST CODEGEN DO AND DO NOT PROVE

State this verbatim in `docs/guards.md` and link it from the README. OVERRIDES Part I: the ECLIPSE
§7 "simulator vs kernel agree on randomized configurations" gate is hereby DEMOTED to a codegen
regression test and renamed `guard-codegen-regression`. It is not validation and may not be
described as validation anywhere. Validation comes from §62's independent oracles.

DOES establish:
- The Rust kernel's evaluator and the Go checker's evaluator agree on the parse, the type
  assignment, the canonical form and the bit assignment of every guard in the table.
- A change to a guard's meaning changes `guard_ast_hash`, so a certificate cannot silently refer
  to a different rule table than the one that produced it.
- The committed generated code matches the AST it claims to come from (63.8 gate).
- The binary encoding is stable across machines, OSes and toolchain versions (byte-identical
  `.sglb` on two differing CI runners is a separate gate, `make guards-cross-runner`).

DOES NOT establish, and may never be claimed to establish:
- That any guard expresses the security condition the author intended. A guard that says
  `ctl.session_binding >= bound` where the technique is actually defeated at `>= strict` is
  perfectly consistent, perfectly hashed, and wrong.
- That the rule table models the attack, or that the control catalog is complete.
- That a shared design error is absent. The Go path is independently authored and therefore
  catches implementation divergence; it cannot catch a defect in this specification, because both
  implementations are written from this specification.
- Anything about the concrete simulator. The simulator is independently authored, enforces
  controls at its own enforcement points, and MUST NOT link, import, vendor, or read
  `crates/eclipse-kernel`, `generated/guards.rs`, or `guards/ast.sglb`. A build-graph gate
  (`make sim-independence`) inspects the simulator crate's dependency graph and fails on any edge
  into kernel or guard artifacts, and greps its source for those paths.
- Anything about reality. Agreement between two readers of one text is agreement about the text.

Where an independently authored implementation is required instead of shared codegen:
(a) the Go checker's entire guard front end and evaluator; (b) the concrete simulator's
enforcement semantics; (c) the Haskell admissibility oracle, if built; (d) the Z3 encoding used as
a test-only oracle, which must be emitted from `.sglb` by a separate tool and never from the
kernel's in-memory structures.

63.11 ERROR CATALOGUE (all compile time; a guard never fails at runtime)

| Code | Condition |
|------|-----------|
| E-LEX-001 | CR byte, non-UTF-8, or non-NFC input |
| E-LEX-004 | float-shaped literal, or `.` followed by a digit |
| E-LEX-007 | unknown token, or reserved word used as identifier |
| E-SYN-006 | chained relational operators (`a < b < c`) |
| E-SYN-009 | `not`, arithmetic, literal, or variable inside a `blocked_when` expression |
| E-SYN-010 | `ctl.` reference inside a `when` expression |
| E-SYN-012 | level named by integer instead of symbol in a threshold |
| E-TYP-001 | `when` root is not `Bool` |
| E-TYP-002 | `blocked_when` root is not `Ctl` |
| E-TYP-005 | operand type mismatch (`Int` vs `Dur`, `Ent<user>` vs `Ent<host>`, ...) |
| E-TYP-008 | ordering operator applied to an unordered type |
| E-TYP-011 | symbol not a member of the declared domain (typo catcher) |
| E-TYP-014 | unknown field path, or path depth > 3 |
| E-SEM-030 | duration literal not an integral number of ticks |
| E-SEM-033 | `MulLit` factor outside 1..=1024 |
| E-SEM-041 | control guard exceeds 8 DNF terms after distribution |
| E-SEM-044 | structural cap exceeded (depth, node count, arity, set size) |
| E-CFG-050 | `controls.lock` missing, stale, or assigning bit >= 64 |
| E-CFG-052 | guard references a control or level absent from the catalog |
| E-ICE-090 | canonicalization not idempotent (internal compiler error) |

Warnings do not exist. `sglc` has no warning level and no `--allow`. Everything that is wrong is
an error, because a warning in the artifact that decides verdicts is a defect with a grace period.

63.12 DIFFERENTIAL FUZZ AND MUTATION GATES

`make guard-fuzz` (per-push, bounded; extended run nightly):
1. A seeded generator produces well-typed random ASTs against a synthetic fact schema — depth,
   arity, type mix and control-atom count drawn from declared distributions, seed recorded in the
   run manifest.
2. Each AST is encoded to `.sglb`, decoded independently by the Go and C implementations, and
   canonicalized independently by the Go implementation.
3. Assert: all implementations report the same `guard_ast_hash`; all implementations produce the
   same Boolean for every generated environment; all produce the same blocked/enabled result for
   every sampled cut, including non-downward-closed cuts (which must be rejected identically).
4. Any disagreement is a build failure and the failing case is minimized and committed to
   `tests/guards/corpus/` as a permanent regression, with the triage procedure in §62.
5. The corpus is append-only; deleting a corpus entry requires a `WAIVER.md` entry.

`make guard-mutation` (gate-liveness, nightly): apply a fixed list of committed mutations to the
Rust evaluator and the canonicalizer — swap `Lt` operands, drop De Morgan in C3, drop child
sorting in C4, drop level absorption in C7b, invert one threshold, change one bit assignment — and
assert that each mutation turns a named gate red. A mutation that leaves all gates green is a
hole in the test suite and fails the build until a test is added. The mutation-to-gate table is
published in `docs/research/gate-liveness.md`.

63.13 CLI AND CONFIG

```
sglc check      --rules rules.toml --schema facts.schema.toml --controls controls.lock
sglc fmt        [--write] [--canonical]     # --canonical reprints from the canonical AST
sglc emit-ast   --out guards/ast.sglb --hash-out guards/ast.hash
sglc hash       --quiet                     # prints guard_ast_hash only
sglc codegen    --target rust-kernel --out crates/eclipse-kernel/src/generated/guards.rs
sglc explain    --rule r0071                # prints source, canonical AST, DNF terms, bit names
```

```
$ sglc explain --rule r0071
rule r0071  session_bound_reuse
  when  = "s.subject == e.subject and within(e.t, s.issued_at, 30m) and e.verb in {#auth, #refresh}"
  canonical:
    And[ Eq(Slot0, Slot2),
         Not(Lt(ConstInt(1800000), Abs(Sub(Slot1, Slot3)))),
         Or[ Eq(Slot4,#auth), Eq(Slot4,#refresh) ] ]
  blocked_when = "ctl.session_binding >= bound or (ctl.egress_seg >= l1 and ctl.mtls >= required)"
  DNF terms (bit names):
    t0 = { session_binding>=bound }                      mask 0x0000000000000004
    t1 = { egress_seg>=l1, mtls>=required }              mask 0x0000000000000280
  guard_ast_hash contribution: node 41..58
```

`rules.toml` shape (the fields this section owns; the rest belongs to the rule-table section):

```toml
[[rule]]
id            = "r0071"
head          = "session.reused(S, T)"
body          = ["session.issued(S, T0)", "auth.event(E, T)"]
when          = "s.subject == e.subject and within(e.t, s.issued_at, 30m) and e.verb in {#auth, #refresh}"
blocked_when  = "ctl.session_binding >= bound or (ctl.egress_seg >= l1 and ctl.mtls >= required)"
note          = "free prose; NOT hashed into guard_ast_hash"
attck         = ["T1550.004"]
```

OVERRIDES Part I sections 25.3 and 25.4: the single free-prose `provenance` field with the
technique id embedded in its text is replaced by two fields, `note` for prose and `attck` for the
list of technique ids. An implementer following Part I produces a rule table with no `attck`
field, so `rules_table_hash` (63.7) cannot be computed as specified, and the guarantee that
editing a comment does not invalidate a certificate holds only for prose kept in `note`.

63.14 NEGATIVE REQUIREMENTS AND FORBIDDEN CLAIMS

1. Do not add a float, a probability, a weight, a score, a confidence, or a severity to SGL. There
   is no numeric type in the language other than i64-backed `Int`, `Tick` and `Dur`.
2. Do not add division, modulo, exponentiation, string operations, regular expressions, or any
   operator whose cost depends on a value.
3. Do not add `null`, `None`, an option type, an absence test, a default value, or a coalescing
   operator. Unknown is a declared member of a `Sym` domain or it does not exist.
4. Do not add negation, equality, `<`, arithmetic, or numeric level references to the CONTROL sort.
5. Do not allow a guard to read wall-clock time, the environment, a file, a random source, a
   database, an event ordering, or any state outside its bound variables.
6. Do not let a guard mutate anything or observe evaluation order.
7. Do not evaluate a guard in the TypeScript frontend, and do not compute a verdict client-side.
8. Do not generate the Go checker's guard front end, the concrete simulator, the Z3 encoding, or
   the Haskell oracle from the AST, from `sglc`, or from any Rust crate in this repository.
9. Do not silently cap, truncate, round, or coerce. Every cap in 63.3 and every condition in 63.11
   is a build failure with a code.
10. Do not hand-edit a file under `generated/`. Do not add a `sglc` invocation to a downstream
    build script in place of the `guards-check` gate.
11. Do not describe the AST-hash gate, the codegen regression test, or the guard fuzz as
    "verification", "formal verification", "proof of correctness", or "validation of the rules".
    The permitted phrasing is: "the kernel and the independently authored checker agree on the
    canonical form and evaluation of every guard in the table at hash <hex>".
12. Do not print `guard_ast_hash` without its scope in any user-facing verdict string; verdict
    strings carry their binding hashes per the verdict-algebra section.

63.15 DONE CRITERIA

| Requirement | Proven by |
|---|---|
| Grammar and types implemented | `make guards` compiles the shipped table with zero errors; every code in 63.11 has a negative fixture under `tests/guards/errors/` that must fail with exactly that code |
| Totality / no-throw | `make guard-lint` (evaluator greps) plus the fuzz in 63.12 reaching zero panics over the seeded budget |
| Canonicalization idempotent | C8 assertion on every compile; property test over the fuzz corpus |
| Encoding stable | `make guards-cross-runner` diffs `.sglb` bytes produced on two differing CI runners |
| Generated code not stale | `make guards-check` (`git diff --exit-code`) |
| Backends agree | `make guard-hash-gate` plus `make guard-fuzz` |
| Monotonicity in controls | grammar (63.1.2) plus `make guard-lattice-test` |
| Simulator independence | `make sim-independence` build-graph gate |
| Gates are alive | `make guard-mutation` with the published mutation-to-gate table |
