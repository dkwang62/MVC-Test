import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .resort-btn.active { background: #1f77b4 !important; color: white !important; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .warning { color: #d00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None
if 'clone_mode' not in st.session_state:
    st.session_state.clone_mode = False

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

# === FIX JSON ===
def fix_json(raw_data):
    defaults = {
        "resorts_list": [],
        "season_blocks": {},
        "point_costs": {},
        "reference_points": {},
        "maintenance_rates": {"2025": 0.81, "2026": 0.86},
        "global_dates": {"2025": {}, "2026": {}}
    }
    for key, value in defaults.items():
        if key not in raw_data:
            raw_data[key] = value
    if not raw_data["resorts_list"] and raw_data["season_blocks"]:
        raw_data["resorts_list"] = sorted(raw_data["season_blocks"].keys())
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
            st.session_state.clone_mode = False
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

# === RESORT GRID ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"resort_{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

# === CLONE & EDIT – NOW ASKS FOR SOURCE + NAME ===
if st.button("Clone & Edit", type="primary"):
    st.session_state.clone_mode = True
    st.rerun()

if st.session_state.clone_mode:
    st.markdown("### Clone Resort")
    source = st.selectbox("Select resort to clone", options=resorts)
    new_name = st.text_input("New resort name", placeholder="Pulse San Francisco")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Proceed", type="primary"):
            if not new_name.strip():
                st.error("Enter a name")
            elif new_name in resorts:
                st.error("Already exists")
            else:
                # DEEP CLONE – THIS WORKS
                data["resorts_list"].append(new_name)
                data["season_blocks"][new_name] = json.loads(json.dumps(data["season_blocks"].get(source, {"2025": {}, "2026": {}})))
                data["point_costs"][new_name] = json.loads(json.dumps(data["point_costs"].get(source, {})))
                data["reference_points"][new_name] = json.loads(json.dumps(data["reference_points"].get(source, {})))
                
                save_data()
                st.session_state.current_resort = new_name
                st.session_state.clone_mode = False
                st.success(f"CLONED: {source} → **{new_name}**")
                st.rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.clone_mode = False
            st.rerun()

# === CREATE BLANK ===
with st.expander("Add New Resort"):
    blank = st.text_input("Blank resort name")
    if st.button("Create Blank") and blank and blank not in resorts:
        data["resorts_list"].append(blank)
        data["season_blocks"][blank] = {"2025": {}, "2026": {}}
        data["point_costs"][blank] = {}
        data["reference_points"][blank] = {}
        save_data()
        st.session_state.current_resort = blank
        st.success(f"Created: {blank}")
        st.rerun()

# === EDIT CURRENT RESORT ===
if current_resort:
    st.markdown(f"### **{current_resort}**")
    
    if st.button("Delete Resort", type="secondary"):
        if st.checkbox("I understand – cannot be undone"):
            if st.button("DELETE FOREVER", type="primary"):
                for k in ["season_blocks", "point_costs", "reference_points"]:
                    data[k].pop(current_resort, None)
                if current_resort in data["resorts_list"]:
                    data["resorts_list"].remove(current_resort)
                save_data()
                st.session_state.current_resort = None
                st.rerun()

    # === SEASONS ===
    st.subheader("Season Dates")
    data["season_blocks"].setdefault(current_resort, {"2025": {}, "2026": {}})
    save_data()

    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"][current_resort][year]
            seasons = list(year_data.keys())

            c1, c2 = st.columns([4, 1])
            with c1:
                new_s = st.text_input(f"New season ({year})", key=f"new_season_{year}")
            with c2:
                if st.button("Add", key=f"add_season_{year}") and new_s and new_s not in year_data:
                    year_data[new_s] = []
                    save_data()
                    st.rerun()

            for idx, season in enumerate(seasons):
                st.markdown(f"**{season}**")
                ranges = year_data[season]
                for i, (s, e) in enumerate(ranges):
                    ca, cb, cc = st.columns([3, 3, 1])
                    with ca:
                        ns = st.date_input("Start", safe_date(s), key=f"start_{year}_{idx}_{i}")
                    with cb:
                        ne = st.date_input("End", safe_date(e), key=f"end_{year}_{idx}_{i}")
                    with cc:
                        if st.button("X", key=f"del_{year}_{idx}_{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if ns.isoformat() != s or ne.isoformat() != e:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                        save_data()

                if st.button("+ Add Range", key=f"range_{year}_{idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save_data()
                    st.rerun()

    # === POINT COSTS ===
    st.subheader("Point Costs")
    point_data = data["point_costs"].setdefault(current_resort, {})

    for season, content in point_data.items():
        with st.expander(season, expanded=True):
            if isinstance(content, dict) and any(isinstance(v, dict) for v in content.values()):
                for hol, rooms in content.items():
                    st.markdown(f"**{hol}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=50, key=f"h_{season}_{hol}_{j}")
                            if new != pts:
                                rooms[room] = new
                                save_data()
            else:
                day_types = ["Fri-Sat", "Sun", "Mon-Thu", "Sun-Thu"]
                available = [d for d in day_types if d in content]
                for dt in available:
                    rooms = content[dt]
                    st.write(f"**{dt}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            step = 50 if "Holiday" in season else 25
                            new = st.number_input(room, value=int(pts), step=step, key=f"p_{season}_{dt}_{j}")
                            if new != pts:
                                rooms[room] = new
                                save_data()

    # === REFERENCE POINTS ===
    st.subheader("Reference Points")
    ref = data["reference_points"].setdefault(current_resort, {})
    for season, content in ref.items():
        with st.expander(season, expanded=True):
            day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat", "Sun"]]
            if day_types:
                for dt in day_types:
                    rooms = content[dt]
                    st.write(f"**{dt}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"r_{season}_{dt}_{j}")
                            if new != pts:
                                rooms[room] = new
                                save_data()

# === GLOBALS ===
st.header("Global Settings")
with st.expander("Maintenance Fees"):
    for i, year in enumerate(sorted(data.get("maintenance_rates", {}).keys())):
        rate = data["maintenance_rates"][year]
        new = st.number_input(year, value=float(rate), step=0.01, format="%.4f", key=f"mf_{i}")
        if new != rate:
            data["maintenance_rates"][year] = new
            save_data()

with st.expander("Holiday Dates"):
    for year in ["2025", "2026"]:
        st.write(f"**{year}**")
        holidays = data["global_dates"].setdefault(year, {})
        for i, name in enumerate(list(holidays.keys())):
            s, e = holidays[name]
            c1, c2 = st.columns(2)
            with c1:
                ns = st.date_input(f"{name} Start", safe_date(s), key=f"hs_{year}_{i}")
            with c2:
                ne = st.date_input(f"{name} End", safe_date(e), key=f"he_{year}_{i}")
            if ns.isoformat() != s or ne.isoformat() != e:
                data["global_dates"][year][name] = [ns.isoformat(), ne.isoformat()]
                save_data()
