from math import inf
from pathlib import Path
import sys, os

ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent

if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from src.osrs.item_properties import osrsItemProperties
from src.util.helpers import format_currency
from dotenv import load_dotenv

load_dotenv(".env_public")

# Constants
ZAHUR_FEE = int(os.getenv("ZAHUR_FEE", default=200))
GOGGLE_CHANCE = float(os.getenv("PRES_GOGGLES_CHANCE", default=0.1111))
CHEM_CHANCE = float(os.getenv("ALC_AMUL_CHANCE", default=0.15))
GE_TAX = float(os.getenv("GE_TAX", default=0.02))

AOC_ID = 21163
VOW_ID = 227

aoc_item = osrsItemProperties(AOC_ID)
vow_item = osrsItemProperties(VOW_ID)

def get_aoc_cost(aoc_low, aoc_avg):
    """Calculate the cost of Amulet of Chemistry proc"""
    raw_cost = aoc_low
    if not raw_cost:
        raw_cost = aoc_avg

    if not raw_cost:
        raw_cost = 0

    proc_cost = raw_cost // 10

    return proc_cost


aoc_proc_cost_5min = get_aoc_cost(
    aoc_item.latest_5min_price_low, aoc_item.latest_5min_price_average
)
aoc_proc_cost_15min = get_aoc_cost(
    aoc_item.latest_15min_price_low, aoc_item.latest_15min_price_average
)
aoc_proc_cost_1h = get_aoc_cost(
    aoc_item.latest_1h_price_low, aoc_item.latest_1h_price_average
)
aoc_proc_cost_3h = get_aoc_cost(
    aoc_item.latest_3h_price_low, aoc_item.latest_3h_price_average
)


class HerblorePotionCalc:
    def __init__(
        self,
        goggles: bool = True,
        alchem: bool = True,
        potions_per_hour: int = 2500,
        primary_herb_id: int = None,
        primary_gherb_id: int = None,
        primary_unf_id: int = None,
        secondary_item_id: int = None,
        product_item_id: int = None,
        product_item_doses: int = 4,
    ):
        """Initialize Herb 3-dose Production Calculator"""
        # Initialize parameters
        self.goggles = goggles
        self.alchem = alchem
        self.potions_per_hour = potions_per_hour
        self.primary_herb_id = primary_herb_id
        self.primary_gherb_id = primary_gherb_id
        self.primary_unf_id = primary_unf_id
        self.secondary_item_id = secondary_item_id
        self.product_item_id = product_item_id
        self.product_item_doses = product_item_doses

        # Fetch item properties
        self.product_item = osrsItemProperties(self.product_item_id)
        self.primary_herb = osrsItemProperties(self.primary_herb_id)
        self.primary_gherb = osrsItemProperties(self.primary_gherb_id)
        self.primary_unf = osrsItemProperties(self.primary_unf_id)
        self.secondary_item = osrsItemProperties(self.secondary_item_id)

        # Initialize production costs
        self.production_cost_5min = 0
        self.production_cost_15min = 0
        self.production_cost_1h = 0
        self.production_cost_3h = 0

        # Initialize cheapest primary herb costs
        self.cheapest_primary_cost_5min = inf
        self.cheapest_primary_cost_15min = inf
        self.cheapest_primary_cost_1h = inf
        self.cheapest_primary_cost_3h = inf

        # Initialize placeholders for cheapest primary herbs
        self.cheapest_primary_5min = None
        self.cheapest_primary_15min = None
        self.cheapest_primary_1h = None
        self.cheapest_primary_3h = None

        # Initialize revenue and profit attributes
        self.product_price_5min = 0
        self.product_price_15min = 0
        self.product_price_1h = 0
        self.product_price_3h = 0

        self.product_ppd_5min = 0
        self.product_ppd_15min = 0
        self.product_ppd_1h = 0
        self.product_ppd_3h = 0

        self.revenue_5min = 0
        self.revenue_15min = 0
        self.revenue_1h = 0
        self.revenue_3h = 0

        self.profit_5min = 0
        self.profit_15min = 0
        self.profit_1h = 0
        self.profit_3h = 0

        self.gp_per_hour_5min = 0
        self.gp_per_hour_15min = 0
        self.gp_per_hour_1h = 0
        self.gp_per_hour_3h = 0

    def calc(self):
        """Perform all calculations"""
        self._calculate_production_cost()
        self._calculate_revenue()
        self._calculate_profit()

    def _calculate_production_cost(self):
        """Calculate the production cost for the herb potion"""
        self._calc_cheapest_primary()
        self._calc_secondary_cost()
        if self.alchem:
            self.production_cost_5min += CHEM_CHANCE * aoc_proc_cost_5min
            self.production_cost_15min += CHEM_CHANCE * aoc_proc_cost_15min
            self.production_cost_1h += CHEM_CHANCE * aoc_proc_cost_1h
            self.production_cost_3h += CHEM_CHANCE * aoc_proc_cost_3h

    def _calculate_revenue(self):
        """Calculate the revenue for the herb potion"""
        prod_5min, prod_15min, prod_1h, prod_3h = self._get_high_price(
            self.product_item
        )

        # Handle None values by defaulting to 0
        prod_5min = prod_5min if prod_5min is not None else 0
        prod_15min = prod_15min if prod_15min is not None else 0
        prod_1h = prod_1h if prod_1h is not None else 0
        prod_3h = prod_3h if prod_3h is not None else 0

        self.product_price_5min = prod_5min
        self.product_price_15min = prod_15min
        self.product_price_1h = prod_1h
        self.product_price_3h = prod_3h

        self.product_ppd_5min = prod_5min // self.product_item_doses
        self.product_ppd_15min = prod_15min // self.product_item_doses
        self.product_ppd_1h = prod_1h // self.product_item_doses
        self.product_ppd_3h = prod_3h // self.product_item_doses

        doses_made = 3.15 if self.alchem else 3.0

        self.revenue_5min = self.product_ppd_5min * doses_made
        self.revenue_15min = self.product_ppd_15min * doses_made
        self.revenue_1h = self.product_ppd_1h * doses_made
        self.revenue_3h = self.product_ppd_3h * doses_made

    def _calculate_profit(self):
        net_mod = 1 - GE_TAX
        
        self.profit_5min = (self.revenue_5min * net_mod) - self.production_cost_5min
        self.profit_15min = (self.revenue_15min * net_mod) - self.production_cost_15min
        self.profit_1h = (self.revenue_1h * net_mod) - self.production_cost_1h
        self.profit_3h = (self.revenue_3h * net_mod) - self.production_cost_3h

        self.gp_per_hour_5min = self.profit_5min * self.potions_per_hour
        self.gp_per_hour_15min = self.profit_15min * self.potions_per_hour
        self.gp_per_hour_1h = self.profit_1h * self.potions_per_hour
        self.gp_per_hour_3h = self.profit_3h * self.potions_per_hour

    def _get_primary_cost(self, item, make_unf: bool, clean_grimy: bool = True):
        # Get the low item price in each time bracket, defaulting to high price if low is unavailable
        price_5min, price_15min, price_1h, price_3h = self._get_low_price(item)
        # Replace None values with inf
        price_5min = price_5min if price_5min is not None else inf
        price_15min = price_15min if price_15min is not None else inf
        price_1h = price_1h if price_1h is not None else inf
        price_3h = price_3h if price_3h is not None else inf
        
        if make_unf:
            # Get vial of water price for each time bracket, defaulting to high price if low is unavailable
            vow_5min, vow_15min, vow_1h, vow_3h = self._get_low_price(vow_item)
            vow_5min = vow_5min if vow_5min is not None else inf
            vow_15min = vow_15min if vow_15min is not None else inf
            vow_1h = vow_1h if vow_1h is not None else inf
            vow_3h = vow_3h if vow_3h is not None else inf
        else:
            vow_5min, vow_15min, vow_1h, vow_3h = 0, 0, 0, 0

        price_5min += ZAHUR_FEE + vow_5min if make_unf else 0
        price_15min += ZAHUR_FEE + vow_15min if make_unf else 0
        price_1h += ZAHUR_FEE + vow_1h if make_unf else 0
        price_3h += ZAHUR_FEE + vow_3h if make_unf else 0
        price_5min += ZAHUR_FEE if clean_grimy else 0
        price_15min += ZAHUR_FEE if clean_grimy else 0
        price_1h += ZAHUR_FEE if clean_grimy else 0
        price_3h += ZAHUR_FEE if clean_grimy else 0

        return price_5min, price_15min, price_1h, price_3h

    def _get_raw_primary_cost(self, item):
        # Get the low item price in each time bracket, defaulting to high price if low is unavailable
        price_5min, price_15min, price_1h, price_3h = self._get_low_price(item)

        # Replace None values with inf
        price_5min = price_5min if price_5min is not None else inf
        price_15min = price_15min if price_15min is not None else inf
        price_1h = price_1h if price_1h is not None else inf
        price_3h = price_3h if price_3h is not None else inf

        return price_5min, price_15min, price_1h, price_3h

    def _calc_cheapest_primary(
        self,
    ):
        """
        Get the cheapest herb prices across different time frames. Updates production cost attributes.
        """
        for item, make_unf, clean_grimy in [
            (self.primary_herb, True, False),
            (self.primary_gherb, True, True),
            (self.primary_unf, False, False),
        ]:
            (
                price_5min,
                price_15min,
                price_1h,
                price_3h,
            ) = self._get_primary_cost(item, make_unf, clean_grimy)

            (
                raw_price_5min,
                raw_price_15min,
                raw_price_1h,
                raw_price_3h,
            ) = self._get_raw_primary_cost(item)

            if price_5min and price_5min < self.cheapest_primary_cost_5min:
                self.cheapest_primary_cost_5min = price_5min
                self.cheapest_primary_raw_5min = raw_price_5min
                self.cheapest_primary_5min = item

            if price_15min and price_15min < self.cheapest_primary_cost_15min:
                self.cheapest_primary_cost_15min = price_15min
                self.cheapest_primary_raw_15min = raw_price_15min
                self.cheapest_primary_15min = item

            if price_1h and price_1h < self.cheapest_primary_cost_1h:
                self.cheapest_primary_cost_1h = price_1h
                self.cheapest_primary_raw_1h = raw_price_1h
                self.cheapest_primary_1h = item

            if price_3h and price_3h < self.cheapest_primary_cost_3h:
                self.cheapest_primary_cost_3h = price_3h
                self.cheapest_primary_raw_3h = raw_price_3h
                self.cheapest_primary_3h = item

        self.production_cost_5min += self.cheapest_primary_cost_5min
        self.production_cost_15min += self.cheapest_primary_cost_15min
        self.production_cost_1h += self.cheapest_primary_cost_1h
        self.production_cost_3h += self.cheapest_primary_cost_3h

    def _calc_secondary_cost(
        self,
    ):
        """Calculate the secondary herb cost, considering goggles if applicable. Updates production cost attributes."""

        price_5min, price_15min, price_1h, price_3h = self._get_low_price(
            self.secondary_item
        )
        item_usage = 1 - GOGGLE_CHANCE if self.goggles else 1

        self.production_cost_5min += item_usage * price_5min
        self.production_cost_15min += item_usage * price_15min
        self.production_cost_1h += item_usage * price_1h
        self.production_cost_3h += item_usage * price_3h
        self.raw_secondary_cost_5min = price_5min
        self.raw_secondary_cost_15min = price_15min
        self.raw_secondary_cost_1h = price_1h
        self.raw_secondary_cost_3h = price_3h

    def _get_low_price(self, item):
        """
        Get the low price of an item, defaulting to average if low is unavailable.
        """
        return (
            (
                item.latest_5min_price_low
                if item.latest_5min_price_low
                else item.latest_5min_price_average
            ),
            (
                item.latest_15min_price_low
                if item.latest_15min_price_low
                else item.latest_15min_price_average
            ),
            (
                item.latest_1h_price_low
                if item.latest_1h_price_low
                else item.latest_1h_price_average
            ),
            (
                item.latest_3h_price_low
                if item.latest_3h_price_low
                else item.latest_3h_price_average
            ),
        )

    def _get_high_price(self, item):
        """
        Get the high price of an item, defaulting to average if high is unavailable.
        """
        return (
            (
                item.latest_5min_price_high
                if item.latest_5min_price_high
                else item.latest_5min_price_average
            ),
            (
                item.latest_15min_price_high
                if item.latest_15min_price_high
                else item.latest_15min_price_average
            ),
            (
                item.latest_1h_price_high
                if item.latest_1h_price_high
                else item.latest_1h_price_average
            ),
            (
                item.latest_3h_price_high
                if item.latest_3h_price_high
                else item.latest_3h_price_average
            ),
        )

    def format_value(self, value):
        formatted_value = ""

        if value is None or value == inf or value == -inf or value == "nan":
            formatted_value = "N/A"  # or some other default string
        else:
            formatted_value = format_currency(
                value, currency_symbol="gp", prefix=False, suffix=True
            )

        return formatted_value
