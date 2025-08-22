#!/usr/bin/env python3
# Aria Corona 2025/06/09

import psycopg2, json, re
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from extras.helpers import send_discord_warning
from functools import wraps
from colorama import Fore

# Access psql defaults
with open('./cred/psql.json', "r") as f:
    psql_cred = json.load(f)
sql_ip = psql_cred.get('ip', "")
sql_port = psql_cred.get('port', "")
sql_user = psql_cred.get('user', "")
sql_pass = psql_cred.get('password', "")

#============================================#      ######
#==========# Connection functions #==========#    ###    E
#============================================#      ######

def init_psql_connection(db, 
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
        con = psycopg2.connect(dbname=db,
                               user=user,
                               password=password,
                               host=host,
                               port=port
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
    psycopg2 connection and cursor factory as a decorator. Handles closing the connection and cursor.
    Inserts connection and cursor into the decorated function args.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract DB connection details from kwargs
        db = kwargs.get("database", "meno_accounts")
        host = kwargs.get("host", sql_ip)
        port = kwargs.get("port", sql_port)
        user = kwargs.get("user", sql_user)
        password = kwargs.get("password", sql_pass)
        print(f"Connecting to database {db} at {host}:{port} as user {user}")
        con = init_psql_connection(db, host, port, user, password)
        cur = con.cursor(cursor_factory=RealDictCursor)

        try:
            # Inject cursor into the decorated function
            result = func(cur, con, *args, **kwargs)
            return result
        finally:
            cur.close()
            con.close()

    return wrapper

#========================================#        ####
#==========# Record Functions #==========#        ####
#========================================#        ####

@init_psql_con_cursor
def get_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    column: str,
    value: str,
    host: str=sql_ip,
    port: int=sql_port,
    user: str=sql_user,
    password: str=sql_pass,
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
    host: str=sql_ip,
    port: int=sql_port,
    user: str=sql_user,
    password: str=sql_pass,
    ) -> list:
    """
    Query a postgreSQL table for a list of records matching the given values.
    Args:
        database (str) : Required, name of database to be queried
        schema (str) : Required, name of schema to be queried
        table (str) : Required, name of table to be queried
        column (str) : Required, column name to query by
        values (list) : Required, list of values to query by
    Returns:
        records (list) : List of RealDictCursor dictionaries.
    """
    records = []
    for value in values:
        query = f'SELECT * FROM "{schema}"."{table}" WHERE "{column}" = %s'
        cursor.execute(query, (value,))
        record = cursor.fetchone()
        records.append(record)
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
    host: str=sql_ip,
    port: int=sql_port,
    user: str=sql_user,
    password: str=sql_pass,
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
        record (list) : List of RealDictCursor dictionaries fetched with the 
            fetchall() method.
    """
    query = f'SELECT * FROM "{schema}"."{table}" WHERE "{column}" = %s'
    cursor.execute(query, (value,))
    records = cursor.fetchall()
    return records


@init_psql_con_cursor
def update_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    columns: list,
    values: list,
    on_conflict: str = [],
    relations: list = [],
 ) -> bool:  
    
    # Validate inputs
    if len(columns) != len(values):
        raise ValueError("Columns and values must have the same length.")
    for relation in relations:
        if not isinstance(relation, dict) or "related_table" not in relation or "related_uids" not in relation:
            raise ValueError("Each relation must be a dictionary with 'related_table' and 'related_uids' keys.")
        if not isinstance(relation["related_table"], str) or not isinstance(relation["related_uids"], list):
            raise ValueError("Invalid relation format. 'related_table' must be a string and 'related_uids' must be a list.")
        for uid in relation["related_uids"]:
            if not isinstance(uid, str):
                raise ValueError("Each UID in 'related_uids' must be a string.")
    
    columns_str = ", ".join([f'"{col}"' for col in columns])
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in columns])

    query = sql.SQL("""
        INSERT INTO {schema}.{table} ({columns})
        VALUES ({placeholders})
        ON CONFLICT ({conflict}) DO UPDATE SET
        {updates}
    """).format(
        schema=sql.Identifier(schema),
        table=sql.Identifier(table),
        columns=sql.SQL(', ').join(map(sql.Identifier, columns)),
        placeholders=sql.SQL(', ').join(sql.Placeholder() for _ in columns),
        conflict=sql.SQL(', ').join(map(sql.Identifier, on_conflict)) if on_conflict else sql.SQL('primary_key_id'),
        updates=sql.SQL(', ').join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
            for col in columns
        )
    )
    try:
        print(query)
        cursor.execute(query, values)
        connection.commit()
    except Exception as e:
        raise
    

@init_psql_con_cursor
def add_update_record(
    cursor,
    connection,
    database: str,
    schema: str,
    table: str,
    columns: list,
    values: list,
    relations: list = None,
) -> list | None:
    """
    OLD -- BEING REWORKED AS `update_record()`
    
    
    Adds or updates a record in a specified database table and manages related join table entries.
    Parameters:
        database (str): The name of the database.
        schema (str): The schema where the target table resides.
        table (str): The name of the target table.
        columns (list): A list of column names to be inserted or updated.
        values (list): A list of values corresponding to the columns.
        relations (list, optional): A list of relation dictionaries, where each dictionary contains...
            - 'column_name' (str): The name of the column representing the relation.
            - 'notionID_from' (any): The primary key value of the current record.
            - 'UID_to' (list): A list of foreign key values to be related.
    Raises:
        psycopg2.errors.UndefinedColumn: If attempting to submit a record with a column
            that does not exist.
        psycopg2.OperationalError: If there is an operational error during query execution.
        ValueError: If a required join table cannot be found.
        psycopg2.errors.ForeignKeyViolation: If attempting to submit a join record with a
            foreign record that does not yet exist.
        Exception: For other SQL execution errors, such as duplicate column errors.
    Returns:
        []: If the operation is successful.
        list: A list of foreign key values that caused a foreign key violation, if applicable.
    Notes:
        - The function builds and executes an `INSERT ... ON CONFLICT` SQL query to add or update records.
        - It also manages relations by inserting entries into a join table if they do not already exist.
        - Errors are sent to a Discord bot for monitoring.
    """

    # Build SQL query to insert/update the primary record into the table
    conflict_target = "primary_key_id"

    query = sql.SQL("""
        INSERT INTO {schema}.{table} ({columns})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_target}) DO UPDATE SET
        {updates}
    """).format(
        schema=sql.Identifier(schema),
        table=sql.Identifier(table),
        columns=sql.SQL(', ').join(map(sql.Identifier, columns)),
        placeholders=sql.SQL(', ').join(sql.Placeholder() for _ in columns),
        conflict_target=sql.SQL(', ').join(map(sql.Identifier, conflict_target if isinstance(conflict_target, list) else [conflict_target])),
        updates=sql.SQL(', ').join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
            for col in columns
        )
    )
    try:
        cursor.execute(query, values)
        connection.commit()
    except psycopg2.errors.UndefinedColumn as e:
        error_message = f"""
## Error adding/updating SQL record:
```psycopg2.errors.UndefinedColumn: {e}```
        """
        connection.rollback()
        send_discord_warning(error_message, username="sql_helper.py")
        raise
    except psycopg2.OperationalError as e:
        error_message = f"""
## Error adding/updating SQL record:
```psycopg2.OperationalError: {e}```
        """
        connection.rollback()
        send_discord_warning(error_message, username="sql_helper.py")
        raise
    except IndexError as e:
        error_message = f"""
## Error adding/updating SQL record:
```IndexError: {e}
---
query_string: {query}
columns: {columns}
values: {values}
---
        """
        connection.rollback()
        raise IndexError(error_message)

    # Now need to add join data
    # Get join tables now so we only have to query once.
    join_schema = "Join"
    join_tables = get_tables(database='meno_db', schema=join_schema)
    print(f"Join tables: {join_tables}")
    
    # Iterate through each relation to add it to the join table.
    for relation in relations:
        join_table = ""
        relation_column = relation["column_name"]
        
        # Join table column key and value to add
        foreign_column = relation_column + "_id"
        prime_column = table + "_id"
        prime_value = relation["notionID_from"]
        foreign_values = relation["UID_to"]

        # Find join table name, start with custom regex string
        regex_string = f"^{schema}_{table}_{relation_column}_col-.*"
        matching_tables = [
            row
            for row in join_tables
            if re.match(regex_string, row)
        ]
        join_table = matching_tables[0] if matching_tables else None
        
        # If regex fails, try the `find_table_name()` function.
        if not join_table:
            join_table = find_table_name(
                f"{schema}_{table}_{relation_column}_col",
                [row for row in join_tables],
            )
            
            # If that fails too, send error message to discord.
            if not join_table:
                error_message = f"""
## Error adding/updating SQL record:
```Join table not found for {schema}.{table} and column {foreign_column}:
query_string: {query}
regex_string: {regex_string}
join_tables: {join_tables}
matching_tables: {matching_tables}
relation_column: {relation_column}
foreign_column: {foreign_column}
prime_column: {prime_column}
prime_value: {prime_value}
foreign_values: {foreign_values}
```
                """
                send_discord_warning(error_message, username="sql_helper.py")
                raise ValueError(error_message)

        # If table is found, iterate through each relation ID to add it to join table
        missing_fv = []
        for foreign_value in foreign_values:
            # Check if the relation already exists. The join tables DO NOT have unique
            # constraints, so this is to avoid duplicates.
            query = f"""
            SELECT 1 FROM \"{join_schema}\".\"{join_table}\"
            WHERE \"{prime_column}\" = %s AND \"{foreign_column}\" = %s
            """
            
            # Execute the join record search query
            try:
                cursor.execute(query, (prime_value, foreign_value))
                result = cursor.fetchone()
            except psycopg2.OperationalError as e:
                error_message = f"""
## Error adding/updating SQL record:
```Operational error: {e}
---
query_string: {query}
regex_string: {regex_string}
join_tables: {join_tables}
matching_tables: {matching_tables}
relation_column: {relation_column}
foreign_column: {foreign_column}
prime_column: {prime_column}
prime_value: {prime_value}
foreign_values: {foreign_values}```
                """
                connection.rollback()
                send_discord_warning(error_message, username="sql_helper.py")
                raise
            # If it exists, skip the insert so there's no duplicate
            if result:
                continue

            # If it doesn't exist, insert the new relation
            query = f"""
            INSERT INTO \"{join_schema}\".\"{join_table}\" (\"{prime_column}\", \"{foreign_column}\")
            VALUES (%s, %s)
            """            
            try:
                cursor.execute(query, (prime_value, foreign_value))
                connection.commit()

            # On ForeignKeyViolation, rollback and continue
            except psycopg2.errors.ForeignKeyViolation as e:
                connection.rollback()
                missing_fv.append(foreign_value)
                continue

            # Catch any other error, send a notification to Discord and raise error.
            except psycopg2.OperationalError as e:
                error_message = f"""
## Error adding/updating SQL record:
```Operational error: {e}```
                """
                connection.rollback()
                send_discord_warning(error_message, username="MenoApi_SQL_Bot")
                raise
            
            except psycopg2.errors.DuplicateColumn as e:
                error_message = f"""
## Error adding/updating SQL record:
```Duplicate column error: {e}```
                """
                connection.rollback()
                send_discord_warning(error_message, username="MenoApi_SQL_Bot")
                raise
            
            except Exception as e:
                error_message = f"""
## Error adding/updating SQL record:
```Unexpected Error: {e}```
                """
                connection.rollback()
                send_discord_warning(error_message, username="MenoApi_SQL_Bot")
                raise

    # Return missing foreign values if any.
    return missing_fv

#=======================================#   ################
#==========# Table functions #==========#    #            #
#=======================================#    #            #

@init_psql_con_cursor
def get_tables(
    cursor,
    connection,
    database: str,
    schema: str,
    host: str=sql_ip,
    port: int=sql_port,
    user: str=sql_user,
    password: str=sql_pass,
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

#==========================================#      #  # ### #
#===========# Utility functions #==========#      #  #  #  #
#==========================================#      ####  #  ###

def map_notion_type_to_sql(notion_property: dict) -> str:
    """
    Maps Notion property types to SQL data types.
    Args:
        notion_type (str): The Notion property.
    Returns:
        str: The corresponding SQL data type.
    """
    notion_to_sql_map = {
        'title': 'VARCHAR(255)',
        'rich_text': 'TEXT',
        'number': 'FLOAT',
        'select': 'VARCHAR(255)',
        'multi_select': 'TEXT[]',
        'date': 'TIMESTAMP',
        'people': 'TEXT[]',
        'files': 'TEXT[]',
        'checkbox': 'BOOLEAN',
        'url': 'TEXT',
        'email': 'VARCHAR(255)',
        'phone_number': 'VARCHAR(255)',
        'formula': 'TEXT',
        'relation': None, # 'Relation' type will be handled separately
        'array': 'TEXT[]',
        'incomplete': 'TEXT',
        'unsupported': 'TEXT',
        'created_time': 'TIMESTAMP',
        'created_by': 'TEXT',
        'last_edited_time': 'TIMESTAMP',
        'last_edited_by': 'TEXT'
    }
    prop_type = notion_property.get('type')
    if prop_type == 'rollup':
        prop_type = notion_property.get('rollup', {}).get('type')

    return notion_to_sql_map.get(prop_type, 'TEXT')
    
    
def parse_notion_page_for_sql(page: dict, notion: object) -> tuple:
    """
    Parses a Notion page object and extracts SQL-compatible columns, values,
    and relations.
    Args:
        page (dict): A dictionary representing a Notion page, containing its
            properties and metadata.
        notion (object): An object providing a method `return_property_value`
            to extract property values from the Notion page.
    Returns:
        tuple: A tuple containing:
            - columns (list): A list of column names derived from the page's
              properties, sanitized for SQL compatibility.
            - values (list): A list of corresponding values for the columns.
            - relations (list): A list of dictionaries representing relations,
              where each dictionary contains:
                - 'column_name': The name of the relation column.
                - 'notionID_from': The ID of the current Notion page.
                - 'UID_to': A list of related Notion page IDs.
    """
    non_null_props = ["created_time", "last_edited_time", "date", "number", "checkbox"]

    columns = []
    values = []
    relations = []

    uid = page.get("id")
    props = page.get("properties", {})

    for prop_name, prop_value in props.items():
        regex = "[^[:ascii:]]|\\'|\\\""
        clean_prop_name = re.sub(regex, "", prop_name).strip().replace(" ", "_")
        clean_prop_value = notion.return_property_value(prop_value, uid)
        prop_type = prop_value.get("type")

        if prop_type == "title":
            clean_prop_value = clean_prop_value[:255]
        elif prop_type == "relation":
            if not clean_prop_value:
                clean_prop_value = []
            relation_dict = {
                "column_name": clean_prop_name,
                "notionID_from": uid,
                "UID_to": clean_prop_value,
            }
            relations.append(relation_dict)
            continue
        elif prop_type not in non_null_props and clean_prop_value is None:
            clean_prop_value = ""

        columns.append(clean_prop_name)
        values.append(clean_prop_value)

    columns.append("primary_key_id")
    values.append(uid)
    return columns, values, relations
