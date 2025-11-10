import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .css-1d391kg { padding-top: 2rem; }
    .resort-btn.active { background: #1a3c6e !important; color: white !important; }
    .stButton>button { min-height: 45px; }
    .warning { color: #d00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- Session State ---
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
        return datetime.fromisoformat(date_str).date()
    except:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return datetime.strptime(fallback, "%Y-%m-%d").date()

# --- Sidebar ---
with st.sidebar:
    st.header("1. Load Data")
    uploaded = st.file_uploader("Upload JSON", type="json")
    if uploaded:
        try:
            st.session_state.data = json.load(uploaded)
            data = st.session_state.data
            st.success("Loaded!")
            st.session_state.current_resort = None
        except Exception as e:
            st.error(f"Error: {e}")

    if data:
        json_str = json.dumps(data, indent=2)
        st.download_button(
            "Download Updated JSON",
            data=json_str,
            file_name="marriott-updated.json",
            mime="application/json"
        )

# --- Main ---
st.title("Marriott Abound Season & Points Editor")
st.warning("Always backup your original file!")

if not data:
    st.info("Upload a JSON file to start.")
    st.stop()

# --- Resort Selection ---
st.header("2. Select Resort")
cols = st.columns(6)
for i, name in enumerate(data.get("resorts_list", [])):
    col = cols[i % 6]
    if col.button(name, key=f"r_{name}", type="primary" if current_resort == name else "secondary"):
        st.session_state.current_resort = name
        st.rerun()

with st.expander("Add New Resort"):
    new_name = st.text_input("Resort name")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create Blank") and new_name and new_name not in data["resorts_list"]:
            data["resorts_list"].append(new_name)
            data["season_blocks"][new_name] = {"2025": {}, "2026": {}}
            data["point_costs"][new_name] = {}
            st.session_state.current_resort = new_name
            save_data()
            st.rerun()
    with col2:
        if st.button("Copy Current") and current_resort and new_name:
            if new_name in data["resorts_list"]:
                st.error("Name taken")
            else:
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                data["point_costs"][new_name] = json.loads(json.dumps(data["point_costs"][current_resort]))
                st.session_state.current_resort = new_name
                save_data()
                st.rerun()

if current_resort:
    st.markdown(f"### Editing: **{current_resort}**")
    if st.button("Delete Resort", type="secondary"):
        if st.checkbox("I understand this is permanent"):
            if st.button("DELETE FOREVER", type="primary"):
                del data["season_blocks"][current_resort]
                del data["point_costs"][current_resort]
                data["resorts_list"].remove(current_resort)
                st.session_state.current_resort = None
                save_data()
                st.rerun()

    # --- Seasons ---
    st.subheader("Season Date Ranges")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"].setdefault(current_resort, {}).setdefault(year, {})
            seasons = list(year_data.keys())

            new_season = st.text_input(f"New season ({year})", key=f"ns_{year}")
            if st.button(f"Add '{new_season}'") and new_season:
                year_data[new_season] = []
                save_data()
                st.rerun()

            for season in seasons:
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                for i, (start, end) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        s = st.date_input("Start", value=safe_date(start), key=f"start_{year}_{season}_{i}")
                    with c2:
                        e = st.date_input("End", value=safe_date(end), key=f"end_{year}_{season}_{i}")
                    with c3:
                        if st.button("X", key=f"del_{year}_{season}_{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if s.isoformat() != start or e.isoformat() != end:
                        ranges[i] = [s.isoformat(), e.isoformat()]
                        save_data()

                if st.button(f"+ Add Range to {season}", key=f"addr_{year}_{season}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save_data()
                    st.rerun()

    # --- Points ---
    st.subheader("Point Costs")
    points = data["point_costs"].setdefault(current_resort, {})
    for season in list(points.keys()):
        with st.expander(season, expanded=True):
            sdata = points[season]
            if "Fri-Sat" in sdata or "Sun-Thu" in sdata:
                for dtype in ["Fri-Sat", "Sun-Thu"]:
                    if dtype not in sdata: continue
                    st.write(f"**{dtype}**")
                    cols = st.columns(4)
                    for j, room in enumerate(sdata[dtype]):
                        with cols[j % 4]:
                            val = sdata[dtype][room]
                            new = st.number_input(room, value=val, step=50, key=f"p_{season}_{dtype}_{room}")
                            if new != val:
                                sdata[dtype][room] = int(new)
                                save_data()
            else:
                st.write("**Holiday Weeks**")
                hw = sdata.get("Holiday Week", {})
                for hol in hw:
                    st.markdown(f"**{hol}**")
                    cols = st.columns(4)
                    for j, room in enumerate(hw[hol]):
                        with cols[j % 4]:
                            val = hw[hol][room]
                            new = st.number_input(room, value=val, step=50, key=f"h_{season}_{hol}_{room}")
                            if new != val:
                                hw[hol][room] = int(new)
                                save_data()

# --- Global Settings ---
st.header("Global Settings")

with st.expander("Maintenance Rates"):
    for year in data.get("maintenance_rates", {}):
        rate = data["maintainment_rates"][year]
        new = st.number_input(f"{year}", value=float(rate), step=0.01, key=f"mr_{year}")
        if new != rate:
            data["maintenance_rates"][year] = new
            save_data()

with st.expander("Global Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for hol in holidays:
            start, end = holidays[hol]
            c1, c2 = st.columns(2)
            with c1:
                s = st.date_input(f"{hol} Start", value=safe_date(start), key=f"ghs_{year}_{hol}")
            with c2:
                e = st.date_input(f"{hol} End", value=safe_date(end), key=f"ghe_{year}_{hol}")
            if s.isoformat() != start or e.isoformat() != end:
                data["global_dates"][year][hol] = [s.isoformat(), e.isoformat()]
                save_data()

st.success("All changes saved instantly!")
