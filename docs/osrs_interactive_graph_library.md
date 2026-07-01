# OSRS Interactive Graph Library — Implementation Spec

## Purpose

Replace the existing Chart.js-based `price_graph_modal.js` / `price_graph_modal.html` with a
self-contained JavaScript library that renders fully interactive price and volume graphs for OSRS
items. The library owns its own canvas rendering — no Chart.js or other graphing dependencies.

---

## Integration Context (Alice Project)

- Flask app at `alice_app.py`; frontend is AJAX-loaded Windows 98-styled panels
- Existing price data endpoint: `POST /osrs/item-price-graph` (returns rendered HTML — to be
  supplemented with a new raw-data JSON endpoint, see §Backend below)
- Existing JS modules: `static/js/` (no build system; plain ES6 modules loaded via `<script>`)
- Existing CSS: `static/css/` uses Windows 98 widget classes (`w98-button`, `w98-input`)
- Graphs are opened inside draggable windows managed by `window_manager.js`
- The entry point for item graphs is `item_search.html` → `loadPriceGraph()` call

### Files to create

| Path | Purpose |
| ----- | --------- |
| `static/js/osrs_graphs.js` | The library (all graph classes) |
| `static/css/osrs_graphs.css` | Container + control styling |

### Files to modify

| Path | Change |
| ----- | -------- |
| `src/website/osrs_router.py` | Add `POST /osrs/item-graph-data` endpoint |
| `templates/osrs/item_search.html` | Replace `loadPriceGraph()` to use new library |
| `templates/osrs/price_graph_modal.html` | Replace Chart.js render with library container HTML |

---

## Database Schema (read-only reference)

All tables live in the `prices` schema of the `osrs` PostgreSQL database.

### `prices.{item_id}_latest`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `timestamp` | psql timestamp | When the record was inserted |
| `high` | int | Most recent high-side trade price (GP) |
| `highTime` | bigint | Unix ms when that trade occurred |
| `low` | int | Most recent low-side trade price (GP) |
| `lowTime` | bigint | Unix ms when that trade occurred |

No volume data. Each row is one API snapshot (roughly every 60 seconds).

### `prices.{item_id}_5min` and `prices.{item_id}_1h`

| Column | Type | Notes |
| ------ | ---- | ----- |
| `timestamp` | psql timestamp | Start of the interval |
| `avgHighPrice` | int | Volume-weighted average high price |
| `avgLowPrice` | int | Volume-weighted average low price |
| `highPriceVolume` | int | Items traded at the high price in this interval |
| `lowPriceVolume` | int | Items traded at the low price in this interval |

---

## Backend: New Data Endpoint

Add to `src/website/osrs_router.py`:

```
POST /osrs/item-graph-data
```

### Request JSON

```json
{
  "item_id":    2,
  "start_date": "2025-06-01T00:00:00",
  "end_date":   "2025-06-11T00:00:00",
  "table_type": "5min"
}
```

`table_type` must be one of `"latest"`, `"5min"`, `"1h"`.
`end_date` defaults to `datetime.now()` if omitted.

### Success Response

```json
{
  "status": "success",
  "item_name": "Cannonball",
  "table_type": "5min",
  "records": [
    {
      "timestamp": "2025-06-01T00:05:00",
      "high":      155,
      "low":       150,
      "highVol":   4200,
      "lowVol":    3100
    }
  ]
}
```

Field mapping from database columns:

| Response field | `latest` source | `5min`/`1h` source |
| -------------- | --------------- | ------------------ |
| `timestamp` | `timestamp` (ISO) | `timestamp` (ISO) |
| `high` | `high` | `avgHighPrice` |
| `low` | `low` | `avgLowPrice` |
| `highVol` | `null` | `highPriceVolume` |
| `lowVol` | `null` | `lowPriceVolume` |

`highVol` and `lowVol` are `null` for `latest` table records.

### Error Response

```json
{ "status": "error", "message": "No data available for the specified range" }
```

---

## Library Architecture (`static/js/osrs_graphs.js`)

Single file, ES6 class syntax, no imports, no build step. Exported to `window` so templates can
call it directly.

```
OSRSGraphBase          — shared canvas utilities, axis math, tooltip logic
  ↳ OSRSPriceLineGraph — line graph with price controls
  ↳ OSRSVolumeBarGraph — bar graph with volume controls
```

### Constructor signature — Price Graph

```js
new OSRSPriceLineGraph(containerId, itemId, options)
```

- `containerId` — ID of the `<div>` to render into (library creates all child elements)
- `itemId` — integer item ID; library constructs its own API calls
- `options` — optional overrides: `{ defaultTableType, defaultTimePeriod, defaultAvgWindow }`

### Constructor signature — Volume Graph

```js
new OSRSVolumeBarGraph(containerId, itemId, options)
```

Same shape as above. `defaultTableType` must be `"5min"` or `"1h"` (no `"latest"`).

### Public methods (both classes)

```js
graph.render()         // fetch data and draw; called automatically on construction
graph.destroy()        // remove all DOM children, cancel pending fetches
```

---

## Price Line Graph

### Controls (rendered above the canvas)

Three control rows, each a flex row of `w98-button` elements. Active button gets class
`w98-button-active` (depressed/highlighted state).

**Row 1 — Source Data Interval**

| Label | Value | Notes |
| ------- | ------- | ------- |
| Latest | `latest` | Sub-minute trade snapshots |
| 5 min | `5min` | 5-minute aggregated intervals |
| 1 hr | `1h` | 1-hour aggregated intervals |

**Row 2 — Time Period**

| Label | Value | Default? |
| ------- | ------- | --------- |
| 1 hr | `1h` | |
| 6 hr | `6h` | |
| 1 day | `1d` | ✓ |
| 1 month | `1mo` | |
| 1 year | `1y` | |
| Custom… | `custom` | opens two datetime-local inputs |

When Custom is selected, show two `<input type="datetime-local">` fields (Start / End) and an
Apply button. Dismiss them when any other period button is clicked.

**Row 3 — Averaging Window**

Groups multiple raw records into a single displayed data point.

| Label | Min interval | Compatible source |
| ------ | ------------- | ------------------- |
| 1 min | 1m | latest |
| 5 min | 5m | latest, 5min |
| 15 min | 15m | latest, 5min |
| 1 hr | 1h | latest, 5min, 1h |
| 3 hr | 3h | latest, 5min, 1h |
| 1 day | 1d | latest, 5min, 1h |

When the source changes, clamp the averaging window to the smallest compatible value (e.g. if
source switches to `1h`, minimum window is `1h`). Disable incompatible buttons (greyed out,
unclickable).

### Canvas layout

```
┌──────────────────────────────────────────────────┐
│  [controls row 1]                                │
│  [controls row 2]                                │
│  [controls row 3]                                │
├───────────┬──────────────────────────────────────┤
│           │                 graph area           │
│  y-axis   │                                      │
│  labels   │    · · · · · · · · · · · · · ·       │
│           │                                      │
│           ├──────────────────────────────────────┤
│           │  x-axis labels                       │
└───────────┴──────────────────────────────────────┘
```

Padding constants (suggested): left=70px, right=20px, top=20px, bottom=40px.

### Rendering — data series

- **High price line**: `#FF8C00` (orange), 2px stroke
- **Low price line**: `#3A8FD4` (blue), 2px stroke
- Each data point: filled circle, radius=4px, same color as its line
- Lines connect circles in time order (no smoothing/bezier)
- Both lines drawn on the same canvas

### Rendering — Y axis (price)

1. Find `minPrice = min(all high + low values in view)`
2. Find `maxPrice = max(all high + low values in view)`
3. Round `minPrice` down to nearest integer; round `maxPrice` up to nearest integer.
4. Draw exactly **6 horizontal grid lines** evenly spaced between `minPrice` and `maxPrice`:

   ```
   step = (maxPrice - minPrice) / 5
   lines at: minPrice, minPrice+step, ..., maxPrice
   ```

5. Each line: `#D0D0D0` (light gray), 1px, dashed (4px dash / 4px gap)
6. Y-axis labels: price values formatted with `toLocaleString()` + " gp", right-aligned in the
   left padding area, vertically centered on each grid line, 11px sans-serif

### Rendering — X axis (time)

Given the time range `[startMs, endMs]` (milliseconds):

1. Compute candidate intervals in ms (smallest to largest):

   ```
   1m=60000, 5m=300000, 15m=900000, 30m=1800000,
   1h=3600000, 3h=10800000, 6h=21600000, 12h=43200000,
   1d=86400000, 1w=604800000, 1mo=2592000000
   ```

2. For each candidate (iterate largest-to-smallest):

   ```
   divisions = floor((endMs - startMs) / intervalMs)
   if 4 ≤ divisions ≤ 7: use this interval; break
   ```

   If no interval gives 4–7, choose the one whose `divisions` is closest to 5.

3. Snap the first tick to the nearest clean multiple of the chosen interval ≥ `startMs`.
   Place subsequent ticks every `intervalMs` until `> endMs`.

4. Each tick line: `#D0D0D0`, 1px, dashed, full graph height
5. X-axis labels below the graph area:
   - If interval < 1 day: format as `HH:MM` (omit date when all ticks share the same date) or
     `MMM D HH:MM` when the range crosses a date boundary
   - If interval ≥ 1 day: format as `MMM D`
   - If interval ≥ 1 month: format as `MMM YYYY`
   - Labels centered on each tick, 11px sans-serif

### Rendering — canvas sizing

Fit the canvas to the container `<div>` width. Listen to `ResizeObserver` on the container;
redraw on size changes (debounce 100ms). Default height: 320px (configurable via option
`graphHeight`).

---

## Volume Bar Graph

### Controls (rendered above the canvas)

Two control rows:

**Row 1 — Source Data Interval** (no "Latest" option)

| Label | Value |
| ------ | ------- |
| 5 min | `5min` |
| 1 hr | `1h` |

**Row 2 — Time Period** — same options as price graph (1hr, 6hr, 1day, 1month, 1year, Custom)

**Row 3 — Averaging Window** — same options as price graph, but minimum is `5min` (no `1min`)

### Bar rendering

For each displayed data point (after averaging is applied):

- Positive bar upward from zero: `highPriceVolume` in `#FF8C00` (orange)
- Negative bar downward from zero: `lowPriceVolume` in `#3A8FD4` (blue), rendered as a positive
  magnitude going downward

Bar width = 80% of the x-distance between consecutive data points.

When bars are too narrow to see (< 2px), collapse to vertical tick marks of the same color.

### Y axis

Same 6-line algorithm as price graph, but values are volume counts. Format labels as integers
with `toLocaleString()` (no "gp" suffix). Show absolute values on both sides of zero; the y-axis
range spans from `-maxLowVol` to `+maxHighVol` (i.e. the zero line is centered if volumes are
equal, otherwise offset).

Draw a solid `#222222` 1px horizontal line at y=0.

### X axis

Same algorithm as price graph.

---

## Averaging Logic (shared)

### Grouping algorithm

Given a sorted array of raw records and a window size `W` (in ms):

```
buckets = {}
for record in records:
  bucket_key = floor(record.timestampMs / W) * W
  buckets[bucket_key].push(record)

display_points = []
for (bucket_time, bucket_records) in buckets:
  display_points.push({
    timestampMs: bucket_time,
    high: volumeWeightedAvg(bucket_records, 'high', 'highVol'),
    low:  volumeWeightedAvg(bucket_records, 'low', 'lowVol'),
    highVol: sum(bucket_records, 'highVol'),
    lowVol:  sum(bucket_records, 'lowVol'),
    rawRecords: bucket_records   // kept for tooltip
  })
```

For `latest` data (no volume), use plain average instead of volume-weighted average.

### Tooltip — hover state

When the mouse is within 12px (x-axis) of a data point's x-coordinate, show a floating tooltip:

```
┌─────────────────────────────────────────┐
│  Thu Jun 5, 14:30 — 14:35               │  ← bucket label
│                                          │
│  High  Low   Time                        │  ← header (sortable)
│  155   150   Thu Jun 5, 14:31            │
│  157   149   Thu Jun 5, 14:33            │
│  156   151   Thu Jun 5, 14:34            │
└─────────────────────────────────────────┘
```

- Ordered by time (ascending) by default
- The tooltip is a `<div>` positioned absolutely over the canvas, not drawn on canvas
- Tooltip appears on `mousemove`; disappears on `mouseleave` (unless pinned)

### Tooltip — pinned state

Clicking a data point **pins** the tooltip. While pinned:

- Tooltip stays visible even as the mouse moves away
- Add two sort buttons to the tooltip header: **Time ↑** and **Price ↓**
  - Time sort: ascending by raw record timestamp
  - Price sort: descending by high price (or volume for the volume graph)
- Add a small **✕** close button to dismiss the pin
- Multiple tooltips can be pinned simultaneously (each click on a different point adds a new
  pinned tooltip)

Tooltip styling: white background, 1px solid `#888`, box-shadow `2px 2px 0 rgba(0,0,0,0.2)`,
11px `monospace` font, `z-index: 10100`. Match the Windows 98 aesthetic.

---

## Loading and Error States

While the API fetch is in progress, draw centered in the canvas area:

```
Loading price data…
```

(gray text, same font as axis labels)

If the fetch fails or returns no data:

```
No data available for this time range.
```

(same position, red text)

---

## CSS (`static/css/osrs_graphs.css`)

Style the control rows and container to match Windows 98 aesthetic:

```css
.osrs-graph-container {
  /* matches existing .window-content padding */
}

.osrs-graph-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}

.w98-button-active {
  /* depressed look: inset border, slight background shift */
  border-color: #808080 #ffffff #ffffff #808080;
  background-color: #c0c0c0;
  padding-top: 3px;
  padding-left: 3px;
}

.osrs-graph-canvas-wrapper {
  position: relative;  /* tooltip positioning anchor */
}

.osrs-graph-tooltip {
  position: absolute;
  pointer-events: none;
  background: white;
  border: 1px solid #888;
  box-shadow: 2px 2px 0 rgba(0,0,0,0.2);
  font: 11px monospace;
  padding: 6px 8px;
  z-index: 10100;
  min-width: 220px;
}

.osrs-graph-tooltip.pinned {
  pointer-events: auto;  /* allow clicking sort buttons */
}
```

---

## Template Integration

In `templates/osrs/price_graph_modal.html` (or a new template), replace the Chart.js canvas with:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/osrs_graphs.css') }}">
<script src="{{ url_for('static', filename='js/osrs_graphs.js') }}"></script>

<div id="osrs-price-graph-{{ item_id }}" class="osrs-graph-container"></div>
<div id="osrs-volume-graph-{{ item_id }}" class="osrs-graph-container"></div>

<script>
  new OSRSPriceLineGraph('osrs-price-graph-{{ item_id }}', {{ item_id }});
  new OSRSVolumeBarGraph('osrs-volume-graph-{{ item_id }}', {{ item_id }});
</script>
```

Both graphs are independent; they can be placed in separate tabs or stacked vertically.

---

## Behavioral Constraints

- All state (selected source, period, averaging) is local to the class instance — no globals
- A new `render()` call cancels any in-flight `fetch` (use `AbortController`)
- The library never calls `eval` or `innerHTML` with user-sourced data
- Price and GP values are always integers (the DB stores them as integers); do not display
  decimal places
- Volume values are also integers; format with `toLocaleString()` and no suffix
- The averaging tooltip list is scrollable (`max-height: 260px; overflow-y: auto`) when it
  contains more than ~10 rows

---

## Reference: Existing API to Reuse

The new `/osrs/item-graph-data` endpoint should reuse the existing Python path:

```python
from src.osrs.item_properties import osrsItemProperties

item = osrsItemProperties(item_id=item_id, load_data=False)
records = item.get_prices_between_dates(
    start_date=start_date,
    end_date=end_date,
    table_type=table_type,
    sort_desc=False,
)
```

`load_data=False` skips the three `get_latest_*` calls made in `__init__` (they are not needed
when only fetching historical ranges) — avoids three extra DB queries per request.

Field extraction per `table_type`:

```python
def format_record(record, table_type):
    ts = record["timestamp"]
    if table_type == "latest":
        return {
            "timestamp": ts.isoformat(),
            "high": record.get("high"),
            "low":  record.get("low"),
            "highVol": None,
            "lowVol":  None,
        }
    else:  # 5min or 1h
        return {
            "timestamp": ts.isoformat(),
            "high": record.get("avgHighPrice"),
            "low":  record.get("avgLowPrice"),
            "highVol": record.get("highPriceVolume"),
            "lowVol":  record.get("lowPriceVolume"),
        }
```
