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

## Phase 1 — Inventory (read-only, no edits)

Collect every place color or background appearance is set. Current known
surface area (verify against the live tree, this list may drift):

**Stylesheets** — `static/css/*.css`
- `main.css`, `index.css`, `blog.css`, `showcase.css`, `forms.css`,
  `osrs_graphs.css`, `price_graph_modal.css`, `shader_editor.css`,
  `supercombats.css`, `taskbar.css`
- No `:root` or CSS custom properties exist anywhere yet — every color is a
  raw literal (`grep -n "background\|color:" static/css/*.css` to enumerate).
- The classic Win98 bevel palette (`#c0c0c0` face, `#dfdfdf` highlight,
  `#808080`/`#404040` shadow, `#0000ff`→`#8080ff` title-bar gradient) is
  repeated independently across most of these files rather than shared.

**Inline `<style>` blocks in templates**
- `templates/index.html`
- `templates/partials/register.html`
- `templates/forms/forgot-password-form.html`
- `templates/osrs/goading_regens.html`
- (Re-check `templates/partials/login.html` and any other template — new
  inline blocks may have been added since this prompt was written.)

**Inline style/color set from JS** (bypasses CSS entirely — these need
their own fix, a stylesheet swap can't reach them)
- `static/js/register.js:70` — `errorMessage.style.color = "red"` hardcoded,
  not theme-aware.
- Everything else in `static/js/*.js` that touches `.style.*` is
  layout/visibility (`display`, `width`, `height`, `position`, `zIndex`) —
  not a theming concern, leave alone.

**Adjacent but distinct system — do NOT fold in casually**
- `static/js/index_background.js` + `static/glsl/indexBGShader.glsl` drive
  the WebGL lava-lamp background via shader uniforms
  (`color1R/G/B`, `color2R/G/B`, `color2MixAmount`, wave params), configured
  through a color/wave editor UI (`static/css/shader_editor.css`,
  `static/js/shader_editor.js` — see recent commit "Update background
  config. Improve BG menu to include color and wave editing.").
  This is a parallel color system (shader uniforms, not CSS). Decide
  explicitly whether a "theme" should also swap the shader's default
  color1/color2 values, or whether the shader stays independently
  configurable. Don't silently entangle the two mechanisms.

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

## Phase 2 — Design questions to resolve with the user before coding

- Where do theme tokens live? (Recommend: one `static/css/theme-*.css` file
  per theme, each defining the same fixed set of CSS custom properties on
  `:root`; all other stylesheets consume `var(--token-name)` and stop
  declaring literal colors.)
- How is the active theme selected and persisted? (e.g. a `<link>` swapped
  by JS, or a `data-theme` attribute on `<html>` with all rules keyed off
  it, stored in `localStorage` and/or a user preference in `auth.users`.)
- Does "theme" include the WebGL background's palette, or is that always
  separately configurable via the existing shader editor?
- Minimum token set needed to cover everything found in Phase 1 — expect
  at least: window face / highlight / shadow / dark-shadow (the four bevel
  tones), title-bar gradient start/end, body background, link/accent color,
  text color, error/warning color (covers the `register.js` hardcode once
  that's moved into CSS with a class instead of inline style).

## Constraints

- Zero layout/spacing/functional changes — this is a pure color/background
  value extraction. If a rule mixes layout and color (e.g. a shorthand
  `border` declaration that sets both width/style and color), split it so
  only the color portion becomes a variable.
- Every existing visual appearance must be reproducible as "Theme: Default"
  — the refactor should be a no-op visually until a second theme is
  authored.
- Fix the `register.js:70` inline-color case by moving it to a CSS class
  rather than adding a JS-side theme branch.

## Phase 3 — Theme switcher UI

Build two draggable windows accessible from the main page:

### A — Theme Preview window (`GET /theme/preview`)

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

The preview renders using real Win98 CSS classes — no synthetic overrides —
so changes to `:root` vars are reflected immediately in every sample.

### B — Theme Manager window (`GET /theme/manager`)

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

**DB table** (in `accounts` database, `auth` schema):
```sql
CREATE TABLE IF NOT EXISTS auth.user_themes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    filename   VARCHAR(80)  NOT NULL,
    content    TEXT         NOT NULL,
    file_size  INTEGER      NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, filename)
);
```

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
