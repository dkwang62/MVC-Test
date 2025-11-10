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
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big'>Marriott Malaysia</p>", unsafe_allow_html=True)
    st.write(f"**Time:** {datetime.now().strftime('%I:%M %p')} MYT")

    uploaded_file = st.file_uploader("Upload data.json", type="json")

    if uploaded_file and not st.session_state.uploaded:
        try:
            raw = json.load(uploaded_file)
            raw.setdefault("resorts_list", [])
            raw.setdefault("reference_points", {})  # ← YOUR REAL KEY
            raw.setdefault("season_blocks", {})
            
            if not raw["resorts_list"]:
                keys = set(raw.get("reference_points", {}).keys()) | set(raw.get("season_blocks", {}).keys())
                raw["resorts_list"] = sorted(keys)
            
            st.session_state.data = raw
            st.session_state.uploaded = True
            st.success(f"Loaded {len(raw['resorts_list'])} resorts — FULLY DYNAMIC")
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
    st.info("Upload your data.json")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Malaysia — 01:45 PM MYT — UNIVERSAL FINAL")
st.success("DATA LOADED — CLICK ANY RESORT")

# === RESORTS ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    if cols[i % 6].button(r, key=f"r_{i}"):
        st.session_state.current_resort = r
        st.rerun()

if not st.session_state.current_resort:
    st.stop()

current = st.session_state.current_resort
st.markdown(f"### **{current}**")

# === UNIVERSAL POINT COSTS — WORKS WITH ALL 3 STRUCTURES ===
st.subheader("Reference Points")
points = data["reference_points"].get(current, {})

if not points:
    st.warning("No reference points")
else:
    for season, content in points.items():
        with st.expander(season, expanded=True):
            # CASE 1: Has day types (Mon-Thu, Sun-Thu, Fri-Sat)
            day_types = [k for k in content.keys() if k in ["Mon-Thu", "Sun-Thu", "Fri-Sat"]]
            if day_types:
                for day_type in day_types:
                    rooms = content[day_type]
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"a_{current}_{season}_{day_type}_{room}_{j}")
                            if new != pts:
                                rooms[room] = new
                                st.session_state.data = data
            else:
                # CASE 2: Holiday weeks — direct points
                for sub_season, rooms in content.items():
                    st.markdown(f"**{sub_season}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(rooms.items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"b_{current}_{season}_{sub_season}_{room}_{j}")
                            if new != pts:
                                rooms[room] = new
                                st.session_state.data = data

st.success("ALL STRUCTURES VISIBLE — MON-THU, SUN-THU, FRI-SAT, HOLIDAY WEEKS — MALAYSIA 01:45 PM")
st.balloons()
