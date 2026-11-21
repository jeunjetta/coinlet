"""Live data handling: tick aggregation, rolling windows, and update hooks.

Supports two modes for the plotting toggle:
1. Per-tick/bar update hook: Call a callback on each new tick or completed bar
2. Rolling-window snapshot: Maintain a fixed-size window of recent bars
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd

from coinlet.data.interfaces import StreamBuffer
from coinlet.data.types import (
    GRANULARITY_SECONDS,
    Bar,
    Granularity,
    Tick,
)

if TYPE_CHECKING:
    from coinlet.data.coinbase import CoinbaseLive

logger = logging.getLogger(__name__)


@dataclass
class BarBuilder:
    """Aggregates ticks into a single bar."""

    interval_secs: int
    current_bar_start: datetime | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float = 0.0
    tick_count: int = 0

    def _bar_start_for(self, ts: datetime) -> datetime:
        """Calculate the bar start time for a given timestamp."""
        epoch = ts.timestamp()
        bar_epoch = (int(epoch) // self.interval_secs) * self.interval_secs
        return datetime.fromtimestamp(bar_epoch, tz=UTC)

    def add_tick(self, tick: Tick) -> Bar | None:
        """Add a tick and return completed bar if interval elapsed.

        Args:
            tick: Incoming tick

        Returns:
            Completed Bar if the interval has elapsed, None otherwise.
        """
        bar_start = self._bar_start_for(tick.timestamp)

        if self.current_bar_start is None:
            self.current_bar_start = bar_start
            self.open = tick.price
            self.high = tick.price
            self.low = tick.price
            self.close = tick.price
            self.volume = tick.size
            self.tick_count = 1
            return None

        if bar_start > self.current_bar_start:
            completed = Bar(
                timestamp=self.current_bar_start,
                open=self.open,
                high=self.high,
                low=self.low,
                close=self.close,
                volume=self.volume,
                tick_count=self.tick_count,
            )

            self.current_bar_start = bar_start
            self.open = tick.price
            self.high = tick.price
            self.low = tick.price
            self.close = tick.price
            self.volume = tick.size
            self.tick_count = 1

            return completed

        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.size
        self.tick_count += 1
        return None

    def get_current_bar(self) -> Bar | None:
        """Get the current incomplete bar."""
        if self.current_bar_start is None:
            return None
        return Bar(
            timestamp=self.current_bar_start,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            tick_count=self.tick_count,
        )

    def flush(self) -> Bar | None:
        """Force completion of current bar regardless of time."""
        bar = self.get_current_bar()
        self.current_bar_start = None
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = 0.0
        self.tick_count = 0
        return bar


@dataclass
class RollingBarWindow:
    """Maintains a rolling window of fixed-interval bars.

    Use this for the plotting toggle's "re-run on rolling window" mode.
    The window can be exported as a DataFrame for wavelet analysis.
    """

    granularity: Granularity
    max_bars: int
    _bars: deque[Bar] = field(default_factory=deque)
    _builder: BarBuilder = field(init=False)

    def __post_init__(self):
        interval_secs = GRANULARITY_SECONDS[self.granularity]
        self._builder = BarBuilder(interval_secs=interval_secs)
        self._bars = deque(maxlen=self.max_bars)

    def add_tick(self, tick: Tick) -> Bar | None:
        """Add a tick and return newly completed bar if any.

        Args:
            tick: Incoming tick

        Returns:
            Completed Bar if one was finalized, None otherwise
        """
        completed = self._builder.add_tick(tick)
        if completed:
            self._bars.append(completed)
        return completed

    def get_snapshot(self) -> pd.DataFrame:
        """Get current window as DataFrame.

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns,
            ready for wavelet analysis.
        """
        if not self._bars:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        data = []
        for bar in self._bars:
            data.append(
                {
                    "timestamp": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        return df

    def get_current_bar(self) -> Bar | None:
        """Get the currently building (incomplete) bar."""
        return self._builder.get_current_bar()

    @property
    def bar_count(self) -> int:
        """Number of completed bars in the window."""
        return len(self._bars)


TickCallback = Callable[[Tick], None]
BarCallback = Callable[[Bar], None]


class LiveDataManager:
    """Manages live data streams with callbacks and rolling windows.

    Supports two modes for the plotting toggle:
    1. Continuous live updating: register tick/bar callbacks
    2. Rolling window snapshot: get_snapshot() returns recent bars

    Example:
        manager = LiveDataManager(
            source=CoinbaseLive(),
            symbols=["BTC-USD"],
            granularity=Granularity.ONE_MINUTE,
            window_size=100,
        )

        # Mode 1: Continuous updates
        manager.on_bar(lambda bar: update_plot(bar))

        # Mode 2: Rolling window (call periodically)
        df = manager.get_snapshot()
        run_wavelet_analysis(df)
    """

    def __init__(
        self,
        source: CoinbaseLive,
        symbols: list[str],
        granularity: Granularity,
        window_size: int = 100,
    ):
        """Initialize live data manager.

        Args:
            source: Live data source (e.g., CoinbaseLive)
            symbols: Trading pairs to subscribe to
            granularity: Bar interval for aggregation
            window_size: Max bars to keep in rolling window
        """
        self._source = source
        self._symbols = symbols
        self._granularity = granularity

        self._windows: dict[str, RollingBarWindow] = {
            sym: RollingBarWindow(granularity=granularity, max_bars=window_size) for sym in symbols
        }
        self._tick_buffers: dict[str, StreamBuffer] = {sym: StreamBuffer() for sym in symbols}

        self._tick_callbacks: list[TickCallback] = []
        self._bar_callbacks: list[BarCallback] = []
        self._running = False

    def on_tick(self, callback: TickCallback) -> None:
        """Register callback for each incoming tick.

        Args:
            callback: Function called with each Tick
        """
        self._tick_callbacks.append(callback)

    def on_bar(self, callback: BarCallback) -> None:
        """Register callback for each completed bar.

        Args:
            callback: Function called with each completed Bar
        """
        self._bar_callbacks.append(callback)

    def get_snapshot(self, symbol: str | None = None) -> pd.DataFrame:
        """Get rolling window snapshot as DataFrame.

        Args:
            symbol: Specific symbol, or None for first symbol

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        if symbol is None:
            symbol = self._symbols[0] if self._symbols else None
        if symbol is None or symbol not in self._windows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        return self._windows[symbol].get_snapshot()

    def get_all_snapshots(self) -> dict[str, pd.DataFrame]:
        """Get snapshots for all symbols.

        Returns:
            Dict mapping symbol to DataFrame
        """
        return {sym: win.get_snapshot() for sym, win in self._windows.items()}

    def get_tick_buffer(self, symbol: str | None = None) -> StreamBuffer:
        """Return the StreamBuffer of raw ticks for a symbol.

        This is the per-tick rolling window used with the scaffold Source
        protocol (`buffer.to_series()` feeds `cwt()`).
        """
        if symbol is None:
            symbol = self._symbols[0] if self._symbols else None
        if symbol is None or symbol not in self._tick_buffers:
            return StreamBuffer()
        return self._tick_buffers[symbol]

    def get_tick_series(self, symbol: str | None = None) -> pd.Series:
        """Return accumulated tick prices as a Series for wavelet analysis."""
        return self.get_tick_buffer(symbol).to_series()

    async def run(self) -> None:
        """Start streaming and processing ticks.

        Runs until cancelled. Handles reconnection automatically.
        """
        self._running = True

        async for tick in self._source.stream_ticks(self._symbols):
            if not self._running:
                break

            for cb in self._tick_callbacks:
                try:
                    cb(tick)
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")

            if tick.product_id in self._tick_buffers:
                self._tick_buffers[tick.product_id].add(pd.Timestamp(tick.timestamp), tick.price)

            if tick.product_id in self._windows:
                completed = self._windows[tick.product_id].add_tick(tick)
                if completed:
                    for cb in self._bar_callbacks:
                        try:
                            cb(completed)
                        except Exception as e:
                            logger.error(f"Bar callback error: {e}")

    def stop(self) -> None:
        """Stop the live data stream."""
        self._running = False
