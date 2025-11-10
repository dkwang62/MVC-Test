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
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(date_str, fmt).date()
        except:
            continue
    return datetime.strptime(fallback, "%Y-%m-%d").date()

# --- Sidebar ---
with st.sidebar:
    st.header("1. Load Data")
    uploaded = st.file_uploader("Upload your Marriott JSON", type="json")
    if uploaded:
        try:
            raw_data = json.load(uploaded)
            if "resorts_list" not in raw_data:
                raw_data["resorts_list"] = sorted(raw_data["season_blocks"].keys())
            st.session_state.data = raw_data
            data = st.session_state.data
            st.success("Loaded & Fixed!")
            st.session_state.current_resort = None
        except Exception as e:
            st.error(f"Error: {e}")

    if data:
        st.download_button(
            "Download Updated JSON",
            data=json.dumps(data, indent=2),
            file_name="marriott-abound-updated.json",
            mime="application/json"
        )

# --- Main ---
st.title("Marriott Abound Season & Points Editor")
st.warning("Always backup! All changes auto-save.")

if not data:
    st.info("Upload your JSON file to start.")
    st.stop()

# --- Resort Selection ---
st.header("2. Select Resort")
resorts = data.get("resorts_list", [])
if not resorts:
    st.error("No resorts found!")
    st.stop()

cols = st.columns(6)
for i, name in enumerate(resorts):
    if cols[i % 6].button(name, key=f"resort_btn_{i}", type="primary" if current_resort == name else "secondary"):
        st.session_state.current_resort = name
        st.rerun()

with st.expander("Add New Resort"):
    new_name = st.text_input("New resort name", key="new_resort_name")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank", key="create_blank"):
            if new_name and new_name not in resorts:
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = {"2025": {}, "2026": {}}
                data["point_costs"][new_name] = {}
                st.session_state.current_resort = new_name
                save_data()
                st.rerun()
            else:
                st.error("Invalid or duplicate name")
    with c2:
        if st.button("Copy Current Resort", key="copy_current") and current_resort:
            copy_name = st.text_input("Copy as", value=f"{current_resort} Copy", key="copy_name")
            if st.button("Create Copy", key="do_copy"):
                if copy_name in resorts:
                    st.error("Name taken")
                else:
                    data["resorts_list"].append(copy_name)
                    data["season_blocks"][copy_name] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                    data["point_costs"][copy_name] = json.loads(json.dumps(data["point_costs"][current_resort]))
                    st.session_state.current_resort = copy_name
                    save_data()
                    st.rerun()

if current_resort:
    st.markdown(f"### Editing: **{current_resort}**")
    if st.button("Delete This Resort", type="secondary", key="delete_resort_btn"):
        if st.checkbox("I understand this is permanent", key="confirm_delete"):
            if st.button("DELETE FOREVER", type="primary", key="confirm_delete_final"):
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

            col1, col2 = st.columns([3, 1])
            with col1:
                new_season = st.text_input(f"New season ({year})", key=f"new_season_input_{year}")
            with col2:
                if st.button("Add Season", key=f"add_season_btn_{year}"):
                    if new_season and new_season not in year_data:
                        year_data[new_season] = []
                        save_data()
                        st.rerun()
                    else:
                        st.error("Invalid or exists")

            for season_idx, season in enumerate(seasons):
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                for i, (start, end) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        s = st.date_input("Start", value=safe_date(start), key=f"start_{year}_{season_idx}_{i}")
                    with c2:
                        e = st.date_input("End", value=safe_date(end), key=f"end_{year}_{season_idx}_{i}")
                    with c3:
                        if st.button("X", key=f"del_range_{year}_{season_idx}_{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if s.isoformat() != start or e.isoformat() != end:
                        ranges[i] = [s.isoformat(), e.isoformat()]
                        save_data()

                if st.button(f"+ Add Range", key=f"add_range_btn_{year}_{season_idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save_data()
                    st.rerun()

    # --- Point Costs ---
    st.subheader("Point Costs")
    points = data["point_costs"].setdefault(current_resort, {})
    for season_idx, season in enumerate(points.keys()):
        with st.expander(season, expanded=True):
            sdata = points[season]
            if "Fri-Sat" in sdata or "Sun-Thu" in sdata:
                for dtype in ["Fri-Sat", "Sun-Thu"]:
                    if dtype not in sdata: continue
                    st.write(f"**{dtype}**")
                    cols = st.columns(4)
                    rooms = list(sdata[dtype].keys())
                    for j, room in enumerate(rooms):
                        with cols[j % 4]:
                            val = sdata[dtype][room]
                            new = st.number_input(room, value=int(val), step=25, key=f"pt_{season_idx}_{dtype}_{j}")
                            if new != val:
                                sdata[dtype][room] = new
                                save_data()
            else:
                st.write("**Holiday Weeks**")
                for hol_idx, hol in enumerate(sdata.keys()):
                    st.markdown(f"**{hol}**")
                    cols = st.columns(4)
                    rooms = list(sdata[hol].keys())
                    for j, room in enumerate(rooms):
                        with cols[j % 4]:
                            val = sdata[hol][room]
                            new = st.number_input(room, value=int(val), step=50, key=f"hol_{season_idx}_{hol_idx}_{j}")
                            if new != val:
                                sdata[hol][room] = new
                                save_data()

# --- Global Settings ---
st.header("Global Settings")

with st.expander("Maintenance Fees"):
    for i, year in enumerate(data.get("maintenance_rates", {})):
        rate = data["maintenance_rates"][year]
        new_rate = st.number_input(f"{year}", value=float(rate), step=0.01, format="%.4f", key=f"mf_rate_{i}")
        if new_rate != rate:
            data["maintenance_rates"][year] = new_rate
            save_data()

with st.expander("Global Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for hol_idx, hol in enumerate(holidays):
            start, end = holidays[hol]
            c1, c2 = st.columns(2)
            with c1:
                s = st.date_input(f"{hol} Start", value=safe_date(start), key=f"global_start_{year}_{hol_idx}")
            with c2:
                e = st.date_input(f"{hol} End", value=safe_date(end), key=f"global_end_{year}_{hol_idx}")
            if s.isoformat() != start or e.isoformat() != end:
                data["global_dates"][year][hol] = [s.isoformat(), e.isoformat()]
                save_data()

st.success("All changes saved instantly!")
