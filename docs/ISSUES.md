# GitHub Issues (from PRD)

Create these issues manually in GitHub:

---

## Issue 1: Core CWT transform module with wavelet selection
**Labels**: `enhancement`

### Description
Implement the core continuous wavelet transform (CWT) module.

### Requirements
- `cwt(series, periods, wavelet='cmor1.5-1.0')` function taking periods in real time units
- `CWTResult` dataclass with times, periods, power, and cone of influence mask
- `log_periods(min_period, max_period, n)` helper for log-spaced periods
- Support multiple wavelets: complex Morlet (default), Mexican hat, Gaussian derivatives
- Automatic sampling interval detection from DatetimeIndex
- Optional log-return and detrend preprocessing

### Acceptance Criteria
- [ ] Synthetic sine signals with known periods are correctly recovered
- [ ] Cone of influence is computed correctly
- [ ] Multiple wavelets work interchangeably

---

## Issue 2: Data loading module with CSV support and Source protocol
**Labels**: `enhancement`

### Description
Implement the data loading module with CSV support and a streaming protocol.

### Requirements
- `load_csv(path, time_col, value_col)` returning pandas Series with DatetimeIndex
- `Source` protocol: iterator interface for streaming data sources
- `StreamBuffer` for accumulating streamed samples

### Acceptance Criteria
- [ ] CSV files load correctly with datetime parsing
- [ ] Source protocol is well-documented and easy to implement

---

## Issue 3: Coinbase data loader (historical CSV + live stream)
**Labels**: `enhancement`, `help wanted`
**Assignee**: Shiny Coin

### Description
Implement Coinbase data integration for both historical and live data.

**Note**: This issue is assigned to teammate **Shiny Coin** for implementation.

### Requirements
- Historical data: Download and parse Coinbase historical price CSVs
- Yahoo Finance fallback for historical data
- Live stream: WebSocket connection to Coinbase for real-time prices
- Implement the `Source` protocol from `coinlet.data`
- Live mode toggle: continuous plot updates vs periodic rolling-window re-transform

### Acceptance Criteria
- [ ] Can fetch BTC/USD historical data (daily since 2015)
- [ ] Support for hourly/minute data
- [ ] Live WebSocket stream works with StreamBuffer
- [ ] Per-tick and rolling-window streaming modes
- [ ] Graceful reconnection on connection loss

---

## Issue 7: DuckDB caching for prices and CWT results
**Labels**: `enhancement`
**Assignee**: Shiny Coin

### Description
Implement persistent caching using DuckDB to avoid recomputing CWT transforms.

**Note**: This issue is assigned to teammate **Shiny Coin** for implementation.

### Requirements
- Store raw price data in DuckDB (or query Parquet directly)
- Cache CWT results keyed by `CWTResult.cache_key()` (hash of data range + wavelet + periods + preprocessing)
- Daily data: commit as Parquet in `data/` folder
- Minute/hourly data: store in `.cache/coinlet/` (git-ignored)
- GitHub Releases option for sharing large snapshots

### Data Size Guidelines
- Keep committed data under 50MB total
- Daily BTC since 2015: ~1MB Parquet
- Minute data: local cache only

### Acceptance Criteria
- [ ] Cache lookup by key before computing CWT
- [ ] Automatic cache invalidation on parameter change
- [ ] Parquet export/import works with DuckDB
- [ ] Clear separation from transform module

---

## Issue 4: Visualization module with 3D surface and 2D scalogram
**Labels**: `enhancement`

### Description
Implement interactive Plotly visualizations for CWT results.

### Requirements
- `surface_3d(result)`: Interactive 3D surface (time × log-period × power)
- `scalogram(result)`: 2D heatmap with cone of influence shading
- Export to HTML files

### Acceptance Criteria
- [ ] 3D surface is interactive and rotatable
- [ ] 2D scalogram clearly shows power distribution
- [ ] Cone of influence is visually marked

---

## Issue 5: CI/CD pipeline with ruff and pytest
**Labels**: `enhancement`

### Description
Set up GitHub Actions for continuous integration.

### Requirements
- Lint with ruff
- Test with pytest
- Run on push and PR to main

---

## Issue 6: Documentation and examples
**Labels**: `documentation`

### Description
Create comprehensive documentation and example scripts.

### Requirements
- README with quick start guide
- Example: synthetic signal analysis
- Example: CSV file analysis
- Caveat about 4-year BTC cycle at COI edge

---

## Issue 8: Live mode integration in marimo explorer
**Labels**: `enhancement`
**Assignee**: Shiny Coin

### Description
Wire the live mode toggle in the marimo explorer to actual streaming data sources.

**Note**: This issue is assigned to teammate **Shiny Coin** for implementation.

### Requirements
- Connect per-tick mode to Coinbase WebSocket Source
- Connect rolling-window mode to periodic re-transform
- Update plots in real-time using `update_surface_data()` / `update_scalogram_data()`
- Handle reconnection gracefully

### Acceptance Criteria
- [ ] Per-tick mode updates plot on each new price
- [ ] Rolling-window mode re-computes CWT periodically
- [ ] Smooth transitions between cached and live data
