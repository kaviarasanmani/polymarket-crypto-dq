"""Tests for ValidateX RunStore and observability metrics."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import polars as pl
import pytest
import validatex as vx
from src.observability.metrics_tracker import ObservabilityTracker


def test_observability_recording_and_trend(tmp_path):
    db_file = tmp_path / "test_runs.db"
    tracker = ObservabilityTracker(store_path=db_file, reports_dir=tmp_path / "reports")

    # Create dummy validation
    df = pl.DataFrame({"id": [1, 2, 3], "val": [10.0, 20.0, 30.0]})
    suite = (
        vx.ExpectationSuite("test_suite")
        .add("expect_column_to_not_be_null", column="id")
        .add("expect_column_values_to_be_between", column="val", min_value=0.0)
    )

    res = vx.validate(df, suite, engine="polars")
    record = tracker.record_validation(res, dataset_name="test_dataset", stage="bronze")
    assert record["quality_score"] == 100.0

    trend = tracker.get_quality_trend("test_dataset")
    assert trend["dataset_name"] == "test_dataset"
    assert trend["latest"] == 100.0
    assert len(trend["scores"]) == 1


def test_freshness_check():
    tracker = ObservabilityTracker()
    now = datetime.now(timezone.utc)
    df = pl.DataFrame({
        "ts": [now - timedelta(hours=2), now - timedelta(hours=1)]
    })
    freshness = tracker.check_dataset_freshness(df, timestamp_column="ts", max_age_hours=24.0)
    assert freshness["is_fresh"] is True
    assert freshness["age_hours"] < 2.0
