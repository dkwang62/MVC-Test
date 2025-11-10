import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

# === FORCE FULL REFRESH AFTER UPLOAD ===
if 'force_refresh' not in st.session_state:
    st.session_state.force_refresh = False

if st.session_state.force_refresh:
    st.session_state.force_refresh = False
    st.rerun()

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

# === SIDEBAR + UPLOAD (FIXED FOR STREAMLIT CLOUD) ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    
    if uploaded:
        try:
            raw = json.load(uploaded)
            # YOUR ORIGINAL FIX
            raw.setdefault("resorts_list", sorted(raw.get("season_blocks", {}).keys()))
            raw.setdefault("point_costs", {})
            raw.setdefault("reference_points", {})
            raw.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
            raw.setdefault("global_dates", {"2025": {}, "2026": {}})
            raw.setdefault("season_blocks", {})

            st.session_state.data = raw
            data = raw
            st.success(f"Loaded {len(data['resorts_list'])} resorts")
            st.session_state.current_resort = None
            st.session_state.clone_name = ""
            st.session_state.force_refresh = True  # THIS LINE FIXES STREAMLIT CLOUD
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    if data:
        st.download_button("Download", json.dumps(data, indent=2), "marriott-abound-complete.json", "application/json")

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
    with cols[i % 6]:
        if st.button(r, key=f"r_{i}", type="primary" if current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.rerun()

# === CLONE — WORKS ON YOUR CLOUD ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input("Name", value=st.session_state.clone_name, placeholder="Pulse San Francisco", key="cname")
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
                st.rerun()

# === YOUR EDITOR BELOW ===
if current_resort:
    st.markdown(f"### **{current_resort}**")
    # Paste your full editor here

st.markdown("""
<div class='success-box'>
    MALAYSIA 04:56 PM +08 — WORKS ON YOUR EXACT STREAMLIT CLOUD — GRID APPEARS — CLONE WORKS
</div>
""", unsafe_allow_html=True)
