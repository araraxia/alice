# Theming System, Round 3 — Standalone Pages, Neglected Templates & Token Vocabulary Gaps

## Prerequisite

Read `.claude/prompts/theming_system.md` (round 1 — token system + switcher UI)
and `.claude/prompts/theming_system_round2.md` (round 2 — chart/price-table
rendering, still unimplemented) first. This round covers neither of those; it
covers surface area both rounds missed or flagged once and never revisited.

## Goal

Find and record every remaining place a visual value is not reachable through
`theme-default.css` / `live-theme-override`, beyond what rounds 1–2 already
scoped. Read-only audit — no edits made producing this document.

## Phase 1 — Inventory (verified against the live tree)

### A. Standalone full-page templates bypass the theme mechanism entirely — new finding

Only four templates in the repo are complete `<!DOCTYPE html>` documents
rather than partials injected into `index.html` via `OpenWindow`:
`templates/index.html`, `templates/404.html`, `templates/500.html`,
`templates/forms/forgot-password-form.html`. Only `index.html` is fully
wired (theme-default.css + theme.js + data-theme + live-theme-override all
present). The other three are not:

- **`templates/404.html`, `templates/500.html`** — link only `main.css`.
  They do **not** link `theme-default.css`, so every `var(--token)`
  reference inside `main.css` (44 of them) resolves against undefined
  custom properties on these two pages specifically — not just "untheme-able"
  but likely rendering with missing bevels/backgrounds wherever `main.css`
  is relied on. Neither page sets `data-theme` or loads `theme.js`. All
  visible text bypasses CSS entirely via inline `style="color: #2f2f2f"`
  (three occurrences each). These are the two most broken pages in the
  audit, not merely unthemed ones.
- **`templates/forms/forgot-password-form.html`** — links
  `theme-default.css` + `forms.css` + `main.css`, so it renders correctly
  as "Theme: Default." But it never loads `theme.js` and never sets
  `data-theme`, so a user with a saved custom theme (localStorage value or
  an active `live-theme-override` elsewhere in the app) always sees Default
  here regardless of what they've set anywhere else. It also has one
  inline-styled success modal at line 41
  (`background-color:white; padding:20px; border:2px solid black`) — the
  same inline-bypass pattern round 1 fixed at `register.js:70`.

### B. Template `<style>` blocks — status refresh of round 1's list

Round 1 tracked five templates with inline `<style>` blocks as a flat list
without individually confirming which had since been migrated. Re-checked:

- **`templates/partials/register.html`** — **already fully tokenized**
  (`var(--panel-bg)`, `var(--shadow)`, `var(--accent)`, `var(--error-text)`
  throughout). Round 1's list still shows this as open; it isn't. Worth
  correcting so it doesn't get re-flagged as work needed.
- **`templates/osrs/herblore.html`** — confirmed still fully hardcoded
  (~26 raw color declarations: `#ffe6e6`, `#cc0000`, `#000080`, `#0000b0`,
  `#0000cc`, `white`, `#808080`, `#f0f4ff`, etc.), zero `var()` use. Matches
  round 1's description exactly — untouched since it was written.
- **`templates/osrs/goading_regens.html`** — **also fully hardcoded**,
  a near-identical ~26 raw color declarations, zero `var()` use. This was
  in round 1's original Phase 1 list (grouped anonymously with the other
  three "as originally listed") but, unlike herblore.html, never got its
  own call-out confirming it was still unmigrated. It's in exactly the same
  shape as herblore.html and should be tracked at the same priority, not
  silently assumed done because it wasn't named individually.
- **`templates/forms/forgot-password-form.html`** — see A; the gap here is
  page-level wiring, not the block's own colors (it has none of note beyond
  the one inline modal).

### C. CSS file migration — refreshed raw-literal-vs-`var()` counts

Rough counts from the live tree (raw hex/`rgba()` not inside a `var()` call,
vs. `var(--token)` uses), for comparison against round 1's numbers:

| File | Raw | `var()` | Round 1 said | Notes |
|---|---|---|---|---|
| `taskbar.css` | 0 | 12 | fully migrated | still true |
| `main.css` | 1 | 44 | 1 raw / 30 var | still negligible |
| `index.css` | 2 | 73 | 1 raw / 50 var | still negligible |
| `theme_manager.css` | 2 | 110 | not listed | effectively fully migrated |
| `blog.css` | 11 | 47 | 11 raw / 35 var | same raw count, more var adopted since |
| `forms.css` | 5 | 3 | 4 raw / 3 var | unchanged in shape |
| `supercombats.css` | 6 | 5 | 6 raw / 5 var | unchanged |
| `shader_editor.css` | 3 | 2 | 3 raw / 2 var | unchanged, deliberately partial (round 1) |
| `osrs_graphs.css` | 14 | 13 | 13 raw / 7 var | more tokens adopted, but the `.osrs-tip` block round 2 described is still 100% unaddressed |
| `showcase.css` | 39 | 7 | 38 raw / 7 var | essentially unchanged |
| `price_graph_modal.css` | 7 | 0 | 5 raw / 0 var | still fully untouched (round 2 scope) |
| `cat_loader.css` | 0 | 0 | n/a — added this session | no raw colors at all; relies entirely on already-tokenized `.w98-window`/`.title-bar` |

Two files are worth flagging beyond the raw count, because a meaningful
share of their remaining literals are values that **already exist as
tokens** and just aren't referenced:

- **`showcase.css`**: `#0a0884` (== `--accent` exactly), `#404040`
  (== `--text-dim`/`--shadow-dark`), `#fff`/`#ffffff` (== `--panel-bg`),
  `#e0e0e0` (close to `--body-bg`). A meaningful chunk of its 39 raw values
  is a mechanical `var()` swap, not new-token work.
- **`blog.css`**: `#c0c0c0` (== `--face` exactly) is one of its 11
  remaining raw values — same mechanical-swap case.

### D. Missing token: hyperlink color

No `--link` / `--link-visited` (or similar) token exists anywhere in
`theme-default.css`'s ~35-token set, despite `blog.css` hardcoding the
classic Win98 link blue `#0000ff` twice (lines 130, 258 — coincidentally
identical to `--titlebar-from`, but not referencing it). This is a gap in
the token *vocabulary* itself, not just an unmigrated file: right now no
theme author has any way to restyle link color anywhere on the site.

### E. Scrollbar styling — inconsistently themed, no category ownership in either prior round

Two files style `::-webkit-scrollbar`:
- `blog.css` — already fully tokenized (`background: var(--face)` track,
  `var(--shadow)` thumb).
- `showcase.css` — fully hardcoded, and for two *different* palettes: the
  sidebar variant is dark (`#1a1a1a` track, `#555`/`#666` thumb) while the
  main-content variant is light (`#f5f5f5` track, `#ccc`/`#bbb` thumb).

Neither prior round called out scrollbars as their own category — they're
buried in showcase.css's aggregate raw count. Note that showcase's sidebar
is a deliberately dark surface, unlike the rest of the Win98-gray chrome, so
it likely needs its own token pair rather than reuse of `--face`/`--shadow`
(see minimum additions below).

### F. Confirmed out of scope — consistent with prior rounds' decisions, not new gaps

- Static raster images (`static/images/favicon.png`, `crt-osrs-128x128.webp`,
  `crt-osrs-16x16.webp`, `sleeping_cat_140x80.webp`, `sleeping_cat_35x20.webp`)
  are fixed bitmaps — same category as the WebGL shader background
  (round 1) and the matplotlib chart PNGs (round 2), both already decided
  to stay independently configurable / outside the token system. Flagging
  only to confirm nothing quietly slipped outside that already-agreed
  boundary; not proposing new work here.
- No `<meta name="theme-color">` or web-app manifest exists, so mobile
  browser chrome (status bar tint) and any future PWA install color won't
  track the active theme. Cosmetic and low-value unless the site gains PWA
  ambitions — noted for completeness, not urgency.

## Suggested minimum additions

- `--link` (and `--link-visited` only if visited-state theming is wanted) —
  closes finding D.
- `--scrollbar-track` / `--scrollbar-thumb` (or a light/dark pair if
  showcase's two scrollbar variants are meant to stay visually distinct
  regardless of theme) — closes finding E.
- No new tokens needed yet for `goading_regens.html` / `herblore.html`:
  their reds/greens/blues (error/success/info-style colors, `#000080`-ish
  navy accents) look like they map onto existing `--error-text`,
  `--success-text`, `--info-text`/`--info-bg` almost one-to-one — confirm
  during implementation before inventing anything new.

## Phase 2 — Design questions to resolve with the user before coding

- **404/500**: bring fully into the theme system (theme-default.css +
  main.css + data-theme + theme.js), or keep them deliberately
  theme-independent as a "something broke, keep the failure page dumb and
  dependency-free" choice? Either is defensible — round 1/2 precedent is to
  make this an explicit, recorded choice rather than an accidental gap.
- **`forgot-password-form.html`**: wire in `theme.js`/`data-theme` so it
  matches the user's active theme, or leave it a deliberately
  always-Default auth-adjacent page? Same either/or framing.
- **`goading_regens.html` / `herblore.html`**: migrate both to tokens at
  the same time (they're in identical shape), and at what priority relative
  to round 2's chart work, which is still unstarted?

## Constraints

- Same zero-layout/spacing/functional-change rule as rounds 1 and 2 — pure
  color/background value extraction, nothing else.
- Every value identified in section C as already matching an existing token
  should be a mechanical `var()` swap, not a pretext to invent a new token.
- Every existing visual appearance must be reproducible as "Theme: Default"
  once this lands, same as prior rounds.
