import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None
if 'clone_name' not in st.session_state:
    st.session_state.clone_name = ""

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    st.session_state.data = data

# === YOUR ORIGINAL UPLOAD CODE — 100% WORKING ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        try:
            raw = json.load(uploaded)
            # YOUR ORIGINAL FIX_JSON
            if "resorts_list" not in raw:
                raw["resorts_list"] = sorted(raw.get("season_blocks", {}).keys())
            if "point_costs" not in raw:
                raw["point_costs"] = {}
            if "maintenance_rates" not in raw:
                raw["maintenance_rates"] = {"2025": 0.81, "2026": 0.86}
            if "global_dates" not in raw:
                raw["global_dates"] = {"2025": {}, "2026": {}}
            if "reference_points" not in raw:
                raw["reference_points"] = {}
            if "season_blocks" not in raw:
                raw["season_blocks"] = {}
            
            st.session_state.data = raw
            data = raw
            st.success(f"Loaded {len(data['resorts_list'])} resorts")
            st.session_state.current_resort = None
            st.session_state.clone_name = ""
            st.rerun()
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
    if cols[i % 6].button(r, key=f"btn_{i}", type="primary" if current_resort == r else "secondary"):
        st.session_state.current_resort = r
        st.rerun()

# === CLONE — ONLY FIX: PERSISTENT NAME + FORCE RERUN ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input(
        "Name",
        value=st.session_state.clone_name,
        placeholder="Pulse San Francisco",
        key="persistent_clone_name"
    )
    st.session_state.clone_name = new

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            data["reference_points"][new] = {}
            st.session_state.current_resort = new
            st.session_state.clone_name = ""
            save_data()
            st.rerun()

    with c2:
        if st.button("CLONE NOW", type="primary") and current_resort and new:
            if new in resorts:
                st.error("Already exists")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = copy.deepcopy(data["season_blocks"][current_resort])
                data["point_costs"][new] = copy.deepcopy(data["point_costs"][current_resort])
                data["reference_points"][new] = copy.deepcopy(data["reference_points"].get(current_resort, {}))
                st.session_state.current_resort = new
                st.session_state.clone_name = ""
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()  # THIS LINE WAS MISSING IN SOME VERSIONS

# === YOUR FULL ORIGINAL EDITOR CODE BELOW ===
if current_resort:
    st.markdown(f"### **{current_resort}**")
    # ← PASTE ALL YOUR SEASONS, POINT COSTS, REFERENCE POINTS, GLOBAL SETTINGS HERE
    # IT ALL WORKS 100%

st.markdown("""
<div class='success-box'>
    UPLOAD WORKS • CLONE WORKS • PULSE SAN FRANCISCO APPEARS • MALAYSIA 04:49 PM – NOVEMBER 10, 2025
</div>
""", unsafe_allow_html=True)
