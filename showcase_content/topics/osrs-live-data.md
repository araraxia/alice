# OSRS Real-Time Prices

## Overview

Old School Runescape has a trading system called the [Grand Exchange](https://oldschool.runescape.wiki/w/Grand_Exchange) where players can list buy and sell orders for tradable items in the game. Items traded through this system have a [guide price](https://oldschool.runescape.wiki/w/Grand_Exchange#Guide_prices), a recommended item price based off supply and demand to estimate the market value of the item, that only updates between a few times per day to once a week. This guide price is usually inaccurate due to the long update cycle, so the community built a real-time crowdsourced price tracking system to improve market value accuracy using the popular game client [RuneLite](https://runelite.net/).

The RuneLite client ships with a plugin that sends Grand Exchange transation data to the OSRS Wiki, where players can [view real-time prices](https://prices.runescape.wiki/osrs/) or create tools using the Wiki's [real-time price API](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices). This project is centered around collecting this real-time data on a local PostgreSQL server that can then be utilized by online tools hosted on this server.

## Technical Implementation

### Endpoint Communication

All communication with the OSRS Wiki Real-time Prices API is managed through the `WikiDataGetter` helper class, which provides a clean interface for retrieving price data from various endpoints. This class handles the complexities of HTTP communication, including proper header management, session persistence, and comprehensive error handling.

#### Available Endpoints

The system interacts with five primary API endpoints:

- **`latest_prices`**: Returns the most recent price data for all items
- **`5min_prices`**: Provides 5-minute rolling average prices
- **`1h_prices`**: Provides 1-hour rolling average prices  
- **`mapping`**: Returns the complete item ID to item name mapping database

#### Implementation Details

The `WikiDataGetter` class leverages Python's `requests` library with a persistent session to efficiently reuse HTTP connections across multiple API calls. This approach significantly reduces overhead when fetching data repeatedly from the same host.

A critical requirement for using the OSRS Wiki API is providing a proper `User-Agent` header that identifies your application and includes contact information. The class loads these headers from a configuration file (`conf/osrs_wiki_headers.json`) and validates that the User-Agent is present before allowing any requests. This ensures compliance with the API's usage policies and helps the Wiki administrators monitor traffic patterns.

The `get_data()` method serves as the primary interface for endpoint communication, accepting an endpoint name and optional parameters (`id` for specific items, `timestamp` for historical data). The method validates the endpoint name, constructs the appropriate request parameters, and handles the HTTP response. If the request succeeds, it returns the parsed JSON data; if it fails, the error is logged both to the application's log files and to the PostgreSQL database for monitoring and debugging purposes.

This abstraction layer simplifies data retrieval throughout the application - instead of managing raw HTTP requests, other modules can simply instantiate a `WikiDataGetter` and call `get_data()` with the desired endpoint, letting the class handle all communication details.

### Item Mapping

Item mapping establishes the foundational relationship between item IDs and their associated metadata in our local PostgreSQL database. The `map_osrs_items.py` script handles this crucial synchronization process, ensuring our local item database remains current with the OSRS Wiki's comprehensive item catalog.

#### Data Retrieval and Processing

The script begins by instantiating a `WikiDataGetter` and calling the [mapping endpoint](https://prices.runescape.wiki/api/v1/osrs/mapping), which returns an array of item objects containing essential item metadata such as item ID, name, examine text, and various boolean flags (members-only status, high-value warnings, etc.).

Rather than using a rigid, predefined schema, the script employs a dynamic column detection system. The `create_map_columns()` function iterates through all retrieved records and examines each key-value pair to automatically determine the appropriate PostgreSQL column types. This adaptive approach means the script can handle schema changes from the API without requiring manual updates - if the Wiki adds new fields to their mapping data, our system automatically accommodates them.

#### Database Synchronization

Once the column structure is determined, the script validates that the target table (`items.map` in the `osrs` database) exists and has the correct schema. If the table doesn't exist, it's created automatically. If it exists but is missing columns, those columns are added. This validation step ensures database integrity while maintaining backward compatibility with existing data.

The actual data insertion leverages an upsert pattern (INSERT ... ON CONFLICT UPDATE) to handle both new items and updates to existing items seamlessly. Each record from the API is parsed into column names and values, then inserted with the item ID as the conflict target. If an item already exists in the database, its fields are updated with the latest values; if it's new, a fresh record is created.

#### Automation and Reliability

The entire process is wrapped in comprehensive error handling and logging. Every major operation - from API retrieval to database insertion - is logged with detailed context, making it easy to diagnose issues when they occur. The script is designed to be run as a scheduled task, keeping the item mapping database continuously synchronized with the upstream Wiki data source.

This mapping data serves as the backbone for all other OSRS-related functionality in the application, providing the reference data needed to translate between item IDs and human-readable names, filter by item properties, and validate item-related user inputs.

### Item Properties and Price Data Access

The `osrsItemProperties` class serves as the primary interface for accessing comprehensive item data and price history within the application. This class encapsulates all item-related information - from basic metadata like names and examine text to complex time-series price data across multiple granularities - providing a unified API for item data retrieval.

#### Data Aggregation and Initialization

When instantiated with an item ID, the `osrsItemProperties` class automatically aggregates data from multiple database sources. It first retrieves the item's core metadata from the `items.map` table (populated by the mapping script), loading properties such as the item name, examine text, members-only status, Grand Exchange trade limits, and high/low alchemy values.

The class then queries three separate price table types for the item, each offering different temporal granularity:

- **Latest prices**: Individual buy/sell transactions with precise timestamps (millisecond accuracy)
- **5-minute averages**: Rolling 5-minute aggregations of high/low prices and trading volumes
- **1-hour averages**: Rolling 1-hour aggregations providing broader trend visibility

For each table type, the class retrieves the most recent records and calculates weighted averages across multiple time windows. For example, from the latest price data, it computes both single-transaction averages and 3x-transaction rolling averages, providing both immediate and short-term price indicators. Similarly, 5-minute data is aggregated into 15-minute windows, and 1-hour data into 3-hour windows, creating a multi-resolution view of price trends.

#### Volume-Weighted Price Calculations

A key feature of the class is its volume-weighted price averaging methodology. Rather than simply averaging prices arithmetically, the `average_price()` method weighs each price by its corresponding trading volume. This approach provides more accurate market value estimates, as high-volume transactions carry more statistical significance than low-volume outliers. This weighted averaging is applied consistently across all time granularities, ensuring that computed averages reflect actual market activity patterns.

It is worth pointing out that the latest price data endpoint does not return item volume data, so it is unable to utilize this methodology,

#### Historical Data Queries

Beyond loading recent price snapshots, the class provides the `get_prices_between_dates()` method for querying historical price data within arbitrary date ranges. This method accepts various date input formats (datetime objects, ISO strings, Unix timestamps) and automatically normalizes them for database queries. It supports all three table types and includes optional result limiting and sorting controls, making it flexible enough to power both detailed analysis and high-level trend visualizations.

#### Database Connection Management

Database operations are handled through a decorator-based connection management system using the `@manage_conn_cursor` decorator. This pattern ensures that database connections are properly opened before method execution and cleanly closed afterward, preventing connection leaks even when exceptions occur. The decorator checks for existing connections and reuses them when possible, optimizing performance for sequential operations while maintaining proper resource cleanup.

#### Visualization Capabilities

The class includes built-in visualization methods that transform raw price data into informative graphs. The `create_price_line_graph()` method generates line charts showing high and low price trends over time, while `create_volume_bar_graph()` creates mirrored bar charts with high volumes extending upward and low volumes extending downward, providing instant visual insight into market liquidity patterns.

Both visualization methods support flexible output options - they can return base64-encoded PNG strings for web embedding, save directly to filesystem paths for reports, or display interactively during development. The graphs leverage matplotlib with carefully chosen styling (colors, markers, grids) to ensure readability and professional presentation.

#### Integration with Application Features

The `osrsItemProperties` class acts as the data layer for various user-facing features throughout the application. Item search functionality uses it to display current prices and metadata, calculator tools reference it for accurate market values in profit calculations, and dashboard widgets query it for real-time price updates. By centralizing all item data access through this single interface, the application maintains consistency across features while simplifying maintenance and testing.

### Automated Price Collection

The `get_osrs_item_prices.py` script orchestrates the continuous collection and storage of real-time price data, maintaining a comprehensive historical record of Grand Exchange market activity. This script serves as the data pipeline that bridges the OSRS Wiki API and our local PostgreSQL database, executing on scheduled intervals to capture price movements throughout the day.

#### Multi-Granularity Price Updates

The script supports three distinct price collection modes, each targeting a different level of temporal resolution:

- **Latest Prices** (`update_latest_prices`): Captures individual transaction data with millisecond-precision timestamps, recording the most recent high/low buy and sell prices for each item. This provides the finest granularity for detecting rapid market fluctuations.
  
  - **!!Warning!!** There is a possibility that there is missed live data with the latest prices endpoint, since there is currently no way of knowing if the endpoint returns the last transactions from the past minute, or if it returns a rolling average from the last minute. I've reached out to the Wiki team for clarity, but did not get a response about what the endpoint actually returns other than that the endpoint data is updated once per minute. Because of this, it is safer to treat it as if the endpoint only returns the last transaction in the past minute and to not rely on it for any price over time data.

- **5-Minute Averages** (`update_5min_prices`): Retrieves rolling 5-minute averages of prices and trading volumes, smoothing out momentary spikes while still capturing short-term trends. This data is particularly useful for identifying intraday patterns and typical trading ranges.

- **1-Hour Averages** (`update_1h_prices`): Fetches hourly aggregations that reveal longer-term market trends and price stability. These averages help filter out noise from volatile trading periods and establish baseline market values.

Each mode operates independently through command-line flags, allowing fine-grained control over which data types to collect during each script execution. This modular design supports flexible scheduling strategies and enables efficient resource usage by updating different granularities on their optimal intervals.

#### Dynamic Schema Management

Following the same adaptive approach as the mapping script, `get_osrs_item_prices.py` employs dynamic schema detection to accommodate API changes gracefully. When price data arrives, the `create_data_columns()` function inspects the structure and infers appropriate PostgreSQL column types for each field. All price records include a `timestamp` column (using PostgreSQL's TIMESTAMP type) that records when the data was collected, serving as both the primary key and the temporal index for historical queries.

The script creates a separate table for each item and price type combination (e.g., `2_latest`, `2_5min`, `2_1h` for item ID 2), enabling efficient per-item queries without scanning across unrelated items. This table-per-item strategy optimizes both storage and retrieval performance, as each table contains only records for a single item, allowing PostgreSQL to leverage smaller indexes and more focused query plans.

#### Validation and Error Recovery

Before inserting price data, the script validates that target tables exist with the correct schema through the `validate_tables()` function. If tables are missing or outdated, they're automatically created or updated. The script adds primary key constraints on the timestamp column, preventing duplicate records for the same collection time and ensuring data integrity.

Robust error handling addresses common failure scenarios: if an insertion fails due to a missing table or column (which can occur if the API schema changes mid-execution), the script catches the PostgreSQL exception and triggers `retry_update_record()`. This function rebuilds the table schema on-the-fly and retries the insertion, ensuring that data collection continues even when unexpected schema changes occur.

#### Scheduling and Automation

The script is designed for unattended operation via cron jobs on the server hosting the Alice Flask application. The collection schedule aligns with each data type's natural update frequency:

- **Latest prices**: Executed every minute to capture near-real-time transaction data
- **5-minute prices**: Executed every 5 minutes to align with the API's aggregation window
- **1-hour prices**: Executed every hour to collect long-term trend data

This staggered scheduling strategy ensures continuous data coverage across all time scales while minimizing database write load. Each execution runs independently, logging all operations to dedicated log files for monitoring and troubleshooting. The `--no-validate` flag can be used to skip table validation on subsequent runs after the initial setup, further optimizing execution speed during routine collection cycles.

#### Data Flow and Storage

When executed, the script follows a consistent workflow: fetch data from the WikiDataGetter, parse the JSON response into item-specific records, validate or create the necessary database tables, and insert records using an upsert pattern (INSERT ... ON CONFLICT UPDATE). The timestamp-based conflict resolution ensures that if a collection runs twice for the same time period, the newer data overwrites the older entry rather than creating duplicates.

This automated collection process runs continuously in production, steadily building a rich historical dataset. Over time, these tables accumulate comprehensive price histories that power trend analysis, volatility calculations, and predictive modeling features throughout the application. The combination of high-frequency latest prices, medium-frequency 5-minute averages, and low-frequency hourly data provides the multi-resolution temporal coverage needed to serve diverse analytical use cases.

## Source Files

- [get_item_data.py](/files/showcase/get_item_data.py) - Real-time price API helper
- [map_osrs_items.py](/files/showcase/map_osrs_items.py) - Item mapping script
- [get_osrs_item_prices.py](/files/showcase/get_osrs_item_prices.py) - Price retrieval and storing script
- [item_properties.py](/files/showcase/item_properties.py) - Item Class

## Future Enhancements

### Architecture Improvements

- [ ] **Temporal Flexibility for `osrsItemProperties`**: The class is currently designed around the latest price data - it should be adapted to support queries for any time period while defaulting to latest. This would enable historical item snapshots at arbitrary timestamps.

- [ ] **Table Consolidation Strategy**: The current per-item table approach (e.g., `2_latest`, `2_5min`, `2_1h`) creates thousands of small tables. Consider consolidating into partitioned tables (e.g., `prices_latest` with partitioning by item_id ranges) to reduce schema complexity and improve table management at scale.

- [ ] **Caching Layer**: Implement Redis or similar caching for frequently accessed price data, especially for popular items. The `osrsItemProperties` class currently queries the database on every instantiation - caching recent data could significantly reduce database load during high-traffic periods.

- [ ] **Data Retention Policies**: Establish automated archival strategies for old price data. Latest prices older than 30 days could be downsampled to 5-minute averages, and 5-minute data older than 90 days could be aggregated into hourly records, significantly reducing storage requirements while maintaining long-term trend visibility.

### Feature Enhancements

- [ ] **Predictive Price Analytics**: Leverage the extensive historical dataset to implement machine learning models that predict short-term price movements based on patterns like time-of-day effects, weekly cycles, and trading volume correlations.

- [ ] **Market Volatility Indicators**: Calculate and expose volatility metrics (standard deviation, coefficient of variation) across different time windows to help users identify stable vs. volatile items for various investment strategies.

- [ ] **Price Alert System**: Build a notification system that monitors price movements and alerts users when items cross specified thresholds or exhibit unusual trading patterns.

- [ ] **Bulk Price Queries**: Extend `osrsItemProperties` to support batch item lookups, returning price data for multiple items in a single operation. This would optimize features that need prices for many items simultaneously.

### Reliability and Monitoring

- [ ] **Gap Backfilling**: Develop utilities to detect and fill gaps in historical data that might occur during server downtime or collection failures, potentially using the timeseries API endpoint to retrieve missed data points.

### Performance Optimization

- [ ] **Batch Insert Operations**: Modify the price collection script to accumulate records and insert them in batches rather than one-by-one, reducing database round-trips and transaction overhead.
