#!/usr/bin/env python3

import uuid
import math
import markdown
from datetime import datetime, timezone

from flask import (
    render_template,
    request,
    jsonify,
    current_app,
    Blueprint,
    abort,
)
from flask_login import login_required, current_user

from src.util.sql_helper import (
    add_update_record,
    update_existing_record,
    init_psql_connection,
)
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

blog_route = Blueprint("blog", __name__, url_prefix="/blog")

DB = "accounts"
SCHEMA = "blog"
TABLE = "post"
PER_PAGE = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_connection():
    return init_psql_connection(DB)


def _render_markdown(raw: str) -> str:
    return markdown.markdown(
        raw,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )


def _fetch_posts(
    page: int = 1,
    year: int = None,
    month: int = None,
    author_uuid: str = None,
    status: str = "published",
) -> tuple[list, int]:
    """
    Returns (posts, total_count) for given filters.
    Uses a raw parameterised query because fetch_top doesn't support WHERE clauses.
    """
    offset = (page - 1) * PER_PAGE
    conditions = ["p.status = %s"]
    params: list = [status]

    if year:
        conditions.append("EXTRACT(YEAR FROM p.post_datetime) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM p.post_datetime) = %s")
        params.append(month)
    if author_uuid:
        conditions.append("p.author_uuid = %s")
        params.append(author_uuid)

    where_clause = " AND ".join(conditions)

    count_sql = f"""
        SELECT COUNT(*) AS cnt
        FROM "{SCHEMA}"."{TABLE}" p
        WHERE {where_clause}
    """
    list_sql = f"""
        SELECT p.id, p.title, p.author_uuid, p.post_datetime, p.last_updated_datetime,
               u.username AS author_name
        FROM "{SCHEMA}"."{TABLE}" p
        LEFT JOIN "auth"."users" u ON u.id = p.author_uuid
        WHERE {where_clause}
        ORDER BY p.post_datetime DESC NULLS LAST
        LIMIT %s OFFSET %s
    """

    con = _get_connection()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(count_sql, params)
            total = cur.fetchone()["cnt"]
            cur.execute(list_sql, params + [PER_PAGE, offset])
            posts = cur.fetchall()
        return list(posts), total
    finally:
        con.close()


def _fetch_post(post_id: str, include_body: bool = True) -> dict | None:
    """Fetch a single post row by id."""
    # We need a JOIN for the author name, so use raw query
    body_col = ", p.body" if include_body else ""
    query = f"""
        SELECT p.id, p.title, p.author_uuid, p.status,
               p.post_datetime, p.last_updated_datetime, p.created_datetime
               {body_col},
               u.username AS author_name
        FROM "{SCHEMA}"."{TABLE}" p
        LEFT JOIN "auth"."users" u ON u.id = p.author_uuid
        WHERE p.id = %s
    """
    con = _get_connection()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (post_id,))
            return cur.fetchone()
    finally:
        con.close()


def _fetch_available_months() -> list[dict]:
    """Return list of {year, month} dicts that have at least one published post."""
    query = f"""
        SELECT EXTRACT(YEAR FROM post_datetime)::int  AS year,
               EXTRACT(MONTH FROM post_datetime)::int AS month
        FROM "{SCHEMA}"."{TABLE}"
        WHERE status = 'published'
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2 DESC
    """
    con = _get_connection()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
    finally:
        con.close()


def _fetch_authors() -> list[dict]:
    """Return list of {author_uuid, author_name} that have published posts."""
    query = f"""
        SELECT DISTINCT p.author_uuid, u.username AS author_name
        FROM "{SCHEMA}"."{TABLE}" p
        LEFT JOIN "auth"."users" u ON u.id = p.author_uuid
        WHERE p.status = 'published'
        ORDER BY u.username
    """
    con = _get_connection()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            return cur.fetchall()
    finally:
        con.close()


def _ensure_blog_schema():
    """Create blog schema + post table if they don't exist."""
    ddl = f"""
        CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";

        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'blog_post_status') THEN
                CREATE TYPE blog_post_status AS ENUM ('draft', 'published', 'deleted');
            END IF;
        END $$;

        CREATE TABLE IF NOT EXISTS "{SCHEMA}"."{TABLE}" (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            author_uuid          UUID NOT NULL,
            title                VARCHAR(255) NOT NULL,
            body                 TEXT NOT NULL DEFAULT '',
            status               blog_post_status NOT NULL DEFAULT 'draft',
            post_datetime        TIMESTAMPTZ,
            last_updated_datetime TIMESTAMPTZ,
            created_datetime     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    con = _get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(ddl)
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Window-mode endpoint (AJAX partial)
# ---------------------------------------------------------------------------


@blog_route.route("/window", methods=["GET"])
def blog_window():
    """Returns the blog window HTML partial for AJAX injection."""
    page = max(1, request.args.get("page", 1, type=int))
    year = request.args.get("year", None, type=int)
    month = request.args.get("month", None, type=int)
    author_uuid = request.args.get("author", None, type=str)

    try:
        posts, total = _fetch_posts(
            page=page, year=year, month=month, author_uuid=author_uuid
        )
        months = _fetch_available_months()
        authors = _fetch_authors()
    except Exception as e:
        current_app.logger.error(f"Blog window error: {e}")
        posts, total, months, authors = [], 0, [], []

    total_pages = max(1, math.ceil(total / PER_PAGE))

    html = render_template(
        "blog/index.html",
        posts=posts,
        page=page,
        total_pages=total_pages,
        year=year,
        month=month,
        author_uuid=author_uuid,
        months=months,
        authors=authors,
        window_mode=True,
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"status": "success", "html": html})


# ---------------------------------------------------------------------------
# Public read routes
# ---------------------------------------------------------------------------


@blog_route.route("/", methods=["GET"])
def index():
    page = max(1, request.args.get("page", 1, type=int))
    year = request.args.get("year", None, type=int)
    month = request.args.get("month", None, type=int)
    author_uuid = request.args.get("author", None, type=str)

    try:
        posts, total = _fetch_posts(
            page=page, year=year, month=month, author_uuid=author_uuid
        )
        months = _fetch_available_months()
        authors = _fetch_authors()
    except Exception as e:
        current_app.logger.error(f"Blog index error: {e}")
        posts, total, months, authors = [], 0, [], []

    total_pages = max(1, math.ceil(total / PER_PAGE))

    return render_template(
        "blog/index.html",
        posts=posts,
        page=page,
        total_pages=total_pages,
        year=year,
        month=month,
        author_uuid=author_uuid,
        months=months,
        authors=authors,
        window_mode=False,
    )


@blog_route.route("/<int:year>/<int:month>", methods=["GET"])
def by_month(year, month):
    page = max(1, request.args.get("page", 1, type=int))
    author_uuid = request.args.get("author", None, type=str)

    try:
        posts, total = _fetch_posts(
            page=page, year=year, month=month, author_uuid=author_uuid
        )
        months = _fetch_available_months()
        authors = _fetch_authors()
    except Exception as e:
        current_app.logger.error(f"Blog by_month error: {e}")
        posts, total, months, authors = [], 0, [], []

    total_pages = max(1, math.ceil(total / PER_PAGE))

    return render_template(
        "blog/index.html",
        posts=posts,
        page=page,
        total_pages=total_pages,
        year=year,
        month=month,
        author_uuid=author_uuid,
        months=months,
        authors=authors,
        window_mode=False,
    )


@blog_route.route("/post/<post_id>", methods=["GET"])
def view_post(post_id):
    post = _fetch_post(post_id)
    if not post or post["status"] != "published":
        abort(404)
    rendered_body = _render_markdown(post["body"])
    return render_template(
        "blog/post.html", post=post, rendered_body=rendered_body, window_mode=False
    )


@blog_route.route("/window/post/<post_id>", methods=["GET"])
def view_post_window(post_id):
    """Window-mode single post partial."""
    post = _fetch_post(post_id)
    if not post or post["status"] != "published":
        return "<p>Post not found.</p>", 404
    rendered_body = _render_markdown(post["body"])
    html = render_template(
        "blog/post.html", post=post, rendered_body=rendered_body, window_mode=True
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"status": "success", "html": html})


# ---------------------------------------------------------------------------
# Authenticated write / edit routes
# ---------------------------------------------------------------------------


@blog_route.route("/write", methods=["GET"])
@login_required
def write():
    html = render_template("blog/editor.html", post=None, window_mode=True)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"status": "success", "html": html})


@blog_route.route("/write", methods=["POST"])
@login_required
def write_post():
    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    action = data.get("action", "publish")  # "publish" or "draft"

    if not title:
        return jsonify({"status": "error", "message": "Title is required."}), 400

    post_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    status = "published" if action == "publish" else "draft"
    post_datetime = now if status == "published" else None

    try:
        add_update_record(
            database=DB,
            schema=SCHEMA,
            table=TABLE,
            columns=[
                "id",
                "author_uuid",
                "title",
                "body",
                "status",
                "post_datetime",
                "last_updated_datetime",
                "created_datetime",
            ],
            values=[
                post_id,
                str(current_user.id),
                title,
                body,
                status,
                post_datetime,
                now,
                now,
            ],
            conflict_target=["id"],
            on_conflict=None,
        )
    except Exception as e:
        current_app.logger.error(f"Blog write error: {e}")
        return jsonify({"status": "error", "message": "Failed to save post."}), 500

    return jsonify({"status": "success", "post_id": post_id, "post_status": status})


@blog_route.route("/edit/<post_id>", methods=["GET"])
@login_required
def edit(post_id):
    post = _fetch_post(post_id)
    if not post:
        abort(404)
    if str(post["author_uuid"]) != str(current_user.id):
        abort(403)
    html = render_template("blog/editor.html", post=post, window_mode=True)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"status": "success", "html": html})


@blog_route.route("/edit/<post_id>", methods=["POST"])
@login_required
def edit_post(post_id):
    post = _fetch_post(post_id, include_body=False)
    if not post:
        return jsonify({"status": "error", "message": "Post not found."}), 404
    if str(post["author_uuid"]) != str(current_user.id):
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    action = data.get("action", "publish")

    if not title:
        return jsonify({"status": "error", "message": "Title is required."}), 400

    now = datetime.now(timezone.utc)
    status = "published" if action == "publish" else "draft"

    update_cols = ["title", "body", "status", "last_updated_datetime"]
    update_vals = [title, body, status, now]

    # Stamp post_datetime on first publish
    if status == "published" and not post["post_datetime"]:
        update_cols.append("post_datetime")
        update_vals.append(now)

    try:
        update_existing_record(
            database=DB,
            schema=SCHEMA,
            table=TABLE,
            update_columns=update_cols,
            update_values=update_vals,
            where_column="id",
            where_value=post_id,
        )
    except Exception as e:
        current_app.logger.error(f"Blog edit error: {e}")
        return jsonify({"status": "error", "message": "Failed to update post."}), 500

    return jsonify({"status": "success", "post_id": post_id, "post_status": status})


@blog_route.route("/delete/<post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = _fetch_post(post_id, include_body=False)
    if not post:
        return jsonify({"status": "error", "message": "Post not found."}), 404
    if str(post["author_uuid"]) != str(current_user.id):
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    try:
        update_existing_record(
            database=DB,
            schema=SCHEMA,
            table=TABLE,
            update_columns=["status"],
            update_values=["deleted"],
            where_column="id",
            where_value=post_id,
        )
    except Exception as e:
        current_app.logger.error(f"Blog delete error: {e}")
        return jsonify({"status": "error", "message": "Failed to delete post."}), 500

    return jsonify({"status": "success"})


# ---------------------------------------------------------------------------
# Draft auto-save
# ---------------------------------------------------------------------------


@blog_route.route("/draft/<post_id>", methods=["POST"])
@login_required
def save_draft(post_id):
    post = _fetch_post(post_id, include_body=False)
    if not post:
        return jsonify({"status": "error", "message": "Post not found."}), 404
    if str(post["author_uuid"]) != str(current_user.id):
        return jsonify({"status": "error", "message": "Forbidden."}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body = data.get("body", "")
    now = datetime.now(timezone.utc)

    try:
        update_existing_record(
            database=DB,
            schema=SCHEMA,
            table=TABLE,
            update_columns=["title", "body", "last_updated_datetime"],
            update_values=[title or post["title"], body, now],
            where_column="id",
            where_value=post_id,
        )
    except Exception as e:
        current_app.logger.error(f"Blog draft save error: {e}")
        return jsonify({"status": "error", "message": "Draft save failed."}), 500

    return jsonify({"status": "success"})


# ---------------------------------------------------------------------------
# JSON data endpoints
# ---------------------------------------------------------------------------


@blog_route.route("/months", methods=["GET"])
def available_months():
    try:
        months = _fetch_available_months()
        return jsonify({"status": "success", "months": [dict(m) for m in months]})
    except Exception as e:
        current_app.logger.error(f"Blog months error: {e}")
        return jsonify({"status": "error"}), 500


@blog_route.route("/preview", methods=["POST"])
@login_required
def preview_markdown():
    """Render a markdown string to HTML for the editor preview pane."""
    data = request.get_json(silent=True) or {}
    raw = data.get("body", "")
    return jsonify({"status": "success", "html": _render_markdown(raw)})
