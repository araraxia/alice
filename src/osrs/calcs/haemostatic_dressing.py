
from pathlib import Path
import sys, os

ROOT_PATH = Path(__file__).parent.parent.parent.parent

if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))
    
from src.osrs.calcs.herblore_potion_calc import HerblorePotionCalc
from src.osrs.item_properties import osrsItemProperties
from src.util.helpers import format_currency
from dotenv import load_dotenv

HAEMOSTATIC_DRESSING_3_ID = 31593
HAEMOSTATIC_DRESSING_4_ID = 31590
HAEMOSTATIC_POULTICE_ID = 31587
BALL_OF_COTTON_ID = 31454
ELKHORN_POTION_UNF_ID = 31662
ELKHORN_CORAL_ID = 31481
SQUID_PASTE_ID = 31569
RAW_SWORDTIP_SQUID_ID = 31553

# Haemostatic_Poultice = 1 Squid Paste + 1 Elkhorn Potion (unf)
HAEMOSTATIC_POULTICE_XP = 27
# Haemostatic_Dressing_3 = 1 Haemostatic Poultice + 1 Ball of Cotton
HAEMOSTATIC_DRESSING_XP = 100

poultice_calc = HerblorePotionCalc(
    goggles=True,
    alchem=False,
    potions_per_hour=2500,
    primary_herb_id=ELKHORN_CORAL_ID,
    primary_gherb_id=None,
    primary_unf_id=ELKHORN_POTION_UNF_ID,
    secondary_item_id=SQUID_PASTE_ID,
    product_item_id=HAEMOSTATIC_POULTICE_ID,
    product_item_doses=1,
)
poultice_calc.calc()

dressing_calc = HerblorePotionCalc(
    goggles=True,
    alchem=True,
    potions_per_hour=2500,
    primary_herb_id=None,
    primary_gherb_id=None,
    primary_unf_id=HAEMOSTATIC_POULTICE_ID,
    secondary_item_id=BALL_OF_COTTON_ID,
    product_item_id=HAEMOSTATIC_DRESSING_4_ID,
    product_item_doses=4,
)
dressing_calc.calc()