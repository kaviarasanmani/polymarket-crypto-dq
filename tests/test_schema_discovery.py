"""Tests for SchemaDiscovery and automated blueprint generation."""
from __future__ import annotations

import polars as pl
import pytest
from src.ingestion.schema_discovery import SchemaDiscovery


def test_map_to_logical_type():
    assert SchemaDiscovery.map_to_logical_type(pl.Int64) == "integer"
    assert SchemaDiscovery.map_to_logical_type(pl.Float64) == "float"
    assert SchemaDiscovery.map_to_logical_type(pl.String) == "string"
    assert SchemaDiscovery.map_to_logical_type(pl.Boolean) == "boolean"
    assert SchemaDiscovery.map_to_logical_type(pl.Datetime) == "timestamp"


def test_inspect_file_and_generate_blueprint(tmp_path):
    # Create test parquet
    df = pl.DataFrame({
        "condition_id": ["0x123", "0x456"],
        "volume": [100.5, 200.75],
        "outcome": ["Up", None],
        "n_ticks": [300, 298],
    })
    test_file = tmp_path / "test_markets.parquet"
    df.write_parquet(test_file)

    profile = SchemaDiscovery.inspect_file(test_file)
    assert profile["total_rows"] == 2
    assert profile["column_count"] == 4

    col_map = {c["name"]: c for c in profile["columns"]}
    assert col_map["condition_id"]["logical_type"] == "string"
    assert col_map["condition_id"]["nullable"] is False
    assert col_map["outcome"]["nullable"] is True

    # Test Markdown rendering
    md_report = SchemaDiscovery.generate_markdown_report(profile)
    assert "# Automated Schema Discovery Report" in md_report
    assert "condition_id" in md_report

    # Test YAML contract blueprint
    yaml_contract = SchemaDiscovery.generate_contract_blueprint_yaml(profile, "test_contract")
    assert "name: test_contract" in yaml_contract
    assert "condition_id" in yaml_contract
