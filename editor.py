import streamlit as st
from common.ui import setup_page, render_resort_card
from common.data import load_data, save_data
from common.utils import sort_resorts_west_to_east
from functools import lru_cache
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import copy
import re                     # ← ADD THIS
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Set

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
DEFAULT_YEARS = ["2025", "2026"]
BASE_YEAR_FOR_POINTS = "2025"

# ----------------------------------------------------------------------
# TIMEZONE SORTING HELPERS (UPDATED FOR WEST TO EAST)
# ----------------------------------------------------------------------
COMMON_TZ_ORDER = [
    "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles", "America/Denver",
    "America/Chicago", "America/New_York", "America/Vancouver", "America/Edmonton",
    "America/Winnipeg", "America/Toronto", "America/Halifax", "America/St_Johns",
    "US/Hawaii", "US/Alaska", "US/Pacific", "US/Mountain", "US/Central", "US/Eastern",
    "America/Aruba", "America/St_Thomas", "Asia/Denpasar",  # Added for Aruba, Virgin Islands, Bali
]

TZ_TO_REGION = {
    "Pacific/Honolulu": "Hawaii",
    "US/Hawaii": "Hawaii",
    "America/Anchorage": "Alaska",
    "US/Alaska": "Alaska",
    "America/Los_Angeles": "West Coast",
    "US/Pacific": "West Coast",
    "America/Denver": "Mountain",
    "US/Mountain": "Mountain",
    "America/Chicago": "Central",
    "US/Central": "Central",
    "America/New_York": "East Coast",
    "US/Eastern": "East Coast",
    "America/Aruba": "Caribbean",
    "America/St_Thomas": "Caribbean",
    "Asia/Denpasar": "Bali/Indonesia",
    # Add more as needed
}

def get_timezone_offset(tz_name: str) -> float:
    """Return UTC offset in hours (negative for west of UTC)"""
    try:
        tz = pytz.timezone(tz_name)
        dt = datetime(2025, 1, 1)
        return tz.utcoffset(dt).total_seconds() / 3600
    except:
        return 0

def get_region_label(tz: str) -> str:
    return TZ_TO_REGION.get(tz, tz.split("/")[-1] if "/" in tz else tz)

def sort_resorts_west_to_east(resorts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort resorts West → East using timezone offset, then address"""
    def sort_key(r):
        tz = r.get("timezone", "UTC")
        if tz in COMMON_TZ_ORDER:
            priority = COMMON_TZ_ORDER.index(tz)  # Lower index for West
        else:
            priority = 1000  # Unknown to end
        
        offset = get_timezone_offset(tz)
        address = (r.get("address") or r.get("resort_name") or r.get("display_name") or "").lower()
        return (priority, offset, address)
    
    return sorted(resorts, key=sort_key)

# ----------------------------------------------------------------------
# WIDGET KEY HELPER (RESORT-SCOPED)
# ----------------------------------------------------------------------
@lru_cache(maxsize=1024)
def rk(resort_id: str, *parts: str) -> str:
    """Build a unique Streamlit widget key scoped to a resort."""
    safe_resort = resort_id or "resort"
    return "__".join([safe_resort] + [str(p) for p in parts])

# ----------------------------------------------------------------------
# PAGE CONFIG & ENHANCED STYLES
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(
        page_title="MVC Resort Editor V2",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'About': "MVC Resort Editor V2 - Professional Resort Management System"
        }
    )
    st.markdown("""
    <style>
        html, body, .main, [data-testid="stAppViewContainer"] {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            color: var(--text-color);
        }
        :root {
            --primary-color: #008080;
            --secondary-color: #556B2F;
            --danger-color: #C0392B;
            --warning-color: #E67E22;
            --success-color: #27AE60;
            --text-color: #34495E;
            --bg-color: #F8F9FA;
            --card-bg: #FFFFFF;
            --border-color: #EAECEE;
        }
        .main {
            background-color: var(--bg-color);
        }
        .big-font {
            font-size: 32px !important;
            font-weight: 600;
            color: var(--text-color);
            border-bottom: 2px solid var(--primary-color);
            text-align: left;
            padding: 10px 0 15px 0;
            margin-bottom: 20px;
        }
        .card {
            background: var(--card-bg);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border: none;
            transition: all 0.2s ease;
        }
        .card:hover {
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.10);
            transform: translateY(-1px);
        }
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
            padding: 0.5rem 1.2rem;
            transition: all 0.2s ease;
            border: 1px solid var(--border-color);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(0,0,0,0.1);
        }
        .stButton [data-testid="baseButton-primary"] {
            background-color: var(--primary-color) !important;
            color: white !important;
            border: 1px solid var(--primary-color) !important;
        }
        .stButton [data-testid="baseButton-primary"]:hover {
            background-color: #006666 !important;
        }
        .success-box {
            background: #E8F8F5;
            color: var(--primary-color);
            padding: 16px;
            border-radius: 8px;
            margin: 20px 0;
            font-weight: 600;
            text-align: center;
            font-size: 15px;
            border: 1px solid #C0DEDD;
            box-shadow: none;
        }
        .section-header {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-color);
            padding: 10px 0;
            border-bottom: 2px solid var(--border-color);
            margin-bottom: 20px;
        }
        .info-box {
            background: #EBF5FB;
            border-left: 4px solid #3498DB;
            color: var(--text-color);
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .warning-box {
            background: #FEF9E7;
            border-left: 4px solid #F39C12;
            color: var(--text-color);
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .error-box {
            background: #FADBD8;
            border-left: 4px solid #C0392B;
            color: var(--text-color);
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }
        .streamlit-expanderHeader {
            background: var(--card-bg);
            border-radius: 6px;
            font-weight: 600;
            padding: 10px 15px;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            transition: background 0.2s;
        }
        .streamlit-expanderHeader:hover {
            background: #F4F6F6;
        }
        section[data-testid="stSidebar"] {
            background-color: var(--card-bg);
            box-shadow: 2px 0 10px rgba(0,0,0,0.05);
            border-right: 1px solid var(--border-color);
        }
        section[data-testid="stSidebar"] * {
            color: var(--text-color) !important;
        }
        section[data-testid="stSidebar"] h2 {
            color: var(--primary-color) !important;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] .streamlit-expanderHeader {
            background: #F4F6F6;
            border: 1px solid var(--border-color);
            color: var(--text-color) !important;
            font-weight: 500;
            margin: 4px 0;
        }
        section[data-testid="stSidebar"] .stButton>button {
            background: #ECF0F1;
            color: var(--text-color) !important;
            border: 1px solid var(--border-color);
            box-shadow: none;
        }
        section[data-testid="stSidebar"] .stDownloadButton>button {
            background: var(--primary-color) !important;
            color: white !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] .stDownloadButton>button * {
            color: white !important;
        }
        section[data-testid="stSidebar"] .stFileUploader {
            background: var(--card-bg) !important;
            padding: 0 !important;
            margin: 10px 0 !important;
            border: none !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFileUploadDropzone"] {
            border: 1px dashed var(--border-color) !important;
            background: #FAFAFA !important;
        }
        .metric-card {
            background: #ECF0F1 !important;
            border-radius: 8px;
            padding: 15px;
            box-shadow: none;
            border: 1px solid var(--border-color);
        }
        .metric-card * {
            color: var(--text-color) !important;
        }
        .metric-value {
            color: var(--primary-color) !important;
            font-size: 28px;
        }
        .metric-label {
            color: #64748b !important;
            font-size: 13px;
            font-weight: 500;
            margin-top: 5px;
        }
        div[data-testid="column"] .stButton [data-testid="baseButton-secondary"] {
            border: 1px solid var(--border-color);
            background: var(--card-bg);
            color: var(--text-color) !important;
        }
        .dataframe {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 6px 6px 0 0;
            padding: 10px 20px;
            font-weight: 500;
        }
        .stNumberInput>div>div>input,
        .stTextInput>div>div>input,
        .stDateInput>div>div>input,
        .stSelectbox>div>div,
        .stMultiSelect>div>div {
            border-radius: 6px;
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
            transition: border-color 0.2s;
        }
        .stNumberInput:focus-within>div>div>input,
        .stTextInput:focus-within>div>div>input,
        .stDateInput:focus-within>div>div>input,
        .stSelectbox:focus-within>div>div,
        .stMultiSelect:focus-within>div>div {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 1px var(--primary-color);
        }
    </style>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# ----------------------------------------------------------------------
def initialize_session_state():
    defaults = {
        'refresh_trigger': False,
        'last_upload_sig': None,
        'data': None,
        'current_resort_id': None,
        'previous_resort_id': None,
        'working_resorts': {},
        'last_save_time': None,
        'delete_confirm': False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def save_data():
    st.session_state.last_save_time = datetime.now()

def show_save_indicator():
    if st.session_state.last_save_time:
        elapsed = (datetime.now() - st.session_state.last_save_time).total_seconds()
        if elapsed < 3:
            st.sidebar.markdown("""
                <div style='background: #4caf50; color: white; padding: 12px; border-radius: 8px; text-align: center; font-weight: 600;'>
                    ✓ Changes Saved
                </div>
            """, unsafe_allow_html=True)

def reset_state_for_new_file():
    for k in ["data", "current_resort_id", "previous_resort_id",
              "working_resorts", "delete_confirm", "last_save_time"]:
        st.session_state[k] = {} if k == "working_resorts" else None

# ----------------------------------------------------------------------
# BASIC RESORT NAME / TIMEZONE HELPERS
# ----------------------------------------------------------------------
def detect_timezone_from_name(name: str) -> str:
    """Simple placeholder timezone detector; keep as UTC or customise later."""
    return "UTC"

def get_resort_full_name(resort_id: str, display_name: str) -> str:
    """For new resorts, treat display_name as full resort name."""
    return display_name

# ----------------------------------------------------------------------
# OPTIMIZED HELPER FUNCTIONS
# ----------------------------------------------------------------------
@lru_cache(maxsize=128)
def get_years_from_data_cached(data_hash: int) -> Tuple[str, ...]:
    """Cached version of get_years_from_data"""
    return tuple(sorted(get_years_from_data(st.session_state.data)))

def get_years_from_data(data: Dict[str, Any]) -> List[str]:
    """Derive list of years from global_holidays or resort years."""
    years: Set[str] = set()
    gh = data.get("global_holidays", {})
    years.update(gh.keys())
    for r in data.get("resorts", []):
        years.update(str(y) for y in r.get("years", {}).keys())
    return sorted(years) if years else DEFAULT_YEARS

def safe_date(d: Optional[str], default: str = "2025-01-01") -> date:
    if not d or not isinstance(d, str):
        return datetime.strptime(default, "%Y-%m-%d").date()
    try:
        return datetime.strptime(d.strip(), "%Y-%m-%d").date()
    except ValueError:
        return datetime.strptime(default, "%Y-%m-%d").date()

def get_resort_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return data.get("resorts", [])

def find_resort_by_id(data: Dict[str, Any], rid: str) -> Optional[Dict[str, Any]]:
    return next((r for r in data.get("resorts", []) if r.get("id") == rid), None)

def find_resort_index(data: Dict[str, Any], rid: str) -> Optional[int]:
    return next((i for i, r in enumerate(data.get("resorts", [])) if r.get("id") == rid), None)

def generate_resort_id(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.strip().lower())
    return re.sub(r'-+', '-', slug).strip('-') or "resort"

def generate_resort_code(name: str) -> str:
    parts = [p for p in name.replace("'", "'").split() if p]
    return "".join(p[0].upper() for p in parts[:3]) or "RST"

def make_unique_resort_id(base_id: str, resorts: List[Dict[str, Any]]) -> str:
    existing = {r.get("id") for r in resorts}
    if base_id not in existing:
        return base_id
    i = 2
    while f"{base_id}-{i}" in existing:
        i += 1
    return f"{base_id}-{i}"

# ----------------------------------------------------------------------
# FILE OPERATIONS WITH ENHANCED UI
# ----------------------------------------------------------------------
def handle_file_upload():
    st.sidebar.markdown("### 📤 Upload Data")
    with st.sidebar.expander("📤 Upload JSON file", expanded=False):
        uploaded = st.file_uploader(
            "Choose JSON file",
            type="json",
            key="file_uploader",
            help="Upload your MVC data file"
        )
        if uploaded:
            size = getattr(uploaded, "size", 0)
            current_sig = f"{uploaded.name}:{size}"
            if current_sig != st.session_state.last_upload_sig:
                try:
                    raw_data = json.load(uploaded)
                    if "schema_version" not in raw_data or not raw_data.get("resorts"):
                        st.error("❌ Invalid file format")
                        return
                    reset_state_for_new_file()
                    st.session_state.data = raw_data
                    st.session_state.last_upload_sig = current_sig
                    resorts_list = get_resort_list(raw_data)
                    st.success(f"✅ Loaded {len(resorts_list)} resorts")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

def create_download_button_v2(data: Dict[str, Any]):
    st.sidebar.markdown("### 📥 Save Data")
    json_data = json.dumps(data, indent=2, ensure_ascii=False)
    st.sidebar.download_button(
        label="💾 Save",
        data=json_data,
        file_name="data_v2.json",
        mime="application/json",
        key="download_v2_btn",
        use_container_width=True
    )

def handle_file_verification():
    with st.sidebar.expander("🔍 Verify File", expanded=False):
        verify_upload = st.file_uploader(
            "Verify",
            type="json",
            key="verify_uploader"
        )
        if verify_upload:
            try:
                uploaded_data = json.load(verify_upload)
                current_json = json.dumps(st.session_state.data, sort_keys=True)
                uploaded_json = json.dumps(uploaded_data, sort_keys=True)
                if current_json == uploaded_json:
                    st.success("✅ Files match")
                else:
                    st.error("❌ Files differ")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        st.sidebar.markdown("### 📥 Merge Data")

def handle_merge_from_another_file_v2(data: Dict[str, Any]):
    with st.sidebar.expander("🔀 Merge", expanded=False):
        merge_upload = st.file_uploader(
            "Upload to merge resorts",
            type="json",
            key="merge_uploader_v2"
        )
        if merge_upload:
            try:
                merge_data = json.load(merge_upload)
                if "resorts" not in merge_data:
                    st.error("❌ Invalid V2 schema")
                    return
                target_resorts = data.setdefault("resorts", [])
                existing_ids = {r.get("id") for r in target_resorts}
                merge_resorts = merge_data.get("resorts", [])
                if not merge_resorts:
                    st.warning("No resorts found")
                    return
                display_map = {
                    f"{r.get('display_name', r.get('id'))} ({r.get('id')})": r
                    for r in merge_resorts
                }
                selected_labels = st.multiselect(
                    "Select resorts",
                    list(display_map.keys()),
                    key="selected_merge_resorts_v2"
                )
                if selected_labels and st.button("🔀 Merge", key="merge_btn_v2", use_container_width=True):
                    merged_count = 0
                    skipped = []
                    for label in selected_labels:
                        resort_obj = display_map[label]
                        rid = resort_obj.get("id")
                        if rid in existing_ids:
                            skipped.append(resort_obj.get("display_name", rid))
                            continue
                        target_resorts.append(copy.deepcopy(resort_obj))
                        existing_ids.add(rid)
                        merged_count += 1
                    save_data()
                    if merged_count:
                        st.success(f"✅ Merged {merged_count} resort(s)")
                    if skipped:
                        st.warning(f"Skipped: {', '.join(skipped)}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ----------------------------------------------------------------------
# RESORT MANAGEMENT WITH ENHANCED UI
# ----------------------------------------------------------------------
def render_resort_grid(resorts: List[Dict[str, Any]], current_resort_id: Optional[str]):
    st.markdown("<div class='section-header'>🏨 Resorts in Memory (West to East); Select a resort to edit</div>", unsafe_allow_html=True)
    if not resorts:
        st.info("No resorts available. Create one below!")
        return
    sorted_resorts = sort_resorts_west_to_east(resorts)
    num_cols = 6
    cols = st.columns(num_cols)
    num_resorts = len(sorted_resorts)
    num_rows = (num_resorts + num_cols - 1) // num_cols  # ceil division
    for col_idx, col in enumerate(cols):
        with col:
            for row in range(num_rows):
                idx = col_idx * num_rows + row
                if idx < num_resorts:
                    resort = sorted_resorts[idx]
                    rid = resort.get("id")
                    name = resort.get("display_name", rid or f"Resort {idx+1}")
                    tz = resort.get("timezone", "UTC")
                    region = get_region_label(tz)
                    button_type = "primary" if current_resort_id == rid else "secondary"
                    if st.button(
                        f"🏨 {name}",
                        key=f"resort_btn_{rid}",
                        type=button_type,
                        use_container_width=True,
                        help=resort.get("address", "No address")
                    ):
                        st.session_state.current_resort_id = rid
                        st.session_state.delete_confirm = False
                        st.rerun()

def is_duplicate_resort_name(name: str, resorts: List[Dict[str, Any]]) -> bool:
    target = name.strip().lower()
    return any(r.get("display_name", "").strip().lower() == target for r in resorts)

def handle_resort_creation_v2(data: Dict[str, Any], current_resort_id: Optional[str]):
    resorts = data.setdefault("resorts", [])
    with st.expander("➕ Create or Clone Resort", expanded=False):
        new_name = st.text_input(
            "Resort Name",
            placeholder="e.g., Pulse San Francisco",
            key="new_resort_name"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✨ Create Blank", key="create_blank_btn", use_container_width=True) and new_name:
                name = new_name.strip()
                if not name:
                    st.error("❌ Name cannot be empty")
                elif is_duplicate_resort_name(name, resorts):
                    st.error("❌ Name already exists")
                else:
                    base_id = generate_resort_id(name)
                    rid = make_unique_resort_id(base_id, resorts)
                    code = generate_resort_code(name)
                    detected_timezone = detect_timezone_from_name(name)
                    full_name = get_resort_full_name(rid, name)
                    new_resort = {
                        "id": rid,
                        "display_name": name,
                        "code": code,
                        "resort_name": full_name,
                        "address": "",
                        "timezone": detected_timezone,
                        "years": {}
                    }
                    resorts.append(new_resort)
                    st.session_state.current_resort_id = rid
                    save_data()
                    st.success(f"✅ Created {name} (Timezone: {detected_timezone})")
                    st.rerun()
        with col2:
            if st.button("📋 Clone Current", key="clone_current_resort_action", use_container_width=True) and new_name:
                name = new_name.strip()
                if not name:
                    st.error("❌ Name cannot be empty")
                elif is_duplicate_resort_name(name, resorts):
                    st.error("❌ Name already exists")
                elif not current_resort_id:
                    st.error("❌ Select a resort first")
                else:
                    src = find_resort_by_id(data, current_resort_id)
                    if src is None:
                        st.error("❌ Source not found")
                    else:
                        base_id = generate_resort_id(name)
                        rid = make_unique_resort_id(base_id, resorts)
                        code = generate_resort_code(name)
                        detected_timezone = detect_timezone_from_name(name)
                        cloned = copy.deepcopy(src)
                        cloned["id"] = rid
                        cloned["display_name"] = name
                        cloned["code"] = code
                        cloned["resort_name"] = get_resort_full_name(rid, name)
                        cloned["timezone"] = detected_timezone
                        resorts.append(cloned)
                        st.session_state.current_resort_id = rid
                        save_data()
                        st.success(f"✅ Cloned to {name} (Timezone: {detected_timezone})")
                        st.rerun()

def handle_resort_deletion_v2(data: Dict[str, Any], current_resort_id: Optional[str]):
    if not current_resort_id:
        return
    current_resort = find_resort_by_id(data, current_resort_id)
    if not current_resort:
        return
    if not st.session_state.delete_confirm:
        if st.button("🗑️ Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        name = current_resort.get("display_name", current_resort_id)
        st.markdown(f"""
            <div class='error-box'>
                <h4>⚠️ Confirm Deletion</h4>
                <p>Are you sure you want to permanently delete <strong>{name}</strong>?</p>
                <p>This action cannot be undone.</p>
            </div>
        """, unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔥 DELETE FOREVER", key=f"delete_resort_final_{current_resort_id}", type="primary", use_container_width=True):
                idx = find_resort_index(data, current_resort_id)
                if idx is not None:
                    data.get("resorts", []).pop(idx)
                st.session_state.current_resort_id = None
                st.session_state.delete_confirm = False
                st.session_state.working_resorts.pop(current_resort_id, None)
                save_data()
                st.success("✅ Resort deleted")
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"delete_cancel_{current_resort_id}", use_container_width=True):
                st.session_state.delete_confirm = False
                st.rerun()
        st.stop()

# ----------------------------------------------------------------------
# WORKING RESORT MANAGEMENT
# ----------------------------------------------------------------------
def handle_resort_switch_v2(data: Dict[str, Any], current_resort_id: Optional[str], previous_resort_id: Optional[str]):
    if previous_resort_id and previous_resort_id != current_resort_id:
        working_resorts = st.session_state.working_resorts
        if previous_resort_id in working_resorts:
            working = working_resorts[previous_resort_id]
            committed = find_resort_by_id(data, previous_resort_id)
            if committed is None:
                working_resorts.pop(previous_resort_id, None)
            elif working != committed:
                st.warning(f"⚠️ Unsaved changes in {committed.get('display_name', previous_resort_id)}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Save", key="switch_save_prev", use_container_width=True):
                        commit_working_to_data_v2(data, working, previous_resort_id)
                        del working_resorts[previous_resort_id]
                        st.session_state.previous_resort_id = current_resort_id
                        st.rerun()
                with col2:
                    if st.button("🚫 Discard", key="switch_discard_prev", use_container_width=True):
                        del working_resorts[previous_resort_id]
                        st.session_state.previous_resort_id = current_resort_id
                        st.rerun()
                with col3:
                    if st.button("↩️ Stay", key="switch_cancel_prev", use_container_width=True):
                        st.session_state.current_resort_id = previous_resort_id
                        st.rerun()
                st.stop()
    st.session_state.previous_resort_id = current_resort_id

def commit_working_to_data_v2(data: Dict[str, Any], working: Dict[str, Any], resort_id: str):
    idx = find_resort_index(data, resort_id)
    if idx is not None:
        data["resorts"][idx] = copy.deepcopy(working)
        save_data()

def render_save_button_v2(data: Dict[str, Any], working: Dict[str, Any], resort_id: str):
    committed = find_resort_by_id(data, resort_id)
    if committed is not None and committed != working:
        if st.button("💾 Save All Changes", type="primary", key=f"save_resort_{resort_id}", use_container_width=True):
            commit_working_to_data_v2(data, working, resort_id)
            st.session_state.working_resorts.pop(resort_id, None)
            st.success("✅ Changes saved successfully!")
            st.rerun()

# ----------------------------------------------------------------------
# SEASON MANAGEMENT
# ----------------------------------------------------------------------
def ensure_year_structure(resort: Dict[str, Any], year: str):
    years = resort.setdefault("years", {})
    year_obj = years.setdefault(year, {})
    year_obj.setdefault("seasons", [])
    year_obj.setdefault("holidays", [])
    return year_obj

def get_all_season_names_for_resort(working: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for year_obj in working.get("years", {}).values():
        names.update(s.get("name") for s in year_obj.get("seasons", []) if s.get("name"))
    return names

def delete_season_across_years(working: Dict[str, Any], season_name: str):
    years = working.get("years", {})
    for year_obj in years.values():
        year_obj["seasons"] = [s for s in year_obj.get("seasons", []) if s.get("name") != season_name]

def rename_season_across_years(working: Dict[str, Any], old_name: str, new_name: str):
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name:
        st.error("Season names cannot be empty")
        return
    if old_name == new_name:
        st.info("Season name unchanged.")
        return
    all_names = get_all_season_names_for_resort(working)
    if any(n.lower() == new_name.lower() and n != old_name for n in all_names):
        st.error(f"❌ Season '{new_name}' already exists")
        return
    changed = False
    for year_obj in working.get("years", {}).values():
        for s in year_obj.get("seasons", []):
            if (s.get("name") or "").strip() == old_name:
                s["name"] = new_name
                changed = True
    if changed:
        st.success(f"✅ Renamed season '{old_name}' → '{new_name}' across all years")
    else:
        st.warning(f"No season named '{old_name}' found")

def render_season_rename_panel_v2(working: Dict[str, Any], resort_id: str):
    all_names = sorted(get_all_season_names_for_resort(working))
    if not all_names:
        st.caption("No seasons available to rename yet.")
        return
    st.markdown("**✏️ Rename Seasons (applies to all years)**")
    for name in all_names:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_name = st.text_input(
                f"Rename '{name}' to",
                value=name,
                key=rk(resort_id, "rename_season_input", name)
            )
        with col2:
            if st.button("Apply", key=rk(resort_id, "rename_season_btn", name)):
                if new_name and new_name != name:
                    rename_season_across_years(working, name, new_name)
                    st.rerun()

def render_season_dates_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>📅 Season Dates</div>", unsafe_allow_html=True)
    st.caption("Define season date ranges for each year. Season names apply across all years.")
    render_season_rename_panel_v2(working, resort_id)
    all_names = get_all_season_names_for_resort(working)
    for year in years:
        year_obj = ensure_year_structure(working, year)
        seasons = year_obj.get("seasons", [])
        with st.expander(f"📆 {year} Seasons", expanded=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season_name = st.text_input(
                    f"New season (applies to all years)",
                    key=rk(resort_id, "new_season", year),
                    placeholder="e.g., Peak Season"
                )
            with col2:
                if st.button("➕ Add", key=rk(resort_id, "add_season_all_years", year), use_container_width=True) and new_season_name:
                    name = new_season_name.strip()
                    if not name:
                        st.error("❌ Name required")
                    elif any(name.lower() == n.lower() for n in all_names):
                        st.error("❌ Season exists")
                    else:
                        for y2 in years:
                            y2_obj = ensure_year_structure(working, y2)
                            y2_obj.setdefault("seasons", []).append({
                                "name": name,
                                "periods": [],
                                "day_categories": {}
                            })
                        st.success(f"✅ Added '{name}'")
                        st.rerun()
            for idx, season in enumerate(seasons):
                render_single_season_v2(working, year, season, idx, resort_id)

def render_single_season_v2(working: Dict[str, Any], year: str, season: Dict[str, Any], idx: int, resort_id: str):
    sname = season.get("name", f"Season {idx+1}")
    st.markdown(f"**🎯 {sname}**")
    periods = season.setdefault("periods", [])
    for r_idx, p in enumerate(periods):
        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            new_start = st.date_input(
                "Start",
                safe_date(p.get("start") or f"{year}-01-01"),
                key=rk(resort_id, "season", year, idx, "start", r_idx)
            )
        with col2:
            new_end = st.date_input(
                "End",
                safe_date(p.get("end") or f"{year}-01-07"),
                key=rk(resort_id, "season", year, idx, "end", r_idx)
            )
        with col3:
            if st.button("❌", key=rk(resort_id, "season", year, idx, "del_range", r_idx)):
                periods.pop(r_idx)
                st.rerun()
        p["start"] = new_start.isoformat()
        p["end"] = new_end.isoformat()
    col_add, col_del = st.columns([1, 1])
    with col_add:
        if st.button("➕ Add Date Range", key=rk(resort_id, "season", year, idx, "add_range"), use_container_width=True):
            periods.append({"start": f"{year}-01-01", "end": f"{year}-01-07"})
            st.rerun()
    with col_del:
        if st.button("🗑️ Delete Season", key=rk(resort_id, "season_del_all_years", year, idx), use_container_width=True):
            delete_season_across_years(working, sname)
            st.rerun()

# ----------------------------------------------------------------------
# ROOM TYPE MANAGEMENT
# ----------------------------------------------------------------------
def get_all_room_types_for_resort(working: Dict[str, Any]) -> List[str]:
    rooms: Set[str] = set()
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                if isinstance(rp := cat.get("room_points", {}), dict):
                    rooms.update(rp.keys())
        for h in year_obj.get("holidays", []):
            if isinstance(rp := h.get("room_points", {}), dict):
                rooms.update(rp.keys())
    return sorted(rooms)

def add_room_type_master(working: Dict[str, Any], room: str, base_year: str):
    room = room.strip()
    if not room:
        return
    years = working.get("years", {})
    if base_year in years:
        base_year_obj = ensure_year_structure(working, base_year)
        for season in base_year_obj.get("seasons", []):
            for cat in season.setdefault("day_categories", {}).values():
                cat.setdefault("room_points", {}).setdefault(room, 0)
    for year_obj in years.values():
        for h in year_obj.get("holidays", []):
            h.setdefault("room_points", {}).setdefault(room, 0)

def delete_room_type_master(working: Dict[str, Any], room: str):
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                if isinstance(rp := cat.get("room_points", {}), dict):
                    rp.pop(room, None)
        for h in year_obj.get("holidays", []):
            if isinstance(rp := h.get("room_points", {}), dict):
                rp.pop(room, None)

def rename_room_type_across_resort(working: Dict[str, Any], old_name: str, new_name: str):
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name:
        st.error("Room names cannot be empty")
        return
    if old_name == new_name:
        st.info("Room name unchanged.")
        return
    all_rooms = get_all_room_types_for_resort(working)
    if any(r.lower() == new_name.lower() and r != old_name for r in all_rooms):
        st.error(f"❌ Room type '{new_name}' already exists")
        return
    changed = False
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points")
                if isinstance(rp, dict) and old_name in rp:
                    rp[new_name] = rp.pop(old_name)
                    changed = True
        for h in year_obj.get("holidays", []):
            rp = h.get("room_points")
            if isinstance(rp, dict) and old_name in rp:
                rp[new_name] = rp.pop(old_name)
                changed = True
    if changed:
        st.success(f"✅ Renamed room '{old_name}' → '{new_name}' across all years and holidays")
    else:
        st.warning(f"No room named '{old_name}' found")

# ----------------------------------------------------------------------
# SYNC FUNCTIONS
# ----------------------------------------------------------------------
def sync_season_room_points_across_years(working: Dict[str, Any], base_year: str):
    years = working.get("years", {})
    if not years or base_year not in years:
        return
    canonical_rooms: Set[str] = set()
    for y_obj in years.values():
        for season in y_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                if isinstance(rp := cat.get("room_points", {}), dict):
                    canonical_rooms |= set(rp.keys())
    if not canonical_rooms:
        return
    base_year_obj = years[base_year]
    base_seasons = base_year_obj.get("seasons", [])
    for season in base_seasons:
        for cat in season.setdefault("day_categories", {}).values():
            rp = cat.setdefault("room_points", {})
            for room in canonical_rooms:
                rp.setdefault(room, 0)
            for room in list(rp.keys()):
                if room not in canonical_rooms:
                    del rp[room]
    base_by_name = {s.get("name", ""): s for s in base_seasons if s.get("name")}
    for year_name, year_obj in years.items():
        if year_name != base_year:
            for season in year_obj.get("seasons", []):
                if (name := season.get("name", "")) in base_by_name:
                    season["day_categories"] = copy.deepcopy(base_by_name[name].get("day_categories", {}))

def sync_holiday_room_points_across_years(working: Dict[str, Any], base_year: str):
    years = working.get("years", {})
    if not years or base_year not in years:
        return
    base_year_obj = ensure_year_structure(working, base_year)
    base_holidays = base_year_obj.get("holidays", [])
    all_rooms = get_all_room_types_for_resort(working)
    for h in base_holidays:
        rp = h.setdefault("room_points", {})
        for room in all_rooms:
            rp.setdefault(room, 0)
        for room in list(rp.keys()):
            if room not in all_rooms:
                del rp[room]
    base_by_key = {
        (h.get("global_reference") or h.get("name") or "").strip(): h
        for h in base_holidays
        if (h.get("global_reference") or h.get("name") or "").strip()
    }
    for year_name, year_obj in years.items():
        if year_name != base_year:
            for h in year_obj.get("holidays", []):
                if (key := (h.get("global_reference") or h.get("name") or "").strip()) in base_by_key:
                    h["room_points"] = copy.deepcopy(base_by_key[key].get("room_points", {}))

# ----------------------------------------------------------------------
# RESORT BASIC INFO EDITOR (helper)
# ----------------------------------------------------------------------
def edit_resort_basics(working: Dict[str, Any], resort_id: str):
    """
    Renders editable fields for resort_name, timezone and address.
    Returns nothing – directly mutates the working dict.
    """
    st.markdown("### Basic Resort Information")
    # Current values (with fallbacks)
    current_name = working.get("resort_name", "")
    current_tz = working.get("timezone", "UTC")
    current_addr = working.get("address", "")
    # Full Resort Name
    new_name = st.text_input(
        "Full Resort Name (resort_name)",
        value=current_name,
        key=rk(resort_id, "resort_name_edit"),
        help="Official name stored in the 'resort_name' field"
    )
    working["resort_name"] = new_name.strip()
    # Timezone & Address side-by-side
    col_tz, col_addr = st.columns(2)
    with col_tz:
        new_tz = st.text_input(
            "Timezone",
            value=current_tz,
            key=rk(resort_id, "timezone_edit"),
            help="e.g. America/New_York, Europe/London, etc."
        )
        working["timezone"] = new_tz.strip() or "UTC"
    with col_addr:
        new_addr = st.text_area( # text_area gives a bit more space for addresses
            "Address",
            value=current_addr,
            height=80,
            key=rk(resort_id, "address_edit"),
            help="Full street address of the resort"
        )
        working["address"] = new_addr.strip()

# ----------------------------------------------------------------------
# MASTER POINTS EDITOR
# ----------------------------------------------------------------------
def render_reference_points_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>🎯 Master Room Points</div>", unsafe_allow_html=True)
    st.caption("Edit nightly points for each season. Changes apply to all years automatically.")
    base_year = BASE_YEAR_FOR_POINTS if BASE_YEAR_FOR_POINTS in years else (sorted(years)[0] if years else BASE_YEAR_FOR_POINTS)
    base_year_obj = ensure_year_structure(working, base_year)
    seasons = base_year_obj.get("seasons", [])
    if not seasons:
        st.info(f"💡 No seasons defined yet. Add seasons in the Season Dates section first.")
        return
    canonical_rooms = get_all_room_types_for_resort(working)
    for s_idx, season in enumerate(seasons):
        with st.expander(f"🏖️ {season.get('name', f'Season {s_idx+1}')}", expanded=True):
            dc = season.setdefault("day_categories", {})
            if not dc:
                dc["sun_thu"] = {
                    "day_pattern": ["Sun", "Mon", "Tue", "Wed", "Thu"],
                    "room_points": {}
                }
                dc["fri_sat"] = {
                    "day_pattern": ["Fri", "Sat"],
                    "room_points": {}
                }
            for key, cat in dc.items():
                day_pattern = cat.setdefault("day_pattern", [])
                st.markdown(f"**📅 {key}** – {', '.join(day_pattern) if day_pattern else 'No days set'}")
                room_points = cat.setdefault("room_points", {})
                rooms_here = canonical_rooms or sorted(room_points.keys())
                for room in rooms_here:
                    room_points.setdefault(room, 0)
                cols = st.columns(4)
                for j, room in enumerate(sorted(room_points.keys())):
                    with cols[j % 4]:
                        current_val = int(room_points.get(room, 0) or 0)
                        new_val = st.number_input(
                            room,
                            value=current_val,
                            step=25,
                            key=rk(resort_id, "master_rp", base_year, s_idx, key, room),
                            help=f"Nightly points for {room}"
                        )
                        if new_val != current_val:
                            room_points[room] = int(new_val)
    st.markdown("---")
    st.markdown("**🏠 Manage Room Types**")
    col1, col2 = st.columns(2)
    with col1:
        new_room = st.text_input(
            "Add room type (applies to all seasons/years)",
            key=rk(resort_id, "room_add_master"),
            placeholder="e.g., 2BR Ocean View"
        )
        if st.button("➕ Add Room", key=rk(resort_id, "room_add_btn_master"), use_container_width=True) and new_room:
            add_room_type_master(working, new_room.strip(), base_year)
            st.success(f"✅ Added {new_room}")
            st.rerun()
    with col2:
        del_room = st.selectbox(
            "Delete room type",
            [""] + get_all_room_types_for_resort(working),
            key=rk(resort_id, "room_del_master")
        )
        if del_room and st.button("🗑️ Delete Room", key=rk(resort_id, "room_del_btn_master"), use_container_width=True):
            delete_room_type_master(working, del_room)
            st.success(f"✅ Deleted {del_room}")
            st.rerun()
    # Room rename panel
    all_rooms_list = get_all_room_types_for_resort(working)
    if all_rooms_list:
        st.markdown("**✏️ Rename Room Type (applies everywhere)**")
        col3, col4 = st.columns(2)
        with col3:
            old_room = st.selectbox(
                "Room to rename",
                [""] + all_rooms_list,
                key=rk(resort_id, "room_rename_old")
            )
        with col4:
            new_room_name = st.text_input(
                "New name",
                key=rk(resort_id, "room_rename_new")
            )
        if st.button("✅ Apply Rename", key=rk(resort_id, "room_rename_apply"), use_container_width=True):
            if old_room and new_room_name:
                rename_room_type_across_resort(working, old_room, new_room_name)
                st.rerun()
    sync_season_room_points_across_years(working, base_year=base_year)

# ----------------------------------------------------------------------
# HOLIDAY MANAGEMENT
# ----------------------------------------------------------------------
def get_all_holidays_for_resort(working: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get unique list of holidays across all years (by global_reference)"""
    holidays_map = {}
    for year_obj in working.get("years", {}).values():
        for h in year_obj.get("holidays", []):
            key = (h.get("global_reference") or h.get("name") or "").strip()
            if key and key not in holidays_map:
                holidays_map[key] = {
                    "name": h.get("name", key),
                    "global_reference": key
                }
    return list(holidays_map.values())

def add_holiday_to_all_years(working: Dict[str, Any], holiday_name: str, global_ref: str):
    """Add a holiday to all years in the resort"""
    holiday_name = holiday_name.strip()
    global_ref = (global_ref or holiday_name).strip()
    if not holiday_name or not global_ref:
        return False
    
    years = working.get("years", {})
    for year_obj in years.values():
        holidays = year_obj.setdefault("holidays", [])
        # Check if already exists
        if any((h.get("global_reference") or h.get("name") or "").strip() == global_ref for h in holidays):
            continue
        holidays.append({
            "name": holiday_name,
            "global_reference": global_ref,
            "room_points": {}
        })
    return True

def delete_holiday_from_all_years(working: Dict[str, Any], global_ref: str):
    """Delete a holiday from all years in the resort"""
    global_ref = (global_ref or "").strip()
    if not global_ref:
        return False
    
    changed = False
    for year_obj in working.get("years", {}).values():
        holidays = year_obj.get("holidays", [])
        original_len = len(holidays)
        year_obj["holidays"] = [
            h for h in holidays 
            if (h.get("global_reference") or h.get("name") or "").strip() != global_ref
        ]
        if len(year_obj["holidays"]) < original_len:
            changed = True
    return changed

def rename_holiday_across_years(working: Dict[str, Any], old_global_ref: str, new_name: str, new_global_ref: str):
    """Rename a holiday across all years"""
    old_global_ref = (old_global_ref or "").strip()
    new_name = (new_name or "").strip()
    new_global_ref = (new_global_ref or "").strip()
    
    if not old_global_ref or not new_name or not new_global_ref:
        st.error("All fields must be filled")
        return False
    
    changed = False
    for year_obj in working.get("years", {}).values():
        for h in year_obj.get("holidays", []):
            if (h.get("global_reference") or h.get("name") or "").strip() == old_global_ref:
                h["name"] = new_name
                h["global_reference"] = new_global_ref
                changed = True
    return changed

def render_holiday_management_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>🎄 Holiday Management</div>", unsafe_allow_html=True)
    base_year = BASE_YEAR_FOR_POINTS if BASE_YEAR_FOR_POINTS in years else (sorted(years)[0] if years else BASE_YEAR_FOR_POINTS)
    
    st.markdown("**📋 Manage Holidays (applies to all years)**")
    st.caption("Holidays are automatically synchronized across all years. Changes here affect every year.")
    
    # Show current holidays
    current_holidays = get_all_holidays_for_resort(working)
    
    if current_holidays:
        st.markdown("**Current Holidays:**")
        for h in current_holidays:
            # Use global_reference as the stable unique key
            unique_key = h.get("global_reference", "")
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                new_display = st.text_input(
                    "Display Name",
                    value=h.get("name", ""),
                    key=rk(resort_id, "holiday_display", unique_key)
                )
            with col2:
                new_global = st.text_input(
                    "Global Reference",
                    value=h.get("global_reference", ""),
                    key=rk(resort_id, "holiday_ref", unique_key)
                )
            with col3:
                if st.button("🗑️", key=rk(resort_id, "holiday_del_global", unique_key)):
                    if delete_holiday_from_all_years(working, unique_key):
                        st.success(f"✅ Deleted '{h['name']}' from all years")
                        st.rerun()
            
            # Check if values changed and update across all years
            if new_display != h["name"] or new_global != h["global_reference"]:
                if rename_holiday_across_years(working, unique_key, new_display, new_global):
                    # Silently update - will be saved when user clicks Save button
                    pass
    else:
        st.info("💡 No holidays assigned yet. Add one below.")
    
    st.markdown("---")
    st.markdown("**➕ Add New Holiday**")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_name = st.text_input(
            "Holiday name (will be added to all years)",
            key=rk(resort_id, "new_holiday_name"),
            placeholder="e.g., Christmas Week"
        )
    with col2:
        if st.button("➕ Add to All Years", key=rk(resort_id, "btn_add_holiday_global"), use_container_width=True) and new_name:
            name = new_name.strip()
            if not name:
                st.error("❌ Name cannot be empty")
            elif any(h["global_reference"].lower() == name.lower() for h in current_holidays):
                st.error("❌ Holiday already exists")
            else:
                if add_holiday_to_all_years(working, name, name):
                    st.success(f"✅ Added '{name}' to all years")
                    st.rerun()
    
    sync_holiday_room_points_across_years(working, base_year=base_year)
    
    st.markdown("---")
    st.markdown("**💰 Master Holiday Points**")
    st.caption("Edit holiday room points once. Applied to all years automatically.")
    base_year_obj = ensure_year_structure(working, base_year)
    base_holidays = base_year_obj.get("holidays", [])
    if not base_holidays:
        st.info(f"💡 No holidays defined in {base_year}. Add holidays above first.")
    else:
        all_rooms = get_all_room_types_for_resort(working)
        for h_idx, h in enumerate(base_holidays):
            disp_name = h.get("name", f"Holiday {h_idx+1}")
            key = (h.get("global_reference") or h.get("name") or "").strip()
            with st.expander(f"🎊 {disp_name}", expanded=False):
                st.caption(f"Reference key: {key}")
                rp = h.setdefault("room_points", {})
                rooms_here = sorted(all_rooms or rp.keys())
                cols = st.columns(4)
                for j, room in enumerate(rooms_here):
                    rp.setdefault(room, 0)
                    with cols[j % 4]:
                        current_val = int(rp.get(room, 0) or 0)
                        new_val = st.number_input(
                            room,
                            value=current_val,
                            step=25,
                            key=rk(resort_id, "holiday_master_rp", base_year, h_idx, room)
                        )
                        if new_val != current_val:
                            rp[room] = int(new_val)
    sync_holiday_room_points_across_years(working, base_year=base_year)
# ----------------------------------------------------------------------
# RESORT SUMMARY
# ----------------------------------------------------------------------
def compute_weekly_totals_for_season_v2(season: Dict[str, Any], room_types: List[str]) -> Tuple[Dict[str, int], bool]:
    weekly_totals = {room: 0 for room in room_types}
    any_data = False
    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    for cat in season.get("day_categories", {}).values():
        pattern = cat.get("day_pattern", [])
        if not (rp := cat.get("room_points", {})) or not isinstance(rp, dict):
            continue
        n_days = len([d for d in pattern if d in valid_days])
        if n_days > 0:
            for room in room_types:
                if room in rp and rp[room] is not None:
                    weekly_totals[room] += int(rp[room]) * n_days
                    any_data = True
    return weekly_totals, any_data

def render_resort_summary_v2(working: Dict[str, Any]):
    st.markdown("<div class='section-header'>📊 Resort Summary</div>", unsafe_allow_html=True)
    resort_years = working.get("years", {})
    if not resort_years:
        st.info("💡 No data available yet")
        return
    sorted_years = sorted(resort_years.keys(), key=lambda y: int(y) if str(y).isdigit() else 0)
    ref_year = next((y for y in sorted_years if resort_years[y].get("seasons")), None)
    if not ref_year:
        st.info("💡 No seasons defined yet")
        return
    room_types = get_all_room_types_for_resort(working)
    if not room_types:
        st.info("💡 No room types defined yet")
        return
    rows = []
    for season in resort_years[ref_year].get("seasons", []):
        sname = season.get("name", "").strip() or "(Unnamed)"
        weekly_totals, any_data = compute_weekly_totals_for_season_v2(season, room_types)
        if any_data:
            row = {"Season": sname}
            row.update({room: (total if total else "—") for room, total in weekly_totals.items()})
            rows.append(row)
    last_holiday_year = None
    for y in reversed(sorted_years):
        if resort_years.get(y, {}).get("holidays"):
            last_holiday_year = y
            break
    if last_holiday_year:
        for h in resort_years[last_holiday_year].get("holidays", []):
            hname = h.get("name", "").strip() or "(Unnamed)"
            rp = h.get("room_points", {}) or {}
            row = {"Season": f"Holiday – {hname}"}
            for room in room_types:
                val = rp.get(room)
                row[room] = val if isinstance(val, (int, float)) and val not in (0, None) else "—"
            rows.append(row)
    if rows:
        df = pd.DataFrame(rows, columns=["Season"] + room_types)
        st.caption("Season rows show 7-night totals computed from nightly rates. Holiday rows show weekly totals directly from holiday points (no extra calculations).")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 No rate or holiday data available")

# ----------------------------------------------------------------------
# VALIDATION
# ----------------------------------------------------------------------
def validate_resort_data_v2(working: Dict[str, Any], data: Dict[str, Any], years: List[str]) -> List[str]:
    issues = []
    ALL_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}   # ← fixed name
    all_rooms = get_all_room_types_for_resort(working)
    global_holidays = data.get("global_holidays", {})

    for year in years:
        year_obj = working.get("years", {}).get(year, {})
        seasons = year_obj.get("seasons", [])

        # 1. No seasons at all
        if not seasons:
            issues.append(f"[{year}] No seasons defined")
            continue

        # 2. Validate every season
        for s_idx, season in enumerate(seasons):
            sname = season.get("name", f"Season {s_idx+1}")

            # Day coverage & overlap check
            covered_days: Set[str] = set()
            for cat in season.get("day_categories", {}).values():
                pattern = cat.get("day_pattern", [])
                valid_days_in_cat = {d for d in pattern if d in ALL_DAYS}

                overlap = covered_days & valid_days_in_cat
                if overlap:
                    issues.append(f"[{year}] {sname} → overlapping days: {', '.join(sorted(overlap))}")

                covered_days.update(valid_days_in_cat)

            missing_days = ALL_DAYS - covered_days
            if missing_days:
                issues.append(f"[{year}] {sname} → missing days: {', '.join(sorted(missing_days))}")

            # Room points completeness
            if all_rooms:
                for cat in season.get("day_categories", {}).values():
                    rp = cat.get("room_points", {})
                    if isinstance(rp, dict):
                        missing_rooms = all_rooms - set(rp.keys())
                        if missing_rooms:
                            issues.append(f"[{year}] {sname} → missing room points for: {', '.join(sorted(missing_rooms))}")

        # 3. Holiday validation
        for h in year_obj.get("holidays", []):
            hname = h.get("name", "(unnamed holiday)")
            key = (h.get("global_reference") or h.get("name") or "").strip()

            if key and key not in global_holidays.get(year, {}):
                issues.append(f"[{year}] Holiday '{hname}' references missing global key → '{key}'")

            if all_rooms:
                rp = h.get("room_points", {})
                if isinstance(rp, dict):
                    missing_rooms = all_rooms - set(rp.keys())
                    if missing_rooms:
                        issues.append(f"[{year}] Holiday '{hname}' → missing room points for: {', '.join(sorted(missing_rooms))}")

    return issues


def render_validation_panel_v2(working: Dict[str, Any], data: Dict[str, Any], years: List[str]):
    with st.expander("Data Validation", expanded=False):
        issues = validate_resort_data_v2(working, data, years)
        if issues:
            st.error(f"Found {len(issues)} issue(s):")
            for issue in issues:
                st.write(f"• {issue}")
        else:
            st.success("All checks passed – data is valid!")

# ----------------------------------------------------------------------
# WORKING RESORT LOADER + HEADER RENDERER (single combined helper)
# ----------------------------------------------------------------------
def load_resort(
    data: Dict[str, Any],
    current_resort_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not current_resort_id:
        return None
    # Ensure we have a working copy in memory
    working_resorts = st.session_state.working_resorts
    if current_resort_id not in working_resorts:
        if resort_obj := find_resort_by_id(data, current_resort_id):
            working_resorts[current_resort_id] = copy.deepcopy(resort_obj)
    working = working_resorts.get(current_resort_id)
    if not working:
        return None
    return working

def render_resort_card(resort_name: str, timezone: str, address: str):
    """Render an enhanced resort information card"""
    st.markdown(f"""
        <div style="
            background: var(--card-bg);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            margin-bottom: 20px;
            border-left: 4px solid var(--primary-color);
            transition: all 0.2s ease;
        ">
            <h2 style="margin:0; color: var(--primary-color); font-size: 28px; font-weight: 700;">
                🖖️ {resort_name}
            </h2>
            <p style="margin: 8px 0 0 0; color: #64748b; font-size: 16px;">
                🕒 Timezone: {timezone}
            </p>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">
                📍 {address}
            </p>
        </div>
    """, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# GANTT CHART
# ----------------------------------------------------------------------
def create_gantt_chart_v2(working: Dict[str, Any], year: str, data: Dict[str, Any]) -> go.Figure:
    rows = []
    year_obj = working.get("years", {}).get(year, {})
    for season in year_obj.get("seasons", []):
        sname = season.get("name", "(Unnamed)")
        for i, p in enumerate(season.get("periods", []), 1):
            try:
                start_dt = datetime.strptime(p.get("start"), "%Y-%m-%d")
                end_dt = datetime.strptime(p.get("end"), "%Y-%m-%d")
                if start_dt <= end_dt:
                    rows.append({
                        "Task": f"{sname} #{i}",
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Type": sname
                    })
            except:
                continue
    gh_year = data.get("global_holidays", {}).get(year, {})
    for h in year_obj.get("holidays", []):
        global_ref = h.get("global_reference") or h.get("name")
        if gh := gh_year.get(global_ref):
            try:
                start_dt = datetime.strptime(gh.get("start_date"), "%Y-%m-%d")
                end_dt = datetime.strptime(gh.get("end_date"), "%Y-%m-%d")
                if start_dt <= end_dt:
                    rows.append({
                        "Task": h.get("name", "(Unnamed)"),
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Type": "Holiday"
                    })
            except:
                continue
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
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        title=f"{working.get('display_name', 'Resort')} – {year} Timeline",
        height=max(400, len(df) * 35)
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d %b %Y")
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Start: %{base|%d %b %Y}<br>End: %{x|%d %b %Y}<extra></extra>"
    )
    fig.update_layout(
        showlegend=True,
        xaxis_title="Date",
        yaxis_title="Period",
        font=dict(size=12),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def render_gantt_charts_v2(working: Dict[str, Any], years: List[str], data: Dict[str, Any]):
    st.markdown("<div class='section-header'>📊 Visual Timeline</div>", unsafe_allow_html=True)
    tabs = st.tabs([f"📅 {year}" for year in years])
    for tab, year in zip(tabs, years):
        with tab:
            fig = create_gantt_chart_v2(working, year, data)
            st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------------------------
# GLOBAL SETTINGS
# ----------------------------------------------------------------------
def render_maintenance_fees_v2(data: Dict[str, Any]):
    rates = data.setdefault("configuration", {}).setdefault("maintenance_rates", {})
    st.caption("Define maintenance fee rates per point for each year")
    for year in sorted(rates.keys()):
        current_rate = float(rates[year])
        new_rate = st.number_input(
            f"💵 {year}",
            value=current_rate,
            step=0.01,
            format="%.4f",
            key=f"mf_{year}"
        )
        if new_rate != current_rate:
            rates[year] = float(new_rate)
            save_data()

def render_global_holiday_dates_editor_v2(data: Dict[str, Any], years: List[str]):
    global_holidays = data.setdefault("global_holidays", {})
    for year in years:
        st.markdown(f"**📆 {year}**")
        holidays = global_holidays.setdefault(year, {})
        for i, (name, obj) in enumerate(list(holidays.items())):
            with st.expander(f"🎉 {name}", expanded=False):
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    new_start = st.date_input(
                        "Start date",
                        safe_date(obj.get("start_date") or f"{year}-01-01"),
                        key=f"ghs_{year}_{i}"
                    )
                with col2:
                    new_end = st.date_input(
                        "End date",
                        safe_date(obj.get("end_date") or f"{year}-01-07"),
                        key=f"ghe_{year}_{i}"
                    )
                with col3:
                    if st.button("🗑️", key=f"ghd_{year}_{i}"):
                        del holidays[name]
                        save_data()
                        st.rerun()
                obj["start_date"] = new_start.isoformat()
                obj["end_date"] = new_end.isoformat()
                new_type = st.text_input("Type", value=obj.get("type", "other"), key=f"ght_{year}_{i}")
                obj["type"] = new_type or "other"
                regions_str = ", ".join(obj.get("regions", []))
                new_regions = st.text_input("Regions (comma-separated)", value=regions_str, key=f"ghr_{year}_{i}")
                obj["regions"] = [r.strip() for r in new_regions.split(",") if r.strip()]
                save_data()
        st.markdown("---")
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            new_name = st.text_input(f"New holiday name", key=f"gh_new_name_{year}", placeholder="e.g., New Year")
        with col2:
            new_start = st.date_input("Start", datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(), key=f"gh_new_start_{year}")
        with col3:
            new_end = st.date_input("End", datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(), key=f"gh_new_end_{year}")
        if st.button("➕ Add Global Holiday", key=f"gh_add_{year}", use_container_width=True) and new_name and new_name not in holidays:
            holidays[new_name] = {
                "start_date": new_start.isoformat(),
                "end_date": new_end.isoformat(),
                "type": "other",
                "regions": ["global"]
            }
            save_data()
            st.rerun()

def render_global_settings_v2(data: Dict[str, Any], years: List[str]):
    st.markdown("<div class='section-header'>⚙️ Global Configuration</div>", unsafe_allow_html=True)
    with st.expander("💰 Maintenance Fee Rates", expanded=False):
        render_maintenance_fees_v2(data)
    with st.expander("🎅 Global Holiday Calendar", expanded=False):
        render_global_holiday_dates_editor_v2(data, years)

# ----------------------------------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------------------------------
def main():
    setup_page()
    initialize_session_state()
    # Auto-load data file (optional)
    if st.session_state.data is None:
        try:
            with open("data_v2.json", "r") as f:
                raw_data = json.load(f)
                if "schema_version" in raw_data and "resorts" in raw_data:
                    st.session_state.data = raw_data
                    st.toast(f"✅ Auto-loaded {len(raw_data.get('resorts', []))} resorts", icon="✅")
        except FileNotFoundError:
            pass
        except Exception as e:
            st.toast(f"⚠️ Auto-load error: {str(e)}", icon="⚠️")
    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div style='text-align: center; padding: 20px; margin-bottom: 20px;'>
                <h1 style='color: #0891b2 !important; margin: 0; font-size: 28px;'>🏨 File Operations</h1>
                <p style='color: #64748b !important; margin: 8px 0 0 0; font-size: 14px;'>Resort Management System</p>
            </div>
        """, unsafe_allow_html=True)
        with st.expander("ℹ️ How File Operations Work", expanded=False):
            st.markdown(
            """
            - Data are pre-loaded into memory and can be edited.
            - Loading another file will replace data in memory.
            - Edits in memory are temporary — SAVE or they may be lost on refresh.
            - Verify by matching saved file to what’s in memory.
            - Upload a different file to merge selected resorts to memory.
            """)
        handle_file_upload()
        if st.session_state.data:
            st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
            create_download_button_v2(st.session_state.data)
            handle_file_verification()
            handle_merge_from_another_file_v2(st.session_state.data)
        show_save_indicator()
    # Main content
    st.markdown("<div class='big-font'>MVC Resort Editor V2</div>", unsafe_allow_html=True)
    if not st.session_state.data:
        st.markdown("""
            <div class='info-box'>
                <h3>👋 Welcome!</h3>
                <p>Upload your V2 data.json file from the sidebar to begin editing resort data.</p>
            </div>
        """, unsafe_allow_html=True)
        return
    data = st.session_state.data
    resorts = get_resort_list(data)
    years = get_years_from_data(data)
    current_resort_id = st.session_state.current_resort_id
    previous_resort_id = st.session_state.previous_resort_id
    render_resort_grid(resorts, current_resort_id)
    handle_resort_switch_v2(data, current_resort_id, previous_resort_id)
    # Working resort
    working = load_resort(data, current_resort_id)
   
    if working:
        resort_name = working.get("resort_name") or working.get("display_name") or current_resort_id
        timezone = working.get("timezone", "UTC")
        address = working.get("address", "No address provided")
        render_resort_card(resort_name, timezone, address)
        render_validation_panel_v2(working, data, years)
        render_save_button_v2(data, working, current_resort_id)
        handle_resort_creation_v2(data, current_resort_id)
        handle_resort_deletion_v2(data, current_resort_id)
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Overview",
            "📅 Season Dates",
            "💰 Room Points",
            "🎄 Holidays",
            "📈 Points Summary"
        ])
        with tab1:
            edit_resort_basics(working, current_resort_id)
        with tab2:
            render_gantt_charts_v2(working, years, data)
            render_season_dates_editor_v2(working, years, current_resort_id)
        with tab3:
            render_reference_points_editor_v2(working, years, current_resort_id)
        with tab4:
            render_holiday_management_v2(working, years, current_resort_id)
        with tab5:
            render_resort_summary_v2(working)
    st.markdown("---")
    render_global_settings_v2(data, years)
    st.markdown("""
        <div class='success-box'>
            <p style='margin: 0;'>✨ MVC Resort Editor V2</p>
            <p style='margin: 8px 0 0 0; font-size: 14px; opacity: 0.9;'>
                Master data management • Real-time sync across years • Professional-grade tools
            </p>
        </div>
    """, unsafe_allow_html=True)
def run():
    main()
if __name__ == "__main__":
    main()
