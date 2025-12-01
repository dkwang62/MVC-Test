import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date

# Standard Colors
COLOR_MAP = {
    "Peak": "#D73027",     # Red
    "High": "#FC8D59",     # Orange
    "Mid": "#FEE08B",      # Yellow
    "Low": "#1F78B4",      # Blue
    "Holiday": "#9333EA",  # Purple
    "No Data": "#E5E7EB"   # Grey
}

def render_gantt(rows: list, title: str = "", height: int = 300) -> go.Figure:
    """
    Unified plotter optimized for mobile.
    Expects rows: [{"Task": str, "Start": dt, "Finish": dt, "Type": str}]
    """
    if not rows:
        # Fallback to prevent crash
        today = datetime.now()
        rows = [{"Task": "No Data", "Start": today, "Finish": today, "Type": "No Data"}]

    df = pd.DataFrame(rows)
    
    fig = px.timeline(
        df, 
        x_start="Start", x_end="Finish", y="Task", color="Type",
        height=height, 
        color_discrete_map=COLOR_MAP
    )

    # Minimalist mobile layout
    fig.update_yaxes(autorange="reversed", title=None, tickfont=dict(size=10))
    fig.update_xaxes(title=None, tickformat="%b %d", tickfont=dict(size=10))
    
    fig.update_layout(
        margin=dict(l=5, r=5, t=20, b=10), # Tight margins
        showlegend=False, # Legend takes too much space on mobile
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10),
        title=dict(text=title, font=dict(size=12)) if title else None
    )
    return fig

def get_season_bucket(name: str) -> str:
    """Helper to categorize seasons for coloring."""
    n = name.lower()
    if "peak" in n: return "Peak"
    if "high" in n: return "High"
    if "mid" in n or "shoulder" in n: return "Mid"
    if "low" in n: return "Low"
    return "No Data"
