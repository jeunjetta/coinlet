"""Core data types for the coinlet data layer."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

import pandas as pd


class Granularity(StrEnum):
    """Supported candle granularities."""

    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    ONE_DAY = "1d"


GRANULARITY_SECONDS: dict[Granularity, int] = {
    Granularity.ONE_MINUTE: 60,
    Granularity.FIVE_MINUTES: 300,
    Granularity.FIFTEEN_MINUTES: 900,
    Granularity.ONE_HOUR: 3600,
    Granularity.SIX_HOURS: 21600,
    Granularity.ONE_DAY: 86400,
}

COINBASE_GRANULARITY_MAP: dict[Granularity, int] = {
    Granularity.ONE_MINUTE: 60,
    Granularity.FIVE_MINUTES: 300,
    Granularity.FIFTEEN_MINUTES: 900,
    Granularity.ONE_HOUR: 3600,
    Granularity.SIX_HOURS: 21600,
    Granularity.ONE_DAY: 86400,
}


@dataclass(frozen=True, slots=True)
class OHLCV:
    """Single OHLCV candle."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class Tick:
    """Single trade tick from live feed."""

    timestamp: datetime
    price: float
    size: float
    side: Literal["buy", "sell"]
    product_id: str


@dataclass(frozen=True, slots=True)
class Bar:
    """Aggregated bar from live ticks (same structure as OHLCV but from live data)."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_count: int


def ohlcv_list_to_dataframe(candles: list[OHLCV]) -> pd.DataFrame:
    """Convert list of OHLCV to DataFrame with UTC timestamp index.

    Returns DataFrame with columns: open, high, low, close, volume
    Index: DatetimeIndex (UTC) named 'timestamp'
    """
    if not candles:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame([c.to_dict() for c in candles])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df


def dataframe_to_ohlcv_list(df: pd.DataFrame) -> list[OHLCV]:
    """Convert DataFrame with OHLCV columns back to list of OHLCV objects."""
    candles = []
    for ts, row in df.iterrows():
        candles.append(
            OHLCV(
                timestamp=ts.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    return candles
