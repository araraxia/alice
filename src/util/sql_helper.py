#!/usr/bin/env python3
# Aria Corona 2025/06/09

import psycopg2, json
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
from functools import wraps
from colorama import Fore
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent # alice/
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
) -> list:
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
) -> list:
    """
    Query a postgreSQL table for a list of records matching the given value.
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
        column (str) : Required, column name to query by
        value (str) : Required, value to query by
    Returns:
        records (list) : List of RealDictCursor dictionaries fetched with the
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
        column_defs.append(
            sql.SQL("{} {}").format(col_name_obj, col_type_obj)
        )

    query = sql.SQL("""
        CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} ({column_defs})
        """).format(
        schema_name=schema_name_obj,
        table_name=table_name_obj,
        column_defs=sql.SQL(", ").join(column_defs)
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
        not_null=sql.SQL("NOT NULL") if col_not_null else sql.SQL("")
    )
    try:
        cursor.execute(alter_query)
        connection.commit()
        return True
    except Exception as e:
        log.error(f"Error adding column {column_name} to table {schema_name}.{table_name}: {e}")
        connection.rollback()
        return False

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
    check_query = sql.SQL(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_schema = {schema_name}
        AND table_name = {table_name}
        AND constraint_type = 'PRIMARY KEY'
        """
    ).format(
        schema_name=schema_name_obj,
        table_name=table_name_obj,
    )
    try:
        cursor.execute(check_query)
        existing_constraints = cursor.fetchall()
        if existing_constraints:
            return True  # Primary key constraint already exists
    except Exception as e:
        print(Fore.RED + f"Error checking existing constraints on {schema_name}.{table_name}: {e}" + Fore.RESET)
        return False
    
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
        print(Fore.RED + f"Error adding primary key constraint to {schema_name}.{table_name}: {e}" + Fore.RESET)
        connection.rollback()
        return False
    

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
    elif isinstance(value, int):
        return "INTEGER"
    elif isinstance(value, float):
        return "FLOAT"
    elif isinstance(value, dict):
        return "JSONB"
    elif isinstance(value, str):
        return "TEXT"
    elif isinstance(value, list):
        if value:
            return f"{guess_column_type(value[0])}[]"
    else:
        return "TEXT"