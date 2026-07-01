# Super Combat Potion Profit Calculator

## Overview

Herblore is typically an expensive skill to train, but with the right methods and good margins you can turn a considerable profit. Making Super Combat potions while using Prescription Goggles is one of the methods that can potentially turn a profit, and I wanted a way to quickly and easily calculate the profit margins of each combination of ways to make a super combat potion.

## What Are Super Combat Potions?

Super Combat potions are high-level combination potions in Old School RuneScape that provide temporary boosts to Attack, Strength, and Defence stats simultaneously. They're created by combining four doses of Super Attack, Super Strength, and Super Defence potions with a Torstol herb. These potions are highly valued in combat-focused content like bossing and PvP, making them consistently profitable to produce when ingredient costs are favorable.

The production process requires:

- 4 doses of Super Attack potion
- 4 doses of Super Strength potion  
- 4 doses of Super Defence potion
- 1 Unfinished Torstol potion or clean Torstol

Crucially, players with prescription goggles, which provide a 10% chance to conserve secondary ingredients (the clean Torstol). This substantially reduces average production costs and is factored into all calculator estimates.

Grimy Torstol can be (efficiently) cleaned to become clean Torstol at the cost of 200gp per herb, unfinished Torstol potions can be used in place of clean Torstol and different potion dosages can be decanted into 4 dose potions. This leads to a relatively large number of items that need to be price-checked each time you need to purchase potion materials.

## Ingredient Optimization Strategy

### Multi-Dose Economics

One of the calculator's key insights is that ingredient prices vary significantly based on dose count. The Grand Exchange market treats a Super Strength (1), Super Strength (2), Super Strength (3), and Super Strength (4) as separate items with independent prices. Counter-intuitively, lower-dose potions sometimes trade at better per-dose rates than their full-bottle counterparts, creating arbitrage opportunities.

The calculator evaluates all dose variations for each ingredient type, normalizing costs to a "per-4-dose-equivalent" metric. For example:

- A Super Strength (2) priced at 3,000gp represents 1,500gp per dose
- A Super Strength (4) priced at 7,000gp represents 1,750gp per dose
- The calculator would identify the (2)-dose variant as more cost-effective

This normalization allows fair comparison across all variations, ensuring the tool recommends genuinely optimal purchasing decisions regardless of dose count.

### Torstol Form Selection

Torstol can be purchased in three states: grimy, clean, or as an unfinished potion. Each has different pricing and preparation requirements:

- **Grimy Torstol**: Requires cleaning (200gp Zahur service cost) before use
- **Clean Torstol**: Ready to use, typically more expensive than grimy
- **Unfinished Torstol Potion**: Pre-prepared, often the most expensive when just a clean Torstol will suffice.

The calculator evaluates all three forms, factoring in the processing fees for Grimy Torstol, and selects whichever option yields the lowest effective cost per potion. This ensures players don't overpay for convenience when cheaper preparation options exist.

### Prescription Goggles Integration

The calculator assumes players are wearing prescription goggles which grant a 10% chance to conserve secondary ingredients. Statistically, this means players consume approximately 11.11% fewer secondaries across large production runs.

## Liquidity Filtering

### Volume Requirements

Raw price data can be misleading if trading volume is insufficient. An item might show an attractive price, but if only a handful trade per day, actually purchasing meaningful quantities at that price becomes impractical. The calculator addresses this by enforcing minimum volume thresholds:

- **15-Minute Data**: Requires ≥500 average volume
- **3-Hour Data**: Requires ≥2,000 average volume

Items failing to meet these thresholds are excluded from consideration, even if their prices appear favorable. This ensures recommendations reflect liquid market conditions where players can realistically execute purchases without significantly moving the market price through their buying activity.

### Multi-Timeframe Analysis

The calculator queries both 15-minute and 3-hour rolling average price data from the database. This dual-timeframe approach provides:

- **Short-term visibility**: 15-minute data captures current market conditions and recent price spikes or crashes
- **Long-term stability**: 3-hour data smooths out transient volatility, revealing sustainable price levels

An ingredient qualifies if it meets volume requirements in *either* timeframe, providing flexibility while maintaining liquidity standards. When both timeframes show adequate volume, the calculator preferentially uses 15-minute data (being more current) unless it shows high volatility relative to the 3-hour average.

## Cost and Profit Calculations

### Production Cost Breakdown

Once optimal ingredients are identified, the calculator computes comprehensive production costs across multiple scenarios:

**Standard Production Costs**:

- **15-Minute High**: Cost assuming immediate purchase at current high prices (worst case for buyers)
- **15-Minute Low**: Cost assuming purchase at current low prices (best immediate case)
- **15-Minute Average**: Most likely actual cost for typical market orders
- **3-Hour High/Low/Average**: Same metrics over a longer time horizon

Each scenario accounts for the prescription goggles' secondary ingredient savings and includes Zahur cleaning fees if grimy torstol is the optimal choice.

**Slow Buy Costs**:
The calculator also computes "slow buy" costs, representing a patient purchasing strategy where players place low-ball offers and wait for market dips. These use the low price points from each timeframe, showing the best-case ingredient costs achievable without time pressure.

### Profit Margin Projections

Profit calculations compare production costs against Super Combat potion (4) selling prices across the same timeframes:

**Standard Profits**:

- Sell High vs. Cost High: Conservative estimate when both buying and selling face unfavorable prices
- Sell Low vs. Cost Low: Worst-case scenario (buying at lows but forced to sell at lows)
- Sell Average vs. Cost Average: Most realistic profit expectation under typical conditions

**Slow Buy Profits**:  
Best-case scenario where patient buying accumulates ingredients at low prices, then sells the finished product at high market prices. This represents maximum achievable profit but requires time and capital to execute.

These multi-dimensional projections help players understand profit variance and risk—active traders might target average profits with high volume, while patient players might focus on slow buy strategies for maximum margins.

## Technical Implementation

### Item Properties Integration

The `SuperCombats` class instantiates `osrsItemProperties` objects for all potential ingredients during initialization—12 potion variants (4 dose options x 3 required potion types) and 3 torstol forms. Each object pre-loads comprehensive price and volume data from the database, enabling rapid comparisons without repeated queries.

### Optimization Algorithm

The `find_cheapest_ingredients()` method implements the core optimization logic:

1. **Iterate through recipe**: Loop through each ingredient category and its variants
2. **Filter by volume**: Exclude items failing liquidity thresholds
3. **Normalize costs**: Convert all prices to per-4-dose-equivalent metrics
4. **Apply modifiers**: Factor in goggles savings and Zahur cleaning fees
5. **Track minimums**: Maintain running record of cheapest option per category
6. **Validate completeness**: Ensure all four ingredient types have valid selections

If any ingredient lacks a viable option (no variants meet volume requirements), the entire calculation aborts, preventing invalid recommendations based on incomplete data.

### Multi-Pass Calculations

After determining optimal ingredients, the system performs three sequential calculations:

1. **`get_production_cost()`**: Aggregates ingredient costs with all modifiers applied
2. **`calculate_slow_buy_cost()`**: Computes best-case costs using low prices only
3. **`calculate_profit()`**: Performs margin analysis by comparing costs against selling prices

This separation of concerns keeps each calculation focused and testable, while the sequential dependency chain ensures all required data flows correctly through the analysis pipeline.

### Template Rendering

The `display()` method orchestrates the entire workflow, catching exceptions and providing graceful fallbacks. Successful calculations pass all computed data to the Jinja2 template, which renders the multi-card interface. If errors occur (database connectivity issues, incomplete data), users see a clear error message rather than a broken interface.

## Future Enhancements

Several improvements could extend the calculator's capabilities:

- **Historical Profit Trends**: Graph profit margins over days/weeks to identify cyclical patterns in manufacturing profitability
- **Break-Even Analysis**: Calculate the minimum selling price needed to cover costs, helping players set GE offer prices
- **Batch Production Calculator**: Allow users to specify desired production quantities and calculate total ingredient requirements and expected profits
- **Alert System**: Notify users when profit margins exceed specified thresholds, signaling favorable production windows
- **API Access**: Expose calculator results via REST API for integration into external tools and Discord bots

## Source Files

- [super_combats.py](/files/showcase/super_combats.py)
