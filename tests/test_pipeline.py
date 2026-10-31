"""End-to-end integration tests for Bronze, Silver, and Gold pipelines."""
from __future__ import annotations

import polars as pl
import pytest
from src.ingestion.downloader import DatasetManager
from src.observability.metrics_tracker import ObservabilityTracker
from src.pipeline.bronze_layer import BronzePipeline
from src.pipeline.gold_layer import GoldAnalyticsPipeline
from src.pipeline.silver_layer import SilverPipeline


def test_full_pipeline_execution(tmp_path):
    raw_dir = tmp_path / "raw"
    bronze_dir = tmp_path / "bronze"
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    db_file = tmp_path / "runs.db"
    duckdb_file = gold_dir / "test_analytics.duckdb"

    # 1. Generate small synthetic benchmark
    mgr = DatasetManager(raw_dir=raw_dir)
    m_files, t_files = mgr.generate_synthetic_benchmark(
        coins=["BTC"],
        windows_per_coin=2,
        ticks_per_window=10,
    )
    assert len(m_files) == 1
    assert len(t_files) == 1

    tracker = ObservabilityTracker(store_path=db_file, reports_dir=tmp_path / "reports")

    # 2. Bronze
    bronze = BronzePipeline(raw_dir=raw_dir, bronze_dir=bronze_dir, tracker=tracker)
    b_res = bronze.run_all(["BTC"])
    assert len(b_res["markets"]) == 1
    assert b_res["markets"][0]["quality_score"] >= 90.0

    # 3. Silver
    silver = SilverPipeline(bronze_dir=bronze_dir, silver_dir=silver_dir, tracker=tracker)
    s_res = silver.run_all(["BTC"])
    assert len(s_res["markets"]) == 1
    assert s_res["markets"][0]["contract_passed"] is True
    assert s_res["ticks"][0]["contract_passed"] is True

    # 4. Gold
    gold = GoldAnalyticsPipeline(
        silver_dir=silver_dir,
        gold_dir=gold_dir,
        duckdb_path=duckdb_file,
        tracker=tracker,
    )
    g_res = gold.build_analytics_models(export_html=False)
    assert g_res["gold_market_summary_rows"] >= 2
    assert g_res["summary_quality_score"] >= 95.0
