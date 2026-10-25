"""Tests for coinlet.transform module using synthetic sine signals."""

import numpy as np
import pandas as pd
import pytest

from coinlet.transform import CWTResult, cwt, log_periods


class TestLogPeriods:
    def test_log_periods_range(self):
        periods = log_periods(1.0, 100.0, 10)
        assert len(periods) == 10
        assert np.isclose(periods[0], 1.0)
        assert np.isclose(periods[-1], 100.0)

    def test_log_periods_spacing(self):
        periods = log_periods(1.0, 1000.0, 4)
        ratios = periods[1:] / periods[:-1]
        assert np.allclose(ratios, ratios[0])


class TestCWT:
    @pytest.fixture
    def sample_rate(self):
        return 1.0  # 1 sample per day

    @pytest.fixture
    def synthetic_sine(self, sample_rate):
        """Create a synthetic sine wave with known period of 30 days."""
        period_days = 30.0
        n_samples = 365
        t = np.arange(n_samples) / sample_rate
        values = np.sin(2 * np.pi * t / period_days)
        dates = pd.date_range("2020-01-01", periods=n_samples, freq="D")
        return pd.Series(values, index=dates), period_days

    @pytest.fixture
    def multi_period_sine(self, sample_rate):
        """Create a signal with two distinct periods: 10 and 50 days."""
        n_samples = 365
        t = np.arange(n_samples) / sample_rate
        values = np.sin(2 * np.pi * t / 10.0) + 0.5 * np.sin(2 * np.pi * t / 50.0)
        dates = pd.date_range("2020-01-01", periods=n_samples, freq="D")
        return pd.Series(values, index=dates), [10.0, 50.0]

    def test_cwt_returns_result_dataclass(self, synthetic_sine):
        series, _ = synthetic_sine
        periods = log_periods(5.0, 60.0, 20)
        result = cwt(series, periods)
        assert isinstance(result, CWTResult)
        assert hasattr(result, "times")
        assert hasattr(result, "periods")
        assert hasattr(result, "power")
        assert hasattr(result, "coi_mask")

    def test_cwt_output_shapes(self, synthetic_sine):
        series, _ = synthetic_sine
        periods = log_periods(5.0, 60.0, 20)
        result = cwt(series, periods)
        n_times = len(series)
        n_periods = len(periods)
        assert result.power.shape == (n_periods, n_times)
        assert result.coi_mask.shape == (n_periods, n_times)
        assert len(result.times) == n_times
        assert len(result.periods) == n_periods

    def test_cwt_detects_single_period(self, synthetic_sine):
        """Core TDD test: a 30-day sine must show max power near 30 days."""
        series, true_period = synthetic_sine
        periods = log_periods(10.0, 100.0, 50)
        result = cwt(series, periods)

        time_center = len(series) // 2
        power_at_center = result.power[:, time_center]
        peak_idx = np.argmax(power_at_center)
        detected_period = result.periods[peak_idx]

        assert np.isclose(detected_period, true_period, rtol=0.15), (
            f"Expected period ~{true_period}, detected {detected_period}"
        )

    def test_cwt_detects_multiple_periods(self, multi_period_sine):
        """Two distinct periods should both appear as local maxima."""
        series, true_periods = multi_period_sine
        periods = log_periods(5.0, 100.0, 60)
        result = cwt(series, periods)

        time_center = len(series) // 2
        power_at_center = result.power[:, time_center]

        for true_period in true_periods:
            period_mask = (result.periods > true_period * 0.7) & (result.periods < true_period * 1.3)
            local_power = power_at_center[period_mask]
            local_periods = result.periods[period_mask]
            local_peak_idx = np.argmax(local_power)
            detected = local_periods[local_peak_idx]
            assert np.isclose(detected, true_period, rtol=0.2), (
                f"Expected period ~{true_period}, detected {detected}"
            )

    def test_cwt_with_different_wavelets(self, synthetic_sine):
        series, true_period = synthetic_sine
        periods = log_periods(10.0, 100.0, 30)

        for wavelet in ["cmor1.5-1.0", "mexh", "gaus1"]:
            result = cwt(series, periods, wavelet=wavelet)
            assert result.power.shape[0] == len(periods)
            assert not np.any(np.isnan(result.power))

    def test_cwt_cone_of_influence(self, synthetic_sine):
        series, _ = synthetic_sine
        periods = log_periods(10.0, 100.0, 20)
        result = cwt(series, periods)

        assert result.coi_mask.sum() > 0
        assert result.coi_mask[:, 0].any()
        assert result.coi_mask[:, -1].any()

    def test_cwt_with_log_returns(self, synthetic_sine):
        series, _ = synthetic_sine
        series_positive = series + 2.0
        periods = log_periods(10.0, 100.0, 20)
        result = cwt(series_positive, periods, preprocess="log_return")
        assert not np.any(np.isnan(result.power))

    def test_cwt_with_detrend(self, synthetic_sine):
        series, _ = synthetic_sine
        series_with_trend = series + np.linspace(0, 10, len(series))
        series_trended = pd.Series(series_with_trend.values, index=series.index)
        periods = log_periods(10.0, 100.0, 20)
        result = cwt(series_trended, periods, preprocess="detrend")
        assert not np.any(np.isnan(result.power))


class TestCWTEdgeCases:
    def test_short_series(self):
        dates = pd.date_range("2020-01-01", periods=50, freq="D")
        values = np.sin(2 * np.pi * np.arange(50) / 10.0)
        series = pd.Series(values, index=dates)
        periods = log_periods(5.0, 20.0, 10)
        result = cwt(series, periods)
        assert result.power.shape == (10, 50)

    def test_hourly_sampling(self):
        dates = pd.date_range("2020-01-01", periods=24 * 30, freq="h")
        period_hours = 24.0
        values = np.sin(2 * np.pi * np.arange(len(dates)) / period_hours)
        series = pd.Series(values, index=dates)
        periods = log_periods(12.0, 72.0, 20)
        result = cwt(series, periods)

        time_center = len(series) // 2
        power_at_center = result.power[:, time_center]
        peak_idx = np.argmax(power_at_center)
        detected = result.periods[peak_idx]
        assert np.isclose(detected, 24.0, rtol=0.2)
