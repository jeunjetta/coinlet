"""Tests for CWTResult serialization methods."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from coinlet.transform import CWTResult, cwt, log_periods


@pytest.fixture
def sample_result():
    """Create a sample CWT result for testing."""
    n_samples = 100
    dates = pd.date_range("2020-01-01", periods=n_samples, freq="D")
    values = np.sin(2 * np.pi * np.arange(n_samples) / 20.0)
    series = pd.Series(values, index=dates)
    periods = log_periods(5.0, 50.0, 20)
    return cwt(series, periods)


class TestCacheKey:
    def test_cache_key_is_string(self, sample_result):
        key = sample_result.cache_key()
        assert isinstance(key, str)
        assert len(key) == 16

    def test_cache_key_is_stable(self, sample_result):
        key1 = sample_result.cache_key()
        key2 = sample_result.cache_key()
        assert key1 == key2

    def test_different_results_different_keys(self):
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        values = np.sin(2 * np.pi * np.arange(100) / 20.0)
        series = pd.Series(values, index=dates)

        result1 = cwt(series, log_periods(5.0, 50.0, 20))
        result2 = cwt(series, log_periods(10.0, 100.0, 20))

        assert result1.cache_key() != result2.cache_key()


class TestDataFrameSerialization:
    def test_to_dataframe_columns(self, sample_result):
        df = sample_result.to_dataframe()
        assert set(df.columns) == {"time", "period", "power", "in_coi"}

    def test_to_dataframe_size(self, sample_result):
        df = sample_result.to_dataframe()
        n_periods, n_times = sample_result.power.shape
        assert len(df) == n_periods * n_times

    def test_roundtrip_dataframe(self, sample_result):
        df = sample_result.to_dataframe()
        restored = CWTResult.from_dataframe(df)

        assert restored.power.shape == sample_result.power.shape
        assert np.allclose(restored.power, sample_result.power)
        assert np.array_equal(restored.coi_mask, sample_result.coi_mask)


class TestParquetSerialization:
    def test_to_parquet_creates_file(self, sample_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result.parquet"
            sample_result.to_parquet(path)
            assert path.exists()

    def test_roundtrip_parquet(self, sample_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result.parquet"
            sample_result.to_parquet(path)
            restored = CWTResult.from_parquet(path)

            assert restored.power.shape == sample_result.power.shape
            assert np.allclose(restored.power, sample_result.power)
            assert np.array_equal(restored.coi_mask, sample_result.coi_mask)

    def test_metadata_preserved_in_parquet(self, sample_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "result.parquet"
            sample_result.to_parquet(path)
            restored = CWTResult.from_parquet(path)

            assert restored.metadata is not None
            assert restored.metadata.get("wavelet") == sample_result.metadata.get("wavelet")
