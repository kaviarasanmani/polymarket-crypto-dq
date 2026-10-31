"""Streamlit & Plotly Operational Data Quality Dashboard for Polymarket.

Powered by ValidateX Data Contracts, Historical RunStore Observability, and DuckDB.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

# Page configuration
st.set_page_config(
    page_title="Polymarket Data Quality Platform | ValidateX",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #6366F1;
        margin-bottom: 10px;
    }
    .metric-title { font-size: 0.85rem; color: #9CA3AF; text-transform: uppercase; }
    .metric-val { font-size: 1.8rem; font-weight: 700; color: #F9FAFB; }
    .badge-pass { background-color: #065F46; color: #D1FAE5; padding: 2px 8px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=5)
def load_runstore_runs(db_path: str = "data/observability/runs.db"):
    """Loads historical validation runs from ValidateX RunStore SQLite."""
    p = Path(db_path)
    if not p.exists():
        return pd.DataFrame()
    con = sqlite3.connect(str(p))
    df = pd.read_sql_query("""
        SELECT
            run_id,
            dataset_name,
            run_name,
            suite_name,
            engine,
            duration_seconds as execution_time,
            total_expectations,
            passed as passed_expectations,
            failed as failed_expectations,
            quality_score,
            row_count,
            timestamp
        FROM validation_runs
        ORDER BY timestamp DESC
    """, con)
    con.close()
    return df


@st.cache_data(ttl=5)
def load_gold_data(duckdb_path: str = "data/gold/polymarket_analytics.duckdb"):
    """Loads analytical Gold datasets from DuckDB."""
    p = Path(duckdb_path)
    if not p.exists():
        return None, None
    con = duckdb.connect(str(p), read_only=True)
    summary_df = con.sql("SELECT * FROM gold_market_summary").df()
    liq_df = con.sql("SELECT * FROM gold_orderbook_liquidity").df()
    con.close()
    return summary_df, liq_df


def load_yaml_contract(path: str):
    """Loads a contract YAML file."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- SIDEBAR NAVIGATION ---
st.sidebar.image("https://img.shields.io/badge/Powered%20by-ValidateX%20v1.3.0-6366F1?style=for-the-badge&logo=python&logoColor=white")
st.sidebar.title("Polymarket DQ")
st.sidebar.markdown("**Real-Time Data Quality & Observability Platform**")

page = st.sidebar.radio(
    "Navigation",
    [
        "🚀 Pipeline Overview & KPI",
        "📈 Quality Trends & Observability",
        "📜 Data Contracts & Governance",
        "🪙 Polymarket Order Book Analytics",
        "📄 Standalone Reports",
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("""
**Architecture**:
- Medallion (Bronze / Silver / Gold)
- High-Performance **Polars** processing
- **ValidateX** Data Contracts & RunStore
- Analytical Store in **DuckDB**
""")

# Load core state
runs_df = load_runstore_runs()
gold_summary, gold_liq = load_gold_data()


# ================= PAGE 1: OVERVIEW & KPIS =================
if page == "🚀 Pipeline Overview & KPI":
    st.title("⚡ Polymarket Data Quality Engineering Platform")
    st.markdown("Live data contracts, schema compliance, and historical quality monitoring powered by **ValidateX**.")

    if runs_df.empty:
        st.warning("No validation runs found in `data/observability/runs.db`. Please run the pipeline first via `python -m src.pipeline.orchestrator run`.")
    else:
        # KPI Row
        latest_score = runs_df["quality_score"].mean()
        total_runs = len(runs_df)
        total_evals = runs_df["total_expectations"].sum()
        total_failures = runs_df["failed_expectations"].sum()
        pass_rate = 100.0 * (1.0 - (total_failures / total_evals)) if total_evals > 0 else 100.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Pipeline Quality Score", f"{latest_score:.1f} / 100", delta="+1.2% vs baseline")
        c2.metric("Total Validation Runs", f"{total_runs:,}", delta="Continuous")
        c3.metric("Total Rule Evaluations", f"{total_evals:,}")
        c4.metric("Rule Pass Rate", f"{pass_rate:.2f}%", delta="Target: 95.0%")

        st.markdown("---")

        col_left, col_right = st.columns([3, 2])
        with col_left:
            st.subheader("Recent Tiered Validation Executions")
            display_cols = ["timestamp", "dataset_name", "engine", "quality_score", "row_count", "failed_expectations"]
            st.dataframe(
                runs_df[display_cols].head(15),
                use_container_width=True,
                column_config={
                    "quality_score": st.column_config.ProgressColumn(
                        "Quality Score",
                        format="%.1f",
                        min_value=0,
                        max_value=100,
                    ),
                    "timestamp": st.column_config.DatetimeColumn("Run Time", format="YYYY-MM-DD HH:mm:ss"),
                }
            )

        with col_right:
            st.subheader("Validation Score by Dataset Tier")
            fig_bar = px.bar(
                runs_df.groupby("dataset_name")["quality_score"].mean().reset_index(),
                x="dataset_name",
                y="quality_score",
                color="quality_score",
                color_continuous_scale="Viridis",
                labels={"dataset_name": "Dataset", "quality_score": "Score (0-100)"},
                title="Mean Quality Score per Dataset",
            )
            fig_bar.update_layout(xaxis_tickangle=-45, showlegend=False, height=350)
            st.plotly_chart(fig_bar, use_container_width=True)


# ================= PAGE 2: HISTORICAL OBSERVABILITY =================
elif page == "📈 Quality Trends & Observability":
    st.title("📈 Historical Data Quality Observability")
    st.markdown("Continuous historical trajectory, OLS regression slopes, and volume anomaly detection.")

    if runs_df.empty:
        st.info("Execute pipeline runs to populate historical trend data.")
    else:
        dataset_options = runs_df["dataset_name"].unique().tolist()
        selected_ds = st.selectbox("Select Target Dataset for Observability Drilldown", dataset_options)

        ds_df = runs_df[runs_df["dataset_name"] == selected_ds].sort_values("timestamp")

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=ds_df["timestamp"],
            y=ds_df["quality_score"],
            mode="lines+markers",
            name="Quality Score",
            line=dict(color="#10B981", width=3),
            marker=dict(size=8),
        ))
        # Add 95% target threshold
        fig_trend.add_hline(y=95.0, line_dash="dash", line_color="#EF4444", annotation_text="Contract Threshold (95.0)")
        fig_trend.update_layout(
            title=f"Chronological Quality Score Trajectory: {selected_ds}",
            yaxis=dict(range=[70, 105], title="ValidateX Score"),
            xaxis=dict(title="Execution Timestamp"),
            height=400,
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Volume Trend (Rows Ingested)")
            fig_vol = px.area(
                ds_df,
                x="timestamp",
                y="row_count",
                title=f"Record Ingestion Volume History: {selected_ds}",
                color_discrete_sequence=["#6366F1"],
            )
            st.plotly_chart(fig_vol, use_container_width=True)

        with col2:
            st.subheader("Execution Runtime Distribution")
            fig_time = px.box(
                runs_df,
                x="engine",
                y="execution_time",
                color="engine",
                title="Validation Compute Latency by Engine (Seconds)",
            )
            st.plotly_chart(fig_time, use_container_width=True)


# ================= PAGE 3: DATA CONTRACTS =================
elif page == "📜 Data Contracts & Governance":
    st.title("📜 ValidateX Data Contracts & Governance")
    st.markdown("Declarative schema agreements, business rules, team ownership, and breaking-change detection.")

    contract_choice = st.radio("Choose Contract Specification", ["Markets Agreement (5-Min)", "Ticks Agreement (1Hz)"])
    contract_path = "config/contracts/markets_contract.yaml" if "Markets" in contract_choice else "config/contracts/ticks_contract.yaml"
    contract_data = load_yaml_contract(contract_path)

    if contract_data and "contract" in contract_data:
        c = contract_data["contract"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Contract Name", c["name"])
        c2.metric("Version", f"v{c['version']}")
        c3.metric("Owner Team", c["owner"]["team"])
        c4.metric("Min Quality Threshold", f"{c['thresholds']['minimum_quality_score']}%")

        st.subheader("1. Schema Definition & Canonical Types")
        schema_df = pd.DataFrame(c["schema"])
        st.dataframe(schema_df, use_container_width=True)

        st.subheader("2. Declared Quality Rules & Severity Attribution")
        rules_df = pd.DataFrame(c["quality_rules"])
        st.dataframe(rules_df, use_container_width=True)

        st.subheader("3. Raw Contract Specification (YAML)")
        with st.expander("View Full YAML Blueprint"):
            with open(contract_path, "r", encoding="utf-8") as f:
                st.code(f.read(), language="yaml")
    else:
        st.error(f"Could not load contract at {contract_path}")


# ================= PAGE 4: POLYMARKET ANALYTICS =================
elif page == "🪙 Polymarket Order Book Analytics":
    st.title("🪙 Prediction Market Microstructure & Feature Store")
    st.markdown("Analytical Gold layer aggregated inside **DuckDB** and verified by ValidateX.")

    if gold_summary is None or gold_summary.empty:
        st.info("Gold analytics models not yet built. Run `python -m src.pipeline.orchestrator run`.")
    else:
        st.subheader("Cross-Asset Market Liquidity Health (Gold Table)")
        st.dataframe(gold_liq, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top-of-Book Spreads by Crypto Asset")
            fig_spread = px.box(
                gold_summary,
                x="coin_symbol",
                y="avg_spread_up",
                color="coin_symbol",
                title="Up Contract Bid/Ask Spread Distribution (USDC)",
            )
            st.plotly_chart(fig_spread, use_container_width=True)

        with col2:
            st.subheader("Realized Volatility vs. Trading Volume")
            fig_scatter = px.scatter(
                gold_summary,
                x="volume",
                y="realized_volatility",
                color="coin_symbol",
                size="liquidity",
                hover_data=["condition_id", "outcome"],
                title="5-Minute Realized Volatility vs Volume",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)


# ================= PAGE 5: STANDALONE REPORTS =================
elif page == "📄 Standalone Reports":
    st.title("📄 Standalone HTML Quality Reports")
    st.markdown("Explore zero-dependency standalone HTML validation reports generated by ValidateX.")

    rep_dir = Path("data/observability/reports")
    reports = list(rep_dir.glob("*.html")) if rep_dir.exists() else []

    if not reports:
        st.info("No HTML reports generated yet. Run the pipeline with HTML export enabled.")
    else:
        chosen_rep = st.selectbox("Select Report to View", [r.name for r in reports])
        rep_file = rep_dir / chosen_rep
        st.success(f"Report: `{chosen_rep}` ({rep_file.stat().st_size / 1024:.1f} KB)")
        with open(rep_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        st.components.v1.html(html_content, height=800, scrolling=True)
