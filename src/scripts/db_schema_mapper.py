#!/usr/bin/env python3
"""
Database Schema Mapper
======================
Generates (or updates) a Markdown file that maps every schema, table, and
column in a PostgreSQL database.  The output file is designed to be edited
by hand so that engineers can annotate tables with roles and legacy status.

Usage
-----
# Full map of a database
    python db_schema_mapper.py example_db

# Scope to a single schema
    python db_schema_mapper.py example_db --schema <schema>

# Scope to a single table within a schema
    python db_schema_mapper.py example_db --schema <schema> --table orders

# Update an existing map (only appends NEW schemas/tables, preserves notes)
    python db_schema_mapper.py example_db --update

# Skip row-count queries (faster for large databases)
    python db_schema_mapper.py example_db --no-counts

Importable Modules
------------------
Each section is independently importable for mid-task exploration:

    from db_schema_mapper import (
        get_connection, release_connection,
        fetch_schemas, fetch_tables, fetch_columns,
        fetch_primary_keys, fetch_foreign_keys,
        render_table_block, render_schema_block, render_full_doc,
        get_output_path, load_existing_map, extract_mapped_tables,
        write_map, update_map,
    )
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Path setup (mirrors sql_helper.py convention)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
CRED_PATH = ROOT_DIR / "conf" / "cred" / "psql.json"
OUTPUT_DIR = ROOT_DIR / "docs" / "sql"

# Schemas that belong to PostgreSQL itself – skip unless explicitly requested
_SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
    "pg_temp_1",
    "pg_toast_temp_1",
}


# ===========================================================================
# ── Module 1: Connection ────────────────────────────────────────────────────
# ===========================================================================


def _load_creds() -> dict:
    """Load PostgreSQL credentials from cred/psql.json."""
    if not CRED_PATH.exists():
        raise FileNotFoundError(f"Credentials file not found: {CRED_PATH}")
    with open(CRED_PATH, "r") as f:
        return json.load(f)


def get_connection(database: str) -> psycopg2.extensions.connection:
    """
    Open a psycopg2 connection to *database*.

    Credentials are read from ``cred/psql.json`` (same source as sql_helper).

    Args:
        database: PostgreSQL database name.

    Returns:
        An open psycopg2 connection.
    """
    creds = _load_creds()
    try:
        con = psycopg2.connect(
            dbname=database,
            user=creds.get("user", ""),
            password=creds.get("password", ""),
            host=creds.get("ip", "localhost"),
            port=int(creds.get("port", 5432)),
        )
        return con
    except psycopg2.Error as e:
        print(f"[ERROR] Could not connect to '{database}': {e}", file=sys.stderr)
        raise


def release_connection(con: psycopg2.extensions.connection) -> None:
    """Close a psycopg2 connection safely."""
    try:
        con.close()
    except Exception:
        pass


# ===========================================================================
# ── Module 2: Discovery ─────────────────────────────────────────────────────
# ===========================================================================


def fetch_schemas(con: psycopg2.extensions.connection) -> list:
    """
    Return all non-system schema names in the connected database.

    Args:
        con: Open psycopg2 connection.

    Returns:
        Sorted list of schema name strings.
    """
    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT LIKE 'pg_%'
              AND schema_name != 'information_schema'
            ORDER BY schema_name
            """
        )
        return [row["schema_name"] for row in cur.fetchall()]


def fetch_tables(con: psycopg2.extensions.connection, schema: str) -> list:
    """
    Return all table names in *schema*.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.

    Returns:
        Sorted list of table name strings.
    """
    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema,),
        )
        return [row["table_name"] for row in cur.fetchall()]


def fetch_columns(con: psycopg2.extensions.connection, schema: str, table: str) -> list:
    """
    Return column metadata for *schema.table*.

    Each item is a dict with keys:
        column_name, data_type, character_maximum_length,
        is_nullable, column_default, is_primary_key (bool), ordinal_position.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.
        table:  Table name.

    Returns:
        List of column dicts ordered by ordinal_position.
    """
    pks = fetch_primary_keys(con, schema, table)

    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        rows = cur.fetchall()

    columns = []
    for row in rows:
        col = dict(row)
        col["is_primary_key"] = col["column_name"] in pks
        # Build a concise type string  e.g.  "character varying(255)"
        dtype = col["data_type"]
        if col.get("character_maximum_length"):
            dtype = f"{dtype}({col['character_maximum_length']})"
        col["type_display"] = dtype
        columns.append(col)

    return columns


def fetch_primary_keys(
    con: psycopg2.extensions.connection, schema: str, table: str
) -> set:
    """
    Return the set of column names that form the primary key of *schema.table*.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.
        table:  Table name.

    Returns:
        Set of PK column name strings (may be empty).
    """
    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
             AND tc.table_name      = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema    = %s
              AND tc.table_name      = %s
            """,
            (schema, table),
        )
        return {row["column_name"] for row in cur.fetchall()}


def fetch_foreign_keys(
    con: psycopg2.extensions.connection, schema: str, table: str
) -> list:
    """
    Return foreign-key relationships defined on *schema.table*.

    Each item is a dict:
        column_name, foreign_schema, foreign_table, foreign_column,
        constraint_name.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.
        table:  Table name.

    Returns:
        List of FK dicts.
    """
    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                kcu.column_name,
                ccu.table_schema  AS foreign_schema,
                ccu.table_name    AS foreign_table,
                ccu.column_name   AS foreign_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
             AND tc.table_name      = kcu.table_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema    = %s
              AND tc.table_name      = %s
            ORDER BY kcu.column_name
            """,
            (schema, table),
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_row_count(
    con: psycopg2.extensions.connection, schema: str, table: str
) -> int:
    """
    Return an estimated row count for *schema.table* via pg_class statistics.

    This is fast (no full scan) but may be slightly stale between ANALYZE runs.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.
        table:  Table name.

    Returns:
        Estimated row count integer.
    """
    with con.cursor() as cur:
        cur.execute(
            """
            SELECT reltuples::bigint AS estimate
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname  = %s
            """,
            (schema, table),
        )
        result = cur.fetchone()
        return result[0] if result else 0


# ===========================================================================
# ── Module 3: Rendering ─────────────────────────────────────────────────────
# ===========================================================================


def render_table_block(
    schema: str,
    table: str,
    columns: list,
    foreign_keys: list,
    row_count: int | None = None,
) -> str:
    """
    Build a Markdown block for a single table.

    The output includes an annotation section (pre-filled with placeholders)
    that the engineer can edit, a column table, and an FK section.

    Args:
        schema:       Schema name.
        table:        Table name.
        columns:      Column dicts from fetch_columns().
        foreign_keys: FK dicts from fetch_foreign_keys().
        row_count:    Optional estimated row count.

    Returns:
        Markdown string for the table block.
    """
    lines = []

    # ── heading ──
    lines.append(f"### Table: `{table}`")
    lines.append("")

    # ── annotation block (engineer-editable) ──
    count_str = f"~{row_count:,}" if row_count is not None else "unknown"
    lines.append(f"> **Status:** <!-- active | legacy | deprecated -->  ")
    lines.append(f"> **Role:** <!-- Describe what this table is used for -->  ")
    lines.append(f"> **Rows (est.):** {count_str}  ")
    lines.append(f"> **Notes:** <!-- Any additional notes -->  ")
    lines.append("")

    # ── column table ──
    lines.append("| Column | Type | Nullable | Default | Flags | Notes |")
    lines.append("|--------|------|----------|---------|-------|-------|")

    for col in columns:
        flags = []
        if col.get("is_primary_key"):
            flags.append("PK")
        # Mark if any FK references this column
        if any(fk["column_name"] == col["column_name"] for fk in foreign_keys):
            flags.append("FK")

        nullable = "YES" if col.get("is_nullable") == "YES" else "NO"
        default = col.get("column_default") or ""
        # Truncate long defaults (e.g. nextval sequences)
        if len(default) > 40:
            default = default[:37] + "..."

        lines.append(
            f"| `{col['column_name']}` "
            f"| {col['type_display']} "
            f"| {nullable} "
            f"| {default} "
            f"| {', '.join(flags) if flags else ''} "
            f"| <!-- notes --> |"
        )

    lines.append("")

    # ── foreign keys ──
    if foreign_keys:
        lines.append("**Foreign Keys:**")
        lines.append("")
        for fk in foreign_keys:
            lines.append(
                f"- `{fk['column_name']}` → "
                f"`{fk['foreign_schema']}.{fk['foreign_table']}.{fk['foreign_column']}`"
            )
        lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def render_schema_block(
    schema: str,
    tables_data: list,
) -> str:
    """
    Build the Markdown section for a whole schema.

    Args:
        schema:      Schema name.
        tables_data: List of dicts, each with keys:
                     table, columns, foreign_keys, row_count.

    Returns:
        Markdown string for the schema section.
    """
    lines = []
    lines.append(f"## Schema: `{schema}`")
    lines.append("")
    lines.append(f"> **Notes:** <!-- Schema-level notes, purpose, team ownership -->")
    lines.append("")

    if not tables_data:
        lines.append("*No tables found in this schema.*")
        lines.append("")
    else:
        for td in tables_data:
            lines.append(
                render_table_block(
                    schema=schema,
                    table=td["table"],
                    columns=td["columns"],
                    foreign_keys=td["foreign_keys"],
                    row_count=td.get("row_count"),
                )
            )

    return "\n".join(lines)


def render_full_doc(
    database: str,
    schemas_data: list,
    scoped_schema: str | None = None,
    scoped_table: str | None = None,
) -> str:
    """
    Build the complete Markdown document for one or more schemas.

    Args:
        database:      Database name (used in title).
        schemas_data:  List of dicts with keys: schema, tables (list of table dicts).
        scoped_schema: If set, note in the header that this is a partial map.
        scoped_table:  If set, note in the header that this is a partial map.

    Returns:
        Full Markdown document string.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    scope_note = ""
    if scoped_table:
        scope_note = f" *(scoped to `{scoped_schema}.{scoped_table}`)*"
    elif scoped_schema:
        scope_note = f" *(scoped to schema `{scoped_schema}`)*"

    lines = [
        f"# Database Map: `{database}`{scope_note}",
        "",
        f"*Generated: {now}*  ",
        "*This file is auto-generated. Annotation fields marked `<!-- -->` are for manual edits and will be preserved during `--update` runs.*",
        "",
        "---",
        "",
    ]

    for sd in schemas_data:
        lines.append(render_schema_block(sd["schema"], sd["tables"]))

    return "\n".join(lines)


# ===========================================================================
# ── Module 4: File Management ───────────────────────────────────────────────
# ===========================================================================


def get_output_path(database: str) -> Path:
    """
    Return the canonical output path for a database map.

    Files are written to ``docs/sql/{database}_schema.md``.

    Args:
        database: Database name.

    Returns:
        pathlib.Path object.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / f"{database}_schema.md"


def load_existing_map(path: Path) -> str:
    """
    Load the content of an existing schema map file.

    Args:
        path: Path to the existing .md file.

    Returns:
        File content string, or empty string if the file doesn't exist.
    """
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def extract_mapped_tables(content: str) -> set:
    """
    Parse an existing schema map and return the set of (schema, table) pairs
    that are already documented.

    Uses the heading pattern ``## Schema: `X``` ... ``### Table: `Y```.

    Args:
        content: Markdown file content string.

    Returns:
        Set of (schema_name, table_name) tuples.
    """
    mapped = set()
    current_schema = None

    for line in content.splitlines():
        schema_match = re.match(r"^## Schema: `(.+?)`", line)
        table_match = re.match(r"^### Table: `(.+?)`", line)

        if schema_match:
            current_schema = schema_match.group(1)
        elif table_match and current_schema:
            mapped.add((current_schema, table_match.group(1)))

    return mapped


def write_map(path: Path, content: str) -> None:
    """
    Write (overwrite) a schema map file.

    Args:
        path:    Destination path.
        content: Markdown content to write.
    """
    path.write_text(content, encoding="utf-8")
    print(f"[OK] Written → {path}")


# ===========================================================================
# ── Module 5: Update / Diff ─────────────────────────────────────────────────
# ===========================================================================


def update_map(
    database: str,
    con: psycopg2.extensions.connection,
    include_counts: bool = True,
    scoped_schema: str | None = None,
) -> None:
    """
    Update an existing schema map, appending only new schemas and tables.

    Existing annotations and notes are fully preserved.  New items are appended
    at the end of the file (or at the end of the relevant schema section if the
    schema already exists).

    Args:
        database:       Database name.
        con:            Open psycopg2 connection.
        include_counts: Whether to include row count estimates.
        scoped_schema:  If set, only check for new tables in this schema.
    """
    path = get_output_path(database)
    existing_content = load_existing_map(path)

    if not existing_content:
        print("[INFO] No existing map found — running full generation instead.")
        run_full_map(
            database, con, include_counts=include_counts, scoped_schema=scoped_schema
        )
        return

    already_mapped = extract_mapped_tables(existing_content)

    schemas = [scoped_schema] if scoped_schema else fetch_schemas(con)
    schemas = [s for s in schemas if s not in _SYSTEM_SCHEMAS]

    new_blocks = []

    for schema in schemas:
        tables = fetch_tables(con, schema)
        new_tables = [t for t in tables if (schema, t) not in already_mapped]

        if not new_tables:
            continue

        print(f"[INFO] {len(new_tables)} new table(s) found in schema '{schema}'")

        # Check if the schema itself is already in the map
        schema_in_map = any(s == schema for (s, _) in already_mapped)

        tables_data = _collect_tables_data(con, schema, new_tables, include_counts)

        if not schema_in_map:
            # Whole new schema — render header + tables
            new_blocks.append(render_schema_block(schema, tables_data))
        else:
            # Schema exists, just append the table blocks
            header = f"\n<!-- New tables added {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n\n"
            table_md = header + "".join(
                render_table_block(
                    schema,
                    td["table"],
                    td["columns"],
                    td["foreign_keys"],
                    td.get("row_count"),
                )
                for td in tables_data
            )
            # Insert before the NEXT schema heading or at end of file
            next_schema_pattern = re.compile(
                r"^## Schema: `(?!" + re.escape(schema) + r")`", re.MULTILINE
            )
            match = next_schema_pattern.search(existing_content)
            if match:
                insert_pos = match.start()
                existing_content = (
                    existing_content[:insert_pos]
                    + table_md
                    + "\n"
                    + existing_content[insert_pos:]
                )
            else:
                existing_content = existing_content.rstrip() + "\n\n" + table_md

    if new_blocks:
        full_new = "\n".join(new_blocks)
        existing_content = existing_content.rstrip() + "\n\n" + full_new

    if not new_blocks and not any(
        (schema, t) not in already_mapped
        for schema in (schemas)
        for t in fetch_tables(con, schema)
    ):
        print("[INFO] Map is already up to date — no new tables found.")
        return

    # Update the "Generated" timestamp note
    existing_content = re.sub(
        r"\*Generated: .+?\*",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        existing_content,
        count=1,
    )

    write_map(path, existing_content)


# ===========================================================================
# ── Module 6: Orchestration ─────────────────────────────────────────────────
# ===========================================================================


def _collect_tables_data(
    con: psycopg2.extensions.connection,
    schema: str,
    tables: list,
    include_counts: bool,
) -> list:
    """
    Fetch column, FK, and (optionally) row-count data for a list of tables.

    Returns a list of dicts suitable for the rendering functions.
    """
    tables_data = []
    for table in tables:
        print(f"  ↳ {schema}.{table}")
        columns = fetch_columns(con, schema, table)
        foreign_keys = fetch_foreign_keys(con, schema, table)
        row_count = fetch_row_count(con, schema, table) if include_counts else None
        tables_data.append(
            {
                "table": table,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "row_count": row_count,
            }
        )
    return tables_data


def run_full_map(
    database: str,
    con: psycopg2.extensions.connection,
    include_counts: bool = True,
    scoped_schema: str | None = None,
    scoped_table: str | None = None,
) -> None:
    """
    Generate (or overwrite) a complete schema map for *database*.

    Args:
        database:       Database name.
        con:            Open psycopg2 connection.
        include_counts: Include estimated row counts (default True).
        scoped_schema:  Limit output to this schema only.
        scoped_table:   Limit output to this table only (requires scoped_schema).
    """
    schemas = [scoped_schema] if scoped_schema else fetch_schemas(con)
    schemas = [s for s in schemas if s not in _SYSTEM_SCHEMAS]

    schemas_data = []

    for schema in schemas:
        print(f"[INFO] Processing schema: {schema}")
        if scoped_table:
            tables = [scoped_table]
        else:
            tables = fetch_tables(con, schema)

        tables_data = _collect_tables_data(con, schema, tables, include_counts)
        schemas_data.append({"schema": schema, "tables": tables_data})

    content = render_full_doc(
        database=database,
        schemas_data=schemas_data,
        scoped_schema=scoped_schema,
        scoped_table=scoped_table,
    )

    path = get_output_path(database)
    write_map(path, content)


# ===========================================================================
# ── CLI ─────────────────────────────────────────────────────────────────────
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db_schema_mapper",
        description="Generate a Markdown schema map for a PostgreSQL database.",
    )
    parser.add_argument("database", help="PostgreSQL database name (e.g. example_db)")
    parser.add_argument(
        "--schema",
        "-s",
        metavar="SCHEMA",
        help="Limit output to this schema only.",
    )
    parser.add_argument(
        "--table",
        "-t",
        metavar="TABLE",
        help="Limit output to this table (requires --schema).",
    )
    parser.add_argument(
        "--update",
        "-u",
        action="store_true",
        help="Append only new schemas/tables to an existing map (preserves annotations).",
    )
    parser.add_argument(
        "--no-counts",
        action="store_true",
        help="Skip row-count estimation (faster for very large databases).",
    )
    return parser


def main(argv: list | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.table and not args.schema:
        parser.error("--table requires --schema to be specified.")

    print(f"[INFO] Connecting to database '{args.database}'...")
    con = get_connection(args.database)

    try:
        if args.update:
            update_map(
                database=args.database,
                con=con,
                include_counts=not args.no_counts,
                scoped_schema=args.schema,
            )
        else:
            run_full_map(
                database=args.database,
                con=con,
                include_counts=not args.no_counts,
                scoped_schema=args.schema,
                scoped_table=args.table,
            )
    finally:
        release_connection(con)


if __name__ == "__main__":
    main()