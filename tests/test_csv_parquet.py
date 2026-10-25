"""Tests for CSV source and Parquet loader."""

from datetime import datetime, timezone

import pandas as pd

from coinlet.data.csv_source import CSVSource
from coinlet.data.parquet import ParquetLoader, load_parquet
from coinlet.data.types import Granularity


class TestCSVSource:
    """Tests for CSVSource class."""

    def test_load_standard_csv(self, tmp_path, sample_ohlcv_df):
        """Test loading standard OHLCV CSV."""
        csv_path = tmp_path / "test.csv"
        sample_ohlcv_df.to_csv(csv_path)

        source = CSVSource()
        df = source.load(csv_path)

        assert len(df) == len(sample_ohlcv_df)
        assert "close" in df.columns
        assert df.index.tzinfo is not None

    def test_load_with_column_map(self, tmp_path):
        """Test loading CSV with custom column names."""
        csv_path = tmp_path / "test.csv"
        pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=5, freq="D"),
            "price": [100, 101, 102, 103, 104],
            "qty": [1000, 1100, 1200, 1300, 1400],
        }).to_csv(csv_path, index=False)

        source = CSVSource(
            column_map={"close": "price", "volume": "qty"},
            timestamp_column="time",
        )
        df = source.load(csv_path)

        assert len(df) == 5
        assert "close" in df.columns
        assert df["close"].iloc[0] == 100

    def test_load_missing_file(self, tmp_path):
        """Test loading non-existent file."""
        source = CSVSource()
        df = source.load(tmp_path / "nonexistent.csv")
        assert len(df) == 0

    def test_save_csv(self, tmp_path, sample_ohlcv_df):
        """Test saving DataFrame to CSV."""
        csv_path = tmp_path / "output.csv"
        CSVSource.save(sample_ohlcv_df, csv_path)

        assert csv_path.exists()

        df = pd.read_csv(csv_path)
        assert len(df) == len(sample_ohlcv_df)

    def test_fetch_historical_interface(self, tmp_path, sample_ohlcv_df):
        """Test using CSV source through PriceSource interface."""
        csv_path = tmp_path / "test.csv"
        sample_ohlcv_df.to_csv(csv_path)

        source = CSVSource()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 5, tzinfo=timezone.utc)

        df = source.fetch_historical(str(csv_path), Granularity.ONE_DAY, start, end)

        assert len(df) <= len(sample_ohlcv_df)


class TestParquetLoader:
    """Tests for ParquetLoader class."""

    def test_load_local_parquet(self, tmp_path, sample_ohlcv_df):
        """Test loading local Parquet file."""
        parquet_path = tmp_path / "test.parquet"
        sample_ohlcv_df.reset_index().to_parquet(parquet_path)

        loader = ParquetLoader()
        df = loader.load(parquet_path)

        assert len(df) == len(sample_ohlcv_df)
        assert df.index.tzinfo is not None
        assert "close" in df.columns

    def test_load_missing_file(self, tmp_path):
        """Test loading non-existent file."""
        loader = ParquetLoader()
        df = loader.load(tmp_path / "nonexistent.parquet")
        assert len(df) == 0

    def test_list_available_datasets(self, tmp_path, sample_ohlcv_df):
        """Test listing available Parquet files."""
        (tmp_path / "btc_1d.parquet").write_bytes(b"fake parquet")
        (tmp_path / "eth_1d.parquet").write_bytes(b"fake parquet 2")

        datasets = ParquetLoader.list_available_datasets(tmp_path)

        assert len(datasets) == 2
        names = [d["name"] for d in datasets]
        assert "btc_1d" in names
        assert "eth_1d" in names

    def test_normalize_dataframe(self, tmp_path, sample_ohlcv_df):
        """Test DataFrame normalization."""
        parquet_path = tmp_path / "test.parquet"
        df_no_tz = sample_ohlcv_df.copy()
        df_no_tz.index = df_no_tz.index.tz_localize(None)
        df_no_tz.reset_index().to_parquet(parquet_path)

        loader = ParquetLoader()
        df = loader.load(parquet_path)

        assert df.index.tzinfo is not None
        assert df.index.name == "timestamp"


def test_load_parquet_convenience(tmp_path, sample_ohlcv_df):
    """Test convenience function."""
    parquet_path = tmp_path / "test.parquet"
    sample_ohlcv_df.reset_index().to_parquet(parquet_path)

    df = load_parquet(parquet_path)

    assert len(df) == len(sample_ohlcv_df)
