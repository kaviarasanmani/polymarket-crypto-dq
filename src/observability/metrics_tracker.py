"""Observability tracker managing ValidateX RunStore and analytical health metrics.

Records validation runs across pipeline tiers, generates historical trend analysis,
evaluates volume anomalies and data freshness, and exports standalone HTML reports.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import validatex as vx


class ObservabilityTracker:
    """Encapsulates historical tracking and health alerting with ValidateX."""

    def __init__(
        self,
        store_path: str | Path = "data/observability/runs.db",
        reports_dir: str | Path = "data/observability/reports",
    ):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.store = vx.RunStore(str(self.store_path))

    def record_validation(
        self,
        result: Any,
        dataset_name: str,
        stage: str,
        coin: Optional[str] = None,
        html_report_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Saves a validation run into the RunStore and optionally exports HTML."""
        run_name = f"{stage}_{coin or 'all'}"
        
        val_result = getattr(result, "validation", result)
        row_count = getattr(val_result, "row_count", None) or len(getattr(val_result, "results", []))
        run_id = self.store.log_run(
            val_result,
            dataset_name=dataset_name,
            run_name=run_name,
            row_count=row_count,
        )

        report_path = None
        if html_report_filename:
            report_file = self.reports_dir / html_report_filename
            result.to_html(str(report_file))
            report_path = str(report_file)

        return {
            "run_id": run_id,
            "dataset_name": dataset_name,
            "stage": stage,
            "coin": coin,
            "quality_score": result.quality_score,
            "success": result.success,
            "total_expectations": getattr(val_result, "total_expectations", len(getattr(val_result, "results", []))),
            "passed_expectations": getattr(val_result, "successful_expectations", 0),
            "failed_expectations": getattr(val_result, "failed_expectations", 0),
            "report_path": report_path,
        }

    def get_quality_trend(self, dataset_name: str, limit: int = 30) -> Dict[str, Any]:
        """Fetches chronological quality scores and trajectory slope."""
        trend = self.store.quality_trend(dataset_name=dataset_name, limit=limit)
        return {
            "dataset_name": dataset_name,
            "direction": trend.direction,
            "slope": trend.slope,
            "latest": trend.latest,
            "mean": trend.mean,
            "delta_from_mean": getattr(trend, "delta_from_mean", (trend.latest - trend.mean) if trend.latest and trend.mean else 0.0),
            "scores": [
                {"run_id": p.get("run_id"), "score": p.get("quality_score"), "timestamp": p.get("timestamp")}
                for p in trend.points
            ],
        }

    def get_failing_streaks(self, dataset_name: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Identifies persistently failing or degrading expectations."""
        trends = self.store.failed_expectation_trends(dataset_name=dataset_name, limit=limit)
        return [
            {
                "expectation_type": item.expectation_type,
                "column": item.column,
                "failures": item.failures,
                "evaluations": item.evaluations,
                "failure_rate": item.failure_rate,
                "current_streak": item.current_streak,
                "trend": item.trend,
            }
            for item in trends
        ]

    def check_volume_anomaly(self, dataset_name: str, current_count: int) -> Dict[str, Any]:
        """Detects whether current row count is an outlier using median/MAD modified z-score."""
        anomaly_res = vx.detect_volume_anomaly(
            store=self.store,
            dataset_name=dataset_name,
            current_row_count=current_count,
            min_history=3,
        )
        return {
            "dataset_name": dataset_name,
            "current_count": current_count,
            "is_anomaly": anomaly_res.is_anomaly,
            "score": getattr(anomaly_res, "z_score", getattr(anomaly_res, "score", 0.0)),
            "direction": anomaly_res.direction,
            "expected_range": getattr(anomaly_res, "expected_range", None),
        }

    def check_dataset_freshness(
        self,
        df: Any,
        timestamp_column: str,
        max_age_hours: float = 48.0,
    ) -> Dict[str, Any]:
        """Verifies if the latest record in the dataset is within acceptable recency."""
        # Convert polars to pandas if needed for check_freshness
        data = df.to_pandas() if hasattr(df, "to_pandas") else df
        freshness_res = vx.check_freshness(
            data=data,
            column=timestamp_column,
            max_age=f"{int(max_age_hours)}h",
        )
        return {
            "timestamp_column": timestamp_column,
            "is_fresh": freshness_res.fresh,
            "age_hours": freshness_res.age_seconds / 3600.0 if freshness_res.age_seconds else None,
            "latest_timestamp": str(freshness_res.latest_timestamp),
            "max_age_hours": max_age_hours,
        }
