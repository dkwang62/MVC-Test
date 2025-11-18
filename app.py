import streamlit as st
import math
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px

# ----------------------------------------------------------------------
# Setup page
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(page_title="MVC Calculator", layout="wide")
    st.markdown("""
    <style>
        .stButton button {
            font-size: 12px !important;
            padding: 5px 10px !important;
            height: auto !important;
        }
        .block-container {
            padding-top: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Initialize session state
# ----------------------------------------------------------------------
def initialize_session_state():
    defaults = {
        "data": None,
        "current_resort": None,
        "data_cache": {},
        "allow_renter_modifications": False,
        "last_resort": None,
        "last_year": None,
        "room_types": None,
        "disp_to_int": None
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

# ----------------------------------------------------------------------
# File handling
# ----------------------------------------------------------------------
def handle_file_upload():
    uploaded_file = st.file_uploader("Upload JSON file", type="json")
    if uploaded_file:
        try:
            raw_data = json.load(uploaded_file)
            st.session_state.data = raw_data
            st.success("File uploaded successfully!")
        except Exception as e:
            st.error(f"Error loading file: {e}")

# ----------------------------------------------------------------------
# Custom date formatter
# ----------------------------------------------------------------------
def fmt_date(d):
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    elif isinstance(d, (pd.Timestamp, datetime)):
        d = d.date()
    return d.strftime("%d %b %Y")

# ----------------------------------------------------------------------
# Core helpers & data generation (same as before, kept unchanged)
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
    if key in legend:
        return legend[key]
    if key.startswith("AP_"):
        return {"AP_Studio_MA": "AP Studio Mountain", "AP_1BR_MA": "AP 1BR Mountain",
                "AP_2BR_MA": "AP 2BR Mountain", "AP_2BR_MK": "AP 2BR Ocean"}.get(key, key)
    parts = key.split()
    view = parts[-1] if len(parts) > 1 and parts[-1] in legend else ""
    return f"{parts[0]} {legend.get(view, view)}" if view else key

def resolve_global(year: str, key: str) -> list:
    return st.session_state.data.get("global_dates", {}).get(year, {}).get(key, [])

# [Keep generate_data, gantt_chart, renter_breakdown, owner_breakdown, compare_renter, compare_owner, adjust_date_range functions exactly as before]
# (Omitted here for brevity — copy them unchanged from your current code)

# ----------------------------------------------------------------------
# Main App
# ----------------------------------------------------------------------
setup_page()
initialize_session_state()

# Load data
if st.session_state.data is None:
    try:
        with open("data.json", "r") as f:
            st.session_state.data = json.load(f)
            st.info(f"Loaded {len(st.session_state.data.get('resorts_list', []))} resorts from data.json")
    except FileNotFoundError:
        st.info("No data.json found. Please upload a file.")
    except Exception as e:
        st.error(f"Error loading data.json: {e}")

with st.sidebar:
    handle_file_upload()

if not st.session_state.data:
    st.error("No data loaded. Please upload a JSON file.")
    st.stop()

data = st.session_state.data
ROOM_VIEW_LEGEND = data.get("room_view_legend", {})
SEASON_BLOCKS = data.get("season_blocks", {})
REF_POINTS = data.get("reference_points", {})
HOLIDAY_WEEKS = data.get("holiday_weeks", {})
resorts = data.get("resorts_list", [])

# --- SIDEBAR: User Mode & Parameters (Always Visible) ---
with st.sidebar:
    st.header("Mode & Parameters")
    user_mode = st.selectbox("User Mode", ["Renter", "Owner"], key="mode")

    default_rate = data.get("maintenance_rates", {}).get("2026", 0.86)

    if user_mode == "Owner":
        cap_per_pt = st.number_input("Purchase Price per Point ($)", 0.0, step=0.1, value=16.0, key="cap_per_pt")
        disc_lvl = st.selectbox("Last-Minute Discount", [0, 25, 30],
                                format_func=lambda x: f"{x}% ({['Ordinary','Executive','Presidential'][x//25]})",
                                key="disc_lvl")
        disc_mul = 1 - disc_lvl/100

        inc_maint = st.checkbox("Include Maintenance Cost", True, key="inc_maint")
        rate_per_point = st.number_input("Maintenance Rate per Point ($)", 0.0, step=0.01, value=default_rate,
                                         disabled=not inc_maint, key="maint_rate")

        inc_cap = st.checkbox("Include Capital Cost", True, key="inc_cap")
        if inc_cap:
            coc = st.number_input("Cost of Capital (%)", 0.0, 100.0, 7.0, 0.1, key="coc") / 100

        inc_dep = st.checkbox("Include Depreciation Cost", True, key="inc_dep")
        if inc_dep:
            life = st.number_input("Useful Life (Years)", 1, value=15, key="life")
            salvage = st.number_input("Salvage Value per Point ($)", 0.0, value=3.0, step=0.1, key="salvage")

    else:  # Renter mode
        st.session_state.allow_renter_modifications = st.checkbox("More Options", key="allow_renter_mod")
        if st.session_state.allow_renter_modifications:
            opt = st.radio("Rate Option", [
                "Based on Maintenance Rate", "Custom Rate",
                "Booked within 60 days", "Booked within 30 days"
            ], key="rate_opt")
            if opt == "Custom Rate":
                rate_per_point = st.number_input("Custom Rate per Point ($)", 0.0, step=0.01, value=default_rate, key="custom_rate")
                discount_opt = None
            elif "within_60_days" in opt:
                rate_per_point, discount_opt = default_rate, "within_60_days"
            elif "within_30_days" in opt:
                rate_per_point, discount_opt = default_rate, "within_30_days"
            else:
                rate_per_point, discount_opt = default_rate, None
        else:
            rate_per_point, discount_opt = default_rate, None

# --- Resort Selection ---
st.subheader("Select Resort")
cols = st.columns(6)
current_resort = st.session_state.current_resort
for i, resort_name in enumerate(resorts):
    with cols[i % 6]:
        if st.button(resort_name, key=f"resort_{i}",
                     type="primary" if current_resort == resort_name else "secondary"):
            st.session_state.current_resort = resort_name
            st.rerun()

resort = st.session_state.current_resort
if not resort:
    st.warning("Please select a resort to continue.")
    st.stop()

# --- Main Inputs ---
st.title(f"Marriott Vacation Club {'Rent' if user_mode=='Renter' else 'Cost'} Calculator")

checkin = st.date_input("Check-in Date", value=datetime(2026, 6, 12).date(),
                        min_value=datetime(2025, 1, 3).date(),
                        max_value=datetime(2026, 12, 31).date(), key="checkin")
nights = st.number_input("Number of Nights", 1, 30, 7, key="nights")

# Cache management
year = str(checkin.year)
if (st.session_state.last_resort != resort or st.session_state.last_year != year):
    st.session_state.data_cache.clear()
    st.session_state.room_types = None
    st.session_state.last_resort = resort
    st.session_state.last_year = year

# Load room types
if st.session_state.room_types is None:
    entry, d2i = generate_data(resort, checkin)
    st.session_state.room_types = sorted([k for k in entry.keys() if k not in
                                          {"HolidayWeek", "HolidayWeekStart", "holiday_name",
                                           "holiday_start", "holiday_end"}])
    st.session_state.disp_to_int = d2i

room = st.selectbox("Select Room Type", st.session_state.room_types, key="room_sel")
compare = st.multiselect("Compare With", [r for r in st.session_state.room_types if r != room], key="compare")

# Adjust dates for full holiday weeks
checkin_adj, nights_adj, adjusted = adjust_date_range(resort, checkin, nights)
if adjusted:
    end_date = checkin_adj + timedelta(days=nights_adj - 1)
    st.info(f"Adjusted to full holiday week: **{fmt_date(checkin_adj)} – {fmt_date(end_date)}** ({nights_adj} nights)")

# --- AUTOMATIC CALCULATION (No Button!) ---
gantt = gantt_chart(resort, checkin.year)

if user_mode == "Renter":
    df, pts, rent, disc_applied, disc_days = renter_breakdown(
        resort, room, checkin_adj, nights_adj, rate_per_point, discount_opt)
    
    st.subheader(f"{resort} Rental Breakdown")
    st.dataframe(df, use_container_width=True)
    
    if discount_opt and disc_applied:
        pct = 30 if discount_opt == "within_60_days" else 25
        st.success(f"Discount Applied: {pct}% off points ({len(disc_days)} day(s): {', '.join(disc_days)})")
    
    st.success(f"Total Points Required: {pts:,} | Total Rent: ${rent:,}")
    st.download_button("Download Breakdown CSV", df.to_csv(index=False),
                       f"{resort}_{fmt_date(checkin_adj)}_rental.csv", "text/csv")

else:  # Owner mode
    df, pts, cost, m_cost, c_cost, d_cost = owner_breakdown(
        resort, room, checkin_adj, nights_adj, disc_mul,
        inc_maint, inc_cap, inc_dep,
        rate_per_point, cap_per_pt,
        coc if 'coc' in locals() else 0.07,
        life if 'life' in locals() else 15,
        salvage if 'salvage' in locals() else 3.0)

    cols = ["Date", "Day", "Points"]
    if inc_maint or inc_cap or inc_dep:
        if inc_maint: cols.append("Maintenance")
        if inc_cap: cols.append("Capital Cost")
        if inc_dep: cols.append("Depreciation")
        cols.append("Total Cost")

    st.subheader(f"{resort} Ownership Cost Breakdown")
    st.dataframe(df[cols], use_container_width=True)
    st.success(f"Total Points Used: {pts:,} | Total Cost: ${cost:,}")
    if inc_maint and m_cost: st.info(f"Maintenance: ${m_cost:,}")
    if inc_cap and c_cost: st.info(f"Capital Cost: ${c_cost:,}")
    if inc_dep and d_cost: st.info(f"Depreciation: ${d_cost:,}")
    st.download_button("Download Cost CSV", df.to_csv(index=False),
                       f"{resort}_{fmt_date(checkin_adj)}_cost.csv", "text/csv")

# --- Comparison ---
if compare:
    all_rooms = [room] + compare
    if user_mode == "Renter":
        pivot, chart_df, holiday_df, _, _ = compare_renter(resort, all_rooms, checkin_adj, nights_adj, rate_per_point, discount_opt)
    else:
        pivot, chart_df, holiday_df = compare_owner(resort, all_rooms, checkin_adj, nights_adj, disc_mul,
                                                    inc_maint, inc_cap, inc_dep,
                                                    rate_per_point, cap_per_pt,
                                                    coc if 'coc' in locals() else 0.07,
                                                    life if 'life' in locals() else 15,
                                                    salvage if 'salvage' in locals() else 3.0)

    st.subheader("Room Type Comparison")
    st.dataframe(pivot, use_container_width=True)
    if not chart_df.empty:
        fig = px.bar(chart_df, x="Day", y="RentValue" if user_mode == "Renter" else "TotalCostValue",
                     color="Room Type", barmode="group", text_auto=True,
                     category_orders={"Day": ["Fri","Sat","Sun","Mon","Tue","Wed","Thu"]})
        st.plotly_chart(fig, use_container_width=True)
    if not holiday_df.empty:
        fig = px.bar(holiday_df, x="Holiday", y="RentValue" if user_mode == "Renter" else "TotalCostValue",
                     color="Room Type", barmode="group", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

# --- Gantt Chart ---
st.plotly_chart(gantt, use_container_width=True)
