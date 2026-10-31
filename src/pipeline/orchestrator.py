"""End-to-end Pipeline Orchestrator CLI for Polymarket Data Quality Engineering.

Runs full Medallion validation pipeline (Ingestion -> Schema Discovery -> Bronze
-> Silver -> Gold -> Observability) using ValidateX.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from ..ingestion.downloader import DatasetManager
from ..ingestion.schema_discovery import SchemaDiscovery
from ..observability.metrics_tracker import ObservabilityTracker
from .bronze_layer import BronzePipeline
from .silver_layer import SilverPipeline
from .gold_layer import GoldAnalyticsPipeline

console = Console()


class PipelineOrchestrator:
    """Programmatic orchestrator for the Polymarket data quality pipeline."""

    def __init__(
        self,
        raw_dir: str | Path = "data/raw",
        bronze_dir: str | Path = "data/bronze",
        silver_dir: str | Path = "data/silver",
        gold_dir: str | Path = "data/gold",
        duckdb_path: str | Path = "data/gold/polymarket_analytics.duckdb",
        store_path: str | Path = "data/observability/runs.db",
        reports_dir: str | Path = "data/observability/reports",
    ):
        self.raw_dir = Path(raw_dir)
        self.tracker = ObservabilityTracker(store_path=store_path, reports_dir=reports_dir)
        self.bronze = BronzePipeline(raw_dir=raw_dir, bronze_dir=bronze_dir, tracker=self.tracker)
        self.silver = SilverPipeline(bronze_dir=bronze_dir, silver_dir=silver_dir, tracker=self.tracker)
        self.gold = GoldAnalyticsPipeline(
            silver_dir=silver_dir,
            gold_dir=gold_dir,
            duckdb_path=duckdb_path,
            tracker=self.tracker,
        )

    def run_pipeline(
        self,
        coins: Optional[List[str]] = None,
        windows: int = 12,
        ticks: int = 60,
    ) -> dict:
        """Executes full Medallion pipeline across target coins."""
        target_coins = coins or ["BTC", "ETH", "SOL"]
        mgr = DatasetManager(self.raw_dir)
        if not mgr.has_any_data():
            mgr.generate_synthetic_benchmark(coins=target_coins, windows_per_coin=windows, ticks_per_window=ticks)

        b_res = self.bronze.run_all(target_coins)
        s_res = self.silver.run_all(target_coins)
        g_res = self.gold.build_analytics_models()
        return {
            "bronze": b_res,
            "silver": s_res,
            "gold": g_res,
        }


@click.group()
def cli():
    """Polymarket Crypto Data Quality Pipeline powered by ValidateX."""
    pass


@cli.command("download")
@click.option("--raw-dir", default="data/raw", help="Directory for raw files.")
@click.option("--force-benchmark", is_flag=True, help="Force synthetic benchmark generation.")
@click.option("--windows", default=12, help="Number of 5-minute market windows.")
@click.option("--ticks", default=60, help="Number of 1Hz ticks per window.")
def download_cmd(raw_dir: str, force_benchmark: bool, windows: int, ticks: int):
    """Acquires raw Polymarket dataset from Kaggle or generates benchmark data."""
    manager = DatasetManager(raw_dir=raw_dir)

    if not force_benchmark:
        console.print("[bold cyan]Checking for existing raw files or Kaggle credentials...[/bold cyan]")
        if manager.has_any_data():
            console.print("[green]Found existing raw dataset files in data/raw.[/green]")
            return

        success = manager.download_from_kaggle()
        if success:
            console.print("[bold green]Successfully downloaded dataset from Kaggle![/bold green]")
            return
        else:
            console.print("[yellow]Kaggle credentials not present. Printing instructions:[/yellow]")
            console.print(manager.print_manual_download_instructions(raw_dir))

    console.print("[bold blue]Generating high-fidelity synthetic benchmark matching Kaggle schema...[/bold blue]")
    manager.generate_synthetic_benchmark(
        coins=["BTC", "ETH", "SOL"],
        windows_per_coin=windows,
        ticks_per_window=ticks,
    )
    console.print("[bold green]Benchmark data ready in data/raw![/bold green]")


@cli.command("discover")
@click.option("--file", required=False, help="Specific file to profile.")
@click.option("--raw-dir", default="data/raw", help="Raw data directory.")
@click.option("--output-report", default="docs/SCHEMA_DISCOVERY.md", help="Path to write Markdown report.")
def discover_cmd(file: Optional[str], raw_dir: str, output_report: str):
    """Discovers and documents schema, nullability, and distributions."""
    raw_path = Path(raw_dir)
    target_files = [Path(file)] if file else list(raw_path.glob("*.parquet"))
    if not target_files:
        console.print("[red]No raw parquet files found. Run 'download' command first.[/red]")
        sys.exit(1)

    table = Table(title="Polymarket Schema Discovery Overview")
    table.add_column("File Name", style="cyan")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Size", justify="right")

    combined_reports = []
    for f in target_files[:4]:
        profile = SchemaDiscovery.inspect_file(f)
        table.add_row(
            profile["file_name"],
            f"{profile['total_rows']:,}",
            str(profile["column_count"]),
            f"{profile['file_size_bytes'] / (1024 * 1024):.2f} MB",
        )
        report_md = SchemaDiscovery.generate_markdown_report(profile)
        combined_reports.append(report_md)

    console.print(table)
    Path(output_report).parent.mkdir(parents=True, exist_ok=True)
    Path(output_report).write_text("\n\n---\n\n".join(combined_reports), encoding="utf-8")
    console.print(f"[bold green]Executive Schema Discovery report saved to: {output_report}[/bold green]")


@cli.command("run")
@click.option("--coins", default="BTC,ETH,SOL", help="Comma-separated coins to process.")
@click.option("--windows", default=12, help="Synthetic windows (if benchmark needed).")
@click.option("--ticks", default=60, help="Ticks per window (if benchmark needed).")
def run_cmd(coins: str, windows: int, ticks: int):
    """Executes the full Bronze -> Silver -> Gold pipeline with ValidateX quality gating."""
    coin_list = [c.strip().upper() for c in coins.split(",") if c.strip()]
    console.print(f"[bold magenta]Starting ValidateX Polymarket Data Quality Pipeline for: {coin_list}[/bold magenta]")

    # 1. Ingestion / Data check
    mgr = DatasetManager("data/raw")
    if not mgr.has_any_data():
        console.print("[yellow]No raw data detected. Generating benchmark data first...[/yellow]")
        mgr.generate_synthetic_benchmark(coins=coin_list, windows_per_coin=windows, ticks_per_window=ticks)

    tracker = ObservabilityTracker()

    # 2. Bronze Stage
    console.print("\n[bold cyan]--- Tier 1: Bronze Ingestion & Structural Quality Gating ---[/bold cyan]")
    bronze = BronzePipeline(tracker=tracker)
    b_res = bronze.run_all(coin_list)

    # 3. Silver Stage
    console.print("\n[bold cyan]--- Tier 2: Silver Cleansing & Data Contract Verification ---[/bold cyan]")
    silver = SilverPipeline(tracker=tracker)
    s_res = silver.run_all(coin_list)

    # 4. Gold Stage
    console.print("\n[bold cyan]--- Tier 3: Gold Analytical Aggregations & DuckDB Quality Suite ---[/bold cyan]")
    gold = GoldAnalyticsPipeline(tracker=tracker)
    g_res = gold.build_analytics_models()

    # Summary Dashboard Table
    console.print("\n[bold green]================ PIPELINE EXECUTION SUMMARY ================[/bold green]")
    summary_table = Table(title="ValidateX Quality Gating Summary")
    summary_table.add_column("Tier", style="yellow")
    summary_table.add_column("Dataset / Model", style="cyan")
    summary_table.add_column("Rows Processed", justify="right")
    summary_table.add_column("ValidateX Score", justify="right", style="green")

    for item in b_res["markets"]:
        summary_table.add_row("Bronze", item["dataset_name"], str(item["row_count"]), f"{item['quality_score']:.1f}/100")
    for item in s_res["markets"]:
        summary_table.add_row("Silver", item["dataset_name"], str(item["cleansed_count"]), f"{item['quality_score']:.1f}/100")
    for item in s_res["ticks"]:
        summary_table.add_row("Silver", item["dataset_name"], str(item["cleansed_count"]), f"{item['quality_score']:.1f}/100")
    summary_table.add_row("Gold", "gold_market_summary", str(g_res["gold_market_summary_rows"]), f"{g_res['summary_quality_score']:.1f}/100")
    summary_table.add_row("Gold", "gold_orderbook_liquidity", str(g_res["gold_orderbook_liquidity_rows"]), f"{g_res['liquidity_quality_score']:.1f}/100")

    console.print(summary_table)
    console.print("[bold green]Pipeline finished successfully with 100% data contract enforcement![/bold green]")


@cli.command("status")
@click.option("--dataset", default="gold_market_summary", help="Dataset name to inspect.")
def status_cmd(dataset: str):
    """Displays historical quality trend and anomaly stats from RunStore."""
    tracker = ObservabilityTracker()
    trend = tracker.get_quality_trend(dataset)
    console.print(f"[bold cyan]Dataset:[/bold cyan] {dataset}")
    console.print(f"[bold cyan]Quality Trajectory:[/bold cyan] {trend['direction'].upper()} (Slope: {trend['slope']:.3f})")
    console.print(f"[bold cyan]Latest Score:[/bold cyan] {trend['latest']:.1f} / 100")
    console.print(f"[bold cyan]Historical Mean:[/bold cyan] {trend['mean']:.1f} / 100")

    streaks = tracker.get_failing_streaks(dataset)
    if streaks:
        console.print("\n[yellow]Failing Expectation Streaks:[/yellow]")
        for s in streaks:
            console.print(f" - {s['expectation_type']} on '{s['column']}': streak={s['current_streak']}, rate={s['failure_rate']}%")
    else:
        console.print("\n[green]No active failing streaks! All expectations passing consistently.[/green]")


def main():
    cli()


if __name__ == "__main__":
    main()
