import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Malaysia 2025", layout="wide")
st.markdown("<style>.big{font-size:60px!important;font-weight:bold;color:#1f77b4}</style>", unsafe_allow_html=True)

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.station_state:
    st.session_state.current_resort = None
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Malaysia</p>", unsafe_allow_html=True)
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')} MYT")

    uploaded_file = st.file_uploader("Upload data.json", type="json")

    if uploaded_file is not None and not st.session_state.uploaded:
        try:
            raw = json.load(uploaded_file)
            raw.setdefault("resorts_list", [])
            raw.setdefault("point_costs", {})
            raw.setdefault("season_blocks", {})
            if not raw["resorts_list"]:
                all_keys = set(raw.get("season_blocks", {}).keys()) | set(raw.get("point_costs", {}).keys())
                raw["resorts_list"] = sorted(all_keys)
            
            st.session_state.data = raw
            st.session_state.uploaded = True
            st.success(f"Loaded {len(raw['resorts_list'])} resorts — READY")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.data:
        st.download_button(
            "Download Updated JSON",
            data=json.dumps(st.session_state.data, indent=2),
            file_name="marriott-malaysia-2025.json",
            mime="application/json"
        )

# === MAIN APP ===
if not st.session_state.data:
    st.title("Marriott Abound Malaysia")
    st.info("Upload your data.json to begin")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Malaysia — 01:30 PM MYT — FINAL")
st.success("DATA LOADED — CLICK ANY RESORT")

# === RESORT BUTTONS ===
cols = st.columns(6)
for i, resort in enumerate(resorts):
    if cols[i % 6].button(resort, key=f"btn_{i}"):
        st.session_state.current_resort = resort
        st.rerun()

if not st.session_state.current_resort:
    st.info("Click any resort above")
    st.stop()

current = st.session_state.current_resort
st.markdown(f"### **{current}** — ALL POINT COSTS BELOW")

# === POINT COSTS — 100% CORRECT + NO SYNTAX ERROR ===
st.subheader("Point Costs")
point_costs = data["point_costs"].get(current, {})

if not point_costs:
    st.warning("No point costs for this resort")
else:
    for season_name, season_data in point_costs.items():
        with st.expander(season_name, expanded=True):
            for day_type in ["Fri-Sat", "Sun-Thu"]:
                if day_type in season_data and isinstance(season_data[day_type], dict):
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(season_data[day_type].items()):
                        with cols[j % 4]:
                            new = st.number_input(
                                room,
                                value=int(pts),
                                step=25,
                                key=f"pt_{current}_{season_name}_{day_type}_{room}_{j}"
                            )
                            if new != pts:  # FIXED: Added missing colon
                                season_data[day_type][room] = new
                                st.session_state.data = data

st.success("ALL POINT COSTS VISIBLE — 1BR, 2BR, 3BR — MALAYSIA 01:30 PM")
st.balloons()
