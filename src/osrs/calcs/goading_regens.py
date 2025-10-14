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
aldarium_item = osrsItemProperties(ALDARIUM_ID)

AOC_ID = 21163
aoc_item = osrsItemProperties(AOC_ID)

ZAHUR_FEE = 200
GOGGLE_CHANCE = 0.1111
CHEM_CHANCE = 0.15
aoc_proc_cost_5min = (
    aoc_item.latest_5min_price_low // 10 if aoc_item.latest_5min_price_low else inf
)
aoc_proc_cost_15min = (
    aoc_item.latest_15min_price_low // 10 if aoc_item.latest_15min_price_low else inf
)
aoc_proc_cost_1h = (
    aoc_item.latest_1h_price_low // 10 if aoc_item.latest_1h_price_low else inf
)
aoc_proc_cost_3h = (
    aoc_item.latest_3h_price_low // 10 if aoc_item.latest_3h_price_low else inf
)


class TempItem:
    def __init__(
        self,
        latest_5min_price_low=None,
        latest_15min_price_low=None,
        latest_1h_price_low=None,
        latest_3h_price_low=None,
    ):
        self.latest_5min_price_low = latest_5min_price_low
        self.latest_15min_price_low = latest_15min_price_low
        self.latest_1h_price_low = latest_1h_price_low
        self.latest_3h_price_low = latest_3h_price_low


def calculate_goading_prod_cost(
    goggles: bool = True, alchem: bool = True, potions_per_hour: int = 2500
):
    """
    Calculate Goading Regens production cost and profit.
    Args:
        goggles (bool): Whether to account for the use of goggles.
        alchem (bool): Whether to account for alchemy usage.
        potions_per_hour (int): Number of potions made per hour.
    Returns:
        dict: Formatted production cost and profit values.
            - aldarium_cost_15m_fmt
            - aldarium_cost_1h_fmt
            - aldarium_cost_3h_fmt
            - cheapest_15min_primary_cost_fmt
            - cheapest_1h_primary_cost_fmt
            - cheapest_3h_primary_cost_fmt
            - production_cost_15m_fmt
            - production_cost_1h_fmt
            - production_cost_3h_fmt
            - price_per_dose_15m_fmt
            - price_per_dose_1h_fmt
            - price_per_dose_3h_fmt
            - revenue_15m_fmt
            - revenue_1h_fmt
            - revenue_3h_fmt
            - profit_15m_fmt
            - profit_1h_fmt
            - profit_3h_fmt
            - gp_per_hour_15m_fmt
            - gp_per_hour_1h_fmt
            - gp_per_hour_3h_fmt
    """
    production_cost_5min = 0
    production_cost_15min = 0
    production_cost_1h = 0
    production_cost_3h = 0

    # Get Item costs
    goading_4 = osrsItemProperties(GOADING_4_ID)
    harralander = osrsItemProperties(HARRALANDER_ID)
    g_harralander = osrsItemProperties(G_HARRALANDER_ID)
    harralander_unf = osrsItemProperties(HARRALANDER_UNF_ID)

    # Calculate Primary Herb Cost (Harralander)
    harralander_cost = TempItem(
        *get_primary_cost(harralander, make_unf=True, clean_grimy=False)
    )
    g_harralander_cost = TempItem(
        *get_primary_cost(g_harralander, make_unf=True, clean_grimy=True)
    )
    harralander_unf_cost = TempItem(
        *get_primary_cost(harralander_unf, make_unf=False, clean_grimy=False)
    )

    # Find the cheapest primary herb option
    (
        cheapest_5min_primary_cost,
        cheapest_15min_primary_cost,
        cheapest_1h_primary_cost,
        cheapest_3h_primary_cost,
        cheapest_5min_primary_label,
        cheapest_15min_primary_label,
        cheapest_1h_primary_label,
        cheapest_3h_primary_label,
    ) = get_cheapest_herb(
        [
            (harralander_cost, "Harralander"),
            (g_harralander_cost, "Grimy Harralander"),
            (harralander_unf_cost, "Unf Harralander"),
        ]
    )

    # Calculate Secondary Herb Cost (Aldarium)
    (aldarium_cost_5min, aldarium_cost_15min, aldarium_cost_1h, aldarium_cost_3h) = (
        get_secondary_cost(aldarium_item, goggles=goggles)
    )

    # Total Production Cost
    production_cost_5min += cheapest_5min_primary_cost + aldarium_cost_5min
    production_cost_15min += cheapest_15min_primary_cost + aldarium_cost_15min
    production_cost_1h += cheapest_1h_primary_cost + aldarium_cost_1h
    production_cost_3h += cheapest_3h_primary_cost + aldarium_cost_3h
    print(
        f"""
Goading 4 production cost (goggles: {goggles}, alchem: {alchem}):
 5min: {production_cost_5min}, 15min: {production_cost_15min}, 1h: {production_cost_1h}, 3h: {production_cost_3h}
 (Primary: {cheapest_5min_primary_label}, {cheapest_15min_primary_label}, {cheapest_1h_primary_label}, {cheapest_3h_primary_label})
 (Aldarium: {aldarium_cost_5min}, {aldarium_cost_15min}, {aldarium_cost_1h}, {aldarium_cost_3h})
    """
    )

    # Calculate price per dosage.
    dose_price_5min = (
        goading_4.latest_5min_price_low // 4 if goading_4.latest_5min_price_low else inf
    )
    dose_price_15min = (
        goading_4.latest_15min_price_low // 4
        if goading_4.latest_15min_price_low
        else inf
    )
    dose_price_1h = (
        goading_4.latest_1h_price_low // 4 if goading_4.latest_1h_price_low else inf
    )
    dose_price_3h = (
        goading_4.latest_3h_price_low // 4 if goading_4.latest_3h_price_low else inf
    )

    # Determine avg. doses made.
    doses_made = 3.15 if alchem else 3.0

    # Avg. Revenue per action.
    revenue_5min = dose_price_5min * doses_made
    revenue_15min = dose_price_15min * doses_made
    revenue_1h = dose_price_1h * doses_made
    revenue_3h = dose_price_3h * doses_made
    print(
        f"Goading 4 revenue (goggles: {goggles}, alchem: {alchem}):"
        f" 15min: {revenue_15min}, 1h: {revenue_1h}, 3h: {revenue_3h}"
    )

    # Profit after 2% tax
    profit_5min = (revenue_5min * 0.98) - production_cost_5min
    profit_15min = (revenue_15min * 0.98) - production_cost_15min
    profit_1h = (revenue_1h * 0.98) - production_cost_1h
    profit_3h = (revenue_3h * 0.98) - production_cost_3h
    print(
        f"Goading 4 profit (goggles: {goggles}, alchem: {alchem}):"
        f"5min: {profit_5min}, 15min: {profit_15min}, 1h: {profit_1h}, 3h: {profit_3h}"
    )

    # Profit per hour
    gp_per_hour_5min = profit_5min * potions_per_hour
    gp_per_hour_15min = profit_15min * potions_per_hour
    gp_per_hour_1h = profit_1h * potions_per_hour
    gp_per_hour_3h = profit_3h * potions_per_hour
    print(
        f"Goading 4 gp per hour (goggles: {goggles}, alchem: {alchem}):"
        f" 5min: {gp_per_hour_5min}, 15min: {gp_per_hour_15min}, 1h: {gp_per_hour_1h}, 3h: {gp_per_hour_3h}"
    )

    # Formatted Outputs - using dictionary for efficiency
    values_to_format = {
        "goading_4_cost_5m": goading_4.latest_5min_price_high,
        "goading_4_cost_15m": goading_4.latest_15min_price_high,
        "goading_4_cost_1h": goading_4.latest_1h_price_high,
        "goading_4_cost_3h": goading_4.latest_3h_price_high,
        "aldarium_cost_5m": aldarium_cost_5min,
        "aldarium_cost_15m": aldarium_cost_15min,
        "aldarium_cost_1h": aldarium_cost_1h,
        "aldarium_cost_3h": aldarium_cost_3h,
        "cheapest_5min_primary_cost": cheapest_5min_primary_cost,
        "cheapest_15min_primary_cost": cheapest_15min_primary_cost,
        "cheapest_1h_primary_cost": cheapest_1h_primary_cost,
        "cheapest_3h_primary_cost": cheapest_3h_primary_cost,
        "production_cost_5m": production_cost_5min,
        "production_cost_15m": production_cost_15min,
        "production_cost_1h": production_cost_1h,
        "production_cost_3h": production_cost_3h,
        "price_per_dose_5m": dose_price_5min,
        "price_per_dose_15m": dose_price_15min,
        "price_per_dose_1h": dose_price_1h,
        "price_per_dose_3h": dose_price_3h,
        "revenue_5m": revenue_5min,
        "revenue_15m": revenue_15min,
        "revenue_1h": revenue_1h,
        "revenue_3h": revenue_3h,
        "profit_5m": profit_5min,
        "profit_15m": profit_15min,
        "profit_1h": profit_1h,
        "profit_3h": profit_3h,
        "gp_per_hour_5m": gp_per_hour_5min,
        "gp_per_hour_15m": gp_per_hour_15min,
        "gp_per_hour_1h": gp_per_hour_1h,
        "gp_per_hour_3h": gp_per_hour_3h,
    }

    # Format all values in one go
    formatted_values = {}
    for key, value in values_to_format.items():
        if value is None or value == inf or value == -inf:
            formatted_values[key + "_fmt"] = "N/A"  # or some other default string
        else:
            formatted_values[key + "_fmt"] = format_currency(
                value, currency_symbol="gp", prefix=False, suffix=True
            )

    formatted_values = {
        "cheapest_5min_primary_label": cheapest_5min_primary_label,
        "cheapest_15min_primary_label": cheapest_15min_primary_label,
        "cheapest_1h_primary_label": cheapest_1h_primary_label,
        "cheapest_3h_primary_label": cheapest_3h_primary_label,
        **formatted_values,
    }

    # Now you can access like: formatted_values['aldarium_cost_15m_fmt']
    return formatted_values


def calculate_p_regen_prod_cost(
    goggles: bool = True, alchem: bool = True, potions_per_hour: int = 2500
):
    production_cost_5min = 0
    production_cost_15min = 0
    production_cost_1h = 0
    production_cost_3h = 0

    # Get Item costs
    p_regen_4 = osrsItemProperties(P_REGEN_4_ID)
    huasca = osrsItemProperties(HUASCA_ID)
    g_huasca = osrsItemProperties(G_HUASCA_ID)
    huasca_unf = osrsItemProperties(HUASCA_UNF_ID)

    # Calculate Primary Herb Cost (Huasca)
    huasca_cost = TempItem(*get_primary_cost(huasca, make_unf=True, clean_grimy=False))
    g_huasca_cost = TempItem(
        *get_primary_cost(g_huasca, make_unf=True, clean_grimy=True)
    )
    huasca_unf_cost = TempItem(
        *get_primary_cost(huasca_unf, make_unf=False, clean_grimy=False)
    )

    # Find the cheapest primary herb option
    (
        cheapest_5min_primary_cost,
        cheapest_15min_primary_cost,
        cheapest_1h_primary_cost,
        cheapest_3h_primary_cost,
        cheapest_5min_primary_label,
        cheapest_15min_primary_label,
        cheapest_1h_primary_label,
        cheapest_3h_primary_label,
    ) = get_cheapest_herb(
        [
            (huasca_cost, "Huasca"),
            (g_huasca_cost, "Grimy Huasca"),
            (huasca_unf_cost, "Unf Huasca"),
        ]
    )

    # Calculate Secondary Herb Cost (Aldarium)
    (aldarium_cost_5min, aldarium_cost_15min, aldarium_cost_1h, aldarium_cost_3h) = (
        get_secondary_cost(aldarium_item, goggles=goggles)
    )

    # Total Production Cost
    production_cost_5min += cheapest_5min_primary_cost + aldarium_cost_5min
    production_cost_15min += cheapest_15min_primary_cost + aldarium_cost_15min
    production_cost_1h += cheapest_1h_primary_cost + aldarium_cost_1h
    production_cost_3h += cheapest_3h_primary_cost + aldarium_cost_3h
    print(
        f"""
P Regen 4 production cost (goggles: {goggles}, alchem: {alchem}):
 5min: {production_cost_5min}, 15min: {production_cost_15min}, 1h: {production_cost_1h}, 3h: {production_cost_3h}
 (Primary: {cheapest_5min_primary_label}, {cheapest_15min_primary_label}, {cheapest_1h_primary_label}, {cheapest_3h_primary_label})
 (Aldarium: {aldarium_cost_5min}, {aldarium_cost_15min}, {aldarium_cost_1h}, {aldarium_cost_3h})
    """
    )

    # Calculate price per dosage.
    dose_price_5min = (
        p_regen_4.latest_5min_price_low // 4 if p_regen_4.latest_5min_price_low else inf
    )
    dose_price_15min = (
        p_regen_4.latest_15min_price_low // 4
        if p_regen_4.latest_15min_price_low
        else inf
    )
    dose_price_1h = (
        p_regen_4.latest_1h_price_low // 4 if p_regen_4.latest_1h_price_low else inf
    )
    dose_price_3h = (
        p_regen_4.latest_3h_price_low // 4 if p_regen_4.latest_3h_price_low else inf
    )

    # Determine avg. doses made.
    doses_made = 3.15 if alchem else 3.0

    # Avg. Revenue per action.
    revenue_5min = dose_price_5min * doses_made
    revenue_15min = dose_price_15min * doses_made
    revenue_1h = dose_price_1h * doses_made
    revenue_3h = dose_price_3h * doses_made
    print(
        f"P Regen 4 revenue (goggles: {goggles}, alchem: {alchem}):"
        f" 5min: {revenue_5min}, 15min: {revenue_15min}, 1h: {revenue_1h}, 3h: {revenue_3h}"
    )

    # Profit after 2% tax
    profit_5min = (revenue_5min * 0.98) - production_cost_5min
    profit_15min = (revenue_15min * 0.98) - production_cost_15min
    profit_1h = (revenue_1h * 0.98) - production_cost_1h
    profit_3h = (revenue_3h * 0.98) - production_cost_3h
    print(
        f"P Regen 4 profit (goggles: {goggles}, alchem: {alchem}):"
        f" 5min: {profit_5min}, 15min: {profit_15min}, 1h: {profit_1h}, 3h: {profit_3h}"
    )

    # Profit per hour
    gp_per_hour_5min = profit_5min * potions_per_hour
    gp_per_hour_15min = profit_15min * potions_per_hour
    gp_per_hour_1h = profit_1h * potions_per_hour
    gp_per_hour_3h = profit_3h * potions_per_hour
    print(
        f"P Regen 4 gp per hour (goggles: {goggles}, alchem: {alchem}):"
        f" 5min: {gp_per_hour_5min}, 15min: {gp_per_hour_15min}, 1h: {gp_per_hour_1h}, 3h: {gp_per_hour_3h}"
    )

    # Formatted Outputs - using dictionary for efficiency
    values_to_format = {
        "pregen4_cost_5m": p_regen_4.latest_5min_price_high,
        "pregen4_cost_15m": p_regen_4.latest_15min_price_high,
        "pregen4_cost_1h": p_regen_4.latest_1h_price_high,
        "pregen4_cost_3h": p_regen_4.latest_3h_price_high,
        "aldarium_cost_5m": aldarium_cost_5min,
        "aldarium_cost_15m": aldarium_cost_15min,
        "aldarium_cost_1h": aldarium_cost_1h,
        "aldarium_cost_3h": aldarium_cost_3h,
        "cheapest_5min_primary_cost": cheapest_5min_primary_cost,
        "cheapest_15min_primary_cost": cheapest_15min_primary_cost,
        "cheapest_1h_primary_cost": cheapest_1h_primary_cost,
        "cheapest_3h_primary_cost": cheapest_3h_primary_cost,
        "production_cost_5m": production_cost_5min,
        "production_cost_15m": production_cost_15min,
        "production_cost_1h": production_cost_1h,
        "production_cost_3h": production_cost_3h,
        "price_per_dose_5m": dose_price_5min,
        "price_per_dose_15m": dose_price_15min,
        "price_per_dose_1h": dose_price_1h,
        "price_per_dose_3h": dose_price_3h,
        "revenue_5m": revenue_5min,
        "revenue_15m": revenue_15min,
        "revenue_1h": revenue_1h,
        "revenue_3h": revenue_3h,
        "profit_5m": profit_5min,
        "profit_15m": profit_15min,
        "profit_1h": profit_1h,
        "profit_3h": profit_3h,
        "gp_per_hour_5m": gp_per_hour_5min,
        "gp_per_hour_15m": gp_per_hour_15min,
        "gp_per_hour_1h": gp_per_hour_1h,
        "gp_per_hour_3h": gp_per_hour_3h,
    }

    # Format all values in one go
    formatted_values = {}
    for key, value in values_to_format.items():
        if value is None or value == inf or value == -inf or value == 'nan':
            formatted_values[key + "_fmt"] = "N/A"  # or some other default string
        else:
            formatted_values[key + "_fmt"] = format_currency(
                value, currency_symbol="gp", prefix=False, suffix=True
            )

    formatted_values = {
        "cheapest_5min_primary_label": cheapest_5min_primary_label,
        "cheapest_15min_primary_label": cheapest_15min_primary_label,
        "cheapest_1h_primary_label": cheapest_1h_primary_label,
        "cheapest_3h_primary_label": cheapest_3h_primary_label,
        **formatted_values,
    }
    # Now you can access like: formatted_values['aldarium_cost_15m_fmt']
    return formatted_values

def get_cheapest_herb(items: list[tuple]):
    cheapest_5min = inf
    cheapest_5min_label = ""
    cheapest_15min = inf
    cheapest_15min_label = ""
    cheapest_1h = inf
    cheapest_1h_label = ""
    cheapest_3h = inf
    cheapest_3h_label = ""

    for item, label in items:
        price_5min = item.latest_5min_price_low if item.latest_5min_price_low else inf
        price_15min = (
            item.latest_15min_price_low if item.latest_15min_price_low else inf
        )
        price_1h = item.latest_1h_price_low if item.latest_1h_price_low else inf
        price_3h = item.latest_3h_price_low if item.latest_3h_price_low else inf

        if price_5min < cheapest_5min:
            cheapest_5min = price_5min
            cheapest_5min_label = label
        if price_15min < cheapest_15min:
            cheapest_15min = price_15min
            cheapest_15min_label = label
        if price_1h < cheapest_1h:
            cheapest_1h = price_1h
            cheapest_1h_label = label
        if price_3h < cheapest_3h:
            cheapest_3h = price_3h
            cheapest_3h_label = label

    print(
        f"5min: {cheapest_5min},        15min: {cheapest_15min},        1h: {cheapest_1h},        3h: {cheapest_3h}"
    )
    print(
        f"Labels: {cheapest_5min_label}, {cheapest_15min_label}, {cheapest_1h_label}, {cheapest_3h_label}"
    )
    return (
        cheapest_5min,
        cheapest_15min,
        cheapest_1h,
        cheapest_3h,
        cheapest_5min_label,
        cheapest_15min_label,
        cheapest_1h_label,
        cheapest_3h_label,
    )


def get_secondary_cost(item, goggles: bool = True):
    price_5min = item.latest_5min_price_low if item.latest_5min_price_low else inf
    price_15min = item.latest_15min_price_low if item.latest_15min_price_low else inf
    price_1h = item.latest_1h_price_low if item.latest_1h_price_low else inf
    price_3h = item.latest_3h_price_low if item.latest_3h_price_low else inf
    item_usage = 1 - GOGGLE_CHANCE if goggles else 1

    if goggles:
        price_5min += (
            (GOGGLE_CHANCE * aoc_proc_cost_5min) if aoc_proc_cost_5min else inf
        )
        price_15min += (
            (GOGGLE_CHANCE * aoc_proc_cost_15min) if aoc_proc_cost_15min else inf
        )
        price_1h += (GOGGLE_CHANCE * aoc_proc_cost_1h) if aoc_proc_cost_1h else inf
        price_3h += (GOGGLE_CHANCE * aoc_proc_cost_3h) if aoc_proc_cost_3h else inf

    price_5min = item_usage * price_5min
    price_15min = item_usage * price_15min
    price_1h = item_usage * price_1h
    price_3h = item_usage * price_3h

    return price_5min, price_15min, price_1h, price_3h


def get_primary_cost(item, make_unf: bool = True, clean_grimy: bool = True):
    price_5min = item.latest_5min_price_low if item.latest_5min_price_low else inf
    price_15min = item.latest_15min_price_low if item.latest_15min_price_low else inf
    price_1h = item.latest_1h_price_low if item.latest_1h_price_low else inf
    price_3h = item.latest_3h_price_low if item.latest_3h_price_low else inf

    price_5min += ZAHUR_FEE if make_unf else 0
    price_15min += ZAHUR_FEE if make_unf else 0
    price_1h += ZAHUR_FEE if make_unf else 0
    price_3h += ZAHUR_FEE if make_unf else 0
    price_5min += ZAHUR_FEE if clean_grimy else 0
    price_15min += ZAHUR_FEE if clean_grimy else 0
    price_1h += ZAHUR_FEE if clean_grimy else 0
    price_3h += ZAHUR_FEE if clean_grimy else 0

    return price_5min, price_15min, price_1h, price_3h


class GoadingRegens:
    def __init__(self):
        """Initialize Goading Regens calculator"""
        from flask import render_template

        self.render_template = render_template

    def display(self):
        """Display the goading regens calculation results"""
        try:
            # Calculate both goading and p_regen data
            goading_data = calculate_goading_prod_cost(
                goggles=True, alchem=True, potions_per_hour=2500
            )
            p_regen_data = calculate_p_regen_prod_cost(
                goggles=True, alchem=True, potions_per_hour=2500
            )

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
    import json

    print("Calculating goading and p_regen production costs and profits...")
    print("\n" + "=" * 60)
    print("GOADING 4 CALCULATIONS")
    print("=" * 60)
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
