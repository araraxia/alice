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
)
from src.osrs.get_item_data import WikiDataGetter

log = Logger(
    log_name="MapOSRSItems", log_dir=ROOT_DIR / "logs", log_file="map_osrs_items.log"
).get_logger()
DB_NAME = "osrs"
SCHEMA_NAME = "items"
TABLE_NAME = "map"
PK = "id"

wiki_getter = WikiDataGetter()


def get_map_data() -> list[dict]:
    return wiki_getter.get_data(endpoint="mapping")


def create_map_columns(records: list[dict]) -> dict:
    log.info("Creating map columns from records.")
    if not records:
        log.error("No records provided to create_map_columns.")
        return {}

    columns = []
    recorded_keys = set()
    for record in records:
        for key, value in record.items():
            if key not in recorded_keys and value:
                col_type = guess_column_type(value)
                column_kit = {"name": key, "type": col_type}
                columns.append(column_kit)
                recorded_keys.add(key)
    log.info(f"Found columns from records: {columns}")
    return columns


def validate_table(conn, cursor, columns: dict):
    log.info("Validating table structure.")
    validated = ensure_table_exists(
        cursor=cursor,
        connection=conn,
        database=DB_NAME,
        log=log,
        schema_name=SCHEMA_NAME,
        table_name=TABLE_NAME,
        columns=columns,
    )
    if validated:
        log.info("Table structure validated.")
    else:
        log.error("Failed to validate table structure.")
        raise Exception("Table validation failed.")


def add_records(conn, cursor, records: list[dict]):
    def _parse_record(_record: list[dict]) -> tuple[list, list]:
        _values = []
        _columns = []
        for _key, _value in _record.items():
            _columns.append(_key)
            _values.append(_value)
        return _values, _columns  
    
    log.info("Adding or updating records in the database.")
    for record in records:
        values, columns = _parse_record(record)
        add_update_record(
            cursor=cursor,
            connection=conn,
            database=DB_NAME,
            schema=SCHEMA_NAME,
            table=TABLE_NAME,
            columns=columns,
            values=values,
            conflict_target=PK,
        )
    log.info("All records processed.")


def main():
    log.info("Starting OSRS item mapping process.")
    conn = init_psql_connection(db=DB_NAME)
    cursor = create_cursor(connection=conn)
    try:
        records = get_map_data()
        if not records:
            log.error("No mapping data retrieved from WikiDataGetter.")
            return

        columns = create_map_columns(records)
        if not columns:
            log.error("No columns created from records.")
            return

        validate_table(
            conn=conn,
            cursor=cursor,
            columns=columns,
        )

        add_records(
            conn=conn,
            cursor=cursor,
            records=records,
        )
    finally:
        cursor.close()
        conn.close()
    log.info("OSRS item mapping process completed.")


if __name__ == "__main__":
    main()
