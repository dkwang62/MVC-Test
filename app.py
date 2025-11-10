import streamlit as st
import json

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
    .stButton>button { min-height: 40px; }
</style>
""", unsafe_allow_html=True)

# ---- Session State ----
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

# ---- Helper: Save & Download ----
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
        mime="application/json",
        use_container_width=True
    )

# ---- Sidebar: Load File ----
with st.sidebar:
    st.header("1. Load Data")
    uploaded_file = st.file_uploader("Upload your Marriott JSON file", type="json")
    if uploaded_file:
        try:
            st.session_state.data = json.load(uploaded_file)
            data = st.session_state.data
            st.success("Data loaded successfully!")
            st.session_state.current_resort = None  # Reset selection
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

    st.markdown("---")
    if data:
        download_json()

# ---- Main UI ----
st.title("Marriott Abound Season & Points Editor")
st.warning("Always backup your original file before editing!")

if not data:
    st.info("Please upload a JSON file in the sidebar to begin.")
    st.stop()

# ---- Resort Selection ----
st.header("2. Select Resort")

# Resort buttons
cols = st.columns(6)
for i, name in enumerate(data["resorts_list"]):
    col = cols[i % 6]
    active = (current_resort == name)
    if col.button(
        name,
        key=f"resort_{name}",
        use_container_width=True,
        type="primary" if active else "secondary"
    ):
        st.session_state.current_resort = name
        st.rerun()

# Add new resort
with st.expander("➕ Add New Resort", expanded=False):
    new_name = st.text_input("New resort name")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create Blank Resort", use_container_width=True):
            if not new_name or new_name in data["resorts_list"]:
                st.error("Invalid or duplicate name")
            else:
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = {"2025": {}, "2026": {}}
                data["point_costs"][new_name] = {}
                st.session_state.current_resort = new_name
                save_data()
                st.success(f"Created: {new_name}")
                st.rerun()
    with col2:
        if st.button("Create from Template", use_container_width=True) and current_resort:
            template_name = st.text_input("New name (copy of current)", value=f"{current_resort} Copy")
            if st.button("Copy & Create"):
                if template_name in data["resorts_list"]:
                    st.error("Name exists")
                else:
                    data["resorts_list"].append(template_name)
                    data["season_blocks"][template_name] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                    data["point_costs"][template_name] = json.loads(json.dumps(data["point_costs"][current_resort]))
                    st.session_state.current_resort = template_name
                    save_data()
                    st.success(f"Copied to: {template_name}")
                    st.rerun()

if current_resort:
    st.markdown(f"### Editing: **{current_resort}**")
    
    # Delete resort
    if st.button("🗑️ Delete This Resort", type="secondary"):
        if st.checkbox("I understand this cannot be undone", key="confirm_del"):
            if st.button("PERMANENTLY DELETE", type="primary"):
                del data["season_blocks"][current_resort]
                del data["point_costs"][current_resort]
                data["resorts_list"].remove(current_resort)
                st.session_state.current_resort = None
                save_data()
                st.success("Resort deleted")
                st.rerun()

    # ---- Season Blocks ----
    st.subheader("Season Date Ranges (2025 & 2026)")
    for year in ["2025", "2026"]:
        with st.expander(f"📅 {year} Seasons", expanded=True):
            year_data = data["season_blocks"].setdefault(current_resort, {}).setdefault(year, {})
            seasons = list(year_data.keys())

            # Add new season
            new_season = st.text_input(f"Add new season for {year}", key=f"new_season_{year}")
            if st.button(f"Add Season: {new_season or '...'}", disabled=not new_season):
                if new_season in year_data:
                    st.error("Season exists")
                else:
                    year_data[new_season] = []
                    save_data()
                    st.rerun()

            for season in seasons:
                with st.container():
                    st.markdown(f"**{season}**")
                    ranges = year_data[season]
                    for idx, (start, end) in enumerate(ranges):
                        c1, c2, c3 = st.columns([3, 3, 1])
                        with c1:
                            new_start = st.date_input("Start", value=st.date.fromisoformat(start), key=f"s_{year}_{season}_{idx}_start")
                        with c2:
                            new_end = st.date_input("End", value=st.date.fromisoformat(end), key=f"s_{year}_{season}_{idx}_end")
                        with c3:
                            if st.button("Remove", key=f"del_{year}_{season}_{idx}"):
                                ranges.pop(idx)
                                save_data()
                                st.rerun()
                        if new_start.isoformat() != start or new_end.isoformat() != end:
                            ranges[idx] = [new_start.isoformat(), new_end.isoformat()]
                            save_data()

                    if st.button(f"+ Add Date Range to {season}", key=f"add_range_{year}_{season}"):
                        ranges.append([f"{year}-01-01", f"{year}-01-07"])
                        save_data()
                        st.rerun()

    # ---- Point Costs ----
    st.subheader("Point Costs by Season")
    points = data["point_costs"].setdefault(current_resort, {})
    for season in list(points.keys()):
        with st.expander(f"💰 {season}", expanded=True):
            season_data = points[season]
            if "Fri-Sat" in season_data or "Sun-Thu" in season_data:
                for day_type in ["Fri-Sat", "Sun-Thu"]:
                    if day_type not in season_data: continue
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for i, room in enumerate(season_data[day_type]):
                        with cols[i % 4]:
                            old_val = season_data[day_type][room]
                            new_val = st.number_input(room, value=old_val, step=50, key=f"pt_{season}_{day_type}_{room}")
                            if new_val != old_val:
                                season_data[day_type][room] = int(new_val)
                                save_data()
            else:
                st.write("**Holiday Weeks**")
                holiday_data = season_data.get("Holiday Week", {})
                for holiday in holiday_data:
                    st.markdown(f"**{holiday}**")
                    cols = st.columns(4)
                    for i, room in enumerate(holiday_data[holiday]):
                        with cols[i % 4]:
                            old_val = holiday_data[holiday][room]
                            new_val = st.number_input(room, value=old_val, step=50, key=f"h_{season}_{holiday}_{room}")
                            if new_val != old_val:
                                holiday_data[holiday][room] = int(new_val)
                                save_data()

# ---- Global Settings ----
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for year in data["maintenance_rates"]:
        rate = data["maintenance_rates"][year]
        new_rate = st.number_input(f"{year} Rate", value=float(rate), step=0.01, format="%.4f", key=f"mf_{year}")
        if new_rate != rate:
            data["maintenance_rates"][year] = new_rate
            save_data()

with st.expander("Global Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        for holiday in holidays:
            start, end = holidays[holiday]
            c1, c2 = st.columns(2)
            with c1:
                s = st.date_input(f"{holiday} Start", value=st.date.fromisoformat(start), key=f"ghs_{year}_{holiday}")
            with c2:
                e = st.date_input(f"{holiday} End", value=st.date.fromisoformat(end), key=f"ghe_{year}_{holiday}")
            if s.isoformat() != start or e.isoformat() != end:
                data["global_dates"][year][holiday] = [s.isoformat(), e.isoformat()]
                save_data()

st.success("All changes saved automatically!")
