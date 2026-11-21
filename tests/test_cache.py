"""Tests for DuckDB cache layer."""

from datetime import UTC, datetime

import pandas as pd

from coinlet.data.cache import PriceCache, fetch_with_cache
from coinlet.data.types import Granularity


class TestPriceCache:
    """Tests for PriceCache class."""

    def test_store_and_retrieve_ohlcv(self, temp_cache_dir, sample_ohlcv_df):
        """Test storing and retrieving OHLCV data."""
        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        try:
            cache.store_ohlcv("test", "BTC-USD", Granularity.ONE_DAY, sample_ohlcv_df)

            df = cache.get_ohlcv("test", "BTC-USD", Granularity.ONE_DAY)

            assert len(df) == len(sample_ohlcv_df)
            assert df["close"].iloc[0] == sample_ohlcv_df["close"].iloc[0]
        finally:
            cache.close()

    def test_get_cached_ranges(self, temp_cache_dir, sample_ohlcv_df):
        """Test getting cached date ranges."""
        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        try:
            start = sample_ohlcv_df.index.min().to_pydatetime()
            end = sample_ohlcv_df.index.max().to_pydatetime()

            cache.store_ohlcv(
                "test",
                "BTC-USD",
                Granularity.ONE_DAY,
                sample_ohlcv_df,
                start=start,
                end=end,
            )

            ranges = cache.get_cached_ranges("test", "BTC-USD", Granularity.ONE_DAY)

            assert len(ranges) == 1
            assert ranges[0][0] == start
            assert ranges[0][1] == end
        finally:
            cache.close()

    def test_get_missing_ranges_empty_cache(self, temp_cache_dir):
        """Test missing ranges with empty cache."""
        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        try:
            start = datetime(2024, 1, 1, tzinfo=UTC)
            end = datetime(2024, 1, 10, tzinfo=UTC)

            missing = cache.get_missing_ranges("test", "BTC-USD", Granularity.ONE_DAY, start, end)

            assert len(missing) == 1
            assert missing[0] == (start, end)
        finally:
            cache.close()

    def test_get_missing_ranges_partial_cache(self, temp_cache_dir, sample_ohlcv_df):
        """Test missing ranges with partial cache coverage."""
        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        try:
            cached_start = datetime(2024, 1, 3, tzinfo=UTC)
            cached_end = datetime(2024, 1, 7, tzinfo=UTC)

            partial_df = sample_ohlcv_df[
                (sample_ohlcv_df.index >= cached_start) & (sample_ohlcv_df.index <= cached_end)
            ]
            cache.store_ohlcv(
                "test",
                "BTC-USD",
                Granularity.ONE_DAY,
                partial_df,
                start=cached_start,
                end=cached_end,
            )

            request_start = datetime(2024, 1, 1, tzinfo=UTC)
            request_end = datetime(2024, 1, 10, tzinfo=UTC)

            missing = cache.get_missing_ranges(
                "test",
                "BTC-USD",
                Granularity.ONE_DAY,
                request_start,
                request_end,
            )

            assert len(missing) == 2
        finally:
            cache.close()

    def test_wavelet_result_cache(self, temp_cache_dir):
        """Test saving and loading wavelet results."""
        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        try:
            cache_key = "morlet_btc_1d_abc123"
            data_hash = "abc123"
            wavelet_type = "morlet"
            params = {"scales": [1, 2, 4, 8], "omega0": 6.0}
            result = b"serialized_wavelet_result"

            cache.save_wavelet_result(cache_key, data_hash, wavelet_type, params, result)

            assert cache.has_wavelet_result(cache_key)
            assert not cache.has_wavelet_result("nonexistent")

            loaded = cache.load_wavelet_result(cache_key)
            assert loaded == result
        finally:
            cache.close()

    def test_export_import_parquet(self, temp_cache_dir, temp_data_dir, sample_ohlcv_df):
        """Test Parquet export and import."""
        cache = PriceCache(
            db_path=temp_cache_dir / "test.duckdb",
            data_dir=temp_data_dir,
        )

        try:
            cache.store_ohlcv("test", "BTC-USD", Granularity.ONE_DAY, sample_ohlcv_df)

            parquet_path = cache.export_to_parquet("test", "BTC-USD", Granularity.ONE_DAY)

            assert parquet_path.exists()
            assert parquet_path.suffix == ".parquet"

            cache2 = PriceCache(db_path=temp_cache_dir / "test2.duckdb")
            df = cache2.import_from_parquet(
                parquet_path, "imported", "BTC-USD", Granularity.ONE_DAY
            )

            assert len(df) == len(sample_ohlcv_df)
            cache2.close()
        finally:
            cache.close()

    def test_save_and_load_cwt(self, temp_cache_dir):
        """Wavelet results are keyed by CWTResult.cache_key()."""
        import numpy as np

        from coinlet.transform import CWTResult

        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb", cache_dir=temp_cache_dir)
        result = CWTResult(
            times=np.array(["2024-01-01", "2024-01-02"], dtype="datetime64[D]"),
            periods=np.array([7.0, 14.0]),
            power=np.array([[1.0, 2.0], [3.0, 4.0]]),
            coi_mask=np.array([[False, False], [True, True]]),
            metadata={"wavelet": "cmor1.5-1.0", "preprocess": "none"},
        )
        try:
            key = cache.save_cwt(result)
            assert key == result.cache_key()
            assert cache.has_wavelet_result(key)
            loaded = cache.load_cwt(key)
            assert loaded is not None
            assert np.allclose(loaded.power, result.power)
            assert np.allclose(loaded.periods, result.periods)
            assert loaded.metadata == result.metadata
            # Different params → different key
            other = CWTResult(
                times=result.times,
                periods=np.array([8.0, 16.0]),
                power=result.power,
                coi_mask=result.coi_mask,
                metadata={"wavelet": "mexh", "preprocess": "none"},
            )
            assert other.cache_key() != key
            assert not cache.has_wavelet_result(other.cache_key())
        finally:
            cache.close()

    def test_compute_data_hash(self, sample_ohlcv_df):
        """Test data hash computation."""
        hash1 = PriceCache.compute_data_hash(sample_ohlcv_df)

        assert len(hash1) == 16
        assert hash1.isalnum()

        hash2 = PriceCache.compute_data_hash(sample_ohlcv_df)
        assert hash1 == hash2

        modified_df = sample_ohlcv_df.copy()
        modified_df.iloc[0, 0] = 999.0
        hash3 = PriceCache.compute_data_hash(modified_df)
        assert hash1 != hash3


class TestFetchWithCache:
    """Tests for fetch_with_cache function."""

    def test_fetch_with_cache_empty(self, temp_cache_dir, sample_coinbase_response):
        """Test fetching with empty cache."""
        from unittest.mock import MagicMock

        cache = PriceCache(db_path=temp_cache_dir / "test.duckdb")

        mock_source = MagicMock()
        mock_source.source_name = "mock"
        mock_source.fetch_historical.return_value = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
                "open": [100, 101, 102],
                "high": [102, 103, 104],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000, 1100, 1200],
            }
        ).set_index("timestamp")

        try:
            start = datetime(2024, 1, 1, tzinfo=UTC)
            end = datetime(2024, 1, 4, tzinfo=UTC)

            df = fetch_with_cache(cache, mock_source, "BTC-USD", Granularity.ONE_DAY, start, end)

            assert len(df) == 3
            mock_source.fetch_historical.assert_called_once()

            df2 = fetch_with_cache(cache, mock_source, "BTC-USD", Granularity.ONE_DAY, start, end)

            assert len(df2) == 3
            assert mock_source.fetch_historical.call_count == 1
        finally:
            cache.close()
