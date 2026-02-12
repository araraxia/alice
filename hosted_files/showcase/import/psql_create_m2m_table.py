#!/usr/bin/env python3
# Script to create many-to-many join tables in PostgreSQL
# Aria Corona - 2025/12/18

from pathlib import Path
FILE_PATH = Path(__file__).resolve()
ROOT_PATH = FILE_PATH.parent.parent.parent

import sys
from psycopg2.errors import DuplicateColumn
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import psycopg2

DEFAULT_DB = "meno_prod_mgmt"
DEFAULT_JOIN_SCHEMA = "join_tables"

DEFAULT_SCHEMA_1 = "sale_order"
DEFAULT_TABLE_1 = "active_line_item"
DEFAULT_PK_NAME_1 = "pk_uuid"

DEFAULT_SCHEMA_2 = "sale_order"
DEFAULT_TABLE_2 = "active_production_part"
DEFAULT_PK_NAME_2 = "pk_uuid"


def load_creds(cred_path):
    import json
    with open(cred_path, 'r') as f:
        creds = json.load(f)
    return creds

def connect_to_database(database_name, cred_path=None):
    if not cred_path:
        cred_path = ROOT_PATH / "cred" / "psql.json"
    creds = load_creds(cred_path)
    
    print(f"Connecting to database '{database_name}'...")
    try:
        connection = psycopg2.connect(
            dbname=database_name,
            user=creds['user'],
            password=creds['password'],
            host=creds['ip'],
            port=creds['port']
        )
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    print(f"Connected to database '{database_name}'.")
    return cursor, connection

def schema_exists(cursor, schema_name):
    """Check if a schema exists in the database."""
    query = sql.SQL("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name = %s
    """)
    cursor.execute(query, (schema_name,))
    return cursor.fetchone() is not None

def create_schema_if_not_exists(cursor, connection, schema_name):
    """Create schema if it doesn't exist."""
    if not schema_exists(cursor, schema_name):
        print(f"Schema '{schema_name}' does not exist. Creating...")
        query = sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name))
        cursor.execute(query)
        connection.commit()
        print(f"Schema '{schema_name}' created successfully.")
        return True
    return False

def table_exists(cursor, schema_name, table_name):
    """Check if a table exists in the specified schema."""
    query = sql.SQL("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
    """)
    cursor.execute(query, (schema_name, table_name))
    return cursor.fetchone() is not None

def column_exists(cursor, schema_name, table_name, column_name):
    """Check if a column exists in the specified table."""
    query = sql.SQL("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """)
    cursor.execute(query, (schema_name, table_name, column_name))
    return cursor.fetchone() is not None

def get_column_type(cursor, schema_name, table_name, column_name):
    """Get the data type of a column."""
    query = sql.SQL("""
        SELECT data_type, udt_name
        FROM information_schema.columns 
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """)
    cursor.execute(query, (schema_name, table_name, column_name))
    result = cursor.fetchone()
    if result:
        return result['udt_name'] if result['data_type'] == 'USER-DEFINED' else result['data_type']
    return None

def has_primary_key_or_unique_constraint(cursor, schema_name, table_name, column_name):
    """Check if a column has a primary key or unique constraint."""
    query = sql.SQL("""
        SELECT tc.constraint_name, tc.constraint_type
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name 
            AND tc.table_schema = kcu.table_schema
            AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = %s 
            AND tc.table_name = %s 
            AND kcu.column_name = %s
            AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
    """)
    cursor.execute(query, (schema_name, table_name, column_name))
    return cursor.fetchone() is not None

def validate_tables_and_columns(cursor, table_1_schema, table_1_name, pk_name_1, 
                                table_2_schema, table_2_name, pk_name_2):
    """Validate that tables and columns exist and have proper constraints."""
    errors = []
    
    # Check table 1
    if not table_exists(cursor, table_1_schema, table_1_name):
        errors.append(f"Table '{table_1_schema}.{table_1_name}' does not exist.")
    else:
        if not column_exists(cursor, table_1_schema, table_1_name, pk_name_1):
            errors.append(f"Column '{pk_name_1}' does not exist in table '{table_1_schema}.{table_1_name}'.")
        elif not has_primary_key_or_unique_constraint(cursor, table_1_schema, table_1_name, pk_name_1):
            errors.append(f"Column '{pk_name_1}' in table '{table_1_schema}.{table_1_name}' does not have a PRIMARY KEY or UNIQUE constraint.")
    
    # Check table 2
    if not table_exists(cursor, table_2_schema, table_2_name):
        errors.append(f"Table '{table_2_schema}.{table_2_name}' does not exist.")
    else:
        if not column_exists(cursor, table_2_schema, table_2_name, pk_name_2):
            errors.append(f"Column '{pk_name_2}' does not exist in table '{table_2_schema}.{table_2_name}'.")
        elif not has_primary_key_or_unique_constraint(cursor, table_2_schema, table_2_name, pk_name_2):
            errors.append(f"Column '{pk_name_2}' in table '{table_2_schema}.{table_2_name}' does not have a PRIMARY KEY or UNIQUE constraint.")
    
    return errors

def prompt_dynamic():
    """Seperate function to loop for additional join tables."""
    # First table    
    table_1_schema = input(f"Enter the first table schema name (default: {DEFAULT_SCHEMA_1}): ").strip()
    if not table_1_schema:
        table_1_schema = DEFAULT_SCHEMA_1
    
    table_1_name = input(f"Enter the first table name (default: {DEFAULT_TABLE_1}): ").strip()
    if not table_1_name:
        table_1_name = DEFAULT_TABLE_1

    # Second table        
    table_2_schema = input(f"Enter the second table schema name (default: {DEFAULT_SCHEMA_2}): ").strip()
    if not table_2_schema:
        table_2_schema = DEFAULT_SCHEMA_2
    
    table_2_name = input(f"Enter the second table name (default: {DEFAULT_TABLE_2}): ").strip()
    if not table_2_name:
        table_2_name = DEFAULT_TABLE_2

    # Determine default join table name
    if table_1_name < table_2_name:
        join_table_name = f"{table_1_name}.{table_2_name}:{table_2_name}.{table_1_name}"[:64]
    else:
        join_table_name = f"{table_2_name}.{table_1_name}:{table_1_name}.{table_2_name}"[:64]
    print(f"Join table will be created as: {join_table_name}")
    change_table_name = input("Is this correct? (y/N): ").strip().lower()
    if change_table_name == 'n':
        while True:
            join_table_name = input("Enter the full join table name (excluding the schema): ").strip()[:64]
            again = input(f"Join table name will be: `{join_table_name}` Is this correct? (Y/n): ").strip().lower()
            if again in ('y', ''):
                break

    # Change PK
    pk_name_1, pk_name_2 = DEFAULT_PK_NAME_1, DEFAULT_PK_NAME_2
    change_pk = input(f"Do you want to change the primary key names (default: {DEFAULT_PK_NAME_1} and {DEFAULT_PK_NAME_2})? (y/N): ").strip().lower()   
    if change_pk == 'y':
        while True:
            pk_name_1 = input(f"Enter the primary key name for the first table: ").strip()
            pk_name_2 = input(f"Enter the primary key name for the second table: ").strip()
            if not pk_name_1 or not pk_name_2:
                print("Primary key names cannot be empty. Please try again.")
            else:
                break
        
    return table_1_schema, table_1_name, pk_name_1, table_2_schema, table_2_name, pk_name_2, join_table_name

def prompt_user():
    cred_path = input("Enter the path to your DB credentials file (default: %PROJECT_ROOT%/cred/psql.json): ").strip()
    if not cred_path:
        cred_path = ROOT_PATH / "cred" / "psql.json"
    
    database_name = input(f"Enter the database name (default: {DEFAULT_DB}): ").strip()
    if not database_name:
        database_name = DEFAULT_DB
    
    join_schema_name = input(f"Enter the join table schema name (default: {DEFAULT_JOIN_SCHEMA}): ").strip()
    if not join_schema_name:
        join_schema_name = DEFAULT_JOIN_SCHEMA

    (table_1_schema, table_1_name, pk_name_1,
     table_2_schema, table_2_name, pk_name_2, join_table_name
     ) = prompt_dynamic()
    
    return (database_name, join_schema_name,
            table_1_schema, table_1_name,
            table_2_schema, table_2_name,
            pk_name_1, pk_name_2,
            join_table_name, cred_path)
    
def main():
    (database_name, join_schema_name,
     table_1_schema, table_1_name,
     table_2_schema, table_2_name,
     pk_name_1, pk_name_2,
     join_table_name, cred_path) = prompt_user()
    
    cursor, connection = connect_to_database(database_name, cred_path)
    
    try:
        while True:
            # Validate tables and columns
            print("\nValidating tables and columns...")
            errors = validate_tables_and_columns(cursor, table_1_schema, table_1_name, pk_name_1,
                                                 table_2_schema, table_2_name, pk_name_2)
            
            if errors:
                print("\nValidation failed:")
                for error in errors:
                    print(f"  - {error}")
                print("\nPlease fix these issues before creating the join table.")
                retry = input("\nDo you want to try again with different parameters? (y/N/[E]xit): ").strip().lower()
                if retry == 'y':
                    (table_1_schema, table_1_name, pk_name_1,
                     table_2_schema, table_2_name, pk_name_2, join_table_name
                    ) = prompt_dynamic()
                    continue
                elif retry == 'e':
                    print("Exiting.")
                    break
                else:
                    print("Retrying table creation with the same parameters.")
                    continue
            
            print("Validation successful.")
            
            # Get column types dynamically
            pk1_type = get_column_type(cursor, table_1_schema, table_1_name, pk_name_1)
            pk2_type = get_column_type(cursor, table_2_schema, table_2_name, pk_name_2)
            
            print(f"\nDetected column types:")
            print(f"  - {table_1_schema}.{table_1_name}.{pk_name_1}: {pk1_type}")
            print(f"  - {table_2_schema}.{table_2_name}.{pk_name_2}: {pk2_type}")
            
            # Ensure join schema exists
            create_schema_if_not_exists(cursor, connection, join_schema_name)
            
            # Check if join table already exists
            if table_exists(cursor, join_schema_name, join_table_name):
                print(f"\nWarning: Join table '{join_schema_name}.{join_table_name}' already exists.")
                overwrite = input("Do you want to drop and recreate it? (y/N): ").strip().lower()
                if overwrite == 'y':
                    drop_query = sql.SQL("DROP TABLE {}.{}").format(
                        sql.Identifier(join_schema_name),
                        sql.Identifier(join_table_name)
                    )
                    cursor.execute(drop_query)
                    connection.commit()
                    print(f"Dropped existing table '{join_schema_name}.{join_table_name}'.")
                else:
                    print("Skipping table creation.")
                    another = input("\nDo you want to create another join table? (y/N): ").strip().lower()
                    if another != 'y':
                        break
                    (table_1_schema, table_1_name, pk_name_1,
                     table_2_schema, table_2_name, pk_name_2, join_table_name
                    ) = prompt_dynamic()
                    continue
            
            pk1 = table_1_name + "_pk"
            pk2 = table_2_name + "_pk"
    
            print(f"\nCreating join table '{join_schema_name}.{join_table_name}'...")
            query = sql.SQL("""
            CREATE TABLE {join_schema}.{join_table} (
                {pk1} {pk1_type} NOT NULL,
                {pk2} {pk2_type} NOT NULL,
                PRIMARY KEY ({pk1}, {pk2}),
                FOREIGN KEY ({pk1}) REFERENCES {table1_schema}.{table1} ({ref_pk1}) ON DELETE CASCADE,
                FOREIGN KEY ({pk2}) REFERENCES {table2_schema}.{table2} ({ref_pk2}) ON DELETE CASCADE
            );
            """).format(
                join_schema=sql.Identifier(join_schema_name),
                join_table=sql.Identifier(join_table_name),
                pk1=sql.Identifier(pk1),
                pk2=sql.Identifier(pk2),
                pk1_type=sql.SQL(pk1_type.upper()),
                pk2_type=sql.SQL(pk2_type.upper()),
                table1_schema=sql.Identifier(table_1_schema),
                table1=sql.Identifier(table_1_name),
                ref_pk1=sql.Identifier(pk_name_1),
                table2_schema=sql.Identifier(table_2_schema),
                table2=sql.Identifier(table_2_name),
                ref_pk2=sql.Identifier(pk_name_2)
            )
            print("\nExecuting SQL:")
            print(query.as_string(connection))
            cursor.execute(query)
            connection.commit()
            print(f"Join table '{join_schema_name}.{join_table_name}' created successfully.")
            another = input("Do you want to create another join table? (y/N): ").strip().lower()
            if another != 'y':
                break
            (table_1_schema, table_1_name, pk_name_1,
             table_2_schema, table_2_name, pk_name_2, join_table_name
            ) = prompt_dynamic()
    except Exception as e:
        print(f"Error creating join table: {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()
        print("\nDatabase connection closed.")
        
if __name__ == "__main__":
    main()