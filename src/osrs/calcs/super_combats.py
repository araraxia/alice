from cmath import inf
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
        "one_dose": {"items": [ss1_item, sa1_item, sd1_item], "quantity": 4},
        "two_dose": {"items": [ss2_item, sa2_item, sd2_item], "quantity": 3},
        "three_dose": {"items": [ss3_item, sa3_item, sd3_item], "quantity": 2},
        "four_dose": {"items": [ss4_item, sa4_item, sd4_item], "quantity": 1},
    }

    recipe: dict = {
        "super_attack": [sa1_item, sa2_item, sa3_item, sa4_item],
        "super_strength": [ss1_item, ss2_item, ss3_item, ss4_item],
        "super_defence": [sd1_item, sd2_item, sd3_item, sd4_item],
        "clean_torstol": [clean_torstol_item, grimy_torstol_item, unf_torstol_item],
    }
    
    def find_cheapest_ingredients(self):
        cheapest = {
            "super_attack": {"item": None, "price": None, "quantity": None},
            "super_strength": {"item": None, "price": None, "quantity": None},
            "super_defence": {"item": None, "price": None, "quantity": None},
            "clean_torstol": {"item": None, "price": None, "quantity": None},
        }
        
        for ingredient, data in self.recipe.items():
            cheapest_ingredient = {"item": None, "price": float(inf), "quantity": 1}
            for item in data.get("items", []):
                # Determine quantity based on item dosage
                quantity = 0
                for dosage, dose_data in self.dosages.items():
                    if item in dose_data["items"]:
                        quantity = dose_data["quantity"]
                        break
                
                if not quantity:
                    # Torstol case
                    quantity = 1 - self.reduced_secondaries if self.goggles_equipped else 1
                # Calculate the price per potion