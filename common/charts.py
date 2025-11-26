# common/charts.py
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Consistent color mapping for all Gantt charts
GANTT_COLOR_MAP = {
    "Holiday": "#6A0DAD",      # Purple
    "Mid Season": "#56B4E9",   # Sky Blue
    "Low Season": "#009E73",   # Green
    "High Season": "#E69F00",  # Orange
    "Peak Season": "#AA0044",  # Dark Red
    "No Data": "#CCCCCC"       # Gray
}

def create_gantt_chart(
    resort_name: str,
    year: str,
    seasons: List[Dict[str, Any]],
    holidays: List[Dict[str, Any]],
    global_holidays: Dict[str, Any] = None,
    title: str = None,
    height: int = 500
):
    """
    Create a standardized Gantt chart for resort seasons and holidays.
    
    Args:
        resort_name: Name of the resort
        year: Year string (e.g., "2025")
        seasons: List of season dictionaries with name, periods
        holidays: List of holiday dictionaries with name, global_reference
        global_holidays: Global holidays dict from data (optional, for dates)
        title: Custom chart title (optional)
        height: Chart height in pixels
    
    Returns:
        Plotly figure object
    """
    rows = []
    
    # Add season date ranges
    for season in seasons:
        season_name = season.get("name", "(Unnamed)")
        for i, period in enumerate(season.get("periods", []), 1):
            try:
                start = datetime.strptime(period.get("start", ""), "%Y-%m-%d")
                end = datetime.strptime(period.get("end", ""), "%Y-%m-%d")
                if start <= end:
                    rows.append({
                        "Task": f"{season_name} #{i}",
                        "Start": start,
                        "Finish": end + timedelta(days=1),  # Add 1 day for Plotly timeline
                        "Type": season_name
                    })
            except:
                continue
    
    # Add holiday date ranges
    if global_holidays and year in global_holidays:
        gh_year = global_holidays[year]
        for h in holidays:
            global_ref = h.get("global_reference") or h.get("name")
            if gh := gh_year.get(global_ref):
                try:
                    start = datetime.strptime(gh.get("start_date", ""), "%Y-%m-%d")
                    end = datetime.strptime(gh.get("end_date", ""), "%Y-%m-%d")
                    if start <= end:
                        rows.append({
                            "Task": h.get("name", "(Unnamed)"),
                            "Start": start,
                            "Finish": end + timedelta(days=1),
                            "Type": "Holiday"
                        })
                except:
                    continue
    
    # Handle empty data
    if not rows:
        today = datetime.now()
        rows.append({
            "Task": "No Data",
            "Start": today,
            "Finish": today + timedelta(days=1),
            "Type": "No Data"
        })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
    
    # Create chart title
    if title is None:
        title = f"{resort_name} - {year} Calendar Overview"
    
    # Create Gantt chart
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        color_discrete_map=GANTT_COLOR_MAP,
        title=title
    )
    
    # Update layout for consistent styling
    fig.update_layout(
        height=height,
        xaxis_title="Date",
        yaxis_title="Period",
        showlegend=True,
        hovermode="closest",
        font=dict(size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    # Reverse y-axis so earliest dates appear at top
    fig.update_yaxes(autorange="reversed")
    
    # Format x-axis
    fig.update_xaxes(
        tickformat="%b %d, %Y",
        tickangle=-45
    )
    
    # Enhanced hover template
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Start: %{base|%b %d, %Y}<br>End: %{x|%b %d, %Y}<extra></extra>"
    )
    
    return fig


def create_gantt_chart_from_working(
    working: Dict[str, Any],
    year: str,
    data: Dict[str, Any],
    height: int = 500
):
    """
    Create Gantt chart from working resort data (used in editor).
    
    Args:
        working: Working resort dictionary
        year: Year string
        data: Full data dict with global_holidays
        height: Chart height in pixels
    
    Returns:
        Plotly figure object
    """
    resort_name = working.get("display_name", "Resort")
    year_obj = working.get("years", {}).get(year, {})
    
    seasons = year_obj.get("seasons", [])
    holidays = year_obj.get("holidays", [])
    global_holidays = data.get("global_holidays", {})
    
    return create_gantt_chart(
        resort_name=resort_name,
        year=year,
        seasons=seasons,
        holidays=holidays,
        global_holidays=global_holidays,
        height=height
    )


def create_gantt_chart_from_resort_data(
    resort_data,  # ResortData object from calculator
    year: str,
    global_holidays: Dict[str, Any],
    height: int = 500
):
    """
    Create Gantt chart from ResortData object (used in calculator).
    
    Args:
        resort_data: ResortData object with name and years
        year: Year string
        global_holidays: Global holidays dict
        height: Chart height in pixels
    
    Returns:
        Plotly figure object
    """
    if year not in resort_data.years:
        # Return empty chart
        return create_gantt_chart(
            resort_name=resort_data.name,
            year=year,
            seasons=[],
            holidays=[],
            global_holidays=global_holidays,
            height=height
        )
    
    year_data = resort_data.years[year]
    
    # Build rows directly from ResortData objects
    rows = []
    
    # Add seasons
    for season in year_data.seasons:
        for i, period in enumerate(season.periods, 1):
            rows.append({
                "Task": f"{season.name} #{i}",
                "Start": period.start,
                "Finish": period.end + timedelta(days=1),
                "Type": season.name
            })
    
    # Add holidays (we have dates directly in Holiday objects)
    for h in year_data.holidays:
        rows.append({
            "Task": h.name,
            "Start": h.start_date,
            "Finish": h.end_date + timedelta(days=1),
            "Type": "Holiday"
        })
    
    # Handle empty data
    if not rows:
        today = datetime.now()
        rows.append({
            "Task": "No Data",
            "Start": today,
            "Finish": today + timedelta(days=1),
            "Type": "No Data"
        })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
    
    # Create Gantt chart
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        color_discrete_map=GANTT_COLOR_MAP,
        title=f"{resort_data.name} - {year} Calendar Overview"
    )
    
    # Update layout for consistent styling
    fig.update_layout(
        height=height,
        xaxis_title="Date",
        yaxis_title="Period",
        showlegend=True,
        hovermode="closest",
        font=dict(size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    # Reverse y-axis so earliest dates appear at top
    fig.update_yaxes(autorange="reversed")
    
    # Format x-axis
    fig.update_xaxes(
        tickformat="%b %d, %Y",
        tickangle=-45
    )
    
    # Enhanced hover template
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Start: %{base|%b %d, %Y}<br>End: %{x|%b %d, %Y}<extra></extra>"
    )
    
    return fig
