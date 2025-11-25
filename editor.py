import streamlit as st
import json
import copy
import os
from datetime import date
from typing import Dict, List, Any, Optional

# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = None
if "working_resorts" not in st.session_state:
    st.session_state.working_resorts = {}
if "current_resort_id" not in st.session_state:
    st.session_state.current_resort_id = None

# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def load_data():
    if os.path.exists("data_v2.json"):
        try:
            with open("data_v2.json", "r") as f:
                return json.load(f)
        except:
            return None
    return None

def save_data(data):
    with open("data_v2.json", "w") as f:
        json.dump(data, f, indent=2)

def find_resort_by_id(data: Dict, rid: str):
    for r in data.get("resorts", []):
        if r.get("id") == rid:
            return r
    return None

def get_working_resort(data: Dict, resort_id: str):
    if not resort_id:
        return None
    if resort_id not in st.session_state.working_resorts:
        committed = find_resort_by_id(data, resort_id)
        if committed:
            st.session_state.working_resorts[resort_id] = copy.deepcopy(committed)
    return st.session_state.working_resorts.get(resort_id)

def validate_resort(working: Dict):
    issues = []
    years = working.get("years", {})
    for year, ydata in years.items():
        seasons = ydata.get("seasons", [])
        if not seasons:
            issues.append(f"[{year}] NO SEASONS DEFINED — RESORT IS BROKEN")
    return issues

# ----------------------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------------------
def main():
    st.set_page_config(page_title="MVC Resort Editor V2", layout="wide")
    st.title("MVC Resort Editor V2")

    # Load data
    if st.session_state.data is None:
        auto_data = load_data()
        if auto_data and auto_data.get("resorts"):
            st.session_state.data = auto_data
            st.success("Loaded data_v2.json")
        else:
            st.info("Place your `data_v2.json` in the same folder as this app")
            uploaded = st.file_uploader("Or upload your data file", type="json")
            if uploaded:
                st.session_state.data = json.load(uploaded)
                save_data(st.session_state.data)
                st.rerun()

    if not st.session_state.data or not st.session_state.data.get("resorts"):
        st.warning("No valid data loaded")
        st.stop()

    data = st.session_state.data
    resorts = data["resorts"]

    # Resort selector in sidebar
    resort_names = [r.get("display_name") or r.get("resort_name") or r.get("id") or "Unknown" for r in resorts]
    selected_name = st.sidebar.selectbox("Select Resort", resort_names)

    if not selected_name:
        st.info("Please select a resort")
        st.stop()

    # Find selected resort
    selected_resort = None
    for r in resorts:
        if (r.get("display_name") or r.get("resort_name") or r.get("id")) == selected_name:
            selected_resort = r
            break

    if not selected_resort:
        st.error("Resort not found")
        st.stop()

    resort_id = selected_resort["id"]
    st.session_state.current_resort_id = resort_id

    working = get_working_resort(data, resort_id)
    if not working:
        st.error("Failed to load resort")
        st.stop()

    # Header
    name = working.get("resort_name") or working.get("display_name") or resort_id
    st.header(f"Resort: {name}")

    # Validation
    issues = validate_resort(working)
    with st.expander("Data Validation", expanded=True):
        if issues:
            st.error(f"{len(issues)} critical issue(s):")
            for issue in issues:
                st.write("• " + issue)
        else:
            st.success("All validation passed!")

    # Simple season editor
    st.write("### Seasons")
    years = list(working.get("years", {}).keys()) or ["2025"]
    
    for year in years:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = working.setdefault("years", {}).setdefault(year, {})
            seasons = year_data.setdefault("seasons", [])

            # List existing seasons
            for i, season in enumerate(seasons[:]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{season.get('name', 'Unnamed Season')}**")
                with col2:
                    if st.button("Delete", key=f"del_{year}_{i}"):
                        seasons.pop(i)
                        st.success("Season deleted")
                        st.rerun()

            # Add new season
            new_name = st.text_input("New season name", key=f"new_season_{year}")
            if st.button("Add Season", key=f"add_season_{year}") and new_name.strip():
                seasons.append({
                    "name": new_name.strip(),
                    "periods": [],
                    "day_categories": {}
                })
                st.success(f"Added season: {new_name}")
                st.rerun()

    # Save button
    if st.button("Save All Changes", type="primary"):
        idx = next((i for i, r in enumerate(resorts) if r["id"] == resort_id), None)
        if idx is not None:
            data["resorts"][idx] = copy.deepcopy(working)
            save_data(data)
            st.session_state.working_resorts.pop(resort_id, None)
            st.success("Changes saved to data_v2.json!")
            st.rerun()

    # Download
    st.download_button(
        "Download data_v2.json",
        json.dumps(data, indent=2),
        "data_v2.json",
        "application/json"
    )

# ----------------------------------------------------------------------
# REQUIRED: run() function for app.py
# ----------------------------------------------------------------------
def run():
    main()

# Run directly if executed
if __name__ == "__main__":
    run()
