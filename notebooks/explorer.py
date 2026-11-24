# /// script
# requires-python = ">=3.11.5"
# dependencies = [
#     "coinlet",
#     "marimo",
#     "numpy",
#     "pandas",
#     "plotly",
#     "pywavelets",
#     "pyarrow",
# ]
#
# [tool.uv.sources]
# coinlet = { git = "https://github.com/jeunjetta/coinlet.git" }
# ///
"""
Wavelet Explorer - Interactive CWT analysis with coinlet.

Run locally:
    uv run marimo edit notebooks/explorer.py
    uv run marimo run notebooks/explorer.py

Molab notes:
    - Marimo's auto-installer maps ``import coinlet`` to PyPI (which has no
      coinlet). This notebook bootstraps via local ``src/`` or
      ``git+https://github.com/jeunjetta/coinlet.git`` and loads coinlet with
      ``importlib`` so the AST scanner does not trigger a PyPI install.
    - Data is searched in ``notebooks/public/``, ``data/``, ``../data/``, then
      downloaded into ``coinlet_data/`` (or ``COINLET_DATA_DIR``). In molab,
      prefer workspace / ``mo.persistent_cache`` paths — container files may reset.

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
    """Ensure coinlet is importable before any other cell loads it.

    Returns ``coinlet_source`` so marimo's DAG runs this cell first wherever
    that name is a dependency. Uses importlib (not ``import coinlet``) so
    marimo does not try ``uv pip install coinlet`` from PyPI.
    """
    import importlib
    import importlib.util
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    _GIT_URL = "git+https://github.com/jeunjetta/coinlet.git"
    _SRC_HINTS = (
        "../src",
        "src",
        "./src",
        "coinlet/src",
        "./coinlet/src",
        "../coinlet/src",
    )

    def _notebook_dir() -> Path:
        nb_dir_fn = getattr(mo, "notebook_dir", None)
        if callable(nb_dir_fn):
            nb_dir = nb_dir_fn()
            if nb_dir is not None:
                return Path(nb_dir)
        loc_fn = getattr(mo, "notebook_location", None)
        loc = loc_fn() if callable(loc_fn) else None
        return Path(loc).parent if loc else Path.cwd()

    def _find_bootstrap_file(nb_dir: Path, cwd: Path) -> Path | None:
        for root in (nb_dir, cwd):
            for hint in _SRC_HINTS:
                candidate = (root / hint / "coinlet" / "bootstrap.py").resolve()
                if candidate.is_file():
                    return candidate
        return None

    def _install_from_git() -> None:
        python = sys.executable
        uv = shutil.which("uv")
        if uv is not None:
            try:
                subprocess.run(
                    [uv, "pip", "install", "--python", python, _GIT_URL],
                    check=True,
                )
                importlib.invalidate_caches()
                return
            except (OSError, subprocess.CalledProcessError):
                pass
        subprocess.run(
            [python, "-m", "pip", "install", "--no-input", _GIT_URL],
            check=True,
        )
        importlib.invalidate_caches()

    def _load_bootstrap(nb_dir: Path, cwd: Path):
        """Return ``(module_or_None, installed_from_git)``."""
        boot_file = _find_bootstrap_file(nb_dir, cwd)
        if boot_file is not None:
            spec = importlib.util.spec_from_file_location(
                "_coinlet_nb_bootstrap",
                boot_file,
            )
            if spec is not None and spec.loader is not None:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod, False
        if importlib.util.find_spec("coinlet") is not None:
            return importlib.import_module("coinlet.bootstrap"), False
        if sys.platform == "emscripten":
            return None, False
        _install_from_git()
        return importlib.import_module("coinlet.bootstrap"), True

    nb_dir = _notebook_dir()
    cwd = Path.cwd()
    bootstrap, installed_from_git = _load_bootstrap(nb_dir, cwd)
    if bootstrap is None:
        coinlet_source = {
            "kind": "wasm",
            "detail": "Pyodide/WASM runtime — skip pip/uv install",
            "src_path": None,
        }
    elif installed_from_git:
        coinlet_source = {
            "kind": "github",
            "detail": f"Installed from {_GIT_URL}",
            "src_path": None,
        }
    else:
        result = bootstrap.ensure_coinlet(notebook_dir=nb_dir, cwd=cwd)
        coinlet_source = result.as_dict() if hasattr(result, "as_dict") else dict(result)

    kind = coinlet_source.get("kind", "unknown")
    detail = coinlet_source.get("detail", "")
    mo.callout(
        mo.md(
            f"""
            **coinlet bootstrap:** `{kind}`

            {detail}

            Data cache: local `data/` / `notebooks/public/` when present; otherwise
            downloads into `coinlet_data/` (override with `COINLET_DATA_DIR`).
            In molab, files outside persistent workspace storage may reset between
            sessions — use **Sync / Refresh data from GitHub** below if needed.
            """
        ),
        kind="success" if kind in {"repo", "installed", "github", "wasm"} else "warn",
    )
    return (coinlet_source,)


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
def __(coinlet_source):
    # Depend on coinlet_source so bootstrap always runs first.
    # importlib avoids marimo's static ``import coinlet`` → PyPI auto-install.
    import importlib

    import numpy as np
    import pandas as pd
    from pathlib import Path

    _ = coinlet_source
    ensure_cached_data = importlib.import_module("coinlet.data").ensure_cached_data

    return Path, ensure_cached_data, np, pd


@app.cell
def __(mo):
    refresh_data = mo.ui.run_button(label="Sync / Refresh data from GitHub")
    return (refresh_data,)


@app.cell
def __(Path, coinlet_source, ensure_cached_data, mo, refresh_data):
    _ = coinlet_source
    notebook_loc_fn = getattr(mo, "notebook_location", None)
    notebook_dir_fn = getattr(mo, "notebook_dir", None)
    if callable(notebook_dir_fn) and notebook_dir_fn() is not None:
        notebook_dir = Path(notebook_dir_fn())
    elif callable(notebook_loc_fn) and notebook_loc_fn():
        notebook_dir = Path(notebook_loc_fn()).parent
    else:
        notebook_dir = Path(".")

    force_refresh = bool(refresh_data.value)

    def _ensure() -> Path:
        return ensure_cached_data(
            notebook_dir=notebook_dir,
            force_refresh=force_refresh,
        )

    # mo.persistent_cache keeps the resolved directory across molab sessions when
    # available; force_refresh bypasses it so Sync always re-downloads.
    if force_refresh:
        data_dir = _ensure()
        cache_note = "Forced refresh — re-downloaded into persistent cache dir."
    else:
        try:
            with mo.persistent_cache("coinlet_data_dir_v1") as _cache:
                data_dir = _ensure()
            cache_note = (
                "Resolved via `mo.persistent_cache` when available "
                "(molab-friendly); falls back to `coinlet_data/` / local `data/`."
            )
        except Exception:
            data_dir = _ensure()
            cache_note = (
                "`mo.persistent_cache` unavailable — using "
                f"`{data_dir}` directly (local / WASM safe)."
            )
        # Container files may vanish between molab sessions even when the
        # persistent_cache hit restores the Path — re-ensure if empty.
        data_path = Path(data_dir)
        if not data_path.is_dir() or not any(data_path.glob("*.parquet")):
            data_dir = _ensure()
            cache_note += " Re-synced because cached path had no Parquet files."

    data_files = sorted(data_dir.glob("*.csv")) + sorted(data_dir.glob("*.parquet"))
    file_options = {f.name: str(f) for f in data_files} or {"demo (synthetic)": "demo"}
    file_list = ", ".join(f.name for f in data_files) if data_files else "(none — using demo)"

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

    mo.vstack(
        [
            mo.md("### Controls"),
            mo.callout(
                mo.md(
                    f"""
                    **Data directory:** `{data_dir.resolve() if data_dir.exists() else data_dir}`

                    **Files:** {file_list}

                    {cache_note}

                    coinlet loaded from: `{coinlet_source.get("kind")}` —
                    {coinlet_source.get("detail")}
                    """
                ),
                kind="info",
            ),
        ]
    )
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
def __(coinlet_source, mo):
    import importlib

    _ = coinlet_source
    live_runtime_supported = importlib.import_module(
        "coinlet.data.live_session"
    ).live_runtime_supported

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
def __(cached_series, coinlet_source, data_source):
    import importlib

    _ = coinlet_source
    live_session_mod = importlib.import_module("coinlet.data.live_session")
    types_mod = importlib.import_module("coinlet.data.types")
    LiveExplorerSession = live_session_mod.LiveExplorerSession
    infer_product_id = live_session_mod.infer_product_id
    Granularity = types_mod.Granularity

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
    coinlet_source,
    wavelet_type,
    preprocess_type,
    min_period,
    max_period,
    n_periods,
):
    import importlib

    _ = coinlet_source
    coinlet_mod = importlib.import_module("coinlet")
    cwt = coinlet_mod.cwt
    log_periods = coinlet_mod.log_periods

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
def __(coinlet_source, result, show_coi, plot_figs):
    import importlib

    _ = coinlet_source
    coinlet_mod = importlib.import_module("coinlet")
    create_scalogram_figure = coinlet_mod.create_scalogram_figure
    create_surface_figure = coinlet_mod.create_surface_figure
    update_scalogram_data = coinlet_mod.update_scalogram_data
    update_surface_data = coinlet_mod.update_surface_data

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
