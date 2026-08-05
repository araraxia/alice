#!/usr/bin/env python3
"""
Sync conf/herblore_action_table.csv <-> herblore.action_step (osrs database).

Usage:
    python src/scripts/load_herblore_action_table.py            # CSV -> SQL (upsert, default)
    python src/scripts/load_herblore_action_table.py --to-sql    # CSV -> SQL (upsert)
    python src/scripts/load_herblore_action_table.py --from-sql  # SQL -> CSV (overwrite CSV)
"""

from pathlib import Path
import sys, json, argparse

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.osrs.calcs.herblore_step_calc import parse_csv, export_csv
from src.util.sql_helper import add_update_record

COLUMNS = [
    "step_id",
    "potion_family",
    "step_label",
    "input_1_item",
    "input_1_qty",
    "input_2",
    "output",
    "output_extra_dose",
    "output_doses",
    "xp",
    "level_req",
    "zahur_clean",
    "zahur_unf",
    "wesley",
    "dose_amulet",
    "goggles",
]


def load(csv_path=None):
    steps = parse_csv(csv_path)

    for step in steps:
        values = [
            step["step_id"],
            step["potion_family"],
            step["step_label"],
            step["input_1"]["name"] if step["input_1"] else "",
            step["input_1"]["qty"] if step["input_1"] else 1,
            json.dumps(step["input_2"]),
            step["output"],
            step["output_extra_dose_flag"] or None,
            step["output_doses"],
            step["xp"],
            step["level_req"],
            step["zahur_clean"],
            step["zahur_unf"],
            step["wesley"],
            step["dose_amulet"],
            step["goggles"],
        ]

        add_update_record(
            database="osrs",
            schema="herblore",
            table="action_step",
            columns=COLUMNS,
            values=values,
            conflict_target=["step_id"],
            on_conflict="DO UPDATE SET",
        )
        print(f"Upserted {step['step_id']}")

    print(f"Done — {len(steps)} steps synced to herblore.action_step")


def pull(csv_path=None):
    """Overwrite the CSV with the current contents of herblore.action_step."""
    count = export_csv(csv_path)
    print(f"Done — {count} steps exported from herblore.action_step to CSV")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    direction = parser.add_mutually_exclusive_group()
    direction.add_argument("--to-sql", action="store_true", help="CSV -> SQL (upsert, default)")
    direction.add_argument("--from-sql", action="store_true", help="SQL -> CSV (overwrite CSV)")
    parser.add_argument("--csv-path", default=None, help="Override the CSV path (defaults to conf/herblore_action_table.csv)")
    args = parser.parse_args()

    if args.from_sql:
        pull(args.csv_path)
    else:
        load(args.csv_path)
