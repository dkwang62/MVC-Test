import streamlit as st
import json
import copy
import os
from datetime import date, datetime
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
def find_resort_by_id(data: Dict, rid: str) -> Optional[Dict]:
    return next((r for r in data.get("resorts", []) if r.get("id") == rid), None)

def get_years(data: Dict) -> List[str]:
    years = set()
    for r in data.get("resorts", []):
        years.update(r.get("years", {}).keys())
    return sorted(years) or ["2025"]

def get_working_resort(data: Dict, resort_id: str) -> Optional[Dict]:
    if not resort_id:
        return None
    if resort_id not in st.session_state.working_resorts:
        committed = find_resort_by_id(data, resort_id)
        if committed:
            st.session_state.working_resorts[resort_id] = copy.deepcopy(committed)
    return st.session_state.working_resorts.get(resort_id)

# ----------------------------------------------------------------------
# VALIDATION
# ----------------------------------------------------------------------
def validate_resort(working: Dict, years: List[str]) -> List[str]:
    issues = []
    for year in years:
        year_obj = working.get("years", {}).get(year, {})
        seasons = year_obj.get("seasons", []) if year_obj else []
        if not seasons:
            issues.append(f"[{year}] NO SEASONS DEFINED — RESORT IS BROKEN")
    return issues

def render_validation(working: Dict, years: List[str]):
    with st.expander("Data Validation", expanded=True):
        issues = validate_resort(working, years)
        if issues:
            st.error(f"{len(issues)} critical issue(s):")
            for i in issues:
                st.write("• " + i)
        else:
            st.success("All good!")

# ----------------------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------------------
def main():
    st.set_page_config(page_title="MVC Resort Editor", layout="wide")
    st.title("MVC Resort Editor V2")

    # Load data
    if st.session_state.data is None:
        if os.path.exists("data_v2.json"):
            with open("data_v2.json") as f:
                st.session_state.data = json.load(f)
            st.success("Loaded data_v2.json")
        else:
            st.info("Place your `data_v2.json` next to this app")
            uploaded = st.file_uploader("Or upload here", type="json")
            if uploaded:
                st.session_state.data = json.load(uploaded)
                st.rerun()

    if not st.session_state.data:
        st.stop()

    data = st.session_state.data
    resorts = data.get("resorts", [])

    # Resort selector
    if resorts:
        names = {r.get("display_name") or r.get("id", "Unknown"): r.get("id") for r in resorts}
        selected = st.sidebar.selectbox("Select Resort", options=[""] + list(names.keys()))
        if selected:
            st.session_state.current_resort_id = names[selected]

    working = get_working_resort(data, st.session_state.current_resort_id)

    if not working:
        st.info("No resort selected")
        st.stop()

    st.header(working.get("resort_name") or working.get("display_name") or "Unnamed Resort")
    years = get_years(data)

    render_validation(working, years)

    # Save button
    if st.button("Save Changes", type="primary"):
        idx = next((i for i, r in enumerate(resorts) if r.get("id") == working.get("id")), None)
        if idx is not None:
            data["resorts"][idx] = copy.deepcopy(working)
            with open("data_v2.json", "w") as f:
                json.dump(data, f, indent=2)
            st.success("Saved!")
            st.session_state.working_resorts.pop(working.get("id"), None)
            st.rerun()

    # Simple season editor
    for year in years:
        with st.expander(f"{year} Seasons", expanded=True):
            year_obj = working.setdefault("years", {}).setdefault(year, {})
            seasons = year_obj.setdefault("seasons", [])

            for i, season in enumerate(seasons[:]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{season.get('name', 'Unnamed')}**")
                with col2:
                    if st.button("Delete", key=f"del_{year}_{i}"):
                        seasons.pop(i)
                        st.rerun()

            new_name = st.text_input("New season name", key=f"new_{year}")
            if st.button("Add Season", key=f"add_{year}") and new_name.strip():
                seasons.append({"name": new_name.strip(), "periods": [], "day_categories": {}})
                st.rerun()

    st.download_button("Download data", json.dumps(data, indent=2), "data_v2.json")

# ----------------------------------------------------------------------
# THIS IS THE EXACT FUNCTION YOUR app.py EXPECTS
# ----------------------------------------------------------------------
def run():
    main()

# ----------------------------------------------------------------------
# Run when executed directly
# ----------------------------------------------------------------------
if __name__ == "__main__":
    run()
