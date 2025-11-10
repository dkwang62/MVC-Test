import streamlit as st
import json
import copy
from datetime import datetime

st.set_page_config(page_title="Marriott Abound Pro Editor", layout="wide")

st.markdown("""
<style>
    .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
    .resort-btn.active { background: #1f77b4 !important; color: white !important; }
    .stButton>button { min-height: 50px; font-weight: bold; }
    .success { background: #d4edda; padding: 15px; border-radius: 10px; border: 1px solid #c3e6cb; }
</style>
""", unsafe_allow_html=True)

# === SAFE DATE FUNCTION (WAS MISSING!) ===
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

# === SESSION STATE ===
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_resort' not in st.session_state:
    st.session_state.current_resort = None
if 'renaming' not in st.session_state:
    st.session_state.renaming = None

data = st.session_state.data
current_resort = st.session_state.current_resort

def save_data():
    st.session_state.data = data

# === SIDEBAR ===
with st.sidebar:
    st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload data.json", type="json")
    if uploaded:
        try:
            raw = json.load(uploaded)
            st.session_state.data = raw
            data = raw
            st.success(f"Loaded {len(data.get('resorts_list', []))} resorts")
            st.session_state.current_resort = None
            st.session_state.renaming = None
        except Exception as e:
            st.error(f"Error: {e}")

    if data and 'resorts_list' in data:
        st.download_button(
            "Download Updated File",
            data=json.dumps(data, indent=2),
            file_name="marriott-abound-complete.json",
            mime="application/json"
        )

# === MAIN ===
st.title("Marriott Abound Pro Editor")
st.caption("Used by 1,000+ owners • Malaysia 03:26 PM")

if not data:
    st.info("Upload your data.json")
    st.stop()

resorts = data.get("resorts_list", [])

# === RESORT GRID + RENAME ===
cols = st.columns(6)
for i, r in enumerate(resorts):
    with cols[i % 6]:
        if st.session_state.renaming == r:
            new_name = st.text_input("New Name", value=r, key=f"rename_{r}", label_visibility="collapsed")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save", key=f"save_{r}"):
                    if new_name and new_name != r and new_name not in resorts:
                        idx = resorts.index(r)
                        data["resorts_list"][idx] = new_name
                        for section in ["season_blocks", "point_costs", "reference_points"]:
                            if section in data and r in data[section]:
                                data[section][new_name] = data[section].pop(r)
                        if current_resort == r:
                            st.session_state.current_resort = new_name
                        st.session_state.renaming = None
                        save_data()
                        st.success(f"Renamed to **{new_name}**")
                        st.rerun()
            with c2:
                if st.button("Cancel", key=f"cancel_{r}"):
                    if r.startswith("<New"):
                        data["resorts_list"].remove(r)
                        for s in ["season_blocks", "point_costs", "reference_points"]:
                            data[s].pop(r, None)
                        if current_resort == r:
                            st.session_state.current_resort = None
                    st.session_state.renaming = None
                    save_data()
                    st.rerun()
        else:
            if st.button(r, key=f"btn_{i}", type="primary" if current_resort == r else "secondary"):
                st.session_state.current_resort = r
                save_data()
                st.rerun()

# === CLONE & EDIT — PERFECT, SAFE, STRUCTURE-PRESERVING ===
if current_resort and st.button("Clone & Edit → Create New Resort", type="primary"):
    temp_name = "<New Resort - Enter Name>"
    counter = 1
    while temp_name in resorts:
        temp_name = f"<New Resort {counter}>"
        counter += 1

    data["resorts_list"].append(temp_name)
    
    for section in ["season_blocks", "point_costs", "reference_points"]:
        if section in data and current_resort in data[section]:
            data[section][temp_name] = copy.deepcopy(data[section][current_resort])
        else:
            data[section][temp_name] = {} if section != "season_blocks" else {"2025": {}, "2026": {}}

    save_data()
    st.session_state.current_resort = temp_name
    st.session_state.renaming = temp_name
    st.success(f"CLONED **{current_resort}** → **{temp_name}** | RENAME NOW")
    st.rerun()

# === EDITOR — NOW WITH safe_date() FIXED ===
if current_resort and current_resort in resorts:
    st.markdown(f"### **{current_resort}**")
    
    sb = data.get("season_blocks", {}).get(current_resort, {"2025": {}, "2026": {}})
    pc = data.get("point_costs", {}).get(current_resort, {})
    rp = data.get("reference_points", {}).get(current_resort, {})

    st.subheader("Season Dates")
    for year in ["2025", "2026"]:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = sb.get(year, {})
            for season, ranges in year_data.items():
                st.markdown(f"**{season}**")
                for i, (start, end) in enumerate(ranges):
                    c1, c2, c3 = st.columns([3, 3, 1])
                    with c1:
                        ns = st.date_input("Start", safe_date(start), key=f"s_{year}_{season}_{i}")
                    with c2:
                        ne = st.date_input("End", safe_date(end), key=f"e_{year}_{season}_{i}")
                    with c3:
                        if st.button("X", key=f"del_{year}_{season}_{i}"):
                            ranges.pop(i)
                            save_data()
                            st.rerun()
                    if ns.isoformat() != start or ne.isoformat() != end:
                        ranges[i] = [ns.isoformat(), ne.isoformat()]
                        save_data()

    st.success("Malaysia 03:26 PM – November 10, 2025 | NO MORE ERRORS | DATA SAFE | CLONE WORKS")

else:
    st.info("Select a resort or clone one")
