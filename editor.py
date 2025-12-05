import streamlit as st
from common.ui import render_resort_card, render_resort_selector, render_page_header
from common.charts import render_gantt, get_season_bucket
from functools import lru_cache
import json
import pandas as pd
import copy
import re
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Set

# ----------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------
DEFAULT_YEARS = ["2025", "2026"]
BASE_YEAR_FOR_POINTS = "2025"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ----------------------------------------------------------------------
# WIDGET KEY HELPER
# ----------------------------------------------------------------------
@lru_cache(maxsize=1024)
def rk(resort_id: str, *parts: str) -> str:
    """Build a unique Streamlit widget key scoped to a resort."""
    safe_resort = resort_id or "resort"
    return "__".join([safe_resort] + [str(p) for p in parts])

# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
def initialize_session_state():
    defaults = {
        "refresh_trigger": False,
        "last_upload_sig": None,
        "data": None,
        "current_resort_id": None,
        "previous_resort_id": None,
        "working_resorts": {},
        "last_save_time": None,
        "delete_confirm": False,
        "download_verified": False, 
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def save_data():
    st.session_state.last_save_time = datetime.now()

def reset_state_for_new_file():
    for k in [
        "data",
        "current_resort_id",
        "previous_resort_id",
        "working_resorts",
        "delete_confirm",
        "last_save_time",
        "download_verified",
    ]:
        st.session_state[k] = {} if k == "working_resorts" else None
        if k == "download_verified":
            st.session_state[k] = False

# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------
def detect_timezone_from_name(name: str) -> str:
    return "UTC"

def get_resort_full_name(resort_id: str, display_name: str) -> str:
    return display_name

def get_years_from_data(data: Dict[str, Any]) -> List[str]:
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
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return re.sub(r"-+", "-", slug).strip("-") or "resort"

def generate_resort_code(name: str) -> str:
    parts = [p for p in name.replace("'", "'").split() if p]
    return "".join(p[0].upper() for p in parts[:3]) or "RST"

def make_unique_resort_id(base_id: str, resorts: List[Dict[str, Any]]) -> str:
    existing = {r.get("id") for r in resorts}
    if base_id not in existing: return base_id
    i = 2
    while f"{base_id}-{i}" in existing: i += 1
    return f"{base_id}-{i}"

def sanitize_loaded_data(data: Dict[str, Any]) -> Dict[str, Any]:
    # Fix Day Patterns
    for r in data.get("resorts", []):
        for y_obj in r.get("years", {}).values():
            for s in y_obj.get("seasons", []):
                dc = s.get("day_categories", {})
                if not dc:
                    s["day_categories"] = {
                        "sun_thu": {"day_pattern": ["Sun", "Mon", "Tue", "Wed", "Thu"], "room_points": {}},
                        "fri_sat": {"day_pattern": ["Fri", "Sat"], "room_points": {}}
                    }
                else:
                    for cat_key, cat_val in dc.items():
                        if "day_pattern" not in cat_val or not cat_val["day_pattern"]:
                            if "fri" in cat_key.lower() or "sat" in cat_key.lower():
                                cat_val["day_pattern"] = ["Fri", "Sat"]
                            else:
                                cat_val["day_pattern"] = ["Sun", "Mon", "Tue", "Wed", "Thu"]
    # Fix Global Holidays
    gh = data.get("global_holidays", {})
    if isinstance(gh, dict):
        for year, holidays in gh.items():
            if isinstance(holidays, list):
                new_dict = {}
                for h in holidays:
                    if isinstance(h, str):
                        new_dict[h] = {"start_date": f"{year}-01-01", "end_date": f"{year}-01-01"}
                    elif isinstance(h, dict):
                        name = h.get("name", "Unnamed")
                        if "start_date" not in h:
                            h["start_date"] = h.get("date", f"{year}-01-01")
                        if "end_date" not in h:
                            h["end_date"] = h["start_date"]
                        new_dict[name] = h
                gh[year] = new_dict
    return data

# ----------------------------------------------------------------------
# FILE OPERATIONS
# ----------------------------------------------------------------------
def handle_file_upload():
    st.sidebar.markdown("### 📤 File to Memory")
    with st.sidebar.expander("📤 Load", expanded=False):
        uploaded = st.file_uploader("Choose JSON file", type="json", key="file_uploader")
        if uploaded:
            size = getattr(uploaded, "size", 0)
            current_sig = f"{uploaded.name}:{size}"
            if current_sig != st.session_state.last_upload_sig:
                try:
                    raw_data = json.load(uploaded)
                    clean_data = sanitize_loaded_data(raw_data)
                    reset_state_for_new_file()
                    st.session_state.data = clean_data
                    st.session_state.last_upload_sig = current_sig
                    resorts_list = get_resort_list(clean_data)
                    st.success(f"✅ Loaded {len(resorts_list)} resorts")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

def create_download_button_v2(data: Dict[str, Any]):
    st.sidebar.markdown("### 📥 Memory to File")
    if "download_verified" not in st.session_state:
        st.session_state.download_verified = False
    with st.sidebar.expander("💾 Save & Download", expanded=False):
        current_id = st.session_state.get("current_resort_id")
        working_resorts = st.session_state.get("working_resorts", {})
        has_unsaved_changes = False
        if current_id and current_id in working_resorts:
            working_copy = working_resorts[current_id]
            committed_copy = find_resort_by_id(data, current_id)
            if committed_copy != working_copy:
                has_unsaved_changes = True
        
        if has_unsaved_changes:
            st.session_state.download_verified = False
            st.warning("⚠️ Unsaved changes pending.")
            if st.button("🧠 COMMIT TO MEMORY", type="primary", use_container_width=True):
                commit_working_to_data_v2(data, working_resorts[current_id], current_id)
                st.toast("Committed.", icon="✅")
                st.rerun()
            st.caption("You must commit changes to memory before proceeding.")
        elif not st.session_state.download_verified:
            st.info("ℹ️ Memory updated.")
            if st.button("🔍 Verify memory", use_container_width=True):
                st.session_state.download_verified = True
                st.rerun()
        else:
            st.success("✅ Ready.")
            filename = st.text_input("File name", value="data_v2.json", key="download_filename_input").strip()
            if not filename: filename = "data_v2.json"
            if not filename.lower().endswith(".json"): filename += ".json"
            json_data = json.dumps(data, indent=2, ensure_ascii=False)
            st.download_button("⬇️ DOWNLOAD JSON", data=json_data, file_name=filename, mime="application/json", key="download_v2_btn", type="primary", use_container_width=True)

def handle_file_verification():
    with st.sidebar.expander("🔍 Verify File", expanded=False):
        verify_upload = st.file_uploader("Upload file to compare", type="json", key="verify_uploader")
        if verify_upload:
            try:
                uploaded_data = json.load(verify_upload)
                current_json = json.dumps(st.session_state.data, sort_keys=True)
                uploaded_json = json.dumps(sanitize_loaded_data(uploaded_data), sort_keys=True)
                if current_json == uploaded_json: st.success("✅ Match.")
                else: st.error("❌ Mismatch.")
            except Exception as e: st.error(f"❌ Error: {str(e)}")

def handle_merge_from_another_file_v2(data: Dict[str, Any]):
    with st.sidebar.expander("🔀 Merge", expanded=False):
        merge_upload = st.file_uploader("File with resorts", type="json", key="merge_uploader_v2")
        if merge_upload:
            try:
                merge_data = sanitize_loaded_data(json.load(merge_upload))
                target_resorts = data.setdefault("resorts", [])
                existing_ids = {r.get("id") for r in target_resorts}
                merge_resorts = merge_data.get("resorts", [])
                display_map = {f"{r.get('display_name', r.get('id'))} ({r.get('id')})": r for r in merge_resorts}
                selected_labels = st.multiselect("Select resorts", list(display_map.keys()), key="selected_merge_resorts_v2")
                if selected_labels and st.button("🔀 Merge", key="merge_btn_v2", use_container_width=True):
                    merged_count = 0
                    for label in selected_labels:
                        resort_obj = display_map[label]
                        rid = resort_obj.get("id")
                        if rid in existing_ids: continue
                        target_resorts.append(copy.deepcopy(resort_obj))
                        existing_ids.add(rid)
                        merged_count += 1
                    save_data()
                    if merged_count: st.success(f"✅ Merged {merged_count} resort(s)")
                    st.rerun()
            except Exception as e: st.error(f"❌ Error: {str(e)}")

# ----------------------------------------------------------------------
# RESORT MANAGEMENT
# ----------------------------------------------------------------------
def is_duplicate_resort_name(name: str, resorts: List[Dict[str, Any]]) -> bool:
    target = name.strip().lower()
    return any(r.get("display_name", "").strip().lower() == target for r in resorts)

def handle_resort_creation_v2(data: Dict[str, Any], current_resort_id: Optional[str]):
    resorts = data.setdefault("resorts", [])
    with st.expander("➕ Create or Clone Resort", expanded=False):
        tab_new, tab_clone = st.tabs(["✨ New Blank", "📋 Clone Current"])
        with tab_new:
            new_name = st.text_input("New Resort Name", key="new_resort_name_blank")
            if st.button("Create Blank Resort", use_container_width=True):
                if new_name and not is_duplicate_resort_name(new_name, resorts):
                    base_id = generate_resort_id(new_name)
                    rid = make_unique_resort_id(base_id, resorts)
                    new_resort = {
                        "id": rid, "display_name": new_name, "code": generate_resort_code(new_name),
                        "resort_name": new_name, "address": "", "timezone": "UTC", "years": {},
                    }
                    resorts.append(new_resort)
                    st.session_state.current_resort_id = rid
                    save_data()
                    st.rerun()
        with tab_clone:
            if current_resort_id:
                if st.button("📋 Clone This Resort", use_container_width=True):
                    src = find_resort_by_id(data, current_resort_id)
                    if src:
                        new_name = f"{src.get('display_name')} (Copy)"
                        counter = 1
                        while is_duplicate_resort_name(new_name, resorts):
                            counter += 1
                            new_name = f"{src.get('display_name')} (Copy {counter})"
                        cloned = copy.deepcopy(src)
                        cloned["id"] = make_unique_resort_id(generate_resort_id(new_name), resorts)
                        cloned["display_name"] = new_name
                        cloned["code"] = generate_resort_code(new_name)
                        cloned["resort_name"] = new_name
                        resorts.append(cloned)
                        st.session_state.current_resort_id = cloned["id"]
                        save_data()
                        st.rerun()

def handle_resort_deletion_v2(data: Dict[str, Any], current_resort_id: Optional[str]):
    if not current_resort_id: return
    if not st.session_state.delete_confirm:
        if st.button("🗑️ Delete Resort", key="delete_resort_init", type="secondary"):
            st.session_state.delete_confirm = True
            st.rerun()
    else:
        st.warning("Are you sure? This cannot be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔥 DELETE FOREVER", key="del_final", type="primary", use_container_width=True):
                idx = find_resort_index(data, current_resort_id)
                if idx is not None: data.get("resorts", []).pop(idx)
                st.session_state.current_resort_id = None
                st.session_state.delete_confirm = False
                st.session_state.working_resorts.pop(current_resort_id, None)
                save_data()
                st.rerun()
        with c2:
            if st.button("Cancel", key="del_cancel", use_container_width=True):
                st.session_state.delete_confirm = False
                st.rerun()
        st.stop()

def handle_resort_switch_v2(data: Dict[str, Any], current_resort_id: Optional[str], previous_resort_id: Optional[str]):
    if previous_resort_id and previous_resort_id != current_resort_id:
        working_resorts = st.session_state.working_resorts
        if previous_resort_id in working_resorts:
            working = working_resorts[previous_resort_id]
            committed = find_resort_by_id(data, previous_resort_id)
            if committed and working != committed:
                st.warning(f"⚠️ Unsaved changes in {committed.get('display_name')}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Save", key="sw_save", use_container_width=True):
                        commit_working_to_data_v2(data, working, previous_resort_id)
                        del working_resorts[previous_resort_id]
                        st.session_state.previous_resort_id = current_resort_id
                        st.rerun()
                with c2:
                    if st.button("Discard", key="sw_discard", use_container_width=True):
                        del working_resorts[previous_resort_id]
                        st.session_state.previous_resort_id = current_resort_id
                        st.rerun()
                with c3:
                    if st.button("Stay", key="sw_stay", use_container_width=True):
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
        st.caption("Changes are in working memory. Switch resorts to save.")
    else:
        st.caption("Working memory is clean.")

def load_resort(data: Dict[str, Any], current_resort_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not current_resort_id: return None
    working_resorts = st.session_state.working_resorts
    if current_resort_id not in working_resorts:
        if resort_obj := find_resort_by_id(data, current_resort_id):
            working_resorts[current_resort_id] = copy.deepcopy(resort_obj)
    return working_resorts.get(current_resort_id)

def edit_resort_basics(working: Dict[str, Any], resort_id: str):
    st.markdown("### Basic Info")
    c1, c2 = st.columns([3, 1])
    with c1:
        working["display_name"] = st.text_input("Display Name", value=working.get("display_name", ""), key=rk(resort_id, "dn"))
    with c2:
        working["code"] = st.text_input("Code", value=working.get("code", ""), key=rk(resort_id, "cd"))
    working["resort_name"] = st.text_input("Official Name", value=working.get("resort_name", ""), key=rk(resort_id, "rn"))
    c3, c4 = st.columns(2)
    with c3:
        working["timezone"] = st.text_input("Timezone", value=working.get("timezone", "UTC"), key=rk(resort_id, "tz"))
    with c4:
        working["address"] = st.text_area("Address", value=working.get("address", ""), key=rk(resort_id, "ad"), height=100)
    
    if st.button("Save Overview Changes", key=rk(resort_id, "save_ov")):
        commit_working_to_data_v2(st.session_state.data, working, resort_id)
        st.toast("Overview Saved!")

# ----------------------------------------------------------------------
# HOLIDAY HELPERS (These were missing!)
# ----------------------------------------------------------------------
def get_all_holidays_for_resort(working: Dict[str, Any]) -> List[Dict[str, Any]]:
    holidays_map = {}
    for year_obj in working.get("years", {}).values():
        for h in year_obj.get("holidays", []):
            key = (h.get("global_reference") or h.get("name") or "").strip()
            if key and key not in holidays_map:
                holidays_map[key] = {
                    "name": h.get("name", key),
                    "global_reference": key,
                }
    return list(holidays_map.values())

def add_holiday_to_all_years(working: Dict[str, Any], holiday_name: str, global_ref: str):
    holiday_name = holiday_name.strip()
    global_ref = (global_ref or holiday_name).strip()
    if not holiday_name or not global_ref: return False
    years = working.get("years", {})
    for year_obj in years.values():
        holidays = year_obj.setdefault("holidays", [])
        if any((h.get("global_reference") or h.get("name") or "").strip() == global_ref for h in holidays):
            continue
        holidays.append({"name": holiday_name, "global_reference": global_ref, "room_points": {}})
    return True

def delete_holiday_from_all_years(working: Dict[str, Any], global_ref: str):
    global_ref = (global_ref or "").strip()
    if not global_ref: return False
    changed = False
    for year_obj in working.get("years", {}).values():
        holidays = year_obj.get("holidays", [])
        original_len = len(holidays)
        year_obj["holidays"] = [h for h in holidays if (h.get("global_reference") or h.get("name") or "").strip() != global_ref]
        if len(year_obj["holidays"]) < original_len: changed = True
    return changed

def rename_holiday_across_years(working: Dict[str, Any], old_global_ref: str, new_name: str, new_global_ref: str):
    old_global_ref = (old_global_ref or "").strip()
    new_name = (new_name or "").strip()
    new_global_ref = (new_global_ref or "").strip()
    if not old_global_ref or not new_name or not new_global_ref: return False
    changed = False
    for year_obj in working.get("years", {}).values():
        for h in year_obj.get("holidays", []):
            if ((h.get("global_reference") or h.get("name") or "").strip() == old_global_ref):
                h["name"] = new_name
                h["global_reference"] = new_global_ref
                changed = True
    return changed

# ----------------------------------------------------------------------
# SEASONS & POINTS
# ----------------------------------------------------------------------
def ensure_year_structure(resort: Dict[str, Any], year: str):
    years = resort.setdefault("years", {})
    year_obj = years.setdefault(year, {})
    year_obj.setdefault("seasons", [])
    year_obj.setdefault("holidays", [])
    return year_obj

def render_season_dates_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>📅 Season Dates</div>", unsafe_allow_html=True)
    for year in years:
        with st.expander(f"📆 {year} Seasons", expanded=True):
            c1, c2 = st.columns([4, 1])
            with c1: ns = st.text_input("New Season", key=rk(resort_id, "ns", year))
            with c2:
                if st.button("Add", key=rk(resort_id, "add_s", year)) and ns:
                    for y2 in years:
                        ensure_year_structure(working, y2).setdefault("seasons", []).append(
                            {"name": ns, "periods": [], "day_categories": {}}
                        )
                    st.rerun()

            year_obj = ensure_year_structure(working, year)
            for idx, season in enumerate(year_obj.get("seasons", [])):
                render_single_season_v2(working, year, season, idx, resort_id)

def render_single_season_v2(working: Dict[str, Any], year: str, season: Dict[str, Any], idx: int, resort_id: str):
    sname = season.get("name", f"Season {idx+1}")
    st.markdown(f"**🎯 {sname}**")
    
    periods = season.get("periods", [])
    df_data = [{"start": safe_date(p.get("start")), "end": safe_date(p.get("end"))} for p in periods]
    df = pd.DataFrame(df_data)
    
    wk = rk(resort_id, "se_edit", year, idx)
    edited_df = st.data_editor(
        df, key=wk, num_rows="dynamic", use_container_width=True,
        column_config={
            "start": st.column_config.DateColumn("Start Date", format="YYYY-MM-DD", required=True),
            "end": st.column_config.DateColumn("End Date", format="YYYY-MM-DD", required=True)
        },
        hide_index=True
    )
    if st.button("Save Dates", key=rk(resort_id, "save_se_btn", year, idx), use_container_width=True):
        new_periods = []
        for _, row in edited_df.iterrows():
            if pd.notnull(row["start"]) and pd.notnull(row["end"]):
                s_str = row["start"].isoformat() if hasattr(row["start"], 'isoformat') else str(row["start"])
                e_str = row["end"].isoformat() if hasattr(row["end"], 'isoformat') else str(row["end"])
                new_periods.append({"start": s_str, "end": e_str})
        season["periods"] = new_periods
        st.toast("Dates saved to working memory.", icon="💾")

    # Replaced delete logic with simple removal to match Grok version simplicity
    if st.button("🗑️ Delete Season", key=rk(resort_id, "del_s", year, idx)):
        ensure_year_structure(working, year)["seasons"].pop(idx)
        st.rerun()

def get_all_room_types_for_resort(working: Dict[str, Any]) -> List[str]:
    rooms = set()
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                if isinstance(rp := cat.get("room_points", {}), dict):
                    for k in rp.keys():
                        if k is not None: rooms.add(str(k))
        for h in year_obj.get("holidays", []):
            if isinstance(rp := h.get("room_points", {}), dict):
                for k in rp.keys():
                    if k is not None: rooms.add(str(k))
    return sorted(list(rooms))

def add_room_type_master(working: Dict[str, Any], room: str, base_year: str):
    room = room.strip()
    if not room: return
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
        st.error("Names cannot be empty")
        return
    all_rooms = get_all_room_types_for_resort(working)
    if any(r.lower() == new_name.lower() and r != old_name for r in all_rooms):
        st.error("Name exists")
        return
    for year_obj in working.get("years", {}).values():
        for season in year_obj.get("seasons", []):
            for cat in season.get("day_categories", {}).values():
                rp = cat.get("room_points")
                if isinstance(rp, dict) and old_name in rp:
                    rp[new_name] = rp.pop(old_name)
        for h in year_obj.get("holidays", []):
            rp = h.get("room_points")
            if isinstance(rp, dict) and old_name in rp:
                rp[new_name] = rp.pop(old_name)
    st.success("Renamed!")

def sync_season_room_points_across_years(working: Dict[str, Any], base_year: str):
    years = working.get("years", {})
    if base_year not in years: return
    base_seasons = years[base_year].get("seasons", [])
    base_by_name = {s.get("name"): s for s in base_seasons if s.get("name")}
    for year_name, year_obj in years.items():
        if year_name != base_year:
            for season in year_obj.get("seasons", []):
                if (name := season.get("name", "")) in base_by_name:
                    season["day_categories"] = copy.deepcopy(base_by_name[name].get("day_categories", {}))

def render_reference_points_editor_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>🎯 Master Room Points</div>", unsafe_allow_html=True)
    base_year = BASE_YEAR_FOR_POINTS if BASE_YEAR_FOR_POINTS in years else (sorted(years)[0] if years else "2025")
    base_year_obj = ensure_year_structure(working, base_year)
    canonical_rooms = get_all_room_types_for_resort(working)

    c1, c2 = st.columns(2)
    with c1:
        nr = st.text_input("Add Room Type", key=rk(resort_id, "new_room"))
        if st.button("Add Room", key=rk(resort_id, "add_room_btn")) and nr:
             add_room_type_master(working, nr, base_year)
             st.rerun()
    with c2:
        del_room = st.selectbox("Delete Room", [""]+canonical_rooms, key=rk(resort_id, "del_room_sel"))
        if st.button("Delete Room") and del_room:
            delete_room_type_master(working, del_room)
            st.rerun()

    for s_idx, season in enumerate(base_year_obj.get("seasons", [])):
        with st.expander(f"🏖️ {season.get('name')}", expanded=True):
            dc = season.setdefault("day_categories", {})
            if not dc:
                dc["sun_thu"] = {"day_pattern": ["Sun", "Mon", "Tue", "Wed", "Thu"], "room_points": {}}
                dc["fri_sat"] = {"day_pattern": ["Fri", "Sat"], "room_points": {}}
            
            for key, cat in dc.items():
                st.markdown(f"**📅 {key}**")
                curr_days = cat.get("day_pattern", [])
                new_days = st.multiselect("Days", WEEKDAYS, default=curr_days, key=rk(resort_id, "dp", base_year, s_idx, key))
                cat["day_pattern"] = new_days

                rp = cat.setdefault("room_points", {})
                df_data = [{"Room Type": r, "Points": int(rp.get(r, 0) or 0)} for r in canonical_rooms]
                df = pd.DataFrame(df_data)
                
                wk = rk(resort_id, "rp_ed", base_year, s_idx, key)
                edited_df = st.data_editor(
                    df, key=wk, use_container_width=True, hide_index=True,
                    column_config={
                        "Room Type": st.column_config.TextColumn(disabled=True),
                        "Points": st.column_config.NumberColumn(min_value=0, step=25)
                    }
                )
                
                if st.button("Save Changes", key=rk(resort_id, "save_pts", base_year, s_idx, key), use_container_width=True):
                    new_rp = dict(zip(edited_df["Room Type"], edited_df["Points"]))
                    cat["room_points"] = new_rp
                    sync_season_room_points_across_years(working, base_year)
                    st.toast("Points Saved & Synced!", icon="💾")
                    st.rerun()
                st.divider()

def sync_holiday_room_points_across_years(working: Dict[str, Any], base_year: str):
    years = working.get("years", {})
    if not years or base_year not in years: return
    base_year_obj = ensure_year_structure(working, base_year)
    base_holidays = base_year_obj.get("holidays", [])
    base_map = { (h.get("global_reference") or h.get("name")): h for h in base_holidays }
    for year_name, year_obj in years.items():
        if year_name != base_year:
            for h in year_obj.get("holidays", []):
                if (key := (h.get("global_reference") or h.get("name") or "").strip()) in base_map:
                    h["room_points"] = copy.deepcopy(base_map[key].get("room_points", {}))

def render_holiday_management_v2(working: Dict[str, Any], years: List[str], resort_id: str):
    st.markdown("<div class='section-header'>🎄 Holiday Management</div>", unsafe_allow_html=True)
    base_year = BASE_YEAR_FOR_POINTS if BASE_YEAR_FOR_POINTS in years else (sorted(years)[0] if years else "2025")
    
    holidays_map = {}
    for y_obj in working.get("years", {}).values():
        for h in y_obj.get("holidays", []):
            k = h.get("global_reference") or h.get("name")
            if k and k not in holidays_map: holidays_map[k] = h

    if holidays_map:
        for k, h in holidays_map.items():
            c1, c2 = st.columns([3, 1])
            with c1: 
                new_display = st.text_input("Name", value=h.get("name"), key=rk(resort_id, "hn", k))
                if new_display != h.get("name"):
                    rename_holiday_across_years(working, k, new_display, h.get("global_reference"))
                    st.rerun()
            with c2: 
                 if st.button("🗑️", key=rk(resort_id, "hd", k)):
                     delete_holiday_from_all_years(working, k)
                     st.rerun()

    st.markdown("**➕ Add New Holiday**")
    c1, c2 = st.columns([3, 1])
    with c1: nh = st.text_input("Holiday Name", key=rk(resort_id, "new_h_name"))
    with c2:
        if st.button("Add", key=rk(resort_id, "add_h_btn")) and nh:
            add_holiday_to_all_years(working, nh, nh)
            st.rerun()
    
    st.markdown("---")
    st.markdown("**💰 Master Holiday Points**")
    
    base_year_obj = ensure_year_structure(working, base_year)
    canonical_rooms = get_all_room_types_for_resort(working)

    for idx, h in enumerate(base_year_obj.get("holidays", [])):
        with st.expander(f"🎊 {h.get('name')}", expanded=False):
            rp = h.setdefault("room_points", {})
            df_data = [{"Room Type": r, "Points": int(rp.get(r, 0) or 0)} for r in canonical_rooms]
            df = pd.DataFrame(df_data)
            wk = rk(resort_id, "hp_ed", base_year, idx)
            edited_df = st.data_editor(
                df, key=wk, use_container_width=True, hide_index=True,
                column_config={
                    "Room Type": st.column_config.TextColumn(disabled=True),
                    "Points": st.column_config.NumberColumn(min_value=0, step=25)
                }
            )
            if st.button("Save Changes", key=rk(resort_id, "save_h_pts", base_year, idx), use_container_width=True):
                new_rp = dict(zip(edited_df["Room Type"], edited_df["Points"]))
                h["room_points"] = new_rp
                sync_holiday_room_points_across_years(working, base_year)
                st.toast("Holiday points saved to working memory.", icon="💾")
                st.rerun()

# ----------------------------------------------------------------------
# GANTT CHART
# ----------------------------------------------------------------------
def render_gantt_charts_v2(working: Dict[str, Any], years: List[str], data: Dict[str, Any]):
    from common.charts import render_gantt, get_season_bucket
    st.markdown("<div class='section-header'>📊 Visual Timeline</div>", unsafe_allow_html=True)
    tabs = st.tabs([f"📅 {year}" for year in years])
    for tab, year in zip(tabs, years):
        with tab:
            y_data = working.get("years", {}).get(year, {})
            global_holidays = data.get("global_holidays", {})
            g_rows = []
            for s in y_data.get("seasons", []):
                for p in s.get("periods", []):
                    g_rows.append({
                        "Task": s["name"],
                        "Start": p["start"],
                        "Finish": p["end"],
                        "Type": get_season_bucket(s["name"])
                    })
            
            gh_list = global_holidays.get(year, {})
            for h in y_data.get("holidays", []):
                h_name = h.get("name", "(Unnamed Holiday)")
                global_ref = h.get("global_reference") or h_name
                gh_data = gh_list.get(global_ref)
                if gh_data:
                    start = gh_data.get("start_date")
                    end = gh_data.get("end_date")
                    if start and end:
                        g_rows.append({"Task": h_name, "Start": start, "Finish": end, "Type": "Holiday"})

            if g_rows:
                fig = render_gantt(g_rows)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("No dates set.")

# ----------------------------------------------------------------------
# SUMMARY
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
                    try:
                        pts = int(rp[room])
                    except:
                        pts = 0
                    weekly_totals[room] += pts * n_days
                    any_data = True
    return weekly_totals, any_data

def render_resort_summary_v2(working: Dict[str, Any]):
    st.markdown("<div class='section-header'>📊 Resort Summary</div>", unsafe_allow_html=True)
    room_types = get_all_room_types_for_resort(working)
    if not room_types:
        st.info("No room types.")
        return

    years = sorted(working.get("years", {}).keys())
    base_year = BASE_YEAR_FOR_POINTS if BASE_YEAR_FOR_POINTS in years else (years[0] if years else "2025")
    
    if base_year not in working.get("years", {}):
        st.warning(f"No data for {base_year}")
        return

    ref_year_data = working["years"][base_year]
    rows = []

    for s in ref_year_data.get("seasons", []):
        t, ok = compute_weekly_totals_for_season_v2(s, room_types)
        if ok:
            r = {"Season": s.get("name")}
            r.update({k: (v if v else "—") for k, v in t.items()})
            rows.append(r)
            
    for h in ref_year_data.get("holidays", []):
        rp = h.get("room_points", {})
        r = {"Season": f"Holiday - {h.get('name')}"}
        r.update({rt: (rp.get(rt) if rp.get(rt) else "—") for rt in room_types})
        rows.append(r)

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df.astype(str), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------
# GLOBAL SETTINGS
# ----------------------------------------------------------------------
def render_maintenance_fees_v2(data: Dict[str, Any]):
    rates = data.setdefault("configuration", {}).setdefault("maintenance_rates", {})
    st.caption("Define maintenance fee rates per point for each year")
    for year in sorted(rates.keys()):
        current_rate = float(rates[year])
        new_rate = st.number_input(f"💵 {year}", value=current_rate, step=0.01, format="%.4f", key=f"mf_{year}")
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
                    new_start = st.date_input("Start", safe_date(obj.get("start_date") or f"{year}-01-01"), key=f"ghs_{year}_{i}")
                with col2:
                    new_end = st.date_input("End", safe_date(obj.get("end_date") or f"{year}-01-07"), key=f"ghe_{year}_{i}")
                with col3:
                    if st.button("🗑️", key=f"ghd_{year}_{i}"):
                        del holidays[name]
                        save_data()
                        st.rerun()
                obj["start_date"] = new_start.isoformat()
                obj["end_date"] = new_end.isoformat()
                save_data()
        
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1: new_name = st.text_input("Name", key=f"gh_new_{year}", placeholder="New Holiday")
        with c2: new_start = st.date_input("Start", datetime.strptime(f"{year}-01-01", "%Y-%m-%d"), key=f"gh_ns_{year}")
        with c3: new_end = st.date_input("End", datetime.strptime(f"{year}-01-07", "%Y-%m-%d"), key=f"gh_ne_{year}")
        if st.button("➕ Add", key=f"gh_add_{year}", use_container_width=True) and new_name and new_name not in holidays:
            holidays[new_name] = {
                "start_date": new_start.isoformat(),
                "end_date": new_end.isoformat(),
                "type": "other",
                "regions": ["global"],
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
# MAIN
# ----------------------------------------------------------------------
def run():
    initialize_session_state()
    # Auto-load data file (optional)
    if st.session_state.data is None:
        try:
            with open("data_v2.json", "r") as f:
                raw_data = json.load(f)
                if "schema_version" in raw_data and "resorts" in raw_data:
                    st.session_state.data = raw_data
                    st.toast(f"Auto-loaded {len(raw_data.get('resorts', []))} resorts", icon="✅")
        except FileNotFoundError:
            pass
        except Exception as e:
            st.toast(f"Auto-load error: {str(e)}", icon="⚠️")

    with st.sidebar:
        st.divider()
        handle_file_upload()
        if st.session_state.data:
            handle_merge_from_another_file_v2(st.session_state.data)
            create_download_button_v2(st.session_state.data)
            handle_file_verification()

    render_page_header("Editor", "Creating Your Data File", icon="🏨", badge_color="#EF4444")
    
    if not st.session_state.data:
        st.info("Please load a file.")
        return

    data = st.session_state.data
    resorts = get_resort_list(data)
    years = get_years_from_data(data)
    current_resort_id = st.session_state.current_resort_id
    previous_resort_id = st.session_state.previous_resort_id
    
    render_resort_selector(resorts, current_resort_id)
    handle_resort_switch_v2(data, current_resort_id, previous_resort_id)
    
    working = load_resort(data, current_resort_id)
    if working:
        render_resort_card(working.get("display_name"), working.get("timezone"), working.get("address"))
        render_save_button_v2(data, working, current_resort_id)
        handle_resort_creation_v2(data, current_resort_id)
        handle_resort_deletion_v2(data, current_resort_id)
        render_validation_panel_v2(working, data, years)
        
        t1, t2, t3, t4, t5 = st.tabs(["Overview", "Seasons", "Points", "Holidays", "Summary"])
        
        with t1: edit_resort_basics(working, current_resort_id)
        with t2: 
            render_gantt_charts_v2(working, years, data)
            render_season_dates_editor_v2(working, years, current_resort_id)
        with t3: render_reference_points_editor_v2(working, years, current_resort_id)
        with t4: render_holiday_management_v2(working, years, current_resort_id)
        with t5: render_resort_summary_v2(working)

    st.markdown("---")
    render_global_settings_v2(data, years)

if __name__ == "__main__":
    run()
