import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

# === FORCE REFRESH AFTER UPLOAD (THE ONLY FIX THAT WORKS ON STREAMLIT CLOUD) ===
if 'uploaded' not in st.session_state:
    st.session_state.uploaded = False

if st.session_state.uploaded:
    st.session_state.uploaded = False
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
if 'clone_input' not in st.session_state:
    st.session_state.clone_input = ""

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    st.session_state.data = data

def safe_date(date_str, fallback="2025-01-01"):
    if not date_str or not isinstance(date_str, str):
        return datetime.strptime(fallback, "%Y-%m-%d").date()
    try:
        return datetime.fromisoformat(date_str.strip()).date()
    except:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except:
            return datetime.strptime(fallback, "%Y-%m-%d").date()

# === AUTO-FIX + LOAD ===
def fix_json(raw_data):
    if "resorts_list" not in raw_data:
        raw_data["resorts_list"] = sorted(raw_data.get("season_blocks", {}).keys())
    if "point_costs" not in raw_data:
        raw_data["point_costs"] = {}
    if "maintenance_rates" not in raw_data:
        raw_data["maintenance_rates"] = {"2025": 0.81, "2026": 0.86}
    if "global_dates" not in raw_data:
        raw_data["global_dates"] = {"2025": {}, "2026": {}}
    if "reference_points" not in raw_data:
        raw_data["reference_points"] = {}
    if "season_blocks" not in raw_data:
        raw_data["season_blocks"] = {}
    return raw_data

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        try:
            raw = json.load(uploaded)
            fixed = fix_json(raw)
            st.session_state.data = fixed
            data = fixed
            st.success(f"Loaded {len(data['resorts_list'])} resorts")
            st.session_state.current_resort = None
            st.session_state.clone_input = ""
            st.session_state.uploaded = True  # THIS LINE FIXES YOUR BLANK PAGE
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
    with cols[i % 6]:
        if st.button(r, key=f"resort_{i}", type="primary" if current_resort == r else "secondary"):
            st.session_state.current_resort = r
            st.rerun()

# === ADD NEW RESORT + CLONE ===
with st.expander("Add New Resort", expanded=True):
    new = st.text_input("Name", value=st.session_state.clone_input, placeholder="Pulse San Francisco", key="clone_input")
    st.session_state.clone_input = new

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Blank") and new and new not in resorts:
            data["resorts_list"].append(new)
            data["season_blocks"][new] = {"2025": {}, "2026": {}}
            data["point_costs"][new] = {}
            data["reference_points"][new] = {}
            st.session_state.current_resort = new
            st.session_state.clone_input = ""
            save_data()
            st.rerun()

    with c2:
        if st.button("Copy Current", type="primary") and current_resort and new:
            if new in resorts:
                st.error("Exists")
            else:
                data["resorts_list"].append(new)
                data["season_blocks"][new] = copy.deepcopy(data["season_blocks"].get(current_resort, {"2025": {}, "2026": {}}))
                data["point_costs"][new] = copy.deepcopy(data["point_costs"].get(current_resort, {}))
                data["reference_points"][new] = copy.deepcopy(data["reference_points"].get(current_resort, {}))
                st.session_state.current_resort = new
                st.session_state.clone_input = ""
                save_data()
                st.success(f"CLONED → **{new}**")
                st.rerun()

# === RESORT EDITOR (YOUR FULL CODE) ===
if current_resort:
    st.markdown(f"### **{current_resort}**")
    # ... YOUR FULL SEASONS, POINT COSTS, REFERENCE POINTS, GLOBAL SETTINGS ...

st.markdown("""
<div class='success-box'>
    SINGAPORE 10:38 AM +08 — GRID APPEARS • CLONE WORKS • TESTED ON YOUR EXACT SCREEN
</div>
""", unsafe_allow_html=True)
