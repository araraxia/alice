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

Production runs as a systemd service (`alice.service`, waitress on `127.0.0.1:6969`, behind an Apache reverse proxy) from `/mnt/ssd/opt/alice` as user `alice`. The `alice` user's home is `/var/lib/alice`, which holds the GitHub deploy key (`~/.ssh/id_ed25519`) used for pulls. The tree is group `alice` and group-writable (setgid dirs); `aria` is in the `alice` group. Do not make anything world-writable. Deploy via:

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
- Secret key stored as a pickled random hex string at `conf/cred/secret_key.pkl` (generated if missing; rotating it logs everyone out)

Blueprints are registered from `src/util/blueprint_init.py` — 7 total: `fort_route` (/fort), `wiki_route` (/wiki), `osrs_route` (/osrs), `showcase_route` (/showcase), `blog_route` (/blog), `discord_route`, and user routes.

### Database

PostgreSQL 15 on port 5454. The app connects as the non-superuser role `alice`, which owns these three databases and everything in them:

- **accounts** — `auth.users` (users), `auth.user_themes` / `auth.theme_ratings`, `settings`; `blog.post` (blog posts with `blog_post_status` ENUM: draft/published/deleted) is created on first use
- **osrs** — `items.map` (item ID → name/properties), `herblore.*`, and one table per item per timeframe in schema `prices`: `prices."<item_id>_latest"`, `"<item_id>_5min"`, `"<item_id>_1h"` (~13.6k tables, created on demand by `sql_helper.ensure_table_exists`; numeric columns are `BIGINT` because some prices exceed int4 — `guess_column_type` maps Python `int` → `BIGINT`)
- **server** — `notification.*`

The `postgres` superuser has no password (local `sudo -u postgres psql` only). `pg_hba.conf` allows password logins from localhost and the LAN (`192.168.1.0/24`) only.

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

Public env vars are in `.env_public` (GE tax rate, Zahur fee, alchemy chances). Secrets live in `conf/cred/` (git-ignored, dir 700 / files 600, owner `alice`): `psql.json` (DB host/port/user/password), `secret_key.pkl`, `minecraft_rcon.json` (RCON to the Minecraft server at 192.168.1.50 — Minecraft is not hosted on this machine), `gcloud_service.json`. Python 3.13 (venv at `.venv`, interpreter from `/opt/python3.13`). Optional services: Memcached (rate limiting), Google Cloud Storage (backups), Discord.py (webhook integration).
