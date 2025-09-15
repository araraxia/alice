from dataclasses import dataclass
from src.util.sql_helper import get_record, get_all_records, init_psql_connection, create_cursor
from datetime import datetime

DB_NAME = "osrs"
MAP_PK = "id"
MAP_SCHEMA = "items"
MAP_TABLE = "map"
PRICE_SCHEMA = "prices"
PRICE_PK = "timestamp"

@dataclass
class osrsItemProperties:
    # Required    
    item_id: int

    # Optional    
    name: str=None
    examine: str=None
    members: bool=None
    icon: str=None
    limit: int=None
    value: int=None
    highalch: int=None
    lowalch: int=None

    latest_price: int=None
    latest_price_high: int=None
    latest_price_low: int=None

    latest_5min_price: int=None
    latest_5min_price_high: int=None
    latest_5min_volume_high: int=None
    latest_5min_price_low: int=None
    latest_5min_volume_low: int=None

    latest_1h_price: int=None
    latest_1h_price_high: int=None
    latest_1h_volume_high: int=None
    latest_1h_price_low: int=None
    latest_1h_volume_low: int=None

    """
    To-Do:

    Pulling all rows then max-ing is wasteful. Prefer server-side:
    SELECT ... FROM schema.table ORDER BY timestamp DESC LIMIT 1 Or add a helper get_latest_record(...).
    """

    def init_conn_cursor(self):
        self.conn = init_psql_connection(db=DB_NAME)
        self.cursor = create_cursor(self.conn)
        
    def destroy_conn_cursor(self):
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def load_stored_data(self):
        if not hasattr(self, 'conn') or not hasattr(self, 'cursor'):
            self.init_conn_cursor()
        
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
            
    def get_latest_latest_price(self):
        if not hasattr(self, 'conn') or not hasattr(self, 'cursor'):
            self.init_conn_cursor()
        latest_prices = get_all_records(
            cursor=self.cursor,
            connection=self.conn,
            database=DB_NAME,
            schema=PRICE_SCHEMA,
            table=f"{str(self.item_id)}_latest",
        )
        if latest_prices:
            recent_record = max(latest_prices, key=lambda x: x.get("timestamp") or datetime.min)
            self.latest_price_high = recent_record.get("high") or 0
            self.latest_price_low = recent_record.get("low") or 0
            # Eliminate large variations if only one price is available
            if self.latest_price_high and self.latest_price_low:
                self.latest_price = (self.latest_price_high + self.latest_price_low) // 2
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

    def get_latest_5min_price(self):
        if not hasattr(self, 'conn') or not hasattr(self, 'cursor'):
            self.init_conn_cursor()
        prices_5min = get_all_records(
            cursor=self.cursor,
            connection=self.conn,
            database=DB_NAME,
            schema=PRICE_SCHEMA,
            table=f"{str(self.item_id)}_5min",
        )
        if prices_5min:
            recent_record = max(prices_5min, key=lambda x: x.get("timestamp", 0))
            self.latest_5min_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_5min_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_5min_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_5min_volume_low = recent_record.get("lowPriceVolume") or 0
            # Eliminate large variations if only one price is available
            if self.latest_5min_price_high and self.latest_5min_price_low:
                self.latest_5min_price = (self.latest_5min_price_high + self.latest_5min_price_low) // 2
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

    def get_latest_1h_price(self):
        if not hasattr(self, 'conn') or not hasattr(self, 'cursor'):
            self.init_conn_cursor()
        prices_1h = get_all_records(
            cursor=self.cursor,
            connection=self.conn,
            database=DB_NAME,
            schema=PRICE_SCHEMA,
            table=f"{str(self.item_id)}_1h",
        )
        if prices_1h:
            recent_record = max(prices_1h, key=lambda x: x.get("timestamp", 0))
            self.latest_1h_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_1h_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_1h_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_1h_volume_low = recent_record.get("lowPriceVolume") or 0
            # Eliminate large variations if only one price is available
            if self.latest_1h_price_high and self.latest_1h_price_low:
                self.latest_1h_price = (self.latest_1h_price_high + self.latest_1h_price_low) // 2
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