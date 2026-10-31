"""Silver Layer Data Cleaning, Microstructure Feature Engineering & Data Contract Validation.

Deduplicates raw events, computes order-book metrics (spreads, mid-prices, imbalance, arbitrage bounds),
and enforces version-controlled ValidateX Data Contracts and domain business rules.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl
import validatex as vx

from ..observability.metrics_tracker import ObservabilityTracker
from ..validation.silver_rules import build_silver_business_suite, load_markets_contract, load_ticks_contract


class SilverPipeline:
    """Cleanses Bronze data, computes order-book metrics, and enforces ValidateX Data Contracts."""

    def __init__(
        self,
        bronze_dir: str | Path = "data/bronze",
        silver_dir: str | Path = "data/silver",
        tracker: Optional[ObservabilityTracker] = None,
    ):
        self.bronze_dir = Path(bronze_dir)
        self.silver_dir = Path(silver_dir)
        self.silver_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = tracker or ObservabilityTracker()

        self.markets_contract = load_markets_contract()
        self.ticks_contract = load_ticks_contract()

    def clean_and_validate_markets(
        self,
        coin: str,
        export_html: bool = True,
    ) -> Dict[str, Any]:
        """Cleanses and validates Bronze markets data against the markets Data Contract."""
        coin_lower = coin.lower()
        bronze_file = self.bronze_dir / "markets" / f"coin={coin.upper()}" / f"{coin_lower}_markets_bronze.parquet"
        if not bronze_file.exists():
            raise FileNotFoundError(f"Bronze markets file missing: {bronze_file}")

        df = pl.read_parquet(bronze_file)
        initial_count = len(df)

        # 1. Deduplication on primary key `condition_id`
        df_clean = df.unique(subset=["condition_id"], keep="first")

        # 2. Invalidate negative volume or liquidity anomalies by clamping to 0.0
        df_clean = df_clean.with_columns([
            pl.when(pl.col("volume") < 0.0).then(0.0).otherwise(pl.col("volume")).alias("volume"),
            pl.when(pl.col("liquidity") < 0.0).then(0.0).otherwise(pl.col("liquidity")).alias("liquidity"),
            pl.lit(datetime.now(timezone.utc)).alias("silver_processed_at"),
        ])

        # 3. ValidateX Data Contract Validation
        contract_res = vx.validate_contract(df_clean, self.markets_contract, engine="polars")

        # Failures by owner routing check
        failures_by_owner = contract_res.failures_by_owner()

        html_name = f"silver_markets_{coin_lower}_contract_report.html" if export_html else None
        metrics = self.tracker.record_validation(
            result=contract_res,
            dataset_name=f"silver_markets_{coin_lower}",
            stage="silver",
            coin=coin,
            html_report_filename=html_name,
        )

        # Write partitioned Silver Parquet
        dest_dir = self.silver_dir / "markets" / f"coin={coin.upper()}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_file = dest_dir / f"{coin_lower}_markets_silver.parquet"
        df_clean.write_parquet(out_file)

        metrics["output_file"] = str(out_file)
        metrics["initial_count"] = initial_count
        metrics["cleansed_count"] = len(df_clean)
        metrics["contract_passed"] = contract_res.success
        metrics["owner_failures"] = {k: len(v) for k, v in failures_by_owner.items()}
        return metrics

    def clean_and_validate_ticks(
        self,
        coin: str,
        export_html: bool = True,
    ) -> Dict[str, Any]:
        """Cleanses ticks, computes order book features, and validates Data Contract & business rules."""
        coin_lower = coin.lower()
        bronze_file = self.bronze_dir / "ticks" / f"coin={coin.upper()}" / f"{coin_lower}_ticks_bronze.parquet"
        if not bronze_file.exists():
            raise FileNotFoundError(f"Bronze ticks file missing: {bronze_file}")

        df = pl.read_parquet(bronze_file)
        initial_count = len(df)

        # 1. Deduplicate by condition_id + timestamp
        df_clean = df.unique(subset=["condition_id", "t"], keep="first").sort(["condition_id", "t"])

        # 2. Derive prediction-market microstructure metrics
        # - Spreads: au - bu and ad - bd
        # - Mid-market price: (bu + au) / 2
        # - Order book imbalance: (su - sau) / (su + sau + 1e-6)
        # - Arbitrage cost: bu + bd
        df_features = df_clean.with_columns([
            (pl.col("au") - pl.col("bu")).round(4).alias("spread_up"),
            (pl.col("ad") - pl.col("bd")).round(4).alias("spread_down"),
            ((pl.col("au") + pl.col("bu")) / 2.0).round(4).alias("mid_up"),
            ((pl.col("ad") + pl.col("bd")) / 2.0).round(4).alias("mid_down"),
            (pl.col("bu") + pl.col("bd")).round(4).alias("arb_bid_sum"),
            ((pl.col("su") - pl.col("sau")) / (pl.col("su") + pl.col("sau") + 1e-6)).round(4).alias("imbalance"),
            pl.lit(datetime.now(timezone.utc)).alias("silver_processed_at"),
        ])

        # 3. ValidateX Data Contract Validation
        contract_res = vx.validate_contract(df_features, self.ticks_contract, engine="polars")

        # 4. Domain Business Suite Validation
        biz_suite = build_silver_business_suite()
        biz_res = vx.validate(df_features, biz_suite, engine="polars")

        html_name = f"silver_ticks_{coin_lower}_report.html" if export_html else None
        metrics = self.tracker.record_validation(
            result=contract_res,
            dataset_name=f"silver_ticks_{coin_lower}",
            stage="silver",
            coin=coin,
            html_report_filename=html_name,
        )

        dest_dir = self.silver_dir / "ticks" / f"coin={coin.upper()}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_file = dest_dir / f"{coin_lower}_ticks_silver.parquet"
        df_features.write_parquet(out_file)

        metrics["output_file"] = str(out_file)
        metrics["initial_count"] = initial_count
        metrics["cleansed_count"] = len(df_features)
        metrics["contract_passed"] = contract_res.success
        metrics["business_score"] = biz_res.quality_score
        return metrics

    def run_all(self, coins: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Runs Silver cleansing and contract validation across coins."""
        results = {"markets": [], "ticks": []}
        for c in coins:
            try:
                m_res = self.clean_and_validate_markets(c)
                results["markets"].append(m_res)
                print(f"[SILVER] Markets {c}: Contract Passed={m_res['contract_passed']}, Score={m_res['quality_score']:.1f}")
            except Exception as e:
                print(f"[SILVER ERROR] Markets {c}: {e}")

            try:
                t_res = self.clean_and_validate_ticks(c)
                results["ticks"].append(t_res)
                print(f"[SILVER] Ticks {c}: Contract Passed={t_res['contract_passed']}, BizScore={t_res.get('business_score', 0):.1f}")
            except Exception as e:
                print(f"[SILVER ERROR] Ticks {c}: {e}")
        return results
