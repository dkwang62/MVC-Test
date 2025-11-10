import streamlit as st
import json
from streamlit_elements import mui, html, mwc
import streamlit.components.v1 as components

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

# ---- Custom CSS ----
st.markdown("""
<style>
    .css-1d391kg { padding-top: 2rem; }
    .section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }
    .resort-btn { display: inline-block; padding: 10px 15px; margin: 5px; background: #e3e8f0; 
                   border: 1px solid #ccc; border-radius: 5px; cursor: pointer; }
    .resort-btn.active { background: #1a3c6e; color: white; }
    .date-range { margin: 8px 0; padding: 8px; background: white; border: 1px solid #ccc; border-radius: 4px; }
    .add-btn { background: #28a745; color: white; }
    .remove-btn { background: #dc3545; color: white; font-size: 12px; padding: 5px 8px; }
    .warning { color: #d00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ---- Session State Initialization ----
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

# ---- Helper Functions ----
def save_data():
    st.session_state.data = data

def download_json():
    if not data:
        st.error("No data loaded!")
        return
    json_str = json.dumps(data, indent=2)
    st.download_button(
        label="Download Updated JSON",
        data=json_str,
        file_name="data-updated.json",
        mime="application/json"
    )

# ---- Sidebar: Load File ----
with st.sidebar:
    st.header("1. Load Data")
    uploaded_file = st.file_uploader("Upload JSON", type="json")
    if uploaded_file:
        try:
            st.session_state.data = json.load(uploaded_file)
            data = st.session_state.data
            st.success("Data loaded successfully!")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

    if data:
        download_json()

# ---- Main Content ----
st.title("Marriott Abound Season & Points Editor")
st.warning("Always backup your original file!")

if not data:
    st.info("Please upload a JSON file to begin.")
    st.stop()

# ---- Resort Selection ----
st.header("2. Select Resort")
col1, col2 = st.columns([4, 1])
with col1:
    resort_cols = st.columns(5)
    for i, name in enumerate(data["resorts_list"]):
        col = resort_cols[i % 5]
        active = (current_resort == name)
        if col.button(name, key=f"resort_{name}", 
                      help="Click to edit",
                      type="primary" if active else "secondary"):
            st.session_state.current_resort = name
            st.rerun()
with col2:
    if st.button("+ Add New Resort"):
        new_name = st.text_input("New resort name:", key="new_resort_input")
        if st.button("Create", key="create_resort"):
            if not new_name or new_name in data["resorts_list"]:
                st.error("Invalid or duplicate name")
            else:
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = {"2025": {}, "2026": {}}
                data["point_costs"][new_name] = {}
                st.session_state.current_resort = new_name
                save_data()
                st.success(f"Resort '{new_name}' created!")
                st.rerun()

if current_resort:
    st.markdown(f"### Editing: **{current_resort}**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Copy as Template for New Resort"):
            copy_name = st.text_input("New resort name (copy):", key="copy_name")
            if st.button("Copy", key="do_copy"):
                if copy_name in data["resorts_list"]:
                    st.error("Name already exists")
                else:
                    data["resorts_list"].append(copy_name)
                    data["season_blocks"][copy_name] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                    data["point_costs"][copy_name] = json.loads(json.dumps(data["point_costs"][current_resort]))
                    st.session_state.current_resort = copy_name
                    save_data()
                    st.success(f"Copied to '{copy_name}'")
                    st.rerun()
    with col2:
        if st.button("Delete This Resort", type="secondary"):
            if st.checkbox("Confirm permanent deletion", key="confirm_delete"):
                if st.button("YES, DELETE FOREVER", type="primary"):
                    del data["season_blocks"][current_resort]
                    del data["point_costs"][current_resort]
                    data["resorts_list"].remove(current_resort)
                    st.session_state.current_resort = None
                    save_data()
                    st.success("Resort deleted")
                    st.rerun()

    # ---- Season Blocks Editor ----
    st.subheader("Season Blocks (2025 & 2026)")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"].setdefault(current_resort, {}).setdefault(year, {})
            seasons = list(year_data.keys())
            season_cols = st.columns(4)
            for i, season in enumerate(seasons + [""]):
                col = season_cols[i % 4] if i < len(seasons) else season_cols[0]
                with col:
                    if season:
                        st.write(f"**{season}**")
                    else:
                        new_season = st.text_input("New season name", key=f"new_season_{year}")
                        if st.button("Add Season", key=f"add_season_{year}"):
                            if new_season:
                                year_data[new_season] = []
                                save_data()
                                st.rerun()

            for season in seasons:
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                for idx, (start, end) in enumerate(ranges):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        new_start = st.date_input("Start", value=st.date.fromisoformat(start), key=f"start_{year}_{season}_{idx}")
                    with col2:
                        new_end = st.date_input("End", value=st.date.fromisoformat(end), key=f"end_{year}_{season}_{idx}")
                    with col3:
                        if st.button("X", key=f"del_range_{year}_{season}_{idx}"):
                            ranges.pop(idx)
                            save_data()
                            st.rerun()
                    if new_start.isoformat() != start or new_end.isoformat() != end:
                        ranges[idx] = [new_start.isoformat(), new_end.isoformat()]
                        save_data()
                if st.button(f"+ Add Date Range to {season} ({year})", key=f"add_range_{year}_{season}"):
                    ranges.append(["2025-01-01", "2025-01-07"])
                    save_data()
                    st.rerun()

    # ---- Point Costs Editor ----
    st.subheader("Point Costs")
    points = data["point_costs"].setdefault(current_resort, {})
    for season in points.keys():
        with st.expander(season, expanded=True):
            season_data = points[season]
            if "Fri-Sat" in season_data or "Sun-Thu" in season_data:
                for day_type in ["Fri-Sat", "Sun-Thu"]:
                    if day_type not in season_data:
                        continue
                    st.write(f"**{day_type}**")
                    room_cols = st.columns(4)
                    for i, room in enumerate(season_data[day_type]):
                        with room_cols[i % 4]:
                            val = season_data[day_type][room]
                            new_val = st.number_input(room, value=val, step=1, key=f"pts_{season}_{day_type}_{room}")
                            if new_val != val:
                                season_data[day_type][room] = int(new_val)
                                save_data()
            else:
                # Holiday Week format
                st.write("**Holiday Week**")
                for holiday in season_data.get("Holiday Week", {}):
                    st.markdown(f"**{holiday} (Full Week)**")
                    holiday_data = season_data["Holiday Week"][holiday]
                    room_cols = st.columns(4)
                    for i, room in enumerate(holiday_data):
                        with room_cols[i % 4]:
                            val = holiday_data[room]
                            new_val = st.number_input(room, value=val, step=1, key=f"holiday_{season}_{holiday}_{room}")
                            if new_val != val:
                                holiday_data[room] = int(new_val)
                                save_data()

    # ---- Global Settings ----
    st.header("Global Settings")
    with st.expander("Maintenance Rates"):
        for year in data["maintenance_rates"]:
            rate = data["maintenance_rates"][year]
            new_rate = st.number_input(f"{year} Rate", value=float(rate), step=0.01, key=f"mr_{year}")
            if new_rate != rate:
                data["maintenance_rates"][year] = new_rate
                save_data()

    with st.expander("Global Holiday Dates"):
        for year in ["2025", "2026"]:
            st.write(f"**{year}**")
            holidays = data["global_dates"].get(year, {})
            for holiday in holidays:
                start, end = holidays[holiday]
                col1, col2 = st.columns(2)
                with col1:
                    new_start = st.date_input(holiday + " Start", value=st.date.fromisoformat(start), key=f"gh_start_{year}_{holiday}")
                with col2:
                    new_end = st.date_input(holiday + " End", value=st.date.fromisoformat(end), key=f"gh_end_{year}_{holiday}")
                if new_start.isoformat() != start or new_end.isoformat() != end:
                    data["global_dates"][year][holiday] = [new_start.isoformat(), new_end.isoformat()]
                    save_data()

else:
    st.info("Select a resort to start editing.")
