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
import psycopg2.errors as psql_errors

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


def create_data_columns(records: dict) -> list[dict]:
    """
    Creates data columns from the provided records by inferring the column types.
    Args:
        records (dict): Dictionary of records to analyze for column creation.
    Returns:
        list[dict]: A dictionary with column names as keys and their inferred types as values.
    """
    log.info("Creating data columns from records.")
    if not records:
        log.error("No records provided to create_data_columns.")
        return [{}]

    columns = [{"name": PK, "type": "TIMESTAMP"}]
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


def validate_tables(
    conn, cursor, table_name_mod: str, columns: dict, records: dict
) -> tuple[list, list]:
    validated_tables = []
    invalid_tables = []
    table_name_list = [str(record_id)+table_name_mod for record_id in records.keys()]
    log.info(f"Validating table structure for {table_name_list}.")
    for record_id, record in records.items():
        table_name = str(record_id)+table_name_mod
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
            constraint_name=f"pk_{str(table_name)}_constraint",
        )
        if not validated:
            invalid_tables.append(table_name)
            log.error(f"Failed to validate table structure for (table_name).")
            continue
        validated_tables.append(table_name)
        continue

    log.info(f"Validation complete. Failed tables: {invalid_tables}")
    return validated_tables, invalid_tables


def update_records(conn, cursor, records: list[dict], table_name: str, **kwargs):
    name_mod = kwargs.get("name_mod", "")
    for record in records:
        now = datetime.now()
        column_names, column_values = [PK], [now]
        for key, value in record.items():
            column_names.append(str(key))
            column_values.append(value)
        if not column_names or not column_values:
            continue
        if len(column_names) != len(column_values):
            log.error(
                "Column names and values not equal length for table: " + table_name
            )
            continue
        try:
            add_update_record(
                cursor=cursor,
                connection=conn,
                database=DB_NAME,
                schema=SCHEMA_NAME,
                table=table_name,
                columns=column_names,
                values=column_values,
                conflict_target=PK,
            )
        except psql_errors.UndefinedTable as e:
            if not kwargs.get("retry", True):
                log.error(f"Table {table_name} does not exist and retry disabled: {e}")
                continue
            log.warning(f"Table {table_name} does not exist: {e}")
            retry_update_record(conn, cursor, record, table_name, name_mod)
        except psql_errors.UndefinedColumn as e:
            if not kwargs.get("retry", True):
                log.error(f"Column does not exist in {table_name}: {e}")
                continue
            log.warning(f"Column does not exist in {table_name}: {e}")
            retry_update_record(conn, cursor, record, table_name, name_mod)
        except Exception as e:
            log.error(f"Failed to add/update record in {table_name}: {e}")
            continue


def retry_update_record(conn, cursor, record, table_name, name_mod):
    item_id = table_name.rsplit("_", 1)
    temp_record = {item_id: record}
    columns = create_data_columns(temp_record)
    if not columns:
        log.error(f"Failed to create columns for {item_id}.")
        return
    
    valid_tables, failed_tables = validate_tables(
        conn=conn,
        cursor=cursor,
        table_name_mod=name_mod,
        columns=columns,
        records=temp_record,
    )
    if failed_tables:
        log.error(f"Failed to create table for {item_id}: {failed_tables}")
        return
    log.info(f"Retrying to add record for {item_id} after creating table.")
    update_records(conn, cursor, [record], table_name, retry=False)


def get_latest_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="latest_prices")


def get_5min_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="5min_prices")


def get_1hr_prices() -> list[dict]:
    return wiki_getter.get_data(endpoint="1h_prices")


@init_connection
def update_prices(*args, **kwargs):
    conn = args[0]
    cursor = args[1]
    no_validate = kwargs.get("no_validate", False)

    get_map = {
        "update_latest_prices": get_latest_prices,
        "update_5min_prices": get_5min_prices,
        "update_1h_prices": get_1hr_prices,
    }

    table_mod_map = {
        "update_latest_prices": "_latest",
        "update_5min_prices": "_5min",
        "update_1h_prices": "_1h",
    }

    for update_key, update_func in get_map.items():
        if not kwargs.get(update_key, False):
            log.info(f"Skipping {update_key} as per arguments.")
            continue
        response = update_func()
        records = response.get("data", {})
        log.info(f"Updating {update_key}.")
        if not records:
            log.warning(f"No records to update for {update_key}.")
            continue

        # Validate tables if needed
        if not no_validate:
            log.info(f"Validating tables for {update_key}.")
            columns = create_data_columns(records)
            if not columns:
                log.error(f"Failed to create columns for {update_key}.")
                continue

            valid_tables, failed_tables = validate_tables(
                conn=conn,
                cursor=cursor,
                table_name_mod=table_mod_map[update_key],
                columns=columns,
                records=records,
            )
            if failed_tables:
                log.error(f"Failed to validate tables: {failed_tables}")
                continue

        log.info(f"Updating records for {update_key}.")
        for item_id, record in records.items():
            table_name = str(item_id) + table_mod_map[update_key]
            try:
                update_records(
                    conn=conn,
                    cursor=cursor,
                    records=[record],
                    table_name=table_name,
                    name_mod=table_mod_map[update_key],
                )
            except Exception as e:
                log.error(f"Failed to update {update_key} for {item_id}: {e}")
                continue
        log.info(f"{update_key} updated successfully.")


def argsparser():
    import argparse

    parser = argparse.ArgumentParser(
        description="Update OSRS item prices in the database."
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip table validation before updating prices.",
        default=False,
    )
    parser.add_argument(
        "--update-latest-prices",
        action="store_true",
        help="Update latest prices.",
        default=False,
    )
    parser.add_argument(
        "--update-5min-prices",
        action="store_true",
        help="Update 5 minute prices.",
        default=False,
    )
    parser.add_argument(
        "--update-1h-prices",
        action="store_true",
        help="Update 1 hour prices.",
        default=False,
    )

    return parser.parse_args()


def main():
    args = argsparser()
    log.info("Starting OSRS item price update script.")
    update_prices(
        no_validate=args.no_validate,
        update_latest_prices=args.update_latest_prices,
        update_5min_prices=args.update_5min_prices,
        update_1h_prices=args.update_1h_prices,
    )


if __name__ == "__main__":
    main()
