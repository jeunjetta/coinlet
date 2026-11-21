"""Yahoo Finance data source via yfinance.

Provides historical OHLCV data for any ticker available on Yahoo Finance,
including crypto (BTC-USD, ETH-USD), stocks, indices, etc.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd

from coinlet.data.interfaces import SeriesReplay
from coinlet.data.types import Granularity

if TYPE_CHECKING:
    import yfinance

logger = logging.getLogger(__name__)

GRANULARITY_TO_YFINANCE: dict[Granularity, str] = {
    Granularity.ONE_MINUTE: "1m",
    Granularity.FIVE_MINUTES: "5m",
    Granularity.FIFTEEN_MINUTES: "15m",
    Granularity.ONE_HOUR: "1h",
    Granularity.SIX_HOURS: "1h",  # yfinance doesn't have 6h, we'll resample
    Granularity.ONE_DAY: "1d",
}


class YahooFinanceSource(SeriesReplay):
    """Yahoo Finance historical data source.

    Implements the scaffold `Source` protocol by replaying close prices.

    Works for crypto (BTC-USD, ETH-USD), stocks, indices, etc.
    Note: yfinance has limitations on intraday data history.
    """

    source_name = "yahoo"

    def __init__(
        self,
        symbol: str | None = None,
        granularity: Granularity = Granularity.ONE_DAY,
        start: datetime | None = None,
        end: datetime | None = None,
    ):
        self._symbol = symbol
        self._granularity = granularity
        self._start = start
        self._end = end
        self._yf: yfinance | None = None
        self._replay_series = None

    def _get_yf(self):
        if self._yf is None:
            import yfinance

            self._yf = yfinance
        return self._yf

    def fetch_historical(
        self,
        symbol: str,
        granularity: Granularity,
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data from Yahoo Finance.

        Args:
            symbol: Ticker symbol (e.g., 'BTC-USD', 'AAPL')
            granularity: Candle interval
            start: Start time (UTC)
            end: End time (UTC), defaults to now

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        yf = self._get_yf()

        if end is None:
            end = datetime.now(UTC)

        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        yf_interval = GRANULARITY_TO_YFINANCE[granularity]
        needs_resample = granularity == Granularity.SIX_HOURS

        ticker = yf.Ticker(symbol)

        try:
            df = ticker.history(
                start=start,
                end=end,
                interval=yf_interval,
                auto_adjust=True,
            )
        except Exception as e:
            logger.error(f"Failed to fetch {symbol} from Yahoo Finance: {e}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )

        df = df[["open", "high", "low", "close", "volume"]]

        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        df.index.name = "timestamp"

        if needs_resample:
            df = (
                df.resample("6h")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna()
            )

        if not df.empty:
            self._set_replay_series(df["close"])
        return df

    def _load_replay_series(self) -> pd.Series:
        series = getattr(self, "_replay_series", None)
        if series is not None and not series.empty:
            return series
        if self._symbol is None:
            return super()._load_replay_series()
        start = self._start or datetime(2015, 1, 1, tzinfo=UTC)
        df = self.fetch_historical(self._symbol, self._granularity, start, self._end)
        return df["close"]
