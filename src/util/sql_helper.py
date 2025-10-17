#!/usr/bin/env python3
# Aria Corona 2025/06/09

"""
SQL Helper Module Summary
========================

Purpose: PostgreSQL database helper functions and utilities
Total Lines: 1,204 lines
Dependencies: psycopg2, json, colorama, pathlib, rapidfuzz

Configuration:
- Loads PostgreSQL credentials from conf/cred/psql.json
- Default connection parameters: sql_ip, sql_port, sql_user, sql_pass

Functions & Methods Inventory:

🔌 CONNECTION FUNCTIONS
- init_psql_connection(): PostgreSQL connection factory with auto-retry
- init_psql_con_cursor(): Decorator that injects connection/cursor, handles cleanup
- create_cursor(): Creates new cursor for given connection

📊 RECORD QUERY FUNCTIONS
- get_record(): Query single record by unique key
- get_records(): Query multiple records matching list of values
- search_records(): Query records matching single value
- fuzzy_search_records(): Text pattern search using LIKE/ILIKE/regex
- edit_distance_search_records(): Levenshtein distance fuzzy search (requires fuzzystrmatch)
- similarity_search_records(): Trigram similarity search (requires pg_trgm)
- get_all_records(): Fetch all records from table
- fetch_top(): Fetch top N records with sorting and pagination

✏️ RECORD MODIFICATION FUNCTIONS
- update_existing_record(): Update existing record by WHERE condition
- add_join_records(): Add records to join tables with conflict handling
- add_update_record(): Upsert operation (INSERT or UPDATE)
- update_record(): Alias for add_update_record()
- delete_record(): Delete records matching criteria

🏗️ SCHEMA/TABLE MANAGEMENT FUNCTIONS
- get_tables(): List all tables in schema
- ensure_table_exists(): Create table if not exists, ensure columns exist
- find_table_name(): Fuzzy table name matching with multi-stage resolution
- add_column_to_table(): Add column to existing table
- get_column_data_type(): Get data type of specific column
- get_column_comments(): Retrieve column comments from table
- get_primary_key_info(): Get primary key constraint details
- add_pk_constraint(): Add primary key constraint to table

🛠️ UTILITY FUNCTIONS
- guess_column_type(): Infer SQL column type from Python value

Key Features:
- Decorator Pattern: Auto connection/cursor injection and cleanup
- Security: Parameterized queries, SQL identifier escaping
- Error Handling: Comprehensive exception handling, transaction rollback
- Advanced Search: Pattern matching, regex, fuzzy matching, trigram similarity
- Schema Management: Dynamic table/column creation, constraint handling
- Performance: Batch operations, connection reuse, pagination support
"""

import psycopg2, json
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
from functools import wraps
from colorama import Fore
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # alice/
# Access psql defaults
with open(ROOT_DIR / "conf" / "cred" / "psql.json", "r") as f:
    psql_cred = json.load(f)
sql_ip = psql_cred.get("ip", "")
sql_port = psql_cred.get("port", "")
sql_user = psql_cred.get("user", "")
sql_pass = psql_cred.get("password", "")

# ============================================#      ######
# ==========# Connection functions #==========#    ###    E
# ============================================#      ######


def init_psql_connection(
    db,
    host=sql_ip,
    port=sql_port,
    user=sql_user,
    password=sql_pass,
    _rt=False,
) -> object:
    """
    psycopg2 connection factory.
    Args:
        db (str) : Database name **REQUIRED**
        host (str) : PostgreSQL Host IP
        port (int) : PostgreSQL Host Port
        user (str) : User registed in PSQL Server
        password (str) : Password for user.
    Returns:
        con (object) : Instance of the psycopg2.connect object.
    """
    try:
        con = psycopg2.connect(
            dbname=db, user=user, password=password, host=host, port=port
        )
    except psycopg2.Error as e:
        print(Fore.RED + f"Error connecting to database: {e}" + Fore.RESET)
        if _rt:
            print(Fore.RED + "Could not establish connection." + Fore.RESET)
            raise psycopg2.Error(f"Could not establish connection: {e}")
        else:
            print(Fore.RED + "Retrying connection..." + Fore.RESET)
            return init_psql_connection(db, host, port, user, password, _rt=True)

    return con


def init_psql_con_cursor(func):
    """
    If the function is given a connection and cursor, it will use them.
    If not, it will create a new psycopg2 connection and cursor.
    This decorator is used to ensure that the function has a valid
    Inserts connection and cursor into the decorated function args.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract DB connection details from kwargs
        db = kwargs.get("database", "accounts")
        host = kwargs.pop("host", sql_ip)
        port = kwargs.pop("port", sql_port)
        user = kwargs.pop("user", sql_user)
        password = kwargs.pop("password", sql_pass)

        connection = kwargs.pop("connection", None)
        cursor = kwargs.pop("cursor", None)

        needs_new_connection = (
            connection is None
            or cursor is None
            or (connection is not None and connection.closed != 0)
            or (cursor is not None and cursor.closed)
        )

        if needs_new_connection:
            con = init_psql_connection(db, host, port, user, password)
            cur = con.cursor(cursor_factory=RealDictCursor)
            try:
                # Inject cursor into the decorated function
                result = func(cur, con, *args, **kwargs)
                return result
            finally:
                cur.close()
                con.close()
        else:
            con = connection
            cur = cursor
            return func(cur, con, *args, **kwargs)

    return wrapper


def create_cursor(
    connection: object,
    cursor_factory=RealDictCursor,
) -> object:
    """
    Create a new cursor for the given connection.
    """
    return connection.cursor(cursor_factory=cursor_factory)


# ========================================#        ####
# ==========# Record Functions #==========#        ####
# ========================================#        ####


@init_psql_con_cursor
def get_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    column: str,
    value: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> dict:
    """
    Query a postgreSQL table for a single record. Intended to get records by primary or
    other unique key.
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
        column (str) : Required, column name to query by
        value (str) : Required, value to query by
    Returns:
        record (dict) : RealDictCursor dictionary fetched with the fetchone() method.
    """
    query = f'SELECT * FROM "{schema}"."{table}" WHERE "{column}" = %s'
    cursor.execute(query, (value,))
    record = cursor.fetchone()
    return record


@init_psql_con_cursor
def get_records(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    column: str,
    values: list,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list:
    """
    Query a postgreSQL table for a list of records matching any the given values.
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
        column (str) : Required, column name to query by
        value (any) : Required, value to query by
    Returns:
        records (list) : List of RealDictCursor dictionaries.
    """
    if not isinstance(values, list):
        values = [values]

    schema_str = sql.Identifier(schema)
    table_str = sql.Identifier(table)
    column_str = sql.Identifier(column)

    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in values)

    records = []
    query = sql.SQL(
        "SELECT * FROM {schema}.{table} WHERE {column} IN ({placeholders})"
    ).format(
        schema=schema_str, table=table_str, column=column_str, placeholders=placeholders
    )

    cursor.execute(query, values)
    records = cursor.fetchall()
    return records


@init_psql_con_cursor
def search_records(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    column: str,
    value: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Query a postgreSQL table for a list of records matching the given single value.
    To query by multiple values, use get_records(...)
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
        column (str) : Required, column name to query by
        value (str) : Required, value to query by
    Returns:
        records (list[dict]) : List of RealDictCursor dictionaries fetched with the
            fetchall() method.
    """
    schema_str = sql.Identifier(schema)
    table_str = sql.Identifier(table)
    column_str = sql.Identifier(column)
    query = sql.SQL("SELECT * FROM {schema}.{table} WHERE {column} = %s").format(
        schema=schema_str, table=table_str, column=column_str
    )

    cursor.execute(query, (value,))
    records = cursor.fetchall()
    return records


@init_psql_con_cursor
def fuzzy_search_records(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    column_name: str,
    search_pattern: str,
    case_sensitive: bool = False,
    pattern_negation: bool = False,
    escape_char: str = None,
    regex: bool = False,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Use text patterns to search for records in a PostgreSQL table.
    `%` is used to match any sequence of characters (including an empty sequence).
    `_` is used to match any single character.

    Args:
        cursor (object) : psycopg2 cursor object, uses provided. (injected by decorator, uses RealDictCursor)
        connection (object) : psycopg2 connection object, uses provided. (injected by decorator)
        database (str) : Required, name of database to be queried
        schema_name (str) : Required, name of schema to be queried
        table_name (str) : Required, name of table to be queried
        column_name (str) : Required, column name to query by
        search_pattern (str) : Required, pattern to search for
        case_sensitive (bool) : Whether the search should be case-sensitive (default: False)
        pattern_negation (bool) : Whether to negate the pattern match (default: False)
        escape_char (str) : Optional character to escape special characters in the pattern
        regex (bool) : Whether to use regex matching instead of LIKE/ILIKE (default: False)
    Returns:
        records (list[dict]) : List of RealDictCursor dictionaries fetched with the
            fetchall() method.
    """
    schema_obj = sql.Identifier(schema_name)
    table_obj = sql.Identifier(table_name)
    col_obj = sql.Identifier(column_name)
    not_str = "NOT" if pattern_negation else ""
    escape_str = f"ESCAPE '{escape_char}'" if escape_char else ""

    if regex:
        func_str = "~*"
    elif case_sensitive:
        func_str = "LIKE"
        if not "%" in search_pattern and not "_" in search_pattern:
            search_pattern = f"%{search_pattern}%"
    else:
        func_str = "ILIKE"
        if not "%" in search_pattern and not "_" in search_pattern:
            search_pattern = f"%{search_pattern}%"

    query = (
        sql.SQL(
            """
        SELECT * FROM {schema}.{table}
        WHERE {col} {NOT} {FUNC} %s {ESCAPE}
    """
        )
        .replace("{NOT}", not_str)
        .replace("{FUNC}", func_str)
        .replace("{ESCAPE}", escape_str)
        .format(
            schema=schema_obj,
            table=table_obj,
            col=col_obj,
        )
    )

    try:
        cursor.execute(query, (search_pattern,))
        records = cursor.fetchall()
        return records
    except Exception as e:
        # eventually ill add an in-module logger
        raise e


@init_psql_con_cursor
def edit_distance_search_records(
    cursor,
    connection,
    database,
    schema_name,
    table_name,
    column_name,
    search_pattern,
    max_distance: int = 2,
    limit: int = 10,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Use edit_distance string matching to search for records in a PostgreSQL table.
    Requires the `fuzzystrmatch` extension to be enabled on the database.
    Args:
        cursor (object) : psycopg2 cursor object, uses provided. (injected by decorator, uses RealDictCursor)
        connection (object) : psycopg2 connection object, uses provided. (injected by decorator)
        database (str) : Required, name of database to be queried
        schema_name (str) : Required, name of schema to be queried
        table_name (str) : Required, name of table to be queried
        column_name (str) : Required, column name to query by
        search_pattern (str) : Required, pattern to search for
        max_distance (int) : Maximum Levenshtein distance for matches (default: 2)
        limit (int) : Maximum number of records to return (default: 10)
    Returns:
        records (list[dict]) : List of RealDictCursor dictionaries fetched with the
            fetchall() method.
    """
    schema_obj = sql.Identifier(schema_name)
    table_obj = sql.Identifier(table_name)
    col_obj = sql.Identifier(column_name)

    query = sql.SQL(
        """
        SELECT {col}, LEVENSHTEIN({col}, %s) AS distance
        FROM {schema}.{table}
        WHERE LEVENSHTEIN({col}, %s) <= %s
        ORDER BY distance
        LIMIT %s
    """
    ).format(
        schema=schema_obj,
        table=table_obj,
        col=col_obj,
    )

    try:
        cursor.execute(query, (search_pattern, search_pattern, max_distance, limit))
        records = cursor.fetchall()
        return records
    except Exception as e:
        raise e


@init_psql_con_cursor
def similarity_search_records(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    column_name: str,
    search_pattern: str,
    limit: int = 10,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Run a similarity search on a PostgreSQL table using the pg_trgm extension.
    Requires the `pg_trgm` extension to be enabled on the database.
    Args:
        cursor (object) : psycopg2 cursor object, uses provided. (injected by decorator, uses RealDictCursor)
        connection (object) : psycopg2 connection object, uses provided. (injected by decorator)
        database (str) : Required, name of database to be queried
        schema_name (str) : Required, name of schema to be queried
        table_name (str) : Required, name of table to be queried
        column_name (str) : Required, column name to query by
        search_pattern (str) : Required, pattern to search for
        limit (int) : Maximum number of records to return (default: 10)
    Returns:
        records (list[dict]) : List of RealDictCursor dictionaries fetched with the
            fetchall() method.
    """
    schema_obj = sql.Identifier(schema_name)
    table_obj = sql.Identifier(table_name)
    col_obj = sql.Identifier(column_name)

    query = sql.SQL(
        """
        SELECT {col}, SIMILARITY({col}, %s) AS similar
        FROM {schema}.{table}
        WHERE {col} % %s
        ORDER BY similar DESC
        LIMIT %s
    """
    ).format(
        schema=schema_obj,
        table=table_obj,
        col=col_obj,
    )

    try:
        cursor.execute(query, (search_pattern, search_pattern, limit))
        records = cursor.fetchall()
        return records
    except Exception as e:
        raise e


@init_psql_con_cursor
def get_all_records(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Query a postgreSQL table for all records.
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
    Returns:
        records (list) : List of RealDictCursor dictionaries.
    """
    query = f'SELECT * FROM "{schema}"."{table}"'
    cursor.execute(query)
    records = cursor.fetchall()
    return records


@init_psql_con_cursor
def get_filtered_records(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    filters: list[dict] = [],
    sort_by: str = None,
    descending: bool = True,
    nulls_last: bool = True,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list:
    """
    Query a PostgreSQL table for records matching the given filters.
    Args:
        database (str) : Required, name of database to be queried
        schema_name (str) : Required, name of schema to be queried
        table_name (str) : Required, name of table to be queried
        filters (list[dict]) : List of filter dictionaries. Each dictionary should have:
            - logic (str{'AND', 'OR'}) : Logical operator to combine with previous filter
            - rules (list[dict]) : List of rule dictionaries. Each rule should have:
                - property (str) : Column name to filter on
                - operator (str) : Named operators:
                    - contains : ILIKE '%value%'
                    - equals : = 'value'
                    - does_not_contain : NOT ILIKE '%value%'
                    - starts_with : ILIKE 'value%'
                    - ends_with : ILIKE '%value'
                    - greater_than : > 'value'
                    - less_than : < 'value'
                    - greater_than_or_equal_to : >= 'value'
                    - less_than_or_equal_to : <= 'value'
                    - not_equals : != 'value'
                    - is_empty : IS NULL OR = ''
                    - is_not_empty : IS NOT NULL AND != ''
                - value (any) : Value to compare against
                - logic (str{'AND', 'OR'}) : Logical operator to combine with previous rule
        sort_by (str) : Optional, column name to sort by
        descending (bool) : Whether to sort in descending order (default: True)
        nulls_last (bool) : Whether NULL values should appear last (default: True)
    """

    def build_rule(rule):
        col_str = rule.get("property", "")
        col = sql.Identifier(col_str)
        op = rule["operator"].lower()
        value = rule.get("value", "")

        if op in ["contains", "does_not_contain"]:
            value = f"%{value}%"
            op_sql = "ILIKE" if op == "contains" else "NOT ILIKE"
            return sql.SQL("{col} {op} %s").format(col=col, op=sql.SQL(op_sql)), value
        elif op == "starts_with":
            value = f"{value}%"
            return sql.SQL("{col} ILIKE %s").format(col=col), value
        elif op == "ends_with":
            value = f"%{value}"
            return sql.SQL("{col} ILIKE %s").format(col=col), value
        elif op in ["is_empty", "is_not_empty"]:
            if op == "is_empty":
                return sql.SQL("({col} IS NULL OR {col} = '')").format(col=col), None
            else:
                return (
                    sql.SQL("({col} IS NOT NULL AND {col} != '')").format(col=col),
                    None,
                )
        elif op in [
            "equals",
            "not_equals",
            "greater_than",
            "less_than",
            "greater_than_or_equal_to",
            "less_than_or_equal_to",
        ]:
            op_map = {
                "equals": "=",
                "not_equals": "!=",
                "greater_than": ">",
                "less_than": "<",
                "greater_than_or_equal_to": ">=",
                "less_than_or_equal_to": "<=",
            }
            if op not in op_map:
                raise ValueError(f"Unsupported operator: {op}")
            return (
                sql.SQL("{col} {op} %s").format(col=col, op=sql.SQL(op_map[op])),
                value,
            )
        else:
            raise ValueError(f"Unsupported operator: {op}")

    def build_group(filter):
        rules = filter.get("rules", [])
        rule_parts = []
        values = []
        group_logic = filter.get("logic", "AND").upper()

        if group_logic not in ["AND", "OR"]:
            raise ValueError("Group logic must be 'AND' or 'OR'.")

        if not rules:
            return sql.SQL(""), []

        for index, rule in enumerate(rules):
            if "property" not in rule or "operator" not in rule:
                raise ValueError("Each rule must have 'property' and 'operator' keys.")

            if index > 0:
                rule_parts.append(sql.SQL(f" {group_logic} "))

            rule_sql, rule_value = build_rule(rule)
            rule_parts.append(rule_sql)

            if rule_value is not None:
                values.append(rule_value)

        if len(rule_parts) == 1:
            return rule_parts[0], values

        group_sql = sql.SQL("({})").format(sql.SQL("").join(rule_parts))
        return group_sql, values

    schema_obj = sql.Identifier(schema_name)
    table_obj = sql.Identifier(table_name)
    where_parts = []
    all_values = []

    for index, filter in enumerate(filters):
        if "rules" not in filter or not filter["rules"]:
            continue

        if index > 0:
            filter_logic = filter.get("logic", "AND").upper()
            if filter_logic not in ["AND", "OR"]:
                raise ValueError("Filter logic must be 'AND' or 'OR'.")
            where_parts.append(sql.SQL(f" {filter_logic} "))

        group_sql, group_values = build_group(filter)
        where_parts.append(group_sql)
        all_values.extend(group_values)

    where_clause = sql.SQL("")
    if where_parts:
        where_clause = sql.SQL("WHERE {}").format(sql.SQL("").join(where_parts))

    sort_clause = sql.SQL("")
    if sort_by:
        sort_clause = sql.SQL("ORDER BY {sort_col} {order} NULLS {nulls}").format(
            sort_col=sql.Identifier(sort_by),
            order=sql.SQL("DESC") if descending else sql.SQL("ASC"),
            nulls=sql.SQL("LAST") if nulls_last else sql.SQL("FIRST"),
        )

    query = sql.SQL(
        """
    SELECT * FROM {schema}.{table}
    {where}
    {sort}
    """
    ).format(schema=schema_obj, table=table_obj, where=where_clause, sort=sort_clause)
    print(query.as_string(cursor))
    print(query)
    try:
        cursor.execute(query, all_values)
        records = cursor.fetchall()
        return records
    except Exception as e:
        connection.rollback()
        raise e


@init_psql_con_cursor
def fetch_top(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    sort_col: str,
    sort_desc: bool = True,
    limit: int = 1,
    offset: int = 0,
    nulls_last: bool = True,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list[dict]:
    """
    Fetch the top N records from a PostgreSQL table, ordered by a specified column.
    Args:
        cursor (object) : psycopg2 cursor object, uses provided. (injected by decorator, uses RealDictCursor)
        connection (object) : psycopg2 connection object, uses provided. (injected by decorator)
        database (str) : Required, name of database to be queried
        schema_name (str) : Required, name of schema to be queried
        table_name (str) : Required, name of table to be queried
        sort_col (str) : Required, column name to sort by
        sort_desc (bool) : Whether to sort in descending order (default: True)
        limit (int) : Number of records to fetch (default: 1)
        offset (int) : Number of records to skip (default: 0)
        nulls_last (bool) : Whether NULL values should appear last (default: True)
    returns:
        records (list) : List of RealDictCursor dictionaries fetched with the
            fetchall() method.
    """

    if limit < 1:
        raise ValueError(f"Limit must be at least 1, got {limit}")
    if offset < 0:
        raise ValueError(f"Offset cannot be negative, got {offset}")

    direction = sql.SQL("DESC") if sort_desc else sql.SQL("ASC")
    nulls_order = sql.SQL("NULLS LAST") if nulls_last else sql.SQL("NULLS FIRST")
    schema_obj = sql.Identifier(schema_name)
    table_obj = sql.Identifier(table_name)
    col_obj = sql.Identifier(sort_col)

    query = sql.SQL(
        """ 
        SELECT * FROM {schema}.{table}
        ORDER BY {col} {direction} {nulls_order}
        LIMIT %s OFFSET %s                
    """
    ).format(
        schema=schema_obj,
        table=table_obj,
        col=col_obj,
        direction=direction,
        nulls_order=nulls_order,
    )
    try:
        cursor.execute(query, (limit, offset))
        records = cursor.fetchall()
        return records
    except Exception as e:
        # eventually ill add an in-module logger
        raise e


@init_psql_con_cursor
def update_existing_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    update_columns: list,
    update_values: list,
    where_column: str,
    where_value: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
):
    """
    Updates an existing record in a specified database table.
    Args:

    """
    if len(update_columns) != len(update_values):
        raise ValueError("Update columns and values must have the same length.")

    set_clause = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(col)) for col in update_columns
    )

    query = sql.SQL(
        """
        UPDATE {schema}.{table}
        SET {set_clause}
        WHERE {where_column} = %s
    """
    ).format(
        schema=sql.Identifier(schema),
        table=sql.Identifier(table),
        set_clause=set_clause,
        where_column=sql.Identifier(where_column),
    )

    try:
        cursor.execute(query, update_values + [where_value])
        connection.commit()
    except Exception:
        connection.rollback()
        raise


@init_psql_con_cursor
def add_join_records(
    cursor,
    connection,
    database: str,
    log,
    join_table: str,
    columns: list,
    values: list,
    join_schema: str = "Join",
):
    """
    Adds a record to the join table.
    Args:
        join_table (str) : The name of the join table.
        columns (list) : List of column names to insert.
        values (list(tuple)) :  List of values corresponding to the columns.
    """
    log.debug(f"Adding record to join table {join_table}")

    if not columns or not values:
        log.error("Record must be provided for adding to join table.")
        return

    query = sql.SQL(
        """
        INSERT INTO {schema}.{table} ({columns}) 
        VALUES %s
        ON CONFLICT DO NOTHING
        """
    ).format(
        schema=sql.Identifier(join_schema),
        table=sql.Identifier(join_table),
        columns=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
    )

    try:
        execute_values(cursor, query, values)
        connection.commit()
        log.debug(f"Record added to join table {join_table}")
    except psycopg2.errors.ForeignKeyViolation as e:
        log.warning(
            f"Foreign key violation when adding records to join table {join_table}: {e}"
        )
        connection.rollback()
        raise e
    except psycopg2.Error as e:
        log.error(f"Error adding record to join table {join_table}: {e}")
        log.error(query.as_string(cursor))
        connection.rollback()
        raise e
    except Exception as e:
        log.error(f"Unexpected error adding record to join table {join_table}: {e}")
        log.error(query.as_string(cursor))
        connection.rollback()
        raise e


@init_psql_con_cursor
def add_update_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    columns: list,
    values: list,
    conflict_target: list = ["primary_key_id"],
    on_conflict: str = "DO UPDATE SET",
) -> bool:
    """
    Adds or updates a single record in a specified database table.
    Args:
        - database (str): The name of the database.
        - schema (str): The schema where the target table resides.
        - table (str): The name of the target table.
        - columns (list): A list of column names to be inserted or updated.
        - values (list): A list of values corresponding to the columns.
        - conflict_target (list): A list of columns to check for conflicts.
        - on_conflict (str): The conflict resolution strategy.
            - "DO UPDATE SET": Update existing record on conflict.
            - "DO NOTHING": Do nothing on conflict.
    """
    # Validate inputs
    if isinstance(conflict_target, str):
        conflict_target = [conflict_target]

    if len(columns) != len(values):
        raise ValueError("Columns and values must have the same length.")

    schema_str = sql.Identifier(schema)
    table_str = sql.Identifier(table)
    columns_str = sql.SQL(", ").join(map(sql.Identifier, columns))
    placeholders_str = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    conflict_target_str = sql.SQL(", ").join(map(sql.Identifier, conflict_target))

    if on_conflict == "DO UPDATE SET":
        updates = sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
            for col in columns
        )

        query = sql.SQL(
            """
            INSERT INTO {schema}.{table} ({columns})
            VALUES ({placeholders})
            ON CONFLICT ({conflict}) {on_conflict}
            {updates}
        """
        ).format(
            schema=schema_str,
            table=table_str,
            columns=columns_str,
            placeholders=placeholders_str,
            conflict=conflict_target_str,
            on_conflict=sql.SQL(on_conflict),
            updates=updates,
        )
    elif on_conflict == "DO NOTHING":
        query = sql.SQL(
            """
            INSERT INTO {schema}.{table} ({columns})
            VALUES ({placeholders})
            ON CONFLICT ({conflict}) DO NOTHING
        """
        ).format(
            schema=schema_str,
            table=table_str,
            columns=columns_str,
            placeholders=placeholders_str,
            conflict=conflict_target_str,
        )
    elif not on_conflict:
        query = sql.SQL(
            """
            INSERT INTO {schema}.{table} ({columns})
            VALUES ({placeholders})
        """
        ).format(
            schema=schema_str,
            table=table_str,
            columns=columns_str,
            placeholders=placeholders_str,
        )

    try:
        cursor.execute(query, values)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def update_record(*args, **kwargs):
    return add_update_record(*args, **kwargs)


@init_psql_con_cursor
def delete_record(
    cursor,
    connection,
    database: str,
    log,
    schema_name,
    table_name,
    columns: list[str],
    values: list,
):
    if len(columns) != len(values):
        raise ValueError("Columns and values must have the same length.")

    schema_str = sql.Identifier(schema_name)
    table_str = sql.Identifier(table_name)
    conditions = [
        sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
        for col in columns
    ]
    conditions_str = sql.SQL(" AND ").join(conditions)

    query = sql.SQL("DELETE FROM {schema}.{table} WHERE {conditions}").format(
        schema=schema_str,
        table=table_str,
        conditions=conditions_str,
    )

    try:
        log.debug(f"Executing delete query: {query.as_string(connection)}")
        cursor.execute(query, values)
        rows_affected = cursor.rowcount
        connection.commit()
        log.info(f"Delete operation successful for {rows_affected} rows.")
        return
    except psycopg2.Error as e:
        log.error(f"Error executing delete query: {e}")
        connection.rollback()
        raise e
    except Exception as e:
        log.error(f"Unexpected error during delete operation: {e}")
        connection.rollback()
        raise e


################################################
# ==========# Schema/Table Functions #==========#
################################################


@init_psql_con_cursor
def get_tables(
    cursor,
    connection,
    database: str,
    schema: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> list:
    """
    Get a list of all tables in a given database schema.
    Args:
        database (str) : Name of the database
        schema (str) : Name of the schema
    Returns:
        (str) A list of tables
    """
    query = f"""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = %s
    AND table_type = 'BASE TABLE'
    """
    try:
        cursor.execute(query, (schema,))
    except Exception as e:
        return []
    return [row["table_name"] for row in cursor.fetchall()]


@init_psql_con_cursor
def ensure_table_exists(
    cursor,
    connection,
    database: str,
    log: object,
    schema_name: str,
    table_name: str,
    columns: list[dict],
):
    """
    Ensure that the specified table exists in the database. If the table does not exist, it will be created.
    If the table exists, it will ensure that all specified columns exist, adding any that are missing.
    Args:
        database (str) : Name of the database
        log (object) : Logger object for logging messages
        schema (str) : Name of the schema
        table (str) : Name of the table
        columns (list[dict]) : List of column definitions
            Each column definition should be a dictionary with the following keys:
            - name (str) : Column name
            - type (str) : Column data type (default: "TEXT")
            - default (str) : Default value for the column (default: "NULL")
            - not_null (bool) : Whether the column should be NOT NULL (default: False)
    Returns:
        Bool : True if the table exists or was created successfully, False otherwise.
    """
    log.debug(f"Ensuring table {table_name} exists in schema {schema_name}")

    schema_name_obj = sql.Identifier(schema_name)
    table_name_obj = sql.Identifier(table_name)

    # Create table if not exists
    column_defs = []
    for col in columns:
        col_name = col.get("name")
        col_name_obj = sql.Identifier(col_name)
        col_type = col.get("type", "TEXT")
        col_type_obj = sql.SQL(col_type)
        column_defs.append(sql.SQL("{} {}").format(col_name_obj, col_type_obj))

    query = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} ({column_defs})
        """
    ).format(
        schema_name=schema_name_obj,
        table_name=table_name_obj,
        column_defs=sql.SQL(", ").join(column_defs),
    )

    try:
        cursor.execute(query)
        connection.commit()
    except Exception as e:
        log.error(f"Error creating table {table_name} in schema {schema_name}: {e}")
        connection.rollback()
        return False

    # Ensure all columns exist
    for col in columns:
        col_name = col.get("name")
        col_type = col.get("type", "TEXT")
        default_value = col.get("default", "NULL")
        not_null = col.get("not_null", False)
        add_column_to_table(
            cursor=cursor,
            connection=connection,
            database=database,
            log=log,
            schema_name=schema_name,
            table_name=table_name,
            column_name=col_name,
            column_type=col_type,
            default_value=default_value,
            not_null=not_null,
        )

    log.debug(f"Table {table_name} ensured in schema {schema_name}")
    return True


def find_table_name(key: str, tables: list) -> str | None:
    """
    Attempts to find a table that closely matches a given key out of a list of tables.
    Args:
        key (str) : The string to search by.
        tables(list) : The list of table names to be searched.
    Returns:
        table(str) : The matching table name, None if no match.
    """

    def normalize(name):
        return name.lower().replace(" ", "").replace("_", "")

    # 1. Exact match
    if key in tables:
        return key

    # 2. Normalized match
    normalized_key = normalize(key)
    for table in tables:
        if normalized_key == normalize(table):
            return table

    # 3. Substring match
    for table in tables:
        if normalize(table) in normalized_key or normalized_key in normalize(table):
            return table

    # 4. Token set match
    key_tokens = set(key.lower().split())
    for table in tables:
        table_tokens = set(table.lower().split())
        if key_tokens & table_tokens:
            return table

    # 5. Fuzzy match (RapidFuzz)
    from rapidfuzz import process

    result = process.extractOne(key, tables)
    if result and result[1] > 70:  # adjust threshold as needed
        return result[0]

    return None


@init_psql_con_cursor
def add_column_to_table(
    cursor,
    connection,
    database: str,
    log,
    schema_name: str,
    table_name: str,
    column_name: str,
    column_type: str,
    default_value: str = None,
    not_null: bool = False,
):
    """
    Adds a new column to an existing table. If the column already exists, no action is taken.
    Args:
        database (str) : Name of the database
        log (object) : Logger object for logging messages
        schema_name (str) : Name of the schema
        table_name (str) : Name of the table
        column_name (str) : Name of the new column to add
        column_type (str) : Data type of the new column (e.g., "TEXT", "INTEGER")
        default_value (str) : Default value for the new column (default: "NULL")
        not_null (bool) : Whether the new column should be NOT NULL (default: False)
    Returns:
        Bool : True if the column was added successfully or already exists, False otherwise.
    """
    schema_name_obj = sql.Identifier(schema_name)
    table_name_obj = sql.Identifier(table_name)

    col_name_obj = sql.Identifier(column_name)
    col_type_obj = sql.SQL(column_type)
    col_default_obj = sql.SQL(default_value if default_value is not None else "NULL")
    col_not_null = not_null

    alter_query = sql.SQL(
        """
        ALTER TABLE {schema_name}.{table_name}
        ADD COLUMN IF NOT EXISTS {col_name} {col_type} DEFAULT {col_default}
        {not_null}
    """
    ).format(
        schema_name=schema_name_obj,
        table_name=table_name_obj,
        col_name=col_name_obj,
        col_type=col_type_obj,
        col_default=col_default_obj,
        not_null=sql.SQL("NOT NULL") if col_not_null else sql.SQL(""),
    )
    try:
        cursor.execute(alter_query)
        connection.commit()
        return True
    except Exception as e:
        log.error(
            f"Error adding column {column_name} to table {schema_name}.{table_name}: {e}"
        )
        connection.rollback()
        return False


@init_psql_con_cursor
def get_column_data_type(
    cursor, connection, database: str, schema: str, table: str, column: str
) -> str | None:
    """
    Get the data type of a specific column in a table.
    Args:
        cursor (object): Database cursor object.
        connection (object): Database connection object.
        database (str): Name of the database.
        schema (str): Name of the schema.
        table (str): Name of the table.
        column (str): Name of the column.
    Returns:
        (str | None): The data type of the column, or None if not found.
    """
    query = f"""
    SELECT data_type FROM information_schema.columns
    WHERE table_schema = %s
    AND table_name = %s
    AND column_name = %s
    """
    try:
        cursor.execute(query, (schema, table, column))
        result = cursor.fetchone()
        return result["data_type"] if result else None
    except Exception as e:
        return None


@init_psql_con_cursor
def get_column_comments(
    cursor,
    connection,
    database,
    schema_name,
    table_name,
) -> dict:
    """
    Get column comments for a given table.
    Args:
        database (str): The name of the database.
        schema_name (str): The name of the schema.
        table_name (str): The name of the table.
    Returns:
        dict: Dictionary with column names as keys and comments as values.
    """

    query = """
    SELECT 
        column_name,
        col_description(pgc.oid, ordinal_position) as comment
    FROM information_schema.columns c
    JOIN pg_class pgc ON pgc.relname = c.table_name
    JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
    WHERE table_schema = %s
    AND table_name = %s
    ORDER BY ordinal_position;
    """

    try:
        cursor.execute(query, (schema_name, table_name))
        results = cursor.fetchall()

        comments = {}
        for row in results:
            comments[row["column_name"]] = row["comment"] or ""

        return comments
    except Exception as e:
        print(f"Error in get_column_comments: {e}")
        print(f"Schema: {schema_name}, Table: {table_name}")
        return {}


@init_psql_con_cursor
def get_primary_key_info(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> dict | None:
    """Return primary key constraint name and ordered columns for a table.

    Args:
        database (str): Database name.
        schema (str): Schema name.
        table (str): Table name.
    Returns:
        dict | None: { 'constraint_name': str, 'columns': [str, ...] } or None if no PK.
    """
    query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
         AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = %s
          AND tc.table_name = %s
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position;
    """
    cursor.execute(query, (schema, table))
    rows = cursor.fetchall()
    if not rows:
        return None
    constraint_name = rows[0]["constraint_name"]
    columns = [r["column_name"] for r in rows]
    return {"constraint_name": constraint_name, "columns": columns}


@init_psql_con_cursor
def add_pk_constraint(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    pk_column: str,
    constraint_name: str = None,
):
    """
    Adds a primary key constraint to an existing table column.
    Args:
        database (str) : Name of the database
        schema_name (str) : Name of the schema
        table_name (str) : Name of the table
        pk_column (str) : Name of the column to set as primary key
        constraint_name (str) : Optional name for the primary key constraint
    Returns:
        Bool : True if the constraint was added successfully, False otherwise.
    """
    schema_name_obj = sql.Identifier(schema_name)
    table_name_obj = sql.Identifier(table_name)
    pk_column_obj = sql.Identifier(pk_column)
    constraint_name_obj = (
        sql.Identifier(constraint_name)
        if constraint_name
        else sql.SQL(f"{table_name}_pkey")
    )

    # Set to check if the column already has a primary key constraint
    primary_key = get_primary_key_info(
        cursor=cursor,
        connection=connection,
        database=database,
        schema=schema_name,
        table=table_name,
    )
    if primary_key:
        return True

    alter_query = sql.SQL(
        """
        ALTER TABLE {schema_name}.{table_name}
        ADD CONSTRAINT {constraint_name} PRIMARY KEY ({pk_column})
    """
    ).format(
        schema_name=schema_name_obj,
        table_name=table_name_obj,
        constraint_name=constraint_name_obj,
        pk_column=pk_column_obj,
    )
    try:
        cursor.execute(alter_query)
        connection.commit()
        return True
    except Exception as e:
        print(
            Fore.RED
            + f"Error adding primary key constraint to {schema_name}.{table_name}: {e}"
            + Fore.RESET
        )
        connection.rollback()
        return False


###########################################
# ==========# Utility Functions #==========#
###########################################


def guess_column_type(value) -> str:
    """
    Attempts to guess the SQL column type based on a sample value.
    Args:
        value (any) : The sample value to analyze.
    Returns:
        column_type (str) : The guessed SQL column type.
    """
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, dict):
        return "JSONB"
    if isinstance(value, str):
        return "TEXT"
    if isinstance(value, list):
        if value:
            return f"{guess_column_type(value[0])}[]"
        return "TEXT[]"  # empty list fallback
    return "TEXT"
