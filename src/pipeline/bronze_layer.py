"""Bronze Layer Ingestion & Structural Quality Validation Pipeline.

Reads raw Parquet/CSV files, injects ingestion audit metadata,
validates structural contracts using ValidateX, and writes partitioned Bronze data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl
import validatex as vx

from ..observability.metrics_tracker import ObservabilityTracker
from ..validation.bronze_rules import build_bronze_markets_suite, build_bronze_ticks_suite


class BronzePipeline:
    """Manages raw ingestion into Bronze Parquet with ValidateX quality gating."""

    def __init__(
        self,
        raw_dir: str | Path = "data/raw",
        bronze_dir: str | Path = "data/bronze",
        tracker: Optional[ObservabilityTracker] = None,
    ):
        self.raw_dir = Path(raw_dir)
        self.bronze_dir = Path(bronze_dir)
        self.bronze_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = tracker or ObservabilityTracker()

    def process_coin_markets(
        self,
        coin: str,
        export_html: bool = True,
    ) -> Dict[str, Any]:
        """Ingests and validates raw markets data for a given cryptocurrency."""
        coin_lower = coin.lower()
        candidates = [
            self.raw_dir / f"{coin_lower}_markets.parquet",
            self.raw_dir / f"{coin.upper()}_markets.parquet",
            self.raw_dir / f"{coin_lower}_markets.csv",
        ]
        src_file = next((f for f in candidates if f.exists()), None)
        if not src_file:
            raise FileNotFoundError(f"Raw markets file not found for coin '{coin}' in {self.raw_dir}")

        # Ingest with Polars
        if src_file.suffix == ".parquet":
            df = pl.read_parquet(src_file)
        else:
            df = pl.read_csv(src_file)

        # Audit columns
        now_utc = datetime.now(timezone.utc)
        df_bronze = df.with_columns([
            pl.lit(coin.upper()).alias("coin_symbol"),
            pl.lit(now_utc).alias("bronze_ingested_at"),
            pl.lit(src_file.name).alias("source_filename"),
        ])

        # ValidateX Bronze Structural Validation
        suite = build_bronze_markets_suite()
        result = vx.validate(df_bronze, suite, engine="polars")

        # Record in Observability RunStore
        html_name = f"bronze_markets_{coin_lower}_report.html" if export_html else None
        metrics = self.tracker.record_validation(
            result=result,
            dataset_name=f"bronze_markets_{coin_lower}",
            stage="bronze",
            coin=coin,
            html_report_filename=html_name,
        )

        # Write partitioned Bronze Parquet
        dest_dir = self.bronze_dir / "markets" / f"coin={coin.upper()}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_file = dest_dir / f"{coin_lower}_markets_bronze.parquet"
        df_bronze.write_parquet(out_file)

        metrics["output_file"] = str(out_file)
        metrics["row_count"] = len(df_bronze)
        return metrics

    def process_coin_ticks(
        self,
        coin: str,
        export_html: bool = True,
        max_rows: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ingests and validates raw 1Hz ticks order-book data for a given cryptocurrency."""
        coin_lower = coin.lower()
        candidates = [
            self.raw_dir / f"{coin_lower}_ticks.parquet",
            self.raw_dir / f"{coin.upper()}_ticks.parquet",
            self.raw_dir / f"{coin_lower}_ticks.csv",
        ]
        src_file = next((f for f in candidates if f.exists()), None)
        if not src_file:
            raise FileNotFoundError(f"Raw ticks file not found for coin '{coin}' in {self.raw_dir}")

        # Ingest with Polars
        if src_file.suffix == ".parquet":
            scan = pl.scan_parquet(src_file)
        else:
            scan = pl.scan_csv(src_file)

        if max_rows:
            scan = scan.limit(max_rows)
        df = scan.collect()

        now_utc = datetime.now(timezone.utc)
        df_bronze = df.with_columns([
            pl.lit(coin.upper()).alias("coin_symbol"),
            pl.lit(now_utc).alias("bronze_ingested_at"),
            pl.lit(src_file.name).alias("source_filename"),
        ])

        # ValidateX Bronze Structural Validation
        suite = build_bronze_ticks_suite()
        result = vx.validate(df_bronze, suite, engine="polars")

        html_name = f"bronze_ticks_{coin_lower}_report.html" if export_html else None
        metrics = self.tracker.record_validation(
            result=result,
            dataset_name=f"bronze_ticks_{coin_lower}",
            stage="bronze",
            coin=coin,
            html_report_filename=html_name,
        )

        dest_dir = self.bronze_dir / "ticks" / f"coin={coin.upper()}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_file = dest_dir / f"{coin_lower}_ticks_bronze.parquet"
        df_bronze.write_parquet(out_file)

        metrics["output_file"] = str(out_file)
        metrics["row_count"] = len(df_bronze)
        return metrics

    def run_all(self, coins: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Runs Bronze ingestion across a list of target cryptocurrencies."""
        results = {"markets": [], "ticks": []}
        for c in coins:
            try:
                m_res = self.process_coin_markets(c)
                results["markets"].append(m_res)
                print(f"[BRONZE] Markets {c}: Score={m_res['quality_score']:.1f}/100, Rows={m_res['row_count']}")
            except Exception as e:
                print(f"[BRONZE ERROR] Markets {c}: {e}")

            try:
                t_res = self.process_coin_ticks(c)
                results["ticks"].append(t_res)
                print(f"[BRONZE] Ticks {c}: Score={t_res['quality_score']:.1f}/100, Rows={t_res['row_count']}")
            except Exception as e:
                print(f"[BRONZE ERROR] Ticks {c}: {e}")
        return results
