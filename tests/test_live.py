"""Tests for live data handling."""

from datetime import datetime, timezone

import pytest

from coinlet.data.live import BarBuilder, RollingBarWindow
from coinlet.data.types import Granularity, Tick


class TestBarBuilder:
    """Tests for BarBuilder class."""

    def test_single_tick(self):
        """Test adding a single tick."""
        builder = BarBuilder(interval_secs=60)

        tick = Tick(
            timestamp=datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc),
            price=50000.0,
            size=0.1,
            side="buy",
            product_id="BTC-USD",
        )

        result = builder.add_tick(tick)

        assert result is None
        bar = builder.get_current_bar()
        assert bar is not None
        assert bar.open == 50000.0
        assert bar.tick_count == 1

    def test_multiple_ticks_same_interval(self):
        """Test multiple ticks in same interval."""
        builder = BarBuilder(interval_secs=60)

        def ts(m, s):
            return datetime(2024, 1, 1, 12, m, s, tzinfo=timezone.utc)

        ticks = [
            Tick(ts(0, 10), 50000.0, 0.1, "buy", "BTC-USD"),
            Tick(ts(0, 20), 50100.0, 0.2, "buy", "BTC-USD"),
            Tick(ts(0, 30), 49900.0, 0.15, "sell", "BTC-USD"),
            Tick(ts(0, 50), 50050.0, 0.1, "buy", "BTC-USD"),
        ]

        for tick in ticks:
            result = builder.add_tick(tick)
            assert result is None

        bar = builder.get_current_bar()
        assert bar.open == 50000.0
        assert bar.high == 50100.0
        assert bar.low == 49900.0
        assert bar.close == 50050.0
        assert bar.tick_count == 4
        assert bar.volume == pytest.approx(0.55)

    def test_bar_completion(self):
        """Test bar completion on new interval."""
        builder = BarBuilder(interval_secs=60)

        ts1 = datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        tick1 = Tick(ts1, 50000.0, 0.1, "buy", "BTC-USD")
        builder.add_tick(tick1)

        ts2 = datetime(2024, 1, 1, 12, 1, 10, tzinfo=timezone.utc)
        tick2 = Tick(ts2, 50100.0, 0.2, "buy", "BTC-USD")
        completed = builder.add_tick(tick2)

        assert completed is not None
        assert completed.timestamp == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert completed.close == 50000.0
        assert completed.tick_count == 1

        current = builder.get_current_bar()
        assert current.timestamp == datetime(2024, 1, 1, 12, 1, 0, tzinfo=timezone.utc)
        assert current.close == 50100.0

    def test_flush(self):
        """Test flushing incomplete bar."""
        builder = BarBuilder(interval_secs=60)

        ts = datetime(2024, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        tick = Tick(ts, 50000.0, 0.1, "buy", "BTC-USD")
        builder.add_tick(tick)

        flushed = builder.flush()

        assert flushed is not None
        assert flushed.close == 50000.0
        assert builder.get_current_bar() is None


class TestRollingBarWindow:
    """Tests for RollingBarWindow class."""

    def test_add_ticks_build_bars(self):
        """Test building bars from ticks."""
        window = RollingBarWindow(granularity=Granularity.ONE_MINUTE, max_bars=10)

        for i in range(5):
            for j in range(3):
                tick = Tick(
                    timestamp=datetime(2024, 1, 1, 12, i, j * 20, tzinfo=timezone.utc),
                    price=50000.0 + i * 100 + j,
                    size=0.1,
                    side="buy",
                    product_id="BTC-USD",
                )
                window.add_tick(tick)

        tick_next = Tick(
            timestamp=datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
            price=50500.0,
            size=0.1,
            side="buy",
            product_id="BTC-USD",
        )
        window.add_tick(tick_next)

        assert window.bar_count == 5

    def test_get_snapshot(self):
        """Test getting DataFrame snapshot."""
        window = RollingBarWindow(granularity=Granularity.ONE_MINUTE, max_bars=10)

        for i in range(3):
            tick = Tick(
                timestamp=datetime(2024, 1, 1, 12, i, 30, tzinfo=timezone.utc),
                price=50000.0 + i * 100,
                size=0.1,
                side="buy",
                product_id="BTC-USD",
            )
            window.add_tick(tick)

        tick_final = Tick(
            timestamp=datetime(2024, 1, 1, 12, 3, 0, tzinfo=timezone.utc),
            price=50300.0,
            size=0.1,
            side="buy",
            product_id="BTC-USD",
        )
        window.add_tick(tick_final)

        df = window.get_snapshot()

        assert len(df) == 3
        assert "open" in df.columns
        assert "close" in df.columns
        assert df.index.tzinfo is not None

    def test_max_bars_limit(self):
        """Test that window respects max_bars limit."""
        window = RollingBarWindow(granularity=Granularity.ONE_MINUTE, max_bars=5)

        for i in range(10):
            tick = Tick(
                timestamp=datetime(2024, 1, 1, 12, i, 30, tzinfo=timezone.utc),
                price=50000.0,
                size=0.1,
                side="buy",
                product_id="BTC-USD",
            )
            window.add_tick(tick)

        tick_final = Tick(
            timestamp=datetime(2024, 1, 1, 12, 10, 0, tzinfo=timezone.utc),
            price=50000.0,
            size=0.1,
            side="buy",
            product_id="BTC-USD",
        )
        window.add_tick(tick_final)

        assert window.bar_count == 5


class TestLiveDataManagerBuffer:
    """StreamBuffer integration for the per-tick live mode."""

    def test_tick_buffer_starts_empty(self):
        from coinlet.data.live import LiveDataManager

        manager = LiveDataManager(
            source=None,
            symbols=["BTC-USD"],
            granularity=Granularity.ONE_MINUTE,
        )
        buffer = manager.get_tick_buffer("BTC-USD")
        assert len(buffer) == 0
        assert len(manager.get_tick_series("BTC-USD")) == 0
