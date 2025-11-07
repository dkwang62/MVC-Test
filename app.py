import streamlit as st
import math
import json
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import plotly.express as px

# ----------------------------------------------------------------------
# Custom date formatter: 12 Jan 2026
# ----------------------------------------------------------------------
def fmt_date(date_obj):
    if not isinstance(date_obj, (datetime, pd.Timestamp)):
        date_obj = pd.to_datetime(date_obj).date()
    else:
        date_obj = date_obj.date() if isinstance(date_obj, (datetime, pd.Timestamp)) else date_obj
    return date_obj.strftime("%d %b %Y")

# Apply to Plotly (global)
px.defaults.template = "plotly"
px.defaults.color_continuous_scale = px.colors.sequential.Plasma

# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
with open("data.json", "r") as f:
    data = json.load(f)

ROOM_VIEW_LEGEND = { ... }  # (unchanged - keeping your original dict)

SEASON_BLOCKS = data.get("season_blocks", {})
REF_POINTS = data.get("reference_points", {})
HOLIDAY_WEEKS = data.get("holiday_weeks", {})

# ----------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------
st.session_state.setdefault("data_cache", {})
st.session_state.setdefault("allow_renter_modifications", False)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def display_room(key: str) -> str:
    # ... (unchanged)

def internal_room(display: str) -> str:
    # ... (unchanged)

def resolve_global(year: str, key: str) -> list:
    return data.get("global_dates", {}).get(year, {}).get(key, [])

# ----------------------------------------------------------------------
# Core data generation (cached)
# ----------------------------------------------------------------------
def generate_data(resort: str, date: datetime.date):
    # ... (unchanged, only returns entry + disp_to_int)
    # But we'll format dates later when displaying
    cache = st.session_state.data_cache
    ds = date.strftime("%Y-%m-%d")
    if ds in cache:
        return cache[ds]
    # ... (rest unchanged)
    cache[ds] = (entry, disp_to_int)
    return entry, disp_to_int

# ----------------------------------------------------------------------
# Gantt Chart - now with custom date format
# ----------------------------------------------------------------------
def gantt_chart(resort: str, year: int):
    rows = []
    ys = str(year)
    for name, raw in HOLIDAY_WEEKS.get(resort, {}).get(ys, {}).items():
        if isinstance(raw, str) and raw.startswith("global:"):
            raw = resolve_global(ys, raw.split(":", 1)[1])
        if len(raw) >= 2:
            rows.append(dict(Task=name,
                             Start=datetime.strptime(raw[0], "%Y-%m-%d").date(),
                             Finish=datetime.strptime(raw[1], "%Y-%m-%d").date(),
                             Type="Holiday"))
    for s_name, ranges in SEASON_BLOCKS.get(resort, {}).get(ys, {}).items():
        for i, (s, e) in enumerate(ranges, 1):
            rows.append(dict(Task=f"{s_name} {i}",
                             Start=datetime.strptime(s, "%Y-%m-%d").date(),
                             Finish=datetime.strptime(e, "%Y-%m-%d").date(),
                             Type=s_name))

    df = pd.DataFrame(rows) if rows else pd.DataFrame({
        "Task": ["No Data"], "Start": [datetime.now().date()],
        "Finish": [datetime.now().date() + timedelta(days=1)], "Type": ["No Data"]
    })

    colors = {t: {"Holiday": "rgb(255,99,71)", "Low Season": "rgb(135,206,250)",
                 "High Season": "rgb(255,69,0)", "Peak Season": "rgb(255,215,0)",
                 "Shoulder": "rgb(50,205,50)", "Peak": "rgb(255,69,0)",
                 "Summer": "rgb(255,165,0)", "Low": "rgb(70,130,180)",
                 "Mid Season": "rgb(60,179,113)", "No Data": "rgb(128,128,128)"}.get(t, "rgb(169,169,169)")
              for t in df["Type"].unique()}

    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task",
                      color="Type", color_discrete_map=colors,
                      title=f"{resort} Seasons & Holidays ({year})", height=600)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Date", yaxis_title="Period", showlegend=True)

    # Custom date format on hover and axis
    fig.update_xaxes(
        tickformat="%d %b %Y",
        hoverformat="%d %b %Y"
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Start: %{x|%d %b %Y}<br>End: %{x|%d %b %Y}<extra></extra>"
    )
    return fig

# ----------------------------------------------------------------------
# Discount & Breakdowns - now with fmt_date
# ----------------------------------------------------------------------
def renter_breakdown(resort, room, checkin, nights, rate, discount):
    rows, tot_pts, tot_rent = [], 0, 0
    cur_h, h_end = None, None
    applied, disc_days = False, []
    for i in range(nights):
        d = checkin + timedelta(days=i)
        entry, _ = generate_data(resort, d)
        pts = entry.get(room, 0)
        eff_pts, disc = apply_discount(pts, discount, d)
        if disc:
            applied = True
            disc_days.append(fmt_date(d))
        rent = math.ceil(pts * rate)
        if entry.get("HolidayWeek"):
            if entry.get("HolidayWeekStart"):
                cur_h = entry["holiday_name"]
                h_start = entry["holiday_start"]
                h_end = entry["holiday_end"]
                rows.append({"Date": f"{cur_h} ({fmt_date(h_start)} - {fmt_date(h_end)})",
                             "Day": "", "Points": eff_pts, room: f"${rent}"})
                tot_pts += eff_pts
                tot_rent += rent
            elif cur_h and d <= h_end:
                continue
        else:
            cur_h = h_end = None
            rows.append({"Date": fmt_date(d), "Day": d.strftime("%a"),
                         "Points": eff_pts, room: f"${rent}"})
            tot_pts += eff_pts
            tot_rent += rent
    return pd.DataFrame(rows), tot_pts, tot_rent, applied, disc_days

def owner_breakdown(resort, room, checkin, nights, disc_mul,
                    inc_maint, inc_cap, inc_dep,
                    rate, cap_per_pt, coc, life, salvage):
    # ... same as before but using fmt_date(d)
    # Only showing modified part:
    # Inside loop:
    # rows.append({"Date": fmt_date(d), "Day": d.strftime("%a"), "Points": dpts})
    # Holiday:
    # {"Date": f"{cur_h} ({fmt_date(h_start)} - {fmt_date(h_end)})"

# ----------------------------------------------------------------------
# COMPARISON - updated with fmt_date
# ----------------------------------------------------------------------
def compare_renter(resort, rooms, checkin, nights, rate, discount):
    # ... inside loop:
    # data_rows.append({"Date": fmt_date(d), "Room Type": room, "Rent": f"${rent}"})
    # Holiday: f"{h_name} ({fmt_date(h_start)} - {fmt_date(h_end)})"

# Same for compare_owner

# ----------------------------------------------------------------------
# UI - Date input with custom format
# ----------------------------------------------------------------------
# Custom date input display
checkin = st.date_input(
    "Check-in Date",
    min_value=datetime(2025,1,3).date(),
    max_value=datetime(2026,12,31).date(),
    value=datetime(2026,6,12).date(),
    format="DD MMM YYYY",   # This is the key!
    key="checkin_date"
)

# Optional: Show formatted value above
st.markdown(f"**Selected Check-in:** {fmt_date(checkin)}")

nights = st.number_input("Number of Nights", 1, 30, 7)

# ----------------------------------------------------------------------
# Adjusted holiday message
# ----------------------------------------------------------------------
if adjusted:
    end_date = checkin_adj + timedelta(days=nights_adj-1)
    st.info(f"Adjusted to full holiday: **{fmt_date(checkin_adj)}** to **{fmt_date(end_date)}** "
            f"({nights_adj} nights)")

# ----------------------------------------------------------------------
# Final success message
# ----------------------------------------------------------------------
if user_mode == "Renter":
    st.success(f"Total Points: {pts} | Total Rent: ${rent}")
    if disc_ap:
        st.success(f"Discount Applied: {disc_pct}% off points "
                   f"({len(disc_days)} day(s): {', '.join(disc_days)})")
else:
    st.success(f"Total Points: {pts} | Total Cost: ${cost}")

# ----------------------------------------------------------------------
# Download buttons - with nice date in filename
# ----------------------------------------------------------------------
filename_date = fmt_date(checkin).replace(" ", "_")
st.download_button(
    "Download CSV",
    df.to_csv(index=False).encode(),
    f"{resort}_{filename_date}_breakdown.csv",
    "text/csv"
)

# ----------------------------------------------------------------------
# Gantt at bottom
# ----------------------------------------------------------------------
st.plotly_chart(gantt, use_container_width=True)
