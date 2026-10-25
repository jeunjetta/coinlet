"""Protocol definitions for data sources.

These protocols define the interface that all data sources must implement,
allowing generic code to work with any source (crypto exchanges, CSV files,
future PMU data, etc.).
"""

from abc import abstractmethod
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd

from coinlet.data.types import Bar, Granularity, Tick


@runtime_checkable
class PriceSource(Protocol):
    """Protocol for historical price data sources.

    Implementations must provide:
    - fetch_historical: Retrieve OHLCV data for a date range
    - source_name: Identifier for caching and display

    The returned DataFrame must have:
    - UTC DatetimeIndex named 'timestamp'
    - Columns: open, high, low, close, volume
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source (e.g., 'coinbase', 'yahoo')."""
        ...

    @abstractmethod
    def fetch_historical(
        self,
        symbol: str,
        granularity: Granularity,
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data.

        Args:
            symbol: Trading pair or ticker (e.g., 'BTC-USD')
            granularity: Candle interval
            start: Start time (UTC)
            end: End time (UTC), defaults to now

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns.
            Empty DataFrame if no data available.
        """
        ...


@runtime_checkable
class LiveSource(Protocol):
    """Protocol for live price data sources.

    Implementations provide real-time tick or trade data via async iteration.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        ...

    @abstractmethod
    def stream_ticks(self, symbols: list[str]) -> AsyncIterator[Tick]:
        """Stream live ticks for the given symbols.

        Args:
            symbols: List of trading pairs (e.g., ['BTC-USD', 'ETH-USD'])

        Yields:
            Tick objects as they arrive from the exchange.
            Should handle reconnection internally on connection drops.
        """
        ...


class SyncLiveSource(Protocol):
    """Synchronous live source for simpler use cases."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source."""
        ...

    @abstractmethod
    def stream_ticks_sync(self, symbols: list[str]) -> Iterator[Tick]:
        """Stream live ticks synchronously.

        Args:
            symbols: List of trading pairs

        Yields:
            Tick objects. Blocks until next tick arrives.
        """
        ...


class BarAggregator(Protocol):
    """Protocol for aggregating ticks into bars."""

    @abstractmethod
    def add_tick(self, tick: Tick) -> Bar | None:
        """Add a tick and return completed bar if interval elapsed.

        Args:
            tick: Incoming tick

        Returns:
            Completed Bar if the interval has elapsed, None otherwise.
        """
        ...

    @abstractmethod
    def get_current_bar(self) -> Bar | None:
        """Get the current incomplete bar.

        Returns:
            Current bar being built, or None if no ticks received yet.
        """
        ...

    @abstractmethod
    def flush(self) -> Bar | None:
        """Force completion of current bar regardless of time.

        Returns:
            The current bar if any ticks were aggregated, None otherwise.
        """
        ...
