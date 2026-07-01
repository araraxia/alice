from math import inf
from flask import render_template
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent  # alice/
if str(ROOT_DIR) not in os.sys.path:
    os.sys.path.append(str(ROOT_DIR))

from src.osrs.item_properties import osrsItemProperties


class SuperCombats:
    def __init__(self):
        # Item properties initialization
        self.sc4_item = osrsItemProperties(item_id=12695) # Super combat potion (4)
        self.ss1_item = osrsItemProperties(item_id=161) # Super strength (1)
        self.ss2_item = osrsItemProperties(item_id=159) # Super strength (2)
        self.ss3_item = osrsItemProperties(item_id=157) # Super strength (3)
        self.ss4_item = osrsItemProperties(item_id=2440) # Super strength (4)
        self.sa1_item = osrsItemProperties(item_id=149) # Super attack (1)
        self.sa2_item = osrsItemProperties(item_id=147) # Super attack (2)
        self.sa3_item = osrsItemProperties(item_id=145) # Super attack (3)
        self.sa4_item = osrsItemProperties(item_id=2436) # Super attack (4)
        self.sd1_item = osrsItemProperties(item_id=167) # Super defence (1)
        self.sd2_item = osrsItemProperties(item_id=165) # Super defence (2)
        self.sd3_item = osrsItemProperties(item_id=163) # Super defence (3)
        self.sd4_item = osrsItemProperties(item_id=2442) # Super defence (4)
        self.grimy_torstol_item = osrsItemProperties(item_id=219)
        self.clean_torstol_item = osrsItemProperties(item_id=269)
        self.unf_torstol_item = osrsItemProperties(item_id=111)

        # Configuration parameters
        self.zahur_clean_price = 200
        self.goggle_save_chance = 0.10  # 10%
        self.reduced_secondaries = 0.11111  # 11.111...%
        self.goggles_equipped = True  # Assume goggles are equipped for calculations

        # Initialize dosages and recipe after all items are created
        self.dosages = {
            "one_dose": {
                "items": [self.ss1_item, self.sa1_item, self.sd1_item],
                "dosage": 1,
            },
            "two_dose": {
                "items": [self.ss2_item, self.sa2_item, self.sd2_item],
                "dosage": 2,
            },
            "three_dose": {
                "items": [self.ss3_item, self.sa3_item, self.sd3_item],
                "dosage": 3,
            },
            "four_dose": {
                "items": [self.ss4_item, self.sa4_item, self.sd4_item],
                "dosage": 4,
            },
        }

        self.recipe = {
            "super_attack": [
                self.sa1_item,
                self.sa2_item,
                self.sa3_item,
                self.sa4_item,
            ],
            "super_strength": [
                self.ss1_item,
                self.ss2_item,
                self.ss3_item,
                self.ss4_item,
            ],
            "super_defence": [
                self.sd1_item,
                self.sd2_item,
                self.sd3_item,
                self.sd4_item,
            ],
            "torstol": [
                self.clean_torstol_item,
                self.grimy_torstol_item,
                self.unf_torstol_item,
            ],
        }

    def find_cheapest_ingredients(
        self,
        vol_min_15m: int = 100,
        vol_min_3h: int = 500,
        goggles: bool = True,
    ):
        """
        When called, this function will return a dictionary of the cheapest ingredients
        for making super combat potions and cleaning torstol, based on recent market data.
        It considers both 5-minute and 1-hour low prices, as well as volume thresholds
        to ensure liquidity. The function also accounts for the effects of wearing
        the "Goggles of the Eye" which provides a chance to save secondary ingredients
        when making potions.
        """
        self.goggles_equipped = goggles
        cheapest_template = {
            "item": None,
            "cost_per_4_doses": inf,
            "quantity": None,
        }

        cheapest = {
            "super_attack": cheapest_template.copy(),
            "super_strength": cheapest_template.copy(),
            "super_defence": cheapest_template.copy(),
            "torstol": cheapest_template.copy(),
        }

        for ingredient, item_data in self.recipe.items():
            for item in item_data:
                item_name = getattr(item, "name", "Unknown")

                # Debug volume data
                vol_15m = getattr(item, "latest_15min_volume_average", None)
                vol_3h = getattr(item, "latest_3h_volume_average", None)

                # Skip items that don't meet volume requirements
                if vol_15m is None and vol_3h is None:
                    continue

                # Item needs good volume in either 5m OR 1h timeframe
                vol_5m_ok = vol_15m is not None and vol_15m >= vol_min_15m
                vol_1h_ok = vol_3h is not None and vol_3h >= vol_min_3h
                if not vol_5m_ok and not vol_1h_ok:
                    continue

                # Debug price data
                price_15m_raw = getattr(item, "latest_15min_price_average", None)
                price_1h_raw = getattr(item, "latest_3h_price_average", None)

                # Handle zero prices by setting them to None instead of inf
                if price_15m_raw == 0:
                    price_15m_raw = None
                if price_1h_raw == 0:
                    price_1h_raw = None

                # Determine dosage based on item dosage
                dosage = 0
                average_quant = 1  # Default quantity for potions

                for dose_name, dose_data in self.dosages.items():
                    if item in dose_data["items"]:
                        dosage = dose_data["dosage"]
                        break

                if not dosage:  # Torstol case
                    # Torstol: 1 per 4-dose potion
                    # With goggles: 11.11% save chance on secondaries
                    goggles_save_chance = (
                        self.reduced_secondaries if self.goggles_equipped else 0
                    )

                    # Calculate effective torstol needed per 4-dose potion
                    # Base: 0.9 torstol per potion (due to 10% save)
                    # With goggles: further reduction by goggles_save_chance
                    effective_torstol_per_potion = 1 - goggles_save_chance
                    
                    # Clean grimy torstol has a fixed NPC price for cleaning
                    if item.item_id == 219:
                        base_15min = (
                            (price_15m_raw + self.zahur_clean_price)
                            if price_15m_raw
                            else None
                        )
                        base_3h = (
                            (price_1h_raw + self.zahur_clean_price)
                            if price_1h_raw
                            else None
                        )
                    else:
                        base_15min = price_15m_raw
                        base_3h = price_1h_raw

                    # Calculate cost per 4-dose potion accounting for save chances
                    price_15min = (
                        (base_15min * effective_torstol_per_potion)
                        if base_15min
                        else None
                    )
                    price_3h = (
                        (base_3h * effective_torstol_per_potion) if base_3h else None
                    )

                else:  # Potion case
                    # Calculate how many of this potion we need to equal 4 doses
                    potions_needed = 4.0 / dosage
                    price_15min = (
                        (price_15m_raw * potions_needed) if price_15m_raw else None
                    )
                    price_3h = (price_1h_raw * potions_needed) if price_1h_raw else None

                # Choose the best available price (prefer 5min if available and stable)
                if price_15min is not None and price_3h is not None:
                    # Both prices available - check for stability
                    diff_15m_3h = abs(price_15min - price_3h)
                    if diff_15m_3h / price_3h > 0.10:
                        calculation_price = price_3h
                    else:
                        calculation_price = price_15min
                elif price_15min is not None:
                    calculation_price = price_15min
                elif price_3h is not None:
                    calculation_price = price_3h
                else:
                    continue

                # Compare with current best
                current_best = cheapest[ingredient].get(
                    "cost_per_4_doses", float("inf")
                )

                if not cheapest[ingredient]["item"] or calculation_price < current_best:
                    # For potions, calculation_price is already the total cost for 4-dose equivalent
                    # For torstol, calculation_price is the effective cost per 4-dose potion
                    if dosage and dosage <= 4:  # This is a potion
                        potions_needed = 4.0 / dosage
                        cheapest[ingredient] = {
                            "item": item,
                            "item_cost": calculation_price,
                            "cost_per_4_doses": calculation_price,
                            "quantity": potions_needed,
                        }
                    else:  # This is torstol
                        cheapest[ingredient] = {
                            "item": item,
                            "item_cost": calculation_price,
                            "cost_per_4_doses": calculation_price,
                            "quantity": effective_torstol_per_potion,
                        }
                else:
                    continue

        missing_ingredients = []
        for ingredient, data in cheapest.items():
            if not data["item"]:
                missing_ingredients.append(ingredient)
            else:
                item_name = getattr(
                    data["item"], "item_name", f"Item {data['item'].item_id}"
                )
                print(
                    f"  - {ingredient}: {item_name} @ {data['cost_per_4_doses']} cost per 4-dose equivalent"
                )

        if missing_ingredients:
            print(
                f"Returning empty dict - missing ingredients: {missing_ingredients}"
            )
            return {}

        return cheapest

    def get_production_cost(self, cheapest_ingredients):
        """
        Calculate production costs for super combat potions using 15-minute and 3-hour
        price data (high, low, average) from the cheapest ingredients.

        Returns a dictionary with cost breakdowns for different timeframes and price types.
        """
        if not cheapest_ingredients:
            return {
                "15min": {"high": 0, "low": 0, "average": 0},
                "3hour": {"high": 0, "low": 0, "average": 0},
                "error": "No ingredient data available",
            }

        costs = {
            "15min": {"high": 0, "low": 0, "average": 0},
            "3hour": {"high": 0, "low": 0, "average": 0},
        }

        for ingredient_type, ingredient_data in cheapest_ingredients.items():
            if not ingredient_data.get("item"):
                print(f"  ❌ Missing item data for {ingredient_type}")
                continue

            item = ingredient_data["item"]
            quantity = ingredient_data.get("quantity", 1)

            print(f"  🧪 Processing {ingredient_type} (quantity: {quantity}):")

            # Get 15-minute prices
            price_15min_high = getattr(item, "latest_15min_price_high", None) or 0
            price_15min_low = getattr(item, "latest_15min_price_low", None) or 0
            price_15min_avg = getattr(item, "latest_15min_price_average", None) or 0

            # Get 3-hour prices
            price_3h_high = getattr(item, "latest_3h_price_high", None) or 0
            price_3h_low = getattr(item, "latest_3h_price_low", None) or 0
            price_3h_avg = getattr(item, "latest_3h_price_average", None) or 0

            # For potions, quantity represents how many potions needed for 4-dose equivalent
            # For torstol, quantity represents the goggles save chance factor
            cost_15min_high = price_15min_high * quantity
            cost_15min_low = price_15min_low * quantity
            cost_15min_avg = price_15min_avg * quantity

            cost_3h_high = price_3h_high * quantity
            cost_3h_low = price_3h_low * quantity
            cost_3h_avg = price_3h_avg * quantity
            cost_15min_avg = price_15min_avg * quantity

            cost_3h_high = price_3h_high * quantity
            cost_3h_low = price_3h_low * quantity
            cost_3h_avg = price_3h_avg * quantity

            # Handle special cases for torstol (add cleaning cost for grimy)
            if ingredient_type == "torstol" and item.item_id == 219:  # Grimy torstol
                cleaning_cost = self.zahur_clean_price * quantity
                cost_15min_high += cleaning_cost
                cost_15min_low += cleaning_cost
                cost_15min_avg += cleaning_cost
                cost_3h_high += cleaning_cost
                cost_3h_low += cleaning_cost
                cost_3h_avg += cleaning_cost
                print(f"    💸 Added cleaning cost: {cleaning_cost}")

            # Add to totals
            costs["15min"]["high"] += cost_15min_high
            costs["15min"]["low"] += cost_15min_low
            costs["15min"]["average"] += cost_15min_avg

            costs["3hour"]["high"] += cost_3h_high
            costs["3hour"]["low"] += cost_3h_low
            costs["3hour"]["average"] += cost_3h_avg

            print(
                f"    📊 15min costs - H:{cost_15min_high}, L:{cost_15min_low}, A:{cost_15min_avg}"
            )
            print(
                f"    📊 3h costs - H:{cost_3h_high}, L:{cost_3h_low}, A:{cost_3h_avg}"
            )

        # Round all values to 2 decimal places
        for timeframe in costs:
            for price_type in costs[timeframe]:
                costs[timeframe][price_type] = round(costs[timeframe][price_type], 2)

        print(f"\n💰 Total production costs:")
        print(
            f"  15min - High: {costs['15min']['high']}, Low: {costs['15min']['low']}, Avg: {costs['15min']['average']}"
        )
        print(
            f"  3hour - High: {costs['3hour']['high']}, Low: {costs['3hour']['low']}, Avg: {costs['3hour']['average']}"
        )

        return costs

    def calculate_slow_buy_cost(self, cheapest_ingredients):
        """
        Calculate production costs using the LOW prices of ingredients for a "slow buy" strategy.
        This represents buying ingredients cheaply over time when prices are favorable.

        Returns costs using low prices for both 15min and 3hour timeframes.
        """
        if not cheapest_ingredients:
            return {
                "15min": {"low": 0},
                "3hour": {"low": 0},
                "error": "No ingredient data available",
            }

        print(f"\n💰 Calculating slow buy costs (low ingredient prices)...")

        costs = {"15min": {"low": 0}, "3hour": {"low": 0}}

        for ingredient_type, ingredient_data in cheapest_ingredients.items():
            if not ingredient_data.get("item"):
                print(f"  ❌ Missing item data for {ingredient_type}")
                continue

            item = ingredient_data["item"]
            quantity = ingredient_data.get("quantity", 1)

            # Get LOW prices for slow buy strategy
            price_15min_low = getattr(item, "latest_15min_price_low", None) or 0
            price_3h_low = getattr(item, "latest_3h_price_low", None) or 0

            # Apply quantity adjustments
            cost_15min_low = price_15min_low * quantity
            cost_3h_low = price_3h_low * quantity

            # Handle special cases for torstol (add cleaning cost for grimy)
            if ingredient_type == "torstol" and item.item_id == 219:  # Grimy torstol
                cleaning_cost = self.zahur_clean_price * quantity
                cost_15min_low += cleaning_cost
                cost_3h_low += cleaning_cost
                print(f"    💸 Added cleaning cost: {cleaning_cost}")

            # Add to totals
            costs["15min"]["low"] += cost_15min_low
            costs["3hour"]["low"] += cost_3h_low

        # Round all values to 2 decimal places
        for timeframe in costs:
            for price_type in costs[timeframe]:
                costs[timeframe][price_type] = round(costs[timeframe][price_type], 2)

        print(f"\n💰 Total slow buy costs:")
        print(f"  15min low: {costs['15min']['low']}")
        print(f"  3hour low: {costs['3hour']['low']}")

        return costs

    def calculate_profit(self, production_costs, slow_buy_costs=None):
        """
        Calculate profit margins for super combat potions by comparing production costs
        with selling prices across different timeframes (15min, 3hour) and price types (high, low, average).
        Also calculates "slow buy" profits if slow_buy_costs are provided.

        Returns a dictionary with profit data for each timeframe and price category.
        """
        if not production_costs or production_costs.get("error"):
            return {
                "15min": {"high": 0, "low": 0, "average": 0},
                "3hour": {"high": 0, "low": 0, "average": 0},
                "slow_buy": {"15min": 0, "3hour": 0},
                "error": "No production cost data available",
            }

        print(f"\n💰 Calculating profit margins...")

        # Get Super Combat potion (4) selling prices
        selling_prices = {
            "15min": {
                "high": getattr(self.sc4_item, "latest_15min_price_high", None) or 0,
                "low": getattr(self.sc4_item, "latest_15min_price_low", None) or 0,
                "average": getattr(self.sc4_item, "latest_15min_price_average", None)
                or 0,
            },
            "3hour": {
                "high": getattr(self.sc4_item, "latest_3h_price_high", None) or 0,
                "low": getattr(self.sc4_item, "latest_3h_price_low", None) or 0,
                "average": getattr(self.sc4_item, "latest_3h_price_average", None) or 0,
            },
        }

        profits = {
            "15min": {"high": 0, "low": 0, "average": 0},
            "3hour": {"high": 0, "low": 0, "average": 0},
            "slow_buy": {"15min": 0, "3hour": 0},
        }

        # Calculate regular profits for each timeframe and price type
        for timeframe in ["15min", "3hour"]:
            for price_type in ["high", "low", "average"]:
                selling_price = selling_prices[timeframe][price_type]
                production_cost = production_costs[timeframe][price_type]
                profit = selling_price - production_cost
                profits[timeframe][price_type] = round(profit, 2)

                print(
                    f"  📊 {timeframe} {price_type}: Sell {selling_price} - Cost {production_cost} = Profit {profit}"
                )

        # Calculate slow buy profits (low ingredient costs vs high selling prices)
        if slow_buy_costs and not slow_buy_costs.get("error"):
            print(
                f"\n💰 Calculating slow buy profits (low costs vs high sell prices)..."
            )
            for timeframe in ["15min", "3hour"]:
                selling_high = selling_prices[timeframe]["high"]
                cost_low = slow_buy_costs[timeframe]["low"]
                slow_buy_profit = selling_high - cost_low
                profits["slow_buy"][timeframe] = round(slow_buy_profit, 2)

                print(
                    f"  📊 Slow buy {timeframe}: Sell high {selling_high} - Cost low {cost_low} = Profit {slow_buy_profit}"
                )

        print(f"\n💰 Total profit margins:")
        print(
            f"  15min - High: {profits['15min']['high']}, Low: {profits['15min']['low']}, Avg: {profits['15min']['average']}"
        )
        print(
            f"  3hour - High: {profits['3hour']['high']}, Low: {profits['3hour']['low']}, Avg: {profits['3hour']['average']}"
        )
        print(
            f"  Slow buy - 15min: {profits['slow_buy']['15min']}, 3hour: {profits['slow_buy']['3hour']}"
        )

        return profits

    def display(self):
        try:
            data = self.find_cheapest_ingredients()
            production_costs = self.get_production_cost(data)
            slow_buy_costs = self.calculate_slow_buy_cost(data)
            profit_data = self.calculate_profit(production_costs, slow_buy_costs)

            sc_data = {
                "item": self.sc4_item,
                "name": getattr(self.sc4_item, "item_name", "Super combat potion (4)"),
                "id": self.sc4_item.item_id,
            }

            if not data:
                return render_template(
                    "osrs/super_combats.html", error="No data available"
                )

            return render_template(
                "osrs/super_combats.html",
                data=data,
                sc_data=sc_data,
                production_costs=production_costs,
                slow_buy_costs=slow_buy_costs,
                profit_data=profit_data,
            )
        except Exception as e:
            return render_template("osrs/super_combats.html", error=str(e))


if __name__ == "__main__":
    sc = SuperCombats()
    import json

    cheapest_data = sc.find_cheapest_ingredients()
    print("\n" + "=" * 50)
    print("CHEAPEST INGREDIENTS:")
    print(json.dumps(cheapest_data, indent=4, default=str))

    print("\n" + "=" * 50)
    print("PRODUCTION COSTS:")
    production_costs = sc.get_production_cost(cheapest_data)
    print(json.dumps(production_costs, indent=4, default=str))

    print("\n" + "=" * 50)
    print("SLOW BUY COSTS:")
    slow_buy_costs = sc.calculate_slow_buy_cost(cheapest_data)
    print(json.dumps(slow_buy_costs, indent=4, default=str))

    print("\n" + "=" * 50)
    print("PROFIT CALCULATIONS:")
    profit_data = sc.calculate_profit(production_costs, slow_buy_costs)
    print(json.dumps(profit_data, indent=4, default=str))
