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
    def wrapper(self: "osrsItemProperties", *args, **kwargs):
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
        print(f"🏗️ Initializing osrsItemProperties for item_id: {item_id}")
        self.item_id = item_id

        self.name: str = None
        self.examine: str = None
        self.members: bool = None
        self.icon: str = None
        self.limit: int = None
        self.value: int = None
        self.highalch: int = None
        self.lowalch: int = None

        self.latest_price_high: int = None
        self.latest_timestamp_high: int = None
        self.latest_price_low: int = None
        self.latest_timestamp_low: int = None
        self.latest_price_average: float = None
        self.latest_3x_price_high: float = None
        self.latest_3x_timestamp_high: float = None
        self.latest_3x_price_low: float = None
        self.latest_3x_timestamp_low: float = None
        self.latest_3x_price_average: float = None
        

        self.latest_5min_price_high: int = None
        self.latest_5min_price_low: int = None
        self.latest_5min_price_average: float = None
        self.latest_5min_volume_high: int = None
        self.latest_5min_volume_low: int = None
        self.latest_5min_volume_average: float = None
        self.latest_5min_timestamp: float = None
        self.latest_15min_price_high: float = None
        self.latest_15min_price_low: float = None
        self.latest_15min_price_average: float = None
        self.latest_15min_volume_high: float = None
        self.latest_15min_volume_low: float = None
        self.latest_15min_volume_average: float = None
        self.latest_15min_timestamp: float = None

        self.latest_1h_price_high: int = None
        self.latest_1h_price_low: int = None
        self.latest_1h_price_average: float = None
        self.latest_1h_volume_high: int = None
        self.latest_1h_volume_low: int = None
        self.latest_1h_volume_average: float = None
        self.latest_1h_timestamp: float = None
        self.latest_3h_price_high: float = None
        self.latest_3h_price_low: float = None
        self.latest_3h_price_average: float = None
        self.latest_3h_volume_high: float = None
        self.latest_3h_volume_low: float = None
        self.latest_3h_volume_average: float = None
        self.latest_3h_timestamp: float = None

        self.load_stored_data()
        print(f"✅ Finished initializing {getattr(self, 'name', f'item_{item_id}')}")
        print(
            f"📊 Final data - 5m vol: {self.latest_5min_volume_low}, 1h vol: {self.latest_1h_volume_low}"
        )
        print(
            f"💰 Final prices - 5m: {self.latest_5min_price_low}, 1h: {self.latest_1h_price_low}"
        )

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
        print(f"🔍 Loading stored data for item {self.item_id}")

        if not self.item_id:
            print(f"❌ No item_id provided, skipping data load")
            return None

        print(f"📋 Fetching item map from {MAP_SCHEMA}.{MAP_TABLE}")
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
            print(f"❌ No item map found for item_id {self.item_id}")
            return None

        print(f"✅ Found item map: {dict(item_map)}")
        for key, value in item_map.items():
            setattr(self, key, value)

        print(f"📈 Loading price data...")
        self.get_latest_latest_price()
        self.get_latest_5min_price()
        self.get_latest_1h_price()

    @manage_conn_cursor
    def get_latest_latest_price(self):
        table_name = f"{str(self.item_id)}_latest"
        print(f"💰 Fetching latest price from {PRICE_SCHEMA}.{table_name}")

        try:
            latest_price = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PRICE_PK,
                limit=3,
            )
            print(f"✅ Latest price query successful, records: {len(latest_price)}")
        except UndefinedTable:
            print(f"⚠️ Table {PRICE_SCHEMA}.{table_name} does not exist")
            self.conn.rollback()
            latest_price = []
        except Exception as e:
            print(f"❌ Error fetching latest price: {e}")
            self.conn.rollback()
            latest_price = []

        if latest_price:
            recent_record = latest_price[0]

            print(f"📊 Latest price record: {dict(recent_record)}")

            self.latest_price_high = recent_record.get("high") or 0
            self.latest_price_low = recent_record.get("low") or 0
            self.latest_timestamp_high = recent_record.get("highTime", 0) # Unix timestamp in ms
            self.latest_timestamp_low = recent_record.get("lowTime", 0) # Unix timestamp
            self.latest_price_average = self.average_price(
                [self.latest_price_high, self.latest_price_low]
            )

            self.latest_3x_price_high = self.average_price(
                prices=[r.get("high") or 0 for r in latest_price]
            )
            self.latest_3x_timestamp_high = max(r.get("highTime", 0) for r in latest_price) # Unix timestamp in ms
            self.latest_3x_price_low = self.average_price(
                prices=[r.get("low") or 0 for r in latest_price]
            )
            self.latest_3x_timestamp_low = min(r.get("lowTime", 0) for r in latest_price) # Unix timestamp
            self.latest_3x_price_average = self.average_price(
                [self.latest_3x_price_high, self.latest_3x_price_low]
            )

            print(
                f"💰 Set latest prices - high: {self.latest_price_high}, low: {self.latest_price_low}, avg: {self.latest_price_average}"
            )
        else:
            print(f"❌ No latest price data found")
            self.latest_price_average = 0
            self.latest_price_high = 0
            self.latest_price_low = 0
            self.latest_3x_price_high = 0
            self.latest_3x_price_low = 0
            self.latest_3x_price_average = 0

    @manage_conn_cursor
    def get_latest_5min_price(self):
        table_name = f"{str(self.item_id)}_5min"
        print(f"⏱️ Fetching 5min price from {PRICE_SCHEMA}.{table_name}")

        try:
            prices_5min = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PRICE_PK,
                limit=3,
            )
            print(f"✅ 5min price query successful, records: {len(prices_5min)}")
        except UndefinedTable:
            print(f"⚠️ Table {PRICE_SCHEMA}.{table_name} does not exist")
            self.conn.rollback()
            prices_5min = []
        except Exception as e:
            print(f"❌ Error fetching 5min price: {e}")
            self.conn.rollback()
            prices_5min = []

        if prices_5min:
            recent_record = prices_5min[0]

            print(f"📊 5min price record: {dict(recent_record)}")

            self.latest_5min_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_5min_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_5min_price_average = self.average_price(
                [self.latest_5min_price_high, self.latest_5min_price_low]
            )
            self.latest_5min_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_5min_volume_low = recent_record.get("lowPriceVolume") or 0
            self.latest_5min_volume_average = self.average_price(
                [self.latest_5min_volume_high, self.latest_5min_volume_low]
            )
            self.latest_5min_timestamp = recent_record.get("timestamp", 0) # Unix timestamp in ms

            self.latest_15min_price_high = self.average_price(
                prices=[r.get("avgHighPrice") or 0 for r in prices_5min]
            )
            self.latest_15min_price_low = self.average_price(
                prices=[r.get("avgLowPrice") or 0 for r in prices_5min]
            )
            self.latest_15min_price_average = self.average_price(
                [self.latest_15min_price_high, self.latest_15min_price_low]
            )
            self.latest_15min_volume_high = self.average_price(
                prices=[r.get("highPriceVolume") or 0 for r in prices_5min]
            )
            self.latest_15min_volume_low = self.average_price(
                prices=[r.get("lowPriceVolume") or 0 for r in prices_5min]
            )
            self.latest_15min_volume_average = self.average_price(
                [self.latest_15min_volume_high, self.latest_15min_volume_low]
            )
            self.latest_15min_timestamp = max(r.get("timestamp", 0) for r in prices_5min) # Unix timestamp in ms

            print(
                f"⏱️ Set 5min data - price_low: {self.latest_5min_price_low}, vol_low: {self.latest_5min_volume_low}"
            )
        else:
            print(f"❌ No 5min price data found")
            self.latest_5min_price_average = 0
            self.latest_5min_price_high = 0
            self.latest_5min_price_low = 0
            self.latest_5min_volume_average = 0
            self.latest_5min_volume_high = 0
            self.latest_5min_volume_low = 0
            self.latest_15min_price_high = 0
            self.latest_15min_price_low = 0
            self.latest_15min_price_average = 0
            self.latest_15min_volume_high = 0
            self.latest_15min_volume_low = 0
            self.latest_15min_volume_average = 0

    @manage_conn_cursor
    def get_latest_1h_price(self):
        table_name = f"{str(self.item_id)}_1h"
        print(f"🕐 Fetching 1h price from {PRICE_SCHEMA}.{table_name}")

        try:
            prices_1h = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PRICE_PK,
                limit=3,
            )
            print(f"✅ 1h price query successful, records: {len(prices_1h)}")
        except UndefinedTable:
            print(f"⚠️ Table {PRICE_SCHEMA}.{table_name} does not exist")
            self.conn.rollback()
            prices_1h = []
        except Exception as e:
            print(f"❌ Error fetching 1h price: {e}")
            self.conn.rollback()
            prices_1h = []

        if prices_1h:
            recent_record = prices_1h[0]

            print(f"📊 1h price record: {dict(recent_record)}")

            self.latest_1h_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_1h_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_1h_price_average = self.average_price(
                [self.latest_1h_price_high, self.latest_1h_price_low]
            )
            self.latest_1h_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_1h_volume_low = recent_record.get("lowPriceVolume") or 0
            self.latest_1h_volume_average = self.average_price(
                [self.latest_1h_price_high, self.latest_1h_price_low]
            )
            self.latest_1h_timestamp = recent_record.get("timestamp", 0) # Unix timestamp in ms

            self.latest_3h_price_high = self.average_price(
                prices=[r.get("avgHighPrice") or 0 for r in prices_1h]
            )
            self.latest_3h_price_low = self.average_price(
                prices=[r.get("avgLowPrice") or 0 for r in prices_1h]
            )
            self.latest_3h_price_average = self.average_price(
                [self.latest_3h_price_high, self.latest_3h_price_low]
            )
            self.latest_3h_volume_high = self.average_price(
                prices=[r.get("highPriceVolume") or 0 for r in prices_1h]
            )
            self.latest_3h_volume_low = self.average_price(
                prices=[r.get("lowPriceVolume") or 0 for r in prices_1h]
            )
            self.latest_3h_volume_average = self.average_price(
                [self.latest_3h_volume_high, self.latest_3h_volume_low]
            )
            self.latest_3h_timestamp = max(r.get("timestamp", 0) for r in prices_1h) # Unix timestamp in ms

        else:
            print(f"❌ No 1h price data found")
            self.latest_1h_price_average = 0
            self.latest_1h_price_high = 0
            self.latest_1h_price_low = 0
            self.latest_1h_volume_average = 0
            self.latest_1h_volume_high = 0
            self.latest_1h_volume_low = 0
            self.latest_3h_price_high = 0
            self.latest_3h_price_low = 0
            self.latest_3h_price_average = 0
            self.latest_3h_volume_high = 0
            self.latest_3h_volume_low = 0
            self.latest_3h_volume_average = 0

    def average_price(self, prices: list[int]) -> float:
        n = 0
        sum = 0
        for price in prices:
            if price:
                n += 1
                sum += price
        return sum / n if n > 0 else 0
