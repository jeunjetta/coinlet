"""Tests that historical and live sources implement the scaffold Source protocol."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd

from coinlet.data import Source, StreamBuffer
from coinlet.data.coinbase import CoinbaseHistorical, CoinbaseSource
from coinlet.data.csv_source import CSVSource
from coinlet.data.types import Granularity, Tick
from coinlet.data.yahoo import YahooFinanceSource


def test_csv_source_is_source(tmp_path, sample_ohlcv_df):
    csv_path = tmp_path / "prices.csv"
    sample_ohlcv_df.to_csv(csv_path)

    source = CSVSource(filepath=csv_path)
    assert isinstance(source, Source)

    pairs = list(source)
    assert len(pairs) == len(sample_ohlcv_df)
    assert pairs[0][1] == float(sample_ohlcv_df["close"].iloc[0])

    buffer = StreamBuffer.from_source(source)
    assert len(buffer) == len(sample_ohlcv_df)
    assert buffer.to_series().iloc[-1] == float(sample_ohlcv_df["close"].iloc[-1])


def test_coinbase_historical_is_source_after_fetch(sample_coinbase_response):
    source = CoinbaseHistorical(rate_limit_delay=0)
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_coinbase_response
    mock_session.get.return_value = mock_response
    source._session = mock_session

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 4, tzinfo=timezone.utc)
    df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

    assert isinstance(source, Source)
    pairs = list(source)
    assert len(pairs) == len(df)
    assert pairs[0][1] == float(df["close"].iloc[0])


def test_yahoo_source_is_source_after_fetch():
    source = YahooFinanceSource()
    source._set_replay_series(
        pd.Series(
            [100.0, 101.0],
            index=pd.date_range("2024-01-01", periods=2, tz="UTC"),
        )
    )
    assert isinstance(source, Source)
    pairs = list(source)
    assert len(pairs) == 2
    assert pairs[1][1] == 101.0


def test_coinbase_source_is_source():
    live_source = CoinbaseSource("BTC-USD", max_samples=2)
    assert isinstance(live_source, Source)

    ticks = [
        Tick(
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            price=50000.0,
            size=0.1,
            side="buy",
            product_id="BTC-USD",
        ),
        Tick(
            timestamp=datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
            price=50010.0,
            size=0.2,
            side="sell",
            product_id="BTC-USD",
        ),
    ]
    live_source._iter = iter(ticks)

    buffer = StreamBuffer.from_source(live_source, max_samples=2)
    assert len(buffer) == 2
    assert list(buffer.to_series()) == [50000.0, 50010.0]
