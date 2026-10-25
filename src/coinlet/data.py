"""Data loading and streaming interfaces."""

from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

import pandas as pd


def load_csv(
    path: str | Path,
    time_col: str,
    value_col: str,
    parse_dates: bool = True,
) -> pd.Series:
    """Load time series data from a CSV file.

    Args:
        path: Path to the CSV file.
        time_col: Name of the column containing timestamps.
        value_col: Name of the column containing values.
        parse_dates: Whether to parse the time column as datetime.

    Returns:
        A pandas Series with DatetimeIndex.
    """
    df = pd.read_csv(path)

    if parse_dates:
        df[time_col] = pd.to_datetime(df[time_col])

    df = df.sort_values(time_col)
    series = pd.Series(df[value_col].values, index=df[time_col])
    series.index.name = None

    return series


@runtime_checkable
class Source(Protocol):
    """Protocol for streaming data sources.

    Implement this to create custom data sources (e.g., Coinbase WebSocket, PMU streams).
    Each iteration should yield a (timestamp, value) tuple.

    Example:
        class CoinbaseSource:
            def __iter__(self):
                return self

            def __next__(self) -> tuple[pd.Timestamp, float]:
                # Get next price from WebSocket
                ...
    """

    def __iter__(self) -> Iterator[tuple[pd.Timestamp, float]]: ...

    def __next__(self) -> tuple[pd.Timestamp, float]: ...


class StreamBuffer:
    """Buffer for accumulating streaming samples into a Series."""

    def __init__(self) -> None:
        self._timestamps: list[pd.Timestamp] = []
        self._values: list[float] = []

    def add(self, timestamp: pd.Timestamp, value: float) -> None:
        """Add a sample to the buffer."""
        self._timestamps.append(timestamp)
        self._values.append(value)

    def __len__(self) -> int:
        return len(self._timestamps)

    def to_series(self) -> pd.Series:
        """Convert buffer contents to a pandas Series."""
        return pd.Series(self._values, index=pd.DatetimeIndex(self._timestamps))

    def clear(self) -> None:
        """Clear the buffer."""
        self._timestamps.clear()
        self._values.clear()

    @classmethod
    def from_source(cls, source: Source, max_samples: int | None = None) -> "StreamBuffer":
        """Create a buffer by consuming samples from a Source.

        Args:
            source: A Source to consume.
            max_samples: Maximum number of samples to collect (None for all).
        """
        buffer = cls()
        for i, (ts, val) in enumerate(source):
            buffer.add(ts, val)
            if max_samples is not None and i + 1 >= max_samples:
                break
        return buffer
