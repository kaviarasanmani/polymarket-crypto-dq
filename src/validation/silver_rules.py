"""Silver layer validation and Data Contracts for cleansed Polymarket data.

Enforces versioned Data Contracts and prediction-market domain business rules:
order-book integrity (no crossed books), probability limits, and complementary arbitrage bounds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import validatex as vx


def load_markets_contract(contract_path: Optional[str | Path] = None) -> vx.DataContract:
    """Loads the Polymarket 5-Minute Markets DataContract."""
    path = Path(contract_path or "config/contracts/markets_contract.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Markets contract not found at: {path}")
    return vx.DataContract.from_yaml_file(str(path))


def load_ticks_contract(contract_path: Optional[str | Path] = None) -> vx.DataContract:
    """Loads the Polymarket 1Hz Ticks DataContract."""
    path = Path(contract_path or "config/contracts/ticks_contract.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Ticks contract not found at: {path}")
    return vx.DataContract.from_yaml_file(str(path))


def build_silver_business_suite(suite_name: str = "silver_prediction_market_business_rules") -> vx.ExpectationSuite:
    """Builds ValidateX ExpectationSuite for derived order-book metrics and arbitrage bounds."""
    suite = (
        vx.ExpectationSuite(suite_name)
        # Order-book integrity: Spreads must be strictly non-negative (no crossed book)
        .add("expect_column_values_to_be_between", column="spread_up", min_value=0.0, max_value=1.0, severity="critical")
        .add("expect_column_values_to_be_between", column="spread_down", min_value=0.0, max_value=1.0, severity="critical")
        # Probability bounds on mid-market prices
        .add("expect_column_values_to_be_between", column="mid_up", min_value=0.0, max_value=1.0, severity="critical")
        .add("expect_column_values_to_be_between", column="mid_down", min_value=0.0, max_value=1.0, severity="critical")
        # Order book depth & imbalance
        .add("expect_column_values_to_be_between", column="imbalance", min_value=-1.0, max_value=1.0, severity="warning")
        # Arbitrage sanity: Combined best bid probability should not exceed 1.05 (allowing 5% slippage/margin)
        .add("expect_column_values_to_be_between", column="arb_bid_sum", min_value=0.0, max_value=1.05, severity="warning")
    )
    return suite
