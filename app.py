import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False

# === SIDEBAR ===
with st.sidebar:
    st.title("Marriott")
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')}")

    uploaded_file = st.file_uploader("Upload data.json", type="json")

    if uploaded_file and not st.session_state.uploaded:
        try:
            raw = json.load(uploaded_file)
            raw.setdefault("resorts_list", [])
            raw.setdefault("reference_points", {})
            raw.setdefault("season_blocks", {})
            raw.setdefault("global_holidays", {})
            raw.setdefault("maintenance_years", {})

            if not raw["resorts_list"]:
                keys = (set(raw.get("reference_points", {}).keys()) |
                        set(raw.get("season_blocks", {}).keys()))
                raw["resorts_list"] = sorted(keys)

            st.session_state.data = raw
            st.session_state.uploaded = True
            st.success(f"Loaded {len(raw['resorts_list'])} resorts")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.data:
        st.download_button(
            "Download Updated JSON",
            data=json.dumps(st.session_state.data, indent=2),
            file_name="data-updated.json",
            mime="application/json"
        )

# === MAIN APP ===
if not st.session_state.data:
    st.title("Marriott Abound Editor")
    st.info("Upload your data.json to begin")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Editor")

# === RESORT BUTTONS ===
cols = st.columns(6)
for i, resort in enumerate(resorts):
    if cols[i % 6].button(resort, key=f"resort_{i}"):
        st.session_state.current_resort = resort
        st.rerun()

if not st.session_state.current_resort:
    st.info("Select a resort above")
    st.stop()

current = st.session_state.current_resort
st.header(current)

# === REFERENCE POINTS ===
st.subheader("Reference Points")
points = data["reference_points"].get(current, {})

if not points:
    st.info("No point data available")
else:
    for season, content in points.items():
        with st.expander(season, expanded=True):
            day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat"]]
            if day_types:
                for dt in day_types:
                    rooms = content[dt]
                    st.write(f"**{dt}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"pt_{current}_{season}_{dt}_{room}_{j}")
                            if new != pts:
                                rooms[room] = new
            else:
                for sub_season, rooms in content.items():
                    st.markdown(f"**{sub_season}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"hpt_{current}_{season}_{sub_season}_{room}_{j}")
                            if new != pts:
                                rooms[room] = new

# === SEASON DATES ===
st.subheader("Season Dates")
seasons = data["season_blocks"].get(current, {})
for year in ["2025", "2026"]:
    with st.expander(f"{year} Seasons", expanded=True):
        year_data = seasons.get(year, {})
        for season_name, ranges in year_data.items():
            st.markdown(f"**{season_name}**")
            for i, (start, end) in enumerate(ranges):
                c1, c2, c3 = st.columns([3, 3, 1])
                with c1:
                    ns = st.date_input("Start", datetime.fromisoformat(start).date(), key=f"s_{year}_{season_name}_{i}")
                with c2:
                    ne = st.date_input("End", datetime.fromisoformat(end).date(), key=f"e_{year}_{season_name}_{i}")
                with c3:
                    if st.button("Delete", key=f"del_{year}_{season_name}_{i}"):
                        ranges.pop(i)
                        st.rerun()
                if ns.isoformat() != start or ne.isoformat() != end:
                    ranges[i] = [ns.isoformat(), ne.isoformat()]

# === GLOBAL HOLIDAYS ===
st.subheader("Global Holidays")
holidays = data.get("global_holidays", {})
for year in ["2025", "2026"]:
    with st.expander(f"{year} Holidays", expanded=True):
        year_hols = holidays.get(year, {})
        if not year_hols:
            st.write("No holidays defined")
        for hol_name, dates in year_hols.items():
            st.markdown(f"**{hol_name}**")
            for i, date_str in enumerate(dates):
                c1, c2 = st.columns([3, 1])
                with c1:
                    new_date = st.date_input("Date", datetime.fromisoformat(date_str).date(), key=f"gh_{year}_{hol_name}_{i}")
                with c2:
                    if st.button("Delete", key=f"ghdel_{year}_{hol_name}_{i}"):
                        dates.pop(i)
                        st.rerun()
                if new_date.isoformat() != date_str:
                    dates[i] = new_date.isoformat()

# === MAINTENANCE FEES — ALWAYS POPULATED ===
st.subheader("Maintenance Fee per Point (USD)")
maintenance = data.get("maintenance_years", {})

for year in ["2025", "2026", "2027", "2028"]:
    current_val = maintenance.get(year, 0.0)
    # Force float and show 4 decimals
    display_val = float(current_val) if current_val else 0.0
    new_val = st.number_input(
        f"{year} Fee per Point",
        value=display_val,
        step=0.0001,
        format="%.4f",
        key=f"mf_{year}"
    )
    if round(new_val, 4) != round(display_val, 4):
        maintenance[year] = round(new_val, 4)
