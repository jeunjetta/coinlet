"""Tests for coinlet.plot module."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from coinlet.plot import (
    create_scalogram_figure,
    create_surface_figure,
    scalogram,
    surface_3d,
    update_scalogram_data,
    update_surface_data,
)
from coinlet.transform import cwt, log_periods


@pytest.fixture
def sample_cwt_result():
    n_samples = 100
    dates = pd.date_range("2020-01-01", periods=n_samples, freq="D")
    values = np.sin(2 * np.pi * np.arange(n_samples) / 20.0)
    series = pd.Series(values, index=dates)
    periods = log_periods(5.0, 50.0, 20)
    return cwt(series, periods)


@pytest.fixture
def longer_cwt_result():
    n_samples = 120
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


class TestLivePlotUpdates:
    def test_update_surface_grows_with_new_result(self, sample_cwt_result, longer_cwt_result):
        fig = create_surface_figure(sample_cwt_result)
        assert sample_cwt_result.power.shape[1] == 100

        update_surface_data(fig, longer_cwt_result)
        assert np.asarray(fig.data[0].z).shape[1] == 120
        assert len(np.asarray(fig.data[0].x)) == 120

    def test_update_scalogram_grows_with_new_result(self, sample_cwt_result, longer_cwt_result):
        fig = create_scalogram_figure(sample_cwt_result, show_coi=True)
        update_scalogram_data(fig, longer_cwt_result, show_coi=True)

        assert np.asarray(fig.data[0].z).shape[1] == 120
        assert len(np.asarray(fig.data[0].x)) == 120
        # COI curve tracks the new time axis
        assert len(np.asarray(fig.data[1].x)) == 120
