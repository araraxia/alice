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
        self.sc4_item = osrsItemProperties(item_id=12695)
        self.ss1_item = osrsItemProperties(item_id=161)
        self.ss2_item = osrsItemProperties(item_id=159)
        self.ss3_item = osrsItemProperties(item_id=157)
        self.ss4_item = osrsItemProperties(item_id=2440)
        self.sa1_item = osrsItemProperties(item_id=149)
        self.sa2_item = osrsItemProperties(item_id=147)
        self.sa3_item = osrsItemProperties(item_id=145)
        self.sa4_item = osrsItemProperties(item_id=2436)
        self.sd1_item = osrsItemProperties(item_id=167)
        self.sd2_item = osrsItemProperties(item_id=165)
        self.sd3_item = osrsItemProperties(item_id=163)
        self.sd4_item = osrsItemProperties(item_id=2442)
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
        vol_min_5m: int = 100,
        vol_min_1h: int = 500,
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
        print(
            f"🔍 Starting ingredient search with volume thresholds: 5m={vol_min_5m}, 1h={vol_min_1h}"
        )
        print(f"⚗️ Goggles equipped: {goggles}")

        self.goggles_equipped = goggles
        cheapest_template = {
            "item": None,
            "min_ppd": inf,
            "quantity": None,
        }

        cheapest = {
            "super_attack": cheapest_template.copy(),
            "super_strength": cheapest_template.copy(),
            "super_defence": cheapest_template.copy(),
            "torstol": cheapest_template.copy(),
        }

        for ingredient, item_data in self.recipe.items():
            print(f"\n🧪 Processing {ingredient} ({len(item_data)} options):")

            for item in item_data:
                print(f"  📦 Item {item.item_id} ({getattr(item, 'name', 'Unknown')}):")

                # Debug volume data
                vol_5m = getattr(item, "latest_5min_volume_low", None)
                vol_1h = getattr(item, "latest_1h_volume_low", None)

                # Skip items that don't meet volume requirements
                if vol_5m is None and vol_1h is None:
                    print(f"    ❌ Skipped: No volume data for item {item.item_id}")
                    continue
                
                # Item needs good volume in either 5m OR 1h timeframe
                vol_5m_ok = vol_5m is not None and vol_5m >= vol_min_5m
                vol_1h_ok = vol_1h is not None and vol_1h >= vol_min_1h
                if not vol_5m_ok and not vol_1h_ok:
                    print(f"    ❌ Skipped: 5m vol {vol_5m} < {vol_min_5m} AND 1h vol {vol_1h} < {vol_min_1h}")
                    continue

                # Debug price data
                price_5m_raw = getattr(item, "latest_5min_price_low", None)
                price_1h_raw = getattr(item, "latest_1h_price_low", None)

                # Handle zero prices by setting them to None instead of inf
                prices_5m_raw = price_5m_raw if price_5m_raw not in (0, None) else None
                prices_1h_raw = price_1h_raw if price_1h_raw not in (0, None) else None

                # Determine dosage based on item dosage
                dosage = 0
                for dose_name, dose_data in self.dosages.items():
                    if item in dose_data["items"]:
                        dosage = dose_data["dosage"]
                        break

                if not dosage:  # Torstol case
                    # Calculate the price per herb w/ save chance
                    quantity = (
                        1 - self.reduced_secondaries if self.goggles_equipped else 1
                    )
                    dosage = quantity

                    # Clean grimy torstol has a fixed NPC price for cleaning
                    if item.item_id == 219:
                        price_5min = ((price_5m_raw or 0) + self.zahur_clean_price) / quantity if price_5m_raw else None
                        price_1h = ((price_1h_raw or 0) + self.zahur_clean_price) / quantity if price_1h_raw else None
                    else:
                        price_5min = price_5m_raw / quantity if price_5m_raw else None
                        price_1h = price_1h_raw / quantity if price_1h_raw else None

                else:  # Potion case
                    price_5min = price_5m_raw / dosage if price_5m_raw else None
                    price_1h = price_1h_raw / dosage if price_1h_raw else None

                # Choose the best available price (prefer 5min if available and stable)
                if price_5min is not None and price_1h is not None:
                    # Both prices available - check for stability
                    diff_5m_1h = abs(price_5min - price_1h)
                    if diff_5m_1h / price_1h > 0.10:
                        calculation_price = price_1h
                        print(f"    📊 Using 1h price {price_1h} (large swing: {diff_5m_1h/price_1h:.1%})")
                    else:
                        calculation_price = price_5min
                        print(f"    📊 Using 5m price {price_5min} (stable)")
                elif price_5min is not None:
                    calculation_price = price_5min
                    print(f"    📊 Using 5m price {price_5min} (only option)")
                elif price_1h is not None:
                    calculation_price = price_1h
                    print(f"    📊 Using 1h price {price_1h} (only option)")
                else:
                    print(f"    ❌ No valid prices available")
                    continue

                # Compare with current best
                current_best = cheapest[ingredient]["min_ppd"]
                print(
                    f"    🏆 Comparing {calculation_price} vs current best {current_best}"
                )

                if not cheapest[ingredient]["item"] or calculation_price < current_best:
                    cheapest[ingredient] = {
                        "item": item,
                        "min_ppd": calculation_price,
                        "quantity": dosage,
                    }
                    print(
                        f"    ✅ NEW BEST for {ingredient}! Price: {calculation_price}"
                    )
                else:
                    print(f"    ❌ Not better than current best")

        print(f"\n🔍 Final results check:")
        missing_ingredients = []
        for ingredient, data in cheapest.items():
            if not data["item"]:
                missing_ingredients.append(ingredient)
                print(f"  ❌ Missing: {ingredient}")
            else:
                item_name = getattr(data["item"], "name", "Unknown")
                print(f"  ✅ {ingredient}: {item_name} @ {data['min_ppd']} price per dose")

        if missing_ingredients:
            print(
                f"🚫 Returning empty dict - missing ingredients: {missing_ingredients}"
            )
            return {}

        print(f"🎉 All ingredients found!")
        return cheapest

    def display(self):
        try:
            data = self.find_cheapest_ingredients()

            if not data:
                return render_template('osrs/super_combats.html', error="No data available")

            return render_template('osrs/super_combats.html', data=data)
        except Exception as e:
            self.log.error(f"Error in super_combats route: {e}")
            return render_template('osrs/super_combats.html', error=str(e))
        

if __name__ == "__main__":
    sc = SuperCombats()
    import json

    print(json.dumps(sc.find_cheapest_ingredients(), indent=4, default=str))
