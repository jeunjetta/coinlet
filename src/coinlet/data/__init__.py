"""Data layer for coinlet: sources, caching, and live streaming.

This module is designed to degrade gracefully in WASM/Pyodide environments:
- Core types and Parquet reading work everywhere
- Heavy deps (duckdb, websockets, yfinance) are optional imports
- Use `coinlet.data.parquet` for browser-compatible Parquet reading over HTTP
"""

from coinlet.data.protocol import LiveSource, PriceSource
from coinlet.data.types import GRANULARITY_SECONDS, OHLCV, Bar, Granularity, Tick

__all__ = [
    # Core types (always available)
    "OHLCV",
    "Tick",
    "Bar",
    "Granularity",
    "GRANULARITY_SECONDS",
    # Protocols
    "PriceSource",
    "LiveSource",
]


def _lazy_import(name: str):
    """Lazy import for optional heavy dependencies."""
    if name == "CoinbaseHistorical":
        from coinlet.data.coinbase import CoinbaseHistorical
        return CoinbaseHistorical
    elif name == "CoinbaseLive":
        from coinlet.data.coinbase import CoinbaseLive
        return CoinbaseLive
    elif name == "YahooFinanceSource":
        from coinlet.data.yahoo import YahooFinanceSource
        return YahooFinanceSource
    elif name == "CSVSource":
        from coinlet.data.csv_source import CSVSource
        return CSVSource
    elif name == "PriceCache":
        from coinlet.data.cache import PriceCache
        return PriceCache
    elif name == "RollingBarWindow":
        from coinlet.data.live import RollingBarWindow
        return RollingBarWindow
    elif name == "LiveDataManager":
        from coinlet.data.live import LiveDataManager
        return LiveDataManager
    elif name == "ParquetLoader":
        from coinlet.data.parquet import ParquetLoader
        return ParquetLoader
    raise AttributeError(f"module 'coinlet.data' has no attribute {name!r}")


def __getattr__(name: str):
    """Enable lazy imports for optional components."""
    try:
        return _lazy_import(name)
    except ImportError as e:
        raise ImportError(
            f"Cannot import {name}: {e}. "
            "This component requires optional dependencies. "
            "Install with: uv pip install coinlet[full]"
        ) from e
