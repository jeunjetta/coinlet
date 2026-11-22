"""Explorer live-mode session: cached Parquet + public Coinbase feeds.

Wires the marimo explorer's live toggle to Coinbase public market data only
(no API keys). Supports:

- **per_tick**: WebSocket ticker updates; each new price appends to history
- **rolling**: periodic REST candle refresh over a trailing window, then CWT

WASM / no-network environments fall back to cached data with a visible status.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from coinlet.data.types import Granularity, Tick

if TYPE_CHECKING:
    from coinlet.data.coinbase import CoinbaseHistorical, CoinbaseLive

logger = logging.getLogger(__name__)

CapabilityCheck = Callable[[], tuple[bool, str]]

_PRODUCT_FROM_NAME = re.compile(
    r"(?:coinbase_)?([A-Z0-9]+)_([A-Z0-9]+)(?:_|\.|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LiveStatus:
    """User-visible live-mode status for the explorer UI."""

    mode: str
    state: str
    message: str
    tick_count: int = 0
    last_price: float | None = None
    last_timestamp: pd.Timestamp | None = None
    analysis_points: int = 0


def live_runtime_supported() -> tuple[bool, str]:
    """Return whether live feeds can run in this process.

    The static marimo WASM / Pyodide build cannot open WebSockets or reliably
    call the Coinbase REST API; callers must keep using cached Parquet.
    """
    if sys.platform == "emscripten":
        return (
            False,
            "Live mode is unavailable in the static WASM build; using cached Parquet only.",
        )
    try:
        import requests  # noqa: F401
        import websockets  # noqa: F401
    except ImportError as exc:
        return False, f"Live mode requires optional dependencies: {exc}"
    return True, ""


def infer_product_id(data_path: str | Path | None, default: str = "BTC-USD") -> str:
    """Infer a Coinbase product id from a cached filename when possible."""
    if data_path is None:
        return default
    name = Path(data_path).name
    match = _PRODUCT_FROM_NAME.search(name.replace("-", "_"))
    if not match:
        return default
    base, quote = match.group(1).upper(), match.group(2).upper()
    if base in {"COINBASE", "DEMO"} or quote in {"CSV", "PARQUET"}:
        return default
    return f"{base}-{quote}"


def _as_utc_timestamp(value: datetime | pd.Timestamp) -> pd.Timestamp:
    """Normalize a datetime-like value to a UTC pandas Timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def merge_cached_and_live(cached: pd.Series, live: pd.Series) -> pd.Series:
    """Append live prices that are strictly newer than the cached history.

    Preserves cached points so switching into live mode does not reset the plot.
    """
    if cached is None or len(cached) == 0:
        return live.copy() if live is not None else pd.Series(dtype=float)
    if live is None or len(live) == 0:
        return cached.copy()

    cached_idx = pd.DatetimeIndex(pd.to_datetime(cached.index, utc=True))
    live_idx = pd.DatetimeIndex(pd.to_datetime(live.index, utc=True))
    cached = pd.Series(cached.to_numpy(dtype=float), index=cached_idx).sort_index()
    live = pd.Series(live.to_numpy(dtype=float), index=live_idx).sort_index()

    cutoff = cached.index[-1]
    newer = live[live.index > cutoff]
    if newer.empty:
        return cached.copy()

    merged = pd.concat([cached, newer])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return merged


class LiveExplorerSession:
    """Thread-safe session bridging cached history with public Coinbase feeds.

    Designed for marimo: call :meth:`set_mode`, then :meth:`poll` from a
    ``mo.ui.refresh`` cell. Network failures set ``state='fallback'`` and
    return cached / last-known data instead of raising.
    """

    def __init__(
        self,
        cached_series: pd.Series,
        product_id: str = "BTC-USD",
        granularity: Granularity = Granularity.ONE_DAY,
        window_size: int = 256,
        *,
        capability_check: CapabilityCheck | None = None,
        live_source: CoinbaseLive | None = None,
        historical_source: CoinbaseHistorical | None = None,
        reconnect_delay: float = 1.0,
    ) -> None:
        if not isinstance(cached_series.index, pd.DatetimeIndex):
            cached_series = cached_series.copy()
            cached_series.index = pd.to_datetime(cached_series.index, utc=True)
        else:
            cached_series = cached_series.copy()
            if cached_series.index.tz is None:
                cached_series.index = cached_series.index.tz_localize("UTC")
            else:
                cached_series.index = cached_series.index.tz_convert("UTC")

        self._cached = cached_series.sort_index()
        self._series = self._cached.copy()
        self._product_id = product_id
        self._granularity = granularity
        self._window_size = max(2, int(window_size))
        self._capability_check = capability_check or live_runtime_supported
        self._live_source = live_source
        self._historical_source = historical_source
        self._reconnect_delay = reconnect_delay

        self._mode = "off"
        self._state = "idle"
        self._message = "Using cached data"
        self._tick_count = 0
        self._last_price: float | None = float(self._cached.iloc[-1]) if len(self._cached) else None
        self._last_timestamp: pd.Timestamp | None = (
            pd.Timestamp(self._cached.index[-1]) if len(self._cached) else None
        )

        self._lock = threading.RLock()
        self._pending_ticks: list[Tick] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def mode(self) -> str:
        return self._mode

    def full_series(self) -> pd.Series:
        """Return the full merged series (not window-truncated)."""
        with self._lock:
            return self._series.copy()

    def status(self) -> LiveStatus:
        with self._lock:
            analysis = self._analysis_series_unlocked()
            return LiveStatus(
                mode=self._mode,
                state=self._state,
                message=self._message,
                tick_count=self._tick_count,
                last_price=self._last_price,
                last_timestamp=self._last_timestamp,
                analysis_points=len(analysis),
            )

    def set_mode(self, mode: str) -> LiveStatus:
        """Switch live mode. Unknown modes are treated as ``off``."""
        mode = mode if mode in {"off", "per_tick", "rolling"} else "off"
        if mode == "off":
            self.stop()
            return self.status()

        ok, reason = self._capability_check()
        if not ok:
            with self._lock:
                self._mode = mode
                self._state = "unsupported"
                self._message = reason
            return self.status()

        with self._lock:
            self._mode = mode
            self._state = "connecting"
            self._message = (
                "Connecting to Coinbase public WebSocket…"
                if mode == "per_tick"
                else "Fetching public Coinbase candles…"
            )

        if mode == "per_tick":
            self._ensure_ws_thread()
        else:
            self._stop_ws_thread()

        return self.status()

    def stop(self) -> None:
        """Stop live feeds and return to cached-only idle state.

        Appended live points remain in ``full_series()`` so re-enabling live
        mode continues smoothly from the extended history.
        """
        self._stop_ws_thread()
        with self._lock:
            self._mode = "off"
            self._state = "idle"
            self._message = "Using cached data"
            self._pending_ticks.clear()

    def ingest_tick(self, tick: Tick) -> None:
        """Inject a tick (used by the WS thread and by unit tests)."""
        if tick.product_id and tick.product_id != self._product_id:
            return
        with self._lock:
            self._pending_ticks.append(tick)

    def poll(self) -> tuple[pd.Series, LiveStatus]:
        """Apply pending updates and return the analysis series + status.

        Never raises for network errors; falls back to cached / last-known data.
        """
        with self._lock:
            mode = self._mode

        if mode == "off":
            with self._lock:
                self._state = "idle"
                self._message = "Using cached data"
            return self._cached.copy(), self.status()

        ok, reason = self._capability_check()
        if not ok:
            with self._lock:
                self._state = "unsupported"
                self._message = reason
            return self._analysis_from_series(self._series), self.status()

        if mode == "per_tick":
            self._drain_ticks()
            self._ensure_ws_thread()
        elif mode == "rolling":
            self._poll_rolling_candles()

        return self._analysis_from_series(self._series), self.status()

    def _analysis_from_series(self, series: pd.Series) -> pd.Series:
        with self._lock:
            mode = self._mode
            window = self._window_size
        if mode == "rolling" and len(series) > window:
            return series.iloc[-window:].copy()
        if mode == "per_tick" and len(series) > window * 4:
            # Keep a generous trailing window so CWT stays responsive
            return series.iloc[-(window * 4) :].copy()
        return series.copy()

    def _analysis_series_unlocked(self) -> pd.Series:
        series = self._series
        if self._mode == "rolling" and len(series) > self._window_size:
            return series.iloc[-self._window_size :]
        if self._mode == "per_tick" and len(series) > self._window_size * 4:
            return series.iloc[-(self._window_size * 4) :]
        return series

    def _drain_ticks(self) -> None:
        with self._lock:
            ticks = list(self._pending_ticks)
            self._pending_ticks.clear()

        if not ticks:
            with self._lock:
                if self._mode == "per_tick" and self._state in {
                    "connecting",
                    "reconnecting",
                }:
                    # Still waiting for first tick
                    pass
                elif self._mode == "per_tick" and self._state != "fallback":
                    if self._tick_count > 0:
                        self._state = "live"
                        self._message = (
                            f"Live per-tick ({self._product_id}): {self._tick_count} updates"
                        )
            return

        live_idx = [_as_utc_timestamp(t.timestamp) for t in ticks]
        live = pd.Series([float(t.price) for t in ticks], index=pd.DatetimeIndex(live_idx))
        with self._lock:
            self._series = merge_cached_and_live(self._series, live)
            self._tick_count += len(ticks)
            self._last_price = float(ticks[-1].price)
            self._last_timestamp = _as_utc_timestamp(ticks[-1].timestamp)
            self._state = "live"
            self._message = (
                f"Live per-tick ({self._product_id}): {self._tick_count} updates, "
                f"last={self._last_price:.2f}"
            )

    def _poll_rolling_candles(self) -> None:
        try:
            candles = self._fetch_recent_candles()
        except Exception as exc:
            logger.warning("Rolling candle fetch failed: %s", exc)
            with self._lock:
                self._state = "fallback"
                self._message = f"Live feed unavailable ({exc}); using cached data"
            return

        if candles is None or candles.empty:
            with self._lock:
                if self._state != "fallback":
                    self._state = "live"
                    self._message = (
                        f"Rolling window ({self._product_id}): "
                        f"no new candles yet; showing cached tail"
                    )
            return

        closes = candles["close"] if "close" in candles.columns else candles.iloc[:, 0]
        closes = pd.Series(
            closes.to_numpy(dtype=float),
            index=pd.DatetimeIndex(pd.to_datetime(closes.index, utc=True)),
        )
        with self._lock:
            self._series = merge_cached_and_live(self._series, closes)
            self._last_price = float(self._series.iloc[-1])
            self._last_timestamp = pd.Timestamp(self._series.index[-1])
            self._state = "live"
            self._message = (
                f"Rolling window ({self._product_id}): "
                f"{min(len(self._series), self._window_size)} bars, "
                f"last={self._last_price:.2f}"
            )

    def _fetch_recent_candles(self) -> pd.DataFrame:
        """Fetch recent public candles; overridable in tests."""
        from coinlet.data.coinbase import CoinbaseHistorical

        source = self._historical_source
        if source is None:
            source = CoinbaseHistorical(rate_limit_delay=0.12)

        with self._lock:
            end = datetime.now(tz=UTC)
            if len(self._series):
                start = self._series.index[-1].to_pydatetime() - timedelta(days=1)
            else:
                start = end - timedelta(days=max(7, self._window_size))
            granularity = self._granularity
            product = self._product_id

        return source.fetch_historical(product, granularity, start, end)

    def _ensure_ws_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._ws_thread_main,
            name=f"coinlet-live-{self._product_id}",
            daemon=True,
        )
        self._thread.start()

    def _stop_ws_thread(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _ws_thread_main(self) -> None:
        try:
            asyncio.run(self._consume_ticks())
        except Exception as exc:
            logger.warning("Live WebSocket thread exited: %s", exc)
            with self._lock:
                if self._mode == "per_tick":
                    self._state = "fallback"
                    self._message = f"WebSocket error ({exc}); using cached data"

    async def _consume_ticks(self) -> None:
        from coinlet.data.coinbase import CoinbaseLive

        source: Any = self._live_source
        if source is None:
            source = CoinbaseLive(reconnect_delay=self._reconnect_delay)

        with self._lock:
            self._state = "connecting"
            self._message = f"Connecting to Coinbase ticker ({self._product_id})…"

        try:
            async for tick in source.stream_ticks([self._product_id]):
                if self._stop_event.is_set():
                    break
                self.ingest_tick(tick)
        except Exception as exc:
            logger.warning("Tick stream error: %s", exc)
            with self._lock:
                if self._mode == "per_tick":
                    self._state = "reconnecting" if not self._stop_event.is_set() else "fallback"
                    self._message = f"Disconnected ({exc}); will retry or use cache"
