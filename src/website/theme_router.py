import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, current_app
from flask_login import login_required, current_user
from psycopg2.extras import RealDictCursor

from src.util.sql_helper import (
    init_psql_connection,
    search_records,
    add_update_record,
    delete_record,
    get_record,
)

theme_route = Blueprint("theme", __name__, url_prefix="/theme")

MAX_FILES = 10
MAX_BYTES = 51_200  # 50 KB
FILENAME_RE = re.compile(r"^[\w\- .]{1,77}\.css$")

# ── DB setup ──────────────────────────────────────────────────────────────────

_db_ready = False


def _init_db():
    global _db_ready
    if _db_ready:
        return
    con = init_psql_connection("accounts")
    cur = con.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth.user_themes (
                id         SERIAL PRIMARY KEY,
                user_id    VARCHAR(36)  NOT NULL,
                filename   VARCHAR(80)  NOT NULL,
                content    TEXT         NOT NULL,
                file_size  INTEGER      NOT NULL,
                created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, filename)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth.theme_ratings (
                id         SERIAL PRIMARY KEY,
                user_id    VARCHAR(36) NOT NULL,
                theme_id   INTEGER     NOT NULL,
                value      SMALLINT    NOT NULL CHECK (value IN (-1, 1)),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, theme_id)
            )
        """)
        # Migrate: if tables were created with INTEGER user_id, convert to VARCHAR(36)
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'auth' AND table_name = 'user_themes' AND column_name = 'user_id'
        """)
        row = cur.fetchone()
        if row and row[0].lower() == "integer":
            cur.execute("ALTER TABLE auth.user_themes ALTER COLUMN user_id TYPE VARCHAR(36) USING user_id::text")
            cur.execute("ALTER TABLE auth.theme_ratings ALTER COLUMN user_id TYPE VARCHAR(36) USING user_id::text")
        con.commit()
        _db_ready = True
    except Exception as e:
        con.rollback()
        raise RuntimeError(f"Failed to init theme tables: {e}") from e
    finally:
        cur.close()
        con.close()


@theme_route.before_request
def ensure_db():
    if not _db_ready:
        try:
            _init_db()
        except Exception as e:
            current_app.logger.error(f"theme DB init failed: {e}")


# ── Partials ──────────────────────────────────────────────────────────────────


@theme_route.route("/preview", methods=["GET"])
def preview():
    html = render_template("theme/preview.html")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"html": html})


@theme_route.route("/manager", methods=["GET"])
def manager():
    html = render_template(
        "theme/manager.html",
        is_authenticated=current_user.is_authenticated,
        max_files=MAX_FILES,
        max_kb=MAX_BYTES // 1024,
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"html": html})


@theme_route.route("/gallery", methods=["GET"])
def gallery():
    html = render_template(
        "theme/gallery.html",
        is_authenticated=current_user.is_authenticated,
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return html
    return jsonify({"html": html})


# ── Private file API ──────────────────────────────────────────────────────────


@theme_route.route("/files", methods=["GET"])
@login_required
def list_files():
    rows = search_records(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="user_id",
        value=current_user.user_id,
    )
    rows = sorted(rows, key=lambda r: r["updated_at"], reverse=True)
    return jsonify([
        {
            "id": r["id"],
            "filename": r["filename"],
            "file_size": r["file_size"],
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ])


@theme_route.route("/files", methods=["POST"])
@login_required
def save_file():
    data = request.get_json(silent=True) or {}
    filename = (data.get("filename") or "").strip()
    content = data.get("content") or ""

    if not FILENAME_RE.match(filename):
        return jsonify({"error": "Invalid filename (alphanumeric, hyphens, spaces, must end in .css, max 80 chars)"}), 400
    if not content:
        return jsonify({"error": "CSS content is required"}), 400

    size = len(content.encode())
    if size > MAX_BYTES:
        return jsonify({"error": f"File too large (max {MAX_BYTES // 1024} KB)"}), 400

    existing = search_records(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="user_id",
        value=current_user.user_id,
    )
    existing_names = {r["filename"] for r in existing}
    if filename not in existing_names and len(existing) >= MAX_FILES:
        return jsonify({"error": f"Theme file limit reached (max {MAX_FILES})"}), 400

    add_update_record(
        database="accounts",
        schema="auth",
        table="user_themes",
        columns=["user_id", "filename", "content", "file_size", "updated_at"],
        values=[current_user.user_id, filename, content, size, datetime.now(timezone.utc)],
        conflict_target=["user_id", "filename"],
    )
    return jsonify({"status": "ok", "filename": filename})


@theme_route.route("/files/<int:file_id>", methods=["GET"])
@login_required
def get_file(file_id):
    record = get_record(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="id",
        value=file_id,
    )
    if not record or record["user_id"] != current_user.user_id:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": record["id"],
        "filename": record["filename"],
        "content": record["content"],
        "file_size": record["file_size"],
    })


@theme_route.route("/files/<int:file_id>", methods=["DELETE"])
@login_required
def delete_file(file_id):
    record = get_record(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="id",
        value=file_id,
    )
    if not record or record["user_id"] != current_user.user_id:
        return jsonify({"error": "Not found"}), 404
    delete_record(
        database="accounts",
        log=current_app.logger,
        schema_name="auth",
        table_name="user_themes",
        columns=["id", "user_id"],
        values=[file_id, current_user.user_id],
    )
    return jsonify({"status": "ok"})


# ── Public gallery API ────────────────────────────────────────────────────────

_GALLERY_SORT = {"rating": "rating", "date": "t.updated_at"}
_GALLERY_ORDER = {"desc": "DESC", "asc": "ASC"}


def _gallery_query(sort_by="rating", order="desc", uid=None):
    sort_col = _GALLERY_SORT.get(sort_by, "rating")
    sort_dir = _GALLERY_ORDER.get(order, "DESC")

    # Correlated subquery for the requesting user's own vote — NULL if logged out
    if uid is not None:
        my_vote_expr = "(SELECT value FROM auth.theme_ratings WHERE user_id = %s AND theme_id = t.id)"
        params = [uid]
    else:
        my_vote_expr = "NULL"
        params = []

    query = f"""
        SELECT
            t.id,
            t.filename,
            t.file_size,
            t.updated_at,
            u.username                                        AS author,
            COALESCE(SUM(r.value), 0)                        AS rating,
            COUNT(CASE WHEN r.value =  1 THEN 1 END)         AS upvotes,
            COUNT(CASE WHEN r.value = -1 THEN 1 END)         AS downvotes,
            {my_vote_expr}                                    AS my_vote
        FROM auth.user_themes t
        JOIN auth.users u ON u.user_id = t.user_id
        LEFT JOIN auth.theme_ratings r ON r.theme_id = t.id
        GROUP BY t.id, t.filename, t.file_size, t.updated_at, u.username
        ORDER BY {sort_col} {sort_dir}, t.updated_at DESC
    """

    con = init_psql_connection("accounts")
    cur = con.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()
        con.close()


@theme_route.route("/gallery/files", methods=["GET"])
def gallery_files():
    sort_by = request.args.get("sort", "rating")
    order   = request.args.get("order", "desc")
    uid     = current_user.user_id if current_user.is_authenticated else None

    rows = _gallery_query(sort_by=sort_by, order=order, uid=uid)
    return jsonify([
        {
            "id":         r["id"],
            "filename":   r["filename"],
            "file_size":  r["file_size"],
            "updated_at": r["updated_at"].isoformat(),
            "author":     r["author"],
            "rating":     int(r["rating"]),
            "upvotes":    int(r["upvotes"]),
            "downvotes":  int(r["downvotes"]),
            "my_vote":    r["my_vote"],  # 1, -1, or None
        }
        for r in rows
    ])


@theme_route.route("/gallery/<int:file_id>/content", methods=["GET"])
def gallery_content(file_id):
    """Public endpoint — returns CSS content for any theme in the gallery."""
    record = get_record(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="id",
        value=file_id,
    )
    if not record:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id":       record["id"],
        "filename": record["filename"],
        "content":  record["content"],
    })


@theme_route.route("/gallery/<int:file_id>/rate", methods=["POST"])
@login_required
def rate_theme(file_id):
    data  = request.get_json(silent=True) or {}
    value = data.get("value")
    if value not in (1, -1):
        return jsonify({"error": "value must be 1 or -1"}), 400

    # Verify theme exists
    theme = get_record(
        database="accounts",
        schema="auth",
        table="user_themes",
        column="id",
        value=file_id,
    )
    if not theme:
        return jsonify({"error": "Not found"}), 404

    con = init_psql_connection("accounts")
    cur = con.cursor(cursor_factory=RealDictCursor)
    try:
        # Check existing vote
        cur.execute(
            "SELECT value FROM auth.theme_ratings WHERE user_id = %s AND theme_id = %s",
            (current_user.user_id, file_id),
        )
        existing = cur.fetchone()

        if existing and existing["value"] == value:
            # Same vote → toggle off (remove)
            cur.execute(
                "DELETE FROM auth.theme_ratings WHERE user_id = %s AND theme_id = %s",
                (current_user.user_id, file_id),
            )
            my_vote = None
        else:
            # New vote or changed vote → upsert
            cur.execute(
                """
                INSERT INTO auth.theme_ratings (user_id, theme_id, value)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, theme_id) DO UPDATE SET value = EXCLUDED.value
                """,
                (current_user.user_id, file_id, value),
            )
            my_vote = value

        # Return updated totals
        cur.execute(
            """
            SELECT
                COALESCE(SUM(value), 0)                  AS rating,
                COUNT(CASE WHEN value =  1 THEN 1 END)   AS upvotes,
                COUNT(CASE WHEN value = -1 THEN 1 END)   AS downvotes
            FROM auth.theme_ratings
            WHERE theme_id = %s
            """,
            (file_id,),
        )
        totals = cur.fetchone()
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        cur.close()
        con.close()

    return jsonify({
        "status":    "ok",
        "my_vote":   my_vote,
        "rating":    int(totals["rating"]),
        "upvotes":   int(totals["upvotes"]),
        "downvotes": int(totals["downvotes"]),
    })
