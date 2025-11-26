# common/charts.py
from __future__ import annotations

from datetime import date
from typing import Dict, Any

import pandas as pd
import plotly.express as px

# Consistent color mapping for all Gantt charts
GANTT_COLOR_MAP = {
    "Holiday": "#6A0DAD",      # Purple
    "Mid Season": "#56B4E9",   # Sky Blue
    "Low Season": "#009E73",   # Green
    "High Season": "#E69F00",  # Orange
    "Peak Season": "#AA0044",  # Dark Red
    "No Data": "#CCCCCC",      # Gray
}


def _get_color_label(season_name: str) -> str:
    """Map arbitrary season names into a small, consistent set for coloring."""
    name = (season_name or "").strip().lower()
    if "low" in name:
        return "Low Season"
    if "mid" in name or "shoulder" in name:
        return "Mid Season"
    if "peak" in name:
        return "Peak Season"
    if "high" in name:
        return "High Season"
    return season_name or "No Data"


def create_gantt_chart_from_resort_data(
    resort_data: Any,
    year: str,
    global_holidays: Dict[str, Dict[str, Dict[str, str]]] | None = None,
    height: int = 500,
):
    """Create a simple season/holiday Gantt-style chart for a single resort/year.

    Parameters
    ----------
    resort_data:
        `ResortData` object from the calculator layer (has `.years[year]`).
    year:
        Year as string (e.g. "2025").
    global_holidays:
        Optional global holiday dict from the JSON. The dates are already
        baked into `resort_data.years[year].holidays` so this is mostly
        for completeness; we do not re-read it.
    height:
        Figure height in pixels.
    """
    if year not in resort_data.years:
        return px.bar(pd.DataFrame(columns=["Label", "Start", "Duration", "Kind"]))

    yd = resort_data.years[year]

    rows = []

    # Seasons
    for season in yd.seasons:
        color_label = _get_color_label(season.name)
        for p in season.periods:
            start: date = p.start
            end: date = p.end
            duration = (end - start).days + 1
            rows.append(
                {
                    "Label": season.name,
                    "Start": start,
                    "Duration": duration,
                    "Kind": color_label,
                }
            )

    # Holidays
    for h in yd.holidays:
        start: date = h.start_date
        end: date = h.end_date
        duration = (end - start).days + 1
        rows.append(
            {
                "Label": h.name,
                "Start": start,
                "Duration": duration,
                "Kind": "Holiday",
            }
        )

    if not rows:
        return px.bar(pd.DataFrame(columns=["Label", "Start", "Duration", "Kind"]))

    df = pd.DataFrame(rows)

    # Horizontal bar chart with base=start and width=duration → simple Gantt
    fig = px.bar(
        df,
        x="Duration",
        y="Label",
        base="Start",
        color="Kind",
        orientation="h",
        color_discrete_map=GANTT_COLOR_MAP,
    )

    fig.update_layout(
        height=height,
        bargap=0.2,
        xaxis_title="Date",
        yaxis_title="Season / Holiday",
        legend_title="Type",
        hovermode="y",
    )

    # Reverse y so first item appears at top
    fig.update_yaxes(autorange="reversed")

    # Format x-axis as dates
    fig.update_xaxes(tickformat="%b %d, %Y", tickangle=-45)

    # Enhanced hover template: base is the start date, x is the end (base + duration)
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>"
        "Start: %{base|%b %d, %Y}<br>"
        "End: %{x|%b %d, %Y}<extra></extra>"
    )

    return fig
