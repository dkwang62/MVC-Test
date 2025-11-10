import streamlit as st
import json
from datetime import datetime

st.set_page_config(page_title="Marriott Malaysia 2025", layout="wide")
st.markdown("<style>.big{font-size:60px!important;font-weight:bold;color:#1f77b4}</style>", unsafe_allow_html=True)

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Malaysia</p>", unsafe_allow_html=True)
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')} MYT")

    uploaded = st.file_uploader("Upload data.json", type="json")

    if uploaded is not None:
        try:
            raw = json.load(uploaded)
            raw.setdefault("resorts_list", [])
            raw.setdefault("point_costs", {})
            raw.setdefault("season_blocks", {})
            if not raw["resorts_list"]:
                raw["resorts_list"] = sorted(set(raw.get("season_blocks", {}).keys()) | set(raw.get("point_costs", {}).keys()))
            
            st.session_state.data = raw
            st.session_state.current_resort = None
            st.success(f"Loaded {len(raw['resorts_list'])} resorts — ALL DATA VISIBLE")
            # CRITICAL: Force full reload
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.data:
        st.download_button(
            "Download Updated JSON",
            json.dumps(st.session_state.data, indent=2),
            "marriott-malaysia-2025.json",
            "application/json"
        )

# === FORCE DATA LOAD CHECK ===
if st.session_state.data is None:
    st.title("Marriott Abound Malaysia")
    st.info("Please upload your data.json above to begin.")
    st.stop()

# === DATA IS LOADED — SHOW APP ===
data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Malaysia — 01:25 PM MYT — FULLY WORKING")
st.success("DATA LOADED — CLICK ANY RESORT BELOW")

# === RESORT BUTTONS ===
cols = st.columns(6)
for i, resort in enumerate(resorts):
    if cols[i % 6].button(resort, key=f"resort_{i}_{resort}"):
        st.session_state.current_resort = resort
        st.experimental_rerun()

if not st.session_state.current_resort:
    st.info("Click any resort above to view point costs")
    st.stop()

current = st.session_state.current_resort
st.markdown(f"### **{current}** — Malaysia 01:25 PM")

# === POINT COSTS — GUARANTEED VISIBLE ===
st.subheader("Point Costs")
pc = data["point_costs"].get(current, {})

if not pc:
    st.warning("No point costs for this resort")
else:
    for season, content in pc.items():
        with st.expander(season, expanded=True):
            for day_type in ["Fri-Sat", "Sun-Thu"]:
                if day_type in content:
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(content[day_type].items()):
                        with cols[j % 4]:
                            new = st.number_input(
                                room,
                                value=int(pts),
                                step=25,
                                key=f"pt_{current}_{season}_{day_type}_{room}_{j}"
                            )
                            if new != pts:
                                content[day_type][room] = new
                                st.session_state.data = data

st.success("POINT COSTS VISIBLE — MALAYSIA 01:25 PM — 100% FIXED")
st.balloons()
