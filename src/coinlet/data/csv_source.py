"""CSV import/export for OHLCV data.

Supports any time series data (crypto, PMU, etc.) that can be
represented as timestamp + OHLCV columns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from coinlet.data.interfaces import SeriesReplay
from coinlet.data.types import Granularity

logger = logging.getLogger(__name__)


class CSVSource(SeriesReplay):
    """CSV file data source for importing/exporting OHLCV data.

    Implements the scaffold `Source` protocol by replaying close prices.

    Expected CSV format:
    - First column: timestamp (ISO format or Unix epoch)
    - Columns: open, high, low, close, volume (case-insensitive)

    For generic time series (e.g., PMU data), map columns via column_map.
    """

    source_name = "csv"

    def __init__(
        self,
        filepath: str | Path | None = None,
        column_map: dict[str, str] | None = None,
        timestamp_column: str = "timestamp",
        timestamp_format: str | None = None,
    ):
        """Initialize CSV source.

        Args:
            filepath: Optional CSV path used when iterating as a Source.
            column_map: Map from expected column names to actual names in CSV.
                       e.g., {"close": "value"} for single-value time series.
            timestamp_column: Name of timestamp column in CSV
            timestamp_format: strptime format for timestamps, or None for auto-detect
        """
        self._filepath = filepath
        self._column_map = column_map or {}
        self._timestamp_col = timestamp_column
        self._timestamp_format = timestamp_format
        self._replay_series = None

    def fetch_historical(
        self,
        symbol: str,
        granularity: Granularity,
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Load OHLCV data from CSV file.

        Args:
            symbol: Path to CSV file (symbol is used as filepath)
            granularity: Ignored for CSV (data is as-is)
            start: Filter start time
            end: Filter end time

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        return self.load(symbol, start=start, end=end)

    def load(
        self,
        filepath: str | Path,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Load OHLCV data from CSV file.

        Args:
            filepath: Path to CSV file
            start: Optional filter start time
            end: Optional filter end time

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        filepath = Path(filepath)
        if not filepath.exists():
            logger.error(f"CSV file not found: {filepath}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.read_csv(filepath)

        df.columns = df.columns.str.lower().str.strip()

        if self._column_map:
            reverse_map = {v.lower(): k for k, v in self._column_map.items()}
            df = df.rename(columns=reverse_map)

        ts_col = self._timestamp_col.lower()
        if ts_col not in df.columns:
            for col in df.columns:
                if "time" in col or "date" in col:
                    ts_col = col
                    break

        if self._timestamp_format:
            df[ts_col] = pd.to_datetime(df[ts_col], format=self._timestamp_format, utc=True)
        else:
            df[ts_col] = pd.to_datetime(df[ts_col], utc=True)

        df = df.set_index(ts_col)
        df.index.name = "timestamp"

        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")

        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                if col == "volume":
                    df[col] = 0.0
                elif "close" in df.columns:
                    df[col] = df["close"]
                elif "value" in df.columns:
                    df[col] = df["value"]
                else:
                    df[col] = 0.0

        df = df[required_cols]
        df = df.sort_index()

        if start:
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            df = df[df.index >= start]
        if end:
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            df = df[df.index <= end]

        if not df.empty:
            self._set_replay_series(df["close"])
        return df

    def _load_replay_series(self) -> pd.Series:
        series = getattr(self, "_replay_series", None)
        if series is not None and not series.empty:
            return series
        if self._filepath is None:
            return super()._load_replay_series()
        df = self.load(self._filepath)
        return df["close"]

    @staticmethod
    def save(
        df: pd.DataFrame,
        filepath: str | Path,
        include_index: bool = True,
    ) -> None:
        """Save DataFrame to CSV.

        Args:
            df: DataFrame with OHLCV data
            filepath: Output path
            include_index: Whether to include timestamp index
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        df_out = df.copy()
        if include_index:
            df_out.index = df_out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
            df_out.to_csv(filepath)
        else:
            df_out.to_csv(filepath, index=False)

        logger.info(f"Saved {len(df)} rows to {filepath}")
