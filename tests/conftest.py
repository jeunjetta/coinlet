"""Pytest configuration and fixtures."""

import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_df():
    """Sample OHLCV DataFrame for testing."""
    data = {
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
        "high": [102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0],
        "low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
        "close": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0],
        "volume": [1000.0] * 10,
    }
    df = pd.DataFrame(data)
    df = df.set_index("timestamp")
    return df


@pytest.fixture
def sample_coinbase_response():
    """Sample Coinbase API response (candles format)."""
    return [
        [1704067200, 99.0, 102.0, 100.0, 101.0, 1000.0],
        [1704153600, 100.0, 103.0, 101.0, 102.0, 1100.0],
        [1704240000, 101.0, 104.0, 102.0, 103.0, 1200.0],
    ]


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for cache testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def temp_data_dir(tmp_path):
    """Temporary directory for data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir
