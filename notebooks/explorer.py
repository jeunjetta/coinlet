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

Live mode (local or molab — public Coinbase data, no API keys):
    1. Select a Coinbase Parquet source (e.g. coinbase_BTC_USD_1d.parquet).
    2. Set Live mode to "Per-tick" to append Exchange WebSocket ticker prices
       and refresh the scalogram/surface via update_*_data().
    3. Set Live mode to "Rolling window" to periodically fetch public REST
       candles, keep a trailing window, and re-run the wavelet transform.
    4. Use the refresh control to choose the poll interval (1–10s).
    Status callouts show connecting / live / fallback; failures keep cached data.

For static WASM export (cached Parquet only — live mode is disabled):
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
    from coinlet.data.live_session import live_runtime_supported

    live_ok, live_capability_reason = live_runtime_supported()

    live_mode = mo.ui.dropdown(
        options={
            "Off (static analysis)": "off",
            "Per-tick (Coinbase ticker)": "per_tick",
            "Rolling window (Coinbase candles)": "rolling",
        },
        value="Off (static analysis)",
        label="Live mode",
    )

    live_refresh = mo.ui.refresh(
        options=[1, 2, 5, 10],
        default_interval=2,
        label="Live refresh (seconds)",
    )

    capability_note = (
        live_capability_reason
        if not live_ok
        else (
            "Per-tick uses the public Coinbase Exchange WebSocket ticker. "
            "Rolling window periodically refreshes public REST candles and "
            "re-runs the wavelet transform on a trailing window. "
            "Live points append to cached Parquet history (no plot reset)."
        )
    )

    mo.vstack(
        [
            mo.hstack([live_mode, live_refresh], justify="start", gap=1),
            mo.callout(
                mo.md(
                    f"""
                    **Live mode** (public Coinbase market data only — no API keys)

                    {capability_note}
                    """
                ),
                kind="warn" if not live_ok else "info",
            ),
        ]
    )
    return live_mode, live_refresh, live_ok, live_capability_reason


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

    cached_series = load_data(data_source.value)
    return load_data, cached_series


@app.cell
def __(cached_series, data_source):
    from coinlet.data.live_session import LiveExplorerSession, infer_product_id
    from coinlet.data.types import Granularity

    product_id = infer_product_id(data_source.value)
    live_session = LiveExplorerSession(
        cached_series=cached_series,
        product_id=product_id,
        granularity=Granularity.ONE_DAY,
        window_size=min(512, max(64, len(cached_series))),
    )
    return live_session, product_id


@app.cell
def __(live_session, live_mode, live_refresh, live_ok):
    # Depend on refresh so per-tick / rolling modes re-poll on an interval.
    _ = live_refresh.value

    desired = live_mode.value if live_ok else "off"
    if live_session.mode != desired:
        live_session.set_mode(desired)

    analysis_series, live_status = live_session.poll()
    return analysis_series, live_status


@app.cell
def __(mo, analysis_series, live_status, product_id):
    status_kind = {
        "idle": "neutral",
        "connecting": "info",
        "live": "success",
        "reconnecting": "warn",
        "fallback": "warn",
        "unsupported": "danger",
    }.get(live_status.state, "neutral")

    mo.vstack(
        [
            mo.md(
                f"""
                ### Data Summary

                - **Product**: `{product_id}`
                - **Points (analysis)**: {len(analysis_series):,}
                - **Date range**: {analysis_series.index[0]} → {analysis_series.index[-1]}
                - **Value range**: {analysis_series.min():.2f} to {analysis_series.max():.2f}
                """
            ),
            mo.callout(
                mo.md(
                    f"**Live status** (`{live_status.mode}` / `{live_status.state}`): "
                    f"{live_status.message}"
                ),
                kind=status_kind,
            ),
        ]
    )
    return


@app.cell
def __(
    analysis_series,
    wavelet_type,
    preprocess_type,
    min_period,
    max_period,
    n_periods,
):
    from coinlet import cwt, log_periods

    periods = log_periods(
        float(min_period.value),
        float(max_period.value),
        int(n_periods.value),
    )

    preprocess = preprocess_type.value if preprocess_type.value != "none" else None

    result = cwt(
        analysis_series,
        periods,
        wavelet=wavelet_type.value,
        preprocess=preprocess,
    )
    return cwt, log_periods, periods, preprocess, result


@app.cell
def __(mo, result, live_status):
    mo.md(
        f"""
        ### Transform Result

        - **Cache key**: `{result.cache_key()}`
        - **Power shape**: {result.power.shape} (periods × times)
        - **Wavelet**: {result.metadata.get('wavelet', 'N/A')}
        - **Live ticks applied**: {live_status.tick_count}
        """
    )
    return


@app.cell
def __():
    # Mutable holders so live refreshes can call update_*_data() in place
    # instead of discarding the Plotly figures on every tick.
    plot_figs = {"scalogram": None, "surface": None, "show_coi": None, "n_periods": None}
    return (plot_figs,)


@app.cell
def __(result, show_coi, plot_figs):
    from coinlet import (
        create_scalogram_figure,
        create_surface_figure,
        update_scalogram_data,
        update_surface_data,
    )

    recreate = (
        plot_figs["scalogram"] is None
        or plot_figs["show_coi"] != show_coi.value
        or plot_figs["n_periods"] != len(result.periods)
    )

    if recreate:
        plot_figs["scalogram"] = create_scalogram_figure(
            result,
            log_period=True,
            show_coi=show_coi.value,
            title="Wavelet Scalogram (2D)",
        )
        plot_figs["surface"] = create_surface_figure(
            result,
            log_period=True,
            title="Wavelet Power Spectrum (3D)",
        )
        plot_figs["show_coi"] = show_coi.value
        plot_figs["n_periods"] = len(result.periods)
    else:
        update_scalogram_data(
            plot_figs["scalogram"],
            result,
            show_coi=show_coi.value,
        )
        update_surface_data(plot_figs["surface"], result)

    scalogram_fig = plot_figs["scalogram"]
    surface_fig = plot_figs["surface"]
    return (
        create_scalogram_figure,
        create_surface_figure,
        update_scalogram_data,
        update_surface_data,
        scalogram_fig,
        surface_fig,
    )


@app.cell
def __(mo, scalogram_fig):
    mo.md("### Scalogram (2D Heatmap)")
    return


@app.cell
def __(mo, scalogram_fig):
    mo.ui.plotly(scalogram_fig)
    return


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
