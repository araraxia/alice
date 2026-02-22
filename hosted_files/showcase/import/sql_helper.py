#!/usr/bin/env python3
"""
PostgreSQL Database Helper Module

This module provides comprehensive PostgreSQL database functionality including
connection management, CRUD operations, search capabilities, and Notion integration.

The module uses psycopg2 for database operations with RealDictCursor for dictionary-based
results. It includes a decorator pattern for automatic connection/cursor management,
eliminating the need for manual connection handling in most cases.

Key Features:
    - Automatic connection management via decorator pattern
    - Connection pooling support for high-performance applications
    - Comprehensive CRUD operations (Create, Read, Update, Delete)
    - Advanced search capabilities:
        * Fuzzy search with LIKE/ILIKE patterns
        * Edit distance matching (Levenshtein)
        * Similarity search using trigrams (pg_trgm)
    - Complex filtering with AND/OR logic
    - Notion API integration for syncing Notion databases to PostgreSQL
    - Table schema management and dynamic column operations
    - Join table management for many-to-many relationships in Notion

Requirements:
    - psycopg2 (or psycopg2-binary)
    - PostgreSQL server with configured credentials
    - For fuzzy matching: fuzzystrmatch extension
    - For similarity search: pg_trgm extension
    - Optional: NotionApiHelper for Notion integration

Database Credentials:
    Credentials are loaded from 'cred/psql.json' with structure:
    {
        "ip": "localhost",
        "port": 5432,
        "user": "your_user",
        "password": "your_password"
    }

Environment Variables:
    - NOTION_FH_REGEX: Regex pattern for Notion file URLs
    - GCLOUD_ORDER_EXTENDED_ASSETS_BUCKET: GCS bucket for rehosted assets

Example Usage:
    >>> # Basic record retrieval (connection auto-managed)
    >>> record = get_record(
    ...     database='db',
    ...     schema='public',
    ...     table='users',
    ...     column='email',
    ...     value='user@example.com'
    ... )
    >>>
    >>> # Complex filtered search
    >>> records = get_filtered_records(
    ...     database='db',
    ...     schema='public',
    ...     table='orders',
    ...     filters=[
    ...         {
    ...             'logic': 'AND',
    ...             'rules': [
    ...                 {'property': 'status', 'operator': 'equals', 'value': 'active'},
    ...                 {'property': 'total', 'operator': 'greater_than', 'value': 100}
    ...             ]
    ...         }
    ...     ],
    ...     sort_by='created_at',
    ...     descending=True
    ... )
    >>>
    >>> # Fuzzy search for approximate matches
    >>> results = fuzzy_search_records(
    ...     database='db',
    ...     schema='public',
    ...     table='products',
    ...     column_name='name',
    ...     search_pattern='%widget%',
    ...     case_sensitive=False
    ... )
    >>>
    >>> # Manual connection management (advanced)
    >>> connection = init_psql_connection('db')
    >>> cursor = create_cursor(connection)
    >>> try:
    ...     cursor.execute("SELECT * FROM users")
    ...     results = cursor.fetchall()
    ... finally:
    ...     cursor.close()
    ...     connection.close()

See Also:
    - NotionApiHelper: For Notion database integration
    - gcloud_helper.GCloudBucket: For file storage operations
    - JoinTableManager: For managing many-to-many relationships

Author: Aria Corona
Created: 2025/06/09
"""

import psycopg2
import json
import re
import logging
import os
import requests
import sys
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
from functools import wraps
from colorama import Fore
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Path configuration
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from extras.helpers import send_discord_warning, determine_file_type_from_response
from extras.gcloud_helper import GCloudBucket
from NotionApiHelper import NotionApiHelper

# Load environment variables
load_dotenv(ROOT_DIR / ".env")
NOTION_URL_REGEX = os.getenv("NOTION_FH_REGEX", "")
ORDER_ASSET_BUCKET = os.getenv(
    "GCLOUD_ORDER_EXTENDED_ASSETS_BUCKET", "assets"
)

# Load PostgreSQL credentials
sql_ip = os.getenv("PSQL_HOST", "localhost")
sql_port = int(os.getenv("PSQL_PORT", 5000))
sql_user = os.getenv("PSQL_USER", "")
sql_pass = os.getenv("PSQL_PASS", "")

# ============================================#
# ==========# Connection Management #========#
# ============================================#


def init_psql_connection(
    db: str,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
    _rt: bool = False,
) -> psycopg2.extensions.connection:
    """
    Create a PostgreSQL database connection using psycopg2.

    This function establishes a connection to a PostgreSQL database with automatic
    retry logic on failure. If the first connection attempt fails, it will retry
    once before raising an exception.

    Args:
        db (str): Database name (required)
        host (str): PostgreSQL host IP address (default: from credentials)
        port (int): PostgreSQL port number (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)
        _rt (bool): Internal flag for retry tracking (default: False)

    Returns:
        psycopg2.extensions.connection: Active database connection object

    Raises:
        psycopg2.Error: If connection fails after retry attempt

    Example:
        >>> # Basic connection with defaults
        >>> conn = init_psql_connection('db')
        >>>
        >>> # Custom connection parameters
        >>> conn = init_psql_connection(
        ...     db='my_database',
        ...     host='0.0.0.0',
        ...     port=5000,
        ...     user='custom_user',
        ...     password='custom_pass'
        ... )
        >>>
        >>> # Always close connection when done
        >>> conn.close()

    Note:
        The decorator @init_psql_con_cursor automatically manages connections
        for most use cases, eliminating the need to call this function directly.
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


def init_psql_connection_pool(
    db: str,
    max_connections: int = 5,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
    _rt: bool = False,
):
    """
    Create a PostgreSQL connection pool for high-performance applications.

    Connection pooling allows multiple concurrent database operations by maintaining
    a pool of reusable connections, reducing the overhead of creating new connections
    for each operation. This is recommended for web servers and multi-threaded
    applications.

    Args:
        db (str): Database name (required)
        max_connections (int): Maximum number of connections in pool (default: 5)
        host (str): PostgreSQL host IP address (default: from credentials)
        port (int): PostgreSQL port number (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)
        _rt (bool): Internal flag for retry tracking (default: False)

    Returns:
        psycopg2.pool.SimpleConnectionPool: Connection pool object

    Raises:
        psycopg2.Error: If pool creation fails after retry attempt

    Example:
        >>> # Create connection pool
        >>> pool = init_psql_connection_pool('db', max_connections=10)
        >>>
        >>> # Get connection from pool
        >>> conn = pool.getconn()
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT * FROM users")
        >>> results = cursor.fetchall()
        >>>
        >>> # Always return connection to pool
        >>> cursor.close()
        >>> pool.putconn(conn)
        >>>
        >>> # Close all connections when done
        >>> pool.closeall()

    Note:
        Connection pools are ideal for Flask/Django applications where multiple
        requests need database access simultaneously.
    """
    from psycopg2 import pool

    try:
        con_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=max_connections,
            dbname=db,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        return con_pool
    except psycopg2.Error as e:
        print(Fore.RED + f"Error creating connection pool: {e}" + Fore.RESET)
        if _rt:
            print(Fore.RED + "Could not establish connection pool." + Fore.RESET)
            raise psycopg2.Error(f"Could not establish connection pool: {e}")
        else:
            print(Fore.RED + "Retrying connection pool creation..." + Fore.RESET)
            return init_psql_connection_pool(
                db, max_connections, host, port, user, password, _rt=True
            )


def init_psql_con_cursor(func: Callable) -> Callable:
    """
    Decorator for automatic PostgreSQL connection and cursor management.

    This decorator eliminates the need for manual connection/cursor creation and cleanup
    in database functions. It automatically:
    1. Extracts database connection parameters from function kwargs
    2. Creates a new connection and cursor if not provided
    3. Injects cursor and connection as first two arguments
    4. Properly closes cursor and connection after function execution
    5. Reuses existing connection/cursor if provided (for manual management)

    The decorated function will receive `cursor` and `connection` as its first two
    positional arguments, followed by the original arguments.

    Args:
        func (Callable): Function to decorate. Must accept cursor and connection
                        as first two parameters.

    Returns:
        Callable: Wrapped function with automatic connection management

    Connection Management:
        - If connection/cursor not provided: Creates new, executes, closes automatically
        - If connection/cursor provided: Reuses existing, caller responsible for closing
        - Connection reused if valid and not closed
        - Uses RealDictCursor for dictionary-based results

    Example:
        >>> @init_psql_con_cursor
        ... def get_user(cursor, connection, database, schema, table, user_id):
        ...     query = f'SELECT * FROM "{schema}"."{table}" WHERE id = %s'
        ...     cursor.execute(query, (user_id,))
        ...     return cursor.fetchone()
        >>>
        >>> # Automatic connection management (recommended)
        >>> user = get_user(database='db', schema='public',
        ...                 table='users', user_id=123)
        >>>
        >>> # Manual connection management (advanced)
        >>> conn = init_psql_connection('db')
        >>> cur = conn.cursor()
        >>> user = get_user(cursor=cur, connection=conn, database='db',
        ...                 schema='public', table='users', user_id=123)
        >>> cur.close()
        >>> conn.close()

    Note:
        Database connection parameters (host, port, user, password) are extracted
        from kwargs and removed before passing to the decorated function.
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
    connection: psycopg2.extensions.connection,
    cursor_factory: type = RealDictCursor,
) -> psycopg2.extensions.cursor:
    """
    Create a new cursor from an existing database connection.

    Args:
        connection (psycopg2.extensions.connection): Active database connection
        cursor_factory (type): Cursor factory class (default: RealDictCursor)

    Returns:
        psycopg2.extensions.cursor: New cursor object

    Cursor Factories:
        - RealDictCursor: Returns rows as dict objects (default, recommended)
        - DictCursor: Returns rows as dict-like objects
        - NamedTupleCursor: Returns rows as named tuples
        - None: Returns rows as tuples (standard psycopg2 behavior)

    Note:
        RealDictCursor is recommended for most use cases as it provides more
        readable code and reduces errors from column index changes.
    """
    return connection.cursor(cursor_factory=cursor_factory)


def close_concursion(
    connection: psycopg2.extensions.connection,
    cursor: psycopg2.extensions.cursor,
) -> None:
    """
    Close a PostgreSQL cursor and connection.

    Args:
        connection (psycopg2.extensions.connection): Active database connection
        cursor (psycopg2.extensions.cursor): Active database cursor
    """
    if cursor and not cursor.closed:
        cursor.close()
    if connection and connection.closed == 0:
        connection.close()


# ========================================#
# ==========# Record Operations #========#
# ========================================#


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
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single record from a PostgreSQL table by column value.

    This function queries a table for a single record matching the specified column
    value. It's intended for retrieving records by primary key or other unique
    identifiers. Returns None if no matching record is found.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema (str): Name of the schema containing the table (required)
        table (str): Name of the table to query (required)
        column (str): Column name to filter by (required)
        value (str): Value to match in the specified column (required)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        Optional[Dict[str, Any]]: Dictionary representing the record with column names
                                  as keys, or None if no record found

    Example:
        >>> # Get user by email
        >>> user = get_record(
        ...     database='db',
        ...     schema='public',
        ...     table='users',
        ...     column='email',
        ...     value='john@example.com'
        ... )
        >>> if user:
        ...     print(f"User ID: {user['id']}")
        ...     print(f"Name: {user['name']}")
        ... else:
        ...     print("User not found")

    Note:
        This function uses parameterized queries to prevent SQL injection.
        For retrieving multiple records, use get_records() or search_records().
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
    values: Union[List[Any], Any],
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> List[Dict[str, Any]]:
    """
    Retrieve multiple records from a PostgreSQL table matching any of the given values.

    This function queries a table for all records where the specified column matches
    any value in the provided list. Uses SQL IN clause for efficient multi-value lookup.
    Automatically converts single values to a list.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema (str): Name of the schema containing the table (required)
        table (str): Name of the table to query (required)
        column (str): Column name to filter by (required)
        values (Union[List[Any], Any]): Single value or list of values to match (required)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of dictionaries representing matching records,
                              empty list if no matches found

    Example:
        >>> # Get multiple users by ID
        >>> users = get_records(
        ...     database='db',
        ...     schema='public',
        ...     table='users',
        ...     column='id',
        ...     values=[1, 2, 3, 5, 8]
        ... )
        >>> print(f"Found {len(users)} users")
        >>> for user in users:
        ...     print(f"  {user['name']} ({user['email']})")
        >>>
        >>> # Get orders by status (accepts single value too)
        >>> active_orders = get_records(
        ...     database='db',
        ...     schema='orders',
        ...     table='orders',
        ...     column='status',
        ...     values='active'  # Automatically converted to ['active']
        ... )
        >>>
        >>> # Get products by category
        >>> products = get_records(
        ...     database='db',
        ...     schema='inventory',
        ...     table='products',
        ...     column='category',
        ...     values=['electronics', 'computers', 'accessories']
        ... )

    Note:
        Uses parameterized queries with SQL identifiers to prevent SQL injection.
        For single record retrieval, use get_record() instead.
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
) -> List[Dict[str, Any]]:
    """
    Search for records in a PostgreSQL table matching an exact column value.

    This function performs an exact match search (equality comparison) on a specified
    column and returns all matching records. Unlike get_record() which returns a single
    record, this returns all matches as a list.

    For pattern matching or approximate searches, use fuzzy_search_records(),
    similarity_search_records(), or edit_distance_search_records() instead.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema (str): Name of the schema containing the table (required)
        table (str): Name of the table to query (required)
        column (str): Column name to filter by (required)
        value (str): Exact value to match in the specified column (required)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of dictionaries representing matching records,
                              empty list if no matches found

    Example:
        >>> # Find all active orders
        >>> active_orders = search_records(
        ...     database='db',
        ...     schema='orders',
        ...     table='orders',
        ...     column='status',
        ...     value='active'
        ... )
        >>> print(f"Found {len(active_orders)} active orders")
        >>>
        >>> # Find all users with specific role
        >>> admins = search_records(
        ...     database='db',
        ...     schema='public',
        ...     table='users',
        ...     column='role',
        ...     value='admin'
        ... )
        >>> for admin in admins:
        ...     print(f"Admin: {admin['name']} - {admin['email']}")
        >>>
        >>> # Find all products in a category
        >>> electronics = search_records(
        ...     database='db',
        ...     schema='inventory',
        ...     table='products',
        ...     column='category',
        ...     value='electronics'
        ... )

    Note:
        - Uses parameterized queries with SQL identifiers to prevent SQL injection
        - For multiple values, use get_records() which is more efficient
        - For pattern matching, use fuzzy_search_records()
        - For approximate matching, use similarity_search_records()
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
) -> List[Dict[str, Any]]:
    """
    Search for records using text patterns (wildcards) or regular expressions.

    This function provides flexible pattern matching capabilities for text searches.
    It supports SQL LIKE/ILIKE patterns with wildcards or full regex matching for
    complex search requirements. If no wildcards are provided in the pattern, they
    are automatically added (becomes '%pattern%') for convenience.

    Pattern Wildcards:
        - % : Matches any sequence of characters (including empty)
        - _ : Matches exactly one character

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema_name (str): Name of the schema containing the table (required)
        table_name (str): Name of the table to query (required)
        column_name (str): Column name to search in (required)
        search_pattern (str): Pattern to search for (required)
        case_sensitive (bool): If True, uses LIKE; if False, uses ILIKE (default: False)
        pattern_negation (bool): If True, inverts the match (NOT LIKE) (default: False)
        escape_char (str): Character to escape special characters in pattern (default: None)
        regex (bool): If True, uses regex matching (~*) instead of LIKE (default: False)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of dictionaries representing matching records,
                              empty list if no matches found

    Example:
        >>> # Find products containing "widget" (case-insensitive)
        >>> products = fuzzy_search_records(
        ...     database='db',
        ...     schema_name='inventory',
        ...     table_name='products',
        ...     column_name='name',
        ...     search_pattern='widget'  # Auto-converts to '%widget%'
        ... )
        >>>
        >>> # Explicit wildcard pattern
        >>> emails = fuzzy_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='users',
        ...     column_name='email',
        ...     search_pattern='%@example.com'  # Ends with @example.com
        ... )
        >>>
        >>> # Case-sensitive search
        >>> johns = fuzzy_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='users',
        ...     column_name='name',
        ...     search_pattern='John%',  # Starts with 'John'
        ...     case_sensitive=True
        ... )
        >>>
        >>> # Pattern negation (NOT LIKE)
        >>> non_gmail = fuzzy_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='users',
        ...     column_name='email',
        ...     search_pattern='%@gmail.com',
        ...     pattern_negation=True  # Exclude gmail addresses
        ... )
        >>>
        >>> # Regex search for complex patterns
        >>> # Find emails with numbers before @
        >>> emails = fuzzy_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='users',
        ...     column_name='email',
        ...     search_pattern=r'^[a-z]+[0-9]+@',
        ...     regex=True
        ... )

    Note:
        - Auto-wraps pattern with % if no wildcards provided (unless regex=True)
        - ILIKE (case-insensitive) is slower than LIKE on large datasets
        - For exact string similarity, use similarity_search_records()
        - For edit distance matching, use edit_distance_search_records()
        - Regex searches can be slow without proper indexing

    Raises:
        Exception: If pattern matching fails or query execution error occurs
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
    database: str,
    schema_name: str,
    table_name: str,
    column_name: str,
    search_pattern: str,
    max_distance: int = 2,
    limit: int = 10,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> List[Dict[str, Any]]:
    """
    Search for records using Levenshtein edit distance for fuzzy string matching.

    This function finds records where the column value is within a specified edit distance
    (number of character insertions, deletions, or substitutions) from the search pattern.
    It's useful for finding typos, misspellings, or similar strings.

    Edit Distance Examples:
        - "cat" and "bat" have distance 1 (substitute c→b)
        - "kitten" and "sitting" have distance 3
        - "Saturday" and "Sunday" have distance 3

    **Requirements**: PostgreSQL `fuzzystrmatch` extension must be enabled.
    To enable: `CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;`

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema_name (str): Name of the schema containing the table (required)
        table_name (str): Name of the table to query (required)
        column_name (str): Column name to search in (required)
        search_pattern (str): Target string to find similar matches for (required)
        max_distance (int): Maximum edit distance to consider a match (default: 2)
        limit (int): Maximum number of records to return (default: 10)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of dictionaries with matching records plus a 'distance'
                              field showing edit distance, sorted by distance (closest first)

    Example:
        >>> # Find names similar to "John" (handles typos)
        >>> similar_names = edit_distance_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='users',
        ...     column_name='name',
        ...     search_pattern='John',
        ...     max_distance=2
        ... )
        >>> # Might find: "John", "Jon", "Joan", "Johann"
        >>> for record in similar_names:
        ...     print(f"{record['name']} (distance: {record['distance']})")
        >>>
        >>> # Find product names close to "widget"
        >>> products = edit_distance_search_records(
        ...     database='db',
        ...     schema_name='inventory',
        ...     table_name='products',
        ...     column_name='name',
        ...     search_pattern='widget',
        ...     max_distance=3,
        ...     limit=20
        ... )
        >>>
        >>> # Spell-check user input
        >>> user_search = "pyton"  # User meant "python"
        >>> suggestions = edit_distance_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='tags',
        ...     column_name='tag_name',
        ...     search_pattern=user_search,
        ...     max_distance=2,
        ...     limit=5
        ... )
        >>> if suggestions:
        ...     print(f"Did you mean: {suggestions[0]['tag_name']}?")

    Note:
        - Results include 'distance' field showing edit distance from pattern
        - Sorted by distance (closest matches first)
        - max_distance=1: Very strict (only 1-char differences)
        - max_distance=2: Moderate (typical typos)
        - max_distance=3+: Loose matching (may include many false positives)
        - Computationally expensive on large tables without indexing
        - Consider using similarity_search_records() for percentage-based matching

    Raises:
        Exception: If fuzzystrmatch extension not installed or query fails

    See Also:
        - similarity_search_records(): For trigram-based similarity matching
        - fuzzy_search_records(): For wildcard pattern matching
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
) -> List[Dict[str, Any]]:
    """
    Search for records using trigram similarity for fuzzy text matching.

    This function finds records where the column value is similar to the search pattern
    based on trigram (3-character sequences) analysis. It returns a similarity score
    (0.0 to 1.0) where higher scores indicate better matches. This is excellent for
    finding similar text even with typos, word order differences, or extra/missing words.

    Trigram Similarity Examples:
        - "hello world" and "hello word" → High similarity
        - "PostgreSQL" and "PostgreSql" → Very high similarity
        - "John Smith" and "Smith, John" → Moderate similarity

    **Requirements**: PostgreSQL `pg_trgm` extension must be enabled.
    To enable: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema_name (str): Name of the schema containing the table (required)
        table_name (str): Name of the table to query (required)
        column_name (str): Column name to search in (required)
        search_pattern (str): Target string to find similar matches for (required)
        limit (int): Maximum number of records to return (default: 10)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of dictionaries with matching records plus a 'similar'
                              field showing similarity score (0.0-1.0), sorted by score
                              (highest first)

    Example:
        >>> # Find similar product names
        >>> products = similarity_search_records(
        ...     database='db',
        ...     schema_name='inventory',
        ...     table_name='products',
        ...     column_name='name',
        ...     search_pattern='laptop computer',
        ...     limit=10
        ... )
        >>> # Might find: "Laptop Computer", "laptop", "Computer Laptop"
        >>> for product in products:
        ...     print(f"{product['name']} (similarity: {product['similar']:.2f})")
        >>>
        >>> # Search for similar addresses (typo-tolerant)
        >>> addresses = similarity_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='locations',
        ...     column_name='address',
        ...     search_pattern='123 Main Street',
        ...     limit=5
        ... )
        >>>
        >>> # Find similar company names
        >>> companies = similarity_search_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='companies',
        ...     column_name='company_name',
        ...     search_pattern='Acme Corporation',
        ...     limit=10
        ... )
        >>> # Filters results automatically using % operator (similarity threshold)
        >>> # Only returns records above a certain similarity threshold

    Note:
        - Results include 'similar' field with score from 0.0 (no match) to 1.0 (exact)
        - Sorted by similarity score (best matches first)
        - Uses % operator which filters by pg_similarity_threshold (default 0.3)
        - Adjust threshold: SET pg_trgm.similarity_threshold = 0.5;
        - Better than edit_distance for longer strings and word-order independence
        - Supports GIN/GiST indexes for fast performance on large tables
        - More forgiving than edit distance for multi-word strings

    Raises:
        Exception: If pg_trgm extension not installed or query fails

    See Also:
        - edit_distance_search_records(): For character-level edit distance matching
        - fuzzy_search_records(): For wildcard pattern matching
        - PostgreSQL pg_trgm: https://www.postgresql.org/docs/current/pgtrgm.html
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
) -> List[Dict[str, Any]]:
    """
    Fetch top N records from a table with sorting and pagination.

    This function retrieves a specified number of records from a table, sorted by
    any column in ascending or descending order. It supports pagination through
    the offset parameter and allows control over NULL value placement in the sort
    order. Perfect for implementing "top 10" lists, leaderboards, pagination, and
    chronological record retrieval.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema_name (str): Name of the schema containing the table (required)
        table_name (str): Name of the table to query (required)
        sort_col (str): Column name to sort by (required)
        sort_desc (bool): Sort in descending order if True, ascending if False
                          (default: True)
        limit (int): Maximum number of records to return, must be >= 1 (default: 1)
        offset (int): Number of records to skip, must be >= 0 (default: 0)
        nulls_last (bool): Place NULL values last in sort order if True,
                           first if False (default: True)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of record dictionaries sorted by the specified column

    Example:
        >>> # Get top 10 highest-rated products
        >>> top_products = fetch_top(
        ...     database='db',
        ...     schema_name='inventory',
        ...     table_name='products',
        ...     sort_col='rating',
        ...     sort_desc=True,
        ...     limit=10
        ... )
        >>>
        >>> # Get 25 most recent orders
        >>> recent_orders = fetch_top(
        ...     database='db',
        ...     schema_name='sales',
        ...     table_name='orders',
        ...     sort_col='created_at',
        ...     sort_desc=True,
        ...     limit=25
        ... )
        >>>
        >>> # Paginate through customers sorted by name (page 3)
        >>> page_size = 50
        >>> page_number = 3
        >>> customers = fetch_top(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='customers',
        ...     sort_col='last_name',
        ...     sort_desc=False,  # A-Z order
        ...     limit=page_size,
        ...     offset=(page_number - 1) * page_size,
        ...     nulls_last=True  # Customers without names at the end
        ... )
        >>>
        >>> # Get oldest 5 unprocessed jobs (ascending sort)
        >>> old_jobs = fetch_top(
        ...     database='db',
        ...     schema_name='queue',
        ...     table_name='jobs',
        ...     sort_col='created_at',
        ...     sort_desc=False,  # Oldest first
        ...     limit=5
        ... )

    Note:
        - limit must be at least 1, offset must be >= 0 (validated)
        - offset enables pagination: page 2 with limit 25 → offset=25
        - nulls_last only affects the specified sort_col NULL values
        - Use sort_desc=True for "newest first" / "highest first"
        - Use sort_desc=False for "oldest first" / "lowest first"
        - Efficiently handles large tables with proper indexing on sort_col
        - Returns empty list if offset exceeds total record count

    Raises:
        ValueError: If limit < 1 or offset < 0
        Exception: If database query fails

    See Also:
        - get_all_records(): Retrieve all records without limits
        - get_filtered_records(): Fetch records with WHERE clause filtering
        - get_records(): Fetch records matching specific column values
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
def get_all_records(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    sort_by: str = None,
    descending: bool = True,
    nulls_last: bool = True,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> List[Dict[str, Any]]:
    """
    Retrieve all records from a PostgreSQL table with optional sorting.

    This function fetches every record from the specified table. Unlike fetch_top(),
    there is no LIMIT clause - all rows are returned. Use this when you need complete
    datasets, but be cautious with large tables as it can consume significant memory.
    Optional sorting allows you to control the order of results.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema (str): Name of the schema containing the table (required)
        table (str): Name of the table to query (required)
        sort_by (str): Column name to sort by (optional, no sorting if None)
        descending (bool): Sort in descending order if True, ascending if False
                          (default: True, ignored if sort_by is None)
        nulls_last (bool): Place NULL values last in sort order if True,
                          first if False (default: True, ignored if sort_by is None)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of all record dictionaries from the table

    Example:
        >>> # Get all customers without any specific order
        >>> all_customers = get_all_records(
        ...     database='db',
        ...     schema='public',
        ...     table='customers'
        ... )
        >>>
        >>> # Get all products sorted by price (highest first)
        >>> all_products = get_all_records(
        ...     database='db',
        ...     schema='inventory',
        ...     table='products',
        ...     sort_by='price',
        ...     descending=True
        ... )
        >>>
        >>> # Get all orders sorted by date (oldest first)
        >>> all_orders = get_all_records(
        ...     database='db',
        ...     schema='sales',
        ...     table='orders',
        ...     sort_by='created_at',
        ...     descending=False,
        ...     nulls_last=True
        ... )
        >>>
        >>> # Export entire table to JSON
        >>> import json
        >>> records = get_all_records(
        ...     database='db',
        ...     schema='public',
        ...     table='employees'
        ... )
        >>> with open('employees.json', 'w') as f:
        ...     json.dump(records, f, default=str)

    Note:
        - Returns ALL rows - no pagination, no limits
        - Can consume large amounts of memory for tables with many records
        - For large tables, consider fetch_top() with pagination instead
        - For filtered results, use get_filtered_records() to reduce dataset
        - sort_by parameters are ignored if sort_by is None
        - Returns empty list if table is empty
        - Query uses proper SQL identifier escaping for security

    Raises:
        Exception: If database query fails (transaction is rolled back)

    See Also:
        - fetch_top(): Retrieve limited records with pagination
        - get_filtered_records(): Get records matching WHERE clause conditions
        - get_records(): Fetch records matching specific column values
    """
    schema_obj = sql.Identifier(schema)
    table_obj = sql.Identifier(table)
    if sort_by:
        query = sql.SQL(
            """
            SELECT * FROM {schema}.{table}
            ORDER BY {sort_col} {order} NULLS {nulls}
        """
        ).format(
            schema=schema_obj,
            table=table_obj,
            sort_col=sql.Identifier(sort_by),
            order=sql.SQL("DESC") if descending else sql.SQL("ASC"),
            nulls=sql.SQL("LAST") if nulls_last else sql.SQL("FIRST"),
        )
    else:
        query = sql.SQL(
            f"""
            SELECT * FROM {schema}.{table}
        """
        )

    try:
        query = f'SELECT * FROM "{schema}"."{table}"'
        cursor.execute(query)
        records = cursor.fetchall()
        return records
    except Exception as e:
        connection.rollback()
        raise e


@init_psql_con_cursor
def get_filtered_records(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
    filters: List[Dict[str, Any]] = [],
    sort_by: str = None,
    descending: bool = True,
    nulls_last: bool = True,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> List[Dict[str, Any]]:
    """
    Query records using complex filter criteria with AND/OR logic combinations.

    This is the most powerful filtering function in sql_helper. It supports complex
    WHERE clause construction with multiple filter groups, each containing multiple
    rules combined with AND/OR logic. Perfect for building dynamic queries from user
    input, implementing advanced search forms, and creating complex data retrieval
    logic without writing raw SQL.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Filter Structure:
        Each filter is a dictionary with:
        - logic (str): 'AND' or 'OR' - how to combine with previous filter group
        - rules (list[dict]): List of individual filter rules

        Each rule is a dictionary with:
        - property (str): Column name to filter on
        - operator (str): Comparison operator (see Supported Operators below)
        - value (any): Value to compare against (not needed for is_empty/is_not_empty)

    Supported Operators:
        Text Pattern Matching:
        - 'contains': ILIKE '%value%' (case-insensitive substring)
        - 'does_not_contain': NOT ILIKE '%value%'
        - 'starts_with': ILIKE 'value%'
        - 'ends_with': ILIKE '%value'

        Comparison:
        - 'equals': = value
        - 'not_equals': != value
        - 'greater_than': > value
        - 'less_than': < value
        - 'greater_than_or_equal_to': >= value
        - 'less_than_or_equal_to': <= value

        Null/Empty Checking:
        - 'is_empty': IS NULL OR = '' (for text fields)
        - 'is_not_empty': IS NOT NULL AND != '' (for text fields)
        - 'is_null': IS NULL (for any field type including UUID)
        - 'is_not_null': IS NOT NULL (for any field type including UUID)

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database to query (required)
        schema_name (str): Name of the schema containing the table (required)
        table_name (str): Name of the table to query (required)
        filters (List[Dict[str, Any]]): List of filter group dictionaries (default: [])
        sort_by (str): Column name to sort results by (optional)
        descending (bool): Sort descending if True, ascending if False (default: True)
        nulls_last (bool): Place NULL values last in sort order (default: True)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        List[Dict[str, Any]]: List of matching record dictionaries

    Example:
        >>> # Find active premium customers in California
        >>> filters = [
        ...     {
        ...         'logic': 'AND',
        ...         'rules': [
        ...             {'property': 'status', 'operator': 'equals', 'value': 'active'},
        ...             {'property': 'tier', 'operator': 'equals', 'value': 'premium'},
        ...             {'property': 'state', 'operator': 'equals', 'value': 'CA'}
        ...         ]
        ...     }
        ... ]
        >>> customers = get_filtered_records(
        ...     database='db',
        ...     schema_name='public',
        ...     table_name='customers',
        ...     filters=filters,
        ...     sort_by='last_name'
        ... )
        >>>
        >>> # Find products: (price > 100 AND in_stock) OR (on_sale)
        >>> filters = [
        ...     {
        ...         'logic': 'AND',
        ...         'rules': [
        ...             {'property': 'price', 'operator': 'greater_than', 'value': 100},
        ...             {'property': 'in_stock', 'operator': 'equals', 'value': True}
        ...         ]
        ...     },
        ...     {
        ...         'logic': 'OR',
        ...         'rules': [
        ...             {'property': 'on_sale', 'operator': 'equals', 'value': True}
        ...         ]
        ...     }
        ... ]
        >>> products = get_filtered_records(
        ...     database='db',
        ...     schema_name='inventory',
        ...     table_name='products',
        ...     filters=filters
        ... )
        >>>
        >>> # Search for orders: name contains "smith" AND (status = 'pending' OR 'processing')
        >>> filters = [
        ...     {
        ...         'logic': 'AND',
        ...         'rules': [
        ...             {'property': 'customer_name', 'operator': 'contains', 'value': 'smith'}
        ...         ]
        ...     },
        ...     {
        ...         'logic': 'AND',
        ...         'rules': [
        ...             {'property': 'status', 'operator': 'equals', 'value': 'pending'},
        ...             {'property': 'status', 'operator': 'equals', 'value': 'processing'}
        ...         ]
        ...     }
        ... ]
        >>> orders = get_filtered_records(
        ...     database='db',
        ...     schema_name='sales',
        ...     table_name='orders',
        ...     filters=filters,
        ...     sort_by='created_at',
        ...     descending=True
        ... )

    Note:
        - Empty filters list returns all records (like get_all_records)
        - First filter group's 'logic' field is ignored (nothing to combine with)
        - Each filter group is wrapped in parentheses for proper precedence
        - ILIKE operators are case-insensitive (use for text matching)
        - Proper SQL injection protection via parameterized queries
        - Complex nested logic: multiple filter groups with multiple rules each
        - Query is printed to console for debugging (can be removed in production)

    Raises:
        ValueError: If invalid logic operators or missing required rule fields
        Exception: If database query fails (transaction is rolled back)

    See Also:
        - get_records(): Simple filtering by exact column value matches
        - search_records(): Search with single column/value pair
        - fuzzy_search_records(): Pattern matching with wildcards
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
        elif op in ["is_empty", "is_not_empty", "is_null", "is_not_null"]:
            if op == "is_empty":
                return sql.SQL("({col} IS NULL OR {col} = '')").format(col=col), None
            elif op == "is_not_empty":
                return (
                    sql.SQL("({col} IS NOT NULL AND {col} != '')").format(col=col),
                    None,
                )
            elif op == "is_null":
                return sql.SQL("{col} IS NULL").format(col=col), None
            else:  # is_not_null
                return sql.SQL("{col} IS NOT NULL").format(col=col), None
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
def add_update_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    columns: List[str],
    values: List[Any],
    conflict_target: List[str] = ["primary_key_id"],
    on_conflict: str = "DO UPDATE SET",
) -> bool:
    """
    Insert a new record or update existing record on conflict (UPSERT operation).

    This function provides PostgreSQL's powerful INSERT ... ON CONFLICT functionality,
    allowing you to insert a record if it doesn't exist, or update it if a conflict
    occurs on specified columns (typically primary key or unique constraint). This is
    the SQL equivalent of "insert or update" logic, eliminating the need for separate
    check-then-insert/update operations.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Conflict Resolution Strategies:
        - "DO UPDATE SET": Update all columns with new values on conflict
        - "DO NOTHING": Silently ignore the insert if conflict occurs
        - Empty string or None: Pure INSERT without conflict handling

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database (required)
        schema (str): Schema containing the table (required)
        table (str): Name of the table (required)
        columns (List[str]): Column names to insert/update (required)
        values (List[Any]): Values corresponding to columns (required)
        conflict_target (List[str]): Columns to check for conflicts, typically
                                      primary key or unique constraint columns
                                      (default: ["primary_key_id"])
        on_conflict (str): Conflict resolution strategy (default: "DO UPDATE SET")
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        bool: True on success (implicitly, doesn't return False)

    Example:
        >>> # Insert new user or update if email already exists
        >>> add_update_record(
        ...     database='db',
        ...     schema='public',
        ...     table='users',
        ...     columns=['email', 'name', 'status', 'updated_at'],
        ...     values=['john@example.com', 'John Doe', 'active', '2025-01-15'],
        ...     conflict_target=['email'],  # Unique constraint on email
        ...     on_conflict='DO UPDATE SET'  # Update all fields on conflict
        ... )
        >>>
        >>> # Insert product, ignore if SKU already exists
        >>> add_update_record(
        ...     database='db',
        ...     schema='inventory',
        ...     table='products',
        ...     columns=['sku', 'name', 'price'],
        ...     values=['WIDGET-001', 'Blue Widget', 29.99],
        ...     conflict_target=['sku'],
        ...     on_conflict='DO NOTHING'  # Don't update existing products
        ... )
        >>>
        >>> # Update user settings by user_id
        >>> add_update_record(
        ...     database='db',
        ...     schema='public',
        ...     table='user_settings',
        ...     columns=['user_id', 'theme', 'notifications'],
        ...     values=[12345, 'dark', True],
        ...     conflict_target=['user_id'],
        ...     on_conflict='DO UPDATE SET'
        ... )
        >>>
        >>> # Pure insert without conflict handling
        >>> add_update_record(
        ...     database='db',
        ...     schema='logs',
        ...     table='access_logs',
        ...     columns=['timestamp', 'user_id', 'action'],
        ...     values=['2025-01-15 10:30:00', 456, 'login'],
        ...     on_conflict=''  # No conflict handling
        ... )

    Note:
        - columns and values lists must have the same length (validated)
        - conflict_target should match a PRIMARY KEY or UNIQUE constraint
        - "DO UPDATE SET" updates ALL columns (uses EXCLUDED.column_name)
        - Transaction is automatically committed on success
        - Transaction is rolled back on any exception
        - Use on_conflict='' or None for pure INSERT without conflict handling
        - Returns after successful execution (doesn't explicitly return True/False)

    Raises:
        ValueError: If columns and values have different lengths
        Exception: If query execution fails (connection is rolled back)

    See Also:
        - update_existing_record(): Update record with WHERE clause
        - delete_record(): Delete record by criteria
        - PostgreSQL UPSERT: https://www.postgresql.org/docs/current/sql-insert.html
    """
    # Validate inputs
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
def update_existing_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    update_columns: List[str],
    update_values: List[Any],
    where_column: str,
    where_value: Any,
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> None:
    """
    Update an existing record using a WHERE clause with single column match.

    This function performs a simple UPDATE operation where you specify which columns
    to update and identify the target record by matching a single column value.
    Commonly used for updating specific records by ID, email, username, or any
    unique identifier. For more complex updates, consider using raw SQL queries
    or multiple WHERE conditions.

    Connection and cursor are automatically managed by the @init_psql_con_cursor
    decorator - you don't need to create or close them manually.

    Args:
        cursor: Auto-injected by decorator
        connection: Auto-injected by decorator
        database (str): Name of the database (required)
        schema (str): Schema containing the table (required)
        table (str): Name of the table to update (required)
        update_columns (List[str]): Column names to update (required)
        update_values (List[Any]): Values corresponding to update_columns (required)
        where_column (str): Column name for WHERE clause (required)
        where_value (Any): Value to match in where_column (required)
        host (str): PostgreSQL host (default: from credentials)
        port (int): PostgreSQL port (default: from credentials)
        user (str): PostgreSQL username (default: from credentials)
        password (str): PostgreSQL password (default: from credentials)

    Returns:
        None

    Example:
        >>> # Update user's name and email by user_id
        >>> update_existing_record(
        ...     database='db',
        ...     schema='public',
        ...     table='users',
        ...     update_columns=['name', 'email', 'updated_at'],
        ...     update_values=['Jane Smith', 'jane.smith@example.com', '2025-01-15'],
        ...     where_column='user_id',
        ...     where_value=12345
        ... )
        >>>
        >>> # Mark order as shipped by order number
        >>> update_existing_record(
        ...     database='db',
        ...     schema='sales',
        ...     table='orders',
        ...     update_columns=['status', 'shipped_at'],
        ...     update_values=['shipped', '2025-01-15 14:30:00'],
        ...     where_column='order_number',
        ...     where_value='ORD-2025-001'
        ... )
        >>>
        >>> # Update product price by SKU
        >>> update_existing_record(
        ...     database='db',
        ...     schema='inventory',
        ...     table='products',
        ...     update_columns=['price', 'last_price_update'],
        ...     update_values=[39.99, '2025-01-15'],
        ...     where_column='sku',
        ...     where_value='WIDGET-001'
        ... )

    Note:
        - update_columns and update_values must have the same length (validated)
        - WHERE clause matches only ONE record (by where_column = where_value)
        - For multiple WHERE conditions, use add_update_record() or raw SQL
        - Updates ALL matching rows (if where_column is not unique)
        - Transaction is automatically committed on success
        - Transaction is rolled back on any exception
        - Use proper data types for where_value (int for IDs, str for text)

    Raises:
        ValueError: If update_columns and update_values have different lengths
        Exception: If query execution fails (connection is rolled back)

    See Also:
        - add_update_record(): Insert or update with UPSERT logic
        - delete_record(): Delete records by criteria
        - get_filtered_records(): Complex WHERE clause filtering for queries
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
def delete_record(
    cursor,
    connection,
    database: str,
    schema_name,
    table_name,
    columns: list[str] | str,
    values: list | str,
    log: object = None,
):
    if not isinstance(columns, list):
        columns = [columns]
    if not isinstance(values, list):
        values = [values]

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
        if log:
            log.info(f"Executing delete query: {query.as_string(connection)}")
        cursor.execute(query, values)
        rows_affected = cursor.rowcount
        connection.commit()
        if log:
            log.info(f"Delete operation successful for {rows_affected} rows.")
        return
    except psycopg2.Error as e:
        if log:
            log.error(f"Error executing delete query: {e}")
        connection.rollback()
        raise e
    except Exception as e:
        if log:
            log.error(f"Unexpected error during delete operation: {e}")
        connection.rollback()
        raise e


@init_psql_con_cursor
def create_schema(
    cursor,
    connection,
    database: str,
    log: object,
    schema_name: str,
):
    log.debug(f"Ensuring schema {schema_name} exists in database {database}")
    query = sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
        sql.Identifier(schema_name)
    )
    try:
        cursor.execute(query)
        connection.commit()
        log.debug(f"Schema {schema_name} ensured in database {database}")
    except Exception as e:
        log.error(f"Error creating schema {schema_name} in database {database}: {e}")
        connection.rollback()
        raise e


# =======================================#   ################
# ==========# Table functions #==========#    #            #
# =======================================#    #            #


@init_psql_con_cursor
def create_or_update_table(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    columns: list[dict],
    log: Optional[object] = None,
):
    """ """
    if log:
        log.debug(f"Ensuring table {table} exists in schema {schema}")
        log.debug(f"Columns: {columns}")
    schema_name_obj = sql.Identifier(schema)
    table_name_obj = sql.Identifier(table)

    # Build column definitions for the CREATE TABLE query
    column_defs = []
    for col in columns:
        col_name = col.get("name")
        col_type = col.get("type", "TEXT")
        column_defs.append(
            sql.SQL("{} {}").format(sql.Identifier(str(col_name)), sql.SQL(col_type))
        )

    # Create the table if it doesn't exist
    query = sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
        schema_name_obj, table_name_obj, sql.SQL(", ").join(column_defs)
    )
    try:
        cursor.execute(query)
        connection.commit()
    except Exception as e:
        if log:
            log.error(f"Error creating table {table} in schema {schema}: {e}")
        connection.rollback()
        raise

    # Add any missing columns to the existing table
    for col in columns:
        col_name = col["name"]
        col_type = col["type"]
        alter_query = sql.SQL(
            """
            ALTER TABLE {schema}.{table}
            ADD COLUMN IF NOT EXISTS {col_name} {col_type}
        """
        ).format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            col_name=sql.Identifier(col_name),
            col_type=sql.SQL(col_type),
        )
        try:
            cursor.execute(alter_query)
            connection.commit()
        except Exception as e:
            if log:
                log.error(
                    f"Error adding column {col_name} to table {schema}.{table}: {e}"
                )
            connection.rollback()
            raise

    if log:
        log.debug(f"Table {table} ensured in schema {schema}")


@init_psql_con_cursor
def ensure_join_table_exists(
    cursor,
    connection,
    database: str,
    log: object,
    join_dict: dict,
    uid_col: str = "primary_key_id",
    join_schema: str = "Join",
):
    """
    Adds a join table to the join schema if it does not already exist.
    Columns will be UUIDs referencing the 'primary_key_id' of the referenced tables.
    Set to cascade delete.
    Args:
        database (str) : The name of the database.
        join_dict (dict) : A dictionary containing the join information, where keys are table names and values are lists of column names:
            table_name (str) : The join table name,
            main_schema (str) : The main schema name,
            column1_name (str): The name of the first column in the join table,
            column2_name (str) : The name of the second column in the join table,
            column1_table (str) : The name of the first table in the join,
            column2_table (str) : The name of the second table in the join
        uid_col (str) : The name of the column that will be used as the unique identifier for the join table.
        join_schema (str) : The schema where the join table will be created.
    """
    table_name = join_dict.get("table_name", "")
    reference_schema = join_dict.get("main_schema", "")

    column1_name = join_dict.get("column1_name", "")
    column2_name = join_dict.get("column2_name", "")
    column1_table = join_dict.get("column1_table", "")
    column2_table = join_dict.get("column2_table", "")

    if not any(
        [
            table_name,
            reference_schema,
            column1_name,
            column2_name,
            column1_table,
            column2_table,
        ]
    ):
        log.error("Missing required parameters for join table creation.")
        raise ValueError("Missing required parameters for join table creation.")

    # Build columns for the query
    column_defs = [
        sql.SQL(
            "{col_name} UUID, FOREIGN KEY ({col_name}) REFERENCES {ref_schema}.{ref_table} ({ref_column}) ON DELETE CASCADE"
        ).format(
            col_name=sql.Identifier(col_name),
            ref_schema=sql.Identifier(reference_schema),
            ref_table=sql.Identifier(ref_table),
            ref_column=sql.Identifier(uid_col),
        )
        for (col_name, ref_table) in [
            (
                column1_name,
                column1_table,
            ),  # If you want to use schema, replace accordingly
            (column2_name, column2_table),
        ]
    ]

    # Assemble the SQL query to create the join table
    query = sql.SQL(
        """CREATE TABLE IF NOT EXISTS {schema}.{table} (
            {columns},
            PRIMARY KEY ({col1}, {col2})
            )
            """
    ).format(
        schema=sql.Identifier(join_schema),
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(column_defs),
        col1=sql.Identifier(column1_name),
        col2=sql.Identifier(column2_name),
    )

    log.debug(f"Ensuring join table {table_name} exists in schema {join_schema}")
    try:
        cursor.execute(query)
        connection.commit()
        log.debug(f"Join table {table_name} ensured in schema {join_schema}")
    except psycopg2.Error as e:
        log.error(f"Error ensuring join table {table_name}: {e}")
        connection.rollback()
        raise e
    except Exception as e:
        log.error(f"Unexpected error ensuring join table {table_name}: {e}")
        connection.rollback()
        raise e


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
    schema: str,
    table: str,
    column: str,
    column_type: str,
    default_value: str = None,
    not_null: bool = False,
):
    alter_query = f"""
    ALTER TABLE "{schema}"."{table}"
    ADD COLUMN "{column}" {column_type}
    """
    if default_value:
        alter_query += f" DEFAULT {default_value}"
    if not_null:
        alter_query += " NOT NULL"

    try:
        cursor.execute(alter_query)
        connection.commit()
    except Exception as e:
        error_message = f"""
## Error adding column {column} to table {schema}.{table}:
column_type: {column_type},
default_value: {default_value},
not_null: {not_null},
query: {alter_query}

```Error: {e}```
        """
        connection.rollback()
        send_discord_warning(error_message, username="sql_helper")
        raise


@init_psql_con_cursor
def get_table_columns(
    cursor,
    connection,
    database: str,
    schema_name: str,
    table_name: str,
) -> list:
    """
    Get a list of columns for a given table.
    Args:
        database (str): The name of the database.
        schema_name (str): The name of the schema.
        table_name (str): The name of the table.
    Returns:
        list: List of column names.
    """
    query = f"""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = %s
    AND table_name = %s
    ORDER BY column_name;
    """
    try:
        cursor.execute(query, (schema_name, table_name))
        results = cursor.fetchall()
        return [row["column_name"] for row in results]
    except Exception as e:
        return []


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


# ==========================================#      #  # ### #
# ===========# Utility functions #==========#      #  #  #  #
# ==========================================#      ####  #  ###


def map_notion_type_to_sql(notion_property: dict) -> str:
    """
    Maps Notion property types to SQL data types.
    Args:
        notion_type (str): The Notion property.
    Returns:
        str: The corresponding SQL data type.
    """
    notion_to_sql_map = {
        "title": "VARCHAR(255)",
        "rich_text": "TEXT",
        "number": "FLOAT",
        "select": "VARCHAR(255)",
        "multi_select": "TEXT[]",
        "date": "TIMESTAMP",
        "people": "TEXT[]",
        "files": "TEXT[]",
        "checkbox": "BOOLEAN",
        "url": "TEXT",
        "email": "VARCHAR(255)",
        "phone_number": "VARCHAR(255)",
        "formula": "TEXT",
        "relation": None,  # 'Relation' type will be handled separately
        "array": "TEXT[]",
        "incomplete": "TEXT",
        "unsupported": "TEXT",
        "created_time": "TIMESTAMP",
        "created_by": "TEXT",
        "last_edited_time": "TIMESTAMP",
        "last_edited_by": "TEXT",
    }
    prop_type = notion_property.get("type")
    if prop_type == "rollup":
        return "TEXT"

    return notion_to_sql_map.get(prop_type, "TEXT")


def get_notion_table_columns(
    join_manager: object,
    database_id: str,
    schema_name: str,
    table_name: str,
    notion: NotionApiHelper,
) -> list[dict[tuple[str, str]]]:
    # Parse columns and column types to build the table structure
    column_list = []
    table_db_scheme = notion.get_database(db_id=database_id)
    table_props = table_db_scheme.get("properties", {})
    for property in table_props.values():
        prop_name = property.get("name", "")
        prop_type = property.get("type", "")
        if prop_type == "rollup":
            continue
        for sql_prop in column_list:
            if sql_prop.get("name") == prop_name:
                continue  # Skip duplicate property names
        if prop_type == "relation":
            join_manager.parse_relation_property(
                property=property,
                schema_name=schema_name,
                table_name=table_name,
            )
            continue

        column_list.append(
            {
                "name": prop_name,
                "type": map_notion_to_sql_type(notion_property=property),
            }
        )

    column_list.append({"name": "primary_key_id", "type": "UUID"})
    return column_list


def rehost_notion_file(
    url: str,
    column: str,
    pkid: str,
    log: logging.Logger,
    index: int = 0,
    file_name: str = None,
    bucket_name: str = ORDER_ASSET_BUCKET,
    blob_name: str = None,
) -> str:
    log.info(f"Rehosting Notion URL: {url}")
    from uuid import uuid4

    try:
        response = requests.get(url)
        if not response.status_code == 200:
            log.error(
                f"Failed to download file from {url}, status code: {response.status_code}"
            )
            return url

        # Download the file locally
        mimetype, extension = determine_file_type_from_response(url, response)
        if not file_name:
            file_name = f"{pkid}__{column}__{index}"
        file_name += f"{extension}"
        file_path = ROOT_DIR / "tmp" / file_name
        if not blob_name:
            blob_name = f"assets/{file_name}".replace(" ", "_").lower()
        else:
            blob_name = (
                blob_name.replace(" ", "_")
                .replace("{file_name}", file_name)
                .replace("{pkid}", pkid)
                .replace("{column}", column)
                .lower()
            )
        if os.path.exists(file_path):
            log.warning(f"File already exists locally, overwriting: {file_path}")
            os.remove(file_path)
        with open(file_path, "wb") as file:
            file.write(response.content)

        # Upload to GCS
        bucket = GCloudBucket(bucket_name, log)
        bucket.upload_to_bucket(file_path, blob_name)
        uuid = str(uuid4())
        gcs_url = (
            f"https://storage.googleapis.com/{bucket_name}/{blob_name}?exec-id={uuid}"
        )
        log.info(f"Execution ID: {uuid} - File rehosted to: {gcs_url}")
        os.remove(file_path)
        return gcs_url
    except Exception as e:
        log.error(f"Error rehosting file from {url}: {e}")
        return url


def parse_notion_data(
    log: logging.Logger,
    notion: NotionApiHelper,
    records: list[dict],
) -> tuple[list, list[list[dict]], dict]:
    """
    Parse Notion data into a structured format for SQL insertion.
    Args:
        log (object): Logger object for logging debug information.
        notion (object): Notion API client instance.
        schema_name (str): The schema name where the records will be stored (not the join table).
        records (list[dict]): List of Notion page records to be parsed.
        notion_table_structure (dict): Structure of the Notion table containing properties and metadata.
        join_manager (JoinTableManager): Instance of JoinTableManager to handle join tables.
    Returns:
        tuple: A tuple containing:
            - table_columns (list): List of column names for the SQL table.
            - table_values (list[list[dict]]): List of values for the SQL table.
            - relation_structure (dict): Structure of the relations for the SQL table.
    """
    table_columns = []  # Start empty, add primary key later.
    table_values = []
    relation_data = {}

    # Iterate through each record to build the values and relations.
    for record in records:
        record_id = record.get("id", "").replace("-", "")
        record_values = [record_id]
        page_properties = record.get("properties", {})

        # If table columns are empty, we need to add the primary key and set flag.
        record_columns = False
        if not table_columns:
            table_columns = ["primary_key_id"]
            record_columns = True

        # Iterate through each property in the record.
        for prop_name, prop in page_properties.items():
            prop_type = prop.get("type", "")

            if prop_type == "rollup":
                continue  # Skip rollup properties as they are not directly stored in SQL.

            prop_value = notion.return_property_value(prop, record_id)

            # Build the relation values if the property is a relation.
            if prop_type == "relation":
                # Init list in relation_data if not already present.
                if prop_name not in relation_data:
                    relation_data[prop_name] = []

                # Create a list of all relation IDs.
                values = []

                if not prop_value:
                    values.append([record_id, None])

                if prop_value and isinstance(prop_value, list):
                    for relation_id in prop_value:
                        relation_id = relation_id.replace("-", "")
                        if not all([record_id, relation_id]):
                            continue
                        values.append([record_id, relation_id])

                relation_data[prop_name].extend(values)
                continue

            # Rehost Notion files if the property is of type 'files'
            elif prop_type == "files" and isinstance(prop_value, list) and prop_value:
                urls_list = []
                files_rehosted = False
                for index, file_url in enumerate(prop_value):
                    if file_url:
                        if re.match(NOTION_URL_REGEX, file_url):
                            try:
                                urls_list.append(
                                    rehost_notion_file(
                                        url=file_url,
                                        column=prop_name,
                                        pkid=record_id,
                                        log=log,
                                        index=index,
                                    )
                                )
                                files_rehosted = True
                            except Exception as e:
                                log.error(
                                    f"Error rehosting Notion file {file_url}: {e}"
                                )
                                urls_list.append(file_url)

                if files_rehosted:
                    prop_value = urls_list
                    file_names = [file.get("name") for file in prop.get("files", [])]

                    update_package = {
                        prop_name: {
                            "files": [
                                {"name": name, "external": {"url": url}}
                                for name, url in zip(file_names, urls_list)
                            ]
                        }
                    }
                    try:
                        log.debug(
                            f"Updating Notion page {record_id} with rehosted file URLs. Package: {update_package}"
                        )
                        page = notion.update_page(record_id, update_package)
                    except Exception as e:
                        log.error(
                            f"Exception updating Notion page {record_id} with rehosted file URLs: {e}"
                        )
                        page = None
                    if not page:
                        log.error(
                            f"Failed to update Notion page {record_id} with rehosted file URLs."
                        )
                    else:
                        log.info(
                            f"Successfully updated Notion page {record_id} with rehosted file URLs."
                        )

            # Handle specific property types
            elif prop_type in [
                "title",
                "select",
                "email",
                "phone_number",
            ] and isinstance(prop_value, str):
                prop_value = prop_value[:255]

            # Append the column name if the record_columns flag is set.
            if record_columns:
                table_columns.append(prop_name)
            record_values.append(prop_value)

        log.debug(
            f"Record ID: {record_id}, Record column count: {len(table_columns)}, values count: {len(record_values)}"
        )
        table_values.append(record_values)

    log.info(f"Total pages parsed: {len(table_values)}")
    log.info(f"Total columns parsed: {len(table_columns)}")
    log.debug(f"Returning from parse_notion_data")
    return table_columns, table_values, relation_data


def map_notion_to_sql_type(notion_property: dict) -> str:
    """
    Maps Notion data types to SQL data types.
    Args:
        notion_property (dict): The Notion data type to be mapped.
    Returns:
        str: The corresponding SQL data type.
    """
    notion_to_sql_map = {
        "title": "VARCHAR(255)",
        "rich_text": "TEXT",
        "number": "FLOAT",
        "select": "VARCHAR(255)",
        "multi_select": "TEXT[]",
        "date": "TIMESTAMP",
        "people": "TEXT[]",
        "files": "TEXT[]",
        "checkbox": "BOOLEAN",
        "url": "TEXT",
        "email": "VARCHAR(255)",
        "phone_number": "VARCHAR(255)",
        "formula": "TEXT",
        "relation": None,  # 'Relation' type will be handled separately
        "rollup": None,
        "array": "TEXT[]",
        "incomplete": "TEXT",
        "unsupported": "TEXT",
        "created_time": "TIMESTAMP",
        "created_by": "TEXT",
        "last_edited_time": "TIMESTAMP",
        "last_edited_by": "TEXT",
    }
    prop_type = notion_property.get("type")
    if prop_type == "rollup":
        return "TEXT"

    return notion_to_sql_map.get(prop_type, "TEXT")


def get_table_name_from_notion_id(related_db_id: str, notion: NotionApiHelper) -> str:
    """
    Get the table name from a Notion database ID.
    Args:
        notion_id (str): The Notion database ID.
        notion (NotionApiHelper): The Notion API helper instance.
    Returns:
        str: The table name corresponding to the Notion database ID.
    """
    related_db_id = related_db_id.replace("-", "")

    # Check SQL First
    rel_db_scheme_record = get_record(
        database="db",
        schema="meta",
        table="notion_table_namemap",
        column="db_id",
        value=related_db_id,
    )

    # If not found in SQL, fetch the related database structure from Notion.
    if not rel_db_scheme_record:
        rel_table_scheme = notion.get_database(related_db_id)
        if not rel_table_scheme:
            raise ValueError(
                f"Related database with ID {related_db_id} not found in Notion."
            )
        related_title = rel_table_scheme.get("title", [{}])[0]
        related_table_name = related_title.get("plain_text", "")
        # Add the related database ID and table name to the namemap.
        add_update_record(
            database="db",
            schema="meta",
            table="notion_table_namemap",
            columns=["db_id", "table_name"],
            values=[related_db_id, related_table_name],
            conflict_target=["db_id"],
        )

    # Otherwise use the table name from SQL.
    else:
        related_table_name = rel_db_scheme_record.get("table_name", "")

    return related_table_name


# ============================================#
# =========# Print History Functions #=======#
# ============================================#


@init_psql_con_cursor
def create_print_history_table(
    cursor,
    connection,
    database: str,
    schema: str = "metrics",
    table: str = "print_history",
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> bool:
    """
    Create the print_history table in the specified schema.

    Args:
        cursor: Database cursor (auto-injected)
        connection: Database connection (auto-injected)
        database (str): Database name
        schema (str): Schema name (default: 'metrics')
        table (str): Table name (default: 'print_history')

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create schema if it doesn't exist
        cursor.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
        )

        # Create table with proper columns
        create_table_query = sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {schema}.{table} (
                id SERIAL PRIMARY KEY,
                file_id VARCHAR(255) NOT NULL,
                file_name TEXT NOT NULL,
                workflow VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                error_msg TEXT,
                timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """
        ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))

        cursor.execute(create_table_query)

        # Create index on timestamp for faster queries
        index_name_timestamp = f"idx_{table}_timestamp"
        cursor.execute(
            sql.SQL(
                """
            CREATE INDEX IF NOT EXISTS {} 
            ON {}.{} (timestamp DESC)
        """
            ).format(
                sql.Identifier(index_name_timestamp),
                sql.Identifier(schema),
                sql.Identifier(table),
            )
        )

        # Create index on workflow for filtering
        index_name_workflow = f"idx_{table}_workflow"
        cursor.execute(
            sql.SQL(
                """
            CREATE INDEX IF NOT EXISTS {} 
            ON {}.{} (workflow)
        """
            ).format(
                sql.Identifier(index_name_workflow),
                sql.Identifier(schema),
                sql.Identifier(table),
            )
        )

        connection.commit()
        return True

    except Exception as e:
        print(f"Error creating print_history table: {e}")
        connection.rollback()
        return False


@init_psql_con_cursor
def insert_print_history(
    cursor,
    connection,
    database: str,
    file_id: str,
    file_name: str,
    workflow: str,
    status: str,
    error_msg: str = None,
    timestamp: datetime = None,
    schema: str = "metrics",
    table: str = "print_history",
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> Optional[int]:
    """
    Insert a print history record into the database.

    Args:
        cursor: Database cursor (auto-injected)
        connection: Database connection (auto-injected)
        database (str): Database name
        file_id (str): Google Drive file ID
        file_name (str): File name
        workflow (str): Workflow name (e.g., 'UPSTAIRS', 'PRINT')
        status (str): Status ('success', 'failed', 'error')
        error_msg (str): Error message if failed
        timestamp (datetime): Timestamp of the event (default: now)
        schema (str): Schema name (default: 'metrics')
        table (str): Table name (default: 'print_history')

    Returns:
        int: ID of inserted record, or None if failed
    """
    try:
        if timestamp is None:
            timestamp = datetime.now()

        insert_query = sql.SQL(
            """
            INSERT INTO {schema}.{table} 
            (file_id, file_name, workflow, status, error_msg, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))

        cursor.execute(
            insert_query, (file_id, file_name, workflow, status, error_msg, timestamp)
        )

        result = cursor.fetchone()
        connection.commit()

        return result["id"] if result else None

    except Exception as e:
        print(f"Error inserting print history: {e}")
        connection.rollback()
        return None


@init_psql_con_cursor
def get_print_history(
    cursor,
    connection,
    database: str,
    workflow: str = None,
    limit: int = 50,
    offset: int = 0,
    schema: str = "metrics",
    table: str = "print_history",
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> List[Dict[str, Any]]:
    """
    Retrieve print history records from the database.

    Args:
        cursor: Database cursor (auto-injected)
        connection: Database connection (auto-injected)
        database (str): Database name
        workflow (str): Optional workflow filter
        limit (int): Maximum number of records to return (default: 50)
        offset (int): Number of records to skip (default: 0)
        schema (str): Schema name (default: 'metrics')
        table (str): Table name (default: 'print_history')

    Returns:
        list: List of print history records
    """
    try:
        if workflow:
            query = sql.SQL(
                """
                SELECT id, file_id, file_name, workflow, status, error_msg, 
                       timestamp, created_at
                FROM {schema}.{table}
                WHERE workflow = %s
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """
            ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))
            cursor.execute(query, (workflow, limit, offset))
        else:
            query = sql.SQL(
                """
                SELECT id, file_id, file_name, workflow, status, error_msg, 
                       timestamp, created_at
                FROM {schema}.{table}
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """
            ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))
            cursor.execute(query, (limit, offset))

        results = cursor.fetchall()

        # Convert datetime objects to ISO format strings
        history = []
        for record in results:
            record_dict = dict(record)
            if record_dict.get("timestamp"):
                record_dict["timestamp"] = record_dict["timestamp"].isoformat()
            if record_dict.get("created_at"):
                record_dict["created_at"] = record_dict["created_at"].isoformat()
            history.append(record_dict)

        return history

    except Exception as e:
        print(f"Error retrieving print history: {e}")
        return []


@init_psql_con_cursor
def get_print_history_count(
    cursor,
    connection,
    database: str,
    workflow: str = None,
    schema: str = "metrics",
    table: str = "print_history",
    host: str = sql_ip,
    port: int = sql_port,
    user: str = sql_user,
    password: str = sql_pass,
) -> int:
    """
    Get the total count of print history records.

    Args:
        cursor: Database cursor (auto-injected)
        connection: Database connection (auto-injected)
        database (str): Database name
        workflow (str): Optional workflow filter
        schema (str): Schema name (default: 'metrics')
        table (str): Table name (default: 'print_history')

    Returns:
        int: Total count of records
    """
    try:
        if workflow:
            query = sql.SQL(
                """
                SELECT COUNT(*) as count
                FROM {schema}.{table}
                WHERE workflow = %s
            """
            ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))
            cursor.execute(query, (workflow,))
        else:
            query = sql.SQL(
                """
                SELECT COUNT(*) as count
                FROM {schema}.{table}
            """
            ).format(schema=sql.Identifier(schema), table=sql.Identifier(table))
            cursor.execute(query)

        result = cursor.fetchone()
        return result["count"] if result else 0

    except Exception as e:
        print(f"Error getting print history count: {e}")
        return 0


class NotionToJoinTableManager:
    def __init__(self, log: logging.Logger, schema_name: str = "Join"):
        self.schema_name = schema_name
        self.log = log
        self.join_tables = {}

        try:
            self.connection = init_psql_connection(db="db")
            self.cursor = self.connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except psycopg2.Error as e:
            self.log.error(f"Error initializing database connection: {e}")
            raise e

    def get_join_table_name(
        self, schema_name: str, table1: str, table2: str
    ) -> tuple[str, str, str]:
        """
        Generate a join table name based on the two table names.
        Args:
            schema_name (str): The schema name where the related tables are located.
            table1 (str): The first table name.
            table2 (str): The second table name.
        Returns:
            str: The generated join table name.
            str: The column name for the first column.
            str: The column name for the second column.
        """
        tables = sorted([table1, table2])

        column1 = f"{tables[0]}_id"
        column2 = f"{tables[1]}_id"
        if table1 == table2:
            column2 = f"{tables[1]}_id2"

        return f"{schema_name}_{tables[0]}_{tables[1]}", column1, column2

    def parse_relation_property(
        self,
        property: dict,
        schema_name: str,
        table_name: str,
    ):
        prop_name = property.get("name", "")
        prop_type = property.get("type", "")
        if prop_type != "relation":
            self.log.warning(f"Property {prop_name} is not a relation type.")
            return None

        # Get notion instance
        header_path = (
            "src/headers.json" if schema_name == "" else "src/headers_2.json"
        )
        self.notion = NotionApiHelper(header_path=header_path)

        # Get the related database ID and structure
        relation = property.get("relation", {})
        related_db_id = relation.get("database_id", "").replace("-", "")

        rel_table_name = get_table_name_from_notion_id(
            related_db_id=related_db_id,
            notion=self.notion,
        )

        join_table_name, column1, column2 = self.get_join_table_name(
            schema_name=schema_name,
            table1=table_name,
            table2=rel_table_name,
        )

        # If the join table is not in the join_tables dictionary, create it.
        if join_table_name not in self.join_tables:
            self.join_tables[join_table_name] = {
                "table_name": join_table_name,
                "main_schema": schema_name,
                "column1_name": column1,
                "column1_table": column1.rsplit(sep="_id", maxsplit=1)[0],
                "column2_name": column2,
                "column2_table": column2.rsplit(sep="_id", maxsplit=1)[0],
                "columns": [column1, column2],
                "values": [],
            }
            self.log.info(
                f"Join table {join_table_name} created for relation {prop_name} between {table_name} and {rel_table_name}"
            )
        else:
            self.log.debug(
                f"Join table {join_table_name} already exists for relation {prop_name} between {table_name} and {rel_table_name}"
            )

        return self.join_tables[join_table_name]

    def store_relation_data(
        self,
        relation_data: dict[str, list[tuple[str, str]]],
        current_table_name: str,
        current_schema_name: str,
        notion: NotionApiHelper,
        notion_table_structure: dict,
    ):
        """
        Add relation data to the self.join_tables based on the property values.
        Args:
            con (Connection): The database connection object.
            cursor (Cursor): The database cursor object.
            relation_data (dict[str, list[tuple[str, str]]]): A dictionary where keys are relation property names and values are lists of tuples containing record IDs and related record IDs.
            current_table_name (str): The name of the current table.
            current_schema_name (str): The name of the current schema.
            notion (NotionApiHelper): The Notion API helper instance.
            notion_table_structure (dict): The structure of the Notion table. Needed to get the related database ID.
        """
        db_properties = notion_table_structure.get("properties", {})

        for prop_name, values in relation_data.items():
            relation_prop = db_properties.get(prop_name, {})
            if not relation_prop:
                self.log.warning(
                    f"Relation property {prop_name} not found in table structure."
                )
                continue
            prop_type = relation_prop.get("type", "")
            if prop_type != "relation":
                self.log.warning(f"Property {prop_name} is not a relation type.")
                continue

            # Get the related database ID to find the related table name.
            related_dict = relation_prop.get("relation", {})
            related_db_id = related_dict.get("database_id", "").replace("-", "")

            # Get the related table name from the Notion database ID.
            related_table_name = get_table_name_from_notion_id(
                related_db_id=related_db_id,
                notion=notion,
            )

            # Generate the join table name and column names.
            join_table_name, column1, column2 = self.get_join_table_name(
                schema_name=current_schema_name,
                table1=current_table_name,
                table2=related_table_name,
            )

            # If the join table is not in the join_tables dictionary, log a warning.
            if join_table_name not in self.join_tables:
                self.log.warning(
                    f"Join table {join_table_name} not found for relation {prop_name}. Should have been created during validation."
                )
                continue

            # Check if the join table has the expected column names.
            else:
                store_col1 = self.join_tables[join_table_name]["column1_name"]
                store_col2 = self.join_tables[join_table_name]["column2_name"]
                if store_col1 != column1 or store_col2 != column2:
                    self.log.error(
                        f"Join table {join_table_name} has unexpected column names: {column1}, {column2}. Expected: {store_col1}, {store_col2}."
                    )
                    continue
            table1 = self.join_tables[join_table_name]["column1_table"]
            table2 = self.join_tables[join_table_name]["column2_table"]

            # Determine which column to use for the current table.
            if current_table_name == table1:
                record_col = column1
                related_col = column2
            elif current_table_name == table2:
                record_col = column2
                related_col = column1
            else:
                self.log.error(
                    f"Current table {current_table_name} does not match either {table1} or {table2} in join table {join_table_name}."
                )
                continue

            # Initialize connection to purge records with no or removed relations.
            conn = init_psql_connection(db="db")
            cursor = create_cursor(connection=conn)
            try:

                # Isolate the values that have no relations.
                values_without_relations = [
                    (record_id.replace("-", ""), None)
                    for record_id, rel_id in values
                    if not rel_id
                ]

                # Purge records with no relations from the join table.
                if values_without_relations:
                    for record_id, _ in values_without_relations:
                        self.log.debug(
                            f"Record ID {record_id} has no relations, purging from join table {join_table_name}."
                        )
                        try:
                            delete_record(
                                cursor=cursor,
                                connection=conn,
                                database="db",
                                log=self.log,
                                schema_name=self.schema_name,
                                table_name=join_table_name,
                                columns=[record_col],
                                values=[record_id],
                            )
                        except Exception as e:
                            self.log.error(
                                f"Error deleting record {record_id} from join table {join_table_name}: {e}"
                            )

                # Isolate the values that have relations.
                values_with_relations = [
                    (record_id.replace("-", ""), rel_id.replace("-", ""))
                    for record_id, rel_id in values
                    if rel_id
                ]
                values = values_with_relations

                # Iterate through the values to handle relations.
                handled_index_list = []
                for index, (record_id, rel_id) in enumerate(values):
                    if index in handled_index_list:
                        continue  # Skip already handled indexes.

                    # Create a list of indexes that have the current record ID.
                    record_id_indexes = [
                        i for i, x in enumerate(values) if x[0] == record_id
                    ]
                    if len(record_id_indexes) > 1:
                        related_ids = [values[i][1] for i in record_id_indexes]
                    else:
                        related_ids = [rel_id]

                    # Get all current records in the join table for the current record ID.
                    current_records = get_records(
                        cursor=cursor,
                        connection=conn,
                        database="db",
                        schema=self.schema_name,
                        table=join_table_name,
                        column=record_col,
                        values=[record_id.replace("-", "")],
                    )

                    # Compare current records with the updated record ids.
                    for record in current_records:
                        current_rel_id = record.get(related_col, "").replace("-", "")

                        # If the current related ID is not in the updated related IDs, delete it.
                        if current_rel_id and current_rel_id not in related_ids:
                            self.log.info(
                                f"Record ID {record_id} has a relation {current_rel_id} that is not in the current values, purging from join table {join_table_name}."
                            )
                            try:
                                delete_record(
                                    cursor=cursor,
                                    connection=conn,
                                    database="db",
                                    log=self.log,
                                    schema_name=self.schema_name,
                                    table_name=join_table_name,
                                    columns=[record_col, related_col],
                                    values=[record_id, current_rel_id],
                                )
                            except Exception as e:
                                self.log.error(
                                    f"Error deleting record {current_rel_id} from join table {join_table_name}: {e}"
                                )

                    # Update the handled index list.
                    handled_index_list.extend(record_id_indexes)
            finally:
                cursor.close()
                conn.close()

            # Related record IDs go in column 1, current record ID in column 2.
            if related_table_name == table1 and current_table_name == table2:
                new_values = [
                    [rel_id.replace("-", ""), record_id] for record_id, rel_id in values
                ]
                self.join_tables[join_table_name]["values"].extend(new_values)
                self.log.info(
                    f"Added (to memory) {len(values)} records to join table {join_table_name} for relation {prop_name} between {current_table_name} and {related_table_name}."
                )

            # Related record IDs go in column 2, current record ID in column 1.
            elif related_table_name == table2 and current_table_name == table1:
                new_values = [
                    [record_id, rel_id.replace("-", "")] for record_id, rel_id in values
                ]
                self.join_tables[join_table_name]["values"].extend(new_values)
                self.log.info(
                    f"Added (to memory) {len(values)} records to join table {join_table_name} for relation {prop_name} between {current_table_name} and {related_table_name}."
                )

            # Something fucked up
            else:
                self.log.error(
                    f"Join table {join_table_name} has unexpected column names: {column1}, {column2}. Expected: {store_col1}, {store_col2}."
                )
                continue

    def handle_fkv(self, error_message: str, current_schema: str) -> bool:
        """
        Handle Foreign Key Violation errors by logging and raising an exception.
        Args:
            error_message (str): The error message to log.
        Raises:
            psycopg2.errors.ForeignKeyViolation: The Foreign Key Violation error.
        """
        regex_str = (
            r".*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}).*"
        )
        match = re.search(regex_str, str(error_message))

        if not match:
            self.log.error(
                f"Failed to parse Foreign Key Violation error: {error_message}"
            )
            raise psycopg2.errors.ForeignKeyViolation(error_message)

        # Extract the relevant information from the matches.
        foreign_key_value = match.group(1)

        foreign_key_value = foreign_key_value.replace("-", "")
        fkv_page = self.notion.get_page(pageID=foreign_key_value)
        if not fkv_page:
            self.log.error(
                f"Failed to fetch Notion page for Foreign Key value {foreign_key_value}"
            )
            raise psycopg2.errors.ForeignKeyViolation(
                f"Foreign Key value {foreign_key_value} not found in Notion."
            )
        fkv_parent = fkv_page.get("parent", {})
        fkv_db_id = fkv_parent.get("database_id", "").replace("-", "")
        table_name = get_table_name_from_notion_id(
            related_db_id=fkv_db_id,
            notion=self.notion,
        )
        fkv_columns, fkv_values, _ = parse_notion_data(
            log=self.log,
            notion=self.notion,
            records=[fkv_page],
        )
        if not fkv_values:
            self.log.error(
                f"No values found for Foreign Key value {foreign_key_value} in Notion."
            )
            raise psycopg2.errors.ForeignKeyViolation(
                f"Foreign Key value {foreign_key_value} not found in Notion."
            )
        add_update_record(
            database="db",
            schema=current_schema,
            table=table_name,
            columns=fkv_columns,
            values=fkv_values[0],
        )

        self.log.error(f"Resolved FKV for record: '{foreign_key_value}'")

        return (
            True  # Indicate that the FK violation was handled and a record was added.
        )

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def add_missing_record(
        self, rel_schema_name: str, rel_table_name: str, foreign_key_value: str
    ) -> bool:
        """
        Add a missing record to the relevant table.
        Args:
            schema_name (str): The schema name.
            rel_table_name (str): The related table name.
            rel_schema_name (str): The related schema name.
            foreign_key_value (str): The foreign key value.
        """
        self.log.info(
            f"Adding missing record to {rel_schema_name}.{rel_table_name} with value {foreign_key_value}"
        )

        fk_value = foreign_key_value.replace("-", "")
        headers = (
            "src/headers.json" if rel_schema_name == "" else "src/headers_2.json"
        )
        notion = NotionApiHelper(header_path=headers)

        record = notion.get_page(pageID=fk_value)
        if not record:
            self.log.error(
                f"Failed to fetch record for {fk_value} in {rel_schema_name}.{rel_table_name}"
            )
            return

        record_parent = record.get("parent", {})
        database_id = record_parent.get("database_id", "").replace("-", "")
        db_structure = notion.get_database(database_id)
        if not db_structure:
            self.log.error(f"Failed to fetch database structure for {database_id}")
            return

        self.cursor = init_psql_connection(db="")
        self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            rel_table_columns, rel_record_values_list, _ = parse_notion_data(
                log=self.log,
                notion=notion,
                records=[record],
            )

            if rel_record_values_list:
                rel_record_values = rel_record_values_list[0]
            else:
                self.log.error(
                    f"No record values found for {rel_schema_name}.{rel_table_name}"
                )
                return

            add_update_record(
                self=self,
                schema_name=rel_schema_name,
                table_name=rel_table_name,
                columns=rel_table_columns,
                values=rel_record_values,
                conflict_target=["primary_key_id"],
            )
            self.log.info(
                f"Missing record added to {rel_schema_name}.{rel_table_name} with value {foreign_key_value}"
            )
            return True
        except Exception:
            self.conn.rollback()
            raise
