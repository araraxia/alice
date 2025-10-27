# OSRS Item Properties - Graph Methods Documentation

## Overview

Two new methods have been added to the `osrsItemProperties` class for visualizing price and volume data over time:

1. **`create_price_line_graph`** - Creates a line graph showing high and low prices over time
2. **`create_volume_bar_graph`** - Creates a bar graph showing high and low volumes over time

Both methods use the existing `get_prices_between_dates` method to fetch data and generate visualizations using matplotlib.

---

## Method 1: `create_price_line_graph`

Creates a line graph with two lines showing the high price (red) and low price (blue) over time.

### Signature

```python
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
)
```

### Parameters

- **`start_date`** (required): Start date for the price data
  - Accepts: `datetime` object, ISO string, or Unix timestamp
  
- **`end_date`** (optional): End date for the price data
  - Defaults to current time if not provided
  - Accepts: `datetime` object, ISO string, or Unix timestamp

- **`table_type`** (optional): Price table type
  - Options: `"latest"`, `"5min"`, `"1h"`
  - Default: `"5min"`

- **`limit`** (optional): Maximum number of records to fetch
  - Default: `None` (no limit)

- **`return_base64`** (optional): Whether to return base64-encoded PNG
  - Default: `False`
  - Use `True` for embedding in HTML/web applications

- **`save_path`** (optional): File path to save the graph
  - Example: `"price_graph.png"`
  - Default: `None` (doesn't save to file)

- **`figsize`** (optional): Figure size as `(width, height)` tuple
  - Default: `(12, 6)`

- **`title`** (optional): Custom title for the graph
  - Default: Uses item name or item ID

### Returns

- `str` or `None`: Base64-encoded PNG string if `return_base64=True`, otherwise `None`

### Example Usage

```python
from datetime import datetime, timedelta
from src.osrs.item_properties import osrsItemProperties

# Initialize item
item = osrsItemProperties(item_id=2)

# Get data for last 7 days
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

# Save to file
item.create_price_line_graph(
    start_date=start_date,
    end_date=end_date,
    table_type="5min",
    limit=100,
    save_path="price_history.png"
)

# Get as base64 for web display
base64_img = item.create_price_line_graph(
    start_date=start_date,
    end_date=end_date,
    return_base64=True
)

# Use in HTML
html = f'<img src="data:image/png;base64,{base64_img}" />'
```

---

## Method 2: `create_volume_bar_graph`

Creates a bar graph showing trading volumes over time. High volumes are shown as upward bars (green) and low volumes are shown as downward bars (orange), creating a mirrored effect.

### Signature

```python
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
)
```

### Parameters

Same as `create_price_line_graph` - see above.

### Returns

- `str` or `None`: Base64-encoded PNG string if `return_base64=True`, otherwise `None`

### Example Usage

```python
from datetime import datetime, timedelta
from src.osrs.item_properties import osrsItemProperties

# Initialize item
item = osrsItemProperties(item_id=2)

# Get data for last 24 hours
end_date = datetime.now()
start_date = end_date - timedelta(hours=24)

# Save to file
item.create_volume_bar_graph(
    start_date=start_date,
    end_date=end_date,
    table_type="5min",
    save_path="volume_history.png"
)

# Get as base64 for web display
base64_img = item.create_volume_bar_graph(
    start_date=start_date,
    end_date=end_date,
    return_base64=True
)
```

---

## Visual Features

### Price Line Graph
- **Red line**: High prices with circular markers
- **Blue line**: Low prices with circular markers
- **Grid**: Dotted grid lines for easier reading
- **X-axis**: Date/time formatted as `YYYY-MM-DD HH:MM`
- **Y-axis**: Price in GP (gold pieces)
- **Legend**: Shows which line represents high/low prices

### Volume Bar Graph
- **Green bars (upward)**: High trading volumes
- **Orange bars (downward)**: Low trading volumes
- **Black horizontal line**: Zero baseline
- **Grid**: Horizontal dotted grid lines
- **X-axis**: Date/time formatted as `YYYY-MM-DD HH:MM`
- **Y-axis**: Volume (absolute values shown)
- **Legend**: Shows which bars represent high/low volumes

---

## Error Handling

Both methods will raise a `ValueError` if:
- No data is found for the specified date range
- Invalid parameters are passed to `get_prices_between_dates`

Example:
```python
try:
    item.create_price_line_graph(
        start_date=start_date,
        end_date=end_date,
        save_path="graph.png"
    )
except ValueError as e:
    print(f"Error: {e}")
```

---

## Dependencies

The following packages are required:
- `matplotlib==3.9.2` (added to requirements.txt)
- `psycopg2` (already in requirements)
- `python-dateutil` (already in requirements)

Install with:
```bash
pip install -r requirements.txt
```

---

## Integration with Flask/Web Applications

Both methods support returning base64-encoded PNG images, making them perfect for web applications:

```python
from flask import render_template
from src.osrs.item_properties import osrsItemProperties

@app.route('/item/<int:item_id>/graph')
def item_graph(item_id):
    item = osrsItemProperties(item_id)
    
    # Generate graphs as base64
    price_graph = item.create_price_line_graph(
        start_date=datetime.now() - timedelta(days=7),
        return_base64=True
    )
    
    volume_graph = item.create_volume_bar_graph(
        start_date=datetime.now() - timedelta(days=7),
        return_base64=True
    )
    
    return render_template(
        'item_graphs.html',
        price_graph=price_graph,
        volume_graph=volume_graph,
        item=item
    )
```

HTML template:
```html
<h2>{{ item.name }} - Price History</h2>
<img src="data:image/png;base64,{{ price_graph }}" alt="Price History" />

<h2>{{ item.name }} - Volume History</h2>
<img src="data:image/png;base64,{{ volume_graph }}" alt="Volume History" />
```

---

## Testing

A test script is provided: `test_graph_methods.py`

Run it with:
```bash
python test_graph_methods.py
```

This will:
1. Generate a price line graph
2. Generate a volume bar graph
3. Test base64 encoding
4. Save sample PNG files for inspection

---

## Notes

- The `@manage_conn_cursor` decorator ensures proper database connection management
- All graphs use tight layout to prevent label cutoff
- The methods automatically close matplotlib figures to prevent memory leaks
- Date formatting on x-axis adjusts based on the data range
- Both methods sort data chronologically (oldest to newest) for proper visualization
