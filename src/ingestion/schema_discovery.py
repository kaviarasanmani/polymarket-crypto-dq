"""Automated schema discovery and profiling for raw Polymarket datasets.

Inspects Parquet and CSV files, extracts Arrow/Polars data types,
identifies nullability, computes cardinality and boundary statistics,
and generates automated Data Contract blueprints.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl
import pyarrow.parquet as pq


@dataclass
class ColumnProfile:
    """Statistical and structural profile for a single column."""
    name: str
    physical_type: str
    logical_type: str
    nullable: bool
    null_count: int
    null_percentage: float
    distinct_count: int
    sample_values: List[Any]
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None


class SchemaDiscovery:
    """Discovers schema, nullability, and value distributions from raw files."""

    # Map physical Polars/Arrow types to ValidateX canonical logical types
    LOGICAL_TYPE_MAPPING = {
        pl.Int8: "integer",
        pl.Int16: "integer",
        pl.Int32: "integer",
        pl.Int64: "integer",
        pl.UInt8: "integer",
        pl.UInt16: "integer",
        pl.UInt32: "integer",
        pl.UInt64: "integer",
        pl.Float32: "float",
        pl.Float64: "float",
        pl.String: "string",
        pl.Utf8: "string",
        pl.Boolean: "boolean",
        pl.Date: "date",
        pl.Datetime: "timestamp",
        pl.Time: "time",
        pl.Duration: "string",
    }

    @classmethod
    def map_to_logical_type(cls, dtype: pl.DataType) -> str:
        """Maps a Polars DataType to a ValidateX logical type."""
        for pl_type, logical in cls.LOGICAL_TYPE_MAPPING.items():
            if dtype == pl_type or isinstance(dtype, pl_type if isinstance(pl_type, type) else type(pl_type)):
                return logical
        # Fallback inspection by string
        type_str = str(dtype).lower()
        if "int" in type_str:
            return "integer"
        if "float" in type_str or "decimal" in type_str:
            return "float"
        if "datetime" in type_str or "timestamp" in type_str:
            return "timestamp"
        if "date" in type_str:
            return "date"
        if "bool" in type_str:
            return "boolean"
        return "string"

    @classmethod
    def inspect_file(
        cls,
        file_path: str | Path,
        sample_limit: Optional[int] = 50000,
    ) -> Dict[str, Any]:
        """Inspects a raw data file (Parquet or CSV) and produces a comprehensive schema profile.

        Args:
            file_path: Path to dataset file.
            sample_limit: Optional row limit for fast profiling on huge files.

        Returns:
            Dictionary with dataset summary, row count, and column profiles.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        # Polars lazy scan to handle massive multi-million row files safely
        if path.suffix == ".parquet":
            lazy_df = pl.scan_parquet(str(path))
        elif path.suffix == ".csv":
            lazy_df = pl.scan_csv(str(path))
        else:
            raise ValueError(f"Unsupported file format '{path.suffix}'. Supported: .parquet, .csv")

        total_rows = lazy_df.select(pl.len()).collect().item()
        
        # Sample for value distributions if dataset is massive
        scan_df = lazy_df.limit(sample_limit).collect() if sample_limit and total_rows > sample_limit else lazy_df.collect()
        eval_rows = len(scan_df)

        profiles: List[ColumnProfile] = []
        for col in scan_df.columns:
            series = scan_df[col]
            dtype = series.dtype
            logical_type = cls.map_to_logical_type(dtype)

            null_count = series.null_count()
            null_pct = round((null_count / eval_rows) * 100, 2) if eval_rows > 0 else 0.0
            nullable = null_count > 0

            distinct_cnt = series.n_unique()

            # Samples
            non_null_s = series.drop_nulls()
            samples = [str(v) if not isinstance(v, (int, float, bool)) else v for v in non_null_s.head(5).to_list()]

            min_val = None
            max_val = None
            if logical_type in ("integer", "float"):
                if len(non_null_s) > 0:
                    min_val = float(non_null_s.min())
                    max_val = float(non_null_s.max())
            elif logical_type in ("timestamp", "date"):
                if len(non_null_s) > 0:
                    min_val = str(non_null_s.min())
                    max_val = str(non_null_s.max())

            profiles.append(
                ColumnProfile(
                    name=col,
                    physical_type=str(dtype),
                    logical_type=logical_type,
                    nullable=nullable,
                    null_count=null_count,
                    null_percentage=null_pct,
                    distinct_count=distinct_cnt,
                    sample_values=samples,
                    min_value=min_val,
                    max_value=max_val,
                )
            )

        return {
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "total_rows": total_rows,
            "sampled_rows": eval_rows,
            "column_count": len(profiles),
            "columns": [asdict(p) for p in profiles],
        }

    @classmethod
    def generate_markdown_report(cls, profile: Dict[str, Any], output_path: Optional[str | Path] = None) -> str:
        """Renders schema discovery profile as an executive Markdown document."""
        md = []
        md.append(f"# Automated Schema Discovery Report: `{profile['file_name']}`\n")
        md.append(f"- **Total Rows**: {profile['total_rows']:,}")
        md.append(f"- **Evaluated Sample**: {profile['sampled_rows']:,}")
        md.append(f"- **Columns Detected**: {profile['column_count']}")
        md.append(f"- **File Size**: {profile['file_size_bytes'] / (1024 * 1024):.2f} MB\n")
        md.append("## Column Profiles\n")
        md.append("| Column | Physical Type | Logical Type | Nullable | Null % | Distinct | Min | Max |")
        md.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

        for c in profile["columns"]:
            min_str = f"{c['min_value']:.4f}" if isinstance(c['min_value'], float) else str(c['min_value'] or "N/A")
            max_str = f"{c['max_value']:.4f}" if isinstance(c['max_value'], float) else str(c['max_value'] or "N/A")
            nullable_badge = "⚠️ Yes" if c["nullable"] else "✅ No"
            md.append(
                f"| **`{c['name']}`** | `{c['physical_type']}` | `{c['logical_type']}` | "
                f"{nullable_badge} | {c['null_percentage']}% | {c['distinct_count']:,} | "
                f"{min_str} | {max_str} |"
            )

        report_str = "\n".join(md)
        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(report_str, encoding="utf-8")
            print(f"[SUCCESS] Saved schema discovery report to {out_file}")

        return report_str

    @classmethod
    def generate_contract_blueprint_yaml(
        cls,
        profile: Dict[str, Any],
        contract_name: str,
        version: str = "1.0.0",
        team: str = "data_platform",
    ) -> str:
        """Generates a ValidateX DataContract YAML string from the discovered schema."""
        lines = [
            "contract:",
            f"  name: {contract_name}",
            f"  version: {version}",
            f"  description: Auto-generated contract from schema discovery of {profile['file_name']}",
            "  owner:",
            f"    team: {team}",
            "    steward: market_operations",
            "  schema:",
        ]

        for c in profile["columns"]:
            lines.append(f"    - name: {c['name']}")
            lines.append(f"      type: {c['logical_type']}")
            lines.append(f"      nullable: {'true' if c['nullable'] else 'false'}")

        lines.extend([
            "  quality_rules:",
        ])
        for c in profile["columns"]:
            if not c["nullable"]:
                lines.append("    - expectation: expect_column_to_not_be_null")
                lines.append(f"      column: {c['name']}")
                lines.append("      severity: critical")

        lines.extend([
            "  thresholds:",
            "    minimum_quality_score: 95.0",
            "    max_critical_failures: 0",
        ])
        return "\n".join(lines)
