# HerblorePotionCalc: Generic OSRS Potion Production Calculator

## Overview

The `HerblorePotionCalc` class is a reusable, generic calculator for analyzing the production economics of any OSRS Herblore potion. Originally developed for the [[/#prayerregen-goading]] calculator, this class was refactored into a standalone module to enable analysis of any herb + secondary ingredient combination without code duplication.

This architectural decision transforms potion profitability analysis from bespoke, single-purpose scripts into a flexible framework where new potions can be analyzed by simply instantiating the class with different item IDs - no reimplementation of calculation logic required.

## Design Philosophy

### Separation of Concerns

The refactoring separates three distinct responsibilities:

**Core Calculation Logic** (HerblorePotionCalc): Implements the universal mechanics of OSRS Herblore production - ingredient optimization, equipment bonuses, multi-timeframe pricing, profit calculations. This logic applies identically whether calculating Goading potions, Super Combats, or any other herb-based potion.

**Potion-Specific Configuration** (Consumer code): Provides the item IDs and parameters that define a specific potion - which herbs, which secondaries, which finished products. This lightweight configuration layer is all that differs between potion types.

**Presentation Layer** (Display classes): Handles Flask template rendering, data formatting, and user interface concerns. Each specific calculator (GoadingRegens, SuperCombats, etc.) manages its own presentation while delegating calculation to shared HerblorePotionCalc instances.

This separation means calculation improvements automatically benefit all potion calculators, while each calculator retains independent control over its presentation.

### Multi-Timeframe Architecture

The class architecture commits to four timeframe windows throughout its design:

- 5-minute data for immediate market conditions
- 15-minute data for near-term planning
- 1-hour data for short-term trends
- 3-hour data for sustained production decisions

Every price fetch, cost calculation, and profit projection maintains separate values for each timeframe. This design choice reflects OSRS's volatile Grand Exchange markets where profitability can shift dramatically within minutes, making single-timeframe analysis inadequate for informed decision-making.

### Fail-Safe Data Handling

The class employs defensive programming throughout, treating missing or invalid price data as expected normal conditions rather than exceptional errors. All price-dependent calculations use fallback chains (low → average → 0 or inf as appropriate) and None checks to prevent crashes when API data is incomplete.

This robustness ensures the calculator remains functional even when specific items have thin trading volume, recent API outages, or market manipulation that creates data gaps.

## Class Parameters

### Initialization Signature

```python
HerblorePotionCalc(
    goggles: bool = True,
    alchem: bool = True,
    potions_per_hour: int = 2500,
    primary_herb_id: int = None,
    primary_gherb_id: int = None,
    primary_unf_id: int = None,
    secondary_item_id: int = None,
    product_item_id: int = None,
    product_item_doses: int = 4,
)
```

### Equipment Flags

**goggles**: Whether to model Prescription Goggles (10% secondary ingredient save rate, represented as 11.111%). When enabled, reduces effective secondary cost and adds fractional Amulet of Chemistry costs for successful procs.

**alchem**: Whether to model Alchemist's Amulet (15% chance for +1 dose). When enabled, increases average yield from 3.0 to 3.15 doses per production cycle.

These boolean flags allow the calculator to model four equipment configurations: no bonuses, goggles only, amulet only, or both items (the recommended optimal configuration).

### Primary Herb IDs

**primary_herb_id**: Item ID for the clean (non-grimy) version of the primary herb. Example: 255 for Harralander.

**primary_gherb_id**: Item ID for the grimy version of the primary herb. Example: 205 for Grimy harralander.

**primary_unf_id**: Item ID for the unfinished potion (herb + vial of water, no secondary). Example: 97 for Harralander potion (unf).

The calculator evaluates all three forms, incorporating applicable preparation fees (cleaning grimy herbs, making unfinished potions), and automatically selects the minimum-cost option per timeframe. This optimization often yields 500-2000gp savings per inventory depending on current market arbitrage opportunities.

### Secondary and Product IDs

**secondary_item_id**: Item ID for the secondary ingredient added to unfinished potions. Example: 29993 for Aldarium. The calculator applies goggle savings to this ingredient if enabled.

**product_item_id**: Item ID for the completed potion product. Example: 30137 for Goading potion (4). This represents the sellable finished good whose price determines revenue.

**product_item_doses**: Number of doses in the finished product item. Default 4 accounts for most OSRS potions being 4-dose when purchased/sold on the GE. The calculator divides finished potion price by this value to determine price-per-dose for revenue calculations.

### Production Rate

**potions_per_hour**: Expected production rate for sustained grinding. Default 2,500 reflects realistic attentive gameplay speed for most potions. This parameter converts per-potion profit into hourly GP rates for comparison against alternative money-making methods.

## Calculation Pipeline

### Stage 1: Production Cost Calculation

The `_calculate_production_cost()` method orchestrates cost analysis through two substages:

#### Primary Herb Optimization

`_calc_cheapest_primary()` evaluates all three primary herb forms:

**Clean Herb Pathway**:

- Cost: Market price + 200gp potion-making fee + Vial of Water price
- Represents buying clean herbs and paying Zahur for unfinished potion creation

**Grimy Herb Pathway**:

- Cost: Market price + 200gp cleaning fee + 200gp unfinished potion fee + Vial of Water price
- Represents buying grimy herbs, which require cleaning before Zahur can make unfinished potions

**Unfinished Potion Pathway**:

- Cost: Market price (no fees)
- Represents buying pre-made unfinished potions, ready for secondary ingredient addition

For each pathway and timeframe, the method:

1. Fetches appropriate prices via `_get_low_price()`
2. Adds applicable Zahur fees and Vial of Water costs
3. Compares total costs across pathways
4. Selects minimum cost option
5. Stores both processed cost (with fees) and raw price (without fees) for display

This optimization runs independently for each timeframe, as market dynamics may favor different forms at different time windows.

#### Secondary Cost Calculation

`_calc_secondary_cost()` models secondary ingredient consumption with equipment modifiers:

**Without Goggles**:

- Cost: 1.0 × secondary ingredient price
- Straightforward - one secondary consumed per production

**With Goggles**:

- Effective consumption: 0.8889 × secondary price (reflecting 11.11% save rate)

The method stores raw secondary prices separately from production costs, enabling the display layer to show both the market price and the effective cost after equipment savings.

#### Product Output Calculation

**[Alchemist's Amulet](https://oldschool.runescape.wiki/w/Alchemist%27s_amulet)**:

- The Alchemist's amulet has a 15% chance to produce a potion with 1 extra dose at the cost of 1/10th of an [Amulet of chemistry](https://oldschool.runescape.wiki/w/Amulet_of_chemistry) when it procs. This is represented by multiplying the chance to proc by 1/10th of the cost of an Amulet of chemistry, and adding the result to the production cost.

### Stage 2: Revenue Calculation

The `_calculate_revenue()` method determines gross income per production cycle:

1. **Fetch Finished Potion Prices**: Retrieves high prices (or average as fallback) via `_get_high_price()`, representing realistic selling prices for immediate GE sales

2. **Calculate Price Per Dose**: Divides finished potion price by `product_item_doses` (typically 4), yielding the value of a single dose

3. **Apply Yield Bonus**: Multiplies price-per-dose by average doses produced:
   - Without amulet: 3.0 doses
   - With amulet: 3.15 doses (3.0 base + 0.15 from 15% proc rate)

4. **Store Revenue Metrics**: Saves finished potion prices, price-per-dose, and total revenue per production for all four timeframes

This calculation accurately models that while players produce 3-dose potions, the 15% amulet proc rate yields 4-dose potions, increasing average value without increasing ingredient costs (beyond marginal amulet charges).

### Stage 3: Profit Calculation

The `_calculate_profit()` method computes net profit and hourly rates:

**Per-Production Profit**:

```
profit = (revenue × (1 - sales tax %)) - production_cost
```

The 0.98 multiplier applies the 2% Grand Exchange sales tax, deducting this from gross revenue to calculate realistic net profit. There is a short list of [items exempt from the tax](https://oldschool.runescape.wiki/w/Grand_Exchange#Exempt_from_tax) that is not taken into account. As of the time writing this, the only potion on this list is the [Energy Potion](https://oldschool.runescape.wiki/w/Energy_potion) which is not something I am hugely concerned about.

**Hourly GP Rate**:

```
gp_per_hour = profit × potions_per_hour
```

Scaling per-production profit by expected hourly production rate yields the money-making rate, enabling comparison against other activities like PvM, skilling, or merchanting.

Both calculations run for all four timeframes, providing graduated temporal perspectives on profitability.

## Key Methods

### Price Retrieval Methods

**`_get_low_price(item)`**: Returns tuple of (5min, 15min, 1h, 3h) low prices with fallback to average prices. Used for ingredient costs to model patient buying below market value.

**`_get_high_price(item)`**: Returns tuple of (5min, 15min, 1h, 3h) high prices with fallback to average prices. Used for finished product revenue to model immediate selling at premium prices.

The distinction between low and high prices implements a conservative "buy low, sell high" model that reflects realistic trading rather than best-case scenarios unlikely to materialize in actual gameplay.

### Cost Analysis Methods

**`_get_primary_cost(item, make_unf, clean_grimy)`**: Calculates total cost for one primary herb form including applicable fees:

- Adds 200gp + Vial of Water if `make_unf` is True
- Adds 200gp if `clean_grimy` is True
- Returns cost tuple for all four timeframes

**`_get_raw_primary_cost(item)`**: Returns just the market prices without any fees. Used to display raw ingredient costs separately from processed costs, helping users understand where fees apply.

These separate raw and processed cost methods enable the display layer to show both "Grimy harralander: 450gp" and "Processed cost: 850gp", making fee impacts transparent.

### Utility Methods

**`format_value(value)`**: Converts numeric values to display strings:

- Formats normal numbers using `format_currency()` helper (e.g., "1,234 gp")
- Handles special values: inf, -inf, None, "nan" all display as "N/A"
- Ensures consistent formatting throughout the interface

This centralized formatting prevents scattered string-building logic and guarantees uniform currency display.

## Usage Example

### Basic Instantiation

```python
from src.osrs.calcs.herblore_potion_calc import HerblorePotionCalc

# Calculate Goading Potion economics
goading_calc = HerblorePotionCalc(
    goggles=True,
    alchem=True,
    potions_per_hour=2500,
    primary_herb_id=255,      # Harralander
    primary_gherb_id=205,     # Grimy harralander
    primary_unf_id=97,        # Harralander potion (unf)
    secondary_item_id=29993,  # Aldarium
    product_item_id=30137,    # Goading potion (4)
    product_item_doses=4,
)

goading_calc.calc()
```

### Accessing Results

After calling `calc()`, all attributes are populated:

```python
# Production costs per timeframe
goading_calc.production_cost_5min
goading_calc.production_cost_15min
goading_calc.production_cost_1h
goading_calc.production_cost_3h

# Revenue per timeframe
goading_calc.revenue_5min
# ... etc

# Profit per production
goading_calc.profit_5min
# ... etc

# Hourly GP rates
goading_calc.gp_per_hour_5min
# ... etc

# Optimal primary herb info
goading_calc.cheapest_primary_5min.name  # e.g., "Harralander potion (unf)"
goading_calc.cheapest_primary_raw_5min   # Raw price without fees
```

### Creating Multiple Calculators

The class design enables easy comparative analysis:

```python
# Calculate Prayer Regen economics
p_regen_calc = HerblorePotionCalc(
    goggles=True,
    alchem=True,
    potions_per_hour=2500,
    primary_herb_id=30097,    # Huasca
    primary_gherb_id=30094,   # Grimy huasca
    primary_unf_id=30100,     # Huasca potion (unf)
    secondary_item_id=29993,  # Aldarium (same as Goading)
    product_item_id=30125,    # Prayer regeneration potion (4)
    product_item_doses=4,
)

p_regen_calc.calc()

# Compare profitability
if goading_calc.gp_per_hour_1h > p_regen_calc.gp_per_hour_1h:
    print("Goading is more profitable")
else:
    print("Prayer Regen is more profitable")
```

This comparative pattern is exactly how the [[/#prayerregen-goading]] calculator implements side-by-side analysis.

## Technical Details

### Constants and Configuration

The module uses environment defined constants:

```python
ZAHUR_FEE = int(os.getenv("ZAHUR_FEE", default=200))                          # GP cost for Zahur services
GOGGLE_CHANCE = float(os.getenv("PRES_GOGGLES_CHANCE", default=0.1111))       # Prescription Goggles save rate (1/9)
CHEM_CHANCE = float(os.getenv("ALC_AMUL_CHANCE", default=0.15))               # Alchemist's Amulet bonus rate
GE_TAX = float(os.getenv("GE_TAX", default=0.02))                # Grand Exchange sales tax
```

These constants centralize game balance parameters, making future updates trivial when Jagex adjusts mechanics.

### Amulet of Chemistry Cost Tracking

The module maintains global cost estimates for Amulet of Chemistry:

```python
AOC_ID = 21163
aoc_item = osrsItemProperties(AOC_ID)

aoc_proc_cost_5min = get_aoc_cost(
    aoc_item.latest_5min_price_low,
    aoc_item.latest_5min_price_average
)
# ... similar for 15min, 1h, 3h
```

The `get_aoc_cost()` function divides amulet price by 10 (charges per amulet), yielding per-charge costs used when calculating goggle proc expenses. This ensures equipment bonuses are properly costed rather than treated as "free."

### State Initialization

The `__init__` method pre-initializes all 48 result attributes (12 metrics × 4 timeframes) to sensible defaults:

- Costs: 0
- Prices: 0
- Profits: 0
- Optimal primary herbs: None
- Optimal primary costs: inf (so any real cost beats default)

This defensive initialization prevents AttributeError crashes if display code accesses results before `calc()` runs, and ensures numeric operations don't fail on uninitialized values.

### osrsItemProperties Integration

The class heavily relies on `osrsItemProperties` for real-time GE price data:

```python
self.product_item = osrsItemProperties(self.product_item_id)
self.primary_herb = osrsItemProperties(self.primary_herb_id)
# ... etc
```

Each `osrsItemProperties` instance provides attributes like:

- `latest_5min_price_low`
- `latest_5min_price_high`
- `latest_5min_price_average`
- (Similar for 15min, 1h, 3h)

This dependency means calculator accuracy depends on the freshness and quality of underlying price API data. Regular price cache updates are essential for reliable results.

## Error Handling and Robustness

### None-Safe Price Operations

All price comparisons use defensive None checks:

```python
price_5min = price_5min if price_5min is not None else inf
```

Using `inf` for missing price data ensures:

- Invalid options automatically lose in minimum-cost comparisons
- Invalid revenue defaults to 0 (since 0 / inf → 0)
- No crashes or exceptions from None arithmetic

This approach treats incomplete data as "unavailable" rather than "broken," maintaining graceful degradation.

### Infinity Handling in Display

The `format_value()` method explicitly handles mathematical edge cases:

```python
if value is None or value == inf or value == -inf or value == "nan":
    formatted_value = "N/A"
```

This prevents displaying "inf gp" or "NaN gp" in the UI, instead showing clean "N/A" placeholders that clearly indicate missing data without alarming users.

### Fallback Price Chains

Both `_get_low_price()` and `_get_high_price()` implement fallback logic:

```python
item.latest_5min_price_low if item.latest_5min_price_low else item.latest_5min_price_average
```

This "low → average" pattern ensures a price is available even when specific timeframe brackets have incomplete data, maximizing calculator utility despite imperfect API coverage.

## Computational Efficiency

### Lazy Evaluation Trade-offs

The class uses eager evaluation - `calc()` computes all metrics immediately rather than on-demand. This design choice prioritizes simplicity and debuggability over memory efficiency, accepting that 48 pre-computed values (12 metrics × 4 timeframes) consume negligible memory compared to API response caching.

For applications not needing all metrics and not wanting to waste memory, updates to calc() or new methods will need to be made.

## Limitations and Assumptions

### Fixed Equipment Bonuses

The calculator models goggles and amulet as binary on/off flags with fixed proc rates. It cannot currently model:

- Partial equipment setups (e.g., using the amulet but not goggles)
- Future equipment with different proc rates
- Player-specific success rates affected by boosts or special mechanics

Adding variable bonus parameters would enable more sophisticated modeling but complicate the interface for marginal benefit given current game mechanics.

### Linear Scaling Assumptions

The `gp_per_hour` calculation assumes:

- Constant production rate (no fatigue, breaks, or efficiency degradation)
- Unlimited capital (able to fund arbitrary production volumes)
- Stable market prices (timeframe prices persist throughout grinding session)

Real-world results may vary due to player stamina, bank standing time, GE buy/sell limits, and price volatility. The calculator provides idealized projections rather than guaranteed outcomes. The `potions_per_hour` argument can be changed to better reflect a player's particular playstyle.

### Grand Exchange Instant Liquidity

Profit calculations assume:

- Ingredients purchase instantly at low prices
- Finished products sell instantly at high prices
- No GE buy/sell limits impact production volume
- No significant market impact from player's trading

High-volume producers or low-liquidity items may experience worse prices, slower trades, or hit daily GE limits, reducing actual profitability below calculator projections.

## Future Enhancement Opportunities

Several potential improvements could extend calculator capabilities:

**Support for Alternative Services**: Model Wesley's crushing service (50gp/item) to increase secondary ingredient options, selecting optimal workflow based on current prices.

**Profit Confidence Intervals**: Use historical price volatility to generate ±X% confidence bounds on profit projections, quantifying risk for different potions.

**Batch Production Planner**: Given available capital, calculate optimal ingredient purchases, expected yields accounting for equipment procs, and total profit for planned production runs.

**Multi-Potion Portfolio Analysis**: Compare multiple potions simultaneously, ranking by profitability and highlighting switching points when market conditions shift optimal choices.

## Source Files

- **Module**: [herblore_potion_calc.py](/files/showcase/herblore_potion_calc.py)
