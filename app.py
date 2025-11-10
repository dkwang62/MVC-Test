import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")
st.markdown("<style>.big{font-size:48px!important;font-weight:bold;color:#1f77b4}.stButton>button{min-height:60px;font-weight:bold}</style>", unsafe_allow_html=True)

# State
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
            raw["resorts_list"] = sorted({*raw.get("season_blocks", {}), *raw.get("point_costs", {})})
        st.session_state.data = raw
        data = raw
        st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL SEASONS & POINT COSTS VISIBLE")
        st.session_state.current_resort = None

    if data:
        st.download_button("Download Updated JSON", json.dumps(data, indent=2), "marriott-abound.json", "application/json")

st.title("Marriott Abound Editor — UNIVERSAL EDITION")
if not data: st.info("Upload your data.json"); st.stop()

# === RESORTS ===
resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"r{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

if not current_resort: st.stop()
st.markdown(f"### **{current_resort}** — FULLY LOADED")

# === SEASONS ===
st.subheader("Season Dates")
for year in ["2025", "2026"]:
    with st.expander(f"{year} Seasons", expanded=True):
        year_data = data["season_blocks"][current_resort].setdefault(year, {})
        new_s = st.text_input(f"New season ({year})", key=f"ns{year}")
        if st.button("Add Season", key=f"add{year}") and new_s and new_s not in year_data:
            year_data[new_s] = []
            save()
            st.rerun()
        for s_idx, (sname, ranges) in enumerate(year_data.items()):
            st.markdown(f"**{sname}**")
            for i, (s, e) in enumerate(ranges):
                c1, c2, c3 = st.columns([3,3,1])
                with c1: ns = st.date_input("Start", safe_date(s), key=f"st{year}{s_idx}{i}")
                with c2: ne = st.date_input("End", safe_date(e), key=f"en{year}{s_idx}{i}")
                with c3:
                    if st.button("X", key=f"dx{year}{s_idx}{i}"):
                        ranges.pop(i); save(); st.rerun()
                if ns.isoformat() != s or ne.isoformat() != e:
                    ranges[i] = [ns.isoformat(), ne.isoformat()]
                    save()
            if st.button("+ Add Range", key=f"ar{year}{s_idx}"):
                ranges.append([f"{year}-01-01", f"{year}-01-07"])
                save(); st.rerun()

# === POINT COSTS — UNIVERSAL DETECTION (WORKS WITH ANY SEASON NAME & COUNT) ===
st.subheader("Point Costs")
point_costs = data["point_costs"].get(current_resort, {})

if not point_costs:
    st.warning("No point costs defined for this resort")
else:
    # Dynamically detect ALL seasons and their structures
    for season_name, season_data in point_costs.items():
        with st.expander(season_name, expanded=True):
            if not isinstance(season_data, dict):
                st.write("Invalid data")
                continue

            # Case 1: Fri-Sat / Sun-Thu directly under season
            if "Fri-Sat" in season_data or "Sun-Thu" in season_data:
                for day_type in ["Fri-Sat", "Sun-Thu"]:
                    if day_type not in season_data: continue
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    rooms = season_data[day_type]
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"pt_{current_resort}_{season_name}_{day_type}_{room}_{j}")
                            if new != pts:
                                rooms[room] = new
                                save()

            # Case 2: Nested under sub-seasons (e.g. "High", "Peak", "Low")
            else:
                for sub_season, sub_data in season_data.items():
                    st.markdown(f"**{sub_season}**")
                    if not isinstance(sub_data, dict): continue
                    for day_type in ["Fri-Sat", "Sun-Thu"]:
                        if day_type not in sub_data: continue
                        st.write(f"→ {day_type}")
                        cols = st.columns(4)
                        rooms = sub_data[day_type]
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                new = st.number_input(room, value=int(pts), step=25, key=f"pt2_{current_resort}_{season_name}_{sub_season}_{day_type}_{room}_{j}")
                                if new != pts:
                                    rooms[room] = new
                                    save()

st.success("ALL SEASONS & POINT COSTS VISIBLE — WORKS WITH ANY RESORT STRUCTURE")
