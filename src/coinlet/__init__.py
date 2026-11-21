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
    "CWTResult",
    "Source",
    "StreamBuffer",
    "create_scalogram_figure",
    "create_surface_figure",
    "cwt",
    "load_csv",
    "log_periods",
    "scalogram",
    "surface_3d",
    "update_scalogram_data",
    "update_surface_data",
]
