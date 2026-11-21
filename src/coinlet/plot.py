"""Visualization functions for CWT results."""

from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from coinlet.transform import CWTResult


def surface_3d(
    result: CWTResult,
    output_dir: str | Path = ".",
    filename: str = "cwt_surface.html",
    log_period: bool = True,
    title: str = "Wavelet Power Spectrum",
) -> str:
    """Create an interactive 3D surface plot of wavelet power.

    Args:
        result: CWTResult from cwt().
        output_dir: Directory to save the HTML file.
        filename: Output filename.
        log_period: Whether to use log scale for period axis.
        title: Plot title.

    Returns:
        Path to the saved HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    times_numeric = np.arange(len(result.times))
    periods_plot = np.log10(result.periods) if log_period else result.periods

    time_labels = [str(t)[:10] for t in result.times]
    tick_indices = np.linspace(0, len(time_labels) - 1, min(10, len(time_labels)), dtype=int)

    fig = go.Figure(
        data=[
            go.Surface(
                x=times_numeric,
                y=periods_plot,
                z=result.power,
                colorscale="Viridis",
                colorbar={"title": "Power"},
            )
        ]
    )

    period_ticks = result.periods[:: max(1, len(result.periods) // 6)]
    period_tick_vals = np.log10(period_ticks) if log_period else period_ticks

    fig.update_layout(
        title=title,
        scene={
            "xaxis": {
                "title": "Time",
                "tickmode": "array",
                "tickvals": times_numeric[tick_indices],
                "ticktext": [time_labels[i] for i in tick_indices],
            },
            "yaxis": {
                "title": "Period (log)" if log_period else "Period",
                "tickmode": "array",
                "tickvals": period_tick_vals,
                "ticktext": [f"{p:.1f}" for p in period_ticks],
            },
            "zaxis": {"title": "Power"},
        },
        width=900,
        height=700,
    )

    output_path = output_dir / filename
    fig.write_html(str(output_path))
    return str(output_path)


def scalogram(
    result: CWTResult,
    output_dir: str | Path = ".",
    filename: str = "cwt_scalogram.html",
    log_period: bool = True,
    show_coi: bool = True,
    title: str = "Wavelet Scalogram",
) -> str:
    """Create a 2D heatmap (scalogram) of wavelet power.

    Args:
        result: CWTResult from cwt().
        output_dir: Directory to save the HTML file.
        filename: Output filename.
        log_period: Whether to use log scale for period axis.
        show_coi: Whether to shade the cone of influence.
        title: Plot title.

    Returns:
        Path to the saved HTML file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    times_numeric = np.arange(len(result.times))
    periods_plot = np.log10(result.periods) if log_period else result.periods

    time_labels = [str(t)[:10] for t in result.times]
    tick_indices = np.linspace(0, len(time_labels) - 1, min(10, len(time_labels)), dtype=int)

    power_display = result.power.copy()
    if show_coi:
        power_display = np.where(result.coi_mask, power_display * 0.3, power_display)

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=times_numeric,
            y=periods_plot,
            z=power_display,
            colorscale="Viridis",
            colorbar={"title": "Power"},
        )
    )

    if show_coi:
        coi_boundary = _compute_coi_boundary(result.periods, len(result.times))
        coi_y = np.log10(coi_boundary) if log_period else coi_boundary
        coi_y = np.clip(coi_y, periods_plot.min(), periods_plot.max())

        fig.add_trace(
            go.Scatter(
                x=times_numeric,
                y=coi_y,
                mode="lines",
                line={"color": "white", "width": 2, "dash": "dash"},
                name="Cone of Influence",
            )
        )

    period_ticks = result.periods[:: max(1, len(result.periods) // 6)]
    period_tick_vals = np.log10(period_ticks) if log_period else period_ticks

    fig.update_layout(
        title=title,
        xaxis={
            "title": "Time",
            "tickmode": "array",
            "tickvals": times_numeric[tick_indices],
            "ticktext": [time_labels[i] for i in tick_indices],
        },
        yaxis={
            "title": "Period (log)" if log_period else "Period",
            "tickmode": "array",
            "tickvals": period_tick_vals,
            "ticktext": [f"{p:.1f}" for p in period_ticks],
        },
        width=900,
        height=500,
    )

    output_path = output_dir / filename
    fig.write_html(str(output_path))
    return str(output_path)


def _compute_coi_boundary(periods: np.ndarray, n_times: int) -> np.ndarray:
    """Compute the COI boundary curve (period at which COI touches each time point)."""
    dt = 1.0
    time_axis = np.arange(n_times) * dt
    edge_distance = np.minimum(time_axis, time_axis[-1] - time_axis)
    coi_boundary = edge_distance / np.sqrt(2)
    coi_boundary = np.clip(coi_boundary, periods.min(), periods.max())
    return coi_boundary


def create_surface_figure(
    result: CWTResult,
    log_period: bool = True,
    title: str = "Wavelet Power Spectrum",
) -> go.Figure:
    """Create a 3D surface figure without saving.

    Use this for embedding in notebooks (marimo) or live updates.
    """
    times_numeric = np.arange(len(result.times))
    periods_plot = np.log10(result.periods) if log_period else result.periods

    time_labels = [str(t)[:10] for t in result.times]
    tick_indices = np.linspace(0, len(time_labels) - 1, min(10, len(time_labels)), dtype=int)

    fig = go.Figure(
        data=[
            go.Surface(
                x=times_numeric,
                y=periods_plot,
                z=result.power,
                colorscale="Viridis",
                colorbar={"title": "Power"},
            )
        ]
    )

    period_ticks = result.periods[:: max(1, len(result.periods) // 6)]
    period_tick_vals = np.log10(period_ticks) if log_period else period_ticks

    fig.update_layout(
        title=title,
        scene={
            "xaxis": {
                "title": "Time",
                "tickmode": "array",
                "tickvals": times_numeric[tick_indices].tolist(),
                "ticktext": [time_labels[i] for i in tick_indices],
            },
            "yaxis": {
                "title": "Period (log)" if log_period else "Period",
                "tickmode": "array",
                "tickvals": period_tick_vals.tolist(),
                "ticktext": [f"{p:.1f}" for p in period_ticks],
            },
            "zaxis": {"title": "Power"},
        },
        width=800,
        height=600,
    )
    return fig


def create_scalogram_figure(
    result: CWTResult,
    log_period: bool = True,
    show_coi: bool = True,
    title: str = "Wavelet Scalogram",
) -> go.Figure:
    """Create a 2D scalogram figure without saving.

    Use this for embedding in notebooks (marimo) or live updates.
    """
    times_numeric = np.arange(len(result.times))
    periods_plot = np.log10(result.periods) if log_period else result.periods

    time_labels = [str(t)[:10] for t in result.times]
    tick_indices = np.linspace(0, len(time_labels) - 1, min(10, len(time_labels)), dtype=int)

    power_display = result.power.copy()
    if show_coi:
        power_display = np.where(result.coi_mask, power_display * 0.3, power_display)

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=times_numeric,
            y=periods_plot,
            z=power_display,
            colorscale="Viridis",
            colorbar={"title": "Power"},
        )
    )

    if show_coi:
        coi_boundary = _compute_coi_boundary(result.periods, len(result.times))
        coi_y = np.log10(coi_boundary) if log_period else coi_boundary
        coi_y = np.clip(coi_y, periods_plot.min(), periods_plot.max())

        fig.add_trace(
            go.Scatter(
                x=times_numeric,
                y=coi_y,
                mode="lines",
                line={"color": "white", "width": 2, "dash": "dash"},
                name="Cone of Influence",
            )
        )

    period_ticks = result.periods[:: max(1, len(result.periods) // 6)]
    period_tick_vals = np.log10(period_ticks) if log_period else period_ticks

    fig.update_layout(
        title=title,
        xaxis={
            "title": "Time",
            "tickmode": "array",
            "tickvals": times_numeric[tick_indices].tolist(),
            "ticktext": [time_labels[i] for i in tick_indices],
        },
        yaxis={
            "title": "Period (log)" if log_period else "Period",
            "tickmode": "array",
            "tickvals": period_tick_vals.tolist(),
            "ticktext": [f"{p:.1f}" for p in period_ticks],
        },
        width=800,
        height=400,
    )
    return fig


def update_surface_data(fig: go.Figure, result: CWTResult) -> go.Figure:
    """Update an existing surface figure with new data (for live mode)."""
    fig.data[0].z = result.power
    return fig


def update_scalogram_data(fig: go.Figure, result: CWTResult, show_coi: bool = True) -> go.Figure:
    """Update an existing scalogram figure with new data (for live mode)."""
    power_display = result.power.copy()
    if show_coi:
        power_display = np.where(result.coi_mask, power_display * 0.3, power_display)
    fig.data[0].z = power_display
    return fig
