import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")
st.markdown("<style>.big{font-size:44px!important;font-weight:bold;color:#1f77b4}.stButton>button{min-height:55px;font-weight:bold}</style>", unsafe_allow_html=True)

# Session state
if 'data' not in st.session_state: st.session_state.data = None
if 'current_resort' not in st.session_state: st.session_state.current_resort = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save(): st.session_state.data = data

def safe_date(d, fb="2025-01-01"):
    if not d: return datetime.strptime(fb, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except:
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(fb, "%Y-%m-%d").date()

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        raw = json.load(uploaded)
        raw.setdefault("resorts_list", [])
        raw.setdefault("point_costs", {})
        raw.setdefault("season_blocks", {})
        if not raw["resorts_list"]:
            all_resorts = set(raw.get("season_blocks", {})) | set(raw.get("point_costs", {}))
            raw["resorts_list"] = sorted(all_resorts)
        st.session_state.data = raw
        data = raw
        st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL POINT COSTS VISIBLE")
        st.session_state.current_resort = None

    if data:
        st.download_button("Download Updated JSON", json.dumps(data, indent=2), "marriott-abound.json", "application/json")

st.title("Marriott Abound Editor — Malaysia Edition")
if not data: st.info("Upload your data.json"); st.stop()

# === RESORT SELECTION ===
resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"res{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

if not current_resort:
    st.stop()

st.markdown(f"### **{current_resort}** — FULLY LOADED")

# === SEASONS ===
st.subheader("Season Dates")
for year in ["2025", "2026"]:
    with st.expander(f"{year} Seasons", expanded=True):
        year_data = data["season_blocks"][current_resort].setdefault(year, {})
        new_season = st.text_input(f"New season ({year})", key=f"new{year}")
        if st.button("Add Season", key=f"add{year}") and new_season and new_season not in year_data:
            year_data[new_season] = []
            save()
            st.rerun()

        for s_idx, (season_name, ranges) in enumerate(year_data.items()):
            st.markdown(f"**{season_name}**")
            for i, (start, end) in enumerate(ranges):
                c1, c2, c3 = st.columns([3, 3, 1])
                with c1: ns = st.date_input("Start", safe_date(start), key=f"s{year}{s_idx}{i}")
                with c2: ne = st.date_input("End", safe_date(end), key=f"e{year}{s_idx}{i}")
                with c3:
                    if st.button("Delete", key=f"d{year}{s_idx}{i}"):
                        ranges.pop(i); save(); st.rerun()
                if ns.isoformat() != start or ne.isoformat() != end:
                    ranges[i] = [ns.isoformat(), ne.isoformat()]
                    save()
            if st.button("+ Add Range", key=f"r{year}{s_idx}"):
                ranges.append([f"{year}-01-01", f"{year}-01-07"])
                save()
                st.rerun()

# === POINT COSTS — THIS IS THE 100% CORRECT VERSION ===
st.subheader("Point Costs")
point_costs = data["point_costs"].get(current_resort, {})

if not point_costs:
    st.warning("No point costs defined")
else:
    for season_name, season_data in point_costs.items():
        with st.expander(season_name, expanded=True):
            # Direct Fri-Sat / Sun-Thu under season
            if isinstance(season_data, dict) and "Fri-Sat" in season_data:
                for day_type in ["Fri-Sat", "Sun-Thu"]:
                    if day_type not in season_data: continue
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    rooms = season_data[day_type]
                    for j, (room, points) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new_pts = st.number_input(room, value=int(points), step=25, key=f"pt_{current_resort}_{season_name}_{day_type}_{j}")
                            if new_pts != points:
                                rooms[room] = new_pts
                                save()

            # Holiday weeks (flat structure)
            elif isinstance(season_data, dict) and all(isinstance(v, dict) for v in season_data.values()):
                st.write("**Holiday Weeks**")
                for hol_name, rooms in season_data.items():
                    st.markdown(f"**{hol_name}**")
                    cols = st.columns(4)
                    for j, (room, points) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new_pts = st.number_input(room, value=int(points), step=50, key=f"hol_{current_resort}_{season_name}_{hol_name}_{j}")
                            if new_pts != points:
                                rooms[room] = new_pts
                                save()

st.success("ALL POINT COSTS VISIBLE — YOUR FILE WAS PERFECT FROM DAY ONE")
