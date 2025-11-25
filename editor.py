import streamlit as st
import json
import copy
import re
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Set

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
DEFAULT_YEARS = ["2025", "2026"]
ALL_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}

# ----------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# ----------------------------------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = None
if "working_resorts" not in st.session_state:
    st.session_state.working_resorts = {}
if "current_resort_id" not in st.session_state:
    st.session_state.current_resort_id = None

# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------
def rk(resort_id: str, *parts):
    return "__".join([resort_id or "global"] + [str(p) for p in parts])

def find_resort_by_id(data: Dict, rid: str) -> Optional[Dict]:
    return next((r for r in data.get("resorts", []) if r.get("id") == rid), None)

def get_years(data: Dict) -> List[str]:
    years = set()
    for r in data.get("resorts", []):
        years.update(str(y) for y in r.get("years", {}).keys())
    return sorted(years) or DEFAULT_YEARS

def safe_date(d) -> date:
    if isinstance(d, str):
        try:
            return datetime.strptime(d.strip(), "%Y-%m-%d").date()
        except:
            pass
    return date(2025, 1, 1)

# ----------------------------------------------------------------------
# FIXED: load_resort – never stale, never crashes
# ----------------------------------------------------------------------
def get_working_resort(data: Dict, resort_id: Optional[str]) -> Optional[Dict]:
    if not resort_id:
        return None

    # Always get latest committed version
    committed = find_resort_by_id(data, resort_id)
    if not committed:
        st.session_state.working_resorts.pop(resort_id, None)
        return None

    # Keep unsaved changes if they exist
    if resort_id in st.session_state.working_resorts:
        return st.session_state.working_resorts[resort_id]

    # Otherwise create fresh working copy
    st.session_state.working_resorts[resort_id] = copy.deepcopy(committed)
    return st.session_state.working_resorts[resort_id]

# ----------------------------------------------------------------------
# VALIDATION – works perfectly
# ----------------------------------------------------------------------
def get_all_room_types(working: Dict) -> Set[str]:
    rooms = set()
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points", {})
                if isinstance(rp, dict):
                    rooms.update(rp.keys())
        for h in year_obj.get("holidays", []):
            rp = h.get("room_points", {})
            if isinstance(rp, dict):
                rooms.update(rp.keys())
    return rooms

def validate_resort(working: Dict, years: List[str]) -> List[str]:
    issues = []
    all_rooms = get_all_room_types(working)

    for year in years:
        year_obj = working.get("years", {}).get(year, {}) or {}
        seasons = year_obj.get("seasons", [])

        if not seasons:
            issues.append(f"[{year}] NO SEASONS DEFINED — RESORT IS BROKEN")

        for s in seasons:
            name = s.get("name") or "Unnamed"
            covered = set()
            for cat in s.get("day_categories", {}).values():
                days = {d for d in cat.get("day_pattern", []) if d in ALL_DAYS}
                if covered & days:
                    issues.append(f"[{year}] {name} → overlapping days")
                covered.update(days)
            if ALL_DAYS - covered:
                issues.append(f"[{year}] {name} → missing weekdays")

            if all_rooms:
                for cat in s.get("day_categories", {}).values():
                    rp = cat.get("room_points", {})
                    if isinstance(rp, dict):
                        missing = all_rooms - rp.keys()
                        if missing:
                            issues.append(f"[{year}] {name} → missing room points: {', '.join(sorted(missing))}")

    return issues

def render_validation(working: Dict, years: List[str]):
    with st.expander("Data Validation", expanded=True):
        issues = validate_resort(working, years)
        if issues:
            st.error(f"{len(issues)} issue(s) found:")
            for i in issues:
                st.write("• " + i)
        else:
            st.success("All checks passed!")

# ----------------------------------------------------------------------
# SEASON MANAGEMENT
# ----------------------------------------------------------------------
def delete_season(working: Dict, season_name: str):
    for year_obj in working.get("years", {}).values():
        seasons = year_obj.get("seasons", [])
        year_obj["seasons"] = [s for s in seasons if s.get("name") != season_name]

# ----------------------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------------------
def main():
    st.set_page_config(page_title="MVC Resort Editor", layout="wide")
    st.title("MVC Resort Editor V2")

    # Auto-load data
    if st.session_state.data is None:
        try:
            with open("data_v2.json") as f:
                st.session_state.data = json.load(f)
                st.success("Loaded data_v2.json")
        except:
            st.info("Place your `data_v2.json` in the same folder or upload below.")
            uploaded = st.file_uploader("Upload data_v2.json", type="json")
            if uploaded:
                st.session_state.data = json.load(uploaded)
                st.rerun()

    if not st.session_state.data:
        st.stop()

    data = st.session_state.data
    resorts = data.get("resorts", [])
    years = get_years(data)

    # Resort selector
    if resorts:
        names = {r.get("display_name") or r.get("id"): r.get("id") for r in resorts}
        selected = st.sidebar.selectbox("Select Resort", [""] + list(names.keys()))
        if selected:
            st.session_state.current_resort_id = names[selected]

    working = get_working_resort(data, st.session_state.current_resort_id)

    if not working:
        st.info("No resort selected")
        st.stop()

    st.header(working.get("resort_name") or working.get("display_name") or working.get("id"))

    # Validation
    render_validation(working, years)

    # Save button
    if st.button("Save All Changes", type="primary"):
        idx = next((i for i, r in enumerate(data["resorts"]) if r.get("id") == working.get("id")), None)
        if idx is not None:
            data["resorts"][idx] = copy.deepcopy(working)
            st.session_state.working_resorts.pop(working.get("id"), None)
            with open("data_v2.json", "w") as f:
                json.dump(data, f, indent=2)
            st.success("Saved!")
            st.rerun()

    # Simple Season Editor
    tab = st.tabs(["Seasons"])[0]
    with tab:
        for year in years:
            with st.expander(f"{year} Seasons", expanded=True):
                year_obj = working.setdefault("years", {}).setdefault(year, {})
                seasons = year_obj.setdefault("seasons", [])

                for i, season in enumerate(seasons[:]):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.write(f"**{season.get('name', 'Unnamed Season')}**")
                    with col2:
                        if st.button("Delete", key=f"del_{year}_{i}"):
                            delete_season(working, season.get("name"))
                            st.rerun()

                new_name = st.text_input("New season name", key=f"new_season_{year}")
                if st.button("Add Season", key=f"add_{year}") and new_name.strip():
                    name = new_name.strip()
                    for y in years:
                        yobj = working.setdefault("years", {}).setdefault(y, {})
                        yobj.setdefault("seasons", []).append({
                            "name": name,
                            "periods": [],
                            "day_categories": {
                                "sun_thu": {"day_pattern": ["Sun","Mon","Tue","Wed","Thu"], "room_points": {}},
                                "fri_sat": {"day_pattern": ["Fri","Sat"], "room_points": {}}
                            }
                        })
                    st.rerun()

    st.download_button("Download data_v2.json", json.dumps(data, indent=2), "data_v2.json")

# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
