# coinlet – Product Requirements Document

## Overview

**coinlet** is a small, readable Python package for continuous wavelet transforms (CWT) on time series data. Initially targeting crypto price analysis (daily BTC since 2015, then hourly/minute), the architecture is designed to later support streaming PMU (Phasor Measurement Unit) data through the same interface.

## Goals

1. **Simplicity**: Clean, readable code that electrical engineers and quants can understand and extend.
2. **Reusability**: Protocol-based data interface allows plugging in any data source (CSV, REST API, WebSocket streams).
3. **Scientific correctness**: Proper handling of sampling intervals, cone of influence, and real-time-unit periods.
4. **Visualization**: Interactive Plotly 3D surfaces and 2D scalograms for exploratory analysis.
5. **Caching**: Avoid redundant computation by caching raw data and CWT results in DuckDB.

## Non-Goals

- Real-time signal processing (batch analysis only for v1)
- Inverse wavelet transforms
- Statistical significance testing (future work)

## User Stories

### US-1: Load historical data
As an analyst, I want to load price data from a CSV file so I can perform wavelet analysis on historical prices.

### US-2: Run CWT with meaningful periods
As an engineer, I want to specify wavelet periods in real time units (days, hours) instead of raw sample indices so results are interpretable.

### US-3: Choose wavelets
As a researcher, I want to select different mother wavelets (Morlet, Mexican Hat, Gaussian) to compare their frequency localization properties.

### US-4: Visualize power spectrum
As an analyst, I want to view an interactive 3D surface plot (time × period × power) and a 2D heatmap to identify dominant cycles.

### US-5: Understand edge effects
As a user, I want the cone of influence clearly marked so I know where edge effects make results unreliable.

### US-6: Stream live data (future)
As a developer, I want a `Source` protocol so I can plug in live WebSocket feeds (Coinbase, PMU) without changing the transform code.

### US-7: Preprocess data
As an analyst, I want optional log-return and detrending preprocessing to remove trends and work with returns.

## Technical Requirements

### Package Structure
```
src/coinlet/
├── __init__.py
├── data.py       # CSV loader + Source protocol
├── transform.py  # CWT implementation
├── plot.py       # Plotly visualizations
└── utils.py      # Helpers (log-spaced periods, preprocessing)
```

### Dependencies
- Python ≥3.11.5 (managed with uv)
- PyWavelets (`pywt`) – CWT implementation
- pandas – Time series handling
- numpy – Numerical operations
- plotly – Interactive visualizations
- pyarrow – Parquet serialization
- duckdb – Local caching (future)

### Data Storage Strategy

**Committed to git (`data/`):**
- Daily price data as Parquet files (small, ~1MB for BTC since 2015)
- Pre-computed CWT results for key analyses (Parquet)
- Keep total committed data under 50MB

**Local cache (`.cache/coinlet/`, git-ignored):**
- Minute/hourly price data (too large for git)
- DuckDB cache file for prices and CWT results
- Results keyed by hash of: data range + wavelet + periods + preprocessing

**Large dataset sharing:**
- GitHub Releases for large snapshots (minute data, extensive results)
- Document download URLs in README

### Data Module (`coinlet.data`)
- `load_csv(path, time_col, value_col) -> pd.Series` with DatetimeIndex
- `Source` protocol: iterator interface yielding `(timestamp, value)` tuples
- `StreamBuffer`: accumulates Source samples into analyzable chunks

> **Note**: Coinbase/Yahoo fetching, live streaming modes, and DuckDB storage are
> implemented separately by Shiny Coin. This module provides only the protocol
> interface and minimal CSV loading.

### Transform Module (`coinlet.transform`)
- `cwt(series, periods, wavelet='cmor1.5-1.0', ...) -> CWTResult`
- `CWTResult` dataclass: times, periods, power, coi_mask
  - `cache_key()`: stable hash for caching (data range + wavelet + periods + preprocess)
  - `to_dataframe()` / `from_dataframe()`: serialize to/from DataFrame
  - `to_parquet(path)` / `from_parquet(path)`: direct Parquet I/O
- `log_periods(min_period, max_period, n)`: generate log-spaced periods
- Supported wavelets: `cmor` (complex Morlet), `mexh`, `gaus1-8`
- Automatic sampling interval detection from DatetimeIndex

### Plot Module (`coinlet.plot`)
- `surface_3d(result, log_period=True) -> str`: returns path to HTML file
- `scalogram(result, log_period=True, show_coi=True) -> str`: 2D heatmap HTML
- `create_surface_figure(result)` / `create_scalogram_figure(result)`: for notebook embedding
- `update_surface_data(fig, result)` / `update_scalogram_data(fig, result)`: for live mode
- Cone of influence shading on both visualizations

> **Future (Shiny Coin)**: Live mode with toggle between continuous plot updates
> and periodic rolling-window re-transform.

### Interactive Explorer (`notebooks/explorer.py`)
Marimo notebook with interactive controls:
- Data source selection (CSV/Parquet from `data/`)
- Wavelet type dropdown
- Period range sliders (min/max, log-spaced)
- Preprocessing toggle (log returns, detrend)
- Live mode placeholder (per-tick vs rolling window)
- Plotly 3D surface + 2D scalogram with COI

**Run modes**:
1. **Local**: `uv run marimo edit/run notebooks/explorer.py`
2. **molab**: Cloud notebooks at https://molab.marimo.io/github/jeunjetta/coinlet/blob/main/notebooks/explorer.py
3. **GitHub Pages**: Static WASM export (manual workflow, cached data only)

> **Note**: GitHub Pages on private repos requires a paid plan and publishes publicly.
> The static build cannot do live streaming—use molab or local for live mode.

### Examples
- `examples/synthetic_demo.py`: sine waves with known periods → verify recovery
- `examples/csv_demo.py`: load and analyze a sample CSV

## Testing Strategy

- **Unit tests**: Transform correctness with synthetic sine signals
- **Property**: Known sine periods must appear as power peaks
- **Edge cases**: Short series, irregular sampling, missing values

## Milestones

1. **M1: Core CWT** – Transform module with serialization + tests ✓ (this PR)
2. **M2: Data interface** – CSV loader + Source protocol ✓ (this PR)
3. **M3: Visualization** – Plotly 3D + 2D plots with update support ✓ (this PR)
4. **M4: Data infrastructure** – Coinbase/Yahoo fetch, DuckDB cache, live modes (Shiny Coin)
5. **M5: PMU streaming** – Real-time industrial data (future)

## Open Questions

- Should we add wavelet coherence for comparing two series?
- Statistical significance via Monte Carlo surrogates?
- Optimal rolling window size for live mode?

## Coordination Notes

**Module boundaries** (to avoid merge conflicts):
- `coinlet/data.py`: Source protocol, load_csv, StreamBuffer (this PR)
- `coinlet/transform.py`: cwt, CWTResult with serialization (this PR)
- `coinlet/plot.py`: Plotly visualizations with update support (this PR)
- `coinlet/store.py`: DuckDB cache, data fetching (Shiny Coin)
- `coinlet/live.py`: Live mode, streaming updates (Shiny Coin)
