"""Parquet loading for WASM/Pyodide compatibility.

Provides Parquet reading that works in browsers without DuckDB, websockets,
or other native dependencies. Designed primarily for marimo WASM notebooks
exported to GitHub Pages.

Default behavior:
1. Look for data files relative to the notebook location (for bundled assets)
2. Fall back to HTTP URLs if explicitly provided

For GitHub Pages / WASM export:
- Bundle `data/*.parquet` files alongside the exported notebook
- The loader automatically finds them via marimo's notebook_location()

Uses pyarrow for Parquet reading (available in Pyodide).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_PAGES_BASE = "https://{owner}.github.io/{repo}"

BUNDLED_DATASETS = {
    "BTC-USD": "coinbase_BTC_USD_1d.parquet",
    "ETH-USD": "coinbase_ETH_USD_1d.parquet",
}


def _get_notebook_data_dir() -> str | None:
    """Get the data directory relative to the current marimo notebook.

    In WASM/Pyodide, marimo's notebook_location() returns the URL base
    where the notebook and its bundled assets are served.

    Returns:
        Base URL/path for data files, or None if not in a marimo context.
    """
    try:
        import marimo as mo
        base = mo.notebook_location()
        if base:
            if not base.endswith("/"):
                base += "/"
            return base + "data/"
    except (ImportError, AttributeError):
        pass
    return None


class ParquetLoader:
    """Load Parquet files from bundled assets, local paths, or HTTP URLs.

    Designed for WASM/Pyodide compatibility in marimo notebooks:
    - Default: loads from bundled assets relative to notebook location
    - Override: explicit HTTP URLs or local paths
    - Uses only pandas + pyarrow (both available in Pyodide)
    - No DuckDB or other native dependencies

    Example (marimo WASM notebook with bundled data):
        loader = ParquetLoader()
        df = loader.load_symbol("BTC-USD")  # Loads from bundled data/

    Example (explicit path/URL override):
        loader = ParquetLoader()
        df = loader.load("https://example.com/data/btc.parquet")
        df = loader.load("./local/data/btc.parquet")

    For GitHub Pages export, bundle these files:
        data/coinbase_BTC_USD_1d.parquet
        data/coinbase_ETH_USD_1d.parquet
    """

    def __init__(self, data_dir: str | Path | None = None):
        """Initialize loader.

        Args:
            data_dir: Base directory/URL for data files. If None, auto-detects:
                      - In marimo WASM: uses notebook_location() + "data/"
                      - Otherwise: uses local "data/" directory
        """
        self._data_dir = data_dir

    def _resolve_data_dir(self) -> str:
        """Resolve the data directory, with auto-detection."""
        if self._data_dir is not None:
            return str(self._data_dir)

        notebook_dir = _get_notebook_data_dir()
        if notebook_dir:
            return notebook_dir

        return "data/"

    def load_symbol(self, symbol: str) -> pd.DataFrame:
        """Load OHLCV data for a known symbol from bundled datasets.

        This is the recommended method for WASM notebooks with bundled data.

        Args:
            symbol: Trading pair (e.g., "BTC-USD", "ETH-USD")

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns

        Raises:
            ValueError: If symbol is not in bundled datasets
        """
        if symbol not in BUNDLED_DATASETS:
            available = ", ".join(BUNDLED_DATASETS.keys())
            raise ValueError(f"Unknown symbol: {symbol}. Available: {available}")

        filename = BUNDLED_DATASETS[symbol]
        data_dir = self._resolve_data_dir()

        if data_dir.startswith(("http://", "https://")):
            return self._load_from_url(data_dir + filename)
        else:
            return self._load_from_file(Path(data_dir) / filename)

    def load(self, path_or_url: str | Path) -> pd.DataFrame:
        """Load Parquet file from explicit path or URL.

        Use this for custom data files or explicit URL overrides.
        For bundled symbol data, prefer load_symbol().

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
    def list_bundled_symbols() -> list[str]:
        """List symbols available in bundled datasets.

        Returns:
            List of symbol names (e.g., ["BTC-USD", "ETH-USD"])
        """
        return list(BUNDLED_DATASETS.keys())

    @staticmethod
    def list_available_datasets(data_dir: str | Path = "data") -> list[dict]:
        """List available Parquet files in a local data directory.

        Note: This only works for local directories, not HTTP URLs.

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
    """Convenience function to load a Parquet file from path or URL.

    Args:
        path_or_url: Local path or HTTP URL

    Returns:
        DataFrame with UTC timestamp index and OHLCV columns
    """
    return ParquetLoader().load(path_or_url)


def load_symbol(symbol: str) -> pd.DataFrame:
    """Convenience function to load a bundled symbol's data.

    This is the simplest way to load data in a WASM notebook:

        from coinlet.data.parquet import load_symbol
        df = load_symbol("BTC-USD")

    Args:
        symbol: Trading pair (e.g., "BTC-USD", "ETH-USD")

    Returns:
        DataFrame with UTC timestamp index and OHLCV columns
    """
    return ParquetLoader().load_symbol(symbol)
