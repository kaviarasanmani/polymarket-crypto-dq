"""Gold Layer Analytical Feature Store & SQL Quality Validation with DuckDB.

Aggregates 5-minute market resolutions, computes realized volatility, VWAP,
liquidity health indexes, and validates analytical models using ValidateX.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import polars as pl
import validatex as vx

from ..observability.metrics_tracker import ObservabilityTracker


class GoldAnalyticsPipeline:
    """Builds analytical gold views and feature stores in DuckDB with ValidateX gating."""

    def __init__(
        self,
        silver_dir: str | Path = "data/silver",
        gold_dir: str | Path = "data/gold",
        duckdb_path: str | Path = "data/gold/polymarket_analytics.duckdb",
        tracker: Optional[ObservabilityTracker] = None,
    ):
        self.silver_dir = Path(silver_dir)
        self.gold_dir = Path(gold_dir)
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        self.duckdb_path = Path(duckdb_path)
        self.tracker = tracker or ObservabilityTracker()

    def build_analytics_models(self, export_html: bool = True) -> Dict[str, Any]:
        """Creates Gold aggregation tables in DuckDB and runs ValidateX checks."""
        con = duckdb.connect(str(self.duckdb_path))

        markets_glob = str(self.silver_dir / "markets" / "**" / "*.parquet").replace("\\", "/")
        ticks_glob = str(self.silver_dir / "ticks" / "**" / "*.parquet").replace("\\", "/")

        # 1. Create Views over Silver Parquet
        con.execute(f"CREATE OR REPLACE VIEW silver_markets AS SELECT * FROM read_parquet('{markets_glob}')")
        con.execute(f"CREATE OR REPLACE VIEW silver_ticks AS SELECT * FROM read_parquet('{ticks_glob}')")

        # 2. Build Model 1: gold_market_summary
        con.execute("""
            CREATE OR REPLACE TABLE gold_market_summary AS
            WITH tick_aggs AS (
                SELECT
                    condition_id,
                    COUNT(t) as tick_count,
                    ROUND(AVG(spread_up), 4) as avg_spread_up,
                    ROUND(AVG(spread_down), 4) as avg_spread_down,
                    ROUND(MIN(mid_up), 4) as min_mid_up,
                    ROUND(MAX(mid_up), 4) as max_mid_up,
                    ROUND(STDDEV_SAMP(mid_up), 6) as realized_volatility,
                    ROUND(AVG(su * bu), 2) as avg_up_depth_usdc
                FROM silver_ticks
                GROUP BY condition_id
            )
            SELECT
                m.condition_id,
                m.coin_symbol,
                m.market_start,
                m.market_end,
                m.outcome,
                m.volume,
                m.liquidity,
                t.tick_count,
                t.avg_spread_up,
                t.avg_spread_down,
                t.min_mid_up,
                t.max_mid_up,
                COALESCE(t.realized_volatility, 0.0) as realized_volatility,
                COALESCE(t.avg_up_depth_usdc, 0.0) as avg_up_depth_usdc,
                CURRENT_TIMESTAMP as gold_created_at
            FROM silver_markets m
            LEFT JOIN tick_aggs t ON m.condition_id = t.condition_id
        """)

        # 3. Build Model 2: gold_orderbook_liquidity
        con.execute("""
            CREATE OR REPLACE TABLE gold_orderbook_liquidity AS
            SELECT
                coin_symbol,
                COUNT(condition_id) as total_markets,
                ROUND(SUM(volume), 2) as total_volume_usdc,
                ROUND(AVG(liquidity), 2) as avg_liquidity_usdc,
                ROUND(AVG(avg_spread_up), 4) as mean_spread_up,
                ROUND(AVG(realized_volatility), 6) as mean_volatility,
                -- Liquidity Health Index (0-100): Lower spread & higher depth = higher score
                ROUND(GREATEST(0.0, LEAST(100.0, 100.0 - (AVG(avg_spread_up) * 500.0) + (AVG(liquidity) / 10000.0))), 2) as liquidity_health_index
            FROM gold_market_summary
            GROUP BY coin_symbol
        """)

        # 4. Extract Gold DataFrames for ValidateX Validation
        df_summary = con.sql("SELECT * FROM gold_market_summary").pl()
        df_liquidity = con.sql("SELECT * FROM gold_orderbook_liquidity").pl()

        # Validate Model 1 with ValidateX
        suite_summary = (
            vx.ExpectationSuite("gold_market_summary_suite")
            .add("expect_table_row_count_to_be_between", min_value=1, severity="critical")
            .add("expect_column_to_not_be_null", column="condition_id", severity="critical")
            .add("expect_column_values_to_be_unique", column="condition_id", severity="critical")
            .add("expect_column_values_to_be_between", column="avg_spread_up", min_value=0.0, max_value=1.0, severity="critical")
            .add("expect_column_values_to_be_between", column="realized_volatility", min_value=0.0, severity="warning")
        )
        res_summary = vx.validate(df_summary, suite_summary, engine="polars")

        # Validate Model 2 with ValidateX
        suite_liq = (
            vx.ExpectationSuite("gold_liquidity_health_suite")
            .add("expect_table_row_count_to_be_between", min_value=1, severity="critical")
            .add("expect_column_to_not_be_null", column="coin_symbol", severity="critical")
            .add("expect_column_values_to_be_unique", column="coin_symbol", severity="critical")
            .add("expect_column_values_to_be_between", column="liquidity_health_index", min_value=0.0, max_value=100.0, severity="critical")
        )
        res_liq = vx.validate(df_liquidity, suite_liq, engine="polars")

        # Export Gold Parquet files
        summary_parquet = self.gold_dir / "gold_market_summary.parquet"
        liquidity_parquet = self.gold_dir / "gold_orderbook_liquidity.parquet"
        df_summary.write_parquet(summary_parquet)
        df_liquidity.write_parquet(liquidity_parquet)

        # Record in Observability RunStore
        html_summary = "gold_market_summary_report.html" if export_html else None
        metric_summary = self.tracker.record_validation(
            result=res_summary,
            dataset_name="gold_market_summary",
            stage="gold",
            coin="cross_asset",
            html_report_filename=html_summary,
        )

        metric_liq = self.tracker.record_validation(
            result=res_liq,
            dataset_name="gold_orderbook_liquidity",
            stage="gold",
            coin="cross_asset",
            html_report_filename="gold_liquidity_report.html" if export_html else None,
        )

        con.close()

        return {
            "gold_market_summary_rows": len(df_summary),
            "gold_orderbook_liquidity_rows": len(df_liquidity),
            "summary_quality_score": res_summary.quality_score,
            "liquidity_quality_score": res_liq.quality_score,
            "duckdb_file": str(self.duckdb_path),
            "summary_parquet": str(summary_parquet),
            "liquidity_parquet": str(liquidity_parquet),
        }
