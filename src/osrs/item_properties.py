from src.util.sql_helper import (
    get_record,
    fetch_top,
    init_psql_connection,
    create_cursor,
)
from psycopg2.errors import UndefinedTable
from functools import wraps

DB_NAME = "osrs"
MAP_PK = "id"
MAP_SCHEMA = "items"
MAP_TABLE = "map"
PRICE_SCHEMA = "prices"
PRICE_PK = "timestamp"

def manage_conn_cursor(func):
    @wraps(func)
    def wrapper(self: osrsItemProperties, *args, **kwargs):
        if not hasattr(self, "conn") or not hasattr(self, "cursor"):
            self.init_conn_cursor()
        if self.conn.closed or self.cursor.closed:
            self.init_conn_cursor()
        try:
            result = func(self, *args, **kwargs)
        finally:
            self.destroy_conn_cursor()
        return result
    return wrapper

class osrsItemProperties:
    @manage_conn_cursor
    def __init__(self, item_id: int):
        self.item_id = item_id
        
        self.name: str = None
        self.examine: str = None
        self.members: bool = None
        self.icon: str = None
        self.limit: int = None
        self.value: int = None
        self.highalch: int = None
        self.lowalch: int = None

        self.latest_price: int = None
        self.latest_price_high: int = None
        self.latest_price_low: int = None

        self.latest_5min_price: int = None
        self.latest_5min_price_high: int = None
        self.latest_5min_volume_high: int = None
        self.latest_5min_price_low: int = None
        self.latest_5min_volume_low: int = None

        self.latest_1h_price: int = None
        self.latest_1h_price_high: int = None
        self.latest_1h_volume_high: int = None
        self.latest_1h_price_low: int = None
        self.latest_1h_volume_low: int = None

        self.load_stored_data()
    """
    To-Do:

    Pulling all rows then max-ing is wasteful. Prefer server-side:
    SELECT ... FROM schema.table ORDER BY timestamp DESC LIMIT 1 Or add a helper get_latest_record(...).
    """

    def init_conn_cursor(self):
        self.conn = init_psql_connection(db=DB_NAME)
        self.cursor = create_cursor(self.conn)


    def destroy_conn_cursor(self):
        if hasattr(self, "cursor"):
            self.cursor.close()
        if hasattr(self, "conn"):
            self.conn.close()

    @manage_conn_cursor
    def load_stored_data(self):
        if not self.item_id:
            return None

        item_map = get_record(
            cursor=self.cursor,
            connection=self.conn,
            database=DB_NAME,
            schema=MAP_SCHEMA,
            table=MAP_TABLE,
            column=MAP_PK,
            value=self.item_id,
        )

        if not item_map:
            return None

        for key, value in item_map.items():
            setattr(self, key, value)

        self.get_latest_latest_price()
        self.get_latest_5min_price()
        self.get_latest_1h_price()

    @manage_conn_cursor
    def get_latest_latest_price(self):
        try:
            latest_price = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema=PRICE_SCHEMA,
                table=f"{str(self.item_id)}_latest",
                order_by=PRICE_PK,
                limit=1,
            )
        except UndefinedTable:
            self.conn.rollback()
            latest_price = []
        except Exception:
            self.conn.rollback()
            latest_price = []

        if latest_price:
            recent_record = latest_price[0]
            self.latest_price_high = recent_record.get("high") or 0
            self.latest_price_low = recent_record.get("low") or 0
            # Eliminate large variations if only one price is available
            if self.latest_price_high and self.latest_price_low:
                self.latest_price = (
                    self.latest_price_high + self.latest_price_low
                ) // 2
            elif self.latest_price_high:
                self.latest_price = self.latest_price_high
            elif self.latest_price_low:
                self.latest_price = self.latest_price_low
            else:
                self.latest_price = 0
        else:
            self.latest_price = 0
            self.latest_price_high = 0
            self.latest_price_low = 0

    @manage_conn_cursor
    def get_latest_5min_price(self):
        try:
            prices_5min = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema=PRICE_SCHEMA,
                table=f"{str(self.item_id)}_5min",
                order_by=PRICE_PK,
                limit=1,
            )
        except UndefinedTable:
            self.conn.rollback()
            prices_5min = []
        except Exception:
            self.conn.rollback()
            prices_5min = []
            
        if prices_5min:
            recent_record = prices_5min[0]
            self.latest_5min_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_5min_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_5min_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_5min_volume_low = recent_record.get("lowPriceVolume") or 0
            # Eliminate large variations if only one price is available
            if self.latest_5min_price_high and self.latest_5min_price_low:
                self.latest_5min_price = (
                    self.latest_5min_price_high + self.latest_5min_price_low
                ) // 2
            elif self.latest_5min_price_high:
                self.latest_5min_price = self.latest_5min_price_high
            elif self.latest_5min_price_low:
                self.latest_5min_price = self.latest_5min_price_low
            else:
                self.latest_5min_price = 0
        else:
            self.latest_5min_price = 0
            self.latest_5min_price_high = 0
            self.latest_5min_price_low = 0
            self.latest_5min_volume_high = 0
            self.latest_5min_volume_low = 0

    @manage_conn_cursor
    def get_latest_1h_price(self):
        try:
            prices_1h = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema=PRICE_SCHEMA,
                table=f"{str(self.item_id)}_1h",
                order_by=PRICE_PK,
                limit=1,
            )
        except UndefinedTable:
            self.conn.rollback()
            prices_1h = []
        except Exception:
            self.conn.rollback()
            prices_1h = []

        if prices_1h:
            recent_record = prices_1h[0]
            self.latest_1h_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_1h_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_1h_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_1h_volume_low = recent_record.get("lowPriceVolume") or 0
            # Eliminate large variations if only one price is available
            if self.latest_1h_price_high and self.latest_1h_price_low:
                self.latest_1h_price = (
                    self.latest_1h_price_high + self.latest_1h_price_low
                ) // 2
            elif self.latest_1h_price_high:
                self.latest_1h_price = self.latest_1h_price_high
            elif self.latest_1h_price_low:
                self.latest_1h_price = self.latest_1h_price_low
            else:
                self.latest_1h_price = 0
        else:
            self.latest_1h_price = 0
            self.latest_1h_price_high = 0
            self.latest_1h_price_low = 0
            self.latest_1h_volume_high = 0
            self.latest_1h_volume_low = 0
