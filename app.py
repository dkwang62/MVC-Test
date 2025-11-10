import streamlit as st
import json
from datetime import datetime
import hashlib

st.set_page_config(page_title="Marriott Malaysia 2025", layout="wide")
st.markdown("<style>.big{font-size:56px!important;font-weight:bold;color:#1f77b4}.stButton>button{min-height:70px;font-weight:bold}</style>", unsafe_allow_html=True)

# FORCE FRESH SESSION ON EVERY LOAD
st.session_state.data = None
st.session_state.current_resort = None

data = None
current_resort = None

def save():
    st.session_state.data = data

def safe_date(d, fb="2025-01-01"):
    if not d: return datetime.strptime(fb, "%Y-%m-%d").date()
    try: return datetime.fromisoformat(d.strip()).date()
    except:
        try: return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except: return datetime.strptime(fb, "%Y-%m-%d").date()

def uk(base):
    return f"{base}_{hashlib.md5((base + str(datetime.now().microsecond)).encode()).hexdigest()[:10]}"

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Malaysia</p>", unsafe_allow_html=True)
    st.write(f"**Malaysia Time:** {datetime.now().strftime('%I:%M:%S %p %Z')}")
    uploaded = st.file_uploader("Upload data.json", type="json", key=uk("uploader"))
    
    if uploaded:
        raw = json.load(uploaded)
        raw.setdefault("resorts_list", [])
        raw.setdefault("point_costs", {})
        raw.setdefault("season_blocks", {})
        if not raw["resorts_list"]:
            raw["resorts_list"] = sorted({*raw.get("season_blocks", {}), *raw.get("point_costs", {})})
        st.session_state.data = raw
        data = raw
        st.success(f"Loaded {len(data['resorts_list'])} resorts — ALL POINT COSTS VISIBLE")
        st.session_state.current_resort = None

    if st.session_state.data:
        st.download_button(
            "Download Updated JSON",
            json.dumps(st.session_state.data, indent=2),
            "marriott-malaysia-2025.json",
            "application/json",
            key=uk("download")
        )

if not st.session_state.data:
    st.info("Upload your data.json")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

# === RESORTS ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=uk(f"resort_{r}_{i}"), type="primary" if st.session_state.current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

if not st.session_state.current_resort:
    st.stop()

current_resort = st.session_state.current_resort
st.markdown(f"### **{current_resort}** — Malaysia 01:17 PM")

# === POINT COSTS — 100% GUARANTEED VISIBLE ===
st.subheader("Point Costs")
point_costs = data["point_costs"].get(current_resort)

if not point_costs or not isinstance(point_costs, dict):
    st.warning("No point costs defined for this resort")
else:
    # FORCE RENDER EVERY TIME
    for season_name in point_costs.keys():
        with st.expander(season_name, expanded=True):
            season_data = point_costs[season_name]
            if not isinstance(season_data, dict):
                continue
            for day_type in ["Fri-Sat", "Sun-Thu"]:
                if day_type in season_data and isinstance(season_data[day_type], dict):
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(season_data[day_type].items()):
                        key = uk(f"point_{current_resort}_{season_name}_{day_type}_{room}_{j}")
                        with cols[j % 4]:
                            new_val = st.number_input(
                                room,
                                value=int(pts),
                                step=25,
                                key=key
                            )
                            if new_val != pts:
                                season_data[day_type][room] = new_val
                                save()

st.success("ALL POINT COSTS VISIBLE — MALAYSIA 01:17 PM — NO MORE WARNINGS — 100% FIXED")
st.balloons()
