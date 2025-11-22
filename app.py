import streamlit as st
import json
import copy
import re
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Set
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
DEFAULT_YEARS = ["2025", "2026"]  # fallback if no years found in data
BASE_YEAR_FOR_POINTS = "2025"     # 2025 is the master year for rates

DEFAULT_POINTS = {
    "Mon-Thu": 100,
    "Fri-Sat": 200,
    "Sun": 150,
    "Sun-Thu": 120
}

DAY_TYPES = ["Sun", "Mon-Thu", "Fri-Sat", "Sun-Thu"]


# ----------------------------------------------------------------------
# WIDGET KEY HELPER (RESORT-SCOPED)
# ----------------------------------------------------------------------
def rk(resort_id: str, *parts: str) -> str:
    """
    Build a unique Streamlit widget key scoped to a resort.
    Example: rk("ko-olina", "season", "2025", "0", "start", "0")
    """
    safe_resort = resort_id or "resort"
    return "__".join([safe_resort] + [str(p) for p in parts])


# ----------------------------------------------------------------------
# PAGE CONFIG & STYLES
# ----------------------------------------------------------------------
def setup_page():
    st.set_page_config(page_title="MVC Resort Editor (V2)", layout="wide")
    st.markdown("""
    <style>
        .big-font { font-size: 42px !important; font-weight: bold; color: #1f77b4; }
        .stButton>button { min-height: 50px; font-weight: bold; }
        .success-box { background: #d4edda; padding: 20px; border-radius: 12px; border: 2px solid #c3e6cb; margin: 20px 0; font-weight: bold; text-align: center; font-size: 18px; }
        .section-header { border-bottom: 2px solid #1f77b4; padding-bottom: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# SESSION STATE MANAGEMENT
# ----------------------------------------------------------------------
def initialize_session_state():
    defaults = {
        'refresh_trigger': False,
        'last_upload_sig': None,
        'data': None,                 # full V2 JSON
        'current_resort_id': None,    # resort.id
        'previous_resort_id': None,
        'working_resorts': {},        # id -> deep copy of resort dict
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
        if elapsed < 2:
            st.sidebar.success("✓ Saved", icon="✅")


def reset_state_for_new_file():
    for k in ["data", "current_resort_id", "previous_resort_id",
              "working_resorts", "delete_confirm", "last_save_time"]:
        if k == "working_resorts":
            st.session_state[k] = {}
        else:
            st.session_state[k] = None


# ----------------------------------------------------------------------
# BASIC HELPERS (V2)
# ----------------------------------------------------------------------
def get_years_from_data(data: Dict[str, Any]) -> List[str]:
    """Derive list of years from global_holidays or resort years."""
    years: Set[str] = set()
    gh = data.get("global_holidays", {})
    years.update(gh.keys())
    for r in data.get("resorts", []):
        for y in r.get("years", {}).keys():
            years.add(str(y))
    if not years:
        return DEFAULT_YEARS
    return sorted(years)


def safe_date(d: Optional[str], default: str = "2025-01-01") -> date:
    if not d or not isinstance(d, str):
        return datetime.strptime(default, "%Y-%m-%d").date()
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(d.strip(), fmt).date()
        except ValueError:
            continue
    return datetime.strptime(default, "%Y-%m-%d").date()


def get_resort_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return data.get("resorts", [])


def find_resort_by_id(data: Dict[str, Any], rid: str) -> Optional[Dict[str, Any]]:
    for r in data.get("resorts", []):
        if r.get("id") == rid:
            return r
    return None


def find_resort_index(data: Dict[str, Any], rid: str) -> Optional[int]:
    for i, r in enumerate(data.get("resorts", [])):
        if r.get("id") == rid:
            return i
    return None


def generate_resort_id(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or "resort"


def generate_resort_code(name: str) -> str:
    parts = [p for p in name.replace("’", "'").split() if p]
    initials = "".join(p[0].upper() for p in parts[:3])
    return initials or "RST"


# ----------------------------------------------------------------------
# FILE UPLOAD/DOWNLOAD (V2)
# ----------------------------------------------------------------------
def handle_file_upload():
    uploaded = st.file_uploader("Upload V2 data.json", type="json", key="file_uploader")
    if uploaded:
        size = getattr(uploaded, "size", 0)
        current_sig = f"{uploaded.name}:{size}"
        if current_sig != st.session_state.last_upload_sig:
            try:
                raw_data = json.load(uploaded)
                if "schema_version" not in raw_data or not raw_data.get("resorts"):
                    st.error("❌ This does not look like a V2 file (missing schema_version or resorts).")
                    return
                reset_state_for_new_file()
                st.session_state.data = raw_data
                st.session_state.last_upload_sig = current_sig
                resorts_list = get_resort_list(raw_data)
                st.success(f"✅ Loaded {len(resorts_list)} resorts (V2 schema)")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")


def create_download_button_v2(data: Dict[str, Any]):
    if data:
        json_data = json.dumps(copy.deepcopy(data), indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download V2 Data",
            data=json_data,
            file_name="data_v2.json",
            mime="application/json",
            key="download_v2_btn",
            help="Download the current V2 data in memory"
        )


def handle_file_verification():
    st.sidebar.markdown("### Verify Downloaded File")
    verify_upload = st.sidebar.file_uploader(
        "Upload data_v2.json to verify",
        type="json",
        key="verify_uploader"
    )
    if verify_upload:
        try:
            uploaded_data = json.load(verify_upload)
            current_json = json.dumps(st.session_state.data, sort_keys=True, ensure_ascii=False)
            uploaded_json = json.dumps(uploaded_data, sort_keys=True, ensure_ascii=False)
            if current_json == uploaded_json:
                st.sidebar.success("✅ The uploaded file matches the current data in memory.")
            else:
                st.sidebar.error("❌ The uploaded file does NOT match.")
        except json.JSONDecodeError:
            st.sidebar.error("❌ Invalid JSON file uploaded.")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")


# ----------------------------------------------------------------------
# MERGE FROM ANOTHER V2 FILE
# ----------------------------------------------------------------------
def handle_merge_from_another_file_v2(data: Dict[str, Any]):
    st.sidebar.markdown("### Merge from Another V2 File")
    merge_upload = st.sidebar.file_uploader(
        "Upload another V2 data.json to merge resorts from",
        type="json",
        key="merge_uploader_v2"
    )

    if merge_upload:
        try:
            merge_data = json.load(merge_upload)
            if "resorts" not in merge_data:
                st.sidebar.error("❌ Uploaded file does not look like a V2 schema (no 'resorts').")
                return

            target_resorts = data.setdefault("resorts", [])
            existing_ids = {r.get("id") for r in target_resorts}

            merge_resorts = merge_data.get("resorts", [])
            if not merge_resorts:
                st.sidebar.warning("No resorts found in uploaded file.")
                return

            display_map = {
                f"{r.get('display_name', r.get('id'))} ({r.get('id')})": r
                for r in merge_resorts
            }

            selection_labels = list(display_map.keys())
            selected_labels = st.sidebar.multiselect(
                "Select resorts to merge",
                selection_labels,
                key="selected_merge_resorts_v2"
            )

            if selected_labels and st.sidebar.button("Merge Selected Resorts", key="merge_btn_v2"):
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
                    st.sidebar.success(f"✅ Merged {merged_count} resort(s)")
                if skipped:
                    st.sidebar.warning(
                        "Skipped existing resorts: " + ", ".join(skipped)
                    )
                st.rerun()

        except json.JSONDecodeError:
            st.sidebar.error("❌ Invalid JSON file uploaded.")
        except Exception as e:
            st.sidebar.error(f"❌ Error during merge: {str(e)}")


# ----------------------------------------------------------------------
# RESORT MANAGEMENT (V2)
# ----------------------------------------------------------------------
def render_resort_grid(resorts: List[Dict[str, Any]], current_resort_id: Optional[str]):
    st.subheader("🏨 Select Resort")
    cols = st.columns(6)
    for i, resort in enumerate(resorts):
        rid = resort.get("id")
        name = resort.get("display_name", rid or f"Resort {i+1}")
        with cols[i % 6]:
            button_type = "primary" if current_resort_id == rid else "secondary"
            if st.button(name, key=f"resort_btn_{rid}", type=button_type):
                st.session_state.current_resort_id = rid
                st.session_state.delete_confirm = False
                st.rerun()


def is_duplicate_resort_name(name: str, resorts: List[Dict[str, Any]]) -> bool:
    target = name.strip().lower()
    for r in resorts:
        if r.get("display_name", "").strip().lower() == target:
            return True
    return False


def handle_resort_creation_v2(data: Dict[str, Any]):
    resorts = data.setdefault("resorts", [])
    with st.expander("➕ Add / Clone Resort", expanded=True):
        new_name = st.text_input("Resort Name", placeholder="Pulse San Francisco", key="new_resort_name")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Create Blank", key="create_blank_btn") and new_name:
                name = new_name.strip()
                if not name:
                    st.error("Resort name cannot be empty")
                elif is_duplicate_resort_name(name, resorts):
                    st.error("❌ Resort name already exists")
                else:
                    rid = generate_resort_id(name)
                    code = generate_resort_code(name)
                    new_resort = {
                        "id": rid,
                        "display_name": name,
                        "code": code,
                        "region": "Unknown",
                        "timezone": "UTC",
                        "years": {}
                    }
                    resorts.append(new_resort)
                    st.session_state.current_resort_id = rid
                    save_data()
                    st.rerun()

        with col2:
            existing_names = [r.get("display_name", r.get("id")) for r in resorts]
            source_name = st.selectbox("Clone From", [""] + existing_names, key="clone_source_resort")
            if st.button("Clone Current", key="clone_resort_btn") and new_name and source_name:
                name = new_name.strip()
                if not name:
                    st.error("Resort name cannot be empty")
                elif is_duplicate_resort_name(name, resorts):
                    st.error("❌ Resort name already exists")
                else:
                    src = None
                    for r in resorts:
                        if r.get("display_name") == source_name:
                            src = r
                            break
                    if src is None:
                        st.error("Source resort not found")
                    else:
                        rid = generate_resort_id(name)
                        code = generate_resort_code(name)
                        cloned = copy.deepcopy(src)
                        cloned["id"] = rid
                        cloned["display_name"] = name
                        cloned["code"] = code
                        resorts.append(cloned)
                        st.session_state.current_resort_id = rid
                        save_data()
                        st.success(f"✅ Cloned **{source_name}** → **{name}**")
                        st.rerun()


def handle_resort_deletion_v2(data: Dict[str, Any], current_resort_id: Optional[str]):
    if not current_resort_id:
        return
    resorts = data.get("resorts", [])
    current_resort = find_resort_by_id(data, current_resort_id)
    if not current_resort:
        return

    if not st.session_state.delete_confirm:
        if st.button("🗑️ Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        name = current_resort.get("display_name", current_resort_id)
        st.warning(f"⚠️ Are you sure you want to permanently delete **{name}**?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔥 DELETE FOREVER", key=f"delete_resort_final_{current_resort_id}", type="primary"):
                idx = find_resort_index(data, current_resort_id)
                if idx is not None:
                    resorts.pop(idx)
                st.session_state.current_resort_id = None
                st.session_state.delete_confirm = False
                st.session_state.working_resorts.pop(current_resort_id, None)
                save_data()
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"delete_cancel_{current_resort_id}"):
                st.session_state.delete_confirm = False
                st.rerun()

    if st.session_state.delete_confirm:
        st.stop()


# ----------------------------------------------------------------------
# WORKING RESORT MANAGEMENT (V2)
# ----------------------------------------------------------------------
def handle_resort_switch_v2(data: Dict[str, Any], current_resort_id: Optional[str], previous_resort_id: Optional[str]):
    if previous_resort_id and previous_resort_id != current_resort_id:
        working_resorts = st.session_state.working_resorts
        if previous_resort_id in working_resorts:
            working = working_resorts[previous_resort_id]
            committed = find_resort_by_id(data, previous_resort_id)
            if committed is None:
                # resort was deleted
                working_resorts.pop(previous_resort_id, None)
            else:
                if working != committed:
                    st.warning(f"You have unsaved changes in {committed.get('display_name', previous_resort_id)}.")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Save Changes", key="switch_save_prev"):
                            commit_working_to_data_v2(data, working, previous_resort_id)
                            del working_resorts[previous_resort_id]
                            st.session_state.previous_resort_id = current_resort_id
                            st.rerun()
                    with col2:
                        if st.button("Discard Changes", key="switch_discard_prev"):
                            del working_resorts[previous_resort_id]
                            st.session_state.previous_resort_id = current_resort_id
                            st.rerun()
                    with col3:
                        if st.button("Cancel Switch", key="switch_cancel_prev"):
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
        if st.button("💾 Save Resort Changes", type="primary", key=f"save_resort_{resort_id}"):
            commit_working_to_data_v2(data, working, resort_id)
            st.session_state.working_resorts.pop(resort_id, None)
            st.rerun()


# ----------------------------------------------------------------------
# SEASON DATES & ROOM POINTS (V2)
# ----------------------------------------------------------------------
def ensure_year_structure(resort: Dict[str, Any], year: str):
    years = resort.setdefault("years", {})
    year_obj = years.setdefault(year, {})
    year_obj.setdefault("seasons", [])
    year_obj.setdefault("holidays", [])
    return year_obj


def render_season_dates_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.subheader("📅 Season Dates (per Year)")
    for year in years:
        year_obj = ensure_year_structure(working, year)
        seasons = year_obj.get("seasons", [])
        with st.expander(f"{year} Seasons", expanded=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_season_name = st.text_input(
                    f"New season name ({year})",
                    key=rk(resort_id, "new_season", year)
                )
            with col2:
                if st.button("Add Season", key=rk(resort_id, "add_season", year)) and new_season_name:
                    seasons.append({
                        "name": new_season_name.strip(),
                        "periods": [],
                        "day_categories": {}
                    })
                    st.rerun()

            for idx, season in enumerate(seasons):
                render_single_season_v2(year_obj, year, season, idx, resort_id)


def render_single_season_v2(year_obj: Dict[str, Any], year: str,
                            season: Dict[str, Any], idx: int, resort_id: str):
    st.markdown(f"**{season.get('name', f'Season {idx+1}')}**")
    periods = season.setdefault("periods", [])

    new_name = st.text_input(
        "Season Name",
        value=season.get("name", ""),
        key=rk(resort_id, "season_name", year, idx)
    )
    if new_name != season.get("name"):
        season["name"] = new_name

    for r_idx, p in enumerate(periods):
        start_str = p.get("start")
        end_str = p.get("end")
        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            new_start = st.date_input(
                "Start",
                safe_date(start_str or f"{year}-01-01"),
                key=rk(resort_id, "season", year, idx, "start", r_idx)
            )
        with col2:
            new_end = st.date_input(
                "End",
                safe_date(end_str or f"{year}-01-07"),
                key=rk(resort_id, "season", year, idx, "end", r_idx)
            )
        with col3:
            if st.button("X", key=rk(resort_id, "season", year, idx, "del", r_idx)):
                periods.pop(r_idx)
                st.rerun()

        if new_start.isoformat() != start_str or new_end.isoformat() != end_str:
            p["start"] = new_start.isoformat()
            p["end"] = new_end.isoformat()

    if st.button("+ Add Range", key=rk(resort_id, "season", year, idx, "add_range")):
        periods.append({
            "start": f"{year}-01-01",
            "end": f"{year}-01-07"
        })
        st.rerun()


# ----------------------------------------------------------------------
# ROOM TYPE HELPERS
# ----------------------------------------------------------------------
def get_all_room_types_for_resort(working: Dict[str, Any]) -> List[str]:
    rooms: Set[str] = set()
    for year, year_obj in working.get("years", {}).items():
        for season in year_obj.get("seasons", []):
            dc = season.get("day_categories", {})
            for cat in dc.values():
                rp = cat.get("room_points", {})
                if isinstance(rp, dict):
                    rooms.update(rp.keys())
        for h in year_obj.get("holidays", []):
            rp = h.get("room_points", {})
            if isinstance(rp, dict):
                rooms.update(rp.keys())
    return sorted(rooms)


# ----------------------------------------------------------------------
# SYNC: ENFORCE SAME ROOMS & SAME POINTS ACROSS YEARS
# ----------------------------------------------------------------------
def sync_season_room_points_across_years(working: Dict[str, Any], base_year: str = BASE_YEAR_FOR_POINTS):
    """
    Enforce:
      1) The set of room types is the SAME for every season in every year.
      2) Points for a given season name are copied from the base year to all other years.

    Rules:
      - Canonical room set = union of all rooms in all seasons, all years.
      - We then ensure the base year contains all canonical rooms in all its day_categories.
      - Finally, for other years, for each season with the same name, we deep-copy
        the base year's day_categories (including room_points).
    """
    years = working.get("years", {})
    if not years or base_year not in years:
        return

    # 1) Canonical room set from ALL seasons in ALL years
    canonical_rooms: Set[str] = set()
    for y_obj in years.values():
        for season in y_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points", {})
                if isinstance(rp, dict):
                    canonical_rooms |= set(rp.keys())

    if not canonical_rooms:
        return

    base_year_obj = years[base_year]
    base_seasons = base_year_obj.get("seasons", [])

    # Helper: find a default value for a (cat_key, room) from any base season
    def find_default_for(cat_key: str, room: str) -> int:
        for s in base_seasons:
            dc2 = s.get("day_categories", {})
            if cat_key in dc2:
                rp2 = dc2[cat_key].get("room_points", {})
                if isinstance(rp2, dict) and room in rp2:
                    return int(rp2[room])
        return 0

    # 2) Ensure base-year seasons themselves have the full canonical room set
    for season in base_seasons:
        dc = season.setdefault("day_categories", {})
        for cat_key, cat in dc.items():
            rp = cat.setdefault("room_points", {})
            if not isinstance(rp, dict):
                cat["room_points"] = {}
                rp = cat["room_points"]
            # Add missing rooms
            for room in canonical_rooms:
                if room not in rp:
                    rp[room] = find_default_for(cat_key, room)

            # Remove stray rooms not in canonical (shouldn't really happen)
            for room in list(rp.keys()):
                if room not in canonical_rooms:
                    del rp[room]

    # Map base seasons by name, AFTER we have cleaned them
    base_by_name: Dict[str, Dict[str, Any]] = {
        s.get("name", ""): s for s in base_seasons if s.get("name")
    }

    # 3) For all other years, copy day_categories from base year for matching season names
    for year_name, year_obj in years.items():
        if year_name == base_year:
            continue
        for season in year_obj.get("seasons", []):
            name = season.get("name", "")
            if name in base_by_name:
                season["day_categories"] = copy.deepcopy(
                    base_by_name[name].get("day_categories", {})
                )


# ----------------------------------------------------------------------
# REFERENCE POINTS EDITOR (V2) – ENFORCING RULES
# ----------------------------------------------------------------------
def render_reference_points_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    """
    Edit room points:

    - Only BASE_YEAR_FOR_POINTS (2025) is editable.
    - Other years are read-only and auto-synced from 2025.
    - After any edit, sync_season_room_points_across_years() enforces:
        • same room set for every season
        • same points across years for same season name
    """
    st.subheader("🎯 Season Room Points (2025 is the master year)")
    st.caption("Edit rates in 2025 only. All other years will automatically mirror 2025 for the same season names and room types.")

    for year in years:
        year_obj = ensure_year_structure(working, year)
        seasons = year_obj.get("seasons", [])

        editable = (year == BASE_YEAR_FOR_POINTS)

        with st.expander(f"{year} – Seasons & Rates {'(editable)' if editable else '(mirrored from 2025)'}", expanded=(year == BASE_YEAR_FOR_POINTS)):
            if not seasons:
                st.info("No seasons defined yet for this year.")
                continue

            for s_idx, season in enumerate(seasons):
                st.markdown(f"**Season: {season.get('name', f'Season {s_idx+1}')}**")
                dc = season.setdefault("day_categories", {})
                if not dc:
                    # Default structure when user first adds a season
                    dc["sun_thu"] = {
                        "day_pattern": ["Sun", "Mon", "Tue", "Wed", "Thu"],
                        "room_points": {}
                    }
                    dc["fri_sat"] = {
                        "day_pattern": ["Fri", "Sat"],
                        "room_points": {}
                    }

                if editable:
                    # FULL editor (number inputs, add room, etc.)
                    all_rooms = get_all_room_types_for_resort(working)
                    for key, cat in dc.items():
                        st.write(f"- **Day Category Key:** `{key}`")
                        day_pattern = cat.setdefault("day_pattern", [])
                        room_points = cat.setdefault("room_points", {})
                        cols = st.columns(4)
                        st.caption(f"Days: {', '.join(day_pattern) if day_pattern else '(not set)'}")

                        rooms_here = sorted(room_points.keys())
                        if not rooms_here and all_rooms:
                            rooms_here = all_rooms

                        for j, room in enumerate(rooms_here):
                            with cols[j % 4]:
                                current_val = int(room_points.get(room, 0) or 0)
                                new_val = st.number_input(
                                    f"{room}",
                                    value=current_val,
                                    step=25,
                                    key=rk(resort_id, "rp", year, s_idx, key, room)
                                )
                                if new_val != current_val:
                                    room_points[room] = int(new_val)

                        new_room_name = st.text_input(
                            "Add Room Type",
                            key=rk(resort_id, "add_room", year, s_idx, key),
                            placeholder="e.g. 2-BDRM OV"
                        )
                        if st.button("Add Room", key=rk(resort_id, "btn_add_room", year, s_idx, key)) and new_room_name:
                            room_points.setdefault(new_room_name.strip(), DEFAULT_POINTS.get("Sun-Thu", 100))
                            st.rerun()
                else:
                    # READ-ONLY view for mirrored years
                    for key, cat in dc.items():
                        st.write(f"- **Day Category Key:** `{key}`")
                        day_pattern = cat.get("day_pattern", [])
                        rp = cat.get("room_points", {})
                        st.caption(f"Days: {', '.join(day_pattern) if day_pattern else '(not set)'}")
                        if not isinstance(rp, dict) or not rp:
                            st.write("_No room points (will be set once 2025 is filled)._")
                        else:
                            df = pd.DataFrame(
                                [{"Room": r, "Points": rp[r]} for r in sorted(rp.keys())]
                            )
                            st.dataframe(df, use_container_width=True, hide_index=True)

    # AFTER editing 2025, enforce uniform rooms + synced points
    sync_season_room_points_across_years(working, base_year=BASE_YEAR_FOR_POINTS)


# ----------------------------------------------------------------------
# HOLIDAY MANAGEMENT (V2 per Resort)
# ----------------------------------------------------------------------
def render_holiday_management_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.subheader("🎄 Resort Holiday Room Points (per Year)")
    all_rooms = get_all_room_types_for_resort(working)

    for year in years:
        year_obj = ensure_year_structure(working, year)
        holidays = year_obj.get("holidays", [])
        with st.expander(f"{year} Holidays", expanded=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_name = st.text_input(
                    f"New Holiday Name ({year})",
                    key=rk(resort_id, "new_holiday", year)
                )
            with col2:
                if st.button("Add Holiday", key=rk(resort_id, "btn_add_holiday", year)) and new_name:
                    holidays.append({
                        "name": new_name.strip(),
                        "global_reference": new_name.strip(),
                        "room_points": {}
                    })
                    st.rerun()

            for h_idx, h in enumerate(holidays):
                st.markdown(f"**{h.get('name', f'Holiday {h_idx+1}')}**")
                coln1, coln2, coln3 = st.columns([3, 3, 1])
                with coln1:
                    new_disp = st.text_input(
                        "Display Name",
                        value=h.get("name", ""),
                        key=rk(resort_id, "holiday_name", year, h_idx)
                    )
                    if new_disp != h.get("name"):
                        h["name"] = new_disp
                with coln2:
                    new_global = st.text_input(
                        "Global Reference",
                        value=h.get("global_reference", ""),
                        key=rk(resort_id, "holiday_global", year, h_idx)
                    )
                    if new_global != h.get("global_reference"):
                        h["global_reference"] = new_global
                with coln3:
                    if st.button("Delete", key=rk(resort_id, "holiday_del", year, h_idx)):
                        holidays.pop(h_idx)
                        st.rerun()

                room_points = h.setdefault("room_points", {})
                rooms_here = sorted(room_points.keys())
                if not rooms_here and all_rooms:
                    rooms_here = all_rooms

                cols = st.columns(4)
                for j, room in enumerate(rooms_here):
                    with cols[j % 4]:
                        current_val = int(room_points.get(room, 0) or 0)
                        new_val = st.number_input(
                            f"{room}",
                            value=current_val,
                            step=25,
                            key=rk(resort_id, "holiday_rp", year, h_idx, room)
                        )
                        if new_val != current_val:
                            room_points[room] = int(new_val)

                new_room_name = st.text_input(
                    "Add Room Type to Holiday",
                    key=rk(resort_id, "holiday_add_room", year, h_idx),
                    placeholder="e.g. 2-BDRM OV"
                )
                if st.button("Add Holiday Room", key=rk(resort_id, "holiday_add_room_btn", year, h_idx)) and new_room_name:
                    room_points.setdefault(new_room_name.strip(), 1500)
                    st.rerun()


# ----------------------------------------------------------------------
# RESORT SUMMARY – WEEKLY POINTS (7 NIGHTS) FOR V2
# ----------------------------------------------------------------------
def compute_weekly_totals_for_season_v2(season: Dict[str, Any], room_types: List[str]) -> Tuple[Dict[str, int], bool]:
    """
    Compute total points for a 7-night week for a single season using V2 schema.

    We look at season["day_categories"], each with:
      - "day_pattern": ["Sun", "Mon", ...]
      - "room_points": { room_type: nightly_points }

    For each category:
      weekly_points += nightly_points * len(day_pattern)

    This works for arbitrary patterns (Sun/Mon-Thu/Fri-Sat/etc).
    """
    weekly_totals = {room: 0 for room in room_types}
    any_data = False
    valid_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}

    day_cats = season.get("day_categories", {})
    for cat in day_cats.values():
        pattern = cat.get("day_pattern", [])
        rp = cat.get("room_points", {})
        if not isinstance(rp, dict):
            continue
        n_days = len([d for d in pattern if d in valid_days])
        if n_days <= 0:
            continue
        for room in room_types:
            if room in rp and rp[room] is not None:
                weekly_totals[room] += int(rp[room]) * n_days
                any_data = True

    return weekly_totals, any_data


def render_resort_summary_v2(working: Dict[str, Any]):
    """
    Compact summary:

    - Use a single 'reference year' (earliest year that has seasons).
    - One row per Season (in the order they appear in that year).
    - One column per room type.
    - Value = total points for a 7-night stay for that season.
    - Holidays are ignored.
    """
    st.subheader("📋 Resort Summary – Weekly Points (7 nights)")

    resort_years = working.get("years", {})
    if not resort_years:
        st.info("No year/season data defined yet for this resort.")
        return

    # Determine reference year: earliest year that has at least one season
    ref_year = None
    for y in sorted(resort_years.keys()):
        seasons = resort_years[y].get("seasons", [])
        if seasons:
            ref_year = y
            break

    if ref_year is None:
        st.info("No seasons with date/rate data to summarise.")
        return

    year_obj = resort_years[ref_year]
    seasons = year_obj.get("seasons", [])

    room_types = get_all_room_types_for_resort(working)
    if not room_types:
        st.info("No room types found in this resort.")
        return

    rows: List[Dict[str, Any]] = []
    for season in seasons:
        sname = season.get("name", "").strip() or "(Unnamed Season)"

        weekly_totals, any_data = compute_weekly_totals_for_season_v2(season, room_types)
        if not any_data:
            continue

        row: Dict[str, Any] = {"Season": sname}
        for room in room_types:
            row[room] = "" if weekly_totals[room] == 0 else weekly_totals[room]
        rows.append(row)

    if not rows:
        st.info("No usable rate data to compute weekly totals.")
        return

    df = pd.DataFrame(rows, columns=["Season"] + room_types)
    st.dataframe(df, use_container_width=True)


# ----------------------------------------------------------------------
# VALIDATION (V2)
# ----------------------------------------------------------------------
def validate_resort_data_v2(working: Dict[str, Any], data: Dict[str, Any], years: List[str]) -> List[str]:
    """
    Validate a single resort in pure V2 schema:
    - Overlapping seasons
    - Overlapping holidays
    - Overlaps between seasons and holidays
    - Gaps in coverage
    - Day-of-week coverage per season
    - Room coverage consistency across seasons & holidays
    - Global holiday references existence
    """
    issues: List[str] = []

    all_days = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
    all_rooms = set(get_all_room_types_for_resort(working))
    resort_years = working.get("years", {})
    global_holidays = data.get("global_holidays", {})

    for year in years:
        year_obj = resort_years.get(year, {})
        # ------------------------
        # SEASON RANGES
        # ------------------------
        season_ranges: List[Tuple[str, datetime, datetime]] = []
        for season in year_obj.get("seasons", []):
            sname = season.get("name", "(Unnamed Season)")
            for p in season.get("periods", []):
                start_str = p.get("start")
                end_str = p.get("end")
                try:
                    start = datetime.strptime(start_str, "%Y-%m-%d")
                    end = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)  # end-inclusive
                    season_ranges.append((sname, start, end))
                except Exception:
                    issues.append(f"[{year}] Invalid season range in '{sname}': {start_str} - {end_str}")

        season_ranges.sort(key=lambda x: x[1])
        for i in range(1, len(season_ranges)):
            prev_name, prev_start, prev_end = season_ranges[i - 1]
            curr_name, curr_start, curr_end = season_ranges[i]
            if curr_start < prev_end:
                issues.append(f"[{year}] Overlapping seasons: {prev_name} and {curr_name}")

        # ------------------------
        # HOLIDAY RANGES (from global_holidays)
        # ------------------------
        holiday_ranges: List[Tuple[str, datetime, datetime]] = []
        gh_year = global_holidays.get(year, {})
        for h in year_obj.get("holidays", []):
            disp_name = h.get("name", "(Unnamed Holiday)")
            global_ref = h.get("global_reference") or disp_name
            gh_obj = gh_year.get(global_ref)
            if not gh_obj:
                issues.append(f"[{year}] Holiday '{disp_name}' references missing global holiday '{global_ref}'")
                continue
            start_str = gh_obj.get("start_date")
            end_str = gh_obj.get("end_date")
            try:
                start = datetime.strptime(start_str, "%Y-%m-%d")
                end = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)
                holiday_ranges.append((disp_name, start, end))
            except Exception:
                issues.append(f"[{year}] Invalid global holiday dates for '{global_ref}': {start_str} - {end_str}")

        holiday_ranges.sort(key=lambda x: x[1])
        for i in range(1, len(holiday_ranges)):
            prev_name, prev_start, prev_end = holiday_ranges[i - 1]
            curr_name, curr_start, curr_end = holiday_ranges[i]
            if curr_start < prev_end:
                issues.append(f"[{year}] Overlapping holidays: {prev_name} and {curr_name}")

        # ------------------------
        # CROSS OVERLAPS (season vs holiday)
        # ------------------------
        for s_name, s_start, s_end in season_ranges:
            for h_name, h_start, h_end in holiday_ranges:
                if max(s_start, h_start) < min(s_end, h_end):
                    issues.append(f"[{year}] Overlap between season '{s_name}' and holiday '{h_name}'")

        # ------------------------
        # COVERAGE GAPS
        # ------------------------
        all_ranges = season_ranges + holiday_ranges
        if all_ranges:
            all_ranges.sort(key=lambda x: x[1])
            merged_start = all_ranges[0][1]
            merged_end = all_ranges[0][2]
            gaps: List[Tuple[datetime, datetime]] = []
            for _, start, end in all_ranges[1:]:
                if start <= merged_end:  # merge overlapping/adjacent
                    merged_end = max(merged_end, end)
                else:
                    gaps.append((merged_end, start - timedelta(days=1)))
                    merged_start = start
                    merged_end = end

            year_start = datetime(int(year), 1, 1)
            year_end = datetime(int(year), 12, 31) + timedelta(days=1)

            # NOTE: we now ignore gaps before the first defined block,
            # to allow Jan 1–2 to belong to previous year's schedule.
            if merged_end < year_end:
                gaps.append((merged_end, year_end - timedelta(days=1)))

            for gs, ge in gaps:
                issues.append(f"[{year}] Gap in coverage: {gs.date()} to {ge.date()}")
        else:
            issues.append(f"[{year}] No coverage at all (no seasons or holidays defined)")

        # ------------------------
        # DAY-OF-WEEK COVERAGE + ROOM CONSISTENCY
        # ------------------------
        for season in year_obj.get("seasons", []):
            sname = season.get("name", "(Unnamed Season)")
            day_cats = season.get("day_categories", {})
            covered_days: Set[str] = set()

            for key, cat in day_cats.items():
                pattern = cat.get("day_pattern", [])
                pattern_days = {d for d in pattern if d in all_days}
                overlap = covered_days & pattern_days
                if overlap:
                    issues.append(
                        f"[{year}] Season '{sname}' has overlapping day patterns "
                        f"({', '.join(sorted(overlap))}) in category '{key}'"
                    )
                covered_days |= pattern_days

            if covered_days != all_days:
                missing = all_days - covered_days
                if missing:
                    issues.append(
                        f"[{year}] Season '{sname}' does not cover full week; "
                        f"missing days: {', '.join(sorted(missing))}"
                    )

            # Room coverage for this season
            if all_rooms:
                season_rooms: Set[str] = set()
                for cat in day_cats.values():
                    rp = cat.get("room_points", {})
                    if isinstance(rp, dict):
                        season_rooms |= set(rp.keys())
                missing_rooms = all_rooms - season_rooms
                if missing_rooms:
                    issues.append(
                        f"[{year}] Season '{sname}' missing rooms in day_categories: "
                        f"{', '.join(sorted(missing_rooms))}"
                    )

        # Holiday room coverage
        if all_rooms:
            for h in year_obj.get("holidays", []):
                hname = h.get("name", "(Unnamed Holiday)")
                rp = h.get("room_points", {})
                if not isinstance(rp, dict):
                    issues.append(f"[{year}] Holiday '{hname}' has invalid room_points (not a dict)")
                    continue
                missing_rooms = all_rooms - set(rp.keys())
                if missing_rooms:
                    issues.append(
                        f"[{year}] Holiday '{hname}' missing rooms: "
                        f"{', '.join(sorted(missing_rooms))}"
                    )

    return issues


def render_validation_panel_v2(working: Dict[str, Any], data: Dict[str, Any], years: List[str]):
    """Render validation issues panel for a V2 resort."""
    with st.expander("🔍 Validation Check", expanded=False):
        issues = validate_resort_data_v2(working, data, years)
        if issues:
            st.error("Validation Issues Found:")
            for issue in issues:
                st.write(f"• {issue}")
        else:
            st.success("✓ No validation issues found")


# ----------------------------------------------------------------------
# GANTT CHART (V2)
# ----------------------------------------------------------------------
def create_gantt_chart_v2(working: Dict[str, Any], year: str, data: Dict[str, Any]) -> go.Figure:
    """Create a Gantt chart for seasons and holidays in V2 schema."""
    rows: List[Dict[str, Any]] = []
    resort_years = working.get("years", {})
    year_obj = resort_years.get(year, {})

    # Seasons
    for season in year_obj.get("seasons", []):
        sname = season.get("name", "(Unnamed Season)")
        for i, p in enumerate(season.get("periods", []), 1):
            start_str = p.get("start")
            end_str = p.get("end")
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                if start_dt <= end_dt:
                    rows.append({
                        "Task": f"{sname} #{i}",
                        "Start": start_dt,
                        "Finish": end_dt,
                        "Type": sname
                    })
            except Exception:
                continue

    # Holidays – using global_holidays dates
    gh_year = data.get("global_holidays", {}).get(year, {})
    for h in year_obj.get("holidays", []):
        disp_name = h.get("name", "(Unnamed Holiday)")
        global_ref = h.get("global_reference") or disp_name
        gh = gh_year.get(global_ref)
        if not gh:
            continue
        start_str = gh.get("start_date")
        end_str = gh.get("end_date")
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            if start_dt <= end_dt:
                rows.append({
                    "Task": disp_name,
                    "Start": start_dt,
                    "Finish": end_dt,
                    "Type": "Holiday"
                })
        except Exception:
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
        title=f"{working.get('display_name', 'Resort')} – Seasons & Holidays ({year})",
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


def render_gantt_charts_v2(working: Dict[str, Any], years: List[str], data: Dict[str, Any]):
    """Render Gantt charts for all years of a resort."""
    st.subheader("📊 Season & Holiday Timeline")
    tabs = st.tabs(years)
    for tab, year in zip(tabs, years):
        with tab:
            fig = create_gantt_chart_v2(working, year, data)
            st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------------------
# GLOBAL SETTINGS (V2)
# ----------------------------------------------------------------------
def render_maintenance_fees_v2(data: Dict[str, Any]):
    cfg = data.setdefault("configuration", {})
    rates = cfg.setdefault("maintenance_rates", {})
    st.caption("Edit maintenance fee rates (per point, per year)")
    for year in sorted(rates.keys()):
        current_rate = float(rates[year])
        new_rate = st.number_input(
            year, value=current_rate, step=0.01, format="%.4f", key=f"mf_{year}"
        )
        if new_rate != current_rate:
            rates[year] = float(new_rate)
            save_data()


def render_global_holiday_dates_editor_v2(data: Dict[str, Any], years: List[str]):
    st.subheader("🎅 Global Holidays (dates, type, regions)")
    global_holidays = data.setdefault("global_holidays", {})
    for year in years:
        st.write(f"**{year}**")
        holidays = global_holidays.setdefault(year, {})
        # existing holidays
        for i, (name, obj) in enumerate(list(holidays.items())):
            start = obj.get("start_date")
            end = obj.get("end_date")
            h_type = obj.get("type", "other")
            regions = obj.get("regions", [])

            st.markdown(f"*{name}*")
            col1, col2, col3, col4 = st.columns([3, 3, 3, 1])
            with col1:
                new_start = st.date_input(
                    "Start",
                    safe_date(start or f"{year}-01-01"),
                    key=f"ghs_{year}_{i}",
                    label_visibility="collapsed"
                )
            with col2:
                new_end = st.date_input(
                    "End",
                    safe_date(end or f"{year}-01-07"),
                    key=f"ghe_{year}_{i}",
                    label_visibility="collapsed"
                )
            with col3:
                new_type = st.text_input(
                    "Type",
                    value=h_type,
                    key=f"ght_{year}_{i}",
                    label_visibility="collapsed"
                )
            with col4:
                if st.button("Delete", key=f"ghd_{year}_{i}"):
                    del holidays[name]
                    save_data()
                    st.rerun()

            # regions editor (simple comma-separated)
            regions_str = ", ".join(regions) if regions else ""
            new_regions_str = st.text_input(
                "Regions (comma-separated)",
                value=regions_str,
                key=f"ghr_{year}_{i}"
            )

            obj["start_date"] = new_start.isoformat()
            obj["end_date"] = new_end.isoformat()
            obj["type"] = new_type or "other"
            obj["regions"] = [r.strip() for r in new_regions_str.split(",") if r.strip()]
            save_data()

        st.markdown("---")
        # add new holiday
        new_name = st.text_input(f"New Holiday Name ({year})", key=f"gh_new_name_{year}")
        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            new_start = st.date_input(
                "New Start Date",
                datetime.strptime(f"{year}-01-01", "%Y-%m-%d").date(),
                key=f"gh_new_start_{year}"
            )
        with col2:
            new_end = st.date_input(
                "New End Date",
                datetime.strptime(f"{year}-01-07", "%Y-%m-%d").date(),
                key=f"gh_new_end_{year}"
            )
        with col3:
            if st.button("Add Holiday", key=f"gh_add_{year}") and new_name and new_name not in holidays:
                holidays[new_name] = {
                    "start_date": new_start.isoformat(),
                    "end_date": new_end.isoformat(),
                    "type": "other",
                    "regions": ["global"]
                }
                save_data()
                st.rerun()


def render_global_settings_v2(data: Dict[str, Any], years: List[str]):
    st.header("⚙️ Global Settings (V2)")
    with st.expander("💰 Maintenance Fees", expanded=False):
        render_maintenance_fees_v2(data)
    with st.expander("🎅 Global Holiday Dates", expanded=False):
        render_global_holiday_dates_editor_v2(data, years)


# ----------------------------------------------------------------------
# MAIN APPLICATION (V2)
# ----------------------------------------------------------------------
def main():
    setup_page()
    initialize_session_state()

    # Auto-load optional local file if present (V2)
    if st.session_state.data is None:
        try:
            with open("data_v2.json", "r") as f:
                raw_data = json.load(f)
                if "schema_version" in raw_data and "resorts" in raw_data:
                    st.session_state.data = raw_data
                    st.info(f"✅ Automatically loaded {len(raw_data.get('resorts', []))} resorts from data_v2.json")
                else:
                    st.info("Found data_v2.json but it does not look like V2 schema.")
        except FileNotFoundError:
            st.info("No data_v2.json found for automatic load. Please upload a V2 file.")
        except Exception as e:
            st.error(f"❌ Error automatically loading data_v2.json: {e}")

    # Sidebar
    with st.sidebar:
        st.markdown("<p class='big-font'>File Operations (V2)</p>", unsafe_allow_html=True)
        handle_file_upload()
        if st.session_state.data:
            create_download_button_v2(st.session_state.data)
            handle_file_verification()
            handle_merge_from_another_file_v2(st.session_state.data)
        show_save_indicator()

    st.title("MVC Resort Editor – V2 Schema")
    st.caption("Edit seasons, holidays, and room points directly in V2 format • 2025 is the master year for rates")

    if not st.session_state.data:
        st.info("📁 Upload your V2 data.json file to start editing")
        return

    data = st.session_state.data
    resorts = get_resort_list(data)
    years = get_years_from_data(data)

    current_resort_id = st.session_state.current_resort_id
    previous_resort_id = st.session_state.previous_resort_id

    # Resort selector grid
    render_resort_grid(resorts, current_resort_id)

    # Handle resort switch
    handle_resort_switch_v2(data, current_resort_id, previous_resort_id)

    # Resort creation / cloning
    handle_resort_creation_v2(data)

    # Prepare working copy for current resort
    working = None
    if current_resort_id:
        working_resorts = st.session_state.working_resorts
        if current_resort_id not in working_resorts:
            resort_obj = find_resort_by_id(data, current_resort_id)
            if resort_obj:
                working_resorts[current_resort_id] = copy.deepcopy(resort_obj)
        working = working_resorts.get(current_resort_id)

    # Resort-specific editing
    if working:
        name = working.get("display_name", current_resort_id)
        st.markdown(f"### **{name}**")

        # Validation panel
        render_validation_panel_v2(working, data, years)

        # Save button
        render_save_button_v2(data, working, current_resort_id)

        # Delete resort
        handle_resort_deletion_v2(data, current_resort_id)

        # Gantt charts
        render_gantt_charts_v2(working, years, data)

        # Season dates
        render_season_dates_editor_v2(working, years, current_resort_id)

        # Season room points (enforces your two rules)
        render_reference_points_editor_v2(working, years, current_resort_id)

        # Holiday room points per resort
        render_holiday_management_v2(working, years, current_resort_id)

        # Resort weekly summary (7 nights)
        render_resort_summary_v2(working)

    # Global settings at bottom
    render_global_settings_v2(data, years)

    st.markdown("""
    <div class='success-box'>
        V2 MODE • 2025 as master rate year • Same room types across all seasons • Points synced across years
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
