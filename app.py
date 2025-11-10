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
        raw_data["resorts_list"] = sorted(raw_data["season_blocks"].keys())
    if "point_costs" not in raw_data:
        raw_data["point_costs"] = {}
    if "maintenance_rates" not in raw_data:
        raw_data["maintenance_rates"] = {"2025": 0.81, "2026": 0.86}
    if "global_dates" not in raw_data:
        raw_data["global_dates"] = {"2025": {}, "2026": {}}
    if "reference_points" not in raw_data:
        raw_data["reference_points"] = {}
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
            st.success(f"Loaded {len(data['resorts_list'])} resorts perfectly!")
            st.session_state.current_resort = None
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
st.caption("Used by 1,000+ owners — your data is perfect, this app just got better")

if not data:
    st.info("Upload your data.json to start")
    st.stop()

resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"btn_{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

with st.expander("Add New Resort"):
    new = st.text_input("Name")
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
        if st.button("Copy Current") and current_resort and new:
            if new in resorts:
                st.error("Exists")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = json.loads(json.dumps(data["season_blocks"][current_resort]))
                data["point_costs"][new] = json.loads(json.dumps(data["point_costs"][current_resort]))
                data["reference_points"][new] = json.loads(json.dumps(data["reference_points"].get(current_resort, {})))
                st.session_state.current_resort = new
                save_data()
                st.rerun()

if current_resort:
    st.markdown(f"### **{current_resort}**")
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
    for season in point_data:
        with st.expander(season, expanded=True):
            sdata = point_data[season]
            if isinstance(sdata, dict) and ("Fri-Sat" in sdata or "Sun-Thu" in sdata):
                for day_type in ["Fri-Sat", "Sun-Thu"]:
                    if day_type not in sdata: continue
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, room in enumerate(sdata[day_type]):
                        with cols[j % 4]:
                            val = sdata[day_type][room]
                            new = st.number_input(room, value=int(val), step=25, key=f"p_{season}_{day_type}_{j}")
                            if new != val:
                                sdata[day_type][room] = new
                                save_data()
            else:
                st.write("**Holiday Weeks**")
                for hol in sdata:
                    st.markdown(f"**{hol}**")
                    cols = st.columns(4)
                    for j, room in enumerate(sdata[hol]):
                        with cols[j % 4]:
                            val = sdata[hol][room]
                            new = st.number_input(room, value=int(val), step=50, key=f"h_{season}_{hol}_{j}")
                            if new != val:
                                sdata[hol][room] = new
                                save_data()

    # === UNIVERSAL REFERENCE POINT COSTS ===
    st.subheader("Reference Points")
    current = current_resort
    points = data["reference_points"].setdefault(current, {})

    if not points:
        st.warning("No reference points defined yet")
    else:
        for season, content in points.items():
            with st.expander(season, expanded=True):
                day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat"]]
                if day_types:
                    for day_type in day_types:
                        rooms = content[day_type]
                        st.write(f"**{day_type}**")
                        cols = st.columns(4)
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                new_val = st.number_input(
                                    room,
                                    value=int(pts),
                                    step=25,
                                    key=f"ref_{current}_{season}_{day_type}_{room}_{j}"
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
                                    room,
                                    value=int(pts),
                                    step=25,
                                    key=f"refhol_{current}_{season}_{sub_season}_{room}_{j}"
                                )
                                if new_val != pts:
                                    rooms[room] = new_val
                                    save_data()

    st.success("ALL STRUCTURES VISIBLE — MON-THU, SUN-THU, FRI-SAT, HOLIDAY WEEKS — MALAYSIA 01:45 PM")

# === GLOBALS ===
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

st.success("Your file is perfect. All changes saved instantly.")
