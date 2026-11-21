"""Tests for coinlet.data module."""

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from coinlet.data import StreamBuffer, load_csv


class TestLoadCSV:
    @pytest.fixture
    def sample_csv(self):
        content = """date,price,volume
2020-01-01,100.0,1000
2020-01-02,101.5,1100
2020-01-03,99.8,900
2020-01-04,102.3,1200
2020-01-05,103.1,1050
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_load_csv_returns_series(self, sample_csv):
        series = load_csv(sample_csv, time_col="date", value_col="price")
        assert isinstance(series, pd.Series)

    def test_load_csv_has_datetime_index(self, sample_csv):
        series = load_csv(sample_csv, time_col="date", value_col="price")
        assert isinstance(series.index, pd.DatetimeIndex)

    def test_load_csv_values(self, sample_csv):
        series = load_csv(sample_csv, time_col="date", value_col="price")
        assert len(series) == 5
        assert series.iloc[0] == 100.0
        assert series.iloc[1] == 101.5

    def test_load_csv_sorted_by_time(self, sample_csv):
        series = load_csv(sample_csv, time_col="date", value_col="price")
        assert series.index.is_monotonic_increasing


class MockSource:
    """A mock Source for testing."""

    def __init__(self, data: list[tuple]):
        self._data = data
        self._index = 0

    def __iter__(self) -> Iterator[tuple]:
        return self

    def __next__(self) -> tuple:
        if self._index >= len(self._data):
            raise StopIteration
        item = self._data[self._index]
        self._index += 1
        return item


class TestSourceProtocol:
    def test_mock_source_is_iterable(self):
        source = MockSource([(pd.Timestamp("2020-01-01"), 100.0)])
        assert hasattr(source, "__iter__")
        assert hasattr(source, "__next__")

    def test_mock_source_yields_tuples(self):
        data = [
            (pd.Timestamp("2020-01-01"), 100.0),
            (pd.Timestamp("2020-01-02"), 101.0),
        ]
        source = MockSource(data)
        collected = list(source)
        assert collected == data


class TestStreamBuffer:
    def test_buffer_accumulates_samples(self):
        buffer = StreamBuffer()
        buffer.add(pd.Timestamp("2020-01-01"), 100.0)
        buffer.add(pd.Timestamp("2020-01-02"), 101.0)
        assert len(buffer) == 2

    def test_buffer_to_series(self):
        buffer = StreamBuffer()
        buffer.add(pd.Timestamp("2020-01-01"), 100.0)
        buffer.add(pd.Timestamp("2020-01-02"), 101.0)
        series = buffer.to_series()
        assert isinstance(series, pd.Series)
        assert isinstance(series.index, pd.DatetimeIndex)
        assert len(series) == 2

    def test_buffer_from_source(self):
        data = [
            (pd.Timestamp("2020-01-01"), 100.0),
            (pd.Timestamp("2020-01-02"), 101.0),
            (pd.Timestamp("2020-01-03"), 102.0),
        ]
        source = MockSource(data)
        buffer = StreamBuffer.from_source(source)
        series = buffer.to_series()
        assert len(series) == 3

    def test_buffer_clear(self):
        buffer = StreamBuffer()
        buffer.add(pd.Timestamp("2020-01-01"), 100.0)
        buffer.clear()
        assert len(buffer) == 0
