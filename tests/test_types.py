"""Tests for data types."""

from datetime import datetime, timezone

from coinlet.data.types import (
    OHLCV,
    Bar,
    Granularity,
    Tick,
    dataframe_to_ohlcv_list,
    ohlcv_list_to_dataframe,
)


def test_ohlcv_creation():
    """Test OHLCV dataclass creation."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candle = OHLCV(
        timestamp=ts,
        open=100.0,
        high=105.0,
        low=99.0,
        close=103.0,
        volume=1000.0,
    )

    assert candle.timestamp == ts
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 99.0
    assert candle.close == 103.0
    assert candle.volume == 1000.0


def test_ohlcv_to_dict():
    """Test OHLCV to_dict method."""
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candle = OHLCV(ts, 100.0, 105.0, 99.0, 103.0, 1000.0)

    d = candle.to_dict()
    assert d["timestamp"] == ts
    assert d["close"] == 103.0


def test_tick_creation():
    """Test Tick dataclass creation."""
    ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    tick = Tick(
        timestamp=ts,
        price=50000.0,
        size=0.01,
        side="buy",
        product_id="BTC-USD",
    )

    assert tick.timestamp == ts
    assert tick.price == 50000.0
    assert tick.side == "buy"


def test_bar_creation():
    """Test Bar dataclass creation."""
    ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    bar = Bar(
        timestamp=ts,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.5,
        tick_count=150,
    )

    assert bar.timestamp == ts
    assert bar.tick_count == 150


def test_granularity_enum():
    """Test Granularity enum values."""
    assert Granularity.ONE_DAY.value == "1d"
    assert Granularity.ONE_HOUR.value == "1h"
    assert Granularity.ONE_MINUTE.value == "1m"


def test_ohlcv_list_to_dataframe():
    """Test conversion from OHLCV list to DataFrame."""
    candles = [
        OHLCV(datetime(2024, 1, 1, tzinfo=timezone.utc), 100, 105, 99, 103, 1000),
        OHLCV(datetime(2024, 1, 2, tzinfo=timezone.utc), 103, 108, 102, 106, 1100),
    ]

    df = ohlcv_list_to_dataframe(candles)

    assert len(df) == 2
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "timestamp"
    assert df.iloc[0]["close"] == 103


def test_ohlcv_list_to_dataframe_empty():
    """Test empty list conversion."""
    df = ohlcv_list_to_dataframe([])
    assert len(df) == 0
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_dataframe_to_ohlcv_list(sample_ohlcv_df):
    """Test conversion from DataFrame to OHLCV list."""
    candles = dataframe_to_ohlcv_list(sample_ohlcv_df)

    assert len(candles) == 10
    assert candles[0].close == 101.0
    assert candles[-1].close == 110.0
