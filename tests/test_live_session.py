"""Tests for explorer live-session helpers (network mocked)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from coinlet.data.live_session import (
    LiveExplorerSession,
    LiveStatus,
    infer_product_id,
    live_runtime_supported,
    merge_cached_and_live,
)
from coinlet.data.types import Tick


@pytest.fixture
def cached_series() -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    return pd.Series(range(100, 110), index=idx, dtype=float)


class TestMergeCachedAndLive:
    def test_appends_newer_points_only(self, cached_series: pd.Series) -> None:
        live_idx = pd.DatetimeIndex(
            [
                cached_series.index[-1],
                cached_series.index[-1] + pd.Timedelta(days=1),
                cached_series.index[-1] + pd.Timedelta(days=2),
            ],
            tz="UTC",
        )
        live = pd.Series([999.0, 200.0, 201.0], index=live_idx)

        merged = merge_cached_and_live(cached_series, live)

        assert len(merged) == len(cached_series) + 2
        assert merged.iloc[-1] == 201.0
        assert merged.iloc[-2] == 200.0
        # Cached tail unchanged (no jarring reset / overwrite)
        assert merged.iloc[-3] == cached_series.iloc[-1]

    def test_empty_live_returns_cached_copy(self, cached_series: pd.Series) -> None:
        merged = merge_cached_and_live(cached_series, pd.Series(dtype=float))
        assert merged.equals(cached_series)
        assert merged is not cached_series

    def test_empty_cached_returns_live(self) -> None:
        live = pd.Series(
            [1.0, 2.0],
            index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
        )
        merged = merge_cached_and_live(pd.Series(dtype=float), live)
        assert merged.equals(live)


class TestInferProductId:
    def test_from_coinbase_parquet_name(self) -> None:
        assert infer_product_id("data/coinbase_BTC_USD_1d.parquet") == "BTC-USD"
        assert infer_product_id("coinbase_ETH_USD_1h.parquet") == "ETH-USD"

    def test_default_when_unknown(self) -> None:
        assert infer_product_id("demo_prices.csv") == "BTC-USD"
        assert infer_product_id(None, default="ETH-USD") == "ETH-USD"


class TestLiveRuntimeSupported:
    def test_wasm_unsupported(self) -> None:
        with patch("coinlet.data.live_session.sys.platform", "emscripten"):
            ok, reason = live_runtime_supported()
        assert ok is False
        assert "WASM" in reason or "wasm" in reason.lower() or "static" in reason.lower()

    def test_normal_runtime_supported(self) -> None:
        with patch("coinlet.data.live_session.sys.platform", "linux"):
            ok, reason = live_runtime_supported()
        assert ok is True
        assert reason == ""


class TestLiveExplorerSession:
    def test_off_mode_returns_cached(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
        )
        series, status = session.poll()
        assert series.equals(cached_series)
        assert status.mode == "off"
        assert status.state == "idle"

    def test_unsupported_runtime_falls_back(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            capability_check=lambda: (False, "no network"),
        )
        session.set_mode("per_tick")
        series, status = session.poll()
        assert series.equals(cached_series)
        assert status.state == "unsupported"
        assert "no network" in status.message

    def test_per_tick_appends_without_reset(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            capability_check=lambda: (True, ""),
        )
        session.set_mode("per_tick")

        tick_ts = cached_series.index[-1] + pd.Timedelta(hours=1)
        session.ingest_tick(
            Tick(
                timestamp=tick_ts.to_pydatetime(),
                price=12345.0,
                size=0.01,
                side="buy",
                product_id="BTC-USD",
            )
        )

        series, status = session.poll()
        assert len(series) == len(cached_series) + 1
        assert series.iloc[-1] == 12345.0
        assert series.iloc[0] == cached_series.iloc[0]
        assert status.state == "live"
        assert status.mode == "per_tick"
        assert status.last_price == 12345.0
        assert status.tick_count == 1

    def test_rolling_window_uses_trailing_slice(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            window_size=5,
            capability_check=lambda: (True, ""),
        )
        session.set_mode("rolling")

        # Inject a successful candle fetch
        new_idx = pd.date_range(
            cached_series.index[-1] + pd.Timedelta(days=1),
            periods=2,
            freq="D",
            tz="UTC",
        )
        candles = pd.DataFrame(
            {
                "open": [110.0, 111.0],
                "high": [111.0, 112.0],
                "low": [109.0, 110.0],
                "close": [110.5, 111.5],
                "volume": [1.0, 1.0],
            },
            index=new_idx,
        )
        session._fetch_recent_candles = MagicMock(return_value=candles)

        series, status = session.poll()
        assert status.mode == "rolling"
        assert status.state == "live"
        assert len(series) == 5  # rolling window
        assert series.iloc[-1] == 111.5
        # Full history still retained for smooth resume
        assert len(session.full_series()) == len(cached_series) + 2

    def test_rolling_fetch_failure_falls_back(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            window_size=5,
            capability_check=lambda: (True, ""),
        )
        session.set_mode("rolling")
        session._fetch_recent_candles = MagicMock(side_effect=ConnectionError("rate limited"))

        series, status = session.poll()
        assert status.state == "fallback"
        assert "rate limited" in status.message.lower() or "rate" in status.message.lower()
        assert len(series) == 5
        assert series.iloc[-1] == cached_series.iloc[-1]

    def test_stop_resets_to_idle(self, cached_series: pd.Series) -> None:
        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            capability_check=lambda: (True, ""),
        )
        session.set_mode("per_tick")
        session.stop()
        series, status = session.poll()
        assert status.mode == "off"
        assert status.state == "idle"
        assert series.equals(cached_series)

    def test_status_dataclass_fields(self) -> None:
        status = LiveStatus(
            mode="per_tick",
            state="live",
            message="ok",
            tick_count=3,
            last_price=1.0,
            last_timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
            analysis_points=10,
        )
        assert status.tick_count == 3


class TestLiveExplorerSessionThreading:
    def test_start_ws_thread_ingests_mock_ticks(self, cached_series: pd.Series) -> None:
        """Mock CoinbaseLive stream yields ticks; session merges them."""

        async def fake_stream(symbols: list[str]):
            base = cached_series.index[-1].to_pydatetime()
            for i in range(3):
                yield Tick(
                    timestamp=base + timedelta(minutes=i + 1),
                    price=50000.0 + i,
                    size=0.1,
                    side="buy",
                    product_id=symbols[0],
                )

        mock_live = MagicMock()
        mock_live.stream_ticks = fake_stream

        session = LiveExplorerSession(
            cached_series=cached_series,
            product_id="BTC-USD",
            capability_check=lambda: (True, ""),
            live_source=mock_live,
        )
        session.set_mode("per_tick")
        # Allow background consumer to drain the short stream
        import time

        deadline = time.time() + 2.0
        while time.time() < deadline:
            series, status = session.poll()
            if status.tick_count >= 3:
                break
            time.sleep(0.05)

        series, status = session.poll()
        session.stop()

        assert status.tick_count >= 3
        assert len(series) >= len(cached_series) + 3
        assert series.iloc[-1] == 50002.0
