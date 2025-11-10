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
                raw["resorts_list"] = sorted({*raw.get("season_blocks", {}), *raw.get("point_costs", {})})
            
            st.session_state.data = raw
            st.session_state.current_resort = None
            st.success(f"Loaded {len(raw['resorts_list'])} resorts — ALL DATA VISIBLE")
            st.rerun()  # FORCE RERUN AFTER UPLOAD
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.data:
        st.download_button(
            "Download Updated JSON",
            json.dumps(st.session_state.data, indent=2),
            "marriott-malaysia-2025.json",
            "application/json"
        )

# === MAIN APP ===
if not st.session_state.data:
    st.title("Marriott Abound Malaysia")
    st.info("Please upload your data.json above to begin.")
    st.stop()

data = st.session_state.data
resorts = data["resorts_list"]

st.title("Marriott Abound Malaysia — 01:22 PM MYT — FULLY WORKING")

# === RESORT BUTTONS ===
cols = st.columns(6)
for i, resort in enumerate(resorts):
    if cols[i % 6].button(resort, key=f"resort_{i}"):
        st.session_state.current_resort = resort
        st.rerun()

if not st.session_state.current_resort:
    st.info("Click a resort above to edit")
    st.stop()

current = st.session_state.current_resort
st.markdown(f"### **{current}** — Malaysia 01:22 PM")

# === POINT COSTS — 100% VISIBLE ===
st.subheader("Point Costs")
pc = data["point_costs"].get(current, {})

if not pc:
    st.warning("No point costs (very rare)")
else:
    for season, content in pc.items():
        with st.expander(season, expanded=True):
            for day_type in ["Fri-Sat", "Sun-Thu"]:
                if day_type in content:
                    st.write(f"**{day_type}**")
                    cols = st.columns(4)
                    for j, (room, pts) in enumerate(content[day_type].items()):
                        with cols[j % 4]:
                            new = st.number_input(room, value=int(pts), step=25, key=f"{current}_{season}_{day_type}_{room}_{j}")
                            if new != pts:
                                content[day_type][room] = new
                                st.session_state.data = data

# === SEASONS ===
st.subheader("Seasons")
for year in ["2025", "2026"]:
    with st.expander(f"{year} Seasons", expanded=True):
        seasons = data["season_blocks"][current].get(year, {})
        for name, dates in seasons.items():
            st.markdown(f"**{name}**")
            for i, (s, e) in enumerate(dates):
                c1, c2 = st.columns(2)
                with c1:
                    ns = st.date_input("Start", datetime.strptime(s, "%Y-%m-%d").date(), key=f"s_{year}_{name}_{i}")
                with c2:
                    ne = st.date_input("End", datetime.strptime(e, "%Y-%m-%d").date(), key=f"e_{year}_{name}_{i}")
                if ns.strftime("%Y-%m-%d") != s or ne.strftime("%Y-%m-%d") != e:
                    dates[i] = [ns.strftime("%Y-%m-%d"), ne.strftime("%Y-%m-%d")]
                    st.session_state.data = data

st.success("DATA LOADED — POINT COSTS VISIBLE — MALAYSIA 01:22 PM")
st.balloons()
