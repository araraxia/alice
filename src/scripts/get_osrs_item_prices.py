#!/opt/alice/.venv/bin/python3

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # alice/
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.util.independant_logger import Logger
from src.util.sql_helper import (
    init_psql_connection,
    create_cursor,
    add_update_record,
    ensure_table_exists,
    guess_column_type,
    add_pk_constraint,
)
from src.osrs.get_item_data import WikiDataGetter
from functools import wraps
from datetime import datetime

log = Logger(
    log_name="PriceOSRSItems",
    log_dir=ROOT_DIR / "logs",
    log_file="price_osrs_items.log",
).get_logger()
DB_NAME = "osrs"
SCHEMA_NAME = "prices"
PK = "timestamp"

wiki_getter = WikiDataGetter()


def init_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = init_psql_connection(db=DB_NAME)
        if not conn:
            log.error("Failed to establish database connection.")
            return
        cursor = create_cursor(conn)
        if not cursor:
            log.error("Failed to create database cursor.")
            conn.close()
            return
        try:
            return func(conn, cursor, *args, **kwargs)
        finally:
            cursor.close()
            conn.close()

    return wrapper


def create_data_columns(records: dict) -> dict:
    """
    Creates data columns from the provided records by inferring the column types.
    Args:
        records (list[dict]): List of records to analyze for column creation.
    Returns:
        dict: A dictionary with column names as keys and their inferred types as values.
    """
    log.info("Creating data columns from records.")
    if not records:
        log.error("No records provided to create_data_columns.")
        return {}

    columns = [{"name": PK, "type": "INTEGER"}]
    recorded_keys = [PK]
    for item_id, record in records.items():
        for key, value in record.items():
            if key not in recorded_keys:
                col_type = guess_column_type(value)
                column_kit = {"name": key, "type": col_type}
                columns.append(column_kit)
                recorded_keys.append(key)
    log.info(f"Found columns from records: {columns}")
    return columns


def validate_tables(conn, cursor, columns: dict, records: dict) -> bool:
    validated_tables = []
    invalid_tables = []
    for record_id, record in records.items():
        table_name = str(record_id)
        log.info(f"Validating table structure for {table_name}.")
        validated = ensure_table_exists(
            cursor=cursor,
            connection=conn,
            database=DB_NAME,
            log=log,
            schema_name=SCHEMA_NAME,
            table_name=table_name,
            columns=columns,
        )
        if not validated:
            invalid_tables.append(table_name)
            log.error(f"Failed to validate table structure for {table_name}.")
            continue

        validated = add_pk_constraint(
            cursor=cursor,
            connection=conn,
            database=DB_NAME,
            schema_name=SCHEMA_NAME,
            table_name=table_name,
            pk_column=PK,
        )
        if not validated:
            invalid_tables.append(table_name)
            log.error(f"Failed to validate table structure for (table_name).")
            continue
        validated_tables.append(table_name)
        continue

    return validated_tables, invalid_tables


def get_latest_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="latest_prices")


def get_5min_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="5min_prices")


def get_1hr_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="1hr_prices")


@init_connection
def update_latest_prices(*args, **kwargs):
    conn = args[0]
    cursor = args[1]
    response = get_latest_prices()
    records = response.get("data", {})
    log.info("Updating latest prices.")
    if not records:
        log.warning("No records to update for latest prices.")
        return

    now = datetime.now()

    columns = create_data_columns(records)
    if not columns:
        log.error("Failed to create columns for latest prices.")
        return

    valid_tables, failed_tables = validate_tables(
        conn=conn, cursor=cursor, columns=columns, records=records
    )
    if failed_tables:
        log.error(f"Failed to validate tables: {failed_tables}")
        return

    for item_id, record in records.items():
        column_names, column_values = [], []
        for key, value in record.items():
            column_names.append(str(key))
            column_values.append(value)
        if not column_names or not column_values:
            continue
        if len(column_names) != len(column_values):
            log.error(
                "Column names and values not equal length for table: " + str(item_id)
            )
        add_update_record(
            cursor=cursor,
            connection=conn,
            database=DB_NAME,
            schema=SCHEMA_NAME,
            table=str(item_id),
            columns=column_names,
            values=column_values,
            conflict_target=PK,
        )
    log.info("Latest prices updated successfully.")


def main():
    log.info("Starting OSRS item price update script.")
    update_latest_prices()


if __name__ == "__main__":
    main()
