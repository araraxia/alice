
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent # alice/
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

log = Logger(name="MapOSRSItems", log_file=ROOT_DIR / "logs" / "map_osrs_items.log")
DB_NAME = "osrs"
SCHEMA_NAME = "items"
TABLE_NAME = "map"
PK = "wiki_id"