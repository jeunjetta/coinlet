"""Tests for coinlet.plot module."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from coinlet.plot import scalogram, surface_3d
from coinlet.transform import cwt, log_periods


@pytest.fixture
def sample_cwt_result():
    n_samples = 100
    dates = pd.date_range("2020-01-01", periods=n_samples, freq="D")
    values = np.sin(2 * np.pi * np.arange(n_samples) / 20.0)
    series = pd.Series(values, index=dates)
    periods = log_periods(5.0, 50.0, 20)
    return cwt(series, periods)


class TestSurface3D:
    def test_surface_3d_creates_html(self, sample_cwt_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = surface_3d(sample_cwt_result, output_dir=tmpdir)
            assert Path(path).exists()
            assert path.endswith(".html")

    def test_surface_3d_html_contains_plotly(self, sample_cwt_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = surface_3d(sample_cwt_result, output_dir=tmpdir)
            content = Path(path).read_text()
            assert "plotly" in content.lower()


class TestScalogram:
    def test_scalogram_creates_html(self, sample_cwt_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scalogram(sample_cwt_result, output_dir=tmpdir)
            assert Path(path).exists()
            assert path.endswith(".html")

    def test_scalogram_html_contains_plotly(self, sample_cwt_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scalogram(sample_cwt_result, output_dir=tmpdir)
            content = Path(path).read_text()
            assert "plotly" in content.lower()

    def test_scalogram_with_coi(self, sample_cwt_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = scalogram(sample_cwt_result, output_dir=tmpdir, show_coi=True)
            assert Path(path).exists()
