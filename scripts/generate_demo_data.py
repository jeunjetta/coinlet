#!/usr/bin/env python3
"""Generate demo price data with known periodicities."""

import numpy as np
import pandas as pd

np.random.seed(42)

n_days = 365 * 3
dates = pd.date_range("2021-01-01", periods=n_days, freq="D")
t = np.arange(n_days)

trend = 100 * np.exp(0.0003 * t)
cycle_30d = 5 * np.sin(2 * np.pi * t / 30)
cycle_90d = 10 * np.sin(2 * np.pi * t / 90)
cycle_365d = 20 * np.sin(2 * np.pi * t / 365)
noise = np.random.randn(n_days) * 3

price = trend + cycle_30d + cycle_90d + cycle_365d + noise
price = np.maximum(price, 1)

df = pd.DataFrame({"date": dates, "price": price.round(2)})
df.to_csv("data/demo_prices.csv", index=False)
print(f"Generated {len(df)} rows to data/demo_prices.csv")
print(f"Known periods: 30 days, 90 days, 365 days")
print(f"Date range: {dates[0].date()} to {dates[-1].date()}")
