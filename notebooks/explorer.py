# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "coinlet @ git+https://github.com/jeunjetta/coinlet",
#     "marimo",
#     "numpy",
#     "pandas",
#     "plotly",
#     "pywavelets",
#     "pyarrow",
# ]
# ///
"""
Wavelet Explorer - Interactive CWT analysis with coinlet.

Run locally:
    uv run marimo edit notebooks/explorer.py
    uv run marimo run notebooks/explorer.py

For static WASM export (cached data only):
    uv run marimo export html-wasm --mode run notebooks/explorer.py -o dist/explorer.html
"""

import marimo

__generated_with = "0.8.0"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
def __(mo):
    mo.md(
        """
        # 🌊 Wavelet Explorer

        Interactive continuous wavelet transform (CWT) analysis using **coinlet**.

        Explore periodicities in time series data with different wavelets and parameters.
        The **cone of influence** (COI) marks edge regions where results are less reliable.
        """
    )
    return


@app.cell
def __():
    import numpy as np
    import pandas as pd
    from pathlib import Path

    from coinlet.data import ensure_cached_data

    return Path, ensure_cached_data, np, pd


@app.cell
def __(mo):
    refresh_data = mo.ui.run_button(label="Refresh cached data")
    return (refresh_data,)


@app.cell
def __(Path, ensure_cached_data, mo, refresh_data):
    notebook_loc = mo.notebook_location()
    notebook_dir = Path(notebook_loc).parent if notebook_loc else Path(".")

    data_dir = ensure_cached_data(
        notebook_dir=notebook_dir,
        force_refresh=bool(refresh_data.value),
    )
    data_files = sorted(data_dir.glob("*.csv")) + sorted(data_dir.glob("*.parquet"))
    file_options = {f.name: str(f) for f in data_files} or {"demo (synthetic)": "demo"}

    data_source = mo.ui.dropdown(
        options=file_options,
        value=next(iter(file_options)),
        label="Data source",
    )

    wavelet_type = mo.ui.dropdown(
        options={
            "Complex Morlet (cmor1.5-1.0)": "cmor1.5-1.0",
            "Mexican Hat (mexh)": "mexh",
            "Gaussian 1 (gaus1)": "gaus1",
            "Gaussian 2 (gaus2)": "gaus2",
        },
        value="Complex Morlet (cmor1.5-1.0)",
        label="Wavelet",
    )

    preprocess_type = mo.ui.dropdown(
        options={
            "None": "none",
            "Log Returns": "log_return",
            "Detrend": "detrend",
        },
        value="None",
        label="Preprocessing",
    )

    mo.md(f"### Controls\n\nData directory: `{data_dir}`")
    return data_dir, data_files, data_source, file_options, preprocess_type, wavelet_type


@app.cell
def __(mo):
    min_period = mo.ui.slider(
        start=1, stop=100, value=7, step=1, label="Min period (days)"
    )
    max_period = mo.ui.slider(
        start=30, stop=730, value=365, step=10, label="Max period (days)"
    )
    n_periods = mo.ui.slider(
        start=10, stop=100, value=50, step=5, label="Number of periods"
    )

    show_coi = mo.ui.checkbox(value=True, label="Show cone of influence")

    return max_period, min_period, n_periods, show_coi


@app.cell
def __(data_source, mo, preprocess_type, refresh_data, wavelet_type):
    mo.hstack(
        [data_source, wavelet_type, preprocess_type, refresh_data],
        justify="start",
        gap=1,
    )
    return


@app.cell
def __(max_period, min_period, mo, n_periods, show_coi):
    mo.hstack(
        [min_period, max_period, n_periods, show_coi],
        justify="start",
        gap=1,
    )
    return


@app.cell
def __(mo):
    live_mode = mo.ui.dropdown(
        options={
            "Off (static analysis)": "off",
            "Per-tick (placeholder)": "per_tick",
            "Rolling window (placeholder)": "rolling",
        },
        value="Off (static analysis)",
        label="Live mode",
    )

    mo.callout(
        mo.md(
            f"""
            **Live mode**: {live_mode}

            *Per-tick and rolling window modes require a live data source
            (Coinbase WebSocket). These will be wired by a teammate's Source implementation.*
            """
        ),
        kind="info",
    )
    return (live_mode,)


@app.cell
def __(data_source, np, pd, Path):
    def load_data(source_path: str) -> pd.Series:
        """Load data from CSV/Parquet or generate demo data."""
        path = Path(source_path)

        if path.exists():
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path)

            time_col = next(
                (c for c in df.columns if c.lower() in ("date", "time", "timestamp")),
                df.columns[0],
            )
            value_col = next(
                (c for c in df.columns if c.lower() in ("price", "close", "value")),
                df.columns[1] if len(df.columns) > 1 else df.columns[0],
            )

            df[time_col] = pd.to_datetime(df[time_col])
            return pd.Series(df[value_col].values, index=df[time_col]).sort_index()

        n_days = 365 * 2
        dates = pd.date_range("2022-01-01", periods=n_days, freq="D")
        t = np.arange(n_days)
        trend = 100 * np.exp(0.0002 * t)
        cycles = (
            5 * np.sin(2 * np.pi * t / 30)
            + 10 * np.sin(2 * np.pi * t / 90)
            + 15 * np.sin(2 * np.pi * t / 365)
        )
        noise = np.random.randn(n_days) * 2
        return pd.Series(trend + cycles + noise, index=dates)

    series = load_data(data_source.value)
    return load_data, series


@app.cell
def __(mo, series):
    mo.md(
        f"""
        ### Data Summary

        - **Points**: {len(series):,}
        - **Date range**: {series.index[0].date()} to {series.index[-1].date()}
        - **Value range**: {series.min():.2f} to {series.max():.2f}
        """
    )
    return


@app.cell
def __(series, wavelet_type, preprocess_type, min_period, max_period, n_periods):
    from coinlet import cwt, log_periods

    periods = log_periods(
        float(min_period.value),
        float(max_period.value),
        int(n_periods.value),
    )

    preprocess = preprocess_type.value if preprocess_type.value != "none" else None

    result = cwt(
        series,
        periods,
        wavelet=wavelet_type.value,
        preprocess=preprocess,
    )
    return cwt, log_periods, periods, preprocess, result


@app.cell
def __(mo, result):
    mo.md(
        f"""
        ### Transform Result

        - **Cache key**: `{result.cache_key()}`
        - **Power shape**: {result.power.shape} (periods × times)
        - **Wavelet**: {result.metadata.get('wavelet', 'N/A')}
        """
    )
    return


@app.cell
def __(result, show_coi):
    from coinlet import create_scalogram_figure, create_surface_figure

    scalogram_fig = create_scalogram_figure(
        result,
        log_period=True,
        show_coi=show_coi.value,
        title="Wavelet Scalogram (2D)",
    )
    return create_scalogram_figure, create_surface_figure, scalogram_fig


@app.cell
def __(mo, scalogram_fig):
    mo.md("### Scalogram (2D Heatmap)")
    return


@app.cell
def __(mo, scalogram_fig):
    mo.ui.plotly(scalogram_fig)
    return


@app.cell
def __(result):
    from coinlet import create_surface_figure

    surface_fig = create_surface_figure(
        result,
        log_period=True,
        title="Wavelet Power Spectrum (3D)",
    )
    return (surface_fig,)


@app.cell
def __(mo):
    mo.md("### 3D Surface")
    return


@app.cell
def __(mo, surface_fig):
    mo.ui.plotly(surface_fig)
    return


@app.cell
def __(mo):
    mo.md(
        """
        ---

        ### Understanding the Output

        - **Scalogram**: Time on x-axis, period (log scale) on y-axis, power as color intensity.
        - **3D Surface**: Same data as a rotatable surface for exploring power distribution.
        - **Cone of Influence (COI)**: Dashed line / shaded region marks where edge effects
          reduce reliability. For a ~4-year BTC cycle with data since 2015, this period
          sits at the COI edge—interpret with caution.
        - **Periods**: Log-spaced from min to max. Peaks in power indicate dominant cycles.

        *Built with [coinlet](https://github.com/jeunjetta/coinlet) and [marimo](https://marimo.io)*
        """
    )
    return


if __name__ == "__main__":
    app.run()
