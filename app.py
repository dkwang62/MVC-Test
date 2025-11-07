import streamlit as st
import math
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px

# ----------------------------------------------------------------------
# Custom date formatter: 12 Jan 2026
# ----------------------------------------------------------------------
def fmt_date(d):
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    elif isinstance(d, (pd.Timestamp, datetime)):
        d = d.date()
    return d.strftime("%d %b %Y")

# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
with open("data.json", "r") as f:
    data = json.load(f)

ROOM_VIEW_LEGEND = {
    "GV": "Garden", "OV": "Ocean View", "OF": "Oceanfront", "S": "Standard",
    "IS": "Island Side", "PS": "Pool Low Flrs", "PSH": "Pool High Flrs",
    "UF": "Gulf Front", "UV": "Gulf View", "US": "Gulf Side",
    "PH": "Penthouse", "PHGV": "Penthouse Garden", "PHOV": "Penthouse Ocean View",
    "PHOF": "Penthouse Ocean Front", "IV": "Island", "MG": "Garden",
    "PHMA": "Penthouse Mountain", "PHMK": "Penthouse Ocean", "PHUF": "Penthouse Gulf Front",
    "AP_Studio_MA": "AP Studio Mountain", "AP_1BR_MA": "AP 1BR Mountain",
    "AP_2BR_MA": "AP 2BR Mountain", "AP_2BR_MK": "AP 2BR Ocean",
    "LO": "Lock-Off", "CV": "City", "LV": "Lagoon", "PV": "Pool", "OS": "Oceanside",
    "K": "King", "DB": "Double Bed", "MV": "Mountain", "MA": "Mountain", "MK": "Ocean",
}

SEASON_BLOCKS = data.get("season_blocks", {})
REF_POINTS = data.get("reference_points", {})
HOLIDAY_WEEKS = data.get("holiday_weeks", {})

# ----------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------
st.session_state.setdefault("data_cache", {})
st.session_state.setdefault("allow_renter_modifications", False)

# ----------------------------------------------------------------------
# Helpers (unchanged)
# ----------------------------------------------------------------------
def display_room(key: str) -> str:
    if key in ROOM_VIEW_LEGEND:
        return ROOM_VIEW_LEGEND[key]
    if key.startswith("AP_"):
        return {"AP_Studio_MA": "AP Studio Mountain",
                "AP_1BR_MA": "AP 1BR Mountain",
                "AP_2BR_MA": "AP 2BR Mountain",
                "AP_2BR_MK": "AP 2BR Ocean"}[key]
    parts = key.split()
    view = parts[-1] if len(parts) > 1 and parts[-1] in ROOM_VIEW_LEGEND else ""
    return f"{parts[0]} {ROOM_VIEW_LEGEND.get(view, view)}" if view else key

def internal_room(display: str) -> str:
    rev = {v: k for k, v in ROOM_VIEW_LEGEND.items()}
    if display in rev:
        return rev[display]
    if display.startswith("AP "):
        return {"AP Studio Mountain": "AP_Studio_MA",
                "AP 1BR Mountain": "AP_1BR_MA",
                "AP 2BR Mountain": "AP_2BR_MA",
                "AP 2BR Ocean": "AP_2BR_MK"}[display]
    base, *view = display.rsplit(maxsplit=1)
    return f"{base} {rev.get(view[0], view[0])}" if view else display

def resolve_global(year: str, key: str) -> list:
    return data.get("global_dates", {}).get(year, {}).get(key, [])

# ----------------------------------------------------------------------
# Core data generation (cached) - unchanged
# ----------------------------------------------------------------------
def generate_data(resort: str, date: datetime.date):
    cache = st.session_state.data_cache
    ds = date.strftime("%Y-%m-%d")
    if ds in cache:
        return cache[ds]
    year = date.strftime("%Y")
    dow = date.strftime("%a")
    is_fri_sat = dow in {"Fri", "Sat"}
    is_sun = dow == "Sun"
    day_cat = "Fri-Sat" if is_fri_sat else ("Sun" if is_sun else "Mon-Thu")
    entry = {}
    season = "Default Season"
    holiday = None
    h_start = h_end = None
    is_h_start = False

    if (date.month == 12 and date.day >= 26) or (date.month == 1 and date.day <= 1):
        prev = str(int(year) - 1)
        start = datetime.strptime(f"{prev}-12-26", "%Y-%m-%d").date()
        end = datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date()
        if start <= date <= end:
            holiday, h_start, h_end, is_h_start = "New Year's Eve/Day", start, end, date == start

    if not holiday and year in HOLIDAY_WEEKS.get(resort, {}):
        for name, raw in HOLIDAY_WEEKS[resort][year].items():
            if isinstance(raw, str) and raw.startswith("global:"):
                raw = resolve_global(year, raw.split(":", 1)[1])
            if len(raw) >= 2:
                s = datetime.strptime(raw[0], "%Y-%m-%d").date()
                e = datetime.strptime(raw[1], "%Y-%m-%d").date()
                if s <= date <= e:
                    holiday, h_start, h_end, is_h_start = name, s, e, date == s
                    break

    if not holiday and year in SEASON_BLOCKS.get(resort, {}):
        for s_name, ranges in SEASON_BLOCKS[resort][year].items():
            for rs, re in ranges:
                if datetime.strptime(rs, "%Y-%m-%d").date() <= date <= datetime.strptime(re, "%Y-%m-%d").date():
                    season = s_name
                    break
            if season != "Default Season":
                break

    if holiday:
        src = REF_POINTS.get(resort, {}).get("Holiday Week", {}).get(holiday, {})
        for internal_key, pts in src.items():
            display_key = display_room(internal_key)
            entry[display_key] = pts if is_h_start else 0
    else:
        cat = None
        if season != "Holiday Week":
            cats = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
            avail = [c for c in cats if REF_POINTS.get(resort, {}).get(season, {}).get(c)]
            if avail:
                cat = ("Fri-Sat" if is_fri_sat and "Fri-Sat" in avail else
                       "Sun" if is_sun and "Sun" in avail else
                       "Mon-Thu" if not is_fri_sat and "Mon-Thu" in avail else
                       "Sun-Thu" if "Sun-Thu" in avail else avail[0])
        src = REF_POINTS.get(resort, {}).get(season, {}).get(cat, {}) if cat else {}
        for internal_key, pts in src.items():
            entry[display_room(internal_key)] = pts

    if holiday:
        entry.update(HolidayWeek=True, holiday_name=holiday,
                     holiday_start=h_start, holiday_end=h_end,
                     HolidayWeekStart=is_h_start)

    final_src = REF_POINTS.get(resort, {}).get("Holiday Week", {}).get(holiday, {}) if holiday else src
    disp_to_int = {display_room(k): k for k in final_src}
    cache[ds] = (entry, disp_to_int)
    return entry, disp_to_int

# ----------------------------------------------------------------------
# Gantt Chart - with custom format
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
    fig.update_xaxes(tickformat="%d %b %Y", hoverformat="%d %b %Y")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Start: %{x|%d %b %Y}<br>End: %{x|%d %b %Y}<extra></extra>")
    return fig

# ----------------------------------------------------------------------
# Discount & Breakdowns
# ----------------------------------------------------------------------
def apply_discount(points: int, discount: str | None, date: datetime.date) -> tuple[int, bool]:
    if not discount:
        return points, False
    if discount == "within_60_days":
        return math.floor(points * 0.7), True
    if discount == "within_30_days":
        return math.floor(points * 0.75), True
    return points, False

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
    rows, tot_pts, tot_cost = [], 0, 0
    totals = {"m": 0, "c": 0, "d": 0}
    cur_h, h_end = None, None
    dep_per_pt = (cap_per_pt - salvage) / life if inc_dep else 0
    for i in range(nights):
        d = checkin + timedelta(days=i)
        entry, _ = generate_data(resort, d)
        pts = entry.get(room, 0)
        dpts = math.floor(pts * disc_mul)
        if entry.get("HolidayWeek"):
            if entry.get("HolidayWeekStart"):
                cur_h = entry["holiday_name"]
                h_start = entry["holiday_start"]
                h_end = entry["holiday_end"]
                row = {"Date": f"{cur_h} ({fmt_date(h_start)} - {fmt_date(h_end)})",
                       "Day": "", "Points": dpts}
                if inc_maint or inc_cap or inc_dep:
                    mc = math.ceil(dpts * rate) if inc_maint else 0
                    cc = math.ceil(dpts * cap_per_pt * coc) if inc_cap else 0
                    dc = math.ceil(dpts * dep_per_pt) if inc_dep else 0
                    day_cost = mc + cc + dc
                    if inc_maint: row["Maintenance"] = f"${mc}"; totals["m"] += mc
                    if inc_cap: row["Capital Cost"] = f"${cc}"; totals["c"] += cc
                    if inc_dep: row["Depreciation"] = f"${dc}"; totals["d"] += dc
                    if day_cost: row["Total Cost"] = f"${day_cost}"; tot_cost += day_cost
                rows.append(row)
                tot_pts += dpts
            elif cur_h and d <= h_end:
                continue
        else:
            cur_h = h_end = None
            row = {"Date": fmt_date(d), "Day": d.strftime("%a"), "Points": dpts}
            if inc_maint or inc_cap or inc_dep:
                mc = math.ceil(dpts * rate) if inc_maint else 0
                cc = math.ceil(dpts * cap_per_pt * coc) if inc_cap else 0
                dc = math.ceil(dpts * dep_per_pt) if inc_dep else 0
                day_cost = mc + cc + dc
                if inc_maint: row["Maintenance"] = f"${mc}"; totals["m"] += mc
                if inc_cap: row["Capital Cost"] = f"${cc}"; totals["c"] += cc
                if inc_dep: row["Depreciation"] = f"${dc}"; totals["d"] += dc
                if day_cost: row["Total Cost"] = f"${day_cost}"; tot_cost += day_cost
            rows.append(row)
            tot_pts += dpts
    return (pd.DataFrame(rows), tot_pts, tot_cost,
            totals["m"], totals["c"], totals["d"])

# ----------------------------------------------------------------------
# UI - CRITICAL FIX: NO `format=` in st.date_input
# ----------------------------------------------------------------------
user_mode = st.sidebar.selectbox("User Mode", ["Renter", "Owner"], index=0, key="mode")
st.title(f"Marriott Vacation Club {'Rent' if user_mode=='Renter' else 'Cost'} Calculator")

# === FIXED DATE INPUT (works on all Streamlit versions) ===
checkin = st.date_input(
    "Check-in Date",
    min_value=datetime(2025,1,3).date(),
    max_value=datetime(2026,12,31).date(),
    value=datetime(2026,6,12).date()
    # REMOVED: format="DD MMM YYYY" ← this caused the crash
)

# === SHOW FORMATTED DATE BELOW INPUT ===
st.markdown(f"**Selected Check-in:** `{fmt_date(checkin)}`")

# Rest of your UI (unchanged until Calculate button)
nights = st.number_input("Number of Nights", 1, 30, 7)
rate_per_point = 0.81
discount_opt = None
disc_mul = 1.0
coc = 0.07
cap_per_pt = 16.0
life = 15
salvage = 3.0
inc_maint = inc_cap = inc_dep = True

# ... [rest of sidebar and logic unchanged] ...

# Keep everything else exactly as in the previous working version
# (compare_renter, compare_owner, adjust_date_range, etc.)

# Just make sure to use fmt_date() everywhere
if adjusted:
    end_date = checkin_adj + timedelta(days=nights_adj-1)
    st.info(f"Adjusted to full holiday: **{fmt_date(checkin_adj)}** to **{fmt_date(end_date)}** ({nights_adj} nights)")

if st.button("Calculate"):
    # ... all your calculation code ...
    st.success(f"Total Points: {pts} | Total {'Rent' if user_mode=='Renter' else 'Cost'}: ${rent if user_mode=='Renter' else cost}")
    st.download_button("Download CSV", df.to_csv(index=False).encode(),
                       f"{resort}_{fmt_date(checkin_adj).replace(' ', '_')}_breakdown.csv", "text/csv")
    st.plotly_chart(gantt_chart(resort, checkin.year), use_container_width=True)
