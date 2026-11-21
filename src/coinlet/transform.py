"""Continuous wavelet transform implementation."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pywt


@dataclass
class CWTResult:
    """Result of a continuous wavelet transform.

    Attributes:
        times: Array of timestamps from the input series.
        periods: Array of periods used in the transform (same units as input).
        power: 2D array of shape (n_periods, n_times) containing wavelet power.
        coi_mask: Boolean mask where True indicates values outside cone of influence
                  (i.e., affected by edge effects).
        metadata: Optional dict with wavelet, preprocess, and other parameters.
    """

    times: np.ndarray
    periods: np.ndarray
    power: np.ndarray
    coi_mask: np.ndarray
    metadata: dict | None = None

    def cache_key(self) -> str:
        """Generate a stable hash key for caching.

        The key is derived from: time range, periods, wavelet, and preprocessing.
        """
        parts = [
            str(self.times[0]) if len(self.times) > 0 else "",
            str(self.times[-1]) if len(self.times) > 0 else "",
            str(len(self.times)),
            ",".join(f"{p:.6f}" for p in self.periods),
        ]
        if self.metadata:
            parts.append(self.metadata.get("wavelet") or "")
            parts.append(self.metadata.get("preprocess") or "")

        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dataframe(self) -> pd.DataFrame:
        """Serialize result to a DataFrame for storage.

        Returns a long-form DataFrame with columns: time, period, power, in_coi.
        Metadata is stored in DataFrame.attrs.
        """
        n_periods, n_times = self.power.shape
        times_repeated = np.tile(self.times, n_periods)
        periods_repeated = np.repeat(self.periods, n_times)
        power_flat = self.power.flatten()
        coi_flat = self.coi_mask.flatten()

        df = pd.DataFrame(
            {
                "time": times_repeated,
                "period": periods_repeated,
                "power": power_flat,
                "in_coi": coi_flat,
            }
        )
        if self.metadata:
            df.attrs["metadata"] = self.metadata
        return df

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "CWTResult":
        """Reconstruct CWTResult from a DataFrame."""
        times = df["time"].unique()
        periods = df["period"].unique()
        n_times = len(times)
        n_periods = len(periods)

        power = df["power"].values.reshape(n_periods, n_times)
        coi_mask = df["in_coi"].values.reshape(n_periods, n_times)
        metadata = df.attrs.get("metadata")

        return cls(
            times=times,
            periods=periods,
            power=power,
            coi_mask=coi_mask,
            metadata=metadata,
        )

    def to_parquet(self, path: str | Path) -> None:
        """Save result to a Parquet file."""
        import json

        import pyarrow as pa
        import pyarrow.parquet as pq

        df = self.to_dataframe()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pandas(df)

        if self.metadata:
            existing_meta = table.schema.metadata or {}
            new_meta = {
                **existing_meta,
                b"coinlet_metadata": json.dumps(self.metadata).encode(),
            }
            table = table.replace_schema_metadata(new_meta)

        pq.write_table(table, path)

    @classmethod
    def from_parquet(cls, path: str | Path) -> "CWTResult":
        """Load result from a Parquet file."""
        import json

        import pyarrow.parquet as pq

        path = Path(path)
        table = pq.read_table(path)
        df = table.to_pandas()

        metadata = None
        if table.schema.metadata and b"coinlet_metadata" in table.schema.metadata:
            meta_bytes = table.schema.metadata[b"coinlet_metadata"]
            if meta_bytes:
                metadata = json.loads(meta_bytes.decode())

        result = cls.from_dataframe(df)
        result.metadata = metadata
        return result


def log_periods(min_period: float, max_period: float, n: int) -> np.ndarray:
    """Generate logarithmically-spaced periods.

    Args:
        min_period: Minimum period.
        max_period: Maximum period.
        n: Number of periods to generate.

    Returns:
        Array of n log-spaced periods from min_period to max_period.
    """
    return np.geomspace(min_period, max_period, n)


def _detect_sampling_interval(series: pd.Series) -> float:
    """Detect the sampling interval from a DatetimeIndex.

    Returns interval in the same units as the index (typically days for daily data).
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("Series must have a DatetimeIndex")

    diffs = np.diff(series.index.values).astype("timedelta64[s]").astype(float)
    median_seconds = np.median(diffs)

    return median_seconds / 86400.0


def _compute_coi(periods: np.ndarray, n_times: int, dt: float) -> np.ndarray:
    """Compute the cone of influence mask.

    The COI marks regions where edge effects become significant. For the Morlet wavelet,
    the e-folding time is sqrt(2) * period. Points closer to the edge than this are
    in the COI.
    """
    coi_mask = np.zeros((len(periods), n_times), dtype=bool)
    time_axis = np.arange(n_times) * dt

    for i, period in enumerate(periods):
        e_folding = np.sqrt(2) * period
        coi_boundary = np.minimum(time_axis, time_axis[-1] - time_axis)
        coi_mask[i, :] = coi_boundary < e_folding

    return coi_mask


def _preprocess(series: pd.Series, method: str | None) -> pd.Series:
    """Apply preprocessing to the series."""
    if method is None:
        return series

    if method == "log_return":
        values = np.log(series.values[1:] / series.values[:-1])
        return pd.Series(values, index=series.index[1:])

    if method == "detrend":
        x = np.arange(len(series))
        coeffs = np.polyfit(x, series.values, 1)
        trend = np.polyval(coeffs, x)
        return pd.Series(series.values - trend, index=series.index)

    raise ValueError(f"Unknown preprocess method: {method}")


def cwt(
    series: pd.Series,
    periods: np.ndarray,
    wavelet: str = "cmor1.5-1.0",
    preprocess: str | None = None,
) -> CWTResult:
    """Compute continuous wavelet transform.

    Args:
        series: Input time series with DatetimeIndex.
        periods: Array of periods to analyze (in same time units as series index,
                 e.g., days for daily data).
        wavelet: Mother wavelet name. Options:
            - "cmor<B>-<C>": Complex Morlet with bandwidth B and center frequency C.
                            Default "cmor1.5-1.0" is good for most time series.
            - "mexh": Mexican hat wavelet (good for detecting peaks/transients).
            - "gaus<N>": Gaussian derivative of order N (1-8).
        preprocess: Optional preprocessing:
            - "log_return": Compute log returns (for price data).
            - "detrend": Remove linear trend.

    Returns:
        CWTResult containing times, periods, power spectrum, and COI mask.

    Example:
        >>> series = load_csv("prices.csv", "date", "close")
        >>> periods = log_periods(7, 365, 50)  # 1 week to 1 year
        >>> result = cwt(series, periods)
        >>> surface_3d(result)  # Visualize
    """
    series = _preprocess(series, preprocess)

    dt = _detect_sampling_interval(series)

    scales = periods / dt

    data = series.values
    if np.isnan(data).any():
        data = pd.Series(data).interpolate().values

    coefficients, _ = pywt.cwt(data, scales, wavelet, sampling_period=dt)

    power = np.abs(coefficients) ** 2

    times = series.index.values
    coi_mask = _compute_coi(periods, len(times), dt)

    return CWTResult(
        times=times,
        periods=periods.copy(),
        power=power,
        coi_mask=coi_mask,
        metadata={
            "wavelet": wavelet,
            "preprocess": preprocess,
        },
    )
