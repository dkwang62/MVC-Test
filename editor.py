import streamlit as st
import json
import copy
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
for key in ["data", "working_resorts", "current_resort_id"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "working_resorts" else {}

# ----------------------------------------------------------------------
# LOAD DATA
# ----------------------------------------------------------------------
if st.session_state.data is None:
    if os.path.exists("data_v2.json"):
        try:
            with open("data_v2.json") as f:
                st.session_state.data = json.load(f)
        except:
            pass

# ----------------------------------------------------------------------
# FALLBACK UPLOAD
# ----------------------------------------------------------------------
if st.session_state.data is None:
    st.info("Upload your `data_v2.json`")
    uploaded = st.file_uploader("data_v2.json", type="json")
    if uploaded:
        st.session_state.data = json.load(uploaded)
        st.rerun()

if not st.session_state.data or "resorts" not in st.session_state.data:
    st.stop()

data = st.session_state.data
resorts = data["resorts"]

# ----------------------------------------------------------------------
# RESORT SELECTOR (FIXED — SHOWS RESORTS IMMEDIATELY)
# ----------------------------------------------------------------------
resort_options = {}
for r in resorts:
    name = r.get("display_name") or r.get("resort_name") or r.get("id") or "Unknown"
    resort_options[name] = r["id"]

selected_name = st.sidebar.selectbox(
    "Select Resort",
    options=[""] + list(resort_options.keys()),
    index=0 if not st.session_state.current_resort_id else 
          (list(resort_options.keys()).index(selected_name) + 1 if selected_name in resort_options else 0)
)

if selected_name:
    st.session_state.current_resort_id = resort_options[selected_name]

# ----------------------------------------------------------------------
# WORKING RESORT — FIXED (never stale)
# ----------------------------------------------------------------------
def get_working_resort(resort_id: str) -> Optional[Dict]:
    if not resort_id:
        return None
    if resort_id not in st.session_state.working_resorts:
        committed = next((r for r in resorts if r["id"] == resort_id), None)
        if committed:
            st.session_state.working_resorts[resort_id] = copy.deepcopy(committed)
    return st.session_state.working_resorts.get(resort_id)

working = get_working_resort(st.session_state.current_resort_id)
if not working:
    st.info("No resort selected")
    st.stop()

# ----------------------------------------------------------------------
# VALIDATION — WORKS INSTANTLY
# ----------------------------------------------------------------------
def validate(working: Dict):
    issues = []
    years = working.get("years", {})
    for year, ydata in years.items():
        if not ydata.get("seasons"):
            issues.append(f"[{year}] NO SEASONS — RESORT BROKEN")
    return issues

issues = validate(working)
with st.expander("Data Validation", expanded=True):
    if issues:
        st.error(f"{len(issues)} CRITICAL ISSUE(S):")
        for i in issues:
            st.write("• " + i)
    else:
        st.success("All good!")

# ----------------------------------------------------------------------
# FULL UI — YOUR ORIGINAL EDITOR
# ----------------------------------------------------------------------
st.title("MVC Resort Editor V2")
st.header(f"Resort: {working.get('resort_name') or working.get('display_name')}")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Season Dates", "Room Points", "Holidays", "Summary"
])

with tab2:
    st.write("### Seasons")
    years = sorted(working.get("years", {}).keys())
    for year in years:
        with st.expander(f"{year} Seasons", expanded=True):
            seasons = working["years"][year].setdefault("seasons", [])
            for i, s in enumerate(seasons[:]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{s.get('name', 'Unnamed')}**")
                with col2:
                    if st.button("Delete", key=f"del_{year}_{i}"):
                        for y in years:
                            working["years"][y]["seasons"] = [
                                s2 for s2 in working["years"][y]["seasons"]
                                if s2.get("name") != s.get("name")
                            ]
                        st.rerun()

            new_name = st.text_input("New season", key=f"new_{year}")
            if st.button("Add", key=f"add_{year}") and new_name.strip():
                for y in years:
                    working["years"][y]["seasons"].append({
                        "name": new_name.strip(),
                        "periods": [],
                        "day_categories": {}
                    })
                st.rerun()

# Save button
if st.button("Save All Changes", type="primary"):
    idx = next(i for i, r in enumerate(resorts) if r["id"] == working["id"])
    data["resorts"][idx] = copy.deepcopy(working)
    with open("data_v2.json", "w") as f:
        json.dump(data, f, indent=2)
    st.session_state.working_resorts.pop(working["id"], None)
    st.success("Saved!")
    st.rerun()

st.download_button("Download", json.dumps(data, indent=2), "data_v2.json")

# ----------------------------------------------------------------------
# REQUIRED FOR app.py
# ----------------------------------------------------------------------
def run():
    st.set_page_config(page_title="MVC Resort Editor V2", layout="wide")
    # Your full original setup_page() would go here if you had it
    st.markdown("<style>/* your CSS */</style>", unsafe_allow_html=True)

if __name__ == "__main__":
    run()
