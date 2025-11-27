# common/charts.py
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ======================================================================
# COLOUR MAP: Peak / High / Mid / Low / Holiday
# ======================================================================

COLOR_MAP: Dict[str, str] = {
    "Peak": "#D73027",     # Hot red
    "High": "#FC8D59",     # Orange
    "Mid": "#FEE08B",      # Gold / yellow
    "Low": "#1F78B4",      # Cool blue
    "Holiday": "#D73027",  # Purple
    "No Data": "#A6CEE3",  # Soft blue fallback
}


def _season_bucket(season_name: str) -> str:
    """
    Map an arbitrary season name to one of:
        Peak, High, Mid, Low, No Data

    Uses simple keyword heuristics based on the season name string.
    """
    name = (season_name or "").strip().lower()

    if "peak" in name:
        return "Peak"
    if "high" in name:
        return "High"
    if "mid" in name or "shoulder" in name:
        return "Mid"
    if "low" in name:
        return "Low"

    # If nothing matches, fall back
    return "No Data"


# ======================================================================
# SHARED GANTT (working dict + global_holidays from data)
# ======================================================================

def create_gantt_chart_from_working(
    working: Dict[str, Any],
    year: str,
    data: Dict[str, Any],
    height: Optional[int] = None,
) -> go.Figure:
    """
    Build a season + holiday Gantt chart for the editor UI.

    This follows your original create_gantt_chart_v2 logic, but the
    `Type` field is now a semantic bucket (Peak/High/Mid/Low/Holiday/No Data)
    so we can apply a consistent colour scheme.

    Parameters
    ----------
    working : dict
        Editable resort dict (one resort), structure:
          working["years"][year]["seasons"]  -> list of dicts with:
              {"name": str, "periods": [{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, ...], ...}
          working["years"][year]["holidays"] -> list of dicts with:
              {"name": str, "global_reference": str, ...}
    year : str
        Year string (e.g. "2025").
    data : dict
        Full JSON data (has data["global_holidays"][year][ref] with dates).
    height : int, optional
        Preferred figure height. If None, we auto-size: max(400, len(df) * 35).
    """
    rows: List[Dict[str, Any]] = []

    year_obj = working.get("years", {}).get(year, {})

    # Seasons – dates from working
    for season in year_obj.get("seasons", []):
        sname = season.get("name", "(Unnamed)")
        bucket = _season_bucket(sname)
        for i, p in enumerate(season.get("periods", []), 1):
            try:
                start_dt = datetime.strptime(p.get("start"), "%Y-%m-%d")
                end_dt = datetime.strptime(p.get("end"), "%Y-%m-%d")
                if start_dt <= end_dt:
                    rows.append(
                        {
                            "Task": f"{sname} #{i}",
                            "Start": start_dt,
                            "Finish": end_dt,
                            "Type": bucket,
                        }
                    )
            except Exception:
                continue

    # Holidays – dates from global_holidays in `data`
    gh_year = data.get("global_holidays", {}).get(year, {})
    for h in year_obj.get("holidays", []):
        global_ref = h.get("global_reference") or h.get("name")
        if gh := gh_year.get(global_ref):
            try:
                start_dt = datetime.strptime(gh.get("start_date"), "%Y-%m-%d")
                end_dt = datetime.strptime(gh.get("end_date"), "%Y-%m-%d")
                if start_dt <= end_dt:
                    rows.append(
                        {
                            "Task": h.get("name", "(Unnamed)"),
                            "Start": start_dt,
                            "Finish": end_dt,
                            "Type": "Holiday",
                        }
                    )
            except Exception:
                continue

    # Fallback when nothing is defined
    if not rows:
        today = datetime.now()
        rows.append(
            {
                "Task": "No Data",
                "Start": today,
                "Finish": today + timedelta(days=1),
                "Type": "No Data",
            }
        )

    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])

    fig_height = height if height is not None else max(400, len(df) * 35)

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        title=f"{working.get('display_name', 'Resort')} – {year} Timeline",
        height=fig_height,
        color_discrete_map=COLOR_MAP,
    )

    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>"
        "Start: %{base|%d %b %Y}<br>"
        "End: %{x|%d %b %Y}<extra></extra>"
    )
    fig.update_layout(
        showlegend=True,
        xaxis_title="Date",
        yaxis_title="Period",
        font=dict(size=12),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    return fig
