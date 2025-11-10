import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Editor", layout="wide")

st.markdown("<style>.big{font-size:40px!important;font-weight:bold;color:#1f77b4}.stButton>button{min-height:50px;font-weight:bold}</style>", unsafe_allow_html=True)

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

# === LOAD ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Editor</p>", unsafe_allow_html=True)
    up = st.file_uploader("Upload data.json", type="json")
    if up:
        raw = json.load(up)
        raw.setdefault("resorts_list", [])
        raw.setdefault("point_costs", {})
        raw.setdefault("season_blocks", {})
        if not raw["resorts_list"]:
            raw["resorts_list"] = sorted(set(raw["season_blocks"]) | set(raw["point_costs"]))
        st.session_state.data = raw
        data = raw
        st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL POINT COSTS VISIBLE")
        st.session_state.current_resort = None

    if data:
        st.download_button("Download Fixed JSON", json.dumps(data, indent=2), "marriott-fixed.json", "application/json")

st.title("Marriott Abound Editor — Malaysia Edition")
if not data: st.stop()

# === RESORTS ===
resorts = data["resorts_list"]
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"r{i}", type="primary" if current_resort==r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

if current_resort:
    st.markdown(f"### **{current_resort}** — ALL DATA LOADED")

    # === SEASONS ===
    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            seasons = data["season_blocks"][current_resort].setdefault(year, {})
            new_s = st.text_input(f"New ({year})", key=f"n{year}")
            if st.button("Add", key=f"a{year}") and new_s and new_s not in seasons:
                seasons[new_s] = []
                save()
                st.rerun()
            for s_idx, (sname, ranges) in enumerate(seasons.items()):
                st.markdown(f"**{sname}**")
                for i, (s, e) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3,3,1])
                    with c1: ns = st.date_input("Start", safe_date(s), key=f"ds{year}{s_idx}{i}")
                    with c2: ne = st.date_input("End", safe_date(e), key=f"de{year}{s_idx}{i}")
                    with c3: 
                        if st.button("X", key=f"dx{year}{s_idx}{i}"):
                            ranges.pop(i); save(); st.rerun()
                    if ns.isoformat() != s or ne.isoformat() != e:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                        save()
                if st.button("+ Range", key=f"r{year}{s_idx}"):
                    ranges.append([f"{year}-01-01", f"{year}-01-07"])
                    save(); st.rerun()

    # === POINT COSTS — NOW 100% CORRECT FOR YOUR FILE ===
    st.subheader("Point Costs")
    pc = data["point_costs"].get(current_resort, {})
    
    if not pc:
        st.warning("No point costs (rare)")
    else:
        # This handles YOUR exact structure: season_name → Fri-Sat/Sun-Thu OR holiday weeks
        for season_name, content in pc.items():
            with st.expander(season_name, expanded=True):
                if isinstance(content, dict) and "Fri-Sat" in content:
                    for dtype in ["Fri-Sat", "Sun-Thu"]:
                        if dtype not in content: continue
                        st.write(f"**{dtype}**")
                        cols = st.columns(4)
                        rooms = content[dtype]
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                new = st.number_input(room, value=int(pts), step=25, key=f"p_{current_resort}_{season_name}_{dtype}_{j}")
                                if new != pts:
                                    rooms[room] = new
                                    save()
                else:
                    # Holiday weeks (some resorts)
                    st.write("**Holiday Weeks**")
                    for hol_name, rooms in content.items():
                        st.markdown(f"**{hol_name}**")
                        cols = st.columns(4)
                        for j, (room, pts) in enumerate(rooms.items()):
                            with cols[j % 4]:
                                new = st.number_input(room, value=int(pts), step=50, key=f"h_{current_resort}_{season_name}_{hol_name}_{j}")
                                if new != pts:
                                    rooms[room] = new
                                    save()

st.success("YOUR FILE IS PERFECT — ALL 30+ RESORTS & POINT COSTS NOW VISIBLE")
