import streamlit as st
import math
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(page_title="MVC Calculator", layout="wide")
    st.markdown("""
    <style>
        .stButton button { font-size: 12px !important; padding: 5px 10px !important; height: auto !important; }
    </style>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------
def initialize_session_state():
    for key in ['data', 'current_resort', 'data_cache', 'allow_renter_modifications', 'last_resort', 'last_year', 'room_types', 'disp_to_int']:
        st.session_state.setdefault(key, None if 'data' in key or 'room_types' in key or 'disp_to_int' in key else {})

# ----------------------------------------------------------------------
# File upload
# ----------------------------------------------------------------------
def handle_file_upload():
    uploaded = st.file_uploader("Upload JSON", type="json")
    if uploaded:
        try:
            st.session_state.data = json.load(uploaded)
            st.success("Loaded!")
        except Exception as e:
            st.error(f"Error: {e}")

# ----------------------------------------------------------------------
# Date formatter
# ----------------------------------------------------------------------
def fmt_date(d):
    if isinstance(d, str): d = datetime.strptime(d, "%Y-%m-%d").date()
    elif isinstance(d, (pd.Timestamp, datetime)): d = d.date()
    return d.strftime("%d %b %Y")

# ----------------------------------------------------------------------
# Room display
# ----------------------------------------------------------------------
def display_room(key: str) -> str:
    legend = {
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
    if key in legend: return legend[key]
    if key.startswith("AP_"):
        return {"AP_Studio_MA": "AP Studio Mountain", "AP_1BR_MA": "AP 1BR Mountain",
                "AP_2BR_MA": "AP 2BR Mountain", "AP_2BR_MK": "AP 2BR Ocean"}.get(key, key)
    parts = key.split()
    view = parts[-1] if len(parts) > 1 and parts[-1] in legend else ""
    return f"{parts[0]} {legend.get(view, view)}" if view else key

# ----------------------------------------------------------------------
# Generate data (v2 schema)
# ----------------------------------------------------------------------
def generate_data(resort: str, date: datetime.date):
    cache = st.session_state.data_cache
    ds = date.strftime("%Y-%m-%d")
    if ds in cache: return cache[ds]
    year = date.strftime("%Y")
    dow = date.strftime("%a")
    is_fri_sat = dow in {"Fri", "Sat"}
    is_sun = dow == "Sun"
    day_cat = "Fri-Sat" if is_fri_sat else ("Sun" if is_sun else "Mon-Thu")
    entry = {}
    season = "Default Season"
    holiday = None
    is_h_start = False

    # Holiday check
    data = st.session_state.data
    holidays = data.get("resorts", {}).get(resort, {}).get("years", {}).get(year, {}).get("holidays", [])
    for h in holidays:
        if "start_date" in h and "end_date" in h:
            s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
            if s <= date <= e:
                holiday = h["name"]
                is_h_start = date == s
                entry.update({display_room(k): v for k, v in h.get("room_points", {}).items()})
                break

    # Season check
    if not holiday:
        seasons = data.get("resorts", {}).get(resort, {}).get("years", {}).get(year, {}).get("seasons", [])
        for s in seasons:
            for p in s.get("periods", []):
                start = datetime.strptime(p["start"], "%Y-%m-%d").date()
                end = datetime.strptime(p["end"], "%Y-%m-%d").date()
                if start <= date <= end:
                    season = s["name"]
                    for cat_data in s.get("day_categories", {}).values():
                        if dow in cat_data.get("day_pattern", []):
                            entry.update({display_room(k): v for k, v in cat_data.get("room_points", {}).items()})
                            break
                    break
            if season != "Default Season": break

    if holiday:
        entry.update(HolidayWeek=True, holiday_name=holiday, holiday_start=s, holiday_end=e, HolidayWeekStart=is_h_start)
    elif not entry:
        default = data.get("resorts", {}).get(resort, {}).get("default_points", {})
        entry.update({display_room(k): v for k, v in default.items()})

    disp_to_int = {display_room(k): k for k in entry if k not in {"HolidayWeek", "holiday_name", "holiday_start", "holiday_end", "HolidayWeekStart"}}
    cache[ds] = (entry, disp_to_int)
    return entry, disp_to_int

# ----------------------------------------------------------------------
# Gantt chart
# ----------------------------------------------------------------------
def gantt_chart(resort: str, year: int):
    data = st.session_state.data
    rows = []
    ys = str(year)

    # Holidays
    holidays = data.get("resorts", {}).get(resort, {}).get("years", {}).get(ys, {}).get("holidays", [])
    for h in holidays:
        if "start_date" in h and "end_date" in h:
            start_dt = datetime.strptime(h["start_date"], "%Y-%m-%d")
            end_dt = datetime.strptime(h["end_date"], "%Y-%m-%d")
            if start_dt <= end_dt:
                rows.append({"Task": h["name"], "Start": start_dt, "Finish": end_dt, "Type": "Holiday"})

    # Seasons
    seasons = data.get("resorts", {}).get(resort, {}).get("years", {}).get(ys, {}).get("seasons", [])
    for s in seasons:
        for i, p in enumerate(s.get("periods", []), 1):
            start_dt = datetime.strptime(p["start"], "%Y-%m-%d")
            end_dt = datetime.strptime(p["end"], "%Y-%m-%d")
            if start_dt <= end_dt:
                rows.append({"Task": f"{s['name']} #{i}", "Start": start_dt, "Finish": end_dt, "Type": s["name"]})

    if not rows:
        today = datetime.now()
        rows = [{"Task": "No Data", "Start": today, "Finish": today + timedelta(days=1), "Type": "No Data"}]

    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])

    color_dict = {
        "Holiday": "rgb(255,99,71)", "Low Season": "rgb(135,206,250)", "High Season": "rgb(255,69,0)",
        "Peak Season": "rgb(255,215,0)", "Shoulder": "rgb(50,205,50)", "Peak": "rgb(255,69,0)",
        "Summer": "rgb(255,165,0)", "Low": "rgb(70,130,180)", "Mid Season": "rgb(60,179,113)",
        "No Data": "rgb(128,128,128)"
    }
    colors = {t: color_dict.get(t, "rgb(169,169,169)") for t in df["Type"].unique()}

    fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Type", color_discrete_map=colors,
                      title=f"{resort} Seasons & Holidays ({year})", height=max(400, len(df) * 35))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Start: %{base|%d %b %Y}<br>End: %{x|%d %b %Y}<extra></extra>")
    fig.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="Period")
    return fig

# ----------------------------------------------------------------------
# Apply discount
# ----------------------------------------------------------------------
def apply_discount(points: int, discount: str | None, date: datetime.date) -> tuple[int, bool]:
    if not discount: return points, False
    if discount == "within_60_days": return math.floor(points * 0.7), True  # 30%
    if discount == "within_30_days": return math.floor(points * 0.75), True  # 25%
    return points, False

# ----------------------------------------------------------------------
# Renter breakdown
# ----------------------------------------------------------------------
def renter_breakdown(resort, room, checkin, nights, rate, discount):
    rows, tot_pts, tot_rent = [], 0, 0
    cur_h, h_end = None, None
    applied, disc_days = False, []
    for i in range(nights):
        d = checkin + timedelta(days=i)
        entry, _ = generate_data(resort, d)
        raw_pts = entry.get(room, 0)
        eff_pts, disc = apply_discount(raw_pts, discount, d)
        if disc:
            applied = True
            disc_days.append(fmt_date(d))
        rent = math.ceil(raw_pts * rate)

        if entry.get("HolidayWeek"):
            if entry.get("HolidayWeekStart"):
                cur_h = entry["holiday_name"]
                h_start = entry["holiday_start"]
                h_end = entry["holiday_end"]
                rows.append({"Date": f"{cur_h} ({fmt_date(h_start)} - {fmt_date(h_end)})",
                             "Day": "", "Points": eff_pts, room: f"${rent}"})
                tot_pts += eff_pts
                tot_rent += rent
            elif cur_h and d <= h_end: continue
        else:
            cur_h = h_end = None
            rows.append({"Date": fmt_date(d), "Day": d.strftime("%a"),
                         "Points": eff_pts, room: f"${rent}"})
            tot_pts += eff_pts
            tot_rent += rent
    return pd.DataFrame(rows), tot_pts, tot_rent, applied, disc_days

# ----------------------------------------------------------------------
# Owner breakdown
# ----------------------------------------------------------------------
def owner_breakdown(resort, room, checkin, nights, disc_mul, inc_maint, inc_cap, inc_dep, rate, cap_per_pt, coc, life, salvage):
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
            elif cur_h and d <= h_end: continue
        else:
            cur_h = h_end = None
            row = {"Date": fmt_date(d), "Day": d.strftime("%a"), "Points": dpts}
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
    return pd.DataFrame(rows), tot_pts, tot_cost, totals["m"], totals["c"], totals["d"]

# ----------------------------------------------------------------------
# Compare renter
# ----------------------------------------------------------------------
def compare_renter(resort, rooms, checkin, nights, rate, discount):
    data_rows = []
    chart_rows = []
    total_rent = {r: 0 for r in rooms}
    holiday_totals = {r: {} for r in rooms}
    applied, disc_days = False, []
    stay_end = checkin + timedelta(days=nights - 1)
    holiday_ranges = []
    data = st.session_state.data
    holidays = data.get("resorts", {}).get(resort, {}).get("years", {}).get(str(checkin.year), {}).get("holidays", [])
    for h in holidays:
        if "start_date" in h and "end_date" in h:
            s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
            if s <= stay_end and e >= checkin:
                holiday_ranges.append((s, e, h["name"]))
    for i in range(nights):
        d = checkin + timedelta(days=i)
        entry, _ = generate_data(resort, d)
        is_holiday = any(s <= d <= e for s, e, _ in holiday_ranges)
        h_name = next((n for s, e, n in holiday_ranges if s <= d <= e), None)
        is_h_start = entry.get("HolidayWeekStart")
        for room in rooms:
            raw_pts = entry.get(room, 0)
            eff_pts, disc = apply_discount(raw_pts, discount, d)
            if disc:
                applied = True
                disc_days.append(fmt_date(d))
            rent = math.ceil(raw_pts * rate)

            if is_holiday and is_h_start:
                if h_name not in holiday_totals[room]:
                    h_start = min(s for s, _, n in holiday_ranges if n == h_name)
                    h_end = max(e for _, e, n in holiday_ranges if n == h_name)
                    holiday_totals[room][h_name] = {"rent": rent, "start": h_start, "end": h_end}
                start_str = fmt_date(holiday_totals[room][h_name]["start"])
                end_str = fmt_date(holiday_totals[room][h_name]["end"])
                data_rows.append({"Date": f"{h_name} ({start_str} - {end_str})",
                                 "Room Type": room, "Rent": f"${rent}"})
                continue
            if not is_holiday:
                data_rows.append({"Date": fmt_date(d),
                                 "Room Type": room, "Rent": f"${rent}"})
                total_rent[room] += rent
                chart_rows.append({"Date": d, "Day": d.strftime("%a"),
                                  "Room Type": room, "RentValue": rent,
                                  "Holiday": "No"})
    total_row = {"Date": "Total Rent (Non-Holiday)"}
    for r in rooms:
        total_row[r] = f"${total_rent[r]}"
    data_rows.append(total_row)
    df = pd.DataFrame(data_rows)
    pivot = df.pivot_table(index="Date", columns="Room Type", values="Rent", aggfunc="first")
    pivot = pivot.reset_index()[["Date"] + [c for c in rooms if c in pivot.columns]]
    holiday_chart = []
    for room in rooms:
        for h, info in holiday_totals[room].items():
            holiday_chart.append({"Holiday": h, "Room Type": room,
                                 "RentValue": info["rent"]})
    holiday_df = pd.DataFrame(holiday_chart)
    chart_df = pd.DataFrame(chart_rows)
    return pivot, chart_df, holiday_df, applied, disc_days

# ----------------------------------------------------------------------
# Compare owner
# ----------------------------------------------------------------------
def compare_owner(resort, rooms, checkin, nights, disc_mul, inc_maint, inc_cap, inc_dep, rate, cap_per_pt, coc, life, salvage):
    data_rows = []
    chart_rows = []
    total_cost = {r: 0 for r in rooms}
    holiday_totals = {r: {} for r in rooms}
    dep_per_pt = (cap_per_pt - salvage) / life if inc_dep else 0
    stay_end = checkin + timedelta(days=nights - 1)
    holiday_ranges = []
    data = st.session_state.data
    holidays = data.get("resorts", {}).get(resort, {}).get("years", {}).get(str(checkin.year), {}).get("holidays", [])
    for h in holidays:
        if "start_date" in h and "end_date" in h:
            s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
            if s <= stay_end and e >= checkin:
                holiday_ranges.append((s, e, h["name"]))
    for i in range(nights):
        d = checkin + timedelta(days=i)
        entry, _ = generate_data(resort, d)
        is_holiday = any(s <= d <= e for s, e, _ in holiday_ranges)
        h_name = next((n for s, e, n in holiday_ranges if s <= d <= e), None)
        is_h_start = entry.get("HolidayWeekStart")
        for room in rooms:
            pts = entry.get(room, 0)
            dpts = math.floor(pts * disc_mul)
            mc = math.ceil(dpts * rate) if inc_maint else 0
            cc = math.ceil(dpts * cap_per_pt * coc) if inc_cap else 0
            dc = math.ceil(dpts * dep_per_pt) if inc_dep else 0
            day_cost = mc + cc + dc
            if is_holiday and is_h_start:
                if h_name not in holiday_totals[room]:
                    h_start = min(s for s, _, n in holiday_ranges if n == h_name)
                    h_end = max(e for _, e, n in holiday_ranges if n == h_name)
                    holiday_totals[room][h_name] = {"cost": day_cost, "start": h_start, "end": h_end}
                start_str = fmt_date(holiday_totals[room][h_name]["start"])
                end_str = fmt_date(holiday_totals[room][h_name]["end"])
                data_rows.append({"Date": f"{h_name} ({start_str} - {end_str})",
                                 "Room Type": room, "Total Cost": f"${day_cost}"})
                continue
            if not is_holiday:
                data_rows.append({"Date": fmt_date(d),
                                 "Room Type": room, "Total Cost": f"${day_cost}"})
                total_cost[room] += day_cost
                chart_rows.append({"Date": d, "Day": d.strftime("%a"),
                                  "Room Type": room, "TotalCostValue": day_cost,
                                  "Holiday": "No"})
    total_row = {"Date": "Total Cost (Non-Holiday)"}
    for r in rooms:
        total_row[r] = f"${total_cost[r]}"
    data_rows.append(total_row)
    df = pd.DataFrame(data_rows)
    pivot = df.pivot_table(index="Date", columns="Room Type", values="Total Cost", aggfunc="first")
    pivot = pivot.reset_index()[["Date"] + [c for c in rooms if c in pivot.columns]]
    holiday_chart = []
    for room in rooms:
        for h, info in holiday_totals[room].items():
            holiday_chart.append({"Holiday": h, "Room Type": room,
                                 "TotalCostValue": info["cost"]})
    holiday_df = pd.DataFrame(holiday_chart)
    chart_df = pd.DataFrame(chart_rows)
    return pivot, chart_df, holiday_df

# ----------------------------------------------------------------------
# Adjust holiday
# ----------------------------------------------------------------------
def adjust_date_range(resort, start, nights):
    end = start + timedelta(days=nights-1)
    ranges = []
    data = st.session_state.data
    holidays = data.get("resorts", {}).get(resort, {}).get("years", {}).get(str(start.year), {}).get("holidays", [])
    for h in holidays:
        if "start_date" in h and "end_date" in h:
            s = datetime.strptime(h["start_date"], "%Y-%m-%d").date()
            e = datetime.strptime(h["end_date"], "%Y-%m-%d").date()
            if s <= end and e >= start:
                ranges.append((s, e, h["name"]))
    if ranges:
        s0 = min(s for s, _, _ in ranges)
        e0 = max(e for _, e, _ in ranges)
        return min(start, s0), (max(end, e0) - min(start, s0)).days + 1, True
    return start, nights, False

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
setup_page()
initialize_session_state()

if st.session_state.data is None:
    try:
        with open("data_v2.json", "r") as f:
            st.session_state.data = json.load(f)
            st.info(f"Loaded {len(st.session_state.data.get('resorts', {}))} resorts")
    except FileNotFoundError:
        st.info("No data_v2.json. Upload file.")
    except Exception as e:
        st.error(f"Error: {e}")

with st.sidebar:
    handle_file_upload()

if not st.session_state.data:
    st.error("No data. Upload JSON.")
    st.stop()

data = st.session_state.data
resorts = list(data.get("resorts", {}).keys())

# Sidebar params
with st.sidebar:
    st.header("Parameters")
    user_mode = st.selectbox("User Mode", ["Renter", "Owner"], index=0)
    default_rate = data.get("configuration", {}).get("maintenance_rates", {}).get(str(datetime.now().year), 0.86)
    if user_mode == "Owner":
        cap_per_pt = st.number_input("Purchase Price per Point ($)", 0.0, step=0.1, value=16.0)
        disc_lvl = st.selectbox("Last-Minute Discount", [0, 25, 30], format_func=lambda x: f"{x}% ({['Ordinary','Executive','Presidential'][x//25]})")
        disc_mul = 1 - disc_lvl/100
        inc_maint = st.checkbox("Include Maintenance Cost", True)
        if inc_maint:
            rate_per_point = st.number_input("Maintenance Rate per Point ($)", 0.0, step=0.01, value=default_rate)
        inc_cap = st.checkbox("Include Capital Cost", True)
        if inc_cap:
            coc = st.number_input("Cost of Capital (%)", 0.0, 100.0, 7.0, 0.1) / 100
        inc_dep = st.checkbox("Include Depreciation Cost", True)
        if inc_dep:
            life = st.number_input("Useful Life (Years)", 1, value=15)
            salvage = st.number_input("Salvage Value per Point ($)", 0.0, value=3.0, step=0.1)
    else:
        st.session_state.allow_renter_modifications = st.checkbox("More Options", st.session_state.allow_renter_modifications)
        if st.session_state.allow_renter_modifications:
            opt = st.radio("Rate Option", ["Based on Maintenance Rate", "Custom Rate", "Booked within 60 days", "Booked within 30 days"])
            if opt == "Based on Maintenance Rate":
                rate_per_point, discount_opt = default_rate, None
            elif opt == "Booked within 60 days":
                rate_per_point, discount_opt = default_rate, "within_60_days"
            elif opt == "Booked within 30 days":
                rate_per_point, discount_opt = default_rate, "within_30_days"
            else:
                rate_per_point = st.number_input("Custom Rate per Point ($)", 0.0, step=0.01, value=default_rate)
                discount_opt = None
        else:
            rate_per_point = default_rate
            discount_opt = None

# Resort grid
st.subheader("🏨 Select Resort")
cols = st.columns(6)
current_resort = st.session_state.current_resort
for i, resort in enumerate(resorts):
    with cols[i % 6]:
        button_type = "primary" if current_resort == resort else "secondary"
        if st.button(resort, key=f"resort_btn_{i}", type=button_type):
            st.session_state.current_resort = resort
            st.rerun()
resort = current_resort
if not resort:
    st.warning("Please select a resort.")
    st.stop()

st.title(f"Marriott Vacation Club {'Rent' if user_mode=='Renter' else 'Cost'} Calculator")

# Inputs
col1, col2, col3, col4 = st.columns(4)
with col1:
    checkin = st.date_input("Check-in Date", value=datetime(2026, 6, 12).date(),
                            min_value=datetime(2025, 1, 3).date(), max_value=datetime(2026, 12, 31).date())
with col2:
    nights = st.number_input("Number of Nights", 1, 30, 7)
with col3:
    if st.session_state.room_types is None:
        entry, d2i = generate_data(resort, checkin)
        st.session_state.room_types = sorted([k for k in entry if k not in {"HolidayWeek", "HolidayWeekStart", "holiday_name", "holiday_start", "holiday_end"}])
        st.session_state.disp_to_int = d2i
    room = st.selectbox("Select Room Type", st.session_state.room_types)
with col4:
    compare = st.multiselect("Compare With", [r for r in st.session_state.room_types if r != room])

# Holiday adjust
checkin_adj, nights_adj, adjusted = adjust_date_range(resort, checkin, nights)
if adjusted:
    end_date = checkin_adj + timedelta(days=nights_adj - 1)
    st.info(f"Adjusted to full holiday: **{fmt_date(checkin_adj)}** to **{fmt_date(end_date)}** ({nights_adj} nights)")

# Expander
with st.expander("How " + ("Rent" if user_mode=="Renter" else "Cost") + " Is Calculated"):
    if user_mode == "Renter":
        st.markdown(f"""
        - Rental Rate per Point based on MVC Abound maintenance fees
        - Default: **${default_rate:.2f}/point** for {checkin.year} (from data_v2.json)
        - **Booked within 60 days**: 30% discount on points required (Presidential)
        - **Booked within 30 days**: 25% discount on points required (Executive)
        - **Rent = Full Points × Rate** (discount does NOT reduce rent)
        """)
    else:
        st.markdown("""
        - Cost of capital = Points × Purchase Price per Point × Cost of Capital %
        - Depreciation = Points × [(Purchase Price – Salvage) ÷ Useful Life]
        - Total cost = Maintenance + Capital Cost + Depreciation
        """)

# Automatic calculation
gantt = gantt_chart(resort, checkin.year)

if user_mode == "Renter":
    df, pts, rent, disc_ap, disc_days = renter_breakdown(resort, room, checkin_adj, nights_adj, rate_per_point, discount_opt)
    st.subheader(f"{resort} Stay Breakdown")
    st.dataframe(df, use_container_width=True)
    # Always show discount message
    if discount_opt:
        disc_pct = 30 if discount_opt == "within_60_days" else 25
        days_str = f"({len(disc_days)} day(s): {', '.join(disc_days)})" if disc_days else "(0 days)"
        st.success(f"Discount Applied: {disc_pct}% off points {days_str}")
    else:
        st.success("Discount Applied: 0% off points (0 days)")
    st.success(f"Total Points Required: {pts:,} | Total Rent: ${rent:,}")
    st.download_button("Download CSV", df.to_csv(index=False).encode(),
                       f"{resort}_{fmt_date(checkin_adj).replace(' ', '_')}_breakdown.csv", "text/csv")
else:
    df, pts, cost, m_cost, c_cost, d_cost = owner_breakdown(resort, room, checkin_adj, nights_adj, disc_mul,
                                                           inc_maint, inc_cap, inc_dep, rate_per_point, cap_per_pt, coc, life, salvage)
    cols = ["Date", "Day", "Points"]
    if inc_maint or inc_cap or inc_dep:
        if inc_maint: cols.append("Maintenance")
        if inc_cap: cols.append("Capital Cost")
        if inc_dep: cols.append("Depreciation")
        cols.append("Total Cost")
    st.subheader(f"{resort} Stay Breakdown")
    st.dataframe(df[cols], use_container_width=True)
    st.success(f"Total Points Used: {pts:,} | Total Cost: ${cost:,}")
    if inc_maint and m_cost: st.success(f"Maintenance: ${m_cost:,}")
    if inc_cap and c_cost: st.success(f"Capital Cost: ${c_cost:,}")
    if inc_dep and d_cost: st.success(f"Depreciation: ${d_cost:,}")
    st.download_button("Download CSV", df.to_csv(index=False).encode(),
                       f"{resort}_{fmt_date(checkin_adj).replace(' ', '_')}_breakdown.csv", "text/csv")

# Comparison
if compare:
    all_rooms = [room] + compare
    if user_mode == "Renter":
        pivot, chart_df, holiday_df, _, _ = compare_renter(resort, all_rooms, checkin_adj, nights_adj, rate_per_point, discount_opt)
        st.subheader(f"{resort} Room-Type Comparison")
        st.dataframe(pivot, use_container_width=True)
        st.download_button("Download Comparison CSV", pivot.to_csv(index=False).encode(),
                           f"{resort}_{fmt_date(checkin_adj).replace(' ', '_')}_comparison.csv", "text/csv")
        if not chart_df.empty:
            day_order = ["Fri","Sat","Sun","Mon","Tue","Wed","Thu"]
            fig = px.bar(chart_df, x="Day", y="RentValue", color="Room Type", barmode="group", text="RentValue", height=600,
                         category_orders={"Day": day_order})
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="auto")
            st.plotly_chart(fig, use_container_width=True)
        if not holiday_df.empty:
            fig = px.bar(holiday_df, x="Holiday", y="RentValue", color="Room Type", barmode="group", text="RentValue", height=600)
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="auto")
            st.plotly_chart(fig, use_container_width=True)
    else:
        pivot, chart_df, holiday_df = compare_owner(resort, all_rooms, checkin_adj, nights_adj, disc_mul,
                                                   inc_maint, inc_cap, inc_dep, rate_per_point, cap_per_pt, coc, life, salvage)
        st.subheader(f"{resort} Room-Type Cost Comparison")
        st.dataframe(pivot, use_container_width=True)
        st.download_button("Download Comparison CSV", pivot.to_csv(index=False).encode(),
                           f"{resort}_{fmt_date(checkin_adj).replace(' ', '_')}_comparison.csv", "text/csv")
        if not chart_df.empty:
            day_order = ["Fri","Sat","Sun","Mon","Tue","Wed","Thu"]
            fig = px.bar(chart_df, x="Day", y="TotalCostValue", color="Room Type", barmode="group", text="TotalCostValue", height=600,
                         category_orders={"Day": day_order})
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="auto")
            st.plotly_chart(fig, use_container_width=True)
        if not holiday_df.empty:
            fig = px.bar(holiday_df, x="Holiday", y="TotalCostValue", color="Room Type", barmode="group", text="TotalCostValue", height=600)
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="auto")
            st.plotly_chart(fig, use_container_width=True)

st.plotly_chart(gantt, use_container_width=True)
