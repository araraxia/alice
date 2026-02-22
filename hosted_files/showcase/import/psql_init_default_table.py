#!/usr/bin/env python3
#
# Aria Corona - 2025/12/22

from pathlib import Path

FILE_PATH = Path(__file__).resolve()
ROOT_PATH = FILE_PATH.parent.parent.parent

import sys
from psycopg2.errors import DuplicateColumn
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import psycopg2

CREATED_AT_QUERY = """
ALTER TABLE {schema_name}.{table_name}
    ADD created_at TIMESTAMPTZ NOT NULL DEFAULT now();
"""

UPDATED_AT_QUERY = """
ALTER TABLE {schema_name}.{table_name}
    ADD updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
"""

CREATE_FUNCTION_QUERY = """
CREATE OR REPLACE FUNCTION {schema_name}.set_updated_at()
    RETURNS trigger as
$$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
end;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGER_QUERY = """
CREATE TRIGGER {trigger_name}
    BEFORE UPDATE
    ON {schema_name}.{table_name}
    FOR EACH ROW
EXECUTE FUNCTION {schema_name}.set_updated_at()
"""

CREATE_SEQUENCE_QUERY = """
CREATE SEQUENCE {sequence_name}
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
"""

CREATE_HRID_COLUMN_QUERY = """
ALTER TABLE {schema_name}.{table_name}
    ADD hrid INT UNIQUE DEFAULT nextval({sequence_name});
"""

ALTER_HRID_COLUMN_QUERY = """
ALTER TABLE {schema_name}.{table_name}
    ALTER COLUMN hrid SET DEFAULT nextval({sequence_name});
"""

SEQUENCE_OWNERSHIP_QUERY = """
ALTER SEQUENCE {sequence_name}
    OWNED BY {schema_name}.{table_name}.hrid;
"""

DEFAULT_DB = "meno_prod_mgmt"
DEFAULT_SCHEMA = "sale_order"


def prompt_user():
    cred_path = input(
        "Enter the path to your DB credentials file (default: %PROJECT_ROOT%/cred/psql.json): "
    ).strip()
    database_name = input(f"Enter the database name (default: {DEFAULT_DB}): ").strip()
    if not database_name:
        database_name = DEFAULT_DB
    schema_name = input(f"Enter the schema name (default: {DEFAULT_SCHEMA}): ").strip()
    if not schema_name:
        schema_name = DEFAULT_SCHEMA
    table_name = input("Enter the table name: ").strip()
    return database_name, schema_name, table_name


def load_creds(cred_path):
    import json

    with open(cred_path, "r") as f:
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
            user=creds["user"],
            password=creds["password"],
            host=creds["ip"],
            port=creds["port"],
        )
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    print(f"Connected to database '{database_name}'.")
    return cursor, connection


def table_exists(cursor, schema_name, table_name):
    """Check if a table exists in the specified schema."""
    query = sql.SQL(
        """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = %s
    """
    )
    cursor.execute(query, (schema_name, table_name))
    return cursor.fetchone() is not None


def create_table_if_not_exists(cursor, connection, schema_name, table_name):
    """Create a basic table with pk_uuid if it doesn't exist."""
    if table_exists(cursor, schema_name, table_name):
        print(f"Table '{schema_name}.{table_name}' already exists.")
        return True

    print(f"Table '{schema_name}.{table_name}' does not exist.")
    create = input("Do you want to create it? (Y/n): ").strip().lower()

    if create == "n":
        print("Skipping table creation.")
        return False

    try:
        print(f"Creating table '{schema_name}.{table_name}' with pk_uuid column...")
        query = sql.SQL(
            """
            CREATE TABLE {schema}.{table} (
                pk_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid()
            )
        """
        ).format(schema=sql.Identifier(schema_name), table=sql.Identifier(table_name))
        cursor.execute(query)
        connection.commit()
        print(f"Table '{schema_name}.{table_name}' created successfully.")
        return True
    except Exception as e:
        print(f"Error creating table: {e}")
        connection.rollback()
        return False


def create_created_at(cursor, connection, schema_name, table_name):
    try:
        print(f"Adding 'created_at' column to '{schema_name}.{table_name}'...")
        query = sql.SQL(CREATED_AT_QUERY).format(
            schema_name=sql.Identifier(schema_name),
            table_name=sql.Identifier(table_name),
        )
        cursor.execute(query)
        print("'created_at' column added successfully.")
    except DuplicateColumn:
        print(f"Column 'created_at' already exists in '{schema_name}.{table_name}'.")
        connection.rollback()
    except Exception as e:
        print(f"Error adding 'created_at' column: {e}")
        connection.rollback()
        import time

        time.sleep(2)


def create_updated_at(cursor, connection, schema_name, table_name):
    try:
        print(f"Adding 'updated_at' column to '{schema_name}.{table_name}'...")
        query = sql.SQL(UPDATED_AT_QUERY).format(
            schema_name=sql.Identifier(schema_name),
            table_name=sql.Identifier(table_name),
        )
        cursor.execute(query)
        print("'updated_at' column added successfully.")
    except DuplicateColumn:
        print(f"Column 'updated_at' already exists in '{schema_name}.{table_name}'.")
        connection.rollback()
    except Exception as e:
        print(f"Error adding 'updated_at' column: {e}")
        connection.rollback()
        import time

        time.sleep(2)
        sys.exit(1)


def create_trigger(cursor, connection, schema_name, table_name):
    try:
        print(f"Creating trigger for 'updated_at' on '{schema_name}.{table_name}'...")
        query = sql.SQL(CREATE_FUNCTION_QUERY).format(
            schema_name=sql.Identifier(schema_name)
        )
        cursor.execute(query)
        print("Function created successfully.")
        trigger_name = (
            f"{table_name.replace('.', '_').replace('-', '_')}_set_updated_at"
        )
        query = sql.SQL(CREATE_TRIGGER_QUERY).format(
            schema_name=sql.Identifier(schema_name),
            table_name=sql.Identifier(table_name),
            trigger_name=sql.Identifier(trigger_name),
        )
        cursor.execute(query)
        connection.commit()
        print("Trigger created successfully.")
    except Exception as e:
        print(f"Error creating trigger: {e}")
        connection.rollback()
        if "already exists" in str(e):
            print(f"Trigger already exists on '{schema_name}.{table_name}'.")
            return

        import time

        time.sleep(2)
        sys.exit(1)


def create_hrid_sequence(cursor, connection, schema_name, table_name):
    """Create a sequence for HRID (Human Readable ID) column."""
    sequence_name = f"{schema_name}.{table_name}_hrid_seq"
    try:
        print(f"Creating HRID sequence '{sequence_name}'...")
        query = sql.SQL(CREATE_SEQUENCE_QUERY).format(
            sequence_name=sql.Identifier(schema_name, f"{table_name}_hrid_seq"),
        )
        cursor.execute(query)
        connection.commit()
        print("HRID sequence created successfully.")
    except Exception as e:
        if "already exists" in str(e):
            print(f"HRID sequence '{sequence_name}' already exists.")
            connection.rollback()
        else:
            print(f"Error creating HRID sequence: {e}")
            connection.rollback()


def create_hrid_column(cursor, connection, schema_name, table_name):
    """Add HRID column to the table."""
    sequence_name = f"{schema_name}.{table_name}_hrid_seq"
    try:
        print(f"Adding 'hrid' column to '{schema_name}.{table_name}'...")
        query = sql.SQL(CREATE_HRID_COLUMN_QUERY).format(
            schema_name=sql.Identifier(schema_name),
            table_name=sql.Identifier(table_name),
            sequence_name=sql.SQL("'{}'").format(sql.SQL(sequence_name)),
        )
        cursor.execute(query)
        connection.commit()
        print("'hrid' column added successfully.")
    except DuplicateColumn:
        print(f"Column 'hrid' already exists in '{schema_name}.{table_name}'.")
        connection.rollback()
        # Try to set the default value if column exists
        try:
            print(f"Setting default value for existing 'hrid' column...")
            query = sql.SQL(ALTER_HRID_COLUMN_QUERY).format(
                schema_name=sql.Identifier(schema_name),
                table_name=sql.Identifier(table_name),
                sequence_name=sql.SQL("'{}'").format(sql.SQL(sequence_name)),
            )
            cursor.execute(query)
            connection.commit()
            print("Default value set for 'hrid' column.")
        except Exception as e:
            print(f"Error setting default for 'hrid' column: {e}")
            connection.rollback()
    except Exception as e:
        print(f"Error adding 'hrid' column: {e}")
        connection.rollback()


def set_sequence_ownership(cursor, connection, schema_name, table_name):
    """Set the sequence ownership to the hrid column."""
    sequence_name = f"{schema_name}.{table_name}_hrid_seq"
    try:
        print(f"Setting sequence ownership for '{sequence_name}'...")
        query = sql.SQL(SEQUENCE_OWNERSHIP_QUERY).format(
            sequence_name=sql.Identifier(schema_name, f"{table_name}_hrid_seq"),
            schema_name=sql.Identifier(schema_name),
            table_name=sql.Identifier(table_name),
        )
        cursor.execute(query)
        connection.commit()
        print("Sequence ownership set successfully.")
    except Exception as e:
        if "must have same owner" in str(e):
            print(
                f"Note: Sequence ownership could not be set (permission/owner mismatch). This is usually not critical."
            )
            connection.rollback()
        else:
            print(f"Error setting sequence ownership: {e}")
            connection.rollback()


def main():
    database_name, schema_name, table_name = prompt_user()
    cursor, connection = connect_to_database(database_name)
    try:
        while True:
            # Check if table exists and create if necessary
            if not create_table_if_not_exists(
                cursor, connection, schema_name, table_name
            ):
                print("Cannot proceed without a table. Exiting.")
                break

            # Add created_at and updated_at columns with trigger
            create_created_at(cursor, connection, schema_name, table_name)
            create_updated_at(cursor, connection, schema_name, table_name)
            create_trigger(cursor, connection, schema_name, table_name)

            # Add HRID sequence and column
            create_hrid_sequence(cursor, connection, schema_name, table_name)
            create_hrid_column(cursor, connection, schema_name, table_name)
            set_sequence_ownership(cursor, connection, schema_name, table_name)

            repeat = (
                input("\nDo you want to modify another table? (y/n): ").strip().lower()
            )
            if repeat != "y":
                break
            table_name = input("Enter the table name: ").strip()
    finally:
        cursor.close()
        connection.close()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()
    print("Exiting script.")
