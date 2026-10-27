"""Coinbase Exchange data sources.

Historical: Public REST API (no auth required)
Live: Public WebSocket feed (no auth required)

API docs: https://docs.cloud.coinbase.com/exchange/reference

Implements the scaffold's `Source` protocol for streaming integration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd

from coinlet.data.interfaces import SeriesReplay
from coinlet.data.types import (
    COINBASE_GRANULARITY_MAP,
    GRANULARITY_SECONDS,
    OHLCV,
    Granularity,
    Tick,
    ohlcv_list_to_dataframe,
)

if TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)

COINBASE_REST_BASE = "https://api.exchange.coinbase.com"
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"
MAX_CANDLES_PER_REQUEST = 300
RATE_LIMIT_DELAY = 0.12  # ~8 requests/sec to stay under public rate limits


class CoinbaseHistorical(SeriesReplay):
    """Coinbase Exchange historical candle data via public REST API.

    Implements the scaffold `Source` protocol by replaying close prices
    after a fetch (or when constructed with symbol/start).

    No authentication required. Respects rate limits with configurable delay.
    Handles pagination for large date ranges (max 300 candles per request).
    """

    source_name = "coinbase"

    def __init__(
        self,
        symbol: str | None = None,
        granularity: Granularity = Granularity.ONE_DAY,
        start: datetime | None = None,
        end: datetime | None = None,
        rate_limit_delay: float = RATE_LIMIT_DELAY,
    ):
        self._symbol = symbol
        self._granularity = granularity
        self._start = start
        self._end = end
        self._delay = rate_limit_delay
        self._session: requests.Session | None = None
        self._replay_series = None

    def _get_session(self) -> "requests.Session":
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": "coinlet/0.1.0",
                "Accept": "application/json",
            })
        return self._session

    def _fetch_page(
        self,
        product: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> list[list]:
        """Fetch a single page of candles (up to 300)."""
        import requests

        session = self._get_session()
        url = f"{COINBASE_REST_BASE}/products/{product}/candles"
        params = {
            "granularity": granularity,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

        for attempt in range(8):
            try:
                resp = session.get(url, params=params, timeout=30)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait}s")
                    time.sleep(wait)
                elif resp.status_code == 404:
                    logger.warning(f"Product {product} not found or no data")
                    return []
                else:
                    logger.warning(f"Request failed: {resp.status_code} {resp.text}")
                    time.sleep(1 + attempt)
            except requests.RequestException as e:
                logger.warning(f"Request error: {e}, retrying...")
                time.sleep(1 + attempt)

        raise RuntimeError(f"Failed to fetch candles after 8 attempts for {product}")

    def fetch_historical(
        self,
        symbol: str,
        granularity: Granularity,
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data with automatic pagination.

        Args:
            symbol: Trading pair (e.g., 'BTC-USD')
            granularity: Candle interval
            start: Start time (UTC)
            end: End time (UTC), defaults to now

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        if end is None:
            end = datetime.now(timezone.utc)

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        granularity_secs = COINBASE_GRANULARITY_MAP[granularity]
        interval_secs = GRANULARITY_SECONDS[granularity]
        max_span_secs = MAX_CANDLES_PER_REQUEST * interval_secs

        all_candles: list[OHLCV] = []
        current_start = start

        while current_start < end:
            from datetime import timedelta
            page_end = min(
                current_start + timedelta(seconds=max_span_secs),
                end
            )

            raw = self._fetch_page(symbol, granularity_secs, current_start, page_end)

            for row in raw:
                ts = datetime.fromtimestamp(row[0], tz=timezone.utc)
                candle = OHLCV(
                    timestamp=ts,
                    open=float(row[3]),
                    high=float(row[2]),
                    low=float(row[1]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
                all_candles.append(candle)

            current_start = page_end
            if current_start < end:
                time.sleep(self._delay)

        df = ohlcv_list_to_dataframe(all_candles)
        if not df.empty:
            self._set_replay_series(df["close"])
        return df

    def _load_replay_series(self) -> pd.Series:
        series = getattr(self, "_replay_series", None)
        if series is not None and not series.empty:
            return series
        if self._symbol is None:
            return super()._load_replay_series()
        start = self._start or datetime(2015, 1, 1, tzinfo=timezone.utc)
        df = self.fetch_historical(self._symbol, self._granularity, start, self._end)
        return df["close"]

    def close(self):
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None


class CoinbaseLive:
    """Coinbase Exchange live WebSocket feed.

    Streams ticker channel for real-time trade data.
    Handles automatic reconnection on connection drops.
    """

    source_name = "coinbase_live"

    def __init__(
        self,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ):
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay

    async def stream_ticks(self, symbols: list[str]) -> AsyncIterator[Tick]:
        """Stream live ticks from Coinbase WebSocket feed.

        Uses the 'ticker' channel which provides last trade info.
        Reconnects automatically on connection drops.

        Args:
            symbols: Trading pairs (e.g., ['BTC-USD', 'ETH-USD'])

        Yields:
            Tick objects for each trade
        """
        import websockets

        delay = self._reconnect_delay

        while True:
            try:
                async with websockets.connect(
                    COINBASE_WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    subscribe_msg = json.dumps({
                        "type": "subscribe",
                        "product_ids": symbols,
                        "channels": ["ticker"],
                    })
                    await ws.send(subscribe_msg)
                    delay = self._reconnect_delay

                    async for raw_msg in ws:
                        msg = json.loads(raw_msg)
                        msg_type = msg.get("type")

                        if msg_type == "ticker":
                            try:
                                tick = Tick(
                                    timestamp=datetime.fromisoformat(
                                        msg["time"].replace("Z", "+00:00")
                                    ),
                                    price=float(msg["price"]),
                                    size=float(msg.get("last_size", 0)),
                                    side=msg.get("side", "buy"),
                                    product_id=msg["product_id"],
                                )
                                yield tick
                            except (KeyError, ValueError) as e:
                                logger.debug(f"Skipping malformed ticker: {e}")

                        elif msg_type == "error":
                            logger.error(f"WebSocket error: {msg}")

                        elif msg_type == "subscriptions":
                            logger.info(f"Subscribed to: {msg.get('channels')}")

            except Exception as e:
                logger.warning(f"WebSocket connection error: {e}, reconnecting in {delay}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_reconnect_delay)

    def stream_ticks_sync(self, symbols: list[str]):
        """Synchronous wrapper for streaming ticks.

        Warning: This blocks the current thread.

        Args:
            symbols: Trading pairs

        Yields:
            Tick objects
        """
        import asyncio

        async def collect():
            async for tick in self.stream_ticks(symbols):
                yield tick

        loop = asyncio.new_event_loop()
        try:
            gen = collect()
            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()


class CoinbaseSource:
    """Coinbase live data source implementing the scaffold's Source protocol.

    This class yields (timestamp, price) tuples for use with StreamBuffer
    and the wavelet transform pipeline.

    Example:
        from coinlet import StreamBuffer
        from coinlet.data import CoinbaseSource

        source = CoinbaseSource("BTC-USD", max_samples=1000)
        buffer = StreamBuffer.from_source(source)
        series = buffer.to_series()
    """

    def __init__(
        self,
        symbol: str,
        max_samples: int | None = None,
        reconnect_delay: float = 1.0,
    ):
        """Initialize Coinbase source.

        Args:
            symbol: Trading pair (e.g., 'BTC-USD')
            max_samples: Maximum samples to yield (None for infinite)
            reconnect_delay: Initial reconnect delay in seconds
        """
        self._symbol = symbol
        self._max_samples = max_samples
        self._live = CoinbaseLive(reconnect_delay=reconnect_delay)
        self._iter: Iterator[tuple[pd.Timestamp, float]] | None = None
        self._count = 0

    def __iter__(self) -> Iterator[tuple[pd.Timestamp, float]]:
        """Return iterator."""
        self._count = 0
        return self

    def __next__(self) -> tuple[pd.Timestamp, float]:
        """Get next (timestamp, price) tuple.

        Returns:
            Tuple of (pandas Timestamp, price as float)

        Raises:
            StopIteration: When max_samples reached
        """
        if self._max_samples is not None and self._count >= self._max_samples:
            raise StopIteration

        if self._iter is None:
            self._iter = self._create_sync_iter()

        tick = next(self._iter)
        self._count += 1
        return pd.Timestamp(tick.timestamp), tick.price

    def _create_sync_iter(self) -> Iterator[Tick]:
        """Create synchronous tick iterator."""
        return self._live.stream_ticks_sync([self._symbol])
