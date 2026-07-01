#!/usr/bin/env python3
"""
Database Object Generator
=========================
Generates Python class files for each table in a PostgreSQL database.
Each class has load(), save(), delete() (with automatic join-table cleanup),
and relation helpers for every join table that references it.

Usage
-----
# Generate all classes for a database
    python db_object_generator.py example_db

# Scope to a single schema
    python db_object_generator.py example_db --schema organization

# Scope to a single table
    python db_object_generator.py example_db --schema organization --table customer

# Only generate files for new tables (preserve existing)
    python db_object_generator.py example_db --update

# Regenerate all, replacing existing files
    python db_object_generator.py example_db --overwrite

Importable Modules
------------------
    from db_object_generator import (
        fetch_reverse_foreign_keys,
        is_join_table,
        collect_table_data,
        render_class,
        get_output_path,
        write_object_file,
        run_full_generate,
        update_generate,
    )
"""

import argparse
import re
import sys
from pathlib import Path

from psycopg2.extras import RealDictCursor

from db_schema_mapper import (
    get_connection,
    release_connection,
    fetch_schemas,
    fetch_tables,
    fetch_columns,
    fetch_primary_keys,
    fetch_foreign_keys,
)

_SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
    "pg_temp_1",
    "pg_toast_temp_1",
}

# Output root: src/sql/generated/{database}/{schema}/{table}.py
# parents[5] from any generated file reaches the project root.
OUTPUT_BASE = Path(__file__).resolve().parent / "src" / "sql" / "generated"

# Sentinel lines that delimit the preserved custom-extension block.
# These exact strings must not be modified inside generated files —
# the generator uses them to locate and re-inject custom code on --overwrite.
_CUSTOM_BEGIN = "    # ── CUSTOM EXTENSIONS BEGIN"
_CUSTOM_END   = "    # ── CUSTOM EXTENSIONS END"


# ===========================================================================
# ── Module 1: Discovery ─────────────────────────────────────────────────────
# ===========================================================================


def fetch_reverse_foreign_keys(con, schema: str, table: str) -> list:
    """
    Return every table that has a foreign key pointing into schema.table.

    Each item is a dict with keys:
        referencing_schema, referencing_table, referencing_column,
        local_column, constraint_name.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name of the target table.
        table:  Table name of the target table.

    Returns:
        List of reverse-FK dicts ordered by referencing schema and table.
    """
    with con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                tc.table_schema   AS referencing_schema,
                tc.table_name     AS referencing_table,
                kcu.column_name   AS referencing_column,
                ccu.column_name   AS local_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema    = kcu.table_schema
             AND tc.table_name      = kcu.table_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_schema   = %s
              AND ccu.table_name     = %s
            ORDER BY tc.table_schema, tc.table_name
            """,
            (schema, table),
        )
        return [dict(row) for row in cur.fetchall()]


def is_join_table(con, schema: str, table: str) -> bool:
    """
    Return True if schema.table is a pure join table.

    A table is treated as a join table when both:
      - It has exactly 2 columns that are foreign keys.
      - Its primary key is the composite of those exact same 2 columns.

    Args:
        con:    Open psycopg2 connection.
        schema: Schema name.
        table:  Table name.

    Returns:
        True if the table is a pure join table, False otherwise.
    """
    fks = fetch_foreign_keys(con, schema, table)
    pks = fetch_primary_keys(con, schema, table)

    if len(fks) != 2:
        return False

    fk_columns = {fk["column_name"] for fk in fks}
    return fk_columns == pks


def _collect_join_references(con, schema: str, table: str, database: str) -> list:
    """
    For each join table that references schema.table, collect metadata
    about both sides of the join.

    Each item is a dict:
        join_schema, join_table, my_column, other_column,
        other_table, other_schema.

    Args:
        con:      Open psycopg2 connection.
        schema:   Schema of the owning table.
        table:    Name of the owning table.
        database: Database name (used for join-schema detection).

    Returns:
        List of join-reference dicts.
    """
    reverse_fks = fetch_reverse_foreign_keys(con, schema, table)
    refs = []

    for rfk in reverse_fks:
        ref_schema = rfk["referencing_schema"]
        ref_table = rfk["referencing_table"]
        my_col = rfk["referencing_column"]

        if not is_join_table(con, ref_schema, ref_table):
            continue

        # Find the FK in the join table that does NOT point back to us —
        # that's the "other side" of the relationship.
        join_fks = fetch_foreign_keys(con, ref_schema, ref_table)
        other_fk = next(
            (fk for fk in join_fks if fk["column_name"] != my_col),
            None,
        )
        if not other_fk:
            continue

        refs.append(
            {
                "join_schema": ref_schema,
                "join_table": ref_table,
                "my_column": my_col,
                "other_column": other_fk["column_name"],
                "other_table": other_fk["foreign_table"],
                "other_schema": other_fk["foreign_schema"],
            }
        )

    return refs


def collect_table_data(con, schema: str, table: str, database: str) -> dict:
    """
    Gather all metadata needed to render a class for schema.table.

    Args:
        con:      Open psycopg2 connection.
        schema:   Schema name.
        table:    Table name.
        database: Database name.

    Returns:
        Dict with keys: columns, primary_keys, foreign_keys, join_references.
    """
    columns = fetch_columns(con, schema, table)
    primary_keys = fetch_primary_keys(con, schema, table)
    foreign_keys = fetch_foreign_keys(con, schema, table)
    join_references = _collect_join_references(con, schema, table, database)
    return {
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "join_references": join_references,
    }


# ===========================================================================
# ── Module 2: Code Generation ───────────────────────────────────────────────
# ===========================================================================


def _to_pascal_case(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    return "".join(w.capitalize() for w in re.split(r"[_\-\s]+", name))


def _to_env_key(s: str) -> str:
    """Convert a string to UPPER_SNAKE_CASE for use in env var names."""
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")


def _detect_join_schema(database: str) -> str:
    """Return the conventional join-table schema name for a given database."""
    if database == "example_db":
        return "join_tables"
    if database == "example_db":
        return "Join"
    return "public"


def _render_init(
    class_name: str,
    database: str,
    schema: str,
    table: str,
    columns: list,
    primary_keys: set,
    join_references: list,
    pk_col: str,
    is_composite: bool,
    db_key: str,
    schema_key: str,
    table_key: str,
    join_schema_default: str,
) -> list:
    """Return lines for the __init__ method."""
    lines = []

    if is_composite:
        lines.append("    def __init__(self, pk: dict = None):")
        lines.append("        # TODO: composite PK — pk is a dict of {column: value}")
    else:
        lines.append("    def __init__(self, pk=None):")

    lines += [
        "        # --- config ---",
        f"        self.database    = os.getenv('GEN_{db_key}_DATABASE',    '{database}')",
        f"        self.schema      = os.getenv('GEN_{db_key}_{schema_key}_SCHEMA',      '{schema}')",
        f"        self.table       = os.getenv('GEN_{db_key}_{schema_key}_{table_key}_TABLE',       '{table}')",
        f"        self.join_schema = os.getenv('GEN_{db_key}_JOIN_SCHEMA', '{join_schema_default}')",
        "",
        "        # --- column attributes ---",
    ]

    for col in columns:
        cname = col["column_name"]
        if cname in primary_keys:
            lines.append(f"        self.{cname} = pk")
        else:
            lines.append(f"        self.{cname} = None")

    if join_references:
        lines.append("")
        lines.append("        # --- relationship attributes ---")
        for ref in join_references:
            attr = _to_env_key(ref["other_table"]).lower()
            lines.append(f"        self.{attr}_pks = []")

    lines += [
        "",
        "        if pk:",
        "            self.load(pk)",
        "",
    ]
    return lines


def _render_load(pk_col: str, is_composite: bool) -> list:
    """Return lines for the load() method."""
    lines = [
        "    # ------------------------------------------------------------------ load",
        "",
    ]
    if is_composite:
        lines += [
            "    def load(self, pk: dict) -> bool:",
            "        # TODO: composite PK — implement custom query using pk dict",
            "        raise NotImplementedError('Composite PK load not auto-generated')",
            "",
        ]
    else:
        lines += [
            "    def load(self, pk) -> bool:",
            '        """Fetch the record from the database and populate attributes."""',
            "        record = get_record(",
            "            database=self.database,",
            "            schema=self.schema,",
            "            table=self.table,",
            f"            column='{pk_col}',",
            "            value=pk,",
            "        )",
            "        if not record:",
            "            return False",
            "        for key, val in record.items():",
            "            if hasattr(self, key):",
            "                setattr(self, key, val)",
            "        return True",
            "",
        ]
    return lines


def _render_save(col_names: list, pk_col: str, is_composite: bool, pk_list: list) -> list:
    """Return lines for the save() method."""
    col_list_str = ", ".join(f"'{c}'" for c in col_names)
    val_list_str = ", ".join(f"self.{c}" for c in col_names)
    conflict_target = (
        "[" + ", ".join(f"'{p}'" for p in pk_list) + "]"
        if is_composite
        else f"['{pk_col}']"
    )

    lines = [
        "    # ------------------------------------------------------------------ save",
        "",
        "    def save(self) -> bool:",
        '        """Upsert this record (insert or update on conflict)."""',
    ]
    if not is_composite:
        lines += [
            f"        if not self.{pk_col}:",
            "            import uuid",
            f"            self.{pk_col} = str(uuid.uuid4())",
            "",
        ]
    lines += [
        f"        columns = [{col_list_str}]",
        f"        values  = [{val_list_str}]",
        "",
        "        add_update_record(",
        "            database=self.database,",
        "            schema=self.schema,",
        "            table=self.table,",
        "            columns=columns,",
        "            values=values,",
        f"            conflict_target={conflict_target},",
        "            on_conflict='DO UPDATE SET',",
        "        )",
        "        return True",
        "",
    ]
    return lines


def _render_delete(pk_col: str, join_references: list) -> list:
    """Return lines for the delete() method."""
    lines = [
        "    # ------------------------------------------------------------------ delete",
        "",
        "    def delete(self) -> bool:",
        '        """Delete all join-table references for this record, then delete the record."""',
        f"        if not self.{pk_col}:",
        "            return False",
        "",
    ]

    if join_references:
        lines.append("        # --- join-table cleanup ---")
        for ref in join_references:
            lines += [
                "        delete_record(",
                "            database=self.database,",
                "            schema_name=self.join_schema,",
                f"            table_name='{ref['join_table']}',",
                f"            columns=['{ref['my_column']}'],",
                f"            values=[self.{pk_col}],",
                "        )",
            ]
        lines.append("")

    lines += [
        "        # --- delete main record ---",
        "        delete_record(",
        "            database=self.database,",
        "            schema_name=self.schema,",
        "            table_name=self.table,",
        f"            columns=['{pk_col}'],",
        f"            values=[self.{pk_col}],",
        "        )",
        f"        self.{pk_col} = None",
        "        return True",
        "",
    ]
    return lines


def _render_relations(pk_col: str, join_references: list) -> list:
    """Return lines for all get_X_relations / update_X_relations method pairs."""
    if not join_references:
        return []

    lines = [
        "    # ------------------------------------------------------------------ relations",
        "",
    ]
    for ref in join_references:
        attr = _to_env_key(ref["other_table"]).lower()
        jt = ref["join_table"]
        my_col = ref["my_column"]
        other_col = ref["other_column"]

        lines += [
            f"    def get_{attr}_relations(self) -> list:",
            f'        """Return all {ref["other_table"]} PKs linked to this record."""',
            "        records = get_records(",
            "            database=self.database,",
            "            schema=self.join_schema,",
            f"            table='{jt}',",
            f"            column='{my_col}',",
            f"            values=self.{pk_col},",
            "        )",
            f"        self.{attr}_pks = [r['{other_col}'] for r in records]",
            f"        return self.{attr}_pks",
            "",
            f"    def update_{attr}_relations(self) -> None:",
            f'        """Sync self.{attr}_pks to the join table (add new, remove missing)."""',
            f"        existing = self.get_{attr}_relations()",
            "",
            "        for existing_pk in existing:",
            f"            if existing_pk not in self.{attr}_pks:",
            "                delete_record(",
            "                    database=self.database,",
            "                    schema_name=self.join_schema,",
            f"                    table_name='{jt}',",
            f"                    columns=['{my_col}', '{other_col}'],",
            f"                    values=[self.{pk_col}, existing_pk],",
            "                )",
            "",
            f"        for new_pk in self.{attr}_pks:",
            "            add_update_record(",
            "                database=self.database,",
            "                schema=self.join_schema,",
            f"                table='{jt}',",
            f"                columns=['{my_col}', '{other_col}'],",
            f"                values=[self.{pk_col}, new_pk],",
            f"                conflict_target=['{my_col}', '{other_col}'],",
            "                on_conflict='DO NOTHING',",
            "            )",
            "",
        ]
    return lines


def _render_custom_block() -> list:
    """Return the sentinel block where hand-written class extensions are preserved."""
    return [
        "",
        "    # ── CUSTOM EXTENSIONS BEGIN — preserved across regeneration ─────────────────",
        "    # Add custom methods below. Use 4-space indentation (standard class body).",
        "    # Do not remove or modify either sentinel comment line.",
        "",
        "    # ── CUSTOM EXTENSIONS END ────────────────────────────────────────────────────",
    ]


def _render_to_dict(col_names: list) -> list:
    """Return lines for the to_dict() method."""
    lines = [
        "    # ------------------------------------------------------------------ utility",
        "",
        "    def to_dict(self) -> dict:",
        '        """Return column attributes as a plain dict (no relation lists)."""',
        "        return {",
    ]
    for cname in col_names:
        lines.append(f"            '{cname}': self.{cname},")
    lines.append("        }")
    return lines


def render_class(
    database: str,
    schema: str,
    table: str,
    columns: list,
    primary_keys: set,
    foreign_keys: list,
    join_references: list,
) -> str:
    """
    Generate the full Python source for a class representing schema.table.

    Args:
        database:        Database name.
        schema:          Schema name.
        table:           Table name.
        columns:         Column dicts from fetch_columns().
        primary_keys:    Set of PK column names from fetch_primary_keys().
        foreign_keys:    FK dicts from fetch_foreign_keys() (FKs FROM this table).
        join_references: Join-reference dicts from _collect_join_references().

    Returns:
        String of valid Python source code.
    """
    class_name = _to_pascal_case(table)
    db_key = _to_env_key(database)
    schema_key = _to_env_key(schema)
    table_key = _to_env_key(table)
    join_schema_default = _detect_join_schema(database)

    pk_list = sorted(primary_keys)
    is_composite = len(pk_list) > 1
    pk_col = pk_list[0] if pk_list else "pk"
    col_names = [c["column_name"] for c in columns]

    lines = [
        f'"""Auto-generated SQL model for {schema}.{table}.',
        "Generated by db_object_generator.py — do not edit directly.",
        f"Regenerate with: python db_object_generator.py {database} --schema {schema} --table {table}",
        '"""',
        "",
        "from pathlib import Path",
        "",
        "FILE_PATH = Path(__file__).resolve()",
        "ROOT_PATH = FILE_PATH.parents[5]",
        "SRC_PATH  = FILE_PATH.parents[4]",
        "",
        "import sys, os",
        "if str(SRC_PATH) not in sys.path:",
        "    sys.path.append(str(SRC_PATH))",
        "",
        "from dotenv import load_dotenv",
        "load_dotenv(ROOT_PATH / '.env')",
        "",
        "from extras.sql_helper import get_record, get_records, add_update_record, delete_record",
        "",
        "",
        f"class {class_name}:",
    ]

    lines += _render_init(
        class_name,
        database,
        schema,
        table,
        columns,
        primary_keys,
        join_references,
        pk_col,
        is_composite,
        db_key,
        schema_key,
        table_key,
        join_schema_default,
    )
    lines += _render_load(pk_col, is_composite)
    lines += _render_save(col_names, pk_col, is_composite, pk_list)
    lines += _render_delete(pk_col, join_references)
    lines += _render_relations(pk_col, join_references)
    lines += _render_to_dict(col_names)
    lines += _render_custom_block()

    return "\n".join(lines) + "\n"


# ===========================================================================
# ── Module 3: File Management ───────────────────────────────────────────────
# ===========================================================================


def get_output_path(database: str, schema: str, table: str) -> Path:
    """
    Return the output path for a generated class file.

    Files are written to src/sql/generated/{database}/{schema}/{table}.py.

    Args:
        database: Database name.
        schema:   Schema name.
        table:    Table name.

    Returns:
        pathlib.Path of the output file.
    """
    path = OUTPUT_BASE / database / schema / f"{table}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _extract_custom_block(content: str) -> str:
    """
    Return the text between the custom-extension sentinels in an existing
    generated file, or an empty string if no sentinels are found.

    The returned string includes the trailing newline after _CUSTOM_BEGIN
    up to (but not including) the line that starts with _CUSTOM_END, so it
    can be spliced directly back into a new generated file.

    Args:
        content: Full text of an existing generated class file.

    Returns:
        Preserved custom content string, or "" if sentinels are absent.
    """
    begin = content.find(_CUSTOM_BEGIN)
    end   = content.find(_CUSTOM_END)
    if begin == -1 or end == -1 or end <= begin:
        return ""
    inner_start = content.index("\n", begin) + 1
    return content[inner_start:end]


def write_object_file(path: Path, content: str, overwrite: bool = False) -> bool:
    """
    Write a generated class file to disk.

    When overwriting an existing file, any code between the custom-extension
    sentinel lines is extracted from the old file and re-injected into the
    new content before writing, so hand-written additions are preserved.

    Args:
        path:      Destination path.
        content:   Python source content.
        overwrite: If False (default), skip files that already exist.

    Returns:
        True if written, False if skipped.
    """
    if path.exists() and not overwrite:
        print(f"[SKIP] {path} already exists (use --overwrite to replace)")
        return False

    # Re-inject any preserved custom code from the existing file.
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        custom = _extract_custom_block(existing)
        if custom:
            begin_idx = content.find(_CUSTOM_BEGIN)
            end_idx   = content.find(_CUSTOM_END)
            if begin_idx != -1 and end_idx != -1:
                inner_start = content.index("\n", begin_idx) + 1
                content = content[:inner_start] + custom + content[end_idx:]
                print(f"[INFO] Custom extensions preserved in {path.name}")

    path.write_text(content, encoding="utf-8")
    print(f"[OK] Written → {path}")
    return True


# ===========================================================================
# ── Module 4: Orchestration ─────────────────────────────────────────────────
# ===========================================================================


def _generate_table(
    con,
    database: str,
    schema: str,
    table: str,
    overwrite: bool,
) -> None:
    """Collect data and write the class file for one table."""
    print(f"  ↳ {schema}.{table}")
    pks = fetch_primary_keys(con, schema, table)
    if not pks:
        print(f"[WARN] Skipping {schema}.{table} — no primary key found")
        return

    if is_join_table(con, schema, table):
        print(f"[SKIP] {schema}.{table} — detected as join table, skipped")
        return

    data = collect_table_data(con, schema, table, database)
    content = render_class(
        database=database,
        schema=schema,
        table=table,
        columns=data["columns"],
        primary_keys=data["primary_keys"],
        foreign_keys=data["foreign_keys"],
        join_references=data["join_references"],
    )
    path = get_output_path(database, schema, table)
    write_object_file(path, content, overwrite=overwrite)


def run_full_generate(
    database: str,
    con,
    scoped_schema: str | None = None,
    scoped_table: str | None = None,
    overwrite: bool = False,
) -> None:
    """
    Generate class files for all (or scoped) tables in database.

    Args:
        database:      Database name.
        con:           Open psycopg2 connection.
        scoped_schema: Limit to this schema only.
        scoped_table:  Limit to this table only (requires scoped_schema).
        overwrite:     Replace existing files.
    """
    schemas = [scoped_schema] if scoped_schema else fetch_schemas(con)
    schemas = [s for s in schemas if s not in _SYSTEM_SCHEMAS]

    for schema in schemas:
        print(f"[INFO] Processing schema: {schema}")
        tables = [scoped_table] if scoped_table else fetch_tables(con, schema)
        for table in tables:
            _generate_table(con, database, schema, table, overwrite)


def update_generate(
    database: str,
    con,
    scoped_schema: str | None = None,
    overwrite: bool = False,
) -> None:
    """
    Generate class files only for tables that don't already have one.

    Args:
        database:      Database name.
        con:           Open psycopg2 connection.
        scoped_schema: Limit to this schema only.
        overwrite:     Replace existing files (same as run_full_generate).
    """
    schemas = [scoped_schema] if scoped_schema else fetch_schemas(con)
    schemas = [s for s in schemas if s not in _SYSTEM_SCHEMAS]

    for schema in schemas:
        print(f"[INFO] Processing schema: {schema}")
        tables = fetch_tables(con, schema)
        for table in tables:
            path = get_output_path(database, schema, table)
            if path.exists() and not overwrite:
                print(f"[SKIP] {schema}.{table} — file exists")
                continue
            _generate_table(con, database, schema, table, overwrite)


# ===========================================================================
# ── CLI ─────────────────────────────────────────────────────────────────────
# ===========================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="db_object_generator",
        description="Generate Python class files from a PostgreSQL database schema.",
    )
    parser.add_argument("database", help="PostgreSQL database name (e.g. example_db)")
    parser.add_argument(
        "--schema", "-s", metavar="SCHEMA", help="Limit output to this schema only."
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
        help="Only generate files for tables that don't already have one.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate all files, replacing existing ones.",
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
            update_generate(
                database=args.database,
                con=con,
                scoped_schema=args.schema,
                overwrite=args.overwrite,
            )
        else:
            run_full_generate(
                database=args.database,
                con=con,
                scoped_schema=args.schema,
                scoped_table=args.table,
                overwrite=args.overwrite,
            )
    finally:
        release_connection(con)


if __name__ == "__main__":
    main()
