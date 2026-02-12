from math import inf
from pathlib import Path
import sys

ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent

if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from src.osrs.item_properties import osrsItemProperties
from src.util.helpers import format_currency

GOADING_4_ID = 30137
goading_4 = None
P_REGEN_4_ID = 30125
p_regen_4 = None

HUASCA_ID = 30097
huasca = None
G_HUASCA_ID = 30094
g_huasca = None
HUASCA_UNF_ID = 30100
huasca_unf = None

HARRALANDER_ID = 255
harralander = None
G_HARRALANDER_ID = 205
g_harralander = None
HARRALANDER_UNF_ID = 97
harralander_unf = None

ALDARIUM_ID = 29993

AOC_ID = 21163
aoc_item = osrsItemProperties(AOC_ID)

ZAHUR_FEE = 200
GOGGLE_CHANCE = 0.1111
CHEM_CHANCE = 0.15
GE_TAX = 0.02


def get_aoc_cost(aoc_low, aoc_avg):
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
        secondary_item_id: int = ALDARIUM_ID,
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

        price_5min += ZAHUR_FEE if make_unf else 0
        price_15min += ZAHUR_FEE if make_unf else 0
        price_1h += ZAHUR_FEE if make_unf else 0
        price_3h += ZAHUR_FEE if make_unf else 0
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

        if self.goggles:
            self.production_cost_5min += GOGGLE_CHANCE * aoc_proc_cost_5min
            self.production_cost_15min += GOGGLE_CHANCE * aoc_proc_cost_15min
            self.production_cost_1h += GOGGLE_CHANCE * aoc_proc_cost_1h
            self.production_cost_3h += GOGGLE_CHANCE * aoc_proc_cost_3h

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


class GoadingRegens:
    def __init__(self):
        """Initialize Goading Regens calculator"""
        from flask import render_template

        self.render_template = render_template

    def display(self):
        """Display the goading regens calculation results"""
        try:
            # Calculate both goading and p_regen data
            goading_calc = HerblorePotionCalc(
                goggles=True,
                alchem=True,
                potions_per_hour=2500,
                primary_herb_id=HARRALANDER_ID,
                primary_gherb_id=G_HARRALANDER_ID,
                primary_unf_id=HARRALANDER_UNF_ID,
                secondary_item_id=ALDARIUM_ID,
                product_item_id=GOADING_4_ID,
                product_item_doses=4,
            )

            goading_calc.calc()

            # Safely get harralander costs and names with None checks
            harr_cost_5min = (
                goading_calc.cheapest_primary_5min.latest_5min_price_low
                if goading_calc.cheapest_primary_5min
                and goading_calc.cheapest_primary_5min.latest_5min_price_low
                else (
                    goading_calc.cheapest_primary_5min.latest_5min_price_average
                    if goading_calc.cheapest_primary_5min
                    else 0
                )
            )
            harr_cost_15min = (
                goading_calc.cheapest_primary_15min.latest_15min_price_low
                if goading_calc.cheapest_primary_15min
                and goading_calc.cheapest_primary_15min.latest_15min_price_low
                else (
                    goading_calc.cheapest_primary_15min.latest_15min_price_average
                    if goading_calc.cheapest_primary_15min
                    else 0
                )
            )
            harr_cost_1h = (
                goading_calc.cheapest_primary_1h.latest_1h_price_low
                if goading_calc.cheapest_primary_1h
                and goading_calc.cheapest_primary_1h.latest_1h_price_low
                else (
                    goading_calc.cheapest_primary_1h.latest_1h_price_average
                    if goading_calc.cheapest_primary_1h
                    else 0
                )
            )
            harr_cost_3h = (
                goading_calc.cheapest_primary_3h.latest_3h_price_low
                if goading_calc.cheapest_primary_3h
                and goading_calc.cheapest_primary_3h.latest_3h_price_low
                else (
                    goading_calc.cheapest_primary_3h.latest_3h_price_average
                    if goading_calc.cheapest_primary_3h
                    else 0
                )
            )
            harr_name_5min = (
                goading_calc.cheapest_primary_5min.name
                if goading_calc.cheapest_primary_5min
                else "N/A"
            )
            harr_name_15min = (
                goading_calc.cheapest_primary_15min.name
                if goading_calc.cheapest_primary_15min
                else "N/A"
            )
            harr_name_1h = (
                goading_calc.cheapest_primary_1h.name
                if goading_calc.cheapest_primary_1h
                else "N/A"
            )
            harr_name_3h = (
                goading_calc.cheapest_primary_3h.name
                if goading_calc.cheapest_primary_3h
                else "N/A"
            )

            p_regen_calc = HerblorePotionCalc(
                goggles=True,
                alchem=True,
                potions_per_hour=2500,
                primary_herb_id=HUASCA_ID,
                primary_gherb_id=G_HUASCA_ID,
                primary_unf_id=HUASCA_UNF_ID,
                secondary_item_id=ALDARIUM_ID,
                product_item_id=P_REGEN_4_ID,
                product_item_doses=4,
            )

            p_regen_calc.calc()

            # Safely get huasca costs and names with None checks
            huasca_cost_5min = (
                p_regen_calc.cheapest_primary_5min.latest_5min_price_low
                if p_regen_calc.cheapest_primary_5min
                and p_regen_calc.cheapest_primary_5min.latest_5min_price_low
                else (
                    p_regen_calc.cheapest_primary_5min.latest_5min_price_average
                    if p_regen_calc.cheapest_primary_5min
                    else 0
                )
            )
            huasca_cost_15min = (
                p_regen_calc.cheapest_primary_15min.latest_15min_price_low
                if p_regen_calc.cheapest_primary_15min
                and p_regen_calc.cheapest_primary_15min.latest_15min_price_low
                else (
                    p_regen_calc.cheapest_primary_15min.latest_15min_price_average
                    if p_regen_calc.cheapest_primary_15min
                    else 0
                )
            )
            huasca_cost_1h = (
                p_regen_calc.cheapest_primary_1h.latest_1h_price_low
                if p_regen_calc.cheapest_primary_1h
                and p_regen_calc.cheapest_primary_1h.latest_1h_price_low
                else (
                    p_regen_calc.cheapest_primary_1h.latest_1h_price_average
                    if p_regen_calc.cheapest_primary_1h
                    else 0
                )
            )
            huasca_cost_3h = (
                p_regen_calc.cheapest_primary_3h.latest_3h_price_low
                if p_regen_calc.cheapest_primary_3h
                and p_regen_calc.cheapest_primary_3h.latest_3h_price_low
                else (
                    p_regen_calc.cheapest_primary_3h.latest_3h_price_average
                    if p_regen_calc.cheapest_primary_3h
                    else 0
                )
            )
            huasca_name_5min = (
                p_regen_calc.cheapest_primary_5min.name
                if p_regen_calc.cheapest_primary_5min
                else "N/A"
            )
            huasca_name_15min = (
                p_regen_calc.cheapest_primary_15min.name
                if p_regen_calc.cheapest_primary_15min
                else "N/A"
            )
            huasca_name_1h = (
                p_regen_calc.cheapest_primary_1h.name
                if p_regen_calc.cheapest_primary_1h
                else "N/A"
            )
            huasca_name_3h = (
                p_regen_calc.cheapest_primary_3h.name
                if p_regen_calc.cheapest_primary_3h
                else "N/A"
            )
            (
                aldarium_5min_price,
                aldarium_15min_price,
                aldarium_1h_price,
                aldarium_3h_price,
            ) = p_regen_calc._get_low_price(p_regen_calc.secondary_item)

            goading_data = {
                "production_cost_5min": goading_calc.format_value(
                    goading_calc.production_cost_5min
                ),
                "revenue_5min": goading_calc.format_value(goading_calc.revenue_5min),
                "profit_5min": goading_calc.format_value(goading_calc.profit_5min),
                "gp_per_hour_5min": goading_calc.format_value(
                    goading_calc.gp_per_hour_5min
                ),
                "production_cost_15min": goading_calc.format_value(
                    goading_calc.production_cost_15min
                ),
                "revenue_15min": goading_calc.format_value(goading_calc.revenue_15min),
                "profit_15min": goading_calc.format_value(goading_calc.profit_15min),
                "gp_per_hour_15min": goading_calc.format_value(
                    goading_calc.gp_per_hour_15min
                ),
                "production_cost_1h": goading_calc.format_value(
                    goading_calc.production_cost_1h
                ),
                "revenue_1h": goading_calc.format_value(goading_calc.revenue_1h),
                "profit_1h": goading_calc.format_value(goading_calc.profit_1h),
                "gp_per_hour_1h": goading_calc.format_value(
                    goading_calc.gp_per_hour_1h
                ),
                "production_cost_3h": goading_calc.format_value(
                    goading_calc.production_cost_3h
                ),
                "revenue_3h": goading_calc.format_value(goading_calc.revenue_3h),
                "profit_3h": goading_calc.format_value(goading_calc.profit_3h),
                "gp_per_hour_3h": goading_calc.format_value(
                    goading_calc.gp_per_hour_3h
                ),
                "goading_4_price_5m": goading_calc.format_value(
                    goading_calc.product_price_5min
                ),
                "goading_4_price_15m": goading_calc.format_value(
                    goading_calc.product_price_15min
                ),
                "goading_4_price_1h": goading_calc.format_value(
                    goading_calc.product_price_1h
                ),
                "goading_4_price_3h": goading_calc.format_value(
                    goading_calc.product_price_3h
                ),
                "primary_cost_5min": goading_calc.format_value(
                    goading_calc.cheapest_primary_raw_5min
                ),
                "primary_cost_15min": goading_calc.format_value(
                    goading_calc.cheapest_primary_raw_15min
                ),
                "primary_cost_1h": goading_calc.format_value(
                    goading_calc.cheapest_primary_raw_1h
                ),
                "primary_cost_3h": goading_calc.format_value(
                    goading_calc.cheapest_primary_raw_3h
                ),
                "primary_name_5min": (
                    goading_calc.cheapest_primary_5min.name
                    if goading_calc.cheapest_primary_5min
                    else "N/A"
                ),
                "primary_name_15min": (
                    goading_calc.cheapest_primary_15min.name
                    if goading_calc.cheapest_primary_15min
                    else "N/A"
                ),
                "primary_name_1h": (
                    goading_calc.cheapest_primary_1h.name
                    if goading_calc.cheapest_primary_1h
                    else "N/A"
                ),
                "primary_name_3h": (
                    goading_calc.cheapest_primary_3h.name
                    if goading_calc.cheapest_primary_3h
                    else "N/A"
                ),
                "potions_per_hour": goading_calc.potions_per_hour,
                "alchemical_amulet_bonus": f"{int(CHEM_CHANCE * 100)}%",
                "goggles_bonus": f"{int(GOGGLE_CHANCE * 100)}%",
                "ge_tax_rate": f"{int(GE_TAX * 100)}%",
            }
            p_regen_data = {
                "production_cost_5min": p_regen_calc.format_value(
                    p_regen_calc.production_cost_5min
                ),
                "revenue_5min": p_regen_calc.format_value(p_regen_calc.revenue_5min),
                "profit_5min": p_regen_calc.format_value(p_regen_calc.profit_5min),
                "gp_per_hour_5min": p_regen_calc.format_value(
                    p_regen_calc.gp_per_hour_5min
                ),
                "production_cost_15min": p_regen_calc.format_value(
                    p_regen_calc.production_cost_15min
                ),
                "revenue_15min": p_regen_calc.format_value(p_regen_calc.revenue_15min),
                "profit_15min": p_regen_calc.format_value(p_regen_calc.profit_15min),
                "gp_per_hour_15min": p_regen_calc.format_value(
                    p_regen_calc.gp_per_hour_15min
                ),
                "production_cost_1h": p_regen_calc.format_value(
                    p_regen_calc.production_cost_1h
                ),
                "revenue_1h": p_regen_calc.format_value(p_regen_calc.revenue_1h),
                "profit_1h": p_regen_calc.format_value(p_regen_calc.profit_1h),
                "gp_per_hour_1h": p_regen_calc.format_value(
                    p_regen_calc.gp_per_hour_1h
                ),
                "production_cost_3h": p_regen_calc.format_value(
                    p_regen_calc.production_cost_3h
                ),
                "revenue_3h": p_regen_calc.format_value(p_regen_calc.revenue_3h),
                "profit_3h": p_regen_calc.format_value(p_regen_calc.profit_3h),
                "gp_per_hour_3h": p_regen_calc.format_value(
                    p_regen_calc.gp_per_hour_3h
                ),
                "p_regen_4_price_5m": p_regen_calc.format_value(
                    p_regen_calc.product_price_5min
                ),
                "p_regen_4_price_15m": p_regen_calc.format_value(
                    p_regen_calc.product_price_15min
                ),
                "p_regen_4_price_1h": p_regen_calc.format_value(
                    p_regen_calc.product_price_1h
                ),
                "p_regen_4_price_3h": p_regen_calc.format_value(
                    p_regen_calc.product_price_3h
                ),
                "aldarium_price_5m": p_regen_calc.format_value(
                    p_regen_calc.raw_secondary_cost_5min
                ),
                "aldarium_price_15m": p_regen_calc.format_value(
                    p_regen_calc.raw_secondary_cost_15min
                ),
                "aldarium_price_1h": p_regen_calc.format_value(
                    p_regen_calc.raw_secondary_cost_1h
                ),
                "aldarium_price_3h": p_regen_calc.format_value(
                    p_regen_calc.raw_secondary_cost_3h
                ),
                "primary_name_5min": huasca_name_5min if huasca_name_5min else "N/A",
                "primary_name_15min": huasca_name_15min if huasca_name_15min else "N/A",
                "primary_name_1h": huasca_name_1h if huasca_name_1h else "N/A",
                "primary_name_3h": huasca_name_3h if huasca_name_3h else "N/A",
                "primary_cost_5min": p_regen_calc.format_value(
                    p_regen_calc.cheapest_primary_raw_5min
                ),
                "primary_cost_15min": p_regen_calc.format_value(
                    p_regen_calc.cheapest_primary_raw_15min
                ),
                "primary_cost_1h": p_regen_calc.format_value(
                    p_regen_calc.cheapest_primary_raw_1h
                ),
                "primary_cost_3h": p_regen_calc.format_value(
                    p_regen_calc.cheapest_primary_raw_3h
                ),
                "potions_per_hour": p_regen_calc.potions_per_hour,
                "alchemical_amulet_bonus": f"{int(CHEM_CHANCE * 100)}%",
                "goggles_bonus": f"{int(GOGGLE_CHANCE * 100)}%",
                "ge_tax_rate": f"{int(GE_TAX * 100)}%",
            }

            goading_info = {
                "name": "Goading Potion",
                "id": GOADING_4_ID,
            }

            p_regen_info = {
                "name": "Prayer Regeneration",
                "id": P_REGEN_4_ID,
            }

            return self.render_template(
                "osrs/goading_regens.html",
                goading_data=goading_data,
                p_regen_data=p_regen_data,
                goading_info=goading_info,
                p_regen_info=p_regen_info,
            )
        except Exception as e:
            return self.render_template("osrs/goading_regens.html", error=str(e))


if __name__ == "__main__":
    # import json

    print("Calculating goading and p_regen production costs and profits...")
    print("\n" + "=" * 60)
    print("GOADING 4 CALCULATIONS")
    print("=" * 60)
    """
    print(
        json.dumps(
            calculate_goading_prod_cost(
                goggles=True, alchem=True, potions_per_hour=2500
            ),
            indent=4,
        )
    )

    print("\n" + "=" * 60)
    print("P REGEN 4 CALCULATIONS")
    print("=" * 60)
    print(
        json.dumps(
            calculate_p_regen_prod_cost(
                goggles=True, alchem=True, potions_per_hour=2500
            ),
            indent=4,
        )
    )
    """
