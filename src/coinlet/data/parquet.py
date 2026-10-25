"""Parquet loading for WASM/Pyodide compatibility.

Provides HTTP-based Parquet reading that works in browsers without
DuckDB, websockets, or other native dependencies.

Uses pyarrow for Parquet reading (available in Pyodide) with
optional HTTP fetching via urllib or pyodide's fetch.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_PAGES_BASE = "https://{owner}.github.io/{repo}"


class ParquetLoader:
    """Load Parquet files from local paths or HTTP URLs.

    Designed for WASM/Pyodide compatibility:
    - Uses only pandas + pyarrow (both available in Pyodide)
    - Supports HTTP URLs for loading from GitHub raw/Pages
    - No DuckDB or other native dependencies

    Example:
        # In a marimo notebook running as WASM:
        loader = ParquetLoader()
        df = loader.load("https://raw.githubusercontent.com/user/coinlet/main/data/btc_usd_1d.parquet")

        # Or with convenience methods:
        df = loader.from_github_raw("user", "coinlet", "main", "data/btc_usd_1d.parquet")
    """

    def __init__(self, base_url: str | None = None):
        """Initialize loader.

        Args:
            base_url: Optional base URL for relative paths
        """
        self._base_url = base_url

    def load(self, path_or_url: str | Path) -> pd.DataFrame:
        """Load Parquet file from path or URL.

        Args:
            path_or_url: Local path or HTTP(S) URL

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        path_str = str(path_or_url)

        if path_str.startswith(("http://", "https://")):
            return self._load_from_url(path_str)
        else:
            return self._load_from_file(Path(path_str))

    def _load_from_file(self, path: Path) -> pd.DataFrame:
        """Load from local file."""
        if not path.exists():
            logger.error(f"File not found: {path}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.read_parquet(path)
        return self._normalize_df(df)

    def _load_from_url(self, url: str) -> pd.DataFrame:
        """Load from HTTP URL."""
        try:
            data = self._fetch_url(url)
            df = pd.read_parquet(io.BytesIO(data))
            return self._normalize_df(df)
        except Exception as e:
            logger.error(f"Failed to load from {url}: {e}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    def _fetch_url(self, url: str) -> bytes:
        """Fetch URL content, with Pyodide compatibility."""
        try:
            import asyncio

            from pyodide.http import pyfetch

            async def fetch():
                response = await pyfetch(url)
                return await response.bytes()

            return asyncio.get_event_loop().run_until_complete(fetch())

        except ImportError:
            from urllib.request import urlopen
            with urlopen(url, timeout=60) as response:
                return response.read()

    def _normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame to standard format."""
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
        elif not isinstance(df.index, pd.DatetimeIndex):
            if df.index.name and "time" in df.index.name.lower():
                df.index = pd.to_datetime(df.index, utc=True)

        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")

        df.index.name = "timestamp"
        return df.sort_index()

    def from_github_raw(
        self,
        owner: str,
        repo: str,
        ref: str,
        path: str,
    ) -> pd.DataFrame:
        """Load Parquet from GitHub raw content.

        Args:
            owner: GitHub username or org
            repo: Repository name
            ref: Branch, tag, or commit
            path: Path within repo (e.g., "data/btc_usd_1d.parquet")

        Returns:
            DataFrame with OHLCV data
        """
        url = f"{GITHUB_RAW_BASE}/{owner}/{repo}/{ref}/{path}"
        return self._load_from_url(url)

    def from_github_pages(
        self,
        owner: str,
        repo: str,
        path: str,
    ) -> pd.DataFrame:
        """Load Parquet from GitHub Pages.

        Args:
            owner: GitHub username or org
            repo: Repository name
            path: Path within Pages site (e.g., "data/btc_usd_1d.parquet")

        Returns:
            DataFrame with OHLCV data
        """
        base = GITHUB_PAGES_BASE.format(owner=owner, repo=repo)
        url = f"{base}/{path}"
        return self._load_from_url(url)

    @staticmethod
    def list_available_datasets(data_dir: str | Path = "data") -> list[dict]:
        """List available Parquet files in data directory.

        Args:
            data_dir: Directory to scan

        Returns:
            List of dicts with file info (name, size, path)
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            return []

        datasets = []
        for f in data_path.glob("*.parquet"):
            datasets.append({
                "name": f.stem,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            })

        return sorted(datasets, key=lambda x: x["name"])


def load_parquet(path_or_url: str | Path) -> pd.DataFrame:
    """Convenience function to load a Parquet file.

    Args:
        path_or_url: Local path or HTTP URL

    Returns:
        DataFrame with UTC timestamp index and OHLCV columns
    """
    return ParquetLoader().load(path_or_url)
