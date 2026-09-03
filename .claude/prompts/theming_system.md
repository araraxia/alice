# Theming System — Audit & Implementation Prompt

## Goal

Let the whole site (Win98-styled UI) switch between visual "themes" —
different color palettes / background treatments — via a single stylesheet
swap, without touching layout, spacing, or functionality. Getting there
requires two phases: (1) an audit of every hardcoded visual value, (2) a
refactor onto CSS custom properties plus a theme-switch mechanism.

Do not start Phase 2 until Phase 1's inventory has been reviewed with the
user — the amount of HTML/CSS de-duplication required directly shapes how
big this task is.

## Status (as of 2026-08-16)

Phases 1–3 below have shipped. This file now doubles as historical spec and
a punch list of what's still incomplete or was never covered by the original
write-up — treat the phase sections as "what was asked for," not "what's
still to do." Verified against the live tree:

- **Phase 1 (inventory)**: no standalone inventory document was ever
  produced — the refactor happened directly instead. Migration onto tokens
  is uneven file-by-file; see "Known gaps" below.
- **Phase 2 (tokens + mechanism)**: shipped, but resolved a few of the open
  design questions differently than this doc recommended — see inline notes
  in that section.
- **Phase 3 (switcher UI)**: shipped, and exceeded — Theme Preview and Theme
  Manager windows both exist and are wired into `templates/index.html`'s
  title bar, plus an entire third feature (a public Theme Gallery with
  ratings) was built with no spec in this file at all. See "Known gaps."
- **Chart & price-table appearance**: still not covered by any of the work
  above — split into a dedicated follow-up prompt,
  `.claude/prompts/theming_system_round2.md`, since it's new scope rather
  than an unfinished piece of what's specced here.

## Phase 1 — Inventory (read-only, no edits)

Collect every place color or background appearance is set. Current known
surface area (verify against the live tree, this list may drift):

**Stylesheets** — `static/css/*.css`
- `main.css`, `index.css`, `blog.css`, `showcase.css`, `forms.css`,
  `osrs_graphs.css`, `price_graph_modal.css`, `shader_editor.css`,
  `supercombats.css`, `taskbar.css`
- `theme-default.css` now exists and defines the token set (see Phase 2).
  Migration of the other files onto `var(--token)` is **uneven** — rough
  raw-literal-vs-`var()` counts from the live tree:
  - Fully migrated: `taskbar.css` (0 raw hex left, 9 `var()` uses)
  - Nearly done: `main.css` (1 raw / 30 `var()`), `index.css` (1 raw / 50 `var()`)
  - Partial: `blog.css` (11 raw / 35 `var()`), `forms.css` (4 raw / 3 `var()`),
    `supercombats.css` (6 raw / 5 `var()`), `shader_editor.css`
    (3 raw / 2 `var()`), `osrs_graphs.css` (13 raw / 7 `var()` — the
    `.osrs-tip` tooltip block specifically is untouched, tracked in round 2)
  - Barely started: `showcase.css` (38 raw / 7 `var()`)
  - Untouched: `price_graph_modal.css` (5 raw / 0 `var()` — tracked in round 2)
- The classic Win98 bevel palette (`#c0c0c0` face, `#dfdfdf` highlight,
  `#808080`/`#404040` shadow, `#0000ff`→`#8080ff` title-bar gradient) is now
  centralized in `theme-default.css` rather than repeated per-file, for the
  files that have migrated.

**Inline `<style>` blocks in templates**
- `templates/index.html`, `templates/partials/register.html`,
  `templates/forms/forgot-password-form.html`,
  `templates/osrs/goading_regens.html` — as originally listed.
- **New since this prompt was written**: `templates/osrs/herblore.html` has
  a substantial inline `<style>` block full of hardcoded colors
  (`#ffe6e6`, `#cc0000`, `#e6f3ff`, `white`, `#000080`, `#0000b0`,
  `#0000cc`, `#fff`, `#008000`, `#f0f4ff`, `#f5f5f5`, `#e8e8e8`) — not
  covered by the token migration at all. Needs the same treatment as the
  other inline-style templates.
- Re-check for any other new inline blocks before starting further work —
  this list has already drifted once.

**Inline style/color set from JS** (bypasses CSS entirely — these need
their own fix, a stylesheet swap can't reach them)
- `static/js/register.js:70` — **fixed**. No longer sets
  `errorMessage.style.color` inline; now assigns `className = "form-error"`
  and lets CSS own the color. Confirms the pattern to follow for any
  similar case found elsewhere (see round 2 for one: the OSRS price-table
  tooltip still does this).
- Everything else in `static/js/*.js` that touches `.style.*` is
  layout/visibility (`display`, `width`, `height`, `position`, `zIndex`) —
  not a theming concern, leave alone.

**Adjacent but distinct system — do NOT fold in casually**
- `static/js/index_background.js` + `static/glsl/indexBGShader.glsl` drive
  the WebGL lava-lamp background via shader uniforms
  (`color1R/G/B`, `color2R/G/B`, `color2MixAmount`, wave params), configured
  through a color/wave editor UI (`static/css/shader_editor.css`,
  `static/js/shader_editor.js`). This is a parallel color system (shader
  uniforms, not CSS).
  **Resolved**: the shader was kept independently configurable — its
  default `color1`/`color2` values are still hardcoded in
  `index_background.js` with no `var(--token)` involvement. Themes do not
  currently touch the background shader; that remains a deliberate
  separation, not an oversight.

Produce an inventory (table or list) of:
1. Every color/background declaration, grouped by file, with the raw value.
2. Every duplicated Win98-bevel-style rule block (e.g. the repeated
   3D-border gradient pattern) that appears near-identically in more than
   one file — these are refactor targets regardless of theming, since
   squashing them is a prerequisite for a single theme stylesheet to have
   universal effect.
3. Any place a color is computed or set outside CSS (JS inline styles,
   canvas/shader uniforms) that a stylesheet-only theme mechanism cannot
   reach.

## Phase 2 — Design questions (resolved)

- Where do theme tokens live? (Recommended: one `static/css/theme-*.css`
  file per theme, swapped wholesale.)
  **Resolved differently, and more granular than recommended**: there is a
  single `static/css/theme-default.css` defining the full token set on
  `:root`. On top of it, `theme_manager.js` maintains a live
  `<style id="live-theme-override">` element in `<head>` that can hold
  either a whole pasted-in CSS file's text, or a generated
  `:root { --token: value; ... }` block produced by a **per-token color
  editor** sub-window (not in the original spec — see Phase 3 gaps) that
  lets a user tweak individual tokens without writing CSS at all. Both
  sources can be combined.
- How is the active theme selected and persisted?
  **Resolved**: `static/js/theme.js` sets `data-theme` on
  `document.documentElement` and mirrors it to `localStorage["alice-theme"]`.
  There is no `auth.users` DB column for a theme preference — persistence
  is per-browser via `localStorage` only. (Separately, *saved custom CSS
  files* — the Theme Manager's save/load feature — are DB-backed and tied
  to the logged-in user; that's a different piece of state than "which
  theme is currently active.")
- Does "theme" include the WebGL background's palette, or is that always
  separately configurable via the existing shader editor?
  **Resolved**: stays separate — see "Adjacent but distinct system" above.
- Minimum token set — **delivered and exceeded**. `theme-default.css`
  defines ~35 tokens: the four bevel tones plus composite bevel
  box-shadows, title-bar gradient stops, accent color, a five-step text
  hierarchy (`--text` → `--text-disabled`), backgrounds, button gradients,
  status colors (error/success/info), code-block colors, **and** a tiled
  surface-overlay system (`--tile-image`, `--tile-overlay-base/alt`,
  targeted via `[data-theme-surface="striped|panel|inset|header"]`) for
  patterned/textured themes — a category the original minimum-token list
  didn't anticipate at all.

## Constraints

- Zero layout/spacing/functional changes — this is a pure color/background
  value extraction. If a rule mixes layout and color (e.g. a shorthand
  `border` declaration that sets both width/style and color), split it so
  only the color portion becomes a variable.
- Every existing visual appearance must be reproducible as "Theme: Default"
  — the refactor should be a no-op visually until a second theme is
  authored.
- Fix the `register.js:70` inline-color case by moving it to a CSS class
  rather than adding a JS-side theme branch. **Done** — see Phase 1.

## Phase 3 — Theme switcher UI

Build two draggable windows accessible from the main page:

### A — Theme Preview window (`GET /theme/preview`)

**Shipped** — `templates/theme/preview.html`, served by
`src/website/theme_router.py`, opened via a "Theme Preview" title-bar button
in `templates/index.html`. Coverage of the "must include" checklist below
was not re-verified line-by-line in this audit — confirm before relying on
it as a complete swatch catalog:

A compact, scrollable catalog of every UI element that responds to theme
tokens. Used to evaluate a loaded theme without navigating the whole site.
Must cover:

- **Bevel surfaces**: raised, sunken, pressed, canvas — as labelled boxes
- **Title bars**: one in active gradient, one in inactive gradient
- **Buttons**: normal, hover-state (via `.hover-demo` forced class), pressed
  (`:active`-forced), disabled
- **Form controls**: text input, checkbox (checked + unchecked side-by-side),
  radio (checked + unchecked), `w98-select-wrapper` dropdown
- **Typography**: `--text`, `--text-secondary`, `--text-muted`, `--text-disabled`
- **Status**: error block (`--error-bg` + `--error-text`), success text, info block
- **Code**: a `<pre>` block (`--code-bg`, `--code-text`), inline `<code>` chip
- **Color token swatches**: a grid showing each token name next to its color
  box using a `background: var(--token)` swatch element
- Chart/price-table swatches are intentionally **not** in this list — see
  round 2, which will need to extend this window once chart tokens exist.

The preview renders using real Win98 CSS classes — no synthetic overrides —
so changes to `:root` vars are reflected immediately in every sample.

### B — Theme Manager window (`GET /theme/manager`)

**Shipped and exceeded.** `templates/theme/manager.html`, served by
`src/website/theme_router.py`, opened via a "Theme" title-bar button in
`templates/index.html`. Matches the spec below, plus an undocumented
addition: a **per-token color editor** sub-window
(`ThemeManager._ensureColorEditorWindow()` in `static/js/theme_manager.js`)
that lets a user edit individual `--token` values live instead of only
uploading a whole CSS file — this extends the "Load section" beyond what
was originally specced and should be treated as part of the real contract
going forward.

A two-section draggable window for loading and persisting custom themes.

**Load section (works without login)**:
- A CSS `<input type="file" accept=".css">` file picker
- On file select, reads the CSS with FileReader and injects it as
  `<style id="live-theme-override">` in `<head>`, overriding `theme-default.css`
- Inject button to apply; a "Reset to default" button to remove the override
- Shows the filename and byte count of the loaded file

**Save / manage section (login required, hidden with prompt if logged out)**:
- A filename `<input>` (must end in `.css`, max 80 chars, alphanumeric + `-_. `)
- A "Save" button that POSTs the content of `#live-theme-override` to the
  server; disabled and shows "Load a CSS file first" if no override is active
- A file list table (filename | size | modified | [Load] [Download] [Delete])
  — "Load" fetches the file's content from the server and re-injects it as the
  live override; "Download" creates a Blob URL download; "Delete" sends DELETE

**Backend** (`src/website/theme_router.py`, blueprint prefix `/theme`):
- `GET  /theme/preview` → preview partial HTML
- `GET  /theme/manager` → manager partial HTML
- `GET  /theme/files`           `@login_required` → JSON list (no content field)
- `POST /theme/files`           `@login_required` → upsert by (user_id, filename)
- `GET  /theme/files/<id>`      `@login_required` → JSON with content field
- `DELETE /theme/files/<id>`    `@login_required` → delete, verify ownership
- CSRF (`X-CSRFToken` header on every mutating request) — **confirmed
  present** in `theme_manager.js` for save/delete/rate calls.

**DB table** (in `accounts` database, `auth` schema) — **as actually
implemented**, which differs from the original spec below in the `user_id`
column type, and adds a second table this prompt never specified:
```sql
CREATE TABLE IF NOT EXISTS auth.user_themes (
    id         SERIAL PRIMARY KEY,
    user_id    VARCHAR(36)  NOT NULL,  -- spec said INTEGER; actual auth.users id is UUID-shaped
    filename   VARCHAR(80)  NOT NULL,
    content    TEXT         NOT NULL,
    file_size  INTEGER      NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, filename)
);

-- Not in the original spec — backs the Gallery feature below
CREATE TABLE IF NOT EXISTS auth.theme_ratings (
    id         SERIAL PRIMARY KEY,
    user_id    VARCHAR(36) NOT NULL,
    theme_id   INTEGER     NOT NULL,
    value      SMALLINT    NOT NULL CHECK (value IN (-1, 1)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, theme_id)
);
```

`theme_router.py` also carries a runtime migration: if `user_themes` was
ever created with the old `INTEGER` `user_id`, it `ALTER`s both tables to
`VARCHAR(36)` on next request. Worth knowing if you're touching this table.

**Constraints**:
- Max 10 files per user; enforced server-side (check count before INSERT of new name)
- Max file size: 50 KB (51 200 bytes); enforced on both client (warn) and server (reject 400)
- Filename must match `^[\w\- .]{1,77}\.css$`
- All POST/DELETE endpoints require valid CSRF token via `X-CSRFToken` header
- Ownership is verified on every file fetch/delete by checking `user_id = current_user.id`

**Integration**:
- Add a "Theme" button to the title bar of the main index window (alongside existing "BG")
- Both windows open via the existing `WindowInitializer` + `OpenWindow` system
- The preview and manager windows are independent draggable windows (can be open simultaneously)
- `theme.js` already handles `localStorage` persistence — no change needed there

### C — Theme Gallery window (`GET /theme/gallery`) — not in the original spec, shipped anyway

Found during this audit with **no corresponding entry anywhere in this
prompt file**. A third title-bar button ("Gallery") in `templates/index.html`
opens `templates/theme/gallery.html`, backed by public endpoints on
`theme_router.py`:

- `GET  /theme/gallery` → gallery partial HTML
- `GET  /theme/gallery/files` → public, sortable list of all saved themes
  across all users (`?sort=rating|date&order=desc|asc`), each row including
  author username, upvote/downvote counts, and the requesting user's own
  vote if logged in
- `GET  /theme/gallery/<id>/content` → public, returns any user's saved
  theme CSS by id (no ownership check — by design, it's a public gallery)
- `POST /theme/gallery/<id>/rate` `@login_required` → toggle-style up/down
  vote (posting the same value twice removes the vote), backed by
  `auth.theme_ratings`

Since this exists and is live, it should be treated as part of the real
theming system contract, not an unofficial side feature. If it should stay
that way, it at minimum needs the "must cover" style checklist the other
two windows got; if it was meant to be temporary/experimental, that's worth
confirming with whoever built it rather than assuming.

## Known gaps / follow-up

- **CSS files not fully on tokens yet**: `showcase.css` (barely started),
  `blog.css`, `forms.css`, `supercombats.css`, `shader_editor.css` — see
  the raw-vs-`var()` counts in Phase 1. None of these block a "Theme:
  Default" no-op, but a second theme will visibly miss these surfaces.
- **`templates/osrs/herblore.html`** — newly found inline `<style>` block,
  fully hardcoded, not part of any inventory or migration pass yet.
- **Chart & price-table appearance** — three separate rendering paths
  (canvas-drawn graph, Chart.js modal, server-side matplotlib PNGs) still
  entirely outside the token system. Tracked in
  `.claude/prompts/theming_system_round2.md`.
- **Theme Preview window's coverage** — not re-verified against its "must
  cover" checklist in this audit; do that before treating it as exhaustive.
- **Theme Gallery** — confirm whether it's intentionally in scope for this
  system (see "Phase 3C" above) and, if so, give it the same level of spec
  rigor the other two windows have.
