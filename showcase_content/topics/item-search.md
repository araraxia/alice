# Item Search Tool

## Overview

The official OSRS wiki does not list item IDs on their wiki page (if they do I'm stupid and missed it or they changed it), so I needed an easy way to look up items by name to get their ID while I make price scripts. This provides a simple UI to do that, and opens the door for future item lookup functions.

## Search Functionality

### Dual Search Modes

The search interface supports two distinct query types, selectable via a dropdown menu:

- **Name Search**: Performs fuzzy matching against item names using SQL's ILIKE pattern matching. This forgiving search approach means users don't need exact spelling - searching "dragon scim" successfully returns "Dragon scimitar", and "pot prayer" finds all prayer potions. The fuzzy search wraps the query in wildcard patterns (`%query%`), matching items where the search term appears anywhere in the name.

- **ID Search**: Enables direct lookup by item ID for users who know the specific numeric identifier. This provides instantaneous exact-match retrieval, useful for developers, API integrations, or players referencing items from external tools.

Both search types operate against the `items.map` table in the PostgreSQL database, which contains the synchronized item catalog populated by the mapping script discussed in the [OSRS Live Data Management](/showcase/osrs-live-data) documentation.

### Backend Implementation

The `ItemSearch` class provides a clean abstraction over database queries through three primary methods:

- **`search_by_id(item_id)`**: Executes a direct lookup using the `get_record()` SQL helper, returning a single item dictionary or None if not found.

- **`search_by_name(name, exact=False)`**: Implements dual-mode name searching. When `exact=False` (default), it uses `fuzzy_search_records()` with case-insensitive pattern matching. When `exact=True`, it performs precise equality matching via `search_records()`. The fuzzy mode provides better user experience for typical interactive searches.

- **`display()`**: Renders the search interface template, returning the HTML/JavaScript frontend that handles user interaction and API communication.

The class maintains database connection parameters as instance variables (`database="osrs"`, `schema="items"`, `table="map"`), centralizing configuration and simplifying maintenance.

## Item Information Display

### Metadata Presentation

Search results display as styled cards, each containing comprehensive item details extracted from the mapping database:

- **Basic Info**: Item name displayed prominently alongside its numeric ID
- **Examine Text**: The in-game item description, providing context and lore
- **Economic Data**:
  - Store value (base game price)
  - High alchemy value (gold obtained from high-level alchemy spell)
  - Low alchemy value (gold obtained from low-level alchemy spell)
  - Grand Exchange trade limit (maximum purchases per 4 hours)
- **Access Requirements**: Members-only flag indicating whether the item requires a paid membership

This information proves valuable for various use cases: alchemy profit calculations reference the store value vs. alchemy values, traders monitor GE limits for bulk operations, and new players check membership requirements before planning item acquisitions.

### Frontend Design

The interface embraces a retro Windows 98 aesthetic that aligns with the broader Alice application theme. The search window features:

- **Draggable Title Bar**: Users can reposition the search interface anywhere on screen by dragging the title bar, mimicking classic desktop window behavior
- **Styled Form Elements**: Dropdown selectors, text inputs, and buttons all use custom `.w98-button` and `.w98-input` CSS classes for consistent retro styling
- **Scrollable Results Pane**: Search results appear in a constrained-height container with automatic scrolling, preventing extremely long result lists from overwhelming the interface
- **Responsive Feedback**: Loading states and error messages provide clear user feedback during asynchronous operations

## Price Data Integration (In Progress)

### Current Implementation

While the core price data integration is still under active development, the frontend includes substantial groundwork for time-series price visualization:

**Time Range Selection**: When a user clicks the "Price Data" button on an item card, a modal selector appears offering four preset time ranges:

- Last 12 Hours
- Last 1 Day
- Last 7 Days
- Last 1 Month

I've only been collecting data since September 2025, so there is little need for a wider range than 1 month until I start backporting older data into my SQL server.

### Architecture Decisions

The price graphing system demonstrates several thoughtful design choices:

- **Dynamic Window Creation**: Each price data request spawns a new window instance managed by the global `WindowInitializer` system, ensuring multiple graphs can coexist without ID conflicts
- **CSRF Protection**: All AJAX requests include CSRF tokens extracted from meta tags, protecting against cross-site request forgery attacks
- **Separation of Concerns**: The frontend handles user interaction, date range calculation and interactive visualization generation, while the backend focuses on data retrieval and static visualizations, maintaining clean boundaries between layers

### Pending Enhancements

Several improvements remain on the roadmap to mature the price data integration:

- **Volume Visualization**: Add companion graphs showing trading volume alongside price trends to identify liquidity patterns
- **Multi-Item Comparison**: Support overlaying multiple item price trends on a single graph for comparative analysis
- **Interactive Tooltips**: Implement hover tooltips on graph data points showing exact prices and timestamps
- **Export Functionality**: Enable downloading graph images or raw CSV data for external analysis
- **Caching Strategy**: Implement Redis caching for recently generated graphs to reduce database load and improve response times

## Technical Architecture

### Request Flow

A typical search operation follows this path:

1. User enters search query and clicks "Search" (or presses Enter)
2. JavaScript captures the event and validates the input
3. Frontend POSTs to `/osrs/item-search/search` with `search_type` and `search_value`
4. Backend router invokes appropriate `ItemSearch` method (`search_by_id` or `search_by_name`)
5. SQL helper functions query the PostgreSQL database
6. Results serialize to JSON and return to the frontend
7. JavaScript dynamically generates HTML cards and injects them into the results pane

This AJAX-based approach provides instant results without page reloads, maintaining smooth user experience consistent with modern single-page application patterns.

### Error Handling

The system implements defensive error handling at multiple layers:

- **Frontend Validation**: Empty queries trigger user-friendly messages before making network requests
- **Backend Try-Catch**: Database exceptions are caught, logged, and converted to structured error responses
- **Network Failure Recovery**: Failed fetch operations display graceful error messages rather than leaving the UI in broken states
- **SQL Injection Protection**: All queries use parameterized statements through the SQL helper abstraction, preventing injection attacks

### Integration Points

The item search tool integrates seamlessly with other OSRS features:

- **Calculator Tools**: Search results can trigger profit calculators that reference item prices and alchemy values
- **Price Tracking**: Item IDs from search results flow into price graph generation and historical analysis features
- **User Workflows**: The search acts as the entry point for most item-related operations, serving as a discovery mechanism that feeds into deeper analytical tools

## Future Development

Beyond the in-progress price graphing improvements, several enhancements could expand the tool's capabilities:

- **Advanced Filtering**: Add filters for members/F2P, high-alch profit thresholds, or GE limits
- **Saved Searches**: Allow users to bookmark frequently searched items or custom search queries
- **Search History**: Maintain a session-based history of recent searches for quick re-access
- **Batch Operations**: Support searching multiple items simultaneously via comma-separated IDs or names
- **Mobile Optimization**: Adapt the interface for touch interactions and smaller viewport sizes
- **Item List Dashboard**: Dynamically generated dashboards from a user created list of items.
