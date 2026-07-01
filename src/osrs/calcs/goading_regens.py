from pathlib import Path
import sys

ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent

if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from src.osrs.calcs.herblore_potion_calc import (
    HerblorePotionCalc,
    CHEM_CHANCE,
    GOGGLE_CHANCE,
    GE_TAX,
)

# Potion-specific item IDs
GOADING_4_ID = 30137
P_REGEN_4_ID = 30125

HUASCA_ID = 30097
G_HUASCA_ID = 30094
HUASCA_UNF_ID = 30100

HARRALANDER_ID = 255
G_HARRALANDER_ID = 205
HARRALANDER_UNF_ID = 97

ALDARIUM_ID = 29993


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
