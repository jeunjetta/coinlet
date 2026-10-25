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
