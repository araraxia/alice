# Blog

## Overview

New sub-section of the website. The blog can function both in a window within the site's primary index page, or as it's own independant website page with modified styling to function better as a full page.

Maintain the retro-90s / w98 style.

The blog will have a date-based directory and optional author filters.

Users who are logged in may write blog-posts in markdown format. They can preview their blog before posting it. Once submitted, the blog post will be stored in the SQL server in database `<DATABASE>` in `blog`.`post` with the actual blog artical as a column, along with metadata such as author UUID, post datetime, last updated datetime, etc.

Users who are logged in my view their own blogposts, along with edit existing blog posts.

---

## UI / Display Modes

### Window Mode (Embedded)
The blog renders as a draggable window on the main index page, consistent with the site's existing window system. The window has a fixed default size but can be resized. It displays a paginated post list with a title, author, and date for each entry. Clicking a post opens the full post in a child window or replaces the current window content.

### Full-Page Mode
When navigated to directly (e.g. `/blog`), the layout expands to use the full page width with modified CSS. The W98-style chrome (title bar, borders, scroll bar styling) is preserved but the window is anchored full-width rather than floating. A breadcrumb trail or back button navigates back to the index.

---

## Post Browsing & Filtering

- **Date directory**: Posts are browsable by year and month (e.g. `/blog/2026/05`). A sidebar or dropdown lists available months that have at least one post.
- **Author filter**: A dropdown or clickable author tag filters the visible post list to entries from that author. Multiple authors can be selected.
- **Pagination**: Post lists are paginated (e.g. 10 posts per page). Page state is preserved in the URL (`?page=2`).
- **Anonymous access**: All published posts are publicly visible. No login is required to read.

---

## Writing & Editing

- **Markdown editor**: A textarea with a live preview panel side-by-side (or toggled). The preview renders the markdown using the same CSS applied to published posts so the author sees exactly what will appear.
- **Draft saving**: A draft is auto-saved to `blog`.`draft` (or a `status` column on `blog`.`post`) so the author can leave and return without losing work.
- **Submit flow**: On submission the post status is set to `published` and `post_datetime` is stamped. Edits update `last_updated_datetime` and preserve the original `post_datetime`.
- **Delete**: Authors can soft-delete their own posts (status `deleted`), removing them from public listings without permanently destroying the record.

---

## Database Schema

### `blog`.`post`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` (PK) | Generated on insert |
| `author_uuid` | `UUID` (FK → users) | |
| `title` | `VARCHAR(255)` | |
| `body` | `TEXT` | Raw markdown |
| `status` | `ENUM('draft', 'published', 'deleted')` | Default `draft` |
| `post_datetime` | `TIMESTAMPTZ` | Set on first publish |
| `last_updated_datetime` | `TIMESTAMPTZ` | Updated on every edit |
| `created_datetime` | `TIMESTAMPTZ` | Set on first insert |

### `blog`.`tag` *(optional, future)*

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` (PK) | |
| `post_id` | `UUID` (FK → post) | |
| `label` | `VARCHAR(64)` | e.g. `osrs`, `devlog` |

---

## Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/blog` | Public | Paginated post list, newest first |
| `GET` | `/blog/<year>/<month>` | Public | Posts filtered by month |
| `GET` | `/blog/post/<id>` | Public | Single post view |
| `GET` | `/blog/write` | Required | New post editor |
| `POST` | `/blog/write` | Required | Submit new post |
| `GET` | `/blog/edit/<id>` | Required (owner) | Edit existing post |
| `POST` | `/blog/edit/<id>` | Required (owner) | Save edited post |
| `POST` | `/blog/delete/<id>` | Required (owner) | Soft-delete post |

---

## Templates

- `templates/blog/index.html` — post list (window & full-page variants via a flag or separate template)
- `templates/blog/post.html` — single post view
- `templates/blog/editor.html` — write/edit form with preview panel
- `templates/partials/blog_window.html` — embedded window partial for the index page

---

## Backend Module

`src/website/blog_router.py` — Flask blueprint registered at `/blog`. Relies on `src/util/sql_helper.py` for DB access and `src/user_auth.py` for the `@login_required` guard.

---

## Styling Notes

- Post body rendered markdown should use a scoped CSS class (e.g. `.blog-post-body`) to avoid polluting global styles.
- Code blocks in posts should use a monospace font consistent with the retro theme.
- The date/author line beneath the post title uses the same muted-text treatment used elsewhere on the site.
- In window mode the post list scroll area uses the styled scrollbar already defined in `main.css`.
