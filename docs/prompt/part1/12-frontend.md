============================================================
39. FRONTEND ARCHITECTURE
============================================================

39.1 Stack (pinned, no substitutions)

- React 18.3 (concurrent features on: `createRoot`, `useDeferredValue`, `useSyncExternalStore`).
- TypeScript 5.6, `strict: true`, plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`,
  `noImplicitOverride`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`. `any` is banned by
  ESLint rule `@typescript-eslint/no-explicit-any: error`. `as` casts are banned except inside
  `src/lib/codecs/` where every cast is adjacent to a zod parse.
- Vite 5 + `@vitejs/plugin-react` + `vite-plugin-wasm` + `vite-plugin-top-level-await`.
- Tailwind CSS 3.4 in token-only mode (see section 40): arbitrary values (`text-[13px]`,
  `bg-[#123456]`) are rejected by `eslint-plugin-tailwindcss` with a custom `no-arbitrary-value` rule.
- TanStack Query v5 for all server state. Zustand 4 for ephemeral view state only.
- D3 7 used as a *math and layout library only* (`d3-scale`, `d3-shape`, `d3-hierarchy`,
  `d3-force`, `d3-time-format`, `d3-zoom`). React owns the DOM. `d3-selection` may not touch
  any node React renders; it is permitted only inside `useD3Zoom` for the zoom behaviour attached
  to an SVG root React never re-keys.
- TanStack Virtual 3 for list virtualization. No other virtualization library.
- Vitest + React Testing Library + Playwright. MSW for network-level fixtures.

39.2 Directory layout

```
frontend/
  index.html
  vite.config.ts
  tailwind.config.ts
  tsconfig.json
  src/
    main.tsx
    app/
      router.tsx              # route objects, lazy boundaries
      providers.tsx           # QueryClientProvider, ThemeProvider, ErrorBoundary root
      shell/                  # AppShell, CommandPalette, GlobalKeymap, StatusBar
    routes/                   # one folder per route, colocated loader+view+tests
      overview/
      investigations/
      investigation-detail/
      timeline/
      entities/
      entity-detail/
      state-explorer/
      reconstruction/
      replay-lab/
      controls/
      proof/                  # ECLIPSE
      evidence/
      scenarios/
      rules/
      benchmarks/
      research/
      datasets/
      health/
      settings/
    api/
      client.ts               # fetch wrapper, AbortSignal, problem+json decoding
      keys.ts                 # query key factory (single source of truth)
      schemas/                # zod schemas generated from backend OpenAPI, checked in
      hooks/                  # one hook per endpoint, no ad-hoc useQuery in components
    viz/
      timeline-rail/
      state-graph/            # AND/OR hypergraph + state transition graph renderers
      corridor-strip/
      degradation-matrix/
      scrubber/
      primitives/             # Axis, Brush, Legend, HatchDefs, ZoomRoot
    state/
      cursor.ts               # shared temporal cursor (Zustand slice)
      selection.ts            # selected entity / fact / event / corridor
      panels.ts               # triptych sizing, collapsed sections
      theme.ts
    wasm/
      pkg/                    # wasm-pack output of crates/spectra-evidence-wasm
      verifier.ts             # typed façade + worker bootstrap
      verifier.worker.ts
    lib/
      url-state.ts            # zod-validated search param codecs
      format.ts               # id/time/hash formatters (monospace discipline)
      a11y/
    styles/
      tokens.css              # generated from design/tokens.json — never hand-edited
      index.css
```

39.3 Routing

- React Router 6.26 data router (`createBrowserRouter`) with route objects. Every route is
  `React.lazy`-split. Route-level `ErrorBoundary` is mandatory; a route without one fails the
  `router.spec.ts` test that walks the route tree.
- The URL is the single source of truth for anything a user could want to share. Route params
  carry identity; search params carry view state; nothing shareable lives only in Zustand.

| Route | Path | Route params | Search params (zod-validated) |
|---|---|---|---|
| Overview | `/` | — | `range` |
| Investigations | `/investigations` | — | `q,status,severity,sort,page` |
| Investigation Detail | `/investigations/:invId` | `invId` | `t,fact,evt,rail,panel,zoom` |
| Timeline | `/timeline` | — | `t,from,to,src[],dim[],ghost` |
| Entities | `/entities` | — | `q,kind,sort,page` |
| Entity Detail | `/entities/:entityId` | `entityId` | `t,tab` |
| State Explorer | `/state` | — | `t,dim[],entity,play,speed` |
| Reconstruction | `/investigations/:invId/reconstruction` | `invId` | `t,node,layout,depth` |
| Replay Lab | `/replay` | — | `scenario,baseline,variant,step,sync` |
| What-If Controls | `/controls` | — | `scenario,cfg` |
| Proof (ECLIPSE) | `/proof` | — | `scenario,cfg,mode,cut,corridor,cert` |
| Evidence & Integrity | `/evidence` | — | `bundle,src,q,page` |
| Scenarios | `/scenarios` | — | `q,tag` |
| Rules | `/rules` | — | `q,rule,silent` |
| Benchmarks | `/benchmarks` | — | `suite,run` |
| Research | `/research` | — | `figure` |
| Datasets | `/datasets` | — | `seed,completeness` |
| System Health | `/health` | — | — |
| Settings | `/settings` | — | `tab` |

- `cfg` encodes the full control configuration as a compact ordered string
  `mfa=2,session_binding=1,egress_seg=0,...` — never an opaque index into server state.
- `t` is an RFC 3339 UTC instant with millisecond precision. Never a slider percentage.
- Unknown or malformed search params: strip, render the route with defaults, and show a one-line
  dismissible notice "3 unrecognised URL parameters ignored: foo, bar, baz". Never throw.

39.4 Data-fetching discipline (hard rules)

1. Exactly one query-key factory, `src/api/keys.ts`. Literal key arrays in components are a lint
   error (`no-restricted-syntax` on `useQuery` called with an inline array).
2. Every response is parsed by a zod schema derived from the backend OpenAPI document. Schemas are
   generated by `pnpm gen:api` and committed; CI regenerates and fails on diff. A parse failure is
   an error state, not a silent fallback: the UI shows "Response did not match schema" plus the
   path of the first offending field and a copy button for the raw payload.
3. **The frontend performs no security-relevant computation.** It may sort, filter, paginate,
   format and lay out. It may not compute counts, ratios, scores, cut cardinalities, coverage
   percentages, blast radii, or verdicts. If a number is on screen it came from a JSON field.
   A unit test enumerates every `.length`, `/`, `*`, `reduce(` occurrence inside `src/routes/**`
   and requires an inline `// display-only:` justification comment; unjustified arithmetic fails CI.
4. `staleTime` policy: immutable artefacts (bundles, certificates, completed runs, benchmark
   results) `Infinity`; catalogues (rules, controls, scenarios) 5 min; live job status via SSE, not
   polling. `refetchOnWindowFocus: false` globally.
5. Long-running work (grounding, cut search, replay, degradation sweep) is a job: `POST` returns
   `{ job_id }`, progress arrives on `GET /api/v1/jobs/{id}/events` (SSE), result is fetched once
   `status == "succeeded"`. The SSE hook reconnects with exponential backoff to 30 s and surfaces
   "Reconnecting (attempt n)" in the status bar. Progress bars display server-reported
   `completed/total` only; never a synthetic animation.
6. Mutations invalidate by key prefix, never `queryClient.clear()`.
7. No `useEffect` fetching. No fetch inside `viz/`. Visualization components receive plain data
   props and are pure.

```ts
// src/api/keys.ts (shape is normative)
export const qk = {
  investigations: (f: InvFilter) => ['investigations', f] as const,
  investigation:  (id: InvId)    => ['investigation', id] as const,
  timeline:       (id: InvId, w: Window) => ['investigation', id, 'timeline', w] as const,
  facts:          (id: InvId, t: Instant) => ['investigation', id, 'facts', t] as const,
  evidence:       (eid: EventId) => ['evidence', eid] as const,
  proof:          (s: ScenarioId, cfg: CfgHash, mode: ProofMode) =>
                    ['proof', s, cfg, mode] as const,
  cert:           (h: Blake3) => ['cert', h] as const,
  liveness:       (b: BundleHash) => ['liveness', b] as const,
  replay:         (s: ScenarioId, a: CfgHash, b: CfgHash) => ['replay', s, a, b] as const,
} as const;
```

39.5 View-state machine (loading / empty / error are first-class)

Every data-bearing region renders through `<AsyncRegion>` which accepts a discriminated union and
refuses to render children until the state is `ok` or `partial`:

```ts
type RegionState<T> =
  | { kind: 'idle' }                                            // user has not run anything yet
  | { kind: 'loading'; since: number; progress?: Progress }      // skeleton, not spinner
  | { kind: 'empty'; reason: EmptyReason; action?: CallToAction }
  | { kind: 'partial'; data: T; missing: MissingNote[] }         // e.g. blind windows
  | { kind: 'error'; problem: ProblemDetails; retry: () => void }
  | { kind: 'ok'; data: T };
```

- `empty` must state *why* and offer the next action ("No investigations. Run a scenario →").
  "No data" alone is a review-blocking defect.
- `partial` is the normal state for blind intervals and capped grounding: the region renders what
  exists and shows a `MissingNote` strip naming source and interval.
- Skeletons mirror the final layout (same row heights, same column widths); no layout shift on
  resolve. Loading states appear only after 150 ms to avoid flash.
- Three root-level error boundaries: app shell, route, and panel. A panel crash must not blank the
  triptych; the failed panel shows its own error card with a "Copy diagnostics" button that copies
  route, search params, query keys in flight, commit SHA and the error stack.

39.6 Virtualization and large-data rules

- Any list that can exceed 200 rows uses `useVirtualizer` with fixed row height 28 px (`--row-h`).
  Event lists, fact lists, rule-instance lists, evidence tables, corridor lists are all virtualized.
- Timeline rail: events are bucketed server-side into fixed-width bins; the client renders at most
  2,000 marks and one aggregate density band. When bins are collapsed the rail says
  "3,412 events in 240 bins" — never silently drops marks.
- Graph rendering: SVG up to 1,500 nodes; above that switch to canvas (`viz/state-graph/canvas.ts`)
  with an offscreen hit-test buffer. The switch threshold is displayed in the graph footer.
- Force layout runs in a Web Worker (`viz/state-graph/layout.worker.ts`) with a seeded PRNG so a
  given graph lays out identically every time. Non-deterministic layout is a defect.
- Frame budget: interaction-to-paint under 100 ms for scrub, hover and selection on the 50k-event
  reference bundle; Playwright performance test asserts it and fails CI on regression.

39.7 Keyboard-first navigation

- Command palette `Ctrl/Cmd+K`: routes, scenarios, entities, rules, controls, actions. Fuzzy match
  on id and label; ids shown monospace.
- Global: `g o` Overview, `g i` Investigations, `g t` Timeline, `g s` State Explorer,
  `g r` Replay Lab, `g p` Proof, `g e` Evidence, `g h` Health, `?` shortcut sheet.
- Temporal cursor: `,` / `.` step one event, `Shift+,` / `Shift+.` step one transition,
  `[` / `]` jump to previous/next blind-window boundary, `Home`/`End` bundle bounds,
  `Space` play/pause scrub, `t` focus the time input (accepts RFC 3339 or `+15m`).
- Panels: `1`/`2`/`3` focus rail/graph/inspector; `\` toggle inspector; `f` fit graph to view.
- Proof screen: `p` PROVE, `v` run checker, `x` toggle selected control, `n`/`N` next/prev corridor.
- Every interactive element is reachable by Tab in DOM order; visible focus ring
  (`outline: 2px solid var(--focus); outline-offset: 2px`) is never removed. Roving tabindex inside
  grids and the graph. Escape closes the topmost overlay only.
- `jest-axe`/`axe-core` runs on every route in Playwright; zero violations of severity
  serious/critical is a merge gate.

39.8 WASM evidence verifier (client-side integrity)

Crate `crates/spectra-evidence-wasm`, compiled with `wasm-pack build --target web --release`,
sharing the BLAKE3 chain and Merkle code with the ingest pipeline via the `spectra-evidence` crate.
It runs in a dedicated worker so a 50 MB bundle never blocks the main thread.

```ts
// src/wasm/verifier.ts
export interface EvidenceVerifier {
  init(): Promise<void>;                                   // instantiate module, report version+hash
  hashBundle(bytes: ArrayBuffer): Promise<Blake3>;         // streaming, 1 MiB chunks
  verifyChain(src: SourceId, bytes: ArrayBuffer): Promise<ChainReport>;
  verifyMerkleProof(leaf: EventId, proof: MerkleProof, root: Blake3): Promise<boolean>;
  recomputeCertHash(cert: CertJson): Promise<Blake3>;      // canonical JSON, then BLAKE3
  moduleFingerprint(): { version: string; wasmHash: Blake3; builtFrom: GitSha };
}

export interface ChainReport {
  records: number;
  firstSeq: number; lastSeq: number;
  breaks: Array<{ atSeq: number; expected: Blake3; found: Blake3 }>;
  gaps:   Array<{ fromSeq: number; toSeq: number }>;
  verdict: 'INTACT' | 'GAP' | 'BROKEN';
}
```

Rules:
1. Raw evidence the user drops into the browser (a `bundle.jsonl`, a `cert.json`) is hashed and
   chain-checked locally. It is **not uploaded** to verify integrity. The drop zone states this.
2. The WASM verifier checks *integrity and addressing only*: hashes, sequence chains, Merkle
   proofs, canonical-JSON certificate hashes. It must never be described, labelled or presented as
   verifying the ECLIPSE proof. The authoritative proof check is the independent Go checker
   (see section 5 of the ECLIPSE spec and section 27). The Proof screen shows both, separately
   labelled "Client integrity (WASM)" and "Independent checker (Go)".
3. The module fingerprint (version, wasm hash, source commit) is displayed in Settings → About and
   in the Evidence screen footer. A mismatch between `wasmHash` and the value the API reports for
   the build renders a warning banner.
4. If WASM is unavailable (blocked, old browser), integrity panels render `kind: 'error'` with
   "Client-side verification unavailable in this browser" — they never fall back to a server call
   and never show a green tick.

39.9 Negative requirements

- Do not add a UI component library (MUI, Chakra, AntD, shadcn wholesale). Build the ~30 primitives
  the product needs in `src/ui/`, on Radix UI unstyled primitives for dialog, popover, tooltip,
  tabs, dropdown and toggle-group only.
- Do not use a charting library (Recharts, Chart.js, ECharts, Nivo, visx). All visuals are D3 scales
  plus hand-written SVG/canvas in `src/viz/`.
- Do not install a state manager beyond Zustand; no Redux, MobX, Jotai, Recoil, XState.
- Do not use `dangerouslySetInnerHTML` anywhere. Markdown in narration is rendered by a hardened
  renderer with an allowlist of inline nodes and no raw HTML.
- Do not use `localStorage` for anything the URL should carry. Permitted local storage: theme,
  density, last-used scenario, collapsed-panel sizes, shortcut-sheet dismissal. Nothing else.
- Do not ship analytics, telemetry, fonts from a CDN, error-reporting SaaS, or any network call to a
  host other than the local API. CSP is `default-src 'self'` with `connect-src 'self'` and
  `wasm-unsafe-eval` only; a Playwright test asserts zero third-party requests.
- Do not animate for decoration. Permitted motion: 120 ms opacity/transform on overlays, the
  step-through replay diff, and the scrub cursor. All motion respects
  `prefers-reduced-motion: reduce` by dropping to instant transitions.


============================================================
40. DESIGN LANGUAGE
============================================================

40.1 Intent

Build the visual language of an instrument, not a dashboard. Dense, quiet, typographically
disciplined, readable for an hour at a time. Every pixel of colour carries state semantics. The
default impression must be "this tool is telling me exactly what it knows and exactly what it does
not know".

40.2 Token source of truth

`design/tokens.json` is the only place values are authored. `pnpm tokens:build` emits
`src/styles/tokens.css` (CSS custom properties) and `tailwind.config.ts` theme extensions.
Hand-editing either output fails CI. Tailwind's default colour, spacing, radius, shadow and font
scales are **replaced**, not extended, so `bg-blue-500` and `p-5` do not exist.

40.3 Neutral palette

Dark (default):

| Token | Hex | Use |
|---|---|---|
| `--bg-canvas` | `#0B0D10` | app background |
| `--bg-surface` | `#101317` | panels, cards |
| `--bg-raised` | `#161A1F` | headers, toolbars, sticky rows |
| `--bg-overlay` | `#1D2228` | dialogs, popovers, menus |
| `--bg-inset` | `#080A0C` | code blocks, inputs, terminal pane |
| `--bd-subtle` | `#20262D` | hairlines inside a panel |
| `--bd-default` | `#2B333C` | panel and control borders |
| `--bd-strong` | `#3A444F` | focused/active borders, table header rules |
| `--fg-primary` | `#E7ECF2` | body text, values |
| `--fg-secondary` | `#A6B0BC` | labels, secondary values |
| `--fg-muted` | `#717D8A` | metadata, units, disabled |
| `--fg-inverse` | `#0B0D10` | text on solid state fills |
| `--focus` | `#7AA7FF` | focus ring only |
| `--link` | `#8FB6FF` | interactive text only |
| `--sel-bg` | `#1B3350` | row/mark selection |

Light:

| Token | Hex |
|---|---|
| `--bg-canvas` | `#F7F8FA` |
| `--bg-surface` | `#FFFFFF` |
| `--bg-raised` | `#F1F3F6` |
| `--bg-overlay` | `#FFFFFF` |
| `--bg-inset` | `#EEF1F4` |
| `--bd-subtle` | `#E3E7EC` |
| `--bd-default` | `#CDD4DC` |
| `--bd-strong` | `#A4AFBB` |
| `--fg-primary` | `#11161C` |
| `--fg-secondary` | `#3D4853` |
| `--fg-muted` | `#5E6975` |
| `--focus` | `#1F5FD0` |
| `--link` | `#12459E` |
| `--sel-bg` | `#DCE8FB` |

Blue (`--focus`, `--link`, `--sel-bg`) is reserved for interaction affordance and is excluded from
the state palette so that "interactive" and "state" never collide.

40.4 Semantic state palette (colour encodes state only)

Derived from Okabe–Ito for deuteranopia/protanopia/tritanopia safety. Every state has a colour, a
glyph, a fill pattern and a text label; **colour alone never carries meaning**.

| State | Dark hex | Light hex | Glyph | Pattern | Meaning |
|---|---|---|---|---|---|
| normal | `#7E8A97` | `#5E6975` | `·` | none | observed, within baseline |
| watch | `#E69F00` | `#A16A00` | `△` | 45° sparse hatch | elevated, not anomalous |
| anomalous | `#CC79A7` | `#9A3F76` | `◆` | dotted | deviates from baseline |
| blocked | `#56B4E9` | `#0072B2` | `⊘` | horizontal rule | control stopped this step |
| compromised | `#D55E00` | `#B34700` | `✕` | solid | attacker-controlled in reconstruction |
| unknown | `#8A94A0` | `#6B7580` | `?` | cross-hatch | not observed / not determinable |

Verdict palette (ECLIPSE only, never reused for entity state):

| Verdict | Dark | Light | Rendering |
|---|---|---|---|
| ROBUST | `#009E73` | `#007454` | solid chip, glyph `■` |
| OPTIMISTIC-ONLY | `#E69F00` | `#A16A00` | chip with right-edge notch, glyph `◧` |
| UNSAFE | `#D55E00` | `#B34700` | solid chip, glyph `✕` |
| FLAGGED | inherits verdict hue | inherits | mandatory cross-hatch overlay + `flag` icon |

Rules:
1. A run carrying any of `grounding_capped`, `subset_minimal_only`, `greedy_cover` renders FLAGGED
   cross-hatch and the words "flagged — not a ROBUST result" next to the chip. A flagged run must
   never be painted with the plain ROBUST chip. A visual-regression test covers this.
2. GHOST (licensed silent) elements render as `unknown` cross-hatch with a dashed 1 px outline at
   60% opacity and the label `GHOST`. They are visually distinguishable at 1× zoom in greyscale.
3. No other colours exist. There is no success green outside ROBUST, no "info" blue outside
   interaction, no severity red outside `compromised`/UNSAFE.
4. Charts use the state palette when encoding state, and a 5-step neutral ramp
   (`#2B333C → #4B5661 → #6C7885 → #8E99A5 → #B3BCC6`) when encoding magnitude. Categorical series
   that are not states use shape and dash pattern first, neutral ramp second.

40.5 Typography

| Token | Family |
|---|---|
| `--font-ui` | `Inter var, ui-sans-serif, system-ui, "Segoe UI", sans-serif` |
| `--font-mono` | `"JetBrains Mono", ui-monospace, "SF Mono", "Cascadia Mono", monospace` |

Fonts are self-hosted WOFF2 in `public/fonts/`, subset to latin + the glyph set above. No Google
Fonts request.

| Token | Size / line-height / weight / tracking | Use |
|---|---|---|
| `--t-micro` | 11 / 16 / 500 / +0.02em | table sub-labels, axis ticks, units |
| `--t-meta` | 12 / 18 / 400 / 0 | metadata, captions, footnotes |
| `--t-body` | 13 / 20 / 400 / 0 | default body and table cells |
| `--t-body-strong` | 13 / 20 / 600 / 0 | emphasised values |
| `--t-subhead` | 15 / 22 / 600 / -0.005em | panel titles |
| `--t-head` | 19 / 26 / 600 / -0.01em | screen titles |
| `--t-display` | 26 / 32 / 600 / -0.015em | verdict chip, single hero number |

Monospace is mandatory, not optional, for: event ids, fact ids, rule ids, entity ids, hashes,
timestamps, durations, byte counts, IP addresses, ports, file paths, control atoms (`mfa≥2`),
cut sets, seeds, and every numeric value in a table column. `tabular-nums` and
`font-variant-numeric: tabular-nums` on all numeric cells. Hashes render as
`blake3:3f9a1c…8d20` with first 6 and last 4 hex characters, full value on hover and on copy.
Timestamps render `2026-03-14 09:41:07.312Z` and never as "3 hours ago" unless a relative value is
shown *next to* the absolute one.

40.6 Spacing, sizing, borders, elevation

- Spacing scale (px): `0, 2, 4, 8, 12, 16, 24, 32, 48, 64`. Tokens `--sp-0 … --sp-64`. Values off
  the scale are a lint error. 2 and 4 exist only for intra-control padding and icon gaps.
- Density: `--row-h: 28px` (comfortable) / `24px` (compact, Settings toggle). Table cell padding
  `0 8px`. Panel padding `12px`. Section gap `16px`. Screen gutter `16px`.
- Radii: `--r-0: 0`, `--r-1: 2px`, `--r-2: 4px`. Nothing larger. No pill shapes except keyboard-key
  glyphs. Circles only for the 6 px state dot.
- Borders: 1 px, `--bd-subtle` inside panels, `--bd-default` on panel edges, `--bd-strong` on focus
  and table header rules. All at device-pixel crispness (no sub-pixel borders in SVG).
- Elevation in dark theme is expressed by background step + border, not shadow. Shadows are
  permitted only on overlay layers: `--elev-overlay: 0 8px 24px rgba(0,0,0,0.45)` (dark),
  `0 8px 24px rgba(16,24,32,0.12)` (light). Cards, panels and rows have no shadow, ever.
- Icons: 16 px grid, 1.5 px stroke, from a single hand-curated inline SVG set in `src/ui/icons/`.
  No icon font. No emoji anywhere in the product UI, including empty states and toasts.

40.7 Accessibility requirements

- WCAG 2.1 AA: text ≥ 4.5:1 against its actual background token; text ≥ 18.66 px bold or ≥ 24 px
  ≥ 3:1; non-text UI (borders of inputs, chart marks, focus ring, state dots) ≥ 3:1.
- `scripts/check-contrast.ts` reads `design/tokens.json`, enumerates every documented
  foreground/background pairing, and fails the build on any violation. Its output table is committed
  to `docs/design/contrast.md` and regenerated in CI.
- Colourblind verification: `scripts/check-cvd.ts` simulates deuteranopia, protanopia and
  tritanopia over the state palette and requires pairwise ΔE2000 ≥ 15 under each simulation.
  Failure blocks the build.
- Greyscale test: a Playwright visual test renders the Proof, State Explorer and Replay screens with
  a greyscale filter; a human-reviewed baseline requires every state to remain distinguishable.
- Respect `prefers-reduced-motion`, `prefers-contrast: more` (swaps `--bd-default` → `--bd-strong`,
  raises `--fg-secondary` to `--fg-primary`), and `prefers-color-scheme` (with explicit override).
- Minimum hit target 24 × 24 px; 32 × 32 px for toolbar buttons. Dense table rows expose a
  full-row click target.

40.8 Banned (build a different thing than the default "cyber" look)

Do not produce, and reject in review: neon cyberpunk palettes; glow, bloom, outer-glow or
`box-shadow` used as light emission; gradient fills of any kind including subtle "premium"
gradients, glassmorphism, blur backdrops; fake terminal typing animations or simulated hacking
output; scanline, CRT, noise or grain overlays; matrix rain; skulls, hoodies, crosshairs, padlock
mascots, shield icons as decoration; radial/semicircular gauges, speedometers, donut "risk scores";
a top row of KPI cards showing numbers nobody acts on; animated counters that tick up; confetti;
drop shadows on cards; rounded-2xl card grids; hero sections; marketing copy; badges reading "AI",
"AI-powered", "GPT", "Neural" or similar; emoji in UI copy, chart labels, toasts or empty states;
more than one accent hue; any colour used decoratively.

Also banned as *claims* rendered in the UI: percentage confidence, probability, risk score out of
100, letter grades, "likelihood", star ratings, threat-level dials. SPECTRA's verdict vocabulary is
ROBUST / OPTIMISTIC-ONLY / UNSAFE / FLAGGED and its state vocabulary is the six semantic states.


============================================================
41. SCREEN SPECIFICATIONS
============================================================

Each screen below is specified as: purpose, route, data (API reads), primary actions, empty state,
done criteria. Every screen has a persistent left rail (routes), a top bar (scenario selector,
bundle hash chip, temporal cursor readout, theme, command palette hint) and a bottom status bar
(active job, SSE connection, API latency, build SHA, WASM fingerprint).

41.1 Overview — `/`

- Purpose: what exists in this local instance right now. Not a KPI wall.
- Data: `GET /api/v1/investigations?limit=10`, `GET /api/v1/scenarios`,
  `GET /api/v1/runs/recent`, `GET /api/v1/datasets/summary`, `GET /api/v1/health`.
- Content: four dense lists — Recent investigations (id, scenario, verdict chip, cut size, bundle
  hash, time), Recent proof runs (mode, verdict, flags, checker result, duration), Datasets
  (seed, completeness, event count), Degraded/unhealthy services.
- Actions: open investigation; run scenario; continue last proof.
- Empty: "No scenarios have been run in this instance. `spectra scenario run --id lateral-01`
  or press Run scenario." with a button.
- Done: no computed aggregates on this screen; every row links to its detail route.

41.2 Investigations — `/investigations`

- Purpose: list and filter reconstructions.
- Data: `GET /api/v1/investigations?q&status&severity&sort&page` (server-side filter/sort/page).
- Columns: id (mono), scenario, window (start → end, mono), events ingested, entities resolved,
  dimensions touched, verdict chip, flags, bundle hash, created.
- Actions: open; compare two selected (opens Replay Lab with both); delete run; export bundle.
- Empty (no data): as Overview. Empty (filters exclude everything): "0 of 47 investigations match.
  Clear filters." — the *unfiltered* total is always shown.

41.3 Investigation Detail — `/investigations/:invId` (flagship triptych)

- Purpose: reconstruct, inspect and challenge a single incident.
- Data: `GET /api/v1/investigations/{id}`, `/timeline?from&to`, `/facts?at=t`, `/transitions?at=t`,
  `/hypothesis`, `/evidence/{eventId}`, `/liveness`.
- Layout: three resizable columns (default 22% / 52% / 26%), sizes persisted per user, encoded in
  `panel` search param when changed.

```
+--------------------------------------------------------------------------------------------+
| investigation inv_7f31c2  scenario lateral-01  bundle blake3:9c41ab…07de   [ROBUST] [flags:0]|
| cursor 2026-03-14 09:41:07.312Z          [<] [,] [ play ] [.] [>]        [fit] [\] [?]      |
+------------------+---------------------------------------------------+---------------------+
| TIMELINE RAIL    | STATE TRANSITION GRAPH                            | EVIDENCE INSPECTOR   |
|                  |                                                   |                      |
| 09:38:02 ▪ auth  |     (identity)            (session)               | selected             |
| 09:38:44 ▪ auth  |   svc_deploy ──issue──▶ sess_4a1 ──bind?──▶ ✕     |  fact  f:1042        |
| 09:39:10 △ netfl |        │                     │                    |  session.used(       |
| 09:40:55 ◆ proc  |        │                  ⌁GHOST⌁                 |    sess_4a1, host_9) |
| 09:41:07 ✕ proc  |        ▼                     ▼                    |  @ 09:41:07.312Z     |
| 09:41:09 ✕ netfl |   (credential)          (privilege)               |                      |
| 09:41:40 ⊘ egres |   cred_ci ──use──▶ role_admin ──▶ (resource)      | derivation           |
|                  |                                   s3_backups      |  rule R17 session_use|
| ░░ blind ░░      |                                                   |   ├ evt:e8831 authlog|
| iam_audit        |  legend: · normal △ watch ◆ anomalous             |   ├ evt:e8834 proc   |
| 09:39:55–09:44:10|          ⊘ blocked ✕ compromised ? unknown        |   └ GHOST lic:L3 ⌁   |
|                  |          ⌁ GHOST (licensed silent, not observed)  |                      |
| 240 bins,        |                                                   | raw record  [copy]   |
| 3412 events      |  [layout: dagre|force]  [depth 3]  [1,204 nodes]  |  {"ts":"…","src":…}  |
+------------------+---------------------------------------------------+---------------------+
| 3412 events · 118 entities · 2104 rule instances · 37 GHOST · liveness: 2 blind, 1 suppressed |
+--------------------------------------------------------------------------------------------+
```

- Rail: one mark per event, coloured by state glyph, grouped by source lane; blind intervals drawn
  as cross-hatched bands labelled with source and interval; suppressed intervals additionally
  carry the `chain break` icon and the offending sequence number.
- Graph: OR-nodes = facts (rounded rect, dimension in small caps), AND-nodes = rule instances
  (small square, rule id). Blocked edges render `⊘` with the control atom that blocks them.
  GHOST instances render dashed/cross-hatched and are excluded from every observed-event count.
- Inspector: selected fact or event; derivation tree with real `EventId` leaves, each leaf
  expandable to the raw normalized record and the original line offset in `bundle.jsonl`.
- Actions: set cursor from any mark; pin a fact; open in Reconstruction; open in Proof with this
  investigation's bundle; export selection as evidence pack.
- Empty: if the investigation has no derived facts, the graph column shows "No facts derived at
  this cursor. 3,412 events ingested, 0 rules fired — check rule table version." with a link to
  Rules.

41.4 Timeline — `/timeline`

- Purpose: cross-investigation event stream with source lanes and liveness overlay.
- Data: `GET /api/v1/events?from&to&src[]&dim[]&cursor` (keyset pagination), `/liveness`.
- Content: virtualized event table (ts, source, seq, chain ok, entity, dimension, state glyph,
  summary) plus a density band per source and blind/suppressed overlays.
- Actions: filter by source/dimension; jump to cursor; open evidence; toggle GHOST visibility
  (default off; when on, GHOST rows are visually separated and counted separately).
- Empty: "No events in 2026-03-14 09:00 → 10:00 for sources [authlog]. Widen the window or clear
  source filter."

41.5 Entities — `/entities`

- Purpose: resolved entity inventory.
- Data: `GET /api/v1/entities?q&kind&sort&page`.
- Columns: entity id (mono), kind (identity / session / credential / privilege / process / host /
  network endpoint / api client / service / resource / trust anchor), display name, alias count,
  resolution confidence source (which rule merged it — never a numeric score), first seen, last
  seen, current state glyph at cursor.
- Actions: open; view merge provenance; split-check (shows the evidence that caused a merge).
- Empty: "Entity resolution has not run for this bundle."

41.6 Entity Detail — `/entities/:entityId`

- Purpose: everything known about one entity, over time.
- Tabs: State history (per-dimension lane chart against the shared cursor), Events, Relations
  (graph neighbourhood), Merge provenance (which records were unified and by which rule),
  Facts (derived atoms mentioning this entity), Blind coverage (intervals where sources that would
  observe this entity were not live).
- Actions: pin to comparison tray; set cursor to first anomalous transition; open in State Explorer.
- Empty per tab, e.g. Relations: "No relations at or before the cursor. This entity first appears
  at 09:40:55."

41.7 Security State Explorer — `/state`

- Purpose: scrub time and watch the security state of the whole system evolve, per dimension.
- Data: `GET /api/v1/state?at=t&dim[]`, `GET /api/v1/state/transitions?from&to`.
- Layout: dimension lanes (identity, session, credential, privilege, process, network, api,
  service, resource, trust), each a horizontal band of state segments; the scrubber below drives
  everything.

```
+--------------------------------------------------------------------------------------------+
| SECURITY STATE EXPLORER          at 2026-03-14 09:41:07.312Z        [dims ▾] [entity ▾]     |
+--------------------------------------------------------------------------------------------+
| identity    ················△△△△△◆◆◆◆◆◆◆◆✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕ |
| session     ·····················????????⌁⌁⌁⌁⌁◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆ |
| credential  ·································································◆◆◆◆◆◆◆◆◆◆◆◆◆ |
| privilege   ·············································✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕ |
| process     ···························◆◆◆◆◆✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕✕ |
| network     ························△△△△△△△△△△△△△△△△△△△△△△△⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘⊘ |
+--------------------------------------------------------------------------------------------+
| SCRUBBER                                                                                     |
| 09:38:00                          ▼ cursor 09:41:07.312                           09:46:00   |
| |---------------------------------|------------------------------------------------------|  |
| |  ▪▪ ▪  ▪▪▪   ░░░░░░░░░░░░░░  ▪▪▪ | ▪ ▪▪▪▪   ▪▪▪    ▪▪  ▪        ▪▪▪                     |  |
| |          ^iam_audit BLIND     ^chain break authlog seq 40122                            |  |
| [⏮] [◀ ,] [ ▶ play 1× ] [. ▶] [⏭]   snap: [event|transition|blind edge]   window [15m ▾]    |
+--------------------------------------------------------------------------------------------+
| at cursor: 118 entities · 41 facts true · 6 unknown (no live source) · 3 GHOST-derived        |
+--------------------------------------------------------------------------------------------+
```

- Unknown segments are cross-hatched `?`, never rendered as `normal` and never as a gap.
- Actions: play/pause, speed 0.25×–8× (stepping is discrete over real events, never interpolated),
  snap mode, dimension filter, entity focus, copy deep link at cursor.
- Empty: "Bundle covers 09:38:00 → 09:46:00. The requested cursor 11:02:00 is outside the bundle."

41.8 Attack Reconstruction — `/investigations/:invId/reconstruction`

- Purpose: the hypothesis as an explicit, evidence-backed structure.
- Data: `GET /api/v1/investigations/{id}/hypothesis`, `/hypergraph?depth`, `/goal`.
- Content: ordered attack steps (technique label from the rule table, not from an external
  taxonomy claim), each with: rule id, time, entities, evidence event ids, whether any step in the
  chain is GHOST, and the licenses relied upon. A right pane shows the AND/OR hypergraph with the
  goal atom highlighted.
- Actions: expand step to derivation tree; jump cursor to step; "Why not blocked?" opens Proof with
  the current control configuration and this goal; export step list as JSON.
- Empty: "No derivation of the goal atom `resource.exfiltrated(s3_backups)` exists under P_min or
  P_max. Goal unreachable with this rule table." — this is a result, displayed as such.

41.9 Replay Lab — `/replay`

- Purpose: run the identical scenario under two control configurations and diff the outcomes.
- Data: `POST /api/v1/replay {scenario, baseline_cfg, variant_cfg, seed}` → job; result
  `GET /api/v1/replay/{runId}` with aligned step lists and a divergence index.
- Guarantee shown on screen: same seed, same bundle hash, byte-identical baseline re-run
  (`baseline re-run hash matches: yes`). If it does not match, the screen renders an error, not a
  diff.

```
+--------------------------------------------------------------------------------------------+
| REPLAY LAB   scenario lateral-01   seed 0x5EED0001   bundle blake3:9c41ab…07de              |
| A: baseline  mfa=1 session_binding=0 egress_seg=0        B: variant  mfa=1 session_binding=2 |
| determinism: A re-run hash matches (blake3:71b0…9ac2)    [step 14 / 38]  [◀] [▶] [play] [⤓] |
+---------------------------------+----------------------------------------------------------+
| A — BASELINE                    | B — VARIANT                                              |
|  1 ✓ auth.success svc_deploy    |  1 ✓ auth.success svc_deploy            same             |
|  2 ✓ session.issued sess_4a1    |  2 ✓ session.issued sess_4a1           same             |
|  …                              |  …                                                       |
| 13 ✓ session.used host_9        | 13 ⊘ session.used host_9    BLOCKED  session_binding≥2   |
| 14 ✓ priv.escalate role_admin   | 14 — not reached                        DIVERGE ◀ here   |
| 15 ✓ resource.read s3_backups   | 15 — not reached                                        |
| 16 ✕ resource.exfiltrated       | 16 — not reached                                        |
|                                 |                                                          |
| outcome: GOAL REACHED @ step 16 | outcome: TERMINATED @ step 13 (control session_binding)  |
+---------------------------------+----------------------------------------------------------+
| divergence: first at step 13 · 4 steps unreachable in B · evidence: evt:e8834, evt:e8836     |
| [why blocked?] [open in Proof] [copy deep link] [export replay.json]                         |
+--------------------------------------------------------------------------------------------+
```

- Rows align by causal step index; unmatched steps show `—` with "not reached", never a blank cell.
- Actions: step forward/back, play at 1 step/500 ms, jump to first divergence, swap A/B, promote
  variant to the current control configuration, export.
- Empty: "Pick a scenario and two control configurations. B defaults to A with no controls."

41.10 What-If Controls — `/controls`

- Purpose: edit the control configuration that Replay and Proof consume.
- Data: `GET /api/v1/controls` (catalogue with ordered levels, level descriptions, guard AST
  excerpt, `producing_sources` affected), `GET /api/v1/costs` (user-authored; may be absent).
- Content: one row per control `c_k`, a segmented level selector `0..m_k` with each level's exact
  semantic text taken from `controls.toml`, the threshold atoms it induces (`x_{k,ℓ}`), the rules
  whose `blockers` mask mentions it, and the declared cost if `costs.toml` exists.
- Actions: set level; reset to scenario default; copy `cfg` string; run replay; run proof.
- Empty cost state: "No costs.toml loaded. Cost columns and the cost/residual frontier are
  unavailable." — never a placeholder or invented figure.
- Negative: do not show a recommendation, a "suggested" configuration, or a security score.

41.11 Proof — ECLIPSE — `/proof` (flagship mechanism screen)

- Purpose: compute and display the evidence-licensed cut proof, and let an independent checker
  validate it in front of the user.
- Data: `POST /api/v1/proof {scenario, cfg, mode}` → job; `GET /api/v1/proof/{id}` →
  `{verdict, mode, cut, psi, corridors, lower_bound, licenses_used, flags, cert_hash}`;
  `GET /api/v1/cert/{hash}`; `POST /api/v1/verify {cert_hash}` streams the Go checker's stdout.
- Regions:
  1. Header: verdict chip, mode (ROBUST / OPTIMISTIC), minimum cut rendered as atoms
     `{session_binding≥2, egress_seg≥1}`, `|S|`, lower bound, corridor count, cert hash chip,
     flags strip (each flag a chip with its meaning and the consequence).
  2. Corridor list (virtualized): each irreducible corridor with the atoms that hit it, the
     rule instances forming it, and whether it depends on a license.
  3. Blindness premium panel: `S_rob \ S_opt` with, per control, the licenses responsible
     (source, interval, basis Blind|Suppressed, witness event ids) and the sentence
     "in the cut only because <source> was blind over <interval>".
  4. Counterexample pane: removing a control from the cut renders its derivation tree down to real
     `EventId` leaves; GHOST nodes marked and licensed.
  5. Decisive observation set: minimum (source, window) pairs that would collapse remaining
     ambiguity, with "exact (≤3)" or "greedy, ln n + 1 bound" stated explicitly.
  6. Cost/residual frontier: Pareto points from the knapsack, each annotated with its cut; hidden
     entirely when no `costs.toml` is loaded.
  7. Checker pane: a monospace terminal region streaming the Go checker.

```
$ spectra verify cert_3f9a1c8d20.json
reading rules.toml        blake3:11ce…a4     OK
reading bundle.jsonl      blake3:9c41ab…07de OK
reading liveness.json     blake3:5d20…b1     recomputed, matches
grounding                 2104 instances (37 silent, all licensed)
(a) axioms subset U       OK
(b) closure               OK   2104/2104 instances checked
(c) goal not in U         OK   resource.exfiltrated(s3_backups)
(d) licenses admissible   OK   3/3 licenses re-derived from liveness
(e) redundancy witnesses  OK   2/2 witnesses re-derive goal under S\{c}
(f) no smaller cut        OK   searched 64 masks of popcount 1 against Psi(6)
VERDICT: ROBUST                                                          11ms
```

- Actions: PROVE (`p`), run checker (`v`), toggle a control and re-prove, download `cert.json`,
  verify a dropped `cert.json` locally with the WASM integrity module, permalink.
- Empty: "No proof has been run for scenario lateral-01 at cfg `mfa=1,session_binding=0`.
  Press PROVE."
- Negative: the verdict chip may not appear before the checker section exists in the DOM; a proof
  whose checker has not been run shows `checker: not run` in the header, never an implied pass.

41.12 Evidence & Integrity — `/evidence`

- Purpose: the raw substrate and its verifiability.
- Data: `GET /api/v1/bundles`, `/bundles/{hash}/sources`, `/bundles/{hash}/chain`,
  `/evidence/{eventId}`, `/liveness`.
- Content: per-source table (records, seq range, chain status INTACT/GAP/BROKEN, q99 inter-arrival,
  live intervals, blind intervals, suppressed intervals with the break location); event lookup by
  id showing the normalized record, the raw line, the Merkle proof, and every fact derived from it.
- Actions: drop a `bundle.jsonl` or `cert.json` to verify locally (WASM, no upload — stated in the
  UI); copy Merkle proof; export evidence pack for a selected fact.
- Empty: "No bundles registered. Generate one: `spectra dataset gen --seed 0x5EED0001`."

41.13 Scenarios — `/scenarios`

- Purpose: the synthetic attack scenarios and their ground truth.
- Data: `GET /api/v1/scenarios`, `/scenarios/{id}` (steps, goal atom, generator seed, ground-truth
  chain, control defaults).
- Content: scenario card with the declared ground truth (since the generator knows it), the goal
  atom, horizon `k`, and the ground-truth-vs-reconstruction comparison for the last run.
- Actions: run; run degradation sweep; open ground truth; open bundle.
- Empty: "No scenarios found in `scenarios/`."

41.14 Rules — `/rules`

- Purpose: read the rule table that everything else is relative to.
- Data: `GET /api/v1/rules` (parsed `rules.toml`), `/rules/{id}` with guard AST, the generated Rust
  for kernel and simulator, `producing_sources`, `silent_possible`, provenance note, and the
  obligation axioms with their must-fire / must-not-fire unit tests.
- Content: searchable table; per-rule detail shows head, body, guard expression, blocker mask,
  instance count in the current bundle, and a link to instances in the hypergraph.
- Actions: filter to `silent_possible`; show obligation axioms; copy rule id; open instances.
- Empty: "rules.toml declares 0 rules — the reconstruction core cannot run."

41.15 Benchmarks — `/benchmarks`

- Purpose: measured performance, published rather than claimed.
- Data: `GET /api/v1/benchmarks/suites`, `/benchmarks/runs/{id}` (per-stage timings, instance
  counts, corridor counts, memory, host fingerprint, commit SHA).
- Content: per-stage table (ingest, resolve, ground, liveness, fixpoint, hitting-set, knapsack,
  checker) with n, p50, p95, max, and the input size that produced them; history chart per stage
  over commits; the grounding cap and whether it was hit.
- Empty: "No benchmark runs recorded. `make bench` writes to `bench/results/`."
- Negative: no projected numbers, no numbers from a different machine presented as this one's, no
  "up to" phrasing. Every row carries its host fingerprint.

41.16 Research — `/research`

- Purpose: the degradation and tampering axis, as figures generated from real runs.
- Data: `GET /api/v1/research/degradation` (100%→30% completeness matrix × tamper modes:
  delete, delay, duplicate, reorder, corrupt, suppress), `/research/figures/{id}`.
- Content: the completeness × tamper heatmap of reconstruction quality (recall of ground-truth
  chain steps, GHOST count, blindness premium size, verdict distribution), and the invariant panel
  "false ROBUST verdicts: 0 / 1,540 cells" with a link to the cell-level table.
- Actions: open a cell (loads that bundle in Investigation Detail), export CSV, export figure SVG.
- Empty: "Degradation matrix has not been generated. `make research-matrix` (≈18 min, 1,540 runs)."

41.17 Datasets — `/datasets`

- Purpose: generated data provenance.
- Data: `GET /api/v1/datasets` (seed, generator version, completeness, tamper profile, event count,
  entity count, bundle hash, ground-truth hash).
- Actions: generate with a seed; regenerate and confirm byte-identical hash; delete; open.
- Empty: "No datasets. Generate one with a seed."

41.18 System Health — `/health`

- Purpose: is this local instance actually working.
- Data: `GET /api/v1/health` (api, postgres, redis, rust kernel binary version, go checker binary
  version, wasm module hash, disk, queue depth, last migration).
- Content: one row per component, state glyph, version, last check, latency. Failed components show
  the exact error text from the backend.
- Empty: not possible; if the API is unreachable the screen renders the connection error and the
  command to start the stack.

41.19 Settings — `/settings`

- Tabs: Appearance (theme auto/dark/light, density comfortable/compact, reduce motion override),
  Time (display timezone — UTC default, absolute-only vs absolute+relative), Data (grounding cap,
  horizon default, GHOST visibility default), About (versions, commit SHA, WASM fingerprint,
  rule-table hash, licence, "SPECTRA proves properties of the model, not of reality" statement
  verbatim from section 9 of the ECLIPSE spec).
- Negative: no account, no telemetry opt-in, no remote sync, no API keys.


============================================================
42. INTERACTION CONTRACT
============================================================

These rules are non-negotiable. Each is testable; each has a named test. A pull request that
violates one is rejected regardless of visual quality.

42.1 Every claim is click-through to its evidence

1. Any rendered assertion — a fact, a transition, a state segment, an attack step, a cut member, a
   corridor, a verdict, a blind interval — is a click target that opens its derivation.
2. A derivation terminates in either real `EventId` leaves (with the raw normalized record and the
   byte offset in `bundle.jsonl`) or an explicit GHOST leaf carrying its `LicenseId`, source,
   interval, basis and witness events. There is no third kind of leaf.
3. Depth is unlimited: every intermediate fact in a derivation tree is itself expandable.
4. Test `evidence-reachability.spec.ts`: crawl every rendered assertion node on the reference
   investigation, click it, assert a derivation opens, assert every leaf resolves to an evidence
   record or a license record. Zero dead ends.

42.2 Nothing is displayed that the backend did not compute

1. Every number, label, verdict and colour on screen maps to a field in a validated API response.
2. The frontend may format and lay out. It may not derive. (See 39.4 rule 3 and its lint gate.)
3. No placeholder content, no lorem ipsum, no mock data in any code path reachable from `main.tsx`.
   Fixtures live only under `src/**/__fixtures__/` and MSW handlers, excluded from the production
   bundle by a Rollup guard that fails the build if `__fixtures__` appears in the output graph.
4. Test `no-derived-values.spec.ts` snapshots every numeric DOM node on each route against the API
   response bodies captured in the same run and asserts each value appears verbatim in a response.

42.3 Unknown is rendered as unknown

1. Absent data renders as the `unknown` state: cross-hatch, `?` glyph, the literal word "unknown".
2. It is never rendered as `0`, `—` alone, `N/A`, an empty cell, a zero-height bar, a gap in a
   line, or `normal`.
3. Counts distinguish three quantities wherever both exist: observed, unknown, GHOST. A total that
   merges them is forbidden; totals are written `41 true · 6 unknown · 3 GHOST-derived`.
4. GHOST elements are excluded from every count labelled "events", "observed", or "ingested". A
   tooltip on any GHOST element repeats: "Licensed silent step. Not an observed event."
5. Test `unknown-rendering.spec.ts`: feed responses with nulls and blind intervals into every
   route; assert no `0`, `-`, `N/A` or empty cell appears where the field is null.

42.4 Every score shows its formula

1. There are no probabilities and no confidence scores in SPECTRA. The quantities that do exist —
   `red(i,j)` redundancy index, corridor counts, `|S|`, lower bound, blindness-premium size,
   degradation recall, q99 inter-arrival, coverage of the decisive observation set — each expose a
   formula popover on hover and on keyboard focus (`Shift+F1` on the focused element).
2. The popover schema is fixed:

```ts
interface FormulaPopover {
  symbol: string;        // "red(i,j)"
  definition: string;    // "|corridors hit by both| / |corridors hit by either|"
  substitution: string;  // "4 / 9"
  value: string;         // "0.444"
  scope: string;         // "scenario lateral-01, P_max, 6 corridors"
  inputs: Array<{ label: string; href: string }>; // links to the corridor list, liveness, etc.
  exactness: 'exact' | 'greedy (ln n + 1 bound)' | 'capped';
  computedBy: string;    // "rust kernel v0.7.2, eclipse::redundancy"
}
```

3. Any value whose `exactness` is not `exact` renders with the FLAGGED cross-hatch treatment and
   the qualifier inline, not only in the popover.
4. Test `formula-popovers.spec.ts`: every element with `data-metric` must produce a popover
   containing a `substitution` string whose arithmetic evaluates to `value`.

42.5 One shared temporal cursor

1. A single Zustand slice `state/cursor.ts` holds `{ t: Instant, source: 'url'|'rail'|'scrub'|
   'keyboard'|'link' }`. Every panel subscribes; no panel keeps its own time.
2. Changing the cursor updates the URL `t` param (replace, not push, while scrubbing; push on
   discrete jumps) and re-renders all panels against the same instant within one frame.
3. The cursor snaps to real events, real transitions or blind-window edges according to the snap
   mode. It never interpolates between events and never implies state between observations.
4. Panels that cannot answer at the cursor render `partial`/`unknown` for that instant, never the
   last known value silently carried forward. Carry-forward, where the model genuinely defines it
   (a fact true from `t` onward until its time-indexed successor is not derived), is drawn with a
   distinct lower-opacity continuation and labelled "held since 09:39:10".
5. Test `cursor-sync.spec.ts`: set `t` via URL, keyboard, rail click and scrub; assert the rail
   marker, graph highlight, state lanes, inspector header and status bar all report the identical
   instant string.

42.6 Replay diff is step-wise and manually steppable

1. The diff animates one causal step at a time at 500 ms per step; `◀`/`▶` step manually; `Space`
   plays/pauses; the step index is in the URL (`step`).
2. Animation never runs before the full result is loaded; there is no progressive reveal that could
   be mistaken for live computation.
3. The divergence step is marked, addressable (`#step-13`), and explains itself: which control at
   which level blocked which rule instance, with evidence ids.
4. Steps that do not exist in one side render "not reached", with the reason (blocked by control X,
   or precondition fact never derived). Never blank.
5. Determinism is asserted on screen: the baseline re-run hash is displayed and compared. If it
   differs, the diff is replaced by an error panel; a non-deterministic replay is never shown as a
   result.
6. Test `replay-step.spec.ts`: step through all 38 steps with the keyboard, assert URL updates,
   assert reverse stepping reproduces identical DOM at each index.

42.7 Deep links encode full view state

1. Every screen is restorable from its URL alone: route params, cursor, selection, filters, panel
   sizing, control configuration, proof mode, selected corridor, certificate hash.
2. `Ctrl/Cmd+L` copies the current deep link; a toast confirms with the character count.
3. Links are stable across runs when the underlying artefacts are content-addressed: a proof link
   carries `cert=blake3:…` so it resolves to the same certificate or to an explicit
   "certificate not present in this instance — import cert.json" state.
4. Test `deep-link-roundtrip.spec.ts`: for each route, perform a scripted interaction, copy the
   link, open it in a fresh context, assert a pixel-identical screenshot and identical
   `data-state` attributes.

42.8 Additional non-negotiables

1. **No hidden work.** Any action that takes over 300 ms shows a determinate progress indicator fed
   by server-reported progress, names the stage ("grounding 1,204 / 2,104 instances"), and is
   cancellable. Cancel aborts the request with `AbortSignal` and tells the backend to kill the job.
2. **No destructive action without a typed confirmation** naming the artefact (delete dataset,
   delete run). Undo is not offered where it does not exist.
3. **Copy is available on every identifier**: event id, fact id, entity id, rule id, hash, cut,
   `cfg` string, corridor, deep link. One click, monospace, toast confirms.
4. **Errors are actionable**: problem type, human sentence, the exact CLI command or next step, and
   a "Copy diagnostics" button. No error toast that disappears before it can be read; errors in the
   result path are panels, not toasts.
5. **Flags are never suppressed.** `grounding_capped`, `subset_minimal_only`, `greedy_cover` appear
   in the header of every screen that consumes the affected result, in exports, and in the deep
   link. A flagged proof rendered without its flags is a release-blocking defect.
6. **Scope statements are attached, not buried.** The Proof screen footer states verbatim:
   "Soundness is relative to the rule table, entity resolution, the declared control catalogue and
   the telemetry ingested. ROBUST means: holds for every hypothesis the licenses admit under this
   catalogue. This is not formal verification of any real system."
7. **The LLM narration pane, where present, is clearly demarcated**, labelled "Narration (generated
   text over computed structures)", collapsed by default, and every sentence in it is anchored to
   the computed object it describes. Narration may not introduce a number, a verdict, an entity or
   a claim absent from the structure it narrates; a post-check rejects narration containing tokens
   not present in the source structure and renders "narration withheld: unanchored content".
8. **Latency budgets** (reference bundle, local Docker, mid-range laptop): route transition < 200 ms
   to first meaningful paint; cursor scrub < 100 ms to repaint; evidence popover < 80 ms; proof
   header render < 50 ms after job completion; checker pane first line < 300 ms after invocation.
   Playwright asserts each; regressions fail CI.
