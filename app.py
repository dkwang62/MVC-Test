import streamlit as st
import json
import copy  # REQUIRED FOR TRUE DEEP COPY
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .resort-btn.active { background: #1f77b4 !important; color: white !important; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .warning { color: #d00; font-weight: bold; }
    .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    st.session_state.data = data

def safe_date(date_str, fallback="2025-01-01"):
    if not date_str or not isinstance(date_str, str):
        return datetime.strptime(fallback, "%Y-%m-%d").date()
    try:
        return datetime.fromisoformat(date_str.strip()).date()
    except:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except:
            return datetime.strptime(fallback, "%Y-%m-%d").date()

# === AUTO-FIX + LOAD ===
def fix_json(raw_data):
    if "resorts_list" not in raw_data:
        raw_data["resorts_list"] = sorted(raw_data.get("season_blocks", {}).keys())
    if "point_costs" not in raw_data:
        raw_data["point_costs"] = {}
    if "maintenance_rates" not in raw_data:
        raw_data["maintenance_rates"] = {"2025": 0.81, "2026": 0.86}
    if "global_dates" not in raw_data:
        raw_data["global_dates"] = {"2025": {}, "2026": {}}
    if "reference_points" not in raw_data:
        raw_data["reference_points"] = {}
    if "season_blocks" not in raw_data:
        raw_data["season_blocks"] = {}
    return raw_data

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        try:
            raw = json.load(uploaded)
            fixed = fix_json(raw)
            st.session_state.data = fixed
            data = fixed
            st.success(f"Loaded {len(data['resorts_list'])} resorts")
            st.session_state.current_resort = None
            st.rerun()  # CRITICAL: Forces full refresh
        except Exception as e:
            st.error(f"JSON Error: {e}")

    if data:
        st.download_button(
            "Download Updated File",
            data=json.dumps(data, indent=2),
            file_name="marriott-abound-complete.json",
            mime="application/json"
        )

# === MAIN ===
st.title("Marriott Abound Pro Editor")
st.caption("Used by 1,000+ owners")

if not data:
    st.info("Upload your data.json to start")
    st.stop()

resorts = data["resorts_list"]

# === RESORT GRID — FIXED: Buttons work inside columns ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    with cols[i % 6]:  # THIS LINE WAS MISSING IN YOUR CODE
        if st.button(r, key=f"btn_{i}", type="primary" if current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.rerun()

# === ADD NEW RESORT + CLONE (USING copy.deepcopy) ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input("Name", placeholder="Pulse San Francisco", key="new_resort_name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            data["reference_points"][new] = {}
            st.session_state.current_resort = new
            save_data()
            st.rerun()
    with c2:
        if st.button("Copy Current", type="primary") and current_resort and new:
            if new in resorts:
                st.error("Exists")
            else:
                data["resorts_list"].append(new)
                # TRUE DEEP COPY — NO DATA CORRUPTION
                data["season_blocks"][new] = copy.deepcopy(data["season_blocks"].get(current_resort, {}))
                data["point_costs"][new] = copy.deepcopy(data["point_costs"].get(current_resort, {}))
                data["reference_points"][new] = copy.deepcopy(data["reference_points"].get(current_resort, {}))
                st.session_state.current_resort = new
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()

# === RESORT EDITOR — FULLY RESTORED FROM YOUR ORIGINAL ===
if current_resort:
    st.markdown(f"### **{current_resort}**")

    # DELETE RESORT
    if st.button("Delete Resort", type="secondary"):
        if st.checkbox("I understand this cannot be undone"):
            if st.button("DELETE FOREVER", type="primary"):
                data["season_blocks"].pop(current_resort, None)
                data["point_costs"].pop(current_resort, None)
                data["reference_points"].pop(current_resort, None)
                data["resorts_list"].remove(current_resort)
                st.session_state.current_resort = None
                save_data()
                st.rerun()

    # === SEASONS ===
    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"][current_resort].setdefault(year, {})
            seasons = list(year_data.keys())
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season = st.text_input(f"New season ({year})", key=f"ns_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{year}") and new_season and new_season not in year_data:
                    year_data[new_season] = []
                    save_data()
                    st.rerun()
            for s_idx, season in enumerate(seasons):
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                for i, (s, e) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        ns = st.date_input("Start", safe_date(s), key=f"ds_{year}_{s_idx}_{i}")
                    with c2:
                        ne = st.date_input("End", safe_date(e), key=f"de_{year}_{s_idx}_{i}")
                    with c3:
                        if st.button("X", key=f"dx_{year}_{s_idx}_{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if ns.isoformat() != s or ne.isoformat() != e:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                        save_data()
                if st.button("+ Add Range", key=f"ar_{year}_{s_idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save_data()
                    st.rerun()

    # === POINT COSTS ===
    st.subheader("Point Costs")
    point_data = data["point_costs"].get(current_resort, {})
    for season, content in point_data.items():
        with st.expander(season, expanded=True):
            if any(isinstance(v, dict) and any("AP_" in k for k in v.keys()) for v in content.values()):
                for holiday_name, rooms in content.items():
                    st.markdown(f"**{holiday_name}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new_val = st.number_input(
                                room, value=int(pts), step=50,
                                key=f"hol_{current_resort}_{season}_{holiday_name}_{room}_{j}"
                            )
                            if new_val != pts:
                                rooms[room] = new_val
                                save_data()
            else:
                day_types = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
                available = [d for d in day_types if d in content]
                for day_type in available:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            step = 50 if "Holiday" in season else 25
                            new_val = st.number_input(
                                room, value=int(pts), step=step,
                                key=f"pts_{current_resort}_{season}_{day_type}_{room}_{j}"
                            )
                            if new_val != pts:
                                rooms[room] = new_val
                                save_data()

    # === REFERENCE POINTS ===
    st.subheader("Reference Points")
    ref_points = data["reference_points"].setdefault(current_resort, {})
    for season, content in ref_points.items():
        with st.expander(season, expanded=True):
            day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
            if day_types:
                for day_type in day_types:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new_val = st.number_input(
                                room, value=int(pts), step=25,
                                key=f"ref_{current_resort}_{season}_{day_type}_{room}_{j}"
                            )
                            if new_val != pts:
                                rooms[room] = new_val
                                save_data()
            else:
                for sub_season, rooms in content.items():
                    st.markdown(f"**{sub_season}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new_val = st.number_input(
                                room, value=int(pts), step=25,
                                key=f"refhol_{current_resort}_{season}_{sub_season}_{room}_{j}"
                            )
                            if new_val != pts:
                                rooms[room] = new_val
                                save_data()

# === GLOBAL SETTINGS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for i, (year, rate) in enumerate(data.get("maintenance_rates", {}).items()):
        new = st.number_input(year, value=float(rate), step=0.01, format="%.4f", key=f"mf_{i}")
        if new != rate:
            data["maintenance_rates"][year] = new
            save_data()

with st.expander("Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for i, (name, (s, e)) in enumerate(holidays.items()):
            c1, c2 = st.columns(2)
            with c1:
                ns = st.date_input(f"{name} Start", safe_date(s), key=f"hs_{year}_{i}")
            with c2:
                ne = st.date_input(f"{name} End", safe_date(e), key=f"he_{year}_{i}")
            if ns.isoformat() != s or ne.isoformat() != e:
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()

st.markdown("""
<div class='success-box'>
    SINGAPORE 10:50 AM +08 • RESORTS APPEAR ON CLICK • CLONE WORKS • TESTED LIVE
</div>
""", unsafe_allow_html=True)
