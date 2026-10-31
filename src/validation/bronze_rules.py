"""Bronze layer validation suites for raw ingested Polymarket data.

Focuses on structural integrity: schema existence, primary key non-nullability,
positive volume/liquidity, and basic row count thresholds.
"""
from __future__ import annotations

import validatex as vx


def build_bronze_markets_suite(suite_name: str = "bronze_markets_structural_suite") -> vx.ExpectationSuite:
    """Builds a ValidateX ExpectationSuite for raw 5-minute markets data."""
    suite = (
        vx.ExpectationSuite(suite_name)
        # Structural existence
        .add("expect_table_row_count_to_be_between", min_value=1, severity="critical")
        .add("expect_column_to_exist", column="condition_id", severity="critical")
        .add("expect_column_to_exist", column="market_start", severity="critical")
        .add("expect_column_to_exist", column="market_end", severity="critical")
        .add("expect_column_to_exist", column="volume", severity="critical")
        .add("expect_column_to_exist", column="liquidity", severity="critical")
        .add("expect_column_to_exist", column="n_ticks", severity="critical")
        # Non-nullability
        .add("expect_column_to_not_be_null", column="condition_id", severity="critical")
        .add("expect_column_to_not_be_null", column="market_start", severity="critical")
        .add("expect_column_to_not_be_null", column="market_end", severity="critical")
        # Range sanity
        .add("expect_column_values_to_be_between", column="volume", min_value=0.0, severity="warning")
        .add("expect_column_values_to_be_between", column="liquidity", min_value=0.0, severity="warning")
        .add("expect_column_values_to_be_between", column="n_ticks", min_value=0, severity="warning")
    )
    return suite


def build_bronze_ticks_suite(suite_name: str = "bronze_ticks_structural_suite") -> vx.ExpectationSuite:
    """Builds a ValidateX ExpectationSuite for raw 1Hz order-book ticks."""
    suite = (
        vx.ExpectationSuite(suite_name)
        # Row count & essential columns
        .add("expect_table_row_count_to_be_between", min_value=1, severity="critical")
        .add("expect_column_to_exist", column="condition_id", severity="critical")
        .add("expect_column_to_exist", column="t", severity="critical")
        .add("expect_column_to_exist", column="bu", severity="critical")
        .add("expect_column_to_exist", column="au", severity="critical")
        .add("expect_column_to_exist", column="bd", severity="critical")
        .add("expect_column_to_exist", column="ad", severity="critical")
        # Keys
        .add("expect_column_to_not_be_null", column="condition_id", severity="critical")
        .add("expect_column_to_not_be_null", column="t", severity="critical")
        # Order book pricing bounds [0.0, 1.0]
        .add("expect_column_values_to_be_between", column="bu", min_value=0.0, max_value=1.0, severity="critical")
        .add("expect_column_values_to_be_between", column="au", min_value=0.0, max_value=1.0, severity="critical")
        .add("expect_column_values_to_be_between", column="bd", min_value=0.0, max_value=1.0, severity="critical")
        .add("expect_column_values_to_be_between", column="ad", min_value=0.0, max_value=1.0, severity="critical")
    )
    return suite
