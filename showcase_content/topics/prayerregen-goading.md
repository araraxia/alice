# Goading & Prayer Regeneration Potion Production Calculator

## NOTE

This got refactored into [[/#herblore-potion-calc]] for modularity sake, and is remaining as historic documentatin.

## Overview

The Goading & Prayer Regeneration Potion share the same expensive secondary ingredient, [Aldarium](https://oldschool.runescape.wiki/w/Aldarium). Thanks to the secondary's high price, we can take advantage of the effects of the [Prescription Goggles](https://oldschool.runescape.wiki/w/Prescription_goggles) and [Alchemist's amulet](https://oldschool.runescape.wiki/w/Alchemist%27s_amulet) to turn a profit. Due to the volitility of this method, it is recommended to only create these potions in a quantity large enough to be statistically significant to avoid losing money.

## What Are Goading and Prayer Regeneration Potions?

Both potions were introduced with the Varlamore expansion and represent new Herblore content with distinct uses:

**[Goading Potions](https://oldschool.runescape.wiki/w/Goading_potion)**: Provide temporary combat stat boosts and special effects useful in specific combat scenarios. The production process creates 3-dose potions by combining Harralander herbs with Aldarium.

**[Prayer Regeneration Potions](https://oldschool.runescape.wiki/w/Prayer_regeneration_potion)**: Offer prayer restoration over a seven minute period, serving as an supplement to traditional prayer restoration methods and typically conserving inventory space in more long-winded content. This potion is created by combining Huasca herbs with Aldarium.

Despite different effects, both potions share identical production mechanics and benefit from the same efficiency equipment, making them natural candidates for comparative profitability analysis within a single interface.

## Production Mechanics

### Base Production Process

The standard Herblore production flow applies to both potions:

1. Obtain a primary herb (Harralander for Goading, Huasca for Prayer Regen)
2. Clean the herb if purchased grimy (200gp Zahur service cost)
3. Create an unfinished potion (200gp Zahur service cost + 1 Vial of Water)
4. Add the secondary ingredient (Aldarium) to complete the potion
5. Receive a 3-dose potion as the base output

This process typically yields 3 doses per production cycle. However, two equipment bonuses significantly alter the economics.

### Prescription Goggles Bonus

Prescription goggles (obtained as a reward from the Colossal Wyrm boss) provide an 11.11% chance to conserve secondary ingredients during potion production. While these goggles initially required 98 Herblore to wear, this restriction was removed, making them accessible to players at any Herblore level.

Statistically, this 11.11% save rate means players consume approximately 0.8889 Aldarium per potion instead of 1.0, providing substantial cost savings on the secondary ingredient. The calculator models this by reducing effective Aldarium usage by 11.11%.

### Alchemist's Amulet Bonus

The Alchemist's Amulet provides a 15% chance to create a potion with one additional dose, so a 4-dose potion instead of a 3-dose potion in this case. This increasing average yield from 3.0 doses to 3.15 doses per production cycle. This increased yield directly improves revenue without increasing ingredient costs (beyond the marginal amulet charge consumption).

The amulet is charged with Amulets of Chemistry, adding 10 charges per amulet, meaning each production that benefits from goggles consumes 1/10th of an amulet. The calculator factors in the cost of using the amulet to accurately represent this cost.

### Combined Equipment Synergy

Together, these two equipment pieces create powerful production bonuses:

- 11.11% reduction in secondary ingredient costs
- 15% increase in dose output

The calculator's strength lies in properly modeling these interactions, including the subtle cost relationship between goggle procs and amulet charge consumption that manual calculations often miss.

## Ingredient Optimization Strategy

### Primary Herb Form Selection

Both Harralander (Goading) and Huasca (Prayer Regen) can be purchased in three states, each with different preparation requirements and market prices:

**Grimy Herb**: Requires both cleaning (200gp Zahur fee) and converting to unfinished potion before use. Typically the cheapest to purchase but has the highest total preparation cost.

**Clean Herb**: Requires converting to unfinished potion (200gp Zahur fee) before adding the secondary. Usually priced between grimy and unfinished.

**Unfinished Potion**: Ready to use immediately - just add Aldarium. Often the most expensive to purchase but saves both preparation fees.

The calculator evaluates all three forms across each timeframe, incorporating preparation fees where applicable, and selects the option yielding the lowest total cost. This optimal selection often changes between timeframes as market dynamics shift different forms in and out of profitability.

## Multi-Timeframe Analysis

### Four-Level Temporal Resolution

Unlike the Super Combat calculator's two timeframes, this tool analyzes four distinct temporal windows:

- **5-Minute Data**: Captures immediate market conditions and very recent price spikes or crashes. Useful for opportunistic production when sudden favorable conditions emerge.

- **15-Minute Data**: Provides near-term market visibility while smoothing out momentary volatility. Represents typical conditions for players starting a production session within the next 15 minutes.

- **1-Hour Data**: Shows established short-term trends, filtering out transient fluctuations. Appropriate for planning production sessions expected to last 30-60 minutes.

- **3-Hour Data**: Reveals longer-term price stability and sustained market conditions. Best for evaluating whether to commit to extended production runs lasting multiple hours.

This graduated temporal analysis enables players to match their planning horizon with appropriate data - short-term opportunists reference 5-minute data, while players planning multi-hour grinds focus on 3-hour averages.

### Price Selection Logic

For ingredient costs, the calculator uses low prices (with average as fallback if low is unavailable), representing achievable purchase prices for patient buyers using limit orders below market value.

For finished potion revenue, it uses high prices (with average as fallback), representing realistic selling prices for immediate sales to active buyers paying premium for instant delivery.

This conservative approach (buy low, sell high) provides realistic profit projections rather than optimistic best-case scenarios that may not materialize in actual trading.

## Cost and Profit Calculations

### Production Cost Breakdown

Each timeframe shows complete production costs including:

**Primary Herb Cost**: Lowest cost among grimy, clean, and unfinished variants, with preparation fees included as applicable. The interface displays which specific form was selected (e.g., "Grimy harralander" or "Harralander potion (unf)") along with its raw price.

**Secondary Ingredient Cost**: Aldarium price reduced by 11.11% to reflect goggle savings, plus 11.11% of the Alchemist's Amulet's fractional cost representing charge consumption when goggles proc.

**Total Production Cost**: Sum of primary and secondary costs, representing the all-in cost to produce one 3-dose potion (before amulet bonus).

### Revenue Calculation

Revenue accounts for the Alchemist's Amulet's yield bonus:

**Doses Produced**: 3.15 average doses (3.0 base + 0.15 from 15% amulet proc rate)

**Price Per Dose**: Finished potion high price divided by 4 (since finished potions are 4-dose)

**Revenue Per Production**: Price per dose × 3.15 doses

This accurately models that while players produce 3-dose potions, 15% of the time they receive a 4-dose potion, increasing average value per production cycle.

### Profit and Hourly Rate

**Profit Per Potion**: (Revenue × 0.98) - Production Cost

The 0.98 multiplier represents the 2% Grand Exchange sales tax, deducted from gross revenue to calculate net profit.

**GP Per Hour**: Profit per potion × Potions per hour (default: 2,500)

The 2,500 potions-per-hour rate represents realistic sustained production speed for attentive players. This hourly projection helps players compare potion production profits against alternative money-making methods.

### Comparative Analysis

The side-by-side presentation of Goading and Prayer Regen calculations enables instant comparative analysis:

- Which potion offers higher profit margins currently?
- How do profit differences vary across timeframes?
- Are both potions profitable, or just one?
- Which potion shows more stable profits across time windows?

These comparisons inform production decisions - players might switch between potions hourly to capture the most favorable markets, or commit to the consistently more profitable option for sustained grinds.

## Technical Implementation

### HerblorePotionCalc Class

The calculator architecture uses a generic `HerblorePotionCalc` class that can model any herb + secondary ingredient potion combination. This class is instantiated twice (once for Goading, once for Prayer Regen) with different parameters:

```
goading_calc = HerblorePotionCalc(
    primary_herb_id=HARRALANDER_ID,
    primary_gherb_id=G_HARRALANDER_ID,
    primary_unf_id=HARRALANDER_UNF_ID,
    secondary_item_id=ALDARIUM_ID,
    product_item_id=GOADING_4_ID,
    ...
)
```

Each calculator instance independently:

1. Fetches item properties for all ingredient variants and the finished product
2. Evaluates primary herb costs across all forms and timeframes
3. Calculates secondary costs with equipment modifiers
4. Determines revenue with yield bonuses
5. Computes profits after taxes
6. Projects hourly rates

### Calculation Pipeline

The `calc()` method orchestrates a three-stage calculation pipeline:

**Stage 1 - Production Costs** (`_calculate_production_cost`):

- Evaluates all primary herb forms via `_calc_cheapest_primary()`
- Selects minimum cost option per timeframe
- Calculates secondary costs with modifiers via `_calc_secondary_cost()`
- Sums to total production cost

**Stage 2 - Revenue** (`_calculate_revenue`):

- Retrieves finished potion high prices
- Divides by 4 to get price per dose
- Multiplies by 3.15 (base 3.0 + 15% amulet bonus)
- Stores revenue per production cycle

**Stage 3 - Profit** (`_calculate_profit`):

- Applies 2% GE tax to revenue (multiply by 0.98)
- Subtracts production costs
- Multiplies by potions-per-hour rate
- Stores both per-potion profit and hourly GP rate

This separation allows clean testing of individual calculation stages and makes the logic easy to audit.

### Template Data Marshaling

The `display()` method marshals calculated data into template-compatible dictionaries:

```python
goading_data = {
    'production_cost_5min': format_currency(...),
    'revenue_5min': format_currency(...),
    'profit_5min': format_currency(...),
    'gp_per_hour_5min': format_currency(...),
    'primary_cost_5min': ...,
    'primary_name_5min': ...,
    ...
}
```

Currency formatting uses the `format_currency()` helper to produce consistent "1,234 gp" strings throughout the interface. This abstraction keeps formatting logic centralized and maintainable.

### Error Handling

Like the Super Combat calculator, extensive None checks prevent crashes when price data is incomplete:

```python
price_5min = price_5min if price_5min is not None else inf
```

Using `inf` for missing values ensures invalid options automatically lose in minimum-cost comparisons, gracefully excluding incomplete data without breaking the calculation pipeline.

## Source Files

- [goading_regens.py](/files/showcase/goading_regens.html)
- [goading_regens.html](/files/showcase/goading_regens.html)

## Future Enhancements

Several improvements could extend the calculator's utility:

- **Break-Even Analysis**: Show the minimum selling price needed to achieve zero profit, helping players set realistic offer prices
- **Historical Profit Charts**: Graph profit margins over days/weeks to identify cyclical patterns and optimal production times
- **Primary Herb Arbitrage Detection**: Flag situations where buying one form and selling another form yields profit independent of potion production
- **Batch Production Planner**: Allow users to specify available capital and calculate optimal ingredient purchases and expected total profit
- **Equipment Requirement Toggle**: Add options to disable goggles/amulet bonuses for players without these items, showing unequipped production economics
- **Mobile-Responsive Layout**: Adapt the dense desktop layout for smartphone viewing without losing critical information
- **Alert System**: Notify users when profit margins exceed threshold values, signaling favorable production opportunities
- **Parallel Potion Expansion**: Extend the framework to cover other paired potions with shared secondary ingredients
