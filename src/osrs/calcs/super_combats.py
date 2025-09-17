from math import inf
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent  # alice/
if str(ROOT_DIR) not in os.sys.path:
    os.sys.path.append(str(ROOT_DIR))

from src.osrs.item_properties import osrsItemProperties

from dataclasses import dataclass


@dataclass
class SuperCombats:
    sc4_item: object = osrsItemProperties(item_id=12695)
    ss1_item: object = osrsItemProperties(item_id=161)
    ss2_item: object = osrsItemProperties(item_id=159)
    ss3_item: object = osrsItemProperties(item_id=157)
    ss4_item: object = osrsItemProperties(item_id=2440)
    sa1_item: object = osrsItemProperties(item_id=149)
    sa2_item: object = osrsItemProperties(item_id=147)
    sa3_item: object = osrsItemProperties(item_id=145)
    sa4_item: object = osrsItemProperties(item_id=2436)
    sd1_item: object = osrsItemProperties(item_id=167)
    sd2_item: object = osrsItemProperties(item_id=165)
    sd3_item: object = osrsItemProperties(item_id=163)
    sd4_item: object = osrsItemProperties(item_id=2442)
    grimy_torstol_item: object = osrsItemProperties(item_id=219)
    clean_torstol_item: object = osrsItemProperties(item_id=269)
    unf_torstol_item: object = osrsItemProperties(item_id=111)

    zahur_clean_price: int = 200
    goggle_save_chance: float = 0.10  # 10%
    reduced_secondaries: float = 0.11111  # 11.111...%
    goggles_equipped: bool = True  # Assume goggles are equipped for calculations

    dosages: dict = {
        "one_dose": {"items": [ss1_item, sa1_item, sd1_item], "dosage": 1},
        "two_dose": {"items": [ss2_item, sa2_item, sd2_item], "dosage": 2},
        "three_dose": {"items": [ss3_item, sa3_item, sd3_item], "dosage": 3},
        "four_dose": {"items": [ss4_item, sa4_item, sd4_item], "dosage": 4},
    }

    recipe: dict = {
        "super_attack": [sa1_item, sa2_item, sa3_item, sa4_item],
        "super_strength": [ss1_item, ss2_item, ss3_item, ss4_item],
        "super_defence": [sd1_item, sd2_item, sd3_item, sd4_item],
        "torstol": [clean_torstol_item, grimy_torstol_item, unf_torstol_item],
    }

    def find_cheapest_ingredients(self, vol_min_5m: int = 500, vol_min_1h: int = 2000):
        cheapest_template = {
            "item": None,
            "min_buy_price": inf,
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
                # Skip items that don't meet volume requirements
                if (
                    item.latest_5min_volume_low is not None
                    and item.latest_5min_volume_low < vol_min_5m
                ):
                    continue
                if (
                    item.latest_1h_volume_low is not None
                    and item.latest_1h_volume_low < vol_min_1h
                ):
                    continue

                # Handle zero prices
                if item.latest_price_5min_low == 0:
                    item.latest_price_5min_low = inf
                if item.latest_price_1h_low == 0:
                    item.latest_price_1h_low = inf

                # Determine dosage based on item dosage
                dosage = 0
                for dose_name, dose_data in self.dosages.items():
                    if item in dose_data["items"]:
                        dosage = dose_data["dosage"]
                        break

                if not dosage: # Torstol case
                    # Calculate the price per herb w/ save chance
                    quantity = (
                        1 - self.reduced_secondaries if self.goggles_equipped else 1
                    )
                    # Clean grimy torstol has a fixed NPC price for cleaning
                    if item.item_id == 219:
                        price_5min = (
                            ((item.latest_price_5min_low or inf) + self.zahur_clean_price) 
                            // quantity
                        )
                        price_1h = (
                            ((item.latest_price_1h_low or inf) + self.zahur_clean_price) 
                            // quantity
                        )
                    else:
                        price_5min = (item.latest_price_5min_low or inf) // quantity
                        price_1h = (item.latest_price_1h_low or inf) // quantity

                else: # Potion case
                    # Calculate the price per dose
                    quantity = 4 - (dosage - 1)
                    price_5min = (item.latest_price_5min_low or inf) // dosage
                    price_1h = (item.latest_price_1h_low or inf) // dosage

                # Avoid large price swings by comparing 5min and 1h prices
                diff_5m_1h = abs(price_5min - price_1h)
                if price_1h > 0 and diff_5m_1h / price_1h > 0.10:
                    calculation_price = price_1h
                else:
                    calculation_price = price_5min

                # Compare with latest price if available
                if (
                    not cheapest[ingredient]["item"]
                    or calculation_price < cheapest[ingredient]["min_buy_price"]
                ):
                    cheapest[ingredient] = {
                        "item": item,
                        "min_buy_price": calculation_price,
                        "quantity": dosage,
                    }
                else:
                    continue

        if not all(cheap_ing["item"] for cheap_ing in cheapest.values()):
            return {}
        return cheapest
    
if __name__ == "__main__":
    sc = SuperCombats()
    import json
    print(json.dumps(sc.find_cheapest_ingredients(), indent=4, default=str))