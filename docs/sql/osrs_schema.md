# Database Map: `osrs`

*Generated: 2026-06-11 14:28*  
*This file is auto-generated. Annotation fields marked `<!-- -->` are for manual edits and will be preserved during `--update` runs.*

---

## Schema: `items`

> **Notes:** <!-- Schema-level notes, purpose, team ownership -->

### Table: `map`

> **Status:** <!-- active | legacy | deprecated -->  
> **Role:** <!-- Describe what this table is used for -->  
> **Rows (est.):** ~4,525  
> **Notes:** <!-- Any additional notes -->  

| Column | Type | Nullable | Default | Flags | Notes |
|--------|------|----------|---------|-------|-------|
| `id` | integer | NO |  | PK | <!-- notes --> |
| `examine` | text | YES |  |  | <!-- notes --> |
| `lowalch` | integer | YES |  |  | <!-- notes --> |
| `limit` | integer | YES |  |  | <!-- notes --> |
| `value` | integer | YES |  |  | <!-- notes --> |
| `highalch` | integer | YES |  |  | <!-- notes --> |
| `icon` | text | YES |  |  | <!-- notes --> |
| `name` | text | YES |  |  | <!-- notes --> |
| `members` | boolean | YES |  |  | <!-- notes --> |

---

## Schema: `prices`

> **Notes:** <!-- Schema-level notes, purpose, team ownership -->

### Table: `10000_1h`

> **Status:** <!-- active | legacy | deprecated -->  
> **Role:** <!-- Describe what this table is used for -->  
> **Rows (est.):** ~3,703  
> **Notes:** <!-- Any additional notes -->  

| Column | Type | Nullable | Default | Flags | Notes |
|--------|------|----------|---------|-------|-------|
| `timestamp` | timestamp without time zone | NO |  | PK | <!-- notes --> |
| `avgHighPrice` | integer | YES |  |  | <!-- notes --> |
| `highPriceVolume` | integer | YES |  |  | <!-- notes --> |
| `avgLowPrice` | integer | YES |  |  | <!-- notes --> |
| `lowPriceVolume` | integer | YES |  |  | <!-- notes --> |

---

### Table: `10000_5min`

> **Status:** <!-- active | legacy | deprecated -->  
> **Role:** <!-- Describe what this table is used for -->  
> **Rows (est.):** ~6,963  
> **Notes:** <!-- Any additional notes -->  

| Column | Type | Nullable | Default | Flags | Notes |
|--------|------|----------|---------|-------|-------|
| `timestamp` | timestamp without time zone | NO |  | PK | <!-- notes --> |
| `avgHighPrice` | integer | YES |  |  | <!-- notes --> |
| `highPriceVolume` | integer | YES |  |  | <!-- notes --> |
| `avgLowPrice` | integer | YES |  |  | <!-- notes --> |
| `lowPriceVolume` | integer | YES |  |  | <!-- notes --> |

---

### Table: `10000_latest`

> **Status:** <!-- active | legacy | deprecated -->  
> **Role:** <!-- Describe what this table is used for -->  
> **Rows (est.):** ~288,126  
> **Notes:** <!-- Any additional notes -->  

| Column | Type | Nullable | Default | Flags | Notes |
|--------|------|----------|---------|-------|-------|
| `timestamp` | timestamp without time zone | NO |  | PK | <!-- notes --> |
| `high` | integer | YES |  |  | <!-- notes --> |
| `highTime` | integer | YES |  |  | <!-- notes --> |
| `low` | integer | YES |  |  | <!-- notes --> |
| `lowTime` | integer | YES |  |  | <!-- notes --> |

---

### Table: `10002_1h`

> **Status:** <!-- active | legacy | deprecated -->  
> **Role:** <!-- Describe what this table is used for -->  
> **Rows (est.):** ~2,260  
> **Notes:** <!-- Any additional notes -->  

| Column | Type | Nullable | Default | Flags | Notes |
|--------|------|----------|---------|-------|-------|
| `timestamp` | timestamp without time zone | NO |  | PK | <!-- notes --> |
| `avgHighPrice` | integer | YES |  |  | <!-- notes --> |
| `highPriceVolume` | integer | YES |  |  | <!-- notes --> |
| `avgLowPrice` | integer | YES |  |  | <!-- notes --> |
| `lowPriceVolume` | integer | YES |  |  | <!-- notes --> |
