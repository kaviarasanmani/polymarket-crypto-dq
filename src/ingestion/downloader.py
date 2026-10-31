"""Dataset manager for Polymarket 5-Minute Crypto Up/Down Markets.

Handles Kaggle dataset discovery, automated download via Kaggle API,
fallback instructions for manual download, and a high-fidelity
synthetic benchmark generator for instant local testing and CI/CD.
"""
from __future__ import annotations

import hashlib
import os
import random
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import polars as pl


class DatasetManager:
    """Manages raw dataset acquisition from Kaggle or synthetic simulation."""

    KAGGLE_DATASET = "kachoio/polymarket-5-minute-crypto-updown-markets"
    DEFAULT_COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "BNB"]

    def __init__(self, raw_dir: str | Path = "data/raw"):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def locate_existing_files(self) -> Dict[str, Dict[str, Optional[Path]]]:
        """Scans raw_dir for existing market and tick parquet/csv files per coin."""
        inventory: Dict[str, Dict[str, Optional[Path]]] = {}
        for coin in self.DEFAULT_COINS:
            coin_lower = coin.lower()
            coin_upper = coin.upper()

            # Markets file lookup
            m_path = None
            for cand in [
                self.raw_dir / f"{coin_lower}_markets.parquet",
                self.raw_dir / f"{coin_upper}_markets.parquet",
                self.raw_dir / f"{coin_lower}_markets.csv",
            ]:
                if cand.exists():
                    m_path = cand
                    break

            # Ticks file lookup
            t_path = None
            for cand in [
                self.raw_dir / f"{coin_lower}_ticks.parquet",
                self.raw_dir / f"{coin_upper}_ticks.parquet",
                self.raw_dir / f"{coin_lower}_ticks.csv",
            ]:
                if cand.exists():
                    t_path = cand
                    break

            inventory[coin] = {"markets": m_path, "ticks": t_path}
        return inventory

    def has_any_data(self) -> bool:
        """Returns True if any valid market/tick data files are found in raw_dir."""
        inv = self.locate_existing_files()
        return any(files["markets"] is not None for files in inv.values())

    def download_from_kaggle(self, target_dir: Optional[str | Path] = None) -> bool:
        """Attempts to download the dataset using kaggle CLI or kaggle API."""
        dest = Path(target_dir) if target_dir else self.raw_dir

        # Check for kaggle.json or environment variables
        has_creds = (
            "KAGGLE_USERNAME" in os.environ and "KAGGLE_KEY" in os.environ
        ) or Path(os.path.expanduser("~/.kaggle/kaggle.json")).exists()

        if not has_creds:
            print("[INFO] Kaggle credentials not found in ~/.kaggle/kaggle.json or environment.")
            return False

        try:
            import subprocess

            print(f"[INFO] Downloading Kaggle dataset '{self.KAGGLE_DATASET}' into '{dest}'...")
            result = subprocess.run(
                ["kaggle", "datasets", "download", "-d", self.KAGGLE_DATASET, "-p", str(dest), "--unzip"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                print(f"[SUCCESS] Downloaded and unzipped Kaggle dataset to {dest}")
                self._extract_any_nested_zips(dest)
                return True
            else:
                print(f"[WARN] Kaggle download failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"[WARN] Could not invoke Kaggle CLI: {e}")
            return False

    def _extract_any_nested_zips(self, directory: Path) -> None:
        """Unzips any zip files downloaded in the directory."""
        for item in directory.glob("*.zip"):
            try:
                with zipfile.ZipFile(item, "r") as z:
                    z.extractall(directory)
                item.unlink(missing_ok=True)
            except Exception as e:
                print(f"[WARN] Could not unzip {item}: {e}")

    @staticmethod
    def print_manual_download_instructions(target_dir: str | Path = "data/raw") -> str:
        """Returns clear user instructions for downloading the dataset manually."""
        instructions = f"""
================================================================================
KAGGLE DATASET ACQUISITION INSTRUCTIONS
================================================================================
Dataset: Polymarket 5-Minute Crypto Up/Down Markets
URL: https://www.kaggle.com/kachoio/polymarket-5-minute-crypto-updown-markets

Option A (Automated Kaggle CLI):
  1. Obtain your API key from https://www.kaggle.com/settings -> "Create New Token"
  2. Place kaggle.json into ~/.kaggle/kaggle.json (chmod 600 ~/.kaggle/kaggle.json)
  3. Run:
     kaggle datasets download -d kachoio/polymarket-5-minute-crypto-updown-markets -p {target_dir} --unzip

Option B (Manual Web Download):
  1. Visit: https://www.kaggle.com/kachoio/polymarket-5-minute-crypto-updown-markets
  2. Click "Download" (ZIP archive)
  3. Extract all <coin>_markets.parquet and <coin>_ticks.parquet files into:
     {Path(target_dir).resolve()}

Option C (High-Fidelity Synthetic Benchmark):
  The pipeline automatically generates structurally identical synthetic datasets
  matching the exact schema, probability bounds, and order-book microstructure
  if no raw files are detected.
================================================================================
"""
        return instructions

    def generate_synthetic_benchmark(
        self,
        coins: Optional[List[str]] = None,
        windows_per_coin: int = 12,
        ticks_per_window: int = 60,
        inject_anomalies: bool = False,
        seed: int = 42,
    ) -> Tuple[List[Path], List[Path]]:
        """Generates realistic synthetic Polymarket markets and ticks matching schema.

        Args:
            coins: List of coin symbols (default: BTC, ETH, SOL).
            windows_per_coin: Number of 5-minute market windows.
            ticks_per_window: Number of 1-second ticks per window.
            inject_anomalies: If True, injects controlled anomalies to test ValidateX rules.
            seed: Random seed for deterministic reproducibility.

        Returns:
            Tuple of (market_file_paths, tick_file_paths).
        """
        random.seed(seed)
        target_coins = coins or ["BTC", "ETH", "SOL"]
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        # Snap to recent 5-min boundary
        start_time = now - timedelta(minutes=5 * windows_per_coin)

        market_paths: List[Path] = []
        tick_paths: List[Path] = []

        print(f"[INFO] Generating high-fidelity synthetic benchmark for {len(target_coins)} coins...")

        for coin in target_coins:
            market_rows = []
            tick_rows = []

            for w_idx in range(windows_per_coin):
                m_start = start_time + timedelta(minutes=5 * w_idx)
                m_end = m_start + timedelta(minutes=5)
                rec_at = m_end + timedelta(seconds=2)

                # Deterministic condition_id hash
                cond_hash = hashlib.sha256(f"{coin}_{m_start.isoformat()}".encode()).hexdigest()[:32]
                cond_id = f"0x{cond_hash}"
                token_up = f"0xup_{cond_hash[:16]}"
                token_down = f"0xdown_{cond_hash[16:]}"

                volume = round(random.uniform(5000.0, 150000.0), 2)
                liquidity = round(random.uniform(10000.0, 500000.0), 2)
                outcome = random.choice(["Up", "Down"])
                n_ticks = ticks_per_window

                # Inject deliberate markets anomaly if requested for DQ testing
                if inject_anomalies and w_idx == 0 and coin == "BTC":
                    volume = -50.0  # Invalid negative volume

                market_rows.append({
                    "condition_id": cond_id,
                    "market_start": m_start,
                    "market_end": m_end,
                    "recorded_at": rec_at,
                    "token_up": token_up,
                    "token_down": token_down,
                    "volume": float(volume),
                    "liquidity": float(liquidity),
                    "outcome": outcome,
                    "n_ticks": int(n_ticks),
                })

                # Generate 1-second order book ticks
                base_up_prob = random.uniform(0.35, 0.65)
                for s in range(ticks_per_window):
                    tick_dt = m_start + timedelta(seconds=s)
                    epoch_s = int(tick_dt.timestamp())

                    # Micro-price drift (Brownian motion)
                    drift = random.gauss(0, 0.005)
                    base_up_prob = max(0.05, min(0.95, base_up_prob + drift))

                    # Bid / Ask spreads
                    spread_up = random.uniform(0.01, 0.03)
                    bu = max(0.01, round(base_up_prob - spread_up / 2, 4))
                    au = min(0.99, round(base_up_prob + spread_up / 2, 4))

                    # Down contract price (approx complementary: 1 - up_prob)
                    base_down_prob = 1.0 - base_up_prob
                    spread_down = random.uniform(0.01, 0.03)
                    bd = max(0.01, round(base_down_prob - spread_down / 2, 4))
                    ad = min(0.99, round(base_down_prob + spread_down / 2, 4))

                    # Share sizes & depth
                    su = round(random.uniform(100.0, 5000.0), 2)
                    sd = round(random.uniform(100.0, 5000.0), 2)
                    sau = round(random.uniform(100.0, 5000.0), 2)
                    sad = round(random.uniform(100.0, 5000.0), 2)
                    du = round(su * bu * 1.5, 2)
                    dd = round(sd * bd * 1.5, 2)

                    # Inject deliberate ticks anomaly if requested
                    if inject_anomalies and w_idx == 1 and s == 10 and coin == "ETH":
                        bu = 1.25  # Invalid probability price > 1.0

                    tick_rows.append({
                        "condition_id": cond_id,
                        "t": epoch_s,
                        "ts_utc": tick_dt,
                        "bu": float(bu),
                        "au": float(au),
                        "bd": float(bd),
                        "ad": float(ad),
                        "su": float(su),
                        "sd": float(sd),
                        "sau": float(sau),
                        "sad": float(sad),
                        "du": float(du),
                        "dd": float(dd),
                    })

            m_df = pl.DataFrame(market_rows)
            t_df = pl.DataFrame(tick_rows)

            m_file = self.raw_dir / f"{coin.lower()}_markets.parquet"
            t_file = self.raw_dir / f"{coin.lower()}_ticks.parquet"

            m_df.write_parquet(m_file)
            t_df.write_parquet(t_file)

            market_paths.append(m_file)
            tick_paths.append(t_file)
            print(f"[SUCCESS] Wrote {len(market_rows)} markets and {len(tick_rows)} ticks to {m_file.name} & {t_file.name}")

        return market_paths, tick_paths
