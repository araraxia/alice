# Theming System, Round 2 — Chart & Price-Table Appearance

## Prerequisite

Round 1 (`.claude/prompts/theming_system.md`) shipped the base token system:
`static/css/theme-default.css` defines ~35 `--token` custom properties on
`:root`; `static/js/theme.js` selects/persists the active theme via a
`data-theme` attribute + `localStorage`; `static/js/theme_manager.js` lets a
user override tokens live via a `<style id="live-theme-override">` element,
either by uploading a whole CSS file or by editing individual tokens through
a per-token color-editor sub-window. Read that file's "Status" section
before starting — it also documents an unspecced Theme Gallery feature and
several CSS files still not migrated onto tokens, which are separate from
this round's scope.

## Goal

Bring OSRS price/volume chart rendering — and the price table embedded in
it — under the same theme system, so a loaded theme's colors show up in the
charts too, not just the surrounding Win98 chrome.

This is harder than round 1's CSS-token swap because **none of the three
chart rendering paths are CSS-driven**. A `data-theme` attribute change or a
`--token` override alone cannot repaint any of them — each one needs an
explicit "read the current theme's colors and redraw" step wired in.

## Phase 1 — Inventory (read-only, no edits)

Three separate rendering paths, verified against the live tree:

- **`static/js/osrs_graphs.js`** — the canvas-drawn interactive price/volume
  graph used on the main page (`templates/index.html`). Colors are drawn
  straight into the 2D canvas context, invisible to CSS entirely:
  - Hardcoded palette object at the top of the file (`const C = { high:
    '#FF8C00', low: '#3A8FD4', grid: '#D0D0D0', text: '#444444', zero:
    '#222222' }`) consumed by `ctx.strokeStyle`/`ctx.fillStyle` in
    `_drawLine()` and the axis/grid drawing.
  - Scattered inline hex literals for status messages passed to `_msg()`
    (`'#c00'` for errors, `'#888'` for "no data", `'#666'` default).
  - **The price table**: the hover tooltip's data rows (`.osrs-tip-row`,
    populated around the `${(r.high||0).toLocaleString()}` /
    `${(r.highVol||0)...}` template strings) set cell color via inline
    `style="color:${C.high}"` / `style="color:${C.low}"` — the same bypass
    pattern `register.js:70` had before round 1 fixed it (moved to a CSS
    class instead of an inline style). Do the same fix here.
  - The surrounding `.osrs-tip*` structural rules live in `osrs_graphs.css`
    and are a **partially-migrated** file: `.osrs-graph-canvas` already
    consumes theme tokens (`var(--shadow)`, `var(--panel-bg)`,
    `var(--highlight-alt)`, `var(--bevel-canvas)`), but the tooltip block
    (`.osrs-tip`–`.osrs-tip-row`) is still fully hardcoded (`#fff`, `#888`,
    `#ccc`, `#555`, `#ddd`, `#bbb`, `#eee`, `#f7f7f7`, `rgba(0,0,0,0.18)`).
- **`static/js/price_graph_modal.js` + `static/css/price_graph_modal.css`**
  — a separate, still-live Chart.js-based modal graph (routed through
  `src/website/osrs_router.py`, templated by
  `templates/osrs/price_graph_modal.html`; see
  `docs/osrs_interactive_graph_library.md` for how it relates to
  `osrs_graphs.js`). Fully untouched by round 1 on both sides:
  - JS: dataset `borderColor`/`backgroundColor` hardcoded per series
    (`#e74c3c` high, `#3498db` low, plus matching `rgba(...)` fills) inside
    the Chart.js config object.
  - CSS: none of the existing bevel/panel/text tokens are used anywhere in
    this file — white modal background, `#dee2e6` borders, `#f8f9fa`
    footer, `#6c757d` muted text, `#e74c3c` hover color are all literals.
- **`src/osrs/item_properties.py`** (~lines 673–881) — the price line graph
  and volume bar graph rendered server-side with matplotlib, returned as a
  base64 PNG. Hardcoded series colors (`#e74c3c`/`#3498db` price lines,
  `#2ecc71`/`#e67e22` volume bars, `black` axis/zero-line). This is the
  hardest case: the image is baked once per request on the server, before
  the client's chosen theme (a `localStorage` value the server never sees)
  is knowable to that process at all.

## Phase 2 — Design questions to resolve with the user before coding

- **How do the client-side renderers pick up the active theme's colors at
  draw time?** Both `osrs_graphs.js` (canvas) and `price_graph_modal.js`
  (Chart.js) run in the browser, where `data-theme` and any
  `live-theme-override` values are already available. Plausible approach:
  read the resolved values of new `--chart-*` tokens via
  `getComputedStyle(document.documentElement)` at draw/init time instead of
  hardcoding the `C` object / dataset colors, and re-run the draw when
  `AliceTheme` changes (round 1's `theme.js` exposes `window.AliceTheme` —
  check whether it fires a change event today, or needs one added, so chart
  code can subscribe instead of polling).
- **What happens to the matplotlib PNG?** It runs server-side per request
  with no access to the client's theme state. Options, roughly in
  increasing effort: (a) accept it stays a fixed palette regardless of
  theme, same as the WebGL shader; (b) have the client pass the active
  theme name as a query param/cookie the Flask route reads before choosing
  a hardcoded matplotlib color set per known theme (doesn't generalize to
  arbitrary user-uploaded theme CSS, only to named/first-party themes); (c)
  move this rendering client-side (Chart.js or canvas) so it can read
  `--chart-*` tokens directly like the other two. Don't default to (a)
  without surfacing the tradeoff — round 1 made an explicit, documented
  choice to keep the shader separate; this should be an equally explicit
  choice, not a fallback.
- **Fix the price-table inline-color bypass** in `osrs_graphs.js` the same
  way round 1 fixed `register.js:70`: a theme-aware CSS class on the
  tooltip row cells, not a JS-side color branch reading `C.high`/`C.low`.
- **Does the per-token color editor (round 1, `theme_manager.js`
  `_ensureColorEditorWindow()`) need entries for the new `--chart-*`
  tokens?** If chart colors become theme tokens, a user editing a theme
  live should presumably be able to tweak them from the same UI rather than
  only via a full CSS file upload.

## Minimum new token set

- `--chart-high`, `--chart-low`, `--chart-grid`, `--chart-axis-text`,
  `--chart-zero-line` — cover both the canvas graph's `C` object and the
  Chart.js dataset colors, so both renderers read the same source of truth.
- `--tooltip-bg`, `--tooltip-border`, `--tooltip-text` — for the
  `osrs-tip` price table specifically (distinct from the chart's own line
  colors).
- If Phase 2 lands on option (b) or (c) for matplotlib, the bar-chart pair
  (`--chart-vol-high`, `--chart-vol-low` or similar) will also need to
  exist, matching `#2ecc71`/`#e67e22` in `item_properties.py`.

## Constraints

- Same zero-layout/spacing rule as round 1 — this is a color-only change.
- Round 1's constraint on `register.js:70` established the fix pattern for
  inline JS color bypasses (CSS class, not JS branch) — apply the same
  pattern to the `osrs_graphs.js` tooltip rows here rather than inventing a
  new approach.
- Every existing visual appearance must be reproducible as "Theme: Default"
  once this lands — no-op visually until a second theme defines different
  `--chart-*` values.

## Phase 3 — Theme Preview window coverage

Round 1's Theme Preview window (`GET /theme/preview`,
`templates/theme/preview.html`) does not currently include a chart sample —
confirmed absent from its "must cover" checklist in round 1's spec. Once
the tokens above exist, add:

- A static high/low line-pair sample using `--chart-high`/`--chart-low`/
  `--chart-grid`/`--chart-axis-text`.
- A small `osrs-tip` tooltip mockup showing `--tooltip-bg`/
  `--tooltip-border`/`--tooltip-text`, so the price-table colors are
  checkable without opening a real graph.

Add these to the same swatch-grid pattern the rest of the preview window
already uses (real Win98 CSS classes, no synthetic overrides) rather than a
one-off chart-specific layout.
