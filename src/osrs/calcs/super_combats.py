import os
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent  # alice/
if str(ROOT_DIR) not in os.sys.path:
    os.sys.path.append(str(ROOT_DIR))
    
from src.osrs.item_properties import osrsItemProperties

from dataclasses import dataclass

@dataclass
class SuperCombats:
    sc4_item_id: int = 12695
    ss1_item_id: int
    ss2_item_id: int
    ss3_item_id: int
    ss4_item_id: int
    sa1_item_id: int = 149
    sa2_item_id: int = 147
    sa3_item_id: int = 147
    sa4_item_id: int
    sd1_item_id: int
    sd2_item_id: int
    sd3_item_id: int
    sd4_item_id: int
    grimy_torstol_item_id: int = 259
    clean_torstol_item_id: int = 3051
    zahur_clean_price: int = 200
    
    def get_properties(self, item_id: int) -> dict:
        return osrsItemProperties.get(item_id, {})
        