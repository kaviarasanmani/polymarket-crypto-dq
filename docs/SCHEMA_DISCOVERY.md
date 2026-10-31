# Automated Schema Discovery Report: `btc_markets.parquet`

- **Total Rows**: 10
- **Evaluated Sample**: 10
- **Columns Detected**: 10
- **File Size**: 0.00 MB

## Column Profiles

| Column | Physical Type | Logical Type | Nullable | Null % | Distinct | Min | Max |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`condition_id`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`market_start`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:25:00+00:00 | 2026-10-31 00:10:00+00:00 |
| **`market_end`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:30:00+00:00 | 2026-10-31 00:15:00+00:00 |
| **`recorded_at`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:30:02+00:00 | 2026-10-31 00:15:02+00:00 |
| **`token_up`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`token_down`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`volume`** | `Float64` | `float` | ✅ No | 0.0% | 10 | 16714.6200 | 132170.5700 |
| **`liquidity`** | `Float64` | `float` | ✅ No | 0.0% | 10 | 22255.2700 | 469411.7000 |
| **`outcome`** | `String` | `string` | ✅ No | 0.0% | 2 | N/A | N/A |
| **`n_ticks`** | `Int64` | `integer` | ✅ No | 0.0% | 1 | 50.0000 | 50.0000 |

---

# Automated Schema Discovery Report: `btc_ticks.parquet`

- **Total Rows**: 500
- **Evaluated Sample**: 500
- **Columns Detected**: 13
- **File Size**: 0.03 MB

## Column Profiles

| Column | Physical Type | Logical Type | Nullable | Null % | Distinct | Min | Max |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`condition_id`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`t`** | `Int64` | `integer` | ✅ No | 0.0% | 500 | 1793402700.0000 | 1793405449.0000 |
| **`ts_utc`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 500 | 2026-10-30 23:25:00+00:00 | 2026-10-31 00:10:49+00:00 |
| **`bu`** | `Float64` | `float` | ✅ No | 0.0% | 453 | 0.2790 | 0.6553 |
| **`au`** | `Float64` | `float` | ✅ No | 0.0% | 450 | 0.3019 | 0.6704 |
| **`bd`** | `Float64` | `float` | ✅ No | 0.0% | 462 | 0.3275 | 0.7037 |
| **`ad`** | `Float64` | `float` | ✅ No | 0.0% | 450 | 0.3498 | 0.7195 |
| **`su`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 125.4600 | 4998.0200 |
| **`sd`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 107.6700 | 4999.8900 |
| **`sau`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 103.3500 | 4996.6300 |
| **`sad`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 115.9000 | 4998.0700 |
| **`du`** | `Float64` | `float` | ✅ No | 0.0% | 499 | 55.9100 | 4629.2100 |
| **`dd`** | `Float64` | `float` | ✅ No | 0.0% | 499 | 75.4100 | 5095.0000 |

---

# Automated Schema Discovery Report: `eth_markets.parquet`

- **Total Rows**: 10
- **Evaluated Sample**: 10
- **Columns Detected**: 10
- **File Size**: 0.00 MB

## Column Profiles

| Column | Physical Type | Logical Type | Nullable | Null % | Distinct | Min | Max |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`condition_id`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`market_start`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:25:00+00:00 | 2026-10-31 00:10:00+00:00 |
| **`market_end`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:30:00+00:00 | 2026-10-31 00:15:00+00:00 |
| **`recorded_at`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 10 | 2026-10-30 23:30:02+00:00 | 2026-10-31 00:15:02+00:00 |
| **`token_up`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`token_down`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`volume`** | `Float64` | `float` | ✅ No | 0.0% | 10 | 5318.5600 | 125202.3300 |
| **`liquidity`** | `Float64` | `float` | ✅ No | 0.0% | 10 | 78781.6400 | 491953.7600 |
| **`outcome`** | `String` | `string` | ✅ No | 0.0% | 2 | N/A | N/A |
| **`n_ticks`** | `Int64` | `integer` | ✅ No | 0.0% | 1 | 50.0000 | 50.0000 |

---

# Automated Schema Discovery Report: `eth_ticks.parquet`

- **Total Rows**: 500
- **Evaluated Sample**: 500
- **Columns Detected**: 13
- **File Size**: 0.03 MB

## Column Profiles

| Column | Physical Type | Logical Type | Nullable | Null % | Distinct | Min | Max |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`condition_id`** | `String` | `string` | ✅ No | 0.0% | 10 | N/A | N/A |
| **`t`** | `Int64` | `integer` | ✅ No | 0.0% | 500 | 1793402700.0000 | 1793405449.0000 |
| **`ts_utc`** | `Datetime(time_unit='us', time_zone='UTC')` | `timestamp` | ✅ No | 0.0% | 500 | 2026-10-30 23:25:00+00:00 | 2026-10-31 00:10:49+00:00 |
| **`bu`** | `Float64` | `float` | ✅ No | 0.0% | 438 | 0.3076 | 0.6367 |
| **`au`** | `Float64` | `float` | ✅ No | 0.0% | 443 | 0.3324 | 0.6564 |
| **`bd`** | `Float64` | `float` | ✅ No | 0.0% | 450 | 0.3415 | 0.6713 |
| **`ad`** | `Float64` | `float` | ✅ No | 0.0% | 444 | 0.3633 | 0.6885 |
| **`su`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 116.2100 | 4994.8600 |
| **`sd`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 106.6800 | 4987.5300 |
| **`sau`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 100.9600 | 4999.7600 |
| **`sad`** | `Float64` | `float` | ✅ No | 0.0% | 499 | 115.0700 | 4996.3800 |
| **`du`** | `Float64` | `float` | ✅ No | 0.0% | 500 | 84.6000 | 4452.8500 |
| **`dd`** | `Float64` | `float` | ✅ No | 0.0% | 499 | 85.5500 | 4836.5200 |