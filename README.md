# coinlet

Continuous wavelet transforms for time series analysis — crypto prices, PMU data, and beyond.

## Quick Start

```bash
# Install with uv
uv add coinlet

# Or install with notebook support
uv add "coinlet[notebook]"
```

### Basic Usage

```python
import pandas as pd
from coinlet import load_csv, cwt, log_periods, scalogram, surface_3d

# Load data
series = load_csv("prices.csv", time_col="date", value_col="close")

# Define periods to analyze (7 days to 1 year, log-spaced)
periods = log_periods(7, 365, 50)

# Compute CWT
result = cwt(series, periods, wavelet="cmor1.5-1.0")

# Visualize
scalogram(result, show_coi=True)  # 2D heatmap
surface_3d(result)                 # Interactive 3D surface
```

### Preprocessing Options

```python
# Log returns (for price data)
result = cwt(series, periods, preprocess="log_return")

# Detrend (remove linear trend)
result = cwt(series, periods, preprocess="detrend")
```

### Available Wavelets

- `cmor1.5-1.0` (default) — Complex Morlet, good general-purpose choice
- `mexh` — Mexican hat, detects peaks and transients
- `gaus1` to `gaus8` — Gaussian derivatives

## Interactive Explorer (marimo)

The explorer notebook provides an interactive UI for wavelet analysis.

### Run Locally

```bash
# Edit mode (with live reload)
uv run marimo edit notebooks/explorer.py

# Run mode (read-only)
uv run marimo run notebooks/explorer.py
```

### Run in molab (Cloud)

> **Note for private repos**: molab's direct GitHub link requires the repo to be public.
> For private repos, download `notebooks/explorer.py` and upload it to
> [molab.io](https://molab.marimo.app) manually.

For public repos:

[![Open in molab](https://marimo.io/shield.svg)](https://molab.marimo.app/#github.com/jeunjetta/coinlet/blob/main/notebooks/explorer.py)

### Static Export (GitHub Pages)

The notebook can be exported as a static WASM site for sharing. This mode:
- Uses **cached data only** (bundled from `notebooks/public/` or `data/`)
- Does **not** support live WebSocket streaming
- Requires GitHub Pages to be enabled (private repos need paid plan)
- Publishes **publicly** even from a private repo

**Data bundling**: The CI workflow copies `data/*.parquet` to `notebooks/public/` before
export. marimo's `html-wasm` export bundles the `public/` folder with the notebook, so
the WASM build can read data locally without fetching from GitHub (which wouldn't work
for private repos anyway).

To deploy manually:
1. Enable Pages in repo Settings → Pages → Source: GitHub Actions
2. Go to Actions → "Deploy to GitHub Pages (Manual)" → Run workflow
3. Type "yes" to confirm public deployment

For live/private analysis, use molab or run locally.

## Understanding the Output

### Scalogram (2D Heatmap)
- **X-axis**: Time
- **Y-axis**: Period (log scale) — longer periods at top
- **Color**: Wavelet power — brighter = stronger signal at that period

### 3D Surface
Same data as a rotatable surface for exploring power distribution.

### Cone of Influence (COI)
The dashed line / shaded region marks where **edge effects** reduce reliability.
Values inside the COI are influenced by the series boundaries and should be
interpreted with caution.

**Example**: A ~4-year BTC market cycle, with data since ~2015, sits right at the
COI edge. This doesn't mean the cycle isn't real, but wavelet power at that period
is partially influenced by edge effects.

## Serialization & Caching

Results can be saved for later use:

```python
# Save to Parquet
result.to_parquet("data/btc_cwt.parquet")

# Load from Parquet
from coinlet import CWTResult
result = CWTResult.from_parquet("data/btc_cwt.parquet")

# Cache key for deduplication
key = result.cache_key()  # e.g., "a1b2c3d4e5f6g7h8"
```

## Data Layer

The `coinlet.data` subpackage provides data fetching, caching, and live streaming.

### Data Sources

```python
from datetime import datetime, timezone
from coinlet.data import CoinbaseHistorical, YahooFinanceSource, Granularity
from coinlet.data.cache import PriceCache, fetch_with_cache

# Coinbase Exchange (historical, no auth required)
source = CoinbaseHistorical()
df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

# Yahoo Finance (crypto, stocks, indices)
source = YahooFinanceSource()
df = source.fetch_historical("BTC-USD", Granularity.ONE_DAY, start, end)

# With caching (only fetches missing date ranges)
cache = PriceCache()
df = fetch_with_cache(cache, source, "BTC-USD", Granularity.ONE_DAY, start, end)
```

### CLI

```bash
# Fetch historical data
uv run coinlet fetch BTC-USD --granularity 1d --since 2015-01-01

# Stream live data (1 minute)
uv run coinlet stream BTC-USD ETH-USD --granularity 1m --duration 60
```

### Live Streaming

```python
from coinlet.data import CoinbaseLive, LiveDataManager, Granularity

manager = LiveDataManager(
    source=CoinbaseLive(),
    symbols=["BTC-USD"],
    granularity=Granularity.ONE_MINUTE,
    window_size=100,
)

# Per-bar callback for continuous updates
manager.on_bar(lambda bar: update_plot(bar))

# Rolling window snapshot for wavelet analysis
df = manager.get_snapshot()
```

### DuckDB Cache

The cache stores prices and wavelet results locally:

```python
from coinlet.data import PriceCache

cache = PriceCache()

# Wavelet results (keyed by CWTResult.cache_key())
if not cache.has_wavelet_result(result.cache_key()):
    cache.save_wavelet_result(
        cache_key=result.cache_key(),
        data_hash=cache.compute_data_hash(df),
        wavelet_type="morlet",
        params={"omega0": 6.0},
        result=result.to_parquet_bytes(),
    )
```

### WASM/Pyodide (for marimo notebooks)

```python
from coinlet.data.parquet import load_symbol

# Load bundled dataset (auto-detects path via mo.notebook_location())
df = load_symbol("BTC-USD")
df = load_symbol("ETH-USD")
```

Files to bundle for WASM export:
- `data/coinbase_BTC_USD_1d.parquet` (187 KB)
- `data/coinbase_ETH_USD_1d.parquet` (163 KB)

## Data Storage

| Data Type | Location | Git |
|-----------|----------|-----|
| Daily prices | `data/*.parquet` | ✓ Committed |
| Daily CWT results | `data/*.parquet` | ✓ Committed |
| Minute/hourly data | `.cache/coinlet/` | ✗ Ignored |
| DuckDB cache | `.cache/coinlet/` | ✗ Ignored |

Large datasets can be shared via GitHub Releases.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/
```

## License

MIT
