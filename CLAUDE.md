# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alice is a personal Flask/WSGI web server and automation platform. Live at https://araxia.xyz/. It serves a retro Windows 98-styled UI, aggregates live OSRS item price data into PostgreSQL, hosts a blog, and runs personal automations.

## Running & Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server — restarts automatically on crash or Ctrl+C (Ctrl+C twice to stop)
python Test_Server_Loop.py

# Run server directly (single run, port 6969)
python alice_app.py
```

## Testing

There is no test suite. Ad-hoc test scripts exist at the repo root:

```bash
python test_graph_methods.py   # Tests OSRS price/volume graph generation
```

## Deployment

Production runs as a systemd service (`alice.service`) at `/opt/alice`. Deploy via:

```bash
sudo ./deploy.sh                     # Standard deploy
sudo ./deploy.sh --branch develop    # Deploy a specific branch
sudo ./deploy.sh --dry-run           # Preview without applying
sudo ./deploy.sh --skip-reqs         # Skip pip install
sudo ./deploy.sh --tag               # Create git tag on success
```

The script does a fast-forward merge, pip install (hash-cached), health check at `/health`, and auto-rollback on failure. Logs go to `/var/log/alice_deploy.log`.

## Architecture

### Application Entry Point

`alice_app.py` defines an `Alice` class wrapping Flask. It sets up:

- ProxyFix middleware for reverse proxy
- CSRF via flask-wtf
- Rate limiting with Memcached (falls back to in-memory)
- Session timeout: 90 minutes
- Secret key stored encrypted at `conf/cred/secret_key.pkl`

Blueprints are registered from `src/util/blueprint_init.py` — 7 total: `fort_route` (/fort), `wiki_route` (/wiki), `osrs_route` (/osrs), `showcase_route` (/showcase), `blog_route` (/blog), `discord_route`, and user routes.

### Database

Two PostgreSQL databases:

- **accounts** — `auth.users` (users), `blog.post` (blog posts with `blog_post_status` ENUM: draft/published/deleted)
- **osrs** — `items.map` (item ID → name/properties), `prices.latest` / `prices.5min` / `prices.1h` (price history with high/low/volume columns)

All DB access goes through `src/util/sql_helper.py` (50KB) — connection management and parameterized queries live there.

### Authentication

`src/user_auth.py` — `UserAuth(UserMixin)` for Flask-Login. SHA256 password hashing. Rate-limited login (10/15 min). 7-day remember-me. Strong session protection (regenerates session on login).

### OSRS Module (`src/osrs/`)

- `item_properties.py` — core item data + matplotlib graph generation (price line graphs, volume bar graphs returned as base64 for web embedding)
- `get_item_data.py` — fetches from OSRS Wiki Real-time Prices API (headers in `conf/osrs_wiki_headers.json`)
- `item_search.py` — fuzzy item search via rapidfuzz
- `calcs/` — standalone calculation modules (herblore, super combats, prayer regen, haemostatic dressing)

### Showcase System

Content-driven: `showcase_content/navigation.json` defines sidebar structure, `showcase_content/topics/*.md` are the individual pages. Client-side rendering via marked.js with hash-based URL navigation. To add a topic: add a markdown file and register it in `navigation.json`.

### Frontend

Retro Windows 98 aesthetic. Key JS modules: `drag_window.js` / `open_window.js` implement draggable windows opened via AJAX. `index_background.js` drives a WebGL lava-lamp shader (`static/glsl/indexBGShader.glsl`) adapted from [Demonin's Item Shop](https://demonin.com/).

### File Hosting

`GET /files/<path>` serves files from `hosted_files/` with directory traversal prevention. Max 64 MB.

## Environment

Public env vars are in `.env_public` (GE tax rate, Zahur fee, alchemy chances). Secrets (DB credentials, secret key) are loaded from `.env` in production (not committed). Python 3.12. Optional services: Memcached (rate limiting), Google Cloud Storage (backups), Discord.py (webhook integration).
