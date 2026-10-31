"""Tests for ValidateX Data Contracts on Polymarket schemas."""
from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
import pytest
import validatex as vx
from src.validation.silver_rules import load_markets_contract, load_ticks_contract


def test_load_contracts():
    m_contract = load_markets_contract()
    assert m_contract.name == "polymarket_5min_markets"
    assert m_contract.version == "1.0.0"
    assert len(m_contract.schema) >= 10
    assert len(m_contract.quality_rules) >= 5

    t_contract = load_ticks_contract()
    assert t_contract.name == "polymarket_1hz_ticks"
    assert t_contract.version == "1.0.0"


def test_validate_contract_pass():
    m_contract = load_markets_contract()
    t1 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 12, 5, 2, tzinfo=timezone.utc)
    df = pl.DataFrame({
        "condition_id": ["0xabc1", "0xabc2"],
        "market_start": [t1, t2],
        "market_end": [t2, t3],
        "recorded_at": [t3, t3],
        "token_up": ["0xup1", "0xup2"],
        "token_down": ["0xdn1", "0xdn2"],
        "volume": [15000.0, 25000.0],
        "liquidity": [50000.0, 75000.0],
        "outcome": ["Up", "Down"],
        "n_ticks": [300, 299],
    })

    result = vx.validate_contract(df, m_contract, engine="polars")
    assert result.success is True
    assert result.quality_score >= 95.0
    assert len(result.failures_by_owner()) == 0


def test_contract_breaking_change_detection():
    m_contract = load_markets_contract()

    # Simulate updated contract where fields were dropped
    new_contract = vx.DataContract.create(
        name="polymarket_5min_markets",
        version="1.1.0",
        team="prediction_market_quant",
    ).add_field("condition_id", "string", nullable=False)

    diff = vx.compare_contracts(m_contract, new_contract)
    assert diff.has_breaking_changes is True
    assert any("removed" in change.kind or "removed" in change.message.lower() for change in diff.breaking_changes)
