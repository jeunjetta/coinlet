#!/usr/bin/env python3
"""CSV data demo: analyze time series from a CSV file.

This demo shows how to load and analyze real data from a CSV file.
A sample data file is included in examples/data/sample_prices.csv.
"""

import argparse
from pathlib import Path

from coinlet import cwt, load_csv, log_periods, scalogram, surface_3d


def main():
    parser = argparse.ArgumentParser(description="Analyze time series from CSV")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).parent / "data" / "sample_prices.csv",
        help="Path to CSV file",
    )
    parser.add_argument("--time-col", default="date", help="Name of timestamp column")
    parser.add_argument("--value-col", default="price", help="Name of value column")
    parser.add_argument("--min-period", type=float, default=7.0, help="Minimum period (days)")
    parser.add_argument("--max-period", type=float, default=365.0, help="Maximum period (days)")
    parser.add_argument("--n-periods", type=int, default=50, help="Number of periods")
    parser.add_argument(
        "--preprocess", choices=["none", "log_return", "detrend"], default="none"
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}")
        print("\nTo use this demo, provide a CSV file with columns:")
        print(f"  - {args.time_col}: timestamps (e.g., '2020-01-01')")
        print(f"  - {args.value_col}: numeric values")
        print("\nExample:")
        print(f"  python csv_demo.py --file my_data.csv --time-col date --value-col close")
        return

    print(f"Loading data from: {args.file}")
    series = load_csv(args.file, args.time_col, args.value_col)
    print(f"Loaded {len(series)} data points")
    print(f"Date range: {series.index[0]} to {series.index[-1]}")

    periods = log_periods(args.min_period, args.max_period, args.n_periods)
    print(f"\nAnalyzing periods from {periods.min():.1f} to {periods.max():.1f} days")

    preprocess = args.preprocess if args.preprocess != "none" else None
    if preprocess:
        print(f"Preprocessing: {preprocess}")

    result = cwt(series, periods, preprocess=preprocess)
    print(f"CWT complete. Power shape: {result.power.shape}")

    print("\nGenerating visualizations...")
    surface_path = surface_3d(result, title=f"CWT: {args.file.name}")
    print(f"  3D surface: {surface_path}")

    scalogram_path = scalogram(result, title=f"Scalogram: {args.file.name}")
    print(f"  Scalogram: {scalogram_path}")


if __name__ == "__main__":
    main()
