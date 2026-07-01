from src.util.sql_helper import (
    get_record,
    fetch_top,
    init_psql_connection,
    create_cursor,
    get_filtered_records
)
from src.util.independant_logger import Logger
from psycopg2.errors import UndefinedTable
from functools import wraps
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64

DB_NAME = "osrs"
MAP_PK = "id"
MAP_SCHEMA = "items"
MAP_TABLE = "map"
PRICE_SCHEMA = "prices"
PK_COLUMN = "timestamp"
logger = Logger(
    log_name="item_properties_logger",
    log_file="item_properties.log",
    log_level=10,
    file_level=20,
    console_level=10,
).get_logger()

def prepare_datetime_for_timestamp_column(date_input):
    """
    Prepare a datetime for PostgreSQL timestamp column queries.

    Converts various date input formats to a datetime object that can be used
    with PostgreSQL's timestamp columns (timestamp without time zone).

    Args:
        date_input: datetime object, Unix timestamp (int/float in seconds or ms),
                   ISO format string, or None

    Returns:
        datetime: A datetime object ready for psycopg2 timestamp column queries

    Examples:
        >>> dt = datetime(2024, 1, 1, 12, 0, 0)
        >>> prepare_datetime_for_timestamp_column(dt)
        datetime.datetime(2024, 1, 1, 12, 0, 0)

        >>> prepare_datetime_for_timestamp_column(1704110400000)  # milliseconds
        datetime.datetime(2024, 1, 1, 12, 0, 0)

        >>> prepare_datetime_for_timestamp_column("2024-01-01T12:00:00")
        datetime.datetime(2024, 1, 1, 12, 0, 0)
    """
    if date_input is None:
        return None
    elif isinstance(date_input, datetime):
        return date_input
    elif isinstance(date_input, str):
        try:
            # Try parsing ISO format
            return datetime.fromisoformat(date_input.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid date string format: {date_input}")
    elif isinstance(date_input, (int, float)):
        # Assume it's a Unix timestamp
        # Detect if it's in milliseconds (> 10 billion means milliseconds)
        if date_input > 10**10:
            return datetime.fromtimestamp(date_input / 1000)
        else:
            return datetime.fromtimestamp(date_input)
    else:
        raise ValueError(f"Unsupported date type: {type(date_input)}")


def prepare_datetime_for_unix_ms_column(date_input):
    """
    Prepare a datetime for PostgreSQL integer columns storing Unix timestamps in milliseconds.

    Converts various date input formats to Unix timestamp in milliseconds (int4/bigint).
    This is used for columns like 'highTime' and 'lowTime' that store timestamps as integers.

    Args:
        date_input: datetime object, Unix timestamp (int/float in seconds or ms),
                   ISO format string, or None

    Returns:
        int: Unix timestamp in milliseconds, or None if input is None

    Examples:
        >>> dt = datetime(2024, 1, 1, 12, 0, 0)
        >>> prepare_datetime_for_unix_ms_column(dt)
        1704110400000

        >>> prepare_datetime_for_unix_ms_column(1704110400)  # seconds
        1704110400000

        >>> prepare_datetime_for_unix_ms_column("2024-01-01T12:00:00")
        1704110400000
    """
    if date_input is None:
        return None
    elif isinstance(date_input, datetime):
        return int(date_input.timestamp() * 1000)
    elif isinstance(date_input, str):
        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(date_input.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            raise ValueError(f"Invalid date string format: {date_input}")
    elif isinstance(date_input, (int, float)):
        # Assume it's already a timestamp
        # Convert to milliseconds if it looks like seconds (< 10 billion)
        if date_input < 10**10:
            return int(date_input * 1000)
        return int(date_input)
    else:
        raise ValueError(f"Unsupported date type: {type(date_input)}")


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
    def __init__(self, item_id: int, load_data: bool = True):
        logger.debug(f"Initializing osrsItemProperties for item_id: {item_id}")
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

        if load_data:
            self.load_stored_data()
        self.interize_attributes()
        logger.debug(f"Completed initialization for item_id: {item_id}")

    def interize_attributes(self):
        logger.debug("Converting float attributes to int where applicable")
        for attr, value in self.__dict__.items():
            if isinstance(value, float):
                setattr(self, attr, int(value))

    def init_conn_cursor(self):
        logger.debug("Initializing database connection and cursor")
        self.conn = init_psql_connection(db=DB_NAME)
        self.cursor = create_cursor(self.conn)

    def destroy_conn_cursor(self):
        logger.debug("Destroying database connection and cursor")
        if hasattr(self, "cursor"):
            logger.debug("Closing cursor")
            self.cursor.close()
        if hasattr(self, "conn"):
            logger.debug("Closing connection")
            self.conn.close()

    @manage_conn_cursor
    def load_stored_data(self):
        logger.debug(f"Loading stored data for item_id: {self.item_id}")

        if not self.item_id:
            logger.warning("Invalid item_id provided.")
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
            logger.warning(f"No item_map found for item_id: {self.item_id}")
            return None
        else:
            logger.debug(f"Retrieved item_map for item_id: {self.item_id}")

        logger.debug(f"Adding map data as attributes")
        for key, value in item_map.items():
            setattr(self, key, value)

        self.get_latest_latest_price()
        self.get_latest_5min_price()
        self.get_latest_1h_price()

    @manage_conn_cursor
    def get_latest_latest_price(self):
        """
        Get the latest price data interactions for the item.
        
        Latest price data structure:
        {
            "high": int,
            "highTime": int,  # Unix timestamp in ms
            "low": int,
            "lowTime": int,   # Unix timestamp in ms
            "timestamp": datetime  # Timestamp of when the data was recorded
        }
        """
        logger.debug(f"Fetching latest price data for item_id: {self.item_id}")
        table_name = f"{str(self.item_id)}_latest"

        try:
            latest_price = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PK_COLUMN,
                limit=3,
            )
        except UndefinedTable:
            logger.warning(f"Price table '{table_name}' does not exist.")
            self.conn.rollback()
            latest_price = []
        except Exception as e:
            logger.error(f"Error fetching latest price data: {e}", exc_info=True)
            self.conn.rollback()
            latest_price = []

        if latest_price:
            logger.debug(f"Processing latest price records for item_id: {self.item_id}")
            recent_record = latest_price[0]

            self.latest_price_high = recent_record.get("high") or 0
            self.latest_price_low = recent_record.get("low") or 0
            self.latest_timestamp_high = recent_record.get("highTime", 0) # Unix timestamp in ms
            self.latest_timestamp_low = recent_record.get("lowTime", 0) # Unix timestamp
            
            self.latest_price_average = self.average_price(
                prices=[self.latest_price_high, self.latest_price_low],
                volumes=[1, 1]  # Volume is unknown, assuming equal volume for average
            )

            self.latest_3x_price_high = self.average_price(
                prices=[r.get("high") or 0 for r in latest_price],
                volumes=[1 for r in latest_price]  # Volume is unknown, assuming equal volume for 3x average
            )
            self.latest_3x_timestamp_high = max(
                r.get("highTime", 0) for r in latest_price
            )  # Unix timestamp in ms
            self.latest_3x_price_low = self.average_price(
                prices=[r.get("low") or 0 for r in latest_price],
                volumes=[1 for r in latest_price]  # Volume is unknown, assuming equal volume for 3x average
            )
            self.latest_3x_timestamp_low = max(r.get("lowTime", 0) for r in latest_price) # Unix timestamp
            self.latest_3x_price_average = self.average_price(
                [self.latest_3x_price_high, self.latest_3x_price_low],
                [1, 1]  # Volume is unknown, assuming equal volume for 3x average
            )

        else:
            self.latest_price_average = 0
            self.latest_price_high = 0
            self.latest_price_low = 0
            self.latest_3x_price_high = 0
            self.latest_3x_price_low = 0
            self.latest_3x_price_average = 0
        logger.debug(f"Completed fetching latest price data for item_id: {self.item_id}")

    @manage_conn_cursor
    def get_latest_5min_price(self):
        """
        Get the latest 5-minute price data interactions for the item.
        
        5-minute price data structure:
        {
            "avgHighPrice": int,
            "avgLowPrice": int,
            "highPriceVolume": int,
            "lowPriceVolume": int,
            "timestamp": datetime  # Timestamp of when the data was recorded
        }
        """
        logger.debug(f"Fetching latest 5-minute price data for item_id: {self.item_id}")
        table_name = f"{str(self.item_id)}_5min"

        try:
            latest_5min_records = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PK_COLUMN,
                limit=3,
            )
        except UndefinedTable:
            logger.warning(f"Price table '{table_name}' does not exist.")
            self.conn.rollback()
            latest_5min_records = []
        except Exception as e:
            logger.error(f"Error fetching latest 5-minute price data: {e}", exc_info=True)
            self.conn.rollback()
            latest_5min_records = []

        if latest_5min_records:
            logger.debug(f"Processing latest 5-minute price records for item_id: {self.item_id}")
            recent_record = latest_5min_records[0]

            # Get 5min data from the most recent record
            # 5m Volumes
            self.latest_5min_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_5min_volume_low = recent_record.get("lowPriceVolume") or 0
            # Not the average of volumes, but the total volume of the averaged high/low prices.
            self.latest_5min_volume_average = self.latest_5min_volume_high + self.latest_5min_volume_low
            # 5m Prices
            self.latest_5min_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_5min_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_5min_price_average = self.average_price(
                prices=[self.latest_5min_price_high, self.latest_5min_price_low],
                volumes=[self.latest_5min_volume_high, self.latest_5min_volume_low]
            )
            self.latest_5min_timestamp = recent_record.get("timestamp", 0) # psql Timestamp

            # Calculate 15min averages from the last 3 records (15 minutes)
            # 15m Volumes
            self.latest_15min_volume_high = sum(
                r.get("highPriceVolume") or 0 for r in latest_5min_records
            )
            self.latest_15min_volume_low = sum(
                r.get("lowPriceVolume") or 0 for r in latest_5min_records
            )
            self.latest_15min_volume_average = self.latest_15min_volume_high + self.latest_15min_volume_low
            # 15m Prices
            self.latest_15min_price_high = self.average_price(
                prices=[r.get("avgHighPrice") or 0 for r in latest_5min_records],
                volumes=[r.get("highPriceVolume") or 0 for r in latest_5min_records]
            )
            self.latest_15min_price_low = self.average_price(
                prices=[r.get("avgLowPrice") or 0 for r in latest_5min_records],
                volumes=[r.get("lowPriceVolume") or 0 for r in latest_5min_records]
            )
            
            # 15m Average Price
            high_price_list = [r.get("avgHighPrice") for r in latest_5min_records]
            low_price_list = [r.get("avgLowPrice") for r in latest_5min_records]
            high_volume_list = [r.get("highPriceVolume") for r in latest_5min_records]
            low_volume_list = [r.get("lowPriceVolume") for r in latest_5min_records]
            self.latest_15min_price_average = self.average_price(
                prices=high_price_list + low_price_list,
                volumes=high_volume_list + low_volume_list
            )
            self.latest_15min_timestamp = max(r.get("timestamp", 0) for r in latest_5min_records) # psql Timestamp

        else: # No records found
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
            
        logger.debug(f"Completed fetching latest 5-minute price data for item_id: {self.item_id}")

    @manage_conn_cursor
    def get_latest_1h_price(self):
        logger.debug(f"Fetching latest 1-hour price data for item_id: {self.item_id}")
        table_name = f"{str(self.item_id)}_1h"

        try:
            prices_1h = fetch_top(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                sort_col=PK_COLUMN,
                limit=3,
            )
        except UndefinedTable:
            logger.warning(f"Price table '{table_name}' does not exist.")
            self.conn.rollback()
            prices_1h = []
        except Exception as e:
            logger.error(f"Error fetching latest 1-hour price data: {e}", exc_info=True)
            self.conn.rollback()
            prices_1h = []

        if prices_1h:
            logger.debug(f"Processing latest 1-hour price records for item_id: {self.item_id}")
            recent_record = prices_1h[0]

            # Get 1h data from the most recent record
            # 1h Volumes
            self.latest_1h_volume_high = recent_record.get("highPriceVolume") or 0
            self.latest_1h_volume_low = recent_record.get("lowPriceVolume") or 0
            # Not the average of volumes, but the total volume of the averaged high/low prices.
            self.latest_1h_volume_average = self.latest_1h_volume_high + self.latest_1h_volume_low
            # 1h Prices
            self.latest_1h_price_high = recent_record.get("avgHighPrice") or 0
            self.latest_1h_price_low = recent_record.get("avgLowPrice") or 0
            self.latest_1h_price_average = self.average_price(
                prices=[self.latest_1h_price_high, self.latest_1h_price_low],
                volumes=[self.latest_1h_volume_high, self.latest_1h_volume_low]
            )
            self.latest_1h_timestamp = recent_record.get("timestamp", 0) # psql Timestamp

            # Calculate 3h averages from the last 3 records (3 hours)
            # 3h Volumes
            self.latest_3h_volume_high = sum(
                r.get("highPriceVolume") or 0 for r in prices_1h
            )
            self.latest_3h_volume_low = sum(
                r.get("lowPriceVolume") or 0 for r in prices_1h
            )
            self.latest_3h_volume_average = self.latest_3h_volume_high + self.latest_3h_volume_low
            # 3h Prices
            self.latest_3h_price_high = self.average_price(
                prices=[r.get("avgHighPrice") or 0 for r in prices_1h],
                volumes=[r.get("highPriceVolume") or 0 for r in prices_1h]
            )
            self.latest_3h_price_low = self.average_price(
                prices=[r.get("avgLowPrice") or 0 for r in prices_1h],
                volumes=[r.get("lowPriceVolume") or 0 for r in prices_1h]
            )
            
            # 3h Average Price
            high_price_list = [r.get("avgHighPrice") for r in prices_1h]
            low_price_list = [r.get("avgLowPrice") for r in prices_1h]
            high_volume_list = [r.get("highPriceVolume") for r in prices_1h]
            low_volume_list = [r.get("lowPriceVolume") for r in prices_1h]
            self.latest_3h_price_average = self.average_price(
                prices=high_price_list + low_price_list,
                volumes=high_volume_list + low_volume_list
            )
            self.latest_3h_timestamp = max(r.get("timestamp", 0) for r in prices_1h) # psql Timestamp

        else:
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
            
        logger.debug(f"Completed fetching latest 1-hour price data for item_id: {self.item_id}")

    @manage_conn_cursor
    def get_prices_between_dates(
        self, start_date, end_date=None, table_type="5min", limit=None, sort_desc=True
    ):
        """
        Get item prices between two given dates.

        Args:
            start_date: Start date (datetime object, ISO string, or Unix timestamp)
            end_date: End date (datetime object, ISO string, or Unix timestamp).
                     Defaults to current time if None.
            table_type: Price table type ("latest", "5min", "1h"). Defaults to "5min".
            limit: Maximum number of records to return. No limit if None.
            sort_desc: Sort by timestamp in descending order. Defaults to True.

        Returns:
            list: List of price records within the date range, or empty list if none found.

        Raises:
            ValueError: If start_date is after end_date or invalid table_type.
        """
        logger.debug(f"Fetching prices between dates for item_id: {self.item_id}, table_type: {table_type}")

        # Validate table_type
        valid_table_types = ["latest", "5min", "1h"]
        if table_type not in valid_table_types:
            logger.error(f"Invalid table_type: {table_type}")
            raise ValueError(
                f"table_type must be one of {valid_table_types}, got '{table_type}'"
            )

        # Set end_date to current time if not provided
        if end_date is None:
            end_date = datetime.now()

        if table_type in ["5min", "1h"]:
            # Convert dates to datetime objects for PostgreSQL timestamp column
            start_dt = prepare_datetime_for_timestamp_column(start_date)
            end_dt = prepare_datetime_for_timestamp_column(end_date)
        else:
            # "latest" table uses Unix timestamps in milliseconds (int4/bigint)
            start_dt = prepare_datetime_for_unix_ms_column(start_date)
            end_dt = prepare_datetime_for_unix_ms_column(end_date)


        # Validate date range
        if start_dt >= end_dt:
            raise ValueError("start_date must be before end_date")

        # Construct table name
        table_name = f"{self.item_id}_{table_type}"

        # Build the SQL Filter
        filters = [
            {"logic": "AND", "rules": [
                {"property": PK_COLUMN, "operator": "greater_than", "value": start_dt, "logic": "AND"},
                {"property": PK_COLUMN, "operator": "less_than", "value": end_dt, "logic": "AND"}
            ]}
        ]
        
        # Execute the SQL query
        try:
            logger.debug(f"Executing filtered records query on table: {table_name} with filters: {filters}")
            records = get_filtered_records(
                cursor=self.cursor,
                connection=self.conn,
                database=DB_NAME,
                schema_name=PRICE_SCHEMA,
                table_name=table_name,
                filters=filters,
                sort_by=PK_COLUMN,
                descending=sort_desc,
                nulls_last=True,
            )
            logger.debug(f"Retrieved {len(records)} records from table: {table_name}")
            return records[:limit] if limit is not None else records
        except Exception as e:
            logger.error(f"Error fetching prices between dates: {e}", exc_info=True)
            raise e
            
    def average_price(self, prices: list[int], volumes: list[int]) -> float:
        """
        Average price weighted by volume.
        Args:
            prices (list[int]): List of prices.
            volumes (list[int]): List of volumes corresponding to the prices.
        """
        if len(prices) != len(volumes):
            raise ValueError("Prices and volumes lists must have the same length.")
        
        n = 0
        sum = 0
        for price, volume in zip(prices, volumes):
            if price and volume:
                n += volume
                sum += price * volume
        return sum / n if n > 0 else 0

    @manage_conn_cursor
    def create_price_line_graph(
        self,
        start_date,
        end_date=None,
        table_type="5min",
        limit=None,
        return_base64=False,
        save_path=None,
        figsize=(12, 6),
        title=None,
    ):
        """
        Create a line graph showing high and low prices over time.

        Args:
            start_date: Start date for the price data
            end_date: End date for the price data (defaults to now)
            table_type: Price table type ("latest", "5min", "1h")
            limit: Maximum number of records to fetch
            return_base64: If True, return base64-encoded PNG image string
            save_path: If provided, save the graph to this file path
            figsize: Tuple of (width, height) for the figure size
            title: Custom title for the graph (defaults to item name)

        Returns:
            str or None: Base64-encoded PNG string if return_base64=True, otherwise None
        """
        # Fetch price data
        price_data = self.get_prices_between_dates(
            start_date=start_date,
            end_date=end_date,
            table_type=table_type,
            limit=limit,
            sort_desc=False,  # Sort ascending for chronological order
        )

        if not price_data:
            raise ValueError(
                f"No price data found for item {self.item_id} in the specified date range"
            )

        # Extract data for plotting
        timestamps = []
        high_prices = []
        low_prices = []

        for record in price_data:
            # Convert timestamp (milliseconds) to datetime
            timestamp_ms = record.get("timestamp")
            if timestamp_ms:
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                timestamps.append(dt)
                high_prices.append(record.get("price_high", 0))
                low_prices.append(record.get("price_low", 0))

        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)

        # Plot the lines
        ax.plot(
            timestamps,
            high_prices,
            label="High Price",
            color="#e74c3c",
            linewidth=2,
            marker="o",
            markersize=3,
        )
        ax.plot(
            timestamps,
            low_prices,
            label="Low Price",
            color="#3498db",
            linewidth=2,
            marker="o",
            markersize=3,
        )

        # Formatting
        ax.set_xlabel("Date", fontsize=12, fontweight="bold")
        ax.set_ylabel("Price (GP)", fontsize=12, fontweight="bold")

        # Set title
        graph_title = (
            title
            if title
            else (
                f"{self.name} - Price History"
                if self.name
                else f"Item {self.item_id} - Price History"
            )
        )
        ax.set_title(graph_title, fontsize=14, fontweight="bold")

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        plt.xticks(rotation=45, ha="right")

        # Add grid
        ax.grid(True, alpha=0.3, linestyle="--")

        # Add legend
        ax.legend(loc="best", frameon=True, shadow=True)

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Handle output
        result = None
        if return_base64:
            # Save to BytesIO buffer and encode as base64
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            buffer.close()
            result = img_base64

        if save_path:
            plt.savefig(save_path, dpi=100, bbox_inches="tight")

        plt.close(fig)
        return result

    @manage_conn_cursor
    def create_volume_bar_graph(
        self,
        start_date,
        end_date=None,
        table_type="5min",
        limit=None,
        return_base64=False,
        save_path=None,
        figsize=(12, 6),
        title=None,
    ):
        """
        Create a bar graph showing high and low volumes over time.
        High volumes go upward, low volumes go downward (mirrored).

        Args:
            start_date: Start date for the volume data
            end_date: End date for the volume data (defaults to now)
            table_type: Price table type ("latest", "5min", "1h")
            limit: Maximum number of records to fetch
            return_base64: If True, return base64-encoded PNG image string
            save_path: If provided, save the graph to this file path
            figsize: Tuple of (width, height) for the figure size
            title: Custom title for the graph (defaults to item name)

        Returns:
            str or None: Base64-encoded PNG string if return_base64=True, otherwise None
        """
        # Fetch price data (includes volume information)
        price_data = self.get_prices_between_dates(
            start_date=start_date,
            end_date=end_date,
            table_type=table_type,
            limit=limit,
            sort_desc=False,  # Sort ascending for chronological order
        )

        if not price_data:
            raise ValueError(
                f"No volume data found for item {self.item_id} in the specified date range"
            )

        # Extract data for plotting
        timestamps = []
        high_volumes = []
        low_volumes = []

        for record in price_data:
            # Convert timestamp (milliseconds) to datetime
            timestamp_ms = record.get("timestamp")
            if timestamp_ms:
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
                timestamps.append(dt)
                high_volumes.append(record.get("volume_high", 0))
                # Make low volumes negative for downward bars
                low_volumes.append(-record.get("volume_low", 0))

        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)

        # Calculate bar width based on number of data points
        if len(timestamps) > 1:
            time_diff = timestamps[1] - timestamps[0]
            bar_width = time_diff * 0.8  # 80% of the time between points
        else:
            bar_width = 0.8

        # Plot the bars
        ax.bar(
            timestamps,
            high_volumes,
            width=bar_width,
            label="High Volume",
            color="#2ecc71",
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )
        ax.bar(
            timestamps,
            low_volumes,
            width=bar_width,
            label="Low Volume",
            color="#e67e22",
            alpha=0.8,
            edgecolor="black",
            linewidth=0.5,
        )

        # Add a horizontal line at y=0
        ax.axhline(y=0, color="black", linewidth=1.5, linestyle="-")

        # Formatting
        ax.set_xlabel("Date", fontsize=12, fontweight="bold")
        ax.set_ylabel("Volume", fontsize=12, fontweight="bold")

        # Set title
        graph_title = (
            title
            if title
            else (
                f"{self.name} - Volume History"
                if self.name
                else f"Item {self.item_id} - Volume History"
            )
        )
        ax.set_title(graph_title, fontsize=14, fontweight="bold")

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        plt.xticks(rotation=45, ha="right")

        # Add grid
        ax.grid(True, alpha=0.3, linestyle="--", axis="y")

        # Add legend
        ax.legend(loc="best", frameon=True, shadow=True)

        # Format y-axis to show absolute values with labels
        y_ticks = ax.get_yticks()
        ax.set_yticklabels([f"{abs(int(y))}" for y in y_ticks])

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Handle output
        result = None
        if return_base64:
            # Save to BytesIO buffer and encode as base64
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            buffer.close()
            result = img_base64

        if save_path:
            plt.savefig(save_path, dpi=100, bbox_inches="tight")

        plt.close(fig)
        return result
