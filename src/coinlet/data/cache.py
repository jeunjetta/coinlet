"""DuckDB caching layer with Parquet export/import.

Stores raw OHLCV data and computed wavelet results locally.
Supports incremental fetching (only downloads missing date ranges).
Exports to Parquet for browser-compatible reading and Git commits.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from coinlet.data.types import Granularity

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_DATA_DIR = Path("data")


class PriceCache:
    """DuckDB-backed cache for OHLCV data and wavelet results.

    Features:
    - Incremental fetching: only downloads missing date ranges
    - Parquet export/import for committed files and HTTP loading
    - Wavelet results cache keyed by cache_key from wavelet module

    The DuckDB file stays local (gitignored). Parquet files can be
    committed to Git for sharing and browser-based loading.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        cache_dir: Path | None = None,
        data_dir: Path | None = None,
    ):
        """Initialize cache.

        Args:
            db_path: Path to DuckDB file, or None for in-memory
            cache_dir: Directory for DuckDB file (default: cache/)
            data_dir: Directory for Parquet exports (default: data/)
        """
        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self._data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

        if db_path is None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = self._cache_dir / "coinlet.duckdb"

        self._db_path = Path(db_path) if db_path else None
        self._conn: "duckdb.DuckDBPyConnection" | None = None

    def _get_conn(self) -> "duckdb.DuckDBPyConnection":
        """Get or create DuckDB connection."""
        if self._conn is None:
            import duckdb
            self._conn = duckdb.connect(str(self._db_path) if self._db_path else ":memory:")
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                source VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                granularity VARCHAR NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                open DOUBLE NOT NULL,
                high DOUBLE NOT NULL,
                low DOUBLE NOT NULL,
                close DOUBLE NOT NULL,
                volume DOUBLE NOT NULL,
                PRIMARY KEY (source, symbol, granularity, timestamp)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_ranges (
                source VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                granularity VARCHAR NOT NULL,
                start_time TIMESTAMPTZ NOT NULL,
                end_time TIMESTAMPTZ NOT NULL,
                fetched_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (source, symbol, granularity, start_time)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS wavelet_results (
                cache_key VARCHAR PRIMARY KEY,
                data_hash VARCHAR NOT NULL,
                wavelet_type VARCHAR NOT NULL,
                params JSON NOT NULL,
                result BLOB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
        """)

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_cached_ranges(
        self,
        source: str,
        symbol: str,
        granularity: Granularity,
    ) -> list[tuple[datetime, datetime]]:
        """Get list of date ranges already cached.

        Returns:
            List of (start, end) tuples for cached ranges
        """
        conn = self._get_conn()
        result = conn.execute("""
            SELECT start_time, end_time FROM ohlcv_ranges
            WHERE source = ? AND symbol = ? AND granularity = ?
            ORDER BY start_time
        """, [source, symbol, granularity.value]).fetchall()

        return [(row[0], row[1]) for row in result]

    def get_missing_ranges(
        self,
        source: str,
        symbol: str,
        granularity: Granularity,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """Calculate date ranges not yet cached.

        Args:
            source: Data source name
            symbol: Trading pair
            granularity: Candle interval
            start: Desired start time
            end: Desired end time

        Returns:
            List of (start, end) tuples that need fetching
        """
        cached = self.get_cached_ranges(source, symbol, granularity)
        if not cached:
            return [(start, end)]

        sorted_ranges = sorted(cached, key=lambda x: x[0])
        merged = []
        for r_start, r_end in sorted_ranges:
            if merged and r_start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], r_end))
            else:
                merged.append((r_start, r_end))

        missing = []
        current = start

        for r_start, r_end in merged:
            if current < r_start:
                missing.append((current, min(r_start, end)))
            current = max(current, r_end)

        if current < end:
            missing.append((current, end))

        return [(s, e) for s, e in missing if s < e]

    def store_ohlcv(
        self,
        source: str,
        symbol: str,
        granularity: Granularity,
        df: pd.DataFrame,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        """Store OHLCV data in cache.

        Args:
            source: Data source name
            symbol: Trading pair
            granularity: Candle interval
            df: DataFrame with UTC timestamp index and OHLCV columns
            start: Range start (defaults to df min timestamp)
            end: Range end (defaults to df max timestamp)
        """
        if df.empty:
            return

        conn = self._get_conn()

        if start is None:
            start = df.index.min().to_pydatetime()
        if end is None:
            end = df.index.max().to_pydatetime()

        for ts, row in df.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO ohlcv
                (source, symbol, granularity, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                source, symbol, granularity.value,
                ts.to_pydatetime(),
                float(row["open"]), float(row["high"]),
                float(row["low"]), float(row["close"]),
                float(row["volume"]),
            ])

        conn.execute("""
            INSERT OR REPLACE INTO ohlcv_ranges
            (source, symbol, granularity, start_time, end_time, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            source, symbol, granularity.value,
            start, end, datetime.now(timezone.utc),
        ])

    def get_ohlcv(
        self,
        source: str,
        symbol: str,
        granularity: Granularity,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """Retrieve OHLCV data from cache.

        Args:
            source: Data source name
            symbol: Trading pair
            granularity: Candle interval
            start: Filter start time
            end: Filter end time

        Returns:
            DataFrame with UTC timestamp index and OHLCV columns
        """
        conn = self._get_conn()

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE source = ? AND symbol = ? AND granularity = ?
        """
        params = [source, symbol, granularity.value]

        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)

        query += " ORDER BY timestamp"

        result = conn.execute(query, params).fetchdf()

        if result.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
        result = result.set_index("timestamp")
        return result

    def save_wavelet_result(
        self,
        cache_key: str,
        data_hash: str,
        wavelet_type: str,
        params: dict[str, Any],
        result: bytes,
    ) -> None:
        """Save wavelet computation result to cache.

        Args:
            cache_key: Unique key from wavelet module's cache_key()
            data_hash: Hash of input data
            wavelet_type: Type of wavelet (e.g., 'morlet')
            params: Wavelet parameters (scale range, etc.)
            result: Serialized result (e.g., pickled numpy array)
        """
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO wavelet_results
            (cache_key, data_hash, wavelet_type, params, result, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            cache_key, data_hash, wavelet_type,
            json.dumps(params), result,
            datetime.now(timezone.utc),
        ])

    def load_wavelet_result(self, cache_key: str) -> bytes | None:
        """Load wavelet computation result from cache.

        Args:
            cache_key: Unique key from wavelet module's cache_key()

        Returns:
            Serialized result bytes, or None if not cached
        """
        conn = self._get_conn()
        result = conn.execute("""
            SELECT result FROM wavelet_results WHERE cache_key = ?
        """, [cache_key]).fetchone()

        return result[0] if result else None

    def has_wavelet_result(self, cache_key: str) -> bool:
        """Check if wavelet result is cached.

        Args:
            cache_key: Unique key from wavelet module's cache_key()

        Returns:
            True if result exists in cache
        """
        conn = self._get_conn()
        result = conn.execute("""
            SELECT 1 FROM wavelet_results WHERE cache_key = ? LIMIT 1
        """, [cache_key]).fetchone()
        return result is not None

    def export_to_parquet(
        self,
        source: str,
        symbol: str,
        granularity: Granularity,
        output_path: str | Path | None = None,
    ) -> Path:
        """Export OHLCV data to Parquet file.

        Args:
            source: Data source name
            symbol: Trading pair
            granularity: Candle interval
            output_path: Output path (default: data/{source}_{symbol}_{granularity}.parquet)

        Returns:
            Path to created Parquet file
        """
        df = self.get_ohlcv(source, symbol, granularity)

        if output_path is None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{source}_{symbol.replace('-', '_')}_{granularity.value}.parquet"
            output_path = self._data_dir / filename

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        df.reset_index().to_parquet(output_path, index=False, compression="snappy")
        logger.info(f"Exported {len(df)} rows to {output_path}")

        return output_path

    def import_from_parquet(
        self,
        parquet_path: str | Path,
        source: str,
        symbol: str,
        granularity: Granularity,
    ) -> pd.DataFrame:
        """Import OHLCV data from Parquet file into cache.

        Args:
            parquet_path: Path to Parquet file
            source: Data source name to store under
            symbol: Trading pair
            granularity: Candle interval

        Returns:
            Imported DataFrame
        """
        conn = self._get_conn()

        df = conn.execute(f"""
            SELECT * FROM read_parquet('{parquet_path}')
        """).fetchdf()

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()

        self.store_ohlcv(source, symbol, granularity, df)
        logger.info(f"Imported {len(df)} rows from {parquet_path}")

        return df

    @staticmethod
    def compute_data_hash(df: pd.DataFrame) -> str:
        """Compute hash of DataFrame for cache key generation.

        Args:
            df: OHLCV DataFrame

        Returns:
            SHA256 hash of data content
        """
        content = df.to_csv().encode("utf-8")
        return hashlib.sha256(content).hexdigest()[:16]


def fetch_with_cache(
    cache: PriceCache,
    source: Any,
    symbol: str,
    granularity: Granularity,
    start: datetime,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV data with incremental caching.

    Only fetches date ranges not already in cache.

    Args:
        cache: PriceCache instance
        source: PriceSource implementation
        symbol: Trading pair
        granularity: Candle interval
        start: Start time
        end: End time (defaults to now)

    Returns:
        Complete DataFrame for requested range
    """
    if end is None:
        end = datetime.now(timezone.utc)

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    missing = cache.get_missing_ranges(
        source.source_name, symbol, granularity, start, end
    )

    for range_start, range_end in missing:
        logger.info(f"Fetching {symbol} {granularity.value} from {range_start} to {range_end}")
        df = source.fetch_historical(symbol, granularity, range_start, range_end)
        if not df.empty:
            cache.store_ohlcv(
                source.source_name, symbol, granularity, df,
                start=range_start, end=range_end,
            )

    return cache.get_ohlcv(source.source_name, symbol, granularity, start, end)
