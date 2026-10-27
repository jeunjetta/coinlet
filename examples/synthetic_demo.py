#!/usr/bin/env python3
"""Synthetic signal demo: sine waves with known periods.

This demo verifies that coinlet correctly identifies periodicities in synthetic data.
We create a signal with two known periods (30 and 90 days) and show that the CWT
recovers them.
"""

import numpy as np
import pandas as pd

from coinlet import cwt, log_periods, scalogram, surface_3d


def main():
    np.random.seed(42)
    n_days = 730
    dates = pd.date_range("2020-01-01", periods=n_days, freq="D")
    t = np.arange(n_days)

    period_1 = 30.0
    period_2 = 90.0

    signal = (
        np.sin(2 * np.pi * t / period_1)
        + 0.5 * np.sin(2 * np.pi * t / period_2)
        + 0.1 * np.random.randn(n_days)
    )
    series = pd.Series(signal, index=dates)

    print(f"Created synthetic signal with periods: {period_1} days, {period_2} days")
    print(f"Signal length: {n_days} days")

    periods = log_periods(10.0, 200.0, 50)
    print(f"Analyzing periods from {periods.min():.1f} to {periods.max():.1f} days")

    result = cwt(series, periods)
    print(f"CWT complete. Power shape: {result.power.shape}")

    time_center = n_days // 2
    power_at_center = result.power[:, time_center]
    peak_idx = np.argmax(power_at_center)
    peak_period = result.periods[peak_idx]
    print(f"\nDominant period detected: {peak_period:.1f} days (expected: {period_1})")

    sorted_indices = np.argsort(power_at_center)[::-1]
    print("\nTop 3 power peaks:")
    for i, idx in enumerate(sorted_indices[:3]):
        print(f"  {i+1}. Period: {result.periods[idx]:.1f} days, Power: {power_at_center[idx]:.2f}")

    surface_path = surface_3d(result, title="Synthetic Signal: 30 + 90 day periods")
    print(f"\n3D surface saved to: {surface_path}")

    scalogram_path = scalogram(result, title="Synthetic Signal Scalogram")
    print(f"Scalogram saved to: {scalogram_path}")


if __name__ == "__main__":
    main()
