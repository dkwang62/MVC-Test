import streamlit as st
import json
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import plotly.express as px

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
        'editing_season': None,
        'editing_room': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

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

def fix_json(raw_data: Dict) -> Dict:
    """Ensure JSON data has proper structure with all required fields."""
    fixed = copy.deepcopy(raw_data)
    
    # Initialize missing top-level keys
    fixed.setdefault("season_blocks", {})
    fixed.setdefault("point_costs", {})
    fixed.setdefault("reference_points", {})
    fixed.setdefault("maintenance_rates", {"2025": 0.81, "2026": 0.86})
    fixed.setdefault("global_dates", {"2025": {}, "2026": {}})
    fixed.setdefault("holiday_weeks", {})
    
    # Ensure resorts_list exists and is sorted
    resorts = sorted(fixed.get("season_blocks", {}).keys())
    fixed["resorts_list"] = resorts
    
    # Initialize structure for each resort
    for resort in resorts:
        fixed["season_blocks"].setdefault(resort, {"2025": {}, "2026": {}})
        fixed["point_costs"].setdefault(resort, {})
        fixed["reference_points"].setdefault(resort, {})
        fixed["holiday_weeks"].setdefault(resort, {"2025": {}, "2026": {}})
        
        # Clean season blocks data
        for year in YEARS:
            season_data = fixed["season_blocks"][resort].setdefault(year, {})
            for season, ranges in list(season_data.items()):
                if not isinstance(ranges, list) or any(
                    not isinstance(r, (list, tuple)) or len(r) != 2 for r in ranges
                ):
                    season_data[season] = []
    
    return fixed

def save_data(data: Dict):
    """Save data to session state."""
    st.session_state.data = data

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
                fixed_data = fix_json(raw_data)
                st.session_state.data = fixed_data
                st.session_state.current_resort = None
                st.session_state.last_upload_sig = current_sig
                st.success(f"✅ Loaded {len(fixed_data['resorts_list'])} resorts")
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
            if st.button("Create Blank", key="create_blank_btn") and new_name and new_name not in resorts:
                create_blank_resort(data, new_name)
                
        with col2:
            if st.button("Clone Current", key="copy_current_btn", type="primary") and st.session_state.current_resort and new_name:
                clone_resort(data, st.session_state.current_resort, new_name, resorts)

def create_blank_resort(data: Dict, new_name: str):
    """Create a new blank resort."""
    data["resorts_list"].append(new_name)
    data["season_blocks"][new_name] = {year: {} for year in YEARS}
    data["point_costs"][new_name] = {}
    data["reference_points"][new_name] = {}
    data["holiday_weeks"][new_name] = {year: {} for year in YEARS}
    st.session_state.current_resort = new_name
    save_data(data)
    st.rerun()

def clone_resort(data: Dict, source: str, target: str, resorts: List[str]):
    """Clone an existing resort."""
    if target in resorts:
        st.error("❌ Resort name already exists")
        return
        
    data["resorts_list"].append(target)
    data["season_blocks"][target] = copy.deepcopy(data["season_blocks"].get(source, {year: {} for year in YEARS}))
    data["point_costs"][target] = copy.deepcopy(data["point_costs"].get(source, {}))
    data["reference_points"][target] = copy.deepcopy(data["reference_points"].get(source, {}))
    data["holiday_weeks"][target] = copy.deepcopy(data["holiday_weeks"].get(source, {year: {} for year in YEARS}))
    st.session_state.current_resort = target
    save_data(data)
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
            if st.checkbox("I understand — this cannot be undone", key="delete_confirm_check"):
                if st.button("🔥 DELETE FOREVER", key="delete_resort_final", type="primary"):
                    delete_resort(data, current_resort)
                    
        with col2:
            if st.button("❌ Cancel", key="delete_cancel"):
                st.session_state.delete_confirm = False
                st.rerun()
    
    if st.session_state.delete_confirm:
        st.stop()

def delete_resort(data: Dict, resort: str):
    """Delete a resort from all data structures."""
    for category in ["season_blocks", "point_costs", "reference_points", "holiday_weeks"]:
        data[category].pop(resort, None)
    data["resorts_list"].remove(resort)
    st.session_state.current_resort = None
    st.session_state.delete_confirm = False
    save_data(data)
    st.rerun()

# ----------------------------------------------------------------------
# SEASON MANAGEMENT
# ----------------------------------------------------------------------
def get_all_seasons(data: Dict, resort: str) -> List[str]:
    """Get all unique seasons used across years and categories."""
    seasons = set()
    for year in YEARS:
        seasons.update(data["season_blocks"][resort].get(year, {}).keys())
    seasons.update(data["point_costs"].get(resort, {}).keys())
    seasons.update(data["reference_points"].get(resort, {}).keys())
    return sorted(seasons)

def handle_season_renaming(data: Dict, resort: str):
    """Handle renaming of seasons."""
    st.subheader("🏷️ Rename Seasons")
    st.caption("Applies to all years & sections")
    
    seasons = get_all_seasons(data, resort)
    
    for old_name in seasons:
        if old_name == HOLIDAY_SEASON_KEY:
            continue
            
        col1, col2 = st.columns([3, 1])
        with col1:
            new_name = st.text_input(f"Rename **{old_name}** →", value=old_name, key=f"rename_season_{old_name}")
        with col2:
            if st.button("Apply", key=f"apply_rename_season_{old_name}") and new_name != old_name and new_name:
                rename_season(data, resort, old_name, new_name)

def rename_season(data: Dict, resort: str, old_name: str, new_name: str):
    """Rename a season across all data structures."""
    # Update season blocks
    for year in YEARS:
        if old_name in data["season_blocks"][resort].get(year, {}):
            data["season_blocks"][resort][year][new_name] = data["season_blocks"][resort][year].pop(old_name)
    
    # Update point costs and reference points
    for category in ["point_costs", "reference_points"]:
        if old_name in data[category].get(resort, {}):
            data[category][resort][new_name] = data[category][resort].pop(old_name)
    
    save_data(data)
    st.success(f"✅ Renamed **{old_name}** → **{new_name}**")
    st.rerun()

def handle_season_operations(data: Dict, resort: str):
    """Handle adding and deleting seasons."""
    st.subheader("➕➖ Add / Delete Season")
    seasons = get_all_seasons(data, resort)
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_season = st.text_input("New Season Name", key="new_season_input")
        if st.button("Add Season", key="add_season_btn") and new_season:
            add_season(data, resort, new_season)
    
    with col2:
        del_season = st.selectbox("Delete Season", [""] + seasons, key="del_season_select")
        if st.button("Delete Season", key="delete_season_btn") and del_season:
            delete_season(data, resort, del_season)

def add_season(data: Dict, resort: str, season: str):
    """Add a new season to all years and categories."""
    for year in YEARS:
        data["season_blocks"][resort].setdefault(year, {})[season] = []
    data["reference_points"].setdefault(resort, {})[season] = {}
    data["point_costs"].setdefault(resort, {})[season] = {}
    save_data(data)
    st.success(f"✅ Added **{season}**")
    st.rerun()

def delete_season(data: Dict, resort: str, season: str):
    """Delete a season from all data structures."""
    for year in YEARS:
        data["season_blocks"][resort].get(year, {}).pop(season, None)
    data["point_costs"].get(resort, {}).pop(season, None)
    data["reference_points"].get(resort, {}).pop(season, None)
    save_data(data)
    st.success(f"✅ Deleted **{season}**")
    st.rerun()

# ----------------------------------------------------------------------
# ROOM TYPE MANAGEMENT
# ----------------------------------------------------------------------
def get_all_room_types(data: Dict, resort: str) -> List[str]:
    """Get all unique room types used in the resort."""
    rooms = set()
    for category in [data["point_costs"].get(resort, {}), data["reference_points"].get(resort, {})]:
        for season_data in category.values():
            for day_or_room in season_data.values():
                if isinstance(day_or_room, dict):
                    rooms.update(day_or_room.keys())
    return sorted(rooms)

def handle_room_renaming(data: Dict, resort: str):
    """Handle renaming of room types."""
    st.subheader("🚪 Rename Room Types")
    st.caption("Applies everywhere")
    
    rooms = get_all_room_types(data, resort)
    
    for old_room in rooms:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_room = st.text_input(f"Rename **{old_room}** →", value=old_room, key=f"rename_room_{old_room}")
        with col2:
            if st.button("Apply", key=f"apply_rename_room_{old_room}") and new_room != old_room and new_room:
                rename_room_type(data, resort, old_room, new_room)

def rename_room_type(data: Dict, resort: str, old_name: str, new_name: str):
    """Rename a room type across all data structures."""
    for category in [data["point_costs"].get(resort, {}), data["reference_points"].get(resort, {})]:
        for season in category:
            for day_type in category[season]:
                if old_name in category[season][day_type]:
                    category[season][day_type][new_name] = category[season][day_type].pop(old_name)
    
    save_data(data)
    st.success(f"✅ Renamed **{old_name}** → **{new_name}**")
    st.rerun()

def handle_room_operations(data: Dict, resort: str):
    """Handle adding and deleting room types."""
    st.subheader("➕➖ Add / Delete Room Type")
    rooms = get_all_room_types(data, resort)
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_room = st.text_input("New Room Type", key="new_room_input")
        if st.button("Add Room Type", key="add_room_btn") and new_room:
            add_room_type(data, resort, new_room)
    
    with col2:
        del_room = st.selectbox("Delete Room Type", [""] + rooms, key="del_room_select")
        if st.button("Delete Room", key="delete_room_btn") and del_room:
            delete_room_type(data, resort, del_room)

def add_room_type(data: Dict, resort: str, room: str):
    """Add a new room type with default points."""
    for category in [data["reference_points"].get(resort, {}), data["point_costs"].get(resort, {})]:
        for season in category:
            for day_type in DAY_TYPES:
                if day_type in category[season]:
                    default_pts = DEFAULT_POINTS.get(day_type, 100)
                    category[season][day_type].setdefault(room, default_pts)
                else:
                    for sub_season_data in category[season].values():
                        if isinstance(sub_season_data, dict):
                            sub_season_data.setdefault(room, DEFAULT_POINTS["Mon-Thu"])
    
    save_data(data)
    st.success(f"✅ Added **{room}**")
    st.rerun()

def delete_room_type(data: Dict, resort: str, room: str):
    """Delete a room type from all data structures."""
    for category in [data["point_costs"].get(resort, {}), data["reference_points"].get(resort, {})]:
        for season in category:
            for day_type in category[season]:
                if isinstance(category[season][day_type], dict):
                    category[season][day_type].pop(room, None)
                else:
                    category[season].pop(room, None)
    
    save_data(data)
    st.success(f"✅ Deleted **{room}**")
    st.rerun()

# ----------------------------------------------------------------------
# HOLIDAY MANAGEMENT
# ----------------------------------------------------------------------
def handle_holiday_management(data: Dict, resort: str):
    """Manage individual holiday weeks for a resort."""
    st.subheader("🎄 Manage Holiday Weeks")
    st.caption("Add or remove specific holiday weeks from reference points")
    
    ref_points = data["reference_points"].setdefault(resort, {})
    ref_points.setdefault(HOLIDAY_SEASON_KEY, {})
    
    # Get available holidays
    all_holidays = set()
    for year in YEARS:
        all_holidays.update(data["global_dates"].get(year, {}).keys())
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
        render_holiday_removal(data, resort, current_active)
    
    with col2:
        render_holiday_addition(data, resort, available_to_add)

def render_holiday_removal(data: Dict, resort: str, current_holidays: List[str]):
    """Render holiday removal interface."""
    st.markdown("##### Remove Holiday Week")
    del_holiday = st.selectbox("Select Holiday to Remove", [""] + current_holidays, key="del_holiday_select")
    
    if st.button("Remove Selected Holiday", key="remove_holiday_btn", disabled=not del_holiday):
        remove_holiday(data, resort, del_holiday)

def remove_holiday(data: Dict, resort: str, holiday: str):
    """Remove a holiday from all data structures."""
    data["reference_points"][resort].get(HOLIDAY_SEASON_KEY, {}).pop(holiday, None)
    data["point_costs"][resort].get(HOLIDAY_SEASON_KEY, {}).pop(holiday, None)
    
    for year in YEARS:
        data["holiday_weeks"][resort].get(year, {}).pop(holiday, None)
    
    save_data(data)
    st.success(f"✅ Removed **{holiday}**")
    st.rerun()

def render_holiday_addition(data: Dict, resort: str, available_holidays: List[str]):
    """Render holiday addition interface."""
    st.markdown("##### Add Holiday Week")
    add_holiday = st.selectbox("Select Holiday to Add", [""] + available_holidays, key="add_holiday_select")
    
    if st.button("Add Selected Holiday", key="add_holiday_btn", type="primary", disabled=not add_holiday):
        add_holiday_to_resort(data, resort, add_holiday)

def add_holiday_to_resort(data: Dict, resort: str, holiday: str):
    """Add a holiday to resort data structures."""
    rooms = get_all_room_types(data, resort)
    holiday_data = {}
    
    for room in rooms:
        holiday_data[room] = DEFAULT_HOLIDAY_POINTS.get(room, 1500)
    
    if not holiday_data:
        holiday_data = copy.deepcopy(DEFAULT_HOLIDAY_POINTS)
    
    # Add to reference points and point costs
    data["reference_points"][resort].setdefault(HOLIDAY_SEASON_KEY, {})[holiday] = copy.deepcopy(holiday_data)
    data["point_costs"][resort].setdefault(HOLIDAY_SEASON_KEY, {})[holiday] = copy.deepcopy(holiday_data)
    
    # Add to holiday weeks for both years
    for year in YEARS:
        data["holiday_weeks"][resort].setdefault(year, {})[holiday] = f"global:{holiday}"
    
    save_data(data)
    st.success(f"✅ Added **{holiday}**")
    st.rerun()

# ----------------------------------------------------------------------
# SEASON DATES EDITOR
# ----------------------------------------------------------------------
def render_season_dates_editor(data: Dict, resort: str):
    """Edit season date ranges for each year."""
    st.subheader("📅 Season Dates")
    
    for year in YEARS:
        with st.expander(f"{year} Seasons", expanded=True):
            year_data = data["season_blocks"][resort].setdefault(year, {})
            seasons = list(year_data.keys())
            
            # Add new season
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season = st.text_input(f"New season ({year})", key=f"ns_{year}")
            with col2:
                if st.button("Add", key=f"add_s_{year}") and new_season and new_season not in year_data:
                    year_data[new_season] = []
                    save_data(data)
                    st.rerun()
            
            # Edit existing seasons
            for season_idx, season in enumerate(seasons):
                render_season_ranges(data, resort, year, season, season_idx)

def render_season_ranges(data: Dict, resort: str, year: str, season: str, season_idx: int):
    """Render date ranges for a specific season."""
    st.markdown(f"**{season}**")
    ranges = data["season_blocks"][resort][year][season]
    
    for range_idx, (start_str, end_str) in enumerate(ranges):
        render_date_range(data, resort, year, season, season_idx, range_idx, start_str, end_str)
    
    # Add new range
    if st.button("+ Add Range", key=f"ar_{year}_{season_idx}"):
        ranges.append([f"{year}-01-01", f"{year}-01-07"])
        save_data(data)
        st.rerun()

def render_date_range(data: Dict, resort: str, year: str, season: str, 
                     season_idx: int, range_idx: int, start_str: str, end_str: str):
    """Render a single date range with edit/delete controls."""
    col1, col2, col3 = st.columns([3, 3, 1])
    
    with col1:
        new_start = st.date_input("Start", safe_date(start_str), key=f"ds_{year}_{season_idx}_{range_idx}")
    with col2:
        new_end = st.date_input("End", safe_date(end_str), key=f"de_{year}_{season_idx}_{range_idx}")
    with col3:
        if st.button("X", key=f"dx_{year}_{season_idx}_{range_idx}"):
            data["season_blocks"][resort][year][season].pop(range_idx)
            save_data(data)
            st.rerun()
    
    # Update if dates changed
    if new_start.isoformat() != start_str or new_end.isoformat() != end_str:
        data["season_blocks"][resort][year][season][range_idx] = [new_start.isoformat(), new_end.isoformat()]
        save_data(data)

# ----------------------------------------------------------------------
# REFERENCE POINTS EDITOR
# ----------------------------------------------------------------------
def render_reference_points_editor(data: Dict, resort: str):
    """Edit reference points for seasons and room types."""
    st.subheader("🎯 Reference Points")
    ref_points = data["reference_points"].setdefault(resort, {})
    
    for season, content in ref_points.items():
        with st.expander(season, expanded=True):
            render_season_points(content, resort, season)

def render_season_points(content: Dict, resort: str, season: str):
    """Render points editor for a specific season."""
    day_types = [k for k in content.keys() if k in DAY_TYPES]
    is_holiday_season = not day_types and all(isinstance(v, dict) for v in content.values())
    
    if day_types:
        render_regular_season(content, resort, season, day_types)
    elif is_holiday_season:
        render_holiday_season(content, resort, season)

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
                    save_data(st.session_state.data)

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
                    save_data(st.session_state.data)

# ----------------------------------------------------------------------
# GANTT CHART
# ----------------------------------------------------------------------
def create_gantt_chart(resort: str, year: int) -> px.timeline:
    """Create a Gantt chart for seasons and holidays."""
    rows = []
    year_str = str(year)
    
    # Add holidays
    add_holidays_to_gantt(rows, resort, year_str)
    
    # Add seasons
    add_seasons_to_gantt(rows, resort, year_str)
    
    # Handle no data case
    if not rows:
        today = datetime.now()
        rows.append({
            "Task": "No Data",
            "Start": today,
            "Finish": today + timedelta(days=1),
            "Type": "No Data"
        })
    
    return create_plotly_chart(rows, resort, year)

def add_holidays_to_gantt(rows: List[Dict], resort: str, year: str):
    """Add holiday periods to Gantt chart data."""
    holiday_dict = st.session_state.data["holiday_weeks"].get(resort, {}).get(year, {})
    
    for name, raw in holiday_dict.items():
        dates = resolve_holiday_dates(raw, year)
        if dates and dates[0] < dates[1]:
            rows.append({
                "Task": name,
                "Start": dates[0],
                "Finish": dates[1],
                "Type": "Holiday"
            })

def resolve_holiday_dates(raw: Any, year: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Resolve holiday dates from various formats."""
    if isinstance(raw, str) and raw.startswith("global:"):
        holiday_name = raw.split(":", 1)[1]
        raw = st.session_state.data["global_dates"].get(year, {}).get(holiday_name, [])
    
    if isinstance(raw, list) and len(raw) >= 2:
        try:
            start_dt = datetime.strptime(raw[0], "%Y-%m-%d")
            end_dt = datetime.strptime(raw[1], "%Y-%m-%d")
            return start_dt, end_dt
        except (ValueError, TypeError):
            pass
    
    return None, None

def add_seasons_to_gantt(rows: List[Dict], resort: str, year: str):
    """Add season periods to Gantt chart data."""
    season_dict = st.session_state.data["season_blocks"].get(resort, {}).get(year, {})
    
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

def create_plotly_chart(rows: List[Dict], resort: str, year: int) -> px.timeline:
    """Create the Plotly timeline chart."""
    df = pd.DataFrame(rows)
    df["Start"] = pd.to_datetime(df["Start"])
    df["Finish"] = pd.to_datetime(df["Finish"])
    
    color_map = create_color_mapping(df["Type"].unique())
    
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
    
    configure_chart_layout(fig)
    return fig

def create_color_mapping(types: List[str]) -> Dict[str, str]:
    """Create color mapping for Gantt chart types."""
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
    return {t: color_palette.get(t, "rgb(169,169,169)") for t in types}

def configure_chart_layout(fig: px.timeline):
    """Configure Plotly chart layout and hover behavior."""
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Start: %{base|%d %b %Y}<br>"
            "End:   %{x|%d %b %Y}<extra></extra>"
        )
    )
    fig.update_layout(showlegend=True, xaxis_title="Date", yaxis_title="Period")

def render_gantt_charts(resort: str):
    """Render Gantt charts for both years."""
    st.subheader("📊 Season & Holiday Timeline")
    tab2025, tab2026 = st.tabs(["2025", "2026"])
    
    with tab2025:
        st.plotly_chart(create_gantt_chart(resort, 2025), use_container_width=True)
    with tab2026:
        st.plotly_chart(create_gantt_chart(resort, 2026), use_container_width=True)

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
            rates[year] = float(new_rate)
            save_data(data)

def render_holiday_dates_editor(data: Dict):
    """Edit global holiday dates."""
    for year in YEARS:
        st.write(f"**{year}**")
        holidays = data["global_dates"].get(year, {})
        
        # Existing holidays
        for i, (name, dates) in enumerate(holidays.items()):
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
            del holidays[name]
            save_data(data)
            st.rerun()

    stored_start_iso = start_str if start_str else safe_date(start_str).isoformat()
    stored_end_iso = end_str if end_str else safe_date(end_str).isoformat()
    if new_start.isoformat() != stored_start_iso or new_end.isoformat() != stored_end_iso:
        data["global_dates"][year][name] = [new_start.isoformat(), new_end.isoformat()]
        save_data(data)

def render_new_holiday_interface(data: Dict, year: str):
    """Render interface for adding new holidays."""
    new_name = st.text_input(f"New Holiday Name ({year})", key=f"nhn_{year}")
    col1, col2, col3 = st.columns([4, 4, 1])
    with col1:
        new_start = st.date_input("New Start Date", datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(), key=f"nhs_{year}")
    with col2:
        new_end = st.date_input("New End Date", datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(), key=f"nhe_{year}")
    with col3:
        if st.button("Add Holiday", key=f"add_h_{year}") and new_name and new_name not in data["global_dates"][year]:
            data["global_dates"][year][new_name] = [new_start.isoformat(), new_end.isoformat()]
            save_data(data)
            st.rerun()

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
    
    # Main content
    st.title("Marriott Data Editor")
    st.caption("Rename • Add • Delete • Sync — All in One Place")
    
    # Check if data is loaded
    if not st.session_state.data:
        st.info("📁 Upload your data.json file to start editing")
        return
    
    data = st.session_state.data
    resorts = data["resorts_list"]
    current_resort = st.session_state.current_resort
    
    # Resort grid
    render_resort_grid(resorts, current_resort)
    
    # Resort creation
    handle_resort_creation(data, resorts)
    
    # Resort-specific editing
    if current_resort:
        st.markdown(f"### **{current_resort}**")
        
        # Resort deletion
        handle_resort_deletion(data, current_resort)
        
        # Season management
        handle_season_renaming(data, current_resort)
        handle_season_operations(data, current_resort)
        
        # Room type management
        handle_room_renaming(data, current_resort)
        handle_room_operations(data, current_resort)
        
        # Holiday management
        handle_holiday_management(data, current_resort)
        
        # Season dates editor
        render_season_dates_editor(data, current_resort)
        
        # Reference points editor
        render_reference_points_editor(data, current_resort)
        
        # Gantt charts
        render_gantt_charts(current_resort)
    
    # Global settings
    render_global_settings(data)
    
    # Footer
    st.markdown("""
    <div class='success-box'>
        SINGAPORE 5:09 PM +08 • FINAL CODE • ALL SYNTAX ERRORS FIXED
    </div>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# RUN APPLICATION
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
