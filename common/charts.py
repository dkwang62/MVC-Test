import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime

# Standard Colors
COLOR_MAP = {
    "Peak": "#D73027",     # Red
    "High": "#FC8D59",     # Orange
    "Mid": "#FEE08B",      # Yellow
    "Low": "#1F78B4",      # Blue
    "Holiday": "#9333EA",  # Purple
    "No Data": "#E5E7EB"   # Grey
}

def render_gantt(rows: list, title: str = ""):
    """
    Renders a Gantt chart as a Matplotlib Figure (Static Image).
    Allows native pinch-to-zoom on mobile.
    """
    if not rows:
        return None

    df = pd.DataFrame(rows)
    
    # Ensure dates
    df['Start'] = pd.to_datetime(df['Start'])
    df['Finish'] = pd.to_datetime(df['Finish'])
    
    # Calculate duration (days) and start position (matplotlib date format)
    df['duration'] = (df['Finish'] - df['Start']).dt.days
    df['start_num'] = mdates.date2num(df['Start'])
    
    # Assign Colors
    colors = [COLOR_MAP.get(t, "#E5E7EB") for t in df['Type']]

    # Determine Y-Axis Grouping (So same seasons appear on one line)
    # Get unique tasks in order of appearance
    unique_tasks = list(dict.fromkeys(df['Task']))
    # Reverse so the first item appears at the TOP of the chart
    unique_tasks.reverse() 
    task_map = {task: i for i, task in enumerate(unique_tasks)}
    
    # Map each row to its Y-coordinate
    y_coordinates = [task_map[t] for t in df['Task']]

    # --- PLOT SETUP ---
    # Dynamic height: ~0.5 inches per unique task + buffer
    fig_height = max(3, len(unique_tasks) * 0.5 + 1)
    fig, ax = plt.subplots(figsize=(8, fig_height)) # 8 inches wide
    
    # Plot Horizontal Bars
    ax.barh(y_coordinates, df['duration'], left=df['start_num'], color=colors, height=0.6, align='center')
    
    # Formatting Y-Axis
    ax.set_yticks(range(len(unique_tasks)))
    ax.set_yticklabels(unique_tasks)
    
    # Formatting X-Axis (Dates)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    
    # Styling
    ax.grid(axis='x', linestyle=':', alpha=0.5)
    ax.set_title(title, fontsize=10, pad=10)
    plt.tight_layout()
    
    return fig

def get_season_bucket(name: str) -> str:
    """Helper to categorize seasons for coloring."""
    n = str(name).lower()
    if "peak" in n: return "Peak"
    if "high" in n: return "High"
    if "mid" in n or "shoulder" in n: return "Mid"
    if "low" in n: return "Low"
    return "No Data"
