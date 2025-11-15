import streamlit as st
import json
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
YEARS = ["2025", "2026"]
DAY_TYPES = ["Mon-Thu", "Fri-Sat", "Sun", "Sun-Thu"]
HOLIDAY_SEASON_KEY = "Holiday Week"
DEFAULT_POINTS = {
    "Mon-Thu": 100,
    "Fri-Sat": 200,
    "Sun": 150,
    "Sun-Thu": 120
}
DEFAULT_HOLIDAY_POINTS = {
    "Doubles": 1750,
    "King": 1750,
    "King City": 1925,
    "2-Bedroom": 3500,
}
# ----------------------------------------------------------------------
# PAGE CONFIG & STYLES
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(page_title="Marriott Data Editor", layout="wide")
    st.markdown("""
    <style>
        .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
        .stButton>button { min-height: 50px; font-weight: bold; }
        .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
        .rename-input { margin: 5px 0; }
        .section-header { border-bottom: 2px solid #1f77b4; padding-bottom: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)
# ----------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# ----------------------------------------------------------------------
def initialize_session_state():
    """Initialize all session state variables"""
    defaults = {
        'refresh_trigger': False,
        'last_upload_sig': None,
        'delete_confirm': False,
        'data': None,
        'current_resort': None,
        'previous_resort': None,
        'working_resorts': {},
        'editing_season': None,
        'editing_room': None,
        'change_history': [],
        'last_save_time': None
    }
 
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
def save_data():
    """Update last save time (history managed by callers)."""
    st.session_state.last_save_time = datetime.now()
def show_save_indicator():
    """Show a small save indicator."""
    if st.session_state.last_save_time:
        elapsed = (datetime.now() - st.session_state.last_save_time).total_seconds()
        if elapsed < 2: # Show for 2 seconds after save
            st.sidebar.success("✓ Saved", icon="✅")
def revert_last_change():
    """Revert to previous state if available."""
    if st.session_state.change_history:
        st.session_state.data = st.session_state.change_history.pop()
        # Drop all per-resort working copies – they’ll be recreated from reverted data
        st.session_state.working_resorts = {}
        st.rerun()
def snapshot_before_change():
    if st.session_state.data is not None:
        st.session_state.change_history.append(copy.deepcopy(st.session_state.data))
        st.session_state.change_history = st.session_state.change_history[-10:]
# ----------------------------------------------------------------------
# DATA MANAGEMENT
# ----------------------------------------------------------------------
def safe_date(date_str: Optional[str], default: str = "2025-01-01") -> datetime.date:
    """Safely converts a date string to a datetime.date object."""
    if not date_str or not isinstance(date_str, str):
        return datetime.strptime(default, "%Y-%m-%d").date()
 
    try:
        return datetime.fromisoformat(date_str.strip()).date()
    except ValueError:
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return datetime.strptime(default, "%Y-%m-%d").date()
def is_duplicate_resort_name(name: str, resorts: List[str]) -> bool:
    """Check if resort name already exists (case-insensitive)."""
    name_clean = name.strip().lower()
    return any(r.strip().lower() == name_clean for r in resorts)
# ----------------------------------------------------------------------
# FILE UPLOAD/DOWNLOAD COMPONENTS
# ----------------------------------------------------------------------
def handle_file_upload():
    """Handle JSON file upload with signature tracking."""
    uploaded = st.file_uploader("Upload data.json", type="json", key="file_uploader")
 
    if uploaded:
        size = getattr(uploaded, "size", 0)
        current_sig = f"{uploaded.name}:{size}"
     
        if current_sig != st.session_state.last_upload_sig:
            try:
                raw_data = json.load(uploaded)
                st.session_state.data = raw_data
                st.session_state.current_resort = None
                st.session_state.last_upload_sig = current_sig
                resorts_list = raw_data.get("resorts_list", [])
                st.success(f"✅ Loaded {len(resorts_list)} resorts")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")
def create_download_button(data: Dict):
    """Create download button for current data."""
    if data:
        json_data = json.dumps(copy.deepcopy(data), indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download Current Data",
            data=json_data,
            file_name="data.json",
            mime="application/json",
            key="download_btn",
            help="Download the most recent version of your data"
        )
# ----------------------------------------------------------------------
# VERIFY DOWNLOADED FILE
# ----------------------------------------------------------------------
def handle_file_verification():
    """Handle verification of downloaded file against current memory."""
    st.sidebar.markdown("### Verify Downloaded File")
    verify_upload = st.sidebar.file_uploader(
        "Upload data.json to verify",
        type="json",
        key="verify_uploader"
    )
 
    if verify_upload:
        try:
            uploaded_data = json.load(verify_upload)
            # Generate compact JSON strings with sorted keys for comparison
            current_json = json.dumps(st.session_state.data, sort_keys=True, ensure_ascii=False)
            uploaded_json = json.dumps(uploaded_data, sort_keys=True, ensure_ascii=False)
         
            if current_json == uploaded_json:
                st.sidebar.success("✅ The uploaded file matches the current data in memory.")
            else:
                st.sidebar.error("❌ The uploaded file does NOT match. Download again after confirming changes are saved.")
        except json.JSONDecodeError:
            st.sidebar.error("❌ Invalid JSON file uploaded.")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
# ----------------------------------------------------------------------
# RESORT MANAGEMENT COMPONENTS
# ----------------------------------------------------------------------
def render_resort_grid(resorts: List[str], current_resort: str):
    """Render the resort selection grid."""
    st.subheader("🏨 Select Resort")
    cols = st.columns(6)
 
    for i, resort in enumerate(resorts):
        with cols[i % 6]:
            button_type = "primary" if current_resort == resort else "secondary"
            if st.button(resort, key=f"resort_btn_{i}", type=button_type):
                st.session_state.current_resort = resort
                st.session_state.delete_confirm = False
                st.rerun()
def handle_resort_creation(data: Dict, resorts: List[str]):
    """Handle creation of new resorts."""
    with st.expander("➕ Add New Resort", expanded=True):
        new_name = st.text_input("Resort Name", placeholder="Pulse San Francisco", key="new_resort_name")
        col1, col2 = st.columns(2)
     
        with col1:
            if st.button("Create Blank", key="create_blank_btn") and new_name:
                new_name_clean = new_name.strip()
                if not new_name_clean:
                    st.error("Resort name cannot be empty")
                elif is_duplicate_resort_name(new_name_clean, resorts):
                    st.error("❌ Resort name already exists")
                else:
                    create_blank_resort(data, new_name_clean)
             
        with col2:
            if st.button("Clone Current", key="copy_current_btn", type="primary") and st.session_state.current_resort and new_name:
                new_name_clean = new_name.strip()
                if not new_name_clean:
                    st.error("Resort name cannot be empty")
                elif is_duplicate_resort_name(new_name_clean, resorts):
                    st.error("❌ Resort name already exists")
                else:
                    clone_resort(data, st.session_state.current_resort, new_name_clean)
def create_blank_resort(data: Dict, new_name: str):
    """Create a new blank resort."""
    snapshot_before_change()
    data.setdefault("resorts_list", []).append(new_name)
    data.setdefault("season_blocks", {})[new_name] = {year: {} for year in YEARS}
    data.setdefault("reference_points", {})[new_name] = {}
    data.setdefault("holiday_weeks", {})[new_name] = {year: {} for year in YEARS}
    st.session_state.current_resort = new_name
    save_data()
    st.rerun()
def clone_resort(data: Dict, source: str, target: str):
    """Clone an existing resort."""
    snapshot_before_change()
    data.setdefault("resorts_list", []).append(target)
    season_blocks = data.get("season_blocks", {})
    ref_points = data.get("reference_points", {})
    holiday_weeks = data.get("holiday_weeks", {})
    data.setdefault("season_blocks", {})[target] = copy.deepcopy(
        season_blocks.get(source, {year: {} for year in YEARS})
    )
    data.setdefault("reference_points", {})[target] = copy.deepcopy(
        ref_points.get(source, {})
    )
    data.setdefault("holiday_weeks", {})[target] = copy.deepcopy(
        holiday_weeks.get(source, {year: {} for year in YEARS})
    )
    st.session_state.current_resort = target
    save_data()
    st.success(f"✅ Cloned **{source}** → **{target}**")
    st.rerun()
def handle_resort_deletion(data: Dict, current_resort: str):
    """Handle resort deletion with confirmation."""
    if not st.session_state.delete_confirm:
        if st.button("🗑️ Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.warning(f"⚠️ Are you sure you want to permanently delete **{current_resort}**?")
        col1, col2 = st.columns(2)
     
        with col1:
            if st.checkbox("I understand — this cannot be undone", key=f"delete_confirm_check_{current_resort}"):
                if st.button("🔥 DELETE FOREVER", key=f"delete_resort_final_{current_resort}", type="primary"):
                    delete_resort(data, current_resort)
                 
        with col2:
            if st.button("❌ Cancel", key=f"delete_cancel_{current_resort}"):
                st.session_state.delete_confirm = False
                st.rerun()
 
    if st.session_state.delete_confirm:
        st.stop()
def delete_resort(data: Dict, resort: str):
    """Delete a resort from all data structures."""
    snapshot_before_change()
    for category in ["season_blocks", "reference_points", "holiday_weeks"]:
        data.get(category, {}).pop(resort, None)
    data["resorts_list"].remove(resort)
    st.session_state.current_resort = None
    st.session_state.delete_confirm = False
    if resort in st.session_state.working_resorts:
        del st.session_state.working_resorts[resort]
    save_data()
    st.rerun()
# ----------------------------------------------------------------------
# SEASON MANAGEMENT
# ----------------------------------------------------------------------
def get_all_seasons(working: Dict) -> List[str]:
    """Get all unique seasons used across years and categories."""
    seasons: Set[str] = set()
    season_blocks = working.get("season_blocks", {})
    ref_points = working.get("reference_points", {})
    for year in YEARS:
        seasons.update(season_blocks.get(year, {}).keys())
    seasons.update(ref_points.keys())
    return sorted(seasons)
def handle_season_renaming(working: Dict):
    """Handle renaming of seasons."""
    st.subheader("🏷️ Rename Seasons")
    st.caption("Applies to all years & sections")
 
    seasons = get_all_seasons(working)
 
    for old_name in seasons:
        if old_name == HOLIDAY_SEASON_KEY:
            continue
         
        col1, col2 = st.columns([3, 1])
        with col1:
            new_name = st.text_input(f"Rename **{old_name}** →", value=old_name, key=f"rename_season_{old_name}")
        with col2:
            if st.button("Apply", key=f"apply_rename_season_{old_name}") and new_name != old_name and new_name:
                rename_season(working, old_name, new_name)
def rename_season(working: Dict, old_name: str, new_name: str):
    """Rename a season across all data structures."""
    if new_name == HOLIDAY_SEASON_KEY:
        st.error("❌ Cannot rename to reserved season name 'Holiday Week'")
        return
    # Update season blocks
    season_blocks = working.get("season_blocks", {})
    for year in YEARS:
        year_block = season_blocks.get(year, {})
        if old_name in year_block:
            year_block[new_name] = year_block.pop(old_name)
    # Update reference points only
    ref_points = working.get("reference_points", {})
    if old_name in ref_points:
        ref_points[new_name] = ref_points.pop(old_name)
    st.success(f"✅ Renamed **{old_name}** → **{new_name}**")
    st.rerun()
def handle_season_operations(working: Dict):
    """Handle adding and deleting seasons - ADDED confirmation."""
    st.subheader("➕➖ Add / Delete Season")
    seasons = get_all_seasons(working)
 
    col1, col2 = st.columns(2)
 
    with col1:
        new_season = st.text_input("New Season Name", key="new_season_input")
        if st.button("Add Season", key="add_season_btn") and new_season:
            if new_season.strip() and not any(s.lower() == new_season.lower() for s in seasons):
                add_season(working, new_season.strip())
            else:
                st.error("Season name already exists or is invalid")
 
    with col2:
        del_season = st.selectbox("Delete Season", [""] + seasons, key="del_season_select")
        if del_season:
            if st.button("Delete Season", key="delete_season_btn"):
                # Confirmation for destructive operation
                if st.session_state.get(f"confirm_delete_season_{del_season}"):
                    delete_season(working, del_season)
                    st.session_state[f"confirm_delete_season_{del_season}"] = False
                else:
                    st.session_state[f"confirm_delete_season_{del_season}"] = True
                    st.warning(f"Are you sure you want to delete season '{del_season}'?")
                    if st.button("Confirm Delete", key=f"confirm_del_season_{del_season}"):
                        delete_season(working, del_season)
                        st.session_state[f"confirm_delete_season_{del_season}"] = False
                        st.rerun()
def add_season(working: Dict, season: str):
    """Add a new season to all years and categories."""
    season = season.strip()
    if not season:
        st.error("Season name cannot be empty")
        return
    if season == HOLIDAY_SEASON_KEY:
        st.error("❌ Reserved season name 'Holiday Week' cannot be used")
        return
    season_blocks = working.setdefault("season_blocks", {})
    for year in YEARS:
        season_blocks.setdefault(year, {})[season] = []
    working.setdefault("reference_points", {})[season] = {}
    st.success(f"✅ Added **{season}**")
    st.rerun()
def delete_season(working: Dict, season: str):
    """Delete a season from all data structures."""
    season_blocks = working.get("season_blocks", {})
    for year in YEARS:
        season_blocks.get(year, {}).pop(season, None)
    ref_points = working.get("reference_points", {})
    ref_points.pop(season, None)
    st.success(f"✅ Deleted **{season}**")
    st.rerun()
# ----------------------------------------------------------------------
# ROOM TYPE MANAGEMENT
# ----------------------------------------------------------------------
def get_all_room_types(working: Dict) -> List[str]:
    """Get all unique room types used in the resort."""
    rooms: Set[str] = set()
    ref_points = working.get("reference_points", {})
    for season_data in ref_points.values():
        for day_or_room in season_data.values():
            if isinstance(day_or_room, dict):
                rooms.update(day_or_room.keys())
    return sorted(rooms)
def handle_room_renaming(working: Dict):
    """Handle renaming of room types with automatic Reference Points propagation."""
    st.subheader("🚪 Rename Room Types")
    st.caption("Applies everywhere including Reference Points")
 
    rooms = get_all_room_types(working)
 
    for old_room in rooms:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_room = st.text_input(f"Rename **{old_room}** →", value=old_room, key=f"rename_room_{old_room}")
        with col2:
            if st.button("Apply", key=f"apply_rename_room_{old_room}") and new_room != old_room and new_room:
                # Show confirmation for major changes
                if old_room in get_all_room_types(working): # Double-check it still exists
                    rename_room_type(working, old_room, new_room)
                else:
                    st.error("Room type no longer exists or was already renamed")
def rename_room_type(working: Dict, old_name: str, new_name: str):
    """Enhanced room renaming with comprehensive propagation to Reference Points."""
    new_name = new_name.strip()
    if not new_name:
        st.error("Room name cannot be empty")
        return
    if any(new_name.lower() == r.lower() for r in get_all_room_types(working)):
        st.error("❌ Room type name already exists (case-insensitive)")
        return
    changes_made = False
 
    # Update reference_points section
    section_name = "reference_points"
    section_data = working.get(section_name, {})
    section_changes = update_room_in_section(section_data, old_name, new_name)
    changes_made = changes_made or section_changes
 
    if changes_made:
        st.success(f"✅ Renamed **{old_name}** → **{new_name}** across all sections including Reference Points")
        st.rerun()
    else:
        st.error("❌ No changes made - room name not found or already updated")
def update_room_in_section(section_data: Dict, old_name: str, new_name: str) -> bool:
    """Update room name in a specific data section."""
    changes_made = False
 
    for season, season_data in section_data.items():
        for sub_name, sub_data in season_data.items():
            if isinstance(sub_data, dict) and old_name in sub_data:
                sub_data[new_name] = sub_data.pop(old_name)
                changes_made = True
 
    return changes_made
def handle_room_operations(working: Dict):
    """Handle adding and deleting room types - ADDED confirmation."""
    st.subheader("➕➖ Add / Delete Room Type")
    rooms = get_all_room_types(working)
 
    col1, col2 = st.columns(2)
 
    with col1:
        new_room = st.text_input("New Room Type", key="new_room_input")
        if st.button("Add Room Type", key="add_room_btn") and new_room:
            if new_room.strip() and not any(r.lower() == new_room.lower() for r in rooms):
                add_room_type(working, new_room.strip())
            else:
                st.error("Room type already exists or is invalid")
 
    with col2:
        del_room = st.selectbox("Delete Room Type", [""] + rooms, key="del_room_select")
        if del_room:
            if st.button("Delete Room", key="delete_room_btn"):
                # Confirmation for destructive operation
                if st.session_state.get(f"confirm_delete_room_{del_room}"):
                    delete_room_type(working, del_room)
                    st.session_state[f"confirm_delete_room_{del_room}"] = False
                else:
                    st.session_state[f"confirm_delete_room_{del_room}"] = True
                    st.warning(f"Are you sure you want to delete room type '{del_room}'?")
                    if st.button("Confirm Delete", key=f"confirm_del_room_{del_room}"):
                        delete_room_type(working, del_room)
                        st.session_state[f"confirm_delete_room_{del_room}"] = False
                        st.rerun()
def add_room_type(working: Dict, room: str):
    """Add a new room type with default points - improved schema enforcement."""
    room = room.strip()
    if not room:
        st.error("Room type name cannot be empty")
        return
     
    ref_points = working.get("reference_points", {})
    for season in ref_points:
        if season != HOLIDAY_SEASON_KEY:
            for day_type in DAY_TYPES:
                ref_points[season].setdefault(day_type, {})
                ref_points[season][day_type].setdefault(
                    room, DEFAULT_POINTS.get(day_type, 100)
                )
        else:
            for sub_season in ref_points[season]:
                if isinstance(ref_points[season][sub_season], dict):
                    ref_points[season][sub_season].setdefault(
                        room, DEFAULT_HOLIDAY_POINTS.get(room, 1500)
                    )
 
    st.success(f"✅ Added **{room}**")
    st.rerun()
def delete_room_type(working: Dict, room: str):
    """Delete a room type from all data structures - FIXED logic."""
    ref_points = working.get("reference_points", {})
    for season in ref_points:
        for day_type, value in ref_points[season].items():
            if isinstance(value, dict):
                value.pop(room, None)
 
    st.success(f"✅ Deleted **{room}**")
    st.rerun()
# ----------------------------------------------------------------------
# HOLIDAY MANAGEMENT
# ----------------------------------------------------------------------
def handle_holiday_management(working: Dict, resort: str, data: Dict):
    """Manage individual holiday weeks for a resort."""
    st.subheader("🎄 Manage Holiday Weeks")
    st.caption("Add or remove specific holiday weeks from reference points")
 
    ref_points = working.setdefault("reference_points", {})
    ref_points.setdefault(HOLIDAY_SEASON_KEY, {})
 
    # Get available holidays
    all_holidays = set()
    global_dates = data.setdefault("global_dates", {})
    for year in YEARS:
        all_holidays.update(global_dates.get(year, {}).keys())
    all_holidays = {h for h in all_holidays if h}
 
    current_holidays = set(ref_points.get(HOLIDAY_SEASON_KEY, {}).keys())
    available_to_add = sorted(list(all_holidays - current_holidays))
    current_active = sorted(list(current_holidays))
 
    if not all_holidays:
        st.warning("⚠️ No global holiday dates defined in Global Settings.")
        return
 
    # Display current active holidays
    if current_active:
        st.info(f"**Active Holidays:** {', '.join(current_active)}")
    else:
        st.info("No holiday weeks currently active. Use controls below to add.")
 
    col1, col2 = st.columns(2)
 
    with col1:
        render_holiday_removal(working, resort, current_active)
 
    with col2:
        render_holiday_addition(working, resort, available_to_add)
def render_holiday_removal(working: Dict, resort: str, current_holidays: List[str]):
    """Render holiday removal interface."""
    st.markdown("##### Remove Holiday Week")
    del_holiday = st.selectbox("Select Holiday to Remove", [""] + current_holidays, key=f"del_holiday_select_{resort}")
 
    if st.button("Remove Selected Holiday", key=f"remove_holiday_btn_{resort}", disabled=not del_holiday):
        remove_holiday(working, del_holiday)
def remove_holiday(working: Dict, holiday: str):
    """Remove a holiday from all data structures."""
    ref_points = working.get("reference_points", {})
    holiday_section = ref_points.get(HOLIDAY_SEASON_KEY, {})
    holiday_section.pop(holiday, None)
    holiday_weeks = working.get("holiday_weeks", {})
    for year in YEARS:
        holiday_weeks.get(year, {}).pop(holiday, None)
 
    st.success(f"✅ Removed **{holiday}**")
    st.rerun()
def render_holiday_addition(working: Dict, resort: str, available_holidays: List[str]):
    """Render holiday addition interface."""
    st.markdown("##### Add Holiday Week")
    add_holiday = st.selectbox("Select Holiday to Add", [""] + available_holidays, key=f"add_holiday_select_{resort}")
 
    if st.button("Add Selected Holiday", key=f"add_holiday_btn_{resort}", type="primary", disabled=not add_holiday):
        add_holiday_to_resort(working, add_holiday)
def add_holiday_to_resort(working: Dict, holiday: str):
    """Add a holiday to resort data structures with room sync."""
    rooms = get_all_room_types(working)
    holiday_data: Dict[str, int] = {}
    # Build holiday data from current rooms
    for room in rooms:
        holiday_data[room] = DEFAULT_HOLIDAY_POINTS.get(room, 1500)
 
    # If no rooms exist yet, use defaults but warn
    if not holiday_data:
        holiday_data = copy.deepcopy(DEFAULT_HOLIDAY_POINTS)
        st.warning(f"Used default room types for holiday '{holiday}'. Add rooms to resort first for better defaults.")
 
    # Add to reference points
    ref_points = working.setdefault("reference_points", {})
    ref_points.setdefault(HOLIDAY_SEASON_KEY, {})[holiday] = copy.deepcopy(holiday_data)
 
    # Add to holiday weeks for both years
    holiday_weeks = working.setdefault("holiday_weeks", {})
    for year in YEARS:
        holiday_weeks.setdefault(year, {})[holiday] = f"global:{holiday}"
 
    st.success(f"✅ Added **{holiday}**")
    if rooms:
        st.info(f"Remember to update holiday point values for {len(rooms)} room types")
    st.rerun()
# ----------------------------------------------------------------------
# SEASON DATES EDITOR
# ----------------------------------------------------------------------
def render_season_dates_editor(working: Dict, resort: str):
    """Edit season date ranges for each year."""
    st.subheader("📅 Season Dates")
 
    season_blocks = working.setdefault("season_blocks", {})
 
    for year in YEARS:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = season_blocks.setdefault(year, {})
            seasons = list(year_data.keys())
         
            # Add new season
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season = st.text_input(f"New season ({year})", key=f"ns_{resort}_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{resort}_{year}") and new_season:
                    add_season(working, new_season.strip())
         
            # Edit existing seasons
            for season_idx, season in enumerate(seasons):
                render_season_ranges(working, resort, year, season, season_idx)
def render_season_ranges(working: Dict, resort: str, year: str, season: str, season_idx: int):
    """Render date ranges for a specific season."""
    st.markdown(f"**{season}**")
    ranges = working["season_blocks"][year][season]
 
    for range_idx, (start_str, end_str) in enumerate(ranges):
        render_date_range(working, resort, year, season, season_idx, range_idx, start_str, end_str)
 
    # Add new range
    if st.button("+ Add Range", key=f"ar_{resort}_{year}_{season_idx}"):
        ranges.append([f"{year}-01-01", f"{year}-01-07"])
        st.rerun()
def render_date_range(working: Dict, resort: str, year: str, season: str,
                     season_idx: int, range_idx: int, start_str: str, end_str: str):
    """Render a single date range with edit/delete controls."""
    col1, col2, col3 = st.columns([3, 3, 1])
 
    with col1:
        new_start = st.date_input("Start", safe_date(start_str), key=f"ds_{resort}_{year}_{season_idx}_{range_idx}")
    with col2:
        new_end = st.date_input("End", safe_date(end_str), key=f"de_{resort}_{year}_{season_idx}_{range_idx}")
    with col3:
        if st.button("X", key=f"dx_{resort}_{year}_{season_idx}_{range_idx}"):
            working["season_blocks"][year][season].pop(range_idx)
            st.rerun()
 
    # Update if dates changed
    if new_start.isoformat() != start_str or new_end.isoformat() != end_str:
        working["season_blocks"][year][season][range_idx] = [new_start.isoformat(), new_end.isoformat()]
# ----------------------------------------------------------------------
# REFERENCE POINTS EDITOR
# ----------------------------------------------------------------------
def render_reference_points_editor(working: Dict, resort: str):
    """Edit reference points for seasons and room types."""
    st.subheader("🎯 Reference Points")
    ref_points = working.setdefault("reference_points", {})
 
    for season, content in ref_points.items():
        with st.expander(season, expanded=True):
            render_season_points(content, resort, season)
def render_season_points(content: Dict, resort: str, season: str):
    """Render points editor for a specific season - ADDED validation."""
    day_types = [k for k in content.keys() if k in DAY_TYPES]
    extra_keys = [k for k in content.keys() if k not in DAY_TYPES]
    has_extra_nested = any(isinstance(content[k], dict) for k in extra_keys)
    has_nested_dicts = any(isinstance(v, dict) for v in content.values())
    is_holiday_season = not day_types and has_nested_dicts
 
    # Warn about mixed schema
    if day_types and has_extra_nested:
        st.warning(f"⚠️ Season '{season}' has mixed data structure (day types + extra nested dicts)")
 
    if day_types:
        render_regular_season(content, resort, season, day_types)
    elif is_holiday_season:
        render_holiday_season(content, resort, season)
    else:
        st.warning(f"⚠️ Season '{season}' has unexpected data structure")
def render_regular_season(content: Dict, resort: str, season: str, day_types: List[str]):
    """Render points editor for regular seasons."""
    for day_type in day_types:
        st.write(f"**{day_type}**")
        rooms = content[day_type]
        cols = st.columns(4)
     
        for j, (room, points) in enumerate(rooms.items()):
            with cols[j % 4]:
                current_points = int(points)
                new_value = st.number_input(
                    room, value=current_points, step=25,
                    key=f"ref_{resort}_{season}_{day_type}_{room}_{j}"
                )
                if new_value != current_points:
                    rooms[room] = int(new_value)
def render_holiday_season(content: Dict, resort: str, season: str):
    """Render points editor for holiday seasons."""
    for sub_season, rooms in content.items():
        st.markdown(f"**{sub_season}**")
        cols = st.columns(4)
     
        for j, (room, points) in enumerate(rooms.items()):
            with cols[j % 4]:
                current_points = int(points)
                new_value = st.number_input(
                    room, value=current_points, step=25,
                    key=f"refhol_{resort}_{season}_{sub_season}_{room}_{j}"
                )
                if new_value != current_points:
                    rooms[room] = int(new_value)
# ----------------------------------------------------------------------
# GANTT CHART
# ----------------------------------------------------------------------
def create_gantt_chart(working: Dict, resort: str, year: int, data: Dict) -> go.Figure:
    """Create a Gantt chart for seasons and holidays."""
    rows = []
    year_str = str(year)
 
    # Add holidays
    holiday_dict = working.get("holiday_weeks", {}).get(year_str, {})
 
    for name, raw in holiday_dict.items():
        if isinstance(raw, str) and raw.startswith("global:"):
            holiday_name = raw.split(":", 1)[1]
            raw = data.get("global_dates", {}).get(year_str, {}).get(holiday_name, [])
        if isinstance(raw, list) and len(raw) >= 2:
            try:
                start_dt = datetime.strptime(raw[0], "%Y-%m-%d")
                end_dt = datetime.strptime(raw[1], "%Y-%m-%d")
                if start_dt < end_dt:
                    rows.append({
                        "Task": name,
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Type": "Holiday"
                    })
            except (ValueError, TypeError):
                pass
 
    # Add seasons
    season_dict = working.get("season_blocks", {}).get(year_str, {})
 
    for season_name, ranges in season_dict.items():
        for i, (start_str, end_str) in enumerate(ranges, 1):
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                if start_dt < end_dt:
                    rows.append({
                        "Task": f"{season_name} #{i}",
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Type": season_name
                    })
            except (ValueError, TypeError):
                continue
 
    # Handle no data case
    if not rows:
        today = datetime.now()
        rows.append({
            "Task": "No Data",
            "Start": today,
            "Finish": today + timedelta(days=1),
            "Type": "No Data"
        })
 
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
 
    # Colors
    color_palette = {
        "Holiday": "rgb(255,99,71)",
        "Low Season": "rgb(135,206,250)",
        "High Season": "rgb(255,69,0)",
        "Peak Season": "rgb(255,215,0)",
        "Shoulder": "rgb(50,205,50)",
        "Peak": "rgb(255,69,0)",
        "Summer": "rgb(255,165,0)",
        "Low": "rgb(70,130,180)",
        "Mid Season": "rgb(60,179,113)",
        "No Data": "rgb(128,128,128)"
    }
    color_map = {t: color_palette.get(t, "rgb(169,169,169)") for t in df["Type"].unique()}
 
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        color_discrete_map=color_map,
        title=f"{resort} – Seasons & Holidays ({year})",
        height=max(400, len(df) * 35)
    )
 
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Start: %{base|%d %b %Y}<br>"
            "End: %{x|%d %b %Y}<extra></extra>"
        )
    )
    fig.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="Period")
    return fig
def render_gantt_charts(working: Dict, resort: str, data: Dict):
    """Render Gantt charts for both years."""
    st.subheader("📊 Season & Holiday Timeline")
    tab2025, tab2026 = st.tabs(["2025", "2026"])
 
    with tab2025:
        st.plotly_chart(create_gantt_chart(working, resort, 2025, data), use_container_width=True)
    with tab2026:
        st.plotly_chart(create_gantt_chart(working, resort, 2026, data), use_container_width=True)
# ----------------------------------------------------------------------
# VALIDATION
# ----------------------------------------------------------------------
def validate_resort_data(working: Dict, data: Dict) -> List[str]:
    """Validate resort data and return list of issues."""
    issues: List[str] = []
    season_blocks = working.get("season_blocks", {})
    days_covered = {
        "Mon-Thu": {"Mon", "Tue", "Wed", "Thu"},
        "Fri-Sat": {"Fri", "Sat"},
        "Sun": {"Sun"},
        "Sun-Thu": {"Sun", "Mon", "Tue", "Wed", "Thu"}
    }
    all_days = set(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    # Check for overlapping season ranges and holidays
    for year in YEARS:
        season_ranges: List[Tuple[str, datetime, datetime]] = []
        season_data = season_blocks.get(year, {})
     
        for season_name, ranges in season_data.items():
            for start_str, end_str in ranges:
                try:
                    start = datetime.strptime(start_str, "%Y-%m-%d")
                    end = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)  # end inclusive for checks
                    season_ranges.append((season_name, start, end))
                except (ValueError, TypeError):
                    issues.append(f"Invalid date range in {year} {season_name}: {start_str} - {end_str}")
     
        season_ranges.sort(key=lambda x: x[1])
        for i in range(1, len(season_ranges)):
            prev_name, prev_start, prev_end = season_ranges[i-1]
            curr_name, curr_start, curr_end = season_ranges[i]
            if curr_start < prev_end:
                issues.append(f"Overlapping seasons in {year}: {prev_name} and {curr_name}")
 
        # Holiday ranges
        holiday_ranges: List[Tuple[str, datetime, datetime]] = []
        holiday_dict = working.get("holiday_weeks", {}).get(year, {})
        for name, raw in holiday_dict.items():
            if isinstance(raw, str) and raw.startswith("global:"):
                holiday_name = raw.split(":", 1)[1]
                raw = data.get("global_dates", {}).get(year, {}).get(holiday_name, [])
            if isinstance(raw, list) and len(raw) >= 2:
                try:
                    start = datetime.strptime(raw[0], "%Y-%m-%d")
                    end = datetime.strptime(raw[1], "%Y-%m-%d") + timedelta(days=1)
                    holiday_ranges.append((name, start, end))
                except (ValueError, TypeError):
                    issues.append(f"Invalid holiday date in {year} {name}: {raw}")
        holiday_ranges.sort(key=lambda x: x[1])
        for i in range(1, len(holiday_ranges)):
            prev_name, prev_start, prev_end = holiday_ranges[i-1]
            curr_name, curr_start, curr_end = holiday_ranges[i]
            if curr_start < prev_end:
                issues.append(f"Overlapping holidays in {year}: {prev_name} and {curr_name}")
 
        # Check cross overlaps (season and holiday)
        for s_name, s_start, s_end in season_ranges:
            for h_name, h_start, h_end in holiday_ranges:
                if max(s_start, h_start) < min(s_end, h_end):
                    issues.append(f"Overlap between season {s_name} and holiday {h_name} in {year}")
 
        # Check overall coverage (no gaps in union)
        all_ranges = season_ranges + holiday_ranges
        if all_ranges:
            all_ranges.sort(key=lambda x: x[1])
            merged_start = all_ranges[0][1]
            merged_end = all_ranges[0][2]
            for _, start, end in all_ranges[1:]:
                if start <= merged_end:  # merge adjacent or overlapping
                    merged_end = max(merged_end, end)
                else:
                    gap_start = merged_end
                    gap_end = start - timedelta(days=1)
                    issues.append(f"Gap in overall coverage in {year}: {gap_start.date()} to {gap_end.date()}")
                    merged_start = start
                    merged_end = end
            year_start = datetime(int(year), 1, 1)
            year_end = datetime(int(year), 12, 31) + timedelta(days=1)
            if merged_start > year_start:
                gap_start = year_start
                gap_end = merged_start - timedelta(days=1)
                issues.append(f"Gap at start of {year}: {gap_start.date()} to {gap_end.date()}")
            if merged_end < year_end:
                gap_start = merged_end
                gap_end = year_end - timedelta(days=1)
                issues.append(f"Gap at end of {year}: {gap_start.date()} to {gap_end.date()}")
        else:
            issues.append(f"No coverage at all for {year}")
 
    # Check for empty seasons
    all_seasons = get_all_seasons(working)
    ref_points = working.get("reference_points", {})
    for season in all_seasons:
        if season == HOLIDAY_SEASON_KEY:
            continue
        has_data = False
        for year in YEARS:
            if season_blocks.get(year, {}).get(season):
                has_data = True
                break
        if not has_data and season in ref_points:
            issues.append(f"Season '{season}' has reference points but no date ranges")
 
    # Check room consistency
    all_rooms = set(get_all_room_types(working))
    for season, season_content in ref_points.items():
        if season == HOLIDAY_SEASON_KEY:
            continue
        for day_type, rooms_dict in season_content.items():
            if isinstance(rooms_dict, dict):
                season_rooms = set(rooms_dict.keys())
                missing = all_rooms - season_rooms
                if missing:
                    issues.append(f"Season '{season}' missing rooms in {day_type}: {', '.join(sorted(missing))}")
 
    # Check holiday consistency
    if HOLIDAY_SEASON_KEY in ref_points:
        for holiday, room_data in ref_points[HOLIDAY_SEASON_KEY].items():
            if isinstance(room_data, dict):
                holiday_rooms = set(room_data.keys())
                missing = all_rooms - holiday_rooms
                if missing:
                    issues.append(f"Holiday '{holiday}' missing rooms: {', '.join(sorted(missing))}")
            else:
                issues.append(f"Invalid data structure for holiday '{holiday}'")
 
    # Check structural integrity for reference_points only
    for season, content in ref_points.items():
        if season == HOLIDAY_SEASON_KEY:
            for holiday, rooms in content.items():
                if not isinstance(rooms, dict):
                    issues.append(f"reference_points Holiday '{holiday}' invalid (not dict)")
        else:
            found_day_types = [k for k in content if k in DAY_TYPES]
            extra = [k for k in content if k not in DAY_TYPES]
            if extra:
                issues.append(f"reference_points Season '{season}' has extra keys: {', '.join(extra)}")
            for day, rooms in content.items():
                if day in DAY_TYPES and not isinstance(rooms, dict):
                    issues.append(f"reference_points Season '{season}' day '{day}' invalid (not dict)")
            # Check day coverage
            covered_days = set()
            for day_type in found_day_types:
                new_days = days_covered.get(day_type, set())
                overlap = covered_days & new_days
                if overlap:
                    issues.append(f"Overlapping days in Season '{season}': {', '.join(overlap)}")
                covered_days.update(new_days)
            if len(covered_days) != 7:
                missing_days = all_days - covered_days
                issues.append(f"Season '{season}' does not cover full week: missing {', '.join(missing_days)}")
 
    return issues
def render_validation_panel(working: Dict, data: Dict):
    """Render validation issues panel."""
    with st.expander("🔍 Validation Check", expanded=False):
        issues = validate_resort_data(working, data)
        if issues:
            st.error("Validation Issues Found:")
            for issue in issues:
                st.write(f"• {issue}")
        else:
            st.success("✓ No validation issues found")
# ----------------------------------------------------------------------
# GLOBAL SETTINGS
# ----------------------------------------------------------------------
def render_global_settings(data: Dict):
    """Render global settings for maintenance fees and holiday dates."""
    st.header("⚙️ Global Settings")
 
    with st.expander("💰 Maintenance Fees"):
        render_maintenance_fees(data)
 
    with st.expander("🎅 Holiday Dates"):
        render_holiday_dates_editor(data)
def render_maintenance_fees(data: Dict):
    """Edit maintenance fee rates."""
    rates = data.setdefault("maintenance_rates", {})
 
    for i, (year, rate) in enumerate(rates.items()):
        current_rate = float(rate)
        new_rate = st.number_input(
            year, value=current_rate, step=0.01, format="%.4f", key=f"mf_{i}"
        )
        if new_rate != current_rate:
            snapshot_before_change()
            rates[year] = float(new_rate)
            save_data()
def render_holiday_dates_editor(data: Dict):
    """Edit global holiday dates - IMPROVED defensive coding."""
    global_dates = data.setdefault("global_dates", {})
    for year in YEARS:
        st.write(f"**{year}**")
        # Defensive setdefault
        holidays = global_dates.setdefault(year, {})
     
        # Existing holidays
        for i, (name, dates) in enumerate(list(holidays.items())):
            render_holiday_date_range(data, year, name, dates, i)
     
        st.markdown("---")
        render_new_holiday_interface(data, year)
def render_holiday_date_range(data: Dict, year: str, name: str, dates: List, index: int):
    """Render a single holiday date range with delete option."""
    date_list = dates if isinstance(dates, list) else [None, None]
    start_str, end_str = date_list[0], date_list[1]
    st.markdown(f"*{name}*")
    col1, col2, col3 = st.columns([4, 4, 1])
    with col1:
        new_start = st.date_input(f"Start", safe_date(start_str), key=f"hs_{year}_{index}", label_visibility="collapsed")
    with col2:
        new_end = st.date_input(f"End", safe_date(end_str), key=f"he_{year}_{index}", label_visibility="collapsed")
    with col3:
        if st.button("Delete", key=f"del_h_{year}_{index}"):
            snapshot_before_change()
            del data["global_dates"][year][name]
            save_data()
            st.rerun()
    stored_start_iso = start_str if start_str else safe_date(start_str).isoformat()
    stored_end_iso = end_str if end_str else safe_date(end_str).isoformat()
    if new_start.isoformat() != stored_start_iso or new_end.isoformat() != stored_end_iso:
        snapshot_before_change()
        data["global_dates"][year][name] = [new_start.isoformat(), new_end.isoformat()]
        save_data()
def render_new_holiday_interface(data: Dict, year: str):
    """Render interface for adding new holidays."""
    new_name = st.text_input(f"New Holiday Name ({year})", key=f"nhn_{year}")
    col1, col2, col3 = st.columns([4, 4, 1])
    with col1:
        new_start = st.date_input("New Start Date", datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(), key=f"nhs_{year}")
    with col2:
        new_end = st.date_input("New End Date", datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(), key=f"nhe_{year}")
    with col3:
        if st.button("Add Holiday", key=f"add_h_{year}") and new_name and new_name not in data.get("global_dates", {}).get(year, {}):
            snapshot_before_change()
            data.setdefault("global_dates", {}).setdefault(year, {})[new_name] = [new_start.isoformat(), new_end.isoformat()]
            save_data()
            st.rerun()
# ----------------------------------------------------------------------
# REVERT FUNCTIONALITY
# ----------------------------------------------------------------------
def render_revert_controls():
    """Render revert controls in sidebar."""
    if st.session_state.change_history:
        st.sidebar.markdown("---")
        if st.sidebar.button("↶ Revert Last Change", help="Undo the last change"):
            revert_last_change()
# ----------------------------------------------------------------------
# HANDLE RESORT SWITCH
# ----------------------------------------------------------------------
def handle_resort_switch(data: Dict, current_resort: str, previous_resort: str):
    if previous_resort and previous_resort != current_resort:
        working_resorts = st.session_state.working_resorts
        if previous_resort in working_resorts:
            working = working_resorts[previous_resort]
            committed = {
                'season_blocks': data.get("season_blocks", {}).get(previous_resort, {year: {} for year in YEARS}),
                'reference_points': data.get("reference_points", {}).get(previous_resort, {}),
                'holiday_weeks': data.get("holiday_weeks", {}).get(previous_resort, {year: {} for year in YEARS})
            }
            if working != committed:
                st.warning(f"You have unsaved changes in {previous_resort}.")
                changed_sections = []
                for section in committed:
                    if working[section] != committed[section]:
                        changed_sections.append(section.replace('_', ' ').title())
                if changed_sections:
                    st.write("Changed sections: " + ', '.join(changed_sections))
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Save Changes"):
                        commit_working_to_data(data, working, previous_resort)
                        del working_resorts[previous_resort]
                        st.session_state.previous_resort = current_resort
                        st.rerun()
                with col2:
                    if st.button("Discard Changes"):
                        del working_resorts[previous_resort]
                        st.session_state.previous_resort = current_resort
                        st.rerun()
                with col3:
                    if st.button("Cancel Switch"):
                        st.session_state.current_resort = previous_resort
                        st.rerun()
                st.stop()
    st.session_state.previous_resort = current_resort
# ----------------------------------------------------------------------
# COMMIT WORKING TO DATA
# ----------------------------------------------------------------------
def commit_working_to_data(data: Dict, working: Dict, resort: str):
    snapshot_before_change()
    for section in ("season_blocks", "reference_points", "holiday_weeks"):
        data.setdefault(section, {})[resort] = copy.deepcopy(working.get(section, {}))
    save_data()
# ----------------------------------------------------------------------
# RENDER SAVE BUTTON FOR RESORT
# ----------------------------------------------------------------------
def render_save_button(data: Dict, working: Dict, resort: str):
    committed = {
        'season_blocks': data.get("season_blocks", {}).get(resort, {year: {} for year in YEARS}),
        'reference_points': data.get("reference_points", {}).get(resort, {}),
        'holiday_weeks': data.get("holiday_weeks", {}).get(resort, {year: {} for year in YEARS})
    }
    if working != committed:
        if st.button("💾 Save Resort Changes", type="primary"):
            commit_working_to_data(data, working, resort)
            del st.session_state.working_resorts[resort]
            st.rerun()
# ----------------------------------------------------------------------
# MERGE FROM ANOTHER FILE
# ----------------------------------------------------------------------
def handle_merge_from_another_file(data: Dict):
    st.sidebar.markdown("### Merge from Another File")
    merge_upload = st.sidebar.file_uploader(
        "Upload another data.json to merge",
        type="json",
        key="merge_uploader"
    )
 
    if merge_upload:
        try:
            merge_data = json.load(merge_upload)
            merge_resorts = merge_data.get("resorts_list", [])
            if merge_resorts:
                selected_resorts = st.sidebar.multiselect(
                    "Select resorts to merge (up to 2)",
                    merge_resorts,
                    max_selections=2,
                    key="selected_merge_resorts"
                )
                if selected_resorts and st.sidebar.button("Merge Selected Resorts"):
                    snapshot_before_change()
                    for resort in selected_resorts:
                        if resort in data["resorts_list"]:
                            st.sidebar.warning(f"Resort '{resort}' already exists. Skipping to avoid overwrite.")
                            continue
                        data["resorts_list"].append(resort)
                        for section in ["season_blocks", "reference_points", "holiday_weeks"]:
                            if resort in merge_data.get(section, {}):
                                data.setdefault(section, {})[resort] = copy.deepcopy(merge_data[section][resort])
                    save_data()
                    st.sidebar.success(f"✅ Merged {len(selected_resorts)} resorts")
                    st.rerun()
        except json.JSONDecodeError:
            st.sidebar.error("❌ Invalid JSON file uploaded.")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
# ----------------------------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------------------------
def main():
    """Main application function."""
    # Setup
    setup_page()
    initialize_session_state()
 
    # Sidebar
    with st.sidebar:
        st.markdown("<p class='big-font'>Marriott Editor</p>", unsafe_allow_html=True)
        handle_file_upload()
        if st.session_state.data:
            create_download_button(st.session_state.data)
            handle_file_verification()
            render_revert_controls()
            handle_merge_from_another_file(st.session_state.data)
        show_save_indicator()
 
    # Main content
    st.title("Marriott Data Editor")
    st.caption("Rename • Add • Delete • Sync — All in One Place")
 
    # Check if data is loaded
    if not st.session_state.data:
        st.info("📁 Upload your data.json file to start editing")
        return
 
    data = st.session_state.data
    resorts = data.get("resorts_list", [])
    current_resort = st.session_state.current_resort
    previous_resort = st.session_state.previous_resort
 
    # Resort grid
    render_resort_grid(resorts, current_resort)
 
    # Handle switch
    handle_resort_switch(data, current_resort, previous_resort)
 
    # Load or create working for current
    if current_resort:
        working_resorts = st.session_state.working_resorts
        if current_resort not in working_resorts:
            working_resorts[current_resort] = {
                'season_blocks': copy.deepcopy(data.get("season_blocks", {}).get(current_resort, {year: {} for year in YEARS})),
                'reference_points': copy.deepcopy(data.get("reference_points", {}).get(current_resort, {})),
                'holiday_weeks': copy.deepcopy(data.get("holiday_weeks", {}).get(current_resort, {year: {} for year in YEARS}))
            }
        working = working_resorts[current_resort]
 
    # Resort creation
    handle_resort_creation(data, resorts)
 
    # Resort-specific editing
    if current_resort:
        st.markdown(f"### **{current_resort}**")
     
        # Validation panel
        render_validation_panel(working, data)
     
        # Save button
        render_save_button(data, working, current_resort)
     
        # Resort deletion
        handle_resort_deletion(data, current_resort)
     
        # Gantt charts
        render_gantt_charts(working, current_resort, data)
 
        # Season dates editor
        render_season_dates_editor(working, current_resort)
     
        # Season management
        handle_season_renaming(working)
        handle_season_operations(working)
     
        # Room type management
        handle_room_renaming(working)
        handle_room_operations(working)
     
        # Holiday management
        handle_holiday_management(working, current_resort, data)
     
        # Reference points editor
        render_reference_points_editor(working, current_resort)
     
    # Global settings
    render_global_settings(data)
 
    # Footer
    st.markdown("""
    <div class='success-box'>
        SINGAPORE 5:09 PM +08 • ALL ISSUES FIXED • WITH VALIDATION
    </div>
    """, unsafe_allow_html=True)
# ----------------------------------------------------------------------
# RUN APPLICATION
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
