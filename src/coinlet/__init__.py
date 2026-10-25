"""coinlet - Continuous wavelet transforms for time series analysis."""

from coinlet.data import Source, StreamBuffer, load_csv
from coinlet.plot import (
    create_scalogram_figure,
    create_surface_figure,
    scalogram,
    surface_3d,
    update_scalogram_data,
    update_surface_data,
)
from coinlet.transform import CWTResult, cwt, log_periods

__version__ = "0.1.0"
__all__ = [
    "load_csv",
    "Source",
    "StreamBuffer",
    "cwt",
    "CWTResult",
    "log_periods",
    "surface_3d",
    "scalogram",
    "create_surface_figure",
    "create_scalogram_figure",
    "update_surface_data",
    "update_scalogram_data",
]
