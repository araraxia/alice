# Herblore CSV Tool — Planning Document

## Overview

A Python script (`src/osrs/calcs/herblore_calc.py` or similar) ingests a CSV of herblore
combination steps, looks up live GE prices for each named item, and outputs profit/loss and
XP/cost data. This feeds a new website tool that lets users toggle NPC services and equipment
to see how those choices affect each step's economics.

**Reference implementations:**
- `src/osrs/calcs/herblore_potion_calc.py` — existing per-potion calc class
- `showcase_content/topics/prayerregen-goading.md` — design doc for existing tool

---

## Existing `.env_public` Constants (confirmed)

```
GE_TAX              = 0.02       # 2% Grand Exchange sales tax
ZAHUR_FEE           = 200        # gp per herb cleaning OR unfinished potion creation
WESLEY_FEE          = 50         # gp per item Wesley processes
ALC_AMUL_CHANCE     = 0.15       # Alchemist's Amulet: 15% chance for +1 dose
CHEM_AMU_CHANCE     = 0.10       # Amulet of Chemistry: 10% chance for +1 dose
PRES_GOGGLES_CHANCE = 0.1111     # Prescription Goggles: ~1/9 chance to save secondary
```

**No new constants needed** — all values are already present.

---

## CSV Schema

Each row represents one combination step (herb + secondary → product, grimy → clean, etc.).
Steps are intentionally flat and non-linear — there is no required ordering or chaining in the
CSV itself.

### Required Columns

| Column | Type | Description |
|---|---|---|
| `step_id` | string | Unique identifier, e.g. `"goading_make_unf"`. Used for linking on the website. |
| `potion_family` | string (pipe-separated) | One or more family IDs this step belongs to, e.g. `"goading_potion"` or `"goading_potion\|prayer_regen_potion"`. A step listed in multiple families appears in each family's display card. Pipe `\|` used as delimiter to avoid conflicting with CSV commas. |
| `step_label` | string | Human-readable label shown in the UI, e.g. `"Make unfinished (Zahur)"`. |
| `input_1` | string | GE item name of the primary input. Optional quantity prefix: `"2x Harralander"` means 2 of that item are consumed per step. Defaults to 1 if no prefix. |
| `input_2` | string (pipe-separated) | One or more secondary inputs, each optionally quantity-prefixed. e.g. `"Aldarium"` or `"2x Vial of water\|Snape grass"`. All listed items are consumed per combination. Blank if none. |
| `output` | string | Exact GE item name of the output for baseline case (no amulet proc), e.g. `"Goading potion(3)"`. |
| `output_extra_dose` | string | GE item name produced on an amulet proc (e.g. `"Goading potion(4)"`). Blank if amulets don't apply to this step or if output is not a dosage potion. |
| `output_doses` | int | Doses in the baseline output (e.g. `3`). Used for price-per-dose math. Leave blank for non-potion outputs. |
| `xp` | float | XP gained per combination (e.g. `80.0`). Zero for non-XP steps (e.g. grimy cleaning). |
| `level_req` | int | Herblore level required to perform this step (e.g. `72`). Used for display only — shown in the UI step table alongside the step label. |

### Optional Boolean Columns

These control which NPC/equipment options are available **for this step**. The website renders
toggles only for columns that have at least one `true` row in the loaded data.

| Column | Description |
|---|---|
| `zahur_clean` | Zahur can clean `input_1` (grimy → clean, costs `ZAHUR_FEE`). |
| `zahur_unf` | Zahur can make unfinished potion from `input_1` (costs `ZAHUR_FEE`). The Vial of Water must be listed explicitly in `input_2`. |
| `wesley` | Wesley can process `input_2` (costs `WESLEY_FEE`). |
| `dose_amulet` | Either dose-bonus amulet (Alchemist's or Chemistry) applies to this step. Both share the same AoC charge cost model. The user selects which one to equip in the UI; only one applies at a time. |
| `goggles` | Prescription Goggles apply to this step (`PRES_GOGGLES_CHANCE` secondary save). |

### Example CSV

```csv
step_id,potion_family,step_label,input_1,input_2,output,output_extra_dose,output_doses,xp,level_req,zahur_clean,zahur_unf,wesley,dose_amulet,goggles
harralander_clean,goading_potion|harralander_potion,Clean grimy herb,Grimy harralander,,Harralander,,,0,1,true,false,false,false,false
harralander_make_unf,goading_potion|harralander_potion,Make unfinished,Harralander,Vial of water,Harralander potion (unf),,,0,1,false,true,false,false,false
goading_combine,goading_potion,Combine,Harralander potion (unf),Aldarium,Goading potion(3),Goading potion(4),3,80,72,false,false,false,true,true
pregen_combine,prayer_regen_potion,Combine,Huasca potion (unf),Aldarium,Prayer regeneration potion(3),Prayer regeneration potion(4),3,87.5,91,false,false,false,true,true
example_multi_secondary,some_potion,Combine,2x Some herb,2x Ingredient A|Ingredient B,Some potion(3),,3,60,50,false,false,false,false,false
```

---

## Pricing Logic

### Item Price Lookup

The script uses `osrsItemProperties` (existing class) to look up prices by item ID. Since the
CSV stores item **names**, the script needs a name→ID resolver. Options:

- Query `items.map` in the `osrs` DB (already has name→ID mapping)
- Fall back to fuzzy search via `item_search.py` if exact match fails

**Untradable / unlisted items:** if an item name cannot be resolved to a DB entry, or resolves
but has no GE price data (e.g. untradable quest items, NPC-only rewards), all price values for
that item are treated as `0`. This allows steps involving untradable inputs or outputs to still
produce valid cost/profit figures — the untradable item simply contributes nothing to the
monetary calculation. The script should log a warning for any item that falls back to 0 so
discrepancies are visible without halting execution.

### Selling Assumption

Revenue calculation depends on whether `output_doses` is populated:

#### Case A — Dosage potion (`output_doses` is set)

All finished potions are sold at their **4-dose equivalent price**, regardless of what dose
count was actually produced:

```
price_per_dose = price_of_4dose_potion / 4
```

If `output_extra_dose` is set and `output_doses` < 4, the script looks up the 4-dose version's
price directly (e.g. `"Goading potion(4)"` price / 4). If the 4-dose form doesn't trade on the
GE, it falls back to `output_extra_dose` price / doses.

Amulet procs increase expected doses:

```
# Baseline (no amulet)
avg_doses = output_doses

# With Amulet of Chemistry (CHEM_AMU_CHANCE = 0.10)
avg_doses = output_doses + CHEM_AMU_CHANCE        # e.g. 3.10

# With Alchemist's Amulet (ALC_AMUL_CHANCE = 0.15)
avg_doses = output_doses + ALC_AMUL_CHANCE        # e.g. 3.15

revenue = price_per_dose * avg_doses * (1 - GE_TAX)
```

`dose_amulet` and `output_extra_dose` are only meaningful when `output_doses` is set. If
`output_doses` is blank, both should be left blank/false in the CSV.

#### Case B — Non-dose output (`output_doses` is blank)

The output is an intermediate item (cleaned herb, unfinished potion, processed ingredient, etc.).
Two sub-cases:

**B1 — Tradable output** (GE price resolves successfully and is > 0):

```
revenue = output_price * (1 - GE_TAX)
profit  = revenue - cost
```

Revenue and profit are shown in the UI. This covers steps like selling an unfinished potion
directly, or selling a cleaned herb rather than using it.

**B2 — Untradable / unlisted output** (price resolves to 0 per the untradable rule):

```
revenue = 0
profit  = null
```

Revenue and profit columns show `—` in the UI. The cost column is still shown so the user
can see how much this intermediate step contributes to the pipeline.

The script distinguishes B1 from B2 solely by whether the item's resolved price is 0 after
the standard lookup — no extra CSV column is needed.

### Alchemist's Amulet Charge Cost

The Alch Amulet is charged with Amulets of Chemistry (AoC), 10 charges per amulet. Goggles
proc is what consumes an amulet charge — not every combination. So:

```
aoc_cost_per_step = (AoC price / 10) * PRES_GOGGLES_CHANCE   # if goggles=true on this step
                  = (AoC price / 10) * 0                      # if goggles=false
```

This matches the existing `HerblorePotionCalc` charge model.

### Production Cost Per Step

```
cost = input_1_price
     + sum(input_2_prices) * (1 - PRES_GOGGLES_CHANCE)   # if goggles=true, else full price
     + ZAHUR_FEE                                          # if zahur_clean or zahur_unf enabled
     + WESLEY_FEE                                         # if wesley enabled
     + aoc_cost_per_step                                  # if dose_amulet enabled
```

### Output Metrics Per Step

- `cost` — total production cost per combination
- `revenue` — expected revenue (4-dose-equivalent, after GE tax)
- `profit` — `revenue - cost`
- `xp_per_cost` — `xp / cost` (0 if XP is 0 or cost is 0)

---

## Pipeline Aggregation

### Concept

Each CSV row is an atomic step. The `potion_family` tag groups related steps for display. When
a user chains multiple steps together (e.g. grimy → clean → unf → combine), intermediate item
prices cancel — the clean herb's sell price and its cost as an input to the next step are the
same number and net to zero (ignoring GE tax on the intermediate trade, which the user avoids
by processing continuously). The pipeline therefore collapses to:

```
pipeline_cost    = sum of all external GE inputs across selected steps
                   (items whose names do not appear as the `output` of another selected step)
pipeline_revenue = revenue of the final selected step only
pipeline_xp      = sum of xp across all selected steps
pipeline_profit  = pipeline_revenue - pipeline_cost
pipeline_xp_cost = pipeline_xp / pipeline_cost
```

### Intermediate Item Cancellation

The script pre-computes a `feeds_into` field per step: the set of `step_id`s within the same
family whose `input_1` or `input_2` items match this step's `output`. This is resolved by item
name at parse time and written into the JSON output so the client doesn't need to repeat it.

When the client builds a pipeline from a set of selected steps:

1. Collect all input items across selected steps.
2. For each input item, check if it is the `output` of another selected step in the same family.
3. If yes, exclude it from `pipeline_cost` (it is produced internally, not bought).
4. Sum remaining external input costs; use final step's revenue as `pipeline_revenue`.

The "final step" is the selected step whose `output` is not consumed by any other selected step.
If multiple terminal steps are selected (branching pipelines), each branch is treated separately.

### UI Model

Each potion-family card shows an entry-point selector rather than free-form step checkboxes.
The user picks their starting material from a dropdown or radio group:

- **From grimy herb** → steps: clean + make unf + combine
- **From clean herb** → steps: make unf + combine
- **From unfinished potion** → steps: combine only

The UI derives which steps are active from the selected entry point by walking `feeds_into`
links forward from the chosen starting step to the terminal step. This prevents nonsensical
combinations (e.g. selecting combine without making unf) and keeps the UI simple.

A **Pipeline row** is appended below the individual step rows in the table showing the
aggregated cost, revenue, profit, XP, and XP/cost for the active chain. Individual step rows
remain visible above it for reference.

### JSON additions

The `feeds_into` field is added to each step in the output JSON:

```json
"harralander_clean": {
  "label": "Clean grimy herb",
  "feeds_into": ["harralander_make_unf"],
  "timeframes": { ... },
  "available_modifiers": []
}
```

Steps with no downstream consumer within the family have `"feeds_into": []` and are terminal.

---

## Script Design (`herblore_step_calc.py`)

```
herblore_step_calc.py --csv potions.csv [--output results.json]
```

### Steps

1. Load `.env_public` constants
2. Parse CSV → list of step dicts; apply the following field normalisations:
   - `potion_family`: split on `|` → list of family IDs
   - `input_1`: parse optional `Nx` prefix → `{"name": str, "qty": int}` (default qty 1)
   - `input_2`: split on `|`, then parse each token's optional `Nx` prefix → list of `{"name": str, "qty": int}`
   - Regex for quantity prefix: `^(\d+)x\s+(.+)$` — if no match, qty defaults to 1
3. For each step: resolve item names → IDs → fetch prices via `osrsItemProperties`
4. Apply the pricing logic above across all four timeframes (5min, 15min, 1h, 3h)
5. Compute metrics for all modifier combinations:
   - No NPC services, no equipment
   - Per boolean column that is `true` for this step: compute marginal impact
6. Output JSON keyed by `step_id`, grouped by `potion_family`

### Output JSON Structure

```json
{
  "goading_potion": {
    "label": "Goading Potion",
    "steps": {
      "goading_combine": {
        "label": "Combine",
        "timeframes": {
          "5min": {
            "baseline":       { "cost": 1234, "revenue": 1456, "profit": 222, "xp_per_cost": 0.065 },
            "with_goggles":       { "cost": 1100, "revenue": 1456, "profit": 356, "xp_per_cost": 0.073 },
            "with_chem_amulet":   { "cost": 1100, "revenue": 1490, "profit": 390, "xp_per_cost": 0.073 },
            "with_alch_amulet":   { "cost": 1105, "revenue": 1503, "profit": 398, "xp_per_cost": 0.073 }
          },
          "15min": { ... },
          "1h":    { ... },
          "3h":    { ... }
        },
        "available_modifiers": ["goggles", "dose_amulet"]
      }
    }
  }
}
```

---

## Database Storage

The parsed/normalized CSV data (post field-normalisation, see Script Design step 2) is persisted
to the `osrs` database under a new `herblore` schema, so the website tool can read steps without
re-parsing the CSV on every request.

### Schema

- **Database:** `osrs`
- **Schema:** `herblore`
- **Table:** `herblore.action_step`

```sql
CREATE SCHEMA IF NOT EXISTS herblore;

CREATE TABLE IF NOT EXISTS herblore.action_step (
    step_id             VARCHAR(64)  PRIMARY KEY,
    potion_family        TEXT[]       NOT NULL,
    step_label           VARCHAR(128) NOT NULL,
    input_1_item          VARCHAR(128) NOT NULL,
    input_1_qty           INTEGER      NOT NULL DEFAULT 1,
    input_2               JSONB        NOT NULL DEFAULT '[]'::jsonb,
    output                VARCHAR(128) NOT NULL,
    output_extra_dose     VARCHAR(128),
    output_doses          SMALLINT,
    xp                    NUMERIC(6,2) NOT NULL DEFAULT 0,
    level_req             SMALLINT     NOT NULL,
    zahur_clean           BOOLEAN      NOT NULL DEFAULT FALSE,
    zahur_unf             BOOLEAN      NOT NULL DEFAULT FALSE,
    wesley                BOOLEAN      NOT NULL DEFAULT FALSE,
    dose_amulet           BOOLEAN      NOT NULL DEFAULT FALSE,
    goggles                BOOLEAN      NOT NULL DEFAULT FALSE,
    created_datetime       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_datetime       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_herblore_action_step_family
    ON herblore.action_step USING GIN (potion_family);
```

Column notes:

- `potion_family` — Postgres `TEXT[]`, the parsed form of the CSV's pipe-delimited
  `potion_family` column. GIN-indexed so `'goading' = ANY(potion_family)` lookups (building a
  family's step list) are fast.
- `input_1_item` / `input_1_qty` — the parsed `{"name": str, "qty": int}` form of the CSV's
  `input_1` column.
- `input_2` — `JSONB` array of `{"name": str, "qty": int}` objects, the parsed form of the CSV's
  pipe-delimited `input_2` column. Stored as JSONB rather than a second array pair since each
  secondary carries its own qty.
- `output_extra_dose` / `output_doses` — nullable; blank/absent for non-dose outputs and for
  steps where the dosing behaviour isn't yet confirmed (e.g. `make_antivenom_p`,
  `make_super_combat` — see CSV).

### Migration

Table creation lives in `migrations/002_herblore_schema.sql`, following the same convention as
`migrations/001_blog_schema.sql` (idempotent `IF NOT EXISTS`, wrapped in a transaction).

### Ingestion

`herblore_step_calc.py` (or a small companion loader) re-parses `conf/herblore_action_table.csv`
per the Step 2 field normalisations and upserts rows into `herblore.action_step` on `step_id`
conflict, keeping the table in sync with the CSV as the source of truth. Price/XP/cost
calculations still happen at request time against live GE prices — this table only stores the
static recipe data, not computed economics.

---

## Website Tool Design

### URL / Blueprint

New route in `osrs_route`, e.g. `/osrs/herblore` or as a modal from the OSRS tools window.

### UI

A **per-potion-family card** showing a table of steps. At the top of the card (or page):

- **Timeframe selector** — 5min / 15min / 1h / 3h (radio or tab)
- **Equipment toggles** — globally applied where the step supports it:
  - `[ ] Prescription Goggles`
  - `( ) Amulet of Chemistry` / `( ) Alchemist's Amulet` (mutually exclusive radio pair, shown when any step has `dose_amulet=true`)
  - `[ ] Zahur (cleaning)` / `[ ] Zahur (unfinished)` / `[ ] Wesley` (independent checkboxes)

Each toggle is only shown if at least one step in the loaded data has that boolean set to `true`.

### Step Table Columns

Individual step rows always shown. A **Pipeline** row is appended below, aggregating the active
chain selected by the entry-point picker (see Pipeline Aggregation section).

| Step | Lvl | Cost | Revenue | Profit | XP | XP/Cost |
| --- | --- | --- | --- | --- | --- | --- |
| Clean grimy herb | 1 | 450 gp | 480 gp | 30 gp | 0 | — |
| Make unfinished (Zahur) | 1 | 655 gp | 700 gp | 45 gp | 0 | — |
| Combine | 72 | 812 gp | 1,234 gp | 422 gp | 80 | 0.099/gp |
| **Pipeline (from grimy)** | — | **1,650 gp** | **1,234 gp** | **−416 gp** | **80** | **0.048/gp** |

Revenue/Profit for non-dose steps reflect the standalone sell value of the output (Case B1/B2
from Pricing Logic). In the Pipeline row, intermediate revenues are cancelled and only the
terminal step's revenue is used.

Revenue/Profit columns are blank for non-potion-output steps (cleaning, unf creation).

---

## Questions for the User

**Q2 — Wesley's exact role**
What items does Wesley process, and does his processing replace an input ingredient (e.g.
processing `input_2` before it's added), or does it affect a post-combination step? The
WESLEY_FEE is charged per item — confirm this applies to `input_2` unless the CSV design
should allow specifying which input Wesley processes.

**Q5 — Item name resolution**
Item names in OSRS can be inconsistent (e.g., `"Goading potion(3)"` vs `"Goading potion (3)"`).
Should the script require exact matches against `items.map`, use fuzzy search with a confidence
threshold, or should the CSV include item IDs as a second column alongside names for precision?

**Q6 — Potion families across the website**
Should this tool eventually replace or absorb the existing Goading/Prayer Regen calculator
(`/osrs/goading_regens`), or live alongside it as a separate more-generic tool?

**Q7 — Initial CSV content**
What potions/steps should be included in the first version of the CSV? (e.g. just the two
existing goading/prayer-regen families, or a broader set from launch?)
