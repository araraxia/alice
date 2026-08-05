from pathlib import Path
import csv, os, re, sys, json

ROOT_PATH = Path(__file__).resolve().parent.parent.parent.parent

if str(ROOT_PATH) not in sys.path:
    sys.path.append(str(ROOT_PATH))

from psycopg2.errors import UndefinedTable
from psycopg2.extras import RealDictCursor

from src.osrs.item_properties import osrsItemProperties
from src.util.sql_helper import (
    init_psql_connection,
    create_cursor,
    get_records,
    get_all_records,
    fetch_top,
    search_records,
    fuzzy_search_records,
)
from dotenv import load_dotenv

load_dotenv(".env_public")

# Constants (see plan_herblore_csv_tool.md)
GE_TAX = float(os.getenv("GE_TAX", default=0.02))
ZAHUR_FEE = int(os.getenv("ZAHUR_FEE", default=200))
WESLEY_FEE = int(os.getenv("WESLEY_FEE", default=50))
ALC_AMUL_CHANCE = float(os.getenv("ALC_AMUL_CHANCE", default=0.15))
CHEM_AMU_CHANCE = float(os.getenv("CHEM_AMU_CHANCE", default=0.10))
PRES_GOGGLES_CHANCE = float(os.getenv("PRES_GOGGLES_CHANCE", default=0.1111))

AOC_ITEM_ID = 21163  # Amulet of Chemistry

CSV_PATH = ROOT_PATH / "conf" / "herblore_action_table.csv"

TIMEFRAMES = ["5min", "15min", "1h", "3h"]

QTY_RE = re.compile(r"^(\d+)x\s+(.+)$")
DOSE_SUFFIX_RE = re.compile(r"\(\d+\)\s*$")

FAMILY_LABEL_OVERRIDES = {
    "antivenom_p": "Anti-venom+",
    "super_combat": "Super Combat Potion",
    "prayer_regen": "Prayer Regeneration Potion",
}


def _parse_qty_item(raw: str) -> dict:
    """Parse an optional 'Nx ' quantity prefix off an item name. Defaults qty to 1."""
    raw = raw.strip()
    match = QTY_RE.match(raw)
    if match:
        return {"name": match.group(2).strip(), "qty": int(match.group(1))}
    return {"name": raw, "qty": 1}


def _split_pipe(field: str) -> list:
    """CSV multi-value fields (potion_family, input_2) are delimited with a literal '\\|'."""
    if not field:
        return []
    return [part.strip() for part in field.split("\\|") if part.strip()]


def _base_potion_name(output_name: str) -> str:
    """Strip a trailing '(N)' dose suffix off a GE item name, e.g. 'Goading potion(3)' -> 'Goading potion'."""
    return DOSE_SUFFIX_RE.sub("", output_name).strip()


def _to_four_dose_name(output_name: str) -> str:
    """Replace the trailing dose suffix with (4), preserving any space before the paren.
    e.g. 'Goading potion(3)' -> 'Goading potion(4)', 'Haemostatic dressing (3)' -> 'Haemostatic dressing (4)'."""
    return DOSE_SUFFIX_RE.sub("(4)", output_name)


def _to_bool(value) -> bool:
    return str(value).strip().upper() == "TRUE"


def _format_qty_item(name: str, qty: int) -> str:
    """Inverse of _parse_qty_item: 'Harralander', 1 -> 'Harralander'; 'Harralander', 2 -> '2x Harralander'."""
    return f"{qty}x {name}" if qty and qty != 1 else name


def _join_pipe(parts: list) -> str:
    return "\\|".join(p for p in parts if p)


def _format_number(value) -> str:
    """Render a number without a trailing '.0'/'.00' so re-exported CSVs match the hand-authored style."""
    if value is None:
        return ""
    value = float(value)  # psycopg2 returns NUMERIC columns as decimal.Decimal
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _weighted_avg(prices: list, volumes: list) -> float:
    """Volume-weighted average price — same algorithm as osrsItemProperties.average_price."""
    n = total = 0
    for p, v in zip(prices, volumes):
        if p and v:
            n += v
            total += p * v
    return total / n if n > 0 else 0


class _PriceData:
    """
    Lightweight price attribute bag with the same interface _price_from_props() expects.
    Used by the batch loader to avoid instantiating osrsItemProperties per item.
    """
    __slots__ = [
        "latest_5min_price_high", "latest_5min_price_low", "latest_5min_price_average",
        "latest_15min_price_high", "latest_15min_price_low", "latest_15min_price_average",
        "latest_1h_price_high", "latest_1h_price_low", "latest_1h_price_average",
        "latest_3h_price_high", "latest_3h_price_low", "latest_3h_price_average",
    ]

    def __init__(self):
        for attr in self.__slots__:
            setattr(self, attr, 0)


CSV_FIELDNAMES = [
    "step_id",
    "potion_family",
    "step_label",
    "input_1",
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


def db_record_to_csv_row(record: dict) -> dict:
    """Reverse of parse_csv()'s normalisation, applied to a herblore.action_step DB row."""
    input_2_items = record.get("input_2") or []
    if isinstance(input_2_items, str):
        input_2_items = json.loads(input_2_items)

    input_1_item = record.get("input_1_item") or ""
    input_1_display = (
        _format_qty_item(input_1_item, record.get("input_1_qty") or 1) if input_1_item else ""
    )

    return {
        "step_id": record["step_id"],
        "potion_family": _join_pipe(record.get("potion_family") or []),
        "step_label": record.get("step_label") or "",
        "input_1": input_1_display,
        "input_2": _join_pipe(_format_qty_item(i["name"], i.get("qty", 1)) for i in input_2_items),
        "output": record.get("output") or "",
        "output_extra_dose": record.get("output_extra_dose") or "",
        "output_doses": _format_number(record.get("output_doses")),
        "xp": _format_number(record.get("xp")),
        "level_req": _format_number(record.get("level_req")),
        "zahur_clean": "TRUE" if record.get("zahur_clean") else "FALSE",
        "zahur_unf": "TRUE" if record.get("zahur_unf") else "FALSE",
        "wesley": "TRUE" if record.get("wesley") else "FALSE",
        "dose_amulet": "TRUE" if record.get("dose_amulet") else "FALSE",
        "goggles": "TRUE" if record.get("goggles") else "FALSE",
    }


def export_csv(csv_path=None) -> int:
    """
    Pull the current state of herblore.action_step and overwrite conf/herblore_action_table.csv
    with it — the reverse of parse_csv() + the loader's upsert. Rows are ordered by step_id for
    a stable, diffable output.
    """
    records = get_all_records(database="osrs", schema="herblore", table="action_step")
    records.sort(key=lambda r: r["step_id"])

    path = Path(csv_path) if csv_path else CSV_PATH
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(db_record_to_csv_row(record))

    return len(records)


def parse_csv(csv_path=None) -> list:
    """
    Parse conf/herblore_action_table.csv into a list of normalized step dicts, per the field
    normalisations described in plan_herblore_csv_tool.md's Script Design section.
    """
    path = Path(csv_path) if csv_path else CSV_PATH
    steps = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step_id = (row.get("step_id") or "").strip()
            if not step_id:
                continue

            input_1_raw = (row.get("input_1") or "").strip()
            output_doses_raw = (row.get("output_doses") or "").strip()
            level_req_raw = (row.get("level_req") or "").strip()
            xp_raw = (row.get("xp") or "").strip()

            steps.append(
                {
                    "step_id": step_id,
                    "potion_family": _split_pipe(row.get("potion_family") or ""),
                    "step_label": (row.get("step_label") or "").strip(),
                    "input_1": _parse_qty_item(input_1_raw) if input_1_raw else None,
                    "input_2": [_parse_qty_item(x) for x in _split_pipe(row.get("input_2") or "")],
                    "output": (row.get("output") or "").strip(),
                    "output_extra_dose_flag": (row.get("output_extra_dose") or "").strip(),
                    "output_doses": int(float(output_doses_raw)) if output_doses_raw else None,
                    "xp": float(xp_raw) if xp_raw else 0.0,
                    "level_req": int(float(level_req_raw)) if level_req_raw else 0,
                    "zahur_clean": _to_bool(row.get("zahur_clean")),
                    "zahur_unf": _to_bool(row.get("zahur_unf")),
                    "wesley": _to_bool(row.get("wesley")),
                    "dose_amulet": _to_bool(row.get("dose_amulet")),
                    "goggles": _to_bool(row.get("goggles")),
                }
            )

    return steps


def parse_sql() -> list:
    """
    Load herblore.action_step from PostgreSQL and return the same normalized step dicts
    as parse_csv(). DB values are already typed — no string parsing required.
    """
    records = get_all_records(database="osrs", schema="herblore", table="action_step")
    records.sort(key=lambda r: r["step_id"])

    steps = []
    for record in records:
        input_2_raw = record.get("input_2") or []
        if isinstance(input_2_raw, str):
            input_2_raw = json.loads(input_2_raw)

        input_1_item = (record.get("input_1_item") or "").strip()
        input_1_qty = record.get("input_1_qty") or 1
        output_doses = record.get("output_doses")

        steps.append(
            {
                "step_id": record["step_id"],
                "potion_family": list(record.get("potion_family") or []),
                "step_label": (record.get("step_label") or "").strip(),
                "input_1": {"name": input_1_item, "qty": int(input_1_qty)} if input_1_item else None,
                "input_2": [{"name": i["name"], "qty": int(i.get("qty", 1))} for i in input_2_raw],
                "output": (record.get("output") or "").strip(),
                "output_extra_dose_flag": (record.get("output_extra_dose") or "").strip(),
                "output_doses": int(output_doses) if output_doses is not None else None,
                "xp": float(record.get("xp") or 0),
                "level_req": int(record.get("level_req") or 0),
                "zahur_clean": bool(record.get("zahur_clean")),
                "zahur_unf": bool(record.get("zahur_unf")),
                "wesley": bool(record.get("wesley")),
                "dose_amulet": bool(record.get("dose_amulet")),
                "goggles": bool(record.get("goggles")),
            }
        )

    return steps


class HerbloreStepCalc:
    """
    Ingests conf/herblore_action_table.csv, resolves live GE prices for every referenced item,
    and computes cost/revenue/profit/xp-per-cost for each step across all four price timeframes
    and all applicable equipment/NPC modifiers. See plan_herblore_csv_tool.md for the full spec.
    """

    def __init__(self):
        self.steps = []
        self._item_id_cache = {}
        self._props_cache = {}

    # ------------------------------------------------------------------ #
    # Item resolution / pricing
    # ------------------------------------------------------------------ #

    def _resolve_item_id(self, name: str):
        key = name.strip()
        if key in self._item_id_cache:
            return self._item_id_cache[key]

        item_id = None
        try:
            exact = search_records(
                database="osrs", schema="items", table="map", column="name", value=key
            )
        except Exception as e:
            print(f"[herblore_step_calc] ERROR: exact lookup for '{key}' failed: {e}")
            exact = []

        if exact:
            item_id = exact[0]["id"]
        else:
            try:
                fuzzy = fuzzy_search_records(
                    database="osrs",
                    schema_name="items",
                    table_name="map",
                    column_name="name",
                    search_pattern=key,
                    case_sensitive=False,
                )
            except Exception as e:
                print(f"[herblore_step_calc] ERROR: fuzzy lookup for '{key}' failed: {e}")
                fuzzy = []

            if len(fuzzy) == 1:
                item_id = fuzzy[0]["id"]
                print(
                    f"[herblore_step_calc] WARNING: '{key}' resolved via fuzzy match to "
                    f"'{fuzzy[0]['name']}' (id {item_id})"
                )
            else:
                print(
                    f"[herblore_step_calc] WARNING: could not resolve item '{key}' to a unique "
                    f"GE item ({len(fuzzy)} fuzzy matches) — pricing this item as 0"
                )

        self._item_id_cache[key] = item_id
        return item_id

    def _get_props(self, name: str):
        item_id = self._resolve_item_id(name)
        if item_id is None:
            return None
        if item_id not in self._props_cache:
            self._props_cache[item_id] = osrsItemProperties(item_id)
        return self._props_cache[item_id]

    def _aoc_props(self):
        if AOC_ITEM_ID not in self._props_cache:
            self._props_cache[AOC_ITEM_ID] = osrsItemProperties(AOC_ITEM_ID)
        return self._props_cache[AOC_ITEM_ID]

    # ------------------------------------------------------------------ #
    # Batch preloading — collapses N×4 connections down to 1
    # ------------------------------------------------------------------ #

    def _collect_all_item_names(self) -> set:
        """Walk self.steps and return every distinct item name that will need a price lookup."""
        names = set()
        for step in self.steps:
            if step["input_1"]:
                names.add(step["input_1"]["name"])
            for item in step["input_2"]:
                names.add(item["name"])
            if step["output"]:
                names.add(step["output"])
                if step["output_doses"]:
                    # Revenue is priced off the 4-dose form regardless of actual output dose count
                    names.add(_to_four_dose_name(step["output"]))
        return names

    def _batch_resolve_names(self, names: set):
        """
        Resolve all item names to IDs in a single WHERE name IN (...) query, then fall back
        to per-item fuzzy search only for names that still couldn't be matched exactly.
        Populates self._item_id_cache.
        """
        names_list = [n for n in names if n not in self._item_id_cache]
        if not names_list:
            return

        conn = init_psql_connection("osrs")
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            rows = get_records(
                database="osrs", schema="items", table="map", column="name",
                values=names_list, cursor=cur, connection=conn,
            )
            for row in rows:
                self._item_id_cache[row["name"]] = row["id"]
        except Exception as e:
            print(f"[herblore_step_calc] ERROR: batch name resolution failed: {e}")
        finally:
            cur.close()
            conn.close()

        # Fuzzy fallback only for the unresolved remainder
        for name in names_list:
            if name not in self._item_id_cache:
                self._resolve_item_id(name)

    def _load_item_prices_shared(self, item_id: int, cursor, conn) -> _PriceData:
        """
        Fetch price data for one item using a caller-supplied shared cursor/connection.
        Replicates the 5min→15min and 1h→3h derivation logic from osrsItemProperties
        without opening any new connections.
        """
        data = _PriceData()

        # 5min table → populates latest_5min_* and derived latest_15min_*
        try:
            rows_5 = fetch_top(
                cursor=cursor, connection=conn,
                database="osrs", schema_name="prices",
                table_name=f"{item_id}_5min",
                sort_col="timestamp", limit=3,
            )
        except UndefinedTable:
            conn.rollback()
            rows_5 = []
        except Exception:
            conn.rollback()
            rows_5 = []

        if rows_5:
            r0 = rows_5[0]
            data.latest_5min_price_high = r0.get("avgHighPrice") or 0
            data.latest_5min_price_low = r0.get("avgLowPrice") or 0
            vh0 = r0.get("highPriceVolume") or 0
            vl0 = r0.get("lowPriceVolume") or 0
            data.latest_5min_price_average = _weighted_avg(
                [data.latest_5min_price_high, data.latest_5min_price_low], [vh0, vl0]
            )
            h_prices = [r.get("avgHighPrice") or 0 for r in rows_5]
            l_prices = [r.get("avgLowPrice") or 0 for r in rows_5]
            h_vols = [r.get("highPriceVolume") or 0 for r in rows_5]
            l_vols = [r.get("lowPriceVolume") or 0 for r in rows_5]
            data.latest_15min_price_high = _weighted_avg(h_prices, h_vols)
            data.latest_15min_price_low = _weighted_avg(l_prices, l_vols)
            data.latest_15min_price_average = _weighted_avg(h_prices + l_prices, h_vols + l_vols)

        # 1h table → populates latest_1h_* and derived latest_3h_*
        try:
            rows_1h = fetch_top(
                cursor=cursor, connection=conn,
                database="osrs", schema_name="prices",
                table_name=f"{item_id}_1h",
                sort_col="timestamp", limit=3,
            )
        except UndefinedTable:
            conn.rollback()
            rows_1h = []
        except Exception:
            conn.rollback()
            rows_1h = []

        if rows_1h:
            r0 = rows_1h[0]
            data.latest_1h_price_high = r0.get("avgHighPrice") or 0
            data.latest_1h_price_low = r0.get("avgLowPrice") or 0
            vh0 = r0.get("highPriceVolume") or 0
            vl0 = r0.get("lowPriceVolume") or 0
            data.latest_1h_price_average = _weighted_avg(
                [data.latest_1h_price_high, data.latest_1h_price_low], [vh0, vl0]
            )
            h_prices = [r.get("avgHighPrice") or 0 for r in rows_1h]
            l_prices = [r.get("avgLowPrice") or 0 for r in rows_1h]
            h_vols = [r.get("highPriceVolume") or 0 for r in rows_1h]
            l_vols = [r.get("lowPriceVolume") or 0 for r in rows_1h]
            data.latest_3h_price_high = _weighted_avg(h_prices, h_vols)
            data.latest_3h_price_low = _weighted_avg(l_prices, l_vols)
            data.latest_3h_price_average = _weighted_avg(h_prices + l_prices, h_vols + l_vols)

        return data

    def _batch_load_prices(self):
        """
        Open one shared connection and load price data for every item in self._item_id_cache
        plus AoC. Populates self._props_cache with _PriceData objects.
        Each item still requires two fetch_top calls (5min table + 1h table) but all of them
        share the same connection, eliminating the per-item open/close overhead.
        """
        item_ids = list({id for id in self._item_id_cache.values() if id is not None})
        item_ids.append(AOC_ITEM_ID)
        item_ids = list(set(item_ids))

        conn = init_psql_connection("osrs")
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for item_id in item_ids:
                if item_id not in self._props_cache:
                    self._props_cache[item_id] = self._load_item_prices_shared(item_id, cur, conn)
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def _price_from_props(props, timeframe: str, side: str) -> float:
        if not props:
            return 0
        primary = getattr(props, f"latest_{timeframe}_price_{side}", None)
        if primary:
            return primary
        avg = getattr(props, f"latest_{timeframe}_price_average", None)
        return avg or 0

    def _price(self, name: str, timeframe: str, side: str) -> float:
        return self._price_from_props(self._get_props(name), timeframe, side)

    # ------------------------------------------------------------------ #
    # Pricing logic (see plan_herblore_csv_tool.md "Pricing Logic")
    # ------------------------------------------------------------------ #

    def _price_components(self, step: dict, timeframe: str) -> dict:
        """Raw, unmodified price components for one step/timeframe (pre-modifier)."""
        in1_price = 0.0
        if step["input_1"]:
            in1_price = self._price(step["input_1"]["name"], timeframe, "low") * step["input_1"]["qty"]

        in2 = [
            {"name": i["name"], "price": round(self._price(i["name"], timeframe, "low") * i["qty"], 2)}
            for i in step["input_2"]
        ]

        four_dose_price = 0.0
        standalone_price = 0.0
        if step["output_doses"]:
            four_dose_price = self._price(_to_four_dose_name(step["output"]), timeframe, "high")
        else:
            standalone_price = self._price(step["output"], timeframe, "high")

        aoc_price = self._price_from_props(self._aoc_props(), timeframe, "low")

        return {
            "input_1_name": step["input_1"]["name"] if step["input_1"] else None,
            "input_1_price": round(in1_price, 2),
            "input_2": in2,
            "output_doses": step["output_doses"],
            "four_dose_price": round(four_dose_price, 2),
            "standalone_price": round(standalone_price, 2),
            "aoc_price": round(aoc_price, 2),
        }

    @staticmethod
    def _economics_from_raw(step: dict, raw: dict, goggles: bool, zahur_clean: bool, zahur_unf: bool, wesley: bool, amulet: str) -> dict:
        """
        Compute cost/revenue/profit/xp_per_cost from raw price components given a modifier
        selection. `amulet` is one of "none" | "chem" | "alch". Mirrors the formulas in
        plan_herblore_csv_tool.md's "Pricing Logic" section — used for both the per-step
        variant table and (by the frontend, reimplemented in JS from the same `raw` data) for
        pipeline aggregation.
        """
        mods = set(
            flag
            for flag in ("zahur_clean", "zahur_unf", "wesley", "goggles", "dose_amulet")
            if step[flag]
        )

        sec_total = sum(i["price"] for i in raw["input_2"])
        if goggles and "goggles" in mods:
            sec_total *= 1 - PRES_GOGGLES_CHANCE

        cost = raw["input_1_price"] + sec_total
        if zahur_clean and "zahur_clean" in mods:
            cost += ZAHUR_FEE
        if zahur_unf and "zahur_unf" in mods:
            cost += ZAHUR_FEE
        if wesley and "wesley" in mods:
            cost += WESLEY_FEE
        if amulet != "none" and "dose_amulet" in mods:
            cost += (raw["aoc_price"] / 10) * PRES_GOGGLES_CHANCE if "goggles" in mods else 0

        revenue = None
        if raw["output_doses"]:
            price_per_dose = raw["four_dose_price"] / 4 if raw["four_dose_price"] else 0
            doses = raw["output_doses"]
            if amulet == "chem" and "dose_amulet" in mods:
                doses += CHEM_AMU_CHANCE
            elif amulet == "alch" and "dose_amulet" in mods:
                doses += ALC_AMUL_CHANCE
            revenue = price_per_dose * doses * (1 - GE_TAX)
        elif raw["standalone_price"]:
            revenue = raw["standalone_price"] * (1 - GE_TAX)

        profit = (revenue - cost) if revenue is not None else None
        xp_per_cost = (step["xp"] / cost) if (step["xp"] and cost) else 0

        return {
            "cost": round(cost, 2),
            "revenue": round(revenue, 2) if revenue is not None else None,
            "profit": round(profit, 2) if profit is not None else None,
            "xp_per_cost": round(xp_per_cost, 4),
        }

    def _compute_timeframe(self, step: dict, timeframe: str) -> dict:
        raw = self._price_components(step, timeframe)

        variant_selections = {"baseline": dict(goggles=False, zahur_clean=False, zahur_unf=False, wesley=False, amulet="none")}
        if step["goggles"]:
            variant_selections["with_goggles"] = dict(goggles=True, zahur_clean=False, zahur_unf=False, wesley=False, amulet="none")
        if step["zahur_clean"]:
            variant_selections["with_zahur_clean"] = dict(goggles=False, zahur_clean=True, zahur_unf=False, wesley=False, amulet="none")
        if step["zahur_unf"]:
            variant_selections["with_zahur_unf"] = dict(goggles=False, zahur_clean=False, zahur_unf=True, wesley=False, amulet="none")
        if step["wesley"]:
            variant_selections["with_wesley"] = dict(goggles=False, zahur_clean=False, zahur_unf=False, wesley=True, amulet="none")
        if step["dose_amulet"]:
            variant_selections["with_chem_amulet"] = dict(goggles=False, zahur_clean=False, zahur_unf=False, wesley=False, amulet="chem")
            variant_selections["with_alch_amulet"] = dict(goggles=False, zahur_clean=False, zahur_unf=False, wesley=False, amulet="alch")

        out = {
            key: self._economics_from_raw(step, raw, **selection)
            for key, selection in variant_selections.items()
        }
        out["raw"] = raw
        return out

    # ------------------------------------------------------------------ #
    # Step / family assembly
    # ------------------------------------------------------------------ #

    @staticmethod
    def _family_label(family_id: str) -> str:
        if family_id in FAMILY_LABEL_OVERRIDES:
            return FAMILY_LABEL_OVERRIDES[family_id]
        return family_id.replace("_", " ").title()

    @staticmethod
    def _display_item(item: dict) -> str:
        prefix = f"{item['qty']}x " if item["qty"] != 1 else ""
        return f"{prefix}{item['name']}"

    def _compute_step(self, step: dict) -> dict:
        timeframes_out = {tf: self._compute_timeframe(step, tf) for tf in TIMEFRAMES}

        available_modifiers = [
            flag
            for flag in ("zahur_clean", "zahur_unf", "wesley", "goggles", "dose_amulet")
            if step[flag]
        ]

        if step["zahur_clean"]:
            step_type = "clean"
        elif step["zahur_unf"]:
            step_type = "make_unf"
        else:
            step_type = "combine"

        return {
            "label": step["step_label"],
            "step_type": step_type,
            "level_req": step["level_req"],
            "xp": step["xp"],
            "input_1": self._display_item(step["input_1"]) if step["input_1"] else None,
            "input_2": [self._display_item(i) for i in step["input_2"]],
            "output": step["output"],
            "timeframes": timeframes_out,
            "available_modifiers": available_modifiers,
        }

    def compute(self) -> dict:
        self.steps = parse_sql()

        # Pre-load all item IDs and prices in two bulk passes instead of per-step
        self._batch_resolve_names(self._collect_all_item_names())
        self._batch_load_prices()

        family_entries = {}  # family_id -> [(raw_step, computed_step_dict), ...]
        for step in self.steps:
            computed = self._compute_step(step)
            for family_id in step["potion_family"]:
                family_entries.setdefault(family_id, []).append((step, computed))

        result = {}
        for family_id, entries in family_entries.items():
            steps_dict = {}
            for step, computed in entries:
                consumer_names = []
                for other, _ in entries:
                    if other["step_id"] == step["step_id"]:
                        continue
                    other_inputs = []
                    if other["input_1"]:
                        other_inputs.append(other["input_1"]["name"])
                    other_inputs.extend(i["name"] for i in other["input_2"])
                    if step["output"] in other_inputs:
                        consumer_names.append(other["step_id"])

                computed = dict(computed)
                computed["feeds_into"] = consumer_names
                steps_dict[step["step_id"]] = computed

            result[family_id] = {
                "label": self._family_label(family_id),
                "steps": steps_dict,
            }

        result["_meta"] = {
            "constants": {
                "GE_TAX": GE_TAX,
                "ZAHUR_FEE": ZAHUR_FEE,
                "WESLEY_FEE": WESLEY_FEE,
                "ALC_AMUL_CHANCE": ALC_AMUL_CHANCE,
                "CHEM_AMU_CHANCE": CHEM_AMU_CHANCE,
                "PRES_GOGGLES_CHANCE": PRES_GOGGLES_CHANCE,
            },
            "timeframes": TIMEFRAMES,
        }

        return result

    def to_json(self) -> dict:
        return self.compute()

    def display(self) -> str:
        from flask import render_template

        try:
            data = self.compute()
            return render_template("osrs/herblore.html", herblore_data_json=json.dumps(data))
        except Exception as e:
            return render_template("osrs/herblore.html", error=str(e), herblore_data_json="null")


if __name__ == "__main__":
    calc = HerbloreStepCalc()
    print(json.dumps(calc.compute(), indent=2))
